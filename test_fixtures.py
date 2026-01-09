"""
Test Fixtures for Confluence Calculator Testing
Fix 10: Reusable test fixtures for consistent testing
"""
from unittest.mock import Mock, MagicMock
from typing import Dict, Any, Optional
import threading


class MockIndicatorBridge:
    """Mock indicator bridge for testing"""
    
    def __init__(self, custom_data: Optional[Dict[str, Dict]] = None):
        """
        Initialize mock indicator bridge
        
        Args:
            custom_data: Optional custom multi-timeframe data per symbol
        """
        self.multi_data = custom_data or {}
    
    def get_multi(self, symbol: str) -> Dict[str, Dict]:
        """Return mock multi-timeframe data"""
        if symbol not in self.multi_data:
            # Default data structure
            self.multi_data[symbol] = {
                "M5": {
                    "atr14": 50.0,
                    "atr50": 45.0,
                    "current_close": 10000.0,
                    "ema20": 10050.0,
                    "ema50": 10030.0,
                    "ema200": 10000.0,
                    "rsi": 55,
                    "macd": 10,
                    "macd_signal": 5,
                    "bb_upper": 10100.0,
                    "bb_lower": 9900.0
                },
                "M15": {
                    "atr14": 75.0,
                    "atr50": 70.0,
                    "current_close": 10000.0,
                    "ema20": 10050.0,
                    "ema50": 10030.0,
                    "ema200": 10000.0,
                    "rsi": 55,
                    "macd": 10,
                    "macd_signal": 5,
                    "bb_upper": 10100.0,
                    "bb_lower": 9900.0
                },
                "H1": {
                    "atr14": 100.0,
                    "atr50": 90.0,
                    "current_close": 10000.0,
                    "ema20": 10050.0,
                    "ema50": 10030.0,
                    "ema200": 10000.0,
                    "rsi": 55,
                    "macd": 10,
                    "macd_signal": 5,
                    "bb_upper": 10100.0,
                    "bb_lower": 9900.0
                }
            }
        return self.multi_data[symbol]


class MockM1Analyzer:
    """Mock M1 Microstructure Analyzer for testing"""
    
    def __init__(self):
        self.analysis_result = {
            'available': True,
            'choch_bos': {'confidence': 75},
            'session_context': {'volatility_tier': 'NORMAL'},
            'momentum': {'quality': 'STRONG'},
            'liquidity': {'proximity_score': 80},
            'strategy_fit': 70
        }
    
    def analyze_microstructure(self, symbol: str, candles: list, current_price: float) -> Dict[str, Any]:
        """Return mock microstructure analysis"""
        return self.analysis_result
    
    def calculate_microstructure_confluence(
        self, 
        analysis: Dict, 
        symbol: str = None, 
        session: str = None,
        volatility_regime: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return mock confluence result"""
        return {
            'score': 75,
            'grade': 'B',
            'components': {
                'm1_signal_confidence': 75,
                'session_volatility_suitability': 80,
                'momentum_quality': 85,
                'liquidity_proximity': 80,
                'strategy_fit': 70
            }
        }


class MockM1DataFetcher:
    """Mock M1 Data Fetcher for testing"""
    
    def __init__(self, candle_count: int = 200):
        self.candle_count = candle_count
    
    def fetch_m1_data(self, symbol: str, count: int = 200) -> list:
        """Return mock M1 candles"""
        candles = []
        base_price = 10000.0
        for i in range(count):
            candles.append({
                'time': i,
                'open': base_price + i * 0.1,
                'high': base_price + i * 0.1 + 5,
                'low': base_price + i * 0.1 - 5,
                'close': base_price + i * 0.1 + 2,
                'volume': 1000
            })
        return candles


def create_btc_data(atr_percent: float = 2.5) -> Dict[str, Dict]:
    """
    Create BTC-specific test data
    
    Args:
        atr_percent: ATR as percentage of price (e.g., 2.5 for 2.5%)
    
    Returns:
        Multi-timeframe data dict for BTC
    """
    base_price = 100000.0  # BTC price
    atr_value = base_price * (atr_percent / 100.0)
    
    return {
        "M5": {
            "atr14": atr_value * 0.5,
            "atr50": atr_value * 0.45,
            "current_close": base_price,
            "ema20": base_price * 1.005,
            "ema50": base_price * 1.003,
            "ema200": base_price,
            "rsi": 55,
            "macd": 10,
            "macd_signal": 5,
            "bb_upper": base_price * 1.01,
            "bb_lower": base_price * 0.99
        },
        "M15": {
            "atr14": atr_value * 0.75,
            "atr50": atr_value * 0.70,
            "current_close": base_price,
            "ema20": base_price * 1.005,
            "ema50": base_price * 1.003,
            "ema200": base_price,
            "rsi": 55,
            "macd": 10,
            "macd_signal": 5,
            "bb_upper": base_price * 1.01,
            "bb_lower": base_price * 0.99
        },
        "H1": {
            "atr14": atr_value,
            "atr50": atr_value * 0.9,
            "current_close": base_price,
            "ema20": base_price * 1.005,
            "ema50": base_price * 1.003,
            "ema200": base_price,
            "rsi": 55,
            "macd": 10,
            "macd_signal": 5,
            "bb_upper": base_price * 1.01,
            "bb_lower": base_price * 0.99
        }
    }


def create_xau_data(atr_percent: float = 0.8) -> Dict[str, Dict]:
    """
    Create XAU-specific test data
    
    Args:
        atr_percent: ATR as percentage of price (e.g., 0.8 for 0.8%)
    
    Returns:
        Multi-timeframe data dict for XAU
    """
    base_price = 2000.0  # XAU price
    atr_value = base_price * (atr_percent / 100.0)
    
    return {
        "M5": {
            "atr14": atr_value * 0.5,
            "atr50": atr_value * 0.45,
            "current_close": base_price,
            "ema20": base_price * 1.0005,
            "ema50": base_price * 1.0003,
            "ema200": base_price,
            "rsi": 55,
            "macd": 10,
            "macd_signal": 5,
            "bb_upper": base_price * 1.001,
            "bb_lower": base_price * 0.999
        },
        "M15": {
            "atr14": atr_value * 0.75,
            "atr50": atr_value * 0.70,
            "current_close": base_price,
            "ema20": base_price * 1.0005,
            "ema50": base_price * 1.0003,
            "ema200": base_price,
            "rsi": 55,
            "macd": 10,
            "macd_signal": 5,
            "bb_upper": base_price * 1.001,
            "bb_lower": base_price * 0.999
        },
        "H1": {
            "atr14": atr_value,
            "atr50": atr_value * 0.9,
            "current_close": base_price,
            "ema20": base_price * 1.0005,
            "ema50": base_price * 1.0003,
            "ema200": base_price,
            "rsi": 55,
            "macd": 10,
            "macd_signal": 5,
            "bb_upper": base_price * 1.001,
            "bb_lower": base_price * 0.999
        }
    }


def reset_singleton(cls):
    """
    Reset singleton instance for testing
    
    Args:
        cls: Class with singleton pattern
    """
    cls._instance = None
    cls._lock = threading.RLock()


def create_invalid_data() -> Dict[str, Dict]:
    """Create invalid test data (missing required fields)"""
    return {
        "M5": {
            "atr14": None,  # Invalid
            "current_close": 0,  # Invalid
        },
        "M15": {},  # Empty
        "H1": {
            "atr14": -10,  # Negative
            "current_close": None  # None
        }
    }


def create_regime_test_data(regime: str = 'STABLE') -> Dict[str, Dict]:
    """
    Create test data for regime testing
    
    Args:
        regime: Regime type ('STABLE', 'TRANSITIONAL', 'VOLATILE')
    
    Returns:
        Multi-timeframe data with ATR ratios matching regime
    """
    base_price = 10000.0
    
    # ATR ratios for different regimes
    # STABLE: ratio <= 1.2
    # TRANSITIONAL: ratio 1.2-1.4
    # VOLATILE: ratio >= 1.4
    if regime == 'STABLE':
        atr14 = 100.0
        atr50 = 90.0  # ratio = 1.11
    elif regime == 'TRANSITIONAL':
        atr14 = 130.0
        atr50 = 100.0  # ratio = 1.3
    else:  # VOLATILE
        atr14 = 150.0
        atr50 = 100.0  # ratio = 1.5
    
    return {
        "M5": {
            "atr14": atr14 * 0.5,
            "atr50": atr50 * 0.45,
            "current_close": base_price,
            "ema20": base_price * 1.005,
            "ema50": base_price * 1.003,
            "ema200": base_price,
            "rsi": 55,
            "macd": 10,
            "macd_signal": 5,
            "bb_upper": base_price * 1.01,
            "bb_lower": base_price * 0.99
        },
        "M15": {
            "atr14": atr14 * 0.75,
            "atr50": atr50 * 0.70,
            "current_close": base_price,
            "ema20": base_price * 1.005,
            "ema50": base_price * 1.003,
            "ema200": base_price,
            "rsi": 55,
            "macd": 10,
            "macd_signal": 5,
            "bb_upper": base_price * 1.01,
            "bb_lower": base_price * 0.99
        },
        "H1": {
            "atr14": atr14,
            "atr50": atr50,
            "current_close": base_price,
            "ema20": base_price * 1.005,
            "ema50": base_price * 1.003,
            "ema200": base_price,
            "rsi": 55,
            "macd": 10,
            "macd_signal": 5,
            "bb_upper": base_price * 1.01,
            "bb_lower": base_price * 0.99
        }
    }

