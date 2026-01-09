"""
Phase 4.4.3 - Momentum-Aware Trailing Stops Tests
Tests intelligent stop trailing based on momentum state
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.trailing_stops import TrailingStopCalculator, calculate_trailing_stop


def test_no_trail_before_trigger():
    """Test that SL doesn't trail before reaching trigger profit."""
    print("\n" + "="*60)
    print("TEST: No Trail Before Trigger")
    print("="*60)
    
    calculator = TrailingStopCalculator(trigger_r=1.0)
    
    entry = 100.0
    current_sl = 98.0  # 2.0 risk
    current_price = 101.5  # 0.75R profit (below 1.0R trigger)
    atr = 2.0
    
    features = {
        "macd_hist": 0.3,
        "macd_hist_prev": 0.2,
        "macd_hist_prev2": 0.1,
        "range_current": 1.0,
        "range_median_20": 1.0,
        "volume_zscore": 0.5,
        "atr_5": 1.0,
        "atr_14": 1.0
    }
    
    result = calculator.calculate_trailing_stop(
        entry, current_sl, current_price, "long", atr, features
    )
    
    print(f"Entry: {entry}, SL: {current_sl}")
    print(f"Current price: {current_price}")
    print(f"Unrealized R: {result.unrealized_r:.2f}")
    print(f"Trigger: 1.0R")
    print(f"New SL: {result.new_sl}")
    print(f"Trailed: {result.trailed}")
    print(f"Rationale: {result.rationale}")
    
    # Should not trail
    assert result.new_sl == current_sl
    assert result.trailed == False
    assert result.trail_method == "no_trail"
    
    print(f"\n[OK] No trail before trigger correctly enforced")
    return True


def test_wide_trail_strong_momentum():
    """Test wide trail with strong momentum."""
    print("\n" + "="*60)
    print("TEST: Wide Trail - Strong Momentum")
    print("="*60)
    
    calculator = TrailingStopCalculator(trigger_r=1.0, wide_trail_atr=2.0)
    
    entry = 100.0
    current_sl = 98.0  # 2.0 risk
    current_price = 104.0  # 2.0R profit (above trigger)
    atr = 2.0
    
    # Strong momentum features
    features = {
        "macd_hist": 0.5,
        "macd_hist_prev": 0.3,
        "macd_hist_prev2": 0.1,
        "range_current": 1.3,
        "range_median_20": 1.0,
        "volume_zscore": 1.5,
        "atr_5": 1.2,
        "atr_14": 1.0
    }
    
    result = calculator.calculate_trailing_stop(
        entry, current_sl, current_price, "long", atr, features
    )
    
    print(f"Entry: {entry}, SL: {current_sl}")
    print(f"Current price: {current_price}")
    print(f"Unrealized R: {result.unrealized_r:.2f}")
    print(f"Momentum: {result.momentum_state}")
    print(f"Trail method: {result.trail_method}")
    print(f"New SL: {result.new_sl:.2f}")
    print(f"Distance: {result.trail_distance_atr:.2f}× ATR")
    
    # Should use wide trail (current - 2.0× ATR)
    expected_sl = current_price - (2.0 * atr)  # 104 - 4 = 100
    assert abs(result.new_sl - expected_sl) < 0.01
    assert result.trail_method == "wide"
    assert result.trailed == True
    
    print(f"\n[OK] Wide trail applied for strong momentum")
    return True


def test_standard_trail_normal_momentum():
    """Test standard trail with normal momentum."""
    print("\n" + "="*60)
    print("TEST: Standard Trail - Normal Momentum")
    print("="*60)
    
    calculator = TrailingStopCalculator(trigger_r=1.0, standard_trail_atr=1.5)
    
    entry = 100.0
    current_sl = 98.0
    current_price = 104.0  # 2.0R profit
    atr = 2.0
    
    # Normal momentum features
    features = {
        "macd_hist": 0.05,
        "macd_hist_prev": 0.04,
        "macd_hist_prev2": 0.03,
        "range_current": 1.0,
        "range_median_20": 1.0,
        "volume_zscore": 0.3,
        "atr_5": 1.0,
        "atr_14": 1.0
    }
    
    result = calculator.calculate_trailing_stop(
        entry, current_sl, current_price, "long", atr, features
    )
    
    print(f"Momentum: {result.momentum_state}")
    print(f"Trail method: {result.trail_method}")
    print(f"New SL: {result.new_sl:.2f}")
    
    # Should use standard trail (current - 1.5× ATR)
    expected_sl = current_price - (1.5 * atr)  # 104 - 3 = 101
    assert abs(result.new_sl - expected_sl) < 0.01
    assert result.trail_method == "standard"
    assert result.trailed == True
    
    print(f"\n[OK] Standard trail applied for normal momentum")
    return True


def test_tight_trail_fading_momentum():
    """Test tight trail with fading momentum."""
    print("\n" + "="*60)
    print("TEST: Tight Trail - Fading Momentum")
    print("="*60)
    
    calculator = TrailingStopCalculator(trigger_r=1.0, tight_trail_r=0.5)
    
    entry = 100.0
    current_sl = 98.0  # 2.0 risk
    current_price = 103.0  # 1.5R profit
    atr = 2.0
    
    # Fading momentum features
    features = {
        "macd_hist": -0.2,
        "macd_hist_prev": -0.1,
        "macd_hist_prev2": 0.1,
        "range_current": 0.7,
        "range_median_20": 1.0,
        "volume_zscore": -0.5,
        "atr_5": 1.0,
        "atr_14": 1.0
    }
    
    result = calculator.calculate_trailing_stop(
        entry, current_sl, current_price, "long", atr, features
    )
    
    print(f"Momentum: {result.momentum_state}")
    print(f"Trail method: {result.trail_method}")
    print(f"New SL: {result.new_sl:.2f}")
    
    # Should use tight trail (entry + 0.5R)
    expected_sl = entry + (0.5 * (entry - current_sl))  # 100 + 1 = 101
    assert abs(result.new_sl - expected_sl) < 0.01
    assert result.trail_method == "tight"
    assert result.trailed == True
    
    print(f"\n[OK] Tight trail applied for fading momentum")
    return True


def test_never_trail_backwards():
    """Test that SL never trails backwards (worse than current)."""
    print("\n" + "="*60)
    print("TEST: Never Trail Backwards")
    print("="*60)
    
    calculator = TrailingStopCalculator(trigger_r=1.0, wide_trail_atr=2.0)
    
    entry = 100.0
    current_sl = 101.0  # Already at breakeven + 1
    current_price = 102.0  # Only 1.0 profit above current SL
    atr = 2.0
    
    # Strong momentum (would calculate SL at 102 - 4 = 98, worse than 101)
    features = {
        "macd_hist": 0.5,
        "macd_hist_prev": 0.3,
        "macd_hist_prev2": 0.1,
        "range_current": 1.3,
        "range_median_20": 1.0,
        "volume_zscore": 1.5,
        "atr_5": 1.2,
        "atr_14": 1.0
    }
    
    result = calculator.calculate_trailing_stop(
        entry, current_sl, current_price, "long", atr, features
    )
    
    print(f"Current SL: {current_sl}")
    print(f"Calculated trail would be: {current_price - (2.0 * atr):.2f}")
    print(f"Final SL: {result.new_sl}")
    print(f"Trailed: {result.trailed}")
    
    # Should keep current SL
    assert result.new_sl == current_sl
    assert result.trailed == False
    
    print(f"\n[OK] Never trails backwards")
    return True


def test_min_trail_distance():
    """Test that minimum trail distance is enforced."""
    print("\n" + "="*60)
    print("TEST: Minimum Trail Distance")
    print("="*60)
    
    calculator = TrailingStopCalculator(trigger_r=1.0, min_trail_distance=0.3)
    
    entry = 100.0
    current_sl = 100.5  # Already very tight
    current_price = 102.0
    atr = 2.0
    
    # Normal momentum
    features = {
        "macd_hist": 0.05,
        "macd_hist_prev": 0.04,
        "macd_hist_prev2": 0.03,
        "range_current": 1.0,
        "range_median_20": 1.0,
        "volume_zscore": 0.3,
        "atr_5": 1.0,
        "atr_14": 1.0
    }
    
    result = calculator.calculate_trailing_stop(
        entry, current_sl, current_price, "long", atr, features
    )
    
    print(f"Current SL: {current_sl}")
    print(f"Min trail distance: {0.3 * atr:.2f}")
    print(f"New SL: {result.new_sl}")
    print(f"Trailed: {result.trailed}")
    
    # If trail distance too small, should keep current SL
    if not result.trailed:
        assert result.new_sl == current_sl
        print(f"\n[OK] Min distance enforced, SL kept")
    else:
        # Or it's far enough to trail
        trail_dist = abs(result.new_sl - current_sl)
        assert trail_dist >= (0.3 * atr)
        print(f"\n[OK] Trail distance {trail_dist:.2f} >= min {0.3 * atr:.2f}")
    
    return True


def test_short_trade_trailing():
    """Test trailing for short trades."""
    print("\n" + "="*60)
    print("TEST: Short Trade Trailing")
    print("="*60)
    
    calculator = TrailingStopCalculator(trigger_r=1.0, standard_trail_atr=1.5)
    
    entry = 100.0
    current_sl = 102.0  # Short trade
    current_price = 96.0  # 2.0R profit (4.0 move / 2.0 risk)
    atr = 2.0
    
    # Normal momentum
    features = {
        "macd_hist": 0.05,
        "macd_hist_prev": 0.04,
        "macd_hist_prev2": 0.03,
        "range_current": 1.0,
        "range_median_20": 1.0,
        "volume_zscore": 0.3,
        "atr_5": 1.0,
        "atr_14": 1.0
    }
    
    result = calculator.calculate_trailing_stop(
        entry, current_sl, current_price, "short", atr, features
    )
    
    print(f"Entry: {entry}, SL: {current_sl} (SHORT)")
    print(f"Current price: {current_price}")
    print(f"Unrealized R: {result.unrealized_r:.2f}")
    print(f"New SL: {result.new_sl:.2f}")
    print(f"Trailed: {result.trailed}")
    
    # Should trail down (lower SL = better for short)
    expected_sl = current_price + (1.5 * atr)  # 96 + 3 = 99
    assert abs(result.new_sl - expected_sl) < 0.01
    assert result.new_sl < current_sl  # Lower is better for short
    assert result.trailed == True
    
    print(f"\n[OK] Short trade trailing working correctly")
    return True


def test_structure_anchor_ema20():
    """Test trailing with EMA20 structure anchor."""
    print("\n" + "="*60)
    print("TEST: Structure Anchor - EMA20")
    print("="*60)
    
    calculator = TrailingStopCalculator(trigger_r=1.0)
    
    entry = 100.0
    current_sl = 98.0
    current_price = 104.0
    atr = 2.0
    
    # Normal momentum features
    features = {
        "macd_hist": 0.05,
        "macd_hist_prev": 0.04,
        "macd_hist_prev2": 0.03,
        "range_current": 1.0,
        "range_median_20": 1.0,
        "volume_zscore": 0.3,
        "atr_5": 1.0,
        "atr_14": 1.0
    }
    
    # Structure with EMA20
    structure = {
        "ema20": 101.0
    }
    
    result = calculator.calculate_trailing_stop(
        entry, current_sl, current_price, "long", atr, features, structure
    )
    
    print(f"Current price: {current_price}")
    print(f"EMA20: {structure['ema20']}")
    print(f"New SL: {result.new_sl:.2f}")
    print(f"Trail method: {result.trail_method}")
    
    # Should use EMA20 as anchor
    assert result.new_sl == 101.0
    assert "ema20" in result.trail_method
    assert result.trailed == True
    
    print(f"\n[OK] EMA20 structure anchor used correctly")
    return True


def test_convenience_function():
    """Test convenience function."""
    print("\n" + "="*60)
    print("TEST: Convenience Function")
    print("="*60)
    
    features = {
        "macd_hist": 0.05,
        "macd_hist_prev": 0.04,
        "macd_hist_prev2": 0.03,
        "range_current": 1.0,
        "range_median_20": 1.0,
        "volume_zscore": 0.3,
        "atr_5": 1.0,
        "atr_14": 1.0
    }
    
    result = calculate_trailing_stop(
        entry=100.0,
        current_sl=98.0,
        current_price=104.0,
        direction="long",
        atr=2.0,
        features=features
    )
    
    print(f"Using convenience function: calculate_trailing_stop()")
    print(f"New SL: {result.new_sl:.2f}")
    print(f"Trail method: {result.trail_method}")
    
    assert result.new_sl > 0
    assert result.trail_method in ["wide", "standard", "tight", "no_trail", "wide_structure", "standard_ema20"]
    
    print(f"\n[OK] Convenience function working")
    return True


def run_all_tests():
    """Run all trailing stop tests."""
    print("\n" + "="*70)
    print("PHASE 4.4.3 - MOMENTUM-AWARE TRAILING STOPS TESTS")
    print("="*70)
    
    tests = [
        ("No Trail Before Trigger", test_no_trail_before_trigger),
        ("Wide Trail - Strong Momentum", test_wide_trail_strong_momentum),
        ("Standard Trail - Normal Momentum", test_standard_trail_normal_momentum),
        ("Tight Trail - Fading Momentum", test_tight_trail_fading_momentum),
        ("Never Trail Backwards", test_never_trail_backwards),
        ("Minimum Trail Distance", test_min_trail_distance),
        ("Short Trade Trailing", test_short_trade_trailing),
        ("Structure Anchor - EMA20", test_structure_anchor_ema20),
        ("Convenience Function", test_convenience_function)
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"\n[FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*70)
    print(f"RESULTS: {passed}/{len(tests)} tests passed")
    if failed == 0:
        print("[SUCCESS] All Phase 4.4.3 trailing stop tests passed!")
        print("\nMomentum-Aware Trailing Stops are ready for integration!")
    else:
        print(f"[FAILED] {failed} tests failed")
    print("="*70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

