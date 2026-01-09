"""
Range Scalping Analysis Tool
Main analysis function for range scalping opportunities.
"""

import logging
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime
import pandas as pd
import numpy as np

from infra.range_boundary_detector import RangeBoundaryDetector, RangeStructure
from infra.range_scalping_risk_filters import RangeScalpingRiskFilters
from infra.range_scalping_scorer import RangeScalpingScorer
from infra.session_analyzer import SessionAnalyzer
from infra.indicator_bridge import IndicatorBridge
from config.range_scalping_config_loader import load_range_scalping_config, load_rr_config

logger = logging.getLogger(__name__)


def _detect_rejection_wick(
    recent_candles: List[Dict[str, Any]],
    range_high: float,
    range_low: float,
    atr: float
) -> bool:
    """
    Detect rejection wick pattern near range boundaries.
    
    Pattern: Long wick above/below body near range edge, price closes inside range.
    
    Args:
        recent_candles: List of candle dicts with 'high', 'low', 'open', 'close'
        range_high: Upper range boundary
        range_low: Lower range boundary
        atr: Average True Range for tolerance calculation
    
    Returns:
        True if rejection wick detected, False otherwise
    """
    if not recent_candles or len(recent_candles) < 2:
        return False
    
    if atr <= 0:
        return False
    
    # Check last 2-3 candles
    tolerance = atr * 0.15  # 0.15 ATR tolerance for "near" range edge
    
    for candle in recent_candles[-3:]:
        high = candle.get('high', 0)
        low = candle.get('low', 0)
        open_price = candle.get('open', 0)
        close = candle.get('close', 0)
        
        if high <= 0 or low <= 0:
            continue
        
        body_top = max(open_price, close)
        body_bottom = min(open_price, close)
        upper_wick = high - body_top
        lower_wick = body_bottom - low
        body_size = abs(close - open_price)
        
        # Skip if body is too large (not a rejection pattern)
        if body_size <= 0:
            continue
        
        # Upper rejection: Long upper wick near range_high, closes inside
        if (abs(high - range_high) <= tolerance and
            upper_wick > body_size * 1.5 and  # Wick > 1.5x body
            close < range_high):
            logger.debug(f"Rejection wick detected: upper wick {upper_wick:.2f} > body {body_size:.2f} × 1.5 near range_high")
            return True
        
        # Lower rejection: Long lower wick near range_low, closes inside
        if (abs(low - range_low) <= tolerance and
            lower_wick > body_size * 1.5 and  # Wick > 1.5x body
            close > range_low):
            logger.debug(f"Rejection wick detected: lower wick {lower_wick:.2f} > body {body_size:.2f} × 1.5 near range_low")
            return True
    
    return False


def _calculate_vwap_history(candles_df: Optional[pd.DataFrame], recent_candles: List[Dict[str, Any]], periods: int = 5) -> List[float]:
    """
    Calculate VWAP history from candles for momentum detection.
    
    Args:
        candles_df: DataFrame with OHLCV columns (preferred)
        recent_candles: List of candle dicts (fallback)
        periods: Number of periods to calculate VWAP for
    
    Returns:
        List of VWAP values (most recent first), or empty list if insufficient data
    """
    vwap_history = []
    
    try:
        if candles_df is not None and not candles_df.empty and len(candles_df) >= periods:
            # Use DataFrame (preferred)
            if 'high' in candles_df.columns and 'low' in candles_df.columns and 'close' in candles_df.columns:
                # Calculate typical price
                typical_price = (candles_df['high'] + candles_df['low'] + candles_df['close']) / 3
                
                # Get volume (try different column names)
                volume_col = None
                for col in ['volume', 'tick_volume', 'volumes']:
                    if col in candles_df.columns:
                        volume_col = col
                        break
                
                if volume_col:
                    volumes = candles_df[volume_col].fillna(0)
                else:
                    # No volume data - use simple average
                    volumes = pd.Series([1.0] * len(candles_df), index=candles_df.index)
                
                # Calculate rolling VWAP for last N periods
                for i in range(min(periods, len(candles_df))):
                    end_idx = len(candles_df) - i
                    start_idx = max(0, end_idx - 20)  # Use last 20 candles for each VWAP
                    
                    window_tp = typical_price.iloc[start_idx:end_idx]
                    window_vol = volumes.iloc[start_idx:end_idx]
                    
                    if window_vol.sum() > 0:
                        vwap = (window_tp * window_vol).sum() / window_vol.sum()
                        vwap_history.append(vwap)
                    else:
                        # Fallback to simple average
                        vwap_history.append(window_tp.mean())
                
                # Reverse to get most recent first
                vwap_history = vwap_history[::-1] if vwap_history else []
        
        elif recent_candles and len(recent_candles) >= periods * 4:  # Need enough candles
            # Use list of dicts (fallback)
            # Calculate VWAP for rolling windows
            for i in range(periods):
                start_idx = max(0, len(recent_candles) - (i + 1) * 4 - 20)
                end_idx = len(recent_candles) - i * 4
                
                window_candles = recent_candles[start_idx:end_idx]
                
                if not window_candles:
                    continue
                
                total_pv = 0.0
                total_volume = 0.0
                
                for candle in window_candles:
                    high = candle.get('high', 0)
                    low = candle.get('low', 0)
                    close = candle.get('close', 0)
                    volume = candle.get('volume', candle.get('tick_volume', 1))
                    
                    if volume <= 0:
                        volume = 1  # Fallback
                    
                    typical_price = (high + low + close) / 3
                    total_pv += typical_price * volume
                    total_volume += volume
                
                if total_volume > 0:
                    vwap_history.append(total_pv / total_volume)
                else:
                    # Fallback to simple average
                    typical_prices = [(c.get('high', 0) + c.get('low', 0) + c.get('close', 0)) / 3 for c in window_candles]
                    vwap_history.append(sum(typical_prices) / len(typical_prices) if typical_prices else 0)
            
            # Reverse to get most recent first
            vwap_history = vwap_history[::-1] if vwap_history else []
    
    except Exception as e:
        logger.debug(f"Error calculating VWAP history: {e}")
        vwap_history = []
    
    return vwap_history


def _calculate_bb_width_expansion(candles_df: Optional[pd.DataFrame], recent_candles: List[Dict[str, Any]], 
                                   period: int = 20, lookback: int = 40) -> Optional[float]:
    """
    Calculate Bollinger Bands width expansion percentage.
    
    Args:
        candles_df: DataFrame with OHLC columns (preferred)
        recent_candles: List of candle dicts (fallback)
        period: BB period (default: 20)
        lookback: Historical lookback for comparison (default: 40)
    
    Returns:
        BB width expansion percentage (positive = expanding, negative = contracting), or None if insufficient data
    """
    try:
        if candles_df is not None and not candles_df.empty and len(candles_df) >= period + lookback:
            # Use DataFrame
            closes = candles_df['close'].values
            
            # Calculate current BB width
            current_window = closes[-period:]
            current_sma = np.mean(current_window)
            current_std = np.std(current_window)
            current_bb_width = (current_std * 4) / current_sma * 100 if current_sma > 0 else 0  # As percentage
            
            # Calculate historical BB widths
            historical_widths = []
            for i in range(max(period, len(candles_df) - lookback), len(candles_df) - period):
                if i >= period:
                    hist_window = closes[i - period:i]
                    hist_sma = np.mean(hist_window)
                    hist_std = np.std(hist_window)
                    if hist_sma > 0:
                        hist_width = (hist_std * 4) / hist_sma * 100
                        historical_widths.append(hist_width)
            
            if historical_widths:
                avg_historical_width = np.mean(historical_widths)
                if avg_historical_width > 0:
                    expansion_pct = ((current_bb_width - avg_historical_width) / avg_historical_width) * 100
                    return expansion_pct
        
        elif recent_candles and len(recent_candles) >= period + lookback:
            # Use list of dicts
            closes = [c.get('close', 0) for c in recent_candles[-period - lookback:]]
            closes = [c for c in closes if c > 0]
            
            if len(closes) < period:
                return None
            
            # Calculate current BB width
            current_window = closes[-period:]
            current_sma = sum(current_window) / len(current_window)
            current_variance = sum((x - current_sma) ** 2 for x in current_window) / len(current_window)
            current_std = current_variance ** 0.5
            current_bb_width = (current_std * 4) / current_sma * 100 if current_sma > 0 else 0
            
            # Calculate historical BB widths
            historical_widths = []
            for i in range(max(period, len(closes) - lookback), len(closes) - period):
                if i >= period:
                    hist_window = closes[i - period:i]
                    hist_sma = sum(hist_window) / len(hist_window)
                    hist_variance = sum((x - hist_sma) ** 2 for x in hist_window) / len(hist_window)
                    hist_std = hist_variance ** 0.5
                    if hist_sma > 0:
                        hist_width = (hist_std * 4) / hist_sma * 100
                        historical_widths.append(hist_width)
            
            if historical_widths:
                avg_historical_width = sum(historical_widths) / len(historical_widths)
                if avg_historical_width > 0:
                    expansion_pct = ((current_bb_width - avg_historical_width) / avg_historical_width) * 100
                    return expansion_pct
    
    except Exception as e:
        logger.debug(f"Error calculating BB width expansion: {e}")
    
    return None


def _calculate_volume_from_candles(candles_df: Optional[pd.DataFrame], recent_candles: List[Dict[str, Any]]) -> Tuple[float, float]:
    """
    Calculate current volume and 1-hour average volume from candles.
    
    Args:
        candles_df: DataFrame with OHLCV columns (preferred)
        recent_candles: List of candle dicts (fallback)
    
    Returns:
        (volume_current, volume_1h_avg) tuple
    """
    try:
        if candles_df is not None and not candles_df.empty:
            # Use DataFrame
            volume_col = None
            for col in ['volume', 'tick_volume', 'volumes']:
                if col in candles_df.columns:
                    volume_col = col
                    break
            
            if volume_col:
                volumes = candles_df[volume_col].fillna(0).values
                
                # Current volume (last candle)
                volume_current = float(volumes[-1]) if len(volumes) > 0 else 0.0
                
                # 1-hour average (last 12 M5 candles = 1 hour)
                volume_1h_avg = float(np.mean(volumes[-12:])) if len(volumes) >= 12 else float(np.mean(volumes)) if len(volumes) > 0 else 0.0
                
                return volume_current, volume_1h_avg
        
        elif recent_candles and len(recent_candles) > 0:
            # Use list of dicts
            volumes = []
            for candle in recent_candles:
                vol = candle.get('volume', candle.get('tick_volume', 0))
                volumes.append(vol if vol > 0 else 0)
            
            if volumes:
                volume_current = float(volumes[0])  # Most recent first
                volume_1h_avg = float(sum(volumes[:12]) / min(12, len(volumes))) if len(volumes) >= 12 else float(sum(volumes) / len(volumes))
                return volume_current, volume_1h_avg
    
    except Exception as e:
        logger.debug(f"Error calculating volume from candles: {e}")
    
    return 0.0, 0.0


def _calculate_cvd_data(candles_df: Optional[pd.DataFrame], recent_candles: List[Dict[str, Any]], 
                        order_flow: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Calculate CVD (Cumulative Volume Delta) data for false range detection.
    
    Args:
        candles_df: DataFrame with OHLCV columns (preferred)
        recent_candles: List of candle dicts (fallback)
        order_flow: Optional order flow data with CVD
    
    Returns:
        Dict with CVD data including divergence_strength, or empty dict if unavailable
    """
    cvd_data = {}
    
    try:
        # First, try to get CVD from order flow service
        if order_flow and isinstance(order_flow, dict):
            cvd = order_flow.get('cvd', order_flow.get('cumulative_volume_delta'))
            cvd_divergence = order_flow.get('cvd_divergence', {})
            
            if cvd is not None:
                cvd_data['cvd'] = float(cvd)
                cvd_data['cvd_slope'] = order_flow.get('cvd_slope', 0.0)
                
                if isinstance(cvd_divergence, dict):
                    cvd_data['divergence_strength'] = cvd_divergence.get('strength', 0.0)
                    cvd_data['divergence_type'] = cvd_divergence.get('type')
                else:
                    cvd_data['divergence_strength'] = 0.0
                
                return cvd_data
        
        # Fallback: Calculate CVD from candles
        if candles_df is not None and not candles_df.empty and len(candles_df) >= 10:
            # Use DataFrame
            if 'open' in candles_df.columns and 'close' in candles_df.columns:
                price_changes = candles_df['close'].values - candles_df['open'].values
                
                volume_col = None
                for col in ['volume', 'tick_volume', 'volumes']:
                    if col in candles_df.columns:
                        volume_col = col
                        break
                
                if volume_col:
                    volumes = candles_df[volume_col].fillna(0).values
                    
                    # Calculate volume delta (positive if close > open, negative if close < open)
                    volume_delta = np.where(price_changes > 0, volumes, 
                                          np.where(price_changes < 0, -volumes, 0))
                    
                    # Calculate cumulative volume delta (CVD)
                    cvd = np.cumsum(volume_delta)
                    current_cvd = float(cvd[-1])
                    
                    # Calculate CVD slope (rate of change)
                    if len(cvd) >= 10:
                        cvd_slope = float((cvd[-1] - cvd[-10]) / 10)
                    else:
                        cvd_slope = float((cvd[-1] - cvd[0]) / len(cvd)) if len(cvd) > 1 else 0.0
                    
                    # Simple divergence detection (compare recent CVD trend with price trend)
                    if len(cvd) >= 10:
                        recent_cvd = cvd[-10:]
                        cvd_trend = recent_cvd[-1] - recent_cvd[0]
                        
                        recent_prices = candles_df['close'].values[-10:]
                        price_trend = recent_prices[-1] - recent_prices[0]
                        
                        # Divergence: price and CVD moving in opposite directions
                        if (price_trend > 0 and cvd_trend < 0) or (price_trend < 0 and cvd_trend > 0):
                            divergence_strength = min(1.0, abs(cvd_trend) / max(abs(price_trend), 1) * 10)
                            divergence_type = "bearish" if price_trend > 0 else "bullish"
                        else:
                            divergence_strength = 0.0
                            divergence_type = None
                    else:
                        divergence_strength = 0.0
                        divergence_type = None
                    
                    cvd_data = {
                        'cvd': current_cvd,
                        'cvd_slope': cvd_slope,
                        'divergence_strength': divergence_strength,
                        'divergence_type': divergence_type
                    }
        
        elif recent_candles and len(recent_candles) >= 10:
            # Use list of dicts
            price_changes = []
            volumes = []
            
            for candle in recent_candles[:20]:  # Use last 20 candles
                open_price = candle.get('open', 0)
                close = candle.get('close', 0)
                volume = candle.get('volume', candle.get('tick_volume', 0))
                
                price_changes.append(close - open_price)
                volumes.append(volume if volume > 0 else 0)
            
            if price_changes and volumes:
                # Calculate volume delta
                volume_delta = []
                for i, (price_change, vol) in enumerate(zip(price_changes, volumes)):
                    if price_change > 0:
                        volume_delta.append(vol)
                    elif price_change < 0:
                        volume_delta.append(-vol)
                    else:
                        volume_delta.append(0)
                
                # Calculate CVD
                cvd = []
                cumsum = 0
                for delta in volume_delta:
                    cumsum += delta
                    cvd.append(cumsum)
                
                current_cvd = float(cvd[-1]) if cvd else 0.0
                
                # Calculate CVD slope
                if len(cvd) >= 10:
                    cvd_slope = float((cvd[-1] - cvd[-10]) / 10)
                else:
                    cvd_slope = float((cvd[-1] - cvd[0]) / len(cvd)) if len(cvd) > 1 else 0.0
                
                # Simple divergence detection
                if len(cvd) >= 10:
                    recent_cvd = cvd[-10:]
                    cvd_trend = recent_cvd[-1] - recent_cvd[0]
                    
                    recent_prices = [c.get('close', 0) for c in recent_candles[:10]]
                    price_trend = recent_prices[0] - recent_prices[-1]  # Most recent first
                    
                    if (price_trend > 0 and cvd_trend < 0) or (price_trend < 0 and cvd_trend > 0):
                        divergence_strength = min(1.0, abs(cvd_trend) / max(abs(price_trend), 1) * 10)
                        divergence_type = "bearish" if price_trend > 0 else "bullish"
                    else:
                        divergence_strength = 0.0
                        divergence_type = None
                else:
                    divergence_strength = 0.0
                    divergence_type = None
                
                cvd_data = {
                    'cvd': current_cvd,
                    'cvd_slope': cvd_slope,
                    'divergence_strength': divergence_strength,
                    'divergence_type': divergence_type
                }
    
    except Exception as e:
        logger.debug(f"Error calculating CVD data: {e}")
        cvd_data = {}
    
    return cvd_data


async def analyse_range_scalp_opportunity(
    symbol: str,
    strategy_filter: Optional[str] = None,
    check_risk_filters: bool = True,
    market_data: Optional[Dict] = None,
    indicators: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Analyse range scalping opportunities for a symbol.
    
    Follows the execution flow pipeline:
    1. Range Detection Layer
    2. Data Quality Validation
    3. Risk Filtering Layer
    4. Strategy Scoring Layer
    5. Return analysis results
    
    Args:
        symbol: Trading symbol
        strategy_filter: Optional strategy name to focus on
        check_risk_filters: Whether to apply risk mitigation (default: true)
        market_data: Pre-fetched market data (optional)
        indicators: Pre-calculated indicators (optional)
    
    Returns:
        Analysis results with range structure, risk checks, top strategy, warnings
    """
    try:
        # Load configurations
        config = load_range_scalping_config()
        rr_config = load_rr_config()
        
        # Check if range scalping is enabled
        if not config.get("enabled", False):
            return {
                "range_detected": False,
                "error": "Range scalping is disabled in configuration",
                "warnings": ["Range scalping system is disabled"]
            }
        
        # Initialize components
        range_detector = RangeBoundaryDetector()
        # Pass mt5_service if available (from desktop_agent context)
        mt5_service = market_data.get("mt5_service") if market_data else None
        risk_filters = RangeScalpingRiskFilters(config, mt5_service=mt5_service)
        scorer = RangeScalpingScorer(config, rr_config)
        session_analyzer = SessionAnalyzer()
        bridge = IndicatorBridge()
        
        # Normalize symbol
        symbol_normalized = symbol if symbol.endswith('c') else f"{symbol}c"
        
        # Fetch M15 candles if not provided (needed for dynamic range detection)
        candles_df = None
        if market_data and "m15_df" in market_data:
            candles_df = market_data.get("m15_df")
            if candles_df is None:
                logger.debug(f"m15_df was in market_data but is None for {symbol_normalized}")
        else:
            logger.debug(f"m15_df not found in market_data for {symbol_normalized}, fetching via IndicatorBridge")
        
        # If still None, try to fetch it ourselves
        if candles_df is None or (hasattr(candles_df, 'empty') and candles_df.empty):
            try:
                logger.debug(f"Attempting to fetch M15 candles via IndicatorBridge for {symbol_normalized}")
                all_timeframe_data = bridge.get_multi(symbol_normalized)
                m15_data = all_timeframe_data.get("M15")
                
                if m15_data:
                    # Check if DataFrame already exists
                    if m15_data.get("df") is not None:
                        candles_df = m15_data.get("df")
                        logger.debug(f"✅ Successfully fetched M15 DataFrame: {len(candles_df)} rows")
                    # Otherwise, convert lists to DataFrame (IndicatorBridge returns lists, not df)
                    elif "times" in m15_data or "opens" in m15_data:
                        import pandas as pd
                        times = m15_data.get("times", [])
                        opens = m15_data.get("opens", [])
                        highs = m15_data.get("highs", [])
                        lows = m15_data.get("lows", [])
                        closes = m15_data.get("closes", [])
                        volumes = m15_data.get("volumes", m15_data.get("tick_volume", []))
                        
                        if len(times) > 0 and len(opens) > 0:
                            # Convert times to datetime
                            try:
                                if isinstance(times[0], str):
                                    times_dt = pd.to_datetime(times)
                                else:
                                    # Assume Unix timestamp
                                    times_dt = pd.to_datetime(times, unit='s', errors='coerce')
                            except:
                                times_dt = pd.to_datetime(times, errors='coerce')
                            
                            candles_df = pd.DataFrame({
                                "open": opens,
                                "high": highs,
                                "low": lows,
                                "close": closes,
                                "tick_volume": volumes if volumes else [0] * len(times)
                            }, index=times_dt)
                            
                            if len(candles_df) > 0:
                                logger.debug(f"✅ Converted M15 lists to DataFrame ({len(candles_df)} rows)")
                            else:
                                logger.warning(f"⚠️ Converted M15 DataFrame is empty for {symbol_normalized}")
                        else:
                            logger.warning(f"⚠️ IndicatorBridge M15 data missing times/opens for {symbol_normalized}")
                    else:
                        logger.warning(f"⚠️ IndicatorBridge returned M15 data but missing 'df', 'times', or 'opens' keys for {symbol_normalized}. Available keys: {list(m15_data.keys())}")
                else:
                    logger.warning(f"⚠️ IndicatorBridge returned no M15 data for {symbol_normalized}")
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch M15 candles via IndicatorBridge for {symbol_normalized}: {e}", exc_info=True)
        
        # Get session info
        session_info = session_analyzer.get_current_session()
        session_name = session_info.get("name", "").lower()
        
        # Calculate session start time for filtering candles
        from datetime import datetime, timezone, timedelta
        now_utc = datetime.now(timezone.utc)
        utc_hour = now_utc.hour
        
        # Determine session start hour based on current hour (matching desktop_agent.py logic)
        session_start_hour = None
        if 0 <= utc_hour < 8:
            session_start_hour = 0  # Asian session
        elif 8 <= utc_hour < 13:
            session_start_hour = 8  # London session
        elif 13 <= utc_hour < 16:
            session_start_hour = 13  # Overlap (use overlap start)
        elif 16 <= utc_hour < 20:
            session_start_hour = 13  # NY session (started at overlap)
        else:  # 20-24 (Late NY)
            session_start_hour = 13  # Late NY, still part of NY session
        
        # Calculate session_start datetime
        session_start_time = None
        if session_start_hour is not None:
            today = now_utc.date()
            session_start_time = datetime.combine(today, datetime.min.time()).replace(
                hour=session_start_hour, minute=0, second=0, tzinfo=timezone.utc
            )
            # If current hour < session_start_hour, session started yesterday
            if session_start_hour > utc_hour:
                session_start_time = session_start_time - timedelta(days=1)
        
        # Get session adjustments from RR config
        session_adjustments = rr_config.get("session_adjustments", {}).get(session_name, {})
        
        # ========== STEP 1: RANGE DETECTION ==========
        logger.info(f"🔍 Detecting range for {symbol_normalized}...")
        
        range_data = None
        range_detected = False
        
        # Get required data from market_data
        session_high = market_data.get("session_high") if market_data else None
        session_low = market_data.get("session_low") if market_data else None
        pdh = market_data.get("pdh") if market_data else None
        pdl = market_data.get("pdl") if market_data else None
        vwap = market_data.get("vwap") if market_data else None
        atr = market_data.get("atr") if market_data else market_data.get("atr_5m") if market_data else None
        
        # Log what we received for debugging
        logger.debug(f"Range detection inputs for {symbol_normalized}:")
        logger.debug(f"   → session_high: {session_high}, session_low: {session_low}")
        logger.debug(f"   → pdh: {pdh}, pdl: {pdl}")
        logger.debug(f"   → vwap: {vwap}, atr: {atr}")
        logger.debug(f"   → candles_df: {'✅' if candles_df is not None and not (hasattr(candles_df, 'empty') and candles_df.empty) else '❌ None/Empty'}")
        logger.debug(f"   → session_start_time: {session_start_time}")
        
        # Try session range first
        try:
            if session_high is not None and session_low is not None:
                # Pass M15 DataFrame for touch count calculation
                m15_df = market_data.get("m15_df") if market_data else None
                range_data = range_detector.detect_range(
                    symbol=symbol_normalized,
                    timeframe="M15",
                    range_type="session",
                    candles_df=m15_df,  # Pass DataFrame for touch counting
                    session_high=session_high,
                    session_low=session_low,
                    vwap=vwap,
                    atr=atr,
                    session_start_time=session_start_time  # Filter candles to current session only
                )
                
                if range_data:
                    range_detected = True
                    logger.info(f"✅ Session range detected: {range_data.range_low:.2f} - {range_data.range_high:.2f}")
            else:
                logger.debug(f"Skipping session range: session_high={session_high}, session_low={session_low}")
        except Exception as e:
            logger.warning(f"Session range detection failed: {e}", exc_info=True)
        
        # Fallback to daily range
        if not range_data:
            try:
                if pdh is not None and pdl is not None:
                    range_data = range_detector.detect_range(
                        symbol=symbol_normalized,
                        timeframe="M15",
                        range_type="daily",
                        pdh=pdh,
                        pdl=pdl,
                        vwap=vwap,
                        atr=atr
                    )
                    if range_data:
                        range_detected = True
                        logger.info(f"✅ Daily range detected: {range_data.range_low:.2f} - {range_data.range_high:.2f}")
                else:
                    logger.debug(f"Skipping daily range: pdh={pdh}, pdl={pdl}")
            except Exception as e:
                logger.warning(f"Daily range detection failed: {e}", exc_info=True)
        
        # Fallback to dynamic range
        if not range_data:
            try:
                # Log candles_df status for debugging
                if candles_df is None:
                    logger.warning(f"⚠️ candles_df is None for dynamic range detection")
                elif hasattr(candles_df, 'empty') and candles_df.empty:
                    logger.warning(f"⚠️ candles_df is empty for dynamic range detection")
                elif hasattr(candles_df, '__len__'):
                    logger.debug(f"candles_df has {len(candles_df)} rows for dynamic range detection")
                
                range_data = range_detector.detect_range(
                    symbol=symbol_normalized,
                    timeframe="M15",
                    range_type="dynamic",
                    candles_df=candles_df,
                    vwap=vwap,
                    atr=atr
                )
                if range_data:
                    range_detected = True
                    logger.info(f"✅ Dynamic range detected: {range_data.range_low:.2f} - {range_data.range_high:.2f}")
            except Exception as e:
                logger.warning(f"Dynamic range detection failed: {e}", exc_info=True)
        
        if not range_detected or not range_data:
            return {
                "range_detected": False,
                "error": "No valid range detected",
                "warnings": ["Unable to detect range structure - market may be trending or data insufficient"]
            }
        
        # ========== STEP 2: DATA QUALITY VALIDATION ==========
        data_quality_warnings = []
        if check_risk_filters:
            logger.info(f"🔍 Checking data quality for {symbol_normalized}...")
            
            required_sources = ["mt5_candles", "vwap"]
            # Pass VWAP from market_data if available (assumes it's fresh)
            vwap_value = market_data.get("vwap") if market_data else None
            all_available, quality_report, warnings = risk_filters.check_data_quality(
                symbol=symbol_normalized,
                required_sources=required_sources,
                vwap_value=vwap_value  # Pass freshly calculated VWAP
            )
            
            data_quality_warnings.extend(warnings)
            
            # Note: Don't block analysis if data quality fails - just warn
            # The risk filters will handle blocking trades
        
        # ========== STEP 3: RISK FILTERING LAYER ==========
        if check_risk_filters:
            logger.info(f"🔍 Applying risk filters for {symbol_normalized}...")
            
            current_price = market_data.get("current_price", 0) if market_data else 0
            if current_price <= 0:
                logger.warning(f"Invalid current_price: {current_price} for {symbol_normalized}")
                current_price = range_data.range_mid  # Fallback to range mid
            
            effective_atr = risk_filters.calculate_effective_atr(
                atr_5m=market_data.get("atr_5m", 0) if market_data else 0,
                bb_width=market_data.get("bb_width", 0) if market_data else 0,
                price_mid=range_data.range_mid
            )
            
            # 3-Confluence Rule
            range_width = range_data.range_high - range_data.range_low
            price_position = (current_price - range_data.range_low) / range_width if range_width > 0 else 0.5
            
            # Get RSI and check for extremes
            rsi = indicators.get("rsi", 50) if indicators else 50
            rsi_extreme = (rsi < 30) or (rsi > 70)
            
            # Check order flow signal
            order_flow_signal = market_data.get("order_flow", {}).get("signal", "NEUTRAL") if market_data else "NEUTRAL"
            tape_pressure = order_flow_signal in ["BULLISH", "BEARISH"]
            
            # Detect rejection wick from recent candles
            recent_candles = market_data.get("recent_candles", []) if market_data else []
            rejection_wick = _detect_rejection_wick(
                recent_candles=recent_candles,
                range_high=range_data.range_high,
                range_low=range_data.range_low,
                atr=effective_atr
            )
            
            signals = {
                "rsi": rsi,
                "rsi_extreme": rsi_extreme,
                "rejection_wick": rejection_wick,  # Now calculated from candle analysis
                "tape_pressure": tape_pressure,
                "at_pdh": abs(current_price - range_data.range_high) < (effective_atr * 0.1) if effective_atr > 0 else False,
                "at_pdl": abs(current_price - range_data.range_low) < (effective_atr * 0.1) if effective_atr > 0 else False
            }
            
            confluence_score, component_scores, missing_components = risk_filters.check_3_confluence_rule_weighted(
                range_data=range_data,
                price_position=price_position,
                signals=signals,
                atr=effective_atr
            )
            
            # Calculate VWAP momentum for false range detection
            vwap_history = _calculate_vwap_history(candles_df, recent_candles, periods=5)
            if vwap_history and len(vwap_history) >= 2:
                vwap_slope_pct_atr = risk_filters.calculate_vwap_momentum(
                    vwap_values=vwap_history,
                    atr=effective_atr,
                    price_mid=range_data.range_mid
                )
            else:
                # Fallback to simplified calculation if insufficient data
                logger.debug(f"Insufficient data for VWAP history, using simplified calculation")
                vwap_slope_pct_atr = risk_filters.calculate_vwap_momentum(
                    vwap_values=[range_data.range_mid] * 5,
                    atr=effective_atr,
                    price_mid=range_data.range_mid
                )
            
            # Calculate CVD data for false range detection
            order_flow = market_data.get("order_flow", {}) if market_data else {}
            cvd_data = _calculate_cvd_data(candles_df, recent_candles, order_flow)
            
            # Check false range
            is_false_range, false_range_flags = risk_filters.detect_false_range(
                range_data=range_data,
                volume_trend=market_data.get("volume_trend", {}) if market_data else {},
                candles_df=candles_df,  # Pass DataFrame if available
                vwap_slope_pct_atr=vwap_slope_pct_atr,
                cvd_data=cvd_data if cvd_data else None
            )
            
            # Reuse VWAP momentum for range validity check (already calculated above)
            
            # Calculate BB width expansion from historical candles
            bb_width_expansion = _calculate_bb_width_expansion(candles_df, recent_candles)
            
            # Check range validity
            range_valid, invalidation_signals = risk_filters.check_range_validity(
                range_data=range_data,
                current_price=current_price,
                recent_candles=market_data.get("recent_candles", []) if market_data else [],
                vwap_slope_pct_atr=vwap_slope_pct_atr,
                bb_width_expansion=bb_width_expansion,
                candles_df_m15=candles_df,
                atr_m15=effective_atr
            )
            
            # Session filters
            session_allows, session_reason = risk_filters.check_session_filters(
                current_time=None,  # Uses current time by default
                broker_timezone_offset_hours=config.get("broker_timezone", {}).get("offset_hours", 0)
            )
            
            # Trade activity criteria
            # Calculate price deviation (absolute distance from VWAP/range_mid)
            price_deviation = abs(current_price - range_data.range_mid)
            
            # Get volume data - calculate from candles if not provided
            volume_current = market_data.get("volume_current", 0) if market_data else 0
            volume_1h_avg = market_data.get("volume_1h_avg", 0) if market_data else 0
            
            # If no volume data available, calculate from candles
            if volume_current == 0 and volume_1h_avg == 0:
                calc_volume_current, calc_volume_1h_avg = _calculate_volume_from_candles(candles_df, recent_candles)
                if calc_volume_current > 0 and calc_volume_1h_avg > 0:
                    volume_current = calc_volume_current
                    volume_1h_avg = calc_volume_1h_avg
                    logger.debug(f"Calculated volume from candles: current={volume_current:.2f}, 1h_avg={volume_1h_avg:.2f}")
                else:
                    # Still no volume data - set to default to skip volume ratio check
                    volume_current = 100
                    volume_1h_avg = 100  # Ratio = 1.0, will pass volume check
                    logger.debug(f"No volume data available for {symbol_normalized}, using fallback")
            
            # For cooldown: if no previous trades, set to large value to skip check
            # (In production, this would query trade history)
            minutes_since_last_trade = 999  # Skip cooldown if no trade tracking available
            
            # Get upcoming news events from news service
            upcoming_news = []
            if risk_filters.news_service:
                try:
                    if hasattr(risk_filters.news_service, 'get_upcoming_events'):
                        upcoming_news = risk_filters.news_service.get_upcoming_events(hours_ahead=24)
                        if upcoming_news:
                            logger.debug(f"Found {len(upcoming_news)} upcoming news events")
                except Exception as e:
                    logger.debug(f"Error getting upcoming news: {e}")
            
            trade_activity_sufficient, activity_failures = risk_filters.check_trade_activity_criteria(
                symbol=symbol_normalized,
                volume_current=volume_current,
                volume_1h_avg=volume_1h_avg,
                price_deviation_from_vwap=price_deviation,
                atr=effective_atr,
                minutes_since_last_trade=minutes_since_last_trade,
                upcoming_news=upcoming_news
            )
            
            # Nested range alignment check
            # Try to detect nested ranges from market_data if available
            h1_range = None
            m5_range = None
            
            # Check if we have nested range data in market_data
            if market_data:
                nested_ranges = market_data.get("nested_ranges", {})
                if nested_ranges:
                    h1_range = nested_ranges.get("H1")
                    m5_range = nested_ranges.get("M5")
            
            # Use existing method to check alignment
            nested_aligned, nested_reason = risk_filters.check_nested_range_alignment(
                h1_range=h1_range,
                m15_range=range_data,
                m5_range=m5_range,
                trade_direction="BUY" if price_position > 0.5 else "SELL"  # Simplified direction
            )
            
            # Check if all risk filters pass
            risk_passed = (
                confluence_score >= 80 and
                not is_false_range and
                range_valid and
                session_allows and
                trade_activity_sufficient
            )
            
            risk_checks = {
                "3_confluence_passed": confluence_score >= 80,
                "confluence_score": confluence_score,
                "component_scores": component_scores,
                "missing_components": missing_components,
                "false_range_detected": is_false_range,
                "false_range_flags": false_range_flags,
                "range_valid": range_valid,
                "invalidation_signals": invalidation_signals,
                "session_allows_trading": session_allows,
                "session_reason": session_reason,
                "trade_activity_sufficient": trade_activity_sufficient,
                "activity_failures": activity_failures,
                "nested_ranges_aligned": nested_aligned,
                "risk_passed": risk_passed
            }
            
            # NOTE: Even if risk filters fail, we still score strategies
            # to show what WOULD be available if conditions improved
            # This provides better feedback to the user
            if not risk_passed:
                warnings_list = []
                if confluence_score < 80:
                    warnings_list.append(f"3-confluence score too low: {confluence_score}/100 (required: 80+)")
                if is_false_range:
                    warnings_list.append(f"False range detected: {', '.join(false_range_flags)}")
                if not range_valid:
                    warnings_list.append(f"Range invalidated: {', '.join(invalidation_signals)}")
                if not session_allows:
                    warnings_list.append(f"Session filter blocked: {session_reason}")
                if not trade_activity_sufficient:
                    warnings_list.append(f"Trade activity insufficient: {', '.join(activity_failures)}")
                
                # Store warnings but continue to strategy scoring
                data_quality_warnings.extend(warnings_list)
        
        else:
            risk_checks = {
                "risk_filters_skipped": True
            }
        
        # ========== STEP 4: STRATEGY SCORING LAYER ==========
        logger.info(f"🔍 Scoring strategies for {symbol_normalized}...")
        
        # Get ADX for dynamic weighting
        adx_h1 = indicators.get("adx_h1", 20) if indicators else 20
        
        # Prepare market data for scorer
        scorer_market_data = {
            "current_price": current_price,
            "indicators": indicators or {},
            "effective_atr": effective_atr,
            "pdh": market_data.get("pdh") if market_data else None,
            "pdl": market_data.get("pdl") if market_data else None,
            "volume_current": market_data.get("volume_current", 0) if market_data else 0,
            "volume_1h_avg": market_data.get("volume_1h_avg", 0) if market_data else 0,
            "recent_candles": market_data.get("recent_candles", []) if market_data else [],
            "order_flow": market_data.get("order_flow", {}) if market_data else {},
            "session_adjustments": session_adjustments,
            "adx_h1": adx_h1
        }
        
        # Score all strategies
        scored_strategies = scorer.score_all_strategies(
            symbol=symbol_normalized,
            range_data=range_data,
            market_data=scorer_market_data,
            session_info=session_info,
            adx_h1=adx_h1
        )
        
        # Filter by strategy_filter if provided
        if strategy_filter and scored_strategies:
            scored_strategies = [s for s in scored_strategies if s.entry_signal.strategy_name == strategy_filter]
        
        # Get top strategy
        top_strategy = None
        if scored_strategies:
            top_score = scored_strategies[0]
            entry_signal = top_score.entry_signal
            
            top_strategy = {
                "name": entry_signal.strategy_name,
                "direction": entry_signal.direction,
                "entry_price": entry_signal.entry_price,
                "stop_loss": entry_signal.stop_loss,
                "take_profit": entry_signal.take_profit,
                "r_r_ratio": entry_signal.r_r_ratio,
                "lot_size": entry_signal.lot_size,
                "confidence": entry_signal.confidence,
                "confluence_score": top_score.total_score,
                "weighted_score": top_score.weighted_score,
                "reason": entry_signal.reason
            }
        
        # Prepare warnings
        warnings_list = []
        if not scored_strategies:
            # Provide more context about why no strategies were found
            if adx_h1 > 25:
                warnings_list.append(f"ADX {adx_h1:.1f} > 25 - Market trending, range scalps disabled (all strategies filtered)")
            elif risk_checks.get("3_confluence_passed") == False:
                warnings_list.append(f"No strategies found - Entry conditions not met (confluence score: {risk_checks.get('confluence_score', 0)}/100)")
            elif risk_checks.get("range_valid") == False:
                warnings_list.append("No strategies found - Range invalidated or breaking down")
            else:
                warnings_list.append("No strategies found - Entry conditions not met by any strategy (check indicators, price position, order flow)")
        elif adx_h1 > 25:
            warnings_list.append(f"ADX {adx_h1:.1f} > 25 - Market trending, range scalps disabled")
        
        # Combine all warnings (data quality + strategy warnings)
        all_warnings = data_quality_warnings + warnings_list
        
        # Prepare early exit triggers
        early_exit_triggers = [
            "Range invalidation (2+ candles outside range)",
            "M15 BOS confirmed",
            "Quick move to +0.5R (move SL to breakeven)",
            "Stagnation after 1 hour",
            "Opposite order flow shift"
        ]
        
        # Build response
        response = {
            "range_detected": True,
            "range_structure": range_data.to_dict(),
            "risk_checks": risk_checks,
            "top_strategy": top_strategy,
            "early_exit_triggers": early_exit_triggers,
            "session_context": f"{session_info.get('name', 'Unknown')} session",
            "warnings": all_warnings if all_warnings else []
        }
        
        logger.info(f"✅ Range scalping analysis complete for {symbol_normalized}")
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Range scalping analysis failed: {e}", exc_info=True)
        return {
            "range_detected": False,
            "error": f"Analysis failed: {str(e)}",
            "warnings": [f"Error during analysis: {str(e)}"]
        }

