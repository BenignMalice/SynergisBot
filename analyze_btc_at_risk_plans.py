"""
Analyze why BTC plans are at risk
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def analyze_at_risk_plans():
    """Analyze BTC at-risk plans in detail"""
    bridge = get_bridge()
    
    print("=" * 80)
    print("BTC AT-RISK PLANS ANALYSIS")
    print("=" * 80)
    
    # Get current BTC price
    print("\n1. Getting Current BTC Price...")
    btc_analysis = await bridge.registry.execute("moneybot.analyse_symbol_full", {
        "symbol": "BTCUSD"
    })
    btc_data = btc_analysis.get("data", {})
    btc_price = btc_data.get("current_price", 0)
    
    print(f"   Current BTC Price: ${btc_price:,.2f}")
    
    # Get all plans
    print("\n2. Getting BTC Plans...")
    status_result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status_result.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    btc_plans = [p for p in all_plans if p.get("symbol", "").startswith("BTC")]
    
    # At-risk plan IDs from review
    at_risk_plan_ids = [
        "chatgpt_c0c1d595",
        "chatgpt_1a952a76",
        "chatgpt_d7558ecf",
        "chatgpt_8b77a585",
        "chatgpt_61730aed",
        "chatgpt_65b35a1a",
        "chatgpt_141e2aa6",
    ]
    
    print(f"\n3. Analyzing At-Risk Plans:")
    print("-" * 80)
    
    for plan_id in at_risk_plan_ids:
        plan = next((p for p in btc_plans if p.get("plan_id") == plan_id), None)
        if not plan:
            print(f"\n   {plan_id}: NOT FOUND")
            continue
        
        direction = plan.get("direction", "N/A")
        status = plan.get("status", "N/A")
        conditions = plan.get("conditions", {})
        
        price_near = conditions.get("price_near")
        tolerance = conditions.get("tolerance", 0)
        
        if price_near is None:
            print(f"\n   {plan_id}: {direction} ({status}) - No price_near (structure-based)")
            continue
        
        price_diff = abs(btc_price - price_near)
        price_diff_pct = (price_diff / btc_price * 100) if btc_price > 0 else 0
        
        # Calculate status
        if price_diff <= tolerance:
            status_label = "✅ VIABLE (within tolerance)"
        elif price_diff <= tolerance * 2:
            status_label = "⚠️  AT RISK (within 2x tolerance)"
        else:
            status_label = "❌ OBSOLETE (beyond 2x tolerance)"
        
        print(f"\n   {plan_id}: {direction} ({status})")
        print(f"      Target Price: ${price_near:,.2f}")
        print(f"      Tolerance: ±${tolerance:,.2f}")
        print(f"      Current Price: ${btc_price:,.2f}")
        print(f"      Price Difference: ${price_diff:,.2f} ({price_diff_pct:.2f}%)")
        print(f"      Status: {status_label}")
        
        # Explain why it's at risk
        if price_diff > tolerance and price_diff <= tolerance * 2:
            print(f"      ⚠️  REASON: Price is {price_diff - tolerance:.2f} points beyond tolerance")
            print(f"         Price needs to move ${price_diff - tolerance:,.2f} closer to trigger")
            if direction == "BUY" and btc_price > price_near:
                print(f"         → Price needs to DROP ${price_diff - tolerance:,.2f} to enter range")
            elif direction == "BUY" and btc_price < price_near:
                print(f"         → Price needs to RISE ${price_diff - tolerance:,.2f} to enter range")
            elif direction == "SELL" and btc_price > price_near:
                print(f"         → Price needs to RISE ${price_diff - tolerance:,.2f} to enter range")
            elif direction == "SELL" and btc_price < price_near:
                print(f"         → Price needs to DROP ${price_diff - tolerance:,.2f} to enter range")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print(f"\nWhy These Plans Are 'At Risk':")
    print(f"   - Price is within 2x tolerance range but NOT within tolerance range")
    print(f"   - Plans will become 'viable' if price moves closer to target")
    print(f"   - Plans will become 'obsolete' if price moves further away")
    print(f"\n   Current BTC Price: ${btc_price:,.2f}")
    print(f"   Most plans target: $87,000 (BUY) or $88,200 (SELL)")
    print(f"   Price is in the middle, making many plans 'at risk'")

if __name__ == "__main__":
    asyncio.run(analyze_at_risk_plans())
