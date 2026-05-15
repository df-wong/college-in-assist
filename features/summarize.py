"""Summarize a paper from raw text, a PDF file, or a URL."""
from __future__ import annotations

from core.llm import LLM
from core.pdf import (
    extract_text_from_bytes,
    extract_text_from_url,
    truncate_for_llm,
)
from core.prompts import SUMMARIZE_SYSTEM, SUMMARIZE_USER_TEMPLATE


def summarize_text(llm: LLM, paper_text: str) -> str:
    text = truncate_for_llm(paper_text)
    return llm.chat(
        SUMMARIZE_SYSTEM,
        SUMMARIZE_USER_TEMPLATE.format(paper=text),
        max_tokens=1200,
    )


def summarize_pdf_bytes(llm: LLM, data: bytes) -> str:
    return summarize_text(llm, extract_text_from_bytes(data))


def summarize_url(llm: LLM, url: str) -> str:
    return summarize_text(llm, extract_text_from_url(url))
