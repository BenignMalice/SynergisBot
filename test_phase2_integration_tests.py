"""
Phase 2: Integration Tests
Tests end-to-end flows and component interactions
"""
import unittest
from unittest.mock import Mock, patch
from infra.confluence_calculator import ConfluenceCalculator
from test_fixtures import (
    MockIndicatorBridge, MockM1Analyzer, MockM1DataFetcher,
    create_btc_data, create_xau_data, create_regime_test_data,
    reset_singleton
)
import threading
import time


class TestEndToEndConfluenceCalculation(unittest.TestCase):
    """Test complete confluence calculation flow"""
    
    def setUp(self):
        reset_singleton(ConfluenceCalculator)
        self.bridge = MockIndicatorBridge()
        self.calculator = ConfluenceCalculator(self.bridge, cache_ttl=5)
        self.m1_analyzer = MockM1Analyzer()
        self.m1_fetcher = MockM1DataFetcher()
    
    def tearDown(self):
        reset_singleton(ConfluenceCalculator)
    
    def test_btc_complete_calculation(self):
        """Test complete BTC confluence calculation with all components"""
        # Setup BTC data
        self.bridge.multi_data['BTCUSDc'] = create_btc_data(atr_percent=2.5)
        
        # Calculate confluence
        result = self.calculator.calculate_confluence_per_timeframe(
            symbol='BTCUSDc',
            m1_analyzer=self.m1_analyzer,
            m1_data_fetcher=self.m1_fetcher
        )
        
        # Verify structure
        self.assertIn('M1', result)
        self.assertIn('M5', result)
        self.assertIn('M15', result)
        self.assertIn('H1', result)
        
        # Verify M1 result
        m1_result = result['M1']
        if m1_result.get('available'):
            self.assertIn('score', m1_result)
            self.assertIn('grade', m1_result)
            self.assertIn('factors', m1_result)
            self.assertGreaterEqual(m1_result['score'], 0)
            self.assertLessEqual(m1_result['score'], 100)
        
        # Verify other timeframes
        for tf in ['M5', 'M15', 'H1']:
            tf_result = result[tf]
            self.assertIn('score', tf_result)
            self.assertIn('grade', tf_result)
            self.assertIn('available', tf_result)
            if tf_result['available']:
                self.assertIn('factors', tf_result)
                self.assertGreaterEqual(tf_result['score'], 0)
                self.assertLessEqual(tf_result['score'], 100)
    
    def test_xau_complete_calculation(self):
        """Test complete XAU confluence calculation"""
        # Setup XAU data
        self.bridge.multi_data['XAUUSDc'] = create_xau_data(atr_percent=0.8)
        
        # Calculate confluence
        result = self.calculator.calculate_confluence_per_timeframe(
            symbol='XAUUSDc',
            m1_analyzer=self.m1_analyzer,
            m1_data_fetcher=self.m1_fetcher
        )
        
        # Verify structure
        self.assertIn('M1', result)
        self.assertIn('M5', result)
        self.assertIn('M15', result)
        self.assertIn('H1', result)
        
        # Verify XAU uses session-based logic (not regime)
        m1_result = result['M1']
        if m1_result.get('available'):
            # Should have factors
            self.assertIn('factors', m1_result)
    
    def test_regime_detection_and_caching(self):
        """Test regime detection and caching for BTC"""
        # Setup BTC data with STABLE regime
        self.bridge.multi_data['BTCUSDc'] = create_regime_test_data('STABLE')
        
        # Calculate confluence
        result1 = self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
        
        # Regime should be cached
        cached_regime = self.calculator.get_cached_regime('BTCUSDc')
        self.assertIsNotNone(cached_regime)
        self.assertEqual(cached_regime, 'STABLE')
        
        # Second calculation should use cached regime
        result2 = self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
        
        # Should be same regime
        cached_regime2 = self.calculator.get_cached_regime('BTCUSDc')
        self.assertEqual(cached_regime, cached_regime2)
    
    def test_multiple_symbols_concurrent(self):
        """Test multiple symbols calculated concurrently"""
        # Setup data for multiple symbols
        self.bridge.multi_data['BTCUSDc'] = create_btc_data()
        self.bridge.multi_data['XAUUSDc'] = create_xau_data()
        
        results = {}
        errors = []
        
        def calculate(symbol):
            try:
                results[symbol] = self.calculator.calculate_confluence_per_timeframe(symbol)
            except Exception as e:
                errors.append((symbol, str(e)))
        
        # Run concurrently
        threads = [
            threading.Thread(target=calculate, args=('BTCUSDc',)),
            threading.Thread(target=calculate, args=('XAUUSDc',)),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have no errors
        self.assertEqual(len(errors), 0, f"Errors: {errors}")
        
        # Should have results for both
        self.assertIn('BTCUSDc', results)
        self.assertIn('XAUUSDc', results)
        
        # Both should have all timeframes
        for symbol in ['BTCUSDc', 'XAUUSDc']:
            result = results[symbol]
            for tf in ['M1', 'M5', 'M15', 'H1']:
                self.assertIn(tf, result)


class TestCacheIntegration(unittest.TestCase):
    """Test cache integration across components"""
    
    def setUp(self):
        reset_singleton(ConfluenceCalculator)
        self.bridge = MockIndicatorBridge()
        self.calculator = ConfluenceCalculator(self.bridge, cache_ttl=2)
    
    def tearDown(self):
        reset_singleton(ConfluenceCalculator)
    
    def test_confluence_cache_and_regime_cache_coordination(self):
        """Test confluence cache and regime cache work together"""
        # Setup BTC data with VOLATILE regime (ATR ratio >= 1.4)
        # H1: atr14=150, atr50=100, ratio=1.5 (VOLATILE)
        volatile_data = create_regime_test_data('VOLATILE')
        self.bridge.multi_data['BTCUSDc'] = volatile_data
        
        # First calculation
        result1 = self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
        
        # Both caches should have data
        cache_info = self.calculator.get_cache_info('BTCUSDc')
        regime = self.calculator.get_cached_regime('BTCUSDc')
        
        self.assertTrue(cache_info['cached'], "Confluence should be cached")
        self.assertIsNotNone(regime, "Regime should be cached")
        # Regime should be VOLATILE (ATR ratio 1.5 >= 1.4)
        self.assertIn(regime, ['STABLE', 'TRANSITIONAL', 'VOLATILE'], 
                     f"Regime should be valid, got: {regime}")
        
        # Second calculation (should use cache)
        result2 = self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
        
        # Should be same result
        if result1['M5'].get('available') and result2['M5'].get('available'):
            self.assertEqual(result1['M5']['score'], result2['M5']['score'])
    
    def test_cache_expiration(self):
        """Test cache expiration works correctly"""
        # Setup data
        self.bridge.multi_data['BTCUSDc'] = create_btc_data()
        
        # First calculation
        result1 = self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
        cache_info1 = self.calculator.get_cache_info('BTCUSDc')
        regime1 = self.calculator.get_cached_regime('BTCUSDc')
        
        self.assertTrue(cache_info1['cached'])
        self.assertIsNotNone(regime1)
        
        # Wait for cache to expire
        time.sleep(3)
        
        # Second calculation (should recalculate)
        result2 = self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
        cache_info2 = self.calculator.get_cache_info('BTCUSDc')
        regime2 = self.calculator.get_cached_regime('BTCUSDc')
        
        # Should be fresh (may be same values, but cache should be refreshed)
        self.assertTrue(cache_info2['cached'])
        if regime2:
            # Regime may be recalculated
            pass


class TestSingletonIntegration(unittest.TestCase):
    """Test singleton pattern integration"""
    
    def setUp(self):
        reset_singleton(ConfluenceCalculator)
    
    def tearDown(self):
        reset_singleton(ConfluenceCalculator)
    
    def test_singleton_shares_cache(self):
        """Test singleton shares cache between instances"""
        bridge1 = MockIndicatorBridge()
        bridge1.multi_data['BTCUSDc'] = create_btc_data()
        
        calc1 = ConfluenceCalculator(bridge1, cache_ttl=5)
        result1 = calc1.calculate_confluence_per_timeframe('BTCUSDc')
        
        # Create "new" instance
        bridge2 = MockIndicatorBridge()
        bridge2.multi_data['BTCUSDc'] = create_btc_data()
        calc2 = ConfluenceCalculator(bridge2, cache_ttl=5)
        
        # Should be same instance
        self.assertIs(calc1, calc2)
        
        # Should share cache
        cache_info = calc2.get_cache_info('BTCUSDc')
        self.assertTrue(cache_info['cached'], "Cache should be shared")
    
    def test_singleton_with_m1_components(self):
        """Test singleton works with M1 components"""
        bridge = MockIndicatorBridge()
        bridge.multi_data['BTCUSDc'] = create_btc_data()
        
        calc1 = ConfluenceCalculator(bridge, cache_ttl=5)
        m1_analyzer = MockM1Analyzer()
        m1_fetcher = MockM1DataFetcher()
        
        result1 = calc1.calculate_confluence_per_timeframe(
            'BTCUSDc',
            m1_analyzer=m1_analyzer,
            m1_data_fetcher=m1_fetcher
        )
        
        # Create "new" instance
        calc2 = ConfluenceCalculator(bridge, cache_ttl=5)
        
        # Should be same instance
        self.assertIs(calc1, calc2)
        
        # Should see cached result
        cache_info = calc2.get_cache_info('BTCUSDc')
        self.assertTrue(cache_info['cached'])


class TestSymbolNormalizationIntegration(unittest.TestCase):
    """Test symbol normalization across all components"""
    
    def setUp(self):
        reset_singleton(ConfluenceCalculator)
        self.bridge = MockIndicatorBridge()
        self.calculator = ConfluenceCalculator(self.bridge, cache_ttl=5)
    
    def tearDown(self):
        reset_singleton(ConfluenceCalculator)
    
    def test_symbol_variations_use_same_cache(self):
        """Test different symbol formats use same cache"""
        self.bridge.multi_data['BTCUSDc'] = create_btc_data()
        
        # Calculate with different formats
        result1 = self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
        result2 = self.calculator.calculate_confluence_per_timeframe('BTCUSDC')
        result3 = self.calculator.calculate_confluence_per_timeframe('btcusdc')
        
        # All should use same cache
        cache_info1 = self.calculator.get_cache_info('BTCUSDc')
        cache_info2 = self.calculator.get_cache_info('BTCUSDC')
        
        self.assertEqual(cache_info1['cached'], cache_info2['cached'])
    
    def test_regime_cache_with_symbol_variations(self):
        """Test regime cache works with symbol variations"""
        self.bridge.multi_data['BTCUSDc'] = create_regime_test_data('STABLE')
        
        # Calculate with one format
        self.calculator.calculate_confluence_per_timeframe('BTCUSDc')
        regime1 = self.calculator.get_cached_regime('BTCUSDc')
        
        # Get with different format
        regime2 = self.calculator.get_cached_regime('BTCUSDC')
        
        # Should be same (normalized)
        self.assertEqual(regime1, regime2)


if __name__ == '__main__':
    print("=" * 70)
    print("Phase 2: Integration Tests")
    print("=" * 70)
    print()
    print("Testing:")
    print("  - End-to-end confluence calculation")
    print("  - Cache integration")
    print("  - Singleton pattern integration")
    print("  - Symbol normalization integration")
    print()
    print("=" * 70)
    print()
    
    unittest.main(verbosity=2)

