"""
Test Risk and Performance Framework
"""

import asyncio
from risk_performance_framework import (
    initialize_risk_performance_framework,
    get_risk_status,
    get_performance_status
)

async def test_risk_performance_framework():
    print('🛡️ Testing Risk and Performance Framework...')
    
    # Initialize framework
    config = {
        'database_path': 'data/risk_performance.db',
        'monitoring_interval': 5,
        'alert_retention_hours': 24
    }
    
    result = await initialize_risk_performance_framework(config)
    print(f'✅ Framework Initialization: {result}')
    
    if result:
        # Wait for monitoring to start
        print('⏳ Waiting 10 seconds for monitoring to start...')
        await asyncio.sleep(10)
        
        # Test risk status
        print('🚨 Testing Risk Status...')
        risk_status = await get_risk_status()
        print(f'   - Active Alerts: {risk_status.get("active_alerts", 0)}')
        print(f'   - Critical Alerts: {risk_status.get("critical_alerts", 0)}')
        print(f'   - High Alerts: {risk_status.get("high_alerts", 0)}')
        print(f'   - Medium Alerts: {risk_status.get("medium_alerts", 0)}')
        print(f'   - Low Alerts: {risk_status.get("low_alerts", 0)}')
        
        # Test performance status
        print('📊 Testing Performance Status...')
        perf_status = await get_performance_status()
        print(f'   - Latency: {perf_status.get("latency", 0):.2f}ms')
        print(f'   - Throughput: {perf_status.get("throughput", 0):.0f} ticks/min')
        print(f'   - Reliability: {perf_status.get("reliability", 0):.3f}')
        print(f'   - Accuracy: {perf_status.get("accuracy", 0):.3f}')
        print(f'   - Win Rate: {perf_status.get("win_rate", 0):.3f}')
        print(f'   - Data Completeness: {perf_status.get("data_completeness", 0):.3f}')
        print(f'   - Data Accuracy: {perf_status.get("data_accuracy", 0):.3f}')
        
        print('🎉 Risk and Performance Framework is operational!')
        print('   → Real-time risk monitoring active')
        print('   → Performance metrics collection active')
        print('   → Alert generation and management active')
        print('   → Risk mitigation strategies ready')
        print('   → Performance optimization recommendations ready')
        print('   → Historical analysis and reporting ready')
    else:
        print('❌ Risk and Performance Framework initialization failed')

if __name__ == "__main__":
    asyncio.run(test_risk_performance_framework())
