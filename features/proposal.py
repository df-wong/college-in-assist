"""Generate a structured research proposal."""
from __future__ import annotations

from core.llm import LLM
from core.prompts import PROPOSAL_SYSTEM, PROPOSAL_USER_TEMPLATE


def generate(llm: LLM, topic: str, context: str = "") -> str:
    return llm.chat(
        PROPOSAL_SYSTEM,
        PROPOSAL_USER_TEMPLATE.format(topic=topic, context=context or "(none)"),
        temperature=0.5,
        max_tokens=2000,
    )
