"""Pydantic models shared across routers."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

GradeType = Literal["raw", "cgc", "cbcs", "pgx", "other"]
ValueLens = Literal["all", "raw", "certified"]
SubmitVerdict = Literal["submit", "hold", "skip"]


class VisionResult(BaseModel):
    """Output of the AI vision pipeline for one scanned cover."""

    title: str = Field(..., examples=["Amazing Spider-Man"])
    issue_number: str = Field(..., examples=["300"])
    publisher: str = Field(default="Unknown", examples=["Marvel"])
    tentative_grade: float = Field(..., ge=0.1, le=10.0, examples=[9.2])
    signature_detected: bool = False
    notes: str = ""


# ------------------------------------------------------------ grade reports


class DefectScore(BaseModel):
    area: str
    score: float = Field(..., ge=0, le=10)
    note: str


class SlabEconomics(BaseModel):
    raw_value: float
    slabbed_value: float
    grading_fee: float
    shipping: float
    net_uplift: float
    turnaround_days: int
    verdict: SubmitVerdict


class GradeReportBody(BaseModel):
    """Explainable grade: range, per-area breakdown, and (for raw books) slab maths."""

    grade: float = Field(..., ge=0.5, le=10)
    grade_low: float = Field(..., ge=0.5, le=10)
    grade_high: float = Field(..., ge=0.5, le=10)
    confidence: float = Field(..., ge=0, le=1)
    defects: list[DefectScore] = Field(default_factory=list)
    exterior_only: bool = True
    # 'claude:<model>', 'openai:<model>', 'mock', or 'estimate' (built from the stored grade)
    source: str = "estimate"
    photos_used: int = 0
    slab: Optional[SlabEconomics] = None


class GradeReportOut(GradeReportBody):
    comic_id: str


class GradeReportIn(BaseModel):
    """A report the client got from POST /vision/grade, stored with the comic."""

    grade: float = Field(..., ge=0.5, le=10)
    grade_low: float = Field(..., ge=0.5, le=10)
    grade_high: float = Field(..., ge=0.5, le=10)
    confidence: float = Field(..., ge=0, le=1)
    defects: list[DefectScore] = Field(default_factory=list)
    exterior_only: bool = True
    source: str = "estimate"
    photos_used: int = Field(1, ge=0, le=3)


# ------------------------------------------------------------------ comics


class ComicCreate(BaseModel):
    # Optional client id: sending the same id again updates that row instead of
    # inserting a second one (the scanner saves, then attaches the cover).
    id: Optional[str] = None
    title: str
    issue_number: str
    publisher: str = "Unknown"
    year: Optional[int] = Field(None, ge=1800, le=2100)
    key_note: Optional[str] = None
    cover_image_url: Optional[str] = None
    estimated_grade: Optional[float] = Field(None, ge=0.1, le=10.0)
    # 'raw' = our camera/AI estimate; others = professionally slabbed
    grade_type: GradeType = "raw"
    slab_cert_number: Optional[str] = None
    current_market_value: Optional[float] = Field(None, ge=0)
    # Stored as the comic's grade report when present (scan results).
    report: Optional[GradeReportIn] = None


class ComicOut(BaseModel):
    id: str
    title: str
    issue_number: str
    publisher: str
    year: Optional[int] = None
    key_note: Optional[str] = None
    cover_image_url: Optional[str] = None
    estimated_grade: Optional[float] = None
    grade_type: str = "raw"
    slab_cert_number: Optional[str] = None
    current_market_value: Optional[float] = None
    # Percent change between the first and latest recorded price.
    change_pct: Optional[float] = None
    user_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True, "extra": "ignore"}


class PricePointOut(BaseModel):
    comic_id: str
    sale_date: date
    price: float
    source: str

    model_config = {"from_attributes": True, "extra": "ignore"}


# --------------------------------------------------------------- portfolio


class PortfolioPoint(BaseModel):
    month: str  # YYYY-MM
    value: float
    # 'snapshot' when a nightly snapshot covered the month, else 'price_history'
    source: Literal["snapshot", "price_history", "live"]


class PortfolioHistory(BaseModel):
    lens: ValueLens
    points: list[PortfolioPoint]


class SnapshotOut(BaseModel):
    user_id: str
    snapshot_date: date
    lens: ValueLens
    total_value: float
    book_count: int


# -------------------------------------------------------------------- runs


class RunGap(BaseModel):
    id: str
    name: str
    publisher: str
    owned: int
    total: int
    missing_key: str
    missing_note: str
    raw_price: float
    slab_price: float


# ----------------------------------------------------------------- scanning


class ScanIdentification(BaseModel):
    title: str
    issue_number: str
    publisher: str = "Unknown"
    year: Optional[int] = None
    key_note: Optional[str] = None
    signature_detected: bool = False
    notes: str = ""


class GradeScanResult(BaseModel):
    """Response of POST /vision/grade: who the book is plus its full grade report."""

    identification: ScanIdentification
    report: GradeReportBody
    # How sure the model is that the identification is right (0-1).
    match_confidence: float = Field(..., ge=0, le=1)
    estimated_value: Optional[float] = None
    value_source: Optional[str] = None
