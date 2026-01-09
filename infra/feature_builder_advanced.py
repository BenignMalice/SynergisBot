"""
Feature Builder Advanced - Advanced Technical Indicators
=========================================================
Implements 11 advanced technical features for institutional-grade analysis:

1. RMAG (Relative Moving Average Gap) - stretch from mean
2. EMA Slope Strength - trend quality
3. Bollinger-ADX Fusion - squeeze/breakout state
4. RSI-ADX Pressure Ratio - momentum quality
5. Candle Body-Wick Profile - conviction vs rejection
6. Liquidity Targets - swing highs/lows, PDH/PDL, equal levels
7. Fair Value Gaps (FVG) - imbalance zones
8. VWAP Deviation Zones - institutional mean reversion
9. Momentum Acceleration - MACD/RSI velocity
10. Multi-Timeframe Alignment Score - confluence rating
11. Volume Profile HVN/LVN - magnet/vacuum zones

Anchors:
    # === ANCHOR: IMPORTS ===
    # === ANCHOR: CLASS_INIT ===
    # === ANCHOR: RMAG ===
    # === ANCHOR: EMA_SLOPE ===
    # === ANCHOR: BOLLINGER_ADX ===
    # === ANCHOR: RSI_ADX_PRESSURE ===
    # === ANCHOR: CANDLE_PROFILE ===
    # === ANCHOR: LIQUIDITY_TARGETS ===
    # === ANCHOR: FVG ===
    # === ANCHOR: VWAP_DEVIATION ===
    # === ANCHOR: MOMENTUM_ACCEL ===
    # === ANCHOR: MTF_ALIGNMENT ===
    # === ANCHOR: VOLUME_PROFILE ===
    # === ANCHOR: BUILD_FEATURES ===
    # === ANCHOR: COMPACT_FORMAT ===
"""

from __future__ import annotations

# === ANCHOR: IMPORTS ===
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5

from infra.mt5_service import MT5Service
from infra.indicator_bridge import IndicatorBridge
from infra.feature_patterns import PatternFeatures

logger = logging.getLogger(__name__)

# === ANCHOR: CLASS_INIT ===
class FeatureBuilderAdvanced:
    """
    Advanced feature builder with institutional-grade technical indicators.
    Designed for fast computation (<5ms per timeframe) and compact output.
    """
    
    def __init__(self, mt5svc: MT5Service, bridge: IndicatorBridge):
        self.mt5svc = mt5svc
        self.bridge = bridge
        self.cache = {}
        self.pattern_features = PatternFeatures()
        
    def build_features(self, symbol: str, timeframes: List[str] = None) -> Dict[str, Any]:
        """
        Build comprehensive advanced features for symbol across timeframes.
        Returns compact, AI-ready features optimized for GPT consumption.
        
        Args:
            symbol: Trading symbol (e.g., "XAUUSDc")
            timeframes: List of timeframes (defaults to ["M5", "M15", "H1"])
            
        Returns:
            Dict with compact feature representation
        """
        if timeframes is None:
            timeframes = ["M5", "M15", "H1"]
            
        try:
            # Get multi-timeframe data
            multi = self.bridge.get_multi(symbol)
            if not multi:
                logger.warning(f"No data available for {symbol}")
                return self._empty_features()
                
            features = {}
            
            # Build features for each timeframe
            for tf in timeframes:
                if tf not in multi:
                    continue
                    
                data = multi[tf]
                df = self._data_to_dataframe(data)
                
                if df is None or len(df) < 300:
                    logger.debug(f"Insufficient data for {symbol} {tf}: {len(df) if df is not None else 0} bars")
                    continue
                
                # Get current price for calculations
                current_price = df['close'].iloc[-1]
                
                # Compute all features for this timeframe
                tf_features = {}
                tf_features.update(self._compute_rmag(df, current_price))
                tf_features.update(self._compute_ema_slope(df))
                tf_features.update(self._compute_bollinger_adx(df, data))
                tf_features.update(self._compute_rsi_adx_pressure(df, data))
                tf_features.update(self._compute_candle_profile(df))
                tf_features.update(self._compute_liquidity_targets(df, current_price))
                # Add stop cluster detection (wick-based liquidity zones)
                stop_clusters = self._compute_stop_clusters(df, current_price)
                # Merge stop clusters into liquidity dict
                if "liquidity" in tf_features:
                    tf_features["liquidity"].update(stop_clusters.get("liquidity", {}))
                tf_features.update(self._compute_fvg(df, current_price))
                tf_features.update(self._compute_vwap_deviation(df, current_price, data))
                tf_features.update(self._compute_momentum_accel(df, data))
                # Add candlestick pattern detection
                pattern_data = self.pattern_features.compute(df, symbol, tf)
                tf_features.update(pattern_data)
                
                features[tf] = tf_features
            
            # Add multi-timeframe alignment score
            features["mtf_score"] = self._compute_mtf_alignment(features, multi)
            
            # Add volume profile (from primary timeframe)
            primary_tf = timeframes[0] if timeframes else "M15"
            if primary_tf in multi:
                df = self._data_to_dataframe(multi[primary_tf])
                if df is not None and len(df) >= 100:
                    features["vp"] = self._compute_volume_profile(df, df['close'].iloc[-1])
            
            return self._compact_format(features, symbol)
            
        except Exception as e:
            logger.error(f"Feature building failed for {symbol}: {e}", exc_info=True)
            return self._empty_features()
    
    # === ANCHOR: RMAG ===
    def _compute_rmag(self, df: pd.DataFrame, current_price: float) -> Dict[str, Any]:
        """
        Relative Moving Average Gap - quantify stretch from mean.
        Returns ATR-normalized distance from EMA200 and VWAP.
        """
        try:
            # Get ATR for normalization
            atr = self._calculate_atr(df, 14)
            if atr == 0:
                atr = df['close'].std() * 0.1  # Fallback
            
            # Calculate EMA200
            ema200 = df['close'].ewm(span=200, adjust=False).mean().iloc[-1]
            
            # Calculate VWAP (session VWAP - simplified)
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            vwap = (typical_price * df['volume']).sum() / df['volume'].sum() if df['volume'].sum() > 0 else typical_price.mean()
            
            # Normalize by ATR
            gap_ema200_atr = round((current_price - ema200) / atr, 2)
            gap_vwap_atr = round((current_price - vwap) / atr, 2)
            
            return {
                "rmag": {
                    "ema200_atr": gap_ema200_atr,
                    "vwap_atr": gap_vwap_atr
                }
            }
        except Exception as e:
            logger.debug(f"RMAG calculation failed: {e}")
            return {"rmag": {"ema200_atr": 0.0, "vwap_atr": 0.0}}
    
    # === ANCHOR: EMA_SLOPE ===
    def _compute_ema_slope(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        EMA Slope Strength - trend quality vs flat drift.
        Returns ATR-normalized slope over 20 bars.
        """
        try:
            lookback = 20
            if len(df) < lookback + 200:
                return {"ema_slope": {"ema50": 0.0, "ema200": 0.0}}
            
            atr = self._calculate_atr(df, 14)
            if atr == 0:
                atr = 1.0
            
            # Calculate EMAs
            ema50 = df['close'].ewm(span=50, adjust=False).mean()
            ema200 = df['close'].ewm(span=200, adjust=False).mean()
            
            # Calculate slopes
            slope_ema50 = (ema50.iloc[-1] - ema50.iloc[-lookback]) / (lookback * atr)
            slope_ema200 = (ema200.iloc[-1] - ema200.iloc[-lookback]) / (lookback * atr)
            
            return {
                "ema_slope": {
                    "ema50": round(slope_ema50, 3),
                    "ema200": round(slope_ema200, 3)
                }
            }
        except Exception as e:
            logger.debug(f"EMA slope calculation failed: {e}")
            return {"ema_slope": {"ema50": 0.0, "ema200": 0.0}}
    
    # === ANCHOR: BOLLINGER_ADX ===
    def _compute_bollinger_adx(self, df: pd.DataFrame, data: Dict) -> Dict[str, Any]:
        """
        Bollinger-ADX Fusion - squeeze/breakout state.
        Combines BB width with ADX to identify volatility regimes.
        """
        try:
            # Calculate Bollinger Bands
            bb_period = 20
            bb_std = 2
            sma = df['close'].rolling(window=bb_period).mean()
            std = df['close'].rolling(window=bb_period).std()
            bb_upper = sma + (std * bb_std)
            bb_lower = sma - (std * bb_std)
            
            # Get current BB width
            atr = self._calculate_atr(df, 14)
            if atr == 0:
                atr = 1.0
            bb_width = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / atr
            
            # Get ADX from data (if available) or calculate
            adx = data.get('adx', 0.0) if isinstance(data.get('adx'), (int, float)) else \
                  data.get('adx', [0.0])[-1] if isinstance(data.get('adx'), list) and len(data.get('adx', [])) > 0 else 0.0
            
            # Calculate BB width percentile (is it squeezed?)
            if len(df) >= 100:
                bb_width_series = (bb_upper - bb_lower) / atr
                bb_width_p20 = bb_width_series.iloc[-100:].quantile(0.20)
                is_squeeze = bb_width < bb_width_p20
            else:
                is_squeeze = bb_width < 1.0
            
            # Determine state
            if is_squeeze and adx < 20:
                state = "squeeze_no_trend"
            elif is_squeeze and adx >= 20:
                state = "squeeze_with_trend"
            elif not is_squeeze and adx >= 25:
                state = "expansion_strong_trend"
            else:
                state = "expansion_weak_trend"
            
            return {
                "vol_trend": {
                    "bb_width": round(bb_width, 2),
                    "adx": round(adx, 1),
                    "state": state
                }
            }
        except Exception as e:
            logger.debug(f"Bollinger-ADX calculation failed: {e}")
            return {"vol_trend": {"bb_width": 0.0, "adx": 0.0, "state": "unknown"}}
    
    # === ANCHOR: RSI_ADX_PRESSURE ===
    def _compute_rsi_adx_pressure(self, df: pd.DataFrame, data: Dict) -> Dict[str, Any]:
        """
        RSI-ADX Pressure Ratio - momentum quality.
        High RSI with weak ADX = fake push; high/high = quality trend.
        """
        try:
            # Calculate RSI
            rsi = self._calculate_rsi(df, 14)
            
            # Get ADX
            adx = data.get('adx', 0.0) if isinstance(data.get('adx'), (int, float)) else \
                  data.get('adx', [0.0])[-1] if isinstance(data.get('adx'), list) and len(data.get('adx', [])) > 0 else 0.0
            
            # Calculate ratio
            ratio = rsi / max(adx, 1.0)
            
            return {
                "pressure": {
                    "ratio": round(ratio, 2),
                    "rsi": round(rsi, 1),
                    "adx": round(adx, 1)
                }
            }
        except Exception as e:
            logger.debug(f"RSI-ADX pressure calculation failed: {e}")
            return {"pressure": {"ratio": 0.0, "rsi": 50.0, "adx": 0.0}}
    
    # === ANCHOR: CANDLE_PROFILE ===
    def _compute_candle_profile(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Candle Body-Wick Profile - conviction vs rejection.
        Analyzes last 3 candles for body/wick ratios.
        """
        try:
            atr = self._calculate_atr(df, 14)
            if atr == 0:
                atr = 1.0
            
            profiles = []
            for i in range(-3, 0):  # Last 3 candles
                if abs(i) > len(df):
                    continue
                    
                row = df.iloc[i]
                body = abs(row['close'] - row['open'])
                upper_wick = row['high'] - max(row['open'], row['close'])
                lower_wick = min(row['open'], row['close']) - row['low']
                total_wick = upper_wick + lower_wick
                
                # Normalize by ATR
                body_atr = body / atr
                wick_to_body = total_wick / max(body, atr * 0.1)
                
                # Determine type
                if wick_to_body > 2.0:
                    if upper_wick > lower_wick * 1.5:
                        ctype = "rejection_up"
                    elif lower_wick > upper_wick * 1.5:
                        ctype = "rejection_down"
                    else:
                        ctype = "indecision"
                elif body_atr > 0.5:
                    ctype = "conviction"
                else:
                    ctype = "neutral"
                
                profiles.append({
                    "idx": i,
                    "body_atr": round(body_atr, 2),
                    "w2b": round(wick_to_body, 2),
                    "type": ctype
                })
            
            return {"candle_profile": profiles}
        except Exception as e:
            logger.debug(f"Candle profile calculation failed: {e}")
            return {"candle_profile": []}
    
    # === ANCHOR: LIQUIDITY_TARGETS ===
    def _compute_liquidity_targets(self, df: pd.DataFrame, current_price: float) -> Dict[str, Any]:
        """
        Liquidity Targets - swing highs/lows, PDH/PDL, equal levels.
        Identifies key liquidity zones that price tends to target.
        """
        try:
            atr = self._calculate_atr(df, 14)
            if atr == 0:
                atr = 1.0
            
            # Previous Day High/Low (last 24 hours of data)
            # Assuming 15-min bars, 96 bars = 24 hours
            bars_per_day = 96 if len(df) > 96 else len(df) // 2
            recent = df.iloc[-bars_per_day:]
            pdh = recent['high'].max()
            pdl = recent['low'].min()
            
            # Recent swing points (lookback 50 bars)
            lookback = min(50, len(df) - 1)
            swing_highs = []
            swing_lows = []
            
            for i in range(len(df) - lookback, len(df) - 5):
                if i < 5 or i >= len(df) - 5:
                    continue
                    
                # Check for swing high
                if df['high'].iloc[i] == df['high'].iloc[i-5:i+5].max():
                    swing_highs.append(df['high'].iloc[i])
                    
                # Check for swing low
                if df['low'].iloc[i] == df['low'].iloc[i-5:i+5].min():
                    swing_lows.append(df['low'].iloc[i])
            
            # Check for equal highs/lows (within 0.1% tolerance)
            tolerance = 0.001
            equal_highs = self._find_equal_levels(swing_highs, tolerance)
            equal_lows = self._find_equal_levels(swing_lows, tolerance)
            
            # Distance to targets (ATR-normalized)
            pdl_dist_atr = round(abs(current_price - pdl) / atr, 2)
            pdh_dist_atr = round(abs(pdh - current_price) / atr, 2)
            
            return {
                "liquidity": {
                    "pdl_dist_atr": pdl_dist_atr,
                    "pdh_dist_atr": pdh_dist_atr,
                    "equal_highs": equal_highs,
                    "equal_lows": equal_lows,
                    "pdh": round(pdh, 5),
                    "pdl": round(pdl, 5)
                }
            }
        except Exception as e:
            logger.debug(f"Liquidity targets calculation failed: {e}")
            return {"liquidity": {"pdl_dist_atr": 0.0, "pdh_dist_atr": 0.0, "equal_highs": False, "equal_lows": False}}
    
    def _compute_stop_clusters(self, df: pd.DataFrame, current_price: float) -> Dict[str, Any]:
        """
        Compute stop clusters (wick-based liquidity zones).
        Detects clusters of candle wicks > 0.5 ATR at similar price levels.
        """
        try:
            from domain.liquidity import detect_stop_clusters
            
            atr = self._calculate_atr(df, 14)
            if atr == 0:
                atr = 1.0
            
            # Detect stop clusters
            stop_clusters = detect_stop_clusters(
                df, atr,
                lookback=min(50, len(df)),
                min_wick_atr=0.5,
                cluster_tolerance_atr=0.15,
                min_wicks=3
            )
            
            return {
                "liquidity": {
                    "stop_cluster_above": stop_clusters.get("stop_cluster_above", False),
                    "stop_cluster_above_price": stop_clusters.get("stop_cluster_above_price", 0.0),
                    "stop_cluster_above_count": stop_clusters.get("stop_cluster_above_count", 0),
                    "stop_cluster_above_dist_atr": stop_clusters.get("stop_cluster_above_dist_atr", 999.0),
                    "stop_cluster_below": stop_clusters.get("stop_cluster_below", False),
                    "stop_cluster_below_price": stop_clusters.get("stop_cluster_below_price", 0.0),
                    "stop_cluster_below_count": stop_clusters.get("stop_cluster_below_count", 0),
                    "stop_cluster_below_dist_atr": stop_clusters.get("stop_cluster_below_dist_atr", 999.0)
                }
            }
            
        except Exception as e:
            logger.debug(f"Stop cluster calculation failed: {e}")
            return {"liquidity": {}}
    
    # === ANCHOR: FVG ===
    def _compute_fvg(self, df: pd.DataFrame, current_price: float) -> Dict[str, Any]:
        """
        Fair Value Gaps (FVG) - imbalance zones.
        Classic 3-bar pattern: low[t] > high[t-2] (bull) or high[t] < low[t-2] (bear).
        """
        try:
            if len(df) < 10:
                return {"fvg": {"type": "none", "dist_to_fill_atr": 0.0}}
            
            atr = self._calculate_atr(df, 14)
            if atr == 0:
                atr = 1.0
            
            # Scan last 50 bars for FVGs
            fvgs = []
            lookback = min(50, len(df) - 3)
            
            for i in range(len(df) - lookback, len(df) - 2):
                # Bull FVG: low[i] > high[i-2]
                if df['low'].iloc[i] > df['high'].iloc[i-2]:
                    gap_top = df['low'].iloc[i]
                    gap_bottom = df['high'].iloc[i-2]
                    fvgs.append({
                        "type": "bull",
                        "top": gap_top,
                        "bottom": gap_bottom,
                        "idx": i
                    })
                    
                # Bear FVG: high[i] < low[i-2]
                elif df['high'].iloc[i] < df['low'].iloc[i-2]:
                    gap_top = df['low'].iloc[i-2]
                    gap_bottom = df['high'].iloc[i]
                    fvgs.append({
                        "type": "bear",
                        "top": gap_top,
                        "bottom": gap_bottom,
                        "idx": i
                    })
            
            # Find nearest unfilled FVG
            nearest_fvg = None
            min_dist = float('inf')
            
            for fvg in fvgs:
                # Check if FVG is unfilled (price hasn't entered the gap)
                if fvg["type"] == "bull" and current_price > fvg["top"]:
                    # Unfilled bull FVG below price
                    dist = current_price - fvg["top"]
                    if dist < min_dist:
                        min_dist = dist
                        nearest_fvg = fvg
                elif fvg["type"] == "bear" and current_price < fvg["bottom"]:
                    # Unfilled bear FVG above price
                    dist = fvg["bottom"] - current_price
                    if dist < min_dist:
                        min_dist = dist
                        nearest_fvg = fvg
            
            if nearest_fvg:
                dist_atr = round(min_dist / atr, 2)
                return {
                    "fvg": {
                        "type": nearest_fvg["type"],
                        "dist_to_fill_atr": dist_atr
                    }
                }
            else:
                return {"fvg": {"type": "none", "dist_to_fill_atr": 0.0}}
                
        except Exception as e:
            logger.debug(f"FVG calculation failed: {e}")
            return {"fvg": {"type": "none", "dist_to_fill_atr": 0.0}}
    
    # === ANCHOR: VWAP_DEVIATION ===
    def _compute_vwap_deviation(self, df: pd.DataFrame, current_price: float, data: Dict) -> Dict[str, Any]:
        """
        VWAP Deviation Zones - institutional mean reversion.
        ATR-normalized distance from VWAP with zone labels.
        """
        try:
            # Calculate VWAP
            typical_price = (df['high'] + df['low'] + df['close']) / 3
            vwap = (typical_price * df['volume']).sum() / df['volume'].sum() if df['volume'].sum() > 0 else typical_price.mean()
            
            # Get ATR
            atr = self._calculate_atr(df, 14)
            if atr == 0:
                atr = 1.0
            
            # Calculate deviation
            dev_atr = (current_price - vwap) / atr
            
            # Determine zone
            abs_dev = abs(dev_atr)
            if abs_dev <= 0.5:
                zone = "inside"
            elif abs_dev <= 1.5:
                zone = "mid"
            else:
                zone = "outer"
            
            return {
                "vwap": {
                    "dev_atr": round(dev_atr, 2),
                    "zone": zone
                }
            }
        except Exception as e:
            logger.debug(f"VWAP deviation calculation failed: {e}")
            return {"vwap": {"dev_atr": 0.0, "zone": "inside"}}
    
    # === ANCHOR: MOMENTUM_ACCEL ===
    def _compute_momentum_accel(self, df: pd.DataFrame, data: Dict) -> Dict[str, Any]:
        """
        Momentum Acceleration - MACD/RSI velocity.
        Detects if momentum is strengthening or fading.
        """
        try:
            # Calculate MACD histogram slope
            macd_hist = data.get('macd_histogram', [])
            if isinstance(macd_hist, list) and len(macd_hist) >= 2:
                macd_slope = macd_hist[-1] - macd_hist[-2]
            else:
                macd_slope = 0.0
            
            # Calculate RSI slope
            rsi_values = []
            for i in range(-3, 0):
                if abs(i) <= len(df):
                    rsi = self._calculate_rsi(df.iloc[:len(df)+i], 14)
                    rsi_values.append(rsi)
            
            if len(rsi_values) >= 2:
                rsi_slope = rsi_values[-1] - rsi_values[-2]
            else:
                rsi_slope = 0.0
            
            return {
                "accel": {
                    "macd_slope": round(macd_slope, 3),
                    "rsi_slope": round(rsi_slope, 2)
                }
            }
        except Exception as e:
            logger.debug(f"Momentum acceleration calculation failed: {e}")
            return {"accel": {"macd_slope": 0.0, "rsi_slope": 0.0}}
    
    # === ANCHOR: MTF_ALIGNMENT ===
    def _compute_mtf_alignment(self, features: Dict[str, Any], multi: Dict) -> Dict[str, Any]:
        """
        Multi-Timeframe Alignment Score - confluence rating.
        +1 if price > EMA200 & MACD > 0 & ADX > 25 on a TF.
        """
        try:
            timeframes = ["M5", "M15", "H1"]
            scores = {}
            total_score = 0
            
            for tf in timeframes:
                if tf not in multi or tf not in features:
                    scores[tf.lower()] = 0
                    continue
                
                data = multi[tf]
                score = 0
                
                # Get current close
                closes = data.get('closes', [])
                if not closes:
                    scores[tf.lower()] = 0
                    continue
                current_close = closes[-1]
                
                # Check EMA200
                df_temp = self._data_to_dataframe(data)
                if df_temp is not None and len(df_temp) >= 200:
                    ema200 = df_temp['close'].ewm(span=200, adjust=False).mean().iloc[-1]
                    if current_close > ema200:
                        score += 1
                
                # Check MACD
                macd_hist = data.get('macd_histogram', [])
                if isinstance(macd_hist, list) and len(macd_hist) > 0:
                    if macd_hist[-1] > 0:
                        score += 1
                elif isinstance(macd_hist, (int, float)) and macd_hist > 0:
                    score += 1
                
                # Check ADX
                adx = data.get('adx', 0.0)
                if isinstance(adx, list) and len(adx) > 0:
                    adx = adx[-1]
                if adx > 25:
                    score += 1
                
                # Normalize to 0 or 1 (require at least 2/3 conditions)
                scores[tf.lower()] = 1 if score >= 2 else 0
                total_score += scores[tf.lower()]
            
            max_score = len(timeframes)
            
            return {
                **scores,
                "total": total_score,
                "max": max_score
            }
        except Exception as e:
            logger.debug(f"MTF alignment calculation failed: {e}")
            return {"m5": 0, "m15": 0, "h1": 0, "total": 0, "max": 3}
    
    # === ANCHOR: VOLUME_PROFILE ===
    def _compute_volume_profile(self, df: pd.DataFrame, current_price: float) -> Dict[str, Any]:
        """
        Volume Profile HVN/LVN - magnet/vacuum zones.
        Coarse histogram over recent N bars to find high/low volume nodes.
        """
        try:
            if len(df) < 100:
                return {"hvn_dist_atr": 0.0, "lvn_dist_atr": 0.0}
            
            atr = self._calculate_atr(df, 14)
            if atr == 0:
                atr = 1.0
            
            # Use last 200 bars for volume profile
            recent = df.iloc[-200:]
            
            # Create price bins (20 bins)
            price_min = recent['low'].min()
            price_max = recent['high'].max()
            num_bins = 20
            bin_size = (price_max - price_min) / num_bins
            
            # Calculate volume per price level
            bins = []
            for i in range(num_bins):
                bin_low = price_min + i * bin_size
                bin_high = bin_low + bin_size
                bin_mid = (bin_low + bin_high) / 2
                
                # Sum volume where price was in this bin
                mask = (recent['low'] <= bin_high) & (recent['high'] >= bin_low)
                bin_volume = recent.loc[mask, 'volume'].sum()
                
                bins.append({"price": bin_mid, "volume": bin_volume})
            
            # Sort by volume to find HVN and LVN
            sorted_bins = sorted(bins, key=lambda x: x['volume'], reverse=True)
            
            # Top 2 HVNs (High Volume Nodes)
            hvns = [sorted_bins[0]['price'], sorted_bins[1]['price']] if len(sorted_bins) >= 2 else [sorted_bins[0]['price']]
            
            # Bottom LVN (Low Volume Node)
            lvn = sorted_bins[-1]['price'] if len(sorted_bins) > 0 else current_price
            
            # Find nearest HVN
            hvn_dists = [abs(hvn - current_price) for hvn in hvns]
            nearest_hvn_dist = min(hvn_dists) if hvn_dists else 0.0
            
            # LVN distance
            lvn_dist = abs(lvn - current_price)
            
            return {
                "hvn_dist_atr": round(nearest_hvn_dist / atr, 2),
                "lvn_dist_atr": round(lvn_dist / atr, 2)
            }
        except Exception as e:
            logger.debug(f"Volume profile calculation failed: {e}")
            return {"hvn_dist_atr": 0.0, "lvn_dist_atr": 0.0}
    
    # === ANCHOR: BUILD_FEATURES ===
    # (Main build_features method already defined above in CLASS_INIT section)
    
    # === ANCHOR: COMPACT_FORMAT ===
    def _compact_format(self, features: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """
        Format features in compact form for GPT consumption.
        Keeps only the most important features and rounds values.
        """
        try:
            compact = {
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "features": features
            }
            return compact
        except Exception as e:
            logger.error(f"Compact formatting failed: {e}")
            return {"symbol": symbol, "features": {}}
    
    # === Helper Methods ===
    
    def _data_to_dataframe(self, data: Dict) -> Optional[pd.DataFrame]:
        """Convert indicator bridge data to DataFrame."""
        try:
            if not data:
                return None
                
            # Use the keys from indicator_bridge format
            opens = data.get('opens', [])
            highs = data.get('highs', [])
            lows = data.get('lows', [])
            closes = data.get('closes', [])
            volumes = data.get('volumes', [])
            times = data.get('times', [])
            
            if not closes:
                return None
            
            df = pd.DataFrame({
                'open': opens,
                'high': highs,
                'low': lows,
                'close': closes,
                'volume': volumes
            })
            
            # Add time index if available
            if times:
                try:
                    # Handle different time formats: Unix timestamps (int/float) or ISO strings
                    if times and len(times) > 0:
                        first_time = times[0]
                        if isinstance(first_time, (int, float)):
                            # Unix timestamp - check if seconds or milliseconds
                            if first_time > 1e10:  # Likely milliseconds
                                df.index = pd.to_datetime(times, unit='ms', errors='coerce')
                            else:  # Likely seconds
                                df.index = pd.to_datetime(times, unit='s', errors='coerce')
                        else:
                            # String or datetime - use errors='coerce' to suppress warnings and handle parsing errors
                            df.index = pd.to_datetime(times, errors='coerce')
                except:
                    pass
            
            return df
        except Exception as e:
            logger.debug(f"DataFrame conversion failed: {e}")
            return None
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range."""
        try:
            high = df['high']
            low = df['low']
            close = df['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean().iloc[-1]
            
            return float(atr) if not pd.isna(atr) else 0.0
        except Exception as e:
            logger.debug(f"ATR calculation failed: {e}")
            return 0.0
    
    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        try:
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
        except Exception as e:
            logger.debug(f"RSI calculation failed: {e}")
            return 50.0
    
    def _find_equal_levels(self, levels: List[float], tolerance: float = 0.001) -> bool:
        """Check if there are equal levels within tolerance."""
        if len(levels) < 2:
            return False
        
        for i in range(len(levels)):
            for j in range(i + 1, len(levels)):
                if abs(levels[i] - levels[j]) / levels[i] <= tolerance:
                    return True
        return False
    
    def _empty_features(self) -> Dict[str, Any]:
        """Return empty feature structure."""
        return {
            "symbol": "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "features": {}
        }


# === Module-level convenience function ===
def build_features_advanced(symbol: str, mt5svc: MT5Service, bridge: IndicatorBridge,
                     timeframes: List[str] = None) -> Dict[str, Any]:
    """
    Convenience function to build advanced features for a symbol.

    Example usage:
        features = build_features_advanced("XAUUSDc", mt5_service, indicator_bridge)
        print(features["features"]["M15"]["rmag"])
    """
    try:
        builder = FeatureBuilderAdvanced(mt5svc, bridge)
        return builder.build_features(symbol, timeframes)
    except Exception as e:
        logger.error(f"Feature building failed for {symbol}: {e}", exc_info=True)
        return FeatureBuilderAdvanced(mt5svc, bridge)._empty_features()

