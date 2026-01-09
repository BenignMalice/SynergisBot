"""
Create optimized XAUUSD plans with tighter stop losses based on analysis
"""
import asyncio
import json
from cursor_trading_bridge import get_bridge

async def create_optimized_plans():
    """Create optimized XAUUSD plans"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("CREATING OPTIMIZED XAUUSD PLANS")
    print("=" * 70)
    
    # Get current price
    try:
        xau_price = await bridge.get_current_price("XAUUSD")
        xau_bid = xau_price.get("data", {}).get("bid", None)
        print(f"\n💰 Current XAUUSD Price: ${xau_bid:.2f}" if xau_bid else "\n💰 Current XAUUSD Price: N/A")
    except:
        xau_bid = 4484.0  # Fallback
        print(f"\n💰 Using fallback price: ${xau_bid:.2f}")
    
    # Analysis findings:
    # - Average SL distance: 6.36 points (too wide)
    # - Optimal SL: 3-4 points
    # - BUY trades have 2.7x more losses
    # - SELL trades perform better
    # - Price-only plans need minimal confluence
    # - Structure-based plans need tighter SL
    
    print("\n📊 Optimization Strategy:")
    print("   • Tighten SL to 3-4 points (from 6.36 avg)")
    print("   • Focus more on SELL opportunities (better win rate)")
    print("   • Add minimal confluence to price-only plans")
    print("   • Use tighter tolerance for better entry timing")
    
    # Create optimized plans
    optimized_plans = []
    
    # Strategy 1: SELL plans with tight SL (3-4 points)
    # SELL performed better, so create more SELL opportunities
    sell_levels = [
        xau_bid + 2.0,   # Just above current
        xau_bid + 5.0,   # Short-term resistance
        xau_bid + 8.0,   # Medium-term resistance
        xau_bid + 12.0,  # Extended resistance
    ]
    
    for i, level in enumerate(sell_levels, 1):
        # Tight SL: 3.5 points
        sl_distance = 3.5
        tp_distance = 6.0  # R:R of 1:1.71
        
        optimized_plans.append({
            "plan_type": "auto_trade",
            "symbol": "XAUUSDc",
            "direction": "SELL",
            "entry": level,
            "stop_loss": level + sl_distance,
            "take_profit": level - tp_distance,
            "volume": 0.01,
            "conditions": {
                "price_near": level,
                "tolerance": 1.5,  # Tighter tolerance for better entry
                "confluence_min": 55,  # Minimal confluence requirement
            },
            "expires_hours": 12,
            "notes": f"OPTIMIZED: SELL Level {i} - Tight SL (3.5pt) - Based on analysis"
        })
    
    # Strategy 2: BUY plans with tight SL and better confluence
    # BUY had more losses, so be more selective
    buy_levels = [
        xau_bid - 2.0,   # Just below current
        xau_bid - 5.0,   # Short-term support
        xau_bid - 8.0,   # Medium-term support
    ]
    
    for i, level in enumerate(buy_levels, 1):
        # Tight SL: 3.5 points
        sl_distance = 3.5
        tp_distance = 6.0  # R:R of 1:1.71
        
        optimized_plans.append({
            "plan_type": "auto_trade",
            "symbol": "XAUUSDc",
            "direction": "BUY",
            "entry": level,
            "stop_loss": level - sl_distance,
            "take_profit": level + tp_distance,
            "volume": 0.01,
            "conditions": {
                "price_near": level,
                "tolerance": 1.5,  # Tighter tolerance
                "confluence_min": 60,  # Higher confluence for BUY (more selective)
            },
            "expires_hours": 12,
            "notes": f"OPTIMIZED: BUY Level {i} - Tight SL (3.5pt) - Higher confluence"
        })
    
    # Strategy 3: Structure-based plans with tight SL
    # Structure-based had higher win rate but larger losses
    # Solution: Keep structure but tighten SL
    
    optimized_plans.append({
        "plan_type": "auto_trade",
        "symbol": "XAUUSDc",
        "direction": "SELL",
        "entry": xau_bid + 6.0,
        "stop_loss": xau_bid + 9.5,  # 3.5 point SL
        "take_profit": xau_bid,  # 6 point TP
        "volume": 0.01,
        "conditions": {
            "price_near": xau_bid + 6.0,
            "tolerance": 2.0,
            "confluence_min": 60,
            "rejection_wick": True,  # Structure confirmation
            "timeframe": "M15"
        },
        "expires_hours": 12,
        "notes": "OPTIMIZED: SELL Structure-Based - Tight SL (3.5pt) - Rejection wick"
    })
    
    optimized_plans.append({
        "plan_type": "auto_trade",
        "symbol": "XAUUSDc",
        "direction": "BUY",
        "entry": xau_bid - 6.0,
        "stop_loss": xau_bid - 9.5,  # 3.5 point SL
        "take_profit": xau_bid,  # 6 point TP
        "volume": 0.01,
        "conditions": {
            "price_near": xau_bid - 6.0,
            "tolerance": 2.0,
            "confluence_min": 65,  # Higher for BUY
            "rejection_wick": True,  # Structure confirmation
            "timeframe": "M15"
        },
        "expires_hours": 12,
        "notes": "OPTIMIZED: BUY Structure-Based - Tight SL (3.5pt) - Rejection wick"
    })
    
    # Strategy 4: Order block plans with tight SL
    optimized_plans.append({
        "plan_type": "order_block",
        "symbol": "XAUUSDc",
        "direction": "SELL",
        "entry": xau_bid + 4.0,
        "stop_loss": xau_bid + 7.5,  # 3.5 point SL
        "take_profit": xau_bid - 2.0,  # 6 point TP
        "volume": 0.01,
        "order_block_type": "bear",
        "min_validation_score": 60,
        "expires_hours": 12,
        "notes": "OPTIMIZED: SELL Order Block - Tight SL (3.5pt)"
    })
    
    optimized_plans.append({
        "plan_type": "order_block",
        "symbol": "XAUUSDc",
        "direction": "BUY",
        "entry": xau_bid - 4.0,
        "stop_loss": xau_bid - 7.5,  # 3.5 point SL
        "take_profit": xau_bid + 2.0,  # 6 point TP
        "volume": 0.01,
        "order_block_type": "bull",
        "min_validation_score": 65,  # Higher for BUY
        "expires_hours": 12,
        "notes": "OPTIMIZED: BUY Order Block - Tight SL (3.5pt)"
    })
    
    print(f"\n📋 Created {len(optimized_plans)} optimized plans")
    print(f"   • {sum(1 for p in optimized_plans if p['direction'] == 'SELL')} SELL plans")
    print(f"   • {sum(1 for p in optimized_plans if p['direction'] == 'BUY')} BUY plans")
    print(f"   • All with 3.5 point stop losses")
    print(f"   • Tighter tolerance (1.5-2.0 points)")
    print(f"   • Minimal confluence requirements")
    
    # Create plans
    print(f"\n🚀 Creating optimized plans...")
    result = await bridge.registry.execute(
        "moneybot.create_multiple_auto_plans",
        {"plans": optimized_plans}
    )
    
    result_data = result.get("data", {})
    successful = result_data.get("successful", 0)
    failed = result_data.get("failed", 0)
    
    print(f"\n✅ Results:")
    print(f"   Created: {successful}")
    print(f"   Failed: {failed}")
    
    if result_data.get("results"):
        print(f"\n📋 Plan IDs Created:")
        for i, res in enumerate(result_data["results"], 1):
            if res.get("status") == "created":
                plan_id = res.get("plan_id", "N/A")
                direction = optimized_plans[i-1].get("direction", "N/A")
                entry = optimized_plans[i-1].get("entry", 0)
                notes = optimized_plans[i-1].get("notes", "")
                print(f"   {i}. {plan_id[:20]}... | {direction} @ ${entry:.2f}")
                print(f"      {notes}")
    
    # Summary
    print("\n" + "=" * 70)
    print("OPTIMIZATION SUMMARY")
    print("=" * 70)
    
    print(f"\n✅ Key Optimizations Applied:")
    print(f"   1. Stop Loss: Reduced from 6.36 avg to 3.5 points (45% reduction)")
    print(f"   2. Tolerance: Tightened to 1.5-2.0 points (better entry timing)")
    print(f"   3. Confluence: Added minimal requirements (55-65%)")
    print(f"   4. Direction Bias: More SELL plans (better win rate)")
    print(f"   5. BUY Selectivity: Higher confluence for BUY (60-65%)")
    print(f"   6. Structure: Added structure confirmation where appropriate")
    
    print(f"\n📊 Expected Improvements:")
    print(f"   • Reduced average loss (from $5.64 to ~$3.50)")
    print(f"   • Better entry timing (tighter tolerance)")
    print(f"   • Higher quality entries (confluence requirements)")
    print(f"   • More SELL opportunities (better win rate)")
    
    print(f"\n💡 Next Steps:")
    print(f"   1. Monitor these optimized plans")
    print(f"   2. Compare performance vs previous plans")
    print(f"   3. Adjust further based on results")
    print(f"   4. Consider canceling old plans with wide SL")

if __name__ == "__main__":
    asyncio.run(create_optimized_plans())
