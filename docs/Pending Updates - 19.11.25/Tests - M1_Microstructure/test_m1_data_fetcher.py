# =====================================
# tests/test_m1_data_fetcher.py
# =====================================
"""
Tests for M1 Data Fetcher Module (Phase 1.1)
"""

import unittest
import time
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add project root to path (adjust for new location in docs folder)
# From: docs/Pending Updates - 19.11.25/Tests - M1_Microstructure/
# To: project root (3 levels up: .. -> .. -> ..)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.m1_data_fetcher import M1DataFetcher


class MockMT5Service:
    """Mock MT5Service for testing"""
    
    def __init__(self):
        self.connected = True
    
    def get_bars(self, symbol, timeframe, count):
        """Mock get_bars method"""
        if timeframe != 'M1':
            return None
        
        # Generate mock M1 candles
        candles = []
        base_price = 2400.0 if 'XAU' in symbol else 50000.0
        base_time = int(time.time()) - (count * 60)  # Start count minutes ago
        
        for i in range(count):
            candle = {
                'time': base_time + (i * 60),
                'open': base_price + (i * 0.1),
                'high': base_price + (i * 0.1) + 0.5,
                'low': base_price + (i * 0.1) - 0.5,
                'close': base_price + (i * 0.1) + 0.2,
                'tick_volume': 100 + i,
                'real_volume': 50 + i
            }
            candles.append(candle)
        
        # Return as list of dicts (simulating pandas DataFrame conversion)
        return candles


class TestM1DataFetcher(unittest.TestCase):
    """Test cases for M1DataFetcher"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_mt5 = MockMT5Service()
        self.fetcher = M1DataFetcher(
            data_source=self.mock_mt5,
            max_candles=200,
            cache_ttl=300
        )
    
    def test_initialization(self):
        """Test M1DataFetcher initialization"""
        self.assertIsNotNone(self.fetcher)
        self.assertEqual(self.fetcher.max_candles, 200)
        self.assertEqual(self.fetcher.cache_ttl, 300)
        self.assertEqual(self.fetcher.data_source, self.mock_mt5)
    
    def test_symbol_normalization(self):
        """Test symbol normalization (adds 'c' suffix)"""
        normalized = self.fetcher._normalize_symbol("XAUUSD")
        self.assertEqual(normalized, "XAUUSDc")
        
        normalized2 = self.fetcher._normalize_symbol("XAUUSDc")
        self.assertEqual(normalized2, "XAUUSDc")
    
    def test_fetch_m1_data_basic(self):
        """Test basic M1 data fetching"""
        candles = self.fetcher.fetch_m1_data("XAUUSD", count=50)
        
        self.assertIsInstance(candles, list)
        self.assertGreater(len(candles), 0)
        self.assertLessEqual(len(candles), 50)
        
        # Check candle structure
        if candles:
            candle = candles[0]
            self.assertIn('timestamp', candle)
            self.assertIn('open', candle)
            self.assertIn('high', candle)
            self.assertIn('low', candle)
            self.assertIn('close', candle)
            self.assertIn('volume', candle)
            self.assertIn('symbol', candle)
            self.assertEqual(candle['symbol'], 'XAUUSDc')
    
    def test_fetch_m1_data_caching(self):
        """Test M1 data caching"""
        # First fetch
        candles1 = self.fetcher.fetch_m1_data("XAUUSD", count=50, use_cache=True)
        first_fetch_time = self.fetcher._last_fetch_time.get("XAUUSDc")
        
        # Second fetch (should use cache if within TTL)
        time.sleep(0.1)  # Small delay
        candles2 = self.fetcher.fetch_m1_data("XAUUSD", count=50, use_cache=True)
        second_fetch_time = self.fetcher._last_fetch_time.get("XAUUSDc")
        
        # Should have same number of candles
        self.assertEqual(len(candles1), len(candles2))
        
        # Cache should be used (same fetch time if within TTL)
        if time.time() - first_fetch_time < self.fetcher.cache_ttl:
            self.assertEqual(first_fetch_time, second_fetch_time)
    
    def test_fetch_m1_data_no_cache(self):
        """Test M1 data fetching without cache"""
        candles1 = self.fetcher.fetch_m1_data("XAUUSD", count=50, use_cache=False)
        time.sleep(0.1)
        candles2 = self.fetcher.fetch_m1_data("XAUUSD", count=50, use_cache=False)
        
        # Both should fetch fresh data
        self.assertIsInstance(candles1, list)
        self.assertIsInstance(candles2, list)
    
    def test_get_latest_m1(self):
        """Test getting latest M1 candle"""
        # Fetch some data first
        self.fetcher.fetch_m1_data("XAUUSD", count=50)
        
        latest = self.fetcher.get_latest_m1("XAUUSD")
        
        self.assertIsNotNone(latest)
        self.assertIn('close', latest)
        self.assertIn('timestamp', latest)
        self.assertEqual(latest['symbol'], 'XAUUSDc')
    
    def test_refresh_symbol(self):
        """Test symbol refresh"""
        # Fetch initial data
        self.fetcher.fetch_m1_data("XAUUSD", count=50)
        
        # Refresh
        result = self.fetcher.refresh_symbol("XAUUSD")
        
        self.assertTrue(result)
        
        # Verify cache was cleared and refetched
        candles = self.fetcher.fetch_m1_data("XAUUSD", count=50, use_cache=True)
        self.assertGreater(len(candles), 0)
    
    def test_force_refresh(self):
        """Test force refresh"""
        # Fetch initial data
        self.fetcher.fetch_m1_data("XAUUSD", count=50)
        
        # Force refresh
        result = self.fetcher.force_refresh("XAUUSD")
        
        self.assertTrue(result)
    
    def test_get_data_age(self):
        """Test getting data age"""
        # Fetch data
        self.fetcher.fetch_m1_data("XAUUSD", count=50)
        
        # Get age
        age = self.fetcher.get_data_age("XAUUSD")
        
        self.assertIsNotNone(age)
        self.assertGreaterEqual(age, 0)
        self.assertLess(age, 10)  # Should be very recent
    
    def test_get_all_symbols(self):
        """Test getting all cached symbols"""
        # Fetch data for multiple symbols
        self.fetcher.fetch_m1_data("XAUUSD", count=50)
        self.fetcher.fetch_m1_data("BTCUSD", count=50)
        
        symbols = self.fetcher.get_all_symbols()
        
        self.assertIn("XAUUSDc", symbols)
        self.assertIn("BTCUSDc", symbols)
    
    def test_is_data_stale(self):
        """Test data staleness check"""
        # Fetch fresh data
        self.fetcher.fetch_m1_data("XAUUSD", count=50)
        
        # Should not be stale
        is_stale = self.fetcher.is_data_stale("XAUUSD", max_age_seconds=180)
        self.assertFalse(is_stale)
        
        # Check with very short max age (should be stale)
        is_stale_short = self.fetcher.is_data_stale("XAUUSD", max_age_seconds=0.001)
        # May or may not be stale depending on timing, but should not crash
    
    def test_clear_cache_symbol(self):
        """Test clearing cache for specific symbol"""
        # Fetch data for multiple symbols
        self.fetcher.fetch_m1_data("XAUUSD", count=50)
        self.fetcher.fetch_m1_data("BTCUSD", count=50)
        
        # Clear cache for one symbol
        self.fetcher.clear_cache("XAUUSD")
        
        # XAUUSD should be cleared, BTCUSD should remain
        symbols = self.fetcher.get_all_symbols()
        self.assertNotIn("XAUUSDc", symbols)
        self.assertIn("BTCUSDc", symbols)
    
    def test_clear_cache_all(self):
        """Test clearing all cache"""
        # Fetch data for multiple symbols
        self.fetcher.fetch_m1_data("XAUUSD", count=50)
        self.fetcher.fetch_m1_data("BTCUSD", count=50)
        
        # Clear all cache
        self.fetcher.clear_cache()
        
        # All symbols should be cleared
        symbols = self.fetcher.get_all_symbols()
        self.assertEqual(len(symbols), 0)
    
    def test_max_candles_limit(self):
        """Test max candles limit"""
        # Request more than max_candles
        candles = self.fetcher.fetch_m1_data("XAUUSD", count=500)
        
        # Should be limited to max_candles
        self.assertLessEqual(len(candles), self.fetcher.max_candles)
    
    def test_fetch_m1_data_async(self):
        """Test async fetch method"""
        import asyncio
        
        async def test_async():
            candles = await self.fetcher.fetch_m1_data_async("XAUUSD", count=50)
            return candles
        
        # Run async test
        candles = asyncio.run(test_async())
        
        self.assertIsInstance(candles, list)
        self.assertGreater(len(candles), 0)
    
    def test_error_handling_invalid_symbol(self):
        """Test error handling for invalid symbol"""
        # Mock service to return None
        mock_service = Mock()
        mock_service.get_bars = Mock(return_value=None)
        
        fetcher = M1DataFetcher(data_source=mock_service)
        candles = fetcher.fetch_m1_data("INVALID", count=50)
        
        # Should return empty list, not crash
        self.assertIsInstance(candles, list)
    
    def test_convert_to_dict(self):
        """Test candle data conversion"""
        # Test with dict input
        candle_dict = {
            'time': datetime.now(timezone.utc),
            'open': 2400.0,
            'high': 2401.0,
            'low': 2399.0,
            'close': 2400.5,
            'volume': 100
        }
        
        converted = self.fetcher._convert_to_dict(candle_dict, "XAUUSD")
        
        self.assertIn('timestamp', converted)
        self.assertEqual(converted['open'], 2400.0)
        self.assertEqual(converted['symbol'], 'XAUUSDc')


if __name__ == '__main__':
    unittest.main()

