"""
Comprehensive tests for Binance symbol normalization system

Tests symbol mapping, normalization, asset type detection,
and configuration management for broker-to-Binance symbol conversion.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from infra.binance_symbol_normalization import (
    BinanceSymbolNormalizer, SymbolMapping, NormalizationResult,
    AssetType, get_normalizer, normalize_broker_to_binance,
    normalize_binance_to_broker, get_binance_symbol, get_broker_symbol,
    is_crypto_symbol, is_forex_symbol, is_metals_symbol,
    get_supported_crypto_symbols, get_supported_forex_symbols,
    get_mapping_statistics
)

class TestAssetType:
    """Test asset type enumeration"""
    
    def test_asset_types(self):
        """Test all asset types"""
        asset_types = [
            AssetType.CRYPTO,
            AssetType.FOREX,
            AssetType.METALS,
            AssetType.INDICES,
            AssetType.COMMODITIES
        ]
        
        for asset_type in asset_types:
            assert isinstance(asset_type, AssetType)
            assert asset_type.value in ["crypto", "forex", "metals", "indices", "commodities"]

class TestSymbolMapping:
    """Test symbol mapping data structure"""
    
    def test_symbol_mapping_creation(self):
        """Test symbol mapping creation"""
        mapping = SymbolMapping(
            broker_symbol="BTCUSDc",
            binance_symbol="BTCUSDT",
            asset_type=AssetType.CRYPTO,
            base_currency="BTC",
            quote_currency="USDT",
            is_active=True,
            description="Bitcoin vs USDT"
        )
        
        assert mapping.broker_symbol == "BTCUSDc"
        assert mapping.binance_symbol == "BTCUSDT"
        assert mapping.asset_type == AssetType.CRYPTO
        assert mapping.base_currency == "BTC"
        assert mapping.quote_currency == "USDT"
        assert mapping.is_active is True
        assert mapping.description == "Bitcoin vs USDT"
    
    def test_symbol_mapping_defaults(self):
        """Test symbol mapping with defaults"""
        mapping = SymbolMapping(
            broker_symbol="EURUSDc",
            binance_symbol=None,
            asset_type=AssetType.FOREX,
            base_currency="EUR",
            quote_currency="USD"
        )
        
        assert mapping.broker_symbol == "EURUSDc"
        assert mapping.binance_symbol is None
        assert mapping.asset_type == AssetType.FOREX
        assert mapping.base_currency == "EUR"
        assert mapping.quote_currency == "USD"
        assert mapping.is_active is True  # Default
        assert mapping.description == ""  # Default

class TestNormalizationResult:
    """Test normalization result data structure"""
    
    def test_normalization_result_creation(self):
        """Test normalization result creation"""
        result = NormalizationResult(
            broker_symbol="BTCUSDc",
            binance_symbol="BTCUSDT",
            asset_type=AssetType.CRYPTO,
            is_supported=True,
            mapping_found=True,
            error_message=None
        )
        
        assert result.broker_symbol == "BTCUSDc"
        assert result.binance_symbol == "BTCUSDT"
        assert result.asset_type == AssetType.CRYPTO
        assert result.is_supported is True
        assert result.mapping_found is True
        assert result.error_message is None
    
    def test_normalization_result_with_error(self):
        """Test normalization result with error"""
        result = NormalizationResult(
            broker_symbol="UNKNOWNc",
            binance_symbol=None,
            asset_type=AssetType.FOREX,
            is_supported=False,
            mapping_found=False,
            error_message="Unknown broker symbol: UNKNOWNc"
        )
        
        assert result.broker_symbol == "UNKNOWNc"
        assert result.binance_symbol is None
        assert result.asset_type == AssetType.FOREX
        assert result.is_supported is False
        assert result.mapping_found is False
        assert result.error_message == "Unknown broker symbol: UNKNOWNc"

class TestBinanceSymbolNormalizer:
    """Test Binance symbol normalizer functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.normalizer = BinanceSymbolNormalizer()
    
    def test_normalizer_initialization(self):
        """Test normalizer initialization"""
        assert isinstance(self.normalizer.symbol_mappings, dict)
        assert isinstance(self.normalizer.reverse_mappings, dict)
        assert len(self.normalizer.symbol_mappings) > 0
        assert len(self.normalizer.reverse_mappings) > 0
    
    def test_crypto_symbol_normalization(self):
        """Test crypto symbol normalization"""
        crypto_symbols = ["BTCUSDc", "ETHUSDc", "ADAUSDc", "DOTUSDc"]
        
        for symbol in crypto_symbols:
            result = self.normalizer.normalize_broker_to_binance(symbol)
            assert result.broker_symbol == symbol
            assert result.asset_type == AssetType.CRYPTO
            assert result.is_supported is True
            assert result.mapping_found is True
            assert result.binance_symbol is not None
            assert result.error_message is None
    
    def test_forex_symbol_normalization(self):
        """Test forex symbol normalization"""
        forex_symbols = ["EURUSDc", "GBPUSDc", "USDJPYc", "AUDUSDc"]
        
        for symbol in forex_symbols:
            result = self.normalizer.normalize_broker_to_binance(symbol)
            assert result.broker_symbol == symbol
            assert result.asset_type == AssetType.FOREX
            assert result.is_supported is False  # No Binance support for forex
            assert result.mapping_found is True
            assert result.binance_symbol is None
            assert result.error_message is None
    
    def test_metals_symbol_normalization(self):
        """Test metals symbol normalization"""
        metals_symbols = ["XAUUSDc", "XAGUSDc"]
        
        for symbol in metals_symbols:
            result = self.normalizer.normalize_broker_to_binance(symbol)
            assert result.broker_symbol == symbol
            assert result.asset_type == AssetType.METALS
            assert result.is_supported is True
            assert result.mapping_found is True
            assert result.binance_symbol is not None
            assert result.error_message is None
    
    def test_unknown_symbol_normalization(self):
        """Test unknown symbol normalization"""
        unknown_symbols = ["UNKNOWNc", "INVALIDc", "TESTc"]
        
        for symbol in unknown_symbols:
            result = self.normalizer.normalize_broker_to_binance(symbol)
            assert result.broker_symbol == symbol
            assert result.asset_type == AssetType.FOREX  # Default fallback
            assert result.is_supported is False
            assert result.mapping_found is False
            assert result.binance_symbol is None
            assert result.error_message is not None
            assert "Unknown broker symbol" in result.error_message
    
    def test_binance_to_broker_normalization(self):
        """Test Binance to broker symbol normalization"""
        binance_symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "XAUUSDT"]
        
        for symbol in binance_symbols:
            result = self.normalizer.normalize_binance_to_broker(symbol)
            assert result.binance_symbol == symbol
            assert result.is_supported is True
            assert result.mapping_found is True
            assert result.broker_symbol is not None
            assert result.broker_symbol.endswith('c')
            assert result.error_message is None
    
    def test_unknown_binance_symbol_normalization(self):
        """Test unknown Binance symbol normalization"""
        unknown_symbols = ["UNKNOWNUSDT", "INVALIDUSDT", "TESTUSDT"]
        
        for symbol in unknown_symbols:
            result = self.normalizer.normalize_binance_to_broker(symbol)
            assert result.binance_symbol == symbol
            assert result.asset_type == AssetType.CRYPTO  # Default for Binance
            assert result.is_supported is False
            assert result.mapping_found is False
            assert result.broker_symbol == ""
            assert result.error_message is not None
            assert "Unknown Binance symbol" in result.error_message
    
    def test_get_supported_crypto_symbols(self):
        """Test getting supported crypto symbols"""
        crypto_symbols = self.normalizer.get_supported_crypto_symbols()
        
        assert isinstance(crypto_symbols, list)
        assert len(crypto_symbols) > 0
        
        # Check that all returned symbols are crypto
        for symbol in crypto_symbols:
            assert symbol.endswith('c')
            assert self.normalizer.is_crypto_symbol(symbol)
    
    def test_get_supported_forex_symbols(self):
        """Test getting supported forex symbols"""
        forex_symbols = self.normalizer.get_supported_forex_symbols()
        
        assert isinstance(forex_symbols, list)
        assert len(forex_symbols) > 0
        
        # Check that all returned symbols are forex
        for symbol in forex_symbols:
            assert symbol.endswith('c')
            assert self.normalizer.is_forex_symbol(symbol)
    
    def test_get_supported_metals_symbols(self):
        """Test getting supported metals symbols"""
        metals_symbols = self.normalizer.get_supported_metals_symbols()
        
        assert isinstance(metals_symbols, list)
        assert len(metals_symbols) > 0
        
        # Check that all returned symbols are metals
        for symbol in metals_symbols:
            assert symbol.endswith('c')
            assert self.normalizer.is_metals_symbol(symbol)
    
    def test_get_all_supported_symbols(self):
        """Test getting all supported symbols"""
        all_symbols = self.normalizer.get_all_supported_symbols()
        
        assert isinstance(all_symbols, list)
        assert len(all_symbols) > 0
        
        # Check that all returned symbols are active
        for symbol in all_symbols:
            mapping = self.normalizer.get_symbol_info(symbol)
            assert mapping is not None
            assert mapping.is_active is True
    
    def test_get_symbol_info(self):
        """Test getting symbol information"""
        # Test known symbol
        info = self.normalizer.get_symbol_info("BTCUSDc")
        assert info is not None
        assert info.broker_symbol == "BTCUSDc"
        assert info.binance_symbol == "BTCUSDT"
        assert info.asset_type == AssetType.CRYPTO
        
        # Test unknown symbol
        info = self.normalizer.get_symbol_info("UNKNOWNc")
        assert info is None
    
    def test_is_crypto_symbol(self):
        """Test crypto symbol detection"""
        crypto_symbols = ["BTCUSDc", "ETHUSDc", "ADAUSDc"]
        non_crypto_symbols = ["EURUSDc", "GBPUSDc", "XAUUSDc"]
        
        for symbol in crypto_symbols:
            assert self.normalizer.is_crypto_symbol(symbol)
        
        for symbol in non_crypto_symbols:
            assert not self.normalizer.is_crypto_symbol(symbol)
    
    def test_is_forex_symbol(self):
        """Test forex symbol detection"""
        forex_symbols = ["EURUSDc", "GBPUSDc", "USDJPYc"]
        non_forex_symbols = ["BTCUSDc", "ETHUSDc", "XAUUSDc"]
        
        for symbol in forex_symbols:
            assert self.normalizer.is_forex_symbol(symbol)
        
        for symbol in non_forex_symbols:
            assert not self.normalizer.is_forex_symbol(symbol)
    
    def test_is_metals_symbol(self):
        """Test metals symbol detection"""
        metals_symbols = ["XAUUSDc", "XAGUSDc"]
        non_metals_symbols = ["BTCUSDc", "EURUSDc", "GBPUSDc"]
        
        for symbol in metals_symbols:
            assert self.normalizer.is_metals_symbol(symbol)
        
        for symbol in non_metals_symbols:
            assert not self.normalizer.is_metals_symbol(symbol)
    
    def test_get_binance_symbol(self):
        """Test getting Binance symbol"""
        # Test crypto symbol with Binance support
        binance_symbol = self.normalizer.get_binance_symbol("BTCUSDc")
        assert binance_symbol == "BTCUSDT"
        
        # Test forex symbol without Binance support
        binance_symbol = self.normalizer.get_binance_symbol("EURUSDc")
        assert binance_symbol is None
        
        # Test unknown symbol
        binance_symbol = self.normalizer.get_binance_symbol("UNKNOWNc")
        assert binance_symbol is None
    
    def test_get_broker_symbol(self):
        """Test getting broker symbol"""
        # Test Binance symbol with broker mapping
        broker_symbol = self.normalizer.get_broker_symbol("BTCUSDT")
        assert broker_symbol == "BTCUSDc"
        
        # Test unknown Binance symbol
        broker_symbol = self.normalizer.get_broker_symbol("UNKNOWNUSDT")
        assert broker_symbol is None
    
    def test_get_mapping_statistics(self):
        """Test mapping statistics"""
        stats = self.normalizer.get_mapping_statistics()
        
        assert isinstance(stats, dict)
        assert 'total_mappings' in stats
        assert 'active_mappings' in stats
        assert 'crypto_mappings' in stats
        assert 'forex_mappings' in stats
        assert 'metals_mappings' in stats
        assert 'binance_supported' in stats
        assert 'binance_coverage' in stats
        
        assert stats['total_mappings'] > 0
        assert stats['active_mappings'] > 0
        assert stats['crypto_mappings'] > 0
        assert stats['forex_mappings'] > 0
        assert stats['metals_mappings'] > 0
        assert stats['binance_supported'] > 0
        assert 0.0 <= stats['binance_coverage'] <= 1.0
    
    def test_config_file_loading(self):
        """Test configuration file loading"""
        # Create temporary config file
        config_data = {
            'mappings': [
                {
                    'broker_symbol': 'CUSTOMc',
                    'binance_symbol': 'CUSTOMUSDT',
                    'asset_type': 'crypto',
                    'base_currency': 'CUSTOM',
                    'quote_currency': 'USDT',
                    'is_active': True,
                    'description': 'Custom test symbol'
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name
        
        try:
            # Create normalizer with config file
            normalizer = BinanceSymbolNormalizer(config_file)
            
            # Test that custom symbol is loaded
            result = normalizer.normalize_broker_to_binance('CUSTOMc')
            assert result.broker_symbol == 'CUSTOMc'
            assert result.binance_symbol == 'CUSTOMUSDT'
            assert result.asset_type == AssetType.CRYPTO
            assert result.is_supported is True
            
        finally:
            # Clean up
            Path(config_file).unlink(missing_ok=True)
    
    def test_save_config(self):
        """Test saving configuration"""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            config_file = f.name
        
        try:
            # Save configuration
            success = self.normalizer.save_config(config_file)
            assert success is True
            
            # Verify file was created
            assert Path(config_file).exists()
            
            # Load and verify content
            with open(config_file, 'r') as f:
                saved_data = json.load(f)
            
            assert 'mappings' in saved_data
            assert len(saved_data['mappings']) > 0
            
        finally:
            # Clean up
            Path(config_file).unlink(missing_ok=True)

class TestGlobalFunctions:
    """Test global normalization functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global normalizer
        import infra.binance_symbol_normalization
        infra.binance_symbol_normalization._normalizer = None
    
    def test_get_normalizer(self):
        """Test global normalizer access"""
        normalizer1 = get_normalizer()
        normalizer2 = get_normalizer()
        
        # Should return same instance
        assert normalizer1 is normalizer2
        assert isinstance(normalizer1, BinanceSymbolNormalizer)
    
    def test_normalize_broker_to_binance_global(self):
        """Test global broker to Binance normalization"""
        result = normalize_broker_to_binance("BTCUSDc")
        
        assert result.broker_symbol == "BTCUSDc"
        assert result.binance_symbol == "BTCUSDT"
        assert result.asset_type == AssetType.CRYPTO
        assert result.is_supported is True
        assert result.mapping_found is True
    
    def test_normalize_binance_to_broker_global(self):
        """Test global Binance to broker normalization"""
        result = normalize_binance_to_broker("BTCUSDT")
        
        assert result.binance_symbol == "BTCUSDT"
        assert result.broker_symbol == "BTCUSDc"
        assert result.asset_type == AssetType.CRYPTO
        assert result.is_supported is True
        assert result.mapping_found is True
    
    def test_get_binance_symbol_global(self):
        """Test global Binance symbol retrieval"""
        binance_symbol = get_binance_symbol("BTCUSDc")
        assert binance_symbol == "BTCUSDT"
        
        binance_symbol = get_binance_symbol("EURUSDc")
        assert binance_symbol is None
    
    def test_get_broker_symbol_global(self):
        """Test global broker symbol retrieval"""
        broker_symbol = get_broker_symbol("BTCUSDT")
        assert broker_symbol == "BTCUSDc"
        
        broker_symbol = get_broker_symbol("UNKNOWNUSDT")
        assert broker_symbol is None
    
    def test_is_crypto_symbol_global(self):
        """Test global crypto symbol detection"""
        assert is_crypto_symbol("BTCUSDc") is True
        assert is_crypto_symbol("ETHUSDc") is True
        assert is_crypto_symbol("EURUSDc") is False
        assert is_crypto_symbol("XAUUSDc") is False
    
    def test_is_forex_symbol_global(self):
        """Test global forex symbol detection"""
        assert is_forex_symbol("EURUSDc") is True
        assert is_forex_symbol("GBPUSDc") is True
        assert is_forex_symbol("BTCUSDc") is False
        assert is_forex_symbol("XAUUSDc") is False
    
    def test_is_metals_symbol_global(self):
        """Test global metals symbol detection"""
        assert is_metals_symbol("XAUUSDc") is True
        assert is_metals_symbol("XAGUSDc") is True
        assert is_metals_symbol("BTCUSDc") is False
        assert is_metals_symbol("EURUSDc") is False
    
    def test_get_supported_crypto_symbols_global(self):
        """Test global supported crypto symbols"""
        crypto_symbols = get_supported_crypto_symbols()
        
        assert isinstance(crypto_symbols, list)
        assert len(crypto_symbols) > 0
        assert "BTCUSDc" in crypto_symbols
        assert "ETHUSDc" in crypto_symbols
    
    def test_get_supported_forex_symbols_global(self):
        """Test global supported forex symbols"""
        forex_symbols = get_supported_forex_symbols()
        
        assert isinstance(forex_symbols, list)
        assert len(forex_symbols) > 0
        assert "EURUSDc" in forex_symbols
        assert "GBPUSDc" in forex_symbols
    
    def test_get_mapping_statistics_global(self):
        """Test global mapping statistics"""
        stats = get_mapping_statistics()
        
        assert isinstance(stats, dict)
        assert 'total_mappings' in stats
        assert 'active_mappings' in stats
        assert 'crypto_mappings' in stats
        assert 'forex_mappings' in stats
        assert 'metals_mappings' in stats
        assert 'binance_supported' in stats
        assert 'binance_coverage' in stats

class TestNormalizationIntegration:
    """Integration tests for symbol normalization"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global normalizer
        import infra.binance_symbol_normalization
        infra.binance_symbol_normalization._normalizer = None
    
    def test_comprehensive_symbol_mapping(self):
        """Test comprehensive symbol mapping across all asset types"""
        # Test crypto symbols
        crypto_symbols = ["BTCUSDc", "ETHUSDc", "ADAUSDc", "DOTUSDc"]
        for symbol in crypto_symbols:
            result = normalize_broker_to_binance(symbol)
            assert result.is_supported is True
            assert result.binance_symbol is not None
            assert result.asset_type == AssetType.CRYPTO
        
        # Test forex symbols
        forex_symbols = ["EURUSDc", "GBPUSDc", "USDJPYc", "AUDUSDc"]
        for symbol in forex_symbols:
            result = normalize_broker_to_binance(symbol)
            assert result.is_supported is False  # No Binance support
            assert result.binance_symbol is None
            assert result.asset_type == AssetType.FOREX
        
        # Test metals symbols
        metals_symbols = ["XAUUSDc", "XAGUSDc"]
        for symbol in metals_symbols:
            result = normalize_broker_to_binance(symbol)
            assert result.is_supported is True
            assert result.binance_symbol is not None
            assert result.asset_type == AssetType.METALS
    
    def test_bidirectional_mapping(self):
        """Test bidirectional symbol mapping"""
        # Test broker -> Binance -> broker
        broker_symbols = ["BTCUSDc", "ETHUSDc", "XAUUSDc"]
        
        for broker_symbol in broker_symbols:
            # Broker to Binance
            result1 = normalize_broker_to_binance(broker_symbol)
            if result1.is_supported and result1.binance_symbol:
                # Binance to broker
                result2 = normalize_binance_to_broker(result1.binance_symbol)
                assert result2.broker_symbol == broker_symbol
                assert result2.is_supported is True
    
    def test_asset_type_detection(self):
        """Test asset type detection for all symbols"""
        # Get all supported symbols
        normalizer = get_normalizer()
        all_symbols = normalizer.get_all_supported_symbols()
        
        crypto_count = 0
        forex_count = 0
        metals_count = 0
        
        for symbol in all_symbols:
            if is_crypto_symbol(symbol):
                crypto_count += 1
            elif is_forex_symbol(symbol):
                forex_count += 1
            elif is_metals_symbol(symbol):
                metals_count += 1
        
        assert crypto_count > 0
        assert forex_count > 0
        assert metals_count > 0
        
        # Verify counts match statistics
        stats = get_mapping_statistics()
        assert crypto_count == stats['crypto_mappings']
        assert forex_count == stats['forex_mappings']
        assert metals_count == stats['metals_mappings']
    
    def test_error_handling(self):
        """Test error handling for invalid symbols"""
        invalid_symbols = ["", "INVALID", "BTCUSD", "BTCUSDT", "UNKNOWNc"]
        
        for symbol in invalid_symbols:
            result = normalize_broker_to_binance(symbol)
            assert result.is_supported is False
            assert result.mapping_found is False
            assert result.error_message is not None
    
    def test_case_sensitivity(self):
        """Test case sensitivity handling"""
        # Test that symbols are case-sensitive
        result1 = normalize_broker_to_binance("BTCUSDc")
        result2 = normalize_broker_to_binance("btcusdc")
        
        assert result1.is_supported is True
        assert result2.is_supported is False  # Case sensitive
    
    def test_symbol_validation(self):
        """Test symbol validation and edge cases"""
        # Test symbols with different suffixes
        test_symbols = [
            "BTCUSDc",  # Valid
            "BTCUSD",   # Missing 'c'
            "BTCUSDT",  # Binance format
            "BTCUSDcX", # Extra suffix
            "BTCUSDcc", # Double 'c'
        ]
        
        expected_results = [True, False, False, False, False]
        
        for symbol, expected in zip(test_symbols, expected_results):
            result = normalize_broker_to_binance(symbol)
            assert result.is_supported == expected

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
