# Comics CRUD + valuation router.

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from ..schemas import ComicCreate, ComicOut, PricePointOut
from ..supabase_client import get_supabase

router = APIRouter(prefix="/comics", tags=["comics"])


@router.get("", response_model=list[ComicOut])
def list_comics(
    user_id: Optional[str] = Query(None, description="Filter by Supabase user id"),
    grade_type: Optional[str] = Query(
        None, description="Filter by grade type: raw | cgc | cbcs | pgx | other"
    ),
    sb=Depends(get_supabase),
):
    query = sb.table("comics").select("*").order("created_at", desc=True)
    if user_id:
        query = query.eq("user_id", user_id)
    if grade_type:
        query = query.eq("grade_type", grade_type)
    data = query.execute().data or []
    return [ComicOut(**row) for row in data]


@router.post("", response_model=ComicOut, status_code=201)
def create_comic(body: ComicCreate, sb=Depends(get_supabase)):
    row = body.model_dump()
    row.setdefault("id", str(uuid.uuid4()))
    res = sb.table("comics").insert(row).execute()
    return ComicOut(**(res.data[0]))


@router.get("/{comic_id}", response_model=ComicOut)
def get_comic(comic_id: str, sb=Depends(get_supabase)):
    res = sb.table("comics").select("*").eq("id", comic_id).maybe_single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Comic not found")
    return ComicOut(**res.data)


@router.delete("/{comic_id}", status_code=204)
def delete_comic(comic_id: str, sb=Depends(get_supabase)):
    sb.table("comics").delete().eq("id", comic_id).execute()
    return None


# ---------------------- price history ----------------------


@router.get("/{comic_id}/prices", response_model=list[PricePointOut])
def list_prices(comic_id: str, sb=Depends(get_supabase)):
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
    sb=Depends(get_supabase),
):
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


# ---------------------- valuation refresh ----------------------


@router.post("/{comic_id}/refresh_value", response_model=PricePointOut)
async def refresh_value(comic_id: str, sb=Depends(get_supabase)):
    """Re-value a comic from the source matching its grade_type.

    Slabbed books (cgc/cbcs/pgx) price via the GoCollect Insights API
    (grade-keyed); raw books use the raw-comps provider (mock until a raw
    comps partner is wired). Result lands in price_history with the source
    name and syncs current_market_value.
    """
    from ..pricing import provider_for_grade_type

    res = sb.table("comics").select("*").eq("id", comic_id).maybe_single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Comic not found")
    comic = res.data

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


# ---------------------- cover image upload ----------------------


@router.post("/{comic_id}/cover", response_model=ComicOut)
async def upload_cover(
    comic_id: str,
    image: UploadFile = File(...),
    sb=Depends(get_supabase),
):
    """Upload a cover image to Supabase Storage and attach its public URL."""
    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty image")
    ext = "jpg"
    if image.filename and "." in image.filename:
        ext = image.filename.rsplit(".", 1)[-1].lower() or "jpg"
    object_path = f"{comic_id}/cover.{ext}"
    res = sb.table("comics").select("*").eq("id", comic_id).maybe_single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Comic not found")
    try:
        sb.storage.from_("cover-images").upload(
            object_path, payload, {"content-type": image.content_type or "image/jpeg", "upsert": "true"}
        )
        public_url = sb.storage.from_("cover-images").get_public_url(object_path)
    except Exception as exc:  # storage bucket missing / perms
        raise HTTPException(status_code=502, detail=f"Storage upload failed: {exc}")
    updated = sb.table("comics").update({"cover_image_url": public_url}).eq("id", comic_id).execute()
    return ComicOut(**updated.data[0])