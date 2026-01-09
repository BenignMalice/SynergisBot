"""
Integration Test for Range Scalping System
Tests via desktop_agent.py tool registry (requires running desktop agent)

Usage:
    1. Start desktop_agent.py
    2. Run: python test_range_scalping_integration.py BTCUSD
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_via_desktop_agent(symbol: str = "BTCUSD"):
    """Test range scalping via desktop_agent tool registry"""
    
    logger.info("=" * 80)
    logger.info(f"🧪 INTEGRATION TEST: Range Scalping via Desktop Agent")
    logger.info(f"Symbol: {symbol}")
    logger.info("=" * 80)
    
    try:
        # Import desktop_agent components
        from desktop_agent import registry
        
        # Check if tool is registered
        tool_name = "moneybot.analyse_range_scalp_opportunity"
        if tool_name not in registry.tools:
            logger.error(f"❌ Tool {tool_name} not registered in desktop_agent")
            logger.info("💡 Make sure desktop_agent.py has been updated with tool registration")
            return False
        
        logger.info(f"✅ Tool {tool_name} is registered")
        
        # Prepare arguments
        args = {
            "symbol": symbol,
            "check_risk_filters": True
        }
        
        # Execute tool
        logger.info("📊 Executing range scalping analysis...")
        result = await registry.execute(tool_name, args)
        
        # Display results
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 ANALYSIS RESULTS")
        logger.info("=" * 80)
        
        data = result.get("data", {})
        
        if data.get("error"):
            logger.error(f"❌ Error: {data['error']}")
            if data.get("warnings"):
                for warning in data["warnings"]:
                    logger.warning(f"⚠️ {warning}")
            return False
        
        # Display summary
        summary = result.get("summary", "N/A")
        logger.info(f"Summary: {summary}")
        
        # Range detection
        if data.get("range_detected"):
            logger.info("✅ Range Detected")
            range_structure = data.get("range_structure", {})
            logger.info(f"   Type: {range_structure.get('range_type', 'unknown')}")
            logger.info(f"   High: {range_structure.get('range_high', 0):.2f}")
            logger.info(f"   Low: {range_structure.get('range_low', 0):.2f}")
            logger.info(f"   Mid: {range_structure.get('range_mid', 0):.2f}")
        
        # Risk checks
        risk_checks = data.get("risk_checks", {})
        if risk_checks.get("confluence_score") is not None:
            logger.info(f"🔍 3-Confluence Score: {risk_checks.get('confluence_score', 0)}/100")
        
        # Top strategy
        top_strategy = data.get("top_strategy")
        if top_strategy:
            logger.info("")
            logger.info("🎯 Top Strategy:")
            logger.info(f"   Name: {top_strategy.get('name', 'unknown')}")
            logger.info(f"   Direction: {top_strategy.get('direction', 'N/A')}")
            logger.info(f"   Entry: {top_strategy.get('entry_price', 0):.2f}")
            logger.info(f"   SL: {top_strategy.get('stop_loss', 0):.2f}")
            logger.info(f"   TP: {top_strategy.get('take_profit', 0):.2f}")
            logger.info(f"   R:R: {top_strategy.get('r_r_ratio', 0):.2f}")
            logger.info(f"   Confidence: {top_strategy.get('confidence', 0)}/100")
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ INTEGRATION TEST COMPLETE")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Integration test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    # Get symbol from command line or use default
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSD"
    
    logger.info("⚠️  This test requires desktop_agent.py to be running")
    logger.info("⚠️  Run: python desktop_agent.py (in another terminal)")
    logger.info("")
    
    success = asyncio.run(test_via_desktop_agent(symbol))
    
    sys.exit(0 if success else 1)

