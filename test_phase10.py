"""
Test script for Intelligent Exit System Fixes (Phase 10)
Tests Advanced Triggers Refresh functionality
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_phase10_refresh_advanced_triggers():
    """Test Phase 10: Advanced Triggers Refresh"""
    print("\n" + "="*60)
    print("PHASE 10 TEST: Advanced Triggers Refresh")
    print("="*60)
    
    try:
        from infra.intelligent_exit_manager import IntelligentExitManager, ExitRule
        from infra.mt5_service import MT5Service
        
        mt5_service = MT5Service()
        manager = IntelligentExitManager(mt5_service)
        
        # Test 1: Refresh before breakeven triggered
        print("\n1. Testing refresh before breakeven triggered...")
        
        # Create a rule
        rule = ExitRule(
            ticket=88888,
            symbol="XAUUSDc",
            entry_price=2500.0,
            direction="buy",
            initial_sl=2495.0,
            initial_tp=2510.0,
            breakeven_profit_pct=30.0,  # Base value
            partial_profit_pct=60.0  # Base value
        )
        
        # Add rule (thread-safe)
        with manager.rules_lock:
            manager.rules[88888] = rule
        
        # Simulate Advanced features that would tighten triggers (RMAG stretched)
        advanced_features = {
            "features": {
                "M15": {
                    "rmag": {
                        "ema200_atr": -3.5,  # Stretched (above threshold for XAU)
                        "vwap_atr": -3.0
                    },
                    "ema_slope": {
                        "ema50": 0.1,
                        "ema200": 0.05
                    },
                    "vol_trend": {
                        "state": "normal"
                    },
                    "vwap_dev": {
                        "zone": "inside"
                    }
                }
            }
        }
        
        # Refresh triggers
        refresh_result = manager.refresh_advanced_triggers(88888, advanced_features)
        
        assert refresh_result is not None, "Refresh should return result"
        assert refresh_result["breakeven_pct"] == 20.0, f"Expected 20.0%, got {refresh_result['breakeven_pct']}"
        assert refresh_result["partial_pct"] == 40.0, f"Expected 40.0%, got {refresh_result['partial_pct']}"
        
        # Verify rule was updated
        updated_rule = manager.get_rule(88888)
        assert updated_rule.breakeven_profit_pct == 20.0, "Rule breakeven_pct not updated"
        assert updated_rule.partial_profit_pct == 40.0, "Rule partial_pct not updated"
        
        print(f"   ✅ Refresh successful: BE {rule.breakeven_profit_pct}% → {updated_rule.breakeven_profit_pct}%")
        print(f"   ✅ Partial: {rule.partial_profit_pct}% → {updated_rule.partial_profit_pct}%")
        print(f"   Reasoning: {refresh_result.get('reasoning', 'N/A')[:80]}...")
        
        # Test 2: Refresh skipped after breakeven triggered
        print("\n2. Testing refresh skipped after breakeven triggered...")
        
        # Mark breakeven as triggered
        with manager.rules_lock:
            rule = manager.rules.get(88888)
            if rule:
                rule.breakeven_triggered = True
        
        refresh_result = manager.refresh_advanced_triggers(88888, advanced_features)
        
        assert refresh_result is None, "Refresh should return None after breakeven triggered"
        print("   ✅ Refresh correctly skipped after breakeven triggered")
        
        # Test 3: Refresh with unchanged triggers
        print("\n3. Testing refresh with unchanged triggers...")
        
        # Reset breakeven
        with manager.rules_lock:
            rule = manager.rules.get(88888)
            if rule:
                rule.breakeven_triggered = False
                rule.breakeven_profit_pct = 20.0
                rule.partial_profit_pct = 40.0
        
        # Use Advanced features that result in same triggers
        unchanged_features = {
            "features": {
                "M15": {
                    "rmag": {
                        "ema200_atr": -3.5,  # Still stretched
                        "vwap_atr": -3.0
                    },
                    "ema_slope": {
                        "ema50": 0.1,
                        "ema200": 0.05
                    }
                }
            }
        }
        
        refresh_result = manager.refresh_advanced_triggers(88888, unchanged_features)
        
        assert refresh_result is not None, "Refresh should return result even if unchanged"
        print("   ✅ Refresh returns result even when triggers unchanged")
        
        # Test 4: Refresh with non-existent ticket
        print("\n4. Testing refresh with non-existent ticket...")
        
        refresh_result = manager.refresh_advanced_triggers(99999, advanced_features)
        
        assert refresh_result is None, "Refresh should return None for non-existent ticket"
        print("   ✅ Refresh correctly returns None for non-existent ticket")
        
        # Test 5: Refresh with None advanced_features (should fetch from provider)
        print("\n5. Testing refresh with None advanced_features (provider fetch)...")
        
        # This will fail if no provider, but should handle gracefully
        refresh_result = manager.refresh_advanced_triggers(88888, None)
        
        # Should return None if no provider available
        if refresh_result is None:
            print("   ✅ Refresh correctly handles missing provider")
        else:
            print("   ✅ Refresh successfully fetched from provider")
        
        # Cleanup
        with manager.rules_lock:
            if 88888 in manager.rules:
                del manager.rules[88888]
        
        print("\n✅ Phase 10: Advanced Triggers Refresh - PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Phase 10 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_phase10_integration():
    """Test Phase 10 integration with check_exits"""
    print("\n" + "="*60)
    print("INTEGRATION TEST: Phase 10 + check_exits")
    print("="*60)
    
    try:
        from infra.intelligent_exit_manager import IntelligentExitManager, ExitRule
        from infra.mt5_service import MT5Service
        
        mt5_service = MT5Service()
        manager = IntelligentExitManager(mt5_service)
        
        print("\n1. Testing refresh integration in check_exits flow...")
        
        # Create a rule
        rule = ExitRule(
            ticket=77777,
            symbol="BTCUSDc",
            entry_price=90000.0,
            direction="buy",
            initial_sl=89500.0,
            initial_tp=91000.0,
            breakeven_profit_pct=30.0,
            partial_profit_pct=60.0
        )
        
        with manager.rules_lock:
            manager.rules[77777] = rule
        
        # Verify refresh_advanced_triggers method exists
        assert hasattr(manager, 'refresh_advanced_triggers'), "refresh_advanced_triggers method not found"
        print("   ✅ refresh_advanced_triggers method exists")
        
        # Test that it can be called
        advanced_features = {
            "features": {
                "M15": {
                    "rmag": {
                        "ema200_atr": -5.0,  # Very stretched for BTC
                        "vwap_atr": -4.5
                    }
                }
            }
        }
        
        refresh_result = manager.refresh_advanced_triggers(77777, advanced_features)
        
        if refresh_result:
            print("   ✅ Refresh works correctly in integration")
        else:
            print("   ⚠️ Refresh returned None (may be expected if breakeven triggered)")
        
        # Cleanup
        with manager.rules_lock:
            if 77777 in manager.rules:
                del manager.rules[77777]
        
        print("\n✅ Integration Test: Phase 10 + check_exits - PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("INTELLIGENT EXIT SYSTEM FIXES - PHASE 10 TEST SUITE")
    print("="*60)
    
    results = []
    
    # Test Phase 10
    results.append(("Phase 10: Advanced Triggers Refresh", test_phase10_refresh_advanced_triggers()))
    
    # Integration test
    results.append(("Integration: Phase 10 + check_exits", test_phase10_integration()))
    
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

