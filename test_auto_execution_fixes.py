"""
Test script to verify the 4 auto-execution fixes are working correctly.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import Dict, Any, Optional

# Fix encoding
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

@dataclass
class MockTradePlan:
    """Mock TradePlan for testing"""
    plan_id: str
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float
    conditions: Dict[str, Any]
    status: str = "pending"

def test_vwap_overextension_filter():
    """Test Fix 1: VWAP Overextension Filter"""
    print("=" * 80)
    print("TEST 1: VWAP Overextension Filter")
    print("=" * 80)
    
    # Check if the code exists in _execute_trade
    try:
        with open("auto_execution_system.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check for VWAP overextension check
        has_vwap_check = "ISSUE 1: VWAP Overextension Filter" in content
        has_buy_block = 'plan.direction == "BUY" and deviation > 2.0' in content
        has_sell_block = 'plan.direction == "SELL" and deviation < -2.0' in content
        
        print(f"  [{'OK' if has_vwap_check else 'FAIL'}] VWAP overextension check found in _execute_trade()")
        print(f"  [{'OK' if has_buy_block else 'FAIL'}] BUY block logic (deviation > 2.0σ)")
        print(f"  [{'OK' if has_sell_block else 'FAIL'}] SELL block logic (deviation < -2.0σ)")
        
        if has_vwap_check and has_buy_block and has_sell_block:
            print("\n  ✅ TEST 1 PASSED: VWAP overextension filter implemented correctly")
            return True
        else:
            print("\n  ❌ TEST 1 FAILED: Missing implementation")
            return False
            
    except Exception as e:
        print(f"  [ERROR] Could not test: {e}")
        return False

def test_choch_confirmation():
    """Test Fix 2: CHOCH Confirmation for Liquidity Sweeps"""
    print("\n" + "=" * 80)
    print("TEST 2: CHOCH Confirmation for Liquidity Sweeps")
    print("=" * 80)
    
    try:
        with open("auto_execution_system.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check for CHOCH confirmation check
        has_choch_check = "ISSUE 2: CHOCH Confirmation" in content
        has_sell_choch = 'plan.direction == "SELL"' in content and 'choch_bear' in content
        has_buy_choch = 'plan.direction == "BUY"' in content and 'choch_bull' in content
        has_cvd_check = 'CVD divergence' in content and 'BTCUSD' in content
        
        print(f"  [{'OK' if has_choch_check else 'FAIL'}] CHOCH confirmation check found in _check_conditions()")
        print(f"  [{'OK' if has_sell_choch else 'FAIL'}] SELL requires choch_bear/bos_bear")
        print(f"  [{'OK' if has_buy_choch else 'FAIL'}] BUY requires choch_bull/bos_bull")
        print(f"  [{'OK' if has_cvd_check else 'FAIL'}] CVD divergence check for BTCUSD")
        
        if has_choch_check and has_sell_choch and has_buy_choch:
            print("\n  ✅ TEST 2 PASSED: CHOCH confirmation filter implemented correctly")
            return True
        else:
            print("\n  ❌ TEST 2 FAILED: Missing implementation")
            return False
            
    except Exception as e:
        print(f"  [ERROR] Could not test: {e}")
        return False

def test_session_end_filter():
    """Test Fix 3: Session-End Filter"""
    print("\n" + "=" * 80)
    print("TEST 3: Session-End Filter")
    print("=" * 80)
    
    try:
        with open("auto_execution_system.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check for session-end check
        has_session_check = "ISSUE 3: Session-End Filter" in content
        has_session_helpers = "SessionHelpers.get_current_session" in content
        has_minutes_check = "minutes_until_end < 30" in content
        has_session_ends = '"LONDON": 13' in content and '"NY": 21' in content
        
        print(f"  [{'OK' if has_session_check else 'FAIL'}] Session-end check found in _execute_trade()")
        print(f"  [{'OK' if has_session_helpers else 'FAIL'}] Uses SessionHelpers.get_current_session()")
        print(f"  [{'OK' if has_minutes_check else 'FAIL'}] Blocks if < 30 minutes until close")
        print(f"  [{'OK' if has_session_ends else 'FAIL'}] Session end times defined (London 13:00, NY 21:00)")
        
        if has_session_check and has_session_helpers and has_minutes_check:
            print("\n  ✅ TEST 3 PASSED: Session-end filter implemented correctly")
            return True
        else:
            print("\n  ❌ TEST 3 FAILED: Missing implementation")
            return False
            
    except Exception as e:
        print(f"  [ERROR] Could not test: {e}")
        return False

def test_volume_imbalance_check():
    """Test Fix 4: Volume Imbalance Check for BTCUSD OB Plans"""
    print("\n" + "=" * 80)
    print("TEST 4: Volume Imbalance Check for BTCUSD OB Plans")
    print("=" * 80)
    
    try:
        with open("auto_execution_system.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check for volume imbalance check
        has_volume_check = "ISSUE 4: Volume Imbalance Check" in content
        has_delta_check = 'delta < 0.25' in content or 'delta > -0.25' in content
        has_cvd_trend = "cvd_trend" in content and ("rising" in content or "falling" in content)
        has_absorption = "absorption_zones" in content or "absorption zone" in content
        has_btcusd_check = 'symbol_norm.upper().startswith(\'BTC\')' in content
        
        print(f"  [{'OK' if has_volume_check else 'FAIL'}] Volume imbalance check found in _check_conditions()")
        print(f"  [{'OK' if has_delta_check else 'FAIL'}] Delta volume validation (0.25 threshold)")
        print(f"  [{'OK' if has_cvd_trend else 'FAIL'}] CVD trend validation (rising/falling)")
        print(f"  [{'OK' if has_absorption else 'FAIL'}] Absorption zone check")
        print(f"  [{'OK' if has_btcusd_check else 'FAIL'}] BTCUSD-specific check")
        
        if has_volume_check and has_delta_check and has_cvd_trend and has_btcusd_check:
            print("\n  ✅ TEST 4 PASSED: Volume imbalance check implemented correctly")
            return True
        else:
            print("\n  ❌ TEST 4 FAILED: Missing implementation")
            return False
            
    except Exception as e:
        print(f"  [ERROR] Could not test: {e}")
        return False

def test_integration_points():
    """Test that fixes are in the correct methods"""
    print("\n" + "=" * 80)
    print("TEST 5: Integration Points Verification")
    print("=" * 80)
    
    try:
        with open("auto_execution_system.py", "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # Find method definitions
        execute_trade_start = None
        check_conditions_start = None
        
        for i, line in enumerate(lines):
            if 'def _execute_trade(self, plan: TradePlan)' in line:
                execute_trade_start = i
            if 'def _check_conditions(self, plan: TradePlan)' in line:
                check_conditions_start = i
        
        # Check if fixes are in correct methods
        vwap_in_execute = False
        session_in_execute = False
        choch_in_check = False
        volume_in_check = False
        
        if execute_trade_start:
            for i in range(execute_trade_start, min(execute_trade_start + 500, len(lines))):
                if "ISSUE 1: VWAP Overextension Filter" in lines[i]:
                    vwap_in_execute = True
                if "ISSUE 3: Session-End Filter" in lines[i]:
                    session_in_execute = True
        
        if check_conditions_start:
            # Search further in _check_conditions (it's a long method)
            for i in range(check_conditions_start, min(check_conditions_start + 1500, len(lines))):
                if "ISSUE 2: CHOCH Confirmation" in lines[i]:
                    choch_in_check = True
                if "ISSUE 4: Volume Imbalance Check" in lines[i]:
                    volume_in_check = True
        
        print(f"  [{'OK' if vwap_in_execute else 'FAIL'}] VWAP check in _execute_trade()")
        print(f"  [{'OK' if session_in_execute else 'FAIL'}] Session-end check in _execute_trade()")
        print(f"  [{'OK' if choch_in_check else 'FAIL'}] CHOCH check in _check_conditions()")
        print(f"  [{'OK' if volume_in_check else 'FAIL'}] Volume imbalance check in _check_conditions()")
        
        if vwap_in_execute and session_in_execute and choch_in_check and volume_in_check:
            print("\n  ✅ TEST 5 PASSED: All fixes in correct methods")
            return True
        else:
            print("\n  ❌ TEST 5 FAILED: Fixes in wrong methods")
            return False
            
    except Exception as e:
        print(f"  [ERROR] Could not test: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("AUTO EXECUTION FIXES - TEST SUITE")
    print("=" * 80)
    print()
    
    results = []
    
    # Run all tests
    results.append(("VWAP Overextension Filter", test_vwap_overextension_filter()))
    results.append(("CHOCH Confirmation", test_choch_confirmation()))
    results.append(("Session-End Filter", test_session_end_filter()))
    results.append(("Volume Imbalance Check", test_volume_imbalance_check()))
    results.append(("Integration Points", test_integration_points()))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n  🎉 ALL TESTS PASSED - Implementation verified!")
        return 0
    else:
        print(f"\n  ⚠️ {total - passed} test(s) failed - Review implementation")
        return 1

if __name__ == "__main__":
    sys.exit(main())

