"""
Test suite for advanced delta proxy system.
Tests mid-price change analysis, tick direction detection, and precision/recall validation.
"""

import pytest
import time
import numpy as np
from unittest.mock import patch, MagicMock

# Add the project root to the path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.engine.advanced_delta_proxy import (
    AdvancedDeltaProxy,
    DeltaProxyConfig,
    TickDirection,
    DeltaStrength,
    TickData,
    DeltaMetrics,
    DeltaValidation
)

class TestTickDirection:
    """Test TickDirection enum."""
    
    def test_tick_direction_values(self):
        """Test tick direction enum values."""
        assert TickDirection.UP.value == "up"
        assert TickDirection.DOWN.value == "down"
        assert TickDirection.SIDE.value == "side"

class TestDeltaStrength:
    """Test DeltaStrength enum."""
    
    def test_delta_strength_values(self):
        """Test delta strength enum values."""
        assert DeltaStrength.WEAK.value == "weak"
        assert DeltaStrength.MODERATE.value == "moderate"
        assert DeltaStrength.STRONG.value == "strong"
        assert DeltaStrength.EXTREME.value == "extreme"

class TestDeltaProxyConfig:
    """Test DeltaProxyConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = DeltaProxyConfig()
        
        assert config.min_tick_interval_ms == 100
        assert config.max_tick_interval_ms == 5000
        assert config.price_change_threshold == 0.0001
        assert config.volume_spike_threshold == 2.0
        assert config.volume_imbalance_threshold == 0.3
        assert config.delta_window_size == 100
        assert config.delta_smoothing_factor == 0.1
        assert config.validation_window_size == 1000
        assert config.validation_threshold == 0.7
        assert config.max_buffer_size == 10000
        assert config.cleanup_interval_ms == 60000

    def test_custom_config(self):
        """Test custom configuration values."""
        config = DeltaProxyConfig(
            min_tick_interval_ms=50,
            price_change_threshold=0.0005,
            delta_window_size=50,
            validation_window_size=500
        )
        
        assert config.min_tick_interval_ms == 50
        assert config.price_change_threshold == 0.0005
        assert config.delta_window_size == 50
        assert config.validation_window_size == 500

class TestTickData:
    """Test TickData dataclass."""
    
    def test_tick_data_creation(self):
        """Test tick data creation."""
        tick_data = TickData(
            timestamp_ms=1234567890,
            bid=1.1000,
            ask=1.1002,
            volume=1000.0,
            mid_price=1.1001,
            spread=0.0002,
            direction=TickDirection.UP,
            price_change=0.0001,
            volume_weighted_price=1100.1
        )
        
        assert tick_data.timestamp_ms == 1234567890
        assert tick_data.bid == 1.1000
        assert tick_data.ask == 1.1002
        assert tick_data.volume == 1000.0
        assert tick_data.mid_price == 1.1001
        assert tick_data.spread == 0.0002
        assert tick_data.direction == TickDirection.UP
        assert tick_data.price_change == 0.0001
        assert tick_data.volume_weighted_price == 1100.1

class TestDeltaMetrics:
    """Test DeltaMetrics dataclass."""
    
    def test_delta_metrics_creation(self):
        """Test delta metrics creation."""
        metrics = DeltaMetrics(
            total_volume=10000.0,
            buy_volume=6000.0,
            sell_volume=4000.0,
            net_delta=2000.0,
            delta_ratio=0.2,
            volume_imbalance=0.2,
            price_momentum=0.001,
            tick_velocity=5.0,
            strength=DeltaStrength.MODERATE
        )
        
        assert metrics.total_volume == 10000.0
        assert metrics.buy_volume == 6000.0
        assert metrics.sell_volume == 4000.0
        assert metrics.net_delta == 2000.0
        assert metrics.delta_ratio == 0.2
        assert metrics.volume_imbalance == 0.2
        assert metrics.price_momentum == 0.001
        assert metrics.tick_velocity == 5.0
        assert metrics.strength == DeltaStrength.MODERATE

class TestAdvancedDeltaProxy:
    """Test AdvancedDeltaProxy class."""
    
    def test_initialization(self):
        """Test delta proxy initialization."""
        config = DeltaProxyConfig(delta_window_size=50)
        delta_proxy = AdvancedDeltaProxy("BTCUSDc", config)
        
        assert delta_proxy.symbol == "BTCUSDc"
        assert delta_proxy.config == config
        assert delta_proxy.last_tick is None
        assert delta_proxy.current_delta is None
        assert delta_proxy.last_validation is None
        assert delta_proxy.total_ticks_processed == 0
        assert delta_proxy.delta_calculations == 0
        assert delta_proxy.validations_performed == 0

    def test_initialization_default_config(self):
        """Test initialization with default config."""
        delta_proxy = AdvancedDeltaProxy("EURUSDc")
        
        assert delta_proxy.symbol == "EURUSDc"
        assert isinstance(delta_proxy.config, DeltaProxyConfig)
        assert delta_proxy.config.delta_window_size == 100

    def test_process_tick_insufficient_data(self):
        """Test processing tick with insufficient data."""
        delta_proxy = AdvancedDeltaProxy("BTCUSDc")
        
        # Process single tick
        delta = delta_proxy.process_tick(50000.0, 50002.0, 0.1, int(time.time() * 1000))
        
        assert delta is None  # Not enough data for delta calculation
        assert delta_proxy.total_ticks_processed == 1
        assert delta_proxy.last_tick is not None

    def test_process_tick_sufficient_data(self):
        """Test processing tick with sufficient data."""
        config = DeltaProxyConfig(delta_window_size=5)
        delta_proxy = AdvancedDeltaProxy("BTCUSDc", config)
        
        current_time = int(time.time() * 1000)
        
        # Process enough ticks to trigger delta calculation
        for i in range(10):
            bid = 50000.0 + i * 10.0
            ask = bid + 2.0
            volume = 0.1 + i * 0.01
            delta = delta_proxy.process_tick(bid, ask, volume, current_time + i * 1000)
            
            if i >= 4:  # After 5th tick, should start calculating delta
                assert delta is not None
                assert isinstance(delta, DeltaMetrics)
                assert delta.total_volume > 0
                assert delta.buy_volume >= 0
                assert delta.sell_volume >= 0
                assert isinstance(delta.strength, DeltaStrength)

    def test_determine_tick_direction(self):
        """Test tick direction determination."""
        delta_proxy = AdvancedDeltaProxy("BTCUSDc")
        
        # First tick should be SIDE
        direction = delta_proxy._determine_tick_direction(50000.0, int(time.time() * 1000))
        assert direction == TickDirection.SIDE
        
        # Set up last tick
        delta_proxy.last_tick = TickData(
            timestamp_ms=int(time.time() * 1000) - 200,
            bid=49999.0,
            ask=50001.0,
            volume=0.1,
            mid_price=50000.0,
            spread=2.0,
            direction=TickDirection.SIDE,
            price_change=0.0,
            volume_weighted_price=5000.0
        )
        
        # Test different directions
        current_time = int(time.time() * 1000)
        
        # Up direction
        direction = delta_proxy._determine_tick_direction(50010.0, current_time)
        assert direction == TickDirection.UP
        
        # Down direction
        direction = delta_proxy._determine_tick_direction(49990.0, current_time + 100)
        assert direction == TickDirection.DOWN
        
        # Side direction (small change)
        direction = delta_proxy._determine_tick_direction(50000.00001, current_time + 200)
        assert direction == TickDirection.SIDE

    def test_calculate_delta_metrics(self):
        """Test delta metrics calculation."""
        config = DeltaProxyConfig(delta_window_size=5)
        delta_proxy = AdvancedDeltaProxy("BTCUSDc", config)
        
        # Add some test ticks
        current_time = int(time.time() * 1000)
        for i in range(10):
            bid = 50000.0 + i * 5.0
            ask = bid + 2.0
            volume = 0.1 + i * 0.01
            direction = TickDirection.UP if i % 2 == 0 else TickDirection.DOWN
            
            tick_data = TickData(
                timestamp_ms=current_time + i * 1000,
                bid=bid,
                ask=ask,
                volume=volume,
                mid_price=(bid + ask) / 2.0,
                spread=2.0,
                direction=direction,
                price_change=5.0 if i > 0 else 0.0,
                volume_weighted_price=(bid + ask) / 2.0 * volume
            )
            delta_proxy.tick_buffer.append(tick_data)
        
        # Calculate delta metrics
        delta_metrics = delta_proxy._calculate_delta_metrics()
        
        assert delta_metrics is not None
        assert delta_metrics.total_volume > 0
        assert delta_metrics.buy_volume >= 0
        assert delta_metrics.sell_volume >= 0
        assert isinstance(delta_metrics.strength, DeltaStrength)

    def test_calculate_price_momentum(self):
        """Test price momentum calculation."""
        delta_proxy = AdvancedDeltaProxy("BTCUSDc")
        
        # Create test ticks with known price changes
        ticks = []
        base_price = 50000.0
        for i in range(5):
            price = base_price + i * 10.0
            tick_data = TickData(
                timestamp_ms=int(time.time() * 1000) + i * 1000,
                bid=price,
                ask=price + 2.0,
                volume=0.1 + i * 0.01,
                mid_price=price + 1.0,
                spread=2.0,
                direction=TickDirection.UP,
                price_change=10.0 if i > 0 else 0.0,
                volume_weighted_price=(price + 1.0) * (0.1 + i * 0.01)
            )
            ticks.append(tick_data)
        
        momentum = delta_proxy._calculate_price_momentum(ticks)
        assert isinstance(momentum, float)

    def test_calculate_tick_velocity(self):
        """Test tick velocity calculation."""
        delta_proxy = AdvancedDeltaProxy("BTCUSDc")
        
        # Create test ticks with known time intervals
        ticks = []
        base_time = int(time.time() * 1000)
        for i in range(5):
            tick_data = TickData(
                timestamp_ms=base_time + i * 1000,  # 1 second intervals
                bid=50000.0,
                ask=50002.0,
                volume=0.1,
                mid_price=50001.0,
                spread=2.0,
                direction=TickDirection.UP,
                price_change=0.0,
                volume_weighted_price=5000.1
            )
            ticks.append(tick_data)
        
        velocity = delta_proxy._calculate_tick_velocity(ticks)
        assert velocity > 0
        assert velocity <= 5.0  # Should be around 1 tick per second

    def test_classify_delta_strength(self):
        """Test delta strength classification."""
        delta_proxy = AdvancedDeltaProxy("BTCUSDc")
        
        # Test different strength levels
        test_cases = [
            (0.1, 0.1, 1.0, DeltaStrength.WEAK),
            (0.3, 0.2, 3.0, DeltaStrength.MODERATE),
            (0.5, 0.4, 5.0, DeltaStrength.STRONG),
            (0.8, 0.6, 8.0, DeltaStrength.EXTREME)
        ]
        
        for volume_imbalance, price_momentum, tick_velocity, expected_strength in test_cases:
            strength = delta_proxy._classify_delta_strength(volume_imbalance, price_momentum, tick_velocity)
            assert strength == expected_strength

    def test_get_current_delta(self):
        """Test getting current delta."""
        delta_proxy = AdvancedDeltaProxy("BTCUSDc")
        
        # No delta yet
        assert delta_proxy.get_current_delta() is None
        
        # Set a delta
        delta_metrics = DeltaMetrics(
            total_volume=1000.0,
            buy_volume=600.0,
            sell_volume=400.0,
            net_delta=200.0,
            delta_ratio=0.2,
            volume_imbalance=0.2,
            price_momentum=0.001,
            tick_velocity=5.0,
            strength=DeltaStrength.MODERATE
        )
        delta_proxy.current_delta = delta_metrics
        
        current_delta = delta_proxy.get_current_delta()
        assert current_delta == delta_metrics

    def test_is_delta_spike(self):
        """Test delta spike detection."""
        delta_proxy = AdvancedDeltaProxy("BTCUSDc")
        
        # No delta
        assert delta_proxy.is_delta_spike() is False
        
        # Weak delta
        weak_delta = DeltaMetrics(
            total_volume=1000.0,
            buy_volume=550.0,
            sell_volume=450.0,
            net_delta=100.0,
            delta_ratio=0.1,
            volume_imbalance=0.1,
            price_momentum=0.001,
            tick_velocity=2.0,
            strength=DeltaStrength.WEAK
        )
        delta_proxy.current_delta = weak_delta
        assert delta_proxy.is_delta_spike() is False
        
        # Strong delta
        strong_delta = DeltaMetrics(
            total_volume=1000.0,
            buy_volume=800.0,
            sell_volume=200.0,
            net_delta=600.0,
            delta_ratio=0.6,
            volume_imbalance=0.6,
            price_momentum=0.01,
            tick_velocity=8.0,
            strength=DeltaStrength.STRONG
        )
        delta_proxy.current_delta = strong_delta
        assert delta_proxy.is_delta_spike() is True

    def test_get_delta_trend(self):
        """Test delta trend calculation."""
        delta_proxy = AdvancedDeltaProxy("BTCUSDc")
        
        # No data
        trend = delta_proxy.get_delta_trend()
        assert trend == "insufficient_data"
        
        # Add some delta history
        for i in range(15):
            delta_metrics = DeltaMetrics(
                total_volume=1000.0,
                buy_volume=500.0 + i * 10.0,
                sell_volume=500.0 - i * 10.0,
                net_delta=i * 20.0,
                delta_ratio=i * 0.02,
                volume_imbalance=abs(i * 0.02),
                price_momentum=i * 0.001,
                tick_velocity=5.0,
                strength=DeltaStrength.MODERATE
            )
            delta_proxy.delta_history.append(delta_metrics)
        
        trend = delta_proxy.get_delta_trend()
        assert trend in ["increasing", "decreasing", "sideways"]

    def test_get_delta_statistics(self):
        """Test getting delta statistics."""
        delta_proxy = AdvancedDeltaProxy("BTCUSDc")
        
        # Process some ticks
        current_time = int(time.time() * 1000)
        for i in range(10):
            delta_proxy.process_tick(50000.0 + i, 50002.0 + i, 0.1, current_time + i * 1000)
        
        stats = delta_proxy.get_delta_statistics()
        
        assert "symbol" in stats
        assert "total_ticks_processed" in stats
        assert "delta_calculations" in stats
        assert "validations_performed" in stats
        assert "buffer_size" in stats
        assert "delta_history_size" in stats
        assert "validation_history_size" in stats
        assert "current_delta" in stats
        assert "last_validation" in stats
        assert "cumulative_metrics" in stats
        
        assert stats["symbol"] == "BTCUSDc"
        assert stats["total_ticks_processed"] >= 10

    def test_validation_metrics_calculation(self):
        """Test validation metrics calculation."""
        delta_proxy = AdvancedDeltaProxy("BTCUSDc")
        
        # Test validation calculation
        actual_moves = [True, False, True, True, False]
        predicted_moves = [True, True, True, False, False]
        
        validation = delta_proxy._calculate_validation_metrics(actual_moves, predicted_moves)
        
        assert validation is not None
        assert validation.true_positives >= 0
        assert validation.false_positives >= 0
        assert validation.false_negatives >= 0
        assert 0.0 <= validation.precision <= 1.0
        assert 0.0 <= validation.recall <= 1.0
        assert 0.0 <= validation.f1_score <= 1.0
        assert 0.0 <= validation.accuracy <= 1.0

    def test_get_cumulative_validation_metrics(self):
        """Test cumulative validation metrics."""
        delta_proxy = AdvancedDeltaProxy("BTCUSDc")
        
        # Set some validation metrics
        delta_proxy.true_positives = 50
        delta_proxy.false_positives = 20
        delta_proxy.false_negatives = 30
        
        metrics = delta_proxy.get_cumulative_validation_metrics()
        
        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1_score" in metrics
        assert "accuracy" in metrics
        assert "total_predictions" in metrics
        assert "true_positives" in metrics
        assert "false_positives" in metrics
        assert "false_negatives" in metrics
        
        assert metrics["true_positives"] == 50
        assert metrics["false_positives"] == 20
        assert metrics["false_negatives"] == 30

class TestIntegration:
    """Integration tests for delta proxy system."""
    
    def test_full_delta_analysis_workflow(self):
        """Test complete delta analysis workflow."""
        config = DeltaProxyConfig(
            delta_window_size=10,
            validation_window_size=50
        )
        delta_proxy = AdvancedDeltaProxy("BTCUSDc", config)
        
        # Simulate realistic tick data
        current_time = int(time.time() * 1000)
        base_price = 50000.0
        
        for i in range(100):
            # Simulate price movement with some trend
            price_change = np.sin(i * 0.1) * 10.0 + np.random.normal(0, 2.0)
            bid = base_price + price_change
            ask = bid + np.random.uniform(1.0, 3.0)
            volume = np.random.uniform(0.05, 0.5)
            
            delta = delta_proxy.process_tick(bid, ask, volume, current_time + i * 100)
            
            if i % 20 == 0 and delta:
                print(f"Delta at tick {i}: ratio={delta.delta_ratio:.4f}, strength={delta.strength.value}")
        
        # Check final statistics
        stats = delta_proxy.get_delta_statistics()
        assert stats["total_ticks_processed"] == 100
        assert stats["delta_calculations"] > 0
        
        # Check if we have validation data
        if stats["validations_performed"] > 0:
            cumulative_metrics = stats["cumulative_metrics"]
            assert "precision" in cumulative_metrics
            assert "recall" in cumulative_metrics
            assert "f1_score" in cumulative_metrics

    def test_delta_spike_detection(self):
        """Test delta spike detection with realistic data."""
        config = DeltaProxyConfig(
            delta_window_size=20,
            volume_imbalance_threshold=0.3
        )
        delta_proxy = AdvancedDeltaProxy("BTCUSDc", config)
        
        current_time = int(time.time() * 1000)
        base_price = 50000.0
        
        # Normal trading
        for i in range(50):
            price_change = np.random.normal(0, 1.0)
            bid = base_price + price_change
            ask = bid + 2.0
            volume = np.random.uniform(0.1, 0.3)
            delta_proxy.process_tick(bid, ask, volume, current_time + i * 100)
        
        # Simulate a volume spike
        for i in range(10):
            price_change = 5.0 if i < 5 else -5.0  # Strong directional movement
            bid = base_price + price_change
            ask = bid + 2.0
            volume = 2.0  # High volume
            delta = delta_proxy.process_tick(bid, ask, volume, current_time + (50 + i) * 100)
            
            if delta and delta_proxy.is_delta_spike():
                print(f"Delta spike detected at tick {50 + i}: {delta.strength.value}")
                break

    def test_precision_recall_validation(self):
        """Test precision/recall validation with known patterns."""
        config = DeltaProxyConfig(
            delta_window_size=5,
            validation_window_size=20
        )
        delta_proxy = AdvancedDeltaProxy("BTCUSDc", config)
        
        current_time = int(time.time() * 1000)
        base_price = 50000.0
        
        # Create a pattern that should be predictable
        for i in range(100):
            if i % 10 < 5:
                # Strong upward movement with high volume
                price_change = 5.0
                volume = 1.0
            else:
                # Weak movement with low volume
                price_change = 0.5
                volume = 0.1
            
            bid = base_price + price_change
            ask = bid + 2.0
            delta_proxy.process_tick(bid, ask, volume, current_time + i * 100)
        
        # Check validation metrics
        cumulative_metrics = delta_proxy.get_cumulative_validation_metrics()
        if cumulative_metrics["total_predictions"] > 0:
            assert cumulative_metrics["precision"] >= 0.0
            assert cumulative_metrics["recall"] >= 0.0
            assert cumulative_metrics["f1_score"] >= 0.0

if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
