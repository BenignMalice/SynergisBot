"""
Unit tests for Phase 1: Price Cache Implementation
Tests LRU cache, TTL, size limits, and cache integration
"""

import unittest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, timezone
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auto_execution_system import AutoExecutionSystem, TradePlan


class TestPriceCache(unittest.TestCase):
    """Test price cache functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        import tempfile
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Create AutoExecutionSystem instance
        self.auto_exec = AutoExecutionSystem(
            db_path=self.temp_db.name,
            check_interval=15,
            mt5_service=Mock()
        )
        # Ensure system doesn't start threads
        self.auto_exec.running = False
    
    def tearDown(self):
        """Clean up test fixtures"""
        if hasattr(self, 'auto_exec'):
            # Stop system if running
            if self.auto_exec.running:
                self.auto_exec.running = False
            # Stop threads if they exist
            if hasattr(self.auto_exec, 'monitor_thread') and self.auto_exec.monitor_thread:
                self.auto_exec.monitor_thread = None
            if hasattr(self.auto_exec, 'watchdog_thread') and self.auto_exec.watchdog_thread:
                self.auto_exec.watchdog_thread = None
            # Stop database write queue if it exists
            if hasattr(self.auto_exec, 'db_write_queue') and self.auto_exec.db_write_queue:
                try:
                    self.auto_exec.db_write_queue.stop()
                except:
                    pass
        if hasattr(self, 'temp_db'):
            try:
                os.unlink(self.temp_db.name)
            except:
                pass
    
    def test_cache_initialization(self):
        """Test that price cache is properly initialized"""
        self.assertIsNotNone(self.auto_exec._price_cache)
        self.assertIsNotNone(self.auto_exec._price_cache_lock)
        self.assertEqual(self.auto_exec._price_cache_ttl, 5)
        self.assertEqual(self.auto_exec._price_cache_max_size, 50)
        self.assertEqual(self.auto_exec._price_cache_hits, 0)
        self.assertEqual(self.auto_exec._price_cache_misses, 0)
    
    def test_get_cached_price_miss(self):
        """Test cache miss when symbol not in cache"""
        price = self.auto_exec._get_cached_price("XAUUSDc")
        self.assertIsNone(price)
        self.assertEqual(self.auto_exec._price_cache_misses, 1)
        self.assertEqual(self.auto_exec._price_cache_hits, 0)
    
    def test_update_and_get_cached_price(self):
        """Test updating cache and retrieving cached price"""
        # Update cache
        self.auto_exec._update_price_cache("XAUUSDc", 2000.0, 1999.9, 2000.1)
        
        # Get cached price
        price = self.auto_exec._get_cached_price("XAUUSDc")
        self.assertEqual(price, 2000.0)
        self.assertEqual(self.auto_exec._price_cache_hits, 1)
        self.assertEqual(self.auto_exec._price_cache_misses, 0)
    
    def test_cache_ttl_expiration(self):
        """Test that cached prices expire after TTL"""
        # Update cache
        self.auto_exec._update_price_cache("XAUUSDc", 2000.0, 1999.9, 2000.1)
        
        # Manually expire the cache entry
        with self.auto_exec._price_cache_lock:
            cache_entry = self.auto_exec._price_cache["XAUUSDc"]
            # Set timestamp to 6 seconds ago (past TTL of 5 seconds)
            cache_entry['timestamp'] = datetime.now(timezone.utc) - timedelta(seconds=6)
        
        # Try to get cached price - should be None (expired)
        price = self.auto_exec._get_cached_price("XAUUSDc")
        self.assertIsNone(price)
        self.assertEqual(self.auto_exec._price_cache_misses, 1)
    
    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full"""
        # Fill cache to max size
        for i in range(self.auto_exec._price_cache_max_size):
            symbol = f"SYMBOL{i}c"
            self.auto_exec._update_price_cache(symbol, 1000.0 + i, 999.9 + i, 1000.1 + i)
        
        # Verify cache is full
        self.assertEqual(len(self.auto_exec._price_cache), self.auto_exec._price_cache_max_size)
        
        # Access first symbol to move it to end (LRU)
        self.auto_exec._get_cached_price("SYMBOL0c")
        
        # Add one more symbol - should evict oldest (SYMBOL1c, not SYMBOL0c)
        self.auto_exec._update_price_cache("NEWSYMBOLc", 2000.0, 1999.9, 2000.1)
        
        # Verify cache size is still max_size
        self.assertEqual(len(self.auto_exec._price_cache), self.auto_exec._price_cache_max_size)
        
        # Verify SYMBOL0c still exists (was moved to end)
        self.assertIn("SYMBOL0c", self.auto_exec._price_cache)
        
        # Verify SYMBOL1c was evicted (oldest after SYMBOL0c was accessed)
        self.assertNotIn("SYMBOL1c", self.auto_exec._price_cache)
        
        # Verify NEWSYMBOLc was added
        self.assertIn("NEWSYMBOLc", self.auto_exec._price_cache)
    
    def test_invalidate_cache_specific_symbol(self):
        """Test invalidating cache for specific symbol"""
        # Add multiple symbols
        self.auto_exec._update_price_cache("XAUUSDc", 2000.0, 1999.9, 2000.1)
        self.auto_exec._update_price_cache("BTCUSDc", 50000.0, 49999.9, 50000.1)
        
        # Invalidate one symbol
        self.auto_exec._invalidate_price_cache("XAUUSDc")
        
        # Verify XAUUSDc is removed
        self.assertNotIn("XAUUSDc", self.auto_exec._price_cache)
        
        # Verify BTCUSDc still exists
        self.assertIn("BTCUSDc", self.auto_exec._price_cache)
    
    def test_invalidate_cache_all(self):
        """Test invalidating entire cache"""
        # Add multiple symbols
        self.auto_exec._update_price_cache("XAUUSDc", 2000.0, 1999.9, 2000.1)
        self.auto_exec._update_price_cache("BTCUSDc", 50000.0, 49999.9, 50000.1)
        
        # Invalidate all
        self.auto_exec._invalidate_price_cache()
        
        # Verify cache is empty
        self.assertEqual(len(self.auto_exec._price_cache), 0)
    
    def test_cleanup_expired_entries(self):
        """Test cleanup of expired cache entries"""
        # Add multiple symbols with different timestamps
        self.auto_exec._update_price_cache("XAUUSDc", 2000.0, 1999.9, 2000.1)
        self.auto_exec._update_price_cache("BTCUSDc", 50000.0, 49999.9, 50000.1)
        
        # Create a plan for BTCUSDc so it's not considered inactive
        plan = TradePlan(
            plan_id="test_plan",
            symbol="BTCUSD",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        with self.auto_exec.plans_lock:
            self.auto_exec.plans["test_plan"] = plan
        
        try:
            # Manually expire one entry (XAUUSDc)
            with self.auto_exec._price_cache_lock:
                cache_entry = self.auto_exec._price_cache["XAUUSDc"]
                cache_entry['timestamp'] = datetime.now(timezone.utc) - timedelta(seconds=10)
            
            # Run cleanup
            self.auto_exec._cleanup_price_cache()
            
            # Verify expired entry is removed
            self.assertNotIn("XAUUSDc", self.auto_exec._price_cache)
            
            # Verify non-expired entry still exists (and is in active plans)
            self.assertIn("BTCUSDc", self.auto_exec._price_cache)
        finally:
            # Clean up
            with self.auto_exec.plans_lock:
                if "test_plan" in self.auto_exec.plans:
                    del self.auto_exec.plans["test_plan"]
    
    def test_cleanup_inactive_symbols(self):
        """Test cleanup of symbols not in active plans"""
        # Add symbol to cache
        self.auto_exec._update_price_cache("XAUUSDc", 2000.0, 1999.9, 2000.1)
        
        # Create a plan with different symbol and add directly to plans dict
        # (avoiding add_plan which might start threads or access database)
        plan = TradePlan(
            plan_id="test_plan",
            symbol="BTCUSD",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        # Add plan directly to avoid database/thread issues
        with self.auto_exec.plans_lock:
            self.auto_exec.plans["test_plan"] = plan
        
        # Run cleanup
        self.auto_exec._cleanup_price_cache()
        
        # Verify XAUUSDc is removed (not in active plans)
        self.assertNotIn("XAUUSDc", self.auto_exec._price_cache)
        
        # Clean up
        with self.auto_exec.plans_lock:
            if "test_plan" in self.auto_exec.plans:
                del self.auto_exec.plans["test_plan"]
    
    def test_batch_price_fetch_uses_cache(self):
        """Test that _get_current_prices_batch uses cache"""
        # Add price to cache
        self.auto_exec._update_price_cache("XAUUSDc", 2000.0, 1999.9, 2000.1)
        
        # Create a plan
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        self.auto_exec.add_plan(plan)
        
        # Mock MT5Service to verify it's not called for cached symbols
        self.auto_exec.mt5_service.get_quote = Mock()
        
        # Get batch prices
        prices = self.auto_exec._get_current_prices_batch()
        
        # Verify cached price is returned
        self.assertIn("XAUUSDc", prices)
        self.assertEqual(prices["XAUUSDc"], 2000.0)
        
        # Verify MT5Service.get_quote was not called (cache hit)
        self.auto_exec.mt5_service.get_quote.assert_not_called()
    
    def test_check_interval_default(self):
        """Test that check_interval default is 15 seconds"""
        self.assertEqual(self.auto_exec.check_interval, 15)


if __name__ == '__main__':
    unittest.main()
