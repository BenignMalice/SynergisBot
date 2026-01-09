"""
Test Phase 1.1: Order Type Detection Method
Tests for _determine_order_type() method
"""

import unittest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from auto_execution_system import AutoExecutionSystem, TradePlan


class TestOrderTypeDetection(unittest.TestCase):
    """Test _determine_order_type() method"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create minimal AutoExecutionSystem instance for testing
        # We'll mock the database path to avoid actual DB operations
        import tempfile
        import os
        
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        try:
            self.auto_exec = AutoExecutionSystem(
                db_path=self.temp_db.name,
                mt5_service=None  # We don't need MT5 for this test
            )
        except Exception as e:
            # If initialization fails, we'll skip these tests
            self.skipTest(f"Could not initialize AutoExecutionSystem: {e}")
    
    def tearDown(self):
        """Clean up test fixtures"""
        import os
        import time
        
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
        if hasattr(self, 'temp_db') and os.path.exists(self.temp_db.name):
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
    
    def _create_test_plan(self, direction="BUY", order_type=None):
        """Helper to create a test plan"""
        conditions = {}
        if order_type is not None:
            conditions["order_type"] = order_type
        
        return TradePlan(
            plan_id="test_plan",
            symbol="XAUUSDc",
            direction=direction,
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions=conditions,
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending"
        )
    
    def test_market_order_default(self):
        """Test default behavior - no order_type specified"""
        plan = self._create_test_plan(direction="BUY", order_type=None)
        result = self.auto_exec._determine_order_type(plan)
        self.assertEqual(result, "market")
    
    def test_market_order_explicit(self):
        """Test explicit market order"""
        plan = self._create_test_plan(direction="BUY", order_type="market")
        result = self.auto_exec._determine_order_type(plan)
        self.assertEqual(result, "market")
    
    def test_buy_stop_order(self):
        """Test BUY STOP order type"""
        plan = self._create_test_plan(direction="BUY", order_type="stop")
        result = self.auto_exec._determine_order_type(plan)
        self.assertEqual(result, "buy_stop")
    
    def test_buy_limit_order(self):
        """Test BUY LIMIT order type"""
        plan = self._create_test_plan(direction="BUY", order_type="limit")
        result = self.auto_exec._determine_order_type(plan)
        self.assertEqual(result, "buy_limit")
    
    def test_sell_stop_order(self):
        """Test SELL STOP order type"""
        plan = self._create_test_plan(direction="SELL", order_type="stop")
        result = self.auto_exec._determine_order_type(plan)
        self.assertEqual(result, "sell_stop")
    
    def test_sell_limit_order(self):
        """Test SELL LIMIT order type"""
        plan = self._create_test_plan(direction="SELL", order_type="limit")
        result = self.auto_exec._determine_order_type(plan)
        self.assertEqual(result, "sell_limit")
    
    def test_invalid_order_type(self):
        """Test invalid order_type defaults to market"""
        plan = self._create_test_plan(direction="BUY", order_type="invalid")
        result = self.auto_exec._determine_order_type(plan)
        self.assertEqual(result, "market")
    
    def test_case_insensitive_direction(self):
        """Test that direction is case-insensitive"""
        plan = self._create_test_plan(direction="buy", order_type="stop")
        result = self.auto_exec._determine_order_type(plan)
        self.assertEqual(result, "buy_stop")
        
        plan = self._create_test_plan(direction="sell", order_type="limit")
        result = self.auto_exec._determine_order_type(plan)
        self.assertEqual(result, "sell_limit")
    
    def test_none_order_type(self):
        """Test None order_type defaults to market"""
        plan = self._create_test_plan(direction="BUY", order_type=None)
        plan.conditions["order_type"] = None
        result = self.auto_exec._determine_order_type(plan)
        self.assertEqual(result, "market")
    
    def test_no_conditions_dict(self):
        """Test plan with no conditions dict"""
        plan = TradePlan(
            plan_id="test_plan",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions=None,  # No conditions
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="pending"
        )
        result = self.auto_exec._determine_order_type(plan)
        self.assertEqual(result, "market")


if __name__ == '__main__':
    unittest.main()
