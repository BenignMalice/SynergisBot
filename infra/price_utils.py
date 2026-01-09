# File: infra/price_utils.py
# --------------------------
from __future__ import annotations
import MetaTrader5 as mt5
from dataclasses import dataclass
from typing import Tuple


@dataclass
class SymbolMeta:
    symbol: str
    digits: int
    point: float
    tick_size: float
    stops_level_pts: int


def get_symbol_meta(symbol: str) -> SymbolMeta:
    si = mt5.symbol_info(symbol)
    if not si:
        raise RuntimeError(f"Symbol not found or not visible: {symbol}")
    return SymbolMeta(
        symbol=symbol,
        digits=si.digits,
        point=si.point,
        tick_size=(si.trade_tick_size or si.point),
        stops_level_pts=(si.trade_stops_level or 0),
    )


def round_to_tick(price: float, tick: float) -> float:
    # robust tick rounding
    return round(round(price / tick) * tick, 10)


def fmt_price(symbol: str, price: float) -> str:
    meta = get_symbol_meta(symbol)
    return f"{price:.{meta.digits}f}"


def ensure_min_distance(
    symbol: str, entry: float, sl: float | None, tp: float | None
) -> Tuple[float | None, float | None]:
    """
    Make sure SL/TP respect broker stops level and don't collapse to entry due to rounding.
    """
    meta = get_symbol_meta(symbol)
    min_dist = max(meta.stops_level_pts, 1) * meta.point  # at least 1 point

    def _fix(target: float | None, is_tp: bool) -> float | None:
        if target is None:
            return None
        if abs(target - entry) < min_dist:
            # nudge away from entry by 2×min_dist to be safe
            target = entry + (2 * min_dist if is_tp else -2 * min_dist)
        return round_to_tick(target, meta.tick_size)

    sl = _fix(sl, is_tp=False)
    tp = _fix(tp, is_tp=True)
    return sl, tp


# --- Phase1 Risk/Reward helpers (non-invasive; safe to import anywhere) ---
def _clamp(v: float, lo: float, hi: float) -> float:
    try:
        if lo > hi:
            lo, hi = hi, lo
        return max(lo, min(hi, v))
    except Exception:
        return v

def calc_R(entry: float, sl: float, px: float) -> float:
    """Return progress in R units at price px, given entry and SL."""
    risk = abs(entry - sl)
    if risk <= 0:
        return 0.0
    return (px - entry) / risk if entry is not None and sl is not None else 0.0

def rr_from_targets(entry: float, sl: float, tp: float) -> float:
    """Return RR given entry, SL, TP (sanity-checks sign)."""
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    return round(reward / risk, 2) if risk > 0 else 0.0

def progress_reached(px: float, entry: float, sl: float, target_R: float) -> bool:
    """True if price has progressed to >= target_R (handles long/short)."""
    risk = entry - sl
    if risk == 0:
        return False
    # Long if entry > sl; Short if entry < sl
    is_long = entry > sl
    progress = (px - entry) / abs(risk)
    return (progress >= target_R) if is_long else (-progress >= target_R)
