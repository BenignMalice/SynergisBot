"""
Phase III: Volatility Pattern Recognition Module
Detects volatility fractals, IV collapse, and recoil patterns
"""

import logging
from typing import Dict, Optional, Any, List
from collections import deque
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class VolatilityPatternRecognizer:
    """
    Phase III: Recognizes volatility patterns for institutional-grade trading.
    
    Patterns detected:
    - Consecutive inside bars
    - Volatility fractal expansion
    - IV collapse/recoil
    - BB width trends
    - RMAG ATR ratios
    """
    
    def __init__(self, cache_ttl_seconds: int = 120):
        """
        Initialize volatility pattern recognizer.
        
        Args:
            cache_ttl_seconds: Cache TTL in seconds (default: 120 = 2 minutes)
        """
        self.cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}  # key -> {result, timestamp}
        logger.info("Phase III: VolatilityPatternRecognizer initialized")
    
    def _get_cache_key(self, symbol: str, pattern_type: str, timeframe: str = "M15") -> str:
        """Generate cache key"""
        return f"{symbol}_{timeframe}_{pattern_type}"
    
    def _get_cached(self, cache_key: str) -> Optional[Any]:
        """Get cached result if still valid"""
        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]
            age_seconds = (datetime.now(timezone.utc) - timestamp).total_seconds()
            if age_seconds < self.cache_ttl:
                return result
            else:
                del self._cache[cache_key]
        return None
    
    def _cache_result(self, cache_key: str, result: Any):
        """Cache result"""
        self._cache[cache_key] = (result, datetime.now(timezone.utc))
        # Limit cache size (remove oldest if > 100 entries)
        if len(self._cache) > 100:
            oldest_key = min(self._cache.keys(), 
                           key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
    
    def detect_consecutive_inside_bars(
        self, 
        candles: List[Dict], 
        min_count: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Detect consecutive inside bar pattern.
        
        Args:
            candles: List of candle dicts (newest first)
            min_count: Minimum number of consecutive inside bars (default: 3)
        
        Returns:
            {
                "consecutive_inside_bars": int,
                "pattern_detected": bool,
                "first_inside_index": int
            } or None
        """
        if not candles or len(candles) < min_count + 1:
            return None
        
        consecutive_count = 0
        first_inside_index = None
        
        # Check for consecutive inside bars
        for i in range(len(candles) - 1):
            current = candles[i]
            mother = candles[i + 1]
            
            current_high = current.get('high') if isinstance(current, dict) else current.high
            current_low = current.get('low') if isinstance(current, dict) else current.low
            mother_high = mother.get('high') if isinstance(mother, dict) else mother.high
            mother_low = mother.get('low') if isinstance(mother, dict) else mother.low
            
            # Check if current is inside mother
            is_inside = (current_high <= mother_high and current_low >= mother_low)
            
            if is_inside:
                if consecutive_count == 0:
                    first_inside_index = i
                consecutive_count += 1
            else:
                # Reset if sequence breaks
                if consecutive_count < min_count:
                    consecutive_count = 0
                    first_inside_index = None
        
        pattern_detected = consecutive_count >= min_count
        
        return {
            "consecutive_inside_bars": consecutive_count,
            "pattern_detected": pattern_detected,
            "first_inside_index": first_inside_index
        }
    
    def detect_volatility_fractal_expansion(
        self,
        candles: List[Dict],
        bb_widths: List[float],
        atr_values: List[float],
        bb_expansion_threshold: float = 0.20,
        atr_expansion_threshold: float = 0.15,
        window_bars: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Detect volatility fractal expansion pattern.
        
        Pattern: BB width expands >20% AND ATR increases >15% within 3-5 bars.
        
        Args:
            candles: List of candle dicts (newest first)
            bb_widths: List of BB widths (newest first, same length as candles)
            atr_values: List of ATR values (newest first, same length as candles)
            bb_expansion_threshold: BB width expansion threshold (default: 0.20 = 20%)
            atr_expansion_threshold: ATR expansion threshold (default: 0.15 = 15%)
            window_bars: Window size for expansion check (default: 5)
        
        Returns:
            {
                "volatility_fractal_expansion": bool,
                "bb_expansion_pct": float,
                "atr_expansion_pct": float,
                "expansion_bars": int
            } or None
        """
        if not candles or len(candles) < window_bars + 1:
            return None
        
        if len(bb_widths) < window_bars + 1 or len(atr_values) < window_bars + 1:
            return None
        
        # Get recent values
        recent_bb = bb_widths[:window_bars]
        recent_atr = atr_values[:window_bars]
        
        # Calculate expansion percentages
        current_bb = recent_bb[0]
        baseline_bb = sum(recent_bb[1:]) / len(recent_bb[1:]) if len(recent_bb) > 1 else current_bb
        
        current_atr = recent_atr[0]
        baseline_atr = sum(recent_atr[1:]) / len(recent_atr[1:]) if len(recent_atr) > 1 else current_atr
        
        if baseline_bb == 0 or baseline_atr == 0:
            return None
        
        bb_expansion_pct = (current_bb - baseline_bb) / baseline_bb
        atr_expansion_pct = (current_atr - baseline_atr) / baseline_atr
        
        # Check if both thresholds met
        volatility_fractal_expansion = (
            bb_expansion_pct >= bb_expansion_threshold and
            atr_expansion_pct >= atr_expansion_threshold
        )
        
        return {
            "volatility_fractal_expansion": volatility_fractal_expansion,
            "bb_expansion_pct": bb_expansion_pct,
            "atr_expansion_pct": atr_expansion_pct,
            "expansion_bars": window_bars
        }
    
    def detect_iv_collapse(
        self,
        atr_values: List[float],
        vix_value: Optional[float] = None,
        collapse_threshold: float = 0.30,
        window_bars: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        Detect IV (implied volatility) collapse.
        
        Uses ATR as proxy for IV. If VIX available, can use that too.
        
        Args:
            atr_values: List of ATR values (newest first)
            vix_value: Current VIX value (optional)
            collapse_threshold: Collapse threshold (default: 0.30 = 30% drop)
            window_bars: Window size for collapse check (default: 10)
        
        Returns:
            {
                "iv_collapse_detected": bool,
                "atr_collapse_pct": float,
                "vix_collapse_pct": Optional[float]
            } or None
        """
        if not atr_values or len(atr_values) < window_bars + 1:
            return None
        
        # Calculate ATR collapse
        recent_atr = atr_values[:window_bars + 1]
        current_atr = recent_atr[0]
        baseline_atr = sum(recent_atr[1:]) / len(recent_atr[1:]) if len(recent_atr) > 1 else current_atr
        
        if baseline_atr == 0:
            return None
        
        atr_collapse_pct = (baseline_atr - current_atr) / baseline_atr
        
        iv_collapse_detected = atr_collapse_pct >= collapse_threshold
        
        return {
            "iv_collapse_detected": iv_collapse_detected,
            "atr_collapse_pct": atr_collapse_pct,
            "vix_collapse_pct": None  # Would need VIX history to calculate
        }
    
    def detect_volatility_recoil(
        self,
        atr_values: List[float],
        collapse_threshold: float = 0.30,
        recoil_threshold: float = 0.15,
        window_bars: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        Detect volatility recoil pattern.
        
        Pattern: IV/ATR collapses >30% then rebounds >15% within 5-10 bars.
        
        Args:
            atr_values: List of ATR values (newest first)
            collapse_threshold: Collapse threshold (default: 0.30 = 30%)
            recoil_threshold: Recoil threshold (default: 0.15 = 15%)
            window_bars: Window size for pattern check (default: 10)
        
        Returns:
            {
                "volatility_recoil_confirmed": bool,
                "collapse_pct": float,
                "recoil_pct": float,
                "pattern_bars": int
            } or None
        """
        if not atr_values or len(atr_values) < window_bars + 1:
            return None
        
        # Find collapse point (look back further)
        lookback = min(window_bars * 2, len(atr_values) - 1)
        if lookback < window_bars:
            return None
        
        # Find minimum ATR in lookback window (collapse point)
        recent_atr = atr_values[:lookback + 1]
        min_atr = min(recent_atr[1:])  # Exclude current
        min_index = recent_atr.index(min_atr)
        
        # Get baseline before collapse
        if min_index + 1 >= len(recent_atr):
            return None
        
        baseline_atr = recent_atr[min_index + 1]
        current_atr = recent_atr[0]
        
        if baseline_atr == 0 or min_atr == 0:
            return None
        
        # Calculate collapse and recoil
        collapse_pct = (baseline_atr - min_atr) / baseline_atr
        recoil_pct = (current_atr - min_atr) / min_atr
        
        # Check if pattern confirmed
        volatility_recoil_confirmed = (
            collapse_pct >= collapse_threshold and
            recoil_pct >= recoil_threshold
        )
        
        return {
            "volatility_recoil_confirmed": volatility_recoil_confirmed,
            "collapse_pct": collapse_pct,
            "recoil_pct": recoil_pct,
            "pattern_bars": lookback - min_index
        }
    
    def calculate_bb_width_trend(
        self,
        bb_widths: List[float],
        window: int = 10
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate BB width trend (rising/falling).
        
        Args:
            bb_widths: List of BB widths (newest first)
            window: Window size for trend calculation (default: 10)
        
        Returns:
            {
                "bb_width_rising": bool,
                "bb_width_falling": bool,
                "trend_slope": float,
                "trend_strength": float
            } or None
        """
        if not bb_widths or len(bb_widths) < window:
            return None
        
        recent_widths = bb_widths[:window]
        
        # Calculate linear regression slope
        n = len(recent_widths)
        x = list(range(n))
        y = recent_widths
        
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(x[i] * x[i] for i in range(n))
        
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return None
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        
        # Determine trend
        bb_width_rising = slope > 0.001  # Small threshold to avoid noise
        bb_width_falling = slope < -0.001
        
        # Calculate trend strength (R-squared approximation)
        y_mean = sum_y / n
        ss_res = sum((y[i] - (slope * x[i] + (sum_y - slope * sum_x) / n)) ** 2 for i in range(n))
        ss_tot = sum((y[i] - y_mean) ** 2 for i in range(n))
        trend_strength = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        
        return {
            "bb_width_rising": bb_width_rising,
            "bb_width_falling": bb_width_falling,
            "trend_slope": slope,
            "trend_strength": abs(trend_strength)
        }
    
    def calculate_rmag_atr_ratio(
        self,
        rmag_value: float,
        atr_value: float
    ) -> Optional[float]:
        """
        Calculate RMAG ATR ratio.
        
        Args:
            rmag_value: RMAG value (from advanced features)
            atr_value: ATR value (from M5 or M15 timeframe)
        
        Returns:
            RMAG ATR ratio (rmag_value / atr_value) or None
        """
        if atr_value == 0:
            return None
        
        return rmag_value / atr_value

