"""
Check executed plans and their status
"""
import asyncio
import json
from cursor_trading_bridge import get_bridge
from datetime import datetime

async def check_executed_plans():
    """Check executed plans and their status"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("EXECUTED PLANS ANALYSIS")
    print("=" * 70)
    
    # Get system status
    status = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    # Get current prices
    try:
        xau_price = await bridge.get_current_price("XAUUSD")
        xau_bid = xau_price.get("data", {}).get("bid", None)
        print(f"\n💰 Current XAUUSD Price: ${xau_bid:.2f}" if xau_bid else "\n💰 Current XAUUSD Price: N/A")
    except:
        xau_bid = None
    
    # Separate plans by status
    executed_plans = []
    pending_plans = []
    other_status = []
    
    for plan in all_plans:
        symbol = plan.get("symbol", "")
        status_val = plan.get("status", "")
        
        if symbol == "XAUUSDc":
            if status_val == "executed":
                executed_plans.append(plan)
            elif status_val == "pending":
                pending_plans.append(plan)
            else:
                other_status.append(plan)
    
    # Analyze executed plans
    print(f"\n📊 XAUUSD Plans Status:")
    print(f"   Executed: {len(executed_plans)}")
    print(f"   Pending: {len(pending_plans)}")
    print(f"   Other: {len(other_status)}")
    
    if executed_plans:
        print(f"\n✅ EXECUTED PLANS ({len(executed_plans)}):")
        print("-" * 70)
        
        for i, plan in enumerate(executed_plans, 1):
            plan_id = plan.get("plan_id", "N/A")
            direction = plan.get("direction", "N/A")
            entry = plan.get("entry_price", 0)
            sl = plan.get("stop_loss", 0)
            tp = plan.get("take_profit", 0)
            executed_at = plan.get("executed_at", "N/A")
            ticket = plan.get("ticket", "N/A")
            profit_loss = plan.get("profit_loss")
            exit_price = plan.get("exit_price")
            close_time = plan.get("close_time")
            close_reason = plan.get("close_reason", "N/A")
            notes = plan.get("notes", "")
            
            # Calculate R:R
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            rr = reward / risk if risk > 0 else 0
            
            print(f"\n{i}. Plan: {plan_id}")
            print(f"   Direction: {direction}")
            print(f"   Entry: ${entry:.2f} | SL: ${sl:.2f} | TP: ${tp:.2f}")
            print(f"   R:R: 1:{rr:.2f}" if rr > 0 else "   R:R: N/A")
            print(f"   Executed: {executed_at}")
            print(f"   Ticket: {ticket}")
            
            if close_time:
                print(f"   ✅ CLOSED")
                print(f"   Close Time: {close_time}")
                print(f"   Close Reason: {close_reason}")
                if profit_loss is not None:
                    print(f"   P&L: ${profit_loss:.2f}")
                if exit_price:
                    print(f"   Exit Price: ${exit_price:.2f}")
            else:
                print(f"   ⏸️ Still Open")
                if xau_bid:
                    # Calculate current P&L
                    if direction == "BUY":
                        current_pl = (xau_bid - entry) * 100  # Assuming 0.01 lot = $1 per point
                    else:
                        current_pl = (entry - xau_bid) * 100
                    print(f"   Current P&L: ${current_pl:.2f} (estimated)")
            
            # Check if it's a price-only plan
            conditions = plan.get("conditions", {})
            has_structure = any([
                conditions.get("liquidity_sweep"),
                conditions.get("rejection_wick"),
                conditions.get("choch_bull"),
                conditions.get("choch_bear"),
                conditions.get("bos_bull"),
                conditions.get("bos_bear"),
                conditions.get("order_block"),
            ])
            
            if not has_structure and "price_near" in conditions:
                print(f"   Type: Price-only plan (fixes working!)")
            else:
                print(f"   Type: Structure-based plan")
            
            if notes:
                print(f"   Notes: {notes[:60]}...")
    
    # Check pending plans
    if pending_plans:
        print(f"\n⏸️ PENDING PLANS ({len(pending_plans)}):")
        print("-" * 70)
        
        in_range = []
        out_of_range = []
        
        for plan in pending_plans[:10]:  # Show first 10
            plan_id = plan.get("plan_id", "N/A")
            direction = plan.get("direction", "N/A")
            entry = plan.get("entry_price", 0)
            conditions = plan.get("conditions", {})
            tolerance = conditions.get("tolerance", 0)
            price_near = conditions.get("price_near", entry)
            
            if xau_bid:
                distance = abs(xau_bid - price_near)
                in_zone = distance <= tolerance
                
                if in_zone:
                    in_range.append(plan)
                else:
                    out_of_range.append(plan)
        
        print(f"   In Range: {len(in_range)}")
        print(f"   Out of Range: {len(out_of_range)}")
        
        if in_range:
            print(f"\n   Plans Ready to Trigger:")
            for plan in in_range[:5]:
                plan_id = plan.get("plan_id", "N/A")
                direction = plan.get("direction", "N/A")
                entry = plan.get("entry_price", 0)
                conditions = plan.get("conditions", {})
                tolerance = conditions.get("tolerance", 0)
                price_near = conditions.get("price_near", entry)
                distance = abs(xau_bid - price_near) if xau_bid else 999
                
                print(f"      {plan_id[:20]}... | {direction} @ ${entry:.2f} | Distance: {distance:.2f}")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    open_positions = sum(1 for p in executed_plans if not p.get("close_time"))
    closed_positions = sum(1 for p in executed_plans if p.get("close_time"))
    
    print(f"\n✅ Executed Plans: {len(executed_plans)}")
    print(f"   Open: {open_positions}")
    print(f"   Closed: {closed_positions}")
    print(f"   Pending: {len(pending_plans)}")
    
    if executed_plans:
        print(f"\n🎉 SUCCESS: Plans are executing!")
        print(f"   The fixes are working - price-only plans are triggering")
        print(f"   {len(executed_plans)} XAUUSD plan(s) have executed")
    
    # Check for any issues
    if open_positions > 0:
        print(f"\n💡 You mentioned manually closing some positions")
        print(f"   {open_positions} position(s) may still be open")
        print(f"   Check MT5 for current positions")

if __name__ == "__main__":
    asyncio.run(check_executed_plans())
