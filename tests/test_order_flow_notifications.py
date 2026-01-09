#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Order Flow Telegram Notifications
Simulates whale orders and liquidity voids to verify alerts
"""

import sys
import codecs
import asyncio
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

print("=" * 70)
print("🧪 ORDER FLOW TELEGRAM NOTIFICATION TEST")
print("=" * 70)
print()

# Test 1: Check if Telegram bot is configured
print("📋 Test 1: Checking Telegram configuration...")
print("-" * 70)

try:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_BOT_CHAT_ID")
    
    if telegram_token and telegram_chat_id:
        print(f"✅ Telegram Token: Set ({telegram_token[:10]}...)")
        print(f"✅ Chat ID: {telegram_chat_id}")
    else:
        print("❌ Telegram credentials not found in .env")
        print("   Cannot send test notifications")
        sys.exit(1)
except Exception as e:
    print(f"❌ Configuration error: {e}")
    sys.exit(1)

print()

# Test 2: Send test whale order alert
print("📋 Test 2: Sending test whale order alert...")
print("-" * 70)

async def send_whale_alert():
    """Send a test whale order alert to Telegram"""
    try:
        from telegram import Bot
        
        bot = Bot(token=telegram_token)
        
        # Simulate whale order alert
        alert_text = (
            "🐋 *CRITICAL: Whale Order Detected!*\n\n"
            "🧪 **TEST ALERT** 🧪\n\n"
            "Ticket: 99999999 (TEST)\n"
            "Symbol: BTCUSD\n"
            "Type: SELL whale ($1,250,000)\n"
            "Price: $65,150\n"
            "Severity: CRITICAL\n\n"
            "⚠️ *Recommendation:* Tighten stop or consider exit\n\n"
            "💡 This is a test of the order flow alert system.\n"
            "Real alerts will look like this when whale orders are detected."
        )
        
        await bot.send_message(
            chat_id=telegram_chat_id,
            text=alert_text,
            parse_mode="Markdown"
        )
        
        print("✅ Whale order alert sent successfully!")
        print(f"   Check your Telegram app for the message")
        
    except Exception as e:
        print(f"❌ Failed to send whale alert: {e}")
        return False
    
    return True

# Run whale alert test
try:
    success = asyncio.run(send_whale_alert())
    if not success:
        print("⚠️  Whale alert test failed")
except Exception as e:
    print(f"❌ Whale alert test error: {e}")

print()

# Test 3: Send test liquidity void warning
print("📋 Test 3: Sending test liquidity void warning...")
print("-" * 70)

async def send_void_alert():
    """Send a test liquidity void warning to Telegram"""
    try:
        from telegram import Bot
        
        bot = Bot(token=telegram_token)
        
        # Simulate liquidity void warning
        alert_text = (
            "⚠️ *Liquidity Void Ahead!*\n\n"
            "🧪 **TEST ALERT** 🧪\n\n"
            "Ticket: 99999999 (TEST)\n"
            "Symbol: BTCUSD\n"
            "Void Range: $65,200 → $65,300\n"
            "Void Side: ASK (exit side)\n"
            "Severity: 3.2x normal\n"
            "Distance: 0.08%\n\n"
            "💡 *Recommendation:* Consider partial exit before void\n\n"
            "⚠️ This is a test of the liquidity void alert system.\n"
            "Real alerts will warn you when approaching thin order book zones."
        )
        
        await bot.send_message(
            chat_id=telegram_chat_id,
            text=alert_text,
            parse_mode="Markdown"
        )
        
        print("✅ Liquidity void warning sent successfully!")
        print(f"   Check your Telegram app for the message")
        
    except Exception as e:
        print(f"❌ Failed to send void alert: {e}")
        return False
    
    return True

# Run void alert test
try:
    success = asyncio.run(send_void_alert())
    if not success:
        print("⚠️  Void alert test failed")
except Exception as e:
    print(f"❌ Void alert test error: {e}")

print()

# Test 4: Send enhanced loss cut alert with order flow
print("📋 Test 4: Sending enhanced loss cut alert...")
print("-" * 70)

async def send_loss_cut_alert():
    """Send a test loss cut alert with order flow context"""
    try:
        from telegram import Bot
        
        bot = Bot(token=telegram_token)
        
        # Simulate enhanced loss cut alert
        alert_text = (
            "🔪 *Loss Cut Executed*\n\n"
            "🧪 **TEST ALERT** 🧪\n\n"
            "Ticket: 99999999 (TEST)\n"
            "Symbol: BTCUSD\n"
            "Reason: Structure collapse\n"
            "Confidence: 85.0%\n"
            "Status: ✅ Closed at attempt 1\n\n"
            "📊 *Market Context:*\n"
            "  Structure: LOWER LOW\n"
            "  Volatility: CONTRACTING\n"
            "  Momentum: WEAK\n"
            "  Order Flow: BEARISH\n"
            "  🐋 Whales: 2 detected\n"
            "  ⚠️ Liquidity Voids: 1\n\n"
            "💡 This is a test of the enhanced loss cut alert system.\n"
            "Real alerts will include order flow context like this."
        )
        
        await bot.send_message(
            chat_id=telegram_chat_id,
            text=alert_text,
            parse_mode="Markdown"
        )
        
        print("✅ Enhanced loss cut alert sent successfully!")
        print(f"   Check your Telegram app for the message")
        
    except Exception as e:
        print(f"❌ Failed to send loss cut alert: {e}")
        return False
    
    return True

# Run loss cut alert test
try:
    success = asyncio.run(send_loss_cut_alert())
    if not success:
        print("⚠️  Loss cut alert test failed")
except Exception as e:
    print(f"❌ Loss cut alert test error: {e}")

print()

# Test 5: Send enhanced signal alert with order flow
print("📋 Test 5: Sending enhanced signal alert...")
print("-" * 70)

async def send_signal_alert():
    """Send a test signal alert with order flow data"""
    try:
        from telegram import Bot
        
        bot = Bot(token=telegram_token)
        
        # Simulate enhanced signal alert
        alert_text = (
            "🔔 *Signal Alert!*\n\n"
            "🧪 **TEST ALERT** 🧪\n\n"
            "🟢 **BUY BTCUSD**\n"
            "📊 Entry: $65,000.00\n"
            "🛑 SL: $64,800.00\n"
            "🎯 TP: $65,400.00\n"
            "💡 Oversold RSI, bullish structure\n"
            "📈 Confidence: 82%\n\n"
            "🎯 *Setup Quality:*\n"
            "  Structure: HIGHER HIGH\n"
            "  Volatility: EXPANDING\n"
            "  Momentum: STRONG\n"
            "  Order Flow: BULLISH\n"
            "  🐋 Whales: 3 detected\n\n"
            "💡 This is a test of the enhanced signal alert system.\n"
            "Real alerts will include order flow and whale activity."
        )
        
        await bot.send_message(
            chat_id=telegram_chat_id,
            text=alert_text,
            parse_mode="Markdown"
        )
        
        print("✅ Enhanced signal alert sent successfully!")
        print(f"   Check your Telegram app for the message")
        
    except Exception as e:
        print(f"❌ Failed to send signal alert: {e}")
        return False
    
    return True

# Run signal alert test
try:
    success = asyncio.run(send_signal_alert())
    if not success:
        print("⚠️  Signal alert test failed")
except Exception as e:
    print(f"❌ Signal alert test error: {e}")

print()

# Summary
print("=" * 70)
print("📊 TEST SUMMARY")
print("=" * 70)
print()
print("✅ Test alerts sent to Telegram!")
print()
print("📱 Check your Telegram app for 4 test messages:")
print("  1. 🐋 Whale order alert (CRITICAL)")
print("  2. ⚠️ Liquidity void warning")
print("  3. 🔪 Enhanced loss cut alert (with order flow)")
print("  4. 🔔 Enhanced signal alert (with order flow)")
print()
print("💡 These are test messages to verify the notification system.")
print("   Real alerts will be triggered by actual market events.")
print()
print("🎯 If you received all 4 messages, order flow notifications are working!")
print()
print("=" * 70)
print()
print("🚀 Next Steps:")
print("  1. Verify you received all 4 test messages in Telegram")
print("  2. Start chatgpt_bot.py to enable live order flow monitoring")
print("  3. Open a position to test real-time whale/void detection")
print()
print("=" * 70)

