# =====================================
# domain/breakout_quality.py
# =====================================
from __future__ import annotations

import logging
from typing import Literal, Optional

import numpy as np
import pandas as pd

from .zones import Zone

logger = logging.getLogger(__name__)


def _atr_like(df: pd.DataFrame) -> np.ndarray:
    if "atr" in df.columns:
        return df["atr"].to_numpy(dtype=float)
    if "ATR" in df.columns:
        return df["ATR"].to_numpy(dtype=float)
    # fallback Wilder(14)
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    prev_c = np.roll(c, 1)
    prev_c[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    n = 14
    out = tr.copy()
    for i in range(1, len(tr)):
        out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


def assess_breakout(
    df: pd.DataFrame,
    zone: Zone,
    idx: int,
    next_bars: int = 2,
    min_body_to_atr: float = 0.6,
    min_close_beyond_atr: float = 0.2,
) -> Literal["good", "weak", "failure"]:
    """
    Classify the breakout quality of bar at idx relative to zone.
    - 'good': strong body vs ATR + close holds beyond zone; optional follow-through
    - 'weak': crossed but small body or marginal close
    - 'failure': closes back inside opposite side within next_bars
    """
    n = len(df)
    if idx <= 0 or idx >= n:
        return "weak"

    o = float(
        df["open"].iloc[idx] if "open" in df.columns else df["close"].iloc[idx - 1]
    )
    c = float(df["close"].iloc[idx])
    h = float(df["high"].iloc[idx])
    l = float(df["low"].iloc[idx])

    atr = _atr_like(df)
    atr_i = float(atr[idx]) if idx < len(atr) else max(1e-9, np.nanmean(atr))

    body = abs(c - o)
    body_to_atr = body / max(atr_i, 1e-9)

    # Direction check (bullish vs bearish breakout)
    bullish_cross = (c > zone.level) and (o <= zone.level)
    bearish_cross = (c < zone.level) and (o >= zone.level)

    if not bullish_cross and not bearish_cross:
        # Could be gap or wick cross; treat as weak unless follow-through proves otherwise
        cross_dir = "bullish" if c > zone.level else "bearish"
    else:
        cross_dir = "bullish" if bullish_cross else "bearish"

    # Distance of close beyond zone in ATRs
    dist_beyond = (c - zone.level) / max(atr_i, 1e-9)
    if cross_dir == "bearish":
        dist_beyond = (zone.level - c) / max(atr_i, 1e-9)

    # Immediate failure check: next bars flip back inside
    end = min(n, idx + 1 + max(1, next_bars))
    nxt_closes = df["close"].iloc[idx + 1 : end].to_numpy(dtype=float)
    if cross_dir == "bullish":
        if np.any(nxt_closes <= zone.level):
            return "failure"
    else:
        if np.any(nxt_closes >= zone.level):
            return "failure"

    # Score quality
    if body_to_atr >= min_body_to_atr and dist_beyond >= min_close_beyond_atr:
        return "good"
    # Crossed but didn’t meet strength thresholds
    return "weak"


def latest_breakout_quality(
    df: pd.DataFrame,
    zone: Zone,
    lookback: int = 20,
    **kw,
) -> Optional[Literal["good", "weak", "failure"]]:
    """
    Find the most recent bar within lookback that interacts with zone and assess.
    """
    n = len(df)
    if n == 0:
        return None
    start = max(1, n - int(lookback))
    # Choose the latest bar whose high/low crosses the zone
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    idxs = [i for i in range(start, n) if (low[i] <= zone.level <= high[i])]
    if not idxs:
        return None
    return assess_breakout(df, zone, idx=idxs[-1], **kw)


__all__ = ["assess_breakout", "latest_breakout_quality"]
