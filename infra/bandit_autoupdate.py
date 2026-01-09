# =====================================
# infra/bandit_autoupdate.py
# =====================================
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Callable

from config import settings

logger = logging.getLogger("infra.bandit_autoupdate")
logger.setLevel(logging.DEBUG)
logger.propagate = True

# Import the bandit updater from the selector we wrote
try:
    from infra.strategy_selector import bandit_update_from_trade
except Exception as e:  # pragma: no cover
    raise ImportError(f"Missing infra.strategy_selector.bandit_update_from_trade: {e}")

# Heuristics: which journal event names we’ll treat as “closure-ish”
_CLOSURE_EVENTS = {
    # common
    "tp_hit",
    "sl_hit",
    "close_by_rule",
    "manual_close",
    "position_closed",
    # fallbacks/aliases seen in bots
    "exit_tp",
    "exit_sl",
    "exit_rule",
    "breakeven_close",
}


def _json_loads_safe(s: str) -> dict:
    try:
        return json.loads(s) if isinstance(s, str) and s else {}
    except Exception:
        return {}


def _extract_features_from_event(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a small feature dict for the bandit from a journal event row.
    Prefers 'extra' JSON; falls back to top-level fields when present.
    Keys expected by the bandit: adx, bb_width, rsi_align (optional), session, regime_scores.
    """
    extra = (
        _json_loads_safe(row.get("extra", ""))
        if isinstance(row.get("extra", ""), str)
        else (row.get("extra") or {})
    )
    feat: Dict[str, Any] = {}
    # try explicit tech snapshots first
    snap = extra.get("tech") or extra.get("snapshot") or extra
    # tolerant extraction
    feat["adx"] = float(snap.get("adx") or snap.get("adx_14") or row.get("adx") or 0.0)
    feat["bb_width"] = float(snap.get("bb_width") or row.get("bb_width") or 0.0)
    # rsi_align is optional; if you only have RSI(14), map it to [-1,1] around 50
    rsi14 = snap.get("rsi_align")
    if rsi14 is None:
        rsi = snap.get("rsi_14") or row.get("rsi_14")
        if rsi is not None:
            try:
                rsi = float(rsi)
                rsi14 = max(-1.0, min(1.0, (rsi - 50.0) / 50.0))
            except Exception:
                rsi14 = None
    feat["rsi_align"] = rsi14 if rsi14 is not None else 0.0
    feat["session"] = (snap.get("session") or row.get("session") or "").upper()

    # regime scores if present
    rs = snap.get("regime_scores") or row.get("regime_scores") or {}
    if isinstance(rs, dict):
        feat["regime_scores"] = {
            "trend": float(rs.get("trend") or 0.0),
            "range": float(rs.get("range") or 0.0),
            "volatile": float(rs.get("volatile") or 0.0),
        }
    else:
        feat["regime_scores"] = {}
    return feat


def _ticket_from_event(row: Dict[str, Any]) -> Optional[int]:
    for k in ("ticket", "position", "deal", "order"):
        v = row.get(k)
        try:
            if v is not None:
                return int(v)
        except Exception:
            continue
    return None


def _should_trigger_close(event: str, row: Dict[str, Any]) -> bool:
    ev = (event or "").lower().strip()
    if ev in _CLOSURE_EVENTS:
        return True
    # or if r_multiple is already provided in the event row
    try:
        r = row.get("r_multiple")
        return r is not None and str(r) != ""
    except Exception:
        return False


def _resolve_strategy_symbol_journal(
    journal_repo: Any, ticket: Optional[int]
) -> tuple[Optional[str], Optional[str], Optional[float]]:
    """
    Query the journal's trades table for (strategy, symbol, r_multiple) by ticket.
    Returns (strategy, symbol, r_multiple) or (None, None, None) if unavailable.
    """
    if not journal_repo or ticket is None:
        return None, None, None
    try:
        if not hasattr(journal_repo, "_conn") or journal_repo._conn is None:
            return None, None, None
        cur = journal_repo._conn.cursor()
        cur.execute(
            "SELECT strategy, symbol, r_multiple FROM trades WHERE ticket = ? ORDER BY opened_ts DESC LIMIT 1",
            (int(ticket),),
        )
        row = cur.fetchone()
        if not row:
            return None, None, None
        strat = row[0] if row[0] else None
        symbol = row[1] if row[1] else None
        rmult = float(row[2]) if row[2] is not None else None
        return strat, symbol, rmult
    except Exception:
        logger.debug("bandit resolve failed for ticket=%s", ticket, exc_info=True)
        return None, None, None


def _compute_reward(r_multiple: Optional[float], event_row: Dict[str, Any]) -> float:
    """
    Reward shaping. Prefer realized R from the trade row; else fallback to event row.
    Clips to [-1.0, +2.0] by default.
    """
    try:
        r = float(r_multiple if r_multiple is not None else event_row.get("r_multiple"))
    except Exception:
        r = 0.0
    r = max(-1.0, min(2.0, r))
    return r


def _safe_selector_path() -> str:
    try:
        return getattr(
            settings, "STRATEGY_SELECTOR_PATH", "data/strategy_selector.json"
        )
    except Exception:
        return "data/strategy_selector.json"


def wire_bandit_updates(journal_repo: Any) -> None:
    """
    Idempotently wraps journal_repo.add_event / write_event so that when a trade closes,
    we update the bandit with (symbol, strategy, tech_features, reward).
    """
    if not journal_repo:
        return
    # Don’t double-wrap
    if getattr(journal_repo, "_bandit_wired", False):
        return

    def _wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        def _inner(*args, **kwargs):
            # Original write first (so DB is updated)
            try:
                res = fn(*args, **kwargs)
            except Exception:
                # Even if original write fails, surface the error and stop
                raise

            # Extract a normalized event row
            row = {}
            if args and isinstance(args[-1], dict) and "event" in args[-1]:
                # write_event(self, {"event": "...", ...})
                row = dict(args[-1])
            else:
                # add_event(self, event="...", **data)
                row = dict(kwargs or {})
                if "event" not in row and args:
                    row["event"] = args[1] if len(args) > 1 else kwargs.get("event")

            event = (row.get("event") or "").lower().strip()
            if not _should_trigger_close(event, row):
                return res

            ticket = _ticket_from_event(row)
            strat, symbol, r_from_trade = _resolve_strategy_symbol_journal(
                journal_repo, ticket
            )
            # If we still don’t know symbol, accept a direct event symbol
            if symbol is None:
                symbol = row.get("symbol")

            # Build features and reward
            feats = _extract_features_from_event(row)
            reward = _compute_reward(r_from_trade, row)

            try:
                bandit_update_from_trade(
                    selector_path=_safe_selector_path(),
                    symbol=str(symbol) if symbol else "UNKNOWN",
                    strategy_name=(
                        str(strat) if strat else ""
                    ),  # updater will ignore unknown keys safely
                    tech_snapshot=feats,
                    reward=reward,
                )
            except Exception:
                logger.debug(
                    "bandit_update_from_trade failed (symbol=%s strat=%s ticket=%s)",
                    symbol,
                    strat,
                    ticket,
                    exc_info=True,
                )
            return res

        return _inner

    # Patch methods if they exist
    if hasattr(journal_repo, "add_event"):
        journal_repo.add_event = _wrap(journal_repo.add_event)  # type: ignore
    if hasattr(journal_repo, "write_event"):
        journal_repo.write_event = _wrap(journal_repo.write_event)  # type: ignore

    # Not strictly needed on write_exec (opens), but harmless if someone logs r_multiple there
    if hasattr(journal_repo, "write_exec"):
        journal_repo.write_exec = _wrap(journal_repo.write_exec)  # type: ignore

    setattr(journal_repo, "_bandit_wired", True)
    logger.debug("Bandit autoupdate wired to journal_repo.")
