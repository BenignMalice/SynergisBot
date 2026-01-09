# =====================================
# handlers/journal.py
# =====================================
from __future__ import annotations
from telegram import Update, InputFile
from telegram.ext import ContextTypes


def register_journal_handlers(app, journal_repo, settings):
    async def journal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Send the journal CSV and/or SQLite database to the user.

        Historically the config used JOURNAL_CSV and JOURNAL_DB; newer versions
        use JOURNAL_CSV_PATH and JOURNAL_DB_PATH.  We try both names to find
        the journal files.  If neither file exists, we notify the user.
        """
        journal_repo.ensure()
        sent_any = False

        # Resolve CSV and DB paths from settings (support legacy names)
        csv_attr = None
        db_attr = None
        try:
            if hasattr(settings, "JOURNAL_CSV_PATH"):
                csv_attr = getattr(settings, "JOURNAL_CSV_PATH")
            elif hasattr(settings, "JOURNAL_CSV"):
                # JOURNAL_CSV may be a Path instance
                csv_attr = getattr(settings, "JOURNAL_CSV")
        except Exception:
            pass
        try:
            if hasattr(settings, "JOURNAL_DB_PATH"):
                db_attr = getattr(settings, "JOURNAL_DB_PATH")
            elif hasattr(settings, "JOURNAL_DB"):
                db_attr = getattr(settings, "JOURNAL_DB")
        except Exception:
            pass

        # Helper to send a file if path exists
        from pathlib import Path
        async def send_file(path_like, default_name: str):
            nonlocal sent_any
            try:
                p = Path(path_like)
                if p.exists():
                    with p.open("rb") as f:
                        await context.bot.send_document(
                            chat_id=update.effective_chat.id,
                            document=InputFile(f, filename=p.name or default_name),
                        )
                    sent_any = True
            except Exception:
                pass

        # Send CSV and DB if available
        if csv_attr:
            await send_file(csv_attr, "journal.csv")
        if db_attr:
            await send_file(db_attr, "journal.sqlite")

        await (update.message or update.callback_query.message).reply_text(
            "Journal sent. ✅" if sent_any else "No journal files found yet."
        )

    async def pnl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        days = 7
        if context.args:
            try:
                days = max(1, min(90, int(context.args[0])))
            except Exception:
                pass
        txt = journal_repo.pnl_summary(days)
        await (update.message or update.callback_query.message).reply_text(txt)

    app.add_handler(
        __import__("telegram.ext").ext.CommandHandler("journal", journal_command)
    )
    app.add_handler(__import__("telegram.ext").ext.CommandHandler("pnl", pnl_command))
