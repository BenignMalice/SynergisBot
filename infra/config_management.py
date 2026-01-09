"""
Configuration Management System

This module implements a comprehensive configuration management system with
per-symbol TOML/JSON support and hot-reload functionality for dynamic
configuration updates without system restart.

Key Features:
- Per-symbol configuration files (TOML/JSON)
- Hot-reload functionality with file watching
- Configuration validation and schema enforcement
- Environment-specific configurations
- Configuration versioning and rollback
- Thread-safe configuration access
"""

import os
import json
import toml
import time
import logging
import threading
from typing import Dict, List, Optional, Any, Union, Callable, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)

class ConfigFormat(Enum):
    """Configuration file formats"""
    JSON = "json"
    TOML = "toml"
    YAML = "yaml"

class ConfigStatus(Enum):
    """Configuration status"""
    LOADED = "loaded"
    LOADING = "loading"
    ERROR = "error"
    STALE = "stale"
    RELOADING = "reloading"

class ConfigEnvironment(Enum):
    """Configuration environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"

@dataclass
class ConfigMetadata:
    """Configuration metadata"""
    version: str
    last_modified: float
    file_size: int
    checksum: str
    environment: ConfigEnvironment
    format: ConfigFormat
    schema_version: str = "1.0"

@dataclass
class ConfigValidationResult:
    """Configuration validation result"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    schema_version: str = "1.0"

@dataclass
class ConfigReloadEvent:
    """Configuration reload event"""
    symbol: str
    timestamp: float
    old_checksum: str
    new_checksum: str
    changes: List[str] = field(default_factory=list)
    success: bool = True
    error_message: Optional[str] = None

class ConfigFileHandler(FileSystemEventHandler):
    """File system event handler for configuration files"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.lock = threading.RLock()
    
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if file_path.suffix.lower() in ['.json', '.toml', '.yaml']:
            with self.lock:
                self.config_manager._handle_file_change(file_path)

class ConfigSchema:
    """Configuration schema validator"""
    
    def __init__(self):
        self.schemas = {
            "symbol_config": {
                "required_fields": ["symbol", "asset_type", "enabled"],
                "optional_fields": ["binance_symbol", "vwap", "atr", "delta", "micro_bos", "spread_filter", "risk"],
                "field_types": {
                    "symbol": str,
                    "asset_type": str,
                    "enabled": bool,
                    "binance_symbol": (str, type(None)),
                    "vwap": dict,
                    "atr": dict,
                    "delta": dict,
                    "micro_bos": dict,
                    "spread_filter": dict,
                    "risk": dict
                }
            }
        }
    
    def validate_config(self, config_data: Dict[str, Any], schema_name: str) -> ConfigValidationResult:
        """Validate configuration against schema"""
        if schema_name not in self.schemas:
            return ConfigValidationResult(
                is_valid=False,
                errors=[f"Unknown schema: {schema_name}"]
            )
        
        schema = self.schemas[schema_name]
        errors = []
        warnings = []
        
        # Check required fields
        for field in schema["required_fields"]:
            if field not in config_data:
                errors.append(f"Missing required field: {field}")
        
        # Check field types
        for field, expected_type in schema["field_types"].items():
            if field in config_data:
                value = config_data[field]
                if not isinstance(value, expected_type):
                    if isinstance(expected_type, tuple):
                        if not isinstance(value, expected_type):
                            errors.append(f"Field '{field}' has invalid type. Expected {expected_type}, got {type(value)}")
                    else:
                        errors.append(f"Field '{field}' has invalid type. Expected {expected_type}, got {type(value)}")
        
        # Check for unknown fields
        known_fields = set(schema["required_fields"] + schema["optional_fields"])
        for field in config_data.keys():
            if field not in known_fields:
                warnings.append(f"Unknown field: {field}")
        
        return ConfigValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

class ConfigManager:
    """Main configuration manager"""
    
    def __init__(self, config_dir: str = "config", environment: ConfigEnvironment = ConfigEnvironment.DEVELOPMENT):
        self.config_dir = Path(config_dir)
        self.environment = environment
        self.configs: Dict[str, Dict[str, Any]] = {}
        self.metadata: Dict[str, ConfigMetadata] = {}
        self.schema = ConfigSchema()
        self.lock = threading.RLock()
        
        # File watching
        self.observer = Observer()
        self.file_handler = ConfigFileHandler(self)
        self.watching = False
        
        # Callbacks
        self.on_config_loaded: Optional[Callable[[str, Dict[str, Any]], None]] = None
        self.on_config_reloaded: Optional[Callable[[ConfigReloadEvent], None]] = None
        self.on_config_error: Optional[Callable[[str, str], None]] = None
        
        # Create config directory if it doesn't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load initial configurations
        self._load_all_configs()
    
    def set_callbacks(self,
                      on_config_loaded: Optional[Callable[[str, Dict[str, Any]], None]] = None,
                      on_config_reloaded: Optional[Callable[[ConfigReloadEvent], None]] = None,
                      on_config_error: Optional[Callable[[str, str], None]] = None) -> None:
        """Set callback functions for configuration events"""
        self.on_config_loaded = on_config_loaded
        self.on_config_reloaded = on_config_reloaded
        self.on_config_error = on_config_error
    
    def start_watching(self) -> None:
        """Start watching configuration files for changes"""
        if not self.watching:
            self.observer.schedule(self.file_handler, str(self.config_dir), recursive=True)
            self.observer.start()
            self.watching = True
            logger.info("Started watching configuration files")
    
    def stop_watching(self) -> None:
        """Stop watching configuration files"""
        if self.watching:
            self.observer.stop()
            self.observer.join()
            self.watching = False
            logger.info("Stopped watching configuration files")
    
    def _load_all_configs(self) -> None:
        """Load all configuration files"""
        for config_file in self.config_dir.rglob("*"):
            if config_file.is_file() and config_file.suffix.lower() in ['.json', '.toml', '.yaml']:
                self._load_config_file(config_file)
    
    def _load_config_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load a single configuration file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.suffix.lower() == '.json':
                    config_data = json.load(f)
                    format_type = ConfigFormat.JSON
                elif file_path.suffix.lower() == '.toml':
                    config_data = toml.load(f)
                    format_type = ConfigFormat.TOML
                else:
                    logger.warning(f"Unsupported file format: {file_path.suffix}")
                    return None
            
            # Extract symbol from filename or config
            symbol = self._extract_symbol(file_path, config_data)
            if not symbol:
                logger.warning(f"Could not extract symbol from {file_path}")
                return None
            
            # Validate configuration
            validation_result = self.schema.validate_config(config_data, "symbol_config")
            if not validation_result.is_valid:
                error_msg = f"Configuration validation failed for {symbol}: {validation_result.errors}"
                logger.error(error_msg)
                if self.on_config_error:
                    self.on_config_error(symbol, error_msg)
                return None
            
            # Calculate metadata
            file_stat = file_path.stat()
            checksum = self._calculate_checksum(file_path)
            
            metadata = ConfigMetadata(
                version=config_data.get('version', '1.0'),
                last_modified=file_stat.st_mtime,
                file_size=file_stat.st_size,
                checksum=checksum,
                environment=self.environment,
                format=format_type
            )
            
            with self.lock:
                self.configs[symbol] = config_data
                self.metadata[symbol] = metadata
            
            logger.info(f"Loaded configuration for {symbol}")
            
            # Call config loaded callback
            if self.on_config_loaded:
                try:
                    self.on_config_loaded(symbol, config_data)
                except Exception as e:
                    logger.error(f"Error in on_config_loaded callback: {e}")
            
            return config_data
            
        except Exception as e:
            logger.error(f"Error loading configuration file {file_path}: {e}")
            return None
    
    def _extract_symbol(self, file_path: Path, config_data: Dict[str, Any]) -> Optional[str]:
        """Extract symbol from file path or configuration data"""
        # Try to get symbol from config data first
        if 'symbol' in config_data:
            return config_data['symbol']
        
        # Extract from filename
        filename = file_path.stem
        if filename.startswith('symbol_'):
            return filename[7:]  # Remove 'symbol_' prefix
        elif filename.endswith('_config'):
            return filename[:-7]  # Remove '_config' suffix
        else:
            return filename
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate file checksum"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def _handle_file_change(self, file_path: Path) -> None:
        """Handle configuration file changes"""
        symbol = self._extract_symbol(file_path, {})
        if not symbol:
            return
        
        old_checksum = self.metadata.get(symbol, {}).get('checksum', '')
        
        # Wait a bit for file to be fully written
        time.sleep(0.1)
        
        # Reload configuration
        new_config = self._load_config_file(file_path)
        if new_config and symbol in self.metadata:
            new_checksum = self.metadata[symbol].checksum
            
            # Detect changes
            changes = self._detect_changes(symbol, new_config)
            
            # Create reload event
            reload_event = ConfigReloadEvent(
                symbol=symbol,
                timestamp=time.time(),
                old_checksum=old_checksum,
                new_checksum=new_checksum,
                changes=changes,
                success=True
            )
            
            # Call reload callback
            if self.on_config_reloaded:
                try:
                    self.on_config_reloaded(reload_event)
                except Exception as e:
                    logger.error(f"Error in on_config_reloaded callback: {e}")
            
            logger.info(f"Reloaded configuration for {symbol}")
        else:
            # Create error event
            reload_event = ConfigReloadEvent(
                symbol=symbol,
                timestamp=time.time(),
                old_checksum=old_checksum,
                new_checksum="",
                success=False,
                error_message="Failed to load configuration"
            )
            
            if self.on_config_reloaded:
                try:
                    self.on_config_reloaded(reload_event)
                except Exception as e:
                    logger.error(f"Error in on_config_reloaded callback: {e}")
    
    def _detect_changes(self, symbol: str, new_config: Dict[str, Any]) -> List[str]:
        """Detect changes between old and new configuration"""
        if symbol not in self.configs:
            return ["New configuration loaded"]
        
        old_config = self.configs[symbol]
        changes = []
        
        # Compare configurations
        for key, new_value in new_config.items():
            if key not in old_config:
                changes.append(f"Added field: {key}")
            elif old_config[key] != new_value:
                changes.append(f"Changed field: {key}")
        
        # Check for removed fields
        for key in old_config.keys():
            if key not in new_config:
                changes.append(f"Removed field: {key}")
        
        return changes
    
    def get_config(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a symbol"""
        with self.lock:
            return self.configs.get(symbol)
    
    def get_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get all configurations"""
        with self.lock:
            return dict(self.configs)
    
    def get_metadata(self, symbol: str) -> Optional[ConfigMetadata]:
        """Get configuration metadata for a symbol"""
        with self.lock:
            return self.metadata.get(symbol)
    
    def get_all_metadata(self) -> Dict[str, ConfigMetadata]:
        """Get all configuration metadata"""
        with self.lock:
            return dict(self.metadata)
    
    def save_config(self, symbol: str, config_data: Dict[str, Any], 
                   format_type: ConfigFormat = ConfigFormat.JSON) -> bool:
        """Save configuration for a symbol"""
        try:
            # Validate configuration
            validation_result = self.schema.validate_config(config_data, "symbol_config")
            if not validation_result.is_valid:
                logger.error(f"Configuration validation failed for {symbol}: {validation_result.errors}")
                return False
            
            # Determine file path
            if format_type == ConfigFormat.JSON:
                file_path = self.config_dir / f"{symbol}.json"
            elif format_type == ConfigFormat.TOML:
                file_path = self.config_dir / f"{symbol}.toml"
            else:
                logger.error(f"Unsupported format: {format_type}")
                return False
            
            # Create backup
            if file_path.exists():
                backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
                shutil.copy2(file_path, backup_path)
            
            # Write configuration
            with open(file_path, 'w', encoding='utf-8') as f:
                if format_type == ConfigFormat.JSON:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
                elif format_type == ConfigFormat.TOML:
                    toml.dump(config_data, f)
            
            # Reload configuration
            self._load_config_file(file_path)
            
            logger.info(f"Saved configuration for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration for {symbol}: {e}")
            return False
    
    def delete_config(self, symbol: str) -> bool:
        """Delete configuration for a symbol"""
        try:
            # Find configuration file
            config_file = None
            for ext in ['.json', '.toml', '.yaml']:
                file_path = self.config_dir / f"{symbol}{ext}"
                if file_path.exists():
                    config_file = file_path
                    break
            
            if not config_file:
                logger.warning(f"Configuration file not found for {symbol}")
                return False
            
            # Create backup
            backup_path = config_file.with_suffix(f"{config_file.suffix}.deleted")
            shutil.copy2(config_file, backup_path)
            
            # Delete file
            config_file.unlink()
            
            # Remove from memory
            with self.lock:
                if symbol in self.configs:
                    del self.configs[symbol]
                if symbol in self.metadata:
                    del self.metadata[symbol]
            
            logger.info(f"Deleted configuration for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting configuration for {symbol}: {e}")
            return False
    
    def reload_config(self, symbol: str) -> bool:
        """Manually reload configuration for a symbol"""
        try:
            # Find configuration file
            config_file = None
            for ext in ['.json', '.toml', '.yaml']:
                file_path = self.config_dir / f"{symbol}{ext}"
                if file_path.exists():
                    config_file = file_path
                    break
            
            if not config_file:
                logger.warning(f"Configuration file not found for {symbol}")
                return False
            
            # Reload configuration
            config_data = self._load_config_file(config_file)
            return config_data is not None
            
        except Exception as e:
            logger.error(f"Error reloading configuration for {symbol}: {e}")
            return False
    
    def get_config_statistics(self) -> Dict[str, Any]:
        """Get configuration statistics"""
        with self.lock:
            total_configs = len(self.configs)
            total_size = sum(metadata.file_size for metadata in self.metadata.values())
            
            format_counts = {}
            for metadata in self.metadata.values():
                format_name = metadata.format.value
                format_counts[format_name] = format_counts.get(format_name, 0) + 1
            
            return {
                'total_configs': total_configs,
                'total_size_bytes': total_size,
                'format_distribution': format_counts,
                'environment': self.environment.value,
                'watching_enabled': self.watching
            }
    
    def validate_all_configs(self) -> Dict[str, ConfigValidationResult]:
        """Validate all configurations"""
        results = {}
        with self.lock:
            for symbol, config_data in self.configs.items():
                results[symbol] = self.schema.validate_config(config_data, "symbol_config")
        return results
    
    def cleanup_backups(self, max_age_days: int = 7) -> int:
        """Clean up old backup files"""
        cleaned_count = 0
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        
        for backup_file in self.config_dir.rglob("*.backup"):
            if backup_file.stat().st_mtime < cutoff_time:
                backup_file.unlink()
                cleaned_count += 1
        
        for deleted_file in self.config_dir.rglob("*.deleted"):
            if deleted_file.stat().st_mtime < cutoff_time:
                deleted_file.unlink()
                cleaned_count += 1
        
        logger.info(f"Cleaned up {cleaned_count} old backup files")
        return cleaned_count

# Global configuration manager
_config_manager: Optional[ConfigManager] = None

def get_config_manager(config_dir: str = "config", 
                      environment: ConfigEnvironment = ConfigEnvironment.DEVELOPMENT) -> ConfigManager:
    """Get global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_dir, environment)
    return _config_manager

def get_config(symbol: str) -> Optional[Dict[str, Any]]:
    """Get configuration for a symbol"""
    manager = get_config_manager()
    return manager.get_config(symbol)

def save_config(symbol: str, config_data: Dict[str, Any], 
               format_type: ConfigFormat = ConfigFormat.JSON) -> bool:
    """Save configuration for a symbol"""
    manager = get_config_manager()
    return manager.save_config(symbol, config_data, format_type)

def reload_config(symbol: str) -> bool:
    """Reload configuration for a symbol"""
    manager = get_config_manager()
    return manager.reload_config(symbol)

def start_config_watching() -> None:
    """Start watching configuration files"""
    manager = get_config_manager()
    manager.start_watching()

def stop_config_watching() -> None:
    """Stop watching configuration files"""
    manager = get_config_manager()
    manager.stop_watching()

if __name__ == "__main__":
    # Example usage
    manager = ConfigManager("config", ConfigEnvironment.DEVELOPMENT)
    
    # Create a sample configuration
    sample_config = {
        "symbol": "BTCUSDc",
        "asset_type": "crypto",
        "enabled": True,
        "binance_symbol": "BTCUSDT",
        "vwap": {
            "session_anchor": "crypto",
            "sigma_window_minutes": 60
        },
        "atr": {
            "period": 14,
            "multiplier": 2.0
        },
        "risk": {
            "max_lot_size": 0.01,
            "stop_loss_pips": 50
        }
    }
    
    # Save configuration
    success = manager.save_config("BTCUSDc", sample_config, ConfigFormat.JSON)
    print(f"Configuration saved: {success}")
    
    # Get configuration
    config = manager.get_config("BTCUSDc")
    print(f"Configuration loaded: {config is not None}")
    
    # Start watching
    manager.start_watching()
    
    # Get statistics
    stats = manager.get_config_statistics()
    print(f"Configuration statistics: {stats}")
    
    # Stop watching
    manager.stop_watching()
