"""
Update existing auto-execution plan to add missing price_near and tolerance conditions
"""
import sqlite3
import json
from pathlib import Path
from infra.tolerance_helper import get_price_tolerance

def update_plan_conditions(plan_id: str, add_price_near: bool = True):
    """Update a plan's conditions to add price_near and tolerance"""
    db_path = Path("data/auto_execution.db")
    
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return False
    
    try:
        with sqlite3.connect(db_path) as conn:
            # Get the plan
            cursor = conn.execute("""
                SELECT plan_id, symbol, entry_price, conditions, status
                FROM trade_plans 
                WHERE plan_id = ?
            """, (plan_id,))
            
            row = cursor.fetchone()
            
            if not row:
                print(f"Plan {plan_id} not found")
                return False
            
            plan_id_db, symbol, entry_price, conditions_json, status = row
            
            if status != 'pending':
                print(f"Plan {plan_id} is not pending (status: {status}). Cannot update.")
                return False
            
            # Parse conditions
            conditions = json.loads(conditions_json)
            
            print(f"\nCurrent plan: {plan_id}")
            print(f"Symbol: {symbol}")
            print(f"Entry Price: {entry_price}")
            print(f"Current Conditions: {json.dumps(conditions, indent=2)}")
            
            # Add price_near and tolerance if not present
            updated = False
            if add_price_near:
                if 'price_near' not in conditions:
                    conditions['price_near'] = entry_price
                    updated = True
                    print(f"\n[OK] Added price_near: {entry_price}")
                
                if 'tolerance' not in conditions:
                    # Get symbol-specific tolerance
                    symbol_base = symbol.upper().rstrip('Cc')
                    tolerance = get_price_tolerance(symbol_base)
                    conditions['tolerance'] = tolerance
                    updated = True
                    print(f"[OK] Added tolerance: {tolerance}")
            
            if not updated:
                print("\n[WARNING] Plan already has price_near and tolerance conditions")
                return False
            
            # Update the plan
            conn.execute("""
                UPDATE trade_plans 
                SET conditions = ?
                WHERE plan_id = ?
            """, (json.dumps(conditions), plan_id))
            
            conn.commit()
            
            print(f"\n[SUCCESS] Successfully updated plan {plan_id}")
            print(f"New Conditions: {json.dumps(conditions, indent=2)}")
            
            return True
            
    except Exception as e:
        print(f"Error updating plan: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    
    plan_id = "chatgpt_0ea79233"
    
    if len(sys.argv) > 1:
        plan_id = sys.argv[1]
    
    print(f"Updating plan: {plan_id}")
    success = update_plan_conditions(plan_id)
    
    if success:
        print(f"\n[SUCCESS] Plan {plan_id} updated successfully!")
    else:
        print(f"\n[ERROR] Failed to update plan {plan_id}")

