#!/usr/bin/env python3
"""
Test Discord Notifications
Simple test for Discord webhook
"""

import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_discord_webhook():
    """Test Discord webhook"""
    print("Testing Discord Webhook...")
    print("=" * 30)
    
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    
    if not webhook_url:
        print("FAILED: DISCORD_WEBHOOK_URL not found in .env file")
        print("Please add it to your .env file:")
        print("DISCORD_WEBHOOK_URL=your_webhook_url_here")
        return False
    
    try:
        # Test webhook with simple message
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
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"ERROR: Discord test failed: {e}")
        return False

def test_discord_embed():
    """Test Discord embed message"""
    print("\nTesting Discord Embed...")
    print("=" * 30)
    
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    
    if not webhook_url:
        print("FAILED: DISCORD_WEBHOOK_URL not found")
        return False
    
    try:
        # Test webhook with embed
        embed = {
            "title": "Trading Bot - Test Alert",
            "description": "This is a test embed message from your trading bot",
            "color": 0x00ff00,
            "fields": [
                {
                    "name": "Symbol",
                    "value": "EURUSD",
                    "inline": True
                },
                {
                    "name": "Action",
                    "value": "BUY",
                    "inline": True
                },
                {
                    "name": "Price",
                    "value": "1.0850",
                    "inline": True
                }
            ],
            "footer": {
                "text": "MoneyBot"
            }
        }
        
        data = {
            "username": "Trading Bot",
            "embeds": [embed]
        }
        
        response = requests.post(webhook_url, json=data, timeout=10)
        
        if response.status_code == 204:
            print("SUCCESS: Discord embed is working!")
            print("Check your Discord channel for the test embed")
            return True
        else:
            print(f"FAILED: Discord embed failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"ERROR: Discord embed test failed: {e}")
        return False

if __name__ == "__main__":
    print("Discord Webhook Test")
    print("=" * 40)
    
    # Test basic webhook
    basic_success = test_discord_webhook()
    
    # Test embed
    embed_success = test_discord_embed()
    
    print("\nTest Results:")
    print("=" * 20)
    print(f"Basic Webhook: {'SUCCESS' if basic_success else 'FAILED'}")
    print(f"Embed Message: {'SUCCESS' if embed_success else 'FAILED'}")
    
    if basic_success and embed_success:
        print("\nSUCCESS: Discord notifications are ready!")
        print("You can now use Discord for trading alerts")
    else:
        print("\nFAILED: Discord setup incomplete")
        print("Please check your webhook URL and try again")
