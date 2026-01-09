# =====================================
# app/engine/volatile_strategies.py
# =====================================
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple, List
import math


# Light duplication to keep this file standalone and stable
@dataclass
class StrategyPlan:
    symbol: str
    strategy: str
    regime: str
    direction: str  # "LONG" | "SHORT"
    pending_type: (
        str  # "BUY_STOP" | "SELL_STOP" | "BUY_LIMIT" | "SELL_LIMIT" | "OCO_STOP"
    )
    entry: float
    sl: Optional[float]
    tp: Optional[float]
    rr: Optional[float]
    notes: str
    ttl_min: Optional[int] = None
    oco_companion: Optional[Dict[str, Any]] = None


# ---------- tiny helpers (safe, tolerant) ----------
def _f(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return float(d)


def _get_from(tech: Dict[str, Any], tf: Optional[str], keys: List[str]) -> float:
    containers: List[Dict[str, Any]] = []
    if tf:
        containers += [
            tech.get(tf) or {},
            tech.get(f"_tf_{tf}") or {},
            tech.get(tf.upper()) or {},
        ]
    containers += [tech]
    for k in keys:
        for c in containers:
            if not isinstance(c, dict):
                continue
            v = c.get(k)
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


def _price(tech: Dict[str, Any]) -> float:
    p = _get_from(tech, None, ["last", "close", "price"])
    if p:
        return p
    bid = _get_from(tech, None, ["bid", "Bid", "BID"])
    ask = _get_from(tech, None, ["ask", "Ask", "ASK"])
    return (bid + ask) / 2.0 if bid and ask else 0.0


def _atr(tech: Dict[str, Any], tf: str = "M15", period: int = 14) -> float:
    return _get_from(
        tech, tf, [f"atr_{period}", f"ATR_{period}", f"atr{period}", f"ATR{period}"]
    ) or _get_from(
        tech, "H1", [f"atr_{period}", f"ATR_{period}", f"atr{period}", f"ATR{period}"]
    )


def _bb_width(tech: Dict[str, Any], tf: str = "M15") -> float:
    return _get_from(tech, tf, ["bb_width", "BBWidth", "bbwidth"])


def _ema(tech: Dict[str, Any], tf: str, n: int) -> float:
    return _get_from(tech, tf, [f"ema_{n}", f"EMA_{n}", f"ema{n}", f"EMA{n}"])


def _macd_hist(tech: Dict[str, Any], tf: str = "M15") -> float:
    return _get_from(
        tech, tf, ["macd_hist", "MACD_HIST", "macdHistogram", "macd_hist_12_26_9"]
    )


def _sr_near(tech: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    sr = tech.get("sr") or {}
    sup = sr.get("nearest_support") or tech.get("nearest_support")
    res = sr.get("nearest_resistance") or tech.get("nearest_resistance")
    try:
        sup = float(sup) if sup is not None else None
    except Exception:
        sup = None
    try:
        res = float(res) if res is not None else None
    except Exception:
        res = None
    return sup, res


def _pending_type(side: str, entry: float, ref: float) -> str:
    if side == "LONG":
        return "BUY_STOP" if entry >= ref else "BUY_LIMIT"
    return "SELL_STOP" if entry <= ref else "SELL_LIMIT"


def _calc_rr(
    side: str, entry: float, sl: Optional[float], tp: Optional[float]
) -> Optional[float]:
    try:
        if sl is None or tp is None:
            return None
        risk = abs(entry - sl)
        rew = abs(tp - entry)
        return (rew / risk) if risk > 0 else None
    except Exception:
        return None


def _respect_spread_and_news(
    tech: Dict[str, Any], max_spread_pct_atr: float = 0.30, hi_news_before_min: int = 30
) -> Tuple[bool, List[str]]:
    notes: List[str] = []
    try:
        spread = _f(
            tech.get("_live_spread")
            or tech.get("spread_pts")
            or tech.get("spread")
            or 0.0
        )
        point = _f(tech.get("_point") or 0.0)
        atr = _atr(tech) or _f(tech.get("atr_14"))
        atr_eff = max(atr, 3.0 * point) if point else atr
        if atr_eff > 0 and (spread / atr_eff) > max_spread_pct_atr:
            notes.append(
                f"spread_guard:{(spread/atr_eff):.2f} > {(max_spread_pct_atr):.2f}"
            )
            return False, notes
    except Exception as e:
        notes.append(f"spread_guard_error:{e}")

    try:
        mins_to_news = int(tech.get("minutes_to_next_news") or 999)
        if mins_to_news < hi_news_before_min:
            notes.append("news_guard:soon")
            return False, notes
    except Exception:
        pass

    return True, notes


# ---------- 1) Volatility Breakout (momentum riding) ----------
def strat_vol_breakout(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    if regime not in {"VOLATILE", "TREND"}:
        return None
    bbw = _bb_width(tech)
    if bbw < 0.012:  # want widened bands in vol
        return None
    px = _price(tech)
    atr = _atr(tech)
    if not atr or not px:
        return None

    # Find small recent consolidation box if provided
    box = tech.get("consolidation") or {}
    hi = _f(box.get("high"), 0.0)
    lo = _f(box.get("low"), 0.0)
    if not hi or not lo or not (hi > lo):
        # fallback: synthetic box around price using fraction of ATR
        hi = px + 0.5 * atr
        lo = px - 0.5 * atr

    # Entry a touch outside the box; SL ~1–1.5 ATR; TP 2–3 ATR
    entry_long = hi + 0.15 * atr
    sl_long = entry_long - 1.2 * atr
    tp_long = entry_long + 2.4 * atr

    entry_short = lo - 0.15 * atr
    sl_short = entry_short + 1.2 * atr
    tp_short = entry_short - 2.4 * atr

    ok, blocks = _respect_spread_and_news(
        tech, max_spread_pct_atr=0.30, hi_news_before_min=30
    )
    if not ok:
        return None

    # Prefer STOPs for breakouts
    plan_long = StrategyPlan(
        symbol=symbol,
        strategy="vol_breakout",
        regime=regime,
        direction="LONG",
        pending_type="BUY_STOP",
        entry=entry_long,
        sl=sl_long,
        tp=tp_long,
        rr=_calc_rr("LONG", entry_long, sl_long, tp_long),
        notes=f"Volatility Breakout above box {hi:.2f}; guards ok.",
    )
    plan_short = StrategyPlan(
        symbol=symbol,
        strategy="vol_breakout",
        regime=regime,
        direction="SHORT",
        pending_type="SELL_STOP",
        entry=entry_short,
        sl=sl_short,
        tp=tp_short,
        rr=_calc_rr("SHORT", entry_short, sl_short, tp_short),
        notes=f"Volatility Breakout below box {lo:.2f}; guards ok.",
    )
    # You can choose one by bias (e.g., MACD), but return None here to allow selector to pick
    # We’ll return LONG if MACD>0 else SHORT; if MACD neutral, prefer LONG
    macd = _macd_hist(tech)
    return plan_long if macd >= 0 else plan_short


# ---------- 2) Volatility Fade / Mean Reversion ----------
def strat_vol_fade(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    if regime not in {"VOLATILE", "RANGE"}:
        return None
    atr = _atr(tech)
    if not atr:
        return None
    px = _price(tech)
    ema20 = _ema(tech, "M15", 20) or _ema(tech, "H1", 20)
    vwap = _f(tech.get("vwap"), None)

    # "Stretch" = price distance from mean in ATRs
    mean = vwap or ema20
    if not mean:
        return None
    stretch = abs(px - mean) / max(1e-9, atr)
    if stretch < 2.0:  # need >= ~2x ATR stretch for a quality fade
        return None

    sup, res = _sr_near(tech)
    side = "SHORT" if px > mean else "LONG"

    # SL beyond the wick/extreme ~1.0 ATR; TP at mean (first target)
    entry = px
    sl = entry + 1.0 * atr if side == "SHORT" else entry - 1.0 * atr
    tp = mean
    ok, blocks = _respect_spread_and_news(
        tech, max_spread_pct_atr=0.30, hi_news_before_min=30
    )
    if not ok:
        return None

    return StrategyPlan(
        symbol=symbol,
        strategy="vol_fade",
        regime=regime,
        direction=side,
        pending_type=_pending_type(side, entry, px),
        entry=entry,
        sl=sl,
        tp=tp,
        rr=_calc_rr(side, entry, sl, tp),
        notes=f"Volatility Fade: stretch {stretch:.2f} ATR to mean ({'VWAP' if vwap else 'EMA20'}).",
    )


# ---------- 3) Volatility Scalping (micro-trend on M1–M5) ----------
def strat_vol_scalp(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    if regime != "VOLATILE":
        return None
    atr = _atr(tech, "M5") or _atr(tech, "M15")
    if not atr:
        return None
    px = _price(tech)
    ema20 = _ema(tech, "M5", 20) or _ema(tech, "M15", 20)
    adx = _get_from(tech, "M5", ["adx", "ADX", "adx_14", "ADX_14"])
    if not ema20 or adx < 25:
        return None

    side = "LONG" if px >= ema20 else "SHORT"
    entry = px
    sl = entry - 0.8 * atr if side == "LONG" else entry + 0.8 * atr
    tp = entry + 1.0 * atr if side == "LONG" else entry - 1.0 * atr

    ok, blocks = _respect_spread_and_news(
        tech, max_spread_pct_atr=0.30, hi_news_before_min=30
    )
    if not ok:
        return None

    return StrategyPlan(
        symbol=symbol,
        strategy="vol_scalp",
        regime=regime,
        direction=side,
        pending_type="MARKET",
        entry=entry,
        sl=sl,
        tp=tp,
        rr=_calc_rr(side, entry, sl, tp),
        notes="Volatility Scalping (EMA20 + ADX>25, 1×ATR target).",
    )


# ---------- 4) Post-News Continuation ----------
def strat_vol_news_react(
    symbol: str, tech: Dict[str, Any], regime: str
) -> Optional[StrategyPlan]:
    # Enter after first spike settles: require a big candle then a confirming candle
    if regime not in {"VOLATILE", "TREND"}:
        return None
    atr = _atr(tech)
    if not atr:
        return None
    last = tech.get("last_candle") or {}
    rng = _f(last.get("range"), 0.0)
    body_pct = _f(last.get("body_pct"), 0.0)
    dir_hint = str(last.get("dir") or "").upper()
    if rng < 1.2 * atr or body_pct < 0.5:
        return None  # need strong bar

    macd = _macd_hist(tech)
    side = "LONG" if (dir_hint == "BULL" or macd > 0) else "SHORT"

    # Wait for 1–2 bars confirmation → emulate with small buffer outside last high/low
    hi = _f(last.get("high"), 0.0)
    lo = _f(last.get("low"), 0.0)
    if not hi or not lo:
        px = _price(tech)
        hi, lo = px + 0.6 * atr, px - 0.6 * atr

    entry = hi + 0.1 * atr if side == "LONG" else lo - 0.1 * atr
    sl = entry - 1.0 * atr if side == "LONG" else entry + 1.0 * atr
    tp = entry + 1.8 * atr if side == "LONG" else entry - 1.8 * atr

    ok, blocks = _respect_spread_and_news(
        tech, max_spread_pct_atr=0.30, hi_news_before_min=15
    )  # allow a bit sooner post-release
    if not ok:
        return None

    return StrategyPlan(
        symbol=symbol,
        strategy="vol_news_react",
        regime=regime,
        direction=side,
        pending_type="BUY_STOP" if side == "LONG" else "SELL_STOP",
        entry=entry,
        sl=sl,
        tp=tp,
        rr=_calc_rr(side, entry, sl, tp),
        notes="Post-news continuation after confirmation (ATR-scaled SL/TP).",
    )


# ---------- registry ----------
ALL_VOL_STRATEGIES = [
    strat_vol_breakout,
    strat_vol_fade,
    strat_vol_scalp,
    strat_vol_news_react,
]
