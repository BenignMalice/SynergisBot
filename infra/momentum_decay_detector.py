"""
Phase III: Momentum Decay Detection Module
Tracks RSI/MACD over time and detects divergence patterns
"""

import logging
import threading
from typing import Dict, Optional, Any, List
from datetime import datetime, timezone, timedelta
from collections import deque

logger = logging.getLogger(__name__)


class MomentumDecayDetector:
    """
    Phase III: Detects momentum decay patterns for entry conditions.
    
    Patterns detected:
    - RSI divergence from price
    - MACD divergence from price
    - Tick rate decline
    - Momentum decay confirmation (composite)
    """
    
    def __init__(self, cache_ttl_seconds: int = 120):
        """
        Initialize momentum decay detector.
        
        Args:
            cache_ttl_seconds: Cache TTL in seconds (default: 120 = 2 minutes)
        """
        self.cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}  # key -> {result, timestamp}
        self._lock = threading.RLock()  # Thread safety for cache access
        
        # Store momentum history per symbol
        self._momentum_history: Dict[str, deque] = {}  # symbol -> deque of {rsi, macd, price, timestamp}
        self._tick_rate_history: Dict[str, deque] = {}  # symbol -> deque of {rate, timestamp}
        
        logger.info("Phase III: MomentumDecayDetector initialized")
    
    def _get_cache_key(self, symbol: str, pattern_type: str) -> str:
        """Generate cache key"""
        return f"{symbol}_{pattern_type}"
    
    def _get_cached(self, cache_key: str) -> Optional[Any]:
        """Get cached result if still valid"""
        with self._lock:
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
        with self._lock:
            self._cache[cache_key] = (result, datetime.now(timezone.utc))
            # Limit cache size
            if len(self._cache) > 100:
                oldest_key = min(self._cache.keys(),
                               key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]
    
    def _update_momentum_history(
        self,
        symbol: str,
        rsi: float,
        macd: float,
        price: float
    ):
        """Update momentum history for a symbol"""
        with self._lock:
            if symbol not in self._momentum_history:
                self._momentum_history[symbol] = deque(maxlen=50)  # Store last 50 periods
            
            self._momentum_history[symbol].append({
                "rsi": rsi,
                "macd": macd,
                "price": price,
                "timestamp": datetime.now(timezone.utc)
            })
    
    def _update_tick_rate_history(self, symbol: str, tick_rate: float):
        """Update tick rate history for a symbol"""
        with self._lock:
            if symbol not in self._tick_rate_history:
                self._tick_rate_history[symbol] = deque(maxlen=20)  # Store last 20 readings (5-10 minutes)
            
            self._tick_rate_history[symbol].append({
                "rate": tick_rate,
                "timestamp": datetime.now(timezone.utc)
            })
    
    def detect_rsi_divergence(
        self,
        symbol: str,
        current_rsi: float,
        current_price: float,
        lookback_periods: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Detect RSI divergence from price.
        
        Args:
            symbol: Trading symbol
            current_rsi: Current RSI value
            current_price: Current price
            lookback_periods: Number of periods to look back (default: 20)
        
        Returns:
            {
                "rsi_divergence_detected": bool,
                "divergence_type": "bullish" | "bearish" | None,
                "strength": float  # 0-1
            } or None
        """
        try:
            with self._lock:
                if symbol not in self._momentum_history or len(self._momentum_history[symbol]) < lookback_periods:
                    return None
                
                history = list(self._momentum_history[symbol])
                if len(history) < lookback_periods:
                    return None
                
                # Get price and RSI trends
                recent_history = history[-lookback_periods:]
                prices = [h["price"] for h in recent_history]
                rsis = [h["rsi"] for h in recent_history]
                
                # Calculate trends (simple linear regression slope)
                n = len(prices)
                x = list(range(n))
                
                # Price trend
                price_slope = (n * sum(x[i] * prices[i] for i in range(n)) - sum(x) * sum(prices)) / (n * sum(x[i]**2 for i in range(n)) - sum(x)**2) if n > 1 else 0
                
                # RSI trend
                rsi_slope = (n * sum(x[i] * rsis[i] for i in range(n)) - sum(x) * sum(rsis)) / (n * sum(x[i]**2 for i in range(n)) - sum(x)**2) if n > 1 else 0
                
                # Detect divergence: price and RSI moving in opposite directions
                divergence_detected = False
                divergence_type = None
                
                if price_slope > 0 and rsi_slope < -0.1:  # Price rising, RSI falling (bearish divergence)
                    divergence_detected = True
                    divergence_type = "bearish"
                elif price_slope < 0 and rsi_slope > 0.1:  # Price falling, RSI rising (bullish divergence)
                    divergence_detected = True
                    divergence_type = "bullish"
                
                # Calculate strength (magnitude of divergence)
                strength = abs(price_slope * rsi_slope) if divergence_detected else 0.0
                strength = min(1.0, strength * 10)  # Normalize to 0-1
                
                return {
                    "rsi_divergence_detected": divergence_detected,
                    "divergence_type": divergence_type,
                    "strength": strength
                }
        except Exception as e:
            logger.error(f"Error detecting RSI divergence for {symbol}: {e}", exc_info=True)
            return None
    
    def detect_macd_divergence(
        self,
        symbol: str,
        current_macd: float,
        current_price: float,
        lookback_periods: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Detect MACD divergence from price.
        
        Args:
            symbol: Trading symbol
            current_macd: Current MACD value
            current_price: Current price
            lookback_periods: Number of periods to look back (default: 20)
        
        Returns:
            {
                "macd_divergence_detected": bool,
                "divergence_type": "bullish" | "bearish" | None,
                "strength": float  # 0-1
            } or None
        """
        try:
            with self._lock:
                if symbol not in self._momentum_history or len(self._momentum_history[symbol]) < lookback_periods:
                    return None
                
                history = list(self._momentum_history[symbol])
                if len(history) < lookback_periods:
                    return None
                
                # Get price and MACD trends
                recent_history = history[-lookback_periods:]
                prices = [h["price"] for h in recent_history]
                macds = [h["macd"] for h in recent_history]
                
                # Calculate trends
                n = len(prices)
                x = list(range(n))
                
                # Price trend
                price_slope = (n * sum(x[i] * prices[i] for i in range(n)) - sum(x) * sum(prices)) / (n * sum(x[i]**2 for i in range(n)) - sum(x)**2) if n > 1 else 0
                
                # MACD trend
                macd_slope = (n * sum(x[i] * macds[i] for i in range(n)) - sum(x) * sum(macds)) / (n * sum(x[i]**2 for i in range(n)) - sum(x)**2) if n > 1 else 0
                
                # Detect divergence
                divergence_detected = False
                divergence_type = None
                
                if price_slope > 0 and macd_slope < -0.01:  # Price rising, MACD falling (bearish divergence)
                    divergence_detected = True
                    divergence_type = "bearish"
                elif price_slope < 0 and macd_slope > 0.01:  # Price falling, MACD rising (bullish divergence)
                    divergence_detected = True
                    divergence_type = "bullish"
                
                # Calculate strength
                strength = abs(price_slope * macd_slope) if divergence_detected else 0.0
                strength = min(1.0, strength * 100)  # Normalize to 0-1
                
                return {
                    "macd_divergence_detected": divergence_detected,
                    "divergence_type": divergence_type,
                    "strength": strength
                }
        except Exception as e:
            logger.error(f"Error detecting MACD divergence for {symbol}: {e}", exc_info=True)
            return None
    
    def detect_tick_rate_decline(
        self,
        symbol: str,
        current_tick_rate: float,
        decline_threshold: float = 0.20,
        window_minutes: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Detect tick rate decline.
        
        Args:
            symbol: Trading symbol
            current_tick_rate: Current tick rate
            decline_threshold: Decline threshold (default: 0.20 = 20%)
            window_minutes: Time window in minutes (default: 5)
        
        Returns:
            {
                "tick_rate_declining": bool,
                "decline_pct": float,
                "current_rate": float,
                "average_rate": float
            } or None
        """
        try:
            with self._lock:
                if symbol not in self._tick_rate_history or len(self._tick_rate_history[symbol]) < 5:
                    return None
                
                history = list(self._tick_rate_history[symbol])
                
                # Filter to window
                now = datetime.now(timezone.utc)
                window_start = now - timedelta(minutes=window_minutes)
                recent_history = [h for h in history if h["timestamp"] >= window_start]
                
                if len(recent_history) < 3:
                    return None
                
                # Calculate average rate
                rates = [h["rate"] for h in recent_history]
                average_rate = sum(rates) / len(rates) if rates else 0
                
                if average_rate == 0:
                    return None
                
                # Calculate decline percentage
                decline_pct = (average_rate - current_tick_rate) / average_rate if average_rate > 0 else 0
                tick_rate_declining = decline_pct >= decline_threshold
                
                return {
                    "tick_rate_declining": tick_rate_declining,
                    "decline_pct": decline_pct,
                    "current_rate": current_tick_rate,
                    "average_rate": average_rate
                }
        except Exception as e:
            logger.error(f"Error detecting tick rate decline for {symbol}: {e}", exc_info=True)
            return None
    
    def detect_momentum_decay(
        self,
        symbol: str,
        current_rsi: float,
        current_macd: float,
        current_price: float,
        current_tick_rate: float
    ) -> Optional[Dict[str, Any]]:
        """
        Detect momentum decay confirmation (composite check).
        
        Pattern: RSI/MACD divergence detected AND tick rate declines >20% for >5 minutes.
        
        Args:
            symbol: Trading symbol
            current_rsi: Current RSI value
            current_macd: Current MACD value
            current_price: Current price
            current_tick_rate: Current tick rate
        
        Returns:
            {
                "momentum_decay_confirmed": bool,
                "rsi_divergence": bool,
                "macd_divergence": bool,
                "tick_rate_declining": bool
            } or None
        """
        try:
            # Update history first
            self._update_momentum_history(symbol, current_rsi, current_macd, current_price)
            self._update_tick_rate_history(symbol, current_tick_rate)
            
            # Check RSI divergence
            rsi_result = self.detect_rsi_divergence(symbol, current_rsi, current_price)
            rsi_divergence = rsi_result.get("rsi_divergence_detected", False) if rsi_result else False
            
            # Check MACD divergence
            macd_result = self.detect_macd_divergence(symbol, current_macd, current_price)
            macd_divergence = macd_result.get("macd_divergence_detected", False) if macd_result else False
            
            # Check tick rate decline
            tick_result = self.detect_tick_rate_decline(symbol, current_tick_rate)
            tick_declining = tick_result.get("tick_rate_declining", False) if tick_result else False
            
            # Confirm momentum decay: divergence AND tick rate decline
            momentum_decay_confirmed = (rsi_divergence or macd_divergence) and tick_declining
            
            return {
                "momentum_decay_confirmed": momentum_decay_confirmed,
                "rsi_divergence": rsi_divergence,
                "macd_divergence": macd_divergence,
                "tick_rate_declining": tick_declining
            }
        except Exception as e:
            logger.error(f"Error detecting momentum decay for {symbol}: {e}", exc_info=True)
            return None

