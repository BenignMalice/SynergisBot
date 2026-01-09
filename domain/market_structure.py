# =====================================
# domain/market_structure.py
# =====================================
"""
Market structure detection.

This module labels recent price structure (trending up/down or range),
and exposes helpers to label swing structure (HH/HL/LH/LL) and derive
a simple micro-structure bias. It’s robust to short inputs and missing
columns, and is designed to be fast for per-tick or per-minute use.

Public API:
    - label_structure(df: pd.DataFrame, lookback: int = 10) -> Dict[str, object]
    - label_swings(swings: List[PivotLike]) -> List[StructurePoint]
    - structure_bias(labels: List[StructurePoint], lookback: int = 6) -> Literal['up','down','range']

Anchors:
    # === ANCHOR: IMPORTS ===
    # === ANCHOR: TYPES ===
    # === ANCHOR: HELPERS_SWINGS ===
    # === ANCHOR: PUBLIC_API ===
"""

from __future__ import annotations

# === ANCHOR: IMPORTS ===
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Union

import numpy as np
import pandas as pd  # type: ignore

logger = logging.getLogger(__name__)

# === ANCHOR: TYPES ===
LabelKind = Literal["HH", "HL", "LH", "LL"]
PivotLike = Union[dict, Any]  # dict or object with .idx/.price/.kind


@dataclass
class StructurePoint:
    idx: int
    price: float
    kind: LabelKind  # HH/HL/LH/LL


# ------------------------------------------------------------
# === ANCHOR: HELPERS_SWINGS ===
# ------------------------------------------------------------
def _safe_array(series: pd.Series, dtype=float) -> np.ndarray:
    """Return a numpy array, replacing non-finite values with last valid then with overall fallback."""
    arr = np.asarray(series.to_numpy(copy=True), dtype=dtype)
    if arr.size == 0:
        return np.asarray([], dtype=dtype)
    # forward-fill NaNs
    for i in range(1, arr.size):
        if not np.isfinite(arr[i]):
            arr[i] = arr[i - 1]
    # backfill first if still nan
    if not np.isfinite(arr[0]):
        arr[0] = np.nanmean(arr) if np.isfinite(np.nanmean(arr)) else 0.0
    # final fallback
    arr[~np.isfinite(arr)] = 0.0
    return arr


def _coerce_epoch_seconds(ts_val: Any) -> int:
    """Best-effort convert timestamps (pd.Timestamp, numpy datetime64, ints) to epoch seconds; fallback 0."""
    try:
        if isinstance(ts_val, (int, np.integer)):
            return int(ts_val)
        if isinstance(ts_val, pd.Timestamp):
            return int(
                ts_val.tz_localize(
                    "UTC", nonexistent="shift_forward", ambiguous="NaT"
                ).timestamp()
                if ts_val.tzinfo is None
                else int(ts_val.timestamp())
            )
        # numpy datetime64 → pandas Timestamp
        if "datetime64" in str(type(ts_val)):
            return int(pd.Timestamp(ts_val).tz_localize("UTC").timestamp())
        # strings or other: let pandas try
        return int(pd.to_datetime(ts_val, utc=True, errors="coerce").timestamp())
    except Exception:
        return 0


def _find_pivots(df: pd.DataFrame, lookback: int = 10) -> Optional[Dict[str, float]]:
    """
    (Kept from your original, with safety tweaks.)
    Find recent pivot highs and lows in the last `lookback` bars of a
    DataFrame containing columns 'high' and 'low'. Returns a dict with:
      'last_high', 'prev_high', 'last_low', 'prev_low'
    """
    try:
        if (
            df is None
            or df.empty
            or ("high" not in df.columns)
            or ("low" not in df.columns)
        ):
            return None
        n = min(len(df), max(int(lookback), 5))
        highs = _safe_array(df["high"].iloc[-n:])
        lows = _safe_array(df["low"].iloc[-n:])
        if highs.size < 3 or lows.size < 3:
            return None

        pivot_highs: List[tuple[int, float]] = []
        pivot_lows: List[tuple[int, float]] = []
        # local extrema detection
        for i in range(1, n - 1):
            if highs[i] >= highs[i - 1] and highs[i] > highs[i + 1]:
                pivot_highs.append((i, float(highs[i])))
            if lows[i] <= lows[i - 1] and lows[i] < lows[i + 1]:
                pivot_lows.append((i, float(lows[i])))

        if not pivot_highs or not pivot_lows:
            return None

        last_high_idx, last_high_val = pivot_highs[-1]
        prev_high_idx, prev_high_val = (
            pivot_highs[-2] if len(pivot_highs) >= 2 else pivot_highs[-1]
        )
        last_low_idx, last_low_val = pivot_lows[-1]
        prev_low_idx, prev_low_val = (
            pivot_lows[-2] if len(pivot_lows) >= 2 else pivot_lows[-1]
        )

        return {
            "last_high": float(last_high_val),
            "prev_high": float(prev_high_val),
            "last_low": float(last_low_val),
            "prev_low": float(prev_low_val),
        }
    except Exception:
        logger.debug("_find_pivots failed", exc_info=True)
        return None


# ------------------------------------------------------------
# === ANCHOR: HELPERS_SWINGS ===
# ------------------------------------------------------------
def _symmetric_swings(
    df: pd.DataFrame,
    left: int = 3,
    right: int = 3,
    price_col_high: str = "high",
    price_col_low: str = "low",
    ts_col: str = "time",
    lookback: Optional[int] = None,
) -> List[dict]:
    """
    Robust symmetric swing detector (local maxima/minima with L/R windows).
    Returns a list of dicts [{idx, ts, price, kind}], sorted by idx.
    kind is 'H' for swing-high, 'L' for swing-low.
    """
    if (
        df is None
        or df.empty
        or price_col_high not in df.columns
        or price_col_low not in df.columns
    ):
        return []

    n = len(df)

    # --- Adaptive L/R for tiny samples ---
    L_req, R_req = int(left), int(right)
    if n < (L_req + R_req + 1) * 2:
        # For very small n, fall back to 1/1 which needs only 3-bars window
        L_req, R_req = 1, 1

    # Respect lookback but keep enough margin for the windows
    if lookback is None:
        start = 0
    else:
        start = max(0, n - int(lookback) - (L_req + R_req + 2))

    highs = _safe_array(df[price_col_high])
    lows = _safe_array(df[price_col_low])
    tss = df[ts_col].to_numpy() if ts_col in df.columns else np.arange(n)

    swings: List[dict] = []

    # Detect highs
    for i in range(start + L_req, n - R_req):
        window = highs[i - L_req : i + R_req + 1]
        if window.size < (L_req + R_req + 1):
            continue
        if highs[i] == np.max(window) and int(np.argmax(window)) == L_req:
            swings.append(
                {
                    "idx": i,
                    "ts": _coerce_epoch_seconds(tss[i]),
                    "price": float(highs[i]),
                    "kind": "H",
                }
            )

    # Detect lows
    for i in range(start + L_req, n - R_req):
        window = lows[i - L_req : i + R_req + 1]
        if window.size < (L_req + R_req + 1):
            continue
        if lows[i] == np.min(window) and int(np.argmin(window)) == L_req:
            swings.append(
                {
                    "idx": i,
                    "ts": _coerce_epoch_seconds(tss[i]),
                    "price": float(lows[i]),
                    "kind": "L",
                }
            )

    swings.sort(key=lambda s: s["idx"])
    return swings


def _get_field(obj: PivotLike, name: str, default: Any = None) -> Any:
    """Read `name` from dict or attribute; fall back to default."""
    try:
        if isinstance(obj, dict):
            return obj.get(name, default)
        val = getattr(obj, name, default)
        return val
    except Exception:
        return default


def label_swings(swings: List[PivotLike]) -> List[StructurePoint]:
    """
    Label a swing list as HH/HL/LH/LL. Compares each new high to the previous high,
    and each new low to the previous low. Returns a merged, idx-sorted label list.

    Accepts either dicts (with keys 'idx','price','kind' in {'H','L'}) or
    objects with attributes .idx, .price, .kind.
    """
    if not swings:
        return []

    highs = []
    lows = []
    for s in swings:
        k = str(_get_field(s, "kind", "")).upper()
        if k == "H":
            highs.append(
                {
                    "idx": int(_get_field(s, "idx", 0)),
                    "price": float(_get_field(s, "price", 0.0)),
                }
            )
        elif k == "L":
            lows.append(
                {
                    "idx": int(_get_field(s, "idx", 0)),
                    "price": float(_get_field(s, "price", 0.0)),
                }
            )

    labels: List[StructurePoint] = []

    last_h = None
    for h in highs:
        if last_h is None:
            last_h = h
            continue
        kind: LabelKind = "HH" if h["price"] > last_h["price"] else "LH"
        labels.append(StructurePoint(idx=h["idx"], price=h["price"], kind=kind))
        last_h = h

    last_l = None
    for l in lows:
        if last_l is None:
            last_l = l
            continue
        kind: LabelKind = "HL" if l["price"] > last_l["price"] else "LL"
        labels.append(StructurePoint(idx=l["idx"], price=l["price"], kind=kind))
        last_l = l

    labels.sort(key=lambda x: x.idx)
    return labels


def structure_bias(
    labels: List[StructurePoint], lookback: int = 6
) -> Literal["up", "down", "range"]:
    """
    Decide micro-structure bias:
        - 'up'   if last two highs are HH AND last two lows are HL
        - 'down' if last two highs are LH AND last two lows are LL
        - else 'range'
    """
    if not labels:
        return "range"

    L = labels[-max(1, int(lookback)) :]  # last N labels
    highs = [x for x in L if x.kind in ("HH", "LH")]
    lows = [x for x in L if x.kind in ("HL", "LL")]

    hh = [x for x in highs if x.kind == "HH"]
    lh = [x for x in highs if x.kind == "LH"]
    hl = [x for x in lows if x.kind == "HL"]
    ll = [x for x in lows if x.kind == "LL"]

    if len(hh) >= 2 and len(hl) >= 2:
        return "up"
    if len(lh) >= 2 and len(ll) >= 2:
        return "down"
    return "range"


# ------------------------------------------------------------
# === ANCHOR: PUBLIC_API ===
# ------------------------------------------------------------
def label_structure(
    df: Optional[pd.DataFrame],
    lookback: int = 10,
    pivots_mode: Literal["legacy", "symmetric"] = "symmetric",
) -> Dict[str, object]:
    """
    Analyse recent price swings to determine market structure.

    Returns a dict with:
      - trend: 'UP', 'DOWN' or 'RANGE'
      - break: True/False -> whether latest close has broken
               the last swing high (in uptrend) or low (in downtrend)
      - micro_bias: 'up'/'down'/'range' from HH/HL/LH/LL labels (extra)

    If data is insufficient, returns {'trend': 'UNKNOWN', 'break': False}.
    """
    try:
        if df is None or df.empty:
            return {"trend": "UNKNOWN", "break": False, "micro_bias": "range"}

        # Ensure required columns
        for col in ("high", "low", "close"):
            if col not in df.columns:
                return {"trend": "UNKNOWN", "break": False, "micro_bias": "range"}

        # 1) Pivots for coarse trend
        if pivots_mode == "legacy":
            piv = _find_pivots(df, lookback)
            if not piv:
                return {"trend": "RANGE", "break": False, "micro_bias": "range"}
            lh = float(piv["last_high"])
            ph = float(piv["prev_high"])
            ll = float(piv["last_low"])
            pl = float(piv["prev_low"])

            if lh > ph and ll > pl:
                trend = "UP"
            elif lh < ph and ll < pl:
                trend = "DOWN"
            else:
                trend = "RANGE"
        else:
            # symmetric mode uses more robust windowed swings
            swings = _symmetric_swings(df, left=3, right=3, lookback=max(lookback, 20))
            highs = [s for s in swings if s["kind"] == "H"]
            lows = [s for s in swings if s["kind"] == "L"]

            if len(highs) >= 2 and len(lows) >= 2:
                lh, ph = highs[-1]["price"], highs[-2]["price"]
                ll, pl = lows[-1]["price"], lows[-2]["price"]
                if lh > ph and ll > pl:
                    trend = "UP"
                elif lh < ph and ll < pl:
                    trend = "DOWN"
                else:
                    trend = "RANGE"
            else:
                # Fallback: try legacy pivots on short or choppy samples
                piv = _find_pivots(df, lookback)
                if piv:
                    lh = float(piv["last_high"])
                    ph = float(piv["prev_high"])
                    ll = float(piv["last_low"])
                    pl = float(piv["prev_low"])
                    if lh > ph and ll > pl:
                        trend = "UP"
                    elif lh < ph and ll < pl:
                        trend = "DOWN"
                    else:
                        trend = "RANGE"
                else:
                    trend = "RANGE"

        # 2) Break condition vs last pivot high/low
        close = float(_safe_array(df["close"])[-1])  # last close
        brk = False
        if pivots_mode == "legacy":
            if trend == "UP" and close > lh:
                brk = True
            if trend == "DOWN" and close < ll:
                brk = True
        else:
            # In symmetric mode recompute last/prev for break check when available
            if len(highs) >= 1 and len(lows) >= 1:
                last_high = highs[-1]["price"]
                last_low = lows[-1]["price"]
                if trend == "UP" and close > last_high:
                    brk = True
                if trend == "DOWN" and close < last_low:
                    brk = True

        # 3) Micro-structure bias from HH/HL/LH/LL
        if pivots_mode == "legacy":
            swings = _symmetric_swings(df, left=3, right=3, lookback=max(lookback, 20))
        labels = label_swings(swings) if swings else []
        micro = structure_bias(labels, lookback=6)

        return {"trend": trend, "break": brk, "micro_bias": micro}
    except Exception:
        logger.debug("label_structure failed", exc_info=True)
        return {"trend": "UNKNOWN", "break": False, "micro_bias": "range"}


def detect_bos_choch(
    swings: List[Dict[str, Any]],
    current_close: float,
    atr: float,
    bos_threshold: float = 0.2,
    sustained_bars: int = 1
) -> Dict[str, Any]:
    """
    Detect Break of Structure (BOS) and Change of Character (CHOCH).
    
    BOS: Close beyond last swing by ≥bos_threshold×ATR, sustained ≥sustained_bars
    CHOCH: BOS that reverses prior swing sequence (LL → HH or HH → LL)
    
    Args:
        swings: List of swing dicts with keys: price, kind (HH/HL/LH/LL), idx
        current_close: Current close price
        atr: Average True Range for normalization
        bos_threshold: Minimum break distance as multiple of ATR
        sustained_bars: Minimum bars to sustain break
    
    Returns:
        {
            "bos_bull": bool,
            "bos_bear": bool,
            "choch_bull": bool,
            "choch_bear": bool,
            "bars_since_bos": int,
            "break_level": float
        }
    """
    try:
        if not swings or len(swings) < 2 or atr <= 0:
            return _empty_bos_choch()
        
        # Get last few swings to analyze
        recent_swings = swings[-5:] if len(swings) >= 5 else swings
        
        # Find last significant swing high and low
        swing_highs = [s for s in recent_swings if s.get("kind") in ["HH", "LH"]]
        swing_lows = [s for s in recent_swings if s.get("kind") in ["HL", "LL"]]
        
        if not swing_highs or not swing_lows:
            return _empty_bos_choch()
        
        last_swing_high = max(swing_highs, key=lambda s: s.get("price", 0))
        last_swing_low = min(swing_lows, key=lambda s: s.get("price", float("inf")))
        
        # Check for bullish BOS (break above last swing high)
        bos_bull = False
        choch_bull = False
        bull_break_level = 0.0
        
        break_distance_bull = current_close - last_swing_high["price"]
        if break_distance_bull >= bos_threshold * atr:
            bos_bull = True
            bull_break_level = last_swing_high["price"]
            
            # Check for CHOCH (reversal of structure)
            # If prior swings were making lower highs (downtrend), this is CHOCH
            if len(recent_swings) >= 3:
                prev_structure = _analyze_swing_structure(recent_swings[:-1])
                if prev_structure == "down":
                    choch_bull = True
        
        # Check for bearish BOS (break below last swing low)
        bos_bear = False
        choch_bear = False
        bear_break_level = 0.0
        
        break_distance_bear = last_swing_low["price"] - current_close
        if break_distance_bear >= bos_threshold * atr:
            bos_bear = True
            bear_break_level = last_swing_low["price"]
            
            # Check for CHOCH (reversal of structure)
            # If prior swings were making higher lows (uptrend), this is CHOCH
            if len(recent_swings) >= 3:
                prev_structure = _analyze_swing_structure(recent_swings[:-1])
                if prev_structure == "up":
                    choch_bear = True
        
        # Calculate bars since BOS (approximate - would need bar index tracking)
        bars_since = 0 if (bos_bull or bos_bear) else -1
        
        return {
            "bos_bull": bos_bull,
            "bos_bear": bos_bear,
            "choch_bull": choch_bull,
            "choch_bear": choch_bear,
            "bars_since_bos": bars_since,
            "break_level": bull_break_level if bos_bull else bear_break_level
        }
        
    except Exception as e:
        logger.debug(f"BOS/CHOCH detection failed: {e}")
        return _empty_bos_choch()


def _analyze_swing_structure(swings: List[Dict[str, Any]]) -> str:
    """
    Analyze swing structure to determine trend direction.
    
    Returns: "up" (higher lows), "down" (lower highs), or "mixed"
    """
    if len(swings) < 2:
        return "mixed"
    
    # Check for higher lows (uptrend)
    lows = [s for s in swings if s.get("kind") in ["HL", "LL"]]
    if len(lows) >= 2:
        is_higher_lows = all(
            lows[i]["price"] > lows[i-1]["price"] 
            for i in range(1, len(lows))
        )
        if is_higher_lows:
            return "up"
    
    # Check for lower highs (downtrend)
    highs = [s for s in swings if s.get("kind") in ["HH", "LH"]]
    if len(highs) >= 2:
        is_lower_highs = all(
            highs[i]["price"] < highs[i-1]["price"]
            for i in range(1, len(highs))
        )
        if is_lower_highs:
            return "down"
    
    return "mixed"


def _empty_bos_choch() -> Dict[str, Any]:
    """Return empty BOS/CHOCH result."""
    return {
        "bos_bull": False,
        "bos_bear": False,
        "choch_bull": False,
        "choch_bear": False,
        "bars_since_bos": -1,
        "break_level": 0.0
    }


__all__ = [
    "StructurePoint",
    "label_swings",
    "structure_bias",
    "label_structure",
    "detect_bos_choch",
]
