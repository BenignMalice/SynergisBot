#!/usr/bin/env python3
"""
Discord Setup Guide
Non-interactive guide for setting up Discord notifications
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def show_discord_setup_guide():
    """Show Discord setup guide"""
    print("Discord Trading Notifications Setup")
    print("=" * 40)
    print()
    print("STEP 1: Create Discord Webhook")
    print("-" * 30)
    print("1. Open Discord in your browser or app")
    print("2. Go to your server (or create one)")
    print("3. Right-click on a channel -> 'Edit Channel'")
    print("4. Go to 'Integrations' -> 'Webhooks'")
    print("5. Click 'Create Webhook'")
    print("6. Copy the webhook URL")
    print()
    print("STEP 2: Add to .env file")
    print("-" * 30)
    print("Add these lines to your .env file:")
    print()
    print("# Discord Notifications")
    print("DISCORD_WEBHOOK_URL=your_webhook_url_here")
    print("DISCORD_BOT_NAME=Trading Bot")
    print()
    print("Example webhook URL:")
    print("https://discord.com/api/webhooks/123456789/abcdefghijklmnop")
    print()
    print("STEP 3: Test Discord Notifications")
    print("-" * 30)
    print("Run: python test_discord.py")
    print()

def test_discord_connection():
    """Test Discord connection"""
    print("Testing Discord Connection...")
    print("=" * 30)
    
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    
    if not webhook_url:
        print("FAILED: DISCORD_WEBHOOK_URL not found in .env file")
        print("Please add it following the setup guide above")
        return False
    
    try:
        import requests
        
        # Test webhook
        data = {
            "username": "Trading Bot",
            "content": "Test message from your trading bot!"
        }
        
        response = requests.post(webhook_url, json=data, timeout=10)
        
        if response.status_code == 204:
            print("SUCCESS: Discord webhook is working!")
            print("Check your Discord channel for the test message")
            return True
        else:
            print(f"FAILED: Discord webhook failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"ERROR: Discord test failed: {e}")
        return False

def create_discord_example():
    """Create Discord example"""
    example_content = '''#!/usr/bin/env python3
"""
Discord Trading Bot Example
This shows how to use Discord notifications in your trading bot.
"""

from discord_notifications import DiscordNotifier

def example_trading_scenario():
    """Example trading scenario with Discord notifications"""
    
    discord = DiscordNotifier()
    
    if not discord.enabled:
        print("Discord not configured. Please set up webhook first.")
        return
    
    # 1. Bot startup
    discord.send_system_alert("BOT_START", "Trading bot has started successfully")
    
    # 2. Trade opened
    discord.send_trade_alert(
        symbol="EURUSD",
        action="BUY",
        price="1.0850",
        lot_size="0.01",
        status="OPENED"
    )
    
    # 3. DTMS protection
    discord.send_dtms_alert(
        ticket="12345",
        action="STOP_LOSS_UPDATED",
        reason="Price moved in favor",
        price="1.0840"
    )
    
    # 4. Trade closed with profit
    discord.send_trade_alert(
        symbol="EURUSD",
        action="SELL",
        price="1.0875",
        lot_size="0.01",
        status="CLOSED",
        profit="+$25.00"
    )
    
    # 5. Risk alert
    discord.send_risk_alert(
        level="HIGH",
        message="Maximum drawdown reached",
        action="Reducing position size"
    )

if __name__ == "__main__":
    print("Discord Trading Bot Example")
    print("=" * 40)
    example_trading_scenario()
    print("SUCCESS: Example completed - check your Discord channel!")
'''
    
    with open("discord_trading_example.py", 'w', encoding='utf-8') as f:
        f.write(example_content)
    
    print("SUCCESS: Created discord_trading_example.py")

if __name__ == "__main__":
    show_discord_setup_guide()
    
    # Check if Discord is already configured
    if os.getenv("DISCORD_WEBHOOK_URL"):
        print("Discord webhook found in .env file")
        test_discord_connection()
        create_discord_example()
    else:
        print("No Discord webhook configured yet")
        print("Please follow the setup guide above")
