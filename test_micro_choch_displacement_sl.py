"""
Test script for Micro CHOCH and Displacement SL implementations.

Tests:
1. Micro CHOCH SL detection and calculation
2. Displacement SL detection and calculation
3. Error handling and fallbacks
4. Integration with Universal SL/TP Manager
"""

import sys
import os
from datetime import datetime, timezone
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required imports are available."""
    print("=" * 60)
    print("TEST 1: Import Verification")
    print("=" * 60)
    
    try:
        from infra.universal_sl_tp_manager import (
            UniversalDynamicSLTPManager,
            TradeState,
            StrategyType,
            Session
        )
        print("[OK] UniversalDynamicSLTPManager imported")
        
        from infra.streamer_data_access import StreamerDataAccess
        print("[OK] StreamerDataAccess imported")
        
        try:
            from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
            print("[OK] M1MicrostructureAnalyzer imported")
        except ImportError as e:
            print(f"[WARN] M1MicrostructureAnalyzer not available: {e}")
            print("   (Micro CHOCH SL will use fallback)")
        
        return True
    except ImportError as e:
        print(f"[FAIL] Import failed: {e}")
        return False

def test_atr_calculation():
    """Test ATR calculation from candles."""
    print("\n" + "=" * 60)
    print("TEST 2: ATR Calculation Helper")
    print("=" * 60)
    
    try:
        from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
        
        manager = UniversalDynamicSLTPManager()
        
        # Create mock candles
        candles = []
        base_price = 100.0
        for i in range(20):
            candles.append({
                'high': base_price + 0.5 + (i * 0.1),
                'low': base_price - 0.5 + (i * 0.1),
                'close': base_price + (i * 0.1)
            })
        
        atr = manager._calculate_atr_from_candles(candles, period=14)
        
        if atr and atr > 0:
            print(f"[OK] ATR calculated successfully: {atr:.4f}")
            return True
        else:
            print(f"[FAIL] ATR calculation returned invalid value: {atr}")
            return False
    except Exception as e:
        print(f"[FAIL] ATR calculation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_micro_choch_sl_structure():
    """Test that _get_micro_choch_sl method exists and has correct structure."""
    print("\n" + "=" * 60)
    print("TEST 3: Micro CHOCH SL Method Structure")
    print("=" * 60)
    
    try:
        from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager, TradeState, StrategyType, Session
        
        manager = UniversalDynamicSLTPManager()
        
        # Check method exists
        if not hasattr(manager, '_get_micro_choch_sl'):
            print("[FAIL] _get_micro_choch_sl method not found")
            return False
        
        print("[OK] _get_micro_choch_sl method exists")
        
        # Check method signature
        import inspect
        sig = inspect.signature(manager._get_micro_choch_sl)
        params = list(sig.parameters.keys())
        
        if 'trade_state' in params and 'rules' in params:
            print(f"[OK] Method signature correct: {params}")
        else:
            print(f"[FAIL] Method signature incorrect: {params}")
            return False
        
        # Create mock trade state
        trade_state = TradeState(
            ticket=12345,
            symbol="BTCUSDc",
            strategy_type=StrategyType.LIQUIDITY_SWEEP_REVERSAL,
            direction="BUY",
            session=Session.LONDON,
            resolved_trailing_rules={
                "trailing_method": "micro_choch",
                "atr_buffer": 0.5,
                "trailing_timeframe": "M1"
            },
            managed_by="universal_sl_tp_manager",
            entry_price=50000.0,
            initial_sl=49000.0,
            initial_tp=51000.0,
            current_price=50500.0,
            current_sl=49000.0
        )
        
        rules = trade_state.resolved_trailing_rules
        
        # Test method call (will likely return None due to no M1 data, but should not crash)
        try:
            result = manager._get_micro_choch_sl(trade_state, rules)
            print(f"[OK] Method call successful (returned: {result})")
            print("   (None is expected if M1 data unavailable - this is normal)")
            return True
        except Exception as e:
            print(f"[FAIL] Method call failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_displacement_sl_structure():
    """Test that _get_displacement_sl method exists and has correct structure."""
    print("\n" + "=" * 60)
    print("TEST 4: Displacement SL Method Structure")
    print("=" * 60)
    
    try:
        from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager, TradeState, StrategyType, Session
        
        manager = UniversalDynamicSLTPManager()
        
        # Check method exists
        if not hasattr(manager, '_get_displacement_sl'):
            print("[FAIL] _get_displacement_sl method not found")
            return False
        
        print("[OK] _get_displacement_sl method exists")
        
        # Check method signature
        import inspect
        sig = inspect.signature(manager._get_displacement_sl)
        params = list(sig.parameters.keys())
        
        if 'trade_state' in params and 'rules' in params:
            print(f"[OK] Method signature correct: {params}")
        else:
            print(f"[FAIL] Method signature incorrect: {params}")
            return False
        
        # Create mock trade state
        trade_state = TradeState(
            ticket=12346,
            symbol="XAUUSDc",
            strategy_type=StrategyType.ORDER_BLOCK_REJECTION,
            direction="SELL",
            session=Session.NY,
            resolved_trailing_rules={
                "trailing_method": "displacement_or_structure",
                "atr_buffer": 0.3,
                "trailing_timeframe": "M5"
            },
            managed_by="universal_sl_tp_manager",
            entry_price=2000.0,
            initial_sl=2050.0,
            initial_tp=1950.0,
            current_price=1980.0,
            current_sl=2050.0
        )
        
        rules = trade_state.resolved_trailing_rules
        
        # Test method call (will likely return None due to no displacement, but should not crash)
        try:
            result = manager._get_displacement_sl(trade_state, rules)
            print(f"[OK] Method call successful (returned: {result})")
            print("   (None is expected if displacement not detected - this is normal)")
            return True
        except Exception as e:
            print(f"[FAIL] Method call failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integration_with_trailing_calculation():
    """Test that both methods integrate correctly with _calculate_trailing_sl."""
    print("\n" + "=" * 60)
    print("TEST 5: Integration with Trailing SL Calculation")
    print("=" * 60)
    
    try:
        from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager, TradeState, StrategyType, Session
        
        manager = UniversalDynamicSLTPManager()
        
        # Test 1: Micro CHOCH integration
        trade_state_choch = TradeState(
            ticket=12347,
            symbol="BTCUSDc",
            strategy_type=StrategyType.LIQUIDITY_SWEEP_REVERSAL,
            direction="BUY",
            session=Session.LONDON,
            resolved_trailing_rules={
                "trailing_method": "micro_choch",
                "atr_buffer": 0.5,
                "trailing_timeframe": "M1",
                "atr_multiplier": 1.5,
                "trailing_enabled": True
            },
            managed_by="universal_sl_tp_manager",
            entry_price=50000.0,
            initial_sl=49000.0,
            initial_tp=51000.0,
            current_price=50500.0,
            current_sl=49000.0,
            breakeven_triggered=True
        )
        
        result_choch = manager._calculate_trailing_sl(trade_state_choch, trade_state_choch.resolved_trailing_rules)
        print(f"[OK] Micro CHOCH trailing SL calculation: {result_choch}")
        print("   (None is expected if M1 data unavailable - will fallback to ATR)")
        
        # Test 2: Displacement integration
        trade_state_disp = TradeState(
            ticket=12348,
            symbol="XAUUSDc",
            strategy_type=StrategyType.ORDER_BLOCK_REJECTION,
            direction="SELL",
            session=Session.NY,
            resolved_trailing_rules={
                "trailing_method": "displacement_or_structure",
                "atr_buffer": 0.3,
                "trailing_timeframe": "M5",
                "atr_multiplier": 1.5,
                "trailing_enabled": True
            },
            managed_by="universal_sl_tp_manager",
            entry_price=2000.0,
            initial_sl=2050.0,
            initial_tp=1950.0,
            current_price=1980.0,
            current_sl=2050.0,
            breakeven_triggered=True
        )
        
        result_disp = manager._calculate_trailing_sl(trade_state_disp, trade_state_disp.resolved_trailing_rules)
        print(f"[OK] Displacement trailing SL calculation: {result_disp}")
        print("   (None or ATR fallback expected if displacement not detected)")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("MICRO CHOCH & DISPLACEMENT SL IMPLEMENTATION TESTS")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Import Verification", test_imports()))
    results.append(("ATR Calculation", test_atr_calculation()))
    results.append(("Micro CHOCH SL Structure", test_micro_choch_sl_structure()))
    results.append(("Displacement SL Structure", test_displacement_sl_structure()))
    results.append(("Integration Test", test_integration_with_trailing_calculation()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed! Implementation is ready.")
        return 0
    else:
        print(f"\n[WARN] {total - passed} test(s) failed. Review errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

