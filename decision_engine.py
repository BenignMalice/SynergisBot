# =====================================
# decision_engine.py
# =====================================
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, Optional, Any
import logging
import numpy as np
import pandas as pd
from infra.price_utils import get_symbol_meta
from domain.candle_stats import compute_candle_stats
from config import settings

# --- S/R module ---
from domain.levels import compute_sr_snapshot

# --- PA 2.0: zones, sweeps, breakout quality, micro-structure ---
from domain.zones import compute_zones, find_swings, nearest_zones
from domain.liquidity import detect_sweep
from domain.breakout_quality import latest_breakout_quality
from domain.market_structure import label_swings, structure_bias

# --- Chart patterns module ---
from domain.patterns import detect_patterns, summarize_patterns

# === ANCHOR: IMPORTS_END ===

# Try to import advanced features
try:
    from infra.feature_builder_advanced import build_features_advanced, FeatureBuilderAdvanced
except Exception:
    build_features_advanced = None
    FeatureBuilderAdvanced = None

# S/R sensitivity knobs
SR_NEAR_FRAC = 0.30  # within 0.30 * ATR → "near" support/resistance (adds trigger)
SR_BLOCK_FRAC = (
    0.20  # within 0.20 * ATR against direction AND RR low → add guard & HOLD
)

try:
    from domain.confluence import compute_mtf_confluence
except Exception:
    compute_mtf_confluence = None

try:
    from domain.candles import detect_recent_patterns
except Exception:
    detect_recent_patterns = None

logger = logging.getLogger(__name__)

# Thresholds / knobs
ADX_TREND = 35.0
ADX_SIDEWAYS_CUTOFF = 28.0
ADX_WEAK = 22.0

BB_SQUEEZE = 0.012
RANGE_FRAC = 0.004
MICRO_ROC = 0.0005
EMA_SLOPE = 2e-4

ATR_SPIKE_MULT = 1.8  # kept as a global default (overridden per symbol at runtime)
HTF_WICK_FRAC = 0.45  # reserved for future use

TREND_SL_MULT = 1.20
TREND_TP_MULT = 1.80
RANGE_SL_MULT = 1.00
RANGE_TP_MULT = 1.00
VOL_SL_MULT = 1.30
VOL_TP_MULT = 1.70

# --- RSI alignment ---
RSI_BULL = 55.0
RSI_BEAR = 45.0

# --- Range patience ---
# Require the box to be "valid" (both edges touched >= 2 times)
# AND to have soaked for at least this many M5 bars since the first edge touch we observed.
RANGE_MIN_TOUCHES_EACH = 2
RANGE_PATIENCE_BARS = 6  # ~30 minutes on M5

# --- PA 2.0 zones lookback ---
ZONES_LOOKBACK = 120  # 120 bars for zone detection


@dataclass
class Recommendation:
    direction: str
    entry: float
    sl: float
    tp: float
    rr: float
    regime: str
    reasoning: str
    strategy: str
    confidence: int

    def as_dict(self) -> Dict[str, object]:
        return {
            "direction": self.direction,
            "entry": float(self.entry),
            "sl": float(self.sl),
            "tp": float(self.tp),
            "rr": float(self.rr),
            "regime": self.regime,
            "reasoning": self.reasoning,
            "strategy": self.strategy,
            "confidence": int(self.confidence),
        }


# ---------------- helpers ----------------
def _safe_float(x, default=None):
    try:
        return float(x)
    except Exception:
        return default


def _recompute_rr(direction: str, entry, sl, tp) -> Optional[float]:
    """Return R:R if levels are consistent for the side, else None."""
    e = _safe_float(entry)
    s = _safe_float(sl)
    t = _safe_float(tp)
    if e is None or s is None or t is None:
        return None
    if str(direction).upper() == "BUY":
        if not (s < e < t):
            return None
        r = abs(t - e) / max(1e-12, abs(e - s))
        return r
    if str(direction).upper() == "SELL":
        if not (t < e < s):
            return None
        r = abs(e - t) / max(1e-12, abs(s - e))
        return r
    return None


def _nearest_from_sr_blob(tech: dict) -> Optional[dict]:
    """
    Expects tech['sr'] = {'nearest': {'kind','level','distance_frac_atr','label'?}, ...}
    If distance_frac_atr is missing, derive it from ATR and current close.
    Returns the 'nearest' dict or None.
    """
    sr = tech.get("sr")
    if not isinstance(sr, dict):
        return None
    nearest = sr.get("nearest")
    if not isinstance(nearest, dict):
        return None

    # Fill distance_frac_atr if missing
    if "distance_frac_atr" not in nearest or nearest.get("distance_frac_atr") is None:
        lvl = _safe_float(nearest.get("level"))
        close = _safe_float(tech.get("close"))
        atr = _safe_float(tech.get("atr_14"), 0.0)
        if lvl is not None and close is not None and atr and atr > 0:
            nearest["distance_frac_atr"] = abs(lvl - close) / atr
    return nearest


def _fmt_snapshot(
    symbol: str,
    bid: float,
    ask: float,
    ema20: float,
    ema50: float,
    ema200: float,
    atr14: float,
    adx: float,
    bb_width: float,
) -> str:
    meta = get_symbol_meta(symbol)
    bid_s = f"{bid:.{meta.digits}f}"
    ask_s = f"{ask:.{meta.digits}f}"
    e20 = f"{ema20:.{meta.digits}f}"
    e50 = f"{ema50:.{meta.digits}f}"
    e200 = f"{ema200:.{meta.digits}f}"
    atr_s = f"{atr14:.{meta.digits}f}"
    bb_s = f"{bb_width:.6f}"
    return f"ADX={adx:.2f}, ATR14={atr_s}, EMA20/50/200={e20}/{e50}/{e200}, BBWidth={bb_s}\n**Live:** Bid={bid_s} | Ask={ask_s}"


def _atr_is_sane(symbol: str, atr14: float) -> bool:
    # Reject obviously broken ATR (e.g., 0.0 due to data gap). Threshold = 2 ticks.
    meta = get_symbol_meta(symbol)
    return atr14 and atr14 >= 2 * meta.tick_size


def _to_f(x, d=0.0):
    """
    Convert x to float when possible.
    Returns d (or float(d)) if conversion fails.
    Preserves None if d is None so callers can detect 'unknown'.
    """
    if x is None:
        return d if d is None else float(d)
    try:
        return float(x)
    except Exception:
        try:
            return d if d is None else float(d)
        except Exception:
            return 0.0


def _safe(key: str, *sources, default=None):
    for s in sources:
        if isinstance(s, dict) and key in s and s[key] is not None:
            return s[key]
    return default


def _rr(entry: float, sl: float, tp: float) -> float:
    risk = abs(entry - sl)
    rew = abs(tp - entry)
    return rew / max(1e-9, risk)


def _wick_stats(o, h, l, c):
    rng = max(1e-9, h - l)
    return (h - max(o, c)) / rng, (min(o, c) - l) / rng, rng


def _mtf_confluence(m5: Dict, m15: Dict, m30: Dict, h1: Dict) -> Tuple[float, str, int]:
    if callable(compute_mtf_confluence):
        return compute_mtf_confluence(m5, m15, m30, h1)

    # simple fallback
    def align(d):
        try:
            return 1 if float(d.get("close", 0)) >= float(d.get("ema_200", 0)) else -1
        except Exception:
            return 0

    def trend_ok(d):
        a = _to_f(d.get("adx_14", d.get("adx")), 0.0)
        return max(0.0, min(1.0, (a - ADX_WEAK) / (ADX_TREND - ADX_WEAK)))

    a5, a15, a30, a60 = align(m5), align(m15), align(m30), align(h1)
    bias = (
        1 if (a5 + a15 + a30 + a60) > 0 else (-1 if (a5 + a15 + a30 + a60) < 0 else 0)
    )
    agree = (sum(v == bias for v in (a5, a15, a30, a60)) / 4.0) if bias != 0 else 0.0
    trend = max(trend_ok(m5), trend_ok(m15), trend_ok(m30)) * 0.4 + trend_ok(h1) * 0.6
    score = max(0.0, min(1.0, 0.6 * agree + 0.4 * trend))
    label = (
        "STRONG_CONFLUENCE"
        if score >= 0.7
        else (
            "MODERATE_CONFLUENCE"
            if score >= 0.45
            else ("WEAK_CONFLUENCE" if score >= 0.25 else "NO_CONFLUENCE")
        )
    )
    return score, label, bias


def _pattern_bias(df: Optional[pd.DataFrame]) -> Tuple[str, int]:
    if not callable(detect_recent_patterns) or df is None or df.empty:
        return "", 0
    try:
        pat, bias = detect_recent_patterns(df)
        return pat, int(bias)
    except Exception:
        return "", 0


def _compute_regime(adx: float, bb_width: float, ema_slope_h1: float) -> str:
    if adx >= ADX_TREND and abs(ema_slope_h1) >= EMA_SLOPE:
        return "TREND"
    if bb_width <= BB_SQUEEZE and adx < 25:
        return "RANGE"
    return "VOLATILE"


def _determine_trend_direction(m5: dict, m15: dict, m30: dict, h1: dict, price: float, 
                              ema200: float, mtf_bias: float, rsi5: float, rsi15: float, rsi30: float) -> str:
    """
    IMPROVED: Determine trend direction with timeframe priority and confluence scoring.
    Prioritizes H1 > M15 > M5 for trend direction, with RSI confluence validation.
    """
    # Timeframe priority weights
    h1_weight = 0.5
    m15_weight = 0.3  
    m5_weight = 0.2
    
    # Get ADX and trend direction from each timeframe
    adx_h1 = _to_f(_safe("adx_14", h1, default=_safe("adx", h1, default=0)), 0.0)
    adx_m15 = _to_f(_safe("adx_14", m15, default=_safe("adx", m15, default=0)), 0.0)
    adx_m5 = _to_f(_safe("adx_14", m5, default=_safe("adx", m5, default=0)), 0.0)
    
    # Get EMA slopes for trend direction
    ema_slope_h1 = _to_f(_safe("ema_200_slope", h1, default=_safe("ema_slope_h1", h1, default=0)), 0.0)
    ema_slope_m15 = _to_f(_safe("ema_200_slope", m15, default=_safe("ema_slope_m15", m15, default=0)), 0.0)
    ema_slope_m5 = _to_f(_safe("ema_200_slope", m5, default=_safe("ema_slope_m5", m5, default=0)), 0.0)
    
    # Calculate trend direction scores (-1 to +1)
    h1_direction = 1 if ema_slope_h1 > 0 else (-1 if ema_slope_h1 < 0 else 0)
    m15_direction = 1 if ema_slope_m15 > 0 else (-1 if ema_slope_m15 < 0 else 0)
    m5_direction = 1 if ema_slope_m5 > 0 else (-1 if ema_slope_m5 < 0 else 0)
    
    # Weighted trend direction
    weighted_direction = (
        h1_weight * h1_direction + 
        m15_weight * m15_direction + 
        m5_weight * m5_direction
    )
    
    # RSI confluence check (all timeframes should agree)
    rsi_bullish = rsi5 > 50 and rsi15 > 50 and rsi30 > 50
    rsi_bearish = rsi5 < 50 and rsi15 < 50 and rsi30 < 50
    rsi_neutral = not (rsi_bullish or rsi_bearish)
    
    # ADX strength check (at least H1 or M15 should show trend strength)
    adx_strong = adx_h1 > 25 or adx_m15 > 25
    
    # Final decision logic
    if weighted_direction > 0.2 and (rsi_bullish or rsi_neutral) and adx_strong:
        return "BUY"
    elif weighted_direction < -0.2 and (rsi_bearish or rsi_neutral) and adx_strong:
        return "SELL"
    else:
        # Fallback to original logic if no clear direction
        return "BUY" if (mtf_bias if mtf_bias != 0 else (1 if price >= ema200 else -1)) >= 0 else "SELL"


def _atr_series(df: Optional[pd.DataFrame], period: int = 14) -> np.ndarray:
    """Return a simple ATR series aligned to df using classic Wilder smoothing (approx via SMA for brevity)."""
    if df is None or df.empty or not {"high", "low", "close"}.issubset(df.columns):
        return np.array([])
    h = df["high"].astype(float).to_numpy()
    l = df["low"].astype(float).to_numpy()
    c = df["close"].astype(float).to_numpy()
    prev_c = np.roll(c, 1)
    prev_c[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    # simple rolling mean; good enough for pattern thresholds
    atr = pd.Series(tr).rolling(period, min_periods=period).mean().to_numpy()
    return atr


def _calc_rsi(df: Optional[pd.DataFrame], period: int = 14) -> Optional[float]:
    """
    Compute the classic RSI (14) for the provided pandas DataFrame of OHLCV data.
    Returns the last RSI value or None on error/insufficient data.
    """
    if df is None or len(df) < period + 1:
        return None
    try:
        close = df["close"].astype(float)
        diffs = close.diff().dropna()
        gains = diffs.clip(lower=0.0)
        losses = (-diffs).clip(lower=0.0)
        avg_gain = gains.rolling(period).mean().iloc[-1]
        avg_loss = losses.rolling(period).mean().iloc[-1]
        if avg_loss is not None and avg_loss > 1e-12:
            rs = avg_gain / avg_loss
            return float(100.0 - (100.0 / (1.0 + rs)))
        elif avg_gain is not None:
            return 100.0
    except Exception:
        return None
    return None


def _rsi_dir(val: float) -> int:
    if val is None:
        return 0
    if val >= RSI_BULL:
        return +1
    if val <= RSI_BEAR:
        return -1
    return 0


def _count_touches(
    series: np.ndarray, level: float, price: float, eps_frac: float = 0.0008
) -> int:
    if series.size == 0:
        return 0
    eps = max(1e-9, price * eps_frac)
    return int(np.sum(np.abs(series - level) <= eps))


# --- S/R post-process helper (zones as bands + session-aware keepaway) ---
def apply_sr_postprocess(
    rec: Dict[str, object],
    tech_like: Dict[str, object],
    *,
    pad_sl_frac: float = 0.15,
    pad_tp_frac: float = 0.20,
    min_keepaway_frac: float = 0.05,
    allow_llm_anchor: bool = True,
) -> Dict[str, object]:
    """
    - Treat zones as bands (level±width).
    - Pad SL/TP beyond zone edges (fractions of ATR).
    - Add session-aware "keepaway" distance checks (NY overruns allowed slightly).
    - Optionally accept LLM-anchored SL/TP if they land on the correct opposite band.
    - Enforce headroom guard (flip to HOLD) if RR weak & opposing band too close.
    """
    out = dict(rec or {})
    sr = (tech_like or {}).get("sr") or out.get("sr")
    if not isinstance(sr, dict):
        return out

    atr = _to_f((tech_like or {}).get("atr_14"), 0.0)
    price = _to_f((tech_like or {}).get("close"), _to_f(out.get("entry"), 0.0))
    session = _safe("session", tech_like, default=None) or sr.get("session")

    # session keepaway modifier (NY tends to overrun → allow slightly smaller keepaway)
    sess_mod = 1.0
    s = str(session or "").upper()
    if "US" in s or "NY" in s:
        sess_mod = 0.85
    elif "ASIA" in s:
        sess_mod = 1.10
    # LDN/default → 1.0

    keepaway = max(0.0, float(min_keepaway_frac) * float(atr)) * float(sess_mod)
    pad_sl = max(0.0, float(pad_sl_frac) * float(atr))
    pad_tp = max(0.0, float(pad_tp_frac) * float(atr))

    zones = list(sr.get("zones") or [])
    if not zones or atr <= 0.0:
        return out

    # pick nearest band above/below current price (anchor by entry if present, else price)
    ref = _to_f(out.get("entry"), price)
    above = sorted(
        [z for z in zones if _to_f(z.get("level")) >= ref],
        key=lambda z: _to_f(z.get("level")),
    )
    below = sorted(
        [z for z in zones if _to_f(z.get("level")) <= ref],
        key=lambda z: _to_f(z.get("level")),
        reverse=True,
    )
    z_above = above[0] if above else None
    z_below = below[0] if below else None

    def band_top(z):
        return _to_f(z.get("level")) + _to_f(z.get("width"), 0.0)

    def band_bot(z):
        return _to_f(z.get("level")) - _to_f(z.get("width"), 0.0)

    direction = str(out.get("direction", "")).upper()
    e = _to_f(out.get("entry"), ref)
    sl = _to_f(out.get("sl"), None)
    tp = _to_f(out.get("tp"), None)

    # (Optional) accept LLM levels if they properly anchor to opposite band
    if (
        allow_llm_anchor
        and direction in ("BUY", "SELL")
        and sl is not None
        and tp is not None
    ):
        if direction == "BUY" and z_below and z_above:
            ok_sl = sl <= band_bot(z_below) - keepaway
            ok_tp = tp <= band_top(z_above) + pad_tp  # don’t force; we cap next
            if not ok_sl:
                sl = min(sl, band_bot(z_below) - pad_sl)
            tp = min(tp, band_top(z_above))  # TP anchored at next resistance edge
        elif direction == "SELL" and z_above and z_below:
            ok_sl = sl >= band_top(z_above) + keepaway
            ok_tp = tp >= band_bot(z_below) - pad_tp
            if not ok_sl:
                sl = max(sl, band_top(z_above) + pad_sl)
            tp = max(tp, band_bot(z_below))  # TP anchored at next support edge

    # If we still have None, seed ATR-based levels (already seeded by caller usually)
    if direction == "BUY":
        if sl is None and z_below:
            sl = band_bot(z_below) - pad_sl
        if tp is None and z_above:
            tp = band_top(z_above)
    elif direction == "SELL":
        if sl is None and z_above:
            sl = band_top(z_above) + pad_sl
        if tp is None and z_below:
            tp = band_bot(z_below)

    # Headroom guard: if opposing band is too close AND RR already weak → HOLD
    rr = _rr(e, sl, tp) if (sl is not None and tp is not None) else 0.0
    nearest = sr.get("nearest") or {}
    nr_kind = str(nearest.get("kind") or "").upper()
    nr_frac = float(nearest.get("distance_frac_atr") or 1e9)

    if direction in ("BUY", "SELL") and rr < 1.2 and nr_frac < (0.20 * sess_mod):
        if (direction == "BUY" and nr_kind == "RESISTANCE") or (
            direction == "SELL" and nr_kind == "SUPPORT"
        ):
            out["direction"] = "HOLD"
            g = set(out.get("guards") or [])
            g.add("sr_headroom_small")
            out["guards"] = sorted(g)
            # keep sr attached and exit early
            out["rr"] = rr
            out["sr"] = sr
            return out

    # writeback (and recompute RR)
    if sl is not None:
        out["sl"] = float(sl)
    if tp is not None:
        out["tp"] = float(tp)
    if direction in ("BUY", "SELL") and sl is not None and tp is not None:
        out["rr"] = _rr(e, sl, tp)
    out["sr"] = sr
    return out


# ---------------- main ----------------
def decide_trade(
    symbol: str,
    m5: Dict,
    m15: Dict,
    m30: Dict,
    h1: Dict,
    *,
    m5_df: Optional[pd.DataFrame] = None,
    m15_df: Optional[pd.DataFrame] = None,
    range_state: Optional[dict] = None,  # <-- stateful range patience
    advanced_features: Optional[Dict[str, Any]] = None,  # <-- advanced features
) -> Dict[str, object]:

    guards: list[str] = []  # negative filters that blocked stuff
    triggers: list[str] = []  # positive confirmations
    state = dict(range_state or {})

    # Extract advanced features if available
    rmag = {}
    ema_slope_advanced = {}
    vol_trend = {}
    pressure = {}
    candle_profile = []
    liquidity = {}
    fvg = {}
    vwap_dev = {}
    accel = {}
    mtf_score_advanced = {}
    vp = {}
    
    if advanced_features and isinstance(advanced_features, dict):
        features_data = advanced_features.get("features", {})
        
        # Get M5 features (primary timeframe for scalping)
        m5_features = features_data.get("M5", {})
        rmag = m5_features.get("rmag", {})
        ema_slope_advanced = m5_features.get("ema_slope", {})
        vol_trend = m5_features.get("vol_trend", {})
        pressure = m5_features.get("pressure", {})
        candle_profile = m5_features.get("candle_profile", [])
        liquidity = m5_features.get("liquidity", {})
        fvg = m5_features.get("fvg", {})
        vwap_dev = m5_features.get("vwap", {})
        accel = m5_features.get("accel", {})
        
        # Get MTF alignment score
        mtf_score_advanced = features_data.get("mtf_score", {})
        
        # Get volume profile
        vp = features_data.get("vp", {})

    price = _to_f(_safe("close", m5, h1), 0.0)
    atr = _to_f(_safe("atr_14", m5), 2.0)
    ema200 = _to_f(_safe("ema_200", m5, h1), price)
    adx = _to_f(_safe("adx_14", m5), _to_f(_safe("adx", m5), 0.0))
    bbw = _to_f(_safe("bb_width", m5), 0.0)
    ema_slope_h1 = _to_f(
        _safe(
            "ema_200_slope",
            h1,
            {"ema_200_slope": _safe("ema_slope_h1", h1, m5, default=0.0)},
        ),
        0.0,
    )

    # regime
    regime = _compute_regime(adx, bbw, ema_slope_h1)

    # range features
    in_range = bool(_safe("in_range", m5, default=False))
    rng_hi = _to_f(_safe("range_high_m5", m5), price * (1 + RANGE_FRAC))
    rng_lo = _to_f(_safe("range_low_m5", m5), price * (1 - RANGE_FRAC))
    micro_roc = _to_f(_safe("micro_roc5", m5), 0.0)
    squeeze = bool(_safe("squeeze", m5, default=False))
    bb_change = _to_f(_safe("bb_width_change", m5), 0.0)

    # timestamps (for patience)
    last_ts = None
    if m5_df is not None and "time" in m5_df.columns and not m5_df.empty:
        try:
            last_ts = pd.to_datetime(m5_df["time"].iloc[-1])
        except Exception:
            last_ts = None

    # --- Session for S/R + geometry thresholds ---
    sess: Optional[str] = None
    if last_ts is not None:
        try:
            sess = settings.get_trading_session(last_ts, tz="Africa/Johannesburg")
        except Exception:
            sess = None

    # MTF confluence
    mtf_score, mtf_label, mtf_bias = _mtf_confluence(m5, m15, m30, h1)

    # Patterns (once)
    pat_m5, bias5 = _pattern_bias(m5_df)
    pat_m15, bias15 = _pattern_bias(m15_df)
    pat_bias = int(bias5) + int(bias15)
    if pat_m5:
        triggers.append(f"m5:{pat_m5}")
    if pat_m15:
        triggers.append(f"m15:{pat_m15}")

    # --- Structural chart patterns (rectangles/triangles/double tops/flags/channels)
    patterns_summary = "none"
    try:
        pcfg = getattr(settings, "PATTERN_CONFIG", {})  # optional knobs in settings
        atr_m5 = _atr_series(m5_df, 14)
        patterns_m5 = detect_patterns(m5_df, atr_m5, pcfg) if m5_df is not None else []
        # bias nudge from top pattern (small, because we already use candle patterns)
        if patterns_m5:
            top = patterns_m5[0]
            triggers.append(f"pattern:{top.name}:{top.bias}")
            if top.bias == "BULL":
                pat_bias += 1
            elif top.bias == "BEAR":
                pat_bias -= 1
        patterns_summary = summarize_patterns(patterns_m5, limit=3)
    except Exception:
        pass

    # === ANCHOR: ADVANCED_FEATURES_GUARDS ===
    # --- Advanced Feature Filters ---
    # Apply institutional-grade filters based on advanced features
    if advanced_features:
        try:
            # RMAG: Avoid stretched trends
            if rmag.get("ema200_atr", 0) > 2.0:
                guards.append(f"rmag:stretched_above_ema200({rmag['ema200_atr']:.1f}σ)")
            elif rmag.get("ema200_atr", 0) < -2.0:
                guards.append(f"rmag:stretched_below_ema200({abs(rmag['ema200_atr']):.1f}σ)")
            
            if abs(rmag.get("vwap_atr", 0)) > 1.8:
                guards.append(f"rmag:far_from_vwap({rmag['vwap_atr']:.1f}σ)")
            
            # EMA Slope: Avoid flat markets
            ema50_slope = ema_slope_advanced.get("ema50", 0)
            ema200_slope = ema_slope_advanced.get("ema200", 0)
            if abs(ema50_slope) < 0.05 and abs(ema200_slope) < 0.03:
                guards.append("ema_slope:flat_trend_avoid")
            elif ema50_slope > 0.15 and ema200_slope > 0.05:
                triggers.append("ema_slope:strong_uptrend")
            elif ema50_slope < -0.15 and ema200_slope < -0.05:
                triggers.append("ema_slope:strong_downtrend")
            
            # Bollinger-ADX Fusion: Squeeze detection
            vol_state = vol_trend.get("state", "unknown")
            if vol_state == "squeeze_no_trend":
                triggers.append("vol_trend:squeeze_breakout_pending")
            elif vol_state == "expansion_strong_trend":
                triggers.append("vol_trend:momentum_continuation")
            elif vol_state == "squeeze_with_trend":
                guards.append("vol_trend:choppy_with_trend")
            
            # RSI-ADX Pressure: Fake vs quality
            pressure_ratio = pressure.get("ratio", 0)
            rsi_val = pressure.get("rsi", 50)
            adx_val = pressure.get("adx", 0)
            if rsi_val > 65 and adx_val < 20:
                guards.append(f"pressure:overbought_weak_trend(rsi={rsi_val:.0f},adx={adx_val:.0f})")
            elif rsi_val < 35 and adx_val < 20:
                guards.append(f"pressure:oversold_weak_trend(rsi={rsi_val:.0f},adx={adx_val:.0f})")
            elif (rsi_val > 60 and adx_val > 30) or (rsi_val < 40 and adx_val > 30):
                triggers.append(f"pressure:quality_momentum(rsi={rsi_val:.0f},adx={adx_val:.0f})")
            
            # Candle Profile: Rejection vs conviction
            if candle_profile:
                last_candle = candle_profile[-1]
                ctype = last_candle.get("type", "neutral")
                if ctype in ["rejection_up", "rejection_down"]:
                    triggers.append(f"candle:strong_rejection_{ctype.split('_')[1]}")
                elif ctype == "conviction":
                    triggers.append("candle:full_body_conviction")
            
            # Liquidity: Avoid pre-grab entries
            pdl_dist = liquidity.get("pdl_dist_atr", 999)
            pdh_dist = liquidity.get("pdh_dist_atr", 999)
            if pdl_dist < 0.5:
                guards.append(f"liquidity:too_close_to_pdl({pdl_dist:.1f}σ)")
            elif pdh_dist < 0.5:
                guards.append(f"liquidity:too_close_to_pdh({pdh_dist:.1f}σ)")
            
            if liquidity.get("equal_highs") or liquidity.get("equal_lows"):
                triggers.append("liquidity:equal_levels_detected")
            
            # FVG: Use as targets or entries
            fvg_type = fvg.get("type", "none")
            fvg_dist = fvg.get("dist_to_fill_atr", 999)
            if fvg_type != "none" and fvg_dist < 1.0:
                triggers.append(f"fvg:{fvg_type}_gap_nearby({fvg_dist:.1f}σ)")
            
            # VWAP Deviation: Mean reversion context
            vwap_zone = vwap_dev.get("zone", "inside")
            if vwap_zone == "outer":
                triggers.append(f"vwap:outer_zone_mean_reversion({vwap_dev.get('dev_atr', 0):.1f}σ)")
            
            # Momentum Acceleration: Fading or strengthening
            macd_slope = accel.get("macd_slope", 0)
            rsi_slope = accel.get("rsi_slope", 0)
            if macd_slope < -0.02 and rsi_slope < -2.0:
                guards.append("accel:momentum_fading")
            elif macd_slope > 0.03 and rsi_slope > 2.0:
                triggers.append("accel:momentum_accelerating")
            
            # MTF Alignment: Require confluence
            mtf_total = mtf_score_advanced.get("total", 0)
            mtf_max = mtf_score_advanced.get("max", 3)
            if mtf_total >= 2:
                triggers.append(f"mtf:aligned_{mtf_total}/{mtf_max}")
            elif mtf_total == 0:
                guards.append("mtf:no_timeframe_agreement")
            
            # Volume Profile: HVN/LVN zones
            hvn_dist = vp.get("hvn_dist_atr", 999)
            if hvn_dist < 0.3:
                triggers.append(f"vp:near_hvn_magnet({hvn_dist:.1f}σ)")
        
        except Exception as e:
            logger.debug(f"Advanced features guard/trigger processing failed: {e}")
    # === ANCHOR: ADVANCED_FEATURES_GUARDS_END ===

    # --- Support/Resistance snapshot (session-aware) ---
    try:
        point = float(_safe("_point", m5, default=0.0))
    except Exception:
        point = 0.0
    sr = compute_sr_snapshot(
        m5_df, m15_df, price, atr, symbol, point=point, session=sess, max_zones=10
    )

    # === ANCHOR: PA20_START ===
    # PA 2.0 context (zones, sweeps, breakout quality, micro-structure)
    # Use M5 dataframe as working TF; fallback safe if missing.
    pa_ctx = {}
    try:
        _df = m5_df if (m5_df is not None and not m5_df.empty) else None
        if _df is not None:
            # Compute zones once; modest lookback keeps it quick
            zones = compute_zones(_df, left=3, right=3, lookback=ZONES_LOOKBACK)
            swings = find_swings(_df, left=3, right=3, lookback=ZONES_LOOKBACK)
            struct_pts = label_swings(swings)
            struct_bias = structure_bias(struct_pts, lookback=6)

            last_price = float(_df["close"].iloc[-1])
            z_above, z_below = nearest_zones(last_price, zones)

            # Evaluate breakout quality near nearest zone if within 2×zone span
            bq = None
            if z_above and (z_above.level - last_price) < (z_above.span * 2):
                bq = latest_breakout_quality(_df, z_above, lookback=20)
            elif z_below and (last_price - z_below.level) < (z_below.span * 2):
                bq = latest_breakout_quality(_df, z_below, lookback=20)

            # sweeps = detect_sweeps(_df, zones, lookback=120, min_wick_ratio=1.5)  # Old function signature
            sweeps = []  # TODO: Update to use Phase 4.1 detect_sweep function

            pa_ctx = {
                "zones": [
                    {
                        "level": z.level,
                        "span": z.span,
                        "touches": z.touches,
                        "score": z.score,
                        "kind": z.kind,
                    }
                    for z in zones[:10]
                ],
                "nearest": {
                    "above": (
                        {"level": z_above.level, "span": z_above.span}
                        if z_above
                        else None
                    ),
                    "below": (
                        {"level": z_below.level, "span": z_below.span}
                        if z_below
                        else None
                    ),
                },
                "sweeps": [
                    {
                        "kind": s.kind,
                        "bar_index": s.bar_index,
                        "zone_level": s.zone_level,
                        "wick_ratio": s.wick_ratio,
                    }
                    for s in sweeps[-5:]
                ],
                "breakout_quality": bq,
                "structure_bias": struct_bias,
            }
    except Exception:
        # Keep analysis resilient; PA context is optional.
        pa_ctx = {}
        # === ANCHOR: PA20_END ===

    # === ANCHOR: FINALIZE_HELPER_START ===
    def _finalize(rec_dict: Dict[str, object]) -> Dict[str, object]:
        """
        Single post-process exit: apply S/R band rules and attach PA context and advanced features.
        """
        tech_pp = {"sr": sr, "atr_14": atr, "close": price, "session": sess}
        rec_out = apply_sr_postprocess(
            rec_dict,
            tech_pp,
            pad_sl_frac=0.15,
            pad_tp_frac=0.20,
            min_keepaway_frac=0.05,
        )
        if pa_ctx:
            rec_out["pa"] = pa_ctx
        
        # Attach advanced features in compact format for AI consumption
        if advanced_features:
            rec_out["advanced"] = {
                "rmag": rmag,
                "ema_slope": ema_slope_advanced,
                "vol_trend": vol_trend,
                "pressure": pressure,
                "candle_profile": candle_profile[-1] if candle_profile else {},
                "liquidity": liquidity,
                "fvg": fvg,
                "vwap": vwap_dev,
                "accel": accel,
                "mtf_score": mtf_score_advanced,
                "vp": vp
            }
        
        return rec_out
        # === ANCHOR: FINALIZE_HELPER_END ===

    # nearest zone context to shape triggers/guards
    sr_nearest = sr.get("nearest") or {}
    sr_kind = str(sr_nearest.get("kind") or "")
    sr_frac = float(sr_nearest.get("distance_frac_atr") or 1e9)

    if sr_kind == "SUPPORT" and sr_frac <= SR_NEAR_FRAC:
        triggers.append("near_support")
    elif sr_kind == "RESISTANCE" and sr_frac <= SR_NEAR_FRAC:
        triggers.append("near_resistance")

    # --- Geometry (wick/spike) triggers ---
    try:
        # Per-timeframe tuned thresholds; layer session overrides on top of symbol/timeframe
        if sess:
            w5, b5, bb5 = settings.get_wick_geometry_for_session(symbol, "M5", sess)
            w15, b15, bb15 = settings.get_wick_geometry_for_session(symbol, "M15", sess)
        else:
            w5, b5, bb5 = settings.get_wick_geometry_for(symbol, "M5")
            w15, b15, bb15 = settings.get_wick_geometry_for(symbol, "M15")
        # Per-symbol spike multiple (fallback to global if not overridden)
        spike_mult = float(settings.get_wick_symbol_overrides(symbol)[0])

        def _geom_flags(df, w_thr, body_max, bb_near):
            stats = (
                compute_candle_stats(df, bb_period=20, atr_period=14)
                if df is not None
                else {}
            )
            if not stats:
                return {}
            o = float(df.iloc[-1]["open"] if "open" in df.columns else df.iloc[-1]["o"])
            c = float(
                df.iloc[-1]["close"] if "close" in df.columns else df.iloc[-1]["c"]
            )
            up = stats.get("uw_frac", 0.0)
            lo = stats.get("lw_frac", 0.0)
            body = stats.get("body_frac", 0.0)
            dbu = stats.get("bb_dist_upper_frac", 1.0)
            dbl = stats.get("bb_dist_lower_frac", 1.0)
            near_upper = dbu <= float(bb_near)
            near_lower = dbl <= float(bb_near)
            spike = stats.get("rng_atr_mult", 0.0) >= float(spike_mult)
            spike_dir = "UP" if c > o else "DOWN"
            return {
                "near_upper": near_upper,
                "near_lower": near_lower,
                "wick_up": (up >= float(w_thr)) and (body <= float(body_max)),
                "wick_lo": (lo >= float(w_thr)) and (body <= float(body_max)),
                "spike": spike,
                "spike_dir": spike_dir,
            }

        geom_m5 = _geom_flags(m5_df, w5, b5, bb5)
        geom_m15 = _geom_flags(m15_df, w15, b15, bb15)

        if geom_m5:
            if geom_m5.get("wick_up") and geom_m5.get("near_upper"):
                triggers.append("m5:WICK_REJECT_UP")
            if geom_m5.get("wick_lo") and geom_m5.get("near_lower"):
                triggers.append("m5:WICK_REJECT_LO")
            if geom_m5.get("spike"):
                triggers.append(f"m5:SPIKE_{geom_m5.get('spike_dir','')}")

        if geom_m15:
            if geom_m15.get("wick_up") and geom_m15.get("near_upper"):
                triggers.append("m15:WICK_REJECT_UP")
            if geom_m15.get("wick_lo") and geom_m15.get("near_lower"):
                triggers.append("m15:WICK_REJECT_LO")
            if geom_m15.get("spike"):
                triggers.append(f"m15:SPIKE_{geom_m15.get('spike_dir','')}")
    except Exception:
        # keep analysis resilient
        pass

    # RSI alignment on M5/M15/M30
    rsi5 = _to_f(_safe("rsi_14", m5, default=_safe("rsi", m5, default=None)), None)
    if (rsi5 is None) and (m5_df is not None):
        try:
            rsi5 = _calc_rsi(m5_df, 14)
        except Exception:
            rsi5 = None
    rsi15 = _to_f(_safe("rsi_14", m15, default=_safe("rsi", m15, default=None)), None)
    if (rsi15 is None) and (m15_df is not None):
        try:
            rsi15 = _calc_rsi(m15_df, 14)
        except Exception:
            rsi15 = None
    rsi30 = _to_f(_safe("rsi_14", m30, default=_safe("rsi", m30, default=None)), None)
    r5, r15, r30 = _rsi_dir(rsi5), _rsi_dir(rsi15), _rsi_dir(rsi30)

    # H1 wick info
    try:
        o = (
            _to_f(h1.get("open")),
            _to_f(h1.get("high")),
            _to_f(h1.get("low")),
            _to_f(h1.get("close")),
        )
        up_wick, lo_wick, _ = _wick_stats(*o)
    except Exception:
        up_wick = lo_wick = 0.0

    # Side proposal from EMA/MTF
    ema_align = 1 if price >= ema200 else -1
    base_bias = mtf_bias if mtf_bias != 0 else ema_align

    # -------- STRICT SIDEWAYS MODE BLOCK --------
    if (
        (in_range or squeeze)
        and (bb_change <= 0)
        and (adx < ADX_SIDEWAYS_CUTOFF)
        and (pat_bias == 0)
    ):
        guards.append("sideways_block(BB↓, ADX<28, no_candle)")
        rec = Recommendation(
            "HOLD",
            price,
            max(0.0, price - atr),
            price + atr,
            1.0,
            "RANGE" if regime != "TREND" else regime,
            "Strict sideways block.",
            "idle",
            int(35 + 30 * mtf_score),
        ).as_dict()
        rec.update(
            {
                "mtf_label": mtf_label,
                "mtf_score": mtf_score,
                "pattern_m5": pat_m5,
                "pattern_m15": pat_m15,
                "rsi5": rsi5,
                "rsi15": rsi15,
                "rsi30": rsi30,
                "touches_hi": 0,
                "touches_lo": 0,
                "near_edge": "",
                "guards": guards,
                "triggers": triggers,
                "range_state": state,
            }
        )
        # === ANCHOR: PA20_ATTACH ===
        return _finalize(rec)
        # === ANCHOR: PA20_ATTACH_END ===

    # -------- RANGE VALIDATION & PATIENCE --------
    touches_hi = touches_lo = 0
    near_edge = ""
    if regime != "TREND" and in_range:
        if m5_df is not None and not m5_df.empty:
            closes = m5_df["close"].to_numpy(dtype=float)
            last60 = closes[-60:] if closes.size >= 60 else closes
            touches_hi = _count_touches(last60, rng_hi, price)
            touches_lo = _count_touches(last60, rng_lo, price)
        valid = (touches_hi >= RANGE_MIN_TOUCHES_EACH) and (
            touches_lo >= RANGE_MIN_TOUCHES_EACH
        )

        # establish or update patience timer
        if valid and last_ts is not None:
            if "range_started_ts" not in state:
                state["range_started_ts"] = str(last_ts)  # ISO-ish
                state["range_started_bar_index"] = int(
                    getattr(m5_df, "shape", (0, 0))[0]
                )
            # compute dwell bars since start
            try:
                start_idx = int(state.get("range_started_bar_index", 0))
                cur_idx = int(getattr(m5_df, "shape", (0, 0))[0])
                dwell_bars = max(0, cur_idx - start_idx)
            except Exception:
                dwell_bars = 0
        else:
            # if invalid range, reset patience
            state.pop("range_started_ts", None)
            state.pop("range_started_bar_index", None)
            dwell_bars = 0

        if not valid:
            guards.append("range_not_validated(touches<2)")
            rec = Recommendation(
                "HOLD",
                price,
                max(0.0, price - atr),
                price + atr,
                1.0,
                "RANGE",
                "Range not validated (need ≥2 tests of both boundaries).",
                "idle",
                int(38 + 25 * mtf_score),
            ).as_dict()
            rec.update(
                {
                    "mtf_label": mtf_label,
                    "mtf_score": mtf_score,
                    "pattern_m5": pat_m5,
                    "pattern_m15": pat_m15,
                    "rsi5": rsi5,
                    "rsi15": rsi15,
                    "rsi30": rsi30,
                    "touches_hi": touches_hi,
                    "touches_lo": touches_lo,
                    "near_edge": "",
                    "guards": guards,
                    "triggers": triggers,
                    "range_state": state,
                }
            )
            # === ANCHOR: PA20_ATTACH ===
            return _finalize(rec)
            # === ANCHOR: PA20_ATTACH_END ===

        if dwell_bars < RANGE_PATIENCE_BARS:
            guards.append(f"range_patience({dwell_bars}/{RANGE_PATIENCE_BARS} bars)")
            rec = Recommendation(
                "HOLD",
                price,
                max(0.0, price - atr),
                price + atr,
                1.0,
                "RANGE",
                "Range validated but soaking — waiting for patience timer.",
                "idle",
                int(40 + 25 * mtf_score),
            ).as_dict()
            rec.update(
                {
                    "mtf_label": mtf_label,
                    "mtf_score": mtf_score,
                    "pattern_m5": pat_m5,
                    "pattern_m15": pat_m15,
                    "rsi5": rsi5,
                    "rsi15": rsi15,
                    "rsi30": rsi30,
                    "touches_hi": touches_hi,
                    "touches_lo": touches_lo,
                    "near_edge": "",
                    "guards": guards,
                    "triggers": triggers,
                    "range_state": state,
                }
            )
            # === ANCHOR: PA20_ATTACH ===
            return _finalize(rec)
            # === ANCHOR: PA20_ATTACH_END ===

        near_edge = "upper" if abs(price - rng_hi) < abs(price - rng_lo) else "lower"

    # -------- REVERSAL INSIDE RANGE: require strong candle + RSI alignment --------
    def rsi_agrees_bearish():
        return r5 == -1 and r15 == -1 and r30 == -1

    def rsi_agrees_bullish():
        return r5 == +1 and r15 == +1 and r30 == +1

    strong_bear = pat_m5 in (
        "BEAR_ENGULF",
        "SHOOTING_STAR",
        "BEAR_MARUBOZU",
        "BEAR_PIN",
    ) or pat_m15 in ("BEAR_ENGULF", "SHOOTING_STAR", "BEAR_MARUBOZU", "BEAR_PIN")
    strong_bull = pat_m5 in (
        "BULL_ENGULF",
        "HAMMER",
        "BULL_MARUBOZU",
        "BULL_PIN",
    ) or pat_m15 in ("BULL_ENGULF", "HAMMER", "BULL_MARUBOZU", "BULL_PIN")

    if in_range:
        if near_edge == "upper":
            if not (strong_bear and rsi_agrees_bearish()):
                guards.append("range_upper_no_confirm")
                rec = Recommendation(
                    "HOLD",
                    price,
                    max(0.0, price - atr),
                    price + atr,
                    1.0,
                    "RANGE",
                    "Upper range edge but no strong bearish confirmation + RSI alignment.",
                    "mean_reversion",
                    int(40 + 25 * mtf_score),
                ).as_dict()
                rec.update(
                    {
                        "mtf_label": mtf_label,
                        "mtf_score": mtf_score,
                        "pattern_m5": pat_m5,
                        "pattern_m15": pat_m15,
                        "rsi5": rsi5,
                        "rsi15": rsi15,
                        "rsi30": rsi30,
                        "touches_hi": touches_hi,
                        "touches_lo": touches_lo,
                        "near_edge": near_edge,
                        "guards": guards,
                        "triggers": triggers,
                        "range_state": state,
                    }
                )
                # === ANCHOR: PA20_ATTACH ===
                return _finalize(rec)
                # === ANCHOR: PA20_ATTACH_END ===

            direction = "SELL"
            triggers.append("range_upper_confirmed")
        else:
            if not (strong_bull and rsi_agrees_bullish()):
                guards.append("range_lower_no_confirm")
                rec = Recommendation(
                    "HOLD",
                    price,
                    max(0.0, price - atr),
                    price + atr,
                    1.0,
                    "RANGE",
                    "Lower range edge but no strong bullish confirmation + RSI alignment.",
                    "mean_reversion",
                    int(40 + 25 * mtf_score),
                ).as_dict()
                rec.update(
                    {
                        "mtf_label": mtf_label,
                        "mtf_score": mtf_score,
                        "pattern_m5": pat_m5,
                        "pattern_m15": pat_m15,
                        "rsi5": rsi5,
                        "rsi15": rsi15,
                        "rsi30": rsi30,
                        "touches_hi": touches_hi,
                        "touches_lo": touches_lo,
                        "near_edge": near_edge,
                        "guards": guards,
                        "triggers": triggers,
                        "range_state": state,
                    }
                )
                # === ANCHOR: PA20_ATTACH ===
                return _finalize(rec)
                # === ANCHOR: PA20_ATTACH_END ===

            direction = "BUY"
            triggers.append("range_lower_confirmed")

        # Levels for MR (seed with ATR/range edges)
        sl = (
            price - RANGE_SL_MULT * atr
            if direction == "BUY"
            else price + RANGE_SL_MULT * atr
        )
        tp = (
            min(rng_hi, price + RANGE_TP_MULT * atr)
            if direction == "BUY"
            else max(rng_lo, price - RANGE_TP_MULT * atr)
        )

        rec = Recommendation(
            direction,
            price,
            sl,
            tp,
            _rr(price, sl, tp),
            "RANGE",
            "Range mean-reversion with strong candle + RSI alignment.",
            "mean_reversion",
            int(55 + 30 * mtf_score),
        ).as_dict()
        rec.update(
            {
                "mtf_label": mtf_label,
                "mtf_score": mtf_score,
                "pattern_m5": pat_m5,
                "pattern_m15": pat_m15,
                "rsi5": rsi5,
                "rsi15": rsi15,
                "rsi30": rsi30,
                "touches_hi": touches_hi,
                "touches_lo": touches_lo,
                "near_edge": near_edge,
                "guards": guards,
                "triggers": triggers,
                "range_state": state,
            }
        )
        # === ANCHOR: PA20_ATTACH ===
        return _finalize(rec)
        # === ANCHOR: PA20_ATTACH_END ===

    # -------- TREND path --------
    if regime == "TREND":
        if mtf_score < 0.45 or abs(micro_roc) < MICRO_ROC:
            guards.append("trend_weak_confirmation")
            rec = Recommendation(
                "HOLD",
                price,
                max(0.0, price - atr),
                price + atr,
                1.0,
                "TREND",
                "Trend regime but confirmation weak (MTF or micro momentum).",
                "trend_pullback",
                int(40 + 40 * mtf_score),
            ).as_dict()
            rec.update(
                {
                    "mtf_label": mtf_label,
                    "mtf_score": mtf_score,
                    "pattern_m5": pat_m5,
                    "pattern_m15": pat_m15,
                    "rsi5": rsi5,
                    "rsi15": rsi15,
                    "rsi30": rsi30,
                    "touches_hi": touches_hi,
                    "touches_lo": touches_lo,
                    "near_edge": "",
                    "guards": guards,
                    "triggers": triggers,
                    "range_state": state,
                }
            )
            # === ANCHOR: PA20_ATTACH ===
            return _finalize(rec)
            # === ANCHOR: PA20_ATTACH_END ===

        # IMPROVED: Better trend direction logic with timeframe priority
        direction = _determine_trend_direction(m5, m15, m30, h1, price, ema200, mtf_bias, rsi5, rsi15, rsi30)
        sl = (
            price - TREND_SL_MULT * atr
            if direction == "BUY"
            else price + TREND_SL_MULT * atr
        )
        tp = (
            price + TREND_TP_MULT * atr
            if direction == "BUY"
            else price - TREND_TP_MULT * atr
        )

        triggers.append("trend_ok")
        rec = Recommendation(
            direction,
            price,
            sl,
            tp,
            _rr(price, sl, tp),
            "TREND",
            f"Trend with MTF={mtf_label}, microROC={micro_roc:.4f}.",
            "trend_pullback",
            int(55 + 35 * mtf_score),
        ).as_dict()
        rec.update(
            {
                "mtf_label": mtf_label,
                "mtf_score": mtf_score,
                "pattern_m5": pat_m5,
                "pattern_m15": pat_m15,
                "rsi5": rsi5,
                "rsi15": rsi15,
                "rsi30": rsi30,
                "touches_hi": touches_hi,
                "touches_lo": touches_lo,
                "near_edge": "",
                "guards": guards,
                "triggers": triggers,
                "range_state": state,
            }
        )

        # === ANCHOR: PA20_ATTACH ===
        return _finalize(rec)
        # === ANCHOR: PA20_ATTACH_END ===

    # -------- PHASE 4.4.4: OCO BRACKETS for consolidation --------
    # Check if OCO brackets are suitable (before breakout)
    try:
        from config import settings
        from infra.oco_brackets import calculate_oco_bracket
        
        if settings.USE_OCO_BRACKETS and regime != "TREND":
            # Get session for OCO validation
            session_str = sess if sess else "UNKNOWN"
            
            # Prepare features for OCO detection
            oco_features = {
                "adx_14": adx,
                "bb_width": bbw,
                "recent_highs": [],  # Will be populated if m5_df available
                "recent_lows": [],
                "close": price,
                "spread_atr_pct": _to_f(_safe("spread_atr_pct", m5), 0.15),
                "has_pending_orders": False,  # TODO: query from MT5
                "news_blackout": _safe("news_blackout", m5, default=False)
            }
            
            # Extract recent highs/lows from m5_df if available
            if m5_df is not None and not m5_df.empty and len(m5_df) >= 20:
                try:
                    recent_data = m5_df.tail(20)
                    oco_features["recent_highs"] = recent_data["high"].tolist()
                    oco_features["recent_lows"] = recent_data["low"].tolist()
                except Exception:
                    pass
            
            # Calculate OCO bracket
            oco_result = calculate_oco_bracket(
                features=oco_features,
                atr=atr,
                session=session_str,
                symbol=symbol
            )
            
            if oco_result.is_valid:
                # OCO bracket is suitable - return both orders
                logger.info(f"OCO bracket detected for {symbol}: {oco_result.rationale}")
                
                # FIXED Bug #2: Convert OCO bracket to oco_companion format expected by handlers/trading.py
                rec = Recommendation(
                    "BUY",  # Primary leg direction (will be BUY STOP)
                    oco_result.buy_stop,  # Primary entry
                    oco_result.buy_sl,  # Primary SL
                    oco_result.buy_tp,  # Primary TP
                    oco_result.buy_rr,  # Primary RR
                    "CONSOLIDATION",
                    oco_result.rationale,
                    "oco_bracket",
                    int(45 + 25 * mtf_score),
                ).as_dict()
                
                # Add OCO-specific fields + oco_companion for trading handler
                rec.update({
                    "oco_bracket": True,
                    "pending_type": "OCO_STOP",  # Signal this is an OCO order
                    "order_side": "buy",  # Primary leg
                    # Primary leg (BUY STOP)
                    "buy_stop": oco_result.buy_stop,
                    "buy_sl": oco_result.buy_sl,
                    "buy_tp": oco_result.buy_tp,
                    "buy_rr": oco_result.buy_rr,
                    # Secondary leg (SELL STOP)
                    "sell_stop": oco_result.sell_stop,
                    "sell_sl": oco_result.sell_sl,
                    "sell_tp": oco_result.sell_tp,
                    "sell_rr": oco_result.sell_rr,
                    # CRITICAL: Add oco_companion dict expected by _place_oco_breakout
                    "oco_companion": {
                        "direction": "SELL",
                        "order_side": "sell",
                        "entry": oco_result.sell_stop,
                        "sl": oco_result.sell_sl,
                        "tp": oco_result.sell_tp,
                        "rr": oco_result.sell_rr
                    },
                    # Metadata
                    "range_high": oco_result.range_high,
                    "range_low": oco_result.range_low,
                    "expiry_minutes": oco_result.expiry_minutes,
                    "consolidation_confidence": oco_result.consolidation_confidence,
                    "mtf_label": mtf_label,
                    "mtf_score": mtf_score,
                    "pattern_m5": pat_m5,
                    "pattern_m15": pat_m15,
                    "rsi5": rsi5,
                    "rsi15": rsi15,
                    "rsi30": rsi30,
                    "touches_hi": touches_hi if in_range else 0,
                    "touches_lo": touches_lo if in_range else 0,
                    "near_edge": "",
                    "guards": guards,
                    "triggers": triggers + ["oco_consolidation"],
                    "range_state": state,
                })
                
                # === ANCHOR: PA20_ATTACH ===
                return _finalize(rec)
                # === ANCHOR: PA20_ATTACH_END ===
            else:
                # OCO not suitable, log reasons and continue to regular breakout logic
                if oco_result.skip_reasons:
                    logger.debug(f"OCO bracket skipped for {symbol}: {oco_result.skip_reasons[0]}")
    
    except Exception as e:
        logger.warning(f"OCO bracket calculation failed for {symbol}: {e}")
        # Continue to regular breakout logic
    
    # -------- VOLATILE → breakout --------
    breakout_up = price > rng_hi + 0.1 * atr
    breakout_down = price < rng_lo - 0.1 * atr
    if breakout_up or breakout_down:
        direction = "BUY" if breakout_up else "SELL"
        ok_rsi = (_rsi_dir(rsi5) == (1 if breakout_up else -1)) and (
            _rsi_dir(rsi15) == _rsi_dir(rsi5) or _rsi_dir(rsi30) == _rsi_dir(rsi5)
        )
        if ok_rsi or mtf_score >= 0.45 or pat_bias != 0:
            sl = (
                price - VOL_SL_MULT * atr
                if direction == "BUY"
                else price + VOL_SL_MULT * atr
            )
            tp = (
                price + VOL_TP_MULT * atr
                if direction == "BUY"
                else price - VOL_TP_MULT * atr
            )

            triggers.append("breakout_confirmed")
            rec = Recommendation(
                direction,
                price,
                sl,
                tp,
                _rr(price, sl, tp),
                "VOLATILE",
                f"Breakout {'up' if breakout_up else 'down'} with RSI/MTF support.",
                "breakout",
                int(52 + 30 * mtf_score),
            ).as_dict()
            rec.update(
                {
                    "mtf_label": mtf_label,
                    "mtf_score": mtf_score,
                    "pattern_m5": pat_m5,
                    "pattern_m15": pat_m15,
                    "rsi5": rsi5,
                    "rsi15": rsi15,
                    "rsi30": rsi30,
                    "touches_hi": touches_hi,
                    "touches_lo": touches_lo,
                    "near_edge": "",
                    "guards": guards,
                    "triggers": triggers,
                    "range_state": state,
                }
            )

            # === ANCHOR: PA20_ATTACH ===
            return _finalize(rec)
            # === ANCHOR: PA20_ATTACH_END ===

    # default: stand aside
    guards.append("no_setup")
    rec = Recommendation(
        "HOLD",
        price,
        max(0.0, price - atr),
        price + atr,
        1.0,
        regime,
        "No high-quality setup after strict filters.",
        "idle",
        int(35 + 30 * mtf_score),
    ).as_dict()
    rec.update(
        {
            "mtf_label": mtf_label,
            "mtf_score": mtf_score,
            "pattern_m5": pat_m5,
            "pattern_m15": pat_m15,
            "rsi5": rsi5,
            "rsi15": rsi15,
            "rsi30": rsi30,
            "touches_hi": touches_hi,
            "touches_lo": touches_lo,
            "near_edge": "",
            "guards": guards,
            "triggers": triggers,
            "range_state": state,
        }
    )
    # === ANCHOR: PA20_ATTACH ===
    return _finalize(rec)
    # === ANCHOR: PA20_ATTACH_END ===
