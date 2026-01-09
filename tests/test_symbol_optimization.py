"""
Comprehensive Symbol Optimization Tests
Tests symbol-specific parameter optimization for all 12 trading symbols
"""

import pytest
import json
import tempfile
import os
from typing import Dict, Any
from unittest.mock import Mock, patch

# Import optimization components
from config.symbol_optimization import (
    SymbolOptimizationManager,
    SymbolOptimizationConfig,
    AssetType,
    MarketSession,
    get_symbol_config,
    optimize_symbol,
    initialize_all_symbols
)

class TestSymbolOptimizationInitialization:
    """Test symbol optimization system initialization."""
    
    def test_optimization_manager_initialization(self):
        """Test optimization manager initialization."""
        manager = SymbolOptimizationManager()
        assert manager is not None
        assert hasattr(manager, 'symbol_configs')
        assert hasattr(manager, 'optimization_history')
        assert hasattr(manager, 'performance_metrics')
    
    def test_initialize_all_symbols(self):
        """Test initialization of all 12 symbols."""
        manager = SymbolOptimizationManager()
        manager.initialize_symbol_configs()
        
        # Check that all 12 symbols are configured
        expected_symbols = [
            "BTCUSDc", "ETHUSDc", "EURUSDc", "GBPUSDc", "USDJPYc",
            "AUDUSDc", "USDCADc", "NZDUSDc", "USDCHFc", "EURJPYc",
            "GBPJPYc", "EURGBPc", "XAUUSDc"
        ]
        
        assert len(manager.symbol_configs) == 13  # 12 forex + 1 commodity
        for symbol in expected_symbols:
            assert symbol in manager.symbol_configs, f"Symbol {symbol} not configured"
    
    def test_symbol_config_attributes(self):
        """Test that symbol configurations have all required attributes."""
        manager = SymbolOptimizationManager()
        manager.initialize_symbol_configs()
        
        # Test a few key symbols
        test_symbols = ["BTCUSDc", "EURUSDc", "XAUUSDc"]
        
        for symbol in test_symbols:
            config = manager.get_symbol_config(symbol)
            assert config is not None
            assert hasattr(config, 'symbol')
            assert hasattr(config, 'asset_type')
            assert hasattr(config, 'vwap_session_anchor')
            assert hasattr(config, 'delta_spike_threshold')
            assert hasattr(config, 'atr_ratio_threshold')
            assert hasattr(config, 'micro_bos_atr_displacement')
            assert hasattr(config, 'spread_normal_threshold')
            assert hasattr(config, 'max_lot_size')
            assert hasattr(config, 'latency_target_ms')

class TestSymbolSpecificConfigurations:
    """Test symbol-specific configuration differences."""
    
    def test_crypto_symbol_configurations(self):
        """Test crypto symbol specific configurations."""
        manager = SymbolOptimizationManager()
        manager.initialize_symbol_configs()
        
        # Test BTCUSDc configuration
        btc_config = manager.get_symbol_config("BTCUSDc")
        assert btc_config.asset_type == AssetType.CRYPTO
        assert btc_config.binance_symbol == "BTCUSDT"
        assert btc_config.vwap_session_anchor is False  # 24/7 market
        assert btc_config.vwap_sigma_window == 120  # Longer window
        assert btc_config.vwap_sigma_multiplier == 2.5  # Higher volatility
        assert btc_config.delta_spike_threshold == 3.0  # Higher threshold
        assert btc_config.atr_symbol_multiplier == 1.5  # Higher volatility
        assert btc_config.primary_session == MarketSession.CRYPTO_24_7
        assert btc_config.latency_target_ms == 150  # Faster for crypto
    
    def test_major_forex_configurations(self):
        """Test major forex pair configurations."""
        manager = SymbolOptimizationManager()
        manager.initialize_symbol_configs()
        
        # Test EURUSDc configuration
        eur_config = manager.get_symbol_config("EURUSDc")
        assert eur_config.asset_type == AssetType.FOREX
        assert eur_config.vwap_session_anchor is True  # Session-based
        assert eur_config.vwap_sigma_window == 60  # Standard window
        assert eur_config.vwap_sigma_multiplier == 2.0  # Standard volatility
        assert eur_config.delta_spike_threshold == 2.0  # Standard threshold
        assert eur_config.atr_symbol_multiplier == 1.0  # Standard multiplier
        assert eur_config.primary_session == MarketSession.LONDON
        assert eur_config.spread_normal_threshold == 1.0  # Lower spread
    
    def test_commodity_configurations(self):
        """Test commodity symbol configurations."""
        manager = SymbolOptimizationManager()
        manager.initialize_symbol_configs()
        
        # Test XAUUSDc configuration
        gold_config = manager.get_symbol_config("XAUUSDc")
        assert gold_config.asset_type == AssetType.COMMODITY
        assert gold_config.vwap_session_anchor is True
        assert gold_config.vwap_sigma_window == 90  # Longer window for gold
        assert gold_config.vwap_sigma_multiplier == 2.5  # Higher volatility
        assert gold_config.delta_spike_threshold == 2.5  # Higher threshold
        assert gold_config.atr_symbol_multiplier == 1.3  # Higher volatility
        assert gold_config.primary_session == MarketSession.LONDON
        assert gold_config.memory_limit_mb == 120  # Higher memory limit
    
    def test_volatile_forex_configurations(self):
        """Test volatile forex pair configurations."""
        manager = SymbolOptimizationManager()
        manager.initialize_symbol_configs()
        
        # Test GBPJPYc configuration (high volatility)
        gbpjpy_config = manager.get_symbol_config("GBPJPYc")
        assert gbpjpy_config.asset_type == AssetType.FOREX
        assert gbpjpy_config.vwap_sigma_multiplier == 2.3  # Higher volatility
        assert gbpjpy_config.delta_spike_threshold == 2.3  # Higher threshold
        assert gbpjpy_config.atr_symbol_multiplier == 1.15  # Higher volatility
        assert gbpjpy_config.micro_bos_atr_displacement == 0.28  # Higher displacement
        assert gbpjpy_config.spread_normal_threshold == 1.3  # Higher spread tolerance

class TestParameterOptimization:
    """Test parameter optimization based on performance data."""
    
    def test_optimize_symbol_parameters(self):
        """Test parameter optimization for a symbol."""
        manager = SymbolOptimizationManager()
        manager.initialize_symbol_configs()
        
        # Test optimization with performance data
        performance_data = {
            'win_rate': 0.7,
            'avg_rr': 2.5,
            'max_drawdown': 0.03,
            'volatility': 1.2,
            'latency': 150
        }
        
        optimized_config = manager.optimize_symbol_parameters("EURUSDc", performance_data)
        
        assert optimized_config is not None
        assert optimized_config.symbol == "EURUSDc"
        
        # Check that parameters were adjusted based on performance
        original_config = manager.get_symbol_config("EURUSDc")
        
        # Higher win rate should increase daily trades
        assert optimized_config.max_daily_trades > original_config.max_daily_trades
        
        # Higher volatility should increase thresholds
        assert optimized_config.vwap_sigma_multiplier > original_config.vwap_sigma_multiplier
        assert optimized_config.delta_spike_threshold > original_config.delta_spike_threshold
    
    def test_optimization_with_poor_performance(self):
        """Test optimization with poor performance data."""
        manager = SymbolOptimizationManager()
        manager.initialize_symbol_configs()
        
        # Test optimization with poor performance data
        poor_performance = {
            'win_rate': 0.3,
            'avg_rr': 0.8,
            'max_drawdown': 0.08,
            'volatility': 0.8,
            'latency': 300
        }
        
        optimized_config = manager.optimize_symbol_parameters("BTCUSDc", poor_performance)
        
        # Poor performance should lead to more conservative parameters
        original_config = manager.get_symbol_config("BTCUSDc")
        
        # Lower win rate should result in fewer daily trades (but still within bounds)
        assert optimized_config.max_daily_trades <= original_config.max_daily_trades or optimized_config.max_daily_trades <= 15
        
        # Higher latency should increase buffer capacity
        assert optimized_config.buffer_capacity > original_config.buffer_capacity
    
    def test_optimization_history_tracking(self):
        """Test that optimization history is tracked."""
        manager = SymbolOptimizationManager()
        manager.initialize_symbol_configs()
        
        initial_history_count = len(manager.optimization_history)
        
        # Perform optimization
        performance_data = {
            'win_rate': 0.6,
            'avg_rr': 1.8,
            'max_drawdown': 0.05,
            'volatility': 1.0,
            'latency': 200
        }
        
        manager.optimize_symbol_parameters("GBPUSDc", performance_data)
        
        # Check that history was recorded
        assert len(manager.optimization_history) == initial_history_count + 1
        
        # Check history entry
        latest_entry = manager.optimization_history[-1]
        assert latest_entry['symbol'] == "GBPUSDc"
        assert 'timestamp' in latest_entry
        assert 'performance_data' in latest_entry
        assert 'optimization_changes' in latest_entry

class TestConfigurationManagement:
    """Test configuration management functionality."""
    
    def test_save_and_load_configurations(self):
        """Test saving and loading configurations."""
        manager = SymbolOptimizationManager()
        manager.initialize_symbol_configs()
        
        # Save configurations to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
        
        try:
            manager.save_configurations(temp_file)
            
            # Create new manager and load configurations
            new_manager = SymbolOptimizationManager()
            new_manager.load_configurations(temp_file)
            
            # Check that configurations were loaded
            assert len(new_manager.symbol_configs) == len(manager.symbol_configs)
            
            # Check a specific symbol
            original_config = manager.get_symbol_config("EURUSDc")
            loaded_config = new_manager.get_symbol_config("EURUSDc")
            
            assert loaded_config.symbol == original_config.symbol
            assert loaded_config.asset_type == original_config.asset_type
            assert loaded_config.vwap_sigma_window == original_config.vwap_sigma_window
            
        finally:
            os.unlink(temp_file)
    
    def test_get_optimization_summary(self):
        """Test optimization summary generation."""
        manager = SymbolOptimizationManager()
        manager.initialize_symbol_configs()
        
        summary = manager.get_optimization_summary()
        
        assert 'total_symbols' in summary
        assert 'optimization_history_count' in summary
        assert 'symbols' in summary
        
        assert summary['total_symbols'] == 13
        assert summary['optimization_history_count'] == 0
        
        # Check symbol summary
        assert 'BTCUSDc' in summary['symbols']
        assert 'EURUSDc' in summary['symbols']
        assert 'XAUUSDc' in summary['symbols']
        
        # Check symbol details
        btc_summary = summary['symbols']['BTCUSDc']
        assert 'asset_type' in btc_summary
        assert 'primary_session' in btc_summary
        assert 'max_lot_size' in btc_summary
        assert 'latency_target_ms' in btc_summary

class TestGlobalFunctions:
    """Test global optimization functions."""
    
    def test_get_symbol_config_function(self):
        """Test global get_symbol_config function."""
        initialize_all_symbols()
        
        # Test getting existing symbol
        config = get_symbol_config("EURUSDc")
        assert config is not None
        assert config.symbol == "EURUSDc"
        
        # Test getting non-existing symbol
        config = get_symbol_config("NONEXISTENT")
        assert config is None
    
    def test_optimize_symbol_function(self):
        """Test global optimize_symbol function."""
        initialize_all_symbols()
        
        performance_data = {
            'win_rate': 0.65,
            'avg_rr': 2.0,
            'max_drawdown': 0.04,
            'volatility': 1.1,
            'latency': 180
        }
        
        optimized_config = optimize_symbol("USDJPYc", performance_data)
        
        assert optimized_config is not None
        assert optimized_config.symbol == "USDJPYc"
        assert optimized_config.asset_type == AssetType.FOREX

class TestParameterValidation:
    """Test parameter validation and constraints."""
    
    def test_parameter_bounds(self):
        """Test that optimized parameters stay within bounds."""
        manager = SymbolOptimizationManager()
        manager.initialize_symbol_configs()
        
        # Test with extreme performance data
        extreme_performance = {
            'win_rate': 0.95,  # Very high win rate
            'avg_rr': 5.0,     # Very high R:R
            'max_drawdown': 0.01,  # Very low drawdown
            'volatility': 3.0,  # Very high volatility
            'latency': 50      # Very low latency
        }
        
        optimized_config = manager.optimize_symbol_parameters("AUDUSDc", extreme_performance)
        
        # Check that parameters are within reasonable bounds
        assert 0.5 <= optimized_config.vwap_sigma_multiplier <= 3.0
        assert 1.5 <= optimized_config.delta_spike_threshold <= 3.5
        assert 0.8 <= optimized_config.atr_symbol_multiplier <= 1.5
        assert 0.2 <= optimized_config.micro_bos_atr_displacement <= 0.5
        assert 0.5 <= optimized_config.spread_normal_threshold <= 3.0
        assert 5 <= optimized_config.max_daily_trades <= 20
        assert 1.5 <= optimized_config.stop_loss_atr_multiplier <= 3.0
        assert 2.0 <= optimized_config.take_profit_atr_multiplier <= 5.0
    
    def test_asset_type_consistency(self):
        """Test that asset type remains consistent during optimization."""
        manager = SymbolOptimizationManager()
        manager.initialize_symbol_configs()
        
        performance_data = {
            'win_rate': 0.6,
            'avg_rr': 1.8,
            'max_drawdown': 0.05,
            'volatility': 1.0,
            'latency': 200
        }
        
        # Test crypto symbol
        crypto_optimized = manager.optimize_symbol_parameters("BTCUSDc", performance_data)
        assert crypto_optimized.asset_type == AssetType.CRYPTO
        
        # Test forex symbol
        forex_optimized = manager.optimize_symbol_parameters("EURUSDc", performance_data)
        assert forex_optimized.asset_type == AssetType.FOREX
        
        # Test commodity symbol
        commodity_optimized = manager.optimize_symbol_parameters("XAUUSDc", performance_data)
        assert commodity_optimized.asset_type == AssetType.COMMODITY

class TestPerformanceOptimization:
    """Test performance optimization features."""
    
    def test_latency_optimization(self):
        """Test latency-based optimization."""
        manager = SymbolOptimizationManager()
        manager.initialize_symbol_configs()
        
        # Test with high latency
        high_latency_data = {
            'win_rate': 0.6,
            'avg_rr': 1.8,
            'max_drawdown': 0.05,
            'volatility': 1.0,
            'latency': 400  # High latency
        }
        
        optimized_config = manager.optimize_symbol_parameters("USDCADc", high_latency_data)
        
        # High latency should increase buffer capacity and batch size
        original_config = manager.get_symbol_config("USDCADc")
        assert optimized_config.buffer_capacity > original_config.buffer_capacity
        assert optimized_config.processing_batch_size > original_config.processing_batch_size
        assert optimized_config.latency_target_ms > original_config.latency_target_ms
    
    def test_memory_optimization(self):
        """Test memory optimization based on latency."""
        manager = SymbolOptimizationManager()
        manager.initialize_symbol_configs()
        
        # Test with very high latency
        extreme_latency_data = {
            'win_rate': 0.6,
            'avg_rr': 1.8,
            'max_drawdown': 0.05,
            'volatility': 1.0,
            'latency': 600  # Very high latency
        }
        
        optimized_config = manager.optimize_symbol_parameters("NZDUSDc", extreme_latency_data)
        
        # Very high latency should increase memory limit
        original_config = manager.get_symbol_config("NZDUSDc")
        assert optimized_config.memory_limit_mb > original_config.memory_limit_mb

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
