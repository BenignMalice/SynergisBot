"""Verify test Phase III plans were created correctly"""
import sys
import json
import codecs
import urllib.request
import sqlite3
from pathlib import Path

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

def verify_via_api(plan_ids: list):
    """Verify plans via API"""
    print("\n" + "="*70)
    print("Verifying Plans via API")
    print("="*70)
    
    API_BASE_URL = "http://localhost:8000"
    
    for plan_id in plan_ids:
        try:
            url = f"{API_BASE_URL}/auto-execution/plan-status?plan_id={plan_id}"
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                if data.get('plan_id'):
                    print(f"\n✅ Plan {plan_id}:")
                    print(f"   Symbol: {data.get('symbol')}")
                    print(f"   Direction: {data.get('direction')}")
                    print(f"   Status: {data.get('status')}")
                    print(f"   Entry: {data.get('entry_price')}")
                    print(f"   Conditions: {json.dumps(data.get('conditions', {}), indent=6)}")
                else:
                    print(f"❌ Plan {plan_id} not found via API")
        except Exception as e:
            print(f"⚠️  Error checking plan {plan_id} via API: {e}")

def verify_via_database(plan_ids: list):
    """Verify plans via database"""
    print("\n" + "="*70)
    print("Verifying Plans via Database")
    print("="*70)
    
    db_path = "data/auto_execution.db"
    
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            for plan_id in plan_ids:
                cursor.execute("""
                    SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit,
                           conditions, status, created_at, notes
                    FROM trade_plans
                    WHERE plan_id = ?
                """, (plan_id,))
                
                row = cursor.fetchone()
                if row:
                    print(f"\n✅ Plan {plan_id} found in database:")
                    print(f"   Symbol: {row['symbol']}")
                    print(f"   Direction: {row['direction']}")
                    print(f"   Status: {row['status']}")
                    print(f"   Entry: {row['entry_price']}")
                    print(f"   SL: {row['stop_loss']}")
                    print(f"   TP: {row['take_profit']}")
                    
                    # Parse conditions
                    try:
                        conditions = json.loads(row['conditions'])
                        print(f"   Conditions:")
                        for key, value in conditions.items():
                            print(f"      {key}: {value}")
                    except:
                        print(f"   Conditions: {row['conditions']}")
                    
                    print(f"   Notes: {row['notes']}")
                    print(f"   Created: {row['created_at']}")
                else:
                    print(f"❌ Plan {plan_id} not found in database")
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Test plan IDs from creation
    plan_ids = ["chatgpt_d05d9985", "chatgpt_0a116fe0"]
    
    print("="*70)
    print("Verifying Test Phase III Plans")
    print("="*70)
    print(f"Plan IDs: {', '.join(plan_ids)}")
    
    # Verify via database (more reliable)
    verify_via_database(plan_ids)
    
    # Try API verification
    try:
        verify_via_api(plan_ids)
    except Exception as e:
        print(f"\n⚠️  API verification skipped: {e}")
    
    print("\n" + "="*70)
    print("Verification Complete")
    print("="*70)

