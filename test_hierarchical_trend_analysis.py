"""
Test script for Hierarchical Trend Analysis Implementation (Phase 1)
Tests all new methods and enhancements
"""
import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_imports():
    """Test that all imports work"""
    logger.info("=" * 60)
    logger.info("TEST 1: Testing Imports")
    logger.info("=" * 60)
    try:
        from infra.multi_timeframe_analyzer import MultiTimeframeAnalyzer, VOLATILITY_WEIGHTS
        logger.info("✅ Successfully imported MultiTimeframeAnalyzer")
        logger.info(f"✅ VOLATILITY_WEIGHTS constant exists: {len(VOLATILITY_WEIGHTS)} regimes")
        return True
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        return False

def test_volatility_weights():
    """Test VOLATILITY_WEIGHTS constant"""
    logger.info("=" * 60)
    logger.info("TEST 2: Testing VOLATILITY_WEIGHTS Constant")
    logger.info("=" * 60)
    try:
        from infra.multi_timeframe_analyzer import VOLATILITY_WEIGHTS
        
        # Check structure
        assert "low" in VOLATILITY_WEIGHTS, "Missing 'low' regime"
        assert "medium" in VOLATILITY_WEIGHTS, "Missing 'medium' regime"
        assert "high" in VOLATILITY_WEIGHTS, "Missing 'high' regime"
        
        # Check weights sum to ~1.0 for each regime
        for regime, weights in VOLATILITY_WEIGHTS.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.01, f"{regime} regime weights don't sum to 1.0: {total}"
            logger.info(f"✅ {regime} regime: {weights} (sum: {total:.2f})")
        
        logger.info("✅ VOLATILITY_WEIGHTS structure is correct")
        return True
    except Exception as e:
        logger.error(f"❌ VOLATILITY_WEIGHTS test failed: {e}")
        return False

def test_analyzer_initialization():
    """Test analyzer initialization with trend memory"""
    logger.info("=" * 60)
    logger.info("TEST 3: Testing Analyzer Initialization")
    logger.info("=" * 60)
    try:
        from infra.multi_timeframe_analyzer import MultiTimeframeAnalyzer
        
        # Create mock indicator bridge
        class MockIndicatorBridge:
            def get_multi(self, symbol):
                return {}
        
        analyzer = MultiTimeframeAnalyzer(MockIndicatorBridge())
        
        # Check trend memory initialized
        assert hasattr(analyzer, 'trend_memory'), "trend_memory not initialized"
        assert hasattr(analyzer, 'trend_memory_lock'), "trend_memory_lock not initialized"
        assert "H4" in analyzer.trend_memory, "H4 not in trend_memory"
        assert "H1" in analyzer.trend_memory, "H1 not in trend_memory"
        
        logger.info("✅ Analyzer initialized with trend memory")
        logger.info(f"   Trend memory keys: {list(analyzer.trend_memory.keys())}")
        return True
    except Exception as e:
        logger.error(f"❌ Analyzer initialization test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_trend_memory():
    """Test trend memory buffer functionality"""
    logger.info("=" * 60)
    logger.info("TEST 4: Testing Trend Memory Buffer")
    logger.info("=" * 60)
    try:
        from infra.multi_timeframe_analyzer import MultiTimeframeAnalyzer
        
        class MockIndicatorBridge:
            def get_multi(self, symbol):
                return {}
        
        analyzer = MultiTimeframeAnalyzer(MockIndicatorBridge())
        
        # Test insufficient data
        result1 = analyzer._update_trend_memory("H4", "BULLISH", 70)
        assert result1["stability"] == "INSUFFICIENT_DATA", f"Expected INSUFFICIENT_DATA, got {result1['stability']}"
        logger.info(f"✅ Insufficient data: {result1['stability']}")
        
        # Add 2 more bars (total 3)
        analyzer._update_trend_memory("H4", "BULLISH", 75)
        result2 = analyzer._update_trend_memory("H4", "BULLISH", 80)
        assert result2["stability"] == "STABLE", f"Expected STABLE, got {result2['stability']}"
        assert result2["bias"] == "BULLISH", f"Expected BULLISH, got {result2['bias']}"
        logger.info(f"✅ 3-bar confirmation: {result2['stability']}, bias: {result2['bias']}")
        
        # Test mixed signals
        analyzer._update_trend_memory("H1", "BULLISH", 70)
        analyzer._update_trend_memory("H1", "BEARISH", 60)  # Mixed
        result3 = analyzer._update_trend_memory("H1", "BULLISH", 65)
        assert result3["stability"] == "UNSTABLE", f"Expected UNSTABLE, got {result3['stability']}"
        logger.info(f"✅ Mixed signals: {result3['stability']}")
        
        logger.info("✅ Trend memory buffer working correctly")
        return True
    except Exception as e:
        logger.error(f"❌ Trend memory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_primary_trend_determination():
    """Test primary trend determination"""
    logger.info("=" * 60)
    logger.info("TEST 5: Testing Primary Trend Determination")
    logger.info("=" * 60)
    try:
        from infra.multi_timeframe_analyzer import MultiTimeframeAnalyzer
        
        class MockIndicatorBridge:
            def get_multi(self, symbol):
                return {}
        
        analyzer = MultiTimeframeAnalyzer(MockIndicatorBridge())
        
        # Test BULLISH alignment
        h4_bullish = {"bias": "BULLISH", "confidence": 75}
        h1_continuation = {"status": "CONTINUATION", "confidence": 80}
        result1 = analyzer._determine_primary_trend(h4_bullish, h1_continuation)
        assert result1["primary_trend"] == "BULLISH", f"Expected BULLISH, got {result1['primary_trend']}"
        assert result1["trend_strength"] == "STRONG", f"Expected STRONG, got {result1['trend_strength']}"
        logger.info(f"✅ BULLISH alignment: {result1['primary_trend']}, strength: {result1['trend_strength']}")
        
        # Test BEARISH alignment
        h4_bearish = {"bias": "BEARISH", "confidence": 70}
        h1_pullback = {"status": "PULLBACK", "confidence": 65}
        result2 = analyzer._determine_primary_trend(h4_bearish, h1_pullback)
        assert result2["primary_trend"] == "BEARISH", f"Expected BEARISH, got {result2['primary_trend']}"
        logger.info(f"✅ BEARISH alignment: {result2['primary_trend']}, strength: {result2['trend_strength']}")
        
        # Test NEUTRAL
        h4_neutral = {"bias": "NEUTRAL", "confidence": 50}
        h1_neutral = {"status": "NEUTRAL", "confidence": 50}
        result3 = analyzer._determine_primary_trend(h4_neutral, h1_neutral)
        assert result3["primary_trend"] == "NEUTRAL", f"Expected NEUTRAL, got {result3['primary_trend']}"
        logger.info(f"✅ NEUTRAL: {result3['primary_trend']}")
        
        logger.info("✅ Primary trend determination working correctly")
        return True
    except Exception as e:
        logger.error(f"❌ Primary trend determination test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_counter_trend_detection():
    """Test counter-trend opportunity detection"""
    logger.info("=" * 60)
    logger.info("TEST 6: Testing Counter-Trend Detection")
    logger.info("=" * 60)
    try:
        from infra.multi_timeframe_analyzer import MultiTimeframeAnalyzer
        
        class MockIndicatorBridge:
            def get_multi(self, symbol):
                return {}
        
        analyzer = MultiTimeframeAnalyzer(MockIndicatorBridge())
        
        # Test counter-trend BUY (primary BEARISH, lower TF BULLISH)
        primary_bearish = {
            "primary_trend": "BEARISH",
            "trend_strength": "STRONG",
            "confidence": 75
        }
        m30 = {"setup": "BUY_SETUP", "confidence": 60}
        m15 = {"trigger": "BUY_TRIGGER", "confidence": 65}
        m5 = {"execution": "BUY_NOW", "confidence": 70}
        
        result1 = analyzer._detect_counter_trend_opportunities(primary_bearish, m30, m15, m5)
        assert result1 is not None, "Counter-trend should be detected"
        assert result1["type"] == "COUNTER_TREND_BUY", f"Expected COUNTER_TREND_BUY, got {result1['type']}"
        assert result1["risk_level"] == "HIGH", f"Expected HIGH risk, got {result1['risk_level']}"
        assert result1["confidence"] <= 60, f"Counter-trend confidence should be capped at 60%, got {result1['confidence']}"
        assert result1["risk_adjustments"]["sl_multiplier"] == 1.25, "STRONG counter-trend should have 1.25x SL"
        assert result1["risk_adjustments"]["tp_multiplier"] == 0.50, "STRONG counter-trend should have 0.50x TP"
        logger.info(f"✅ Counter-trend BUY detected: {result1['type']}, risk: {result1['risk_level']}")
        logger.info(f"   Risk adjustments: SL×{result1['risk_adjustments']['sl_multiplier']}, "
                   f"TP×{result1['risk_adjustments']['tp_multiplier']}, "
                   f"Max R:R={result1['risk_adjustments']['max_risk_rr']}")
        
        # Test trend continuation
        primary_bullish = {
            "primary_trend": "BULLISH",
            "trend_strength": "MODERATE",
            "confidence": 70
        }
        result2 = analyzer._detect_counter_trend_opportunities(primary_bullish, m30, m15, m5)
        assert result2 is not None, "Trend continuation should be detected"
        assert result2["type"] == "TREND_CONTINUATION_BUY", f"Expected TREND_CONTINUATION_BUY, got {result2['type']}"
        assert result2["risk_level"] == "LOW", f"Expected LOW risk, got {result2['risk_level']}"
        logger.info(f"✅ Trend continuation BUY: {result2['type']}, risk: {result2['risk_level']}")
        
        logger.info("✅ Counter-trend detection working correctly")
        return True
    except Exception as e:
        logger.error(f"❌ Counter-trend detection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_volatility_weights():
    """Test dynamic volatility weighting"""
    logger.info("=" * 60)
    logger.info("TEST 7: Testing Dynamic Volatility Weighting")
    logger.info("=" * 60)
    try:
        from infra.multi_timeframe_analyzer import MultiTimeframeAnalyzer
        
        class MockIndicatorBridge:
            def get_multi(self, symbol):
                return {}
        
        analyzer = MultiTimeframeAnalyzer(MockIndicatorBridge())
        
        # Mock _analyze_volatility_state to return different regimes
        original_method = analyzer._analyze_volatility_state
        
        # Test high volatility
        def mock_high_vol():
            return {"state": "expansion_strong_trend"}
        analyzer._analyze_volatility_state = mock_high_vol
        weights_high = analyzer._get_volatility_based_weights()
        assert weights_high["H4"] == 0.50, f"High volatility should weight H4 at 0.50, got {weights_high['H4']}"
        assert weights_high["M5"] == 0.02, f"High volatility should weight M5 at 0.02, got {weights_high['M5']}"
        logger.info(f"✅ High volatility weights: H4={weights_high['H4']}, M5={weights_high['M5']}")
        
        # Test low volatility
        def mock_low_vol():
            return {"state": "squeeze_no_trend"}
        analyzer._analyze_volatility_state = mock_low_vol
        weights_low = analyzer._get_volatility_based_weights()
        assert weights_low["H4"] == 0.30, f"Low volatility should weight H4 at 0.30, got {weights_low['H4']}"
        assert weights_low["M5"] == 0.10, f"Low volatility should weight M5 at 0.10, got {weights_low['M5']}"
        logger.info(f"✅ Low volatility weights: H4={weights_low['H4']}, M5={weights_low['M5']}")
        
        # Restore original method
        analyzer._analyze_volatility_state = original_method
        
        logger.info("✅ Dynamic volatility weighting working correctly")
        return True
    except Exception as e:
        logger.error(f"❌ Volatility weighting test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_h1_status_mapping():
    """Test H1 status to bias mapping"""
    logger.info("=" * 60)
    logger.info("TEST 8: Testing H1 Status to Bias Mapping")
    logger.info("=" * 60)
    try:
        from infra.multi_timeframe_analyzer import MultiTimeframeAnalyzer
        
        class MockIndicatorBridge:
            def get_multi(self, symbol):
                return {}
        
        analyzer = MultiTimeframeAnalyzer(MockIndicatorBridge())
        
        # Test CONTINUATION
        h1_cont = {"status": "CONTINUATION", "confidence": 70}
        bias1 = analyzer._map_h1_status_to_bias(h1_cont, "BULLISH")
        assert bias1 == "BULLISH", f"CONTINUATION should return H4 bias, got {bias1}"
        logger.info(f"✅ CONTINUATION: {bias1}")
        
        # Test PULLBACK
        h1_pull = {"status": "PULLBACK", "confidence": 65}
        bias2 = analyzer._map_h1_status_to_bias(h1_pull, "BEARISH")
        assert bias2 == "BEARISH", f"PULLBACK should return H4 bias, got {bias2}"
        logger.info(f"✅ PULLBACK: {bias2}")
        
        # Test DIVERGENCE
        h1_div = {"status": "DIVERGENCE", "price_vs_ema20": "above", "confidence": 60}
        bias3 = analyzer._map_h1_status_to_bias(h1_div, "BEARISH")
        assert bias3 == "BULLISH", f"DIVERGENCE with price above EMA should return BULLISH, got {bias3}"
        logger.info(f"✅ DIVERGENCE (above EMA): {bias3}")
        
        logger.info("✅ H1 status mapping working correctly")
        return True
    except Exception as e:
        logger.error(f"❌ H1 status mapping test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_auto_execution_integration():
    """Test auto-execution system integration"""
    logger.info("=" * 60)
    logger.info("TEST 9: Testing Auto-Execution Integration")
    logger.info("=" * 60)
    try:
        # Check source code directly instead of importing (avoids MetaTrader5 dependency)
        import inspect
        import ast
        
        with open('auto_execution_system.py', 'r', encoding='utf-8') as f:
            source = f.read()
        
        # Parse the source code
        tree = ast.parse(source)
        
        # Find AutoExecutionSystem class
        class_found = False
        init_params = []
        methods = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == 'AutoExecutionSystem':
                class_found = True
                # Find __init__ method
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == '__init__':
                        # Extract parameters
                        for arg in item.args.args:
                            if arg.arg != 'self':
                                init_params.append(arg.arg)
                    elif isinstance(item, ast.FunctionDef) and item.name.startswith('_get_'):
                        methods.append(item.name)
        
        assert class_found, "AutoExecutionSystem class not found"
        assert 'mtf_analyzer' in init_params, f"mtf_analyzer parameter not found in __init__. Found: {init_params}"
        logger.info(f"✅ mtf_analyzer parameter exists in AutoExecutionSystem.__init__")
        logger.info(f"   All __init__ parameters: {init_params}")
        
        # Check helper methods exist
        required_methods = ['_get_mtf_analysis', '_get_confluence_score', '_get_liquidity_context']
        for method in required_methods:
            assert method in methods, f"{method} method not found. Found methods: {methods}"
        logger.info(f"✅ Helper methods exist: {required_methods}")
        
        # Check for enhanced validation in _check_conditions
        check_conditions_found = False
        enhanced_validation_found = False
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == '_check_conditions':
                check_conditions_found = True
                # Check for enhanced validation code patterns
                # Look for calls to _get_mtf_analysis or references to primary_trend
                for item in ast.walk(node):
                    if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute):
                        if item.func.attr == '_get_mtf_analysis':
                            enhanced_validation_found = True
                            break
                    elif isinstance(item, ast.Name) and item.id == 'primary_trend':
                        enhanced_validation_found = True
                        break
        
        assert check_conditions_found, "_check_conditions method not found"
        assert enhanced_validation_found, "Enhanced validation code not found in _check_conditions (looking for _get_mtf_analysis or primary_trend)"
        logger.info("✅ Enhanced validation code found in _check_conditions")
        
        logger.info("✅ Auto-execution integration structure is correct")
        return True
    except Exception as e:
        logger.error(f"❌ Auto-execution integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    logger.info("\n" + "=" * 60)
    logger.info("HIERARCHICAL TREND ANALYSIS - PHASE 1 TEST SUITE")
    logger.info("=" * 60 + "\n")
    
    tests = [
        ("Imports", test_imports),
        ("VOLATILITY_WEIGHTS Constant", test_volatility_weights),
        ("Analyzer Initialization", test_analyzer_initialization),
        ("Trend Memory Buffer", test_trend_memory),
        ("Primary Trend Determination", test_primary_trend_determination),
        ("Counter-Trend Detection", test_counter_trend_detection),
        ("Dynamic Volatility Weighting", test_volatility_weights),
        ("H1 Status Mapping", test_h1_status_mapping),
        ("Auto-Execution Integration", test_auto_execution_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
        logger.info("")
    
    # Summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("")
    logger.info(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Phase 1 implementation is working correctly.")
        return 0
    else:
        logger.error(f"⚠️ {total - passed} test(s) failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

