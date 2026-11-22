"""Shared Supabase client for the FastAPI backend.

Uses the service-role key server-side (bypasses RLS — the backend is the only
thing that should hold this key). Falls back to the anon key if the service
key is absent so the prototype still runs in read-only public mode.
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException
from supabase import Client, create_client

from .config import settings


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    key = settings.supabase_service_role_key or settings.supabase_anon_key
    if not settings.supabase_url or not key:
        # 503 so a misconfigured server says so instead of failing with a bare 500.
        raise HTTPException(
            status_code=503,
            detail="Server is not connected to Supabase: set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY (see backend/.env.example).",
        )
    return create_client(settings.supabase_url, key)