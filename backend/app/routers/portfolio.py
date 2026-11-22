# Collection value over time (Vault chart) and the nightly snapshot job.

from __future__ import annotations

import hmac
from collections import defaultdict
from datetime import date
from typing import Iterable

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from ..auth import current_user_id
from ..config import settings
from ..schemas import PortfolioHistory, PortfolioPoint, SnapshotOut, ValueLens
from ..supabase_client import get_supabase

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

LENSES: tuple[ValueLens, ...] = ("all", "raw", "certified")
PAGE = 1000  # PostgREST's default row cap per request


def in_lens(grade_type: str | None, lens: str) -> bool:
    raw = (grade_type or "raw") == "raw"
    return lens == "all" or (raw if lens == "raw" else not raw)


def month_starts(today: date, months: int) -> list[date]:
    """First day of each of the last `months` months, oldest first, ending with today's month."""
    out = []
    y, m = today.year, today.month
    for _ in range(months):
        out.append(date(y, m, 1))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def month_end(start: date) -> date:
    nxt = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return date.fromordinal(nxt.toordinal() - 1)


def _paged(query_factory) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        page = query_factory().range(offset, offset + PAGE - 1).execute().data or []
        rows.extend(page)
        if len(page) < PAGE:
            return rows
        offset += PAGE


def totals(comics: Iterable[dict]) -> dict[str, tuple[float, int]]:
    """(total value, book count) per lens."""
    out = {lens: [0.0, 0] for lens in LENSES}
    for c in comics:
        value = float(c.get("current_market_value") or 0)
        for lens in LENSES:
            if in_lens(c.get("grade_type"), lens):
                out[lens][0] += value
                out[lens][1] += 1
    return {lens: (round(v, 2), n) for lens, (v, n) in out.items()}


def write_snapshots(sb, user_id: str, comics: list[dict], today: date) -> list[SnapshotOut]:
    rows = [
        {
            "user_id": user_id,
            "snapshot_date": str(today),
            "lens": lens,
            "total_value": value,
            "book_count": count,
        }
        for lens, (value, count) in totals(comics).items()
    ]
    sb.table("portfolio_snapshots").upsert(rows, on_conflict="user_id,snapshot_date,lens").execute()
    return [SnapshotOut(**r) for r in rows]


@router.get("/history", response_model=PortfolioHistory)
def history(
    lens: ValueLens = Query("all"),
    months: int = Query(10, ge=2, le=36),
    user_id: str = Depends(current_user_id),
    sb=Depends(get_supabase),
):
    """Month-end collection value for the last `months` months.

    Each past month uses that month's latest nightly snapshot when one exists,
    and otherwise rebuilds the value from price_history (each book's latest
    price on or before month end). The current month is the live total.
    """
    today = date.today()
    starts = month_starts(today, months)

    comics = [
        c
        for c in sb.table("comics")
        .select("id, grade_type, current_market_value")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
        if in_lens(c.get("grade_type"), lens)
    ]
    ids = [c["id"] for c in comics]

    prices: dict[str, list[tuple[str, float]]] = defaultdict(list)
    if ids:
        for r in _paged(
            lambda: sb.table("price_history")
            .select("comic_id, sale_date, price")
            .in_("comic_id", ids)
            .order("sale_date", desc=False)
            .order("id", desc=False)
        ):
            prices[r["comic_id"]].append((str(r["sale_date"]), float(r["price"])))

    snaps: dict[str, float] = {}
    for s in (
        sb.table("portfolio_snapshots")
        .select("snapshot_date, total_value")
        .eq("user_id", user_id)
        .eq("lens", lens)
        .gte("snapshot_date", str(starts[0]))
        .order("snapshot_date", desc=False)
        .execute()
        .data
        or []
    ):
        # Ordered ascending, so the last write per month is that month's latest.
        snaps[str(s["snapshot_date"])[:7]] = float(s["total_value"])

    points: list[PortfolioPoint] = []
    for start in starts:
        key = start.strftime("%Y-%m")
        if start.year == today.year and start.month == today.month:
            live = sum(float(c.get("current_market_value") or 0) for c in comics)
            points.append(PortfolioPoint(month=key, value=round(live), source="live"))
            continue
        if key in snaps:
            points.append(PortfolioPoint(month=key, value=round(snaps[key]), source="snapshot"))
            continue
        cutoff = str(month_end(start))
        total = 0.0
        for c in comics:
            history = prices.get(c["id"])
            if not history:
                total += float(c.get("current_market_value") or 0)
                continue
            before = [p for d, p in history if d <= cutoff]
            # Books with a short history carry their first known price back,
            # matching the demo chart.
            total += before[-1] if before else history[0][1]
        points.append(PortfolioPoint(month=key, value=round(total), source="price_history"))

    return PortfolioHistory(lens=lens, points=points)


@router.post("/snapshot", response_model=list[SnapshotOut])
def snapshot_me(user_id: str = Depends(current_user_id), sb=Depends(get_supabase)):
    """Record today's totals (all, raw, certified) for the signed-in user."""
    comics = (
        sb.table("comics")
        .select("grade_type, current_market_value")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    return write_snapshots(sb, user_id, comics, date.today())


@router.post("/snapshot/all")
def snapshot_all(
    x_cron_secret: str | None = Header(default=None),
    sb=Depends(get_supabase),
) -> dict:
    """Nightly job: snapshot every user with books. Needs the X-Cron-Secret header."""
    if not settings.cron_secret:
        raise HTTPException(status_code=404, detail="Not found")
    if not x_cron_secret or not hmac.compare_digest(x_cron_secret, settings.cron_secret):
        raise HTTPException(status_code=401, detail="Bad cron secret")

    rows = _paged(
        lambda: sb.table("comics")
        .select("user_id, grade_type, current_market_value")
        .order("user_id")
        .order("id")
    )
    by_user: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("user_id"):
            by_user[r["user_id"]].append(r)
    today = date.today()
    for uid, books in by_user.items():
        write_snapshots(sb, uid, books, today)
    return {"users": len(by_user), "snapshot_date": str(today)}
