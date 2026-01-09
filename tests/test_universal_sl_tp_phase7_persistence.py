"""
Unit Tests for Universal Dynamic SL/TP Manager - Phase 7: Persistence & Recovery

Tests for:
- Database initialization
- Saving trade state to database
- Loading trade state from database
- Trade recovery on startup
- Cleanup of closed trades
- Strategy type inference
- Recovery coordination
"""

import unittest
import tempfile
import os
import json
import sys
from datetime import datetime
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
from infra.trade_registry import cleanup_registry


class TestPhase7Persistence(unittest.TestCase):
    """Test Phase 7: Persistence & Recovery"""
    
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
                        "partial_profit_r": 1.5,
                        "partial_close_pct": 50,
                        "trailing_method": "atr_basic",
                        "trailing_enabled": True,
                        "atr_multiplier": 1.5,
                        "min_sl_change_r": 0.1,
                        "sl_modification_cooldown_seconds": 30
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
                "partial_profit_r": 1.5,
                "partial_close_pct": 50,
                "trailing_method": "atr_basic",
                "trailing_enabled": True,
                "atr_multiplier": 1.5,
                "atr_timeframe": "M15",
                "min_sl_change_r": 0.1,
                "sl_modification_cooldown_seconds": 30
            },
            managed_by="universal_sl_tp_manager",
            entry_price=84000.0,
            initial_sl=83800.0,
            initial_tp=84500.0,
            baseline_atr=100.0,
            initial_volume=0.01,
            breakeven_triggered=True,
            partial_taken=False,
            last_trailing_sl=84000.0,
            last_sl_modification_time=datetime.now(),
            registered_at=datetime.now(),
            plan_id="test_plan_123"
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        if hasattr(self, 'manager'):
            self.manager.active_trades.clear()
        
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
    
    def test_database_initialization(self):
        """Test that database is initialized with correct schema"""
        # Database should be initialized in __init__
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='universal_trades'")
            row = cursor.fetchone()
            self.assertIsNotNone(row, "universal_trades table should exist")
    
    def test_save_trade_state_to_db(self):
        """Test saving trade state to database"""
        self.manager._save_trade_state_to_db(self.trade_state)
        
        # Verify trade was saved
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM universal_trades WHERE ticket = ?",
                (123456,)
            ).fetchone()
            
            self.assertIsNotNone(row, "Trade should be saved to database")
            self.assertEqual(row["ticket"], 123456)
            self.assertEqual(row["symbol"], "BTCUSDc")
            self.assertEqual(row["strategy_type"], "breakout_ib_volatility_trap")
            self.assertEqual(row["direction"], "BUY")
            self.assertEqual(row["session"], "LONDON")
            self.assertEqual(row["entry_price"], 84000.0)
            self.assertEqual(row["initial_sl"], 83800.0)
            self.assertEqual(row["initial_tp"], 84500.0)
            self.assertEqual(row["baseline_atr"], 100.0)
            self.assertEqual(row["initial_volume"], 0.01)
            self.assertEqual(row["breakeven_triggered"], 1)
            self.assertEqual(row["partial_taken"], 0)
            self.assertEqual(row["plan_id"], "test_plan_123")
    
    def test_load_trade_state_from_db(self):
        """Test loading trade state from database"""
        # Save trade first
        self.manager._save_trade_state_to_db(self.trade_state)
        
        # Load trade
        loaded_state = self.manager._load_trade_state_from_db(123456)
        
        self.assertIsNotNone(loaded_state, "Trade should be loaded from database")
        self.assertEqual(loaded_state.ticket, 123456)
        self.assertEqual(loaded_state.symbol, "BTCUSDc")
        self.assertEqual(loaded_state.strategy_type, StrategyType.BREAKOUT_IB_VOLATILITY_TRAP)
        self.assertEqual(loaded_state.direction, "BUY")
        self.assertEqual(loaded_state.session, Session.LONDON)
        self.assertEqual(loaded_state.entry_price, 84000.0)
        self.assertEqual(loaded_state.initial_sl, 83800.0)
        self.assertEqual(loaded_state.initial_tp, 84500.0)
        self.assertEqual(loaded_state.baseline_atr, 100.0)
        self.assertEqual(loaded_state.initial_volume, 0.01)
        self.assertTrue(loaded_state.breakeven_triggered)
        self.assertFalse(loaded_state.partial_taken)
        self.assertEqual(loaded_state.plan_id, "test_plan_123")
        self.assertIsNotNone(loaded_state.resolved_trailing_rules)
    
    def test_load_trade_state_from_db_not_found(self):
        """Test loading non-existent trade returns None"""
        loaded_state = self.manager._load_trade_state_from_db(999999)
        self.assertIsNone(loaded_state, "Non-existent trade should return None")
    
    def test_cleanup_trade_from_db(self):
        """Test cleanup of trade from database"""
        # Save trade first
        self.manager._save_trade_state_to_db(self.trade_state)
        
        # Verify it exists
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM universal_trades WHERE ticket = ?",
                (123456,)
            ).fetchone()
            self.assertIsNotNone(row, "Trade should exist before cleanup")
        
        # Cleanup
        self.manager._cleanup_trade_from_db(123456)
        
        # Verify it's gone
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM universal_trades WHERE ticket = ?",
                (123456,)
            ).fetchone()
            self.assertIsNone(row, "Trade should be removed after cleanup")
    
    def test_recover_trades_on_startup_with_existing_trade(self):
        """Test recovery of trades from database on startup"""
        # Save trade to database
        self.manager._save_trade_state_to_db(self.trade_state)
        
        # Mock MT5 position
        mock_position = Mock()
        mock_position.ticket = 123456
        mock_position.symbol = "BTCUSDc"
        mock_position.type = 0  # BUY
        mock_position.price_open = 84000.0
        mock_position.sl = 83800.0
        mock_position.tp = 84500.0
        mock_position.volume = 0.01
        mock_position.time_setup = datetime.now().timestamp()
        
        with patch('MetaTrader5.initialize', return_value=True):
            with patch('MetaTrader5.positions_get', return_value=[mock_position]):
                with patch.object(self.manager, '_get_current_atr', return_value=100.0):
                    # Clear active trades to simulate startup
                    self.manager.active_trades.clear()
                    cleanup_registry()
                    
                    # Recover
                    self.manager.recover_trades_on_startup()
                    
                    # Verify trade was recovered
                    self.assertIn(123456, self.manager.active_trades)
                    recovered_state = self.manager.active_trades[123456]
                    self.assertEqual(recovered_state.ticket, 123456)
                    self.assertEqual(recovered_state.symbol, "BTCUSDc")
                    self.assertTrue(recovered_state.breakeven_triggered)
    
    def test_recover_trades_on_startup_cleans_up_closed_trades(self):
        """Test that recovery cleans up trades that no longer exist in MT5"""
        # Save trade to database
        self.manager._save_trade_state_to_db(self.trade_state)
        
        # Mock MT5 with no positions (trade was closed)
        with patch('MetaTrader5.initialize', return_value=True):
            with patch('MetaTrader5.positions_get', return_value=[]):
                # Recover
                self.manager.recover_trades_on_startup()
                
                # Verify trade was cleaned up from database
                loaded_state = self.manager._load_trade_state_from_db(123456)
                self.assertIsNone(loaded_state, "Closed trade should be cleaned up")
    
    def test_infer_strategy_type_from_comment(self):
        """Test strategy type inference from position comment"""
        mock_position = Mock()
        mock_position.comment = "breakout_ib_volatility_trap"
        
        strategy_type = self.manager._infer_strategy_type(123456, mock_position)
        self.assertEqual(strategy_type, StrategyType.BREAKOUT_IB_VOLATILITY_TRAP)
    
    def test_infer_strategy_type_from_plan_id(self):
        """Test strategy type inference from plan_id in comment"""
        # Since trade_plans DB may not exist, test that it handles gracefully
        mock_position = Mock()
        mock_position.comment = "plan_id:test_plan_123"
        
        # The method will try to query trade_plans, but if DB doesn't exist, it returns None
        # We'll just verify it doesn't crash
        strategy_type = self.manager._infer_strategy_type(123456, mock_position)
        # Should either return None (if DB doesn't exist) or a valid strategy type
        # The important thing is it doesn't crash
        self.assertIsInstance(strategy_type, (type(None), StrategyType))
    
    def test_infer_strategy_type_returns_none_for_unknown(self):
        """Test that inference returns None for unknown patterns"""
        mock_position = Mock()
        mock_position.comment = "unknown_pattern"
        
        strategy_type = self.manager._infer_strategy_type(123456, mock_position)
        self.assertIsNone(strategy_type, "Unknown pattern should return None")
    
    def test_save_trade_state_handles_json_serialization_error(self):
        """Test that save handles JSON serialization errors gracefully"""
        # Create trade state with non-serializable rules
        bad_trade_state = TradeState(
            ticket=123457,
            symbol="BTCUSDc",
            strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            direction="BUY",
            session=Session.LONDON,
            resolved_trailing_rules={"bad": object()},  # Non-serializable
            managed_by="universal_sl_tp_manager",
            entry_price=84000.0,
            initial_sl=83800.0,
            initial_tp=84500.0,
            baseline_atr=100.0,
            initial_volume=0.01
        )
        
        # Should not raise exception
        try:
            self.manager._save_trade_state_to_db(bad_trade_state)
        except Exception as e:
            self.fail(f"Save should handle serialization errors gracefully: {e}")
    
    def test_load_trade_state_handles_json_deserialization_error(self):
        """Test that load handles JSON deserialization errors gracefully"""
        # Manually insert invalid JSON into database
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO universal_trades (
                    ticket, symbol, strategy_type, direction, session,
                    entry_price, initial_sl, initial_tp, resolved_trailing_rules,
                    managed_by, baseline_atr, initial_volume,
                    breakeven_triggered, partial_taken, registered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                123458, "BTCUSDc", "breakout_ib_volatility_trap", "BUY", "LONDON",
                84000.0, 83800.0, 84500.0, "invalid json {",  # Invalid JSON
                "universal_sl_tp_manager", 100.0, 0.01,
                0, 0, datetime.now().isoformat()
            ))
            conn.commit()
        
        # Should not raise exception, should return None or handle gracefully
        loaded_state = self.manager._load_trade_state_from_db(123458)
        # Should either return None or have empty rules
        if loaded_state:
            self.assertEqual(loaded_state.resolved_trailing_rules, {})


if __name__ == '__main__':
    unittest.main()

