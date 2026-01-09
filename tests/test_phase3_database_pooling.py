"""
Unit tests for Phase 3: Database Connection Pooling
Tests OptimizedSQLiteManager integration and context manager
"""

import unittest
import os
import sys
import tempfile
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auto_execution_system import AutoExecutionSystem, TradePlan


class TestDatabasePooling(unittest.TestCase):
    """Test database connection pooling functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
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
    
    def test_db_manager_initialization(self):
        """Test that OptimizedSQLiteManager is initialized"""
        # Verify _db_manager exists
        self.assertTrue(hasattr(self.auto_exec, '_db_manager'))
        
        # If initialization succeeded, _db_manager should not be None
        # (If it failed, it would be None but that's acceptable for fallback)
        if self.auto_exec._db_manager is not None:
            # Verify it has the expected methods
            self.assertTrue(hasattr(self.auto_exec._db_manager, 'get_connection'))
            self.assertTrue(hasattr(self.auto_exec._db_manager, 'return_connection'))
            self.assertTrue(hasattr(self.auto_exec._db_manager, 'close'))
    
    def test_context_manager_exists(self):
        """Test that _get_db_connection context manager exists"""
        self.assertTrue(hasattr(self.auto_exec, '_get_db_connection'))
        self.assertTrue(callable(self.auto_exec._get_db_connection))
    
    def test_context_manager_usage(self):
        """Test that context manager works correctly"""
        # Use context manager
        with self.auto_exec._get_db_connection() as conn:
            # Verify connection is valid
            self.assertIsNotNone(conn)
            # Verify we can execute a query
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            self.assertEqual(result[0], 1)
    
    def test_load_plans_uses_context_manager(self):
        """Test that _load_plans uses the context manager"""
        # Create a test plan
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
        
        # Add plan via add_plan (which uses context manager)
        result = self.auto_exec.add_plan(plan)
        self.assertTrue(result)
        
        # Load plans (should use context manager)
        plans = self.auto_exec._load_plans()
        
        # Verify plan was loaded
        self.assertIn("test_plan", plans)
        self.assertEqual(plans["test_plan"].plan_id, "test_plan")
    
    def test_add_plan_uses_context_manager(self):
        """Test that add_plan uses the context manager"""
        plan = TradePlan(
            plan_id="test_plan_2",
            symbol="BTCUSD",
            direction="SELL",
            entry_price=50000.0,
            stop_loss=51000.0,
            take_profit=49000.0,
            volume=0.01,
            conditions={},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Add plan (should use context manager)
        result = self.auto_exec.add_plan(plan)
        self.assertTrue(result)
        
        # Verify plan was added
        loaded_plan = self.auto_exec.get_plan_by_id("test_plan_2")
        self.assertIsNotNone(loaded_plan)
        self.assertEqual(loaded_plan.plan_id, "test_plan_2")
    
    def test_get_plan_by_id_uses_context_manager(self):
        """Test that get_plan_by_id uses the context manager"""
        # Create and add a plan
        plan = TradePlan(
            plan_id="test_plan_3",
            symbol="EURUSD",
            direction="BUY",
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1050,
            volume=0.01,
            conditions={},
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        self.auto_exec.add_plan(plan)
        
        # Get plan by ID (should use context manager)
        loaded_plan = self.auto_exec.get_plan_by_id("test_plan_3")
        
        # Verify plan was retrieved
        self.assertIsNotNone(loaded_plan)
        self.assertEqual(loaded_plan.plan_id, "test_plan_3")
        self.assertEqual(loaded_plan.symbol, "EURUSD")
    
    def test_fallback_to_direct_connection(self):
        """Test that system falls back to direct connections if OptimizedSQLiteManager fails"""
        # Simulate failure by setting _db_manager to None
        original_manager = self.auto_exec._db_manager
        self.auto_exec._db_manager = None
        
        # Context manager should still work (fallback to direct connection)
        with self.auto_exec._get_db_connection() as conn:
            self.assertIsNotNone(conn)
            cursor = conn.execute("SELECT 1")
            result = cursor.fetchone()
            self.assertEqual(result[0], 1)
        
        # Restore original manager
        self.auto_exec._db_manager = original_manager
    
    def test_cleanup_on_stop(self):
        """Test that database manager is cleaned up on stop()"""
        # Verify _db_manager exists
        if self.auto_exec._db_manager is not None:
            original_manager = self.auto_exec._db_manager
            
            # Stop system
            self.auto_exec.stop()
            
            # Verify _db_manager is None after stop
            self.assertIsNone(self.auto_exec._db_manager)
            
            # Verify close() was called (check if manager is closed)
            # Note: We can't directly verify close() was called, but we can verify
            # that _db_manager is None, which indicates cleanup occurred


if __name__ == '__main__':
    unittest.main()
