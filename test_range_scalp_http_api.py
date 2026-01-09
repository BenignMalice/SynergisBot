"""
HTTP API Test for Range Scalping Tool
Tests the tool via HTTP API endpoint

Usage:
    python test_range_scalp_http_api.py BTCUSD
    python test_range_scalp_http_api.py XAUUSD --port 8000
"""

import requests
import json
import logging
import sys
import argparse
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_range_scalp_http_api(symbol: str = "BTCUSD", base_url: str = "http://localhost:8000"):
    """Test range scalping tool via HTTP API"""
    
    logger.info("=" * 80)
    logger.info(f"🧪 HTTP API TEST: Range Scalping Analysis")
    logger.info(f"Symbol: {symbol}")
    logger.info(f"API URL: {base_url}")
    logger.info("=" * 80)
    
    try:
        # Test 1: Check if API server is running
        logger.info("📡 Checking API server status...")
        try:
            health_response = requests.get(f"{base_url}/health", timeout=5)
            if health_response.status_code == 200:
                logger.info("✅ API server is running")
            else:
                logger.warning(f"⚠️ API server returned status {health_response.status_code}")
        except requests.exceptions.ConnectionError:
            logger.error(f"❌ Cannot connect to API server at {base_url}")
            logger.info("\n💡 Make sure desktop_agent.py API server is running")
            logger.info("   Or specify different URL with --url argument")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Health check failed: {e}")
            logger.info("   Continuing anyway...")
        
        # Test 2: Call range scalping tool
        logger.info("")
        logger.info("📊 Calling range scalping analysis tool...")
        
        # Prepare API request
        api_endpoint = f"{base_url}/api/v1/tools/execute"
        
        payload = {
            "tool": "moneybot.analyse_range_scalp_opportunity",
            "arguments": {
                "symbol": symbol,
                "check_risk_filters": True
            }
        }
        
        logger.info(f"   Endpoint: {api_endpoint}")
        logger.info(f"   Payload: {json.dumps(payload, indent=2)}")
        logger.info("-" * 80)
        
        # Make API call
        response = requests.post(
            api_endpoint,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        # Check response
        if response.status_code != 200:
            logger.error(f"❌ API call failed with status {response.status_code}")
            logger.error(f"   Response: {response.text}")
            return False
        
        result = response.json()
        
        # Display results
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 API RESPONSE")
        logger.info("=" * 80)
        
        # Check for errors
        if "error" in result:
            logger.error(f"❌ Error: {result['error']}")
            if "details" in result:
                logger.error(f"   Details: {result['details']}")
            return False
        
        # Get data
        data = result.get("data", result)  # Some APIs return data directly
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
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ HTTP API TEST COMPLETE")
        logger.info("=" * 80)
        
        return True
        
    except requests.exceptions.Timeout:
        logger.error("❌ API call timed out (>30s)")
        logger.info("   Analysis may be taking longer than expected")
        return False
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Cannot connect to API server at {base_url}")
        logger.info("\n💡 Make sure API server is running:")
        logger.info("   - Check if desktop_agent.py has API server started")
        logger.info("   - Verify the URL and port are correct")
        return False
    except Exception as e:
        logger.error(f"❌ HTTP API test failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test range scalping tool via HTTP API")
    parser.add_argument("symbol", nargs="?", default="BTCUSD", help="Trading symbol")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--port", type=int, help="API port (overrides --url port)")
    
    args = parser.parse_args()
    
    # Adjust URL if port specified
    if args.port:
        base_url = f"http://localhost:{args.port}"
    else:
        base_url = args.url
    
    logger.info("⚠️  Make sure API server is running")
    logger.info(f"   Expected URL: {base_url}")
    logger.info("")
    
    success = test_range_scalp_http_api(args.symbol, base_url)
    
    sys.exit(0 if success else 1)

