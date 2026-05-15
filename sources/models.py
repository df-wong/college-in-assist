"""Common data model used across academic source clients."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Paper:
    title: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    year: str = ""
    url: str = ""
    source: str = ""  # "arxiv" | "pubmed" | "manual"
    identifier: str = ""  # arxiv id, pmid, doi, etc.

    def short(self) -> str:
        a = ", ".join(self.authors[:3])
        if len(self.authors) > 3:
            a += " et al."
        return f"{self.title} ({a}, {self.year}) [{self.source}:{self.identifier}]"
