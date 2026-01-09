#!/usr/bin/env python3
"""Fixed test - uses plan_id directly to verify message format"""

from discord_notifications import DiscordNotifier

# Use the plan_id from the user's example
TEST_PLAN_ID = "chatgpt_b6963118"
TEST_TICKET = 164023491

print("=" * 60)
print("Testing Plan ID Inclusion (Fixed Version)")
print("=" * 60)

print(f"\nUsing:")
print(f"  Plan ID: {TEST_PLAN_ID}")
print(f"  Ticket: {TEST_TICKET}")

try:
    discord_notifier = DiscordNotifier()
    
    if not discord_notifier.enabled:
        print("⚠️ Discord notifications are disabled")
        exit(1)
    
    # Build message WITH plan_id (simulating what should happen)
    plan_id_line = f"📊 **Plan ID**: {TEST_PLAN_ID}\n"
    
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
        f"✅ This test shows how the message SHOULD look with plan_id included!"
    )
    
    print(f"\nMessage preview:")
    print("-" * 60)
    print(test_message)
    print("-" * 60)
    
    success = discord_notifier.send_system_alert("Intelligent Exits Auto-Enabled", test_message)
    
    if success:
        print(f"\n✅ Discord message sent!")
        print(f"   Check Discord - you should see '📊 **Plan ID**: {TEST_PLAN_ID}' in the message")
    else:
        print("\n❌ Failed to send Discord message")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)

