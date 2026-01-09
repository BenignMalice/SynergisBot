#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Check if Telegram Bot is properly configured for alerts
"""

import sys
import os
import codecs

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

print("=" * 70)
print("🔍 TELEGRAM BOT ALERT SYSTEM - STATUS CHECK")
print("=" * 70)
print()

# Check 1: Environment variables
print("📋 Check 1: Environment Variables")
print("-" * 70)

try:
    from dotenv import load_dotenv
    load_dotenv()
    
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_BOT_CHAT_ID")
    
    if telegram_token:
        print(f"✅ TELEGRAM_TOKEN: Set ({telegram_token[:10]}...)")
    else:
        print("❌ TELEGRAM_TOKEN: NOT SET")
    
    if telegram_chat_id:
        print(f"✅ TELEGRAM_BOT_CHAT_ID: {telegram_chat_id}")
    else:
        print("❌ TELEGRAM_BOT_CHAT_ID: NOT SET")
except Exception as e:
    print(f"❌ Error loading .env: {e}")

print()

# Check 2: Config settings
print("📋 Check 2: Config Settings")
print("-" * 70)

try:
    from config import settings
    
    chat_id = getattr(settings, "DEFAULT_NOTIFY_CHAT_ID", None)
    if chat_id:
        print(f"✅ DEFAULT_NOTIFY_CHAT_ID: {chat_id}")
    else:
        print("❌ DEFAULT_NOTIFY_CHAT_ID: NOT SET")
    
    # Check signal scanner settings
    scanner_enabled = getattr(settings, "SIGNAL_SCANNER_ENABLED", False)
    scanner_symbols = getattr(settings, "SIGNAL_SCANNER_SYMBOLS", [])
    scanner_interval = getattr(settings, "SIGNAL_SCANNER_INTERVAL", 0)
    
    print(f"{'✅' if scanner_enabled else '❌'} SIGNAL_SCANNER_ENABLED: {scanner_enabled}")
    print(f"✅ SIGNAL_SCANNER_SYMBOLS: {scanner_symbols}")
    print(f"✅ SIGNAL_SCANNER_INTERVAL: {scanner_interval} seconds")
    
except Exception as e:
    print(f"❌ Error loading config: {e}")

print()

# Check 3: Check if chatgpt_bot.py exists
print("📋 Check 3: Bot File")
print("-" * 70)

if os.path.exists("chatgpt_bot.py"):
    print("✅ chatgpt_bot.py: EXISTS")
    
    # Check if it has the scheduler
    with open("chatgpt_bot.py", "r", encoding="utf-8") as f:
        content = f.read()
        
        if "scheduler.add_job" in content:
            print("✅ Scheduler code: FOUND")
        else:
            print("❌ Scheduler code: NOT FOUND")
        
        if "check_positions" in content:
            print("✅ Position monitoring: FOUND")
        else:
            print("❌ Position monitoring: NOT FOUND")
        
        if "scan_for_signals" in content:
            print("✅ Signal scanner: FOUND")
        else:
            print("❌ Signal scanner: NOT FOUND")
else:
    print("❌ chatgpt_bot.py: NOT FOUND")

print()

# Check 4: Check if bot is currently running
print("📋 Check 4: Bot Process")
print("-" * 70)

try:
    import psutil
    
    bot_running = False
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            if cmdline and 'python' in proc.info['name'].lower():
                if any('chatgpt_bot.py' in str(arg) for arg in cmdline):
                    bot_running = True
                    print(f"✅ Telegram Bot is RUNNING (PID: {proc.info['pid']})")
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if not bot_running:
        print("❌ Telegram Bot is NOT RUNNING")
        print("   To start: python chatgpt_bot.py")
except ImportError:
    print("⚠️  Cannot check if bot is running (psutil not installed)")
    print("   Manually check if you have a window running chatgpt_bot.py")

print()

# Summary
print("=" * 70)
print("📊 SUMMARY")
print("=" * 70)
print()

print("✅ = Working | ❌ = Problem | ⚠️  = Warning")
print()

print("For REAL alerts, you need:")
print("  1. ✅ Telegram bot token configured")
print("  2. ✅ Chat ID configured")
print("  3. ✅ chatgpt_bot.py running 24/7")
print("  4. ✅ Scheduler active (checks every 30s-5min)")
print()

print("ChatGPT Online CANNOT:")
print("  ❌ Monitor in background")
print("  ❌ Send proactive alerts")
print("  ❌ Run scheduled tasks")
print()

print("Use Telegram Bot for alerts, Phone ChatGPT for trading!")
print()

print("=" * 70)
print("💡 NEXT STEPS")
print("=" * 70)
print()

# Determine what needs to be done
needs_action = []

try:
    if not os.getenv("TELEGRAM_TOKEN"):
        needs_action.append("Set TELEGRAM_TOKEN in .env file")
    if not os.getenv("TELEGRAM_BOT_CHAT_ID"):
        needs_action.append("Set TELEGRAM_BOT_CHAT_ID in .env file")
except:
    pass

try:
    import psutil
    bot_running = any(
        'chatgpt_bot.py' in str(proc.info.get('cmdline', []))
        for proc in psutil.process_iter(['cmdline'])
    )
    if not bot_running:
        needs_action.append("Start Telegram bot: python chatgpt_bot.py")
except:
    needs_action.append("Check if chatgpt_bot.py is running")

if needs_action:
    print("⚠️  ACTION REQUIRED:")
    for i, action in enumerate(needs_action, 1):
        print(f"  {i}. {action}")
else:
    print("✅ Everything looks good!")
    print("   Test with: /status in Telegram")

print()
print("=" * 70)

