from __future__ import annotations
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from pathlib import Path

from config import settings
from infra.chart_arranger import ChartArranger
from trade_manager import (
    monitor_live_trades,
    register_chat,
)  # background loop & chat registry


async def loadcharts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🥇 XAUUSDc", callback_data="loadcharts_XAUUSDc")],
            [InlineKeyboardButton("₿ BTCUSDc", callback_data="loadcharts_BTCUSDc")],
            [InlineKeyboardButton("Ξ ETHUSDc", callback_data="loadcharts_ETHUSDc")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_menu")],
        ]
    )
    reply = update.message or update.callback_query.message
    await reply.reply_text(
        "Select the symbol to load and arrange charts:", reply_markup=kb
    )


def write_chartload_command(common_dir: Path, symbol: str) -> Path:
    common_dir.mkdir(parents=True, exist_ok=True)
    path = common_dir / "chartload.txt"
    path.write_text(f"symbol={symbol}\ntimeframes=M5,M15,M30,H1,H4\n", encoding="utf-8")
    return path


async def run_manager_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the live trade manager loop and remember this chat for notifications."""
    register_chat(update.effective_chat.id)
    reply = update.message or update.callback_query.message
    await reply.reply_text("Starting live-trade monitor (market-only adjustments)…")
    # Fire-and-forget the monitor loop
    asyncio.create_task(monitor_live_trades(context.bot))
    await reply.reply_text("Manager loop started ✅")


async def button_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Central callback router for charts + manager buttons."""
    query = update.callback_query
    data = query.data

    # Load charts submenu trigger
    if data == "loadcharts":
        return await loadcharts_menu(update, context)

    # Specific symbol load + arrange
    if data.startswith("loadcharts_"):
        arranger = ChartArranger(
            settings.MT5_WINDOW_TITLE,
            settings.AHK_EXE,
            settings.AHK_SCRIPT,
            settings.AUTO_ARRANGE,
        )
        symbol = data.split("_", 1)[1]
        try:
            write_chartload_command(settings.MT5_FILES_DIR, symbol)
            arranger.arrange()
            await query.message.reply_text(
                "Attempted to arrange charts. Sending screenshot…"
            )
            buf = arranger.screenshot()
            await query.message.reply_photo(buf)
        except Exception as e:
            await query.message.reply_text(f"❌ Load charts error: {e}")
        return

    # Run manager from inline button
    if data == "run_manager":
        return await run_manager_command(update, context)

    # Back to menu hint
    if data == "back_to_menu":
        await query.message.reply_text("Back to menu. Use /menu.")
        return
