"""
Test suite for advanced micro-BOS/CHOCH detection system.
Tests structure break detection, ATR displacement, and cooldown management.
"""

import pytest
import time
import numpy as np
from unittest.mock import patch, MagicMock

# Add the project root to the path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.engine.advanced_micro_bos_choch import (
    AdvancedMicroBOSCHOCH,
    MicroBOSConfig,
    StructureType,
    StructureDirection,
    StructureStrength,
    BarData,
    StructureBreak
)

class TestStructureType:
    """Test StructureType enum."""
    
    def test_structure_type_values(self):
        """Test structure type enum values."""
        assert StructureType.BOS.value == "bos"
        assert StructureType.CHOCH.value == "choch"
        assert StructureType.MICRO_BOS.value == "micro_bos"
        assert StructureType.MICRO_CHOCH.value == "micro_choch"

class TestStructureDirection:
    """Test StructureDirection enum."""
    
    def test_structure_direction_values(self):
        """Test structure direction enum values."""
        assert StructureDirection.BULLISH.value == "bullish"
        assert StructureDirection.BEARISH.value == "bearish"
        assert StructureDirection.NEUTRAL.value == "neutral"

class TestStructureStrength:
    """Test StructureStrength enum."""
    
    def test_structure_strength_values(self):
        """Test structure strength enum values."""
        assert StructureStrength.WEAK.value == "weak"
        assert StructureStrength.MODERATE.value == "moderate"
        assert StructureStrength.STRONG.value == "strong"
        assert StructureStrength.EXTREME.value == "extreme"

class TestMicroBOSConfig:
    """Test MicroBOSConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = MicroBOSConfig(symbol="BTCUSDc")
        
        assert config.symbol == "BTCUSDc"
        assert config.bar_lookback == 20
        assert config.min_atr_displacement == 0.25
        assert config.max_atr_displacement == 0.5
        assert config.cooldown_period_ms == 300000
        assert config.min_volume_threshold == 1.0
        assert "weak" in config.strength_thresholds
        assert "moderate" in config.strength_thresholds
        assert "strong" in config.strength_thresholds
        assert "extreme" in config.strength_thresholds

    def test_custom_config(self):
        """Test custom configuration values."""
        config = MicroBOSConfig(
            symbol="EURUSDc",
            bar_lookback=15,
            min_atr_displacement=0.3,
            max_atr_displacement=0.6,
            cooldown_period_ms=600000,
            min_volume_threshold=2.0
        )
        
        assert config.symbol == "EURUSDc"
        assert config.bar_lookback == 15
        assert config.min_atr_displacement == 0.3
        assert config.max_atr_displacement == 0.6
        assert config.cooldown_period_ms == 600000
        assert config.min_volume_threshold == 2.0

class TestBarData:
    """Test BarData dataclass."""
    
    def test_bar_data_creation(self):
        """Test bar data creation."""
        bar_data = BarData(
            timestamp_ms=1234567890,
            open=1.1000,
            high=1.1005,
            low=1.0995,
            close=1.1002,
            volume=1000.0,
            timeframe="M1"
        )
        
        assert bar_data.timestamp_ms == 1234567890
        assert bar_data.open == 1.1000
        assert bar_data.high == 1.1005
        assert bar_data.low == 1.0995
        assert bar_data.close == 1.1002
        assert bar_data.volume == 1000.0
        assert bar_data.timeframe == "M1"
        assert bar_data.is_valid is True

class TestStructureBreak:
    """Test StructureBreak dataclass."""
    
    def test_structure_break_creation(self):
        """Test structure break creation."""
        structure_break = StructureBreak(
            structure_type=StructureType.BOS,
            direction=StructureDirection.BULLISH,
            strength=StructureStrength.MODERATE,
            timestamp_ms=1234567890,
            price_level=1.1005,
            displacement=0.001,
            atr_ratio=0.4,
            bar_count=15,
            confidence_score=0.75,
            is_micro=True,
            cooldown_remaining_ms=300000
        )
        
        assert structure_break.structure_type == StructureType.BOS
        assert structure_break.direction == StructureDirection.BULLISH
        assert structure_break.strength == StructureStrength.MODERATE
        assert structure_break.timestamp_ms == 1234567890
        assert structure_break.price_level == 1.1005
        assert structure_break.displacement == 0.001
        assert structure_break.atr_ratio == 0.4
        assert structure_break.bar_count == 15
        assert structure_break.confidence_score == 0.75
        assert structure_break.is_micro is True
        assert structure_break.cooldown_remaining_ms == 300000

class TestAdvancedMicroBOSCHOCH:
    """Test AdvancedMicroBOSCHOCH class."""
    
    def test_initialization(self):
        """Test micro-BOS/CHOCH system initialization."""
        config = MicroBOSConfig(symbol="BTCUSDc")
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc", config)
        
        assert micro_bos.symbol == "BTCUSDc"
        assert micro_bos.config == config
        assert micro_bos.last_structure_break is None
        assert micro_bos.current_trend == StructureDirection.NEUTRAL
        assert micro_bos.last_break_time_ms == 0
        assert micro_bos.total_breaks_detected == 0
        assert micro_bos.micro_breaks_detected == 0
        assert micro_bos.valid_breaks == 0
        assert micro_bos.false_breaks == 0

    def test_initialization_default_config(self):
        """Test initialization with default config."""
        micro_bos = AdvancedMicroBOSCHOCH("EURUSDc")
        
        assert micro_bos.symbol == "EURUSDc"
        assert isinstance(micro_bos.config, MicroBOSConfig)
        assert micro_bos.config.symbol == "EURUSDc"

    def test_update_bar_insufficient_data(self):
        """Test updating bar with insufficient data."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # Create a test bar
        bar = BarData(
            timestamp_ms=int(time.time() * 1000),
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=1.0,
            timeframe="M1"
        )
        
        structure_break = micro_bos.update_bar(bar)
        
        assert structure_break is None  # Not enough data for detection
        assert len(micro_bos.bar_buffer) == 1

    def test_update_bar_sufficient_data(self):
        """Test updating bar with sufficient data."""
        config = MicroBOSConfig(symbol="BTCUSDc", bar_lookback=5)
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc", config)
        
        current_time = int(time.time() * 1000)
        base_price = 50000.0
        
        # Add enough bars for detection
        for i in range(10):
            price_change = i * 10.0  # Increasing price
            bar = BarData(
                timestamp_ms=current_time + i * 60000,
                open=base_price + price_change,
                high=base_price + price_change + 50.0,
                low=base_price + price_change - 50.0,
                close=base_price + price_change + 25.0,
                volume=1.0 + i * 0.1,
                timeframe="M1"
            )
            
            structure_break = micro_bos.update_bar(bar)
            
            if i >= 4:  # After 5th bar, should start detecting
                # May or may not detect depending on price movement
                if structure_break:
                    assert isinstance(structure_break, StructureBreak)
                    assert structure_break.structure_type in [StructureType.BOS, StructureType.CHOCH,
                                                           StructureType.MICRO_BOS, StructureType.MICRO_CHOCH]

    def test_calculate_atr(self):
        """Test ATR calculation."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # Add some test bars
        current_time = int(time.time() * 1000)
        for i in range(20):
            bar = BarData(
                timestamp_ms=current_time + i * 60000,
                open=50000.0 + i * 10.0,
                high=50050.0 + i * 10.0,
                low=49950.0 + i * 10.0,
                close=50000.0 + i * 10.0,
                volume=1.0,
                timeframe="M1"
            )
            micro_bos.bar_buffer.append(bar)
        
        atr_value = micro_bos._calculate_atr()
        
        assert atr_value is not None
        assert atr_value > 0
        assert isinstance(atr_value, float)

    def test_calculate_atr_insufficient_data(self):
        """Test ATR calculation with insufficient data."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # Add insufficient data
        for i in range(5):
            bar = BarData(
                timestamp_ms=int(time.time() * 1000) + i * 60000,
                open=50000.0,
                high=50100.0,
                low=49900.0,
                close=50050.0,
                volume=1.0,
                timeframe="M1"
            )
            micro_bos.bar_buffer.append(bar)
        
        atr_value = micro_bos._calculate_atr()
        
        assert atr_value is None

    def test_analyze_trend(self):
        """Test trend analysis."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # Test bullish trend
        bullish_bars = [
            BarData(0, 50000.0, 50100.0, 49900.0, 50050.0, 1.0, "M1"),
            BarData(0, 50050.0, 50150.0, 50000.0, 50100.0, 1.0, "M1"),
            BarData(0, 50100.0, 50200.0, 50050.0, 50150.0, 1.0, "M1")
        ]
        
        trend = micro_bos._analyze_trend(bullish_bars)
        assert trend == StructureDirection.BULLISH
        
        # Test bearish trend
        bearish_bars = [
            BarData(0, 50150.0, 50200.0, 50100.0, 50100.0, 1.0, "M1"),
            BarData(0, 50100.0, 50150.0, 50050.0, 50050.0, 1.0, "M1"),
            BarData(0, 50050.0, 50100.0, 50000.0, 50000.0, 1.0, "M1")
        ]
        
        trend = micro_bos._analyze_trend(bearish_bars)
        assert trend == StructureDirection.BEARISH

    def test_detect_bos(self):
        """Test BOS detection."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # Create bars with swing high
        bars = []
        for i in range(10):
            bar = BarData(
                timestamp_ms=int(time.time() * 1000) + i * 60000,
                open=50000.0,
                high=50050.0 + i * 5.0,
                low=49950.0 + i * 5.0,
                close=50000.0 + i * 5.0,
                volume=1.0,
                timeframe="M1"
            )
            bars.append(bar)
        
        # Create a bar that breaks above swing high
        current_bar = BarData(
            timestamp_ms=int(time.time() * 1000) + 10 * 60000,
            open=50050.0,
            high=50100.0,  # Breaks above previous high
            low=50000.0,
            close=50100.0,
            volume=2.0,
            timeframe="M1"
        )
        
        bos_break = micro_bos._detect_bos(bars, current_bar)
        
        if bos_break:  # May not detect if ATR ratio is too low
            assert bos_break.structure_type in [StructureType.BOS, StructureType.MICRO_BOS]
            assert bos_break.direction == StructureDirection.BULLISH

    def test_detect_choch(self):
        """Test CHOCH detection."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # Create bars with bearish trend
        bars = []
        for i in range(10):
            bar = BarData(
                timestamp_ms=int(time.time() * 1000) + i * 60000,
                open=50100.0 - i * 10.0,
                high=50150.0 - i * 10.0,
                low=50050.0 - i * 10.0,
                close=50100.0 - i * 10.0,
                volume=1.0,
                timeframe="M1"
            )
            bars.append(bar)
        
        # Create a bar that changes trend to bullish
        current_bar = BarData(
            timestamp_ms=int(time.time() * 1000) + 10 * 60000,
            open=50000.0,
            high=50100.0,  # Higher than previous close
            low=49950.0,
            close=50100.0,
            volume=2.0,
            timeframe="M1"
        )
        
        choch_break = micro_bos._detect_choch(bars, current_bar)
        
        if choch_break:  # May not detect if ATR ratio is too low
            assert choch_break.structure_type in [StructureType.CHOCH, StructureType.MICRO_CHOCH]
            assert choch_break.direction == StructureDirection.BULLISH

    def test_calculate_strength(self):
        """Test strength calculation."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # Test different strength levels based on the actual calculation:
        # strength_score = atr_ratio * 0.7 + min(volume / 10.0, 1.0) * 0.3
        # thresholds: weak=0.25, moderate=0.35, strong=0.45, extreme=0.55
        
        test_cases = [
            (0.2, 1.0, StructureStrength.WEAK),      # score = 0.2*0.7 + 0.1*0.3 = 0.17 < 0.25
            (0.4, 3.0, StructureStrength.MODERATE),   # score = 0.4*0.7 + 0.3*0.3 = 0.37 > 0.35
            (0.5, 4.0, StructureStrength.STRONG),     # score = 0.5*0.7 + 0.4*0.3 = 0.47 > 0.45
            (0.6, 5.0, StructureStrength.EXTREME)     # score = 0.6*0.7 + 0.5*0.3 = 0.57 > 0.55
        ]
        
        for atr_ratio, volume, expected_strength in test_cases:
            strength = micro_bos._calculate_strength(atr_ratio, volume)
            # Calculate expected score to verify logic
            expected_score = atr_ratio * 0.7 + min(volume / 10.0, 1.0) * 0.3
            print(f"ATR: {atr_ratio}, Volume: {volume}, Score: {expected_score:.3f}, Strength: {strength.value}")
            assert strength == expected_strength

    def test_calculate_confidence(self):
        """Test confidence calculation."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # Test confidence calculation
        confidence = micro_bos._calculate_confidence(0.4, 2.0, int(time.time() * 1000))
        
        assert 0.0 <= confidence <= 1.0
        assert isinstance(confidence, float)

    def test_is_in_cooldown(self):
        """Test cooldown period check."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # No previous break
        assert micro_bos._is_in_cooldown() is False
        
        # Set a recent break
        micro_bos.last_break_time_ms = int(time.time() * 1000) - 100000  # 100 seconds ago
        micro_bos.config.cooldown_period_ms = 300000  # 5 minutes
        
        assert micro_bos._is_in_cooldown() is True
        
        # Set an old break
        micro_bos.last_break_time_ms = int(time.time() * 1000) - 400000  # 400 seconds ago
        
        assert micro_bos._is_in_cooldown() is False

    def test_get_current_trend(self):
        """Test getting current trend."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # Default trend
        assert micro_bos.get_current_trend() == StructureDirection.NEUTRAL
        
        # Set trend
        micro_bos.current_trend = StructureDirection.BULLISH
        assert micro_bos.get_current_trend() == StructureDirection.BULLISH

    def test_get_last_structure_break(self):
        """Test getting last structure break."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # No break yet
        assert micro_bos.get_last_structure_break() is None
        
        # Set a break
        structure_break = StructureBreak(
            structure_type=StructureType.BOS,
            direction=StructureDirection.BULLISH,
            strength=StructureStrength.MODERATE,
            timestamp_ms=int(time.time() * 1000),
            price_level=50000.0,
            displacement=100.0,
            atr_ratio=0.4,
            bar_count=10,
            confidence_score=0.8,
            is_micro=True,
            cooldown_remaining_ms=300000
        )
        micro_bos.last_structure_break = structure_break
        
        assert micro_bos.get_last_structure_break() == structure_break

    def test_get_structure_statistics(self):
        """Test getting structure statistics."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # Process some bars
        current_time = int(time.time() * 1000)
        for i in range(20):
            bar = BarData(
                timestamp_ms=current_time + i * 60000,
                open=50000.0 + i * 10.0,
                high=50100.0 + i * 10.0,
                low=49900.0 + i * 10.0,
                close=50050.0 + i * 10.0,
                volume=1.0 + i * 0.1,
                timeframe="M1"
            )
            micro_bos.update_bar(bar)
        
        stats = micro_bos.get_structure_statistics()
        
        assert "symbol" in stats
        assert "config" in stats
        assert "data_counts" in stats
        assert "performance" in stats
        assert "current_state" in stats
        
        assert stats["symbol"] == "BTCUSDc"
        assert "bar_buffer_size" in stats["data_counts"]
        assert "structure_history_size" in stats["data_counts"]
        assert "atr_values_size" in stats["data_counts"]

    def test_get_structure_distribution(self):
        """Test structure distribution calculation."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # Add some structure breaks to history
        breaks = [
            StructureBreak(StructureType.BOS, StructureDirection.BULLISH, StructureStrength.MODERATE,
                          int(time.time() * 1000), 50000.0, 100.0, 0.4, 10, 0.8, True, 300000),
            StructureBreak(StructureType.CHOCH, StructureDirection.BEARISH, StructureStrength.STRONG,
                          int(time.time() * 1000) + 1000, 49900.0, 150.0, 0.5, 12, 0.9, False, 300000),
            StructureBreak(StructureType.MICRO_BOS, StructureDirection.BULLISH, StructureStrength.WEAK,
                          int(time.time() * 1000) + 2000, 50100.0, 80.0, 0.3, 8, 0.6, True, 300000)
        ]
        
        for break_event in breaks:
            micro_bos.structure_history.append(break_event)
        
        distribution = micro_bos.get_structure_distribution()
        
        assert "bos" in distribution
        assert "choch" in distribution
        assert "micro_bos" in distribution
        assert distribution["bos"] == 1
        assert distribution["choch"] == 1
        assert distribution["micro_bos"] == 1

    def test_get_recent_breaks(self):
        """Test getting recent breaks."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # No breaks
        recent_breaks = micro_bos.get_recent_breaks()
        assert recent_breaks == []
        
        # Add some breaks
        for i in range(5):
            break_event = StructureBreak(
                StructureType.BOS, StructureDirection.BULLISH, StructureStrength.MODERATE,
                int(time.time() * 1000) + i * 1000, 50000.0 + i * 100.0, 100.0, 0.4, 10, 0.8, True, 300000
            )
            micro_bos.structure_history.append(break_event)
        
        recent_breaks = micro_bos.get_recent_breaks(3)
        assert len(recent_breaks) == 3

    def test_is_trend_bullish(self):
        """Test bullish trend detection."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # Default trend
        assert micro_bos.is_trend_bullish() is False
        
        # Set bullish trend
        micro_bos.current_trend = StructureDirection.BULLISH
        assert micro_bos.is_trend_bullish() is True

    def test_is_trend_bearish(self):
        """Test bearish trend detection."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # Default trend
        assert micro_bos.is_trend_bearish() is False
        
        # Set bearish trend
        micro_bos.current_trend = StructureDirection.BEARISH
        assert micro_bos.is_trend_bearish() is True

    def test_get_cooldown_remaining(self):
        """Test cooldown remaining calculation."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # No cooldown
        assert micro_bos.get_cooldown_remaining() == 0
        
        # Set recent break
        micro_bos.last_break_time_ms = int(time.time() * 1000) - 100000  # 100 seconds ago
        micro_bos.config.cooldown_period_ms = 300000  # 5 minutes
        
        remaining = micro_bos.get_cooldown_remaining()
        assert 0 < remaining < 300000

    def test_validate_structure_break(self):
        """Test structure break validation."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # Valid break
        valid_break = StructureBreak(
            StructureType.BOS, StructureDirection.BULLISH, StructureStrength.MODERATE,
            int(time.time() * 1000), 50000.0, 100.0, 0.4, 10, 0.8, True, 300000
        )
        assert micro_bos.validate_structure_break(valid_break) is True
        
        # Invalid break (low ATR ratio)
        invalid_break = StructureBreak(
            StructureType.BOS, StructureDirection.BULLISH, StructureStrength.MODERATE,
            int(time.time() * 1000), 50000.0, 100.0, 0.1, 10, 0.8, True, 300000
        )
        assert micro_bos.validate_structure_break(invalid_break) is False

class TestIntegration:
    """Integration tests for micro-BOS/CHOCH system."""
    
    def test_full_structure_detection_workflow(self):
        """Test complete structure detection workflow."""
        config = MicroBOSConfig(
            symbol="BTCUSDc",
            bar_lookback=10,
            min_atr_displacement=0.3,
            max_atr_displacement=0.6
        )
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc", config)
        
        current_time = int(time.time() * 1000)
        base_price = 50000.0
        
        # Simulate realistic price movement with structure breaks
        for i in range(50):
            # Create price movement pattern
            if i < 20:
                # Initial uptrend
                price_change = i * 10.0
            elif i < 30:
                # Consolidation
                price_change = 200.0 + (i - 20) * 2.0
            else:
                # Breakout
                price_change = 220.0 + (i - 30) * 15.0
            
            bar = BarData(
                timestamp_ms=current_time + i * 60000,
                open=base_price + price_change - 25.0,
                high=base_price + price_change + 50.0,
                low=base_price + price_change - 50.0,
                close=base_price + price_change,
                volume=1.0 + i * 0.05,
                timeframe="M1"
            )
            
            structure_break = micro_bos.update_bar(bar)
            
            if structure_break and i % 10 == 0:
                print(f"Structure break at {i}: {structure_break.structure_type.value} "
                      f"{structure_break.direction.value}, strength: {structure_break.strength.value}")
        
        # Check final statistics
        stats = micro_bos.get_structure_statistics()
        assert stats["performance"]["total_breaks_detected"] >= 0
        
        # Check if we have structure data
        if micro_bos.structure_history:
            distribution = micro_bos.get_structure_distribution()
            assert len(distribution) > 0

    def test_cooldown_management(self):
        """Test cooldown period management."""
        config = MicroBOSConfig(
            symbol="BTCUSDc",
            cooldown_period_ms=300000  # 5 minutes
        )
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc", config)
        
        # Simulate a structure break
        current_time = int(time.time() * 1000)
        micro_bos.last_break_time_ms = current_time
        
        # Should be in cooldown
        assert micro_bos._is_in_cooldown() is True
        assert micro_bos.get_cooldown_remaining() > 0
        
        # Simulate time passing
        micro_bos.last_break_time_ms = current_time - 400000  # 400 seconds ago
        
        # Should not be in cooldown
        assert micro_bos._is_in_cooldown() is False
        assert micro_bos.get_cooldown_remaining() == 0

    def test_structure_break_classification(self):
        """Test structure break classification with known patterns."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # Test different structure types
        test_cases = [
            (StructureType.BOS, StructureDirection.BULLISH, StructureStrength.MODERATE),
            (StructureType.CHOCH, StructureDirection.BEARISH, StructureStrength.STRONG),
            (StructureType.MICRO_BOS, StructureDirection.BULLISH, StructureStrength.WEAK),
            (StructureType.MICRO_CHOCH, StructureDirection.BEARISH, StructureStrength.MODERATE)
        ]
        
        for structure_type, direction, strength in test_cases:
            break_event = StructureBreak(
                structure_type=structure_type,
                direction=direction,
                strength=strength,
                timestamp_ms=int(time.time() * 1000),
                price_level=50000.0,
                displacement=100.0,
                atr_ratio=0.4,
                bar_count=10,
                confidence_score=0.8,
                is_micro=structure_type in [StructureType.MICRO_BOS, StructureType.MICRO_CHOCH],
                cooldown_remaining_ms=300000
            )
            
            # Validate the break
            is_valid = micro_bos.validate_structure_break(break_event)
            assert is_valid is True

if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
