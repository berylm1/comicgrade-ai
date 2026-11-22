# Value estimates for a book that is not saved yet (the scan review screen
# re-prices when the user picks a different identification).

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import current_user_id
from ..pricing import provider_for_grade_type
from ..schemas import GradeType, PriceEstimate

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.get("/estimate", response_model=PriceEstimate)
async def estimate(
    title: str = Query(..., min_length=1),
    issue_number: str = Query(..., min_length=1),
    grade: Optional[float] = Query(None, ge=0.5, le=10),
    grade_type: GradeType = Query("raw"),
    _user: str = Depends(current_user_id),
):
    """Value for a title, issue and grade from the source for that grade type.

    Raw books use the mock raw-comps provider (source "mock") until a real raw
    comps source is chosen, so treat raw values as sample estimates.
    """
    try:
        quote = await provider_for_grade_type(grade_type).quote(
            title=title, issue_number=issue_number, grade=grade, slab_cert_number=None
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Price source error: {exc}")
    return PriceEstimate(value=quote.value, source=quote.source)
