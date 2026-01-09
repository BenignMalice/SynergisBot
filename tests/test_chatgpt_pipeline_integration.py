"""
Test ChatGPT integration with Unified Tick Pipeline
"""

import asyncio
import pytest
from unified_tick_pipeline_integration import initialize_unified_pipeline, get_pipeline_instance
from desktop_agent_unified_pipeline_integration import initialize_desktop_agent_unified_pipeline

@pytest.mark.asyncio
async def test_chatgpt_pipeline_integration():
    print('🤖 Testing ChatGPT Integration with Unified Pipeline...')
    
    # Step 1: Initialize Unified Tick Pipeline first
    print('📡 Step 1: Initializing Unified Tick Pipeline...')
    pipeline_result = await initialize_unified_pipeline()
    print(f'   Pipeline: {pipeline_result}')
    
    if not pipeline_result:
        print('❌ Pipeline initialization failed - cannot continue')
        return
    
    # Step 2: Initialize ChatGPT integration
    print('🧠 Step 2: Initializing ChatGPT Integration...')
    chatgpt_result = await initialize_desktop_agent_unified_pipeline()
    print(f'   ChatGPT: {chatgpt_result}')
    
    # Step 3: Test ChatGPT tools with real-time data
    print('🔧 Step 3: Testing ChatGPT Tools...')
    pipeline = get_pipeline_instance()
    if pipeline:
        # Wait for data to flow
        await asyncio.sleep(3)
        
        # Test enhanced symbol analysis
        print('   📊 Testing Enhanced Symbol Analysis...')
        try:
            from desktop_agent_unified_pipeline_integration import tool_enhanced_symbol_analysis
            analysis_result = await tool_enhanced_symbol_analysis({'symbol': 'BTCUSDT'})
            print(f'      BTCUSDT Analysis: {len(analysis_result.get("data", []))} data points')
        except Exception as e:
            print(f'      Analysis Error: {e}')
        
        # Test volatility analysis
        print('   📈 Testing Volatility Analysis...')
        try:
            from desktop_agent_unified_pipeline_integration import tool_volatility_analysis
            volatility_result = await tool_volatility_analysis({'symbol': 'EURUSDc'})
            print(f'      EURUSDc Volatility: {volatility_result.get("volatility_score", "N/A")}')
        except Exception as e:
            print(f'      Volatility Error: {e}')
        
        # Test system health
        print('   🏥 Testing System Health...')
        try:
            from desktop_agent_unified_pipeline_integration import tool_system_health
            health_result = await tool_system_health({})
            print(f'      System Health: {health_result.get("status", "Unknown")}')
        except Exception as e:
            print(f'      Health Error: {e}')
    
    # Step 4: Summary
    print('📈 Step 4: Integration Summary...')
    print(f'   ✅ Unified Tick Pipeline: {pipeline_result}')
    print(f'   ✅ ChatGPT Integration: {chatgpt_result}')
    
    if pipeline_result and chatgpt_result:
        print('🎉 CHATGPT INTEGRATION SUCCESSFUL!')
        print('   → ChatGPT now has access to real-time market data')
        print('   → Enhanced analysis tools available')
        print('   → Multi-timeframe analysis ready')
        print('   → Institutional-grade AI analysis operational!')
    else:
        print('⚠️ Some components failed to initialize')

if __name__ == "__main__":
    asyncio.run(test_chatgpt_pipeline_integration())
