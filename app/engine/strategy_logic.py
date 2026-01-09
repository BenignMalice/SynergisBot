# =====================================
# app/engine/strategy_logic.py
# =====================================
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple, Literal
from pathlib import Path
import json
import logging
from copy import deepcopy

from config import settings

logger = logging.getLogger("app.engine.strategy_logic")
logger.setLevel(logging.DEBUG)
logger.propagate = True
logger.info(
    "strategy_logic imported as %s, eff=%s",
    __name__,
    logging.getLevelName(logger.getEffectiveLevel()),
)
print(
    f"[PRINT] strategy_logic import, logger eff={logging.getLevelName(logger.getEffectiveLevel())}"
)

# === MULTI-TIMEFRAME CONFLUENCE ==============================================
def compute_mtf_confluence(tech: dict) -> dict:
    """
    Safe, dependency-light multi-timeframe confluence summariser.
    Expects a `tech` dict with nested per-timeframe blobs like `_tf_M5`, `_tf_M15`, `_tf_H1`.
    Returns: {"score": 0..1, "bias": "bull"/"bear"/None, "details": {...}}
    """
    def _blob(t: dict, tf: str) -> dict:
        if not isinstance(t, dict):
            return {}
        return (t.get(f"_tf_{tf}") or t.get(tf) or {}) if isinstance(t.get(f"_tf_{tf}") or t.get(tf), dict) else {}

    m5 = _blob(tech, "M5")
    m15 = _blob(tech, "M15")
    h1 = _blob(tech, "H1")

    def _ema_bias(d: dict) -> int:
        if not isinstance(d, dict) or not d:
            return 0
        e20 = d.get("ema_20"); e50 = d.get("ema_50"); e200 = d.get("ema_200")
        price = d.get("close") or d.get("price") or d.get("last")
        try:
            bull = all(x is not None for x in (e20, e50, e200, price)) and (e20 > e50 > e200) and (price > e20)
            bear = all(x is not None for x in (e20, e50, e200, price)) and (e20 < e50 < e200) and (price < e20)
        except Exception:
            return 0
        return 1 if bull else (-1 if bear else 0)

    ema_scores = [_ema_bias(x) for x in (m5, m15, h1) if isinstance(x, dict)]
    ema_sum = sum(ema_scores)
    ema_align = ema_sum >= 2 or ema_sum <= -2
    ema_partial = not ema_align and ema_sum != 0

    adx_m15 = 0.0
    try:
        if isinstance(m15, dict):
            adx_m15 = float(m15.get("adx") or m15.get("adx_14") or 0.0)
    except Exception:
        adx_m15 = 0.0
    strong = adx_m15 >= 25.0

    bias = "bull" if ema_sum > 0 else ("bear" if ema_sum < 0 else None)
    base = 0.4 if ema_align else (0.2 if ema_partial else 0.0)
    base += 0.3 if strong else 0.0
    score = max(0.0, min(1.0, base))

    details = {"ema_align": bool(ema_align), "ema_partial": bool(ema_partial), "adx_m15": adx_m15}
    return {"score": float(score), "bias": bias, "details": details}


# === Legacy-safe helper shims (to satisfy older strategy calls) ==================
def _tf_blob(tech: dict, tf: str) -> dict:
    try:
        b = tech.get(f"_tf_{tf}") or tech.get(tf) or {}
        return b if isinstance(b, dict) else {}
    except Exception:
        return {}

def _ema(tech: dict, tf: str | None, period: int) -> float | None:
    """
    Return EMA(period) from the given timeframe blob when available, else from top-level.
    """
    try:
        key = f"ema_{int(period)}"
        if tf:
            d = _tf_blob(tech, tf)
            v = d.get(key) if isinstance(d, dict) else None
            if v is not None:
                return float(v)
        v = tech.get(key)
        return float(v) if v is not None else None
    except Exception:
        return None

def _adx(tech: dict) -> float:
    """
    Fallback ADX accessor (prefers M15 blob, then top-level). Default 0.0.
    """
    try:
        d = _tf_blob(tech, "M15")
        v = (d.get("adx") if isinstance(d, dict) else None) or tech.get("adx") or tech.get("adx_14")
        return float(v) if v is not None else 0.0
    except Exception:
        return 0.0

def _atr(tech: dict, tf: str = "M15", period: int = 14) -> float | None:
    try:
        d = _tf_blob(tech, tf)
        v = (d.get(f"atr_{int(period)}") if isinstance(d, dict) else None) or tech.get(f"atr_{int(period)}")
        return float(v) if v is not None else None
    except Exception:
        return None

def _bb_width(tech: dict, tf: str = "M15") -> float | None:
    try:
        d = _tf_blob(tech, tf)
        v = (d.get("bb_width") if isinstance(d, dict) else None) or tech.get("bb_width")
        return float(v) if v is not None else None
    except Exception:
        return None


# === PHASE2_GATES: global gating (MTF align, ADX thresholds, breakout retest, reversal confirmations) ===
def _phase2_strategy_kind(name: str) -> str:
    """Return 'trend' | 'range' | 'reversal' heuristic from strategy name."""
    nm = (name or "").lower()
    if any(k in nm for k in ("reversal", "double", "hs_")):
        return "reversal"
    if any(k in nm for k in ("range", "fade", "mean_reversion")):
        return "range"
    # default: treat as trend/breakout
    return "trend"

def _phase2_supports_reversal(tech: dict, direction_long: bool) -> int:
    """
    Return a count of reversal confirmations present in tech.
    We approximate 2-of-3 using available fields:
      - Candlestick pattern on M5 (HAMMER/SHOOTING_STAR/ENGULF)
      - pattern_bias sign (from M5)
      - Low ADX (<= ADX_THRESH['range']) as a proxy for exhaustion
    """
    try:
        patt = str(tech.get("pattern_m5") or "").upper()
        bias = int(tech.get("pattern_bias") or 0)
        adx = float(_adx(tech))
        want = 1 if direction_long else -1
        cnt = 0
        if patt in ("HAMMER", "SHOOTING_STAR", "BULL_ENGULF", "BEAR_ENGULF", "MORNING_STAR", "EVENING_STAR"):
            # Check if pattern direction makes sense for our side
            if ("BULL" in patt and direction_long) or ("BEAR" in patt and not direction_long) or patt in ("HAMMER","SHOOTING_STAR","MORNING_STAR","EVENING_STAR"):
                cnt += 1
        if bias == want:
            cnt += 1
        # Low ADX supports mean-reversion/reversal environment
        try:
            thr = float(getattr(settings, "ADX_THRESH", {}).get("range", 20.0))
        except Exception:
            thr = 20.0
        if adx <= thr + 1e-6:
            cnt += 1
        return cnt
    except Exception:
        return 0

def _phase2_apply_gates(plan: "StrategyPlan", tech: dict, mode: str = "pending") -> "StrategyPlan":
    try:
        name = getattr(plan, "strategy", "") or ""
        kind = _phase2_strategy_kind(name)
        adx = float(_adx(tech))
        # MTF confluence
        conf = compute_mtf_confluence(tech) if callable(compute_mtf_confluence) else {"score": 0.0, "bias": None, "details": {}}
        details = conf.get("details") or {}
        bias = (conf.get("bias") or "").lower()
        # Determine plan side
        d = (getattr(plan, "direction", "") or "").upper()
        long_side = (d in ("LONG", "BUY"))
        short_side = (d in ("SHORT", "SELL"))
        # Settings
        try:
            need_align = bool(getattr(settings, "MTF_ALIGN", {}).get("require_align", True))
            adx_trend = float(getattr(settings, "ADX_THRESH", {}).get("trend", 25.0))
            adx_range = float(getattr(settings, "ADX_THRESH", {}).get("range", 20.0))
            need_close_retest = bool(getattr(settings, "PENDING_RULES", {}).get("breakout_requires_close_retest", True))
        except Exception:
            need_align, adx_trend, adx_range, need_close_retest = True, 25.0, 20.0, True

        blocked = list(getattr(plan, "blocked_by", []) or [])
        preview = bool(getattr(plan, "preview_only", False))

        # 1) MTF align gate
        if need_align:
            # If bias known, require consistency with direction; else use ema_align flag when available
            align_ok = True
            if bias in ("bull", "bear"):
                if (bias == "bull" and not long_side) or (bias == "bear" and not short_side):
                    align_ok = False
            elif isinstance(details, dict) and isinstance(details.get("ema_align"), bool):
                if not details.get("ema_align"):
                    align_ok = False
            if not align_ok:
                blocked.append("mtf_misaligned")
                preview = True

        # 2) ADX regime gate
        if kind == "trend":
            if adx < adx_trend:
                blocked.append(f"adx<{adx_trend}")
                preview = True
        elif kind == "range":
            if adx > adx_range:
                blocked.append(f"adx>{adx_range}")
                preview = True
        else:  # reversal
            # require 2-of-3 confirmations if configured
            if bool(getattr(settings, "REVERSAL_2OF3", True)):
                cnt = _phase2_supports_reversal(tech, direction_long=long_side)
                if cnt < 2:
                    blocked.append("reversal_confirmations<2")
                    preview = True

        # 3) Breakout close+retest enforcement for market mode
        if mode == "market" and need_close_retest and "breakout" in name.lower():
            # We only allow MARKET if an explicit retest flag is present and confirmed true on tech/patterns.
            patt = tech.get("patterns") or tech.get("pattern") or {}
            ret_ok = False
            try:
                # Accept either explicit boolean or geometry where entry equals retest_level and last close beyond break
                if isinstance(patt, dict) and (patt.get("retest_confirmed") or patt.get("close_beyond_confirmed")):
                    ret_ok = True
                else:
                    # Weak heuristic: if price is beyond break level and plan entry equals stored retest_level
                    brk = float(patt.get("break_level") or 0.0)
                    ret = float(patt.get("retest_level") or 0.0)
                    if ret and getattr(plan, "entry", None) is not None:
                        try:
                            e = float(plan.entry)
                            ret_ok = (abs(e - ret) <= max(1e-9, 0.0000001))
                        except Exception:
                            ret_ok = False
            except Exception:
                ret_ok = False
            if not ret_ok:
                blocked.append("needs_close_retest")
                preview = True

        # Apply to plan and return
        plan.blocked_by = sorted(set([b for b in blocked if b]))
        plan.preview_only = bool(preview)
        return plan
    except Exception:
        return plan
def _calc_rr(side: str, entry: float, sl: float, tp: float) -> float | None:
    try:
        side = str(side).upper()
        entry = float(entry); sl = float(sl); tp = float(tp)
        if side in ("BUY", "LONG"):
            risk = entry - sl
            reward = tp - entry
        else:
            risk = sl - entry
            reward = entry - tp
        if risk <= 0:
            return None
        return round(reward / risk, 2)
    except Exception:
        return None

def _streak_boost(*args, **kwargs) -> float:
    # Conservative default until risk_model wiring is engaged.
    return 1.0

def _price(tech: dict, tf: str | None = None) -> float | None:
    """
    Return a reasonable 'price' reference:
    - If tf provided, try that blob's 'close' first.
    - Else use top-level 'close' or 'price' or 'last'.
    """
    try:
        if tf:
            d = _tf_blob(tech, tf)
            v = (d.get("close") if isinstance(d, dict) else None)
            if v is not None:
                return float(v)
        for k in ("close", "price", "last"):
            v = tech.get(k)
            if v is not None:
                return float(v)
    except Exception:
        return None
    return None

def _pending_type_from_entry(side: str, entry: float, price_now: float | None, tol: float | None = None) -> str:
    """
    Infer pending order type from side + entry vs current price.
    BUY  -> entry above price  => BUY_STOP; entry below => BUY_LIMIT
    SELL -> entry below price  => SELL_STOP; entry above => SELL_LIMIT
    If price_now is None, default to STOP (safer).
    tol: optional tolerance (e.g., a few points) to avoid jitter around equality.
    """
    try:
        s = str(side).upper()
        e = float(entry)
        if price_now is None:
            return "BUY_STOP" if s in ("BUY", "LONG") else "SELL_STOP"
        p = float(price_now)
        if tol is None:
            tol = 0.0
        if s in ("BUY", "LONG"):
            return "BUY_STOP" if e >= p - float(tol) else "BUY_LIMIT"
        else:
            return "SELL_STOP" if e <= p + float(tol) else "SELL_LIMIT"
    except Exception:
        # Defensive default
        return "BUY_STOP" if str(side).upper() in ("BUY", "LONG") else "SELL_STOP"

def _respect_spread_and_news(
    tech: dict,
    max_spread_over_atr_pct: float = 25.0,
    min_minutes_to_news: float = 15.0,
) -> tuple[bool, dict]:
    """
    Return (ok, blocks) gating conditions based on spread and upcoming news.

    - Uses _spread_over_atr_pct(tech) if available; if missing, assumes spread is acceptable.
    - News is blocked if `news_block` is True OR minutes_to_next_news < threshold (when available).
    """
    blocks: dict[str, dict] = {}

    # Spread guard (prefer % of ATR so it's symbol/volatility aware)
    try:
        try:
            pct = float(_spread_over_atr_pct(tech))
        except Exception:
            pct = None
        spread_ok = True if pct is None else (pct <= float(max_spread_over_atr_pct))
        if not spread_ok:
            blocks["spread"] = {"over_atr_pct": pct, "limit_pct": max_spread_over_atr_pct}
    except Exception:
        # If anything goes wrong, don't hard-block the trade because of telemetry failure
        pass

    # News guard: explicit block flag or time proximity
    try:
        news_block_flag = bool(tech.get("news_block"))
        minutes_to_next = tech.get("minutes_to_next_news")
        minutes_ok = True if minutes_to_next in (None, "") else (float(minutes_to_next) >= float(min_minutes_to_news))
        if news_block_flag or not minutes_ok:
            blocks["news"] = {
                "minutes_to_next_news": (None if minutes_to_next in (None, "") else float(minutes_to_next)),
                "min_required": float(min_minutes_to_news),
                "news_block_flag": news_block_flag,
            }
    except Exception:
        # Defensive: treat as no additional block information
        pass

    ok = (len(blocks) == 0)
    return ok, blocks
# === Legacy helper shims (neutral-safe fallbacks) ==============================

# === Legacy helper shims (neutral-safe fallbacks) ==============================
def _pattern_breakout_retest(*args, **kwargs):
    return False

def _range_fade_sr(*args, **kwargs):
    return False

def _pct(x: float, y: float) -> float:
    try:
        return (float(x) / float(y)) * 100.0 if y not in (0, None) else 0.0
    except Exception:
        return 0.0

def _mult_add(a: float, b: float, c: float) -> float:
    try:
        return float(a) + float(b) * float(c)
    except Exception:
        return 0.0

def _mult_mult(a: float, b: float, c: float) -> float:
    try:
        return float(a) * float(b) * float(c)
    except Exception:
        return 0.0

def _get_from(d: dict, *keys, default=None):
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d:
            return d[k]
    return default
# ==============================================================================


def _pattern_breakout_retest(*args, **kwargs):
    """Legacy placeholder: breakout/retest pattern filter. Returns False by default."""
    return False

def _range_fade_sr(*args, **kwargs):
    """Legacy placeholder: range fade near S/R. Returns False by default."""
    return False

def _pct(x: float, y: float) -> float:
    """Return percentage ratio (x / y * 100). Safe default 0 if y is 0."""
    try:
        return (float(x) / float(y)) * 100.0 if y not in (0, None) else 0.0
    except Exception:
        return 0.0

def _mult_add(a: float, b: float, c: float) -> float:
    """Legacy math shim: a + b*c."""
    try:
        return float(a) + float(b) * float(c)
    except Exception:
        return 0.0

def _mult_mult(a: float, b: float, c: float) -> float:
    """Legacy math shim: a * b * c."""
    try:
        return float(a) * float(b) * float(c)
    except Exception:
        return 0.0

def _get_from(d: dict, *keys, default=None):
    """Safe dict getter across multiple keys."""
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d:
            return d[k]
    return default

# ==============================================================================
# Feature Flags and Confidence Threshold Helpers (Phase 0.2.4)
# ==============================================================================

# Module-level cache for feature flags
_feature_flags_cache: Optional[Dict[str, Any]] = None
_feature_flags_cache_time: Optional[float] = None

def _load_feature_flags() -> Dict[str, Any]:
    """Load feature flags configuration from JSON file (with caching)"""
    import time  # Import here to avoid circular dependencies
    global _feature_flags_cache, _feature_flags_cache_time
    cache_ttl = 60.0
    
    if _feature_flags_cache is not None and _feature_flags_cache_time:
        if (time.time() - _feature_flags_cache_time) < cache_ttl:
            return _feature_flags_cache
    
    config_path = Path("config/strategy_feature_flags.json")
    
    try:
        if config_path.exists():
            with open(config_path, 'r') as f:
                _feature_flags_cache = json.load(f)
                _feature_flags_cache_time = time.time()
                return _feature_flags_cache
        else:
            logger.debug(f"Feature flags file not found: {config_path}")
            _feature_flags_cache = {}
            _feature_flags_cache_time = time.time()
            return {}
    except Exception as e:
        logger.warning(f"Failed to load feature flags: {e}")
        _feature_flags_cache = {}
        _feature_flags_cache_time = time.time()
        return {}

def _is_strategy_enabled(strategy_name: str) -> bool:
    """
    Check if strategy is enabled via feature flag.
    
    Note: If feature flags file doesn't exist, all strategies are enabled by default
    (graceful degradation - allow strategies if we can't check).
    """
    try:
        flags = _load_feature_flags()
        strategy_flags = flags.get("strategy_feature_flags", {})
        strategy_cfg = strategy_flags.get(strategy_name, {})
        # If file doesn't exist or strategy not in file, default to enabled (graceful degradation)
        return strategy_cfg.get("enabled", True)
    except Exception:
        # Graceful degradation: if check fails, allow strategy
        return True

def _has_required_fields(tech: Dict[str, Any], required_fields: List[str]) -> bool:
    """Check if tech dict has all required fields (at least one if list provided)"""
    if not required_fields:
        return True
    # Check if at least one field exists (for OR conditions like order_block_bull OR order_block_bear)
    return any(field in tech and tech[field] is not None for field in required_fields)

def _get_confidence_threshold(strategy_name: str) -> float:
    """Get confidence threshold for strategy"""
    try:
        flags = _load_feature_flags()
        thresholds = flags.get("confidence_thresholds", {})
        return thresholds.get(strategy_name, 0.5)  # Default 0.5
    except Exception:
        return 0.5  # Default if check fails

def _meets_confidence_threshold(tech: Dict[str, Any], strategy_name: str) -> bool:
    """Check if pattern meets minimum confidence threshold"""
    # Get confidence field based on strategy
    confidence_fields = {
        "order_block_rejection": "ob_strength",
        "fvg_retracement": "fvg_strength",
        "breaker_block": "breaker_block_strength",
        "mitigation_block": "mitigation_block_strength",
        "market_structure_shift": "mss_strength",
        "inducement_reversal": "rejection_strength",  # Using rejection_strength for inducement
        "premium_discount_array": "fib_strength",
        "kill_zone": None,  # Time-based, no confidence score
        "session_liquidity_run": "session_liquidity_strength",
    }
    
    field = confidence_fields.get(strategy_name)
    if not field:  # None or not in map
        return True  # No confidence requirement
    
    confidence = tech.get(field)
    if confidence is None:
        return False  # Missing confidence field = doesn't meet threshold
    
    threshold = _get_confidence_threshold(strategy_name)
    return float(confidence) >= float(threshold)

# ==============================================================================





def _respect_spread_and_news(tech: dict) -> tuple[bool, list[str]]:
    """
    Guardrail shim: check spread and news context.
    Returns (ok, blocks) where:
      ok = True if allowed to trade, False if blocked
      blocks = list of reasons ("spread_high", "news_block", ...)
    """
    reasons = []
    try:
        spr = float(tech.get("spread_pts") or 0.0)
        maxspr = float(tech.get("max_spread_allowed") or 0.0)
        if maxspr and spr > maxspr > 0:
            reasons.append("spread_high")
    except Exception:
        pass
    try:
        if tech.get("news_block") or (isinstance(tech.get("minutes_to_next_news"), (int, float)) and (tech.get("minutes_to_next_news") or 9999) < 30):
            reasons.append("news_block")
    except Exception:
        pass
    return (len(reasons) == 0), reasons





def _sr_anchor(side: str, entry: float, sl: float, tp: float, symbol: str, tech: dict):
    """
    Structure/rounding anchor shim.
    - Ensures SL beyond entry by a minimal tick if inverted.
    - Optionally nudges SL/TP to nearest sensible level; currently no-op except validation.
    Returns: (entry, sl, tp, notes_str)
    """
    try:
        side_up = str(side).upper()
        e = float(entry); s = float(sl); t = float(tp)
        notes = []
        # Minimal sanity: SL must be on the risk side of entry
        if side_up in ("BUY", "LONG") and s >= e:
            s = e - max(0.01, float(tech.get("_point") or 0.01) * 5.0)
            notes.append("sl_nudged_below_entry")
        elif side_up in ("SELL", "SHORT") and s <= e:
            s = e + max(0.01, float(tech.get("_point") or 0.01) * 5.0)
            notes.append("sl_nudged_above_entry")
        return e, s, t, (";".join(notes) if notes else "")
    except Exception:
        return entry, sl, tp, ""

def _near_sr(tech: dict):
    """
    Best-effort nearest Support/Resistance finder.
    Returns (support_price or None, resistance_price or None).
    Looks for common keys; falls back to None/None.
    """
    try:
        # Try explicit fields that might exist in your pipeline
        s = tech.get("nearest_support")
        r = tech.get("nearest_resistance")
        # Try nested blobs (M15 preferred)
        if s is None or r is None:
            m15 = _tf_blob(tech, "M15")
            if isinstance(m15, dict):
                s = m15.get("nearest_support") if s is None else s
                r = m15.get("nearest_resistance") if r is None else r
        # Generic level arrays
        levels = tech.get("levels") or {}
        if isinstance(levels, dict):
            s = s or levels.get("support") or levels.get("nearest_support")
            r = r or levels.get("resistance") or levels.get("nearest_resistance")
        # Coerce to float when possible
        def _cof(x):
            try:
                return float(x) if x is not None else None
            except Exception:
                return None
        return _cof(s), _cof(r)
    except Exception:
        return None, None





# ================================================================================



_STRAT_MAP_CACHE: Optional[dict] = None


def _load_strategy_map() -> dict:
    """Primary: infra.strategy_map.get_strategy_map(); fallback: app/config/strategy_map.json; else {}."""
    global _STRAT_MAP_CACHE
    if _STRAT_MAP_CACHE is not None:
        return _STRAT_MAP_CACHE
    # Primary: via helper if present
    try:
        from infra.strategy_map import get_strategy_map  # type: ignore

        m = get_strategy_map()
        if isinstance(m, dict):
            _STRAT_MAP_CACHE = m
            return m
    except Exception:
        pass
    # File fallback
    try:
        here = Path(__file__).resolve()
        cfg = (
            here.parent.parent / "config" / "strategy_map.json"
        )  # app/engine -> app/config
        if not cfg.exists():
            alt = Path.cwd() / "app" / "config" / "strategy_map.json"
            cfg = alt if alt.exists() else cfg
        _STRAT_MAP_CACHE = (
            json.loads(cfg.read_text(encoding="utf-8") or "{}") if cfg.exists() else {}
        )
        return _STRAT_MAP_CACHE
    except Exception:
        _STRAT_MAP_CACHE = {}
        return {}


def _sess(tech: Dict[str, Any]) -> str:
    return str(
        tech.get("session") or tech.get("_tf_M5", {}).get("session") or ""
    ).upper()


# --- deep update helper so symbol/session/regime overrides merge nested dicts ---
def _deep_update(base: dict, override: dict) -> dict:
    """Recursively update dict `base` with values from `override`.
    Lists/tuples and scalars are replaced; dicts merged. Returns a new dict."""
    if not isinstance(base, dict):
        base = {}
    if not isinstance(override, dict):
        return deepcopy(base)
    out = deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_update(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out


def _builder_cfg(name: str, tech: Dict[str, Any], regime: str) -> dict:
    """
    Merge defaults <- strategy_map['builders']['default'] <- strategy_map['builders'][name]
    Apply optional 'session_overrides' and 'regime_overrides'.
    (We primarily read per-strategy config from strategy_map['strategies'], but this
     helper is available if you later choose to move builder knobs under 'builders'.)
    """
    mp = _load_strategy_map()
    root = (mp.get("builders") or {}) if isinstance(mp, dict) else {}
    base = dict(root.get("default") or {})
    spec = dict(root.get(name) or {})
    out = {**base, **spec}

    # session/regime specific tweaks
    session = _sess(tech)
    so = out.get("session_overrides") or {}
    if isinstance(so, dict) and session in so:
        out.update({k: v for k, v in (so[session] or {}).items() if v is not None})
    ro = out.get("regime_overrides") or {}
    if isinstance(ro, dict) and regime in ro:
        out.update({k: v for k, v in (ro[regime] or {}).items() if v is not None})
    return out


def _allowed_here(cfg: dict, tech: Dict[str, Any], regime: str) -> bool:
    """Check optional allow/block lists for sessions/regimes."""
    ses = _sess(tech)
    allow_s = (
        set(cfg.get("allow_sessions") or [])
        if isinstance(cfg.get("allow_sessions"), list)
        else None
    )
    block_s = (
        set(cfg.get("block_sessions") or [])
        if isinstance(cfg.get("block_sessions"), list)
        else set()
    )
    allow_r = (
        set(cfg.get("allow_regimes") or [])
        if isinstance(cfg.get("allow_regimes"), list)
        else None
    )
    block_r = (
        set(cfg.get("block_regimes") or [])
        if isinstance(cfg.get("block_regimes"), list)
        else set()
    )

    if allow_s is not None and ses not in allow_s:
        return False
    if allow_r is not None and regime not in allow_r:
        return False
    if ses in block_s:
        return False
    if regime in block_r:
        return False
    return True


def _session_from_tech(tech: Dict[str, Any]) -> str:
    return str(tech.get("session") or "").upper()


def _strat_cfg(
    name: str,
    symbol: Optional[str] = None,
    tech: Optional[Dict[str, Any]] = None,
    regime: Optional[str] = None,
) -> dict:
    """Return per-strategy config merged with optional symbol/session/regime overrides.

    Merge order (later wins):
      strategies[name]
        -> symbol_overrides[symbol]
        -> session_overrides[session]
        -> regime_overrides[regime]
    """
    mp = _load_strategy_map() or {}
    strat_root = mp.get("strategies") or {}
    base = deepcopy(strat_root.get(name, {}) or {})

    # Symbol-specific override
    if symbol and isinstance(base.get("symbol_overrides"), dict):
        sym_cfg = base["symbol_overrides"].get(symbol)
        if isinstance(sym_cfg, dict):
            base = _deep_update(base, sym_cfg)

    # Session/regime overrides (generic, not just rr_floor)
    if tech is not None:
        ses = _session_from_tech(tech)
        so = base.get("session_overrides") or {}
        if isinstance(so, dict) and ses in so and isinstance(so[ses], dict):
            base = _deep_update(base, so[ses])
    if regime is not None:
        ro = base.get("regime_overrides") or {}
        if isinstance(ro, dict) and regime in ro and isinstance(ro[regime], dict):
            base = _deep_update(base, ro[regime])

    return base


def _rr_floor_for(
    strategy: str, symbol: Optional[str], tech: Dict[str, Any], default_rr: float
) -> float:
    """Per-strategy RR floor with optional symbol + session overrides (handled in _strat_cfg)."""
    cfg = _strat_cfg(strategy, symbol=symbol, tech=tech)
    rr = float(cfg.get("rr_floor", default_rr))
    return rr


def _get_filter(cfg: dict, *names: str, default=None):
    """Safe nested getter for filters in the strat map."""
    try:
        f = cfg.get("filters") or {}
        for n in names:
            if isinstance(f, dict):
                if n in f:
                    return f.get(n)
                # tolerate snake/camel keys
                if n.lower() in f:
                    return f.get(n.lower())
                if n.upper() in f:
                    return f.get(n.upper())
        return default
    except Exception:
        return default


def _get_sl_tp(cfg: dict) -> tuple[dict, dict]:
    st = cfg.get("sl_tp") or {}
    return (st.get("sl") or {}), (st.get("tp") or {})


# ----- formatting helper (soft import) -----
try:
    from infra.formatting import fmt_price
except Exception:

    def fmt_price(sym: str, p: float) -> str:
        return f"{p:.2f}"


# Optional domain utilities (soft imports)
try:
    from domain.market_structure import last_swings  # returns swing highs/lows
except Exception:
    last_swings = None
try:
    from domain.patterns import (
        detect_recent_patterns,
    )  # triangle, wedge, rectangle, H&S, DT/DB, IB/mother
except Exception:
    detect_recent_patterns = None


def _safe_float(x, default=None):
    try:
        return float(x)
    except Exception:
        return default


def _infer_direction_from_levels(entry, sl, tp):
    """
    Infer LONG/SHORT from structure around ENTRY:
      LONG  -> SL < Entry < TP
      SHORT -> SL > Entry > TP
    Return "LONG"/"SHORT"/None
    """
    e = _safe_float(entry)
    s = _safe_float(sl)
    t = _safe_float(tp)
    if e is None or s is None or t is None:
        return None
    if s < e < t:
        return "LONG"
    if s > e > t:
        return "SHORT"
    return None


def _price_ref_from_tech(tech: dict) -> float | None:
    """Prefer 'close', else M5/H1 close as price reference."""
    px = _safe_float(tech.get("close"))
    if px is not None and px > 0:
        return px
    try:
        return _safe_float((tech.get("_tf_M5") or {}).get("close")) or _safe_float(
            (tech.get("_tf_H1") or {}).get("close")
        )
    except Exception:
        return None


def _convert_to_market(plan, tech: Dict[str, Any]):
    """Convert a pending plan to MARKET using live mid/close and fix SL/TP geometry."""
    entry = getattr(plan, "entry", None)
    try:
        bid, ask = tech.get("_live_bid"), tech.get("_live_ask")
        entry = (
            (float(bid) + float(ask)) / 2.0
            if isinstance(bid, (int, float)) and isinstance(ask, (int, float))
            else float(tech.get("close") if tech.get("close") is not None else entry)
        )
    except Exception:
        pass

    plan.entry = entry
    plan.pending_type = "MARKET"

    # keep SL/TP but fix obvious geometry using ATR as a pad
    atr = 0.0
    try:
        atr = float(tech.get("atr_14") or 0.0)
    except Exception:
        pass

    d = (getattr(plan, "direction", "") or "").upper()
    s = getattr(plan, "sl", None)
    t = getattr(plan, "tp", None)

    try:
        e = float(entry)
        s = float(s) if s is not None else None
        t = float(t) if t is not None else None
    except Exception:
        return plan

    pad = max(atr * 0.25, 1e-6)

    if d == "LONG":
        if s is not None and not (s < e):
            s = e - pad
        if t is not None and not (t > e):
            t = e + max(atr, pad)
    elif d == "SHORT":
        if s is not None and not (s > e):
            s = e + pad
        if t is not None and not (t < e):
            t = e - max(atr, pad)

    plan.sl, plan.tp = s, t
    if plan.entry is not None and plan.sl is not None and plan.tp is not None:
        plan.rr = _recompute_rr(plan.entry, plan.sl, plan.tp)
    return plan


def _finalise_pending_type(plan, tech: Dict[str, Any]):
    """IMPROVED: Decide STOP vs LIMIT based on strategy type and market structure."""
    try:
        bid, ask = tech.get("_live_bid"), tech.get("_live_ask")
        ref = (
            (float(bid) + float(ask)) / 2.0
            if isinstance(bid, (int, float)) and isinstance(ask, (int, float))
            else float(tech.get("close"))
        )
    except Exception:
        ref = None

    d = (getattr(plan, "direction", "") or "").upper()
    e = float(getattr(plan, "entry", 0.0) or 0.0)
    strategy = getattr(plan, "strategy", "")

    # IMPROVED: Strategy-specific entry type logic
    if strategy == "trend_pullback_ema":
        # For trend pullback, use LIMIT to catch pullbacks
        if d == "LONG":
            plan.pending_type = "BUY_LIMIT"
        elif d == "SHORT":
            plan.pending_type = "SELL_LIMIT"
    elif strategy == "range_fade_sr":
        # For range fade, use LIMIT to fade at S/R levels
        if d == "LONG":
            plan.pending_type = "BUY_LIMIT"
        elif d == "SHORT":
            plan.pending_type = "SELL_LIMIT"
    elif strategy == "liquidity_sweep_reversal":
        # For liquidity sweep, use STOP to catch breakouts
        if d == "LONG":
            plan.pending_type = "BUY_STOP"
        elif d == "SHORT":
            plan.pending_type = "SELL_STOP"
    else:
        # Default logic based on entry vs current price
        if d == "LONG":
            plan.pending_type = (
                "BUY_STOP" if (ref is not None and e >= ref) else "BUY_LIMIT"
            )
        elif d == "SHORT":
            plan.pending_type = (
                "SELL_STOP" if (ref is not None and e <= ref) else "SELL_LIMIT"
            )
    return plan


def _recompute_rr(entry: float, sl: float, tp: float) -> float:
    try:
        e, s, t = float(entry), float(sl), float(tp)
        return abs(t - e) / max(1e-9, abs(e - s))
    except Exception:
        return 0.0


def _coerce_direction_if_misfit(plan):
    """If SL/ENTRY/TP geometry contradicts direction, flip it (defensive)."""
    try:
        e, s, t = float(plan.entry), float(plan.sl), float(plan.tp)
    except Exception:
        return plan
    d = (getattr(plan, "direction", "") or "").upper() or "HOLD"
    if d == "LONG":
        if not (s < e < t) and (s > e > t):
            plan.direction = "SHORT"
    elif d == "SHORT":
        if not (t < e < s) and (t > e > s):
            plan.direction = "LONG"
    return plan


# ---- regime-based SL/TP tweaks (map-driven, optional) -------------------------
def _apply_regime_sl_tp_tweaks(
    sl_mult: float, tp_mult: float, regime: str
) -> tuple[float, float]:
    """
    Allow global regime-level tweaks without touching per-strategy cfg.
    strategy_map.json may define:

    "regime": {
      "sl_tp_tweaks": {
        "TREND":  {"tp_mult_add": 0.2},
        "RANGE":  {"tp_mult_mult": 0.85},
        "VOLATILE":{"sl_mult_add": 0.1}
      }
    }

    Supported keys per regime:
      - tp_mult_add / sl_mult_add (additive)
      - tp_mult_mult / sl_mult_mult (multiplicative)
    """
    try:
        mp = _load_strategy_map() or {}
        tweaks = (mp.get("regime") or {}).get("sl_tp_tweaks") or {}  # type: ignore[assignment]
        t = (tweaks or {}).get(regime) or {}
        if not isinstance(t, dict):
            return sl_mult, tp_mult
        tp_mult = tp_mult * float(t.get("tp_mult_mult", 1.0)) + float(
            t.get("tp_mult_add", 0.0)
        )
        sl_mult = sl_mult * float(t.get("sl_mult_mult", 1.0)) + float(
            t.get("sl_mult_add", 0.0)
        )
        return sl_mult, tp_mult
    except Exception:
        return sl_mult, tp_mult


# ---- risk sizing from map.risk_overrides (optional) ---------------------------
def _spread_over_atr(tech: Dict[str, Any]) -> float:
    """Compute spread / ATR_eff (ATR M15 or M5, with a tick floor)."""
    try:
        spread = float(
            tech.get("_live_spread")
            or tech.get("spread_pts")
            or tech.get("spread")
            or 0.0
        )
        point = float(tech.get("_point") or 0.0)
        atr_m15 = float((tech.get("_tf_M15") or {}).get("atr_14") or 0.0)
        atr_m5 = float(tech.get("atr_14") or 0.0)
        atr = atr_m15 or atr_m5
        min_ticks = float(getattr(settings, "ATR_FLOOR_TICKS", 3.0))
        atr_eff = max(atr, min_ticks * point) if point else atr
        return (spread / atr_eff) if atr_eff > 0 else 0.0
    except Exception:
        return 0.0


def _compute_risk_pct(
    symbol: str, strategy: str, tech: Dict[str, Any], strat_cfg: dict
) -> float:
    """
    Start from strategy risk_base_pct, then apply map.risk_overrides deltas.
    Deltas are additive on the *multiplier* (i.e., risk = base * (1 + sum_deltas)).
    Example entries under "risk_overrides":
      "minutes_to_high_impact_news_lt": [30, -0.15],
      "spread_atr_pct_gt":             [0.25, -0.20],
      "adx_boost":                     [35,  0.10],
      "win_streak_boost":              [2,   0.05]
    """
    base = float(
        strat_cfg.get("risk_base_pct", getattr(settings, "DEFAULT_RISK_PCT", 0.30))
    )
    mp = _load_strategy_map() or {}
    ro = (mp.get("risk_overrides") or {}) if isinstance(mp, dict) else {}

    mult_delta = 0.0

    # minutes_to_high_impact_news_lt
    try:
        if "minutes_to_high_impact_news_lt" in ro:
            threshold, delta = ro["minutes_to_high_impact_news_lt"]
            mins_to_news = int(tech.get("minutes_to_next_news") or 999)
            if mins_to_news < float(threshold):
                mult_delta += float(delta)
    except Exception:
        pass

    # spread_atr_pct_gt
    try:
        if "spread_atr_pct_gt" in ro:
            threshold, delta = ro["spread_atr_pct_gt"]
            if _spread_over_atr(tech) > float(threshold):
                mult_delta += float(delta)
    except Exception:
        pass

    # adx_boost
    try:
        if "adx_boost" in ro:
            threshold, delta = ro["adx_boost"]
            if _adx(tech) >= float(threshold):
                mult_delta += float(delta)
    except Exception:
        pass

    # win_streak_boost (expects tech.win_streak int)
    try:
        if "win_streak_boost" in ro:
            threshold, delta = ro["win_streak_boost"]
            if int(tech.get("win_streak") or 0) >= int(threshold):
                mult_delta += float(delta)
    except Exception:
        pass

    eff = base * max(0.0, 1.0 + mult_delta)
    # Soft clamps (can be tuned via settings if you want)
    min_risk = float(getattr(settings, "MIN_RISK_PCT", 0.05))
    max_risk = float(getattr(settings, "MAX_RISK_PCT", 1.00))
    return max(min_risk, min(max_risk, eff))


def _attach_risk(plan, strat_cfg: dict, tech: Dict[str, Any], symbol: str):
    """Compute and attach risk_pct to the plan (does not size position; just metadata)."""
    try:
        plan.risk_pct = _compute_risk_pct(
            symbol, getattr(plan, "strategy", ""), tech, strat_cfg
        )
    except Exception:
        # keep going even if sizing computation fails
        plan.risk_pct = float(strat_cfg.get("risk_base_pct") or 0.0)
    return plan


# ------------------------ data class ------------------------------------------
from dataclasses import dataclass, field


@dataclass
class StrategyPlan:
    symbol: str
    strategy: str
    regime: str
    direction: str  # "LONG"|"SHORT"
    pending_type: str  # BUY_STOP|SELL_STOP|BUY_LIMIT|SELL_LIMIT|OCO_STOP|MARKET
    entry: float
    sl: Optional[float]
    tp: Optional[float]
    rr: Optional[float]
    notes: str
    ttl_min: Optional[int] = None
    oco_companion: Optional[Dict[str, Any]] = None  # for OCO: the other side
    # Preview/telemetry
    blocked_by: List[str] = field(default_factory=list)
    preview_only: bool = False
    # Risk metadata (percentage of equity to risk, e.g., 0.45 == 0.45%)
    risk_pct: Optional[float] = None


def _convert_to_market(plan, tech: Dict[str, Any]):
    """Convert a pending plan to MARKET using live mid/close and fix SL/TP geometry."""
    entry = getattr(plan, "entry", None)
    try:
        bid, ask = tech.get("_live_bid"), tech.get("_live_ask")
        entry = (
            (float(bid) + float(ask)) / 2.0
            if isinstance(bid, (int, float)) and isinstance(ask, (int, float))
            else float(tech.get("close") if tech.get("close") is not None else entry)
        )
    except Exception:
        pass

    plan.entry = entry
    plan.pending_type = "MARKET"

    # keep SL/TP but fix obvious geometry using ATR as a pad
    atr = 0.0
    try:
        atr = float(tech.get("atr_14") or 0.0)
    except Exception:
        pass

    d = (getattr(plan, "direction", "") or "").upper()
    s = getattr(plan, "sl", None)
    t = getattr(plan, "tp", None)

    try:
        e = float(entry)
        s = float(s) if s is not None else None
        t = float(t) if t is not None else None
    except Exception:
        return plan

    pad = max(atr * 0.25, 1e-6)

    if d == "LONG":
        if s is not None and not (s < e):
            s = e - pad
        if t is not None and not (t > e):
            t = e + max(atr, pad)
    elif d == "SHORT":
        if s is not None and not (s > e):
            s = e + pad
        if t is not None and not (t < e):
            t = e - max(atr, pad)

    plan.sl, plan.tp = s, t
    if plan.entry is not None and plan.sl is not None and plan.tp is not None:
        plan.rr = _recompute_rr(plan.entry, plan.sl, plan.tp)
    return plan


def _finalise_pending_type(plan, tech: Dict[str, Any]):
    """IMPROVED: Decide STOP vs LIMIT based on strategy type and market structure."""
    try:
        bid, ask = tech.get("_live_bid"), tech.get("_live_ask")
        ref = (
            (float(bid) + float(ask)) / 2.0
            if isinstance(bid, (int, float)) and isinstance(ask, (int, float))
            else float(tech.get("close"))
        )
    except Exception:
        ref = None

    d = (getattr(plan, "direction", "") or "").upper()
    e = float(getattr(plan, "entry", 0.0) or 0.0)
    strategy = getattr(plan, "strategy", "")

    # IMPROVED: Strategy-specific entry type logic
    if strategy == "trend_pullback_ema":
        # For trend pullback, use LIMIT to catch pullbacks
        if d == "LONG":
            plan.pending_type = "BUY_LIMIT"
        elif d == "SHORT":
            plan.pending_type = "SELL_LIMIT"
    elif strategy == "range_fade_sr":
        # For range fade, use LIMIT to fade at S/R levels
        if d == "LONG":
            plan.pending_type = "BUY_LIMIT"
        elif d == "SHORT":
            plan.pending_type = "SELL_LIMIT"
    elif strategy == "liquidity_sweep_reversal":
        # For liquidity sweep, use STOP to catch breakouts
        if d == "LONG":
            plan.pending_type = "BUY_STOP"
        elif d == "SHORT":
            plan.pending_type = "SELL_STOP"
    else:
        # Default logic based on entry vs current price
        if d == "LONG":
            plan.pending_type = (
                "BUY_STOP" if (ref is not None and e >= ref) else "BUY_LIMIT"
            )
        elif d == "SHORT":
            plan.pending_type = (
                "SELL_STOP" if (ref is not None and e <= ref) else "SELL_LIMIT"
            )
    return plan


def _recompute_rr(entry: float, sl: float, tp: float) -> float:
    try:
        e, s, t = float(entry), float(sl), float(tp)
        return abs(t - e) / max(1e-9, abs(e - s))
    except Exception:
        return 0.0


def _coerce_direction_if_misfit(plan):
    """If SL/ENTRY/TP geometry contradicts direction, flip it (defensive)."""
    try:
        e, s, t = float(plan.entry), float(plan.sl), float(plan.tp)
    except Exception:
        return plan
    d = (getattr(plan, "direction", "") or "").upper() or "HOLD"
    if d == "LONG":
        if not (s < e < t) and (s > e > t):
            plan.direction = "SHORT"
    elif d == "SHORT":
        if not (t < e < s) and (t > e > s):
            plan.direction = "LONG"
    return plan


# ---- regime-based SL/TP tweaks (map-driven, optional) -------------------------
def _apply_regime_sl_tp_tweaks(
    sl_mult: float, tp_mult: float, regime: str
) -> tuple[float, float]:
    """
    Allow global regime-level tweaks without touching per-strategy cfg.
    strategy_map.json may define:

    "regime": {
      "sl_tp_tweaks": {
        "TREND":  {"tp_mult_add": 0.2},
        "RANGE":  {"tp_mult_mult": 0.85},
        "VOLATILE":{"sl_mult_add": 0.1}
      }
    }

    Supported keys per regime:
      - tp_mult_add / sl_mult_add (additive)
      - tp_mult_mult / sl_mult_mult (multiplicative)
    """
    try:
        mp = _load_strategy_map() or {}
        tweaks = (mp.get("regime") or {}).get("sl_tp_tweaks") or {}  # type: ignore[assignment]
        t = (tweaks or {}).get(regime) or {}
        if not isinstance(t, dict):
            return sl_mult, tp_mult
        tp_mult = tp_mult * float(t.get("tp_mult_mult", 1.0)) + float(
            t.get("tp_mult_add", 0.0)
        )
        sl_mult = sl_mult * float(t.get("sl_mult_mult", 1.0)) + float(
            t.get("sl_mult_add", 0.0)
        )
        return sl_mult, tp_mult
    except Exception:
        return sl_mult, tp_mult


# ---- risk sizing from map.risk_overrides (optional) ---------------------------
def _spread_over_atr(tech: Dict[str, Any]) -> float:
    """Compute spread / ATR_eff (ATR M15 or M5, with a tick floor)."""
    try:
        spread = float(
            tech.get("_live_spread")
            or tech.get("spread_pts")
            or tech.get("spread")
            or 0.0
        )
        point = float(tech.get("_point") or 0.0)
        atr_m15 = float((tech.get("_tf_M15") or {}).get("atr_14") or 0.0)
        atr_m5 = float(tech.get("atr_14") or 0.0)
        atr = atr_m15 or atr_m5
        min_ticks = float(getattr(settings, "ATR_FLOOR_TICKS", 3.0))
        atr_eff = max(atr, min_ticks * point) if point else atr
        return (spread / atr_eff) if atr_eff > 0 else 0.0
    except Exception:
        return 0.0


def _compute_risk_pct(
    symbol: str, strategy: str, tech: Dict[str, Any], strat_cfg: dict
) -> float:
    """
    Start from strategy risk_base_pct, then apply map.risk_overrides deltas.
    Deltas are additive on the *multiplier* (i.e., risk = base * (1 + sum_deltas)).
    Example entries under "risk_overrides":
      "minutes_to_high_impact_news_lt": [30, -0.15],
      "spread_atr_pct_gt":             [0.25, -0.20],
      "adx_boost":                     [35,  0.10],
      "win_streak_boost":              [2,   0.05]
    """
    base = float(
        strat_cfg.get("risk_base_pct", getattr(settings, "DEFAULT_RISK_PCT", 0.30))
    )
    mp = _load_strategy_map() or {}
    ro = (mp.get("risk_overrides") or {}) if isinstance(mp, dict) else {}

    mult_delta = 0.0

    # minutes_to_high_impact_news_lt
    try:
        if "minutes_to_high_impact_news_lt" in ro:
            threshold, delta = ro["minutes_to_high_impact_news_lt"]
            mins_to_news = int(tech.get("minutes_to_next_news") or 999)
            if mins_to_news < float(threshold):
                mult_delta += float(delta)
    except Exception:
        pass

    # spread_atr_pct_gt
    try:
        if "spread_atr_pct_gt" in ro:
            threshold, delta = ro["spread_atr_pct_gt"]
            if _spread_over_atr(tech) > float(threshold):
                mult_delta += float(delta)
    except Exception:
        pass

    # adx_boost
    try:
        if "adx_boost" in ro:
            threshold, delta = ro["adx_boost"]
            if _adx(tech) >= float(threshold):
                mult_delta += float(delta)
    except Exception:
        pass

    # win_streak_boost (expects tech.win_streak int)
    try:
        if "win_streak_boost" in ro:
            threshold, delta = ro["win_streak_boost"]
            if int(tech.get("win_streak") or 0) >= int(threshold):
                mult_delta += float(delta)
    except Exception:
        pass

    eff = base * max(0.0, 1.0 + mult_delta)
    # Soft clamps (can be tuned via settings if you want)
    min_risk = float(getattr(settings, "MIN_RISK_PCT", 0.05))
    max_risk = float(getattr(settings, "MAX_RISK_PCT", 1.00))
    return max(min_risk, min(max_risk, eff))


def _attach_risk(plan, strat_cfg: dict, tech: Dict[str, Any], symbol: str):
    """Compute and attach risk_pct to the plan (does not size position; just metadata)."""
    try:
        plan.risk_pct = _compute_risk_pct(
            symbol, getattr(plan, "strategy", ""), tech, strat_cfg
        )
    except Exception:
        # keep going even if sizing computation fails
        plan.risk_pct = float(strat_cfg.get("risk_base_pct") or 0.0)
    return plan


# ------------------------ data class ------------------------------------------
from dataclasses import dataclass, field


@dataclass
class StrategyPlan:
    symbol: str
    strategy: str
    regime: str
    direction: str  # "LONG"|"SHORT"
    pending_type: str  # BUY_STOP|SELL_STOP|BUY_LIMIT|SELL_LIMIT|OCO_STOP|MARKET
    entry: float
    sl: Optional[float]
    tp: Optional[float]
    rr: Optional[float]
    notes: str
    ttl_min: Optional[int] = None
    oco_companion: Optional[Dict[str, Any]] = None  # for OCO: the other side
    # Preview/telemetry
    blocked_by: List[str] = field(default_factory=list)
    preview_only: bool = False
    # Risk metadata (percentage of equity to risk, e.g., 0.45 == 0.45%)
    risk_pct: Optional[float] = None


# -------- IMPROVED Strategy Direction Logic --------
def _determine_strategy_direction(tech: Dict[str, Any], strategy_name: str) -> Optional[str]:
    """
    IMPROVED: Determine strategy direction with timeframe priority and market structure awareness.
    Returns "LONG", "SHORT", or None if no clear direction.
    """
    # Get timeframe data
    m5_data = tech.get("_tf_M5", {})
    m15_data = tech.get("_tf_M15", {})
    h1_data = tech.get("_tf_H1", {})
    
    # Get ADX values
    adx_m5 = _safe_float(m5_data.get("adx_14"), 0.0)
    adx_m15 = _safe_float(m15_data.get("adx_14"), 0.0)
    adx_h1 = _safe_float(h1_data.get("adx_14"), 0.0)
    
    # Get RSI values
    rsi_m5 = _safe_float(m5_data.get("rsi_14"), 50.0)
    rsi_m15 = _safe_float(m15_data.get("rsi_14"), 50.0)
    rsi_h1 = _safe_float(h1_data.get("rsi_14"), 50.0)
    
    # Get EMA slopes
    ema_slope_m5 = _safe_float(m5_data.get("ema_200_slope"), 0.0)
    ema_slope_m15 = _safe_float(m15_data.get("ema_200_slope"), 0.0)
    ema_slope_h1 = _safe_float(h1_data.get("ema_200_slope"), 0.0)
    
    # Strategy-specific logic
    if strategy_name == "trend_pullback_ema":
        # For trend pullback, require clear uptrend on higher timeframes
        if adx_h1 > 25 and ema_slope_h1 > 0 and rsi_h1 > 50:
            return "LONG"
        elif adx_h1 > 25 and ema_slope_h1 < 0 and rsi_h1 < 50:
            return "SHORT"
        else:
            return None
    
    elif strategy_name == "range_fade_sr":
        # For range fade, look for rejection at S/R levels
        price = _price(tech)
        nearest_sr = tech.get("sr", {}).get("nearest", {})
        sr_kind = nearest_sr.get("kind", "")
        
        if sr_kind == "RESISTANCE" and rsi_m15 > 70:
            return "SHORT"
        elif sr_kind == "SUPPORT" and rsi_m15 < 30:
            return "LONG"
        else:
            return None
    
    elif strategy_name == "liquidity_sweep_reversal":
        # For liquidity sweep, look for false breakouts
        if adx_m5 > 30 and rsi_m5 < 30 and rsi_m15 < 40:
            return "LONG"  # Oversold reversal
        elif adx_m5 > 30 and rsi_m5 > 70 and rsi_m15 > 60:
            return "SHORT"  # Overbought reversal
        else:
            return None
    
    # Default fallback
    if adx_h1 > 25 and ema_slope_h1 > 0:
        return "LONG"
    elif adx_h1 > 25 and ema_slope_h1 < 0:
        return "SHORT"
    else:
        return None


# -------- Strategy implementations (map-aware) --------


def strat_trend_pullback_ema(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    cfg = _strat_cfg("trend_pullback_ema", symbol=symbol, tech=tech, regime=regime)
    if not _allowed_here(cfg, tech, regime):
        return None

    # Gates from map (with tolerances)
    adx_min = float(_get_filter(cfg, "adx_min", default=22))
    need_align = bool(_get_filter(cfg, "ema200_align", default=True))

    adx = _adx(tech)
    if adx < adx_min:
        return None

    # IMPROVED: Better direction logic with timeframe priority
    side = _determine_strategy_direction(tech, "trend_pullback_ema")
    if not side:
        return None

    # Pullback level: prefer EMA20/50; if missing, use current price
    ema20 = (
        _ema(tech, "M15", 20)
        or _ema(tech, "H1", 20)
        or _get_from(tech, None, ["ema_20", "EMA_20", "ema20", "EMA20"])
    )
    ema50 = (
        _ema(tech, "M15", 50)
        or _ema(tech, "H1", 50)
        or _get_from(tech, None, ["ema_50", "EMA_50", "ema50", "EMA50"])
    )
    entry = ema20 or ema50 or price

    atr = _atr(tech) or _atr(tech, "H1")
    if not atr:
        return None  # nothing we can size with

    sl_cfg, tp_cfg = _get_sl_tp(cfg)
    sl_mult = float(sl_cfg.get("atr_mult", 1.2))
    tp_mult = float(tp_cfg.get("atr_mult", 1.8))

    # Regime-level tweaks (e.g., wider TP in TREND, closer in RANGE)
    sl_mult, tp_mult = _apply_regime_sl_tp_tweaks(sl_mult, tp_mult, regime)

    sl = entry - sl_mult * atr if side == "LONG" else entry + sl_mult * atr
    tp = entry + tp_mult * atr if side == "LONG" else entry - tp_mult * atr

    # S/R anchoring
    entry, sl, tp, anchor_notes = _sr_anchor(side, entry, sl, tp, symbol, tech)

    rr = _calc_rr(side, entry, sl, tp)
    price_now = price or entry
    pending_type = _pending_type_from_entry(side, entry, price_now)

    ttl_min = int(cfg.get("ttl_min", 0) or 0) or None

    ok, blocks = _respect_spread_and_news(tech)
    note = (
        ("EMA pullback. " + "; ".join(anchor_notes))
        if anchor_notes
        else "EMA pullback."
    )
    plan = StrategyPlan(
        symbol=symbol,
        strategy="trend_pullback_ema",
        regime=regime,
        direction=side,
        pending_type=pending_type,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr,
        notes=note,
        ttl_min=ttl_min,
        preview_only=not ok,
        blocked_by=(blocks if not ok else []),
    )
    return _attach_risk(plan, cfg, tech, symbol)


def strat_range_fade_sr(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    cfg = _strat_cfg("range_fade_sr", symbol=symbol, tech=tech, regime=regime)
    if not _allowed_here(cfg, tech, regime):
        return None
    if regime != "RANGE":
        return None

    # IMPROVED: Use new direction logic
    side = _determine_strategy_direction(tech, "range_fade_sr")
    if not side:
        return None

    squeeze_max = float(_get_filter(cfg, "bb_squeeze_max", default=0.012))
    bb = _bb_width(tech)
    if bb > squeeze_max:
        return None

    sup, res = _near_sr(tech)
    price = _price(tech)
    if not sup or not res:
        return None
    atr = _atr(tech)
    if not atr:
        return None

    # Choose side based on proximity
    long_bias = abs(price - sup) < abs(res - price)
    side = "LONG" if long_bias else "SHORT"
    entry = sup if long_bias else res

    sl_cfg, tp_cfg = _get_sl_tp(cfg)
    sl_mult = float(sl_cfg.get("atr_mult", 1.0))
    tp_mult = float(tp_cfg.get("atr_mult", 1.0))

    # Regime tweaks
    sl_mult, tp_mult = _apply_regime_sl_tp_tweaks(sl_mult, tp_mult, regime)

    sl = (entry - sl_mult * atr) if long_bias else (entry + sl_mult * atr)
    tp = (entry + tp_mult * atr) if long_bias else (entry - tp_mult * atr)

    entry, sl, tp, anchor_notes = _sr_anchor(side, entry, sl, tp, symbol, tech)
    rr = _calc_rr(side, entry, sl, tp)
    pending_type = _pending_type_from_entry(side, entry, price)
    ttl_min = int(cfg.get("ttl_min", 0) or 0) or None

    ok, blocks = _respect_spread_and_news(tech)
    note = "Range fade at S/R. " + "; ".join(anchor_notes)
    plan = StrategyPlan(
        symbol=symbol,
        strategy="range_fade_sr",
        regime=regime,
        direction=side,
        pending_type=pending_type,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr,
        notes=note,
        ttl_min=ttl_min,
        preview_only=not ok,
        blocked_by=(blocks if not ok else []),
    )
    return _attach_risk(plan, cfg, tech, symbol)


def strat_opening_range_breakout(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    cfg = _strat_cfg("opening_range_breakout", symbol=symbol, tech=tech, regime=regime)
    if not _allowed_here(cfg, tech, regime):
        return None

    # Expect tech["session"] and tech["open_range"] = {"high":..,"low":..,"minutes":..}
    allowed_sessions = set(
        (_get_filter(cfg, "session_in") or []) or ["LONDON", "NEWYORK"]
    )
    sess = (tech.get("session") or "").upper()
    if allowed_sessions and sess not in allowed_sessions:
        return None

    rng = tech.get("open_range") or {}
    min_minutes = int(_get_filter(cfg, "open_range_minutes", default=45))
    hi, lo, mins = rng.get("high"), rng.get("low"), rng.get("minutes")
    if not (hi and lo and mins and mins >= min_minutes):
        return None

    ttl_min = int((cfg.get("entry") or {}).get("ttl_min", cfg.get("ttl_min", 90)))

    # TP: range height * mult (subject to regime tweaks on the mult)
    sl_cfg, tp_cfg = _get_sl_tp(cfg)
    base_tp_mult = float(tp_cfg.get("mult", 1.5))
    # Apply regime tweak as if it's a generic tp multiplier
    _, tp_mult = _apply_regime_sl_tp_tweaks(1.0, base_tp_mult, regime)
    rng_h = float(hi) - float(lo)

    long = StrategyPlan(
        symbol=symbol,
        strategy="opening_range_breakout",
        regime=regime,
        direction="LONG",
        pending_type="OCO_STOP",
        entry=float(hi),
        sl=float((hi + lo) / 2),
        tp=float(hi + tp_mult * rng_h),
        rr=None,
        notes=f"OR breakout long over {hi:.2f}",
        ttl_min=ttl_min,
    )
    short = StrategyPlan(
        symbol=symbol,
        strategy="opening_range_breakout",
        regime=regime,
        direction="SHORT",
        pending_type="OCO_STOP",
        entry=float(lo),
        sl=float((hi + lo) / 2),
        tp=float(lo - tp_mult * rng_h),
        rr=None,
        notes=f"OR breakout short under {lo:.2f}",
        ttl_min=ttl_min,
    )
    long.oco_companion = {
        "direction": "SHORT",
        "entry": short.entry,
        "sl": short.sl,
        "tp": short.tp,
    }
    short.oco_companion = {
        "direction": "LONG",
        "entry": long.entry,
        "sl": long.sl,
        "tp": long.tp,
    }

    ok, blocks = _respect_spread_and_news(tech)
    if not ok:
        long.blocked_by = blocks
        long.preview_only = True

    # Attach risk metadata
    long = _attach_risk(long, cfg, tech, symbol)
    return long if regime in {"VOLATILE", "TREND"} else None


# ---- Regime-aware SL/TP tweaks + risk wiring --------------------------------


def _apply_regime_sl_tp_tweaks(
    sl_mult: float, tp_mult: float, regime: str
) -> Tuple[float, float]:
    """
    Adjust ATR multipliers by regime.
    Uses map['regime_tweaks'][REGIME] if present; else sensible defaults:
      - TREND:    wider TP (+0.20), unchanged SL
      - RANGE:    closer TP (-0.20), unchanged SL
      - VOLATILE: modestly wider SL/TP (+0.05/+0.10)
    Map keys supported (per-regime):
      { "tp_add": 0.2, "sl_add": 0.05 }  # additive deltas to ATR multiples
      (aliases: 'tp_mult_bump', 'sl_mult_bump')
    """
    try:
        mp = _load_strategy_map() or {}
        rt = (mp.get("regime_tweaks") or {}).get(str(regime).upper(), {}) or {}
    except Exception:
        rt = {}

    # defaults
    defaults = {
        "TREND": {"tp_add": 0.20, "sl_add": 0.00},
        "RANGE": {"tp_add": -0.20, "sl_add": 0.00},
        "VOLATILE": {"tp_add": 0.10, "sl_add": 0.05},
    }
    d = defaults.get(str(regime).upper(), {"tp_add": 0.0, "sl_add": 0.0})

    # map overrides
    tp_add = float(rt.get("tp_add", rt.get("tp_mult_bump", d["tp_add"])))
    sl_add = float(rt.get("sl_add", rt.get("sl_mult_bump", d["sl_add"])))

    sl_out = max(0.1, sl_mult + sl_add)
    tp_out = max(0.1, tp_mult + tp_add)
    return sl_out, tp_out


def _attach_risk(
    plan: StrategyPlan, cfg: dict, tech: Dict[str, Any], symbol: str
) -> StrategyPlan:
    """
    Compute per-trade risk_pct using strategy base + map['risk_overrides'].
    Supported overrides in map['risk_overrides']:
      - "minutes_to_high_impact_news_lt": [mins, delta]
      - "spread_atr_pct_gt":              [ratio, delta]
      - "adx_boost":                      [adx, +delta]
      - "win_streak_boost":               [n, +delta]
    Notes: deltas are additive (e.g., +0.05 => +5% of account risk).
    """
    base = float(cfg.get("risk_base_pct", 0.35))
    eff = base
    applied: List[str] = []

    mp = _load_strategy_map() or {}
    ro = (mp.get("risk_overrides") or {}) if isinstance(mp, dict) else {}

    # --- helpers from tech ---
    def _mins_to_news() -> Optional[float]:
        for k in ("minutes_to_next_news", "minutes_to_high_impact_news", "news_mins"):
            v = tech.get(k)
            try:
                if v is not None:
                    return float(v)
            except Exception:
                pass
        return None

    def _spread_atr_ratio() -> Optional[float]:
        try:
            spread = float(
                tech.get("_live_spread")
                or tech.get("spread_pts")
                or tech.get("spread")
                or 0.0
            )
            point = float(tech.get("_point") or 0.0)
            atr_m15 = float((tech.get("_tf_M15") or {}).get("atr_14") or 0.0)
            atr_m5 = float(tech.get("atr_14") or 0.0)
            atr = atr_m15 or atr_m5
            # small ATR floor by ticks
            min_ticks = float(getattr(settings, "ATR_FLOOR_TICKS", 3.0))
            atr_eff = max(atr, min_ticks * point) if point else atr
            if atr_eff > 0:
                return spread / atr_eff
            return None
        except Exception:
            return None

    def _adx_now() -> float:
        return float(_adx(tech) or 0.0)

    def _win_streak() -> int:
        for path in ("win_streak", ("stats", "win_streak")):
            try:
                if isinstance(path, tuple):
                    v = (tech.get(path[0]) or {}).get(path[1])
                else:
                    v = tech.get(path)
                if v is not None:
                    return int(v)
            except Exception:
                pass
        return 0

    # --- apply overrides if present ---
    try:
        mins_thr, delta = ro.get("minutes_to_high_impact_news_lt", [None, 0])
        if mins_thr is not None:
            mins = _mins_to_news()
            if mins is not None and mins < float(mins_thr):
                eff += float(delta)
                applied.append(f"news<{mins_thr}m:{delta:+.2f}")
    except Exception:
        pass

    try:
        ratio_thr, delta = ro.get("spread_atr_pct_gt", [None, 0])
        if ratio_thr is not None:
            r = _spread_atr_ratio()
            if r is not None and r > float(ratio_thr):
                eff += float(delta)
                applied.append(f"spread/ATR>{ratio_thr:.2f}:{float(delta):+.2f}")
    except Exception:
        pass

    try:
        adx_thr, delta = ro.get("adx_boost", [None, 0])
        if adx_thr is not None and _adx_now() >= float(adx_thr):
            eff += float(delta)
            applied.append(f"ADX>={adx_thr}:{float(delta):+.2f}")
    except Exception:
        pass

    try:
        n_thr, delta = ro.get("win_streak_boost", [None, 0])
        if n_thr is not None and _win_streak() >= int(n_thr):
            eff += float(delta)
            applied.append(f"win_streak>={n_thr}:{float(delta):+.2f}")
    except Exception:
        pass

    # clamp to reasonable bounds
    eff = max(0.01, min(1.00, eff))
    # set dynamically (dataclass allows new attrs without __slots__)
    setattr(plan, "risk_pct", round(eff, 4))
    if applied:
        plan.notes = (
            plan.notes or ""
        ) + f" | risk={eff:.2f} (base {base:.2f}; {'; '.join(applied)})"
    else:
        plan.notes = (plan.notes or "") + f" | risk={eff:.2f} (base {base:.2f})"
    return plan


# -------- Remaining strategies (map-aware) --------


def strat_liquidity_sweep_reversal(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    cfg = _strat_cfg(
        "liquidity_sweep_reversal", symbol=symbol, tech=tech, regime=regime
    )
    if not _allowed_here(cfg, tech, regime):
        return None
    if not tech.get("liquidity_sweep"):
        return None
    price = _price(tech)
    atr = _atr(tech)
    if not atr:
        return None

    # Side from sweep direction
    side = "LONG" if tech.get("sweep_down") else "SHORT"

    sl_cfg, tp_cfg = _get_sl_tp(cfg)
    sl_mult = float(sl_cfg.get("atr_mult", 1.0))
    tp_mult = float(tp_cfg.get("atr_mult", 1.5))

    # Regime tweaks
    sl_mult, tp_mult = _apply_regime_sl_tp_tweaks(sl_mult, tp_mult, regime)

    entry = (price - 0.5 * atr) if side == "LONG" else (price + 0.5 * atr)
    sl = (entry - sl_mult * atr) if side == "LONG" else (entry + sl_mult * atr)
    tp = (entry + tp_mult * atr) if side == "LONG" else (entry - tp_mult * atr)

    entry, sl, tp, notes = _sr_anchor(side, entry, sl, tp, symbol, tech)
    rr = _calc_rr(side, entry, sl, tp)
    pending_type = _pending_type_from_entry(side, entry, price)
    ttl_min = int(cfg.get("ttl_min", 0) or 0) or None

    ok, blocks = _respect_spread_and_news(tech)
    plan = StrategyPlan(
        symbol=symbol,
        strategy="liquidity_sweep_reversal",
        regime=regime,
        direction=side,
        pending_type=pending_type,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr,
        notes="Sweep + reversal at HTF level. " + "; ".join(notes),
        blocked_by=(blocks if not ok else []),
        preview_only=not ok,
        ttl_min=ttl_min,
    )
    return _attach_risk(plan, cfg, tech, symbol)


def strat_pattern_breakout_retest(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    cfg = _strat_cfg("pattern_breakout_retest", symbol=symbol, tech=tech, regime=regime)
    if not _allowed_here(cfg, tech, regime):
        return None
    patt = tech.get("pattern") or tech.get("patterns") or {}
    kind = (patt.get("type") or "").lower()
    allowed = set((cfg.get("patterns_any") or []) or ["triangle", "wedge", "rectangle"])
    if kind not in allowed:
        return None

    price = _price(tech)
    atr = _atr(tech)
    if not atr:
        return None

    side = "LONG" if tech.get("break_dir", "up") == "up" else "SHORT"
    brk = float(patt.get("break_level") or price)
    ret = float(patt.get("retest_level") or brk)

    sl_cfg, tp_cfg = _get_sl_tp(cfg)
    sl_mult = float(sl_cfg.get("atr_mult", 1.2))
    tp_mult = float(tp_cfg.get("atr_mult", 2.0))

    # Regime tweaks
    sl_mult, tp_mult = _apply_regime_sl_tp_tweaks(sl_mult, tp_mult, regime)

    entry = ret
    sl = entry - sl_mult * atr if side == "LONG" else entry + sl_mult * atr
    tp = entry + tp_mult * atr if side == "LONG" else entry - tp_mult * atr

    entry, sl, tp, notes = _sr_anchor(side, entry, sl, tp, symbol, tech)
    rr = _calc_rr(side, entry, sl, tp)
    pending_type = _pending_type_from_entry(side, entry, price)
    ttl_min = int(cfg.get("ttl_min", 0) or 0) or None

    ok, blocks = _respect_spread_and_news(tech)
    plan = StrategyPlan(
        symbol=symbol,
        strategy="pattern_breakout_retest",
        regime=regime,
        direction=side,
        pending_type=pending_type,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr,
        notes=f"{kind} breakout + retest. " + "; ".join(notes),
        blocked_by=(blocks if not ok else []),
        preview_only=not ok,
        ttl_min=ttl_min,
    )
    return _attach_risk(plan, cfg, tech, symbol)


def strat_hs_or_double_reversal(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    cfg = _strat_cfg("hs_or_double_reversal", symbol=symbol, tech=tech, regime=regime)
    if not _allowed_here(cfg, tech, regime):
        return None
    patt = tech.get("pattern") or tech.get("patterns") or {}
    kind = (patt.get("type") or "").lower()
    allowed = set(
        (cfg.get("patterns_any") or [])
        or ["head_shoulders", "double_top", "double_bottom"]
    )
    if kind not in allowed:
        return None

    side = "SHORT" if kind in {"head_shoulders", "double_top"} else "LONG"
    price = _price(tech)
    atr = _atr(tech)
    if not atr:
        return None

    neckline = float(patt.get("neckline") or price)
    ret = float(patt.get("retest_level") or neckline)

    sl_cfg, tp_cfg = _get_sl_tp(cfg)
    sl_mult = float(sl_cfg.get("atr_mult", 1.2))
    tp_mult = float(tp_cfg.get("atr_mult", 2.0))

    # Regime tweaks
    sl_mult, tp_mult = _apply_regime_sl_tp_tweaks(sl_mult, tp_mult, regime)

    entry = ret
    sl = (entry + sl_mult * atr) if side == "SHORT" else (entry - sl_mult * atr)
    tp = (entry - tp_mult * atr) if side == "SHORT" else (entry + tp_mult * atr)

    entry, sl, tp, notes = _sr_anchor(side, entry, sl, tp, symbol, tech)
    rr = _calc_rr(side, entry, sl, tp)
    pending_type = _pending_type_from_entry(side, entry, price)
    ttl_min = int(cfg.get("ttl_min", 0) or 0) or None

    ok, blocks = _respect_spread_and_news(tech)
    plan = StrategyPlan(
        symbol=symbol,
        strategy="hs_or_double_reversal",
        regime=regime,
        direction=side,
        pending_type=pending_type,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr,
        notes=f"{kind} neckline retest.",
        blocked_by=(blocks if not ok else []),
        preview_only=not ok,
        ttl_min=ttl_min,
    )
    return _attach_risk(plan, cfg, tech, symbol)


# ==============================================================================
# High-Priority SMC Strategies (Phase 1)
# ==============================================================================

def strat_order_block_rejection(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    """
    Order Block Rejection Strategy
    
    Entry: Retest of order block zone (bullish/bearish OB)
    SL: Beyond OB zone (0.8-1.0x ATR)
    TP: Target next structure level or 1.5-2.0x ATR
    """
    # Early exit: Check feature flag
    if not _is_strategy_enabled("order_block_rejection"):
        return None
    
    # Early exit: Check required fields (at least one OB must exist)
    ob_bull = tech.get("order_block_bull")
    ob_bear = tech.get("order_block_bear")
    if not ob_bull and not ob_bear:
        return None
    
    # Early exit: Check confidence threshold
    if not _meets_confidence_threshold(tech, "order_block_rejection"):
        return None
    
    cfg = _strat_cfg("order_block_rejection", symbol=symbol, tech=tech, regime=regime)
    if not _allowed_here(cfg, tech, regime):
        return None
    
    price = _price(tech)
    atr = _atr(tech)
    if not atr or not price:
        return None
    
    # Determine direction: prioritize by proximity to current price or strength
    ob_strength = tech.get("ob_strength", 0.5)
    side = None
    ob_level = None
    
    if ob_bull and ob_bear:
        # Both exist - choose based on proximity to current price
        dist_bull = abs(float(ob_bull) - price)
        dist_bear = abs(float(ob_bear) - price)
        if dist_bull <= dist_bear:
            side = "LONG"
            ob_level = float(ob_bull)
        else:
            side = "SHORT"
            ob_level = float(ob_bear)
    elif ob_bull:
        side = "LONG"
        ob_level = float(ob_bull)
    elif ob_bear:
        side = "SHORT"
        ob_level = float(ob_bear)
    
    if not side or not ob_level:
        return None
    
    # Get SL/TP configuration
    sl_cfg, tp_cfg = _get_sl_tp(cfg)
    sl_mult = float(sl_cfg.get("atr_mult", 0.9))
    tp_mult = float(tp_cfg.get("atr_mult", 1.8))
    
    # Regime tweaks
    sl_mult, tp_mult = _apply_regime_sl_tp_tweaks(sl_mult, tp_mult, regime)
    
    # Entry: At OB level (or slightly inside for better fill)
    entry = ob_level
    
    # SL: Beyond OB zone (0.8-1.0x ATR from entry)
    if side == "LONG":
        sl = entry - sl_mult * atr
        tp = entry + tp_mult * atr
    else:
        sl = entry + sl_mult * atr
        tp = entry - tp_mult * atr
    
    # Apply S/R anchoring
    entry, sl, tp, notes = _sr_anchor(side, entry, sl, tp, symbol, tech)
    rr = _calc_rr(side, entry, sl, tp)
    pending_type = _pending_type_from_entry(side, entry, price)
    ttl_min = int(cfg.get("ttl_min", 0) or 0) or None
    
    # Check spread and news
    ok, blocks = _respect_spread_and_news(tech)
    
    # Build notes
    confluence = tech.get("ob_confluence", [])
    confluence_str = f"Confluence: {', '.join(confluence)}" if confluence else ""
    notes_str = f"Order Block {side} rejection at {fmt_price(symbol, ob_level)}. Strength: {ob_strength:.2f}. {confluence_str}"
    if notes:
        notes_str += "; " + "; ".join(notes)
    
    plan = StrategyPlan(
        symbol=symbol,
        strategy="order_block_rejection",
        regime=regime,
        direction=side,
        pending_type=pending_type,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr,
        notes=notes_str,
        blocked_by=(blocks if not ok else []),
        preview_only=not ok,
        ttl_min=ttl_min,
    )
    return _attach_risk(plan, cfg, tech, symbol)


def strat_fvg_retracement(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    """
    FVG Retracement Strategy
    
    Entry: When FVG is 50-75% filled (retracement into zone)
    SL: Beyond FVG zone (0.8-1.0x ATR)
    TP: Target next structure level or 1.5-2.0x ATR
    """
    # Early exit: Check feature flag
    if not _is_strategy_enabled("fvg_retracement"):
        return None
    
    # Early exit: Check required fields
    fvg_bull = tech.get("fvg_bull")
    fvg_bear = tech.get("fvg_bear")
    if not fvg_bull and not fvg_bear:
        return None
    
    # Early exit: Check confidence threshold
    if not _meets_confidence_threshold(tech, "fvg_retracement"):
        return None
    
    cfg = _strat_cfg("fvg_retracement", symbol=symbol, tech=tech, regime=regime)
    if not _allowed_here(cfg, tech, regime):
        return None
    
    price = _price(tech)
    atr = _atr(tech)
    if not atr or not price:
        return None
    
    # Check FVG fill percentage (50-75% is optimal for retracement entry)
    fvg_filled_pct = tech.get("fvg_filled_pct", 0.0)
    min_fill = float(cfg.get("min_fill_pct", 50.0))
    max_fill = float(cfg.get("max_fill_pct", 75.0))
    
    if fvg_filled_pct < min_fill or fvg_filled_pct > max_fill:
        return None  # Not in optimal fill range
    
    # Determine direction and FVG zone
    side = None
    fvg_zone = None
    
    if fvg_bull and isinstance(fvg_bull, dict):
        filled_pct = fvg_bull.get("filled_pct", 0.0)
        if min_fill <= filled_pct <= max_fill:
            side = "LONG"
            fvg_zone = fvg_bull
    
    if fvg_bear and isinstance(fvg_bear, dict) and not side:
        filled_pct = fvg_bear.get("filled_pct", 0.0)
        if min_fill <= filled_pct <= max_fill:
            side = "SHORT"
            fvg_zone = fvg_bear
    
    if not side or not fvg_zone:
        return None
    
    # Get FVG zone boundaries
    zone_high = float(fvg_zone.get("high", 0))
    zone_low = float(fvg_zone.get("low", 0))
    if zone_high <= zone_low:
        return None
    
    # Get SL/TP configuration
    sl_cfg, tp_cfg = _get_sl_tp(cfg)
    sl_mult = float(sl_cfg.get("atr_mult", 0.8))
    tp_mult = float(tp_cfg.get("atr_mult", 1.5))
    
    # Regime tweaks
    sl_mult, tp_mult = _apply_regime_sl_tp_tweaks(sl_mult, tp_mult, regime)
    
    # Entry: Current price (price is already in zone at 50-75% fill)
    entry = price
    
    # SL: Beyond FVG zone
    if side == "LONG":
        sl = zone_low - sl_mult * atr
        tp = entry + tp_mult * atr
    else:
        sl = zone_high + sl_mult * atr
        tp = entry - tp_mult * atr
    
    # Apply S/R anchoring
    entry, sl, tp, notes = _sr_anchor(side, entry, sl, tp, symbol, tech)
    rr = _calc_rr(side, entry, sl, tp)
    pending_type = _pending_type_from_entry(side, entry, price)
    ttl_min = int(cfg.get("ttl_min", 0) or 0) or None
    
    # Check spread and news
    ok, blocks = _respect_spread_and_news(tech)
    
    # Build notes
    fvg_strength = tech.get("fvg_strength", 0.5)
    confluence = tech.get("fvg_confluence", [])
    confluence_str = f"Confluence: {', '.join(confluence)}" if confluence else ""
    notes_str = f"FVG {side} retracement. Fill: {fvg_filled_pct:.1f}%. Strength: {fvg_strength:.2f}. {confluence_str}"
    if notes:
        notes_str += "; " + "; ".join(notes)
    
    plan = StrategyPlan(
        symbol=symbol,
        strategy="fvg_retracement",
        regime=regime,
        direction=side,
        pending_type=pending_type,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr,
        notes=notes_str,
        blocked_by=(blocks if not ok else []),
        preview_only=not ok,
        ttl_min=ttl_min,
    )
    return _attach_risk(plan, cfg, tech, symbol)


def strat_breaker_block(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    """
    Breaker Block Strategy
    
    Entry: Retest of broken order block (flipped support/resistance)
    SL: Beyond breaker block zone (1.0-1.2x ATR)
    TP: Target next structure level or 1.8-2.5x ATR
    """
    # Early exit: Check feature flag
    if not _is_strategy_enabled("breaker_block"):
        return None
    
    # Early exit: Check required fields
    breaker_bull = tech.get("breaker_block_bull")
    breaker_bear = tech.get("breaker_block_bear")
    ob_broken = tech.get("ob_broken", False)
    price_retesting = tech.get("price_retesting_breaker", False)
    
    if not breaker_bull and not breaker_bear:
        return None
    if not ob_broken or not price_retesting:
        return None
    
    # Early exit: Check confidence threshold
    if not _meets_confidence_threshold(tech, "breaker_block"):
        return None
    
    cfg = _strat_cfg("breaker_block", symbol=symbol, tech=tech, regime=regime)
    if not _allowed_here(cfg, tech, regime):
        return None
    
    price = _price(tech)
    atr = _atr(tech)
    if not atr or not price:
        return None
    
    # Determine direction
    side = None
    breaker_level = None
    
    if breaker_bull and breaker_bear:
        # Both exist - choose based on proximity
        dist_bull = abs(float(breaker_bull) - price)
        dist_bear = abs(float(breaker_bear) - price)
        if dist_bull <= dist_bear:
            side = "LONG"
            breaker_level = float(breaker_bull)
        else:
            side = "SHORT"
            breaker_level = float(breaker_bear)
    elif breaker_bull:
        side = "LONG"
        breaker_level = float(breaker_bull)
    elif breaker_bear:
        side = "SHORT"
        breaker_level = float(breaker_bear)
    
    if not side or not breaker_level:
        return None
    
    # Get SL/TP configuration
    sl_cfg, tp_cfg = _get_sl_tp(cfg)
    sl_mult = float(sl_cfg.get("atr_mult", 1.0))
    tp_mult = float(tp_cfg.get("atr_mult", 2.0))
    
    # Regime tweaks
    sl_mult, tp_mult = _apply_regime_sl_tp_tweaks(sl_mult, tp_mult, regime)
    
    # Entry: At breaker block level
    entry = breaker_level
    
    # SL: Beyond breaker block zone (wider than regular OB)
    if side == "LONG":
        sl = entry - sl_mult * atr
        tp = entry + tp_mult * atr
    else:
        sl = entry + sl_mult * atr
        tp = entry - tp_mult * atr
    
    # Apply S/R anchoring
    entry, sl, tp, notes = _sr_anchor(side, entry, sl, tp, symbol, tech)
    rr = _calc_rr(side, entry, sl, tp)
    pending_type = _pending_type_from_entry(side, entry, price)
    ttl_min = int(cfg.get("ttl_min", 0) or 0) or None
    
    # Check spread and news
    ok, blocks = _respect_spread_and_news(tech)
    
    # Build notes
    breaker_strength = tech.get("breaker_block_strength", 0.5)
    notes_str = f"Breaker Block {side} at {fmt_price(symbol, breaker_level)}. OB broken + retest. Strength: {breaker_strength:.2f}."
    if notes:
        notes_str += "; " + "; ".join(notes)
    
    plan = StrategyPlan(
        symbol=symbol,
        strategy="breaker_block",
        regime=regime,
        direction=side,
        pending_type=pending_type,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr,
        notes=notes_str,
        blocked_by=(blocks if not ok else []),
        preview_only=not ok,
        ttl_min=ttl_min,
    )
    return _attach_risk(plan, cfg, tech, symbol)


def strat_market_structure_shift(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    """
    Market Structure Shift (MSS) Strategy
    
    Entry: Pullback to MSS break level after structure shift
    SL: Beyond MSS level (1.0-1.2x ATR)
    TP: Target next structure level or 1.8-2.5x ATR
    """
    # Early exit: Check feature flag
    if not _is_strategy_enabled("market_structure_shift"):
        return None
    
    # Early exit: Check required fields
    mss_bull = tech.get("mss_bull", False)
    mss_bear = tech.get("mss_bear", False)
    pullback_to_mss = tech.get("pullback_to_mss", False)
    mss_level = tech.get("mss_level", 0.0)
    
    if not (mss_bull or mss_bear):
        return None
    if not pullback_to_mss or not mss_level:
        return None
    
    # Early exit: Check confidence threshold
    if not _meets_confidence_threshold(tech, "market_structure_shift"):
        return None
    
    cfg = _strat_cfg("market_structure_shift", symbol=symbol, tech=tech, regime=regime)
    if not _allowed_here(cfg, tech, regime):
        return None
    
    price = _price(tech)
    atr = _atr(tech)
    if not atr or not price:
        return None
    
    # Determine direction
    side = "LONG" if mss_bull else "SHORT"
    
    # Get SL/TP configuration
    sl_cfg, tp_cfg = _get_sl_tp(cfg)
    sl_mult = float(sl_cfg.get("atr_mult", 1.0))
    tp_mult = float(tp_cfg.get("atr_mult", 2.0))
    
    # Regime tweaks
    sl_mult, tp_mult = _apply_regime_sl_tp_tweaks(sl_mult, tp_mult, regime)
    
    # Entry: At MSS level (pullback entry)
    entry = float(mss_level)
    
    # SL: Beyond MSS level
    if side == "LONG":
        sl = entry - sl_mult * atr
        tp = entry + tp_mult * atr
    else:
        sl = entry + sl_mult * atr
        tp = entry - tp_mult * atr
    
    # Apply S/R anchoring
    entry, sl, tp, notes = _sr_anchor(side, entry, sl, tp, symbol, tech)
    rr = _calc_rr(side, entry, sl, tp)
    pending_type = _pending_type_from_entry(side, entry, price)
    ttl_min = int(cfg.get("ttl_min", 0) or 0) or None
    
    # Check spread and news
    ok, blocks = _respect_spread_and_news(tech)
    
    # Build notes
    mss_strength = tech.get("mss_strength", 0.5)
    notes_str = f"MSS {side} pullback at {fmt_price(symbol, mss_level)}. Structure shift confirmed. Strength: {mss_strength:.2f}."
    if notes:
        notes_str += "; " + "; ".join(notes)
    
    plan = StrategyPlan(
        symbol=symbol,
        strategy="market_structure_shift",
        regime=regime,
        direction=side,
        pending_type=pending_type,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr,
        notes=notes_str,
        blocked_by=(blocks if not ok else []),
        preview_only=not ok,
        ttl_min=ttl_min,
    )
    return _attach_risk(plan, cfg, tech, symbol)


def strat_inducement_reversal(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    """
    Inducement + Reversal Strategy
    
    Entry: After liquidity grab and rejection back into structure
    SL: Beyond liquidity grab level (1.0-1.2x ATR)
    TP: Target next structure level or 1.5-2.0x ATR
    """
    # Early exit: Check feature flag
    if not _is_strategy_enabled("inducement_reversal"):
        return None
    
    # Early exit: Check required fields
    liquidity_grab_bull = tech.get("liquidity_grab_bull", False)
    liquidity_grab_bear = tech.get("liquidity_grab_bear", False)
    rejection_detected = tech.get("rejection_detected", False)
    
    if not rejection_detected:
        return None
    if not liquidity_grab_bull and not liquidity_grab_bear:
        return None
    
    # Early exit: Check confidence threshold
    if not _meets_confidence_threshold(tech, "inducement_reversal"):
        return None
    
    # Require confluence (OB or FVG) for higher probability
    order_block_present = tech.get("order_block", False)
    fvg_present = bool(tech.get("fvg_bull") or tech.get("fvg_bear"))
    
    if not order_block_present and not fvg_present:
        return None  # Require at least one confluence factor
    
    cfg = _strat_cfg("inducement_reversal", symbol=symbol, tech=tech, regime=regime)
    if not _allowed_here(cfg, tech, regime):
        return None
    
    price = _price(tech)
    atr = _atr(tech)
    if not atr or not price:
        return None
    
    # Determine direction from rejection
    side = None
    rejection_strength = tech.get("rejection_strength", 0.5)
    
    if liquidity_grab_bull:
        side = "LONG"  # Bullish liquidity grab + rejection = LONG
    elif liquidity_grab_bear:
        side = "SHORT"  # Bearish liquidity grab + rejection = SHORT
    
    if not side:
        return None
    
    # Get SL/TP configuration
    sl_cfg, tp_cfg = _get_sl_tp(cfg)
    sl_mult = float(sl_cfg.get("atr_mult", 1.0))
    tp_mult = float(tp_cfg.get("atr_mult", 1.8))
    
    # Regime tweaks
    sl_mult, tp_mult = _apply_regime_sl_tp_tweaks(sl_mult, tp_mult, regime)
    
    # Entry: After rejection (current price or slightly inside structure)
    entry = price
    
    # SL: Beyond liquidity grab level
    if side == "LONG":
        sl = entry - sl_mult * atr
        tp = entry + tp_mult * atr
    else:
        sl = entry + sl_mult * atr
        tp = entry - tp_mult * atr
    
    # Apply S/R anchoring
    entry, sl, tp, notes = _sr_anchor(side, entry, sl, tp, symbol, tech)
    rr = _calc_rr(side, entry, sl, tp)
    pending_type = _pending_type_from_entry(side, entry, price)
    ttl_min = int(cfg.get("ttl_min", 0) or 0) or None
    
    # Check spread and news
    ok, blocks = _respect_spread_and_news(tech)
    
    # Build notes
    confluence_factors = []
    if order_block_present:
        confluence_factors.append("OB")
    if fvg_present:
        confluence_factors.append("FVG")
    confluence_str = f"Confluence: {', '.join(confluence_factors)}" if confluence_factors else ""
    notes_str = f"Inducement {side} reversal. Liquidity grab + rejection. Strength: {rejection_strength:.2f}. {confluence_str}"
    if notes:
        notes_str += "; " + "; ".join(notes)
    
    plan = StrategyPlan(
        symbol=symbol,
        strategy="inducement_reversal",
        regime=regime,
        direction=side,
        pending_type=pending_type,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr,
        notes=notes_str,
        blocked_by=(blocks if not ok else []),
        preview_only=not ok,
        ttl_min=ttl_min,
    )
    return _attach_risk(plan, cfg, tech, symbol)


def strat_mitigation_block(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    """
    Mitigation Block Strategy
    
    Entry: Last bullish/bearish candle before structure break
    SL: Beyond mitigation block zone (1.0-1.2x ATR)
    TP: Target next structure level or 1.5-2.0x ATR
    """
    # Early exit: Check feature flag
    if not _is_strategy_enabled("mitigation_block"):
        return None
    
    # Early exit: Check required fields
    mitigation_bull = tech.get("mitigation_block_bull")
    mitigation_bear = tech.get("mitigation_block_bear")
    structure_broken = tech.get("structure_broken", False)
    
    if not mitigation_bull and not mitigation_bear:
        return None
    if not structure_broken:
        return None
    
    # Early exit: Check confidence threshold
    if not _meets_confidence_threshold(tech, "mitigation_block"):
        return None
    
    cfg = _strat_cfg("mitigation_block", symbol=symbol, tech=tech, regime=regime)
    if not _allowed_here(cfg, tech, regime):
        return None
    
    price = _price(tech)
    atr = _atr(tech)
    if not atr or not price:
        return None
    
    # Determine direction
    side = None
    mitigation_level = None
    
    if mitigation_bull and mitigation_bear:
        # Both exist - choose based on proximity
        dist_bull = abs(float(mitigation_bull) - price)
        dist_bear = abs(float(mitigation_bear) - price)
        if dist_bull <= dist_bear:
            side = "LONG"
            mitigation_level = float(mitigation_bull)
        else:
            side = "SHORT"
            mitigation_level = float(mitigation_bear)
    elif mitigation_bull:
        side = "LONG"
        mitigation_level = float(mitigation_bull)
    elif mitigation_bear:
        side = "SHORT"
        mitigation_level = float(mitigation_bear)
    
    if not side or not mitigation_level:
        return None
    
    # Get SL/TP configuration
    sl_cfg, tp_cfg = _get_sl_tp(cfg)
    sl_mult = float(sl_cfg.get("atr_mult", 1.0))
    tp_mult = float(tp_cfg.get("atr_mult", 1.8))
    
    # Regime tweaks
    sl_mult, tp_mult = _apply_regime_sl_tp_tweaks(sl_mult, tp_mult, regime)
    
    # Entry: At mitigation block level
    entry = mitigation_level
    
    # SL: Beyond mitigation block zone
    if side == "LONG":
        sl = entry - sl_mult * atr
        tp = entry + tp_mult * atr
    else:
        sl = entry + sl_mult * atr
        tp = entry - tp_mult * atr
    
    # Apply S/R anchoring
    entry, sl, tp, notes = _sr_anchor(side, entry, sl, tp, symbol, tech)
    rr = _calc_rr(side, entry, sl, tp)
    pending_type = _pending_type_from_entry(side, entry, price)
    ttl_min = int(cfg.get("ttl_min", 0) or 0) or None
    
    # Check spread and news
    ok, blocks = _respect_spread_and_news(tech)
    
    # Build notes
    mitigation_strength = tech.get("mitigation_block_strength", 0.5)
    fvg_present = bool(tech.get("fvg_bull") or tech.get("fvg_bear"))
    fvg_note = " + FVG confluence" if fvg_present else ""
    notes_str = f"Mitigation Block {side} at {fmt_price(symbol, mitigation_level)}. Structure broken. Strength: {mitigation_strength:.2f}.{fvg_note}"
    if notes:
        notes_str += "; " + "; ".join(notes)
    
    plan = StrategyPlan(
        symbol=symbol,
        strategy="mitigation_block",
        regime=regime,
        direction=side,
        pending_type=pending_type,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr,
        notes=notes_str,
        blocked_by=(blocks if not ok else []),
        preview_only=not ok,
        ttl_min=ttl_min,
    )
    return _attach_risk(plan, cfg, tech, symbol)


def strat_premium_discount_array(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    """
    Premium/Discount Array Strategy
    
    Entry: When price is in discount zone (0.62-0.79 fib) for LONG or premium zone (0.21-0.38 fib) for SHORT
    SL: Beyond zone (0.8-1.0x ATR)
    TP: Target opposite zone or 1.5-2.0x ATR
    """
    # Early exit: Check feature flag
    if not _is_strategy_enabled("premium_discount_array"):
        return None
    
    # Early exit: Check required fields
    price_in_discount = tech.get("price_in_discount", False)
    price_in_premium = tech.get("price_in_premium", False)
    fib_levels = tech.get("fib_levels", {})
    
    if not price_in_discount and not price_in_premium:
        return None
    if not fib_levels:
        return None
    
    # Early exit: Check confidence threshold
    if not _meets_confidence_threshold(tech, "premium_discount_array"):
        return None
    
    cfg = _strat_cfg("premium_discount_array", symbol=symbol, tech=tech, regime=regime)
    if not _allowed_here(cfg, tech, regime):
        return None
    
    price = _price(tech)
    atr = _atr(tech)
    if not atr or not price:
        return None
    
    # Determine direction
    side = None
    fib_level = tech.get("fib_level", 0.0)
    
    if price_in_discount:
        side = "LONG"  # Price in discount zone (0.62-0.79) = buy opportunity
    elif price_in_premium:
        side = "SHORT"  # Price in premium zone (0.21-0.38) = sell opportunity
    
    if not side:
        return None
    
    # Get SL/TP configuration
    sl_cfg, tp_cfg = _get_sl_tp(cfg)
    sl_mult = float(sl_cfg.get("atr_mult", 0.9))
    tp_mult = float(tp_cfg.get("atr_mult", 1.8))
    
    # Regime tweaks
    sl_mult, tp_mult = _apply_regime_sl_tp_tweaks(sl_mult, tp_mult, regime)
    
    # Entry: Current price (price is already in the zone)
    entry = price
    
    # SL: Beyond zone
    if side == "LONG":
        sl = entry - sl_mult * atr
        tp = entry + tp_mult * atr
    else:
        sl = entry + sl_mult * atr
        tp = entry - tp_mult * atr
    
    # Apply S/R anchoring
    entry, sl, tp, notes = _sr_anchor(side, entry, sl, tp, symbol, tech)
    rr = _calc_rr(side, entry, sl, tp)
    pending_type = _pending_type_from_entry(side, entry, price)
    ttl_min = int(cfg.get("ttl_min", 0) or 0) or None
    
    # Check spread and news
    ok, blocks = _respect_spread_and_news(tech)
    
    # Build notes
    fib_strength = tech.get("fib_strength", 0.5)
    zone = "discount (0.62-0.79)" if side == "LONG" else "premium (0.21-0.38)"
    notes_str = f"Premium/Discount {side} at {zone} fib zone. Fib level: {fib_level:.3f}. Strength: {fib_strength:.2f}."
    if notes:
        notes_str += "; " + "; ".join(notes)
    
    plan = StrategyPlan(
        symbol=symbol,
        strategy="premium_discount_array",
        regime=regime,
        direction=side,
        pending_type=pending_type,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr,
        notes=notes_str,
        blocked_by=(blocks if not ok else []),
        preview_only=not ok,
        ttl_min=ttl_min,
    )
    return _attach_risk(plan, cfg, tech, symbol)


def strat_kill_zone(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    """
    Kill Zone Strategy
    
    Entry: During high volatility windows (London/NY open)
    SL: 0.8-1.0x ATR (tighter during volatility)
    TP: 1.5-2.0x ATR
    """
    # Early exit: Check feature flag
    if not _is_strategy_enabled("kill_zone"):
        return None
    
    # Early exit: Check required fields
    kill_zone_active = tech.get("kill_zone_active", False)
    session = tech.get("session", "").upper()
    
    if not kill_zone_active:
        return None
    
    # Early exit: Check confidence threshold (kill zone is time-based, no confidence score)
    # Skip confidence check for kill zone as it's time-based
    
    cfg = _strat_cfg("kill_zone", symbol=symbol, tech=tech, regime=regime)
    if not _allowed_here(cfg, tech, regime):
        return None
    
    price = _price(tech)
    atr = _atr(tech)
    if not atr or not price:
        return None
    
    # Determine direction from structure/trend during kill zone
    # Use existing direction helpers or structure signals
    choch_bull = tech.get("choch_bull", False)
    choch_bear = tech.get("choch_bear", False)
    bos_bull = tech.get("bos_bull", False)
    bos_bear = tech.get("bos_bear", False)
    
    side = None
    if bos_bull or choch_bull:
        side = "LONG"
    elif bos_bear or choch_bear:
        side = "SHORT"
    else:
        # Fallback: use trend direction if available
        trend = tech.get("trend", "").upper()
        if "UP" in trend or "BULL" in trend:
            side = "LONG"
        elif "DOWN" in trend or "BEAR" in trend:
            side = "SHORT"
    
    if not side:
        return None  # Need structure confirmation during kill zone
    
    # Get SL/TP configuration
    sl_cfg, tp_cfg = _get_sl_tp(cfg)
    sl_mult = float(sl_cfg.get("atr_mult", 0.9))
    tp_mult = float(tp_cfg.get("atr_mult", 1.8))
    
    # Regime tweaks
    sl_mult, tp_mult = _apply_regime_sl_tp_tweaks(sl_mult, tp_mult, regime)
    
    # Entry: Current price during kill zone
    entry = price
    
    # SL: Tighter during volatility
    if side == "LONG":
        sl = entry - sl_mult * atr
        tp = entry + tp_mult * atr
    else:
        sl = entry + sl_mult * atr
        tp = entry - tp_mult * atr
    
    # Apply S/R anchoring
    entry, sl, tp, notes = _sr_anchor(side, entry, sl, tp, symbol, tech)
    rr = _calc_rr(side, entry, sl, tp)
    pending_type = _pending_type_from_entry(side, entry, price)
    ttl_min = int(cfg.get("ttl_min", 0) or 0) or None
    
    # Check spread and news
    ok, blocks = _respect_spread_and_news(tech)
    
    # Build notes
    notes_str = f"Kill Zone {side} during {session} session. High volatility window."
    if notes:
        notes_str += "; " + "; ".join(notes)
    
    plan = StrategyPlan(
        symbol=symbol,
        strategy="kill_zone",
        regime=regime,
        direction=side,
        pending_type=pending_type,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr,
        notes=notes_str,
        blocked_by=(blocks if not ok else []),
        preview_only=not ok,
        ttl_min=ttl_min,
    )
    return _attach_risk(plan, cfg, tech, symbol)


def strat_session_liquidity_run(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    """
    Session Liquidity Run Strategy
    
    Entry: After sweep of Asian session highs/lows during London + reversal
    SL: Beyond Asian session high/low (1.0-1.2x ATR)
    TP: Target next structure level or 1.5-2.0x ATR
    """
    # Early exit: Check feature flag
    if not _is_strategy_enabled("session_liquidity_run"):
        return None
    
    # Early exit: Check required fields
    session_liquidity_run = tech.get("session_liquidity_run", False)
    asian_session_high = tech.get("asian_session_high")
    asian_session_low = tech.get("asian_session_low")
    london_session_active = tech.get("london_session_active", False)
    
    if not session_liquidity_run:
        return None
    if not london_session_active:
        return None
    if not asian_session_high and not asian_session_low:
        return None
    
    # Early exit: Check confidence threshold
    if not _meets_confidence_threshold(tech, "session_liquidity_run"):
        return None
    
    cfg = _strat_cfg("session_liquidity_run", symbol=symbol, tech=tech, regime=regime)
    if not _allowed_here(cfg, tech, regime):
        return None
    
    price = _price(tech)
    atr = _atr(tech)
    if not atr or not price:
        return None
    
    # Determine direction from sweep
    side = None
    liquidity_level = None
    
    # Check if price swept Asian session high (bearish) or low (bullish)
    if asian_session_high and price >= float(asian_session_high):
        # Swept high, expect reversal down
        side = "SHORT"
        liquidity_level = float(asian_session_high)
    elif asian_session_low and price <= float(asian_session_low):
        # Swept low, expect reversal up
        side = "LONG"
        liquidity_level = float(asian_session_low)
    
    if not side or not liquidity_level:
        return None
    
    # Require reversal confirmation (CHOCH/BOS)
    if side == "LONG" and not (tech.get("choch_bull") or tech.get("bos_bull")):
        return None
    if side == "SHORT" and not (tech.get("choch_bear") or tech.get("bos_bear")):
        return None
    
    # Get SL/TP configuration
    sl_cfg, tp_cfg = _get_sl_tp(cfg)
    sl_mult = float(sl_cfg.get("atr_mult", 1.0))
    tp_mult = float(tp_cfg.get("atr_mult", 1.8))
    
    # Regime tweaks
    sl_mult, tp_mult = _apply_regime_sl_tp_tweaks(sl_mult, tp_mult, regime)
    
    # Entry: After sweep + reversal (current price)
    entry = price
    
    # SL: Beyond Asian session high/low
    if side == "LONG":
        sl = entry - sl_mult * atr
        tp = entry + tp_mult * atr
    else:
        sl = entry + sl_mult * atr
        tp = entry - tp_mult * atr
    
    # Apply S/R anchoring
    entry, sl, tp, notes = _sr_anchor(side, entry, sl, tp, symbol, tech)
    rr = _calc_rr(side, entry, sl, tp)
    pending_type = _pending_type_from_entry(side, entry, price)
    ttl_min = int(cfg.get("ttl_min", 0) or 0) or None
    
    # Check spread and news
    ok, blocks = _respect_spread_and_news(tech)
    
    # Build notes
    session_liquidity_strength = tech.get("session_liquidity_strength", 0.5)
    target = "Asian high" if side == "SHORT" else "Asian low"
    notes_str = f"Session Liquidity Run {side}. Swept {target} during London. Reversal confirmed. Strength: {session_liquidity_strength:.2f}."
    if notes:
        notes_str += "; " + "; ".join(notes)
    
    plan = StrategyPlan(
        symbol=symbol,
        strategy="session_liquidity_run",
        regime=regime,
        direction=side,
        pending_type=pending_type,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=rr,
        notes=notes_str,
        blocked_by=(blocks if not ok else []),
        preview_only=not ok,
        ttl_min=ttl_min,
    )
    return _attach_risk(plan, cfg, tech, symbol)


# ---------------- Registry ----------------------------------------------------
# Phase 3: Complete SMC Strategy Priority Hierarchy
# Priority order: Tier 1 (highest confluence) → Tier 5 (lower priority)

_REGISTRY = [
    # 🥇 TIER 1: Highest Confluence (Institutional Footprints)
    strat_order_block_rejection,      # Order blocks - institutional zones
    strat_breaker_block,              # Failed OB - flipped zones (higher probability)
    strat_market_structure_shift,     # MSS - trend change confirmation
    
    # 🥈 TIER 2: High Confluence (Smart Money Patterns)
    strat_fvg_retracement,            # FVG retracement - after CHOCH/BOS
    strat_mitigation_block,            # Mitigation block - before structure break
    strat_inducement_reversal,        # Liquidity grab + rejection + OB/FVG
    
    # 🥉 TIER 3: Medium-High Confluence
    strat_liquidity_sweep_reversal,   # Liquidity sweep - stop hunt reversal
    strat_session_liquidity_run,      # Session liquidity runs
    
    # 🏅 TIER 4: Medium Confluence
    strat_trend_pullback_ema,         # Trend continuation pullback
    strat_premium_discount_array,     # Premium/discount zones
    
    # ⚪ TIER 5: Lower Priority
    strat_pattern_breakout_retest,
    strat_opening_range_breakout,
    strat_range_fade_sr,
    strat_hs_or_double_reversal,
    strat_kill_zone,                  # Time-based (lower priority than structure)
    # Note: Inside Bar Volatility Trap (IBVT) is NOT in registry - handled separately
    # by ChatGPT/VolatilityStrategySelector as last resort fallback
]


# --------- Global RR floor helper (reads session overrides if present) --------


# ---------------- Regime-level RR floor with session overrides ----------------
def _global_rr_floor_from_map(tech: Dict[str, Any]) -> float:
    try:
        mp = _load_strategy_map() or {}
        rg = mp.get("regime") or {}
        base = float(rg.get("rr_floor", getattr(settings, "MIN_RR_FOR_PENDINGS", 1.3)))
        ses = _session_from_tech(tech)
        so = rg.get("session_overrides") or {}
        if isinstance(so, dict):
            s_cfg = so.get(ses) or {}
            if isinstance(s_cfg, dict) and "rr_floor" in s_cfg:
                base = float(s_cfg["rr_floor"])
        return base
    except Exception:
        try:
            return float(getattr(settings, "MIN_RR_FOR_PENDINGS", 1.3))
        except Exception:
            return 1.3


# ---------------- Main builder -----------------------------------------------


def choose_and_build(
    symbol: str,
    tech: Dict[str, Any],
    mode: Literal["market", "pending"] = "pending",
) -> Optional["StrategyPlan"]:
    """
    Build a strategy plan. In `pending` mode, return a STOP/LIMIT (or OCO) plan.
    In `market` mode, convert the best acceptable plan into a MARKET plan.
    """
    # --- debug visibility: what data do we have?
    try:
        logger.debug("TECH KEYS: %s", sorted(list(tech.keys())))
        m15_blob = tech.get("M15") or tech.get("_tf_M15") or tech.get("m15") or {}
        h1_blob = tech.get("H1") or tech.get("_tf_H1") or tech.get("h1") or {}
        logger.debug("M15 KEYS: %s", list(m15_blob.keys())[:30])
        logger.debug("H1 KEYS: %s", list(h1_blob.keys())[:30])
    except Exception:
        pass

    regime = str(tech.get("regime") or tech.get("regime_label") or "UNKNOWN").upper()
    logger.debug("choose_and_build: symbol=%s regime=%s mode=%s", symbol, regime, mode)
    print(f"[PRINT] choose_and_build called for {symbol} regime={regime} mode={mode}")

    # Global RR floor (map + session overrides)
    global_rr_floor = _global_rr_floor_from_map(tech)
    mode = (mode or "pending").lower()

    for fn in _REGISTRY:
        plan = None
        try:
            plan = fn(symbol, tech, regime)
            logger.debug("strategy %s -> %s", fn.__name__, "PLAN" if plan else "None")
        except Exception as e:
            logger.exception("strategy %s raised: %s", fn.__name__, e)
            continue

        if not plan:
            continue

        # Normalize direction and then classify pending type (for pending mode)
        plan = _coerce_direction_if_misfit(plan)

        # Skip OCO in market mode (not meaningful for market execution)
        if mode == "market" and (
            (getattr(plan, "pending_type", "") or "").upper().startswith("OCO")
        ):
            logger.debug(
                "skip OCO plan in market mode: %s", getattr(plan, "strategy", "")
            )
            continue

        if mode == "pending":
            plan = _finalise_pending_type(plan, tech)

        
        # Phase2 global gates (unconditional)
        plan = _phase2_apply_gates(plan, tech, mode=mode)

        # Per-strategy RR floor (symbol + session merges already in _strat_cfg)
        strat_name = getattr(plan, "strategy", "")
        rr_floor = _rr_floor_for(strat_name, symbol, tech, global_rr_floor)

        pt = (getattr(plan, "pending_type", "") or "").upper()

        # Allow previews (blocked_by reasons) to flow up for UI, but don't accept as executable
        if getattr(plan, "preview_only", False):
            logger.debug("plan %s is preview_only; returning as preview.", strat_name)
            print(
                f"[PRINT] preview_only plan {strat_name} reasons={getattr(plan, 'blocked_by', [])}"
            )
            return plan  # caller can render a non-executable preview card

        # Accept if RR meets per-strategy floor or it’s OCO (tolerate lower RR there).
        accepted = (
            (getattr(plan, "rr", None) is None)
            or (float(plan.rr) >= rr_floor)
            or pt.startswith("OCO")
        )

        logger.debug(
            "plan details: strat=%s dir=%s type=%s rr=%s rr_floor=%s accepted=%s",
            getattr(plan, "strategy", None),
            getattr(plan, "direction", None),
            pt,
            getattr(plan, "rr", None),
            rr_floor,
            accepted,
        )
        print(
            f"[PRINT] plan {getattr(plan, 'strategy', None)} dir={getattr(plan, 'direction', None)} "
            f"type={pt} rr={getattr(plan, 'rr', None)} rr_floor={rr_floor} accepted={accepted}"
        )

        if not accepted:
            continue

        if mode == "market":
            return _convert_to_market(plan, tech)  # finalize as MARKET plan

        # pending mode → return as-is
        return plan

    logger.debug("no strategy plan selected for %s (regime=%s)", symbol, regime)
    print(f"[PRINT] no strategy plan selected for {symbol}")
    return None


# ---------------- Dry-run helpers (manual test harness) -----------------------


def _sample_blob_xau(session: str, regime: str) -> Dict[str, Any]:
    """Lightweight XAUUSD tech blob for sanity checks."""
    return {
        "session": session,
        "regime": regime,
        "close": 2350.0,
        "atr_14": 6.0,
        "_tf_M15": {
            "atr_14": 6.0,
            "ema_20": 2348.0,
            "ema_50": 2345.0,
            "bb_width": 0.010,
        },
        "_tf_H1": {"ema_200": 2325.0},
        "adx": 27.0,
        "sr": {"nearest_support": 2346.0, "nearest_resistance": 2360.0},
        "open_range": {"high": 2356.0, "low": 2348.0, "minutes": 50},
        "_live_spread": 0.3,
        "_point": 0.1,
        "minutes_to_next_news": 120,
        "win_streak": 2,
    }


def _sample_blob_btc(session: str, regime: str) -> Dict[str, Any]:
    """Lightweight BTCUSD tech blob for sanity checks."""
    return {
        "session": session,
        "regime": regime,
        "close": 67000.0,
        "atr_14": 900.0,
        "_tf_M15": {
            "atr_14": 900.0,
            "ema_20": 66850.0,
            "ema_50": 66500.0,
            "bb_width": 0.015,
        },
        "_tf_H1": {"ema_200": 64000.0},
        "adx": 30.0,
        "sr": {"nearest_support": 66600.0, "nearest_resistance": 67500.0},
        "open_range": {"high": 67300.0, "low": 66650.0, "minutes": 65},
        "_live_spread": 15.0,
        "_point": 0.5,
        "minutes_to_next_news": 999,
        "win_streak": 3,
    }


def dry_run_demo() -> None:
    """Print quick sanity-checks for XAUUSD (London TREND) and BTCUSD (Crypto VOLATILE)."""
    cases = [
        ("XAUUSD", _sample_blob_xau("LONDON", "TREND")),
        ("BTCUSD", _sample_blob_btc("CRYPTO", "VOLATILE")),
        ("XAUUSD", _sample_blob_xau("ASIA", "RANGE")),
        ("BTCUSD", _sample_blob_btc("NEWYORK", "TREND")),
    ]
    for sym, blob in cases:
        plan = choose_and_build(sym, blob, mode="pending")
        if plan is None:
            print(f"[DRYRUN] {sym} {blob['session']}/{blob['regime']}: no-plan")
            continue
        print(
            "[DRYRUN] {sym} {sess}/{reg}: {strat} {dir} {ptype} "
            "entry={e:.2f} sl={sl:.2f} tp={tp:.2f} rr={rr} risk={risk}".format(
                sym=sym,
                sess=str(blob.get("session")),
                reg=str(blob.get("regime")),
                strat=plan.strategy,
                dir=plan.direction,
                ptype=plan.pending_type,
                e=float(plan.entry),
                sl=float(plan.sl) if plan.sl is not None else float("nan"),
                tp=float(plan.tp) if plan.tp is not None else float("nan"),
                rr=(f"{float(plan.rr):.2f}" if plan.rr is not None else "n/a"),
                risk=getattr(plan, "risk_pct", None),
            )
        )


if __name__ == "__main__":
    # Optional quick check when running this module directly
    dry_run_demo()

# ---------------- Risk sizing helpers (map-aware) -----------------------------


def _risk_bounds() -> Tuple[float, float]:
    """Read hard bounds from settings (fallbacks provided)."""
    try:
        rmin = float(getattr(settings, "MIN_RISK_PCT", 0.10))
        rmax = float(getattr(settings, "MAX_RISK_PCT", 0.60))
    except Exception:
        rmin, rmax = 0.10, 0.60
    return rmin, rmax


def _spread_over_atr_pct(tech: Dict[str, Any]) -> float:
    """
    Compute spread / ATR_eff where ATR_eff uses ATR floor ticks.
    Returns 0 if unknown.
    """
    try:
        spread = float(
            tech.get("_live_spread")
            or tech.get("spread_pts")
            or tech.get("spread")
            or 0.0
        )
        point = float(tech.get("_point") or 0.0)

        atr_m15 = float(tech.get("_tf_M15", {}).get("atr_14") or 0.0)
        atr_m5 = float(tech.get("atr_14") or 0.0)
        atr = atr_m15 or atr_m5

        min_ticks = float(getattr(settings, "ATR_FLOOR_TICKS", 3.0))
        atr_eff = max(atr, (min_ticks * point) if point else atr)
        if atr_eff <= 0:
            return 0.0
        return spread / atr_eff
    except Exception:
        return 0.0


def _risk_overrides_from_map() -> dict:
    """Get map-level risk overrides (safe default {})."""
    try:
        mp = _load_strategy_map() or {}
        ro = mp.get("risk_overrides") or {}
        return ro if isinstance(ro, dict) else {}
    except Exception:
        return {}


def _compute_risk_pct_for_strategy(
    symbol: str, strategy: str, tech: Dict[str, Any], regime: Optional[str] = None
) -> float:
    """
    Base risk from strategy_map['strategies'][strategy]['risk_base_pct'] (after symbol/session/regime merges),
    then apply root-level risk_overrides additively, clamp to [MIN_RISK_PCT, MAX_RISK_PCT].
    """
    cfg = _strat_cfg(strategy, symbol=symbol, tech=tech, regime=regime)
    base = float(cfg.get("risk_base_pct", 0.35))

    ro = _risk_overrides_from_map()

    # minutes_to_high_impact_news_lt: [threshold_min, delta]
    try:
        thr, delta = ro.get("minutes_to_high_impact_news_lt", [None, 0.0])
        if thr is not None:
            mins = int(tech.get("minutes_to_next_news") or 999)
            if mins < float(thr):
                base += float(delta)
    except Exception:
        pass

    # spread_atr_pct_gt: [threshold_pct (0-1), delta]
    try:
        thr, delta = ro.get("spread_atr_pct_gt", [None, 0.0])
        if thr is not None:
            ratio = _spread_over_atr_pct(tech)
            if ratio > float(thr):
                base += float(delta)
    except Exception:
        pass

    # adx_boost: [adx_min, delta]
    try:
        thr, delta = ro.get("adx_boost", [None, 0.0])
        if thr is not None:
            if _adx(tech) >= float(thr):
                base += float(delta)
    except Exception:
        pass

    # win_streak_boost: [streak_min, delta]
    try:
        thr, delta = ro.get("win_streak_boost", [None, 0.0])
        if thr is not None:
            streak = float(tech.get("win_streak") or 0.0)
            if streak >= float(thr):
                base += float(delta)
    except Exception:
        pass

    rmin, rmax = _risk_bounds()
    return max(rmin, min(rmax, base))


# ---------------- Patched Main builder (adds risk_pct on accepted plan) -------


def choose_and_build(
    symbol: str,
    tech: Dict[str, Any],
    mode: Literal["market", "pending"] = "pending",
) -> Optional["StrategyPlan"]:
    """
    Build a strategy plan. In `pending` mode, return a STOP/LIMIT (or OCO) plan.
    In `market` mode, convert the best acceptable plan into a MARKET plan.
    Also attaches plan.risk_pct using strategy base + map.risk_overrides.
    """
    # --- debug visibility: what data do we have?
    try:
        logger.debug("TECH KEYS: %s", sorted(list(tech.keys())))
        m15_blob = tech.get("M15") or tech.get("_tf_M15") or tech.get("m15") or {}
        h1_blob = tech.get("H1") or tech.get("_tf_H1") or tech.get("h1") or {}
        logger.debug("M15 KEYS: %s", list(m15_blob.keys())[:30])
        logger.debug("H1 KEYS: %s", list(h1_blob.keys())[:30])
    except Exception:
        pass

    regime = str(tech.get("regime") or tech.get("regime_label") or "UNKNOWN").upper()
    logger.debug("choose_and_build: symbol=%s regime=%s mode=%s", symbol, regime, mode)
    print(f"[PRINT] choose_and_build called for {symbol} regime={regime} mode={mode}")

    # Global RR floor (map + session overrides)
    global_rr_floor = _global_rr_floor_from_map(tech)
    mode = (mode or "pending").lower()

    for fn in _REGISTRY:
        plan = None
        try:
            plan = fn(symbol, tech, regime)
            logger.debug("strategy %s -> %s", fn.__name__, "PLAN" if plan else "None")
        except Exception as e:
            logger.exception("strategy %s raised: %s", fn.__name__, e)
            continue

        if not plan:
            continue

        # Normalize direction and then classify pending type (for pending mode)
        plan = _coerce_direction_if_misfit(plan)

        # Skip OCO in market mode (not meaningful for market execution)
        if mode == "market" and (
            (getattr(plan, "pending_type", "") or "").upper().startswith("OCO")
        ):
            logger.debug(
                "skip OCO plan in market mode: %s", getattr(plan, "strategy", "")
            )
            continue

        if mode == "pending":
            plan = _finalise_pending_type(plan, tech)

        # Per-strategy RR floor (symbol + session merges already in _strat_cfg)
        strat_name = getattr(plan, "strategy", "")
        rr_floor = _rr_floor_for(strat_name, symbol, tech, global_rr_floor)

        pt = (getattr(plan, "pending_type", "") or "").upper()

        # Allow previews (blocked_by reasons) to flow up for UI, but don't accept as executable
        if getattr(plan, "preview_only", False):
            logger.debug("plan %s is preview_only; returning as preview.", strat_name)
            print(
                f"[PRINT] preview_only plan {strat_name} reasons={getattr(plan, 'blocked_by', [])}"
            )
            # attach risk for visibility even in preview
            try:
                setattr(
                    plan,
                    "risk_pct",
                    _compute_risk_pct_for_strategy(symbol, strat_name, tech, regime),
                )
            except Exception:
                pass
            return plan  # caller can render a non-executable preview card

        # Accept if RR meets per-strategy floor or it’s OCO (tolerate lower RR there).
        accepted = (
            (getattr(plan, "rr", None) is None)
            or (float(plan.rr) >= rr_floor)
            or pt.startswith("OCO")
        )

        logger.debug(
            "plan details: strat=%s dir=%s type=%s rr=%s rr_floor=%s accepted=%s",
            getattr(plan, "strategy", None),
            getattr(plan, "direction", None),
            pt,
            getattr(plan, "rr", None),
            rr_floor,
            accepted,
        )
        print(
            f"[PRINT] plan {getattr(plan, 'strategy', None)} dir={getattr(plan, 'direction', None)} "
            f"type={pt} rr={getattr(plan, 'rr', None)} rr_floor={rr_floor} accepted={accepted}"
        )

        if not accepted:
            continue

        # ---- attach risk sizing from map (base + overrides) ----
        try:
            risk_pct = _compute_risk_pct_for_strategy(symbol, strat_name, tech, regime)
            setattr(plan, "risk_pct", float(risk_pct))
        except Exception as e:
            logger.debug("risk sizing failed: %s", e)

        if mode == "market":
            return _convert_to_market(plan, tech)  # finalize as MARKET plan

        # pending mode → return as-is
        return plan

    logger.debug("no strategy plan selected for %s (regime=%s)", symbol, regime)
    print(f"[PRINT] no strategy plan selected for {symbol}")
    return None


# ---------------- Regime-level RR floor with session overrides ----------------


def _global_rr_floor_from_map(tech: Dict[str, Any]) -> float:
    """
    Resolve a global RR floor from strategy_map['regime']['rr_floor'] with optional
    session overrides. Falls back to settings.MIN_RR_FOR_PENDINGS when absent.
    """
    try:
        mp = _load_strategy_map() or {}
        rg = mp.get("regime") or {}
        base = float(rg.get("rr_floor", getattr(settings, "MIN_RR_FOR_PENDINGS", 1.3)))
        ses = _session_from_tech(tech)
        so = rg.get("session_overrides") or {}
        if isinstance(so, dict):
            s_cfg = so.get(ses) or {}
            if isinstance(s_cfg, dict) and "rr_floor" in s_cfg:
                base = float(s_cfg["rr_floor"])
        return base
    except Exception:
        try:
            return float(getattr(settings, "MIN_RR_FOR_PENDINGS", 1.3))
        except Exception:
            return 1.3


# --- EOF ---