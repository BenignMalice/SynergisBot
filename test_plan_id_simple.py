#!/usr/bin/env python3
"""Simple test for plan_id Discord inclusion"""

import sys
import sqlite3
from pathlib import Path

# Force output
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

print("Starting test...", flush=True)

# Test database connection
db_path = Path("data/auto_execution.db")
print(f"Database path: {db_path}", flush=True)
print(f"Database exists: {db_path.exists()}", flush=True)

if db_path.exists():
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("""
            SELECT plan_id, ticket, symbol, direction, executed_at
            FROM trade_plans 
            WHERE status = 'executed' AND ticket IS NOT NULL
            ORDER BY executed_at DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()
        
        if row:
            plan_id, ticket, symbol, direction, executed_at = row
            print(f"\n✅ Found executed plan:", flush=True)
            print(f"   Plan ID: {plan_id}", flush=True)
            print(f"   Ticket: {ticket}", flush=True)
            print(f"   Symbol: {symbol}", flush=True)
            
            # Test lookup
            conn2 = sqlite3.connect(str(db_path))
            cursor2 = conn2.execute("SELECT plan_id FROM trade_plans WHERE ticket = ?", (ticket,))
            result = cursor2.fetchone()
            conn2.close()
            
            if result and result[0] == plan_id:
                print(f"✅ Lookup test PASSED - Retrieved: {result[0]}", flush=True)
                
                # Test Discord message
                try:
                    from discord_notifications import DiscordNotifier
                    notifier = DiscordNotifier()
                    
                    if notifier.enabled:
                        plan_id_line = f"📊 **Plan ID**: {plan_id}\n"
                        test_msg = (
                            f"🧪 **TEST: Plan ID Inclusion**\n\n"
                            f"🎫 **Ticket**: {ticket}\n"
                            f"{plan_id_line}"
                            f"💱 **Symbol**: {symbol}\n"
                            f"📊 **Direction**: {direction}\n\n"
                            f"✅ This is a test to verify plan_id is included in Discord messages!"
                        )
                        
                        success = notifier.send_system_alert("TEST", test_msg)
                        if success:
                            print(f"✅ Discord message sent! Check Discord for plan_id: {plan_id}", flush=True)
                        else:
                            print("❌ Failed to send Discord message", flush=True)
                    else:
                        print("⚠️ Discord notifications disabled", flush=True)
                except Exception as e:
                    print(f"❌ Discord error: {e}", flush=True)
            else:
                print(f"❌ Lookup test FAILED", flush=True)
        else:
            print("⚠️ No executed plans found in database", flush=True)
    except Exception as e:
        print(f"❌ Database error: {e}", flush=True)
        import traceback
        traceback.print_exc()
else:
    print("❌ Database file not found", flush=True)

print("\nTest complete!", flush=True)

