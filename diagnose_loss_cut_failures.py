#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnose why loss cuts are failing for specific positions
"""

import sys
import codecs
import MetaTrader5 as mt5

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

print("=" * 70)
print("🔍 LOSS CUT FAILURE DIAGNOSTIC")
print("=" * 70)
print()

# Failed tickets from your message
failed_tickets = [121121937, 121121944, 122129616]

# Initialize MT5
if not mt5.initialize():
    print("❌ Failed to initialize MT5")
    sys.exit(1)

print("✅ MT5 Connected")
print()

# Check each position
for ticket in failed_tickets:
    print("-" * 70)
    print(f"🎫 Ticket: {ticket}")
    print("-" * 70)
    
    # Get position
    positions = mt5.positions_get(ticket=ticket)
    
    if not positions or len(positions) == 0:
        print(f"❌ Position NOT FOUND (already closed?)")
        print()
        continue
    
    pos = positions[0]
    symbol = pos.symbol
    
    # Get symbol info
    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info:
        print(f"❌ Symbol {symbol} info not available")
        print()
        continue
    
    # Get current quote
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print(f"❌ No tick data for {symbol}")
        print()
        continue
    
    # Position details
    print(f"Symbol: {symbol}")
    print(f"Type: {'BUY' if pos.type == 0 else 'SELL'}")
    print(f"Volume: {pos.volume}")
    print(f"Entry: {pos.price_open}")
    print(f"Current: {tick.bid if pos.type == 0 else tick.ask}")
    print(f"P&L: ${pos.profit:.2f}")
    print()
    
    # Market status
    print("📊 Market Status:")
    print(f"  Trade Mode: {symbol_info.trade_mode}")
    print(f"  Trade Allowed: {symbol_info.trade_mode in [mt5.SYMBOL_TRADE_MODE_FULL, mt5.SYMBOL_TRADE_MODE_CLOSEONLY]}")
    print(f"  Session Deals: {bool(symbol_info.session_deals)}")
    print()
    
    # Spread analysis
    spread_points = tick.ask - tick.bid
    point = symbol_info.point
    spread_in_points = spread_points / point if point > 0 else 0
    
    print("📏 Spread Analysis:")
    print(f"  Bid: {tick.bid}")
    print(f"  Ask: {tick.ask}")
    print(f"  Spread: {spread_points:.5f} ({spread_in_points:.1f} points)")
    print(f"  Point Size: {point}")
    
    # Check if spread is too wide
    if spread_in_points > 50:
        print(f"  ⚠️  SPREAD TOO WIDE! ({spread_in_points:.1f} points)")
    else:
        print(f"  ✅ Spread OK")
    print()
    
    # Filling modes
    print("🔧 Filling Modes Supported:")
    filling = symbol_info.filling_mode
    
    # MT5 filling mode flags
    SYMBOL_FILLING_IOC = 2
    SYMBOL_FILLING_FOK = 1
    SYMBOL_FILLING_RETURN = 4
    
    if filling & SYMBOL_FILLING_IOC:
        print("  ✅ IOC (Immediate or Cancel)")
    else:
        print("  ❌ IOC NOT supported")
    
    if filling & SYMBOL_FILLING_FOK:
        print("  ✅ FOK (Fill or Kill)")
    else:
        print("  ❌ FOK NOT supported")
    
    if filling & SYMBOL_FILLING_RETURN:
        print("  ✅ RETURN")
    else:
        print("  ❌ RETURN NOT supported")
    print()
    
    # Volume limits
    print("📦 Volume Limits:")
    print(f"  Min Volume: {symbol_info.volume_min}")
    print(f"  Max Volume: {symbol_info.volume_max}")
    print(f"  Volume Step: {symbol_info.volume_step}")
    print(f"  Position Volume: {pos.volume}")
    
    if pos.volume < symbol_info.volume_min:
        print(f"  ❌ Volume too small!")
    elif pos.volume > symbol_info.volume_max:
        print(f"  ❌ Volume too large!")
    else:
        print(f"  ✅ Volume OK")
    print()
    
    # Try to simulate close
    print("🧪 Simulated Close Test:")
    
    # Determine close parameters
    is_buy = pos.type == 0
    close_price = tick.bid if is_buy else tick.ask
    order_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
    
    # Compute deviation
    atr_points = 20  # Default
    deviation = max(10, int(atr_points * 2))
    
    # Determine best filling mode
    if filling & SYMBOL_FILLING_IOC:
        filling_mode = mt5.ORDER_FILLING_IOC
        filling_name = "IOC"
    elif filling & SYMBOL_FILLING_FOK:
        filling_mode = mt5.ORDER_FILLING_FOK
        filling_name = "FOK"
    elif filling & SYMBOL_FILLING_RETURN:
        filling_mode = mt5.ORDER_FILLING_RETURN
        filling_name = "RETURN"
    else:
        print("  ❌ NO SUPPORTED FILLING MODE!")
        print()
        continue
    
    print(f"  Close Price: {close_price}")
    print(f"  Order Type: {'SELL' if is_buy else 'BUY'}")
    print(f"  Deviation: {deviation} points")
    print(f"  Filling Mode: {filling_name}")
    print()
    
    # Check if we can actually close
    can_close = True
    reasons = []
    
    if not symbol_info.trade_mode in [mt5.SYMBOL_TRADE_MODE_FULL, mt5.SYMBOL_TRADE_MODE_CLOSEONLY]:
        can_close = False
        reasons.append("Trading not allowed")
    
    if not bool(symbol_info.session_deals):
        can_close = False
        reasons.append("Session deals disabled")
    
    if spread_in_points > 100:
        can_close = False
        reasons.append(f"Spread too wide ({spread_in_points:.1f} points)")
    
    if pos.volume < symbol_info.volume_min:
        can_close = False
        reasons.append("Volume too small")
    
    if can_close:
        print("  ✅ Position SHOULD be closeable")
        print()
        print("  💡 Possible reasons for failure:")
        print("     - Broker-side restrictions")
        print("     - Insufficient margin")
        print("     - Price moved during execution")
        print("     - Broker rejecting IOC orders")
        print()
        print("  🔧 Suggested fixes:")
        print("     1. Try FOK instead of IOC")
        print("     2. Increase deviation (currently using 2x ATR)")
        print("     3. Wait for spread to normalize")
        print("     4. Check broker's trading hours for this symbol")
    else:
        print("  ❌ Position CANNOT be closed:")
        for reason in reasons:
            print(f"     - {reason}")
    
    print()

# Get last error
last_error = mt5.last_error()
if last_error and last_error[0] != 1:  # 1 = RET_OK
    print("=" * 70)
    print("⚠️  MT5 LAST ERROR")
    print("=" * 70)
    print(f"Code: {last_error[0]}")
    print(f"Message: {last_error[1]}")
    print()

mt5.shutdown()

print("=" * 70)
print("💡 RECOMMENDATIONS")
print("=" * 70)
print()
print("1. Check if these positions still exist")
print("   (They may have been closed manually or hit SL)")
print()
print("2. If spread is too wide:")
print("   - Wait for market to calm down")
print("   - System will retry automatically")
print()
print("3. If filling mode is the issue:")
print("   - Update loss_cutter.py to try FOK if IOC fails")
print("   - Or use RETURN mode as fallback")
print()
print("4. Check broker's trading hours:")
print("   - Some brokers have restricted hours for certain symbols")
print("   - GBPJPY may have different hours than EURUSD")
print()
print("5. Monitor Telegram bot console:")
print("   - Look for MT5 retcode errors")
print("   - Common codes: 10004 (requote), 10006 (rejected)")
print()
print("=" * 70)

