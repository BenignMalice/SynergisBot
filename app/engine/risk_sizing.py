# app/engine/risk_sizing.py
from __future__ import annotations
from typing import Dict, Any
from math import isfinite
from app.engine.strategy_logic import _load_strategy_map, _strat_cfg, _adx, _atr


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def risk_pct_for(plan, tech: Dict[str, Any], *, floor=0.05, cap=1.0) -> float:
    mp = _load_strategy_map() or {}
    # base from strategy (default 0.3% if missing)
    scfg = _strat_cfg(plan.strategy, symbol=plan.symbol, tech=tech, regime=plan.regime)
    base = float(scfg.get("risk_base_pct", 0.3))

    ro = (mp.get("risk_overrides") or {}) if isinstance(mp, dict) else {}

    # minutes_to_high_impact_news_lt: [threshold_minutes, delta]
    try:
        th, delta = ro.get("minutes_to_high_impact_news_lt", [None, 0.0])
        mins = float(tech.get("minutes_to_next_news") or 9e9)
        if th is not None and mins < float(th):
            base += float(delta)
    except Exception:
        pass

    # spread_atr_pct_gt: [threshold_ratio, delta]
    try:
        th, delta = ro.get("spread_atr_pct_gt", [None, 0.0])
        spread = float(
            tech.get("_live_spread")
            or tech.get("spread_pts")
            or tech.get("spread")
            or 0.0
        )
        atr = _atr(tech) or _atr(tech, "M15") or 1.0
        ratio = (spread / atr) if atr else 0.0
        if th is not None and ratio > float(th):
            base += float(delta)
    except Exception:
        pass

    # adx_boost: [threshold_adx, delta]
    try:
        th, delta = ro.get("adx_boost", [None, 0.0])
        adx = _adx(tech)
        if th is not None and adx >= float(th):
            base += float(delta)
    except Exception:
        pass

    # win_streak_boost: [threshold_wins, delta]
    try:
        th, delta = ro.get("win_streak_boost", [None, 0.0])
        streak = float(tech.get("win_streak") or 0.0)
        if th is not None and streak >= float(th):
            base += float(delta)
    except Exception:
        pass

    return _clip(base, floor, cap)


def position_size(
    units_per_price: float, entry: float, sl: float, equity: float, risk_pct: float
) -> float:
    # Basic: risk $ = equity * risk_pct% ; size = risk$ / |entry-sl|
    if not (isfinite(entry) and isfinite(sl) and entry != sl and isfinite(equity)):
        return 0.0
    risk_dollars = equity * (risk_pct / 100.0)
    per_unit_risk = abs(entry - sl) * units_per_price  # instrument specific
    return risk_dollars / per_unit_risk if per_unit_risk > 0 else 0.0
