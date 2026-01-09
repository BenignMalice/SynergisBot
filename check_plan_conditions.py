"""
Check auto-execution plan conditions
"""
import sqlite3
import json
import sys
from pathlib import Path

def check_plan_conditions(plan_id: str):
    """Check conditions for a specific plan"""
    db_path = Path("data/auto_execution.db")
    
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        return
    
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute("""
                SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit, 
                       volume, conditions, created_at, created_by, status, expires_at, 
                       executed_at, ticket, notes
                FROM trade_plans 
                WHERE plan_id = ?
            """, (plan_id,))
            
            row = cursor.fetchone()
            
            if not row:
                print(f"Plan {plan_id} not found in database")
                return
            
            # Parse conditions
            conditions = json.loads(row[7]) if row[7] else {}
            notes = row[14] or ""
            
            print(f"Plan ID: {row[0]}")
            print(f"Symbol: {row[1]}")
            print(f"Direction: {row[2]}")
            print(f"Entry: {row[3]}")
            print(f"Stop Loss: {row[4]}")
            print(f"Take Profit: {row[5]}")
            print(f"Volume: {row[6]}")
            print(f"Status: {row[10]}")
            print(f"Notes: {notes}")
            print()
            print("=" * 60)
            print("CONDITIONS ANALYSIS")
            print("=" * 60)
            print()
            print(f"Conditions: {json.dumps(conditions, indent=2)}")
            print()
            
            # Analyze conditions
            has_order_block = conditions.get("order_block", False)
            has_choch = conditions.get("choch_bull", False) or conditions.get("choch_bear", False)
            has_rejection_wick = conditions.get("rejection_wick", False)
            has_price_above = "price_above" in conditions
            has_price_below = "price_below" in conditions
            has_price_near = "price_near" in conditions
            
            # Check if notes mention strategy types
            notes_lower = notes.lower()
            mentions_ob = "order block" in notes_lower or "ob" in notes_lower or "bullish ob" in notes_lower or "bearish ob" in notes_lower
            mentions_choch = "choch" in notes_lower or "bos" in notes_lower or "structure" in notes_lower
            mentions_breakout = "breakout" in notes_lower or "inside bar" in notes_lower or "volatility trap" in notes_lower
            mentions_rejection = "rejection" in notes_lower or "wick" in notes_lower or "pin bar" in notes_lower
            
            print("=" * 60)
            print("STRATEGY ANALYSIS")
            print("=" * 60)
            print()
            
            if mentions_ob:
                print("WARNING: Notes mention Order Block strategy")
                if not has_order_block:
                    print("MISSING: order_block condition!")
                    print("   Should have: {\"order_block\": true, \"order_block_type\": \"auto\" or \"bull\", \"min_validation_score\": 60}")
                else:
                    print("OK: Has order_block condition")
                    print(f"   order_block_type: {conditions.get('order_block_type', 'not set')}")
                    print(f"   min_validation_score: {conditions.get('min_validation_score', 'not set (default: 60)')}")
            
            if mentions_choch:
                print("WARNING: Notes mention CHOCH/BOS/Structure strategy")
                if not has_choch and not has_price_above and not has_price_below:
                    print("MISSING: choch_bull/choch_bear or price_above/price_below condition!")
                    print("   Should have: {\"choch_bull\": true, \"timeframe\": \"M5\"} or {\"price_above\": entry_price}")
                else:
                    print("OK: Has structure condition")
            
            if mentions_breakout:
                print("WARNING: Notes mention Breakout strategy")
                if not has_price_above and not has_price_below:
                    print("MISSING: price_above or price_below condition!")
                    print("   Should have: {\"price_above\": entry_price} or {\"price_below\": entry_price}")
                else:
                    print("OK: Has breakout condition")
            
            if mentions_rejection:
                print("WARNING: Notes mention Rejection Wick strategy")
                if not has_rejection_wick:
                    print("MISSING: rejection_wick condition!")
                    print("   Should have: {\"rejection_wick\": true, \"timeframe\": \"M5\"}")
                else:
                    print("OK: Has rejection_wick condition")
            
            print()
            print("=" * 60)
            print("RECOMMENDATION")
            print("=" * 60)
            print()
            
            if mentions_ob and not has_order_block:
                print("ERROR: PLAN IS MISSING REQUIRED CONDITIONS!")
                print()
                print("This plan mentions Order Block but only has price_near condition.")
                print("It will execute when price reaches entry, NOT when Order Block is detected!")
                print()
                print("Required conditions:")
                print(json.dumps({
                    "order_block": True,
                    "order_block_type": "bull",  # or "auto" since notes say "bullish OB"
                    "min_validation_score": 60,
                    "price_near": row[3],
                    "tolerance": conditions.get("tolerance", 100.0),
                    "timeframe": "M1"
                }, indent=2))
            elif mentions_choch and not has_choch and not has_price_above and not has_price_below:
                print("ERROR: PLAN IS MISSING REQUIRED CONDITIONS!")
                print("This plan mentions CHOCH/Structure but only has price_near condition.")
            elif mentions_breakout and not has_price_above and not has_price_below:
                print("ERROR: PLAN IS MISSING REQUIRED CONDITIONS!")
                print("This plan mentions Breakout but only has price_near condition.")
            elif mentions_rejection and not has_rejection_wick:
                print("ERROR: PLAN IS MISSING REQUIRED CONDITIONS!")
                print("This plan mentions Rejection Wick but only has price_near condition.")
            else:
                print("SUCCESS: Plan has appropriate conditions for the strategy mentioned in notes")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    plan_id = sys.argv[1] if len(sys.argv) > 1 else "chatgpt_edc91450"
    check_plan_conditions(plan_id)

