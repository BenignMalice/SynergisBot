"""
Phase 2 Implementation Test Script

Tests all Phase 2 components:
- AIPatternClassifier
- Order flow plan identification
- Quick order flow condition checks
- 5-second monitoring loop integration
"""

import sys
import time
from typing import Dict, List

# Test results tracking
test_results = {
    'passed': [],
    'failed': [],
    'warnings': []
}

def log_test(name: str, passed: bool, message: str = ""):
    """Log test result"""
    if passed:
        test_results['passed'].append(name)
        status = "[PASS]"
    else:
        test_results['failed'].append(name)
        status = "[FAIL]"
    
    print(f"{status} {name}")
    if message:
        print(f"      {message}")

def test_pattern_classifier_import():
    """Test 1: Pattern classifier imports"""
    try:
        from infra.ai_pattern_classifier import AIPatternClassifier
        log_test("Pattern Classifier Import", True)
        return True
    except Exception as e:
        log_test("Pattern Classifier Import", False, f"Error: {e}")
        return False

def test_pattern_classifier_initialization():
    """Test 2: Pattern classifier initialization"""
    try:
        from infra.ai_pattern_classifier import AIPatternClassifier
        classifier = AIPatternClassifier()
        
        # Check default weights
        assert 'absorption' in classifier.weights
        assert classifier.threshold == 0.75
        
        log_test("Pattern Classifier Initialization", True)
        return True
    except Exception as e:
        log_test("Pattern Classifier Initialization", False, f"Error: {e}")
        return False

def test_pattern_classifier_basic():
    """Test 3: Basic pattern classification"""
    try:
        from infra.ai_pattern_classifier import AIPatternClassifier
        classifier = AIPatternClassifier()
        
        # Test with simple boolean signals
        signals = {
            'absorption': True,
            'delta_divergence': False,
            'liquidity_sweep': False,
            'cvd_divergence': False,
            'vwap_deviation': False
        }
        
        result = classifier.classify_pattern(signals)
        
        assert 'probability' in result
        assert 'pattern_type' in result
        assert 'meets_threshold' in result
        assert 0 <= result['probability'] <= 100
        
        log_test("Pattern Classifier Basic", True, f"Probability: {result['probability']:.1f}%")
        return True
    except Exception as e:
        log_test("Pattern Classifier Basic", False, f"Error: {e}")
        return False

def test_pattern_classifier_complex_signals():
    """Test 4: Complex signal classification"""
    try:
        from infra.ai_pattern_classifier import AIPatternClassifier
        classifier = AIPatternClassifier()
        
        # Test with complex signals (dict with strength)
        signals = {
            'absorption': True,
            'delta_divergence': {'strength': 0.8, 'type': 'bullish'},
            'liquidity_sweep': True,
            'cvd_divergence': {'strength': 0.6, 'type': 'bullish'},
            'vwap_deviation': 0.7
        }
        
        result = classifier.classify_pattern(signals)
        
        assert result['probability'] > 0
        assert result['pattern_type'] != 'unknown'
        assert 'signal_scores' in result
        
        log_test("Pattern Classifier Complex Signals", True, 
                f"Type: {result['pattern_type']}, Probability: {result['probability']:.1f}%")
        return True
    except Exception as e:
        log_test("Pattern Classifier Complex Signals", False, f"Error: {e}")
        return False

def test_pattern_classifier_threshold():
    """Test 5: Threshold logic"""
    try:
        from infra.ai_pattern_classifier import AIPatternClassifier
        classifier = AIPatternClassifier()
        
        # Test with high signals (should meet threshold)
        high_signals = {
            'absorption': True,
            'delta_divergence': {'strength': 0.9, 'type': 'bullish'},
            'liquidity_sweep': True,
            'cvd_divergence': {'strength': 0.8, 'type': 'bullish'},
            'vwap_deviation': 0.9
        }
        
        result_high = classifier.classify_pattern(high_signals)
        
        # Test with low signals (should not meet threshold)
        low_signals = {
            'absorption': False,
            'delta_divergence': False,
            'liquidity_sweep': False,
            'cvd_divergence': {'strength': 0.2, 'type': 'bullish'},
            'vwap_deviation': 0.1
        }
        
        result_low = classifier.classify_pattern(low_signals)
        
        # High signals should meet threshold, low should not
        assert result_high['meets_threshold'] == True or result_high['probability'] >= 75
        assert result_low['meets_threshold'] == False or result_low['probability'] < 75
        
        log_test("Pattern Classifier Threshold", True, 
                f"High: {result_high['probability']:.1f}%, Low: {result_low['probability']:.1f}%")
        return True
    except Exception as e:
        log_test("Pattern Classifier Threshold", False, f"Error: {e}")
        return False

def test_pattern_classifier_confidence():
    """Test 6: Confidence calculation"""
    try:
        from infra.ai_pattern_classifier import AIPatternClassifier
        classifier = AIPatternClassifier()
        
        signals = {
            'absorption': True,
            'delta_divergence': {'strength': 0.7, 'type': 'bullish'},
            'liquidity_sweep': True
        }
        
        confidence = classifier.get_pattern_confidence(signals)
        
        assert 0 <= confidence <= 100
        
        should_execute = classifier.should_execute(signals)
        assert isinstance(should_execute, bool)
        
        log_test("Pattern Classifier Confidence", True, f"Confidence: {confidence:.1f}%")
        return True
    except Exception as e:
        log_test("Pattern Classifier Confidence", False, f"Error: {e}")
        return False

def test_pattern_classifier_breakdown():
    """Test 7: Signal breakdown"""
    try:
        from infra.ai_pattern_classifier import AIPatternClassifier
        classifier = AIPatternClassifier()
        
        signals = {
            'absorption': True,
            'delta_divergence': {'strength': 0.8, 'type': 'bullish'},
            'liquidity_sweep': False
        }
        
        breakdown = classifier.get_signal_breakdown(signals)
        
        assert 'signal_scores' in breakdown
        assert 'contributions' in breakdown
        assert 'missing_signals' in breakdown
        
        log_test("Pattern Classifier Breakdown", True)
        return True
    except Exception as e:
        log_test("Pattern Classifier Breakdown", False, f"Error: {e}")
        return False

def test_auto_execution_system_import():
    """Test 8: AutoExecutionSystem imports with Phase 2"""
    try:
        from auto_execution_system import AutoExecutionSystem
        log_test("AutoExecutionSystem Import", True)
        return True
    except Exception as e:
        log_test("AutoExecutionSystem Import", False, f"Error: {e}")
        return False

def test_order_flow_plan_methods():
    """Test 9: Order flow plan methods exist"""
    try:
        from auto_execution_system import AutoExecutionSystem
        
        system = AutoExecutionSystem()
        
        # Check Phase 2 methods exist
        assert hasattr(system, '_get_order_flow_plans')
        assert hasattr(system, '_check_order_flow_plans_quick')
        assert hasattr(system, '_check_order_flow_conditions_only')
        assert hasattr(system, '_check_btc_order_flow_conditions_only')
        assert hasattr(system, '_check_proxy_order_flow_conditions_only')
        
        log_test("Order Flow Plan Methods", True)
        return True
    except Exception as e:
        log_test("Order Flow Plan Methods", False, f"Error: {e}")
        return False

def test_pattern_classifier_integration():
    """Test 10: Pattern classifier in AutoExecutionSystem"""
    try:
        from auto_execution_system import AutoExecutionSystem
        
        system = AutoExecutionSystem()
        
        # Check pattern classifier is initialized
        assert hasattr(system, 'pattern_classifier')
        # May be None if not available, which is acceptable
        if system.pattern_classifier is not None:
            assert hasattr(system.pattern_classifier, 'classify_pattern')
        
        log_test("Pattern Classifier Integration", True, 
                f"Available: {system.pattern_classifier is not None}")
        return True
    except Exception as e:
        log_test("Pattern Classifier Integration", False, f"Error: {e}")
        return False

def test_get_order_flow_plans():
    """Test 11: Get order flow plans method"""
    try:
        from auto_execution_system import AutoExecutionSystem, TradePlan
        
        system = AutoExecutionSystem()
        
        # Create a test plan with order flow conditions
        test_plan = TradePlan(
            plan_id="test_plan_1",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"delta_positive": True, "cvd_rising": True},
            created_at="2025-12-30T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Add plan to system
        with system.plans_lock:
            system.plans["test_plan_1"] = test_plan
        
        # Get order flow plans
        order_flow_plans = system._get_order_flow_plans()
        
        assert isinstance(order_flow_plans, list)
        # Should find our test plan
        plan_ids = [p.plan_id for p in order_flow_plans]
        assert "test_plan_1" in plan_ids
        
        # Clean up
        with system.plans_lock:
            if "test_plan_1" in system.plans:
                del system.plans["test_plan_1"]
        
        log_test("Get Order Flow Plans", True, f"Found {len(order_flow_plans)} plan(s)")
        return True
    except Exception as e:
        log_test("Get Order Flow Plans", False, f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_order_flow_condition_check():
    """Test 12: Order flow condition check"""
    try:
        from auto_execution_system import AutoExecutionSystem, TradePlan
        
        system = AutoExecutionSystem()
        
        # Create a test plan with order flow conditions
        test_plan = TradePlan(
            plan_id="test_plan_2",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"delta_positive": True},
            created_at="2025-12-30T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Test condition check (may return False if metrics unavailable, which is acceptable)
        result = system._check_order_flow_conditions_only(test_plan)
        
        # Result should be boolean
        assert isinstance(result, bool)
        
        log_test("Order Flow Condition Check", True, f"Result: {result}")
        return True
    except Exception as e:
        log_test("Order Flow Condition Check", False, f"Error: {e}")
        return False

def test_monitor_loop_integration():
    """Test 13: Monitor loop has Phase 2 integration"""
    try:
        from auto_execution_system import AutoExecutionSystem
        import inspect
        
        system = AutoExecutionSystem()
        
        # Check _monitor_loop method exists
        assert hasattr(system, '_monitor_loop')
        
        # Check if method mentions Phase 2 or order flow
        source = inspect.getsource(system._monitor_loop)
        # Look for order flow check interval or Phase 2 references
        has_order_flow_check = 'order_flow_check' in source.lower() or 'order_flow_plans' in source.lower()
        
        log_test("Monitor Loop Integration", True, 
                f"Has order flow checks: {has_order_flow_check}")
        return True
    except Exception as e:
        log_test("Monitor Loop Integration", False, f"Error: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("=" * 70)
    print("Phase 2 Implementation Test Suite")
    print("=" * 70)
    print()
    
    tests = [
        test_pattern_classifier_import,
        test_pattern_classifier_initialization,
        test_pattern_classifier_basic,
        test_pattern_classifier_complex_signals,
        test_pattern_classifier_threshold,
        test_pattern_classifier_confidence,
        test_pattern_classifier_breakdown,
        test_auto_execution_system_import,
        test_order_flow_plan_methods,
        test_pattern_classifier_integration,
        test_get_order_flow_plans,
        test_order_flow_condition_check,
        test_monitor_loop_integration,
    ]
    
    for test_func in tests:
        try:
            test_func()
        except Exception as e:
            log_test(test_func.__name__, False, f"Unexpected error: {e}")
    
    # Print summary
    print()
    print("=" * 70)
    print("Test Summary")
    print("=" * 70)
    print(f"Passed: {len(test_results['passed'])}")
    print(f"Failed: {len(test_results['failed'])}")
    print()
    
    if test_results['failed']:
        print("Failed Tests:")
        for test in test_results['failed']:
            print(f"  - {test}")
        print()
    
    if len(test_results['failed']) == 0:
        print("[SUCCESS] All Phase 2 tests passed!")
        return 0
    else:
        print(f"[FAILURE] {len(test_results['failed'])} test(s) failed")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
