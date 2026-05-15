"""Telegram command and message handlers."""
from __future__ import annotations

import io
import logging
from typing import cast

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes, CallbackQueryHandler

from core import pdf
from features import (
    citations,
    convert,
    gap_analysis,
    interpret,
    literature_review,
    proposal,
    summarize,
)

from .services import Services

log = logging.getLogger(__name__)

PENDING_KEY = "pending_intent"  # one of: "summarize", "interpret", "cite_text", "review", "proposal"
CONVERT_FILE_KEY = "convert_file_data"
CONVERT_FILENAME_KEY = "convert_file_name"

WELCOME = (
    "*College-In Research Assistant*\n\n"
    "I help you analyze papers and accelerate your research.\n\n"
    "*Commands*\n"
    "/summarize \\- send a PDF or paste a paper URL/abstract\n"
    "/gaps \\- find research gaps in your last paper\n"
    "/review <topic> \\- literature review across arXiv \\+ PubMed \\+ Scholar\n"
    "/cite <text> \\- generate a citation\n"
    "/style <APA\\|IEEE\\|MLA\\|Chicago\\|BibTeX> \\- set citation style\n"
    "/proposal <topic> \\- write a research proposal\n"
    "/interpret <stats text> \\- explain statistics in plain language\n"
    "/convert \\- convert files \\(PDF↔Word, PDF↔PNG, Word↔TXT, etc\\.\\)\n"
    "/help \\- show this message\n\n"
    "Tip: upload a PDF to auto\\-summarize, or use /convert then upload a file\\."
)


def _services(context: ContextTypes.DEFAULT_TYPE) -> Services:
    return cast(Services, context.application.bot_data["services"])


async def _typing(update: Update) -> None:
    if update.effective_chat:
        try:
            await update.effective_chat.send_action(ChatAction.TYPING)
        except Exception:  # noqa: BLE001
            pass


async def _send_long(update: Update, text: str) -> None:
    """Telegram caps messages at 4096 chars. Split safely on paragraph boundaries."""
    LIMIT = 3800
    if len(text) <= LIMIT:
        await update.effective_message.reply_text(text)
        return
    chunk: list[str] = []
    size = 0
    for para in text.split("\n\n"):
        if size + len(para) + 2 > LIMIT and chunk:
            await update.effective_message.reply_text("\n\n".join(chunk))
            chunk, size = [], 0
        chunk.append(para)
        size += len(para) + 2
    if chunk:
        await update.effective_message.reply_text("\n\n".join(chunk))


# -- basic --------------------------------------------------------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user:
        _services(context).db.upsert_user(user.id, user.username)
    await update.effective_message.reply_text(WELCOME, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(WELCOME, parse_mode=ParseMode.MARKDOWN_V2)


# -- summarize ----------------------------------------------------------------
async def cmd_summarize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    arg = " ".join(context.args or []).strip()
    if arg:
        await _do_summarize(update, context, arg)
        return
    context.user_data[PENDING_KEY] = "summarize"
    await update.effective_message.reply_text(
        "Send me a PDF, a paper URL, or paste the abstract / full text and I'll summarize it."
    )


async def _do_summarize(update: Update, context: ContextTypes.DEFAULT_TYPE, source: str) -> None:
    svc = _services(context)
    await _typing(update)
    try:
        if source.startswith("http://") or source.startswith("https://"):
            text = pdf.extract_text_from_url(source) if source.lower().endswith(".pdf") else source
            if not source.lower().endswith(".pdf"):
                # treat as URL to a landing page; user can paste abstract instead
                await update.effective_message.reply_text(
                    "I can only fetch PDFs by URL. For HTML pages, please paste the abstract or upload the PDF."
                )
                return
        else:
            text = source
        result = summarize.summarize_text(svc.llm, text)
        if update.effective_user:
            svc.db.set_last_paper(update.effective_user.id, text)
        await _send_long(update, result)
    except Exception as exc:  # noqa: BLE001
        log.exception("summarize failed")
        await update.effective_message.reply_text(f"Could not summarize: {exc}")


# -- document upload (PDF) ----------------------------------------------------
async def on_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    doc = msg.document if msg else None
    if not doc:
        return

    # Check if user is in convert mode
    pending = context.user_data.get(PENDING_KEY)
    if pending == "convert":
        await _handle_convert_upload(update, context)
        return

    if not (doc.mime_type == "application/pdf" or (doc.file_name or "").lower().endswith(".pdf")):
        await msg.reply_text("Please send a PDF file, or use /convert to convert between formats.")
        return
    await _typing(update)
    try:
        tg_file = await doc.get_file()
        data = bytes(await tg_file.download_as_bytearray())
        text = pdf.extract_text_from_bytes(data)
        if not text.strip():
            await msg.reply_text("I couldn't extract any text from that PDF (it may be scanned images).")
            return
        svc = _services(context)
        if update.effective_user:
            svc.db.set_last_paper(update.effective_user.id, text)
        result = summarize.summarize_text(svc.llm, text)
        await _send_long(update, result)
        await msg.reply_text(
            "Stored. Try /gaps for research-gap analysis or /interpret for stats explanations."
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("document handler failed")
        await msg.reply_text(f"Failed to process PDF: {exc}")


# -- gaps ---------------------------------------------------------------------
async def cmd_gaps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    svc = _services(context)
    if not update.effective_user:
        return
    last = svc.db.get_last_paper(update.effective_user.id)
    if not last:
        await update.effective_message.reply_text(
            "I don't have a paper for you yet. Upload a PDF or run /summarize first."
        )
        return
    await _typing(update)
    try:
        result = gap_analysis.analyze(svc.llm, last)
        await _send_long(update, result)
    except Exception as exc:  # noqa: BLE001
        log.exception("gaps failed")
        await update.effective_message.reply_text(f"Gap analysis failed: {exc}")


# -- literature review --------------------------------------------------------
async def cmd_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    topic = " ".join(context.args or []).strip()
    if not topic:
        context.user_data[PENDING_KEY] = "review"
        await update.effective_message.reply_text("What topic should I review? Send it as a message.")
        return
    await _do_review(update, context, topic)


async def _do_review(update: Update, context: ContextTypes.DEFAULT_TYPE, topic: str) -> None:
    svc = _services(context)
    await _typing(update)
    try:
        cached = svc.db.get_cached_search(topic)
        if cached:
            log.info("Using cached search for: %s", topic)
            papers = cached
            review_text = literature_review.review(svc.llm, topic, papers)
        else:
            review_text, papers = literature_review.run(
                svc.llm, topic, svc.settings.pubmed_email, per_source=5
            )
            svc.db.cache_search(topic, papers)

        await _send_long(update, review_text)

        if papers:
            listing = "\n".join(
                f"[{i + 1}] {p.short()}\n    {p.url}" for i, p in enumerate(papers)
            )
            await _send_long(update, "Sources:\n" + listing)
    except Exception as exc:  # noqa: BLE001
        log.exception("review failed")
        await update.effective_message.reply_text(f"Literature review failed: {exc}")


# -- citations ----------------------------------------------------------------
async def cmd_cite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    svc = _services(context)
    raw = " ".join(context.args or []).strip()
    if not raw:
        context.user_data[PENDING_KEY] = "cite_text"
        await update.effective_message.reply_text("Paste the source (title/authors/year/url) and I'll cite it.")
        return
    style = svc.db.get_citation_style(update.effective_user.id) if update.effective_user else "APA"
    await _typing(update)
    try:
        result = citations.cite_text(svc.llm, raw, style=style)
        await update.effective_message.reply_text(f"({style})\n{result}")
    except Exception as exc:  # noqa: BLE001
        log.exception("cite failed")
        await update.effective_message.reply_text(f"Citation failed: {exc}")


async def cmd_style(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    svc = _services(context)
    style = " ".join(context.args or []).strip().upper() or "APA"
    if update.effective_user:
        svc.db.set_citation_style(update.effective_user.id, style)
    await update.effective_message.reply_text(f"Citation style set to: {style}")


# -- proposal -----------------------------------------------------------------
async def cmd_proposal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    topic = " ".join(context.args or []).strip()
    if not topic:
        context.user_data[PENDING_KEY] = "proposal"
        await update.effective_message.reply_text("What's the proposal topic?")
        return
    await _do_proposal(update, context, topic)


async def _do_proposal(update: Update, context: ContextTypes.DEFAULT_TYPE, topic: str) -> None:
    svc = _services(context)
    await _typing(update)
    try:
        result = proposal.generate(svc.llm, topic)
        await _send_long(update, result)
    except Exception as exc:  # noqa: BLE001
        log.exception("proposal failed")
        await update.effective_message.reply_text(f"Proposal generation failed: {exc}")


# -- interpret ----------------------------------------------------------------
async def cmd_interpret(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = " ".join(context.args or []).strip()
    if not raw:
        context.user_data[PENDING_KEY] = "interpret"
        await update.effective_message.reply_text(
            "Paste the statistical content (e.g. p-values, confidence intervals, table)."
        )
        return
    await _do_interpret(update, context, raw)


async def _do_interpret(update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str) -> None:
    svc = _services(context)
    await _typing(update)
    try:
        result = interpret.interpret(svc.llm, raw)
        await _send_long(update, result)
    except Exception as exc:  # noqa: BLE001
        log.exception("interpret failed")
        await update.effective_message.reply_text(f"Interpretation failed: {exc}")


# -- convert ------------------------------------------------------------------
async def cmd_convert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[PENDING_KEY] = "convert"
    await update.effective_message.reply_text(
        "Send me a file to convert. I support:\n"
        "• PDF → Word (.docx)\n"
        "• PDF → PNG images\n"
        "• Word (.docx) → PDF\n"
        "• Word (.docx) → PNG images\n"
        "• Word (.docx) → Plain text (.txt)\n"
        "• TXT → Word (.docx)\n"
        "• TXT → PDF\n"
        "• Image (PNG/JPG) → PDF\n\n"
        "Upload your file now."
    )


async def _handle_convert_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle file upload when user is in convert mode."""
    msg = update.effective_message
    doc = msg.document
    if not doc:
        return

    context.user_data.pop(PENDING_KEY, None)

    mime = doc.mime_type or ""
    filename = doc.file_name or ""
    options = convert.detect_possible_conversions(mime, filename)

    if not options:
        await msg.reply_text(
            "I don't support converting this file type. Supported: PDF, Word (.docx), TXT, PNG, JPG."
        )
        return

    # Download and store the file data temporarily
    await _typing(update)
    try:
        tg_file = await doc.get_file()
        data = bytes(await tg_file.download_as_bytearray())
    except Exception as exc:  # noqa: BLE001
        await msg.reply_text(f"Failed to download file: {exc}")
        return

    context.user_data[CONVERT_FILE_KEY] = data
    context.user_data[CONVERT_FILENAME_KEY] = filename

    if len(options) == 1:
        # Only one option, do it directly
        await _execute_conversion(update, context, options[0])
    else:
        # Show inline keyboard with options
        keyboard = [
            [InlineKeyboardButton(convert.CONVERSION_LABELS.get(opt, opt), callback_data=f"conv:{opt}")]
            for opt in options
        ]
        await msg.reply_text(
            "Choose a conversion format:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def on_convert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button press for conversion choice."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("conv:"):
        return
    await query.answer()
    conversion_type = query.data.removeprefix("conv:")
    await _execute_conversion(update, context, conversion_type)


async def _execute_conversion(update: Update, context: ContextTypes.DEFAULT_TYPE, conv_type: str) -> None:
    """Run the actual conversion and send the result back."""
    data: bytes | None = context.user_data.pop(CONVERT_FILE_KEY, None)
    filename: str = context.user_data.pop(CONVERT_FILENAME_KEY, "file")

    chat = update.effective_chat
    if not chat:
        return

    if not data:
        if update.callback_query:
            await update.callback_query.edit_message_text("File data expired. Please /convert and upload again.")
        return

    try:
        await chat.send_action(ChatAction.UPLOAD_DOCUMENT)
    except Exception:  # noqa: BLE001
        pass

    base_name = filename.rsplit(".", 1)[0] if "." in filename else filename

    try:
        if conv_type == "pdf_to_word":
            result = convert.pdf_to_word(data)
            await chat.send_document(
                document=io.BytesIO(result),
                filename=f"{base_name}.docx",
                caption="Here's your Word document.",
            )

        elif conv_type == "pdf_to_png":
            images = convert.pdf_to_png(data)
            for i, img_bytes in enumerate(images[:20]):  # cap at 20 pages
                await chat.send_document(
                    document=io.BytesIO(img_bytes),
                    filename=f"{base_name}_page{i + 1}.png",
                    caption=f"Page {i + 1}" if i == 0 else None,
                )
            if len(images) > 20:
                await chat.send_message(f"(Showing first 20 of {len(images)} pages)")

        elif conv_type == "word_to_pdf":
            result = convert.word_to_pdf(data)
            await chat.send_document(
                document=io.BytesIO(result),
                filename=f"{base_name}.pdf",
                caption="Here's your PDF.",
            )

        elif conv_type == "word_to_png":
            images = convert.word_to_png(data)
            for i, img_bytes in enumerate(images[:20]):
                await chat.send_document(
                    document=io.BytesIO(img_bytes),
                    filename=f"{base_name}_page{i + 1}.png",
                    caption=f"Page {i + 1}" if i == 0 else None,
                )
            if len(images) > 20:
                await chat.send_message(f"(Showing first 20 of {len(images)} pages)")

        elif conv_type == "word_to_txt":
            text = convert.word_to_txt(data)
            txt_bytes = text.encode("utf-8")
            await chat.send_document(
                document=io.BytesIO(txt_bytes),
                filename=f"{base_name}.txt",
                caption="Here's the plain text extracted from your Word document.",
            )

        elif conv_type == "txt_to_word":
            text = data.decode("utf-8", errors="replace")
            result = convert.txt_to_word(text)
            await chat.send_document(
                document=io.BytesIO(result),
                filename=f"{base_name}.docx",
                caption="Here's your Word document.",
            )

        elif conv_type == "txt_to_pdf":
            text = data.decode("utf-8", errors="replace")
            result = convert.txt_to_pdf(text)
            await chat.send_document(
                document=io.BytesIO(result),
                filename=f"{base_name}.pdf",
                caption="Here's your PDF.",
            )

        elif conv_type in ("png_to_pdf", "jpg_to_pdf"):
            result = convert.png_to_pdf(data)
            await chat.send_document(
                document=io.BytesIO(result),
                filename=f"{base_name}.pdf",
                caption="Here's your image as a PDF.",
            )

        else:
            await chat.send_message(f"Unknown conversion type: {conv_type}")

    except Exception as exc:  # noqa: BLE001
        log.exception("Conversion failed: %s", conv_type)
        await chat.send_message(f"Conversion failed: {exc}")


# -- photo upload (for image → PDF conversion) --------------------------------
async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo uploads — only process if user is in convert mode."""
    pending = context.user_data.get(PENDING_KEY)
    if pending != "convert":
        return

    msg = update.effective_message
    if not msg or not msg.photo:
        return

    context.user_data.pop(PENDING_KEY, None)

    await _typing(update)
    try:
        # Get the highest resolution photo
        photo = msg.photo[-1]
        tg_file = await photo.get_file()
        data = bytes(await tg_file.download_as_bytearray())
        context.user_data[CONVERT_FILE_KEY] = data
        context.user_data[CONVERT_FILENAME_KEY] = "photo.png"
        await _execute_conversion(update, context, "png_to_pdf")
    except Exception as exc:  # noqa: BLE001
        log.exception("photo convert failed")
        await msg.reply_text(f"Failed to convert image: {exc}")


# -- catch-all text -----------------------------------------------------------
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not msg.text:
        return
    text = msg.text.strip()
    pending = context.user_data.pop(PENDING_KEY, None)

    if pending == "summarize":
        await _do_summarize(update, context, text)
    elif pending == "review":
        await _do_review(update, context, text)
    elif pending == "proposal":
        await _do_proposal(update, context, text)
    elif pending == "interpret":
        await _do_interpret(update, context, text)
    elif pending == "cite_text":
        # reuse cite path
        context.args = text.split()
        await cmd_cite(update, context)
    else:
        # No pending intent: gentle nudge.
        await msg.reply_text(
            "Not sure what to do with that. Try /help to see what I can do, "
            "or upload a PDF and I'll summarize it."
        )


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("Unhandled error", exc_info=context.error)
