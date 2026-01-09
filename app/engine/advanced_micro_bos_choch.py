"""
Advanced micro-BOS/CHOCH detection system.
Implements bar-count lookback, ATR displacement thresholds, and cooldown periods.
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

class StructureType(Enum):
    """Market structure types."""
    BOS = "bos"  # Break of Structure
    CHOCH = "choch"  # Change of Character
    MICRO_BOS = "micro_bos"
    MICRO_CHOCH = "micro_choch"

class StructureDirection(Enum):
    """Structure direction."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"

class StructureStrength(Enum):
    """Structure strength classification."""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    EXTREME = "extreme"

@dataclass
class BarData:
    """Bar data structure."""
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str
    is_valid: bool = True

@dataclass
class StructureBreak:
    """Structure break detection result."""
    structure_type: StructureType
    direction: StructureDirection
    strength: StructureStrength
    timestamp_ms: int
    price_level: float
    displacement: float
    atr_ratio: float
    bar_count: int
    confidence_score: float
    is_micro: bool
    cooldown_remaining_ms: int

@dataclass
class MicroBOSConfig:
    """Configuration for micro-BOS/CHOCH detection."""
    symbol: str
    bar_lookback: int = 20  # Number of bars to look back
    min_atr_displacement: float = 0.25  # Minimum ATR displacement (0.25-0.5x)
    max_atr_displacement: float = 0.5   # Maximum ATR displacement
    cooldown_period_ms: int = 300000   # 5 minutes cooldown
    min_volume_threshold: float = 1.0   # Minimum volume threshold
    strength_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "weak": 0.25,
        "moderate": 0.35,
        "strong": 0.45,
        "extreme": 0.55
    })
    confidence_factors: Dict[str, float] = field(default_factory=lambda: {
        "volume_weight": 0.3,
        "displacement_weight": 0.4,
        "time_weight": 0.3
    })

class AdvancedMicroBOSCHOCH:
    """
    Advanced micro-BOS/CHOCH detection system.
    Detects small market structure breaks with ATR displacement and cooldown management.
    """
    
    def __init__(self, symbol: str, config: MicroBOSConfig = None):
        self.symbol = symbol
        self.config = config or MicroBOSConfig(symbol=symbol)
        
        # Bar data storage
        self.bar_buffer: deque = deque(maxlen=self.config.bar_lookback * 2)
        self.structure_history: deque = deque(maxlen=1000)
        
        # ATR data for displacement calculation
        self.atr_period = 14
        self.atr_values: deque = deque(maxlen=self.atr_period * 2)
        
        # State tracking
        self.last_structure_break: Optional[StructureBreak] = None
        self.current_trend: StructureDirection = StructureDirection.NEUTRAL
        self.last_break_time_ms: int = 0
        
        # Performance metrics
        self.total_breaks_detected = 0
        self.micro_breaks_detected = 0
        self.valid_breaks = 0
        self.false_breaks = 0
        
        # Thread safety
        self._lock = threading.RLock()
        
        logger.info(f"AdvancedMicroBOSCHOCH initialized for {symbol}")

    def update_bar(self, bar: BarData) -> Optional[StructureBreak]:
        """
        Update with new bar data and detect structure breaks.
        Returns structure break if detected.
        """
        with self._lock:
            # Add bar to buffer
            self.bar_buffer.append(bar)
            
            # Update ATR if we have enough data
            if len(self.bar_buffer) >= self.atr_period:
                atr_value = self._calculate_atr()
                if atr_value is not None:
                    self.atr_values.append(atr_value)
            
            # Check for structure breaks if we have enough data
            if len(self.bar_buffer) >= self.config.bar_lookback:
                structure_break = self._detect_structure_break(bar)
                if structure_break:
                    self._process_structure_break(structure_break)
                    return structure_break
        
        return None

    def _calculate_atr(self) -> Optional[float]:
        """Calculate ATR from recent bars."""
        if len(self.bar_buffer) < self.atr_period:
            return None
        
        recent_bars = list(self.bar_buffer)[-self.atr_period:]
        true_ranges = []
        
        for i in range(1, len(recent_bars)):
            high = recent_bars[i].high
            low = recent_bars[i].low
            prev_close = recent_bars[i-1].close
            
            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)
            
            true_range = max(tr1, tr2, tr3)
            true_ranges.append(true_range)
        
        return sum(true_ranges) / len(true_ranges) if true_ranges else None

    def _detect_structure_break(self, current_bar: BarData) -> Optional[StructureBreak]:
        """Detect structure breaks in the current bar."""
        # Check cooldown period
        if self._is_in_cooldown():
            return None
        
        # Get recent bars for analysis
        recent_bars = list(self.bar_buffer)[-self.config.bar_lookback:]
        
        # Detect BOS (Break of Structure)
        bos_break = self._detect_bos(recent_bars, current_bar)
        if bos_break:
            return bos_break
        
        # Detect CHOCH (Change of Character)
        choch_break = self._detect_choch(recent_bars, current_bar)
        if choch_break:
            return choch_break
        
        return None

    def _detect_bos(self, bars: List[BarData], current_bar: BarData) -> Optional[StructureBreak]:
        """Detect Break of Structure."""
        if len(bars) < 5:
            return None
        
        # Find recent swing high/low
        swing_high = max(bar.high for bar in bars[-10:])
        swing_low = min(bar.low for bar in bars[-10:])
        
        # Check for bullish BOS (break above swing high)
        if current_bar.close > swing_high:
            displacement = current_bar.close - swing_high
            return self._create_structure_break(
                StructureType.BOS,
                StructureDirection.BULLISH,
                displacement,
                current_bar
            )
        
        # Check for bearish BOS (break below swing low)
        elif current_bar.close < swing_low:
            displacement = swing_low - current_bar.close
            return self._create_structure_break(
                StructureType.BOS,
                StructureDirection.BEARISH,
                displacement,
                current_bar
            )
        
        return None

    def _detect_choch(self, bars: List[BarData], current_bar: BarData) -> Optional[StructureBreak]:
        """Detect Change of Character."""
        if len(bars) < 10:
            return None
        
        # Analyze trend change
        recent_trend = self._analyze_trend(bars[-10:])
        current_trend = self._analyze_trend([bars[-1], current_bar])
        
        # Check for trend change
        if recent_trend != current_trend and current_trend != StructureDirection.NEUTRAL:
            displacement = abs(current_bar.close - bars[-1].close)
            return self._create_structure_break(
                StructureType.CHOCH,
                current_trend,
                displacement,
                current_bar
            )
        
        return None

    def _analyze_trend(self, bars: List[BarData]) -> StructureDirection:
        """Analyze trend direction from bars."""
        if len(bars) < 2:
            return StructureDirection.NEUTRAL
        
        # Simple trend analysis based on closes
        closes = [bar.close for bar in bars]
        if len(closes) < 3:
            return StructureDirection.NEUTRAL
        
        # Check if trend is clearly up or down
        if closes[-1] > closes[0] and all(closes[i] >= closes[i-1] for i in range(1, len(closes))):
            return StructureDirection.BULLISH
        elif closes[-1] < closes[0] and all(closes[i] <= closes[i-1] for i in range(1, len(closes))):
            return StructureDirection.BEARISH
        else:
            return StructureDirection.NEUTRAL

    def _create_structure_break(self, structure_type: StructureType, direction: StructureDirection, 
                              displacement: float, current_bar: BarData) -> Optional[StructureBreak]:
        """Create structure break object."""
        # Get current ATR
        current_atr = self.atr_values[-1] if self.atr_values else 0.001
        
        # Calculate ATR ratio
        atr_ratio = displacement / current_atr if current_atr > 0 else 0
        
        # Check if displacement meets minimum threshold
        if atr_ratio < self.config.min_atr_displacement:
            return None
        
        # Determine if it's a micro break
        is_micro = atr_ratio < self.config.max_atr_displacement
        
        # Determine structure type
        if is_micro:
            structure_type = StructureType.MICRO_BOS if structure_type == StructureType.BOS else StructureType.MICRO_CHOCH
        
        # Calculate strength
        strength = self._calculate_strength(atr_ratio, current_bar.volume)
        
        # Calculate confidence score
        confidence = self._calculate_confidence(atr_ratio, current_bar.volume, current_bar.timestamp_ms)
        
        return StructureBreak(
            structure_type=structure_type,
            direction=direction,
            strength=strength,
            timestamp_ms=current_bar.timestamp_ms,
            price_level=current_bar.close,
            displacement=displacement,
            atr_ratio=atr_ratio,
            bar_count=len(self.bar_buffer),
            confidence_score=confidence,
            is_micro=is_micro,
            cooldown_remaining_ms=self.config.cooldown_period_ms
        )

    def _calculate_strength(self, atr_ratio: float, volume: float) -> StructureStrength:
        """Calculate structure strength."""
        # Combine ATR ratio and volume factors
        strength_score = atr_ratio * 0.7 + min(volume / 10.0, 1.0) * 0.3
        
        if strength_score >= self.config.strength_thresholds["extreme"]:
            return StructureStrength.EXTREME
        elif strength_score >= self.config.strength_thresholds["strong"]:
            return StructureStrength.STRONG
        elif strength_score >= self.config.strength_thresholds["moderate"]:
            return StructureStrength.MODERATE
        else:
            return StructureStrength.WEAK

    def _calculate_confidence(self, atr_ratio: float, volume: float, timestamp_ms: int) -> float:
        """Calculate confidence score for the structure break."""
        # Volume confidence
        volume_confidence = min(volume / self.config.min_volume_threshold, 1.0)
        
        # Displacement confidence
        displacement_confidence = min(atr_ratio / self.config.max_atr_displacement, 1.0)
        
        # Time confidence (recent breaks are less confident)
        time_since_last = timestamp_ms - self.last_break_time_ms
        time_confidence = min(time_since_last / (self.config.cooldown_period_ms * 2), 1.0)
        
        # Weighted combination
        confidence = (
            volume_confidence * self.config.confidence_factors["volume_weight"] +
            displacement_confidence * self.config.confidence_factors["displacement_weight"] +
            time_confidence * self.config.confidence_factors["time_weight"]
        )
        
        return min(confidence, 1.0)

    def _process_structure_break(self, structure_break: StructureBreak):
        """Process a detected structure break."""
        # Update state
        self.last_structure_break = structure_break
        self.last_break_time_ms = structure_break.timestamp_ms
        self.current_trend = structure_break.direction
        
        # Add to history
        self.structure_history.append(structure_break)
        
        # Update metrics
        self.total_breaks_detected += 1
        if structure_break.is_micro:
            self.micro_breaks_detected += 1
        
        # Validate break (simplified validation)
        if structure_break.confidence_score > 0.5:
            self.valid_breaks += 1
        else:
            self.false_breaks += 1
        
        logger.info(f"Structure break detected: {structure_break.structure_type.value} "
                   f"{structure_break.direction.value} at {structure_break.price_level:.4f}")

    def _is_in_cooldown(self) -> bool:
        """Check if system is in cooldown period."""
        if self.last_break_time_ms == 0:
            return False
        
        current_time = int(time.time() * 1000)
        time_since_last = current_time - self.last_break_time_ms
        
        return time_since_last < self.config.cooldown_period_ms

    def get_current_trend(self) -> StructureDirection:
        """Get current market trend."""
        return self.current_trend

    def get_last_structure_break(self) -> Optional[StructureBreak]:
        """Get the last detected structure break."""
        return self.last_structure_break

    def get_structure_statistics(self) -> Dict[str, Any]:
        """Get comprehensive structure detection statistics."""
        stats = {
            "symbol": self.symbol,
            "config": {
                "bar_lookback": self.config.bar_lookback,
                "min_atr_displacement": self.config.min_atr_displacement,
                "max_atr_displacement": self.config.max_atr_displacement,
                "cooldown_period_ms": self.config.cooldown_period_ms
            },
            "data_counts": {
                "bar_buffer_size": len(self.bar_buffer),
                "structure_history_size": len(self.structure_history),
                "atr_values_size": len(self.atr_values)
            },
            "performance": {
                "total_breaks_detected": self.total_breaks_detected,
                "micro_breaks_detected": self.micro_breaks_detected,
                "valid_breaks": self.valid_breaks,
                "false_breaks": self.false_breaks
            },
            "current_state": {
                "current_trend": self.current_trend.value,
                "last_break": self.last_structure_break.__dict__ if self.last_structure_break else None,
                "in_cooldown": self._is_in_cooldown()
            }
        }
        
        return stats

    def get_structure_distribution(self) -> Dict[str, int]:
        """Get distribution of structure types."""
        if not self.structure_history:
            return {}
        
        distribution = {}
        for break_event in self.structure_history:
            structure_type = break_event.structure_type.value
            distribution[structure_type] = distribution.get(structure_type, 0) + 1
        
        return distribution

    def get_recent_breaks(self, count: int = 10) -> List[StructureBreak]:
        """Get recent structure breaks."""
        return list(self.structure_history)[-count:] if self.structure_history else []

    def is_trend_bullish(self) -> bool:
        """Check if current trend is bullish."""
        return self.current_trend == StructureDirection.BULLISH

    def is_trend_bearish(self) -> bool:
        """Check if current trend is bearish."""
        return self.current_trend == StructureDirection.BEARISH

    def get_cooldown_remaining(self) -> int:
        """Get remaining cooldown time in milliseconds."""
        if not self._is_in_cooldown():
            return 0
        
        current_time = int(time.time() * 1000)
        return max(0, self.config.cooldown_period_ms - (current_time - self.last_break_time_ms))

    def validate_structure_break(self, break_event: StructureBreak) -> bool:
        """Validate a structure break."""
        # Basic validation checks
        if break_event.atr_ratio < self.config.min_atr_displacement:
            return False
        
        if break_event.confidence_score < 0.3:
            return False
        
        if break_event.displacement <= 0:
            return False
        
        return True

    def cleanup_old_data(self, max_age_hours: int = 24):
        """Clean up old data to prevent memory bloat."""
        current_time = int(time.time() * 1000)
        cutoff_time = current_time - (max_age_hours * 3600 * 1000)
        
        # Clean up structure history
        while self.structure_history and self.structure_history[0].timestamp_ms < cutoff_time:
            self.structure_history.popleft()
        
        logger.info(f"Micro-BOS/CHOCH cleanup completed for {self.symbol}")

# Example usage and testing
if __name__ == "__main__":
    # Test micro-BOS/CHOCH system
    config = MicroBOSConfig(
        symbol="BTCUSDc",
        bar_lookback=15,
        min_atr_displacement=0.3,
        max_atr_displacement=0.6,
        cooldown_period_ms=300000  # 5 minutes
    )
    
    micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc", config)
    
    # Simulate some bars
    import random
    base_price = 50000.0
    current_time = int(time.time() * 1000)
    
    for i in range(100):
        # Simulate price movement
        price_change = random.uniform(-100, 100)
        high = base_price + abs(price_change) + random.uniform(0, 50)
        low = base_price - abs(price_change) - random.uniform(0, 50)
        close = base_price + price_change
        volume = random.uniform(0.5, 5.0)
        
        bar = BarData(
            timestamp_ms=current_time + i * 60000,  # 1 minute bars
            open=base_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
            timeframe="M1"
        )
        
        structure_break = micro_bos.update_bar(bar)
        if structure_break:
            print(f"Structure break at {i}: {structure_break.structure_type.value} "
                  f"{structure_break.direction.value}, strength: {structure_break.strength.value}")
        
        base_price = close  # Update base price for next bar
    
    # Print final statistics
    stats = micro_bos.get_structure_statistics()
    print(f"Structure Statistics: {stats}")
