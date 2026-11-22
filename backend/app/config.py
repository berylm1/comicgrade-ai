"""Central configuration loaded from environment / .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env sitting next to the backend/ directory (fall back silently to
# process env when the file does not exist).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class Settings:
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # ---- Auth ----
    # When true every request needs a Supabase access token (Authorization: Bearer).
    # When false, requests without a token act as DEV_USER_ID (local testing only).
    auth_required: bool = os.getenv("AUTH_REQUIRED", "false").strip().lower() in {"1", "true", "yes"}
    dev_user_id: str = os.getenv("DEV_USER_ID", "")
    # Shared secret for the nightly POST /portfolio/snapshot/all job (disabled when empty).
    cron_secret: str = os.getenv("CRON_SECRET", "")

    vision_provider: str = os.getenv("VISION_PROVIDER", "mock")
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY") or None
    claude_vision_model: str = os.getenv("CLAUDE_VISION_MODEL", "claude-opus-5-5")
    claude_effort: str = os.getenv("CLAUDE_EFFORT", "medium")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    openai_vision_model: str = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")

    # ---- Valuation sources ----
    gocollect_api_key: str = os.getenv("GOCOLLECT_API_KEY", "")

    storage_bucket: str = os.getenv("STORAGE_BUCKET", "cover-images")


settings = Settings()