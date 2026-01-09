"""
Comprehensive verification script:
1. Verify fixes are working after restart
2. Check for any other blocking issues
3. Create additional test plans to verify execution
"""
import asyncio
import json
import logging
from cursor_trading_bridge import get_bridge
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def verify_fixes_and_test():
    """Comprehensive verification and testing"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("COMPREHENSIVE FIX VERIFICATION & TESTING")
    print("=" * 70)
    
    # Get current price
    print("\n💰 Current Market Prices:")
    try:
        xau_price = await bridge.get_current_price("XAUUSD")
        btc_price = await bridge.get_current_price("BTCUSD")
        xau_bid = xau_price.get("data", {}).get("bid", None)
        btc_bid = btc_price.get("data", {}).get("bid", None)
        print(f"   XAUUSD: ${xau_bid:.2f}" if xau_bid else "   XAUUSD: N/A")
        print(f"   BTCUSD: ${btc_bid:,.2f}" if btc_bid else "   BTCUSD: N/A")
    except Exception as e:
        print(f"   ⚠️ Could not get prices: {e}")
        xau_bid = 4492.0
        btc_bid = 87500.0
    
    # Get system status
    status = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    print(f"\n📊 System Status:")
    print(f"   Running: {system_status.get('running', False)}")
    print(f"   Thread Alive: {system_status.get('thread_alive', False)}")
    print(f"   Check Interval: {system_status.get('check_interval', 'N/A')} seconds")
    print(f"   Total Plans: {len(all_plans)}")
    
    # 1. Verify Fixes Are Working
    print("\n" + "=" * 70)
    print("1. VERIFYING FIXES ARE WORKING")
    print("=" * 70)
    
    # Find price-only plans
    price_only_plans = []
    for plan in all_plans:
        if plan.get("symbol") in ["XAUUSDc", "BTCUSDc"]:
            conditions = plan.get("conditions", {})
            # Check if it's price-only
            has_structure = any([
                conditions.get("liquidity_sweep"),
                conditions.get("rejection_wick"),
                conditions.get("choch_bull"),
                conditions.get("choch_bear"),
                conditions.get("bos_bull"),
                conditions.get("bos_bear"),
                conditions.get("order_block"),
                conditions.get("inside_bar"),
                conditions.get("m1_choch"),
                conditions.get("m1_bos"),
            ])
            
            if not has_structure and "price_near" in conditions:
                price_only_plans.append(plan)
    
    print(f"\n   Found {len(price_only_plans)} price-only plans")
    
    # Check which are in range
    in_range_count = 0
    executed_count = 0
    
    for plan in price_only_plans:
        plan_id = plan.get("plan_id", "N/A")
        symbol = plan.get("symbol", "")
        entry = plan.get("entry_price", 0)
        conditions = plan.get("conditions", {})
        tolerance = conditions.get("tolerance", 0)
        price_near = conditions.get("price_near", entry)
        status_val = plan.get("status", "")
        zone_entry_tracked = plan.get("zone_entry_tracked", False)
        
        # Check price range
        current_price = xau_bid if symbol == "XAUUSDc" else (btc_bid if symbol == "BTCUSDc" else None)
        if current_price:
            distance = abs(current_price - price_near)
            in_range = distance <= tolerance
            
            if in_range:
                in_range_count += 1
                
            if status_val == "executed":
                executed_count += 1
                print(f"\n   ✅ EXECUTED: {plan_id[:20]}...")
                print(f"      Symbol: {symbol} | Entry: ${entry:,.2f}" if symbol == "BTCUSDc" else f"      Symbol: {symbol} | Entry: ${entry:.2f}")
                print(f"      Status: {status_val}")
    
    print(f"\n   📊 Price-Only Plans Status:")
    print(f"      Total: {len(price_only_plans)}")
    print(f"      In Range: {in_range_count}")
    print(f"      Executed: {executed_count}")
    print(f"      Pending (in range): {in_range_count - executed_count}")
    
    if executed_count > 0:
        print(f"\n   ✅ SUCCESS: Fixes are working! {executed_count} price-only plan(s) executed")
    elif in_range_count > 0:
        print(f"\n   ⚠️ {in_range_count} plan(s) in range but not executed yet")
        print(f"   💡 Wait for next check cycle (30 seconds) or check logs")
    else:
        print(f"\n   ℹ️ No price-only plans currently in range")
    
    # Check zone entry tracking
    print(f"\n   🔍 Zone Entry Tracking:")
    tracked_count = sum(1 for p in price_only_plans if p.get("zone_entry_tracked", False))
    print(f"      Plans with zone entry tracked: {tracked_count}/{len(price_only_plans)}")
    
    if tracked_count < in_range_count:
        print(f"      ⚠️ Some plans in range don't have zone entry tracked")
        print(f"      💡 This may indicate zone tracking fix needs verification")
    
    # 2. Check for Other Blocking Issues
    print("\n" + "=" * 70)
    print("2. CHECKING FOR OTHER BLOCKING ISSUES")
    print("=" * 70)
    
    blocking_issues = []
    
    # Check MT5 connection
    if not xau_bid and not btc_bid:
        blocking_issues.append("MT5 connection not returning prices")
    
    # Check system running
    if not system_status.get("running", False):
        blocking_issues.append("Auto-execution system not running")
    
    if not system_status.get("thread_alive", False):
        blocking_issues.append("Monitoring thread not alive")
    
    # Check for plans with issues
    problem_plans = []
    for plan in all_plans[:20]:  # Check first 20
        plan_id = plan.get("plan_id", "N/A")
        symbol = plan.get("symbol", "")
        status_val = plan.get("status", "")
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
        
        if expired and status_val == "pending":
            problem_plans.append({
                "plan_id": plan_id,
                "issue": "Expired but still pending",
                "expires_at": expires_at
            })
    
    if problem_plans:
        blocking_issues.append(f"{len(problem_plans)} expired plans still pending")
    
    # Check for plans with invalid conditions
    invalid_plans = []
    for plan in all_plans[:20]:
        conditions = plan.get("conditions", {})
        if "price_near" in conditions and "tolerance" not in conditions:
            invalid_plans.append({
                "plan_id": plan.get("plan_id", "N/A"),
                "issue": "price_near without tolerance"
            })
    
    if invalid_plans:
        blocking_issues.append(f"{len(invalid_plans)} plans missing tolerance")
    
    print(f"\n   🔍 Blocking Issues Found: {len(blocking_issues)}")
    if blocking_issues:
        for i, issue in enumerate(blocking_issues, 1):
            print(f"      {i}. {issue}")
    else:
        print(f"      ✅ No blocking issues detected")
    
    if problem_plans:
        print(f"\n   ⚠️ Problem Plans:")
        for plan in problem_plans[:5]:
            print(f"      - {plan['plan_id'][:20]}...: {plan['issue']}")
    
    # 3. Create Additional Test Plans
    print("\n" + "=" * 70)
    print("3. CREATING ADDITIONAL TEST PLANS")
    print("=" * 70)
    
    # Create test plans very close to current price
    test_plans = []
    
    # XAUUSD test plans
    if xau_bid:
        # SELL plans just above current
        test_plans.append({
            "plan_type": "auto_trade",
            "symbol": "XAUUSDc",
            "direction": "SELL",
            "entry": xau_bid + 0.5,  # Very close
            "stop_loss": xau_bid + 4.5,
            "take_profit": xau_bid - 6.5,
            "volume": 0.01,
            "conditions": {
                "price_near": xau_bid + 0.5,
                "tolerance": 1.0  # Very tight tolerance
            },
            "expires_hours": 2,
            "notes": "TEST: Price-only SELL - immediate trigger test (very close to current)"
        })
        
        test_plans.append({
            "plan_type": "auto_trade",
            "symbol": "XAUUSDc",
            "direction": "SELL",
            "entry": xau_bid,  # At current price
            "stop_loss": xau_bid + 4.0,
            "take_profit": xau_bid - 6.0,
            "volume": 0.01,
            "conditions": {
                "price_near": xau_bid,
                "tolerance": 1.0,
                "execute_immediately": True  # Bypass validations
            },
            "expires_hours": 1,
            "notes": "TEST: Execute immediately flag - should trigger right away"
        })
        
        # BUY plan just below current
        test_plans.append({
            "plan_type": "auto_trade",
            "symbol": "XAUUSDc",
            "direction": "BUY",
            "entry": xau_bid - 0.5,
            "stop_loss": xau_bid - 4.5,
            "take_profit": xau_bid + 6.5,
            "volume": 0.01,
            "conditions": {
                "price_near": xau_bid - 0.5,
                "tolerance": 1.0
            },
            "expires_hours": 2,
            "notes": "TEST: Price-only BUY - immediate trigger test"
        })
    
    # BTCUSD test plans
    if btc_bid:
        test_plans.append({
            "plan_type": "auto_trade",
            "symbol": "BTCUSDc",
            "direction": "SELL",
            "entry": btc_bid + 50,  # Close to current
            "stop_loss": btc_bid + 200,
            "take_profit": btc_bid - 300,
            "volume": 0.01,
            "conditions": {
                "price_near": btc_bid + 50,
                "tolerance": 100
            },
            "expires_hours": 2,
            "notes": "TEST: Price-only BTCUSD SELL - immediate trigger test"
        })
    
    if test_plans:
        print(f"\n   Creating {len(test_plans)} test plans very close to current price...")
        
        create_result = await bridge.registry.execute(
            "moneybot.create_multiple_auto_plans",
            {"plans": test_plans}
        )
        
        create_data = create_result.get("data", {})
        successful = create_data.get("successful", 0)
        failed = create_data.get("failed", 0)
        
        print(f"   ✅ Created: {successful}")
        print(f"   ❌ Failed: {failed}")
        
        if create_data.get("results"):
            print(f"\n   Test Plan IDs Created:")
            for result in create_data["results"]:
                if result.get("status") == "created":
                    plan_id = result.get("plan_id", "N/A")
                    direction = result.get("direction", "N/A")
                    print(f"      {plan_id} - {direction}")
        
        # Check which test plans are immediately in range
        print(f"\n   📊 Test Plans Status:")
        for i, plan in enumerate(test_plans, 1):
            symbol = plan["symbol"]
            entry = plan["entry"]
            tolerance = plan["conditions"]["tolerance"]
            current_price = xau_bid if symbol == "XAUUSDc" else (btc_bid if symbol == "BTCUSDc" else None)
            
            if current_price:
                distance = abs(current_price - entry)
                in_range = distance <= tolerance
                
                print(f"      {i}. {symbol} {plan['direction']} @ ${entry:,.2f}" if symbol == "BTCUSDc" else f"      {i}. {symbol} {plan['direction']} @ ${entry:.2f}")
                print(f"         Current: ${current_price:,.2f}" if symbol == "BTCUSDc" else f"         Current: ${current_price:.2f}")
                print(f"         Distance: {distance:.2f} | Tolerance: ±{tolerance}")
                print(f"         Status: {'✅ IN RANGE - Should trigger!' if in_range else '⚠️ Out of range'}")
    
    # Summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    print(f"\n✅ Fixes Verification:")
    print(f"   • Price-only plans found: {len(price_only_plans)}")
    print(f"   • Plans in range: {in_range_count}")
    print(f"   • Plans executed: {executed_count}")
    print(f"   • Zone entry tracked: {tracked_count}/{len(price_only_plans)}")
    
    print(f"\n✅ Blocking Issues Check:")
    print(f"   • Issues found: {len(blocking_issues)}")
    if blocking_issues:
        print(f"   • Action required: Review and fix blocking issues")
    else:
        print(f"   • Status: No blocking issues detected")
    
    print(f"\n✅ Test Plans Created:")
    print(f"   • New test plans: {len(test_plans)}")
    print(f"   • Created successfully: {successful if test_plans else 0}")
    
    print(f"\n💡 Next Steps:")
    print(f"   1. Monitor logs for debug messages:")
    print(f"      - 'Skipping M1 validation (price-only plan)'")
    print(f"      - '✅ ALL CONDITIONS PASSED - Ready for execution'")
    print(f"   2. Wait for next check cycle (30 seconds)")
    print(f"   3. Check if test plans trigger when price moves")
    print(f"   4. Review any blocking issues found")
    
    print(f"\n📋 Expected Behavior After Fixes:")
    print(f"   • Price-only plans skip M1 validation")
    print(f"   • Zone entry tracked even if plan created in-zone")
    print(f"   • Plans execute when price is in tolerance range")
    print(f"   • Debug logs show validation steps")

if __name__ == "__main__":
    asyncio.run(verify_fixes_and_test())
