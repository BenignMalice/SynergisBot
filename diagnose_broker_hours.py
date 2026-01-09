#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnose Broker Trading Hours Issue
Check what MT5 is reporting for symbol trading status
"""

import sys
import codecs
import MetaTrader5 as mt5
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

print("=" * 70)
print("🔍 BROKER TRADING HOURS DIAGNOSTIC")
print("=" * 70)
print()

# Initialize MT5
print("📋 Initializing MT5...")
if not mt5.initialize():
    print(f"❌ MT5 initialization failed: {mt5.last_error()}")
    sys.exit(1)

print("✅ MT5 initialized")
print()

# Get account info
account_info = mt5.account_info()
if account_info:
    print(f"📊 Account: {account_info.login}")
    print(f"   Server: {account_info.server}")
    print(f"   Broker: {account_info.company}")
    print()

# Check the problematic symbols
symbols_to_check = ["GBPUSDc", "GBPJPYc", "EURUSDc", "BTCUSDc", "XAUUSDc"]

print("=" * 70)
print("📊 SYMBOL TRADING STATUS")
print("=" * 70)
print()

for symbol in symbols_to_check:
    print(f"🔍 Checking {symbol}...")
    print("-" * 70)
    
    # Get symbol info
    symbol_info = mt5.symbol_info(symbol)
    
    if symbol_info is None:
        print(f"❌ Symbol not found: {symbol}")
        print()
        continue
    
    # Get last tick
    tick = mt5.symbol_info_tick(symbol)
    
    # Current time
    now = datetime.now()
    
    print(f"✅ Symbol found")
    print()
    
    # Trading flags
    print("🚦 Trading Flags:")
    print(f"   visible: {symbol_info.visible}")
    print(f"   select: {symbol_info.select}")
    print(f"   trade_mode: {symbol_info.trade_mode}")
    print(f"      (0=disabled, 1=longonly, 2=shortonly, 3=closeonly, 4=full)")
    
    # Session flags - these are the ones causing issues
    print()
    print("⏰ Session Flags:")
    print(f"   session_deals: {symbol_info.session_deals}")
    print(f"   session_buy_orders: {symbol_info.session_buy_orders}")
    print(f"   session_sell_orders: {symbol_info.session_sell_orders}")
    
    # Tick info
    print()
    print("📈 Last Tick:")
    if tick:
        tick_time = datetime.fromtimestamp(tick.time)
        age_seconds = (now - tick_time).total_seconds()
        print(f"   time: {tick_time}")
        print(f"   age: {age_seconds:.1f} seconds")
        print(f"   bid: {tick.bid}")
        print(f"   ask: {tick.ask}")
    else:
        print("   ❌ No tick data")
    
    # Trading hours info
    print()
    print("🕐 Trading Hours:")
    print(f"   trade_stops_level: {symbol_info.trade_stops_level}")
    print(f"   trade_freeze_level: {symbol_info.trade_freeze_level}")
    
    # Diagnosis
    print()
    print("🎯 Diagnosis:")
    
    can_trade = True
    reasons = []
    
    if not symbol_info.session_deals:
        can_trade = False
        reasons.append("❌ session_deals = False (broker says deals disabled)")
    else:
        reasons.append("✅ session_deals = True")
    
    if symbol_info.trade_mode not in [4]:  # 4 = full trading
        can_trade = False
        reasons.append(f"❌ trade_mode = {symbol_info.trade_mode} (not full trading)")
    else:
        reasons.append("✅ trade_mode = 4 (full trading)")
    
    if tick:
        tick_time = datetime.fromtimestamp(tick.time)
        age_seconds = (now - tick_time).total_seconds()
        if age_seconds > 600:  # 10 minutes
            can_trade = False
            reasons.append(f"❌ Last tick is {age_seconds:.0f}s old (stale)")
        else:
            reasons.append(f"✅ Last tick is {age_seconds:.0f}s old (fresh)")
    else:
        can_trade = False
        reasons.append("❌ No tick data available")
    
    for reason in reasons:
        print(f"   {reason}")
    
    print()
    if can_trade:
        print("   ✅ SHOULD BE ABLE TO TRADE")
    else:
        print("   ❌ CANNOT TRADE (according to MT5)")
    
    print()
    print("=" * 70)
    print()

# Check open positions
print()
print("=" * 70)
print("📊 OPEN POSITIONS")
print("=" * 70)
print()

positions = mt5.positions_get()
if positions:
    print(f"Found {len(positions)} open position(s):")
    print()
    
    for pos in positions:
        print(f"Ticket: {pos.ticket}")
        print(f"  Symbol: {pos.symbol}")
        print(f"  Type: {'BUY' if pos.type == 0 else 'SELL'}")
        print(f"  Volume: {pos.volume}")
        print(f"  Price: {pos.price_open}")
        print(f"  Current: {pos.price_current}")
        print(f"  Profit: ${pos.profit:.2f}")
        
        # Check if we can close this position
        symbol_info = mt5.symbol_info(pos.symbol)
        if symbol_info:
            print(f"  session_deals: {symbol_info.session_deals}")
            print(f"  trade_mode: {symbol_info.trade_mode}")
            
            if symbol_info.session_deals and symbol_info.trade_mode == 4:
                print(f"  ✅ Should be closeable")
            else:
                print(f"  ❌ Cannot close (broker restriction)")
        
        print()
else:
    print("No open positions")
    print()

# Manual close test
print("=" * 70)
print("🧪 MANUAL CLOSE TEST")
print("=" * 70)
print()

print("Testing if we can create a close request for GBPUSDc...")
print()

# Find a GBPUSDc position
gbpusd_positions = [p for p in (positions or []) if p.symbol == "GBPUSDc"]

if gbpusd_positions:
    pos = gbpusd_positions[0]
    print(f"Found position: {pos.ticket}")
    print(f"  Type: {'BUY' if pos.type == 0 else 'SELL'}")
    print(f"  Volume: {pos.volume}")
    print()
    
    # Get current price
    tick = mt5.symbol_info_tick("GBPUSDc")
    if tick:
        close_price = tick.bid if pos.type == 0 else tick.ask
        print(f"Close price: {close_price}")
        print()
        
        # Create request (but don't send it)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
            "position": pos.ticket,
            "price": close_price,
            "deviation": 20,
            "magic": 234000,
            "comment": "diagnostic test",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        print("📋 Close request structure:")
        for key, value in request.items():
            print(f"   {key}: {value}")
        print()
        
        print("⚠️ NOT sending request (diagnostic only)")
        print("   If you want to test actual close, do it manually in MT5")
    else:
        print("❌ Cannot get tick for GBPUSDc")
else:
    print("No GBPUSDc positions found")

print()
print("=" * 70)
print("🎯 SUMMARY")
print("=" * 70)
print()

print("If you can close positions manually in MT5 but the bot cannot:")
print()
print("1️⃣ **MT5 Info Stale**")
print("   → MT5 might be caching old session_deals status")
print("   → Try: Restart MT5 terminal")
print()
print("2️⃣ **Symbol Not Selected**")
print("   → Symbol might not be in Market Watch")
print("   → Try: Add symbol to Market Watch, enable 'Show All'")
print()
print("3️⃣ **Broker-Specific Hours**")
print("   → Some brokers have symbol-specific trading hours")
print("   → Check: Broker's trading schedule for GBP pairs")
print()
print("4️⃣ **Weekend/Holiday**")
print("   → Some symbols close earlier than others")
print("   → GBP pairs might close before USD pairs")
print()
print("5️⃣ **MT5 API Lag**")
print("   → session_deals flag updates with delay")
print("   → Try: Wait 1-2 minutes, check again")
print()

print("=" * 70)
print()

# Cleanup
mt5.shutdown()
print("✅ MT5 shutdown")

