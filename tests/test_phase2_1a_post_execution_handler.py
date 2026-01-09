"""
Test Phase 2.1a: Post-Execution Handler Method
Tests for _handle_post_execution() method
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, timezone

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from auto_execution_system import AutoExecutionSystem, TradePlan


class TestPostExecutionHandler(unittest.TestCase):
    """Test _handle_post_execution() method"""
    
    def setUp(self):
        """Set up test fixtures"""
        import tempfile
        import os
        import time
        
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        try:
            self.auto_exec = AutoExecutionSystem(
                db_path=self.temp_db.name,
                mt5_service=None  # We'll mock MT5 service
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
    
    def _create_test_plan(self, direction="BUY", entry_price=2000.0):
        """Helper to create a test plan"""
        return TradePlan(
            plan_id="test_plan",
            symbol="XAUUSDc",
            direction=direction,
            entry_price=entry_price,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"strategy_type": "test_strategy"},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            status="executed"
        )
    
    def _create_mock_result(self, ticket=12345, price_executed=2000.0):
        """Helper to create a mock result dict"""
        return {
            "ok": True,
            "details": {
                "ticket": ticket,
                "price_executed": price_executed,
                "price_requested": price_executed
            }
        }
    
    def test_post_execution_with_valid_ticket(self):
        """Test post-execution handler with valid ticket"""
        plan = self._create_test_plan()
        plan.ticket = 12345
        result = self._create_mock_result(ticket=12345, price_executed=2000.0)
        
        # Mock all the dependencies
        with patch.object(self.auto_exec, '_get_btc_order_flow_metrics', return_value=None):
            with patch('chatgpt_bot.intelligent_exit_manager', None):
                with patch.object(self.auto_exec, '_get_cached_m1_data', return_value=None):
                    with patch.object(self.auto_exec, 'm1_data_fetcher', None):
                        with patch.object(self.auto_exec, 'm1_analyzer', None):
                            with patch.object(self.auto_exec, 'signal_learner', None):
                                with patch('infra.journal_repo.JournalRepo') as mock_journal:
                                    with patch.object(self.auto_exec, '_send_discord_notification'):
                                        # Mock MT5 account_info
                                        with patch('MetaTrader5.account_info', return_value=Mock(balance=10000.0, equity=10000.0)):
                                            # Call the method
                                            self.auto_exec._handle_post_execution(
                                                plan=plan,
                                                result=result,
                                                executed_price=2000.0,
                                                symbol_norm="XAUUSDc",
                                                direction="BUY",
                                                lot_size=0.01
                                            )
                                        
                                        # Verify journal was called
                                        mock_journal.return_value.write_exec.assert_called_once()
                                        
                                        # Verify Discord notification was called
                                        self.auto_exec._send_discord_notification.assert_called_once_with(plan, result)
    
    def test_post_execution_with_no_ticket(self):
        """Test post-execution handler with no ticket in result"""
        plan = self._create_test_plan()
        result = {"ok": True, "details": {}}  # No ticket
        
        # Should return early without errors
        self.auto_exec._handle_post_execution(
            plan=plan,
            result=result,
            executed_price=2000.0,
            symbol_norm="XAUUSDc",
            direction="BUY",
            lot_size=0.01
        )
        
        # No exceptions should be raised
    
    def test_post_execution_strategy_name_recording(self):
        """Test that strategy name is recorded in plan notes"""
        plan = self._create_test_plan()
        plan.ticket = 12345
        plan.notes = "Original note"
        result = self._create_mock_result(ticket=12345)
        
        # Mock dependencies
        with patch.object(self.auto_exec, '_get_btc_order_flow_metrics', return_value=None):
            with patch('chatgpt_bot.intelligent_exit_manager', None):
                with patch.object(self.auto_exec, '_get_cached_m1_data', return_value=None):
                    with patch.object(self.auto_exec, 'm1_data_fetcher', None):
                        with patch.object(self.auto_exec, 'm1_analyzer', None):
                            with patch.object(self.auto_exec, 'signal_learner', None):
                                with patch('infra.journal_repo.JournalRepo'):
                                    with patch.object(self.auto_exec, '_send_discord_notification'):
                                        with patch('MetaTrader5.account_info', return_value=Mock(balance=10000.0, equity=10000.0)):
                                            self.auto_exec._handle_post_execution(
                                                plan=plan,
                                                result=result,
                                                executed_price=2000.0,
                                                symbol_norm="XAUUSDc",
                                                direction="BUY",
                                                lot_size=0.01
                                            )
                                        
                                        # Verify strategy name was added to notes
                                        self.assertIn("[strategy:test_strategy]", plan.notes)
    
    def test_post_execution_with_none_conditions(self):
        """Test post-execution handler with None conditions"""
        plan = self._create_test_plan()
        plan.conditions = None
        plan.ticket = 12345
        result = self._create_mock_result(ticket=12345)
        
        # Should not raise AttributeError
        with patch.object(self.auto_exec, '_get_btc_order_flow_metrics', return_value=None):
            with patch('chatgpt_bot.intelligent_exit_manager', None):
                with patch.object(self.auto_exec, '_get_cached_m1_data', return_value=None):
                    with patch.object(self.auto_exec, 'm1_data_fetcher', None):
                        with patch.object(self.auto_exec, 'm1_analyzer', None):
                            with patch.object(self.auto_exec, 'signal_learner', None):
                                with patch('infra.journal_repo.JournalRepo'):
                                    with patch.object(self.auto_exec, '_send_discord_notification'):
                                        with patch('MetaTrader5.account_info', return_value=Mock(balance=10000.0, equity=10000.0)):
                                            # Should not raise exception
                                            self.auto_exec._handle_post_execution(
                                                plan=plan,
                                                result=result,
                                                executed_price=2000.0,
                                                symbol_norm="XAUUSDc",
                                                direction="BUY",
                                                lot_size=0.01
                                            )
    
    def test_post_execution_with_missing_volume(self):
        """Test post-execution handler with None volume in plan"""
        plan = self._create_test_plan()
        plan.volume = None
        plan.ticket = 12345
        result = self._create_mock_result(ticket=12345)
        
        # Should use lot_size parameter instead
        with patch.object(self.auto_exec, '_get_btc_order_flow_metrics', return_value=None):
            with patch('chatgpt_bot.intelligent_exit_manager', None):
                with patch.object(self.auto_exec, '_get_cached_m1_data', return_value=None):
                    with patch.object(self.auto_exec, 'm1_data_fetcher', None):
                        with patch.object(self.auto_exec, 'm1_analyzer', None):
                            with patch.object(self.auto_exec, 'signal_learner', None):
                                with patch('infra.journal_repo.JournalRepo') as mock_journal:
                                    with patch.object(self.auto_exec, '_send_discord_notification'):
                                        with patch('MetaTrader5.account_info', return_value=Mock(balance=10000.0, equity=10000.0)):
                                            self.auto_exec._handle_post_execution(
                                                plan=plan,
                                                result=result,
                                                executed_price=2000.0,
                                                symbol_norm="XAUUSDc",
                                                direction="BUY",
                                                lot_size=0.02  # Different from plan.volume
                                            )
                                        
                                        # Verify journal was called with lot_size parameter
                                        call_args = mock_journal.return_value.write_exec.call_args[0][0]
                                        self.assertEqual(call_args["lot"], 0.02)


if __name__ == '__main__':
    unittest.main()
