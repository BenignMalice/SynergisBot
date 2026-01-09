# =====================================
# domain/levels.py
# =====================================
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import math
import numpy as np
import pandas as pd


def _np(x) -> np.ndarray:
    if isinstance(x, np.ndarray):
        return x
    try:
        return np.asarray(x, dtype=float)
    except Exception:
        return np.array([], dtype=float)


def _safe_float(x, d=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(d)


def _session_label(session: Optional[str]) -> str:
    s = (session or "").lower()
    if "ny" in s or "new york" in s or "us" in s or "newyork" in s:
        return "US"
    if "lon" in s or "ldn" in s or "london" in s or "eu" in s or "europe" in s:
        return "LDN"
    if "tok" in s or "tokyo" in s or "asia" in s or "sg" in s or "hong kong" in s:
        return "ASIA"
    return "GEN"


def _vap_histogram(
    df: Optional[pd.DataFrame], bins: int = 100
) -> Tuple[np.ndarray, np.ndarray]:
    if (
        df is None
        or df.empty
        or not {"high", "low", "tick_volume"}.issubset(df.columns)
    ):
        return np.array([]), np.array([])
    hi = df["high"].astype(float).to_numpy()
    lo = df["low"].astype(float).to_numpy()
    vol = df["tick_volume"].astype(float).to_numpy()
    pmin, pmax = float(np.nanmin(lo)), float(np.nanmax(hi))
    if not np.isfinite(pmin) or not np.isfinite(pmax) or pmax <= pmin:
        return np.array([]), np.array([])
    edges = np.linspace(pmin, pmax, bins + 1)
    hist = np.zeros(bins, dtype=float)
    # distribute each bar’s volume across the overlapping bins
    for L, H, V in zip(lo, hi, vol):
        if not np.isfinite(L) or not np.isfinite(H) or H <= L:
            continue
        # find bins spanned by [L,H]
        i0 = np.searchsorted(edges, L, side="right") - 1
        i1 = np.searchsorted(edges, H, side="right") - 1
        i0 = max(0, min(i0, bins - 1))
        i1 = max(0, min(i1, bins - 1))
        span = max(1, i1 - i0 + 1)
        hist[i0 : i1 + 1] += V / span
    centers = 0.5 * (edges[:-1] + edges[1:])
    return centers, hist


def _valid_df(df: Optional[pd.DataFrame]) -> bool:
    return (
        isinstance(df, pd.DataFrame)
        and not df.empty
        and all(c in df.columns for c in ("high", "low", "close", "time"))
    )


def _find_swings(df: pd.DataFrame, window: int = 3) -> Tuple[np.ndarray, np.ndarray]:
    """
    Simple swing high/low detection using a symmetric 'window' pivot.
    Returns arrays of swing_highs and swing_lows (values only).
    """
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    n = len(df)
    if n < (2 * window + 1):
        return np.array([]), np.array([])

    swing_highs = []
    swing_lows = []
    for i in range(window, n - window):
        seg_hi = h[i - window : i + window + 1]
        seg_lo = l[i - window : i + window + 1]
        if h[i] == seg_hi.max() and (seg_hi.argmax() == window):
            swing_highs.append((i, h[i]))
        if l[i] == seg_lo.min() and (seg_lo.argmin() == window):
            swing_lows.append((i, l[i]))

    return np.array(swing_highs, dtype=object), np.array(swing_lows, dtype=object)


def _cluster_levels(levels: np.ndarray, tol: float) -> List[np.ndarray]:
    if levels.size == 0:
        return []
    idx = np.argsort(levels)
    levels = levels[idx]
    bands = []
    cur = [levels[0]]
    for x in levels[1:]:
        if abs(x - cur[-1]) <= tol:
            cur.append(x)
        else:
            bands.append(np.array(cur))
            cur = [x]
    bands.append(np.array(cur))
    return bands


# ---- swing clustering -------------------------------------------------------


def _pivots(
    df: Optional[pd.DataFrame], left=3, right=3
) -> Tuple[np.ndarray, np.ndarray]:
    if df is None or df.empty or not {"high", "low"}.issubset(df.columns):
        return np.array([], dtype=int), np.array([], dtype=int)
    H = df["high"].astype(float).to_numpy()
    L = df["low"].astype(float).to_numpy()
    n = len(df)
    highs, lows = [], []
    for i in range(left, n - right):
        winH = H[i - left : i + right + 1]
        winL = L[i - left : i + right + 1]
        if H[i] == np.max(winH):
            highs.append(i)
        if L[i] == np.min(winL):
            lows.append(i)
    return np.array(highs, dtype=int), np.array(lows, dtype=int)


def _make_eps(price: float, atr: float | None, point: float | None) -> float:
    # clustering bandwidth: prefer ATR fraction; fallback to price*0.0008; never below 4*point
    base = atr or (price * 0.004)
    eps = 0.25 * base
    if point:
        eps = max(eps, 4.0 * float(point))
    return float(eps)


# ---- main API ---------------------------------------------------------------


def compute_sr_snapshot(
    m5_df: Optional[pd.DataFrame],
    m15_df: Optional[pd.DataFrame],
    price_now: float,
    atr: float,
    symbol: str,
    *,
    point: float = 0.0,
    session: Optional[str] = None,
    max_zones: int = 10,
) -> Dict[str, object]:
    """
    Returns:
      {
        "zones": [
          {
            "level": float,        # center of band
            "width": float,        # half-width (treat zone as [level - width, level + width])
            "kind": "SUPPORT"|"RESISTANCE",
            "strength": float,     # 0..1
            "touches": int,        # pivot-count backing this zone
            "volume_weight": float,# 0..1 relative weight from VAP
            "label": str           # e.g., "LDN-Support" or "US-Resistance"
          }, ...
        ],
        "nearest": { ... same keys ... , "distance_frac_atr": float },
        "session": "US|LDN|ASIA|GEN"
      }
    """
    price = _safe_float(price_now, 0.0)
    atr = _safe_float(atr, 0.0)
    tol = max(
        atr * 0.20, price * 0.0004, 6.0 * float(point or 0.0)
    )  # cluster tolerance
    band_half_min = max(atr * 0.10, price * 0.0002, 3.0 * float(point or 0.0))

    # pivots from M5+M15
    h5, l5 = _pivots(m5_df, 3, 3)
    h15, l15 = _pivots(m15_df, 2, 2)
    piv_hi_vals = []
    piv_lo_vals = []
    if m5_df is not None and len(h5):
        piv_hi_vals.extend(m5_df["high"].iloc[h5].astype(float).tolist())
    if m15_df is not None and len(h15):
        piv_hi_vals.extend(m15_df["high"].iloc[h15].astype(float).tolist())
    if m5_df is not None and len(l5):
        piv_lo_vals.extend(m5_df["low"].iloc[l5].astype(float).tolist())
    if m15_df is not None and len(l15):
        piv_lo_vals.extend(m15_df["low"].iloc[l15].astype(float).tolist())
    piv_hi = _np(piv_hi_vals)
    piv_lo = _np(piv_lo_vals)

    # cluster highs/lows into bands
    hi_bands = _cluster_levels(piv_hi, tol)
    lo_bands = _cluster_levels(piv_lo, tol)

    # volume-at-price proxy (M5 preferred)
    centers, vap = _vap_histogram(m5_df, bins=120)
    vap_norm = vap / vap.max() if vap.size and vap.max() > 0 else vap

    zones: List[Dict[str, object]] = []

    def _band_stats(vals: np.ndarray) -> Tuple[float, float, int]:
        if vals.size == 0:
            return 0.0, 0.0, 0
        center = float(np.median(vals))
        width = max(float(np.std(vals)), band_half_min)
        if atr > 0:
            width = min(width, 0.75 * atr)  # soft cap
        touches = int(vals.size)
        return center, width, touches

    def _vap_weight_at(level: float, width: float) -> float:
        if centers.size == 0:
            return 0.0
        lo = level - width
        hi = level + width
        mask = (centers >= lo) & (centers <= hi)
        score = float(np.nanmean(vap_norm[mask])) if np.any(mask) else 0.0
        if not np.isfinite(score):
            score = 0.0
        return score

    sess = _session_label(session)
    sess_prefix = {"US": "US", "LDN": "LDN", "ASIA": "ASIA", "GEN": "GEN"}[sess]

    # Build zones from high-bands (resistance) and low-bands (support)
    for band in hi_bands:
        lvl, w, n = _band_stats(band)
        vw = _vap_weight_at(lvl, w)
        strength = float(min(1.0, 0.25 + 0.12 * n + 0.6 * vw))
        zones.append(
            {
                "level": lvl,
                "width": w,
                "kind": "RESISTANCE",
                "strength": strength,
                "touches": n,
                "volume_weight": vw,
                "label": f"{sess_prefix}-Resistance",
            }
        )
    for band in lo_bands:
        lvl, w, n = _band_stats(band)
        vw = _vap_weight_at(lvl, w)
        strength = float(min(1.0, 0.25 + 0.12 * n + 0.6 * vw))
        zones.append(
            {
                "level": lvl,
                "width": w,
                "kind": "SUPPORT",
                "strength": strength,
                "touches": n,
                "volume_weight": vw,
                "label": f"{sess_prefix}-Support",
            }
        )

    # Sort zones by distance to price and strength
    def _dist_frac(z):
        d = abs(_safe_float(z.get("level")) - price) - _safe_float(z.get("width"))
        d = max(0.0, d)
        return (d / max(1e-9, atr)) if atr > 0 else d

    zones.sort(key=lambda z: (_dist_frac(z), -_safe_float(z.get("strength"), 0.0)))
    zones = zones[:max_zones]

    # Nearest zone (by edge distance)
    nearest = None
    if zones:
        nearest = min(
            zones,
            key=lambda z: max(
                0.0,
                abs(_safe_float(z["level"]) - price) - _safe_float(z["width"], 0.0),
            ),
        )
        if nearest is not None:
            edge_dist = max(
                0.0,
                abs(_safe_float(nearest["level"]) - price)
                - _safe_float(nearest.get("width"), 0.0),
            )
            nearest = dict(nearest)
            nearest["distance_frac_atr"] = (
                edge_dist / max(1e-9, atr) if atr > 0 else float("inf")
            )

    return {"zones": zones, "nearest": nearest, "session": sess}
