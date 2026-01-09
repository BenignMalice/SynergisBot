"""
Test Intelligent Exits System Directly
"""

import asyncio
from intelligent_exits_unified_pipeline_integration import (
    initialize_intelligent_exits_unified_pipeline,
    get_intelligent_exits_unified_integration,
    get_intelligent_exits_unified_status
)

async def test_intelligent_exits_direct():
    print('🧠 Testing Intelligent Exits System Directly')
    print('=' * 50)
    
    # Initialize Intelligent Exits
    print('🚀 Initializing Intelligent Exits...')
    result = await initialize_intelligent_exits_unified_pipeline()
    print(f'   → Initialization Result: {result}')
    
    # Get integration instance
    integration = get_intelligent_exits_unified_integration()
    print(f'   → Integration Instance: {integration is not None}')
    
    if integration:
        # Get status
        status = integration.get_status()
        print(f'   → Status: {status}')
        
        # Check if active
        is_active = status.get('is_active', False)
        print(f'   → Is Active: {is_active}')
        
        # Check pipeline availability
        pipeline_available = status.get('pipeline_available', False)
        print(f'   → Pipeline Available: {pipeline_available}')
        
        # Check exit rules
        exit_rules = status.get('exit_rules', 0)
        print(f'   → Exit Rules: {exit_rules}')
        
        # Check performance metrics
        metrics = status.get('performance_metrics', {})
        print(f'   → Performance Metrics: {metrics}')
        
        if is_active:
            print('')
            print('✅ INTELLIGENT EXITS IS OPERATIONAL!')
            print('')
            print('📊 System Status:')
            print(f'   → Active: {is_active}')
            print(f'   → Pipeline Connected: {pipeline_available}')
            print(f'   → Exit Rules: {exit_rules}')
            print(f'   → Breakeven Moves: {metrics.get("breakeven_moves", 0)}')
            print(f'   → Partial Profits: {metrics.get("partial_profits", 0)}')
            print(f'   → Volatility Adjustments: {metrics.get("volatility_adjustments", 0)}')
            print(f'   → Trailing Stops: {metrics.get("trailing_stops", 0)}')
            print(f'   → Error Count: {metrics.get("error_count", 0)}')
            print('')
            print('🎯 INTELLIGENT EXITS IS READY FOR TRADING!')
            return True
        else:
            print('')
            print('❌ INTELLIGENT EXITS IS NOT OPERATIONAL')
            print('')
            print('🔍 Debugging Information:')
            print(f'   → Integration Instance: {integration is not None}')
            print(f'   → Is Active: {is_active}')
            print(f'   → Pipeline Available: {pipeline_available}')
            print(f'   → Status: {status}')
            print('')
            print('🔧 Please check system initialization')
            return False
    else:
        print('')
        print('❌ INTELLIGENT EXITS INTEGRATION NOT AVAILABLE')
        print('')
        print('🔧 Please check system initialization')
        return False

if __name__ == "__main__":
    success = asyncio.run(test_intelligent_exits_direct())
    if success:
        print('')
        print('🎉 INTELLIGENT EXITS IS FULLY OPERATIONAL!')
    else:
        print('')
        print('❌ INTELLIGENT EXITS NEEDS ATTENTION')
