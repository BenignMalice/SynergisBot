"""
Property Tests for Trading Algorithms

This module implements property-based testing for critical trading algorithm invariants:
1. VWAP reclaim monotonicity - VWAP should never decrease after a reclaim
2. ATR boundary conditions - ATR should be within valid ranges
3. BOS displacement - Break of Structure should have minimum displacement

Property tests use hypothesis to generate random test cases and verify invariants.
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, settings, example
from hypothesis.strategies import floats, integers, lists, composite
from typing import List, Tuple, Dict, Any
import time
import random
from datetime import datetime, timedelta

# Import our trading modules
from app.engine.advanced_vwap_calculator import AdvancedVWAPCalculator
from app.engine.advanced_atr_ratio_system import AdvancedATRRatioSystem, SymbolATRConfig
from app.engine.advanced_micro_bos_choch import AdvancedMicroBOSCHOCH, MicroBOSConfig, StructureType
from app.engine.volume_delta_proxy import VolumeDeltaProxy
from app.engine.advanced_spread_filter import AdvancedSpreadFilter, SpreadFilterConfig, SpreadData
from app.schemas.trading_events import TickEvent, OHLCVBarEvent, MarketStructureEvent
from app.engine.advanced_micro_bos_choch import BarData


class PropertyTestConfig:
    """Configuration for property tests"""
    
    # VWAP test parameters
    VWAP_MIN_TICKS = 10
    VWAP_MAX_TICKS = 1000
    VWAP_PRICE_MIN = 0.01
    VWAP_PRICE_MAX = 100000.0
    VWAP_VOLUME_MIN = 0.001
    VWAP_VOLUME_MAX = 1000.0
    
    # ATR test parameters
    ATR_MIN_PERIOD = 5
    ATR_MAX_PERIOD = 50
    ATR_PRICE_MIN = 0.01
    ATR_PRICE_MAX = 100000.0
    ATR_MIN_VALUE = 0.0001
    ATR_MAX_VALUE = 1000.0
    
    # BOS test parameters
    BOS_MIN_BARS = 3
    BOS_MAX_BARS = 50
    BOS_MIN_DISPLACEMENT = 0.0001
    BOS_MAX_DISPLACEMENT = 100.0
    BOS_MIN_COOLDOWN = 1000  # 1 second
    BOS_MAX_COOLDOWN = 3600000  # 1 hour
    
    # Test execution parameters
    MAX_EXAMPLES = 100
    DEADLINE = 5000  # 5 seconds per test


@composite
def vwap_tick_data(draw, min_ticks=PropertyTestConfig.VWAP_MIN_TICKS, 
                   max_ticks=PropertyTestConfig.VWAP_MAX_TICKS):
    """Generate random tick data for VWAP testing"""
    num_ticks = draw(integers(min_ticks, max_ticks))
    
    ticks = []
    base_time = int(time.time() * 1000)
    
    for i in range(num_ticks):
        timestamp = base_time + i * 1000  # 1 second intervals
        bid = draw(floats(PropertyTestConfig.VWAP_PRICE_MIN, PropertyTestConfig.VWAP_PRICE_MAX))
        ask = draw(floats(bid, bid * 1.01))  # Ask > Bid
        volume = draw(floats(PropertyTestConfig.VWAP_VOLUME_MIN, PropertyTestConfig.VWAP_VOLUME_MAX))
        
        tick = TickEvent(
            symbol="BTCUSDc",
            timestamp_ms=timestamp,
            bid=bid,
            ask=ask,
            volume=volume,
            source="mt5"
        )
        ticks.append(tick)
    
    return ticks


@composite
def atr_bar_data(draw, min_bars=PropertyTestConfig.ATR_MIN_PERIOD, 
                  max_bars=PropertyTestConfig.ATR_MAX_PERIOD):
    """Generate random bar data for ATR testing"""
    num_bars = draw(integers(min_bars, max_bars))
    
    bars = []
    base_time = int(time.time() * 1000)
    
    for i in range(num_bars):
        timestamp = base_time + i * 300000  # 5 minute intervals
        high = draw(floats(PropertyTestConfig.ATR_PRICE_MIN, PropertyTestConfig.ATR_PRICE_MAX))
        low = draw(floats(PropertyTestConfig.ATR_PRICE_MIN, high))
        close = draw(floats(low, high))
        open_price = draw(floats(low, high))
        volume = draw(floats(PropertyTestConfig.VWAP_VOLUME_MIN, PropertyTestConfig.VWAP_VOLUME_MAX))
        
        bar = BarData(
            symbol="BTCUSDc",
            timeframe="M5",
            timestamp_ms=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
            is_valid=True
        )
        bars.append(bar)
    
    return bars


@composite
def bos_bar_data(draw, min_bars=PropertyTestConfig.BOS_MIN_BARS, 
                  max_bars=PropertyTestConfig.BOS_MAX_BARS):
    """Generate random bar data for BOS testing"""
    num_bars = draw(integers(min_bars, max_bars))
    
    bars = []
    base_time = int(time.time() * 1000)
    
    for i in range(num_bars):
        timestamp = base_time + i * 60000  # 1 minute intervals
        high = draw(floats(PropertyTestConfig.ATR_PRICE_MIN, PropertyTestConfig.ATR_PRICE_MAX))
        low = draw(floats(PropertyTestConfig.ATR_PRICE_MIN, high))
        close = draw(floats(low, high))
        open_price = draw(floats(low, high))
        volume = draw(floats(PropertyTestConfig.VWAP_VOLUME_MIN, PropertyTestConfig.VWAP_VOLUME_MAX))
        
        bar = BarData(
            symbol="BTCUSDc",
            timeframe="M1",
            timestamp_ms=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
            is_valid=True
        )
        bars.append(bar)
    
    return bars


class TestVWAPPropertyTests:
    """Property tests for VWAP reclaim monotonicity"""
    
    @given(vwap_tick_data())
    @settings(max_examples=PropertyTestConfig.MAX_EXAMPLES, deadline=PropertyTestConfig.DEADLINE)
    def test_vwap_monotonicity_after_reclaim(self, ticks):
        """Test that VWAP never decreases after a reclaim signal"""
        symbol_config = {
            "symbol": "BTCUSDc",
            "session_type": "CRYPTO_24_7",
            "vwap_period": 60,
            "sigma_multiplier": 2.0
        }
        
        vwap_calc = AdvancedVWAPCalculator(symbol_config)
        
        vwap_values = []
        reclaim_signals = []
        
        for tick in ticks:
            vwap_calc.update_tick(tick)
            current_vwap = vwap_calc.get_current_vwap()
            
            if current_vwap is not None:
                vwap_values.append(current_vwap)
                
                # Check for reclaim signal
                if vwap_calc.is_reclaim():
                    reclaim_signals.append(len(vwap_values) - 1)
        
        # Verify monotonicity after reclaims
        for reclaim_idx in reclaim_signals:
            if reclaim_idx < len(vwap_values) - 1:
                reclaim_vwap = vwap_values[reclaim_idx]
                for i in range(reclaim_idx + 1, len(vwap_values)):
                    assert vwap_values[i] >= reclaim_vwap, \
                        f"VWAP decreased after reclaim: {reclaim_vwap} -> {vwap_values[i]}"
    
    @given(vwap_tick_data())
    @settings(max_examples=PropertyTestConfig.MAX_EXAMPLES, deadline=PropertyTestConfig.DEADLINE)
    def test_vwap_positive_values(self, ticks):
        """Test that VWAP values are always positive"""
        symbol_config = {
            "symbol": "BTCUSDc",
            "session_type": "CRYPTO_24_7",
            "vwap_period": 60,
            "sigma_multiplier": 2.0
        }
        
        vwap_calc = AdvancedVWAPCalculator(symbol_config)
        
        for tick in ticks:
            vwap_calc.update_tick(tick)
            current_vwap = vwap_calc.get_current_vwap()
            
            if current_vwap is not None:
                assert current_vwap > 0, f"VWAP should be positive: {current_vwap}"
    
    @given(vwap_tick_data())
    @settings(max_examples=PropertyTestConfig.MAX_EXAMPLES, deadline=PropertyTestConfig.DEADLINE)
    def test_vwap_within_price_range(self, ticks):
        """Test that VWAP is within the price range of ticks"""
        symbol_config = {
            "symbol": "BTCUSDc",
            "session_type": "CRYPTO_24_7",
            "vwap_period": 60,
            "sigma_multiplier": 2.0
        }
        
        vwap_calc = AdvancedVWAPCalculator(symbol_config)
        
        min_price = float('inf')
        max_price = 0.0
        
        for tick in ticks:
            min_price = min(min_price, tick.bid, tick.ask)
            max_price = max(max_price, tick.bid, tick.ask)
            
            vwap_calc.update_tick(tick)
            current_vwap = vwap_calc.get_current_vwap()
            
            if current_vwap is not None:
                assert min_price <= current_vwap <= max_price, \
                    f"VWAP {current_vwap} outside price range [{min_price}, {max_price}]"


class TestATRPropertyTests:
    """Property tests for ATR boundary conditions"""
    
    @given(atr_bar_data())
    @settings(max_examples=PropertyTestConfig.MAX_EXAMPLES, deadline=PropertyTestConfig.DEADLINE)
    def test_atr_positive_values(self, bars):
        """Test that ATR values are always positive"""
        atr_config = SymbolATRConfig(
            symbol="BTCUSDc",
            m1_atr_period=14,
            m5_atr_period=14,
            ratio_multiplier=1.0,
            high_volatility_threshold=2.0
        )
        
        atr_system = AdvancedATRRatioSystem("BTCUSDc", atr_config)
        
        for bar in bars:
            atr_system.update_m1_bar(bar)
            atr_system.update_m5_bar(bar)
            
            m1_atr = atr_system.get_m1_atr()
            m5_atr = atr_system.get_m5_atr()
            atr_ratio = atr_system.get_atr_ratio()
            
            if m1_atr is not None:
                assert m1_atr > 0, f"M1 ATR should be positive: {m1_atr}"
            if m5_atr is not None:
                assert m5_atr > 0, f"M5 ATR should be positive: {m5_atr}"
            if atr_ratio is not None:
                assert atr_ratio > 0, f"ATR ratio should be positive: {atr_ratio}"
    
    @given(atr_bar_data())
    @settings(max_examples=PropertyTestConfig.MAX_EXAMPLES, deadline=PropertyTestConfig.DEADLINE)
    def test_atr_within_reasonable_bounds(self, bars):
        """Test that ATR values are within reasonable bounds"""
        atr_config = SymbolATRConfig(
            symbol="BTCUSDc",
            m1_atr_period=14,
            m5_atr_period=14,
            ratio_multiplier=1.0,
            high_volatility_threshold=2.0
        )
        
        atr_system = AdvancedATRRatioSystem("BTCUSDc", atr_config)
        
        for bar in bars:
            atr_system.update_m1_bar(bar)
            atr_system.update_m5_bar(bar)
            
            m1_atr = atr_system.get_m1_atr()
            m5_atr = atr_system.get_m5_atr()
            
            if m1_atr is not None:
                assert PropertyTestConfig.ATR_MIN_VALUE <= m1_atr <= PropertyTestConfig.ATR_MAX_VALUE, \
                    f"M1 ATR {m1_atr} outside bounds [{PropertyTestConfig.ATR_MIN_VALUE}, {PropertyTestConfig.ATR_MAX_VALUE}]"
            
            if m5_atr is not None:
                assert PropertyTestConfig.ATR_MIN_VALUE <= m5_atr <= PropertyTestConfig.ATR_MAX_VALUE, \
                    f"M5 ATR {m5_atr} outside bounds [{PropertyTestConfig.ATR_MIN_VALUE}, {PropertyTestConfig.ATR_MAX_VALUE}]"
    
    @given(atr_bar_data())
    @settings(max_examples=PropertyTestConfig.MAX_EXAMPLES, deadline=PropertyTestConfig.DEADLINE)
    def test_atr_ratio_bounds(self, bars):
        """Test that ATR ratio is within reasonable bounds"""
        atr_config = SymbolATRConfig(
            symbol="BTCUSDc",
            m1_atr_period=14,
            m5_atr_period=14,
            ratio_multiplier=1.0,
            high_volatility_threshold=2.0
        )
        
        atr_system = AdvancedATRRatioSystem("BTCUSDc", atr_config)
        
        for bar in bars:
            atr_system.update_m1_bar(bar)
            atr_system.update_m5_bar(bar)
            
            atr_ratio = atr_system.get_atr_ratio()
            
            if atr_ratio is not None:
                # ATR ratio should be between 0.1 and 10.0 (reasonable bounds)
                assert 0.1 <= atr_ratio <= 10.0, \
                    f"ATR ratio {atr_ratio} outside reasonable bounds [0.1, 10.0]"


class TestBOSPropertyTests:
    """Property tests for BOS displacement"""
    
    @given(bos_bar_data())
    @settings(max_examples=PropertyTestConfig.MAX_EXAMPLES, deadline=PropertyTestConfig.DEADLINE)
    def test_bos_minimum_displacement(self, bars):
        """Test that BOS signals have minimum displacement"""
        bos_config = MicroBOSConfig(
            symbol="BTCUSDc",
            bar_lookback=10,
            min_atr_displacement=0.5,
            cooldown_period_ms=300000  # 5 minutes
        )
        
        bos_system = AdvancedMicroBOSCHOCH("BTCUSDc", bos_config)
        
        for bar in bars:
            bos_system.update_bar(bar)
            
            if bos_system.has_bos_signal():
                signal = bos_system.get_bos_signal()
                
                # Check that displacement meets minimum requirement
                if signal and 'displacement' in signal:
                    displacement = signal['displacement']
                    assert displacement >= bos_config.min_atr_displacement, \
                        f"BOS displacement {displacement} below minimum {bos_config.min_atr_displacement}"
    
    @given(bos_bar_data())
    @settings(max_examples=PropertyTestConfig.MAX_EXAMPLES, deadline=PropertyTestConfig.DEADLINE)
    def test_bos_cooldown_respect(self, bars):
        """Test that BOS signals respect cooldown period"""
        bos_config = MicroBOSConfig(
            symbol="BTCUSDc",
            bar_lookback=10,
            min_atr_displacement=0.5,
            cooldown_period_ms=300000  # 5 minutes
        )
        
        bos_system = AdvancedMicroBOSCHOCH("BTCUSDc", bos_config)
        
        last_signal_time = None
        
        for bar in bars:
            bos_system.update_bar(bar)
            
            if bos_system.has_bos_signal():
                current_time = bar.timestamp_ms
                
                if last_signal_time is not None:
                    time_diff = current_time - last_signal_time
                    assert time_diff >= bos_config.cooldown_period_ms, \
                        f"BOS signal too soon: {time_diff}ms < {bos_config.cooldown_period_ms}ms"
                
                last_signal_time = current_time
    
    @given(bos_bar_data())
    @settings(max_examples=PropertyTestConfig.MAX_EXAMPLES, deadline=PropertyTestConfig.DEADLINE)
    def test_bos_strength_bounds(self, bars):
        """Test that BOS strength is within valid bounds"""
        bos_config = MicroBOSConfig(
            symbol="BTCUSDc",
            bar_lookback=10,
            min_atr_displacement=0.5,
            cooldown_period_ms=300000  # 5 minutes
        )
        
        bos_system = AdvancedMicroBOSCHOCH("BTCUSDc", bos_config)
        
        for bar in bars:
            bos_system.update_bar(bar)
            
            if bos_system.has_bos_signal():
                signal = bos_system.get_bos_signal()
                
                if signal and 'strength' in signal:
                    strength = signal['strength']
                    # Strength should be between 0 and 1
                    assert 0.0 <= strength <= 1.0, \
                        f"BOS strength {strength} outside bounds [0.0, 1.0]"


class TestCombinedPropertyTests:
    """Property tests for combined system behavior"""
    
    @given(vwap_tick_data(), atr_bar_data())
    @settings(max_examples=PropertyTestConfig.MAX_EXAMPLES, deadline=PropertyTestConfig.DEADLINE)
    def test_vwap_atr_consistency(self, ticks, bars):
        """Test consistency between VWAP and ATR calculations"""
        symbol_config = {
            "symbol": "BTCUSDc",
            "session_type": "CRYPTO_24_7",
            "vwap_period": 60,
            "sigma_multiplier": 2.0
        }
        
        atr_config = SymbolATRConfig(
            symbol="BTCUSDc",
            m1_atr_period=14,
            m5_atr_period=14,
            ratio_multiplier=1.0,
            high_volatility_threshold=2.0
        )
        
        vwap_calc = AdvancedVWAPCalculator(symbol_config)
        atr_system = AdvancedATRRatioSystem("BTCUSDc", atr_config)
        
        # Process ticks for VWAP
        for tick in ticks:
            vwap_calc.update_tick(tick)
        
        # Process bars for ATR
        for bar in bars:
            atr_system.update_m1_bar(bar)
            atr_system.update_m5_bar(bar)
        
        # Both systems should have processed data
        vwap = vwap_calc.get_current_vwap()
        m1_atr = atr_system.get_m1_atr()
        
        if vwap is not None and m1_atr is not None:
            # VWAP and ATR should be in similar price ranges
            price_diff = abs(vwap - m1_atr)
            max_price = max(vwap, m1_atr)
            
            # Relative difference should be reasonable (within 50%)
            if max_price > 0:
                relative_diff = price_diff / max_price
                assert relative_diff <= 0.5, \
                    f"VWAP {vwap} and ATR {m1_atr} too different: {relative_diff:.2%}"
    
    @given(bos_bar_data(), atr_bar_data())
    @settings(max_examples=PropertyTestConfig.MAX_EXAMPLES, deadline=PropertyTestConfig.DEADLINE)
    def test_bos_atr_displacement_consistency(self, bos_bars, atr_bars):
        """Test consistency between BOS displacement and ATR values"""
        bos_config = MicroBOSConfig(
            symbol="BTCUSDc",
            bar_lookback=10,
            min_atr_displacement=0.5,
            cooldown_period_ms=300000  # 5 minutes
        )
        
        atr_config = SymbolATRConfig(
            symbol="BTCUSDc",
            m1_atr_period=14,
            m5_atr_period=14,
            ratio_multiplier=1.0,
            high_volatility_threshold=2.0
        )
        
        bos_system = AdvancedMicroBOSCHOCH("BTCUSDc", bos_config)
        atr_system = AdvancedATRRatioSystem("BTCUSDc", atr_config)
        
        # Process bars for both systems
        for bar in bos_bars:
            bos_system.update_bar(bar)
        
        for bar in atr_bars:
            atr_system.update_m1_bar(bar)
        
        # Check BOS signals
        if bos_system.has_bos_signal():
            signal = bos_system.get_bos_signal()
            m1_atr = atr_system.get_m1_atr()
            
            if signal and 'displacement' in signal and m1_atr is not None:
                displacement = signal['displacement']
                
                # Displacement should be reasonable relative to ATR
                if m1_atr > 0:
                    relative_displacement = displacement / m1_atr
                    # Should be between 0.1 and 5.0 ATR units
                    assert 0.1 <= relative_displacement <= 5.0, \
                        f"BOS displacement {displacement} relative to ATR {m1_atr}: {relative_displacement:.2f}"


class TestEdgeCasePropertyTests:
    """Property tests for edge cases and boundary conditions"""
    
    def test_empty_data_handling(self):
        """Test that systems handle empty data gracefully"""
        symbol_config = {
            "symbol": "BTCUSDc",
            "session_type": "CRYPTO_24_7",
            "vwap_period": 60,
            "sigma_multiplier": 2.0
        }
        
        vwap_calc = AdvancedVWAPCalculator(symbol_config)
        
        # Empty data should not crash
        assert vwap_calc.get_current_vwap() is None
        assert not vwap_calc.is_reclaim()
    
    def test_single_tick_handling(self):
        """Test that systems handle single tick gracefully"""
        symbol_config = {
            "symbol": "BTCUSDc",
            "session_type": "CRYPTO_24_7",
            "vwap_period": 60,
            "sigma_multiplier": 2.0
        }
        
        vwap_calc = AdvancedVWAPCalculator(symbol_config)
        
        # Single tick
        tick = TickEvent(
            symbol="BTCUSDc",
            timestamp_ms=int(time.time() * 1000),
            bid=50000.0,
            ask=50001.0,
            volume=1.0,
            source="mt5"
        )
        
        vwap_calc.update_tick(tick)
        vwap = vwap_calc.get_current_vwap()
        
        # Should handle single tick
        assert vwap is not None
        assert vwap > 0
    
    def test_extreme_values_handling(self):
        """Test that systems handle extreme values gracefully"""
        symbol_config = {
            "symbol": "BTCUSDc",
            "session_type": "CRYPTO_24_7",
            "vwap_period": 60,
            "sigma_multiplier": 2.0
        }
        
        vwap_calc = AdvancedVWAPCalculator(symbol_config)
        
        # Extreme values
        tick = TickEvent(
            symbol="BTCUSDc",
            timestamp_ms=int(time.time() * 1000),
            bid=0.000001,  # Very small price
            ask=1000000.0,  # Very large price
            volume=0.000001,  # Very small volume
            source="mt5"
        )
        
        vwap_calc.update_tick(tick)
        vwap = vwap_calc.get_current_vwap()
        
        # Should handle extreme values without crashing
        assert vwap is not None
        assert vwap > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
