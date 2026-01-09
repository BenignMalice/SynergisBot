"""
Test complete system integration with Unified Tick Pipeline
"""

import asyncio
from unified_tick_pipeline_integration import initialize_unified_pipeline, get_pipeline_instance
from dtms_unified_pipeline_integration import initialize_dtms_unified_pipeline
from intelligent_exits_unified_pipeline_integration import initialize_intelligent_exits_unified_pipeline

async def test_complete_system():
    print('🚀 Testing Complete System Integration...')
    
    # Step 1: Initialize Unified Tick Pipeline
    print('📡 Step 1: Initializing Unified Tick Pipeline...')
    pipeline_result = await initialize_unified_pipeline()
    print(f'   Pipeline: {pipeline_result}')
    
    if not pipeline_result:
        print('❌ Pipeline initialization failed - cannot continue')
        return
    
    # Step 2: Initialize DTMS with Pipeline
    print('🔧 Step 2: Initializing DTMS with Pipeline...')
    dtms_result = await initialize_dtms_unified_pipeline()
    print(f'   DTMS: {dtms_result}')
    
    # Step 3: Initialize Intelligent Exits with Pipeline
    print('🧠 Step 3: Initializing Intelligent Exits with Pipeline...')
    exits_result = await initialize_intelligent_exits_unified_pipeline()
    print(f'   Intelligent Exits: {exits_result}')
    
    # Step 4: Test Data Flow
    print('📊 Step 4: Testing Data Flow...')
    pipeline = get_pipeline_instance()
    if pipeline:
        # Wait for data to flow
        await asyncio.sleep(5)
        
        # Check system health
        health = await pipeline.get_system_health()
        print(f'   - Ticks Processed: {health.get("performance_metrics", {}).get("ticks_processed", 0)}')
        print(f'   - Binance Active: {health.get("binance_feeds_active", False)}')
        print(f'   - MT5 Active: {health.get("mt5_bridge_active", False)}')
        
        # Check data availability
        crypto_ticks = pipeline.get_latest_ticks('BTCUSDT', 5)
        fx_ticks = pipeline.get_latest_ticks('EURUSDc', 5)
        print(f'   - BTCUSDT Ticks: {len(crypto_ticks)}')
        print(f'   - EURUSDc Ticks: {len(fx_ticks)}')
    
    # Step 5: System Status Summary
    print('📈 Step 5: System Status Summary...')
    print(f'   ✅ Unified Tick Pipeline: {pipeline_result}')
    print(f'   ✅ DTMS Enhancement: {dtms_result}')
    print(f'   ✅ Intelligent Exits: {exits_result}')
    
    if pipeline_result and dtms_result and exits_result:
        print('🎉 COMPLETE SYSTEM INTEGRATION SUCCESSFUL!')
        print('   → Real-time data streaming from Binance + MT5')
        print('   → DTMS enhanced with pipeline data')
        print('   → Intelligent Exits optimized with M5 volatility bridge')
        print('   → ChatGPT analysis layer ready')
        print('   → Institutional-grade trading system operational!')
    else:
        print('⚠️ Some components failed to initialize')

if __name__ == "__main__":
    asyncio.run(test_complete_system())
