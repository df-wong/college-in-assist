"""PubMed search client using pymed (NCBI E-utilities under the hood)."""
from __future__ import annotations

import logging

from pymed import PubMed

from .models import Paper

log = logging.getLogger(__name__)


def search(query: str, email: str, max_results: int = 5) -> list[Paper]:
    log.info("PubMed search: %s (n=%d)", query, max_results)
    pm = PubMed(tool="college-in-assist", email=email)
    out: list[Paper] = []
    try:
        for r in pm.query(query, max_results=max_results):
            authors = []
            for a in (r.authors or []):
                last = a.get("lastname") or ""
                first = a.get("firstname") or ""
                name = f"{first} {last}".strip()
                if name:
                    authors.append(name)
            year = ""
            if getattr(r, "publication_date", None):
                year = str(r.publication_date.year)
            pmid = (r.pubmed_id or "").splitlines()[0] if r.pubmed_id else ""
            out.append(
                Paper(
                    title=(r.title or "").strip(),
                    authors=authors,
                    abstract=(r.abstract or "").strip(),
                    year=year,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                    source="pubmed",
                    identifier=pmid,
                )
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("PubMed search failed: %s", exc)
    return out
