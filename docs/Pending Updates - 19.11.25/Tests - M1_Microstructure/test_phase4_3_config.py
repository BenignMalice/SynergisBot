# =====================================
# tests/test_phase4_3_config.py
# =====================================
"""
Tests for Phase 4.3: Configuration System
Tests M1ConfigLoader configuration loading and access
"""

import unittest
import sys
import os
import tempfile
import json
from pathlib import Path

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.m1_config_loader import M1ConfigLoader


class TestPhase4_3Config(unittest.TestCase):
    """Test cases for Phase 4.3 Configuration System"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary config file
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_config.write('''{
  "m1_data": {
    "enabled": true,
    "max_candles_per_symbol": 200,
    "refresh_interval_active_scalp": 30,
    "refresh_interval_active": 60,
    "refresh_interval_inactive": 300,
    "force_refresh_on_stale": true,
    "stale_threshold_seconds": 180,
    "skip_weekend_refresh": true,
    "weekend_start_utc": "21:00",
    "weekend_end_utc": "22:00",
    "symbols": {
      "active_scalp": ["XAUUSD", "BTCUSD"],
      "active": ["EURUSD", "GBPUSD"]
    },
    "choch_detection": {
      "require_3_candle_confirmation": true,
      "confidence_threshold": 70,
      "symbol_thresholds": {
        "BTCUSD": 75,
        "XAUUSD": 72,
        "EURUSD": 70
      },
      "session_adjustments": {
        "ASIAN": 5.0,
        "LONDON": -5.0,
        "OVERLAP": -8.0
      }
    },
    "cache": {
      "enabled": true,
      "ttl_seconds": 300
    },
    "snapshots": {
      "enabled": true,
      "interval": 1800
    }
  }
}''')
        self.temp_config.close()
        
        self.config_loader = M1ConfigLoader(config_path=self.temp_config.name)
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_config.name):
            os.unlink(self.temp_config.name)
    
    def test_load_config(self):
        """Test loading configuration from file"""
        self.assertTrue(self.config_loader.is_enabled())
        self.assertIsNotNone(self.config_loader.get_m1_config())
    
    def test_get_value(self):
        """Test getting configuration value"""
        enabled = self.config_loader.get("m1_data.enabled")
        self.assertTrue(enabled)
        
        max_candles = self.config_loader.get("m1_data.max_candles_per_symbol")
        self.assertEqual(max_candles, 200)
    
    def test_get_default_value(self):
        """Test getting default value when key not found"""
        value = self.config_loader.get("m1_data.nonexistent", default="default_value")
        self.assertEqual(value, "default_value")
    
    def test_get_refresh_interval_active_scalp(self):
        """Test getting refresh interval for active_scalp symbols"""
        interval = self.config_loader.get_refresh_interval("XAUUSD")
        self.assertEqual(interval, 30)
        
        interval = self.config_loader.get_refresh_interval("BTCUSD")
        self.assertEqual(interval, 30)
    
    def test_get_refresh_interval_active(self):
        """Test getting refresh interval for active symbols"""
        interval = self.config_loader.get_refresh_interval("EURUSD")
        self.assertEqual(interval, 60)
        
        interval = self.config_loader.get_refresh_interval("GBPUSD")
        self.assertEqual(interval, 60)
    
    def test_get_refresh_interval_inactive(self):
        """Test getting refresh interval for inactive symbols"""
        interval = self.config_loader.get_refresh_interval("UNKNOWN")
        self.assertEqual(interval, 300)  # Default to inactive
    
    def test_get_choch_config(self):
        """Test getting CHOCH detection configuration"""
        choch_config = self.config_loader.get_choch_config()
        
        self.assertIn("require_3_candle_confirmation", choch_config)
        self.assertIn("confidence_threshold", choch_config)
        self.assertTrue(choch_config["require_3_candle_confirmation"])
        self.assertEqual(choch_config["confidence_threshold"], 70)
    
    def test_get_cache_config(self):
        """Test getting cache configuration"""
        cache_config = self.config_loader.get_cache_config()
        
        self.assertIn("enabled", cache_config)
        self.assertIn("ttl_seconds", cache_config)
        self.assertTrue(cache_config["enabled"])
        self.assertEqual(cache_config["ttl_seconds"], 300)
    
    def test_get_snapshot_config(self):
        """Test getting snapshot configuration"""
        snapshot_config = self.config_loader.get_snapshot_config()
        
        self.assertIn("enabled", snapshot_config)
        self.assertIn("interval", snapshot_config)
        self.assertTrue(snapshot_config["enabled"])
        self.assertEqual(snapshot_config["interval"], 1800)
    
    def test_get_symbol_threshold_direct_match(self):
        """Test getting symbol threshold with direct match"""
        threshold = self.config_loader.get_symbol_threshold("BTCUSD")
        self.assertEqual(threshold, 75)
        
        threshold = self.config_loader.get_symbol_threshold("XAUUSD")
        self.assertEqual(threshold, 72)
        
        threshold = self.config_loader.get_symbol_threshold("EURUSD")
        self.assertEqual(threshold, 70)
    
    def test_get_symbol_threshold_pattern_match(self):
        """Test getting symbol threshold with pattern matching"""
        # Update config to include pattern matching
        config = self.config_loader.config
        config["m1_data"]["choch_detection"]["symbol_thresholds"]["BTC*"] = 75
        config["m1_data"]["choch_detection"]["symbol_thresholds"]["XAU*"] = 72
        config["m1_data"]["choch_detection"]["symbol_thresholds"]["FOREX*"] = 70
        
        threshold = self.config_loader.get_symbol_threshold("BTCETH")
        self.assertEqual(threshold, 75)
        
        threshold = self.config_loader.get_symbol_threshold("XAUUSD")
        self.assertEqual(threshold, 72)  # Direct match takes precedence
        
        threshold = self.config_loader.get_symbol_threshold("GBPUSD")
        self.assertEqual(threshold, 70)
    
    def test_get_symbol_threshold_not_found(self):
        """Test getting symbol threshold when not configured"""
        threshold = self.config_loader.get_symbol_threshold("UNKNOWN")
        self.assertIsNone(threshold)
    
    def test_get_session_adjustment(self):
        """Test getting session-based threshold adjustment"""
        adjustment = self.config_loader.get_session_adjustment("ASIAN")
        self.assertEqual(adjustment, 5.0)
        
        adjustment = self.config_loader.get_session_adjustment("LONDON")
        self.assertEqual(adjustment, -5.0)
        
        adjustment = self.config_loader.get_session_adjustment("OVERLAP")
        self.assertEqual(adjustment, -8.0)
    
    def test_get_session_adjustment_not_found(self):
        """Test getting session adjustment when not configured"""
        adjustment = self.config_loader.get_session_adjustment("UNKNOWN")
        self.assertEqual(adjustment, 0.0)  # Default to 0
    
    def test_should_refresh_on_weekend_btc(self):
        """Test weekend refresh check for BTC (should refresh)"""
        should_refresh = self.config_loader.should_refresh_on_weekend("BTCUSD")
        self.assertTrue(should_refresh)  # BTC trades 24/7
    
    def test_should_refresh_on_weekend_forex(self):
        """Test weekend refresh check for forex (should skip)"""
        should_refresh = self.config_loader.should_refresh_on_weekend("EURUSD")
        self.assertFalse(should_refresh)  # Forex skips weekend
    
    def test_should_refresh_on_weekend_when_disabled(self):
        """Test weekend refresh when skip_weekend_refresh is false"""
        # Update config
        self.config_loader.config["m1_data"]["skip_weekend_refresh"] = False
        
        should_refresh = self.config_loader.should_refresh_on_weekend("EURUSD")
        self.assertTrue(should_refresh)  # Should refresh if skip is disabled
    
    def test_default_config(self):
        """Test default configuration when file doesn't exist"""
        loader = M1ConfigLoader(config_path="nonexistent.json")
        
        # Should use defaults
        self.assertTrue(loader.is_enabled())
        self.assertEqual(loader.get_refresh_interval("XAUUSD"), 30)
        self.assertIsNotNone(loader.get_choch_config())
    
    def test_reload_config(self):
        """Test reloading configuration"""
        # Modify config file
        with open(self.temp_config.name, 'r') as f:
            config = json.load(f)
        
        config["m1_data"]["enabled"] = False
        
        with open(self.temp_config.name, 'w') as f:
            json.dump(config, f)
        
        # Reload
        self.config_loader.reload()
        
        # Should reflect changes
        self.assertFalse(self.config_loader.is_enabled())


if __name__ == '__main__':
    unittest.main()

