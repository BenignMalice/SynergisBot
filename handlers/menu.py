# =====================================
# handlers/menu.py
# =====================================
from __future__ import annotations

import logging
from typing import List, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from handlers.trading import trade_command
from handlers.pending import pending_command, pendings_list_command
from handlers.status import status_command  # new status command

logger = logging.getLogger(__name__)

PAIRS: List[Tuple[str, str]] = [
    ("BTCUSDc", "₿ BTCUSDc"),
    ("XAUUSDc", "🥇 XAUUSDc"),
    ("ETHUSDc", "Ξ ETHUSDc"),
    ("AUDCADc", "💱 AUDCADc"),
    ("EURGBPc", "💱 EURGBPc"),
    ("EURUSDc", "💱 EURUSDc"),
    ("GBPNZDc", "💱 GBPNZDc"),
    ("GBPUSDc", "💱 GBPUSDc"),
    ("NZDJPYc", "💱 NZDJPYc"),
    ("NZDUSDc", "💱 NZDUSDc"),
    ("USDJPYc", "💱 USDJPYc"),
]


def main_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🧠 Trade", callback_data="menu|trade")],
            [InlineKeyboardButton("⏳ Pending Trade", callback_data="menu|pending")],
            [InlineKeyboardButton("📝 List Trades", callback_data="menu|list")],
        ]
    )


def _main_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        # AI & Analysis
        [InlineKeyboardButton("🤖 ChatGPT Assistant", callback_data="menu|chatgpt")],
        [InlineKeyboardButton("📊 Market Analysis", callback_data="menu|analysis")],
        
        # Trading
        [InlineKeyboardButton("🧠 Trade", callback_data="menu|trade")],
        [InlineKeyboardButton("⏳ Pending Trade", callback_data="menu|pending")],
        
        # Account & Status
        [InlineKeyboardButton("💰 Account Status", callback_data="menu|status")],
        [InlineKeyboardButton("📝 List Trades", callback_data="menu|list")],
        
        # Charts & Tools
        [InlineKeyboardButton("📈 Charts", callback_data="menu|charts")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="menu|help")],
    ]
    return InlineKeyboardMarkup(rows)


def _trade_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"trade|{sym}")]
        for sym, label in PAIRS
    ]
    rows.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu|back")])
    return InlineKeyboardMarkup(rows)


def _pending_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"pendmenu|{sym}")]
        for sym, label in PAIRS
    ]
    rows.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu|back")])
    return InlineKeyboardMarkup(rows)


async def start_menu(update: Update, _: ContextTypes.DEFAULT_TYPE):
    msg = update.message or update.callback_query.message
    await msg.reply_text("Choose an option:", reply_markup=_main_menu_kb())


async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return
    await q.answer()
    data = q.data or ""
    logger.debug("menu_router data=%r", data)

    parts = data.split("|", 1)
    if len(parts) != 2 or parts[0] != "menu":
        return

    action = parts[1]
    
    # AI & Analysis
    if action == "chatgpt":
        await q.message.reply_text(
            "🤖 **ChatGPT Trading Assistant**\n\n"
            "Start a conversation with AI:\n"
            "`/chatgpt` - Start ChatGPT session\n\n"
            "Ask me anything:\n"
            "• 'Give me a trade for XAUUSD'\n"
            "• 'Analyze BTCUSD'\n"
            "• 'What's my balance?'\n"
            "• 'Should I buy or sell?'\n\n"
            "I can fetch real-time data, analyze markets, and execute trades!",
            parse_mode="Markdown"
        )
        return
    
    if action == "analysis":
        await q.message.reply_text(
            "📊 **Market Analysis**\n\n"
            "Get AI-powered analysis:\n"
            "• `/chatgpt` - Ask ChatGPT to analyze any symbol\n"
            "• Real-time RSI, ADX, EMAs\n"
            "• Market regime detection\n"
            "• Trade recommendations\n\n"
            "Try: `/chatgpt` then say 'Analyze XAUUSD'",
            parse_mode="Markdown"
        )
        return
    
    if action == "status":
        await status_command(update, context)
        return
    
    if action == "charts":
        from handlers.charts import loadcharts_menu
        await loadcharts_menu(update, context)
        return
    
    if action == "help":
        from handlers.help import help_command
        await help_command(update, context)
        return
    
    # Trading
    if action == "trade":
        await q.message.edit_text("Trade menu:", reply_markup=_trade_menu_kb())
        return
    if action == "pending":
        await q.message.edit_text(
            "Pending trade menu:", reply_markup=_pending_menu_kb()
        )
        return
    if action == "list":
        await pendings_list_command(update, context)
        return
    if action == "back":
        await q.message.edit_text("Choose an option:", reply_markup=_main_menu_kb())
        return


async def trade_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return
    await q.answer()
    data = q.data or ""
    logger.debug("trade_menu_router data=%r", data)

    _, sym = data.split("|", 1)
    try:
        await q.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await trade_command(update, context, symbol=sym)


async def pending_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return
    await q.answer()
    data = q.data or ""
    logger.debug("pending_menu_router data=%r", data)

    _, sym = data.split("|", 1)
    try:
        await q.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await pending_command(update, context, symbol=sym)


async def noop_button(update: Update, _: ContextTypes.DEFAULT_TYPE):
    try:
        await update.callback_query.answer("Already handled ✅", cache_time=1)
    except Exception:
        pass


def register_menu_handlers(
    app: Application,
    *,
    commands_group: int = 0,
    callbacks_group: int = 1,
) -> None:
    """
    Register menu commands in an early group (0) and callbacks later (1),
    so slash-commands like /trade are never pre-empted by callback routers.
    """
    # --- Commands (group 0 by default)
    app.add_handler(CommandHandler("start", start_menu), group=commands_group)
    app.add_handler(CommandHandler("menu", start_menu), group=commands_group)
    app.add_handler(CommandHandler("status", status_command), group=commands_group)

    # --- Callback buttons (group 1 by default)
    app.add_handler(
        CallbackQueryHandler(menu_router, pattern=r"^menu\|"), group=callbacks_group
    )
    app.add_handler(
        CallbackQueryHandler(trade_menu_router, pattern=r"^trade\|"),
        group=callbacks_group,
    )
    app.add_handler(
        CallbackQueryHandler(pending_menu_router, pattern=r"^pendmenu\|"),
        group=callbacks_group,
    )
    app.add_handler(
        CallbackQueryHandler(noop_button, pattern=r"^noop$"), group=callbacks_group
    )
