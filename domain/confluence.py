# =====================================
# domain/confluence.py
# =====================================
from __future__ import annotations
from typing import Dict, Tuple


def _bool(x) -> bool:
    return bool(x) if x is not None else False


def _sgn(x: float) -> int:
    return 1 if x > 0 else (-1 if x < 0 else 0)


def _ema_align(price: float, ema200: float) -> int:
    if price is None or ema200 is None:
        return 0
    return 1 if price >= ema200 else -1


def _trend_ok(adx: float, thresh: float = 22.0) -> float:
    try:
        a = float(adx or 0.0)
        return max(0.0, min(1.0, (a - thresh) / (35.0 - thresh)))
    except Exception:
        return 0.0


def _slope_bias(slope: float, tol: float = 2e-4) -> int:
    try:
        s = float(slope or 0.0)
        if s > tol:
            return 1
        if s < -tol:
            return -1
        return 0
    except Exception:
        return 0


def compute_mtf_confluence(
    m5: Dict, m15: Dict, m30: Dict, h1: Dict
) -> Tuple[float, str, int]:
    """
    Returns (score 0..1, label, bias_sign +1/-1/0).
    Simple, robust MTF blend: EMA alignment & trendiness across TFs with H1 slope as tie-break.
    """
    # EMA alignment biases
    a5 = _ema_align(float(m5.get("close") or 0.0), float(m5.get("ema_200") or 0.0))
    a15 = _ema_align(float(m15.get("close") or 0.0), float(m15.get("ema_200") or 0.0))
    a30 = _ema_align(float(m30.get("close") or 0.0), float(m30.get("ema_200") or 0.0))
    a60 = _ema_align(float(h1.get("close") or 0.0), float(h1.get("ema_200") or 0.0))

    # ADX trend strength per TF
    t5 = _trend_ok(float(m5.get("adx_14") or m5.get("adx") or 0.0))
    t15 = _trend_ok(float(m15.get("adx_14") or m15.get("adx") or 0.0))
    t30 = _trend_ok(float(m30.get("adx_14") or m30.get("adx") or 0.0))
    t60 = _trend_ok(float(h1.get("adx_14") or h1.get("adx") or 0.0))

    # H1 EMA200 slope as higher-timeframe bias
    slope_bias = _slope_bias(
        float(h1.get("ema_200_slope") or h1.get("ema_slope") or 0.0)
    )

    # Aggregate direction votes
    votes = [a5, a15, a30, a60, slope_bias]
    bias = _sgn(sum(votes))

    # Strength is mix of directional agreement & trendiness
    agree = (
        (sum(1 for v in [a5, a15, a30, a60] if v == bias) / 4.0) if bias != 0 else 0.0
    )
    trend = max(t5, t15, t30) * 0.4 + t60 * 0.6
    score = max(0.0, min(1.0, 0.6 * agree + 0.4 * trend))

    if score >= 0.7:
        label = "STRONG_CONFLUENCE"
    elif score >= 0.45:
        label = "MODERATE_CONFLUENCE"
    elif score >= 0.25:
        label = "WEAK_CONFLUENCE"
    else:
        label = "NO_CONFLUENCE"

    return score, label, bias
