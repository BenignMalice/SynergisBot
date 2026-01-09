#!/usr/bin/env python3
"""Debug test to find a real plan_id and test with it"""

import sqlite3
from pathlib import Path
from discord_notifications import DiscordNotifier

db_path = Path("data/auto_execution.db")

print("=" * 60)
print("Debugging Plan ID Inclusion")
print("=" * 60)

# Step 1: Check if ticket 164023491 exists
print(f"\n1. Checking ticket 164023491 in database...")
if not db_path.exists():
    print(f"❌ Database not found at {db_path}")
    exit(1)

try:
    with sqlite3.connect(str(db_path), timeout=5.0) as conn:
        cursor = conn.execute("SELECT plan_id, ticket, symbol, direction, status, executed_at FROM trade_plans WHERE ticket = ?", (164023491,))
        row = cursor.fetchone()
        
        if row:
            plan_id, ticket, symbol, direction, status, executed_at = row
            print(f"✅ Found plan for ticket {ticket}:")
            print(f"   Plan ID: {plan_id}")
            print(f"   Status: {status}")
            print(f"   Executed: {executed_at}")
        else:
            print(f"⚠️ No plan found for ticket 164023491")
            print(f"   This ticket may not be from an auto-execution plan")
            
            # Find any executed plan with a ticket
            print(f"\n2. Looking for ANY executed plan with ticket...")
            cursor2 = conn.execute("""
                SELECT plan_id, ticket, symbol, direction, executed_at
                FROM trade_plans 
                WHERE status = 'executed' AND ticket IS NOT NULL
                ORDER BY executed_at DESC
                LIMIT 1
            """)
            row2 = cursor2.fetchone()
            
            if row2:
                plan_id, ticket, symbol, direction, executed_at = row2
                print(f"✅ Found executed plan:")
                print(f"   Plan ID: {plan_id}")
                print(f"   Ticket: {ticket}")
                print(f"   Symbol: {symbol}")
                print(f"   Direction: {direction}")
                print(f"   Executed: {executed_at}")
            else:
                print(f"❌ No executed plans found in database")
                exit(1)
        
        # Step 3: Test the lookup function
        print(f"\n3. Testing lookup function...")
        test_plan_id = get_plan_id_from_ticket(ticket)
        
        if test_plan_id == plan_id:
            print(f"✅ Lookup successful! Retrieved: {test_plan_id}")
        else:
            print(f"❌ Lookup failed! Expected {plan_id}, got {test_plan_id}")
            exit(1)
        
        # Step 4: Send test message WITH plan_id
        print(f"\n4. Sending test Discord message WITH plan_id...")
        discord_notifier = DiscordNotifier()
        
        if not discord_notifier.enabled:
            print("⚠️ Discord notifications are disabled")
            exit(1)
        
        # Build message with plan_id
        plan_id_line = f"📊 **Plan ID**: {plan_id}\n"
        
        test_message = (
            f"🧪 **TEST: Intelligent Exits Auto-Enabled**\n\n"
            f"🎫 **Ticket**: {ticket}\n"
            f"{plan_id_line}"
            f"💱 **Symbol**: {symbol}\n"
            f"📊 **Direction**: {direction}\n"
            f"💰 **Entry**: 89760.0\n\n"
            f"📊 Auto-Management Active:\n"
            f"• 🎯 Breakeven: Test level\n"
            f"• 💰 Partial: Test level\n"
            f"• 🔬 Hybrid ATR+VIX: ON\n"
            f"• 📈 ATR Trailing: ON\n\n"
            f"✅ This is a TEST message - plan_id '{plan_id}' should be visible above!"
        )
        
        success = discord_notifier.send_system_alert("Intelligent Exits Auto-Enabled", test_message)
        
        if success:
            print(f"✅ Discord message sent successfully!")
            print(f"   Plan ID '{plan_id}' should be visible in Discord")
        else:
            print("❌ Failed to send Discord message")
            
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

def get_plan_id_from_ticket(ticket: int):
    """Get auto-execution plan_id from ticket number."""
    try:
        with sqlite3.connect(str(db_path), timeout=5.0) as conn:
            cursor = conn.execute("SELECT plan_id FROM trade_plans WHERE ticket = ?", (ticket,))
            row = cursor.fetchone()
            if row:
                return row[0]
            return None
    except Exception as e:
        print(f"Error in lookup: {e}")
        return None

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)

