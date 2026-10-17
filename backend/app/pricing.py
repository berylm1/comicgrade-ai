"""Pluggable valuation sources.

Design rationale (market research 2026-10): slabbed (CGC/CBCS) books and raw
books need DIFFERENT price sources, and mixing them skews portfolio valuations.

- Slabbed: GoCollect Insights API is the primary source — it prices by
  certification grade (`GET /v1/insights/item/{id}?grade=9.8`). Requires an
  API key (free account = basic access; full FMV = Pro/Enterprise).
- Raw: no sanctioned free comps API exists (eBay killed findCompletedItems in
  Feb 2025; GPA has no API). Until a raw-comps partner is wired, raw books use
  the mock provider so the prototype stays demoable end to end.

Every provider returns a PriceQuote; the value refresh routes on the comic's
`grade_type` and records which source produced the number in price_history.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional, Protocol

import httpx

from .config import settings


@dataclass(frozen=True)
class PriceQuote:
    value: float
    source: str  # stored in price_history.source, e.g. "gocollect", "mock"


class PriceProvider(Protocol):
    async def quote(
        self,
        *,
        title: str,
        issue_number: str,
        grade: Optional[float],
        slab_cert_number: Optional[str],
    ) -> PriceQuote: ...


# ---------------------------------------------------------------------------
# Mock — deterministic pseudo-quote per (title, issue, grade). Demo default.
# ---------------------------------------------------------------------------
_RAW_BASE: list[tuple[str, float]] = [
    ("Amazing Spider-Man 300", 400.0),
    ("Invincible 1", 60.0),
    ("Spawn 1", 25.0),
]


class MockProvider:
    source = "mock"

    async def quote(
        self,
        *,
        title: str,
        issue_number: str,
        grade: Optional[float],
        slab_cert_number: Optional[str],
    ) -> PriceQuote:
        key = f"{title} {issue_number}".lower()
        # Equality scan, not dict hashing — equal strings must compare equal.
        base = next((b for k, b in _RAW_BASE if k.lower() == key), None)
        if base is None:
            base = 12.0 + (len(title) % 7) * 3.5
        g = grade if grade is not None else 5.0
        # Grade exponent mimics real raw curves: condition drives value hard.
        value = base * (max(g, 0.5) / 9.8) ** 2.2
        value = round(max(value, 0.5) * random.Random(f"{key}{g}").uniform(0.92, 1.08), 2)
        return PriceQuote(value=value, source=self.source)


# ---------------------------------------------------------------------------
# GoCollect — slabbed books (CGC/CBCS). Bearer-key Insights API.
# ---------------------------------------------------------------------------
class GoCollectProvider:
    source = "gocollect"
    base_url = "https://api.gocollect.com/v1"

    async def quote(
        self,
        *,
        title: str,
        issue_number: str,
        grade: Optional[float],
        slab_cert_number: Optional[str],
    ) -> PriceQuote:
        key = settings.gocollect_api_key
        if not key:
            # No key configured: degrade to the mock provider rather than fail
            # the refresh, but label the source honestly.
            fallback = await MockProvider().quote(
                title=title, issue_number=issue_number, grade=grade,
                slab_cert_number=slab_cert_number,
            )
            return PriceQuote(value=fallback.value, source="mock (no GoCollect key)")
        # 1. Resolve the GoCollect item id from title + issue.
        async with httpx.AsyncClient(timeout=30) as client:
            search = await client.get(
                f"{self.base_url}/collectibles",
                headers={"Authorization": f"Bearer {key}"},
                params={"q": f"{title} #{issue_number}", "market": "comics"},
            )
            search.raise_for_status()
            items = (search.json() or {}).get("data") or []
            if not items:
                raise LookupError(f"No GoCollect match for {title} #{issue_number}")
            item_id = items[0]["id"]
            # 2. Grade-specific valuation insight.
            insight = await client.get(
                f"{self.base_url}/insights/item/{item_id}",
                headers={"Authorization": f"Bearer {key}"},
                params={"grade": str(grade or 9.8)},
            )
            insight.raise_for_status()
            data = insight.json() or {}
            value = data.get("fmv") or data.get("value")
            if value is None:
                raise LookupError("GoCollect insight returned no valuation")
        return PriceQuote(value=round(float(value), 2), source=self.source)


def provider_for_grade_type(grade_type: Optional[str]) -> PriceProvider:
    """Route: slabbed books -> GoCollect, raw books -> raw-comps provider."""
    if grade_type and grade_type != "raw":
        return GoCollectProvider()
    return MockProvider()