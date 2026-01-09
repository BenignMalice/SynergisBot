"""
Test data flow in Unified Tick Pipeline
"""

import asyncio
import time
from unified_tick_pipeline_integration import initialize_unified_pipeline, get_pipeline_instance

async def test_data_collection():
    print('🚀 Testing data collection...')
    
    # Initialize pipeline
    result = await initialize_unified_pipeline()
    print(f'✅ Init: {result}')
    
    pipeline = get_pipeline_instance()
    print(f'✅ Pipeline: {pipeline is not None}')
    
    if pipeline:
        # Check system health
        health = await pipeline.get_system_health()
        print('📊 System Health:')
        print(f'   - Running: {health.get("is_running", False)}')
        print(f'   - Binance Feeds: {health.get("binance_feeds_active", False)}')
        print(f'   - MT5 Bridge: {health.get("mt5_bridge_active", False)}')
        print(f'   - Buffer Sizes: {health.get("buffer_sizes", {})}')
        
        # Wait a moment for data to start flowing
        print('⏳ Waiting 5 seconds for data to start flowing...')
        await asyncio.sleep(5)
        
        # Check ticks again
        ticks = pipeline.get_latest_ticks('BTCUSDT', 10)
        print(f'📈 Ticks after 5s: {len(ticks)}')
        
        # Check all symbols
        for symbol in ['BTCUSDT', 'XAUUSDT', 'ETHUSDT', 'EURUSDc', 'GBPUSDc']:
            symbol_ticks = pipeline.get_latest_ticks(symbol, 5)
            print(f'   {symbol}: {len(symbol_ticks)} ticks')
        
        # Check performance metrics
        perf = health.get('performance_metrics', {})
        print('📊 Performance:')
        print(f'   - Ticks Processed: {perf.get("ticks_processed", 0)}')
        print(f'   - Error Count: {perf.get("error_count", 0)}')
    
    print('🎉 Data collection test completed!')

if __name__ == "__main__":
    asyncio.run(test_data_collection())
