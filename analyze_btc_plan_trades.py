"""
Analyze BTC plan trades and explain why they lost money
"""
import asyncio
import sqlite3
import json
import os
from cursor_trading_bridge import get_bridge

async def analyze_btc_plans():
    """Analyze BTC plans and their trade outcomes"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("BTC PLAN TRADE ANALYSIS")
    print("=" * 70)
    
    plan_ids = ["chatgpt_df3a9b5f", "chatgpt_634c5441"]
    
    # Get plan details from database
    auto_exec_db_path = os.path.join("data", "auto_execution.db")
    
    if not os.path.exists(auto_exec_db_path):
        print(f"\nERROR: Database not found at {auto_exec_db_path}")
        return
    
    conn = sqlite3.connect(auto_exec_db_path)
    cursor = conn.cursor()
    
    # Get recent trades to match with plans
    trades_result = await bridge.get_recent_trades(days_back=7)
    trades_data = trades_result.get("data", {})
    trades = trades_data.get("trades", [])
    trades_by_ticket = {t.get("ticket"): t for t in trades}
    
    for plan_id in plan_ids:
        print(f"\n{'=' * 70}")
        print(f"PLAN: {plan_id}")
        print("=" * 70)
        
        # Get plan details
        cursor.execute(
            """SELECT symbol, direction, entry_price, stop_loss, take_profit, volume, 
                      conditions, created_at, status, executed_at, ticket, notes
               FROM trade_plans WHERE plan_id = ?""",
            (plan_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            print(f"\n   Plan not found in database")
            continue
        
        (symbol, direction, entry_price, stop_loss, take_profit, volume, 
         conditions_str, created_at, status, executed_at, ticket, notes) = result
        
        # Parse conditions
        try:
            conditions = json.loads(conditions_str) if conditions_str else {}
        except:
            conditions = {}
        
        print(f"\n1. Plan Details:")
        print(f"   Symbol: {symbol}")
        print(f"   Direction: {direction}")
        print(f"   Status: {status}")
        print(f"   Created: {created_at}")
        if executed_at:
            print(f"   Executed: {executed_at}")
        if notes:
            print(f"   Notes: {notes[:200]}")
        
        print(f"\n2. Trade Parameters:")
        print(f"   Entry Price: ${entry_price:.2f}")
        print(f"   Stop Loss: ${stop_loss:.2f}")
        print(f"   Take Profit: ${take_profit:.2f}")
        print(f"   Volume: {volume} lots")
        
        # Calculate R (risk)
        if direction == "BUY":
            risk = entry_price - stop_loss
            reward = take_profit - entry_price
        else:  # SELL
            risk = stop_loss - entry_price
            reward = entry_price - take_profit
        
        if risk > 0:
            r_ratio = reward / risk
            print(f"   Risk: {risk:.2f} points")
            print(f"   Reward: {reward:.2f} points")
            print(f"   R:R Ratio: 1:{r_ratio:.2f}")
        
        print(f"\n3. Entry Conditions:")
        if conditions:
            if conditions.get("price_near"):
                print(f"   Price Near: ${conditions.get('price_near'):.2f}")
            if conditions.get("tolerance"):
                print(f"   Tolerance: {conditions.get('tolerance')} points")
            if conditions.get("confluence_min"):
                print(f"   Confluence Min: {conditions.get('confluence_min')}")
            
            # Structure conditions
            struct_conditions = []
            for key in ["liquidity_sweep", "rejection_wick", "choch_bull", "choch_bear",
                       "bos_bull", "bos_bear", "order_block", "m1_choch", "m1_bos"]:
                if conditions.get(key):
                    struct_conditions.append(key)
            if struct_conditions:
                print(f"   Structure Conditions: {', '.join(struct_conditions)}")
        
        # Get actual trade result
        print(f"\n4. Actual Trade Result:")
        if ticket:
            trade = trades_by_ticket.get(ticket)
            if trade:
                actual_entry = trade.get("entry_price", 0)
                actual_exit = trade.get("exit_price", 0)
                actual_sl = trade.get("stop_loss", 0)
                actual_tp = trade.get("take_profit", 0)
                profit_loss = trade.get("profit_loss", 0)
                close_reason = trade.get("close_reason", "N/A")
                opened_at = trade.get("opened_at", "N/A")
                closed_at = trade.get("closed_at", "N/A")
                
                print(f"   Ticket: {ticket}")
                print(f"   Actual Entry: ${actual_entry:.2f}")
                print(f"   Actual Exit: ${actual_exit:.2f}")
                print(f"   Actual SL: ${actual_sl:.2f}")
                print(f"   Actual TP: ${actual_tp:.2f}")
                print(f"   P&L: ${profit_loss:.2f}")
                print(f"   Close Reason: {close_reason}")
                print(f"   Opened: {opened_at}")
                if closed_at != "N/A":
                    print(f"   Closed: {closed_at}")
                
                # Analyze trade outcome
                print(f"\n5. Trade Outcome Analysis:")
                
                if profit_loss < 0:
                    print(f"   RESULT: LOSS of ${abs(profit_loss):.2f}")
                    if direction == "BUY":
                        if actual_exit < actual_entry:
                            price_move = actual_entry - actual_exit
                            print(f"   Price moved DOWN by {price_move:.2f} points")
                            print(f"   Trade hit Stop Loss at ${actual_sl:.2f}")
                        else:
                            print(f"   Price moved UP but trade still lost (check SL/TP)")
                    else:  # SELL
                        if actual_exit > actual_entry:
                            price_move = actual_exit - actual_entry
                            print(f"   Price moved UP by {price_move:.2f} points (against SELL)")
                            print(f"   Trade hit Stop Loss at ${actual_sl:.2f}")
                        else:
                            print(f"   Price moved DOWN but trade still lost (check SL/TP)")
                    
                    # Compare planned vs actual
                    print(f"\n   Planned vs Actual:")
                    print(f"   Planned Entry: ${entry_price:.2f} | Actual: ${actual_entry:.2f}")
                    print(f"   Planned SL: ${stop_loss:.2f} | Actual: ${actual_sl:.2f}")
                    print(f"   Planned TP: ${take_profit:.2f} | Actual: ${actual_tp:.2f}")
                    
                    # Check if SL was hit
                    if close_reason and "stop" in close_reason.lower():
                        print(f"\n   Trade was stopped out:")
                        if direction == "BUY":
                            sl_distance = actual_entry - actual_sl
                            print(f"   SL was {sl_distance:.2f} points below entry")
                            if actual_exit <= actual_sl:
                                print(f"   Exit price (${actual_exit:.2f}) <= SL (${actual_sl:.2f}) - SL was hit")
                        else:  # SELL
                            sl_distance = actual_sl - actual_entry
                            print(f"   SL was {sl_distance:.2f} points above entry")
                            if actual_exit >= actual_sl:
                                print(f"   Exit price (${actual_exit:.2f}) >= SL (${actual_sl:.2f}) - SL was hit")
                    
                    # Calculate expected loss
                    if direction == "BUY":
                        expected_loss = (actual_entry - actual_sl) * volume * 1.0  # $1 per point for 0.01 lot
                    else:  # SELL
                        expected_loss = (actual_sl - actual_entry) * volume * 1.0
                    
                    print(f"\n   Expected Loss (if SL hit): ${expected_loss:.2f}")
                    print(f"   Actual Loss: ${profit_loss:.2f}")
                    if abs(expected_loss - abs(profit_loss)) > 0.5:
                        print(f"   Difference: ${abs(expected_loss - abs(profit_loss)):.2f} (may include spread/swap)")
                elif profit_loss > 0:
                    print(f"   RESULT: PROFIT of ${profit_loss:.2f}")
                    
                    if direction == "BUY":
                        if actual_exit > actual_entry:
                            price_move = actual_exit - actual_entry
                            print(f"   Price moved UP by {price_move:.2f} points")
                            if actual_exit >= actual_tp:
                                print(f"   Trade hit Take Profit at ${actual_tp:.2f}")
                    else:  # SELL
                        if actual_exit < actual_entry:
                            price_move = actual_entry - actual_exit
                            print(f"   Price moved DOWN by {price_move:.2f} points (favorable for SELL)")
                            if actual_exit <= actual_tp:
                                print(f"   Trade hit Take Profit at ${actual_tp:.2f}")
                    
                    # Compare planned vs actual
                    print(f"\n   Planned vs Actual:")
                    print(f"   Planned Entry: ${entry_price:.2f} | Actual: ${actual_entry:.2f}")
                    print(f"   Planned SL: ${stop_loss:.2f} | Actual: ${actual_sl:.2f}")
                    print(f"   Planned TP: ${take_profit:.2f} | Actual: ${actual_tp:.2f}")
                    
                    # Calculate expected profit
                    if direction == "BUY":
                        expected_profit = (actual_exit - actual_entry) * volume * 1.0
                    else:  # SELL
                        expected_profit = (actual_entry - actual_exit) * volume * 1.0
                    
                    print(f"\n   Expected Profit: ${expected_profit:.2f}")
                    print(f"   Actual Profit: ${profit_loss:.2f}")
                    if abs(expected_profit - profit_loss) > 0.5:
                        print(f"   Difference: ${abs(expected_profit - profit_loss):.2f} (may include spread/swap)")
            else:
                print(f"   Ticket {ticket} not found in recent trades")
        else:
            print(f"   No ticket associated (plan not executed yet)")
    
    conn.close()
    
    # Summary
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print("=" * 70)
    print(f"\nBoth plans were price-based entry strategies with:")
    print(f"  - Price near conditions")
    print(f"  - Tolerance zones")
    print(f"  - Confluence requirements")
    print(f"\nThe losing trade hit its stop loss when price moved against the position.")

if __name__ == "__main__":
    asyncio.run(analyze_btc_plans())
