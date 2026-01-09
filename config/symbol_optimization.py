"""
Symbol-Specific Optimization Tuning
Comprehensive parameter optimization for all 12 trading symbols
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AssetType(Enum):
    """Asset type classifications."""
    CRYPTO = "crypto"
    FOREX = "forex"
    COMMODITY = "commodity"

class MarketSession(Enum):
    """Market session classifications."""
    ASIAN = "asian"
    LONDON = "london"
    NEW_YORK = "new_york"
    OVERLAP = "overlap"
    CRYPTO_24_7 = "crypto_24_7"

@dataclass
class SymbolOptimizationConfig:
    """Symbol-specific optimization configuration."""
    symbol: str
    asset_type: AssetType
    binance_symbol: Optional[str] = None
    
    # VWAP Configuration
    vwap_session_anchor: bool = True
    vwap_sigma_window: int = 60
    vwap_sigma_multiplier: float = 2.0
    
    # Delta Proxy Configuration
    delta_spike_threshold: float = 2.0
    delta_lookback_period: int = 20
    delta_min_volume: float = 0.1
    
    # ATR Ratio Configuration
    atr_m1_period: int = 14
    atr_m5_period: int = 14
    atr_ratio_threshold: float = 1.5
    atr_symbol_multiplier: float = 1.0
    atr_high_volatility_threshold: float = 1.5
    atr_low_volatility_threshold: float = 0.5
    atr_extreme_volatility_threshold: float = 2.0
    
    # Micro-BOS/CHOCH Configuration
    micro_bos_bar_lookback: int = 5
    micro_bos_atr_displacement: float = 0.25
    micro_bos_cooldown_period: int = 3
    micro_bos_min_volume_threshold: float = 1.0
    
    # Spread Filter Configuration
    spread_normal_threshold: float = 1.5
    spread_elevated_threshold: float = 3.0
    spread_high_threshold: float = 5.0
    spread_extreme_threshold: float = 10.0
    spread_median_window: int = 20
    
    # Risk Management Configuration
    max_lot_size: float = 0.01
    max_daily_trades: int = 10
    max_drawdown_percent: float = 5.0
    stop_loss_atr_multiplier: float = 2.0
    take_profit_atr_multiplier: float = 3.0
    
    # Market Session Configuration
    primary_session: MarketSession = MarketSession.LONDON
    secondary_session: MarketSession = MarketSession.NEW_YORK
    session_overlap_hours: int = 2
    
    # Performance Optimization
    buffer_capacity: int = 10000
    processing_batch_size: int = 100
    latency_target_ms: int = 200
    memory_limit_mb: int = 100

class SymbolOptimizationManager:
    """Manages symbol-specific optimization tuning."""
    
    def __init__(self):
        self.symbol_configs: Dict[str, SymbolOptimizationConfig] = {}
        self.optimization_history: List[Dict[str, Any]] = []
        self.performance_metrics: Dict[str, Dict[str, float]] = {}
        
    def initialize_symbol_configs(self):
        """Initialize optimization configurations for all 12 symbols."""
        
        # Crypto Symbols
        self.symbol_configs["BTCUSDc"] = SymbolOptimizationConfig(
            symbol="BTCUSDc",
            asset_type=AssetType.CRYPTO,
            binance_symbol="BTCUSDT",
            vwap_session_anchor=False,  # 24/7 market
            vwap_sigma_window=120,  # Longer window for crypto
            vwap_sigma_multiplier=2.5,  # Higher volatility
            delta_spike_threshold=3.0,  # Higher threshold for crypto
            delta_lookback_period=30,  # Longer lookback
            atr_symbol_multiplier=1.5,  # Higher volatility multiplier
            atr_high_volatility_threshold=2.0,  # Higher threshold
            micro_bos_atr_displacement=0.3,  # Higher displacement
            spread_normal_threshold=2.0,  # Higher spread tolerance
            spread_elevated_threshold=5.0,
            spread_high_threshold=10.0,
            spread_extreme_threshold=20.0,
            primary_session=MarketSession.CRYPTO_24_7,
            max_lot_size=0.01,
            latency_target_ms=150,  # Faster for crypto
            memory_limit_mb=150
        )
        
        self.symbol_configs["ETHUSDc"] = SymbolOptimizationConfig(
            symbol="ETHUSDc",
            asset_type=AssetType.CRYPTO,
            binance_symbol="ETHUSDT",
            vwap_session_anchor=False,
            vwap_sigma_window=120,
            vwap_sigma_multiplier=2.5,
            delta_spike_threshold=3.0,
            delta_lookback_period=30,
            atr_symbol_multiplier=1.5,
            atr_high_volatility_threshold=2.0,
            micro_bos_atr_displacement=0.3,
            spread_normal_threshold=2.0,
            spread_elevated_threshold=5.0,
            spread_high_threshold=10.0,
            spread_extreme_threshold=20.0,
            primary_session=MarketSession.CRYPTO_24_7,
            max_lot_size=0.01,
            latency_target_ms=150,
            memory_limit_mb=150
        )
        
        # Major Forex Pairs
        self.symbol_configs["EURUSDc"] = SymbolOptimizationConfig(
            symbol="EURUSDc",
            asset_type=AssetType.FOREX,
            vwap_session_anchor=True,
            vwap_sigma_window=60,
            vwap_sigma_multiplier=2.0,
            delta_spike_threshold=2.0,
            delta_lookback_period=20,
            atr_symbol_multiplier=1.0,
            atr_high_volatility_threshold=1.5,
            micro_bos_atr_displacement=0.25,
            spread_normal_threshold=1.0,  # Lower spread for major pairs
            spread_elevated_threshold=2.0,
            spread_high_threshold=3.0,
            spread_extreme_threshold=5.0,
            primary_session=MarketSession.LONDON,
            secondary_session=MarketSession.NEW_YORK,
            session_overlap_hours=2,
            max_lot_size=0.01,
            latency_target_ms=200,
            memory_limit_mb=100
        )
        
        self.symbol_configs["GBPUSDc"] = SymbolOptimizationConfig(
            symbol="GBPUSDc",
            asset_type=AssetType.FOREX,
            vwap_session_anchor=True,
            vwap_sigma_window=60,
            vwap_sigma_multiplier=2.2,  # Slightly higher volatility
            delta_spike_threshold=2.2,
            delta_lookback_period=22,
            atr_symbol_multiplier=1.1,
            atr_high_volatility_threshold=1.6,
            micro_bos_atr_displacement=0.26,
            spread_normal_threshold=1.2,
            spread_elevated_threshold=2.5,
            spread_high_threshold=4.0,
            spread_extreme_threshold=6.0,
            primary_session=MarketSession.LONDON,
            secondary_session=MarketSession.NEW_YORK,
            session_overlap_hours=2,
            max_lot_size=0.01,
            latency_target_ms=200,
            memory_limit_mb=100
        )
        
        self.symbol_configs["USDJPYc"] = SymbolOptimizationConfig(
            symbol="USDJPYc",
            asset_type=AssetType.FOREX,
            vwap_session_anchor=True,
            vwap_sigma_window=60,
            vwap_sigma_multiplier=2.0,
            delta_spike_threshold=2.0,
            delta_lookback_period=20,
            atr_symbol_multiplier=1.0,
            atr_high_volatility_threshold=1.5,
            micro_bos_atr_displacement=0.25,
            spread_normal_threshold=1.0,
            spread_elevated_threshold=2.0,
            spread_high_threshold=3.0,
            spread_extreme_threshold=5.0,
            primary_session=MarketSession.ASIAN,
            secondary_session=MarketSession.LONDON,
            session_overlap_hours=1,
            max_lot_size=0.01,
            latency_target_ms=200,
            memory_limit_mb=100
        )
        
        self.symbol_configs["AUDUSDc"] = SymbolOptimizationConfig(
            symbol="AUDUSDc",
            asset_type=AssetType.FOREX,
            vwap_session_anchor=True,
            vwap_sigma_window=60,
            vwap_sigma_multiplier=2.1,
            delta_spike_threshold=2.1,
            delta_lookback_period=21,
            atr_symbol_multiplier=1.05,
            atr_high_volatility_threshold=1.55,
            micro_bos_atr_displacement=0.26,
            spread_normal_threshold=1.1,
            spread_elevated_threshold=2.2,
            spread_high_threshold=3.5,
            spread_extreme_threshold=5.5,
            primary_session=MarketSession.ASIAN,
            secondary_session=MarketSession.LONDON,
            session_overlap_hours=1,
            max_lot_size=0.01,
            latency_target_ms=200,
            memory_limit_mb=100
        )
        
        self.symbol_configs["USDCADc"] = SymbolOptimizationConfig(
            symbol="USDCADc",
            asset_type=AssetType.FOREX,
            vwap_session_anchor=True,
            vwap_sigma_window=60,
            vwap_sigma_multiplier=2.0,
            delta_spike_threshold=2.0,
            delta_lookback_period=20,
            atr_symbol_multiplier=1.0,
            atr_high_volatility_threshold=1.5,
            micro_bos_atr_displacement=0.25,
            spread_normal_threshold=1.0,
            spread_elevated_threshold=2.0,
            spread_high_threshold=3.0,
            spread_extreme_threshold=5.0,
            primary_session=MarketSession.NEW_YORK,
            secondary_session=MarketSession.LONDON,
            session_overlap_hours=2,
            max_lot_size=0.01,
            latency_target_ms=200,
            memory_limit_mb=100
        )
        
        self.symbol_configs["NZDUSDc"] = SymbolOptimizationConfig(
            symbol="NZDUSDc",
            asset_type=AssetType.FOREX,
            vwap_session_anchor=True,
            vwap_sigma_window=60,
            vwap_sigma_multiplier=2.2,
            delta_spike_threshold=2.2,
            delta_lookback_period=22,
            atr_symbol_multiplier=1.1,
            atr_high_volatility_threshold=1.6,
            micro_bos_atr_displacement=0.26,
            spread_normal_threshold=1.2,
            spread_elevated_threshold=2.5,
            spread_high_threshold=4.0,
            spread_extreme_threshold=6.0,
            primary_session=MarketSession.ASIAN,
            secondary_session=MarketSession.LONDON,
            session_overlap_hours=1,
            max_lot_size=0.01,
            latency_target_ms=200,
            memory_limit_mb=100
        )
        
        self.symbol_configs["USDCHFc"] = SymbolOptimizationConfig(
            symbol="USDCHFc",
            asset_type=AssetType.FOREX,
            vwap_session_anchor=True,
            vwap_sigma_window=60,
            vwap_sigma_multiplier=2.0,
            delta_spike_threshold=2.0,
            delta_lookback_period=20,
            atr_symbol_multiplier=1.0,
            atr_high_volatility_threshold=1.5,
            micro_bos_atr_displacement=0.25,
            spread_normal_threshold=1.0,
            spread_elevated_threshold=2.0,
            spread_high_threshold=3.0,
            spread_extreme_threshold=5.0,
            primary_session=MarketSession.LONDON,
            secondary_session=MarketSession.NEW_YORK,
            session_overlap_hours=2,
            max_lot_size=0.01,
            latency_target_ms=200,
            memory_limit_mb=100
        )
        
        # Cross Currency Pairs
        self.symbol_configs["EURJPYc"] = SymbolOptimizationConfig(
            symbol="EURJPYc",
            asset_type=AssetType.FOREX,
            vwap_session_anchor=True,
            vwap_sigma_window=60,
            vwap_sigma_multiplier=2.1,
            delta_spike_threshold=2.1,
            delta_lookback_period=21,
            atr_symbol_multiplier=1.05,
            atr_high_volatility_threshold=1.55,
            micro_bos_atr_displacement=0.26,
            spread_normal_threshold=1.1,
            spread_elevated_threshold=2.2,
            spread_high_threshold=3.5,
            spread_extreme_threshold=5.5,
            primary_session=MarketSession.LONDON,
            secondary_session=MarketSession.ASIAN,
            session_overlap_hours=1,
            max_lot_size=0.01,
            latency_target_ms=200,
            memory_limit_mb=100
        )
        
        self.symbol_configs["GBPJPYc"] = SymbolOptimizationConfig(
            symbol="GBPJPYc",
            asset_type=AssetType.FOREX,
            vwap_session_anchor=True,
            vwap_sigma_window=60,
            vwap_sigma_multiplier=2.3,  # Higher volatility for GBP/JPY
            delta_spike_threshold=2.3,
            delta_lookback_period=23,
            atr_symbol_multiplier=1.15,
            atr_high_volatility_threshold=1.7,
            micro_bos_atr_displacement=0.28,
            spread_normal_threshold=1.3,
            spread_elevated_threshold=2.8,
            spread_high_threshold=4.5,
            spread_extreme_threshold=7.0,
            primary_session=MarketSession.LONDON,
            secondary_session=MarketSession.ASIAN,
            session_overlap_hours=1,
            max_lot_size=0.01,
            latency_target_ms=200,
            memory_limit_mb=100
        )
        
        self.symbol_configs["EURGBPc"] = SymbolOptimizationConfig(
            symbol="EURGBPc",
            asset_type=AssetType.FOREX,
            vwap_session_anchor=True,
            vwap_sigma_window=60,
            vwap_sigma_multiplier=2.0,
            delta_spike_threshold=2.0,
            delta_lookback_period=20,
            atr_symbol_multiplier=1.0,
            atr_high_volatility_threshold=1.5,
            micro_bos_atr_displacement=0.25,
            spread_normal_threshold=1.0,
            spread_elevated_threshold=2.0,
            spread_high_threshold=3.0,
            spread_extreme_threshold=5.0,
            primary_session=MarketSession.LONDON,
            secondary_session=MarketSession.NEW_YORK,
            session_overlap_hours=2,
            max_lot_size=0.01,
            latency_target_ms=200,
            memory_limit_mb=100
        )
        
        # Commodity
        self.symbol_configs["XAUUSDc"] = SymbolOptimizationConfig(
            symbol="XAUUSDc",
            asset_type=AssetType.COMMODITY,
            vwap_session_anchor=True,
            vwap_sigma_window=90,  # Longer window for gold
            vwap_sigma_multiplier=2.5,  # Higher volatility
            delta_spike_threshold=2.5,
            delta_lookback_period=25,
            atr_symbol_multiplier=1.3,
            atr_high_volatility_threshold=1.8,
            micro_bos_atr_displacement=0.3,
            spread_normal_threshold=1.5,
            spread_elevated_threshold=3.0,
            spread_high_threshold=5.0,
            spread_extreme_threshold=8.0,
            primary_session=MarketSession.LONDON,
            secondary_session=MarketSession.NEW_YORK,
            session_overlap_hours=2,
            max_lot_size=0.01,
            latency_target_ms=200,
            memory_limit_mb=120
        )
        
        logger.info(f"Initialized optimization configurations for {len(self.symbol_configs)} symbols")
    
    def get_symbol_config(self, symbol: str) -> Optional[SymbolOptimizationConfig]:
        """Get optimization configuration for a specific symbol."""
        return self.symbol_configs.get(symbol)
    
    def update_symbol_config(self, symbol: str, config: SymbolOptimizationConfig):
        """Update optimization configuration for a specific symbol."""
        self.symbol_configs[symbol] = config
        logger.info(f"Updated optimization configuration for {symbol}")
    
    def optimize_symbol_parameters(self, symbol: str, performance_data: Dict[str, Any]) -> SymbolOptimizationConfig:
        """Optimize parameters for a specific symbol based on performance data."""
        current_config = self.get_symbol_config(symbol)
        if not current_config:
            raise ValueError(f"No configuration found for symbol {symbol}")
        
        # Extract performance metrics
        win_rate = performance_data.get('win_rate', 0.5)
        avg_rr = performance_data.get('avg_rr', 1.0)
        max_drawdown = performance_data.get('max_drawdown', 0.0)
        volatility = performance_data.get('volatility', 1.0)
        latency = performance_data.get('latency', 200)
        
        # Create optimized configuration
        optimized_config = SymbolOptimizationConfig(
            symbol=symbol,
            asset_type=current_config.asset_type,
            binance_symbol=current_config.binance_symbol,
            
            # Adjust VWAP parameters based on volatility
            vwap_session_anchor=current_config.vwap_session_anchor,
            vwap_sigma_window=max(30, min(120, int(60 * volatility))),
            vwap_sigma_multiplier=max(1.5, min(3.0, 2.0 * volatility)),
            
            # Adjust delta parameters based on performance
            delta_spike_threshold=max(1.5, min(3.5, 2.0 + (1.0 - win_rate))),
            delta_lookback_period=max(10, min(50, int(20 * (1.0 + volatility)))),
            delta_min_volume=current_config.delta_min_volume,
            
            # Adjust ATR parameters based on volatility
            atr_m1_period=current_config.atr_m1_period,
            atr_m5_period=current_config.atr_m5_period,
            atr_ratio_threshold=max(1.2, min(2.0, 1.5 * volatility)),
            atr_symbol_multiplier=max(0.8, min(1.5, 1.0 * volatility)),
            atr_high_volatility_threshold=max(1.2, min(2.5, 1.5 * volatility)),
            atr_low_volatility_threshold=max(0.3, min(0.8, 0.5 * volatility)),
            atr_extreme_volatility_threshold=max(1.8, min(3.0, 2.0 * volatility)),
            
            # Adjust micro-BOS parameters based on performance
            micro_bos_bar_lookback=max(3, min(10, int(5 * (1.0 + volatility)))),
            micro_bos_atr_displacement=max(0.2, min(0.5, 0.25 * (1.0 + volatility))),
            micro_bos_cooldown_period=max(2, min(5, int(3 * (1.0 + volatility)))),
            micro_bos_min_volume_threshold=current_config.micro_bos_min_volume_threshold,
            
            # Adjust spread parameters based on performance
            spread_normal_threshold=max(0.5, min(3.0, 1.5 * (1.0 + volatility))),
            spread_elevated_threshold=max(1.0, min(6.0, 3.0 * (1.0 + volatility))),
            spread_high_threshold=max(2.0, min(10.0, 5.0 * (1.0 + volatility))),
            spread_extreme_threshold=max(5.0, min(20.0, 10.0 * (1.0 + volatility))),
            spread_median_window=current_config.spread_median_window,
            
            # Adjust risk parameters based on performance
            max_lot_size=current_config.max_lot_size,
            max_daily_trades=max(5, min(20, int(10 * (1.0 + win_rate)))),  # Higher win rate = more trades
            max_drawdown_percent=max(3.0, min(8.0, 5.0 * (1.0 + max_drawdown))),
            stop_loss_atr_multiplier=max(1.5, min(3.0, 2.0 * (1.0 + volatility))),
            take_profit_atr_multiplier=max(2.0, min(5.0, 3.0 * (1.0 + avg_rr))),
            
            # Keep session configuration
            primary_session=current_config.primary_session,
            secondary_session=current_config.secondary_session,
            session_overlap_hours=current_config.session_overlap_hours,
            
            # Adjust performance parameters based on latency
            buffer_capacity=max(5000, min(20000, int(10000 * (1.0 + latency/200)))),
            processing_batch_size=max(50, min(200, int(100 * (1.0 + latency/200)))),
            latency_target_ms=max(100, min(500, int(200 * (1.0 + latency/200)))),
            memory_limit_mb=max(50, min(200, int(100 * (1.0 + latency/200))))
        )
        
        # Record optimization
        self.optimization_history.append({
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'performance_data': performance_data,
            'optimization_changes': self._calculate_parameter_changes(current_config, optimized_config)
        })
        
        return optimized_config
    
    def _calculate_parameter_changes(self, old_config: SymbolOptimizationConfig, new_config: SymbolOptimizationConfig) -> Dict[str, Any]:
        """Calculate parameter changes between configurations."""
        changes = {}
        
        # Compare key parameters
        key_params = [
            'vwap_sigma_window', 'vwap_sigma_multiplier',
            'delta_spike_threshold', 'delta_lookback_period',
            'atr_ratio_threshold', 'atr_symbol_multiplier',
            'micro_bos_atr_displacement', 'micro_bos_cooldown_period',
            'spread_normal_threshold', 'spread_elevated_threshold'
        ]
        
        for param in key_params:
            old_value = getattr(old_config, param)
            new_value = getattr(new_config, param)
            if old_value != new_value:
                changes[param] = {
                    'old': old_value,
                    'new': new_value,
                    'change_percent': ((new_value - old_value) / old_value) * 100 if old_value != 0 else 0
                }
        
        return changes
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """Get summary of all symbol optimizations."""
        summary = {
            'total_symbols': len(self.symbol_configs),
            'optimization_history_count': len(self.optimization_history),
            'symbols': {}
        }
        
        for symbol, config in self.symbol_configs.items():
            summary['symbols'][symbol] = {
                'asset_type': config.asset_type.value,
                'primary_session': config.primary_session.value,
                'max_lot_size': config.max_lot_size,
                'latency_target_ms': config.latency_target_ms,
                'memory_limit_mb': config.memory_limit_mb
            }
        
        return summary
    
    def save_configurations(self, filepath: str):
        """Save all configurations to a JSON file."""
        config_data = {}
        for symbol, config in self.symbol_configs.items():
            config_data[symbol] = asdict(config)
        
        with open(filepath, 'w') as f:
            json.dump(config_data, f, indent=2, default=str)
        
        logger.info(f"Saved {len(config_data)} symbol configurations to {filepath}")
    
    def load_configurations(self, filepath: str):
        """Load configurations from a JSON file."""
        with open(filepath, 'r') as f:
            config_data = json.load(f)
        
        self.symbol_configs = {}
        for symbol, data in config_data.items():
            # Convert string enums back to enum objects
            if 'asset_type' in data:
                # Handle both string values and enum representations
                asset_type_value = data['asset_type']
                if isinstance(asset_type_value, str) and asset_type_value.startswith('AssetType.'):
                    asset_type_value = asset_type_value.split('.')[1]
                # Convert to lowercase for enum matching
                asset_type_value = asset_type_value.lower()
                data['asset_type'] = AssetType(asset_type_value)
            if 'primary_session' in data:
                session_value = data['primary_session']
                if isinstance(session_value, str) and session_value.startswith('MarketSession.'):
                    session_value = session_value.split('.')[1]
                # Convert to lowercase for enum matching
                session_value = session_value.lower()
                data['primary_session'] = MarketSession(session_value)
            if 'secondary_session' in data:
                session_value = data['secondary_session']
                if isinstance(session_value, str) and session_value.startswith('MarketSession.'):
                    session_value = session_value.split('.')[1]
                # Convert to lowercase for enum matching
                session_value = session_value.lower()
                data['secondary_session'] = MarketSession(session_value)
            
            self.symbol_configs[symbol] = SymbolOptimizationConfig(**data)
        
        logger.info(f"Loaded {len(self.symbol_configs)} symbol configurations from {filepath}")

# Global optimization manager instance
optimization_manager = SymbolOptimizationManager()

def get_symbol_config(symbol: str) -> Optional[SymbolOptimizationConfig]:
    """Get optimization configuration for a symbol."""
    return optimization_manager.get_symbol_config(symbol)

def optimize_symbol(symbol: str, performance_data: Dict[str, Any]) -> SymbolOptimizationConfig:
    """Optimize parameters for a symbol based on performance data."""
    return optimization_manager.optimize_symbol_parameters(symbol, performance_data)

def initialize_all_symbols():
    """Initialize optimization configurations for all symbols."""
    optimization_manager.initialize_symbol_configs()

if __name__ == "__main__":
    # Initialize all symbol configurations
    initialize_all_symbols()
    
    # Print summary
    summary = optimization_manager.get_optimization_summary()
    print(f"Initialized {summary['total_symbols']} symbol configurations")
    
    # Save configurations
    optimization_manager.save_configurations("config/symbol_optimizations.json")
