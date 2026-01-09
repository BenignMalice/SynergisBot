"""
Check optimized plans:
1. Show details of simplified plans created
2. Check which plans are now in price range
"""
import asyncio
import json
from cursor_trading_bridge import get_bridge
from datetime import datetime

async def check_optimized_plans():
    """Check simplified plans and price range status"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("OPTIMIZED PLANS ANALYSIS")
    print("=" * 70)
    
    # Get current prices
    print("\n💰 Current Market Prices:")
    try:
        btc_price = await bridge.get_current_price("BTCUSD")
        xau_price = await bridge.get_current_price("XAUUSD")
        btc_bid = btc_price.get("data", {}).get("bid", None)
        xau_bid = xau_price.get("data", {}).get("bid", None)
        print(f"   BTCUSD: ${btc_bid:,.2f}" if btc_bid else "   BTCUSD: N/A")
        print(f"   XAUUSD: ${xau_bid:.2f}" if xau_bid else "   XAUUSD: N/A")
    except Exception as e:
        print(f"   ⚠️ Could not get prices: {e}")
        btc_bid = None
        xau_bid = None
    
    # Get all plans
    status = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    print(f"\n📊 Total Active Plans: {len(all_plans)}")
    
    # Find simplified plans (those with "Simplified:" in notes)
    simplified_plans = []
    updated_plans = []
    other_plans = []
    
    for plan in all_plans:
        notes = plan.get("notes", "")
        if "Simplified:" in notes:
            simplified_plans.append(plan)
        elif "[Tolerance increased" in notes:
            updated_plans.append(plan)
        else:
            other_plans.append(plan)
    
    # 1. Show simplified plans details
    print("\n" + "=" * 70)
    print("1. SIMPLIFIED PLANS CREATED")
    print("=" * 70)
    print(f"\n📋 Found {len(simplified_plans)} simplified plans:")
    
    for i, plan in enumerate(simplified_plans, 1):
        plan_id = plan.get("plan_id", "N/A")
        symbol = plan.get("symbol", "N/A")
        direction = plan.get("direction", "N/A")
        entry = plan.get("entry_price", 0)
        sl = plan.get("stop_loss", 0)
        tp = plan.get("take_profit", 0)
        conditions = plan.get("conditions", {})
        tolerance = conditions.get("tolerance", 0)
        expires_at = plan.get("expires_at", "")
        
        # Check if expired
        expired = False
        if expires_at:
            try:
                exp_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                now = datetime.now(exp_time.tzinfo)
                expired = now > exp_time
            except:
                pass
        
        # Check price range
        in_range = False
        current_price = None
        distance = 0
        
        if symbol == "BTCUSDc" and btc_bid:
            current_price = btc_bid
            price_near = conditions.get("price_near", entry)
            distance = abs(current_price - price_near)
            in_range = distance <= tolerance
        elif symbol == "XAUUSDc" and xau_bid:
            current_price = xau_bid
            price_near = conditions.get("price_near", entry)
            distance = abs(current_price - price_near)
            in_range = distance <= tolerance
        
        # Extract key conditions
        key_conditions = []
        if conditions.get("choch_bull"):
            key_conditions.append(f"CHOCH Bull ({conditions.get('timeframe', 'N/A')})")
        if conditions.get("choch_bear"):
            key_conditions.append(f"CHOCH Bear ({conditions.get('timeframe', 'N/A')})")
        if conditions.get("bos_bull"):
            key_conditions.append(f"BOS Bull ({conditions.get('timeframe', 'N/A')})")
        if conditions.get("bos_bear"):
            key_conditions.append(f"BOS Bear ({conditions.get('timeframe', 'N/A')})")
        if conditions.get("order_block"):
            key_conditions.append(f"Order Block ({conditions.get('order_block_type', 'auto')})")
        if conditions.get("liquidity_sweep"):
            key_conditions.append(f"Liquidity Sweep ({conditions.get('timeframe', 'N/A')})")
        if conditions.get("confluence_min"):
            key_conditions.append(f"Confluence ≥ {conditions['confluence_min']}")
        if not key_conditions:
            key_conditions.append("Price proximity only")
        
        print(f"\n{i}. Plan ID: {plan_id}")
        print(f"   Symbol: {symbol} | Direction: {direction}")
        print(f"   Entry: ${entry:,.2f}" if symbol == "BTCUSDc" else f"   Entry: ${entry:.2f}")
        print(f"   SL: ${sl:,.2f} | TP: ${tp:,.2f}" if symbol == "BTCUSDc" else f"   SL: ${sl:.2f} | TP: ${tp:.2f}")
        print(f"   Tolerance: ±{tolerance}")
        print(f"   Conditions: {', '.join(key_conditions)}")
        print(f"   Status: {'✅ IN RANGE' if in_range else '⚠️ OUT OF RANGE'}")
        if current_price:
            print(f"   Current: ${current_price:,.2f} | Distance: {distance:.2f}" if symbol == "BTCUSDc" else f"   Current: ${current_price:.2f} | Distance: {distance:.2f}")
        print(f"   Expired: {'❌ YES' if expired else '✅ NO'}")
        print(f"   Notes: {notes[:80]}...")
    
    # 2. Check which plans are in price range
    print("\n" + "=" * 70)
    print("2. PLANS IN PRICE RANGE")
    print("=" * 70)
    
    plans_in_range = []
    plans_out_of_range = []
    plans_expired = []
    
    for plan in all_plans:
        symbol = plan.get("symbol", "")
        conditions = plan.get("conditions", {})
        entry = plan.get("entry_price", 0)
        expires_at = plan.get("expires_at", "")
        
        # Check expiration
        expired = False
        if expires_at:
            try:
                exp_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                now = datetime.now(exp_time.tzinfo)
                expired = now > exp_time
            except:
                pass
        
        if expired:
            plans_expired.append(plan)
            continue
        
        # Check price range
        in_range = False
        current_price = None
        distance = 0
        tolerance = conditions.get("tolerance", 0)
        price_near = conditions.get("price_near", entry)
        
        if symbol == "BTCUSDc" and btc_bid:
            current_price = btc_bid
            distance = abs(current_price - price_near)
            in_range = distance <= tolerance
        elif symbol == "XAUUSDc" and xau_bid:
            current_price = xau_bid
            distance = abs(current_price - price_near)
            in_range = distance <= tolerance
        
        if in_range:
            plans_in_range.append((plan, distance))
        else:
            plans_out_of_range.append((plan, distance))
    
    # Sort by distance
    plans_in_range.sort(key=lambda x: x[1])
    plans_out_of_range.sort(key=lambda x: x[1])
    
    print(f"\n✅ Plans IN Price Range: {len(plans_in_range)}")
    if plans_in_range:
        print("\n   Closest to triggering:")
        for i, (plan, distance) in enumerate(plans_in_range[:10], 1):
            plan_id = plan.get("plan_id", "N/A")
            symbol = plan.get("symbol", "")
            direction = plan.get("direction", "")
            entry = plan.get("entry_price", 0)
            conditions = plan.get("conditions", {})
            tolerance = conditions.get("tolerance", 0)
            
            # Check conditions
            condition_summary = []
            if conditions.get("choch_bull") or conditions.get("choch_bear"):
                condition_summary.append("CHOCH")
            if conditions.get("bos_bull") or conditions.get("bos_bear"):
                condition_summary.append("BOS")
            if conditions.get("liquidity_sweep"):
                condition_summary.append("Liquidity Sweep")
            if conditions.get("order_block"):
                condition_summary.append("Order Block")
            if conditions.get("rejection_wick"):
                condition_summary.append("Rejection Wick")
            if conditions.get("inside_bar"):
                condition_summary.append("Inside Bar")
            if conditions.get("confluence_min"):
                condition_summary.append(f"Confluence≥{conditions['confluence_min']}")
            
            condition_str = ", ".join(condition_summary) if condition_summary else "Price only"
            
            print(f"   {i}. {plan_id[:20]}... | {symbol} {direction}")
            print(f"      Entry: ${entry:,.2f} | Tolerance: ±{tolerance}" if symbol == "BTCUSDc" else f"      Entry: ${entry:.2f} | Tolerance: ±{tolerance}")
            print(f"      Distance: {distance:.2f} | Conditions: {condition_str}")
    
    print(f"\n⚠️ Plans OUT of Price Range: {len(plans_out_of_range)}")
    if plans_out_of_range:
        print("\n   Closest to entry zones:")
        for i, (plan, distance) in enumerate(plans_out_of_range[:5], 1):
            plan_id = plan.get("plan_id", "N/A")
            symbol = plan.get("symbol", "")
            direction = plan.get("direction", "")
            entry = plan.get("entry_price", 0)
            conditions = plan.get("conditions", {})
            tolerance = conditions.get("tolerance", 0)
            
            print(f"   {i}. {plan_id[:20]}... | {symbol} {direction}")
            print(f"      Entry: ${entry:,.2f} | Tolerance: ±{tolerance} | Distance: {distance:.2f}" if symbol == "BTCUSDc" else f"      Entry: ${entry:.2f} | Tolerance: ±{tolerance} | Distance: {distance:.2f}")
    
    print(f"\n❌ Expired Plans: {len(plans_expired)}")
    
    # Summary statistics
    print("\n" + "=" * 70)
    print("SUMMARY STATISTICS")
    print("=" * 70)
    print(f"\n📊 Plan Breakdown:")
    print(f"   Total Plans: {len(all_plans)}")
    print(f"   Simplified Plans: {len(simplified_plans)}")
    print(f"   Updated Plans (tolerance): {len(updated_plans)}")
    print(f"   Original Plans: {len(other_plans)}")
    print(f"\n📍 Price Range Status:")
    print(f"   ✅ In Range: {len(plans_in_range)} plans")
    print(f"   ⚠️ Out of Range: {len(plans_out_of_range)} plans")
    print(f"   ❌ Expired: {len(plans_expired)} plans")
    print(f"\n💡 Plans in range are waiting for structure conditions to form")
    print(f"   They will trigger when all conditions are met simultaneously")

if __name__ == "__main__":
    asyncio.run(check_optimized_plans())
