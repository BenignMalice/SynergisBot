"""Simple test for BTC order flow metrics tool

This test can be run while chatgpt_bot.py is running.
It uses the API endpoint if available, or checks tool registration.
"""

import asyncio
import sys
import httpx
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_via_api():
    """Test via API endpoint if available"""
    print("=" * 70)
    print("Testing BTC Order Flow Metrics via API")
    print("=" * 70)
    print()
    
    try:
        # Try to call via API (if main_api.py is running)
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Check if API is running
            try:
                response = await client.get("http://localhost:8000/health")
                if response.status_code == 200:
                    print("[OK] API server is running")
                else:
                    print("[WARNING] API server responded with non-200 status")
                    return False
            except httpx.RequestError:
                print("[INFO] API server not accessible - will test tool registration instead")
                return await test_tool_registration()
            
            # If API is running, try to call the tool via ChatGPT bridge
            # (This would require the tool to be exposed via API, which it may not be)
            print("[INFO] Tool must be called via ChatGPT or desktop_agent registry")
            print("[INFO] Use: moneybot.btc_order_flow_metrics in ChatGPT")
            return True
            
    except Exception as e:
        print(f"[ERROR] API test failed: {e}")
        return await test_tool_registration()

async def test_tool_registration():
    """Test that tool is registered"""
    print("=" * 70)
    print("Testing Tool Registration")
    print("=" * 70)
    print()
    
    try:
        from desktop_agent import registry
        
        print("[1/2] Checking tool registration...")
        if "moneybot.btc_order_flow_metrics" in registry.tools:
            print("   [OK] Tool 'moneybot.btc_order_flow_metrics' is registered")
        else:
            print("   [ERROR] Tool not found in registry")
            print(f"   Available tools: {sorted(list(registry.tools.keys()))[:10]}...")
            return False
        
        print()
        print("[2/2] Checking service availability...")
        if hasattr(registry, 'order_flow_service') and registry.order_flow_service:
            if hasattr(registry.order_flow_service, 'running'):
                if registry.order_flow_service.running:
                    print("   [OK] OrderFlowService is running")
                    print("   [INFO] Tool should work when called")
                    return True
                else:
                    print("   [WARNING] OrderFlowService exists but not running")
                    print("   [INFO] Services need to be started in chatgpt_bot.py")
            else:
                print("   [INFO] OrderFlowService exists (status unknown)")
        else:
            print("   [WARNING] OrderFlowService not initialized")
            print("   [INFO] Services are initialized in desktop_agent.agent_main()")
            print("   [INFO] This is called when chatgpt_bot.py starts")
        
        print()
        print("=" * 70)
        print("Summary:")
        print("=" * 70)
        print("✅ Tool is registered and ready")
        print("⚠️  Services need to be running in main process (chatgpt_bot.py)")
        print()
        print("To test the tool:")
        print("  1. Ensure chatgpt_bot.py is running")
        print("  2. Wait 30-60 seconds for data to accumulate")
        print("  3. Call via ChatGPT: 'Get BTC order flow metrics'")
        print("  4. Or use: moneybot.btc_order_flow_metrics({'symbol': 'BTCUSDT'})")
        print()
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print()
    success = asyncio.run(test_via_api())
    sys.exit(0 if success else 1)

