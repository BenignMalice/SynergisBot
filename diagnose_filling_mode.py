#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnose Filling Mode Issue
Check what filling modes are supported for GBPJPYc
"""

import sys
import codecs
import MetaTrader5 as mt5

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

print("=" * 70)
print("🔍 FILLING MODE DIAGNOSTIC")
print("=" * 70)
print()

# Initialize MT5
print("📋 Initializing MT5...")
if not mt5.initialize():
    print(f"❌ MT5 initialization failed: {mt5.last_error()}")
    sys.exit(1)

print("✅ MT5 initialized")
print()

# Define filling mode constants
FILLING_MODES = {
    0: "FOK (Fill or Kill)",
    1: "IOC (Immediate or Cancel)",
    2: "RETURN (Return)",
}

# Check GBPJPYc
symbol = "GBPJPYc"
print(f"🔍 Checking {symbol}...")
print("-" * 70)
print()

symbol_info = mt5.symbol_info(symbol)
if not symbol_info:
    print(f"❌ Symbol not found: {symbol}")
    mt5.shutdown()
    sys.exit(1)

print(f"✅ Symbol found")
print()

# Check filling mode
print("📊 Filling Mode Info:")
print(f"   filling_mode: {symbol_info.filling_mode}")
print()

# Decode filling mode
print("🎯 Supported Filling Modes:")

# Check each bit
if symbol_info.filling_mode & 1:  # FOK
    print("   ✅ FOK (Fill or Kill) - bit 0")
else:
    print("   ❌ FOK (Fill or Kill) - NOT supported")

if symbol_info.filling_mode & 2:  # IOC
    print("   ✅ IOC (Immediate or Cancel) - bit 1")
else:
    print("   ❌ IOC (Immediate or Cancel) - NOT supported")

if symbol_info.filling_mode & 4:  # RETURN
    print("   ✅ RETURN - bit 2")
else:
    print("   ❌ RETURN - NOT supported")

print()

# Determine best filling mode
print("🎯 Recommended Filling Mode:")
if symbol_info.filling_mode & 2:  # IOC
    print("   → Use IOC (mt5.ORDER_FILLING_IOC = 1)")
    recommended = mt5.ORDER_FILLING_IOC
elif symbol_info.filling_mode & 1:  # FOK
    print("   → Use FOK (mt5.ORDER_FILLING_FOK = 0)")
    recommended = mt5.ORDER_FILLING_FOK
elif symbol_info.filling_mode & 4:  # RETURN
    print("   → Use RETURN (mt5.ORDER_FILLING_RETURN = 2)")
    recommended = mt5.ORDER_FILLING_RETURN
else:
    print("   ❌ No filling modes supported!")
    recommended = None

print()

# Check open position
print("=" * 70)
print("📊 OPEN POSITION CHECK")
print("=" * 70)
print()

positions = mt5.positions_get(symbol=symbol)
if positions and len(positions) > 0:
    pos = positions[0]
    print(f"Found position: {pos.ticket}")
    print(f"  Symbol: {pos.symbol}")
    print(f"  Type: {'BUY' if pos.type == 0 else 'SELL'}")
    print(f"  Volume: {pos.volume}")
    print(f"  Price: {pos.price_open}")
    print(f"  Current: {pos.price_current}")
    print(f"  Profit: ${pos.profit:.2f}")
    print()
    
    # Get current tick
    tick = mt5.symbol_info_tick(symbol)
    if tick:
        close_price = tick.bid if pos.type == 0 else tick.ask
        print(f"Close price: {close_price}")
        print()
        
        # Create test request (but don't send)
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
            "type_filling": recommended if recommended is not None else mt5.ORDER_FILLING_IOC,
        }
        
        print("📋 Test Close Request:")
        for key, value in request.items():
            print(f"   {key}: {value}")
        print()
        
        print("⚠️ Would you like to test this close? (y/n)")
        print("   (This will actually close the position!)")
        print()
        
        # Don't actually send for safety
        print("🛡️ Safety: Not sending request (diagnostic only)")
        print()
        print("💡 To test manually:")
        print(f"   1. Open MT5")
        print(f"   2. Right-click position {pos.ticket}")
        print(f"   3. Select 'Close'")
        print(f"   4. Check if it closes successfully")
    else:
        print("❌ Cannot get tick for close price")
else:
    print(f"No open positions for {symbol}")

print()
print("=" * 70)
print("🎯 SUMMARY")
print("=" * 70)
print()

print(f"Symbol: {symbol}")
print(f"Filling Mode Flags: {symbol_info.filling_mode}")
print()

if recommended == mt5.ORDER_FILLING_IOC:
    print("✅ IOC is supported and recommended")
    print("   → Bot should use: mt5.ORDER_FILLING_IOC (1)")
elif recommended == mt5.ORDER_FILLING_FOK:
    print("⚠️ IOC NOT supported, use FOK instead")
    print("   → Bot should use: mt5.ORDER_FILLING_FOK (0)")
elif recommended == mt5.ORDER_FILLING_RETURN:
    print("⚠️ IOC/FOK NOT supported, use RETURN instead")
    print("   → Bot should use: mt5.ORDER_FILLING_RETURN (2)")
else:
    print("❌ No filling modes supported!")

print()

if recommended != mt5.ORDER_FILLING_IOC:
    print("🔧 ACTION REQUIRED:")
    print(f"   Update loss_cutter.py to use filling mode: {recommended}")
    print()

print("=" * 70)

# Cleanup
mt5.shutdown()
print()
print("✅ MT5 shutdown")

