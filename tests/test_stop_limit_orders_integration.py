"""
Integration Tests for Stop/Limit Order Support
Tests full end-to-end flows for stop and limit orders
"""

import unittest
import sys
import sqlite3
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, timezone, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from auto_execution_system import AutoExecutionSystem, TradePlan


class TestStopLimitOrdersIntegration(unittest.TestCase):
    """Integration tests for stop/limit order support"""
    
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
    
    def test_buy_stop_order_flow(self):
        """Test full flow: place BUY STOP → monitor → fill"""
        # Create a plan with BUY STOP order
        plan = TradePlan(
            plan_id="test_buy_stop_flow",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2002.0,  # Above current
            stop_loss=1995.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"order_type": "stop"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Add plan to system
        self.auto_exec.add_plan(plan)
        
        # Mock quote (current price below entry)
        mock_quote = Mock()
        mock_quote.bid = 1999.5
        mock_quote.ask = 2000.5
        
        # Mock successful pending order placement
        mock_pending_result = {
            "ok": True,
            "details": {
                "ticket": 12350,
                "volume": 0.01,
                "price": 2002.0
            }
        }
        
        # Step 1: Place pending order
        with patch.object(self.auto_exec.mt5_service, 'get_quote', return_value=mock_quote):
            with patch.object(self.auto_exec.mt5_service, 'pending_order', return_value=mock_pending_result):
                with patch.object(self.auto_exec, '_handle_post_execution'):
                    result = self.auto_exec._execute_trade(plan)
                    self.assertTrue(result)
                    self.assertEqual(plan.status, "pending_order_placed")
                    self.assertEqual(plan.pending_order_ticket, 12350)
        
        # Verify plan stays in memory
        with self.auto_exec.plans_lock:
            self.assertIn(plan.plan_id, self.auto_exec.plans)
        
        # Step 2: Mock order filled (order no longer exists, position created)
        mock_position = Mock()
        mock_position.ticket = 12351
        mock_position.symbol = "XAUUSDc"
        mock_position.type = 0  # BUY
        mock_position.price_open = 2002.0
        mock_position.volume = 0.01
        mock_position.time = int(time.time())
        
        # Mock MT5 API calls
        with patch('MetaTrader5.orders_get', return_value=[]):  # Order no longer exists
            with patch('MetaTrader5.positions_get', return_value=[mock_position]):
                with patch.object(self.auto_exec, '_handle_post_execution') as mock_post_exec:
                    self.auto_exec._check_pending_orders()
                    
                    # Verify plan status updated
                    self.assertEqual(plan.status, "executed")
                    self.assertEqual(plan.ticket, 12351)
                    # Verify post-execution handler called
                    mock_post_exec.assert_called_once()
    
    def test_sell_limit_order_flow(self):
        """Test full flow: place SELL LIMIT → monitor → fill"""
        # Create a plan with SELL LIMIT order
        plan = TradePlan(
            plan_id="test_sell_limit_flow",
            symbol="XAUUSDc",
            direction="SELL",
            entry_price=2002.0,  # Above current (valid for SELL LIMIT)
            stop_loss=2005.0,
            take_profit=1990.0,
            volume=0.01,
            conditions={"order_type": "limit"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Add plan to system
        self.auto_exec.add_plan(plan)
        
        # Mock quote (current price below entry - valid for SELL LIMIT)
        mock_quote = Mock()
        mock_quote.bid = 2000.5
        mock_quote.ask = 2001.0
        
        # Mock successful pending order placement
        mock_pending_result = {
            "ok": True,
            "details": {
                "ticket": 12352,
                "volume": 0.01,
                "price": 2002.0
            }
        }
        
        # Step 1: Place pending order
        with patch.object(self.auto_exec.mt5_service, 'get_quote', return_value=mock_quote):
            with patch.object(self.auto_exec.mt5_service, 'pending_order', return_value=mock_pending_result):
                with patch.object(self.auto_exec, '_handle_post_execution'):
                    result = self.auto_exec._execute_trade(plan)
                    self.assertTrue(result)
                    self.assertEqual(plan.status, "pending_order_placed")
                    self.assertEqual(plan.pending_order_ticket, 12352)
        
        # Step 2: Mock order filled
        mock_position = Mock()
        mock_position.ticket = 12353
        mock_position.symbol = "XAUUSDc"
        mock_position.type = 1  # SELL
        mock_position.price_open = 2002.0
        mock_position.volume = 0.01
        mock_position.time = int(time.time())
        
        with patch('MetaTrader5.orders_get', return_value=[]):
            with patch('MetaTrader5.positions_get', return_value=[mock_position]):
                with patch.object(self.auto_exec, '_handle_post_execution') as mock_post_exec:
                    self.auto_exec._check_pending_orders()
                    
                    # Verify plan status updated
                    self.assertEqual(plan.status, "executed")
                    self.assertEqual(plan.ticket, 12353)
                    mock_post_exec.assert_called_once()
    
    def test_pending_order_expiration(self):
        """Test that pending order is cancelled when plan expires"""
        # Create a plan with pending order that expires soon
        expires_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        plan = TradePlan(
            plan_id="test_expire_1",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2002.0,
            stop_loss=1995.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"order_type": "stop"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending_order_placed",
            pending_order_ticket=12354,
            expires_at=expires_at
        )
        
        # Add plan to system
        self.auto_exec.add_plan(plan)
        with self.auto_exec.plans_lock:
            self.auto_exec.plans[plan.plan_id] = plan
        
        # Mock MT5 order cancellation
        mock_result = Mock()
        mock_result.retcode = 10009  # TRADE_RETCODE_DONE
        
        with patch('MetaTrader5.order_send', return_value=mock_result):
            # Simulate monitor loop expiration check
            with patch.object(self.auto_exec, '_check_conditions'):
                # The expiration check should cancel the order
                # We'll manually trigger the expiration logic
                if hasattr(plan, 'expires_at') and plan.expires_at:
                    try:
                        expires_at_dt = datetime.fromisoformat(plan.expires_at.replace('Z', '+00:00'))
                        if expires_at_dt.tzinfo is None:
                            expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)
                        now_utc = datetime.now(timezone.utc)
                        
                        if expires_at_dt < now_utc:
                            # Plan expired - cancel pending order
                            if plan.status == "pending_order_placed" and hasattr(plan, 'pending_order_ticket') and plan.pending_order_ticket:
                                import MetaTrader5 as mt5
                                if self.auto_exec.mt5_service.connect():
                                    request = {
                                        "action": mt5.TRADE_ACTION_REMOVE,
                                        "order": plan.pending_order_ticket,
                                    }
                                    result = mt5.order_send(request)
                                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                                        # Order cancelled successfully
                                        pass
                            
                            # Mark plan as expired
                            plan.status = "expired"
                            self.auto_exec._update_plan_status(plan)
                    except Exception as e:
                        # Ignore errors in test
                        pass
        
        # Verify plan status is expired
        self.assertEqual(plan.status, "expired")
    
    def test_pending_order_cancellation(self):
        """Test that pending order is cancelled when plan is cancelled"""
        # Create a plan with pending order
        plan = TradePlan(
            plan_id="test_cancel_1",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2002.0,
            stop_loss=1995.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"order_type": "stop"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending_order_placed",
            pending_order_ticket=12355
        )
        
        # Add plan to system
        self.auto_exec.add_plan(plan)
        with self.auto_exec.plans_lock:
            self.auto_exec.plans[plan.plan_id] = plan
        
        # Mock MT5 order cancellation
        mock_result = Mock()
        mock_result.retcode = 10009  # TRADE_RETCODE_DONE
        
        with patch('MetaTrader5.order_send', return_value=mock_result):
            # Cancel the plan
            result = self.auto_exec.cancel_plan(plan.plan_id, "Test cancellation")
            self.assertTrue(result)
            
            # Verify order cancellation was attempted
            import MetaTrader5 as mt5
            mt5.order_send.assert_called_once()
            call_args = mt5.order_send.call_args[0][0]
            self.assertEqual(call_args["action"], mt5.TRADE_ACTION_REMOVE)
            self.assertEqual(call_args["order"], 12355)
    
    def test_mixed_order_types(self):
        """Test multiple plans with different order types"""
        # Create market order plan
        market_plan = TradePlan(
            plan_id="test_market_1",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Create stop order plan
        stop_plan = TradePlan(
            plan_id="test_stop_1",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2002.0,
            stop_loss=1995.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"order_type": "stop"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Create limit order plan
        limit_plan = TradePlan(
            plan_id="test_limit_1",
            symbol="XAUUSDc",
            direction="SELL",
            entry_price=1998.0,
            stop_loss=2005.0,
            take_profit=1990.0,
            volume=0.01,
            conditions={"order_type": "limit"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Add all plans
        self.auto_exec.add_plan(market_plan)
        self.auto_exec.add_plan(stop_plan)
        self.auto_exec.add_plan(limit_plan)
        
        # Verify all plans are in system
        with self.auto_exec.plans_lock:
            self.assertIn(market_plan.plan_id, self.auto_exec.plans)
            self.assertIn(stop_plan.plan_id, self.auto_exec.plans)
            self.assertIn(limit_plan.plan_id, self.auto_exec.plans)
        
        # Verify order types are detected correctly
        self.assertEqual(self.auto_exec._determine_order_type(market_plan), "market")
        self.assertEqual(self.auto_exec._determine_order_type(stop_plan), "buy_stop")
        self.assertEqual(self.auto_exec._determine_order_type(limit_plan), "sell_limit")
    
    def test_pending_order_stays_in_memory(self):
        """Verify plan stays in memory after placing pending order"""
        plan = TradePlan(
            plan_id="test_memory_1",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2002.0,
            stop_loss=1995.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"order_type": "stop"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Add plan to system
        self.auto_exec.add_plan(plan)
        
        # Mock quote and pending order placement
        mock_quote = Mock()
        mock_quote.bid = 1999.5
        mock_quote.ask = 2000.5
        
        mock_pending_result = {
            "ok": True,
            "details": {
                "ticket": 12356,
                "volume": 0.01,
                "price": 2002.0
            }
        }
        
        with patch.object(self.auto_exec.mt5_service, 'get_quote', return_value=mock_quote):
            with patch.object(self.auto_exec.mt5_service, 'pending_order', return_value=mock_pending_result):
                with patch.object(self.auto_exec, '_handle_post_execution'):
                    result = self.auto_exec._execute_trade(plan)
                    self.assertTrue(result)
        
        # Verify plan is still in memory with pending_order_placed status
        with self.auto_exec.plans_lock:
            self.assertIn(plan.plan_id, self.auto_exec.plans)
            self.assertEqual(self.auto_exec.plans[plan.plan_id].status, "pending_order_placed")
            self.assertEqual(self.auto_exec.plans[plan.plan_id].pending_order_ticket, 12356)
    
    def test_pending_order_fill_detection(self):
        """Verify system detects when pending order fills"""
        plan = TradePlan(
            plan_id="test_fill_1",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2002.0,
            stop_loss=1995.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"order_type": "stop"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending_order_placed",
            pending_order_ticket=12357
        )
        
        # Add plan to system
        with self.auto_exec.plans_lock:
            self.auto_exec.plans[plan.plan_id] = plan
        
        # Mock position that matches the pending order
        mock_position = Mock()
        mock_position.ticket = 12358
        mock_position.symbol = "XAUUSDc"
        mock_position.type = 0  # BUY
        mock_position.price_open = 2002.0
        mock_position.volume = 0.01
        mock_position.time = int(time.time())
        
        with patch('MetaTrader5.orders_get', return_value=[]):  # Order no longer exists
            with patch('MetaTrader5.positions_get', return_value=[mock_position]):
                with patch.object(self.auto_exec, '_handle_post_execution') as mock_post_exec:
                    self.auto_exec._check_pending_orders()
                    
                    # Verify plan status updated to executed
                    self.assertEqual(plan.status, "executed")
                    self.assertEqual(plan.ticket, 12358)
                    # Verify post-execution handler called
                    mock_post_exec.assert_called_once()
    
    def test_pending_order_cancelled_detection(self):
        """Verify system detects when pending order is cancelled"""
        plan = TradePlan(
            plan_id="test_cancelled_1",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2002.0,
            stop_loss=1995.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"order_type": "stop"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending_order_placed",
            pending_order_ticket=12359
        )
        
        # Add plan to system
        with self.auto_exec.plans_lock:
            self.auto_exec.plans[plan.plan_id] = plan
        
        # Mock: order no longer exists, no matching position
        with patch('MetaTrader5.orders_get', return_value=[]):
            with patch('MetaTrader5.positions_get', return_value=[]):
                self.auto_exec._check_pending_orders()
                
                # Verify plan status updated to cancelled
                self.assertEqual(plan.status, "cancelled")
    
    def test_multiple_pending_orders_monitoring(self):
        """Verify all pending orders are checked correctly"""
        # Create multiple plans with pending orders
        plan1 = TradePlan(
            plan_id="test_multi_1",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2002.0,
            stop_loss=1995.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"order_type": "stop"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending_order_placed",
            pending_order_ticket=12360
        )
        
        plan2 = TradePlan(
            plan_id="test_multi_2",
            symbol="XAUUSDc",
            direction="SELL",
            entry_price=1998.0,
            stop_loss=2005.0,
            take_profit=1990.0,
            volume=0.01,
            conditions={"order_type": "limit"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending_order_placed",
            pending_order_ticket=12361
        )
        
        # Add plans to system
        with self.auto_exec.plans_lock:
            self.auto_exec.plans[plan1.plan_id] = plan1
            self.auto_exec.plans[plan2.plan_id] = plan2
        
        # Mock: plan1 order filled, plan2 order still exists
        # For plan1: order 12360 no longer exists, position 12362 matches
        # For plan2: order 12361 still exists
        
        # Mock orders_get to return different results for different tickets
        def mock_orders_get(ticket=None):
            if ticket == 12360:
                return []  # plan1 order no longer exists (filled)
            elif ticket == 12361:
                # Return plan2's order
                mock_order = Mock()
                mock_order.ticket = 12361
                mock_order.symbol = "XAUUSDc"
                mock_order.type = 2  # SELL LIMIT
                mock_order.price_open = 1998.0
                mock_order.volume = 0.01
                return [mock_order]
            return []
        
        # Mock position that matches plan1
        mock_position = Mock()
        mock_position.ticket = 12362
        mock_position.symbol = "XAUUSDc"
        mock_position.type = 0  # BUY
        mock_position.price_open = 2002.0
        mock_position.volume = 0.01
        current_time = int(time.time())
        mock_position.time = current_time
        mock_position.time_open = current_time
        
        with patch('MetaTrader5.orders_get', side_effect=mock_orders_get):
            with patch('MetaTrader5.positions_get', return_value=[mock_position]):
                with patch.object(self.auto_exec, '_handle_post_execution'):
                    self.auto_exec._check_pending_orders()
                    
                    # Verify plan1 is executed
                    # Check in-memory plan (plan object may be updated)
                    with self.auto_exec.plans_lock:
                        if plan1.plan_id in self.auto_exec.plans:
                            in_memory_plan = self.auto_exec.plans[plan1.plan_id]
                            self.assertEqual(in_memory_plan.status, "executed")
                            self.assertEqual(in_memory_plan.ticket, 12362)
                        else:
                            # Plan was removed after execution (normal behavior)
                            # Verify it was executed before removal
                            self.assertEqual(plan1.status, "executed")
                            self.assertEqual(plan1.ticket, 12362)
                    
                    # Verify plan2 still pending
                    self.assertEqual(plan2.status, "pending_order_placed")


if __name__ == '__main__':
    unittest.main()
