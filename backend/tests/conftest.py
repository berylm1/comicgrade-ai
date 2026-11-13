from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.supabase_client import get_supabase  # noqa: E402
from fake_supabase import FakeSupabase  # noqa: E402

USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"
TOKEN_A = "token-a"
TOKEN_B = "token-b"
AUTH_A = {"Authorization": f"Bearer {TOKEN_A}"}
AUTH_B = {"Authorization": f"Bearer {TOKEN_B}"}


@pytest.fixture
def sb():
    return FakeSupabase(tokens={TOKEN_A: USER_A, TOKEN_B: USER_B})


@pytest.fixture
def client(sb, monkeypatch):
    monkeypatch.setattr(settings, "auth_required", False)
    monkeypatch.setattr(settings, "dev_user_id", USER_A)
    monkeypatch.setattr(settings, "vision_provider", "mock")
    monkeypatch.setattr(settings, "cron_secret", "")
    app.dependency_overrides[get_supabase] = lambda: sb
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def add_comic(sb: FakeSupabase, user_id: str = USER_A, **fields) -> dict:
    row = {
        "title": "Saga",
        "issue_number": "1",
        "publisher": "Image",
        "grade_type": "raw",
        "estimated_grade": 9.6,
        "current_market_value": 180.0,
        "user_id": user_id,
        **fields,
    }
    return sb.table("comics").insert(row).execute().data[0]
