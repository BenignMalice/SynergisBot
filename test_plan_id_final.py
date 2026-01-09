#!/usr/bin/env python3
"""Final test - finds a real executed plan and tests with it"""

import sqlite3
from pathlib import Path
from discord_notifications import DiscordNotifier

db_path = Path("data/auto_execution.db")

print("=" * 70)
print("FINAL TEST: Plan ID Inclusion in Discord Messages")
print("=" * 70)

if not db_path.exists():
    print(f"❌ Database not found at {db_path}")
    exit(1)

try:
    with sqlite3.connect(str(db_path), timeout=5.0) as conn:
        # Find the most recent executed plan with a ticket
        cursor = conn.execute("""
            SELECT plan_id, ticket, symbol, direction, entry_price, executed_at
            FROM trade_plans 
            WHERE status = 'executed' AND ticket IS NOT NULL
            ORDER BY executed_at DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        
        if not row:
            print("❌ No executed plans found in database")
            print("   Wait for an auto-execution plan to execute, then test again")
            exit(1)
        
        plan_id, ticket, symbol, direction, entry_price, executed_at = row
        
        print(f"\n✅ Found executed plan:")
        print(f"   Plan ID: {plan_id}")
        print(f"   Ticket: {ticket}")
        print(f"   Symbol: {symbol}")
        print(f"   Direction: {direction}")
        print(f"   Entry: {entry_price}")
        print(f"   Executed: {executed_at}")
        
        # Test lookup function
        print(f"\n🔍 Testing lookup function...")
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
        
        retrieved_plan_id = get_plan_id_from_ticket(ticket)
        
        if retrieved_plan_id == plan_id:
            print(f"✅ Lookup PASSED - Retrieved: {retrieved_plan_id}")
        else:
            print(f"❌ Lookup FAILED - Expected {plan_id}, got {retrieved_plan_id}")
            exit(1)
        
        # Send test Discord message
        print(f"\n📤 Sending test Discord message...")
        discord_notifier = DiscordNotifier()
        
        if not discord_notifier.enabled:
            print("⚠️ Discord notifications are disabled")
            exit(1)
        
        # Build message exactly like the real notification code
        plan_id_line = f"📊 Plan ID: {retrieved_plan_id}\n" if retrieved_plan_id else ""
        
        test_message = (
            f"🧪 **TEST: Intelligent Exits Auto-Enabled**\n\n"
            f"Ticket: {ticket}\n"
            f"{plan_id_line}"
            f"Symbol: {symbol}\n"
            f"Direction: {direction.upper()}\n"
            f"Entry: {entry_price:.5f}\n\n"
            f"📊 Auto-Management Active:\n"
            f"• 🎯 Breakeven: Test level\n"
            f"• 💰 Partial: Test level\n"
            f"• 🔬 Hybrid ATR+VIX: ON\n"
            f"• 📈 ATR Trailing: ON\n\n"
            f"✅ TEST: Plan ID '{retrieved_plan_id}' should be visible above!"
        )
        
        print(f"\n📋 Message that will be sent:")
        print("-" * 70)
        print(test_message)
        print("-" * 70)
        
        success = discord_notifier.send_system_alert("Intelligent Exits Auto-Enabled", test_message)
        
        if success:
            print(f"\n✅ Discord message sent successfully!")
            print(f"   👉 Check your Discord - you should see:")
            print(f"      📊 Plan ID: {retrieved_plan_id}")
            print(f"   between the Ticket and Symbol lines")
        else:
            print("\n❌ Failed to send Discord message")
            
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("Test complete!")
print("=" * 70)

