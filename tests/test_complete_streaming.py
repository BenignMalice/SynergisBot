"""
Test complete streaming data from both Binance and MT5
"""

import asyncio
from unified_tick_pipeline_integration import initialize_unified_pipeline, get_pipeline_instance

async def test_complete_streaming():
    print('🚀 Testing Complete Streaming Data System...')
    
    # Initialize pipeline
    result = await initialize_unified_pipeline()
    pipeline = get_pipeline_instance()
    
    if pipeline:
        print('⏳ Waiting 15 seconds for full data flow...')
        await asyncio.sleep(15)
        
        # Check all data sources
        print('📊 Complete Data Status:')
        
        # Crypto data (Binance)
        print('₿ Crypto Data (Binance):')
        crypto_symbols = ['BTCUSDT', 'ETHUSDT']
        for symbol in crypto_symbols:
            ticks = pipeline.get_latest_ticks(symbol, 10)
            print(f'   {symbol}: {len(ticks)} ticks')
        
        # FX data (MT5)
        print('💱 FX Data (MT5):')
        fx_symbols = ['EURUSDc', 'GBPUSDc', 'XAUUSDc']
        for symbol in fx_symbols:
            ticks = pipeline.get_latest_ticks(symbol, 10)
            print(f'   {symbol}: {len(ticks)} ticks')
        
        # System health
        health = await pipeline.get_system_health()
        print('🏥 System Health:')
        print(f'   - Binance Active: {health.get("binance_feeds_active", False)}')
        print(f'   - MT5 Active: {health.get("mt5_bridge_active", False)}')
        print(f'   - Ticks Processed: {health.get("performance_metrics", {}).get("ticks_processed", 0)}')
        print(f'   - Error Count: {health.get("performance_metrics", {}).get("error_count", 0)}')
        
        # Buffer sizes
        buffer_sizes = health.get("buffer_sizes", {})
        print(f'📈 Data Buffers:')
        for symbol, size in buffer_sizes.items():
            print(f'   {symbol}: {size} ticks')
        
        # Calculate total data flow
        total_ticks = sum(buffer_sizes.values())
        print(f'📊 Total Data Flow: {total_ticks} ticks across all symbols')
        
        if total_ticks > 0:
            print('✅ SUCCESS: Constant streaming data is now available for analysis!')
        else:
            print('⚠️ WARNING: Limited data flow detected')

if __name__ == "__main__":
    asyncio.run(test_complete_streaming())
