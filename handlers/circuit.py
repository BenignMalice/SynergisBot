# =====================================
# handlers/circuit.py
# =====================================
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from infra.circuit_breaker import CircuitBreaker


def register_circuit_handlers(app: Application, circuit: CircuitBreaker, journal_repo):
    async def _resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
        circuit.resume(journal_repo, auto=False)
        await update.effective_message.reply_text(
            "🟢 Trading resumed. Circuit breaker reset."
        )

    async def _circuit(update: Update, context: ContextTypes.DEFAULT_TYPE):
        st = circuit.status(journal_repo)
        msg = (
            "⚙️ Circuit status\n"
            f"• Enabled: {st['enabled']}\n"
            f"• Tripped: {st['tripped']}\n"
            f"• Reason: {st['reason'] or '—'}\n"
            f"• Until: {st['until_ts'] or '—'}\n"
            f"• Today net R: {st['net_r']:.2f}\n"
            f"• Loss streak: {st['losses_streak']}\n"
            f"• Cool-off (min): {st['cool_off_min']}"
        )
        await update.effective_message.reply_text(msg)

    app.add_handler(CommandHandler("resume", _resume))
    app.add_handler(CommandHandler("circuit", _circuit))
