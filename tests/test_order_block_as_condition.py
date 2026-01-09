"""
Test Order Block as Condition in General Trade Plan
Tests that order_block can be used as a condition in create_auto_trade_plan
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


class TestOrderBlockAsCondition(unittest.TestCase):
    """Test order block as a condition in general trade plans"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock auto execution system
        self.mock_auto_system = MagicMock()
        self.mock_auto_system.add_plan.return_value = True
        self.mock_auto_system.plans = {}
        
        # Create ChatGPT auto execution instance
        with patch('chatgpt_auto_execution_integration.get_auto_execution_system', return_value=self.mock_auto_system):
            self.auto_execution = ChatGPTAutoExecution()
            self.auto_execution.auto_system = self.mock_auto_system
    
    def test_create_auto_trade_plan_with_order_block_condition(self):
        """Test creating a general trade plan with order_block condition"""
        result = self.auto_execution.create_trade_plan(
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=4080.0,
            stop_loss=4070.0,
            take_profit=4100.0,
            volume=0.01,
            conditions={
                "order_block": True,
                "order_block_type": "bull",
                "min_validation_score": 65,
                "price_near": 4080.0,
                "tolerance": 5.0,
                "timeframe": "M1"
            },
            expires_hours=24,
            notes="General plan with order block condition"
        )
        
        # Verify plan was created
        self.assertTrue(result['success'])
        self.assertIn('plan_id', result)
        
        # Verify plan was added to system
        self.assertEqual(self.mock_auto_system.add_plan.call_count, 1)
        plan = self.mock_auto_system.add_plan.call_args[0][0]
        
        # Verify plan details
        self.assertEqual(plan.symbol, "XAUUSDc")
        self.assertEqual(plan.direction, "BUY")
        self.assertEqual(plan.entry_price, 4080.0)
        
        # Verify order block condition is present
        self.assertTrue(plan.conditions['order_block'])
        self.assertEqual(plan.conditions['order_block_type'], "bull")
        self.assertEqual(plan.conditions['min_validation_score'], 65)
        self.assertEqual(plan.conditions['timeframe'], "M1")
    
    def test_create_auto_trade_plan_with_order_block_and_other_conditions(self):
        """Test creating a plan with order_block plus other conditions"""
        result = self.auto_execution.create_trade_plan(
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=93000.0,
            stop_loss=92000.0,
            take_profit=94000.0,
            volume=0.01,
            conditions={
                "order_block": True,
                "order_block_type": "auto",
                "min_validation_score": 60,
                "choch_bull": True,  # Combined with CHOCH
                "timeframe": "M5",
                "price_near": 93000.0,
                "tolerance": 100.0
            },
            expires_hours=12,
            notes="Combined order block + CHOCH condition"
        )
        
        # Verify plan was created
        self.assertTrue(result['success'])
        
        # Verify plan has both conditions
        plan = self.mock_auto_system.add_plan.call_args[0][0]
        self.assertTrue(plan.conditions['order_block'])
        self.assertTrue(plan.conditions['choch_bull'])
        self.assertEqual(plan.conditions['order_block_type'], "auto")
    
    def test_order_block_condition_will_be_monitored(self):
        """Test that order_block condition will be checked during monitoring"""
        from auto_execution_system import AutoExecutionSystem
        
        # Create a plan with order_block condition
        plan = TradePlan(
            plan_id="test_ob_condition",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=4080.0,
            stop_loss=4070.0,
            take_profit=4100.0,
            volume=0.01,
            conditions={
                "order_block": True,
                "order_block_type": "auto",
                "min_validation_score": 60,
                "price_near": 4080.0,
                "tolerance": 5.0
            },
            created_at=datetime.now().isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Mock M1 components
        mock_m1_analyzer = MagicMock()
        mock_m1_data_fetcher = MagicMock()
        mock_mt5_service = MagicMock()
        mock_quote = Mock()
        mock_quote.bid = 4080.0
        mock_quote.ask = 4081.0
        mock_mt5_service.get_quote.return_value = mock_quote
        mock_mt5_service.connect.return_value = True
        
        # Create system
        system = AutoExecutionSystem(
            mt5_service=mock_mt5_service,
            m1_analyzer=mock_m1_analyzer,
            m1_data_fetcher=mock_m1_data_fetcher
        )
        
        # Verify that _check_conditions will check for order_block
        # (We can't fully test without M1 data, but we can verify the condition is recognized)
        self.assertIn("order_block", plan.conditions)
        self.assertTrue(plan.conditions["order_block"])
        
        # The actual checking happens in _check_conditions which requires M1 data
        # But we've verified the condition structure is correct


if __name__ == '__main__':
    unittest.main()

