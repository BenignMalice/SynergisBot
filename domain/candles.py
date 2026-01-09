# =====================================
# domain/candles.py
# =====================================
from __future__ import annotations
from typing import Dict, Tuple
import numpy as np


def _body_wick(o: float, h: float, l: float, c: float):
    body = abs(c - o)
    rng = max(1e-9, h - l)
    up_wick = h - max(o, c)
    lo_wick = min(o, c) - l
    return body, up_wick, lo_wick, rng


def _bar(df, idx: int) -> Dict[str, float]:
    return {
        "o": float(df["open"].iloc[idx]),
        "h": float(df["high"].iloc[idx]),
        "l": float(df["low"].iloc[idx]),
        "c": float(df["close"].iloc[idx]),
    }


def is_bullish_engulf(prev, cur) -> bool:
    return (
        (cur["c"] > cur["o"])
        and (prev["c"] < prev["o"])
        and (cur["c"] >= prev["o"])
        and (cur["o"] <= prev["c"])
    )


def is_bearish_engulf(prev, cur) -> bool:
    return (
        (cur["c"] < cur["o"])
        and (prev["c"] > prev["o"])
        and (cur["o"] >= prev["c"])
        and (cur["c"] <= prev["o"])
    )


def is_inside(prev, cur) -> bool:
    return (cur["h"] <= prev["h"]) and (cur["l"] >= prev["l"])


def is_pin_bar(
    bar, side: str, min_ratio: float = 0.6, max_body_frac: float = 0.35
) -> bool:
    body, up, lo, rng = _body_wick(bar["o"], bar["h"], bar["l"], bar["c"])
    if rng == 0:
        return False
    body_ok = (body / rng) <= max_body_frac
    if side == "bull":
        return body_ok and (lo / rng) >= min_ratio
    else:
        return body_ok and (up / rng) >= min_ratio


def is_shooting_star(
    bar, min_up_wick: float = 0.6, max_body_frac: float = 0.35
) -> bool:
    body, up, lo, rng = _body_wick(bar["o"], bar["h"], bar["l"], bar["c"])
    if rng == 0:
        return False
    return (
        (up / rng) >= min_up_wick
        and (body / rng) <= max_body_frac
        and (lo / rng) <= 0.15
    )


def is_hammer(bar, min_lo_wick: float = 0.6, max_body_frac: float = 0.35) -> bool:
    body, up, lo, rng = _body_wick(bar["o"], bar["h"], bar["l"], bar["c"])
    if rng == 0:
        return False
    return (
        (lo / rng) >= min_lo_wick
        and (body / rng) <= max_body_frac
        and (up / rng) <= 0.15
    )


def is_marubozu(bar, min_body_frac: float = 0.75) -> int:
    """Return +1 for bullish marubozu, -1 for bearish, 0 otherwise."""
    body, up, lo, rng = _body_wick(bar["o"], bar["h"], bar["l"], bar["c"])
    if rng == 0:
        return 0
    if (body / rng) >= min_body_frac:
        return 1 if bar["c"] > bar["o"] else -1
    return 0


def detect_recent_patterns(df) -> Tuple[str, int]:
    """
    Detect notable candlestick patterns on the latest bars of `df`.

    Returns a tuple of (pattern_name, bias) where `bias` is +1 for bullish, -1 for
    bearish and 0 when neutral.  Recognition is performed on up to the last three
    bars and includes classic two‑ and three‑bar reversals.  Patterns include:

      • BULL_ENGULF / BEAR_ENGULF: strong reversal engulfings
      • MORNING_STAR / EVENING_STAR: three‑bar reversal stars
      • THREE_WHITE_SOLDIERS / THREE_BLACK_CROWS: three consecutive strong
        continuation candles
      • TWEEZER_TOP / TWEEZER_BOTTOM: equal highs/lows indicating potential reversals
      • INSIDE: an inside bar (neutral)
      • SHOOTING_STAR / HAMMER: single bar patterns
      • BULL_MARUBOZU / BEAR_MARUBOZU: full‑body marubozu bars
      • BULL_PIN / BEAR_PIN: fallback pin bars

    If no pattern is recognised, returns ("", 0).
    """
    if df is None or len(df) < 2:
        return "", 0

    # Helper to classify a bar as bullish or bearish with body fraction
    def _is_bull(bar):
        return bar["c"] > bar["o"]

    def _is_bear(bar):
        return bar["c"] < bar["o"]

    # Access last three bars if available
    bars = []
    n = len(df)
    for idx in range(max(0, n - 3), n):
        bars.append(_bar(df, idx - n))  # negative index from end

    # When we have three bars, attempt multi‑bar patterns first
    if len(bars) >= 3:
        b1, b2, b3 = bars[-3], bars[-2], bars[-1]
        # Identify range sizes to normalise thresholds
        rng1 = max(1e-9, b1["h"] - b1["l"])
        rng2 = max(1e-9, b2["h"] - b2["l"])
        rng3 = max(1e-9, b3["h"] - b3["l"])

        # Morning Star: first bar bearish with large body, second small candle
        # (bullish or bearish), third bullish closing above midpoint of b1.
        body1 = abs(b1["c"] - b1["o"]) / rng1
        body2 = abs(b2["c"] - b2["o"]) / rng2
        body3 = abs(b3["c"] - b3["o"]) / rng3
        midpoint1 = (b1["c"] + b1["o"]) / 2.0
        if (
            _is_bear(b1)
            and body1 >= 0.4
            and body2 <= 0.3
            and _is_bull(b3)
            and b3["c"] > midpoint1
        ):
            return "MORNING_STAR", +1
        # Evening Star: first bar bullish, second small, third bearish closing below midpoint
        if (
            _is_bull(b1)
            and body1 >= 0.4
            and body2 <= 0.3
            and _is_bear(b3)
            and b3["c"] < midpoint1
        ):
            return "EVENING_STAR", -1
        # Three White Soldiers: three bullish candles with consecutive higher closes and opens
        if (
            _is_bull(b1)
            and _is_bull(b2)
            and _is_bull(b3)
            and b2["c"] > b1["c"]
            and b3["c"] > b2["c"]
            and b1["o"] < b2["o"] < b3["o"]
        ):
            return "THREE_WHITE_SOLDIERS", +1
        # Three Black Crows: three bearish candles with consecutive lower closes and opens
        if (
            _is_bear(b1)
            and _is_bear(b2)
            and _is_bear(b3)
            and b2["c"] < b1["c"]
            and b3["c"] < b2["c"]
            and b1["o"] > b2["o"] > b3["o"]
        ):
            return "THREE_BLACK_CROWS", -1

        # Tweezer top: last two bars have very similar highs and second bar bearish
        if (
            abs(b2["h"] - b3["h"]) <= 0.1 * ((b2["h"] + b3["h"]) / 2.0)
            and _is_bull(b2)
            and _is_bear(b3)
        ):
            return "TWEEZER_TOP", -1
        # Tweezer bottom: last two bars have similar lows and second bar bullish
        if (
            abs(b2["l"] - b3["l"]) <= 0.1 * ((b2["l"] + b3["l"]) / 2.0)
            and _is_bear(b2)
            and _is_bull(b3)
        ):
            return "TWEEZER_BOTTOM", +1

    # Fallback to two‑bar and single‑bar patterns
    prev = _bar(df, -2)
    cur = _bar(df, -1)

    if is_bullish_engulf(prev, cur):
        return "BULL_ENGULF", +1
    if is_bearish_engulf(prev, cur):
        return "BEAR_ENGULF", -1
    if is_inside(prev, cur):
        return "INSIDE", 0

    if is_shooting_star(cur):
        return "SHOOTING_STAR", -1
    if is_hammer(cur):
        return "HAMMER", +1

    m = is_marubozu(cur)
    if m == +1:
        return "BULL_MARUBOZU", +1
    if m == -1:
        return "BEAR_MARUBOZU", -1

    # Pin bars as a fallback classification
    if is_pin_bar(cur, "bull"):
        return "BULL_PIN", +1
    if is_pin_bar(cur, "bear"):
        return "BEAR_PIN", -1

    return "", 0


# --- Phase1 convenience helpers (non-invasive) ---
def wick_strength_ratio(bar: Dict[str, float]) -> Dict[str, float]:
    """Return up/down wick vs body ratios for a bar with keys o,h,l,c."""
    body, up, lo, rng = _body_wick(bar.get("o",0.0), bar.get("h",0.0), bar.get("l",0.0), bar.get("c",0.0))
    return {
        "body": float(body),
        "range": float(rng),
        "up_wick": float(up),
        "lo_wick": float(lo),
        "up_over_body": float(up / max(1e-9, body)),
        "lo_over_body": float(lo / max(1e-9, body)),
        "up_over_range": float(up / max(1e-9, rng)),
        "lo_over_range": float(lo / max(1e-9, rng)),
    }
