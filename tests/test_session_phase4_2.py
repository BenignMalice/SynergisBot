"""
Phase 4.2 Session Playbooks - Unit Tests
Tests session profiles, rules engine, and enhanced detection
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, time
from infra.session_profiles import (
    get_session_profile,
    get_strategy_confidence_adjustment,
    TradingSession,
    SessionOverlap
)
from infra.session_rules import SessionRules, check_session_trade
from infra.feature_session_news import SessionNewsFeatures, SessionInfo


def test_session_profiles():
    """Test session profile loading and strategy adjustments."""
    print("\n" + "="*60)
    print("TEST: Session Profiles")
    print("="*60)
    
    # Test London profile
    london = get_session_profile("LONDON")
    assert london.name == "LONDON"
    assert "trend_pullback" in london.preferred_strategies
    assert london.min_adx == 20.0
    print(f"[OK] London profile loaded: {london.preferred_strategies}")
    
    # Test strategy confidence adjustment
    trend_adj = get_strategy_confidence_adjustment(london, "trend_pullback", "EURUSD")
    assert trend_adj > 0  # Should be positive for London trend
    print(f"[OK] London trend_pullback + EURUSD = {trend_adj:+d}")
    
    # Test Asia profile
    asia = get_session_profile("ASIA")
    assert asia.name == "ASIA"
    assert "range_fade" in asia.preferred_strategies
    breakout_adj = get_strategy_confidence_adjustment(asia, "breakout", "BTCUSD")
    assert breakout_adj < 0  # Should be negative for Asia breakout
    print(f"[OK] Asia breakout + BTCUSD = {breakout_adj:+d}")
    
    # Test overlap profile
    overlap = get_session_profile("LONDON", is_overlap=True, overlap_type="LONDON_NY")
    assert overlap.name == "LONDON_NY_OVERLAP"
    print(f"[OK] London-NY overlap profile: base_conf_adj = {overlap.base_confidence_adj:+d}")
    
    # Test transition profile
    transition = get_session_profile("NY", is_transition=True)
    assert transition.name == "TRANSITION"
    assert transition.base_confidence_adj < 0
    print(f"[OK] Transition profile: base_conf_adj = {transition.base_confidence_adj:+d}")
    
    print("\n[PASS] All profile tests passed")
    return True


def test_session_overlap_detection():
    """Test overlap detection logic."""
    print("\n" + "="*60)
    print("TEST: Overlap Detection")
    print("="*60)
    
    session_features = SessionNewsFeatures()
    
    # Test LONDON-NY overlap (13:00-16:00 UTC)
    time_14 = datetime(2025, 10, 2, 14, 30, tzinfo=timezone.utc)  # Thursday 14:30 UTC
    is_overlap, overlap_type = session_features._detect_overlap(time_14)
    assert is_overlap == True
    assert overlap_type == "LONDON_NY"
    print(f"[OK] 14:30 UTC detected as {overlap_type} overlap")
    
    # Test ASIA-LONDON overlap (08:00-09:00 UTC)
    time_08 = datetime(2025, 10, 2, 8, 15, tzinfo=timezone.utc)
    is_overlap, overlap_type = session_features._detect_overlap(time_08)
    assert is_overlap == True
    assert overlap_type == "ASIA_LONDON"
    print(f"[OK] 08:15 UTC detected as {overlap_type} overlap")
    
    # Test no overlap (pure London)
    time_10 = datetime(2025, 10, 2, 10, 0, tzinfo=timezone.utc)
    is_overlap, overlap_type = session_features._detect_overlap(time_10)
    assert is_overlap == False
    assert overlap_type is None
    print(f"[OK] 10:00 UTC detected as no overlap")
    
    print("\n[PASS] All overlap detection tests passed")
    return True


def test_session_info_generation():
    """Test complete session info generation."""
    print("\n" + "="*60)
    print("TEST: Session Info Generation")
    print("="*60)
    
    session_features = SessionNewsFeatures()
    
    # Test London session
    london_time = datetime(2025, 10, 2, 10, 30, tzinfo=timezone.utc)  # Thursday 10:30 UTC
    info = session_features.get_session_info(london_time)
    
    assert info.primary_session == "LONDON"
    assert info.is_overlap == False
    assert info.is_weekend == False
    assert info.is_market_open == True
    assert 0.0 <= info.session_strength <= 1.0
    
    print(f"[OK] London 10:30 UTC:")
    print(f"     Session: {info.primary_session}")
    print(f"     Overlap: {info.is_overlap}")
    print(f"     Minutes in: {info.minutes_into_session}")
    print(f"     Strength: {info.session_strength:.2f}")
    print(f"     Transition: {info.is_transition_period}")
    
    # Test transition period detection
    london_early = datetime(2025, 10, 2, 8, 15, tzinfo=timezone.utc)  # 15 min into session
    info_early = session_features.get_session_info(london_early)
    assert info_early.is_transition_period == True
    print(f"\n[OK] London 08:15 UTC (15min in) detected as transition: {info_early.is_transition_period}")
    
    print("\n[PASS] All session info tests passed")
    return True


def test_session_rules_filters():
    """Test session rules filtering."""
    print("\n" + "="*60)
    print("TEST: Session Rules Filtering")
    print("="*60)
    
    rules = SessionRules()
    
    # Test ASIA breakout block (should fail without high volume)
    trade_spec = {
        "strategy": "breakout",
        "confidence": 60,
        "entry": 100.0,
        "sl": 98.0,
        "tp": 104.0
    }
    
    session_info = {
        "primary_session": "ASIA",
        "is_overlap": False,
        "overlap_type": None,
        "minutes_into_session": 120,
        "session_strength": 0.7,
        "is_transition_period": False
    }
    
    features = {
        "adx_14": 25.0,
        "volume_zscore": 0.5,  # Too low for Asia breakout
        "spread_atr_pct": 0.15,
        "bb_width": 0.04,
        "donchian_breakout": False,
        "bos_bull": False,
        "bos_bear": False
    }
    
    pass_filter, skip_reasons = rules.apply_filters(trade_spec, session_info, features, "BTCUSD")
    
    assert pass_filter == False
    assert len(skip_reasons) > 0
    # Encode skip reason to avoid unicode issues
    reason_text = skip_reasons[0][:80].encode('ascii', errors='replace').decode('ascii')
    print(f"[OK] ASIA breakout blocked: {reason_text}")
    
    # Test LONDON trend with good conditions (should pass)
    trade_spec_london = {
        "strategy": "trend_pullback",
        "confidence": 70
    }
    
    session_info_london = {
        "primary_session": "LONDON",
        "is_overlap": False,
        "overlap_type": None,
        "minutes_into_session": 60,  # Past first 30min
        "session_strength": 0.95,
        "is_transition_period": False
    }
    
    features_london = {
        "adx_14": 28.0,
        "volume_zscore": 1.2,
        "spread_atr_pct": 0.12,
        "bb_width": 0.05,
        "bos_bull": True,
        "bos_bear": False,
        "range_position": 0.25  # Near support, not mid-range
    }
    
    pass_filter2, skip_reasons2 = rules.apply_filters(
        trade_spec_london, session_info_london, features_london, "EURUSD"
    )
    
    if not pass_filter2:
        print(f"[DEBUG] London filter failed: {skip_reasons2}")
    
    assert pass_filter2 == True, f"Filter failed: {skip_reasons2}"
    print(f"[OK] LONDON trend_pullback passed filters")
    
    print("\n[PASS] All filtering tests passed")
    return True


def test_confidence_adjustment():
    """Test confidence adjustment logic."""
    print("\n" + "="*60)
    print("TEST: Confidence Adjustment")
    print("="*60)
    
    rules = SessionRules()
    
    # Test LONDON trend boost
    session_info = {
        "primary_session": "LONDON",
        "is_overlap": False,
        "overlap_type": None,
        "minutes_into_session": 90,
        "session_strength": 0.95,
        "is_transition_period": False
    }
    
    features = {
        "adx_14": 30.0,
        "volume_zscore": 1.5,
        "spread_atr_pct": 0.10,
        "bos_bull": True,  # BOS confirmation
        "eq_high_cluster": False,
        "sweep_bull": False
    }
    
    base_conf = 65.0
    adjusted, reasons = rules.adjust_confidence(
        base_conf, "trend_pullback", session_info, features, "EURUSD"
    )
    
    assert adjusted > base_conf  # Should be boosted
    print(f"[OK] LONDON trend confidence: {base_conf:.0f} -> {adjusted:.0f}")
    for reason in reasons:
        print(f"     {reason}")
    
    # Test ASIA breakout penalty
    session_info_asia = {
        "primary_session": "ASIA",
        "is_overlap": False,
        "overlap_type": None,
        "minutes_into_session": 180,
        "session_strength": 0.7,
        "is_transition_period": False
    }
    
    adjusted_asia, reasons_asia = rules.adjust_confidence(
        70.0, "breakout", session_info_asia, features, "BTCUSD"
    )
    
    assert adjusted_asia < 70.0  # Should be penalized
    print(f"\n[OK] ASIA breakout confidence: 70 -> {adjusted_asia:.0f}")
    for reason in reasons_asia:
        print(f"     {reason}")
    
    print("\n[PASS] All confidence adjustment tests passed")
    return True


def run_all_tests():
    """Run all Phase 4.2 tests."""
    print("\n" + "="*70)
    print("PHASE 4.2 - SESSION PLAYBOOKS UNIT TESTS")
    print("="*70)
    
    tests = [
        ("Session Profiles", test_session_profiles),
        ("Overlap Detection", test_session_overlap_detection),
        ("Session Info Generation", test_session_info_generation),
        ("Session Rules Filtering", test_session_rules_filters),
        ("Confidence Adjustment", test_confidence_adjustment)
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
        print("[SUCCESS] All Phase 4.2 foundation tests passed!")
    else:
        print(f"[FAILED] {failed} tests failed")
    print("="*70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

