# AI vision pipeline router.
#
# POST /vision/analyze receives an uploaded cover image, routes it through the
# configured provider (mock by default, real OpenAI vision when VISION_PROVIDER=openai),
# and returns a tentative identification + CGC-style grade.

from __future__ import annotations

import base64
import random
from typing import Final

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile

from ..config import settings
from ..schemas import VisionResult

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


@router.post("/analyze", response_model=VisionResult)
async def analyze_cover(image: UploadFile = File(...)) -> VisionResult:
    """Analyze an uploaded comic cover image and return identification + grade."""
    if not image.filename:
        raise HTTPException(status_code=400, detail="No file received")
    ctype = image.content_type or ""
    if ctype and ctype not in _ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported image type: {ctype}")
    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty image")
    if len(payload) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 10 MB")

    if settings.vision_provider == "openai":
        return await _openai_analysis(payload, ctype or "image/jpeg")
    return _mock_analysis(payload)