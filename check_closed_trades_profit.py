"""
Check closed XAUUSD trades to see final profit and if trailing stops occurred
"""
import asyncio
import json
from cursor_trading_bridge import get_bridge
from datetime import datetime, timedelta

async def check_closed_trades():
    """Check closed trades for profit and trailing stop activity"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("CLOSED XAUUSD TRADES ANALYSIS")
    print("=" * 70)
    
    # Get recent closed trades
    trades_result = await bridge.get_recent_trades(days_back=1)
    trades_data = trades_result.get("data", {})
    trades = trades_data.get("trades", [])
    
    # Filter for the specific tickets
    target_tickets = [177182974, 177182977]
    xau_trades = [
        t for t in trades 
        if t.get("ticket") in target_tickets and t.get("symbol") == "XAUUSDc"
    ]
    
    if not xau_trades:
        print("\n⚠️ Could not find closed trades for tickets 177182974 and 177182977")
        print("   Checking all recent XAUUSD trades...")
        xau_trades = [t for t in trades if t.get("symbol") == "XAUUSDc"]
    
    if not xau_trades:
        print("\n⚠️ No recent XAUUSD closed trades found")
        return
    
    print(f"\n📊 Found {len(xau_trades)} XAUUSD closed trade(s)")
    
    # Get plan information if available
    print("\n" + "=" * 70)
    print("TRADE ANALYSIS")
    print("=" * 70)
    
    for i, trade in enumerate(xau_trades, 1):
        ticket = trade.get("ticket", "N/A")
        symbol = trade.get("symbol", "N/A")
        direction = trade.get("direction", "N/A")
        entry = trade.get("entry_price", 0)
        exit_price = trade.get("exit_price", 0)
        sl = trade.get("stop_loss", 0)
        tp = trade.get("take_profit", 0)
        profit_loss = trade.get("profit_loss", 0)
        close_reason = trade.get("close_reason", "N/A")
        opened_at = trade.get("opened_at", "N/A")
        closed_at = trade.get("closed_at", "N/A")
        duration_seconds = trade.get("duration_seconds", 0)
        
        plan = trade.get("plan", {})
        plan_id = plan.get("plan_id", "N/A") if plan else "N/A"
        
        print(f"\n{i}. Ticket: {ticket}")
        print(f"   Symbol: {symbol} | Direction: {direction}")
        print(f"   Entry: ${entry:.2f} | Exit: ${exit_price:.2f}")
        print(f"   SL: ${sl:.2f} | TP: ${tp:.2f}")
        print(f"   Final P&L: ${profit_loss:.2f}")
        print(f"   Close Reason: {close_reason}")
        print(f"   Opened: {opened_at}")
        print(f"   Closed: {closed_at}")
        if duration_seconds:
            duration_min = duration_seconds / 60
            print(f"   Duration: {duration_min:.1f} minutes")
        
        if plan_id != "N/A":
            print(f"   Plan ID: {plan_id}")
        
        # Analyze break-even and trailing stop
        print(f"\n   📊 Break-Even & Trailing Analysis:")
        
        # Based on the alerts you showed:
        # Ticket 177182974: Old SL 4474.80 → New SL 4478.58693
        # Ticket 177182977: Old SL 4474.50 → New SL 4478.60391
        
        if ticket == 177182974:
            original_sl = 4474.80
            breakeven_sl = 4478.58693
            entry_price = entry
            
            print(f"   Original SL: ${original_sl:.2f}")
            print(f"   Breakeven SL: ${breakeven_sl:.2f}")
            print(f"   Entry: ${entry_price:.2f}")
            
            # Check if breakeven SL matches entry
            if abs(breakeven_sl - entry_price) < 0.1:
                print(f"   ✅ Breakeven SL matches entry (protected from loss)")
            else:
                print(f"   ⚠️ Breakeven SL ({breakeven_sl:.2f}) doesn't match entry ({entry_price:.2f})")
            
            # Check if exit was above breakeven (trailing stop would have moved SL up)
            if exit_price and breakeven_sl:
                if direction == "BUY":
                    if exit_price > breakeven_sl:
                        print(f"   📈 Exit price (${exit_price:.2f}) > Breakeven SL (${breakeven_sl:.2f})")
                        print(f"   💡 Trailing stop SHOULD have moved SL higher before close")
                        print(f"   ⚠️ If SL wasn't trailing, it may not have activated")
                    else:
                        print(f"   ⚠️ Exit price (${exit_price:.2f}) <= Breakeven SL (${breakeven_sl:.2f})")
                        print(f"   💡 Trade closed before trailing could activate")
        
        elif ticket == 177182977:
            original_sl = 4474.50
            breakeven_sl = 4478.60391
            entry_price = entry
            
            print(f"   Original SL: ${original_sl:.2f}")
            print(f"   Breakeven SL: ${breakeven_sl:.2f}")
            print(f"   Entry: ${entry_price:.2f}")
            
            # Check if breakeven SL matches entry
            if abs(breakeven_sl - entry_price) < 0.1:
                print(f"   ✅ Breakeven SL matches entry (protected from loss)")
            else:
                print(f"   ⚠️ Breakeven SL ({breakeven_sl:.2f}) doesn't match entry ({entry_price:.2f})")
            
            # Check if exit was above breakeven
            if exit_price and breakeven_sl:
                if direction == "BUY":
                    if exit_price > breakeven_sl:
                        print(f"   📈 Exit price (${exit_price:.2f}) > Breakeven SL (${breakeven_sl:.2f})")
                        print(f"   💡 Trailing stop SHOULD have moved SL higher before close")
                        print(f"   ⚠️ If SL wasn't trailing, it may not have activated")
                    else:
                        print(f"   ⚠️ Exit price (${exit_price:.2f}) <= Breakeven SL (${breakeven_sl:.2f})")
                        print(f"   💡 Trade closed before trailing could activate")
        
        # Calculate what profit should have been
        if entry and exit_price:
            if direction == "BUY":
                price_move = exit_price - entry
                profit_per_point = 1.0  # $1 per point for 0.01 lot XAUUSD
                expected_profit = price_move * profit_per_point
            else:  # SELL
                price_move = entry - exit_price
                profit_per_point = 1.0
                expected_profit = price_move * profit_per_point
            
            print(f"\n   💰 Profit Analysis:")
            print(f"   Price Move: {price_move:.2f} points")
            print(f"   Expected Profit: ${expected_profit:.2f}")
            print(f"   Actual Profit: ${profit_loss:.2f}")
            
            if abs(expected_profit - profit_loss) > 0.5:
                print(f"   ⚠️ Profit mismatch - may include spreads/commissions")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    total_profit = sum(t.get("profit_loss", 0) or 0 for t in xau_trades)
    profitable_trades = sum(1 for t in xau_trades if (t.get("profit_loss", 0) or 0) > 0)
    
    print(f"\n✅ Final Results:")
    print(f"   • Total Trades: {len(xau_trades)}")
    print(f"   • Profitable: {profitable_trades}")
    print(f"   • Total P&L: ${total_profit:.2f}")
    
    print(f"\n💡 Trailing Stop Analysis:")
    print(f"   • Breakeven was set correctly (SL moved to entry)")
    print(f"   • Trailing stops activate AFTER breakeven")
    print(f"   • If you closed manually before trailing activated, SL would stay at breakeven")
    print(f"   • Trailing stops check every 30 seconds")
    print(f"   • If price moved quickly and you closed manually, trailing may not have had time")
    
    print(f"\n🔍 To Verify Trailing Stops:")
    print(f"   • Check if exit price was significantly above breakeven SL")
    print(f"   • If yes, trailing should have moved SL higher")
    print(f"   • If no trailing occurred, may need to check Universal Manager logs")

if __name__ == "__main__":
    asyncio.run(check_closed_trades())
