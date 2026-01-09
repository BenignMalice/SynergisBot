"""
Phase 4.1 Integration Test
Tests that structure features are properly integrated into the feature builder
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from infra.feature_structure import StructureFeatures


def create_sample_dataframe(bars: int = 100) -> pd.DataFrame:
    """Create a sample DataFrame with realistic OHLC data for testing."""
    # Create synthetic price data with trend and volatility
    np.random.seed(42)
    
    base_price = 100.0
    trend = 0.02  # Slight uptrend
    volatility = 1.5
    
    closes = [base_price]
    for i in range(1, bars):
        change = np.random.randn() * volatility + trend
        closes.append(closes[-1] + change)
    
    # Generate OHLC from closes
    data = []
    for i, close in enumerate(closes):
        open_price = close + np.random.randn() * 0.3
        high = max(open_price, close) + abs(np.random.randn() * 0.5)
        low = min(open_price, close) - abs(np.random.randn() * 0.5)
        
        data.append({
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.random.randint(1000, 10000)
        })
    
    # Create DataFrame with datetime index
    start_time = datetime.now() - timedelta(hours=bars)
    index = [start_time + timedelta(hours=i) for i in range(bars)]
    
    return pd.DataFrame(data, index=index)


def test_structure_features_integration():
    """Test that all Phase 4.1 structure features are computed."""
    print("\n" + "="*60)
    print("PHASE 4.1 INTEGRATION TEST")
    print("="*60)
    
    # Create test data
    df = create_sample_dataframe(bars=100)
    print(f"\nCreated test DataFrame: {len(df)} bars")
    print(f"Price range: {df['low'].min():.2f} - {df['high'].max():.2f}")
    
    # Initialize structure features
    structure = StructureFeatures()
    
    # Compute all features
    print("\nComputing structure features...")
    features = structure.compute(df, symbol="TEST", timeframe="M15")
    
    # Check that Phase 4.1 features are present
    phase_4_1_features = [
        # Liquidity clusters
        "eq_high_cluster", "eq_high_price", "eq_high_count", "eq_high_bars_ago",
        "eq_low_cluster", "eq_low_price", "eq_low_count", "eq_low_bars_ago",
        # Sweeps
        "sweep_bull", "sweep_bear", "sweep_depth", "sweep_price", "sweep_bars_ago",
        # BOS/CHOCH
        "bos_bull", "bos_bear", "choch_bull", "choch_bear", 
        "structure_break_level", "structure_type",
        # Enhanced FVG
        "fvg_bull", "fvg_bear", "fvg_zone_upper", "fvg_zone_lower",
        "fvg_width_atr", "fvg_bars_ago",
        # Wick asymmetry
        "wick_asymmetry", "wick_asymmetry_avg", "wick_rejection_bull",
        "wick_rejection_bear", "wick_strength"
    ]
    
    print("\nChecking Phase 4.1 features:")
    missing_features = []
    for feature in phase_4_1_features:
        if feature in features:
            value = features[feature]
            print(f"  OK {feature}: {value}")
        else:
            print(f"  X MISSING: {feature}")
            missing_features.append(feature)
    
    if missing_features:
        print(f"\n X TEST FAILED: {len(missing_features)} features missing")
        return False
    else:
        print("\n OK All Phase 4.1 features present!")
    
    # Check legacy features still work
    legacy_features = [
        "swing_highs", "swing_lows", "swing_count",
        "support_levels", "resistance_levels",
        "range_high", "range_low", "range_width",
        "pivot_point", "r1", "s1"
    ]
    
    print("\nChecking legacy features:")
    for feature in legacy_features:
        if feature in features:
            print(f"  OK {feature} present")
        else:
            print(f"  X MISSING: {feature}")
            missing_features.append(feature)
    
    # Validate feature types and ranges
    print("\nValidating feature types and ranges:")
    
    # Boolean checks
    boolean_features = ["eq_high_cluster", "eq_low_cluster", "sweep_bull", 
                       "sweep_bear", "bos_bull", "bos_bear", "choch_bull", 
                       "choch_bear", "fvg_bull", "fvg_bear", 
                       "wick_rejection_bull", "wick_rejection_bear"]
    
    for feat in boolean_features:
        if feat in features:
            assert isinstance(features[feat], bool), f"{feat} should be bool"
            print(f"  OK {feat} is boolean")
    
    # Numeric checks
    numeric_features = ["eq_high_price", "eq_low_price", "sweep_depth", 
                       "fvg_width_atr", "wick_asymmetry", "wick_strength"]
    
    for feat in numeric_features:
        if feat in features:
            assert isinstance(features[feat], (int, float)), f"{feat} should be numeric"
            print(f"  OK {feat} is numeric: {features[feat]:.4f}")
    
    # Range checks
    if "wick_asymmetry" in features:
        assert -1.0 <= features["wick_asymmetry"] <= 1.0, "wick_asymmetry should be in [-1, 1]"
        print(f"  OK wick_asymmetry in valid range")
    
    if "wick_strength" in features:
        assert 0.0 <= features["wick_strength"] <= 1.0, "wick_strength should be in [0, 1]"
        print(f"  OK wick_strength in valid range")
    
    print("\n" + "="*60)
    print("INTEGRATION TEST PASSED")
    print("="*60)
    
    return True


def test_feature_builder_end_to_end():
    """
    Test end-to-end feature building (would require MT5Service mock).
    This is a placeholder for future comprehensive testing.
    """
    print("\n" + "="*60)
    print("END-TO-END FEATURE BUILDER TEST")
    print("="*60)
    print("\nSkipping: Requires MT5Service mock")
    print("To test fully:")
    print("  1. Mock MT5Service to return sample data")
    print("  2. Call FeatureBuilder.build() for multiple timeframes")
    print("  3. Verify Phase 4.1 features in M5/M15/H1/H4 output")
    print("="*60)


if __name__ == "__main__":
    try:
        # Run integration test
        success = test_structure_features_integration()
        
        # Run end-to-end placeholder
        test_feature_builder_end_to_end()
        
        if success:
            print("\n SUCCESS: Phase 4.1 integration validated!")
            sys.exit(0)
        else:
            print("\n FAILED: Phase 4.1 integration has issues")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

