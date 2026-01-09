"""
Create auto-execution plans based on market direction analysis
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def create_direction_based_plans():
    """Analyze market direction and create appropriate plans"""
    bridge = get_bridge()
    
    print("=" * 80)
    print("CREATING DIRECTION-BASED AUTO-EXECUTION PLANS")
    print("=" * 80)
    
    symbols = ["BTCUSDc", "XAUUSDc"]
    
    created_plans = []
    
    for symbol in symbols:
        print(f"\n{'='*80}")
        print(f"ANALYZING {symbol}")
        print(f"{'='*80}")
        
        # Get market analysis
        print(f"\n1. Analyzing Market Direction...")
        print("-" * 80)
        
        analysis = await bridge.registry.execute("moneybot.analyse_symbol_full", {
            "symbol": symbol
        })
        
        data = analysis.get("data", {})
        current_price = data.get("current_price", 0)
        
        # Extract structure data
        structure = data.get("smc", {})
        structure_type = "N/A"
        if isinstance(structure, dict):
            structure_type = structure.get("structure_type", "N/A")
            if structure_type == "N/A":
                recommendation = structure.get("recommendation", {})
                if isinstance(recommendation, dict):
                    market_bias = recommendation.get("market_bias", {})
                    if isinstance(market_bias, dict):
                        bias_trend = market_bias.get("trend", "NEUTRAL")
                        if "BULL" in str(bias_trend).upper():
                            structure_type = "BULLISH"
                        elif "BEAR" in str(bias_trend).upper():
                            structure_type = "BEARISH"
        
        # Get confluence
        confluence = data.get("confluence_score", 0)
        if not confluence:
            confluence_data = data.get("confluence", {})
            if isinstance(confluence_data, dict):
                confluence = confluence_data.get("score", 0)
        
        # Get volatility
        volatility_regime = data.get("volatility_regime", {})
        regime = "UNKNOWN"
        if isinstance(volatility_regime, dict):
            regime = volatility_regime.get("regime", "UNKNOWN")
        
        volatility_metrics = data.get("volatility_metrics", {})
        atr = volatility_metrics.get("atr", 0) if isinstance(volatility_metrics, dict) else 0
        
        print(f"   Current Price: ${current_price:,.2f}")
        print(f"   Structure: {structure_type}")
        print(f"   Confluence: {confluence}/100")
        print(f"   Volatility Regime: {regime}")
        print(f"   ATR: {atr:.2f}")
        
        # Determine direction and create plans
        print(f"\n2. Creating Plans Based on Analysis...")
        print("-" * 80)
        
        # Calculate tolerance based on symbol
        if "BTC" in symbol:
            tolerance = 200.0
            sl_multiplier = 1.5  # 1.5x tolerance for stop loss
            tp_multiplier = 3.0  # 3x tolerance for take profit
        else:  # XAU
            tolerance = 5.0
            sl_multiplier = 1.5
            tp_multiplier = 3.0
        
        # Determine plans to create based on structure
        plans_to_create = []
        
        if structure_type == "BEARISH":
            # Create SELL plan
            entry = current_price
            stop_loss = entry + (tolerance * sl_multiplier)
            take_profit = entry - (tolerance * tp_multiplier)
            
            plans_to_create.append({
                "direction": "SELL",
                "entry": entry,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "reasoning": f"BEARISH structure detected - SELL opportunity"
            })
            
        elif structure_type == "BULLISH":
            # Create BUY plan
            entry = current_price
            stop_loss = entry - (tolerance * sl_multiplier)
            take_profit = entry + (tolerance * tp_multiplier)
            
            plans_to_create.append({
                "direction": "BUY",
                "entry": entry,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "reasoning": f"BULLISH structure detected - BUY opportunity"
            })
            
        else:
            # NEUTRAL - create both BUY and SELL plans with tighter conditions
            # BUY plan
            entry_buy = current_price
            stop_loss_buy = entry_buy - (tolerance * sl_multiplier)
            take_profit_buy = entry_buy + (tolerance * tp_multiplier)
            
            plans_to_create.append({
                "direction": "BUY",
                "entry": entry_buy,
                "stop_loss": stop_loss_buy,
                "take_profit": take_profit_buy,
                "reasoning": f"NEUTRAL structure - BUY on bullish confirmation"
            })
            
            # SELL plan
            entry_sell = current_price
            stop_loss_sell = entry_sell + (tolerance * sl_multiplier)
            take_profit_sell = entry_sell - (tolerance * tp_multiplier)
            
            plans_to_create.append({
                "direction": "SELL",
                "entry": entry_sell,
                "stop_loss": stop_loss_sell,
                "take_profit": take_profit_sell,
                "reasoning": f"NEUTRAL structure - SELL on bearish confirmation"
            })
        
        # Create plans
        for plan_config in plans_to_create:
            direction = plan_config["direction"]
            entry = plan_config["entry"]
            stop_loss = plan_config["stop_loss"]
            take_profit = plan_config["take_profit"]
            reasoning = plan_config["reasoning"]
            
            print(f"\n   Creating {direction} plan:")
            print(f"      Entry: ${entry:,.2f}")
            print(f"      Stop Loss: ${stop_loss:,.2f}")
            print(f"      Take Profit: ${take_profit:,.2f}")
            
            # Build conditions based on structure type
            conditions = {
                "price_near": entry,
                "tolerance": tolerance
            }
            
            # Add structure conditions
            if structure_type == "BEARISH" and direction == "SELL":
                conditions["order_block"] = True
                conditions["order_block_type"] = "bear"
                conditions["timeframe"] = "M5"
                conditions["min_validation_score"] = 60
                strategy_type = "order_block_rejection"
            elif structure_type == "BULLISH" and direction == "BUY":
                conditions["order_block"] = True
                conditions["order_block_type"] = "bull"
                conditions["timeframe"] = "M5"
                conditions["min_validation_score"] = 60
                strategy_type = "order_block_rejection"
            else:
                # For neutral or opposite direction, use auto_trade with rejection_wick condition
                if direction == "BUY":
                    conditions["rejection_wick"] = True
                    conditions["timeframe"] = "M5"
                    conditions["min_wick_ratio"] = 2.0
                    strategy_type = "rejection_wick"
                else:
                    conditions["rejection_wick"] = True
                    conditions["timeframe"] = "M5"
                    conditions["min_wick_ratio"] = 2.0
                    strategy_type = "rejection_wick"
            
            # Add accuracy filters
            if confluence > 0:
                conditions["min_confluence"] = max(60, confluence - 10)  # Slightly below current
            
            conditions["volume_confirmation"] = True
            conditions["structure_confirmation"] = True
            
            # Add volatility filter if needed
            if regime == "STABLE" or (isinstance(volatility_metrics, dict) and volatility_metrics.get("atr_ratio", 1.0) < 0.8):
                conditions["min_volatility"] = 0.5
            
            try:
                # Create plan using appropriate API
                if conditions.get("order_block"):
                    result = await bridge.registry.execute("moneybot.create_order_block_plan", {
                        "symbol": symbol,
                        "direction": direction,
                        "entry": entry,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "conditions": conditions
                    })
                elif conditions.get("rejection_wick"):
                    # Use auto_trade_plan for rejection_wick with custom conditions
                    result = await bridge.registry.execute("moneybot.create_auto_trade_plan", {
                        "symbol": symbol,
                        "direction": direction,
                        "entry": entry,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "volume": 0.01,
                        "conditions": conditions,
                        "strategy_type": strategy_type,
                        "reasoning": reasoning
                    })
                else:
                    result = await bridge.registry.execute("moneybot.create_auto_trade_plan", {
                        "symbol": symbol,
                        "direction": direction,
                        "entry": entry,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "volume": 0.01,  # Auto-calculated
                        "conditions": conditions,
                        "strategy_type": strategy_type,
                        "reasoning": reasoning
                    })
                
                result_data = result.get("data", {})
                if result_data.get("success"):
                    plan_id = result_data.get("plan_id", "N/A")
                    print(f"      ✅ Plan created: {plan_id}")
                    created_plans.append({
                        "plan_id": plan_id,
                        "symbol": symbol,
                        "direction": direction,
                        "entry": entry
                    })
                else:
                    error = result_data.get("error", "Unknown error")
                    print(f"      ❌ Failed: {error}")
                    
            except Exception as e:
                print(f"      ❌ Error: {str(e)}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print(f"\n✅ Created {len(created_plans)} plan(s):")
    for plan in created_plans:
        print(f"   - {plan['plan_id']}: {plan['symbol']} {plan['direction']} @ ${plan['entry']:,.2f}")
    
    print(f"\n📊 Plan Details:")
    print(f"   - All plans include: structure confirmation, volume confirmation, confluence filter")
    print(f"   - Structure-based plans use order_block or rejection_wick conditions")
    print(f"   - Plans will only execute when all conditions align")
    
    return created_plans

if __name__ == "__main__":
    asyncio.run(create_direction_based_plans())
