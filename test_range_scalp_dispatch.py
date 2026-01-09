"""
Test Range Scalping Tool via /dispatch API Endpoint

This test uses the existing /dispatch endpoint which the system uses.
No external dependencies required - uses urllib which is built-in.

Usage:
    python test_range_scalp_dispatch.py BTCUSD
"""

import json
import urllib.request
import urllib.error
import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_range_scalp_dispatch(symbol: str = "BTCUSDccl", base_url: str = "http://localhost:8000"):
    """Test range scalping tool via /dispatch endpoint"""
    
    logger.info("=" * 80)
    logger.info(f"🧪 DISPATCH API TEST: Range Scalping Analysis")
    logger.info(f"Symbol: {symbol}")
    logger.info(f"API URL: {base_url}")
    logger.info("=" * 80)
    
    try:
        # Prepare request
        endpoint = f"{base_url}/dispatch"
        
        payload = {
            "tool": "moneybot.analyse_range_scalp_opportunity",
            "arguments": {
                "symbol": symbol,
                "check_risk_filters": True
            },
            "timeout": 30
        }
        
        # Get phone bearer token from environment or use default
        # (This should match what's in your API config)
        phone_token = "phone_control_bearer_token_2025_v1_secure"  # Default from docs
        
        logger.info(f"📡 Calling {endpoint}")
        logger.info(f"   Tool: {payload['tool']}")
        logger.info(f"   Symbol: {symbol}")
        logger.info("-" * 80)
        
        # Create request
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {phone_token}",
                "X-Phone-Token": phone_token  # Some APIs use this header
            }
        )
        
        # Make request
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                result = json.loads(response.read().decode('utf-8'))
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else "No error body"
            logger.error(f"❌ HTTP Error {e.code}: {e.reason}")
            logger.error(f"   Response: {error_body}")
            return False
        
        # Display results
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 API RESPONSE")
        logger.info("=" * 80)
        
        # Check response structure
        if result.get("status") == "error":
            logger.error(f"❌ Error: {result.get('error', 'Unknown error')}")
            logger.error(f"   Summary: {result.get('summary', 'N/A')}")
            return False
        
        # Get data (could be in result.data or result directly)
        data = result.get("data", result)
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        
        summary = result.get("summary", data.get("summary", "N/A"))
        logger.info(f"Summary: {summary}")
        logger.info("")
        
        # Range detection
        if data.get("range_detected"):
            logger.info("✅ Range Detected")
            range_struct = data.get("range_structure", {})
            logger.info(f"   Type: {range_struct.get('range_type', 'unknown')}")
            logger.info(f"   High: {range_struct.get('range_high', 0):.2f}")
            logger.info(f"   Low: {range_struct.get('range_low', 0):.2f}")
            logger.info(f"   Mid: {range_struct.get('range_mid', 0):.2f}")
            logger.info(f"   Width (ATR): {range_struct.get('range_width_atr', 0):.2f}")
        else:
            logger.warning("⚠️ No range detected")
            if data.get("error"):
                logger.error(f"   Error: {data['error']}")
        
        # Risk checks
        risk_checks = data.get("risk_checks", {})
        if risk_checks:
            logger.info("")
            logger.info("🔍 Risk Checks:")
            
            if risk_checks.get("risk_filters_skipped"):
                logger.info("   ⚠️ Risk filters were skipped")
            else:
                confluence_score = risk_checks.get("confluence_score", 0)
                logger.info(f"   3-Confluence Score: {confluence_score}/100")
                logger.info(f"   Confluence Passed: {'✅' if risk_checks.get('3_confluence_passed') else '❌'}")
                
                if risk_checks.get("false_range_detected"):
                    logger.warning(f"   ❌ False Range: {', '.join(risk_checks.get('false_range_flags', []))}")
                else:
                    logger.info("   ✅ False Range: None")
                
                logger.info(f"   Range Valid: {'✅' if risk_checks.get('range_valid') else '❌'}")
                logger.info(f"   Session Allows: {'✅' if risk_checks.get('session_allows_trading') else '❌'}")
                logger.info(f"   Trade Activity: {'✅' if risk_checks.get('trade_activity_sufficient') else '❌'}")
                logger.info(f"   Overall: {'✅ PASSED' if risk_checks.get('risk_passed') else '❌ FAILED'}")
        
        # Top strategy
        top_strategy = data.get("top_strategy")
        logger.info("")
        if top_strategy:
            logger.info("🎯 Top Strategy:")
            logger.info(f"   Name: {top_strategy.get('name', 'unknown')}")
            logger.info(f"   Direction: {top_strategy.get('direction', 'N/A')}")
            logger.info(f"   Entry: {top_strategy.get('entry_price', 0):.2f}")
            logger.info(f"   SL: {top_strategy.get('stop_loss', 0):.2f}")
            logger.info(f"   TP: {top_strategy.get('take_profit', 0):.2f}")
            logger.info(f"   R:R: {top_strategy.get('r_r_ratio', 0):.2f}")
            logger.info(f"   Confidence: {top_strategy.get('confidence', 0)}/100")
        else:
            logger.warning("⚠️ No top strategy found")
        
        # Warnings
        warnings = data.get("warnings", [])
        if warnings:
            logger.info("")
            logger.info("⚠️ Warnings:")
            for warning in warnings:
                logger.warning(f"   • {warning}")
        
        # Execution time
        exec_time = result.get("execution_time", 0)
        logger.info("")
        logger.info(f"⏱️  Execution Time: {exec_time:.2f}s")
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ DISPATCH API TEST COMPLETE")
        logger.info("=" * 80)
        
        return True
        
    except urllib.error.URLError as e:
        logger.error(f"❌ Connection error: {e}")
        logger.info("\n💡 Make sure:")
        logger.info("   1. API server is running (app/main_api.py)")
        logger.info("   2. Desktop agent is connected (desktop_agent.py)")
        logger.info("   3. Port 8000 is accessible")
        return False
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "BTCUSD"
    
    logger.info("⚠️  Prerequisites:")
    logger.info("   1. API server running (app/main_api.py on port 8000)")
    logger.info("   2. Desktop agent connected (desktop_agent.py)")
    logger.info("   3. Tool registered in desktop_agent.py")
    logger.info("")
    
    success = test_range_scalp_dispatch(symbol)
    
    sys.exit(0 if success else 1)

