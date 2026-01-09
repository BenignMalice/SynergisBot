"""
Test suite for Loss Cut Detector
Tests the 7-category framework and 3-Strikes Rule
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from infra.loss_cut_detector import (
    LossCutDetector,
    LossCutCategory,
    LossCutUrgency
)


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print test result."""
    status = "[PASS]" if passed else "[FAIL]"
    try:
        print(f"{status} - {test_name}")
        if details:
            print(f"    {details}")
    except UnicodeEncodeError:
        # Fallback for Windows console
        print(f"{status} - {test_name}".encode('ascii', 'replace').decode('ascii'))
        if details:
            print(f"    {details}".encode('ascii', 'replace').decode('ascii'))


def test_structure_break_buy():
    """Test structure break detection for BUY position"""
    print("\n=== Test 1: Structure Break (BUY) ===")
    
    detector = LossCutDetector()
    
    # BUY position with price below EMA20
    features = {
        "ema20": 3920.0,
        "price": 3915.0,  # Below EMA20
        "rsi": 50,
        "adx": 30,
        "macd_hist": 0.001,
        "atr_14": 5.0
    }
    
    # Create bars with swing low break
    bars = pd.DataFrame({
        'time': pd.date_range(start='2025-10-06 10:00', periods=5, freq='15min'),
        'open': [3925, 3923, 3920, 3918, 3916],
        'high': [3928, 3925, 3922, 3920, 3918],
        'low': [3922, 3920, 3918, 3915, 3914],  # Breaking swing low
        'close': [3923, 3921, 3919, 3916, 3915]
    })
    
    analysis = detector.analyze_loss_cut(
        direction="buy",
        entry_price=3925.0,
        entry_time=datetime.now() - timedelta(minutes=30),
        current_price=3915.0,
        current_sl=3910.0,
        features=features,
        bars=bars,
        trade_type="intraday"
    )
    
    # Should detect structure break
    passed = (
        analysis.structure_broken and
        analysis.strikes >= 1 and
        LossCutCategory.STRUCTURE in [s.category for s in analysis.signals]
    )
    
    print_result(
        "Structure Break Detection (BUY)",
        passed,
        f"Strikes: {analysis.strikes}, Urgency: {analysis.urgency.value}, Action: {analysis.action}"
    )
    
    return passed


def test_momentum_failure():
    """Test momentum failure detection"""
    print("\n=== Test 2: Momentum Failure ===")
    
    detector = LossCutDetector()
    
    # Position with weak ADX and negative MACD
    features = {
        "ema20": 3920.0,
        "price": 3918.0,
        "rsi": 50,
        "adx": 15,  # Below 20 = weak
        "macd_hist": -0.005,  # Negative for BUY
        "atr_14": 5.0
    }
    
    # Create bars with RSI failure
    bars = pd.DataFrame({
        'time': pd.date_range(start='2025-10-06 10:00', periods=5, freq='15min'),
        'open': [3925, 3923, 3920, 3918, 3916],
        'high': [3928, 3925, 3922, 3920, 3918],
        'low': [3922, 3920, 3918, 3915, 3914],
        'close': [3923, 3921, 3919, 3916, 3915],
        'rsi': [65, 60, 55, 50, 45]  # Dropping from peak
    })
    
    analysis = detector.analyze_loss_cut(
        direction="buy",
        entry_price=3925.0,
        entry_time=datetime.now() - timedelta(minutes=30),
        current_price=3918.0,
        current_sl=3910.0,
        features=features,
        bars=bars,
        trade_type="intraday"
    )
    
    # Should detect momentum failure
    passed = (
        analysis.momentum_failed and
        analysis.strikes >= 1 and
        LossCutCategory.MOMENTUM in [s.category for s in analysis.signals]
    )
    
    print_result(
        "Momentum Failure Detection",
        passed,
        f"Strikes: {analysis.strikes}, Urgency: {analysis.urgency.value}, ADX: {features['adx']}"
    )
    
    return passed


def test_volatility_spike():
    """Test volatility spike detection"""
    print("\n=== Test 3: Volatility Spike ===")
    
    detector = LossCutDetector(atr_spike_multiplier=2.0)
    
    features = {
        "ema20": 3920.0,
        "price": 3915.0,
        "rsi": 50,
        "adx": 30,
        "macd_hist": 0.001,
        "atr_14": 5.0
    }
    
    # Create bars with large bearish candle (2.5x ATR = 12.5 points)
    bars = pd.DataFrame({
        'time': pd.date_range(start='2025-10-06 10:00', periods=5, freq='15min'),
        'open': [3925, 3923, 3920, 3930, 3916],  # Last candle opens high
        'high': [3928, 3925, 3922, 3932, 3918],
        'low': [3922, 3920, 3918, 3910, 3902],  # Last candle drops to 3902 (16-point range)
        'close': [3923, 3921, 3919, 3916, 3915]
    })
    
    analysis = detector.analyze_loss_cut(
        direction="buy",
        entry_price=3925.0,
        entry_time=datetime.now() - timedelta(minutes=30),
        current_price=3915.0,
        current_sl=3910.0,
        features=features,
        bars=bars,
        trade_type="intraday"
    )
    
    # Should detect volatility spike
    passed = (
        analysis.volatility_spike and
        analysis.strikes >= 1 and
        LossCutCategory.VOLATILITY in [s.category for s in analysis.signals]
    )
    
    print_result(
        "Volatility Spike Detection",
        passed,
        f"Strikes: {analysis.strikes}, Last candle range: {bars.iloc[-1]['high'] - bars.iloc[-1]['low']:.2f} (ATR: {features['atr_14']})"
    )
    
    return passed


def test_confluence_breakdown():
    """Test confluence breakdown detection"""
    print("\n=== Test 4: Confluence Breakdown ===")
    
    detector = LossCutDetector(
        min_confluence_indicators=3,
        confluence_break_threshold=0.67
    )
    
    # All indicators against BUY position
    features = {
        "ema20": 3920.0,
        "price": 3915.0,  # Below EMA20 ❌
        "rsi": 42,  # Below 45 ❌
        "adx": 20,  # Weak ❌
        "macd_hist": -0.005,  # Negative ❌
        "atr_14": 5.0
    }
    
    analysis = detector.analyze_loss_cut(
        direction="buy",
        entry_price=3925.0,
        entry_time=datetime.now() - timedelta(minutes=30),
        current_price=3915.0,
        current_sl=3910.0,
        features=features,
        trade_type="intraday"
    )
    
    # Should detect confluence breakdown (4/4 indicators broken)
    passed = (
        analysis.confluence_broken and
        analysis.strikes >= 1 and
        LossCutCategory.CONFLUENCE in [s.category for s in analysis.signals]
    )
    
    print_result(
        "Confluence Breakdown Detection",
        passed,
        f"Strikes: {analysis.strikes}, Confidence: {analysis.confidence:.2f}"
    )
    
    return passed


def test_time_expiration():
    """Test time-based invalidation"""
    print("\n=== Test 5: Time Expiration ===")
    
    detector = LossCutDetector(intraday_timeout=240)  # 4 hours
    
    features = {
        "ema20": 3920.0,
        "price": 3918.0,
        "rsi": 50,
        "adx": 30,
        "macd_hist": 0.001,
        "atr_14": 5.0
    }
    
    # Position open for 5 hours (exceeds 4-hour timeout)
    analysis = detector.analyze_loss_cut(
        direction="buy",
        entry_price=3925.0,
        entry_time=datetime.now() - timedelta(hours=5),
        current_price=3918.0,
        current_sl=3910.0,
        features=features,
        trade_type="intraday"
    )
    
    # Should detect time expiration
    passed = (
        analysis.time_expired and
        analysis.strikes >= 1 and
        LossCutCategory.TIME in [s.category for s in analysis.signals]
    )
    
    print_result(
        "Time Expiration Detection",
        passed,
        f"Strikes: {analysis.strikes}, Time in trade: {analysis.time_in_trade_minutes} min"
    )
    
    return passed


def test_risk_limits():
    """Test risk limit breaches"""
    print("\n=== Test 6: Risk Limits ===")
    
    detector = LossCutDetector(
        max_loss_r=-1.5,
        max_daily_loss_pct=0.05
    )
    
    features = {
        "ema20": 3920.0,
        "price": 3905.0,  # Deep loss
        "rsi": 50,
        "adx": 30,
        "macd_hist": 0.001,
        "atr_14": 5.0
    }
    
    # Position with -2.0R loss (exceeds -1.5R limit)
    # Entry: 3925, SL: 3915, Current: 3905
    # Risk: 10, Loss: 20, R: -2.0
    analysis = detector.analyze_loss_cut(
        direction="buy",
        entry_price=3925.0,
        entry_time=datetime.now() - timedelta(minutes=30),
        current_price=3905.0,
        current_sl=3915.0,
        features=features,
        trade_type="intraday",
        daily_pnl_pct=-0.06  # -6% daily loss (exceeds 5% limit)
    )
    
    # Should detect risk limit breach
    passed = (
        analysis.risk_exceeded and
        analysis.strikes >= 1 and
        LossCutCategory.RISK in [s.category for s in analysis.signals] and
        analysis.urgency == LossCutUrgency.CRITICAL
    )
    
    print_result(
        "Risk Limit Breach Detection",
        passed,
        f"Strikes: {analysis.strikes}, Unrealized R: {analysis.unrealized_r:.2f}, Urgency: {analysis.urgency.value}"
    )
    
    return passed


def test_three_strikes_rule():
    """Test 3-Strikes Rule (CRITICAL urgency)"""
    print("\n=== Test 7: 3-Strikes Rule (CRITICAL) ===")
    
    detector = LossCutDetector()
    
    # Multiple signals: structure + momentum + volatility
    features = {
        "ema20": 3920.0,
        "price": 3912.0,  # Below EMA20 (structure) ✅
        "rsi": 50,
        "adx": 15,  # Weak (momentum) ✅
        "macd_hist": -0.005,  # Negative (momentum) ✅
        "atr_14": 5.0
    }
    
    # Large bearish candle (volatility) ✅
    bars = pd.DataFrame({
        'time': pd.date_range(start='2025-10-06 10:00', periods=5, freq='15min'),
        'open': [3925, 3923, 3920, 3930, 3916],
        'high': [3928, 3925, 3922, 3932, 3918],
        'low': [3922, 3920, 3918, 3910, 3909],  # 22-point range
        'close': [3923, 3921, 3919, 3912, 3912]
    })
    
    analysis = detector.analyze_loss_cut(
        direction="buy",
        entry_price=3925.0,
        entry_time=datetime.now() - timedelta(minutes=30),
        current_price=3912.0,
        current_sl=3910.0,
        features=features,
        bars=bars,
        trade_type="intraday"
    )
    
    # Should trigger CRITICAL urgency (3+ strikes)
    passed = (
        analysis.strikes >= 3 and
        analysis.urgency == LossCutUrgency.CRITICAL and
        analysis.action in ["cut_full", "cut_50"]
    )
    
    print_result(
        "3-Strikes Rule (CRITICAL)",
        passed,
        f"Strikes: {analysis.strikes}/7, Urgency: {analysis.urgency.value}, Action: {analysis.action}"
    )
    
    return passed


def test_sell_position():
    """Test loss cut detection for SELL position"""
    print("\n=== Test 8: SELL Position Loss Cut ===")
    
    detector = LossCutDetector()
    
    # SELL position with price above EMA20
    features = {
        "ema20": 1.0850,
        "price": 1.0865,  # Above EMA20 (structure break for SELL)
        "rsi": 60,
        "adx": 18,  # Weak
        "macd_hist": 0.0005,  # Positive (against SELL)
        "atr_14": 0.0010
    }
    
    analysis = detector.analyze_loss_cut(
        direction="sell",
        entry_price=1.0850,
        entry_time=datetime.now() - timedelta(minutes=30),
        current_price=1.0865,
        current_sl=1.0870,
        features=features,
        trade_type="intraday"
    )
    
    # Should detect structure + momentum breaks
    passed = (
        analysis.structure_broken and
        analysis.momentum_failed and
        analysis.strikes >= 2
    )
    
    print_result(
        "SELL Position Loss Cut",
        passed,
        f"Strikes: {analysis.strikes}, Unrealized R: {analysis.unrealized_r:.2f}"
    )
    
    return passed


def test_no_loss_cut_needed():
    """Test that profitable positions don't trigger loss cuts"""
    print("\n=== Test 9: No Loss Cut (Profitable Position) ===")
    
    detector = LossCutDetector()
    
    features = {
        "ema20": 3920.0,
        "price": 3935.0,  # In profit
        "rsi": 65,
        "adx": 30,
        "macd_hist": 0.005,
        "atr_14": 5.0
    }
    
    # Position in profit
    analysis = detector.analyze_loss_cut(
        direction="buy",
        entry_price=3925.0,
        entry_time=datetime.now() - timedelta(minutes=30),
        current_price=3935.0,
        current_sl=3920.0,
        features=features,
        trade_type="intraday"
    )
    
    # Should NOT trigger any loss cuts
    passed = (
        analysis.urgency == LossCutUrgency.NONE and
        analysis.strikes == 0 and
        analysis.action == "hold" and
        analysis.unrealized_r > 0
    )
    
    print_result(
        "No Loss Cut (Profitable)",
        passed,
        f"Unrealized R: +{analysis.unrealized_r:.2f}, Action: {analysis.action}"
    )
    
    return passed


def test_confidence_scoring():
    """Test confidence score calculation"""
    print("\n=== Test 10: Confidence Scoring ===")
    
    detector = LossCutDetector()
    
    # High-severity signals
    features = {
        "ema20": 3920.0,
        "price": 3910.0,  # Well below EMA20
        "rsi": 35,  # Very weak
        "adx": 12,  # Very weak
        "macd_hist": -0.008,  # Strongly negative
        "atr_14": 5.0
    }
    
    # Deep loss
    analysis = detector.analyze_loss_cut(
        direction="buy",
        entry_price=3925.0,
        entry_time=datetime.now() - timedelta(minutes=30),
        current_price=3910.0,
        current_sl=3915.0,
        features=features,
        trade_type="intraday"
    )
    
    # Should have high confidence (multiple severe signals + deep loss)
    passed = (
        analysis.confidence >= 0.7 and
        analysis.strikes >= 2
    )
    
    print_result(
        "Confidence Scoring",
        passed,
        f"Confidence: {analysis.confidence:.2f}, Strikes: {analysis.strikes}, Loss: {analysis.unrealized_r:.2f}R"
    )
    
    return passed


def main():
    """Run all tests"""
    print("=" * 60)
    print("LOSS CUT DETECTOR TEST SUITE")
    print("=" * 60)
    
    tests = [
        test_structure_break_buy,
        test_momentum_failure,
        test_volatility_spike,
        test_confluence_breakdown,
        test_time_expiration,
        test_risk_limits,
        test_three_strikes_rule,
        test_sell_position,
        test_no_loss_cut_needed,
        test_confidence_scoring
    ]
    
    results = []
    for test in tests:
        try:
            passed = test()
            results.append(passed)
        except Exception as e:
            print_result(test.__name__, False, f"Exception: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed_count = sum(results)
    total_count = len(results)
    print(f"Passed: {passed_count}/{total_count}")
    print(f"Failed: {total_count - passed_count}/{total_count}")
    
    if passed_count == total_count:
        print("\nALL TESTS PASSED!")
        return 0
    else:
        print(f"\n{total_count - passed_count} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
