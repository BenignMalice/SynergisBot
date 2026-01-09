# app/engine/regime_classifier.py
from __future__ import annotations
from typing import Dict, Any, Tuple, Optional
from pathlib import Path
import json
import logging

logger = logging.getLogger("app.engine.regime_classifier")
logger.setLevel(logging.DEBUG)
logger.propagate = True


# ------- tolerant getters (mirror style used elsewhere) -------
def _safe_f(x, d=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(d)


def _get(tech: Dict[str, Any], tf: str | None, names: list[str]) -> float:
    containers = []
    if tf:
        containers += [
            tech.get(tf) or {},
            tech.get(f"_tf_{tf}") or {},
            tech.get(tf.upper()) or {},
        ]
    containers += [tech]
    for nm in names:
        for c in containers:
            if not isinstance(c, dict):
                continue
            v = c.get(nm)
            if v is None:
                continue
            try:
                return float(v)
            except Exception:
                try:
                    return float(str(v).replace(",", ""))
                except Exception:
                    continue
    return 0.0


def _adx(tech, tf="M15"):
    return _get(tech, tf, ["adx", "ADX", "adx_14", "ADX_14"])


def _atr(tech, tf="M15"):
    return _get(tech, tf, ["atr_14", "ATR_14", "atr14", "ATR14"])


def _bbw(tech, tf="M15"):
    return _get(tech, tf, ["bb_width", "BBWidth", "bbwidth"])


def _ema(tech, tf, n):
    return _get(tech, tf, [f"ema_{n}", f"EMA_{n}", f"ema{n}", f"EMA{n}"])


def _slope200(tech, tf="H1"):
    # Accept either dedicated slope fields or a generic slope; values are model-dependent, treated as signed strength
    return _get(
        tech,
        tf,
        [
            "ema_slope_h1",
            "EMA_SLOPE_H1",
            "ema200_slope",
            "EMA200_SLOPE",
            "slope_ema200",
        ],
    )


def _ret_std(tech, tf="M15"):
    return _get(tech, tf, ["ret_std", "RET_STD"])  # optional if you have it


def _session(tech) -> str:
    return str(tech.get("session") or "").upper()


def _price(tech) -> float:
    p = _get(tech, None, ["last", "close", "price"])
    if p:
        return p
    bid = _get(tech, None, ["bid", "Bid", "BID"])
    ask = _get(tech, None, ["ask", "Ask", "ASK"])
    return (bid + ask) / 2.0 if bid and ask else 0.0


# ------- strategy map loader (optional SSOT) -------
_STRAT_MAP_CACHE: Optional[dict] = None


def _load_strategy_map() -> dict:
    """Try infra.strategy_map.get_strategy_map(); else app/config/strategy_map.json; else {}."""
    global _STRAT_MAP_CACHE
    if _STRAT_MAP_CACHE is not None:
        return _STRAT_MAP_CACHE
    try:
        from infra.strategy_map import get_strategy_map  # type: ignore

        m = get_strategy_map()
        if isinstance(m, dict):
            _STRAT_MAP_CACHE = m
            return m
    except Exception:
        pass
    # file fallback
    try:
        here = Path(__file__).resolve()
        cfg = (
            here.parent.parent / "config" / "strategy_map.json"
        )  # app/engine -> app/config
        if not cfg.exists():
            alt = Path.cwd() / "app" / "config" / "strategy_map.json"
            cfg = alt if alt.exists() else cfg
        if cfg.exists():
            _STRAT_MAP_CACHE = json.loads(cfg.read_text(encoding="utf-8") or "{}")
            return _STRAT_MAP_CACHE
    except Exception as e:
        logger.debug("regime_classifier: strategy_map load failed: %s", e)
    _STRAT_MAP_CACHE = {}
    return {}


def _detect_timeframe_conflict(adx_m5: float, adx_m15: float, adx_h1: float, adx_trend_gate: float) -> bool:
    """
    IMPROVED: Detect when timeframes show conflicting trend signals.
    Returns True if there's significant conflict between timeframes.
    """
    # Count timeframes above trend gate
    tf_above_gate = sum([
        adx_m5 > adx_trend_gate,
        adx_m15 > adx_trend_gate, 
        adx_h1 > adx_trend_gate
    ])
    
    # Conflict exists if only 1 or 2 timeframes show trend (not 0 or 3)
    return tf_above_gate in (1, 2)


def _regime_cfg(profile: dict | None, sess: str) -> dict:
    """
    Merge defaults <- strategy_map['regime'] <- profile['regime'] <- session_overrides.
    Safe if any layer missing.
    """
    defaults = {
        "adx_trend_gate": 35.0,
        "adx_range_low": 25.0,
        "bb_squeeze": 0.012,  # narrower = more "range"
        "vol_wide": 0.020,  # wider = more "volatile"
        "adx_cap": 50.0,
        "confident_gate": 0.48,
        "hysteresis_bonus": 0.05,
        "smooth_alpha": 0.30,  # if prev_scores provided
        # session nudges (additive before normalization)
        "session_nudges": {
            "LONDON": {"trend": 0.05, "volatile": 0.03, "range": 0.00},
            "NEWYORK": {"trend": 0.05, "volatile": 0.03, "range": 0.00},
            "ASIA": {"trend": 0.00, "volatile": 0.00, "range": 0.05},
        },
        # Optional news-based volatile bump
        "news_vol_boost_min": 30,  # minutes
        "news_vol_boost": 0.05,
    }

    mp = _load_strategy_map()
    strat_regime = (mp.get("regime") or {}) if isinstance(mp, dict) else {}
    prof_regime = (profile or {}).get("regime", {}) if isinstance(profile, dict) else {}

    cfg = {**defaults, **strat_regime, **prof_regime}

    # session overrides (if present)
    so = cfg.get("session_overrides") or {}
    if isinstance(so, dict):
        s_cfg = so.get(sess) or {}
        if isinstance(s_cfg, dict):
            cfg.update({k: v for k, v in s_cfg.items() if v is not None})

    return cfg


# ------- core classifier -------
def classify_regime(
    tech: dict, prev_regime: str | None = None, profile: dict | None = None
) -> Tuple[str, Dict[str, float]]:
    """
    Return (label, scores) where label in {"TREND","RANGE","VOLATILE"}
    and scores = {"trend": x, "range": y, "volatile": z} for telemetry.

    Improvements:
    - Strategy-map aware thresholds (app/config/strategy_map.json or infra.strategy_map)
    - Session nudges (configurable)
    - Optional smoothing using profile['prev_scores'] or tech['prev_scores']
    - News proximity bump to volatile if within 'news_vol_boost_min'
    """
    sess = _session(tech)
    cfg = _regime_cfg(profile, sess)

    adx_cap = _safe_f(cfg.get("adx_cap"), 50.0)
    adx_trend_gate = _safe_f(cfg.get("adx_trend_gate"), 35.0)
    adx_range_low = _safe_f(cfg.get("adx_range_low"), 25.0)
    bb_squeeze = _safe_f(cfg.get("bb_squeeze"), 0.012)
    vol_wide = _safe_f(cfg.get("vol_wide"), 0.020)
    confident_gate = _safe_f(cfg.get("confident_gate"), 0.48)
    hyst_bonus = _safe_f(cfg.get("hysteresis_bonus"), 0.05)
    smooth_alpha = _safe_f(cfg.get("smooth_alpha"), 0.30)
    session_nudges = cfg.get("session_nudges") or {}
    news_min = int(cfg.get("news_vol_boost_min", 30))
    news_boost = _safe_f(cfg.get("news_vol_boost"), 0.05)

    # --- read inputs across TFs ---
    adx_m5, adx_m15, adx_h1 = _adx(tech, "M5"), _adx(tech, "M15"), _adx(tech, "H1")
    bbw_m5, bbw_m15, bbw_h1 = _bbw(tech, "M5"), _bbw(tech, "M15"), _bbw(tech, "H1")
    atr_m15, atr_h1 = _atr(tech, "M15"), _atr(tech, "H1")
    slope_h1 = _slope200(tech, "H1")

    ema200_m15 = _ema(tech, "M15", 200) or 0.0
    px = _price(tech)

    # --- IMPROVED trend score with timeframe conflict detection ---
    # Blend ADX across TFs and normalize
    adx_mix = (0.20 * adx_m5) + (0.50 * adx_m15) + (0.30 * adx_h1)
    adx_norm = min(1.0, max(0.0, adx_mix / max(1e-9, adx_cap)))

    # IMPROVED: Detect timeframe conflicts
    tf_conflict = _detect_timeframe_conflict(adx_m5, adx_m15, adx_h1, adx_trend_gate)
    conflict_penalty = 0.3 if tf_conflict else 0.0

    # Alignment: price vs EMA200 + slope agreement
    if ema200_m15 > 0.0 and px > 0.0:
        align_flag = 1.0  # EMA200 present and comparable
        slope_agrees = (
            1.0
            if (
                (px >= ema200_m15 and slope_h1 >= 0)
                or (px < ema200_m15 and slope_h1 <= 0)
            )
            else 0.0
        )
    else:
        align_flag = 0.7  # weaker confidence if EMA missing
        slope_agrees = 1.0 if slope_h1 != 0 else 0.0

    # IMPROVED: Apply conflict penalty to trend score
    trend_score = (0.60 * adx_norm) + (0.25 * slope_agrees) + (0.15 * align_flag) - conflict_penalty

    # --- range score ---
    # Low ADX + squeeze (narrow bands)
    bbw_ref = bbw_m15 if bbw_m15 > 0 else (bbw_h1 or bbw_m5)
    low_adx_component = 1.0 - min(adx_m15, adx_range_low) / max(1e-9, adx_range_low)
    squeeze_component = max(
        0.0, (bb_squeeze - (bbw_ref or 0.0)) / max(1e-9, bb_squeeze)
    )
    range_score = (0.60 * max(0.0, low_adx_component)) + (0.40 * squeeze_component)

    # --- volatile score ---
    # Wide bands + mid ADX (20–30) + TF disagreement
    bbw_wide_component = min(1.0, (bbw_ref or 0.0) / max(1e-9, vol_wide))
    adx_mid = max(
        0.0, min(1.0, (min(max(adx_m15, 20.0), 30.0) - 20.0) / 10.0)
    )  # 0..1 when 20..30
    # Disagreement: count of TFs above trend gate neither 0 nor 3
    tf_above = (
        int(adx_m5 > adx_trend_gate)
        + int(adx_m15 > adx_trend_gate)
        + int(adx_h1 > adx_trend_gate)
    )
    disagree_bonus = 0.20 if tf_above in (1, 2) else 0.0
    volatile_score = (0.60 * bbw_wide_component) + (0.25 * adx_mid) + (disagree_bonus)

    # --- session nudges (additive pre-normalization) ---
    sess_nudge = (
        (session_nudges.get(sess) or {}) if isinstance(session_nudges, dict) else {}
    )
    trend_score += _safe_f(sess_nudge.get("trend"), 0.0)
    range_score += _safe_f(sess_nudge.get("range"), 0.0)
    volatile_score += _safe_f(sess_nudge.get("volatile"), 0.0)

    # --- news proximity bump (optional) ---
    try:
        mins_to_news = int(tech.get("minutes_to_next_news") or 999)
        if mins_to_news < news_min:
            volatile_score += news_boost
    except Exception:
        pass

    # --- optional smoothing from previous scores (profile or tech) ---
    prev_scores = None
    if isinstance(profile, dict):
        prev_scores = profile.get("prev_scores")
    if prev_scores is None and isinstance(tech, dict):
        prev_scores = tech.get("prev_scores")

    if isinstance(prev_scores, dict):
        # EMA smoothing: new = a*new + (1-a)*old
        ps_trend = _safe_f(prev_scores.get("trend"), 0.0)
        ps_range = _safe_f(prev_scores.get("range"), 0.0)
        ps_vol = _safe_f(prev_scores.get("volatile"), 0.0)
        a = max(0.0, min(1.0, smooth_alpha))
        trend_score = (a * trend_score) + ((1 - a) * ps_trend)
        range_score = (a * range_score) + ((1 - a) * ps_range)
        volatile_score = (a * volatile_score) + ((1 - a) * ps_vol)

    # --- softmax-like normalization (safe if all zeros) ---
    ssum = max(1e-9, trend_score + range_score + volatile_score)
    trend_p, range_p, vol_p = (
        trend_score / ssum,
        range_score / ssum,
        volatile_score / ssum,
    )

    # --- hysteresis: bias toward previous label to reduce churn ---
    if prev_regime == "TREND":
        trend_p += hyst_bonus
    elif prev_regime == "RANGE":
        range_p += hyst_bonus
    elif prev_regime == "VOLATILE":
        vol_p += hyst_bonus

    # clamp and re-normalize
    trend_p = max(0.0, min(1.0, trend_p))
    range_p = max(0.0, min(1.0, range_p))
    vol_p = max(0.0, min(1.0, vol_p))
    ssum = max(1e-9, trend_p + range_p + vol_p)
    trend_p, range_p, vol_p = trend_p / ssum, range_p / ssum, vol_p / ssum

    # --- decision thresholds (two-stage) ---
    mx = max(trend_p, range_p, vol_p)
    if mx >= confident_gate:
        label = "TREND" if mx == trend_p else ("RANGE" if mx == range_p else "VOLATILE")
    else:
        # borderline fallback: prefer RANGE when ADX very low & squeeze, else VOL if very wide bands, else TREND
        if adx_m15 < (adx_range_low - 7) and (bbw_m15 or 0.0) < bb_squeeze:
            label = "RANGE"
        elif (bbw_m15 or 0.0) > vol_wide:
            label = "VOLATILE"
        else:
            label = "TREND"

    scores = {
        "trend": round(float(trend_p), 4),
        "range": round(float(range_p), 4),
        "volatile": round(float(vol_p), 4),
    }
    return label, scores
