"""
Calculate break-even prices and profit at 0.3R for XAUUSD trades
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def calculate_breakeven():
    """Calculate break-even prices and profit at 0.3R"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("BREAK-EVEN & 0.3R PROFIT CALCULATIONS")
    print("=" * 70)
    
    # Get current positions
    positions_result = await bridge.registry.execute("moneybot.getPositions", {})
    positions_data = positions_result.get("data", {})
    positions = positions_data.get("positions", [])
    
    # Filter XAUUSD positions
    xau_positions = [p for p in positions if p.get("symbol", "").startswith("XAUUSD")]
    
    if not xau_positions:
        print("\n⚠️ No XAUUSD positions found")
        return
    
    # Get current price
    try:
        xau_price = await bridge.get_current_price("XAUUSD")
        xau_bid = xau_price.get("data", {}).get("bid", None)
    except:
        xau_bid = None
    
    print(f"\n💰 Current XAUUSD Price: ${xau_bid:.2f}" if xau_bid else "\n💰 Current XAUUSD Price: N/A")
    
    print("\n" + "=" * 70)
    print("BREAK-EVEN CALCULATIONS")
    print("=" * 70)
    
    for i, pos in enumerate(xau_positions, 1):
        ticket = pos.get("ticket", "N/A")
        direction = pos.get("type", "N/A")
        entry = pos.get("price_open", 0)
        sl = pos.get("sl", 0)
        tp = pos.get("tp", 0)
        volume = pos.get("volume", 0)
        profit = pos.get("profit", 0)
        
        if not entry or not sl or not tp:
            print(f"\n{i}. Ticket: {ticket}")
            print(f"   ⚠️ Missing entry/SL/TP data")
            continue
        
        # Calculate R (Risk)
        if direction == 0 or direction == "BUY":
            risk = entry - sl  # Risk in points
            reward = tp - entry  # Reward in points
            direction_str = "BUY"
        else:  # SELL
            risk = sl - entry  # Risk in points
            reward = entry - tp  # Reward in points
            direction_str = "SELL"
        
        # Calculate R:R ratio
        rr_ratio = reward / risk if risk > 0 else 0
        
        # Break-even occurs at 0.3R (30% of the way to TP)
        # For BUY: Break-even price = Entry + (0.3 × Risk)
        # For SELL: Break-even price = Entry - (0.3 × Risk)
        
        if direction_str == "BUY":
            be_price = entry + (0.3 * risk)
            # Profit at 0.3R = 0.3 × Risk (in points) × pip value
            # For XAUUSD, 1 point = $1 per 0.01 lot
            profit_at_03r = 0.3 * risk * volume * 100  # Approximate
        else:  # SELL
            be_price = entry - (0.3 * risk)
            profit_at_03r = 0.3 * risk * volume * 100  # Approximate
        
        # Calculate distance to break-even from current price
        if xau_bid:
            if direction_str == "BUY":
                distance_to_be = be_price - xau_bid
            else:
                distance_to_be = xau_bid - be_price
        else:
            distance_to_be = None
        
        print(f"\n{i}. Ticket: {ticket} ({direction_str})")
        print(f"   Entry: ${entry:.2f}")
        print(f"   SL: ${sl:.2f}")
        print(f"   TP: ${tp:.2f}")
        print(f"   Volume: {volume}")
        print(f"   Current P&L: ${profit:.2f}")
        
        print(f"\n   📊 Risk/Reward Analysis:")
        print(f"   Risk (R): {risk:.2f} points (${risk * volume * 100:.2f})")
        print(f"   Reward: {reward:.2f} points (${reward * volume * 100:.2f})")
        print(f"   R:R Ratio: 1:{rr_ratio:.2f}")
        
        print(f"\n   🎯 Break-Even Trigger (0.3R):")
        print(f"   Break-even Price: ${be_price:.2f}")
        print(f"   Profit at 0.3R: ${profit_at_03r:.2f}")
        
        if xau_bid:
            if distance_to_be is not None:
                if direction_str == "BUY":
                    if distance_to_be <= 0:
                        print(f"   ✅ Break-even ALREADY TRIGGERED!")
                        print(f"      Current price (${xau_bid:.2f}) is above break-even (${be_price:.2f})")
                    else:
                        print(f"   ⏸️ Break-even PENDING")
                        print(f"      Price needs to move ${distance_to_be:.2f} higher")
                        print(f"      From ${xau_bid:.2f} → ${be_price:.2f}")
                else:  # SELL
                    if distance_to_be <= 0:
                        print(f"   ✅ Break-even ALREADY TRIGGERED!")
                        print(f"      Current price (${xau_bid:.2f}) is below break-even (${be_price:.2f})")
                    else:
                        print(f"   ⏸️ Break-even PENDING")
                        print(f"      Price needs to move ${distance_to_be:.2f} lower")
                        print(f"      From ${xau_bid:.2f} → ${be_price:.2f}")
        
        # Show what happens after break-even
        print(f"\n   📈 After Break-Even:")
        print(f"   • SL will move to entry price: ${entry:.2f}")
        print(f"   • Trade protected from loss")
        print(f"   • Trailing stops will activate")
        print(f"   • SL will trail upward (BUY) or downward (SELL) to lock in profit")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    print(f"\n💡 Key Points:")
    print(f"   • Break-even triggers at 0.3R (30% of the way to TP)")
    print(f"   • At 0.3R, profit = 0.3 × Risk")
    print(f"   • After break-even, SL moves to entry (protects from loss)")
    print(f"   • Trailing stops activate after break-even")
    print(f"   • System monitors every 30 seconds and adjusts automatically")

if __name__ == "__main__":
    asyncio.run(calculate_breakeven())
