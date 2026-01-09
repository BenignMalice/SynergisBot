# =====================================
# infra/scheduler.py
# =====================================
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
import asyncio
from typing import Optional, Callable, Awaitable

from config import settings

_log = logging.getLogger("infra.scheduler")
logger = logging.getLogger(__name__)

# Throttle state (module-level so it persists across JobQueue ticks)
_LAST_SNAPSHOT_TS: float | None = None
_LAST_JOURNAL_TS: float | None = None

# Defaults (seconds)
DEFAULT_SNAPSHOT_EVERY = 300  # 5 minutes
DEFAULT_JOURNAL_EVERY = 300  # 5 minutes


def _get_poll_interval() -> float:
    try:
        v = float(getattr(settings, "PENDING_MONITOR_SECS", 5))
        return max(1.0, v)
    except Exception:
        return 5.0


def start_pending_monitor(
    app,  # telegram.Application or similar
    pm,  # VirtualPendingManager
    mt5svc,  # MT5Service
    journal_repo=None,
    notify_async: Optional[Callable[[int, str], Awaitable[None]]] = None,
):
    """
    Spawns an asyncio task that polls virtual pendings and fills/cancels OCO etc.
    Call once at startup after your bot and services are ready.
    """
    if notify_async is None:

        async def notify_async(chat_id: int, text: str) -> None:
            try:
                await app.bot.send_message(chat_id=chat_id, text=text)
            except Exception:
                _log.warning("notify_async send failed", exc_info=True)

    async def _runner():
        interval = _get_poll_interval()
        _log.info("Pending monitor started (interval=%.1fs)", interval)
        while True:
            try:
                pm.poll_once(
                    mt5svc=mt5svc,
                    notify_async=notify_async,
                    journal_repo=journal_repo,
                    poswatch=None,
                    circuit=None,
                )
            except Exception:
                _log.exception("pending monitor iteration failed")
                # small backoff on error
                await asyncio.sleep(2.0)
            else:
                await asyncio.sleep(interval)

    # Prefer Application.create_task (PTB v20+) if present; else fall back
    try:
        create_task = getattr(app, "create_task", None)
        if callable(create_task):
            create_task(_runner(), name="pending_monitor")
        else:
            loop = asyncio.get_running_loop()
            loop.create_task(_runner(), name="pending_monitor")
    except RuntimeError:
        # No running loop yet; schedule on default policy loop
        loop = asyncio.get_event_loop()
        loop.create_task(_runner(), name="pending_monitor")

    _log.debug("pending_monitor task created")


async def history_watcher(
    app,
    mt5svc,
    journal,
    interval_seconds: int,
    *,
    snapshot_every: int | None = None,
    journal_every: int | None = None,
) -> None:
    """
    Single tick. Do a little housekeeping, then exit quickly.
    Called by PTB JobQueue on a schedule (so do NOT loop here).

    - Optionally snapshot balance/equity (rate-limited to avoid log spam)
    - Optionally ensure/flush journal (also rate-limited)
    """
    global _LAST_SNAPSHOT_TS, _LAST_JOURNAL_TS

    try:
        now_ts = time.time()

        # ---- Balance/Equity snapshot (INFO, throttled) ----
        snap_every = (
            snapshot_every
            if snapshot_every is not None
            else max(DEFAULT_SNAPSHOT_EVERY, 2 * max(1, int(interval_seconds)))
        )
        if _LAST_SNAPSHOT_TS is None or (now_ts - _LAST_SNAPSHOT_TS) >= snap_every:
            try:
                bal, eq = mt5svc.account_bal_eq()
                logger.info(
                    "Acct snapshot: balance=%.2f equity=%.2f @ %s",
                    bal,
                    eq,
                    datetime.now(timezone.utc).isoformat(),
                )
            except Exception:
                # Non-fatal: MT5 might be disconnected briefly
                logger.debug("account_bal_eq() failed during snapshot.", exc_info=True)
            _LAST_SNAPSHOT_TS = now_ts

        # ---- Journal housekeeping (throttled) ----
        jrnl_every = (
            journal_every if journal_every is not None else DEFAULT_JOURNAL_EVERY
        )
        if _LAST_JOURNAL_TS is None or (now_ts - _LAST_JOURNAL_TS) >= jrnl_every:
            try:
                # Ensure/rotate if your repo exposes it
                if getattr(journal, "ensure", None):
                    journal.ensure()
            except Exception:
                logger.debug("journal.ensure() failed.", exc_info=True)

            try:
                # Optional flush if available
                if getattr(journal, "flush", None):
                    journal.flush()
            except Exception:
                logger.debug("journal.flush() failed.", exc_info=True)

            _LAST_JOURNAL_TS = now_ts

        # Return quickly; JobQueue will call us again on schedule
        return

    except Exception as e:
        logger.warning("history_watcher tick error: %s", e, exc_info=True)
        return
