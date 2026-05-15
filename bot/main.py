"""Telegram bot entrypoint (long polling)."""
from __future__ import annotations

import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import Settings, configure_logging

from .handlers import (
    cmd_cite,
    cmd_convert,
    cmd_gaps,
    cmd_help,
    cmd_interpret,
    cmd_proposal,
    cmd_review,
    cmd_start,
    cmd_style,
    cmd_summarize,
    on_convert_callback,
    on_document,
    on_error,
    on_photo,
    on_text,
)
from .services import Services


def build_application(settings: Settings) -> Application:
    services = Services.build(settings)
    app = Application.builder().token(settings.telegram_token).build()
    app.bot_data["services"] = services

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("summarize", cmd_summarize))
    app.add_handler(CommandHandler("gaps", cmd_gaps))
    app.add_handler(CommandHandler("review", cmd_review))
    app.add_handler(CommandHandler("cite", cmd_cite))
    app.add_handler(CommandHandler("style", cmd_style))
    app.add_handler(CommandHandler("proposal", cmd_proposal))
    app.add_handler(CommandHandler("interpret", cmd_interpret))
    app.add_handler(CommandHandler("convert", cmd_convert))

    app.add_handler(CallbackQueryHandler(on_convert_callback, pattern=r"^conv:"))
    app.add_handler(MessageHandler(filters.Document.ALL, on_document))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    app.add_error_handler(on_error)
    return app


def main() -> None:
    settings = Settings.load()
    configure_logging(settings.log_level)
    logging.getLogger(__name__).info("Starting College-In Research Assistant bot")
    app = build_application(settings)
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
