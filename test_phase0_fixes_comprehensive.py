"""
Comprehensive Test Suite for Phase 0 Fixes
Tests all implemented fixes and improvements
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
from infra.confluence_calculator import ConfluenceCalculator
from datetime import datetime, timezone
import threading
import time


class MockIndicatorBridge:
    """Mock indicator bridge for testing"""
    
    def __init__(self):
        self.multi_data = {}
    
    def get_multi(self, symbol):
        """Return mock multi-timeframe data"""
        if symbol not in self.multi_data:
            # Generate default data
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


class TestPhase0FixesComprehensive(unittest.TestCase):
    """Comprehensive test suite for all Phase 0 fixes"""
    
    def setUp(self):
        """Set up test environment"""
        self.mock_bridge = MockIndicatorBridge()
        self.calculator = ConfluenceCalculator(self.mock_bridge, cache_ttl=5)
    
    # ========== Fix 22: Symbol Parameter Passing ==========
    def test_fix_22_symbol_parameter_passed(self):
        """Test Fix 22: Symbol parameter is passed to volatility calculation"""
        # Test BTC with 2.5% ATR (should score 100 - optimal for BTC)
        tf_data = {
            'atr14': 250.0,  # 2.5% of 10000
            'current_close': 10000.0
        }
        
        score_btc = self.calculator._calculate_volatility_health_for_timeframe(
            tf_data, symbol='BTCUSDc'
        )
        self.assertEqual(score_btc, 100, "BTC should score 100 for 2.5% ATR")
        
        # Test XAU with 0.8% ATR (should score 100 - optimal for XAU)
        tf_data_xau = {
            'atr14': 80.0,  # 0.8% of 10000
            'current_close': 10000.0
        }
        score_xau = self.calculator._calculate_volatility_health_for_timeframe(
            tf_data_xau, symbol='XAUUSDc'
        )
        self.assertEqual(score_xau, 100, "XAU should score 100 for 0.8% ATR")
    
    # ========== Adjustment 1: Symbol-Specific Thresholds ==========
    def test_adjustment_1_symbol_specific_thresholds(self):
        """Test Adjustment 1: Symbol-specific ATR% thresholds"""
        # Test BTC thresholds
        thresholds_btc = self.calculator._get_volatility_thresholds('BTCUSDc')
        self.assertEqual(thresholds_btc['optimal_low'], 1.0)
        self.assertEqual(thresholds_btc['optimal_high'], 4.0)
        
        # Test XAU thresholds
        thresholds_xau = self.calculator._get_volatility_thresholds('XAUUSDc')
        self.assertEqual(thresholds_xau['optimal_low'], 0.4)
        self.assertEqual(thresholds_xau['optimal_high'], 1.5)
        
        # Test default thresholds
        thresholds_default = self.calculator._get_volatility_thresholds('EURUSDc')
        self.assertEqual(thresholds_default['optimal_low'], 0.5)
        self.assertEqual(thresholds_default['optimal_high'], 2.0)
    
    # ========== Fix 11: Thread Safety ==========
    def test_fix_11_thread_safety(self):
        """Test Fix 11: Thread safety for cache operations"""
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
            threading.Thread(target=calculate, args=('EURUSDc',)),
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Should have no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        
        # Should have results for all symbols
        self.assertIn('BTCUSDc', results)
        self.assertIn('XAUUSDc', results)
        self.assertIn('EURUSDc', results)
    
    # ========== Fix 12: Input Validation ==========
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
    
    # ========== Fix 15: Cache Key Normalization ==========
    def test_fix_15_cache_key_normalization(self):
        """Test Fix 15: Cache key normalization"""
        # Test normalization removes all trailing 'c'
        key1 = self.calculator._normalize_cache_key("btcusdc")
        key2 = self.calculator._normalize_cache_key("BTCUSDc")
        key3 = self.calculator._normalize_cache_key("BTCUSD")
        key4 = self.calculator._normalize_cache_key("btcusdcc")
        key5 = self.calculator._normalize_cache_key("btcusdccc")
        
        # All should produce same cache key
        expected = "BTCUSDc"
        self.assertEqual(key1, expected)
        self.assertEqual(key2, expected)
        self.assertEqual(key3, expected)
        self.assertEqual(key4, expected)
        self.assertEqual(key5, expected)
    
    # ========== Fix 21: Public Cache Methods ==========
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
    
    # ========== Fix 20: Timezone-Aware Timestamps ==========
    def test_fix_20_timezone_aware_timestamps(self):
        """Test Fix 20: Timezone-aware timestamps"""
        result = self.calculator.calculate_confluence('BTCUSDc')
        
        # Check timestamp is timezone-aware
        timestamp_str = result.get('timestamp')
        self.assertIsNotNone(timestamp_str, "Should have timestamp")
        
        # Parse and verify it's timezone-aware
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        self.assertIsNotNone(timestamp.tzinfo, "Timestamp should be timezone-aware")
    
    # ========== Fix: Indicator Bridge None Checks ==========
    def test_indicator_bridge_none_checks(self):
        """Test indicator bridge None checks"""
        # Create calculator with None bridge (should raise)
        with self.assertRaises(ValueError):
            ConfluenceCalculator(None)
        
        # Test that get_multi is checked
        calc = ConfluenceCalculator(self.mock_bridge)
        # This should work
        result = calc.calculate_confluence('BTCUSDc')
        self.assertIsNotNone(result)
    
    # ========== Fix 1: ATR Ratio Consistency (Lightweight) ==========
    def test_fix_1_atr_ratio_consistency(self):
        """Test Fix 1: ATR ratio consistency with lightweight multi-timeframe"""
        # Create multi-data with different ATR ratios
        multi_data = {
            'H1': {'atr14': 140.0, 'atr50': 100.0},  # Ratio: 1.4 (VOLATILE)
            'M15': {'atr14': 130.0, 'atr50': 100.0},  # Ratio: 1.3 (TRANSITIONAL)
            'M5': {'atr14': 120.0, 'atr50': 100.0},  # Ratio: 1.2 (STABLE)
        }
        
        # Calculate weighted ratio: (1.4*0.5 + 1.3*0.3 + 1.2*0.2) / 1.0 = 1.33
        regime = self.calculator._calculate_volatility_regime_lightweight(multi_data, 'BTCUSDc')
        self.assertEqual(regime, 'TRANSITIONAL', "Weighted ratio 1.33 should be TRANSITIONAL")
        
        # Test with only H1 data
        multi_data_h1_only = {
            'H1': {'atr14': 150.0, 'atr50': 100.0},  # Ratio: 1.5 (VOLATILE)
        }
        regime = self.calculator._calculate_volatility_regime_lightweight(multi_data_h1_only, 'BTCUSDc')
        self.assertEqual(regime, 'VOLATILE', "Ratio 1.5 should be VOLATILE")
    
    # ========== Fix 2: Symbol Normalization ==========
    def test_fix_2_symbol_normalization(self):
        """Test Fix 2: Symbol normalization for BTC detection"""
        # Test normalization
        normalized1 = self.calculator._normalize_symbol_for_check("btcusdc")
        normalized2 = self.calculator._normalize_symbol_for_check("BTCUSDc")
        normalized3 = self.calculator._normalize_symbol_for_check("BTCUSD")
        
        self.assertEqual(normalized1, "BTCUSDc")
        self.assertEqual(normalized2, "BTCUSDc")
        self.assertEqual(normalized3, "BTCUSDc")
        
        # Test BTC detection uses normalized symbol
        # This is tested indirectly through regime detection
        # (which uses normalized symbol for BTC check)
    
    # ========== Fix 9: Error Handling & Validation ==========
    def test_fix_9_error_handling_validation(self):
        """Test Fix 9: Error handling and data validation"""
        # Test validation with missing required keys
        invalid_data = {'atr14': 50.0}  # Missing current_close
        is_valid = self.calculator._validate_timeframe_data(invalid_data, ['atr14', 'current_close'])
        self.assertFalse(is_valid, "Should be invalid - missing current_close")
        
        # Test validation with None values
        invalid_data2 = {'atr14': None, 'current_close': 10000.0}
        is_valid = self.calculator._validate_timeframe_data(invalid_data2, ['atr14', 'current_close'])
        self.assertFalse(is_valid, "Should be invalid - atr14 is None")
        
        # Test validation with invalid numeric values
        invalid_data3 = {'atr14': -10.0, 'current_close': 10000.0}
        is_valid = self.calculator._validate_timeframe_data(invalid_data3, ['atr14', 'current_close'])
        self.assertFalse(is_valid, "Should be invalid - atr14 is negative")
        
        # Test validation with valid data
        valid_data = {'atr14': 50.0, 'current_close': 10000.0}
        is_valid = self.calculator._validate_timeframe_data(valid_data, ['atr14', 'current_close'])
        self.assertTrue(is_valid, "Should be valid")
    
    # ========== Fix 13: Score Bounds Validation ==========
    def test_fix_13_score_bounds_validation(self):
        """Test Fix 13: Score bounds validation (clamp to 0-100)"""
        # Test that scores are clamped
        # This is tested indirectly through calculate_confluence_per_timeframe
        # which should always return scores between 0-100
        
        result = self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
        
        for tf in ['M1', 'M5', 'M15', 'H1']:
            if result[tf].get('available'):
                score = result[tf]['score']
                self.assertGreaterEqual(score, 0, f"{tf} score should be >= 0")
                self.assertLessEqual(score, 100, f"{tf} score should be <= 100")
    
    # ========== Fix 17: M1 Component Validation ==========
    def test_fix_17_m1_component_validation(self):
        """Test Fix 17: M1 component validation"""
        # Test with both components missing
        result = self.calculator.calculate_confluence_per_timeframe(
            'BTCUSDc',
            m1_analyzer=None,
            m1_data_fetcher=None
        )
        self.assertFalse(result['M1']['available'], "M1 should be unavailable when both components missing")
        
        # Test with only analyzer missing
        mock_fetcher = Mock()
        result = self.calculator.calculate_confluence_per_timeframe(
            'BTCUSDc',
            m1_analyzer=None,
            m1_data_fetcher=mock_fetcher
        )
        self.assertFalse(result['M1']['available'], "M1 should be unavailable when analyzer missing")
        
        # Test with only fetcher missing
        mock_analyzer = Mock()
        result = self.calculator.calculate_confluence_per_timeframe(
            'BTCUSDc',
            m1_analyzer=mock_analyzer,
            m1_data_fetcher=None
        )
        self.assertFalse(result['M1']['available'], "M1 should be unavailable when fetcher missing")
    
    # ========== Integration Tests ==========
    def test_integration_btc_vs_xau_different_scoring(self):
        """Integration test: BTC and XAU score differently for same ATR%"""
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
        # XAU: 2.0% is at high_max boundary (0.4%-1.5% optimal, 2.0% high_max) -> 70
        self.assertEqual(score_btc, 100, "BTC should score 100 for 2.0% ATR")
        self.assertEqual(score_xau, 70, "XAU should score 70 for 2.0% ATR (at boundary)")
    
    def test_integration_cache_functionality(self):
        """Integration test: Cache functionality"""
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
    
    def test_integration_end_to_end_btc_calculation(self):
        """Integration test: End-to-end BTC calculation with all fixes"""
        result = self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
        
        # Verify structure
        self.assertIn('M1', result)
        self.assertIn('M5', result)
        self.assertIn('M15', result)
        self.assertIn('H1', result)
        
        # Verify scores are valid
        for tf in ['M5', 'M15', 'H1']:
            tf_result = result[tf]
            if tf_result.get('available'):
                self.assertGreaterEqual(tf_result['score'], 0)
                self.assertLessEqual(tf_result['score'], 100)
                self.assertIn('grade', tf_result)
                self.assertIn('factors', tf_result)
    
    def test_integration_end_to_end_xau_calculation(self):
        """Integration test: End-to-end XAU calculation with all fixes"""
        result = self.calculator.calculate_confluence_per_timeframe('XAUUSDc')
        
        # Verify structure
        self.assertIn('M1', result)
        self.assertIn('M5', result)
        self.assertIn('M15', result)
        self.assertIn('H1', result)
        
        # Verify XAU uses different thresholds than BTC
        # (tested through volatility health scoring)


if __name__ == '__main__':
    print("=" * 70)
    print("Comprehensive Phase 0 Fixes Test Suite")
    print("=" * 70)
    print()
    print("Testing all Phase 0 fixes:")
    print("  - Fix 22: Symbol Parameter Passing")
    print("  - Adjustment 1: Symbol-Specific Thresholds")
    print("  - Fix 11: Thread Safety")
    print("  - Fix 12: Input Validation")
    print("  - Fix 15: Cache Key Normalization")
    print("  - Fix 21: Public Cache Methods")
    print("  - Fix 20: Timezone-Aware Timestamps")
    print("  - Fix: Indicator Bridge None Checks")
    print("  - Fix 1: ATR Ratio Consistency")
    print("  - Fix 2: Symbol Normalization")
    print("  - Fix 9: Error Handling & Validation")
    print("  - Fix 13: Score Bounds Validation")
    print("  - Fix 17: M1 Component Validation")
    print()
    print("=" * 70)
    print()
    
    unittest.main(verbosity=2)

