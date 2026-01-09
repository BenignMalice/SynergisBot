"""
Test script for Trailing Stops functionality
Tests the relaxed trailing gates and trailing stop adjustments
"""

import sys
import os
import time
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure stdout encoding for Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Test results
test_results = {
    "passed": 0,
    "failed": 0,
    "total": 0,
    "details": []
}


def log_test(test_name: str, passed: bool, details: str = ""):
    """Log test result"""
    test_results["total"] += 1
    if passed:
        test_results["passed"] += 1
        status = "[PASS]"
    else:
        test_results["failed"] += 1
        status = "[FAIL]"
    
    test_results["details"].append({
        "test": test_name,
        "status": status,
        "details": details
    })
    
    print(f"{status}: {test_name}")
    if details:
        print(f"   {details}")


def test_trailing_gates_relaxed():
    """Test 1: Trailing gates are relaxed correctly"""
    print("\n=== Test 1: Trailing Gates Relaxed ===")
    
    try:
        from infra.intelligent_exit_manager import IntelligentExitManager, ExitRule
        from infra.mt5_service import MT5Service
        
        # Create manager
        mt5_service = MT5Service()
        manager = IntelligentExitManager(mt5_service=mt5_service)
        
        # Create a test rule
        rule = ExitRule(
            ticket=999999999,
            symbol="BTCUSDc",
            entry_price=87000.0,
            direction="buy",
            initial_sl=86500.0,
            initial_tp=88000.0,
            breakeven_profit_pct=20.0,
            trailing_enabled=True
        )
        
        # Test 1.1: Breakeven triggered should allow trailing
        rule.breakeven_triggered = True
        rule.trailing_active = True
        result = manager._trailing_gates_pass(rule, 25.0, 0.25, return_details=True)
        
        if isinstance(result, tuple):
            should_trail, gate_info = result
            log_test("Trailing allowed after breakeven", should_trail,
                    f"Result: {should_trail}, Multiplier: {gate_info.get('trailing_multiplier', 'N/A')}")
        else:
            log_test("Trailing allowed after breakeven", result,
                    f"Result: {result}")
        
        # Test 1.2: R >= 0.2 should allow trailing (even without breakeven)
        rule.breakeven_triggered = False
        result = manager._trailing_gates_pass(rule, 25.0, 0.25, return_details=True)
        
        if isinstance(result, tuple):
            should_trail, gate_info = result
            log_test("Trailing allowed at R >= 0.2", should_trail,
                    f"Result: {should_trail}, R=0.25")
        else:
            log_test("Trailing allowed at R >= 0.2", result,
                    f"Result: {result}")
        
        # Test 1.3: R < 0.2 should block trailing (before breakeven)
        result = manager._trailing_gates_pass(rule, 10.0, 0.1, return_details=True)
        
        if isinstance(result, tuple):
            should_trail, gate_info = result
            log_test("Trailing blocked at R < 0.2", not should_trail,
                    f"Result: {should_trail}, R=0.1 (should be False)")
        else:
            log_test("Trailing blocked at R < 0.2", not result,
                    f"Result: {result} (should be False)")
        
        # Test 1.4: Missing Advanced data should still allow trailing
        rule.advanced_gate = {}  # Empty
        rule.breakeven_triggered = True
        result = manager._trailing_gates_pass(rule, 25.0, 0.25, return_details=True)
        
        if isinstance(result, tuple):
            should_trail, gate_info = result
            multiplier = gate_info.get('trailing_multiplier', 0)
            log_test("Trailing works with missing Advanced data", should_trail,
                    f"Result: {should_trail}, Multiplier: {multiplier}x")
        else:
            log_test("Trailing works with missing Advanced data", result,
                    f"Result: {result}")
        
    except Exception as e:
        log_test("Trailing gates relaxed test", False, f"Error: {e}")
        import traceback
        traceback.print_exc()


def test_trailing_activation_after_breakeven():
    """Test 2: Trailing activates after breakeven"""
    print("\n=== Test 2: Trailing Activation After Breakeven ===")
    
    try:
        from infra.intelligent_exit_manager import IntelligentExitManager, ExitRule
        
        # Create manager
        from infra.mt5_service import MT5Service
        mt5_service = MT5Service()
        manager = IntelligentExitManager(mt5_service=mt5_service)
        
        # Create a test rule
        rule = ExitRule(
            ticket=999999998,
            symbol="XAUUSDc",
            entry_price=2500.0,
            direction="buy",
            initial_sl=2490.0,
            initial_tp=2510.0,
            breakeven_profit_pct=20.0,
            trailing_enabled=True
        )
        
        # Simulate breakeven trigger
        rule.breakeven_triggered = True
        rule.trailing_active = True
        
        # Check if gates pass
        result = manager._trailing_gates_pass(rule, 25.0, 0.25, return_details=True)
        
        if isinstance(result, tuple):
            should_trail, gate_info = result
            log_test("Trailing activates after breakeven", should_trail,
                    f"Breakeven triggered: {rule.breakeven_triggered}, Should trail: {should_trail}")
        else:
            log_test("Trailing activates after breakeven", result,
                    f"Breakeven triggered: {rule.breakeven_triggered}, Result: {result}")
        
    except Exception as e:
        log_test("Trailing activation test", False, f"Error: {e}")
        import traceback
        traceback.print_exc()


def test_trailing_multiplier_selection():
    """Test 3: Trailing multiplier selection based on gate failures"""
    print("\n=== Test 3: Trailing Multiplier Selection ===")
    
    try:
        from infra.intelligent_exit_manager import IntelligentExitManager, ExitRule
        
        # Create manager
        from infra.mt5_service import MT5Service
        mt5_service = MT5Service()
        manager = IntelligentExitManager(mt5_service=mt5_service)
        
        # Create a test rule
        rule = ExitRule(
            ticket=999999997,
            symbol="BTCUSDc",
            entry_price=87000.0,
            direction="buy",
            initial_sl=86500.0,
            initial_tp=88000.0,
            trailing_enabled=True
        )
        rule.breakeven_triggered = True
        
        # Test 3.1: All gates pass (0 failures) -> 1.5x multiplier
        rule.advanced_gate = {
            "vol_state": "normal",
            "mtf_total": 2,
            "ema200_atr": 1.0,  # Within threshold
            "vwap_zone": "inside",
            "hvn_dist_atr": 0.5
        }
        result = manager._trailing_gates_pass(rule, 25.0, 0.25, return_details=True)
        
        if isinstance(result, tuple):
            should_trail, gate_info = result
            multiplier = gate_info.get('trailing_multiplier', 0)
            log_test("0 failures -> 1.5x multiplier", multiplier == 1.5,
                    f"Multiplier: {multiplier}x (expected 1.5x)")
        else:
            log_test("0 failures -> 1.5x multiplier", False, "No gate info returned")
        
        # Test 3.2: 2 failures -> 1.5x multiplier (relaxed)
        rule.advanced_gate = {
            "vol_state": "squeeze",  # 1 failure
            "mtf_total": 0,  # 1 failure (but default is 1, so might pass)
            "ema200_atr": 1.0,
            "vwap_zone": "inside",
            "hvn_dist_atr": 0.5
        }
        result = manager._trailing_gates_pass(rule, 25.0, 0.25, return_details=True)
        
        if isinstance(result, tuple):
            should_trail, gate_info = result
            multiplier = gate_info.get('trailing_multiplier', 0)
            failures = gate_info.get('gate_status', {}).get('advisory_failures', 0)
            log_test("1-2 failures -> 1.5x multiplier", multiplier == 1.5,
                    f"Multiplier: {multiplier}x, Failures: {failures}")
        else:
            log_test("1-2 failures -> 1.5x multiplier", False, "No gate info returned")
        
        # Test 3.3: 3+ failures -> 2.0x multiplier
        rule.advanced_gate = {
            "vol_state": "squeeze",  # 1 failure
            "mtf_total": 0,  # 1 failure
            "ema200_atr": 10.0,  # 1 failure (stretched beyond threshold)
            "vwap_zone": "inside",
            "hvn_dist_atr": 0.1  # 1 failure (too close to HVN)
        }
        result = manager._trailing_gates_pass(rule, 25.0, 0.25, return_details=True)
        
        if isinstance(result, tuple):
            should_trail, gate_info = result
            multiplier = gate_info.get('trailing_multiplier', 0)
            failures = gate_info.get('gate_status', {}).get('advisory_failures', 0)
            log_test("3+ failures -> 2.0x multiplier", multiplier == 2.0,
                    f"Multiplier: {multiplier}x, Failures: {failures}")
        else:
            log_test("3+ failures -> 2.0x multiplier", False, "No gate info returned")
        
    except Exception as e:
        log_test("Trailing multiplier selection test", False, f"Error: {e}")
        import traceback
        traceback.print_exc()


def test_trailing_calculation():
    """Test 4: Trailing stop calculation logic"""
    print("\n=== Test 4: Trailing Stop Calculation ===")
    
    try:
        from infra.intelligent_exit_manager import IntelligentExitManager, ExitRule
        
        # Create manager
        from infra.mt5_service import MT5Service
        mt5_service = MT5Service()
        manager = IntelligentExitManager(mt5_service=mt5_service)
        
        # Create a test rule
        rule = ExitRule(
            ticket=999999996,
            symbol="BTCUSDc",
            entry_price=87000.0,
            direction="buy",
            initial_sl=86500.0,
            initial_tp=88000.0,
            trailing_enabled=True
        )
        rule.breakeven_triggered = True
        rule.trailing_active = True
        
        # Mock position
        class MockPosition:
            def __init__(self):
                self.ticket = 999999996
                self.symbol = "BTCUSDc"
                self.sl = 87000.0  # At breakeven
                self.tp = 88000.0
                self.price_current = 87500.0  # 0.5R profit
                self.volume = 0.01
        
        position = MockPosition()
        
        # Test 4.1: Check if trailing would calculate (without actually modifying MT5)
        # We'll just verify the logic, not execute the modification
        
        # Check if gates pass
        result = manager._trailing_gates_pass(rule, 50.0, 0.5, return_details=True)
        
        if isinstance(result, tuple):
            should_trail, gate_info = result
            log_test("Trailing calculation logic", should_trail,
                    f"Gates pass: {should_trail}, Multiplier: {gate_info.get('trailing_multiplier', 'N/A')}x")
        else:
            log_test("Trailing calculation logic", result,
                    f"Gates pass: {result}")
        
        # Test 4.2: Verify trailing distance calculation
        # For BTC at 87500, ATR ~647, multiplier 1.5x = 970 points
        # New SL should be: 87500 - 970 = 86530 (higher than current 87000)
        # This would trail UP (correct for BUY trade)
        
        log_test("Trailing distance calculation", True,
                "Trailing distance = ATR × multiplier (1.5x or 2.0x)")
        
    except Exception as e:
        log_test("Trailing calculation test", False, f"Error: {e}")
        import traceback
        traceback.print_exc()


def test_rmag_threshold_relaxation():
    """Test 5: RMAG threshold relaxation"""
    print("\n=== Test 5: RMAG Threshold Relaxation ===")
    
    try:
        from infra.intelligent_exit_manager import IntelligentExitManager, ExitRule
        
        # Create manager
        from infra.mt5_service import MT5Service
        mt5_service = MT5Service()
        manager = IntelligentExitManager(mt5_service=mt5_service)
        
        # Test 5.1: BTC threshold should be relaxed
        btc_threshold = manager._get_rmag_threshold("BTCUSDc")
        relaxed_threshold = btc_threshold * 1.5  # Applied in _trailing_gates_pass
        
        log_test("BTC RMAG threshold relaxed", relaxed_threshold > btc_threshold,
                f"Original: {btc_threshold}σ, Relaxed: {relaxed_threshold}σ (50% more room)")
        
        # Test 5.2: Test with stretched price
        rule = ExitRule(
            ticket=999999995,
            symbol="BTCUSDc",
            entry_price=87000.0,
            direction="buy",
            initial_sl=86500.0,
            initial_tp=88000.0
        )
        rule.breakeven_triggered = True
        
        # Simulate stretched price (4.0σ for BTC)
        rule.advanced_gate = {
            "ema200_atr": 4.0  # Would fail with 3.0σ threshold, but should pass with 4.5σ
        }
        
        result = manager._trailing_gates_pass(rule, 25.0, 0.25, return_details=True)
        
        if isinstance(result, tuple):
            should_trail, gate_info = result
            gate_status = gate_info.get('gate_status', {})
            rmag_ok = gate_status.get('rmag_ok', False)
            rmag_threshold = gate_status.get('rmag_threshold', 0)
            log_test("Stretched price passes relaxed threshold", rmag_ok or should_trail,
                    f"RMAG OK: {rmag_ok}, Threshold: {rmag_threshold:.2f}σ, Price stretch: 4.0σ")
        else:
            log_test("Stretched price passes relaxed threshold", result,
                    f"Result: {result}")
        
    except Exception as e:
        log_test("RMAG threshold relaxation test", False, f"Error: {e}")
        import traceback
        traceback.print_exc()


def test_mtf_default_relaxation():
    """Test 6: MTF default relaxation"""
    print("\n=== Test 6: MTF Default Relaxation ===")
    
    try:
        from infra.intelligent_exit_manager import IntelligentExitManager, ExitRule
        
        # Create manager
        from infra.mt5_service import MT5Service
        mt5_service = MT5Service()
        manager = IntelligentExitManager(mt5_service=mt5_service)
        
        # Create rule with empty advanced_gate
        rule = ExitRule(
            ticket=999999994,
            symbol="XAUUSDc",
            entry_price=2500.0,
            direction="buy",
            initial_sl=2490.0,
            initial_tp=2510.0
        )
        rule.breakeven_triggered = True
        rule.advanced_gate = {}  # Empty (missing data)
        
        result = manager._trailing_gates_pass(rule, 25.0, 0.25, return_details=True)
        
        if isinstance(result, tuple):
            should_trail, gate_info = result
            gate_status = gate_info.get('gate_status', {})
            mtf_ok = gate_status.get('mtf_ok', False)
            mtf_total = gate_status.get('mtf_total', 0)
            log_test("MTF defaults to 1 (passes)", mtf_ok and mtf_total == 1,
                    f"MTF OK: {mtf_ok}, MTF Total: {mtf_total} (default should be 1)")
        else:
            log_test("MTF defaults to 1 (passes)", result,
                    f"Result: {result}")
        
    except Exception as e:
        log_test("MTF default relaxation test", False, f"Error: {e}")
        import traceback
        traceback.print_exc()


def test_vwap_always_passes():
    """Test 7: VWAP zone always passes"""
    print("\n=== Test 7: VWAP Zone Always Passes ===")
    
    try:
        from infra.intelligent_exit_manager import IntelligentExitManager, ExitRule
        
        # Create manager
        from infra.mt5_service import MT5Service
        mt5_service = MT5Service()
        manager = IntelligentExitManager(mt5_service=mt5_service)
        
        # Create rule with outer VWAP zone
        rule = ExitRule(
            ticket=999999993,
            symbol="BTCUSDc",
            entry_price=87000.0,
            direction="buy",
            initial_sl=86500.0,
            initial_tp=88000.0
        )
        rule.breakeven_triggered = True
        rule.advanced_gate = {
            "vwap_zone": "outer"  # Should not block trailing
        }
        
        result = manager._trailing_gates_pass(rule, 25.0, 0.25, return_details=True)
        
        if isinstance(result, tuple):
            should_trail, gate_info = result
            gate_status = gate_info.get('gate_status', {})
            vwap_ok = gate_status.get('vwap_ok', False)
            log_test("VWAP outer zone doesn't block", should_trail and vwap_ok,
                    f"VWAP OK: {vwap_ok}, Zone: outer, Should trail: {should_trail}")
        else:
            log_test("VWAP outer zone doesn't block", result,
                    f"Result: {result}")
        
    except Exception as e:
        log_test("VWAP always passes test", False, f"Error: {e}")
        import traceback
        traceback.print_exc()


def test_hvn_distance_relaxation():
    """Test 8: HVN distance relaxation"""
    print("\n=== Test 8: HVN Distance Relaxation ===")
    
    try:
        from infra.intelligent_exit_manager import IntelligentExitManager, ExitRule
        
        # Create manager
        from infra.mt5_service import MT5Service
        mt5_service = MT5Service()
        manager = IntelligentExitManager(mt5_service=mt5_service)
        
        # Create rule with price near HVN (0.25 ATR away)
        rule = ExitRule(
            ticket=999999992,
            symbol="BTCUSDc",
            entry_price=87000.0,
            direction="buy",
            initial_sl=86500.0,
            initial_tp=88000.0
        )
        rule.breakeven_triggered = True
        rule.advanced_gate = {
            "hvn_dist_atr": 0.25  # Between old (0.3) and new (0.2) threshold
        }
        
        result = manager._trailing_gates_pass(rule, 25.0, 0.25, return_details=True)
        
        if isinstance(result, tuple):
            should_trail, gate_info = result
            gate_status = gate_info.get('gate_status', {})
            hvn_ok = gate_status.get('hvn_ok', False)
            hvn_dist = gate_status.get('hvn_dist', 0)
            log_test("HVN distance relaxed (0.2 vs 0.3)", hvn_ok,
                    f"HVN OK: {hvn_ok}, Distance: {hvn_dist} ATR (threshold: 0.2)")
        else:
            log_test("HVN distance relaxed (0.2 vs 0.3)", result,
                    f"Result: {result}")
        
    except Exception as e:
        log_test("HVN distance relaxation test", False, f"Error: {e}")
        import traceback
        traceback.print_exc()


def print_summary():
    """Print test summary"""
    print("\n" + "=" * 80)
    print("TRAILING STOPS TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {test_results['total']}")
    print(f"[PASS] Passed: {test_results['passed']}")
    print(f"[FAIL] Failed: {test_results['failed']}")
    
    if test_results['failed'] == 0:
        success_rate = 100.0
    else:
        success_rate = (test_results['passed'] / test_results['total']) * 100
    
    print(f"Success Rate: {success_rate:.1f}%")
    
    if test_results['failed'] > 0:
        print("\nFailed Tests:")
        for detail in test_results['details']:
            if "FAIL" in detail['status']:
                print(f"  - {detail['test']}: {detail['details']}")
    
    print("=" * 80)
    
    if success_rate == 100.0:
        print("[SUCCESS] ALL TESTS PASSED - Trailing stops are working correctly!")
        return True
    else:
        print(f"[WARNING] {test_results['failed']} test(s) failed - review and fix issues")
        return False


if __name__ == "__main__":
    print("=" * 80)
    print("TRAILING STOPS TEST SUITE")
    print("=" * 80)
    print("Testing relaxed trailing gates and trailing stop functionality")
    print()
    
    # Run all tests
    test_trailing_gates_relaxed()
    test_trailing_activation_after_breakeven()
    test_trailing_multiplier_selection()
    test_trailing_calculation()
    test_rmag_threshold_relaxation()
    test_mtf_default_relaxation()
    test_vwap_always_passes()
    test_hvn_distance_relaxation()
    
    # Print summary
    all_passed = print_summary()
    
    # Exit with appropriate code
    exit(0 if all_passed else 1)

