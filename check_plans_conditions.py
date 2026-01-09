"""Check conditions for specific plans"""
import sqlite3
import json
from pathlib import Path

db_path = Path("data/auto_execution.db")

if not db_path.exists():
    print(f"ERROR: Database not found at {db_path}")
    exit(1)

plan_ids = ["chatgpt_b2dcbd59", "chatgpt_82d42dc8", "chatgpt_993ed80e", "chatgpt_e1cb3b86"]

conn = sqlite3.connect(str(db_path))
for plan_id in plan_ids:
    cursor = conn.execute("""
        SELECT plan_id, symbol, direction, entry_price, conditions, status
        FROM trade_plans 
        WHERE plan_id = ?
    """, (plan_id,))
    
    row = cursor.fetchone()
    
    if not row:
        print(f"\n❌ Plan {plan_id} not found")
        continue
    
    plan_id_db, symbol, direction, entry_price, conditions_json, status = row
    
    try:
        conditions = json.loads(conditions_json) if conditions_json else {}
    except:
        conditions = {}
    
    print(f"\n{'='*80}")
    print(f"Plan ID: {plan_id_db}")
    print(f"Symbol: {symbol}")
    print(f"Direction: {direction}")
    print(f"Entry: {entry_price}")
    print(f"Status: {status}")
    print(f"\nConditions:")
    print(json.dumps(conditions, indent=2))
    
    # Check required conditions
    print(f"\nConditions Check:")
    required_conditions = {
        "price_near": "Price near entry",
        "choch_bull": "CHOCH Bull (BUY)",
        "choch_bear": "CHOCH Bear (SELL)",
        "order_block": "Order Block",
        "order_block_type": "Order Block Type",
        "price_in_premium": "Price In Premium",
        "price_in_discount": "Price In Discount",
        "m1_choch_bos_combo": "M1 CHOCH BOS Combo",
        "min_volatility": "Min Volatility",
        "timeframe": "Timeframe",
        "strategy_type": "Strategy Type"
    }
    
    for key, desc in required_conditions.items():
        if key in conditions:
            value = conditions[key]
            print(f"  [OK] {desc}: {value}")
        else:
            print(f"  [MISSING] {desc}: NOT SET")

conn.close()

