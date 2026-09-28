# ai: claude-sonnet-4-6 | 2026-06-18
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
_ENV_EXAMPLE = Path(__file__).resolve().parent.parent / ".env.example"


def _ensure_env_file() -> None:
    if not _ENV_FILE.exists():
        _ENV_FILE.write_text(_ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")  # ai: claude-opus-5-5 | 2026-09-28
        print(
            f"[config] No .env found — created a template at {_ENV_FILE}\n"
            "         Fill in ANTHROPIC_API_KEY and restart.",
            file=sys.stderr,
        )
        sys.exit(1)


_ensure_env_file()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    anthropic_api_key: str
    database_url: str = "sqlite:///./costco_prices.db"
    cors_origins: str = "http://costco.localhost"  # ai: claude-opus-5-5 | 2026-09-28


settings = Settings()
