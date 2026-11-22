"""Who is calling: verifies the Supabase access token on each request.

The backend talks to Supabase with the service-role (secret) key, which
bypasses row level security, so every route must scope its queries to the
user returned here. Never trust a user id sent in the body or query string.

How tokens are checked:
* Projects with asymmetric signing keys (ES256/RS256, the Supabase default
  for new projects) are verified locally against the project's public JWKS:
  signature, expiry, audience and issuer. No secret and no per-request call.
  The JWKS is fetched once and cached.
* Legacy projects that sign with a shared HS256 secret fall back to asking
  Supabase (auth.get_user). That path works with legacy JWT service keys; with
  the new sb_secret_ keys Supabase replaces the user's token at its gateway,
  which is why local verification is the main path.

A locally verified token stays valid until it expires (about an hour) even
after the user signs out; that is the usual trade-off of stateless JWTs.
"""
from __future__ import annotations

import uuid
from functools import lru_cache

import jwt
from fastapi import Depends, Header, HTTPException

from .config import settings
from .supabase_client import get_supabase

ASYMMETRIC_ALGS = ["ES256", "RS256", "EdDSA"]
LEEWAY_S = 30  # clock skew between Supabase and this server


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Authorization header must be 'Bearer <token>'")
    return token.strip()


def _issuer() -> str:
    return settings.supabase_url.rstrip("/") + "/auth/v1"


@lru_cache(maxsize=1)
def jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(_issuer() + "/.well-known/jwks.json", cache_keys=True, lifespan=600)


def _invalid() -> HTTPException:
    return HTTPException(status_code=401, detail="Invalid or expired session")


def verify_token(token: str, sb) -> str:
    """User id from a Supabase access token, or 401."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise _invalid()

    if header.get("alg") in ASYMMETRIC_ALGS:
        try:
            key = jwks_client().get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=ASYMMETRIC_ALGS,
                audience="authenticated",
                issuer=_issuer(),
                leeway=LEEWAY_S,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except jwt.PyJWKClientError:
            raise HTTPException(status_code=503, detail="Could not load the project's signing keys")
        except jwt.PyJWTError:
            raise _invalid()
        sub = claims.get("sub")
        try:
            return str(uuid.UUID(str(sub)))
        except ValueError:
            raise _invalid()

    # Legacy HS256 projects: ask Supabase.
    try:
        res = sb.auth.get_user(token)
    except Exception:
        raise _invalid()
    user = getattr(res, "user", None)
    if not user or not getattr(user, "id", None):
        raise _invalid()
    return str(user.id)


def current_user_id(
    authorization: str | None = Header(default=None),
    sb=Depends(get_supabase),
) -> str:
    token = _bearer(authorization)
    if token:
        return verify_token(token, sb)

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
