# Series run gaps for the Insights screen: catalog vs the user's owned books.

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends

from ..auth import current_user_id
from ..schemas import RunGap
from ..supabase_client import get_supabase

router = APIRouter(prefix="/runs", tags=["runs"])


def issue_int(value) -> Optional[int]:
    text = str(value or "").strip().lstrip("#")
    return int(text) if text.isdigit() else None


def _key_rank(issue: dict) -> tuple:
    # Prefer catalogued keys, then the priciest slab, then the priciest raw copy,
    # then the earliest issue.
    return (
        0 if issue.get("key_note") else 1,
        -float(issue.get("slab_price") or 0),
        -float(issue.get("raw_price") or 0),
        issue["n"],
    )


def compute_gaps(series: list[dict], issues: list[dict], comics: list[dict]) -> list[RunGap]:
    by_series: dict[str, dict[int, dict]] = defaultdict(dict)
    for row in issues:
        n = issue_int(row.get("issue_number"))
        if n is not None:
            by_series[row["series_id"]][n] = {**row, "n": n}

    gaps: list[RunGap] = []
    for s in series:
        first, last = int(s["first_issue"]), int(s["last_issue"])
        match = str(s["match_title"]).strip().lower()
        owned = {
            n
            for c in comics
            if (c.get("series_id") == s["id"] or str(c.get("title", "")).strip().lower() == match)
            and (n := issue_int(c.get("issue_number"))) is not None
            and first <= n <= last
        }
        total = last - first + 1
        if not owned or len(owned) >= total:
            continue
        catalog = by_series.get(s["id"], {})
        missing = [catalog.get(n, {"n": n}) for n in range(first, last + 1) if n not in owned]
        key = min(missing, key=_key_rank)
        gaps.append(
            RunGap(
                id=str(s["id"]),
                name=s["name"],
                publisher=s["publisher"],
                owned=len(owned),
                total=total,
                missing_key=f"#{key['n']}",
                missing_note=key.get("key_note") or f"Next missing issue in the run ({len(missing)} to go)",
                raw_price=float(key.get("raw_price") or 0),
                slab_price=float(key.get("slab_price") or 0),
            )
        )
    gaps.sort(key=lambda g: (-g.owned / g.total, g.name))
    return gaps


@router.get("/gaps", response_model=list[RunGap])
def run_gaps(user_id: str = Depends(current_user_id), sb=Depends(get_supabase)):
    """Runs the user has started but not finished, with the best issue to buy next."""
    comics = (
        sb.table("comics")
        .select("title, issue_number, series_id")
        .eq("user_id", user_id)
        .execute()
        .data
        or []
    )
    if not comics:
        return []
    series = sb.table("series").select("*").execute().data or []
    if not series:
        return []
    issues = (
        sb.table("series_issues")
        .select("*")
        .in_("series_id", [s["id"] for s in series])
        .execute()
        .data
        or []
    )
    return compute_gaps(series, issues, comics)
