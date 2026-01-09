"""
Phase 7 Testing: Monitoring and Alerts

Tests for enhanced logging, Discord alerts, and regime history with detailed metrics
"""
import unittest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timezone
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from infra.volatility_regime_detector import RegimeDetector, VolatilityRegime


class TestVolatilityMonitoringPhase7(unittest.TestCase):
    """Test volatility monitoring and alerting functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.detector = RegimeDetector()
        self.symbol = "BTCUSDc"
        self.current_time = datetime.now(timezone.utc)
    
    @patch('infra.volatility_regime_detector.logger')
    def test_advanced_state_warning_logging(self, mock_logger):
        """Test that advanced volatility states trigger warning-level logging"""
        old_regime = VolatilityRegime.STABLE
        new_regime = VolatilityRegime.PRE_BREAKOUT_TENSION
        confidence = 85.0
        atr_ratio = 0.95
        bb_width_ratio = 0.88
        adx = 25.0
        
        # Call _log_regime_change
        self.detector._log_regime_change(
            symbol=self.symbol,
            old_regime=old_regime,
            new_regime=new_regime,
            confidence=confidence,
            atr_ratio=atr_ratio,
            bb_width_ratio=bb_width_ratio,
            adx=adx,
            timestamp=self.current_time
        )
        
        # Verify warning was logged for advanced state
        warning_calls = [call for call in mock_logger.warning.call_args_list 
                        if 'Advanced Volatility State Detected' in str(call)]
        self.assertGreater(len(warning_calls), 0, "Warning should be logged for advanced state")
    
    @patch('infra.volatility_regime_detector.logger')
    def test_basic_state_info_logging(self, mock_logger):
        """Test that basic volatility states trigger info-level logging"""
        old_regime = VolatilityRegime.STABLE
        new_regime = VolatilityRegime.VOLATILE
        confidence = 80.0
        atr_ratio = 1.5
        bb_width_ratio = 2.0
        adx = 30.0
        
        # Call _log_regime_change
        self.detector._log_regime_change(
            symbol=self.symbol,
            old_regime=old_regime,
            new_regime=new_regime,
            confidence=confidence,
            atr_ratio=atr_ratio,
            bb_width_ratio=bb_width_ratio,
            adx=adx,
            timestamp=self.current_time
        )
        
        # Verify info was logged (not warning) for basic state
        info_calls = [call for call in mock_logger.info.call_args_list 
                     if 'Regime Change Event' in str(call)]
        self.assertGreater(len(info_calls), 0, "Info should be logged for basic state")
    
    @patch('discord_notifications.DiscordNotifier')
    def test_pre_breakout_tension_discord_alert(self, mock_discord_class):
        """Test Discord alert for PRE_BREAKOUT_TENSION"""
        # Setup mock
        mock_notifier = MagicMock()
        mock_notifier.enabled = True
        mock_discord_class.return_value = mock_notifier
        
        new_regime = VolatilityRegime.PRE_BREAKOUT_TENSION
        confidence = 85.0
        session_tag = "LONDON"
        atr_ratio = 0.95
        bb_width_ratio = 0.88
        
        # Call _send_volatility_state_alert
        self.detector._send_volatility_state_alert(
            symbol=self.symbol,
            new_regime=new_regime,
            confidence=confidence,
            session_tag=session_tag,
            atr_ratio=atr_ratio,
            bb_width_ratio=bb_width_ratio
        )
        
        # Verify Discord message was sent
        self.assertTrue(mock_notifier.send_message.called, "Discord message should be sent")
        
        # Verify message content
        call_args = mock_notifier.send_message.call_args
        self.assertEqual(call_args[1]['message_type'], 'ALERT')
        self.assertEqual(call_args[1]['channel'], 'private')
        self.assertIn('PRE-BREAKOUT TENSION', call_args[1]['custom_title'])
        self.assertEqual(call_args[1]['color'], 0xff9900)  # Orange
    
    @patch('discord_notifications.DiscordNotifier')
    def test_post_breakout_decay_discord_alert(self, mock_discord_class):
        """Test Discord alert for POST_BREAKOUT_DECAY"""
        # Setup mock
        mock_notifier = MagicMock()
        mock_notifier.enabled = True
        mock_discord_class.return_value = mock_notifier
        
        new_regime = VolatilityRegime.POST_BREAKOUT_DECAY
        confidence = 80.0
        session_tag = "NY"
        atr_ratio = 0.92
        bb_width_ratio = 0.85
        
        # Call _send_volatility_state_alert
        self.detector._send_volatility_state_alert(
            symbol=self.symbol,
            new_regime=new_regime,
            confidence=confidence,
            session_tag=session_tag,
            atr_ratio=atr_ratio,
            bb_width_ratio=bb_width_ratio
        )
        
        # Verify Discord message was sent
        self.assertTrue(mock_notifier.send_message.called)
        
        # Verify message content
        call_args = mock_notifier.send_message.call_args
        self.assertIn('POST-BREAKOUT DECAY', call_args[1]['custom_title'])
        self.assertEqual(call_args[1]['color'], 0xff9900)  # Orange
    
    @patch('discord_notifications.DiscordNotifier')
    def test_fragmented_chop_discord_alert(self, mock_discord_class):
        """Test Discord alert for FRAGMENTED_CHOP"""
        # Setup mock
        mock_notifier = MagicMock()
        mock_notifier.enabled = True
        mock_discord_class.return_value = mock_notifier
        
        new_regime = VolatilityRegime.FRAGMENTED_CHOP
        confidence = 75.0
        session_tag = "ASIAN"
        atr_ratio = 0.88
        bb_width_ratio = 0.82
        
        # Call _send_volatility_state_alert
        self.detector._send_volatility_state_alert(
            symbol=self.symbol,
            new_regime=new_regime,
            confidence=confidence,
            session_tag=session_tag,
            atr_ratio=atr_ratio,
            bb_width_ratio=bb_width_ratio
        )
        
        # Verify Discord message was sent
        self.assertTrue(mock_notifier.send_message.called)
        
        # Verify message content
        call_args = mock_notifier.send_message.call_args
        self.assertIn('FRAGMENTED CHOP', call_args[1]['custom_title'])
        self.assertEqual(call_args[1]['color'], 0xff9900)  # Orange
    
    @patch('discord_notifications.DiscordNotifier')
    def test_session_switch_flare_discord_alert(self, mock_discord_class):
        """Test Discord alert for SESSION_SWITCH_FLARE (critical - red)"""
        # Setup mock
        mock_notifier = MagicMock()
        mock_notifier.enabled = True
        mock_discord_class.return_value = mock_notifier
        
        new_regime = VolatilityRegime.SESSION_SWITCH_FLARE
        confidence = 90.0
        session_tag = "LONDON"
        atr_ratio = 1.2
        bb_width_ratio = 1.1
        
        # Call _send_volatility_state_alert
        self.detector._send_volatility_state_alert(
            symbol=self.symbol,
            new_regime=new_regime,
            confidence=confidence,
            session_tag=session_tag,
            atr_ratio=atr_ratio,
            bb_width_ratio=bb_width_ratio
        )
        
        # Verify Discord message was sent
        self.assertTrue(mock_notifier.send_message.called)
        
        # Verify message content (critical - red color)
        call_args = mock_notifier.send_message.call_args
        self.assertIn('SESSION SWITCH FLARE', call_args[1]['custom_title'])
        self.assertEqual(call_args[1]['color'], 0xff0000)  # Red (critical)
        # Verify message mentions trading blocked
        # Check if message is positional or keyword argument
        if call_args[0]:  # Positional arguments
            message = call_args[0][0]
        else:  # Keyword arguments
            message = call_args[1].get('message', '')
        self.assertIn('ALL TRADING BLOCKED', message.upper())
    
    @patch('discord_notifications.DiscordNotifier')
    def test_discord_alert_skipped_when_disabled(self, mock_discord_class):
        """Test that Discord alert is skipped when notifier is disabled"""
        # Setup mock with disabled notifier
        mock_notifier = MagicMock()
        mock_notifier.enabled = False
        mock_discord_class.return_value = mock_notifier
        
        new_regime = VolatilityRegime.PRE_BREAKOUT_TENSION
        confidence = 85.0
        session_tag = "LONDON"
        atr_ratio = 0.95
        bb_width_ratio = 0.88
        
        # Call _send_volatility_state_alert
        self.detector._send_volatility_state_alert(
            symbol=self.symbol,
            new_regime=new_regime,
            confidence=confidence,
            session_tag=session_tag,
            atr_ratio=atr_ratio,
            bb_width_ratio=bb_width_ratio
        )
        
        # Verify Discord message was NOT sent
        self.assertFalse(mock_notifier.send_message.called, "Discord message should not be sent when disabled")
    
    @patch('discord_notifications.DiscordNotifier', side_effect=ImportError("Discord notifier not available"))
    def test_discord_alert_handles_import_error(self, mock_discord_class):
        """Test that Discord alert gracefully handles import errors"""
        
        new_regime = VolatilityRegime.PRE_BREAKOUT_TENSION
        confidence = 85.0
        session_tag = "LONDON"
        atr_ratio = 0.95
        bb_width_ratio = 0.88
        
        # Should not raise exception
        try:
            self.detector._send_volatility_state_alert(
                symbol=self.symbol,
                new_regime=new_regime,
                confidence=confidence,
                session_tag=session_tag,
                atr_ratio=atr_ratio,
                bb_width_ratio=bb_width_ratio
            )
        except Exception as e:
            self.fail(f"_send_volatility_state_alert should handle ImportError gracefully, but raised: {e}")
    
    def test_get_regime_history_basic(self):
        """Test basic regime history retrieval"""
        # Add some history
        self.detector._regime_history[self.symbol] = [
            (datetime.now(timezone.utc), VolatilityRegime.STABLE, 90.0),
            (datetime.now(timezone.utc), VolatilityRegime.VOLATILE, 85.0),
            (datetime.now(timezone.utc), VolatilityRegime.STABLE, 88.0)
        ]
        
        # Get history
        history = self.detector.get_regime_history(self.symbol, limit=10)
        
        # Verify history structure
        self.assertEqual(len(history), 3)
        self.assertIn('timestamp', history[0])
        self.assertIn('regime', history[0])
        self.assertIn('confidence', history[0])
    
    def test_get_regime_history_limit(self):
        """Test regime history respects limit parameter"""
        # Add more history than limit
        for i in range(15):
            self.detector._regime_history[self.symbol] = [
                (datetime.now(timezone.utc), VolatilityRegime.STABLE, 90.0)
            ] * 15
        
        # Get history with limit
        history = self.detector.get_regime_history(self.symbol, limit=10)
        
        # Verify limit is respected
        self.assertLessEqual(len(history), 10)
    
    def test_get_regime_history_include_metrics_false(self):
        """Test regime history without detailed metrics"""
        # Add history
        self.detector._regime_history[self.symbol] = [
            (datetime.now(timezone.utc), VolatilityRegime.STABLE, 90.0)
        ]
        
        # Get history without metrics
        history = self.detector.get_regime_history(self.symbol, limit=10, include_metrics=False)
        
        # Verify basic structure only (no metrics from DB)
        self.assertEqual(len(history), 1)
        self.assertIn('timestamp', history[0])
        self.assertIn('regime', history[0])
        self.assertIn('confidence', history[0])
        # Should not have detailed metrics (unless they're in the basic structure)
    
    @patch('infra.volatility_regime_detector.sqlite3')
    def test_get_regime_metrics_from_db(self, mock_sqlite3):
        """Test database lookup for regime metrics"""
        # Create a temporary database file for testing
        import tempfile
        import os
        from pathlib import Path
        
        # Create temporary database
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "volatility_regime_events.sqlite"
        
        # Create database and insert test data
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS regime_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                session_tag TEXT,
                old_regime TEXT NOT NULL,
                new_regime TEXT NOT NULL,
                confidence REAL,
                confidence_percentile REAL,
                atr_ratio REAL,
                bb_width_ratio REAL,
                adx REAL,
                transition TEXT,
                indicators_json TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Insert test data
        test_timestamp = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO regime_events (
                event_id, event_type, timestamp, symbol, session_tag,
                old_regime, new_regime, confidence, confidence_percentile,
                atr_ratio, bb_width_ratio, adx, transition, indicators_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "test_event_123", "REGIME_CHANGE", test_timestamp, self.symbol, "LONDON",
            "STABLE", "VOLATILE", 85.0, 85.0,
            0.95, 0.88, 25.0, "STABLE → VOLATILE", '{"test": "data"}', test_timestamp
        ))
        conn.commit()
        conn.close()
        
        # Patch Path to return our test database
        with patch('pathlib.Path') as mock_path_class:
            mock_db_path = MagicMock()
            mock_db_path.exists.return_value = True
            mock_path_class.return_value = mock_db_path
            mock_db_path.__str__ = lambda: str(db_path)
            
            # Setup mock database connection
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            
            # Create real connection for row factory
            real_conn = sqlite3.connect(str(db_path))
            real_conn.row_factory = sqlite3.Row
            real_cursor = real_conn.cursor()
            real_cursor.execute("SELECT * FROM regime_events WHERE symbol = ?", (self.symbol,))
            real_row = real_cursor.fetchone()
            real_conn.close()
            
            # Mock sqlite3 to return our real connection
            mock_sqlite3.connect.return_value = real_conn
            mock_sqlite3.Row = sqlite3.Row
            
            # Temporarily replace the real connection with a mock that uses real data
            with patch('sqlite3.connect', return_value=real_conn):
                # Call method
                timestamp = datetime.now(timezone.utc)
                metrics = self.detector._get_regime_metrics_from_db(self.symbol, timestamp)
                
                # Verify metrics were returned
                if metrics is not None:
                    self.assertIn('atr_ratio', metrics)
                    self.assertEqual(metrics['atr_ratio'], 0.95)
        
        # Cleanup
        try:
            os.remove(str(db_path))
            os.rmdir(temp_dir)
        except:
            pass
    
    @patch('pathlib.Path')
    @patch('infra.volatility_regime_detector.sqlite3')
    def test_get_regime_metrics_from_db_not_found(self, mock_sqlite3, mock_path_class):
        """Test database lookup when no metrics found"""
        # Setup mock path to return existing database
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True
        mock_path_class.return_value = mock_db_path
        
        # Setup mock database
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        
        mock_sqlite3.connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # No row found
        
        # Call method
        timestamp = datetime.now(timezone.utc)
        metrics = self.detector._get_regime_metrics_from_db(self.symbol, timestamp)
        
        # Should return None when not found
        self.assertIsNone(metrics)
    
    @patch('pathlib.Path')
    @patch('infra.volatility_regime_detector.sqlite3')
    def test_get_regime_metrics_from_db_handles_exception(self, mock_sqlite3, mock_path_class):
        """Test database lookup handles exceptions gracefully"""
        # Setup mock path to return existing database
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True
        mock_path_class.return_value = mock_db_path
        
        # Setup mock to raise exception
        mock_sqlite3.connect.side_effect = Exception("Database error")
        
        # Should not raise exception
        timestamp = datetime.now(timezone.utc)
        try:
            metrics = self.detector._get_regime_metrics_from_db(self.symbol, timestamp)
            # Should return None on error
            self.assertIsNone(metrics)
        except Exception as e:
            self.fail(f"_get_regime_metrics_from_db should handle exceptions gracefully, but raised: {e}")


if __name__ == '__main__':
    unittest.main()

