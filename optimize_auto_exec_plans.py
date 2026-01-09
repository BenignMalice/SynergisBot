"""
Optimize auto-execution plans:
1. Increase tolerance for price proximity
2. Create simplified versions with fewer conditions
"""
import asyncio
import json
from cursor_trading_bridge import get_bridge

async def optimize_plans():
    """Optimize plans by increasing tolerance and creating simplified versions"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("OPTIMIZING AUTO-EXECUTION PLANS")
    print("=" * 70)
    
    # Get all plans
    status = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    print(f"\n📊 Found {len(all_plans)} pending plans")
    
    # Separate plans by symbol and identify low tolerance plans
    btc_plans_to_update = []
    xau_plans_to_update = []
    simplified_plans_to_create = []
    
    for plan in all_plans:
        plan_id = plan.get("plan_id")
        symbol = plan.get("symbol", "")
        conditions = plan.get("conditions", {})
        tolerance = conditions.get("tolerance", 0)
        entry_price = plan.get("entry_price", 0)
        direction = plan.get("direction", "")
        stop_loss = plan.get("stop_loss", 0)
        take_profit = plan.get("take_profit", 0)
        expires_at = plan.get("expires_at")
        
        # Check if plan needs tolerance update
        needs_update = False
        new_tolerance = tolerance
        
        if symbol == "BTCUSDc":
            # BTCUSD: increase tolerance if ≤ 200
            if tolerance <= 200:
                new_tolerance = min(500, tolerance * 2)  # Double, max 500
                needs_update = True
        elif symbol == "XAUUSDc":
            # XAUUSD: increase tolerance if ≤ 4
            if tolerance <= 4:
                new_tolerance = min(10, max(5, tolerance * 2))  # Double, between 5-10
                needs_update = True
        
        # Check if plan has complex conditions (needs simplification)
        has_complex_conditions = False
        condition_count = 0
        
        complex_indicators = [
            "liquidity_sweep", "rejection_wick", "inside_bar", "bb_expansion",
            "choch_bull", "choch_bear", "bos_bull", "bos_bear",
            "order_block", "breaker_block", "vwap_deviation"
        ]
        
        for indicator in complex_indicators:
            if conditions.get(indicator):
                condition_count += 1
        
        # If plan has 2+ complex conditions, create simplified version
        if condition_count >= 2:
            has_complex_conditions = True
        
        # Prepare update if needed
        if needs_update:
            new_conditions = conditions.copy()
            new_conditions["tolerance"] = new_tolerance
            
            if symbol == "BTCUSDc":
                btc_plans_to_update.append({
                    "plan_id": plan_id,
                    "conditions": new_conditions,
                    "notes": f"{plan.get('notes', '')} [Tolerance increased: {tolerance} → {new_tolerance}]"
                })
            elif symbol == "XAUUSDc":
                xau_plans_to_update.append({
                    "plan_id": plan_id,
                    "conditions": new_conditions,
                    "notes": f"{plan.get('notes', '')} [Tolerance increased: {tolerance} → {new_tolerance}]"
                })
        
        # Create simplified version if complex
        if has_complex_conditions:
            # Simplified: keep only price_near + tolerance + one main condition
            simplified_conditions = {
                "price_near": conditions.get("price_near", entry_price),
                "tolerance": new_tolerance if needs_update else tolerance
            }
            
            # Keep the most important condition
            if conditions.get("choch_bull") or conditions.get("choch_bear"):
                simplified_conditions["choch_bull"] = conditions.get("choch_bull", False)
                simplified_conditions["choch_bear"] = conditions.get("choch_bear", False)
                simplified_conditions["timeframe"] = conditions.get("timeframe", "M15")
            elif conditions.get("bos_bull") or conditions.get("bos_bear"):
                simplified_conditions["bos_bull"] = conditions.get("bos_bull", False)
                simplified_conditions["bos_bear"] = conditions.get("bos_bear", False)
                simplified_conditions["timeframe"] = conditions.get("timeframe", "M15")
            elif conditions.get("order_block"):
                simplified_conditions["order_block"] = True
                simplified_conditions["order_block_type"] = conditions.get("order_block_type", "auto")
            elif conditions.get("liquidity_sweep"):
                simplified_conditions["liquidity_sweep"] = True
                simplified_conditions["timeframe"] = conditions.get("timeframe", "M15")
            else:
                # Just price proximity
                pass
            
            # Add min_confluence if original had it
            if conditions.get("confluence_min"):
                simplified_conditions["confluence_min"] = max(50, conditions.get("confluence_min", 60) - 10)
            
            simplified_plans_to_create.append({
                "plan_type": "auto_trade",
                "symbol": symbol,
                "direction": direction,
                "entry": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "volume": 0.01,
                "conditions": simplified_conditions,
                "expires_hours": 24,
                "notes": f"Simplified: {plan.get('notes', '')} [Reduced conditions for higher trigger probability]"
            })
    
    # Update plans with increased tolerance
    print(f"\n📝 Plans to Update:")
    print(f"   BTCUSD: {len(btc_plans_to_update)} plans")
    print(f"   XAUUSD: {len(xau_plans_to_update)} plans")
    
    all_updates = btc_plans_to_update + xau_plans_to_update
    
    if all_updates:
        print(f"\n🔄 Updating {len(all_updates)} plans with increased tolerance...")
        update_result = await bridge.registry.execute(
            "moneybot.update_multiple_auto_plans",
            {"updates": all_updates}
        )
        
        update_data = update_result.get("data", {})
        successful_updates = update_data.get("successful", 0)
        failed_updates = update_data.get("failed", 0)
        
        print(f"   ✅ Updated: {successful_updates}")
        print(f"   ❌ Failed: {failed_updates}")
        
        if update_data.get("results"):
            print(f"\n   Update Results:")
            for result in update_data["results"][:5]:  # Show first 5
                plan_id = result.get("plan_id", "N/A")
                status = result.get("status", "N/A")
                print(f"      {plan_id[:20]}... → {status}")
    
    # Create simplified plans
    print(f"\n📝 Simplified Plans to Create:")
    print(f"   Total: {len(simplified_plans_to_create)} plans")
    
    if simplified_plans_to_create:
        print(f"\n🆕 Creating {len(simplified_plans_to_create)} simplified plans...")
        
        # Split into batches of 20 (max per batch)
        batch_size = 20
        total_created = 0
        total_failed = 0
        
        for i in range(0, len(simplified_plans_to_create), batch_size):
            batch = simplified_plans_to_create[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(simplified_plans_to_create) + batch_size - 1) // batch_size
            
            print(f"   Creating batch {batch_num}/{total_batches} ({len(batch)} plans)...")
            
            create_result = await bridge.registry.execute(
                "moneybot.create_multiple_auto_plans",
                {"plans": batch}
            )
            
            create_data = create_result.get("data", {})
            batch_created = create_data.get("successful", 0)
            batch_failed = create_data.get("failed", 0)
            
            total_created += batch_created
            total_failed += batch_failed
            
            print(f"      ✅ Created: {batch_created}")
            print(f"      ❌ Failed: {batch_failed}")
        
        print(f"\n   📊 Total Simplified Plans:")
        print(f"      ✅ Created: {total_created}")
        print(f"      ❌ Failed: {total_failed}")
    
    # Summary
    print("\n" + "=" * 70)
    print("OPTIMIZATION SUMMARY")
    print("=" * 70)
    print(f"\n✅ Updated {len(all_updates)} plans with increased tolerance")
    print(f"✅ Created {len(simplified_plans_to_create)} simplified plan versions")
    print(f"\n💡 Benefits:")
    print(f"   • Higher tolerance = More flexible price entry")
    print(f"   • Simplified conditions = Higher trigger probability")
    print(f"   • Both versions active = More opportunities to catch moves")
    print(f"\n📈 Your total plans should now be: {len(all_plans) + len(simplified_plans_to_create)}")

if __name__ == "__main__":
    asyncio.run(optimize_plans())
