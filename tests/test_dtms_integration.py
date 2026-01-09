"""
Test DTMS Integration
Comprehensive test to verify DTMS ChatGPT access integration
"""

import asyncio
import httpx
import logging
from desktop_agent import tool_dtms_status, tool_dtms_trade_info, tool_dtms_action_history

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_api_server():
    """Test if DTMS API server is running and accessible"""
    print("🔍 Testing DTMS API Server...")
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Test health endpoint
            response = await client.get("http://127.0.0.1:8001/health")
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ API Server Health: {health_data['status']}")
                print(f"   DTMS Available: {health_data.get('dtms_available', False)}")
                return True
            else:
                print(f"❌ API Server Health Check Failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ API Server Not Accessible: {e}")
        return False

async def test_dtms_status_api():
    """Test DTMS status API endpoint"""
    print("\n🔍 Testing DTMS Status API...")
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://127.0.0.1:8001/dtms/status")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ DTMS Status API: {data['summary']}")
                print(f"   Success: {data.get('success', False)}")
                return data
            else:
                print(f"❌ DTMS Status API Failed: {response.status_code}")
                return None
    except Exception as e:
        print(f"❌ DTMS Status API Error: {e}")
        return None

async def test_chatgpt_tools():
    """Test ChatGPT DTMS tools"""
    print("\n🔍 Testing ChatGPT DTMS Tools...")
    
    # Test DTMS Status Tool
    print("Testing moneybot.dtms_status...")
    try:
        result = await tool_dtms_status({})
        print(f"✅ DTMS Status Tool: {result.get('summary', 'No summary')}")
        print(f"   Success: {result.get('success', False)}")
        print(f"   Uses API: {'API not available' not in result.get('summary', '')}")
    except Exception as e:
        print(f"❌ DTMS Status Tool Error: {e}")
    
    # Test DTMS Trade Info Tool
    print("\nTesting moneybot.dtms_trade_info...")
    try:
        result = await tool_dtms_trade_info({"ticket": 123456})
        print(f"✅ DTMS Trade Info Tool: {result.get('summary', 'No summary')}")
        print(f"   Success: {result.get('success', False)}")
    except Exception as e:
        print(f"❌ DTMS Trade Info Tool Error: {e}")
    
    # Test DTMS Action History Tool
    print("\nTesting moneybot.dtms_action_history...")
    try:
        result = await tool_dtms_action_history({})
        print(f"✅ DTMS Action History Tool: {result.get('summary', 'No summary')}")
        print(f"   Success: {result.get('success', False)}")
    except Exception as e:
        print(f"❌ DTMS Action History Tool Error: {e}")

async def test_integration_status():
    """Test overall integration status"""
    print("\n🔍 Testing Integration Status...")
    
    # Test API server
    api_available = await test_api_server()
    
    # Test API endpoints
    dtms_data = await test_dtms_status_api()
    
    # Test ChatGPT tools
    await test_chatgpt_tools()
    
    # Summary
    print("\n📊 Integration Status Summary:")
    print(f"   API Server: {'✅ Available' if api_available else '❌ Not Available'}")
    print(f"   DTMS System: {'✅ Available' if dtms_data and dtms_data.get('success') else '❌ Not Available'}")
    print(f"   ChatGPT Tools: {'✅ Working' if api_available else '⚠️ Fallback Mode'}")
    
    if api_available and dtms_data and dtms_data.get('success'):
        print("\n🎉 INTEGRATION FULLY WORKING!")
        print("   ChatGPT can access live DTMS data")
    elif api_available:
        print("\n⚠️ INTEGRATION PARTIALLY WORKING")
        print("   API server is running but DTMS system is not initialized")
        print("   Need to restart bot with new integration")
    else:
        print("\n❌ INTEGRATION NOT WORKING")
        print("   API server is not running")
        print("   Need to start bot with new integration")

async def main():
    """Main test function"""
    print("🛡️ DTMS ChatGPT Integration Test")
    print("=" * 50)
    
    await test_integration_status()
    
    print("\n" + "=" * 50)
    print("Test Complete!")

if __name__ == "__main__":
    asyncio.run(main())
