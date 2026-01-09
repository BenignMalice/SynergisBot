"""
Micro Order Block Detector for Micro-Scalp Strategy

Detects micro order blocks on M1 timeframe:
- Last candle before micro impulse (within last 3 M1 candles)
- Dynamic ATR-based range threshold (0.1-0.3 × ATR(1))
- Validates OB retest for entry
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MicroOrderBlock:
    """Micro order block result"""
    detected: bool
    direction: Optional[str]  # "BULLISH" or "BEARISH"
    price_range: Tuple[float, float]  # (low, high)
    candle_index: int  # Index of OB candle
    strength: float  # Strength score (0.0-1.0)
    atr_based: bool  # Whether range is ATR-based
    retest_detected: bool  # Whether price is retesting the OB


class MicroOrderBlockDetector:
    """
    Detects micro order blocks on M1 timeframe.
    
    A micro order block is:
    1. Last candle before a micro impulse move (within last 3 candles)
    2. Strong candle (bullish/bearish) followed by consolidation
    3. Price range within ATR-based threshold (0.1-0.3 × ATR(1))
    4. Can be retested for entry
    """
    
    def __init__(self, lookback: int = 3, 
                 atr_multiplier_range: Tuple[float, float] = (0.1, 0.3),
                 fallback_range_pct: Tuple[float, float] = (0.001, 0.003)):
        """
        Initialize Micro Order Block Detector.
        
        Args:
            lookback: Number of M1 candles to look back (default: 3)
            atr_multiplier_range: ATR multiplier range for dynamic threshold (default: (0.1, 0.3))
            fallback_range_pct: Fallback percentage range if ATR unavailable (default: (0.001, 0.003))
        """
        self.lookback = lookback
        self.atr_multiplier_range = atr_multiplier_range
        self.fallback_range_pct = fallback_range_pct
    
    def detect_micro_obs(self, candles: List[Dict[str, Any]], 
                        atr_value: Optional[float] = None,
                        current_price: Optional[float] = None) -> List[MicroOrderBlock]:
        """
        Detect micro order blocks from M1 candles.
        
        Args:
            candles: List of M1 candle dicts with keys: 'time', 'open', 'high', 'low', 'close', 'volume'
            atr_value: Optional ATR(1) value for dynamic range calculation
            current_price: Optional current price for retest detection
        
        Returns:
            List of MicroOrderBlock objects (most recent first)
        """
        if len(candles) < self.lookback + 1:
            return []
        
        # Get recent candles (last lookback + 1 for comparison)
        recent_candles = candles[-(self.lookback + 1):]
        
        # Calculate dynamic range threshold
        range_threshold = self._calculate_range_threshold(
            candles[-1] if candles else None, atr_value
        )
        
        micro_obs = []
        
        # Check each candle in lookback period
        for i in range(len(recent_candles) - 1):
            candle_idx = len(candles) - len(recent_candles) + i
            candle = recent_candles[i]
            next_candle = recent_candles[i + 1]
            
            # Check for bullish micro OB
            bull_ob = self._check_bullish_ob(candle, next_candle, range_threshold)
            if bull_ob:
                retest = False
                if current_price is not None:
                    retest = self._check_retest(
                        current_price, bull_ob['price_range'], "BULLISH"
                    )
                
                micro_obs.append(MicroOrderBlock(
                    detected=True,
                    direction="BULLISH",
                    price_range=bull_ob['price_range'],
                    candle_index=candle_idx,
                    strength=bull_ob['strength'],
                    atr_based=atr_value is not None,
                    retest_detected=retest
                ))
            
            # Check for bearish micro OB
            bear_ob = self._check_bearish_ob(candle, next_candle, range_threshold)
            if bear_ob:
                retest = False
                if current_price is not None:
                    retest = self._check_retest(
                        current_price, bear_ob['price_range'], "BEARISH"
                    )
                
                micro_obs.append(MicroOrderBlock(
                    detected=True,
                    direction="BEARISH",
                    price_range=bear_ob['price_range'],
                    candle_index=candle_idx,
                    strength=bear_ob['strength'],
                    atr_based=atr_value is not None,
                    retest_detected=retest
                ))
        
        # Return most recent first
        return sorted(micro_obs, key=lambda x: x.candle_index, reverse=True)
    
    def _calculate_range_threshold(self, last_candle: Optional[Dict[str, Any]], 
                                   atr_value: Optional[float]) -> Tuple[float, float]:
        """
        Calculate dynamic range threshold for micro OB.
        
        Args:
            last_candle: Last candle (for fallback calculation)
            atr_value: Optional ATR(1) value
        
        Returns:
            Tuple of (min_range, max_range)
        """
        if atr_value is not None and atr_value > 0:
            # ATR-based range
            min_range = atr_value * self.atr_multiplier_range[0]
            max_range = atr_value * self.atr_multiplier_range[1]
            return (min_range, max_range)
        else:
            # Fallback to percentage-based range
            if last_candle is None:
                return (0.0, 0.0)
            
            price = last_candle.get('close', 0) or last_candle.get('open', 0)
            if price <= 0:
                return (0.0, 0.0)
            
            min_range = price * self.fallback_range_pct[0]
            max_range = price * self.fallback_range_pct[1]
            return (min_range, max_range)
    
    def _check_bullish_ob(self, candle: Dict[str, Any], next_candle: Dict[str, Any],
                          range_threshold: Tuple[float, float]) -> Optional[Dict[str, Any]]:
        """
        Check if candle is a bullish micro order block.
        
        Criteria:
        1. Strong bullish candle (close > open, body > threshold)
        2. Next candle is consolidation (small body)
        3. Price range within threshold
        """
        candle_open = candle.get('open', 0)
        candle_close = candle.get('close', 0)
        candle_high = candle.get('high', 0)
        candle_low = candle.get('low', 0)
        
        next_open = next_candle.get('open', 0)
        next_close = next_candle.get('close', 0)
        
        # Check if bullish candle
        if candle_close <= candle_open:
            return None
        
        # Calculate body sizes
        candle_body = candle_close - candle_open
        next_body = abs(next_close - next_open)
        
        # Strong bullish candle followed by consolidation
        if candle_body <= 0 or next_body >= candle_body * 0.5:
            return None
        
        # Check if body is strong enough (at least 2× next body)
        if candle_body < next_body * 2:
            return None
        
        # Calculate price range
        price_range = (min(candle_low, next_candle.get('low', candle_low)),
                      max(candle_high, next_candle.get('high', candle_high)))
        range_size = price_range[1] - price_range[0]
        
        # Check if range is within threshold
        min_range, max_range = range_threshold
        if range_size < min_range or range_size > max_range:
            return None
        
        # Calculate strength
        strength = min(1.0, candle_body / (next_body + 0.0001))
        
        return {
            'price_range': price_range,
            'strength': strength
        }
    
    def _check_bearish_ob(self, candle: Dict[str, Any], next_candle: Dict[str, Any],
                          range_threshold: Tuple[float, float]) -> Optional[Dict[str, Any]]:
        """
        Check if candle is a bearish micro order block.
        
        Criteria:
        1. Strong bearish candle (close < open, body > threshold)
        2. Next candle is consolidation (small body)
        3. Price range within threshold
        """
        candle_open = candle.get('open', 0)
        candle_close = candle.get('close', 0)
        candle_high = candle.get('high', 0)
        candle_low = candle.get('low', 0)
        
        next_open = next_candle.get('open', 0)
        next_close = next_candle.get('close', 0)
        
        # Check if bearish candle
        if candle_close >= candle_open:
            return None
        
        # Calculate body sizes
        candle_body = abs(candle_close - candle_open)
        next_body = abs(next_close - next_open)
        
        # Strong bearish candle followed by consolidation
        if candle_body <= 0 or next_body >= candle_body * 0.5:
            return None
        
        # Check if body is strong enough (at least 2× next body)
        if candle_body < next_body * 2:
            return None
        
        # Calculate price range
        price_range = (min(candle_low, next_candle.get('low', candle_low)),
                      max(candle_high, next_candle.get('high', candle_high)))
        range_size = price_range[1] - price_range[0]
        
        # Check if range is within threshold
        min_range, max_range = range_threshold
        if range_size < min_range or range_size > max_range:
            return None
        
        # Calculate strength
        strength = min(1.0, candle_body / (next_body + 0.0001))
        
        return {
            'price_range': price_range,
            'strength': strength
        }
    
    def validate_ob_retest(self, candles: List[Dict[str, Any]], 
                          ob_range: Tuple[float, float],
                          direction: str) -> bool:
        """
        Validate that price is retesting an order block zone.
        
        Args:
            candles: List of M1 candles (should include recent candles)
            ob_range: Order block price range (low, high)
            direction: "BULLISH" or "BEARISH"
        
        Returns:
            True if retest validated, False otherwise
        """
        if len(candles) == 0:
            return False
        
        last_candle = candles[-1]
        ob_low, ob_high = ob_range
        
        # Check if price is touching the OB zone
        price_touching = (last_candle.get('low', 0) <= ob_high and 
                         last_candle.get('high', 0) >= ob_low)
        
        if not price_touching:
            return False
        
        # For bullish OB, look for rejection wick or bullish confirmation
        if direction == "BULLISH":
            # Price should be near or above OB zone
            close = last_candle.get('close', 0)
            return close >= ob_low
        
        # For bearish OB, look for rejection wick or bearish confirmation
        else:  # BEARISH
            # Price should be near or below OB zone
            close = last_candle.get('close', 0)
            return close <= ob_high
    
    def _check_retest(self, current_price: float, ob_range: Tuple[float, float],
                     direction: str) -> bool:
        """
        Check if current price is retesting the order block.
        
        Args:
            current_price: Current market price
            ob_range: Order block price range (low, high)
            direction: "BULLISH" or "BEARISH"
        
        Returns:
            True if retesting, False otherwise
        """
        ob_low, ob_high = ob_range
        
        # Check if price is within OB zone
        if ob_low <= current_price <= ob_high:
            return True
        
        # For bullish OB, price approaching from below
        if direction == "BULLISH":
            return current_price >= ob_low * 0.999 and current_price <= ob_high * 1.001
        
        # For bearish OB, price approaching from above
        else:  # BEARISH
            return current_price <= ob_high * 1.001 and current_price >= ob_low * 0.999

