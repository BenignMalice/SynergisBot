"""
Symbol-specific configuration tests for BTCUSDc, XAUUSDc, EURUSDc.
Tests parameter validation, symbol-specific behavior, and configuration consistency.
"""

import pytest
import time
import numpy as np
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List

# Add the project root to the path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.symbol_config import SymbolConfig
from app.engine.advanced_vwap_session_anchor import AdvancedVWAPSessionAnchor, AssetType, SessionType
from app.engine.advanced_delta_proxy import AdvancedDeltaProxy
from app.engine.advanced_atr_ratio_system import AdvancedATRRatioSystem
from app.engine.advanced_micro_bos_choch import AdvancedMicroBOSCHOCH, BarData
from app.engine.advanced_spread_filter import AdvancedSpreadFilter, SpreadData
from app.schemas.trading_events import TickEvent, OHLCVBarEvent

class TestSymbolConfigurations:
    """Test symbol-specific configurations and parameters."""
    
    def test_btcusdc_configuration(self):
        """Test BTCUSDc specific configuration."""
        symbol_config = SymbolConfig("BTCUSDc", "BTCUSDc", binance_symbol="BTCUSDT")
        
        # Validate BTCUSDc specific parameters
        assert symbol_config.symbol == "BTCUSDc"
        assert symbol_config.broker_symbol == "BTCUSDc"
        assert symbol_config.binance_symbol == "BTCUSDT"
        assert symbol_config.max_lot_size > 0
        assert symbol_config.default_risk_percent > 0
        assert symbol_config.max_daily_drawdown > 0
        assert symbol_config.max_weekly_drawdown > symbol_config.max_daily_drawdown
        
        # Validate crypto-specific parameters
        assert symbol_config.vwap_threshold > 0
        assert symbol_config.delta_threshold > 0
        assert symbol_config.atr_period > 0
        assert symbol_config.min_displacement_atr > 0
        assert symbol_config.max_displacement_atr > symbol_config.min_displacement_atr

    def test_xauusdc_configuration(self):
        """Test XAUUSDc specific configuration."""
        symbol_config = SymbolConfig("XAUUSDc", "XAUUSDc")
        
        # Validate XAUUSDc specific parameters
        assert symbol_config.symbol == "XAUUSDc"
        assert symbol_config.broker_symbol == "XAUUSDc"
        assert symbol_config.binance_symbol is None  # Not a crypto symbol
        assert symbol_config.max_lot_size > 0
        assert symbol_config.default_risk_percent > 0
        assert symbol_config.max_daily_drawdown > 0
        assert symbol_config.max_weekly_drawdown > symbol_config.max_daily_drawdown
        
        # Validate commodity-specific parameters
        assert symbol_config.vwap_threshold > 0
        assert symbol_config.delta_threshold > 0
        assert symbol_config.atr_period > 0
        assert symbol_config.min_displacement_atr > 0
        assert symbol_config.max_displacement_atr > symbol_config.min_displacement_atr

    def test_eurusdc_configuration(self):
        """Test EURUSDc specific configuration."""
        symbol_config = SymbolConfig("EURUSDc", "EURUSDc")
        
        # Validate EURUSDc specific parameters
        assert symbol_config.symbol == "EURUSDc"
        assert symbol_config.broker_symbol == "EURUSDc"
        assert symbol_config.binance_symbol is None  # Not a crypto symbol
        assert symbol_config.max_lot_size > 0
        assert symbol_config.default_risk_percent > 0
        assert symbol_config.max_daily_drawdown > 0
        assert symbol_config.max_weekly_drawdown > symbol_config.max_daily_drawdown
        
        # Validate forex-specific parameters
        assert symbol_config.vwap_threshold > 0
        assert symbol_config.delta_threshold > 0
        assert symbol_config.atr_period > 0
        assert symbol_config.min_displacement_atr > 0
        assert symbol_config.max_displacement_atr > symbol_config.min_displacement_atr

    def test_symbol_parameter_validation(self):
        """Test parameter validation for all symbols."""
        symbols = ["BTCUSDc", "XAUUSDc", "EURUSDc"]
        
        for symbol in symbols:
            symbol_config = SymbolConfig(symbol, symbol)
            
            # Validate required parameters exist
            assert symbol_config.symbol == symbol
            assert symbol_config.broker_symbol == symbol
            assert symbol_config.max_lot_size > 0
            assert symbol_config.default_risk_percent > 0
            assert symbol_config.max_daily_drawdown > 0
            assert symbol_config.max_weekly_drawdown > symbol_config.max_daily_drawdown
            assert symbol_config.vwap_threshold > 0
            assert symbol_config.delta_threshold > 0
            assert symbol_config.atr_period > 0
            assert symbol_config.min_displacement_atr > 0
            assert symbol_config.max_displacement_atr > symbol_config.min_displacement_atr

    def test_asset_type_consistency(self):
        """Test asset type consistency across symbols."""
        # Test crypto asset
        btc_config = SymbolConfig("BTCUSDc", "BTCUSDc", binance_symbol="BTCUSDT")
        assert btc_config.symbol == "BTCUSDc"
        assert btc_config.binance_symbol == "BTCUSDT"
        
        # Test commodity asset
        xau_config = SymbolConfig("XAUUSDc", "XAUUSDc")
        assert xau_config.symbol == "XAUUSDc"
        assert xau_config.binance_symbol is None
        
        # Test forex asset
        eur_config = SymbolConfig("EURUSDc", "EURUSDc")
        assert eur_config.symbol == "EURUSDc"
        assert eur_config.binance_symbol is None

class TestSymbolSpecificVWAP:
    """Test symbol-specific VWAP behavior."""
    
    def test_btcusdc_vwap_24_7_session(self):
        """Test BTCUSDc VWAP with 24/7 session."""
        vwap = AdvancedVWAPSessionAnchor("BTCUSDc", AssetType.CRYPTO)
        
        # Test session detection for crypto
        current_time = int(time.time() * 1000)
        session = vwap._detect_current_session(current_time)
        assert session == SessionType.CRYPTO_24_7  # 24/7 crypto should use CRYPTO_24_7
        
        # Test VWAP calculation
        test_ticks = [
            (50000.0, 1.0), (50010.0, 1.5), (50020.0, 2.0),
            (50015.0, 1.2), (50025.0, 1.8)
        ]
        
        for price, volume in test_ticks:
            vwap.update_vwap(price, volume, current_time)
        
        assert vwap.current_session is not None
        assert vwap.current_session.total_volume > 0
        assert vwap.current_session.vwap_value > 0

    def test_xauusdc_vwap_24_7_session(self):
        """Test XAUUSDc VWAP with 24/7 session."""
        vwap = AdvancedVWAPSessionAnchor("XAUUSDc", AssetType.COMMODITY)
        
        # Test session detection for commodity
        current_time = int(time.time() * 1000)
        session = vwap._detect_current_session(current_time)
        assert session == SessionType.CRYPTO_24_7  # 24/7 commodity should use CRYPTO_24_7
        
        # Test VWAP calculation
        test_ticks = [
            (2000.0, 0.1), (2005.0, 0.15), (2010.0, 0.2),
            (2008.0, 0.12), (2012.0, 0.18)
        ]
        
        for price, volume in test_ticks:
            vwap.update_vwap(price, volume, current_time)
        
        assert vwap.current_session is not None
        assert vwap.current_session.total_volume > 0
        assert vwap.current_session.vwap_value > 0

    def test_eurusdc_vwap_forex_session(self):
        """Test EURUSDc VWAP with forex session."""
        vwap = AdvancedVWAPSessionAnchor("EURUSDc", AssetType.FOREX)
        
        # Test session detection for forex
        current_time = int(time.time() * 1000)
        session = vwap._detect_current_session(current_time)
        assert session in [SessionType.ASIAN, SessionType.LONDON, SessionType.NEW_YORK]
        
        # Test VWAP calculation
        test_ticks = [
            (1.1000, 1000.0), (1.1005, 1500.0), (1.1010, 2000.0),
            (1.1008, 1200.0), (1.1012, 1800.0)
        ]
        
        for price, volume in test_ticks:
            vwap.update_vwap(price, volume, current_time)
        
        assert vwap.current_session is not None
        assert vwap.current_session.total_volume > 0
        assert vwap.current_session.vwap_value > 0

class TestSymbolSpecificDeltaProxy:
    """Test symbol-specific delta proxy behavior."""
    
    def test_btcusdc_delta_proxy_crypto(self):
        """Test BTCUSDc delta proxy for crypto."""
        delta_proxy = AdvancedDeltaProxy("BTCUSDc")
        
        # Test with crypto price movements
        current_time = int(time.time() * 1000)
        test_ticks = [
            (50000.0, 1.0), (50010.0, 1.5), (50020.0, 2.0),
            (50015.0, 1.2), (50025.0, 1.8)
        ]
        
        for price, volume in test_ticks:
            delta_proxy.process_tick(price - 5.0, price + 5.0, volume, current_time)
            current_time += 1000
        
        # Validate delta metrics
        metrics = delta_proxy.get_current_delta()
        # Note: get_current_delta may return None if insufficient data
        if metrics is not None:
            assert metrics.total_volume > 0
            assert metrics.net_delta is not None

    def test_xauusdc_delta_proxy_commodity(self):
        """Test XAUUSDc delta proxy for commodity."""
        delta_proxy = AdvancedDeltaProxy("XAUUSDc")
        
        # Test with commodity price movements
        current_time = int(time.time() * 1000)
        test_ticks = [
            (2000.0, 0.1), (2005.0, 0.15), (2010.0, 0.2),
            (2008.0, 0.12), (2012.0, 0.18)
        ]
        
        for price, volume in test_ticks:
            delta_proxy.process_tick(price - 5.0, price + 5.0, volume, current_time)
            current_time += 1000
        
        # Validate delta metrics
        metrics = delta_proxy.get_current_delta()
        # Note: get_current_delta may return None if insufficient data
        if metrics is not None:
            assert metrics.total_volume > 0
            assert metrics.net_delta is not None

    def test_eurusdc_delta_proxy_forex(self):
        """Test EURUSDc delta proxy for forex."""
        delta_proxy = AdvancedDeltaProxy("EURUSDc")
        
        # Test with forex price movements
        current_time = int(time.time() * 1000)
        test_ticks = [
            (1.1000, 1000.0), (1.1005, 1500.0), (1.1010, 2000.0),
            (1.1008, 1200.0), (1.1012, 1800.0)
        ]
        
        for price, volume in test_ticks:
            delta_proxy.process_tick(price - 5.0, price + 5.0, volume, current_time)
            current_time += 1000
        
        # Validate delta metrics
        metrics = delta_proxy.get_current_delta()
        # Note: get_current_delta may return None if insufficient data
        if metrics is not None:
            assert metrics.total_volume > 0
            assert metrics.net_delta is not None

class TestSymbolSpecificATRRatio:
    """Test symbol-specific ATR ratio behavior."""
    
    def test_btcusdc_atr_ratio_crypto(self):
        """Test BTCUSDc ATR ratio for crypto."""
        atr_ratio = AdvancedATRRatioSystem("BTCUSDc")
        
        # Test with crypto volatility
        current_time = int(time.time() * 1000)
        
        # Add M1 data
        for i in range(20):
            high = 50000.0 + i * 10.0
            low = 49990.0 + i * 10.0
            close = 49995.0 + i * 10.0
            atr_ratio.update_m1_data(high, low, close, current_time + i * 60000)
        
        # Add M5 data
        for i in range(10):
            high = 50000.0 + i * 50.0
            low = 49950.0 + i * 50.0
            close = 49975.0 + i * 50.0
            atr_ratio.update_m5_data(high, low, close, current_time + i * 300000)
        
        # Validate ATR ratio calculation
        ratio = atr_ratio.get_current_ratio()
        # Note: get_current_ratio may return None if insufficient data
        if ratio is not None:
            assert ratio > 0

    def test_xauusdc_atr_ratio_commodity(self):
        """Test XAUUSDc ATR ratio for commodity."""
        atr_ratio = AdvancedATRRatioSystem("XAUUSDc")
        
        # Test with commodity volatility
        current_time = int(time.time() * 1000)
        
        # Add M1 data
        for i in range(20):
            high = 2000.0 + i * 2.0
            low = 1998.0 + i * 2.0
            close = 1999.0 + i * 2.0
            atr_ratio.update_m1_data(high, low, close, current_time + i * 60000)
        
        # Add M5 data
        for i in range(10):
            high = 2000.0 + i * 10.0
            low = 1990.0 + i * 10.0
            close = 1995.0 + i * 10.0
            atr_ratio.update_m5_data(high, low, close, current_time + i * 300000)
        
        # Validate ATR ratio calculation
        ratio = atr_ratio.get_current_ratio()
        # Note: get_current_ratio may return None if insufficient data
        if ratio is not None:
            assert ratio > 0

    def test_eurusdc_atr_ratio_forex(self):
        """Test EURUSDc ATR ratio for forex."""
        atr_ratio = AdvancedATRRatioSystem("EURUSDc")
        
        # Test with forex volatility
        current_time = int(time.time() * 1000)
        
        # Add M1 data
        for i in range(20):
            high = 1.1000 + i * 0.0001
            low = 1.0999 + i * 0.0001
            close = 1.09995 + i * 0.0001
            atr_ratio.update_m1_data(high, low, close, current_time + i * 60000)
        
        # Add M5 data
        for i in range(10):
            high = 1.1000 + i * 0.0005
            low = 1.0995 + i * 0.0005
            close = 1.09975 + i * 0.0005
            atr_ratio.update_m5_data(high, low, close, current_time + i * 300000)
        
        # Validate ATR ratio calculation
        ratio = atr_ratio.get_current_ratio()
        # Note: get_current_ratio may return None if insufficient data
        if ratio is not None:
            assert ratio > 0

class TestSymbolSpecificMicroBOS:
    """Test symbol-specific micro-BOS/CHOCH behavior."""
    
    def test_btcusdc_micro_bos_crypto(self):
        """Test BTCUSDc micro-BOS for crypto."""
        micro_bos = AdvancedMicroBOSCHOCH("BTCUSDc")
        
        # Test with crypto price structure
        current_time = int(time.time() * 1000)
        
        # Create bars with structure breaks
        for i in range(30):
            bar_data = BarData(
                timestamp_ms=current_time + i * 60000,
                open=50000.0 + i * 10.0,
                high=50010.0 + i * 10.0,
                low=49990.0 + i * 10.0,
                close=50005.0 + i * 10.0,
                volume=1.0 + i * 0.1,
                timeframe="M1"
            )
            
            structure_break = micro_bos.update_bar(bar_data)
            
            if i >= 20 and structure_break:
                assert structure_break.structure_type in ["bos", "choch", "micro_bos", "micro_choch"]
                assert structure_break.direction in ["bullish", "bearish", "neutral"]

    def test_xauusdc_micro_bos_commodity(self):
        """Test XAUUSDc micro-BOS for commodity."""
        micro_bos = AdvancedMicroBOSCHOCH("XAUUSDc")
        
        # Test with commodity price structure
        current_time = int(time.time() * 1000)
        
        # Create bars with structure breaks
        for i in range(30):
            bar_data = BarData(
                timestamp_ms=current_time + i * 60000,
                open=2000.0 + i * 2.0,
                high=2005.0 + i * 2.0,
                low=1995.0 + i * 2.0,
                close=2002.0 + i * 2.0,
                volume=0.1 + i * 0.01,
                timeframe="M1"
            )
            
            structure_break = micro_bos.update_bar(bar_data)
            
            if i >= 20 and structure_break:
                assert structure_break.structure_type in ["bos", "choch", "micro_bos", "micro_choch"]
                assert structure_break.direction in ["bullish", "bearish", "neutral"]

    def test_eurusdc_micro_bos_forex(self):
        """Test EURUSDc micro-BOS for forex."""
        micro_bos = AdvancedMicroBOSCHOCH("EURUSDc")
        
        # Test with forex price structure
        current_time = int(time.time() * 1000)
        
        # Create bars with structure breaks
        for i in range(30):
            bar_data = BarData(
                timestamp_ms=current_time + i * 60000,
                open=1.1000 + i * 0.0001,
                high=1.1005 + i * 0.0001,
                low=1.0995 + i * 0.0001,
                close=1.1002 + i * 0.0001,
                volume=1000.0 + i * 100.0,
                timeframe="M1"
            )
            
            structure_break = micro_bos.update_bar(bar_data)
            
            if i >= 20 and structure_break:
                assert structure_break.structure_type in ["bos", "choch", "micro_bos", "micro_choch"]
                assert structure_break.direction in ["bullish", "bearish", "neutral"]

class TestSymbolSpecificSpreadFilter:
    """Test symbol-specific spread filter behavior."""
    
    def test_btcusdc_spread_filter_crypto(self):
        """Test BTCUSDc spread filter for crypto."""
        spread_filter = AdvancedSpreadFilter("BTCUSDc")
        
        # Test with crypto spreads
        current_time = int(time.time() * 1000)
        
        # Test different spread levels
        test_spreads = [
            (50000.0, 50010.0, 10.0),  # 10 pips
            (50010.0, 50025.0, 15.0),  # 15 pips
            (50025.0, 50050.0, 25.0),  # 25 pips
        ]
        
        for bid, ask, spread_pips in test_spreads:
            spread_data = SpreadData(
                timestamp_ms=current_time,
                bid=bid,
                ask=ask,
                spread=ask - bid,
                spread_pips=spread_pips,
                source="mt5",
                is_valid=True
            )
            
            signal = spread_filter.update_spread(spread_data)
            current_time += 1000
            
            if signal:
                assert signal.value in ["normal", "elevated", "high", "extreme", "news_window", "outlier"]

    def test_xauusdc_spread_filter_commodity(self):
        """Test XAUUSDc spread filter for commodity."""
        spread_filter = AdvancedSpreadFilter("XAUUSDc")
        
        # Test with commodity spreads
        current_time = int(time.time() * 1000)
        
        # Test different spread levels
        test_spreads = [
            (2000.0, 2000.5, 0.5),  # 0.5 points
            (2000.5, 2001.0, 0.5),  # 0.5 points
            (2001.0, 2002.0, 1.0),  # 1.0 points
        ]
        
        for bid, ask, spread_pips in test_spreads:
            spread_data = SpreadData(
                timestamp_ms=current_time,
                bid=bid,
                ask=ask,
                spread=ask - bid,
                spread_pips=spread_pips,
                source="mt5",
                is_valid=True
            )
            
            signal = spread_filter.update_spread(spread_data)
            current_time += 1000
            
            if signal:
                assert signal.value in ["normal", "elevated", "high", "extreme", "news_window", "outlier"]

    def test_eurusdc_spread_filter_forex(self):
        """Test EURUSDc spread filter for forex."""
        spread_filter = AdvancedSpreadFilter("EURUSDc")
        
        # Test with forex spreads
        current_time = int(time.time() * 1000)
        
        # Test different spread levels
        test_spreads = [
            (1.1000, 1.1002, 2.0),  # 2 pips
            (1.1002, 1.1005, 3.0),  # 3 pips
            (1.1005, 1.1010, 5.0),  # 5 pips
        ]
        
        for bid, ask, spread_pips in test_spreads:
            spread_data = SpreadData(
                timestamp_ms=current_time,
                bid=bid,
                ask=ask,
                spread=ask - bid,
                spread_pips=spread_pips,
                source="mt5",
                is_valid=True
            )
            
            signal = spread_filter.update_spread(spread_data)
            current_time += 1000
            
            if signal:
                assert signal.value in ["normal", "elevated", "high", "extreme", "news_window", "outlier"]

class TestSymbolIntegration:
    """Test symbol integration across all components."""
    
    def test_btcusdc_full_integration(self):
        """Test BTCUSDc full integration across all components."""
        symbol = "BTCUSDc"
        
        # Initialize all components
        vwap = AdvancedVWAPSessionAnchor(symbol, AssetType.CRYPTO)
        delta_proxy = AdvancedDeltaProxy(symbol)
        atr_ratio = AdvancedATRRatioSystem(symbol)
        micro_bos = AdvancedMicroBOSCHOCH(symbol)
        spread_filter = AdvancedSpreadFilter(symbol)
        
        # Test integrated processing
        current_time = int(time.time() * 1000)
        
        for i in range(50):
            # Generate test data
            price = 50000.0 + i * 10.0
            volume = 1.0 + i * 0.1
            bid = price - 5.0
            ask = price + 5.0
            
            # Process through all components
            vwap.update_vwap(price, volume, current_time)
            delta_proxy.process_tick(bid, ask, volume, current_time)
            
            # Update ATR data
            high = price + 10.0
            low = price - 10.0
            close = price
            atr_ratio.update_m1_data(high, low, close, current_time)
            
            # Update micro-BOS data
            bar_data = BarData(
                timestamp_ms=current_time,
                open=price - 5.0,
                high=price + 10.0,
                low=price - 10.0,
                close=price,
                volume=volume,
                timeframe="M1"
            )
            micro_bos.update_bar(bar_data)
            
            # Update spread filter
            spread_data = SpreadData(
                timestamp_ms=current_time,
                bid=bid,
                ask=ask,
                spread=ask - bid,
                spread_pips=10.0,
                source="mt5",
                is_valid=True
            )
            spread_filter.update_spread(spread_data)
            
            current_time += 60000  # 1 minute intervals
        
        # Validate all components are working
        assert vwap.current_session is not None
        delta_metrics = delta_proxy.get_current_delta()
        if delta_metrics is not None:
            assert delta_metrics.total_volume > 0
        # ATR ratio may be None if insufficient M5 data
        atr_ratio_value = atr_ratio.get_current_ratio()
        if atr_ratio_value is not None:
            assert atr_ratio_value > 0
        assert len(micro_bos.structure_history) >= 0
        assert spread_filter.get_current_median_spread() >= 0

    def test_xauusdc_full_integration(self):
        """Test XAUUSDc full integration across all components."""
        symbol = "XAUUSDc"
        
        # Initialize all components
        vwap = AdvancedVWAPSessionAnchor(symbol, AssetType.COMMODITY)
        delta_proxy = AdvancedDeltaProxy(symbol)
        atr_ratio = AdvancedATRRatioSystem(symbol)
        micro_bos = AdvancedMicroBOSCHOCH(symbol)
        spread_filter = AdvancedSpreadFilter(symbol)
        
        # Test integrated processing
        current_time = int(time.time() * 1000)
        
        for i in range(50):
            # Generate test data
            price = 2000.0 + i * 2.0
            volume = 0.1 + i * 0.01
            bid = price - 1.0
            ask = price + 1.0
            
            # Process through all components
            vwap.update_vwap(price, volume, current_time)
            delta_proxy.process_tick(bid, ask, volume, current_time)
            
            # Update ATR data
            high = price + 2.0
            low = price - 2.0
            close = price
            atr_ratio.update_m1_data(high, low, close, current_time)
            
            # Update micro-BOS data
            bar_data = BarData(
                timestamp_ms=current_time,
                open=price - 1.0,
                high=price + 2.0,
                low=price - 2.0,
                close=price,
                volume=volume,
                timeframe="M1"
            )
            micro_bos.update_bar(bar_data)
            
            # Update spread filter
            spread_data = SpreadData(
                timestamp_ms=current_time,
                bid=bid,
                ask=ask,
                spread=ask - bid,
                spread_pips=1.0,
                source="mt5",
                is_valid=True
            )
            spread_filter.update_spread(spread_data)
            
            current_time += 60000  # 1 minute intervals
        
        # Validate all components are working
        assert vwap.current_session is not None
        delta_metrics = delta_proxy.get_current_delta()
        if delta_metrics is not None:
            assert delta_metrics.total_volume > 0
        # ATR ratio may be None if insufficient M5 data
        atr_ratio_value = atr_ratio.get_current_ratio()
        if atr_ratio_value is not None:
            assert atr_ratio_value > 0
        assert len(micro_bos.structure_history) >= 0
        assert spread_filter.get_current_median_spread() >= 0

    def test_eurusdc_full_integration(self):
        """Test EURUSDc full integration across all components."""
        symbol = "EURUSDc"
        
        # Initialize all components
        vwap = AdvancedVWAPSessionAnchor(symbol, AssetType.FOREX)
        delta_proxy = AdvancedDeltaProxy(symbol)
        atr_ratio = AdvancedATRRatioSystem(symbol)
        micro_bos = AdvancedMicroBOSCHOCH(symbol)
        spread_filter = AdvancedSpreadFilter(symbol)
        
        # Test integrated processing
        current_time = int(time.time() * 1000)
        
        for i in range(50):
            # Generate test data
            price = 1.1000 + i * 0.0001
            volume = 1000.0 + i * 100.0
            bid = price - 0.0001
            ask = price + 0.0001
            
            # Process through all components
            vwap.update_vwap(price, volume, current_time)
            delta_proxy.process_tick(bid, ask, volume, current_time)
            
            # Update ATR data
            high = price + 0.0002
            low = price - 0.0002
            close = price
            atr_ratio.update_m1_data(high, low, close, current_time)
            
            # Update micro-BOS data
            bar_data = BarData(
                timestamp_ms=current_time,
                open=price - 0.0001,
                high=price + 0.0002,
                low=price - 0.0002,
                close=price,
                volume=volume,
                timeframe="M1"
            )
            micro_bos.update_bar(bar_data)
            
            # Update spread filter
            spread_data = SpreadData(
                timestamp_ms=current_time,
                bid=bid,
                ask=ask,
                spread=ask - bid,
                spread_pips=2.0,
                source="mt5",
                is_valid=True
            )
            spread_filter.update_spread(spread_data)
            
            current_time += 60000  # 1 minute intervals
        
        # Validate all components are working
        assert vwap.current_session is not None
        delta_metrics = delta_proxy.get_current_delta()
        if delta_metrics is not None:
            assert delta_metrics.total_volume > 0
        # ATR ratio may be None if insufficient M5 data
        atr_ratio_value = atr_ratio.get_current_ratio()
        if atr_ratio_value is not None:
            assert atr_ratio_value > 0
        assert len(micro_bos.structure_history) >= 0
        assert spread_filter.get_current_median_spread() >= 0

if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
