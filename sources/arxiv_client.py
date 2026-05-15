"""arXiv search client (uses the official arxiv python package)."""
from __future__ import annotations

import logging

import arxiv

from .models import Paper

log = logging.getLogger(__name__)


def search(query: str, max_results: int = 5) -> list[Paper]:
    log.info("arXiv search: %s (n=%d)", query, max_results)
    search_obj = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )
    client = arxiv.Client(page_size=max_results, delay_seconds=1.0, num_retries=3)
    out: list[Paper] = []
    for r in client.results(search_obj):
        out.append(
            Paper(
                title=(r.title or "").strip(),
                authors=[a.name for a in r.authors],
                abstract=(r.summary or "").strip(),
                year=str(r.published.year) if r.published else "",
                url=r.entry_id or "",
                source="arxiv",
                identifier=r.get_short_id(),
            )
        )
    return out
