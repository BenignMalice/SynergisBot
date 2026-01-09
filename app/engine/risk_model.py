# =====================================
# File: app/engine/risk_model.py
# =====================================
from __future__ import annotations

from typing import Optional


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def map_risk_pct(
    *,
    base_pct: float,
    confidence: int,
    adx: float,
    spread_pct_atr: float,
    minutes_to_news: Optional[float] = None,
    min_pct: float = 0.2,
    max_pct: float = 2.0,
    advanced_features: Optional[dict] = None,
) -> float:
    """
    Map current context to a risk% with V8 feature integration:
      - Higher with confidence and moderate/strong ADX
      - Lower when spread% of ATR is high and near news
      - Adaptive adjustments based on V8 advanced indicators
    
    Advanced Adjustments:
      - RMAG: Reduce risk if price stretched (>2σ from EMA200/VWAP)
      - EMA Slope: Increase risk for quality trends, reduce for flat markets
      - Vol Trend: Reduce risk in choppy conditions, increase for strong trends
      - Pressure: Reduce risk for fake momentum (high RSI + weak ADX)
      - MTF Alignment: Boost risk when timeframes align (≥2/3)
      - Momentum Accel: Reduce risk when momentum fading
    
    Returns a rounded risk% (two decimals).
    """
    c = _clip(float(confidence), 1.0, 99.0)
    a = max(0.0, float(adx))
    s = max(0.0, float(spread_pct_atr))
    m = 9999.0 if minutes_to_news is None else max(0.0, float(minutes_to_news))

    # Confidence factor: 0.7x at 40 → 1.3x at 85+
    f_conf = 0.7 + 0.6 * ((c - 40.0) / 45.0)
    f_conf = _clip(f_conf, 0.6, 1.35)

    # ADX factor: weak <18 down to 0.8x; 25–40 → 1.1x; >45 cool slightly to 1.05
    if a < 14:
        f_adx = 0.75
    elif a < 18:
        f_adx = 0.85
    elif a < 25:
        f_adx = 1.00
    elif a < 40:
        f_adx = 1.10
    elif a < 55:
        f_adx = 1.05
    else:
        f_adx = 1.00

    # Spread as % of ATR (penalise)
    if s > 0.40:
        f_spread = 0.55
    elif s > 0.30:
        f_spread = 0.70
    elif s > 0.20:
        f_spread = 0.85
    else:
        f_spread = 1.00

    # News proximity (penalise <60m)
    if m < 15:
        f_news = 0.5
    elif m < 30:
        f_news = 0.65
    elif m < 60:
        f_news = 0.8
    else:
        f_news = 1.0

    # === V8 FEATURE ADJUSTMENTS ===
    f_v8 = 1.0  # Default: no adjustment
    
    if advanced_features and isinstance(advanced_features, dict):
        try:
            # Get M5 features (primary timeframe)
            m5_features = advanced_features.get("M5", {})
            
            # 1. RMAG: Stretched price reduces risk
            rmag = m5_features.get("rmag", {})
            ema200_atr = abs(rmag.get("ema200_atr", 0))
            vwap_atr = abs(rmag.get("vwap_atr", 0))
            
            if ema200_atr > 2.5:
                f_v8 *= 0.70  # Very stretched: reduce risk by 30%
            elif ema200_atr > 2.0:
                f_v8 *= 0.85  # Stretched: reduce risk by 15%
            
            if vwap_atr > 2.0:
                f_v8 *= 0.85  # Far from VWAP: reduce risk by 15%
            
            # 2. EMA Slope: Quality trends increase risk, flat reduces
            ema_slope = m5_features.get("ema_slope", {})
            ema50_slope = abs(ema_slope.get("ema50", 0))
            ema200_slope = abs(ema_slope.get("ema200", 0))
            
            if ema50_slope > 0.15 and ema200_slope > 0.05:
                f_v8 *= 1.15  # Quality trend: boost risk by 15%
            elif ema50_slope < 0.05 and ema200_slope < 0.03:
                f_v8 *= 0.75  # Flat market: reduce risk by 25%
            
            # 3. Volatility Trend: Adjust based on state
            vol_trend = m5_features.get("vol_trend", {})
            vol_state = vol_trend.get("state", "unknown")
            
            if vol_state == "expansion_strong_trend":
                f_v8 *= 1.10  # Strong trending: boost risk by 10%
            elif vol_state == "squeeze_with_trend":
                f_v8 *= 0.80  # Choppy: reduce risk by 20%
            elif vol_state == "squeeze_no_trend":
                f_v8 *= 0.85  # Pre-breakout uncertainty: reduce risk by 15%
            
            # 4. Pressure Ratio: Fake momentum reduces risk
            pressure = m5_features.get("pressure", {})
            pressure_rsi = pressure.get("rsi", 50)
            pressure_adx = pressure.get("adx", 0)
            
            if (pressure_rsi > 65 and pressure_adx < 20) or (pressure_rsi < 35 and pressure_adx < 20):
                f_v8 *= 0.75  # Fake momentum: reduce risk by 25%
            elif (pressure_rsi > 60 and pressure_adx > 30) or (pressure_rsi < 40 and pressure_adx > 30):
                f_v8 *= 1.10  # Quality momentum: boost risk by 10%
            
            # 5. MTF Alignment: Strong confluence boosts risk
            mtf_score = advanced_features.get("mtf_score", {})
            mtf_total = mtf_score.get("total", 0)
            mtf_max = mtf_score.get("max", 3)
            
            if mtf_total >= 2:
                f_v8 *= 1.15  # Strong alignment: boost risk by 15%
            elif mtf_total == 0:
                f_v8 *= 0.70  # No alignment: reduce risk by 30%
            
            # 6. Momentum Acceleration: Fading momentum reduces risk
            accel = m5_features.get("accel", {})
            macd_slope = accel.get("macd_slope", 0)
            rsi_slope = accel.get("rsi_slope", 0)
            
            if macd_slope < -0.02 and rsi_slope < -2.0:
                f_v8 *= 0.80  # Fading momentum: reduce risk by 20%
            elif macd_slope > 0.03 and rsi_slope > 2.0:
                f_v8 *= 1.10  # Accelerating momentum: boost risk by 10%
            
            # 7. VWAP Deviation: Outer zone mean reversion
            vwap = m5_features.get("vwap", {})
            vwap_zone = vwap.get("zone", "inside")
            
            if vwap_zone == "outer":
                f_v8 *= 0.85  # Mean reversion risk: reduce by 15%
            
            # Clip V8 factor to reasonable bounds (0.5x to 1.5x)
            f_v8 = _clip(f_v8, 0.5, 1.5)
            
        except Exception:
            # If V8 processing fails, use default (no adjustment)
            f_v8 = 1.0

    risk = float(base_pct) * f_conf * f_adx * f_spread * f_news * f_v8
    risk = _clip(risk, float(min_pct), float(max_pct))
    # round to 2dp for readability in Telegram
    return round(risk, 2)



def ensure_orientation(entry: float, sl: float, tp: float, direction: str, point: float | None = None) -> tuple[float, float]:
    """
    Defensive guard: force SL/TP to the correct side of entry given direction.
    - For BUY/LONG: SL < entry < TP
    - For SELL/SHORT: SL > entry > TP
    If violated, nudge SL/TP by a minimal tick (5 * point) to restore geometry.
    """
    try:
        e = float(entry); s = float(sl); t = float(tp)
        d = str(direction).upper()
        tick = max(0.0000001, float(point or 0.0) * 5.0)  # minimal nudge
        if d in ("BUY", "LONG"):
            if s >= e: s = e - tick
            if t <= e: t = e + max(tick, abs(e - s))  # keep RR positive
        elif d in ("SELL", "SHORT"):
            if s <= e: s = e + tick
            if t >= e: t = e - max(tick, abs(s - e))
        return float(s), float(t)
    except Exception:
        return sl, tp


def pa_atr_stop(
    price: float, side: str, plan: dict, atr_mult_floor: float = 0.8
) -> float:
    """
    Choose SL at structure edge if available, but not tighter than ATR floor.
    """
    atr = (
        float(plan["indicators"]["atr"])
        if "indicators" in plan and "atr" in plan["indicators"]
        else plan.get("atr", 0.0)
    )
    floor = atr * atr_mult_floor if atr > 0 else 0.0

    nz = plan.get("pa", {}).get("nearest", {})
    if side == "long" and nz.get("below"):
        level, span = float(nz["below"]["level"]), float(nz["below"]["span"])
        struct_sl = level - span  # just outside the zone
        return min(price - floor, struct_sl) if floor > 0 else struct_sl
    if side == "short" and nz.get("above"):
        level, span = float(nz["above"]["level"]), float(nz["above"]["span"])
        struct_sl = level + span
        return max(price + floor, struct_sl) if floor > 0 else struct_sl

    # No structural anchor; fallback to ATR-only
    return price - floor if side == "long" else price + floor


def pa_targets(
    price: float, side: str, plan: dict, rr_floor: float = 1.2
) -> tuple[float, float]:
    """
    TP1/TP2 using opposing zone (or mid-range of current zone); ensures RR >= floor.
    """
    nz = plan.get("pa", {}).get("nearest", {})
    atr = float(plan.get("atr", plan.get("indicators", {}).get("atr", 0.0)))
    sl = (
        float(plan["levels"]["sl"])
        if "levels" in plan and "sl" in plan["levels"]
        else pa_atr_stop(price, side, plan)
    )

    risk = abs(price - sl)
    min_reward = max(risk * rr_floor, atr) if atr else risk * rr_floor

    # Opposing zones
    if side == "long" and nz.get("above"):
        tp1 = min(price + min_reward, float(nz["above"]["level"]))
        tp2 = tp1 + risk  # trail or measured-move
        return tp1, tp2
    if side == "short" and nz.get("below"):
        tp1 = max(price - min_reward, float(nz["below"]["level"]))
        tp2 = tp1 - risk
        return tp1, tp2

    # Fallback ATR-based
    tp1 = price + min_reward if side == "long" else price - min_reward
    tp2 = price + 2 * min_reward if side == "long" else price - 2 * min_reward
    return tp1, tp2
