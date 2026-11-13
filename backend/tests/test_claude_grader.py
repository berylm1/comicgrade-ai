import asyncio
import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import anthropic
import httpx2
import pytest

from app import claude_grader
from app.claude_grader import (
    GRADE_SCHEMA,
    GradingError,
    GradingRefused,
    Photo,
    grade_with_claude,
    parse_response,
)
from app.config import settings

GOOD = {
    "is_comic": True,
    "identification": {
        "title": " Amazing Spider-Man ",
        "issue_number": "#300",
        "publisher": "Marvel",
        "year": 1988,
        "key_note": "1st full appearance of Venom",
        "signature_detected": False,
    },
    "match_confidence": 0.97,
    "grade": 9.25,  # off the CGC scale: snapped to 9.2
    "grade_low": 9.0,
    "grade_high": 9.5,  # snapped to 9.4 (ties go down)
    "confidence": 0.81,
    "defects": [
        {"area": "Corners", "score": 9.4, "note": "Sharp"},
        {"area": "Spine", "score": 11, "note": "Flat"},  # clamped to 10
    ],
    "notes": "Slight glare on the back cover photo.",
}


def response(payload=None, stop_reason="end_turn", text=None, **extra):
    content = [SimpleNamespace(type="thinking", thinking="")]
    if payload is not None or text is not None:
        content.append(SimpleNamespace(type="text", text=text if text is not None else json.dumps(payload)))
    return SimpleNamespace(
        stop_reason=stop_reason, content=content, model="claude-opus-5-5", stop_details=None, **extra
    )


def jpeg(role="front", size=10):
    return Photo(role, b"\xff\xd8" + b"0" * size, "image/jpeg")


# ------------------------------------------------------------- parsing


def test_parse_good_response():
    graded = parse_response(response(GOOD), photos_used=3)
    ident, report = graded.identification, graded.report
    assert ident.title == "Amazing Spider-Man"
    assert ident.issue_number == "300"
    assert ident.year == 1988
    assert ident.notes == "Slight glare on the back cover photo."
    assert (report.grade_low, report.grade, report.grade_high) == (9.0, 9.2, 9.4)
    assert report.defects[1].score == 10
    assert report.source == "claude:claude-opus-5-5"
    assert report.photos_used == 3
    assert report.exterior_only is True
    assert graded.match_confidence == 0.97


def test_parse_keeps_range_around_grade():
    bad_range = {**GOOD, "grade": 8.0, "grade_low": 9.0, "grade_high": 7.0}
    report = parse_response(response(bad_range), 1).report
    assert report.grade_low <= report.grade <= report.grade_high


def test_refusal_is_checked_before_content():
    details = SimpleNamespace(type="refusal", category="cyber", explanation="Declined.")
    r = response(None, stop_reason="refusal")
    r.stop_details = details
    with pytest.raises(GradingRefused) as err:
        parse_response(r, 1)
    assert err.value.status_code == 422
    assert "Declined." in str(err.value)


def test_max_tokens_is_an_error():
    with pytest.raises(GradingError):
        parse_response(response(GOOD, stop_reason="max_tokens"), 1)


def test_non_json_is_an_error():
    with pytest.raises(GradingError):
        parse_response(response(text="not json"), 1)


def test_wrong_shape_is_an_error():
    with pytest.raises(GradingError):
        parse_response(response({"grade": 9.2}), 1)


def test_not_a_comic_is_422():
    with pytest.raises(GradingError) as err:
        parse_response(response({**GOOD, "is_comic": False}), 1)
    assert err.value.status_code == 422


def test_fallback_block_is_skipped():
    r = response(GOOD)
    r.content.insert(0, SimpleNamespace(type="fallback"))
    assert parse_response(r, 1).report.grade == 9.2


# -------------------------------------------------------------- schema


def _objects(schema):
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            yield schema
        for value in schema.values():
            yield from _objects(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from _objects(value)


def test_schema_is_valid_for_structured_outputs():
    for obj in _objects(GRADE_SCHEMA):
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])
    text = json.dumps(GRADE_SCHEMA)
    for unsupported in ("minimum", "maximum", "minLength", "maxLength", "multipleOf"):
        assert unsupported not in text


# ------------------------------------------------------------ requests


def fake_client(result=None, error=None):
    create = AsyncMock(return_value=result, side_effect=error)
    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create))), create


def test_request_shape():
    client, create = fake_client(response(GOOD))
    photos = [jpeg("front"), jpeg("back"), jpeg("spine")]
    graded = asyncio.run(grade_with_claude(photos, client=client))
    assert graded.report.photos_used == 3

    kwargs = create.await_args.kwargs
    assert kwargs["model"] == settings.claude_vision_model
    assert kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert kwargs["fallbacks"] == "default"
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["output_config"]["format"] == {"type": "json_schema", "schema": GRADE_SCHEMA}
    content = kwargs["messages"][0]["content"]
    images = [b for b in content if b["type"] == "image"]
    assert len(images) == 3
    assert base64.standard_b64decode(images[0]["source"]["data"]) == photos[0].data
    labels = [b["text"] for b in content if b["type"] == "text"]
    assert labels[:3] == ["Photo 1: Front cover", "Photo 2: Back cover", "Photo 3: Spine"]


def test_photo_count_limits():
    client, create = fake_client(response(GOOD))
    with pytest.raises(GradingError):
        asyncio.run(grade_with_claude([], client=client))
    with pytest.raises(GradingError):
        asyncio.run(grade_with_claude([jpeg()] * 4, client=client))
    create.assert_not_awaited()


def test_heic_and_oversize_rejected_before_calling():
    client, create = fake_client(response(GOOD))
    with pytest.raises(GradingError) as err:
        asyncio.run(grade_with_claude([Photo("front", b"x", "image/heic")], client=client))
    assert err.value.status_code == 415
    with pytest.raises(GradingError) as err:
        asyncio.run(grade_with_claude([jpeg(size=5 * 1024 * 1024 + 1)], client=client))
    assert err.value.status_code == 413
    create.assert_not_awaited()


def test_rate_limit_maps_to_429():
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    err = anthropic.RateLimitError("slow down", response=httpx2.Response(429, request=req), body=None)
    client, _ = fake_client(error=err)
    with pytest.raises(GradingError) as caught:
        asyncio.run(grade_with_claude([jpeg()], client=client))
    assert caught.value.status_code == 429


# --------------------------------------------------------------- route


def test_grade_route_with_claude_provider(client, monkeypatch):
    monkeypatch.setattr(settings, "vision_provider", "claude")
    fake, create = fake_client(response(GOOD))
    monkeypatch.setattr(claude_grader, "get_client", lambda: fake)
    files = {
        "front": ("f.jpg", b"\xff\xd8f", "image/jpeg"),
        "back": ("b.jpg", b"\xff\xd8b", "image/jpeg"),
        "spine": ("s.jpg", b"\xff\xd8s", "image/jpeg"),
    }
    r = client.post("/vision/grade", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["identification"]["title"] == "Amazing Spider-Man"
    assert body["identification"]["key_note"] == "1st full appearance of Venom"
    assert body["report"]["photos_used"] == 3
    assert body["report"]["slab"] is not None
    assert body["estimated_value"] > 0


def test_grade_route_refusal_is_422(client, monkeypatch):
    monkeypatch.setattr(settings, "vision_provider", "claude")
    fake, _ = fake_client(response(None, stop_reason="refusal"))
    monkeypatch.setattr(claude_grader, "get_client", lambda: fake)
    r = client.post("/vision/grade", files={"front": ("f.jpg", b"\xff\xd8f", "image/jpeg")})
    assert r.status_code == 422
