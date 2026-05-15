"""PDF text extraction from local files or HTTP(S) URLs."""
from __future__ import annotations

import io
import logging
import re
from pathlib import Path

import httpx
from pypdf import PdfReader

log = logging.getLogger(__name__)

MAX_PDF_BYTES = 25 * 1024 * 1024  # 25 MB safety cap


def extract_text_from_bytes(data: bytes) -> str:
    """Extract text from raw PDF bytes."""
    reader = PdfReader(io.BytesIO(data))
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to extract a page: %s", exc)
    text = "\n".join(pages)
    return _clean(text)


def extract_text_from_path(path: str | Path) -> str:
    return extract_text_from_bytes(Path(path).read_bytes())


def extract_text_from_url(url: str, *, timeout: float = 30.0) -> str:
    log.info("Fetching PDF: %s", url)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        if len(resp.content) > MAX_PDF_BYTES:
            raise ValueError("PDF exceeds maximum allowed size")
        return extract_text_from_bytes(resp.content)


def _clean(text: str) -> str:
    # Collapse excessive whitespace while keeping paragraph breaks.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate_for_llm(text: str, max_chars: int = 60_000) -> str:
    """Naive truncation. For long papers we keep head + tail to preserve abstract & conclusion."""
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.7)]
    tail = text[-int(max_chars * 0.3):]
    return f"{head}\n\n[...truncated...]\n\n{tail}"
