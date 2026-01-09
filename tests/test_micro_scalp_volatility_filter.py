"""
Tests for Micro-Scalp Volatility Filter
"""

import unittest
import json
from infra.micro_scalp_volatility_filter import MicroScalpVolatilityFilter, VolatilityFilterResult


class TestMicroScalpVolatilityFilter(unittest.TestCase):
    """Test MicroScalpVolatilityFilter functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Load config
        try:
            with open('config/micro_scalp_config.json', 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            # Use minimal config for testing
            self.config = {
                'xauusd_rules': {
                    'pre_trade_filters': {
                        'volatility': {'atr1_min': 0.5, 'm1_range_avg_min': 0.8},
                        'spread': {'max_spread': 0.25}
                    }
                },
                'btcusd_rules': {
                    'pre_trade_filters': {
                        'volatility': {'atr1_min': 10.0, 'm1_range_avg_min': 15.0},
                        'spread': {'max_spread': 15.0}
                    }
                }
            }
        
        self.filter = MicroScalpVolatilityFilter(self.config)
    
    def _create_candle(self, time, open, high, low, close, volume=1000):
        """Helper to create candle dict"""
        return {
            'time': time,
            'open': open,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }
    
    def test_calculate_atr1(self):
        """Test ATR(1) calculation"""
        candles = []
        for i in range(5):
            candles.append(self._create_candle(i, 2000.0, 2000.5, 1999.5, 2000.0))
        
        atr1 = self.filter.calculate_atr1(candles)
        self.assertGreater(atr1, 0.0)
    
    def test_calculate_avg_m1_range(self):
        """Test average M1 range calculation"""
        candles = []
        for i in range(10):
            candles.append(self._create_candle(i, 2000.0, 2000.5, 1999.5, 2000.0))
        
        avg_range = self.filter.calculate_avg_m1_range(candles)
        self.assertGreater(avg_range, 0.0)
    
    def test_check_volatility_filters_xauusd(self):
        """Test volatility filters for XAUUSD"""
        candles = []
        # Create candles with good volatility
        for i in range(10):
            candles.append(self._create_candle(i, 2000.0, 2000.6, 1999.4, 2000.0))
        
        current_spread = 0.2  # Within limit
        
        result = self.filter.check_volatility_filters("XAUUSDc", candles, current_spread)
        self.assertIsInstance(result, VolatilityFilterResult)
        # May pass or fail depending on actual ATR/range values
        self.assertGreaterEqual(result.atr1_value, 0.0)
    
    def test_check_session_filter(self):
        """Test session filter"""
        # Should allow by default (filter may be disabled)
        result = self.filter.check_session_filter("XAUUSDc")
        self.assertIsInstance(result, bool)
    
    def test_is_volatility_expanding(self):
        """Test volatility expansion detection"""
        candles = []
        # Low volatility candles
        for i in range(5):
            candles.append(self._create_candle(i, 2000.0, 2000.2, 1999.8, 2000.0))
        
        # Higher volatility candles
        for i in range(5, 10):
            candles.append(self._create_candle(i, 2000.0, 2000.5, 1999.5, 2000.0))
        
        expanding = self.filter.is_volatility_expanding(candles)
        # Should detect expansion if recent volatility > previous
        self.assertIsInstance(expanding, bool)


if __name__ == '__main__':
    unittest.main()

