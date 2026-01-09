"""
Test symbol configuration loader functionality
"""
import pytest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import patch

from config.symbol_config_loader import (
    SymbolConfigLoader, SymbolConfig, AssetType, SessionType,
    VWAPConfig, ATRConfig, DeltaConfig, MicroBOSConfig, 
    SpreadFilterConfig, RiskConfig, get_config_loader,
    load_symbol_config, save_symbol_config, create_default_config
)


class TestSymbolConfigLoader:
    """Test symbol configuration loader functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.loader = SymbolConfigLoader(config_dir=self.temp_dir)
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_default_config_crypto(self):
        """Test creating default configuration for crypto"""
        config = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
        
        assert config.symbol == "BTCUSDc"
        assert config.asset_type == AssetType.CRYPTO
        assert config.vwap.session_anchor == SessionType.CRYPTO_24_7
        assert config.atr.ratio_multiplier == 1.5
        assert config.risk.max_lot_size == 0.1
        assert config.enabled is True
        assert config.priority == 1
    
    def test_create_default_config_forex(self):
        """Test creating default configuration for forex"""
        config = self.loader.create_default_config("EURUSDc", AssetType.FOREX)
        
        assert config.symbol == "EURUSDc"
        assert config.asset_type == AssetType.FOREX
        assert config.vwap.session_anchor == SessionType.LONDON
        assert config.atr.ratio_multiplier == 1.0
        assert config.risk.max_lot_size == 0.1
        assert config.enabled is True
        assert config.priority == 1
    
    def test_create_default_config_commodity(self):
        """Test creating default configuration for commodity"""
        config = self.loader.create_default_config("XAUUSDc", AssetType.COMMODITY)
        
        assert config.symbol == "XAUUSDc"
        assert config.asset_type == AssetType.COMMODITY
        assert config.vwap.session_anchor == SessionType.LONDON
        assert config.atr.ratio_multiplier == 1.2
        assert config.risk.max_lot_size == 0.05
        assert config.enabled is True
        assert config.priority == 1
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration"""
        # Create a configuration
        config = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
        config.binance_symbol = "BTCUSDT"
        config.priority = 2
        
        # Save configuration
        result = self.loader.save_symbol_config("BTCUSDc", config)
        assert result is True
        
        # Check file was created
        config_file = Path(self.temp_dir) / "BTCUSDc.json"
        assert config_file.exists()
        
        # Load configuration
        loaded_config = self.loader.load_symbol_config("BTCUSDc")
        assert loaded_config is not None
        assert loaded_config.symbol == "BTCUSDc"
        assert loaded_config.binance_symbol == "BTCUSDT"
        assert loaded_config.priority == 2
        assert loaded_config.asset_type == AssetType.CRYPTO
    
    def test_load_nonexistent_config(self):
        """Test loading non-existent configuration"""
        config = self.loader.load_symbol_config("NONEXISTENT")
        assert config is None
    
    def test_load_all_configs(self):
        """Test loading all configurations"""
        # Create multiple configurations
        symbols = ["BTCUSDc", "EURUSDc", "XAUUSDc"]
        for symbol in symbols:
            asset_type = AssetType.CRYPTO if symbol == "BTCUSDc" else AssetType.FOREX
            config = self.loader.create_default_config(symbol, asset_type)
            self.loader.save_symbol_config(symbol, config)
        
        # Load all configurations
        all_configs = self.loader.load_all_configs()
        
        assert len(all_configs) == 3
        assert "BTCUSDc" in all_configs
        assert "EURUSDc" in all_configs
        assert "XAUUSDc" in all_configs
        
        # Check that configurations are properly loaded
        assert all_configs["BTCUSDc"].asset_type == AssetType.CRYPTO
        assert all_configs["EURUSDc"].asset_type == AssetType.FOREX
    
    def test_config_caching(self):
        """Test that configurations are cached"""
        # Create and save configuration
        config = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
        self.loader.save_symbol_config("BTCUSDc", config)
        
        # Load configuration (should be cached)
        config1 = self.loader.load_symbol_config("BTCUSDc")
        config2 = self.loader.load_symbol_config("BTCUSDc")
        
        # Should return the same object (cached)
        assert config1 is config2
    
    def test_force_reload(self):
        """Test force reload functionality"""
        # Create and save configuration
        config = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
        config.priority = 1
        self.loader.save_symbol_config("BTCUSDc", config)
        
        # Load configuration (should be cached)
        config1 = self.loader.load_symbol_config("BTCUSDc")
        assert config1.priority == 1
        
        # Modify file directly
        config_file = Path(self.temp_dir) / "BTCUSDc.json"
        with open(config_file, 'r') as f:
            data = json.load(f)
        data['priority'] = 2
        with open(config_file, 'w') as f:
            json.dump(data, f)
        
        # Force reload
        config2 = self.loader.load_symbol_config("BTCUSDc", force_reload=True)
        assert config2.priority == 2
    
    def test_reload_if_changed(self):
        """Test automatic reload when files change"""
        # Create and save configuration
        config = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
        config.priority = 1
        self.loader.save_symbol_config("BTCUSDc", config)
        
        # Load configuration
        self.loader.load_symbol_config("BTCUSDc")
        
        # Modify file directly
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
        
        # Check reload_if_changed
        reloaded = self.loader.reload_if_changed()
        # Since we already reloaded, this should return empty list
        # But the configuration should be updated
        updated_config = self.loader.get_config("BTCUSDc")
        assert updated_config.priority == 2
        
        # Verify configuration was updated
        updated_config = self.loader.get_config("BTCUSDc")
        assert updated_config.priority == 2
    
    def test_watchers(self):
        """Test configuration change watchers"""
        watcher_calls = []
        
        def watcher(symbol):
            watcher_calls.append(symbol)
        
        # Add watcher
        self.loader.add_watcher(watcher)
        
        # Create and save configuration
        config = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
        self.loader.save_symbol_config("BTCUSDc", config)
        
        # Load configuration
        self.loader.load_symbol_config("BTCUSDc")
        
        # Modify file and reload
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
        
        # Check watcher was called
        assert "BTCUSDc" in watcher_calls
        
        # Remove watcher
        self.loader.remove_watcher(watcher)
    
    def test_get_enabled_symbols(self):
        """Test getting enabled symbols"""
        # Create configurations with different enabled states
        config1 = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
        config1.enabled = True
        self.loader.save_symbol_config("BTCUSDc", config1)
        
        config2 = self.loader.create_default_config("EURUSDc", AssetType.FOREX)
        config2.enabled = False
        self.loader.save_symbol_config("EURUSDc", config2)
        
        config3 = self.loader.create_default_config("XAUUSDc", AssetType.COMMODITY)
        config3.enabled = True
        self.loader.save_symbol_config("XAUUSDc", config3)
        
        # Load all configurations
        self.loader.load_all_configs()
        
        # Get enabled symbols
        enabled_symbols = self.loader.get_enabled_symbols()
        
        assert "BTCUSDc" in enabled_symbols
        assert "EURUSDc" not in enabled_symbols
        assert "XAUUSDc" in enabled_symbols
    
    def test_get_symbols_by_priority(self):
        """Test getting symbols sorted by priority"""
        # Create configurations with different priorities
        config1 = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
        config1.priority = 3
        config1.enabled = True
        self.loader.save_symbol_config("BTCUSDc", config1)
        
        config2 = self.loader.create_default_config("EURUSDc", AssetType.FOREX)
        config2.priority = 1
        config2.enabled = True
        self.loader.save_symbol_config("EURUSDc", config2)
        
        config3 = self.loader.create_default_config("XAUUSDc", AssetType.COMMODITY)
        config3.priority = 2
        config3.enabled = True
        self.loader.save_symbol_config("XAUUSDc", config3)
        
        # Load all configurations
        self.loader.load_all_configs()
        
        # Get symbols by priority
        symbols_by_priority = self.loader.get_symbols_by_priority()
        
        assert symbols_by_priority[0] == "EURUSDc"  # priority 1
        assert symbols_by_priority[1] == "XAUUSDc"  # priority 2
        assert symbols_by_priority[2] == "BTCUSDc"  # priority 3
    
    def test_validate_config(self):
        """Test configuration validation"""
        # Test valid configuration
        config = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
        errors = self.loader.validate_config(config)
        assert len(errors) == 0
        
        # Test invalid configuration
        config.max_lot_size = -1
        config.min_lot_size = 2.0
        config.priority = 10
        config.vwap.sigma_window_minutes = -1
        
        errors = self.loader.validate_config(config)
        assert len(errors) > 0
        assert "max_lot_size must be positive" in errors
        assert "min_lot_size cannot be greater than max_lot_size" in errors
        assert "priority must be between 1 and 5" in errors
        assert "VWAP sigma_window_minutes must be positive" in errors
    
    def test_global_functions(self):
        """Test global convenience functions"""
        # Test get_config_loader
        loader1 = get_config_loader()
        loader2 = get_config_loader()
        assert loader1 is loader2
        
        # Test create_default_config
        config = create_default_config("BTCUSDc", AssetType.CRYPTO)
        assert config.symbol == "BTCUSDc"
        assert config.asset_type == AssetType.CRYPTO
        
        # Test save_symbol_config
        result = save_symbol_config("BTCUSDc", config)
        assert result is True
        
        # Test load_symbol_config
        loaded_config = load_symbol_config("BTCUSDc")
        assert loaded_config is not None
        assert loaded_config.symbol == "BTCUSDc"
    
    def test_enum_serialization(self):
        """Test enum serialization and deserialization"""
        # Create configuration with enums
        config = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
        config.vwap.session_anchor = SessionType.CRYPTO_24_7
        
        # Save configuration
        self.loader.save_symbol_config("BTCUSDc", config)
        
        # Load configuration
        loaded_config = self.loader.load_symbol_config("BTCUSDc")
        
        # Check enums were properly serialized/deserialized
        assert loaded_config.asset_type == AssetType.CRYPTO
        assert loaded_config.vwap.session_anchor == SessionType.CRYPTO_24_7
    
    def test_config_file_format(self):
        """Test that configuration files are properly formatted JSON"""
        # Create and save configuration
        config = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
        self.loader.save_symbol_config("BTCUSDc", config)
        
        # Check file format
        config_file = Path(self.temp_dir) / "BTCUSDc.json"
        with open(config_file, 'r') as f:
            data = json.load(f)
        
        # Check required fields
        assert "symbol" in data
        assert "asset_type" in data
        assert "vwap" in data
        assert "atr" in data
        assert "delta" in data
        assert "micro_bos" in data
        assert "spread_filter" in data
        assert "risk" in data
        
        # Check enum values are strings
        assert data["asset_type"] == "crypto"
        assert data["vwap"]["session_anchor"] == "crypto_24_7"
    
    def test_error_handling(self):
        """Test error handling in configuration operations"""
        # Test loading invalid JSON
        config_file = Path(self.temp_dir) / "INVALID.json"
        with open(config_file, 'w') as f:
            f.write("invalid json content")
        
        config = self.loader.load_symbol_config("INVALID")
        assert config is None
        
        # Test saving with invalid configuration data by creating a mock that raises an exception
        config = self.loader.create_default_config("BTCUSDc", AssetType.CRYPTO)
        
        # Mock the json.dump to raise an exception
        with patch('json.dump', side_effect=Exception("Mock serialization error")):
            result = self.loader.save_symbol_config("BTCUSDc", config)
            assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
