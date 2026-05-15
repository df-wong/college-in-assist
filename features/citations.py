"""Generate citations in arbitrary styles (APA, IEEE, MLA, Chicago, BibTeX, ...)."""
from __future__ import annotations

from core.llm import LLM
from core.prompts import CITATION_SYSTEM, CITATION_USER_TEMPLATE
from sources.models import Paper

DEFAULT_STYLE = "APA"


def cite_text(llm: LLM, source: str, style: str = DEFAULT_STYLE) -> str:
    return llm.chat(
        CITATION_SYSTEM,
        CITATION_USER_TEMPLATE.format(style=style, source=source),
        temperature=0.0,
        max_tokens=400,
    )


def cite_paper(llm: LLM, paper: Paper, style: str = DEFAULT_STYLE) -> str:
    blob = (
        f"Title: {paper.title}\n"
        f"Authors: {', '.join(paper.authors) or 'Unknown'}\n"
        f"Year: {paper.year or 'n.d.'}\n"
        f"Source: {paper.source}\n"
        f"Identifier: {paper.identifier}\n"
        f"URL: {paper.url}\n"
        f"Abstract: {paper.abstract[:600]}"
    )
    return cite_text(llm, blob, style=style)
