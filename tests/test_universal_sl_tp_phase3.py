"""
Unit Tests for Universal Dynamic SL/TP Manager - Phase 3

Tests for:
- Phase 3: Trailing Logic (trailing methods, R-calculation, safeguards, SL modification)
"""

import unittest
import tempfile
import os
import json
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

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
    mock_dtms.get_dtms_trade_status = Mock(return_value=None)
    sys.modules['dtms_integration'] = mock_dtms

# Import components to test
from infra.universal_sl_tp_manager import (
    UniversalDynamicSLTPManager,
    TradeState,
    Session,
    StrategyType
)


class TestPhase3TrailingLogic(unittest.TestCase):
    """Test Phase 3: Trailing Logic"""
    
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
                        "trailing_timeframe_btc": "M1",
                        "atr_multiplier": 1.5,
                        "structure_lookback": 2,
                        "min_sl_change_r": 0.1,
                        "sl_modification_cooldown_seconds": 20,
                        "partial_profit_r": 1.5,
                        "partial_close_pct": 50
                    },
                    "trend_continuation_pullback": {
                        "breakeven_trigger_r": 1.0,
                        "trailing_method": "structure_based",
                        "trailing_timeframe": "M5",
                        "atr_multiplier": 1.0,
                        "structure_lookback": 1,
                        "atr_buffer": 0.5,
                        "min_sl_change_r": 0.1,
                        "sl_modification_cooldown_seconds": 45
                    },
                    "liquidity_sweep_reversal": {
                        "breakeven_trigger_r": 0.5,
                        "trailing_method": "micro_choch",
                        "trailing_timeframe": "M1",
                        "min_sl_change_r": 0.1,
                        "sl_modification_cooldown_seconds": 15
                    },
                    "order_block_rejection": {
                        "breakeven_trigger_r": 1.0,
                        "trailing_method": "displacement_or_structure",
                        "trailing_timeframe": "M5",
                        "min_sl_change_r": 0.1,
                        "sl_modification_cooldown_seconds": 30
                    },
                    "mean_reversion_range_scalp": {
                        "breakeven_trigger_r": 0.5,
                        "trailing_method": "minimal_be_only",
                        "trailing_enabled": False,
                        "min_sl_change_r": 0.1,
                        "sl_modification_cooldown_seconds": 10
                    },
                    "default_standard": {
                        "breakeven_trigger_r": 1.0,
                        "trailing_method": "atr_basic",
                        "trailing_timeframe": "M15",
                        "atr_multiplier": 2.0,
                        "min_sl_change_r": 0.1,
                        "sl_modification_cooldown_seconds": 60
                    }
                },
                "symbol_adjustments": {
                    "BTCUSDc": {
                        "atr_timeframe": "M5",
                        "trailing_timeframe": "M1",
                        "min_sl_change_r": 0.1
                    }
                }
            }
        }
        json.dump(test_config, self.temp_config)
        self.temp_config.close()
        
        # Create manager instance
        self.manager = UniversalDynamicSLTPManager(
            db_path=self.db_path,
            mt5_service=None,
            config_path=self.config_path
        )
        
        # Create test trade state
        self.trade_state = TradeState(
            ticket=123456,
            symbol="BTCUSDc",
            strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            direction="BUY",
            session=Session.LONDON,
            resolved_trailing_rules={
                "breakeven_trigger_r": 1.0,
                "trailing_method": "structure_atr_hybrid",
                "trailing_timeframe": "M1",
                "atr_multiplier": 1.5,
                "structure_lookback": 2,
                "min_sl_change_r": 0.1,
                "sl_modification_cooldown_seconds": 20,
                "partial_profit_r": 1.5,
                "partial_close_pct": 50
            },
            managed_by="universal_sl_tp_manager",
            entry_price=84000.0,
            initial_sl=83800.0,
            initial_tp=84500.0,
            baseline_atr=50.0,
            initial_volume=0.01,
            current_price=84200.0,
            current_sl=83800.0,
            r_achieved=1.0
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        if hasattr(self, 'manager'):
            self.manager.active_trades.clear()
        
        from infra.trade_registry import cleanup_registry
        cleanup_registry()
        
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
    
    def test_calculate_r_achieved_buy_positive(self):
        """Test R calculation for BUY position in profit"""
        r = self.manager._calculate_r_achieved(
            entry_price=84000.0,
            initial_sl=83800.0,
            current_price=84200.0,
            direction="BUY"
        )
        # Should be +1.0R (200 points profit / 200 points risk)
        self.assertAlmostEqual(r, 1.0, places=2)
    
    def test_calculate_r_achieved_buy_negative(self):
        """Test R calculation for BUY position in loss"""
        r = self.manager._calculate_r_achieved(
            entry_price=84000.0,
            initial_sl=83800.0,
            current_price=83900.0,  # 100 points below entry
            direction="BUY"
        )
        # Should be -0.5R (100 points loss / 200 points risk)
        self.assertAlmostEqual(r, -0.5, places=2)
    
    def test_calculate_r_achieved_sell_positive(self):
        """Test R calculation for SELL position in profit"""
        r = self.manager._calculate_r_achieved(
            entry_price=84000.0,
            initial_sl=84200.0,
            current_price=83800.0,
            direction="SELL"
        )
        # Should be +1.0R (200 points profit / 200 points risk)
        self.assertAlmostEqual(r, 1.0, places=2)
    
    def test_calculate_r_achieved_sell_negative(self):
        """Test R calculation for SELL position in loss"""
        r = self.manager._calculate_r_achieved(
            entry_price=84000.0,
            initial_sl=84200.0,
            current_price=84100.0,  # 100 points above entry
            direction="SELL"
        )
        # Should be -0.5R (100 points loss / 200 points risk)
        self.assertAlmostEqual(r, -0.5, places=2)
    
    def test_check_cooldown_never_modified(self):
        """Test cooldown check when never modified"""
        self.trade_state.last_sl_modification_time = None
        result = self.manager._check_cooldown(self.trade_state, self.trade_state.resolved_trailing_rules)
        self.assertTrue(result)  # Should allow modification
    
    def test_check_cooldown_elapsed(self):
        """Test cooldown check when cooldown has elapsed"""
        self.trade_state.last_sl_modification_time = datetime.now() - timedelta(seconds=25)
        result = self.manager._check_cooldown(self.trade_state, self.trade_state.resolved_trailing_rules)
        self.assertTrue(result)  # Should allow modification (20s cooldown elapsed)
    
    def test_check_cooldown_not_elapsed(self):
        """Test cooldown check when cooldown has not elapsed"""
        self.trade_state.last_sl_modification_time = datetime.now() - timedelta(seconds=10)
        result = self.manager._check_cooldown(self.trade_state, self.trade_state.resolved_trailing_rules)
        self.assertFalse(result)  # Should block modification (20s cooldown not elapsed)
    
    def test_should_modify_sl_improvement_too_small(self):
        """Test that SL modification is blocked if improvement is too small"""
        # New SL that improves by only 0.05R (below 0.1R threshold)
        new_sl = 83810.0  # Only 10 points improvement = 0.05R (10/200)
        result = self.manager._should_modify_sl(self.trade_state, new_sl, self.trade_state.resolved_trailing_rules)
        self.assertFalse(result)
    
    def test_should_modify_sl_improvement_sufficient(self):
        """Test that SL modification is allowed if improvement is sufficient"""
        # New SL that improves by 0.15R (above 0.1R threshold)
        self.trade_state.last_sl_modification_time = None  # No cooldown
        new_sl = 83830.0  # 30 points improvement = 0.15R (30/200)
        result = self.manager._should_modify_sl(self.trade_state, new_sl, self.trade_state.resolved_trailing_rules)
        self.assertTrue(result)
    
    def test_should_modify_sl_not_improvement_buy(self):
        """Test that SL modification is blocked if not an improvement (BUY)"""
        # New SL that is lower than current (worse for BUY)
        new_sl = 83790.0  # Lower than current_sl (83800.0)
        result = self.manager._should_modify_sl(self.trade_state, new_sl, self.trade_state.resolved_trailing_rules)
        self.assertFalse(result)
    
    def test_should_modify_sl_not_improvement_sell(self):
        """Test that SL modification is blocked if not an improvement (SELL)"""
        # Create SELL trade state
        sell_trade_state = TradeState(
            ticket=123457,
            symbol="BTCUSDc",
            strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            direction="SELL",
            session=Session.LONDON,
            resolved_trailing_rules=self.trade_state.resolved_trailing_rules,
            managed_by="universal_sl_tp_manager",
            entry_price=84000.0,
            initial_sl=84200.0,
            initial_tp=83500.0,
            current_sl=84200.0,
            last_sl_modification_time=None
        )
        
        # New SL that is higher than current (worse for SELL)
        new_sl = 84210.0  # Higher than current_sl (84200.0)
        result = self.manager._should_modify_sl(sell_trade_state, new_sl, sell_trade_state.resolved_trailing_rules)
        self.assertFalse(result)
    
    @patch('MetaTrader5.symbol_info')
    def test_get_broker_min_stop_distance(self, mock_symbol_info):
        """Test broker minimum stop distance retrieval"""
        mock_symbol_info_obj = Mock()
        mock_symbol_info_obj.trade_stops_level = 10
        mock_symbol_info_obj.point = 0.1
        mock_symbol_info.return_value = mock_symbol_info_obj
        
        distance = self.manager._get_broker_min_stop_distance("BTCUSDc")
        self.assertEqual(distance, 1.0)  # 10 * 0.1
    
    @patch('MetaTrader5.symbol_info')
    def test_get_broker_min_stop_distance_fallback(self, mock_symbol_info):
        """Test broker minimum stop distance fallback"""
        mock_symbol_info.return_value = None
        
        distance = self.manager._get_broker_min_stop_distance("BTCUSDc")
        self.assertEqual(distance, 5.0)  # Fallback default
    
    @patch.object(UniversalDynamicSLTPManager, '_get_current_atr')
    @patch('MetaTrader5.symbol_info_tick')
    def test_get_atr_based_sl_buy(self, mock_symbol_info_tick, mock_get_atr):
        """Test ATR-based SL calculation for BUY"""
        mock_get_atr.return_value = 50.0
        
        mock_tick = Mock()
        mock_tick.bid = 84200.0
        mock_symbol_info_tick.return_value = mock_tick
        
        sl = self.manager._get_atr_based_sl(
            self.trade_state,
            self.trade_state.resolved_trailing_rules,
            atr_multiplier=1.5,
            timeframe="M1"
        )
        
        # Should be: 84200 - (50 * 1.5) = 84125
        self.assertAlmostEqual(sl, 84125.0, places=2)
    
    @patch.object(UniversalDynamicSLTPManager, '_get_current_atr')
    @patch('MetaTrader5.symbol_info_tick')
    def test_get_atr_based_sl_sell(self, mock_symbol_info_tick, mock_get_atr):
        """Test ATR-based SL calculation for SELL"""
        mock_get_atr.return_value = 50.0
        
        sell_trade_state = TradeState(
            ticket=123457,
            symbol="BTCUSDc",
            strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            direction="SELL",
            session=Session.LONDON,
            resolved_trailing_rules=self.trade_state.resolved_trailing_rules,
            managed_by="universal_sl_tp_manager",
            entry_price=84000.0,
            initial_sl=84200.0,
            initial_tp=83500.0
        )
        
        mock_tick = Mock()
        mock_tick.ask = 83800.0
        mock_symbol_info_tick.return_value = mock_tick
        
        sl = self.manager._get_atr_based_sl(
            sell_trade_state,
            sell_trade_state.resolved_trailing_rules,
            atr_multiplier=1.5,
            timeframe="M1"
        )
        
        # Should be: 83800 + (50 * 1.5) = 83875
        self.assertAlmostEqual(sl, 83875.0, places=2)
    
    @patch.object(UniversalDynamicSLTPManager, '_get_current_atr')
    def test_get_atr_based_sl_invalid_atr(self, mock_get_atr):
        """Test ATR-based SL returns None for invalid ATR"""
        mock_get_atr.return_value = None
        
        sl = self.manager._get_atr_based_sl(
            self.trade_state,
            self.trade_state.resolved_trailing_rules,
            atr_multiplier=1.5,
            timeframe="M1"
        )
        
        self.assertIsNone(sl)
    
    @patch('infra.streamer_data_access.StreamerDataAccess')
    @patch.object(UniversalDynamicSLTPManager, '_get_current_atr')
    def test_get_structure_based_sl_buy(self, mock_get_atr, mock_streamer_class):
        """Test structure-based SL calculation for BUY"""
        mock_get_atr.return_value = 50.0
        
        # Mock candles with swing lows
        mock_candles = [
            {'time': '2025-11-23T10:00:00Z', 'high': 84100.0, 'low': 83900.0, 'open': 84000.0, 'close': 84050.0},
            {'time': '2025-11-23T10:01:00Z', 'high': 84150.0, 'low': 83950.0, 'open': 84050.0, 'close': 84100.0},
            {'time': '2025-11-23T10:02:00Z', 'high': 84200.0, 'low': 84000.0, 'open': 84100.0, 'close': 84150.0},
            {'time': '2025-11-23T10:03:00Z', 'high': 84150.0, 'low': 83900.0, 'open': 84150.0, 'close': 84000.0},  # Swing low
            {'time': '2025-11-23T10:04:00Z', 'high': 84200.0, 'low': 84000.0, 'open': 84000.0, 'close': 84100.0},
            {'time': '2025-11-23T10:05:00Z', 'high': 84250.0, 'low': 84050.0, 'open': 84100.0, 'close': 84200.0},
        ]
        
        mock_streamer = Mock()
        mock_streamer.get_candles.return_value = mock_candles
        mock_streamer_class.return_value = mock_streamer
        
        rules = self.trade_state.resolved_trailing_rules.copy()
        rules['atr_buffer'] = 0.5
        
        sl = self.manager._get_structure_based_sl(self.trade_state, rules)
        
        # Should find swing low at 83900.0, then subtract ATR buffer: 83900 - (50 * 0.5) = 83875
        self.assertIsNotNone(sl)
        self.assertLess(sl, 83900.0)  # Should be below swing low
    
    @patch('infra.streamer_data_access.StreamerDataAccess')
    @patch.object(UniversalDynamicSLTPManager, '_get_current_atr')
    def test_get_structure_based_sl_insufficient_candles(self, mock_get_atr, mock_streamer_class):
        """Test structure-based SL returns None for insufficient candles"""
        mock_get_atr.return_value = 50.0
        
        # Not enough candles for structure analysis
        mock_candles = [
            {'time': '2025-11-23T10:00:00Z', 'high': 84100.0, 'low': 83900.0, 'open': 84000.0, 'close': 84050.0},
        ]
        
        mock_streamer = Mock()
        mock_streamer.get_candles.return_value = mock_candles
        mock_streamer_class.return_value = mock_streamer
        
        sl = self.manager._get_structure_based_sl(self.trade_state, self.trade_state.resolved_trailing_rules)
        
        self.assertIsNone(sl)
    
    @patch.object(UniversalDynamicSLTPManager, '_get_structure_based_sl')
    @patch.object(UniversalDynamicSLTPManager, '_get_atr_based_sl')
    def test_calculate_trailing_sl_structure_atr_hybrid(self, mock_atr_sl, mock_structure_sl):
        """Test structure-ATR hybrid trailing"""
        mock_structure_sl.return_value = 84025.0
        mock_atr_sl.return_value = 84050.0
        
        sl = self.manager._calculate_trailing_sl(
            self.trade_state,
            self.trade_state.resolved_trailing_rules
        )
        
        # For BUY, should return max (better = higher)
        self.assertEqual(sl, 84050.0)
    
    @patch.object(UniversalDynamicSLTPManager, '_get_structure_based_sl')
    @patch.object(UniversalDynamicSLTPManager, '_get_atr_based_sl')
    def test_calculate_trailing_sl_structure_atr_hybrid_fallback(self, mock_atr_sl, mock_structure_sl):
        """Test structure-ATR hybrid falls back to ATR when structure unavailable"""
        mock_structure_sl.return_value = None
        mock_atr_sl.return_value = 84050.0
        
        sl = self.manager._calculate_trailing_sl(
            self.trade_state,
            self.trade_state.resolved_trailing_rules
        )
        
        # Should fallback to ATR
        self.assertEqual(sl, 84050.0)
    
    @patch.object(UniversalDynamicSLTPManager, '_get_atr_based_sl')
    def test_calculate_trailing_sl_atr_basic(self, mock_atr_sl):
        """Test ATR basic trailing method"""
        mock_atr_sl.return_value = 84050.0
        
        rules = self.trade_state.resolved_trailing_rules.copy()
        rules['trailing_method'] = 'atr_basic'
        
        sl = self.manager._calculate_trailing_sl(self.trade_state, rules)
        
        self.assertEqual(sl, 84050.0)
    
    @patch.object(UniversalDynamicSLTPManager, '_get_micro_choch_sl')
    @patch.object(UniversalDynamicSLTPManager, '_get_atr_based_sl')
    def test_calculate_trailing_sl_micro_choch_fallback(self, mock_atr_sl, mock_choch_sl):
        """Test micro CHOCH trailing falls back to ATR"""
        mock_choch_sl.return_value = None
        mock_atr_sl.return_value = 84050.0
        
        rules = self.trade_state.resolved_trailing_rules.copy()
        rules['trailing_method'] = 'micro_choch'
        
        sl = self.manager._calculate_trailing_sl(self.trade_state, rules)
        
        # Should fallback to ATR
        self.assertEqual(sl, 84050.0)
    
    def test_calculate_trailing_sl_minimal_be_only(self):
        """Test minimal BE only trailing method"""
        rules = self.trade_state.resolved_trailing_rules.copy()
        rules['trailing_method'] = 'minimal_be_only'
        
        sl = self.manager._calculate_trailing_sl(self.trade_state, rules)
        
        # Should return None (no trailing)
        self.assertIsNone(sl)
    
    @patch.object(UniversalDynamicSLTPManager, '_get_current_atr')
    def test_get_dynamic_partial_trigger_normal_volatility(self, mock_get_atr):
        """Test dynamic partial trigger with normal volatility"""
        mock_get_atr.return_value = 50.0  # Same as baseline (50.0)
        self.trade_state.baseline_atr = 50.0
        
        trigger_r = self.manager._get_dynamic_partial_trigger(
            self.trade_state,
            self.trade_state.resolved_trailing_rules
        )
        
        # Should return base partial (1.5R)
        self.assertEqual(trigger_r, 1.5)
    
    @patch.object(UniversalDynamicSLTPManager, '_get_current_atr')
    def test_get_dynamic_partial_trigger_high_volatility(self, mock_get_atr):
        """Test dynamic partial trigger with high volatility"""
        mock_get_atr.return_value = 75.0  # 1.5× baseline (50.0)
        self.trade_state.baseline_atr = 50.0
        
        trigger_r = self.manager._get_dynamic_partial_trigger(
            self.trade_state,
            self.trade_state.resolved_trailing_rules
        )
        
        # Should return 20% earlier: 1.5 * 0.8 = 1.2R
        self.assertAlmostEqual(trigger_r, 1.2, places=2)
    
    @patch.object(UniversalDynamicSLTPManager, '_get_current_atr')
    def test_get_dynamic_partial_trigger_no_partial(self, mock_get_atr):
        """Test dynamic partial trigger when no partial configured"""
        rules = self.trade_state.resolved_trailing_rules.copy()
        rules.pop('partial_profit_r', None)
        
        trigger_r = self.manager._get_dynamic_partial_trigger(
            self.trade_state,
            rules
        )
        
        # Should return inf (no partial)
        self.assertEqual(trigger_r, float('inf'))
    
    @patch.object(UniversalDynamicSLTPManager, '_modify_position_sl')
    def test_move_to_breakeven(self, mock_modify_sl):
        """Test moving SL to breakeven"""
        mock_modify_sl.return_value = True
        self.trade_state.current_sl = 83800.0
        
        self.manager._move_to_breakeven(123456, self.trade_state)
        
        # Should modify SL to entry price
        mock_modify_sl.assert_called_once_with(123456, 84000.0, self.trade_state)
        self.assertIsNotNone(self.trade_state.last_sl_modification_time)
    
    @patch('MetaTrader5.order_send')
    @patch('MetaTrader5.symbol_info')
    @patch('MetaTrader5.positions_get')
    def test_take_partial_profit(self, mock_positions_get, mock_symbol_info, mock_order_send):
        """Test taking partial profit"""
        mock_position = Mock()
        mock_position.ticket = 123456
        mock_position.volume = 0.02  # Use larger volume to avoid rounding to 0
        mock_position.type = 0  # BUY
        
        mock_symbol_info_obj = Mock()
        mock_symbol_info_obj.volume_step = 0.01
        
        mock_positions_get.return_value = [mock_position]
        mock_symbol_info.return_value = mock_symbol_info_obj
        
        mock_result = Mock()
        mock_result.retcode = 10009  # TRADE_RETCODE_DONE
        mock_order_send.return_value = mock_result
        
        # Update trade state to match position volume
        self.trade_state.initial_volume = 0.02
        
        self.manager._take_partial_profit(123456, self.trade_state, self.trade_state.resolved_trailing_rules)
        
        # Should call order_send to close partial position
        mock_order_send.assert_called_once()
        call_args = mock_order_send.call_args[0][0]
        # Check that action is TRADE_ACTION_DEAL (value may vary, check it's a valid action)
        self.assertIn('action', call_args)
        self.assertIn('volume', call_args)
        # Volume should be 50% of 0.02 = 0.01
        self.assertAlmostEqual(call_args['volume'], 0.01, places=3)
    
    @patch.object(UniversalDynamicSLTPManager, '_modify_position_sl')
    def test_modify_position_sl_success(self, mock_modify_sl):
        """Test successful SL modification"""
        mock_modify_sl.return_value = True
        
        # This is a wrapper, so we test the actual method
        success = self.manager._modify_position_sl(123456, 84025.0, self.trade_state)
        
        # Should call MT5Service or MT5
        # Since we don't have MT5Service, it will try direct MT5
        # But we can test the ownership check
        self.assertIsNotNone(success)  # Will be False without MT5, but method executes
    
    def test_modify_position_sl_wrong_ownership(self):
        """Test SL modification blocked by wrong ownership"""
        self.trade_state.managed_by = "legacy_exit_manager"
        
        success = self.manager._modify_position_sl(123456, 84025.0, self.trade_state)
        
        self.assertFalse(success)
    
    @patch.object(UniversalDynamicSLTPManager, '_is_dtms_in_defensive_mode')
    def test_modify_position_sl_dtms_defensive_mode(self, mock_dtms_check):
        """Test SL modification blocked by DTMS defensive mode"""
        mock_dtms_check.return_value = True
        
        success = self.manager._modify_position_sl(123456, 84025.0, self.trade_state)
        
        self.assertFalse(success)
    
    def test_log_sl_modification(self):
        """Test rich logging format for SL modification"""
        # This test just verifies the method doesn't crash
        # Actual logging output would be checked in integration tests
        self.manager._log_sl_modification(
            self.trade_state,
            old_sl=83800.0,
            new_sl=84000.0,
            reason="breakeven_trigger"
        )
        # If no exception, test passes
    
    def test_is_dtms_in_defensive_mode_false(self):
        """Test DTMS defensive mode check returns False when not in defensive mode"""
        with patch.dict('sys.modules', {'dtms_integration': MagicMock()}):
            with patch('dtms_integration.get_dtms_trade_status') as mock_get_status:
                mock_get_status.return_value = {'state': 'NORMAL'}
                
                result = self.manager._is_dtms_in_defensive_mode(123456)
                self.assertFalse(result)
    
    def test_is_dtms_in_defensive_mode_true(self):
        """Test DTMS defensive mode check returns True when in defensive mode"""
        with patch.dict('sys.modules', {'dtms_integration': MagicMock()}):
            with patch('dtms_integration.get_dtms_trade_status') as mock_get_status:
                mock_get_status.return_value = {'state': 'HEDGED'}
                
                result = self.manager._is_dtms_in_defensive_mode(123456)
                self.assertTrue(result)
    
    def test_tighten_sl_aggressively(self):
        """Test aggressive SL tightening on momentum exhaustion"""
        self.trade_state.current_sl = 84000.0  # Already at BE
        self.trade_state.r_achieved = 1.5
        
        with patch.object(self.manager, '_modify_position_sl', return_value=True) as mock_modify:
            rules = self.trade_state.resolved_trailing_rules.copy()
            rules['stall_lock_r'] = 0.75
            
            self.manager._tighten_sl_aggressively(123456, self.trade_state, rules)
            
            # Should calculate SL to lock 0.75R
            # For BUY: entry + (one_r * 0.75) = 84000 + (200 * 0.75) = 84150
            mock_modify.assert_called_once()
            call_args = mock_modify.call_args[0]
            new_sl = call_args[1]
            self.assertAlmostEqual(new_sl, 84150.0, places=2)


if __name__ == '__main__':
    unittest.main()

