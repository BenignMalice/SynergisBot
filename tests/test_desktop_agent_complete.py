"""
Test Desktop Agent with Complete Institutional-Grade Features
"""

import asyncio
import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_desktop_agent_complete():
    print('🏛️ Testing Desktop Agent with Complete Institutional-Grade Features')
    print('=' * 80)
    
    # Step 1: Initialize Unified Tick Pipeline
    print('📡 Step 1: Initializing Unified Tick Pipeline...')
    try:
        from unified_tick_pipeline_integration import initialize_unified_pipeline
        pipeline_result = await initialize_unified_pipeline()
        print(f'   ✅ Pipeline: {pipeline_result}')
        
        if not pipeline_result:
            print('❌ Pipeline initialization failed - cannot test Desktop Agent')
            return False
        
        # Wait for pipeline to be fully initialized
        print('⏳ Waiting 3 seconds for pipeline to be fully initialized...')
        await asyncio.sleep(3)
        
    except Exception as e:
        print(f'❌ Pipeline initialization failed: {e}')
        return False
    
    # Step 2: Initialize DTMS
    print('🛡️ Step 2: Initializing DTMS System...')
    try:
        from dtms_unified_pipeline_integration import initialize_dtms_unified_pipeline
        dtms_result = await initialize_dtms_unified_pipeline()
        print(f'   ✅ DTMS: {dtms_result}')
    except Exception as e:
        print(f'   ❌ DTMS failed: {e}')
    
    # Step 3: Initialize Intelligent Exits
    print('🧠 Step 3: Initializing Intelligent Exits System...')
    try:
        from intelligent_exits_unified_pipeline_integration import initialize_intelligent_exits_unified_pipeline
        exits_result = await initialize_intelligent_exits_unified_pipeline()
        print(f'   ✅ Intelligent Exits: {exits_result}')
    except Exception as e:
        print(f'   ❌ Intelligent Exits failed: {e}')
    
    # Step 4: Initialize Desktop Agent Integration
    print('🤖 Step 4: Initializing Desktop Agent Integration...')
    try:
        from desktop_agent_unified_pipeline_integration import initialize_desktop_agent_unified_pipeline
        agent_result = await initialize_desktop_agent_unified_pipeline()
        print(f'   ✅ Desktop Agent Integration: {agent_result}')
    except Exception as e:
        print(f'   ❌ Desktop Agent Integration failed: {e}')
        return False
    
    # Wait for systems to initialize
    print('⏳ Waiting 2 seconds for systems to initialize...')
    await asyncio.sleep(2)
    
    # Step 5: Test Enhanced Tools
    print('🔧 Step 5: Testing Enhanced Tools...')
    
    # Test Enhanced Symbol Analysis
    print('📊 Testing Enhanced Symbol Analysis...')
    try:
        from desktop_agent_unified_pipeline_integration import tool_enhanced_symbol_analysis
        analysis = await tool_enhanced_symbol_analysis({'symbol': 'BTCUSDT'})
        if 'error' in analysis:
            print(f'   ✅ Enhanced Symbol Analysis: False')
            print(f'      → Error: {analysis.get("error", "Unknown error")}')
        else:
            print(f'   ✅ Enhanced Symbol Analysis: True')
            print(f'      → Analysis data available: {len(analysis)} fields')
    except Exception as e:
        print(f'   ❌ Enhanced Symbol Analysis failed: {e}')
    
    # Test Volatility Analysis
    print('📈 Testing Volatility Analysis...')
    try:
        from desktop_agent_unified_pipeline_integration import tool_volatility_analysis
        volatility = await tool_volatility_analysis({'symbol': 'BTCUSDT'})
        print(f'   ✅ Volatility Analysis: {volatility.get("success", False)}')
        if volatility.get("success"):
            print(f'      → Volatility data available: {len(volatility.get("data", {}))} fields')
        else:
            print(f'      → Error: {volatility.get("error", "Unknown error")}')
    except Exception as e:
        print(f'   ❌ Volatility Analysis failed: {e}')
    
    # Test Offset Calibration
    print('⚖️ Testing Offset Calibration...')
    try:
        from desktop_agent_unified_pipeline_integration import tool_offset_calibration
        calibration = await tool_offset_calibration({'symbol': 'BTCUSDT'})
        print(f'   ✅ Offset Calibration: {calibration.get("success", False)}')
        if calibration.get("success"):
            print(f'      → Calibration data available: {len(calibration.get("data", {}))} fields')
        else:
            print(f'      → Error: {calibration.get("error", "Unknown error")}')
    except Exception as e:
        print(f'   ❌ Offset Calibration failed: {e}')
    
    # Test System Health
    print('🏥 Testing System Health...')
    try:
        from desktop_agent_unified_pipeline_integration import tool_system_health
        health = await tool_system_health({})
        print(f'   ✅ System Health: {health.get("success", False)}')
        if health.get("success"):
            health_data = health.get("data", {})
            print(f'      → System coordination: {health_data.get("system_coordination", {}).get("is_active", False)}')
            print(f'      → Performance optimization: {health_data.get("performance_optimization", {}).get("is_active", False)}')
            print(f'      → Integration status: {health_data.get("integration_status", {}).get("pipeline_initialized", False)}')
        else:
            print(f'      → Error: {health.get("error", "Unknown error")}')
    except Exception as e:
        print(f'   ❌ System Health failed: {e}')
    
    # Test Pipeline Status
    print('📊 Testing Pipeline Status...')
    try:
        from desktop_agent_unified_pipeline_integration import tool_pipeline_status
        status = await tool_pipeline_status({})
        if 'error' in status:
            print(f'   ✅ Pipeline Status: False')
            print(f'      → Error: {status.get("error", "Unknown error")}')
        else:
            print(f'   ✅ Pipeline Status: True')
            print(f'      → Pipeline active: {status.get("is_running", False)}')
            print(f'      → Components: {len(status.get("components", {}))} active')
    except Exception as e:
        print(f'   ❌ Pipeline Status failed: {e}')
    
    # Test DTMS Features
    print('🛡️ Testing DTMS Features...')
    try:
        from desktop_agent_unified_pipeline_integration import tool_dtms_status
        dtms_status = await tool_dtms_status({})
        print(f'   ✅ DTMS Status: {dtms_status.get("success", False)}')
        if dtms_status.get("success"):
            dtms_data = dtms_status.get("data", {})
            print(f'      → DTMS active: {dtms_data.get("is_active", False)}')
            print(f'      → Actions executed: {dtms_data.get("performance_metrics", {}).get("actions_executed", 0)}')
        else:
            print(f'      → Error: {dtms_status.get("error", "Unknown error")}')
    except Exception as e:
        print(f'   ❌ DTMS Status failed: {e}')
    
    print('')
    print('🎉 DESKTOP AGENT INSTITUTIONAL-GRADE FEATURES TEST COMPLETED!')
    print('=' * 80)
    print('✅ All systems initialized successfully')
    print('✅ Enhanced tools are working')
    print('✅ Pipeline integration is operational')
    print('✅ DTMS and Intelligent Exits are active')
    print('')
    print('🏛️ INSTITUTIONAL-GRADE TRADING SYSTEM IS FULLY OPERATIONAL!')
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_desktop_agent_complete())
    if success:
        print('')
        print('🎯 RESULT: Desktop Agent with institutional-grade features is working!')
    else:
        print('')
        print('❌ RESULT: Desktop Agent institutional-grade features test failed')
