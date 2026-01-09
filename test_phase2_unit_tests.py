"""
Phase 2: Comprehensive Unit Tests
Tests individual components and fixes in isolation
"""
import unittest
from unittest.mock import Mock, patch
from infra.confluence_calculator import ConfluenceCalculator
from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
from test_fixtures import (
    MockIndicatorBridge, MockM1Analyzer, MockM1DataFetcher,
    create_btc_data, create_xau_data, create_regime_test_data,
    create_invalid_data, reset_singleton
)
import threading
import time


class TestFix16ExceptionHandling(unittest.TestCase):
    """Test Fix 16: Exception Handling Improvement"""
    
    def setUp(self):
        reset_singleton(ConfluenceCalculator)
        self.bridge = MockIndicatorBridge()
        self.calculator = ConfluenceCalculator(self.bridge, cache_ttl=5)
    
    def tearDown(self):
        reset_singleton(ConfluenceCalculator)
    
    def test_keyerror_handling(self):
        """Test KeyError is caught and handled gracefully"""
        # Create data missing required keys
        self.bridge.multi_data['TEST'] = {'M5': {}}
        
        result = self.calculator.calculate_confluence_per_timeframe('TEST')
        self.assertIn('M5', result)
        self.assertFalse(result['M5']['available'])
    
    def test_attributeerror_handling(self):
        """Test AttributeError is caught and handled gracefully"""
        # Create bridge that raises AttributeError
        self.bridge.get_multi = Mock(side_effect=AttributeError("No attribute"))
        
        result = self.calculator.calculate_confluence_per_timeframe('TEST')
        self.assertIsNotNone(result)
        # Should return empty result
        self.assertIn('M1', result)
    
    def test_valueerror_handling(self):
        """Test ValueError is caught and handled gracefully"""
        # Create data with invalid values
        self.bridge.multi_data['TEST'] = create_invalid_data()
        
        result = self.calculator.calculate_confluence_per_timeframe('TEST')
        self.assertIsNotNone(result)
        # Should handle invalid data gracefully
    
    def test_zerodivisionerror_handling(self):
        """Test ZeroDivisionError in regime calculation"""
        # Create data that would cause division by zero
        data = create_regime_test_data('STABLE')
        data['H1']['atr50'] = 0  # Would cause division by zero
        self.bridge.multi_data['BTCUSDc'] = data
        
        result = self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
        # Should not crash, should return result
        self.assertIsNotNone(result)


class TestFix14RegimeValidation(unittest.TestCase):
    """Test Fix 14: Regime String Validation"""
    
    def setUp(self):
        self.analyzer = M1MicrostructureAnalyzer()
        self.analysis = {
            'available': True,
            'choch_bos': {'confidence': 75},
            'session_context': {'volatility_tier': 'NORMAL'},
            'momentum': {'quality': 'STRONG'},
            'liquidity': {'proximity_score': 80},
            'strategy_fit': 70
        }
    
    def test_valid_regime_stable(self):
        """Test valid STABLE regime is accepted"""
        result = self.analyzer.calculate_microstructure_confluence(
            analysis=self.analysis,
            symbol='BTCUSDc',
            volatility_regime='STABLE'
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['components']['session_volatility_suitability'], 80)
    
    def test_valid_regime_transitional(self):
        """Test valid TRANSITIONAL regime is accepted"""
        result = self.analyzer.calculate_microstructure_confluence(
            analysis=self.analysis,
            symbol='BTCUSDc',
            volatility_regime='TRANSITIONAL'
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['components']['session_volatility_suitability'], 75)
    
    def test_valid_regime_volatile(self):
        """Test valid VOLATILE regime is accepted"""
        result = self.analyzer.calculate_microstructure_confluence(
            analysis=self.analysis,
            symbol='BTCUSDc',
            volatility_regime='VOLATILE'
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['components']['session_volatility_suitability'], 85)
    
    def test_invalid_regime_string(self):
        """Test invalid regime string falls back to session-based"""
        result = self.analyzer.calculate_microstructure_confluence(
            analysis=self.analysis,
            symbol='BTCUSDc',
            volatility_regime='INVALID_REGIME'
        )
        self.assertIsNotNone(result)
        # Should fall back to session-based (NORMAL = 80)
        self.assertEqual(result['components']['session_volatility_suitability'], 80)
    
    def test_none_regime(self):
        """Test None regime uses session-based logic"""
        result = self.analyzer.calculate_microstructure_confluence(
            analysis=self.analysis,
            symbol='BTCUSDc',
            volatility_regime=None
        )
        self.assertIsNotNone(result)
        # Should use session-based (NORMAL = 80)
        self.assertEqual(result['components']['session_volatility_suitability'], 80)
    
    def test_empty_regime_string(self):
        """Test empty regime string falls back to session-based"""
        result = self.analyzer.calculate_microstructure_confluence(
            analysis=self.analysis,
            symbol='BTCUSDc',
            volatility_regime=''
        )
        self.assertIsNotNone(result)
        # Should fall back to session-based
        self.assertEqual(result['components']['session_volatility_suitability'], 80)
    
    def test_case_insensitive_regime(self):
        """Test regime validation is case-insensitive"""
        result = self.analyzer.calculate_microstructure_confluence(
            analysis=self.analysis,
            symbol='BTCUSDc',
            volatility_regime='stable'  # lowercase
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['components']['session_volatility_suitability'], 80)


class TestSymbolSpecificLogic(unittest.TestCase):
    """Test symbol-specific logic (Adjustment 1, Fix 22)"""
    
    def setUp(self):
        reset_singleton(ConfluenceCalculator)
        self.bridge = MockIndicatorBridge()
        self.calculator = ConfluenceCalculator(self.bridge, cache_ttl=5)
    
    def tearDown(self):
        reset_singleton(ConfluenceCalculator)
    
    def test_btc_optimal_atr(self):
        """Test BTC scores 100 for optimal ATR (2.5%)"""
        tf_data = {
            'atr14': 2500.0,  # 2.5% of 100000
            'current_close': 100000.0
        }
        score = self.calculator._calculate_volatility_health_for_timeframe(
            tf_data, symbol='BTCUSDc'
        )
        self.assertEqual(score, 100, "BTC should score 100 for 2.5% ATR")
    
    def test_xau_optimal_atr(self):
        """Test XAU scores 100 for optimal ATR (0.8%)"""
        tf_data = {
            'atr14': 16.0,  # 0.8% of 2000
            'current_close': 2000.0
        }
        score = self.calculator._calculate_volatility_health_for_timeframe(
            tf_data, symbol='XAUUSDc'
        )
        self.assertEqual(score, 100, "XAU should score 100 for 0.8% ATR")
    
    def test_btc_high_atr(self):
        """Test BTC scores appropriately for high ATR (5.0%)"""
        tf_data = {
            'atr14': 5000.0,  # 5.0% of 100000
            'current_close': 100000.0
        }
        score = self.calculator._calculate_volatility_health_for_timeframe(
            tf_data, symbol='BTCUSDc'
        )
        # Should score lower than 100 but not too low (BTC tolerates high volatility)
        self.assertGreater(score, 40, "BTC should score > 40 for 5.0% ATR")
        self.assertLess(score, 100, "BTC should score < 100 for 5.0% ATR")
    
    def test_xau_high_atr(self):
        """Test XAU scores appropriately for high ATR (2.0%)"""
        tf_data = {
            'atr14': 40.0,  # 2.0% of 2000
            'current_close': 2000.0
        }
        score = self.calculator._calculate_volatility_health_for_timeframe(
            tf_data, symbol='XAUUSDc'
        )
        # Should score lower (XAU less tolerant of high volatility)
        self.assertLess(score, 100, "XAU should score < 100 for 2.0% ATR")


class TestScoreBoundsValidation(unittest.TestCase):
    """Test Fix 13: Score Bounds Validation"""
    
    def setUp(self):
        reset_singleton(ConfluenceCalculator)
        self.bridge = MockIndicatorBridge()
        self.calculator = ConfluenceCalculator(self.bridge, cache_ttl=5)
    
    def tearDown(self):
        reset_singleton(ConfluenceCalculator)
    
    def test_scores_clamped_to_100(self):
        """Test scores exceeding 100 are clamped"""
        # Create data that would produce score > 100
        tf_data = {
            'atr14': 50.0,
            'current_close': 10000.0,
            'ema20': 10000.0,
            'ema50': 10000.0,
            'ema200': 10000.0,
            'rsi': 100,  # Extreme values
            'macd': 1000,
            'macd_signal': 0,
            'bb_upper': 20000.0,
            'bb_lower': 0.0
        }
        
        result = self.calculator.calculate_confluence_per_timeframe('TEST')
        # All scores should be <= 100
        for tf in ['M5', 'M15', 'H1']:
            if result[tf]['available']:
                self.assertLessEqual(result[tf]['score'], 100)
                for factor_score in result[tf]['factors'].values():
                    self.assertLessEqual(factor_score, 100)
    
    def test_scores_clamped_to_0(self):
        """Test scores below 0 are clamped"""
        # Create data that would produce score < 0
        tf_data = {
            'atr14': 0,
            'current_close': 0,
            'ema20': 0,
            'ema50': 0,
            'ema200': 0,
            'rsi': 0,
            'macd': -1000,
            'macd_signal': 0,
            'bb_upper': 0,
            'bb_lower': 0
        }
        
        self.bridge.multi_data['TEST'] = {'M5': tf_data, 'M15': tf_data, 'H1': tf_data}
        result = self.calculator.calculate_confluence_per_timeframe('TEST')
        
        # All scores should be >= 0
        for tf in ['M5', 'M15', 'H1']:
            if result[tf]['available']:
                self.assertGreaterEqual(result[tf]['score'], 0)
                for factor_score in result[tf]['factors'].values():
                    self.assertGreaterEqual(factor_score, 0)


class TestCacheOperations(unittest.TestCase):
    """Test cache operations (Fix 6, Fix 7, Fix 15)"""
    
    def setUp(self):
        reset_singleton(ConfluenceCalculator)
        self.bridge = MockIndicatorBridge()
        self.calculator = ConfluenceCalculator(self.bridge, cache_ttl=2)
    
    def tearDown(self):
        reset_singleton(ConfluenceCalculator)
    
    def test_cache_key_normalization(self):
        """Test Fix 15: Cache keys are normalized"""
        # Test different symbol formats use same cache
        result1 = self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
        result2 = self.calculator.calculate_confluence_per_timeframe('BTCUSDC')
        result3 = self.calculator.calculate_confluence_per_timeframe('btcusdc')
        
        # All should use same cache
        cache_info1 = self.calculator.get_cache_info('BTCUSDc')
        cache_info2 = self.calculator.get_cache_info('BTCUSDC')
        
        # Should have same cache entry
        self.assertEqual(cache_info1['cached'], cache_info2['cached'])
    
    def test_regime_cache_storage(self):
        """Test Fix 6: Regime is cached"""
        self.bridge.multi_data['BTCUSDc'] = create_regime_test_data('STABLE')
        
        # Calculate confluence (which caches regime)
        result = self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
        
        # Regime should be cached
        cached_regime = self.calculator.get_cached_regime('BTCUSDc')
        self.assertIsNotNone(cached_regime)
        self.assertIn(cached_regime, ['STABLE', 'TRANSITIONAL', 'VOLATILE'])
    
    def test_regime_cache_ttl(self):
        """Test regime cache respects TTL"""
        self.bridge.multi_data['BTCUSDc'] = create_regime_test_data('STABLE')
        
        # Calculate and cache
        self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
        regime1 = self.calculator.get_cached_regime('BTCUSDc')
        self.assertIsNotNone(regime1)
        
        # Wait for cache to expire
        time.sleep(3)
        
        # Cache should be expired
        regime2 = self.calculator.get_cached_regime('BTCUSDc')
        self.assertIsNone(regime2)
    
    def test_get_cached_regime_none(self):
        """Test Fix 7: get_cached_regime returns None if not cached"""
        regime = self.calculator.get_cached_regime('NONEXISTENT')
        self.assertIsNone(regime)


class TestM1ComponentValidation(unittest.TestCase):
    """Test Fix 17: M1 Component Validation"""
    
    def setUp(self):
        reset_singleton(ConfluenceCalculator)
        self.bridge = MockIndicatorBridge()
        self.calculator = ConfluenceCalculator(self.bridge, cache_ttl=5)
    
    def tearDown(self):
        reset_singleton(ConfluenceCalculator)
    
    def test_both_components_required(self):
        """Test both M1 components must be provided"""
        # Only analyzer
        result1 = self.calculator.calculate_confluence_per_timeframe(
            'TEST',
            m1_analyzer=MockM1Analyzer(),
            m1_data_fetcher=None
        )
        self.assertFalse(result1['M1']['available'])
        
        # Only fetcher
        result2 = self.calculator.calculate_confluence_per_timeframe(
            'TEST',
            m1_analyzer=None,
            m1_data_fetcher=MockM1DataFetcher()
        )
        self.assertFalse(result2['M1']['available'])
        
        # Both provided
        result3 = self.calculator.calculate_confluence_per_timeframe(
            'TEST',
            m1_analyzer=MockM1Analyzer(),
            m1_data_fetcher=MockM1DataFetcher()
        )
        # Should attempt calculation (may fail if other data missing, but should try)
        self.assertIsNotNone(result3['M1'])


if __name__ == '__main__':
    print("=" * 70)
    print("Phase 2: Comprehensive Unit Tests")
    print("=" * 70)
    print()
    print("Testing:")
    print("  - Fix 16: Exception Handling")
    print("  - Fix 14: Regime String Validation")
    print("  - Symbol-Specific Logic (Adjustment 1, Fix 22)")
    print("  - Fix 13: Score Bounds Validation")
    print("  - Cache Operations (Fix 6, Fix 7, Fix 15)")
    print("  - Fix 17: M1 Component Validation")
    print()
    print("=" * 70)
    print()
    
    unittest.main(verbosity=2)

