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

import time  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402

from app import auth  # noqa: E402

TEST_SUPABASE_URL = "https://testproject.supabase.co"
ISSUER = TEST_SUPABASE_URL + "/auth/v1"
SIGNING_KEY = ec.generate_private_key(ec.SECP256R1())  # stands in for the project's ES256 key
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())

USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"


def make_token(sub=USER_A, *, key=SIGNING_KEY, exp_in=3600, aud="authenticated", iss=ISSUER, **extra) -> str:
    now = int(time.time())
    claims = {"sub": sub, "aud": aud, "iss": iss, "iat": now, "exp": now + exp_in, "role": "authenticated", **extra}
    return jwt.encode(claims, key, algorithm="ES256", headers={"kid": "test-kid"})


TOKEN_A = make_token(USER_A)
TOKEN_B = make_token(USER_B)
AUTH_A = {"Authorization": f"Bearer {TOKEN_A}"}
AUTH_B = {"Authorization": f"Bearer {TOKEN_B}"}


class FakeJWKS:
    """Returns the test public key, like PyJWKClient does for the project's JWKS."""

    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=SIGNING_KEY.public_key())


@pytest.fixture
def sb():
    return FakeSupabase(tokens={})


@pytest.fixture
def client(sb, monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", TEST_SUPABASE_URL)
    monkeypatch.setattr(auth, "jwks_client", lambda: FakeJWKS())
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
