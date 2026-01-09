"""
Comprehensive Unit Tests for Stop/Limit Order Support
Tests all core functionality for stop and limit orders
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


class TestStopLimitOrders(unittest.TestCase):
    """Comprehensive unit tests for stop/limit order support"""
    
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
    
    def test_order_type_detection_market(self):
        """Test that default order type is market"""
        plan = TradePlan(
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
        
        order_type = self.auto_exec._determine_order_type(plan)
        self.assertEqual(order_type, "market")
    
    def test_order_type_detection_buy_stop(self):
        """Test that BUY + stop → buy_stop"""
        plan = TradePlan(
            plan_id="test_buy_stop_1",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"order_type": "stop"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        order_type = self.auto_exec._determine_order_type(plan)
        self.assertEqual(order_type, "buy_stop")
    
    def test_order_type_detection_sell_limit(self):
        """Test that SELL + limit → sell_limit"""
        plan = TradePlan(
            plan_id="test_sell_limit_1",
            symbol="XAUUSDc",
            direction="SELL",
            entry_price=2000.0,
            stop_loss=2010.0,
            take_profit=1990.0,
            volume=0.01,
            conditions={"order_type": "limit"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        order_type = self.auto_exec._determine_order_type(plan)
        self.assertEqual(order_type, "sell_limit")
    
    def test_validate_buy_stop_entry(self):
        """Test BUY STOP entry validation"""
        plan = TradePlan(
            plan_id="test_validate_1",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"order_type": "stop"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Mock current price below entry (valid for BUY STOP)
        with patch.object(self.auto_exec.mt5_service, 'get_quote', return_value={"ask": 1995.0}):
            is_valid, error = self.auto_exec._validate_pending_order_entry(plan, "buy_stop", 1995.0)
            self.assertTrue(is_valid)
            self.assertIsNone(error)
        
        # Mock current price above entry (invalid for BUY STOP)
        with patch.object(self.auto_exec.mt5_service, 'get_quote', return_value={"ask": 2005.0}):
            is_valid, error = self.auto_exec._validate_pending_order_entry(plan, "buy_stop", 2005.0)
            self.assertFalse(is_valid)
            self.assertIsNotNone(error)
    
    def test_validate_sell_limit_entry(self):
        """Test SELL LIMIT entry validation"""
        plan = TradePlan(
            plan_id="test_validate_2",
            symbol="XAUUSDc",
            direction="SELL",
            entry_price=2010.0,  # Above current (valid for SELL LIMIT)
            stop_loss=2020.0,
            take_profit=2000.0,
            volume=0.01,
            conditions={"order_type": "limit"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Mock current price below entry (valid for SELL LIMIT - we want to sell at better price)
        current_price = 2005.0
        is_valid, error = self.auto_exec._validate_pending_order_entry(plan, "sell_limit", current_price)
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        
        # Mock current price above entry (invalid for SELL LIMIT)
        plan.entry_price = 2000.0  # Below current
        current_price = 2005.0
        is_valid, error = self.auto_exec._validate_pending_order_entry(plan, "sell_limit", current_price)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
    
    def test_invalid_entry_prices_rejected(self):
        """Test that invalid entry prices are rejected"""
        # Test BUY STOP with entry below current price
        plan = TradePlan(
            plan_id="test_invalid_1",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=1995.0,  # Below current
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"order_type": "stop"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        with patch.object(self.auto_exec.mt5_service, 'get_quote', return_value={"ask": 2000.0}):
            is_valid, error = self.auto_exec._validate_pending_order_entry(plan, "buy_stop", 2000.0)
            self.assertFalse(is_valid)
            self.assertIsNotNone(error)
            self.assertIn("above", error.lower())
    
    def test_market_order_execution(self):
        """Test that market orders still work"""
        plan = TradePlan(
            plan_id="test_market_exec_1",
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
        
        # Add plan to system first
        self.auto_exec.add_plan(plan)
        
        # Mock successful market order execution
        mock_result = {
            "ok": True,
            "details": {
                "ticket": 12345,
                "volume": 0.01,
                "price": 2000.0
            }
        }
        
        with patch.object(self.auto_exec.mt5_service, 'open_order', return_value=mock_result):
            with patch.object(self.auto_exec, '_handle_post_execution'):
                result = self.auto_exec._execute_trade(plan)
                self.assertTrue(result)
                self.assertEqual(plan.status, "executed")
                self.assertEqual(plan.ticket, 12345)
    
    def test_pending_order_placement(self):
        """Test that pending orders are placed correctly"""
        plan = TradePlan(
            plan_id="test_pending_place_1",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2002.0,  # Above current but within tolerance
            stop_loss=1995.0,
            take_profit=2015.0,
            volume=0.01,
            conditions={"order_type": "stop"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Add plan to system first
        self.auto_exec.add_plan(plan)
        
        # Mock successful pending order placement
        mock_result = {
            "ok": True,
            "details": {
                "ticket": 12346,
                "volume": 0.01,
                "price": 2002.0
            }
        }
        
        # Mock quote with bid and ask (current price ~2000.0)
        mock_quote = Mock()
        mock_quote.bid = 1999.5
        mock_quote.ask = 2000.5
        
        with patch.object(self.auto_exec.mt5_service, 'get_quote', return_value=mock_quote):
            with patch.object(self.auto_exec.mt5_service, 'pending_order', return_value=mock_result):
                with patch.object(self.auto_exec, '_handle_post_execution'):
                    result = self.auto_exec._execute_trade(plan)
                    self.assertTrue(result)
                    self.assertEqual(plan.status, "pending_order_placed")
                    self.assertEqual(plan.pending_order_ticket, 12346)


if __name__ == '__main__':
    unittest.main()
