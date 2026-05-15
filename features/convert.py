"""File conversion utilities: PDF↔Word, PDF↔PNG, Word↔PNG, Word↔TXT, TXT→Word, PNG→PDF."""
from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
from docx import Document
from PIL import Image

log = logging.getLogger(__name__)


# =============================================================================
# PDF → Word (.docx)
# =============================================================================
def pdf_to_word(pdf_bytes: bytes) -> bytes:
    """Extract text from PDF pages and write into a .docx document."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    word_doc = Document()
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        if page_num > 0:
            word_doc.add_page_break()
        word_doc.add_heading(f"Page {page_num + 1}", level=2)
        for para in text.split("\n"):
            stripped = para.strip()
            if stripped:
                word_doc.add_paragraph(stripped)
    doc.close()
    buf = io.BytesIO()
    word_doc.save(buf)
    return buf.getvalue()


# =============================================================================
# Word (.docx) → PDF
# =============================================================================
def word_to_pdf(docx_bytes: bytes) -> bytes:
    """Convert a .docx to PDF by rendering text paragraphs with PyMuPDF."""
    word_doc = Document(io.BytesIO(docx_bytes))
    paragraphs: list[str] = []
    for para in word_doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)

    # Create PDF with PyMuPDF
    pdf_doc = fitz.open()
    page = pdf_doc.new_page(width=595, height=842)  # A4
    y = 50
    fontsize = 11
    margin_x = 50
    max_width = 495
    line_height = fontsize * 1.4

    for para_text in paragraphs:
        # Simple word-wrap
        words = para_text.split()
        line = ""
        for word in words:
            test_line = f"{line} {word}".strip()
            # Approximate char width
            if len(test_line) * fontsize * 0.5 > max_width:
                if y + line_height > 790:
                    page = pdf_doc.new_page(width=595, height=842)
                    y = 50
                page.insert_text((margin_x, y), line, fontsize=fontsize)
                y += line_height
                line = word
            else:
                line = test_line
        if line:
            if y + line_height > 790:
                page = pdf_doc.new_page(width=595, height=842)
                y = 50
            page.insert_text((margin_x, y), line, fontsize=fontsize)
            y += line_height
        y += line_height * 0.3  # paragraph spacing

    buf = io.BytesIO()
    pdf_doc.save(buf)
    pdf_doc.close()
    return buf.getvalue()


# =============================================================================
# PDF → PNG (one image per page, returned as list)
# =============================================================================
def pdf_to_png(pdf_bytes: bytes, dpi: int = 150) -> list[bytes]:
    """Render each PDF page as a PNG image. Returns list of PNG byte buffers."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images: list[bytes] = []
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=mat)
        images.append(pix.tobytes("png"))
    doc.close()
    return images


# =============================================================================
# Word (.docx) → PNG (render via intermediate PDF)
# =============================================================================
def word_to_png(docx_bytes: bytes, dpi: int = 150) -> list[bytes]:
    """Convert Word to PNG by first converting to PDF, then rendering."""
    pdf_bytes = word_to_pdf(docx_bytes)
    return pdf_to_png(pdf_bytes, dpi=dpi)


# =============================================================================
# Word (.docx) → TXT
# =============================================================================
def word_to_txt(docx_bytes: bytes) -> str:
    """Extract all paragraph text from a Word document."""
    word_doc = Document(io.BytesIO(docx_bytes))
    lines: list[str] = []
    for para in word_doc.paragraphs:
        lines.append(para.text)
    return "\n".join(lines)


# =============================================================================
# TXT → Word (.docx)
# =============================================================================
def txt_to_word(text: str) -> bytes:
    """Wrap plain text into a Word document."""
    word_doc = Document()
    for line in text.split("\n"):
        word_doc.add_paragraph(line)
    buf = io.BytesIO()
    word_doc.save(buf)
    return buf.getvalue()


# =============================================================================
# PNG/Image → PDF
# =============================================================================
def png_to_pdf(image_bytes: bytes) -> bytes:
    """Convert a single PNG/JPEG image into a one-page PDF."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode == "RGBA":
        img = img.convert("RGB")
    # Fit image onto an A4-ish page maintaining aspect ratio
    pdf_doc = fitz.open()
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_buf.seek(0)

    # Get image dimensions
    w, h = img.size
    # Scale to fit A4 (595x842 points) with margins
    max_w, max_h = 545, 792
    scale = min(max_w / w, max_h / h, 1.0)
    new_w, new_h = int(w * scale), int(h * scale)

    page = pdf_doc.new_page(width=595, height=842)
    x_offset = (595 - new_w) // 2
    y_offset = (842 - new_h) // 2
    rect = fitz.Rect(x_offset, y_offset, x_offset + new_w, y_offset + new_h)
    page.insert_image(rect, stream=img_buf.getvalue())

    buf = io.BytesIO()
    pdf_doc.save(buf)
    pdf_doc.close()
    return buf.getvalue()


# =============================================================================
# TXT → PDF
# =============================================================================
def txt_to_pdf(text: str) -> bytes:
    """Convert plain text into a PDF document."""
    pdf_doc = fitz.open()
    page = pdf_doc.new_page(width=595, height=842)
    y = 50
    fontsize = 11
    margin_x = 50
    max_width = 495
    line_height = fontsize * 1.4

    for line in text.split("\n"):
        words = line.split()
        if not words:
            y += line_height
            if y > 790:
                page = pdf_doc.new_page(width=595, height=842)
                y = 50
            continue
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if len(test_line) * fontsize * 0.5 > max_width:
                if y + line_height > 790:
                    page = pdf_doc.new_page(width=595, height=842)
                    y = 50
                page.insert_text((margin_x, y), current_line, fontsize=fontsize)
                y += line_height
                current_line = word
            else:
                current_line = test_line
        if current_line:
            if y + line_height > 790:
                page = pdf_doc.new_page(width=595, height=842)
                y = 50
            page.insert_text((margin_x, y), current_line, fontsize=fontsize)
            y += line_height

    buf = io.BytesIO()
    pdf_doc.save(buf)
    pdf_doc.close()
    return buf.getvalue()


# =============================================================================
# Helpers for detecting file types
# =============================================================================
SUPPORTED_CONVERSIONS = {
    "pdf_to_word": ("application/pdf", ".pdf"),
    "pdf_to_png": ("application/pdf", ".pdf"),
    "word_to_pdf": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    "word_to_png": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    "word_to_txt": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    "txt_to_word": ("text/plain", ".txt"),
    "txt_to_pdf": ("text/plain", ".txt"),
    "png_to_pdf": ("image/png", ".png"),
    "jpg_to_pdf": ("image/jpeg", ".jpg"),
}


def detect_possible_conversions(mime_type: str | None, filename: str | None) -> list[str]:
    """Given a file's mime type and name, return which conversions are available."""
    ext = Path(filename).suffix.lower() if filename else ""
    options: list[str] = []

    if mime_type == "application/pdf" or ext == ".pdf":
        options.extend(["pdf_to_word", "pdf_to_png"])
    elif mime_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ) or ext in (".docx", ".doc"):
        options.extend(["word_to_pdf", "word_to_png", "word_to_txt"])
    elif mime_type == "text/plain" or ext == ".txt":
        options.extend(["txt_to_word", "txt_to_pdf"])
    elif mime_type and mime_type.startswith("image/") or ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        options.append("png_to_pdf")

    return options


CONVERSION_LABELS = {
    "pdf_to_word": "PDF → Word (.docx)",
    "pdf_to_png": "PDF → PNG images",
    "word_to_pdf": "Word → PDF",
    "word_to_png": "Word → PNG images",
    "word_to_txt": "Word → Plain text (.txt)",
    "txt_to_word": "TXT → Word (.docx)",
    "txt_to_pdf": "TXT → PDF",
    "png_to_pdf": "Image → PDF",
    "jpg_to_pdf": "Image → PDF",
}
