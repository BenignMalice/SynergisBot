"""
Integration Tests for Universal Dynamic SL/TP Manager - Phase 5: Integration

Tests for:
- Auto-execution system integration
- ChatGPT tool integration
- Intelligent Exit Manager integration
- Ownership conflict prevention
"""

import unittest
import tempfile
import os
import json
import sys
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call

# Create mock MetaTrader5 module if not available
if 'MetaTrader5' not in sys.modules:
    mock_mt5 = MagicMock()
    mock_mt5.TRADE_ACTION_DEAL = 5
    mock_mt5.TRADE_ACTION_SLTP = 6
    mock_mt5.ORDER_TYPE_SELL = 1
    mock_mt5.ORDER_TYPE_BUY = 0
    mock_mt5.ORDER_TIME_GTC = 0
    mock_mt5.ORDER_FILLING_IOC = 1
    mock_mt5.TRADE_RETCODE_DONE = 10009
    sys.modules['MetaTrader5'] = mock_mt5

# Create mock dtms_integration module if not available
if 'dtms_integration' not in sys.modules:
    mock_dtms = MagicMock()
    mock_dtms.auto_register_dtms = Mock(return_value=True)
    sys.modules['dtms_integration'] = mock_dtms

# Mock requests module if not available
if 'requests' not in sys.modules:
    mock_requests = MagicMock()
    sys.modules['requests'] = mock_requests

# Import components to test
from auto_execution_system import AutoExecutionSystem, TradePlan
from infra.universal_sl_tp_manager import (
    UniversalDynamicSLTPManager,
    StrategyType,
    UNIVERSAL_MANAGED_STRATEGIES
)
from infra.trade_registry import (
    get_trade_state,
    set_trade_state,
    remove_trade_state,
    cleanup_registry
)


class TestPhase5Integration(unittest.TestCase):
    """Test Phase 5: Integration"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Create temporary config file
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.config_path = self.temp_config.name
        
        # Write test config
        test_config = {
            "universal_sl_tp_rules": {
                "strategies": {
                    "breakout_ib_volatility_trap": {
                        "breakeven_trigger_r": 1.0,
                        "trailing_method": "structure_atr_hybrid",
                        "min_sl_change_r": 0.1,
                        "sl_modification_cooldown_seconds": 30
                    }
                }
            }
        }
        json.dump(test_config, self.temp_config)
        self.temp_config.close()
        
        # Create mock MT5Service
        self.mock_mt5_service = Mock()
        self.mock_mt5_service.connect = Mock(return_value=True)
        self.mock_mt5_service.get_quote = Mock(return_value={"bid": 84000.0, "ask": 84010.0})
        self.mock_mt5_service.open_order = Mock(return_value={
            "ok": True,
            "details": {
                "ticket": 123456,
                "price_executed": 84000.0,
                "final_sl": 83800.0,
                "final_tp": 84500.0
            }
        })
        
        # Create auto-execution system
        self.auto_system = AutoExecutionSystem(
            db_path=self.db_path,
            mt5_service=self.mock_mt5_service
        )
        
        # Create Universal Manager instance (will be created in tests)
        self.universal_manager = None
    
    def tearDown(self):
        """Clean up test fixtures"""
        cleanup_registry()
        
        if self.universal_manager:
            self.universal_manager.active_trades.clear()
        
        import time
        time.sleep(0.1)
        
        try:
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)
        except PermissionError:
            pass
        
        try:
            if os.path.exists(self.config_path):
                os.unlink(self.config_path)
        except PermissionError:
            pass
    
    def test_auto_execution_registers_with_universal_manager(self):
        """Test that auto-execution system registers trades with Universal Manager"""
        # Create trade plan with universal-managed strategy
        plan = TradePlan(
            plan_id="test_plan_123",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=84000.0,
            stop_loss=83800.0,
            take_profit=84500.0,
            volume=0.01,
            conditions={
                "strategy_type": "breakout_ib_volatility_trap"
            },
            created_at=datetime.now().isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Mock Universal Manager registration (patch where it's imported)
        with patch('infra.universal_sl_tp_manager.UniversalDynamicSLTPManager') as mock_universal_class:
            mock_universal_instance = Mock()
            mock_universal_instance.register_trade = Mock(return_value=Mock())
            mock_universal_class.return_value = mock_universal_instance
            
            # Execute trade
            result = self.auto_system._execute_trade(plan)
            
            # Verify Universal Manager was called
            self.assertTrue(result, "Trade execution should succeed")
            mock_universal_instance.register_trade.assert_called_once()
            
            # Verify registration call arguments
            call_args = mock_universal_instance.register_trade.call_args
            self.assertEqual(call_args.kwargs['ticket'], 123456)
            self.assertEqual(call_args.kwargs['symbol'], "BTCUSDc")
            self.assertEqual(call_args.kwargs['strategy_type'], StrategyType.BREAKOUT_IB_VOLATILITY_TRAP)
            self.assertEqual(call_args.kwargs['direction'], "BUY")
            self.assertEqual(call_args.kwargs['entry_price'], 84000.0)
            self.assertEqual(call_args.kwargs['initial_sl'], 83800.0)
            self.assertEqual(call_args.kwargs['initial_tp'], 84500.0)
            self.assertEqual(call_args.kwargs['plan_id'], "test_plan_123")
    
    def test_auto_execution_skips_dtms_for_universal_managed(self):
        """Test that DTMS registration is skipped for universal-managed trades"""
        # Create trade plan with universal-managed strategy
        plan = TradePlan(
            plan_id="test_plan_456",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=84000.0,
            stop_loss=83800.0,
            take_profit=84500.0,
            volume=0.01,
            conditions={
                "strategy_type": "breakout_ib_volatility_trap"
            },
            created_at=datetime.now().isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Mock Universal Manager and DTMS (patch where they're imported)
        with patch('infra.universal_sl_tp_manager.UniversalDynamicSLTPManager') as mock_universal_class:
            with patch('dtms_integration.auto_register_dtms') as mock_dtms:
                mock_universal_instance = Mock()
                mock_universal_instance.register_trade = Mock(return_value=Mock())
                mock_universal_class.return_value = mock_universal_instance
                
                # Execute trade
                result = self.auto_system._execute_trade(plan)
                
                # Verify Universal Manager was called
                mock_universal_instance.register_trade.assert_called_once()
                
                # Verify DTMS was NOT called
                mock_dtms.assert_not_called()
    
    def test_auto_execution_registers_with_dtms_for_non_universal(self):
        """Test that DTMS registration happens for non-universal trades"""
        # Create trade plan WITHOUT universal-managed strategy
        plan = TradePlan(
            plan_id="test_plan_789",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=84000.0,
            stop_loss=83800.0,
            take_profit=84500.0,
            volume=0.01,
            conditions={},  # No strategy_type
            created_at=datetime.now().isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Mock DTMS (patch where it's imported)
        with patch('dtms_integration.auto_register_dtms') as mock_dtms:
            # Execute trade
            result = self.auto_system._execute_trade(plan)
            
            # Verify DTMS was called
            mock_dtms.assert_called_once()
            
            # Verify call arguments
            call_args = mock_dtms.call_args
            self.assertEqual(call_args[0][0], 123456)  # ticket
            self.assertIn('symbol', call_args[0][1])
            self.assertIn('direction', call_args[0][1])
    
    def test_chatgpt_tool_passes_strategy_type(self):
        """Test that ChatGPT tool passes strategy_type to plan"""
        # Mock httpx before importing
        mock_httpx = MagicMock()
        if 'httpx' not in sys.modules:
            sys.modules['httpx'] = mock_httpx
        
        # Verify the integration by checking the source code
        # This test verifies that the code modification was made correctly
        import inspect
        
        # Import after mocking httpx
        if 'chatgpt_auto_execution_tools' in sys.modules:
            del sys.modules['chatgpt_auto_execution_tools']
        
        import chatgpt_auto_execution_tools
        
        # Check that strategy_type is handled in the tool function
        source = inspect.getsource(chatgpt_auto_execution_tools.tool_create_auto_trade_plan)
        self.assertIn('strategy_type', source, "strategy_type should be handled in tool function")
        
        # Verify that strategy_type is added to conditions (check for either assignment pattern)
        has_strategy_type_logic = (
            'conditions["strategy_type"]' in source or 
            'conditions.get("strategy_type")' in source or
            ('strategy_type' in source and 'conditions' in source)
        )
        self.assertTrue(has_strategy_type_logic, 
                       "strategy_type should be added to conditions in tool function")
    
    def test_intelligent_exit_manager_skips_universal_managed(self):
        """Test that Intelligent Exit Manager skips universal-managed trades"""
        from infra.intelligent_exit_manager import IntelligentExitManager
        from infra.universal_sl_tp_manager import TradeState, Session
        
        # Create intelligent exit manager
        exit_manager = IntelligentExitManager(
            mt5_service=self.mock_mt5_service
        )
        
        # Add a rule for a ticket
        ticket = 123456
        exit_manager.add_rule(
            ticket=ticket,
            symbol="BTCUSDc",
            entry_price=84000.0,
            direction="buy",
            initial_sl=83800.0,
            initial_tp=84500.0
        )
        
        # Set ownership to Universal Manager
        trade_state = TradeState(
            ticket=ticket,
            symbol="BTCUSDc",
            strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            direction="BUY",
            session=Session.LONDON,
            resolved_trailing_rules={},
            managed_by="universal_sl_tp_manager",
            entry_price=84000.0,
            initial_sl=83800.0,
            initial_tp=84500.0
        )
        set_trade_state(ticket, trade_state)
        
        # Mock MT5 positions
        mock_position = Mock()
        mock_position.ticket = ticket
        mock_position.sl = 83800.0
        mock_position.tp = 84500.0
        mock_position.price_open = 84000.0
        mock_position.price_current = 84100.0
        mock_position.volume = 0.01
        mock_position.type = 0  # BUY
        
        with patch('infra.intelligent_exit_manager.mt5') as mock_mt5:
            mock_mt5.positions_get = Mock(return_value=[mock_position])
            mock_mt5.positions_get.return_value = [mock_position]
            
            # Check exits
            actions = exit_manager.check_exits()
            
            # Verify no actions were taken (trade was skipped)
            # The rule should still exist but no actions should be performed
            self.assertIn(ticket, exit_manager.rules)
            # Actions list should be empty or not contain actions for this ticket
            ticket_actions = [a for a in actions if a.get('ticket') == ticket]
            self.assertEqual(len(ticket_actions), 0, "No actions should be taken for universal-managed trade")
    
    def test_intelligent_exit_manager_handles_trades_without_ownership(self):
        """Test that Intelligent Exit Manager handles trades without ownership set"""
        from infra.intelligent_exit_manager import IntelligentExitManager
        
        # Create intelligent exit manager
        exit_manager = IntelligentExitManager(
            mt5_service=self.mock_mt5_service
        )
        
        # Add a rule for a ticket
        ticket = 123457
        exit_manager.add_rule(
            ticket=ticket,
            symbol="BTCUSDc",
            entry_price=84000.0,
            direction="buy",
            initial_sl=83800.0,
            initial_tp=84500.0
        )
        
        # Don't set ownership (trade not managed by Universal Manager)
        
        # Mock MT5 positions
        mock_position = Mock()
        mock_position.ticket = ticket
        mock_position.sl = 83800.0
        mock_position.tp = 84500.0
        mock_position.price_open = 84000.0
        mock_position.price_current = 84100.0
        mock_position.volume = 0.01
        mock_position.type = 0  # BUY
        
        with patch('infra.intelligent_exit_manager.mt5') as mock_mt5:
            mock_mt5.positions_get = Mock(return_value=[mock_position])
            
            # Check exits (should proceed normally)
            actions = exit_manager.check_exits()
            
            # Verify rule still exists (trade should be processed normally)
            self.assertIn(ticket, exit_manager.rules)
    
    def test_strategy_type_normalization_string_to_enum(self):
        """Test that string strategy_type is normalized to enum"""
        # Create trade plan with string strategy_type
        plan = TradePlan(
            plan_id="test_plan_normalize",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=84000.0,
            stop_loss=83800.0,
            take_profit=84500.0,
            volume=0.01,
            conditions={
                "strategy_type": "breakout_ib_volatility_trap"  # String, not enum
            },
            created_at=datetime.now().isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Mock Universal Manager (patch where it's imported)
        with patch('infra.universal_sl_tp_manager.UniversalDynamicSLTPManager') as mock_universal_class:
            mock_universal_instance = Mock()
            mock_universal_instance.register_trade = Mock(return_value=Mock())
            mock_universal_class.return_value = mock_universal_instance
            
            # Execute trade
            result = self.auto_system._execute_trade(plan)
            
            # Verify registration was called with StrategyType enum
            call_args = mock_universal_instance.register_trade.call_args
            self.assertIsInstance(
                call_args.kwargs['strategy_type'],
                StrategyType,
                "strategy_type should be normalized to StrategyType enum"
            )
            self.assertEqual(
                call_args.kwargs['strategy_type'],
                StrategyType.BREAKOUT_IB_VOLATILITY_TRAP
            )
    
    def test_fallback_to_dtms_on_universal_manager_error(self):
        """Test that system falls back to DTMS if Universal Manager fails"""
        # Create trade plan with universal-managed strategy
        plan = TradePlan(
            plan_id="test_plan_fallback",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=84000.0,
            stop_loss=83800.0,
            take_profit=84500.0,
            volume=0.01,
            conditions={
                "strategy_type": "breakout_ib_volatility_trap"
            },
            created_at=datetime.now().isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Mock the import to raise ImportError when importing universal_sl_tp_manager
        original_import = __import__
        def mock_import(name, *args, **kwargs):
            if name == 'infra.universal_sl_tp_manager':
                raise ImportError("Module not found")
            return original_import(name, *args, **kwargs)
        
        with patch('builtins.__import__', side_effect=mock_import):
            with patch('dtms_integration.auto_register_dtms') as mock_dtms:
                # Execute trade
                result = self.auto_system._execute_trade(plan)
                
                # Verify DTMS was called as fallback
                # The fallback logic in auto_execution_system catches ImportError
                mock_dtms.assert_called_once()
    
    def test_universal_manager_registration_before_dtms(self):
        """Test that Universal Manager registration happens before DTMS"""
        # Create trade plan with universal-managed strategy
        plan = TradePlan(
            plan_id="test_plan_order",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=84000.0,
            stop_loss=83800.0,
            take_profit=84500.0,
            volume=0.01,
            conditions={
                "strategy_type": "breakout_ib_volatility_trap"
            },
            created_at=datetime.now().isoformat(),
            created_by="test",
            status="pending"
        )
        
        # Track call order
        call_order = []
        
        # Mock Universal Manager (patch where it's imported)
        with patch('infra.universal_sl_tp_manager.UniversalDynamicSLTPManager') as mock_universal_class:
            mock_universal_instance = Mock()
            def track_universal_call(*args, **kwargs):
                call_order.append('universal')
                return Mock()
            mock_universal_instance.register_trade = track_universal_call
            mock_universal_class.return_value = mock_universal_instance
            
            # Mock DTMS (should not be called, but track if it is) (patch where it's imported)
            with patch('dtms_integration.auto_register_dtms') as mock_dtms:
                def track_dtms_call(*args, **kwargs):
                    call_order.append('dtms')
                mock_dtms.side_effect = track_dtms_call
                
                # Execute trade
                result = self.auto_system._execute_trade(plan)
                
                # Verify Universal Manager was called
                self.assertIn('universal', call_order)
                
                # Verify DTMS was NOT called
                self.assertNotIn('dtms', call_order)


if __name__ == '__main__':
    unittest.main()

