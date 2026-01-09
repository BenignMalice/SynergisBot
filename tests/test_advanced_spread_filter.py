"""
Test suite for advanced spread filter system.
Tests rolling median, outlier detection, news window exclusion, and spread classification.
"""

import pytest
import time
import numpy as np
from unittest.mock import patch, MagicMock

# Add the project root to the path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.engine.advanced_spread_filter import (
    AdvancedSpreadFilter,
    SpreadFilterConfig,
    SpreadFilterSignal,
    NewsEventType,
    NewsEvent,
    SpreadData
)

class TestSpreadFilterSignal:
    """Test SpreadFilterSignal enum."""
    
    def test_spread_filter_signal_values(self):
        """Test spread filter signal enum values."""
        assert SpreadFilterSignal.NORMAL.value == "normal"
        assert SpreadFilterSignal.ELEVATED.value == "elevated"
        assert SpreadFilterSignal.HIGH.value == "high"
        assert SpreadFilterSignal.EXTREME.value == "extreme"
        assert SpreadFilterSignal.NEWS_WINDOW.value == "news_window"
        assert SpreadFilterSignal.OUTLIER.value == "outlier"

class TestNewsEventType:
    """Test NewsEventType enum."""
    
    def test_news_event_type_values(self):
        """Test news event type enum values."""
        assert NewsEventType.NFP.value == "nfp"
        assert NewsEventType.FOMC.value == "fomc"
        assert NewsEventType.ECB.value == "ecb"
        assert NewsEventType.BOE.value == "boe"
        assert NewsEventType.CPI.value == "cpi"
        assert NewsEventType.GDP.value == "gdp"
        assert NewsEventType.OTHER.value == "other"

class TestNewsEvent:
    """Test NewsEvent dataclass."""
    
    def test_news_event_creation(self):
        """Test news event creation."""
        news_event = NewsEvent(
            event_type=NewsEventType.NFP,
            timestamp_ms=1234567890,
            impact_level="high",
            currency="USD",
            description="Non-Farm Payrolls",
            exclusion_window_minutes=30
        )
        
        assert news_event.event_type == NewsEventType.NFP
        assert news_event.timestamp_ms == 1234567890
        assert news_event.impact_level == "high"
        assert news_event.currency == "USD"
        assert news_event.description == "Non-Farm Payrolls"
        assert news_event.exclusion_window_minutes == 30

class TestSpreadData:
    """Test SpreadData dataclass."""
    
    def test_spread_data_creation(self):
        """Test spread data creation."""
        spread_data = SpreadData(
            timestamp_ms=1234567890,
            bid=1.1000,
            ask=1.1005,
            spread=0.0005,
            spread_pips=5.0,
            source="mt5",
            is_valid=True
        )
        
        assert spread_data.timestamp_ms == 1234567890
        assert spread_data.bid == 1.1000
        assert spread_data.ask == 1.1005
        assert spread_data.spread == 0.0005
        assert spread_data.spread_pips == 5.0
        assert spread_data.source == "mt5"
        assert spread_data.is_valid is True

class TestSpreadFilterConfig:
    """Test SpreadFilterConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = SpreadFilterConfig(symbol="EURUSDc")
        
        assert config.symbol == "EURUSDc"
        assert config.window_size == 20
        assert config.outlier_threshold == 2.5
        assert config.normal_spread_threshold == 1.5
        assert config.elevated_spread_threshold == 3.0
        assert config.high_spread_threshold == 5.0
        assert config.extreme_spread_threshold == 10.0
        assert config.news_exclusion_enabled is True
        assert config.outlier_clipping_enabled is True
        assert config.min_data_points == 10
        assert config.pip_value == 0.0001
        assert config.crypto_pip_multiplier == 1.0

    def test_custom_config(self):
        """Test custom configuration values."""
        config = SpreadFilterConfig(
            symbol="BTCUSDc",
            window_size=15,
            outlier_threshold=3.0,
            normal_spread_threshold=2.0,
            elevated_spread_threshold=4.0,
            high_spread_threshold=6.0,
            extreme_spread_threshold=12.0,
            news_exclusion_enabled=False,
            outlier_clipping_enabled=False,
            min_data_points=5,
            pip_value=0.01,
            crypto_pip_multiplier=2.0
        )
        
        assert config.symbol == "BTCUSDc"
        assert config.window_size == 15
        assert config.outlier_threshold == 3.0
        assert config.normal_spread_threshold == 2.0
        assert config.elevated_spread_threshold == 4.0
        assert config.high_spread_threshold == 6.0
        assert config.extreme_spread_threshold == 12.0
        assert config.news_exclusion_enabled is False
        assert config.outlier_clipping_enabled is False
        assert config.min_data_points == 5
        assert config.pip_value == 0.01
        assert config.crypto_pip_multiplier == 2.0

class TestAdvancedSpreadFilter:
    """Test AdvancedSpreadFilter class."""
    
    def test_initialization(self):
        """Test spread filter initialization."""
        config = SpreadFilterConfig(symbol="EURUSDc")
        spread_filter = AdvancedSpreadFilter("EURUSDc", config)
        
        assert spread_filter.symbol == "EURUSDc"
        assert spread_filter.config == config
        assert spread_filter.total_spreads_processed == 0
        assert spread_filter.filtered_spreads == 0
        assert spread_filter.outlier_spreads == 0
        assert spread_filter.news_window_spreads == 0
        assert spread_filter.current_median_spread == 0.0
        assert spread_filter.current_std_spread == 0.0

    def test_initialization_default_config(self):
        """Test initialization with default config."""
        spread_filter = AdvancedSpreadFilter("GBPUSDc")
        
        assert spread_filter.symbol == "GBPUSDc"
        assert isinstance(spread_filter.config, SpreadFilterConfig)
        assert spread_filter.config.symbol == "GBPUSDc"

    def test_update_spread_insufficient_data(self):
        """Test updating spread with insufficient data."""
        spread_filter = AdvancedSpreadFilter("EURUSDc")
        
        # Create test spread data
        spread_data = SpreadData(
            timestamp_ms=int(time.time() * 1000),
            bid=1.1000,
            ask=1.1005,
            spread=0.0005,
            spread_pips=5.0,
            source="mt5"
        )
        
        signal = spread_filter.update_spread(spread_data)
        
        assert signal == SpreadFilterSignal.NORMAL  # Insufficient data, returns normal
        assert spread_filter.total_spreads_processed == 1

    def test_update_spread_sufficient_data(self):
        """Test updating spread with sufficient data."""
        config = SpreadFilterConfig(symbol="EURUSDc", min_data_points=5)
        spread_filter = AdvancedSpreadFilter("EURUSDc", config)
        
        current_time = int(time.time() * 1000)
        
        # Add enough spreads for analysis
        for i in range(10):
            spread_pips = 1.0 + i * 0.5  # Increasing spreads
            spread_data = SpreadData(
                timestamp_ms=current_time + i * 1000,
                bid=1.1000,
                ask=1.1000 + spread_pips * 0.0001,
                spread=spread_pips * 0.0001,
                spread_pips=spread_pips,
                source="mt5"
            )
            
            signal = spread_filter.update_spread(spread_data)
            
            if i >= 4:  # After 5th spread, should start analyzing
                assert signal is not None
                assert signal in [SpreadFilterSignal.NORMAL, SpreadFilterSignal.ELEVATED,
                                SpreadFilterSignal.HIGH, SpreadFilterSignal.EXTREME]

    def test_news_event_management(self):
        """Test news event management."""
        spread_filter = AdvancedSpreadFilter("EURUSDc")
        
        # Add news event
        news_event = NewsEvent(
            event_type=NewsEventType.NFP,
            timestamp_ms=int(time.time() * 1000),
            impact_level="high",
            currency="USD",
            description="Non-Farm Payrolls",
            exclusion_window_minutes=30
        )
        
        spread_filter.add_news_event(news_event)
        
        assert len(spread_filter.news_events) == 1
        assert len(spread_filter.active_news_windows) == 1

    def test_news_window_exclusion(self):
        """Test news window exclusion."""
        config = SpreadFilterConfig(symbol="EURUSDc", min_data_points=1)
        spread_filter = AdvancedSpreadFilter("EURUSDc", config)
        
        # Add news event
        current_time = int(time.time() * 1000)
        news_event = NewsEvent(
            event_type=NewsEventType.FOMC,
            timestamp_ms=current_time,
            impact_level="high",
            currency="USD",
            description="FOMC Meeting",
            exclusion_window_minutes=30
        )
        
        spread_filter.add_news_event(news_event)
        
        # Test spread during news window (within the 30-minute window)
        spread_data = SpreadData(
            timestamp_ms=current_time + 1000,  # 1 second after news (within window)
            bid=1.1000,
            ask=1.1005,
            spread=0.0005,
            spread_pips=5.0,
            source="mt5"
        )
        
        signal = spread_filter.update_spread(spread_data)
        
        # Should be excluded due to news window
        assert signal == SpreadFilterSignal.NEWS_WINDOW

    def test_outlier_detection(self):
        """Test outlier detection."""
        config = SpreadFilterConfig(symbol="EURUSDc", min_data_points=5)
        spread_filter = AdvancedSpreadFilter("EURUSDc", config)
        
        current_time = int(time.time() * 1000)
        
        # Add normal spreads first
        for i in range(10):
            spread_data = SpreadData(
                timestamp_ms=current_time + i * 1000,
                bid=1.1000,
                ask=1.1000 + 0.0002,  # 2 pips
                spread=0.0002,
                spread_pips=2.0,
                source="mt5"
            )
            spread_filter.update_spread(spread_data)
        
        # Add outlier spread
        outlier_spread = SpreadData(
            timestamp_ms=current_time + 10000,
            bid=1.1000,
            ask=1.1000 + 0.0010,  # 10 pips (outlier)
            spread=0.0010,
            spread_pips=10.0,
            source="mt5"
        )
        
        signal = spread_filter.update_spread(outlier_spread)
        
        # Should be detected as outlier
        assert signal == SpreadFilterSignal.OUTLIER

    def test_spread_classification(self):
        """Test spread classification."""
        config = SpreadFilterConfig(
            symbol="EURUSDc",
            normal_spread_threshold=1.5,
            elevated_spread_threshold=3.0,
            high_spread_threshold=5.0,
            extreme_spread_threshold=10.0,
            min_data_points=5,
            outlier_clipping_enabled=False  # Disable outlier detection for this test
        )
        spread_filter = AdvancedSpreadFilter("EURUSDc", config)
        
        current_time = int(time.time() * 1000)
        
        # Add baseline spreads
        for i in range(10):
            spread_data = SpreadData(
                timestamp_ms=current_time + i * 1000,
                bid=1.1000,
                ask=1.1000 + 0.0002,
                spread=0.0002,
                spread_pips=2.0,
                source="mt5"
            )
            spread_filter.update_spread(spread_data)
        
        # Test different spread levels
        test_cases = [
            (1.0, SpreadFilterSignal.NORMAL),      # Below normal threshold
            (2.0, SpreadFilterSignal.ELEVATED),    # Between normal and elevated
            (4.0, SpreadFilterSignal.HIGH),        # Between elevated and high
            (8.0, SpreadFilterSignal.EXTREME),     # Between high and extreme
            (15.0, SpreadFilterSignal.EXTREME)     # Above extreme threshold
        ]
        
        for spread_pips, expected_signal in test_cases:
            spread_data = SpreadData(
                timestamp_ms=current_time + 20000,
                bid=1.1000,
                ask=1.1000 + spread_pips * 0.0001,
                spread=spread_pips * 0.0001,
                spread_pips=spread_pips,
                source="mt5"
            )
            
            signal = spread_filter.update_spread(spread_data)
            assert signal == expected_signal

    def test_get_current_median_spread(self):
        """Test getting current median spread."""
        spread_filter = AdvancedSpreadFilter("EURUSDc")
        
        # No data yet
        assert spread_filter.get_current_median_spread() == 0.0
        
        # Add some spreads
        current_time = int(time.time() * 1000)
        for i in range(15):
            spread_data = SpreadData(
                timestamp_ms=current_time + i * 1000,
                bid=1.1000,
                ask=1.1000 + 0.0002,
                spread=0.0002,
                spread_pips=2.0,
                source="mt5"
            )
            spread_filter.update_spread(spread_data)
        
        median = spread_filter.get_current_median_spread()
        assert median > 0
        assert isinstance(median, float)

    def test_get_spread_statistics(self):
        """Test getting spread statistics."""
        spread_filter = AdvancedSpreadFilter("EURUSDc")
        
        # Add some spreads
        current_time = int(time.time() * 1000)
        for i in range(15):
            spread_data = SpreadData(
                timestamp_ms=current_time + i * 1000,
                bid=1.1000,
                ask=1.1000 + 0.0002,
                spread=0.0002,
                spread_pips=2.0,
                source="mt5"
            )
            spread_filter.update_spread(spread_data)
        
        stats = spread_filter.get_spread_statistics()
        
        assert "symbol" in stats
        assert "config" in stats
        assert "data_counts" in stats
        assert "current_state" in stats
        assert "performance" in stats
        
        assert stats["symbol"] == "EURUSDc"
        assert stats["data_counts"]["total_spreads_processed"] == 15

    def test_get_recent_spreads(self):
        """Test getting recent spreads."""
        spread_filter = AdvancedSpreadFilter("EURUSDc")
        
        # No spreads yet
        recent = spread_filter.get_recent_spreads(5)
        assert recent == []
        
        # Add some spreads
        current_time = int(time.time() * 1000)
        for i in range(10):
            spread_data = SpreadData(
                timestamp_ms=current_time + i * 1000,
                bid=1.1000,
                ask=1.1000 + 0.0002,
                spread=0.0002,
                spread_pips=2.0,
                source="mt5"
            )
            spread_filter.update_spread(spread_data)
        
        recent = spread_filter.get_recent_spreads(5)
        assert len(recent) == 5

    def test_spread_quality_checks(self):
        """Test spread quality check methods."""
        config = SpreadFilterConfig(symbol="EURUSDc", min_data_points=5)
        spread_filter = AdvancedSpreadFilter("EURUSDc", config)
        
        current_time = int(time.time() * 1000)
        
        # Add baseline spreads with normal spread (1.0 pips)
        for i in range(10):
            spread_data = SpreadData(
                timestamp_ms=current_time + i * 1000,
                bid=1.1000,
                ask=1.1000 + 0.0001,  # 1 pip
                spread=0.0001,
                spread_pips=1.0,
                source="mt5"
            )
            spread_filter.update_spread(spread_data)
        
        # Test quality checks
        assert spread_filter.is_spread_normal() is True
        assert spread_filter.is_spread_elevated() is False
        assert spread_filter.is_spread_high() is False
        assert spread_filter.is_spread_extreme() is False
        
        # Test quality score
        quality_score = spread_filter.get_spread_quality_score()
        assert 0.0 <= quality_score <= 1.0

    def test_should_avoid_trading(self):
        """Test trading avoidance logic."""
        spread_filter = AdvancedSpreadFilter("EURUSDc")
        
        # No data yet
        assert spread_filter.should_avoid_trading() is False
        
        # Add normal spreads
        current_time = int(time.time() * 1000)
        for i in range(10):
            spread_data = SpreadData(
                timestamp_ms=current_time + i * 1000,
                bid=1.1000,
                ask=1.1000 + 0.0002,
                spread=0.0002,
                spread_pips=2.0,
                source="mt5"
            )
            spread_filter.update_spread(spread_data)
        
        # Should not avoid trading with normal spreads
        assert spread_filter.should_avoid_trading() is False

    def test_validate_spread_data(self):
        """Test spread data validation."""
        spread_filter = AdvancedSpreadFilter("EURUSDc")
        
        # Valid data
        valid_data = SpreadData(
            timestamp_ms=int(time.time() * 1000),
            bid=1.1000,
            ask=1.1005,
            spread=0.0005,
            spread_pips=5.0,
            source="mt5",
            is_valid=True
        )
        assert spread_filter.validate_spread_data(valid_data) is True
        
        # Invalid data - negative spread
        invalid_data = SpreadData(
            timestamp_ms=int(time.time() * 1000),
            bid=1.1000,
            ask=1.1005,
            spread=-0.0005,
            spread_pips=-5.0,
            source="mt5",
            is_valid=True
        )
        assert spread_filter.validate_spread_data(invalid_data) is False
        
        # Invalid data - ask <= bid
        invalid_data2 = SpreadData(
            timestamp_ms=int(time.time() * 1000),
            bid=1.1000,
            ask=1.1000,
            spread=0.0,
            spread_pips=0.0,
            source="mt5",
            is_valid=True
        )
        assert spread_filter.validate_spread_data(invalid_data2) is False

    def test_reset_filter(self):
        """Test filter reset."""
        spread_filter = AdvancedSpreadFilter("EURUSDc")
        
        # Add some data
        current_time = int(time.time() * 1000)
        for i in range(10):
            spread_data = SpreadData(
                timestamp_ms=current_time + i * 1000,
                bid=1.1000,
                ask=1.1000 + 0.0002,
                spread=0.0002,
                spread_pips=2.0,
                source="mt5"
            )
            spread_filter.update_spread(spread_data)
        
        # Reset filter
        spread_filter.reset_filter()
        
        assert spread_filter.total_spreads_processed == 0
        assert spread_filter.filtered_spreads == 0
        assert spread_filter.outlier_spreads == 0
        assert spread_filter.news_window_spreads == 0
        assert len(spread_filter.spread_buffer) == 0
        assert len(spread_filter.rolling_median) == 0

    def test_get_filter_status(self):
        """Test getting filter status."""
        spread_filter = AdvancedSpreadFilter("EURUSDc")
        
        status = spread_filter.get_filter_status()
        
        assert "symbol" in status
        assert "is_healthy" in status
        assert "data_quality" in status
        assert "spread_conditions" in status
        assert "trading_recommendation" in status
        
        assert status["symbol"] == "EURUSDc"
        assert status["is_healthy"] is False  # No data yet

class TestIntegration:
    """Integration tests for spread filter system."""
    
    def test_full_spread_filter_workflow(self):
        """Test complete spread filter workflow."""
        config = SpreadFilterConfig(
            symbol="EURUSDc",
            window_size=10,
            min_data_points=5,
            normal_spread_threshold=2.0,
            elevated_spread_threshold=4.0,
            high_spread_threshold=6.0,
            extreme_spread_threshold=10.0
        )
        spread_filter = AdvancedSpreadFilter("EURUSDc", config)
        
        current_time = int(time.time() * 1000)
        
        # Simulate realistic spread data with various conditions
        spread_scenarios = [
            (1.5, "normal"),      # Normal spread
            (2.5, "elevated"),    # Elevated spread
            (3.5, "elevated"),    # Still elevated
            (5.5, "high"),        # High spread
            (8.0, "extreme"),     # Extreme spread
            (1.0, "normal"),      # Back to normal
            (2.0, "normal"),      # Still normal
        ]
        
        for i, (spread_pips, expected_condition) in enumerate(spread_scenarios):
            spread_data = SpreadData(
                timestamp_ms=current_time + i * 1000,
                bid=1.1000,
                ask=1.1000 + spread_pips * 0.0001,
                spread=spread_pips * 0.0001,
                spread_pips=spread_pips,
                source="mt5"
            )
            
            signal = spread_filter.update_spread(spread_data)
            
            if i >= 4:  # After minimum data points
                assert signal is not None
                print(f"Spread {spread_pips} pips -> Signal: {signal.value}")
        
        # Check final statistics
        stats = spread_filter.get_spread_statistics()
        assert stats["data_counts"]["total_spreads_processed"] == len(spread_scenarios)
        
        # Check filter status
        status = spread_filter.get_filter_status()
        assert status["symbol"] == "EURUSDc"

    def test_news_window_exclusion_workflow(self):
        """Test news window exclusion workflow."""
        config = SpreadFilterConfig(symbol="EURUSDc", min_data_points=1)
        spread_filter = AdvancedSpreadFilter("EURUSDc", config)
        
        # Add news event
        current_time = int(time.time() * 1000)
        news_event = NewsEvent(
            event_type=NewsEventType.FOMC,
            timestamp_ms=current_time + 10000,  # 10 seconds from now
            impact_level="high",
            currency="USD",
            description="FOMC Meeting",
            exclusion_window_minutes=5  # 5-minute exclusion window
        )
        spread_filter.add_news_event(news_event)
        
        # Test spreads before, during, and after news window
        test_times = [
            (current_time - 400000, "before"),  # Before news window (6+ minutes before current time)
            (current_time + 12000, "during"),   # During news (2 seconds after news event)
            (current_time + 400000, "after"),   # After news (6+ minutes after news event)
        ]
        
        for test_time, period in test_times:
            spread_data = SpreadData(
                timestamp_ms=test_time,
                bid=1.1000,
                ask=1.1005,
                spread=0.0005,
                spread_pips=5.0,
                source="mt5"
            )
            
            signal = spread_filter.update_spread(spread_data)
            
            if period == "during":
                assert signal == SpreadFilterSignal.NEWS_WINDOW
            else:
                assert signal != SpreadFilterSignal.NEWS_WINDOW

    def test_outlier_detection_workflow(self):
        """Test outlier detection workflow."""
        config = SpreadFilterConfig(
            symbol="EURUSDc",
            outlier_threshold=2.0,
            min_data_points=5
        )
        spread_filter = AdvancedSpreadFilter("EURUSDc", config)
        
        current_time = int(time.time() * 1000)
        
        # Add normal spreads
        for i in range(10):
            spread_data = SpreadData(
                timestamp_ms=current_time + i * 1000,
                bid=1.1000,
                ask=1.1000 + 0.0002,  # 2 pips
                spread=0.0002,
                spread_pips=2.0,
                source="mt5"
            )
            spread_filter.update_spread(spread_data)
        
        # Add outlier spread
        outlier_spread = SpreadData(
            timestamp_ms=current_time + 10000,
            bid=1.1000,
            ask=1.1000 + 0.0010,  # 10 pips (outlier)
            spread=0.0010,
            spread_pips=10.0,
            source="mt5"
        )
        
        signal = spread_filter.update_spread(outlier_spread)
        assert signal == SpreadFilterSignal.OUTLIER
        
        # Check statistics
        stats = spread_filter.get_spread_statistics()
        assert stats["data_counts"]["outlier_spreads"] == 1

if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
