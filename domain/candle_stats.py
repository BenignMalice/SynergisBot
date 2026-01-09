# =====================================
# domain/candle_stats.py
# =====================================
from __future__ import annotations
from typing import Dict, Optional
import numpy as np
import pandas as pd


def _bbands(close: pd.Series, period: int = 20) -> Optional[tuple[float, float, float]]:
    if close is None or len(close) < period + 2:
        return None
    ma = close.rolling(period).mean()
    sd = close.rolling(period).std(ddof=0)
    upper = ma + 2 * sd
    lower = ma - 2 * sd
    u = float(upper.iloc[-1])
    l = float(lower.iloc[-1])
    m = float(ma.iloc[-1])
    return m, u, l


def _atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    if df is None or len(df) < period + 2:
        return None
    high = df["high"].astype(float).to_numpy()
    low = df["low"].astype(float).to_numpy()
    close = df["close"].astype(float).to_numpy()
    prev_close = close[:-1]
    tr1 = high[1:] - low[1:]
    tr2 = np.abs(high[1:] - prev_close)
    tr3 = np.abs(low[1:] - prev_close)
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    atr = np.zeros_like(close, dtype=float)
    n = period
    atr[:n] = np.nan
    # Wilder smoothing
    atr[n] = np.nanmean(tr[:n])
    for i in range(n + 1, len(close)):
        atr[i] = (atr[i - 1] * (n - 1) + tr[i - 1]) / n
    val = atr[-1]
    return float(val) if np.isfinite(val) else None


def calculate_wick_asymmetry(bar: Dict[str, float]) -> float:
    """
    Calculate wick asymmetry for a single bar.
    
    Metric: (upper_wick - lower_wick) / range
    
    Args:
        bar: Dict with 'open', 'high', 'low', 'close' keys
    
    Returns:
        float in range [-1, 1]
            > 0.5: Strong upper rejection (bearish)
            < -0.5: Strong lower rejection (bullish)
            ~0: Balanced wicks
    """
    try:
        o = bar.get("open", 0)
        h = bar.get("high", 0)
        l = bar.get("low", 0)
        c = bar.get("close", 0)
        
        if h == l:  # No range
            return 0.0
        
        # Calculate body bounds
        body_high = max(o, c)
        body_low = min(o, c)
        
        # Calculate wick sizes
        upper_wick = h - body_high
        lower_wick = body_low - l
        
        # Calculate range
        range_size = h - l
        
        # Asymmetry: positive = upper wick dominant, negative = lower wick dominant
        asymmetry = (upper_wick - lower_wick) / range_size if range_size > 0 else 0.0
        
        return max(-1.0, min(1.0, asymmetry))  # Clamp to [-1, 1]
        
    except Exception:
        return 0.0


def compute_candle_stats(
    df: pd.DataFrame, bb_period: int = 20, atr_period: int = 14
) -> Dict[str, float]:
    """Compute body/wick fractions, range, ATR multiple, and BB proximity on the last bar."""
    if df is None or df.empty:
        return {}
    o = float(df.iloc[-1]["open"] if "open" in df.columns else df.iloc[-1]["o"])
    h = float(df.iloc[-1]["high"] if "high" in df.columns else df.iloc[-1]["h"])
    l = float(df.iloc[-1]["low"] if "low" in df.columns else df.iloc[-1]["l"])
    c = float(df.iloc[-1]["close"] if "close" in df.columns else df.iloc[-1]["c"])
    rng = max(1e-9, h - l)
    body = abs(c - o)
    uw = h - max(o, c)
    lw = min(o, c) - l
    body_frac = float(body / rng)
    uw_frac = float(uw / rng)
    lw_frac = float(lw / rng)

    # ATR and spike
    atr = _atr(df, period=atr_period) or 0.0
    rng_atr_mult = float((rng / atr) if atr else 0.0)

    # Bollinger band proximity
    mlu = _bbands(df["close"].astype(float), period=bb_period)
    near_upper = near_lower = False
    bb_dist_upper_frac = bb_dist_lower_frac = None
    if mlu:
        m, u, lwbb = mlu
        # distances as fraction of band span (upper-lower); guard 0 division
        span = max(1e-9, (u - lwbb))
        bb_dist_upper_frac = float(abs(u - c) / span)
        bb_dist_lower_frac = float(abs(c - lwbb) / span)
        # 'near' thresholds to be decided by settings in caller
    return {
        "body_frac": body_frac,
        "uw_frac": uw_frac,
        "lw_frac": lw_frac,
        "rng": float(rng),
        "atr": float(atr or 0.0),
        "rng_atr_mult": rng_atr_mult,
        "bb_dist_upper_frac": (
            bb_dist_upper_frac if bb_dist_upper_frac is not None else 1.0
        ),
        "bb_dist_lower_frac": (
            bb_dist_lower_frac if bb_dist_lower_frac is not None else 1.0
        ),
    }
