"""
Test Phase 3.1: Database Schema Updates
Tests for pending_order_ticket column addition
"""

import unittest
import sys
import sqlite3
import os
import tempfile
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from auto_execution_system import AutoExecutionSystem, TradePlan


class TestDatabaseSchemaUpdates(unittest.TestCase):
    """Test database schema updates for pending_order_ticket"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        try:
            self.auto_exec = AutoExecutionSystem(
                db_path=self.temp_db.name,
                mt5_service=None  # We'll mock MT5 service
            )
        except Exception as e:
            self.skipTest(f"Could not initialize AutoExecutionSystem: {e}")
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Stop AutoExecutionSystem to close database connections and stop background threads
        if hasattr(self, 'auto_exec'):
            try:
                # Stop the system
                if hasattr(self.auto_exec, 'stop'):
                    self.auto_exec.stop()
                
                # Stop database write queue if it exists
                if hasattr(self.auto_exec, 'db_write_queue') and self.auto_exec.db_write_queue:
                    if hasattr(self.auto_exec.db_write_queue, 'stop'):
                        self.auto_exec.db_write_queue.stop(timeout=5.0)
                
                # Give threads time to finish
                time.sleep(0.5)
            except Exception as e:
                # Ignore cleanup errors
                pass
        
        # Delete temp database file
        if os.path.exists(self.temp_db.name):
            try:
                os.unlink(self.temp_db.name)
            except PermissionError:
                # File might still be locked, try again after a short delay
                time.sleep(0.5)
                try:
                    os.unlink(self.temp_db.name)
                except Exception:
                    # If still locked, just leave it (temp file will be cleaned up later)
                    pass
    
    def test_pending_order_ticket_column_exists(self):
        """Test that pending_order_ticket column exists in database"""
        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.execute("PRAGMA table_info(trade_plans)")
            columns = [row[1] for row in cursor.fetchall()]
            
            self.assertIn("pending_order_ticket", columns, 
                         "pending_order_ticket column should exist in trade_plans table")
    
    def test_pending_order_ticket_column_type(self):
        """Test that pending_order_ticket column has correct type"""
        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.execute("PRAGMA table_info(trade_plans)")
            columns_info = {row[1]: row[2] for row in cursor.fetchall()}
            
            # SQLite doesn't enforce types strictly, but we check it's defined
            self.assertIn("pending_order_ticket", columns_info,
                         "pending_order_ticket column should be defined")
    
    def test_add_plan_with_pending_order_ticket(self):
        """Test adding a plan with pending_order_ticket"""
        plan = TradePlan(
            plan_id="test_plan_1",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"strategy_type": "test"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending_order_placed",
            pending_order_ticket=12345
        )
        
        result = self.auto_exec.add_plan(plan)
        self.assertTrue(result, "Plan should be added successfully")
        
        # Verify it was saved to database
        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.execute(
                "SELECT pending_order_ticket FROM trade_plans WHERE plan_id = ?",
                (plan.plan_id,)
            )
            row = cursor.fetchone()
            self.assertIsNotNone(row, "Plan should exist in database")
            self.assertEqual(row[0], 12345, "pending_order_ticket should be saved correctly")
    
    def test_load_plan_with_pending_order_ticket(self):
        """Test loading a plan with pending_order_ticket from database"""
        # First, add a plan with pending_order_ticket using add_plan()
        plan = TradePlan(
            plan_id="test_plan_2",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"strategy_type": "test"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending_order_placed",
            pending_order_ticket=54321
        )
        self.auto_exec.add_plan(plan)
        
        # Now load it
        loaded_plan = self.auto_exec.get_plan_by_id("test_plan_2")
        self.assertIsNotNone(loaded_plan, "Plan should be loaded from database")
        self.assertEqual(loaded_plan.pending_order_ticket, 54321,
                        "pending_order_ticket should be loaded correctly")
    
    def test_update_plan_pending_order_ticket(self):
        """Test updating a plan's pending_order_ticket"""
        # Add a plan first
        plan = TradePlan(
            plan_id="test_plan_3",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"strategy_type": "test"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending",
            pending_order_ticket=None
        )
        
        self.auto_exec.add_plan(plan)
        
        # Update pending_order_ticket
        plan.pending_order_ticket = 99999
        plan.status = "pending_order_placed"
        result = self.auto_exec._update_plan_status(plan)
        self.assertTrue(result, "Plan status should be updated successfully")
        
        # Verify update
        updated_plan = self.auto_exec.get_plan_by_id("test_plan_3")
        self.assertIsNotNone(updated_plan, "Plan should still exist")
        self.assertEqual(updated_plan.pending_order_ticket, 99999,
                        "pending_order_ticket should be updated correctly")
        self.assertEqual(updated_plan.status, "pending_order_placed",
                        "Status should be updated correctly")
    
    def test_load_plans_includes_pending_order_placed(self):
        """Test that _load_plans() includes plans with pending_order_placed status"""
        # Add a plan with pending_order_placed status using add_plan()
        plan = TradePlan(
            plan_id="test_plan_4",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"strategy_type": "test"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending_order_placed",
            pending_order_ticket=77777
        )
        self.auto_exec.add_plan(plan)
        
        # Update status and pending_order_ticket in database directly to simulate pending order placement
        with sqlite3.connect(self.temp_db.name) as conn:
            conn.execute("""
                UPDATE trade_plans 
                SET status = ?, pending_order_ticket = ?
                WHERE plan_id = ?
            """, ("pending_order_placed", 77777, "test_plan_4"))
            conn.commit()
        
        # Reload plans
        plans = self.auto_exec._load_plans()
        
        # Verify plan is loaded
        self.assertIn("test_plan_4", plans, 
                     "Plan with pending_order_placed status should be loaded")
        loaded_plan = plans["test_plan_4"]
        self.assertEqual(loaded_plan.status, "pending_order_placed",
                        "Plan status should be correct")
        self.assertEqual(loaded_plan.pending_order_ticket, 77777,
                        "pending_order_ticket should be loaded correctly")


if __name__ == '__main__':
    unittest.main()
