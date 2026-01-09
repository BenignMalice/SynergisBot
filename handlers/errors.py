# =====================================
# handlers/errors.py
# =====================================
from __future__ import annotations
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def register_error_handler(app):
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.exception("Telegram error", exc_info=context.error)
        try:
            if isinstance(update, Update):
                msg = update.effective_message
                if msg:
                    await msg.reply_text("⚠️ A small wobble occurred. Try again?")
        except Exception:
            pass

    app.add_error_handler(error_handler)
