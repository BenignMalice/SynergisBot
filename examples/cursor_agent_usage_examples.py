"""
Example: How Cursor AI Agent Would Use the Trading Bridge

This file demonstrates how I (Cursor's AI agent) would interact with
your trading bot using the cursor_trading_bridge module.

These are the actual code patterns I would use when you ask me to:
- Analyze markets
- Provide trade recommendations  
- Execute trades
- Review performance
"""

import asyncio
from cursor_trading_bridge import (
    recommend, 
    analyze, 
    execute,
    get_bridge
)


# ============================================================================
# EXAMPLE 1: Simple Market Analysis
# ============================================================================
# User asks: "Analyze BTCUSD"
# I would do this:

async def example_1_simple_analysis():
    """Simple analysis request"""
    result = await recommend("BTCUSD")
    
    # I would then format this for the user:
    rec = result.get("recommendation", {})
    print(f"""
📊 BTCUSD Analysis:
- Current Price: {result.get('current_price')}
- Direction: {rec.get('direction')}
- Entry: {rec.get('entry')}
- SL: {rec.get('stop_loss')}
- TP: {rec.get('take_profit')}
- Confidence: {rec.get('confidence')}/100
- Reasoning: {rec.get('reasoning')}
    """)


# ============================================================================
# EXAMPLE 2: Multi-Symbol Comparison
# ============================================================================
# User asks: "Which is better - BTCUSD or XAUUSD?"
# I would do this:

async def example_2_compare_symbols():
    """Compare multiple symbols"""
    btc = await recommend("BTCUSD")
    gold = await recommend("XAUUSD")
    
    btc_conf = btc.get("recommendation", {}).get("confidence", 0)
    gold_conf = gold.get("recommendation", {}).get("confidence", 0)
    
    better = "BTCUSD" if btc_conf > gold_conf else "XAUUSD"
    
    print(f"""
📊 Symbol Comparison:
- BTCUSD Confidence: {btc_conf}/100
- XAUUSD Confidence: {gold_conf}/100
- Better Setup: {better}
    """)


# ============================================================================
# EXAMPLE 3: Trade Execution with Validation
# ============================================================================
# User asks: "Execute a BUY on BTCUSD"
# I would do this:

async def example_3_execute_trade():
    """Execute a trade with pre-validation"""
    bridge = get_bridge()
    
    # Step 1: Analyze first
    analysis = await analyze("BTCUSD")
    rec = analysis.get("data", {}).get("recommendation", {})
    
    # Step 2: Check confidence
    confidence = rec.get("confidence", 0)
    if confidence < 60:
        print(f"⚠️ Low confidence ({confidence}/100). Not executing.")
        return
    
    # Step 3: Execute
    result = await execute(
        symbol="BTCUSD",
        direction=rec.get("direction"),
        entry=rec.get("entry"),
        sl=rec.get("stop_loss"),
        tp=rec.get("take_profit")
    )
    
    if "error" in result:
        print(f"❌ Execution failed: {result['error']}")
    else:
        print(f"✅ Trade executed: {result.get('ticket')}")


# ============================================================================
# EXAMPLE 4: Auto-Execution Plan Creation
# ============================================================================
# User asks: "Create an auto-execution plan for XAUUSD"
# I would do this:

async def example_4_create_plan():
    """Create auto-execution plan"""
    bridge = get_bridge()
    
    # Analyze first
    analysis = await analyze("XAUUSD")
    rec = analysis.get("data", {}).get("recommendation", {})
    
    # Create plan with conditions
    result = await bridge.create_auto_plan(
        symbol="XAUUSD",
        direction=rec.get("direction"),
        entry=rec.get("entry"),
        sl=rec.get("stop_loss"),
        tp=rec.get("take_profit"),
        conditions={
            "confluence_min": 60,
            "vwap_slope_max": 0.0001,
            "liquidity_sweep": True,
            "timeframe": "M1"
        }
    )
    
    if "error" in result:
        print(f"❌ Plan creation failed: {result['error']}")
    else:
        plan_id = result.get("plan_id")
        print(f"✅ Auto-execution plan created: {plan_id}")


# ============================================================================
# EXAMPLE 5: Trade Performance Review
# ============================================================================
# User asks: "How did my trades perform today?"
# I would do this:

async def example_5_review_trades():
    """Review recent trades"""
    bridge = get_bridge()
    
    trades_data = await bridge.get_recent_trades(days_back=1)
    trades = trades_data.get("trades", [])
    
    if not trades:
        print("No trades found today.")
        return
    
    # Calculate stats
    total_pnl = sum(t.get("profit_loss", 0) for t in trades)
    wins = [t for t in trades if t.get("profit_loss", 0) > 0]
    losses = [t for t in trades if t.get("profit_loss", 0) <= 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    
    print(f"""
📊 Today's Performance:
- Total Trades: {len(trades)}
- Wins: {len(wins)} ({win_rate:.1f}%)
- Losses: {len(losses)}
- Net P/L: ${total_pnl:.2f}
    """)


# ============================================================================
# EXAMPLE 6: Real-Time Monitoring Loop
# ============================================================================
# User asks: "Monitor BTCUSD and alert me when setup is good"
# I would do this:

async def example_6_monitor_symbol():
    """Monitor symbol for good setups"""
    symbol = "BTCUSD"
    min_confidence = 75
    check_interval = 30  # seconds
    
    print(f"🔍 Monitoring {symbol} for setups (confidence ≥ {min_confidence})...")
    
    while True:
        result = await recommend(symbol)
        confidence = result.get("recommendation", {}).get("confidence", 0)
        
        if confidence >= min_confidence:
            rec = result.get("recommendation", {})
            print(f"""
🎯 Good setup detected!
- Confidence: {confidence}/100
- Direction: {rec.get('direction')}
- Entry: {rec.get('entry')}
- SL: {rec.get('stop_loss')}
- TP: {rec.get('take_profit')}
            """)
            break
        
        print(f"  Current confidence: {confidence}/100 (waiting...)")
        await asyncio.sleep(check_interval)


# ============================================================================
# EXAMPLE 7: Strategy Analysis
# ============================================================================
# User asks: "Which strategy worked best this week?"
# I would do this:

async def example_7_analyze_strategies():
    """Analyze strategy performance"""
    bridge = get_bridge()
    
    trades_data = await bridge.get_recent_trades(days_back=7)
    trades = trades_data.get("trades", [])
    
    # Group by strategy
    strategies = {}
    for trade in trades:
        strategy = trade.get("strategy", "Unknown")
        if strategy not in strategies:
            strategies[strategy] = {"trades": [], "pnl": 0, "wins": 0}
        
        strategies[strategy]["trades"].append(trade)
        strategies[strategy]["pnl"] += trade.get("profit_loss", 0)
        if trade.get("profit_loss", 0) > 0:
            strategies[strategy]["wins"] += 1
    
    # Find best strategy
    best = max(strategies.items(), key=lambda x: x[1]["pnl"])
    
    print(f"""
📊 Strategy Performance (Last 7 Days):
{chr(10).join(f"- {name}: ${data['pnl']:.2f} ({data['wins']}/{len(data['trades'])} wins)" 
              for name, data in strategies.items())}

🏆 Best Strategy: {best[0]} (${best[1]['pnl']:.2f})
    """)


# ============================================================================
# EXAMPLE 8: Interactive Trade Planning
# ============================================================================
# User asks: "Help me plan a trade on XAUUSD"
# I would do this:

async def example_8_plan_trade():
    """Interactive trade planning"""
    symbol = "XAUUSD"
    
    print(f"📋 Planning trade for {symbol}...")
    
    # Step 1: Analyze
    print("\nStep 1: Analyzing market...")
    analysis = await analyze(symbol)
    data = analysis.get("data", {})
    rec = data.get("recommendation", {})
    
    print(f"""
Step 2: Recommended Setup:
- Direction: {rec.get('direction')}
- Entry: {rec.get('entry')}
- Stop Loss: {rec.get('stop_loss')}
- Take Profit: {rec.get('take_profit')}
- Risk/Reward: {rec.get('risk_reward')}
- Confidence: {rec.get('confidence')}/100

Step 3: Reasoning:
{rec.get('reasoning')}

Step 4: Options:
A) Create auto-execution plan
B) Execute immediately
C) Adjust parameters
    """)


# ============================================================================
# MAIN: Run Examples
# ============================================================================

async def main():
    """Run all examples"""
    print("=" * 60)
    print("Cursor Agent Trading Bridge - Usage Examples")
    print("=" * 60)
    
    examples = [
        ("Simple Analysis", example_1_simple_analysis),
        ("Compare Symbols", example_2_compare_symbols),
        ("Execute Trade", example_3_execute_trade),
        ("Create Plan", example_4_create_plan),
        ("Review Trades", example_5_review_trades),
        ("Monitor Symbol", example_6_monitor_symbol),
        ("Analyze Strategies", example_7_analyze_strategies),
        ("Plan Trade", example_8_plan_trade),
    ]
    
    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    
    print("\nNote: These are code examples showing how I would use the bridge.")
    print("In practice, you would just ask me naturally, and I'd use these patterns.")
    print("\nExample: 'Analyze BTCUSD' → I'd run example_1_simple_analysis()")


if __name__ == "__main__":
    asyncio.run(main())
