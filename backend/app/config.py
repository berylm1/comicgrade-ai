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

    vision_provider: str = os.getenv("VISION_PROVIDER", "mock")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    openai_vision_model: str = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")

    storage_bucket: str = os.getenv("STORAGE_BUCKET", "cover-images")


settings = Settings()