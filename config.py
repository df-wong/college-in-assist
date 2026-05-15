"""Application configuration loaded from environment variables."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    openai_api_key: str
    openai_model: str
    pubmed_email: str
    db_path: Path
    log_level: str

    @staticmethod
    def load() -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
        if not openai_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        db_path = Path(os.getenv("DB_PATH", "./data/assistant.db")).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        return Settings(
            telegram_token=token,
            openai_api_key=openai_key,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            pubmed_email=os.getenv("PUBMED_EMAIL", "research@example.com"),
            db_path=db_path,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


def configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )
    # Tame chatty libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
