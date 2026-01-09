"""
Analyze which plans are more likely to trigger based on their conditions
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def analyze_trigger_probability():
    """Analyze trigger probability for latest plans"""
    bridge = get_bridge()
    
    print("=" * 80)
    print("PLAN TRIGGER PROBABILITY ANALYSIS")
    print("=" * 80)
    
    # Latest plan IDs
    plan_ids = [
        "chatgpt_92a3aa65",  # order_block BUY (structure-based)
        "chatgpt_ae2c5ce7",  # order_block SELL (structure-based)
        "chatgpt_45b1c505",  # auto_trade BUY (price-only)
        "chatgpt_095a448e",  # auto_trade SELL (price-only)
        "chatgpt_bd18a876",  # XAUUSD bearish breakout (price-only)
    ]
    
    # Get current prices
    print("\n1. Getting Current Market Prices...")
    print("-" * 80)
    
    btc_analysis = await bridge.registry.execute("moneybot.analyse_symbol_full", {
        "symbol": "BTCUSD"
    })
    btc_price = btc_analysis.get("data", {}).get("current_price", 0)
    
    xau_analysis = await bridge.registry.execute("moneybot.analyse_symbol_full", {
        "symbol": "XAUUSDc"
    })
    xau_price = xau_analysis.get("data", {}).get("current_price", 0)
    
    print(f"   BTCUSD: ${btc_price:,.2f}")
    print(f"   XAUUSD: ${xau_price:,.2f}")
    
    # Get plan details
    print("\n2. Analyzing Plan Conditions...")
    print("-" * 80)
    
    status_result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status_result.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    plans_analysis = []
    
    for plan_id in plan_ids:
        plan = next((p for p in all_plans if p.get("plan_id") == plan_id), None)
        if not plan:
            continue
        
        symbol = plan.get("symbol", "N/A")
        direction = plan.get("direction", "N/A")
        conditions = plan.get("conditions", {})
        
        price_near = conditions.get("price_near", 0)
        tolerance = conditions.get("tolerance", 0)
        
        # Determine current price
        current_price = btc_price if "BTC" in symbol else xau_price
        
        # Calculate distance from target
        price_diff = abs(current_price - price_near)
        price_diff_pct = (price_diff / current_price * 100) if current_price > 0 else 0
        
        # Count conditions
        condition_count = 0
        condition_types = []
        
        # Price condition (always present)
        if price_near:
            condition_count += 1
            condition_types.append("Price")
        
        # Structure conditions
        structure_conditions = [
            "order_block", "choch_bull", "choch_bear", "bos_bull", "bos_bear",
            "rejection_wick", "liquidity_sweep", "breaker_block", "fvg_bull", "fvg_bear"
        ]
        has_structure = any(conditions.get(key) for key in structure_conditions)
        if has_structure:
            condition_count += 1
            condition_types.append("Structure")
        
        # Confluence
        if conditions.get("min_confluence") or conditions.get("range_scalp_confluence"):
            condition_count += 1
            condition_types.append("Confluence")
        
        # Volatility
        volatility_conditions = ["bb_squeeze", "bb_expansion", "min_volatility", "max_volatility"]
        has_volatility = any(conditions.get(key) for key in volatility_conditions)
        if has_volatility:
            condition_count += 1
            condition_types.append("Volatility")
        
        # Volume
        volume_conditions = ["volume_confirmation", "volume_spike", "volume_ratio"]
        has_volume = any(conditions.get(key) for key in volume_conditions)
        if has_volume:
            condition_count += 1
            condition_types.append("Volume")
        
        # Time
        if conditions.get("time_after") or conditions.get("time_before"):
            condition_count += 1
            condition_types.append("Time")
        
        # Pattern
        pattern_conditions = ["inside_bar", "equal_highs", "equal_lows"]
        has_pattern = any(conditions.get(key) for key in pattern_conditions)
        if has_pattern:
            condition_count += 1
            condition_types.append("Pattern")
        
        # Determine trigger probability
        if price_diff <= tolerance:
            price_status = "✅ WITHIN RANGE"
            price_probability = 1.0
        elif price_diff <= tolerance * 2:
            price_status = "⚠️  NEAR RANGE"
            price_probability = 0.5
        else:
            price_status = "❌ FAR FROM RANGE"
            price_probability = 0.1
        
        # Overall probability (price probability * condition complexity factor)
        # More conditions = lower probability (all must pass)
        condition_factor = 1.0 / (condition_count ** 0.7)  # Diminishing returns
        
        overall_probability = price_probability * condition_factor
        
        plans_analysis.append({
            "plan_id": plan_id,
            "symbol": symbol,
            "direction": direction,
            "price_near": price_near,
            "tolerance": tolerance,
            "current_price": current_price,
            "price_diff": price_diff,
            "price_diff_pct": price_diff_pct,
            "price_status": price_status,
            "condition_count": condition_count,
            "condition_types": condition_types,
            "has_structure": has_structure,
            "overall_probability": overall_probability
        })
    
    # Sort by probability
    plans_analysis.sort(key=lambda x: x["overall_probability"], reverse=True)
    
    # Display analysis
    print("\n3. TRIGGER PROBABILITY RANKING:")
    print("-" * 80)
    
    for i, plan in enumerate(plans_analysis, 1):
        print(f"\n   #{i} - {plan['plan_id']}")
        print(f"   Symbol: {plan['symbol']} | Direction: {plan['direction']}")
        print(f"   Target: ${plan['price_near']:,.2f} ± ${plan['tolerance']}")
        print(f"   Current: ${plan['current_price']:,.2f}")
        print(f"   Distance: ${plan['price_diff']:,.2f} ({plan['price_diff_pct']:.2f}%)")
        print(f"   Price Status: {plan['price_status']}")
        print(f"   Conditions: {plan['condition_count']} ({', '.join(plan['condition_types'])})")
        print(f"   Structure Required: {'Yes' if plan['has_structure'] else 'No'}")
        print(f"   Trigger Probability: {plan['overall_probability']*100:.1f}%")
        
        # Add recommendation
        if plan['overall_probability'] > 0.7:
            print(f"   💡 HIGH PROBABILITY - Likely to trigger soon")
        elif plan['overall_probability'] > 0.4:
            print(f"   💡 MEDIUM PROBABILITY - May trigger if conditions align")
        else:
            print(f"   💡 LOW PROBABILITY - Multiple conditions must align")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY & INSIGHTS")
    print("=" * 80)
    
    price_only = [p for p in plans_analysis if not p['has_structure']]
    structure_based = [p for p in plans_analysis if p['has_structure']]
    
    avg_price_only_prob = sum(p['overall_probability'] for p in price_only) / len(price_only) if price_only else 0
    avg_structure_prob = sum(p['overall_probability'] for p in structure_based) / len(structure_based) if structure_based else 0
    
    print(f"\nPrice-Only Plans ({len(price_only)}):")
    print(f"   Average Trigger Probability: {avg_price_only_prob*100:.1f}%")
    print(f"   ✅ More likely to trigger (fewer conditions)")
    print(f"   ⚠️  Less selective (may trigger in suboptimal conditions)")
    
    print(f"\nStructure-Based Plans ({len(structure_based)}):")
    print(f"   Average Trigger Probability: {avg_structure_prob*100:.1f}%")
    print(f"   ⚠️  Less likely to trigger (more conditions)")
    print(f"   ✅ More selective (only triggers with structure confirmation)")
    
    print(f"\n🎯 KEY INSIGHT:")
    if avg_price_only_prob > avg_structure_prob:
        print(f"   Price-only plans are {((avg_price_only_prob / avg_structure_prob) - 1) * 100:.0f}% more likely to trigger")
        print(f"   BUT structure-based plans have better quality filters")
    else:
        print(f"   Structure-based plans are more selective but may have better win rates")
    
    print(f"\n💡 RECOMMENDATION:")
    print(f"   - Use price-only plans for: Quick scalps, range trading, high-probability setups")
    print(f"   - Use structure-based plans for: Higher quality entries, trend following, swing trades")

if __name__ == "__main__":
    asyncio.run(analyze_trigger_probability())
