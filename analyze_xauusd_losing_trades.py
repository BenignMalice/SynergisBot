"""
Detailed analysis of XAUUSD losing trades to identify patterns
"""
import asyncio
import json
from cursor_trading_bridge import get_bridge
from collections import defaultdict

async def analyze_xauusd_losers():
    """Analyze XAUUSD losing trades in detail"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("XAUUSD LOSING TRADES ANALYSIS")
    print("=" * 70)
    
    # Get recent trades
    trades_result = await bridge.get_recent_trades(days_back=7)
    trades_data = trades_result.get("data", {})
    trades = trades_data.get("trades", [])
    
    # Filter XAUUSD losing trades
    xau_losers = [
        t for t in trades 
        if t.get("symbol") == "XAUUSDc" and (t.get("profit_loss", 0) or 0) < 0
    ]
    
    if not xau_losers:
        print("\n⚠️ No XAUUSD losing trades found")
        return
    
    print(f"\n📊 Total XAUUSD Losing Trades: {len(xau_losers)}")
    
    # Sort by loss amount (worst first)
    xau_losers.sort(key=lambda t: t.get("profit_loss", 0) or 0)
    
    # Detailed analysis of each losing trade
    print("\n" + "=" * 70)
    print("DETAILED LOSING TRADE ANALYSIS")
    print("=" * 70)
    
    total_loss = 0
    by_direction = defaultdict(list)
    by_plan_type = defaultdict(list)
    by_close_reason = defaultdict(list)
    stop_loss_hits = []
    entry_issues = []
    
    for i, trade in enumerate(xau_losers, 1):
        plan = trade.get("plan", {})
        plan_id = plan.get("plan_id", "N/A")
        direction = trade.get("direction", "N/A")
        entry = trade.get("entry_price", 0)
        exit_price = trade.get("exit_price", 0)
        sl = trade.get("stop_loss", 0)
        tp = trade.get("take_profit", 0)
        pl = trade.get("profit_loss", 0)
        close_reason = trade.get("close_reason", "N/A")
        opened = trade.get("opened_at", "N/A")
        closed = trade.get("closed_at", "N/A")
        duration = trade.get("duration_seconds") or 0
        
        # Calculate metrics
        loss_pct = ((exit_price - entry) / entry * 100) if entry > 0 else 0
        sl_distance = abs(entry - sl) if entry and sl else 0
        tp_distance = abs(tp - entry) if entry and tp else 0
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
        
        # Check if stop loss was hit
        hit_sl = False
        if direction == "BUY" and exit_price <= sl:
            hit_sl = True
        elif direction == "SELL" and exit_price >= sl:
            hit_sl = True
        
        # Check entry quality
        entry_quality = "UNKNOWN"
        conditions = plan.get("conditions", {})
        has_structure = any([
            conditions.get("liquidity_sweep"),
            conditions.get("rejection_wick"),
            conditions.get("choch_bull"),
            conditions.get("choch_bear"),
            conditions.get("bos_bull"),
            conditions.get("bos_bear"),
            conditions.get("order_block"),
        ])
        
        if not has_structure and "price_near" in conditions:
            entry_quality = "Price-Only"
        elif has_structure:
            entry_quality = "Structure-Based"
        
        total_loss += abs(pl)
        
        by_direction[direction].append(trade)
        by_plan_type[entry_quality].append(trade)
        by_close_reason[close_reason].append(trade)
        
        if hit_sl:
            stop_loss_hits.append(trade)
        
        # Print detailed analysis
        print(f"\n{i}. Trade #{trade.get('ticket', 'N/A')} - {direction}")
        print(f"   Plan ID: {plan_id}")
        print(f"   Entry: ${entry:.2f} | Exit: ${exit_price:.2f} | Loss: ${pl:.2f} ({loss_pct:.2f}%)")
        print(f"   SL: ${sl:.2f} | TP: ${tp:.2f} | R:R: 1:{rr_ratio:.2f}")
        print(f"   SL Distance: {sl_distance:.2f} points | TP Distance: {tp_distance:.2f} points")
        print(f"   Close Reason: {close_reason} | Duration: {duration/60:.1f} min")
        print(f"   Entry Quality: {entry_quality}")
        print(f"   Stop Loss Hit: {'✅ YES' if hit_sl else '❌ NO'}")
        
        # Analyze why it lost
        if hit_sl:
            print(f"   ⚠️ Stop loss was hit - SL may be too tight or entry was poor")
        elif close_reason == "manual":
            print(f"   ⚠️ Manually closed at loss - may have been premature")
        else:
            print(f"   ⚠️ Closed at loss without hitting SL - entry timing may be issue")
        
        # Check plan conditions
        notes = plan.get("notes", "")
        if notes:
            print(f"   Notes: {notes[:80]}...")
    
    # Pattern Analysis
    print("\n" + "=" * 70)
    print("PATTERN ANALYSIS")
    print("=" * 70)
    
    print(f"\n📊 Loss Distribution:")
    print(f"   Total Loss: ${total_loss:.2f}")
    print(f"   Average Loss: ${total_loss/len(xau_losers):.2f}")
    print(f"   Largest Loss: ${abs(xau_losers[0].get('profit_loss', 0)):.2f}")
    print(f"   Smallest Loss: ${abs(xau_losers[-1].get('profit_loss', 0)):.2f}")
    
    print(f"\n📊 By Direction:")
    for direction, dir_trades in sorted(by_direction.items()):
        avg_loss = sum(abs(t.get("profit_loss", 0) or 0) for t in dir_trades) / len(dir_trades)
        print(f"   {direction}: {len(dir_trades)} trades, Avg Loss: ${avg_loss:.2f}")
    
    print(f"\n📊 By Plan Type:")
    for plan_type, type_trades in sorted(by_plan_type.items()):
        avg_loss = sum(abs(t.get("profit_loss", 0) or 0) for t in type_trades) / len(type_trades)
        print(f"   {plan_type}: {len(type_trades)} trades, Avg Loss: ${avg_loss:.2f}")
    
    print(f"\n📊 By Close Reason:")
    for reason, reason_trades in sorted(by_close_reason.items()):
        avg_loss = sum(abs(t.get("profit_loss", 0) or 0) for t in reason_trades) / len(reason_trades)
        print(f"   {reason}: {len(reason_trades)} trades, Avg Loss: ${avg_loss:.2f}")
    
    print(f"\n📊 Stop Loss Analysis:")
    print(f"   Trades that hit SL: {len(stop_loss_hits)}/{len(xau_losers)} ({len(stop_loss_hits)/len(xau_losers)*100:.1f}%)")
    
    # Calculate average SL distance
    sl_distances = []
    for trade in xau_losers:
        entry = trade.get("entry_price", 0)
        sl = trade.get("stop_loss", 0)
        if entry and sl:
            sl_distances.append(abs(entry - sl))
    
    if sl_distances:
        avg_sl_distance = sum(sl_distances) / len(sl_distances)
        print(f"   Average SL Distance: {avg_sl_distance:.2f} points")
        print(f"   Min SL Distance: {min(sl_distances):.2f} points")
        print(f"   Max SL Distance: {max(sl_distances):.2f} points")
    
    # Identify patterns
    print("\n" + "=" * 70)
    print("IDENTIFIED PATTERNS")
    print("=" * 70)
    
    patterns = []
    
    # Pattern 1: Stop loss distance
    if sl_distances:
        if avg_sl_distance > 5.0:
            patterns.append("⚠️ Stop losses are too wide (avg {:.2f} points)".format(avg_sl_distance))
            patterns.append("   Recommendation: Tighten SL to 3-4 points for XAUUSD")
        elif avg_sl_distance < 2.0:
            patterns.append("⚠️ Stop losses may be too tight (avg {:.2f} points)".format(avg_sl_distance))
            patterns.append("   Recommendation: Consider slightly wider SL (3-4 points)")
        else:
            patterns.append("✅ Stop loss distance seems reasonable ({:.2f} points)".format(avg_sl_distance))
    
    # Pattern 2: Direction bias
    buy_losses = len(by_direction.get("BUY", []))
    sell_losses = len(by_direction.get("SELL", []))
    if buy_losses > sell_losses * 1.5:
        patterns.append("⚠️ BUY trades have more losses ({}/{} = {:.1f}x)".format(buy_losses, sell_losses, buy_losses/max(sell_losses, 1)))
        patterns.append("   Recommendation: Review BUY entry conditions")
    elif sell_losses > buy_losses * 1.5:
        patterns.append("⚠️ SELL trades have more losses ({}/{} = {:.1f}x)".format(sell_losses, buy_losses, sell_losses/max(buy_losses, 1)))
        patterns.append("   Recommendation: Review SELL entry conditions")
    
    # Pattern 3: Plan type
    price_only_losses = len(by_plan_type.get("Price-Only", []))
    structure_losses = len(by_plan_type.get("Structure-Based", []))
    if price_only_losses > structure_losses:
        patterns.append("⚠️ Price-only plans have more losses")
        patterns.append("   Recommendation: Add minimal confluence to price-only plans")
    
    # Pattern 4: Close reason
    manual_losses = len(by_close_reason.get("manual", []))
    if manual_losses > 0:
        patterns.append("⚠️ {} manual closes were losses".format(manual_losses))
        patterns.append("   Recommendation: Let automatic system handle closes")
    
    # Pattern 5: Largest loss
    largest_loss = xau_losers[0]
    largest_pl = abs(largest_loss.get("profit_loss", 0))
    if largest_pl > 10:
        patterns.append("⚠️ Largest loss is ${:.2f} - significant outlier".format(largest_pl))
        patterns.append("   Recommendation: Review this specific trade for issues")
    
    for pattern in patterns:
        print(f"\n{pattern}")
    
    # Recommendations
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    
    print("\n✅ Immediate Actions:")
    print("   1. Tighten stop losses to 3-4 points for XAUUSD")
    print("   2. Review entry conditions, especially for direction with more losses")
    print("   3. Add minimal confluence to price-only plans")
    print("   4. Let automatic system handle closes (avoid manual closes)")
    print("   5. Review the largest loss trade for specific issues")
    
    print("\n✅ Plan Optimizations:")
    print("   • Reduce SL distance from current average to 3-4 points")
    print("   • Improve entry timing with better confluence")
    print("   • Consider tighter tolerance for price-only plans")
    print("   • Add structure confirmation to price-only plans")

if __name__ == "__main__":
    asyncio.run(analyze_xauusd_losers())
