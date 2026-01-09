"""
Analyze BTC and create auto-execution plans for multiple viable strategies
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def analyze_and_create_plans():
    """Analyze BTC and create plans for viable strategies"""
    bridge = get_bridge()
    
    print("=" * 80)
    print("BTC ANALYSIS & STRATEGY PLAN CREATION")
    print("=" * 80)
    
    # Step 1: Full BTC Analysis
    print("\n1. ANALYZING BTCUSD...")
    print("-" * 80)
    
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
    
    # Get SMC data
    smc = btc_data.get("smc", {})
    choch_detected = smc.get("choch_detected", False)
    bos_detected = smc.get("bos_detected", False)
    
    # Get recommendation
    recommendation = btc_data.get("recommendation", {})
    action = recommendation.get("action", "N/A")
    confidence = recommendation.get("confidence", 0)
    
    print(f"   Current Price: ${btc_price:,.2f}")
    print(f"   Trend: {btc_trend}")
    print(f"   Structure Type: {btc_structure_type}")
    print(f"   Price Structure: {btc_price_structure}")
    print(f"   Confluence Score: {btc_confluence}/100")
    print(f"   Volatility: {btc_volatility}")
    print(f"   Momentum: {btc_momentum}")
    print(f"   CHOCH Detected: {choch_detected}")
    print(f"   BOS Detected: {bos_detected}")
    print(f"   Recommendation: {action} (Confidence: {confidence}%)")
    
    # Step 2: Get M1 microstructure for entry levels
    print("\n2. GETTING M1 MICROSTRUCTURE...")
    print("-" * 80)
    
    m1_data = btc_data.get("m1_microstructure", {})
    if m1_data and m1_data.get("available"):
        order_blocks = m1_data.get("order_blocks", [])
        liquidity_zones = m1_data.get("liquidity_zones", [])
        rejection_wicks = m1_data.get("rejection_wicks", [])
        
        print(f"   Order Blocks: {len(order_blocks)}")
        print(f"   Liquidity Zones: {len(liquidity_zones)}")
        print(f"   Rejection Wicks: {len(rejection_wicks)}")
        
        # Get nearest order blocks
        if order_blocks:
            print(f"\n   Nearest Order Blocks:")
            for ob in order_blocks[:3]:  # Show top 3
                ob_type = ob.get("type", "N/A")
                ob_price = ob.get("price", 0)
                ob_strength = ob.get("strength", 0)
                print(f"      - {ob_type}: ${ob_price:,.2f} (Strength: {ob_strength})")
    
    # Step 3: Identify viable strategies based on current market
    print("\n3. IDENTIFYING VIABLE STRATEGIES...")
    print("-" * 80)
    
    strategies = []
    
    # Get volatility regime
    volatility_regime = btc_data.get("volatility_regime", {})
    regime = volatility_regime.get("regime", "N/A")
    
    # Get decision data
    decision = btc_data.get("decision", {})
    decision_direction = decision.get("direction", "N/A")
    decision_entry = decision.get("entry", btc_price)
    decision_sl = decision.get("stop_loss", 0)
    decision_tp = decision.get("take_profit", 0)
    
    # Strategy 1: Order Block Plans (always create if order blocks detected)
    if order_blocks and len(order_blocks) > 0:
        print(f"   Found {len(order_blocks)} order blocks - creating order block plans")
        # Create order block plans for both directions
        strategies.append({
            "plan_type": "order_block",
            "direction": "BUY",
            "price_near": btc_price * 0.998,  # Slightly below current
            "tolerance": 200,
            "strategy_type": "order_block_rejection",
            "reason": "Bullish order block retest opportunity"
        })
        
        strategies.append({
            "plan_type": "order_block",
            "direction": "SELL",
            "price_near": btc_price * 1.002,  # Slightly above current
            "tolerance": 200,
            "strategy_type": "order_block_rejection",
            "reason": "Bearish order block retest opportunity"
        })
    
    # Strategy 2: Range Scalp Plans (if volatility is stable/choppy)
    if regime in ["STABLE", "FRAGMENTED_CHOP", "TRANSITIONAL"]:
        print(f"   Volatility regime: {regime} - creating range scalp plans")
        support_level = btc_price * 0.995  # 0.5% below
        resistance_level = btc_price * 1.005  # 0.5% above
        
        strategies.append({
            "plan_type": "range_scalp",
            "direction": "BUY",
            "price_near": support_level,
            "tolerance": 300,
            "strategy_type": "mean_reversion_range_scalp",
            "reason": f"Range scalp BUY at support ${support_level:,.2f}"
        })
        
        strategies.append({
            "plan_type": "range_scalp",
            "direction": "SELL",
            "price_near": resistance_level,
            "tolerance": 300,
            "strategy_type": "mean_reversion_range_scalp",
            "reason": f"Range scalp SELL at resistance ${resistance_level:,.2f}"
        })
    
    # Strategy 3: Rejection Wick Plans (if rejection wicks detected)
    if rejection_wicks and len(rejection_wicks) > 0:
        print(f"   Found {len(rejection_wicks)} rejection wicks - creating rejection wick plans")
        strategies.append({
            "plan_type": "rejection_wick",
            "direction": "BUY",
            "price_near": btc_price * 0.997,
            "tolerance": 250,
            "strategy_type": "liquidity_sweep_reversal",
            "reason": "Bullish rejection wick opportunity"
        })
        
        strategies.append({
            "plan_type": "rejection_wick",
            "direction": "SELL",
            "price_near": btc_price * 1.003,
            "tolerance": 250,
            "strategy_type": "liquidity_sweep_reversal",
            "reason": "Bearish rejection wick opportunity"
        })
    
    # Strategy 4: CHOCH Plans (if structure supports)
    if choch_detected or bos_detected:
        print(f"   CHOCH/BOS detected - creating structure-based plans")
        if decision_direction == "BUY" or btc_price_structure == "LOWER_LOW":
            strategies.append({
                "plan_type": "choch",
                "direction": "BUY",
                "price_near": btc_price * 0.998,
                "tolerance": 200,
                "reason": "CHOCH/BOS bullish structure confirmation"
            })
        
        if decision_direction == "SELL" or btc_price_structure == "HIGHER_HIGH":
            strategies.append({
                "plan_type": "choch",
                "direction": "SELL",
                "price_near": btc_price * 1.002,
                "tolerance": 200,
                "reason": "CHOCH/BOS bearish structure confirmation"
            })
    
    # Strategy 5: Generic auto-trade plans at key levels
    if len(strategies) < 4:  # If we don't have enough strategies, add generic ones
        print(f"   Adding generic auto-trade plans at key levels")
        # Support level
        strategies.append({
            "plan_type": "auto_trade",
            "direction": "BUY",
            "price_near": btc_price * 0.992,  # 0.8% below
            "tolerance": 400,
            "strategy_type": "trend_continuation_pullback",
            "reason": f"BUY at support level ${btc_price * 0.992:,.2f}"
        })
        
        # Resistance level
        strategies.append({
            "plan_type": "auto_trade",
            "direction": "SELL",
            "price_near": btc_price * 1.008,  # 0.8% above
            "tolerance": 400,
            "strategy_type": "trend_continuation_pullback",
            "reason": f"SELL at resistance level ${btc_price * 1.008:,.2f}"
        })
    
    print(f"\n   Identified {len(strategies)} viable strategy(ies):")
    for i, strat in enumerate(strategies, 1):
        plan_type = strat.get('plan_type', 'auto_trade')
        print(f"      {i}. {plan_type.upper()}: {strat['direction']} - {strat['reason']}")
        if 'price_near' in strat:
            print(f"         Target: ${strat['price_near']:,.2f} ± ${strat['tolerance']}")
    
    # Step 4: Create plans using batch operation
    if not strategies:
        print("\n   ⚠️  No viable strategies identified based on current market conditions.")
        print("   Market may be too choppy or lacking clear structure.")
        return
    
    print("\n4. CREATING AUTO-EXECUTION PLANS (BATCH)...")
    print("-" * 80)
    
    # Prepare plans for batch creation
    plans_to_create = []
    
    for strat in strategies:
        plan_obj = {
            "plan_type": strat.get("plan_type", "auto_trade"),
            "symbol": "BTCUSDc",  # Must include symbol in each plan
            "direction": strat["direction"],
            "price_near": strat.get("price_near", btc_price),
            "tolerance": strat.get("tolerance", 200),
        }
        
        # Add conditions for strategy_type if specified
        if "strategy_type" in strat:
            plan_obj["conditions"] = {
                "strategy_type": strat["strategy_type"]
            }
        
        # Add entry, SL, TP if we have decision data
        if decision_entry and decision_entry != btc_price:
            plan_obj["entry"] = decision_entry
        
        if decision_sl:
            plan_obj["stop_loss"] = decision_sl
        
        if decision_tp:
            plan_obj["take_profit"] = decision_tp
        
        plans_to_create.append(plan_obj)
    
    print(f"   Creating {len(plans_to_create)} plans in batch...")
    
    # Create plans individually (more reliable)
    created_plans = []
    failed_plans = []
    
    for i, plan_obj in enumerate(plans_to_create, 1):
        plan_type = plan_obj.get("plan_type", "auto_trade")
        direction = plan_obj.get("direction", "N/A")
        price_near = plan_obj.get("price_near", btc_price)
        tolerance = plan_obj.get("tolerance", 200)
        
        # Calculate entry, SL, TP based on direction and price_near
        if direction == "BUY":
            entry_price = price_near
            stop_loss = price_near - (tolerance * 1.5)  # SL 1.5x tolerance below entry
            take_profit = price_near + (tolerance * 3)  # TP 3x tolerance above entry
        else:  # SELL
            entry_price = price_near
            stop_loss = price_near + (tolerance * 1.5)  # SL 1.5x tolerance above entry
            take_profit = price_near - (tolerance * 3)  # TP 3x tolerance below entry
        
        try:
            # Create plan based on type
            if plan_type == "order_block":
                result = await bridge.registry.execute("moneybot.create_order_block_plan", {
                    "symbol": "BTCUSDc",
                    "direction": direction,
                    "entry": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "price_near": price_near,
                    "tolerance": tolerance,
                    "order_block_type": "auto"
                })
            elif plan_type == "rejection_wick":
                result = await bridge.registry.execute("moneybot.create_rejection_wick_plan", {
                    "symbol": "BTCUSDc",
                    "direction": direction,
                    "entry": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "price_near": price_near,
                    "tolerance": tolerance
                })
            elif plan_type == "range_scalp":
                result = await bridge.registry.execute("moneybot.create_range_scalp_plan", {
                    "symbol": "BTCUSDc",
                    "direction": direction,
                    "entry": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "price_near": price_near,
                    "tolerance": tolerance
                })
            elif plan_type == "choch":
                result = await bridge.registry.execute("moneybot.create_choch_plan", {
                    "symbol": "BTCUSDc",
                    "direction": direction,
                    "entry": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "conditions": {
                        "price_near": price_near,
                        "tolerance": tolerance
                    }
                })
            else:  # auto_trade
                conditions = {
                    "price_near": price_near,
                    "tolerance": tolerance
                }
                if "strategy_type" in plan_obj.get("conditions", {}):
                    conditions["strategy_type"] = plan_obj["conditions"]["strategy_type"]
                
                result = await bridge.registry.execute("moneybot.create_auto_trade_plan", {
                    "symbol": "BTCUSDc",
                    "direction": direction,
                    "entry": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "conditions": conditions
                })
            
            # Check response structure
            plan_data = result.get("data", {})
            plan_id = plan_data.get("plan_id") or result.get("plan_id")
            
            if plan_id and plan_id != "N/A":
                created_plans.append({
                    "plan_id": plan_id,
                    "plan_type": plan_type,
                    "direction": direction
                })
                print(f"   ✅ [{i}/{len(plans_to_create)}] Created: {plan_id} ({plan_type} - {direction})")
            else:
                failed_plans.append({"plan_type": plan_type, "direction": direction, "error": "No plan_id returned"})
                print(f"   ❌ [{i}/{len(plans_to_create)}] Failed: {plan_type} - {direction} (no plan_id)")
                if i == 1:  # Show full result for debugging
                    print(f"      Full result: {result}")
        
        except Exception as e:
            failed_plans.append({"plan_type": plan_type, "direction": direction, "error": str(e)})
            print(f"   ❌ [{i}/{len(plans_to_create)}] Error: {plan_type} - {direction}: {str(e)}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print(f"\nPlans Created: {len(created_plans)}/{len(strategies)}")
    
    if created_plans:
        print(f"\n✅ Successfully Created Plans:")
        for plan in created_plans:
            print(f"   - {plan['plan_id']}: {plan['plan_type']} ({plan['direction']})")
    
    if failed_plans:
        print(f"\n❌ Failed to Create Plans:")
        for strat in failed_plans:
            if isinstance(strat, dict):
                plan_type = strat.get('plan_type', strat.get('type', 'N/A'))
                direction = strat.get('direction', 'N/A')
                error = strat.get('error', '')
                print(f"   - {plan_type} ({direction})" + (f": {error}" if error else ""))
            else:
                print(f"   - {str(strat)}")
    
    print(f"\nCurrent BTC Price: ${btc_price:,.2f}")
    print(f"Total Active BTC Plans: {len(created_plans)} new plans created")

if __name__ == "__main__":
    asyncio.run(analyze_and_create_plans())
