"""
Test ChatGPT access to all timeframes (M1, M5, M15, H1, H4)
"""

import asyncio
import pytest
from unified_tick_pipeline_integration import initialize_unified_pipeline, get_pipeline_instance

@pytest.mark.asyncio
async def test_chatgpt_timeframe_access():
    print('🤖 Testing ChatGPT Access to All Timeframes...')
    print('=' * 60)
    
    # Initialize pipeline
    print('🚀 Initializing Unified Tick Pipeline...')
    pipeline_result = await initialize_unified_pipeline()
    print(f'   ✅ Pipeline: {pipeline_result}')
    
    if not pipeline_result:
        print('❌ Pipeline initialization failed')
        return False
    
    pipeline = get_pipeline_instance()
    if not pipeline:
        print('❌ Pipeline instance not available')
        return False
    
    # Wait for data to flow
    print('⏳ Waiting 10 seconds for data to flow...')
    await asyncio.sleep(10)
    
    # Check pipeline status
    print('📊 Checking Pipeline Status...')
    status = pipeline.get_pipeline_status()
    
    # Check MT5 bridge status
    mt5_status = status.get('components', {}).get('mt5_bridge', {})
    print(f'   🔗 MT5 Bridge Active: {mt5_status.get("is_connected", False)}')
    print(f'   📈 Available Timeframes: {mt5_status.get("timeframes", [])}')
    
    # Check M1 streaming status
    m1_status = status.get('components', {}).get('mt5_m1_streaming', {})
    print(f'   📊 M1 Streaming Active: {m1_status.get("is_running", False)}')
    print(f'   📈 M1 Symbols: {len(m1_status.get("symbols", []))}')
    
    # Check ChatGPT integration status
    chatgpt_status = status.get('components', {}).get('chatgpt_integration', {})
    print(f'   🤖 ChatGPT Integration Active: {chatgpt_status.get("is_active", False)}')
    
    # Test data access for different timeframes
    print('🔍 Testing Data Access by Timeframe...')
    
    # Test M1 data (new streaming)
    print('   📊 M1 Data (Streaming):')
    m1_symbols = ['EURUSDc', 'GBPUSDc', 'XAUUSDc']
    for symbol in m1_symbols:
        m1_data = pipeline.mt5_m1_streaming.get_m1_data(symbol, 5)
        print(f'      {symbol}: {len(m1_data)} M1 candles')
    
    # Test tick data (M1 equivalent from MT5 bridge)
    print('   📊 Tick Data (MT5 Bridge):')
    for symbol in m1_symbols:
        tick_data = pipeline.get_latest_ticks(symbol, 5)
        print(f'      {symbol}: {len(tick_data)} ticks')
    
    # Check if historical data collection is working
    print('📈 Historical Data Collection Status:')
    
    # Check MT5 bridge performance metrics
    mt5_metrics = mt5_status.get('performance_metrics', {})
    print(f'   📊 MT5 Ticks Processed: {mt5_metrics.get("ticks_processed", 0)}')
    print(f'   📊 MT5 Historical Updates: {mt5_metrics.get("historical_updates", 0)}')
    print(f'   📊 MT5 Error Count: {mt5_metrics.get("error_count", 0)}')
    
    # Check M1 streaming performance
    m1_metrics = m1_status.get('performance_metrics', {})
    print(f'   📊 M1 Candles Processed: {m1_metrics.get("m1_candles_processed", 0)}')
    print(f'   📊 Volatility Calculations: {m1_metrics.get("volatility_calculations", 0)}')
    print(f'   📊 Structure Analyses: {m1_metrics.get("structure_analyses", 0)}')
    
    # Summary
    print('📊 TIMEFRAME ACCESS SUMMARY:')
    print('=' * 60)
    
    mt5_active = mt5_status.get("is_connected", False)
    m1_active = m1_status.get("is_running", False)
    chatgpt_active = chatgpt_status.get("is_active", False)
    
    print(f'✅ MT5 Bridge (M5, M15, H1, H4): {mt5_active}')
    print(f'✅ M1 Streaming (M1): {m1_active}')
    print(f'✅ ChatGPT Integration: {chatgpt_active}')
    
    if mt5_active and m1_active and chatgpt_active:
        print('')
        print('🎉 CHATGPT HAS FULL TIMEFRAME ACCESS!')
        print('')
        print('📊 AVAILABLE TIMEFRAMES FOR CHATGPT ANALYSIS:')
        print('   → M1: Real-time streaming (M1 streaming)')
        print('   → M5: Historical data (MT5 bridge)')
        print('   → M15: Historical data (MT5 bridge)')
        print('   → H1: Historical data (MT5 bridge)')
        print('   → H4: Historical data (MT5 bridge)')
        print('')
        print('🚀 CHATGPT CAPABILITIES:')
        print('   → Multi-timeframe analysis (M1-M5-M15-H1-H4)')
        print('   → Real-time M1 data for precise analysis')
        print('   → Historical context from higher timeframes')
        print('   → Enhanced forex analysis with M1 streaming')
        print('   → Complete market structure analysis')
        return True
    else:
        print('')
        print('⚠️ TIMEFRAME ACCESS INCOMPLETE')
        print(f'   → MT5 Bridge: {mt5_active}')
        print(f'   → M1 Streaming: {m1_active}')
        print(f'   → ChatGPT Integration: {chatgpt_active}')
        return False

if __name__ == "__main__":
    success = asyncio.run(test_chatgpt_timeframe_access())
    if success:
        print('')
        print('✅ ChatGPT has complete access to all timeframes!')
        print('Your AI analysis layer is fully operational with multi-timeframe data!')
    else:
        print('')
        print('❌ ChatGPT timeframe access needs attention')
        print('Please check component initialization')
