# infra/strategy_map.py
from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from typing import Any, Dict, Optional, Tuple
from pathlib import Path

# ---------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------

# Simple doc cache used by engine via get_strategy_map()
_DOC_CACHE: Optional[dict] = None

# File mtime cache for load_strategy_map(path)
_LOCK = threading.RLock()
_FILE_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}  # path -> (mtime, data)


# ---------------------------------------------------------------------
# Public loader used by engine.strategy_logic (SSOT if present)
# ---------------------------------------------------------------------
def get_strategy_map() -> dict:
    """
    Primary entry point the engine attempts to import.
    Loads app/config/strategy_map.json once and caches the dict.
    """
    global _DOC_CACHE
    if _DOC_CACHE is not None:
        return _DOC_CACHE

    here = Path(__file__).resolve()
    cfg = here.parent.parent / "app" / "config" / "strategy_map.json"
    if not cfg.exists():
        cfg = Path.cwd() / "app" / "config" / "strategy_map.json"

    try:
        _DOC_CACHE = json.loads(cfg.read_text(encoding="utf-8")) if cfg.exists() else {}
    except Exception:
        _DOC_CACHE = {}

    return _DOC_CACHE


def reload_strategy_map() -> dict:
    """Force a reload for tools/tests without restarting the process."""
    global _DOC_CACHE
    _DOC_CACHE = None
    return get_strategy_map()


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------
def _norm_symbol(sym: str) -> str:
    """
    Normalize symbols so 'BTCUSD', 'BTCUSD.', 'BTCUSDc' etc. align.
    - Uppercase
    - Remove separators
    - Strip trailing single-letter feed suffixes like 'c' (broker feed)
    """
    s = (sym or "").upper().replace(".", "").replace("_", "")
    # If endswith 'C' only, strip (your feed suffix); keep legit pairs like USDCAD
    if len(s) >= 6 and s.endswith("C") and s[:-1].isalpha():
        return s[:-1]
    return s


def _deep_merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base or {})
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out


def _warn_unknown_fields(
    obj: Dict[str, Any], allowed: set[str], path: str, acc: list[str]
):
    for k in obj.keys():
        if k not in allowed:
            acc.append(f"Unknown field '{k}' at {path}")


# ---------------------------------------------------------------------
# Schema-lite validator (warnings only)
# ---------------------------------------------------------------------
_ALLOWED_TOP = {
    "version",
    "symbol_overrides",
    "strategies",
    "risk_overrides",
    "session_overrides",
    "regime",  # used by engine for a global rr_floor, etc.
}
_ALLOWED_OVR = {
    "regime",
    "risk",
    "orders",
    "strategies",
    "risk_mult",
    "max_spread_pct_atr",
}
_ALLOWED_REGIME = {
    "adx_trend_gate",
    "bb_squeeze",
    "vol_wide",
    "hysteresis",
    "session_nudges",
}
_ALLOWED_RISK = {
    "rr_floor",
    "max_spread_pct_atr",
    "atr_floor_ticks",
    "news_high_impact_before_min",
    "fomo_atr_mult",  # optional custom knob
}
_ALLOWED_ORDERS = {"oco_ttl_min", "pullback_retest_pct"}
_ALLOWED_STRAT_NODE = {"sl_tp", "sl_buffer_atr", "edge_buffer_atr", "tp_atr"}
_ALLOWED_STRAT = {
    "enabled",
    "priority",
    "allow_regimes",
    "block_regimes",
    "allow_sessions",
    "block_sessions",
    "filters",
    "candles_any",
    "patterns_any",
    "entry",
    "sl_tp",
    "rr_floor",
    "risk_base_pct",
    "selector_hints",
    "session_overrides",
    "symbol_overrides",
    "regime_overrides",
}


def _validate(doc: Dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if not isinstance(doc, dict):
        return ["Root JSON is not an object"]

    _warn_unknown_fields(doc, _ALLOWED_TOP, "$", warnings)

    # symbol_overrides block
    symovr = doc.get("symbol_overrides") or {}
    if not isinstance(symovr, dict):
        warnings.append("symbol_overrides should be an object")
        symovr = {}

    for sk, sv in symovr.items():
        if not isinstance(sv, dict):
            warnings.append(f"symbol_overrides['{sk}'] should be an object")
            continue
        _warn_unknown_fields(sv, _ALLOWED_OVR, f"$.symbol_overrides['{sk}']", warnings)

        if "regime" in sv and isinstance(sv["regime"], dict):
            _warn_unknown_fields(
                sv["regime"],
                _ALLOWED_REGIME,
                f"$.symbol_overrides['{sk}'].regime",
                warnings,
            )
        if "risk" in sv and isinstance(sv["risk"], dict):
            _warn_unknown_fields(
                sv["risk"], _ALLOWED_RISK, f"$.symbol_overrides['{sk}'].risk", warnings
            )
        if "orders" in sv and isinstance(sv["orders"], dict):
            _warn_unknown_fields(
                sv["orders"],
                _ALLOWED_ORDERS,
                f"$.symbol_overrides['{sk}'].orders",
                warnings,
            )
        if "strategies" in sv and isinstance(sv["strategies"], dict):
            for strat, node in sv["strategies"].items():
                if isinstance(node, dict):
                    _warn_unknown_fields(
                        node,
                        _ALLOWED_STRAT_NODE,
                        f"$.symbol_overrides['{sk}'].strategies['{strat}']",
                        warnings,
                    )

    # strategies catalog
    strats = doc.get("strategies") or {}
    if isinstance(strats, dict):
        for name, cfg in strats.items():
            if isinstance(cfg, dict):
                _warn_unknown_fields(
                    cfg, _ALLOWED_STRAT, f"$.strategies['{name}']", warnings
                )

    # risk_overrides/session_overrides: free-form but catch common typos
    if "risk_overrides" in doc and not isinstance(doc["risk_overrides"], dict):
        warnings.append("risk_overrides should be an object")
    if "session_overrides" in doc and not isinstance(doc["session_overrides"], dict):
        warnings.append("session_overrides should be an object")

    # Common typo normalization hint
    def _walk(d: Any, p: str):
        if isinstance(d, dict):
            for k, v in d.items():
                if "spread_guard_atr_pct" in k:
                    warnings.append(f"Use 'max_spread_pct_atr' instead of '{k}' at {p}")
                _walk(v, f"{p}.{k}")
        elif isinstance(d, list):
            for i, v in enumerate(d):
                _walk(v, f"{p}[{i}]")

    _walk(doc, "$")

    return warnings


# ---------------------------------------------------------------------
# Hot-reload loader (optional for tools/tests)
# ---------------------------------------------------------------------
def load_strategy_map(path: str) -> Dict[str, Any]:
    """
    Load + cache by mtime. Also validates and logs warnings into the returned dict
    under ['_warnings'] for the caller to print once.
    """
    with _LOCK:
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            # Allow empty map if not found
            return {
                "version": 0,
                "symbol_overrides": {},
                "strategies": {},
                "_warnings": ["strategy_map file not found"],
            }

        cached = _FILE_CACHE.get(path)
        if cached and cached[0] == mtime:
            return cached[1]

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        warns = _validate(data)
        data = dict(data)
        data["_warnings"] = warns
        _FILE_CACHE[path] = (mtime, data)
        return data


# ---------------------------------------------------------------------
# Resolvers / accessors
# ---------------------------------------------------------------------
def resolve_symbol_profile(doc: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    """
    Returns a merged profile for the symbol:
      - Exact match in symbol_overrides
      - Normalized alias (strip trailing 'c', dots/underscores)
      - Else {}
    If both normalized and exact exist, deep-merge (exact wins).
    """
    symovr = (doc or {}).get("symbol_overrides") or {}
    exact = symovr.get(symbol) or {}
    norm = symovr.get(_norm_symbol(symbol)) or {}
    if exact and norm and symbol != _norm_symbol(symbol):
        return _deep_merge(norm, exact)
    return exact or norm or {}


def get_regime_params(doc: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    return (resolve_symbol_profile(doc, symbol).get("regime")) or {}


def get_risk_params(doc: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    prof = resolve_symbol_profile(doc, symbol)
    risk = (prof.get("risk") or {}).copy()
    # allow shallow passthrough for legacy fields at top level of symbol node
    for k in (
        "risk_mult",
        "max_spread_pct_atr",
        "atr_floor_ticks",
        "news_high_impact_before_min",
        "rr_floor",
        "fomo_atr_mult",
    ):
        if k in prof and k not in risk:
            risk[k] = prof[k]
    return risk


def get_orders_params(doc: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    return (resolve_symbol_profile(doc, symbol).get("orders")) or {}


def get_strategy_overrides(
    doc: Dict[str, Any], symbol: str, strategy: str
) -> Dict[str, Any]:
    return (
        (resolve_symbol_profile(doc, symbol).get("strategies") or {}).get(strategy)
    ) or {}


def get_strategy_catalog(doc: Dict[str, Any]) -> Dict[str, Any]:
    return (doc or {}).get("strategies") or {}


# ---------------------------------------------------------------------
# Effective per-strategy cfg merge (matches engine merge order)
# ---------------------------------------------------------------------
def effective_strategy_cfg(
    doc: Dict[str, Any],
    name: str,
    symbol: Optional[str] = None,
    session: Optional[str] = None,
    regime: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Merge order (later wins):
      strategies[name]
        -> strategies[name].symbol_overrides[symbol or normalized]
        -> strategies[name].session_overrides[SESSION]
        -> strategies[name].regime_overrides[REGIME]
    """
    root = (doc or {}).get("strategies") or {}
    base = deepcopy(root.get(name) or {})
    if symbol and isinstance(base.get("symbol_overrides"), dict):
        sym_node = base["symbol_overrides"].get(symbol) or base["symbol_overrides"].get(
            _norm_symbol(symbol)
        )
        if isinstance(sym_node, dict):
            base = _deep_merge(base, sym_node)
    if session and isinstance(base.get("session_overrides"), dict):
        so = base["session_overrides"].get((session or "").upper())
        if isinstance(so, dict):
            base = _deep_merge(base, so)
    if regime and isinstance(base.get("regime_overrides"), dict):
        # tolerate either UPPER or original case in JSON
        ro = base["regime_overrides"].get((regime or "").upper()) or base[
            "regime_overrides"
        ].get(regime or "")
        if isinstance(ro, dict):
            base = _deep_merge(base, ro)
    return base


def get_rr_floor(
    doc: Dict[str, Any],
    strategy: str,
    symbol: Optional[str] = None,
    session: Optional[str] = None,
    regime: Optional[str] = None,
    default_floor: float = 1.3,
) -> float:
    cfg = effective_strategy_cfg(doc, strategy, symbol, session, regime)
    try:
        return float(cfg.get("rr_floor", default_floor))
    except Exception:
        return float(default_floor)


def get_risk_base_pct(
    doc: Dict[str, Any],
    strategy: str,
    symbol: Optional[str] = None,
    session: Optional[str] = None,
    regime: Optional[str] = None,
    default_pct: float = 0.30,
) -> float:
    cfg = effective_strategy_cfg(doc, strategy, symbol, session, regime)
    try:
        return float(cfg.get("risk_base_pct", default_pct))
    except Exception:
        return float(default_pct)


# ---------------------------------------------------------------------
# Risk overrides application (news/spread/ADX/win-streak, etc.)
# ---------------------------------------------------------------------
def _get_nested(d: Dict[str, Any], dotted: str, default: float = 0.0) -> float:
    """
    Safe float-ish getter supporting dotted paths, e.g. '_tf_M15.atr_14'.
    Returns default on any failure.
    """
    try:
        cur: Any = d
        for part in dotted.split("."):
            if not isinstance(cur, dict):
                return float(default)
            cur = cur.get(part)
        return float(cur)
    except Exception:
        try:
            return float(str(cur).replace(",", ""))  # last-chance coercion
        except Exception:
            return float(default)


def compute_adjusted_risk_pct(
    doc: Dict[str, Any],
    strategy: str,
    tech: Dict[str, Any],
    *,
    symbol: Optional[str] = None,
    session: Optional[str] = None,
    regime: Optional[str] = None,
    min_cap: float = 0.10,
    max_cap: float = 1.50,
) -> Tuple[float, list[str]]:
    """
    Returns (adjusted_risk_pct, reasons[]) using:
      - per-strategy risk_base_pct (with symbol/session/regime merges)
      - global risk_overrides (additive deltas like -0.15, +0.10)

    Expected tech fields (best-effort; missing values are tolerated):
      minutes_to_next_news, _live_spread | spread_pts | spread,
      atr_14 | _tf_M15.atr_14,
      adx | _tf_M15.adx,
      win_streak (rolling wins)
    """
    base = get_risk_base_pct(doc, strategy, symbol, session, regime)
    try:
        cfg = effective_strategy_cfg(doc, strategy, symbol, session, regime)
        rpm = float(cfg.get("risk_pct_mult", 1.0))
        if rpm != 1.0:
            base *= rpm
            reasons.append(f"session_risk_mult×{rpm:.2f}")
    except Exception:
        pass
    reasons: list[str] = [f"base:{base:.4f}"]

    ro = (doc or {}).get("risk_overrides") or {}

    # minutes_to_high_impact_news_lt  -> [threshold_minutes, delta]
    if "minutes_to_high_impact_news_lt" in ro:
        try:
            thr, delta = ro["minutes_to_high_impact_news_lt"]
            mins = _get_nested(tech, "minutes_to_next_news", 9999.0)
            if mins < float(thr):
                base += float(delta)
                reasons.append(f"news<{thr}m:{delta:+.2f}")
        except Exception:
            pass

    # spread_atr_pct_gt -> [threshold_ratio, delta]
    if "spread_atr_pct_gt" in ro:
        try:
            thr, delta = ro["spread_atr_pct_gt"]
            # prefer direct live spread if present
            spread = (
                _get_nested(tech, "_live_spread", 0.0)
                or _get_nested(tech, "spread_pts", 0.0)
                or _get_nested(tech, "spread", 0.0)
            )
            atr = _get_nested(tech, "atr_14", 0.0) or _get_nested(
                tech, "_tf_M15.atr_14", 0.0
            )
            pct = (spread / atr) if atr > 0 else 0.0
            if pct > float(thr):
                base += float(delta)
                reasons.append(f"spread>{thr:.2f}atr:{delta:+.2f}")
        except Exception:
            pass

    # adx_boost -> [threshold_adx, delta]
    if "adx_boost" in ro:
        try:
            thr, delta = ro["adx_boost"]
            adx = (
                _get_nested(tech, "adx", 0.0)
                or _get_nested(tech, "ADX", 0.0)
                or _get_nested(tech, "adx_14", 0.0)
                or _get_nested(tech, "_tf_M15.adx", 0.0)
            )
            if adx >= float(thr):
                base += float(delta)
                reasons.append(f"adx>={thr}:{delta:+.2f}")
        except Exception:
            pass

    # win_streak_boost -> [threshold_wins, delta]
    if "win_streak_boost" in ro:
        try:
            thr, delta = ro["win_streak_boost"]
            ws = _get_nested(tech, "win_streak", 0.0)
            if ws >= float(thr):
                base += float(delta)
                reasons.append(f"win_streak>={thr}:{delta:+.2f}")
        except Exception:
            pass

    # clamp to safety caps
    adj = max(min_cap, min(max_cap, base))
    if adj != base:
        reasons.append(f"clamped->{adj:.4f}")
    return float(adj), reasons


def session_overrides_for(
    mp: Dict[str, Any], strategy_key: str, session: str | None
) -> Dict[str, Any]:
    """
    Return a normalized overrides dict for (strategy_key, session).
    Defaults chosen to be no-ops (enabled=True, multipliers=1.0).
    """
    s = (mp or {}).get(strategy_key, {}) or {}
    so = s.get("session_overrides") or {}
    sess_key = (session or "").upper()
    o = so.get(sess_key) or {}
    return {
        "enabled": bool(o.get("enabled", True)),
        "rr_floor_mult": float(o.get("rr_floor_mult", 1.0)),
        "rr_floor_add": float(o.get("rr_floor_add", 0.0)),
        "risk_pct_mult": float(o.get("risk_pct_mult", 1.0)),
        "prefer_breakout": bool(o.get("prefer_breakout", False)),
    }


def compute_session_rr_floor(
    mp: Dict[str, Any],
    strategy_key: str,
    session: str | None,
    base_rr_floor: float,
) -> float:
    o = session_overrides_for(mp, strategy_key, session)
    return float(base_rr_floor) * float(o["rr_floor_mult"]) + float(o["rr_floor_add"])
