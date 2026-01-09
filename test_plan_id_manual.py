#!/usr/bin/env python3
"""Manual test using the ticket from user's example"""

import sqlite3
from pathlib import Path
from discord_notifications import DiscordNotifier

# Use the ticket from the user's example message
TEST_TICKET = 164023491

print("=" * 60)
print("Testing Plan ID Inclusion in Discord Messages")
print("=" * 60)

# Test 1: Lookup function
print(f"\n1. Testing plan_id lookup for ticket {TEST_TICKET}...")
db_path = Path("data/auto_execution.db")

if not db_path.exists():
    print(f"❌ Database not found at {db_path}")
    exit(1)

try:
    with sqlite3.connect(str(db_path), timeout=5.0) as conn:
        cursor = conn.execute("SELECT plan_id FROM trade_plans WHERE ticket = ?", (TEST_TICKET,))
        row = cursor.fetchone()
        
        if row:
            plan_id = row[0]
            print(f"✅ Found plan_id: {plan_id}")
        else:
            print(f"⚠️ No plan_id found for ticket {TEST_TICKET}")
            print("   This might be a manual trade or the ticket doesn't exist in DB")
            plan_id = None
except Exception as e:
    print(f"❌ Error: {e}")
    plan_id = None

# Test 2: Send Discord message
print(f"\n2. Sending test Discord message...")
try:
    discord_notifier = DiscordNotifier()
    
    if not discord_notifier.enabled:
        print("⚠️ Discord notifications are disabled")
        exit(1)
    
    # Build message similar to Intelligent Exits notification
    plan_id_line = f"📊 **Plan ID**: {plan_id}\n" if plan_id else ""
    
    test_message = (
        f"🧪 **TEST: Intelligent Exits Auto-Enabled**\n\n"
        f"🎫 **Ticket**: {TEST_TICKET}\n"
        f"{plan_id_line}"
        f"💱 **Symbol**: BTCUSDc\n"
        f"📊 **Direction**: BUY\n"
        f"💰 **Entry**: 89760.0\n\n"
        f"📊 Auto-Management Active:\n"
        f"• 🎯 Breakeven: Test level\n"
        f"• 💰 Partial: Test level\n"
        f"• 🔬 Hybrid ATR+VIX: ON\n"
        f"• 📈 ATR Trailing: ON\n\n"
        f"✅ This is a TEST message to verify plan_id inclusion in Discord alerts!"
    )
    
    success = discord_notifier.send_system_alert("Intelligent Exits Auto-Enabled", test_message)
    
    if success:
        print("✅ Discord message sent successfully!")
        if plan_id:
            print(f"   ✅ Plan ID '{plan_id}' should be visible in the Discord message")
        else:
            print(f"   ⚠️ No plan_id found - message sent without plan_id line")
        print("\n   👉 Check your Discord to verify the message format!")
    else:
        print("❌ Failed to send Discord message")
        
except Exception as e:
    print(f"❌ Error sending Discord message: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)

