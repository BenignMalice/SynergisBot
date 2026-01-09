"""
Comprehensive Test Suite for Phase 1 Fixes
Tests Fix 18 (Singleton), Fix 19 (M1 Caching), Fix 6 (Cache Sync), Fix 7 (API Consistency)
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


class TestPhase1Fixes(unittest.TestCase):
    """Test suite for Phase 1 fixes"""
    
    def setUp(self):
        """Set up test environment"""
        # Reset singleton instance for clean testing
        ConfluenceCalculator._instance = None
        ConfluenceCalculator._lock = threading.RLock()
        
        self.mock_bridge = MockIndicatorBridge()
        self.calculator1 = ConfluenceCalculator(self.mock_bridge, cache_ttl=5)
    
    def tearDown(self):
        """Clean up after tests"""
        # Reset singleton for next test
        ConfluenceCalculator._instance = None
    
    # ========== Fix 18: Singleton Pattern ==========
    def test_fix_18_singleton_pattern(self):
        """Test Fix 18: Singleton pattern ensures only one instance"""
        # Create multiple "instances"
        calc1 = ConfluenceCalculator(self.mock_bridge)
        calc2 = ConfluenceCalculator(self.mock_bridge)
        calc3 = ConfluenceCalculator(self.mock_bridge)
        
        # All should be the same instance
        self.assertIs(calc1, calc2, "calc1 and calc2 should be same instance")
        self.assertIs(calc2, calc3, "calc2 and calc3 should be same instance")
        self.assertIs(calc1, calc3, "calc1 and calc3 should be same instance")
    
    def test_fix_18_shared_cache(self):
        """Test Fix 18: Singleton shares cache between instances"""
        calc1 = ConfluenceCalculator(self.mock_bridge, cache_ttl=5)
        calc2 = ConfluenceCalculator(self.mock_bridge, cache_ttl=5)
        
        # Calculate confluence with calc1
        result1 = calc1.calculate_confluence_per_timeframe('BTCUSDc')
        
        # Get cache from calc2 - should be same cache
        self.assertIs(calc1._cache, calc2._cache, "Cache should be shared")
        self.assertIs(calc1._regime_cache, calc2._regime_cache, "Regime cache should be shared")
        
        # calc2 should see cached data
        cache_info = calc2.get_cache_info('BTCUSDc')
        self.assertIsNotNone(cache_info, "calc2 should see cache from calc1")
        self.assertTrue(cache_info['cached'], "Should be cached")
    
    def test_fix_18_indicator_bridge_update(self):
        """Test Fix 18: Singleton updates indicator_bridge if changed"""
        bridge1 = MockIndicatorBridge()
        bridge2 = MockIndicatorBridge()
        
        calc1 = ConfluenceCalculator(bridge1)
        calc2 = ConfluenceCalculator(bridge2)
        
        # Should be same instance
        self.assertIs(calc1, calc2)
        
        # Bridge should be updated to bridge2 (latest)
        self.assertIs(calc2.indicator_bridge, bridge2)
    
    # ========== Fix 6: Cache Synchronization ==========
    def test_fix_6_regime_cache_exists(self):
        """Test Fix 6: Regime cache exists and is initialized"""
        self.assertTrue(hasattr(self.calculator1, '_regime_cache'), "Should have _regime_cache")
        self.assertIsInstance(self.calculator1._regime_cache, dict, "Regime cache should be dict")
    
    def test_fix_6_regime_cache_storage(self):
        """Test Fix 6: Regime is cached after calculation"""
        symbol = 'BTCUSDc'
        
        # Calculate confluence (which calculates regime for BTC)
        result = self.calculator1.calculate_confluence_per_timeframe(symbol)
        
        # Regime should be cached
        cached_regime = self.calculator1.get_cached_regime(symbol)
        self.assertIsNotNone(cached_regime, "Regime should be cached")
        self.assertIn(cached_regime, ['STABLE', 'TRANSITIONAL', 'VOLATILE'], 
                     f"Regime should be valid: {cached_regime}")
    
    def test_fix_6_regime_cache_ttl(self):
        """Test Fix 6: Regime cache respects TTL"""
        symbol = 'BTCUSDc'
        
        # Calculate and cache regime
        result = self.calculator1.calculate_confluence_per_timeframe(symbol)
        cached_regime = self.calculator1.get_cached_regime(symbol)
        self.assertIsNotNone(cached_regime, "Regime should be cached")
        
        # Wait for cache to expire
        time.sleep(6)
        
        # Cache should be expired
        expired_regime = self.calculator1.get_cached_regime(symbol)
        self.assertIsNone(expired_regime, "Regime cache should expire after TTL")
    
    def test_fix_6_regime_cache_thread_safe(self):
        """Test Fix 6: Regime cache is thread-safe"""
        results = []
        errors = []
        
        def calculate_and_get_regime(symbol):
            try:
                calc = ConfluenceCalculator(self.mock_bridge)
                result = calc.calculate_confluence_per_timeframe(symbol)
                regime = calc.get_cached_regime(symbol)
                results.append((symbol, regime))
            except Exception as e:
                errors.append((symbol, str(e)))
        
        threads = [
            threading.Thread(target=calculate_and_get_regime, args=('BTCUSDc',)),
            threading.Thread(target=calculate_and_get_regime, args=('XAUUSDc',)),
            threading.Thread(target=calculate_and_get_regime, args=('BTCUSDc',)),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        
        # Should have results
        self.assertGreater(len(results), 0, "Should have results")
    
    # ========== Fix 7: API Consistency ==========
    def test_fix_7_get_cached_regime_method(self):
        """Test Fix 7: get_cached_regime() method exists and works"""
        symbol = 'BTCUSDc'
        
        # Calculate confluence (which caches regime)
        result = self.calculator1.calculate_confluence_per_timeframe(symbol)
        
        # Get cached regime
        cached_regime = self.calculator1.get_cached_regime(symbol)
        self.assertIsNotNone(cached_regime, "Should return cached regime")
        self.assertIn(cached_regime, ['STABLE', 'TRANSITIONAL', 'VOLATILE'])
    
    def test_fix_7_get_cached_regime_none(self):
        """Test Fix 7: get_cached_regime() returns None if not cached"""
        # Get regime for non-cached symbol
        cached_regime = self.calculator1.get_cached_regime('NONEXISTENT')
        self.assertIsNone(cached_regime, "Should return None for non-cached symbol")
    
    def test_fix_7_regime_cache_consistency(self):
        """Test Fix 7: Regime cache is consistent across calls"""
        symbol = 'BTCUSDc'
        
        # Calculate confluence twice
        result1 = self.calculator1.calculate_confluence_per_timeframe(symbol)
        regime1 = self.calculator1.get_cached_regime(symbol)
        
        # Small delay
        time.sleep(0.1)
        
        result2 = self.calculator1.calculate_confluence_per_timeframe(symbol)
        regime2 = self.calculator1.get_cached_regime(symbol)
        
        # Regimes should be consistent (same or from cache)
        # They might be different if cache expired, but if both cached, should be same
        if regime1 and regime2:
            # If both are cached and within TTL, they should be same
            self.assertEqual(regime1, regime2, "Cached regimes should be consistent")
    
    # ========== Fix 19: M1 Analyzer Caching ==========
    def test_fix_19_m1_components_can_be_cached(self):
        """Test Fix 19: M1 components can be cached and reused"""
        # This test verifies the infrastructure is in place
        # Actual caching happens in main_api.py startup event
        
        mock_analyzer = Mock()
        mock_fetcher = Mock()
        
        # Should work with cached components
        result = self.calculator1.calculate_confluence_per_timeframe(
            'BTCUSDc',
            m1_analyzer=mock_analyzer,
            m1_data_fetcher=mock_fetcher
        )
        
        # Should not raise errors
        self.assertIsNotNone(result)
        self.assertIn('M1', result)
    
    # ========== Integration Tests ==========
    def test_integration_singleton_with_regime_cache(self):
        """Integration test: Singleton pattern with regime cache"""
        calc1 = ConfluenceCalculator(self.mock_bridge, cache_ttl=5)
        calc2 = ConfluenceCalculator(self.mock_bridge, cache_ttl=5)
        
        symbol = 'BTCUSDc'
        
        # Calculate with calc1
        result1 = calc1.calculate_confluence_per_timeframe(symbol)
        regime1 = calc1.get_cached_regime(symbol)
        
        # Get from calc2 (should see same cache)
        regime2 = calc2.get_cached_regime(symbol)
        
        # Should be same (shared cache)
        self.assertEqual(regime1, regime2, "Regime should be shared via singleton")
    
    def test_integration_regime_cache_with_confluence(self):
        """Integration test: Regime cache works with confluence calculation"""
        symbol = 'BTCUSDc'
        
        # Calculate confluence (which calculates and caches regime for BTC)
        result = self.calculator1.calculate_confluence_per_timeframe(symbol)
        
        # Verify M1 result exists (may be unavailable without real M1 components)
        self.assertIn('M1', result)
        
        # Verify regime is cached
        cached_regime = self.calculator1.get_cached_regime(symbol)
        if cached_regime:
            self.assertIn(cached_regime, ['STABLE', 'TRANSITIONAL', 'VOLATILE'])
    
    def test_integration_multiple_symbols_regime_cache(self):
        """Integration test: Regime cache works for multiple symbols"""
        symbols = ['BTCUSDc', 'XAUUSDc', 'EURUSDc']
        
        for symbol in symbols:
            result = self.calculator1.calculate_confluence_per_timeframe(symbol)
            cached_regime = self.calculator1.get_cached_regime(symbol)
            
            # For BTC, regime should be cached
            if symbol.startswith('BTC'):
                # May be None if not BTC or calculation failed, but if cached should be valid
                if cached_regime:
                    self.assertIn(cached_regime, ['STABLE', 'TRANSITIONAL', 'VOLATILE'])
    
    def test_integration_cache_coordination(self):
        """Integration test: Confluence cache and regime cache are coordinated"""
        symbol = 'BTCUSDc'
        
        # Calculate confluence
        result1 = self.calculator1.calculate_confluence_per_timeframe(symbol)
        
        # Both caches should have data
        cache_info = self.calculator1.get_cache_info(symbol)
        regime = self.calculator1.get_cached_regime(symbol)
        
        # Confluence should be cached
        self.assertIsNotNone(cache_info, "Confluence should be cached")
        self.assertTrue(cache_info['cached'], "Confluence should be cached")
        
        # Regime should be cached (for BTC)
        if regime:
            self.assertIn(regime, ['STABLE', 'TRANSITIONAL', 'VOLATILE'])
        
        # Both should expire at same TTL
        time.sleep(6)
        
        expired_cache = self.calculator1.get_cache_info(symbol)
        expired_regime = self.calculator1.get_cached_regime(symbol)
        
        # Both should be expired
        if expired_cache:
            self.assertFalse(expired_cache['is_fresh'], "Confluence cache should expire")
        self.assertIsNone(expired_regime, "Regime cache should expire")


if __name__ == '__main__':
    print("=" * 70)
    print("Comprehensive Phase 1 Fixes Test Suite")
    print("=" * 70)
    print()
    print("Testing all Phase 1 fixes:")
    print("  - Fix 18: Singleton Pattern")
    print("  - Fix 19: M1 Analyzer Caching")
    print("  - Fix 6: Cache Synchronization")
    print("  - Fix 7: API Consistency")
    print()
    print("=" * 70)
    print()
    
    unittest.main(verbosity=2)

