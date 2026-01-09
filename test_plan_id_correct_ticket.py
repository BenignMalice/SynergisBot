#!/usr/bin/env python3
"""Test with the correct ticket from logs"""

import sqlite3
from pathlib import Path
from discord_notifications import DiscordNotifier

# From logs: plan chatgpt_b6963118 executed with ticket 164023493
TEST_PLAN_ID = "chatgpt_b6963118"
TEST_TICKET = 164023493  # Correct ticket from logs

print("=" * 60)
print("Testing with CORRECT ticket from logs")
print("=" * 60)
print(f"Plan ID: {TEST_PLAN_ID}")
print(f"Ticket: {TEST_TICKET}")

db_path = Path("data/auto_execution.db")

# Test 1: Verify ticket exists in database
print(f"\n1. Checking database...")
if not db_path.exists():
    print(f"❌ Database not found")
    exit(1)

try:
    with sqlite3.connect(str(db_path), timeout=5.0) as conn:
        # Check if ticket exists
        cursor = conn.execute("SELECT plan_id, ticket, symbol, status FROM trade_plans WHERE ticket = ?", (TEST_TICKET,))
        row = cursor.fetchone()
        
        if row:
            plan_id, ticket, symbol, status = row
            print(f"✅ Found in database:")
            print(f"   Plan ID: {plan_id}")
            print(f"   Ticket: {ticket}")
            print(f"   Symbol: {symbol}")
            print(f"   Status: {status}")
            
            if plan_id != TEST_PLAN_ID:
                print(f"⚠️ Warning: Plan ID mismatch! Expected {TEST_PLAN_ID}, got {plan_id}")
        else:
            print(f"❌ Ticket {TEST_TICKET} NOT FOUND in database")
            print(f"   This means the ticket wasn't saved when the plan executed")
            exit(1)
        
        # Test 2: Test lookup function
        print(f"\n2. Testing lookup function...")
        def get_plan_id_from_ticket(ticket: int):
            try:
                with sqlite3.connect(str(db_path), timeout=5.0) as conn:
                    cursor = conn.execute("SELECT plan_id FROM trade_plans WHERE ticket = ?", (ticket,))
                    row = cursor.fetchone()
                    if row:
                        return row[0]
                    return None
            except Exception as e:
                print(f"Error: {e}")
                return None
        
        retrieved_plan_id = get_plan_id_from_ticket(TEST_TICKET)
        
        if retrieved_plan_id:
            print(f"✅ Lookup successful! Retrieved: {retrieved_plan_id}")
        else:
            print(f"❌ Lookup returned None")
            exit(1)
        
        # Test 3: Send Discord message
        print(f"\n3. Sending test Discord message...")
        discord_notifier = DiscordNotifier()
        
        if not discord_notifier.enabled:
            print("⚠️ Discord notifications disabled")
            exit(1)
        
        # Build message exactly like the real notification
        plan_id = retrieved_plan_id
        plan_id_line = f"📊 Plan ID: {plan_id}\n" if plan_id else ""
        
        test_message = (
            f"🧪 **TEST: Intelligent Exits Auto-Enabled**\n\n"
            f"Ticket: {TEST_TICKET}\n"
            f"{plan_id_line}"
            f"Symbol: {symbol}\n"
            f"Direction: BUY\n"
            f"Entry: 89760.0\n\n"
            f"📊 Auto-Management Active:\n"
            f"• 🎯 Breakeven: Test level\n"
            f"• 💰 Partial: Test level\n"
            f"• 🔬 Hybrid ATR+VIX: ON\n"
            f"• 📈 ATR Trailing: ON\n\n"
            f"✅ This test uses ticket {TEST_TICKET} - plan_id '{plan_id}' should be visible!"
        )
        
        print(f"\nMessage preview:")
        print("-" * 60)
        print(test_message)
        print("-" * 60)
        
        success = discord_notifier.send_system_alert("Intelligent Exits Auto-Enabled", test_message)
        
        if success:
            print(f"\n✅ Discord message sent!")
            print(f"   Check Discord - plan_id '{plan_id}' should be visible")
        else:
            print("\n❌ Failed to send")
            
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)

