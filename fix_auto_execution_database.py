"""
Fix Auto-Execution Database - Mark expired/executed/cancelled plans correctly
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple

def analyze_database():
    """Analyze current database state"""
    db_path = Path("data/auto_execution.db")
    if not db_path.exists():
        print("ERROR: Database not found")
        return None
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("""
        SELECT plan_id, symbol, direction, entry_price, status, expires_at, executed_at, created_at, conditions
        FROM trade_plans
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    return rows

def fix_database():
    """Fix database by marking expired plans and cleaning up statuses"""
    db_path = Path("data/auto_execution.db")
    if not db_path.exists():
        print("ERROR: Database not found")
        return
    
    print("=" * 80)
    print("AUTO-EXECUTION DATABASE FIX")
    print("=" * 80)
    print()
    
    conn = sqlite3.connect(str(db_path))
    
    # Get all plans
    cursor = conn.execute("""
        SELECT plan_id, symbol, direction, status, expires_at, executed_at, created_at, conditions
        FROM trade_plans
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    
    now_utc = datetime.now(timezone.utc)
    
    stats = {
        "total": len(rows),
        "pending": 0,
        "expired": 0,
        "executed": 0,
        "cancelled": 0,
        "failed": 0,
        "to_expire": 0,
        "to_cancel_old": 0
    }
    
    updates = []
    
    print("Analyzing plans...")
    print()
    
    for row in rows:
        plan_id, symbol, direction, status, expires_at, executed_at, created_at, conditions_json = row
        
        # Parse dates
        try:
            if expires_at:
                expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if expires_dt.tzinfo is None:
                    expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            else:
                expires_dt = None
            
            if created_at:
                created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
            else:
                created_dt = None
        except Exception as e:
            print(f"  [WARNING] Error parsing dates for {plan_id}: {e}")
            continue
        
        # Count by status
        if status == "pending":
            stats["pending"] += 1
            
            # Check if expired
            if expires_at and expires_dt < now_utc:
                updates.append({
                    "plan_id": plan_id,
                    "old_status": status,
                    "new_status": "expired",
                    "reason": f"Expired at {expires_at}"
                })
                stats["to_expire"] += 1
            # Check if very old (created > 7 days ago, no execution)
            elif created_at and created_dt:
                days_old = (now_utc - created_dt).total_seconds() / 86400
                if days_old > 7 and not executed_at:
                    # Very old pending plan with no execution - likely abandoned
                    updates.append({
                        "plan_id": plan_id,
                        "old_status": status,
                        "new_status": "cancelled",
                        "reason": f"Abandoned (created {days_old:.1f} days ago, no execution)"
                    })
                    stats["to_cancel_old"] += 1
        elif status == "expired":
            stats["expired"] += 1
        elif status == "executed":
            stats["executed"] += 1
        elif status == "cancelled":
            stats["cancelled"] += 1
        elif status == "failed":
            stats["failed"] += 1
    
    print("Current Database State:")
    print(f"  Total Plans: {stats['total']}")
    print(f"  Pending: {stats['pending']}")
    print(f"  Expired: {stats['expired']}")
    print(f"  Executed: {stats['executed']}")
    print(f"  Cancelled: {stats['cancelled']}")
    print(f"  Failed: {stats['failed']}")
    print()
    
    print("Plans to Update:")
    print(f"  To mark as expired: {stats['to_expire']}")
    print(f"  To cancel (old/abandoned): {stats['to_cancel_old']}")
    print()
    
    if not updates:
        print("No updates needed - database is clean!")
        conn.close()
        return
    
    # Show what will be updated
    print("Updates to apply:")
    for update in updates[:10]:  # Show first 10
        print(f"  - {update['plan_id']}: {update['old_status']} -> {update['new_status']} ({update['reason']})")
    if len(updates) > 10:
        print(f"  ... and {len(updates) - 10} more")
    print()
    
    # Auto-apply updates (no confirmation needed)
    print(f"Auto-applying {len(updates)} updates...")
    
    # Apply updates
    print()
    print("Applying updates...")
    updated_count = 0
    
    for update in updates:
        try:
            if update["new_status"] == "expired":
                conn.execute("""
                    UPDATE trade_plans
                    SET status = 'expired'
                    WHERE plan_id = ?
                """, (update["plan_id"],))
            elif update["new_status"] == "cancelled":
                conn.execute("""
                    UPDATE trade_plans
                    SET status = 'cancelled'
                    WHERE plan_id = ?
                """, (update["plan_id"],))
            
            updated_count += 1
            if updated_count % 10 == 0:
                print(f"  Updated {updated_count}/{len(updates)} plans...")
        except Exception as e:
            print(f"  [ERROR] Failed to update {update['plan_id']}: {e}")
    
    conn.commit()
    conn.close()
    
    print()
    print(f"[SUCCESS] Updated {updated_count} plans")
    print()
    
    # Show final state
    print("Final Database State:")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("""
        SELECT status, COUNT(*) as count
        FROM trade_plans
        GROUP BY status
        ORDER BY count DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    for status, count in rows:
        print(f"  {status}: {count}")
    
    # Show pending count
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute("SELECT COUNT(*) FROM trade_plans WHERE status = 'pending'")
    pending_count = cursor.fetchone()[0]
    conn.close()
    
    print()
    print(f"Pending Plans: {pending_count}")
    print("=" * 80)

if __name__ == "__main__":
    fix_database()

