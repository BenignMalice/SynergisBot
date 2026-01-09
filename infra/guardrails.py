"""
Guardrails functions for trade risk management.

This module exposes a set of functions that perform checks before a
trade is executed.  Each function returns a tuple `(ok, reason)`
indicating whether the check passed and, if not, a reason for the
block.  The functions are intended to be called by the LLM critic or
execution code to enforce hard rules rather than subjective
judgements.

Available functions:

 - `risk_ok(plan, account_state)`: Ensure the trade risk fits within
   account constraints (placeholder implementation, always True).
 - `exposure_ok(plan)`: Use the existing `ExposureGuard` to avoid
   correlated exposures.
 - `news_ok(symbol, ts)`: Check whether the symbol is currently
   under a news blackout period using `NewsService`.
 - `slippage_ok(symbol)`: Check whether current spread/ATR is below
   a maximum ratio.

These functions are designed to be called from the critic step of
planner → critic → executor pipeline.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple
from infra.exposure_guard import ExposureGuard
import MetaTrader5 as mt5  # type: ignore

import pandas as pd  # type: ignore

from config import settings
from infra.exposure_guard import ExposureGuard
from infra.news_service import NewsService
from infra.mt5_service import MT5Service

logger = logging.getLogger(__name__)


def risk_ok(
    plan: Dict[str, Any], account_state: Dict[str, Any] | None = None
) -> Tuple[bool, str]:
    """Check if the proposed trade risk is within acceptable bounds.

    Currently this is a stub that always returns True.  In future
    implementations, it could look at `plan['confidence']`, account
    equity, margin usage and maximum risk per trade/day.
    """
    try:
        return True, ""
    except Exception:
        logger.debug("risk_ok check failed", exc_info=True)
        return True, ""


def exposure_ok(plan_or_dict: Any) -> Tuple[bool, str]:
    """
    Accepts a dict like:
      {
        "symbol": "XAUUSDc",
        "direction": "BUY"/"SELL"/"HOLD",
        "risk_pct": <optional float>,
        "desired_risk_pct": <optional float>,   # accepted alias
        "journal_repo": <optional repo>
      }

    Returns (ok, reason). Uses ExposureGuard.evaluate(...).
    Fails open (True, "error:<Type>") on any error.

    NOTE: On success we return (True, "ok"). Callers typically only use the
    reason string when ok=False, and they add the "exposure_guard:" prefix
    themselves when building UI guard messages.
    """
    try:
        if not isinstance(plan_or_dict, dict):
            return True, "noop"

        symbol = str(plan_or_dict.get("symbol") or "").strip()
        direction = str(plan_or_dict.get("direction") or "").upper().strip()

        # Prefer 'risk_pct', fall back to 'desired_risk_pct', default 1.0
        desired_risk_pct = float(
            plan_or_dict.get("risk_pct") or plan_or_dict.get("desired_risk_pct") or 1.0
        )
        journal_repo = plan_or_dict.get("journal_repo")

        # If we don't have a clear trade side, don't block.
        if direction not in ("BUY", "SELL") or not symbol:
            return True, "no-direction"

        eg = ExposureGuard(journal_repo=journal_repo)
        res = eg.evaluate(
            symbol=symbol,
            side=direction,
            desired_risk_pct=desired_risk_pct,
            journal_repo=journal_repo,
        )

        # Caller only cares about the reason when res.allow == False.
        return (res.allow, res.reason if not res.allow else "ok")

    except Exception as e:
        # Fail-open to avoid hard stops if guard can’t run
        return True, f"error:{e.__class__.__name__}"


def news_ok(symbol: str, ts: int) -> Tuple[bool, str]:
    """Check if high-impact news is within blackout window for symbol."""
    try:
        ns = NewsService()
        category = "crypto" if "BTC" in symbol or "ETH" in symbol else "macro"
        if ns.is_blackout(category=category):
            return False, "news_blackout"
        return True, ""
    except Exception:
        logger.debug("news_ok check failed", exc_info=True)
        return True, ""


def slippage_ok(symbol: str) -> Tuple[bool, str]:
    """Check whether spread/ATR ratio is within acceptable bounds."""
    try:
        info = mt5.symbol_info(symbol)
        if not info:
            return True, ""
        spread = float(info.spread)
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 200)
        if rates is None or len(rates) < 20:
            return True, ""
        import numpy as np

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        prev_close = np.roll(close, 1)
        tr = np.maximum(
            high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close))
        )
        tr[0] = high[0] - low[0]
        atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().iloc[-1]
        if atr <= 0:
            return True, ""
        ratio = spread / atr
        max_ratio = float(getattr(settings, "MAX_SPREAD_PCT_ATR", 0.2))
        if ratio > max_ratio:
            return False, f"spread_ratio_{ratio:.2f}_exceeds_{max_ratio}"
        return True, ""
    except Exception:
        logger.debug("slippage_ok check failed", exc_info=True)
        return True, ""
