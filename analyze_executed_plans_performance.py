"""
Comprehensive performance analysis of executed auto-execution plans
"""
import asyncio
import json
from cursor_trading_bridge import get_bridge
from datetime import datetime, timezone
from collections import defaultdict

async def analyze_performance():
    """Comprehensive performance analysis"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("EXECUTED PLANS PERFORMANCE ANALYSIS")
    print("=" * 70)
    
    # Get recent trades (last 7 days for more data)
    trades_result = await bridge.get_recent_trades(days_back=7)
    trades_data = trades_result.get("data", {})
    trades = trades_data.get("trades", [])
    
    if not trades:
        print("\n⚠️ No executed trades found in the last 7 days")
        return
    
    print(f"\n📊 Total Executed Trades: {len(trades)}")
    
    # Categorize trades
    by_symbol = defaultdict(list)
    by_plan_type = defaultdict(list)
    by_direction = defaultdict(list)
    by_close_reason = defaultdict(list)
    
    for trade in trades:
        symbol = trade.get("symbol", "UNKNOWN")
        plan = trade.get("plan", {})
        conditions = plan.get("conditions", {})
        direction = trade.get("direction", "UNKNOWN")
        close_reason = trade.get("close_reason", "UNKNOWN")
        
        # Determine plan type
        has_structure = any([
            conditions.get("liquidity_sweep"),
            conditions.get("rejection_wick"),
            conditions.get("choch_bull"),
            conditions.get("choch_bear"),
            conditions.get("bos_bull"),
            conditions.get("bos_bear"),
            conditions.get("order_block"),
            conditions.get("inside_bar"),
        ])
        
        has_m1 = any([
            conditions.get("m1_choch"),
            conditions.get("m1_bos"),
            conditions.get("m1_choch_bos_combo"),
        ])
        
        if not has_structure and not has_m1 and "price_near" in conditions:
            plan_type = "Price-Only"
        elif has_m1:
            plan_type = "M1-Based"
        elif has_structure:
            plan_type = "Structure-Based"
        else:
            plan_type = "Other"
        
        by_symbol[symbol].append(trade)
        by_plan_type[plan_type].append(trade)
        by_direction[direction].append(trade)
        by_close_reason[close_reason].append(trade)
    
    # Calculate metrics
    def calculate_metrics(trade_list):
        if not trade_list:
            return {}
        
        total_pl = sum(t.get("profit_loss", 0) or 0 for t in trade_list)
        wins = [t for t in trade_list if (t.get("profit_loss", 0) or 0) > 0]
        losses = [t for t in trade_list if (t.get("profit_loss", 0) or 0) < 0]
        breakeven = [t for t in trade_list if (t.get("profit_loss", 0) or 0) == 0]
        
        win_rate = (len(wins) / len(trade_list)) * 100 if trade_list else 0
        avg_pl = total_pl / len(trade_list) if trade_list else 0
        avg_win = sum(t.get("profit_loss", 0) or 0 for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.get("profit_loss", 0) or 0 for t in losses) / len(losses) if losses else 0
        
        # Calculate R:R ratios
        rr_ratios = []
        for t in trade_list:
            entry = t.get("entry_price", 0)
            sl = t.get("stop_loss", 0)
            tp = t.get("take_profit", 0)
            if entry and sl and tp:
                risk = abs(entry - sl)
                reward = abs(tp - entry)
                if risk > 0:
                    rr = reward / risk
                    rr_ratios.append(rr)
        
        avg_rr = sum(rr_ratios) / len(rr_ratios) if rr_ratios else 0
        
        # Calculate durations
        durations = []
        for t in trade_list:
            opened = t.get("opened_at")
            closed = t.get("closed_at")
            duration = t.get("duration_seconds")
            if duration:
                durations.append(duration)
        
        avg_duration = sum(durations) / len(durations) if durations else 0
        avg_duration_min = avg_duration / 60 if avg_duration else 0
        
        return {
            "total": len(trade_list),
            "wins": len(wins),
            "losses": len(losses),
            "breakeven": len(breakeven),
            "win_rate": win_rate,
            "total_pl": total_pl,
            "avg_pl": avg_pl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "avg_rr": avg_rr,
            "avg_duration_min": avg_duration_min,
            "profit_factor": abs(avg_win / avg_loss) if avg_loss < 0 else 0,
        }
    
    # Overall Performance
    print("\n" + "=" * 70)
    print("OVERALL PERFORMANCE")
    print("=" * 70)
    
    overall = calculate_metrics(trades)
    print(f"\n📊 Overall Statistics:")
    print(f"   Total Trades: {overall['total']}")
    print(f"   Wins: {overall['wins']} | Losses: {overall['losses']} | Breakeven: {overall['breakeven']}")
    print(f"   Win Rate: {overall['win_rate']:.1f}%")
    print(f"   Total P&L: ${overall['total_pl']:.2f}")
    print(f"   Average P&L: ${overall['avg_pl']:.2f}")
    print(f"   Average Win: ${overall['avg_win']:.2f}")
    print(f"   Average Loss: ${overall['avg_loss']:.2f}")
    print(f"   Profit Factor: {overall['profit_factor']:.2f}" if overall['profit_factor'] > 0 else "   Profit Factor: N/A")
    print(f"   Average R:R: 1:{overall['avg_rr']:.2f}" if overall['avg_rr'] > 0 else "   Average R:R: N/A")
    print(f"   Average Duration: {overall['avg_duration_min']:.1f} minutes")
    
    # Performance by Symbol
    print("\n" + "=" * 70)
    print("PERFORMANCE BY SYMBOL")
    print("=" * 70)
    
    for symbol, symbol_trades in sorted(by_symbol.items()):
        metrics = calculate_metrics(symbol_trades)
        print(f"\n📈 {symbol}:")
        print(f"   Trades: {metrics['total']} | Win Rate: {metrics['win_rate']:.1f}%")
        print(f"   Total P&L: ${metrics['total_pl']:.2f} | Avg P&L: ${metrics['avg_pl']:.2f}")
        print(f"   Avg Win: ${metrics['avg_win']:.2f} | Avg Loss: ${metrics['avg_loss']:.2f}")
        if metrics['profit_factor'] > 0:
            print(f"   Profit Factor: {metrics['profit_factor']:.2f}")
    
    # Performance by Plan Type
    print("\n" + "=" * 70)
    print("PERFORMANCE BY PLAN TYPE")
    print("=" * 70)
    
    for plan_type, type_trades in sorted(by_plan_type.items()):
        metrics = calculate_metrics(type_trades)
        print(f"\n🔧 {plan_type}:")
        print(f"   Trades: {metrics['total']} | Win Rate: {metrics['win_rate']:.1f}%")
        print(f"   Total P&L: ${metrics['total_pl']:.2f} | Avg P&L: ${metrics['avg_pl']:.2f}")
        print(f"   Avg Win: ${metrics['avg_win']:.2f} | Avg Loss: ${metrics['avg_loss']:.2f}")
        if metrics['profit_factor'] > 0:
            print(f"   Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"   Avg Duration: {metrics['avg_duration_min']:.1f} minutes")
    
    # Performance by Direction
    print("\n" + "=" * 70)
    print("PERFORMANCE BY DIRECTION")
    print("=" * 70)
    
    for direction, dir_trades in sorted(by_direction.items()):
        metrics = calculate_metrics(dir_trades)
        print(f"\n📊 {direction}:")
        print(f"   Trades: {metrics['total']} | Win Rate: {metrics['win_rate']:.1f}%")
        print(f"   Total P&L: ${metrics['total_pl']:.2f} | Avg P&L: ${metrics['avg_pl']:.2f}")
    
    # Performance by Close Reason
    print("\n" + "=" * 70)
    print("PERFORMANCE BY CLOSE REASON")
    print("=" * 70)
    
    for reason, reason_trades in sorted(by_close_reason.items()):
        metrics = calculate_metrics(reason_trades)
        print(f"\n🔚 {reason}:")
        print(f"   Trades: {metrics['total']} | Win Rate: {metrics['win_rate']:.1f}%")
        print(f"   Total P&L: ${metrics['total_pl']:.2f} | Avg P&L: ${metrics['avg_pl']:.2f}")
    
    # Individual Trade Analysis
    print("\n" + "=" * 70)
    print("TOP PERFORMING TRADES")
    print("=" * 70)
    
    sorted_trades = sorted(trades, key=lambda t: t.get("profit_loss", 0) or 0, reverse=True)
    
    print(f"\n🏆 Top 5 Winners:")
    for i, trade in enumerate(sorted_trades[:5], 1):
        if (trade.get("profit_loss", 0) or 0) > 0:
            plan = trade.get("plan", {})
            plan_id = plan.get("plan_id", "N/A")
            symbol = trade.get("symbol", "N/A")
            direction = trade.get("direction", "N/A")
            pl = trade.get("profit_loss", 0)
            entry = trade.get("entry_price", 0)
            exit_price = trade.get("exit_price", 0)
            close_reason = trade.get("close_reason", "N/A")
            
            print(f"   {i}. {symbol} {direction} | P&L: ${pl:.2f}")
            print(f"      Plan: {plan_id[:20]}... | Entry: ${entry:.2f} | Exit: ${exit_price:.2f}")
            print(f"      Close: {close_reason}")
    
    print(f"\n📉 Top 5 Losers:")
    for i, trade in enumerate(sorted_trades[-5:], 1):
        if (trade.get("profit_loss", 0) or 0) < 0:
            plan = trade.get("plan", {})
            plan_id = plan.get("plan_id", "N/A")
            symbol = trade.get("symbol", "N/A")
            direction = trade.get("direction", "N/A")
            pl = trade.get("profit_loss", 0)
            entry = trade.get("entry_price", 0)
            exit_price = trade.get("exit_price", 0)
            close_reason = trade.get("close_reason", "N/A")
            
            print(f"   {i}. {symbol} {direction} | P&L: ${pl:.2f}")
            print(f"      Plan: {plan_id[:20]}... | Entry: ${entry:.2f} | Exit: ${exit_price:.2f}")
            print(f"      Close: {close_reason}")
    
    # Insights and Recommendations
    print("\n" + "=" * 70)
    print("INSIGHTS & RECOMMENDATIONS")
    print("=" * 70)
    
    insights = []
    
    # Win rate analysis
    if overall['win_rate'] < 50:
        insights.append(f"⚠️ Win rate is {overall['win_rate']:.1f}% - below 50%. Consider:")
        insights.append("   • Reviewing entry conditions for better timing")
        insights.append("   • Tightening stop losses or adjusting take profit levels")
        insights.append("   • Adding more confluence factors to plans")
    elif overall['win_rate'] >= 50:
        insights.append(f"✅ Win rate is {overall['win_rate']:.1f}% - good performance")
    
    # Profit factor analysis
    if overall['profit_factor'] > 0:
        if overall['profit_factor'] < 1.0:
            insights.append(f"⚠️ Profit factor is {overall['profit_factor']:.2f} - below 1.0 (losing)")
            insights.append("   • Average losses exceed average wins")
            insights.append("   • Consider improving R:R ratios or entry quality")
        elif overall['profit_factor'] >= 1.5:
            insights.append(f"✅ Profit factor is {overall['profit_factor']:.2f} - excellent")
        else:
            insights.append(f"⚠️ Profit factor is {overall['profit_factor']:.2f} - needs improvement")
    
    # Plan type comparison
    if len(by_plan_type) > 1:
        insights.append("\n📊 Plan Type Comparison:")
        for plan_type, type_trades in sorted(by_plan_type.items()):
            metrics = calculate_metrics(type_trades)
            if metrics['total'] > 0:
                insights.append(f"   {plan_type}: {metrics['win_rate']:.1f}% WR, ${metrics['avg_pl']:.2f} avg P&L")
    
    # Manual vs automatic closes
    manual_closes = by_close_reason.get("manual", [])
    auto_closes = [t for t in trades if t.get("close_reason") != "manual"]
    
    if manual_closes:
        manual_metrics = calculate_metrics(manual_closes)
        insights.append(f"\n🔧 Manual Closes: {len(manual_closes)} trades")
        insights.append(f"   Win Rate: {manual_metrics['win_rate']:.1f}% | Avg P&L: ${manual_metrics['avg_pl']:.2f}")
    
    if auto_closes:
        auto_metrics = calculate_metrics(auto_closes)
        insights.append(f"🤖 Automatic Closes: {len(auto_closes)} trades")
        insights.append(f"   Win Rate: {auto_metrics['win_rate']:.1f}% | Avg P&L: ${auto_metrics['avg_pl']:.2f}")
    
    # Print insights
    for insight in insights:
        print(insight)
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    print(f"\n✅ Key Findings:")
    print(f"   • {overall['total']} total trades executed")
    print(f"   • {overall['win_rate']:.1f}% win rate")
    print(f"   • ${overall['total_pl']:.2f} total P&L")
    print(f"   • ${overall['avg_pl']:.2f} average P&L per trade")
    
    if overall['profit_factor'] > 0:
        print(f"   • {overall['profit_factor']:.2f} profit factor")
    
    print(f"\n💡 Next Steps:")
    print(f"   1. Review top performing plan types")
    print(f"   2. Analyze losing trades for patterns")
    print(f"   3. Adjust plan conditions based on performance")
    print(f"   4. Consider creating more plans of successful types")

if __name__ == "__main__":
    asyncio.run(analyze_performance())
