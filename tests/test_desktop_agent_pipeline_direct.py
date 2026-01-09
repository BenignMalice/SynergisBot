"""
Test Desktop Agent Pipeline Integration Directly
"""

import asyncio

async def test_desktop_agent_pipeline_direct():
    print('🚀 Testing Desktop Agent Pipeline Integration Directly')
    print('=' * 60)
    
    # Test direct initialization
    print('🔧 Initializing Unified Tick Pipeline...')
    try:
        # Initialize the pipeline directly
        from unified_tick_pipeline_integration import initialize_unified_pipeline
        result = await initialize_unified_pipeline()
        print(f'   → Pipeline Initialization Result: {result}')
        
        if result:
            print('   ✅ Unified Tick Pipeline initialized successfully!')
            
            # Initialize DTMS
            try:
                from dtms_unified_pipeline_integration import initialize_dtms_unified_pipeline
                dtms_result = await initialize_dtms_unified_pipeline()
                print(f'   → DTMS Initialization Result: {dtms_result}')
            except Exception as e:
                print(f'   → DTMS Initialization failed: {e}')
            
            # Initialize Intelligent Exits
            try:
                from intelligent_exits_unified_pipeline_integration import initialize_intelligent_exits_unified_pipeline
                exits_result = await initialize_intelligent_exits_unified_pipeline()
                print(f'   → Intelligent Exits Initialization Result: {exits_result}')
            except Exception as e:
                print(f'   → Intelligent Exits Initialization failed: {e}')
            
            # Test if pipeline is available
            from unified_tick_pipeline_integration import get_pipeline_instance
            pipeline = get_pipeline_instance()
            
            if pipeline:
                print('   ✅ Pipeline instance available')
                print(f'      → Pipeline type: {type(pipeline).__name__}')
                
                # Initialize Desktop Agent integration
                try:
                    from desktop_agent_unified_pipeline_integration import initialize_desktop_agent_unified_pipeline
                    agent_result = await initialize_desktop_agent_unified_pipeline()
                    print(f'   → Desktop Agent Integration Result: {agent_result}')
                except Exception as e:
                    print(f'   → Desktop Agent Integration failed: {e}')
                
                # Test a simple tool
                try:
                    from desktop_agent_unified_pipeline_integration import tool_system_health
                    health = await tool_system_health({})
                    print(f'   ✅ System health tool working: {health.get("success", False)}')
                    print(f'      → Health data: {health}')
                except Exception as e:
                    print(f'   ❌ System health tool failed: {e}')
                
                return True
            else:
                print('   ❌ Pipeline instance not available after initialization')
                return False
        else:
            print('   ❌ Unified Tick Pipeline initialization failed')
            return False
            
    except Exception as e:
        print(f'   ❌ Error during initialization: {e}')
        return False

if __name__ == "__main__":
    success = asyncio.run(test_desktop_agent_pipeline_direct())
    if success:
        print('')
        print('🎉 DESKTOP AGENT PIPELINE INTEGRATION IS WORKING!')
    else:
        print('')
        print('❌ DESKTOP AGENT PIPELINE INTEGRATION FAILED')
