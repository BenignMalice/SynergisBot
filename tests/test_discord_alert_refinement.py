"""
Test script for BOS/CHOCH Alert Refinement Implementation
Tests tiered alert handling, symbol-specific thresholds, and confidence decay mechanism.
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import unittest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta, timezone
import json
import tempfile
import shutil

# Test imports
try:
    from infra.discord_alert_dispatcher import (
        DiscordAlertDispatcher,
        ConfidenceDecayTracker,
        AlertFormatter,
        AlertData
    )
    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)


class TestConfidenceDecayTracker(unittest.TestCase):
    """Test ConfidenceDecayTracker class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "confidence_decay": {
                "enabled": True,
                "validation_window_minutes": 5,
                "decay_duration_minutes": 30,
                "threshold_adjustment": 5,
                "min_movement_atr": 0.1
            }
        }
        self.tracker = ConfidenceDecayTracker(self.config)
    
    def test_register_alert_70_79_confidence(self):
        """Test registering alert with 70-79% confidence"""
        self.tracker.register_alert("XAUUSDc", "CHOCH_BULL", 2000.0, "buy", 75)
        self.assertEqual(len(self.tracker.tracked_alerts), 1)
        
        key = ("XAUUSDc", "CHOCH_BULL")
        self.assertIn(key, self.tracker.tracked_alerts)
        self.assertEqual(self.tracker.tracked_alerts[key]["price"], 2000.0)
        self.assertEqual(self.tracker.tracked_alerts[key]["direction"], "buy")
    
    def test_register_alert_below_70_ignored(self):
        """Test that alerts below 70% are not tracked"""
        self.tracker.register_alert("XAUUSDc", "CHOCH_BULL", 2000.0, "buy", 65)
        self.assertEqual(len(self.tracker.tracked_alerts), 0)
    
    def test_register_alert_above_80_ignored(self):
        """Test that alerts above 80% are not tracked"""
        self.tracker.register_alert("XAUUSDc", "CHOCH_BULL", 2000.0, "buy", 85)
        self.assertEqual(len(self.tracker.tracked_alerts), 0)
    
    def test_get_threshold_adjustment_no_decay(self):
        """Test threshold adjustment when no decay is active"""
        adjustment = self.tracker.get_threshold_adjustment("XAUUSDc", "CHOCH_BULL")
        self.assertEqual(adjustment, 0)
    
    def test_get_threshold_adjustment_with_decay(self):
        """Test threshold adjustment when decay is active"""
        # Manually activate decay
        key = ("XAUUSDc", "CHOCH_BULL")
        self.tracker.active_decays[key] = {
            "activated_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30),
            "threshold_adjustment": 5
        }
        
        adjustment = self.tracker.get_threshold_adjustment("XAUUSDc", "CHOCH_BULL")
        self.assertEqual(adjustment, 5)
    
    def test_check_price_movement_buy_signal_success(self):
        """Test price movement validation for buy signal that succeeds"""
        # Register alert
        self.tracker.register_alert("XAUUSDc", "CHOCH_BULL", 2000.0, "buy", 75)
        
        # Simulate time passing (5+ minutes)
        key = ("XAUUSDc", "CHOCH_BULL")
        self.tracker.tracked_alerts[key]["timestamp"] = datetime.now(timezone.utc) - timedelta(minutes=6)
        
        # Price moved up by more than 0.1 ATR (ATR = 10, so 0.1 ATR = 1.0)
        current_price = 2001.5  # Moved up 1.5
        atr = 10.0
        
        self.tracker.check_price_movement("XAUUSDc", "CHOCH_BULL", current_price, atr)
        
        # Should not activate decay (price moved correctly)
        self.assertNotIn(key, self.tracker.active_decays)
        # Should remove from tracked alerts
        self.assertNotIn(key, self.tracker.tracked_alerts)
    
    def test_check_price_movement_buy_signal_failure(self):
        """Test price movement validation for buy signal that fails"""
        # Register alert
        self.tracker.register_alert("XAUUSDc", "CHOCH_BULL", 2000.0, "buy", 75)
        
        # Simulate time passing (5+ minutes)
        key = ("XAUUSDc", "CHOCH_BULL")
        self.tracker.tracked_alerts[key]["timestamp"] = datetime.now(timezone.utc) - timedelta(minutes=6)
        
        # Price didn't move up (stayed same or went down)
        current_price = 2000.0  # No movement
        atr = 10.0
        
        self.tracker.check_price_movement("XAUUSDc", "CHOCH_BULL", current_price, atr)
        
        # Should activate decay
        self.assertIn(key, self.tracker.active_decays)
        self.assertEqual(self.tracker.active_decays[key]["threshold_adjustment"], 5)
    
    def test_cleanup_expired(self):
        """Test cleanup of expired decay entries"""
        key = ("XAUUSDc", "CHOCH_BULL")
        # Add expired decay
        self.tracker.active_decays[key] = {
            "activated_at": datetime.now(timezone.utc) - timedelta(minutes=31),
            "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
            "threshold_adjustment": 5
        }
        
        self.tracker.cleanup_expired()
        
        # Expired decay should be removed
        self.assertNotIn(key, self.tracker.active_decays)


class TestTieredAlertHandling(unittest.TestCase):
    """Test tiered alert handling (70-79% log only, 80%+ Discord)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            "enabled": True,
            "min_confidence": 70,
            "actionable_threshold": 80,
            "symbols": ["XAUUSDc"],
            "alerts": {
                "choch": {"enabled": True, "timeframes": ["M5"], "cooldown_minutes": 5}
            }
        }
        
        # Patch the info_alerts_dir
        with patch('infra.discord_alert_dispatcher.Path') as mock_path:
            mock_path.return_value.mkdir = Mock()
            self.dispatcher = DiscordAlertDispatcher.__new__(DiscordAlertDispatcher)
            self.dispatcher.config = self.config
            self.dispatcher.throttler = Mock()
            self.dispatcher.throttler.can_send = Mock(return_value=True)
            self.dispatcher.throttler.record_sent = Mock()
            self.dispatcher.formatter = AlertFormatter()
            self.dispatcher.cross_tf = Mock()
            self.dispatcher.cross_tf.check = Mock(return_value="PASSED")
            self.dispatcher.decay_tracker = ConfidenceDecayTracker(self.config)
            self.dispatcher.info_alerts_dir = Path(self.temp_dir) / "alerts_informational"
            self.dispatcher.info_alerts_dir.mkdir(parents=True, exist_ok=True)
            self.dispatcher.discord_notifier = None
    
    def tearDown(self):
        """Clean up temp directory"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_symbol_threshold_default(self):
        """Test getting default threshold when no symbol override"""
        threshold = self.dispatcher._get_symbol_threshold("UNKNOWN", "min_confidence")
        self.assertEqual(threshold, 70)
    
    def test_get_symbol_threshold_override(self):
        """Test getting symbol-specific threshold"""
        self.config["symbol_overrides"] = {
            "XAUUSDc": {"min_confidence": 80, "actionable_threshold": 80}
        }
        self.dispatcher.config = self.config
        
        threshold = self.dispatcher._get_symbol_threshold("XAUUSDc", "min_confidence")
        self.assertEqual(threshold, 80)
    
    @patch('infra.discord_alert_dispatcher.calculate_confluence')
    async def test_send_alert_70_79_logs_only(self, mock_confluence):
        """Test that 70-79% alerts are logged but not sent to Discord"""
        mock_confluence.return_value = 75  # 75% confidence
        
        detection = {
            "type": "CHOCH_BULL",
            "direction": "buy",
            "price": 2000.0,
            "notes": "Test alert"
        }
        
        result = await self.dispatcher._send_alert(
            symbol="XAUUSDc",
            timeframe="M5",
            detection=detection,
            session="London",
            h1_trend="Bullish",
            volatility="EXPANDING",
            m5_candles=[],
            m15_candles=[]
        )
        
        # Should return False (not sent to Discord)
        self.assertFalse(result)
        
        # Check that log file was created
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        log_file = self.dispatcher.info_alerts_dir / f"{date_str}.jsonl"
        self.assertTrue(log_file.exists())
        
        # Check log content
        with open(log_file, 'r') as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 1)
            logged_alert = json.loads(lines[0])
            self.assertEqual(logged_alert["confidence"], 75)
            self.assertEqual(logged_alert["symbol"], "XAUUSDc")
    
    @patch('infra.discord_alert_dispatcher.calculate_confluence')
    async def test_send_alert_80_plus_sends_to_discord(self, mock_confluence):
        """Test that 80%+ alerts are sent to Discord"""
        mock_confluence.return_value = 85  # 85% confidence
        
        # Mock Discord notifier
        self.dispatcher.discord_notifier = Mock()
        self.dispatcher.discord_notifier.enabled = True
        self.dispatcher._send_to_webhook = AsyncMock(return_value=True)
        self.dispatcher._get_channel_for_symbol = Mock(return_value="gold")
        self.dispatcher.channel_webhooks = {}
        
        detection = {
            "type": "CHOCH_BULL",
            "direction": "buy",
            "price": 2000.0,
            "notes": "Test alert"
        }
        
        result = await self.dispatcher._send_alert(
            symbol="XAUUSDc",
            timeframe="M5",
            detection=detection,
            session="London",
            h1_trend="Bullish",
            volatility="EXPANDING",
            m5_candles=[],
            m15_candles=[]
        )
        
        # Should return True (sent to Discord)
        self.assertTrue(result)
        
        # Check that log file was NOT created (80%+ alerts don't get logged)
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        log_file = self.dispatcher.info_alerts_dir / f"{date_str}.jsonl"
        # File might exist from previous test, but this alert shouldn't be in it
        if log_file.exists():
            with open(log_file, 'r') as f:
                lines = f.readlines()
                # Check that no 85% confidence alert is logged
                for line in lines:
                    logged_alert = json.loads(line)
                    self.assertNotEqual(logged_alert.get("confidence"), 85)


class TestSymbolSpecificThresholds(unittest.TestCase):
    """Test symbol-specific threshold functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "min_confidence": 70,
            "actionable_threshold": 80,
            "symbol_overrides": {
                "XAUUSDc": {"min_confidence": 80, "actionable_threshold": 80},
                "BTCUSDc": {"min_confidence": 75, "actionable_threshold": 80}
            }
        }
        
        with patch('infra.discord_alert_dispatcher.Path') as mock_path:
            mock_path.return_value.mkdir = Mock()
            self.dispatcher = DiscordAlertDispatcher.__new__(DiscordAlertDispatcher)
            self.dispatcher.config = self.config
            self.dispatcher.formatter = AlertFormatter()
    
    def test_xauusd_threshold_80(self):
        """Test XAUUSD has 80% threshold"""
        min_conf = self.dispatcher._get_symbol_threshold("XAUUSDc", "min_confidence")
        actionable = self.dispatcher._get_symbol_threshold("XAUUSDc", "actionable_threshold")
        self.assertEqual(min_conf, 80)
        self.assertEqual(actionable, 80)
    
    def test_btcusd_threshold_75(self):
        """Test BTCUSD has 75% min threshold, 80% actionable"""
        min_conf = self.dispatcher._get_symbol_threshold("BTCUSDc", "min_confidence")
        actionable = self.dispatcher._get_symbol_threshold("BTCUSDc", "actionable_threshold")
        self.assertEqual(min_conf, 75)
        self.assertEqual(actionable, 80)
    
    def test_default_symbol_uses_global(self):
        """Test unknown symbol uses global thresholds"""
        min_conf = self.dispatcher._get_symbol_threshold("UNKNOWN", "min_confidence")
        actionable = self.dispatcher._get_symbol_threshold("UNKNOWN", "actionable_threshold")
        self.assertEqual(min_conf, 70)
        self.assertEqual(actionable, 80)


class TestConfidenceDecayIntegration(unittest.TestCase):
    """Test confidence decay integration with alert sending"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "enabled": True,
            "min_confidence": 70,
            "actionable_threshold": 80,
            "symbols": ["XAUUSDc"],
            "confidence_decay": {
                "enabled": True,
                "validation_window_minutes": 5,
                "decay_duration_minutes": 30,
                "threshold_adjustment": 5,
                "min_movement_atr": 0.1
            },
            "alerts": {
                "choch": {"enabled": True, "timeframes": ["M5"], "cooldown_minutes": 5}
            }
        }
        
        with patch('infra.discord_alert_dispatcher.Path') as mock_path:
            mock_path.return_value.mkdir = Mock()
            self.dispatcher = DiscordAlertDispatcher.__new__(DiscordAlertDispatcher)
            self.dispatcher.config = self.config
            self.dispatcher.throttler = Mock()
            self.dispatcher.throttler.can_send = Mock(return_value=True)
            self.dispatcher.formatter = AlertFormatter()
            self.dispatcher.cross_tf = Mock()
            self.dispatcher.cross_tf.check = Mock(return_value="PASSED")
            self.dispatcher.decay_tracker = ConfidenceDecayTracker(self.config)
            self.dispatcher.discord_notifier = None
    
    @patch('infra.discord_alert_dispatcher.calculate_confluence')
    async def test_decay_adjustment_applied(self, mock_confluence):
        """Test that decay adjustment is applied to thresholds"""
        mock_confluence.return_value = 75  # 75% confidence
        
        # Activate decay manually
        key = ("XAUUSDc", "CHOCH_BULL")
        self.dispatcher.decay_tracker.active_decays[key] = {
            "activated_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30),
            "threshold_adjustment": 5
        }
        
        detection = {
            "type": "CHOCH_BULL",
            "direction": "buy",
            "price": 2000.0,
            "notes": "Test alert"
        }
        
        # With decay, effective min_confidence = 70 + 5 = 75
        # 75% confidence should pass min threshold but fail actionable (80+5=85)
        result = await self.dispatcher._send_alert(
            symbol="XAUUSDc",
            timeframe="M5",
            detection=detection,
            session="London",
            h1_trend="Bullish",
            volatility="EXPANDING",
            m5_candles=[],
            m15_candles=[]
        )
        
        # Should be logged (75% < 85% actionable with decay)
        self.assertFalse(result)  # Not sent to Discord


def run_tests():
    """Run all tests"""
    print("=" * 80)
    print("Testing BOS/CHOCH Alert Refinement Implementation")
    print("=" * 80)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestConfidenceDecayTracker))
    suite.addTests(loader.loadTestsFromTestCase(TestTieredAlertHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestSymbolSpecificThresholds))
    suite.addTests(loader.loadTestsFromTestCase(TestConfidenceDecayIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print()
    print("=" * 80)
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED")
    else:
        print(f"❌ SOME TESTS FAILED: {len(result.failures)} failures, {len(result.errors)} errors")
    print("=" * 80)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())

