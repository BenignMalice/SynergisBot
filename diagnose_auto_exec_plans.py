"""
Diagnose why auto-execution plans aren't triggering
"""
import asyncio
import json
from cursor_trading_bridge import get_bridge
from datetime import datetime

async def diagnose_plans():
    """Diagnose why plans aren't triggering"""
    bridge = get_bridge()
    
    # Get system status
    print("=" * 70)
    print("AUTO-EXECUTION PLAN DIAGNOSIS")
    print("=" * 70)
    
    status = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status.get("data", {})
    system_status = status_data.get("system_status", {})
    
    print(f"\n📊 System Status:")
    print(f"   Running: {system_status.get('running', False)}")
    print(f"   Thread Alive: {system_status.get('thread_alive', False)}")
    print(f"   Check Interval: {system_status.get('check_interval', 'N/A')} seconds")
    print(f"   Pending Plans: {system_status.get('pending_plans', 0)}")
    
    # Get current prices
    print(f"\n💰 Current Prices:")
    try:
        btc_price = await bridge.get_current_price("BTCUSD")
        xau_price = await bridge.get_current_price("XAUUSD")
        btc_bid = btc_price.get("data", {}).get("bid", "N/A")
        xau_bid = xau_price.get("data", {}).get("bid", "N/A")
        print(f"   BTCUSD: {btc_bid}")
        print(f"   XAUUSD: {xau_bid}")
    except Exception as e:
        print(f"   ⚠️ Could not get prices: {e}")
        btc_bid = None
        xau_bid = None
    
    # Analyze sample plans
    plans = system_status.get("plans", [])[:10]  # First 10 plans
    
    print(f"\n🔍 Analyzing {len(plans)} Sample Plans:")
    print("-" * 70)
    
    for i, plan in enumerate(plans, 1):
        plan_id = plan.get("plan_id", "N/A")
        symbol = plan.get("symbol", "N/A")
        direction = plan.get("direction", "N/A")
        entry = plan.get("entry_price", 0)
        conditions = plan.get("conditions", {})
        expires_at = plan.get("expires_at")
        zone_entry_tracked = plan.get("zone_entry_tracked", False)
        
        # Check expiration
        expired = False
        if expires_at:
            try:
                exp_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                now = datetime.now(exp_time.tzinfo)
                expired = now > exp_time
            except:
                pass
        
        # Check price proximity
        current_price = None
        price_in_range = False
        if symbol == "BTCUSDc" and btc_bid:
            current_price = btc_bid
            price_near = conditions.get("price_near", entry)
            tolerance = conditions.get("tolerance", 0)
            price_in_range = abs(current_price - price_near) <= tolerance
        elif symbol == "XAUUSDc" and xau_bid:
            current_price = xau_bid
            price_near = conditions.get("price_near", entry)
            tolerance = conditions.get("tolerance", 0)
            price_in_range = abs(current_price - price_near) <= tolerance
        
        print(f"\n{i}. Plan: {plan_id[:20]}...")
        print(f"   Symbol: {symbol} | Direction: {direction}")
        print(f"   Entry: {entry} | Current: {current_price if current_price else 'N/A'}")
        print(f"   Status: {plan.get('status', 'N/A')} | Expired: {expired}")
        print(f"   Zone Entry Tracked: {zone_entry_tracked}")
        
        if expired:
            print(f"   ❌ EXPIRED (expires_at: {expires_at})")
        elif not price_in_range and current_price:
            price_near = conditions.get("price_near", entry)
            tolerance = conditions.get("tolerance", 0)
            distance = abs(current_price - price_near)
            print(f"   ⚠️ Price NOT in range")
            print(f"      Target: {price_near} ± {tolerance}")
            print(f"      Current: {current_price}")
            print(f"      Distance: {distance:.2f} (needs to be ≤ {tolerance})")
        elif price_in_range:
            print(f"   ✅ Price IS in range")
        
        # Check key conditions
        key_conditions = []
        if conditions.get("choch_bull") or conditions.get("choch_bear"):
            tf = conditions.get("timeframe", "N/A")
            key_conditions.append(f"CHOCH ({tf})")
        if conditions.get("bos_bull") or conditions.get("bos_bear"):
            tf = conditions.get("timeframe", "N/A")
            key_conditions.append(f"BOS ({tf})")
        if conditions.get("liquidity_sweep"):
            tf = conditions.get("timeframe", "N/A")
            key_conditions.append(f"Liquidity Sweep ({tf})")
        if conditions.get("order_block"):
            key_conditions.append("Order Block")
        if conditions.get("inside_bar"):
            key_conditions.append("Inside Bar")
        if conditions.get("rejection_wick"):
            key_conditions.append("Rejection Wick")
        if conditions.get("confluence_min"):
            key_conditions.append(f"Confluence ≥ {conditions['confluence_min']}")
        
        if key_conditions:
            print(f"   Conditions: {', '.join(key_conditions)}")
        
        if zone_entry_tracked:
            print(f"   ℹ️ Price entered zone but conditions not fully met yet")
    
    print("\n" + "=" * 70)
    print("DIAGNOSIS SUMMARY")
    print("=" * 70)
    
    print(f"\n✅ System is running: {system_status.get('running', False)}")
    print(f"✅ Monitoring thread alive: {system_status.get('thread_alive', False)}")
    print(f"✅ Checking every {system_status.get('check_interval', 'N/A')} seconds")
    
    print(f"\n💡 Why Plans Might Not Trigger:")
    print("   1. Price not in range (check price_near ± tolerance)")
    print("   2. Structure conditions not met (CHOCH/BOS not formed yet)")
    print("   3. Confluence too low (if min_confluence required)")
    print("   4. Plans expired (check expires_at)")
    print("   5. Multiple conditions must ALL be true simultaneously")
    print("   6. System checks every 30 seconds - price may move out of range")
    
    print(f"\n🔧 Recommendations:")
    print("   1. Check if current prices are near entry levels")
    print("   2. Verify structure conditions are actually forming")
    print("   3. Consider reducing tolerance if price keeps missing")
    print("   4. Check expiration times - some plans may have expired")
    print("   5. Review condition complexity - simpler = more likely to trigger")

if __name__ == "__main__":
    asyncio.run(diagnose_plans())
