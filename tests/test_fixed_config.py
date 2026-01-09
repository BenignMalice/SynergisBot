"""
Test fixed configuration for data collection
"""

import asyncio
from unified_tick_pipeline_integration import initialize_unified_pipeline, get_pipeline_instance

async def test_fixed_configuration():
    print('🔧 Testing fixed configuration...')
    
    # Initialize pipeline with new config
    result = await initialize_unified_pipeline()
    pipeline = get_pipeline_instance()
    
    if pipeline:
        print('⏳ Waiting 3 seconds for data to flow...')
        await asyncio.sleep(3)
        
        # Check symbol data
        print('📈 Symbol Data Check:')
        symbols_to_check = ['XAUUSDc', 'BTCUSDT', 'ETHUSDT', 'EURUSDc']
        for symbol in symbols_to_check:
            ticks = pipeline.get_latest_ticks(symbol, 5)
            print(f'   {symbol}: {len(ticks)} ticks')
        
        # Check system health
        health = await pipeline.get_system_health()
        print('🏥 System Health:')
        print(f'   - Binance Active: {health.get("binance_feeds_active", False)}')
        print(f'   - MT5 Active: {health.get("mt5_bridge_active", False)}')
        print(f'   - Ticks Processed: {health.get("performance_metrics", {}).get("ticks_processed", 0)}')

if __name__ == "__main__":
    asyncio.run(test_fixed_configuration())
