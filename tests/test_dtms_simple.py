"""
Simple DTMS API Server Test
"""

import asyncio
import httpx
from desktop_agent import tool_dtms_status

async def test_dtms_api_server():
    print("🔍 Testing DTMS API Server...")
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Test health endpoint
            response = await client.get("http://127.0.0.1:8001/health")
            print(f"✅ Health endpoint: {response.status_code}")
            health_data = response.json()
            print(f"   Status: {health_data['status']}")
            print(f"   DTMS Available: {health_data.get('dtms_available', False)}")
            
            # Test DTMS status endpoint
            response = await client.get("http://127.0.0.1:8001/dtms/status")
            print(f"✅ DTMS status endpoint: {response.status_code}")
            dtms_data = response.json()
            print(f"   Summary: {dtms_data['summary']}")
            print(f"   Success: {dtms_data.get('success', False)}")
            
    except Exception as e:
        print(f"❌ API Server Error: {e}")

async def test_chatgpt_tool():
    print("\n🔍 Testing ChatGPT DTMS Tool...")
    
    try:
        result = await tool_dtms_status({})
        print(f"✅ Tool Result: {result.get('summary')}")
        print(f"✅ Success: {result.get('success')}")
        
        # Check if it's using API (not falling back)
        summary = result.get('summary', '')
        uses_api = 'API not available' not in summary
        print(f"✅ Uses API: {uses_api}")
        
    except Exception as e:
        print(f"❌ ChatGPT Tool Error: {e}")

async def main():
    print("🛡️ DTMS API Server Test")
    print("=" * 40)
    
    await test_dtms_api_server()
    await test_chatgpt_tool()
    
    print("\n" + "=" * 40)
    print("✅ Test Complete!")

if __name__ == "__main__":
    asyncio.run(main())
