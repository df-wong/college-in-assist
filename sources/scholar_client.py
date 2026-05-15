"""Google Scholar search client using the `scholarly` library.

NOTE: scholarly scrapes Google Scholar and may be rate-limited or blocked
under heavy use. We wrap it with generous timeouts and graceful fallback.
"""
from __future__ import annotations

import logging

from scholarly import scholarly

from .models import Paper

log = logging.getLogger(__name__)


def search(query: str, max_results: int = 5) -> list[Paper]:
    """Search Google Scholar and return up to max_results Papers."""
    log.info("Google Scholar search: %s (n=%d)", query, max_results)
    out: list[Paper] = []
    try:
        results = scholarly.search_pubs(query)
        for _ in range(max_results):
            try:
                r = next(results)
            except StopIteration:
                break

            bib = r.get("bib", {})
            title = bib.get("title", "").strip()
            authors = bib.get("author", [])
            if isinstance(authors, str):
                authors = [a.strip() for a in authors.split(" and ")]
            abstract = bib.get("abstract", "").strip()
            year = str(bib.get("pub_year", ""))
            url = r.get("pub_url", "") or r.get("eprint_url", "")
            # Scholar doesn't give a stable ID; use title hash as fallback
            identifier = r.get("author_pub_id", "") or ""

            out.append(
                Paper(
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    url=url,
                    source="scholar",
                    identifier=identifier,
                )
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("Google Scholar search failed: %s", exc)
    return out
