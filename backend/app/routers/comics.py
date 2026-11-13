# Comics CRUD + valuation router. Every query is scoped to the signed-in user.

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from ..auth import current_user_id
from ..config import settings
from ..grading import estimate_report, slab_economics
from ..schemas import (
    ComicCreate,
    ComicOut,
    GradeReportIn,
    GradeReportOut,
    PricePointOut,
)
from ..supabase_client import get_supabase

router = APIRouter(prefix="/comics", tags=["comics"])


# ---------------------------------------------------------------- helpers


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def _data(res) -> Optional[dict]:
    # postgrest returns None (not an empty response) from maybe_single() on no rows.
    return getattr(res, "data", None) if res is not None else None


def owned_comic(sb, comic_id: str, user_id: str) -> dict:
    """The comic row if it belongs to user_id, else 404 (never 403, to avoid leaking ids)."""
    if not _is_uuid(comic_id):
        raise HTTPException(status_code=404, detail="Comic not found")
    res = (
        sb.table("comics")
        .select("*")
        .eq("id", comic_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    row = _data(res)
    if not row:
        raise HTTPException(status_code=404, detail="Comic not found")
    return row


def change_pcts(sb, comic_ids: list[str]) -> dict[str, float]:
    """Percent change from each comic's first recorded price to its latest one."""
    if not comic_ids:
        return {}
    rows = (
        sb.table("price_history")
        .select("comic_id, sale_date, price")
        .in_("comic_id", comic_ids)
        .order("sale_date", desc=False)
        .execute()
        .data
        or []
    )
    first: dict[str, float] = {}
    last: dict[str, float] = {}
    count: dict[str, int] = {}
    for r in rows:
        cid = r["comic_id"]
        first.setdefault(cid, float(r["price"]))
        last[cid] = float(r["price"])
        count[cid] = count.get(cid, 0) + 1
    return {
        cid: round((last[cid] / first[cid] - 1) * 100, 1)
        for cid in first
        if first[cid] > 0 and count[cid] > 1
    }


def to_out(row: dict, pct: Optional[float] = None) -> ComicOut:
    return ComicOut(**{**row, "change_pct": pct})


def _store_report(sb, comic_id: str, report: GradeReportIn) -> None:
    sb.table("grade_reports").upsert(
        {
            "comic_id": comic_id,
            "grade": report.grade,
            "grade_low": min(report.grade_low, report.grade),
            "grade_high": max(report.grade_high, report.grade),
            "confidence": report.confidence,
            "defects": [d.model_dump() for d in report.defects],
            "exterior_only": report.exterior_only,
            "source": report.source,
            "photos_used": report.photos_used,
        }
    ).execute()


# ------------------------------------------------------------------ comics


@router.get("", response_model=list[ComicOut])
def list_comics(
    grade_type: Optional[str] = Query(
        None, description="Filter by grade type: raw | cgc | cbcs | pgx | other"
    ),
    user_id: str = Depends(current_user_id),
    sb=Depends(get_supabase),
):
    query = sb.table("comics").select("*").eq("user_id", user_id).order("created_at", desc=True)
    if grade_type:
        query = query.eq("grade_type", grade_type)
    rows = query.execute().data or []
    pcts = change_pcts(sb, [r["id"] for r in rows])
    return [to_out(r, pcts.get(r["id"])) for r in rows]


@router.post("", response_model=ComicOut, status_code=201)
def create_comic(
    body: ComicCreate,
    user_id: str = Depends(current_user_id),
    sb=Depends(get_supabase),
):
    """Create a comic, or update it when `id` names one the caller already owns.

    Sending the same id twice is safe: the second call updates the first row,
    so a retried or two-step save never produces a duplicate book.
    """
    previous: Optional[dict] = None
    if body.id:
        if not _is_uuid(body.id):
            raise HTTPException(status_code=422, detail="id must be a uuid")
        previous = _data(
            sb.table("comics").select("*").eq("id", body.id).maybe_single().execute()
        )
        if previous and previous.get("user_id") != user_id:
            # Someone else's id: behave as if it does not exist.
            raise HTTPException(status_code=404, detail="Comic not found")

    # Only the fields the client sent, so an update never blanks other columns.
    row = body.model_dump(exclude_unset=True, exclude={"report"})
    row["id"] = body.id or str(uuid.uuid4())
    row["user_id"] = user_id
    if previous is None:
        # Fill defaults explicitly for brand new rows.
        row.setdefault("publisher", body.publisher)
        row.setdefault("grade_type", body.grade_type)

    # comics.user_id references profiles(id); make sure the profile row exists.
    sb.table("profiles").upsert({"id": user_id}, ignore_duplicates=True).execute()
    saved = sb.table("comics").upsert(row).execute().data[0]

    value = body.current_market_value
    if value is not None and (previous is None or previous.get("current_market_value") != value):
        source = "scan" if body.report else "manual"
        sb.table("price_history").insert(
            {"comic_id": saved["id"], "price": value, "source": source, "sale_date": str(date.today())}
        ).execute()

    if body.report:
        _store_report(sb, saved["id"], body.report)

    return to_out(saved, change_pcts(sb, [saved["id"]]).get(saved["id"]))


@router.get("/{comic_id}", response_model=ComicOut)
def get_comic(comic_id: str, user_id: str = Depends(current_user_id), sb=Depends(get_supabase)):
    row = owned_comic(sb, comic_id, user_id)
    return to_out(row, change_pcts(sb, [comic_id]).get(comic_id))


@router.delete("/{comic_id}", status_code=204)
def delete_comic(comic_id: str, user_id: str = Depends(current_user_id), sb=Depends(get_supabase)):
    owned_comic(sb, comic_id, user_id)
    sb.table("comics").delete().eq("id", comic_id).eq("user_id", user_id).execute()
    return None


# ------------------------------------------------------------ grade report


@router.get("/{comic_id}/grade_report", response_model=GradeReportOut)
def get_grade_report(
    comic_id: str, user_id: str = Depends(current_user_id), sb=Depends(get_supabase)
):
    """The stored scan report, or one estimated from the stored grade.

    Slab economics are always computed here from the comic's current value, so
    they move with the market instead of freezing at scan time.
    """
    comic = owned_comic(sb, comic_id, user_id)
    stored = _data(
        sb.table("grade_reports").select("*").eq("comic_id", comic_id).maybe_single().execute()
    )
    if not stored:
        return GradeReportOut(comic_id=comic_id, **estimate_report(comic).model_dump())

    grade = float(stored["grade"])
    return GradeReportOut(
        comic_id=comic_id,
        grade=grade,
        grade_low=float(stored["grade_low"]),
        grade_high=float(stored["grade_high"]),
        confidence=float(stored["confidence"]),
        defects=stored.get("defects") or [],
        exterior_only=bool(stored.get("exterior_only", True)),
        source=stored.get("source") or "estimate",
        photos_used=int(stored.get("photos_used") or 0),
        slab=slab_economics(grade, comic.get("grade_type"), comic.get("current_market_value")),
    )


# ----------------------------------------------------------- price history


@router.get("/{comic_id}/prices", response_model=list[PricePointOut])
def list_prices(comic_id: str, user_id: str = Depends(current_user_id), sb=Depends(get_supabase)):
    owned_comic(sb, comic_id, user_id)
    data = (
        sb.table("price_history")
        .select("*")
        .eq("comic_id", comic_id)
        .order("sale_date", desc=False)
        .execute()
        .data
        or []
    )
    return [PricePointOut(**row) for row in data]


@router.post("/{comic_id}/prices", response_model=PricePointOut, status_code=201)
def add_price(
    comic_id: str,
    price: float = Query(..., gt=0),
    source: str = Query("manual"),
    sale_date: Optional[date] = None,
    user_id: str = Depends(current_user_id),
    sb=Depends(get_supabase),
):
    owned_comic(sb, comic_id, user_id)
    if sale_date and sale_date > date.today():
        raise HTTPException(status_code=422, detail="sale_date cannot be in the future")
    row = {
        "comic_id": comic_id,
        "price": price,
        "source": source or "manual",
        "sale_date": str(sale_date or date.today()),
    }
    res = sb.table("price_history").insert(row).execute()
    # Keep the comic's current_market_value in sync with the latest sale.
    sb.table("comics").update({"current_market_value": price}).eq("id", comic_id).execute()
    return PricePointOut(**res.data[0])


# -------------------------------------------------------- valuation refresh


@router.post("/{comic_id}/refresh_value", response_model=PricePointOut)
async def refresh_value(
    comic_id: str, user_id: str = Depends(current_user_id), sb=Depends(get_supabase)
):
    """Re-value a comic from the source matching its grade_type.

    Slabbed books (cgc/cbcs/pgx) price via the GoCollect Insights API
    (grade-keyed); raw books use the raw-comps provider (mock until a raw
    comps partner is wired). Result lands in price_history with the source
    name and syncs current_market_value.
    """
    from ..pricing import provider_for_grade_type

    comic = owned_comic(sb, comic_id, user_id)
    provider = provider_for_grade_type(comic.get("grade_type"))
    try:
        quote = await provider.quote(
            title=comic["title"],
            issue_number=comic["issue_number"],
            grade=comic.get("estimated_grade"),
            slab_cert_number=comic.get("slab_cert_number"),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # network / provider errors
        raise HTTPException(status_code=502, detail=f"Price source error: {exc}")

    row = {
        "comic_id": comic_id,
        "price": quote.value,
        "source": quote.source,
        "sale_date": str(date.today()),
    }
    point = sb.table("price_history").insert(row).execute().data[0]
    sb.table("comics").update({"current_market_value": quote.value}).eq("id", comic_id).execute()
    return PricePointOut(**point)


# -------------------------------------------------------- cover image upload


@router.post("/{comic_id}/cover", response_model=ComicOut)
async def upload_cover(
    comic_id: str,
    image: UploadFile = File(...),
    user_id: str = Depends(current_user_id),
    sb=Depends(get_supabase),
):
    """Upload a cover image to Supabase Storage and attach its public URL."""
    owned_comic(sb, comic_id, user_id)
    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty image")
    ext = "jpg"
    if image.filename and "." in image.filename:
        ext = image.filename.rsplit(".", 1)[-1].lower() or "jpg"
    if ext not in {"jpg", "jpeg", "png", "webp", "heic"}:
        ext = "jpg"
    object_path = f"{comic_id}/cover.{ext}"
    bucket = settings.storage_bucket
    try:
        sb.storage.from_(bucket).upload(
            object_path, payload, {"content-type": image.content_type or "image/jpeg", "upsert": "true"}
        )
        public_url = sb.storage.from_(bucket).get_public_url(object_path)
    except Exception as exc:  # storage bucket missing / perms
        raise HTTPException(status_code=502, detail=f"Storage upload failed: {exc}")
    updated = (
        sb.table("comics")
        .update({"cover_image_url": public_url})
        .eq("id", comic_id)
        .eq("user_id", user_id)
        .execute()
    )
    return to_out(updated.data[0], change_pcts(sb, [comic_id]).get(comic_id))
