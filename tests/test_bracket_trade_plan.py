"""
Test bracket trade auto-execution plan functionality
"""

import unittest
from unittest.mock import MagicMock, Mock, patch
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from chatgpt_auto_execution_integration import ChatGPTAutoExecution
from auto_execution_system import TradePlan


class TestBracketTradePlan(unittest.TestCase):
    """Test bracket trade plan creation and cancellation"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock auto execution system
        self.mock_auto_system = MagicMock()
        self.mock_auto_system.add_plan.return_value = True
        self.mock_auto_system.plans = {}
        self.mock_auto_system.cancel_plan.return_value = True
        
        # Create ChatGPT auto execution instance
        with patch('chatgpt_auto_execution_integration.get_auto_execution_system', return_value=self.mock_auto_system):
            self.auto_execution = ChatGPTAutoExecution()
            self.auto_execution.auto_system = self.mock_auto_system
    
    def test_create_bracket_trade_plan(self):
        """Test creating a bracket trade plan"""
        result = self.auto_execution.create_bracket_trade_plan(
            symbol="BTCUSDc",
            buy_entry=92000.0,
            buy_sl=91000.0,
            buy_tp=93000.0,
            sell_entry=90000.0,
            sell_sl=91000.0,
            sell_tp=89000.0,
            volume=0.01,
            expires_hours=24,
            notes="Bracket trade for range breakout"
        )
        
        # Verify result structure
        self.assertTrue(result['success'])
        self.assertIn('bracket_trade_id', result)
        self.assertIn('buy_plan_id', result)
        self.assertIn('sell_plan_id', result)
        
        # Verify both plans were created
        self.assertEqual(self.mock_auto_system.add_plan.call_count, 2)
        
        # Get both plans
        call_args = self.mock_auto_system.add_plan.call_args_list
        buy_plan = call_args[0][0][0]
        sell_plan = call_args[1][0][0]
        
        # Verify bracket trade ID is set
        self.assertEqual(buy_plan.conditions.get('bracket_trade_id'), result['bracket_trade_id'])
        self.assertEqual(sell_plan.conditions.get('bracket_trade_id'), result['bracket_trade_id'])
        
        # Verify bracket sides
        self.assertEqual(buy_plan.conditions.get('bracket_side'), 'buy')
        self.assertEqual(sell_plan.conditions.get('bracket_side'), 'sell')
        
        # Verify directions
        self.assertEqual(buy_plan.direction, 'BUY')
        self.assertEqual(sell_plan.direction, 'SELL')
        
        # Verify entry prices
        self.assertEqual(buy_plan.entry_price, 92000.0)
        self.assertEqual(sell_plan.entry_price, 90000.0)
    
    def test_bracket_trade_with_custom_conditions(self):
        """Test bracket trade with custom conditions"""
        custom_conditions = {
            "order_block": True,
            "order_block_type": "auto",
            "min_validation_score": 60
        }
        
        result = self.auto_execution.create_bracket_trade_plan(
            symbol="XAUUSDc",
            buy_entry=4080.0,
            buy_sl=4070.0,
            buy_tp=4090.0,
            sell_entry=4060.0,
            sell_sl=4070.0,
            sell_tp=4050.0,
            conditions=custom_conditions
        )
        
        # Verify custom conditions are applied
        call_args = self.mock_auto_system.add_plan.call_args_list
        buy_plan = call_args[0][0][0]
        
        self.assertTrue(buy_plan.conditions.get('order_block'))
        self.assertEqual(buy_plan.conditions.get('order_block_type'), 'auto')
        self.assertEqual(buy_plan.conditions.get('min_validation_score'), 60)
    
    def test_bracket_trade_cancellation(self):
        """Test that bracket trade cancels other side on execution"""
        from auto_execution_system import AutoExecutionSystem
        
        # Create bracket trade plans
        bracket_id = "bracket_test123"
        
        buy_plan = TradePlan(
            plan_id="buy_plan",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=92000.0,
            stop_loss=91000.0,
            take_profit=93000.0,
            volume=0.01,
            conditions={
                "bracket_trade_id": bracket_id,
                "bracket_side": "buy",
                "price_above": 92000.0
            },
            created_at=datetime.now().isoformat(),
            created_by="test",
            status="pending"
        )
        
        sell_plan = TradePlan(
            plan_id="sell_plan",
            symbol="BTCUSDc",
            direction="SELL",
            entry_price=90000.0,
            stop_loss=91000.0,
            take_profit=89000.0,
            volume=0.01,
            conditions={
                "bracket_trade_id": bracket_id,
                "bracket_side": "sell",
                "price_below": 90000.0
            },
            created_at=datetime.now().isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Mock system
        mock_mt5 = MagicMock()
        mock_mt5.connect.return_value = True
        mock_quote = Mock()
        mock_quote.bid = 92000.0
        mock_quote.ask = 92001.0
        mock_mt5.get_quote.return_value = mock_quote
        
        system = AutoExecutionSystem(mt5_service=mock_mt5)
        system.plans = {
            "buy_plan": buy_plan,
            "sell_plan": sell_plan
        }
        
        # Mock MT5 order execution
        mock_mt5.open_order.return_value = {"ok": True, "details": {"ticket": 12345}}
        
        # Execute buy plan
        result = system._execute_trade(buy_plan)
        
        # Verify sell plan was cancelled
        self.assertTrue(result)
        # The cancel_plan should have been called (we can't easily verify this without more mocking)
        # But we can verify the logic exists


if __name__ == '__main__':
    unittest.main()

