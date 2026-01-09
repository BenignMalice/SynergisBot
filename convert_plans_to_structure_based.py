"""
Convert price-only plans to structure-based plans
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def convert_plans_to_structure():
    """Convert price-only plans to structure-based"""
    bridge = get_bridge()
    
    print("=" * 80)
    print("CONVERTING PRICE-ONLY PLANS TO STRUCTURE-BASED")
    print("=" * 80)
    
    # Price-only plan IDs to convert
    price_only_plans = [
        "chatgpt_45b1c505",  # BTCUSDc BUY (auto_trade)
        "chatgpt_095a448e",  # BTCUSDc SELL (auto_trade)
        "chatgpt_bd18a876",  # XAUUSDc SELL (bearish breakout)
    ]
    
    # Get current plan details
    print("\n1. Getting Current Plan Details...")
    print("-" * 80)
    
    status_result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status_result.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    plans_to_update = []
    
    for plan_id in price_only_plans:
        plan = next((p for p in all_plans if p.get("plan_id") == plan_id), None)
        if not plan:
            print(f"   ⚠️  {plan_id}: NOT FOUND - Skipping")
            continue
        
        symbol = plan.get("symbol", "N/A")
        direction = plan.get("direction", "N/A")
        status = plan.get("status", "N/A")
        conditions = plan.get("conditions", {})
        
        if status != "pending":
            print(f"   ⚠️  {plan_id}: Status is '{status}' (not pending) - Cannot update")
            continue
        
        plans_to_update.append({
            "plan_id": plan_id,
            "symbol": symbol,
            "direction": direction,
            "conditions": conditions,
            "entry": plan.get("entry", 0),
            "stop_loss": plan.get("stop_loss", 0),
            "take_profit": plan.get("take_profit", 0)
        })
        
        print(f"   ✅ {plan_id}: {symbol} {direction} - Ready to update")
    
    if not plans_to_update:
        print("\n   ❌ No plans to update")
        return
    
    # Update plans with structure conditions
    print("\n2. Updating Plans with Structure Conditions...")
    print("-" * 80)
    
    for plan in plans_to_update:
        plan_id = plan["plan_id"]
        symbol = plan["symbol"]
        direction = plan["direction"]
        current_conditions = plan["conditions"]
        
        print(f"\n   Updating: {plan_id} ({symbol} {direction})")
        
        # Determine structure condition based on symbol and direction
        new_conditions = current_conditions.copy()
        
        if "BTC" in symbol:
            # BTC plans: Add order_block condition
            new_conditions["order_block"] = True
            new_conditions["order_block_type"] = "auto"  # Let system detect bull/bear
            new_conditions["timeframe"] = "M5"  # Add timeframe for structure detection
            new_conditions["min_validation_score"] = 60  # Minimum order block validation score
            
            print(f"      Adding: order_block=true, order_block_type=auto, timeframe=M5")
            
        elif "XAU" in symbol:
            # XAUUSD plan: Add rejection_wick (for bearish breakout)
            if direction == "SELL":
                new_conditions["rejection_wick"] = True
                new_conditions["timeframe"] = "M5"
                new_conditions["min_wick_ratio"] = 2.0  # Minimum wick ratio for confirmation
                print(f"      Adding: rejection_wick=true, timeframe=M5, min_wick_ratio=2.0")
            else:
                # For BUY, use order_block
                new_conditions["order_block"] = True
                new_conditions["order_block_type"] = "auto"
                new_conditions["timeframe"] = "M5"
                print(f"      Adding: order_block=true, order_block_type=auto, timeframe=M5")
        
        # Keep existing price conditions
        if "price_near" not in new_conditions:
            new_conditions["price_near"] = plan["entry"]
        if "tolerance" not in new_conditions:
            # Set default tolerance based on symbol
            if "BTC" in symbol:
                new_conditions["tolerance"] = 200.0
            else:
                new_conditions["tolerance"] = 5.0
        
        # Update the plan
        try:
            update_result = await bridge.registry.execute("moneybot.update_auto_plan", {
                "plan_id": plan_id,
                "conditions": new_conditions,
                "notes": f"Converted from price-only to structure-based ({'order_block' if 'order_block' in new_conditions else 'rejection_wick'})"
            })
            
            update_data = update_result.get("data", {})
            if update_data.get("success"):
                print(f"      ✅ Successfully updated")
            else:
                print(f"      ❌ Update failed: {update_data.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"      ❌ Error updating plan: {str(e)}")
    
    # Verify updates
    print("\n3. Verifying Updates...")
    print("-" * 80)
    
    status_result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status_result.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    for plan_id in [p["plan_id"] for p in plans_to_update]:
        plan = next((p for p in all_plans if p.get("plan_id") == plan_id), None)
        if plan:
            conditions = plan.get("conditions", {})
            has_structure = conditions.get("order_block") or conditions.get("rejection_wick")
            
            if has_structure:
                structure_type = "order_block" if conditions.get("order_block") else "rejection_wick"
                print(f"   ✅ {plan_id}: Now has {structure_type} condition")
            else:
                print(f"   ⚠️  {plan_id}: Still missing structure condition")
    
    print("\n" + "=" * 80)
    print("CONVERSION COMPLETE")
    print("=" * 80)
    print(f"\n✅ Converted {len(plans_to_update)} plan(s) to structure-based")
    print(f"   Plans now require both price proximity AND structure confirmation")

if __name__ == "__main__":
    asyncio.run(convert_plans_to_structure())
