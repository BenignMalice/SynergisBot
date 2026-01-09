"""
Analyze XAU and BTC and create auto-execution plans for appropriate strategies
Uses the new system-wide improvements (R:R validation, session blocking, order flow, etc.)
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def analyze_and_create_plans():
    """Analyze XAU and BTC, then create appropriate auto-execution plans"""
    bridge = get_bridge()
    
    print("=" * 80)
    print("ANALYZING XAU & BTC AND CREATING AUTO-EXECUTION PLANS")
    print("=" * 80)
    print("\nUsing new system-wide improvements:")
    print("  - R:R validation (min 1.5:1)")
    print("  - Session blocking (XAU blocks Asian session by default)")
    print("  - Order flow conditions for BTC")
    print("  - MTF alignment conditions")
    print("  - News blackout checks")
    print("  - Execution quality validation")
    print("=" * 80)
    
    symbols = ["XAUUSDc", "BTCUSDc"]
    all_created_plans = []
    
    for symbol in symbols:
        print(f"\n{'='*80}")
        print(f"ANALYZING {symbol}")
        print(f"{'='*80}")
        
        # Step 1: Full Analysis
        print(f"\n1. Running Full Analysis...")
        print("-" * 80)
        
        analysis = await bridge.registry.execute("moneybot.analyse_symbol_full", {
            "symbol": symbol
        })
        
        data = analysis.get("data", {})
        summary = analysis.get("summary", "")
        
        # Extract key data
        current_price = data.get("current_price", 0)
        confluence_score = data.get("confluence_score", 0)
        
        # Get SMC structure data
        smc = data.get("smc", {})
        recommendation = smc.get("recommendation", {}) if isinstance(smc, dict) else {}
        market_bias = recommendation.get("market_bias", {}) if isinstance(recommendation, dict) else {}
        trend = market_bias.get("trend", "NEUTRAL") if isinstance(market_bias, dict) else "NEUTRAL"
        
        # Get volatility regime
        volatility_regime = data.get("volatility_regime", {})
        regime = volatility_regime.get("regime", "UNKNOWN") if isinstance(volatility_regime, dict) else "UNKNOWN"
        
        # Get session info
        session = data.get("session", {})
        session_name = session.get("name", "UNKNOWN") if isinstance(session, dict) else "UNKNOWN"
        
        # Get BTC order flow (if BTC)
        btc_order_flow = None
        if "BTC" in symbol:
            btc_order_flow = data.get("btc_order_flow_metrics", {})
        
        print(f"   Current Price: ${current_price:,.2f}")
        print(f"   Confluence Score: {confluence_score}/100")
        print(f"   Trend: {trend}")
        print(f"   Volatility Regime: {regime}")
        print(f"   Session: {session_name}")
        
        if btc_order_flow:
            delta = btc_order_flow.get("delta_volume", 0)
            cvd_trend = btc_order_flow.get("cvd_trend", {})
            cvd_direction = cvd_trend.get("trend", "UNKNOWN") if isinstance(cvd_trend, dict) else "UNKNOWN"
            print(f"   BTC Order Flow:")
            print(f"      Delta Volume: {delta}")
            print(f"      CVD Trend: {cvd_direction}")
        
        # Step 2: Determine Strategy
        print(f"\n2. Determining Appropriate Strategies...")
        print("-" * 80)
        
        plans_to_create = []
        
        # Strategy selection logic
        if "BTC" in symbol:
            # BTC strategies
            if trend in ["BULLISH", "BULL"]:
                # Bullish trend - look for pullback entries
                entry_buy = current_price * 0.995  # 0.5% below current
                sl_buy = entry_buy * 0.99  # 1% below entry
                tp_buy = entry_buy * 1.02  # 2% above entry (R:R = 2:1)
                
                # Check R:R
                sl_distance = abs(entry_buy - sl_buy)
                tp_distance = abs(tp_buy - entry_buy)
                rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
                
                if rr_ratio >= 1.5:  # Meets minimum R:R
                    conditions_buy = {
                        "price_near": entry_buy,
                        "tolerance": current_price * 0.003,  # 0.3% tolerance for BTC
                        "choch_bull": True,
                        "timeframe": "M5",
                        "min_confluence": 65
                    }
                    
                    # Add order flow conditions if available
                    if btc_order_flow:
                        delta = btc_order_flow.get("delta_volume", 0)
                        if delta > 0:
                            conditions_buy["delta_positive"] = True
                        cvd_trend = btc_order_flow.get("cvd_trend", {})
                        if isinstance(cvd_trend, dict) and cvd_trend.get("trend") == "rising":
                            conditions_buy["cvd_rising"] = True
                    
                    plans_to_create.append({
                        "direction": "BUY",
                        "entry": entry_buy,
                        "stop_loss": sl_buy,
                        "take_profit": tp_buy,
                        "conditions": conditions_buy,
                        "strategy_type": "trend_continuation_pullback",
                        "reasoning": f"Bullish trend continuation pullback. R:R = {rr_ratio:.2f}:1. Confluence: {confluence_score}/100."
                    })
            
            if trend in ["BEARISH", "BEAR"]:
                # Bearish trend - look for pullback entries
                entry_sell = current_price * 1.005  # 0.5% above current
                sl_sell = entry_sell * 1.01  # 1% above entry
                tp_sell = entry_sell * 0.98  # 2% below entry (R:R = 2:1)
                
                # Check R:R
                sl_distance = abs(entry_sell - sl_sell)
                tp_distance = abs(entry_sell - tp_sell)
                rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
                
                if rr_ratio >= 1.5:  # Meets minimum R:R
                    conditions_sell = {
                        "price_near": entry_sell,
                        "tolerance": current_price * 0.003,  # 0.3% tolerance for BTC
                        "choch_bear": True,
                        "timeframe": "M5",
                        "min_confluence": 65
                    }
                    
                    # Add order flow conditions if available
                    if btc_order_flow:
                        delta = btc_order_flow.get("delta_volume", 0)
                        if delta < 0:
                            conditions_sell["delta_negative"] = True
                        cvd_trend = btc_order_flow.get("cvd_trend", {})
                        if isinstance(cvd_trend, dict) and cvd_trend.get("trend") == "falling":
                            conditions_sell["cvd_falling"] = True
                    
                    plans_to_create.append({
                        "direction": "SELL",
                        "entry": entry_sell,
                        "stop_loss": sl_sell,
                        "take_profit": tp_sell,
                        "conditions": conditions_sell,
                        "strategy_type": "trend_continuation_pullback",
                        "reasoning": f"Bearish trend continuation pullback. R:R = {rr_ratio:.2f}:1. Confluence: {confluence_score}/100."
                    })
        
        elif "XAU" in symbol:
            # XAU strategies
            if trend in ["BULLISH", "BULL"]:
                # Bullish trend - pullback entry
                entry_buy = current_price * 0.998  # 0.2% below current
                sl_buy = entry_buy - 10  # 10 points below entry
                tp_buy = entry_buy + 20  # 20 points above entry (R:R = 2:1)
                
                # Check R:R
                sl_distance = abs(entry_buy - sl_buy)
                tp_distance = abs(tp_buy - entry_buy)
                rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
                
                if rr_ratio >= 1.5:  # Meets minimum R:R
                    conditions_buy = {
                        "price_near": entry_buy,
                        "tolerance": 5.0,  # 5 points tolerance for XAU
                        "choch_bull": True,
                        "timeframe": "M5",
                        "min_confluence": 70,
                        "require_active_session": True  # Default True for XAU (blocks Asian session)
                    }
                    
                    plans_to_create.append({
                        "direction": "BUY",
                        "entry": entry_buy,
                        "stop_loss": sl_buy,
                        "take_profit": tp_buy,
                        "conditions": conditions_buy,
                        "strategy_type": "trend_continuation_pullback",
                        "reasoning": f"Bullish trend continuation pullback. R:R = {rr_ratio:.2f}:1. Confluence: {confluence_score}/100. Session blocking enabled."
                    })
            
            if trend in ["BEARISH", "BEAR"]:
                # Bearish trend - pullback entry
                entry_sell = current_price * 1.002  # 0.2% above current
                sl_sell = entry_sell + 10  # 10 points above entry
                tp_sell = entry_sell - 20  # 20 points below entry (R:R = 2:1)
                
                # Check R:R
                sl_distance = abs(entry_sell - sl_sell)
                tp_distance = abs(entry_sell - tp_sell)
                rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
                
                if rr_ratio >= 1.5:  # Meets minimum R:R
                    conditions_sell = {
                        "price_near": entry_sell,
                        "tolerance": 5.0,  # 5 points tolerance for XAU
                        "choch_bear": True,
                        "timeframe": "M5",
                        "min_confluence": 70,
                        "require_active_session": True  # Default True for XAU (blocks Asian session)
                    }
                    
                    plans_to_create.append({
                        "direction": "SELL",
                        "entry": entry_sell,
                        "stop_loss": sl_sell,
                        "take_profit": tp_sell,
                        "conditions": conditions_sell,
                        "strategy_type": "trend_continuation_pullback",
                        "reasoning": f"Bearish trend continuation pullback. R:R = {rr_ratio:.2f}:1. Confluence: {confluence_score}/100. Session blocking enabled."
                    })
        
        # Step 3: Create Plans
        if plans_to_create:
            print(f"\n3. Creating {len(plans_to_create)} Plan(s)...")
            print("-" * 80)
            
            for i, plan_data in enumerate(plans_to_create, 1):
                print(f"\n   Plan {i}: {plan_data['direction']} @ ${plan_data['entry']:.2f}")
                print(f"      SL: ${plan_data['stop_loss']:.2f}, TP: ${plan_data['take_profit']:.2f}")
                
                # Calculate R:R for display
                sl_dist = abs(plan_data['entry'] - plan_data['stop_loss'])
                tp_dist = abs(plan_data['take_profit'] - plan_data['entry'])
                rr = tp_dist / sl_dist if sl_dist > 0 else 0
                print(f"      R:R = {rr:.2f}:1")
                print(f"      Strategy: {plan_data['strategy_type']}")
                
                try:
                    result = await bridge.registry.execute("moneybot.create_auto_trade_plan", {
                        "symbol": symbol,
                        "direction": plan_data["direction"],
                        "entry": plan_data["entry"],
                        "stop_loss": plan_data["stop_loss"],
                        "take_profit": plan_data["take_profit"],
                        "conditions": plan_data["conditions"],
                        "strategy_type": plan_data["strategy_type"],
                        "reasoning": plan_data["reasoning"],
                        "expires_hours": 24
                    })
                    
                    plan_id = result.get("data", {}).get("plan_id", "unknown")
                    all_created_plans.append({
                        "symbol": symbol,
                        "plan_id": plan_id,
                        "direction": plan_data["direction"],
                        "entry": plan_data["entry"]
                    })
                    print(f"      [OK] Created: {plan_id}")
                    
                except Exception as e:
                    print(f"      [ERROR] Failed to create plan: {e}")
        else:
            print(f"\n3. No suitable plans to create")
            print(f"   Reason: Market conditions not suitable for plan creation")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"\nTotal Plans Created: {len(all_created_plans)}")
    
    if all_created_plans:
        print("\nCreated Plans:")
        for plan in all_created_plans:
            print(f"  - {plan['symbol']} {plan['direction']} @ ${plan['entry']:.2f} (ID: {plan['plan_id']})")
    
    print(f"\n{'='*80}")
    print("ANALYSIS & PLAN CREATION COMPLETE")
    print(f"{'='*80}")

if __name__ == "__main__":
    asyncio.run(analyze_and_create_plans())
