"""Claude vision grading (VISION_PROVIDER=claude).

Sends one to three photos (front, back, spine) to Claude and gets back the
identification plus a full grade report as structured output (JSON that
matches GRADE_SCHEMA). Server-side refusal fallbacks are on, so a request a
safety classifier declines is retried on a fallback model in the same call.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Optional

import anthropic
from anthropic import AsyncAnthropic
from pydantic import BaseModel, ValidationError

from .config import settings
from .grading import AREA_NAMES, normalize_report
from .schemas import DefectScore, GradeReportBody, ScanIdentification

CLAUDE_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
CLAUDE_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # per-image limit for base64 images
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# The CGC 10-point scale. Grades are snapped to these steps.
CGC_STEPS = [
    0.5, 1.0, 1.5, 1.8, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5,
    7.0, 7.5, 8.0, 8.5, 9.0, 9.2, 9.4, 9.6, 9.8, 10.0,
]

_nullable = lambda t: {"anyOf": [{"type": t}, {"type": "null"}]}  # noqa: E731

GRADE_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "is_comic", "identification", "match_confidence", "grade", "grade_low",
        "grade_high", "confidence", "defects", "notes",
    ],
    "properties": {
        "is_comic": {"type": "boolean"},
        "identification": {
            "type": "object",
            "additionalProperties": False,
            "required": ["title", "issue_number", "publisher", "year", "key_note", "signature_detected"],
            "properties": {
                "title": {"type": "string"},
                "issue_number": {"type": "string"},
                "publisher": {"type": "string"},
                "year": _nullable("integer"),
                "key_note": _nullable("string"),
                "signature_detected": {"type": "boolean"},
            },
        },
        "match_confidence": {"type": "number"},
        "grade": {"type": "number"},
        "grade_low": {"type": "number"},
        "grade_high": {"type": "number"},
        "confidence": {"type": "number"},
        "defects": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["area", "score", "note"],
                "properties": {
                    "area": {"type": "string", "enum": AREA_NAMES},
                    "score": {"type": "number"},
                    "note": {"type": "string"},
                },
            },
        },
        "notes": {"type": "string"},
    },
}

SYSTEM_PROMPT = f"""You are an experienced comic book grader working to CGC standards. \
You receive photos of one comic book and return its identification and a condition grade.

Identification: read the title, issue number and publisher from the cover and indicia \
area you can see. Give the cover year if it is printed or you know it for that issue. \
key_note is a short reason the issue matters to collectors (for example a first \
appearance), or null when it is not a notable issue. Do not guess a key you are not sure of. \
match_confidence (0 to 1) is how sure you are of the title and issue number.

Grading: use the CGC 10-point scale ({", ".join(str(s) for s in CGC_STEPS)}). Score each \
of these areas on the same scale, with a short note naming what you see: \
{", ".join(AREA_NAMES)}. The overall grade is driven by the worst significant defect, not \
the average. grade_low and grade_high bound where a professional grade would most likely \
land; widen the range when photos are blurry, dark, cropped, or when only the front was sent. \
confidence (0 to 1) is how likely a professional grade lands inside that range.

You only see the exterior. You cannot see interior pages, page quality, or most restoration, \
so do not claim anything about them. Mention in notes anything that limited your view \
(glare, a bag or slab, missing photos). If the photos do not show a comic book, set \
is_comic to false and fill the other fields with your best placeholders."""

PHOTO_LABELS = {"front": "Front cover", "back": "Back cover", "spine": "Spine"}


@dataclass
class Photo:
    role: str  # front | back | spine
    data: bytes
    media_type: str


class GradingError(Exception):
    """The model call failed or returned something unusable."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class GradingRefused(GradingError):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)


class _ModelDefect(BaseModel):
    # No range checks here: out-of-scale scores are clamped, not rejected.
    area: str
    score: float
    note: str


class _ModelGrade(BaseModel):
    """Validates the parsed JSON before it is trusted."""

    is_comic: bool
    identification: ScanIdentification
    match_confidence: float
    grade: float
    grade_low: float
    grade_high: float
    confidence: float
    defects: list[_ModelDefect]
    notes: str


@dataclass
class ClaudeGrade:
    identification: ScanIdentification
    report: GradeReportBody
    match_confidence: float
    model: str


def snap(grade: float) -> float:
    return min(CGC_STEPS, key=lambda s: (abs(s - grade), s))


def build_content(photos: list[Photo]) -> list[dict]:
    content: list[dict] = []
    for i, photo in enumerate(photos, start=1):
        content.append({"type": "text", "text": f"Photo {i}: {PHOTO_LABELS.get(photo.role, photo.role)}"})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": photo.media_type,
                    "data": base64.standard_b64encode(photo.data).decode("ascii"),
                },
            }
        )
    roles = ", ".join(PHOTO_LABELS.get(p.role, p.role).lower() for p in photos)
    content.append({"type": "text", "text": f"Identify and grade this comic. Photos sent: {roles}."})
    return content


def parse_response(response, photos_used: int) -> ClaudeGrade:
    """Turn a Messages API response into identification + report, or raise."""
    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        explanation = getattr(details, "explanation", None) if details else None
        raise GradingRefused(explanation or "The grading model declined these photos.")
    if response.stop_reason == "max_tokens":
        raise GradingError("The grading response was cut off. Try again.")

    text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), None)
    if not text:
        raise GradingError("The grading model returned no result.")
    try:
        parsed = _ModelGrade.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise GradingError(f"The grading model returned an unexpected shape: {exc}")

    if not parsed.is_comic:
        raise GradingError("These photos do not look like a comic book. Frame the cover and try again.", 422)

    grade, low, high, conf, defects = normalize_report(
        snap(parsed.grade),
        parsed.grade_low,
        parsed.grade_high,
        parsed.confidence,
        [DefectScore(area=d.area, score=min(10.0, max(0.0, d.score)), note=d.note) for d in parsed.defects],
    )
    low, high = snap(low), snap(high)
    ident = parsed.identification
    notes = " ".join(s for s in (ident.notes, parsed.notes) if s).strip()
    identification = ident.model_copy(
        update={
            "title": ident.title.strip() or "Unknown",
            "issue_number": ident.issue_number.strip().lstrip("#") or "?",
            "publisher": ident.publisher.strip() or "Unknown",
            "key_note": (ident.key_note or "").strip() or None,
            "notes": notes,
        }
    )
    report = GradeReportBody(
        grade=grade,
        grade_low=min(low, grade),
        grade_high=max(high, grade),
        confidence=conf,
        defects=defects,
        exterior_only=True,
        source=f"claude:{response.model}",
        photos_used=photos_used,
    )
    return ClaudeGrade(
        identification=identification,
        report=report,
        match_confidence=round(min(1.0, max(0.0, parsed.match_confidence)), 2),
        model=response.model,
    )


def validate_photo(photo: Photo) -> None:
    if photo.media_type not in CLAUDE_IMAGE_TYPES:
        raise GradingError(
            f"{PHOTO_LABELS.get(photo.role, photo.role)}: {photo.media_type or 'unknown type'} "
            "is not supported. Send JPEG, PNG or WebP.",
            415,
        )
    if len(photo.data) > CLAUDE_MAX_IMAGE_BYTES:
        raise GradingError(
            f"{PHOTO_LABELS.get(photo.role, photo.role)} is over 5 MB. Lower the camera quality.", 413
        )


_client: Optional[AsyncAnthropic] = None


def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        # api_key=None lets the SDK resolve credentials from the environment.
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def grade_with_claude(photos: list[Photo], client: Optional[AsyncAnthropic] = None) -> ClaudeGrade:
    if not 1 <= len(photos) <= 3:
        raise GradingError("Send one to three photos (front, back, spine).", 422)
    for photo in photos:
        validate_photo(photo)

    client = client or get_client()
    try:
        response = await client.beta.messages.create(
            model=settings.claude_vision_model,
            max_tokens=16000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            thinking={"type": "adaptive"},
            output_config={
                "effort": settings.claude_effort,
                "format": {"type": "json_schema", "schema": GRADE_SCHEMA},
            },
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_content(photos)}],
        )
    except anthropic.AuthenticationError:
        raise GradingError("ANTHROPIC_API_KEY is missing or invalid on the server.", 500)
    except anthropic.RateLimitError:
        raise GradingError("Grading is busy right now. Try again in a minute.", 429)
    except anthropic.BadRequestError as exc:
        raise GradingError(f"Grading request rejected: {exc.message}", 502)
    except anthropic.APIStatusError as exc:
        raise GradingError(f"Grading service error ({exc.status_code}). Try again.", 502)
    except anthropic.APIConnectionError:
        raise GradingError("Could not reach the grading service.", 503)

    return parse_response(response, photos_used=len(photos))
