"""
Test Phase 1.1, 1.2, and 1.3.1-1.3.2 Implementation
Tests enum extension, configuration, and tracking infrastructure

⚠️ IMPORTANT: Activate virtual environment before running tests!

Run with:
    .\.venv\Scripts\Activate.ps1
    python -m unittest tests.test_volatility_phase1_basic -v

Or:
    .\.venv\Scripts\Activate.ps1
    python tests/test_volatility_phase1_basic.py
"""

import unittest
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.volatility_regime_detector import VolatilityRegime, RegimeDetector
from config import volatility_regime_config
import sqlite3


class TestPhase1_1_EnumExtension(unittest.TestCase):
    """Test Phase 1.1: Enum extension"""
    
    def test_existing_states(self):
        """Test existing volatility states"""
        self.assertEqual(VolatilityRegime.STABLE.value, "STABLE")
        self.assertEqual(VolatilityRegime.TRANSITIONAL.value, "TRANSITIONAL")
        self.assertEqual(VolatilityRegime.VOLATILE.value, "VOLATILE")
    
    def test_new_states(self):
        """Test new volatility states"""
        self.assertEqual(VolatilityRegime.PRE_BREAKOUT_TENSION.value, "PRE_BREAKOUT_TENSION")
        self.assertEqual(VolatilityRegime.POST_BREAKOUT_DECAY.value, "POST_BREAKOUT_DECAY")
        self.assertEqual(VolatilityRegime.FRAGMENTED_CHOP.value, "FRAGMENTED_CHOP")
        self.assertEqual(VolatilityRegime.SESSION_SWITCH_FLARE.value, "SESSION_SWITCH_FLARE")
    
    def test_all_states_count(self):
        """Test that we have all expected states"""
        all_states = [e.value for e in VolatilityRegime]
        expected_states = [
            "STABLE", "TRANSITIONAL", "VOLATILE",
            "PRE_BREAKOUT_TENSION", "POST_BREAKOUT_DECAY",
            "FRAGMENTED_CHOP", "SESSION_SWITCH_FLARE"
        ]
        self.assertEqual(len(all_states), 7)
        for state in expected_states:
            self.assertIn(state, all_states)


class TestPhase1_2_Configuration(unittest.TestCase):
    """Test Phase 1.2: Configuration parameters"""
    
    def test_pre_breakout_tension_config(self):
        """Test PRE_BREAKOUT_TENSION configuration"""
        self.assertTrue(hasattr(volatility_regime_config, 'BB_WIDTH_NARROW_THRESHOLD'))
        self.assertTrue(hasattr(volatility_regime_config, 'WICK_VARIANCE_INCREASE_THRESHOLD'))
        self.assertTrue(hasattr(volatility_regime_config, 'INTRABAR_VOLATILITY_RISING_THRESHOLD'))
        self.assertTrue(hasattr(volatility_regime_config, 'BB_WIDTH_TREND_WINDOW'))
        
        # Verify values are reasonable
        self.assertGreater(volatility_regime_config.BB_WIDTH_NARROW_THRESHOLD, 0)
        self.assertGreater(volatility_regime_config.WICK_VARIANCE_INCREASE_THRESHOLD, 0)
    
    def test_post_breakout_decay_config(self):
        """Test POST_BREAKOUT_DECAY configuration"""
        self.assertTrue(hasattr(volatility_regime_config, 'ATR_SLOPE_DECLINE_THRESHOLD'))
        self.assertTrue(hasattr(volatility_regime_config, 'ATR_ABOVE_BASELINE_THRESHOLD'))
        self.assertTrue(hasattr(volatility_regime_config, 'POST_BREAKOUT_TIME_WINDOW'))
        self.assertTrue(hasattr(volatility_regime_config, 'ATR_SLOPE_WINDOW'))
        
        self.assertLess(volatility_regime_config.ATR_SLOPE_DECLINE_THRESHOLD, 0)  # Should be negative
        self.assertGreater(volatility_regime_config.POST_BREAKOUT_TIME_WINDOW, 0)
    
    def test_fragmented_chop_config(self):
        """Test FRAGMENTED_CHOP configuration"""
        self.assertTrue(hasattr(volatility_regime_config, 'WHIPSAW_WINDOW'))
        self.assertTrue(hasattr(volatility_regime_config, 'WHIPSAW_MIN_DIRECTION_CHANGES'))
        self.assertTrue(hasattr(volatility_regime_config, 'MEAN_REVERSION_OSCILLATION_THRESHOLD'))
        self.assertTrue(hasattr(volatility_regime_config, 'LOW_MOMENTUM_ADX_THRESHOLD'))
    
    def test_session_switch_flare_config(self):
        """Test SESSION_SWITCH_FLARE configuration"""
        self.assertTrue(hasattr(volatility_regime_config, 'SESSION_TRANSITION_WINDOW_MINUTES'))
        self.assertTrue(hasattr(volatility_regime_config, 'VOLATILITY_SPIKE_THRESHOLD'))
        self.assertTrue(hasattr(volatility_regime_config, 'FLARE_RESOLUTION_DECLINE_THRESHOLD'))
        self.assertTrue(hasattr(volatility_regime_config, 'BASELINE_ATR_WINDOW'))


class TestPhase1_3_1_TrackingStructures(unittest.TestCase):
    """Test Phase 1.3.1: Tracking structures initialization"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.detector = RegimeDetector()
    
    def test_tracking_structures_exist(self):
        """Test that tracking structures are initialized"""
        self.assertTrue(hasattr(self.detector, '_atr_history'))
        self.assertTrue(hasattr(self.detector, '_wick_ratios_history'))
        self.assertTrue(hasattr(self.detector, '_breakout_cache'))
        self.assertTrue(hasattr(self.detector, '_volatility_spike_cache'))
    
    def test_thread_locks_exist(self):
        """Test that thread locks are initialized"""
        self.assertTrue(hasattr(self.detector, '_tracking_lock'))
        self.assertTrue(hasattr(self.detector, '_db_lock'))
    
    def test_ensure_symbol_tracking(self):
        """Test _ensure_symbol_tracking method"""
        test_symbol = "BTCUSDc"
        self.detector._ensure_symbol_tracking(test_symbol)
        
        self.assertIn(test_symbol, self.detector._atr_history)
        self.assertIn(test_symbol, self.detector._wick_ratios_history)
        self.assertIn(test_symbol, self.detector._breakout_cache)
        self.assertIn(test_symbol, self.detector._volatility_spike_cache)
        
        # Test structure format
        self.assertIn("M5", self.detector._atr_history[test_symbol])
        self.assertIn("M15", self.detector._atr_history[test_symbol])
        self.assertIn("H1", self.detector._atr_history[test_symbol])
    
    def test_normalize_rates_dataframe(self):
        """Test _normalize_rates with DataFrame"""
        import pandas as pd
        
        df = pd.DataFrame({
            'time': [1, 2, 3],
            'open': [100, 101, 102],
            'high': [105, 106, 107],
            'low': [95, 96, 97],
            'close': [103, 104, 105]
        })
        result = self.detector._normalize_rates(df)
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 3)
    
    def test_normalize_rates_numpy(self):
        """Test _normalize_rates with numpy array"""
        import numpy as np
        
        arr = np.array([
            [1, 100, 105, 95, 103, 1000],
            [2, 101, 106, 96, 104, 1100],
            [3, 102, 107, 97, 105, 1200]
        ])
        result = self.detector._normalize_rates(arr)
        import pandas as pd
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 3)
    
    def test_normalize_rates_none(self):
        """Test _normalize_rates with None"""
        result = self.detector._normalize_rates(None)
        self.assertIsNone(result)


class TestPhase1_3_2_Database(unittest.TestCase):
    """Test Phase 1.3.2: Database initialization"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.detector = RegimeDetector()
    
    def test_database_path(self):
        """Test database path is configured"""
        self.assertTrue(hasattr(self.detector, '_db_path'))
        self.assertEqual(self.detector._db_path, "data/volatility_regime_events.sqlite")
    
    def test_database_file_exists(self):
        """Test database file exists"""
        self.assertTrue(os.path.exists(self.detector._db_path), 
                       f"Database file not found: {self.detector._db_path}")
    
    def test_table_exists(self):
        """Test breakout_events table exists"""
        conn = sqlite3.connect(self.detector._db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='breakout_events'
        """)
        table_exists = cursor.fetchone() is not None
        conn.close()
        
        self.assertTrue(table_exists, "breakout_events table not found")
    
    def test_table_structure(self):
        """Test table has required columns"""
        conn = sqlite3.connect(self.detector._db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(breakout_events)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()
        
        required_columns = [
            'id', 'symbol', 'timeframe', 'breakout_type', 
            'breakout_price', 'breakout_timestamp', 'is_active'
        ]
        for col in required_columns:
            self.assertIn(col, columns, f"Column {col} not found in breakout_events table")
    
    def test_indices_exist(self):
        """Test indices are created"""
        conn = sqlite3.connect(self.detector._db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND tbl_name='breakout_events'
        """)
        indices = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        # Should have at least one index
        self.assertGreater(len(indices), 0, "No indices found for breakout_events table")


def run_tests():
    """Run all Phase 1.1-1.3.2 tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPhase1_1_EnumExtension))
    suite.addTests(loader.loadTestsFromTestCase(TestPhase1_2_Configuration))
    suite.addTests(loader.loadTestsFromTestCase(TestPhase1_3_1_TrackingStructures))
    suite.addTests(loader.loadTestsFromTestCase(TestPhase1_3_2_Database))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

