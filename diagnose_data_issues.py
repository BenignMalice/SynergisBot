"""
Diagnose data collection issues in Unified Tick Pipeline
"""

import asyncio
from unified_tick_pipeline_integration import initialize_unified_pipeline, get_pipeline_instance

async def diagnose_data_issues():
    print('🔍 Diagnosing data collection issues...')
    
    # Initialize pipeline
    result = await initialize_unified_pipeline()
    pipeline = get_pipeline_instance()
    
    if pipeline:
        # Get detailed status
        status = await pipeline.get_pipeline_status()
        print('📊 Detailed Pipeline Status:')
        
        # Check Binance feeds
        binance_status = status.get('components', {}).get('binance_feeds', {})
        print('🔗 Binance Feeds:')
        print(f'   - Connected: {binance_status.get("is_connected", False)}')
        print(f'   - Active Feeds: {binance_status.get("active_feeds", 0)}')
        print(f'   - Error Count: {binance_status.get("error_count", 0)}')
        print(f'   - Last Error: {binance_status.get("last_error", "None")}')
        
        # Check MT5 bridge
        mt5_status = status.get('components', {}).get('mt5_bridge', {})
        print('🔗 MT5 Bridge:')
        print(f'   - Connected: {mt5_status.get("is_connected", False)}')
        print(f'   - Available Symbols: {mt5_status.get("available_symbols", 0)}')
        print(f'   - Error Count: {mt5_status.get("error_count", 0)}')
        
        # Check symbol availability
        print('📈 Symbol Status:')
        for symbol in ['XAUUSDT', 'XAUUSDc', 'BTCUSDT', 'EURUSDc']:
            ticks = pipeline.get_latest_ticks(symbol, 1)
            print(f'   {symbol}: {len(ticks)} ticks')
        
        # Check system health
        health = await pipeline.get_system_health()
        print('🏥 System Health:')
        print(f'   - Binance Active: {health.get("binance_feeds_active", False)}')
        print(f'   - MT5 Active: {health.get("mt5_bridge_active", False)}')
        print(f'   - Buffer Sizes: {health.get("buffer_sizes", {})}')
        
        # Check specific symbol configurations
        print('🔧 Symbol Configuration Check:')
        print('   - XAUUSDT: Binance crypto symbol (should be available)')
        print('   - XAUUSDc: MT5 FX symbol (may not be available)')
        print('   - BTCUSDT: Binance crypto symbol (should be available)')
        print('   - EURUSDc: MT5 FX symbol (should be available)')

if __name__ == "__main__":
    asyncio.run(diagnose_data_issues())
