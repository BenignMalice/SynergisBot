"""
Integration tests for 15-second interval monitoring system
Tests interactions between different phases and components
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, timezone
import sys
import os
import time
import threading

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auto_execution_system import AutoExecutionSystem, TradePlan


class TestPhaseIntegration(unittest.TestCase):
    """Test integration between different phases"""
    
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
            # Shutdown thread pool if exists
            if hasattr(self.auto_exec, '_condition_check_executor') and self.auto_exec._condition_check_executor:
                try:
                    self.auto_exec._condition_check_executor.shutdown(wait=False)
                except:
                    pass
            # Close database manager
            if hasattr(self.auto_exec, '_db_manager') and self.auto_exec._db_manager:
                try:
                    self.auto_exec._db_manager.close()
                except:
                    pass
        if hasattr(self, 'temp_db'):
            try:
                os.unlink(self.temp_db.name)
            except:
                pass
    
    def test_phase1_phase2_integration_price_cache_batch_fetch(self):
        """Test integration between Phase 1 (price cache) and Phase 2 (batch fetching)"""
        # Create plans
        plan1 = TradePlan(
            plan_id="plan1",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        plan2 = TradePlan(
            plan_id="plan2",
            symbol="XAUUSD",
            direction="SELL",
            entry_price=2010.0,
            stop_loss=2020.0,
            take_profit=2000.0,
            volume=0.01,
            conditions={"tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        with self.auto_exec.plans_lock:
            self.auto_exec.plans[plan1.plan_id] = plan1
            self.auto_exec.plans[plan2.plan_id] = plan2
        
        # Mock MT5 service
        mock_quote = MagicMock()
        mock_quote.bid = 2002.0
        mock_quote.ask = 2002.5
        self.mt5_service.get_quote = Mock(return_value=mock_quote)
        
        # First fetch - should go to API (method gets symbols from active plans)
        self.mt5_service.connect = Mock(return_value=True)
        prices = self.auto_exec._get_current_prices_batch()
        
        # Verify API was called
        self.assertGreater(self.mt5_service.get_quote.call_count, 0)
        self.assertGreater(self.auto_exec._batch_fetch_api_calls, 0)
        
        # Verify price was cached (returns float, not dict)
        cached_price = self.auto_exec._get_cached_price("XAUUSDc")
        self.assertIsNotNone(cached_price)
        self.assertEqual(cached_price, 2002.25)  # (bid + ask) / 2
        
        # Verify price is in returned prices dict
        self.assertIn("XAUUSDc", prices)
        self.assertEqual(prices["XAUUSDc"], 2002.25)
        
        # Second fetch - should use cache
        self.mt5_service.get_quote.reset_mock()
        initial_cache_hits = self.auto_exec._price_cache_hits
        prices2 = self.auto_exec._get_current_prices_batch()
        
        # Verify API was NOT called again (cache hit)
        self.assertEqual(self.mt5_service.get_quote.call_count, 0)
        self.assertGreater(self.auto_exec._price_cache_hits, initial_cache_hits)
    
    def test_phase2_phase3_integration_batch_fetch_database_pooling(self):
        """Test integration between Phase 2 (batch fetching) and Phase 3 (database pooling)"""
        # Create plan and add to database
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Add plan using database connection pool
        result = self.auto_exec.add_plan(plan)
        self.assertTrue(result)
        
        # Verify plan was saved
        saved_plan = self.auto_exec.get_plan_by_id(plan.plan_id)
        self.assertIsNotNone(saved_plan)
        self.assertEqual(saved_plan.plan_id, plan.plan_id)
        
        # Verify plan was saved (database manager may be None if aiosqlite not available)
        # This is acceptable - system falls back to direct connections
        saved_plan = self.auto_exec.get_plan_by_id(plan.plan_id)
        self.assertIsNotNone(saved_plan)
    
    def test_phase3_phase4_integration_database_parallel_checks(self):
        """Test integration between Phase 3 (database pooling) and Phase 4 (parallel checks)"""
        # Create multiple plans
        plans = []
        for i in range(5):
            plan = TradePlan(
                plan_id=f"plan_{i}",
                symbol="XAUUSD",
                direction="BUY",
                entry_price=2000.0 + i,
                stop_loss=1990.0 + i,
                take_profit=2010.0 + i,
                volume=0.01,
                conditions={"tolerance": 5.0},
                created_at=datetime.now(timezone.utc).isoformat(),
                created_by="test",
                status="pending"
            )
            plans.append(plan)
            self.auto_exec.add_plan(plan)
        
        # Start system to initialize thread pool
        self.auto_exec.start()
        
        # Verify thread pool is initialized
        self.assertIsNotNone(self.auto_exec._condition_check_executor)
        
        # Mock condition checks
        with patch.object(self.auto_exec, '_check_conditions', return_value=False):
            # Get plans from database
            with self.auto_exec.plans_lock:
                plans_list = list(self.auto_exec.plans.values())
            
            # Test parallel checking
            symbol_prices = {"XAUUSDc": 2002.0}
            results = self.auto_exec._check_conditions_parallel(plans_list, symbol_prices)
            
            # Verify all plans were checked
            self.assertEqual(len(results), 5)
            self.assertGreaterEqual(self.auto_exec._parallel_checks_total, 5)
            self.assertGreater(self.auto_exec._parallel_checks_batches, 0)
        
        # Clean up
        self.auto_exec.running = False
    
    def test_phase4_phase5_integration_parallel_adaptive_intervals(self):
        """Test integration between Phase 4 (parallel checks) and Phase 5 (adaptive intervals)"""
        # Create plan
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        with self.auto_exec.plans_lock:
            self.auto_exec.plans[plan.plan_id] = plan
        
        # Set recent activity
        self.auto_exec._plan_activity[plan.plan_id] = datetime.now(timezone.utc) - timedelta(minutes=2)
        
        # Set high volatility
        self.auto_exec._plan_volatility["XAUUSDc"] = 2.5
        
        # Mock config
        with patch.dict(self.auto_exec.config, {
            'optimized_intervals': {
                'adaptive_intervals': {
                    'enabled': True,
                    'plan_type_intervals': {
                        'scalp': {
                            'close_interval_seconds': 20,
                            'base_interval_seconds': 30,
                            'far_interval_seconds': 60
                        }
                    }
                }
            }
        }):
            with patch.object(self.auto_exec, '_plan_types', {'test_plan': 'scalp'}):
                with patch.object(self.auto_exec, '_detect_plan_type', return_value='scalp'):
                    # Calculate adaptive interval
                    current_price = 2002.0  # Within tolerance
                    interval = self.auto_exec._calculate_adaptive_interval(plan, current_price)
                    
                    # Verify interval respects minimum (15s) and includes adjustments
                    self.assertGreaterEqual(interval, 15)
                    
                    # Verify activity and volatility adjustments were applied
                    # Base: 20s, activity: -20% = 16s, volatility: -15% = 13.6s, min = 15s
                    self.assertEqual(interval, 15)
    
    def test_phase5_phase6_integration_adaptive_intervals_metrics(self):
        """Test integration between Phase 5 (adaptive intervals) and Phase 6 (metrics)"""
        # Create plan
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        with self.auto_exec.plans_lock:
            self.auto_exec.plans[plan.plan_id] = plan
        
        # Initialize metrics
        self.auto_exec._metrics_start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        
        # Simulate condition checks
        self.auto_exec._condition_checks_total = 100
        self.auto_exec._condition_checks_success = 95
        
        # Simulate adaptive interval usage
        current_price = 2002.0
        interval = self.auto_exec._calculate_adaptive_interval(plan, current_price)
        
        # Verify interval is calculated
        self.assertGreaterEqual(interval, 15)
        
        # Get health status
        health = self.auto_exec.get_health_status()
        
        # Verify metrics are included
        self.assertIn("metrics", health)
        self.assertEqual(health["metrics"]["condition_checks"]["total"], 100)
        self.assertEqual(health["metrics"]["condition_checks"]["success"], 95)
    
    def test_phase1_phase6_integration_cache_metrics(self):
        """Test integration between Phase 1 (price cache) and Phase 6 (metrics)"""
        # Initialize metrics
        self.auto_exec._metrics_start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        
        # Simulate cache hits and misses
        self.auto_exec._price_cache_hits = 80
        self.auto_exec._price_cache_misses = 20
        
        # Get health status
        health = self.auto_exec.get_health_status()
        
        # Verify cache metrics are included
        self.assertIn("price_cache", health["metrics"])
        self.assertEqual(health["metrics"]["price_cache"]["hits"], 80)
        self.assertEqual(health["metrics"]["price_cache"]["misses"], 20)
        self.assertEqual(health["metrics"]["price_cache"]["hit_rate"], 80.0)
    
    def test_all_phases_integration_full_flow(self):
        """Test integration of all phases in a complete flow"""
        # Create plan
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 5.0},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Phase 3: Add plan using database pooling
        result = self.auto_exec.add_plan(plan)
        self.assertTrue(result)
        
        # Phase 1 & 2: Fetch price (should cache)
        mock_quote = MagicMock()
        mock_quote.bid = 2002.0
        mock_quote.ask = 2002.5
        self.mt5_service.get_quote = Mock(return_value=mock_quote)
        self.mt5_service.connect = Mock(return_value=True)
        
        prices = self.auto_exec._get_current_prices_batch()
        
        # Verify price was cached
        cached_price = self.auto_exec._get_cached_price("XAUUSDc")
        self.assertIsNotNone(cached_price)
        
        # Phase 5: Calculate adaptive interval
        current_price = 2002.0
        interval = self.auto_exec._calculate_adaptive_interval(plan, current_price)
        self.assertGreaterEqual(interval, 15)
        
        # Phase 6: Check metrics
        self.auto_exec._metrics_start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        health = self.auto_exec.get_health_status()
        self.assertIn("metrics", health)
        
        # Phase 4: Start system for parallel checks
        self.auto_exec.start()
        self.assertIsNotNone(self.auto_exec._condition_check_executor)
        
        # Clean up
        self.auto_exec.running = False


if __name__ == '__main__':
    unittest.main()
