"""
Final System Validation - Only declare success when truly error-free
"""

import asyncio
from unified_tick_pipeline_integration import initialize_unified_pipeline, get_pipeline_instance
from risk_performance_framework import initialize_risk_performance_framework, get_risk_status

async def test_final_validation():
    print('🔍 FINAL SYSTEM VALIDATION')
    print('=' * 60)
    print('⚠️  Only declaring success if system is truly error-free')
    print('')
    
    errors_detected = []
    warnings_detected = []
    
    # Test 1: Pipeline Initialization
    print('📡 Test 1: Pipeline Initialization')
    try:
        pipeline_result = await initialize_unified_pipeline()
        if not pipeline_result:
            errors_detected.append("Pipeline initialization failed")
        else:
            print('   ✅ Pipeline initialized successfully')
    except Exception as e:
        errors_detected.append(f"Pipeline initialization error: {e}")
    
    # Test 2: Data Flow Validation
    print('📊 Test 2: Data Flow Validation')
    try:
        pipeline = get_pipeline_instance()
        if pipeline:
            print('   ⏳ Waiting 10 seconds for data flow...')
            await asyncio.sleep(10)
            
            # Check for data
            crypto_ticks = pipeline.get_latest_ticks('BTCUSDT', 5)
            fx_ticks = pipeline.get_latest_ticks('EURUSDc', 5)
            
            if len(crypto_ticks) == 0 and len(fx_ticks) == 0:
                warnings_detected.append("No data flow detected")
            else:
                print(f'   ✅ Data flow: {len(crypto_ticks)} crypto + {len(fx_ticks)} FX ticks')
        else:
            errors_detected.append("Pipeline instance not available")
    except Exception as e:
        errors_detected.append(f"Data flow validation error: {e}")
    
    # Test 3: Risk Framework Validation
    print('🛡️ Test 3: Risk Framework Validation')
    try:
        risk_config = {
            'database_path': 'data/risk_performance.db',
            'monitoring_interval': 5,
            'alert_retention_hours': 24
        }
        risk_result = await initialize_risk_performance_framework(risk_config)
        if not risk_result:
            errors_detected.append("Risk framework initialization failed")
        else:
            print('   ✅ Risk framework initialized successfully')
            
            # Check for false positive alerts
            await asyncio.sleep(5)
            risk_status = await get_risk_status()
            high_alerts = risk_status.get("high_alerts", 0)
            
            if high_alerts > 0:
                warnings_detected.append(f"High risk alerts detected: {high_alerts}")
            else:
                print('   ✅ No false positive risk alerts')
    except Exception as e:
        errors_detected.append(f"Risk framework validation error: {e}")
    
    # Test 4: System Health Check
    print('🏥 Test 4: System Health Check')
    try:
        if pipeline:
            health = await pipeline.get_system_health()
            binance_active = health.get("binance_feeds_active", False)
            mt5_active = health.get("mt5_bridge_active", False)
            
            if not binance_active and not mt5_active:
                errors_detected.append("No data feeds active")
            elif not binance_active:
                warnings_detected.append("Binance feeds not active")
            elif not mt5_active:
                warnings_detected.append("MT5 bridge not active")
            else:
                print('   ✅ All data feeds active')
    except Exception as e:
        errors_detected.append(f"System health check error: {e}")
    
    # Final Assessment
    print('')
    print('🏁 FINAL ASSESSMENT')
    print('=' * 60)
    
    if errors_detected:
        print('❌ SYSTEM NOT READY - ERRORS DETECTED:')
        for error in errors_detected:
            print(f'   ❌ {error}')
        print('')
        print('🔧 Please fix errors before declaring success')
        return False
    
    if warnings_detected:
        print('⚠️ SYSTEM HAS WARNINGS:')
        for warning in warnings_detected:
            print(f'   ⚠️ {warning}')
        print('')
        print('🔧 Consider addressing warnings for optimal performance')
        return False
    
    print('🎉 SYSTEM VALIDATION SUCCESSFUL!')
    print('')
    print('✅ All components operational')
    print('✅ No errors detected')
    print('✅ No warnings detected')
    print('✅ Data flow confirmed')
    print('✅ Risk management active')
    print('')
    print('🚀 INSTITUTIONAL-GRADE TRADING SYSTEM IS READY!')
    return True

if __name__ == "__main__":
    success = asyncio.run(test_final_validation())
    if not success:
        print('')
        print('❌ SYSTEM NOT READY FOR PRODUCTION')
        print('Please address all errors and warnings before deployment')
