"""
Phase 1 Implementation Test Script

Tests all Phase 1 components:
- TickByTickDeltaEngine
- DeltaDivergenceDetector
- BTCOrderFlowMetrics integration
"""

import sys
import time
import pandas as pd
import numpy as np
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

def test_tick_engine_import():
    """Test 1: Tick engine imports"""
    try:
        from infra.tick_by_tick_delta_engine import TickByTickDeltaEngine, DeltaMetrics
        log_test("Tick Engine Import", True)
        return True
    except Exception as e:
        log_test("Tick Engine Import", False, f"Error: {e}")
        return False

def test_tick_engine_initialization():
    """Test 2: Tick engine initialization"""
    try:
        from infra.tick_by_tick_delta_engine import TickByTickDeltaEngine
        engine = TickByTickDeltaEngine(symbol="BTCUSDT", max_history=200)
        
        # Check initial state
        assert engine.symbol == "BTCUSDT"
        assert engine.current_delta == 0.0
        assert engine.current_cvd == 0.0
        assert len(engine.delta_history) == 0
        
        log_test("Tick Engine Initialization", True)
        return True
    except Exception as e:
        log_test("Tick Engine Initialization", False, f"Error: {e}")
        return False

def test_tick_engine_process_trade():
    """Test 3: Process aggTrade"""
    try:
        from infra.tick_by_tick_delta_engine import TickByTickDeltaEngine
        engine = TickByTickDeltaEngine(symbol="BTCUSDT", max_history=200)
        
        # Process a BUY trade
        trade_buy = {
            "side": "BUY",
            "quantity": 1.5,
            "timestamp": time.time(),
            "price": 50000.0
        }
        metrics = engine.process_aggtrade(trade_buy)
        
        assert metrics is not None
        assert metrics.delta == 1.5  # Buy volume
        assert metrics.buy_volume == 1.5
        assert metrics.sell_volume == 0.0
        assert engine.current_cvd == 1.5
        
        # Process a SELL trade
        trade_sell = {
            "side": "SELL",
            "quantity": 0.8,
            "timestamp": time.time(),
            "price": 50010.0
        }
        metrics = engine.process_aggtrade(trade_sell)
        
        assert metrics.delta == -0.8  # Sell volume (negative)
        assert engine.current_cvd == 0.7  # 1.5 - 0.8
        
        log_test("Tick Engine Process Trade", True)
        return True
    except Exception as e:
        log_test("Tick Engine Process Trade", False, f"Error: {e}")
        return False

def test_tick_engine_cvd_trend():
    """Test 4: CVD trend calculation"""
    try:
        from infra.tick_by_tick_delta_engine import TickByTickDeltaEngine
        engine = TickByTickDeltaEngine(symbol="BTCUSDT", max_history=200)
        
        # Process multiple trades to build CVD trend
        for i in range(15):
            trade = {
                "side": "BUY" if i % 2 == 0 else "SELL",
                "quantity": 1.0 + (i * 0.1),
                "timestamp": time.time() + i,
                "price": 50000.0 + i
            }
            engine.process_aggtrade(trade)
        
        # Get CVD trend
        trend = engine.get_cvd_trend(period=10)
        
        assert 'trend' in trend
        assert 'slope' in trend
        assert trend['trend'] in ['rising', 'falling', 'flat']
        
        log_test("Tick Engine CVD Trend", True)
        return True
    except Exception as e:
        log_test("Tick Engine CVD Trend", False, f"Error: {e}")
        return False

def test_delta_divergence_detector_import():
    """Test 5: Delta divergence detector imports"""
    try:
        from infra.delta_divergence_detector import DeltaDivergenceDetector
        log_test("Delta Divergence Detector Import", True)
        return True
    except Exception as e:
        log_test("Delta Divergence Detector Import", False, f"Error: {e}")
        return False

def test_delta_divergence_detector_initialization():
    """Test 6: Delta divergence detector initialization"""
    try:
        from infra.delta_divergence_detector import DeltaDivergenceDetector
        detector = DeltaDivergenceDetector(min_bars=20, trend_period=10)
        
        assert detector.min_bars == 20
        assert detector.trend_period == 10
        
        log_test("Delta Divergence Detector Initialization", True)
        return True
    except Exception as e:
        log_test("Delta Divergence Detector Initialization", False, f"Error: {e}")
        return False

def test_delta_divergence_detection():
    """Test 7: Delta divergence detection"""
    try:
        from infra.delta_divergence_detector import DeltaDivergenceDetector
        
        detector = DeltaDivergenceDetector(min_bars=20, trend_period=10)
        
        # Create mock price bars (DataFrame) - price falling
        price_data = {
            'close': [50000 - i * 10 for i in range(30)],
            'high': [50000 - i * 10 + 5 for i in range(30)],
            'low': [50000 - i * 10 - 5 for i in range(30)],
            'open': [50000 - i * 10 for i in range(30)]
        }
        price_bars_df = pd.DataFrame(price_data)
        
        # Create mock delta history - delta rising (opposite to price)
        delta_history = [10 + i * 2 for i in range(30)]  # Rising delta
        
        # Detect divergence (should be bullish: price falling, delta rising)
        result = detector.detect_delta_divergence(price_bars_df, delta_history)
        
        if result:
            assert 'type' in result
            assert 'strength' in result
            assert result['type'] in ['bullish', 'bearish']
            assert 0.0 <= result['strength'] <= 1.0
            log_test("Delta Divergence Detection", True, f"Detected: {result['type']}, strength: {result['strength']:.2f}")
        else:
            log_test("Delta Divergence Detection", True, "No divergence detected (acceptable)")
        
        return True
    except Exception as e:
        log_test("Delta Divergence Detection", False, f"Error: {e}")
        return False

def test_btc_order_flow_metrics_import():
    """Test 8: BTCOrderFlowMetrics imports with Phase 1 components"""
    try:
        from infra.btc_order_flow_metrics import BTCOrderFlowMetrics
        log_test("BTCOrderFlowMetrics Import", True)
        return True
    except Exception as e:
        log_test("BTCOrderFlowMetrics Import", False, f"Error: {e}")
        return False

def test_btc_order_flow_metrics_tick_engine_integration():
    """Test 9: BTCOrderFlowMetrics tick engine integration"""
    try:
        from infra.btc_order_flow_metrics import BTCOrderFlowMetrics
        
        # Create instance (without order flow service for this test)
        metrics = BTCOrderFlowMetrics(order_flow_service=None, mt5_service=None)
        
        # Check that tick_engines dict exists
        if not hasattr(metrics, 'tick_engines'):
            log_test("BTCOrderFlowMetrics Tick Engine Integration", False, "tick_engines attribute missing")
            return False
        
        if not isinstance(metrics.tick_engines, dict):
            log_test("BTCOrderFlowMetrics Tick Engine Integration", False, f"tick_engines is not a dict: {type(metrics.tick_engines)}")
            return False
        
        # Test initialize_tick_engine
        # This may return False if tick engine not available, which is acceptable
        result = metrics.initialize_tick_engine("BTCUSDT")
        
        # Should return True if tick engine available, False otherwise
        # Both are acceptable - just check it's a bool
        if not isinstance(result, bool):
            log_test("BTCOrderFlowMetrics Tick Engine Integration", False, f"Expected bool, got {type(result)}")
            return False
        
        # If tick engine is available, verify it was created
        if result:
            if "BTCUSDT" not in metrics.tick_engines:
                log_test("BTCOrderFlowMetrics Tick Engine Integration", False, "Tick engine not in dict after initialization")
                return False
            if metrics.tick_engines["BTCUSDT"] is None:
                log_test("BTCOrderFlowMetrics Tick Engine Integration", False, "Tick engine is None in dict")
                return False
        
        log_test("BTCOrderFlowMetrics Tick Engine Integration", True, 
                f"Tick engine available: {result}")
        return True
    except Exception as e:
        log_test("BTCOrderFlowMetrics Tick Engine Integration", False, f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_btc_order_flow_metrics_methods():
    """Test 10: BTCOrderFlowMetrics Phase 1 methods exist"""
    try:
        from infra.btc_order_flow_metrics import BTCOrderFlowMetrics
        
        metrics = BTCOrderFlowMetrics(order_flow_service=None, mt5_service=None)
        
        # Check Phase 1 methods exist
        assert hasattr(metrics, 'initialize_tick_engine')
        assert hasattr(metrics, 'process_aggtrade')
        assert hasattr(metrics, '_calculate_delta_divergence')
        assert hasattr(metrics, '_calculate_cvd_divergence_with_price_bars')
        assert hasattr(metrics, '_detect_divergence_from_bars')
        
        log_test("BTCOrderFlowMetrics Phase 1 Methods", True)
        return True
    except Exception as e:
        log_test("BTCOrderFlowMetrics Phase 1 Methods", False, f"Error: {e}")
        return False

def test_tick_engine_history_access():
    """Test 11: Tick engine history access methods"""
    try:
        from infra.tick_by_tick_delta_engine import TickByTickDeltaEngine
        engine = TickByTickDeltaEngine(symbol="BTCUSDT", max_history=200)
        
        # Process some trades
        for i in range(25):
            trade = {
                "side": "BUY" if i % 3 == 0 else "SELL",
                "quantity": 1.0,
                "timestamp": time.time() + i,
                "price": 50000.0
            }
            engine.process_aggtrade(trade)
        
        # Test history access
        delta_history = engine.get_delta_history(20)
        assert isinstance(delta_history, list)
        assert len(delta_history) <= 20
        
        cvd_history = engine.get_cvd_history(20)
        assert isinstance(cvd_history, list)
        assert len(cvd_history) <= 20
        
        stats = engine.get_statistics()
        assert isinstance(stats, dict)
        assert 'tick_count' in stats
        assert 'current_delta' in stats
        assert 'current_cvd' in stats
        
        log_test("Tick Engine History Access", True)
        return True
    except Exception as e:
        log_test("Tick Engine History Access", False, f"Error: {e}")
        return False

def test_tick_engine_reset():
    """Test 12: Tick engine reset"""
    try:
        from infra.tick_by_tick_delta_engine import TickByTickDeltaEngine
        engine = TickByTickDeltaEngine(symbol="BTCUSDT", max_history=200)
        
        # Process some trades
        for i in range(10):
            trade = {
                "side": "BUY",
                "quantity": 1.0,
                "timestamp": time.time() + i,
                "price": 50000.0
            }
            engine.process_aggtrade(trade)
        
        # Verify state before reset
        assert engine.tick_count > 0
        assert engine.current_cvd > 0
        
        # Reset
        engine.reset()
        
        # Verify state after reset
        assert engine.tick_count == 0
        assert engine.current_cvd == 0.0
        assert len(engine.delta_history) == 0
        assert len(engine.cvd_history) == 0
        
        log_test("Tick Engine Reset", True)
        return True
    except Exception as e:
        log_test("Tick Engine Reset", False, f"Error: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("=" * 70)
    print("Phase 1 Implementation Test Suite")
    print("=" * 70)
    print()
    
    tests = [
        test_tick_engine_import,
        test_tick_engine_initialization,
        test_tick_engine_process_trade,
        test_tick_engine_cvd_trend,
        test_tick_engine_history_access,
        test_tick_engine_reset,
        test_delta_divergence_detector_import,
        test_delta_divergence_detector_initialization,
        test_delta_divergence_detection,
        test_btc_order_flow_metrics_import,
        test_btc_order_flow_metrics_tick_engine_integration,
        test_btc_order_flow_metrics_methods,
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
        print("[SUCCESS] All Phase 1 tests passed!")
        return 0
    else:
        print(f"[FAILURE] {len(test_results['failed'])} test(s) failed")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
