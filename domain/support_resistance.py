# =====================================
# File: domain/support_resistance.py (NEW)
# =====================================
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any
import numpy as np
import pandas as pd


@dataclass
class SRZone:
    kind: str  # "support" | "resistance"
    level: float  # representative mid level
    low: float  # zone low bound
    high: float  # zone high bound
    touches: int  # number of swing touches within zone
    last_touch_idx: int  # df index position of last touch
    strength: float  # heuristic score 0..1


def _pivots(df: pd.DataFrame, left: int, right: int) -> Tuple[np.ndarray, np.ndarray]:
    H, L = df["high"].values, df["low"].values
    n = len(df)
    highs, lows = [], []
    for i in range(left, n - right):
        window_h = H[i - left : i + right + 1]
        window_l = L[i - left : i + right + 1]
        if H[i] == window_h.max():
            highs.append(i)
        if L[i] == window_l.min():
            lows.append(i)
    return np.array(highs, dtype=int), np.array(lows, dtype=int)


def _cluster_levels(level_prices: np.ndarray, tol: float) -> List[List[float]]:
    if len(level_prices) == 0:
        return []
    xs = np.sort(level_prices)
    clusters: List[List[float]] = [[xs[0]]]
    for p in xs[1:]:
        if abs(p - clusters[-1][-1]) <= tol:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    return clusters


def detect_sr_zones(
    df: pd.DataFrame,
    atr: np.ndarray,
    left: int = 3,
    right: int = 3,
    zone_atr_width: float = 0.6,
    level_merge_tol_atr: float = 0.5,
    zone_min_touches: int = 3,
) -> List[SRZone]:
    """Build S/R zones by clustering swing highs/lows with ATR-scaled tolerance."""
    n = len(df)
    if n == 0:
        return []
    highs_idx, lows_idx = _pivots(df, left, right)
    atr_now = float(atr[-1]) if len(atr) else max(1e-6, float(df["high"].std()))
    tol = max(1e-6, atr_now * level_merge_tol_atr)

    high_levels = df["high"].values[highs_idx]
    low_levels = df["low"].values[lows_idx]

    high_clusters = _cluster_levels(high_levels, tol)
    low_clusters = _cluster_levels(low_levels, tol)

    zones: List[SRZone] = []
    half = max(1e-6, atr_now * zone_atr_width)

    def _mk_zone(kind: str, cluster: List[float]) -> SRZone:
        level = float(np.median(cluster))
        low, high = level - half, level + half
        # touch stats
        if kind == "resistance":
            idxs = highs_idx[np.isin(high_levels, cluster)]
        else:
            idxs = lows_idx[np.isin(low_levels, cluster)]
        touches = int(len(cluster))
        last_touch_idx = int(idxs.max()) if len(idxs) else 0
        # recency weighting
        recency = 1.0 - (n - 1 - last_touch_idx) / max(1, n)
        strength = min(1.0, 0.5 * (touches / max(1, zone_min_touches)) + 0.5 * recency)
        return SRZone(kind, level, low, high, touches, last_touch_idx, strength)

    for c in high_clusters:
        if len(c) >= zone_min_touches:
            zones.append(_mk_zone("resistance", c))
    for c in low_clusters:
        if len(c) >= zone_min_touches:
            zones.append(_mk_zone("support", c))

    # sort by strength desc
    zones.sort(key=lambda z: z.strength, reverse=True)
    return zones


def summarize_zones(zones: List[SRZone], price: float, limit: int = 6) -> str:
    out = []
    for z in zones[:limit]:
        dist = abs(price - z.level)
        out.append(
            f"{z.kind[:1].upper()}@{z.level:.2f} (±{(z.high - z.low)/2:.2f}), t={z.touches}, s={z.strength:.2f}, d={dist:.2f}"
        )
    return " | ".join(out) if out else "none"
