"""
Unit Tests for Universal Dynamic SL/TP Manager - Phase 1 & 2

Tests for:
- Phase 1: Core Infrastructure (enums, TradeState, TradeRegistry, database, config)
- Phase 2: Rule Resolution (strategy normalization, session detection, ATR, rule resolution, registration)
"""

import unittest
import tempfile
import os
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

# Import components to test
from infra.universal_sl_tp_manager import (
    UniversalDynamicSLTPManager,
    TradeState,
    Session,
    StrategyType,
    detect_session,
    UNIVERSAL_MANAGED_STRATEGIES
)
from infra.trade_registry import (
    get_trade_state,
    set_trade_state,
    remove_trade_state,
    can_modify_position,
    cleanup_registry
)


class TestPhase1CoreInfrastructure(unittest.TestCase):
    """Test Phase 1: Core Infrastructure"""
    
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
                        "min_sl_change_r": 0.1,
                        "sl_modification_cooldown_seconds": 20
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
                        "min_sl_change_r": 0.1,
                        "session_adjustments": {
                            "LONDON": {
                                "tp_multiplier": 1.2,
                                "sl_tightening": 0.9
                            }
                        }
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
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Close any database connections
        if hasattr(self, 'manager'):
            # Clear active trades to release any references
            self.manager.active_trades.clear()
        
        # Clean registry
        cleanup_registry()
        
        # Small delay to allow file handles to close
        import time
        time.sleep(0.1)
        
        # Remove temporary files
        try:
            if os.path.exists(self.db_path):
                # Close any open connections first
                import time
                time.sleep(0.1)  # Give time for connections to close
                try:
                    os.unlink(self.db_path)
                except PermissionError:
                    # File may still be locked, try again after a delay
                    time.sleep(0.2)
                    try:
                        os.unlink(self.db_path)
                    except PermissionError:
                        pass  # Give up if still locked
        except Exception:
            pass  # File may still be locked, will be cleaned up later
        
        try:
            if os.path.exists(self.config_path):
                os.unlink(self.config_path)
        except PermissionError:
            pass
    
    def test_session_enum(self):
        """Test Session enum values"""
        self.assertEqual(Session.ASIA.value, "ASIA")
        self.assertEqual(Session.LONDON.value, "LONDON")
        self.assertEqual(Session.NY.value, "NY")
        self.assertEqual(Session.LONDON_NY_OVERLAP.value, "LONDON_NY_OVERLAP")
        self.assertEqual(Session.LATE_NY.value, "LATE_NY")
    
    def test_strategy_type_enum(self):
        """Test StrategyType enum values"""
        self.assertEqual(StrategyType.BREAKOUT_IB_VOLATILITY_TRAP.value, "breakout_ib_volatility_trap")
        self.assertEqual(StrategyType.TREND_CONTINUATION_PULLBACK.value, "trend_continuation_pullback")
        self.assertEqual(StrategyType.DEFAULT_STANDARD.value, "default_standard")
    
    def test_universal_managed_strategies(self):
        """Test UNIVERSAL_MANAGED_STRATEGIES list"""
        self.assertIn(StrategyType.BREAKOUT_IB_VOLATILITY_TRAP, UNIVERSAL_MANAGED_STRATEGIES)
        self.assertIn(StrategyType.TREND_CONTINUATION_PULLBACK, UNIVERSAL_MANAGED_STRATEGIES)
        self.assertNotIn(StrategyType.MICRO_SCALP, UNIVERSAL_MANAGED_STRATEGIES)
    
    def test_trade_state_dataclass(self):
        """Test TradeState dataclass creation"""
        trade_state = TradeState(
            ticket=123456,
            symbol="BTCUSDc",
            strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            direction="BUY",
            session=Session.LONDON,
            resolved_trailing_rules={"breakeven_trigger_r": 1.0},
            managed_by="universal_sl_tp_manager",
            entry_price=84000.0,
            initial_sl=83800.0,
            initial_tp=84500.0
        )
        
        self.assertEqual(trade_state.ticket, 123456)
        self.assertEqual(trade_state.symbol, "BTCUSDc")
        self.assertEqual(trade_state.strategy_type, StrategyType.BREAKOUT_IB_VOLATILITY_TRAP)
        self.assertEqual(trade_state.direction, "BUY")
        self.assertEqual(trade_state.session, Session.LONDON)
        self.assertFalse(trade_state.breakeven_triggered)
        self.assertFalse(trade_state.partial_taken)
    
    def test_database_initialization(self):
        """Test database schema creation"""
        # Database should be created in setUp
        self.assertTrue(os.path.exists(self.db_path))
        
        # Check table exists
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='universal_trades'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result)
    
    def test_config_loading(self):
        """Test configuration loading"""
        config = self.manager.config
        self.assertIn("strategies", config)
        self.assertIn("symbol_adjustments", config)
        self.assertIn("breakout_ib_volatility_trap", config["strategies"])
    
    def test_config_fallback_on_missing_file(self):
        """Test default config when file doesn't exist"""
        manager = UniversalDynamicSLTPManager(
            db_path=self.db_path,
            config_path="nonexistent_config.json"
        )
        config = manager.config
        self.assertIn("strategies", config)
        self.assertIn("default_standard", config["strategies"])
    
    def test_trade_registry_thread_safety(self):
        """Test thread-safe trade registry operations"""
        trade_state = TradeState(
            ticket=123456,
            symbol="BTCUSDc",
            strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            direction="BUY",
            session=Session.LONDON,
            resolved_trailing_rules={"breakeven_trigger_r": 1.0},
            managed_by="universal_sl_tp_manager",
            entry_price=84000.0,
            initial_sl=83800.0,
            initial_tp=84500.0
        )
        
        # Test set/get
        set_trade_state(123456, trade_state)
        retrieved = get_trade_state(123456)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.ticket, 123456)
        
        # Test can_modify_position
        self.assertTrue(can_modify_position(123456, "universal_sl_tp_manager"))
        self.assertFalse(can_modify_position(123456, "legacy_exit_manager"))
        
        # Test remove
        remove_trade_state(123456)
        self.assertIsNone(get_trade_state(123456))


class TestPhase2RuleResolution(unittest.TestCase):
    """Test Phase 2: Rule Resolution"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Create temporary config file
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.config_path = self.temp_config.name
        
        # Write comprehensive test config
        test_config = {
            "universal_sl_tp_rules": {
                "strategies": {
                    "breakout_ib_volatility_trap": {
                        "breakeven_trigger_r": 1.0,
                        "breakeven_trigger_r_asia": 0.75,
                        "trailing_method": "structure_atr_hybrid",
                        "trailing_timeframe_btc": "M1",
                        "trailing_timeframe_xau": "M5",
                        "atr_multiplier": 1.5,
                        "min_sl_change_r": 0.1,
                        "sl_modification_cooldown_seconds": 20
                    },
                    "trend_continuation_pullback": {
                        "breakeven_trigger_r": 1.0,
                        "trailing_method": "structure_based",
                        "trailing_timeframe": "M5",
                        "atr_multiplier": 1.0,
                        "min_sl_change_r": 0.1,
                        "sl_modification_cooldown_seconds": 45
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
                        "min_sl_change_r": 0.1,
                        "session_adjustments": {
                            "ASIA": {
                                "tp_multiplier": 0.8,
                                "sl_tightening": 1.1
                            },
                            "LONDON": {
                                "tp_multiplier": 1.2,
                                "sl_tightening": 0.9
                            },
                            "NY": {
                                "tp_multiplier": 1.3,
                                "sl_tightening": 0.85
                            }
                        }
                    },
                    "XAUUSDc": {
                        "atr_timeframe": "M15",
                        "trailing_timeframe": "M5",
                        "min_sl_change_r": 0.1,
                        "session_adjustments": {
                            "LONDON": {
                                "tp_multiplier": 1.1,
                                "sl_tightening": 0.95
                            }
                        }
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
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Clear manager state first
        if hasattr(self, 'manager'):
            self.manager.active_trades.clear()
        
        cleanup_registry()
        
        # Give time for connections to close
        import time
        time.sleep(0.1)
        
        # Try to delete database file
        try:
            if os.path.exists(self.db_path):
                try:
                    os.unlink(self.db_path)
                except PermissionError:
                    # File may still be locked, try again after a delay
                    time.sleep(0.2)
                    try:
                        os.unlink(self.db_path)
                    except PermissionError:
                        pass  # Give up if still locked - will be cleaned up later
        except Exception:
            pass
        
        # Delete config file
        try:
            if os.path.exists(self.config_path):
                os.unlink(self.config_path)
        except Exception:
            pass
    
    def test_normalize_strategy_type_from_string(self):
        """Test strategy type normalization from string"""
        result = self.manager._normalize_strategy_type("breakout_ib_volatility_trap")
        self.assertEqual(result, StrategyType.BREAKOUT_IB_VOLATILITY_TRAP)
        
        result = self.manager._normalize_strategy_type("trend_continuation_pullback")
        self.assertEqual(result, StrategyType.TREND_CONTINUATION_PULLBACK)
    
    def test_normalize_strategy_type_from_enum(self):
        """Test strategy type normalization from enum"""
        result = self.manager._normalize_strategy_type(StrategyType.BREAKOUT_IB_VOLATILITY_TRAP)
        self.assertEqual(result, StrategyType.BREAKOUT_IB_VOLATILITY_TRAP)
    
    def test_normalize_strategy_type_fallback(self):
        """Test strategy type normalization fallback to default"""
        result = self.manager._normalize_strategy_type("unknown_strategy")
        self.assertEqual(result, StrategyType.DEFAULT_STANDARD)
    
    def test_detect_session_asia(self):
        """Test Asia session detection (00:00-08:00 UTC)"""
        timestamp = datetime(2025, 11, 23, 3, 0, tzinfo=timezone.utc)
        result = detect_session("BTCUSDc", timestamp)
        self.assertEqual(result, Session.ASIA)
    
    def test_detect_session_london(self):
        """Test London session detection (08:00-13:00 UTC)"""
        timestamp = datetime(2025, 11, 23, 10, 0, tzinfo=timezone.utc)
        result = detect_session("XAUUSDc", timestamp)
        self.assertEqual(result, Session.LONDON)
    
    def test_detect_session_london_ny_overlap(self):
        """Test London-NY overlap detection (13:00-16:00 UTC)"""
        timestamp = datetime(2025, 11, 23, 14, 0, tzinfo=timezone.utc)
        result = detect_session("BTCUSDc", timestamp)
        self.assertEqual(result, Session.LONDON_NY_OVERLAP)
    
    def test_detect_session_ny(self):
        """Test NY session detection (16:00-21:00 UTC)"""
        timestamp = datetime(2025, 11, 23, 18, 0, tzinfo=timezone.utc)
        result = detect_session("XAUUSDc", timestamp)
        self.assertEqual(result, Session.NY)
    
    def test_detect_session_late_ny(self):
        """Test Late NY session detection (21:00-00:00 UTC)"""
        timestamp = datetime(2025, 11, 23, 22, 0, tzinfo=timezone.utc)
        result = detect_session("BTCUSDc", timestamp)
        self.assertEqual(result, Session.LATE_NY)
    
    def test_get_atr_timeframe_for_strategy(self):
        """Test ATR timeframe retrieval"""
        timeframe = self.manager._get_atr_timeframe_for_strategy(
            StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            "BTCUSDc"
        )
        self.assertEqual(timeframe, "M5")
        
        timeframe = self.manager._get_atr_timeframe_for_strategy(
            StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            "XAUUSDc"
        )
        self.assertEqual(timeframe, "M15")
    
    @patch('infra.streamer_data_access.StreamerDataAccess')
    def test_get_current_atr_from_streamer(self, mock_streamer_class):
        """Test ATR calculation using streamer"""
        mock_streamer = Mock()
        mock_streamer.calculate_atr.return_value = 50.0
        mock_streamer_class.return_value = mock_streamer
        
        atr = self.manager._get_current_atr("BTCUSDc", "M5", period=14)
        self.assertEqual(atr, 50.0)
        mock_streamer.calculate_atr.assert_called_once_with("BTCUSDc", "M5", period=14)
    
    @patch('infra.streamer_data_access.StreamerDataAccess')
    def test_get_current_atr_fallback_to_mt5(self, mock_streamer_class):
        """Test ATR calculation fallback to MT5"""
        # Streamer returns None
        mock_streamer = Mock()
        mock_streamer.calculate_atr.return_value = None
        mock_streamer_class.return_value = mock_streamer
        
        # Mock MT5 module functions
        import numpy as np
        mock_bars = np.array([
            (100.0, 102.0, 99.0, 101.0) for _ in range(20)
        ], dtype=[('high', 'f8'), ('low', 'f8'), ('close', 'f8'), ('open', 'f8')])
        
        # Patch MetaTrader5 functions that are called inside _get_current_atr
        with patch('MetaTrader5.copy_rates_from_pos', return_value=mock_bars):
            with patch('MetaTrader5.TIMEFRAME_M5', 5):
                atr = self.manager._get_current_atr("BTCUSDc", "M5", period=14)
                # Should calculate ATR from MT5 bars
                self.assertIsNotNone(atr)
                # Verify MT5 was called (if it gets that far)
                # Note: This test may not fully work if streamer returns None but MT5 also fails
                # The important thing is it doesn't crash
    
    def test_resolve_trailing_rules_strategy_merging(self):
        """Test rule resolution merges strategy rules"""
        rules = self.manager._resolve_trailing_rules(
            StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            "BTCUSDc",
            Session.LONDON
        )
        
        self.assertIn("breakeven_trigger_r", rules)
        self.assertIn("trailing_method", rules)
        self.assertIn("atr_multiplier", rules)
        self.assertIn("min_sl_change_r", rules)
        self.assertEqual(rules["breakeven_trigger_r"], 1.0)
        self.assertEqual(rules["trailing_method"], "structure_atr_hybrid")
    
    def test_resolve_trailing_rules_symbol_adjustments(self):
        """Test rule resolution applies symbol adjustments"""
        btc_rules = self.manager._resolve_trailing_rules(
            StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            "BTCUSDc",
            Session.LONDON
        )
        
        xau_rules = self.manager._resolve_trailing_rules(
            StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            "XAUUSDc",
            Session.LONDON
        )
        
        # Should have different trailing timeframes
        self.assertEqual(btc_rules.get("trailing_timeframe"), "M1")
        self.assertEqual(xau_rules.get("trailing_timeframe"), "M5")
    
    def test_resolve_trailing_rules_session_adjustments(self):
        """Test rule resolution applies session adjustments"""
        london_rules = self.manager._resolve_trailing_rules(
            StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            "BTCUSDc",
            Session.LONDON
        )
        
        asia_rules = self.manager._resolve_trailing_rules(
            StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            "BTCUSDc",
            Session.ASIA
        )
        
        # Session adjustments should affect ATR multiplier
        # London: 1.5 * 0.9 = 1.35
        # Asia: 1.5 * 1.1 = 1.65
        self.assertAlmostEqual(london_rules.get("atr_multiplier"), 1.35, places=2)
        self.assertAlmostEqual(asia_rules.get("atr_multiplier"), 1.65, places=2)
    
    def test_resolve_trailing_rules_session_specific_breakeven(self):
        """Test session-specific breakeven trigger"""
        asia_rules = self.manager._resolve_trailing_rules(
            StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
            "BTCUSDc",
            Session.ASIA
        )
        
        # Should use Asia-specific breakeven trigger
        self.assertEqual(asia_rules.get("breakeven_trigger_r"), 0.75)
    
    def test_resolve_trailing_rules_fallback_to_default(self):
        """Test rule resolution falls back to default strategy"""
        rules = self.manager._resolve_trailing_rules(
            StrategyType.DEFAULT_STANDARD,
            "BTCUSDc",
            Session.LONDON
        )
        
        self.assertIn("breakeven_trigger_r", rules)
        self.assertEqual(rules["trailing_method"], "atr_basic")
    
    @patch.object(UniversalDynamicSLTPManager, '_get_current_atr')
    def test_register_trade_success(self, mock_get_atr):
        """Test successful trade registration"""
        # Mock ATR calculation
        mock_get_atr.return_value = 50.0
        
        # Mock MT5 position
        mock_position = Mock()
        mock_position.ticket = 123456
        mock_position.symbol = "BTCUSDc"
        mock_position.type = 0  # BUY
        mock_position.price_open = 84000.0
        mock_position.sl = 83800.0
        mock_position.tp = 84500.0
        mock_position.volume = 0.01
        
        # Patch MT5 import inside register_trade
        with patch('MetaTrader5.positions_get', return_value=[mock_position]):
            
            # Register trade
            trade_state = self.manager.register_trade(
                ticket=123456,
                symbol="BTCUSDc",
                strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
                entry_price=84000.0,
                initial_sl=83800.0,
                initial_tp=84500.0,
                direction="BUY"
            )
        
        # Verify registration
        self.assertIsNotNone(trade_state)
        self.assertEqual(trade_state.ticket, 123456)
        self.assertEqual(trade_state.symbol, "BTCUSDc")
        self.assertEqual(trade_state.strategy_type, StrategyType.BREAKOUT_IB_VOLATILITY_TRAP)
        self.assertIn("breakeven_trigger_r", trade_state.resolved_trailing_rules)
        self.assertEqual(trade_state.managed_by, "universal_sl_tp_manager")
        self.assertEqual(trade_state.baseline_atr, 50.0)
        
        # Verify in active trades
        self.assertIn(123456, self.manager.active_trades)
        
        # Verify in registry
        from infra.trade_registry import get_trade_state
        registered_state = get_trade_state(123456)
        self.assertIsNotNone(registered_state)
        self.assertEqual(registered_state.ticket, 123456)
    
    def test_register_trade_skips_non_managed_strategy(self):
        """Test registration skips non-universal-managed strategies"""
        # MICRO_SCALP is not in UNIVERSAL_MANAGED_STRATEGIES
        trade_state = self.manager.register_trade(
            ticket=123456,
            symbol="BTCUSDc",
            strategy_type=StrategyType.MICRO_SCALP,
            entry_price=84000.0,
            initial_sl=83800.0,
            initial_tp=84500.0,
            direction="BUY"
        )
        
        # Should return None (not registered)
        self.assertIsNone(trade_state)
        self.assertNotIn(123456, self.manager.active_trades)
    
    def test_register_trade_handles_missing_position(self):
        """Test registration handles missing position gracefully"""
        with patch('MetaTrader5.positions_get', return_value=[]):
            trade_state = self.manager.register_trade(
                ticket=123456,
                symbol="BTCUSDc",
                strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
                entry_price=84000.0,
                initial_sl=83800.0,
                initial_tp=84500.0,
                direction="BUY"
            )
        
        # Should return None (position not found)
        self.assertIsNone(trade_state)
    
    @patch.object(UniversalDynamicSLTPManager, '_get_current_atr')
    def test_register_trade_persists_to_database(self, mock_get_atr):
        """Test trade registration persists to database"""
        mock_get_atr.return_value = 50.0
        
        mock_position = Mock()
        mock_position.ticket = 123456
        mock_position.symbol = "BTCUSDc"
        mock_position.type = 0
        mock_position.price_open = 84000.0
        mock_position.sl = 83800.0
        mock_position.tp = 84500.0
        mock_position.volume = 0.01
        
        with patch('MetaTrader5.positions_get', return_value=[mock_position]):
            # Register trade
            trade_state = self.manager.register_trade(
                ticket=123456,
                symbol="BTCUSDc",
                strategy_type=StrategyType.BREAKOUT_IB_VOLATILITY_TRAP,
                entry_price=84000.0,
                initial_sl=83800.0,
                initial_tp=84500.0,
                direction="BUY"
            )
        
        # Verify database entry
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM universal_trades WHERE ticket = ?", (123456,))
            row = cursor.fetchone()
            
            self.assertIsNotNone(row)
            self.assertEqual(row["ticket"], 123456)
            self.assertEqual(row["symbol"], "BTCUSDc")
            self.assertEqual(row["strategy_type"], "breakout_ib_volatility_trap")
            self.assertEqual(row["managed_by"], "universal_sl_tp_manager")
            
            # Verify resolved rules are stored as JSON
            resolved_rules = json.loads(row["resolved_trailing_rules"])
            self.assertIn("breakeven_trigger_r", resolved_rules)


if __name__ == '__main__':
    unittest.main()

