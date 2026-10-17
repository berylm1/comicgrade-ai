"""Shared Supabase client for the FastAPI backend.

Uses the service-role key server-side (bypasses RLS — the backend is the only
thing that should hold this key). Falls back to the anon key if the service
key is absent so the prototype still runs in read-only public mode.
"""
from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from .config import settings


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    key = settings.supabase_service_role_key or settings.supabase_anon_key
    if not settings.supabase_url or not key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_ANON_KEY are missing. "
            "Copy backend/.env.example to backend/.env and fill in your project credentials."
        )
    return create_client(settings.supabase_url, key)