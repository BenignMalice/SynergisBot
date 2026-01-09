"""
Diagnose why MT5 is returning stale M5 candles for BTCUSDc
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure stdout encoding for Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

print("=" * 80)
print("MT5 STALE CANDLES DIAGNOSIS - BTCUSDc M5")
print("=" * 80)
print()

symbol = "BTCUSDc"
timeframe = "M5"

try:
    import MetaTrader5 as mt5
    from datetime import datetime, timezone
    
    if not mt5.initialize():
        print("❌ MT5 not initialized")
        exit(1)
    
    print("1. Checking MT5 Connection...")
    account_info = mt5.account_info()
    if account_info:
        print(f"   ✅ MT5 Connected (Account: {account_info.login})")
        print(f"   📊 Server: {account_info.server}")
        print(f"   📊 Balance: {account_info.balance}")
    else:
        print("   ❌ No account info")
    
    print()
    
    print("2. Checking Symbol Info...")
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info:
        print(f"   ✅ Symbol found: {symbol}")
        print(f"   📊 Visible: {symbol_info.visible}")
        print(f"   📊 Select: {symbol_info.select}")
        print(f"   📊 Trade mode: {symbol_info.trade_mode}")
        print(f"   📊 Trade allowed: {symbol_info.trade_mode == 4}")  # SYMBOL_TRADE_MODE_FULL
        
        # Check if symbol is selected
        if not symbol_info.visible:
            print(f"   ⚠️  Symbol not visible - selecting...")
            if mt5.symbol_select(symbol, True):
                print(f"   ✅ Symbol selected")
            else:
                print(f"   ❌ Failed to select symbol")
    else:
        print(f"   ❌ Symbol not found: {symbol}")
        exit(1)
    
    print()
    
    print("3. Checking Tick Data...")
    tick = mt5.symbol_info_tick(symbol)
    if tick:
        tick_time = datetime.fromtimestamp(tick.time, tz=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        tick_age = (now_utc - tick_time).total_seconds() / 60
        
        print(f"   ✅ Tick data available")
        print(f"   📊 Bid: {tick.bid}")
        print(f"   📊 Ask: {tick.ask}")
        print(f"   📊 Tick time: {tick_time}")
        print(f"   📊 Current time: {now_utc}")
        print(f"   📊 Tick age: {tick_age:.2f} minutes")
        
        if tick_age < 1:
            print(f"   ✅ Tick data is FRESH")
        else:
            print(f"   ⚠️  Tick data is STALE ({tick_age:.2f} min old)")
    else:
        print(f"   ❌ No tick data available")
    
    print()
    
    print("4. Checking M5 Candles (copy_rates_from_pos)...")
    tf_enum = mt5.TIMEFRAME_M5
    
    # Strategy 1: copy_rates_from_pos(position=0)
    rates_1 = mt5.copy_rates_from_pos(symbol, tf_enum, 0, 10)
    if rates_1 is not None and len(rates_1) > 0:
        latest_candle = rates_1[-1]
        candle_time = datetime.fromtimestamp(latest_candle['time'], tz=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        candle_age = (now_utc - candle_time).total_seconds() / 60
        
        print(f"   📊 Latest candle (position 0):")
        print(f"      Time: {candle_time}")
        print(f"      Open: {latest_candle['open']}")
        print(f"      High: {latest_candle['high']}")
        print(f"      Low: {latest_candle['low']}")
        print(f"      Close: {latest_candle['close']}")
        print(f"      Age: {candle_age:.2f} minutes")
        
        if candle_age > 10:
            print(f"      ❌ STALE (>{candle_age:.1f} min old)")
        else:
            print(f"      ✅ FRESH")
    else:
        print(f"   ❌ No candles returned from copy_rates_from_pos(position=0)")
    
    print()
    
    print("5. Checking M5 Candles (copy_rates_from_pos position=1)...")
    # Strategy 2: Skip position 0 (in case it's cached)
    rates_2 = mt5.copy_rates_from_pos(symbol, tf_enum, 1, 10)
    if rates_2 is not None and len(rates_2) > 0:
        latest_candle = rates_2[-1]
        candle_time = datetime.fromtimestamp(latest_candle['time'], tz=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        candle_age = (now_utc - candle_time).total_seconds() / 60
        
        print(f"   📊 Latest candle (position 1):")
        print(f"      Time: {candle_time}")
        print(f"      Age: {candle_age:.2f} minutes")
        
        if candle_age > 10:
            print(f"      ❌ STALE (>{candle_age:.1f} min old)")
        else:
            print(f"      ✅ FRESH")
    else:
        print(f"   ❌ No candles returned from copy_rates_from_pos(position=1)")
    
    print()
    
    print("6. Checking M5 Candles (copy_rates_from with recent timestamp)...")
    # Strategy 3: Use copy_rates_from with recent timestamp
    from_timestamp = int((datetime.now(timezone.utc).timestamp() - 3600))  # 1 hour ago
    rates_3 = mt5.copy_rates_from(symbol, tf_enum, from_timestamp, 20)
    if rates_3 is not None and len(rates_3) > 0:
        latest_candle = rates_3[-1]
        candle_time = datetime.fromtimestamp(latest_candle['time'], tz=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        candle_age = (now_utc - candle_time).total_seconds() / 60
        
        print(f"   📊 Latest candle (from timestamp):")
        print(f"      Time: {candle_time}")
        print(f"      Age: {candle_age:.2f} minutes")
        
        if candle_age > 10:
            print(f"      ❌ STALE (>{candle_age:.1f} min old)")
        else:
            print(f"      ✅ FRESH")
    else:
        print(f"   ❌ No candles returned from copy_rates_from")
    
    print()
    
    print("7. Checking All Recent M5 Candles...")
    # Get last 20 candles to see the pattern
    all_rates = mt5.copy_rates_from_pos(symbol, tf_enum, 0, 20)
    if all_rates is not None and len(all_rates) > 0:
        print(f"   📊 Last 5 candles:")
        for i, candle in enumerate(all_rates[-5:]):
            candle_time = datetime.fromtimestamp(candle['time'], tz=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            candle_age = (now_utc - candle_time).total_seconds() / 60
            print(f"      {i+1}. {candle_time} (age: {candle_age:.1f} min)")
        
        # Check if there's a gap
        if len(all_rates) >= 2:
            latest_time = datetime.fromtimestamp(all_rates[-1]['time'], tz=timezone.utc)
            prev_time = datetime.fromtimestamp(all_rates[-2]['time'], tz=timezone.utc)
            gap = (latest_time - prev_time).total_seconds() / 60
            print(f"\n   📊 Gap between last 2 candles: {gap:.1f} minutes (expected: 5.0)")
            
            if gap > 10:
                print(f"   ⚠️  Large gap detected - candles may have stopped forming")
    else:
        print(f"   ❌ No candles available")
    
    print()
    
    print("8. Checking MT5 Server Time...")
    server_time = mt5.symbol_info_tick(symbol)
    if server_time:
        server_dt = datetime.fromtimestamp(server_time.time, tz=timezone.utc)
        local_dt = datetime.now(timezone.utc)
        diff = (local_dt - server_dt).total_seconds()
        print(f"   📊 Server time (from tick): {server_dt}")
        print(f"   📊 Local time: {local_dt}")
        print(f"   📊 Difference: {diff:.1f} seconds")
        
        if abs(diff) > 60:
            print(f"   ⚠️  Time difference > 60 seconds - may cause issues")
    
    print()
    
    print("=" * 80)
    print("DIAGNOSIS")
    print("=" * 80)
    print()
    print("💡 Possible Causes:")
    print()
    print("1. Broker Connection Issue:")
    print("   • Broker may have stopped sending candle data")
    print("   • Check broker connection status in MT5")
    print()
    print("2. Symbol Subscription Issue:")
    print("   • Symbol may not be properly subscribed")
    print("   • Try: Right-click symbol in Market Watch → Refresh")
    print()
    print("3. Market Closed/Low Volume:")
    print("   • Market may be closed or very low volume")
    print("   • BTC trades 24/7, so this is unlikely")
    print()
    print("4. MT5 Candle Formation Delay:")
    print("   • MT5 may be delayed in forming new candles")
    print("   • Try restarting MT5 or refreshing symbol")
    print()
    print("5. Broker-Side Issue:")
    print("   • Broker may have an issue with candle data")
    print("   • Contact broker support if persistent")
    print()
    print("🔧 Recommended Actions:")
    print()
    print("1. In MT5 Terminal:")
    print("   • Right-click BTCUSDc in Market Watch")
    print("   • Select 'Refresh' or 'Chart'")
    print("   • Check if new candles appear")
    print()
    print("2. Check Broker Connection:")
    print("   • Verify MT5 is connected to broker")
    print("   • Check for any connection warnings")
    print()
    print("3. Restart MT5:")
    print("   • Close and restart MT5 terminal")
    print("   • This may refresh symbol subscriptions")
    print()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

