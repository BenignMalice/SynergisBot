"""
Phase 4.2 - Validator Session Rules Test
Tests enhanced session validation with Phase 4.2 rules
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.prompt_validator import PromptValidator


def test_asia_breakout_block():
    """Test that ASIA breakouts are blocked without exceptional conditions."""
    print("\n" + "="*60)
    print("TEST: ASIA Breakout Blocking")
    print("="*60)
    
    validator = PromptValidator()
    
    # Template config for breakout
    template_config = {
        "min_rr": 2.0,
        "max_rr": 4.0,
        "order_types": ["buy_stop", "sell_stop"],
        "validation_rules": {"min_adx": 25}
    }
    
    # ASIA breakout with insufficient volume
    response = {
        "strategy": "breakout",
        "order_type": "buy_stop",
        "entry": 100.0,
        "sl": 98.0,
        "tp": 104.0,
        "rr": 2.0,
        "confidence": {"overall": 60}
    }
    
    context = {
        "M5": {
            "session": "ASIA",
            "news_blackout": False,
            "volume_zscore": 1.0,  # Too low for ASIA breakout
            "donchian_breach": False,
            "close": 100.0,
            "atr_14": 2.0,
            "spread_atr_pct": 0.15
        }
    }
    
    result = validator.validate_response(response, "breakout", context, template_config=template_config)
    
    assert not result.is_valid, "ASIA breakout should be blocked with low volume"
    assert any("ASIA" in err and "2.0" in err for err in result.errors), \
        f"Expected ASIA volume error, got: {result.errors}"
    
    print(f"[OK] ASIA breakout blocked: {result.errors[0][:80]}")
    
    # ASIA breakout with exceptional conditions (should pass)
    context_exceptional = {
        "M5": {
            "session": "ASIA",
            "news_blackout": False,
            "volume_zscore": 2.5,  # Exceptional volume
            "donchian_breach": True,  # Strong breakout
            "close": 100.0,
            "atr_14": 2.0,
            "spread_atr_pct": 0.15,
            "adx": 28.0
        }
    }
    
    result2 = validator.validate_response(response, "breakout", context_exceptional, template_config=template_config)
    print(f"[OK] ASIA breakout with exceptional conditions: valid={result2.is_valid}")
    
    print("\n[PASS] ASIA breakout validation passed")
    return True


def test_london_range_fade_block():
    """Test that LONDON range fades are blocked with narrow ranges."""
    print("\n" + "="*60)
    print("TEST: LONDON Range Fade Blocking")
    print("="*60)
    
    validator = PromptValidator()
    
    template_config = {
        "min_rr": 1.5,
        "max_rr": 2.5,
        "order_types": ["buy_limit", "sell_limit"],
        "validation_rules": {"max_adx": 20}
    }
    
    response = {
        "strategy": "range_fade",
        "order_type": "buy_limit",
        "entry": 100.0,
        "sl": 98.0,
        "tp": 102.0,
        "rr": 2.0,
        "confidence": {"overall": 60}
    }
    
    # Narrow range in LONDON
    context = {
        "M5": {
            "session": "LONDON",
            "news_blackout": False,
            "bb_width": 0.02,  # Too narrow for LONDON
            "close": 100.0,
            "atr_14": 2.0,
            "spread_atr_pct": 0.15,
            "range_position": 0.2  # Near support
        }
    }
    
    result = validator.validate_response(response, "range_fade", context, template_config=template_config)
    
    assert not result.is_valid, "LONDON range fade should be blocked with narrow range"
    assert any("LONDON" in err and "0.03" in err for err in result.errors), \
        f"Expected LONDON bb_width error, got: {result.errors}"
    
    print(f"[OK] LONDON range fade blocked: {result.errors[0][:80]}")
    
    # Wide range in LONDON (should pass)
    context_wide = context.copy()
    context_wide["M5"] = context["M5"].copy()
    context_wide["M5"]["bb_width"] = 0.04  # Wide enough
    
    result2 = validator.validate_response(response, "range_fade", context_wide, template_config=template_config)
    print(f"[OK] LONDON range fade with wide range: valid={result2.is_valid}")
    
    print("\n[PASS] LONDON range fade validation passed")
    return True


def test_ny_trend_bos_requirement():
    """Test that NY trend trades require BOS confirmation."""
    print("\n" + "="*60)
    print("TEST: NY Trend BOS Requirement")
    print("="*60)
    
    validator = PromptValidator()
    
    template_config = {
        "min_rr": 1.8,
        "max_rr": 3.0,
        "order_types": ["buy_stop", "sell_stop"],
        "validation_rules": {"min_adx": 20}
    }
    
    response = {
        "strategy": "trend_pullback",
        "order_type": "buy_stop",
        "entry": 100.0,
        "sl": 98.0,
        "tp": 104.0,
        "rr": 2.0,
        "confidence": {"overall": 70}
    }
    
    # NY trend without BOS
    context = {
        "M5": {
            "session": "NY",
            "news_blackout": False,
            "bos_bull": False,
            "bos_bear": False,
            "close": 100.0,
            "atr_14": 2.0,
            "spread_atr_pct": 0.15,
            "range_position": 0.3,
            "adx": 25.0
        }
    }
    
    result = validator.validate_response(response, "trend_pullback", context, template_config=template_config)
    
    assert not result.is_valid, "NY trend should require BOS confirmation"
    assert any("BOS" in err for err in result.errors), \
        f"Expected BOS requirement error, got: {result.errors}"
    
    print(f"[OK] NY trend blocked without BOS: {result.errors[0][:80]}")
    
    # NY trend with BOS (should pass)
    context_bos = context.copy()
    context_bos["M5"] = context["M5"].copy()
    context_bos["M5"]["bos_bull"] = True
    
    result2 = validator.validate_response(response, "trend_pullback", context_bos, template_config=template_config)
    print(f"[OK] NY trend with BOS: valid={result2.is_valid}")
    
    print("\n[PASS] NY trend BOS validation passed")
    return True


def test_mid_range_entry_penalty():
    """Test that mid-range entries are penalized in LONDON/NY."""
    print("\n" + "="*60)
    print("TEST: Mid-Range Entry Penalty")
    print("="*60)
    
    validator = PromptValidator()
    
    template_config = {
        "min_rr": 1.8,
        "max_rr": 3.0,
        "order_types": ["buy_stop", "sell_stop"],
        "validation_rules": {"min_adx": 20}
    }
    
    response = {
        "strategy": "trend_pullback",
        "order_type": "buy_stop",
        "entry": 100.0,
        "sl": 98.0,
        "tp": 104.0,
        "rr": 2.0,
        "confidence": {"overall": 70}
    }
    
    # Mid-range entry in LONDON
    context = {
        "M5": {
            "session": "LONDON",
            "news_blackout": False,
            "bos_bull": True,
            "close": 100.0,
            "atr_14": 2.0,
            "spread_atr_pct": 0.15,
            "range_position": 0.5,  # Mid-range
            "adx": 25.0
        }
    }
    
    result = validator.validate_response(response, "trend_pullback", context, template_config=template_config)
    
    # Should have mid-range error
    has_midrange_error = any("Mid-range" in err or "0.35-0.65" in err for err in result.errors)
    assert has_midrange_error, f"Expected mid-range error, got: {result.errors}"
    
    print(f"[OK] Mid-range entry flagged: {[e for e in result.errors if 'Mid-range' in e or '0.35' in e][0][:80]}")
    
    # Edge entry (should pass)
    context_edge = context.copy()
    context_edge["M5"] = context["M5"].copy()
    context_edge["M5"]["range_position"] = 0.2  # Near support
    
    result2 = validator.validate_response(response, "trend_pullback", context_edge, template_config=template_config)
    print(f"[OK] Edge entry (0.2): valid={result2.is_valid}, errors={len(result2.errors)}")
    
    print("\n[PASS] Mid-range entry validation passed")
    return True


def test_news_blackout_block():
    """Test that news blackout blocks trades."""
    print("\n" + "="*60)
    print("TEST: News Blackout Blocking")
    print("="*60)
    
    validator = PromptValidator()
    
    template_config = {
        "min_rr": 2.0,
        "max_rr": 4.0,
        "order_types": ["buy_stop", "sell_stop"],
        "validation_rules": {"min_adx": 25}
    }
    
    response = {
        "strategy": "breakout",
        "order_type": "buy_stop",
        "entry": 100.0,
        "sl": 98.0,
        "tp": 104.0,
        "rr": 2.0,
        "confidence": {"overall": 70}
    }
    
    context = {
        "M5": {
            "session": "LONDON",
            "news_blackout": True,  # News event
            "volume_zscore": 1.5,
            "close": 100.0,
            "atr_14": 2.0,
            "spread_atr_pct": 0.15
        }
    }
    
    result = validator.validate_response(response, "breakout", context, template_config=template_config)
    
    assert not result.is_valid, "News blackout should block trades"
    assert any("news blackout" in err.lower() for err in result.errors), \
        f"Expected news blackout error, got: {result.errors}"
    
    print(f"[OK] News blackout blocked trade: {result.errors[0]}")
    
    print("\n[PASS] News blackout validation passed")
    return True


def run_all_tests():
    """Run all Phase 4.2 validator tests."""
    print("\n" + "="*70)
    print("PHASE 4.2 - VALIDATOR SESSION RULES TESTS")
    print("="*70)
    
    tests = [
        ("ASIA Breakout Blocking", test_asia_breakout_block),
        ("LONDON Range Fade Blocking", test_london_range_fade_block),
        ("NY Trend BOS Requirement", test_ny_trend_bos_requirement),
        ("Mid-Range Entry Penalty", test_mid_range_entry_penalty),
        ("News Blackout Blocking", test_news_blackout_block)
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
        print("[SUCCESS] All Phase 4.2 validator tests passed!")
    else:
        print(f"[FAILED] {failed} tests failed")
    print("="*70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

