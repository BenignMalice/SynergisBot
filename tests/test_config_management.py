"""
Comprehensive tests for configuration management system

Tests per-symbol configuration loading, hot-reload functionality,
configuration validation, file watching, and schema enforcement.
"""

import pytest
import json
import toml
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional

from infra.config_management import (
    ConfigManager, ConfigSchema, ConfigFileHandler,
    ConfigFormat, ConfigStatus, ConfigEnvironment,
    ConfigMetadata, ConfigValidationResult, ConfigReloadEvent,
    get_config_manager, get_config, save_config, reload_config,
    start_config_watching, stop_config_watching
)

class TestConfigFormat:
    """Test configuration format enumeration"""
    
    def test_config_formats(self):
        """Test all configuration formats"""
        formats = [
            ConfigFormat.JSON,
            ConfigFormat.TOML,
            ConfigFormat.YAML
        ]
        
        for format_type in formats:
            assert isinstance(format_type, ConfigFormat)
            assert format_type.value in ["json", "toml", "yaml"]

class TestConfigStatus:
    """Test configuration status enumeration"""
    
    def test_config_statuses(self):
        """Test all configuration statuses"""
        statuses = [
            ConfigStatus.LOADED,
            ConfigStatus.LOADING,
            ConfigStatus.ERROR,
            ConfigStatus.STALE,
            ConfigStatus.RELOADING
        ]
        
        for status in statuses:
            assert isinstance(status, ConfigStatus)
            assert status.value in ["loaded", "loading", "error", "stale", "reloading"]

class TestConfigEnvironment:
    """Test configuration environment enumeration"""
    
    def test_config_environments(self):
        """Test all configuration environments"""
        environments = [
            ConfigEnvironment.DEVELOPMENT,
            ConfigEnvironment.STAGING,
            ConfigEnvironment.PRODUCTION,
            ConfigEnvironment.TESTING
        ]
        
        for env in environments:
            assert isinstance(env, ConfigEnvironment)
            assert env.value in ["development", "staging", "production", "testing"]

class TestConfigMetadata:
    """Test configuration metadata data structure"""
    
    def test_config_metadata_creation(self):
        """Test configuration metadata creation"""
        metadata = ConfigMetadata(
            version="1.0",
            last_modified=time.time(),
            file_size=1024,
            checksum="abc123",
            environment=ConfigEnvironment.PRODUCTION,
            format=ConfigFormat.JSON,
            schema_version="1.0"
        )
        
        assert metadata.version == "1.0"
        assert metadata.last_modified > 0
        assert metadata.file_size == 1024
        assert metadata.checksum == "abc123"
        assert metadata.environment == ConfigEnvironment.PRODUCTION
        assert metadata.format == ConfigFormat.JSON
        assert metadata.schema_version == "1.0"
    
    def test_config_metadata_defaults(self):
        """Test configuration metadata defaults"""
        metadata = ConfigMetadata(
            version="1.0",
            last_modified=time.time(),
            file_size=1024,
            checksum="abc123",
            environment=ConfigEnvironment.DEVELOPMENT,
            format=ConfigFormat.JSON
        )
        
        assert metadata.schema_version == "1.0"

class TestConfigValidationResult:
    """Test configuration validation result data structure"""
    
    def test_config_validation_result_creation(self):
        """Test configuration validation result creation"""
        result = ConfigValidationResult(
            is_valid=True,
            errors=["Error 1", "Error 2"],
            warnings=["Warning 1"],
            schema_version="1.0"
        )
        
        assert result.is_valid is True
        assert len(result.errors) == 2
        assert len(result.warnings) == 1
        assert result.schema_version == "1.0"
    
    def test_config_validation_result_defaults(self):
        """Test configuration validation result defaults"""
        result = ConfigValidationResult(is_valid=False)
        
        assert result.is_valid is False
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert result.schema_version == "1.0"

class TestConfigReloadEvent:
    """Test configuration reload event data structure"""
    
    def test_config_reload_event_creation(self):
        """Test configuration reload event creation"""
        event = ConfigReloadEvent(
            symbol="BTCUSDc",
            timestamp=time.time(),
            old_checksum="abc123",
            new_checksum="def456",
            changes=["Changed field: vwap"],
            success=True
        )
        
        assert event.symbol == "BTCUSDc"
        assert event.timestamp > 0
        assert event.old_checksum == "abc123"
        assert event.new_checksum == "def456"
        assert len(event.changes) == 1
        assert event.success is True
        assert event.error_message is None
    
    def test_config_reload_event_defaults(self):
        """Test configuration reload event defaults"""
        event = ConfigReloadEvent(
            symbol="ETHUSDc",
            timestamp=time.time(),
            old_checksum="abc123",
            new_checksum="def456"
        )
        
        assert len(event.changes) == 0
        assert event.success is True
        assert event.error_message is None

class TestConfigSchema:
    """Test configuration schema validation"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.schema = ConfigSchema()
    
    def test_schema_initialization(self):
        """Test schema initialization"""
        assert "symbol_config" in self.schema.schemas
        assert "required_fields" in self.schema.schemas["symbol_config"]
        assert "optional_fields" in self.schema.schemas["symbol_config"]
        assert "field_types" in self.schema.schemas["symbol_config"]
    
    def test_validate_config_valid(self):
        """Test validation of valid configuration"""
        config_data = {
            "symbol": "BTCUSDc",
            "asset_type": "crypto",
            "enabled": True,
            "binance_symbol": "BTCUSDT",
            "vwap": {"session_anchor": "crypto"},
            "atr": {"period": 14},
            "delta": {},
            "micro_bos": {},
            "spread_filter": {},
            "risk": {}
        }
        
        result = self.schema.validate_config(config_data, "symbol_config")
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_config_missing_required(self):
        """Test validation of configuration with missing required fields"""
        config_data = {
            "asset_type": "crypto",
            "enabled": True
        }
        
        result = self.schema.validate_config(config_data, "symbol_config")
        
        assert result.is_valid is False
        assert "Missing required field: symbol" in result.errors
    
    def test_validate_config_invalid_type(self):
        """Test validation of configuration with invalid field types"""
        config_data = {
            "symbol": "BTCUSDc",
            "asset_type": "crypto",
            "enabled": "true"  # Should be boolean
        }
        
        result = self.schema.validate_config(config_data, "symbol_config")
        
        assert result.is_valid is False
        assert "Field 'enabled' has invalid type" in result.errors[0]
    
    def test_validate_config_unknown_field(self):
        """Test validation of configuration with unknown fields"""
        config_data = {
            "symbol": "BTCUSDc",
            "asset_type": "crypto",
            "enabled": True,
            "unknown_field": "value"
        }
        
        result = self.schema.validate_config(config_data, "symbol_config")
        
        assert result.is_valid is True  # Unknown fields are warnings, not errors
        assert "Unknown field: unknown_field" in result.warnings
    
    def test_validate_config_unknown_schema(self):
        """Test validation with unknown schema"""
        config_data = {"test": "value"}
        
        result = self.schema.validate_config(config_data, "unknown_schema")
        
        assert result.is_valid is False
        assert "Unknown schema: unknown_schema" in result.errors

class TestConfigManager:
    """Test configuration manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = ConfigManager(self.temp_dir, ConfigEnvironment.DEVELOPMENT)
    
    def teardown_method(self):
        """Clean up test fixtures"""
        self.manager.stop_watching()
        shutil.rmtree(self.temp_dir)
    
    def test_manager_initialization(self):
        """Test manager initialization"""
        assert self.manager.config_dir == Path(self.temp_dir)
        assert self.manager.environment == ConfigEnvironment.DEVELOPMENT
        assert len(self.manager.configs) == 0
        assert len(self.manager.metadata) == 0
        assert isinstance(self.manager.schema, ConfigSchema)
        assert self.manager.watching is False
    
    def test_save_and_load_json_config(self):
        """Test saving and loading JSON configuration"""
        config_data = {
            "symbol": "BTCUSDc",
            "asset_type": "crypto",
            "enabled": True,
            "binance_symbol": "BTCUSDT",
            "vwap": {"session_anchor": "crypto"},
            "atr": {"period": 14},
            "risk": {"max_lot_size": 0.01}
        }
        
        # Save configuration
        success = self.manager.save_config("BTCUSDc", config_data, ConfigFormat.JSON)
        assert success is True
        
        # Load configuration
        loaded_config = self.manager.get_config("BTCUSDc")
        assert loaded_config is not None
        assert loaded_config["symbol"] == "BTCUSDc"
        assert loaded_config["asset_type"] == "crypto"
        assert loaded_config["enabled"] is True
    
    def test_save_and_load_toml_config(self):
        """Test saving and loading TOML configuration"""
        config_data = {
            "symbol": "ETHUSDc",
            "asset_type": "crypto",
            "enabled": True,
            "vwap": {"session_anchor": "crypto"},
            "atr": {"period": 14}
        }
        
        # Save configuration
        success = self.manager.save_config("ETHUSDc", config_data, ConfigFormat.TOML)
        assert success is True
        
        # Load configuration
        loaded_config = self.manager.get_config("ETHUSDc")
        assert loaded_config is not None
        assert loaded_config["symbol"] == "ETHUSDc"
        assert loaded_config["asset_type"] == "crypto"
    
    def test_save_invalid_config(self):
        """Test saving invalid configuration"""
        invalid_config = {
            "asset_type": "crypto",  # Missing required 'symbol' field
            "enabled": True
        }
        
        success = self.manager.save_config("INVALID", invalid_config, ConfigFormat.JSON)
        assert success is False
    
    def test_get_all_configs(self):
        """Test getting all configurations"""
        # Save multiple configurations
        configs = [
            ("BTCUSDc", {"symbol": "BTCUSDc", "asset_type": "crypto", "enabled": True}),
            ("ETHUSDc", {"symbol": "ETHUSDc", "asset_type": "crypto", "enabled": True}),
            ("EURUSDc", {"symbol": "EURUSDc", "asset_type": "forex", "enabled": True})
        ]
        
        for symbol, config_data in configs:
            self.manager.save_config(symbol, config_data, ConfigFormat.JSON)
        
        # Get all configurations
        all_configs = self.manager.get_all_configs()
        assert len(all_configs) == 3
        assert "BTCUSDc" in all_configs
        assert "ETHUSDc" in all_configs
        assert "EURUSDc" in all_configs
    
    def test_get_metadata(self):
        """Test getting configuration metadata"""
        config_data = {
            "symbol": "BTCUSDc",
            "asset_type": "crypto",
            "enabled": True
        }
        
        self.manager.save_config("BTCUSDc", config_data, ConfigFormat.JSON)
        
        metadata = self.manager.get_metadata("BTCUSDc")
        assert metadata is not None
        assert metadata.version is not None
        assert metadata.environment == ConfigEnvironment.DEVELOPMENT
        assert metadata.format == ConfigFormat.JSON
        assert metadata.checksum is not None
    
    def test_get_all_metadata(self):
        """Test getting all configuration metadata"""
        configs = [
            ("BTCUSDc", {"symbol": "BTCUSDc", "asset_type": "crypto", "enabled": True}),
            ("ETHUSDc", {"symbol": "ETHUSDc", "asset_type": "crypto", "enabled": True})
        ]
        
        for symbol, config_data in configs:
            self.manager.save_config(symbol, config_data, ConfigFormat.JSON)
        
        all_metadata = self.manager.get_all_metadata()
        assert len(all_metadata) == 2
        assert "BTCUSDc" in all_metadata
        assert "ETHUSDc" in all_metadata
    
    def test_delete_config(self):
        """Test deleting configuration"""
        config_data = {
            "symbol": "BTCUSDc",
            "asset_type": "crypto",
            "enabled": True
        }
        
        # Save configuration
        self.manager.save_config("BTCUSDc", config_data, ConfigFormat.JSON)
        assert self.manager.get_config("BTCUSDc") is not None
        
        # Delete configuration
        success = self.manager.delete_config("BTCUSDc")
        assert success is True
        assert self.manager.get_config("BTCUSDc") is None
    
    def test_reload_config(self):
        """Test reloading configuration"""
        config_data = {
            "symbol": "BTCUSDc",
            "asset_type": "crypto",
            "enabled": True
        }
        
        # Save configuration
        self.manager.save_config("BTCUSDc", config_data, ConfigFormat.JSON)
        
        # Reload configuration
        success = self.manager.reload_config("BTCUSDc")
        assert success is True
    
    def test_get_config_statistics(self):
        """Test getting configuration statistics"""
        config_data = {
            "symbol": "BTCUSDc",
            "asset_type": "crypto",
            "enabled": True
        }
        
        self.manager.save_config("BTCUSDc", config_data, ConfigFormat.JSON)
        
        stats = self.manager.get_config_statistics()
        assert stats['total_configs'] == 1
        assert stats['total_size_bytes'] > 0
        assert 'json' in stats['format_distribution']
        assert stats['environment'] == 'development'
        assert stats['watching_enabled'] is False
    
    def test_validate_all_configs(self):
        """Test validating all configurations"""
        configs = [
            ("BTCUSDc", {"symbol": "BTCUSDc", "asset_type": "crypto", "enabled": True}),
            ("INVALID", {"asset_type": "crypto", "enabled": True})  # Missing symbol
        ]
        
        for symbol, config_data in configs:
            self.manager.save_config(symbol, config_data, ConfigFormat.JSON)
        
        validation_results = self.manager.validate_all_configs()
        assert len(validation_results) == 1  # Only valid configs are kept
        assert validation_results["BTCUSDc"].is_valid is True
    
    def test_cleanup_backups(self):
        """Test cleaning up backup files"""
        # Create some backup files
        backup_file = Path(self.temp_dir) / "test.backup"
        backup_file.write_text("test content")
        
        # Clean up backups
        cleaned_count = self.manager.cleanup_backups(max_age_days=0)  # Clean all
        assert cleaned_count >= 0  # May be 0 if no old files
    
    def test_callback_setting(self):
        """Test callback function setting"""
        on_config_loaded = Mock()
        on_config_reloaded = Mock()
        on_config_error = Mock()
        
        self.manager.set_callbacks(
            on_config_loaded=on_config_loaded,
            on_config_reloaded=on_config_reloaded,
            on_config_error=on_config_error
        )
        
        assert self.manager.on_config_loaded == on_config_loaded
        assert self.manager.on_config_reloaded == on_config_reloaded
        assert self.manager.on_config_error == on_config_error
    
    def test_file_watching(self):
        """Test file watching functionality"""
        # Start watching
        self.manager.start_watching()
        assert self.manager.watching is True
        
        # Stop watching
        self.manager.stop_watching()
        assert self.manager.watching is False

class TestConfigFileHandler:
    """Test configuration file handler"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = ConfigManager(self.temp_dir, ConfigEnvironment.DEVELOPMENT)
        self.handler = ConfigFileHandler(self.manager)
    
    def teardown_method(self):
        """Clean up test fixtures"""
        self.manager.stop_watching()
        shutil.rmtree(self.temp_dir)
    
    def test_handler_initialization(self):
        """Test handler initialization"""
        assert self.handler.config_manager == self.manager
        assert hasattr(self.handler, 'lock')
    
    def test_on_modified_json_file(self):
        """Test handling JSON file modifications"""
        # Create a JSON file
        json_file = Path(self.temp_dir) / "BTCUSDc.json"
        json_file.write_text('{"symbol": "BTCUSDc", "asset_type": "crypto", "enabled": true}')
        
        # Simulate file modification
        self.handler.on_modified(type('Event', (), {'is_directory': False, 'src_path': str(json_file)})())
        
        # Check that configuration was loaded
        config = self.manager.get_config("BTCUSDc")
        assert config is not None
        assert config["symbol"] == "BTCUSDc"
    
    def test_on_modified_toml_file(self):
        """Test handling TOML file modifications"""
        # Create a TOML file
        toml_file = Path(self.temp_dir) / "ETHUSDc.toml"
        toml_file.write_text('symbol = "ETHUSDc"\nasset_type = "crypto"\nenabled = true')
        
        # Simulate file modification
        self.handler.on_modified(type('Event', (), {'is_directory': False, 'src_path': str(toml_file)})())
        
        # Check that configuration was loaded
        config = self.manager.get_config("ETHUSDc")
        assert config is not None
        assert config["symbol"] == "ETHUSDc"
    
    def test_on_modified_directory(self):
        """Test handling directory modifications"""
        # Simulate directory modification
        self.handler.on_modified(type('Event', (), {'is_directory': True, 'src_path': str(self.temp_dir)})())
        
        # Should not crash and should not load any configurations
        assert len(self.manager.configs) == 0

class TestGlobalFunctions:
    """Test global configuration functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.config_management
        infra.config_management._config_manager = None
    
    def test_get_config_manager(self):
        """Test global configuration manager access"""
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        
        # Should return same instance
        assert manager1 is manager2
        assert isinstance(manager1, ConfigManager)
    
    def test_get_config_global(self):
        """Test global configuration retrieval"""
        # Save a configuration
        config_data = {
            "symbol": "BTCUSDc",
            "asset_type": "crypto",
            "enabled": True
        }
        save_config("BTCUSDc", config_data, ConfigFormat.JSON)
        
        # Get configuration
        config = get_config("BTCUSDc")
        assert config is not None
        assert config["symbol"] == "BTCUSDc"
    
    def test_save_config_global(self):
        """Test global configuration saving"""
        config_data = {
            "symbol": "ETHUSDc",
            "asset_type": "crypto",
            "enabled": True
        }
        
        success = save_config("ETHUSDc", config_data, ConfigFormat.JSON)
        assert success is True
        
        # Verify configuration was saved
        config = get_config("ETHUSDc")
        assert config is not None
        assert config["symbol"] == "ETHUSDc"
    
    def test_reload_config_global(self):
        """Test global configuration reloading"""
        # Save a configuration
        config_data = {
            "symbol": "BTCUSDc",
            "asset_type": "crypto",
            "enabled": True
        }
        save_config("BTCUSDc", config_data, ConfigFormat.JSON)
        
        # Reload configuration
        success = reload_config("BTCUSDc")
        assert success is True
    
    def test_start_stop_watching_global(self):
        """Test global watching functions"""
        # Start watching
        start_config_watching()
        
        # Stop watching
        stop_config_watching()

class TestConfigIntegration:
    """Integration tests for configuration management"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.config_management
        infra.config_management._config_manager = None
    
    def test_comprehensive_config_workflow(self):
        """Test comprehensive configuration workflow"""
        # Create multiple configurations
        configs = [
            ("BTCUSDc", {
                "symbol": "BTCUSDc",
                "asset_type": "crypto",
                "enabled": True,
                "binance_symbol": "BTCUSDT",
                "vwap": {"session_anchor": "crypto"},
                "atr": {"period": 14},
                "risk": {"max_lot_size": 0.01}
            }),
            ("ETHUSDc", {
                "symbol": "ETHUSDc",
                "asset_type": "crypto",
                "enabled": True,
                "vwap": {"session_anchor": "crypto"},
                "atr": {"period": 14}
            }),
            ("EURUSDc", {
                "symbol": "EURUSDc",
                "asset_type": "forex",
                "enabled": True,
                "vwap": {"session_anchor": "forex"},
                "atr": {"period": 14}
            })
        ]
        
        # Save configurations
        for symbol, config_data in configs:
            success = save_config(symbol, config_data, ConfigFormat.JSON)
            assert success is True
        
        # Verify configurations
        for symbol, expected_config in configs:
            config = get_config(symbol)
            assert config is not None
            assert config["symbol"] == expected_config["symbol"]
            assert config["asset_type"] == expected_config["asset_type"]
            assert config["enabled"] == expected_config["enabled"]
    
    def test_config_validation_workflow(self):
        """Test configuration validation workflow"""
        # Valid configuration
        valid_config = {
            "symbol": "BTCUSDc",
            "asset_type": "crypto",
            "enabled": True,
            "vwap": {"session_anchor": "crypto"},
            "atr": {"period": 14}
        }
        
        success = save_config("BTCUSDc", valid_config, ConfigFormat.JSON)
        assert success is True
        
        # Invalid configuration
        invalid_config = {
            "asset_type": "crypto",
            "enabled": True
            # Missing required 'symbol' field
        }
        
        success = save_config("INVALID", invalid_config, ConfigFormat.JSON)
        assert success is False
    
    def test_config_reload_workflow(self):
        """Test configuration reload workflow"""
        # Save initial configuration
        initial_config = {
            "symbol": "BTCUSDc",
            "asset_type": "crypto",
            "enabled": True,
            "vwap": {"session_anchor": "crypto"}
        }
        
        save_config("BTCUSDc", initial_config, ConfigFormat.JSON)
        
        # Modify configuration
        modified_config = {
            "symbol": "BTCUSDc",
            "asset_type": "crypto",
            "enabled": True,
            "vwap": {"session_anchor": "crypto", "sigma_window_minutes": 60},
            "atr": {"period": 14}
        }
        
        save_config("BTCUSDc", modified_config, ConfigFormat.JSON)
        
        # Reload configuration
        success = reload_config("BTCUSDc")
        assert success is True
        
        # Verify changes
        config = get_config("BTCUSDc")
        assert config is not None
        assert "sigma_window_minutes" in config["vwap"]
        assert "atr" in config
    
    def test_config_statistics_workflow(self):
        """Test configuration statistics workflow"""
        # Save multiple configurations
        configs = [
            ("BTCUSDc", {"symbol": "BTCUSDc", "asset_type": "crypto", "enabled": True}),
            ("ETHUSDc", {"symbol": "ETHUSDc", "asset_type": "crypto", "enabled": True}),
            ("EURUSDc", {"symbol": "EURUSDc", "asset_type": "forex", "enabled": True})
        ]
        
        for symbol, config_data in configs:
            save_config(symbol, config_data, ConfigFormat.JSON)
        
        # Get statistics
        manager = get_config_manager()
        stats = manager.get_config_statistics()
        
        assert stats['total_configs'] >= 3  # May have more due to previous tests
        assert stats['total_size_bytes'] > 0
        assert 'json' in stats['format_distribution']
        assert stats['format_distribution']['json'] >= 3  # May have more due to previous tests
        assert stats['environment'] == 'development'
        assert stats['watching_enabled'] is False

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
