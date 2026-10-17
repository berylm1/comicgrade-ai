"""Pydantic models shared across routers."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class VisionResult(BaseModel):
    """Output of the AI vision pipeline for one scanned cover."""

    title: str = Field(..., examples=["Amazing Spider-Man"])
    issue_number: str = Field(..., examples=["300"])
    publisher: str = Field(default="Unknown", examples=["Marvel"])
    tentative_grade: float = Field(..., ge=0.1, le=10.0, examples=[9.2])
    signature_detected: bool = False
    notes: str = ""


class ComicCreate(BaseModel):
    title: str
    issue_number: str
    publisher: str = "Unknown"
    cover_image_url: Optional[str] = None
    estimated_grade: Optional[float] = Field(None, ge=0.1, le=10.0)
    # 'raw' = our camera/AI estimate; others = professionally slabbed
    grade_type: Literal["raw", "cgc", "cbcs", "pgx", "other"] = "raw"
    slab_cert_number: Optional[str] = None
    current_market_value: Optional[float] = Field(None, ge=0)
    user_id: Optional[str] = None


class ComicOut(BaseModel):
    id: str
    title: str
    issue_number: str
    publisher: str
    cover_image_url: Optional[str] = None
    estimated_grade: Optional[float] = None
    grade_type: str = "raw"
    slab_cert_number: Optional[str] = None
    current_market_value: Optional[float] = None
    user_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PricePointOut(BaseModel):
    comic_id: str
    sale_date: date
    price: float
    source: str

    model_config = {"from_attributes": True}


GradingSource = Literal["vision", "manual", "cgc"]