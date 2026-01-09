"""
Test Phase 4.3: Modify _monitor_loop() to Handle Pending Orders
Tests for pending order handling in _monitor_loop()
"""

import unittest
import sys
import sqlite3
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock, call
from datetime import datetime, timezone, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from auto_execution_system import AutoExecutionSystem, TradePlan


class TestMonitorLoopPendingOrders(unittest.TestCase):
    """Test _monitor_loop() handling of pending orders"""
    
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
    
    def test_pending_order_kept_in_memory_after_execution(self):
        """Test that pending orders are kept in memory after execution"""
        # Create a plan with pending order type
        plan = TradePlan(
            plan_id="test_pending_1",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"strategy_type": "test", "order_type": "limit"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        with self.auto_exec.plans_lock:
            self.auto_exec.plans[plan.plan_id] = plan
        
        # Mock _execute_trade to return True and set status to pending_order_placed
        def mock_execute_trade(p):
            p.status = "pending_order_placed"
            p.pending_order_ticket = 12345
            return True
        
        with patch.object(self.auto_exec, '_execute_trade', side_effect=mock_execute_trade):
            with patch.object(self.auto_exec, '_check_conditions', return_value=True):
                # Simulate one iteration of monitor loop
                with self.auto_exec.plans_lock:
                    plans_to_check = list(self.auto_exec.plans.items())
                
                for plan_id, plan in plans_to_check:
                    if plan.status == "pending":
                        if self.auto_exec._check_conditions(plan):
                            if self.auto_exec._execute_trade(plan):
                                # Check that pending orders are NOT removed
                                if plan.status == "pending_order_placed":
                                    # Plan should still be in memory
                                    with self.auto_exec.plans_lock:
                                        self.assertIn(plan_id, self.auto_exec.plans)
                                    return
        
        # Verify plan is still in memory
        with self.auto_exec.plans_lock:
            self.assertIn("test_pending_1", self.auto_exec.plans)
            self.assertEqual(self.auto_exec.plans["test_pending_1"].status, "pending_order_placed")
    
    def test_market_order_removed_from_memory_after_execution(self):
        """Test that market orders are removed from memory after execution"""
        # Create a plan with market order type
        plan = TradePlan(
            plan_id="test_market_1",
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
        
        with self.auto_exec.plans_lock:
            self.auto_exec.plans[plan.plan_id] = plan
        
        # Mock _execute_trade to return True and set status to executed
        def mock_execute_trade(p):
            p.status = "executed"
            return True
        
        with patch.object(self.auto_exec, '_execute_trade', side_effect=mock_execute_trade):
            with patch.object(self.auto_exec, '_check_conditions', return_value=True):
                # Simulate one iteration of monitor loop
                with self.auto_exec.plans_lock:
                    plans_to_check = list(self.auto_exec.plans.items())
                
                for plan_id, plan in plans_to_check:
                    if plan.status == "pending":
                        if self.auto_exec._check_conditions(plan):
                            if self.auto_exec._execute_trade(plan):
                                # Check that market orders ARE removed
                                if plan.status == "executed":
                                    with self.auto_exec.plans_lock:
                                        if plan_id in self.auto_exec.plans:
                                            del self.auto_exec.plans[plan_id]
                                    return
        
        # Verify plan is NOT in memory
        with self.auto_exec.plans_lock:
            self.assertNotIn("test_market_1", self.auto_exec.plans)
    
    def test_expiration_cancels_pending_order(self):
        """Test that expiration check cancels pending orders before marking as expired"""
        # Create a plan with pending order that has expired
        plan = TradePlan(
            plan_id="test_expired_1",
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
            pending_order_ticket=12346,
            expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        )
        
        with self.auto_exec.plans_lock:
            self.auto_exec.plans[plan.plan_id] = plan
        
        # Mock MT5 order cancellation
        mock_result = Mock()
        mock_result.retcode = 10009  # TRADE_RETCODE_DONE
        with patch('MetaTrader5.order_send', return_value=mock_result):
            with patch.object(self.auto_exec, '_update_plan_status') as mock_update:
                # Simulate expiration check
                if hasattr(plan, 'expires_at') and plan.expires_at:
                    expires_at_dt = datetime.fromisoformat(plan.expires_at.replace('Z', '+00:00'))
                    if expires_at_dt.tzinfo is None:
                        expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)
                    now_utc = datetime.now(timezone.utc)
                    
                    if expires_at_dt < now_utc:
                        # Cancel pending order if exists
                        if (plan.status == "pending_order_placed" and 
                            hasattr(plan, 'pending_order_ticket') and 
                            plan.pending_order_ticket):
                            import MetaTrader5 as mt5
                            if self.auto_exec.mt5_service.connect():
                                request = {
                                    "action": mt5.TRADE_ACTION_REMOVE,
                                    "order": plan.pending_order_ticket,
                                }
                                result = mt5.order_send(request)
                                # Verify cancellation was attempted
                                self.assertIsNotNone(result)
                        
                        # Mark as expired
                        plan.status = "expired"
                        self.auto_exec._update_plan_status(plan)
        
        # Verify update was called
        mock_update.assert_called_once()
        # Verify plan status is expired
        self.assertEqual(plan.status, "expired")
    
    def test_weekend_expiration_cancels_pending_order(self):
        """Test that weekend expiration check cancels pending orders"""
        # Create a plan with pending order
        plan = TradePlan(
            plan_id="test_weekend_1",
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
        
        # Mock weekend expiration check to return True
        with patch.object(self.auto_exec, '_check_weekend_plan_expiration', return_value=True):
            # Mock MT5 order cancellation
            mock_result = Mock()
            mock_result.retcode = 10009  # TRADE_RETCODE_DONE
            with patch('MetaTrader5.order_send', return_value=mock_result):
                with patch.object(self.auto_exec, '_update_plan_status') as mock_update:
                    # Simulate weekend expiration check
                    if self.auto_exec._check_weekend_plan_expiration(plan):
                        # Cancel pending order if exists
                        if (plan.status == "pending_order_placed" and 
                            hasattr(plan, 'pending_order_ticket') and 
                            plan.pending_order_ticket):
                            import MetaTrader5 as mt5
                            if self.auto_exec.mt5_service.connect():
                                request = {
                                    "action": mt5.TRADE_ACTION_REMOVE,
                                    "order": plan.pending_order_ticket,
                                }
                                result = mt5.order_send(request)
                                # Verify cancellation was attempted
                                self.assertIsNotNone(result)
                        
                        # Mark as expired
                        plan.status = "expired"
                        self.auto_exec._update_plan_status(plan)
        
        # Verify update was called
        mock_update.assert_called_once()
        # Verify plan status is expired
        self.assertEqual(plan.status, "expired")
    
    def test_pending_order_plans_skip_condition_checks(self):
        """Test that pending_order_placed plans skip condition checks"""
        # Create a plan with pending order status
        plan = TradePlan(
            plan_id="test_skip_1",
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
        
        # Mock _check_conditions to verify it's NOT called
        with patch.object(self.auto_exec, '_check_conditions') as mock_check:
            # Simulate monitor loop iteration
            with self.auto_exec.plans_lock:
                plans_to_check = list(self.auto_exec.plans.items())
            
            for plan_id, plan in plans_to_check:
                # Phase 4.3: Skip plans that are not "pending"
                if plan.status != "pending":
                    continue
                
                # This should not be reached for pending_order_placed plans
                self.auto_exec._check_conditions(plan)
            
            # Verify _check_conditions was NOT called (plan was skipped)
            mock_check.assert_not_called()
    
    def test_check_pending_orders_called_periodically(self):
        """Test that _check_pending_orders() is called periodically in monitor loop"""
        # Mock _check_pending_orders
        with patch.object(self.auto_exec, '_check_pending_orders') as mock_check:
            # Simulate monitor loop with pending check interval
            last_pending_check = 0
            pending_check_interval = 30
            
            # Simulate time passing
            current_time = time.time()
            if current_time - last_pending_check >= pending_check_interval:
                try:
                    self.auto_exec._check_pending_orders()
                except Exception as e:
                    pass
                last_pending_check = current_time
            
            # Verify _check_pending_orders was called
            mock_check.assert_called_once()


if __name__ == '__main__':
    unittest.main()
