"""
handlers/status.py
===================

This module implements a simple `/status` command that provides a snapshot
of the account and trading state: equity, free margin, balance, open positions,
armed pendings, open PnL, and today's PnL.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import MetaTrader5 as mt5
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, Application

from infra.mt5_service import MT5Service
from infra.pseudo_pendings import PseudoPendingManager

logger = logging.getLogger(__name__)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message or update.callback_query.message
    chat_id = update.effective_chat.id

    mt5svc = MT5Service()
    try:
        mt5svc.connect()
    except Exception as e:
        logger.debug("/status: MT5 connect failed", exc_info=True)
        await msg.reply_text(f"⚠️ MT5 connection failed: {e}")
        return

    try:
        ai = mt5.account_info()
        equity = float(getattr(ai, "equity", 0.0) or 0.0) if ai else 0.0
        free_margin = float(getattr(ai, "margin_free", 0.0) or 0.0) if ai else 0.0
        balance = float(getattr(ai, "balance", 0.0) or 0.0) if ai else 0.0
    except Exception:
        equity = free_margin = balance = 0.0

    positions = []
    try:
        positions = mt5.positions_get()
    except Exception:
        positions = []
    n_pos = len(positions) if positions else 0
    open_pnl = 0.0
    if positions:
        try:
            for pos in positions:
                pnl = float(getattr(pos, "profit", 0.0) or 0.0)
                open_pnl += pnl
        except Exception:
            open_pnl = 0.0

    pending_manager: Optional[PseudoPendingManager] = context.application.bot_data.get(
        "pending_manager"
    )
    n_pend = 0
    if pending_manager:
        try:
            n_pend = len(pending_manager.list_for_chat(chat_id))
        except Exception:
            n_pend = 0

    today_pnl = 0.0
    try:
        now = datetime.utcnow()
        start = datetime.combine(now.date(), datetime.min.time())
        deals = mt5.history_deals_get(start, now)
        if deals:
            for d in deals:
                today_pnl += float(getattr(d, "profit", 0.0) or 0.0)
    except Exception:
        today_pnl = 0.0

    text_lines = ["**Account Status:**"]
    text_lines.append(f"Equity: {equity:.2f}")
    text_lines.append(f"Free Margin: {free_margin:.2f}")
    text_lines.append(f"Balance: {balance:.2f}")
    text_lines.append(f"Open positions: {n_pos}")
    text_lines.append(f"Armed pendings: {n_pend}")
    text_lines.append(f"Open P&L: {open_pnl:.2f}")
    text_lines.append(f"Today P&L: {today_pnl:.2f}")

    await msg.reply_text("\n".join(text_lines), parse_mode="Markdown")


def register_status_handler(app: Application) -> None:
    app.add_handler(CommandHandler("status", status_command))
