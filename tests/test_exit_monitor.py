"""
Test Suite for Exit Monitor - Profit Protection System

Tests the ExitSignalDetector and ExitMonitor functionality including:
- Signal detection across all phases (Early Warning, Exhaustion, Breakdown)
- Trailing stop calculations
- Alert formatting
- Action determination
- Confidence scoring
"""

import sys
import logging
from datetime import datetime
from pathlib import Path
import pandas as pd
import numpy as np

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from infra.exit_signal_detector import (
    ExitSignalDetector,
    ExitPhase,
    ExitUrgency,
    detect_exit_signals
)


def print_section(title: str):
    """Print a section header."""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


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


def test_phase1_early_warning():
    """Test Phase 1: Early Warning signals."""
    print_section("TEST 1: Phase 1 - Early Warning Signals")
    
    detector = ExitSignalDetector()
    
    # Scenario: ADX rollover + volume divergence
    features = {
        "adx": 42.5,
        "adx_prev": 45.1,
        "macd_hist": 0.5,
        "macd_hist_prev": 0.6,
        "rsi": 68.0,
        "atr_14": 8.0,
        "atr_14_prev": 8.2,
        "ema20": 3850.0,
        "bb_upper": 3890.0,
        "bb_lower": 3810.0,
        "bb_mid": 3850.0,
    }
    
    # Create bars with volume divergence
    bars_data = {
        'time': pd.date_range('2025-01-01', periods=10, freq='15min'),
        'open': [3850 + i*2 for i in range(10)],
        'high': [3855 + i*2 for i in range(10)],
        'low': [3845 + i*2 for i in range(10)],
        'close': [3852 + i*2 for i in range(10)],  # Rising prices
        'tick_volume': [1000 - i*50 for i in range(10)],  # Declining volume
        'rsi': [65 - i*0.5 for i in range(10)]  # RSI divergence
    }
    bars = pd.DataFrame(bars_data)
    
    analysis = detector.analyze_exit_signals(
        direction="buy",
        entry_price=3850.0,
        current_price=3870.0,
        features=features,
        bars=bars
    )
    
    # Assertions
    test_passed = True
    details = []
    
    if analysis.phase != ExitPhase.EARLY_WARNING:
        test_passed = False
        details.append(f"Expected EARLY_WARNING, got {analysis.phase}")
    
    if analysis.urgency not in [ExitUrgency.LOW, ExitUrgency.MEDIUM]:
        test_passed = False
        details.append(f"Expected LOW/MEDIUM urgency, got {analysis.urgency}")
    
    if analysis.action not in ["trail_normal", "trail_moderate"]:
        test_passed = False
        details.append(f"Expected trail_normal/trail_moderate, got {analysis.action}")
    
    if len(analysis.signals) < 2:
        test_passed = False
        details.append(f"Expected >= 2 signals, got {len(analysis.signals)}")
    
    print_result(
        "Phase 1 Detection",
        test_passed,
        " | ".join(details) if details else f"Phase={analysis.phase}, Urgency={analysis.urgency}, Signals={len(analysis.signals)}"
    )
    
    # Print signal details
    print(f"\n  📊 Analysis Results:")
    print(f"     Phase: {analysis.phase.value}")
    print(f"     Urgency: {analysis.urgency.value}")
    print(f"     Action: {analysis.action}")
    print(f"     Confidence: {analysis.confidence*100:.1f}%")
    print(f"     Signals Detected: {len(analysis.signals)}")
    for sig in analysis.signals:
        print(f"       • {sig.indicator}: {sig.message}")
    print(f"     Rationale: {analysis.rationale}")
    
    return test_passed


def test_phase2_exhaustion():
    """Test Phase 2: Exhaustion signals."""
    print_section("TEST 2: Phase 2 - Exhaustion Signals")
    
    detector = ExitSignalDetector()
    
    # Scenario: ATR compression + BB re-entry + VWAP flattening
    features = {
        "adx": 38.0,
        "adx_prev": 42.0,
        "macd_hist": 0.3,
        "macd_hist_prev": 0.5,
        "rsi": 72.0,
        "atr_14": 6.0,  # Dropped from 8.0 (25% drop)
        "atr_14_prev": 8.0,
        "ema20": 3860.0,
        "bb_upper": 3890.0,
        "bb_lower": 3830.0,
        "bb_mid": 3860.0,
        "vwap": 3865.0,
        "vwap_prev": 3866.0,  # Flattening
    }
    
    # Create bars with BB re-entry
    bars_data = {
        'time': pd.date_range('2025-01-01', periods=10, freq='15min'),
        'open': [3880 + i for i in range(10)],
        'high': [3895 + i for i in range(10)],
        'low': [3875 + i for i in range(10)],
        'close': [3885, 3892, 3895, 3893, 3890, 3888, 3885, 3883, 3880, 3878],  # Peak and decline
        'tick_volume': [1000 - i*40 for i in range(10)],
        'rsi': [70, 72, 74, 73, 71, 69, 67, 65, 63, 61]
    }
    bars = pd.DataFrame(bars_data)
    
    analysis = detector.analyze_exit_signals(
        direction="buy",
        entry_price=3850.0,
        current_price=3878.0,
        features=features,
        bars=bars
    )
    
    # Assertions
    test_passed = True
    details = []
    
    if analysis.phase != ExitPhase.EXHAUSTION:
        test_passed = False
        details.append(f"Expected EXHAUSTION, got {analysis.phase}")
    
    if analysis.urgency not in [ExitUrgency.MEDIUM, ExitUrgency.HIGH]:
        test_passed = False
        details.append(f"Expected MEDIUM/HIGH urgency, got {analysis.urgency}")
    
    if analysis.action not in ["trail_moderate", "trail_tight"]:
        test_passed = False
        details.append(f"Expected trail_moderate/trail_tight, got {analysis.action}")
    
    if len(analysis.signals) < 2:
        test_passed = False
        details.append(f"Expected >= 2 signals, got {len(analysis.signals)}")
    
    print_result(
        "Phase 2 Detection",
        test_passed,
        " | ".join(details) if details else f"Phase={analysis.phase}, Urgency={analysis.urgency}, Signals={len(analysis.signals)}"
    )
    
    # Print signal details
    print(f"\n  📊 Analysis Results:")
    print(f"     Phase: {analysis.phase.value}")
    print(f"     Urgency: {analysis.urgency.value}")
    print(f"     Action: {analysis.action}")
    print(f"     Confidence: {analysis.confidence*100:.1f}%")
    print(f"     Signals Detected: {len(analysis.signals)}")
    for sig in analysis.signals:
        print(f"       • {sig.indicator}: {sig.message}")
    print(f"     Rationale: {analysis.rationale}")
    
    return test_passed


def test_phase3_breakdown():
    """Test Phase 3: Breakdown signals."""
    print_section("TEST 3: Phase 3 - Breakdown Signals")
    
    detector = ExitSignalDetector()
    
    # Scenario: EMA20 break + SAR flip (CRITICAL)
    features = {
        "adx": 35.0,
        "adx_prev": 40.0,
        "macd_hist": -0.1,  # Crossed negative
        "macd_hist_prev": 0.2,
        "rsi": 55.0,
        "atr_14": 5.0,
        "atr_14_prev": 7.0,
        "ema20": 3870.0,
        "bb_upper": 3890.0,
        "bb_lower": 3850.0,
        "bb_mid": 3870.0,
        "sar": 3875.0,  # SAR above price (was below)
        "vwap": 3868.0,
        "vwap_prev": 3872.0,
    }
    
    # Create bars
    bars_data = {
        'time': pd.date_range('2025-01-01', periods=10, freq='15min'),
        'open': [3890, 3888, 3885, 3880, 3875, 3872, 3870, 3868, 3865, 3863],
        'high': [3895, 3890, 3887, 3882, 3877, 3874, 3872, 3870, 3867, 3865],
        'low': [3885, 3883, 3880, 3875, 3870, 3868, 3865, 3863, 3860, 3858],
        'close': [3888, 3885, 3882, 3877, 3872, 3870, 3867, 3865, 3862, 3860],
        'tick_volume': [1000 - i*30 for i in range(10)],
        'rsi': [70, 68, 65, 62, 58, 55, 52, 50, 48, 46]
    }
    bars = pd.DataFrame(bars_data)
    
    # BUY position, current price below EMA20
    analysis = detector.analyze_exit_signals(
        direction="buy",
        entry_price=3850.0,
        current_price=3865.0,  # Below EMA20 (3870)
        features=features,
        bars=bars
    )
    
    # Assertions
    test_passed = True
    details = []
    
    if analysis.phase != ExitPhase.BREAKDOWN:
        test_passed = False
        details.append(f"Expected BREAKDOWN, got {analysis.phase}")
    
    if analysis.urgency not in [ExitUrgency.HIGH, ExitUrgency.CRITICAL]:
        test_passed = False
        details.append(f"Expected HIGH/CRITICAL urgency, got {analysis.urgency}")
    
    if analysis.action not in ["trail_very_tight", "exit_full"]:
        test_passed = False
        details.append(f"Expected trail_very_tight/exit_full, got {analysis.action}")
    
    if len(analysis.signals) < 1:
        test_passed = False
        details.append(f"Expected >= 1 signal, got {len(analysis.signals)}")
    
    print_result(
        "Phase 3 Detection",
        test_passed,
        " | ".join(details) if details else f"Phase={analysis.phase}, Urgency={analysis.urgency}, Signals={len(analysis.signals)}"
    )
    
    # Print signal details
    print(f"\n  📊 Analysis Results:")
    print(f"     Phase: {analysis.phase.value}")
    print(f"     Urgency: {analysis.urgency.value}")
    print(f"     Action: {analysis.action}")
    print(f"     Confidence: {analysis.confidence*100:.1f}%")
    print(f"     Signals Detected: {len(analysis.signals)}")
    for sig in analysis.signals:
        print(f"       • {sig.indicator}: {sig.message}")
    print(f"     Rationale: {analysis.rationale}")
    
    return test_passed


def test_no_signals():
    """Test no exit signals (trend intact)."""
    print_section("TEST 4: No Exit Signals - Trend Intact")
    
    detector = ExitSignalDetector()
    
    # Scenario: Strong trend, no exhaustion
    features = {
        "adx": 48.0,  # Rising
        "adx_prev": 45.0,
        "macd_hist": 0.8,  # Expanding
        "macd_hist_prev": 0.6,
        "rsi": 65.0,
        "atr_14": 8.5,  # Stable/rising
        "atr_14_prev": 8.0,
        "ema20": 3850.0,
        "bb_upper": 3900.0,
        "bb_lower": 3800.0,
        "bb_mid": 3850.0,
        "vwap": 3860.0,
        "vwap_prev": 3855.0,  # Rising
    }
    
    # Create bars with strong trend
    bars_data = {
        'time': pd.date_range('2025-01-01', periods=10, freq='15min'),
        'open': [3850 + i*3 for i in range(10)],
        'high': [3860 + i*3 for i in range(10)],
        'low': [3845 + i*3 for i in range(10)],
        'close': [3855 + i*3 for i in range(10)],
        'tick_volume': [1000 + i*20 for i in range(10)],  # Rising volume
        'rsi': [60 + i*0.5 for i in range(10)]
    }
    bars = pd.DataFrame(bars_data)
    
    analysis = detector.analyze_exit_signals(
        direction="buy",
        entry_price=3850.0,
        current_price=3880.0,
        features=features,
        bars=bars
    )
    
    # Assertions
    test_passed = True
    details = []
    
    if analysis.phase != ExitPhase.NONE:
        test_passed = False
        details.append(f"Expected NONE, got {analysis.phase}")
    
    if analysis.urgency != ExitUrgency.NONE:
        test_passed = False
        details.append(f"Expected NONE urgency, got {analysis.urgency}")
    
    if analysis.action != "hold":
        test_passed = False
        details.append(f"Expected hold, got {analysis.action}")
    
    print_result(
        "No Signals Detection",
        test_passed,
        " | ".join(details) if details else f"Phase={analysis.phase}, Action={analysis.action}"
    )
    
    # Print signal details
    print(f"\n  📊 Analysis Results:")
    print(f"     Phase: {analysis.phase.value}")
    print(f"     Urgency: {analysis.urgency.value}")
    print(f"     Action: {analysis.action}")
    print(f"     Confidence: {analysis.confidence*100:.1f}%")
    print(f"     Signals Detected: {len(analysis.signals)}")
    print(f"     Rationale: {analysis.rationale}")
    
    return test_passed


def test_trailing_stop_calculation():
    """Test trailing stop ATR multiplier logic."""
    print_section("TEST 5: Trailing Stop Calculation")
    
    # Test ATR multipliers
    atr = 8.0
    current_price = 3880.0
    
    test_cases = [
        ("trail_normal", 2.0, 3880 - (2.0 * 8)),
        ("trail_moderate", 1.5, 3880 - (1.5 * 8)),
        ("trail_tight", 1.0, 3880 - (1.0 * 8)),
        ("trail_very_tight", 0.5, 3880 - (0.5 * 8)),
    ]
    
    all_passed = True
    
    for action, multiplier, expected_sl in test_cases:
        calculated_sl = current_price - (multiplier * atr)
        passed = abs(calculated_sl - expected_sl) < 0.01
        all_passed = all_passed and passed
        
        print_result(
            f"{action} ({multiplier}x ATR)",
            passed,
            f"Expected SL={expected_sl:.2f}, Calculated={calculated_sl:.2f}"
        )
    
    return all_passed


def test_sell_position():
    """Test exit signals for SELL position."""
    print_section("TEST 6: SELL Position Exit Signals")
    
    detector = ExitSignalDetector()
    
    # Scenario: SELL position with exhaustion signals
    features = {
        "adx": 40.0,
        "adx_prev": 44.0,
        "macd_hist": -0.4,  # Negative but shrinking
        "macd_hist_prev": -0.6,
        "rsi": 32.0,  # Oversold
        "atr_14": 6.5,
        "atr_14_prev": 8.0,
        "ema20": 3850.0,
        "bb_upper": 3880.0,
        "bb_lower": 3820.0,
        "bb_mid": 3850.0,
    }
    
    # SELL position, price rising (against us)
    analysis = detector.analyze_exit_signals(
        direction="sell",
        entry_price=3900.0,
        current_price=3870.0,  # +30 points profit
        features=features,
        bars=None
    )
    
    # Assertions
    test_passed = True
    details = []
    
    if analysis.phase == ExitPhase.NONE:
        test_passed = False
        details.append(f"Expected some signals for SELL position, got NONE")
    
    print_result(
        "SELL Position Detection",
        test_passed,
        " | ".join(details) if details else f"Phase={analysis.phase}, Urgency={analysis.urgency}, Signals={len(analysis.signals)}"
    )
    
    # Print signal details
    print(f"\n  📊 Analysis Results:")
    print(f"     Direction: SELL")
    print(f"     Phase: {analysis.phase.value}")
    print(f"     Urgency: {analysis.urgency.value}")
    print(f"     Action: {analysis.action}")
    print(f"     Confidence: {analysis.confidence*100:.1f}%")
    print(f"     Signals Detected: {len(analysis.signals)}")
    for sig in analysis.signals:
        print(f"       • {sig.indicator}: {sig.message}")
    
    return test_passed


def test_confidence_scoring():
    """Test confidence scoring logic."""
    print_section("TEST 7: Confidence Scoring")
    
    detector = ExitSignalDetector()
    
    # High confidence scenario (multiple strong signals)
    features_high = {
        "adx": 38.0,
        "adx_prev": 48.0,  # Large rollover
        "macd_hist": 0.1,
        "macd_hist_prev": 0.8,  # Large deceleration
        "rsi": 75.0,
        "atr_14": 5.0,
        "atr_14_prev": 8.5,  # 40% ATR drop
        "ema20": 3870.0,
        "bb_upper": 3890.0,
        "bb_lower": 3850.0,
        "bb_mid": 3870.0,
    }
    
    analysis_high = detector.analyze_exit_signals(
        direction="buy",
        entry_price=3850.0,
        current_price=3865.0,  # Below EMA20
        features=features_high,
        bars=None
    )
    
    # Low confidence scenario (weak signals)
    features_low = {
        "adx": 41.0,
        "adx_prev": 42.0,  # Small rollover
        "macd_hist": 0.5,
        "macd_hist_prev": 0.6,
        "rsi": 68.0,
        "atr_14": 7.8,
        "atr_14_prev": 8.0,
        "ema20": 3850.0,
        "bb_upper": 3890.0,
        "bb_lower": 3810.0,
        "bb_mid": 3850.0,
    }
    
    analysis_low = detector.analyze_exit_signals(
        direction="buy",
        entry_price=3850.0,
        current_price=3870.0,
        features=features_low,
        bars=None
    )
    
    # Assertions
    test_passed = True
    details = []
    
    if analysis_high.confidence <= analysis_low.confidence:
        test_passed = False
        details.append(f"High confidence ({analysis_high.confidence:.2f}) should be > low confidence ({analysis_low.confidence:.2f})")
    
    if analysis_high.confidence < 0.6:
        test_passed = False
        details.append(f"High confidence scenario should be >= 0.6, got {analysis_high.confidence:.2f}")
    
    print_result(
        "Confidence Scoring",
        test_passed,
        " | ".join(details) if details else f"High={analysis_high.confidence*100:.1f}%, Low={analysis_low.confidence*100:.1f}%"
    )
    
    print(f"\n  📊 High Confidence Scenario:")
    print(f"     Confidence: {analysis_high.confidence*100:.1f}%")
    print(f"     Signals: {len(analysis_high.signals)}")
    print(f"     Phase: {analysis_high.phase.value}")
    
    print(f"\n  📊 Low Confidence Scenario:")
    print(f"     Confidence: {analysis_low.confidence*100:.1f}%")
    print(f"     Signals: {len(analysis_low.signals)}")
    print(f"     Phase: {analysis_low.phase.value}")
    
    return test_passed


def test_alert_formatting():
    """Test Telegram alert message formatting."""
    print_section("TEST 8: Alert Message Formatting")
    
    from infra.exit_monitor import ExitMonitor
    
    # Create mock action
    action = {
        "ticket": 123456,
        "symbol": "XAUUSD",
        "direction": "buy",
        "entry_price": 3850.0,
        "current_price": 3878.0,
        "unrealized_r": 1.4,
        "phase": "exhaustion",
        "urgency": "high",
        "action": "trail_tight",
        "confidence": 0.82,
        "signals": [
            {
                "indicator": "ATR_compression",
                "phase": "exhaustion",
                "strength": 0.9,
                "message": "ATR dropped 24.3% (volatility exhaustion)"
            },
            {
                "indicator": "BB_reentry",
                "phase": "exhaustion",
                "strength": 0.9,
                "message": "Price closed back inside upper BB (exhaustion)"
            }
        ],
        "rationale": "Exhaustion confirmed across 2 indicator categories - tighten stops to 1.0x ATR",
        "timestamp": datetime.now().isoformat(),
        "executed": False
    }
    
    # Create ExitMonitor (without MT5 connection for testing)
    try:
        exit_monitor = ExitMonitor(
            mt5_service=None,
            feature_builder=None,
            journal_repo=None,
            auto_exit_enabled=False
        )
        
        message = exit_monitor.format_exit_alert(action)
        
        # Check message contains key elements
        test_passed = True
        details = []
        
        required_elements = [
            "Exit Signal Detected",
            "XAUUSD",
            "123456",
            "1.4",  # Changed from "+1.4R" to "1.4" (formatted as +1.40R)
            "HIGH",
            "Exhaustion",
            "Tighten stops to 1.0x ATR",
            "82%",
            "ATR_compression",
            "BB_reentry"
        ]
        
        for element in required_elements:
            if element not in message:
                test_passed = False
                details.append(f"Missing: {element}")
        
        print_result(
            "Alert Formatting",
            test_passed,
            " | ".join(details) if details else "All required elements present"
        )
        
        print(f"\n  📱 Sample Alert Message:")
        print("  " + "-"*76)
        for line in message.split("\n"):
            print(f"  {line}")
        print("  " + "-"*76)
        
        return test_passed
        
    except Exception as e:
        print_result("Alert Formatting", False, f"Error: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("  EXIT MONITOR TEST SUITE")
    print("  Testing ExitSignalDetector and ExitMonitor functionality")
    print("="*80)
    
    tests = [
        ("Phase 1: Early Warning", test_phase1_early_warning),
        ("Phase 2: Exhaustion", test_phase2_exhaustion),
        ("Phase 3: Breakdown", test_phase3_breakdown),
        ("No Signals (Trend Intact)", test_no_signals),
        ("Trailing Stop Calculation", test_trailing_stop_calculation),
        ("SELL Position", test_sell_position),
        ("Confidence Scoring", test_confidence_scoring),
        ("Alert Formatting", test_alert_formatting),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}", exc_info=True)
            results.append((test_name, False))
    
    # Print summary
    print_section("TEST SUMMARY")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n{'='*80}")
    print(f"  Results: {passed_count}/{total_count} tests passed ({passed_count/total_count*100:.1f}%)")
    print(f"{'='*80}\n")
    
    # Return exit code
    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
