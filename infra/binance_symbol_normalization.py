"""
Binance Symbol Normalization System

This module handles the mapping between broker symbols (with 'c' suffix)
and Binance symbols for proper data integration and order book analysis.

Key Features:
- Symbol mapping between broker and Binance formats
- Automatic symbol detection and conversion
- Support for major trading pairs (BTC, ETH, XAU, etc.)
- Fallback handling for unknown symbols
- Configuration-based mapping system
"""

import logging
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class AssetType(Enum):
    """Asset types for symbol classification"""
    CRYPTO = "crypto"
    FOREX = "forex"
    METALS = "metals"
    INDICES = "indices"
    COMMODITIES = "commodities"

@dataclass
class SymbolMapping:
    """Symbol mapping configuration"""
    broker_symbol: str
    binance_symbol: str
    asset_type: AssetType
    base_currency: str
    quote_currency: str
    is_active: bool = True
    description: str = ""

@dataclass
class NormalizationResult:
    """Result of symbol normalization"""
    broker_symbol: str
    binance_symbol: Optional[str]
    asset_type: AssetType
    is_supported: bool
    mapping_found: bool
    error_message: Optional[str] = None

class BinanceSymbolNormalizer:
    """Main symbol normalization system"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.symbol_mappings: Dict[str, SymbolMapping] = {}
        self.reverse_mappings: Dict[str, str] = {}  # binance -> broker
        self.config_file = config_file or "config/binance_symbol_mappings.json"
        self._load_default_mappings()
        self._load_config_mappings()
    
    def _load_default_mappings(self) -> None:
        """Load default symbol mappings for major trading pairs"""
        default_mappings = [
            # Crypto pairs
            SymbolMapping(
                broker_symbol="BTCUSDc",
                binance_symbol="BTCUSDT",
                asset_type=AssetType.CRYPTO,
                base_currency="BTC",
                quote_currency="USDT",
                description="Bitcoin vs USDT"
            ),
            SymbolMapping(
                broker_symbol="ETHUSDc",
                binance_symbol="ETHUSDT",
                asset_type=AssetType.CRYPTO,
                base_currency="ETH",
                quote_currency="USDT",
                description="Ethereum vs USDT"
            ),
            SymbolMapping(
                broker_symbol="ADAUSDc",
                binance_symbol="ADAUSDT",
                asset_type=AssetType.CRYPTO,
                base_currency="ADA",
                quote_currency="USDT",
                description="Cardano vs USDT"
            ),
            SymbolMapping(
                broker_symbol="DOTUSDc",
                binance_symbol="DOTUSDT",
                asset_type=AssetType.CRYPTO,
                base_currency="DOT",
                quote_currency="USDT",
                description="Polkadot vs USDT"
            ),
            SymbolMapping(
                broker_symbol="LINKUSDc",
                binance_symbol="LINKUSDT",
                asset_type=AssetType.CRYPTO,
                base_currency="LINK",
                quote_currency="USDT",
                description="Chainlink vs USDT"
            ),
            SymbolMapping(
                broker_symbol="SOLUSDc",
                binance_symbol="SOLUSDT",
                asset_type=AssetType.CRYPTO,
                base_currency="SOL",
                quote_currency="USDT",
                description="Solana vs USDT"
            ),
            SymbolMapping(
                broker_symbol="MATICUSDc",
                binance_symbol="MATICUSDT",
                asset_type=AssetType.CRYPTO,
                base_currency="MATIC",
                quote_currency="USDT",
                description="Polygon vs USDT"
            ),
            SymbolMapping(
                broker_symbol="AVAXUSDc",
                binance_symbol="AVAXUSDT",
                asset_type=AssetType.CRYPTO,
                base_currency="AVAX",
                quote_currency="USDT",
                description="Avalanche vs USDT"
            ),
            
            # Forex pairs (no Binance equivalent)
            SymbolMapping(
                broker_symbol="EURUSDc",
                binance_symbol=None,
                asset_type=AssetType.FOREX,
                base_currency="EUR",
                quote_currency="USD",
                description="Euro vs US Dollar"
            ),
            SymbolMapping(
                broker_symbol="GBPUSDc",
                binance_symbol=None,
                asset_type=AssetType.FOREX,
                base_currency="GBP",
                quote_currency="USD",
                description="British Pound vs US Dollar"
            ),
            SymbolMapping(
                broker_symbol="USDJPYc",
                binance_symbol=None,
                asset_type=AssetType.FOREX,
                base_currency="USD",
                quote_currency="JPY",
                description="US Dollar vs Japanese Yen"
            ),
            SymbolMapping(
                broker_symbol="AUDUSDc",
                binance_symbol=None,
                asset_type=AssetType.FOREX,
                base_currency="AUD",
                quote_currency="USD",
                description="Australian Dollar vs US Dollar"
            ),
            SymbolMapping(
                broker_symbol="USDCADc",
                binance_symbol=None,
                asset_type=AssetType.FOREX,
                base_currency="USD",
                quote_currency="CAD",
                description="US Dollar vs Canadian Dollar"
            ),
            SymbolMapping(
                broker_symbol="NZDUSDc",
                binance_symbol=None,
                asset_type=AssetType.FOREX,
                base_currency="NZD",
                quote_currency="USD",
                description="New Zealand Dollar vs US Dollar"
            ),
            SymbolMapping(
                broker_symbol="USDCHFc",
                binance_symbol=None,
                asset_type=AssetType.FOREX,
                base_currency="USD",
                quote_currency="CHF",
                description="US Dollar vs Swiss Franc"
            ),
            SymbolMapping(
                broker_symbol="EURJPYc",
                binance_symbol=None,
                asset_type=AssetType.FOREX,
                base_currency="EUR",
                quote_currency="JPY",
                description="Euro vs Japanese Yen"
            ),
            SymbolMapping(
                broker_symbol="GBPJPYc",
                binance_symbol=None,
                asset_type=AssetType.FOREX,
                base_currency="GBP",
                quote_currency="JPY",
                description="British Pound vs Japanese Yen"
            ),
            SymbolMapping(
                broker_symbol="EURGBPc",
                binance_symbol=None,
                asset_type=AssetType.FOREX,
                base_currency="EUR",
                quote_currency="GBP",
                description="Euro vs British Pound"
            ),
            
            # Metals
            SymbolMapping(
                broker_symbol="XAUUSDc",
                binance_symbol="XAUUSDT",
                asset_type=AssetType.METALS,
                base_currency="XAU",
                quote_currency="USDT",
                description="Gold vs USDT"
            ),
            SymbolMapping(
                broker_symbol="XAGUSDc",
                binance_symbol="XAGUSDT",
                asset_type=AssetType.METALS,
                base_currency="XAG",
                quote_currency="USDT",
                description="Silver vs USDT"
            ),
            
            # Indices (no Binance equivalent)
            SymbolMapping(
                broker_symbol="SPX500c",
                binance_symbol=None,
                asset_type=AssetType.INDICES,
                base_currency="SPX",
                quote_currency="USD",
                description="S&P 500 Index"
            ),
            SymbolMapping(
                broker_symbol="NAS100c",
                binance_symbol=None,
                asset_type=AssetType.INDICES,
                base_currency="NAS",
                quote_currency="USD",
                description="NASDAQ 100 Index"
            ),
            SymbolMapping(
                broker_symbol="UK100c",
                binance_symbol=None,
                asset_type=AssetType.INDICES,
                base_currency="UK100",
                quote_currency="USD",
                description="FTSE 100 Index"
            ),
            SymbolMapping(
                broker_symbol="GER30c",
                binance_symbol=None,
                asset_type=AssetType.INDICES,
                base_currency="GER30",
                quote_currency="USD",
                description="DAX 30 Index"
            ),
        ]
        
        for mapping in default_mappings:
            self._add_mapping(mapping)
    
    def _load_config_mappings(self) -> None:
        """Load additional mappings from configuration file"""
        if not Path(self.config_file).exists():
            logger.info(f"Configuration file {self.config_file} not found, using defaults only")
            return
        
        try:
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
            
            for mapping_data in config_data.get('mappings', []):
                mapping = SymbolMapping(
                    broker_symbol=mapping_data['broker_symbol'],
                    binance_symbol=mapping_data.get('binance_symbol'),
                    asset_type=AssetType(mapping_data['asset_type']),
                    base_currency=mapping_data['base_currency'],
                    quote_currency=mapping_data['quote_currency'],
                    is_active=mapping_data.get('is_active', True),
                    description=mapping_data.get('description', '')
                )
                self._add_mapping(mapping)
            
            logger.info(f"Loaded {len(config_data.get('mappings', []))} mappings from {self.config_file}")
            
        except Exception as e:
            logger.error(f"Error loading configuration file {self.config_file}: {e}")
    
    def _add_mapping(self, mapping: SymbolMapping) -> None:
        """Add a symbol mapping to the system"""
        self.symbol_mappings[mapping.broker_symbol] = mapping
        
        if mapping.binance_symbol:
            self.reverse_mappings[mapping.binance_symbol] = mapping.broker_symbol
    
    def normalize_broker_to_binance(self, broker_symbol: str) -> NormalizationResult:
        """Normalize broker symbol to Binance symbol"""
        if broker_symbol not in self.symbol_mappings:
            return NormalizationResult(
                broker_symbol=broker_symbol,
                binance_symbol=None,
                asset_type=AssetType.FOREX,  # Default fallback
                is_supported=False,
                mapping_found=False,
                error_message=f"Unknown broker symbol: {broker_symbol}"
            )
        
        mapping = self.symbol_mappings[broker_symbol]
        
        if not mapping.is_active:
            return NormalizationResult(
                broker_symbol=broker_symbol,
                binance_symbol=None,
                asset_type=mapping.asset_type,
                is_supported=False,
                mapping_found=True,
                error_message=f"Symbol {broker_symbol} is inactive"
            )
        
        return NormalizationResult(
            broker_symbol=broker_symbol,
            binance_symbol=mapping.binance_symbol,
            asset_type=mapping.asset_type,
            is_supported=mapping.binance_symbol is not None,
            mapping_found=True
        )
    
    def normalize_binance_to_broker(self, binance_symbol: str) -> NormalizationResult:
        """Normalize Binance symbol to broker symbol"""
        if binance_symbol not in self.reverse_mappings:
            return NormalizationResult(
                broker_symbol="",
                binance_symbol=binance_symbol,
                asset_type=AssetType.CRYPTO,  # Default for Binance
                is_supported=False,
                mapping_found=False,
                error_message=f"Unknown Binance symbol: {binance_symbol}"
            )
        
        broker_symbol = self.reverse_mappings[binance_symbol]
        mapping = self.symbol_mappings[broker_symbol]
        
        return NormalizationResult(
            broker_symbol=broker_symbol,
            binance_symbol=binance_symbol,
            asset_type=mapping.asset_type,
            is_supported=True,
            mapping_found=True
        )
    
    def get_supported_crypto_symbols(self) -> List[str]:
        """Get list of supported crypto symbols with Binance mapping"""
        crypto_symbols = []
        for mapping in self.symbol_mappings.values():
            if (mapping.asset_type == AssetType.CRYPTO and 
                mapping.binance_symbol and 
                mapping.is_active):
                crypto_symbols.append(mapping.broker_symbol)
        return crypto_symbols
    
    def get_supported_forex_symbols(self) -> List[str]:
        """Get list of supported forex symbols"""
        forex_symbols = []
        for mapping in self.symbol_mappings.values():
            if (mapping.asset_type == AssetType.FOREX and 
                mapping.is_active):
                forex_symbols.append(mapping.broker_symbol)
        return forex_symbols
    
    def get_supported_metals_symbols(self) -> List[str]:
        """Get list of supported metals symbols with Binance mapping"""
        metals_symbols = []
        for mapping in self.symbol_mappings.values():
            if (mapping.asset_type == AssetType.METALS and 
                mapping.binance_symbol and 
                mapping.is_active):
                metals_symbols.append(mapping.broker_symbol)
        return metals_symbols
    
    def get_all_supported_symbols(self) -> List[str]:
        """Get list of all supported symbols"""
        return [symbol for symbol, mapping in self.symbol_mappings.items() 
                if mapping.is_active]
    
    def get_symbol_info(self, broker_symbol: str) -> Optional[SymbolMapping]:
        """Get detailed information about a symbol"""
        return self.symbol_mappings.get(broker_symbol)
    
    def is_crypto_symbol(self, broker_symbol: str) -> bool:
        """Check if a symbol is a crypto symbol with Binance support"""
        mapping = self.symbol_mappings.get(broker_symbol)
        return (mapping is not None and 
                mapping.asset_type == AssetType.CRYPTO and 
                mapping.binance_symbol is not None and 
                mapping.is_active)
    
    def is_forex_symbol(self, broker_symbol: str) -> bool:
        """Check if a symbol is a forex symbol"""
        mapping = self.symbol_mappings.get(broker_symbol)
        return (mapping is not None and 
                mapping.asset_type == AssetType.FOREX and 
                mapping.is_active)
    
    def is_metals_symbol(self, broker_symbol: str) -> bool:
        """Check if a symbol is a metals symbol with Binance support"""
        mapping = self.symbol_mappings.get(broker_symbol)
        return (mapping is not None and 
                mapping.asset_type == AssetType.METALS and 
                mapping.binance_symbol is not None and 
                mapping.is_active)
    
    def get_binance_symbol(self, broker_symbol: str) -> Optional[str]:
        """Get Binance symbol for a broker symbol"""
        mapping = self.symbol_mappings.get(broker_symbol)
        if mapping and mapping.is_active:
            return mapping.binance_symbol
        return None
    
    def get_broker_symbol(self, binance_symbol: str) -> Optional[str]:
        """Get broker symbol for a Binance symbol"""
        return self.reverse_mappings.get(binance_symbol)
    
    def get_mapping_statistics(self) -> Dict[str, Any]:
        """Get statistics about symbol mappings"""
        total_mappings = len(self.symbol_mappings)
        active_mappings = sum(1 for m in self.symbol_mappings.values() if m.is_active)
        crypto_mappings = sum(1 for m in self.symbol_mappings.values() 
                             if m.asset_type == AssetType.CRYPTO and m.is_active)
        forex_mappings = sum(1 for m in self.symbol_mappings.values() 
                             if m.asset_type == AssetType.FOREX and m.is_active)
        metals_mappings = sum(1 for m in self.symbol_mappings.values() 
                             if m.asset_type == AssetType.METALS and m.is_active)
        binance_supported = sum(1 for m in self.symbol_mappings.values() 
                              if m.binance_symbol and m.is_active)
        
        return {
            'total_mappings': total_mappings,
            'active_mappings': active_mappings,
            'crypto_mappings': crypto_mappings,
            'forex_mappings': forex_mappings,
            'metals_mappings': metals_mappings,
            'binance_supported': binance_supported,
            'binance_coverage': binance_supported / max(1, active_mappings)
        }
    
    def save_config(self, config_file: Optional[str] = None) -> bool:
        """Save current mappings to configuration file"""
        try:
            config_data = {
                'mappings': []
            }
            
            for mapping in self.symbol_mappings.values():
                mapping_data = {
                    'broker_symbol': mapping.broker_symbol,
                    'binance_symbol': mapping.binance_symbol,
                    'asset_type': mapping.asset_type.value,
                    'base_currency': mapping.base_currency,
                    'quote_currency': mapping.quote_currency,
                    'is_active': mapping.is_active,
                    'description': mapping.description
                }
                config_data['mappings'].append(mapping_data)
            
            target_file = config_file or self.config_file
            Path(target_file).parent.mkdir(parents=True, exist_ok=True)
            
            with open(target_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Saved {len(config_data['mappings'])} mappings to {target_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving configuration file: {e}")
            return False

# Global normalizer instance
_normalizer: Optional[BinanceSymbolNormalizer] = None

def get_normalizer() -> BinanceSymbolNormalizer:
    """Get global symbol normalizer instance"""
    global _normalizer
    if _normalizer is None:
        _normalizer = BinanceSymbolNormalizer()
    return _normalizer

def normalize_broker_to_binance(broker_symbol: str) -> NormalizationResult:
    """Normalize broker symbol to Binance symbol"""
    normalizer = get_normalizer()
    return normalizer.normalize_broker_to_binance(broker_symbol)

def normalize_binance_to_broker(binance_symbol: str) -> NormalizationResult:
    """Normalize Binance symbol to broker symbol"""
    normalizer = get_normalizer()
    return normalizer.normalize_binance_to_broker(binance_symbol)

def get_binance_symbol(broker_symbol: str) -> Optional[str]:
    """Get Binance symbol for a broker symbol"""
    normalizer = get_normalizer()
    return normalizer.get_binance_symbol(broker_symbol)

def get_broker_symbol(binance_symbol: str) -> Optional[str]:
    """Get broker symbol for a Binance symbol"""
    normalizer = get_normalizer()
    return normalizer.get_broker_symbol(binance_symbol)

def is_crypto_symbol(broker_symbol: str) -> bool:
    """Check if a symbol is a crypto symbol with Binance support"""
    normalizer = get_normalizer()
    return normalizer.is_crypto_symbol(broker_symbol)

def is_forex_symbol(broker_symbol: str) -> bool:
    """Check if a symbol is a forex symbol"""
    normalizer = get_normalizer()
    return normalizer.is_forex_symbol(broker_symbol)

def is_metals_symbol(broker_symbol: str) -> bool:
    """Check if a symbol is a metals symbol with Binance support"""
    normalizer = get_normalizer()
    return normalizer.is_metals_symbol(broker_symbol)

def get_supported_crypto_symbols() -> List[str]:
    """Get list of supported crypto symbols"""
    normalizer = get_normalizer()
    return normalizer.get_supported_crypto_symbols()

def get_supported_forex_symbols() -> List[str]:
    """Get list of supported forex symbols"""
    normalizer = get_normalizer()
    return normalizer.get_supported_forex_symbols()

def get_mapping_statistics() -> Dict[str, Any]:
    """Get statistics about symbol mappings"""
    normalizer = get_normalizer()
    return normalizer.get_mapping_statistics()

if __name__ == "__main__":
    # Example usage
    normalizer = BinanceSymbolNormalizer()
    
    # Test crypto symbols
    crypto_symbols = ["BTCUSDc", "ETHUSDc", "ADAUSDc"]
    for symbol in crypto_symbols:
        result = normalizer.normalize_broker_to_binance(symbol)
        print(f"{symbol} -> {result.binance_symbol} ({result.asset_type.value})")
    
    # Test forex symbols
    forex_symbols = ["EURUSDc", "GBPUSDc", "USDJPYc"]
    for symbol in forex_symbols:
        result = normalizer.normalize_broker_to_binance(symbol)
        print(f"{symbol} -> {result.binance_symbol} ({result.asset_type.value})")
    
    # Test metals symbols
    metals_symbols = ["XAUUSDc", "XAGUSDc"]
    for symbol in metals_symbols:
        result = normalizer.normalize_broker_to_binance(symbol)
        print(f"{symbol} -> {result.binance_symbol} ({result.asset_type.value})")
    
    # Print statistics
    stats = normalizer.get_mapping_statistics()
    print(f"\nMapping Statistics:")
    print(f"Total mappings: {stats['total_mappings']}")
    print(f"Active mappings: {stats['active_mappings']}")
    print(f"Crypto mappings: {stats['crypto_mappings']}")
    print(f"Forex mappings: {stats['forex_mappings']}")
    print(f"Metals mappings: {stats['metals_mappings']}")
    print(f"Binance supported: {stats['binance_supported']}")
    print(f"Binance coverage: {stats['binance_coverage']:.1%}")
