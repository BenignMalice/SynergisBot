"""
VWAP Micro Filter for Micro-Scalp Strategy

Provides VWAP proximity checks, directional filtering, and retest detection
for micro-scalp entries. Includes persistence tracking for improved accuracy.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class VWAPProximityResult:
    """VWAP proximity check result"""
    is_near_vwap: bool
    distance_pct: float  # Distance as percentage of price
    distance_points: float  # Distance in points
    is_above_vwap: bool
    is_below_vwap: bool
    in_band: bool  # Within VWAP band
    band_lower: float
    band_upper: float


@dataclass
class VWAPRetestResult:
    """VWAP retest detection result"""
    retest_detected: bool
    retest_type: Optional[str]  # "WICK_REJECTION", "ABSORPTION", "DELTA_FLIP"
    retest_candle_index: int
    confidence: float  # 0.0-1.0


class VWAPMicroFilter:
    """
    VWAP micro-filter for micro-scalp strategy.
    
    Features:
    - VWAP proximity band calculation (fixed or ATR-adjusted)
    - Directional filtering (above/below VWAP)
    - Retest detection (wick, rejection, absorption, delta flip)
    - Persistence tracking (time spent inside band)
    """
    
    def __init__(self, tolerance_type: str = "fixed", 
                 tolerance_fixed: float = 0.0005,
                 tolerance_atr_multiplier: float = 0.1,
                 persistence_min_seconds: int = 30):
        """
        Initialize VWAP Micro Filter.
        
        Args:
            tolerance_type: "fixed" or "atr_adjusted"
            tolerance_fixed: Fixed tolerance as percentage (default: 0.0005 = 0.05%)
            tolerance_atr_multiplier: ATR multiplier for dynamic tolerance (default: 0.1)
            persistence_min_seconds: Minimum seconds inside band for persistence (default: 30)
        """
        self.tolerance_type = tolerance_type
        self.tolerance_fixed = tolerance_fixed
        self.tolerance_atr_multiplier = tolerance_atr_multiplier
        self.persistence_min_seconds = persistence_min_seconds
        
        # Persistence tracking: {symbol: {'entry_time': timestamp, 'last_check': timestamp}}
        self.persistence_tracking: Dict[str, Dict[str, float]] = defaultdict(dict)
    
    def calculate_vwap_band(self, vwap: float, price: float, 
                           atr: Optional[float] = None) -> Tuple[float, float]:
        """
        Calculate VWAP proximity band.
        
        Args:
            vwap: Current VWAP value
            price: Current price (for fallback calculation)
            atr: Optional ATR(1) value for dynamic tolerance
        
        Returns:
            Tuple of (band_lower, band_upper)
        """
        if self.tolerance_type == "atr_adjusted" and atr is not None and atr > 0:
            # ATR-adjusted tolerance
            tolerance = atr * self.tolerance_atr_multiplier
        else:
            # Fixed percentage tolerance
            tolerance = vwap * self.tolerance_fixed
        
        return (vwap - tolerance, vwap + tolerance)
    
    def is_price_near_vwap(self, price: float, vwap: float, 
                           atr: Optional[float] = None) -> VWAPProximityResult:
        """
        Check if price is near VWAP.
        
        Args:
            price: Current price
            vwap: Current VWAP value
            atr: Optional ATR(1) value
        
        Returns:
            VWAPProximityResult
        """
        if vwap <= 0:
            return VWAPProximityResult(
                is_near_vwap=False,
                distance_pct=1.0,
                distance_points=abs(price - vwap) if vwap > 0 else 0.0,
                is_above_vwap=False,
                is_below_vwap=False,
                in_band=False,
                band_lower=0.0,
                band_upper=0.0
            )
        
        band_lower, band_upper = self.calculate_vwap_band(vwap, price, atr)
        in_band = band_lower <= price <= band_upper
        
        distance_points = abs(price - vwap)
        distance_pct = distance_points / vwap if vwap > 0 else 0.0
        
        is_above = price > vwap
        is_below = price < vwap
        
        return VWAPProximityResult(
            is_near_vwap=in_band,
            distance_pct=distance_pct,
            distance_points=distance_points,
            is_above_vwap=is_above,
            is_below_vwap=is_below,
            in_band=in_band,
            band_lower=band_lower,
            band_upper=band_upper
        )
    
    def is_price_above_vwap(self, price: float, vwap: float) -> bool:
        """
        Check if price is above VWAP.
        
        Args:
            price: Current price
            vwap: Current VWAP value
        
        Returns:
            True if price > VWAP
        """
        return price > vwap if vwap > 0 else False
    
    def is_price_below_vwap(self, price: float, vwap: float) -> bool:
        """
        Check if price is below VWAP.
        
        Args:
            price: Current price
            vwap: Current VWAP value
        
        Returns:
            True if price < VWAP
        """
        return price < vwap if vwap > 0 else False
    
    def detect_vwap_retest(self, candles: List[Dict[str, Any]], 
                          vwap: float, vwap_band: Tuple[float, float],
                          symbol: str = None) -> VWAPRetestResult:
        """
        Detect VWAP retest from M1 candles.
        
        Args:
            candles: List of M1 candle dicts
            vwap: Current VWAP value
            vwap_band: VWAP band (lower, upper)
            symbol: Optional symbol for logging
        
        Returns:
            VWAPRetestResult
        """
        if len(candles) < 2:
            return VWAPRetestResult(
                retest_detected=False,
                retest_type=None,
                retest_candle_index=-1,
                confidence=0.0
            )
        
        band_lower, band_upper = vwap_band
        last_candle = candles[-1]
        
        # Check if price touched VWAP band
        price_touched = (last_candle.get('low', 0) <= band_upper and 
                        last_candle.get('high', 0) >= band_lower)
        
        if not price_touched:
            return VWAPRetestResult(
                retest_detected=False,
                retest_type=None,
                retest_candle_index=-1,
                confidence=0.0
            )
        
        # Check for wick rejection
        wick_rejection = self._check_wick_rejection(last_candle, vwap)
        
        # Check for absorption (price touched but didn't break)
        absorption = self._check_absorption(last_candle, vwap_band)
        
        retest_type = None
        confidence = 0.0
        
        if wick_rejection:
            retest_type = "WICK_REJECTION"
            confidence = 0.7
        elif absorption:
            retest_type = "ABSORPTION"
            confidence = 0.5
        
        if retest_type:
            return VWAPRetestResult(
                retest_detected=True,
                retest_type=retest_type,
                retest_candle_index=len(candles) - 1,
                confidence=confidence
            )
        
        return VWAPRetestResult(
            retest_detected=False,
            retest_type=None,
            retest_candle_index=-1,
            confidence=0.0
        )
    
    def _check_wick_rejection(self, candle: Dict[str, Any], vwap: float) -> bool:
        """Check for wick rejection at VWAP"""
        open_price = candle.get('open', 0)
        close = candle.get('close', 0)
        high = candle.get('high', 0)
        low = candle.get('low', 0)
        
        body_size = abs(close - open_price)
        if body_size == 0:
            return False
        
        # Upper wick rejection (price above VWAP, rejected down)
        if close < vwap and high > vwap:
            upper_wick = high - max(open_price, close)
            if upper_wick >= body_size * 1.5:  # Wick >= 1.5× body
                return True
        
        # Lower wick rejection (price below VWAP, rejected up)
        if close > vwap and low < vwap:
            lower_wick = min(open_price, close) - low
            if lower_wick >= body_size * 1.5:  # Wick >= 1.5× body
                return True
        
        return False
    
    def _check_absorption(self, candle: Dict[str, Any], 
                         vwap_band: Tuple[float, float]) -> bool:
        """Check for absorption (price touched VWAP but didn't break)"""
        band_lower, band_upper = vwap_band
        low = candle.get('low', 0)
        high = candle.get('high', 0)
        close = candle.get('close', 0)
        
        # Price touched band but closed within or near it
        touched = (low <= band_upper and high >= band_lower)
        closed_near = (band_lower * 0.999 <= close <= band_upper * 1.001)
        
        return touched and closed_near
    
    def track_vwap_persistence(self, symbol: str, price: float, vwap: float,
                              vwap_band: Tuple[float, float]) -> float:
        """
        Track how long price has been inside VWAP band.
        
        Args:
            symbol: Trading symbol
            price: Current price
            vwap: Current VWAP value
            vwap_band: VWAP band (lower, upper)
        
        Returns:
            Persistence in seconds
        """
        band_lower, band_upper = vwap_band
        current_time = time.time()
        in_band = band_lower <= price <= band_upper
        
        if symbol not in self.persistence_tracking:
            if in_band:
                # Entered band
                self.persistence_tracking[symbol] = {
                    'entry_time': current_time,
                    'last_check': current_time
                }
            return 0.0
        
        tracking = self.persistence_tracking[symbol]
        
        if in_band:
            # Still in band - update last check
            tracking['last_check'] = current_time
            persistence = current_time - tracking['entry_time']
            return persistence
        else:
            # Left band - clear tracking
            persistence = current_time - tracking.get('entry_time', current_time)
            del self.persistence_tracking[symbol]
            return 0.0
    
    def get_persistence_bonus(self, persistence_seconds: float) -> float:
        """
        Get confidence bonus based on persistence.
        
        Args:
            persistence_seconds: Time spent inside VWAP band
        
        Returns:
            Confidence multiplier (1.0 = no bonus, 1.2 = 20% bonus)
        """
        if persistence_seconds < self.persistence_min_seconds:
            return 1.0
        
        # Bonus increases with persistence
        # 30s = 1.0×, 60s = 1.1×, 90s+ = 1.2×
        if persistence_seconds >= 90:
            return 1.2
        elif persistence_seconds >= 60:
            return 1.1
        else:
            return 1.0
    
    def validate_retest(self, candles: List[Dict[str, Any]], 
                       retest_data: VWAPRetestResult,
                       symbol: str) -> bool:
        """
        Validate VWAP retest with additional checks.
        
        Args:
            candles: List of M1 candles
            retest_data: VWAPRetestResult from detect_vwap_retest
            symbol: Trading symbol
        
        Returns:
            True if retest validated, False otherwise
        """
        if not retest_data.retest_detected:
            return False
        
        # Additional validation based on retest type
        if retest_data.retest_type == "WICK_REJECTION":
            # Wick rejection is strong signal
            return retest_data.confidence >= 0.6
        
        elif retest_data.retest_type == "ABSORPTION":
            # Absorption needs volume confirmation (if available)
            if len(candles) >= 2:
                last_candle = candles[-1]
                if 'volume' in last_candle:
                    # Check if volume is above average
                    avg_volume = sum(c.get('volume', 0) for c in candles[-5:-1]) / max(1, len(candles) - 1)
                    if avg_volume > 0:
                        volume_ratio = last_candle['volume'] / avg_volume
                        return volume_ratio >= 1.2  # 20% above average
        
        return retest_data.confidence >= 0.5
    
    def clear_persistence(self, symbol: Optional[str] = None):
        """
        Clear persistence tracking for a symbol or all symbols.
        
        Args:
            symbol: Optional symbol to clear (if None, clears all)
        """
        if symbol is not None:
            if symbol in self.persistence_tracking:
                del self.persistence_tracking[symbol]
        else:
            self.persistence_tracking.clear()

