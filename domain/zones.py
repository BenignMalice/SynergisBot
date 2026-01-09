# =====================================
# domain/zones.py
# =====================================
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple, Literal

import numpy as np
import pandas as pd

try:
    # Your project style: centralised settings (safe if missing)
    from config import settings  # type: ignore
except Exception:  # pragma: no cover

    class _Fallback:
        PRICE_TOL_BPS: int = 15  # clustering width in basis points
        ZONE_MAX_AGE_BARS: int = 600  # recency half-life scale
        ZONE_SCORE_WEIGHTS = {
            "touches": 0.45,
            "recency": 0.30,
            "reaction": 0.25,
        }

    settings = _Fallback()  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class Pivot:
    idx: int
    ts: int
    price: float
    kind: Literal["H", "L"]  # High/Low pivot
    reaction_ret: float = 0.0  # forward return after pivot (rough “reaction” strength)


@dataclass
class Zone:
    level: float  # center price of the cluster
    span: float  # half-width of the zone
    touches: int  # how many pivots clustered here
    score: float  # composite score (touches, recency, reaction)
    last_touch_idx: int  # last bar index that touched this zone
    last_reaction_ret: float
    kind: Literal["H", "L", "M"]  # mainly H-cluster, L-cluster, or Mixed
    # Optional metadata
    first_touch_idx: Optional[int] = None


def _basis_points(price: float, bps: float) -> float:
    return abs(price) * (bps / 10_000.0)


def find_swings(
    df: pd.DataFrame,
    left: int = 3,
    right: int = 3,
    price_col_high: str = "high",
    price_col_low: str = "low",
    ts_col: str = "time",
    lookback: Optional[int] = None,
) -> List[Pivot]:
    """
    Symmetric pivot detection (local maxima/minima) on highs/lows.
    Returns Pivot list sorted by idx.
    """
    n = len(df)
    if n == 0:
        return []

    start = 0 if lookback is None else max(0, n - int(lookback) - (left + right + 2))
    highs = df[price_col_high].to_numpy()
    lows = df[price_col_low].to_numpy()
    tss = df[ts_col].to_numpy() if ts_col in df.columns else np.arange(n)

    pivots: List[Pivot] = []
    L = int(left)
    R = int(right)

    # Detect highs
    for i in range(start + L, n - R):
        window = highs[i - L : i + R + 1]
        if len(window) < (L + R + 1):
            continue
        if highs[i] == np.max(window) and np.argmax(window) == L:
            pivots.append(Pivot(idx=i, ts=int(tss[i]), price=float(highs[i]), kind="H"))

    # Detect lows
    for i in range(start + L, n - R):
        window = lows[i - L : i + R + 1]
        if len(window) < (L + R + 1):
            continue
        if lows[i] == np.min(window) and np.argmin(window) == L:
            pivots.append(Pivot(idx=i, ts=int(tss[i]), price=float(lows[i]), kind="L"))

    pivots.sort(key=lambda p: p.idx)

    # Estimate simple forward “reaction” after each pivot: look ahead k bars’ best return
    k = 5
    closes = df.get(
        "close", df.get("Close", df.get("CLOSE", pd.Series(highs)))
    ).to_numpy()
    for pv in pivots:
        j1 = min(n - 1, pv.idx + 1)
        j2 = min(n, pv.idx + 1 + k)
        if pv.kind == "H":
            # reaction = drop from pivot to min of next k
            if j1 < j2:
                mn = float(np.min(closes[j1:j2]))
                pv.reaction_ret = (mn - pv.price) / pv.price
        else:
            if j1 < j2:
                mx = float(np.max(closes[j1:j2]))
                pv.reaction_ret = (mx - pv.price) / pv.price

    return pivots


def cluster_levels(
    pivots: List[Pivot],
    price_tol_bps: Optional[int] = None,
) -> List[List[Pivot]]:
    """
    Greedy clustering by price distance threshold in basis points.
    Returns list of clusters (each a list of Pivot).
    """
    if not pivots:
        return []

    tol_bps = price_tol_bps or getattr(settings, "PRICE_TOL_BPS", 15)
    # Sort pivots by price to cluster close prices, but we’ll keep kinds
    piv_sorted = sorted(pivots, key=lambda p: p.price)
    clusters: List[List[Pivot]] = []

    def within(p: float, q: float) -> bool:
        tol = _basis_points((p + q) / 2.0, tol_bps)
        return abs(p - q) <= tol

    current: List[Pivot] = [piv_sorted[0]]
    for pv in piv_sorted[1:]:
        ref = np.median([x.price for x in current])
        if within(pv.price, ref):
            current.append(pv)
        else:
            clusters.append(current)
            current = [pv]
    clusters.append(current)
    return clusters


def _cluster_to_zone(
    cluster: List[Pivot],
    total_bars: int,
    ts_by_idx: Optional[np.ndarray] = None,
) -> Zone:
    """
    Build a Zone from a pivot cluster.
    - Center near weighted median by reaction magnitude and recency
    - Span = bps tolerance around center (conservative)
    - Score = touches (log-scaled) + recency decay + avg reaction magnitude
    """
    prices = np.array([p.price for p in cluster], dtype=float)
    last_touch_idx = int(max(p.idx for p in cluster))
    first_touch_idx = int(min(p.idx for p in cluster))
    kinds = [p.kind for p in cluster]

    # Recency: exponential decay by distance from last bar
    ages = np.array([total_bars - p.idx for p in cluster], dtype=float)
    hl = float(getattr(settings, "ZONE_MAX_AGE_BARS", 600))
    recency_w = np.exp(-ages / max(1.0, hl))

    # Reaction weights (absolute)
    react = np.array([abs(p.reaction_ret) for p in cluster], dtype=float)
    react_w = 1.0 + react * 20.0  # amplify but bounded-ish

    weights = recency_w * react_w
    # Weighted median center
    order = np.argsort(prices)
    ps, ws = prices[order], weights[order]
    csum = np.cumsum(ws)
    half = csum[-1] / 2.0 if csum[-1] > 0 else 0.0
    center = float(ps[np.searchsorted(csum, half)])

    tol_bps = getattr(settings, "PRICE_TOL_BPS", 15)
    span = _basis_points(center, tol_bps)

    # Zone kind: majority of H/L, else Mixed
    kind = "M"
    if kinds.count("H") > kinds.count("L"):
        kind = "H"
    elif kinds.count("L") > kinds.count("H"):
        kind = "L"

    # Score components
    W = getattr(
        settings,
        "ZONE_SCORE_WEIGHTS",
        {"touches": 0.45, "recency": 0.30, "reaction": 0.25},
    )
    touches_term = math.log(1.0 + len(cluster))
    recency_term = float(np.average(np.exp(-ages / max(1.0, hl)), weights=None))
    reaction_term = float(np.mean(react)) if len(react) else 0.0

    score = (
        W["touches"] * touches_term
        + W["recency"] * recency_term
        + W["reaction"] * reaction_term
    )

    return Zone(
        level=center,
        span=span,
        touches=len(cluster),
        score=float(score),
        last_touch_idx=last_touch_idx,
        last_reaction_ret=float(np.max(react) if len(react) else 0.0),
        kind=kind,  # type: ignore
        first_touch_idx=first_touch_idx,
    )


def score_zones(
    df: pd.DataFrame,
    pivots: List[Pivot],
    clusters: List[List[Pivot]],
) -> List[Zone]:
    """
    Convert clusters to scored Zones.
    """
    zones: List[Zone] = []
    total_bars = len(df)
    for cl in clusters:
        try:
            zones.append(_cluster_to_zone(cl, total_bars))
        except Exception as e:  # pragma: no cover
            logger.exception("zones: failed to build zone from cluster: %s", e)
    # Sort by score desc, then touches desc
    zones.sort(key=lambda z: (round(z.score, 6), z.touches), reverse=True)
    return zones


def nearest_zones(
    price: float, zones: List[Zone]
) -> Tuple[Optional[Zone], Optional[Zone]]:
    """
    Return (above, below) nearest zones around 'price'.
    """
    if not zones:
        return None, None
    above = [z for z in zones if z.level >= price]
    below = [z for z in zones if z.level < price]
    above_zone = min(above, key=lambda z: abs(z.level - price)) if above else None
    below_zone = min(below, key=lambda z: abs(z.level - price)) if below else None
    return above_zone, below_zone


def compute_zones(
    df: pd.DataFrame,
    left: int = 3,
    right: int = 3,
    lookback: Optional[int] = 800,
    price_tol_bps: Optional[int] = None,
) -> List[Zone]:
    """
    One-shot helper: find pivots → cluster → score zones.
    """
    pivots = find_swings(df, left=left, right=right, lookback=lookback)
    if not pivots:
        return []
    clusters = cluster_levels(pivots, price_tol_bps=price_tol_bps)
    return score_zones(df, pivots, clusters)


__all__ = [
    "Pivot",
    "Zone",
    "find_swings",
    "cluster_levels",
    "score_zones",
    "nearest_zones",
    "compute_zones",
]
