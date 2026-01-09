"""
Auto-Execution Outcome Tracker
Background task that monitors executed auto-execution plans and updates
profit/loss data when trades close.
"""

import asyncio
import sqlite3
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from infra.plan_effectiveness_tracker import PlanEffectivenessTracker

logger = logging.getLogger(__name__)


class AutoExecutionOutcomeTracker:
    """Tracks and updates profit/loss for auto-execution plans"""
    
    def __init__(self, auto_execution_system):
        """
        Initialize outcome tracker.
        
        Args:
            auto_execution_system: AutoExecutionSystem instance
        """
        self.auto_execution = auto_execution_system
        self.db_path = self.auto_execution.db_path
        self.tracker = PlanEffectivenessTracker()
        self.running = False
    
    async def start(self, interval_seconds: int = 300):
        """
        Start background monitoring task.
        
        Args:
            interval_seconds: How often to check for closed trades (default: 5 minutes)
        """
        self.running = True
        logger.info(f"🚀 Auto-execution outcome tracker started (checking every {interval_seconds}s)")
        
        try:
            # Run immediately on startup, then continue with interval
            await self._check_and_update_outcomes()
        except Exception as e:
            logger.error(f"Error in initial outcome check: {e}", exc_info=True)
            # Continue despite initial error
        
        try:
            while self.running:
                try:
                    await asyncio.sleep(interval_seconds)
                    await self._check_and_update_outcomes()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in auto-execution outcome tracker: {e}", exc_info=True)
                    await asyncio.sleep(60)  # Wait 1 minute before retrying
        except Exception as fatal_error:
            logger.critical(f"FATAL ERROR in auto-execution outcome tracker: {fatal_error}", exc_info=True)
            self.running = False
        finally:
            logger.info("Auto-execution outcome tracker loop stopped")
    
    def stop(self):
        """Stop background monitoring"""
        self.running = False
        logger.info("⏹️ Auto-execution outcome tracker stopped")
    
    async def _check_and_update_outcomes(self):
        """Check executed plans and update profit/loss for closed trades"""
        try:
            # Validate auto_execution system exists
            if not self.auto_execution:
                logger.warning("Auto-execution system is None - cannot check outcomes")
                return
            
            # Get all plans (include_all_statuses=True), then filter by status
            # AutoExecutionSystem.get_status() returns {running, pending_plans, plans}
            try:
                status_result = self.auto_execution.get_status(include_all_statuses=True)
            except Exception as e:
                logger.error(f"Error getting auto-execution status: {e}", exc_info=True)
                return
            
            if not status_result:
                logger.warning("Auto-execution status result is None or empty")
                return
            
            all_plans = status_result.get("plans", [])
            # Filter by executed status in Python (API doesn't support status parameter)
            executed_plans = [p for p in all_plans if p.get("status", "").lower() == "executed"]
            plans_to_check = [p for p in executed_plans if p.get("ticket") and p.get("profit_loss") is None]
            
            if not plans_to_check:
                return
            
            logger.debug(f"Checking {len(plans_to_check)} executed plans for closed trades")
            
            updated_count = 0
            for plan in plans_to_check:
                try:
                    ticket = plan.get("ticket")
                    plan_id = plan.get("plan_id")
                    
                    if not ticket or not plan_id:
                        logger.debug(f"Skipping plan with missing ticket or plan_id: {plan}")
                        continue
                    
                    # Check if trade closed (run blocking MT5 call in thread pool)
                    # Pass executed_at for date range optimization
                    executed_at = plan.get("executed_at")
                    try:
                        loop = asyncio.get_event_loop()
                        outcome = await loop.run_in_executor(
                            None,
                            self.tracker._get_mt5_trade_outcome,
                            ticket,
                            executed_at
                        )
                    except Exception as e:
                        logger.error(f"Error getting trade outcome for ticket {ticket}: {e}", exc_info=True)
                        continue
                    
                    if outcome and outcome.get('status') == 'closed':
                        # Update database with profit/loss and change status to 'closed'
                        success = self._update_plan_with_outcome(plan_id, outcome, update_status=True)
                        if success:
                            updated_count += 1
                    elif outcome and outcome.get('status') == 'open':
                        # Trade is still open - log for debugging
                        logger.debug(f"Plan {plan_id} ticket {ticket} is still open")
                except Exception as e:
                    logger.error(f"Error processing plan {plan.get('plan_id', 'unknown')}: {e}", exc_info=True)
                    # Continue with next plan
            
            if updated_count > 0:
                logger.info(f"✅ Updated {updated_count} auto-execution plans with profit/loss")
        
        except Exception as e:
            logger.error(f"Error checking auto-execution outcomes: {e}", exc_info=True)
    
    def _update_plan_with_outcome(self, plan_id: str, outcome: Dict[str, Any], update_status: bool = True) -> bool:
        """
        Update plan with profit/loss outcome.
        
        Args:
            plan_id: Plan ID to update
            outcome: Trade outcome from PlanEffectivenessTracker
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            # Use context manager for connection (ensures cleanup on exceptions)
            with sqlite3.connect(str(self.db_path), timeout=10.0) as conn:
                c = conn.cursor()
                
                # Format close_time: _get_mt5_trade_outcome returns datetime object
                close_time = outcome.get('close_time')
                if isinstance(close_time, datetime):
                    close_time_iso = close_time.isoformat()
                elif isinstance(close_time, (int, float)):
                    close_time_iso = datetime.fromtimestamp(close_time).isoformat()
                elif close_time is None:
                    close_time_iso = None
                else:
                    close_time_iso = str(close_time)  # Fallback for other types
                
                # Determine close reason (simplified - could be enhanced)
                close_reason = 'closed'  # Default
                # Could check outcome for more details if available
                
                # Update profit/loss and optionally change status from 'executed' to 'closed'
                if update_status:
                    c.execute("""
                        UPDATE trade_plans 
                        SET profit_loss = ?,
                            exit_price = ?,
                            close_time = ?,
                            close_reason = ?,
                            status = 'closed'
                        WHERE plan_id = ? AND status = 'executed'
                    """, (
                        outcome.get('profit', 0),
                        outcome.get('exit_price'),
                        close_time_iso,
                        close_reason,
                        plan_id
                    ))
                else:
                    c.execute("""
                        UPDATE trade_plans 
                        SET profit_loss = ?,
                            exit_price = ?,
                            close_time = ?,
                            close_reason = ?
                        WHERE plan_id = ?
                    """, (
                        outcome.get('profit', 0),
                        outcome.get('exit_price'),
                        close_time_iso,
                        close_reason,
                        plan_id
                    ))
                
                conn.commit()
                # Connection automatically closed by context manager
            
            logger.debug(f"✅ Updated plan {plan_id} with profit/loss: ${outcome.get('profit', 0):.2f}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating plan {plan_id} with outcome: {e}", exc_info=True)
            return False

