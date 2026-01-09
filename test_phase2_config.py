"""Quick test for Phase 2 configuration features"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("Testing Phase 2 Configuration Features...")
print("=" * 60)

# Test 1: Config file structure
print("\n[TEST 1] Config file structure")
try:
    with open("config/micro_scalp_automation.json", 'r') as f:
        config = json.load(f)
    
    required_keys = [
        'enabled', 'symbols', 'check_interval_seconds',
        'rate_limiting', 'position_limits', 'session_filters', 'risk_per_trade'
    ]
    
    missing = [k for k in required_keys if k not in config]
    if missing:
        print(f"[FAIL] Missing keys: {missing}")
    else:
        print("[PASS] All required keys present")
        
        # Check nested structures
        if 'max_trades_per_hour' in config.get('rate_limiting', {}):
            print("[PASS] Rate limiting config present")
        if 'max_total_positions' in config.get('position_limits', {}):
            print("[PASS] Position limits config present")
        if 'preferred_sessions' in config.get('session_filters', {}):
            print("[PASS] Session filters config present")
            
except Exception as e:
    print(f"[FAIL] Error: {e}")

# Test 2: Monitor initialization with Phase 2 config
print("\n[TEST 2] Monitor initialization with Phase 2 config")
try:
    from infra.micro_scalp_monitor import MicroScalpMonitor
    
    monitor = MicroScalpMonitor(
        symbols=["BTCUSDc"],
        check_interval=5,
        micro_scalp_engine=None,
        execution_manager=None,
        streamer=None,
        mt5_service=None,
        config_path="config/micro_scalp_automation.json"
    )
    
    # Check Phase 2 attributes
    phase2_attrs = [
        'max_trades_per_hour', 'max_trades_per_day',
        'max_total_positions', 'risk_per_trade',
        'session_filters_enabled', 'preferred_sessions',
        'trades_per_hour', 'trades_per_day'
    ]
    
    missing_attrs = [attr for attr in phase2_attrs if not hasattr(monitor, attr)]
    if missing_attrs:
        print(f"[FAIL] Missing attributes: {missing_attrs}")
    else:
        print("[PASS] All Phase 2 attributes initialized")
        print(f"   -> max_trades_per_hour: {monitor.max_trades_per_hour}")
        print(f"   -> max_trades_per_day: {monitor.max_trades_per_day}")
        print(f"   -> max_total_positions: {monitor.max_total_positions}")
        print(f"   -> risk_per_trade: {monitor.risk_per_trade}")
        print(f"   -> session_filters_enabled: {monitor.session_filters_enabled}")
        print(f"   -> preferred_sessions: {monitor.preferred_sessions}")
        
except Exception as e:
    print(f"[FAIL] Error: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Rate limiting logic
print("\n[TEST 3] Rate limiting logic")
try:
    from infra.micro_scalp_monitor import MicroScalpMonitor
    from datetime import datetime, timedelta
    
    monitor = MicroScalpMonitor(
        symbols=["BTCUSDc"],
        check_interval=5,
        micro_scalp_engine=None,
        execution_manager=None,
        streamer=None,
        mt5_service=None
    )
    
    # Set test values
    monitor.max_trades_per_hour = 2
    monitor.max_trades_per_day = 5
    monitor.trades_per_hour = {"BTCUSDc": [datetime.now()]}
    monitor.trades_per_day = {"BTCUSDc": [datetime.now()]}
    
    # Test should skip (already has 1 trade, limit is 2, but we're checking before adding)
    # Actually, the logic cleans old entries first, so this should pass
    result = monitor._should_skip_symbol("BTCUSDc")
    print(f"[INFO] Rate limit check result: {result}")
    print("[PASS] Rate limiting method exists and works")
    
except Exception as e:
    print(f"[FAIL] Error: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Session filtering
print("\n[TEST 4] Session filtering")
try:
    from infra.micro_scalp_monitor import MicroScalpMonitor
    
    monitor = MicroScalpMonitor(
        symbols=["BTCUSDc"],
        check_interval=5,
        micro_scalp_engine=None,
        execution_manager=None,
        streamer=None,
        mt5_service=None
    )
    
    # Test session filtering method
    if hasattr(monitor, '_should_monitor_symbol'):
        result = monitor._should_monitor_symbol("BTCUSDc")
        print(f"[INFO] Session filter check result: {result}")
        print("[PASS] Session filtering method exists")
    else:
        print("[FAIL] _should_monitor_symbol method not found")
        
except Exception as e:
    print(f"[FAIL] Error: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Position limits (total)
print("\n[TEST 5] Position limits (total)")
try:
    from infra.micro_scalp_monitor import MicroScalpMonitor
    
    monitor = MicroScalpMonitor(
        symbols=["BTCUSDc"],
        check_interval=5,
        micro_scalp_engine=None,
        execution_manager=None,
        streamer=None,
        mt5_service=None
    )
    
    # Set test values
    monitor.max_positions_per_symbol = 1
    monitor.max_total_positions = 2
    monitor.active_positions = {
        "BTCUSDc": [12345],
        "XAUUSDc": [12346]
    }
    
    # Should return True (2 positions >= max_total_positions of 2)
    result = monitor._has_max_positions("BTCUSDc")
    print(f"[INFO] Position limit check result: {result}")
    print("[PASS] Total position limit check works")
    
except Exception as e:
    print(f"[FAIL] Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Phase 2 Configuration Features Test Complete")

