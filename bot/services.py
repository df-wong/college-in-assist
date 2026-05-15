"""Service container shared across handlers (kept on Application.bot_data)."""
from __future__ import annotations

from dataclasses import dataclass

from config import Settings
from core.llm import LLM
from storage.db import Database


@dataclass
class Services:
    settings: Settings
    llm: LLM
    db: Database

    @classmethod
    def build(cls, settings: Settings) -> "Services":
        return cls(
            settings=settings,
            llm=LLM(settings.openai_api_key, settings.openai_model),
            db=Database(settings.db_path),
        )
