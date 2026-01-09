# =====================================
# tests/test_phase2_3_threshold_tuning.py
# =====================================
"""
Tests for Phase 2.3: Dynamic Threshold Tuning Integration
Tests SymbolThresholdManager threshold calculations
"""

import unittest
import sys
import os
import tempfile
from unittest.mock import Mock, MagicMock

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.m1_threshold_calibrator import SymbolThresholdManager


class TestPhase2_3ThresholdTuning(unittest.TestCase):
    """Test cases for Phase 2.3 Dynamic Threshold Tuning"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary config file
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_config.write('''{
  "symbol_profiles": {
    "BTCUSD": {
      "base": 75,
      "vol_weight": 0.6,
      "sess_weight": 0.4
    },
    "XAUUSD": {
      "base": 70,
      "vol_weight": 0.5,
      "sess_weight": 0.6
    },
    "EURUSD": {
      "base": 65,
      "vol_weight": 0.4,
      "sess_weight": 0.7
    }
  },
  "session_bias": {
    "ASIAN": {
      "BTCUSD": 0.9,
      "XAUUSD": 0.85,
      "EURUSD": 0.8
    },
    "LONDON": {
      "BTCUSD": 1.0,
      "XAUUSD": 1.1,
      "EURUSD": 1.0
    },
    "OVERLAP": {
      "BTCUSD": 1.1,
      "XAUUSD": 1.2,
      "EURUSD": 1.1
    },
    "NY": {
      "BTCUSD": 1.0,
      "XAUUSD": 1.0,
      "EURUSD": 1.0
    },
    "POST_NY": {
      "BTCUSD": 0.95,
      "XAUUSD": 0.9,
      "EURUSD": 0.85
    }
  }
}''')
        self.temp_config.close()
        self.config_path = self.temp_config.name
        
        # Create threshold manager
        self.threshold_manager = SymbolThresholdManager(profile_file=self.config_path)
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.config_path):
            os.unlink(self.config_path)
    
    def test_symbol_normalization(self):
        """Test that symbols are normalized correctly"""
        # Test with 'c' suffix
        base1 = self.threshold_manager.get_base_confidence("BTCUSDc")
        base2 = self.threshold_manager.get_base_confidence("BTCUSD")
        self.assertEqual(base1, base2, "Symbols with and without 'c' should be normalized")
    
    def test_get_base_confidence(self):
        """Test base confidence retrieval"""
        # Test known symbols
        btc_base = self.threshold_manager.get_base_confidence("BTCUSD")
        self.assertEqual(btc_base, 75.0)
        
        xau_base = self.threshold_manager.get_base_confidence("XAUUSD")
        self.assertEqual(xau_base, 70.0)
        
        eur_base = self.threshold_manager.get_base_confidence("EURUSD")
        self.assertEqual(eur_base, 65.0)
        
        # Test unknown symbol (should return default)
        unknown_base = self.threshold_manager.get_base_confidence("UNKNOWN")
        self.assertEqual(unknown_base, 70.0)  # Default
    
    def test_get_session_bias(self):
        """Test session bias retrieval"""
        # Test known combinations
        btc_asian = self.threshold_manager.get_session_bias("ASIAN", "BTCUSD")
        self.assertEqual(btc_asian, 0.9)
        
        xau_overlap = self.threshold_manager.get_session_bias("OVERLAP", "XAUUSD")
        self.assertEqual(xau_overlap, 1.2)
        
        eur_london = self.threshold_manager.get_session_bias("LONDON", "EURUSD")
        self.assertEqual(eur_london, 1.0)
        
        # Test unknown combination (should return default)
        unknown_bias = self.threshold_manager.get_session_bias("UNKNOWN", "UNKNOWN")
        self.assertEqual(unknown_bias, 1.0)  # Default
    
    def test_compute_threshold_normal_conditions(self):
        """Test threshold calculation under normal conditions"""
        # EURUSD in London, normal ATR (ratio = 1.0)
        threshold = self.threshold_manager.compute_threshold(
            symbol="EURUSD",
            session="LONDON",
            atr_ratio=1.0
        )
        
        # Expected: base (65) * (1 + (1.0 - 1) * 0.4) * (1.0 ^ 0.7) = 65.0
        self.assertAlmostEqual(threshold, 65.0, places=1)
        self.assertGreaterEqual(threshold, 50.0)
        self.assertLessEqual(threshold, 95.0)
    
    def test_compute_threshold_high_volatility(self):
        """Test threshold calculation with high volatility (ATR ratio > 1.0)"""
        # BTCUSD in NY Overlap, high volatility (ATR ratio = 1.4)
        threshold = self.threshold_manager.compute_threshold(
            symbol="BTCUSD",
            session="OVERLAP",
            atr_ratio=1.4
        )
        
        # Expected: base (75) * (1 + (1.4 - 1) * 0.6) * (1.1 ^ 0.4)
        # = 75 * 1.24 * 1.039 ≈ 96.6
        self.assertGreater(threshold, 90.0, "High volatility should increase threshold")
        self.assertLessEqual(threshold, 95.0)  # Clamped to max
    
    def test_compute_threshold_low_volatility(self):
        """Test threshold calculation with low volatility (ATR ratio < 1.0)"""
        # XAUUSD in Asian, low volatility (ATR ratio = 0.8)
        threshold = self.threshold_manager.compute_threshold(
            symbol="XAUUSD",
            session="ASIAN",
            atr_ratio=0.8
        )
        
        # Expected: base (70) * (1 + (0.8 - 1) * 0.5) * (0.85 ^ 0.6)
        # = 70 * 0.9 * 0.91 ≈ 57.3
        self.assertLess(threshold, 70.0, "Low volatility should decrease threshold")
        self.assertGreaterEqual(threshold, 50.0)  # Clamped to min
    
    def test_compute_threshold_session_adjustment(self):
        """Test that session bias affects threshold"""
        # Same symbol, same ATR ratio, different sessions
        threshold_asian = self.threshold_manager.compute_threshold(
            symbol="XAUUSD",
            session="ASIAN",
            atr_ratio=1.0
        )
        
        threshold_overlap = self.threshold_manager.compute_threshold(
            symbol="XAUUSD",
            session="OVERLAP",
            atr_ratio=1.0
        )
        
        # Overlap should have higher threshold (stricter) than Asian
        self.assertGreater(threshold_overlap, threshold_asian,
                          "Overlap session should have stricter threshold than Asian")
    
    def test_compute_threshold_symbol_specific(self):
        """Test that different symbols have different thresholds"""
        # Same session, same ATR ratio, different symbols
        btc_threshold = self.threshold_manager.compute_threshold(
            symbol="BTCUSD",
            session="LONDON",
            atr_ratio=1.0
        )
        
        eur_threshold = self.threshold_manager.compute_threshold(
            symbol="EURUSD",
            session="LONDON",
            atr_ratio=1.0
        )
        
        # BTCUSD should have higher base threshold
        self.assertGreater(btc_threshold, eur_threshold,
                          "BTCUSD should have higher threshold than EURUSD")
    
    def test_compute_threshold_clamping(self):
        """Test that thresholds are clamped to 50-95 range"""
        # Extreme ATR ratio
        threshold_high = self.threshold_manager.compute_threshold(
            symbol="BTCUSD",
            session="OVERLAP",
            atr_ratio=3.0  # Very high volatility
        )
        
        threshold_low = self.threshold_manager.compute_threshold(
            symbol="EURUSD",
            session="ASIAN",
            atr_ratio=0.1  # Very low volatility
        )
        
        self.assertLessEqual(threshold_high, 95.0, "Threshold should be clamped to max 95")
        self.assertGreaterEqual(threshold_low, 50.0, "Threshold should be clamped to min 50")
    
    def test_get_symbol_profile(self):
        """Test symbol profile retrieval"""
        profile = self.threshold_manager.get_symbol_profile("BTCUSD")
        
        self.assertIn('base', profile)
        self.assertIn('vol_weight', profile)
        self.assertIn('sess_weight', profile)
        self.assertEqual(profile['base'], 75.0)
        self.assertEqual(profile['vol_weight'], 0.6)
        self.assertEqual(profile['sess_weight'], 0.4)
    
    def test_get_all_session_biases(self):
        """Test retrieval of all session biases for a symbol"""
        biases = self.threshold_manager.get_all_session_biases("XAUUSD")
        
        self.assertIn('ASIAN', biases)
        self.assertIn('LONDON', biases)
        self.assertIn('OVERLAP', biases)
        self.assertIn('NY', biases)
        self.assertIn('POST_NY', biases)
        
        self.assertEqual(biases['ASIAN'], 0.85)
        self.assertEqual(biases['OVERLAP'], 1.2)
    
    def test_default_profiles_fallback(self):
        """Test that default profiles are used if config file doesn't exist"""
        # Create manager with non-existent file
        manager = SymbolThresholdManager(profile_file="nonexistent.json")
        
        # Should still work with defaults
        threshold = manager.compute_threshold("BTCUSD", "LONDON", 1.0)
        self.assertIsNotNone(threshold)
        self.assertGreaterEqual(threshold, 50.0)
        self.assertLessEqual(threshold, 95.0)
    
    def test_threshold_calculation_examples(self):
        """Test specific calculation examples from plan"""
        # Example 1: BTCUSD in NY Overlap (ATR ratio: 1.4)
        # Expected: base=75, vol_adjusted=75*1.24=93.0, session=93.0*(1.1^0.4)≈96.8
        threshold1 = self.threshold_manager.compute_threshold("BTCUSD", "OVERLAP", 1.4)
        self.assertGreaterEqual(threshold1, 90.0)
        self.assertLessEqual(threshold1, 95.0)  # Clamped
        
        # Example 2: XAUUSD in Asian (ATR ratio: 0.8)
        # Expected: base=70, vol_adjusted=70*0.9=63.0, session=63.0*(0.85^0.6)≈57.3
        threshold2 = self.threshold_manager.compute_threshold("XAUUSD", "ASIAN", 0.8)
        self.assertLessEqual(threshold2, 70.0)
        self.assertGreaterEqual(threshold2, 50.0)  # Clamped
        
        # Example 3: EURUSD in London (ATR ratio: 1.0)
        # Expected: base=65, vol_adjusted=65*1.0=65.0, session=65.0*(1.0^0.7)=65.0
        threshold3 = self.threshold_manager.compute_threshold("EURUSD", "LONDON", 1.0)
        self.assertAlmostEqual(threshold3, 65.0, places=1)


if __name__ == '__main__':
    unittest.main()

