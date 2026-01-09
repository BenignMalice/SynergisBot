"""
Test Phase 1.1, 1.2, and 1.3.1-1.3.2 Implementation
Tests enum extension, configuration, and tracking infrastructure
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from infra.volatility_regime_detector import VolatilityRegime, RegimeDetector
from config import volatility_regime_config
import sqlite3

def test_enum_extension():
    """Test Phase 1.1: Enum extension"""
    print("Testing Phase 1.1: Enum Extension...")
    
    # Test existing states
    assert VolatilityRegime.STABLE.value == "STABLE"
    assert VolatilityRegime.TRANSITIONAL.value == "TRANSITIONAL"
    assert VolatilityRegime.VOLATILE.value == "VOLATILE"
    
    # Test new states
    assert VolatilityRegime.PRE_BREAKOUT_TENSION.value == "PRE_BREAKOUT_TENSION"
    assert VolatilityRegime.POST_BREAKOUT_DECAY.value == "POST_BREAKOUT_DECAY"
    assert VolatilityRegime.FRAGMENTED_CHOP.value == "FRAGMENTED_CHOP"
    assert VolatilityRegime.SESSION_SWITCH_FLARE.value == "SESSION_SWITCH_FLARE"
    
    print("✅ Phase 1.1: Enum extension - PASSED")
    return True

def test_configuration_parameters():
    """Test Phase 1.2: Configuration parameters"""
    print("\nTesting Phase 1.2: Configuration Parameters...")
    
    # Test PRE_BREAKOUT_TENSION config
    assert hasattr(volatility_regime_config, 'BB_WIDTH_NARROW_THRESHOLD')
    assert hasattr(volatility_regime_config, 'WICK_VARIANCE_INCREASE_THRESHOLD')
    assert hasattr(volatility_regime_config, 'INTRABAR_VOLATILITY_RISING_THRESHOLD')
    assert hasattr(volatility_regime_config, 'BB_WIDTH_TREND_WINDOW')
    
    # Test POST_BREAKOUT_DECAY config
    assert hasattr(volatility_regime_config, 'ATR_SLOPE_DECLINE_THRESHOLD')
    assert hasattr(volatility_regime_config, 'ATR_ABOVE_BASELINE_THRESHOLD')
    assert hasattr(volatility_regime_config, 'POST_BREAKOUT_TIME_WINDOW')
    assert hasattr(volatility_regime_config, 'ATR_SLOPE_WINDOW')
    
    # Test FRAGMENTED_CHOP config
    assert hasattr(volatility_regime_config, 'WHIPSAW_WINDOW')
    assert hasattr(volatility_regime_config, 'WHIPSAW_MIN_DIRECTION_CHANGES')
    assert hasattr(volatility_regime_config, 'MEAN_REVERSION_OSCILLATION_THRESHOLD')
    assert hasattr(volatility_regime_config, 'LOW_MOMENTUM_ADX_THRESHOLD')
    
    # Test SESSION_SWITCH_FLARE config
    assert hasattr(volatility_regime_config, 'SESSION_TRANSITION_WINDOW_MINUTES')
    assert hasattr(volatility_regime_config, 'VOLATILITY_SPIKE_THRESHOLD')
    assert hasattr(volatility_regime_config, 'FLARE_RESOLUTION_DECLINE_THRESHOLD')
    assert hasattr(volatility_regime_config, 'BASELINE_ATR_WINDOW')
    
    # Verify values are reasonable
    assert volatility_regime_config.BB_WIDTH_NARROW_THRESHOLD > 0
    assert volatility_regime_config.WICK_VARIANCE_INCREASE_THRESHOLD > 0
    assert volatility_regime_config.POST_BREAKOUT_TIME_WINDOW > 0
    
    print("✅ Phase 1.2: Configuration parameters - PASSED")
    return True

def test_tracking_structures():
    """Test Phase 1.3.1: Tracking structures initialization"""
    print("\nTesting Phase 1.3.1: Tracking Structures...")
    
    detector = RegimeDetector()
    
    # Test tracking structures exist
    assert hasattr(detector, '_atr_history')
    assert hasattr(detector, '_wick_ratios_history')
    assert hasattr(detector, '_breakout_cache')
    assert hasattr(detector, '_volatility_spike_cache')
    
    # Test thread locks exist
    assert hasattr(detector, '_tracking_lock')
    assert hasattr(detector, '_db_lock')
    
    # Test _ensure_symbol_tracking works
    test_symbol = "BTCUSDc"
    detector._ensure_symbol_tracking(test_symbol)
    
    assert test_symbol in detector._atr_history
    assert test_symbol in detector._wick_ratios_history
    assert test_symbol in detector._breakout_cache
    assert test_symbol in detector._volatility_spike_cache
    
    # Test structure format
    assert "M5" in detector._atr_history[test_symbol]
    assert "M15" in detector._atr_history[test_symbol]
    assert "H1" in detector._atr_history[test_symbol]
    
    print("✅ Phase 1.3.1: Tracking structures - PASSED")
    return True

def test_normalize_rates():
    """Test _normalize_rates helper method"""
    print("\nTesting _normalize_rates() method...")
    
    import numpy as np
    import pandas as pd
    
    detector = RegimeDetector()
    
    # Test with DataFrame
    df = pd.DataFrame({
        'time': [1, 2, 3],
        'open': [100, 101, 102],
        'high': [105, 106, 107],
        'low': [95, 96, 97],
        'close': [103, 104, 105]
    })
    result = detector._normalize_rates(df)
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 3
    
    # Test with numpy array
    arr = np.array([
        [1, 100, 105, 95, 103, 1000],
        [2, 101, 106, 96, 104, 1100],
        [3, 102, 107, 97, 105, 1200]
    ])
    result = detector._normalize_rates(arr)
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 3
    
    # Test with None
    result = detector._normalize_rates(None)
    assert result is None
    
    print("✅ _normalize_rates() method - PASSED")
    return True

def test_database_initialization():
    """Test Phase 1.3.2: Database initialization"""
    print("\nTesting Phase 1.3.2: Database Initialization...")
    
    detector = RegimeDetector()
    
    # Test database path exists
    assert hasattr(detector, '_db_path')
    assert detector._db_path == "data/volatility_regime_events.sqlite"
    
    # Test database file exists
    assert os.path.exists(detector._db_path), f"Database file not found: {detector._db_path}"
    
    # Test table exists
    conn = sqlite3.connect(detector._db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='breakout_events'
    """)
    table_exists = cursor.fetchone() is not None
    assert table_exists, "breakout_events table not found"
    
    # Test table structure
    cursor.execute("PRAGMA table_info(breakout_events)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    required_columns = [
        'id', 'symbol', 'timeframe', 'breakout_type', 
        'breakout_price', 'breakout_timestamp', 'is_active'
    ]
    for col in required_columns:
        assert col in columns, f"Column {col} not found in breakout_events table"
    
    # Test indices exist
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND tbl_name='breakout_events'
    """)
    indices = [row[0] for row in cursor.fetchall()]
    
    assert 'idx_symbol_timeframe_active' in indices or any('symbol' in idx for idx in indices)
    
    conn.close()
    
    print("✅ Phase 1.3.2: Database initialization - PASSED")
    return True

def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Phase 1.1, 1.2, and 1.3.1-1.3.2 Implementation")
    print("=" * 60)
    
    results = []
    
    try:
        results.append(("Phase 1.1: Enum Extension", test_enum_extension()))
    except Exception as e:
        print(f"❌ Phase 1.1 FAILED: {e}")
        results.append(("Phase 1.1: Enum Extension", False))
    
    try:
        results.append(("Phase 1.2: Configuration", test_configuration_parameters()))
    except Exception as e:
        print(f"❌ Phase 1.2 FAILED: {e}")
        results.append(("Phase 1.2: Configuration", False))
    
    try:
        results.append(("Phase 1.3.1: Tracking Structures", test_tracking_structures()))
    except Exception as e:
        print(f"❌ Phase 1.3.1 FAILED: {e}")
        results.append(("Phase 1.3.1: Tracking Structures", False))
    
    try:
        results.append(("_normalize_rates()", test_normalize_rates()))
    except Exception as e:
        print(f"❌ _normalize_rates() FAILED: {e}")
        results.append(("_normalize_rates()", False))
    
    try:
        results.append(("Phase 1.3.2: Database", test_database_initialization()))
    except Exception as e:
        print(f"❌ Phase 1.3.2 FAILED: {e}")
        results.append(("Phase 1.3.2: Database", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    exit(main())

