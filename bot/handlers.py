"""Telegram command and message handlers."""
from __future__ import annotations

import logging
from typing import cast

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from core import pdf
from features import (
    citations,
    gap_analysis,
    interpret,
    literature_review,
    proposal,
    summarize,
)

from .services import Services

log = logging.getLogger(__name__)

PENDING_KEY = "pending_intent"  # one of: "summarize", "interpret", "cite_text", "review", "proposal"

WELCOME = (
    "*College-In Research Assistant*\n\n"
    "I help you analyze papers and accelerate your research.\n\n"
    "*Commands*\n"
    "/summarize \\- send a PDF or paste a paper URL/abstract\n"
    "/gaps \\- find research gaps in your last paper\n"
    "/review <topic> \\- literature review across arXiv \\+ PubMed\n"
    "/cite <text> \\- generate a citation\n"
    "/style <APA\\|IEEE\\|MLA\\|Chicago\\|BibTeX> \\- set citation style\n"
    "/proposal <topic> \\- write a research proposal\n"
    "/interpret <stats text> \\- explain statistics in plain language\n"
    "/help \\- show this message\n\n"
    "Tip: you can also just upload a PDF and I'll summarize it\\."
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
    if not (doc.mime_type == "application/pdf" or (doc.file_name or "").lower().endswith(".pdf")):
        await msg.reply_text("Please send a PDF file.")
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
