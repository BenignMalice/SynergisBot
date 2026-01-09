"""
Analyze market data to determine directional probability
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def analyze_direction(symbol: str):
    """Analyze market direction for a symbol"""
    bridge = get_bridge()
    
    print("=" * 80)
    print(f"MARKET DIRECTION ANALYSIS: {symbol}")
    print("=" * 80)
    
    # Get comprehensive market analysis
    print("\n1. Fetching Market Data...")
    print("-" * 80)
    
    analysis = await bridge.registry.execute("moneybot.analyse_symbol_full", {
        "symbol": symbol
    })
    
    data = analysis.get("data", {})
    
    # Extract key metrics with fallback paths
    current_price = data.get("current_price", 0)
    
    # Try multiple paths for trend
    trend = data.get("trend", {})
    if not trend or not isinstance(trend, dict):
        smc = data.get("smc", {})
        trend = smc.get("trend", {}) if isinstance(smc, dict) else {}
        if not trend:
            # Try recommendation path
            recommendation = smc.get("recommendation", {}) if isinstance(smc, dict) else {}
            market_bias = recommendation.get("market_bias", {}) if isinstance(recommendation, dict) else {}
            if market_bias:
                trend = {
                    "direction": market_bias.get("trend", "NEUTRAL"),
                    "strength": market_bias.get("confidence", 0)
                }
    
    # Extract structure data
    structure = data.get("smc", {})
    if not structure:
        structure = {}
    
    # Try multiple paths for confluence
    confluence = data.get("confluence_score", 0)
    if not confluence or confluence == 0:
        # Try top-level confluence key
        confluence_data = data.get("confluence", {})
        if isinstance(confluence_data, dict):
            confluence = confluence_data.get("score", 0)
        elif isinstance(confluence_data, (int, float)):
            confluence = confluence_data
        
        if not confluence or confluence == 0:
            m1_micro = data.get("m1_microstructure", {})
            if isinstance(m1_micro, dict):
                confluence = m1_micro.get("confluence", 0)
        
        if not confluence or confluence == 0:
            smc = data.get("smc", {})
            if isinstance(smc, dict):
                confluence = smc.get("confluence_score", 0)
        
        # Try advanced features
        if not confluence or confluence == 0:
            advanced = data.get("advanced", {})
            if isinstance(advanced, dict):
                confluence = advanced.get("confluence_score", 0)
    
    # Extract volatility
    volatility = data.get("volatility_metrics", {})
    if not volatility:
        volatility = {}
    
    # Extract momentum
    momentum = data.get("momentum", {})
    if not momentum:
        momentum = {}
    
    # Extract macro
    macro = data.get("macro_context", {})
    if not macro:
        macro = {}
    
    print(f"   Current Price: ${current_price:,.2f}")
    print(f"   Confluence Score: {confluence}/100")
    
    # Debug: Show available keys
    print(f"\n   Available data keys: {list(data.keys())[:10]}...")
    
    # Analyze direction
    print("\n2. Directional Analysis...")
    print("-" * 80)
    
    bullish_signals = []
    bearish_signals = []
    neutral_signals = []
    
    # 1. Trend Analysis
    trend_direction = trend.get("direction", "NEUTRAL") if isinstance(trend, dict) else "NEUTRAL"
    if isinstance(trend_direction, str):
        trend_direction = trend_direction.upper()
    else:
        # Try to extract from smc.trend string
        smc_trend = structure.get("trend", "NEUTRAL") if isinstance(structure, dict) else "NEUTRAL"
        if isinstance(smc_trend, str):
            trend_direction = smc_trend.upper()
    
    trend_strength = trend.get("strength", 0) if isinstance(trend, dict) else 0
    if not trend_strength:
        trend_strength = trend.get("confidence", 0) if isinstance(trend, dict) else 0
    
    if "BULL" in trend_direction:
        bullish_signals.append(f"Trend: BULLISH (strength: {trend_strength:.1f})")
    elif "BEAR" in trend_direction:
        bearish_signals.append(f"Trend: BEARISH (strength: {trend_strength:.1f})")
    else:
        neutral_signals.append(f"Trend: NEUTRAL (strength: {trend_strength:.1f})")
    
    # 2. Structure Analysis
    structure_type = "N/A"
    if isinstance(structure, dict):
        structure_type = structure.get("structure_type", "N/A")
        if structure_type == "N/A":
            # Try recommendation path
            recommendation = structure.get("recommendation", {})
            if isinstance(recommendation, dict):
                market_bias = recommendation.get("market_bias", {})
                if isinstance(market_bias, dict):
                    bias_trend = market_bias.get("trend", "NEUTRAL")
                    if "BULL" in str(bias_trend).upper():
                        structure_type = "BULLISH"
                    elif "BEAR" in str(bias_trend).upper():
                        structure_type = "BEARISH"
        
        # Check for CHOCH/BOS
        choch_detected = structure.get("choch_detected", False)
        bos_detected = structure.get("bos_detected", False)
        
        if choch_detected or bos_detected:
            # Try to determine direction from timeframes
            timeframes = structure.get("timeframes", {})
            if isinstance(timeframes, dict):
                h4_data = timeframes.get("H4", {})
                if isinstance(h4_data, dict):
                    h4_bias = h4_data.get("bias", "NEUTRAL")
                    if "BULL" in str(h4_bias).upper():
                        structure_type = "BULLISH"
                    elif "BEAR" in str(h4_bias).upper():
                        structure_type = "BEARISH"
    
    price_structure = structure.get("price_structure", {}) if isinstance(structure, dict) else {}
    
    if "BULL" in str(structure_type).upper():
        bullish_signals.append(f"Structure: BULLISH")
    elif "BEAR" in str(structure_type).upper():
        bearish_signals.append(f"Structure: BEARISH")
    else:
        neutral_signals.append(f"Structure: {structure_type}")
    
    # Check for order blocks
    m1_micro = data.get("m1_microstructure", {})
    order_blocks = m1_micro.get("order_blocks", [])
    
    bullish_obs = [ob for ob in order_blocks if ob.get("type") == "bull"]
    bearish_obs = [ob for ob in order_blocks if ob.get("type") == "bear"]
    
    if bullish_obs:
        bullish_signals.append(f"Order Blocks: {len(bullish_obs)} bullish OB(s) detected")
    if bearish_obs:
        bearish_signals.append(f"Order Blocks: {len(bearish_obs)} bearish OB(s) detected")
    
    # 3. Momentum Analysis
    momentum_direction = "NEUTRAL"
    momentum_strength = 0
    
    if isinstance(momentum, dict):
        momentum_direction = momentum.get("direction", "NEUTRAL")
        momentum_strength = momentum.get("strength", 0)
    
    # Try to extract from advanced features
    if momentum_direction == "NEUTRAL" or not momentum_strength:
        advanced_features = data.get("advanced_features", {})
        if isinstance(advanced_features, dict):
            momentum_data = advanced_features.get("momentum", {})
            if isinstance(momentum_data, dict):
                momentum_direction = momentum_data.get("direction", momentum_direction)
                momentum_strength = momentum_data.get("strength", momentum_strength)
    
    # Try RSI as momentum indicator
    if momentum_direction == "NEUTRAL":
        smc = data.get("smc", {})
        if isinstance(smc, dict):
            timeframes = smc.get("timeframes", {})
            if isinstance(timeframes, dict):
                m5_data = timeframes.get("M5", {})
                if isinstance(m5_data, dict):
                    rsi = m5_data.get("rsi", 50)
                    if rsi > 60:
                        momentum_direction = "BULLISH"
                        momentum_strength = (rsi - 50) / 50 * 100
                    elif rsi < 40:
                        momentum_direction = "BEARISH"
                        momentum_strength = (50 - rsi) / 50 * 100
    
    if "BULL" in str(momentum_direction).upper():
        bullish_signals.append(f"Momentum: BULLISH (strength: {momentum_strength:.1f})")
    elif "BEAR" in str(momentum_direction).upper():
        bearish_signals.append(f"Momentum: BEARISH (strength: {momentum_strength:.1f})")
    else:
        neutral_signals.append(f"Momentum: NEUTRAL")
    
    # 4. Confluence Analysis
    if confluence >= 75:
        bullish_signals.append(f"Confluence: HIGH ({confluence}/100) - Strong alignment")
    elif confluence >= 60:
        neutral_signals.append(f"Confluence: MODERATE ({confluence}/100)")
    else:
        bearish_signals.append(f"Confluence: LOW ({confluence}/100) - Weak alignment")
    
    # 5. Volatility Analysis
    volatility_regime = data.get("volatility_regime", {})
    if not volatility_regime:
        volatility_regime = {}
    
    regime = "UNKNOWN"
    if isinstance(volatility_regime, dict):
        regime = volatility_regime.get("regime", "UNKNOWN")
    elif isinstance(volatility_regime, str):
        regime = volatility_regime
    
    atr_ratio = volatility.get("atr_ratio", 1.0) if isinstance(volatility, dict) else 1.0
    if not atr_ratio or atr_ratio == 0:
        atr_ratio = 1.0
    
    if "EXPAND" in str(regime).upper():
        if "BULL" in trend_direction:
            bullish_signals.append(f"Volatility: EXPANDING (trend continuation likely)")
        elif "BEAR" in trend_direction:
            bearish_signals.append(f"Volatility: EXPANDING (trend continuation likely)")
        else:
            neutral_signals.append(f"Volatility: EXPANDING (breakout potential)")
    elif "STABLE" in str(regime).upper() or "TRANSITION" in str(regime).upper():
        neutral_signals.append(f"Volatility: {regime} (range-bound likely)")
    
    # Add ATR ratio info
    if atr_ratio > 1.5:
        neutral_signals.append(f"ATR Ratio: {atr_ratio:.2f}x (high volatility)")
    elif atr_ratio < 0.8:
        neutral_signals.append(f"ATR Ratio: {atr_ratio:.2f}x (low volatility)")
    
    # 6. Macro Context
    macro_bias = "NEUTRAL"
    if isinstance(macro, dict):
        macro_bias = macro.get("bias", "NEUTRAL")
        if not macro_bias or macro_bias == "NEUTRAL":
            # Try to calculate from macro data
            dxy = macro.get("dxy", 0)
            us10y = macro.get("us10y", 0)
            vix = macro.get("vix", 0)
            
            # DXY high = bearish for risk assets, low = bullish
            # VIX high = bearish, low = bullish
            if dxy > 0 and vix > 0:
                if dxy < 100 and vix < 20:
                    macro_bias = "BULLISH"
                elif dxy > 105 and vix > 25:
                    macro_bias = "BEARISH"
    
    if "BULL" in str(macro_bias).upper():
        bullish_signals.append(f"Macro: BULLISH bias")
    elif "BEAR" in str(macro_bias).upper():
        bearish_signals.append(f"Macro: BEARISH bias")
    
    # 7. Support/Resistance Levels
    support_levels = []
    resistance_levels = []
    
    if isinstance(price_structure, dict):
        support_levels = price_structure.get("support_levels", [])
        resistance_levels = price_structure.get("resistance_levels", [])
    
    # Try alternative paths
    if not support_levels or not resistance_levels:
        smc = data.get("smc", {})
        if isinstance(smc, dict):
            # Try timeframes for levels
            timeframes = smc.get("timeframes", {})
            if isinstance(timeframes, dict):
                h4_data = timeframes.get("H4", {})
                if isinstance(h4_data, dict):
                    # Extract from advanced insights if available
                    advanced_insights = smc.get("advanced_insights", {})
                    if isinstance(advanced_insights, dict):
                        market_structure = advanced_insights.get("market_structure", {})
                        if isinstance(market_structure, dict):
                            support_levels = market_structure.get("support_levels", support_levels)
                            resistance_levels = market_structure.get("resistance_levels", resistance_levels)
    
    if support_levels and isinstance(support_levels, list):
        valid_supports = [s for s in support_levels if isinstance(s, (int, float)) and s < current_price]
        if valid_supports:
            nearest_support = max(valid_supports)
            distance_to_support = current_price - nearest_support
            pct_to_support = (distance_to_support / current_price) * 100
            if pct_to_support < 0.5:  # Within 0.5%
                bullish_signals.append(f"Price near support: ${nearest_support:,.2f} ({pct_to_support:.2f}% away)")
            elif pct_to_support < 1.0:  # Within 1%
                neutral_signals.append(f"Price approaching support: ${nearest_support:,.2f} ({pct_to_support:.2f}% away)")
    
    if resistance_levels and isinstance(resistance_levels, list):
        valid_resistances = [r for r in resistance_levels if isinstance(r, (int, float)) and r > current_price]
        if valid_resistances:
            nearest_resistance = min(valid_resistances)
            distance_to_resistance = nearest_resistance - current_price
            pct_to_resistance = (distance_to_resistance / current_price) * 100
            if pct_to_resistance < 0.5:  # Within 0.5%
                bearish_signals.append(f"Price near resistance: ${nearest_resistance:,.2f} ({pct_to_resistance:.2f}% away)")
            elif pct_to_resistance < 1.0:  # Within 1%
                neutral_signals.append(f"Price approaching resistance: ${nearest_resistance:,.2f} ({pct_to_resistance:.2f}% away)")
    
    # Calculate probability
    print("\n3. Signal Summary...")
    print("-" * 80)
    
    print(f"\n   🟢 BULLISH Signals ({len(bullish_signals)}):")
    for signal in bullish_signals:
        print(f"      ✅ {signal}")
    
    print(f"\n   🔴 BEARISH Signals ({len(bearish_signals)}):")
    for signal in bearish_signals:
        print(f"      ✅ {signal}")
    
    print(f"\n   ⚪ NEUTRAL Signals ({len(neutral_signals)}):")
    for signal in neutral_signals:
        print(f"      ⚪ {signal}")
    
    # Calculate directional probability
    total_signals = len(bullish_signals) + len(bearish_signals) + len(neutral_signals)
    
    if total_signals == 0:
        bullish_prob = 50
        bearish_prob = 50
    else:
        bullish_weight = len(bullish_signals) * 1.5  # Weight bullish signals more
        bearish_weight = len(bearish_signals) * 1.5
        neutral_weight = len(neutral_signals) * 0.5
        
        total_weight = bullish_weight + bearish_weight + neutral_weight
        
        bullish_prob = (bullish_weight / total_weight) * 100 if total_weight > 0 else 50
        bearish_prob = (bearish_weight / total_weight) * 100 if total_weight > 0 else 50
    
    # Adjust based on confluence
    if confluence >= 75:
        if len(bullish_signals) > len(bearish_signals):
            bullish_prob += 10
        elif len(bearish_signals) > len(bullish_signals):
            bearish_prob += 10
    elif confluence < 50:
        # Low confluence = more uncertainty
        bullish_prob = max(30, bullish_prob - 10)
        bearish_prob = max(30, bearish_prob - 10)
    
    # Normalize to 100%
    total_prob = bullish_prob + bearish_prob
    if total_prob > 0:
        bullish_prob = (bullish_prob / total_prob) * 100
        bearish_prob = (bearish_prob / total_prob) * 100
    
    print("\n4. Directional Probability...")
    print("-" * 80)
    
    print(f"\n   📈 BULLISH Probability: {bullish_prob:.1f}%")
    print(f"   📉 BEARISH Probability: {bearish_prob:.1f}%")
    
    # Determine recommendation
    if bullish_prob >= 60:
        recommendation = "BULLISH"
        confidence = "HIGH" if bullish_prob >= 70 else "MODERATE"
    elif bearish_prob >= 60:
        recommendation = "BEARISH"
        confidence = "HIGH" if bearish_prob >= 70 else "MODERATE"
    else:
        recommendation = "NEUTRAL"
        confidence = "LOW"
    
    print(f"\n   🎯 Recommendation: {recommendation} ({confidence} confidence)")
    
    # Key levels
    print("\n5. Key Levels...")
    print("-" * 80)
    
    if support_levels:
        print(f"\n   Support Levels:")
        for level in sorted(support_levels, reverse=True)[:3]:
            distance = current_price - level
            pct = (distance / current_price) * 100
            print(f"      ${level:,.2f} ({pct:.2f}% below)")
    
    if resistance_levels:
        print(f"\n   Resistance Levels:")
        for level in sorted(resistance_levels)[:3]:
            distance = level - current_price
            pct = (distance / current_price) * 100
            print(f"      ${level:,.2f} ({pct:.2f}% above)")
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    
    print(f"\n⚠️  DISCLAIMER:")
    print(f"   This is a probabilistic assessment based on current market data.")
    print(f"   Markets are unpredictable - use this as one input, not a guarantee.")
    print(f"   Always use proper risk management (stop losses, position sizing).")
    
    return {
        "symbol": symbol,
        "current_price": current_price,
        "bullish_probability": bullish_prob,
        "bearish_probability": bearish_prob,
        "recommendation": recommendation,
        "confidence": confidence,
        "bullish_signals": bullish_signals,
        "bearish_signals": bearish_signals
    }

async def main():
    """Main function"""
    bridge = get_bridge()
    
    # Analyze BTC and XAU
    symbols = ["BTCUSDc", "XAUUSDc"]
    
    results = []
    for symbol in symbols:
        result = await analyze_direction(symbol)
        results.append(result)
        print("\n" + "=" * 80 + "\n")
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    for result in results:
        symbol = result["symbol"]
        rec = result["recommendation"]
        conf = result["confidence"]
        bull_prob = result["bullish_probability"]
        bear_prob = result["bearish_probability"]
        
        print(f"\n{symbol}:")
        print(f"   Direction: {rec} ({conf})")
        print(f"   Bullish: {bull_prob:.1f}% | Bearish: {bear_prob:.1f}%")

if __name__ == "__main__":
    asyncio.run(main())
