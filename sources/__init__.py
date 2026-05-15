"""Academic source clients."""
from .models import Paper
from . import arxiv_client, pubmed_client, scholar_client

__all__ = ["Paper", "arxiv_client", "pubmed_client", "scholar_client"]
