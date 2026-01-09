"""
Advanced ATR ratio system for M1 vs M5 ATR comparison.
Implements symbol-specific multipliers and volatility-based filtering.
"""

import numpy as np
import logging
from typing import Dict, Any, List, Optional, Tuple, NamedTuple
from dataclasses import dataclass, field
from enum import Enum
import time
from collections import deque
import threading

logger = logging.getLogger(__name__)

class ATRTimeframe(Enum):
    """ATR timeframe types."""
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    H1 = "H1"

class ATRRatioSignal(Enum):
    """ATR ratio signal types."""
    NORMAL = "normal"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    EXTREME_VOLATILITY = "extreme_volatility"
    VOLATILITY_SPIKE = "volatility_spike"
    VOLATILITY_DROP = "volatility_drop"

@dataclass
class ATRData:
    """ATR data structure for a specific timeframe."""
    timeframe: ATRTimeframe
    timestamp_ms: int
    atr_value: float
    atr_percentile: float
    is_valid: bool
    calculation_period: int
    raw_highs: List[float] = field(default_factory=list)
    raw_lows: List[float] = field(default_factory=list)
    raw_closes: List[float] = field(default_factory=list)

@dataclass
class ATRRatioMetrics:
    """ATR ratio calculation metrics."""
    m1_atr: float
    m5_atr: float
    atr_ratio: float
    normalized_ratio: float
    volatility_regime: ATRRatioSignal
    confidence_score: float
    timestamp_ms: int
    symbol: str

@dataclass
class SymbolATRConfig:
    """Symbol-specific ATR configuration."""
    symbol: str
    m1_atr_period: int = 14
    m5_atr_period: int = 14
    ratio_multiplier: float = 1.0
    high_volatility_threshold: float = 1.5
    low_volatility_threshold: float = 0.5
    extreme_volatility_threshold: float = 2.0
    spike_threshold: float = 2.5
    drop_threshold: float = 0.3
    smoothing_factor: float = 0.1
    min_data_points: int = 20

class AdvancedATRRatioSystem:
    """
    Advanced ATR ratio system for multi-timeframe volatility analysis.
    Compares M1 vs M5 ATR with symbol-specific multipliers and filtering.
    """
    
    def __init__(self, symbol: str, config: SymbolATRConfig = None):
        self.symbol = symbol
        self.config = config or SymbolATRConfig(symbol=symbol)
        
        # ATR data storage
        self.m1_atr_data: deque = deque(maxlen=1000)
        self.m5_atr_data: deque = deque(maxlen=1000)
        self.atr_ratio_history: deque = deque(maxlen=1000)
        
        # Raw price data for ATR calculation
        self.m1_highs: deque = deque(maxlen=self.config.m1_atr_period * 2)
        self.m1_lows: deque = deque(maxlen=self.config.m1_atr_period * 2)
        self.m1_closes: deque = deque(maxlen=self.config.m1_atr_period * 2)
        
        self.m5_highs: deque = deque(maxlen=self.config.m5_atr_period * 2)
        self.m5_lows: deque = deque(maxlen=self.config.m5_atr_period * 2)
        self.m5_closes: deque = deque(maxlen=self.config.m5_atr_period * 2)
        
        # State tracking
        self.current_m1_atr: Optional[ATRData] = None
        self.current_m5_atr: Optional[ATRData] = None
        self.current_ratio: Optional[ATRRatioMetrics] = None
        
        # Performance metrics
        self.calculations_performed = 0
        self.valid_signals = 0
        self.invalid_signals = 0
        
        # Thread safety
        self._lock = threading.RLock()
        
        logger.info(f"AdvancedATRRatioSystem initialized for {symbol}")

    def update_m1_data(self, high: float, low: float, close: float, timestamp_ms: int) -> Optional[ATRData]:
        """Update M1 data and calculate ATR."""
        with self._lock:
            # Add to M1 buffers
            self.m1_highs.append(high)
            self.m1_lows.append(low)
            self.m1_closes.append(close)
            
            # Calculate M1 ATR if we have enough data
            if len(self.m1_highs) >= self.config.m1_atr_period:
                atr_value = self._calculate_atr(
                    list(self.m1_highs),
                    list(self.m1_lows),
                    list(self.m1_closes),
                    self.config.m1_atr_period
                )
                
                if atr_value is not None:
                    # Calculate percentile
                    atr_percentile = self._calculate_atr_percentile(atr_value, self.m1_atr_data)
                    
                    # Create ATR data
                    atr_data = ATRData(
                        timeframe=ATRTimeframe.M1,
                        timestamp_ms=timestamp_ms,
                        atr_value=atr_value,
                        atr_percentile=atr_percentile,
                        is_valid=True,
                        calculation_period=self.config.m1_atr_period,
                        raw_highs=list(self.m1_highs),
                        raw_lows=list(self.m1_lows),
                        raw_closes=list(self.m1_closes)
                    )
                    
                    self.m1_atr_data.append(atr_data)
                    self.current_m1_atr = atr_data
                    
                    # Calculate ratio if we have M5 data
                    if self.current_m5_atr:
                        ratio_metrics = self._calculate_atr_ratio()
                        if ratio_metrics:
                            self.current_ratio = ratio_metrics
                            self.atr_ratio_history.append(ratio_metrics)
                            self.calculations_performed += 1
                            return ratio_metrics
                    
                    return atr_data
        
        return None

    def update_m5_data(self, high: float, low: float, close: float, timestamp_ms: int) -> Optional[ATRData]:
        """Update M5 data and calculate ATR."""
        with self._lock:
            # Add to M5 buffers
            self.m5_highs.append(high)
            self.m5_lows.append(low)
            self.m5_closes.append(close)
            
            # Calculate M5 ATR if we have enough data
            if len(self.m5_highs) >= self.config.m5_atr_period:
                atr_value = self._calculate_atr(
                    list(self.m5_highs),
                    list(self.m5_lows),
                    list(self.m5_closes),
                    self.config.m5_atr_period
                )
                
                if atr_value is not None:
                    # Calculate percentile
                    atr_percentile = self._calculate_atr_percentile(atr_value, self.m5_atr_data)
                    
                    # Create ATR data
                    atr_data = ATRData(
                        timeframe=ATRTimeframe.M5,
                        timestamp_ms=timestamp_ms,
                        atr_value=atr_value,
                        atr_percentile=atr_percentile,
                        is_valid=True,
                        calculation_period=self.config.m5_atr_period,
                        raw_highs=list(self.m5_highs),
                        raw_lows=list(self.m5_lows),
                        raw_closes=list(self.m5_closes)
                    )
                    
                    self.m5_atr_data.append(atr_data)
                    self.current_m5_atr = atr_data
                    
                    # Calculate ratio if we have M1 data
                    if self.current_m1_atr:
                        ratio_metrics = self._calculate_atr_ratio()
                        if ratio_metrics:
                            self.current_ratio = ratio_metrics
                            self.atr_ratio_history.append(ratio_metrics)
                            self.calculations_performed += 1
                            return ratio_metrics
                    
                    return atr_data
        
        return None

    def _calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int) -> Optional[float]:
        """Calculate ATR using the standard formula."""
        if len(highs) < period or len(lows) < period or len(closes) < period:
            return None
        
        # Get the last 'period' values
        recent_highs = highs[-period:]
        recent_lows = lows[-period:]
        recent_closes = closes[-period:]
        
        # Calculate True Range for each period
        true_ranges = []
        
        for i in range(1, len(recent_highs)):
            # True Range = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr1 = recent_highs[i] - recent_lows[i]
            tr2 = abs(recent_highs[i] - recent_closes[i-1])
            tr3 = abs(recent_lows[i] - recent_closes[i-1])
            
            true_range = max(tr1, tr2, tr3)
            true_ranges.append(true_range)
        
        # Calculate ATR as the average of True Ranges
        if true_ranges:
            return sum(true_ranges) / len(true_ranges)
        
        return None

    def _calculate_atr_percentile(self, current_atr: float, atr_history: deque) -> float:
        """Calculate percentile of current ATR relative to history."""
        if len(atr_history) < 2:
            return 50.0  # Default to median if no history
        
        atr_values = [atr.atr_value for atr in atr_history]
        atr_values.append(current_atr)
        
        # Calculate percentile
        sorted_values = sorted(atr_values)
        position = sorted_values.index(current_atr)
        percentile = (position / len(sorted_values)) * 100
        
        return percentile

    def _calculate_atr_ratio(self) -> Optional[ATRRatioMetrics]:
        """Calculate ATR ratio between M1 and M5."""
        if not self.current_m1_atr or not self.current_m5_atr:
            return None
        
        m1_atr = self.current_m1_atr.atr_value
        m5_atr = self.current_m5_atr.atr_value
        
        if m5_atr == 0:
            return None
        
        # Calculate raw ratio
        raw_ratio = m1_atr / m5_atr
        
        # Apply symbol-specific multiplier
        adjusted_ratio = raw_ratio * self.config.ratio_multiplier
        
        # Normalize ratio (0-1 scale)
        normalized_ratio = min(adjusted_ratio / 2.0, 1.0)  # Cap at 1.0
        
        # Determine volatility regime
        volatility_regime = self._classify_volatility_regime(adjusted_ratio)
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(m1_atr, m5_atr, adjusted_ratio)
        
        return ATRRatioMetrics(
            m1_atr=m1_atr,
            m5_atr=m5_atr,
            atr_ratio=raw_ratio,
            normalized_ratio=normalized_ratio,
            volatility_regime=volatility_regime,
            confidence_score=confidence_score,
            timestamp_ms=max(self.current_m1_atr.timestamp_ms, self.current_m5_atr.timestamp_ms),
            symbol=self.symbol
        )

    def _classify_volatility_regime(self, ratio: float) -> ATRRatioSignal:
        """Classify volatility regime based on ATR ratio."""
        if ratio >= self.config.spike_threshold:
            return ATRRatioSignal.VOLATILITY_SPIKE
        elif ratio >= self.config.extreme_volatility_threshold:
            return ATRRatioSignal.EXTREME_VOLATILITY
        elif ratio >= self.config.high_volatility_threshold:
            return ATRRatioSignal.HIGH_VOLATILITY
        elif ratio <= self.config.drop_threshold:
            return ATRRatioSignal.VOLATILITY_DROP
        elif ratio <= self.config.low_volatility_threshold:
            return ATRRatioSignal.LOW_VOLATILITY
        else:
            return ATRRatioSignal.NORMAL

    def _calculate_confidence_score(self, m1_atr: float, m5_atr: float, ratio: float) -> float:
        """Calculate confidence score for the ATR ratio."""
        # Base confidence on data quality and ratio stability
        base_confidence = 0.5
        
        # Increase confidence if both ATRs are reasonable
        if 0.001 < m1_atr < 1.0 and 0.001 < m5_atr < 1.0:
            base_confidence += 0.2
        
        # Increase confidence if ratio is in reasonable range
        if 0.1 < ratio < 10.0:
            base_confidence += 0.2
        
        # Increase confidence based on data history
        history_confidence = min(len(self.atr_ratio_history) / 100.0, 0.1)
        base_confidence += history_confidence
        
        return min(base_confidence, 1.0)

    def get_current_ratio(self) -> Optional[ATRRatioMetrics]:
        """Get current ATR ratio metrics."""
        return self.current_ratio

    def get_volatility_regime(self) -> Optional[ATRRatioSignal]:
        """Get current volatility regime."""
        if self.current_ratio:
            return self.current_ratio.volatility_regime
        return None

    def is_high_volatility(self) -> bool:
        """Check if current regime is high volatility."""
        regime = self.get_volatility_regime()
        return regime in [ATRRatioSignal.HIGH_VOLATILITY, ATRRatioSignal.EXTREME_VOLATILITY, ATRRatioSignal.VOLATILITY_SPIKE]

    def is_low_volatility(self) -> bool:
        """Check if current regime is low volatility."""
        regime = self.get_volatility_regime()
        return regime in [ATRRatioSignal.LOW_VOLATILITY, ATRRatioSignal.VOLATILITY_DROP]

    def is_volatility_spike(self) -> bool:
        """Check if current regime is a volatility spike."""
        regime = self.get_volatility_regime()
        return regime == ATRRatioSignal.VOLATILITY_SPIKE

    def get_ratio_trend(self, window_size: int = 10) -> str:
        """Get ATR ratio trend over recent window."""
        if len(self.atr_ratio_history) < window_size:
            return "insufficient_data"
        
        recent_ratios = list(self.atr_ratio_history)[-window_size:]
        ratio_values = [ratio.atr_ratio for ratio in recent_ratios]
        
        if len(ratio_values) < 2:
            return "insufficient_data"
        
        # Calculate trend slope
        trend_slope = np.polyfit(range(len(ratio_values)), ratio_values, 1)[0]
        
        if trend_slope > 0.1:
            return "increasing"
        elif trend_slope < -0.1:
            return "decreasing"
        else:
            return "sideways"

    def get_atr_statistics(self) -> Dict[str, Any]:
        """Get comprehensive ATR statistics."""
        stats = {
            "symbol": self.symbol,
            "config": {
                "m1_atr_period": self.config.m1_atr_period,
                "m5_atr_period": self.config.m5_atr_period,
                "ratio_multiplier": self.config.ratio_multiplier,
                "high_volatility_threshold": self.config.high_volatility_threshold,
                "low_volatility_threshold": self.config.low_volatility_threshold
            },
            "data_counts": {
                "m1_atr_data": len(self.m1_atr_data),
                "m5_atr_data": len(self.m5_atr_data),
                "ratio_history": len(self.atr_ratio_history)
            },
            "performance": {
                "calculations_performed": self.calculations_performed,
                "valid_signals": self.valid_signals,
                "invalid_signals": self.invalid_signals
            },
            "current_state": {
                "m1_atr": self.current_m1_atr.__dict__ if self.current_m1_atr else None,
                "m5_atr": self.current_m5_atr.__dict__ if self.current_m5_atr else None,
                "current_ratio": self.current_ratio.__dict__ if self.current_ratio else None
            }
        }
        
        return stats

    def get_volatility_distribution(self) -> Dict[str, int]:
        """Get distribution of volatility regimes."""
        if not self.atr_ratio_history:
            return {}
        
        distribution = {}
        for ratio in self.atr_ratio_history:
            regime = ratio.volatility_regime.value
            distribution[regime] = distribution.get(regime, 0) + 1
        
        return distribution

    def validate_atr_ratio(self, expected_range: Tuple[float, float] = (0.1, 5.0)) -> bool:
        """Validate that ATR ratio is within expected range."""
        if not self.current_ratio:
            return False
        
        ratio = self.current_ratio.atr_ratio
        return expected_range[0] <= ratio <= expected_range[1]

    def get_confidence_level(self) -> str:
        """Get confidence level based on current metrics."""
        if not self.current_ratio:
            return "no_data"
        
        confidence = self.current_ratio.confidence_score
        
        if confidence >= 0.8:
            return "high"
        elif confidence >= 0.6:
            return "medium"
        elif confidence >= 0.4:
            return "low"
        else:
            return "very_low"

    def cleanup_old_data(self, max_age_hours: int = 24):
        """Clean up old data to prevent memory bloat."""
        current_time = int(time.time() * 1000)
        cutoff_time = current_time - (max_age_hours * 3600 * 1000)
        
        # Clean up M1 data
        while self.m1_atr_data and self.m1_atr_data[0].timestamp_ms < cutoff_time:
            self.m1_atr_data.popleft()
        
        # Clean up M5 data
        while self.m5_atr_data and self.m5_atr_data[0].timestamp_ms < cutoff_time:
            self.m5_atr_data.popleft()
        
        # Clean up ratio history
        while self.atr_ratio_history and self.atr_ratio_history[0].timestamp_ms < cutoff_time:
            self.atr_ratio_history.popleft()
        
        logger.info(f"ATR ratio system cleanup completed for {self.symbol}")

# Example usage and testing
if __name__ == "__main__":
    # Test ATR ratio system
    config = SymbolATRConfig(
        symbol="BTCUSDc",
        ratio_multiplier=1.2,
        high_volatility_threshold=1.8,
        low_volatility_threshold=0.4
    )
    
    atr_system = AdvancedATRRatioSystem("BTCUSDc", config)
    
    # Simulate some M1 and M5 data
    import random
    base_price = 50000.0
    current_time = int(time.time() * 1000)
    
    # Simulate M1 data
    for i in range(100):
        price_change = random.uniform(-50, 50)
        high = base_price + abs(price_change) + random.uniform(0, 20)
        low = base_price - abs(price_change) - random.uniform(0, 20)
        close = base_price + price_change
        
        m1_atr = atr_system.update_m1_data(high, low, close, current_time + i * 60000)  # 1 minute intervals
        if m1_atr and i % 10 == 0:
            print(f"M1 ATR at {i}: {m1_atr.atr_value:.4f}")
    
    # Simulate M5 data
    for i in range(20):
        price_change = random.uniform(-100, 100)
        high = base_price + abs(price_change) + random.uniform(0, 50)
        low = base_price - abs(price_change) - random.uniform(0, 50)
        close = base_price + price_change
        
        m5_atr = atr_system.update_m5_data(high, low, close, current_time + i * 300000)  # 5 minute intervals
        if m5_atr and i % 5 == 0:
            print(f"M5 ATR at {i}: {m5_atr.atr_value:.4f}")
    
    # Print final statistics
    stats = atr_system.get_atr_statistics()
    print(f"ATR Ratio Statistics: {stats}")
    
    if atr_system.current_ratio:
        print(f"Current ratio: {atr_system.current_ratio.atr_ratio:.4f}")
        print(f"Volatility regime: {atr_system.current_ratio.volatility_regime.value}")
        print(f"Confidence: {atr_system.get_confidence_level()}")
