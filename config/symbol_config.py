"""
Symbol-Specific Configuration System
Per-symbol parameter configuration with hot-reload capability
"""

import json
import toml
import os
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

@dataclass
class SymbolConfig:
    """Symbol-specific configuration parameters"""
    
    # Symbol identification
    symbol: str
    broker_symbol: str  # With 'c' suffix
    binance_symbol: Optional[str] = None  # For crypto symbols
    
    # Risk management
    max_lot_size: float = 0.01
    default_risk_percent: float = 0.5
    max_daily_drawdown: float = 2.0
    max_weekly_drawdown: float = 5.0
    
    # VWAP parameters
    vwap_threshold: float = 0.2  # Sigma threshold
    vwap_window_minutes: int = 60  # Rolling window for sigma calculation
    session_anchor: str = "24/7"  # "24/7" for crypto, "London/NY" for FX
    
    # Delta proxy parameters
    delta_threshold: float = 1.5  # Multiplier for spike detection
    delta_window: int = 20  # Rolling window for average calculation
    
    # ATR ratio parameters
    atr_period: int = 14
    atr_ratio_threshold: float = 0.5  # M1 ATR < threshold * M5 ATR
    
    # Micro-BOS/CHOCH parameters
    min_displacement_atr: float = 0.25  # Minimum displacement in ATR units
    max_displacement_atr: float = 0.5   # Maximum displacement in ATR units
    cooldown_minutes: int = 5  # Cooldown between signals
    
    # Spread filter parameters
    spread_median_window: int = 20
    spread_outlier_clip: float = 2.0  # Clip outliers beyond 2x median
    exclude_news_windows: bool = True
    
    # Timeframe-specific parameters
    timeframes: Dict[str, Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timeframes is None:
            self.timeframes = {
                "H1": {"refresh_seconds": 60, "lookback_bars": 24},
                "M15": {"refresh_seconds": 15, "lookback_bars": 96},
                "M5": {"refresh_seconds": 5, "lookback_bars": 288},
                "M1": {"refresh_seconds": 1, "lookback_bars": 1440}
            }

class SymbolConfigManager:
    """Manages symbol-specific configurations with hot-reload"""
    
    def __init__(self, config_dir: str = "config/symbols"):
        self.config_dir = config_dir
        self.configs: Dict[str, SymbolConfig] = {}
        self.last_modified: Dict[str, float] = {}
        self._ensure_config_dir()
        
    def _ensure_config_dir(self):
        """Ensure config directory exists"""
        os.makedirs(self.config_dir, exist_ok=True)
        
    def load_symbol_config(self, symbol: str) -> Optional[SymbolConfig]:
        """Load configuration for a specific symbol"""
        config_path = os.path.join(self.config_dir, f"{symbol}.toml")
        
        if not os.path.exists(config_path):
            logger.warning(f"Config file not found for {symbol}: {config_path}")
            return None
            
        try:
            # Check if file was modified
            current_mtime = os.path.getmtime(config_path)
            if symbol in self.last_modified and current_mtime <= self.last_modified[symbol]:
                return self.configs.get(symbol)
                
            # Load and parse config
            config_data = toml.load(config_path)
            config = SymbolConfig(**config_data)
            
            # Cache the config
            self.configs[symbol] = config
            self.last_modified[symbol] = current_mtime
            
            logger.info(f"Loaded configuration for {symbol}")
            return config
            
        except Exception as e:
            logger.error(f"Error loading config for {symbol}: {e}")
            return None
            
    def get_config(self, symbol: str) -> Optional[SymbolConfig]:
        """Get configuration for symbol (with hot-reload check)"""
        return self.load_symbol_config(symbol)
        
    def create_default_configs(self):
        """Create default configuration files for all symbols"""
        
        # Phase 1 symbols (Week 1)
        phase1_symbols = {
            "BTCUSDc": {
                "symbol": "BTCUSD",
                "broker_symbol": "BTCUSDc",
                "binance_symbol": "BTCUSDT",
                "max_lot_size": 0.02,
                "default_risk_percent": 0.75,
                "vwap_threshold": 0.2,
                "delta_threshold": 1.5,
                "atr_ratio_threshold": 0.5,
                "session_anchor": "24/7"
            },
            "XAUUSDc": {
                "symbol": "XAUUSD", 
                "broker_symbol": "XAUUSDc",
                "max_lot_size": 0.02,
                "default_risk_percent": 0.75,
                "vwap_threshold": 0.15,
                "delta_threshold": 1.3,
                "atr_ratio_threshold": 0.4,
                "session_anchor": "London/NY"
            },
            "EURUSDc": {
                "symbol": "EURUSD",
                "broker_symbol": "EURUSDc", 
                "max_lot_size": 0.04,
                "default_risk_percent": 0.5,
                "vwap_threshold": 0.1,
                "delta_threshold": 1.2,
                "atr_ratio_threshold": 0.3,
                "session_anchor": "London/NY"
            }
        }
        
        # Phase 2 symbols (Week 2)
        phase2_symbols = {
            "USDCHFc": {
                "symbol": "USDCHF",
                "broker_symbol": "USDCHFc",
                "max_lot_size": 0.04,
                "default_risk_percent": 0.5,
                "vwap_threshold": 0.1,
                "delta_threshold": 1.2,
                "atr_ratio_threshold": 0.3,
                "session_anchor": "London/NY"
            },
            "AUDUSDc": {
                "symbol": "AUDUSD",
                "broker_symbol": "AUDUSDc",
                "max_lot_size": 0.04,
                "default_risk_percent": 0.5,
                "vwap_threshold": 0.15,
                "delta_threshold": 1.4,
                "atr_ratio_threshold": 0.4,
                "session_anchor": "Sydney/London"
            },
            "USDCADc": {
                "symbol": "USDCAD",
                "broker_symbol": "USDCADc",
                "max_lot_size": 0.04,
                "default_risk_percent": 0.5,
                "vwap_threshold": 0.12,
                "delta_threshold": 1.3,
                "atr_ratio_threshold": 0.35,
                "session_anchor": "London/NY"
            },
            "NZDUSDc": {
                "symbol": "NZDUSD",
                "broker_symbol": "NZDUSDc",
                "max_lot_size": 0.04,
                "default_risk_percent": 0.5,
                "vwap_threshold": 0.15,
                "delta_threshold": 1.4,
                "atr_ratio_threshold": 0.4,
                "session_anchor": "Sydney/London"
            }
        }
        
        # Phase 3 symbols (Week 3)
        phase3_symbols = {
            "EURJPYc": {
                "symbol": "EURJPY",
                "broker_symbol": "EURJPYc",
                "max_lot_size": 0.03,
                "default_risk_percent": 0.4,
                "vwap_threshold": 0.12,
                "delta_threshold": 1.3,
                "atr_ratio_threshold": 0.35,
                "session_anchor": "Tokyo/London"
            },
            "GBPJPYc": {
                "symbol": "GBPJPY",
                "broker_symbol": "GBPJPYc",
                "max_lot_size": 0.03,
                "default_risk_percent": 0.4,
                "vwap_threshold": 0.18,
                "delta_threshold": 1.5,
                "atr_ratio_threshold": 0.45,
                "session_anchor": "London"
            },
            "EURGBPc": {
                "symbol": "EURGBP",
                "broker_symbol": "EURGBPc",
                "max_lot_size": 0.03,
                "default_risk_percent": 0.4,
                "vwap_threshold": 0.08,
                "delta_threshold": 1.1,
                "atr_ratio_threshold": 0.25,
                "session_anchor": "London"
            }
        }
        
        # Phase 4 symbols (Week 4) - Additional forex majors
        phase4_symbols = {
            "GBPUSDc": {
                "symbol": "GBPUSD",
                "broker_symbol": "GBPUSDc",
                "max_lot_size": 0.04,
                "default_risk_percent": 0.5,
                "vwap_threshold": 0.15,
                "delta_threshold": 1.4,
                "atr_ratio_threshold": 0.4,
                "session_anchor": "London"
            },
            "USDJPYc": {
                "symbol": "USDJPY",
                "broker_symbol": "USDJPYc",
                "max_lot_size": 0.04,
                "default_risk_percent": 0.5,
                "vwap_threshold": 0.12,
                "delta_threshold": 1.3,
                "atr_ratio_threshold": 0.35,
                "session_anchor": "Tokyo/London"
            }
        }
        
        all_symbols = {**phase1_symbols, **phase2_symbols, **phase3_symbols, **phase4_symbols}
        
        for symbol, config_data in all_symbols.items():
            config_path = os.path.join(self.config_dir, f"{symbol}.toml")
            
            if not os.path.exists(config_path):
                try:
                    with open(config_path, 'w') as f:
                        toml.dump(config_data, f)
                    logger.info(f"Created default config for {symbol}")
                except Exception as e:
                    logger.error(f"Error creating config for {symbol}: {e}")
            else:
                logger.info(f"Config already exists for {symbol}")
                
    def validate_config(self, symbol: str) -> bool:
        """Validate configuration for a symbol"""
        config = self.get_config(symbol)
        if not config:
            return False
            
        # Validate required fields
        required_fields = ['symbol', 'broker_symbol', 'max_lot_size', 'default_risk_percent']
        for field in required_fields:
            if not hasattr(config, field) or getattr(config, field) is None:
                logger.error(f"Missing required field {field} for {symbol}")
                return False
                
        # Validate lot size limits
        if config.max_lot_size > 0.04:
            logger.error(f"Lot size {config.max_lot_size} exceeds limit for {symbol}")
            return False
            
        # Validate risk percentages
        if config.default_risk_percent > 1.0:
            logger.error(f"Risk percentage {config.default_risk_percent} exceeds 100% for {symbol}")
            return False
            
        logger.info(f"Configuration validation passed for {symbol}")
        return True
        
    def get_all_symbols(self) -> list:
        """Get list of all configured symbols"""
        symbols = []
        for filename in os.listdir(self.config_dir):
            if filename.endswith('.toml'):
                symbol = filename[:-5]  # Remove .toml extension
                symbols.append(symbol)
        return sorted(symbols)
        
    def reload_all_configs(self):
        """Reload all configurations (hot-reload)"""
        symbols = self.get_all_symbols()
        for symbol in symbols:
            self.load_symbol_config(symbol)
        logger.info(f"Reloaded configurations for {len(symbols)} symbols")


# Global config manager instance
config_manager = SymbolConfigManager()

def get_symbol_config(symbol: str) -> Optional[SymbolConfig]:
    """Get configuration for a symbol"""
    return config_manager.get_config(symbol)

def validate_all_configs() -> Dict[str, bool]:
    """Validate all symbol configurations"""
    results = {}
    symbols = config_manager.get_all_symbols()
    
    for symbol in symbols:
        results[symbol] = config_manager.validate_config(symbol)
        
    return results

# Example usage and testing
if __name__ == "__main__":
    # Initialize config manager
    manager = SymbolConfigManager()
    
    # Create default configurations
    manager.create_default_configs()
    
    # Test loading configurations
    test_symbols = ["BTCUSDc", "XAUUSDc", "EURUSDc"]
    
    for symbol in test_symbols:
        config = manager.get_config(symbol)
        if config:
            print(f"Loaded config for {symbol}:")
            print(f"  Max lot size: {config.max_lot_size}")
            print(f"  Risk percent: {config.default_risk_percent}")
            print(f"  VWAP threshold: {config.vwap_threshold}")
            print(f"  Session anchor: {config.session_anchor}")
            print()
    
    # Validate all configurations
    validation_results = validate_all_configs()
    print("Configuration validation results:")
    for symbol, is_valid in validation_results.items():
        status = "✓" if is_valid else "✗"
        print(f"  {symbol}: {status}")

