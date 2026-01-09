#!/usr/bin/env python3
"""
Test script to verify plan_id is included in Discord notifications
"""

import sqlite3
from pathlib import Path
from discord_notifications import DiscordNotifier

def get_plan_id_from_ticket(ticket: int):
    """
    Get auto-execution plan_id from ticket number.
    
    Args:
        ticket: MT5 ticket number
        
    Returns:
        plan_id string if found, None otherwise
    """
    try:
        db_path = Path("data/auto_execution.db")
        if not db_path.exists():
            print(f"❌ Database not found at {db_path}")
            return None
        
        with sqlite3.connect(str(db_path), timeout=5.0) as conn:
            cursor = conn.execute("SELECT plan_id FROM trade_plans WHERE ticket = ?", (ticket,))
            row = cursor.fetchone()
            if row:
                return row[0]
            return None
    except Exception as e:
        print(f"❌ Error getting plan_id for ticket {ticket}: {e}")
        return None

def test_with_real_plan():
    """Test with a real plan from the database"""
    print("🔍 Looking for executed plans in database...")
    
    db_path = Path("data/auto_execution.db")
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return False
    
    try:
        with sqlite3.connect(str(db_path), timeout=5.0) as conn:
            # Find a recently executed plan with a ticket
            cursor = conn.execute("""
                SELECT plan_id, ticket, symbol, direction, entry_price, executed_at
                FROM trade_plans 
                WHERE status = 'executed' AND ticket IS NOT NULL
                ORDER BY executed_at DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            
            if not row:
                print("⚠️ No executed plans found in database")
                return False
            
            plan_id, ticket, symbol, direction, entry_price, executed_at = row
            print(f"✅ Found executed plan:")
            print(f"   Plan ID: {plan_id}")
            print(f"   Ticket: {ticket}")
            print(f"   Symbol: {symbol}")
            print(f"   Direction: {direction}")
            print(f"   Entry: {entry_price}")
            print(f"   Executed: {executed_at}")
            
            # Test the lookup function
            print(f"\n🔍 Testing plan_id lookup for ticket {ticket}...")
            retrieved_plan_id = get_plan_id_from_ticket(ticket)
            
            if retrieved_plan_id == plan_id:
                print(f"✅ Lookup successful! Retrieved plan_id: {retrieved_plan_id}")
            else:
                print(f"❌ Lookup failed! Expected {plan_id}, got {retrieved_plan_id}")
                return False
            
            # Send test Discord message
            print(f"\n📤 Sending test Discord message...")
            discord_notifier = DiscordNotifier()
            
            if not discord_notifier.enabled:
                print("⚠️ Discord notifications are disabled")
                return False
            
            # Build test message similar to Intelligent Exits notification
            plan_id_line = f"📊 **Plan ID**: {plan_id}\n" if plan_id else ""
            
            test_message = (
                f"🧪 **TEST: Intelligent Exits Auto-Enabled**\n\n"
                f"🎫 **Ticket**: {ticket}\n"
                f"{plan_id_line}"
                f"💱 **Symbol**: {symbol}\n"
                f"📊 **Direction**: {direction}\n"
                f"💰 **Entry**: {entry_price}\n\n"
                f"📊 Auto-Management Active:\n"
                f"• 🎯 Breakeven: Test level\n"
                f"• 💰 Partial: Test level\n"
                f"• 🔬 Hybrid ATR+VIX: ON\n"
                f"• 📈 ATR Trailing: ON\n\n"
                f"✅ This is a test message to verify plan_id inclusion!"
            )
            
            success = discord_notifier.send_system_alert("Intelligent Exits Auto-Enabled", test_message)
            
            if success:
                print("✅ Test Discord message sent successfully!")
                print(f"   Check Discord to verify plan_id ({plan_id}) is included")
                return True
            else:
                print("❌ Failed to send Discord message")
                return False
                
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_with_sample_ticket():
    """Test with a sample ticket (will show no plan_id)"""
    print("\n🧪 Testing with sample ticket (should show no plan_id)...")
    
    sample_ticket = 999999
    plan_id = get_plan_id_from_ticket(sample_ticket)
    
    if plan_id is None:
        print(f"✅ Correctly returned None for non-existent ticket {sample_ticket}")
    else:
        print(f"⚠️ Unexpectedly found plan_id {plan_id} for ticket {sample_ticket}")
    
    # Send test message without plan_id
    discord_notifier = DiscordNotifier()
    if discord_notifier.enabled:
        test_message = (
            f"🧪 **TEST: Trade Closed (No Plan ID)**\n\n"
            f"Ticket: {sample_ticket}\n"
            f"Symbol: TEST\n"
            f"Close Price: 100.00\n"
            f"Profit/Loss: $0.00\n"
            f"Reason: Test\n\n"
            f"✅ This trade has no plan_id (manual trade)"
        )
        
        success = discord_notifier.send_system_alert("Trade Alert", test_message)
        if success:
            print("✅ Test message sent (no plan_id expected)")
        else:
            print("❌ Failed to send test message")

if __name__ == "__main__":
    print("=" * 60)
    print("Discord Plan ID Inclusion Test")
    print("=" * 60)
    
    # Test with real plan
    success = test_with_real_plan()
    
    # Test with sample ticket
    test_with_sample_ticket()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ Test completed! Check Discord for messages.")
    else:
        print("⚠️ Test completed with warnings. Check output above.")
    print("=" * 60)

