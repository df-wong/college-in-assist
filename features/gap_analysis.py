"""Identify research gaps and propose follow-up studies."""
from __future__ import annotations

from core.llm import LLM
from core.pdf import truncate_for_llm
from core.prompts import GAP_SYSTEM, GAP_USER_TEMPLATE


def analyze(llm: LLM, paper_text: str) -> str:
    text = truncate_for_llm(paper_text)
    return llm.chat(
        GAP_SYSTEM,
        GAP_USER_TEMPLATE.format(paper=text),
        temperature=0.4,
        max_tokens=1500,
    )
