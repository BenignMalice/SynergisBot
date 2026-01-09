"""
Plan-Trade Sync Mechanism
Syncs execution logs from journal database to plan effectiveness tracker.
Links closed trades to their originating auto-execution plans.
"""
import sqlite3
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 not available - cannot query MT5 for closed trades")


class PlanTradeSync:
    """Syncs trade execution logs with plan effectiveness tracking"""
    
    def __init__(
        self,
        journal_db_path: str = "data/journal.sqlite",
        plan_db_path: str = "data/auto_execution.db"
    ):
        self.journal_db_path = Path(journal_db_path)
        self.plan_db_path = Path(plan_db_path)
    
    def sync_closed_trades_to_plans(self, days_back: int = 30) -> Dict[str, Any]:
        """
        Sync closed trades from journal to plan database, and also check MT5 for plans missing close data.
        Updates plan profit_loss, exit_price, close_time, close_reason.
        
        Returns:
            Dict with sync statistics
        """
        if not self.plan_db_path.exists():
            logger.warning(f"Plan database not found: {self.plan_db_path}")
            return {"success": False, "error": "Plan database not found"}
        
        try:
            # Connect to plan database
            plan_conn = sqlite3.connect(str(self.plan_db_path))
            plan_cursor = plan_conn.cursor()
            
            # Get cutoff timestamp
            cutoff_ts = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp())
            cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
            
            synced_count = 0
            updated_count = 0
            errors = []
            
            # PHASE 1: Sync from journal database (if it exists)
            if self.journal_db_path.exists():
                journal_conn = sqlite3.connect(str(self.journal_db_path))
                journal_cursor = journal_conn.cursor()
                
                # Get closed trades with plan_id from journal
                journal_cursor.execute("""
                    SELECT ticket, plan_id, pnl, exit_price, closed_ts, close_reason
                    FROM trades
                    WHERE closed_ts IS NOT NULL 
                    AND closed_ts >= ?
                    AND plan_id IS NOT NULL
                    AND plan_id != ''
                """, (cutoff_ts,))
                
                closed_trades = journal_cursor.fetchall()
                
                for ticket, plan_id, pnl, exit_price, closed_ts, close_reason in closed_trades:
                    try:
                        # Check if plan exists and needs update
                        plan_cursor.execute("""
                            SELECT profit_loss, exit_price, close_time
                            FROM trade_plans
                            WHERE plan_id = ? AND ticket = ?
                        """, (plan_id, ticket))
                        
                        plan_row = plan_cursor.fetchone()
                        
                        if not plan_row:
                            logger.debug(f"Plan {plan_id} not found for ticket {ticket} - skipping")
                            continue
                        
                        current_pnl, current_exit, current_close = plan_row
                        
                        # Only update if data is missing or different
                        needs_update = (
                            current_pnl is None or
                            current_exit is None or
                            current_close is None or
                            abs(current_pnl - (pnl or 0)) > 0.01  # Allow small floating point differences
                        )
                        
                        if needs_update:
                            # Convert closed_ts to ISO format
                            close_time_iso = datetime.fromtimestamp(closed_ts, tz=timezone.utc).isoformat()
                            
                            # Update plan with trade outcome
                            plan_cursor.execute("""
                                UPDATE trade_plans
                                SET profit_loss = ?,
                                    exit_price = ?,
                                    close_time = ?,
                                    close_reason = ?
                                WHERE plan_id = ? AND ticket = ?
                            """, (pnl, exit_price, close_time_iso, close_reason, plan_id, ticket))
                            
                            plan_conn.commit()
                            updated_count += 1
                            logger.debug(f"Synced trade {ticket} to plan {plan_id} from journal: P/L=${pnl:.2f}")
                        
                        synced_count += 1
                        
                    except Exception as e:
                        error_msg = f"Error syncing ticket {ticket} (plan {plan_id}) from journal: {e}"
                        logger.error(error_msg, exc_info=True)
                        errors.append(error_msg)
                
                journal_conn.close()
            
            # PHASE 2: Check MT5 for executed plans missing close data
            if MT5_AVAILABLE:
                try:
                    # Get executed plans that might be closed but don't have close_time
                    plan_cursor.execute("""
                        SELECT plan_id, ticket, executed_at, symbol, direction
                        FROM trade_plans
                        WHERE (status = 'executed' OR status = 'closed')
                        AND ticket IS NOT NULL
                        AND executed_at IS NOT NULL
                        AND executed_at >= ?
                        AND (close_time IS NULL OR profit_loss IS NULL OR exit_price IS NULL)
                        ORDER BY executed_at DESC
                        LIMIT 100
                    """, (cutoff_iso,))
                    
                    plans_missing_data = plan_cursor.fetchall()
                    
                    if plans_missing_data:
                        # Initialize MT5
                        mt5_initialized = mt5.initialize()
                        if mt5_initialized:
                            from infra.plan_effectiveness_tracker import PlanEffectivenessTracker
                            tracker = PlanEffectivenessTracker()
                            
                            for plan_id, ticket, executed_at, symbol, direction in plans_missing_data:
                                try:
                                    # Check MT5 for trade outcome
                                    mt5_outcome = tracker._get_mt5_trade_outcome(ticket, executed_at)
                                    
                                    if mt5_outcome:
                                        status = mt5_outcome.get('status')
                                        
                                        if status == 'closed':
                                            # Trade is closed - update plan
                                            exit_price = mt5_outcome.get('exit_price')
                                            profit_loss = mt5_outcome.get('profit', 0)
                                            close_time = mt5_outcome.get('close_time')
                                            
                                            if close_time:
                                                if isinstance(close_time, datetime):
                                                    close_time_iso = close_time.isoformat()
                                                else:
                                                    close_time_iso = str(close_time)
                                            else:
                                                close_time_iso = None
                                            
                                            # Determine close reason
                                            if profit_loss and profit_loss > 0.5:
                                                close_reason = "TP"
                                            elif profit_loss and profit_loss < -0.5:
                                                close_reason = "SL"
                                            else:
                                                close_reason = "Breakeven"
                                            
                                            # Update plan
                                            plan_cursor.execute("""
                                                UPDATE trade_plans
                                                SET profit_loss = ?,
                                                    exit_price = ?,
                                                    close_time = ?,
                                                    close_reason = ?,
                                                    status = 'closed'
                                                WHERE plan_id = ? AND ticket = ?
                                            """, (profit_loss, exit_price, close_time_iso, close_reason, plan_id, ticket))
                                            
                                            plan_conn.commit()
                                            updated_count += 1
                                            synced_count += 1
                                            logger.debug(f"Synced trade {ticket} to plan {plan_id} from MT5: P/L=${profit_loss:.2f}")
                                        
                                        elif status == 'open':
                                            # Trade is still open - no update needed
                                            logger.debug(f"Trade {ticket} (plan {plan_id}) is still open")
                                    
                                except Exception as e:
                                    error_msg = f"Error checking MT5 for ticket {ticket} (plan {plan_id}): {e}"
                                    logger.debug(error_msg, exc_info=True)
                                    # Don't add to errors - MT5 might not be available or trade might not exist
                            
                            mt5.shutdown()
                        else:
                            logger.debug("MT5 not initialized - skipping MT5 sync")
                    else:
                        logger.debug("No plans missing close data found")
                        
                except Exception as e:
                    logger.warning(f"Error checking MT5 for missing close data: {e}", exc_info=True)
                    # Don't fail the whole sync if MT5 check fails
            
            plan_conn.close()
            
            return {
                "success": True,
                "synced_count": synced_count,
                "updated_count": updated_count,
                "errors": errors,
                "days_back": days_back
            }
            
        except Exception as e:
            logger.error(f"Error in sync_closed_trades_to_plans: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def get_trade_with_plan(self, ticket: int) -> Optional[Dict[str, Any]]:
        """
        Get closed trade with its originating plan details.
        
        Args:
            ticket: MT5 ticket number
            
        Returns:
            Dict with trade and plan details, or None if not found
        """
        if not self.journal_db_path.exists() or not self.plan_db_path.exists():
            return None
        
        try:
            journal_conn = sqlite3.connect(str(self.journal_db_path))
            plan_conn = sqlite3.connect(str(self.plan_db_path))
            
            journal_cursor = journal_conn.cursor()
            plan_cursor = plan_conn.cursor()
            
            # Get trade from journal
            journal_cursor.execute("""
                SELECT ticket, symbol, side, entry_price, sl, tp, volume,
                       pnl, exit_price, closed_ts, close_reason, plan_id,
                       opened_ts, duration_sec
                FROM trades
                WHERE ticket = ?
            """, (ticket,))
            
            trade_row = journal_cursor.fetchone()
            
            if not trade_row:
                journal_conn.close()
                plan_conn.close()
                return None
            
            # Unpack trade data
            (ticket, symbol, side, entry_price, sl, tp, volume,
             pnl, exit_price, closed_ts, close_reason, plan_id,
             opened_ts, duration_sec) = trade_row
            
            trade_data = {
                "ticket": ticket,
                "symbol": symbol,
                "direction": side,
                "entry_price": entry_price,
                "stop_loss": sl,
                "take_profit": tp,
                "volume": volume,
                "profit_loss": pnl,
                "exit_price": exit_price,
                "close_reason": close_reason,
                "opened_at": datetime.fromtimestamp(opened_ts, tz=timezone.utc).isoformat() if opened_ts else None,
                "closed_at": datetime.fromtimestamp(closed_ts, tz=timezone.utc).isoformat() if closed_ts else None,
                "duration_seconds": duration_sec,
                "plan_id": plan_id
            }
            
            # Get plan details if plan_id exists
            if plan_id:
                plan_cursor.execute("""
                    SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit,
                           volume, conditions, created_at, executed_at, notes, status
                    FROM trade_plans
                    WHERE plan_id = ?
                """, (plan_id,))
                
                plan_row = plan_cursor.fetchone()
                
                if plan_row:
                    (plan_id, plan_symbol, plan_direction, plan_entry, plan_sl, plan_tp,
                     plan_volume, conditions_json, created_at, executed_at, notes, status) = plan_row
                    
                    conditions = json.loads(conditions_json) if conditions_json else {}
                    
                    trade_data["plan"] = {
                        "plan_id": plan_id,
                        "symbol": plan_symbol,
                        "direction": plan_direction,
                        "entry_price": plan_entry,
                        "stop_loss": plan_sl,
                        "take_profit": plan_tp,
                        "volume": plan_volume,
                        "conditions": conditions,
                        "created_at": created_at,
                        "executed_at": executed_at,
                        "notes": notes,
                        "status": status,
                        "strategy_type": conditions.get("strategy_type"),
                        "timeframe": conditions.get("timeframe"),
                        "min_confluence": conditions.get("min_confluence")
                    }
            
            journal_conn.close()
            plan_conn.close()
            
            return trade_data
            
        except Exception as e:
            logger.error(f"Error getting trade with plan for ticket {ticket}: {e}", exc_info=True)
            return None
    
    def get_recent_closed_trades_with_plans(
        self,
        days_back: int = 7,
        symbol: Optional[str] = None,
        by_execution_date: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get recent closed trades with their plan details.
        Queries BOTH journal database AND plan database to ensure all trades are found.
        
        Args:
            days_back: Number of days to look back
            symbol: Optional symbol filter
            by_execution_date: If True, filter by opened_ts (execution date). If False, filter by closed_ts (close date).
            
        Returns:
            List of trade dicts with plan details
        """
        if not self.plan_db_path.exists():
            return []
        
        try:
            plan_conn = sqlite3.connect(str(self.plan_db_path))
            plan_cursor = plan_conn.cursor()
            
            # Get cutoff timestamp
            cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days_back)
            cutoff_iso = cutoff_dt.isoformat()
            
            # First, get executed/closed plans from plan database (these are trades that were executed)
            # NOTE: Plans can have status='executed' (still open) or status='closed' (closed)
            if by_execution_date:
                # Plans that were EXECUTED (opened) in the last X days
                plan_query = """
                    SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit,
                           volume, conditions, created_at, executed_at, ticket, notes, status,
                           profit_loss, exit_price, close_time, close_reason
                    FROM trade_plans
                    WHERE (status = 'executed' OR status = 'closed')
                    AND ticket IS NOT NULL
                    AND executed_at IS NOT NULL
                    AND executed_at >= ?
                """
            else:
                # Plans that were CLOSED in the last X days
                # Include plans with close_time OR status='closed' - we'll also check MT5 for plans without close_time
                plan_query = """
                    SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit,
                           volume, conditions, created_at, executed_at, ticket, notes, status,
                           profit_loss, exit_price, close_time, close_reason
                    FROM trade_plans
                    WHERE (status = 'executed' OR status = 'closed')
                    AND ticket IS NOT NULL
                    AND executed_at IS NOT NULL
                    AND (
                        (close_time IS NOT NULL AND close_time >= ?)
                        OR (status = 'closed' AND executed_at >= ?)
                        OR (close_time IS NULL AND status = 'executed' AND executed_at >= ?)
                    )
                """
            
            if by_execution_date:
                plan_params = [cutoff_iso]
            else:
                # For close date, we need cutoff_iso three times (for the three OR conditions)
                plan_params = [cutoff_iso, cutoff_iso, cutoff_iso]
            
            if symbol:
                plan_query += " AND symbol LIKE ?"
                plan_params.append(f"%{symbol.upper()}%")
            
            # Order by execution date or close date
            if by_execution_date:
                plan_query += " ORDER BY executed_at DESC LIMIT 100"
            else:
                plan_query += " ORDER BY COALESCE(close_time, executed_at) DESC LIMIT 100"
            
            plan_cursor.execute(plan_query, plan_params)
            plan_rows = plan_cursor.fetchall()
            
            # Also query journal database if it exists (for trades logged there)
            journal_trades = {}
            if self.journal_db_path.exists():
                try:
                    journal_conn = sqlite3.connect(str(self.journal_db_path))
                    journal_cursor = journal_conn.cursor()
                    
                    cutoff_ts = int(cutoff_dt.timestamp())
                    
                    # Build query - filter by execution date (opened_ts) or close date (closed_ts)
                    if by_execution_date:
                        query = """
                            SELECT ticket, symbol, side, entry_price, sl, tp, volume,
                                   pnl, exit_price, closed_ts, close_reason, plan_id,
                                   opened_ts, duration_sec
                            FROM trades
                            WHERE opened_ts >= ?
                        """
                    else:
                        query = """
                            SELECT ticket, symbol, side, entry_price, sl, tp, volume,
                                   pnl, exit_price, closed_ts, close_reason, plan_id,
                                   opened_ts, duration_sec
                            FROM trades
                            WHERE closed_ts IS NOT NULL 
                            AND closed_ts >= ?
                        """
                    params = [cutoff_ts]
                    
                    if symbol:
                        query += " AND symbol = ?"
                        params.append(symbol.upper())
                    
                    query += " ORDER BY opened_ts DESC LIMIT 100" if by_execution_date else " ORDER BY closed_ts DESC LIMIT 100"
                    
                    journal_cursor.execute(query, params)
                    journal_rows = journal_cursor.fetchall()
                    
                    # Index journal trades by ticket for deduplication
                    for row in journal_rows:
                        (ticket, symbol_j, side, entry_price, sl, tp, volume,
                         pnl, exit_price, closed_ts, close_reason, plan_id,
                         opened_ts, duration_sec) = row
                        journal_trades[ticket] = {
                            "ticket": ticket,
                            "symbol": symbol_j,
                            "side": side,
                            "entry_price": entry_price,
                            "sl": sl,
                            "tp": tp,
                            "volume": volume,
                            "pnl": pnl,
                            "exit_price": exit_price,
                            "closed_ts": closed_ts,
                            "close_reason": close_reason,
                            "plan_id": plan_id,
                            "opened_ts": opened_ts,
                            "duration_sec": duration_sec
                        }
                    
                    journal_conn.close()
                except Exception as e:
                    logger.warning(f"Error querying journal database: {e}", exc_info=True)
            
            # Process plan rows and combine with journal data
            trades = []
            processed_tickets = set()
            
            for plan_row in plan_rows:
                (plan_id, plan_symbol, plan_direction, plan_entry, plan_sl, plan_tp,
                 plan_volume, conditions_json, created_at, executed_at, ticket, notes, status,
                 profit_loss, exit_price, close_time, close_reason) = plan_row
                
                # Skip if already processed (from journal)
                if ticket in processed_tickets:
                    continue
                
                processed_tickets.add(ticket)
                
                # Get journal data if available (for more accurate close info)
                journal_data = journal_trades.get(ticket, {})
                
                # If no close_time in plan and not in journal, check MT5 to see if trade is closed
                close_time_plan = close_time
                exit_price_plan = exit_price
                profit_loss_plan = profit_loss
                close_reason_plan = close_reason
                
                if not close_time_plan and not journal_data.get("closed_ts") and MT5_AVAILABLE:
                    # Check MT5 to see if trade is closed
                    try:
                        mt5_initialized = mt5.initialize()
                        if mt5_initialized:
                            # Check if position is still open
                            positions = mt5.positions_get(ticket=ticket)
                            if not positions or len(positions) == 0:
                                # Position is closed - get close info from MT5 history
                                from infra.plan_effectiveness_tracker import PlanEffectivenessTracker
                                tracker = PlanEffectivenessTracker()
                                mt5_outcome = tracker._get_mt5_trade_outcome(ticket, executed_at)
                                
                                if mt5_outcome and mt5_outcome.get('status') == 'closed':
                                    exit_price_plan = mt5_outcome.get('exit_price')
                                    profit_loss_plan = mt5_outcome.get('profit', 0)
                                    close_time_plan = mt5_outcome.get('close_time')
                                    if close_time_plan:
                                        close_time_plan = close_time_plan.isoformat()
                                    # Determine close reason from profit
                                    if profit_loss_plan and profit_loss_plan > 0.5:
                                        close_reason_plan = "TP"
                                    elif profit_loss_plan and profit_loss_plan < -0.5:
                                        close_reason_plan = "SL"
                                    else:
                                        close_reason_plan = "Breakeven"
                    except Exception as e:
                        logger.debug(f"Error checking MT5 for ticket {ticket}: {e}")
                
                # Use journal data if available, otherwise use plan data (or MT5 data)
                trade_data = {
                    "ticket": ticket,
                    "symbol": journal_data.get("symbol") or plan_symbol,
                    "direction": journal_data.get("side") or plan_direction,
                    "entry_price": journal_data.get("entry_price") or plan_entry,
                    "stop_loss": journal_data.get("sl") or plan_sl,
                    "take_profit": journal_data.get("tp") or plan_tp,
                    "volume": journal_data.get("volume") or plan_volume,
                    "profit_loss": journal_data.get("pnl") or profit_loss_plan,
                    "exit_price": journal_data.get("exit_price") or exit_price_plan,
                    "close_reason": journal_data.get("close_reason") or close_reason_plan,
                    "opened_at": executed_at,  # Use executed_at from plan
                    "closed_at": (journal_data.get("closed_ts") and datetime.fromtimestamp(journal_data["closed_ts"], tz=timezone.utc).isoformat()) or close_time_plan,
                    "duration_seconds": journal_data.get("duration_sec"),
                    "plan_id": plan_id
                }
                
                # If filtering by close date, only include closed trades
                if not by_execution_date and not trade_data["closed_at"]:
                    # Trade is still open - skip
                    continue
                
                # Calculate duration if not available
                if not trade_data["duration_seconds"] and trade_data["opened_at"] and trade_data["closed_at"]:
                    try:
                        opened_dt = datetime.fromisoformat(trade_data["opened_at"].replace('Z', '+00:00'))
                        closed_dt = datetime.fromisoformat(trade_data["closed_at"].replace('Z', '+00:00'))
                        trade_data["duration_seconds"] = int((closed_dt - opened_dt).total_seconds())
                    except:
                        pass
                
                # Get plan details
                conditions = json.loads(conditions_json) if conditions_json else {}
                
                trade_data["plan"] = {
                    "plan_id": plan_id,
                    "symbol": plan_symbol,
                    "direction": plan_direction,
                    "entry_price": plan_entry,
                    "stop_loss": plan_sl,
                    "take_profit": plan_tp,
                    "volume": plan_volume,
                    "conditions": conditions,
                    "created_at": created_at,
                    "executed_at": executed_at,
                    "notes": notes,
                    "status": status,
                    "strategy_type": conditions.get("strategy_type"),
                    "timeframe": conditions.get("timeframe"),
                    "min_confluence": conditions.get("min_confluence")
                }
                
                trades.append(trade_data)
            
            # Also add journal trades that don't have plans (for completeness)
            for ticket, journal_data in journal_trades.items():
                if ticket not in processed_tickets:
                    # This trade is in journal but not in plan database (manual trade or old trade)
                    trade_data = {
                        "ticket": ticket,
                        "symbol": journal_data["symbol"],
                        "direction": journal_data["side"],
                        "entry_price": journal_data["entry_price"],
                        "stop_loss": journal_data.get("sl"),
                        "take_profit": journal_data.get("tp"),
                        "volume": journal_data.get("volume"),
                        "profit_loss": journal_data.get("pnl"),
                        "exit_price": journal_data.get("exit_price"),
                        "close_reason": journal_data.get("close_reason"),
                        "opened_at": datetime.fromtimestamp(journal_data["opened_ts"], tz=timezone.utc).isoformat() if journal_data.get("opened_ts") else None,
                        "closed_at": datetime.fromtimestamp(journal_data["closed_ts"], tz=timezone.utc).isoformat() if journal_data.get("closed_ts") else None,
                        "duration_seconds": journal_data.get("duration_sec"),
                        "plan_id": journal_data.get("plan_id")
                    }
                    
                    # Get plan details if plan_id exists
                    plan_id = journal_data.get("plan_id")
                    if plan_id:
                        plan_cursor.execute("""
                            SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit,
                                   volume, conditions, created_at, executed_at, notes, status
                            FROM trade_plans
                            WHERE plan_id = ?
                        """, (plan_id,))
                        
                        plan_row = plan_cursor.fetchone()
                        
                        if plan_row:
                            (plan_id, plan_symbol, plan_direction, plan_entry, plan_sl, plan_tp,
                             plan_volume, conditions_json, created_at, executed_at, notes, status) = plan_row
                            
                            conditions = json.loads(conditions_json) if conditions_json else {}
                            
                            trade_data["plan"] = {
                                "plan_id": plan_id,
                                "symbol": plan_symbol,
                                "direction": plan_direction,
                                "entry_price": plan_entry,
                                "stop_loss": plan_sl,
                                "take_profit": plan_tp,
                                "volume": plan_volume,
                                "conditions": conditions,
                                "created_at": created_at,
                                "executed_at": executed_at,
                                "notes": notes,
                                "status": status,
                                "strategy_type": conditions.get("strategy_type"),
                                "timeframe": conditions.get("timeframe"),
                                "min_confluence": conditions.get("min_confluence")
                            }
                    
                    trades.append(trade_data)
            
            plan_conn.close()
            
            # Sort by close time or execution time
            if by_execution_date:
                trades.sort(key=lambda x: x.get("opened_at") or "", reverse=True)
            else:
                trades.sort(key=lambda x: x.get("closed_at") or "", reverse=True)
            
            return trades[:100]  # Limit to 100
            
            trades = []
            
            for trade_row in trade_rows:
                (ticket, symbol, side, entry_price, sl, tp, volume,
                 pnl, exit_price, closed_ts, close_reason, plan_id,
                 opened_ts, duration_sec) = trade_row
                
                trade_data = {
                    "ticket": ticket,
                    "symbol": symbol,
                    "direction": side,
                    "entry_price": entry_price,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "volume": volume,
                    "profit_loss": pnl,
                    "exit_price": exit_price,
                    "close_reason": close_reason,
                    "opened_at": datetime.fromtimestamp(opened_ts, tz=timezone.utc).isoformat() if opened_ts else None,
                    "closed_at": datetime.fromtimestamp(closed_ts, tz=timezone.utc).isoformat() if closed_ts else None,
                    "duration_seconds": duration_sec,
                    "plan_id": plan_id
                }
                
                # Get plan details if plan_id exists
                if plan_id:
                    plan_cursor.execute("""
                        SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit,
                               volume, conditions, created_at, executed_at, notes, status
                        FROM trade_plans
                        WHERE plan_id = ?
                    """, (plan_id,))
                    
                    plan_row = plan_cursor.fetchone()
                    
                    if plan_row:
                        (plan_id, plan_symbol, plan_direction, plan_entry, plan_sl, plan_tp,
                         plan_volume, conditions_json, created_at, executed_at, notes, status) = plan_row
                        
                        conditions = json.loads(conditions_json) if conditions_json else {}
                        
                        trade_data["plan"] = {
                            "plan_id": plan_id,
                            "symbol": plan_symbol,
                            "direction": plan_direction,
                            "entry_price": plan_entry,
                            "stop_loss": plan_sl,
                            "take_profit": plan_tp,
                            "volume": plan_volume,
                            "conditions": conditions,
                            "created_at": created_at,
                            "executed_at": executed_at,
                            "notes": notes,
                            "status": status,
                            "strategy_type": conditions.get("strategy_type"),
                            "timeframe": conditions.get("timeframe"),
                            "min_confluence": conditions.get("min_confluence")
                        }
                
                trades.append(trade_data)
            
            journal_conn.close()
            plan_conn.close()
            
            return trades
            
        except Exception as e:
            logger.error(f"Error getting recent closed trades: {e}", exc_info=True)
            return []
