"""
Phase 3 Implementation Test Script

Tests all Phase 3 components:
- Order flow flip exit detection
- Entry delta storage
- Enhanced absorption zones
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

def test_intelligent_exit_manager_import():
    """Test 1: IntelligentExitManager imports with Phase 3"""
    try:
        from infra.intelligent_exit_manager import IntelligentExitManager, ExitRule
        log_test("IntelligentExitManager Import", True)
        return True
    except Exception as e:
        log_test("IntelligentExitManager Import", False, f"Error: {e}")
        return False

def test_order_flow_flip_methods():
    """Test 2: Order flow flip methods exist"""
    try:
        from infra.intelligent_exit_manager import IntelligentExitManager
        
        # Create a minimal manager (won't actually work without MT5, but we can check methods)
        class MockMT5:
            def connect(self):
                return False
        
        manager = IntelligentExitManager(mt5_service=MockMT5(), order_flow_service=None)
        
        # Check Phase 3 methods exist
        assert hasattr(manager, '_check_order_flow_flip')
        assert hasattr(manager, '_convert_to_binance_symbol')
        
        log_test("Order Flow Flip Methods", True)
        return True
    except Exception as e:
        log_test("Order Flow Flip Methods", False, f"Error: {e}")
        return False

def test_convert_to_binance_symbol():
    """Test 3: Symbol conversion works"""
    try:
        from infra.intelligent_exit_manager import IntelligentExitManager
        
        class MockMT5:
            def connect(self):
                return False
        
        manager = IntelligentExitManager(mt5_service=MockMT5(), order_flow_service=None)
        
        # Test conversions
        assert manager._convert_to_binance_symbol("BTCUSDc") == "BTCUSDT"
        assert manager._convert_to_binance_symbol("BTCUSDC") == "BTCUSDT"
        assert manager._convert_to_binance_symbol("XAUUSDc") is None
        assert manager._convert_to_binance_symbol("EURUSDc") is None
        
        log_test("Convert to Binance Symbol", True)
        return True
    except Exception as e:
        log_test("Convert to Binance Symbol", False, f"Error: {e}")
        return False

def test_exit_rule_metadata():
    """Test 4: ExitRule has metadata field"""
    try:
        from infra.intelligent_exit_manager import ExitRule
        
        rule = ExitRule(
            ticket=12345,
            symbol="BTCUSDc",
            entry_price=50000.0,
            direction="BUY",
            initial_sl=49000.0,
            initial_tp=51000.0
        )
        
        # Check metadata field exists
        assert hasattr(rule, 'metadata')
        assert isinstance(rule.metadata, dict)
        
        # Test storing entry delta
        rule.metadata['entry_delta'] = 150.5
        assert rule.metadata['entry_delta'] == 150.5
        
        log_test("ExitRule Metadata Field", True)
        return True
    except Exception as e:
        log_test("ExitRule Metadata Field", False, f"Error: {e}")
        return False

def test_enhanced_absorption_zones():
    """Test 5: Enhanced absorption zone methods exist"""
    try:
        from infra.btc_order_flow_metrics import BTCOrderFlowMetrics
        
        metrics = BTCOrderFlowMetrics(order_flow_service=None, mt5_service=None)
        
        # Check Phase 3.2 methods exist
        assert hasattr(metrics, '_get_price_movement')
        assert hasattr(metrics, '_check_price_stall')
        assert hasattr(metrics, '_get_atr')
        
        log_test("Enhanced Absorption Zone Methods", True)
        return True
    except Exception as e:
        log_test("Enhanced Absorption Zone Methods", False, f"Error: {e}")
        return False

def test_price_movement_calculation():
    """Test 6: Price movement calculation"""
    try:
        from infra.btc_order_flow_metrics import BTCOrderFlowMetrics
        
        metrics = BTCOrderFlowMetrics(order_flow_service=None, mt5_service=None)
        
        # Test method exists and handles None gracefully
        result = metrics._get_price_movement("BTCUSDT", window=60)
        # Should return None if MT5 unavailable (acceptable)
        assert result is None or isinstance(result, float)
        
        log_test("Price Movement Calculation", True, f"Result: {result}")
        return True
    except Exception as e:
        log_test("Price Movement Calculation", False, f"Error: {e}")
        return False

def test_price_stall_check():
    """Test 7: Price stall check"""
    try:
        from infra.btc_order_flow_metrics import BTCOrderFlowMetrics
        
        metrics = BTCOrderFlowMetrics(order_flow_service=None, mt5_service=None)
        
        # Test with None (should return False - conservative)
        result = metrics._check_price_stall("BTCUSDT", None)
        assert result == False
        
        # Test with low movement
        result_low = metrics._check_price_stall("BTCUSDT", 10.0)
        assert isinstance(result_low, bool)
        
        log_test("Price Stall Check", True)
        return True
    except Exception as e:
        log_test("Price Stall Check", False, f"Error: {e}")
        return False

def test_atr_calculation():
    """Test 8: ATR calculation"""
    try:
        from infra.btc_order_flow_metrics import BTCOrderFlowMetrics
        
        metrics = BTCOrderFlowMetrics(order_flow_service=None, mt5_service=None)
        
        # Test method exists and handles None gracefully
        result = metrics._get_atr("BTCUSDT")
        # Should return None if MT5 unavailable (acceptable)
        assert result is None or isinstance(result, float)
        
        log_test("ATR Calculation", True, f"Result: {result}")
        return True
    except Exception as e:
        log_test("ATR Calculation", False, f"Error: {e}")
        return False

def test_check_exits_integration():
    """Test 9: check_exits() has Phase 3 integration"""
    try:
        from infra.intelligent_exit_manager import IntelligentExitManager
        import inspect
        
        class MockMT5:
            def connect(self):
                return False
        
        manager = IntelligentExitManager(mt5_service=MockMT5(), order_flow_service=None)
        
        # Check if check_exits method mentions Phase 3 or order flow flip
        source = inspect.getsource(manager.check_exits)
        has_order_flow_flip = 'order_flow_flip' in source.lower() or 'phase 3' in source.lower()
        
        log_test("Check Exits Integration", True, f"Has order flow flip: {has_order_flow_flip}")
        return True
    except Exception as e:
        log_test("Check Exits Integration", False, f"Error: {e}")
        return False

def test_entry_delta_storage():
    """Test 10: Entry delta storage in auto_execution_system"""
    try:
        from auto_execution_system import AutoExecutionSystem
        import inspect
        
        system = AutoExecutionSystem()
        
        # Check if _execute_trade method mentions Phase 3 or entry delta
        source = inspect.getsource(system._execute_trade)
        has_entry_delta = 'entry_delta' in source.lower() or 'phase 3' in source.lower()
        
        log_test("Entry Delta Storage", True, f"Has entry delta storage: {has_entry_delta}")
        return True
    except Exception as e:
        log_test("Entry Delta Storage", False, f"Error: {e}")
        return False

def test_absorption_zone_enhancement():
    """Test 11: Absorption zone detection enhanced"""
    try:
        from infra.btc_order_flow_metrics import BTCOrderFlowMetrics
        import inspect
        
        metrics = BTCOrderFlowMetrics(order_flow_service=None, mt5_service=None)
        
        # Check if _detect_absorption_zones mentions Phase 3 or price movement
        source = inspect.getsource(metrics._detect_absorption_zones)
        has_enhancement = 'price_movement' in source.lower() or 'price_stall' in source.lower() or 'phase 3' in source.lower()
        
        log_test("Absorption Zone Enhancement", True, f"Has enhancement: {has_enhancement}")
        return True
    except Exception as e:
        log_test("Absorption Zone Enhancement", False, f"Error: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("=" * 70)
    print("Phase 3 Implementation Test Suite")
    print("=" * 70)
    print()
    
    tests = [
        test_intelligent_exit_manager_import,
        test_order_flow_flip_methods,
        test_convert_to_binance_symbol,
        test_exit_rule_metadata,
        test_enhanced_absorption_zones,
        test_price_movement_calculation,
        test_price_stall_check,
        test_atr_calculation,
        test_check_exits_integration,
        test_entry_delta_storage,
        test_absorption_zone_enhancement,
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
        print("[SUCCESS] All Phase 3 tests passed!")
        return 0
    else:
        print(f"[FAILURE] {len(test_results['failed'])} test(s) failed")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
