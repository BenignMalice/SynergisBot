"""
Test MT5 M1 Streaming Enhancement
"""

import asyncio
from unified_tick_pipeline_integration import initialize_unified_pipeline, get_pipeline_instance

async def test_mt5_m1_streaming():
    print('📊 Testing MT5 M1 Streaming Enhancement...')
    print('=' * 60)
    
    # Initialize pipeline with M1 streaming
    print('🚀 Initializing Unified Tick Pipeline with M1 Streaming...')
    pipeline_result = await initialize_unified_pipeline()
    print(f'   ✅ Pipeline: {pipeline_result}')
    
    if not pipeline_result:
        print('❌ Pipeline initialization failed')
        return False
    
    pipeline = get_pipeline_instance()
    if not pipeline:
        print('❌ Pipeline instance not available')
        return False
    
    # Wait for M1 data to start flowing
    print('⏳ Waiting 15 seconds for M1 data to flow...')
    await asyncio.sleep(15)
    
    # Check M1 streaming status
    print('📊 Checking M1 Streaming Status...')
    status = await pipeline.get_pipeline_status()
    m1_status = status.get('components', {}).get('mt5_m1_streaming', {})
    
    print(f'   🔗 M1 Streaming Active: {m1_status.get("is_running", False)}')
    print(f'   📈 Symbols: {len(m1_status.get("symbols", []))}')
    print(f'   📊 Buffer Sizes: {m1_status.get("buffer_sizes", {})}')
    print(f'   ⚡ M1 Candles Processed: {m1_status.get("performance_metrics", {}).get("m1_candles_processed", 0)}')
    print(f'   📈 Volatility Calculations: {m1_status.get("performance_metrics", {}).get("volatility_calculations", 0)}')
    print(f'   🏗️ Structure Analyses: {m1_status.get("performance_metrics", {}).get("structure_analyses", 0)}')
    
    # Test M1 data access
    print('🔍 Testing M1 Data Access...')
    forex_symbols = ['EURUSDc', 'GBPUSDc', 'XAUUSDc']
    
    for symbol in forex_symbols:
        m1_data = pipeline.mt5_m1_streaming.get_m1_data(symbol, 10)
        print(f'   📊 {symbol}: {len(m1_data)} M1 candles')
        
        if m1_data:
            latest_candle = m1_data[-1]
            print(f'      Latest: {latest_candle.get("time", "N/A")} - Close: {latest_candle.get("close", "N/A")}')
    
    # Check system health
    print('🏥 System Health Check...')
    health = await pipeline.get_system_health()
    print(f'   📊 Total Ticks Processed: {health.get("performance_metrics", {}).get("ticks_processed", 0)}')
    print(f'   🔗 Binance Active: {health.get("binance_feeds_active", False)}')
    print(f'   🔗 MT5 Active: {health.get("mt5_bridge_active", False)}')
    
    # Summary
    print('📈 ENHANCEMENT SUMMARY:')
    print('=' * 60)
    
    m1_active = m1_status.get("is_running", False)
    m1_candles = m1_status.get("performance_metrics", {}).get("m1_candles_processed", 0)
    volatility_calcs = m1_status.get("performance_metrics", {}).get("volatility_calculations", 0)
    structure_analyses = m1_status.get("performance_metrics", {}).get("structure_analyses", 0)
    
    if m1_active and m1_candles > 0:
        print('✅ MT5 M1 STREAMING ENHANCEMENT SUCCESSFUL!')
        print('')
        print('🚀 ENHANCED CAPABILITIES:')
        print('   → High-frequency M1 data streaming for forex pairs')
        print('   → Real-time volatility analysis for DTMS')
        print('   → Structure analysis for Intelligent Exits')
        print('   → Enhanced decision-making for forex trades')
        print('   → Improved timing for entry/exit signals')
        print('')
        print(f'📊 PERFORMANCE METRICS:')
        print(f'   → M1 Candles Processed: {m1_candles}')
        print(f'   → Volatility Calculations: {volatility_calcs}')
        print(f'   → Structure Analyses: {structure_analyses}')
        print('')
        print('🎯 DTMS and Intelligent Exits now have:')
        print('   → Higher frequency data for better decisions')
        print('   → Real-time volatility monitoring')
        print('   → Market structure analysis')
        print('   → Enhanced forex trading capabilities')
        return True
    else:
        print('⚠️ M1 STREAMING ENHANCEMENT NEEDS ATTENTION')
        print(f'   → M1 Active: {m1_active}')
        print(f'   → M1 Candles: {m1_candles}')
        print('   → Please check MT5 connection and symbol availability')
        return False

if __name__ == "__main__":
    success = asyncio.run(test_mt5_m1_streaming())
    if success:
        print('')
        print('🎉 MT5 M1 STREAMING ENHANCEMENT COMPLETE!')
        print('Your DTMS and Intelligent Exits systems now have enhanced forex capabilities!')
    else:
        print('')
        print('❌ M1 STREAMING ENHANCEMENT INCOMPLETE')
        print('Please address issues before proceeding')
