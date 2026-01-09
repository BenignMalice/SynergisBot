"""Check if auto-execution system is using 10-second intervals for XAUUSD and BTCUSD plans"""
import sqlite3
import json
from pathlib import Path

# Connect to database
db_path = Path("data/auto_execution.db")
if not db_path.exists():
    print("[ERROR] Database not found at data/auto_execution.db")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Get pending XAUUSD and BTCUSD plans
cursor.execute("""
    SELECT plan_id, symbol, conditions, status 
    FROM trade_plans 
    WHERE status = 'pending' 
    AND (symbol LIKE '%XAUUSD%' OR symbol LIKE '%BTCUSD%')
""")

plans = cursor.fetchall()

print(f"\n{'='*80}")
print(f"Found {len(plans)} pending XAUUSD/BTCUSD plans:")
print(f"{'='*80}\n")

if len(plans) == 0:
    print("[WARN] No pending XAUUSD or BTCUSD plans found")
    print("   Create some M1 micro-scalp plans to test 10-second intervals\n")
else:
    for plan_id, symbol, conditions_json, status in plans:
        try:
            conditions = json.loads(conditions_json) if conditions_json else {}
            timeframe = conditions.get('timeframe', 'N/A')
            
            # Check for micro-scalp indicators
            has_liquidity_sweep = conditions.get('liquidity_sweep', False)
            has_order_block = conditions.get('order_block', False)
            has_equal_lows = conditions.get('equal_lows', False) or conditions.get('equal_highs', False)
            has_vwap_deviation = conditions.get('vwap_deviation', False)
            has_plan_type = conditions.get('plan_type')
            
            # Determine if it should be detected as m1_micro_scalp
            is_m1_micro_scalp = False
            if timeframe == 'M1' and (has_liquidity_sweep or has_order_block or has_equal_lows or has_vwap_deviation):
                is_m1_micro_scalp = True
            
            # Check if it's explicit micro_scalp plan
            is_explicit_micro_scalp = has_plan_type == 'micro_scalp'
            
            print(f"Plan ID: {plan_id}")
            print(f"  Symbol: {symbol}")
            print(f"  Timeframe: {timeframe}")
            print(f"  Status: {status}")
            print(f"  Conditions:")
            print(f"    - liquidity_sweep: {has_liquidity_sweep}")
            print(f"    - order_block: {has_order_block}")
            print(f"    - equal_lows/highs: {has_equal_lows}")
            print(f"    - vwap_deviation: {has_vwap_deviation}")
            print(f"    - plan_type: {has_plan_type}")
            print(f"  Detection:")
            print(f"    - Will be detected as 'm1_micro_scalp': {'[YES]' if is_m1_micro_scalp else '[NO]'}")
            print(f"    - Is explicit 'micro_scalp': {'[YES]' if is_explicit_micro_scalp else '[NO]'}")
            print(f"  Interval:")
            if is_explicit_micro_scalp:
                print(f"    [WARN] Uses standard 30s interval (explicit micro_scalp plans don't use optimized intervals)")
            elif is_m1_micro_scalp:
                print(f"    [OK] Will use 10s base interval (when price within 2x tolerance)")
                print(f"    [OK] Will use 5s close interval (when price within tolerance)")
                print(f"    [OK] Will use 30s far interval (when price far from entry)")
            else:
                print(f"    [WARN] Uses default 30s interval (not detected as m1_micro_scalp)")
            print()
        except Exception as e:
            print(f"[ERROR] Error parsing plan {plan_id}: {e}\n")

# Check config
config_path = Path("config/auto_execution_optimized_intervals.json")
if config_path.exists():
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    opt_config = config.get('optimized_intervals', {})
    adaptive_enabled = opt_config.get('adaptive_intervals', {}).get('enabled', False)
    m1_config = opt_config.get('adaptive_intervals', {}).get('plan_type_intervals', {}).get('m1_micro_scalp', {})
    
    print(f"{'='*80}")
    print("Configuration Status:")
    print(f"{'='*80}")
    print(f"  Adaptive intervals enabled: {'[YES]' if adaptive_enabled else '[NO]'}")
    if adaptive_enabled and m1_config:
        print(f"  M1 micro-scalp intervals:")
        print(f"    - Base interval: {m1_config.get('base_interval_seconds', 'N/A')}s")
        print(f"    - Close interval: {m1_config.get('close_interval_seconds', 'N/A')}s")
        print(f"    - Far interval: {m1_config.get('far_interval_seconds', 'N/A')}s")
    else:
        print(f"  [WARN] M1 micro-scalp config not found or disabled")
else:
    print(f"\n[WARN] Config file not found: {config_path}")
    print(f"   Optimized intervals may not be enabled\n")

conn.close()

print(f"\n{'='*80}")
print("Summary:")
print(f"{'='*80}")
print("To verify 10-second intervals are working:")
print("1. Check logs for 'Adaptive interval' debug messages")
print("2. Look for 'Skipping {plan_id} - only X.Xs since last check (required: 10s)' messages")
print("3. Monitor plan check timestamps - should see checks every 10s when price is near entry")
print(f"{'='*80}\n")
