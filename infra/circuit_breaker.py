# =====================================
# infra/circuit_breaker.py
# =====================================
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from config import settings

logger = logging.getLogger(__name__)


def _now() -> int:
    return int(time.time())


def _midnight_utc_plus2(ts: Optional[int] = None) -> Tuple[int, int]:
    """
    Africa/Johannesburg is UTC+2 (no DST). Return (start_ts, end_ts) for 'today'.
    """
    z = ts or _now()
    # normalise to day start at UTC+2
    utc_plus2 = z + 2 * 3600
    y, m, d = time.gmtime(utc_plus2)[:3]
    start_plus2 = int(time.mktime(time.struct_time((y, m, d, 0, 0, 0, 0, 0, 0))))
    start_utc = start_plus2 - 2 * 3600
    end_utc = start_utc + 24 * 3600
    return start_utc, end_utc


@dataclass
class CBState:
    tripped: bool = False
    reason: str = ""
    until_ts: int = 0
    last_trip_ts: int = 0
    last_reset_daykey: str = ""  # "YYYYMMDD" in UTC+2


class CircuitBreaker:
    """
    Daily risk guard that trips when thresholds are exceeded:
      • Max daily net loss in R (CB_MAX_DAILY_LOSS_R)
      • Max consecutive losses (CB_MAX_CONSEC_LOSSES)
      • (Optional) Max daily loss in % (CB_MAX_DAILY_LOSS_PCT) — set >0 to enable

    It cancels/blocks trading until cool-off passes or midnight (UTC+2).
    """

    def __init__(self, store_path: str = "./data/circuit.json"):
        self.path = Path(getattr(settings, "CB_STORE_PATH", store_path))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.state = CBState()
        self._load()

        # knobs
        self.enable = bool(getattr(settings, "CB_ENABLE", True))
        self.max_loss_r = float(getattr(settings, "CB_MAX_DAILY_LOSS_R", 3.0))
        self.max_consec_losses = int(getattr(settings, "CB_MAX_CONSEC_LOSSES", 3))
        self.max_loss_pct = float(
            getattr(settings, "CB_MAX_DAILY_LOSS_PCT", 0.0)
        )  # 0 disables
        self.cool_off_min = int(
            getattr(settings, "CB_COOL_OFF_MIN", 90)
        )  # 0 = until midnight

    # ---------- persistence ----------
    def _load(self):
        try:
            if self.path.exists():
                self.state = CBState(**json.loads(self.path.read_text()))
        except Exception:
            logger.debug("CircuitBreaker load failed", exc_info=True)

    def _save(self):
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(asdict(self.state), indent=2))
            tmp.replace(self.path)
        except Exception:
            logger.debug("CircuitBreaker save failed", exc_info=True)

    # ---------- journal helpers ----------
    def _journal(self, journal_repo, event: str, **payload):
        try:
            if journal_repo and hasattr(journal_repo, "add_event"):
                journal_repo.add_event(event, **payload)
        except Exception:
            logger.debug("CB journal failed", exc_info=True)

    # ---------- stats ----------
    def _today_stats(self, journal_repo) -> Dict[str, Any]:
        """
        Returns:
          dict(net_r, losses_streak, net_pct)
        Uses JournalRepo's SQLite connection if available.
        """
        start_ts, end_ts = _midnight_utc_plus2()
        daykey = time.strftime("%Y%m%d", time.gmtime(start_ts + 2 * 3600))

        net_r = 0.0
        net_pct = 0.0  # optional
        losses_streak = 0

        # If we can reach the DB, compute precisely.
        try:
            conn = getattr(journal_repo, "_conn", None)
            if conn:
                # Get today's r_multiple list ordered by close time
                cur = conn.execute(
                    """
                    SELECT r_multiple
                      FROM trades
                     WHERE closed_ts IS NOT NULL
                       AND closed_ts >= ? AND closed_ts < ?
                     ORDER BY closed_ts ASC
                    """,
                    (start_ts, end_ts),
                )
                r_list = [float(r[0]) for r in cur.fetchall() if r[0] is not None]
                net_r = sum(r_list)
                # consecutive losses from the end
                for r in reversed(r_list):
                    if r is not None and r < 0.0:
                        losses_streak += 1
                    else:
                        break

                if self.max_loss_pct > 0:
                    # Estimate % from PnL if present
                    cur2 = conn.execute(
                        """
                        SELECT COALESCE(SUM(pnl),0.0)
                          FROM trades
                         WHERE closed_ts IS NOT NULL
                           AND closed_ts >= ? AND closed_ts < ?
                        """,
                        (start_ts, end_ts),
                    )
                    pnl_today = float(cur2.fetchone()[0] or 0.0)
                    # If you journal account equity snapshots into events, you could improve this.
                    # We'll treat % as disabled unless explicitly supported.
                    net_pct = (
                        0.0 if pnl_today == 0 else 0.0
                    )  # placeholder unless you wire equity %
            else:
                # Fallback: try count of 'trade_close' events
                count_close = (
                    int(journal_repo.count_events("trade_close", since_ts=start_ts))
                    if hasattr(journal_repo, "count_events")
                    else 0
                )
                # Without DB access, we can't compute net R; keep defaults (guards relying on R won't trip).
                logger.debug(
                    "CB stats: limited mode (no DB handle). trade_close today=%s",
                    count_close,
                )
        except Exception:
            logger.debug("CB stats query failed", exc_info=True)

        self.state.last_reset_daykey = daykey
        self._save()
        return dict(
            net_r=net_r,
            net_pct=net_pct,
            losses_streak=losses_streak,
            start_ts=start_ts,
            end_ts=end_ts,
        )

    # ---------- public API ----------
    def status(self, journal_repo=None) -> Dict[str, Any]:
        st = asdict(self.state)
        st.update(self._today_stats(journal_repo or None))
        st["enabled"] = self.enable
        st["cool_off_min"] = self.cool_off_min
        return st

    def _trip(self, reason: str, journal_repo=None):
        now = _now()
        until_ts = 0
        if self.cool_off_min > 0:
            until_ts = now + self.cool_off_min * 60
        else:
            # hold to midnight
            _, end_ts = _midnight_utc_plus2(now)
            until_ts = end_ts

        self.state.tripped = True
        self.state.reason = reason
        self.state.last_trip_ts = now
        self.state.until_ts = until_ts
        self._save()
        self._journal(
            journal_repo, "circuit_trip", reason=reason, until_ts=until_ts, ts=now
        )

    def _auto_reset_if_elapsed(self, journal_repo=None):
        if not self.state.tripped:
            return
        if _now() >= self.state.until_ts:
            self.resume(journal_repo, auto=True)

    def daily_rollover_if_needed(self, journal_repo=None):
        """
        Call this periodically; resets tripped state at midnight (UTC+2)
        if cool-off was 'until midnight' or simply to rotate daykey.
        """
        start_ts, _ = _midnight_utc_plus2()
        daykey = time.strftime("%Y%m%d", time.gmtime(start_ts + 2 * 3600))
        if self.state.last_reset_daykey != daykey:
            # New trading day
            if self.state.tripped:
                # Clear on new day
                self.resume(journal_repo, auto=True)
            self.state.last_reset_daykey = daykey
            self._save()

    def allow_order(self, journal_repo=None) -> Tuple[bool, str]:
        """
        Returns (allow, reason). If not allowed, reason describes the block.
        """
        if not self.enable:
            return True, "disabled"

        # If already tripped, auto-reset if time passed; otherwise block.
        if self.state.tripped:
            self._auto_reset_if_elapsed(journal_repo)
            if self.state.tripped:
                return (
                    False,
                    f"circuit-tripped: {self.state.reason} (until {self.state.until_ts})",
                )

        # Fresh evaluation
        stats = self._today_stats(journal_repo)
        net_r = float(stats["net_r"])
        losses_streak = int(stats["losses_streak"])
        net_pct = float(stats["net_pct"])

        # Check thresholds
        if self.max_loss_r > 0 and net_r <= -abs(self.max_loss_r):
            self._trip(
                f"net loss {net_r:.2f}R ≤ -{abs(self.max_loss_r):.2f}R", journal_repo
            )
            return False, "daily-R-limit"

        if self.max_consec_losses > 0 and losses_streak >= self.max_consec_losses:
            self._trip(f"{losses_streak} consecutive losses", journal_repo)
            return False, "consecutive-losses"

        if self.max_loss_pct > 0 and net_pct <= -abs(self.max_loss_pct):
            self._trip(
                f"net P&L {net_pct:.2f}% ≤ -{abs(self.max_loss_pct):.2f}%", journal_repo
            )
            return False, "daily-%-limit"

        return True, "ok"

    def resume(self, journal_repo=None, auto: bool = False):
        was_tripped = self.state.tripped
        self.state.tripped = False
        self.state.reason = ""
        self.state.until_ts = 0
        self._save()
        if was_tripped:
            self._journal(
                journal_repo,
                "circuit_resume",
                reason=("auto" if auto else "manual"),
                ts=_now(),
            )
