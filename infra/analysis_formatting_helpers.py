"""
Analysis Formatting Helpers
Helper functions to format liquidity, volatility, and macro bias data for ChatGPT
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def format_liquidity_summary(m5_features: Dict, m5_data: Dict, current_price: float) -> str:
    """
    Format liquidity data (equal highs/lows, sweeps, HVN/LVN) with explanatory context
    
    Returns natural language summary like:
    - "Equal highs at 4090 detected (3 touches) → Stop hunt likely before continuation"
    - "Liquidity sweep above yesterday's high suggests institutions collected buy stops"
    - "HVN at 4078.5 → Price magnet, use for TP target"
    """
    lines = []
    
    try:
        # Get liquidity clusters (equal highs/lows)
        liquidity = m5_features.get("liquidity", {})
        
        # Equal highs/lows
        eq_high_cluster = liquidity.get("eq_high_cluster", False)
        eq_high_price = liquidity.get("eq_high_price", 0)
        eq_high_count = liquidity.get("eq_high_count", 0)
        
        eq_low_cluster = liquidity.get("eq_low_cluster", False)
        eq_low_price = liquidity.get("eq_low_price", 0)
        eq_low_count = liquidity.get("eq_low_count", 0)
        
        if eq_high_cluster and eq_high_price > 0:
            dist_atr = abs(eq_high_price - current_price) / (m5_data.get("atr_14", 1) or 1)
            if dist_atr < 2.0:  # Within 2 ATR
                lines.append(f"⚠️ Equal highs at ${eq_high_price:,.2f} detected ({eq_high_count} touches) → Stop hunt likely before continuation")
        
        if eq_low_cluster and eq_low_price > 0:
            dist_atr = abs(eq_low_price - current_price) / (m5_data.get("atr_14", 1) or 1)
            if dist_atr < 2.0:  # Within 2 ATR
                lines.append(f"⚠️ Equal lows at ${eq_low_price:,.2f} detected ({eq_low_count} touches) → Liquidity pool - expect sweep before move")
        
        # Stop cluster detection (wick-based)
        stop_cluster_above = liquidity.get("stop_cluster_above", False)
        stop_cluster_above_price = liquidity.get("stop_cluster_above_price", 0)
        stop_cluster_above_count = liquidity.get("stop_cluster_above_count", 0)
        stop_cluster_above_dist_atr = liquidity.get("stop_cluster_above_dist_atr", 999)
        
        stop_cluster_below = liquidity.get("stop_cluster_below", False)
        stop_cluster_below_price = liquidity.get("stop_cluster_below_price", 0)
        stop_cluster_below_count = liquidity.get("stop_cluster_below_count", 0)
        stop_cluster_below_dist_atr = liquidity.get("stop_cluster_below_dist_atr", 999)
        
        if stop_cluster_above and stop_cluster_above_price > 0 and stop_cluster_above_dist_atr < 3.0:
            lines.append(f"🛑 Stop cluster above ${stop_cluster_above_price:,.2f} ({stop_cluster_above_count} wicks > 0.5 ATR) → Expect liquidity sweep before move")
        
        if stop_cluster_below and stop_cluster_below_price > 0 and stop_cluster_below_dist_atr < 3.0:
            lines.append(f"🛑 Stop cluster below ${stop_cluster_below_price:,.2f} ({stop_cluster_below_count} wicks > 0.5 ATR) → Expect liquidity sweep before move")
        
        # Sweep detection (Phase 3.2: Enhanced with validation)
        sweeps = liquidity.get("sweep", {})
        sweep_bull = sweeps.get("sweep_bull", False)
        sweep_bear = sweeps.get("sweep_bear", False)
        sweep_bull_validated = sweeps.get("sweep_bull_validated", False)
        sweep_bear_validated = sweeps.get("sweep_bear_validated", False)
        bull_confidence = sweeps.get("bull_confidence", 0)
        bear_confidence = sweeps.get("bear_confidence", 0)
        bull_fake = sweeps.get("bull_fake", False)
        bear_fake = sweeps.get("bear_fake", False)
        
        if sweep_bull:
            sweep_price = sweeps.get("sweep_price", 0)
            if sweep_price > 0:
                if bull_fake:
                    lines.append(f"⚠️ FAKE sweep above ${sweep_price:,.2f} detected (price continued higher) → Ignore, liquidity not collected")
                elif sweep_bull_validated:
                    confidence_str = f"({bull_confidence:.0f}% confidence)"
                    lines.append(f"✅ VALIDATED liquidity sweep above ${sweep_price:,.2f} {confidence_str} → Institutions collected buy stops. Structure may shift bearish (expect BOS)")
                else:
                    confidence_str = f"({bull_confidence:.0f}% confidence, pending validation)"
                    lines.append(f"📍 Liquidity sweep above ${sweep_price:,.2f} detected {confidence_str} → Institutions may have collected buy stops. Monitor for follow-through")
        
        if sweep_bear:
            sweep_price = sweeps.get("sweep_price", 0)
            if sweep_price > 0:
                if bear_fake:
                    lines.append(f"⚠️ FAKE sweep below ${sweep_price:,.2f} detected (price continued lower) → Ignore, liquidity not collected")
                elif sweep_bear_validated:
                    confidence_str = f"({bear_confidence:.0f}% confidence)"
                    lines.append(f"✅ VALIDATED liquidity sweep below ${sweep_price:,.2f} {confidence_str} → Institutions collected sell stops. Structure may shift bullish (expect BOS)")
                else:
                    confidence_str = f"({bear_confidence:.0f}% confidence, pending validation)"
                    lines.append(f"📍 Liquidity sweep below ${sweep_price:,.2f} detected {confidence_str} → Institutions may have collected sell stops. Monitor for follow-through")
        
        # HVN/LVN (Volume Profile)
        vp = m5_features.get("vp", {})
        hvn_dist_atr = vp.get("hvn_dist_atr", 999)
        lvn_dist_atr = vp.get("lvn_dist_atr", 999)
        atr = m5_data.get("atr_14", 1) or 1
        
        # Calculate actual HVN price if nearby
        if hvn_dist_atr < 1.0 and hvn_dist_atr > 0:
            # Approximate HVN price (using distance from current)
            # Note: This is approximate - actual implementation should return price levels
            hvn_price = current_price + (hvn_dist_atr * atr) if hvn_dist_atr > 0.5 else current_price - (abs(hvn_dist_atr) * atr)
            lines.append(f"🎯 HVN at ~${hvn_price:,.2f} (within {hvn_dist_atr:.1f} ATR) → Price magnet, use for TP target")
        
        if lvn_dist_atr < 1.0 and lvn_dist_atr > 0:
            lvn_price = current_price + (lvn_dist_atr * atr) if lvn_dist_atr > 0.5 else current_price - (abs(lvn_dist_atr) * atr)
            lines.append(f"⚪ LVN at ~${lvn_price:,.2f} (within {lvn_dist_atr:.1f} ATR) → Price vacuum, expect quick move through")
        
        # Phase 3.1 - Rolling Volume Footprint
        footprint = liquidity.get("footprint", {})
        if footprint.get("footprint_active", False):
            poc = footprint.get("poc", 0)
            value_area_high = footprint.get("value_area_high", 0)
            value_area_low = footprint.get("value_area_low", 0)
            current_rank = footprint.get("current_price_volume_rank", 50)
            current_pct = footprint.get("current_price_volume_pct", 0)
            
            if poc > 0:
                poc_dist_atr = abs(poc - current_price) / (m5_data.get("atr_14", 1) or 1)
                if poc_dist_atr < 2.0:
                    lines.append(f"📊 POC (Point of Control) at ${poc:,.2f} → Highest volume node, strong S/R")
            
            if value_area_high > 0 and value_area_low > 0:
                va_range = value_area_high - value_area_low
                if va_range > 0:
                    lines.append(f"📈 Value Area: ${value_area_low:,.2f} - ${value_area_high:,.2f} (70% volume range) → Expected trading zone")
            
            if current_rank <= 25:
                lines.append(f"⚠️ Current price at LOW volume zone (rank {current_rank}/100, {current_pct:.1f}% vol) → Vacuum zone, expect quick moves")
            elif current_rank >= 75:
                lines.append(f"✅ Current price at HIGH volume zone (rank {current_rank}/100, {current_pct:.1f}% vol) → Strong support/resistance")
        
    except Exception as e:
        logger.debug(f"Error formatting liquidity summary: {e}")
    
    if lines:
        return "\n".join(lines)
    return "No significant liquidity zones detected"


def format_volatility_summary(m5_features: Dict, volatility_forecaster=None, m5_df=None) -> str:
    """
    Format volatility data (momentum, expansion probability, signal) with explanatory context
    
    Returns natural language summary like:
    - "Volatility contraction in Asia session — rejection alerts suppressed until London opens"
    - "BB width at 12th percentile (contraction) → Expect breakout within 2-4 hours"
    - "ATR momentum +0.15 (rising volatility) → Use wider stops"
    """
    lines = []
    
    try:
        # Phase 3.3: Session Volatility Curves (check in m5_features first, then from forecaster)
        vol_data = m5_features.get("volatility", {})
        session_curves = vol_data.get("session_volatility_curves", {})
        
        # If not in features, try to calculate from forecaster
        if not session_curves and volatility_forecaster and m5_df is not None:
            try:
                session_curves = volatility_forecaster.calculate_session_volatility_curves(m5_df, lookback_days=7)
            except Exception:
                pass
        
        # Format session volatility curves
        if session_curves and session_curves.get("current_session") != "UNKNOWN":
            current_session = session_curves.get("current_session", "UNKNOWN")
            current_vs_hist = session_curves.get("current_vs_historical", {})
            
            if current_vs_hist:
                vs_avg = current_vs_hist.get("vs_avg", 1.0)
                percentile = current_vs_hist.get("percentile", 50)
                interpretation = current_vs_hist.get("interpretation", "")
                
                lines.append(f"🕐 {current_session} Session: {vs_avg:.1f}x avg volatility ({percentile}th percentile)")
                if interpretation:
                    lines.append(f"   → {interpretation}")
                
                # Show session comparison
                curves = session_curves.get("session_curves", {})
                if curves:
                    sessions_with_vol = []
                    for session in ["ASIA", "LONDON", "NY"]:
                        curve = curves.get(session, {})
                        avg_atr = curve.get("avg_atr", 0)
                        if avg_atr > 0:
                            sessions_with_vol.append((session, avg_atr))
                    
                    if len(sessions_with_vol) >= 2:
                        sessions_with_vol.sort(key=lambda x: x[1], reverse=True)
                        highest_session = sessions_with_vol[0][0]
                        if highest_session != current_session:
                            lines.append(f"   → Peak volatility session: {highest_session} ({sessions_with_vol[0][1]:.2f} avg ATR)")
        
        # Volatility signal (EXPANDING/CONTRACTING/STABLE)
        vol_trend = m5_features.get("vol_trend", {})
        vol_regime = vol_trend.get("regime", "unknown")
        
        # Try to get volatility signal from forecaster if available
        vol_signal = None
        if volatility_forecaster and m5_df is not None:
            try:
                vol_signal = volatility_forecaster.get_volatility_signal(m5_df)
            except Exception:
                pass
        
        # Fallback to regime-based signal
        if not vol_signal:
            if vol_regime in ["high", "spike"]:
                vol_signal = "EXPANDING"
            elif vol_regime == "low":
                vol_signal = "CONTRACTING"
            else:
                vol_signal = "STABLE"
        
        if vol_signal == "EXPANDING":
            lines.append("📈 Volatility EXPANDING → Use wider stops, breakout trades preferred")
        elif vol_signal == "CONTRACTING":
            lines.append("📉 Volatility CONTRACTING → Use tighter stops, mean reversion trades preferred")
        else:
            lines.append("➡️ Volatility STABLE → Standard risk management")
        
        # ATR momentum (if available from forecaster)
        if volatility_forecaster and m5_df is not None:
            try:
                momentum = volatility_forecaster.calculate_atr_momentum(m5_df)
                momentum_dir = momentum.get('direction', 'STABLE')
                momentum_val = momentum.get('momentum', 0)
                
                if momentum_dir == "EXPANDING" and momentum_val > 0.1:
                    lines.append(f"⚡ ATR momentum {momentum_val:+.3f} (rising volatility) → Use wider stops")
                elif momentum_dir == "CONTRACTING" and momentum_val < -0.1:
                    lines.append(f"🔻 ATR momentum {momentum_val:+.3f} (falling volatility) → Expect breakout soon")
            except Exception:
                pass
        
        # BB width percentile (if available)
        if volatility_forecaster and m5_df is not None:
            try:
                bb_percentile_data = volatility_forecaster.calculate_bb_width_percentile(m5_df)
                percentile = bb_percentile_data.get('percentile', 50)
                expansion_prob = bb_percentile_data.get('expansion_probability', 'normal')
                
                if percentile <= 20:
                    lines.append(f"📊 BB width at {percentile}th percentile (contraction) → Expect breakout within 2-4 hours")
                elif percentile >= 80:
                    lines.append(f"📊 BB width at {percentile}th percentile (expansion) → High volatility - breakout likely")
            except Exception:
                pass
        
    except Exception as e:
        logger.debug(f"Error formatting volatility summary: {e}")
    
    if lines:
        return "\n".join(lines)
    return "Volatility analysis unavailable"


def format_order_flow_summary(order_flow: Optional[Dict[str, Any]]) -> str:
    """
    Format order flow data (whale activity, order book imbalance, liquidity voids) with explanatory context
    
    Returns natural language summary
    """
    if not order_flow:
        return "Order flow: Neutral (Binance service not active) - Using MT5 data only"
    
    lines = []
    
    try:
        signal = order_flow.get("signal", "NEUTRAL")
        confidence = order_flow.get("confidence", 0)
        
        if signal != "NEUTRAL":
            lines.append(f"📊 Order Flow Signal: {signal} ({confidence:.0f}% confidence)")
        
        # Whale activity
        whale_activity = order_flow.get("whale_activity")
        if whale_activity:
            total_whales = whale_activity.get("total_whales", 0)
            buy_whales = whale_activity.get("buy_whales", 0)
            sell_whales = whale_activity.get("sell_whales", 0)
            net_side = whale_activity.get("net_whale_side", "NEUTRAL")
            
            if total_whales > 0:
                lines.append(f"🐋 Whale Activity: {buy_whales} buy / {sell_whales} sell → Net: {net_side}")
        
        # Order book imbalance
        order_book = order_flow.get("order_book")
        if order_book:
            imbalance_pct = order_book.get("imbalance_pct", 0)
            if abs(imbalance_pct) > 10:
                direction = "bullish" if imbalance_pct > 0 else "bearish"
                lines.append(f"📈 Order Book Imbalance: {imbalance_pct:+.1f}% ({direction})")
        
        # Liquidity voids
        liquidity_voids = order_flow.get("liquidity_voids", [])
        if liquidity_voids:
            lines.append(f"⚠️ Liquidity Voids: {len(liquidity_voids)} detected → Potential for sharp moves")
        
        # Warnings
        warnings = order_flow.get("warnings", [])
        if warnings:
            for warning in warnings[:3]:  # Limit to 3 warnings
                lines.append(f"⚠️ {warning}")
        
    except Exception as e:
        logger.debug(f"Error formatting order flow summary: {e}")
    
    if lines:
        return "\n".join(lines)
    return "Order flow: Neutral"


def format_macro_bias_summary(macro_bias: Optional[Dict[str, Any]]) -> str:
    """
    Format macro bias score with explanatory context including Fed expectations
    
    Returns natural language summary like:
    - "Rising 10Y and firm DXY maintain downside pressure on EURUSD — only take shorts unless structure strongly flips"
    - "📊 Fed Expectations: 2Y-10Y spread inverted (-0.5%) - recession signal, Fed likely to cut"
    """
    if not macro_bias:
        return "Macro bias: Neutral"
    
    try:
        bias_score = macro_bias.get("bias_score", 0.0)
        bias_direction = macro_bias.get("bias_direction", "neutral")
        bias_strength = macro_bias.get("bias_strength", "weak")
        explanation = macro_bias.get("explanation", "")
        factors = macro_bias.get("factors", {})
        
        lines = []
        
        # Extract and highlight Fed expectations if present
        fed_expectations = factors.get("fed_expectations", {})
        if fed_expectations and fed_expectations.get("reason"):
            fed_reason = fed_expectations.get("reason", "")
            # Extract spread value from reason
            if "spread" in fed_reason.lower():
                if "inverted" in fed_reason.lower():
                    lines.append(f"📊 Fed Expectations: {fed_reason}")
                elif "steep" in fed_reason.lower():
                    lines.append(f"📊 Fed Expectations: {fed_reason}")
                elif "flat" in fed_reason.lower():
                    lines.append(f"📊 Fed Expectations: {fed_reason}")
                else:
                    lines.append(f"📊 Fed Expectations: {fed_reason}")
        
        # Add bias summary
        if abs(bias_score) >= 0.5:
            strength_emoji = "🔴" if bias_direction == "bearish" else "🟢" if bias_direction == "bullish" else "⚪"
            lines.append(f"{strength_emoji} Macro Bias: {bias_direction.upper()} ({bias_strength}) - Score: {bias_score:+.2f}")
            lines.append(f"   {explanation}")
        else:
            lines.append(f"⚪ Macro Bias: {bias_direction.upper()} ({bias_strength}) - Score: {bias_score:+.2f}")
            if explanation:
                lines.append(f"   {explanation}")
        
        return "\n".join(lines)
            
    except Exception as e:
        logger.debug(f"Error formatting macro bias summary: {e}")
        return "Macro bias: Unavailable"


def format_tick_metrics_summary(tick_metrics: Dict[str, Any]) -> str:
    """
    Format tick metrics for ChatGPT display.
    
    Returns formatted string like:
    
    TICK MICROSTRUCTURE:
    M5: Delta -42.5K (SELL dominant) | CVD slope: down | Spread: 1.8 +/- 0.3
    M15: Realized Vol 0.12% (1.2x daily avg) | 3 absorption zones detected
    H1: Volatility expanding (ratio: 1.35) | Tick rate: 18.2/sec
    Hour: 52K ticks | Net delta: -180K | Dominant: SELL
    -> Microstructure: Confirms bearish structure bias
    """
    if not tick_metrics:
        return ""  # Return empty string - tick metrics not available (generator not running or no data yet)
    
    try:
        # Check metadata first (Issue 20 fix)
        metadata = tick_metrics.get("metadata", {})
        if not metadata.get("data_available", True):
            market_status = metadata.get("market_status", "closed")
            return f"TICK MICROSTRUCTURE: Market {market_status} - no tick data available"
        
        # Header with loading indicator if previous_day still computing
        if metadata.get("previous_day_loading", False):
            lines = ["TICK MICROSTRUCTURE (previous_day loading...):"]
        else:
            lines = ["TICK MICROSTRUCTURE:"]
        
        # M5 summary
        m5 = tick_metrics.get("M5", {})
        if m5:
            delta = m5.get("delta_volume", 0)
            delta_str = f"+{delta/1000:.1f}K" if delta >= 0 else f"{delta/1000:.1f}K"
            dominant = m5.get("dominant_side", "NEUTRAL")
            cvd_slope = m5.get("cvd_slope", "flat")
            spread = m5.get("spread", {})
            spread_mean = spread.get("mean", 0)
            spread_std = spread.get("std", 0)
            lines.append(f"M5: Delta {delta_str} ({dominant}) | CVD: {cvd_slope} | Spread: {spread_mean:.1f}+/-{spread_std:.1f}")
        
        # M15 summary
        m15 = tick_metrics.get("M15", {})
        if m15:
            vol = m15.get("realized_volatility", 0) * 100
            vol_ratio = m15.get("volatility_ratio", 1.0)
            absorption = m15.get("absorption", {})
            abs_count = absorption.get("count", 0)
            lines.append(f"M15: Vol {vol:.2f}% ({vol_ratio:.1f}x avg) | Absorption: {abs_count} zones")
        
        # H1 summary
        h1 = tick_metrics.get("H1", {})
        if h1:
            vol_ratio = h1.get("volatility_ratio", 1.0)
            vol_state = "expanding" if vol_ratio > 1.2 else "contracting" if vol_ratio < 0.8 else "stable"
            tick_rate = h1.get("tick_rate", 0)
            lines.append(f"H1: Volatility {vol_state} ({vol_ratio:.2f}x) | Tick rate: {tick_rate:.1f}/sec")
        
        # Previous hour summary
        prev_hour = tick_metrics.get("previous_hour", {})
        if prev_hour:
            tick_count = prev_hour.get("tick_count", 0)
            net_delta = prev_hour.get("net_delta", 0)
            delta_str = f"+{net_delta/1000:.0f}K" if net_delta >= 0 else f"{net_delta/1000:.0f}K"
            dominant = prev_hour.get("dominant_side", "NEUTRAL")
            lines.append(f"Hour: {tick_count/1000:.0f}K ticks | Net delta: {delta_str} | Dominant: {dominant}")
        
    except Exception as e:
        logger.debug(f"Error formatting tick metrics summary: {e}")
        return "Tick microstructure: Formatting error"
    
    if lines and len(lines) > 1:  # More than just the header
        return "\n".join(lines)
    return ""


