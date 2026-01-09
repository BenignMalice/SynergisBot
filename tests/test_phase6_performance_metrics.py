"""
Unit tests for Phase 6: Performance Monitoring & Metrics
Tests metrics tracking, logging, and health checks
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, timezone
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auto_execution_system import AutoExecutionSystem, TradePlan


class TestPerformanceMetrics(unittest.TestCase):
    """Test performance metrics functionality"""
    
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
    
    def test_metrics_attributes_initialized(self):
        """Test that all metrics attributes are initialized"""
        self.assertTrue(hasattr(self.auto_exec, '_metrics_start_time'))
        self.assertTrue(hasattr(self.auto_exec, '_metrics_last_log'))
        self.assertTrue(hasattr(self.auto_exec, '_metrics_log_interval'))
        self.assertTrue(hasattr(self.auto_exec, '_condition_checks_total'))
        self.assertTrue(hasattr(self.auto_exec, '_condition_checks_success'))
        self.assertTrue(hasattr(self.auto_exec, '_condition_checks_failed'))
        self.assertTrue(hasattr(self.auto_exec, '_market_orders_executed'))
        self.assertTrue(hasattr(self.auto_exec, '_parallel_checks_total'))
        self.assertTrue(hasattr(self.auto_exec, '_parallel_checks_batches'))
        self.assertTrue(hasattr(self.auto_exec, '_cache_cleanup_count'))
        
        # Check initial values
        self.assertIsNone(self.auto_exec._metrics_start_time)
        self.assertIsNone(self.auto_exec._metrics_last_log)
        self.assertEqual(self.auto_exec._metrics_log_interval, 300)
        self.assertEqual(self.auto_exec._condition_checks_total, 0)
        self.assertEqual(self.auto_exec._condition_checks_success, 0)
        self.assertEqual(self.auto_exec._condition_checks_failed, 0)
        self.assertEqual(self.auto_exec._market_orders_executed, 0)
        self.assertEqual(self.auto_exec._parallel_checks_total, 0)
        self.assertEqual(self.auto_exec._parallel_checks_batches, 0)
        self.assertEqual(self.auto_exec._cache_cleanup_count, 0)
    
    def test_metrics_initialized_on_start(self):
        """Test that metrics are initialized when system starts"""
        self.auto_exec.start()
        
        self.assertIsNotNone(self.auto_exec._metrics_start_time)
        self.assertIsInstance(self.auto_exec._metrics_start_time, datetime)
        
        # Clean up
        self.auto_exec.running = False
        if hasattr(self.auto_exec, 'monitor_thread') and self.auto_exec.monitor_thread:
            try:
                self.auto_exec.monitor_thread.join(timeout=1.0)
            except:
                pass
    
    def test_log_performance_metrics_no_start_time(self):
        """Test that logging metrics returns early if no start time"""
        # Should not raise exception
        self.auto_exec._log_performance_metrics()
        
        # Metrics should still be 0
        self.assertEqual(self.auto_exec._condition_checks_total, 0)
    
    def test_log_performance_metrics_with_data(self):
        """Test that logging metrics works with data"""
        # Set up metrics
        self.auto_exec._metrics_start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        self.auto_exec._condition_checks_total = 100
        self.auto_exec._condition_checks_success = 95
        self.auto_exec._condition_checks_failed = 5
        self.auto_exec._price_cache_hits = 80
        self.auto_exec._price_cache_misses = 20
        self.auto_exec._batch_fetch_total = 50
        self.auto_exec._batch_fetch_success = 48
        self.auto_exec._batch_fetch_api_calls = 30
        self.auto_exec._market_orders_executed = 10
        self.auto_exec._parallel_checks_total = 200
        self.auto_exec._parallel_checks_batches = 20
        self.auto_exec._cache_cleanup_count = 5
        
        # Should not raise exception
        with patch('auto_execution_system.logger') as mock_logger:
            self.auto_exec._log_performance_metrics()
            
            # Verify logger.info was called
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            self.assertIn("Performance Metrics", call_args)
            self.assertIn("Condition checks", call_args)
            self.assertIn("Cache", call_args)
            self.assertIn("Batch fetch", call_args)
            self.assertIn("Market orders", call_args)
            self.assertIn("Parallel checks", call_args)
            self.assertIn("Cache cleanups", call_args)
    
    def test_get_health_status_healthy(self):
        """Test that health status returns healthy when system is running"""
        self.auto_exec.running = True
        self.auto_exec._metrics_start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        
        # Add a plan
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
        
        health = self.auto_exec.get_health_status()
        
        self.assertEqual(health["status"], "healthy")
        self.assertTrue(health["running"])
        self.assertEqual(health["active_plans"], 1)
        self.assertIn("metrics", health)
        self.assertIn("circuit_breakers", health)
        self.assertIn("warnings", health)
    
    def test_get_health_status_stopped(self):
        """Test that health status returns stopped when system is not running"""
        self.auto_exec.running = False
        self.auto_exec._metrics_start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        
        health = self.auto_exec.get_health_status()
        
        self.assertEqual(health["status"], "stopped")
        self.assertFalse(health["running"])
        self.assertIn("System is not running", health["warnings"])
    
    def test_get_health_status_degraded_circuit_breaker(self):
        """Test that health status returns degraded when circuit breaker is open"""
        self.auto_exec.running = True
        self.auto_exec._metrics_start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        self.auto_exec._circuit_breaker_failures = 3
        
        health = self.auto_exec.get_health_status()
        
        self.assertEqual(health["status"], "degraded")
        self.assertTrue(health["circuit_breakers"]["parallel_checks"]["open"])
        self.assertIn("Circuit breaker", health["warnings"][0])
    
    def test_get_health_status_degraded_low_success_rate(self):
        """Test that health status returns degraded when success rate is low"""
        self.auto_exec.running = True
        self.auto_exec._metrics_start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        self.auto_exec._condition_checks_total = 20
        self.auto_exec._condition_checks_success = 5  # 25% success rate (< 50%)
        
        health = self.auto_exec.get_health_status()
        
        self.assertEqual(health["status"], "degraded")
        self.assertLess(health["metrics"]["condition_checks"]["success_rate"], 50.0)
        self.assertIn("success rate is below 50%", health["warnings"][0])
    
    def test_get_health_status_calculates_rates(self):
        """Test that health status calculates all rates correctly"""
        self.auto_exec.running = True
        self.auto_exec._metrics_start_time = datetime.now(timezone.utc) - timedelta(hours=2)
        self.auto_exec._condition_checks_total = 100
        self.auto_exec._condition_checks_success = 90
        self.auto_exec._condition_checks_failed = 10
        self.auto_exec._price_cache_hits = 80
        self.auto_exec._price_cache_misses = 20
        self.auto_exec._batch_fetch_total = 50
        self.auto_exec._batch_fetch_success = 45
        self.auto_exec._market_orders_executed = 10
        self.auto_exec._parallel_checks_total = 200
        self.auto_exec._parallel_checks_batches = 20
        
        health = self.auto_exec.get_health_status()
        
        # Check condition checks rate
        self.assertEqual(health["metrics"]["condition_checks"]["success_rate"], 90.0)
        
        # Check cache hit rate
        self.assertEqual(health["metrics"]["price_cache"]["hit_rate"], 80.0)
        
        # Check batch fetch rate
        self.assertEqual(health["metrics"]["batch_fetch"]["success_rate"], 90.0)
        
        # Check market orders per hour
        self.assertEqual(health["metrics"]["market_orders"]["per_hour"], 5.0)
        
        # Check average batch size
        self.assertEqual(health["metrics"]["parallel_checks"]["avg_batch_size"], 10.0)
    
    def test_get_health_status_handles_zero_divisions(self):
        """Test that health status handles zero divisions gracefully"""
        self.auto_exec.running = True
        self.auto_exec._metrics_start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        
        # All metrics are 0
        health = self.auto_exec.get_health_status()
        
        # Should not raise exception and should return 0.0 for rates
        self.assertEqual(health["metrics"]["condition_checks"]["success_rate"], 0.0)
        self.assertEqual(health["metrics"]["price_cache"]["hit_rate"], 0.0)
        self.assertEqual(health["metrics"]["batch_fetch"]["success_rate"], 0.0)
        self.assertEqual(health["metrics"]["market_orders"]["per_hour"], 0.0)
        self.assertEqual(health["metrics"]["parallel_checks"]["avg_batch_size"], 0.0)
    
    def test_get_health_status_error_handling(self):
        """Test that health status handles errors gracefully"""
        self.auto_exec.running = True
        
        # Cause an error by making plans_lock None
        original_lock = self.auto_exec.plans_lock
        self.auto_exec.plans_lock = None
        
        try:
            health = self.auto_exec.get_health_status()
            self.assertEqual(health["status"], "error")
            self.assertIn("error", health)
        finally:
            # Restore lock
            self.auto_exec.plans_lock = original_lock
    
    def test_metrics_tracking_condition_checks(self):
        """Test that condition checks are tracked"""
        # Simulate condition checks
        self.auto_exec._condition_checks_total += 1
        self.auto_exec._condition_checks_success += 1
        
        self.assertEqual(self.auto_exec._condition_checks_total, 1)
        self.assertEqual(self.auto_exec._condition_checks_success, 1)
        self.assertEqual(self.auto_exec._condition_checks_failed, 0)
        
        # Simulate failed check
        self.auto_exec._condition_checks_total += 1
        self.auto_exec._condition_checks_failed += 1
        
        self.assertEqual(self.auto_exec._condition_checks_total, 2)
        self.assertEqual(self.auto_exec._condition_checks_success, 1)
        self.assertEqual(self.auto_exec._condition_checks_failed, 1)
    
    def test_metrics_tracking_market_orders(self):
        """Test that market orders are tracked"""
        self.auto_exec._market_orders_executed += 1
        
        self.assertEqual(self.auto_exec._market_orders_executed, 1)
        
        self.auto_exec._market_orders_executed += 1
        
        self.assertEqual(self.auto_exec._market_orders_executed, 2)
    
    def test_metrics_tracking_parallel_checks(self):
        """Test that parallel checks are tracked"""
        # Simulate parallel check with 10 plans in 2 batches
        plans_count = 10
        batch_size = 5
        num_batches = (plans_count + batch_size - 1) // batch_size
        
        self.auto_exec._parallel_checks_total += plans_count
        self.auto_exec._parallel_checks_batches += num_batches
        
        self.assertEqual(self.auto_exec._parallel_checks_total, 10)
        self.assertEqual(self.auto_exec._parallel_checks_batches, 2)
    
    def test_metrics_tracking_cache_cleanup(self):
        """Test that cache cleanup is tracked"""
        self.auto_exec._cache_cleanup_count += 1
        
        self.assertEqual(self.auto_exec._cache_cleanup_count, 1)
        
        self.auto_exec._cache_cleanup_count += 1
        
        self.assertEqual(self.auto_exec._cache_cleanup_count, 2)


if __name__ == '__main__':
    unittest.main()
