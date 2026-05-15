"""Search arXiv + PubMed and synthesize a literature review."""
from __future__ import annotations

import logging

from core.llm import LLM
from core.prompts import LITREVIEW_SYSTEM, LITREVIEW_USER_TEMPLATE
from sources import arxiv_client, pubmed_client
from sources.models import Paper

log = logging.getLogger(__name__)


def search_all(topic: str, pubmed_email: str, per_source: int = 5) -> list[Paper]:
    """Query arXiv and PubMed in parallel-ish (sequential for now), dedupe by title."""
    results: list[Paper] = []
    try:
        results.extend(arxiv_client.search(topic, max_results=per_source))
    except Exception as exc:  # noqa: BLE001
        log.warning("arxiv failed: %s", exc)
    try:
        results.extend(pubmed_client.search(topic, email=pubmed_email, max_results=per_source))
    except Exception as exc:  # noqa: BLE001
        log.warning("pubmed failed: %s", exc)

    seen: set[str] = set()
    deduped: list[Paper] = []
    for p in results:
        key = p.title.strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(p)
    return deduped


def review(llm: LLM, topic: str, papers: list[Paper]) -> str:
    if not papers:
        return "No papers found for that topic. Try a broader or different query."
    formatted = "\n\n".join(
        f"[{i + 1}] {p.title}\n   Authors: {', '.join(p.authors) or 'Unknown'}\n"
        f"   Year: {p.year or 'n.d.'} | Source: {p.source}\n"
        f"   Abstract: {p.abstract[:1200]}"
        for i, p in enumerate(papers)
    )
    return llm.chat(
        LITREVIEW_SYSTEM,
        LITREVIEW_USER_TEMPLATE.format(topic=topic, n=len(papers), papers=formatted),
        temperature=0.3,
        max_tokens=1800,
    )


def run(llm: LLM, topic: str, pubmed_email: str, per_source: int = 5) -> tuple[str, list[Paper]]:
    papers = search_all(topic, pubmed_email, per_source=per_source)
    return review(llm, topic, papers), papers
