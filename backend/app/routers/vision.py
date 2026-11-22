# AI vision pipeline router.
#
# POST /vision/analyze receives one cover image and returns a tentative
# identification + grade. POST /vision/grade receives up to three photos
# (front, back, spine) and returns the identification plus the full grade report.
#
# Providers (VISION_PROVIDER): "mock" (default, no keys), "openai", "claude".
# Only Claude reads all three photos and scores each area; mock and openai
# grade the front cover and the report is estimated from that grade.

from __future__ import annotations

import base64
import random
from typing import Final

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..auth import current_user_id
from ..claude_grader import GradingError, Photo, grade_with_claude
from ..config import settings
from ..grading import estimate_report, slab_economics
from ..pricing import MockProvider
from ..schemas import GradeScanResult, ScanIdentification, VisionResult

router = APIRouter(prefix="/vision", tags=["vision"])

_ALLOWED_TYPES: Final[set[str]] = {"image/jpeg", "image/png", "image/heic", "image/webp"}
_MAX_BYTES: Final[int] = 10 * 1024 * 1024  # 10 MB


# --------------------------------------------------------------------------
# Mock pipeline — deterministic-ish pseudo analysis so the app is demoable
# with zero API keys.
# --------------------------------------------------------------------------
_FAKE_BOOKS: Final[list[dict]] = [
    {"title": "Amazing Spider-Man", "issue_number": "300", "publisher": "Marvel", "grade": 9.2},
    {"title": "Batman", "issue_number": "423", "publisher": "DC", "grade": 8.5},
    {"title": "Mighty Morphin Power Rangers", "issue_number": "1", "publisher": "Boom! Studios", "grade": 9.6},
    {"title": "X-Men", "issue_number": "1", "publisher": "Marvel", "grade": 7.0},
    {"title": "Spawn", "issue_number": "1", "publisher": "Image", "grade": 9.4},
    {"title": "Invincible", "issue_number": "1", "publisher": "Image", "grade": 9.8},
]


def _mock_analysis(image_bytes: bytes) -> VisionResult:
    seed = sum(image_bytes[:64]) if image_bytes else 0
    rng = random.Random(seed)
    pick = _FAKE_BOOKS[rng.randrange(len(_FAKE_BOOKS))]
    # Nudge the grade +/- 0.4 so identical images don't feel canned.
    grade = round(min(10.0, max(0.5, pick["grade"] + rng.uniform(-0.4, 0.4))), 1)
    return VisionResult(
        title=pick["title"],
        issue_number=pick["issue_number"],
        publisher=pick["publisher"],
        tentative_grade=grade,
        notes="Mock vision analysis (VISION_PROVIDER=mock). Wire a real provider in config.py.",
    )


# --------------------------------------------------------------------------
# OpenAI-compatible vision endpoint
# --------------------------------------------------------------------------
async def _openai_analysis(image_bytes: bytes, content_type: str) -> VisionResult:
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    b64 = base64.b64encode(image_bytes).decode()
    payload = {
        "model": settings.openai_vision_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a professional comic book grader. Identify the comic and "
                    "estimate an Overstreet/CGC-style grade from 0.5 to 10 in 0.1 steps. "
                    'Reply ONLY with JSON: {"title","issue_number","publisher",'
                    '"tentative_grade","signature_detected","notes"}'
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Identify and grade this comic cover."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{content_type};base64,{b64}"},
                    },
                ],
            },
        ],
        "max_tokens": 500,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=payload,
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Vision provider error: {resp.status_code}")
    content = resp.json()["choices"][0]["message"]["content"]
    import json

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Model wrapped the JSON in prose/markdown — take the first {...} block.
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end == -1:
            raise HTTPException(status_code=502, detail="Vision provider returned non-JSON")
        data = json.loads(content[start : end + 1])
    return VisionResult(
        title=str(data.get("title", "Unknown")),
        issue_number=str(data.get("issue_number", "?")),
        publisher=str(data.get("publisher", "Unknown")),
        tentative_grade=float(data.get("tentative_grade", 5.0)),
        signature_detected=bool(data.get("signature_detected", False)),
        notes=str(data.get("notes", "")),
    )


async def _read_image(image: UploadFile, label: str = "Image") -> tuple[bytes, str]:
    if not image.filename:
        raise HTTPException(status_code=400, detail=f"{label}: no file received")
    ctype = image.content_type or ""
    if ctype and ctype not in _ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail=f"{label}: unsupported image type {ctype}")
    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail=f"{label}: empty image")
    if len(payload) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"{label}: image exceeds 10 MB")
    return payload, ctype or "image/jpeg"


@router.post("/analyze", response_model=VisionResult)
async def analyze_cover(
    image: UploadFile = File(...),
    _user: str = Depends(current_user_id),
) -> VisionResult:
    """Analyze an uploaded comic cover image and return identification + grade."""
    payload, ctype = await _read_image(image)
    if settings.vision_provider == "claude":
        result = await _claude_grade([Photo("front", payload, ctype)])
        ident, report = result.identification, result.report
        return VisionResult(
            title=ident.title,
            issue_number=ident.issue_number,
            publisher=ident.publisher,
            tentative_grade=report.grade,
            signature_detected=ident.signature_detected,
            notes=ident.notes,
        )
    if settings.vision_provider == "openai":
        return await _openai_analysis(payload, ctype)
    return _mock_analysis(payload)


async def _claude_grade(photos: list[Photo]) -> GradeScanResult:
    try:
        graded = await grade_with_claude(photos)
    except GradingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return GradeScanResult(
        identification=graded.identification,
        alternatives=graded.alternatives,
        report=graded.report,
        match_confidence=graded.match_confidence,
    )


def _from_single(result: VisionResult, source: str) -> GradeScanResult:
    """Mock / OpenAI: they grade the front only, so the area breakdown is estimated."""
    report = estimate_report(
        {
            "title": result.title,
            "issue_number": result.issue_number,
            "estimated_grade": result.tentative_grade,
        }
    ).model_copy(update={"source": source, "photos_used": 1})
    return GradeScanResult(
        identification=ScanIdentification(
            title=result.title,
            issue_number=result.issue_number,
            publisher=result.publisher,
            signature_detected=result.signature_detected,
            notes=result.notes,
        ),
        report=report,
        match_confidence=0.6 if source == "mock" else 0.75,
    )


@router.post("/grade", response_model=GradeScanResult)
async def grade_scan(
    front: UploadFile = File(..., description="Front cover photo"),
    back: UploadFile | None = File(None, description="Back cover photo"),
    spine: UploadFile | None = File(None, description="Spine photo"),
    _user: str = Depends(current_user_id),
) -> GradeScanResult:
    """Identify and grade a book from up to three photos.

    Returns the identification, the full grade report and a raw value estimate
    with the slab-or-not maths computed from it.
    """
    photos: list[Photo] = []
    for role, upload in (("front", front), ("back", back), ("spine", spine)):
        if upload is None:
            continue
        data, ctype = await _read_image(upload, role.capitalize())
        photos.append(Photo(role, data, ctype))

    if settings.vision_provider == "claude":
        result = await _claude_grade(photos)
    elif settings.vision_provider == "openai":
        result = _from_single(
            await _openai_analysis(photos[0].data, photos[0].media_type),
            f"openai:{settings.openai_vision_model}",
        )
    else:
        result = _from_single(_mock_analysis(photos[0].data), "mock")

    # Raw value estimate for the identified book at the graded condition.
    ident = result.identification
    try:
        quote = await MockProvider().quote(
            title=ident.title,
            issue_number=ident.issue_number,
            grade=result.report.grade,
            slab_cert_number=None,
        )
        result.estimated_value, result.value_source = quote.value, quote.source
        result.report.slab = slab_economics(result.report.grade, "raw", quote.value)
    except Exception:
        pass  # a value is a bonus; the grade still stands without it
    return result