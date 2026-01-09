"""
Feature Microstructure Module
Computes spread, slippage, tick volume, and microstructure features
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class MicrostructureFeatures:
    """
    IMPROVED: Computes microstructure features including spread, slippage, and tick volume.
    Focuses on execution quality and market microstructure analysis.
    """
    
    def compute(self, df: pd.DataFrame, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Compute all microstructure features for the given DataFrame."""
        try:
            features = {}
            
            # Spread analysis
            features.update(self._compute_spread_analysis(df, symbol))
            
            # Slippage analysis
            features.update(self._compute_slippage_analysis(df))
            
            # Tick volume analysis
            features.update(self._compute_tick_volume_analysis(df))
            
            # Gap analysis
            features.update(self._compute_gap_analysis(df))
            
            # Execution quality metrics
            features.update(self._compute_execution_quality(df))
            
            return features
            
        except Exception as e:
            logger.error(f"Microstructure computation failed for {symbol} {timeframe}: {e}")
            return {}
    
    def _compute_spread_analysis(self, df: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        """Compute spread analysis features."""
        try:
            features = {}
            
            # Get current spread from MT5 (if available)
            # For now, estimate spread from high-low range
            if len(df) < 1:
                return {"spread_points": 0.0, "spread_atr_pct": 0.0, "spread_regime": "normal"}
            
            current_bar = df.iloc[-1]
            estimated_spread = current_bar["high"] - current_bar["low"]
            
            # Convert to points (assuming 5 decimal places for most FX pairs)
            spread_points = estimated_spread * 100000
            features["spread_points"] = float(spread_points)
            
            # Calculate spread as percentage of ATR
            if len(df) >= 14:
                atr_14 = self._calculate_atr(df.tail(14))
                if atr_14 > 0:
                    spread_atr_pct = estimated_spread / atr_14
                    features["spread_atr_pct"] = float(spread_atr_pct)
                    
                    # Classify spread regime
                    if spread_atr_pct > 0.3:
                        features["spread_regime"] = "wide"
                    elif spread_atr_pct < 0.1:
                        features["spread_regime"] = "tight"
                    else:
                        features["spread_regime"] = "normal"
                else:
                    features["spread_atr_pct"] = 0.0
                    features["spread_regime"] = "normal"
            else:
                features["spread_atr_pct"] = 0.0
                features["spread_regime"] = "normal"
            
            # Spread volatility (rolling standard deviation)
            if len(df) >= 20:
                recent_spreads = []
                for i in range(max(0, len(df) - 20), len(df)):
                    bar = df.iloc[i]
                    bar_spread = bar["high"] - bar["low"]
                    recent_spreads.append(bar_spread)
                
                spread_std = np.std(recent_spreads)
                features["spread_volatility"] = float(spread_std)
            else:
                features["spread_volatility"] = 0.0
            
            return features
            
        except Exception as e:
            logger.error(f"Spread analysis computation failed: {e}")
            return {"spread_points": 0.0, "spread_atr_pct": 0.0, "spread_regime": "normal"}
    
    def _compute_slippage_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute slippage analysis features."""
        try:
            features = {}
            
            if len(df) < 2:
                return {"slippage_proxy": 0.0, "slippage_trend": "stable"}
            
            # Calculate slippage proxy as the difference between close and open
            # This gives us an idea of execution quality
            slippage_values = []
            for i in range(1, min(len(df), 20)):  # Last 20 bars
                bar = df.iloc[i]
                slippage = abs(bar["close"] - bar["open"])
                slippage_values.append(slippage)
            
            if slippage_values:
                features["slippage_proxy"] = float(np.mean(slippage_values))
                features["slippage_std"] = float(np.std(slippage_values))
                
                # Slippage trend
                if len(slippage_values) >= 5:
                    recent_slippage = np.mean(slippage_values[-5:])
                    earlier_slippage = np.mean(slippage_values[:-5])
                    
                    if recent_slippage > earlier_slippage * 1.2:
                        features["slippage_trend"] = "increasing"
                    elif recent_slippage < earlier_slippage * 0.8:
                        features["slippage_trend"] = "decreasing"
                    else:
                        features["slippage_trend"] = "stable"
                else:
                    features["slippage_trend"] = "stable"
            else:
                features["slippage_proxy"] = 0.0
                features["slippage_std"] = 0.0
                features["slippage_trend"] = "stable"
            
            return features
            
        except Exception as e:
            logger.error(f"Slippage analysis computation failed: {e}")
            return {"slippage_proxy": 0.0, "slippage_trend": "stable"}
    
    def _compute_tick_volume_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute tick volume analysis features."""
        try:
            features = {}
            
            if "volume" not in df.columns or df["volume"].sum() == 0:
                # Estimate tick volume from price movement
                features.update(self._estimate_tick_volume(df))
                return features
            
            # Real volume analysis
            volume_series = df["volume"]
            
            # Volume statistics
            features["volume_mean"] = float(volume_series.mean())
            features["volume_std"] = float(volume_series.std())
            features["volume_current"] = float(volume_series.iloc[-1])
            
            # Volume Z-score
            if len(volume_series) >= 20:
                volume_20_mean = volume_series.tail(20).mean()
                volume_20_std = volume_series.tail(20).std()
                if volume_20_std > 0:
                    features["volume_zscore"] = float((volume_series.iloc[-1] - volume_20_mean) / volume_20_std)
                else:
                    features["volume_zscore"] = 0.0
            else:
                features["volume_zscore"] = 0.0
            
            # Volume spikes
            features["volume_spike"] = abs(features["volume_zscore"]) > 2.0
            
            # Volume trend
            if len(volume_series) >= 10:
                recent_volume = volume_series.tail(5).mean()
                earlier_volume = volume_series.tail(10).head(5).mean()
                
                if recent_volume > earlier_volume * 1.2:
                    features["volume_trend"] = "increasing"
                elif recent_volume < earlier_volume * 0.8:
                    features["volume_trend"] = "decreasing"
                else:
                    features["volume_trend"] = "stable"
            else:
                features["volume_trend"] = "stable"
            
            # Volume-price relationship
            features["volume_price_correlation"] = self._calculate_volume_price_correlation(df)
            
            return features
            
        except Exception as e:
            logger.error(f"Tick volume analysis computation failed: {e}")
            return self._estimate_tick_volume(df)
    
    def _estimate_tick_volume(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Estimate tick volume from price movement when real volume is not available."""
        try:
            features = {}
            
            if len(df) < 2:
                return {"volume_zscore": 0.0, "volume_spike": False, "volume_trend": "stable"}
            
            # Estimate volume from price range and movement
            estimated_volume = []
            for i in range(1, len(df)):
                bar = df.iloc[i]
                prev_bar = df.iloc[i-1]
                
                # Volume proxy based on price movement and range
                price_change = abs(bar["close"] - prev_bar["close"])
                bar_range = bar["high"] - bar["low"]
                volume_proxy = price_change + bar_range
                estimated_volume.append(volume_proxy)
            
            if estimated_volume:
                volume_series = pd.Series(estimated_volume)
                features["volume_mean"] = float(volume_series.mean())
                features["volume_std"] = float(volume_series.std())
                features["volume_current"] = float(volume_series.iloc[-1])
                
                # Z-score calculation
                if len(volume_series) >= 20:
                    volume_20_mean = volume_series.tail(20).mean()
                    volume_20_std = volume_series.tail(20).std()
                    if volume_20_std > 0:
                        features["volume_zscore"] = float((volume_series.iloc[-1] - volume_20_mean) / volume_20_std)
                    else:
                        features["volume_zscore"] = 0.0
                else:
                    features["volume_zscore"] = 0.0
                
                features["volume_spike"] = abs(features["volume_zscore"]) > 2.0
                
                # Volume trend
                if len(volume_series) >= 10:
                    recent_volume = volume_series.tail(5).mean()
                    earlier_volume = volume_series.tail(10).head(5).mean()
                    
                    if recent_volume > earlier_volume * 1.2:
                        features["volume_trend"] = "increasing"
                    elif recent_volume < earlier_volume * 0.8:
                        features["volume_trend"] = "decreasing"
                    else:
                        features["volume_trend"] = "stable"
                else:
                    features["volume_trend"] = "stable"
            else:
                features["volume_zscore"] = 0.0
                features["volume_spike"] = False
                features["volume_trend"] = "stable"
            
            return features
            
        except Exception as e:
            logger.error(f"Tick volume estimation failed: {e}")
            return {"volume_zscore": 0.0, "volume_spike": False, "volume_trend": "stable"}
    
    def _compute_gap_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute gap analysis features."""
        try:
            features = {}
            
            if len(df) < 2:
                return {"gap_count": 0, "gap_size": 0.0, "gap_direction": "none"}
            
            # Find gaps in the data
            gaps = []
            for i in range(1, min(len(df), 50)):  # Check last 50 bars
                current_bar = df.iloc[i]
                previous_bar = df.iloc[i-1]
                
                # Gap up: current low > previous high
                if current_bar["low"] > previous_bar["high"]:
                    gap_size = current_bar["low"] - previous_bar["high"]
                    gaps.append({"size": gap_size, "direction": "up", "index": i})
                
                # Gap down: current high < previous low
                elif current_bar["high"] < previous_bar["low"]:
                    gap_size = previous_bar["low"] - current_bar["high"]
                    gaps.append({"size": gap_size, "direction": "down", "index": i})
            
            features["gap_count"] = len(gaps)
            
            if gaps:
                # Recent gaps (last 10)
                recent_gaps = gaps[-10:] if len(gaps) > 10 else gaps
                features["recent_gap_count"] = len(recent_gaps)
                
                # Gap statistics
                gap_sizes = [gap["size"] for gap in recent_gaps]
                features["gap_size"] = float(np.mean(gap_sizes))
                features["gap_size_std"] = float(np.std(gap_sizes))
                features["max_gap_size"] = float(max(gap_sizes))
                
                # Gap direction
                up_gaps = sum(1 for gap in recent_gaps if gap["direction"] == "up")
                down_gaps = sum(1 for gap in recent_gaps if gap["direction"] == "down")
                
                if up_gaps > down_gaps:
                    features["gap_direction"] = "up"
                elif down_gaps > up_gaps:
                    features["gap_direction"] = "down"
                else:
                    features["gap_direction"] = "mixed"
                
                # Gap fill analysis
                features["gaps_filled"] = self._analyze_gap_fills(df, recent_gaps)
            else:
                features["recent_gap_count"] = 0
                features["gap_size"] = 0.0
                features["gap_size_std"] = 0.0
                features["max_gap_size"] = 0.0
                features["gap_direction"] = "none"
                features["gaps_filled"] = 0.0
            
            return features
            
        except Exception as e:
            logger.error(f"Gap analysis computation failed: {e}")
            return {"gap_count": 0, "gap_size": 0.0, "gap_direction": "none"}
    
    def _compute_execution_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute execution quality metrics."""
        try:
            features = {}
            
            if len(df) < 5:
                return {"execution_quality": "unknown", "price_efficiency": 0.0}
            
            # Price efficiency: how much of the range is captured by the close
            efficiency_scores = []
            for i in range(1, min(len(df), 20)):
                bar = df.iloc[i]
                bar_range = bar["high"] - bar["low"]
                if bar_range > 0:
                    # Efficiency based on how close the close is to the high/low
                    if bar["close"] > bar["open"]:  # Bullish bar
                        efficiency = (bar["close"] - bar["low"]) / bar_range
                    else:  # Bearish bar
                        efficiency = (bar["high"] - bar["close"]) / bar_range
                    efficiency_scores.append(efficiency)
            
            if efficiency_scores:
                avg_efficiency = np.mean(efficiency_scores)
                features["price_efficiency"] = float(avg_efficiency)
                
                # Execution quality classification
                if avg_efficiency > 0.8:
                    features["execution_quality"] = "excellent"
                elif avg_efficiency > 0.6:
                    features["execution_quality"] = "good"
                elif avg_efficiency > 0.4:
                    features["execution_quality"] = "fair"
                else:
                    features["execution_quality"] = "poor"
            else:
                features["price_efficiency"] = 0.0
                features["execution_quality"] = "unknown"
            
            # Wicks analysis (execution quality indicator)
            wick_analysis = self._analyze_wick_quality(df)
            features.update(wick_analysis)
            
            return features
            
        except Exception as e:
            logger.error(f"Execution quality computation failed: {e}")
            return {"execution_quality": "unknown", "price_efficiency": 0.0}
    
    def _analyze_wick_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze wick quality as execution indicator."""
        try:
            features = {}
            
            if len(df) < 5:
                return {"wick_quality": "unknown", "rejection_ratio": 0.0}
            
            # Analyze wicks in recent bars
            recent_bars = df.tail(min(10, len(df)))
            wick_ratios = []
            
            for _, bar in recent_bars.iterrows():
                body_size = abs(bar["close"] - bar["open"])
                total_range = bar["high"] - bar["low"]
                
                if total_range > 0:
                    upper_wick = bar["high"] - max(bar["open"], bar["close"])
                    lower_wick = min(bar["open"], bar["close"]) - bar["low"]
                    wick_ratio = (upper_wick + lower_wick) / total_range
                    wick_ratios.append(wick_ratio)
            
            if wick_ratios:
                avg_wick_ratio = np.mean(wick_ratios)
                features["rejection_ratio"] = float(avg_wick_ratio)
                
                # Wick quality classification
                if avg_wick_ratio > 0.6:
                    features["wick_quality"] = "high_rejection"
                elif avg_wick_ratio > 0.4:
                    features["wick_quality"] = "moderate_rejection"
                else:
                    features["wick_quality"] = "low_rejection"
            else:
                features["rejection_ratio"] = 0.0
                features["wick_quality"] = "unknown"
            
            return features
            
        except Exception as e:
            logger.error(f"Wick quality analysis failed: {e}")
            return {"wick_quality": "unknown", "rejection_ratio": 0.0}
    
    def _analyze_gap_fills(self, df: pd.DataFrame, gaps: List[Dict]) -> float:
        """Analyze how many gaps have been filled."""
        if not gaps:
            return 0.0
        
        filled_gaps = 0
        for gap in gaps:
            gap_index = gap["index"]
            if gap_index >= len(df):
                continue
            
            # Check if gap has been filled in subsequent bars
            gap_price = df.iloc[gap_index]["low"] if gap["direction"] == "up" else df.iloc[gap_index]["high"]
            
            for i in range(gap_index + 1, min(gap_index + 20, len(df))):
                bar = df.iloc[i]
                if gap["direction"] == "up" and bar["low"] <= gap_price:
                    filled_gaps += 1
                    break
                elif gap["direction"] == "down" and bar["high"] >= gap_price:
                    filled_gaps += 1
                    break
        
        return filled_gaps / len(gaps) if gaps else 0.0
    
    def _calculate_volume_price_correlation(self, df: pd.DataFrame) -> float:
        """Calculate correlation between volume and price movement."""
        try:
            if len(df) < 10 or "volume" not in df.columns:
                return 0.0
            
            # Calculate price changes
            price_changes = df["close"].pct_change().dropna()
            volume_changes = df["volume"].pct_change().dropna()
            
            # Align the series
            min_length = min(len(price_changes), len(volume_changes))
            if min_length < 5:
                return 0.0
            
            price_changes = price_changes.tail(min_length)
            volume_changes = volume_changes.tail(min_length)
            
            # Calculate correlation
            correlation = price_changes.corr(volume_changes)
            return float(correlation) if not np.isnan(correlation) else 0.0
            
        except Exception:
            return 0.0
    
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
