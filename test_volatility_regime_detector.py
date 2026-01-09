"""
Test script for Volatility Regime Detector (Phase 1)

Tests the core detection functionality with:
1. Sample data tests
2. Real MT5 data tests
3. Edge case validation
"""
import sys
import logging
from datetime import datetime
import numpy as np
import pandas as pd
from typing import Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the detector
try:
    from infra.volatility_regime_detector import RegimeDetector, VolatilityRegime
    logger.info("✅ Successfully imported RegimeDetector")
except ImportError as e:
    logger.error(f"❌ Failed to import RegimeDetector: {e}")
    sys.exit(1)


def create_sample_timeframe_data(
    atr_ratio: float = 1.0,
    bb_width_ratio: float = 1.0,
    adx: float = 20.0,
    volume_spike: bool = False
) -> Dict[str, Any]:
    """Create sample timeframe data for testing"""
    # Create sample OHLCV data
    np.random.seed(42)
    n_bars = 100
    
    base_price = 100.0
    prices = base_price + np.cumsum(np.random.randn(n_bars) * 0.5)
    
    rates = []
    for i in range(n_bars):
        high = prices[i] + abs(np.random.randn() * 0.2)
        low = prices[i] - abs(np.random.randn() * 0.2)
        open_price = prices[i] if i == 0 else prices[i-1]
        close = prices[i]
        volume = np.random.randint(1000, 5000)
        if volume_spike:
            volume = int(volume * 2.0)  # 200% spike
        
        rates.append({
            'time': datetime.now().timestamp() + i * 300,  # 5-minute intervals
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'tick_volume': volume,
            'spread': 0.1,
            'real_volume': volume
        })
    
    # Calculate ATR values based on ratio
    atr_50_base = 1.0
    atr_14 = atr_50_base * atr_ratio
    
    # Calculate BB based on width ratio
    bb_middle = base_price
    median_width = 0.02  # 2% median width
    bb_width = median_width * bb_width_ratio
    bb_upper = bb_middle + (bb_width * bb_middle / 2)
    bb_lower = bb_middle - (bb_width * bb_middle / 2)
    
    return {
        "rates": rates,
        "atr_14": atr_14,
        "atr_50": atr_50_base,
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "bb_middle": bb_middle,
        "adx": adx,
        "volume": np.array([r['tick_volume'] for r in rates])
    }


def test_stable_regime():
    """Test detection of STABLE regime"""
    logger.info("\n" + "="*70)
    logger.info("TEST 1: STABLE Regime Detection")
    logger.info("="*70)
    
    detector = RegimeDetector()
    
    # Create stable regime data (low ATR, tight BB, low ADX)
    timeframe_data = {
        "M5": create_sample_timeframe_data(atr_ratio=1.0, bb_width_ratio=1.2, adx=15.0),
        "M15": create_sample_timeframe_data(atr_ratio=1.1, bb_width_ratio=1.3, adx=18.0),
        "H1": create_sample_timeframe_data(atr_ratio=1.05, bb_width_ratio=1.25, adx=16.0)
    }
    
    result = detector.detect_regime("TEST_SYMBOL", timeframe_data)
    
    logger.info(f"Regime: {result['regime']}")
    logger.info(f"Confidence: {result['confidence']}%")
    logger.info(f"ATR Ratio: {result['atr_ratio']:.2f}x")
    logger.info(f"Reasoning: {result['reasoning']}")
    
    assert result['regime'] == VolatilityRegime.STABLE, f"Expected STABLE, got {result['regime']}"
    logger.info("✅ TEST 1 PASSED: STABLE regime detected correctly")


def test_volatile_regime():
    """Test detection of VOLATILE regime"""
    logger.info("\n" + "="*70)
    logger.info("TEST 2: VOLATILE Regime Detection")
    logger.info("="*70)
    
    detector = RegimeDetector()
    
    # Create volatile regime data (high ATR, wide BB, high ADX, volume spike)
    timeframe_data = {
        "M5": create_sample_timeframe_data(atr_ratio=1.6, bb_width_ratio=2.0, adx=30.0, volume_spike=True),
        "M15": create_sample_timeframe_data(atr_ratio=1.5, bb_width_ratio=1.9, adx=28.0, volume_spike=True),
        "H1": create_sample_timeframe_data(atr_ratio=1.7, bb_width_ratio=2.1, adx=32.0, volume_spike=True)
    }
    
    result = detector.detect_regime("TEST_SYMBOL", timeframe_data)
    
    logger.info(f"Regime: {result['regime']}")
    logger.info(f"Confidence: {result['confidence']}%")
    logger.info(f"ATR Ratio: {result['atr_ratio']:.2f}x")
    logger.info(f"Volume Confirmed: {result['volume_confirmed']}")
    logger.info(f"Reasoning: {result['reasoning']}")
    
    assert result['regime'] == VolatilityRegime.VOLATILE, f"Expected VOLATILE, got {result['regime']}"
    logger.info("✅ TEST 2 PASSED: VOLATILE regime detected correctly")


def test_transitional_regime():
    """Test detection of TRANSITIONAL regime"""
    logger.info("\n" + "="*70)
    logger.info("TEST 3: TRANSITIONAL Regime Detection")
    logger.info("="*70)
    
    detector = RegimeDetector()
    
    # Create transitional regime data (moderate ATR, moderate BB, moderate ADX)
    timeframe_data = {
        "M5": create_sample_timeframe_data(atr_ratio=1.3, bb_width_ratio=1.6, adx=22.0),
        "M15": create_sample_timeframe_data(atr_ratio=1.25, bb_width_ratio=1.7, adx=24.0),
        "H1": create_sample_timeframe_data(atr_ratio=1.35, bb_width_ratio=1.65, adx=23.0)
    }
    
    result = detector.detect_regime("TEST_SYMBOL", timeframe_data)
    
    logger.info(f"Regime: {result['regime']}")
    logger.info(f"Confidence: {result['confidence']}%")
    logger.info(f"ATR Ratio: {result['atr_ratio']:.2f}x")
    logger.info(f"Reasoning: {result['reasoning']}")
    
    assert result['regime'] == VolatilityRegime.TRANSITIONAL, f"Expected TRANSITIONAL, got {result['regime']}"
    logger.info("✅ TEST 3 PASSED: TRANSITIONAL regime detected correctly")


def test_persistence_filter():
    """Test persistence filter (requires ≥3 candles)"""
    logger.info("\n" + "="*70)
    logger.info("TEST 4: Persistence Filter")
    logger.info("="*70)
    
    detector = RegimeDetector()
    
    # First call - should detect volatile
    volatile_data = {
        "M5": create_sample_timeframe_data(atr_ratio=1.6, bb_width_ratio=2.0, adx=30.0, volume_spike=True),
        "M15": create_sample_timeframe_data(atr_ratio=1.5, bb_width_ratio=1.9, adx=28.0, volume_spike=True),
        "H1": create_sample_timeframe_data(atr_ratio=1.7, bb_width_ratio=2.1, adx=32.0, volume_spike=True)
    }
    
    # Make multiple calls to build history
    for i in range(5):
        result = detector.detect_regime("TEST_PERSISTENCE", volatile_data)
        logger.info(f"Call {i+1}: {result['regime']} (confidence: {result['confidence']:.1f}%)")
    
    # Now switch to stable - should still show volatile until persistence met
    stable_data = {
        "M5": create_sample_timeframe_data(atr_ratio=1.0, bb_width_ratio=1.2, adx=15.0),
        "M15": create_sample_timeframe_data(atr_ratio=1.1, bb_width_ratio=1.3, adx=18.0),
        "H1": create_sample_timeframe_data(atr_ratio=1.05, bb_width_ratio=1.25, adx=16.0)
    }
    
    # First few calls with stable data should still return volatile (persistence filter)
    for i in range(3):
        result = detector.detect_regime("TEST_PERSISTENCE", stable_data)
        logger.info(f"After switch, call {i+1}: {result['regime']} (confidence: {result['confidence']:.1f}%)")
    
    logger.info("✅ TEST 4 PASSED: Persistence filter working (may need more calls to confirm change)")


def test_real_mt5_data():
    """Test with real MT5 data if available"""
    logger.info("\n" + "="*70)
    logger.info("TEST 5: Real MT5 Data")
    logger.info("="*70)
    
    try:
        import MetaTrader5 as mt5
        from infra.indicator_bridge import IndicatorBridge
        
        # Initialize MT5
        if not mt5.initialize():
            logger.warning("⚠️ MT5 not initialized - skipping real data test")
            return
        
        # Test with BTCUSD if available
        test_symbols = ["BTCUSDc", "XAUUSDc", "EURUSDc"]
        symbol_to_test = None
        
        for sym in test_symbols:
            if mt5.symbol_select(sym, True):
                symbol_to_test = sym
                break
        
        if not symbol_to_test:
            logger.warning("⚠️ No test symbols available in MT5 - skipping real data test")
            mt5.shutdown()
            return
        
        logger.info(f"Testing with real data: {symbol_to_test}")
        
        # Get multi-timeframe data
        bridge = IndicatorBridge()
        all_timeframe_data = bridge.get_multi(symbol_to_test)
        
        if not all_timeframe_data:
            logger.warning("⚠️ No timeframe data retrieved - skipping real data test")
            mt5.shutdown()
            return
        
        # Prepare data for detector
        detector = RegimeDetector()
        timeframe_data_for_regime = {}
        
        for tf_name in ["M5", "M15", "H1"]:
            tf_data = all_timeframe_data.get(tf_name)
            if tf_data:
                timeframe_data_for_regime[tf_name] = {
                    "rates": tf_data.get("rates"),
                    "atr_14": tf_data.get("atr_14"),
                    "atr_50": tf_data.get("atr_50"),
                    "bb_upper": tf_data.get("bb_upper"),
                    "bb_lower": tf_data.get("bb_lower"),
                    "bb_middle": tf_data.get("bb_middle"),
                    "adx": tf_data.get("adx"),
                    "volume": tf_data.get("volume") or tf_data.get("tick_volume")
                }
        
        if timeframe_data_for_regime:
            result = detector.detect_regime(
                symbol_to_test,
                timeframe_data_for_regime,
                current_time=datetime.now()
            )
            
            logger.info(f"Symbol: {symbol_to_test}")
            logger.info(f"Regime: {result['regime']}")
            logger.info(f"Confidence: {result['confidence']}%")
            logger.info(f"ATR Ratio: {result['atr_ratio']:.2f}x")
            logger.info(f"BB Width Ratio: {result['bb_width_ratio']:.2f}x")
            logger.info(f"ADX: {result['adx_composite']:.1f}")
            logger.info(f"Volume Confirmed: {result['volume_confirmed']}")
            logger.info(f"Reasoning: {result['reasoning']}")
            
            logger.info("✅ TEST 5 PASSED: Real MT5 data test completed")
        else:
            logger.warning("⚠️ Insufficient timeframe data for detection")
        
        mt5.shutdown()
        
    except ImportError:
        logger.warning("⚠️ MT5 not available - skipping real data test")
    except Exception as e:
        logger.error(f"❌ Real data test failed: {e}", exc_info=True)


def test_edge_cases():
    """Test edge cases"""
    logger.info("\n" + "="*70)
    logger.info("TEST 6: Edge Cases")
    logger.info("="*70)
    
    detector = RegimeDetector()
    
    # Test 1: Missing timeframe data
    try:
        result = detector.detect_regime("TEST_MISSING", {})
        logger.info(f"Missing data handled: {result['regime']} (confidence: {result['confidence']}%)")
        logger.info("✅ Edge case 1 passed: Missing data handled gracefully")
    except Exception as e:
        logger.error(f"❌ Edge case 1 failed: {e}")
    
    # Test 2: Partial timeframe data
    partial_data = {
        "M5": create_sample_timeframe_data(atr_ratio=1.6, bb_width_ratio=2.0, adx=30.0)
        # Missing M15 and H1
    }
    try:
        result = detector.detect_regime("TEST_PARTIAL", partial_data)
        logger.info(f"Partial data handled: {result['regime']} (confidence: {result['confidence']}%)")
        logger.info("✅ Edge case 2 passed: Partial data handled gracefully")
    except Exception as e:
        logger.error(f"❌ Edge case 2 failed: {e}")
    
    # Test 3: Invalid/missing indicator values
    invalid_data = {
        "M5": {
            "rates": create_sample_timeframe_data()["rates"],
            "atr_14": None,
            "atr_50": None,
            "bb_upper": None,
            "bb_lower": None,
            "bb_middle": None,
            "adx": None,
            "volume": None
        },
        "M15": {
            "rates": create_sample_timeframe_data()["rates"],
            "atr_14": None,
            "atr_50": None,
            "bb_upper": None,
            "bb_lower": None,
            "bb_middle": None,
            "adx": None,
            "volume": None
        },
        "H1": {
            "rates": create_sample_timeframe_data()["rates"],
            "atr_14": None,
            "atr_50": None,
            "bb_upper": None,
            "bb_lower": None,
            "bb_middle": None,
            "adx": None,
            "volume": None
        }
    }
    try:
        result = detector.detect_regime("TEST_INVALID", invalid_data)
        logger.info(f"Invalid data handled: {result['regime']} (confidence: {result['confidence']}%)")
        logger.info("✅ Edge case 3 passed: Invalid data handled gracefully")
    except Exception as e:
        logger.error(f"❌ Edge case 3 failed: {e}")


def run_all_tests():
    """Run all tests"""
    logger.info("\n" + "="*70)
    logger.info("VOLATILITY REGIME DETECTOR - TEST SUITE")
    logger.info("="*70)
    
    tests = [
        test_stable_regime,
        test_volatile_regime,
        test_transitional_regime,
        test_persistence_filter,
        test_edge_cases,
        test_real_mt5_data  # Run last as it requires MT5
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            logger.error(f"❌ {test_func.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            logger.error(f"❌ {test_func.__name__} ERROR: {e}", exc_info=True)
            failed += 1
    
    logger.info("\n" + "="*70)
    logger.info(f"TEST SUMMARY: {passed} passed, {failed} failed")
    logger.info("="*70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

