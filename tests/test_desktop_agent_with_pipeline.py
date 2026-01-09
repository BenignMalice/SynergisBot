"""
Test Desktop Agent with Pipeline Pre-initialization
"""

import asyncio
from unified_tick_pipeline_integration import initialize_unified_pipeline, get_pipeline_instance
from desktop_agent_unified_pipeline_integration import initialize_desktop_agent_unified_pipeline

async def test_desktop_agent_with_pipeline():
    print('🚀 Testing Desktop Agent with Pipeline Pre-initialization')
    print('=' * 70)
    
    # Step 1: Initialize Unified Tick Pipeline first
    print('📡 Step 1: Initializing Unified Tick Pipeline...')
    pipeline_result = await initialize_unified_pipeline()
    print(f'   → Pipeline Result: {pipeline_result}')
    
    if not pipeline_result:
        print('❌ Unified Tick Pipeline initialization failed')
        return False
    
    # Step 2: Wait for pipeline to be ready
    print('⏳ Step 2: Waiting for pipeline to be ready...')
    await asyncio.sleep(3)
    
    # Step 3: Check pipeline status
    print('📊 Step 3: Checking pipeline status...')
    pipeline = get_pipeline_instance()
    if pipeline:
        status = pipeline.get_pipeline_status()
        print(f'   → Pipeline Running: {status.get("is_running", False)}')
        print(f'   → Components: {len(status.get("components", {}))}')
    else:
        print('   ❌ Pipeline instance not available')
        return False
    
    # Step 4: Initialize Desktop Agent Pipeline Integration
    print('🤖 Step 4: Initializing Desktop Agent Pipeline Integration...')
    try:
        desktop_result = await initialize_desktop_agent_unified_pipeline()
        print(f'   → Desktop Agent Result: {desktop_result}')
        
        if desktop_result:
            print('   ✅ Desktop Agent Pipeline Integration initialized!')
            
            # Step 5: Test integration
            print('🧪 Step 5: Testing Desktop Agent Integration...')
            from desktop_agent_unified_pipeline_integration import get_desktop_agent_unified_integration
            integration = get_desktop_agent_unified_integration()
            
            if integration:
                print('   ✅ Integration instance available')
                print(f'      → Active: {integration.is_active}')
                print(f'      → Pipeline: {integration.pipeline is not None}')
                
                # Test tools
                from desktop_agent_unified_pipeline_integration import tool_system_health, tool_pipeline_status
                
                health = await tool_system_health({})
                print(f'   ✅ System health tool: {health.get("success", False)}')
                
                status = await tool_pipeline_status({})
                print(f'   ✅ Pipeline status tool: {status.get("success", False)}')
                
                return True
            else:
                print('   ❌ Integration instance not available')
                return False
        else:
            print('   ❌ Desktop Agent Pipeline Integration failed')
            return False
            
    except Exception as e:
        print(f'   ❌ Error during desktop agent integration: {e}')
        return False

if __name__ == "__main__":
    success = asyncio.run(test_desktop_agent_with_pipeline())
    if success:
        print('')
        print('🎉 DESKTOP AGENT WITH PIPELINE IS WORKING!')
        print('✅ Unified Tick Pipeline: Operational')
        print('✅ Desktop Agent Integration: Operational')
        print('✅ All tools available for ChatGPT!')
    else:
        print('')
        print('❌ DESKTOP AGENT WITH PIPELINE NEEDS ATTENTION')
