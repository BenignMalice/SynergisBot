"""
Monitor current live BTC trades and identify which plans they came from
"""
import asyncio
from cursor_trading_bridge import get_bridge

async def monitor_btc_trades():
    """Monitor BTC trades and their associated plans"""
    bridge = get_bridge()
    
    print("=" * 70)
    print("LIVE BTC TRADES MONITORING")
    print("=" * 70)
    
    # Get current positions
    print("\n1. Getting Current Positions...")
    positions_result = await bridge.registry.execute("moneybot.getPositions", {})
    positions_data = positions_result.get("data", {})
    positions = positions_data.get("positions", [])
    
    # Filter for BTC trades
    btc_positions = [
        p for p in positions 
        if p.get("symbol", "").startswith("BTCUSD") or p.get("symbol", "").startswith("BTC")
    ]
    
    # Also check for recently closed trades from these plans
    print("\n3. Checking Recently Closed BTC Trades from These Plans...")
    closed_trades_result = await bridge.get_recent_trades(days_back=7)
    closed_trades_data = closed_trades_result.get("data", {})
    all_closed_trades = closed_trades_data.get("trades", [])
    
    # Get tickets we're monitoring
    monitored_tickets = {p.get("ticket") for p in btc_positions}
    
    # Find closed trades from our plans
    closed_btc_trades = [
        t for t in all_closed_trades 
        if (t.get("symbol", "").startswith("BTCUSD") or t.get("symbol", "").startswith("BTC"))
        and t.get("close_reason") != "Still Open"
        and (t.get("ticket") in monitored_tickets or 
             t.get("plan", {}).get("plan_id") in ["chatgpt_df3a9b5f", "chatgpt_634c5441"])
    ]
    
    if closed_btc_trades:
        print(f"   Found {len(closed_btc_trades)} recently closed BTC trade(s) from these plans:")
        for trade in closed_btc_trades[:5]:  # Show first 5
            ticket = trade.get("ticket", "N/A")
            symbol = trade.get("symbol", "N/A")
            direction = trade.get("direction", "N/A")
            entry = trade.get("entry_price", 0)
            exit_price = trade.get("exit_price", 0)
            profit = trade.get("profit_loss", 0)
            plan = trade.get("plan", {})
            plan_id = plan.get("plan_id", "N/A") if plan else ticket_to_plan.get(ticket, "N/A")
            
            print(f"\n   Ticket: {ticket}")
            print(f"   Symbol: {symbol} | Direction: {direction}")
            print(f"   Entry: ${entry:.2f} | Exit: ${exit_price:.2f} | P&L: ${profit:.2f}")
            print(f"   Plan ID: {plan_id}")
    
    if not btc_positions:
        print("\n   No open BTC positions found")
        return
    
    print(f"\n   Found {len(btc_positions)} open BTC position(s)")
    
    # Get plan information
    print("\n2. Getting Plan Information...")
    status_result = await bridge.registry.execute("moneybot.get_auto_system_status", {})
    status_data = status_result.get("data", {})
    system_status = status_data.get("system_status", {})
    all_plans = system_status.get("plans", [])
    
    # Create plan lookup by plan_id
    plans_by_id = {p.get("plan_id"): p for p in all_plans}
    
    # Get recent trades once (not in loop) - try longer period
    print("   Getting recent trades (30 days)...")
    trades_result = await bridge.get_recent_trades(days_back=30)
    trades_data = trades_result.get("data", {})
    trades = trades_data.get("trades", [])
    
    # Create trade lookup by ticket (all trades)
    all_trades_by_ticket = {t.get("ticket"): t for t in trades}
    
    # Also check journal database and auto-execution database directly
    print("   Checking journal and auto-execution databases...")
    import sqlite3
    import os
    
    # Check journal database
    journal_db_path = os.path.join("data", "journal.db")
    ticket_to_plan = {}
    
    if os.path.exists(journal_db_path):
        try:
            conn = sqlite3.connect(journal_db_path)
            cursor = conn.cursor()
            
            # Check if plan_id column exists
            cursor.execute("PRAGMA table_info(trades)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if "plan_id" in columns:
                # Get plan_id for our tickets
                for pos in btc_positions:
                    ticket = pos.get("ticket")
                    cursor.execute(
                        "SELECT plan_id FROM trades WHERE ticket = ?",
                        (ticket,)
                    )
                    result = cursor.fetchone()
                    if result and result[0]:
                        ticket_to_plan[ticket] = result[0]
            
            conn.close()
        except Exception as e:
            print(f"   Warning: Could not check journal database: {e}")
    
    # Check auto-execution database
    auto_exec_db_path = os.path.join("data", "auto_execution.db")
    
    if os.path.exists(auto_exec_db_path):
        try:
            conn = sqlite3.connect(auto_exec_db_path)
            cursor = conn.cursor()
            
            # Check if trade_plans table has ticket column
            cursor.execute("PRAGMA table_info(trade_plans)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if "ticket" in columns:
                # Get plan_id for our tickets
                for pos in btc_positions:
                    ticket = pos.get("ticket")
                    cursor.execute(
                        "SELECT plan_id FROM trade_plans WHERE ticket = ?",
                        (ticket,)
                    )
                    result = cursor.fetchone()
                    if result and result[0]:
                        ticket_to_plan[ticket] = result[0]
            
            # Also check by plan_id (user mentioned these plan IDs)
            known_plan_ids = ["chatgpt_df3a9b5f", "chatgpt_634c5441"]
            for plan_id in known_plan_ids:
                if "ticket" in columns:
                    cursor.execute(
                        "SELECT ticket FROM trade_plans WHERE plan_id = ?",
                        (plan_id,)
                    )
                    result = cursor.fetchone()
                    if result and result[0]:
                        ticket = result[0]
                        ticket_to_plan[ticket] = plan_id
                        print(f"   Found plan {plan_id} linked to ticket {ticket}")
            
            conn.close()
        except Exception as e:
            print(f"   Warning: Could not check auto-execution database: {e}")
    
    if ticket_to_plan:
        print(f"   Found {len(ticket_to_plan)} plan association(s) in databases")
    
    # Display trades with plan information
    print("\n" + "=" * 70)
    print("BTC TRADES DETAILS")
    print("=" * 70)
    
    for i, pos in enumerate(btc_positions, 1):
        ticket = pos.get("ticket", "N/A")
        symbol = pos.get("symbol", "N/A")
        direction = pos.get("type", "N/A")
        entry = pos.get("price_open", 0)
        current_price = pos.get("price_current", 0)
        sl = pos.get("sl", 0)
        tp = pos.get("tp", 0)
        volume = pos.get("volume", 0)
        profit = pos.get("profit", 0)
        swap = pos.get("swap", 0)
        
        print(f"\n{i}. Position {ticket}")
        print(f"   Symbol: {symbol}")
        print(f"   Direction: {direction}")
        print(f"   Volume: {volume} lots")
        print(f"   Entry: ${entry:.2f}")
        print(f"   Current: ${current_price:.2f}")
        print(f"   SL: ${sl:.2f}" if sl else "   SL: Not set")
        print(f"   TP: ${tp:.2f}" if tp else "   TP: Not set")
        print(f"   P&L: ${profit:.2f}")
        if swap != 0:
            print(f"   Swap: ${swap:.2f}")
        
        # Get plan information from trades
        print(f"\n   Plan Information:")
        
        # First check database lookups
        plan_id = ticket_to_plan.get(ticket)
        
        # Then check recent trades
        if not plan_id:
            matching_trade = all_trades_by_ticket.get(ticket)
            if matching_trade:
                plan = matching_trade.get("plan", {})
                plan_id = plan.get("plan_id", "N/A") if plan else "N/A"
        
        if plan_id and plan_id != "N/A":
            print(f"   Plan ID: {plan_id}")
            
            # Get plan details from active plans first
            plan_details = plans_by_id.get(plan_id)
            
            # If not in active plans, check database
            if not plan_details:
                try:
                    if os.path.exists(auto_exec_db_path):
                        conn = sqlite3.connect(auto_exec_db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT symbol, direction, entry_price, stop_loss, take_profit, conditions, status FROM trade_plans WHERE plan_id = ?",
                            (plan_id,)
                        )
                        result = cursor.fetchone()
                        if result:
                            import json
                            plan_details = {
                                "symbol": result[0],
                                "direction": result[1],
                                "entry_price": result[2],
                                "stop_loss": result[3],
                                "take_profit": result[4],
                                "conditions": json.loads(result[5]) if result[5] else {},
                                "status": result[6]
                            }
                        conn.close()
                except Exception as e:
                    print(f"   Warning: Could not get plan details from database: {e}")
            
            if plan_details:
                # Infer plan type from conditions
                conditions = plan_details.get("conditions", {})
                plan_type = "Unknown"
                
                if isinstance(conditions, dict):
                    # Check for structure conditions
                    if conditions.get("liquidity_sweep"):
                        plan_type = "Liquidity Sweep"
                    elif conditions.get("rejection_wick"):
                        plan_type = "Rejection Wick"
                    elif conditions.get("choch_bull") or conditions.get("choch_bear"):
                        plan_type = "CHOCH"
                    elif conditions.get("bos_bull") or conditions.get("bos_bear"):
                        plan_type = "BOS"
                    elif conditions.get("order_block"):
                        plan_type = "Order Block"
                    elif conditions.get("m1_choch") or conditions.get("m1_bos"):
                        plan_type = "M1 Microstructure"
                    elif conditions.get("execute_immediately"):
                        plan_type = "Immediate Execution"
                    else:
                        plan_type = "Price-Based"
                
                print(f"   Plan Type: {plan_type}")
                print(f"   Status: {plan_details.get('status', 'N/A')}")
                
                # Show key conditions
                if conditions:
                    print(f"   Key Conditions:")
                    if conditions.get("price_near"):
                        print(f"      - Price Near: ${conditions.get('price_near'):.2f}")
                    if conditions.get("tolerance"):
                        print(f"      - Tolerance: {conditions.get('tolerance')} points")
                    if conditions.get("confluence_min"):
                        print(f"      - Confluence Min: {conditions.get('confluence_min')}")
                    if conditions.get("structure_conditions"):
                        struct = conditions.get("structure_conditions", {})
                        if struct:
                            struct_keys = [k for k in struct.keys() if struct.get(k)]
                            if struct_keys:
                                print(f"      - Structure: {', '.join(struct_keys)}")
                    
                    # Show structure conditions directly
                    struct_keys = []
                    for key in ["liquidity_sweep", "rejection_wick", "choch_bull", "choch_bear", 
                               "bos_bull", "bos_bear", "order_block", "m1_choch", "m1_bos"]:
                        if conditions.get(key):
                            struct_keys.append(key)
                    if struct_keys:
                        print(f"      - Structure Conditions: {', '.join(struct_keys)}")
                
                # Show notes if available
                if plan_details.get("notes"):
                    notes = plan_details.get("notes", "")
                    if len(notes) > 100:
                        notes = notes[:100] + "..."
                    print(f"   Notes: {notes}")
            else:
                print(f"   Plan details not available (plan may have been removed)")
        else:
            print(f"   No plan ID found (manual trade or plan not linked)")
            print(f"   Checked: recent trades, journal database, auto-execution database")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    total_profit = sum(p.get("profit", 0) or 0 for p in btc_positions)
    profitable = sum(1 for p in btc_positions if (p.get("profit", 0) or 0) > 0)
    
    print(f"\nTotal BTC Positions: {len(btc_positions)}")
    print(f"Profitable: {profitable}")
    print(f"Total P&L: ${total_profit:.2f}")
    
    # Count by plan (using database lookups and trades)
    plan_counts = {}
    for pos in btc_positions:
        ticket = pos.get("ticket")
        plan_id = ticket_to_plan.get(ticket)
        
        if not plan_id:
            matching_trade = all_trades_by_ticket.get(ticket)
            if matching_trade:
                plan = matching_trade.get("plan", {})
                plan_id = plan.get("plan_id", "N/A") if plan else "Manual"
        
        if plan_id and plan_id != "N/A":
            plan_counts[plan_id] = plan_counts.get(plan_id, 0) + 1
        else:
            plan_counts["Manual/Unknown"] = plan_counts.get("Manual/Unknown", 0) + 1
    
    # Also show which plans are active for BTC
    print(f"\n3. Active BTC Plans:")
    btc_plans = [p for p in all_plans if p.get("symbol", "").startswith("BTC")]
    if btc_plans:
        print(f"   Found {len(btc_plans)} active BTC plan(s):")
        for plan in btc_plans[:10]:  # Show first 10
            plan_id = plan.get("plan_id", "N/A")
            plan_type = plan.get("plan_type", "N/A")
            direction = plan.get("direction", "N/A")
            status = plan.get("status", "N/A")
            print(f"   - {plan_id}: {plan_type} {direction} ({status})")
    else:
        print(f"   No active BTC plans found")
    
    if plan_counts:
        print(f"\nTrades by Plan:")
        for plan_id, count in plan_counts.items():
            print(f"   {plan_id}: {count} trade(s)")

if __name__ == "__main__":
    asyncio.run(monitor_btc_trades())



