"""
Review specific plans to check if their conditions will be monitored
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def review_plans():
    """Review specific plans"""
    bridge = get_bridge()
    
    plan_ids = ["chatgpt_c33acacb", "chatgpt_4c23728f"]
    
    print("=" * 80)
    print("REVIEWING PLAN CONDITIONS")
    print("=" * 80)
    print()
    
    # Get all plans
    try:
        result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
        data = result.get("data", {})
        system_status = data.get("system_status", {})
        all_plans = system_status.get("plans", [])
        
        # Find the specific plans
        plans_to_review = [p for p in all_plans if p.get("plan_id") in plan_ids]
        
        if not plans_to_review:
            print(f"Plans not found: {plan_ids}")
            return
        
        # Recognized condition names
        recognized_order_flow = {
            "delta_positive": "Check if delta volume > 0",
            "delta_negative": "Check if delta volume < 0",
            "cvd_rising": "Check if CVD trend is rising",
            "cvd_falling": "Check if CVD trend is falling",
            "avoid_absorption_zones": "Block if entry price in absorption zone"
        }
        
        for plan in plans_to_review:
            plan_id = plan.get("plan_id")
            symbol = plan.get("symbol")
            direction = plan.get("direction")
            conditions = plan.get("conditions", {})
            
            print(f"Plan: {plan_id}")
            print(f"Symbol: {symbol}, Direction: {direction}")
            print()
            print("Conditions in plan:")
            for key, value in conditions.items():
                print(f"  - {key}: {value}")
            print()
            
            # Check for unrecognized condition names
            unrecognized = []
            recognized = []
            
            for key, value in conditions.items():
                key_lower = key.lower()
                
                # Check if it's an order flow condition
                if any(term in key_lower for term in ["cvd", "delta", "absorption", "divergence"]):
                    if key in recognized_order_flow:
                        recognized.append(f"{key}: {recognized_order_flow[key]}")
                    else:
                        # Check for variations
                        if "cvd" in key_lower and "div" in key_lower:
                            if "bear" in key_lower:
                                unrecognized.append(f"{key} → Should be 'cvd_falling' or CVD divergence check")
                            elif "bull" in key_lower:
                                unrecognized.append(f"{key} → Should be 'cvd_rising' or CVD divergence check")
                        elif "delta" in key_lower and "div" in key_lower:
                            if "bull" in key_lower:
                                unrecognized.append(f"{key} → Should be 'delta_positive' or delta divergence check")
                            elif "bear" in key_lower:
                                unrecognized.append(f"{key} → Should be 'delta_negative' or delta divergence check")
                        elif "absorption" in key_lower:
                            if "detected" in key_lower or "zone" in key_lower:
                                unrecognized.append(f"{key} → Should be 'avoid_absorption_zones: true'")
            
            if recognized:
                print("✅ Recognized conditions (WILL be monitored):")
                for cond in recognized:
                    print(f"   {cond}")
                print()
            
            if unrecognized:
                print("❌ Unrecognized conditions (WILL NOT be monitored):")
                for cond in unrecognized:
                    print(f"   {cond}")
                print()
                print("⚠️ ISSUE: These conditions use incorrect names and will be IGNORED by the system!")
                print("   The system only recognizes:")
                for name, desc in recognized_order_flow.items():
                    print(f"     - {name}: {desc}")
                print()
            
            # Check if plan will execute
            has_price_condition = any([
                "price_near" in conditions,
                "price_above" in conditions,
                "price_below" in conditions
            ])
            
            if has_price_condition:
                print("✅ Price condition present - plan can execute when price is near entry")
            else:
                print("❌ No price condition - plan may not execute")
            
            print()
            print("-" * 80)
            print()
        
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print()
        print("System recognizes these order flow conditions:")
        for name, desc in recognized_order_flow.items():
            print(f"  - {name}")
        print()
        print("If plans use different names (e.g., 'Cvd Div Bear', 'Delta Divergence Bull'),")
        print("they will NOT be monitored. Plans need to use exact condition names.")
        print()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(review_plans())
