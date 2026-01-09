"""
Feature Structure Module
Computes swing highs/lows, S/R pivots, ranges, and market structure
IMPROVED: Phase 4.1 - Integrated liquidity, BOS/CHOCH, FVG, and wick asymmetry detectors
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple
import logging

# IMPROVED: Import Phase 4.1 detectors
from domain.liquidity import detect_equal_highs, detect_equal_lows, detect_sweep, detect_stop_clusters, validate_sweep
from domain.market_structure import detect_bos_choch
from domain.fvg import detect_fvg
from domain.candle_stats import calculate_wick_asymmetry
from domain.volume_footprint import calculate_rolling_volume_footprint

logger = logging.getLogger(__name__)

class StructureFeatures:
    """
    IMPROVED: Computes market structure features including swing points, S/R levels, and ranges.
    Focuses on clean, normalized structural analysis.
    """
    
    def compute(self, df: pd.DataFrame, symbol: str, timeframe: str) -> Dict[str, Any]:
        """
        Compute all structure features for the given DataFrame.
        IMPROVED: Phase 4.1 - Added liquidity, BOS/CHOCH, enhanced FVG, and wick asymmetry.
        """
        try:
            features = {}
            
            # Swing analysis
            features.update(self._compute_swing_analysis(df))
            
            # Support/Resistance levels
            features.update(self._compute_support_resistance(df))
            
            # Range analysis
            features.update(self._compute_range_analysis(df))
            
            # Pivot points
            features.update(self._compute_pivot_points(df))
            
            # IMPROVED: Phase 4.1 - Enhanced structure detectors
            atr_14 = self._calculate_atr(df.tail(14)) if len(df) >= 14 else 0.0
            
            # Equal Highs/Lows (liquidity clusters)
            features.update(self._compute_liquidity_clusters(df, atr_14))
            
            # Phase 3.1 - Rolling Volume Footprint
            features.update(self._compute_volume_footprint(df))
            
            # Sweeps (liquidity grabs)
            features.update(self._compute_sweeps(df, atr_14))
            
            # BOS/CHOCH (market structure breaks)
            features.update(self._compute_bos_choch(df, atr_14))
            
            # Fair Value Gaps (enhanced with Phase 4.1 detector)
            features.update(self._compute_fair_value_gaps_enhanced(df, atr_14))
            
            # Wick Asymmetry (rejection bars)
            features.update(self._compute_wick_asymmetry(df))
            
            return features
            
        except Exception as e:
            logger.error(f"Structure computation failed for {symbol} {timeframe}: {e}")
            return {}
    
    def _compute_swing_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute swing highs and lows."""
        try:
            features = {}
            
            if len(df) < 5:
                return {"swing_highs": [], "swing_lows": [], "swing_count": 0}
            
            # Find swing points using fractal method
            swing_highs, swing_lows = self._find_swing_points(df, lookback=2)
            
            # Get recent swing points (last 10)
            recent_highs = swing_highs[-10:] if len(swing_highs) > 10 else swing_highs
            recent_lows = swing_lows[-10:] if len(swing_lows) > 10 else swing_lows
            
            features["swing_highs"] = [{"price": float(high), "index": int(idx)} for high, idx in recent_highs]
            features["swing_lows"] = [{"price": float(low), "index": int(idx)} for low, idx in recent_lows]
            features["swing_count"] = len(recent_highs) + len(recent_lows)
            
            # Swing analysis
            if len(recent_highs) >= 2 and len(recent_lows) >= 2:
                features["swing_trend"] = self._analyze_swing_trend(recent_highs, recent_lows)
                features["swing_strength"] = self._calculate_swing_strength(recent_highs, recent_lows)
            else:
                features["swing_trend"] = "neutral"
                features["swing_strength"] = 0.0
            
            return features
            
        except Exception as e:
            logger.error(f"Swing analysis computation failed: {e}")
            return {"swing_highs": [], "swing_lows": [], "swing_count": 0}
    
    def _compute_support_resistance(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute support and resistance levels."""
        try:
            features = {}
            
            if len(df) < 20:
                return {"support_levels": [], "resistance_levels": [], "level_count": 0}
            
            # Find S/R levels using pivot method
            swing_highs, swing_lows = self._find_swing_points(df, lookback=3)
            
            # Cluster similar levels
            resistance_levels = self._cluster_levels([high for high, _ in swing_highs])
            support_levels = self._cluster_levels([low for low, _ in swing_lows])
            
            # Filter levels by strength (number of touches)
            strong_resistance = [level for level in resistance_levels if level["touches"] >= 2]
            strong_support = [level for level in support_levels if level["touches"] >= 2]
            
            features["resistance_levels"] = [float(level["price"]) for level in strong_resistance]
            features["support_levels"] = [float(level["price"]) for level in strong_support]
            features["level_count"] = len(strong_resistance) + len(strong_support)
            
            # Level proximity to current price
            current_price = df["close"].iloc[-1]
            features["nearest_resistance"] = self._find_nearest_level(current_price, features["resistance_levels"])
            features["nearest_support"] = self._find_nearest_level(current_price, features["support_levels"])
            
            # Level strength analysis
            features["level_strength"] = self._calculate_level_strength(strong_resistance, strong_support)
            
            return features
            
        except Exception as e:
            logger.error(f"Support/Resistance computation failed: {e}")
            return {"support_levels": [], "resistance_levels": [], "level_count": 0}
    
    def _compute_range_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute range analysis."""
        try:
            features = {}
            
            if len(df) < 20:
                return {"range_high": 0.0, "range_low": 0.0, "range_width": 0.0, "range_position": 0.5}
            
            # Calculate range over different periods
            range_20 = self._calculate_range(df.tail(20))
            range_50 = self._calculate_range(df.tail(min(50, len(df))))
            
            features["range_high"] = float(range_20["high"])
            features["range_low"] = float(range_20["low"])
            features["range_width"] = float(range_20["width"])
            features["range_position"] = float(range_20["position"])
            
            # Range expansion/contraction
            features["range_expansion"] = range_20["width"] > range_50["width"] if len(df) >= 50 else False
            
            # Range breakout potential
            current_price = df["close"].iloc[-1]
            features["near_range_high"] = abs(current_price - range_20["high"]) / range_20["width"] < 0.1
            features["near_range_low"] = abs(current_price - range_20["low"]) / range_20["width"] < 0.1
            
            # Range volatility
            if len(df) >= 14:
                atr_14 = self._calculate_atr(df.tail(14))
                features["range_atr_ratio"] = range_20["width"] / atr_14 if atr_14 > 0 else 0.0
            else:
                features["range_atr_ratio"] = 0.0
            
            return features
            
        except Exception as e:
            logger.error(f"Range analysis computation failed: {e}")
            return {"range_high": 0.0, "range_low": 0.0, "range_width": 0.0, "range_position": 0.5}
    
    def _compute_pivot_points(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute classic pivot points."""
        try:
            features = {}
            
            if len(df) < 1:
                return {"pivot_point": 0.0, "r1": 0.0, "r2": 0.0, "s1": 0.0, "s2": 0.0}
            
            # Use previous day's OHLC for pivot calculation
            prev_high = df["high"].iloc[-1]
            prev_low = df["low"].iloc[-1]
            prev_close = df["close"].iloc[-1]
            
            # Calculate pivot points
            pivot = (prev_high + prev_low + prev_close) / 3
            r1 = 2 * pivot - prev_low
            r2 = pivot + (prev_high - prev_low)
            s1 = 2 * pivot - prev_high
            s2 = pivot - (prev_high - prev_low)
            
            features["pivot_point"] = float(pivot)
            features["r1"] = float(r1)
            features["r2"] = float(r2)
            features["s1"] = float(s1)
            features["s2"] = float(s2)
            
            # Pivot level distances (normalized by ATR)
            current_price = df["close"].iloc[-1]
            if len(df) >= 14:
                atr_14 = self._calculate_atr(df.tail(14))
                if atr_14 > 0:
                    features["pivot_distance"] = (current_price - pivot) / atr_14
                    features["r1_distance"] = (current_price - r1) / atr_14
                    features["s1_distance"] = (current_price - s1) / atr_14
                else:
                    features["pivot_distance"] = 0.0
                    features["r1_distance"] = 0.0
                    features["s1_distance"] = 0.0
            else:
                features["pivot_distance"] = 0.0
                features["r1_distance"] = 0.0
                features["s1_distance"] = 0.0
            
            return features
            
        except Exception as e:
            logger.error(f"Pivot points computation failed: {e}")
            return {"pivot_point": 0.0, "r1": 0.0, "r2": 0.0, "s1": 0.0, "s2": 0.0}
    
    def _compute_fair_value_gaps(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute Fair Value Gaps (FVG)."""
        try:
            features = {}
            
            if len(df) < 3:
                return {"fvg_count": 0, "fvg_bullish": 0, "fvg_bearish": 0, "fvg_distance": 0.0}
            
            # Find FVGs in last 20 bars
            fvgs = self._find_fair_value_gaps(df.tail(20))
            
            features["fvg_count"] = len(fvgs)
            features["fvg_bullish"] = sum(1 for fvg in fvgs if fvg["type"] == "bullish")
            features["fvg_bearish"] = sum(1 for fvg in fvgs if fvg["type"] == "bearish")
            
            # Distance to nearest FVG
            current_price = df["close"].iloc[-1]
            if fvgs:
                distances = [abs(current_price - fvg["price"]) for fvg in fvgs]
                features["fvg_distance"] = float(min(distances))
            else:
                features["fvg_distance"] = 0.0
            
            return features
            
        except Exception as e:
            logger.error(f"Fair Value Gap computation failed: {e}")
            return {"fvg_count": 0, "fvg_bullish": 0, "fvg_bearish": 0, "fvg_distance": 0.0}
    
    # Helper methods
    
    def _find_swing_points(self, df: pd.DataFrame, lookback: int = 2) -> Tuple[List[Tuple[float, int]], List[Tuple[float, int]]]:
        """Find swing highs and lows using fractal method."""
        swing_highs = []
        swing_lows = []
        
        for i in range(lookback, len(df) - lookback):
            # Check for swing high
            is_swing_high = True
            for j in range(i - lookback, i + lookback + 1):
                if j != i and df["high"].iloc[j] >= df["high"].iloc[i]:
                    is_swing_high = False
                    break
            
            if is_swing_high:
                swing_highs.append((df["high"].iloc[i], i))
            
            # Check for swing low
            is_swing_low = True
            for j in range(i - lookback, i + lookback + 1):
                if j != i and df["low"].iloc[j] <= df["low"].iloc[i]:
                    is_swing_low = False
                    break
            
            if is_swing_low:
                swing_lows.append((df["low"].iloc[i], i))
        
        return swing_highs, swing_lows
    
    def _cluster_levels(self, levels: List[float], tolerance: float = 0.001) -> List[Dict[str, Any]]:
        """Cluster similar price levels together."""
        if not levels:
            return []
        
        levels = sorted(levels)
        clusters = []
        current_cluster = [levels[0]]
        
        for i in range(1, len(levels)):
            if abs(levels[i] - levels[i-1]) / levels[i-1] <= tolerance:
                current_cluster.append(levels[i])
            else:
                if len(current_cluster) > 0:
                    clusters.append({
                        "price": np.mean(current_cluster),
                        "touches": len(current_cluster),
                        "levels": current_cluster
                    })
                current_cluster = [levels[i]]
        
        if len(current_cluster) > 0:
            clusters.append({
                "price": np.mean(current_cluster),
                "touches": len(current_cluster),
                "levels": current_cluster
            })
        
        return clusters
    
    def _find_nearest_level(self, price: float, levels: List[float]) -> float:
        """Find nearest level to current price."""
        if not levels:
            return 0.0
        
        distances = [abs(price - level) for level in levels]
        nearest_idx = distances.index(min(distances))
        return levels[nearest_idx]
    
    def _calculate_level_strength(self, resistance_levels: List[Dict], support_levels: List[Dict]) -> float:
        """Calculate overall level strength."""
        total_touches = sum(level["touches"] for level in resistance_levels + support_levels)
        total_levels = len(resistance_levels) + len(support_levels)
        
        if total_levels == 0:
            return 0.0
        
        return total_touches / total_levels
    
    def _analyze_swing_trend(self, swing_highs: List[Tuple[float, int]], swing_lows: List[Tuple[float, int]]) -> str:
        """Analyze swing trend direction."""
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return "neutral"
        
        # Check if highs are making higher highs
        recent_highs = [high for high, _ in swing_highs[-2:]]
        higher_highs = recent_highs[-1] > recent_highs[-2] if len(recent_highs) >= 2 else False
        
        # Check if lows are making higher lows
        recent_lows = [low for low, _ in swing_lows[-2:]]
        higher_lows = recent_lows[-1] > recent_lows[-2] if len(recent_lows) >= 2 else False
        
        if higher_highs and higher_lows:
            return "up"
        elif not higher_highs and not higher_lows:
            return "down"
        else:
            return "mixed"
    
    def _calculate_swing_strength(self, swing_highs: List[Tuple[float, int]], swing_lows: List[Tuple[float, int]]) -> float:
        """Calculate swing strength based on price movement."""
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return 0.0
        
        # Calculate average swing size
        high_moves = [swing_highs[i][0] - swing_highs[i-1][0] for i in range(1, len(swing_highs))]
        low_moves = [swing_lows[i][0] - swing_lows[i-1][0] for i in range(1, len(swing_lows))]
        
        avg_high_move = np.mean(high_moves) if high_moves else 0.0
        avg_low_move = np.mean(low_moves) if low_moves else 0.0
        
        # Normalize by average price
        avg_price = np.mean([high for high, _ in swing_highs] + [low for low, _ in swing_lows])
        if avg_price == 0:
            return 0.0
        
        strength = (abs(avg_high_move) + abs(avg_low_move)) / (2 * avg_price)
        return min(strength, 1.0)  # Cap at 1.0
    
    def _calculate_range(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate range metrics for a DataFrame."""
        high = df["high"].max()
        low = df["low"].min()
        width = high - low
        current_price = df["close"].iloc[-1]
        position = (current_price - low) / width if width > 0 else 0.5
        
        return {
            "high": high,
            "low": low,
            "width": width,
            "position": position
        }
    
    def _calculate_atr(self, df: pd.DataFrame) -> float:
        """Calculate Average True Range for a DataFrame."""
        try:
            if len(df) < 2:
                return 0.0
            
            high_low = df["high"] - df["low"]
            high_close = np.abs(df["high"] - df["close"].shift())
            low_close = np.abs(df["low"] - df["close"].shift())
            true_range = np.maximum(high_low, np.maximum(high_close, low_close))
            return float(true_range.mean())
            
        except Exception:
            return 0.0
    
    def _find_fair_value_gaps(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Find Fair Value Gaps in the data."""
        fvgs = []
        
        for i in range(1, len(df) - 1):
            prev = df.iloc[i-1]
            current = df.iloc[i]
            next_candle = df.iloc[i+1]
            
            # Bullish FVG: gap between high of first candle and low of third candle
            if (prev["high"] < next_candle["low"] and 
                current["low"] > prev["high"] and 
                current["high"] < next_candle["low"]):
                fvgs.append({
                    "type": "bullish",
                    "price": (prev["high"] + next_candle["low"]) / 2,
                    "index": i
                })
            
            # Bearish FVG: gap between low of first candle and high of third candle
            elif (prev["low"] > next_candle["high"] and 
                  current["high"] < prev["low"] and 
                  current["low"] > next_candle["high"]):
                fvgs.append({
                    "type": "bearish",
                    "price": (prev["low"] + next_candle["high"]) / 2,
                    "index": i
                })
        
        return fvgs
    
    # IMPROVED: Phase 4.1 - Market Structure Toolkit Integration
    
    def _compute_liquidity_clusters(self, df: pd.DataFrame, atr: float) -> Dict[str, Any]:
        """
        Compute equal highs/lows (liquidity clusters) using Phase 4.1 detector.
        These identify resting liquidity zones where stops are likely parked.
        """
        try:
            if len(df) < 20 or atr <= 0:
                return {
                    "eq_high_cluster": False,
                    "eq_high_price": 0.0,
                    "eq_high_count": 0,
                    "eq_low_cluster": False,
                    "eq_low_price": 0.0,
                    "eq_low_count": 0,
                    "stop_cluster_above": False,
                    "stop_cluster_above_price": 0.0,
                    "stop_cluster_above_count": 0,
                    "stop_cluster_above_dist_atr": 999.0,
                    "stop_cluster_below": False,
                    "stop_cluster_below_price": 0.0,
                    "stop_cluster_below_count": 0,
                    "stop_cluster_below_dist_atr": 999.0
                }
            
            # Extract arrays for detector
            highs = df["high"].values
            lows = df["low"].values
            times = df.index.values if hasattr(df.index, 'values') else np.arange(len(df))
            
            # Detect equal highs
            eq_highs = detect_equal_highs(
                highs, lows, times, atr,
                lookback=min(50, len(df)),
                tolerance_mult=0.1,
                min_touches=2
            )
            
            # Detect equal lows
            eq_lows = detect_equal_lows(
                lows, highs, times, atr,
                lookback=min(50, len(df)),
                tolerance_mult=0.1,
                min_touches=2
            )
            
            # Detect stop clusters (wick-based)
            stop_clusters = detect_stop_clusters(
                df, atr,
                lookback=min(50, len(df)),
                min_wick_atr=0.5,
                cluster_tolerance_atr=0.15,
                min_wicks=3
            )
            
            result = {
                "eq_high_cluster": eq_highs["eq_high_cluster"],
                "eq_high_price": float(eq_highs["cluster_price"]),
                "eq_high_count": eq_highs["cluster_count"],
                "eq_high_bars_ago": eq_highs["bars_ago"],
                "eq_low_cluster": eq_lows["eq_low_cluster"],
                "eq_low_price": float(eq_lows["cluster_price"]),
                "eq_low_count": eq_lows["cluster_count"],
                "eq_low_bars_ago": eq_lows["bars_ago"]
            }
            
            # Add stop cluster data
            result.update(stop_clusters)
            
            # Phase 3.1 - Add volume footprint data to liquidity dict
            footprint_data = self._compute_volume_footprint(df)
            if footprint_data.get("footprint_active", False):
                result["footprint"] = {
                    "footprint_active": True,
                    "poc": footprint_data.get("poc", 0.0),
                    "value_area_high": footprint_data.get("value_area_high", 0.0),
                    "value_area_low": footprint_data.get("value_area_low", 0.0),
                    "current_price_volume_rank": footprint_data.get("current_price_volume_rank", 50),
                    "current_price_volume_pct": footprint_data.get("current_price_volume_pct", 0.0),
                }
            else:
                result["footprint"] = {"footprint_active": False}
            
            return result
            
        except Exception as e:
            logger.debug(f"Liquidity cluster computation failed: {e}")
            return {
                "eq_high_cluster": False,
                "eq_high_price": 0.0,
                "eq_high_count": 0,
                "eq_low_cluster": False,
                "eq_low_price": 0.0,
                "eq_low_count": 0,
                "stop_cluster_above": False,
                "stop_cluster_above_price": 0.0,
                "stop_cluster_above_count": 0,
                "stop_cluster_above_dist_atr": 999.0,
                "stop_cluster_below": False,
                "stop_cluster_below_price": 0.0,
                "stop_cluster_below_count": 0,
                "stop_cluster_below_dist_atr": 999.0
            }
    
    def _compute_volume_footprint(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Phase 3.1: Compute rolling volume footprint.
        
        Creates cumulative volume profile over rolling time window, identifying:
        - POC (Point of Control) - price with highest volume
        - Value Area (70% volume range)
        - HVN/LVN zones (high/low volume nodes)
        - Current price volume rank
        """
        try:
            # Use window of 100 bars for footprint (configurable)
            window_bars = min(100, len(df))
            
            if window_bars < 50:
                return {
                    "footprint_active": False,
                    "poc": 0.0,
                    "value_area_high": 0.0,
                    "value_area_low": 0.0,
                    "current_price_volume_rank": 50,
                    "current_price_volume_pct": 0.0,
                }
            
            # Ensure DataFrame has required columns with correct names
            required_cols = ['open', 'high', 'low', 'close']
            if not all(col in df.columns for col in required_cols):
                return {
                    "footprint_active": False,
                    "poc": 0.0,
                    "value_area_high": 0.0,
                    "value_area_low": 0.0,
                    "current_price_volume_rank": 50,
                    "current_price_volume_pct": 0.0,
                }
            
            # Ensure volume column exists (handle tick_volume, volume, or create dummy)
            if 'volume' not in df.columns:
                if 'tick_volume' in df.columns:
                    df = df.copy()
                    df['volume'] = df['tick_volume']
                else:
                    # No volume data available
                    return {
                        "footprint_active": False,
                        "poc": 0.0,
                        "value_area_high": 0.0,
                        "value_area_low": 0.0,
                        "current_price_volume_rank": 50,
                        "current_price_volume_pct": 0.0,
                    }
            
            # Ensure time index for DataFrame
            if not hasattr(df.index, 'dtype') or 'datetime' not in str(df.index.dtype):
                # Create a time index if missing
                df = df.copy()
                df['time'] = pd.date_range(start='2024-01-01', periods=len(df), freq='5min')
                df = df.set_index('time')
            
            # Calculate footprint
            footprint = calculate_rolling_volume_footprint(
                df,
                window_bars=window_bars,
                price_precision=4,  # Adjust based on symbol (4 for most forex/crypto)
                min_volume_threshold=0.01
            )
            
            if not footprint.get("footprint_active", False):
                return {
                    "footprint_active": False,
                    "poc": 0.0,
                    "value_area_high": 0.0,
                    "value_area_low": 0.0,
                    "current_price_volume_rank": 50,
                    "current_price_volume_pct": 0.0,
                }
            
            # Extract key metrics
            return {
                "footprint_active": True,
                "poc": footprint.get("poc", 0.0),
                "value_area_high": footprint.get("value_area_high", 0.0),
                "value_area_low": footprint.get("value_area_low", 0.0),
                "current_price_volume_rank": footprint.get("current_price_volume_rank", 50),
                "current_price_volume_pct": footprint.get("current_price_volume_pct", 0.0),
                "hvn_count": len(footprint.get("hvn_zones", [])),
                "lvn_count": len(footprint.get("lvn_zones", [])),
            }
            
        except Exception as e:
            logger.debug(f"Volume footprint calculation failed: {e}")
            return {
                "footprint_active": False,
                "poc": 0.0,
                "value_area_high": 0.0,
                "value_area_low": 0.0,
                "current_price_volume_rank": 50,
                "current_price_volume_pct": 0.0,
            }
    
    def _compute_sweeps(self, df: pd.DataFrame, atr: float) -> Dict[str, Any]:
        """
        Phase 3.2: Enhanced sweep detection with validation.
        Computes sweep/liquidity grab detection using Phase 4.1 detector,
        then validates with Phase 3.2 validation logic (volume, follow-through, fake detection).
        """
        try:
            if len(df) < 7 or atr <= 0:
                return {
                    "sweep_bull": False,
                    "sweep_bear": False,
                    "sweep_depth": 0.0,
                    "sweep_price": 0.0,
                    "sweep_bull_validated": False,
                    "sweep_bear_validated": False,
                    "bull_confidence": 0.0,
                    "bear_confidence": 0.0,
                    "bull_fake": False,
                    "bear_fake": False
                }
            
            # Detect sweeps
            sweep = detect_sweep(df, atr, sweep_threshold=0.15, lookback=20)
            
            # Phase 3.2: Validate sweep if detected
            if sweep.get("sweep_bull") or sweep.get("sweep_bear"):
                validation = validate_sweep(df, sweep, atr, confirmation_bars=3)
                
                return {
                    "sweep_bull": sweep["sweep_bull"],
                    "sweep_bear": sweep["sweep_bear"],
                    "sweep_depth": float(sweep["depth"]),
                    "sweep_price": float(sweep["sweep_price"]),
                    "sweep_bars_ago": sweep["bars_ago"],
                    # Phase 3.2 validation fields
                    "sweep_bull_validated": validation.get("sweep_bull_validated", False),
                    "sweep_bear_validated": validation.get("sweep_bear_validated", False),
                    "bull_confidence": validation.get("bull_confidence", 0.0),
                    "bear_confidence": validation.get("bear_confidence", 0.0),
                    "bull_fake": validation.get("bull_fake", False),
                    "bear_fake": validation.get("bear_fake", False),
                    "bull_follow_through": validation.get("bull_follow_through", 0.0),
                    "bear_follow_through": validation.get("bear_follow_through", 0.0),
                    "bull_volume_ratio": validation.get("bull_volume_ratio", 1.0),
                    "bear_volume_ratio": validation.get("bear_volume_ratio", 1.0)
                }
            else:
                # No sweep detected
                return {
                    "sweep_bull": False,
                    "sweep_bear": False,
                    "sweep_depth": 0.0,
                    "sweep_price": 0.0,
                    "sweep_bars_ago": -1,
                    "sweep_bull_validated": False,
                    "sweep_bear_validated": False,
                    "bull_confidence": 0.0,
                    "bear_confidence": 0.0,
                    "bull_fake": False,
                    "bear_fake": False
                }
            
        except Exception as e:
            logger.debug(f"Sweep computation failed: {e}")
            return {
                "sweep_bull": False,
                "sweep_bear": False,
                "sweep_depth": 0.0,
                "sweep_price": 0.0,
                "sweep_bull_validated": False,
                "sweep_bear_validated": False,
                "bull_confidence": 0.0,
                "bear_confidence": 0.0,
                "bull_fake": False,
                "bear_fake": False
            }
    
    def _compute_bos_choch(self, df: pd.DataFrame, atr: float) -> Dict[str, Any]:
        """
        Compute Break of Structure (BOS) and Change of Character (CHOCH) using Phase 4.1 detector.
        BOS = trend continuation, CHOCH = potential reversal.
        """
        try:
            if len(df) < 20 or atr <= 0:
                return {
                    "bos_bull": False,
                    "bos_bear": False,
                    "choch_bull": False,
                    "choch_bear": False,
                    "structure_break_level": 0.0
                }
            
            # Get swing points for BOS/CHOCH detection
            swing_highs, swing_lows = self._find_swing_points(df, lookback=3)
            
            # Convert to format expected by detector
            swings = []
            for high, idx in swing_highs:
                swings.append({"type": "high", "price": high, "index": idx})
            for low, idx in swing_lows:
                swings.append({"type": "low", "price": low, "index": idx})
            
            # Sort by index
            swings = sorted(swings, key=lambda x: x["index"])
            
            current_close = df["close"].iloc[-1]
            
            # Detect BOS/CHOCH
            result = detect_bos_choch(swings, current_close, atr, bos_threshold=0.2, sustained_bars=1)
            
            # Determine structure type from results
            if result["choch_bull"]:
                structure_type = "choch_bull"
            elif result["choch_bear"]:
                structure_type = "choch_bear"
            elif result["bos_bull"]:
                structure_type = "bos_bull"
            elif result["bos_bear"]:
                structure_type = "bos_bear"
            else:
                structure_type = "none"
            
            return {
                "bos_bull": result["bos_bull"],
                "bos_bear": result["bos_bear"],
                "choch_bull": result["choch_bull"],
                "choch_bear": result["choch_bear"],
                "structure_break_level": float(result["break_level"]),
                "structure_type": structure_type,
                "bars_since_bos": result.get("bars_since_bos", -1)
            }
            
        except Exception as e:
            logger.debug(f"BOS/CHOCH computation failed: {e}")
            return {
                "bos_bull": False,
                "bos_bear": False,
                "choch_bull": False,
                "choch_bear": False,
                "structure_break_level": 0.0
            }
    
    def _compute_fair_value_gaps_enhanced(self, df: pd.DataFrame, atr: float) -> Dict[str, Any]:
        """
        Compute Fair Value Gaps using Phase 4.1 enhanced detector.
        Replaces the legacy FVG computation with ATR-normalized detection.
        """
        try:
            if len(df) < 12 or atr <= 0:
                return {
                    "fvg_bull": False,
                    "fvg_bear": False,
                    "fvg_zone_upper": 0.0,
                    "fvg_zone_lower": 0.0,
                    "fvg_width_atr": 0.0,
                    "fvg_bars_ago": -1
                }
            
            # Detect FVG
            fvg = detect_fvg(df, atr, min_width_mult=0.1, lookback=10)
            
            # Unpack the zone tuple (upper, lower)
            zone_upper, zone_lower = fvg["fvg_zone"]
            
            return {
                "fvg_bull": fvg["fvg_bull"],
                "fvg_bear": fvg["fvg_bear"],
                "fvg_zone_upper": float(zone_upper),
                "fvg_zone_lower": float(zone_lower),
                "fvg_width_atr": float(fvg["width_atr"]),
                "fvg_bars_ago": fvg["bars_ago"]
            }
            
        except Exception as e:
            logger.debug(f"Enhanced FVG computation failed: {e}")
            return {
                "fvg_bull": False,
                "fvg_bear": False,
                "fvg_zone_upper": 0.0,
                "fvg_zone_lower": 0.0,
                "fvg_width_atr": 0.0,
                "fvg_bars_ago": -1
            }
    
    def _compute_wick_asymmetry(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Compute wick asymmetry for recent bars using Phase 4.1 calculator.
        Identifies rejection bars (strong wicks indicating failed attempts).
        """
        try:
            if len(df) < 5:
                return {
                    "wick_asymmetry": 0.0,
                    "wick_rejection_bull": False,
                    "wick_rejection_bear": False,
                    "wick_strength": 0.0
                }
            
            # Calculate wick asymmetry for last 5 bars
            recent_bars = df.tail(5)
            asymmetries = []
            
            for i in range(len(recent_bars)):
                bar = {
                    "open": recent_bars.iloc[i]["open"],
                    "high": recent_bars.iloc[i]["high"],
                    "low": recent_bars.iloc[i]["low"],
                    "close": recent_bars.iloc[i]["close"]
                }
                asymmetry = calculate_wick_asymmetry(bar)
                asymmetries.append(asymmetry)
            
            # Use most recent bar's asymmetry
            last_asymmetry = asymmetries[-1] if asymmetries else 0.0
            
            # Average asymmetry over recent bars
            avg_asymmetry = np.mean(asymmetries) if asymmetries else 0.0
            
            # Rejection detection (strong wick with reversal)
            # Positive asymmetry = upper wick dominant (bearish rejection)
            # Negative asymmetry = lower wick dominant (bullish rejection)
            rejection_threshold = 0.4
            
            return {
                "wick_asymmetry": float(last_asymmetry),
                "wick_asymmetry_avg": float(avg_asymmetry),
                "wick_rejection_bull": bool(last_asymmetry < -rejection_threshold),  # Strong lower wick
                "wick_rejection_bear": bool(last_asymmetry > rejection_threshold),   # Strong upper wick
                "wick_strength": float(abs(last_asymmetry))
            }
            
        except Exception as e:
            logger.debug(f"Wick asymmetry computation failed: {e}")
            return {
                "wick_asymmetry": 0.0,
                "wick_rejection_bull": False,
                "wick_rejection_bear": False,
                "wick_strength": 0.0
            }
