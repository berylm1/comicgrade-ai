"""Who is calling: verifies the Supabase access token on each request.

The backend talks to Supabase with the service-role key, which bypasses row
level security, so every route must scope its queries to the user returned
here. Never trust a user id sent in the body or query string.
"""
from __future__ import annotations

import uuid

from fastapi import Depends, Header, HTTPException

from .config import settings
from .supabase_client import get_supabase


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Authorization header must be 'Bearer <token>'")
    return token.strip()


def current_user_id(
    authorization: str | None = Header(default=None),
    sb=Depends(get_supabase),
) -> str:
    token = _bearer(authorization)
    if token:
        try:
            res = sb.auth.get_user(token)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        user = getattr(res, "user", None)
        if not user or not getattr(user, "id", None):
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        return str(user.id)

    if settings.auth_required:
        raise HTTPException(status_code=401, detail="Sign in required")
    if not settings.dev_user_id:
        raise HTTPException(
            status_code=401,
            detail="No session. Sign in, or set DEV_USER_ID in backend/.env for local testing.",
        )
    try:
        uuid.UUID(settings.dev_user_id)
    except ValueError:
        raise HTTPException(status_code=500, detail="DEV_USER_ID must be a Supabase user uuid")
    return settings.dev_user_id
