"""
Pattern Tracker Module
Tracks candlestick patterns and validates them across follow-up candles to confirm or invalidate patterns.

Tracks pattern state: Pending → Confirmed/Invalidated
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class PatternState:
    """State of a detected pattern"""
    pattern_type: str  # e.g., "Morning Star", "Bear Engulfing", "Hammer"
    timeframe: str  # M5, M15, M30, H1, H4
    symbol: str
    detection_time: datetime
    detection_price: float  # Close price when detected
    pattern_high: float  # High of pattern formation
    pattern_low: float  # Low of pattern formation
    strength_score: float  # 0.0-1.0
    bias: str  # "bullish", "bearish", "neutral"
    status: str  # "Pending", "Confirmed", "Invalidated"
    confirmation_time: Optional[datetime] = None
    invalidated_time: Optional[datetime] = None
    
    def __post_init__(self):
        if self.status not in ["Pending", "Confirmed", "Invalidated"]:
            self.status = "Pending"


class PatternTracker:
    """
    Tracks candlestick patterns and validates them across follow-up candles.
    
    Patterns are validated by checking if subsequent candles confirm or invalidate
    the expected direction.
    """
    
    def __init__(self, ttl_candles: int = 5):
        """
        Initialize pattern tracker.
        
        Args:
            ttl_candles: Number of candles to keep pattern state before expiring (default: 5)
        """
        self.patterns: Dict[str, PatternState] = {}  # key: (symbol, timeframe, pattern_type, timestamp)
        self.ttl_candles = ttl_candles
        self.logger = logging.getLogger(__name__)
    
    def _get_key(self, symbol: str, timeframe: str, pattern_type: str, detection_time: datetime) -> str:
        """Generate unique key for pattern"""
        return f"{symbol}_{timeframe}_{pattern_type}_{detection_time.timestamp()}"
    
    def register_pattern(
        self,
        symbol: str,
        timeframe: str,
        pattern_type: str,
        detection_price: float,
        pattern_high: float,
        pattern_low: float,
        strength_score: float,
        bias: str,
        detection_time: Optional[datetime] = None
    ) -> str:
        """
        Register a new pattern detection.
        
        Returns:
            Pattern key for later reference
        """
        if detection_time is None:
            detection_time = datetime.now(timezone.utc)
        
        pattern_state = PatternState(
            pattern_type=pattern_type,
            timeframe=timeframe,
            symbol=symbol,
            detection_time=detection_time,
            detection_price=detection_price,
            pattern_high=pattern_high,
            pattern_low=pattern_low,
            strength_score=strength_score,
            bias=bias,
            status="Pending"
        )
        
        key = self._get_key(symbol, timeframe, pattern_type, detection_time)
        self.patterns[key] = pattern_state
        
        self.logger.debug(f"Registered pattern: {pattern_type} on {symbol} {timeframe} (strength: {strength_score:.2f})")
        
        return key
    
    def validate_pattern(
        self,
        symbol: str,
        timeframe: str,
        current_candle: Dict[str, Any],
        candles_since_detection: int
    ) -> List[Tuple[str, str]]:
        """
        Validate all pending patterns for a symbol/timeframe against current candle.
        
        Args:
            symbol: Symbol to check
            timeframe: Timeframe to check
            current_candle: Latest candle dict with 'open', 'high', 'low', 'close'
            candles_since_detection: Number of candles that have formed since pattern was detected
        
        Returns:
            List of (pattern_key, status) tuples for updated patterns
        """
        updated_patterns = []
        
        # Find all pending patterns for this symbol/timeframe
        pattern_keys = [
            key for key, pattern in self.patterns.items()
            if pattern.symbol == symbol and 
            pattern.timeframe == timeframe and 
            pattern.status == "Pending"
        ]
        
        current_close = float(current_candle.get('close', 0))
        current_high = float(current_candle.get('high', 0))
        current_low = float(current_candle.get('low', 0))
        current_open = float(current_candle.get('open', 0))
        
        for key in pattern_keys:
            pattern = self.patterns[key]
            
            # Skip if too many candles have passed
            if candles_since_detection > self.ttl_candles:
                pattern.status = "Invalidated"
                pattern.invalidated_time = datetime.now(timezone.utc)
                updated_patterns.append((key, "Invalidated"))
                continue
            
            # Validate based on pattern bias
            is_confirmed = False
            is_invalidated = False
            
            if pattern.bias == "bullish":
                # Bullish patterns confirmed if price moves above pattern high
                # Invalidated if price moves below pattern low
                if current_close > pattern.pattern_high:
                    is_confirmed = True
                elif current_close < pattern.pattern_low:
                    is_invalidated = True
                # Also check if current candle closed above pattern high (stronger confirmation)
                if current_high > pattern.pattern_high and current_close > pattern.detection_price:
                    is_confirmed = True
            
            elif pattern.bias == "bearish":
                # Bearish patterns confirmed if price moves below pattern low
                # Invalidated if price moves above pattern high
                if current_close < pattern.pattern_low:
                    is_confirmed = True
                elif current_close > pattern.pattern_high:
                    is_invalidated = True
                # Also check if current candle closed below pattern low (stronger confirmation)
                if current_low < pattern.pattern_low and current_close < pattern.detection_price:
                    is_confirmed = True
            
            # Update pattern status
            if is_confirmed:
                pattern.status = "Confirmed"
                pattern.confirmation_time = datetime.now(timezone.utc)
                updated_patterns.append((key, "Confirmed"))
                self.logger.debug(f"Pattern CONFIRMED: {pattern.pattern_type} on {symbol} {timeframe}")
            
            elif is_invalidated:
                pattern.status = "Invalidated"
                pattern.invalidated_time = datetime.now(timezone.utc)
                updated_patterns.append((key, "Invalidated"))
                self.logger.debug(f"Pattern INVALIDATED: {pattern.pattern_type} on {symbol} {timeframe}")
        
        return updated_patterns
    
    def get_pattern_status(
        self,
        symbol: str,
        timeframe: str,
        pattern_type: str,
        detection_time: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Get status of a pattern (Pending/Confirmed/Invalidated).
        
        Returns:
            Status string or None if pattern not found
        """
        # Find pattern by symbol, timeframe, pattern_type
        # If detection_time provided, use exact match, otherwise get most recent
        matching_patterns = [
            p for key, p in self.patterns.items()
            if p.symbol == symbol and 
            p.timeframe == timeframe and 
            p.pattern_type == pattern_type
        ]
        
        if not matching_patterns:
            return None
        
        if detection_time:
            # Find exact match by time
            for pattern in matching_patterns:
                if abs((pattern.detection_time - detection_time).total_seconds()) < 300:  # 5 min tolerance
                    return pattern.status
        else:
            # Return most recent pattern status
            most_recent = max(matching_patterns, key=lambda p: p.detection_time)
            return most_recent.status
        
        return None
    
    def cleanup_old_patterns(self, max_age_hours: int = 24):
        """Remove patterns older than max_age_hours"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        
        keys_to_remove = [
            key for key, pattern in self.patterns.items()
            if pattern.detection_time < cutoff_time
        ]
        
        for key in keys_to_remove:
            del self.patterns[key]
        
        if keys_to_remove:
            self.logger.debug(f"Cleaned up {len(keys_to_remove)} old patterns")


# Global pattern tracker instance
_pattern_tracker: Optional[PatternTracker] = None


def get_pattern_tracker() -> PatternTracker:
    """Get global pattern tracker instance"""
    global _pattern_tracker
    if _pattern_tracker is None:
        _pattern_tracker = PatternTracker()
    return _pattern_tracker

