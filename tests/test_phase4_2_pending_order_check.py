"""
Test Phase 4.2: Pending Order Check Method
Tests for _check_pending_orders() method
"""

import unittest
import sys
import sqlite3
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, timezone

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from auto_execution_system import AutoExecutionSystem, TradePlan


class TestPendingOrderCheck(unittest.TestCase):
    """Test _check_pending_orders() method"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Mock MT5 service
        self.mock_mt5_service = MagicMock()
        self.mock_mt5_service.connect.return_value = True
        
        try:
            self.auto_exec = AutoExecutionSystem(
                db_path=self.temp_db.name,
                mt5_service=self.mock_mt5_service
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
    
    def test_check_pending_orders_no_pending_orders(self):
        """Test _check_pending_orders() with no pending orders"""
        # No plans in memory
        with patch('MetaTrader5.orders_get', return_value=[]):
            # Should return early without errors
            self.auto_exec._check_pending_orders()
            # No exceptions should be raised
    
    def test_check_pending_orders_mt5_not_connected(self):
        """Test _check_pending_orders() when MT5 is not connected"""
        self.mock_mt5_service.connect.return_value = False
        
        # Should return early without errors
        self.auto_exec._check_pending_orders()
        # No exceptions should be raised
    
    def test_check_pending_orders_order_still_exists(self):
        """Test _check_pending_orders() when order still exists"""
        # Create a plan with pending order
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
        
        with self.auto_exec.plans_lock:
            self.auto_exec.plans[plan.plan_id] = plan
        
        # Mock MT5 to return order still exists
        mock_order = Mock()
        mock_order.ticket = 12345
        with patch('MetaTrader5.orders_get', return_value=[mock_order]):
            self.auto_exec._check_pending_orders()
        
        # Plan should still be in memory with same status
        with self.auto_exec.plans_lock:
            self.assertIn("test_plan_1", self.auto_exec.plans)
            self.assertEqual(self.auto_exec.plans["test_plan_1"].status, "pending_order_placed")
    
    def test_check_pending_orders_order_filled(self):
        """Test _check_pending_orders() when order fills"""
        # Create a plan with pending order
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
            pending_order_ticket=12346
        )
        
        with self.auto_exec.plans_lock:
            self.auto_exec.plans[plan.plan_id] = plan
        
        # Mock MT5: order no longer exists (filled)
        # Mock position that matches the order
        mock_position = Mock()
        mock_position.ticket = 99999
        mock_position.type = 0  # ORDER_TYPE_BUY
        mock_position.price_open = 2000.0
        mock_position.volume = 0.01
        mock_position.time = datetime.now(timezone.utc).timestamp()
        
        with patch('MetaTrader5.orders_get', return_value=None):
            with patch('MetaTrader5.positions_get', return_value=[mock_position]):
                with patch.object(self.auto_exec, '_handle_post_execution') as mock_post_exec:
                    with patch.object(self.auto_exec, '_update_plan_status') as mock_update:
                        self.auto_exec._check_pending_orders()
                        
                        # Verify plan status was updated
                        with self.auto_exec.plans_lock:
                            # Plan should be removed from memory after filling
                            self.assertNotIn("test_plan_2", self.auto_exec.plans)
                        
                        # Verify post-execution was called
                        mock_post_exec.assert_called_once()
                        # Verify status was updated
                        mock_update.assert_called_once()
    
    def test_check_pending_orders_order_cancelled(self):
        """Test _check_pending_orders() when order is cancelled"""
        # Create a plan with pending order
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
            status="pending_order_placed",
            pending_order_ticket=12347
        )
        
        with self.auto_exec.plans_lock:
            self.auto_exec.plans[plan.plan_id] = plan
        
        # Mock MT5: order no longer exists and no matching position (cancelled)
        with patch('MetaTrader5.orders_get', return_value=None):
            with patch('MetaTrader5.positions_get', return_value=[]):
                with patch.object(self.auto_exec, '_update_plan_status') as mock_update:
                    self.auto_exec._check_pending_orders()
                    
                    # Verify plan status was updated to cancelled
                    with self.auto_exec.plans_lock:
                        # Plan should be removed from memory after cancellation
                        self.assertNotIn("test_plan_3", self.auto_exec.plans)
                    
                    # Verify status was updated
                    mock_update.assert_called_once()
                    # Check that cancellation_reason was set
                    call_args = mock_update.call_args[0][0]
                    self.assertEqual(call_args.status, "cancelled")
                    self.assertIsNotNone(call_args.cancellation_reason)
    
    def test_check_pending_orders_plan_removed_during_check(self):
        """Test _check_pending_orders() when plan is removed during check"""
        # Create a plan with pending order
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
            pending_order_ticket=12348
        )
        
        with self.auto_exec.plans_lock:
            self.auto_exec.plans[plan.plan_id] = plan
        
        # Remove plan after copying plan_ids (simulating race condition)
        def remove_plan_after_copy(*args, **kwargs):
            with self.auto_exec.plans_lock:
                if "test_plan_4" in self.auto_exec.plans:
                    del self.auto_exec.plans["test_plan_4"]
            return None
        
        with patch('MetaTrader5.orders_get', side_effect=remove_plan_after_copy):
            # Should handle gracefully without errors
            self.auto_exec._check_pending_orders()
            # No exceptions should be raised
    
    def test_check_pending_orders_multiple_positions_matched(self):
        """Test _check_pending_orders() when multiple positions match"""
        # Create a plan with pending order
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
            status="pending_order_placed",
            pending_order_ticket=12349
        )
        
        with self.auto_exec.plans_lock:
            self.auto_exec.plans[plan.plan_id] = plan
        
        # Mock MT5: order no longer exists, multiple positions match
        mock_position1 = Mock()
        mock_position1.ticket = 99998
        mock_position1.type = 0  # ORDER_TYPE_BUY
        mock_position1.price_open = 2000.0
        mock_position1.volume = 0.01
        mock_position1.time = datetime.now(timezone.utc).timestamp() - 100  # Older
        
        mock_position2 = Mock()
        mock_position2.ticket = 99999
        mock_position2.type = 0  # ORDER_TYPE_BUY
        mock_position2.price_open = 2000.0
        mock_position2.volume = 0.01
        mock_position2.time = datetime.now(timezone.utc).timestamp()  # Newer
        
        with patch('MetaTrader5.orders_get', return_value=None):
            with patch('MetaTrader5.positions_get', return_value=[mock_position1, mock_position2]):
                with patch.object(self.auto_exec, '_handle_post_execution') as mock_post_exec:
                    with patch.object(self.auto_exec, '_update_plan_status') as mock_update:
                        self.auto_exec._check_pending_orders()
                        
                        # Should use most recent position (mock_position2)
                        mock_post_exec.assert_called_once()
                        # Verify the most recent ticket was used
                        call_args = mock_post_exec.call_args[0]
                        result_dict = call_args[1]
                        self.assertEqual(result_dict["details"]["ticket"], 99999)


if __name__ == '__main__':
    unittest.main()
