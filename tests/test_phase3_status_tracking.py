"""
Test Phase 3: Status Tracking
Comprehensive tests for pending order status tracking functionality
"""

import unittest
import sys
import sqlite3
import os
import tempfile
import time
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, timezone

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from auto_execution_system import AutoExecutionSystem, TradePlan


class TestPhase3StatusTracking(unittest.TestCase):
    """Test Phase 3: Status Tracking functionality"""
    
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
    
    def test_tradeplan_has_pending_order_ticket_field(self):
        """Test that TradePlan dataclass has pending_order_ticket field"""
        plan = TradePlan(
            plan_id="test_plan",
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
            pending_order_ticket=12345
        )
        
        self.assertTrue(hasattr(plan, 'pending_order_ticket'), 
                       "TradePlan should have pending_order_ticket field")
        self.assertEqual(plan.pending_order_ticket, 12345,
                        "pending_order_ticket should be set correctly")
    
    def test_add_plan_saves_pending_order_ticket(self):
        """Test that add_plan() saves pending_order_ticket to database"""
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
            pending_order_ticket=99999
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
            self.assertEqual(row[0], 99999, "pending_order_ticket should be saved correctly")
    
    def test_load_plans_includes_pending_order_placed_status(self):
        """Test that _load_plans() includes plans with pending_order_placed status"""
        # Add a plan with pending_order_placed status
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
            pending_order_ticket=88888
        )
        self.auto_exec.add_plan(plan)
        
        # Wait a moment for database to be ready
        time.sleep(0.2)
        
        # Reload plans
        plans = self.auto_exec._load_plans()
        
        # Verify plan is loaded
        self.assertIn("test_plan_2", plans, 
                     "Plan with pending_order_placed status should be loaded")
        loaded_plan = plans["test_plan_2"]
        self.assertEqual(loaded_plan.status, "pending_order_placed",
                        "Plan status should be correct")
        
        # Verify pending_order_ticket was saved to database first
        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.execute(
                "SELECT pending_order_ticket FROM trade_plans WHERE plan_id = ?",
                ("test_plan_2",)
            )
            row = cursor.fetchone()
            if row and row[0] is not None:
                # If it's in the database, it should be loaded
                self.assertEqual(loaded_plan.pending_order_ticket, 88888,
                                "pending_order_ticket should be loaded correctly")
            else:
                # If not in database, that's the real issue
                self.fail("pending_order_ticket was not saved to database")
    
    def test_update_plan_status_includes_pending_order_ticket(self):
        """Test that _update_plan_status() includes pending_order_ticket in update"""
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
        
        # Update pending_order_ticket and status
        plan.pending_order_ticket = 77777
        plan.status = "pending_order_placed"
        result = self.auto_exec._update_plan_status(plan)
        self.assertTrue(result, "Plan status should be updated successfully")
        
        # Wait for database write queue to process
        time.sleep(0.5)
        
        # Verify update in database
        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.execute(
                "SELECT status, pending_order_ticket FROM trade_plans WHERE plan_id = ?",
                ("test_plan_3",)
            )
            row = cursor.fetchone()
            self.assertIsNotNone(row, "Plan should exist in database")
            self.assertEqual(row[0], "pending_order_placed", "Status should be updated")
            self.assertEqual(row[1], 77777, "pending_order_ticket should be updated")
    
    def test_get_plan_by_id_loads_pending_order_ticket(self):
        """Test that get_plan_by_id() loads pending_order_ticket from database"""
        # Add a plan with pending_order_ticket
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
            pending_order_ticket=66666
        )
        self.auto_exec.add_plan(plan)
        
        # Load plan by ID
        loaded_plan = self.auto_exec.get_plan_by_id("test_plan_4")
        self.assertIsNotNone(loaded_plan, "Plan should be loaded from database")
        if loaded_plan:  # Only check if plan was loaded (may fail if columns missing in test DB)
            self.assertEqual(loaded_plan.pending_order_ticket, 66666,
                            "pending_order_ticket should be loaded correctly")
    
    def test_pending_order_ticket_defaults_to_none(self):
        """Test that pending_order_ticket defaults to None when not set"""
        plan = TradePlan(
            plan_id="test_plan_5",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"strategy_type": "test"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # pending_order_ticket should default to None
        self.assertIsNone(plan.pending_order_ticket,
                         "pending_order_ticket should default to None")
    
    def test_update_plan_status_direct_handles_pending_order_ticket(self):
        """Test that _update_plan_status_direct() handles pending_order_ticket"""
        # Add a plan first
        plan = TradePlan(
            plan_id="test_plan_6",
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
        
        # Update using direct method
        plan.pending_order_ticket = 55555
        plan.status = "pending_order_placed"
        result = self.auto_exec._update_plan_status_direct(plan)
        self.assertTrue(result, "Plan status should be updated successfully")
        
        # Verify update in database
        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.execute(
                "SELECT status, pending_order_ticket FROM trade_plans WHERE plan_id = ?",
                ("test_plan_6",)
            )
            row = cursor.fetchone()
            self.assertIsNotNone(row, "Plan should exist in database")
            self.assertEqual(row[0], "pending_order_placed", "Status should be updated")
            self.assertEqual(row[1], 55555, "pending_order_ticket should be updated")
    
    def test_database_write_queue_handles_pending_order_ticket(self):
        """Test that DatabaseWriteQueue handles pending_order_ticket in updates"""
        # Add a plan first
        plan = TradePlan(
            plan_id="test_plan_7",
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
        
        # Update using queue (via _update_plan_status)
        plan.pending_order_ticket = 44444
        plan.status = "pending_order_placed"
        result = self.auto_exec._update_plan_status(plan, wait_for_completion=True)
        self.assertTrue(result, "Plan status should be queued successfully")
        
        # Wait for queue to process
        time.sleep(1.0)
        
        # Verify update in database
        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.execute(
                "SELECT status, pending_order_ticket FROM trade_plans WHERE plan_id = ?",
                ("test_plan_7",)
            )
            row = cursor.fetchone()
            self.assertIsNotNone(row, "Plan should exist in database")
            self.assertEqual(row[0], "pending_order_placed", "Status should be updated")
            self.assertEqual(row[1], 44444, "pending_order_ticket should be updated")


if __name__ == '__main__':
    unittest.main()
