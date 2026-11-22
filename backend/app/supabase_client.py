"""Shared Supabase client for the FastAPI backend.

Uses the secret (service-role) key, which bypasses row level security: the
backend scopes every query to the signed-in user itself (see auth.py) and is
the only thing that should hold this key.

A public key (publishable / anon) must never be used here. With one, row level
security silently hides every row and blocks every write, so the app looks
empty and saving fails with no clear error. get_supabase refuses such keys.
"""
from __future__ import annotations

import base64
import json
from functools import lru_cache
from typing import Optional

from fastapi import HTTPException
from supabase import Client, create_client

from .config import settings

WRONG_KEY = (
    "SUPABASE_SERVICE_ROLE_KEY holds a public key ({kind}). Use the project's secret key "
    "(sb_secret_..., or the legacy service_role key) from Supabase > Project Settings > API Keys."
)


def public_key_kind(key: str) -> Optional[str]:
    """Name of the public key type if `key` is one, else None."""
    if key.startswith("sb_publishable_"):
        return "publishable"
    parts = key.split(".")
    if len(parts) == 3:  # legacy JWT key: read its role claim (no verification needed)
        try:
            claims = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
        except Exception:
            return None
        if claims.get("role") == "anon":
            return "legacy anon"
    return None


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    key = settings.supabase_service_role_key.strip()
    if not settings.supabase_url or not key:
        # 503 so a misconfigured server says so instead of failing with a bare 500.
        raise HTTPException(
            status_code=503,
            detail="Server is not connected to Supabase: set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY (see backend/.env.example).",
        )
    kind = public_key_kind(key)
    if kind:
        raise HTTPException(status_code=503, detail=WRONG_KEY.format(kind=kind))
    try:
        return create_client(settings.supabase_url, key)
    except Exception as exc:  # malformed URL or key
        raise HTTPException(status_code=503, detail=f"Supabase client could not start: {exc}")
