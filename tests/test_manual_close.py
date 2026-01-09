#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Manual Close - Debug MT5 order_send
"""

import sys
import codecs
import MetaTrader5 as mt5

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

print("=" * 70)
print("🧪 MANUAL CLOSE TEST")
print("=" * 70)
print()

# Initialize MT5
print("📋 Initializing MT5...")
if not mt5.initialize():
    print(f"❌ MT5 initialization failed: {mt5.last_error()}")
    sys.exit(1)

print("✅ MT5 initialized")
print()

# Find GBPJPYc position
symbol = "GBPJPYc"
positions = mt5.positions_get(symbol=symbol)

if not positions or len(positions) == 0:
    print(f"❌ No open positions for {symbol}")
    mt5.shutdown()
    sys.exit(1)

pos = positions[0]
print(f"✅ Found position: {pos.ticket}")
print(f"   Symbol: {pos.symbol}")
print(f"   Type: {'BUY' if pos.type == 0 else 'SELL'}")
print(f"   Volume: {pos.volume}")
print(f"   Price: {pos.price_open}")
print(f"   Current: {pos.price_current}")
print(f"   Profit: ${pos.profit:.2f}")
print()

# Get current tick
tick = mt5.symbol_info_tick(symbol)
if not tick:
    print(f"❌ Cannot get tick for {symbol}")
    mt5.shutdown()
    sys.exit(1)

print(f"📊 Current Tick:")
print(f"   Bid: {tick.bid}")
print(f"   Ask: {tick.ask}")
print()

# Determine close price and order type
is_buy = pos.type == mt5.ORDER_TYPE_BUY
close_price = tick.bid if is_buy else tick.ask
order_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY

print(f"🎯 Close Details:")
print(f"   Position Type: {'BUY' if is_buy else 'SELL'}")
print(f"   Close Order Type: {'SELL' if is_buy else 'BUY'}")
print(f"   Close Price: {close_price}")
print()

# Create request
request = {
    "action": mt5.TRADE_ACTION_DEAL,
    "symbol": pos.symbol,
    "volume": pos.volume,
    "type": order_type,
    "position": pos.ticket,
    "price": close_price,
    "deviation": 20,
    "magic": 234000,
    "type_time": mt5.ORDER_TIME_GTC,
    "type_filling": mt5.ORDER_FILLING_IOC,
    "comment": "manual_test_close",
}

print("📋 Close Request:")
for key, value in request.items():
    print(f"   {key}: {value}")
print()

# Validate request
print("🔍 Validating Request...")
print()

# Check each field
errors = []

if request["action"] != mt5.TRADE_ACTION_DEAL:
    errors.append("❌ action must be TRADE_ACTION_DEAL")
else:
    print("✅ action: TRADE_ACTION_DEAL")

if not isinstance(request["symbol"], str):
    errors.append("❌ symbol must be string")
else:
    print(f"✅ symbol: {request['symbol']}")

if not isinstance(request["volume"], float):
    errors.append("❌ volume must be float")
else:
    print(f"✅ volume: {request['volume']}")

if request["type"] not in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL]:
    errors.append("❌ type must be ORDER_TYPE_BUY or ORDER_TYPE_SELL")
else:
    print(f"✅ type: {request['type']}")

if not isinstance(request["position"], int):
    errors.append("❌ position must be int")
else:
    print(f"✅ position: {request['position']}")

if not isinstance(request["price"], float):
    errors.append("❌ price must be float")
else:
    print(f"✅ price: {request['price']}")

if not isinstance(request["deviation"], int):
    errors.append("❌ deviation must be int")
else:
    print(f"✅ deviation: {request['deviation']}")

if not isinstance(request["magic"], int):
    errors.append("❌ magic must be int")
else:
    print(f"✅ magic: {request['magic']}")

if request["type_time"] != mt5.ORDER_TIME_GTC:
    errors.append("❌ type_time must be ORDER_TIME_GTC")
else:
    print(f"✅ type_time: ORDER_TIME_GTC")

if request["type_filling"] not in [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]:
    errors.append("❌ type_filling must be valid filling mode")
else:
    print(f"✅ type_filling: {request['type_filling']}")

print()

if errors:
    print("❌ Request validation failed:")
    for error in errors:
        print(f"   {error}")
    mt5.shutdown()
    sys.exit(1)

print("✅ Request validation passed")
print()

# Auto-proceed (diagnostic mode)
print("=" * 70)
print("⚠️  SENDING CLOSE ORDER (DIAGNOSTIC MODE)")
print("=" * 70)
print()
print(f"Closing position {pos.ticket} ({pos.volume} lots of {symbol})")
print()
print("🚀 Sending close order...")
print()

# Send order
result = mt5.order_send(request)

print("📊 Result:")
print(f"   result: {result}")
print()

if result is None:
    print("❌ MT5 returned None!")
    print()
    print("This means MT5 rejected the request before processing.")
    print("Possible causes:")
    print("  1. MT5 terminal not connected to broker")
    print("  2. AutoTrading disabled in MT5")
    print("  3. Invalid request structure")
    print("  4. Symbol not enabled for trading")
    print()
    
    # Check MT5 connection
    terminal_info = mt5.terminal_info()
    if terminal_info:
        print("🔍 Terminal Info:")
        print(f"   connected: {terminal_info.connected}")
        print(f"   trade_allowed: {terminal_info.trade_allowed}")
        print(f"   tradeapi_disabled: {terminal_info.tradeapi_disabled}")
        print()
        
        if not terminal_info.connected:
            print("❌ MT5 not connected to broker!")
        elif not terminal_info.trade_allowed:
            print("❌ AutoTrading disabled in MT5!")
            print("   → Enable: Tools > Options > Expert Advisors > Allow automated trading")
        elif terminal_info.tradeapi_disabled:
            print("❌ Trade API disabled!")
    
    mt5.shutdown()
    sys.exit(1)

# Parse result
print("📊 Order Result:")
print(f"   retcode: {result.retcode}")
print(f"   deal: {result.deal}")
print(f"   order: {result.order}")
print(f"   volume: {result.volume}")
print(f"   price: {result.price}")
print(f"   comment: {result.comment}")
print()

if result.retcode == mt5.TRADE_RETCODE_DONE:
    print("✅ Order executed successfully!")
    print(f"   Deal: {result.deal}")
    print(f"   Price: {result.price}")
else:
    print(f"❌ Order failed!")
    print(f"   Retcode: {result.retcode}")
    print(f"   Comment: {result.comment}")
    
    # Decode retcode
    retcode_descriptions = {
        10004: "REQUOTE - Requote",
        10006: "REJECT - Request rejected",
        10007: "CANCEL - Request canceled by trader",
        10008: "PLACED - Order placed",
        10009: "DONE - Request completed",
        10010: "DONE_PARTIAL - Only part of the request was completed",
        10011: "ERROR - Request processing error",
        10012: "TIMEOUT - Request canceled by timeout",
        10013: "INVALID - Invalid request",
        10014: "INVALID_VOLUME - Invalid volume in the request",
        10015: "INVALID_PRICE - Invalid price in the request",
        10016: "INVALID_STOPS - Invalid stops in the request",
        10017: "TRADE_DISABLED - Trade is disabled",
        10018: "MARKET_CLOSED - Market is closed",
        10019: "NO_MONEY - There is not enough money to complete the request",
        10020: "PRICE_CHANGED - Prices changed",
        10021: "PRICE_OFF - There are no quotes to process the request",
        10022: "INVALID_EXPIRATION - Invalid order expiration date in the request",
        10023: "ORDER_CHANGED - Order state changed",
        10024: "TOO_MANY_REQUESTS - Too frequent requests",
        10025: "NO_CHANGES - No changes in request",
        10026: "SERVER_DISABLES_AT - Autotrading disabled by server",
        10027: "CLIENT_DISABLES_AT - Autotrading disabled by client terminal",
        10028: "LOCKED - Request locked for processing",
        10029: "FROZEN - Order or position frozen",
        10030: "INVALID_FILL - Invalid order filling type",
    }
    
    description = retcode_descriptions.get(result.retcode, "Unknown error")
    print(f"   Description: {description}")

print()
print("=" * 70)

# Cleanup
mt5.shutdown()
print("✅ MT5 shutdown")

