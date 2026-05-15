"""Plain-language interpretation of statistical content / tables / figures."""
from __future__ import annotations

from core.llm import LLM
from core.prompts import INTERPRET_SYSTEM, INTERPRET_USER_TEMPLATE


def interpret(llm: LLM, content: str) -> str:
    return llm.chat(
        INTERPRET_SYSTEM,
        INTERPRET_USER_TEMPLATE.format(content=content),
        temperature=0.2,
        max_tokens=1200,
    )
