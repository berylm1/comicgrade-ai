"""FastAPI application entry point."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import comics, portfolio, pricing, runs, vision

app = FastAPI(
    title="ComicGrade AI",
    description="Comic book valuation & grading prototype API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # prototype-wide; tighten for production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vision.router)
app.include_router(comics.router)
app.include_router(portfolio.router)
app.include_router(runs.router)
app.include_router(pricing.router)


@app.get("/")
async def root() -> dict:
    return {"app": "ComicGrade AI", "docs": "/docs", "health": "/health"}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/health/config")
def health_config() -> dict:
    """Whether the server's settings look right, without reading any data.

    Safe to open in a browser after a deploy: it never shows secret values.
    """
    from fastapi import HTTPException

    from .config import settings
    from .supabase_client import get_supabase

    checks: dict[str, str] = {}
    try:
        get_supabase()
        checks["supabase"] = "ok"
    except HTTPException as exc:
        checks["supabase"] = str(exc.detail)
    checks["auth_required"] = "on" if settings.auth_required else "OFF (local testing only)"
    provider = settings.vision_provider
    if provider == "claude":
        checks["vision"] = "claude" if settings.anthropic_api_key else "claude, but ANTHROPIC_API_KEY is missing"
    else:
        checks["vision"] = f"{provider} (sample results, not real grading)" if provider == "mock" else provider
    return {"status": "ok" if checks["supabase"] == "ok" else "misconfigured", "checks": checks}