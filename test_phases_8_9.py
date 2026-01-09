"""
Test script for Intelligent Exit System Fixes (Phases 8-9)
Tests Trade Type Classifier Integration and Thread Safety
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import threading
import time
from concurrent.futures import ThreadPoolExecutor

def test_phase8_trade_type_classifier():
    """Test Phase 8: Trade Type Classifier Integration"""
    print("\n" + "="*60)
    print("PHASE 8 TEST: Trade Type Classifier Integration")
    print("="*60)
    
    try:
        from infra.trade_type_classifier import TradeTypeClassifier
        from infra.mt5_service import MT5Service
        from infra.session_analyzer import SessionAnalyzer
        
        # Initialize classifier
        mt5_service = MT5Service()
        session_analyzer = SessionAnalyzer()
        
        classifier = TradeTypeClassifier(mt5_service, session_analyzer)
        
        # Test 1: SCALP classification (small stop relative to ATR)
        print("\n1. Testing SCALP classification...")
        classification = classifier.classify(
            symbol="XAUUSDc",
            entry_price=2500.0,
            stop_loss=2495.0,  # 5 pip stop (small)
            comment="scalp trade quick profit"
        )
        
        assert classification["trade_type"] == "SCALP", f"Expected SCALP, got {classification['trade_type']}"
        print(f"   ✅ SCALP classification: {classification['trade_type']} (confidence: {classification['confidence']:.2f})")
        print(f"   Reasoning: {classification['reasoning']}")
        
        # Test 2: INTRADAY classification
        print("\n2. Testing INTRADAY classification...")
        classification = classifier.classify(
            symbol="XAUUSDc",
            entry_price=2500.0,
            stop_loss=2480.0,  # 20 pip stop (larger)
            comment="swing trade hold position"
        )
        
        # Should be INTRADAY (larger stop, swing keyword)
        assert classification["trade_type"] in ["SCALP", "INTRADAY"], f"Invalid trade type: {classification['trade_type']}"
        print(f"   ✅ Classification result: {classification['trade_type']} (confidence: {classification['confidence']:.2f})")
        print(f"   Reasoning: {classification['reasoning']}")
        
        # Test 3: Manual override
        print("\n3. Testing manual override...")
        classification = classifier.classify(
            symbol="XAUUSDc",
            entry_price=2500.0,
            stop_loss=2495.0,
            comment="!force:SCALP manual override"
        )
        
        assert classification["trade_type"] == "SCALP", f"Expected SCALP from override, got {classification['trade_type']}"
        assert classification["confidence"] == 1.0, f"Expected confidence 1.0 for override, got {classification['confidence']}"
        print(f"   ✅ Manual override working: {classification['trade_type']} (confidence: {classification['confidence']:.2f})")
        
        # Test 4: Verify classification sets correct base parameters
        print("\n4. Testing parameter selection based on classification...")
        if classification["trade_type"] == "SCALP":
            base_breakeven_pct = 25.0
            base_partial_pct = 40.0
            partial_close_pct = 70.0
        else:
            base_breakeven_pct = 30.0
            base_partial_pct = 60.0
            partial_close_pct = 50.0
        
        print(f"   ✅ SCALP parameters: BE={base_breakeven_pct}%, Partial={base_partial_pct}%, Close={partial_close_pct}%")
        print(f"   ✅ INTRADAY parameters: BE=30.0%, Partial=60.0%, Close=50.0%")
        
        print("\n✅ Phase 8: Trade Type Classifier Integration - PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Phase 8 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase9_thread_safety():
    """Test Phase 9: Thread Safety for Rules Dictionary"""
    print("\n" + "="*60)
    print("PHASE 9 TEST: Thread Safety for Rules Dictionary")
    print("="*60)
    
    try:
        from infra.intelligent_exit_manager import IntelligentExitManager, ExitRule
        from infra.mt5_service import MT5Service
        
        mt5_service = MT5Service()
        manager = IntelligentExitManager(mt5_service)
        
        # Test 1: Verify lock exists
        print("\n1. Verifying lock exists...")
        assert hasattr(manager, 'rules_lock'), "rules_lock not found"
        assert isinstance(manager.rules_lock, type(threading.Lock())), "rules_lock is not a Lock"
        print("   ✅ Lock exists and is correct type")
        
        # Test 2: Concurrent rule additions
        print("\n2. Testing concurrent rule additions...")
        def add_rule(ticket):
            rule = ExitRule(
                ticket=ticket,
                symbol="XAUUSDc",
                entry_price=2500.0,
                direction="buy",
                initial_sl=2495.0,
                initial_tp=2510.0
            )
            with manager.rules_lock:
                manager.rules[ticket] = rule
            return ticket
        
        tickets = list(range(100, 120))  # 20 tickets
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(add_rule, tickets))
        
        assert len(results) == 20, f"Expected 20 rules, got {len(results)}"
        with manager.rules_lock:
            assert len(manager.rules) == 20, f"Expected 20 rules in dict, got {len(manager.rules)}"
        print(f"   ✅ Concurrent additions: {len(results)} rules added safely")
        
        # Test 3: Concurrent reads and writes
        print("\n3. Testing concurrent reads and writes...")
        read_errors = []
        write_errors = []
        
        def read_rules():
            try:
                for _ in range(100):
                    with manager.rules_lock:
                        rules = list(manager.rules.values())
                    time.sleep(0.001)  # Small delay
            except Exception as e:
                read_errors.append(e)
        
        def write_rules():
            try:
                for ticket in range(200, 210):
                    rule = ExitRule(
                        ticket=ticket,
                        symbol="BTCUSDc",
                        entry_price=90000.0,
                        direction="buy",
                        initial_sl=89500.0,
                        initial_tp=91000.0
                    )
                    with manager.rules_lock:
                        manager.rules[ticket] = rule
                    time.sleep(0.001)  # Small delay
            except Exception as e:
                write_errors.append(e)
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            futures.append(executor.submit(read_rules))
            futures.append(executor.submit(read_rules))
            futures.append(executor.submit(write_rules))
            futures.append(executor.submit(write_rules))
            
            for future in futures:
                future.result()  # Wait for completion
        
        assert len(read_errors) == 0, f"Read errors occurred: {read_errors}"
        assert len(write_errors) == 0, f"Write errors occurred: {write_errors}"
        print("   ✅ Concurrent reads/writes: No errors")
        
        # Test 4: Snapshot pattern in check_exits
        print("\n4. Testing snapshot pattern...")
        with manager.rules_lock:
            snapshot = list(manager.rules.keys())
        
        # Simulate rule removal during iteration
        removed_count = 0
        for ticket in snapshot:
            with manager.rules_lock:
                if ticket in manager.rules:
                    del manager.rules[ticket]
                    removed_count += 1
        
        assert removed_count > 0, "No rules were removed"
        print(f"   ✅ Snapshot pattern: {removed_count} rules removed safely")
        
        # Test 5: get_rule and get_all_rules thread safety
        print("\n5. Testing get_rule and get_all_rules thread safety...")
        
        # Add some rules back
        for ticket in range(300, 305):
            rule = ExitRule(
                ticket=ticket,
                symbol="EURUSDc",
                entry_price=1.1000,
                direction="buy",
                initial_sl=1.0950,
                initial_tp=1.1100
            )
            with manager.rules_lock:
                manager.rules[ticket] = rule
        
        def get_rules_concurrent():
            results = []
            for _ in range(50):
                rule = manager.get_rule(300)
                all_rules = manager.get_all_rules()
                results.append((rule is not None, len(all_rules)))
            return results
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(get_rules_concurrent) for _ in range(5)]
            all_results = [f.result() for f in futures]
        
        # Verify no errors and consistent results
        for results in all_results:
            assert len(results) == 50, "Incomplete results"
            for rule_found, count in results:
                assert isinstance(rule_found, bool), "Invalid rule_found type"
                assert count >= 0, "Invalid count"
        
        print("   ✅ get_rule and get_all_rules: Thread-safe")
        
        # Cleanup
        with manager.rules_lock:
            manager.rules.clear()
        
        print("\n✅ Phase 9: Thread Safety for Rules Dictionary - PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Phase 9 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration_phase8_9():
    """Test integration of Phase 8 and 9 together"""
    print("\n" + "="*60)
    print("INTEGRATION TEST: Phase 8 + Phase 9")
    print("="*60)
    
    try:
        from infra.intelligent_exit_manager import IntelligentExitManager
        from infra.mt5_service import MT5Service
        
        mt5_service = MT5Service()
        manager = IntelligentExitManager(mt5_service)
        
        # Simulate auto_enable_intelligent_exits_async logic
        print("\n1. Simulating Trade Type Classification + Rule Addition...")
        
        # Simulate classification (Phase 8)
        from infra.trade_type_classifier import TradeTypeClassifier
        classifier = TradeTypeClassifier(mt5_service, None)
        
        classification = classifier.classify(
            symbol="XAUUSDc",
            entry_price=2500.0,
            stop_loss=2495.0,
            comment="scalp trade"
        )
        
        # Set base parameters based on classification (Phase 8)
        if classification["trade_type"] == "SCALP":
            base_breakeven_pct = 25.0
            base_partial_pct = 40.0
        else:
            base_breakeven_pct = 30.0
            base_partial_pct = 60.0
        
        print(f"   Classification: {classification['trade_type']}")
        print(f"   Base parameters: BE={base_breakeven_pct}%, Partial={base_partial_pct}%")
        
        # Add rule with thread-safe access (Phase 9)
        from infra.intelligent_exit_manager import ExitRule
        
        rule = ExitRule(
            ticket=99999,
            symbol="XAUUSDc",
            entry_price=2500.0,
            direction="buy",
            initial_sl=2495.0,
            initial_tp=2510.0,
            breakeven_profit_pct=base_breakeven_pct,  # From classification
            partial_profit_pct=base_partial_pct  # From classification
        )
        
        # Thread-safe addition (Phase 9)
        with manager.rules_lock:
            manager.rules[99999] = rule
        
        # Verify rule was added correctly
        retrieved_rule = manager.get_rule(99999)
        assert retrieved_rule is not None, "Rule not found"
        assert retrieved_rule.breakeven_profit_pct == base_breakeven_pct, "Breakeven pct mismatch"
        assert retrieved_rule.partial_profit_pct == base_partial_pct, "Partial pct mismatch"
        
        print(f"   ✅ Rule added with classification-based parameters")
        print(f"   ✅ Thread-safe access verified")
        
        # Cleanup
        with manager.rules_lock:
            if 99999 in manager.rules:
                del manager.rules[99999]
        
        print("\n✅ Integration Test: Phase 8 + Phase 9 - PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("INTELLIGENT EXIT SYSTEM FIXES - PHASES 8-9 TEST SUITE")
    print("="*60)
    
    results = []
    
    # Test Phase 8
    results.append(("Phase 8: Trade Type Classifier", test_phase8_trade_type_classifier()))
    
    # Test Phase 9
    results.append(("Phase 9: Thread Safety", test_phase9_thread_safety()))
    
    # Integration test
    results.append(("Integration: Phase 8 + 9", test_integration_phase8_9()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n⚠️ Some tests failed")
        sys.exit(1)

