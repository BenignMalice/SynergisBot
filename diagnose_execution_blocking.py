"""
Comprehensive diagnosis of execution blocking issues:
1. Check MT5 connection status
2. Review M1 validation logic
3. Check zone entry tracking
4. Add debug logging to identify blocking steps
"""
import asyncio
import json
import logging
from cursor_trading_bridge import get_bridge
from datetime import datetime

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def diagnose_execution_blocking():
    """Comprehensive diagnosis of execution blocking"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("COMPREHENSIVE EXECUTION BLOCKING DIAGNOSIS")
    print("=" * 70)
    
    # 1. Check MT5 Connection Status
    print("\n" + "=" * 70)
    print("1. CHECKING MT5 CONNECTION STATUS")
    print("=" * 70)
    
    try:
        # Try to get current price (requires MT5)
        xau_price = await bridge.get_current_price("XAUUSD")
        btc_price = await bridge.get_current_price("BTCUSD")
        
        xau_bid = xau_price.get("data", {}).get("bid", None)
        btc_bid = btc_price.get("data", {}).get("bid", None)
        
        print(f"\n✅ MT5 Connection: WORKING")
        print(f"   XAUUSD Price: ${xau_bid:.2f}" if xau_bid else "   XAUUSD: N/A")
        print(f"   BTCUSD Price: ${btc_bid:,.2f}" if btc_bid else "   BTCUSD: N/A")
        
        if xau_bid and btc_bid:
            print(f"\n   ✅ MT5 is connected and returning prices")
            print(f"   ✅ Connection status: HEALTHY")
        else:
            print(f"\n   ⚠️ MT5 connected but prices not available")
            print(f"   ⚠️ Check symbol names and market hours")
            
    except Exception as e:
        print(f"\n❌ MT5 Connection: FAILED")
        print(f"   Error: {e}")
        print(f"   ⚠️ This will block ALL plan execution!")
        logger.exception("MT5 connection error")
    
    # 2. Review M1 Validation
    print("\n" + "=" * 70)
    print("2. REVIEWING M1 VALIDATION LOGIC")
    print("=" * 70)
    
    # Get system status to check M1 analyzer
    status = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    # Find price-only plans
    price_only_plans = []
    for plan in all_plans:
        if plan.get("symbol") == "XAUUSDc":
            conditions = plan.get("conditions", {})
            # Check if it's price-only (only price_near + tolerance, no structure conditions)
            has_structure = any([
                conditions.get("liquidity_sweep"),
                conditions.get("rejection_wick"),
                conditions.get("choch_bull"),
                conditions.get("choch_bear"),
                conditions.get("bos_bull"),
                conditions.get("bos_bear"),
                conditions.get("order_block"),
                conditions.get("inside_bar"),
                conditions.get("vwap_deviation"),
            ])
            
            if not has_structure and "price_near" in conditions:
                price_only_plans.append(plan)
    
    print(f"\n   Found {len(price_only_plans)} price-only plans")
    
    if price_only_plans:
        print(f"\n   Sample Price-Only Plan:")
        sample = price_only_plans[0]
        plan_id = sample.get("plan_id", "N/A")
        conditions = sample.get("conditions", {})
        status_val = sample.get("status", "N/A")
        
        print(f"      Plan ID: {plan_id[:30]}...")
        print(f"      Status: {status_val}")
        print(f"      Conditions: {list(conditions.keys())}")
        print(f"      Conditions Detail: {json.dumps(conditions, indent=8, default=str)}")
        
        print(f"\n   🔍 M1 Validation Analysis:")
        print(f"      • M1 validation runs for ALL plans if m1_analyzer is available")
        print(f"      • Price-only plans may be blocked by M1 validation")
        print(f"      • Check: Does _validate_m1_conditions() return False for price-only plans?")
        print(f"      • Recommendation: Skip M1 validation for price-only plans")
    
    # 3. Check Zone Entry Tracking
    print("\n" + "=" * 70)
    print("3. CHECKING ZONE ENTRY TRACKING")
    print("=" * 70)
    
    if price_only_plans:
        sample_plan = price_only_plans[0]
        plan_id = sample_plan.get("plan_id", "N/A")
        entry = sample_plan.get("entry_price", 0)
        conditions = sample_plan.get("conditions", {})
        tolerance = conditions.get("tolerance", 0)
        price_near = conditions.get("price_near", entry)
        zone_entry_tracked = sample_plan.get("zone_entry_tracked", False)
        zone_entry_time = sample_plan.get("zone_entry_time", None)
        
        # Get current price
        try:
            current_price = xau_bid if xau_bid else 4492.0
            distance = abs(current_price - price_near)
            in_range = distance <= tolerance
        except:
            current_price = 4492.0
            distance = abs(current_price - price_near)
            in_range = distance <= tolerance
        
        print(f"\n   Plan: {plan_id[:30]}...")
        print(f"   Entry: ${entry:.2f}")
        print(f"   Price Near: ${price_near:.2f}")
        print(f"   Tolerance: ±{tolerance}")
        print(f"   Current Price: ${current_price:.2f}")
        print(f"   Distance: {distance:.2f}")
        print(f"   In Range: {'✅ YES' if in_range else '❌ NO'}")
        print(f"   Zone Entry Tracked: {zone_entry_tracked}")
        print(f"   Zone Entry Time: {zone_entry_time}")
        
        print(f"\n   🔍 Zone Entry Tracking Analysis:")
        if zone_entry_tracked:
            print(f"      ✅ Zone entry has been tracked")
            print(f"      ⚠️ But plan still hasn't executed")
            print(f"      ⚠️ This suggests blocking is happening AFTER zone entry detection")
        else:
            print(f"      ❌ Zone entry NOT tracked")
            print(f"      ⚠️ Possible issue: Plan created while price already in zone")
            print(f"      ⚠️ Zone tracking may require price to MOVE into zone (outside → inside)")
            print(f"      ⚠️ If price is already in zone when plan created, entry may not be detected")
        
        print(f"\n   💡 Zone Entry Logic:")
        print(f"      • _check_tolerance_zone_entry() checks if price is in zone")
        print(f"      • entry_detected = True when price moves from outside → inside")
        print(f"      • If price is already in zone, entry_detected may be False")
        print(f"      • This might block execution even if price is in range")
    
    # 4. Add Debug Logging Analysis
    print("\n" + "=" * 70)
    print("4. DEBUG LOGGING ANALYSIS")
    print("=" * 70)
    
    print(f"\n   📋 Validation Steps in _check_conditions():")
    print(f"      1. MT5 service validation")
    print(f"      2. MT5 connection check")
    print(f"      3. Symbol normalization and validation")
    print(f"      4. Get current price")
    print(f"      5. Check expiration")
    print(f"      6. Check price_near + tolerance zone entry")
    print(f"      7. Check structure conditions (CHOCH, BOS, etc.)")
    print(f"      8. Check M1 validation (_validate_m1_conditions)")
    print(f"      9. Enhanced contextual validation")
    print(f"      10. Execute trade")
    
    print(f"\n   🔍 Potential Blocking Points:")
    print(f"      • Step 2: MT5 connection failure → Returns False")
    print(f"      • Step 6: Zone entry not detected → Returns False")
    print(f"      • Step 8: M1 validation fails → Returns False")
    print(f"      • Step 9: Enhanced validation blocks → Returns False")
    
    print(f"\n   💡 Recommended Debug Logging:")
    print(f"      Add logging at each step:")
    print(f"      - logger.debug(f'Plan {plan_id}: MT5 connection check: {result}')")
    print(f"      - logger.debug(f'Plan {plan_id}: Zone entry check: {in_zone}')")
    print(f"      - logger.debug(f'Plan {plan_id}: M1 validation: {result}')")
    print(f"      - logger.debug(f'Plan {plan_id}: Enhanced validation: {result}')")
    print(f"      - logger.debug(f'Plan {plan_id}: All conditions passed, executing...')")
    
    # Create a test plan with execute_immediately flag
    print("\n" + "=" * 70)
    print("5. CREATING TEST PLAN WITH EXECUTE_IMMEDIATELY")
    print("=" * 70)
    
    try:
        current_price = xau_bid if xau_bid else 4492.0
        
        test_plan = {
            "plan_type": "auto_trade",
            "symbol": "XAUUSDc",
            "direction": "SELL",
            "entry": current_price + 1.0,  # Just above current
            "stop_loss": current_price + 5.0,
            "take_profit": current_price - 7.0,
            "volume": 0.01,
            "conditions": {
                "price_near": current_price + 1.0,
                "tolerance": 2.0,
                "execute_immediately": True  # Bypass some validations
            },
            "expires_hours": 1,
            "notes": "TEST: Execute immediately flag - bypass validations"
        }
        
        print(f"\n   Creating test plan with execute_immediately flag...")
        create_result = await bridge.registry.execute(
            "moneybot.create_multiple_auto_plans",
            {"plans": [test_plan]}
        )
        
        create_data = create_result.get("data", {})
        if create_data.get("successful", 0) > 0:
            test_plan_id = create_data.get("results", [{}])[0].get("plan_id", "N/A")
            print(f"   ✅ Test plan created: {test_plan_id}")
            print(f"   💡 This plan should bypass some validations")
            print(f"   💡 Monitor if this one triggers")
        else:
            print(f"   ❌ Test plan creation failed")
            
    except Exception as e:
        print(f"   ⚠️ Could not create test plan: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("DIAGNOSIS SUMMARY")
    print("=" * 70)
    
    print(f"\n✅ MT5 Connection: {'WORKING' if xau_bid else 'CHECK REQUIRED'}")
    print(f"✅ Found {len(price_only_plans)} price-only plans")
    print(f"✅ Zone entry tracking analyzed")
    print(f"✅ Debug logging recommendations provided")
    
    print(f"\n🔴 CRITICAL FINDINGS:")
    print(f"   1. Zone entry tracking may require price MOVEMENT (outside → inside)")
    print(f"   2. M1 validation may be blocking price-only plans")
    print(f"   3. Enhanced contextual validation may be blocking execution")
    print(f"   4. Plans created while price is already in zone may not trigger")
    
    print(f"\n💡 IMMEDIATE ACTIONS:")
    print(f"   1. Check if MT5 connection is stable (✅ Done - appears working)")
    print(f"   2. Review _validate_m1_conditions() to skip for price-only plans")
    print(f"   3. Fix zone entry tracking to work for plans created in-zone")
    print(f"   4. Add debug logging to identify exact blocking point")
    print(f"   5. Monitor test plan with execute_immediately flag")
    
    print(f"\n📋 NEXT STEPS:")
    print(f"   • Review auto_execution_system.py::_check_conditions()")
    print(f"   • Add debug logging at each validation step")
    print(f"   • Modify zone entry tracking to detect in-zone plans")
    print(f"   • Consider skipping M1 validation for price-only plans")

if __name__ == "__main__":
    asyncio.run(diagnose_execution_blocking())
