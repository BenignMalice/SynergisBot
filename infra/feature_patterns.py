"""
Feature Patterns Module
Computes candlestick patterns and simple pattern flags
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)

class PatternFeatures:
    """
    IMPROVED: Computes candlestick patterns and simple pattern flags.
    Focuses on binary/score flags rather than verbose narratives.
    """
    
    def compute(self, df: pd.DataFrame, symbol: str, timeframe: str) -> Dict[str, Any]:
        """Compute all pattern features for the given DataFrame."""
        try:
            features = {}
            
            # Candlestick patterns
            features.update(self._compute_candlestick_patterns(df))
            
            # Multi-bar patterns
            features.update(self._compute_multi_bar_patterns(df))
            
            # Wick analysis
            features.update(self._compute_wick_analysis(df))
            
            # Pattern strength scoring
            features.update(self._compute_pattern_strength(df))
            
            return features
            
        except Exception as e:
            logger.error(f"Pattern computation failed for {symbol} {timeframe}: {e}")
            return {}
    
    def _compute_candlestick_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute single-bar candlestick patterns."""
        try:
            features = {}
            
            if len(df) < 1:
                return self._empty_pattern_features()
            
            # Get current bar
            current = df.iloc[-1]
            features["candlestick_flags"] = {}
            
            # Marubozu (strong body, small wicks)
            body_size = abs(current["close"] - current["open"])
            total_range = current["high"] - current["low"]
            body_ratio = body_size / total_range if total_range > 0 else 0
            
            features["candlestick_flags"]["marubozu_bull"] = body_ratio > 0.8 and current["close"] > current["open"]
            features["candlestick_flags"]["marubozu_bear"] = body_ratio > 0.8 and current["close"] < current["open"]
            
            # Doji (small body, large wicks)
            features["candlestick_flags"]["doji"] = body_ratio < 0.1
            
            # Hammer/Shooting Star (long lower wick, small body)
            lower_wick = current["open"] - current["low"] if current["close"] > current["open"] else current["close"] - current["low"]
            upper_wick = current["high"] - current["open"] if current["close"] > current["open"] else current["high"] - current["close"]
            
            features["candlestick_flags"]["hammer"] = (lower_wick > 2 * body_size and 
                                                      upper_wick < body_size and 
                                                      current["close"] > current["open"])
            features["candlestick_flags"]["shooting_star"] = (upper_wick > 2 * body_size and 
                                                             lower_wick < body_size and 
                                                             current["close"] < current["open"])
            
            # Pin Bar (long wick on one side)
            features["candlestick_flags"]["pin_bar_bull"] = (lower_wick > 2 * body_size and 
                                                            upper_wick < body_size)
            features["candlestick_flags"]["pin_bar_bear"] = (upper_wick > 2 * body_size and 
                                                            lower_wick < body_size)
            
            return features
            
        except Exception as e:
            logger.error(f"Candlestick pattern computation failed: {e}")
            return {"candlestick_flags": {}}
    
    def _compute_multi_bar_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute multi-bar patterns."""
        try:
            features = {}
            features["pattern_flags"] = {}
            
            if len(df) < 2:
                return features
            
            # Get last 2-3 bars
            current = df.iloc[-1]
            previous = df.iloc[-2]
            
            # Engulfing patterns
            current_body = abs(current["close"] - current["open"])
            previous_body = abs(previous["close"] - previous["open"])
            
            features["pattern_flags"]["bull_engulfing"] = (
                previous["close"] < previous["open"] and  # Previous bearish
                current["close"] > current["open"] and    # Current bullish
                current["open"] < previous["close"] and   # Current opens below previous close
                current["close"] > previous["open"] and   # Current closes above previous open
                current_body > previous_body              # Current body engulfs previous
            )
            
            features["pattern_flags"]["bear_engulfing"] = (
                previous["close"] > previous["open"] and  # Previous bullish
                current["close"] < current["open"] and    # Current bearish
                current["open"] > previous["close"] and   # Current opens above previous close
                current["close"] < previous["open"] and   # Current closes below previous open
                current_body > previous_body              # Current body engulfs previous
            )
            
            # Inside/Outside bars
            features["pattern_flags"]["inside_bar"] = (
                current["high"] < previous["high"] and
                current["low"] > previous["low"]
            )
            
            features["pattern_flags"]["outside_bar"] = (
                current["high"] > previous["high"] and
                current["low"] < previous["low"]
            )
            
            # Breakout bar (range expansion)
            if len(df) >= 20:
                recent_high = df["high"].tail(20).max()
                recent_low = df["low"].tail(20).min()
                recent_range = recent_high - recent_low
                
                features["pattern_flags"]["breakout_bar"] = (
                    current["high"] - current["low"] > recent_range * 1.5
                )
            else:
                features["pattern_flags"]["breakout_bar"] = False
            
            # Three-bar patterns
            if len(df) >= 3:
                two_ago = df.iloc[-3]
                features.update(self._compute_three_bar_patterns(two_ago, previous, current))
            
            return features
            
        except Exception as e:
            logger.error(f"Multi-bar pattern computation failed: {e}")
            return {"pattern_flags": {}}
    
    def _compute_three_bar_patterns(self, two_ago: pd.Series, previous: pd.Series, current: pd.Series) -> Dict[str, Any]:
        """Compute three-bar patterns."""
        patterns = {}
        
        # Three Black Crows / Three White Soldiers
        patterns["three_white_soldiers"] = (
            two_ago["close"] > two_ago["open"] and
            previous["close"] > previous["open"] and
            current["close"] > current["open"] and
            two_ago["close"] < previous["close"] < current["close"] and
            two_ago["open"] < previous["open"] < current["open"]
        )
        
        patterns["three_black_crows"] = (
            two_ago["close"] < two_ago["open"] and
            previous["close"] < previous["open"] and
            current["close"] < current["open"] and
            two_ago["close"] > previous["close"] > current["close"] and
            two_ago["open"] > previous["open"] > current["open"]
        )
        
        # Morning Star / Evening Star
        patterns["morning_star"] = (
            two_ago["close"] < two_ago["open"] and  # First bearish
            abs(previous["close"] - previous["open"]) < (two_ago["high"] - two_ago["low"]) * 0.3 and  # Second small body
            current["close"] > current["open"] and  # Third bullish
            current["close"] > (two_ago["open"] + two_ago["close"]) / 2  # Third closes above first midpoint
        )
        
        patterns["evening_star"] = (
            two_ago["close"] > two_ago["open"] and  # First bullish
            abs(previous["close"] - previous["open"]) < (two_ago["high"] - two_ago["low"]) * 0.3 and  # Second small body
            current["close"] < current["open"] and  # Third bearish
            current["close"] < (two_ago["open"] + two_ago["close"]) / 2  # Third closes below first midpoint
        )
        
        return patterns
    
    def _compute_wick_analysis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute wick analysis metrics."""
        try:
            features = {}
            features["wick_metrics"] = {}
            
            if len(df) < 1:
                return features
            
            current = df.iloc[-1]
            body_size = abs(current["close"] - current["open"])
            total_range = current["high"] - current["low"]
            
            if total_range == 0:
                return features
            
            # Calculate wick sizes
            upper_wick = current["high"] - max(current["open"], current["close"])
            lower_wick = min(current["open"], current["close"]) - current["low"]
            
            # Wick percentages
            features["wick_metrics"]["upper_wick_pct"] = upper_wick / total_range
            features["wick_metrics"]["lower_wick_pct"] = lower_wick / total_range
            features["wick_metrics"]["body_pct"] = body_size / total_range
            
            # Wick asymmetry index (-1 to 1, negative = lower wick dominant, positive = upper wick dominant)
            if upper_wick + lower_wick > 0:
                features["wick_metrics"]["wick_asymmetry"] = (upper_wick - lower_wick) / (upper_wick + lower_wick)
            else:
                features["wick_metrics"]["wick_asymmetry"] = 0.0
            
            # ATR-normalized wick sizes
            if len(df) >= 14:
                atr_14 = self._calculate_atr(df.tail(14))
                if atr_14 > 0:
                    features["wick_metrics"]["upper_wick_atr"] = upper_wick / atr_14
                    features["wick_metrics"]["lower_wick_atr"] = lower_wick / atr_14
                else:
                    features["wick_metrics"]["upper_wick_atr"] = 0.0
                    features["wick_metrics"]["lower_wick_atr"] = 0.0
            else:
                features["wick_metrics"]["upper_wick_atr"] = 0.0
                features["wick_metrics"]["lower_wick_atr"] = 0.0
            
            return features
            
        except Exception as e:
            logger.error(f"Wick analysis computation failed: {e}")
            return {"wick_metrics": {}}
    
    def _compute_pattern_strength(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute pattern strength scores."""
        try:
            features = {}
            
            if len(df) < 20:
                return {"pattern_strength": 0.0}
            
            # Calculate pattern strength based on multiple factors
            strength_factors = []
            
            # Body size factor
            current = df.iloc[-1]
            body_size = abs(current["close"] - current["open"])
            total_range = current["high"] - current["low"]
            body_ratio = body_size / total_range if total_range > 0 else 0
            strength_factors.append(min(body_ratio * 2, 1.0))  # Normalize to 0-1
            
            # Volume confirmation (if available)
            if "volume" in df.columns and df["volume"].sum() > 0:
                volume_20_mean = df["volume"].tail(20).mean()
                current_volume = current["volume"]
                volume_factor = min(current_volume / volume_20_mean, 2.0) / 2.0 if volume_20_mean > 0 else 0.5
                strength_factors.append(volume_factor)
            
            # Trend alignment factor
            if len(df) >= 20:
                ema_20 = df["close"].ewm(span=20).mean().iloc[-1]
                trend_alignment = 1.0 if (current["close"] > ema_20 and current["close"] > current["open"]) or (current["close"] < ema_20 and current["close"] < current["open"]) else 0.5
                strength_factors.append(trend_alignment)
            
            # Volatility factor
            if len(df) >= 14:
                atr_14 = self._calculate_atr(df.tail(14))
                atr_100 = self._calculate_atr(df.tail(min(100, len(df))))
                vol_factor = min(atr_14 / atr_100, 2.0) / 2.0 if atr_100 > 0 else 0.5
                strength_factors.append(vol_factor)
            
            # Calculate overall pattern strength
            if strength_factors:
                features["pattern_strength"] = float(np.mean(strength_factors))
            else:
                features["pattern_strength"] = 0.0
            
            return features
            
        except Exception as e:
            logger.error(f"Pattern strength computation failed: {e}")
            return {"pattern_strength": 0.0}
    
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
    
    def _empty_pattern_features(self) -> Dict[str, Any]:
        """Return empty pattern features."""
        return {
            "candlestick_flags": {
                "marubozu_bull": False,
                "marubozu_bear": False,
                "doji": False,
                "hammer": False,
                "shooting_star": False,
                "pin_bar_bull": False,
                "pin_bar_bear": False
            },
            "pattern_flags": {
                "bull_engulfing": False,
                "bear_engulfing": False,
                "inside_bar": False,
                "outside_bar": False,
                "breakout_bar": False,
                "three_white_soldiers": False,
                "three_black_crows": False,
                "morning_star": False,
                "evening_star": False
            },
            "wick_metrics": {
                "upper_wick_pct": 0.0,
                "lower_wick_pct": 0.0,
                "body_pct": 0.0,
                "wick_asymmetry": 0.0,
                "upper_wick_atr": 0.0,
                "lower_wick_atr": 0.0
            },
            "pattern_strength": 0.0
        }
