"""
Advanced delta proxy system for mid-price change and tick direction analysis.
Implements precision/recall validation against actual market moves.
"""

import numpy as np
import logging
from typing import Dict, Any, List, Optional, Tuple, NamedTuple
from dataclasses import dataclass, field
from enum import Enum
import time
from collections import deque

logger = logging.getLogger(__name__)

class TickDirection(Enum):
    """Tick direction classification."""
    UP = "up"
    DOWN = "down"
    SIDE = "side"

class DeltaStrength(Enum):
    """Delta strength classification."""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    EXTREME = "extreme"

@dataclass
class TickData:
    """Individual tick data structure."""
    timestamp_ms: int
    bid: float
    ask: float
    volume: float
    mid_price: float
    spread: float
    direction: TickDirection
    price_change: float
    volume_weighted_price: float

@dataclass
class DeltaMetrics:
    """Delta calculation metrics."""
    total_volume: float
    buy_volume: float
    sell_volume: float
    net_delta: float
    delta_ratio: float
    volume_imbalance: float
    price_momentum: float
    tick_velocity: float
    strength: DeltaStrength

@dataclass
class DeltaValidation:
    """Delta validation results."""
    precision: float
    recall: float
    f1_score: float
    true_positives: int
    false_positives: int
    false_negatives: int
    accuracy: float
    validation_timestamp_ms: int

@dataclass
class DeltaProxyConfig:
    """Configuration for delta proxy system."""
    # Tick analysis parameters
    min_tick_interval_ms: int = 100  # Minimum time between ticks to consider
    max_tick_interval_ms: int = 5000  # Maximum time between ticks
    price_change_threshold: float = 0.0001  # Minimum price change to register direction
    
    # Volume analysis parameters
    volume_spike_threshold: float = 2.0  # Volume spike multiplier
    volume_imbalance_threshold: float = 0.3  # Volume imbalance threshold
    
    # Delta calculation parameters
    delta_window_size: int = 100  # Number of ticks for delta calculation
    delta_smoothing_factor: float = 0.1  # Exponential smoothing factor
    
    # Validation parameters
    validation_window_size: int = 1000  # Ticks for validation
    validation_threshold: float = 0.7  # Minimum precision/recall threshold
    
    # Performance parameters
    max_buffer_size: int = 10000  # Maximum buffer size
    cleanup_interval_ms: int = 60000  # Cleanup interval

class AdvancedDeltaProxy:
    """
    Advanced delta proxy system for analyzing market momentum and volume flow.
    Provides precision/recall validation against actual market moves.
    """
    
    def __init__(self, symbol: str, config: DeltaProxyConfig = None):
        self.symbol = symbol
        self.config = config or DeltaProxyConfig()
        
        # Tick data buffers
        self.tick_buffer: deque = deque(maxlen=self.config.max_buffer_size)
        self.delta_history: deque = deque(maxlen=self.config.max_buffer_size)
        self.validation_history: deque = deque(maxlen=self.config.max_buffer_size)
        
        # State tracking
        self.last_tick: Optional[TickData] = None
        self.current_delta: Optional[DeltaMetrics] = None
        self.last_validation: Optional[DeltaValidation] = None
        
        # Performance metrics
        self.total_ticks_processed = 0
        self.delta_calculations = 0
        self.validations_performed = 0
        
        # Validation tracking
        self.true_positives = 0
        self.false_positives = 0
        self.false_negatives = 0
        
        logger.info(f"AdvancedDeltaProxy initialized for {symbol}")

    def process_tick(self, bid: float, ask: float, volume: float, timestamp_ms: int) -> Optional[DeltaMetrics]:
        """
        Process a new tick and calculate delta metrics.
        Returns delta metrics if significant change detected.
        """
        # Calculate mid-price and spread
        mid_price = (bid + ask) / 2.0
        spread = ask - bid
        
        # Determine tick direction
        direction = self._determine_tick_direction(mid_price, timestamp_ms)
        
        # Calculate price change
        price_change = 0.0
        if self.last_tick:
            price_change = mid_price - self.last_tick.mid_price
        
        # Create tick data
        tick_data = TickData(
            timestamp_ms=timestamp_ms,
            bid=bid,
            ask=ask,
            volume=volume,
            mid_price=mid_price,
            spread=spread,
            direction=direction,
            price_change=price_change,
            volume_weighted_price=mid_price * volume
        )
        
        # Add to buffer
        self.tick_buffer.append(tick_data)
        self.total_ticks_processed += 1
        
        # Calculate delta if we have enough data
        if len(self.tick_buffer) >= self.config.delta_window_size:
            delta_metrics = self._calculate_delta_metrics()
            if delta_metrics:
                self.current_delta = delta_metrics
                self.delta_history.append(delta_metrics)
                self.delta_calculations += 1
                
                # Perform validation if needed
                if len(self.tick_buffer) % self.config.validation_window_size == 0:
                    self._perform_validation()
                
                return delta_metrics
        
        # Update last tick
        self.last_tick = tick_data
        return None

    def _determine_tick_direction(self, mid_price: float, timestamp_ms: int) -> TickDirection:
        """Determine tick direction based on price movement."""
        if not self.last_tick:
            return TickDirection.SIDE
        
        # Check if enough time has passed
        time_diff = timestamp_ms - self.last_tick.timestamp_ms
        if time_diff < self.config.min_tick_interval_ms:
            return TickDirection.SIDE
        
        # Calculate price change
        price_change = mid_price - self.last_tick.mid_price
        
        # Determine direction based on threshold
        if abs(price_change) < self.config.price_change_threshold:
            return TickDirection.SIDE
        elif price_change > 0:
            return TickDirection.UP
        else:
            return TickDirection.DOWN

    def _calculate_delta_metrics(self) -> Optional[DeltaMetrics]:
        """Calculate delta metrics from recent ticks."""
        if len(self.tick_buffer) < self.config.delta_window_size:
            return None
        
        # Get recent ticks for analysis
        recent_ticks = list(self.tick_buffer)[-self.config.delta_window_size:]
        
        # Calculate volume metrics
        total_volume = sum(tick.volume for tick in recent_ticks)
        buy_volume = sum(tick.volume for tick in recent_ticks if tick.direction == TickDirection.UP)
        sell_volume = sum(tick.volume for tick in recent_ticks if tick.direction == TickDirection.DOWN)
        
        # Calculate net delta
        net_delta = buy_volume - sell_volume
        delta_ratio = net_delta / total_volume if total_volume > 0 else 0.0
        
        # Calculate volume imbalance
        volume_imbalance = abs(delta_ratio)
        
        # Calculate price momentum
        price_momentum = self._calculate_price_momentum(recent_ticks)
        
        # Calculate tick velocity
        tick_velocity = self._calculate_tick_velocity(recent_ticks)
        
        # Determine delta strength
        strength = self._classify_delta_strength(volume_imbalance, price_momentum, tick_velocity)
        
        return DeltaMetrics(
            total_volume=total_volume,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            net_delta=net_delta,
            delta_ratio=delta_ratio,
            volume_imbalance=volume_imbalance,
            price_momentum=price_momentum,
            tick_velocity=tick_velocity,
            strength=strength
        )

    def _calculate_price_momentum(self, ticks: List[TickData]) -> float:
        """Calculate price momentum from recent ticks."""
        if len(ticks) < 2:
            return 0.0
        
        # Calculate weighted price change
        total_weight = 0.0
        weighted_change = 0.0
        
        for i in range(1, len(ticks)):
            weight = ticks[i].volume
            price_change = ticks[i].mid_price - ticks[i-1].mid_price
            weighted_change += price_change * weight
            total_weight += weight
        
        return weighted_change / total_weight if total_weight > 0 else 0.0

    def _calculate_tick_velocity(self, ticks: List[TickData]) -> float:
        """Calculate tick velocity (ticks per second)."""
        if len(ticks) < 2:
            return 0.0
        
        time_span = (ticks[-1].timestamp_ms - ticks[0].timestamp_ms) / 1000.0
        return len(ticks) / time_span if time_span > 0 else 0.0

    def _classify_delta_strength(self, volume_imbalance: float, price_momentum: float, tick_velocity: float) -> DeltaStrength:
        """Classify delta strength based on multiple factors."""
        # Combine factors into a strength score
        strength_score = (
            volume_imbalance * 0.4 +
            abs(price_momentum) * 0.3 +
            min(tick_velocity / 10.0, 1.0) * 0.3
        )
        
        if strength_score < 0.2:
            return DeltaStrength.WEAK
        elif strength_score < 0.4:
            return DeltaStrength.MODERATE
        elif strength_score < 0.7:
            return DeltaStrength.STRONG
        else:
            return DeltaStrength.EXTREME

    def _perform_validation(self):
        """Perform precision/recall validation against actual market moves."""
        if len(self.tick_buffer) < self.config.validation_window_size:
            return
        
        # Get recent ticks for validation
        recent_ticks = list(self.tick_buffer)[-self.config.validation_window_size:]
        
        # Calculate actual market moves
        actual_moves = self._calculate_actual_moves(recent_ticks)
        
        # Calculate predicted moves from delta
        predicted_moves = self._calculate_predicted_moves(recent_ticks)
        
        # Calculate validation metrics
        validation = self._calculate_validation_metrics(actual_moves, predicted_moves)
        
        if validation:
            self.last_validation = validation
            self.validation_history.append(validation)
            self.validations_performed += 1
            
            # Update cumulative metrics
            self.true_positives += validation.true_positives
            self.false_positives += validation.false_positives
            self.false_negatives += validation.false_negatives

    def _calculate_actual_moves(self, ticks: List[TickData]) -> List[bool]:
        """Calculate actual market moves from tick data."""
        moves = []
        
        for i in range(1, len(ticks)):
            # Consider a move if price change exceeds threshold
            price_change = abs(ticks[i].mid_price - ticks[i-1].mid_price)
            is_move = price_change > self.config.price_change_threshold
            moves.append(is_move)
        
        return moves

    def _calculate_predicted_moves(self, ticks: List[TickData]) -> List[bool]:
        """Calculate predicted moves from delta analysis."""
        moves = []
        
        # Use delta metrics to predict moves
        for i in range(1, len(ticks)):
            # Predict move based on volume imbalance and price momentum
            volume_imbalance = abs(ticks[i].volume - ticks[i-1].volume) / max(ticks[i].volume, ticks[i-1].volume, 1.0)
            price_momentum = abs(ticks[i].mid_price - ticks[i-1].mid_price)
            
            # Predict move if both volume and price show significant change
            is_predicted_move = (volume_imbalance > self.config.volume_imbalance_threshold and 
                               price_momentum > self.config.price_change_threshold)
            moves.append(is_predicted_move)
        
        return moves

    def _calculate_validation_metrics(self, actual_moves: List[bool], predicted_moves: List[bool]) -> Optional[DeltaValidation]:
        """Calculate precision, recall, and F1 score."""
        if len(actual_moves) != len(predicted_moves) or len(actual_moves) == 0:
            return None
        
        # Calculate confusion matrix
        true_positives = sum(1 for a, p in zip(actual_moves, predicted_moves) if a and p)
        false_positives = sum(1 for a, p in zip(actual_moves, predicted_moves) if not a and p)
        false_negatives = sum(1 for a, p in zip(actual_moves, predicted_moves) if a and not p)
        
        # Calculate metrics
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (true_positives + (len(actual_moves) - true_positives - false_positives - false_negatives)) / len(actual_moves)
        
        return DeltaValidation(
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
            accuracy=accuracy,
            validation_timestamp_ms=int(time.time() * 1000)
        )

    def get_current_delta(self) -> Optional[DeltaMetrics]:
        """Get current delta metrics."""
        return self.current_delta

    def get_validation_metrics(self) -> Optional[DeltaValidation]:
        """Get latest validation metrics."""
        return self.last_validation

    def get_cumulative_validation_metrics(self) -> Dict[str, float]:
        """Get cumulative validation metrics."""
        total_predictions = self.true_positives + self.false_positives + self.false_negatives
        
        if total_predictions == 0:
            return {
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0,
                "accuracy": 0.0,
                "total_predictions": 0
            }
        
        precision = self.true_positives / (self.true_positives + self.false_positives) if (self.true_positives + self.false_positives) > 0 else 0.0
        recall = self.true_positives / (self.true_positives + self.false_negatives) if (self.true_positives + self.false_negatives) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (self.true_positives + (total_predictions - self.true_positives - self.false_positives - self.false_negatives)) / total_predictions
        
        return {
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "accuracy": accuracy,
            "total_predictions": total_predictions,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives
        }

    def get_delta_statistics(self) -> Dict[str, Any]:
        """Get comprehensive delta statistics."""
        stats = {
            "symbol": self.symbol,
            "total_ticks_processed": self.total_ticks_processed,
            "delta_calculations": self.delta_calculations,
            "validations_performed": self.validations_performed,
            "buffer_size": len(self.tick_buffer),
            "delta_history_size": len(self.delta_history),
            "validation_history_size": len(self.validation_history),
            "current_delta": self.current_delta.__dict__ if self.current_delta else None,
            "last_validation": self.last_validation.__dict__ if self.last_validation else None,
            "cumulative_metrics": self.get_cumulative_validation_metrics()
        }
        
        return stats

    def is_delta_spike(self, threshold: float = 0.5) -> bool:
        """Check if current delta indicates a spike."""
        if not self.current_delta:
            return False
        
        return (self.current_delta.volume_imbalance > threshold or 
                self.current_delta.strength in [DeltaStrength.STRONG, DeltaStrength.EXTREME])

    def get_delta_trend(self, window_size: int = 10) -> str:
        """Get delta trend over recent window."""
        if len(self.delta_history) < window_size:
            return "insufficient_data"
        
        recent_deltas = list(self.delta_history)[-window_size:]
        delta_ratios = [delta.delta_ratio for delta in recent_deltas]
        
        if len(delta_ratios) < 2:
            return "insufficient_data"
        
        # Calculate trend
        trend_slope = np.polyfit(range(len(delta_ratios)), delta_ratios, 1)[0]
        
        if trend_slope > 0.1:
            return "increasing"
        elif trend_slope < -0.1:
            return "decreasing"
        else:
            return "sideways"

    def cleanup_old_data(self):
        """Clean up old data to prevent memory bloat."""
        # This is handled by deque maxlen, but we can add additional cleanup logic here
        logger.info(f"Delta proxy cleanup completed for {self.symbol}")

# Example usage and testing
if __name__ == "__main__":
    # Test delta proxy
    config = DeltaProxyConfig(
        delta_window_size=50,
        validation_window_size=200
    )
    
    delta_proxy = AdvancedDeltaProxy("BTCUSDc", config)
    
    # Simulate some ticks
    import random
    base_price = 50000.0
    current_time = int(time.time() * 1000)
    
    for i in range(1000):
        # Simulate price movement
        price_change = random.uniform(-10, 10)
        bid = base_price + price_change
        ask = bid + random.uniform(0.5, 2.0)
        volume = random.uniform(0.1, 1.0)
        
        delta = delta_proxy.process_tick(bid, ask, volume, current_time)
        current_time += random.randint(100, 1000)
        
        if delta and i % 100 == 0:
            print(f"Delta at tick {i}: {delta.delta_ratio:.4f}, strength: {delta.strength.value}")
    
    # Print final statistics
    stats = delta_proxy.get_delta_statistics()
    print(f"Final statistics: {stats}")
