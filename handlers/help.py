# =====================================
# handlers/help.py
# =====================================
from __future__ import annotations

import logging
from typing import List, Dict

from telegram import Update, BotCommand
from telegram.ext import ContextTypes, CommandHandler, Application

logger = logging.getLogger(__name__)

# Optional: human-friendly descriptions for known commands.
# Unknown commands still show up with a generic description.
DESCRIPTIONS: Dict[str, str] = {
    "help": "Show this help panel",
    "start": "Start / reset the bot",
    "menu": "Open the main menu",
    "trade": "Analyse a symbol and propose a trade (e.g. /trade XAUUSDc)",
    "analyse": "Alias of /trade",
    "pending": "Place a pending order (buy/sell stop/limit)",
    "positions": "Show open positions & P/L",
    "manage": "Open trade manager / manage open positions",
    "pause": "Pause trading (circuit breaker ON)",
    "resume": "Resume trading (circuit breaker OFF)",
    "loadcharts": "Arrange and tile MT5 charts",
    "scan": "Run the multi-timeframe scanner now",
    "journal": "Show recent trade journal entries",
    "balance": "Show account balance",
    "equity": "Show account equity",
    "risk": "Show current default risk %",
    "setrisk": "Set default risk % (e.g. /setrisk 1.0)",
    "advanceddashboard": "Advanced institutional analytics dashboard",
    "v8dashboard": "Advanced dashboard (legacy alias)",
    "news": "Economic calendar + headlines",
    "fundamentals": "Daily fundamentals/sentiment snapshot",
    "signal_status": "Show signal scanner status",
    "signal_test": "Manually trigger signal scan",
    "signal_config": "Show signal scanner configuration",
        "feature_test": "Test feature builder for a symbol",
        "feature_compare": "Compare features across symbols",
        "feature_export": "Export features to JSON file",
        "feature_help": "Show feature builder help",
        "router_status": "Show prompt router status and configuration",
        "router_test": "Test prompt router with sample data",
        "router_templates": "List available prompt templates",
        "router_validate": "Test prompt validator with sample data",
    # Add more as you like — unknown ones will still be listed.
}


def _collect_registered_commands(app: Application) -> List[str]:
    """
    Introspects the Application to find all CommandHandlers currently registered.
    """
    commands: List[str] = []
    try:
        # PTB v20+: app.handlers is {group: [handlers]}
        for _group, handlers in getattr(app, "handlers", {}).items():  # type: ignore[attr-defined]
            for h in handlers:
                if h.__class__.__name__ == "CommandHandler":
                    for cmd in getattr(h, "commands", set()):
                        commands.append(str(cmd))
    except Exception as e:
        logger.debug("Could not introspect handlers for commands: %s", e)

    # de-dupe preserving order
    seen = set()
    ordered = []
    for c in commands:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


async def _sync_bot_commands(app: Application) -> None:
    """
    Push discovered commands (with friendly descriptions where available)
    into Telegram's command menu so users see them when typing '/'.
    """
    try:
        discovered = _collect_registered_commands(app)
        if not discovered:
            return

        items = []
        for c in discovered:
            desc = DESCRIPTIONS.get(c, "Available command")
            items.append(BotCommand(c[:32], desc[:256]))
        await app.bot.set_my_commands(items)
    except Exception:
        logger.debug("set_my_commands failed", exc_info=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    found = _collect_registered_commands(app)
    if not found:
        found = sorted(DESCRIPTIONS.keys())

    lines = []
    for c in found:
        desc = DESCRIPTIONS.get(c, "Available command")
        lines.append(f"/{c} — {desc}")

    text = (
        "🆘 *Help*\n\n"
        "Here’s what I can do right now (based on what’s actually loaded):\n\n"
        + "\n".join(lines)
        + "\n\nTip: try `/trade XAUUSDc` to analyse gold."
    )

    try:
        await update.effective_message.reply_text(
            text, disable_web_page_preview=True, parse_mode="Markdown"
        )
    except Exception:
        await update.effective_message.reply_text(
            text.replace("*", "").replace("`", ""),
            disable_web_page_preview=True,
        )


def register_help_handlers(app: Application, sync_menu: bool = True) -> None:
    """
    Register /help and (optionally) sync Telegram '/' menu using the job queue.
    """
    app.add_handler(CommandHandler("help", help_command))
    # Optional: also show help on /start
    # app.add_handler(CommandHandler("start", help_command))

    if sync_menu:
        # Schedule a one-off job shortly after startup to await _sync_bot_commands
        async def _sync_menu_job(_ctx):
            await _sync_bot_commands(app)

        try:
            app.job_queue.run_once(_sync_menu_job, when=1, name="_sync_help_menu")
        except Exception:
            logger.debug("Failed to schedule slash-menu sync", exc_info=True)
