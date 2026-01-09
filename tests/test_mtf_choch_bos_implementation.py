"""
Test script for Phase 0 and Phase 1 implementation
Tests CHOCH/BOS detection in MTF analyzer and updated _format_unified_analysis
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_mtf_analyzer_choch_bos():
    """Test Phase 0: CHOCH/BOS detection in MTF analyzer"""
    logger.info("=" * 80)
    logger.info("TEST: Phase 0 - CHOCH/BOS Detection in MTF Analyzer")
    logger.info("=" * 80)
    
    try:
        from infra.multi_timeframe_analyzer import MultiTimeframeAnalyzer
        from infra.indicator_bridge import IndicatorBridge
        from pathlib import Path
        
        # Initialize analyzer (requires indicator_bridge)
        # Note: This test may require MT5 connection or mock data
        logger.info("Initializing MTF Analyzer...")
        
        # Try to get a test symbol (use a common one)
        test_symbol = "XAUUSDc"  # Gold
        
        try:
            # Try to initialize with actual indicator bridge
            common_dir = Path("common_files")
            if not common_dir.exists():
                logger.warning("common_files directory not found - skipping live test")
                return False
            
            indicator_bridge = IndicatorBridge(common_dir)
            analyzer = MultiTimeframeAnalyzer(indicator_bridge)
            
            logger.info(f"Testing with symbol: {test_symbol}")
            result = analyzer.analyze(test_symbol)
            
            # Verify structure
            assert "timeframes" in result, "Missing 'timeframes' in result"
            assert "H4" in result["timeframes"], "Missing 'H4' timeframe"
            assert "H1" in result["timeframes"], "Missing 'H1' timeframe"
            assert "M30" in result["timeframes"], "Missing 'M30' timeframe"
            assert "M15" in result["timeframes"], "Missing 'M15' timeframe"
            assert "M5" in result["timeframes"], "Missing 'M5' timeframe"
            
            # Verify CHOCH/BOS fields in each timeframe
            timeframes_to_check = ["H4", "H1", "M30", "M15", "M5"]
            all_fields_present = True
            
            for tf in timeframes_to_check:
                tf_data = result["timeframes"].get(tf, {})
                required_fields = [
                    "choch_detected", "choch_bull", "choch_bear",
                    "bos_detected", "bos_bull", "bos_bear"
                ]
                
                missing_fields = [f for f in required_fields if f not in tf_data]
                if missing_fields:
                    logger.error(f"❌ {tf}: Missing fields: {missing_fields}")
                    all_fields_present = False
                else:
                    logger.info(f"✅ {tf}: All CHOCH/BOS fields present")
                    logger.info(f"   - choch_detected: {tf_data.get('choch_detected')}")
                    logger.info(f"   - bos_detected: {tf_data.get('bos_detected')}")
            
            if all_fields_present:
                logger.info("✅ Phase 0: All CHOCH/BOS fields present in all timeframes")
                return True
            else:
                logger.error("❌ Phase 0: Some CHOCH/BOS fields missing")
                return False
                
        except Exception as e:
            logger.error(f"❌ Phase 0 test failed: {e}")
            logger.exception(e)
            return False
            
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return False


def test_format_unified_analysis():
    """Test Phase 1: Updated _format_unified_analysis function"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST: Phase 1 - Updated _format_unified_analysis Function")
    logger.info("=" * 80)
    
    try:
        from desktop_agent import _format_unified_analysis
        
        # Create mock data matching MTF analyzer structure
        mock_smc = {
            "timeframes": {
                "H4": {
                    "bias": "BULLISH",
                    "confidence": 80,
                    "reason": "Test H4",
                    "choch_detected": True,
                    "choch_bull": True,
                    "choch_bear": False,
                    "bos_detected": False,
                    "bos_bull": False,
                    "bos_bear": False
                },
                "H1": {
                    "status": "CONTINUATION",
                    "confidence": 75,
                    "reason": "Test H1",
                    "choch_detected": False,
                    "choch_bull": False,
                    "choch_bear": False,
                    "bos_detected": True,
                    "bos_bull": True,
                    "bos_bear": False
                },
                "M30": {
                    "setup": "BUY_SETUP",
                    "confidence": 70,
                    "reason": "Test M30",
                    "choch_detected": False,
                    "choch_bull": False,
                    "choch_bear": False,
                    "bos_detected": False,
                    "bos_bull": False,
                    "bos_bear": False
                },
                "M15": {
                    "trigger": "BUY_TRIGGER",
                    "confidence": 65,
                    "reason": "Test M15",
                    "choch_detected": False,
                    "choch_bull": False,
                    "choch_bear": False,
                    "bos_detected": False,
                    "bos_bull": False,
                    "bos_bear": False
                },
                "M5": {
                    "execution": "BUY_NOW",
                    "confidence": 60,
                    "reason": "Test M5",
                    "choch_detected": False,
                    "choch_bull": False,
                    "choch_bear": False,
                    "bos_detected": False,
                    "bos_bull": False,
                    "bos_bear": False
                }
            },
            "alignment_score": 75,
            "recommendation": {
                "action": "BUY",
                "confidence": 75,
                "reason": "Test recommendation",
                "h4_bias": "BULLISH",
                "entry_price": 2000.0,
                "stop_loss": 1990.0,
                "summary": "Test summary",
                "market_bias": {
                    "trend": "BULLISH",
                    "strength": "STRONG",
                    "confidence": 80,
                    "stability": "STABLE",
                    "reason": "Test market bias"
                },
                "trade_opportunities": {
                    "type": "TREND",
                    "direction": "BUY",
                    "confidence": 75,
                    "risk_level": "LOW",
                    "risk_adjustments": {
                        "reason": "Test risk"
                    }
                },
                "volatility_regime": "medium",
                "volatility_weights": {
                    "H4": 0.40,
                    "H1": 0.25,
                    "M30": 0.15,
                    "M15": 0.12,
                    "M5": 0.08
                }
            },
            "advanced_insights": {
                "rmag_analysis": {"status": "NORMAL"},
                "volatility_state": {"state": "normal"}
            },
            "advanced_summary": "Test advanced summary"
        }
        
        mock_macro = {
            "summary": "Test macro summary",
            "data": {
                "risk_sentiment": "BULLISH"
            }
        }
        
        mock_advanced = {
            "features": {
                "M5": {"rmag": {}, "vwap": {}, "vol_trend": {}, "pressure": {}},
                "M15": {},
                "H1": {}
            }
        }
        
        logger.info("Calling _format_unified_analysis with mock data...")
        result = _format_unified_analysis(
            symbol="XAUUSDc",
            symbol_normalized="XAUUSDc",
            current_price=2000.0,
            macro=mock_macro,
            smc=mock_smc,
            advanced_features=mock_advanced,
            decision={"direction": "BUY", "entry": 2000.0, "sl": 1990.0, "tp": 2010.0, "confidence": 75, "rr": 1.0},
            m5_data={},
            m15_data={},
            h1_data={}
        )
        
        # Verify response structure
        assert "data" in result, "Missing 'data' in response"
        assert "smc" in result["data"], "Missing 'smc' in response.data"
        
        smc_data = result["data"]["smc"]
        
        # Verify basic fields (backward compatibility)
        assert "choch_detected" in smc_data, "Missing 'choch_detected'"
        assert "bos_detected" in smc_data, "Missing 'bos_detected'"
        assert "trend" in smc_data, "Missing 'trend'"
        
        # Verify calculated values
        assert smc_data["choch_detected"] == True, f"Expected choch_detected=True, got {smc_data['choch_detected']}"
        assert smc_data["bos_detected"] == True, f"Expected bos_detected=True, got {smc_data['bos_detected']}"
        assert smc_data["trend"] == "BULLISH", f"Expected trend='BULLISH', got {smc_data['trend']}"
        
        logger.info(f"✅ Calculated choch_detected: {smc_data['choch_detected']}")
        logger.info(f"✅ Calculated bos_detected: {smc_data['bos_detected']}")
        logger.info(f"✅ Calculated trend: {smc_data['trend']}")
        
        # Verify new MTF fields
        required_mtf_fields = [
            "timeframes", "alignment_score", "recommendation",
            "market_bias", "trade_opportunities", "volatility_regime",
            "volatility_weights", "advanced_insights", "advanced_summary",
            "confidence_score"
        ]
        
        missing_fields = [f for f in required_mtf_fields if f not in smc_data]
        if missing_fields:
            logger.error(f"❌ Missing MTF fields: {missing_fields}")
            return False
        
        logger.info("✅ All MTF fields present")
        
        # Verify field values
        assert smc_data["timeframes"] == mock_smc["timeframes"], "timeframes mismatch"
        assert smc_data["alignment_score"] == 75, "alignment_score mismatch"
        assert smc_data["market_bias"]["trend"] == "BULLISH", "market_bias.trend mismatch"
        assert smc_data["confidence_score"] == 75, "confidence_score mismatch"
        
        logger.info("✅ All field values correct")
        logger.info("✅ Phase 1: _format_unified_analysis working correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Phase 1 test failed: {e}")
        logger.exception(e)
        return False


def test_edge_cases():
    """Test edge cases: None values, empty data, missing fields"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST: Edge Cases")
    logger.info("=" * 80)
    
    try:
        from desktop_agent import _format_unified_analysis
        
        # Test with None smc
        logger.info("Testing with None smc...")
        result = _format_unified_analysis(
            symbol="TEST",
            symbol_normalized="TEST",
            current_price=100.0,
            macro={"summary": "", "data": {}},
            smc=None,
            advanced_features={"features": {}},
            decision={},
            m5_data={},
            m15_data={},
            h1_data={}
        )
        
        smc_data = result["data"]["smc"]
        assert smc_data["choch_detected"] == False, "Should default to False"
        assert smc_data["bos_detected"] == False, "Should default to False"
        assert smc_data["trend"] == "UNKNOWN", "Should default to UNKNOWN"
        logger.info("✅ None smc handled correctly")
        
        # Test with empty timeframes
        logger.info("Testing with empty timeframes...")
        result = _format_unified_analysis(
            symbol="TEST",
            symbol_normalized="TEST",
            current_price=100.0,
            macro={"summary": "", "data": {}},
            smc={"timeframes": {}, "recommendation": {}},
            advanced_features={"features": {}},
            decision={},
            m5_data={},
            m15_data={},
            h1_data={}
        )
        
        smc_data = result["data"]["smc"]
        assert smc_data["choch_detected"] == False, "Should be False with empty timeframes"
        assert smc_data["bos_detected"] == False, "Should be False with empty timeframes"
        logger.info("✅ Empty timeframes handled correctly")
        
        # Test with None recommendation
        logger.info("Testing with None recommendation...")
        result = _format_unified_analysis(
            symbol="TEST",
            symbol_normalized="TEST",
            current_price=100.0,
            macro={"summary": "", "data": {}},
            smc={"timeframes": {}, "recommendation": None},
            advanced_features={"features": {}},
            decision={},
            m5_data={},
            m15_data={},
            h1_data={}
        )
        
        smc_data = result["data"]["smc"]
        assert smc_data["recommendation"] == {}, "Should default to empty dict"
        assert smc_data["market_bias"] == {}, "Should default to empty dict"
        logger.info("✅ None recommendation handled correctly")
        
        logger.info("✅ All edge cases handled correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Edge case test failed: {e}")
        logger.exception(e)
        return False


def main():
    """Run all tests"""
    logger.info("Starting MTF CHOCH/BOS Implementation Tests")
    logger.info("")
    
    results = []
    
    # Test Phase 0
    results.append(("Phase 0: CHOCH/BOS Detection", test_mtf_analyzer_choch_bos()))
    
    # Test Phase 1
    results.append(("Phase 1: _format_unified_analysis", test_format_unified_analysis()))
    
    # Test Edge Cases
    results.append(("Edge Cases", test_edge_cases()))
    
    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    logger.info("")
    if all_passed:
        logger.info("🎉 ALL TESTS PASSED!")
        return 0
    else:
        logger.error("❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

