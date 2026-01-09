"""
Test Volatility Regime Integration - Phase 1

Tests that volatility regime detection is properly integrated into
the analysis flow and displays correctly in the response.
"""
import sys
import logging
import asyncio
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_analysis_integration():
    """Test that volatility regime detection is integrated into analysis"""
    try:
        # Import the desktop agent registry
        import desktop_agent
        from desktop_agent import registry
        
        # Ensure MT5 is initialized
        if not registry.mt5_service:
            from infra.mt5_service import MT5Service
            registry.mt5_service = MT5Service()
            if not registry.mt5_service.connect():
                logger.error("❌ Failed to connect to MT5")
                return False
        
        logger.info("✅ MT5 connected")
        
        # Get the analysis tool
        tool_func = registry.tools.get("moneybot.analyse_symbol_full")
        if not tool_func:
            logger.error("❌ Analysis tool not found")
            return False
        
        logger.info("✅ Analysis tool found")
        
        # Test with BTCUSD
        test_symbol = "BTCUSD"
        logger.info(f"\n{'='*70}")
        logger.info(f"Testing volatility regime integration with {test_symbol}")
        logger.info(f"{'='*70}\n")
        
        # Run analysis
        result = await tool_func({"symbol": test_symbol})
        
        # Check if result contains volatility regime
        summary = result.get("summary", "")
        data = result.get("data", {})
        
        # Check summary for volatility regime display
        has_regime_in_summary = (
            "VOLATILITY REGIME" in summary or
            "volatility regime" in summary.lower() or
            "⚡" in summary or
            "🟡" in summary or
            "🟢" in summary
        )
        
        # Check data for volatility regime
        volatility_regime = data.get("volatility_regime")
        has_regime_in_data = volatility_regime is not None
        
        logger.info(f"\n{'='*70}")
        logger.info("INTEGRATION TEST RESULTS")
        logger.info(f"{'='*70}")
        
        logger.info(f"\n📊 Summary contains regime: {has_regime_in_summary}")
        if has_regime_in_summary:
            # Extract regime line from summary
            lines = summary.split("\n")
            for line in lines:
                if "VOLATILITY REGIME" in line or "volatility regime" in line.lower():
                    logger.info(f"   Found: {line.strip()}")
                    break
        
        logger.info(f"\n📦 Data contains regime: {has_regime_in_data}")
        if has_regime_in_data:
            regime = volatility_regime.get("regime")
            confidence = volatility_regime.get("confidence", 0)
            atr_ratio = volatility_regime.get("atr_ratio", 0)
            
            regime_str = regime.value if hasattr(regime, 'value') else str(regime)
            logger.info(f"   Regime: {regime_str}")
            logger.info(f"   Confidence: {confidence}%")
            logger.info(f"   ATR Ratio: {atr_ratio:.2f}x")
        
        # Overall result
        if has_regime_in_summary and has_regime_in_data:
            logger.info(f"\n✅ INTEGRATION TEST PASSED")
            logger.info("   Volatility regime detection is properly integrated!")
            return True
        else:
            logger.warning(f"\n⚠️ INTEGRATION TEST INCOMPLETE")
            if not has_regime_in_summary:
                logger.warning("   Regime not found in summary")
            if not has_regime_in_data:
                logger.warning("   Regime not found in data")
            return False
        
    except Exception as e:
        logger.error(f"❌ Integration test failed: {e}", exc_info=True)
        return False


async def test_summary_formatting():
    """Test that the summary formatting function works correctly"""
    try:
        from desktop_agent import _format_volatility_regime_display
        from infra.volatility_regime_detector import VolatilityRegime
        
        logger.info(f"\n{'='*70}")
        logger.info("Testing Summary Formatting")
        logger.info(f"{'='*70}\n")
        
        # Test with VOLATILE regime
        volatile_regime = {
            "regime": VolatilityRegime.VOLATILE,
            "confidence": 85.5,
            "atr_ratio": 1.62
        }
        
        display = _format_volatility_regime_display(volatile_regime)
        logger.info("VOLATILE regime display:")
        logger.info(display)
        
        assert "VOLATILE" in display
        assert "⚡" in display
        assert "85.5" in display or "85" in display
        assert "1.62" in display or "1.6" in display
        logger.info("✅ VOLATILE formatting test passed")
        
        # Test with STABLE regime
        stable_regime = {
            "regime": VolatilityRegime.STABLE,
            "confidence": 92.0,
            "atr_ratio": 1.05
        }
        
        display = _format_volatility_regime_display(stable_regime)
        logger.info("\nSTABLE regime display:")
        logger.info(display)
        
        assert "STABLE" in display
        assert "🟢" in display
        logger.info("✅ STABLE formatting test passed")
        
        # Test with TRANSITIONAL regime
        transitional_regime = {
            "regime": VolatilityRegime.TRANSITIONAL,
            "confidence": 75.0,
            "atr_ratio": 1.3
        }
        
        display = _format_volatility_regime_display(transitional_regime)
        logger.info("\nTRANSITIONAL regime display:")
        logger.info(display)
        
        assert "TRANSITIONAL" in display
        assert "🟡" in display
        logger.info("✅ TRANSITIONAL formatting test passed")
        
        # Test with None
        display = _format_volatility_regime_display(None)
        assert display == ""
        logger.info("✅ None handling test passed")
        
        logger.info(f"\n✅ All formatting tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Formatting test failed: {e}", exc_info=True)
        return False


async def run_all_tests():
    """Run all integration tests"""
    logger.info("\n" + "="*70)
    logger.info("VOLATILITY REGIME INTEGRATION TEST SUITE")
    logger.info("="*70)
    
    tests = [
        ("Summary Formatting", test_summary_formatting),
        ("Analysis Integration", test_analysis_integration),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"❌ {test_name} ERROR: {e}", exc_info=True)
            failed += 1
    
    logger.info("\n" + "="*70)
    logger.info(f"TEST SUMMARY: {passed} passed, {failed} failed")
    logger.info("="*70)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)

