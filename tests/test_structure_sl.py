"""
Phase 4.4.1 - Structure-Aware Stop Loss Tests
Tests SL anchoring to swings, FVG, equal highs/lows, and sweep levels
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.structure_sl import StructureSLCalculator, calculate_structure_sl


def test_swing_low_anchor_long():
    """Test SL anchored to swing low for long trade."""
    print("\n" + "="*60)
    print("TEST: Swing Low Anchor (Long)")
    print("="*60)
    
    calculator = StructureSLCalculator()
    
    entry = 100.0
    atr = 2.0
    
    features = {
        "swing_lows": [
            {"price": 98.5, "bars_ago": 5},
            {"price": 97.0, "bars_ago": 15}
        ],
        "swing_highs": []
    }
    
    result = calculator.calculate_structure_sl(entry, "long", features, atr)
    
    print(f"Entry: {entry}")
    print(f"ATR: {atr}")
    print(f"Swing low: 98.5 (5 bars ago)")
    print(f"Calculated SL: {result.sl_price:.2f}")
    print(f"Anchor type: {result.anchor_type}")
    print(f"Distance: {result.distance_atr:.2f}× ATR")
    print(f"Rationale: {result.rationale}")
    
    # SL should be below swing low with buffer
    expected_sl = 98.5 - (0.1 * atr)  # 98.5 - 0.2 = 98.3
    assert abs(result.sl_price - expected_sl) < 0.01, f"Expected SL ~{expected_sl}, got {result.sl_price}"
    assert result.anchor_type == "swing_low"
    assert not result.fallback_used
    
    print(f"\n[OK] Swing low anchor working correctly")
    return True


def test_fvg_edge_anchor_long():
    """Test SL anchored to FVG lower edge for long trade."""
    print("\n" + "="*60)
    print("TEST: FVG Edge Anchor (Long)")
    print("="*60)
    
    calculator = StructureSLCalculator()
    
    entry = 100.0
    atr = 2.0
    
    features = {
        "fvg_bull": True,
        "fvg_zone_lower": 99.0,
        "fvg_zone_upper": 99.5,
        "fvg_bars_ago": 3,
        "swing_lows": []  # No swings, FVG should be used
    }
    
    result = calculator.calculate_structure_sl(entry, "long", features, atr)
    
    print(f"Entry: {entry}")
    print(f"FVG lower edge: 99.0 (3 bars ago)")
    print(f"Calculated SL: {result.sl_price:.2f}")
    print(f"Anchor type: {result.anchor_type}")
    
    expected_sl = 99.0 - (0.1 * atr)  # 99.0 - 0.2 = 98.8
    assert abs(result.sl_price - expected_sl) < 0.01
    assert result.anchor_type == "fvg_edge"
    
    print(f"\n[OK] FVG edge anchor working correctly")
    return True


def test_equal_lows_anchor():
    """Test SL anchored to equal lows cluster."""
    print("\n" + "="*60)
    print("TEST: Equal Lows Anchor")
    print("="*60)
    
    calculator = StructureSLCalculator()
    
    entry = 100.0
    atr = 2.0
    
    features = {
        "eq_low_cluster": True,
        "eq_low_price": 98.0,
        "eq_low_bars_ago": 10,
        "swing_lows": []
    }
    
    result = calculator.calculate_structure_sl(entry, "long", features, atr)
    
    print(f"Entry: {entry}")
    print(f"Equal lows: 98.0")
    print(f"Calculated SL: {result.sl_price:.2f}")
    print(f"Anchor type: {result.anchor_type}")
    
    expected_sl = 98.0 - (0.1 * atr)  # 98.0 - 0.2 = 97.8
    assert abs(result.sl_price - expected_sl) < 0.01
    assert result.anchor_type == "eq_lows"
    
    print(f"\n[OK] Equal lows anchor working correctly")
    return True


def test_sweep_level_anchor():
    """Test SL anchored to sweep level after liquidity grab."""
    print("\n" + "="*60)
    print("TEST: Sweep Level Anchor")
    print("="*60)
    
    calculator = StructureSLCalculator()
    
    entry = 100.0
    atr = 2.0
    
    features = {
        "sweep_bear": True,  # Bearish sweep (liquidity grabbed below)
        "sweep_price": 98.2,
        "sweep_bars_ago": 2,
        "swing_lows": []
    }
    
    result = calculator.calculate_structure_sl(entry, "long", features, atr)
    
    print(f"Entry: {entry}")
    print(f"Sweep level: 98.2 (2 bars ago)")
    print(f"Calculated SL: {result.sl_price:.2f}")
    print(f"Anchor type: {result.anchor_type}")
    
    expected_sl = 98.2 - (0.1 * atr)  # 98.2 - 0.2 = 98.0
    assert abs(result.sl_price - expected_sl) < 0.01
    assert result.anchor_type == "sweep_level"
    
    print(f"\n[OK] Sweep level anchor working correctly")
    return True


def test_swing_high_anchor_short():
    """Test SL anchored to swing high for short trade."""
    print("\n" + "="*60)
    print("TEST: Swing High Anchor (Short)")
    print("="*60)
    
    calculator = StructureSLCalculator()
    
    entry = 100.0
    atr = 2.0
    
    features = {
        "swing_highs": [
            {"price": 101.5, "bars_ago": 5},
            {"price": 103.0, "bars_ago": 15}
        ],
        "swing_lows": []
    }
    
    result = calculator.calculate_structure_sl(entry, "short", features, atr)
    
    print(f"Entry: {entry}")
    print(f"Swing high: 101.5 (5 bars ago)")
    print(f"Calculated SL: {result.sl_price:.2f}")
    print(f"Anchor type: {result.anchor_type}")
    
    # SL should be above swing high with buffer
    expected_sl = 101.5 + (0.1 * atr)  # 101.5 + 0.2 = 101.7
    assert abs(result.sl_price - expected_sl) < 0.01
    assert result.anchor_type == "swing_high"
    
    print(f"\n[OK] Swing high anchor working correctly")
    return True


def test_min_distance_enforcement():
    """Test that minimum SL distance is enforced."""
    print("\n" + "="*60)
    print("TEST: Minimum Distance Enforcement")
    print("="*60)
    
    calculator = StructureSLCalculator(min_distance_atr=0.4)
    
    entry = 100.0
    atr = 2.0
    
    # Swing very close to entry (would violate min distance)
    features = {
        "swing_lows": [
            {"price": 99.7, "bars_ago": 2}  # Only 0.3 away, less than 0.4× ATR
        ]
    }
    
    result = calculator.calculate_structure_sl(entry, "long", features, atr)
    
    print(f"Entry: {entry}")
    print(f"Swing low: 99.7 (too close)")
    print(f"Min distance: 0.4× ATR = {0.4 * atr}")
    print(f"Calculated SL: {result.sl_price:.2f}")
    print(f"Distance: {result.distance_atr:.2f}× ATR")
    
    # Should be widened to min distance
    expected_sl = entry - (0.4 * atr)  # 100.0 - 0.8 = 99.2
    assert abs(result.sl_price - expected_sl) < 0.01
    assert result.distance_atr == 0.4
    assert "Widened" in result.rationale
    
    print(f"\n[OK] Minimum distance enforced correctly")
    return True


def test_max_distance_enforcement():
    """Test that maximum SL distance is enforced."""
    print("\n" + "="*60)
    print("TEST: Maximum Distance Enforcement")
    print("="*60)
    
    calculator = StructureSLCalculator(max_distance_atr=1.5)
    
    entry = 100.0
    atr = 2.0
    
    # Swing very far from entry (would violate max distance)
    features = {
        "swing_lows": [
            {"price": 96.0, "bars_ago": 10}  # 4.0 away, more than 1.5× ATR (3.0)
        ]
    }
    
    result = calculator.calculate_structure_sl(entry, "long", features, atr)
    
    print(f"Entry: {entry}")
    print(f"Swing low: 96.0 (too far)")
    print(f"Max distance: 1.5× ATR = {1.5 * atr}")
    print(f"Calculated SL: {result.sl_price:.2f}")
    print(f"Distance: {result.distance_atr:.2f}× ATR")
    
    # Should be narrowed to max distance
    expected_sl = entry - (1.5 * atr)  # 100.0 - 3.0 = 97.0
    assert abs(result.sl_price - expected_sl) < 0.01
    assert result.distance_atr == 1.5
    assert "Narrowed" in result.rationale
    
    print(f"\n[OK] Maximum distance enforced correctly")
    return True


def test_multiple_anchors_priority():
    """Test that nearest swing is prioritized when multiple anchors exist."""
    print("\n" + "="*60)
    print("TEST: Multiple Anchors Priority")
    print("="*60)
    
    calculator = StructureSLCalculator()
    
    entry = 100.0
    atr = 2.0
    
    # Multiple potential anchors
    features = {
        "swing_lows": [
            {"price": 98.5, "bars_ago": 5},  # Nearest
            {"price": 97.0, "bars_ago": 15}
        ],
        "eq_low_cluster": True,
        "eq_low_price": 97.5,
        "eq_low_bars_ago": 20,
        "fvg_bull": True,
        "fvg_zone_lower": 98.0,
        "fvg_bars_ago": 10
    }
    
    result = calculator.calculate_structure_sl(entry, "long", features, atr)
    
    print(f"Entry: {entry}")
    print(f"Available anchors:")
    print(f"  - Swing low: 98.5 (5 bars ago)")
    print(f"  - FVG edge: 98.0 (10 bars ago)")
    print(f"  - Equal lows: 97.5 (20 bars ago)")
    print(f"Selected anchor: {result.anchor_type} at {result.anchor_price:.2f}")
    
    # Should select swing low (highest confidence + nearest)
    assert result.anchor_type == "swing_low"
    assert result.anchor_price == 98.5
    
    print(f"\n[OK] Swing low correctly prioritized")
    return True


def test_fallback_no_structure():
    """Test fallback to ATR-based SL when no structure is available."""
    print("\n" + "="*60)
    print("TEST: Fallback (No Structure)")
    print("="*60)
    
    calculator = StructureSLCalculator()
    
    entry = 100.0
    atr = 2.0
    
    # No structure features
    features = {}
    
    result = calculator.calculate_structure_sl(entry, "long", features, atr)
    
    print(f"Entry: {entry}")
    print(f"No structure available")
    print(f"Fallback SL: {result.sl_price:.2f}")
    print(f"Distance: {result.distance_atr:.2f}× ATR")
    
    # Should fallback to 0.5× ATR
    expected_sl = entry - (0.5 * atr)  # 100.0 - 1.0 = 99.0
    assert abs(result.sl_price - expected_sl) < 0.01
    assert result.anchor_type == "fallback"
    assert result.fallback_used == True
    assert result.distance_atr == 0.5
    
    print(f"\n[OK] Fallback working correctly")
    return True


def test_convenience_function():
    """Test convenience function."""
    print("\n" + "="*60)
    print("TEST: Convenience Function")
    print("="*60)
    
    entry = 100.0
    atr = 2.0
    features = {
        "swing_lows": [{"price": 98.5, "bars_ago": 5}]
    }
    
    result = calculate_structure_sl(entry, "long", features, atr)
    
    print(f"Using convenience function: calculate_structure_sl()")
    print(f"Calculated SL: {result.sl_price:.2f}")
    
    assert result.sl_price > 0
    assert result.anchor_type == "swing_low"
    
    print(f"\n[OK] Convenience function working")
    return True


def run_all_tests():
    """Run all structure SL tests."""
    print("\n" + "="*70)
    print("PHASE 4.4.1 - STRUCTURE-AWARE STOP LOSS TESTS")
    print("="*70)
    
    tests = [
        ("Swing Low Anchor (Long)", test_swing_low_anchor_long),
        ("FVG Edge Anchor (Long)", test_fvg_edge_anchor_long),
        ("Equal Lows Anchor", test_equal_lows_anchor),
        ("Sweep Level Anchor", test_sweep_level_anchor),
        ("Swing High Anchor (Short)", test_swing_high_anchor_short),
        ("Minimum Distance Enforcement", test_min_distance_enforcement),
        ("Maximum Distance Enforcement", test_max_distance_enforcement),
        ("Multiple Anchors Priority", test_multiple_anchors_priority),
        ("Fallback (No Structure)", test_fallback_no_structure),
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
        print("[SUCCESS] All Phase 4.4.1 structure SL tests passed!")
        print("\nStructure-Aware SL is ready for integration!")
    else:
        print(f"[FAILED] {failed} tests failed")
    print("="*70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

