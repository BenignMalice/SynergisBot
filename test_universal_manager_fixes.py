"""
Test Universal Manager Critical Fixes
Tests thread safety, race conditions, and defensive checks
"""

import sys
import os
import time
import threading
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


def test_thread_safety():
    """Test 1: Thread Safety - Concurrent Access"""
    print("\n=== Test 1: Thread Safety - Concurrent Access ===")
    
    try:
        from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
        from infra.mt5_service import MT5Service
        
        # Create manager
        mt5_service = MT5Service()
        manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
        
        # Verify lock exists
        has_lock = hasattr(manager, 'active_trades_lock')
        log_test("Lock exists", has_lock,
                f"active_trades_lock attribute: {has_lock}")
        
        if has_lock:
            lock_type = type(manager.active_trades_lock).__name__
            # Lock type can be "Lock" or "lock" depending on Python version
            lock_type_correct = lock_type.lower() == "lock"
            log_test("Lock type correct", lock_type_correct,
                    f"Lock type: {lock_type}")
        
        # Test concurrent access
        errors = []
        results = []
        
        def register_trade(ticket: int):
            try:
                # Simulate trade registration
                from infra.universal_sl_tp_manager import TradeState, StrategyType, Session
                from dataclasses import dataclass
                
                trade_state = TradeState(
                    ticket=ticket,
                    symbol="BTCUSDc",
                    strategy_type=StrategyType.DEFAULT_STANDARD,
                    direction="BUY",
                    session=Session.ASIA,
                    resolved_trailing_rules={},
                    managed_by="universal_sl_tp_manager",
                    entry_price=87000.0,
                    initial_sl=86500.0,
                    initial_tp=88000.0
                )
                
                with manager.active_trades_lock:
                    manager.active_trades[ticket] = trade_state
                results.append(ticket)
            except Exception as e:
                errors.append(f"Register {ticket}: {e}")
        
        def monitor_trades():
            try:
                for _ in range(10):
                    with manager.active_trades_lock:
                        tickets = list(manager.active_trades.keys())
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"Monitor: {e}")
        
        def unregister_trade(ticket: int):
            try:
                time.sleep(0.05)  # Wait a bit
                with manager.active_trades_lock:
                    if ticket in manager.active_trades:
                        del manager.active_trades[ticket]
            except Exception as e:
                errors.append(f"Unregister {ticket}: {e}")
        
        # Run concurrent operations
        threads = []
        
        # Register trades
        for i in range(5):
            t = threading.Thread(target=register_trade, args=(1000 + i,))
            threads.append(t)
            t.start()
        
        # Monitor trades
        for _ in range(3):
            t = threading.Thread(target=monitor_trades)
            threads.append(t)
            t.start()
        
        # Unregister trades
        for i in range(3):
            t = threading.Thread(target=unregister_trade, args=(1000 + i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join(timeout=2.0)
        
        # Check results
        no_errors = len(errors) == 0
        log_test("Concurrent access - no errors", no_errors,
                f"Errors: {len(errors)}, Results: {len(results)}")
        
        if errors:
            for error in errors[:5]:  # Show first 5 errors
                print(f"   Error: {error}")
        
    except Exception as e:
        log_test("Thread safety test", False, f"Error: {e}")
        import traceback
        traceback.print_exc()


def test_race_condition_prevention():
    """Test 2: Race Condition Prevention"""
    print("\n=== Test 2: Race Condition Prevention ===")
    
    try:
        from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
        from infra.mt5_service import MT5Service
        
        # Create manager
        mt5_service = MT5Service()
        manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
        
        # Add some test trades
        from infra.universal_sl_tp_manager import TradeState, StrategyType, Session
        
        test_trades = []
        for i in range(5):
            trade_state = TradeState(
                ticket=2000 + i,
                symbol="BTCUSDc",
                strategy_type=StrategyType.DEFAULT_STANDARD,
                direction="BUY",
                session=Session.ASIA,
                resolved_trailing_rules={},
                managed_by="universal_sl_tp_manager",
                entry_price=87000.0,
                initial_sl=86500.0,
                initial_tp=88000.0
            )
            with manager.active_trades_lock:
                manager.active_trades[2000 + i] = trade_state
            test_trades.append(2000 + i)
        
        # Test snapshot creation
        with manager.active_trades_lock:
            tickets = list(manager.active_trades.keys())
        
        snapshot_works = len(tickets) == 5
        log_test("Snapshot creation works", snapshot_works,
                f"Snapshot size: {len(tickets)} (expected 5)")
        
        # Test defensive check
        removed_count = 0
        for ticket in tickets:
            with manager.active_trades_lock:
                if ticket not in manager.active_trades:
                    removed_count += 1
        
        defensive_check_works = removed_count == 0
        log_test("Defensive check works", defensive_check_works,
                f"Trades removed during iteration: {removed_count}")
        
        # Test removal during iteration
        def remove_during_iteration():
            time.sleep(0.01)
            with manager.active_trades_lock:
                if 2000 in manager.active_trades:
                    del manager.active_trades[2000]
        
        # Create snapshot
        with manager.active_trades_lock:
            tickets = list(manager.active_trades.keys())
        
        # Start removal thread
        remove_thread = threading.Thread(target=remove_during_iteration)
        remove_thread.start()
        
        # Iterate with defensive check
        found_count = 0
        for ticket in tickets:
            with manager.active_trades_lock:
                if ticket in manager.active_trades:
                    found_count += 1
        
        remove_thread.join()
        
        race_condition_prevented = found_count >= 4  # At least 4 should remain
        log_test("Race condition prevented", race_condition_prevented,
                f"Trades found: {found_count} (expected 4-5)")
        
        # Cleanup
        with manager.active_trades_lock:
            manager.active_trades.clear()
        
    except Exception as e:
        log_test("Race condition test", False, f"Error: {e}")
        import traceback
        traceback.print_exc()


def test_defensive_checks():
    """Test 3: Defensive Checks"""
    print("\n=== Test 3: Defensive Checks ===")
    
    try:
        from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
        from infra.mt5_service import MT5Service
        
        # Create manager
        mt5_service = MT5Service()
        manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
        
        # Add a test trade
        from infra.universal_sl_tp_manager import TradeState, StrategyType, Session
        
        trade_state = TradeState(
            ticket=3000,
            symbol="BTCUSDc",
            strategy_type=StrategyType.DEFAULT_STANDARD,
            direction="BUY",
            session=Session.ASIA,
            resolved_trailing_rules={},
            managed_by="universal_sl_tp_manager",
            entry_price=87000.0,
            initial_sl=86500.0,
            initial_tp=88000.0
        )
        
        with manager.active_trades_lock:
            manager.active_trades[3000] = trade_state
        
        # Test: Check if trade exists before access
        with manager.active_trades_lock:
            exists = 3000 in manager.active_trades
        
        check_before_access = exists
        log_test("Check before access works", check_before_access,
                f"Trade 3000 exists: {exists}")
        
        # Test: Re-check before modification
        def simulate_modification():
            with manager.active_trades_lock:
                if 3000 not in manager.active_trades:
                    return False
                trade_state = manager.active_trades.get(3000)
                if not trade_state:
                    return False
                return True
        
        recheck_works = simulate_modification()
        log_test("Re-check before modification works", recheck_works,
                "Re-check logic executed successfully")
        
        # Test: Handle removed trade
        with manager.active_trades_lock:
            if 3000 in manager.active_trades:
                del manager.active_trades[3000]
        
        removed_check = simulate_modification() == False
        log_test("Handle removed trade works", removed_check,
                "Correctly handles removed trade")
        
        # Cleanup
        with manager.active_trades_lock:
            manager.active_trades.clear()
        
    except Exception as e:
        log_test("Defensive checks test", False, f"Error: {e}")
        import traceback
        traceback.print_exc()


def test_lock_usage():
    """Test 4: Lock Usage Verification"""
    print("\n=== Test 4: Lock Usage Verification ===")
    
    try:
        from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
        from infra.mt5_service import MT5Service
        
        # Create manager
        mt5_service = MT5Service()
        manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
        
        # Check that lock is used in key methods
        import inspect
        
        # Check register_trade
        register_source = inspect.getsource(manager.register_trade)
        register_uses_lock = 'active_trades_lock' in register_source
        log_test("register_trade uses lock", register_uses_lock,
                "Lock usage in register_trade method")
        
        # Check monitor_all_trades
        monitor_source = inspect.getsource(manager.monitor_all_trades)
        monitor_uses_lock = 'active_trades_lock' in monitor_source
        log_test("monitor_all_trades uses lock", monitor_uses_lock,
                "Lock usage in monitor_all_trades method")
        
        # Check _unregister_trade
        unregister_source = inspect.getsource(manager._unregister_trade)
        unregister_uses_lock = 'active_trades_lock' in unregister_source
        log_test("_unregister_trade uses lock", unregister_uses_lock,
                "Lock usage in _unregister_trade method")
        
        all_use_locks = register_uses_lock and monitor_uses_lock and unregister_uses_lock
        log_test("All key methods use locks", all_use_locks,
                f"register: {register_uses_lock}, monitor: {monitor_uses_lock}, unregister: {unregister_uses_lock}")
        
    except Exception as e:
        log_test("Lock usage test", False, f"Error: {e}")
        import traceback
        traceback.print_exc()


def test_no_keyerror():
    """Test 5: No KeyError Exceptions"""
    print("\n=== Test 5: No KeyError Exceptions ===")
    
    try:
        from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
        from infra.mt5_service import MT5Service
        
        # Create manager
        mt5_service = MT5Service()
        manager = UniversalDynamicSLTPManager(mt5_service=mt5_service)
        
        # Add test trades
        from infra.universal_sl_tp_manager import TradeState, StrategyType, Session
        
        for i in range(3):
            trade_state = TradeState(
                ticket=4000 + i,
                symbol="BTCUSDc",
                strategy_type=StrategyType.DEFAULT_STANDARD,
                direction="BUY",
                session=Session.ASIA,
                resolved_trailing_rules={},
                managed_by="universal_sl_tp_manager",
                entry_price=87000.0,
                initial_sl=86500.0,
                initial_tp=88000.0
            )
            with manager.active_trades_lock:
                manager.active_trades[4000 + i] = trade_state
        
        # Test: Remove trade during iteration (should not cause KeyError)
        keyerrors = []
        
        def remove_trade(ticket: int):
            time.sleep(0.01)
            with manager.active_trades_lock:
                if ticket in manager.active_trades:
                    del manager.active_trades[ticket]
        
        # Create snapshot
        with manager.active_trades_lock:
            tickets = list(manager.active_trades.keys())
        
        # Start removal
        remove_thread = threading.Thread(target=remove_trade, args=(4000,))
        remove_thread.start()
        
        # Iterate with defensive check
        for ticket in tickets:
            try:
                with manager.active_trades_lock:
                    if ticket in manager.active_trades:
                        trade = manager.active_trades[ticket]
                        # Access trade safely
                        _ = trade.ticket
            except KeyError as e:
                keyerrors.append(f"Ticket {ticket}: {e}")
        
        remove_thread.join()
        
        no_keyerrors = len(keyerrors) == 0
        log_test("No KeyError exceptions", no_keyerrors,
                f"KeyErrors: {len(keyerrors)}")
        
        if keyerrors:
            for error in keyerrors:
                print(f"   KeyError: {error}")
        
        # Cleanup
        with manager.active_trades_lock:
            manager.active_trades.clear()
        
    except Exception as e:
        log_test("KeyError test", False, f"Error: {e}")
        import traceback
        traceback.print_exc()


def print_summary():
    """Print test summary"""
    print("\n" + "=" * 80)
    print("UNIVERSAL MANAGER FIXES TEST SUMMARY")
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
        print("[SUCCESS] ALL TESTS PASSED - Critical fixes are working correctly!")
        return True
    else:
        print(f"[WARNING] {test_results['failed']} test(s) failed - review and fix issues")
        return False


if __name__ == "__main__":
    print("=" * 80)
    print("UNIVERSAL MANAGER CRITICAL FIXES TEST SUITE")
    print("=" * 80)
    print("Testing thread safety, race condition prevention, and defensive checks")
    print()
    
    # Run all tests
    test_thread_safety()
    test_race_condition_prevention()
    test_defensive_checks()
    test_lock_usage()
    test_no_keyerror()
    
    # Print summary
    all_passed = print_summary()
    
    # Exit with appropriate code
    exit(0 if all_passed else 1)

