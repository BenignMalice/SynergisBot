import sqlite3
import json
from pathlib import Path

db_path = Path("data/auto_execution.db")
if not db_path.exists():
    print("Database not found")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.execute("""
    SELECT plan_id, symbol, conditions, notes, created_at 
    FROM trade_plans 
    WHERE status = 'pending' 
    ORDER BY created_at DESC 
    LIMIT 1
""")

row = cursor.fetchone()
if row:
    plan_id, symbol, conditions_json, notes, created_at = row
    print(f"Plan ID: {plan_id}")
    print(f"Symbol: {symbol}")
    print(f"Created: {created_at}")
    print("\n" + "=" * 60)
    print("CONDITIONS IN DATABASE:")
    print("=" * 60)
    conditions = json.loads(conditions_json) if conditions_json else {}
    print(json.dumps(conditions, indent=2))
    print("\n" + "=" * 60)
    print("NOTES/REASONING (first 1000 chars):")
    print("=" * 60)
    print(notes[:1000] if notes else "None")
    print("\n" + "=" * 60)
    print("ANALYSIS:")
    print("=" * 60)
    print(f"Total conditions: {len(conditions)}")
    print(f"Has min_confluence: {'min_confluence' in conditions or 'range_scalp_confluence' in conditions}")
    print(f"Has min_validation_score: {'min_validation_score' in conditions}")
    print(f"Has risk_filters: {'risk_filters' in conditions}")
    
    # Check if notes mention these thresholds
    if notes:
        notes_lower = notes.lower()
        mentions_min_confluence = any(term in notes_lower for term in ['min_confluence', 'confluence ≥', 'confluence >=', 'confluence score'])
        mentions_validation = any(term in notes_lower for term in ['min_validation_score', 'validation score', 'validation ≥', 'validation >='])
        mentions_risk = any(term in notes_lower for term in ['risk filter', 'risk filters'])
        
        print(f"\nNotes mentions min_confluence: {mentions_min_confluence}")
        print(f"Notes mentions min_validation_score: {mentions_validation}")
        print(f"Notes mentions risk_filters: {mentions_risk}")
        
        if (mentions_min_confluence and not ('min_confluence' in conditions or 'range_scalp_confluence' in conditions)) or \
           (mentions_validation and 'min_validation_score' not in conditions) or \
           (mentions_risk and 'risk_filters' not in conditions):
            print("\n⚠️ WARNING: Notes mention thresholds but they're NOT in conditions dict!")
else:
    print("No pending plans found")

conn.close()

