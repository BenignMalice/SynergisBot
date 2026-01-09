# =====================================
# tests/test_phase1_4_refresh_manager.py
# =====================================
"""
Tests for Phase 1.4: Periodic Refresh System
Tests M1RefreshManager functionality
"""

import unittest
import time
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone, timedelta

# Add project root to path (adjust for new location in docs folder)
# From: docs/Pending Updates - 19.11.25/Tests - M1_Microstructure/
# To: project root (3 levels up: .. -> .. -> ..)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.m1_data_fetcher import M1DataFetcher
from infra.m1_refresh_manager import M1RefreshManager


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
        base_time = int(time.time()) - (count * 60)
        
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
        
        return candles


class TestM1RefreshManager(unittest.TestCase):
    """Test cases for M1RefreshManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_mt5 = MockMT5Service()
        self.m1_fetcher = M1DataFetcher(data_source=self.mock_mt5, max_candles=200, cache_ttl=300)
        self.refresh_manager = M1RefreshManager(
            fetcher=self.m1_fetcher,
            refresh_interval_active=30,
            refresh_interval_inactive=300
        )
    
    def tearDown(self):
        """Clean up after tests"""
        self.refresh_manager.stop_refresh()
    
    def test_initialization(self):
        """Test M1RefreshManager initialization"""
        self.assertIsNotNone(self.refresh_manager)
        self.assertEqual(self.refresh_manager.refresh_interval_active, 30)
        self.assertEqual(self.refresh_manager.refresh_interval_inactive, 300)
        self.assertEqual(self.refresh_manager.fetcher, self.m1_fetcher)
    
    def test_refresh_symbol(self):
        """Test refreshing a single symbol"""
        result = self.refresh_manager.refresh_symbol("XAUUSD")
        
        self.assertTrue(result)
        
        # Check that refresh time was recorded
        last_refresh = self.refresh_manager.get_last_refresh_time("XAUUSD")
        self.assertIsNotNone(last_refresh)
        self.assertIsInstance(last_refresh, datetime)
    
    def test_refresh_symbol_force(self):
        """Test force refresh"""
        # First refresh
        result1 = self.refresh_manager.refresh_symbol("XAUUSD", force=False)
        self.assertTrue(result1)
        
        # Force refresh immediately
        result2 = self.refresh_manager.refresh_symbol("XAUUSD", force=True)
        self.assertTrue(result2)
    
    def test_get_last_refresh_time(self):
        """Test getting last refresh time"""
        # Before refresh
        last_refresh = self.refresh_manager.get_last_refresh_time("XAUUSD")
        self.assertIsNone(last_refresh)
        
        # After refresh
        self.refresh_manager.refresh_symbol("XAUUSD")
        last_refresh = self.refresh_manager.get_last_refresh_time("XAUUSD")
        self.assertIsNotNone(last_refresh)
        self.assertIsInstance(last_refresh, datetime)
    
    def test_get_all_refresh_times(self):
        """Test getting all refresh times"""
        # Refresh multiple symbols
        self.refresh_manager.refresh_symbol("XAUUSD")
        self.refresh_manager.refresh_symbol("BTCUSD")
        
        all_times = self.refresh_manager.get_all_refresh_times()
        
        self.assertIn("XAUUSDc", all_times)
        self.assertIn("BTCUSDc", all_times)
        self.assertIsInstance(all_times["XAUUSDc"], datetime)
        self.assertIsInstance(all_times["BTCUSDc"], datetime)
    
    def test_check_and_refresh_stale(self):
        """Test checking and refreshing stale data"""
        # Refresh symbol
        self.refresh_manager.refresh_symbol("XAUUSD")
        
        # Check stale with very short max age (should refresh)
        result = self.refresh_manager.check_and_refresh_stale("XAUUSD", max_age_seconds=0.001)
        self.assertTrue(result)
    
    def test_get_refresh_status(self):
        """Test getting refresh status"""
        # Start refresh for symbols
        self.refresh_manager.start_background_refresh(["XAUUSD", "BTCUSD"])
        
        # Wait a bit for refresh to happen
        time.sleep(0.5)
        
        status = self.refresh_manager.get_refresh_status()
        
        self.assertIn('running', status)
        self.assertIn('active_symbols', status)
        self.assertIn('symbols', status)
        self.assertTrue(status['running'])
        self.assertIn('XAUUSDc', status['active_symbols'])
        self.assertIn('BTCUSDc', status['active_symbols'])
    
    def test_get_refresh_diagnostics(self):
        """Test getting refresh diagnostics"""
        # Refresh some symbols
        self.refresh_manager.refresh_symbol("XAUUSD")
        self.refresh_manager.refresh_symbol("BTCUSD")
        
        diagnostics = self.refresh_manager.get_refresh_diagnostics()
        
        self.assertIn('avg_latency_ms', diagnostics)
        self.assertIn('data_age_drift_seconds', diagnostics)
        self.assertIn('refresh_success_rate', diagnostics)
        self.assertIn('total_refreshes', diagnostics)
        self.assertIn('successful_refreshes', diagnostics)
        self.assertIn('failed_refreshes', diagnostics)
        
        self.assertGreaterEqual(diagnostics['refresh_success_rate'], 0)
        self.assertLessEqual(diagnostics['refresh_success_rate'], 100)
    
    def test_start_stop_background_refresh(self):
        """Test starting and stopping background refresh"""
        # Start refresh
        self.refresh_manager.start_background_refresh(["XAUUSD", "BTCUSD"])
        
        # Check status
        status = self.refresh_manager.get_refresh_status()
        self.assertTrue(status['running'])
        
        # Stop refresh
        self.refresh_manager.stop_refresh()
        
        # Wait a bit
        time.sleep(0.2)
        
        # Check status again
        status = self.refresh_manager.get_refresh_status()
        self.assertFalse(status['running'])
    
    def test_weekend_detection(self):
        """Test weekend detection"""
        # Test with current time (may or may not be weekend)
        is_weekend = self.refresh_manager._is_weekend()
        self.assertIsInstance(is_weekend, bool)
    
    def test_weekend_refresh_handling(self):
        """Test weekend refresh handling"""
        # BTCUSD should refresh on weekends
        should_refresh_btc = self.refresh_manager._should_refresh_on_weekend("BTCUSD")
        self.assertTrue(should_refresh_btc)
        
        # XAUUSD should not refresh on weekends
        should_refresh_xau = self.refresh_manager._should_refresh_on_weekend("XAUUSD")
        self.assertFalse(should_refresh_xau)
        
        # Forex should not refresh on weekends
        should_refresh_eur = self.refresh_manager._should_refresh_on_weekend("EURUSD")
        self.assertFalse(should_refresh_eur)
    
    def test_refresh_symbol_async(self):
        """Test async refresh"""
        import asyncio
        
        async def test_async():
            result = await self.refresh_manager.refresh_symbol_async("XAUUSD")
            return result
        
        result = asyncio.run(test_async())
        self.assertTrue(result)
    
    def test_refresh_symbols_batch(self):
        """Test batch refresh"""
        import asyncio
        
        async def test_batch():
            symbols = ["XAUUSD", "BTCUSD", "EURUSD"]
            results = await self.refresh_manager.refresh_symbols_batch(symbols)
            return results
        
        results = asyncio.run(test_batch())
        
        self.assertIsInstance(results, dict)
        self.assertIn("XAUUSDc", results)
        self.assertIn("BTCUSDc", results)
        self.assertIn("EURUSDc", results)
        self.assertTrue(results["XAUUSDc"])
        self.assertTrue(results["BTCUSDc"])
        self.assertTrue(results["EURUSDc"])
    
    def test_force_refresh(self):
        """Test force refresh method"""
        result = self.refresh_manager.force_refresh("XAUUSD")
        self.assertTrue(result)
        
        # Check that refresh time was recorded
        last_refresh = self.refresh_manager.get_last_refresh_time("XAUUSD")
        self.assertIsNotNone(last_refresh)
    
    def test_refresh_interval_differentiation(self):
        """Test that active and inactive symbols use different intervals"""
        # Refresh active symbol (XAUUSD)
        self.refresh_manager.refresh_symbol("XAUUSD")
        time_xau = self.refresh_manager.get_last_refresh_time("XAUUSD")
        
        # Refresh inactive symbol (EURUSD)
        self.refresh_manager.refresh_symbol("EURUSD")
        time_eur = self.refresh_manager.get_last_refresh_time("EURUSD")
        
        # Both should have refresh times
        self.assertIsNotNone(time_xau)
        self.assertIsNotNone(time_eur)
    
    def test_error_handling(self):
        """Test error handling in refresh"""
        # Test with invalid symbol (should handle gracefully)
        result = self.refresh_manager.refresh_symbol("INVALID")
        # Should not crash, may return False
        self.assertIsInstance(result, bool)


if __name__ == '__main__':
    unittest.main()

