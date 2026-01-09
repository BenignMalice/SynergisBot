"""
Test script for Confluence Calculator fixes
Tests Fix 22, Adjustment 1, Fix 11, Fix 12, Fix 15, Fix 21, Fix 20
"""
import unittest
from unittest.mock import Mock, MagicMock
from infra.confluence_calculator import ConfluenceCalculator
from datetime import datetime, timezone
import threading
import time


class MockIndicatorBridge:
    """Mock indicator bridge for testing"""
    
    def get_multi(self, symbol):
        """Return mock multi-timeframe data"""
        return {
            "M5": {
                "atr14": 50.0,
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


class TestConfluenceFixes(unittest.TestCase):
    """Test suite for confluence calculator fixes"""
    
    def setUp(self):
        """Set up test environment"""
        self.mock_bridge = MockIndicatorBridge()
        self.calculator = ConfluenceCalculator(self.mock_bridge, cache_ttl=5)
    
    def test_fix_22_symbol_parameter_passing(self):
        """Test Fix 22: Symbol parameter is passed to volatility calculation"""
        # Test BTC with 2.5% ATR (should score 100 - optimal for BTC)
        tf_data = {
            'atr14': 250.0,  # 2.5% of 10000
            'current_close': 10000.0
        }
        
        # BTC should score 100 for 2.5% ATR (within 1.0%-4.0% optimal range)
        score_btc = self.calculator._calculate_volatility_health_for_timeframe(
            tf_data, symbol='BTCUSDc'
        )
        self.assertEqual(score_btc, 100, "BTC should score 100 for 2.5% ATR")
        
        # XAU with 0.8% ATR (should score 100 - optimal for XAU)
        tf_data_xau = {
            'atr14': 80.0,  # 0.8% of 10000
            'current_close': 10000.0
        }
        score_xau = self.calculator._calculate_volatility_health_for_timeframe(
            tf_data_xau, symbol='XAUUSDc'
        )
        self.assertEqual(score_xau, 100, "XAU should score 100 for 0.8% ATR")
        
        # Default symbol with 1.5% ATR (should score 100 - optimal for default)
        tf_data_default = {
            'atr14': 150.0,  # 1.5% of 10000
            'current_close': 10000.0
        }
        score_default = self.calculator._calculate_volatility_health_for_timeframe(
            tf_data_default, symbol='EURUSDc'
        )
        self.assertEqual(score_default, 100, "Default should score 100 for 1.5% ATR")
    
    def test_adjustment_1_symbol_specific_thresholds(self):
        """Test Adjustment 1: Symbol-specific ATR% thresholds"""
        # Test BTC thresholds
        thresholds_btc = self.calculator._get_volatility_thresholds('BTCUSDc')
        self.assertEqual(thresholds_btc['optimal_low'], 1.0)
        self.assertEqual(thresholds_btc['optimal_high'], 4.0)
        self.assertEqual(thresholds_btc['low_min'], 0.8)
        self.assertEqual(thresholds_btc['high_max'], 5.0)
        
        # Test XAU thresholds
        thresholds_xau = self.calculator._get_volatility_thresholds('XAUUSDc')
        self.assertEqual(thresholds_xau['optimal_low'], 0.4)
        self.assertEqual(thresholds_xau['optimal_high'], 1.5)
        self.assertEqual(thresholds_xau['low_min'], 0.3)
        self.assertEqual(thresholds_xau['high_max'], 2.0)
        
        # Test default thresholds
        thresholds_default = self.calculator._get_volatility_thresholds('EURUSDc')
        self.assertEqual(thresholds_default['optimal_low'], 0.5)
        self.assertEqual(thresholds_default['optimal_high'], 2.0)
        self.assertEqual(thresholds_default['low_min'], 0.3)
        self.assertEqual(thresholds_default['high_max'], 3.0)
        
        # Test BTC with high ATR (5.5% - should score 40)
        tf_data = {
            'atr14': 550.0,  # 5.5% of 10000
            'current_close': 10000.0
        }
        score = self.calculator._calculate_volatility_health_for_timeframe(
            tf_data, symbol='BTCUSDc'
        )
        self.assertEqual(score, 40, "BTC should score 40 for 5.5% ATR (too high)")
        
        # Test XAU with high ATR (2.5% - should score 40)
        tf_data_xau = {
            'atr14': 250.0,  # 2.5% of 10000
            'current_close': 10000.0
        }
        score_xau = self.calculator._calculate_volatility_health_for_timeframe(
            tf_data_xau, symbol='XAUUSDc'
        )
        self.assertEqual(score_xau, 40, "XAU should score 40 for 2.5% ATR (too high)")
    
    def test_fix_12_input_validation(self):
        """Test Fix 12: Input validation and parameter checking"""
        # Test None indicator_bridge
        with self.assertRaises(ValueError):
            ConfluenceCalculator(None)
        
        # Test invalid cache_ttl
        calc = ConfluenceCalculator(self.mock_bridge, cache_ttl=-5)
        self.assertEqual(calc._cache_ttl, 30, "Should default to 30 for invalid TTL")
        
        # Test None symbol
        result = self.calculator.calculate_confluence(None)
        self.assertIn('confluence_score', result)
        self.assertEqual(result['confluence_score'], 0)
        
        # Test empty symbol
        result = self.calculator.calculate_confluence("")
        self.assertIn('confluence_score', result)
        self.assertEqual(result['confluence_score'], 0)
        
        # Test non-string symbol
        result = self.calculator.calculate_confluence(123)
        self.assertIn('confluence_score', result)
        self.assertEqual(result['confluence_score'], 0)
    
    def test_fix_15_cache_key_normalization(self):
        """Test Fix 15: Cache key normalization"""
        # Test normalization
        key1 = self.calculator._normalize_cache_key("btcusdc")
        key2 = self.calculator._normalize_cache_key("BTCUSDc")
        key3 = self.calculator._normalize_cache_key("BTCUSD")
        key4 = self.calculator._normalize_cache_key("btcusdcc")
        
        self.assertEqual(key1, "BTCUSDc")
        self.assertEqual(key2, "BTCUSDc")
        self.assertEqual(key3, "BTCUSDc")
        self.assertEqual(key4, "BTCUSDc")
        
        # All should produce same cache key
        self.assertEqual(key1, key2)
        self.assertEqual(key2, key3)
        self.assertEqual(key3, key4)
    
    def test_fix_11_thread_safety(self):
        """Test Fix 11: Thread safety for cache"""
        results = {}
        errors = []
        
        def calculate(symbol):
            try:
                result = self.calculator.calculate_confluence_per_timeframe(symbol)
                results[symbol] = result
            except Exception as e:
                errors.append((symbol, str(e)))
        
        # Create multiple threads accessing cache simultaneously
        threads = [
            threading.Thread(target=calculate, args=('BTCUSDc',)),
            threading.Thread(target=calculate, args=('XAUUSDc',)),
            threading.Thread(target=calculate, args=('BTCUSDc',)),  # Same symbol
            threading.Thread(target=calculate, args=('XAUUSDc',)),  # Same symbol
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Should have no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        
        # Should have results for both symbols
        self.assertIn('BTCUSDc', results)
        self.assertIn('XAUUSDc', results)
    
    def test_fix_21_public_cache_methods(self):
        """Test Fix 21: Public cache access methods"""
        # Calculate confluence to populate cache
        result = self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
        
        # Get cache info
        cache_info = self.calculator.get_cache_info('BTCUSDc')
        
        self.assertIsNotNone(cache_info, "Cache info should not be None")
        self.assertTrue(cache_info['cached'], "Should be cached")
        self.assertGreaterEqual(cache_info['cache_age_seconds'], 0)
        self.assertIn('cache_timestamp', cache_info)
        self.assertIn('is_fresh', cache_info)
        
        # Test with non-cached symbol
        cache_info_missing = self.calculator.get_cache_info('NONEXISTENT')
        self.assertIsNone(cache_info_missing, "Should return None for non-cached symbol")
        
        # Test with invalid symbol
        cache_info_invalid = self.calculator.get_cache_info(None)
        self.assertIsNone(cache_info_invalid, "Should return None for invalid symbol")
    
    def test_fix_20_timezone_aware_timestamps(self):
        """Test Fix 20: Timezone-aware timestamps"""
        result = self.calculator.calculate_confluence('BTCUSDc')
        
        # Check timestamp is timezone-aware
        timestamp_str = result.get('timestamp')
        self.assertIsNotNone(timestamp_str, "Should have timestamp")
        
        # Parse and verify it's timezone-aware
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        self.assertIsNotNone(timestamp.tzinfo, "Timestamp should be timezone-aware")
    
    def test_cache_functionality(self):
        """Test cache functionality"""
        symbol = 'BTCUSDc'
        
        # First call - should calculate
        result1 = self.calculator.calculate_confluence_per_timeframe(symbol)
        
        # Second call immediately - should use cache
        result2 = self.calculator.calculate_confluence_per_timeframe(symbol)
        
        # Results should be identical
        self.assertEqual(
            result1['M5']['score'],
            result2['M5']['score'],
            "Cached result should be identical"
        )
        
        # Wait for cache to expire
        time.sleep(6)
        
        # Third call after expiry - should recalculate
        result3 = self.calculator.calculate_confluence_per_timeframe(symbol)
        
        # Should still have valid structure
        self.assertIn('M5', result3)
        self.assertIn('M15', result3)
        self.assertIn('H1', result3)
    
    def test_btc_vs_xau_scoring_difference(self):
        """Test that BTC and XAU score differently for same ATR%"""
        # Same ATR% (2.0%) but different symbols
        tf_data = {
            'atr14': 200.0,  # 2.0% of 10000
            'current_close': 10000.0
        }
        
        score_btc = self.calculator._calculate_volatility_health_for_timeframe(
            tf_data, symbol='BTCUSDc'
        )
        score_xau = self.calculator._calculate_volatility_health_for_timeframe(
            tf_data, symbol='XAUUSDc'
        )
        
        # BTC: 2.0% is within optimal range (1.0%-4.0%) -> 100
        # XAU: 2.0% is at high_max boundary (0.4%-1.5% optimal, 2.0% high_max) -> 70 (slightly high)
        self.assertEqual(score_btc, 100, "BTC should score 100 for 2.0% ATR")
        self.assertEqual(score_xau, 70, "XAU should score 70 for 2.0% ATR (at high_max boundary)")


if __name__ == '__main__':
    print("=" * 70)
    print("Testing Confluence Calculator Fixes")
    print("=" * 70)
    print()
    
    unittest.main(verbosity=2)

