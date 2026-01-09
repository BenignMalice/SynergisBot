"""
Delta Divergence Detector (Phase 1.3)

Detects delta divergence by comparing price trend vs. delta trend.
Delta divergence occurs when price and delta move in opposite directions.

Examples:
- Bullish: Price makes lower lows, but delta makes higher lows (buying pressure increasing)
- Bearish: Price makes higher highs, but delta makes lower highs (selling pressure increasing)
"""

import logging
import numpy as np
from typing import Dict, Optional, List
import pandas as pd

logger = logging.getLogger(__name__)


class DeltaDivergenceDetector:
    """
    Detects delta divergence patterns.
    
    Compares price movement trends with delta volume trends to identify
    potential reversals or continuation signals.
    """
    
    def __init__(self, min_bars: int = 20, trend_period: int = 10):
        """
        Initialize delta divergence detector.
        
        Args:
            min_bars: Minimum number of bars required for detection
            trend_period: Number of bars to analyze for trend
        """
        self.min_bars = min_bars
        self.trend_period = trend_period
        logger.debug(f"DeltaDivergenceDetector initialized (min_bars={min_bars}, trend_period={trend_period})")
    
    def detect_delta_divergence(
        self, 
        price_bars_df: pd.DataFrame,
        delta_history: List[float]
    ) -> Optional[Dict]:
        """
        Detect bullish/bearish delta divergence.
        
        Phase 1.3: Compares price trend with delta trend.
        
        Args:
            price_bars_df: pandas DataFrame with price bars (columns: 'close', 'high', 'low', etc.)
            delta_history: List of delta values (aligned with price_bars_df)
        
        Returns:
            Dict with 'type' ('bullish'/'bearish'), 'strength' (0.0-1.0), or None
        """
        if price_bars_df is None or len(price_bars_df) < self.min_bars:
            return None
        
        if not delta_history or len(delta_history) < self.min_bars:
            return None
        
        try:
            # Align delta history with price bars (assume 1:1 if same length)
            if len(delta_history) < len(price_bars_df):
                # Not enough delta values
                return None
            
            # Get aligned delta values
            aligned_delta = delta_history[-len(price_bars_df):]
            
            # Calculate price trend (slope of closes)
            price_closes = price_bars_df['close'].values[-self.trend_period:].tolist()
            price_slope = self._calculate_trend_slope(price_closes)
            
            # Calculate delta trend (slope of delta values)
            delta_slope = self._calculate_trend_slope(aligned_delta[-self.trend_period:])
            
            # Detect divergence
            # Bullish: Price falling (negative slope) but delta rising (positive slope)
            if price_slope < -0.001 and delta_slope > 0.001:
                strength = self._calculate_divergence_strength(price_slope, delta_slope)
                return {
                    'type': 'bullish',
                    'strength': strength,
                    'price_slope': price_slope,
                    'delta_slope': delta_slope
                }
            
            # Bearish: Price rising (positive slope) but delta falling (negative slope)
            if price_slope > 0.001 and delta_slope < -0.001:
                strength = self._calculate_divergence_strength(price_slope, delta_slope)
                return {
                    'type': 'bearish',
                    'strength': strength,
                    'price_slope': price_slope,
                    'delta_slope': delta_slope
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"Error detecting delta divergence: {e}")
            return None
    
    def _calculate_trend_slope(self, values: List[float]) -> float:
        """
        Calculate trend slope using linear regression.
        
        Args:
            values: List of numeric values
        
        Returns:
            Slope value (positive = rising, negative = falling)
        """
        if len(values) < 2:
            return 0.0
        
        try:
            # Simple linear regression
            x = np.arange(len(values))
            y = np.array(values)
            slope = float(np.polyfit(x, y, 1)[0])  # Linear fit, get slope
            return slope
        except Exception as e:
            logger.debug(f"Error calculating trend slope: {e}")
            return 0.0
    
    def _calculate_divergence_strength(self, price_slope: float, delta_slope: float) -> float:
        """
        Calculate divergence strength (0.0-1.0).
        
        Args:
            price_slope: Price trend slope
            delta_slope: Delta trend slope
        
        Returns:
            Strength value between 0.0 and 1.0
        """
        try:
            # Strength is based on how opposite the slopes are
            # Higher strength when slopes are strongly opposite
            price_magnitude = abs(price_slope)
            delta_magnitude = abs(delta_slope)
            
            # Normalize to 0-1
            # Use geometric mean for balanced strength calculation
            if price_magnitude == 0 or delta_magnitude == 0:
                return 0.0
            
            # Strength increases with both price and delta movement magnitude
            # But also considers how opposite they are
            strength = min(1.0, (price_magnitude + delta_magnitude) / (price_magnitude * 2))
            
            # Boost strength if slopes are strongly opposite
            if (price_slope > 0 and delta_slope < 0) or (price_slope < 0 and delta_slope > 0):
                # Both are significant and opposite
                strength = min(1.0, strength * 1.2)  # 20% boost for clear divergence
            
            return strength
            
        except Exception as e:
            logger.debug(f"Error calculating divergence strength: {e}")
            return 0.0
