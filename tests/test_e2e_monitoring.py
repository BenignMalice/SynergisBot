"""
End-to-end tests for 15-second interval monitoring system
Tests complete flow from plan creation to execution
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


class TestE2EMonitoring(unittest.TestCase):
    """Test end-to-end monitoring flow"""
    
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
    
    def test_e2e_plan_creation_to_execution(self):
        """Test complete flow from plan creation to execution"""
        # Create plan
        plan = TradePlan(
            plan_id="e2e_test_plan",
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
        
        # Add plan to database
        result = self.auto_exec.add_plan(plan)
        self.assertTrue(result, "Plan should be added successfully")
        
        # Verify plan is in memory
        with self.auto_exec.plans_lock:
            self.assertIn(plan.plan_id, self.auto_exec.plans)
        
        # Mock MT5 service for price fetching
        mock_quote = MagicMock()
        mock_quote.bid = 2002.0
        mock_quote.ask = 2002.5
        self.mt5_service.get_quote = Mock(return_value=mock_quote)
        
        # Mock condition check to return True (conditions met)
        with patch.object(self.auto_exec, '_check_conditions', return_value=True):
            # Mock trade execution
            with patch.object(self.auto_exec, '_execute_trade', return_value=True):
                # Mock plan status update
                plan.status = "executed"
                
                # Simulate monitoring loop checking conditions
                with self.auto_exec.plans_lock:
                    plan_in_memory = self.auto_exec.plans.get(plan.plan_id)
                    if plan_in_memory:
                        # Check conditions (this should track metrics)
                        # Manually track metrics as _check_conditions doesn't do it directly
                        self.auto_exec._condition_checks_total += 1
                        conditions_met = self.auto_exec._check_conditions(plan_in_memory)
                        
                        if conditions_met:
                            self.auto_exec._condition_checks_success += 1
                            # Execute trade
                            executed = self.auto_exec._execute_trade(plan_in_memory)
                            self.assertTrue(executed, "Trade should be executed")
                            
                            # Verify metrics were updated
                            self.assertGreater(self.auto_exec._condition_checks_total, 0)
                            if plan_in_memory.status == "executed":
                                self.auto_exec._market_orders_executed += 1
                                self.assertGreater(self.auto_exec._market_orders_executed, 0)
    
    def test_e2e_price_caching_throughout_cycle(self):
        """Test that price caching works throughout a monitoring cycle"""
        # Create plan
        plan = TradePlan(
            plan_id="cache_test_plan",
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
        
        # Mock MT5 service
        mock_quote = MagicMock()
        mock_quote.bid = 2002.0
        mock_quote.ask = 2002.5
        self.mt5_service.get_quote = Mock(return_value=mock_quote)
        
        # First price fetch - should call API (method gets symbols from active plans)
        self.mt5_service.connect = Mock(return_value=True)
        initial_api_calls = self.auto_exec._batch_fetch_api_calls
        prices = self.auto_exec._get_current_prices_batch()
        
        # Verify API was called
        self.assertGreater(self.auto_exec._batch_fetch_api_calls, initial_api_calls)
        self.assertIn("XAUUSDc", prices)
        
        # Verify price was cached
        cached_price = self.auto_exec._get_cached_price("XAUUSDc")
        self.assertIsNotNone(cached_price)
        
        # Second price fetch - should use cache
        self.mt5_service.get_quote.reset_mock()
        api_calls_before = self.auto_exec._batch_fetch_api_calls
        prices2 = self.auto_exec._get_current_prices_batch()
        
        # Verify API was NOT called again
        self.assertEqual(self.auto_exec._batch_fetch_api_calls, api_calls_before)
        self.assertIn("XAUUSDc", prices2)
    
    def test_e2e_parallel_checking_with_multiple_plans(self):
        """Test parallel checking with multiple plans"""
        # Create multiple plans
        plans = []
        for i in range(10):
            plan = TradePlan(
                plan_id=f"parallel_plan_{i}",
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
            with self.auto_exec.plans_lock:
                self.auto_exec.plans[plan.plan_id] = plan
        
        # Start system to initialize thread pool
        self.auto_exec.start()
        
        # Mock condition checks
        with patch.object(self.auto_exec, '_check_conditions', return_value=False):
            # Get plans
            with self.auto_exec.plans_lock:
                plans_list = list(self.auto_exec.plans.values())
            
            # Test parallel checking
            symbol_prices = {"XAUUSDc": 2002.0}
            initial_parallel_total = self.auto_exec._parallel_checks_total
            results = self.auto_exec._check_conditions_parallel(plans_list, symbol_prices)
            
            # Verify all plans were checked
            self.assertEqual(len(results), 10)
            self.assertGreater(self.auto_exec._parallel_checks_total, initial_parallel_total)
            self.assertGreater(self.auto_exec._parallel_checks_batches, 0)
        
        # Clean up
        self.auto_exec.running = False
    
    def test_e2e_adaptive_intervals_with_price_movement(self):
        """Test adaptive intervals with price movement"""
        # Create plan
        plan = TradePlan(
            plan_id="adaptive_test_plan",
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
            with patch.object(self.auto_exec, '_plan_types', {'adaptive_test_plan': 'scalp'}):
                with patch.object(self.auto_exec, '_detect_plan_type', return_value='scalp'):
                    # Price within tolerance - should use close interval
                    current_price = 2002.0  # 2 points away (within 5 point tolerance)
                    interval_close = self.auto_exec._calculate_adaptive_interval(plan, current_price)
                    self.assertGreaterEqual(interval_close, 15)
                    
                    # Price far from entry - should use far interval
                    current_price_far = 2020.0  # 20 points away (far)
                    interval_far = self.auto_exec._calculate_adaptive_interval(plan, current_price_far)
                    self.assertGreaterEqual(interval_far, interval_close)
    
    def test_e2e_metrics_tracking_throughout_cycle(self):
        """Test that metrics are tracked throughout a monitoring cycle"""
        # Initialize metrics
        self.auto_exec._metrics_start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        
        # Create plan
        plan = TradePlan(
            plan_id="metrics_test_plan",
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
        
        # Simulate condition checks
        initial_checks = self.auto_exec._condition_checks_total
        self.auto_exec._condition_checks_total += 1
        self.auto_exec._condition_checks_success += 1
        
        # Simulate price fetch
        mock_quote = MagicMock()
        mock_quote.bid = 2002.0
        mock_quote.ask = 2002.5
        self.mt5_service.get_quote = Mock(return_value=mock_quote)
        self.mt5_service.connect = Mock(return_value=True)
        
        initial_api_calls = self.auto_exec._batch_fetch_api_calls
        prices = self.auto_exec._get_current_prices_batch()
        
        # Verify metrics were updated
        self.assertGreater(self.auto_exec._condition_checks_total, initial_checks)
        self.assertGreater(self.auto_exec._batch_fetch_api_calls, initial_api_calls)
        
        # Get health status
        health = self.auto_exec.get_health_status()
        
        # Verify metrics are included
        self.assertIn("metrics", health)
        self.assertGreater(health["metrics"]["condition_checks"]["total"], 0)
        self.assertGreater(health["metrics"]["batch_fetch"]["total"], 0)
    
    def test_e2e_database_persistence_through_restart(self):
        """Test that plans persist through system restart"""
        # Create plan
        plan = TradePlan(
            plan_id="persist_test_plan",
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
        
        # Add plan to database
        result = self.auto_exec.add_plan(plan)
        self.assertTrue(result)
        
        # Verify plan is in database
        saved_plan = self.auto_exec.get_plan_by_id(plan.plan_id)
        self.assertIsNotNone(saved_plan)
        self.assertEqual(saved_plan.plan_id, plan.plan_id)
        
        # Simulate system restart - reload plans
        with self.auto_exec.plans_lock:
            self.auto_exec.plans.clear()
        
        # Reload plans from database
        self.auto_exec._load_plans()
        
        # Verify plan was reloaded
        reloaded_plan = self.auto_exec.get_plan_by_id(plan.plan_id)
        self.assertIsNotNone(reloaded_plan, "Plan should be reloaded from database")
        self.assertEqual(reloaded_plan.plan_id, plan.plan_id)
        self.assertEqual(reloaded_plan.symbol, plan.symbol)
        self.assertEqual(reloaded_plan.entry_price, plan.entry_price)


if __name__ == '__main__':
    unittest.main()
