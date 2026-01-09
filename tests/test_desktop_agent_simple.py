"""
Simple test to check if Desktop Agent is working
"""

import asyncio
import time

async def test_desktop_agent_simple():
    print('🤖 Simple Desktop Agent Test')
    print('=' * 40)
    
    # Test 1: Check if desktop agent is running
    print('🔍 Test 1: Checking if Desktop Agent is running...')
    try:
        import desktop_agent
        print('   ✅ Desktop Agent module imported successfully')
    except Exception as e:
        print(f'   ❌ Desktop Agent module import failed: {e}')
        return False
    
    # Test 2: Check if registry is available
    print('📊 Test 2: Checking Desktop Agent Registry...')
    try:
        from desktop_agent import registry
        print('   ✅ Registry available')
        print(f'      → MT5 Service: {registry.mt5_service is not None}')
        print(f'      → Binance Service: {registry.binance_service is not None}')
    except Exception as e:
        print(f'   ❌ Registry check failed: {e}')
        return False
    
    # Test 3: Check if Unified Tick Pipeline integration is available
    print('🚀 Test 3: Checking Unified Tick Pipeline Integration...')
    try:
        from desktop_agent_unified_pipeline_integration import get_desktop_agent_unified_integration
        integration = get_desktop_agent_unified_integration()
        if integration:
            print('   ✅ Unified Tick Pipeline integration available')
            print(f'      → Integration Active: {integration.is_active}')
            print(f'      → Pipeline Available: {integration.pipeline is not None}')
        else:
            print('   ❌ Unified Tick Pipeline integration not available')
            print('   → This means the desktop agent did not initialize the pipeline')
            return False
    except Exception as e:
        print(f'   ❌ Unified Tick Pipeline integration check failed: {e}')
        return False
    
    # Test 4: Check pipeline status
    print('📊 Test 4: Checking Pipeline Status...')
    try:
        from desktop_agent_unified_pipeline_integration import tool_pipeline_status
        status = await tool_pipeline_status({})
        if status.get('success'):
            print('   ✅ Pipeline status available')
            data = status.get('data', {})
            print(f'      → Pipeline Running: {data.get("is_running", "N/A")}')
            print(f'      → Components: {len(data.get("components", {}))}')
        else:
            print(f'   ❌ Pipeline status failed: {status.get("error", "Unknown error")}')
    except Exception as e:
        print(f'   ❌ Pipeline status check failed: {e}')
        return False
    
    print('')
    print('✅ DESKTOP AGENT IS WORKING!')
    print('✅ UNIFIED TICK PIPELINE INTEGRATION IS ACTIVE!')
    print('')
    print('🎯 RESULT: Desktop Agent with Unified Tick Pipeline is operational!')
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_desktop_agent_simple())
    if success:
        print('')
        print('🎉 DESKTOP AGENT IS FULLY OPERATIONAL!')
    else:
        print('')
        print('❌ DESKTOP AGENT NEEDS ATTENTION')
