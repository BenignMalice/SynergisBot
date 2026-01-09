"""
Review auto-execution plans for viability based on current market conditions
"""
import asyncio
import json
from datetime import datetime
from cursor_trading_bridge import get_bridge

async def analyze_and_review_plans():
    """Analyze XAU and BTC, then review plan viability"""
    bridge = get_bridge()
    
    print("=" * 80)
    print("AUTO-EXECUTION PLAN VIABILITY REVIEW")
    print("=" * 80)
    print(f"Review Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Analyze XAUUSD
    print("\n" + "=" * 80)
    print("STEP 1: ANALYZING XAUUSD (GOLD)")
    print("=" * 80)
    
    print("\n1.1 Getting XAUUSD Full Analysis...")
    xau_analysis = await bridge.registry.execute("moneybot.analyse_symbol_full", {
        "symbol": "XAUUSDc"
    })
    xau_data = xau_analysis.get("data", {})
    
    xau_price = xau_data.get("current_price", 0)
    xau_trend = xau_data.get("trend", "N/A")
    xau_structure = xau_data.get("structure", {})
    xau_structure_type = xau_data.get("structure_type", "N/A")
    xau_price_structure = xau_data.get("price_structure", "N/A")
    xau_confluence = xau_data.get("confluence_score", 0)
    xau_volatility = xau_data.get("volatility_status", "N/A")
    xau_momentum = xau_data.get("momentum_quality", "N/A")
    
    print(f"   Current Price: ${xau_price:.2f}")
    print(f"   Trend: {xau_trend}")
    print(f"   Structure Type: {xau_structure_type}")
    print(f"   Price Structure: {xau_price_structure}")
    print(f"   Confluence Score: {xau_confluence}/100")
    print(f"   Volatility: {xau_volatility}")
    print(f"   Momentum: {xau_momentum}")
    
    # Step 2: Analyze BTCUSD
    print("\n" + "=" * 80)
    print("STEP 2: ANALYZING BTCUSD (BITCOIN)")
    print("=" * 80)
    
    print("\n2.1 Getting BTCUSD Full Analysis...")
    btc_analysis = await bridge.registry.execute("moneybot.analyse_symbol_full", {
        "symbol": "BTCUSD"
    })
    btc_data = btc_analysis.get("data", {})
    
    btc_price = btc_data.get("current_price", 0)
    btc_trend = btc_data.get("trend", "N/A")
    btc_structure = btc_data.get("structure", {})
    btc_structure_type = btc_data.get("structure_type", "N/A")
    btc_price_structure = btc_data.get("price_structure", "N/A")
    btc_confluence = btc_data.get("confluence_score", 0)
    btc_volatility = btc_data.get("volatility_status", "N/A")
    btc_momentum = btc_data.get("momentum_quality", "N/A")
    
    print(f"   Current Price: ${btc_price:.2f}")
    print(f"   Trend: {btc_trend}")
    print(f"   Structure Type: {btc_structure_type}")
    print(f"   Price Structure: {btc_price_structure}")
    print(f"   Confluence Score: {btc_confluence}/100")
    print(f"   Volatility: {btc_volatility}")
    print(f"   Momentum: {btc_momentum}")
    
    # Step 3: Get all auto-execution plans
    print("\n" + "=" * 80)
    print("STEP 3: GETTING ALL AUTO-EXECUTION PLANS")
    print("=" * 80)
    
    print("\n3.1 Fetching Plans...")
    status_result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status_result.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    print(f"   Found {len(all_plans)} total plan(s)")
    
    # Filter for XAU and BTC plans
    xau_plans = [p for p in all_plans if p.get("symbol", "").startswith("XAU")]
    btc_plans = [p for p in all_plans if p.get("symbol", "").startswith("BTC")]
    
    print(f"   XAU Plans: {len(xau_plans)}")
    print(f"   BTC Plans: {len(btc_plans)}")
    
    # Step 4: Analyze plan viability
    print("\n" + "=" * 80)
    print("STEP 4: VIABILITY ANALYSIS")
    print("=" * 80)
    
    # Analyze XAU plans
    print("\n4.1 XAUUSD Plans Viability:")
    print("-" * 80)
    
    xau_viable = []
    xau_at_risk = []
    xau_obsolete = []
    xau_conflicting = []
    
    for plan in xau_plans:
        plan_id = plan.get("plan_id", "N/A")
        direction = plan.get("direction", "N/A")
        status = plan.get("status", "N/A")
        conditions = plan.get("conditions", {})
        
        price_near = conditions.get("price_near")
        tolerance = conditions.get("tolerance", 0)
        
        # Check structure conditions
        has_choch = conditions.get("choch_bull") or conditions.get("choch_bear")
        has_bos = conditions.get("bos_bull") or conditions.get("bos_bear")
        has_order_block = conditions.get("order_block")
        has_liquidity_sweep = conditions.get("liquidity_sweep")
        has_rejection_wick = conditions.get("rejection_wick")
        
        # Check if plan direction conflicts with current structure
        direction_conflict = False
        if direction == "BUY" and xau_price_structure == "LOWER_LOW":
            direction_conflict = True
        elif direction == "SELL" and xau_price_structure == "HIGHER_HIGH":
            direction_conflict = True
        
        # Check if structure conditions are still valid
        structure_valid = True
        if has_choch:
            # CHOCH plans need current structure to match
            if direction == "BUY" and xau_structure_type != "choch_bull":
                structure_valid = False
            elif direction == "SELL" and xau_structure_type != "choch_bear":
                structure_valid = False
        
        if price_near is None:
            # Structure-based plan
            if direction_conflict:
                xau_conflicting.append(plan)
                print(f"   {plan_id}: {direction} ({status}) - CONFLICT: Plan {direction} but structure is {xau_price_structure}")
            elif not structure_valid:
                xau_obsolete.append(plan)
                print(f"   {plan_id}: {direction} ({status}) - Structure condition no longer valid")
            else:
                xau_viable.append(plan)
                structure_type = "CHOCH" if has_choch else "BOS" if has_bos else "Order Block" if has_order_block else "Structure-based"
                print(f"   {plan_id}: {direction} ({status}) - {structure_type} (viable)")
        else:
            # Price-based plan
            price_diff = abs(xau_price - price_near)
            price_diff_pct = (price_diff / xau_price * 100) if xau_price > 0 else 0
            
            if direction_conflict:
                xau_conflicting.append(plan)
                print(f"   {plan_id}: {direction} ({status}) - CONFLICT: Plan {direction} but structure is {xau_price_structure} (Target: ${price_near:.2f}, Diff: ${price_diff:.2f})")
            elif price_diff <= tolerance:
                xau_viable.append(plan)
                print(f"   {plan_id}: {direction} ({status}) - Price within range (${price_near:.2f} ± {tolerance})")
            elif price_diff <= tolerance * 2:
                xau_at_risk.append(plan)
                print(f"   {plan_id}: {direction} ({status}) - Price near range (${price_near:.2f}, diff: ${price_diff:.2f})")
            else:
                xau_obsolete.append(plan)
                print(f"   {plan_id}: {direction} ({status}) - Price far from target (${price_near:.2f}, diff: ${price_diff:.2f})")
    
    # Analyze BTC plans
    print("\n4.2 BTCUSD Plans Viability:")
    print("-" * 80)
    
    btc_viable = []
    btc_at_risk = []
    btc_obsolete = []
    btc_conflicting = []
    
    for plan in btc_plans:
        plan_id = plan.get("plan_id", "N/A")
        direction = plan.get("direction", "N/A")
        status = plan.get("status", "N/A")
        conditions = plan.get("conditions", {})
        
        price_near = conditions.get("price_near")
        tolerance = conditions.get("tolerance", 0)
        
        # Check structure conditions
        has_choch = conditions.get("choch_bull") or conditions.get("choch_bear")
        has_bos = conditions.get("bos_bull") or conditions.get("bos_bear")
        has_order_block = conditions.get("order_block")
        has_liquidity_sweep = conditions.get("liquidity_sweep")
        has_rejection_wick = conditions.get("rejection_wick")
        
        # Check if plan direction conflicts with current structure
        direction_conflict = False
        if direction == "BUY" and btc_price_structure == "LOWER_LOW":
            direction_conflict = True
        elif direction == "SELL" and btc_price_structure == "HIGHER_HIGH":
            direction_conflict = True
        
        # Check if structure conditions are still valid
        structure_valid = True
        if has_choch:
            # CHOCH plans need current structure to match
            if direction == "BUY" and btc_structure_type != "choch_bull":
                structure_valid = False
            elif direction == "SELL" and btc_structure_type != "choch_bear":
                structure_valid = False
        
        if price_near is None:
            # Structure-based plan
            if direction_conflict:
                btc_conflicting.append(plan)
                print(f"   {plan_id}: {direction} ({status}) - CONFLICT: Plan {direction} but structure is {btc_price_structure}")
            elif not structure_valid:
                btc_obsolete.append(plan)
                print(f"   {plan_id}: {direction} ({status}) - Structure condition no longer valid")
            else:
                btc_viable.append(plan)
                structure_type = "CHOCH" if has_choch else "BOS" if has_bos else "Order Block" if has_order_block else "Structure-based"
                print(f"   {plan_id}: {direction} ({status}) - {structure_type} (viable)")
        else:
            # Price-based plan
            price_diff = abs(btc_price - price_near)
            price_diff_pct = (price_diff / btc_price * 100) if btc_price > 0 else 0
            
            if direction_conflict:
                btc_conflicting.append(plan)
                print(f"   {plan_id}: {direction} ({status}) - CONFLICT: Plan {direction} but structure is {btc_price_structure} (Target: ${price_near:.2f}, Diff: ${price_diff:.2f})")
            elif price_diff <= tolerance:
                btc_viable.append(plan)
                print(f"   {plan_id}: {direction} ({status}) - Price within range (${price_near:.2f} ± {tolerance})")
            elif price_diff <= tolerance * 2:
                btc_at_risk.append(plan)
                print(f"   {plan_id}: {direction} ({status}) - Price near range (${price_near:.2f}, diff: ${price_diff:.2f})")
            else:
                btc_obsolete.append(plan)
                print(f"   {plan_id}: {direction} ({status}) - Price far from target (${price_near:.2f}, diff: ${price_diff:.2f})")
    
    # Step 5: Summary and Recommendations
    print("\n" + "=" * 80)
    print("STEP 5: SUMMARY AND RECOMMENDATIONS")
    print("=" * 80)
    
    print(f"\nXAUUSD Plans:")
    print(f"   Viable: {len(xau_viable)}")
    print(f"   At Risk: {len(xau_at_risk)}")
    print(f"   Conflicting: {len(xau_conflicting)}")
    print(f"   Obsolete: {len(xau_obsolete)}")
    
    print(f"\nBTCUSD Plans:")
    print(f"   Viable: {len(btc_viable)}")
    print(f"   At Risk: {len(btc_at_risk)}")
    print(f"   Conflicting: {len(btc_conflicting)}")
    print(f"   Obsolete: {len(btc_obsolete)}")
    
    # Recommendations
    print(f"\nRECOMMENDATIONS:")
    print("-" * 80)
    
    if xau_conflicting:
        print(f"\nXAUUSD - URGENT: Cancel Conflicting Plans ({len(xau_conflicting)} plan(s)):")
        print(f"   These plans conflict with current market structure and should be cancelled immediately.")
        for plan in xau_conflicting:
            plan_id = plan.get("plan_id", "N/A")
            direction = plan.get("direction", "N/A")
            conditions = plan.get("conditions", {})
            price_near = conditions.get("price_near", 0)
            if price_near:
                price_diff = abs(xau_price - price_near)
                print(f"   - {plan_id} ({direction}) - Target: ${price_near:.2f}, Current: ${xau_price:.2f}, Structure: {xau_price_structure}")
            else:
                print(f"   - {plan_id} ({direction}) - Structure: {xau_price_structure}")
    
    if btc_conflicting:
        print(f"\nBTCUSD - URGENT: Cancel Conflicting Plans ({len(btc_conflicting)} plan(s)):")
        print(f"   These plans conflict with current market structure and should be cancelled immediately.")
        for plan in btc_conflicting:
            plan_id = plan.get("plan_id", "N/A")
            direction = plan.get("direction", "N/A")
            conditions = plan.get("conditions", {})
            price_near = conditions.get("price_near", 0)
            if price_near:
                price_diff = abs(btc_price - price_near)
                print(f"   - {plan_id} ({direction}) - Target: ${price_near:.2f}, Current: ${btc_price:.2f}, Structure: {btc_price_structure}")
            else:
                print(f"   - {plan_id} ({direction}) - Structure: {btc_price_structure}")
    
    if xau_obsolete:
        print(f"\nXAUUSD - Consider Cancelling ({len(xau_obsolete)} plan(s)):")
        for plan in xau_obsolete:
            plan_id = plan.get("plan_id", "N/A")
            direction = plan.get("direction", "N/A")
            conditions = plan.get("conditions", {})
            price_near = conditions.get("price_near", 0)
            price_diff = abs(xau_price - price_near)
            print(f"   - {plan_id} ({direction}) - Target: ${price_near:.2f}, Current: ${xau_price:.2f}, Diff: ${price_diff:.2f}")
    
    if btc_obsolete:
        print(f"\nBTCUSD - Consider Cancelling ({len(btc_obsolete)} plan(s)):")
        for plan in btc_obsolete:
            plan_id = plan.get("plan_id", "N/A")
            direction = plan.get("direction", "N/A")
            conditions = plan.get("conditions", {})
            price_near = conditions.get("price_near", 0)
            price_diff = abs(btc_price - price_near)
            print(f"   - {plan_id} ({direction}) - Target: ${price_near:.2f}, Current: ${btc_price:.2f}, Diff: ${price_diff:.2f}")
    
    if xau_at_risk:
        print(f"\nXAUUSD - Monitor Closely ({len(xau_at_risk)} plan(s)):")
        for plan in xau_at_risk:
            plan_id = plan.get("plan_id", "N/A")
            direction = plan.get("direction", "N/A")
            conditions = plan.get("conditions", {})
            price_near = conditions.get("price_near", 0)
            price_diff = abs(xau_price - price_near)
            print(f"   - {plan_id} ({direction}) - Target: ${price_near:.2f}, Current: ${xau_price:.2f}, Diff: ${price_diff:.2f}")
    
    if btc_at_risk:
        print(f"\nBTCUSD - Monitor Closely ({len(btc_at_risk)} plan(s)):")
        for plan in btc_at_risk:
            plan_id = plan.get("plan_id", "N/A")
            direction = plan.get("direction", "N/A")
            conditions = plan.get("conditions", {})
            price_near = conditions.get("price_near", 0)
            price_diff = abs(btc_price - price_near)
            print(f"   - {plan_id} ({direction}) - Target: ${price_near:.2f}, Current: ${btc_price:.2f}, Diff: ${price_diff:.2f}")
    
    if not xau_obsolete and not btc_obsolete:
        print(f"\nAll plans appear viable for current market conditions.")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(analyze_and_review_plans())
