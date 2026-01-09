# =====================================
# File: domain/patterns.py (NEW)
# =====================================
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass
class Pattern:
    name: str  # e.g. RECTANGLE, ASC_TRIANGLE, DOUBLE_TOP, H_S
    bias: str  # BULL | BEAR | NEUTRAL
    confidence: float  # 0..1
    levels: Dict[str, float]  # e.g. {"breakout": ..., "stop": ..., "target": ...}
    span: Tuple[int, int]  # (start_idx, end_idx) bars


# --- Utils ---


def _linreg(y: np.ndarray) -> Tuple[float, float, float]:
    x = np.arange(len(y))
    A = np.vstack([x, np.ones_like(x)]).T
    slope, intercept = np.linalg.lstsq(A, y, rcond=None)[0]
    # R^2 for strength estimation
    y_fit = slope * x + intercept
    ss_res = float(np.sum((y - y_fit) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2)) + 1e-6
    r2 = 1.0 - ss_res / ss_tot
    return slope, intercept, r2


def _last_swings(
    df: pd.DataFrame, left: int, right: int
) -> Tuple[np.ndarray, np.ndarray]:
    H, L = df["high"].values, df["low"].values
    n = len(df)
    highs, lows = [], []
    for i in range(left, n - right):
        if H[i] == H[i - left : i + right + 1].max():
            highs.append(i)
        if L[i] == L[i - left : i + right + 1].min():
            lows.append(i)
    return np.array(highs, dtype=int), np.array(lows, dtype=int)


# --- Rectangle ---


def _detect_rectangle(
    df: pd.DataFrame,
    highs: np.ndarray,
    lows: np.ndarray,
    atr: np.ndarray,
    cfg: Dict[str, Any],
) -> Optional[Pattern]:
    min_sw = int(cfg.get("rectangle_min_swings", 6))
    if len(highs) + len(lows) < min_sw:
        return None
    span_start = int(
        min(
            highs[0] if len(highs) else len(df) - 1,
            lows[0] if len(lows) else len(df) - 1,
        )
    )
    span_end = int(max(highs[-1] if len(highs) else 0, lows[-1] if len(lows) else 0))
    Hs = df["high"].values[highs[-min(len(highs), 6) :]]
    Ls = df["low"].values[lows[-min(len(lows), 6) :]]
    if len(Hs) < 2 or len(Ls) < 2:
        return None
    top, bot = np.median(Hs), np.median(Ls)
    height = top - bot
    if height <= 0:
        return None
    # consolidation test: height vs ATR
    atr_now = float(atr[-1]) if len(atr) else float(height)
    if height / max(1e-6, atr_now) > 6.0:
        return None  # too tall to be a tight rectangle
    bias = "NEUTRAL"
    confidence = 0.4 + min(0.2, (len(Hs) + len(Ls) - 4) * 0.03)
    levels = {
        "top": float(top),
        "bottom": float(bot),
        "breakout_up": float(top + 0.1 * atr_now),
        "breakout_dn": float(bot - 0.1 * atr_now),
        "stop_up": float(bot - 0.2 * atr_now),
        "stop_dn": float(top + 0.2 * atr_now),
        "target_up": float(top + height),
        "target_dn": float(bot - height),
    }
    return Pattern("RECTANGLE", bias, float(confidence), levels, (span_start, span_end))


# --- Double Top/Bottom ---


def _detect_double(
    df: pd.DataFrame,
    highs: np.ndarray,
    lows: np.ndarray,
    atr: np.ndarray,
    cfg: Dict[str, Any],
) -> Optional[Pattern]:
    tol = float(cfg.get("double_peak_tol_atr", 0.8)) * float(
        atr[-1] if len(atr) else df["high"].std()
    )
    sep = int(cfg.get("double_sep_min", 8))
    # Double Top
    for i in range(len(highs) - 2, -1, -1):
        i1, i2 = highs[i], highs[-1]
        if i2 - i1 < sep:
            continue
        p1, p2 = df["high"].iloc[i1], df["high"].iloc[i2]
        if abs(p1 - p2) <= tol:
            mid = int((i1 + i2) // 2)
            neckline = float(df["low"].iloc[mid:i2].min())
            atr_now = float(atr[-1] if len(atr) else (p1 - neckline))
            levels = {
                "neckline": neckline,
                "breakout": neckline - 0.1 * atr_now,
                "stop": float(max(p1, p2) + 0.3 * atr_now),
                "target": float(neckline - (max(p1, p2) - neckline)),
            }
            return Pattern("DOUBLE_TOP", "BEAR", 0.55, levels, (i1, i2))
    # Double Bottom
    for i in range(len(lows) - 2, -1, -1):
        i1, i2 = lows[i], lows[-1]
        if i2 - i1 < sep:
            continue
        p1, p2 = df["low"].iloc[i1], df["low"].iloc[i2]
        if abs(p1 - p2) <= tol:
            mid = int((i1 + i2) // 2)
            neckline = float(df["high"].iloc[mid:i2].max())
            atr_now = float(atr[-1] if len(atr) else (neckline - p1))
            levels = {
                "neckline": neckline,
                "breakout": neckline + 0.1 * atr_now,
                "stop": float(min(p1, p2) - 0.3 * atr_now),
                "target": float(neckline + (neckline - min(p1, p2))),
            }
            return Pattern("DOUBLE_BOTTOM", "BULL", 0.55, levels, (i1, i2))
    return None


# --- Triangles ---


def _detect_triangle(
    df: pd.DataFrame, highs: np.ndarray, lows: np.ndarray, cfg: Dict[str, Any]
) -> Optional[Pattern]:
    min_sw = int(cfg.get("triangle_min_swings", 6))
    if len(highs) < 3 or len(lows) < 3 or (len(highs) + len(lows)) < min_sw:
        return None
    hseg = df["high"].values[highs[-min(5, len(highs)) :]]
    lseg = df["low"].values[lows[-min(5, len(lows)) :]]
    hs, hi, r2h = _linreg(hseg)
    ls, li, r2l = _linreg(lseg)
    # Opposite slopes converging → triangle
    if hs < 0 and ls > 0:
        name = "DESC_TRIANGLE"
        bias = "BEAR"
    elif hs > 0 and ls < 0:
        name = "ASC_TRIANGLE"
        bias = "BULL"
    else:
        return None
    confidence = max(0.35, 0.5 * (r2h + r2l) - 0.1)
    # breakout guide near latest highs/lows regression ends
    end_x = max(len(hseg), len(lseg)) - 1
    up_line = hs * end_x + hi
    dn_line = ls * end_x + li
    levels = {"breakout_up": float(up_line), "breakout_dn": float(dn_line)}
    return Pattern(
        name,
        bias,
        float(confidence),
        levels,
        (int(highs[-min(5, len(highs))]), int(lows[-1])),
    )


# --- Channel / Flag (simple) ---


def _detect_channel_flag(
    df: pd.DataFrame, atr: np.ndarray, cfg: Dict[str, Any]
) -> Optional[Pattern]:
    N = min(len(df), 120)
    if N < 40:
        return None
    close = df["close"].values[-N:]
    slope, intercept, r2 = _linreg(close)
    atr_now = float(atr[-1]) if len(atr) else float(np.std(close))
    # impulse check (flag): last 12 bars move vs ATR
    lastN = 12
    impulse = abs(close[-1] - close[-lastN])
    if impulse / max(1e-6, atr_now) >= float(cfg.get("flag_impulse_atr", 2.0)):
        bias = "BULL" if close[-1] > close[-lastN] else "BEAR"
        conf = 0.45 + min(0.2, r2 * 0.3)
        levels = {}
        return Pattern("FLAG", bias, float(conf), levels, (len(df) - N, len(df) - 1))
    # otherwise channel (if r2 high)
    if r2 > 0.6:
        bias = "BULL" if slope > 0 else "BEAR"
        conf = 0.4 + min(0.2, (r2 - 0.6) * 0.8)
        return Pattern("CHANNEL", bias, float(conf), {}, (len(df) - N, len(df) - 1))
    return None


def detect_patterns(
    df: pd.DataFrame,
    atr: np.ndarray,
    cfg: Dict[str, Any],
) -> List[Pattern]:
    left, right = int(cfg.get("pivot_left", 3)), int(cfg.get("pivot_right", 3))
    highs, lows = _last_swings(df, left, right)
    found: List[Pattern] = []
    for fn in (
        lambda: _detect_rectangle(df, highs, lows, atr, cfg),
        lambda: _detect_double(df, highs, lows, atr, cfg),
        lambda: _detect_triangle(df, highs, lows, cfg),
        lambda: _detect_channel_flag(df, atr, cfg),
    ):
        p = fn()
        if p is not None and p.confidence >= float(cfg.get("min_pattern_conf", 0.35)):
            found.append(p)
    # sort by confidence desc
    found.sort(key=lambda p: p.confidence, reverse=True)
    return found


def summarize_patterns(patterns: List[Pattern], limit: int = 3) -> str:
    if not patterns:
        return "none"
    out = []
    for p in patterns[:limit]:
        key_levels = ", ".join(f"{k}={v:.2f}" for k, v in p.levels.items())
        out.append(
            f"{p.name}({p.bias}, c={p.confidence:.2f}{', ' + key_levels if key_levels else ''})"
        )
    return " | ".join(out)
