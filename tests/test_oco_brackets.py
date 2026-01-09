"""
Phase 4.4.4 - OCO Brackets Tests
Tests consolidation detection and OCO bracket calculation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.oco_brackets import OCOBracketCalculator, calculate_oco_bracket


def test_consolidation_detection_valid():
    """Test detection of valid consolidation."""
    print("\n" + "="*60)
    print("TEST: Valid Consolidation Detection")
    print("="*60)
    
    calculator = OCOBracketCalculator()
    
    atr = 2.0
    features = {
        "adx_14": 18.0,  # Low ADX (consolidation)
        "bb_width": 0.025,  # Narrow BB
        "recent_highs": [102.0, 102.1, 101.9, 102.0, 102.1],  # Tight range
        "recent_lows": [99.0, 98.9, 99.1, 99.0, 98.9],
        "close": 100.5
    }
    
    consolidation = calculator._detect_consolidation(features, atr)
    
    print(f"ADX: {features['adx_14']}")
    print(f"BB width: {features['bb_width']}")
    print(f"Range: {consolidation.range_low:.2f} - {consolidation.range_high:.2f}")
    print(f"Range width: {consolidation.range_width_atr:.2f}× ATR")
    print(f"Is consolidation: {consolidation.is_consolidation}")
    print(f"Confidence: {consolidation.confidence:.0%}")
    print(f"Rationale: {consolidation.rationale}")
    
    assert consolidation.is_consolidation == True
    assert consolidation.confidence >= 0.6
    assert consolidation.range_width_atr >= 0.5  # Not too narrow
    
    print(f"\n[OK] Valid consolidation detected")
    return True


def test_consolidation_detection_trending():
    """Test that trending market is NOT detected as consolidation."""
    print("\n" + "="*60)
    print("TEST: Trending Market (Not Consolidation)")
    print("="*60)
    
    calculator = OCOBracketCalculator()
    
    atr = 2.0
    features = {
        "adx_14": 32.0,  # High ADX (trending)
        "bb_width": 0.045,  # Wide BB
        "recent_highs": [105.0, 106.0, 107.0, 108.0, 109.0],  # Expanding
        "recent_lows": [100.0, 101.0, 102.0, 103.0, 104.0],
        "close": 107.0
    }
    
    consolidation = calculator._detect_consolidation(features, atr)
    
    print(f"ADX: {features['adx_14']} (trending)")
    print(f"BB width: {features['bb_width']} (wide)")
    print(f"Is consolidation: {consolidation.is_consolidation}")
    print(f"Rationale: {consolidation.rationale}")
    
    assert consolidation.is_consolidation == False
    
    print(f"\n[OK] Trending market correctly rejected")
    return True


def test_oco_bracket_calculation_valid():
    """Test OCO bracket calculation with valid consolidation."""
    print("\n" + "="*60)
    print("TEST: Valid OCO Bracket Calculation")
    print("="*60)
    
    calculator = OCOBracketCalculator()
    
    atr = 2.0
    features = {
        "adx_14": 18.0,
        "bb_width": 0.025,
        "recent_highs": [102.0, 102.1, 101.9, 102.0, 102.1],
        "recent_lows": [99.0, 98.9, 99.1, 99.0, 98.9],
        "close": 100.5,
        "spread_atr_pct": 0.10,
        "has_pending_orders": False,
        "news_blackout": False
    }
    
    result = calculator.calculate_oco_bracket(features, atr, session="LONDON")
    
    print(f"Is valid: {result.is_valid}")
    print(f"Range: {result.range_low:.2f} - {result.range_high:.2f}")
    print(f"\nBuy side:")
    print(f"  Stop: {result.buy_stop:.2f}")
    print(f"  SL: {result.buy_sl:.2f}")
    print(f"  TP: {result.buy_tp:.2f}")
    print(f"  RR: {result.buy_rr:.2f}")
    print(f"\nSell side:")
    print(f"  Stop: {result.sell_stop:.2f}")
    print(f"  SL: {result.sell_sl:.2f}")
    print(f"  TP: {result.sell_tp:.2f}")
    print(f"  RR: {result.sell_rr:.2f}")
    print(f"\nExpiry: {result.expiry_minutes} minutes")
    
    assert result.is_valid == True
    # Buy stop should be above range high
    assert result.buy_stop > result.range_high
    # Sell stop should be below range low
    assert result.sell_stop < result.range_low
    # Buy SL should be below buy stop
    assert result.buy_sl < result.buy_stop
    # Sell SL should be above sell stop
    assert result.sell_sl > result.sell_stop
    # RR should be reasonable
    assert result.buy_rr >= 2.0
    assert result.sell_rr >= 2.0
    
    print(f"\n[OK] OCO bracket calculated correctly")
    return True


def test_oco_bracket_session_filter():
    """Test that OCO brackets are only allowed in London/NY sessions."""
    print("\n" + "="*60)
    print("TEST: Session Filter (ASIA Blocked)")
    print("="*60)
    
    calculator = OCOBracketCalculator()
    
    atr = 2.0
    features = {
        "adx_14": 18.0,
        "bb_width": 0.025,
        "recent_highs": [102.0, 102.1, 101.9],
        "recent_lows": [99.0, 98.9, 99.1],
        "close": 100.5,
        "spread_atr_pct": 0.10,
        "has_pending_orders": False,
        "news_blackout": False
    }
    
    result = calculator.calculate_oco_bracket(features, atr, session="ASIA")
    
    print(f"Session: ASIA")
    print(f"Is valid: {result.is_valid}")
    print(f"Skip reasons: {result.skip_reasons}")
    
    assert result.is_valid == False
    assert any("London/NY" in reason or "session" in reason.lower() for reason in result.skip_reasons)
    
    print(f"\n[OK] ASIA session correctly blocked")
    return True


def test_oco_bracket_spread_filter():
    """Test that high spread blocks OCO brackets."""
    print("\n" + "="*60)
    print("TEST: Spread Filter")
    print("="*60)
    
    calculator = OCOBracketCalculator(max_spread_atr_pct=0.20)
    
    atr = 2.0
    features = {
        "adx_14": 18.0,
        "bb_width": 0.025,
        "recent_highs": [102.0, 102.1, 101.9],
        "recent_lows": [99.0, 98.9, 99.1],
        "close": 100.5,
        "spread_atr_pct": 0.25,  # Too high!
        "has_pending_orders": False,
        "news_blackout": False
    }
    
    result = calculator.calculate_oco_bracket(features, atr, session="LONDON")
    
    print(f"Spread: {features['spread_atr_pct']:.1%}")
    print(f"Max allowed: 20%")
    print(f"Is valid: {result.is_valid}")
    print(f"Skip reasons: {result.skip_reasons}")
    
    assert result.is_valid == False
    assert any("spread" in reason.lower() for reason in result.skip_reasons)
    
    print(f"\n[OK] High spread correctly blocked")
    return True


def test_oco_bracket_news_blackout():
    """Test that news blackout blocks OCO brackets."""
    print("\n" + "="*60)
    print("TEST: News Blackout Filter")
    print("="*60)
    
    calculator = OCOBracketCalculator()
    
    atr = 2.0
    features = {
        "adx_14": 18.0,
        "bb_width": 0.025,
        "recent_highs": [102.0, 102.1, 101.9],
        "recent_lows": [99.0, 98.9, 99.1],
        "close": 100.5,
        "spread_atr_pct": 0.10,
        "has_pending_orders": False,
        "news_blackout": True  # News event!
    }
    
    result = calculator.calculate_oco_bracket(features, atr, session="LONDON")
    
    print(f"News blackout: True")
    print(f"Is valid: {result.is_valid}")
    print(f"Skip reasons: {result.skip_reasons}")
    
    assert result.is_valid == False
    assert any("news" in reason.lower() for reason in result.skip_reasons)
    
    print(f"\n[OK] News blackout correctly blocked")
    return True


def test_oco_bracket_pending_orders():
    """Test that existing pending orders block new OCO brackets."""
    print("\n" + "="*60)
    print("TEST: Existing Pending Orders Filter")
    print("="*60)
    
    calculator = OCOBracketCalculator()
    
    atr = 2.0
    features = {
        "adx_14": 18.0,
        "bb_width": 0.025,
        "recent_highs": [102.0, 102.1, 101.9],
        "recent_lows": [99.0, 98.9, 99.1],
        "close": 100.5,
        "spread_atr_pct": 0.10,
        "has_pending_orders": True,  # Already have orders
        "news_blackout": False
    }
    
    result = calculator.calculate_oco_bracket(features, atr, session="LONDON")
    
    print(f"Has pending orders: True")
    print(f"Is valid: {result.is_valid}")
    print(f"Skip reasons: {result.skip_reasons}")
    
    assert result.is_valid == False
    assert any("pending" in reason.lower() for reason in result.skip_reasons)
    
    print(f"\n[OK] Existing pending orders correctly blocked")
    return True


def test_oco_bracket_min_range_width():
    """Test that tiny ranges are rejected."""
    print("\n" + "="*60)
    print("TEST: Minimum Range Width")
    print("="*60)
    
    calculator = OCOBracketCalculator(min_range_width_atr=0.5)
    
    atr = 2.0
    features = {
        "adx_14": 18.0,
        "bb_width": 0.025,
        "recent_highs": [100.3, 100.35, 100.4],  # Very tight range
        "recent_lows": [100.0, 100.05, 100.1],   # Only 0.4 wide (0.2× ATR)
        "close": 100.2,
        "spread_atr_pct": 0.10,
        "has_pending_orders": False,
        "news_blackout": False
    }
    
    result = calculator.calculate_oco_bracket(features, atr, session="LONDON")
    
    print(f"Range width: ~0.2× ATR")
    print(f"Min required: 0.5× ATR")
    print(f"Is valid: {result.is_valid}")
    if not result.is_valid:
        print(f"Skip reasons: {result.skip_reasons}")
    
    assert result.is_valid == False
    
    print(f"\n[OK] Tiny range correctly rejected")
    return True


def test_oco_bracket_expiry_calculation():
    """Test expiry time calculation by session."""
    print("\n" + "="*60)
    print("TEST: Expiry Calculation")
    print("="*60)
    
    calculator = OCOBracketCalculator()
    
    # Test different sessions
    sessions = ["LONDON", "NY", "LONDON_NY"]
    expected_expiries = {
        "LONDON": 75,
        "NY": 60,
        "LONDON_NY": 90
    }
    
    for session in sessions:
        features = {"minutes_to_session_end": 999}
        expiry = calculator._calculate_expiry(session, features)
        print(f"{session}: {expiry} minutes (expected ~{expected_expiries[session]})")
        assert expiry == expected_expiries[session]
    
    # Test session end limit
    features_ending = {"minutes_to_session_end": 40}
    expiry_ending = calculator._calculate_expiry("LONDON", features_ending)
    print(f"\nSession ending in 40min: expiry = {expiry_ending} (limited)")
    assert expiry_ending == 40
    
    print(f"\n[OK] Expiry calculation working correctly")
    return True


def test_convenience_function():
    """Test convenience function."""
    print("\n" + "="*60)
    print("TEST: Convenience Function")
    print("="*60)
    
    features = {
        "adx_14": 18.0,
        "bb_width": 0.025,
        "recent_highs": [102.0, 102.1, 101.9],
        "recent_lows": [99.0, 98.9, 99.1],
        "close": 100.5,
        "spread_atr_pct": 0.10,
        "has_pending_orders": False,
        "news_blackout": False
    }
    
    result = calculate_oco_bracket(features, atr=2.0, session="LONDON")
    
    print(f"Using convenience function: calculate_oco_bracket()")
    print(f"Is valid: {result.is_valid}")
    
    if result.is_valid:
        print(f"Buy stop: {result.buy_stop:.2f}")
        print(f"Sell stop: {result.sell_stop:.2f}")
        assert result.buy_stop > 0
        assert result.sell_stop > 0
    else:
        print(f"Skip reasons: {result.skip_reasons}")
    
    print(f"\n[OK] Convenience function working")
    return True


def run_all_tests():
    """Run all OCO bracket tests."""
    print("\n" + "="*70)
    print("PHASE 4.4.4 - OCO BRACKETS TESTS")
    print("="*70)
    
    tests = [
        ("Valid Consolidation Detection", test_consolidation_detection_valid),
        ("Trending Market (Not Consolidation)", test_consolidation_detection_trending),
        ("Valid OCO Bracket Calculation", test_oco_bracket_calculation_valid),
        ("Session Filter (ASIA Blocked)", test_oco_bracket_session_filter),
        ("Spread Filter", test_oco_bracket_spread_filter),
        ("News Blackout Filter", test_oco_bracket_news_blackout),
        ("Existing Pending Orders Filter", test_oco_bracket_pending_orders),
        ("Minimum Range Width", test_oco_bracket_min_range_width),
        ("Expiry Calculation", test_oco_bracket_expiry_calculation),
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
        print("[SUCCESS] All Phase 4.4.4 OCO bracket tests passed!")
        print("\nOCO Brackets are ready for integration!")
        print("\n" + "="*70)
        print("PHASE 4.4 - EXECUTION UPGRADES COMPLETE!")
        print("="*70)
    else:
        print(f"[FAILED] {failed} tests failed")
    print("="*70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

