"""
Unit tests for Phase 2: Enhanced Batch Price Fetching
Tests chunking, retry logic, circuit breaker, and metrics
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


class TestBatchFetching(unittest.TestCase):
    """Test batch price fetching functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        import tempfile
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Create AutoExecutionSystem instance
        self.mt5_service = Mock()
        self.auto_exec = AutoExecutionSystem(
            db_path=self.temp_db.name,
            check_interval=15,
            mt5_service=self.mt5_service
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
    
    def test_always_use_batch_fetching(self):
        """Test that batch fetching is always used when plans exist"""
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
        with self.auto_exec.plans_lock:
            self.auto_exec.plans["test_plan"] = plan
        
        # Mock MT5Service
        self.mt5_service.connect = Mock(return_value=True)
        quote_mock = Mock()
        quote_mock.bid = 2000.0
        quote_mock.ask = 2000.1
        self.mt5_service.get_quote = Mock(return_value=quote_mock)
        
        # Get batch prices
        prices = self.auto_exec._get_current_prices_batch()
        
        # Verify batch fetch was called
        self.assertIn("XAUUSDc", prices)
        self.mt5_service.get_quote.assert_called()
        
        # Clean up
        with self.auto_exec.plans_lock:
            if "test_plan" in self.auto_exec.plans:
                del self.auto_exec.plans["test_plan"]
    
    def test_chunking_logic(self):
        """Test that symbols are processed in chunks of 20"""
        # Create 25 plans to test chunking
        plans = []
        for i in range(25):
            plan = TradePlan(
                plan_id=f"test_plan_{i}",
                symbol=f"SYMBOL{i}",
                direction="BUY",
                entry_price=1000.0 + i,
                stop_loss=990.0 + i,
                take_profit=1010.0 + i,
                volume=0.01,
                conditions={},
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by="test",
                status="pending"
            )
            plans.append(plan)
        
        with self.auto_exec.plans_lock:
            for plan in plans:
                self.auto_exec.plans[plan.plan_id] = plan
        
        # Mock MT5Service
        self.mt5_service.connect = Mock(return_value=True)
        quote_mock = Mock()
        quote_mock.bid = 1000.0
        quote_mock.ask = 1000.1
        self.mt5_service.get_quote = Mock(return_value=quote_mock)
        
        # Get batch prices
        prices = self.auto_exec._get_current_prices_batch()
        
        # Verify all symbols were fetched (25 symbols = 2 chunks: 20 + 5)
        # get_quote should be called 25 times (once per symbol)
        self.assertEqual(self.mt5_service.get_quote.call_count, 25)
        
        # Clean up
        with self.auto_exec.plans_lock:
            for plan in plans:
                if plan.plan_id in self.auto_exec.plans:
                    del self.auto_exec.plans[plan.plan_id]
    
    def test_circuit_breaker_opens_after_3_failures(self):
        """Test that circuit breaker opens after 3 consecutive failures"""
        symbol = "XAUUSDc"
        
        # Mock MT5Service to fail
        self.mt5_service.connect = Mock(return_value=True)
        self.mt5_service.get_quote = Mock(side_effect=Exception("Connection error"))
        
        # Try to fetch 3 times (should all fail)
        prices = {}
        for _ in range(3):
            self.auto_exec._fetch_price_chunk([symbol], prices, max_retries=1)
        
        # Verify circuit breaker is open
        can_fetch = self.auto_exec._check_circuit_breaker_price_fetch(symbol)
        self.assertFalse(can_fetch, "Circuit breaker should be open after 3 failures")
        
        # Verify failure count
        with self.auto_exec._circuit_breaker_lock:
            cb_state = self.auto_exec._price_fetch_circuit_breakers[symbol]
            self.assertEqual(cb_state['failures'], 3)
    
    def test_circuit_breaker_resets_after_60_seconds(self):
        """Test that circuit breaker resets after 60 seconds"""
        symbol = "XAUUSDc"
        
        # Open circuit breaker
        with self.auto_exec._circuit_breaker_lock:
            self.auto_exec._price_fetch_circuit_breakers[symbol] = {
                'failures': 3,
                'last_failure': datetime.now(timezone.utc),
                'opened_at': datetime.now(timezone.utc) - timedelta(seconds=61)
            }
        
        # Check circuit breaker (should reset)
        can_fetch = self.auto_exec._check_circuit_breaker_price_fetch(symbol)
        self.assertTrue(can_fetch, "Circuit breaker should reset after 60 seconds")
        
        # Verify failure count was reset
        with self.auto_exec._circuit_breaker_lock:
            cb_state = self.auto_exec._price_fetch_circuit_breakers[symbol]
            self.assertEqual(cb_state['failures'], 0)
    
    def test_retry_logic_with_exponential_backoff(self):
        """Test retry logic with exponential backoff"""
        symbol = "XAUUSDc"
        
        # Mock MT5Service to fail twice then succeed
        self.mt5_service.connect = Mock(return_value=True)
        call_count = [0]
        def mock_get_quote(sym):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Temporary error")
            quote_mock = Mock()
            quote_mock.bid = 2000.0
            quote_mock.ask = 2000.1
            return quote_mock
        
        self.mt5_service.get_quote = Mock(side_effect=mock_get_quote)
        
        # Fetch with retries
        prices = {}
        start_time = time.time()
        self.auto_exec._fetch_price_chunk([symbol], prices, max_retries=3)
        elapsed = time.time() - start_time
        
        # Verify price was fetched after retries
        self.assertIn(symbol, prices)
        self.assertEqual(prices[symbol], 2000.05)
        
        # Verify exponential backoff was used (should wait ~2 + 4 = 6 seconds)
        self.assertGreater(elapsed, 5.0, "Should have waited for exponential backoff")
        self.assertLess(elapsed, 10.0, "Should not wait too long")
    
    def test_metrics_tracking(self):
        """Test that batch fetch metrics are tracked"""
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
        with self.auto_exec.plans_lock:
            self.auto_exec.plans["test_plan"] = plan
        
        # Mock MT5Service
        self.mt5_service.connect = Mock(return_value=True)
        quote_mock = Mock()
        quote_mock.bid = 2000.0
        quote_mock.ask = 2000.1
        self.mt5_service.get_quote = Mock(return_value=quote_mock)
        
        # Get batch prices
        initial_total = self.auto_exec._batch_fetch_total
        initial_api_calls = self.auto_exec._batch_fetch_api_calls
        
        prices = self.auto_exec._get_current_prices_batch()
        
        # Verify metrics were updated
        self.assertEqual(self.auto_exec._batch_fetch_total, initial_total + 1)
        self.assertGreater(self.auto_exec._batch_fetch_api_calls, initial_api_calls)
        
        # Clean up
        with self.auto_exec.plans_lock:
            if "test_plan" in self.auto_exec.plans:
                del self.auto_exec.plans["test_plan"]
    
    def test_circuit_breaker_success_resets_failures(self):
        """Test that successful fetch resets circuit breaker failures"""
        symbol = "XAUUSDc"
        
        # Set up circuit breaker with 2 failures
        with self.auto_exec._circuit_breaker_lock:
            self.auto_exec._price_fetch_circuit_breakers[symbol] = {
                'failures': 2,
                'last_failure': datetime.now(timezone.utc),
                'opened_at': None
            }
        
        # Mock successful fetch
        self.mt5_service.connect = Mock(return_value=True)
        quote_mock = Mock()
        quote_mock.bid = 2000.0
        quote_mock.ask = 2000.1
        self.mt5_service.get_quote = Mock(return_value=quote_mock)
        
        # Fetch price
        prices = {}
        self.auto_exec._fetch_price_chunk([symbol], prices, max_retries=1)
        
        # Verify circuit breaker was reset
        with self.auto_exec._circuit_breaker_lock:
            cb_state = self.auto_exec._price_fetch_circuit_breakers[symbol]
            self.assertEqual(cb_state['failures'], 0)
            self.assertIsNone(cb_state['opened_at'])


if __name__ == '__main__':
    unittest.main()
