"""
Phase 4.4.2 - Adaptive TP and Momentum Detection Tests
Tests momentum state detection and adaptive TP calculation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.momentum_detector import MomentumDetector, MomentumState, detect_momentum
from infra.adaptive_tp import AdaptiveTPCalculator, calculate_adaptive_tp


def test_strong_momentum_detection():
    """Test detection of strong momentum."""
    print("\n" + "="*60)
    print("TEST: Strong Momentum Detection")
    print("="*60)
    
    detector = MomentumDetector()
    
    # Strong momentum features
    features = {
        "macd_hist": 0.5,
        "macd_hist_prev": 0.3,
        "macd_hist_prev2": 0.1,  # Slope = (0.5 - 0.1) / 2 = 0.2 (strong)
        "range_current": 1.3,
        "range_median_20": 1.0,   # Ratio = 1.3 (expanding)
        "volume_zscore": 1.5,      # High volume
        "atr_5": 1.2,
        "atr_14": 1.0              # Ratio = 1.2 (expanding)
    }
    
    result = detector.detect_momentum(features)
    
    print(f"MACD slope: {(features['macd_hist'] - features['macd_hist_prev2']) / 2:.2f}")
    print(f"Range ratio: {features['range_current'] / features['range_median_20']:.2f}")
    print(f"Volume z: {features['volume_zscore']:.1f}")
    print(f"ATR ratio: {features['atr_5'] / features['atr_14']:.2f}")
    print(f"\nDetected state: {result.state.value}")
    print(f"Score: {result.score} (macd={result.macd_score}, range={result.range_score}, vol={result.volume_score}, atr={result.atr_score})")
    print(f"Rationale: {result.rationale}")
    
    assert result.state == MomentumState.STRONG
    assert result.score >= 2
    
    print(f"\n[OK] Strong momentum detected correctly")
    return True


def test_fading_momentum_detection():
    """Test detection of fading momentum."""
    print("\n" + "="*60)
    print("TEST: Fading Momentum Detection")
    print("="*60)
    
    detector = MomentumDetector()
    
    # Fading momentum features
    features = {
        "macd_hist": -0.2,
        "macd_hist_prev": -0.1,
        "macd_hist_prev2": 0.1,   # Slope = (-0.2 - 0.1) / 2 = -0.15 (weak)
        "range_current": 0.7,
        "range_median_20": 1.0,   # Ratio = 0.7 (contracting)
        "volume_zscore": -0.5,     # Low volume
        "atr_5": 1.0,
        "atr_14": 1.0              # Ratio = 1.0 (normal)
    }
    
    result = detector.detect_momentum(features)
    
    print(f"MACD slope: {(features['macd_hist'] - features['macd_hist_prev2']) / 2:.2f}")
    print(f"Range ratio: {features['range_current'] / features['range_median_20']:.2f}")
    print(f"Volume z: {features['volume_zscore']:.1f}")
    print(f"\nDetected state: {result.state.value}")
    print(f"Score: {result.score}")
    print(f"Rationale: {result.rationale}")
    
    assert result.state == MomentumState.FADING
    assert result.score <= -2
    
    print(f"\n[OK] Fading momentum detected correctly")
    return True


def test_normal_momentum_detection():
    """Test detection of normal momentum."""
    print("\n" + "="*60)
    print("TEST: Normal Momentum Detection")
    print("="*60)
    
    detector = MomentumDetector()
    
    # Normal momentum features
    features = {
        "macd_hist": 0.05,
        "macd_hist_prev": 0.04,
        "macd_hist_prev2": 0.03,  # Slope = 0.01 (neutral)
        "range_current": 1.0,
        "range_median_20": 1.0,   # Ratio = 1.0 (normal)
        "volume_zscore": 0.3,      # Normal volume
        "atr_5": 1.0,
        "atr_14": 1.0              # Ratio = 1.0 (normal)
    }
    
    result = detector.detect_momentum(features)
    
    print(f"All indicators neutral")
    print(f"Detected state: {result.state.value}")
    print(f"Score: {result.score}")
    
    assert result.state == MomentumState.NORMAL
    assert -1 <= result.score <= 1
    
    print(f"\n[OK] Normal momentum detected correctly")
    return True


def test_adaptive_tp_strong_momentum():
    """Test TP extension with strong momentum."""
    print("\n" + "="*60)
    print("TEST: Adaptive TP - Strong Momentum")
    print("="*60)
    
    calculator = AdaptiveTPCalculator()
    
    entry = 100.0
    sl = 98.0  # 2.0 risk
    base_rr = 2.0
    
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
    
    result = calculator.calculate_adaptive_tp(entry, sl, base_rr, "long", features)
    
    print(f"Entry: {entry}, SL: {sl}, Risk: {entry - sl}")
    print(f"Base RR: {base_rr}R")
    print(f"Base TP: {result.base_tp:.2f}")
    print(f"\nMomentum: {result.momentum_state}")
    print(f"Extension factor: {result.extension_factor:.2f}")
    print(f"Adaptive RR: {result.adaptive_rr:.2f}R")
    print(f"Adaptive TP: {result.adaptive_tp:.2f}")
    rationale_text = result.rationale.encode('ascii', errors='replace').decode('ascii')
    print(f"Rationale: {rationale_text}")
    
    # Should extend TP
    assert result.adaptive_tp > result.base_tp
    assert result.adaptive_rr == base_rr * 1.5  # Extended by 50%
    assert result.momentum_state == "strong"
    
    print(f"\n[OK] TP extended correctly for strong momentum")
    return True


def test_adaptive_tp_fading_momentum():
    """Test TP reduction with fading momentum."""
    print("\n" + "="*60)
    print("TEST: Adaptive TP - Fading Momentum")
    print("="*60)
    
    calculator = AdaptiveTPCalculator()
    
    entry = 100.0
    sl = 98.0
    base_rr = 2.0
    
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
    
    result = calculator.calculate_adaptive_tp(entry, sl, base_rr, "long", features)
    
    print(f"Base TP: {result.base_tp:.2f} ({base_rr}R)")
    print(f"Momentum: {result.momentum_state}")
    print(f"Reduction factor: {result.extension_factor:.2f}")
    print(f"Adaptive TP: {result.adaptive_tp:.2f} ({result.adaptive_rr:.2f}R)")
    
    # Should reduce TP
    assert result.adaptive_tp < result.base_tp
    assert result.adaptive_rr == base_rr * 0.7  # Reduced by 30%
    assert result.momentum_state == "fading"
    
    print(f"\n[OK] TP reduced correctly for fading momentum")
    return True


def test_adaptive_tp_min_rr_clamp():
    """Test that min RR is enforced."""
    print("\n" + "="*60)
    print("TEST: Adaptive TP - Min RR Clamp")
    print("="*60)
    
    calculator = AdaptiveTPCalculator(min_rr=1.2)
    
    entry = 100.0
    sl = 98.0
    base_rr = 1.5
    
    # Very fading momentum (would reduce below min)
    features = {
        "macd_hist": -0.3,
        "macd_hist_prev": -0.1,
        "macd_hist_prev2": 0.2,
        "range_current": 0.6,
        "range_median_20": 1.0,
        "volume_zscore": -1.0,
        "atr_5": 1.0,
        "atr_14": 1.0
    }
    
    result = calculator.calculate_adaptive_tp(entry, sl, base_rr, "long", features)
    
    print(f"Base RR: {base_rr}R")
    print(f"Would be: {base_rr * 0.7:.2f}R (with reduction)")
    print(f"Clamped to min: {result.adaptive_rr:.2f}R")
    print(f"Clamped: {result.clamped}")
    
    # Should be clamped to min 1.2R
    assert result.adaptive_rr == 1.2
    assert result.clamped == True
    
    print(f"\n[OK] Min RR enforced correctly")
    return True


def test_adaptive_tp_max_rr_clamp():
    """Test that max RR is enforced."""
    print("\n" + "="*60)
    print("TEST: Adaptive TP - Max RR Clamp")
    print("="*60)
    
    calculator = AdaptiveTPCalculator(max_rr=4.0)
    
    entry = 100.0
    sl = 98.0
    base_rr = 3.0
    
    # Very strong momentum (would extend beyond max)
    features = {
        "macd_hist": 0.6,
        "macd_hist_prev": 0.3,
        "macd_hist_prev2": 0.0,
        "range_current": 1.5,
        "range_median_20": 1.0,
        "volume_zscore": 2.0,
        "atr_5": 1.3,
        "atr_14": 1.0
    }
    
    result = calculator.calculate_adaptive_tp(entry, sl, base_rr, "long", features)
    
    print(f"Base RR: {base_rr}R")
    print(f"Would be: {base_rr * 1.5:.2f}R (with extension)")
    print(f"Clamped to max: {result.adaptive_rr:.2f}R")
    print(f"Clamped: {result.clamped}")
    
    # Should be clamped to max 4.0R
    assert result.adaptive_rr == 4.0
    assert result.clamped == True
    
    print(f"\n[OK] Max RR enforced correctly")
    return True


def test_adaptive_tp_short_direction():
    """Test adaptive TP for short trades."""
    print("\n" + "="*60)
    print("TEST: Adaptive TP - Short Direction")
    print("="*60)
    
    calculator = AdaptiveTPCalculator()
    
    entry = 100.0
    sl = 102.0  # Short trade
    base_rr = 2.0
    
    # Strong momentum
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
    
    result = calculator.calculate_adaptive_tp(entry, sl, base_rr, "short", features)
    
    print(f"Entry: {entry}, SL: {sl} (SHORT)")
    print(f"Risk: {sl - entry}")
    print(f"Base TP: {result.base_tp:.2f}")
    print(f"Adaptive TP: {result.adaptive_tp:.2f}")
    
    # TP should be below entry for short
    assert result.adaptive_tp < entry
    # Should be extended
    assert result.adaptive_tp < result.base_tp  # Lower TP = better for short
    
    print(f"\n[OK] Short trade adaptive TP working correctly")
    return True


def test_convenience_function():
    """Test convenience function."""
    print("\n" + "="*60)
    print("TEST: Convenience Functions")
    print("="*60)
    
    # Test momentum detector convenience function
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
    
    momentum = detect_momentum(features)
    print(f"Momentum: {momentum.state.value}")
    assert momentum.state in [MomentumState.STRONG, MomentumState.NORMAL, MomentumState.FADING]
    
    # Test adaptive TP convenience function
    result = calculate_adaptive_tp(100.0, 98.0, 2.0, "long", features)
    print(f"Adaptive TP: {result.adaptive_tp:.2f}")
    assert result.adaptive_tp > 0
    
    print(f"\n[OK] Convenience functions working")
    return True


def run_all_tests():
    """Run all adaptive TP tests."""
    print("\n" + "="*70)
    print("PHASE 4.4.2 - ADAPTIVE TP & MOMENTUM DETECTION TESTS")
    print("="*70)
    
    tests = [
        ("Strong Momentum Detection", test_strong_momentum_detection),
        ("Fading Momentum Detection", test_fading_momentum_detection),
        ("Normal Momentum Detection", test_normal_momentum_detection),
        ("Adaptive TP - Strong Momentum", test_adaptive_tp_strong_momentum),
        ("Adaptive TP - Fading Momentum", test_adaptive_tp_fading_momentum),
        ("Adaptive TP - Min RR Clamp", test_adaptive_tp_min_rr_clamp),
        ("Adaptive TP - Max RR Clamp", test_adaptive_tp_max_rr_clamp),
        ("Adaptive TP - Short Direction", test_adaptive_tp_short_direction),
        ("Convenience Functions", test_convenience_function)
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
        print("[SUCCESS] All Phase 4.4.2 adaptive TP tests passed!")
        print("\nAdaptive TP is ready for integration!")
    else:
        print(f"[FAILED] {failed} tests failed")
    print("="*70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

