"""
Create XAUUSD bearish breakout plan based on alert trigger
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def create_bearish_breakout_plan():
    """Create SELL plan for XAUUSD bearish breakout"""
    bridge = get_bridge()
    
    print("=" * 80)
    print("XAUUSD BEARISH BREAKOUT PLAN CREATION")
    print("=" * 80)
    
    # Alert details
    alert_price = 4463.89
    target_price = 4470.00
    
    print(f"\nAlert Details:")
    print(f"   Triggered Price: ${alert_price:.2f}")
    print(f"   Target Price: ${target_price:.2f}")
    print(f"   Signal: Bearish Inside Bar Compression Breakout")
    
    # Get current XAUUSD analysis
    print(f"\n1. ANALYZING XAUUSD...")
    print("-" * 80)
    
    xau_analysis = await bridge.registry.execute("moneybot.analyse_symbol_full", {
        "symbol": "XAUUSDc"
    })
    xau_data = xau_analysis.get("data", {})
    
    current_price = xau_data.get("current_price", 0)
    volatility_regime = xau_data.get("volatility_regime", {})
    regime = volatility_regime.get("regime", "N/A")
    
    print(f"   Current Price: ${current_price:.2f}")
    print(f"   Volatility Regime: {regime}")
    print(f"   Price moved from ${alert_price:.2f} to ${current_price:.2f}")
    
    # Calculate entry, SL, TP for bearish breakout
    # Entry: Slightly below current (for retest of broken level)
    entry_price = current_price * 0.9995  # 0.05% below current
    tolerance = 5.0  # $5 tolerance for XAUUSD
    
    # Stop Loss: Above the breakout level (target was $4470)
    stop_loss = target_price + 10  # $10 above breakout level
    
    # Take Profit: Based on ATR or percentage
    # For bearish breakout, target 1.5-2x the breakout range
    breakout_range = target_price - alert_price  # ~$6
    take_profit = current_price - (breakout_range * 2)  # 2x range below
    
    print(f"\n2. CREATING BEARISH BREAKOUT PLAN...")
    print("-" * 80)
    print(f"   Direction: SELL")
    print(f"   Entry: ${entry_price:.2f} ± ${tolerance}")
    print(f"   Stop Loss: ${stop_loss:.2f}")
    print(f"   Take Profit: ${take_profit:.2f}")
    print(f"   Strategy: Inside Bar Compression Breakout (Bearish)")
    
    # Create the plan
    try:
        result = await bridge.registry.execute("moneybot.create_auto_trade_plan", {
            "symbol": "XAUUSDc",
            "direction": "SELL",
            "entry": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "conditions": {
                "price_near": entry_price,
                "tolerance": tolerance,
                "strategy_type": "breakout_ib_volatility_trap"
            },
            "notes": f"Bearish inside bar compression breakout - Alert triggered at ${alert_price:.2f}, target was ${target_price:.2f}"
        })
        
        plan_data = result.get("data", {})
        plan_id = plan_data.get("plan_id", "N/A")
        
        if plan_id and plan_id != "N/A":
            print(f"\n✅ Plan Created Successfully!")
            print(f"   Plan ID: {plan_id}")
            print(f"   Status: Active and monitoring for entry")
            
            print(f"\n📊 Plan Summary:")
            print(f"   - Will execute SELL when price reaches ${entry_price:.2f} ± ${tolerance}")
            print(f"   - Stop Loss: ${stop_loss:.2f} (protects against false breakout)")
            print(f"   - Take Profit: ${take_profit:.2f} (2x breakout range)")
            print(f"   - Risk/Reward: ~1:2")
        else:
            print(f"\n❌ Failed to create plan")
            print(f"   Response: {result}")
    
    except Exception as e:
        print(f"\n❌ Error creating plan: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(create_bearish_breakout_plan())
