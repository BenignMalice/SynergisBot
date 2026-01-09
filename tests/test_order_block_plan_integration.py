"""
Test Order Block Plan Integration
Tests the complete order block plan creation, monitoring, and execution flow.
"""

import unittest
from unittest.mock import MagicMock, Mock, patch
from datetime import datetime, timedelta
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from chatgpt_auto_execution_integration import ChatGPTAutoExecution
from auto_execution_system import TradePlan
from infra.custom_alerts import CustomAlertManager
from infra.alert_monitor import AlertMonitor


class TestOrderBlockPlanIntegration(unittest.TestCase):
    """Test order block plan creation and monitoring"""
    
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
    
    def test_create_order_block_plan_bullish(self):
        """Test creating a bullish order block plan"""
        result = self.auto_execution.create_order_block_plan(
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=4080.0,
            stop_loss=4070.0,
            take_profit=4100.0,
            volume=0.01,
            order_block_type="bull",
            min_validation_score=60,
            expires_hours=24,
            notes="Test bullish OB plan"
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
        self.assertEqual(plan.conditions['order_block'], True)
        self.assertEqual(plan.conditions['order_block_type'], "bull")
        self.assertEqual(plan.conditions['min_validation_score'], 60)
        self.assertEqual(plan.conditions['timeframe'], "M1")
        self.assertIn('price_near', plan.conditions)
        self.assertIn('tolerance', plan.conditions)
    
    def test_create_order_block_plan_bearish(self):
        """Test creating a bearish order block plan"""
        result = self.auto_execution.create_order_block_plan(
            symbol="BTCUSDc",
            direction="SELL",
            entry_price=93000.0,
            stop_loss=93200.0,
            take_profit=92500.0,
            volume=0.01,
            order_block_type="bear",
            min_validation_score=70,
            expires_hours=12,
            notes="Test bearish OB plan"
        )
        
        # Verify plan was created
        self.assertTrue(result['success'])
        
        # Verify plan details
        plan = self.mock_auto_system.add_plan.call_args[0][0]
        self.assertEqual(plan.symbol, "BTCUSDc")
        self.assertEqual(plan.direction, "SELL")
        self.assertEqual(plan.conditions['order_block_type'], "bear")
        self.assertEqual(plan.conditions['min_validation_score'], 70)
    
    def test_create_order_block_plan_auto_detect(self):
        """Test creating an order block plan with auto-detect direction"""
        result = self.auto_execution.create_order_block_plan(
            symbol="EURUSDc",
            direction="BUY",
            entry_price=1.0800,
            stop_loss=1.0750,
            take_profit=1.0850,
            order_block_type="auto"
        )
        
        # Verify plan was created
        self.assertTrue(result['success'])
        
        # Verify auto-detect is set
        plan = self.mock_auto_system.add_plan.call_args[0][0]
        self.assertEqual(plan.conditions['order_block_type'], "auto")
        # Auto should match plan direction (BUY → bullish OB expected)
    
    def test_order_block_plan_conditions_structure(self):
        """Test that order block plan conditions are properly structured"""
        result = self.auto_execution.create_order_block_plan(
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=4080.0,
            stop_loss=4070.0,
            take_profit=4100.0
        )
        
        plan = self.mock_auto_system.add_plan.call_args[0][0]
        conditions = plan.conditions
        
        # Verify all required conditions are present
        self.assertTrue(conditions['order_block'])
        self.assertIn('order_block_type', conditions)
        self.assertIn('min_validation_score', conditions)
        self.assertIn('price_near', conditions)
        self.assertIn('tolerance', conditions)
        self.assertEqual(conditions['timeframe'], "M1")
        
        # Verify default values
        self.assertEqual(conditions['min_validation_score'], 60)
        self.assertEqual(conditions['order_block_type'], "auto")
    
    def test_order_block_plan_price_tolerance_auto_calculation(self):
        """Test that price tolerance is auto-calculated for different symbols"""
        # Test XAUUSD (should use 5.0)
        result1 = self.auto_execution.create_order_block_plan(
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=4080.0,
            stop_loss=4070.0,
            take_profit=4100.0
        )
        plan1 = self.mock_auto_system.add_plan.call_args[0][0]
        tolerance1 = plan1.conditions['tolerance']
        self.assertIsNotNone(tolerance1)
        
        # Test BTCUSD (should use 100.0)
        result2 = self.auto_execution.create_order_block_plan(
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=93000.0,
            stop_loss=92000.0,
            take_profit=94000.0
        )
        plan2 = self.mock_auto_system.add_plan.call_args[0][0]
        tolerance2 = plan2.conditions['tolerance']
        self.assertIsNotNone(tolerance2)
        
        # BTCUSD tolerance should be larger than XAUUSD
        self.assertGreater(tolerance2, tolerance1)
    
    def test_order_block_plan_notes_generation(self):
        """Test that plan notes are properly generated"""
        result = self.auto_execution.create_order_block_plan(
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=4080.0,
            stop_loss=4070.0,
            take_profit=4100.0,
            order_block_type="bull",
            min_validation_score=65
        )
        
        plan = self.mock_auto_system.add_plan.call_args[0][0]
        
        # Verify notes contain key information
        self.assertIn("Order block", plan.notes)
        self.assertIn("BULL", plan.notes.upper())
        self.assertIn("M1-M5", plan.notes)
        self.assertIn("65", plan.notes)  # min_validation_score
    
    def test_order_block_plan_expiry(self):
        """Test that plan expiry is set correctly"""
        result = self.auto_execution.create_order_block_plan(
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=4080.0,
            stop_loss=4070.0,
            take_profit=4100.0,
            expires_hours=12
        )
        
        plan = self.mock_auto_system.add_plan.call_args[0][0]
        
        # Verify expiry is set
        self.assertIsNotNone(plan.expires_at)
        
        # Verify expiry is approximately 12 hours from now
        expires = datetime.fromisoformat(plan.expires_at)
        now = datetime.now()
        expected_expiry = now + timedelta(hours=12)
        
        # Allow 1 minute tolerance
        time_diff = abs((expires - expected_expiry).total_seconds())
        self.assertLess(time_diff, 60)


class TestOrderBlockPlanConditionChecking(unittest.TestCase):
    """Test order block condition checking in auto-execution system"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock M1 components
        self.mock_m1_analyzer = MagicMock()
        self.mock_m1_data_fetcher = MagicMock()
        self.mock_mt5_service = MagicMock()
        self.mock_session_manager = MagicMock()
        self.mock_asset_profiles = MagicMock()
        self.mock_threshold_manager = MagicMock()
        
        # Mock quote
        mock_quote = Mock()
        mock_quote.bid = 4080.0
        mock_quote.ask = 4081.0
        self.mock_mt5_service.get_quote.return_value = mock_quote
        self.mock_mt5_service.connect.return_value = True
        
        # Create trade plan
        self.plan = TradePlan(
            plan_id="test_ob_plan",
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
                "tolerance": 5.0,
                "timeframe": "M1"
            },
            created_at=datetime.now().isoformat(),
            created_by="test",
            status="pending"
        )
    
    def test_order_block_condition_checking_missing_m1_components(self):
        """Test that condition checking fails gracefully when M1 components are missing"""
        from auto_execution_system import AutoExecutionSystem
        
        # Create system without M1 components
        system = AutoExecutionSystem(
            mt5_service=self.mock_mt5_service,
            m1_analyzer=None,
            m1_data_fetcher=None
        )
        
        # Check conditions should return False
        result = system._check_conditions(self.plan)
        self.assertFalse(result)
    
    def test_order_block_condition_checking_insufficient_data(self):
        """Test that condition checking handles insufficient M1 data"""
        from auto_execution_system import AutoExecutionSystem
        
        # Mock insufficient data
        self.mock_m1_data_fetcher.fetch_m1_data.return_value = []  # Empty data
        
        system = AutoExecutionSystem(
            mt5_service=self.mock_mt5_service,
            m1_analyzer=self.mock_m1_analyzer,
            m1_data_fetcher=self.mock_m1_data_fetcher
        )
        
        result = system._check_conditions(self.plan)
        self.assertFalse(result)
    
    def test_order_block_condition_checking_no_order_blocks(self):
        """Test that condition checking handles when no order blocks are detected"""
        from auto_execution_system import AutoExecutionSystem
        
        # Mock M1 data
        m1_candles = [{'open': 4075.0, 'high': 4085.0, 'low': 4070.0, 'close': 4080.0, 'volume': 100} for _ in range(100)]
        self.mock_m1_data_fetcher.fetch_m1_data.return_value = m1_candles
        
        # Mock M1 analysis with no order blocks
        m1_analysis = {
            'available': True,
            'order_blocks': []  # No order blocks
        }
        self.mock_m1_analyzer.analyze_microstructure.return_value = m1_analysis
        
        system = AutoExecutionSystem(
            mt5_service=self.mock_mt5_service,
            m1_analyzer=self.mock_m1_analyzer,
            m1_data_fetcher=self.mock_m1_data_fetcher
        )
        
        result = system._check_conditions(self.plan)
        self.assertFalse(result)
    
    def test_order_block_condition_checking_validation_score_too_low(self):
        """Test that condition checking rejects OBs with validation score below threshold"""
        from auto_execution_system import AutoExecutionSystem
        
        # Mock M1 data
        m1_candles = [{'open': 4075.0, 'high': 4085.0, 'low': 4070.0, 'close': 4080.0, 'volume': 100} for _ in range(200)]
        self.mock_m1_data_fetcher.fetch_m1_data.return_value = m1_candles
        
        # Mock M1 analysis with order block
        m1_analysis = {
            'available': True,
            'order_blocks': [{
                'type': 'BULLISH',
                'price_range': [4075.0, 4085.0],
                'strength': 70
            }]
        }
        self.mock_m1_analyzer.analyze_microstructure.return_value = m1_analysis
        
        # Mock validation result with low score
        mock_alert_monitor = MagicMock()
        mock_validation_result = {
            'valid': True,
            'score': 55  # Below threshold of 60
        }
        mock_alert_monitor._validate_order_block.return_value = mock_validation_result
        
        # Patch AlertMonitor import inside the function
        with patch('infra.alert_monitor.AlertMonitor', return_value=mock_alert_monitor):
            with patch('infra.custom_alerts.CustomAlertManager'):
                system = AutoExecutionSystem(
                    mt5_service=self.mock_mt5_service,
                    m1_analyzer=self.mock_m1_analyzer,
                    m1_data_fetcher=self.mock_m1_data_fetcher
                )
                # Set attributes manually if needed
                system.session_manager = self.mock_session_manager
                system.asset_profiles = self.mock_asset_profiles
                system.threshold_manager = self.mock_threshold_manager
                
                # Mock M5 candles
                import MetaTrader5 as mt5
                with patch('auto_execution_system.mt5') as mock_mt5:
                    mock_mt5.copy_rates_from_pos.return_value = [
                        {'open': 4070.0, 'high': 4090.0, 'low': 4065.0, 'close': 4080.0} for _ in range(20)
                    ]
                    
                    result = system._check_conditions(self.plan)
                    # Should return False because validation score is too low
                    self.assertFalse(result, "Should reject OB with validation score below threshold")


class TestOrderBlockPlanAPI(unittest.TestCase):
    """Test order block plan API endpoints"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_auto_execution = MagicMock()
        self.mock_auto_execution.create_order_block_plan.return_value = {
            'success': True,
            'plan_id': 'test_plan_123',
            'message': 'Order block plan created successfully'
        }
    
    @patch('app.auto_execution_api.get_chatgpt_auto_execution')
    def test_create_order_block_plan_endpoint(self, mock_get_auto_execution):
        """Test the create order block plan API endpoint"""
        import asyncio
        from app.auto_execution_api import OrderBlockPlanRequest, create_order_block_plan
        
        mock_get_auto_execution.return_value = self.mock_auto_execution
        
        # Create request
        request = OrderBlockPlanRequest(
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=4080.0,
            stop_loss=4070.0,
            take_profit=4100.0,
            volume=0.01,
            order_block_type="bull",
            min_validation_score=60,
            expires_hours=24,
            notes="Test OB plan"
        )
        
        # Call endpoint (async) - use asyncio.run for testing
        import asyncio
        result = asyncio.run(create_order_block_plan(request))
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertIn('plan_id', result)
        
        # Verify create_order_block_plan was called with correct parameters
        self.mock_auto_execution.create_order_block_plan.assert_called_once()
        call_args = self.mock_auto_execution.create_order_block_plan.call_args
        
        self.assertEqual(call_args[1]['symbol'], "XAUUSDc")
        self.assertEqual(call_args[1]['direction'], "BUY")
        self.assertEqual(call_args[1]['order_block_type'], "bull")
        self.assertEqual(call_args[1]['min_validation_score'], 60)


if __name__ == '__main__':
    unittest.main()

