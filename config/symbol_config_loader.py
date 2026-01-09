"""
Per-Symbol Configuration Loader
Manages symbol-specific configuration files with hot-reload capability
"""
import os
import json
import toml
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
import logging
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class AssetType(Enum):
    """Asset type enumeration"""
    FOREX = "forex"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    INDEX = "index"


class SessionType(Enum):
    """Trading session type enumeration"""
    LONDON = "london"
    NEW_YORK = "new_york"
    TOKYO = "tokyo"
    SYDNEY = "sydney"
    CRYPTO_24_7 = "crypto_24_7"


@dataclass
class VWAPConfig:
    """VWAP calculation configuration"""
    session_anchor: SessionType
    sigma_window_minutes: int = 60
    min_volume_threshold: float = 0.01
    price_precision: int = 5


@dataclass
class ATRConfig:
    """ATR calculation configuration"""
    m1_period: int = 14
    m5_period: int = 14
    ratio_multiplier: float = 1.0
    high_volatility_threshold: float = 2.0


@dataclass
class DeltaConfig:
    """Volume delta configuration"""
    spike_threshold: float = 2.0
    min_volume: float = 0.01
    lookback_periods: int = 20


@dataclass
class MicroBOSConfig:
    """Micro-BOS/CHOCH configuration"""
    bar_lookback: int = 5
    min_atr_displacement: float = 0.25
    cooldown_period_ms: int = 300000  # 5 minutes


@dataclass
class SpreadFilterConfig:
    """Spread filter configuration"""
    normal_spread_threshold: float = 1.5
    elevated_spread_threshold: float = 3.0
    high_spread_threshold: float = 5.0
    extreme_spread_threshold: float = 10.0
    window_size: int = 20
    outlier_z_score: float = 2.0


@dataclass
class RiskConfig:
    """Risk management configuration"""
    max_lot_size: float = 0.1
    daily_lot_limit: float = 1.0
    hourly_lot_limit: float = 0.5
    max_drawdown_pct: float = 5.0
    circuit_breaker_threshold: float = 0.02


@dataclass
class SymbolConfig:
    """Complete symbol configuration"""
    symbol: str
    asset_type: AssetType
    binance_symbol: Optional[str] = None
    pip_value: float = 0.0001
    min_lot_size: float = 0.01
    max_lot_size: float = 1.0
    lot_step: float = 0.01
    vwap: VWAPConfig = None
    atr: ATRConfig = None
    delta: DeltaConfig = None
    micro_bos: MicroBOSConfig = None
    spread_filter: SpreadFilterConfig = None
    risk: RiskConfig = None
    enabled: bool = True
    priority: int = 1  # 1=highest, 5=lowest
    
    def __post_init__(self):
        """Initialize default configurations if not provided"""
        if self.vwap is None:
            self.vwap = VWAPConfig(
                session_anchor=SessionType.CRYPTO_24_7 if self.asset_type == AssetType.CRYPTO else SessionType.LONDON
            )
        if self.atr is None:
            self.atr = ATRConfig()
        if self.delta is None:
            self.delta = DeltaConfig()
        if self.micro_bos is None:
            self.micro_bos = MicroBOSConfig()
        if self.spread_filter is None:
            self.spread_filter = SpreadFilterConfig()
        if self.risk is None:
            self.risk = RiskConfig()


class SymbolConfigLoader:
    """Loads and manages per-symbol configuration files"""
    
    def __init__(self, config_dir: str = "config/symbols"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._configs: Dict[str, SymbolConfig] = {}
        self._file_timestamps: Dict[str, float] = {}
        self._watchers: List[callable] = []
    
    def load_symbol_config(self, symbol: str, force_reload: bool = False) -> Optional[SymbolConfig]:
        """
        Load configuration for a specific symbol
        
        Args:
            symbol: Symbol name (e.g., 'BTCUSDc')
            force_reload: Force reload even if file hasn't changed
            
        Returns:
            SymbolConfig object or None if not found
        """
        config_file = self.config_dir / f"{symbol}.json"
        
        if not config_file.exists():
            logger.warning(f"Configuration file not found for symbol {symbol}: {config_file}")
            return None
        
        # Check if file has been modified
        current_mtime = config_file.stat().st_mtime
        if not force_reload and symbol in self._file_timestamps:
            if current_mtime <= self._file_timestamps[symbol]:
                return self._configs.get(symbol)
        
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Convert string enums back to enum objects
            config_data = self._deserialize_enums(config_data)
            
            # Create SymbolConfig object
            symbol_config = SymbolConfig(**config_data)
            
            # Check if this was a reload (configuration already existed)
            was_reload = symbol in self._configs
            
            # Cache the configuration
            self._configs[symbol] = symbol_config
            self._file_timestamps[symbol] = current_mtime
            
            # Notify watchers if this was a reload
            if was_reload:
                self._notify_watchers(symbol)
            
            logger.info(f"Loaded configuration for {symbol}")
            return symbol_config
            
        except Exception as e:
            logger.error(f"Failed to load configuration for {symbol}: {e}")
            return None
    
    def load_all_configs(self, force_reload: bool = False) -> Dict[str, SymbolConfig]:
        """
        Load all symbol configurations
        
        Args:
            force_reload: Force reload all configurations
            
        Returns:
            Dictionary of symbol -> SymbolConfig
        """
        configs = {}
        
        for config_file in self.config_dir.glob("*.json"):
            symbol = config_file.stem
            config = self.load_symbol_config(symbol, force_reload)
            if config:
                configs[symbol] = config
        
        return configs
    
    def save_symbol_config(self, symbol: str, config: SymbolConfig) -> bool:
        """
        Save configuration for a specific symbol
        
        Args:
            symbol: Symbol name
            config: SymbolConfig object
            
        Returns:
            True if successful, False otherwise
        """
        try:
            config_file = self.config_dir / f"{symbol}.json"
            
            # Convert to dictionary and serialize enums
            config_dict = asdict(config)
            config_dict = self._serialize_enums(config_dict)
            
            with open(config_file, 'w') as f:
                json.dump(config_dict, f, indent=2, default=str)
            
            # Update cache
            self._configs[symbol] = config
            self._file_timestamps[symbol] = config_file.stat().st_mtime
            
            logger.info(f"Saved configuration for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save configuration for {symbol}: {e}")
            return False
    
    def create_default_config(self, symbol: str, asset_type: AssetType) -> SymbolConfig:
        """
        Create a default configuration for a symbol
        
        Args:
            symbol: Symbol name
            asset_type: Asset type
            
        Returns:
            Default SymbolConfig object
        """
        # Set default values based on asset type
        if asset_type == AssetType.CRYPTO:
            vwap_config = VWAPConfig(
                session_anchor=SessionType.CRYPTO_24_7,
                sigma_window_minutes=60
            )
            atr_config = ATRConfig(
                ratio_multiplier=1.5,
                high_volatility_threshold=3.0
            )
            risk_config = RiskConfig(
                max_lot_size=0.1,
                daily_lot_limit=2.0,
                hourly_lot_limit=1.0
            )
            # Set binance symbol for crypto
            binance_symbol = "BTCUSDT" if symbol == "BTCUSDc" else None
            # Higher spread thresholds for crypto
            spread_filter_config = SpreadFilterConfig(
                normal_spread_threshold=2.0,
                elevated_spread_threshold=5.0,
                high_spread_threshold=10.0,
                extreme_spread_threshold=20.0
            )
        elif asset_type == AssetType.FOREX:
            vwap_config = VWAPConfig(
                session_anchor=SessionType.LONDON,
                sigma_window_minutes=60
            )
            atr_config = ATRConfig(
                ratio_multiplier=1.0,
                high_volatility_threshold=2.0
            )
            risk_config = RiskConfig(
                max_lot_size=0.1,
                daily_lot_limit=1.0,
                hourly_lot_limit=0.5
            )
        else:  # COMMODITY or INDEX
            vwap_config = VWAPConfig(
                session_anchor=SessionType.LONDON,
                sigma_window_minutes=120
            )
            atr_config = ATRConfig(
                ratio_multiplier=1.2,
                high_volatility_threshold=2.5
            )
            risk_config = RiskConfig(
                max_lot_size=0.05,
                daily_lot_limit=0.5,
                hourly_lot_limit=0.25
            )
        
        return SymbolConfig(
            symbol=symbol,
            asset_type=asset_type,
            binance_symbol=binance_symbol if asset_type == AssetType.CRYPTO else None,
            vwap=vwap_config,
            atr=atr_config,
            delta=DeltaConfig(),
            micro_bos=MicroBOSConfig(),
            spread_filter=spread_filter_config if asset_type == AssetType.CRYPTO else SpreadFilterConfig(),
            risk=risk_config
        )
    
    def get_config(self, symbol: str) -> Optional[SymbolConfig]:
        """Get cached configuration for a symbol"""
        return self._configs.get(symbol)
    
    def reload_if_changed(self) -> List[str]:
        """
        Reload configurations that have changed on disk
        
        Returns:
            List of symbols that were reloaded
        """
        reloaded = []
        
        for symbol in list(self._configs.keys()):
            config_file = self.config_dir / f"{symbol}.json"
            if config_file.exists():
                current_mtime = config_file.stat().st_mtime
                if current_mtime > self._file_timestamps.get(symbol, 0):
                    if self.load_symbol_config(symbol, force_reload=True):
                        reloaded.append(symbol)
                        self._notify_watchers(symbol)
        
        return reloaded
    
    def add_watcher(self, callback: callable):
        """Add a callback to be called when configurations change"""
        self._watchers.append(callback)
    
    def remove_watcher(self, callback: callable):
        """Remove a configuration change callback"""
        if callback in self._watchers:
            self._watchers.remove(callback)
    
    def _notify_watchers(self, symbol: str):
        """Notify all watchers of configuration changes"""
        for callback in self._watchers:
            try:
                callback(symbol)
            except Exception as e:
                logger.error(f"Error in configuration watcher: {e}")
    
    def _serialize_enums(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert enum objects to strings for JSON serialization"""
        if isinstance(data, dict):
            return {k: self._serialize_enums(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._serialize_enums(item) for item in data]
        elif isinstance(data, Enum):
            return data.value
        else:
            return data
    
    def _deserialize_enums(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert string values back to enum objects"""
        if isinstance(data, dict):
            result = {}
            for k, v in data.items():
                if k == 'asset_type' and isinstance(v, str):
                    result[k] = AssetType(v)
                elif k == 'session_anchor' and isinstance(v, str):
                    result[k] = SessionType(v)
                elif k == 'vwap' and isinstance(v, dict):
                    result[k] = VWAPConfig(**self._deserialize_enums(v))
                elif k == 'atr' and isinstance(v, dict):
                    result[k] = ATRConfig(**self._deserialize_enums(v))
                elif k == 'delta' and isinstance(v, dict):
                    result[k] = DeltaConfig(**self._deserialize_enums(v))
                elif k == 'micro_bos' and isinstance(v, dict):
                    result[k] = MicroBOSConfig(**self._deserialize_enums(v))
                elif k == 'spread_filter' and isinstance(v, dict):
                    result[k] = SpreadFilterConfig(**self._deserialize_enums(v))
                elif k == 'risk' and isinstance(v, dict):
                    result[k] = RiskConfig(**self._deserialize_enums(v))
                else:
                    result[k] = self._deserialize_enums(v)
            return result
        elif isinstance(data, list):
            return [self._deserialize_enums(item) for item in data]
        else:
            return data
    
    def get_enabled_symbols(self) -> List[str]:
        """Get list of enabled symbols"""
        return [symbol for symbol, config in self._configs.items() if config.enabled]
    
    def get_symbols_by_priority(self) -> List[str]:
        """Get symbols sorted by priority (1=highest)"""
        enabled_symbols = [(symbol, config.priority) for symbol, config in self._configs.items() if config.enabled]
        return [symbol for symbol, _ in sorted(enabled_symbols, key=lambda x: x[1])]
    
    def validate_config(self, config: SymbolConfig) -> List[str]:
        """
        Validate a symbol configuration
        
        Args:
            config: SymbolConfig to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate basic parameters
        if config.max_lot_size <= 0:
            errors.append("max_lot_size must be positive")
        
        if config.min_lot_size <= 0:
            errors.append("min_lot_size must be positive")
        
        if config.min_lot_size > config.max_lot_size:
            errors.append("min_lot_size cannot be greater than max_lot_size")
        
        if config.priority < 1 or config.priority > 5:
            errors.append("priority must be between 1 and 5")
        
        # Validate VWAP configuration
        if config.vwap.sigma_window_minutes <= 0:
            errors.append("VWAP sigma_window_minutes must be positive")
        
        # Validate ATR configuration
        if config.atr.m1_period <= 0:
            errors.append("ATR m1_period must be positive")
        
        if config.atr.m5_period <= 0:
            errors.append("ATR m5_period must be positive")
        
        # Validate risk configuration
        if config.risk.max_lot_size <= 0:
            errors.append("Risk max_lot_size must be positive")
        
        if config.risk.daily_lot_limit <= 0:
            errors.append("Risk daily_lot_limit must be positive")
        
        return errors


# Global configuration loader instance
_config_loader: Optional[SymbolConfigLoader] = None


def get_config_loader() -> SymbolConfigLoader:
    """Get the global configuration loader instance"""
    global _config_loader
    if _config_loader is None:
        _config_loader = SymbolConfigLoader()
    return _config_loader


def load_symbol_config(symbol: str) -> Optional[SymbolConfig]:
    """Convenience function to load a symbol configuration"""
    return get_config_loader().load_symbol_config(symbol)


def save_symbol_config(symbol: str, config: SymbolConfig) -> bool:
    """Convenience function to save a symbol configuration"""
    return get_config_loader().save_symbol_config(symbol, config)


def create_default_config(symbol: str, asset_type: AssetType) -> SymbolConfig:
    """Convenience function to create a default configuration"""
    return get_config_loader().create_default_config(symbol, asset_type)


if __name__ == "__main__":
    # Example usage
    loader = SymbolConfigLoader()
    
    # Create default configurations for main symbols
    symbols = [
        ("BTCUSDc", AssetType.CRYPTO),
        ("XAUUSDc", AssetType.COMMODITY),
        ("EURUSDc", AssetType.FOREX),
        ("GBPUSDc", AssetType.FOREX),
        ("USDJPYc", AssetType.FOREX)
    ]
    
    for symbol, asset_type in symbols:
        config = loader.create_default_config(symbol, asset_type)
        loader.save_symbol_config(symbol, config)
        print(f"Created default configuration for {symbol}")
    
    # Load and display configurations
    all_configs = loader.load_all_configs()
    for symbol, config in all_configs.items():
        print(f"{symbol}: {config.asset_type.value}, Priority: {config.priority}, Enabled: {config.enabled}")
