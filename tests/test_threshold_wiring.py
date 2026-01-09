"""
Test threshold wiring for the main symbols
"""
import pytest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch

from config.symbol_config_loader import (
    SymbolConfigLoader, SymbolConfig, AssetType, SessionType,
    VWAPConfig, ATRConfig, DeltaConfig, MicroBOSConfig, 
    SpreadFilterConfig, RiskConfig, load_symbol_config
)


class TestThresholdWiring:
    """Test threshold wiring for main symbols"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.loader = SymbolConfigLoader(config_dir=self.temp_dir)
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_btcusdc_configuration(self):
        """Test BTCUSDc configuration thresholds"""
        # Load BTCUSDc configuration
        config = load_symbol_config("BTCUSDc")
        
        if config is None:
            # Create default configuration if not found
            config = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
            self.loader.save_symbol_config("BTCUSDc", config)
            config = load_symbol_config("BTCUSDc")
        
        assert config is not None
        assert config.symbol == "BTCUSDc"
        assert config.asset_type == AssetType.CRYPTO
        assert config.binance_symbol == "BTCUSDT"
        assert config.priority == 1
        assert config.enabled is True
        
        # Test VWAP configuration
        assert config.vwap.session_anchor == SessionType.CRYPTO_24_7
        assert config.vwap.sigma_window_minutes == 60
        assert config.vwap.min_volume_threshold == 0.01
        
        # Test ATR configuration
        assert config.atr.ratio_multiplier == 1.5
        assert config.atr.high_volatility_threshold == 3.0
        
        # Test risk configuration
        assert config.risk.max_lot_size == 0.1
        assert config.risk.daily_lot_limit == 2.0
        assert config.risk.hourly_lot_limit == 1.0
        assert config.risk.max_drawdown_pct == 5.0
        assert config.risk.circuit_breaker_threshold == 0.02
    
    def test_xauusdc_configuration(self):
        """Test XAUUSDc configuration thresholds"""
        # Load XAUUSDc configuration
        config = load_symbol_config("XAUUSDc")
        
        if config is None:
            # Create default configuration if not found
            config = self.loader.create_default_config("XAUUSDc", AssetType.COMMODITY)
            self.loader.save_symbol_config("XAUUSDc", config)
            config = load_symbol_config("XAUUSDc")
        
        assert config is not None
        assert config.symbol == "XAUUSDc"
        assert config.asset_type == AssetType.COMMODITY
        assert config.binance_symbol is None
        assert config.priority == 1
        assert config.enabled is True
        
        # Test VWAP configuration
        assert config.vwap.session_anchor == SessionType.LONDON
        assert config.vwap.sigma_window_minutes == 120
        assert config.vwap.min_volume_threshold == 0.01
        
        # Test ATR configuration
        assert config.atr.ratio_multiplier == 1.2
        assert config.atr.high_volatility_threshold == 2.5
        
        # Test risk configuration (more conservative for commodities)
        assert config.risk.max_lot_size == 0.05
        assert config.risk.daily_lot_limit == 0.5
        assert config.risk.hourly_lot_limit == 0.25
        assert config.risk.max_drawdown_pct == 3.0
        assert config.risk.circuit_breaker_threshold == 0.015
    
    def test_eurusdc_configuration(self):
        """Test EURUSDc configuration thresholds"""
        # Load EURUSDc configuration
        config = load_symbol_config("EURUSDc")
        
        if config is None:
            # Create default configuration if not found
            config = self.loader.create_default_config("EURUSDc", AssetType.FOREX)
            self.loader.save_symbol_config("EURUSDc", config)
            config = load_symbol_config("EURUSDc")
        
        assert config is not None
        assert config.symbol == "EURUSDc"
        assert config.asset_type == AssetType.FOREX
        assert config.binance_symbol is None
        assert config.priority == 1
        assert config.enabled is True
        
        # Test VWAP configuration
        assert config.vwap.session_anchor == SessionType.LONDON
        assert config.vwap.sigma_window_minutes == 60
        assert config.vwap.min_volume_threshold == 0.01
        
        # Test ATR configuration
        assert config.atr.ratio_multiplier == 1.0
        assert config.atr.high_volatility_threshold == 2.0
        
        # Test risk configuration
        assert config.risk.max_lot_size == 0.1
        assert config.risk.daily_lot_limit == 1.0
        assert config.risk.hourly_lot_limit == 0.5
        assert config.risk.max_drawdown_pct == 3.0
        assert config.risk.circuit_breaker_threshold == 0.015
    
    def test_gbpusdc_configuration(self):
        """Test GBPUSDc configuration thresholds"""
        # Load GBPUSDc configuration
        config = load_symbol_config("GBPUSDc")
        
        if config is None:
            # Create default configuration if not found
            config = self.loader.create_default_config("GBPUSDc", AssetType.FOREX)
            config.priority = 2  # Lower priority than EURUSDc
            self.loader.save_symbol_config("GBPUSDc", config)
            config = load_symbol_config("GBPUSDc")
        
        assert config is not None
        assert config.symbol == "GBPUSDc"
        assert config.asset_type == AssetType.FOREX
        assert config.binance_symbol is None
        assert config.priority == 2
        assert config.enabled is True
        
        # Test VWAP configuration
        assert config.vwap.session_anchor == SessionType.LONDON
        assert config.vwap.sigma_window_minutes == 60
        assert config.vwap.min_volume_threshold == 0.01
        
        # Test ATR configuration (slightly higher volatility for GBP)
        assert config.atr.ratio_multiplier == 1.1
        assert config.atr.high_volatility_threshold == 2.2
        
        # Test risk configuration
        assert config.risk.max_lot_size == 0.1
        assert config.risk.daily_lot_limit == 1.0
        assert config.risk.hourly_lot_limit == 0.5
        assert config.risk.max_drawdown_pct == 3.0
        assert config.risk.circuit_breaker_threshold == 0.015
    
    def test_usdjpyc_configuration(self):
        """Test USDJPYc configuration thresholds"""
        # Load USDJPYc configuration
        config = load_symbol_config("USDJPYc")
        
        if config is None:
            # Create default configuration if not found
            config = self.loader.create_default_config("USDJPYc", AssetType.FOREX)
            config.priority = 2  # Lower priority than EURUSDc
            self.loader.save_symbol_config("USDJPYc", config)
            config = load_symbol_config("USDJPYc")
        
        assert config is not None
        assert config.symbol == "USDJPYc"
        assert config.asset_type == AssetType.FOREX
        assert config.binance_symbol is None
        assert config.priority == 2
        assert config.enabled is True
        
        # Test VWAP configuration (Tokyo session for JPY)
        assert config.vwap.session_anchor == SessionType.TOKYO
        assert config.vwap.sigma_window_minutes == 60
        assert config.vwap.min_volume_threshold == 0.01
        
        # Test ATR configuration
        assert config.atr.ratio_multiplier == 1.0
        assert config.atr.high_volatility_threshold == 2.0
        
        # Test risk configuration
        assert config.risk.max_lot_size == 0.1
        assert config.risk.daily_lot_limit == 1.0
        assert config.risk.hourly_lot_limit == 0.5
        assert config.risk.max_drawdown_pct == 3.0
        assert config.risk.circuit_breaker_threshold == 0.015
    
    def test_all_main_symbols_loaded(self):
        """Test that all main symbols can be loaded"""
        main_symbols = ["BTCUSDc", "XAUUSDc", "EURUSDc", "GBPUSDc", "USDJPYc"]
        
        for symbol in main_symbols:
            config = load_symbol_config(symbol)
            if config is None:
                # Create default configuration if not found
                asset_type = AssetType.CRYPTO if symbol == "BTCUSDc" else AssetType.FOREX
                if symbol == "XAUUSDc":
                    asset_type = AssetType.COMMODITY
                
                config = self.loader.create_default_config(symbol, asset_type)
                self.loader.save_symbol_config(symbol, config)
                config = load_symbol_config(symbol)
            
            assert config is not None, f"Failed to load configuration for {symbol}"
            assert config.symbol == symbol
            assert config.enabled is True
    
    def test_priority_ordering(self):
        """Test that symbols are ordered by priority correctly"""
        # Load all configurations
        all_configs = self.loader.load_all_configs()
        
        # Get symbols by priority
        symbols_by_priority = self.loader.get_symbols_by_priority()
        
        # Check that priority 1 symbols come first
        priority_1_symbols = [symbol for symbol, config in all_configs.items() if config.priority == 1]
        priority_2_symbols = [symbol for symbol, config in all_configs.items() if config.priority == 2]
        
        for symbol in priority_1_symbols:
            assert symbol in symbols_by_priority
            priority_1_index = symbols_by_priority.index(symbol)
            for priority_2_symbol in priority_2_symbols:
                if priority_2_symbol in symbols_by_priority:
                    priority_2_index = symbols_by_priority.index(priority_2_symbol)
                    assert priority_1_index < priority_2_index
    
    def test_spread_filter_thresholds(self):
        """Test spread filter thresholds for different asset types"""
        # Test crypto (BTCUSDc) - higher thresholds
        btc_config = load_symbol_config("BTCUSDc")
        if btc_config is None:
            btc_config = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
        
        assert btc_config.spread_filter.normal_spread_threshold >= 2.0
        assert btc_config.spread_filter.elevated_spread_threshold >= 5.0
        assert btc_config.spread_filter.high_spread_threshold >= 10.0
        assert btc_config.spread_filter.extreme_spread_threshold >= 20.0
        
        # Test forex (EURUSDc) - lower thresholds
        eur_config = load_symbol_config("EURUSDc")
        if eur_config is None:
            eur_config = self.loader.create_default_config("EURUSDc", AssetType.FOREX)
        
        assert eur_config.spread_filter.normal_spread_threshold <= 1.0
        assert eur_config.spread_filter.elevated_spread_threshold <= 2.0
        assert eur_config.spread_filter.high_spread_threshold <= 4.0
        assert eur_config.spread_filter.extreme_spread_threshold <= 8.0
        
        # Test commodity (XAUUSDc) - medium thresholds
        xau_config = load_symbol_config("XAUUSDc")
        if xau_config is None:
            xau_config = self.loader.create_default_config("XAUUSDc", AssetType.COMMODITY)
        
        assert xau_config.spread_filter.normal_spread_threshold <= 2.0
        assert xau_config.spread_filter.elevated_spread_threshold <= 4.0
        assert xau_config.spread_filter.high_spread_threshold <= 8.0
        assert xau_config.spread_filter.extreme_spread_threshold <= 16.0
    
    def test_atr_ratio_multipliers(self):
        """Test ATR ratio multipliers for different asset types"""
        # Test crypto (BTCUSDc) - higher multiplier for volatility
        btc_config = load_symbol_config("BTCUSDc")
        if btc_config is None:
            btc_config = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
        
        assert btc_config.atr.ratio_multiplier >= 1.5
        assert btc_config.atr.high_volatility_threshold >= 3.0
        
        # Test forex (EURUSDc) - standard multiplier
        eur_config = load_symbol_config("EURUSDc")
        if eur_config is None:
            eur_config = self.loader.create_default_config("EURUSDc", AssetType.FOREX)
        
        assert eur_config.atr.ratio_multiplier == 1.0
        assert eur_config.atr.high_volatility_threshold == 2.0
        
        # Test commodity (XAUUSDc) - slightly higher multiplier
        xau_config = load_symbol_config("XAUUSDc")
        if xau_config is None:
            xau_config = self.loader.create_default_config("XAUUSDc", AssetType.COMMODITY)
        
        assert xau_config.atr.ratio_multiplier >= 1.2
        assert xau_config.atr.high_volatility_threshold >= 2.5
    
    def test_risk_limits_by_asset_type(self):
        """Test risk limits are appropriate for different asset types"""
        # Test crypto (BTCUSDc) - higher limits
        btc_config = load_symbol_config("BTCUSDc")
        if btc_config is None:
            btc_config = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
        
        assert btc_config.risk.max_lot_size == 0.1
        assert btc_config.risk.daily_lot_limit >= 2.0
        assert btc_config.risk.hourly_lot_limit >= 1.0
        assert btc_config.risk.max_drawdown_pct >= 5.0
        
        # Test forex (EURUSDc) - standard limits
        eur_config = load_symbol_config("EURUSDc")
        if eur_config is None:
            eur_config = self.loader.create_default_config("EURUSDc", AssetType.FOREX)
        
        assert eur_config.risk.max_lot_size == 0.1
        assert eur_config.risk.daily_lot_limit == 1.0
        assert eur_config.risk.hourly_lot_limit == 0.5
        assert eur_config.risk.max_drawdown_pct == 3.0
        
        # Test commodity (XAUUSDc) - conservative limits
        xau_config = load_symbol_config("XAUUSDc")
        if xau_config is None:
            xau_config = self.loader.create_default_config("XAUUSDc", AssetType.COMMODITY)
        
        assert xau_config.risk.max_lot_size <= 0.05
        assert xau_config.risk.daily_lot_limit <= 0.5
        assert xau_config.risk.hourly_lot_limit <= 0.25
        assert xau_config.risk.max_drawdown_pct <= 3.0
    
    def test_configuration_validation(self):
        """Test that all configurations pass validation"""
        main_symbols = ["BTCUSDc", "XAUUSDc", "EURUSDc", "GBPUSDc", "USDJPYc"]
        
        for symbol in main_symbols:
            config = load_symbol_config(symbol)
            if config is None:
                # Create default configuration if not found
                asset_type = AssetType.CRYPTO if symbol == "BTCUSDc" else AssetType.FOREX
                if symbol == "XAUUSDc":
                    asset_type = AssetType.COMMODITY
                
                config = self.loader.create_default_config(symbol, asset_type)
                self.loader.save_symbol_config(symbol, config)
                config = load_symbol_config(symbol)
            
            # Validate configuration
            errors = self.loader.validate_config(config)
            assert len(errors) == 0, f"Configuration validation failed for {symbol}: {errors}"
    
    def test_hot_reload_functionality(self):
        """Test hot reload functionality for configuration changes"""
        # Create initial configuration
        config = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
        config.priority = 1
        self.loader.save_symbol_config("BTCUSDc", config)
        
        # Load configuration
        initial_config = self.loader.load_symbol_config("BTCUSDc")
        assert initial_config.priority == 1
        
        # Modify configuration file directly
        config_file = Path(self.temp_dir) / "BTCUSDc.json"
        with open(config_file, 'r') as f:
            data = json.load(f)
        data['priority'] = 2
        with open(config_file, 'w') as f:
            json.dump(data, f)
        
        # Add small delay to ensure file modification time is updated
        import time
        time.sleep(0.1)
        
        # Force reload by calling load_symbol_config with force_reload=True
        self.loader.load_symbol_config("BTCUSDc", force_reload=True)
        
        # Verify configuration was updated
        updated_config = self.loader.get_config("BTCUSDc")
        assert updated_config.priority == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
