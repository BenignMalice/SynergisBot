"""
Auto Execution System - ChatGPT Trade Plan Monitor
Monitors conditions and executes trades automatically when conditions are met.
"""

import json
import sqlite3
import logging
import time
import threading
import traceback
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path
from collections import OrderedDict  # Phase 1.1: For LRU price cache
from contextlib import contextmanager  # Phase 3.1: For database context manager
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeoutError  # Phase 4.1: For parallel condition checking
import os  # Phase 4.1: For os.cpu_count()
import MetaTrader5 as mt5
import requests
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class TradePlan:
    """Represents a trade plan with conditions to monitor"""
    plan_id: str
    symbol: str
    direction: str  # BUY or SELL
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float
    conditions: Dict[str, Any]  # Conditions to monitor
    created_at: str
    created_by: str  # "chatgpt" or "user"
    status: str  # "pending", "executed", "cancelled", "expired"
    expires_at: Optional[str] = None
    executed_at: Optional[str] = None
    ticket: Optional[int] = None
    pending_order_ticket: Optional[int] = None  # Phase 2.1: Ticket for pending orders (stop/limit)
    notes: Optional[str] = None
    # NEW: Profit/loss fields (added by migration)
    profit_loss: Optional[float] = None
    exit_price: Optional[float] = None
    close_time: Optional[str] = None
    close_reason: Optional[str] = None
    # Phase 1: Zone tracking fields
    zone_entry_tracked: Optional[bool] = False
    zone_entry_time: Optional[str] = None
    zone_exit_time: Optional[str] = None
    # Phase 2: Multi-level entry support
    entry_levels: Optional[List[Dict[str, Any]]] = None
    # Phase 3: Conditional cancellation tracking
    cancellation_reason: Optional[str] = None
    last_cancellation_check: Optional[str] = None
    # Phase 4: Re-evaluation tracking
    last_re_evaluation: Optional[str] = None
    re_evaluation_count_today: Optional[int] = 0
    re_evaluation_count_date: Optional[str] = None
    # Phase 2.4: Kill-switch flag
    kill_switch_triggered: Optional[bool] = False

class AutoExecutionSystem:
    """Monitors trade plans and executes when conditions are met"""
    
    @staticmethod
    def _is_forex_pair(symbol: str) -> bool:
        """Check if symbol is a forex pair (not BTC or XAU)."""
        symbol_upper = symbol.upper()
        # Forex pairs typically contain currency codes like USD, EUR, GBP, JPY, CHF, AUD, CAD, NZD
        # Exclude BTC and XAU (crypto/commodity)
        if 'BTC' in symbol_upper or 'XAU' in symbol_upper or 'GOLD' in symbol_upper:
            return False
        # Common forex currency codes
        forex_codes = ['USD', 'EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD']
        # Check if symbol contains at least 2 forex currency codes
        count = sum(1 for code in forex_codes if code in symbol_upper)
        return count >= 2
    
    def _is_plan_created_during_weekend(self, plan: TradePlan) -> bool:
        """
        Check if plan was created during weekend hours (Fri 23:00 UTC → Mon 03:00 UTC).
        
        Uses multiple detection methods:
        1. Check plan.conditions.get("session") == "Weekend"
        2. Check plan.notes for "weekend" keyword
        3. Check creation time if weekend was active at that time
        """
        try:
            from infra.weekend_profile_manager import WeekendProfileManager
            weekend_manager = WeekendProfileManager()
            
            # Method 1: Check session attribute in conditions
            if plan.conditions and plan.conditions.get("session") == "Weekend":
                return True
            
            # Method 2: Check notes for weekend keyword
            if plan.notes and "weekend" in plan.notes.lower():
                return True
            
            # Method 3: Check if creation time was during weekend
            try:
                created_at_dt = datetime.fromisoformat(plan.created_at.replace('Z', '+00:00'))
                if created_at_dt.tzinfo is None:
                    created_at_dt = created_at_dt.replace(tzinfo=timezone.utc)
                
                if hasattr(weekend_manager, 'is_weekend_active_at_time'):
                    return weekend_manager.is_weekend_active_at_time(created_at_dt)
                else:
                    # Fallback: check weekday and hour
                    weekday = created_at_dt.weekday()
                    hour = created_at_dt.hour
                    return (
                        (weekday == 4 and hour >= 23) or  # Fri 23:00+
                        weekday == 5 or  # Saturday
                        weekday == 6 or  # Sunday
                        (weekday == 0 and hour < 3)  # Mon < 03:00
                    )
            except Exception as e:
                logger.debug(f"Could not check creation time for plan {plan.plan_id}: {e}")
                return False
                
        except Exception as e:
            logger.warning(f"Error checking if plan was created during weekend: {e}")
            return False
    
    def _determine_order_type(self, plan: TradePlan) -> str:
        """
        Determine MT5 order type based on plan direction and order_type condition.
        
        Args:
            plan: TradePlan with order_type condition
            
        Returns:
            - "market" → Use open_order() (immediate execution)
            - "buy_stop", "buy_limit", "sell_stop", "sell_limit" → Use pending_order()
        """
        order_type = plan.conditions.get("order_type", "market") if plan.conditions else "market"
        direction = plan.direction.upper()
        
        # Default to market if not specified
        if order_type is None or order_type == "market":
            return "market"
        
        # Map order_type + direction to MT5 pending order type
        if direction == "BUY":
            if order_type == "stop":
                return "buy_stop"  # BUY STOP: Entry above current price
            elif order_type == "limit":
                return "buy_limit"  # BUY LIMIT: Entry below current price
        else:  # SELL
            if order_type == "stop":
                return "sell_stop"  # SELL STOP: Entry below current price
            elif order_type == "limit":
                return "sell_limit"  # SELL LIMIT: Entry above current price
        
        # Default to market if invalid order_type
        logger.warning(f"Invalid order_type '{order_type}' for {direction} - defaulting to market")
        return "market"
    
    def _validate_pending_order_entry(self, plan: TradePlan, order_type_str: str, 
                                      current_price: float) -> tuple[bool, Optional[str]]:
        """
        Validate entry price is valid for pending order type.
        
        Args:
            plan: TradePlan to validate
            order_type_str: Order type ("buy_stop", "buy_limit", "sell_stop", "sell_limit")
            current_price: Current market price (midpoint of bid/ask)
            
        Returns:
            (is_valid, error_message)
        """
        entry_price = plan.entry_price
        
        if order_type_str == "buy_stop":
            # BUY STOP: Entry must be above current price
            if entry_price <= current_price:
                return False, f"BUY STOP entry {entry_price} must be above current {current_price}"
        elif order_type_str == "sell_stop":
            # SELL STOP: Entry must be below current price
            if entry_price >= current_price:
                return False, f"SELL STOP entry {entry_price} must be below current {current_price}"
        elif order_type_str == "buy_limit":
            # BUY LIMIT: Entry must be below current price
            if entry_price >= current_price:
                return False, f"BUY LIMIT entry {entry_price} must be below current {current_price}"
        elif order_type_str == "sell_limit":
            # SELL LIMIT: Entry must be above current price
            if entry_price <= current_price:
                return False, f"SELL LIMIT entry {entry_price} must be above current {current_price}"
        
        return True, None
    
    def _check_weekend_plan_expiration(self, plan: TradePlan) -> bool:
        """
        Check if weekend plan should expire (24h if price not near entry).
        
        Weekend plans expire after 24h if price is more than 0.5% away from entry.
        Only applies to BTCUSDc plans created during weekend hours.
        
        Returns:
            True if plan should expire, False otherwise
        """
        try:
            # Only check BTCUSDc plans
            if plan.symbol.upper() not in ["BTCUSDc", "BTCUSD"]:
                return False
            
            # Check if plan was created during weekend
            if not self._is_plan_created_during_weekend(plan):
                return False
            
            # Check if plan is older than 24 hours
            try:
                created_at_dt = datetime.fromisoformat(plan.created_at.replace('Z', '+00:00'))
                if created_at_dt.tzinfo is None:
                    created_at_dt = created_at_dt.replace(tzinfo=timezone.utc)
                
                now_utc = datetime.now(timezone.utc)
                plan_age = now_utc - created_at_dt
                
                if plan_age <= timedelta(hours=24):
                    return False  # Plan is less than 24h old, don't expire yet
                
                # Plan is older than 24h - check if price is near entry
                try:
                    # Get current price
                    if not self.mt5_service:
                        from infra.mt5_service import MT5Service
                        self.mt5_service = MT5Service()
                    
                    if not self.mt5_service.connect():
                        logger.warning(f"MT5 not connected, cannot check price distance for plan {plan.plan_id}")
                        return False  # Don't expire if we can't check price
                    
                    symbol_norm = plan.symbol.upper()
                    if not symbol_norm.endswith('C'):
                        symbol_norm = symbol_norm + 'C'
                    
                    tick = mt5.symbol_info_tick(symbol_norm)
                    if not tick:
                        logger.warning(f"Could not get tick for {symbol_norm}, cannot check price distance")
                        return False
                    
                    current_price = (tick.bid + tick.ask) / 2
                    entry_distance_pct = abs(current_price - plan.entry_price) / plan.entry_price * 100
                    
                    # If price is more than 0.5% away from entry, expire plan
                    if entry_distance_pct > 0.5:
                        logger.info(
                            f"Weekend plan {plan.plan_id} expired: price {entry_distance_pct:.2f}% away from entry "
                            f"after {plan_age.total_seconds() / 3600:.1f} hours"
                        )
                        return True
                    
                    return False  # Price is near entry, don't expire
                    
                except Exception as e:
                    logger.warning(f"Error checking price distance for weekend plan {plan.plan_id}: {e}")
                    return False  # Don't expire if we can't check price
                    
            except Exception as e:
                logger.warning(f"Error parsing created_at for weekend plan {plan.plan_id}: {e}")
                return False
                
        except Exception as e:
            logger.warning(f"Error checking weekend plan expiration for {plan.plan_id}: {e}")
            return False
    
    def _load_adaptive_config(self) -> Dict[str, Any]:
        """Load adaptive execution configuration from config file"""
        config_path = Path("config/auto_execution_adaptive_config.json")
        try:
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    logger.debug(f"Loaded adaptive config from {config_path}")
                    return config
            else:
                logger.warning(f"Adaptive config file not found: {config_path}, using defaults")
                return {}
        except Exception as e:
            logger.warning(f"Error loading adaptive config: {e}, using defaults")
            return {}
    
    def _check_plan_cancellation_conditions(self, plan: TradePlan) -> Optional[Dict[str, Any]]:
        """
        Check if plan should be cancelled based on conditional cancellation rules (Phase 3).
        
        Priority order (stop checking once high-priority condition cancels):
        1. Condition Invalidation (highest - if impossible, cancel immediately)
        2. Structure Cancellation (high - if structure broken)
        3. Price Distance Cancellation (medium - may recover)
        4. Time-Based Cancellation (low - may still be valid)
        
        Returns:
            Dict with 'should_cancel' (bool), 'reason' (str), 'priority' (str) if cancellation needed
            None if plan should not be cancelled
        """
        try:
            # Load config if not already loaded
            if not hasattr(self, '_adaptive_config') or self._adaptive_config is None:
                self._adaptive_config = self._load_adaptive_config()
            
            cancellation_rules = self._adaptive_config.get('cancellation_rules', {})
            
            # Priority 1: Condition Invalidation (highest priority)
            if cancellation_rules.get('condition_invalidation', {}).get('enabled', True):
                try:
                    # Check if last cancellation check was recent enough
                    last_check = plan.last_cancellation_check
                    check_interval = cancellation_rules.get('condition_invalidation', {}).get('check_interval_minutes', 15)
                    
                    should_check = True
                    if last_check:
                        try:
                            last_check_dt = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
                            if last_check_dt.tzinfo is None:
                                last_check_dt = last_check_dt.replace(tzinfo=timezone.utc)
                            now_utc = datetime.now(timezone.utc)
                            time_since_check = (now_utc - last_check_dt).total_seconds() / 60.0
                            should_check = time_since_check >= check_interval
                        except Exception:
                            should_check = True  # If parsing fails, check anyway
                    
                    if should_check:
                        # Check if order block is invalidated
                        # Note: Full order block validation is done in _check_conditions
                        # This is a simplified check - we'll rely on price distance and time-based cancellation
                        # for now. Full condition invalidation can be enhanced later.
                        
                        # Check if liquidity sweep already occurred
                        if plan.conditions.get('liquidity_sweep'):
                            # If liquidity sweep was expected but already happened, cancel
                            # This is a simplified check - full implementation would require sweep detection
                            pass  # TODO: Implement liquidity sweep validation
                        
                        # Update last cancellation check time
                        plan.last_cancellation_check = datetime.now(timezone.utc).isoformat()
                except Exception as e:
                    logger.debug(f"Error checking condition invalidation for {plan.plan_id}: {e}")
            
            # Priority 2: Structure Cancellation (high priority)
            if cancellation_rules.get('structure_cancellation', {}).get('enabled', True):
                try:
                    last_check = plan.last_cancellation_check
                    check_interval = cancellation_rules.get('structure_cancellation', {}).get('check_interval_minutes', 60)
                    
                    should_check = True
                    if last_check:
                        try:
                            last_check_dt = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
                            if last_check_dt.tzinfo is None:
                                last_check_dt = last_check_dt.replace(tzinfo=timezone.utc)
                            now_utc = datetime.now(timezone.utc)
                            time_since_check = (now_utc - last_check_dt).total_seconds() / 60.0
                            should_check = time_since_check >= check_interval
                        except Exception:
                            should_check = True
                    
                    if should_check:
                        # Check if market structure invalidates setup
                        # For BUY: Cancel if price breaks below significant support
                        # For SELL: Cancel if price breaks above significant resistance
                        # This is a simplified check - full implementation would require structure analysis
                        # TODO: Integrate with multi_timeframe_analyzer for structure checks
                        pass  # Placeholder for structure cancellation logic
                except Exception as e:
                    logger.debug(f"Error checking structure cancellation for {plan.plan_id}: {e}")
            
            # Priority 3: Price Distance Cancellation (medium priority)
            if cancellation_rules.get('price_distance_cancellation', {}).get('enabled', True):
                try:
                    # Get price distance threshold for symbol
                    thresholds = cancellation_rules.get('price_distance_thresholds', {})
                    # Try exact symbol match first, then normalized symbol, then default
                    symbol_key = plan.symbol.upper()
                    threshold_pct = thresholds.get(symbol_key, thresholds.get(symbol_key.rstrip('Cc') + 'c', thresholds.get('default', 0.5)))
                    
                    # Get current price
                    if not self.mt5_service:
                        from infra.mt5_service import MT5Service
                        self.mt5_service = MT5Service()
                    
                    symbol_norm = plan.symbol.upper().rstrip('Cc') + 'c'
                    tick = self.mt5_service.get_symbol_tick(symbol_norm)
                    if not tick:
                        return None  # Can't check without price
                    
                    current_price = tick.bid if plan.direction == "BUY" else tick.ask
                    
                    # Calculate price distance percentage
                    if plan.entry_levels:
                        # For multi-level plans, use the closest entry level
                        entry_prices = [level.get('price', plan.entry_price) for level in plan.entry_levels]
                        closest_entry = min(entry_prices, key=lambda p: abs(p - current_price))
                        entry_price = closest_entry
                    else:
                        entry_price = plan.entry_price
                    
                    price_distance_pct = abs(current_price - entry_price) / entry_price * 100.0
                    
                    if price_distance_pct > threshold_pct:
                        reason = f"Price moved {price_distance_pct:.2f}% away from entry (threshold: {threshold_pct}%)"
                        logger.info(f"Plan {plan.plan_id}: {reason}")
                        return {
                            'should_cancel': True,
                            'reason': reason,
                            'priority': 'medium'
                        }
                except Exception as e:
                    logger.debug(f"Error checking price distance cancellation for {plan.plan_id}: {e}")
            
            # Priority 4: Time-Based Cancellation (low priority)
            if cancellation_rules.get('time_based_cancellation', {}).get('enabled', True):
                try:
                    max_age_hours = cancellation_rules.get('time_based_cancellation', {}).get('max_age_hours', 24)
                    price_distance_threshold = cancellation_rules.get('time_based_cancellation', {}).get('price_distance_threshold', 0.3)
                    
                    # Check plan age
                    created_at_dt = datetime.fromisoformat(plan.created_at.replace('Z', '+00:00'))
                    if created_at_dt.tzinfo is None:
                        created_at_dt = created_at_dt.replace(tzinfo=timezone.utc)
                    now_utc = datetime.now(timezone.utc)
                    plan_age_hours = (now_utc - created_at_dt).total_seconds() / 3600.0
                    
                    if plan_age_hours > max_age_hours:
                        # Check if price is still far from entry
                        if not self.mt5_service:
                            from infra.mt5_service import MT5Service
                            self.mt5_service = MT5Service()
                        
                        symbol_norm = plan.symbol.upper().rstrip('Cc') + 'c'
                        tick = self.mt5_service.get_symbol_tick(symbol_norm)
                        if tick:
                            current_price = tick.bid if plan.direction == "BUY" else tick.ask
                            
                            if plan.entry_levels:
                                entry_prices = [level.get('price', plan.entry_price) for level in plan.entry_levels]
                                closest_entry = min(entry_prices, key=lambda p: abs(p - current_price))
                                entry_price = closest_entry
                            else:
                                entry_price = plan.entry_price
                            
                            price_distance_pct = abs(current_price - entry_price) / entry_price * 100.0
                            
                            if price_distance_pct > price_distance_threshold:
                                reason = f"Plan is {plan_age_hours:.1f}h old and price is {price_distance_pct:.2f}% away from entry"
                                logger.info(f"Plan {plan.plan_id}: {reason}")
                                return {
                                    'should_cancel': True,
                                    'reason': reason,
                                    'priority': 'low'
                                }
                except Exception as e:
                    logger.debug(f"Error checking time-based cancellation for {plan.plan_id}: {e}")
            
            return None  # No cancellation needed
            
        except Exception as e:
            logger.error(f"Error in cancellation check for plan {plan.plan_id}: {e}", exc_info=True)
            return None
    
    def _should_trigger_re_evaluation(self, plan: TradePlan) -> bool:
        """
        Check if plan should trigger re-evaluation based on triggers (Phase 4).
        
        Returns:
            True if re-evaluation should be triggered, False otherwise
        """
        try:
            # Only re-evaluate pending plans
            if plan.status != "pending":
                return False
            
            # Load config if not already loaded
            if not hasattr(self, '_adaptive_config') or self._adaptive_config is None:
                self._adaptive_config = self._load_adaptive_config()
            
            re_eval_rules = self._adaptive_config.get('re_evaluation_rules', {})
            
            if not re_eval_rules.get('enabled', True):
                return False
            
            # Check cooldown
            if plan.last_re_evaluation:
                try:
                    last_eval_dt = datetime.fromisoformat(plan.last_re_evaluation.replace('Z', '+00:00'))
                    if last_eval_dt.tzinfo is None:
                        last_eval_dt = last_eval_dt.replace(tzinfo=timezone.utc)
                    now_utc = datetime.now(timezone.utc)
                    time_since_eval = (now_utc - last_eval_dt).total_seconds() / 60.0
                    cooldown_minutes = re_eval_rules.get('cooldown_minutes', 60)
                    
                    if time_since_eval < cooldown_minutes:
                        return False  # Still in cooldown
                except Exception:
                    pass  # If parsing fails, continue with checks
            
            # Check daily limit
            try:
                today_str = datetime.now(timezone.utc).date().isoformat()
                if plan.re_evaluation_count_date != today_str:
                    # New day - reset count
                    plan.re_evaluation_count_today = 0
                    plan.re_evaluation_count_date = today_str
                
                daily_limit = re_eval_rules.get('daily_limit', 6)
                if (plan.re_evaluation_count_today or 0) >= daily_limit:
                    return False  # Daily limit reached
            except Exception:
                pass  # If date check fails, continue
            
            # Check price movement trigger
            price_movement_threshold = re_eval_rules.get('price_movement_threshold', 0.2)
            try:
                if not self.mt5_service:
                    from infra.mt5_service import MT5Service
                    self.mt5_service = MT5Service()
                
                symbol_norm = plan.symbol.upper().rstrip('Cc') + 'c'
                tick = self.mt5_service.get_symbol_tick(symbol_norm)
                if tick:
                    current_price = tick.bid if plan.direction == "BUY" else tick.ask
                    
                    if plan.entry_levels:
                        entry_prices = [level.get('price', plan.entry_price) for level in plan.entry_levels]
                        closest_entry = min(entry_prices, key=lambda p: abs(p - current_price))
                        entry_price = closest_entry
                    else:
                        entry_price = plan.entry_price
                    
                    price_distance_pct = abs(current_price - entry_price) / entry_price * 100.0
                    
                    if price_distance_pct >= price_movement_threshold:
                        return True  # Price moved enough to trigger re-evaluation
            except Exception as e:
                logger.debug(f"Error checking price movement trigger for {plan.plan_id}: {e}")
            
            # Check time-based trigger
            time_trigger_hours = re_eval_rules.get('time_based_trigger_hours', 4)
            try:
                if plan.last_re_evaluation:
                    last_eval_dt = datetime.fromisoformat(plan.last_re_evaluation.replace('Z', '+00:00'))
                    if last_eval_dt.tzinfo is None:
                        last_eval_dt = last_eval_dt.replace(tzinfo=timezone.utc)
                    now_utc = datetime.now(timezone.utc)
                    time_since_eval_hours = (now_utc - last_eval_dt).total_seconds() / 3600.0
                    
                    if time_since_eval_hours >= time_trigger_hours:
                        return True  # Time-based trigger
                else:
                    # Never re-evaluated - check plan age
                    created_at_dt = datetime.fromisoformat(plan.created_at.replace('Z', '+00:00'))
                    if created_at_dt.tzinfo is None:
                        created_at_dt = created_at_dt.replace(tzinfo=timezone.utc)
                    now_utc = datetime.now(timezone.utc)
                    plan_age_hours = (now_utc - created_at_dt).total_seconds() / 3600.0
                    
                    if plan_age_hours >= time_trigger_hours:
                        return True  # Plan is old enough for first re-evaluation
            except Exception as e:
                logger.debug(f"Error checking time-based trigger for {plan.plan_id}: {e}")
            
            return False  # No triggers fired
            
        except Exception as e:
            logger.debug(f"Error checking re-evaluation triggers for {plan.plan_id}: {e}")
            return False
    
    def _re_evaluate_plan(self, plan: TradePlan, force: bool = False) -> Dict[str, Any]:
        """
        Re-evaluate a plan based on current market conditions (Phase 4).
        
        Args:
            plan: TradePlan to re-evaluate
            force: Force re-evaluation even if in cooldown or over daily limit
        
        Returns:
            Dict with 'action' (keep/update/cancel_replace/create_additional), 'recommendation', 'changes', etc.
        """
        try:
            # Check if re-evaluation is allowed
            if not force:
                if not self._should_trigger_re_evaluation(plan):
                    return {
                        'action': 'keep',
                        'recommendation': 'Re-evaluation not needed or in cooldown',
                        'available': False
                    }
            
            # Update re-evaluation tracking
            now_utc = datetime.now(timezone.utc)
            today_str = now_utc.date().isoformat()
            
            if plan.re_evaluation_count_date != today_str:
                plan.re_evaluation_count_today = 0
                plan.re_evaluation_count_date = today_str
            
            plan.last_re_evaluation = now_utc.isoformat()
            plan.re_evaluation_count_today = (plan.re_evaluation_count_today or 0) + 1
            
            # Save re-evaluation tracking to database
            try:
                if self.db_write_queue:
                    self.db_write_queue.queue_operation(
                        operation_type="update_status",
                        plan_id=plan.plan_id,
                        data={
                            "last_re_evaluation": plan.last_re_evaluation,
                            "re_evaluation_count_today": plan.re_evaluation_count_today,
                            "re_evaluation_count_date": plan.re_evaluation_count_date
                        },
                        priority=self.OperationPriority.MEDIUM,
                        wait_for_completion=False,
                        timeout=30.0
                    )
                else:
                    # Fallback to direct write
                    with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                        conn.execute("""
                            UPDATE trade_plans 
                            SET last_re_evaluation = ?, 
                                re_evaluation_count_today = ?,
                                re_evaluation_count_date = ?
                            WHERE plan_id = ?
                        """, (plan.last_re_evaluation, plan.re_evaluation_count_today, plan.re_evaluation_count_date, plan.plan_id))
                        conn.commit()
            except Exception as e:
                logger.debug(f"Error saving re-evaluation tracking: {e}")
            
            # For now, return "keep" as default action
            # Full re-evaluation logic (structure analysis, condition re-check) can be enhanced later
            return {
                'action': 'keep',
                'recommendation': 'Plan conditions still valid, no changes needed',
                'available': True,
                'last_re_evaluation': plan.last_re_evaluation,
                're_evaluation_count_today': plan.re_evaluation_count_today
            }
            
        except Exception as e:
            logger.error(f"Error re-evaluating plan {plan.plan_id}: {e}", exc_info=True)
            return {
                'action': 'keep',
                'recommendation': f'Error during re-evaluation: {str(e)}',
                'available': False,
                'error': str(e)
            }
    
    def __init__(
        self,
        db_path: str = "data/auto_execution.db",
        check_interval: int = 15,  # Phase 1.1: Reduced from 30s to 15s for faster market order execution
        mt5_service=None,
        m1_analyzer=None,
        m1_refresh_manager=None,
        m1_data_fetcher=None,
        asset_profiles=None,
        session_manager=None,
        mtf_analyzer=None,  # NEW: Add MTF analyzer parameter
        streamer=None,  # NEW: MultiTimeframeStreamer for adaptive micro-scalp
        news_service=None  # NEW: NewsService for adaptive micro-scalp
    ):
        self.db_path = Path(db_path)
        self.check_interval = check_interval
        self.running = False
        self.monitor_thread = None
        self.watchdog_thread = None  # CRITICAL: Watchdog thread for continuous health monitoring
        # Thread health monitoring
        self.last_health_check = datetime.now(timezone.utc)
        self.health_check_interval = 30  # Check thread health every 30 seconds (very aggressive for reliability)
        self.thread_restart_count = 0
        self.max_thread_restarts = 10  # Maximum restarts before giving up (increased from 5)
        # Event to allow immediate wake-up when stopping (prevents 30s delay)
        self._stop_event = threading.Event()
        
        # Initialize MT5 service (use provided or create new)
        if mt5_service is None:
            from infra.mt5_service import MT5Service
            self.mt5_service = MT5Service()
            # Don't connect here - will connect when needed
        else:
            self.mt5_service = mt5_service
        
        # M1 Microstructure Integration (optional)
        self.m1_analyzer = m1_analyzer
        self.m1_refresh_manager = m1_refresh_manager
        self.m1_data_fetcher = m1_data_fetcher
        self.asset_profiles = asset_profiles
        self.session_manager = session_manager
        
        # News Service (for adaptive scenario conditions)
        self.news_service = news_service
        
        # Multi-Timeframe Analyzer (for enhanced validation)
        self.mtf_analyzer = mtf_analyzer
        self._mtf_analyzer = None  # Lazy initialization fallback
        
        # Phase III: Correlation Context Calculator (for cross-market correlation conditions)
        self.correlation_calculator = None
        try:
            from infra.correlation_context_calculator import CorrelationContextCalculator
            from infra.market_indices_service import create_market_indices_service
            market_indices = create_market_indices_service()
            self.correlation_calculator = CorrelationContextCalculator(
                mt5_service=self.mt5_service,
                market_indices_service=market_indices
            )
            logger.info("Phase III: Correlation context calculator initialized")
        except Exception as e:
            logger.warning(f"Phase III: Could not initialize correlation calculator: {e}")
        
        # Phase III: Correlation calculation cache (5-10 minute TTL)
        self._correlation_cache: Dict[str, Tuple[Any, datetime]] = {}  # key -> (result, timestamp)
        self._correlation_cache_ttl = 300  # 5 minutes default
        
        # Phase 2.1: AI Pattern Classifier (optional)
        self.pattern_classifier = None
        try:
            from infra.ai_pattern_classifier import AIPatternClassifier
            self.pattern_classifier = AIPatternClassifier()
            logger.info("Phase 2.1: AI Pattern Classifier initialized")
        except Exception as e:
            logger.debug(f"AI Pattern Classifier not available: {e}")
        
        # Micro-Scalp Engine (optional)
        self.micro_scalp_engine = None
        try:
            from infra.micro_scalp_engine import MicroScalpEngine
            from infra.btc_order_flow_metrics import BTCOrderFlowMetrics
            
            # Get BTC order flow if available (try multiple sources)
            btc_order_flow = None
            try:
                # Try to get order_flow_service from multiple sources
                order_flow_service = None
                service_status = "not_found"
                
                # Try 1: desktop_agent.registry (primary source - where it's actually initialized)
                try:
                    from desktop_agent import registry
                    if hasattr(registry, 'order_flow_service'):
                        order_flow_service = registry.order_flow_service
                        if order_flow_service and hasattr(order_flow_service, 'running') and order_flow_service.running:
                            service_status = "running_from_registry"
                            logger.info(f"Order flow service found in desktop_agent.registry and running (symbols: {getattr(order_flow_service, 'symbols', 'unknown')})")
                        elif order_flow_service is None:
                            service_status = "none_in_registry"
                            logger.debug("Order flow service found in registry but is None")
                        elif not order_flow_service.running:
                            service_status = "not_running_in_registry"
                            logger.debug(f"Order flow service in registry but not running (running={order_flow_service.running})")
                except ImportError:
                    logger.debug("desktop_agent module not available for import")
                except Exception as e:
                    logger.debug(f"Error accessing order flow service from registry: {e}")
                
                # Try 2: chatgpt_bot module (fallback)
                if not order_flow_service or not (hasattr(order_flow_service, 'running') and order_flow_service.running):
                    try:
                        import chatgpt_bot
                        if hasattr(chatgpt_bot, 'order_flow_service'):
                            order_flow_service = chatgpt_bot.order_flow_service
                            if order_flow_service and hasattr(order_flow_service, 'running') and order_flow_service.running:
                                service_status = "running_from_chatgpt_bot"
                                logger.info(f"Order flow service found in chatgpt_bot and running (symbols: {getattr(order_flow_service, 'symbols', 'unknown')})")
                            elif order_flow_service is None:
                                if service_status == "not_found":
                                    service_status = "none"
                                logger.debug("Order flow service found in chatgpt_bot but is None")
                            elif not order_flow_service.running:
                                if service_status == "not_found":
                                    service_status = "not_running"
                                logger.debug(f"Order flow service found but not running (running={order_flow_service.running})")
                        else:
                            if service_status == "not_found":
                                service_status = "not_initialized"
                            logger.debug("Order flow service not found in chatgpt_bot module")
                    except ImportError:
                        if service_status == "not_found":
                            service_status = "module_not_imported"
                        logger.debug("chatgpt_bot module not available for import")
                    except Exception as e:
                        if service_status == "not_found":
                            service_status = f"error: {str(e)}"
                        logger.debug(f"Error accessing order flow service from chatgpt_bot: {e}")
                
                # Create BTCOrderFlowMetrics with the order flow service
                # Pre-Phase 0 / Before Phase 1: Add mt5_service parameter for price bar alignment
                if order_flow_service and hasattr(order_flow_service, 'running') and order_flow_service.running:
                    btc_order_flow = BTCOrderFlowMetrics(
                        order_flow_service=order_flow_service,
                        mt5_service=mt5_service  # NEW: Pass MT5 service for Phase 1.2 price bar alignment
                    )
                    logger.info("✅ BTC order flow metrics initialized with active service")
                    logger.info(f"   Order flow service status: RUNNING (symbols: {getattr(order_flow_service, 'symbols', 'unknown')})")
                else:
                    # Fallback: create without service (will show warnings but won't crash)
                    btc_order_flow = BTCOrderFlowMetrics(mt5_service=mt5_service)  # NEW: Still pass mt5_service
                    logger.warning(f"⚠️ BTC order flow metrics initialized WITHOUT service (status: {service_status})")
                    logger.warning("   Note: Order flow metrics require Binance service to be running")
                    logger.warning("   Order flow plans will not execute without order flow service")
                    logger.warning("   This is non-critical - system will continue without order flow data")
            except Exception as e:
                logger.warning(f"BTC order flow metrics initialization failed: {e}")
                logger.debug(f"Traceback: {traceback.format_exc()}")
                pass
            
            # Initialize micro-scalp engine
            if mt5_service and m1_data_fetcher:
                self.micro_scalp_engine = MicroScalpEngine(
                    config_path="config/micro_scalp_config.json",
                    mt5_service=mt5_service,
                    m1_fetcher=m1_data_fetcher,
                    streamer=streamer,  # NEW: Pass streamer for M5/M15 data
                    m1_analyzer=m1_analyzer,
                    session_manager=session_manager,
                    btc_order_flow=btc_order_flow,
                    news_service=news_service  # NEW: Pass news_service for news blackout checks
                )
                logger.info("Micro-scalp engine initialized")
        except Exception as e:
            logger.warning(f"Micro-scalp engine not available: {e}")
        
        # Dynamic Threshold Tuning (Phase 2.3)
        # Get threshold_manager from m1_analyzer if available, or accept as parameter
        self.threshold_manager = getattr(m1_analyzer, 'threshold_manager', None) if m1_analyzer else None
        
        # Real-Time Signal Learning (Phase 2.2)
        # Get signal_learner from m1_analyzer if available, or accept as parameter
        self.signal_learner = getattr(m1_analyzer, 'signal_learner', None) if m1_analyzer else None
        
        # Configuration for M1 integration (Phase 2.1.1)
        self.config = {
            'choch_detection': {
                'debug_confidence_weights': False,
                'use_rolling_mean': False
            },
            'm1_integration': {
                'enabled': True,
                'refresh_before_check': True,
                'stale_threshold_seconds': 180,
                'confidence_threshold': 60,
                'batch_refresh': True,
                'cache_duration_seconds': 30,
                'signal_stale_threshold_seconds': 300  # 5 minutes
            }
        }
        
        # Phase 1.1: Load optimized intervals config (if exists)
        optimized_config_path = Path("config/auto_execution_optimized_intervals.json")
        if optimized_config_path.exists():
            try:
                with open(optimized_config_path, 'r') as f:
                    optimized_config = json.load(f)
                    # Merge into existing config (deep merge for nested dicts)
                    # If JSON has 'optimized_intervals' key, it will replace/merge that section
                    if 'optimized_intervals' in optimized_config:
                        # Deep merge nested dicts to preserve existing config values
                        if 'optimized_intervals' in self.config:
                            # Merge nested dicts recursively
                            def _deep_merge(base: dict, override: dict) -> dict:
                                """Recursively merge nested dicts"""
                                # Create a copy to avoid modifying original
                                result = dict(base)
                                for key, value in override.items():
                                    if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                                        result[key] = _deep_merge(result[key], value)
                                    else:
                                        result[key] = value
                                return result
                            self.config['optimized_intervals'] = _deep_merge(
                                self.config.get('optimized_intervals', {}),
                                optimized_config['optimized_intervals']
                            )
                        else:
                            self.config['optimized_intervals'] = optimized_config['optimized_intervals']
                    else:
                        # If JSON doesn't have 'optimized_intervals', merge top-level keys
                        self.config.update(optimized_config)
            except Exception as e:
                logger.warning(f"Error loading optimized intervals config: {e}, using defaults")
                # Use defaults
                self.config['optimized_intervals'] = {
                    'adaptive_intervals': {'enabled': False},
                    'smart_caching': {'enabled': False},
                    'conditional_checks': {'enabled': False},
                    'batch_operations': {'enabled': False}
                }
        else:
            # Use defaults (feature disabled by default)
            self.config['optimized_intervals'] = {
                'adaptive_intervals': {
                    'enabled': False,  # Disabled by default - enable via config file
                    'default_interval_seconds': 30,
                    'plan_type_intervals': {
                        'm1_micro_scalp': {
                            'base_interval_seconds': 10,
                            'far_interval_seconds': 30,
                            'close_interval_seconds': 5,
                            'price_proximity_multiplier': 2.0
                        },
                        'm5_range_scalp': {
                            'base_interval_seconds': 30,
                            'far_interval_seconds': 60,
                            'close_interval_seconds': 20
                        },
                        'm15_range_scalp': {
                            'base_interval_seconds': 30,
                            'far_interval_seconds': 60,
                            'close_interval_seconds': 20
                        }
                    }
                },
                'smart_caching': {
                    'enabled': False,
                    'm1_cache_ttl_seconds': 20,
                    'invalidate_on_candle_close': True,
                    'prefetch_seconds_before_expiry': 3
                },
                'conditional_checks': {
                    'enabled': False,
                    'price_proximity_filter': True,
                    'proximity_multiplier': 2.0,
                    'min_check_interval_seconds': 10
                },
                'batch_operations': {
                    'enabled': False,
                    'mt5_batch_size': 5,
                    'db_batch_size': 10
                }
            }
        
        # M1 data cache for performance optimization (Phase 2.1.1)
        self._m1_data_cache: Dict[str, Dict[str, Any]] = {}  # symbol -> {data, timestamp, last_signal_timestamp}
        self._m1_cache_timestamps: Dict[str, float] = {}  # symbol -> cache timestamp
        self._last_signal_timestamps: Dict[str, str] = {}  # symbol -> last signal timestamp (for change detection)
        
        # Phase 1.2: Plan type tracking (separate from TradePlan dataclass)
        # NOTE: These are accessed only from monitor thread, so no lock needed
        # If accessed from other threads in future, add locks
        self._plan_types: Dict[str, str] = {}  # plan_id -> plan_type
        self._plan_last_check: Dict[str, datetime] = {}  # plan_id -> last check time (UTC datetime)
        self._plan_last_price: Dict[str, float] = {}  # plan_id -> last known price
        
        # M1 cache invalidation tracking (for candle-close detection)
        # CRITICAL: Initialize here, not in method (avoids hasattr check every time)
        self._m1_latest_candle_times: Dict[str, datetime] = {}  # symbol (normalized) -> latest candle time (UTC datetime)
        
        # Phase 1.2: Price cache for reducing API calls
        self._price_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()  # symbol -> {price, timestamp, bid, ask, access_count}
        self._price_cache_lock: threading.Lock = threading.Lock()  # Thread safety for price cache
        self._price_cache_ttl: int = 5  # 5 seconds TTL
        self._price_cache_max_size: int = 50  # Max 50 symbols in cache
        self._price_cache_hits: int = 0  # Cache hit counter
        self._price_cache_misses: int = 0  # Cache miss counter
        
        # Phase 2.4: Circuit breaker for batch price fetching (per-symbol)
        self._price_fetch_circuit_breakers: Dict[str, Dict[str, Any]] = {}  # symbol -> {failures, last_failure, opened_at}
        self._circuit_breaker_lock: threading.Lock = threading.Lock()  # Thread safety for circuit breakers
        
        # Phase 2.5: Batch fetch metrics
        self._batch_fetch_total: int = 0  # Total batch fetches attempted
        self._batch_fetch_success: int = 0  # Successful batch fetches
        self._batch_fetch_failures: int = 0  # Failed batch fetches
        self._batch_fetch_cache_hits: int = 0  # Symbols served from cache
        self._batch_fetch_api_calls: int = 0  # Actual API calls made
        
        # Phase 3.2: Database connection pooling
        try:
            from app.database.optimized_sqlite_manager import OptimizedSQLiteManager
            self._db_manager: Optional[OptimizedSQLiteManager] = OptimizedSQLiteManager(
                db_path=str(self.db_path),
                config=None  # Use default config
            )
            logger.info("Phase 3: OptimizedSQLiteManager initialized for connection pooling")
        except Exception as e:
            logger.warning(f"Failed to initialize OptimizedSQLiteManager: {e}. Using direct connections.")
            self._db_manager: Optional[OptimizedSQLiteManager] = None
        
        # Phase 3.2: Database connection pooling
        try:
            from app.database.optimized_sqlite_manager import OptimizedSQLiteManager
            self._db_manager: Optional[OptimizedSQLiteManager] = OptimizedSQLiteManager(
                db_path=str(self.db_path),
                config=None  # Use default config
            )
            logger.info("Phase 3: OptimizedSQLiteManager initialized for connection pooling")
        except Exception as e:
            logger.warning(f"Failed to initialize OptimizedSQLiteManager: {e}. Using direct connections.")
            self._db_manager: Optional[OptimizedSQLiteManager] = None
        
        # Pre-fetch thread reference (initialized in start() method)
        self.prefetch_thread: Optional[threading.Thread] = None
        
        # Initialize database
        self._init_database()
        
        # Load adaptive config for Phase 3 (conditional cancellation)
        self._adaptive_config = self._load_adaptive_config()
        
        # Run Phase 1 migration (zone tracking columns)
        try:
            from migrations.migrate_phase1_zone_tracking import migrate_zone_tracking
            migrate_zone_tracking(str(self.db_path))
            logger.info("Phase 1 zone tracking migration completed")
        except Exception as e:
            logger.warning(f"Phase 1 migration failed (non-fatal): {e}")
        
        # Run Phase 2 migration (entry levels column)
        try:
            from migrations.migrate_phase2_entry_levels import migrate_entry_levels
            migrate_entry_levels(str(self.db_path))
            logger.info("Phase 2 entry levels migration completed")
        except Exception as e:
            logger.warning(f"Phase 2 migration failed (non-fatal): {e}")
        
        # Run Phase 3 migration (cancellation tracking)
        try:
            from migrations.migrate_phase3_cancellation_tracking import migrate_phase3_cancellation_tracking
            migrate_phase3_cancellation_tracking(str(self.db_path))
            logger.info("Phase 3 cancellation tracking migration completed")
        except Exception as e:
            logger.warning(f"Phase 3 migration failed (non-fatal): {e}")
        
        # Run Phase III migrations (pattern_history and plan_execution_state)
        try:
            from migrations.migrate_phase3_pattern_history import migrate_pattern_history
            migrate_pattern_history(str(self.db_path))
            logger.info("Phase III pattern_history migration completed")
        except Exception as e:
            logger.warning(f"Phase III pattern_history migration failed (non-fatal): {e}")
        
        try:
            from migrations.migrate_phase3_execution_state import migrate_execution_state
            migrate_execution_state(str(self.db_path))
            logger.info("Phase III plan_execution_state migration completed")
        except Exception as e:
            logger.warning(f"Phase III plan_execution_state migration failed (non-fatal): {e}")
        
        # Initialize database write queue (Phase 0)
        try:
            from infra.database_write_queue import DatabaseWriteQueue, OperationPriority
            self.db_write_queue = DatabaseWriteQueue(
                db_path=str(self.db_path),
                queue_maxsize=1000,
                writer_timeout=30.0,
                retry_delay_base=1.0,
                persistence_path="data/db_write_queue.json"
            )
            self.OperationPriority = OperationPriority
            logger.info("Database write queue initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database write queue: {e}", exc_info=True)
            self.db_write_queue = None
            self.OperationPriority = None
        
        # NEW: Volatility tolerance calculator (Phase 2.5)
        self.volatility_tolerance_calculator = None
        try:
            from infra.volatility_tolerance_calculator import VolatilityToleranceCalculator
            from infra.tolerance_calculator import ToleranceCalculator
            tolerance_calc = ToleranceCalculator()
            # VolatilityToleranceCalculator will load RMAG smoothing config from tolerance_config.json
            self.volatility_tolerance_calculator = VolatilityToleranceCalculator(
                tolerance_calculator=tolerance_calc
            )
            
            # Log config version if available
            try:
                import json
                config_path = Path("config/tolerance_config.json")
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                    config_version = config.get("config_version", "unknown")
                    logger.info(f"Volatility-based tolerance calculator initialized (config_version: {config_version})")
                else:
                    logger.info("Volatility-based tolerance calculator initialized (using defaults)")
            except:
                logger.info("Volatility-based tolerance calculator initialized")
        except Exception as e:
            logger.warning(f"Could not initialize volatility tolerance calculator: {e}")
        
        # Load existing plans
        self.plans = self._load_plans()
        
        # Track execution failures for retry logic
        self.execution_failures: Dict[str, int] = {}  # plan_id -> failure_count
        self.max_execution_retries = 3  # Maximum retries before marking as failed
        
        # Phase III: Correlation calculation cache helper methods
        self._correlation_cache_lock = threading.Lock()
        
        # Track last plan reload time for periodic reloading
        self.last_plan_reload = datetime.now(timezone.utc)
        self.plan_reload_interval = 300  # Reload plans every 5 minutes
        
        # Thread safety: Lock for plans dictionary access
        self.plans_lock = threading.Lock()
        
        # Track invalid symbols to avoid repeated checks
        self.invalid_symbols: Dict[str, int] = {}  # symbol -> failure_count
        self.max_symbol_failures = 3  # Mark symbol as invalid after N failures
        
        # Execution locks to prevent duplicate execution
        self.execution_locks: Dict[str, threading.Lock] = {}  # plan_id -> Lock
        self.execution_locks_lock = threading.Lock()  # Lock for execution_locks dictionary access
        self.executing_plans: set = set()  # Set of plan_ids currently executing
        self.executing_plans_lock = threading.Lock()  # Lock for executing_plans set access
        
        # MT5 connection failure tracking
        self.mt5_connection_failures = 0
        self.mt5_last_failure_time: Optional[datetime] = None
        self.mt5_backoff_seconds = 60  # Skip checking if MT5 down for 60 seconds
        
        # Phase 4.1: Thread-safety locks for parallel condition checking
        self._mt5_state_lock: threading.Lock = threading.Lock()  # For mt5_connection_failures and mt5_last_failure_time
        self._invalid_symbols_lock: threading.Lock = threading.Lock()  # For invalid_symbols dict
        
        # Phase 4.1: Thread pool executor for parallel condition checking (initialized in start())
        self._condition_check_executor: Optional[ThreadPoolExecutor] = None
        
        # Phase 4.1: Circuit breaker for parallel checks (simple counter, not per-symbol)
        self._circuit_breaker_failures: int = 0  # Simple counter for parallel check failures
        self._circuit_breaker_last_failure: Optional[datetime] = None
        
        # Phase 4.1: Plan activity tracking (tracks when conditions were MET, distinct from _plan_last_check)
        self._plan_activity: Dict[str, datetime] = {}  # plan_id -> datetime when conditions were met
        
        # Phase 5: Plan volatility tracking for adaptive intervals
        self._plan_volatility: Dict[str, float] = {}  # symbol -> recent ATR value
        
        # Phase 6: Performance metrics tracking
        self._metrics_start_time: Optional[datetime] = None  # System start time for uptime calculation
        self._metrics_last_log: Optional[datetime] = None  # Last metrics log time
        self._metrics_log_interval: int = 300  # Log metrics every 5 minutes
        self._condition_checks_total: int = 0  # Total condition checks performed
        self._condition_checks_success: int = 0  # Successful condition checks
        self._condition_checks_failed: int = 0  # Failed condition checks
        self._market_orders_executed: int = 0  # Market orders executed (per hour)
        self._parallel_checks_total: int = 0  # Total parallel condition checks
        self._parallel_checks_batches: int = 0  # Total batches processed
        self._cache_cleanup_count: int = 0  # Cache cleanup operations performed
        
        # Cache cleanup tracking
        self.last_cache_cleanup = datetime.now(timezone.utc)
        self.cache_cleanup_interval = 3600  # Clean up cache every hour
        
        # Confluence cache for performance optimization (Phase 1.1 - Confluence-Only Implementation)
        # Initialize confluence cache with error handling
        try:
            self._confluence_cache = {}  # {symbol: (score, timestamp)}
            self._confluence_cache_ttl = 30  # seconds (can be made configurable later)
            self._confluence_cache_lock = threading.Lock()  # Thread safety (must exist)
            self._confluence_cache_stats = {  # Performance tracking (must exist)
                "hits": 0,
                "misses": 0,
                "api_calls": 0
            }
        except Exception as e:
            logger.error(f"Failed to initialize confluence cache: {e}", exc_info=True)
            # Fallback: initialize with minimal setup (degraded performance)
            self._confluence_cache = {}
            self._confluence_cache_ttl = 0  # Disable caching on error
            self._confluence_cache_lock = threading.Lock()  # Still need lock for thread safety
            self._confluence_cache_stats = {"hits": 0, "misses": 0, "api_calls": 0}
        
        # Volume metrics cache for performance optimization (Volume Confirmation Implementation)
        # Initialize volume cache with error handling
        try:
            self._volume_cache = {}  # {(symbol, timeframe): (metrics, timestamp)}
            self._volume_cache_ttl = 30  # seconds (same as confluence cache)
            self._volume_cache_lock = threading.Lock()  # Thread safety
        except Exception as e:
            logger.error(f"Failed to initialize volume cache: {e}", exc_info=True)
            # Fallback: initialize with minimal setup (degraded performance)
            self._volume_cache = {}
            self._volume_cache_ttl = 0  # Disable caching on error
            self._volume_cache_lock = threading.Lock()
        
        # Binance pressure cache (for BTCUSD volume confirmation)
        try:
            self._binance_pressure_cache = {}  # {symbol: (pressure_data, timestamp)}
            self._binance_pressure_cache_lock = threading.Lock()
        except Exception as e:
            logger.error(f"Failed to initialize Binance pressure cache: {e}", exc_info=True)
            self._binance_pressure_cache = {}
            self._binance_pressure_cache_lock = threading.Lock()
        
    def _init_database(self):
        """Initialize SQLite database for trade plans"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trade_plans (
                    plan_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    volume REAL NOT NULL,
                    conditions TEXT NOT NULL,  -- JSON string
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    expires_at TEXT,
                    executed_at TEXT,
                    ticket INTEGER,
                    notes TEXT,
                    profit_loss REAL,
                    exit_price REAL,
                    close_time TEXT,
                    close_reason TEXT,
                    kill_switch_triggered INTEGER DEFAULT 0
                )
            """)
            
            # Migration: Add kill_switch_triggered column if it doesn't exist
            try:
                conn.execute("ALTER TABLE trade_plans ADD COLUMN kill_switch_triggered INTEGER DEFAULT 0")
                conn.commit()
            except sqlite3.OperationalError:
                # Column already exists, skip
                pass
            
            # Phase 3.1: Migration: Add pending_order_ticket column if it doesn't exist
            try:
                conn.execute("ALTER TABLE trade_plans ADD COLUMN pending_order_ticket INTEGER")
                conn.commit()
                logger.info("Added pending_order_ticket column to trade_plans table")
            except sqlite3.OperationalError:
                # Column already exists, skip
                pass
            
            # Migration: Add last_re_evaluation column if it doesn't exist
            try:
                conn.execute("ALTER TABLE trade_plans ADD COLUMN last_re_evaluation TEXT")
                conn.commit()
                logger.info("Added last_re_evaluation column to trade_plans table")
            except sqlite3.OperationalError:
                # Column already exists, skip
                pass
            
            # Migration: Add re_evaluation_count_today column if it doesn't exist
            try:
                conn.execute("ALTER TABLE trade_plans ADD COLUMN re_evaluation_count_today INTEGER DEFAULT 0")
                conn.commit()
                logger.info("Added re_evaluation_count_today column to trade_plans table")
            except sqlite3.OperationalError:
                # Column already exists, skip
                pass
            
            # Migration: Add re_evaluation_count_date column if it doesn't exist
            try:
                conn.execute("ALTER TABLE trade_plans ADD COLUMN re_evaluation_count_date TEXT")
                conn.commit()
                logger.info("Added re_evaluation_count_date column to trade_plans table")
            except sqlite3.OperationalError:
                # Column already exists, skip
                pass
            
    def _validate_plan_data(self, plan_id: str, symbol: str, direction: str, entry_price: float, 
                            stop_loss: float, take_profit: float, volume: float, expires_at: Optional[str]) -> tuple[bool, Optional[str]]:
        """
        Validate plan data for correctness.
        
        Returns:
            (is_valid, error_message)
        """
        # Check for negative prices
        if entry_price <= 0:
            return False, f"Invalid entry_price: {entry_price} (must be positive)"
        if stop_loss <= 0:
            return False, f"Invalid stop_loss: {stop_loss} (must be positive)"
        if take_profit <= 0:
            return False, f"Invalid take_profit: {take_profit} (must be positive)"
        if volume <= 0:
            return False, f"Invalid volume: {volume} (must be positive)"
        
        # Validate SL/TP relationships based on direction
        if direction.upper() == "BUY":
            if stop_loss >= entry_price:
                return False, f"BUY plan: stop_loss ({stop_loss}) must be < entry_price ({entry_price})"
            if take_profit <= entry_price:
                return False, f"BUY plan: take_profit ({take_profit}) must be > entry_price ({entry_price})"
        elif direction.upper() == "SELL":
            if stop_loss <= entry_price:
                return False, f"SELL plan: stop_loss ({stop_loss}) must be > entry_price ({entry_price})"
            if take_profit >= entry_price:
                return False, f"SELL plan: take_profit ({take_profit}) must be < entry_price ({entry_price})"
        else:
            return False, f"Invalid direction: {direction} (must be BUY or SELL)"
        
        # Validate lot size against symbol-specific maximums
        symbol_upper = symbol.upper()
        if "BTC" in symbol_upper or "XAU" in symbol_upper or "GOLD" in symbol_upper:
            max_lot_size = 0.03  # FIXED: Updated from 0.02 to 0.03
        else:
            max_lot_size = 0.05  # FIXED: Updated from 0.04 to 0.05

        if volume > max_lot_size:
            return False, f"Lot size {volume} exceeds maximum for {symbol} (max: {max_lot_size})"
        
        # Validate expires_at format if present
        if expires_at:
            try:
                expires_at_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if expires_at_dt.tzinfo is None:
                    expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)
                # Check if already expired (warn but don't fail)
                if expires_at_dt < datetime.now(timezone.utc):
                    logger.warning(f"Plan {plan_id} has expired expires_at: {expires_at}")
            except (ValueError, AttributeError) as e:
                return False, f"Invalid expires_at format: {expires_at} ({e})"
        
        return True, None
    
    # Phase 3.3: Database context manager
    @contextmanager
    def _get_db_connection(self):
        """
        Get database connection from pool (context manager).
        Auto-returns connection on exit.
        """
        conn = None
        try:
            if self._db_manager:
                conn = self._db_manager.get_connection()
            else:
                # Fallback to direct connection
                conn = sqlite3.connect(self.db_path, timeout=10.0)
            yield conn
        except Exception as e:
            logger.error(f"Error in database context manager: {e}")
            raise
        finally:
            if conn:
                if self._db_manager:
                    self._db_manager.return_connection(conn)
                else:
                    conn.close()
    
    def _load_plans(self) -> Dict[str, TradePlan]:
        """Load all pending trade plans from database"""
        plans = {}
        
        try:
            # Phase 3.4: Use OptimizedSQLiteManager if available
            with self._get_db_connection() as conn:
                # Use UTC for consistent timezone comparison
                now_utc = datetime.now(timezone.utc).isoformat()
                # Phase 3.4: Include pending_order_placed status in query
                cursor = conn.execute("""
                    SELECT * FROM trade_plans 
                    WHERE status IN ('pending', 'pending_order_placed')
                    AND (expires_at IS NULL OR expires_at > ?)
                """, (now_utc,))
                
                # Fetch all rows while connection is still open
                rows = cursor.fetchall()
            
            # Process rows after connection is closed (data is already fetched)
            for row in rows:
                try:
                    plan_id = row[0]
                    symbol = row[1]
                    direction = row[2]
                    entry_price = row[3]
                    stop_loss = row[4]
                    take_profit = row[5]
                    volume = row[6] if row[6] and row[6] > 0 else 0.01
                    conditions_json = row[7]
                    created_at = row[8]
                    created_by = row[9]
                    status = row[10]
                    expires_at = row[11]
                    executed_at = row[12]
                    ticket = row[13]
                    notes = row[14]
                    
                    # Validate plan data
                    is_valid, error_msg = self._validate_plan_data(
                        plan_id, symbol, direction, entry_price, stop_loss, 
                        take_profit, volume, expires_at
                    )
                    if not is_valid:
                        logger.warning(f"Skipping invalid plan {plan_id}: {error_msg}")
                        continue
                    
                    # Parse JSON conditions with error handling
                    try:
                        conditions = json.loads(conditions_json) if conditions_json else {}
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping plan {plan_id}: Invalid JSON in conditions: {e}")
                        continue
                    
                    # Handle new columns (profit_loss, exit_price, close_time, close_reason) - indices 15-18
                    profit_loss = row[15] if len(row) > 15 else None
                    exit_price = row[16] if len(row) > 16 else None
                    close_time = row[17] if len(row) > 17 else None
                    close_reason = row[18] if len(row) > 18 else None
                    # Phase 1: Zone tracking fields - indices 19-21
                    zone_entry_tracked = row[19] if len(row) > 19 else False
                    zone_entry_time = row[20] if len(row) > 20 else None
                    zone_exit_time = row[21] if len(row) > 21 else None
                    # Phase 2: Entry levels - index 22
                    entry_levels_json = row[22] if len(row) > 22 else None
                    entry_levels = None
                    if entry_levels_json:
                        try:
                            entry_levels = json.loads(entry_levels_json)
                        except json.JSONDecodeError:
                            pass
                    # Phase 3: Cancellation tracking - indices 23-24
                    cancellation_reason_retry = row[23] if len(row) > 23 else None
                    last_cancellation_check_retry = row[24] if len(row) > 24 else None
                    # Phase 4: Re-evaluation tracking - indices 25-27
                    last_re_evaluation_retry = row[25] if len(row) > 25 else None
                    re_evaluation_count_today_retry = row[26] if len(row) > 26 else 0
                    re_evaluation_count_date_retry = row[27] if len(row) > 27 else None
                    # Phase 2.4: Kill-switch flag - index 28
                    kill_switch_triggered_retry = bool(row[28]) if len(row) > 28 else False
                    # Phase 3: Pending order ticket - index 29
                    pending_order_ticket_retry = row[29] if len(row) > 29 else None
                    
                    plan = TradePlan(
                        plan_id=plan_id,
                        symbol=symbol,
                        direction=direction,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        volume=volume,
                        conditions=conditions,
                        created_at=created_at,
                        created_by=created_by,
                        status=status,
                        expires_at=expires_at,
                        executed_at=executed_at,
                        ticket=ticket,
                        notes=notes,
                        zone_entry_tracked=bool(zone_entry_tracked) if zone_entry_tracked is not None else False,
                        zone_entry_time=zone_entry_time,
                        zone_exit_time=zone_exit_time,
                        entry_levels=entry_levels,
                        cancellation_reason=cancellation_reason_retry,
                        last_cancellation_check=last_cancellation_check_retry,
                        last_re_evaluation=last_re_evaluation_retry,
                        re_evaluation_count_today=re_evaluation_count_today_retry if re_evaluation_count_today_retry is not None else 0,
                        re_evaluation_count_date=re_evaluation_count_date_retry,
                        kill_switch_triggered=kill_switch_triggered_retry,
                        pending_order_ticket=pending_order_ticket_retry  # Phase 3: Pending order ticket
                    )
                    plans[plan.plan_id] = plan
                    
                    # Check if this plan has order flow conditions (for logging)
                    order_flow_conditions = [
                        "delta_positive", "delta_negative",
                        "cvd_rising", "cvd_falling",
                        "cvd_div_bear", "cvd_div_bull",
                        "delta_divergence_bull", "delta_divergence_bear",
                        "absorption_zone_detected"
                    ]
                    has_of = any(plan.conditions.get(cond) for cond in order_flow_conditions)
                    if has_of:
                        matching = [cond for cond in order_flow_conditions if plan.conditions.get(cond)]
                        logger.debug(
                            f"Loaded order flow plan: {plan.plan_id} ({plan.symbol} {plan.direction}) - "
                            f"Conditions: {matching}"
                        )
                except Exception as e:
                    logger.warning(f"Error loading plan {row[0] if row else 'unknown'}: {e}", exc_info=True)
                    continue
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                logger.warning(f"Database locked, retrying plan load in 1 second...")
                time.sleep(1)
                # Retry once
                try:
                    with sqlite3.connect(self.db_path, timeout=15.0) as conn:
                        now_utc = datetime.now(timezone.utc).isoformat()
                        cursor = conn.execute("""
                            SELECT * FROM trade_plans 
                            WHERE status = 'pending' 
                            AND (expires_at IS NULL OR expires_at > ?)
                        """, (now_utc,))
                        rows = cursor.fetchall()
                    
                    # Process rows after connection is closed
                    for row in rows:
                        try:
                            plan_id = row[0]
                            symbol = row[1]
                            direction = row[2]
                            entry_price = row[3]
                            stop_loss = row[4]
                            take_profit = row[5]
                            volume = row[6] if row[6] and row[6] > 0 else 0.01
                            conditions_json = row[7]
                            
                            # Validate plan data
                            is_valid, error_msg = self._validate_plan_data(
                                plan_id, symbol, direction, entry_price, stop_loss, 
                                take_profit, volume, row[11]
                            )
                            if not is_valid:
                                logger.warning(f"Skipping invalid plan {plan_id}: {error_msg}")
                                continue
                            
                            # Parse JSON with error handling
                            try:
                                conditions = json.loads(conditions_json) if conditions_json else {}
                            except json.JSONDecodeError as e:
                                logger.warning(f"Skipping plan {plan_id}: Invalid JSON: {e}")
                                continue
                            
                            # Handle new columns (profit_loss, exit_price, close_time, close_reason) - indices 15-18
                            profit_loss = row[15] if len(row) > 15 else None
                            exit_price = row[16] if len(row) > 16 else None
                            close_time = row[17] if len(row) > 17 else None
                            close_reason = row[18] if len(row) > 18 else None
                            # Phase 1: Zone tracking fields - indices 19-21
                            zone_entry_tracked_retry = row[19] if len(row) > 19 else False
                            zone_entry_time_retry = row[20] if len(row) > 20 else None
                            zone_exit_time_retry = row[21] if len(row) > 21 else None
                            # Phase 2: Entry levels - index 22
                            entry_levels_json_retry = row[22] if len(row) > 22 else None
                            entry_levels_retry = None
                            if entry_levels_json_retry:
                                try:
                                    entry_levels_retry = json.loads(entry_levels_json_retry)
                                except json.JSONDecodeError:
                                    pass
                            # Phase 3: Cancellation tracking - indices 23-24
                            cancellation_reason_retry = row[23] if len(row) > 23 else None
                            last_cancellation_check_retry = row[24] if len(row) > 24 else None
                            # Phase 4: Re-evaluation tracking - indices 25-27
                            last_re_evaluation_retry = row[25] if len(row) > 25 else None
                            re_evaluation_count_today_retry = row[26] if len(row) > 26 else 0
                            re_evaluation_count_date_retry = row[27] if len(row) > 27 else None
                            
                            plan = TradePlan(
                                plan_id=plan_id, symbol=symbol, direction=direction,
                                entry_price=entry_price, stop_loss=stop_loss, take_profit=take_profit,
                                volume=volume, conditions=conditions,
                                created_at=row[8], created_by=row[9], status=row[10],
                                expires_at=row[11], executed_at=row[12], ticket=row[13],
                                notes=row[14],
                                zone_entry_tracked=bool(zone_entry_tracked_retry) if zone_entry_tracked_retry is not None else False,
                                zone_entry_time=zone_entry_time_retry,
                                zone_exit_time=zone_exit_time_retry,
                                entry_levels=entry_levels_retry,
                                cancellation_reason=cancellation_reason_retry,
                                last_cancellation_check=last_cancellation_check_retry,
                                last_re_evaluation=last_re_evaluation_retry,
                                re_evaluation_count_today=re_evaluation_count_today_retry if re_evaluation_count_today_retry is not None else 0,
                                re_evaluation_count_date=re_evaluation_count_date_retry
                            )
                            plans[plan.plan_id] = plan
                        except Exception as e:
                            logger.warning(f"Error loading plan {row[0] if row else 'unknown'}: {e}")
                            continue
                except Exception as retry_error:
                    logger.error(f"Failed to reload plans after retry: {retry_error}")
        except Exception as e:
            logger.error(f"Error loading plans from database: {e}", exc_info=True)
        
        # Log summary of loaded plans including order flow plans
        if plans:
            order_flow_conditions = [
                "delta_positive", "delta_negative",
                "cvd_rising", "cvd_falling",
                "cvd_div_bear", "cvd_div_bull",
                "delta_divergence_bull", "delta_divergence_bear",
                "absorption_zone_detected"
            ]
            of_plans = [
                p for p in plans.values()
                if any(p.conditions.get(cond) for cond in order_flow_conditions)
            ]
            logger.info(
                f"Loaded {len(plans)} plan(s) from database "
                f"({len(of_plans)} with order flow conditions)"
            )
            if of_plans:
                logger.info(
                    f"Order flow plans loaded: {', '.join([p.plan_id for p in of_plans[:5]])}"
                    f"{'...' if len(of_plans) > 5 else ''}"
                )
        else:
            logger.info("No plans loaded from database")
                
        return plans
    
    def add_plan(self, plan: TradePlan) -> bool:
        """Add a new trade plan to monitor"""
        max_retries = 3
        retry_delay_base = 0.5  # Start with 0.5 seconds
        
        for attempt in range(max_retries):
            try:
                try:
                    # Phase 3.4: Use OptimizedSQLiteManager if available
                    with self._get_db_connection() as conn:
                        # Phase 3.5: Include pending_order_ticket in INSERT
                        conn.execute("""
                            INSERT OR REPLACE INTO trade_plans 
                            (plan_id, symbol, direction, entry_price, stop_loss, take_profit, 
                             volume, conditions, created_at, created_by, status, expires_at, notes, entry_levels, pending_order_ticket)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            plan.plan_id, plan.symbol, plan.direction, plan.entry_price,
                            plan.stop_loss, plan.take_profit, plan.volume, json.dumps(plan.conditions),
                            plan.created_at, plan.created_by, plan.status, plan.expires_at, plan.notes,
                            json.dumps(plan.entry_levels) if plan.entry_levels else None,
                            plan.pending_order_ticket  # Phase 3: Pending order ticket
                        ))
                        conn.commit()
                        
                        # Success - add to in-memory plans
                        # Use timeout to prevent blocking if monitoring thread is reloading plans
                        lock_acquired = False
                        try:
                            lock_acquired = self.plans_lock.acquire(timeout=2.0)
                            if lock_acquired:
                                self.plans[plan.plan_id] = plan
                                logger.info(f"Added trade plan {plan.plan_id} for {plan.symbol}")
                            else:
                                # Lock timeout - plan is in database, will be picked up on next reload
                                logger.warning(
                                    f"Could not acquire plans_lock for plan {plan.plan_id} within 2s. "
                                    f"Plan is saved to database and will be picked up on next reload."
                                )
                        finally:
                            if lock_acquired:
                                self.plans_lock.release()
                        
                        return True
                        
                except sqlite3.OperationalError as e:
                    error_msg = str(e).lower()
                    if "locked" in error_msg or "database is locked" in error_msg:
                        if attempt < max_retries - 1:
                            # Exponential backoff: 0.5s, 1s, 2s
                            retry_delay = retry_delay_base * (2 ** attempt)
                            logger.warning(
                                f"Database locked for plan {plan.plan_id} (attempt {attempt + 1}/{max_retries}), "
                                f"retrying in {retry_delay:.1f}s..."
                            )
                            time.sleep(retry_delay)
                            continue
                        else:
                            # Last attempt failed
                            logger.error(
                                f"Failed to add plan {plan.plan_id} after {max_retries} attempts: "
                                f"Database locked (likely during rollover/rebalancing/phase sync)"
                            )
                            raise
                    else:
                        # Other database error - don't retry
                        raise
                        
            except sqlite3.OperationalError as e:
                # Final attempt failed or non-retryable error
                if attempt == max_retries - 1:
                    logger.error(
                        f"Failed to add trade plan {plan.plan_id} after {max_retries} attempts: {e}"
                    )
                    return False
                # Continue to next retry
                continue
                
            except Exception as e:
                # Non-database error - don't retry
                logger.error(f"Failed to add trade plan {plan.plan_id}: {e}", exc_info=True)
                return False
        
        # Should not reach here, but just in case
        logger.error(f"Failed to add trade plan {plan.plan_id}: Max retries exceeded")
        return False
    
    def get_plan_re_evaluation_status(self, plan: TradePlan) -> Dict[str, Any]:
        """
        Get re-evaluation status for a plan (Phase 4).
        
        Returns:
            Dict with re-evaluation information including availability, cooldown, counts, etc.
        """
        try:
            # Load config if not already loaded
            if not hasattr(self, '_adaptive_config') or self._adaptive_config is None:
                self._adaptive_config = self._load_adaptive_config()
            
            re_eval_rules = self._adaptive_config.get('re_evaluation_rules', {})
            cooldown_minutes = re_eval_rules.get('cooldown_minutes', 60)
            daily_limit = re_eval_rules.get('daily_limit', 6)
            
            # Check cooldown
            cooldown_remaining = 0
            if plan.last_re_evaluation:
                try:
                    last_eval_dt = datetime.fromisoformat(plan.last_re_evaluation.replace('Z', '+00:00'))
                    if last_eval_dt.tzinfo is None:
                        last_eval_dt = last_eval_dt.replace(tzinfo=timezone.utc)
                    now_utc = datetime.now(timezone.utc)
                    time_since_eval_minutes = (now_utc - last_eval_dt).total_seconds() / 60.0
                    cooldown_remaining = max(0, cooldown_minutes - time_since_eval_minutes)
                except Exception:
                    pass
            
            # Check daily limit
            today_str = datetime.now(timezone.utc).date().isoformat()
            if plan.re_evaluation_count_date != today_str:
                count_today = 0
            else:
                count_today = plan.re_evaluation_count_today or 0
            
            available = cooldown_remaining == 0 and count_today < daily_limit
            
            return {
                'success': True,
                'last_re_evaluation': plan.last_re_evaluation,
                're_evaluation_count_today': count_today,
                're_evaluation_count_date': plan.re_evaluation_count_date,
                're_evaluation_cooldown_remaining': int(cooldown_remaining * 60),  # seconds
                're_evaluation_available': available,
                'daily_limit': daily_limit,
                'cooldown_minutes': cooldown_minutes
            }
        except Exception as e:
            logger.error(f"Error getting re-evaluation status for plan {plan.plan_id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_plan_zone_status(self, plan: TradePlan, current_price: Optional[float] = None) -> Dict[str, Any]:
        """
        Get zone status for a plan (Phase 1).
        
        Args:
            plan: TradePlan to check
            current_price: Current market price (if None, will fetch from MT5)
        
        Returns:
            Dict with zone status information
        """
        try:
            # Get current price if not provided
            if current_price is None:
                try:
                    if self.mt5_service and self.mt5_service.connect():
                        quote = self.mt5_service.get_quote(plan.symbol)
                        if plan.direction == "BUY":
                            current_price = quote.ask
                        else:
                            current_price = quote.bid
                    else:
                        return {
                            "success": False,
                            "error": "MT5 service not available"
                        }
                except Exception as e:
                    logger.warning(f"Failed to get current price for zone status: {e}")
                    return {
                        "success": False,
                        "error": f"Failed to get current price: {str(e)}"
                    }
            
            # Check zone entry
            previous_in_zone = getattr(plan, 'zone_entry_tracked', None)
            if previous_in_zone is not None:
                previous_in_zone = bool(previous_in_zone)
            
            in_zone, level_index, entry_detected = self._check_tolerance_zone_entry(
                plan, current_price, previous_in_zone
            )
            
            # Calculate price distance from entry
            price_distance = abs(current_price - plan.entry_price)
            
            # Get tolerance
            tolerance = plan.conditions.get("tolerance")
            if tolerance is None:
                from infra.tolerance_helper import get_price_tolerance
                tolerance = get_price_tolerance(plan.symbol)
            
            return {
                "success": True,
                "plan_id": plan.plan_id,
                "in_tolerance_zone": in_zone,
                "zone_entry_tracked": getattr(plan, 'zone_entry_tracked', False),
                "zone_entry_time": getattr(plan, 'zone_entry_time', None),
                "zone_exit_time": getattr(plan, 'zone_exit_time', None),
                "price_distance_from_entry": price_distance,
                "tolerance": tolerance,
                "current_price": current_price,
                "entry_price": plan.entry_price,
                "level_index": level_index  # For multi-level support (Phase 2)
            }
        except Exception as e:
            logger.error(f"Error getting zone status: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_plan_by_id(self, plan_id: str) -> Optional[TradePlan]:
        """Get a trade plan by ID from database (works for any status)"""
        try:
            # Phase 3.4: Use OptimizedSQLiteManager if available
            with self._get_db_connection() as conn:
                # Use explicit column names to avoid index issues
                # Phase 3.8: Include kill_switch_triggered and pending_order_ticket in SELECT
                cursor = conn.execute("""
                    SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit, volume,
                           conditions, created_at, created_by, status, expires_at, executed_at, ticket, notes,
                           profit_loss, exit_price, close_time, close_reason,
                           zone_entry_tracked, zone_entry_time, zone_exit_time,
                           entry_levels,
                           cancellation_reason, last_cancellation_check,
                           last_re_evaluation, re_evaluation_count_today, re_evaluation_count_date,
                           kill_switch_triggered, pending_order_ticket
                    FROM trade_plans WHERE plan_id = ?
                """, (plan_id,))
                row = cursor.fetchone()
                
                if row:
                    try:
                        # Parse JSON with error handling
                        conditions_json = row[7]
                        try:
                            conditions = json.loads(conditions_json) if conditions_json else {}
                        except json.JSONDecodeError as e:
                            logger.warning(f"Plan {row[0]} has invalid JSON in conditions: {e}")
                            conditions = {}  # Use empty dict as fallback
                        
                        # Handle new columns (profit_loss, exit_price, close_time, close_reason) - indices 15-18
                        profit_loss = row[15] if len(row) > 15 else None
                        exit_price = row[16] if len(row) > 16 else None
                        close_time = row[17] if len(row) > 17 else None
                        close_reason = row[18] if len(row) > 18 else None
                        # Phase 1: Zone tracking fields - indices 19-21
                        zone_entry_tracked = row[19] if len(row) > 19 else False
                        zone_entry_time = row[20] if len(row) > 20 else None
                        zone_exit_time = row[21] if len(row) > 21 else None
                        # Phase 2: Entry levels - index 22
                        entry_levels_json = row[22] if len(row) > 22 else None
                        entry_levels = None
                        if entry_levels_json:
                            try:
                                entry_levels = json.loads(entry_levels_json)
                            except json.JSONDecodeError:
                                pass
                        # Phase 3: Cancellation tracking - indices 23-24
                        cancellation_reason = row[23] if len(row) > 23 else None
                        last_cancellation_check = row[24] if len(row) > 24 else None
                        # Phase 4: Re-evaluation tracking - indices 25-27
                        last_re_evaluation = row[25] if len(row) > 25 else None
                        re_evaluation_count_today = row[26] if len(row) > 26 else 0
                        re_evaluation_count_date = row[27] if len(row) > 27 else None
                        # Phase 2.4: Kill-switch flag - index 28
                        kill_switch_triggered = bool(row[28]) if len(row) > 28 else False
                        # Phase 3: Pending order ticket - index 29
                        pending_order_ticket = row[29] if len(row) > 29 else None
                        
                        return TradePlan(
                            plan_id=row[0],
                            symbol=row[1],
                            direction=row[2],
                            entry_price=row[3],
                            stop_loss=row[4],
                            take_profit=row[5],
                            volume=row[6] if row[6] and row[6] > 0 else 0.01,
                            conditions=conditions,
                            created_at=row[8],
                            created_by=row[9],
                            status=row[10],
                            expires_at=row[11],
                            executed_at=row[12],
                            ticket=row[13],
                            notes=row[14],
                            profit_loss=profit_loss,
                            exit_price=exit_price,
                            close_time=close_time,
                            close_reason=close_reason,
                            zone_entry_tracked=bool(zone_entry_tracked) if zone_entry_tracked is not None else False,
                            zone_entry_time=zone_entry_time,
                            zone_exit_time=zone_exit_time,
                            entry_levels=entry_levels,
                            cancellation_reason=cancellation_reason,
                            last_cancellation_check=last_cancellation_check,
                            last_re_evaluation=last_re_evaluation,
                            re_evaluation_count_today=re_evaluation_count_today if re_evaluation_count_today is not None else 0,
                            re_evaluation_count_date=re_evaluation_count_date,
                            kill_switch_triggered=kill_switch_triggered,
                            pending_order_ticket=pending_order_ticket  # Phase 3: Pending order ticket
                        )
                    except Exception as e:
                        logger.error(f"Error loading plan {row[0]}: {e}", exc_info=True)
                        return None
            return None
        except Exception as e:
            logger.error(f"Failed to get plan {plan_id}: {e}")
            return None
    
    def _cleanup_plan_resources(self, plan_id: str, symbol: str):
        """
        Clean up resources associated with a plan.
        Optimized to minimize lock contention.
        
        Args:
            plan_id: Plan ID to clean up
            symbol: Symbol associated with the plan
        """
        try:
            # Remove execution lock (fast operation)
            with self.execution_locks_lock:
                if plan_id in self.execution_locks:
                    del self.execution_locks[plan_id]
            
            # Remove from executing plans set (fast operation)
            with self.executing_plans_lock:
                self.executing_plans.discard(plan_id)
            
            # Clean up M1 cache if no other plans use this symbol
            # Use try/except to avoid blocking if lock is held
            symbol_norm = symbol.upper().rstrip('Cc') + 'c'
            try:
                # Try to acquire lock with timeout (non-blocking check)
                if self.plans_lock.acquire(blocking=False):
                    try:
                        other_plans_use_symbol = any(
                            p.symbol.upper().rstrip('Cc') + 'c' == symbol_norm 
                            for p in self.plans.values()
                        )
                        
                        if not other_plans_use_symbol:
                            # No other plans use this symbol - clean up cache
                            if symbol_norm in self._m1_data_cache:
                                del self._m1_data_cache[symbol_norm]
                            if symbol_norm in self._m1_cache_timestamps:
                                del self._m1_cache_timestamps[symbol_norm]
                            if symbol_norm in self._last_signal_timestamps:
                                del self._last_signal_timestamps[symbol_norm]
                    finally:
                        self.plans_lock.release()
                else:
                    # Lock is held - skip cache cleanup (non-critical)
                    logger.debug(f"Could not acquire plans_lock for cache cleanup (non-critical)")
            except Exception as e:
                logger.debug(f"Error checking other plans for symbol {symbol_norm}: {e}")
            
            # Phase 1.2: Clean up optimized intervals tracking dicts
            # NOTE: These are accessed only from monitor thread, so no lock needed
            # But use hasattr checks for safety in case dicts aren't initialized
            try:
                if hasattr(self, '_plan_types') and plan_id in self._plan_types:
                    del self._plan_types[plan_id]
                if hasattr(self, '_plan_last_check') and plan_id in self._plan_last_check:
                    del self._plan_last_check[plan_id]
                if hasattr(self, '_plan_last_price') and plan_id in self._plan_last_price:
                    del self._plan_last_price[plan_id]
            except Exception as e:
                logger.debug(f"Error cleaning up tracking dicts for {plan_id}: {e}")
            
        except Exception as e:
            logger.debug(f"Error cleaning up resources for plan {plan_id}: {e}")
    
    def cancel_plan(self, plan_id: str, cancellation_reason: Optional[str] = None) -> bool:
        """Cancel a trade plan using write queue (Phase 0). If plan has a pending order, cancel it in MT5 first."""
        try:
            # Phase 5.2: Get plan from memory or database to check for pending orders
            plan = None
            try:
                with self.plans_lock:
                    if plan_id in self.plans:
                        plan = self.plans[plan_id]
            except Exception as e:
                logger.debug(f"Error getting plan from memory: {e}")
            
            # If not in memory, try database
            if not plan:
                plan = self.get_plan_by_id(plan_id)
            
            # Phase 5.2: Check if plan exists
            if not plan:
                logger.warning(f"Plan {plan_id} not found - cannot cancel")
                return False
            
            # Phase 5.2: If plan has pending order, cancel it in MT5 first
            if hasattr(plan, 'pending_order_ticket') and plan.pending_order_ticket:
                try:
                    import MetaTrader5 as mt5
                    if self.mt5_service.connect():
                        request = {
                            "action": mt5.TRADE_ACTION_REMOVE,
                            "order": plan.pending_order_ticket,
                        }
                        result = mt5.order_send(request)
                        if result.retcode == mt5.TRADE_RETCODE_DONE:
                            logger.info(f"Cancelled pending order {plan.pending_order_ticket} for plan {plan_id}")
                        else:
                            logger.warning(f"Failed to cancel pending order {plan.pending_order_ticket} for plan {plan_id}: retcode={result.retcode}")
                    else:
                        logger.warning(f"MT5 not connected - cannot cancel pending order for plan {plan_id}")
                except Exception as e:
                    logger.error(f"Error cancelling pending order for plan {plan_id}: {e}", exc_info=True)
                    # Continue with plan cancellation even if order cancellation fails
            
            # 1. Update database using write queue (HIGH priority)
            if self.db_write_queue:
                try:
                    operation_id = self.db_write_queue.queue_operation(
                        operation_type="cancel_plan",
                        plan_id=plan_id,
                        data={"cancellation_reason": cancellation_reason} if cancellation_reason else {},
                        priority=self.OperationPriority.HIGH,
                        wait_for_completion=False,  # Don't wait - fast response
                        timeout=30.0
                    )
                    logger.debug(f"Queued cancel operation for plan {plan_id}")
                except Exception as e:
                    logger.error(f"Failed to queue cancel operation: {e}")
                    # Fallback to direct write
                    with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                        if cancellation_reason:
                            conn.execute("""
                                UPDATE trade_plans 
                                SET status = 'cancelled', cancellation_reason = ?
                                WHERE plan_id = ?
                            """, (cancellation_reason, plan_id))
                        else:
                            conn.execute("""
                                UPDATE trade_plans 
                                SET status = 'cancelled' 
                                WHERE plan_id = ?
                            """, (plan_id,))
                        conn.commit()
            else:
                # Fallback to direct write if queue not available
                with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                    if cancellation_reason:
                        conn.execute("""
                            UPDATE trade_plans 
                            SET status = 'cancelled', cancellation_reason = ?
                            WHERE plan_id = ?
                        """, (cancellation_reason, plan_id))
                    else:
                        conn.execute("""
                            UPDATE trade_plans 
                            SET status = 'cancelled' 
                            WHERE plan_id = ?
                        """, (plan_id,))
                    conn.commit()
            
            # 2. Get plan symbol quickly (minimal lock time)
            plan_symbol = None
            try:
                with self.plans_lock:
                    if plan_id in self.plans:
                        plan_symbol = self.plans[plan_id].symbol
                        del self.plans[plan_id]
            except Exception as e:
                logger.debug(f"Error removing plan from memory: {e}")
            
            # 3. Clean up resources (separate from plans_lock to avoid nested locks)
            if plan_symbol:
                try:
                    self._cleanup_plan_resources(plan_id, plan_symbol)
                except Exception as e:
                    logger.debug(f"Error cleaning up resources: {e}")
            
            # 4. Clear execution failures (no lock needed)
            if plan_id in self.execution_failures:
                del self.execution_failures[plan_id]
            
            logger.info(f"Cancelled trade plan {plan_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel trade plan {plan_id}: {e}")
            return False
    
    def _update_plan_status(self, plan: TradePlan, wait_for_completion: bool = False) -> bool:
        """
        Update plan status in database using write queue (Phase 0).
        
        Args:
            plan: TradePlan with updated status
            wait_for_completion: Whether to wait for operation to complete (default False)
            
        Returns:
            True if queued successfully, False otherwise
        """
        # Use write queue if available, fallback to direct write
        if self.db_write_queue:
            try:
                # Build data dict
                data = {}
                if plan.status:
                    data["status"] = plan.status
                if plan.executed_at:
                    data["executed_at"] = plan.executed_at
                if plan.ticket is not None:
                    data["ticket"] = plan.ticket
                
                # Phase 3.6: Add pending_order_ticket
                if hasattr(plan, 'pending_order_ticket') and plan.pending_order_ticket is not None:
                    data["pending_order_ticket"] = plan.pending_order_ticket
                
                if not data:
                    # Nothing to update
                    return True
                
                # Determine priority: HIGH for executed/cancelled, MEDIUM for others
                priority = self.OperationPriority.HIGH if plan.status in ["executed", "cancelled"] else self.OperationPriority.MEDIUM
                
                # Queue operation
                operation_id = self.db_write_queue.queue_operation(
                    operation_type="update_status",
                    plan_id=plan.plan_id,
                    data=data,
                    priority=priority,
                    wait_for_completion=wait_for_completion,
                    timeout=30.0
                )
                
                logger.debug(f"Queued plan {plan.plan_id} status update: {plan.status}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to queue plan status update: {e}", exc_info=True)
                # Fallback to direct write
                return self._update_plan_status_direct(plan)
        else:
            # Fallback to direct write if queue not available
            return self._update_plan_status_direct(plan)
    
    def _update_plan_status_direct(self, plan: TradePlan) -> bool:
        """
        Direct database update (fallback when queue unavailable).
        
        Args:
            plan: TradePlan with updated status
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            # Phase 3.4: Use OptimizedSQLiteManager if available
            with self._get_db_connection() as conn:
                # Build update query based on what fields are set
                updates = []
                params = []
                
                if plan.status:
                    updates.append("status = ?")
                    params.append(plan.status)
                
                if plan.executed_at:
                    updates.append("executed_at = ?")
                    params.append(plan.executed_at)
                
                if plan.ticket is not None:
                    updates.append("ticket = ?")
                    params.append(plan.ticket)
                
                if hasattr(plan, 'kill_switch_triggered'):
                    updates.append("kill_switch_triggered = ?")
                    params.append(1 if plan.kill_switch_triggered else 0)
                
                # Phase 3.5: Handle pending_order_ticket
                if hasattr(plan, 'pending_order_ticket') and plan.pending_order_ticket is not None:
                    updates.append("pending_order_ticket = ?")
                    params.append(plan.pending_order_ticket)
                
                if not updates:
                    # Nothing to update
                    return True
                
                params.append(plan.plan_id)
                
                query = f"""
                    UPDATE trade_plans 
                    SET {', '.join(updates)}
                    WHERE plan_id = ?
                """
                conn.execute(query, params)
                conn.commit()
                logger.debug(f"Updated plan {plan.plan_id} status to '{plan.status}' in database (direct)")
                return True
                
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                logger.warning(f"Database locked, retrying plan status update in 1 second...")
                time.sleep(1)
                # Retry once
                try:
                    with sqlite3.connect(self.db_path, timeout=15.0) as conn:
                        updates = []
                        params = []
                        if plan.status:
                            updates.append("status = ?")
                            params.append(plan.status)
                        if plan.executed_at:
                            updates.append("executed_at = ?")
                            params.append(plan.executed_at)
                        if plan.ticket is not None:
                            updates.append("ticket = ?")
                            params.append(plan.ticket)
                        if updates:
                            params.append(plan.plan_id)
                            query = f"UPDATE trade_plans SET {', '.join(updates)} WHERE plan_id = ?"
                            conn.execute(query, params)
                            conn.commit()
                            return True
                except Exception as retry_error:
                    logger.error(f"Failed to update plan status after retry: {retry_error}")
        except Exception as e:
            logger.error(f"Failed to update plan {plan.plan_id} status: {e}", exc_info=True)
            return False
        
        return False
    
    # Phase 2.2: Order Flow Plan Methods
    def _get_order_flow_plans(self) -> List[TradePlan]:
        """
        Get plans that have order flow conditions.
        
        Phase 2.2: Identifies plans with order-flow conditions for high-frequency checks.
        
        Returns:
            List of TradePlan objects with order flow conditions
        """
        order_flow_conditions = [
            "delta_positive", "delta_negative",
            "cvd_rising", "cvd_falling",
            "cvd_div_bear", "cvd_div_bull",
            "Cvd Div Bear", "Cvd Div Bull",  # Aliases
            "delta_divergence_bull", "delta_divergence_bear",
            "Delta Divergence Bull", "Delta Divergence Bear",  # Aliases
            "avoid_absorption_zones", "absorption_zone_detected",
            "Absorption Zone Detected"  # Alias
        ]
        
        # self.plans is a dict, so iterate over values
        with self.plans_lock:  # Thread-safe access
            total_plans = len(self.plans)
            pending_plans = [p for p in self.plans.values() if p.status == "pending"]
            order_flow_plans = []
            
            for plan in pending_plans:
                # Check if plan has any order flow conditions
                has_of_condition = any(plan.conditions.get(cond) for cond in order_flow_conditions)
                if has_of_condition:
                    # Find which conditions match
                    matching_conditions = [cond for cond in order_flow_conditions if plan.conditions.get(cond)]
                    order_flow_plans.append(plan)
                    logger.debug(
                        f"Order flow plan detected: {plan.plan_id} ({plan.symbol} {plan.direction}) - "
                        f"Conditions: {matching_conditions}"
                    )
            
            if order_flow_plans:
                logger.info(
                    f"Found {len(order_flow_plans)} order flow plan(s) out of {len(pending_plans)} pending "
                    f"(total plans in memory: {total_plans})"
                )
            else:
                logger.debug(
                    f"No order flow plans found (checked {len(pending_plans)} pending plans, "
                    f"total in memory: {total_plans})"
                )
            
            return order_flow_plans
    
    def _check_order_flow_plans_quick(self, plans: List[TradePlan]):
        """
        Quick check for order-flow plans (only order flow conditions).
        
        Phase 2.2: Fast check that only validates order-flow conditions,
        then triggers full check if conditions are met.
        
        Phase 4.1: Optimized with batch processing for better performance.
        
        Args:
            plans: List of TradePlan objects with order flow conditions
        """
        if not plans:
            logger.debug("_check_order_flow_plans_quick called with empty plans list")
            return
        
        logger.info(
            f"Checking {len(plans)} order flow plan(s): "
            f"{', '.join([p.plan_id for p in plans[:5]])}"
            f"{'...' if len(plans) > 5 else ''}"
        )
        
        # Phase 4.1: Batch processing - group plans by symbol
        plans_by_symbol = {}
        for plan in plans:
            symbol_norm = plan.symbol.upper().rstrip('Cc')
            if symbol_norm not in plans_by_symbol:
                plans_by_symbol[symbol_norm] = []
            plans_by_symbol[symbol_norm].append(plan)
        
        # Process each symbol's plans (metrics fetched once per symbol)
        for symbol_norm, symbol_plans in plans_by_symbol.items():
            try:
                # Get metrics once for all plans of this symbol
                metrics = None
                if symbol_norm.startswith('BTC'):
                    # Get metrics for first plan (will be cached for others)
                    if symbol_plans:
                        logger.debug(f"Fetching BTC order flow metrics for {symbol_norm} (affects {len(symbol_plans)} plan(s))")
                        metrics = self._get_btc_order_flow_metrics(symbol_plans[0], window_seconds=300)
                        if metrics:
                            logger.debug(f"BTC order flow metrics retrieved successfully for {symbol_norm}")
                        else:
                            logger.warning(f"⚠️ Failed to get BTC order flow metrics for {symbol_norm} - order flow service may be unavailable")
                
                # Check each plan with cached metrics
                for plan in symbol_plans:
                    try:
                        logger.debug(f"Checking order flow conditions for {plan.plan_id} ({plan.symbol} {plan.direction})")
                        # Only check order flow conditions (skip other validations for speed)
                        of_conditions_met = self._check_order_flow_conditions_only(plan)
                        if of_conditions_met:
                            logger.info(
                                f"Order flow conditions met for {plan.plan_id} - triggering full check"
                            )
                            # If order flow conditions met, trigger full check
                            if self._check_conditions(plan):
                                logger.info(f"All conditions met for {plan.plan_id} - executing plan")
                                # Execute the plan using the standard trade execution path
                                # (historically this was named _execute_trade; _execute_plan is not implemented)
                                self._execute_trade(plan)
                        else:
                            logger.debug(f"Order flow conditions not met for {plan.plan_id}")
                    except Exception as e:
                        logger.error(f"Error in quick order-flow check for {plan.plan_id}: {e}", exc_info=True)
            except Exception as e:
                logger.debug(f"Error processing symbol {symbol_norm} plans: {e}")
    
    def _check_order_flow_conditions_only(self, plan: TradePlan) -> bool:
        """
        Check only order flow conditions (faster than full check).
        
        Phase 2.2: Validates only order-flow related conditions without
        checking price, structure, or other non-order-flow conditions.
        
        Args:
            plan: TradePlan to check
        
        Returns:
            True if all order-flow conditions are met, False otherwise
        """
        symbol_norm = plan.symbol.upper().rstrip('Cc')
        
        # Check BTC order flow conditions
        if symbol_norm.startswith('BTC'):
            return self._check_btc_order_flow_conditions_only(plan, symbol_norm)
        
        # Check proxy order flow conditions (XAUUSD, EURUSD)
        elif symbol_norm in ["XAUUSD", "EURUSD"]:
            return self._check_proxy_order_flow_conditions_only(plan, symbol_norm)
        
        # No order flow conditions for this symbol
        return True  # Default: allow if no order-flow conditions specified
    
    def _check_btc_order_flow_conditions_only(self, plan: TradePlan, symbol_norm: str) -> bool:
        """
        Check BTC order flow conditions only.
        
        Args:
            plan: TradePlan to check
            symbol_norm: Normalized symbol (e.g., "BTCUSDT")
        
        Returns:
            True if all BTC order-flow conditions are met
        """
        try:
            # Get order flow metrics
            metrics = self._get_btc_order_flow_metrics(plan, window_seconds=300)
            
            if not metrics:
                logger.warning(
                    f"⚠️ Order flow metrics unavailable for {plan.plan_id} ({symbol_norm}) - "
                    f"order flow service may not be running or initialized"
                )
                return False
            
            # Check delta conditions
            if plan.conditions.get("delta_positive") and metrics.delta_volume <= 0:
                return False
            if plan.conditions.get("delta_negative") and metrics.delta_volume >= 0:
                return False
            
            # Check CVD conditions
            if plan.conditions.get("cvd_rising") and metrics.cvd_slope <= 0:
                return False
            if plan.conditions.get("cvd_falling") and metrics.cvd_slope >= 0:
                return False
            
            # Check CVD divergence
            cvd_div_bear = plan.conditions.get("cvd_div_bear") or plan.conditions.get("Cvd Div Bear")
            cvd_div_bull = plan.conditions.get("cvd_div_bull") or plan.conditions.get("Cvd Div Bull")
            
            if cvd_div_bear and (not metrics.cvd_divergence_type or metrics.cvd_divergence_type != "bearish"):
                return False
            if cvd_div_bull and (not metrics.cvd_divergence_type or metrics.cvd_divergence_type != "bullish"):
                return False
            
            # Check absorption zones
            absorption_detected = plan.conditions.get("absorption_zone_detected") or plan.conditions.get("Absorption Zone Detected")
            if absorption_detected:
                if not metrics.absorption_zones or len(metrics.absorption_zones) == 0:
                    return False
            
            # All order-flow conditions met
            return True
            
        except Exception as e:
            logger.debug(f"Error checking BTC order flow conditions for {plan.plan_id}: {e}")
            return False
    
    def _check_proxy_order_flow_conditions_only(self, plan: TradePlan, symbol_norm: str) -> bool:
        """
        Check proxy order flow conditions for XAUUSD/EURUSD.
        
        Args:
            plan: TradePlan to check
            symbol_norm: Normalized symbol (e.g., "XAUUSD")
        
        Returns:
            True if all proxy order-flow conditions are met
        """
        try:
            # Use GeneralOrderFlowMetrics for proxy symbols
            if not self._general_order_flow_metrics:
                return False
            
            # Get proxy order flow metrics (async call in sync context)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                metrics = loop.run_until_complete(
                    self._general_order_flow_metrics.get_order_flow_metrics(symbol_norm, 30)
                )
            finally:
                loop.close()
                asyncio.set_event_loop(None)
            
            if not metrics:
                return False
            
            # Check proxy order flow conditions (similar to BTC but using proxy metrics)
            # Implementation depends on what proxy metrics provide
            # For now, return True if metrics exist (conditions will be checked in full check)
            return True
            
        except Exception as e:
            logger.debug(f"Error checking proxy order flow conditions for {plan.plan_id}: {e}")
            return False
    
    def _cleanup_volume_cache(self) -> None:
        """Clean up expired volume cache entries"""
        try:
            current_time = time.time()
            with self._volume_cache_lock:
                expired_keys = [
                    key for key, (_, timestamp) in self._volume_cache.items()
                    if current_time - timestamp >= self._volume_cache_ttl * 2  # Keep for 2x TTL
                ]
                for key in expired_keys:
                    del self._volume_cache[key]
                if expired_keys:
                    logger.debug(f"Cleaned up {len(expired_keys)} expired volume cache entries")
        except Exception as e:
            logger.debug(f"Error cleaning up volume cache: {e}")
    
    def _cleanup_binance_pressure_cache(self) -> None:
        """Clean up expired Binance pressure cache entries"""
        try:
            current_time = time.time()
            with self._binance_pressure_cache_lock:
                expired_keys = [
                    key for key, (_, timestamp) in self._binance_pressure_cache.items()
                    if current_time - timestamp >= 20  # Keep for 2x TTL (10s * 2)
                ]
                for key in expired_keys:
                    del self._binance_pressure_cache[key]
                if expired_keys:
                    logger.debug(f"Cleaned up {len(expired_keys)} expired Binance pressure cache entries")
        except Exception as e:
            logger.debug(f"Error cleaning up Binance pressure cache: {e}")
    
    def _periodic_cache_cleanup(self) -> None:
        """
        Periodically clean up caches for symbols that are no longer being monitored.
        Also clean up invalid_symbols entries that are old.
        """
        try:
            # Get all symbols currently in use by active plans
            with self.plans_lock:
                active_symbols = set()
                for plan in self.plans.values():
                    symbol_base = plan.symbol.upper().rstrip('Cc')
                    symbol_norm = symbol_base + 'c'
                    active_symbols.add(symbol_norm)
            
            # Clean up M1 cache for symbols not in active plans
            symbols_to_remove = []
            for symbol_norm in list(self._m1_data_cache.keys()):
                if symbol_norm not in active_symbols:
                    symbols_to_remove.append(symbol_norm)
            
            for symbol_norm in symbols_to_remove:
                if symbol_norm in self._m1_data_cache:
                    del self._m1_data_cache[symbol_norm]
                if symbol_norm in self._m1_cache_timestamps:
                    del self._m1_cache_timestamps[symbol_norm]
                if symbol_norm in self._last_signal_timestamps:
                    del self._last_signal_timestamps[symbol_norm]
                    
                # Clean up confidence history
                if hasattr(self, '_confidence_history') and symbol_norm in self._confidence_history:
                    del self._confidence_history[symbol_norm]
            
            if symbols_to_remove:
                logger.debug(f"Cleaned up M1 cache for {len(symbols_to_remove)} unused symbols")
            
            # Phase 1.4: Clean up price cache
            self._cleanup_price_cache()
            
            # Clean up execution locks for plans that no longer exist
            with self.plans_lock:
                existing_plan_ids = set(self.plans.keys())
            
            with self.execution_locks_lock:
                locks_to_remove = [
                    plan_id for plan_id in self.execution_locks.keys() 
                    if plan_id not in existing_plan_ids
                ]
                for plan_id in locks_to_remove:
                    del self.execution_locks[plan_id]
            
            if locks_to_remove:
                logger.debug(f"Cleaned up {len(locks_to_remove)} orphaned execution locks")
                
        except Exception as e:
            logger.warning(f"Error during periodic cache cleanup: {e}")
    
    def update_plan(
        self,
        plan_id: str,
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        volume: Optional[float] = None,
        conditions: Optional[Dict[str, Any]] = None,
        expires_hours: Optional[int] = None,
        notes: Optional[str] = None
    ) -> bool:
        """Update an existing trade plan (only pending plans can be updated)"""
        try:
            # Get existing plan
            existing_plan = self.get_plan_by_id(plan_id)
            if not existing_plan:
                logger.error(f"Plan {plan_id} not found")
                return False
            
            if existing_plan.status != 'pending':
                logger.error(f"Cannot update plan {plan_id}: status is '{existing_plan.status}' (only 'pending' plans can be updated)")
                return False
            
            # Build update query dynamically
            updates = []
            params = []
            
            if entry_price is not None:
                updates.append("entry_price = ?")
                params.append(entry_price)
            
            if stop_loss is not None:
                updates.append("stop_loss = ?")
                params.append(stop_loss)
            
            if take_profit is not None:
                updates.append("take_profit = ?")
                params.append(take_profit)
            
            if volume is not None:
                updates.append("volume = ?")
                params.append(volume)
            
            if conditions is not None:
                # Merge with existing conditions (new conditions override existing ones)
                merged_conditions = existing_plan.conditions.copy()
                merged_conditions.update(conditions)
                updates.append("conditions = ?")
                params.append(json.dumps(merged_conditions))
            
            if expires_hours is not None:
                expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).isoformat()
                updates.append("expires_at = ?")
                params.append(expires_at)
            
            if notes is not None:
                updates.append("notes = ?")
                params.append(notes)
            
            if not updates:
                logger.warning(f"No updates provided for plan {plan_id}")
                return False
            
            # Add plan_id for WHERE clause
            params.append(plan_id)
            
            # Execute update
            with sqlite3.connect(self.db_path) as conn:
                query = f"""
                    UPDATE trade_plans 
                    SET {', '.join(updates)}
                    WHERE plan_id = ? AND status = 'pending'
                """
                cursor = conn.execute(query, params)
                
                if cursor.rowcount == 0:
                    logger.error(f"Failed to update plan {plan_id}: plan not found or not pending")
                    return False
                
                conn.commit()
            
            # Reload plan into memory if it's there
            with self.plans_lock:
                if plan_id in self.plans:
                    updated_plan = self.get_plan_by_id(plan_id)
                    if updated_plan:
                        self.plans[plan_id] = updated_plan
            
            logger.info(f"Updated trade plan {plan_id}: {', '.join([u.split(' =')[0] for u in updates])}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update trade plan {plan_id}: {e}", exc_info=True)
            return False
    
    def _cancel_bracket_other_side(self, bracket_id: str, executed_plan_id: str) -> None:
        """
        Cancel the other side of a bracket trade when one side executes.
        
        Args:
            bracket_id: Bracket trade ID
            executed_plan_id: Plan ID that just executed
        """
        try:
            # Find all plans with this bracket_id
            plans_to_cancel = []
            with self.plans_lock:
                for plan_id, plan in list(self.plans.items()):
                    if plan.conditions.get("bracket_trade_id") == bracket_id and plan_id != executed_plan_id:
                        plans_to_cancel.append(plan_id)
            
            # Also check database for plans not in memory
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT plan_id FROM trade_plans 
                    WHERE status = 'pending' 
                    AND json_extract(conditions, '$.bracket_trade_id') = ?
                    AND plan_id != ?
                """, (bracket_id, executed_plan_id))
                for row in cursor.fetchall():
                    plans_to_cancel.append(row[0])
            
            # Cancel the other side(s)
            for plan_id in plans_to_cancel:
                logger.info(f"Cancelling bracket trade other side: {plan_id} (bracket: {bracket_id})")
                self.cancel_plan(plan_id)
                
        except Exception as e:
            logger.error(f"Error cancelling bracket trade other side: {e}", exc_info=True)
    
    def _check_tolerance_zone_entry(
        self, 
        plan: TradePlan, 
        current_price: float,
        previous_in_zone: Optional[bool] = None
    ) -> tuple[bool, Optional[int], bool]:
        """
        Check tolerance zone entry for a plan (Phase 1).
        
        Supports both single entry_price and multi-level entry_levels (for Phase 2).
        
        Args:
            plan: TradePlan to check
            current_price: Current market price
            previous_in_zone: Previous zone state (None if unknown)
        
        Returns:
            (in_zone: bool, level_index: Optional[int], entry_detected: bool)
            - in_zone: Whether price is currently in tolerance zone
            - level_index: Which entry level is in zone (None for single entry, 0-based index for multi-level)
            - entry_detected: Whether this is a new zone entry (was outside, now inside)
        """
        # Get base tolerance from conditions or auto-calculate
        base_tolerance = plan.conditions.get("tolerance")
        if base_tolerance is None:
            from infra.tolerance_helper import get_price_tolerance
            base_tolerance = get_price_tolerance(plan.symbol)
        
        # NEW: Preliminary cap on base tolerance (before volatility adjustment)
        # NOTE: This prevents excessive base tolerance values. After volatility adjustment (Phase 2.5),
        # maximum tolerance will be enforced again as the final step.
        max_tolerance = self._get_max_tolerance(plan.symbol)
        if base_tolerance > max_tolerance:
            logger.warning(
                f"Plan {plan.plan_id}: Base tolerance {base_tolerance:.2f} exceeds maximum {max_tolerance:.2f} "
                f"for {plan.symbol}, capping to maximum"
            )
            base_tolerance = max_tolerance
        
        tolerance = base_tolerance  # Start with base, will be adjusted below
        
        # NEW: Apply volatility adjustment if calculator available (Phase 2.5)
        # Order of operations: 1) Get base tolerance, 2) Apply volatility adjustment, 3) Enforce maximum
        if self.volatility_tolerance_calculator:
            try:
                # Get RMAG data if available (from advanced features)
                rmag_data = None
                if hasattr(plan, 'advanced_features') and plan.advanced_features:
                    m5_features = plan.advanced_features.get("M5", {})
                    rmag_data = m5_features.get("rmag", {})
                
                # Get ATR (from volatility tolerance calculator's tolerance_calculator)
                atr = None
                if self.volatility_tolerance_calculator and hasattr(self.volatility_tolerance_calculator, 'tolerance_calculator'):
                    try:
                        atr = self.volatility_tolerance_calculator.tolerance_calculator._get_atr(plan.symbol, "M15")
                    except:
                        pass
                
                # Calculate volatility-adjusted tolerance (replaces base_tolerance)
                tolerance = self.volatility_tolerance_calculator.calculate_volatility_adjusted_tolerance(
                    symbol=plan.symbol,
                    base_tolerance=base_tolerance,  # Use base_tolerance, not adjusted tolerance
                    rmag_data=rmag_data,
                    atr=atr,
                    timeframe="M15"
                )
                
                # Check if kill-switch was triggered (for logging and flag storage)
                # NOTE: The kill-switch is already handled inside calculate_volatility_adjusted_tolerance()
                # which returns base_tolerance * 0.1 when RMAG exceeds threshold. This redundant check
                # is for logging and storing the kill_switch_triggered flag in the plan.
                # Use smoothed RMAG if smoothing is enabled (same as calculator uses)
                if rmag_data:
                    ema200_atr_raw = abs(rmag_data.get('ema200_atr', 0))
                    # Apply smoothing if enabled (same as calculator does)
                    if (self.volatility_tolerance_calculator and 
                        hasattr(self.volatility_tolerance_calculator, 'enable_rmag_smoothing') and
                        self.volatility_tolerance_calculator.enable_rmag_smoothing):
                        ema200_atr = self.volatility_tolerance_calculator._smooth_rmag(plan.symbol, ema200_atr_raw)
                    else:
                        ema200_atr = ema200_atr_raw
                    
                    kill_switch_threshold = self.volatility_tolerance_calculator._get_kill_switch_threshold(plan.symbol)
                    
                    # Detect kill-switch: tolerance is at kill-switch level (0.1 * base) OR RMAG exceeds threshold
                    # NOTE: base_tolerance was already retrieved above, reuse it
                    is_kill_switch_tolerance = tolerance <= base_tolerance * 0.15  # Kill-switch level
                    is_rmag_above_threshold = ema200_atr > kill_switch_threshold
                    
                    if is_kill_switch_tolerance or is_rmag_above_threshold:
                        # Log kill-switch trigger with structured data
                        logger.warning(
                            f"Plan {plan.plan_id}: Kill-switch triggered - "
                            f"RMAG {ema200_atr:.2f} > threshold {kill_switch_threshold:.2f}. "
                            f"kill_switch_triggered=true, symbol={plan.symbol}, "
                            f"rmag_ema200_atr={ema200_atr:.2f}, threshold={kill_switch_threshold:.2f}, "
                            f"tolerance={tolerance:.2f} (kill-switch level)"
                        )
                        # Store kill-switch flag in plan (will be persisted to database)
                        plan.kill_switch_triggered = True
                        
                        # Also store in conditions for logging/audit
                        if not hasattr(plan, 'conditions') or plan.conditions is None:
                            plan.conditions = {}
                        plan.conditions['kill_switch_triggered'] = True
                        plan.conditions['kill_switch_rmag'] = ema200_atr
                        plan.conditions['kill_switch_rmag_raw'] = ema200_atr_raw  # Store raw value too
                        plan.conditions['kill_switch_threshold'] = kill_switch_threshold
                        
                        # CRITICAL: Block zone entry when kill-switch is active
                        # Return False for zone entry to prevent execution during extreme volatility
                        # The tolerance is already at kill-switch level (0.1 * base), which makes zone very small,
                        # but we explicitly block here to be safe
                        return (False, None, False)  # (in_zone=False, level_index=None, entry_detected=False)
            except Exception as e:
                logger.debug(f"Error calculating volatility-adjusted tolerance: {e}, using base tolerance")
        
        # Enforce maximum tolerance (ALWAYS as final step, after all adjustments)
        # This ensures maximum tolerance is always respected, even after volatility adjustments
        # NOTE: If kill-switch was triggered above, we already returned, so this won't execute
        max_tolerance = self._get_max_tolerance(plan.symbol)
        if tolerance > max_tolerance:
            logger.warning(
                f"Plan {plan.plan_id}: Tolerance {tolerance:.2f} exceeds maximum {max_tolerance:.2f}, capping"
            )
            tolerance = max_tolerance
        
        # Check if plan has entry_levels (Phase 2) or single entry_price
        # Priority: plan.entry_levels (database field) > plan.conditions.get("entry_levels") (legacy)
        entry_levels = plan.entry_levels or plan.conditions.get("entry_levels")
        
        if entry_levels and isinstance(entry_levels, list) and len(entry_levels) > 0:
            # Multi-level support (Phase 2)
            # Check each level in priority order (array order)
            for level_idx, level in enumerate(entry_levels):
                if isinstance(level, dict):
                    level_price = level.get("price", plan.entry_price)
                else:
                    level_price = level if isinstance(level, (int, float)) else plan.entry_price
                
                # Calculate zone bounds for this level
                if plan.direction == "BUY":
                    zone_upper = level_price + tolerance
                    zone_lower = level_price - tolerance
                    in_zone = zone_lower <= current_price <= zone_upper
                else:  # SELL
                    zone_upper = level_price + tolerance
                    zone_lower = level_price - tolerance
                    in_zone = zone_lower <= current_price <= zone_upper
                
                if in_zone:
                    # Price is in zone for this level
                    # Check if this is a new entry (was outside, now inside)
                    entry_detected = previous_in_zone is False if previous_in_zone is not None else True
                    return (True, level_idx, entry_detected)
            
            # No level is in zone
            return (False, None, False)
        else:
            # Single entry_price (current implementation)
            entry_price = plan.entry_price
            
            # Calculate zone bounds
            if plan.direction == "BUY":
                # For BUY: Execute when price is at or below entry_price + tolerance
                zone_upper = entry_price + tolerance
                zone_lower = entry_price - tolerance
                in_zone = zone_lower <= current_price <= zone_upper
            else:  # SELL
                # For SELL: Execute when price is at or above entry_price - tolerance
                zone_upper = entry_price + tolerance
                zone_lower = entry_price - tolerance
                in_zone = zone_lower <= current_price <= zone_upper
            
            # Check if this is a new entry (was outside, now inside)
            entry_detected = previous_in_zone is False if previous_in_zone is not None else True
            
            return (in_zone, None, entry_detected)
    
    def _get_max_tolerance(self, symbol: str) -> float:
        """
        Get maximum allowed tolerance for symbol.
        
        NOTE: This method is the source of truth for maximum tolerance values.
        VolatilityToleranceCalculator also has a _get_max_tolerance method for fallback,
        but AutoExecutionSystem's method takes precedence when available.
        """
        symbol_upper = symbol.upper().rstrip('C')
        
        if "XAU" in symbol_upper or "GOLD" in symbol_upper:
            return 10.0  # Maximum 10 points for XAUUSDc
        elif "BTC" in symbol_upper:
            return 200.0  # Maximum 200 points for BTC
        elif "ETH" in symbol_upper:
            return 20.0  # Maximum 20 points for ETH
        else:
            return 0.01  # Default for forex
    
    def _get_config_version(self) -> str:
        """Get config version from tolerance_config.json"""
        try:
            import json
            config_path = Path("config/tolerance_config.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                return config.get("config_version", "unknown")
        except:
            pass
        return "unknown"
    
    def _get_execution_buffer(self, symbol: str, tolerance: float, volatility_regime: Optional[str] = None) -> float:
        """
        Get execution buffer (max acceptable deviation from planned entry).
        
        Supports config-driven buffers with volatility-aware selection.
        Falls back to hard-coded defaults if config unavailable.
        """
        # Normalize symbol for config lookup: ensure consistent format (e.g., "XAUUSDc")
        symbol_base = symbol.upper().rstrip('C')
        symbol_config_key = symbol_base + 'c'  # Always use lowercase 'c' for config keys
        
        # Try to load from config first
        try:
            import json
            config_path = Path("config/tolerance_config.json")
            
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                # Try exact match first (e.g., "XAUUSDc"), then try without 'c' (e.g., "XAUUSD")
                buffers = config.get("execution_buffers", {}).get(symbol_config_key, {})
                if not buffers:
                    buffers = config.get("execution_buffers", {}).get(symbol_base, {})
                
                # Volatility-aware buffer selection
                if volatility_regime == "high_vol" and "high_vol" in buffers:
                    buffer = buffers["high_vol"]
                    logger.debug(f"Using high_vol buffer {buffer:.2f} for {symbol}")
                    return float(buffer)
                elif volatility_regime == "low_vol" and "low_vol" in buffers:
                    buffer = buffers["low_vol"]
                    logger.debug(f"Using low_vol buffer {buffer:.2f} for {symbol}")
                    return float(buffer)
                elif "default" in buffers:
                    buffer = buffers["default"]
                    logger.debug(f"Using default buffer {buffer:.2f} for {symbol} from config")
                    return float(buffer)
        except Exception as e:
            logger.debug(f"Could not load buffer config: {e}, using defaults")
        
        # Fallback to hard-coded defaults (symbol-specific)
        # Use symbol_base (without 'c') for symbol type detection
        if "XAU" in symbol_base or "GOLD" in symbol_base:
            return 3.0  # 3 points buffer for XAUUSDc
        elif "BTC" in symbol_base:
            return 30.0  # 30 points buffer for BTC
        elif "ETH" in symbol_base:
            return 3.0  # 3 points buffer for ETH
        else:
            # Forex and others: 30% of tolerance
            return tolerance * 0.3
    
    def _detect_plan_type(self, plan: TradePlan) -> str:
        """
        Detect plan type based on conditions and timeframe.
        
        Returns:
            'm1_micro_scalp', 'm5_range_scalp', 'm15_range_scalp', or 'default'
        """
        # Check cache first
        if plan.plan_id in self._plan_types:
            return self._plan_types[plan.plan_id]
        
        timeframe = plan.conditions.get('timeframe', '').upper()
        
        # M1 micro-scalp detection
        if timeframe == 'M1':
            # Check for micro-scalp indicators
            has_liquidity_sweep = plan.conditions.get('liquidity_sweep', False)
            has_order_block = plan.conditions.get('order_block', False)
            has_equal_lows = plan.conditions.get('equal_lows', False) or plan.conditions.get('equal_highs', False)
            has_vwap_deviation = plan.conditions.get('vwap_deviation', False)
            
            # M1 with micro-scalp conditions
            if has_liquidity_sweep or has_order_block or has_equal_lows or has_vwap_deviation:
                plan_type = 'm1_micro_scalp'
                self._plan_types[plan.plan_id] = plan_type
                return plan_type
        
        # M5 range scalp detection
        if timeframe == 'M5':
            has_range_scalp = plan.conditions.get('range_scalp_confluence') is not None
            has_vwap_deviation = plan.conditions.get('vwap_deviation', False)
            has_mean_reversion = 'mean_reversion' in str(plan.notes or '').lower()
            
            if has_range_scalp or (has_vwap_deviation and has_mean_reversion):
                plan_type = 'm5_range_scalp'
                self._plan_types[plan.plan_id] = plan_type
                return plan_type
        
        # M15 range scalp detection
        if timeframe == 'M15':
            has_range_scalp = plan.conditions.get('range_scalp_confluence') is not None
            if has_range_scalp:
                plan_type = 'm15_range_scalp'
                self._plan_types[plan.plan_id] = plan_type
                return plan_type
        
        # Default
        plan_type = 'default'
        self._plan_types[plan.plan_id] = plan_type
        return plan_type
    
    def _invalidate_cache_on_candle_close(self, symbol: str, timeframe: str = 'M1'):
        """
        Invalidate M1 cache when new candle closes.
        
        Args:
            symbol: Symbol to check
            timeframe: Timeframe (M1 only for now)
        """
        if timeframe != 'M1' or not self.m1_data_fetcher:
            return
        
        opt_config = self.config.get('optimized_intervals', {})
        if not opt_config.get('smart_caching', {}).get('invalidate_on_candle_close', False):
            return
        
        try:
            # Normalize symbol for consistency
            symbol_base = symbol.upper().rstrip('Cc')
            symbol_norm = symbol_base + 'c'
            
            # Get latest candle time (without cache)
            candles = self.m1_data_fetcher.fetch_m1_data(symbol_norm, count=1, use_cache=False)
            if not candles or len(candles) == 0:
                return
            
            latest_candle = candles[-1]
            latest_candle_time = latest_candle.get('time')
            
            if not latest_candle_time:
                return
            
            # Convert latest_candle_time to comparable format (datetime)
            if isinstance(latest_candle_time, datetime):
                latest_time = latest_candle_time
                # Ensure UTC-aware
                if latest_time.tzinfo is None:
                    latest_time = latest_time.replace(tzinfo=timezone.utc)
            elif isinstance(latest_candle_time, (int, float)):
                # CRITICAL: MT5 timestamps are UTC, must use tz=timezone.utc
                latest_time = datetime.fromtimestamp(latest_candle_time, tz=timezone.utc)
            else:
                logger.debug(f"Unknown candle time format for {symbol_norm}: {type(latest_candle_time)}")
                return  # Unknown format
            
            cached_time = self._m1_latest_candle_times.get(symbol_norm)
            
            if cached_time != latest_time:
                # New candle - invalidate M1 cache (use normalized symbol)
                if symbol_norm in self._m1_data_cache:
                    del self._m1_data_cache[symbol_norm]
                if symbol_norm in self._m1_cache_timestamps:
                    del self._m1_cache_timestamps[symbol_norm]
                
                # Store new candle time (use normalized symbol)
                self._m1_latest_candle_times[symbol_norm] = latest_time
                logger.info(
                    f"Smart caching: Invalidated M1 cache for {symbol_norm} due to new candle close "
                    f"(candle time: {latest_time.strftime('%H:%M:%S')} UTC)"
                )
        except Exception as e:
            logger.debug(f"Error checking candle close for {symbol}: {e}")
    
    def _prefetch_data_before_expiry(self):
        """
        Pre-fetch M1 data for plans before cache expires.
        Runs in background thread.
        """
        opt_config = self.config.get('optimized_intervals', {})
        if not opt_config.get('smart_caching', {}).get('enabled', False):
            return
        
        prefetch_seconds = opt_config.get('smart_caching', {}).get('prefetch_seconds_before_expiry', 3)
        cache_ttl = opt_config.get('smart_caching', {}).get('m1_cache_ttl_seconds', 20)
        
        while self.running:
            try:
                # Get symbols with active plans
                active_symbols = set()
                with self.plans_lock:
                    for plan in self.plans.values():
                        if plan.status == 'pending':
                            symbol_norm = plan.symbol.upper().rstrip('Cc') + 'c'
                            active_symbols.add(symbol_norm)
                
                # Check cache expiry times using existing _m1_cache_timestamps
                # _m1_cache_timestamps stores float timestamps (time.time())
                now_time = time.time()
                
                for symbol in active_symbols:
                    if symbol not in self._m1_cache_timestamps:
                        continue
                    
                    # Get cache timestamp (stored as float from time.time())
                    cache_timestamp = self._m1_cache_timestamps.get(symbol)
                    
                    if not isinstance(cache_timestamp, (int, float)):
                        continue
                    
                    # Calculate time until expiry
                    cache_age = now_time - cache_timestamp
                    time_until_expiry = cache_ttl - cache_age
                    
                    if 0 < time_until_expiry <= prefetch_seconds:
                        # Pre-fetch data
                        logger.debug(
                            f"Smart caching: Pre-fetching M1 data for {symbol} "
                            f"({time_until_expiry:.1f}s until expiry, cache age: {cache_age:.1f}s)"
                        )
                        try:
                            if self.m1_data_fetcher:
                                self.m1_data_fetcher.fetch_m1_data(symbol, count=200, use_cache=False)
                            else:
                                logger.debug(f"M1 data fetcher not available for {symbol}")
                        except Exception as prefetch_error:
                            logger.debug(f"Error pre-fetching M1 data for {symbol}: {prefetch_error}")
                            # Continue with other symbols - pre-fetch failure is non-critical
                
                # Sleep for 1 second
                time.sleep(1)
                
            except Exception as e:
                logger.debug(f"Error in pre-fetch thread: {e}")
                time.sleep(5)
    
    def _should_check_plan(self, plan: TradePlan, current_price: float) -> bool:
        """
        Determine if plan should be checked based on price proximity.
        
        Args:
            plan: Trade plan
            current_price: Current market price
            
        Returns:
            True if plan should be checked, False otherwise
        """
        opt_config = self.config.get('optimized_intervals', {})
        conditional_config = opt_config.get('conditional_checks', {})
        
        if not conditional_config.get('enabled', False):
            return True
        
        if not conditional_config.get('price_proximity_filter', False):
            return True
        
        # Calculate price distance from entry
        entry_price = plan.entry_price
        tolerance = plan.conditions.get('tolerance', 0)
        
        if tolerance == 0:
            return True  # No tolerance specified, always check
        
        price_distance = abs(current_price - entry_price)
        proximity_multiplier = conditional_config.get('proximity_multiplier', 2.0)
        proximity_threshold = tolerance * proximity_multiplier
        
        # Only check if price is within 2× tolerance
        if price_distance <= proximity_threshold:
            return True
        
        # Price is too far - skip check
        logger.debug(
            f"Conditional check: Skipping {plan.plan_id} - price {current_price:.2f} is "
            f"{price_distance:.2f} away from entry {entry_price:.2f} "
            f"(threshold: {proximity_threshold:.2f}, tolerance: {tolerance:.2f})"
        )
        return False
    
    # Phase 1.3: Price cache methods
    def _get_cached_price(self, symbol: str) -> Optional[float]:
        """
        Get cached price for symbol if available and not expired.
        Implements LRU eviction by moving accessed items to end.
        
        Args:
            symbol: Symbol to get price for
            
        Returns:
            Cached price if available and fresh, None otherwise
        """
        with self._price_cache_lock:
            if symbol not in self._price_cache:
                self._price_cache_misses += 1
                return None
            
            cache_entry = self._price_cache[symbol]
            now = datetime.now(timezone.utc)
            age = (now - cache_entry['timestamp']).total_seconds()
            
            # Check if expired
            if age > self._price_cache_ttl:
                # Remove expired entry (LRU: move to end then pop)
                self._price_cache.move_to_end(symbol)
                del self._price_cache[symbol]
                self._price_cache_misses += 1
                return None
            
            # Cache hit - move to end (LRU)
            self._price_cache.move_to_end(symbol)
            cache_entry['access_count'] = cache_entry.get('access_count', 0) + 1
            self._price_cache_hits += 1
            return cache_entry['price']
    
    def _update_price_cache(self, symbol: str, price: float, bid: float, ask: float) -> None:
        """
        Update price cache with new data.
        Implements LRU eviction if cache is full.
        
        Args:
            symbol: Symbol to cache
            price: Mid price
            bid: Bid price
            ask: Ask price
        """
        with self._price_cache_lock:
            now = datetime.now(timezone.utc)
            cache_entry = {
                'price': price,
                'bid': bid,
                'ask': ask,
                'timestamp': now,
                'access_count': 0
            }
            
            # If symbol already exists, update it (move to end for LRU)
            if symbol in self._price_cache:
                self._price_cache.move_to_end(symbol)
                self._price_cache[symbol] = cache_entry
            else:
                # New symbol - check if cache is full
                if len(self._price_cache) >= self._price_cache_max_size:
                    # LRU eviction: remove oldest (first) item
                    self._price_cache.popitem(last=False)
                
                # Add new entry (at end for LRU)
                self._price_cache[symbol] = cache_entry
    
    def _invalidate_price_cache(self, symbol: Optional[str] = None) -> None:
        """
        Invalidate price cache for specific symbol or all symbols.
        
        Args:
            symbol: Symbol to invalidate, or None to invalidate all
        """
        with self._price_cache_lock:
            if symbol is None:
                self._price_cache.clear()
            elif symbol in self._price_cache:
                del self._price_cache[symbol]
    
    def _cleanup_price_cache(self) -> None:
        """
        Clean up expired entries and symbols not in active plans.
        Called periodically from _periodic_cache_cleanup.
        """
        try:
            with self._price_cache_lock:
                now = datetime.now(timezone.utc)
                expired_symbols = []
                
                # Find expired entries
                for symbol, cache_entry in list(self._price_cache.items()):
                    age = (now - cache_entry['timestamp']).total_seconds()
                    if age > self._price_cache_ttl:
                        expired_symbols.append(symbol)
                
                # Remove expired entries
                for symbol in expired_symbols:
                    del self._price_cache[symbol]
                
                if expired_symbols:
                    logger.debug(f"Cleaned up {len(expired_symbols)} expired price cache entries")
                
                # Remove symbols not in active plans
                with self.plans_lock:
                    active_symbols = set()
                    for plan in self.plans.values():
                        if plan.status == 'pending':
                            symbol_norm = plan.symbol.upper().rstrip('Cc') + 'c'
                            active_symbols.add(symbol_norm)
                
                inactive_symbols = [
                    symbol for symbol in self._price_cache.keys()
                    if symbol not in active_symbols
                ]
                
                for symbol in inactive_symbols:
                    del self._price_cache[symbol]
                
                if inactive_symbols:
                    logger.debug(f"Cleaned up {len(inactive_symbols)} inactive price cache entries")
                
                # Phase 6: Track cache cleanup
                if expired_symbols or inactive_symbols:
                    self._cache_cleanup_count += 1
        except Exception as e:
            logger.debug(f"Error cleaning up price cache: {e}")
    
    def _update_volatility_tracking(self, symbol: str) -> None:
        """
        Update volatility tracking for a symbol (ATR).
        Called from price fetching to keep volatility data current.
        
        Phase 5: Used for adaptive interval adjustments.
        
        Args:
            symbol: Symbol to update volatility for
        """
        try:
            if not self.volatility_tolerance_calculator:
                return
            
            # Get current ATR (normalized)
            atr = self.volatility_tolerance_calculator.get_atr(symbol)
            if atr is not None:
                # Store normalized ATR value for adaptive interval calculations
                self._plan_volatility[symbol] = atr
        except Exception as e:
            logger.debug(f"Error updating volatility tracking for {symbol}: {e}")
    
    def _get_current_prices_batch(self) -> Dict[str, float]:
        """
        Get current prices for all active symbols in one batch.
        Phase 1.5: Now uses price cache to reduce API calls.
        
        Returns:
            Dictionary mapping symbol to current price (mid price)
        """
        prices = {}
        
        # Get unique symbols from active plans (with lock)
        active_symbols = set()
        try:
            with self.plans_lock:
                for plan in self.plans.values():
                    if plan.status == 'pending':
                        symbol_norm = plan.symbol.upper().rstrip('Cc') + 'c'
                        active_symbols.add(symbol_norm)
        except Exception as e:
            logger.warning(f"Error getting active symbols: {e}")
            return prices
        
        if not active_symbols:
            return prices
        
        # Phase 1.5: Check cache first, then fetch missing symbols
        symbols_to_fetch = []
        for symbol in active_symbols:
            cached_price = self._get_cached_price(symbol)
            if cached_price is not None:
                prices[symbol] = cached_price
                self._batch_fetch_cache_hits += 1
            else:
                symbols_to_fetch.append(symbol)
        
        # Phase 2.2: True batching - process symbols in chunks of 20
        if symbols_to_fetch and self.mt5_service:
            self._batch_fetch_total += 1
            try:
                if not self.mt5_service.connect():
                    logger.warning("MT5 not connected, cannot fetch prices")
                    self._batch_fetch_failures += 1
                    return prices
                
                # Phase 2.2: Process symbols in chunks of 20
                chunk_size = 20
                for i in range(0, len(symbols_to_fetch), chunk_size):
                    chunk = symbols_to_fetch[i:i + chunk_size]
                    self._fetch_price_chunk(chunk, prices)
                
                # If we got prices for any symbols, mark as success
                if any(s in prices for s in symbols_to_fetch):
                    self._batch_fetch_success += 1
                else:
                    self._batch_fetch_failures += 1
            except Exception as e:
                logger.warning(f"Error in batch price fetch: {e}")
                self._batch_fetch_failures += 1
        
        return prices
    
    # Phase 4.3: Plan priority calculation for market orders
    def _get_plan_priority(self, plan: TradePlan, current_price: Optional[float] = None) -> int:
        """
        Calculate priority for a plan (1=High, 2=Medium, 3=Low).
        Higher priority plans are checked first in parallel batches.
        
        Priority factors:
        - Distance from entry price (<1% = High, <2% = Medium, >2% = Low)
        - Plan activity (recent condition met = High)
        - Plan age (new plans near entry = High)
        
        Args:
            plan: Trade plan to prioritize
            current_price: Current market price (if None, will be fetched)
            
        Returns:
            Priority level: 1 (High), 2 (Medium), or 3 (Low)
        """
        try:
            # Get current price if not provided
            if current_price is None:
                if not self.mt5_service:
                    return 3  # Low priority if MT5 unavailable
                try:
                    symbol_norm = plan.symbol.upper().rstrip('Cc') + 'c'
                    quote = self.mt5_service.get_quote(symbol_norm)
                    if quote:
                        current_price = (quote.bid + quote.ask) / 2
                    else:
                        return 3  # Low priority if price unavailable
                except Exception:
                    return 3  # Low priority on error
            
            # Validate entry price
            if not plan.entry_price or plan.entry_price <= 0:
                logger.warning(f"Invalid entry_price for plan {plan.plan_id}: {plan.entry_price}")
                return 3  # Low priority
            
            # Calculate distance from entry (percentage)
            distance_pct = abs(current_price - plan.entry_price) / plan.entry_price * 100
            
            # Get plan activity (when conditions were last met)
            plan_activity = self._plan_activity.get(plan.plan_id)
            
            # Get plan age
            try:
                plan_created = datetime.fromisoformat(plan.created_at.replace('Z', '+00:00'))
                if plan_created.tzinfo is None:
                    plan_created = plan_created.replace(tzinfo=timezone.utc)
                plan_age_hours = (datetime.now(timezone.utc) - plan_created).total_seconds() / 3600
            except Exception:
                plan_age_hours = 0  # Default to 0 if parsing fails
            
            # Get last check time
            last_check = self._plan_last_check.get(plan.plan_id)
            if last_check:
                time_since_check = (datetime.now(timezone.utc) - last_check).total_seconds() / 60  # minutes
            else:
                time_since_check = None
            
            # Priority calculation for market orders
            # High priority: Near entry (<1%) AND (recent activity OR new plan)
            if distance_pct < 1.0:
                if plan_activity:
                    activity_age_minutes = (datetime.now(timezone.utc) - plan_activity).total_seconds() / 60
                    if activity_age_minutes < 5:  # Activity within last 5 minutes
                        return 1  # High priority
                if plan_age_hours < 1:  # New plan (<1 hour old)
                    return 1  # High priority
                return 2  # Medium priority (near entry but no recent activity)
            
            # Medium priority: Within 2% of entry OR recent check
            if distance_pct < 2.0:
                return 2  # Medium priority
            if time_since_check and time_since_check < 10:  # Checked recently
                return 2  # Medium priority
            
            # Low priority: Far from entry (>2%) AND (old activity OR no activity with old plan)
            if distance_pct > 2.0:
                if plan_activity:
                    activity_age_hours = (datetime.now(timezone.utc) - plan_activity).total_seconds() / 3600
                    if activity_age_hours > 1:  # Activity >1 hour ago
                        return 3  # Low priority
                if plan_age_hours > 1:  # Plan >1 hour old with no activity
                    return 3  # Low priority
            
            # Default to medium priority
            return 2
            
        except Exception as e:
            logger.warning(f"Error calculating priority for plan {plan.plan_id}: {e}")
            return 3  # Low priority on error
    
    # Phase 4.4: Skip logic for plans
    def _should_skip_plan(self, plan: TradePlan, current_price: Optional[float] = None) -> bool:
        """
        Determine if a plan should be skipped in this monitoring cycle.
        
        Args:
            plan: Trade plan to check
            current_price: Current market price (optional)
            
        Returns:
            True if plan should be skipped, False otherwise
        """
        try:
            # Skip if not pending
            if plan.status != "pending":
                return True
            
            # Check adaptive interval (skip if checked recently)
            last_check = self._plan_last_check.get(plan.plan_id)
            if last_check:
                time_since_check = (datetime.now(timezone.utc) - last_check).total_seconds()
                
                # Get priority to determine skip threshold
                priority = self._get_plan_priority(plan, current_price)
                
                # Skip thresholds based on priority
                if priority == 1:  # High priority
                    skip_threshold = 15  # Check every 15s (base interval)
                elif priority == 2:  # Medium priority
                    skip_threshold = 30  # Check every 30s
                else:  # Low priority
                    skip_threshold = 60  # Check every 60s
                
                if time_since_check < skip_threshold:
                    return True  # Skip - checked too recently
            
            return False  # Don't skip
            
        except Exception as e:
            logger.warning(f"Error in skip logic for plan {plan.plan_id}: {e}")
            return False  # Don't skip on error
    
    def _fetch_price_chunk(self, symbols: List[str], prices: Dict[str, float], max_retries: int = 3) -> None:
        """
        Fetch prices for a chunk of symbols with retry logic.
        Phase 2.3: Includes exponential backoff retry logic and circuit breaker.
        
        Args:
            symbols: List of symbols to fetch
            prices: Dictionary to update with fetched prices
            max_retries: Maximum number of retry attempts
        """
        for symbol in symbols:
            # Phase 2.4: Check circuit breaker before fetching
            if not self._check_circuit_breaker_price_fetch(symbol):
                logger.debug(f"Skipping {symbol} - circuit breaker is open")
                continue
            
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    # MT5Service.get_quote() returns Quote dataclass with bid/ask attributes
                    quote = self.mt5_service.get_quote(symbol)
                    self._batch_fetch_api_calls += 1
                    
                    if quote:
                        # Quote is a dataclass with bid and ask attributes
                        try:
                            # Use mid price
                            bid = quote.bid
                            ask = quote.ask
                            mid_price = (bid + ask) / 2
                            prices[symbol] = mid_price
                            # Update cache
                            self._update_price_cache(symbol, mid_price, bid, ask)
                            # Phase 5: Update volatility tracking
                            self._update_volatility_tracking(symbol)
                            # Record success
                            self._record_circuit_breaker_success_price_fetch(symbol)
                            success = True
                        except (AttributeError, TypeError) as e:
                            logger.debug(f"Error accessing quote attributes for {symbol}: {e}")
                            # Fallback: try symbol_info_tick
                            tick = mt5.symbol_info_tick(symbol)
                            self._batch_fetch_api_calls += 1
                            if tick:
                                mid_price = (tick.bid + tick.ask) / 2
                                prices[symbol] = mid_price
                                self._update_price_cache(symbol, mid_price, tick.bid, tick.ask)
                                # Phase 5: Update volatility tracking
                                self._update_volatility_tracking(symbol)
                                self._record_circuit_breaker_success_price_fetch(symbol)
                                success = True
                            else:
                                raise Exception("Both quote and tick are None")
                    else:
                        # Quote is None - fallback to symbol_info_tick
                        tick = mt5.symbol_info_tick(symbol)
                        self._batch_fetch_api_calls += 1
                        if tick:
                            mid_price = (tick.bid + tick.ask) / 2
                            prices[symbol] = mid_price
                            self._update_price_cache(symbol, mid_price, tick.bid, tick.ask)
                            # Phase 5: Update volatility tracking
                            self._update_volatility_tracking(symbol)
                            self._record_circuit_breaker_success_price_fetch(symbol)
                            success = True
                        else:
                            raise Exception("Both quote and tick are None")
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        # Phase 2.3: Exponential backoff
                        wait_time = 2 ** retry_count  # 2, 4, 8 seconds
                        logger.debug(f"Retry {retry_count}/{max_retries} for {symbol} after {wait_time}s: {e}")
                        time.sleep(wait_time)
                    else:
                        # Max retries reached - record failure
                        logger.debug(f"Failed to fetch price for {symbol} after {max_retries} retries: {e}")
                        self._record_circuit_breaker_failure_price_fetch(symbol)
    
    # Phase 2.4: Circuit breaker methods for batch price fetching
    def _check_circuit_breaker_price_fetch(self, symbol: str) -> bool:
        """
        Check if circuit breaker is open for a symbol (skip fetch if open).
        
        Args:
            symbol: Symbol to check
            
        Returns:
            True if circuit breaker is closed (can fetch), False if open (skip fetch)
        """
        with self._circuit_breaker_lock:
            if symbol not in self._price_fetch_circuit_breakers:
                return True  # No circuit breaker = closed (can fetch)
            
            cb_state = self._price_fetch_circuit_breakers[symbol]
            failures = cb_state.get('failures', 0)
            
            # Circuit breaker opens after 3 consecutive failures
            if failures >= 3:
                opened_at = cb_state.get('opened_at')
                if opened_at:
                    # Check if 60 seconds have passed (reset window)
                    now = datetime.now(timezone.utc)
                    age = (now - opened_at).total_seconds()
                    if age >= 60:
                        # Reset circuit breaker (half-open state - allow one attempt)
                        cb_state['failures'] = 0
                        cb_state['opened_at'] = None
                        return True
                else:
                    # Mark as opened
                    cb_state['opened_at'] = datetime.now(timezone.utc)
                
                return False  # Circuit breaker is open
            
            return True  # Circuit breaker is closed
    
    def _record_circuit_breaker_failure_price_fetch(self, symbol: str) -> None:
        """
        Record a failure for a symbol's circuit breaker.
        
        Args:
            symbol: Symbol that failed
        """
        with self._circuit_breaker_lock:
            if symbol not in self._price_fetch_circuit_breakers:
                self._price_fetch_circuit_breakers[symbol] = {
                    'failures': 0,
                    'last_failure': None,
                    'opened_at': None
                }
            
            cb_state = self._price_fetch_circuit_breakers[symbol]
            cb_state['failures'] = cb_state.get('failures', 0) + 1
            cb_state['last_failure'] = datetime.now(timezone.utc)
            
            # If this is the 3rd failure, mark as opened
            if cb_state['failures'] >= 3 and not cb_state.get('opened_at'):
                cb_state['opened_at'] = datetime.now(timezone.utc)
                logger.warning(f"Circuit breaker opened for {symbol} after 3 consecutive failures")
    
    def _record_circuit_breaker_success_price_fetch(self, symbol: str) -> None:
        """
        Record a success for a symbol's circuit breaker (reset failure count).
        
        Args:
            symbol: Symbol that succeeded
        """
        with self._circuit_breaker_lock:
            if symbol in self._price_fetch_circuit_breakers:
                cb_state = self._price_fetch_circuit_breakers[symbol]
                cb_state['failures'] = 0
                cb_state['opened_at'] = None
    
    # Phase 4.5: Circuit breaker methods for parallel checks
    def _check_circuit_breaker_parallel(self) -> bool:
        """
        Check if circuit breaker is open for parallel condition checks.
        
        Returns:
            True if circuit breaker is closed (can proceed), False if open (skip parallel checks)
        """
        with self._circuit_breaker_lock:
            if self._circuit_breaker_failures < 3:
                return True  # Circuit breaker is closed
            
            # Circuit breaker is open - check if 5 minutes have passed
            if self._circuit_breaker_last_failure:
                now = datetime.now(timezone.utc)
                age = (now - self._circuit_breaker_last_failure).total_seconds()
                if age >= 300:  # 5 minutes
                    # Reset circuit breaker (half-open state)
                    self._circuit_breaker_failures = 0
                    self._circuit_breaker_last_failure = None
                    logger.info("Circuit breaker for parallel checks reset after 5 minutes")
                    return True
            
            return False  # Circuit breaker is open
    
    def _record_circuit_breaker_failure_parallel(self) -> None:
        """Record a failure for parallel condition checks circuit breaker."""
        with self._circuit_breaker_lock:
            self._circuit_breaker_failures += 1
            self._circuit_breaker_last_failure = datetime.now(timezone.utc)
            
            if self._circuit_breaker_failures >= 3:
                logger.warning(
                    f"Circuit breaker opened for parallel condition checks "
                    f"after {self._circuit_breaker_failures} consecutive failures"
                )
    
    def _record_circuit_breaker_success_parallel(self) -> None:
        """Record a success for parallel condition checks (reset failure count)."""
        with self._circuit_breaker_lock:
            if self._circuit_breaker_failures > 0:
                self._circuit_breaker_failures = 0
                self._circuit_breaker_last_failure = None
    
    # Phase 4.5: Parallel condition checking
    def _check_conditions_parallel(self, plans: List[TradePlan], symbol_prices: Dict[str, float]) -> Dict[str, bool]:
        """
        Check conditions for multiple plans in parallel.
        
        Args:
            plans: List of plans to check
            symbol_prices: Dictionary of symbol -> current price (from batch fetch)
            
        Returns:
            Dictionary mapping plan_id -> bool (True if conditions met, False otherwise)
        """
        results = {}
        
        if not plans:
            return results
        
        # Check circuit breaker
        if not self._check_circuit_breaker_parallel():
            logger.debug("Circuit breaker is open for parallel checks - falling back to sequential")
            # Fallback to sequential checks
            for plan in plans:
                try:
                    results[plan.plan_id] = self._check_conditions(plan)
                except Exception as e:
                    logger.warning(f"Error checking conditions for plan {plan.plan_id}: {e}")
                    results[plan.plan_id] = False
            return results
        
        if not self._condition_check_executor:
            # Fallback to sequential if executor not available
            logger.debug("Thread pool executor not available - using sequential checks")
            for plan in plans:
                try:
                    results[plan.plan_id] = self._check_conditions(plan)
                except Exception as e:
                    logger.warning(f"Error checking conditions for plan {plan.plan_id}: {e}")
                    results[plan.plan_id] = False
            return results
        
        # Process plans in batches of 10-20 to avoid overwhelming the executor
        batch_size = min(20, len(plans))
        total_failures = 0
        
        # Phase 6: Track parallel check metrics
        self._parallel_checks_total += len(plans)
        num_batches = (len(plans) + batch_size - 1) // batch_size
        self._parallel_checks_batches += num_batches
        
        for i in range(0, len(plans), batch_size):
            batch = plans[i:i + batch_size]
            futures = {}
            
            # Submit batch to executor
            for plan in batch:
                try:
                    # Verify plan still exists (race condition check)
                    with self.plans_lock:
                        if plan.plan_id not in self.plans:
                            results[plan.plan_id] = False
                            continue
                    
                    # Submit condition check
                    future = self._condition_check_executor.submit(self._check_conditions, plan)
                    futures[plan.plan_id] = future
                except Exception as e:
                    logger.warning(f"Error submitting plan {plan.plan_id} for parallel check: {e}")
                    results[plan.plan_id] = False
                    total_failures += 1
            
            # Collect results with timeout
            for plan_id, future in futures.items():
                try:
                    # Timeout per plan: 10 seconds
                    result = future.result(timeout=10.0)
                    results[plan_id] = result
                    
                    # Update activity tracking if conditions were met
                    if result:
                        with self.plans_lock:
                            self._plan_activity[plan_id] = datetime.now(timezone.utc)
                except FutureTimeoutError:
                    logger.warning(f"Timeout checking conditions for plan {plan_id}")
                    results[plan_id] = False
                    total_failures += 1
                except Exception as e:
                    logger.warning(f"Error checking conditions for plan {plan_id}: {e}")
                    results[plan_id] = False
                    total_failures += 1
            
            # Check if batch had too many failures (>50%)
            batch_failures = sum(1 for r in results.values() if not r)
            if batch_failures > len(batch) * 0.5:
                total_failures += batch_failures
        
        # Record circuit breaker state
        if total_failures > len(plans) * 0.5:
            self._record_circuit_breaker_failure_parallel()
        else:
            self._record_circuit_breaker_success_parallel()
        
        return results
    
    def _calculate_adaptive_interval(self, plan: TradePlan, current_price: float) -> int:
        """
        Calculate adaptive check interval based on plan type and price proximity.
        
        Args:
            plan: Trade plan
            current_price: Current market price
            
        Returns:
            Interval in seconds (defaults to self.check_interval on error)
        """
        try:
            # Check if adaptive intervals are enabled
            opt_config = self.config.get('optimized_intervals', {})
            if not opt_config.get('adaptive_intervals', {}).get('enabled', False):
                return self.check_interval
            
            # Get plan type (cached)
            plan_type = self._plan_types.get(plan.plan_id) or self._detect_plan_type(plan)
            interval_config = opt_config.get('adaptive_intervals', {}).get('plan_type_intervals', {}).get(plan_type, {})
            
            if not interval_config:
                return self.check_interval
            
            # Calculate price distance from entry
            entry_price = plan.entry_price
            tolerance = plan.conditions.get('tolerance', 0)
            
            if tolerance == 0:
                # No tolerance specified - use base interval
                return interval_config.get('base_interval_seconds', self.check_interval)
            
            price_distance = abs(current_price - entry_price)
            proximity_multiplier = interval_config.get('price_proximity_multiplier', 2.0)
            proximity_threshold = tolerance * proximity_multiplier
            
            # Phase 5: Determine base interval based on proximity
            calculated_interval = self.check_interval  # Default
            if price_distance <= tolerance:
                # Price is within tolerance - use close interval (fastest)
                calculated_interval = interval_config.get('close_interval_seconds', interval_config.get('base_interval_seconds', 10))
            elif price_distance <= proximity_threshold:
                # Price is within 2× tolerance - use base interval
                calculated_interval = interval_config.get('base_interval_seconds', 30)
            else:
                # Price is far - use far interval (slowest)
                calculated_interval = interval_config.get('far_interval_seconds', 60)
            
            # Phase 5: Activity-based adjustments
            plan_id = plan.plan_id
            plan_activity = self._plan_activity.get(plan_id)
            if plan_activity:
                activity_age_minutes = (datetime.now(timezone.utc) - plan_activity).total_seconds() / 60
                if activity_age_minutes < 5:
                    # Recent activity (<5 min) - reduce interval by 20% (faster checks)
                    calculated_interval = int(calculated_interval * 0.8)
                elif activity_age_minutes > 60:
                    # Old activity (>1 hour) - increase interval by 50% (slower checks)
                    calculated_interval = int(calculated_interval * 1.5)
            
            # Phase 5: Volatility-based adjustments
            symbol_norm = plan.symbol.upper().rstrip('Cc') + 'c'
            volatility = self._plan_volatility.get(symbol_norm)
            if volatility is not None:
                # High volatility (>2.0 ATR) - reduce interval by 15% (faster checks)
                # Low volatility (<0.5 ATR) - increase interval by 20% (slower checks)
                if volatility > 2.0:
                    calculated_interval = int(calculated_interval * 0.85)
                elif volatility < 0.5:
                    calculated_interval = int(calculated_interval * 1.2)
            
            # Phase 5.1: Enforce minimum interval of self.check_interval (15s)
            # Prevents adaptive from returning values below 15s (current code allows 10s)
            calculated_interval = max(calculated_interval, self.check_interval)
            
            # Log interval calculation for monitoring (debug level)
            logger.debug(
                f"Adaptive interval for {plan.plan_id} ({plan_type}): "
                f"{calculated_interval}s (price: {current_price:.2f}, entry: {entry_price:.2f}, "
                f"distance: {abs(current_price - entry_price):.2f}, tolerance: {tolerance:.2f})"
            )
            
            return calculated_interval
        except Exception as e:
            logger.debug(f"Error calculating adaptive interval for {plan.plan_id}: {e}")
            # Return default interval on error
            return self.check_interval
    
    # Phase 6: Performance metrics logging
    def _log_performance_metrics(self) -> None:
        """
        Log performance metrics for monitoring and analysis.
        Called periodically from monitoring loop.
        """
        try:
            if not self._metrics_start_time:
                return
            
            now = datetime.now(timezone.utc)
            uptime_seconds = (now - self._metrics_start_time).total_seconds()
            uptime_hours = uptime_seconds / 3600
            
            # Calculate rates
            condition_check_success_rate = (
                (self._condition_checks_success / self._condition_checks_total * 100)
                if self._condition_checks_total > 0 else 0.0
            )
            
            cache_hit_rate = (
                (self._price_cache_hits / (self._price_cache_hits + self._price_cache_misses) * 100)
                if (self._price_cache_hits + self._price_cache_misses) > 0 else 0.0
            )
            
            batch_fetch_success_rate = (
                (self._batch_fetch_success / self._batch_fetch_total * 100)
                if self._batch_fetch_total > 0 else 0.0
            )
            
            # Market orders per hour
            market_orders_per_hour = (
                self._market_orders_executed / uptime_hours
                if uptime_hours > 0 else 0.0
            )
            
            # Average batch size
            avg_batch_size = (
                self._parallel_checks_total / self._parallel_checks_batches
                if self._parallel_checks_batches > 0 else 0.0
            )
            
            logger.info(
                f"Performance Metrics (uptime: {uptime_hours:.1f}h): "
                f"Condition checks: {self._condition_checks_total} total "
                f"({condition_check_success_rate:.1f}% success), "
                f"Cache: {self._price_cache_hits} hits / {self._price_cache_misses} misses "
                f"({cache_hit_rate:.1f}% hit rate), "
                f"Batch fetch: {self._batch_fetch_total} total "
                f"({batch_fetch_success_rate:.1f}% success, {self._batch_fetch_api_calls} API calls), "
                f"Market orders: {self._market_orders_executed} total "
                f"({market_orders_per_hour:.2f}/hour), "
                f"Parallel checks: {self._parallel_checks_total} plans in {self._parallel_checks_batches} batches "
                f"(avg {avg_batch_size:.1f}/batch), "
                f"Cache cleanups: {self._cache_cleanup_count}"
            )
        except Exception as e:
            logger.warning(f"Error logging performance metrics: {e}")
    
    # Phase 6: Health check method
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of the auto execution system.
        
        Returns:
            Dictionary with health status information
        """
        try:
            health = {
                "status": "healthy",
                "uptime_seconds": 0,
                "uptime_hours": 0.0,
                "running": self.running,
                "active_plans": 0,
                "metrics": {
                    "condition_checks": {
                        "total": self._condition_checks_total,
                        "success": self._condition_checks_success,
                        "failed": self._condition_checks_failed,
                        "success_rate": 0.0
                    },
                    "price_cache": {
                        "hits": self._price_cache_hits,
                        "misses": self._price_cache_misses,
                        "hit_rate": 0.0,
                        "size": len(self._price_cache)
                    },
                    "batch_fetch": {
                        "total": self._batch_fetch_total,
                        "success": self._batch_fetch_success,
                        "failures": self._batch_fetch_failures,
                        "cache_hits": self._batch_fetch_cache_hits,
                        "api_calls": self._batch_fetch_api_calls,
                        "success_rate": 0.0
                    },
                    "market_orders": {
                        "total": self._market_orders_executed,
                        "per_hour": 0.0
                    },
                    "parallel_checks": {
                        "total": self._parallel_checks_total,
                        "batches": self._parallel_checks_batches,
                        "avg_batch_size": 0.0
                    }
                },
                "circuit_breakers": {
                    "parallel_checks": {
                        "failures": self._circuit_breaker_failures,
                        "open": self._circuit_breaker_failures >= 3
                    }
                },
                "warnings": []
            }
            
            # Calculate uptime
            if self._metrics_start_time:
                uptime_seconds = (datetime.now(timezone.utc) - self._metrics_start_time).total_seconds()
                health["uptime_seconds"] = int(uptime_seconds)
                health["uptime_hours"] = uptime_seconds / 3600
            
            # Get active plans count
            with self.plans_lock:
                health["active_plans"] = len([p for p in self.plans.values() if p.status == "pending"])
            
            # Calculate rates
            if self._condition_checks_total > 0:
                health["metrics"]["condition_checks"]["success_rate"] = (
                    self._condition_checks_success / self._condition_checks_total * 100
                )
            
            if (self._price_cache_hits + self._price_cache_misses) > 0:
                health["metrics"]["price_cache"]["hit_rate"] = (
                    self._price_cache_hits / (self._price_cache_hits + self._price_cache_misses) * 100
                )
            
            if self._batch_fetch_total > 0:
                health["metrics"]["batch_fetch"]["success_rate"] = (
                    self._batch_fetch_success / self._batch_fetch_total * 100
                )
            
            if health["uptime_hours"] > 0:
                health["metrics"]["market_orders"]["per_hour"] = (
                    self._market_orders_executed / health["uptime_hours"]
                )
            
            if self._parallel_checks_batches > 0:
                health["metrics"]["parallel_checks"]["avg_batch_size"] = (
                    self._parallel_checks_total / self._parallel_checks_batches
                )
            
            # Health checks
            if not self.running:
                health["status"] = "stopped"
                health["warnings"].append("System is not running")
            
            if self._circuit_breaker_failures >= 3:
                health["status"] = "degraded"
                health["warnings"].append("Circuit breaker for parallel checks is open")
            
            if health["metrics"]["condition_checks"]["success_rate"] < 50.0 and self._condition_checks_total > 10:
                health["status"] = "degraded"
                health["warnings"].append("Condition check success rate is below 50%")
            
            if health["metrics"]["batch_fetch"]["success_rate"] < 50.0 and self._batch_fetch_total > 5:
                health["status"] = "degraded"
                health["warnings"].append("Batch fetch success rate is below 50%")
            
            return health
        except Exception as e:
            logger.error(f"Error getting health status: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _get_btc_order_flow_metrics(self, plan: TradePlan, window_seconds: int = 300):
        """
        Get BTC order flow metrics (cached per plan check).
        
        This helper method centralizes access to order flow metrics and ensures
        we use the correct API (get_metrics() instead of non-existent methods).
        
        Args:
            plan: TradePlan instance
            window_seconds: Time window for metrics calculation (default: 300 = 5 minutes)
        
        Returns:
            OrderFlowMetrics object or None if unavailable
        """
        if not self.micro_scalp_engine:
            logger.debug(f"Order flow metrics unavailable for {plan.plan_id}: micro_scalp_engine not initialized")
            return None
        
        if not hasattr(self.micro_scalp_engine, 'btc_order_flow'):
            logger.debug(f"Order flow metrics unavailable for {plan.plan_id}: btc_order_flow not available in micro_scalp_engine")
            return None
        
        if not self.micro_scalp_engine.btc_order_flow:
            logger.debug(f"Order flow metrics unavailable for {plan.plan_id}: btc_order_flow is None")
            return None
        
        try:
            btc_flow = self.micro_scalp_engine.btc_order_flow
            # If BTCOrderFlowMetrics was initialized before OrderFlowService was running,
            # it may not have a service attached yet. Try to attach lazily.
            try:
                needs_attach = (not getattr(btc_flow, "order_flow_service", None)) or (hasattr(getattr(btc_flow, "order_flow_service", None), "running") and not btc_flow.order_flow_service.running)
                if needs_attach:
                    order_flow_service = None

                    # Try 1: desktop_agent.registry (normal case when running as module)
                    try:
                        from desktop_agent import registry as _da_registry
                        order_flow_service = getattr(_da_registry, "order_flow_service", None)
                    except Exception:
                        order_flow_service = None

                    # Try 2: __main__.registry (critical when desktop_agent.py is run as a script)
                    if not order_flow_service:
                        try:
                            import __main__ as _main
                            _main_registry = getattr(_main, "registry", None)
                            order_flow_service = getattr(_main_registry, "order_flow_service", None) if _main_registry else None
                        except Exception:
                            order_flow_service = None

                    # Try 3: chatgpt_bot.order_flow_service (fallback)
                    if not order_flow_service:
                        try:
                            import chatgpt_bot as _cb
                            order_flow_service = getattr(_cb, "order_flow_service", None)
                        except Exception:
                            order_flow_service = None

                    if order_flow_service and getattr(order_flow_service, "running", False):
                        btc_flow.order_flow_service = order_flow_service
                        # Optional: initialize tick engine if available
                        try:
                            if hasattr(btc_flow, "initialize_tick_engine"):
                                btc_flow.initialize_tick_engine("BTCUSDT")
                        except Exception:
                            pass
                        logger.info("✅ BTC order flow metrics attached to active OrderFlowService (lazy bind)")
            except Exception:
                # Never fail metrics retrieval due to lazy-bind issues
                pass

            metrics = btc_flow.get_metrics("BTCUSDT", window_seconds=window_seconds)
            if metrics:
                logger.debug(f"Order flow metrics retrieved for {plan.plan_id}")
            else:
                logger.debug(f"Order flow metrics returned None for {plan.plan_id} (insufficient data)")
            return metrics
        except Exception as e:
            logger.warning(f"Error getting order flow metrics for {plan.plan_id}: {e}", exc_info=True)
            return None
    
    def _check_conditions(self, plan: TradePlan) -> bool:
        """Check if conditions for a trade plan are met"""
        try:
            logger.debug(f"Plan {plan.plan_id}: Starting condition check")
            # Validate MT5 service exists
            if not self.mt5_service:
                logger.error(f"Plan {plan.plan_id}: MT5 service is None - cannot check conditions")
                return False
            
            # Check MT5 connection with error recovery
            # If MT5 has been down recently, skip checking to avoid wasting resources
            # Phase 4.1: Thread-safe read of MT5 state
            with self._mt5_state_lock:
                mt5_last_failure = self.mt5_last_failure_time
            
            if mt5_last_failure:
                try:
                    time_since_failure = (datetime.now(timezone.utc) - mt5_last_failure).total_seconds()
                    if time_since_failure < self.mt5_backoff_seconds:
                        logger.debug(f"MT5 connection failed recently ({time_since_failure:.0f}s ago), skipping condition check")
                        return False
                except Exception as e:
                    logger.warning(f"Error calculating MT5 failure time: {e}")
                    # Continue with connection attempt
            
            # Ensure MT5 is connected
            try:
                if not self.mt5_service.connect():
                    # Phase 4.1: Thread-safe MT5 state updates
                    with self._mt5_state_lock:
                        self.mt5_connection_failures += 1
                        self.mt5_last_failure_time = datetime.now(timezone.utc)
                        failure_count = self.mt5_connection_failures
                    logger.error(f"Plan {plan.plan_id}: Failed to connect to MT5 (failure #{failure_count})")
                    return False
                logger.debug(f"Plan {plan.plan_id}: MT5 connection OK")
            except AttributeError:
                logger.error("MT5 service missing 'connect' method")
                return False
            except Exception as e:
                logger.error(f"Error connecting to MT5: {e}", exc_info=True)
                return False
            
            # Reset connection failure tracking on successful connection
            # Phase 4.1: Thread-safe MT5 state updates
            with self._mt5_state_lock:
                if self.mt5_connection_failures > 0:
                    logger.debug(f"MT5 connection restored")
                    self.mt5_connection_failures = 0
                    self.mt5_last_failure_time = None
                
            # Validate plan has symbol
            if not plan or not hasattr(plan, 'symbol') or not plan.symbol:
                logger.warning(f"Plan {plan.plan_id if plan and hasattr(plan, 'plan_id') else 'unknown'} missing symbol")
                return False
            
            # Normalize symbol and ensure it's selected in MT5
            # Preserve case of suffix 'c' while uppercasing base symbol
            try:
                symbol_base = plan.symbol.upper().rstrip('Cc')
                if not plan.symbol.upper().endswith('C'):
                    symbol_norm = symbol_base + 'c'  # lowercase 'c' for MT5
                else:
                    symbol_norm = symbol_base + 'c'  # always use lowercase 'c'
            except (AttributeError, TypeError) as e:
                logger.warning(f"Error normalizing symbol for plan: {e}")
                return False
            
            # Try symbol variations if first attempt fails (case sensitivity)
            symbol_variations = [
                symbol_norm,           # BTCUSDc (preferred)
                symbol_base + 'C',     # BTCUSDC (uppercase variant)
                plan.symbol.upper(),   # Original uppercased
                plan.symbol,           # Original as-is
            ]
            
            # Find valid symbol by trying to get quote
            symbol_norm_actual = None
            for sym_var in symbol_variations:
                try:
                    quote = self.mt5_service.get_quote(sym_var)
                    symbol_norm_actual = sym_var
                    if sym_var != symbol_variations[0]:
                        logger.debug(f"Symbol found as '{sym_var}' instead of '{symbol_variations[0]}'")
                    break
                except Exception:
                    continue
            
            if symbol_norm_actual is None:
                # Phase 4.1: Thread-safe invalid_symbols updates
                with self._invalid_symbols_lock:
                    failure_count = self.invalid_symbols.get(plan.symbol, 0) + 1
                    self.invalid_symbols[plan.symbol] = failure_count
                
                if failure_count >= self.max_symbol_failures:
                    logger.error(
                        f"Symbol '{plan.symbol}' not found in MT5 after {failure_count} attempts. "
                        f"Marking plan {plan.plan_id} as failed."
                    )
                    plan.status = "failed"
                    plan.notes = (plan.notes or "") + f" [Symbol not found in MT5 after {failure_count} attempts]"
                    self._update_plan_status(plan)
                    with self.plans_lock:
                        if plan.plan_id in self.plans:
                            del self.plans[plan.plan_id]
                    return False
                else:
                    logger.warning(
                        f"Symbol '{plan.symbol}' not found in MT5 (attempt {failure_count}/{self.max_symbol_failures}). "
                        f"Check that the symbol exists in your MT5 broker's Market Watch."
                    )
                    return False
            
            # Use the actual symbol name that worked
            symbol_norm = symbol_norm_actual
            
            # Get current price using MT5Service
            try:
                quote = self.mt5_service.get_quote(symbol_norm)
                current_bid = quote.bid
                current_ask = quote.ask
            except Exception as e:
                logger.warning(
                    f"No tick data for {symbol_norm} (normalized from {plan.symbol}). "
                    f"Error: {e}"
                )
                return False
                
            current_price = current_ask if plan.direction == "BUY" else current_bid
            
            # ============================================================================
            # Phase 3.2: News Blackout Check & Execution Quality Validation
            # ============================================================================
            # Check news blackout (CRITICAL - prevent trading during high-impact news)
            try:
                from infra.news_service import NewsService
                news_service = NewsService()
                
                # Check if in news blackout for macro events (XAU, BTC affected by macro news)
                if "XAU" in symbol_norm or "BTC" in symbol_norm:
                    if news_service.is_blackout("macro"):
                        logger.warning(
                            f"Plan {plan.plan_id}: BLOCKED - High-impact news event within blackout window"
                        )
                        return False
            except Exception as e:
                logger.debug(f"Error checking news blackout for {plan.plan_id}: {e}")
                # Continue if check fails (non-critical, but should log warning)
            
            # ============================================================================
            # Phase III: Adaptive Scenario Condition Checks
            # ============================================================================
            # Check adaptive scenario conditions (news absorption filter, post-news reclaim)
            try:
                from infra.news_service import NewsService
                # Use instance news_service if available, otherwise try to create new instance
                if self.news_service is None:
                    try:
                        news_service = NewsService()
                    except Exception as e:
                        logger.debug(f"Could not create NewsService: {e}")
                        news_service = None
                else:
                    news_service = self.news_service
                
                # Check news absorption filter (pause breakout strategies during news)
                if plan.conditions.get("news_absorption_filter"):
                    if news_service is None:
                        logger.debug(f"Plan {plan.plan_id}: News service not available, skipping news absorption filter check")
                        # Continue with other conditions (graceful degradation)
                    else:
                        blackout_window = plan.conditions.get("news_blackout_window", 15)  # minutes
                        high_impact_types = plan.conditions.get("high_impact_news_types", ["CPI", "FOMC", "NFP"])
                        
                        # Check if in blackout for specified news types
                        # For now, check macro blackout (would need news type filtering enhancement)
                        if "XAU" in symbol_norm or "BTC" in symbol_norm:
                            try:
                                if news_service.is_blackout("macro"):
                                    logger.debug(f"Plan {plan.plan_id}: News absorption filter - blocked during news blackout")
                                    return False
                            except Exception as e:
                                logger.debug(f"Error checking news blackout: {e}")
                                # Continue with other conditions (graceful degradation)
                        
                        # TODO: Add news type filtering (CPI, FOMC, etc.) when NewsService supports it
                
                # Check post-news reclaim
                if plan.conditions.get("post_news_reclaim") or plan.conditions.get("price_reclaim_confirmed") or plan.conditions.get("cvd_flip_confirmed"):
                    if news_service is None:
                        logger.debug(f"Plan {plan.plan_id}: News service not available, skipping post-news reclaim check")
                        # Continue with other conditions (graceful degradation)
                    else:
                        # Track pre-news level (store when news detected, 15 min before)
                        # For now, use current price as proxy (would need proper tracking)
                        pre_news_level = plan.conditions.get("pre_news_level")
                        
                        if pre_news_level:
                            # Check price reclaim: price returns to within 0.1% of pre-news level (or 0.5 ATR)
                            price_diff_pct = abs(current_price - pre_news_level) / pre_news_level if pre_news_level > 0 else float('inf')
                            atr = _calculate_atr_simple(_get_recent_candles(symbol_norm, timeframe="M15", count=20))
                            
                            if atr:
                                atr_threshold = 0.5 * atr
                            price_reclaim_confirmed = (
                                price_diff_pct <= 0.001 or  # 0.1% threshold
                                abs(current_price - pre_news_level) <= atr_threshold  # 0.5 ATR threshold
                            )
                        else:
                            price_reclaim_confirmed = price_diff_pct <= 0.001
                        
                        if plan.conditions.get("price_reclaim_confirmed") and not price_reclaim_confirmed:
                            logger.debug(f"Plan {plan.plan_id}: Price reclaim not confirmed (diff: {price_diff_pct:.2%})")
                            return False
                        
                        # Check CVD flip (requires order flow data for BTC)
                        if plan.conditions.get("cvd_flip_confirmed"):
                            if symbol_norm.upper().startswith('BTC'):
                                try:
                                    from desktop_agent import registry
                                    if hasattr(registry, 'order_flow_service') and registry.order_flow_service:
                                        if hasattr(registry.order_flow_service, 'analyzer'):
                                            order_flow_analyzer = registry.order_flow_service.analyzer
                                            microstructure = order_flow_analyzer.get_phase3_microstructure_metrics(symbol_norm)
                                            
                                            if microstructure:
                                                # Get CVD from order flow (would need historical CVD tracking)
                                                # For now, check if CVD slope changed
                                                # TODO: Implement proper CVD flip detection with historical tracking
                                                logger.debug(f"Plan {plan.plan_id}: CVD flip check (requires historical CVD tracking)")
                                                # Placeholder - would need CVD history to detect flip
                                            else:
                                                logger.debug(f"Plan {plan.plan_id}: CVD data unavailable for flip check")
                                                return False
                                except (ImportError, AttributeError):
                                    logger.debug(f"Plan {plan.plan_id}: Order flow service unavailable for CVD flip")
                                    return False
                            else:
                                logger.debug(f"Plan {plan.plan_id}: CVD flip only available for BTC symbols")
                                return False
                        else:
                            # Pre-news level not set - would need to track when news detected
                            logger.debug(f"Plan {plan.plan_id}: Pre-news level not available for reclaim check")
                            if plan.conditions.get("price_reclaim_confirmed"):
                                return False
                
            except Exception as e:
                logger.error(f"Error checking adaptive scenario conditions for {plan.plan_id}: {e}", exc_info=True)
                # Continue if check fails (non-critical for some conditions)
                if plan.conditions.get("news_absorption_filter"):
                    return False  # Fail closed for news absorption filter
            
            # Check execution quality (spread width)
            # Wide spreads = poor execution quality, higher slippage risk
            try:
                spread = abs(current_ask - current_bid)
                spread_pct = (spread / current_price) * 100 if current_price > 0 else 0
                
                # XAU: Normal spread ~0.01-0.05% (0.5-2.5 points at 4500)
                # BTC: Normal spread ~0.01-0.03% (10-30 points at 100k)
                # Block if spread > 3x normal (likely poor execution)
                if "XAU" in symbol_norm:
                    max_spread_pct = 0.15  # 0.15% = ~6.75 points at 4500 (3x normal)
                    if spread_pct > max_spread_pct:
                        logger.warning(
                            f"Plan {plan.plan_id}: Spread too wide: {spread:.2f} points ({spread_pct:.3f}%) "
                            f"> {max_spread_pct:.3f}% - poor execution quality"
                        )
                        return False
                elif "BTC" in symbol_norm:
                    max_spread_pct = 0.09  # 0.09% = ~90 points at 100k (3x normal)
                    if spread_pct > max_spread_pct:
                        logger.warning(
                            f"Plan {plan.plan_id}: Spread too wide: {spread:.2f} points ({spread_pct:.3f}%) "
                            f"> {max_spread_pct:.3f}% - poor execution quality"
                        )
                        return False
            except Exception as e:
                logger.debug(f"Error checking execution quality for {plan.plan_id}: {e}")
                # Continue if check fails (non-critical)
            
            # Check plan staleness (entry price still valid)
            # If price has moved too far from entry, plan may be stale
            try:
                entry_price = plan.entry_price
                
                # Calculate price distance
                price_distance = abs(current_price - entry_price)
                price_distance_pct = (price_distance / entry_price) * 100 if entry_price > 0 else 0
                
                # Get tolerance
                tolerance = plan.conditions.get("tolerance")
                if tolerance is None:
                    from infra.tolerance_helper import get_price_tolerance
                    tolerance = get_price_tolerance(plan.symbol)
                
                # If price moved more than 2x tolerance, plan is likely stale
                max_stale_distance = tolerance * 2
                if price_distance > max_stale_distance:
                    logger.warning(
                        f"Plan {plan.plan_id}: Entry price may be stale - "
                        f"current price {current_price:.2f} is {price_distance:.2f} away from entry {entry_price:.2f} "
                        f"(>{max_stale_distance:.2f} tolerance)"
                    )
                    # Don't block, but log warning (price_near condition will handle this)
            except Exception as e:
                logger.debug(f"Error checking plan staleness for {plan.plan_id}: {e}")
                # Continue if check fails (non-critical)
            
            # ============================================================================
            # End Phase 3.2: News Blackout & Execution Quality
            # ============================================================================
            
            # ============================================================================
            # Phase 4.5: Circuit Breaker, Feature Flag, and Confidence Checks
            # ============================================================================
            
            # Check circuit breaker (if strategy_type specified)
            strategy_name = (
                plan.conditions.get("strategy_type") or
                plan.conditions.get("strategy")
            )
            if strategy_name:
                try:
                    from infra.strategy_circuit_breaker import StrategyCircuitBreaker
                    breaker = StrategyCircuitBreaker()
                    
                    if breaker.is_strategy_disabled(strategy_name):
                        logger.debug(f"Plan {plan.plan_id} strategy {strategy_name} disabled by circuit breaker")
                        return False
                except Exception as e:
                    logger.warning(f"Error checking circuit breaker for {plan.plan_id}: {e}")
                    # Don't block execution if circuit breaker check fails (graceful degradation)
            
            # Check feature flag (if strategy_type specified)
            if strategy_name:
                try:
                    import json
                    config_path = Path("config/strategy_feature_flags.json")
                    if config_path.exists():
                        with open(config_path, 'r') as f:
                            flags = json.load(f)
                        strategy_flags = flags.get("strategy_feature_flags", {}).get(strategy_name, {})
                        
                        if not strategy_flags.get("enabled", True):  # Default True for graceful degradation
                            logger.debug(f"Plan {plan.plan_id} strategy {strategy_name} disabled by feature flag")
                            return False
                except Exception as e:
                    logger.warning(f"Error checking feature flag for {plan.plan_id}: {e}")
                    # Don't block execution if feature flag check fails (graceful degradation)
            
            # Check confidence threshold (if strategy_type and min_confidence specified)
            if strategy_name and plan.conditions.get("min_confidence"):
                try:
                    from infra.detection_systems import DetectionSystemManager
                    detector = DetectionSystemManager()
                    
                    # Map strategy name to detection type
                    strategy_to_detection = {
                        "order_block_rejection": "order_block",
                        "breaker_block": "breaker_block",
                        "fvg_retracement": "fvg",
                        "market_structure_shift": "mss",
                        "mitigation_block": "mitigation_block",
                        "inducement_reversal": "rejection_pattern",
                        "premium_discount_array": "fibonacci_levels",
                        "session_liquidity_run": "session_liquidity",
                        "kill_zone": "kill_zone",
                    }
                    
                    detection_type = strategy_to_detection.get(strategy_name)
                    if detection_type:
                        # Get detection result for the strategy
                        detection_result = detector.get_detection_result(symbol_norm, detection_type, timeframe=structure_tf)
                        
                        if not detection_result:
                            logger.debug(f"No detection result for {strategy_name} on {symbol_norm} - rejecting plan {plan.plan_id}")
                            return False
                        
                        # Get confidence score from detection result
                        confidence = detection_result.get("confidence") or detection_result.get("strength") or 0.0
                        min_confidence = float(plan.conditions.get("min_confidence", 0.0))
                        
                        if confidence < min_confidence:
                            logger.debug(f"Confidence {confidence:.2f} < min_confidence {min_confidence:.2f} for {plan.plan_id}")
                            return False
                except Exception as e:
                    logger.warning(f"Error checking confidence threshold for {plan.plan_id}: {e}")
                    # Don't block execution if confidence check fails (graceful degradation)
            
            # Helper: normalize numpy array to list of dicts
            def _normalize_candles(candles):
                """Convert numpy array to list of dictionaries, handle None/empty"""
                if candles is None:
                    return []
                if hasattr(candles, '__len__'):
                    if len(candles) == 0:
                        return []
                    # Convert numpy structured array to list of dicts
                    if not isinstance(candles, list):
                        try:
                            import numpy as np
                            # Check if it's a numpy structured array
                            if isinstance(candles, np.ndarray) and hasattr(candles.dtype, 'names') and candles.dtype.names:
                                # Convert each structured array element to dict
                                result = []
                                for candle in candles:
                                    # Convert numpy structured array to dict
                                    candle_dict = {}
                                    # Use dtype.names from the array, not the element
                                    for name in candles.dtype.names:
                                        try:
                                            value = candle[name]
                                            # Convert numeric fields to float
                                            if name in ['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume']:
                                                candle_dict[name] = float(value)
                                            else:
                                                candle_dict[name] = value
                                        except (KeyError, IndexError, TypeError) as e:
                                            logger.debug(f"Error converting candle field {name}: {e}")
                                            continue
                                    if candle_dict:  # Only add if we got at least some fields
                                        result.append(candle_dict)
                                return result
                            else:
                                # Regular array - convert to list
                                return list(candles)
                        except (TypeError, ValueError, ImportError, AttributeError) as e:
                            logger.debug(f"Error normalizing candles: {e}")
                            return []
                return candles if isinstance(candles, list) else []
            
            # Helper: fetch recent candles for a timeframe
            def _get_recent_candles(symbol: str, timeframe: str = "M5", count: int = 50):
                tf_map = {
                    "M1": mt5.TIMEFRAME_M1,
                    "M5": mt5.TIMEFRAME_M5,
                    "M15": mt5.TIMEFRAME_M15,
                    "M30": mt5.TIMEFRAME_M30,
                    "H1": mt5.TIMEFRAME_H1,
                    "H4": mt5.TIMEFRAME_H4,
                    "D1": mt5.TIMEFRAME_D1,
                }
                tf = tf_map.get(timeframe.upper(), mt5.TIMEFRAME_M5)
                rates = mt5.copy_rates_from_pos(symbol, tf, 0, max(10, count))
                return _normalize_candles(rates)

            # Helper: Calculate ATR for normalization
            def _calculate_atr_simple(candles) -> Optional[float]:
                """Calculate simple ATR for structure break validation"""
                if len(candles) < 14:
                    return None
                try:
                    tr_values = []
                    for i in range(1, min(len(candles), 15)):
                        c = candles[i]
                        prev_c = candles[i-1]
                        h = c['high'] if isinstance(c, dict) else c.high
                        l = c['low'] if isinstance(c, dict) else c.low
                        prev_close = prev_c['close'] if isinstance(prev_c, dict) else prev_c.close
                        tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
                        tr_values.append(tr)
                    return sum(tr_values) / len(tr_values) if tr_values else None
                except Exception:
                    return None
            
            # Helper: Detect Break of Structure (BOS) - trend continuation
            def _detect_bos(candles, direction: str) -> bool:
                """
                Detect Break of Structure (BOS) - trend continuation signal.
                
                BOS Bull: Price breaks above last swing high (uptrend continuation)
                BOS Bear: Price breaks below last swing low (downtrend continuation)
                """
                candles = _normalize_candles(candles)
                if len(candles) < 10:
                    return False
                
                try:
                    highs = [c['high'] for c in candles]
                    lows = [c['low'] for c in candles]
                    closes = [c['close'] for c in candles]
                    
                    # Find recent swing highs/lows using a simple window
                    window = 3
                    swing_highs = []
                    swing_lows = []
                    for i in range(window, len(highs) - window):
                        if highs[i] == max(highs[i-window:i+window+1]):
                            swing_highs.append((i, highs[i]))
                        if lows[i] == min(lows[i-window:i+window+1]):
                            swing_lows.append((i, lows[i]))
                    
                    if direction == "bull":
                        if not swing_highs:
                            return False
                        last_sh_index, last_sh = swing_highs[-1]
                        # BOS: latest close breaks last swing high (trend continuation)
                        if closes[-1] > last_sh:
                            # Optional: ATR normalization to ensure significant break
                            atr = _calculate_atr_simple(candles)
                            if atr:
                                break_distance = closes[-1] - last_sh
                                if break_distance < atr * 0.2:  # Must be at least 0.2 ATR
                                    return False
                            return True
                        return False
                    else:  # bear
                        if not swing_lows:
                            return False
                        last_sl_index, last_sl = swing_lows[-1]
                        # BOS: latest close breaks last swing low (trend continuation)
                        if closes[-1] < last_sl:
                            # Optional: ATR normalization
                            atr = _calculate_atr_simple(candles)
                            if atr:
                                break_distance = last_sl - closes[-1]
                                if break_distance < atr * 0.2:
                                    return False
                            return True
                        return False
                except Exception as e:
                    logger.debug(f"Error detecting BOS: {e}")
                    return False
            
            # Helper: Detect Change of Character (CHOCH) - structure shift/reversal
            def _detect_choch(candles, direction: str) -> bool:
                """
                Detect Change of Character (CHOCH) - structure shift/reversal signal.
                
                CHOCH Bull: In downtrend, price breaks above previous swing high (structure shift to bullish)
                CHOCH Bear: In uptrend, price breaks below previous swing low (structure shift to bearish)
                
                Key difference from BOS:
                - CHOCH requires breaking the SECOND-TO-LAST swing point (previous structure)
                - This indicates a reversal, not continuation
                """
                candles = _normalize_candles(candles)
                if len(candles) < 20:  # Need more candles for CHOCH (need 2+ swing points)
                    return False
                
                try:
                    highs = [c['high'] for c in candles]
                    lows = [c['low'] for c in candles]
                    closes = [c['close'] for c in candles]
                    
                    # Find swing highs/lows
                    window = 3
                    swing_highs = []
                    swing_lows = []
                    for i in range(window, len(highs) - window):
                        if highs[i] == max(highs[i-window:i+window+1]):
                            swing_highs.append((i, highs[i]))
                        if lows[i] == min(lows[i-window:i+window+1]):
                            swing_lows.append((i, lows[i]))
                    
                    # Need at least 2 swing points for CHOCH detection
                    if len(swing_highs) < 2 or len(swing_lows) < 2:
                        return False
                    
                    # Calculate ATR for normalization
                    atr = _calculate_atr_simple(candles)
                    
                    if direction == "bull":
                        # CHOCH Bull: In downtrend, break above SECOND-TO-LAST swing high
                        # This indicates structure shift from bearish to bullish
                        if len(swing_highs) >= 2:
                            # Get second-to-last swing high (previous structure point)
                            prev_sh_index, prev_sh = swing_highs[-2]
                            current_close = closes[-1]
                            
                            # CHOCH: break above previous swing high (structure shift)
                            if current_close > prev_sh:
                                # ATR normalization: break should be significant
                                if atr:
                                    break_distance = current_close - prev_sh
                                    if break_distance < atr * 0.3:  # Must be at least 0.3 ATR
                                        return False
                                return True
                        return False
                    else:  # bear
                        # CHOCH Bear: In uptrend, break below SECOND-TO-LAST swing low
                        # This indicates structure shift from bullish to bearish
                        if len(swing_lows) >= 2:
                            # Get second-to-last swing low (previous structure point)
                            prev_sl_index, prev_sl = swing_lows[-2]
                            current_close = closes[-1]
                            
                            # CHOCH: break below previous swing low (structure shift)
                            if current_close < prev_sl:
                                # ATR normalization: break should be significant
                                if atr:
                                    break_distance = prev_sl - current_close
                                    if break_distance < atr * 0.3:  # Must be at least 0.3 ATR
                                        return False
                                return True
                        return False
                except Exception as e:
                    logger.debug(f"Error detecting CHOCH: {e}")
                    return False

            # Determine structure timeframe from conditions
            structure_tf = (
                plan.conditions.get("structure_tf")
                or plan.conditions.get("timeframe")
                or plan.conditions.get("tf")
                or "M5"
            )

            # Check price conditions
            if "price_above" in plan.conditions:
                if current_price <= plan.conditions["price_above"]:
                    return False
                    
            if "price_below" in plan.conditions:
                if current_price >= plan.conditions["price_below"]:
                    return False
                    
            # ============================================================================
            # Phase 2.3: R:R Ratio Validation & Spread/Slippage Cost Validation (CRITICAL)
            # ============================================================================
            # Validate R:R ratio (CRITICAL - should always check)
            sl_distance = abs(plan.entry_price - plan.stop_loss)
            tp_distance = abs(plan.take_profit - plan.entry_price)
            
            if sl_distance > 0:
                rr_ratio = tp_distance / sl_distance
                
                # Minimum R:R check (always enforce)
                min_rr = plan.conditions.get("min_rr_ratio", 1.5)  # Default 1.5:1 minimum
                if rr_ratio < min_rr:
                    logger.warning(
                        f"Plan {plan.plan_id}: R:R ratio too low: "
                        f"{rr_ratio:.2f}:1 < {min_rr:.2f}:1 (TP: {tp_distance:.2f}, SL: {sl_distance:.2f})"
                    )
                    return False
                
                # Check for backwards R:R (TP smaller than SL) - should never happen
                if rr_ratio < 1.0:
                    logger.error(
                        f"Plan {plan.plan_id}: INVALID R:R - TP smaller than SL: "
                        f"{rr_ratio:.2f}:1 (TP: {tp_distance:.2f}, SL: {sl_distance:.2f})"
                    )
                    return False
                
                # Validate spread/slippage costs don't erode R:R too much
                # Get current spread
                try:
                    spread = abs(current_ask - current_bid)
                    
                    # Estimate expected slippage (5% of SL distance for XAU, 3% for BTC)
                    expected_slippage_pct = 0.05 if "XAU" in symbol_norm else 0.03
                    expected_slippage = sl_distance * expected_slippage_pct
                    
                    # Total execution cost (spread + slippage)
                    total_cost = spread + expected_slippage
                    
                    # Cost should not exceed 20% of planned R:R
                    cost_rr_ratio = total_cost / tp_distance if tp_distance > 0 else 1.0
                    if cost_rr_ratio > 0.20:  # 20% threshold
                        logger.warning(
                            f"Plan {plan.plan_id}: Execution costs too high: "
                            f"{cost_rr_ratio:.1%} of R:R (spread: {spread:.2f}, slippage: {expected_slippage:.2f})"
                        )
                        return False
                except Exception as e:
                    logger.debug(f"Error checking spread/slippage costs for {plan.plan_id}: {e}")
                    # Continue if check fails (non-critical)
            
            # Validate stop distances using ATR (optional)
            # NOTE: ATR extraction requires API call - only validate if condition is set AND ATR is available
            if plan.conditions.get("atr_based_stops", False):
                try:
                    atr = self._extract_atr_from_cached_analysis(symbol_norm)
                    # If ATR is 0, skip validation (non-critical - ATR may not be available)
                    if atr > 0:
                        # BTC: Require SL >= 1.5 ATR, TP >= 3.0 ATR
                        # XAU: Require SL >= 1.2 ATR, TP >= 2.5 ATR
                        if "BTC" in symbol_norm:
                            min_sl_atr = 1.5
                            min_tp_atr = 3.0
                        else:  # XAU
                            min_sl_atr = 1.2
                            min_tp_atr = 2.5
                        
                        if sl_distance < atr * min_sl_atr:
                            logger.debug(
                                f"Plan {plan.plan_id}: Stop loss too tight: "
                                f"{sl_distance:.2f} < {atr * min_sl_atr:.2f} (ATR-based)"
                            )
                            return False
                        
                        if tp_distance < atr * min_tp_atr:
                            logger.debug(
                                f"Plan {plan.plan_id}: Take profit too tight: "
                                f"{tp_distance:.2f} < {atr * min_tp_atr:.2f} (ATR-based)"
                            )
                            return False
                        
                        # Check for immediate stop-out risk (SL too tight relative to ATR)
                        # If SL < 0.5x ATR, likely to stop out immediately
                        if sl_distance < atr * 0.5:
                            logger.warning(
                                f"Plan {plan.plan_id}: Stop loss too tight - likely immediate stop-out: "
                                f"{sl_distance:.2f} < {atr * 0.5:.2f} (0.5x ATR)"
                            )
                            return False
                except Exception as e:
                    logger.debug(f"Error validating ATR-based stops for {plan.plan_id}: {e}")
                    # Continue if check fails (non-critical)
            
            # ============================================================================
            # End Phase 2.3: R:R, Cost & ATR Validation
            # ============================================================================
                    
            if "price_near" in plan.conditions:
                target_price = plan.conditions["price_near"]
                
                # Phase 1: Use unified zone entry check
                # Get previous zone state from plan (if available)
                previous_in_zone = getattr(plan, 'zone_entry_tracked', None)
                if previous_in_zone is not None:
                    previous_in_zone = bool(previous_in_zone)
                
                # Check zone entry
                in_zone, level_index, entry_detected = self._check_tolerance_zone_entry(
                    plan, current_price, previous_in_zone
                )
                
                if not in_zone:
                    return False
                
                # Phase 2: Store triggered level index for execution (if multi-level plan)
                if level_index is not None:
                    plan._triggered_level_index = level_index
                    logger.debug(f"Phase 2: Level {level_index} triggered for plan {plan.plan_id}")
                
                # Phase 1: Track zone entry/exit
                now_utc = datetime.now(timezone.utc).isoformat()
                
                # If price is in zone and zone entry hasn't been tracked yet, track it
                # This handles both: (1) price moving into zone, and (2) plan created while price already in zone
                if in_zone and not getattr(plan, 'zone_entry_tracked', False):
                    plan.zone_entry_tracked = True
                    plan.zone_entry_time = now_utc if entry_detected else getattr(plan, 'created_at', now_utc)
                    plan.zone_exit_time = None
                    
                    # Update zone state in database (via write queue)
                    if self.db_write_queue:
                        try:
                            self.db_write_queue.queue_operation(
                                operation_type="update_zone_state",
                                plan_id=plan.plan_id,
                                data={
                                    "zone_entry_tracked": True,
                                    "zone_entry_time": now_utc,
                                    "zone_exit_time": None
                                },
                                priority=self.OperationPriority.MEDIUM,
                                wait_for_completion=False
                            )
                            logger.debug(f"Zone entry detected for plan {plan.plan_id} at {now_utc}")
                        except Exception as e:
                            logger.warning(f"Failed to queue zone state update: {e}")
                
                # Note: Zone exit tracking is handled separately if price exits zone
                # (This check happens in the monitoring loop, not here)
            
            # Check structure conditions (BOS/CHOCH - now separate functions)
            # Skip CHOCH/BOS checks for forex pairs (only BTC and XAU use these)
            if not self._is_forex_pair(symbol_norm):
                # Check CHOCH conditions (Change of Character - structure shift/reversal)
                if plan.conditions.get("choch_bull") or plan.conditions.get("choch_bear"):
                    candles = _get_recent_candles(symbol_norm, timeframe=structure_tf, count=100)
                    candles = _normalize_candles(candles)
                    if plan.conditions.get("choch_bull"):
                        if not _detect_choch(candles, "bull"):
                            logger.debug(f"CHOCH Bull condition not met for {plan.plan_id}")
                            return False
                    if plan.conditions.get("choch_bear"):
                        if not _detect_choch(candles, "bear"):
                            logger.debug(f"CHOCH Bear condition not met for {plan.plan_id}")
                            return False
                
                # Check BOS conditions (Break of Structure - trend continuation)
                if plan.conditions.get("bos_bull") or plan.conditions.get("bos_bear"):
                    candles = _get_recent_candles(symbol_norm, timeframe=structure_tf, count=100)
                    candles = _normalize_candles(candles)
                    if plan.conditions.get("bos_bull"):
                        if not _detect_bos(candles, "bull"):
                            logger.debug(f"BOS Bull condition not met for {plan.plan_id}")
                            return False
                    if plan.conditions.get("bos_bear"):
                        if not _detect_bos(candles, "bear"):
                            logger.debug(f"BOS Bear condition not met for {plan.plan_id}")
                            return False
            else:
                # For forex pairs, skip CHOCH/BOS checks (these conditions are not applicable)
                if plan.conditions.get("choch_bull") or plan.conditions.get("choch_bear") or plan.conditions.get("bos_bull") or plan.conditions.get("bos_bear"):
                    logger.debug(f"Skipping CHOCH/BOS check for forex pair {symbol_norm}")
                    # Return False to prevent execution if plan requires CHOCH/BOS for forex
                    return False
            
            # ============================================================================
            # Phase III: Multi-Timeframe Confluence Condition Checks
            # ============================================================================
            # Check multi-timeframe conditions (choch_bull_m5, choch_bull_m15, bos_bear_m15, etc.)
            if not self._is_forex_pair(symbol_norm):
                try:
                    from infra.multi_timeframe_data_fetcher import MultiTimeframeDataFetcher
                    
                    # Initialize fetcher (singleton pattern)
                    if not hasattr(self, '_mtf_data_fetcher'):
                        self._mtf_data_fetcher = MultiTimeframeDataFetcher(cache_ttl_seconds=60)
                    
                    mtf_fetcher = self._mtf_data_fetcher
                    
                    # Collect required timeframes from conditions
                    required_tfs = []
                    if plan.conditions.get("choch_bull_m5") or plan.conditions.get("choch_bear_m5"):
                        required_tfs.append("M5")
                    if plan.conditions.get("choch_bull_m15") or plan.conditions.get("choch_bear_m15"):
                        required_tfs.append("M15")
                    if plan.conditions.get("bos_bull_m15") or plan.conditions.get("bos_bear_m15"):
                        required_tfs.append("M15")
                    if plan.conditions.get("fvg_bull_m30") or plan.conditions.get("fvg_bear_m30"):
                        required_tfs.append("M30")
                    
                    # Fetch multi-TF data if needed
                    if required_tfs:
                        # Remove duplicates
                        required_tfs = list(set(required_tfs))
                        
                        tf_data = mtf_fetcher.fetch_multi_timeframe_data(
                            symbol_norm,
                            required_tfs,
                            self.mt5_service,
                            count=100
                        )
                        
                        if not tf_data:
                            logger.debug(f"Plan {plan.plan_id}: Multi-TF data unavailable")
                            return False
                        
                        # Validate alignment
                        if not mtf_fetcher.validate_timeframe_alignment(tf_data, required_tfs):
                            logger.debug(f"Plan {plan.plan_id}: Multi-TF alignment failed")
                            return False
                        
                        # Check M5 CHOCH conditions
                        if plan.conditions.get("choch_bull_m5") or plan.conditions.get("choch_bear_m5"):
                            if "M5" in tf_data:
                                m5_candles = tf_data["M5"]
                                m5_candles = _normalize_candles(m5_candles)
                                if plan.conditions.get("choch_bull_m5"):
                                    if not _detect_choch(m5_candles, "bull"):
                                        logger.debug(f"Plan {plan.plan_id}: CHOCH Bull M5 not detected")
                                        return False
                                if plan.conditions.get("choch_bear_m5"):
                                    if not _detect_choch(m5_candles, "bear"):
                                        logger.debug(f"Plan {plan.plan_id}: CHOCH Bear M5 not detected")
                                        return False
                            else:
                                logger.debug(f"Plan {plan.plan_id}: M5 data unavailable")
                                return False
                        
                        # Check M15 CHOCH conditions
                        if plan.conditions.get("choch_bull_m15") or plan.conditions.get("choch_bear_m15"):
                            if "M15" in tf_data:
                                m15_candles = tf_data["M15"]
                                m15_candles = _normalize_candles(m15_candles)
                                if plan.conditions.get("choch_bull_m15"):
                                    if not _detect_choch(m15_candles, "bull"):
                                        logger.debug(f"Plan {plan.plan_id}: CHOCH Bull M15 not detected")
                                        return False
                                if plan.conditions.get("choch_bear_m15"):
                                    if not _detect_choch(m15_candles, "bear"):
                                        logger.debug(f"Plan {plan.plan_id}: CHOCH Bear M15 not detected")
                                        return False
                            else:
                                logger.debug(f"Plan {plan.plan_id}: M15 data unavailable")
                                return False
                        
                        # Check M15 BOS conditions
                        if plan.conditions.get("bos_bull_m15") or plan.conditions.get("bos_bear_m15"):
                            if "M15" in tf_data:
                                m15_candles = tf_data["M15"]
                                m15_candles = _normalize_candles(m15_candles)
                                if plan.conditions.get("bos_bull_m15"):
                                    if not _detect_bos(m15_candles, "bull"):
                                        logger.debug(f"Plan {plan.plan_id}: BOS Bull M15 not detected")
                                        return False
                                if plan.conditions.get("bos_bear_m15"):
                                    if not _detect_bos(m15_candles, "bear"):
                                        logger.debug(f"Plan {plan.plan_id}: BOS Bear M15 not detected")
                                        return False
                            else:
                                logger.debug(f"Plan {plan.plan_id}: M15 data unavailable")
                                return False
                        
                        # Check M30 FVG conditions
                        if plan.conditions.get("fvg_bull_m30") or plan.conditions.get("fvg_bear_m30"):
                            if "M30" in tf_data:
                                from infra.detection_systems import DetectionSystemManager
                                detection_manager = DetectionSystemManager()
                                fvg_result = detection_manager.get_fvg(symbol_norm, timeframe="M30")
                                
                                if not fvg_result:
                                    logger.debug(f"Plan {plan.plan_id}: FVG M30 not detected")
                                    return False
                                
                                if plan.conditions.get("fvg_bull_m30"):
                                    fvg_bull = fvg_result.get("fvg_bull")
                                    if not fvg_bull or not isinstance(fvg_bull, dict):
                                        logger.debug(f"Plan {plan.plan_id}: FVG Bull M30 not detected")
                                        return False
                                
                                if plan.conditions.get("fvg_bear_m30"):
                                    fvg_bear = fvg_result.get("fvg_bear")
                                    if not fvg_bear or not isinstance(fvg_bear, dict):
                                        logger.debug(f"Plan {plan.plan_id}: FVG Bear M30 not detected")
                                        return False
                            else:
                                logger.debug(f"Plan {plan.plan_id}: M30 data unavailable")
                                return False
                    
                    # Check M1 pullback confirmation (requires structure break first)
                    if plan.conditions.get("m1_pullback_confirmed"):
                        if not self.m1_analyzer or not self.m1_data_fetcher:
                            logger.debug(f"Plan {plan.plan_id}: M1 pullback requires M1 components")
                            return False
                        
                        # First check if structure break occurred (BOS on M15)
                        if not plan.conditions.get("bos_bull_m15") and not plan.conditions.get("bos_bear_m15"):
                            logger.debug(f"Plan {plan.plan_id}: M1 pullback requires BOS on M15 first")
                            return False
                        
                        # Get M1 candles
                        m1_candles = self.m1_data_fetcher.fetch_m1_data(symbol_norm, count=50)
                        if not m1_candles or len(m1_candles) < 20:
                            logger.debug(f"Plan {plan.plan_id}: Insufficient M1 data for pullback check")
                            return False
                        
                        # Detect pullback: price retraces 30-50% of structure break move within 10-20 M1 bars, then bounces
                        # Simplified: check if price retraced and then reversed
                        m1_candles_normalized = _normalize_candles(m1_candles)
                        if len(m1_candles_normalized) < 20:
                            logger.debug(f"Plan {plan.plan_id}: Insufficient M1 candles for pullback")
                            return False
                        
                        # Get structure break direction
                        bos_direction = "bull" if plan.conditions.get("bos_bull_m15") else "bear"
                        
                        # Calculate pullback: look for retracement then bounce
                        # For bull BOS: price should have pulled back (lower lows) then bounced (higher lows)
                        # For bear BOS: price should have pulled back (higher highs) then bounced (lower highs)
                        recent_candles = m1_candles_normalized[:20]
                        closes = [c.get('close') if isinstance(c, dict) else c.close for c in recent_candles]
                        highs = [c.get('high') if isinstance(c, dict) else c.high for c in recent_candles]
                        lows = [c.get('low') if isinstance(c, dict) else c.low for c in recent_candles]
                        
                        pullback_confirmed = False
                        if bos_direction == "bull":
                            # Bull BOS: look for pullback (lower low) then bounce (higher low)
                            min_low = min(lows)
                            min_low_idx = lows.index(min_low)
                            if min_low_idx < len(lows) - 5:  # Pullback happened
                                # Check if price bounced (higher lows after pullback)
                                post_pullback_lows = lows[min_low_idx:]
                                if len(post_pullback_lows) > 3:
                                    pullback_confirmed = min(post_pullback_lows[1:]) > min_low * 1.001  # 0.1% bounce
                        else:
                            # Bear BOS: look for pullback (higher high) then bounce (lower high)
                            max_high = max(highs)
                            max_high_idx = highs.index(max_high)
                            if max_high_idx < len(highs) - 5:  # Pullback happened
                                # Check if price bounced (lower highs after pullback)
                                post_pullback_highs = highs[max_high_idx:]
                                if len(post_pullback_highs) > 3:
                                    pullback_confirmed = max(post_pullback_highs[1:]) < max_high * 0.999  # 0.1% bounce
                        
                        if not pullback_confirmed:
                            logger.debug(f"Plan {plan.plan_id}: M1 pullback not confirmed")
                            return False
                    
                except ImportError:
                    # Multi-TF fetcher not available
                    if any([
                        plan.conditions.get("choch_bull_m5"), plan.conditions.get("choch_bear_m5"),
                        plan.conditions.get("choch_bull_m15"), plan.conditions.get("choch_bear_m15"),
                        plan.conditions.get("bos_bull_m15"), plan.conditions.get("bos_bear_m15"),
                        plan.conditions.get("fvg_bull_m30"), plan.conditions.get("fvg_bear_m30"),
                        plan.conditions.get("m1_pullback_confirmed")
                    ]):
                        logger.debug(f"Plan {plan.plan_id}: Multi-TF fetcher not available")
                        return False
                except Exception as e:
                    logger.error(f"Error checking multi-timeframe conditions for {plan.plan_id}: {e}", exc_info=True)
                    return False
            
            # Check rejection wick conditions
            if plan.conditions.get("rejection_wick"):
                candles = _get_recent_candles(symbol_norm, timeframe=structure_tf, count=3)
                candles = _normalize_candles(candles)
                if not candles:
                    return False
                c = candles[-1]
                # All candles should be dicts after normalization
                o = c['open']
                h = c['high']
                l = c['low']
                cl = c['close']
                body = abs(cl - o)
                upper_wick = max(0.0, h - max(cl, o))
                lower_wick = max(0.0, min(cl, o) - l)
                wick_ratio = max(upper_wick, lower_wick) / (body if body > 1e-9 else 1e-9)
                min_wick_ratio = plan.conditions.get("min_wick_ratio", 2.0)
                near_entry_ok = True
                if "price_near" in plan.conditions:
                    tol = plan.conditions.get("tolerance")
                    if tol is None:
                        from infra.tolerance_helper import get_price_tolerance
                        tol = get_price_tolerance(plan.symbol)
                    near_entry_ok = abs(current_price - plan.entry_price) <= tol
                if wick_ratio < min_wick_ratio or not near_entry_ok:
                    return False
            
            # Check order block conditions (M1-M5 validated)
            if plan.conditions.get("order_block"):
                if not self.m1_analyzer or not self.m1_data_fetcher:
                    logger.warning(f"Order block plan {plan.plan_id} requires M1 components (not available)")
                    return False
                
                try:
                    # Fetch M1 data
                    m1_candles = self.m1_data_fetcher.fetch_m1_data(symbol_norm, count=200)
                    if not m1_candles or len(m1_candles) < 50:
                        logger.debug(f"Insufficient M1 data for order block check on {symbol_norm}")
                        return False
                    
                    # Get M5 candles for HTF validation
                    m5_candles = _get_recent_candles(symbol_norm, timeframe="M5", count=100)
                    m5_candles = _normalize_candles(m5_candles)
                    
                    # Analyze M1 microstructure
                    m1_analysis = self.m1_analyzer.analyze_microstructure(
                        symbol=symbol_norm,
                        candles=m1_candles,
                        current_price=current_price,
                        higher_timeframe_data={"M5": m5_candles} if m5_candles else None
                    )
                    
                    if not m1_analysis or not m1_analysis.get('available'):
                        logger.debug(f"M1 analysis unavailable for order block check on {symbol_norm}")
                        return False
                    
                    # Get order blocks from analysis
                    order_blocks = m1_analysis.get('order_blocks', [])
                    if not order_blocks:
                        logger.debug(f"No order blocks detected for {symbol_norm}")
                        return False
                    
                    # Filter by direction if specified
                    ob_type = plan.conditions.get("order_block_type", "auto").lower()
                    expected_direction = None
                    if ob_type == "bull":
                        expected_direction = "BULLISH"
                    elif ob_type == "bear":
                        expected_direction = "BEARISH"
                    elif ob_type == "auto":
                        # Auto-detect: match plan direction
                        expected_direction = "BULLISH" if plan.direction == "BUY" else "BEARISH"
                    
                    # Find matching order blocks
                    matching_obs = []
                    for ob in order_blocks:
                        ob_direction = ob.get('type', '').upper()
                        if expected_direction and ob_direction != expected_direction:
                            continue
                        matching_obs.append(ob)
                    
                    if not matching_obs:
                        logger.debug(f"No matching order blocks found for {symbol_norm} (expected: {expected_direction})")
                        return False
                    
                    # Validate the most recent matching order block using 10-parameter checklist
                    # Import alert monitor validation logic (reuse the same validation)
                    from infra.alert_monitor import AlertMonitor
                    from infra.custom_alerts import CustomAlertManager
                    
                    # Create a temporary alert monitor instance for validation
                    alert_monitor = AlertMonitor(
                        CustomAlertManager(),
                        self.mt5_service,
                        m1_data_fetcher=self.m1_data_fetcher,
                        m1_analyzer=self.m1_analyzer,
                        session_manager=getattr(self, 'session_manager', None)
                    )
                    
                    # Get M5 data dict format
                    m5_data = None
                    if m5_candles:
                        m5_data = {
                            "highs": [c['high'] if isinstance(c, dict) else c.high for c in m5_candles[-20:]],
                            "lows": [c['low'] if isinstance(c, dict) else c.low for c in m5_candles[-20:]],
                            "closes": [c['close'] if isinstance(c, dict) else c.close for c in m5_candles[-20:]],
                            "opens": [c['open'] if isinstance(c, dict) else c.open for c in m5_candles[-20:]]
                        }
                    
                    # Validate the most recent matching OB
                    latest_ob = matching_obs[-1]
                    validation_result = alert_monitor._validate_order_block(
                        ob=latest_ob,
                        m1_candles=m1_candles,
                        m5_candles=m5_candles,
                        m1_analysis=m1_analysis,
                        m5_data=m5_data,
                        symbol_norm=symbol_norm,
                        current_price=current_price
                    )
                    
                    if not validation_result or not validation_result.get('valid'):
                        logger.debug(f"Order block validation failed for {symbol_norm}")
                        return False
                    
                    # Check minimum validation score
                    min_score = plan.conditions.get("min_validation_score", 60)
                    validation_score = validation_result.get('score', 0)
                    
                    # ============================================================================
                    # ISSUE 4: Volume Imbalance Check for BTCUSD OB Plans
                    # ============================================================================
                    # Validate order flow (delta/CVD) before executing OB plans for BTCUSD
                    if symbol_norm.upper().startswith('BTC'):
                        if self.micro_scalp_engine and hasattr(self.micro_scalp_engine, 'btc_order_flow'):
                            try:
                                # Pre-Phase 0 Fix: Use get_metrics() instead of non-existent methods
                                metrics = self._get_btc_order_flow_metrics(plan)
                                if not metrics:
                                    logger.debug(f"Plan {plan.plan_id}: Could not get order flow metrics for OB validation")
                                    return False
                                
                                # Extract delta and CVD trend from metrics
                                delta = metrics.delta_volume
                                cvd_trend = {
                                    'trend': 'rising' if metrics.cvd_slope > 0 else 'falling' if metrics.cvd_slope < 0 else 'flat',
                                    'slope': metrics.cvd_slope
                                }
                                
                                # Validate direction based on order flow
                                if plan.direction == "BUY":
                                    if delta is not None and delta < 0.25:  # Not enough buying pressure
                                        logger.debug(
                                            f"Plan {plan.plan_id}: OB BUY blocked - Delta {delta:.2f} < 0.25 (bearish imbalance)"
                                        )
                                        return False
                                    if cvd_trend and cvd_trend.get('trend') != 'rising':
                                        logger.debug(
                                            f"Plan {plan.plan_id}: OB BUY blocked - CVD not rising (no accumulation)"
                                        )
                                        return False
                                else:  # SELL
                                    if delta is not None and delta > -0.25:  # Not enough selling pressure
                                        logger.debug(
                                            f"Plan {plan.plan_id}: OB SELL blocked - Delta {delta:.2f} > -0.25 (bullish imbalance)"
                                        )
                                        return False
                                    if cvd_trend and cvd_trend.get('trend') != 'falling':
                                        logger.debug(
                                            f"Plan {plan.plan_id}: OB SELL blocked - CVD not falling (no distribution)"
                                        )
                                        return False
                                
                                # Check absorption zones
                                try:
                                    # Pre-Phase 0 Fix: Use metrics.absorption_zones instead of get_absorption_zones()
                                    absorption_zones = metrics.absorption_zones or []
                                    entry_price = plan.entry_price
                                    if absorption_zones:
                                        for zone in absorption_zones:
                                            zone_high = zone.get('high') or zone.get('upper')
                                            zone_low = zone.get('low') or zone.get('lower')
                                            if zone_high and zone_low:
                                                if zone_high >= entry_price >= zone_low:
                                                    logger.debug(
                                                        f"Plan {plan.plan_id}: OB blocked - Entry price {entry_price:.2f} in absorption zone "
                                                        f"({zone_low:.2f} - {zone_high:.2f})"
                                                    )
                                                    return False
                                except Exception as e:
                                    logger.debug(f"Error checking absorption zones for {plan.plan_id}: {e}")
                                    # Continue if absorption zone check fails
                            except Exception as e:
                                logger.debug(f"Error checking order flow metrics for {plan.plan_id}: {e}")
                                # Continue if order flow check fails (order flow may not be available)
                    if validation_score < min_score:
                        logger.debug(f"Order block validation score too low: {validation_score} < {min_score}")
                        return False
                    
                    # Check if OB zone is near entry price (if price_near condition exists)
                    if "price_near" in plan.conditions:
                        ob_range = latest_ob.get('price_range', [])
                        if ob_range and len(ob_range) >= 2:
                            ob_low = ob_range[0]
                            ob_high = ob_range[1]
                            tolerance = plan.conditions.get("tolerance")
                            if tolerance is None:
                                from infra.tolerance_helper import get_price_tolerance
                                tolerance = get_price_tolerance(plan.symbol)
                            
                            # Check if entry price is within OB zone or near it
                            entry_in_zone = ob_low <= plan.entry_price <= ob_high
                            entry_near_zone = (abs(plan.entry_price - ob_low) <= tolerance) or (abs(plan.entry_price - ob_high) <= tolerance)
                            
                            if not (entry_in_zone or entry_near_zone):
                                logger.debug(f"Entry price {plan.entry_price} not near OB zone [{ob_low}, {ob_high}]")
                                return False
                    
                    logger.info(f"Order block validated for {symbol_norm}: score {validation_score}/{100}, type {latest_ob.get('type')}")
                    # Order block condition met
                    
                except Exception as e:
                    logger.error(f"Error checking order block condition for {symbol_norm}: {e}", exc_info=True)
                    return False
            
            # ============================================================================
            # Phase 1.1: Order Flow Condition Support for ALL BTC Plans (Not Just Order Block)
            # ============================================================================
            # Check order flow conditions for ALL BTC plans (not just order_block)
            # This allows delta_positive, cvd_rising, etc. to be used as conditions in any BTC plan
            if symbol_norm.upper().startswith('BTC'):
                # Check if plan has order flow conditions
                if plan.conditions.get("delta_positive") or plan.conditions.get("delta_negative"):
                    # Pre-Phase 0 Fix: Use get_metrics() instead of get_delta_volume()
                    metrics = self._get_btc_order_flow_metrics(plan)
                    if not metrics:
                        logger.debug(f"Plan {plan.plan_id}: Could not get order flow metrics")
                        return False
                    
                    # Extract delta from metrics
                    delta = metrics.delta_volume
                    
                    if plan.conditions.get("delta_positive"):
                        if delta is None or delta <= 0:
                            logger.debug(f"Plan {plan.plan_id}: delta_positive condition not met (delta: {delta})")
                            return False
                    
                    if plan.conditions.get("delta_negative"):
                        if delta is None or delta >= 0:
                            logger.debug(f"Plan {plan.plan_id}: delta_negative condition not met (delta: {delta})")
                            return False
                
                # Check CVD conditions
                if plan.conditions.get("cvd_rising") or plan.conditions.get("cvd_falling"):
                    # Pre-Phase 0 Fix: Use get_metrics() instead of get_cvd_trend()
                    # Reuse metrics if already fetched above, or fetch new
                    if 'metrics' not in locals():
                        metrics = self._get_btc_order_flow_metrics(plan)
                        if not metrics:
                            logger.debug(f"Plan {plan.plan_id}: Could not get CVD metrics")
                            return False
                    
                    # Calculate CVD trend from slope
                    cvd_trend = {
                        'trend': 'rising' if metrics.cvd_slope > 0 else 'falling' if metrics.cvd_slope < 0 else 'flat',
                        'slope': metrics.cvd_slope
                    }
                    
                    if plan.conditions.get("cvd_rising"):
                        if cvd_trend.get('trend') != 'rising':
                            logger.debug(f"Plan {plan.plan_id}: cvd_rising condition not met")
                            return False
                    
                    if plan.conditions.get("cvd_falling"):
                        if cvd_trend.get('trend') != 'falling':
                            logger.debug(f"Plan {plan.plan_id}: cvd_falling condition not met")
                            return False
                
                # Check CVD divergence conditions (accept multiple name variations for compatibility)
                # Support: cvd_div_bear, cvd_div_bull, cvd_divergence_bear, cvd_divergence_bull
                cvd_div_conditions = {
                    "cvd_div_bear": "bearish",
                    "cvd_div_bull": "bullish",
                    "cvd_divergence_bear": "bearish",
                    "cvd_divergence_bull": "bullish",
                    "cvd_divergence_bearish": "bearish",
                    "cvd_divergence_bullish": "bullish"
                }
                
                for cond_name, expected_type in cvd_div_conditions.items():
                    if plan.conditions.get(cond_name):
                        if self.micro_scalp_engine and hasattr(self.micro_scalp_engine, 'btc_order_flow'):
                            try:
                                btc_flow = self.micro_scalp_engine.btc_order_flow
                                # Get metrics which includes CVD divergence
                                metrics = btc_flow.get_metrics("BTCUSDT", window_seconds=300)
                                
                                if metrics:
                                    div_type = metrics.cvd_divergence_type
                                    div_strength = metrics.cvd_divergence_strength
                                    
                                    if not div_type or div_type != expected_type or div_strength <= 0:
                                        logger.debug(
                                            f"Plan {plan.plan_id}: {cond_name} condition not met "
                                            f"(divergence: {div_type}, strength: {div_strength:.1%})"
                                        )
                                        return False
                                else:
                                    logger.debug(f"Plan {plan.plan_id}: Could not get CVD divergence metrics")
                                    return False
                            except Exception as e:
                                logger.debug(f"Error checking CVD divergence for {plan.plan_id}: {e}")
                                return False
                
                # Check delta divergence conditions (accept multiple name variations for compatibility)
                # Support: delta_divergence_bull, delta_divergence_bear
                # Note: Delta divergence detection requires price vs delta comparison
                # For now, use delta_positive/negative as a proxy (can be enhanced with actual divergence calculation)
                if plan.conditions.get("delta_divergence_bull") or plan.conditions.get("delta_divergence_bullish"):
                    # Bullish delta divergence typically means positive delta with price divergence
                    # For now, check delta_positive as proxy (if not already checked above)
                    if not plan.conditions.get("delta_positive"):
                        # Pre-Phase 0 Fix: Use get_metrics() instead of get_delta_volume()
                        metrics = self._get_btc_order_flow_metrics(plan)
                        if not metrics:
                            logger.debug(f"Plan {plan.plan_id}: Could not get order flow metrics for delta divergence")
                            return False
                        
                        delta = metrics.delta_volume
                        if delta is None or delta <= 0:
                            logger.debug(f"Plan {plan.plan_id}: delta_divergence_bull condition not met (delta: {delta})")
                            return False
                
                if plan.conditions.get("delta_divergence_bear") or plan.conditions.get("delta_divergence_bearish"):
                    # Bearish delta divergence typically means negative delta with price divergence
                    # For now, check delta_negative as proxy (if not already checked above)
                    if not plan.conditions.get("delta_negative"):
                        # Pre-Phase 0 Fix: Use get_metrics() instead of get_delta_volume()
                        metrics = self._get_btc_order_flow_metrics(plan)
                        if not metrics:
                            logger.debug(f"Plan {plan.plan_id}: Could not get order flow metrics for delta divergence")
                            return False
                        
                        delta = metrics.delta_volume
                        if delta is None or delta >= 0:
                            logger.debug(f"Plan {plan.plan_id}: delta_divergence_bear condition not met (delta: {delta})")
                            return False
                
                # Check absorption zones for ALL BTC plans (not just order_block)
                # Accept both "avoid_absorption_zones" and "absorption_zone_detected" for compatibility
                check_absorption = (
                    plan.conditions.get("avoid_absorption_zones", False) or
                    plan.conditions.get("absorption_zone_detected", False)
                )
                
                if check_absorption:
                    if self.micro_scalp_engine and hasattr(self.micro_scalp_engine, 'btc_order_flow'):
                        try:
                            btc_flow = self.micro_scalp_engine.btc_order_flow
                            # Get metrics which includes absorption zones
                            metrics = btc_flow.get_metrics("BTCUSDT", window_seconds=300)
                            entry_price = plan.entry_price
                            
                            if metrics and metrics.absorption_zones:
                                for zone in metrics.absorption_zones:
                                    # Absorption zones can have different structures
                                    zone_price = zone.get('price_level') or zone.get('price')
                                    zone_high = zone.get('high') or zone.get('upper')
                                    zone_low = zone.get('low') or zone.get('lower')
                                    
                                    # Check if entry price is in zone
                                    if zone_price:
                                        # Single price level - check if entry is near (within tolerance)
                                        tolerance = plan.conditions.get("tolerance", 10)
                                        if abs(entry_price - zone_price) <= tolerance:
                                            logger.debug(
                                                f"Plan {plan.plan_id}: Entry price {entry_price:.2f} near absorption zone "
                                                f"at {zone_price:.2f}"
                                            )
                                            return False
                                    elif zone_high and zone_low:
                                        # Price range - check if entry is in range
                                        if zone_low <= entry_price <= zone_high:
                                            logger.debug(
                                                f"Plan {plan.plan_id}: Entry price {entry_price:.2f} in absorption zone "
                                                f"({zone_low:.2f} - {zone_high:.2f})"
                                            )
                                            return False
                        except Exception as e:
                            logger.debug(f"Error checking absorption zones for {plan.plan_id}: {e}")
                            # Continue if check fails (non-critical)
            
            # ============================================================================
            # Phase 4.5: New SMC Strategy Condition Checks
            # ============================================================================
            
            # NEW: Validate strategy-specific conditions match strategy_type (warning only, non-blocking)
            # Accept both strategy_type and plan_type for compatibility
            strategy_type = plan.conditions.get("strategy_type") or plan.conditions.get("plan_type")
            
            if strategy_type == "breaker_block":
                if "breaker_block" not in plan.conditions or not plan.conditions.get("breaker_block"):
                    logger.warning(
                        f"Plan {plan.plan_id} has strategy_type='breaker_block' but missing breaker_block: true condition. "
                        f"Plan will NOT check for breaker blocks - only price conditions will be checked."
                    )
                # Warn if incorrect detection flags are present
                if "ob_broken" in plan.conditions:
                    logger.warning(
                        f"Plan {plan.plan_id} has 'ob_broken' in conditions (should NOT be included - checked dynamically by system)"
                    )
                if "price_retesting_breaker" in plan.conditions:
                    logger.warning(
                        f"Plan {plan.plan_id} has 'price_retesting_breaker' in conditions (should NOT be included - checked dynamically by system)"
                    )
            
            elif strategy_type == "order_block_rejection":
                if "order_block" not in plan.conditions or not plan.conditions.get("order_block"):
                    logger.warning(
                        f"Plan {plan.plan_id} has strategy_type='order_block_rejection' but missing order_block: true condition. "
                        f"Plan will NOT check for order blocks - only price conditions will be checked."
                    )
            
            elif strategy_type == "liquidity_sweep_reversal":
                if "liquidity_sweep" not in plan.conditions or not plan.conditions.get("liquidity_sweep"):
                    logger.warning(
                        f"Plan {plan.plan_id} has strategy_type='liquidity_sweep_reversal' but missing liquidity_sweep: true condition. "
                        f"Plan will NOT detect liquidity sweeps - only price conditions will be checked."
                    )
                if "price_below" not in plan.conditions and "price_above" not in plan.conditions:
                    logger.warning(
                        f"Plan {plan.plan_id} has liquidity_sweep but missing price_below/price_above. "
                        f"Sweep detection may not work correctly."
                    )
            
            # ============================================================================
            # Phase III: Cross-Market Correlation Condition Checks
            # ============================================================================
            # Check correlation conditions (DXY, ETH/BTC, NASDAQ, BTC support)
            if self.correlation_calculator:
                try:
                    # Phase 5: Correlation Asset Validation and Routing
                    # Validate correlation_asset parameter and ensure proper routing
                    correlation_asset = plan.conditions.get("correlation_asset", "").upper() if plan.conditions.get("correlation_asset") else None
                    
                    if correlation_asset:
                        # Validate correlation_asset value and ensure corresponding condition is present
                        if correlation_asset in ["SPX", "SP500", "SP500C"]:
                            # SPX correlation requires spx_up_pct condition
                            if plan.conditions.get("spx_up_pct") is None:
                                logger.debug(f"Plan {plan.plan_id}: correlation_asset='{correlation_asset}' specified but spx_up_pct condition is missing")
                                return False
                        elif correlation_asset in ["US10Y", "TNX", "US10YC"]:
                            # US10Y correlation requires yield_drop condition
                            if plan.conditions.get("yield_drop") is None:
                                logger.debug(f"Plan {plan.plan_id}: correlation_asset='{correlation_asset}' specified but yield_drop condition is missing")
                                return False
                        elif correlation_asset in ["DXY", "DX"]:
                            # DXY correlation - validate dxy_change_pct or correlation_divergence is present
                            if plan.conditions.get("dxy_change_pct") is None and not plan.conditions.get("correlation_divergence"):
                                logger.debug(f"Plan {plan.plan_id}: correlation_asset='{correlation_asset}' specified but no DXY condition (dxy_change_pct or correlation_divergence) is present")
                                return False
                        else:
                            logger.debug(f"Plan {plan.plan_id}: Unknown correlation_asset='{correlation_asset}'. Supported: SPX, SP500, US10Y, TNX, DXY")
                            return False
                    # DXY Inverse Flow Plan conditions
                    if plan.conditions.get("dxy_change_pct") is not None:
                        dxy_change_threshold = plan.conditions.get("dxy_change_pct")
                        # Get cached or calculate DXY change
                        cache_key = f"dxy_change_{plan.symbol}"
                        dxy_change = self._get_cached_correlation(cache_key)
                        if dxy_change is None:
                            # Calculate DXY change (async call in sync context)
                            import asyncio
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                            
                            dxy_change = loop.run_until_complete(
                                self.correlation_calculator.calculate_dxy_change_pct(window_minutes=60)
                            )
                            if dxy_change is not None:
                                self._cache_correlation(cache_key, dxy_change)
                        
                        if dxy_change is None:
                            logger.debug(f"Plan {plan.plan_id}: DXY change data unavailable")
                            return False
                        
                        if dxy_change < dxy_change_threshold:
                            logger.debug(f"Plan {plan.plan_id}: DXY change {dxy_change:.2f}% < threshold {dxy_change_threshold:.2f}%")
                            return False
                    
                    # DXY stall detection
                    if plan.conditions.get("dxy_stall_detected"):
                        cache_key = f"dxy_stall_{plan.symbol}"
                        dxy_stall = self._get_cached_correlation(cache_key)
                        if dxy_stall is None:
                            import asyncio
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                            
                            dxy_stall = loop.run_until_complete(
                                self.correlation_calculator.detect_dxy_stall(window_minutes=60)
                            )
                            self._cache_correlation(cache_key, dxy_stall)
                        
                        if not dxy_stall:
                            logger.debug(f"Plan {plan.plan_id}: DXY stall not detected")
                            return False
                    
                    # SPX percentage change condition
                    if plan.conditions.get("spx_up_pct") is not None:
                        # Check if correlation_asset is SPX or SP500
                        correlation_asset = plan.conditions.get("correlation_asset", "").upper()
                        if correlation_asset not in ["SPX", "SP500", "SP500C"]:
                            logger.debug(f"Plan {plan.plan_id}: spx_up_pct condition requires correlation_asset='SPX' or 'SP500'")
                            return False
                        
                        spx_change_threshold = plan.conditions.get("spx_up_pct")
                        spx_change_window = plan.conditions.get("spx_change_window", 60)  # Default 60 minutes
                        
                        # Get cached or calculate SPX change
                        cache_key = f"spx_change_{plan.symbol}_{spx_change_window}"
                        spx_change = self._get_cached_correlation(cache_key)
                        if spx_change is None:
                            # Calculate SPX change (async call in sync context)
                            import asyncio
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                            
                            spx_change = loop.run_until_complete(
                                self.correlation_calculator.calculate_spx_change_pct(window_minutes=spx_change_window)
                            )
                            if spx_change is not None:
                                self._cache_correlation(cache_key, spx_change)
                        
                        if spx_change is None:
                            logger.debug(f"Plan {plan.plan_id}: SPX change data unavailable")
                            return False
                        
                        if spx_change < spx_change_threshold:
                            logger.debug(f"Plan {plan.plan_id}: SPX change {spx_change:.2f}% < threshold {spx_change_threshold:.2f}%")
                            return False
                        
                        logger.info(f"Plan {plan.plan_id}: SPX change condition met: {spx_change:.2f}% >= {spx_change_threshold:.2f}%")
                    
                    # US10Y yield drop condition
                    if plan.conditions.get("yield_drop") is not None:
                        # Check if correlation_asset is US10Y or TNX
                        correlation_asset = plan.conditions.get("correlation_asset", "").upper()
                        if correlation_asset not in ["US10Y", "TNX", "US10YC"]:
                            logger.debug(f"Plan {plan.plan_id}: yield_drop condition requires correlation_asset='US10Y' or 'TNX'")
                            return False
                        
                        yield_drop_threshold = plan.conditions.get("yield_drop")
                        yield_change_window = plan.conditions.get("yield_change_window", 60)  # Default 60 minutes
                        
                        # Get cached or calculate US10Y yield change
                        cache_key = f"us10y_change_{plan.symbol}_{yield_change_window}"
                        yield_change = self._get_cached_correlation(cache_key)
                        if yield_change is None:
                            # Calculate US10Y yield change (async call in sync context)
                            import asyncio
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                            
                            yield_change = loop.run_until_complete(
                                self.correlation_calculator.calculate_us10y_yield_change(window_minutes=yield_change_window)
                            )
                            if yield_change is not None:
                                self._cache_correlation(cache_key, yield_change)
                        
                        if yield_change is None:
                            logger.debug(f"Plan {plan.plan_id}: US10Y yield change data unavailable")
                            return False
                        
                        # For "yield_drop", we check if yield decreased (negative change) and magnitude >= threshold
                        # yield_change is negative when yield drops, so we check if -yield_change >= threshold
                        if yield_change >= 0:
                            logger.debug(f"Plan {plan.plan_id}: US10Y yield did not drop (change={yield_change:.4f}, expected negative)")
                            return False
                        
                        # Check if drop magnitude meets threshold (convert to positive for comparison)
                        drop_magnitude = abs(yield_change)
                        if drop_magnitude < yield_drop_threshold:
                            logger.debug(f"Plan {plan.plan_id}: US10Y yield drop {drop_magnitude:.4f} < threshold {yield_drop_threshold:.4f}")
                            return False
                        
                        logger.info(f"Plan {plan.plan_id}: US10Y yield drop condition met: drop={drop_magnitude:.4f} >= threshold={yield_drop_threshold:.4f}")
                    
                    # DXY correlation divergence condition
                    if plan.conditions.get("correlation_divergence"):
                        # Check if correlation_asset is DXY
                        correlation_asset = plan.conditions.get("correlation_asset", "").upper()
                        if correlation_asset not in ["DXY", "DX-Y.NYB"]:
                            logger.debug(f"Plan {plan.plan_id}: correlation_divergence condition requires correlation_asset='DXY'")
                            return False
                        
                        divergence_threshold = plan.conditions.get("divergence_threshold", -0.5)  # Default -0.5
                        divergence_window = plan.conditions.get("divergence_window", 60)  # Default 60 minutes
                        
                        # Get cached or calculate divergence
                        cache_key = f"dxy_divergence_{plan.symbol}_{divergence_window}"
                        divergence_result = self._get_cached_correlation(cache_key)
                        if divergence_result is None:
                            # Calculate divergence (async call in sync context)
                            import asyncio
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                            
                            divergence_result = loop.run_until_complete(
                                self.correlation_calculator.detect_dxy_divergence(
                                    symbol=plan.symbol,
                                    window_minutes=divergence_window,
                                    divergence_threshold=divergence_threshold
                                )
                            )
                            if divergence_result and divergence_result.get("data_quality") != "unavailable":
                                self._cache_correlation(cache_key, divergence_result)
                        
                        if not divergence_result or divergence_result.get("data_quality") == "unavailable":
                            logger.debug(f"Plan {plan.plan_id}: DXY divergence data unavailable")
                            return False
                        
                        if not divergence_result.get("divergence_detected", False):
                            correlation = divergence_result.get("correlation")
                            logger.debug(f"Plan {plan.plan_id}: DXY divergence not detected (correlation={correlation:.2f}, threshold={divergence_threshold:.2f})")
                            return False
                        
                        # Optional: Verify direction logic (DXY down + symbol up for BUY, or DXY up + symbol down for SELL)
                        dxy_direction = divergence_result.get("dxy_direction")
                        symbol_direction = divergence_result.get("symbol_direction")
                        correlation = divergence_result.get("correlation")
                        
                        if plan.direction == "BUY":
                            # For BUY: Ideally DXY down + symbol up (bullish divergence)
                            if dxy_direction == "up" and symbol_direction == "down":
                                logger.debug(f"Plan {plan.plan_id}: Divergence direction mismatch for BUY (DXY up, symbol down)")
                                return False
                        elif plan.direction == "SELL":
                            # For SELL: Ideally DXY up + symbol down (bearish divergence)
                            if dxy_direction == "down" and symbol_direction == "up":
                                logger.debug(f"Plan {plan.plan_id}: Divergence direction mismatch for SELL (DXY down, symbol up)")
                                return False
                        
                        logger.info(f"Plan {plan.plan_id}: DXY correlation divergence condition met: correlation={correlation:.2f}, DXY={dxy_direction}, symbol={symbol_direction}")
                    
                    # BTC hold above support
                    if plan.conditions.get("btc_hold_above_support"):
                        if not symbol_norm.upper().startswith('BTC'):
                            logger.debug(f"Plan {plan.plan_id}: btc_hold_above_support only applies to BTC symbols")
                            return False
                        
                        cache_key = f"btc_support_{plan.symbol}"
                        btc_holds = self._get_cached_correlation(cache_key)
                        if btc_holds is None:
                            import asyncio
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                            
                            btc_holds = loop.run_until_complete(
                                self.correlation_calculator.check_btc_hold_above_support(symbol=plan.symbol)
                            )
                            self._cache_correlation(cache_key, btc_holds)
                        
                        if not btc_holds:
                            logger.debug(f"Plan {plan.plan_id}: BTC not holding above support")
                            return False
                    
                    # ETH/BTC Divergence Tracker
                    if plan.conditions.get("ethbtc_ratio_deviation") is not None:
                        deviation_threshold = plan.conditions.get("ethbtc_ratio_deviation")
                        expected_direction = plan.conditions.get("ethbtc_divergence_direction")
                        
                        cache_key = f"ethbtc_ratio_{plan.symbol}"
                        ethbtc_data = self._get_cached_correlation(cache_key)
                        if ethbtc_data is None:
                            import asyncio
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                            
                            ethbtc_data = loop.run_until_complete(
                                self.correlation_calculator.calculate_ethbtc_ratio_deviation()
                            )
                            if ethbtc_data:
                                self._cache_correlation(cache_key, ethbtc_data)
                        
                        if not ethbtc_data:
                            logger.debug(f"Plan {plan.plan_id}: ETH/BTC ratio data unavailable")
                            return False
                        
                        deviation = ethbtc_data.get("deviation", 0)
                        direction = ethbtc_data.get("direction")
                        
                        if abs(deviation) < deviation_threshold:
                            logger.debug(f"Plan {plan.plan_id}: ETH/BTC deviation {deviation:.2f} < threshold {deviation_threshold:.2f}")
                            return False
                        
                        if expected_direction and direction != expected_direction:
                            logger.debug(f"Plan {plan.plan_id}: ETH/BTC direction {direction} != expected {expected_direction}")
                            return False
                    
                    # NASDAQ Risk-On Bridge
                    if plan.conditions.get("nasdaq_15min_bullish") or plan.conditions.get("nasdaq_correlation_confirmed"):
                        cache_key = f"nasdaq_trend_{plan.symbol}"
                        nasdaq_data = self._get_cached_correlation(cache_key)
                        if nasdaq_data is None:
                            import asyncio
                            try:
                                loop = asyncio.get_event_loop()
                            except RuntimeError:
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                            
                            nasdaq_data = loop.run_until_complete(
                                self.correlation_calculator.get_nasdaq_15min_trend()
                            )
                            if nasdaq_data:
                                self._cache_correlation(cache_key, nasdaq_data)
                        
                        if not nasdaq_data:
                            logger.debug(f"Plan {plan.plan_id}: NASDAQ trend data unavailable")
                            return False
                        
                        if plan.conditions.get("nasdaq_15min_bullish") and not nasdaq_data.get("nasdaq_15min_bullish"):
                            logger.debug(f"Plan {plan.plan_id}: NASDAQ 15-min not bullish")
                            return False
                        
                        if plan.conditions.get("nasdaq_correlation_confirmed") and not nasdaq_data.get("nasdaq_correlation_confirmed"):
                            logger.debug(f"Plan {plan.plan_id}: NASDAQ correlation not confirmed")
                            return False
                    
                except Exception as e:
                    logger.error(f"Error checking correlation conditions for {plan.plan_id}: {e}", exc_info=True)
                    # Fail closed - if correlation check fails, don't execute
                    return False
            
            # ============================================================================
            # Phase III: Order Flow Microstructure Condition Checks
            # ============================================================================
            # Check order flow microstructure conditions (imbalance, spoofing, rebuild speed)
            # Only for symbols that have order flow data (primarily BTC)
            if symbol_norm.upper().startswith('BTC'):
                try:
                    # Try to get order flow analyzer from registry
                    order_flow_analyzer = None
                    try:
                        from desktop_agent import registry
                        if hasattr(registry, 'order_flow_service') and registry.order_flow_service:
                            if hasattr(registry.order_flow_service, 'analyzer'):
                                order_flow_analyzer = registry.order_flow_service.analyzer
                    except (ImportError, AttributeError):
                        pass
                    
                    if order_flow_analyzer:
                        # Get Phase III microstructure metrics
                        microstructure = order_flow_analyzer.get_phase3_microstructure_metrics(symbol_norm)
                        
                        if microstructure:
                            # Check imbalance detection
                            if plan.conditions.get("imbalance_detected"):
                                imbalance_data = microstructure.get("imbalance")
                                if not imbalance_data or not imbalance_data.get("imbalance_detected"):
                                    logger.debug(f"Plan {plan.plan_id}: Imbalance not detected")
                                    return False
                                
                                # Check imbalance direction (requires imbalance_detected: true)
                                expected_direction = plan.conditions.get("imbalance_direction")
                                if expected_direction:
                                    actual_direction = imbalance_data.get("imbalance_direction")
                                    if actual_direction != expected_direction:
                                        logger.debug(f"Plan {plan.plan_id}: Imbalance direction {actual_direction} != expected {expected_direction}")
                                        return False
                            
                            # Check spoof detection
                            if plan.conditions.get("spoof_detected"):
                                spoof_data = microstructure.get("spoofing")
                                if not spoof_data or not spoof_data.get("spoof_detected"):
                                    logger.debug(f"Plan {plan.plan_id}: Spoofing not detected")
                                    return False
                            
                            # Check bid/ask rebuild speed
                            rebuild_data = microstructure.get("rebuild_speed")
                            if rebuild_data:
                                bid_rebuild_threshold = plan.conditions.get("bid_rebuild_speed")
                                if bid_rebuild_threshold is not None:
                                    actual_bid_speed = rebuild_data.get("bid_rebuild_speed", 0.0)
                                    if actual_bid_speed < bid_rebuild_threshold:
                                        logger.debug(f"Plan {plan.plan_id}: Bid rebuild speed {actual_bid_speed:.2f} < threshold {bid_rebuild_threshold:.2f}")
                                        return False
                                
                                ask_decay_threshold = plan.conditions.get("ask_decay_speed")
                                if ask_decay_threshold is not None:
                                    actual_ask_speed = rebuild_data.get("ask_decay_speed", 0.0)
                                    if actual_ask_speed < ask_decay_threshold:
                                        logger.debug(f"Plan {plan.plan_id}: Ask decay speed {actual_ask_speed:.2f} < threshold {ask_decay_threshold:.2f}")
                                        return False
                                
                                # Check liquidity rebuild confirmed
                                if plan.conditions.get("liquidity_rebuild_confirmed"):
                                    if not rebuild_data.get("liquidity_rebuild_confirmed"):
                                        logger.debug(f"Plan {plan.plan_id}: Liquidity rebuild not confirmed")
                                        return False
                        else:
                            # Microstructure data unavailable - fail closed if conditions require it
                            if any([
                                plan.conditions.get("imbalance_detected"),
                                plan.conditions.get("spoof_detected"),
                                plan.conditions.get("bid_rebuild_speed") is not None,
                                plan.conditions.get("ask_decay_speed") is not None,
                                plan.conditions.get("liquidity_rebuild_confirmed")
                            ]):
                                logger.debug(f"Plan {plan.plan_id}: Order flow microstructure data unavailable")
                                return False
                    else:
                        # Order flow analyzer not available - fail closed if conditions require it
                        if any([
                            plan.conditions.get("imbalance_detected"),
                            plan.conditions.get("spoof_detected"),
                            plan.conditions.get("bid_rebuild_speed") is not None,
                            plan.conditions.get("ask_decay_speed") is not None,
                            plan.conditions.get("liquidity_rebuild_confirmed")
                        ]):
                            logger.debug(f"Plan {plan.plan_id}: Order flow analyzer not available")
                            return False
                            
                except Exception as e:
                    logger.error(f"Error checking order flow microstructure conditions for {plan.plan_id}: {e}", exc_info=True)
                    # Fail closed - if order flow check fails, don't execute
                    return False
            
            # Check breaker block conditions
            if plan.conditions.get("breaker_block"):
                if not self.m1_analyzer or not self.m1_data_fetcher:
                    logger.warning(f"Breaker block plan {plan.plan_id} requires M1 components (not available)")
                    return False
                
                try:
                    from infra.detection_systems import DetectionSystemManager
                    detector = DetectionSystemManager()
                    breaker_result = detector.get_breaker_block(symbol_norm, timeframe=structure_tf)
                    
                    if not breaker_result:
                        logger.debug(f"Breaker block not detected for {plan.plan_id}")
                        return False
                    
                    # Check if price is retesting broken OB zone
                    if not breaker_result.get("price_retesting_breaker", False):
                        logger.debug(f"Price not retesting breaker zone for {plan.plan_id}")
                        return False
                    
                    # Check if OB was broken first
                    if not breaker_result.get("ob_broken", False):
                        logger.debug(f"Order block not broken before breaker block for {plan.plan_id}")
                        return False
                except Exception as e:
                    logger.warning(f"Error checking breaker block for {plan.plan_id}: {e}")
                    return False
            
            # Check FVG conditions
            if plan.conditions.get("fvg_bull") or plan.conditions.get("fvg_bear"):
                try:
                    from infra.detection_systems import DetectionSystemManager
                    detector = DetectionSystemManager()
                    fvg_result = detector.get_fvg(symbol_norm, timeframe=structure_tf)
                    
                    if not fvg_result:
                        logger.debug(f"FVG not detected for {plan.plan_id}")
                        return False
                    
                    # Check FVG type matches condition
                    if plan.conditions.get("fvg_bull"):
                        fvg_bull = fvg_result.get("fvg_bull")
                        if not fvg_bull or not isinstance(fvg_bull, dict):
                            logger.debug(f"FVG bull not detected or invalid format for {plan.plan_id}")
                            return False
                    if plan.conditions.get("fvg_bear"):
                        fvg_bear = fvg_result.get("fvg_bear")
                        if not fvg_bear or not isinstance(fvg_bear, dict):
                            logger.debug(f"FVG bear not detected or invalid format for {plan.plan_id}")
                            return False
                    
                    # Check FVG fill percentage (if specified)
                    fvg_filled_pct = plan.conditions.get("fvg_filled_pct")
                    if fvg_filled_pct:
                        # Get filled_pct from the appropriate FVG dict
                        if plan.conditions.get("fvg_bull"):
                            fvg_bull = fvg_result.get("fvg_bull", {})
                            actual_filled = fvg_bull.get("filled_pct", 0.0) if isinstance(fvg_bull, dict) else 0.0
                        elif plan.conditions.get("fvg_bear"):
                            fvg_bear = fvg_result.get("fvg_bear", {})
                            actual_filled = fvg_bear.get("filled_pct", 0.0) if isinstance(fvg_bear, dict) else 0.0
                        else:
                            # Fallback to top-level filled_pct
                            actual_filled = fvg_result.get("filled_pct", 0.0)
                        
                        # Parse fill percentage range
                        if isinstance(fvg_filled_pct, dict):
                            min_fill = fvg_filled_pct.get("min", 0.5)
                            max_fill = fvg_filled_pct.get("max", 0.75)
                        elif isinstance(fvg_filled_pct, (int, float)):
                            # Single value means "at least this much filled"
                            min_fill = float(fvg_filled_pct)
                            max_fill = 1.0
                        else:
                            # Default range if invalid format
                            min_fill = 0.5
                            max_fill = 0.75
                        
                        if not (min_fill <= actual_filled <= max_fill):
                            logger.debug(f"FVG fill {actual_filled:.0%} not in range {min_fill:.0%}-{max_fill:.0%} for {plan.plan_id}")
                            return False
                except Exception as e:
                    logger.warning(f"Error checking FVG for {plan.plan_id}: {e}")
                    return False
            
            # ============================================================================
            # Phase III: Institutional Signature Detection Condition Checks
            # ============================================================================
            # Check institutional signature patterns (mitigation cascade, breaker chains, liquidity vacuum)
            try:
                from infra.institutional_signature_detector import InstitutionalSignatureDetector
                
                # Initialize detector (singleton pattern - reuse if exists)
                if not hasattr(self, '_institutional_signature_detector'):
                    self._institutional_signature_detector = InstitutionalSignatureDetector()
                
                detector = self._institutional_signature_detector
                
                # Check mitigation cascade (requires mitigation_block: true)
                if plan.conditions.get("overlapping_obs_count") is not None or plan.conditions.get("mitigation_cascade_confirmed"):
                    # First check if mitigation_block is required
                    if not plan.conditions.get("mitigation_block"):
                        logger.debug(f"Plan {plan.plan_id}: overlapping_obs_count/mitigation_cascade_confirmed requires mitigation_block: true")
                        return False
                    
                    from infra.detection_systems import DetectionSystemManager
                    detection_manager = DetectionSystemManager()
                    mitigation_result = detection_manager.get_mitigation_block(symbol_norm, timeframe=structure_tf)
                    
                    if mitigation_result:
                        # Get recent OB detections
                        ob_detections = [mitigation_result] if mitigation_result else []
                        
                        min_overlapping = plan.conditions.get("overlapping_obs_count", 3)
                        cascade_result = detector.detect_mitigation_cascade(
                            symbol_norm,
                            ob_detections,
                            min_overlapping_count=min_overlapping
                        )
                        
                        if cascade_result:
                            # Check overlapping count threshold
                            if plan.conditions.get("overlapping_obs_count") is not None:
                                actual_count = cascade_result.get("overlapping_obs_count", 0)
                                if actual_count < min_overlapping:
                                    logger.debug(f"Plan {plan.plan_id}: Overlapping OBs count {actual_count} < {min_overlapping}")
                                    return False
                            
                            # Check cascade confirmed
                            if plan.conditions.get("mitigation_cascade_confirmed"):
                                if not cascade_result.get("mitigation_cascade_confirmed"):
                                    logger.debug(f"Plan {plan.plan_id}: Mitigation cascade not confirmed")
                                    return False
                        else:
                            logger.debug(f"Plan {plan.plan_id}: Mitigation cascade detection failed")
                            return False
                    else:
                        logger.debug(f"Plan {plan.plan_id}: Mitigation block not detected")
                        return False
                
                # Check breaker retest chain (requires breaker_block: true)
                if plan.conditions.get("breaker_retest_count") is not None or plan.conditions.get("breaker_retest_chain_confirmed"):
                    # First check if breaker_block is required
                    if not plan.conditions.get("breaker_block"):
                        logger.debug(f"Plan {plan.plan_id}: breaker_retest_count/breaker_retest_chain_confirmed requires breaker_block: true")
                        return False
                    
                    from infra.detection_systems import DetectionSystemManager
                    detection_manager = DetectionSystemManager()
                    breaker_result = detection_manager.get_breaker_block(symbol_norm, timeframe=structure_tf)
                    
                    if breaker_result and breaker_result.get("price_retesting_breaker", False):
                        min_retest = plan.conditions.get("breaker_retest_count", 2)
                        chain_result = detector.detect_breaker_retest_chain(
                            symbol_norm,
                            breaker_result,
                            min_retest_count=min_retest
                        )
                        
                        if chain_result:
                            # Check retest count threshold
                            if plan.conditions.get("breaker_retest_count") is not None:
                                actual_count = chain_result.get("breaker_retest_count", 0)
                                if actual_count < min_retest:
                                    logger.debug(f"Plan {plan.plan_id}: Breaker retest count {actual_count} < {min_retest}")
                                    return False
                            
                            # Check chain confirmed
                            if plan.conditions.get("breaker_retest_chain_confirmed"):
                                if not chain_result.get("breaker_retest_chain_confirmed"):
                                    logger.debug(f"Plan {plan.plan_id}: Breaker retest chain not confirmed")
                                    return False
                        else:
                            logger.debug(f"Plan {plan.plan_id}: Breaker retest chain detection failed")
                            return False
                    else:
                        logger.debug(f"Plan {plan.plan_id}: Breaker block not detected or not retesting")
                        return False
                
                # Check liquidity vacuum refill (requires fvg_bull/bear and imbalance_detected)
                if plan.conditions.get("liquidity_vacuum_refill"):
                    # First check if FVG and imbalance are required
                    fvg_required = plan.conditions.get("fvg_bull") or plan.conditions.get("fvg_bear")
                    imbalance_required = plan.conditions.get("imbalance_detected")
                    
                    if not (fvg_required and imbalance_required):
                        logger.debug(f"Plan {plan.plan_id}: liquidity_vacuum_refill requires fvg_bull/bear and imbalance_detected")
                        return False
                    
                    # Get FVG detection
                    from infra.detection_systems import DetectionSystemManager
                    detection_manager = DetectionSystemManager()
                    fvg_result = detection_manager.get_fvg(symbol_norm, timeframe=structure_tf)
                    
                    # Get imbalance detection (from order flow if available)
                    imbalance_data = None
                    if symbol_norm.upper().startswith('BTC'):
                        try:
                            from desktop_agent import registry
                            if hasattr(registry, 'order_flow_service') and registry.order_flow_service:
                                if hasattr(registry.order_flow_service, 'analyzer'):
                                    order_flow_analyzer = registry.order_flow_service.analyzer
                                    microstructure = order_flow_analyzer.get_phase3_microstructure_metrics(symbol_norm)
                                    if microstructure:
                                        imbalance_data = microstructure.get("imbalance")
                        except (ImportError, AttributeError):
                            pass
                    
                    if fvg_result and imbalance_data and imbalance_data.get("imbalance_detected"):
                        vacuum_result = detector.detect_liquidity_vacuum_refill(
                            symbol_norm,
                            fvg_result,
                            imbalance_data
                        )
                        
                        if not vacuum_result or not vacuum_result.get("liquidity_vacuum_refill"):
                            logger.debug(f"Plan {plan.plan_id}: Liquidity vacuum refill not detected")
                            return False
                    else:
                        logger.debug(f"Plan {plan.plan_id}: FVG or imbalance not detected for liquidity vacuum")
                        return False
                
            except ImportError:
                # Institutional signature detector not available
                if any([
                    plan.conditions.get("overlapping_obs_count") is not None,
                    plan.conditions.get("mitigation_cascade_confirmed"),
                    plan.conditions.get("breaker_retest_count") is not None,
                    plan.conditions.get("breaker_retest_chain_confirmed"),
                    plan.conditions.get("liquidity_vacuum_refill")
                ]):
                    logger.debug(f"Plan {plan.plan_id}: Institutional signature detector not available")
                    return False
            except Exception as e:
                logger.error(f"Error checking institutional signature conditions for {plan.plan_id}: {e}", exc_info=True)
                return False
            
            # Check MSS conditions
            if plan.conditions.get("mss_bull") or plan.conditions.get("mss_bear"):
                try:
                    from infra.detection_systems import DetectionSystemManager
                    detector = DetectionSystemManager()
                    mss_result = detector.get_market_structure_shift(symbol_norm, timeframe=structure_tf)
                    
                    if not mss_result:
                        logger.debug(f"MSS not detected for {plan.plan_id}")
                        return False
                    
                    # Check MSS type matches condition
                    if plan.conditions.get("mss_bull") and not mss_result.get("mss_bull", False):
                        return False
                    if plan.conditions.get("mss_bear") and not mss_result.get("mss_bear", False):
                        return False
                    
                    # Check pullback requirement
                    if plan.conditions.get("pullback_to_mss", True):  # Default True
                        if not mss_result.get("pullback_to_mss", False):
                            logger.debug(f"Pullback to MSS not detected for {plan.plan_id}")
                            return False
                except Exception as e:
                    logger.warning(f"Error checking MSS for {plan.plan_id}: {e}")
                    return False
            
            # Check mitigation block conditions
            if plan.conditions.get("mitigation_block_bull") or plan.conditions.get("mitigation_block_bear"):
                try:
                    from infra.detection_systems import DetectionSystemManager
                    detector = DetectionSystemManager()
                    mitigation_result = detector.get_mitigation_block(symbol_norm, timeframe=structure_tf)
                    
                    if not mitigation_result:
                        logger.debug(f"Mitigation block not detected for {plan.plan_id}")
                        return False
                    
                    # Check type matches
                    if plan.conditions.get("mitigation_block_bull") and not mitigation_result.get("mitigation_block_bull"):
                        return False
                    if plan.conditions.get("mitigation_block_bear") and not mitigation_result.get("mitigation_block_bear"):
                        return False
                    
                    # Check structure broken requirement
                    if plan.conditions.get("structure_broken", True):  # Default True
                        if not mitigation_result.get("structure_broken", False):
                            logger.debug(f"Structure not broken for mitigation block {plan.plan_id}")
                            return False
                except Exception as e:
                    logger.warning(f"Error checking mitigation block for {plan.plan_id}: {e}")
                    return False
            
            # Check inducement reversal conditions
            if plan.conditions.get("liquidity_grab_bull") or plan.conditions.get("liquidity_grab_bear"):
                try:
                    from infra.detection_systems import DetectionSystemManager
                    detector = DetectionSystemManager()
                    inducement_result = detector.get_rejection_pattern(symbol_norm, timeframe=structure_tf)
                    
                    if not inducement_result:
                        logger.debug(f"Inducement not detected for {plan.plan_id}")
                        return False
                    
                    # Check type matches (liquidity grab + rejection)
                    if plan.conditions.get("liquidity_grab_bull") and not inducement_result.get("liquidity_grab_bull"):
                        return False
                    if plan.conditions.get("liquidity_grab_bear") and not inducement_result.get("liquidity_grab_bear"):
                        return False
                    
                    # Check rejection requirement
                    if plan.conditions.get("rejection_detected", True):  # Default True
                        if not inducement_result.get("rejection_detected", False):
                            logger.debug(f"Rejection not detected for inducement {plan.plan_id}")
                            return False
                except Exception as e:
                    logger.warning(f"Error checking inducement for {plan.plan_id}: {e}")
                    return False
            
            # Check premium/discount array conditions
            if plan.conditions.get("price_in_discount") or plan.conditions.get("price_in_premium"):
                try:
                    from infra.detection_systems import DetectionSystemManager
                    detector = DetectionSystemManager()
                    fib_result = detector.get_fibonacci_levels(symbol_norm)
                    
                    if not fib_result:
                        logger.debug(f"Fibonacci levels not available for {plan.plan_id}")
                        return False
                    
                    # Check discount zone
                    if plan.conditions.get("price_in_discount"):
                        if not fib_result.get("price_in_discount", False):
                            logger.debug(f"Price not in discount zone for {plan.plan_id}")
                            return False
                    
                    # Check premium zone
                    if plan.conditions.get("price_in_premium"):
                        if not fib_result.get("price_in_premium", False):
                            logger.debug(f"Price not in premium zone for {plan.plan_id}")
                            return False
                except Exception as e:
                    logger.warning(f"Error checking premium/discount for {plan.plan_id}: {e}")
                    return False
            
            # Check session liquidity run conditions
            if plan.conditions.get("asian_session_high") or plan.conditions.get("asian_session_low"):
                try:
                    from infra.detection_systems import DetectionSystemManager
                    detector = DetectionSystemManager()
                    session_result = detector.get_session_liquidity(symbol_norm)
                    
                    if not session_result:
                        logger.debug(f"Session liquidity not available for {plan.plan_id}")
                        return False
                    
                    # Check London session active
                    if plan.conditions.get("london_session_active", True):  # Default True
                        if not session_result.get("london_session_active", False):
                            logger.debug(f"London session not active for {plan.plan_id}")
                            return False
                    
                    # Check sweep detected
                    if plan.conditions.get("sweep_detected", True):  # Default True
                        if not session_result.get("sweep_detected", False):
                            logger.debug(f"Sweep not detected for {plan.plan_id}")
                            return False
                    
                    # Check reversal structure
                    if plan.conditions.get("reversal_structure", True):  # Default True
                        if not session_result.get("reversal_structure", False):
                            logger.debug(f"Reversal structure not confirmed for {plan.plan_id}")
                            return False
                except Exception as e:
                    logger.warning(f"Error checking session liquidity for {plan.plan_id}: {e}")
                    return False
            
            # ============================================================================
            # Phase III: Momentum Decay Detection Condition Checks
            # ============================================================================
            # Check momentum decay conditions (RSI/MACD divergence, tick rate decline)
            if any([
                plan.conditions.get("momentum_decay_trap"),
                plan.conditions.get("rsi_divergence_detected"),
                plan.conditions.get("macd_divergence_detected"),
                plan.conditions.get("tick_rate_declining"),
                plan.conditions.get("momentum_decay_confirmed")
            ]):
                try:
                    from infra.momentum_decay_detector import MomentumDecayDetector
                    
                    # Initialize detector (singleton pattern)
                    if not hasattr(self, '_momentum_decay_detector'):
                        self._momentum_decay_detector = MomentumDecayDetector(cache_ttl_seconds=120)
                    
                    detector = self._momentum_decay_detector
                    
                    # Get current RSI and MACD from indicators
                    try:
                        from infra.indicator_bridge import IndicatorBridge
                        indicator_bridge = IndicatorBridge()
                        tf_data = indicator_bridge._get_timeframe_data(symbol_norm, mt5.TIMEFRAME_M15, "M15")
                        
                        if not tf_data:
                            logger.debug(f"Plan {plan.plan_id}: Indicator data unavailable for momentum decay check")
                            return False
                        
                        indicators = tf_data.get("indicators", {})
                        current_rsi = indicators.get("rsi", 50.0)
                        current_macd = indicators.get("macd", 0.0)
                        current_price_val = current_price  # Already available from earlier
                        
                        # Get tick rate (from order flow if available, or use default)
                        current_tick_rate = 0.0
                        if symbol_norm.upper().startswith('BTC'):
                            try:
                                from desktop_agent import registry
                                if hasattr(registry, 'order_flow_service') and registry.order_flow_service:
                                    if hasattr(registry.order_flow_service, 'analyzer'):
                                        order_flow_analyzer = registry.order_flow_service.analyzer
                                        microstructure = order_flow_analyzer.get_phase3_microstructure_metrics(symbol_norm)
                                        if microstructure:
                                            rebuild_data = microstructure.get("rebuild_speed")
                                            if rebuild_data:
                                                # Use tick rate from order flow if available
                                                # For now, use a default value (would need tick rate tracking)
                                                current_tick_rate = 1.0  # Placeholder
                            except (ImportError, AttributeError):
                                pass
                        
                        # Check RSI divergence
                        if plan.conditions.get("rsi_divergence_detected"):
                            rsi_result = detector.detect_rsi_divergence(symbol_norm, current_rsi, current_price_val)
                            if not rsi_result or not rsi_result.get("rsi_divergence_detected"):
                                logger.debug(f"Plan {plan.plan_id}: RSI divergence not detected")
                                return False
                        
                        # Check MACD divergence
                        if plan.conditions.get("macd_divergence_detected"):
                            macd_result = detector.detect_macd_divergence(symbol_norm, current_macd, current_price_val)
                            if not macd_result or not macd_result.get("macd_divergence_detected"):
                                logger.debug(f"Plan {plan.plan_id}: MACD divergence not detected")
                                return False
                        
                        # Check tick rate decline
                        if plan.conditions.get("tick_rate_declining"):
                            tick_result = detector.detect_tick_rate_decline(symbol_norm, current_tick_rate)
                            if not tick_result or not tick_result.get("tick_rate_declining"):
                                logger.debug(f"Plan {plan.plan_id}: Tick rate not declining")
                                return False
                        
                        # Check momentum decay confirmation (composite)
                        if plan.conditions.get("momentum_decay_confirmed"):
                            decay_result = detector.detect_momentum_decay(
                                symbol_norm,
                                current_rsi,
                                current_macd,
                                current_price_val,
                                current_tick_rate
                            )
                            if not decay_result or not decay_result.get("momentum_decay_confirmed"):
                                logger.debug(f"Plan {plan.plan_id}: Momentum decay not confirmed")
                                return False
                        
                        # Update detector history for future checks
                        detector._update_momentum_history(symbol_norm, current_rsi, current_macd, current_price_val)
                        if current_tick_rate > 0:
                            detector._update_tick_rate_history(symbol_norm, current_tick_rate)
                        
                    except Exception as e:
                        logger.error(f"Error getting indicators for momentum decay check: {e}", exc_info=True)
                        return False
                        
                except ImportError:
                    # Momentum decay detector not available
                    logger.debug(f"Plan {plan.plan_id}: Momentum decay detector not available")
                    return False
                except Exception as e:
                    logger.error(f"Error checking momentum decay conditions for {plan.plan_id}: {e}", exc_info=True)
                    return False
            
            # Check kill zone conditions
            if plan.conditions.get("kill_zone_active"):
                try:
                    from infra.session_helpers import is_kill_zone_active
                    from infra.detection_systems import DetectionSystemManager
                    
                    # Check kill zone active
                    if not is_kill_zone_active():
                        logger.debug(f"Kill zone not active for {plan.plan_id}")
                        return False
                    
                    # Check volatility spike
                    if plan.conditions.get("volatility_spike", True):  # Default True
                        detector = DetectionSystemManager()
                        vol_result = detector.get_volatility_spike(symbol_norm)
                        if not vol_result or not vol_result.get("volatility_spike", False):
                            logger.debug(f"Volatility spike not detected for {plan.plan_id}")
                            return False
                except Exception as e:
                    logger.warning(f"Error checking kill zone for {plan.plan_id}: {e}")
                    return False
            
            # Check liquidity sweep condition
            if plan.conditions.get("liquidity_sweep"):
                if not self.m1_analyzer or not self.m1_data_fetcher:
                    logger.warning(f"Liquidity sweep plan {plan.plan_id} requires M1 components (not available)")
                    return False
                
                try:
                    # Fetch M1 data
                    m1_candles = self.m1_data_fetcher.fetch_m1_data(symbol_norm, count=200)
                    if not m1_candles or len(m1_candles) < 50:
                        logger.debug(f"Insufficient M1 data for liquidity sweep check on {symbol_norm}")
                        return False
                    
                    # Analyze M1 microstructure
                    m1_analysis = self.m1_analyzer.analyze_microstructure(
                        symbol=symbol_norm,
                        candles=m1_candles,
                        current_price=current_price
                    )
                    
                    if not m1_analysis or not m1_analysis.get('available'):
                        logger.debug(f"M1 analysis unavailable for liquidity sweep check on {symbol_norm}")
                        return False
                    
                    # Check for liquidity sweep using existing method
                    sweep_detected = self._detect_liquidity_sweep(plan, m1_analysis, current_price)
                    if not sweep_detected:
                        logger.debug(f"No liquidity sweep detected for {symbol_norm}")
                        return False
                    
                    logger.info(f"Liquidity sweep detected for {symbol_norm}")
                except Exception as e:
                    logger.error(f"Error checking liquidity sweep condition for {symbol_norm}: {e}", exc_info=True)
                    return False
            
            # Check VWAP deviation condition
            if "vwap_deviation" in plan.conditions:
                deviation_threshold = plan.conditions.get("vwap_deviation_threshold", 2.0)  # Default 2σ
                deviation_direction = plan.conditions.get("vwap_deviation_direction", "any")  # "above", "below", "any"
                
                try:
                    # Get M1 data for VWAP
                    if self.m1_analyzer and self.m1_data_fetcher:
                        m1_candles = self.m1_data_fetcher.fetch_m1_data(symbol_norm, count=200)
                        if m1_candles and len(m1_candles) >= 50:
                            m1_analysis = self.m1_analyzer.analyze_microstructure(
                                symbol=symbol_norm,
                                candles=m1_candles,
                                current_price=current_price
                            )
                            
                            if m1_analysis and m1_analysis.get('available'):
                                vwap_data = m1_analysis.get('vwap', {})
                                vwap_price = vwap_data.get('value')
                                vwap_std = vwap_data.get('std', 0)
                                
                                if vwap_price and vwap_std > 0:
                                    deviation = abs(current_price - vwap_price) / vwap_std
                                    
                                    # Check threshold
                                    if deviation < deviation_threshold:
                                        logger.debug(f"VWAP deviation too low: {deviation:.2f}σ < {deviation_threshold}σ")
                                        return False
                                    
                                    # Check direction if specified
                                    if deviation_direction == "above" and current_price < vwap_price:
                                        logger.debug(f"VWAP deviation direction mismatch: price below VWAP but 'above' required")
                                        return False
                                    elif deviation_direction == "below" and current_price > vwap_price:
                                        logger.debug(f"VWAP deviation direction mismatch: price above VWAP but 'below' required")
                                        return False
                                    
                                    logger.info(f"VWAP deviation condition met: {deviation:.2f}σ ({deviation_direction})")
                                else:
                                    logger.debug(f"VWAP data not available for {symbol_norm} (plan {plan.plan_id})")
                                    return False
                            else:
                                logger.debug(f"M1 analysis not available for VWAP deviation check (plan {plan.plan_id})")
                                return False
                        else:
                            logger.debug(f"Insufficient M1 data for VWAP deviation check (plan {plan.plan_id})")
                            return False
                    else:
                        logger.debug(f"M1 components not available for VWAP deviation check (plan {plan.plan_id})")
                        return False
                except Exception as e:
                    logger.error(f"Error checking VWAP deviation condition: {e}", exc_info=True)
                    return False
            
            # Check EMA slope condition
            if "ema_slope" in plan.conditions:
                ema_period = plan.conditions.get("ema_period", 200)  # Default EMA200
                ema_timeframe = plan.conditions.get("ema_timeframe", "H1")  # Default H1
                slope_direction = plan.conditions.get("ema_slope_direction", "any")  # "bullish", "bearish", "any"
                min_slope_pct = plan.conditions.get("min_ema_slope_pct", 0.0)  # Minimum slope percentage
                
                try:
                    # Get candles for EMA calculation
                    candles = _get_recent_candles(symbol_norm, timeframe=ema_timeframe, count=ema_period + 20)
                    candles = _normalize_candles(candles)
                    if len(candles) < ema_period + 5:
                        logger.warning(f"Insufficient candles for EMA slope check: {len(candles) if candles else 0} < {ema_period + 5}")
                        return False
                    
                    # Calculate EMA
                    closes = [c['close'] if isinstance(c, dict) else c.close for c in candles]
                    
                    # Simple EMA calculation
                    multiplier = 2.0 / (ema_period + 1)
                    ema_values = []
                    ema = closes[0]  # Start with first close
                    
                    for close in closes[1:]:
                        ema = (close - ema) * multiplier + ema
                        ema_values.append(ema)
                    
                    if len(ema_values) < 2:
                        logger.warning("Insufficient EMA values for slope calculation")
                        return False
                    
                    # Calculate slope (percentage change over last N periods)
                    lookback = min(10, len(ema_values))
                    ema_current = ema_values[-1]
                    ema_previous = ema_values[-lookback]
                    
                    if ema_previous == 0:
                        slope_pct = 0.0
                    else:
                        slope_pct = ((ema_current - ema_previous) / ema_previous) * 100
                    
                    # Check minimum slope
                    if abs(slope_pct) < min_slope_pct:
                        logger.debug(f"EMA slope too low: {slope_pct:.2f}% < {min_slope_pct}%")
                        return False
                    
                    # Check direction
                    is_bullish = slope_pct > 0
                    if slope_direction == "bullish" and not is_bullish:
                        logger.debug(f"EMA slope direction mismatch: {slope_pct:.2f}% (bearish) but 'bullish' required")
                        return False
                    elif slope_direction == "bearish" and is_bullish:
                        logger.debug(f"EMA slope direction mismatch: {slope_pct:.2f}% (bullish) but 'bearish' required")
                        return False
                    
                    logger.info(f"EMA slope condition met: {slope_pct:.2f}% ({'bullish' if is_bullish else 'bearish'})")
                except Exception as e:
                    logger.error(f"Error checking EMA slope condition: {e}", exc_info=True)
                    return False
            
            # Check BB squeeze condition
            if plan.conditions.get("bb_squeeze"):
                try:
                    # Get timeframe from conditions or default to M15
                    bb_tf = plan.conditions.get("timeframe", "M15")
                    bb_candles = _get_recent_candles(symbol_norm, timeframe=bb_tf, count=50)
                    bb_candles = _normalize_candles(bb_candles)
                    
                    if not bb_candles or len(bb_candles) < 20:
                        logger.debug(f"Insufficient candles for BB squeeze check on {symbol_norm}")
                        return False
                    
                    # Calculate BB width (as percentage)
                    closes = [c['close'] if isinstance(c, dict) else c.close for c in bb_candles[:20]]
                    sma = sum(closes) / len(closes)
                    if sma == 0:
                        return False
                    
                    std_dev = (sum((c - sma) ** 2 for c in closes) / len(closes)) ** 0.5
                    bb_width_pct = (std_dev * 2) / sma * 100  # As percentage
                    
                    # Squeeze threshold (default 1.5% for M15)
                    squeeze_threshold = plan.conditions.get("bb_squeeze_threshold", 1.5)
                    
                    if bb_width_pct >= squeeze_threshold:
                        logger.debug(f"BB squeeze condition not met: BB width {bb_width_pct:.2f}% >= {squeeze_threshold}%")
                        return False
                    
                    logger.info(f"BB squeeze condition met: BB width {bb_width_pct:.2f}% < {squeeze_threshold}%")
                except Exception as e:
                    logger.error(f"Error checking BB squeeze condition: {e}", exc_info=True)
                    return False
            
            # Check BB expansion condition
            if plan.conditions.get("bb_expansion"):
                try:
                    # Get timeframe(s) from conditions
                    bb_tf = plan.conditions.get("timeframe", "M15")
                    # Support checking both M5 and M15 if specified
                    check_both_tf = plan.conditions.get("bb_expansion_check_both", False)
                    
                    expansion_threshold = plan.conditions.get("bb_expansion_threshold", 2.0)
                    expansion_detected = False
                    
                    # Check specified timeframe
                    timeframes_to_check = [bb_tf]
                    if check_both_tf and bb_tf == "M15":
                        # Also check M5 if both requested
                        timeframes_to_check.append("M5")
                    
                    for tf in timeframes_to_check:
                        bb_candles = _get_recent_candles(symbol_norm, timeframe=tf, count=50)
                        bb_candles = _normalize_candles(bb_candles)
                        
                        if not bb_candles or len(bb_candles) < 20:
                            logger.debug(f"Insufficient candles for BB expansion check on {symbol_norm} {tf}")
                            continue
                        
                        # Calculate BB width (as percentage)
                        closes = [c['close'] if isinstance(c, dict) else c.close for c in bb_candles[:20]]
                        sma = sum(closes) / len(closes)
                        if sma == 0:
                            continue
                        
                        std_dev = (sum((c - sma) ** 2 for c in closes) / len(closes)) ** 0.5
                        bb_width_pct = (std_dev * 2) / sma * 100  # As percentage
                        
                        if bb_width_pct > expansion_threshold:
                            expansion_detected = True
                            logger.info(f"BB expansion condition met on {tf}: BB width {bb_width_pct:.2f}% > {expansion_threshold}%")
                            break
                    
                    if not expansion_detected:
                        logger.debug(f"BB expansion condition not met on any checked timeframe(s): {timeframes_to_check}")
                        return False
                        
                except Exception as e:
                    logger.error(f"Error checking BB expansion condition: {e}", exc_info=True)
                    return False
            
            # Check BB retest condition
            if plan.conditions.get("bb_retest"):
                try:
                    # Get timeframe from conditions or default to M15
                    bb_retest_tf = plan.conditions.get("timeframe", "M15")
                    bb_retest_tolerance = plan.conditions.get("bb_retest_tolerance", 0.5)  # Default 0.5%
                    bb_retest_lookback = plan.conditions.get("bb_retest_lookback", 30)  # Default 30 candles
                    bb_retest_require_bounce = plan.conditions.get("bb_retest_require_bounce", True)  # Default True
                    
                    # Fetch sufficient candles for history (50 for BB calculation + lookback)
                    bb_retest_candles = _get_recent_candles(symbol_norm, timeframe=bb_retest_tf, count=50)
                    bb_retest_candles = _normalize_candles(bb_retest_candles)
                    
                    if not bb_retest_candles or len(bb_retest_candles) < max(30, bb_retest_lookback):
                        logger.debug(f"Insufficient candles for BB retest check on {symbol_norm} {bb_retest_tf}: {len(bb_retest_candles) if bb_retest_candles else 0} < {max(30, bb_retest_lookback)}")
                        return False
                    
                    # BB period (standard 20-period)
                    bb_period = 20
                    if len(bb_retest_candles) < bb_period + bb_retest_lookback:
                        logger.debug(f"Insufficient candles for BB retest: need {bb_period + bb_retest_lookback}, have {len(bb_retest_candles)}")
                        return False
                    
                    # Step 1: Scan backwards to find most recent BB break
                    break_found = False
                    break_level = None
                    break_direction = None  # "bullish" or "bearish"
                    break_candle_idx = None
                    
                    # Start from recent enough to have BB calculation, but not too recent (need history)
                    start_idx = min(len(bb_retest_candles) - bb_period - 1, len(bb_retest_candles) - 5)
                    
                    for i in range(start_idx, bb_period, -1):
                        if i < bb_period:
                            break
                        
                        # Calculate BB for this point in time (rolling window ending at i)
                        window_candles = bb_retest_candles[i - bb_period + 1:i + 1]
                        closes = [c['close'] if isinstance(c, dict) else c.close for c in window_candles]
                        
                        if len(closes) < bb_period:
                            continue
                        
                        sma = sum(closes) / len(closes)
                        if sma == 0:
                            continue
                        
                        std_dev = (sum((c - sma) ** 2 for c in closes) / len(closes)) ** 0.5
                        upper_bb = sma + (2 * std_dev)
                        lower_bb = sma - (2 * std_dev)
                        
                        # Get current candle high/low
                        current_candle = bb_retest_candles[i]
                        current_high = current_candle['high'] if isinstance(current_candle, dict) else current_candle.high
                        current_low = current_candle['low'] if isinstance(current_candle, dict) else current_candle.low
                        
                        # Get previous candle for comparison
                        if i > 0:
                            prev_candle = bb_retest_candles[i - 1]
                            prev_high = prev_candle['high'] if isinstance(prev_candle, dict) else prev_candle.high
                            prev_low = prev_candle['low'] if isinstance(prev_candle, dict) else prev_candle.low
                            
                            # Calculate previous BB (for comparison)
                            prev_window = bb_retest_candles[i - bb_period:i]
                            if len(prev_window) >= bb_period:
                                prev_closes = [c['close'] if isinstance(c, dict) else c.close for c in prev_window]
                                prev_sma = sum(prev_closes) / len(prev_closes)
                                prev_std_dev = (sum((c - prev_sma) ** 2 for c in prev_closes) / len(prev_closes)) ** 0.5
                                prev_upper_bb = prev_sma + (2 * prev_std_dev)
                                prev_lower_bb = prev_sma - (2 * prev_std_dev)
                                
                                # Check for bullish break (high > upper BB, previous didn't)
                                if current_high > upper_bb and prev_high <= prev_upper_bb:
                                    break_found = True
                                    break_level = upper_bb
                                    break_direction = "bullish"
                                    break_candle_idx = i
                                    break
                                
                                # Check for bearish break (low < lower BB, previous didn't)
                                if current_low < lower_bb and prev_low >= prev_lower_bb:
                                    break_found = True
                                    break_level = lower_bb
                                    break_direction = "bearish"
                                    break_candle_idx = i
                                    break
                    
                    if not break_found:
                        logger.debug(f"Plan {plan.plan_id}: No BB break found in history for {symbol_norm} {bb_retest_tf}")
                        return False
                    
                    # Step 2: Check if price is now retesting that BB level (within tolerance)
                    # Check recent candles (last 2-3) for retest
                    retest_found = False
                    retest_candle_idx = None
                    
                    # Check last 3 candles for retest
                    for i in range(min(3, len(bb_retest_candles))):
                        candle = bb_retest_candles[i]
                        candle_close = candle['close'] if isinstance(candle, dict) else candle.close
                        candle_high = candle['high'] if isinstance(candle, dict) else candle.high
                        candle_low = candle['low'] if isinstance(candle, dict) else candle.low
                        
                        # Calculate distance from broken BB level
                        if break_direction == "bullish":
                            # For bullish break, check if price retests upper BB
                            distance = abs(candle_high - break_level)
                            distance_pct = (distance / break_level) * 100 if break_level > 0 else 100
                        else:  # bearish
                            # For bearish break, check if price retests lower BB
                            distance = abs(candle_low - break_level)
                            distance_pct = (distance / break_level) * 100 if break_level > 0 else 100
                        
                        if distance_pct <= bb_retest_tolerance:
                            retest_found = True
                            retest_candle_idx = i
                            logger.debug(f"Plan {plan.plan_id}: BB retest detected at candle {i}, distance {distance_pct:.2f}% <= {bb_retest_tolerance}%")
                            break
                    
                    if not retest_found:
                        logger.debug(f"Plan {plan.plan_id}: BB retest not detected (price not within {bb_retest_tolerance}% of break level {break_level:.2f})")
                        return False
                    
                    # Step 3: Verify bounce/rejection (if required)
                    if bb_retest_require_bounce:
                        # Check if price moved away from BB after retest
                        # Compare retest candle to more recent candle (candle 0 is most recent)
                        if retest_candle_idx is not None and retest_candle_idx > 0:
                            # Get candle after retest (more recent = lower index)
                            after_retest_candle = bb_retest_candles[retest_candle_idx - 1]
                            after_close = after_retest_candle['close'] if isinstance(after_retest_candle, dict) else after_retest_candle.close
                            
                            retest_candle = bb_retest_candles[retest_candle_idx]
                            retest_close = retest_candle['close'] if isinstance(retest_candle, dict) else retest_candle.close
                            
                            if break_direction == "bullish":
                                # For bullish break, price should move down after retest (rejection)
                                bounce_detected = after_close < retest_close
                            else:  # bearish
                                # For bearish break, price should move up after retest (bounce)
                                bounce_detected = after_close > retest_close
                            
                            if not bounce_detected:
                                logger.debug(f"Plan {plan.plan_id}: BB retest found but bounce not detected (require_bounce=True)")
                                return False
                        elif retest_candle_idx == 0:
                            # Retest is on most recent candle, can't verify bounce yet
                            logger.debug(f"Plan {plan.plan_id}: BB retest on most recent candle, bounce verification not possible")
                            return False
                    
                    logger.info(f"Plan {plan.plan_id}: BB retest condition met on {bb_retest_tf} ({break_direction} break at {break_level:.2f}, retest detected)")
                    
                except Exception as e:
                    logger.error(f"Error checking BB retest condition for {plan.plan_id}: {e}", exc_info=True)
                    return False
            
            # Check z-score condition (statistical mean reversion)
            if plan.conditions.get("zscore"):
                try:
                    # Get parameters from conditions
                    z_threshold = plan.conditions.get("z_threshold", 2.0)  # Default 2.0 standard deviations
                    zscore_lookback = plan.conditions.get("zscore_lookback", 20)  # Default 20 periods
                    zscore_tf = plan.conditions.get("timeframe", "M15")  # Use plan timeframe
                    
                    # Fetch recent candles for z-score calculation
                    zscore_candles = _get_recent_candles(symbol_norm, timeframe=zscore_tf, count=max(30, zscore_lookback + 10))
                    zscore_candles = _normalize_candles(zscore_candles)
                    
                    if not zscore_candles or len(zscore_candles) < zscore_lookback:
                        logger.debug(f"Insufficient candles for z-score check on {symbol_norm} {zscore_tf}: {len(zscore_candles) if zscore_candles else 0} < {zscore_lookback}")
                        return False
                    
                    # Extract close prices for lookback period
                    closes = []
                    for i in range(min(zscore_lookback, len(zscore_candles))):
                        candle = zscore_candles[i]
                        close = candle['close'] if isinstance(candle, dict) else candle.close
                        closes.append(close)
                    
                    if len(closes) < zscore_lookback:
                        logger.debug(f"Insufficient close prices for z-score calculation: {len(closes)} < {zscore_lookback}")
                        return False
                    
                    # Calculate mean
                    mean_price = sum(closes) / len(closes)
                    if mean_price == 0:
                        logger.debug(f"Mean price is zero, cannot calculate z-score")
                        return False
                    
                    # Calculate standard deviation
                    variance = sum((price - mean_price) ** 2 for price in closes) / len(closes)
                    std_dev = variance ** 0.5
                    
                    if std_dev == 0:
                        logger.debug(f"Standard deviation is zero, cannot calculate z-score")
                        return False
                    
                    # Get current price (most recent candle close)
                    current_candle = zscore_candles[0]
                    current_price = current_candle['close'] if isinstance(current_candle, dict) else current_candle.close
                    
                    # Calculate z-score
                    z_score = (current_price - mean_price) / std_dev
                    
                    # Check if z-score meets threshold (absolute value)
                    abs_z_score = abs(z_score)
                    if abs_z_score < z_threshold:
                        logger.debug(f"Plan {plan.plan_id}: Z-score condition not met: |z_score|={abs_z_score:.2f} < threshold={z_threshold}")
                        return False
                    
                    # Direction check for mean reversion
                    # BUY: z_score < -threshold (price below mean, oversold)
                    # SELL: z_score > threshold (price above mean, overbought)
                    if plan.direction == "BUY":
                        if z_score >= -z_threshold:
                            logger.debug(f"Plan {plan.plan_id}: Z-score direction mismatch for BUY: z_score={z_score:.2f} >= -{z_threshold} (need oversold)")
                            return False
                    elif plan.direction == "SELL":
                        if z_score <= z_threshold:
                            logger.debug(f"Plan {plan.plan_id}: Z-score direction mismatch for SELL: z_score={z_score:.2f} <= {z_threshold} (need overbought)")
                            return False
                    
                    logger.info(f"Plan {plan.plan_id}: Z-score condition met on {zscore_tf}: z_score={z_score:.2f}, threshold={z_threshold}, mean={mean_price:.2f}, std_dev={std_dev:.2f}")
                    
                except Exception as e:
                    logger.error(f"Error checking z-score condition for {plan.plan_id}: {e}", exc_info=True)
                    return False
            
            # Check ATR stretch condition
            if plan.conditions.get("atr_stretch"):
                try:
                    # Get parameters from conditions
                    atr_multiple = plan.conditions.get("atr_multiple", 2.5)  # Default 2.5x ATR
                    atr_stretch_tf = plan.conditions.get("timeframe", "M15")  # Use plan timeframe
                    atr_period = plan.conditions.get("atr_period", 14)  # Default 14-period ATR
                    
                    # Fetch recent candles for ATR calculation
                    atr_stretch_candles = _get_recent_candles(symbol_norm, timeframe=atr_stretch_tf, count=30)
                    atr_stretch_candles = _normalize_candles(atr_stretch_candles)
                    
                    if not atr_stretch_candles or len(atr_stretch_candles) < atr_period + 5:
                        logger.debug(f"Insufficient candles for ATR stretch check on {symbol_norm} {atr_stretch_tf}: {len(atr_stretch_candles) if atr_stretch_candles else 0} < {atr_period + 5}")
                        return False
                    
                    # Calculate ATR inline (since _calculate_atr is defined later in the function)
                    if len(atr_stretch_candles) < atr_period + 1:
                        logger.debug(f"Insufficient candles for ATR calculation: {len(atr_stretch_candles)} < {atr_period + 1}")
                        return False
                    
                    tr_values = []
                    for i in range(1, min(len(atr_stretch_candles), atr_period + 10)):
                        c = atr_stretch_candles[i]
                        prev_c = atr_stretch_candles[i-1]
                        
                        h = c['high'] if isinstance(c, dict) else c.high
                        l = c['low'] if isinstance(c, dict) else c.low
                        prev_close = prev_c['close'] if isinstance(prev_c, dict) else prev_c.close
                        
                        tr1 = h - l
                        tr2 = abs(h - prev_close)
                        tr3 = abs(l - prev_close)
                        tr = max(tr1, tr2, tr3)
                        tr_values.append(tr)
                    
                    if len(tr_values) < atr_period:
                        logger.debug(f"Insufficient TR values for ATR calculation: {len(tr_values)} < {atr_period}")
                        return False
                    
                    # Calculate ATR as SMA of TR
                    atr_value = sum(tr_values[-atr_period:]) / atr_period
                    
                    if atr_value is None or atr_value == 0:
                        logger.debug(f"Could not calculate ATR for {symbol_norm} {atr_stretch_tf}")
                        return False
                    
                    # Get current price (most recent candle close)
                    current_candle = atr_stretch_candles[0]
                    current_price = current_candle['close'] if isinstance(current_candle, dict) else current_candle.close
                    
                    # Determine reference price (Priority: entry_price > swing high/low > VWAP/SMA)
                    reference_price = None
                    
                    # Priority 1: Use entry_price from plan
                    if plan.entry_price and plan.entry_price > 0:
                        reference_price = plan.entry_price
                    else:
                        # Priority 2: Use recent swing high/low (last 20 candles)
                        lookback_swing = min(20, len(atr_stretch_candles))
                        swing_highs = []
                        swing_lows = []
                        
                        for i in range(1, lookback_swing - 1):
                            candle = atr_stretch_candles[i]
                            high = candle['high'] if isinstance(candle, dict) else candle.high
                            low = candle['low'] if isinstance(candle, dict) else candle.low
                            
                            # Simple swing detection: higher than neighbors
                            if i > 0 and i < len(atr_stretch_candles) - 1:
                                prev_candle = atr_stretch_candles[i + 1]
                                next_candle = atr_stretch_candles[i - 1]
                                prev_high = prev_candle['high'] if isinstance(prev_candle, dict) else prev_candle.high
                                next_high = next_candle['high'] if isinstance(next_candle, dict) else next_candle.high
                                
                                if high > prev_high and high > next_high:
                                    swing_highs.append(high)
                                
                                prev_low = prev_candle['low'] if isinstance(prev_candle, dict) else prev_candle.low
                                next_low = next_candle['low'] if isinstance(next_candle, dict) else next_candle.low
                                
                                if low < prev_low and low < next_low:
                                    swing_lows.append(low)
                        
                        # Use most recent swing high/low based on direction
                        if plan.direction == "BUY" and swing_lows:
                            reference_price = min(swing_lows)  # Use swing low for BUY
                        elif plan.direction == "SELL" and swing_highs:
                            reference_price = max(swing_highs)  # Use swing high for SELL
                        else:
                            # Priority 3: Fallback to simple moving average
                            closes = [c['close'] if isinstance(c, dict) else c.close for c in atr_stretch_candles[:20]]
                            if closes:
                                reference_price = sum(closes) / len(closes)
                    
                    if reference_price is None or reference_price == 0:
                        logger.debug(f"Could not determine reference price for ATR stretch check on {symbol_norm}")
                        return False
                    
                    # Calculate distance from reference price
                    distance = abs(current_price - reference_price)
                    
                    # Calculate stretch ratio (distance / ATR)
                    stretch_ratio = distance / atr_value if atr_value > 0 else 0
                    
                    # Check if stretch meets threshold
                    if stretch_ratio < atr_multiple:
                        logger.debug(f"Plan {plan.plan_id}: ATR stretch condition not met: stretch={stretch_ratio:.2f}x < threshold={atr_multiple}x ATR")
                        return False
                    
                    # Direction check: BUY should be stretched below reference, SELL should be stretched above
                    if plan.direction == "BUY":
                        if current_price >= reference_price:
                            logger.debug(f"Plan {plan.plan_id}: ATR stretch direction mismatch for BUY: current_price={current_price:.2f} >= reference={reference_price:.2f}")
                            return False
                    elif plan.direction == "SELL":
                        if current_price <= reference_price:
                            logger.debug(f"Plan {plan.plan_id}: ATR stretch direction mismatch for SELL: current_price={current_price:.2f} <= reference={reference_price:.2f}")
                            return False
                    
                    logger.info(f"Plan {plan.plan_id}: ATR stretch condition met on {atr_stretch_tf}: stretch={stretch_ratio:.2f}x ATR (threshold={atr_multiple}x), ATR={atr_value:.2f}, distance={distance:.2f}, reference={reference_price:.2f}")
                    
                except Exception as e:
                    logger.error(f"Error checking ATR stretch condition for {plan.plan_id}: {e}", exc_info=True)
                    return False
            
            # Check inside bar condition
            if plan.conditions.get("inside_bar"):
                try:
                    # Get timeframe from conditions or default to M15
                    ib_tf = plan.conditions.get("timeframe", "M15")
                    ib_candles = _get_recent_candles(symbol_norm, timeframe=ib_tf, count=10)
                    ib_candles = _normalize_candles(ib_candles)
                    
                    if not ib_candles or len(ib_candles) < 3:
                        logger.debug(f"Insufficient candles for inside bar check on {symbol_norm}")
                        return False
                    
                    # Check if current candle is inside previous candle
                    current = ib_candles[0]  # Newest first
                    mother = ib_candles[1]
                    
                    current_high = current['high'] if isinstance(current, dict) else current.high
                    current_low = current['low'] if isinstance(current, dict) else current.low
                    mother_high = mother['high'] if isinstance(mother, dict) else mother.high
                    mother_low = mother['low'] if isinstance(mother, dict) else mother.low
                    
                    is_inside = (current_high < mother_high and current_low > mother_low)
                    
                    if not is_inside:
                        logger.debug(f"Inside bar condition not met: current candle not inside mother bar")
                        return False
                    
                    logger.info(f"Inside bar condition met: compression detected")
                except Exception as e:
                    logger.error(f"Error checking inside bar condition: {e}", exc_info=True)
                    return False
            
            # ============================================================================
            # Phase III: Volatility Pattern Recognition Condition Checks
            # ============================================================================
            # Check volatility pattern conditions (fractal expansion, IV collapse, recoil, RMAG)
            try:
                from infra.volatility_pattern_recognition import VolatilityPatternRecognizer
                
                # Initialize recognizer (singleton pattern - reuse if exists)
                if not hasattr(self, '_volatility_pattern_recognizer'):
                    self._volatility_pattern_recognizer = VolatilityPatternRecognizer(cache_ttl_seconds=120)
                
                recognizer = self._volatility_pattern_recognizer
                
                # Check consecutive inside bars
                if plan.conditions.get("consecutive_inside_bars") is not None:
                    min_count = plan.conditions.get("consecutive_inside_bars", 3)
                    pattern_tf = plan.conditions.get("timeframe", "M15")
                    
                    candles = _get_recent_candles(symbol_norm, timeframe=pattern_tf, count=min_count + 5)
                    candles = _normalize_candles(candles)
                    
                    if candles and len(candles) >= min_count + 1:
                        pattern_result = recognizer.detect_consecutive_inside_bars(candles, min_count=min_count)
                        if not pattern_result or not pattern_result.get("pattern_detected"):
                            logger.debug(f"Plan {plan.plan_id}: Consecutive inside bars pattern not detected ({min_count} required)")
                            return False
                    else:
                        logger.debug(f"Plan {plan.plan_id}: Insufficient candles for consecutive inside bars check")
                        return False
                
                # Check volatility fractal expansion
                if plan.conditions.get("volatility_fractal_expansion"):
                    pattern_tf = plan.conditions.get("timeframe", "M15")
                    
                    candles = _get_recent_candles(symbol_norm, timeframe=pattern_tf, count=20)
                    candles = _normalize_candles(candles)
                    
                    if candles and len(candles) >= 10:
                        # Calculate BB widths and ATR values
                        closes = [c.get('close') if isinstance(c, dict) else c.close for c in candles[:20]]
                        highs = [c.get('high') if isinstance(c, dict) else c.high for c in candles[:20]]
                        lows = [c.get('low') if isinstance(c, dict) else c.low for c in candles[:20]]
                        
                        # Calculate BB widths (simplified - using std dev)
                        sma = sum(closes) / len(closes)
                        std_dev = (sum((c - sma) ** 2 for c in closes) / len(closes)) ** 0.5
                        bb_widths = [std_dev * 2] * len(candles)  # Simplified - would need proper BB calculation
                        
                        # Calculate ATR values
                        atr_values = []
                        for i in range(len(candles)):
                            if i < len(candles) - 1:
                                tr = max(
                                    highs[i] - lows[i],
                                    abs(highs[i] - closes[i+1]),
                                    abs(lows[i] - closes[i+1])
                                )
                                atr_values.append(tr)
                            else:
                                atr_values.append(atr_values[-1] if atr_values else 0)
                        
                        expansion_result = recognizer.detect_volatility_fractal_expansion(
                            candles, bb_widths, atr_values
                        )
                        if not expansion_result or not expansion_result.get("volatility_fractal_expansion"):
                            logger.debug(f"Plan {plan.plan_id}: Volatility fractal expansion not detected")
                            return False
                    else:
                        logger.debug(f"Plan {plan.plan_id}: Insufficient candles for volatility fractal expansion check")
                        return False
                
                # Check IV collapse
                if plan.conditions.get("iv_collapse_detected"):
                    pattern_tf = plan.conditions.get("timeframe", "M15")
                    
                    candles = _get_recent_candles(symbol_norm, timeframe=pattern_tf, count=20)
                    candles = _normalize_candles(candles)
                    
                    if candles and len(candles) >= 15:
                        # Calculate ATR values
                        highs = [c.get('high') if isinstance(c, dict) else c.high for c in candles]
                        lows = [c.get('low') if isinstance(c, dict) else c.low for c in candles]
                        closes = [c.get('close') if isinstance(c, dict) else c.close for c in candles]
                        
                        atr_values = []
                        for i in range(len(candles)):
                            if i < len(candles) - 1:
                                tr = max(
                                    highs[i] - lows[i],
                                    abs(highs[i] - closes[i+1]),
                                    abs(lows[i] - closes[i+1])
                                )
                                atr_values.append(tr)
                            else:
                                atr_values.append(atr_values[-1] if atr_values else 0)
                        
                        collapse_result = recognizer.detect_iv_collapse(atr_values)
                        if not collapse_result or not collapse_result.get("iv_collapse_detected"):
                            logger.debug(f"Plan {plan.plan_id}: IV collapse not detected")
                            return False
                    else:
                        logger.debug(f"Plan {plan.plan_id}: Insufficient candles for IV collapse check")
                        return False
                
                # Check volatility recoil
                if plan.conditions.get("volatility_recoil_confirmed"):
                    pattern_tf = plan.conditions.get("timeframe", "M15")
                    
                    candles = _get_recent_candles(symbol_norm, timeframe=pattern_tf, count=30)
                    candles = _normalize_candles(candles)
                    
                    if candles and len(candles) >= 20:
                        # Calculate ATR values
                        highs = [c.get('high') if isinstance(c, dict) else c.high for c in candles]
                        lows = [c.get('low') if isinstance(c, dict) else c.low for c in candles]
                        closes = [c.get('close') if isinstance(c, dict) else c.close for c in candles]
                        
                        atr_values = []
                        for i in range(len(candles)):
                            if i < len(candles) - 1:
                                tr = max(
                                    highs[i] - lows[i],
                                    abs(highs[i] - closes[i+1]),
                                    abs(lows[i] - closes[i+1])
                                )
                                atr_values.append(tr)
                            else:
                                atr_values.append(atr_values[-1] if atr_values else 0)
                        
                        recoil_result = recognizer.detect_volatility_recoil(atr_values)
                        if not recoil_result or not recoil_result.get("volatility_recoil_confirmed"):
                            logger.debug(f"Plan {plan.plan_id}: Volatility recoil not confirmed")
                            return False
                    else:
                        logger.debug(f"Plan {plan.plan_id}: Insufficient candles for volatility recoil check")
                        return False
                
                # Check RMAG ATR ratio
                if plan.conditions.get("rmag_atr_ratio") is not None:
                    rmag_threshold = plan.conditions.get("rmag_atr_ratio", 5.0)
                    pattern_tf = plan.conditions.get("timeframe", "M15")
                    
                    # Get RMAG from advanced features
                    try:
                        from infra.feature_builder_advanced import build_features_advanced
                        from infra.indicator_bridge import IndicatorBridge
                        
                        if self.mt5_service:
                            indicator_bridge = IndicatorBridge()
                            advanced_features = build_features_advanced(
                                symbol=symbol_norm,
                                mt5svc=self.mt5_service,
                                bridge=indicator_bridge,
                                timeframes=[pattern_tf]
                            )
                            
                            if advanced_features and advanced_features.get("features"):
                                tf_features = advanced_features["features"].get(pattern_tf, {})
                                rmag_dict = tf_features.get("rmag", {})
                                
                                if isinstance(rmag_dict, dict):
                                    rmag_value = rmag_dict.get("ema200_atr", 0.0) or rmag_dict.get("vwap_atr", 0.0) or 0.0
                                else:
                                    rmag_value = float(rmag_dict) if rmag_dict else 0.0
                                
                                # Get ATR
                                candles = _get_recent_candles(symbol_norm, timeframe=pattern_tf, count=20)
                                candles = _normalize_candles(candles)
                                
                                if candles and len(candles) >= 14:
                                    atr_value = _calculate_atr_simple(candles)
                                    
                                    if atr_value and atr_value > 0:
                                        rmag_ratio = recognizer.calculate_rmag_atr_ratio(rmag_value, atr_value)
                                        
                                        if rmag_ratio is None or rmag_ratio < rmag_threshold:
                                            logger.debug(f"Plan {plan.plan_id}: RMAG ATR ratio {rmag_ratio:.2f} < threshold {rmag_threshold:.2f}")
                                            return False
                                    else:
                                        logger.debug(f"Plan {plan.plan_id}: ATR calculation failed for RMAG ratio")
                                        return False
                                else:
                                    logger.debug(f"Plan {plan.plan_id}: Insufficient candles for RMAG ATR ratio check")
                                    return False
                            else:
                                logger.debug(f"Plan {plan.plan_id}: Advanced features unavailable for RMAG ATR ratio")
                                return False
                        else:
                            logger.debug(f"Plan {plan.plan_id}: MT5 service unavailable for RMAG ATR ratio")
                            return False
                    except Exception as e:
                        logger.error(f"Error getting RMAG for {plan.plan_id}: {e}", exc_info=True)
                        return False
                
                # Check BB width rising
                if plan.conditions.get("bb_width_rising"):
                    pattern_tf = plan.conditions.get("timeframe", "M15")
                    
                    candles = _get_recent_candles(symbol_norm, timeframe=pattern_tf, count=20)
                    candles = _normalize_candles(candles)
                    
                    if candles and len(candles) >= 10:
                        # Calculate BB widths (simplified)
                        closes = [c.get('close') if isinstance(c, dict) else c.close for c in candles[:20]]
                        sma = sum(closes) / len(closes)
                        std_dev = (sum((c - sma) ** 2 for c in closes) / len(closes)) ** 0.5
                        bb_widths = [std_dev * 2] * len(candles)  # Simplified
                        
                        trend_result = recognizer.calculate_bb_width_trend(bb_widths)
                        if not trend_result or not trend_result.get("bb_width_rising"):
                            logger.debug(f"Plan {plan.plan_id}: BB width not rising")
                            return False
                    else:
                        logger.debug(f"Plan {plan.plan_id}: Insufficient candles for BB width trend check")
                        return False
                
                # Check impulse continuation confirmed
                if plan.conditions.get("impulse_continuation_confirmed"):
                    # Requires: RMAG >5 ATR AND BB width rising for 3+ bars
                    pattern_tf = plan.conditions.get("timeframe", "M15")
                    
                    # Check RMAG ATR ratio (reuse logic above)
                    rmag_threshold = 5.0
                    # ... (would reuse RMAG check logic)
                    
                    # Check BB width rising (reuse logic above)
                    # ... (would reuse BB width check logic)
                    
                    # For now, just check if both conditions would pass
                    # In production, would combine both checks
                    logger.debug(f"Plan {plan.plan_id}: Impulse continuation check (requires both RMAG and BB width)")
                    # This is a composite condition - would need both checks to pass
                    
            except ImportError:
                # Volatility pattern recognizer not available
                if any([
                    plan.conditions.get("consecutive_inside_bars") is not None,
                    plan.conditions.get("volatility_fractal_expansion"),
                    plan.conditions.get("iv_collapse_detected"),
                    plan.conditions.get("volatility_recoil_confirmed"),
                    plan.conditions.get("rmag_atr_ratio") is not None,
                    plan.conditions.get("bb_width_rising"),
                    plan.conditions.get("impulse_continuation_confirmed")
                ]):
                    logger.debug(f"Plan {plan.plan_id}: Volatility pattern recognizer not available")
                    return False
            except Exception as e:
                logger.error(f"Error checking volatility pattern conditions for {plan.plan_id}: {e}", exc_info=True)
                return False
            
            # Check equal highs/lows condition
            if plan.conditions.get("equal_highs") or plan.conditions.get("equal_lows"):
                try:
                    # Get timeframe from conditions or default to H1
                    eq_tf = plan.conditions.get("timeframe", "H1")
                    eq_candles = _get_recent_candles(symbol_norm, timeframe=eq_tf, count=50)
                    eq_candles = _normalize_candles(eq_candles)
                    
                    if not eq_candles or len(eq_candles) < 20:
                        logger.debug(f"Insufficient candles for equal highs/lows check on {symbol_norm}")
                        return False
                    
                    # Get highs and lows
                    highs = [c['high'] if isinstance(c, dict) else c.high for c in eq_candles[:30]]
                    lows = [c['low'] if isinstance(c, dict) else c.low for c in eq_candles[:30]]
                    
                    tolerance_pct = plan.conditions.get("equal_tolerance_pct", 0.1)
                    
                    # Check for equal highs
                    if plan.conditions.get("equal_highs"):
                        found_equal = False
                        for i, h1 in enumerate(highs):
                            for j, h2 in enumerate(highs[i+3:], start=i+3):  # At least 3 candles apart
                                tolerance = h1 * tolerance_pct / 100
                                if abs(h1 - h2) < tolerance:
                                    found_equal = True
                                    break
                            if found_equal:
                                break
                        
                        if not found_equal:
                            logger.debug(f"Equal highs condition not met: no matching highs found")
                            return False
                        logger.info(f"Equal highs condition met: liquidity zone detected")
                    
                    # Check for equal lows
                    if plan.conditions.get("equal_lows"):
                        found_equal = False
                        for i, l1 in enumerate(lows):
                            for j, l2 in enumerate(lows[i+3:], start=i+3):  # At least 3 candles apart
                                tolerance = l1 * tolerance_pct / 100
                                if abs(l1 - l2) < tolerance:
                                    found_equal = True
                                    break
                            if found_equal:
                                break
                        
                        if not found_equal:
                            logger.debug(f"Equal lows condition not met: no matching lows found")
                            return False
                        logger.info(f"Equal lows condition met: liquidity zone detected")
                        
                except Exception as e:
                    logger.error(f"Error checking equal highs/lows condition: {e}", exc_info=True)
                    return False
            
            # Check RSI divergence conditions
            if plan.conditions.get("rsi_div_bull") or plan.conditions.get("rsi_div_bear"):
                try:
                    # Get timeframe from conditions or default to M15
                    rsi_tf = plan.conditions.get("timeframe", "M15")
                    rsi_candles = _get_recent_candles(symbol_norm, timeframe=rsi_tf, count=50)
                    rsi_candles = _normalize_candles(rsi_candles)
                    
                    if not rsi_candles or len(rsi_candles) < 20:
                        logger.debug(f"Insufficient candles for RSI divergence check on {symbol_norm}")
                        return False
                    
                    # Calculate RSI
                    gains = []
                    losses = []
                    for i in range(1, min(15, len(rsi_candles))):
                        c1 = rsi_candles[i-1]
                        c2 = rsi_candles[i]
                        close1 = c1['close'] if isinstance(c1, dict) else c1.close
                        close2 = c2['close'] if isinstance(c2, dict) else c2.close
                        change = close1 - close2  # Newest first
                        if change > 0:
                            gains.append(change)
                            losses.append(0)
                        else:
                            gains.append(0)
                            losses.append(abs(change))
                    
                    if not gains or not losses or sum(losses) == 0:
                        logger.debug(f"Could not calculate RSI for {symbol_norm}")
                        return False
                    
                    avg_gain = sum(gains) / len(gains)
                    avg_loss = sum(losses) / len(losses)
                    rs = avg_gain / avg_loss if avg_loss > 0 else 0
                    rsi = 100 - (100 / (1 + rs)) if rs > 0 else 50
                    
                    # Check price trend
                    c0 = rsi_candles[0]
                    c10 = rsi_candles[10] if len(rsi_candles) > 10 else rsi_candles[-1]
                    price0 = c0['close'] if isinstance(c0, dict) else c0.close
                    price10 = c10['close'] if isinstance(c10, dict) else c10.close
                    price_trend = price0 - price10
                    
                    # Check bullish divergence
                    if plan.conditions.get("rsi_div_bull"):
                        # Bullish divergence: price making lower lows, RSI making higher lows
                        if price_trend >= 0 or rsi <= 30 or rsi >= 50:
                            logger.debug(f"RSI bullish divergence not met: price_trend={price_trend:.2f}, RSI={rsi:.1f}")
                            return False
                        logger.info(f"RSI bullish divergence condition met: RSI={rsi:.1f}, price_trend={price_trend:.2f}")
                    
                    # Check bearish divergence
                    if plan.conditions.get("rsi_div_bear"):
                        # Bearish divergence: price making higher highs, RSI making lower highs
                        if price_trend <= 0 or rsi >= 70 or rsi <= 50:
                            logger.debug(f"RSI bearish divergence not met: price_trend={price_trend:.2f}, RSI={rsi:.1f}")
                            return False
                        logger.info(f"RSI bearish divergence condition met: RSI={rsi:.1f}, price_trend={price_trend:.2f}")
                        
                except Exception as e:
                    logger.error(f"Error checking RSI divergence condition: {e}", exc_info=True)
                    return False
            
            # Check volatility state condition
            if "volatility_state" in plan.conditions:
                required_state = plan.conditions.get("volatility_state")  # "CONTRACTING", "EXPANDING", "STABLE"
                
                try:
                    # Get M1 data for volatility state
                    if self.m1_analyzer and self.m1_data_fetcher:
                        m1_candles = self.m1_data_fetcher.fetch_m1_data(symbol_norm, count=200)
                        if m1_candles and len(m1_candles) >= 50:
                            m1_analysis = self.m1_analyzer.analyze_microstructure(
                                symbol=symbol_norm,
                                candles=m1_candles,
                                current_price=current_price
                            )
                            
                            if m1_analysis and m1_analysis.get('available'):
                                volatility_state = m1_analysis.get('volatility_state', 'UNKNOWN')
                                
                                if volatility_state.upper() != required_state.upper():
                                    logger.debug(f"Volatility state mismatch: {volatility_state} != {required_state}")
                                    return False
                                
                                logger.info(f"Volatility state condition met: {volatility_state}")
                            else:
                                logger.warning(f"M1 analysis not available for volatility state check")
                                return False
                        else:
                            logger.warning(f"Insufficient M1 data for volatility state check")
                            return False
                    else:
                        logger.warning(f"M1 components not available for volatility state check")
                        return False
                except Exception as e:
                    logger.error(f"Error checking volatility state condition: {e}", exc_info=True)
                    return False
            
            # ============================================================================
            # Phase 3.1: Session-Based Volume/Liquidity Checks
            # ============================================================================
            # Check session-based conditions
            # NOTE: Use time-based check instead of API call for performance
            # For XAU, default to True (block Asian session by default) - Trade 178151939 was in Asian session
            # BUT: Allow certain strategies during Asian session (range fade, mean reversion, FVG retracement, etc.)
            if plan.conditions.get("require_active_session", "XAU" in symbol_norm):  # Default True for XAU
                try:
                    from infra.session_helpers import SessionHelpers
                    
                    # Use existing session helper (synchronous, no API call)
                    session_name = SessionHelpers.get_current_session()
                    
                    # Strategies that ARE appropriate for Asian session (low liquidity, range-bound markets)
                    asian_allowed_strategies = [
                        "range_scalp", "range_fade", "mean_reversion",
                        "fvg_retracement", "premium_discount_array",
                        "order_block_rejection"  # At range edges
                    ]
                    
                    # Get strategy type from plan (check both strategy_type and plan_type for compatibility)
                    strategy_type = (
                        plan.conditions.get("strategy_type") or 
                        plan.conditions.get("plan_type") or 
                        plan.strategy_type or
                        getattr(plan, 'plan_type', None)
                    )
                    strategy_type_lower = str(strategy_type).lower() if strategy_type else ""
                    
                    # Check if this is an Asian-session-appropriate strategy
                    is_asian_appropriate = any(
                        allowed in strategy_type_lower 
                        for allowed in asian_allowed_strategies
                    )
                    
                    # BTC: Require US/London overlap (14:00-18:00 UTC)
                    # BUT: Allow range/mean reversion strategies in Asian session
                    if "BTC" in symbol_norm:
                        if session_name == "ASIAN":
                            if not is_asian_appropriate:
                                logger.debug(
                                    f"Plan {plan.plan_id}: BTC plan in ASIAN session (low liquidity) - "
                                    f"strategy '{strategy_type}' not appropriate for Asian session"
                                )
                                return False
                            else:
                                logger.debug(
                                    f"Plan {plan.plan_id}: BTC plan in ASIAN session - "
                                    f"strategy '{strategy_type}' is appropriate for Asian session (range-bound)"
                                )
                    elif "XAU" in symbol_norm:
                        # XAU: Block Asian session (00:00-08:00 UTC) - low liquidity, more slippage
                        # BUT: Allow range/mean reversion strategies in Asian session
                        if session_name == "ASIAN":
                            if not is_asian_appropriate:
                                logger.warning(
                                    f"Plan {plan.plan_id}: XAU plan in ASIAN session (low liquidity, high slippage risk) - "
                                    f"strategy '{strategy_type}' not appropriate for Asian session - BLOCKED"
                                )
                                return False
                            else:
                                logger.info(
                                    f"Plan {plan.plan_id}: XAU plan in ASIAN session - "
                                    f"strategy '{strategy_type}' is appropriate for Asian session (range-bound) - ALLOWED"
                                )
                except Exception as e:
                    logger.debug(f"Error checking session for {plan.plan_id}: {e}")
                    # Continue if check fails (non-critical)
            
            # ============================================================================
            # End Phase 3.1: Session-Based Checks
            # ============================================================================
            
            # Check time conditions
            if "time_after" in plan.conditions:
                target_time = datetime.fromisoformat(plan.conditions["time_after"].replace('Z', '+00:00'))
                if target_time.tzinfo is None:
                    target_time = target_time.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < target_time:
                    return False
                    
            if "time_before" in plan.conditions:
                target_time = datetime.fromisoformat(plan.conditions["time_before"].replace('Z', '+00:00'))
                if target_time.tzinfo is None:
                    target_time = target_time.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > target_time:
                    return False
            
            # Check volatility decay condition (session-based)
            if plan.conditions.get("volatility_decay"):
                try:
                    # CRITICAL: Check session FIRST (performance optimization)
                    from infra.session_helpers import SessionHelpers
                    required_session = plan.conditions.get("session")
                    if required_session:
                        current_session = SessionHelpers.get_current_session()
                        if current_session != required_session:
                            logger.debug(f"Plan {plan.plan_id}: volatility_decay requires session '{required_session}', current is '{current_session}'")
                            return False
                    
                    # Get parameters
                    decay_threshold = plan.conditions.get("decay_threshold", 0.8)  # Default 0.8 = 20% decrease
                    decay_window = plan.conditions.get("decay_window", 5)  # Default 5 candles
                    volatility_decay_tf = plan.conditions.get("timeframe", "M15")
                    
                    # Fetch candles for ATR calculation
                    volatility_decay_candles = _get_recent_candles(symbol_norm, timeframe=volatility_decay_tf, count=decay_window * 3)
                    volatility_decay_candles = _normalize_candles(volatility_decay_candles)
                    
                    if not volatility_decay_candles or len(volatility_decay_candles) < decay_window * 2:
                        logger.debug(f"Insufficient candles for volatility decay check on {symbol_norm} {volatility_decay_tf}: {len(volatility_decay_candles) if volatility_decay_candles else 0} < {decay_window * 2}")
                        return False
                    
                    # Calculate ATR for recent period (last decay_window candles)
                    # Use inline ATR calculation (since _calculate_atr is defined later)
                    recent_candles = volatility_decay_candles[:decay_window]
                    if len(recent_candles) < 14:
                        # Use simple ATR if not enough candles
                        recent_tr_values = []
                        for i in range(1, len(recent_candles)):
                            c = recent_candles[i]
                            prev_c = recent_candles[i-1]
                            h = c['high'] if isinstance(c, dict) else c.high
                            l = c['low'] if isinstance(c, dict) else c.low
                            prev_close = prev_c['close'] if isinstance(prev_c, dict) else prev_c.close
                            tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
                            recent_tr_values.append(tr)
                        recent_atr = sum(recent_tr_values) / len(recent_tr_values) if recent_tr_values else None
                    else:
                        # Full ATR calculation
                        recent_tr_values = []
                        for i in range(1, min(len(recent_candles), 15)):
                            c = recent_candles[i]
                            prev_c = recent_candles[i-1]
                            h = c['high'] if isinstance(c, dict) else c.high
                            l = c['low'] if isinstance(c, dict) else c.low
                            prev_close = prev_c['close'] if isinstance(prev_c, dict) else prev_c.close
                            tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
                            recent_tr_values.append(tr)
                        if len(recent_tr_values) >= 14:
                            recent_atr = sum(recent_tr_values[-14:]) / 14
                        else:
                            recent_atr = sum(recent_tr_values) / len(recent_tr_values) if recent_tr_values else None
                    
                    if recent_atr is None or recent_atr == 0:
                        logger.debug(f"Could not calculate recent ATR for volatility decay check")
                        return False
                    
                    # Calculate ATR for earlier period (decay_window to decay_window*2 candles ago)
                    earlier_candles = volatility_decay_candles[decay_window:decay_window * 2]
                    if len(earlier_candles) < 14:
                        # Use simple ATR if not enough candles
                        earlier_tr_values = []
                        for i in range(1, len(earlier_candles)):
                            c = earlier_candles[i]
                            prev_c = earlier_candles[i-1]
                            h = c['high'] if isinstance(c, dict) else c.high
                            l = c['low'] if isinstance(c, dict) else c.low
                            prev_close = prev_c['close'] if isinstance(prev_c, dict) else prev_c.close
                            tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
                            earlier_tr_values.append(tr)
                        earlier_atr = sum(earlier_tr_values) / len(earlier_tr_values) if earlier_tr_values else None
                    else:
                        # Full ATR calculation
                        earlier_tr_values = []
                        for i in range(1, min(len(earlier_candles), 15)):
                            c = earlier_candles[i]
                            prev_c = earlier_candles[i-1]
                            h = c['high'] if isinstance(c, dict) else c.high
                            l = c['low'] if isinstance(c, dict) else c.low
                            prev_close = prev_c['close'] if isinstance(prev_c, dict) else prev_c.close
                            tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
                            earlier_tr_values.append(tr)
                        if len(earlier_tr_values) >= 14:
                            earlier_atr = sum(earlier_tr_values[-14:]) / 14
                        else:
                            earlier_atr = sum(earlier_tr_values) / len(earlier_tr_values) if earlier_tr_values else None
                    
                    if earlier_atr is None or earlier_atr == 0:
                        logger.debug(f"Could not calculate earlier ATR for volatility decay check")
                        return False
                    
                    # Check if recent ATR < earlier ATR * threshold (decay detected)
                    decay_ratio = recent_atr / earlier_atr if earlier_atr > 0 else 1.0
                    
                    if decay_ratio >= decay_threshold:
                        logger.debug(f"Plan {plan.plan_id}: Volatility decay not detected: recent_ATR={recent_atr:.2f}, earlier_ATR={earlier_atr:.2f}, ratio={decay_ratio:.2f} >= threshold={decay_threshold:.2f}")
                        return False
                    
                    logger.info(f"Plan {plan.plan_id}: Volatility decay condition met on {volatility_decay_tf}: recent_ATR={recent_atr:.2f}, earlier_ATR={earlier_atr:.2f}, decay_ratio={decay_ratio:.2f} < threshold={decay_threshold:.2f}")
                    
                except Exception as e:
                    logger.error(f"Error checking volatility decay condition for {plan.plan_id}: {e}", exc_info=True)
                    return False
            
            # Check momentum follow condition (session-based)
            if plan.conditions.get("momentum_follow"):
                try:
                    # CRITICAL: Check session FIRST (performance optimization)
                    from infra.session_helpers import SessionHelpers
                    required_session = plan.conditions.get("session")
                    if required_session:
                        current_session = SessionHelpers.get_current_session()
                        if current_session != required_session:
                            logger.debug(f"Plan {plan.plan_id}: momentum_follow requires session '{required_session}', current is '{current_session}'")
                            return False
                    
                    # Get parameters
                    momentum_periods = plan.conditions.get("momentum_periods", 5)  # Default 5 periods
                    momentum_threshold = plan.conditions.get("momentum_threshold", 0.5)  # Default 0.5%
                    momentum_tf = plan.conditions.get("timeframe", "M15")
                    
                    # Fetch candles for momentum calculation
                    momentum_candles = _get_recent_candles(symbol_norm, timeframe=momentum_tf, count=momentum_periods + 5)
                    momentum_candles = _normalize_candles(momentum_candles)
                    
                    if not momentum_candles or len(momentum_candles) < momentum_periods + 1:
                        logger.debug(f"Insufficient candles for momentum follow check on {symbol_norm} {momentum_tf}: {len(momentum_candles) if momentum_candles else 0} < {momentum_periods + 1}")
                        return False
                    
                    # Calculate momentum for each period (price change over each candle)
                    momentum_values = []
                    for i in range(momentum_periods):
                        if i + 1 >= len(momentum_candles):
                            break
                        current_candle = momentum_candles[i]
                        prev_candle = momentum_candles[i + 1]
                        
                        current_close = current_candle['close'] if isinstance(current_candle, dict) else current_candle.close
                        prev_close = prev_candle['close'] if isinstance(prev_candle, dict) else prev_candle.close
                        
                        if prev_close > 0:
                            momentum_pct = ((current_close - prev_close) / prev_close) * 100
                            momentum_values.append(momentum_pct)
                    
                    if len(momentum_values) < momentum_periods:
                        logger.debug(f"Insufficient momentum values calculated: {len(momentum_values)} < {momentum_periods}")
                        return False
                    
                    # Check if all momentum values are in same direction
                    # For BUY: all should be positive (or at least majority)
                    # For SELL: all should be negative (or at least majority)
                    if plan.direction == "BUY":
                        positive_count = sum(1 for m in momentum_values if m > 0)
                        if positive_count < len(momentum_values) * 0.6:  # At least 60% positive
                            logger.debug(f"Plan {plan.plan_id}: Momentum not consistently bullish: {positive_count}/{len(momentum_values)} positive")
                            return False
                        
                        # Check if average momentum meets threshold
                        avg_momentum = sum(momentum_values) / len(momentum_values)
                        if avg_momentum < momentum_threshold:
                            logger.debug(f"Plan {plan.plan_id}: Average momentum {avg_momentum:.2f}% < threshold {momentum_threshold:.2f}%")
                            return False
                    elif plan.direction == "SELL":
                        negative_count = sum(1 for m in momentum_values if m < 0)
                        if negative_count < len(momentum_values) * 0.6:  # At least 60% negative
                            logger.debug(f"Plan {plan.plan_id}: Momentum not consistently bearish: {negative_count}/{len(momentum_values)} negative")
                            return False
                        
                        # Check if average momentum magnitude meets threshold (use absolute value)
                        avg_momentum = abs(sum(momentum_values) / len(momentum_values))
                        if avg_momentum < momentum_threshold:
                            logger.debug(f"Plan {plan.plan_id}: Average momentum magnitude {avg_momentum:.2f}% < threshold {momentum_threshold:.2f}%")
                            return False
                    
                    # Optional: Check if momentum is strengthening (increasing magnitude)
                    # Compare first half vs second half of momentum values
                    mid_point = len(momentum_values) // 2
                    first_half_avg = abs(sum(momentum_values[mid_point:]) / len(momentum_values[mid_point:]))
                    second_half_avg = abs(sum(momentum_values[:mid_point]) / len(momentum_values[:mid_point])) if mid_point > 0 else first_half_avg
                    
                    if second_half_avg < first_half_avg * 0.9:  # Momentum weakening (10% decrease)
                        logger.debug(f"Plan {plan.plan_id}: Momentum weakening: recent={second_half_avg:.2f}% < earlier={first_half_avg:.2f}%")
                        return False
                    
                    avg_momentum = sum(momentum_values) / len(momentum_values)
                    logger.info(f"Plan {plan.plan_id}: Momentum follow condition met on {momentum_tf}: avg_momentum={avg_momentum:.2f}%, periods={momentum_periods}")
                    
                except Exception as e:
                    logger.error(f"Error checking momentum follow condition for {plan.plan_id}: {e}", exc_info=True)
                    return False
            
            # Check fakeout sweep condition (session-based)
            if plan.conditions.get("fakeout_sweep"):
                try:
                    # CRITICAL: Check session FIRST (performance optimization)
                    from infra.session_helpers import SessionHelpers
                    required_session = plan.conditions.get("session")
                    if required_session:
                        current_session = SessionHelpers.get_current_session()
                        if current_session != required_session:
                            logger.debug(f"Plan {plan.plan_id}: fakeout_sweep requires session '{required_session}', current is '{current_session}'")
                            return False
                    
                    # Get parameters
                    fakeout_reversal_candles = plan.conditions.get("fakeout_reversal_candles", 5)  # Default 5 candles
                    fakeout_level = plan.conditions.get("fakeout_level")  # Optional specific level
                    fakeout_tf = plan.conditions.get("timeframe", "M15")
                    
                    # Fetch candles for fakeout detection
                    fakeout_candles = _get_recent_candles(symbol_norm, timeframe=fakeout_tf, count=30)
                    fakeout_candles = _normalize_candles(fakeout_candles)
                    
                    if not fakeout_candles or len(fakeout_candles) < 15:
                        logger.debug(f"Insufficient candles for fakeout sweep check on {symbol_norm} {fakeout_tf}: {len(fakeout_candles) if fakeout_candles else 0} < 15")
                        return False
                    
                    # Identify key level (swing high/low or use provided level)
                    key_level = None
                    if fakeout_level:
                        key_level = float(fakeout_level)
                    else:
                        # Find recent swing high/low (last 20 candles, excluding last 3)
                        lookback_candles = fakeout_candles[3:23] if len(fakeout_candles) >= 23 else fakeout_candles[3:]
                        if len(lookback_candles) < 5:
                            logger.debug(f"Insufficient lookback candles for swing identification")
                            return False
                        
                        highs = [c['high'] if isinstance(c, dict) else c.high for c in lookback_candles]
                        lows = [c['low'] if isinstance(c, dict) else c.low for c in lookback_candles]
                        
                        if plan.direction == "BUY":
                            # For BUY: look for fakeout of swing low (break below then reverse up)
                            key_level = min(lows)
                        else:  # SELL
                            # For SELL: look for fakeout of swing high (break above then reverse down)
                            key_level = max(highs)
                    
                    if key_level is None or key_level == 0:
                        logger.debug(f"Could not identify key level for fakeout sweep")
                        return False
                    
                    # Scan recent candles (last fakeout_reversal_candles + 2) for breakout and reversal
                    recent_candles = fakeout_candles[:fakeout_reversal_candles + 2]
                    
                    breakout_found = False
                    breakout_candle_idx = None
                    breakout_direction = None
                    
                    # Detect breakout
                    for i in range(len(recent_candles) - 1):
                        candle = recent_candles[i]
                        candle_high = candle['high'] if isinstance(candle, dict) else candle.high
                        candle_low = candle['low'] if isinstance(candle, dict) else candle.low
                        
                        if plan.direction == "BUY":
                            # For BUY: look for break below key level (swing low)
                            if candle_low < key_level:
                                breakout_found = True
                                breakout_candle_idx = i
                                breakout_direction = "below"
                                break
                        else:  # SELL
                            # For SELL: look for break above key level (swing high)
                            if candle_high > key_level:
                                breakout_found = True
                                breakout_candle_idx = i
                                breakout_direction = "above"
                                break
                    
                    if not breakout_found:
                        logger.debug(f"Plan {plan.plan_id}: No breakout detected for fakeout sweep (key_level={key_level:.2f})")
                        return False
                    
                    # Check for quick reversal (price moves back through level within N candles)
                    reversal_found = False
                    reversal_candle_idx = None
                    
                    # Check candles after breakout (more recent = lower index)
                    for i in range(breakout_candle_idx):
                        candle = recent_candles[i]
                        candle_high = candle['high'] if isinstance(candle, dict) else candle.high
                        candle_low = candle['low'] if isinstance(candle, dict) else candle.low
                        candle_close = candle['close'] if isinstance(candle, dict) else candle.close
                        
                        if plan.direction == "BUY":
                            # For BUY: price should move back above key level (reversal up)
                            if candle_close > key_level:
                                reversal_found = True
                                reversal_candle_idx = i
                                # Verify rejection pattern (long lower wick)
                                wick_size = candle_low - min(candle_low, key_level)
                                body_size = abs(candle_close - (candle['open'] if isinstance(candle, dict) else candle.open))
                                if body_size > 0 and wick_size > body_size * 0.5:  # Long wick relative to body
                                    break
                        else:  # SELL
                            # For SELL: price should move back below key level (reversal down)
                            if candle_close < key_level:
                                reversal_found = True
                                reversal_candle_idx = i
                                # Verify rejection pattern (long upper wick)
                                wick_size = max(candle_high, key_level) - candle_high
                                body_size = abs(candle_close - (candle['open'] if isinstance(candle, dict) else candle.open))
                                if body_size > 0 and wick_size > body_size * 0.5:  # Long wick relative to body
                                    break
                    
                    if not reversal_found:
                        logger.debug(f"Plan {plan.plan_id}: No reversal detected after breakout (breakout at candle {breakout_candle_idx}, max reversal candles={fakeout_reversal_candles})")
                        return False
                    
                    # Verify reversal happened quickly (within fakeout_reversal_candles)
                    candles_since_breakout = breakout_candle_idx - reversal_candle_idx
                    if candles_since_breakout > fakeout_reversal_candles:
                        logger.debug(f"Plan {plan.plan_id}: Reversal too slow: {candles_since_breakout} candles > {fakeout_reversal_candles}")
                        return False
                    
                    logger.info(f"Plan {plan.plan_id}: Fakeout sweep condition met on {fakeout_tf}: breakout {breakout_direction} {key_level:.2f} at candle {breakout_candle_idx}, reversal at candle {reversal_candle_idx} ({candles_since_breakout} candles)")
                    
                except Exception as e:
                    logger.error(f"Error checking fakeout sweep condition for {plan.plan_id}: {e}", exc_info=True)
                    return False
            
            # Check flat volatility hours condition (session-based)
            if plan.conditions.get("flat_vol_hours") is not None:
                try:
                    # CRITICAL: Check session FIRST (performance optimization)
                    from infra.session_helpers import SessionHelpers
                    required_session = plan.conditions.get("session")
                    if required_session:
                        current_session = SessionHelpers.get_current_session()
                        if current_session != required_session:
                            logger.debug(f"Plan {plan.plan_id}: flat_vol_hours requires session '{required_session}', current is '{current_session}'")
                            return False
                    
                    # Get parameters
                    flat_vol_hours = plan.conditions.get("flat_vol_hours", 3)  # Default 3 hours
                    flat_vol_threshold = plan.conditions.get("flat_vol_threshold")  # Optional ATR threshold
                    flat_vol_stability = plan.conditions.get("flat_vol_stability", 0.2)  # Default 0.2 = 20% max variance
                    flat_vol_tf = plan.conditions.get("timeframe", "H1")  # Default H1 for hourly data
                    
                    # Fetch H1 candles for extended period (need at least flat_vol_hours + 2 for comparison)
                    hours_needed = flat_vol_hours + 2
                    flat_vol_candles = _get_recent_candles(symbol_norm, timeframe=flat_vol_tf, count=hours_needed)
                    flat_vol_candles = _normalize_candles(flat_vol_candles)
                    
                    if not flat_vol_candles or len(flat_vol_candles) < hours_needed:
                        logger.debug(f"Insufficient candles for flat vol hours check on {symbol_norm} {flat_vol_tf}: {len(flat_vol_candles) if flat_vol_candles else 0} < {hours_needed}")
                        return False
                    
                    # Calculate ATR for each hour
                    hourly_atrs = []
                    for i in range(min(flat_vol_hours + 1, len(flat_vol_candles))):
                        # Get candles for this hour (if using H1, each candle is an hour)
                        # For simplicity, calculate ATR from the hour's candle itself
                        hour_candle = flat_vol_candles[i]
                        hour_high = hour_candle['high'] if isinstance(hour_candle, dict) else hour_candle.high
                        hour_low = hour_candle['low'] if isinstance(hour_candle, dict) else hour_candle.low
                        hour_open = hour_candle['open'] if isinstance(hour_candle, dict) else hour_candle.open
                        hour_close = hour_candle['close'] if isinstance(hour_candle, dict) else hour_candle.close
                        
                        # Simple ATR approximation: use True Range of the hour candle
                        if i > 0:
                            prev_candle = flat_vol_candles[i + 1] if i + 1 < len(flat_vol_candles) else hour_candle
                            prev_close = prev_candle['close'] if isinstance(prev_candle, dict) else prev_candle.close
                            tr = max(hour_high - hour_low, abs(hour_high - prev_close), abs(hour_low - prev_close))
                        else:
                            tr = hour_high - hour_low
                        
                        hourly_atrs.append(tr)
                    
                    if len(hourly_atrs) < flat_vol_hours:
                        logger.debug(f"Insufficient hourly ATR values: {len(hourly_atrs)} < {flat_vol_hours}")
                        return False
                    
                    # Check if ATR values are consistently low
                    # Use average ATR as baseline if threshold not provided
                    avg_atr = sum(hourly_atrs) / len(hourly_atrs)
                    if flat_vol_threshold:
                        threshold_atr = flat_vol_threshold
                    else:
                        # Use average ATR as threshold (check if all are below average)
                        threshold_atr = avg_atr
                    
                    # Check if all recent hours have ATR below threshold
                    recent_hourly_atrs = hourly_atrs[:flat_vol_hours]
                    low_vol_count = sum(1 for atr in recent_hourly_atrs if atr < threshold_atr)
                    
                    if low_vol_count < flat_vol_hours:
                        logger.debug(f"Plan {plan.plan_id}: Not enough hours with low volatility: {low_vol_count}/{flat_vol_hours} hours below threshold {threshold_atr:.2f}")
                        return False
                    
                    # Check stability (low variance between hours)
                    if len(recent_hourly_atrs) > 1:
                        variance = sum((atr - avg_atr) ** 2 for atr in recent_hourly_atrs) / len(recent_hourly_atrs)
                        std_dev = variance ** 0.5
                        coefficient_of_variation = std_dev / avg_atr if avg_atr > 0 else 1.0
                        
                        if coefficient_of_variation > flat_vol_stability:
                            logger.debug(f"Plan {plan.plan_id}: Volatility not stable: CV={coefficient_of_variation:.2f} > threshold={flat_vol_stability:.2f}")
                            return False
                    
                    logger.info(f"Plan {plan.plan_id}: Flat volatility hours condition met on {flat_vol_tf}: {flat_vol_hours} hours with low stable volatility (avg_ATR={avg_atr:.2f})")
                    
                except Exception as e:
                    logger.error(f"Error checking flat volatility hours condition for {plan.plan_id}: {e}", exc_info=True)
                    return False
            
            # Check evening/morning star pattern condition
            if plan.conditions.get("pattern_evening_morning_star"):
                try:
                    # Get parameters
                    star_body_ratio = plan.conditions.get("star_body_ratio", 0.3)  # Default 0.3 = 30% of range
                    gap_threshold = plan.conditions.get("gap_threshold", 0.005)  # Default 0.5% of price
                    pattern_tf = plan.conditions.get("timeframe", "M15")
                    
                    # Fetch last 3 candles for pattern recognition
                    pattern_candles = _get_recent_candles(symbol_norm, timeframe=pattern_tf, count=3)
                    pattern_candles = _normalize_candles(pattern_candles)
                    
                    if not pattern_candles or len(pattern_candles) < 3:
                        logger.debug(f"Insufficient candles for evening/morning star pattern check on {symbol_norm} {pattern_tf}: {len(pattern_candles) if pattern_candles else 0} < 3")
                        return False
                    
                    # Get last 3 candles (most recent first)
                    c1 = pattern_candles[0]  # Most recent (third candle)
                    c2 = pattern_candles[1]  # Second candle (star)
                    c3 = pattern_candles[2]  # First candle (oldest)
                    
                    # Extract OHLC values
                    def get_ohlc(candle):
                        if isinstance(candle, dict):
                            return candle['open'], candle['high'], candle['low'], candle['close']
                        else:
                            return candle.open, candle.high, candle.low, candle.close
                    
                    o1, h1, l1, c1_val = get_ohlc(c1)
                    o2, h2, l2, c2_val = get_ohlc(c2)
                    o3, h3, l3, c3_val = get_ohlc(c3)
                    
                    # Calculate ranges and body sizes
                    range1 = max(1e-9, h1 - l1)
                    range2 = max(1e-9, h2 - l2)
                    range3 = max(1e-9, h3 - l3)
                    
                    body1 = abs(c1_val - o1)
                    body2 = abs(c2_val - o2)
                    body3 = abs(c3_val - o3)
                    
                    body1_ratio = body1 / range1 if range1 > 0 else 0
                    body2_ratio = body2 / range2 if range2 > 0 else 0
                    body3_ratio = body3 / range3 if range3 > 0 else 0
                    
                    # Check for Morning Star (Bullish reversal pattern)
                    # First candle (c3): Bearish (close < open)
                    # Second candle (c2): Small body (star), gaps down
                    # Third candle (c1): Bullish (close > open), closes above first candle's midpoint
                    is_bearish_c3 = c3_val < o3
                    is_bullish_c1 = c1_val > o1
                    c3_midpoint = (o3 + c3_val) / 2.0
                    gap_down = min(o2, c2_val) < max(o3, c3_val)  # Star gaps below first candle
                    
                    morning_star = (
                        is_bearish_c3 and
                        body3_ratio >= 0.4 and  # First candle has substantial body
                        body2_ratio <= star_body_ratio and  # Second candle has small body (star)
                        gap_down and
                        is_bullish_c1 and
                        c1_val > c3_midpoint  # Third candle closes above first candle's midpoint
                    )
                    
                    # Check for Evening Star (Bearish reversal pattern)
                    # First candle (c3): Bullish (close > open)
                    # Second candle (c2): Small body (star), gaps up
                    # Third candle (c1): Bearish (close < open), closes below first candle's midpoint
                    is_bullish_c3 = c3_val > o3
                    is_bearish_c1 = c1_val < o1
                    gap_up = max(o2, c2_val) > min(o3, c3_val)  # Star gaps above first candle
                    
                    evening_star = (
                        is_bullish_c3 and
                        body3_ratio >= 0.4 and  # First candle has substantial body
                        body2_ratio <= star_body_ratio and  # Second candle has small body (star)
                        gap_up and
                        is_bearish_c1 and
                        c1_val < c3_midpoint  # Third candle closes below first candle's midpoint
                    )
                    
                    # Check if pattern matches plan direction
                    if plan.direction == "BUY":
                        if not morning_star:
                            logger.debug(f"Plan {plan.plan_id}: Morning star pattern not detected for BUY plan")
                            return False
                        logger.info(f"Plan {plan.plan_id}: Morning star pattern detected on {pattern_tf} (bullish reversal)")
                    elif plan.direction == "SELL":
                        if not evening_star:
                            logger.debug(f"Plan {plan.plan_id}: Evening star pattern not detected for SELL plan")
                            return False
                        logger.info(f"Plan {plan.plan_id}: Evening star pattern detected on {pattern_tf} (bearish reversal)")
                    
                except Exception as e:
                    logger.error(f"Error checking evening/morning star pattern condition for {plan.plan_id}: {e}", exc_info=True)
                    return False
            
            # Check three-drive pattern condition
            if plan.conditions.get("pattern_three_drive"):
                try:
                    # Get parameters
                    drive_tolerance = plan.conditions.get("drive_tolerance", 0.01)  # Default 1% of price
                    fibonacci_tolerance = plan.conditions.get("fibonacci_tolerance", 0.1)  # Default 0.1 = 10%
                    pattern_tf = plan.conditions.get("timeframe", "M15")
                    
                    # Fetch extended price history for swing point detection
                    pattern_candles = _get_recent_candles(symbol_norm, timeframe=pattern_tf, count=100)
                    pattern_candles = _normalize_candles(pattern_candles)
                    
                    if not pattern_candles or len(pattern_candles) < 50:
                        logger.debug(f"Insufficient candles for three-drive pattern check on {symbol_norm} {pattern_tf}: {len(pattern_candles) if pattern_candles else 0} < 50")
                        return False
                    
                    # Extract OHLC values
                    def get_ohlc(candle):
                        if isinstance(candle, dict):
                            return candle['open'], candle['high'], candle['low'], candle['close']
                        else:
                            return candle.open, candle.high, candle.low, candle.close
                    
                    # Detect swing points (local highs/lows)
                    swing_points = []
                    window = 5  # Look for swing points with 5 candles on each side
                    
                    for i in range(window, len(pattern_candles) - window):
                        _, h, l, _ = get_ohlc(pattern_candles[i])
                        
                        # Check for swing high
                        is_swing_high = True
                        for j in range(i - window, i + window + 1):
                            if j != i:
                                _, hj, _, _ = get_ohlc(pattern_candles[j])
                                if hj >= h:
                                    is_swing_high = False
                                    break
                        
                        # Check for swing low
                        is_swing_low = True
                        for j in range(i - window, i + window + 1):
                            if j != i:
                                _, _, lj, _ = get_ohlc(pattern_candles[j])
                                if lj <= l:
                                    is_swing_low = False
                                    break
                        
                        if is_swing_high:
                            swing_points.append({'type': 'high', 'price': h, 'index': i})
                        if is_swing_low:
                            swing_points.append({'type': 'low', 'price': l, 'index': i})
                    
                    if len(swing_points) < 6:  # Need at least 6 swing points for three drives
                        logger.debug(f"Insufficient swing points for three-drive pattern: {len(swing_points)} < 6")
                        return False
                    
                    # Find three drives to similar level
                    # For BUY: look for three drives to a low (support level)
                    # For SELL: look for three drives to a high (resistance level)
                    target_type = 'low' if plan.direction == "BUY" else 'high'
                    target_swings = [s for s in swing_points if s['type'] == target_type]
                    
                    if len(target_swings) < 3:
                        logger.debug(f"Insufficient {target_type} swing points for three-drive pattern: {len(target_swings)} < 3")
                        return False
                    
                    # Get most recent three drives to similar level
                    # Sort by index (most recent first)
                    target_swings.sort(key=lambda x: x['index'], reverse=True)
                    
                    # Find three drives within tolerance
                    drives = []
                    base_price = target_swings[0]['price']
                    
                    for swing in target_swings[:10]:  # Check up to 10 most recent swings
                        price_diff = abs(swing['price'] - base_price) / base_price if base_price > 0 else 1.0
                        if price_diff <= drive_tolerance:
                            drives.append(swing)
                            if len(drives) >= 3:
                                break
                    
                    if len(drives) < 3:
                        logger.debug(f"Could not find three drives within tolerance: found {len(drives)} drives")
                        return False
                    
                    # Get the three drives (most recent first)
                    drive1 = drives[0]  # Most recent (third drive)
                    drive2 = drives[1]   # Second drive
                    drive3 = drives[2]   # First drive
                    
                    # Calculate drive lengths (distance from retracement to drive)
                    # For BUY: measure from swing high between drives to swing low (drive)
                    # For SELL: measure from swing low between drives to swing high (drive)
                    retracement_type = 'high' if plan.direction == "BUY" else 'low'
                    retracement_swings = [s for s in swing_points if s['type'] == retracement_type]
                    retracement_swings.sort(key=lambda x: x['index'], reverse=True)
                    
                    # Find retracements between drives
                    retracements = []
                    for ret in retracement_swings:
                        if drive1['index'] < ret['index'] < drive2['index']:
                            retracements.append({'drive': 1, 'price': ret['price'], 'index': ret['index']})
                        elif drive2['index'] < ret['index'] < drive3['index']:
                            retracements.append({'drive': 2, 'price': ret['price'], 'index': ret['index']})
                    
                    # Calculate drive lengths (simplified: use price difference)
                    # Drive 1 length: from retracement to drive1
                    # Drive 2 length: from retracement to drive2
                    # Drive 3 length: from retracement to drive3
                    if len(retracements) < 2:
                        # Simplified: use drive price differences
                        drive1_length = abs(drive1['price'] - drive2['price'])
                        drive2_length = abs(drive2['price'] - drive3['price'])
                        
                        # Check if drives are approximately equal (within Fibonacci tolerance)
                        if drive1_length > 0 and drive2_length > 0:
                            ratio = drive1_length / drive2_length if drive2_length > 0 else 0
                            # Check if ratio is close to 1.0 (equal drives) or Fibonacci ratios (1.272, 1.414)
                            fib_ratios = [1.0, 1.272, 1.414, 1.618]
                            is_valid_ratio = any(abs(ratio - fib) <= fibonacci_tolerance for fib in fib_ratios)
                            
                            if not is_valid_ratio:
                                logger.debug(f"Drive ratios not valid: {ratio:.3f} not close to Fibonacci ratios")
                                return False
                    else:
                        # Use retracements for more accurate calculation
                        ret1 = next((r for r in retracements if r['drive'] == 1), None)
                        ret2 = next((r for r in retracements if r['drive'] == 2), None)
                        
                        if ret1 and ret2:
                            drive1_length = abs(drive1['price'] - ret1['price'])
                            drive2_length = abs(drive2['price'] - ret2['price'])
                            
                            if drive1_length > 0 and drive2_length > 0:
                                ratio = drive1_length / drive2_length if drive2_length > 0 else 0
                                fib_ratios = [1.0, 1.272, 1.414, 1.618]
                                is_valid_ratio = any(abs(ratio - fib) <= fibonacci_tolerance for fib in fib_ratios)
                                
                                if not is_valid_ratio:
                                    logger.debug(f"Drive ratios not valid: {ratio:.3f} not close to Fibonacci ratios")
                                    return False
                    
                    # Check if third drive (most recent) is at completion point
                    # Price should be near the drive level
                    current_price = (drive1['price'] + base_price) / 2  # Approximate current price
                    price_diff = abs(current_price - drive1['price']) / drive1['price'] if drive1['price'] > 0 else 1.0
                    
                    if price_diff > drive_tolerance * 2:  # Allow some tolerance for completion
                        logger.debug(f"Third drive not at completion point: price_diff={price_diff:.3f} > {drive_tolerance * 2:.3f}")
                        return False
                    
                    logger.info(f"Plan {plan.plan_id}: Three-drive pattern detected on {pattern_tf}: {len(drives)} drives to level {base_price:.2f}")
                    
                except Exception as e:
                    logger.error(f"Error checking three-drive pattern condition for {plan.plan_id}: {e}", exc_info=True)
                    return False
            
            # Check volatility conditions
            volatility_conditions_met = True
            
            # Helper: Calculate ATR from candles
            def _calculate_atr(candles, period: int = 14) -> Optional[float]:
                """Calculate Average True Range"""
                if not candles or len(candles) < period + 1:
                    return None
                try:
                    tr_values = []
                    for i in range(1, min(len(candles), period + 10)):
                        c = candles[i]
                        prev_c = candles[i-1]
                        
                        h = c['high'] if isinstance(c, dict) else c.high
                        l = c['low'] if isinstance(c, dict) else c.low
                        prev_close = prev_c['close'] if isinstance(prev_c, dict) else prev_c.close
                        
                        tr1 = h - l
                        tr2 = abs(h - prev_close)
                        tr3 = abs(l - prev_close)
                        tr = max(tr1, tr2, tr3)
                        tr_values.append(tr)
                    
                    if len(tr_values) < period:
                        return None
                    
                    # Calculate ATR as SMA of TR
                    atr = sum(tr_values[-period:]) / period
                    return float(atr)
                except Exception as e:
                    logger.error(f"Error calculating ATR: {e}")
                    return None
            
            # Helper: Calculate Bollinger Bands width in ATR-equivalent units
            def _calculate_bb_width_atr(candles, period: int = 20, std_dev: float = 2.0) -> Optional[float]:
                """Calculate Bollinger Bands width in ATR-equivalent units"""
                if not candles or len(candles) < period:
                    return None
                try:
                    # Get closes
                    closes = [c['close'] if isinstance(c, dict) else c.close for c in candles[-period:]]
                    
                    # Calculate SMA and std dev
                    sma = sum(closes) / len(closes)
                    variance = sum((x - sma) ** 2 for x in closes) / len(closes)
                    std = variance ** 0.5
                    
                    # Upper and lower bands
                    upper = sma + (std * std_dev)
                    lower = sma - (std * std_dev)
                    bb_width = upper - lower
                    
                    # Calculate ATR for normalization
                    atr = _calculate_atr(candles, period=period) or 1.0
                    
                    # Return BB width in ATR-equivalent units
                    return float(bb_width / atr) if atr > 0 else None
                except Exception as e:
                    logger.error(f"Error calculating BB width: {e}")
                    return None
            
            # Check volatility thresholds with 2-of-3 rule
            volatility_triggers = []
            
            # ATR(5m) threshold check
            if "atr_5m_threshold" in plan.conditions:
                m5_candles = _get_recent_candles(symbol_norm, timeframe="M5", count=20)
                m5_candles = _normalize_candles(m5_candles)
                atr_5m = _calculate_atr(m5_candles, period=14)
                threshold = plan.conditions["atr_5m_threshold"]
                if atr_5m is not None:
                    atr_met = atr_5m > threshold
                    volatility_triggers.append(("ATR(5m)", atr_met, f"{atr_5m:.2f} > {threshold}"))
                    logger.debug(f"ATR(5m): {atr_5m:.2f} vs threshold {threshold} = {atr_met}")
                else:
                    logger.warning(f"Could not calculate ATR(5m) for {plan.symbol}")
            
            # VIX threshold check
            if "vix_threshold" in plan.conditions:
                try:
                    from infra.market_indices_service import create_market_indices_service
                    indices = create_market_indices_service()
                    vix_data = indices.get_vix()
                    vix_price = vix_data.get('price')
                    threshold = plan.conditions["vix_threshold"]
                    if vix_price is not None:
                        vix_met = vix_price > threshold
                        volatility_triggers.append(("VIX", vix_met, f"{vix_price:.2f} > {threshold}"))
                        logger.debug(f"VIX: {vix_price:.2f} vs threshold {threshold} = {vix_met}")
                    else:
                        logger.warning("Could not fetch VIX data")
                except Exception as e:
                    logger.error(f"Error fetching VIX: {e}")
            
            # BB Width threshold check
            if "bb_width_threshold" in plan.conditions:
                m5_candles = _get_recent_candles(symbol_norm, timeframe="M5", count=30)
                m5_candles = _normalize_candles(m5_candles)
                bb_width = _calculate_bb_width_atr(m5_candles, period=20, std_dev=2.0)
                threshold = plan.conditions["bb_width_threshold"]
                if bb_width is not None:
                    bb_met = bb_width > threshold
                    volatility_triggers.append(("BB Width", bb_met, f"{bb_width:.2f} > {threshold}"))
                    logger.debug(f"BB Width: {bb_width:.2f} vs threshold {threshold} = {bb_met}")
                else:
                    logger.warning(f"Could not calculate BB Width for {plan.symbol}")
            
            # Apply 2-of-3 rule if volatility triggers are defined
            if volatility_triggers:
                met_count = sum(1 for _, met, _ in volatility_triggers if met)
                required = plan.conditions.get("volatility_trigger_rule", 2)  # Default: 2 of 3
                volatility_conditions_met = met_count >= required
                
                trigger_status = ", ".join([f"{name}: {'✅' if met else '❌'}" for name, met, _ in volatility_triggers])
                logger.info(f"Volatility check for {plan.plan_id}: {met_count}/{len(volatility_triggers)} met ({trigger_status})")
                
                if not volatility_conditions_met:
                    logger.debug(f"Volatility conditions not met: {met_count}/{len(volatility_triggers)} < {required}")
                    return False
            
            # Legacy min/max volatility (if present)
            if "min_volatility" in plan.conditions:
                # Use ATR as proxy for volatility
                m5_candles = _get_recent_candles(symbol_norm, timeframe="M5", count=20)
                m5_candles = _normalize_candles(m5_candles)
                atr = _calculate_atr(m5_candles, period=14)
                if atr is not None and atr < plan.conditions["min_volatility"]:
                    logger.debug(f"Volatility too low: ATR {atr:.2f} < {plan.conditions['min_volatility']}")
                    return False
                    
            if "max_volatility" in plan.conditions:
                # Use ATR as proxy for volatility
                m5_candles = _get_recent_candles(symbol_norm, timeframe="M5", count=20)
                m5_candles = _normalize_candles(m5_candles)
                atr = _calculate_atr(m5_candles, period=14)
                if atr is not None and atr > plan.conditions["max_volatility"]:
                    logger.debug(f"Volatility too high: ATR {atr:.2f} > {plan.conditions['max_volatility']}")
                    return False
            
            # Check for immediate execution flag
            if "execute_immediately" in plan.conditions and plan.conditions["execute_immediately"]:
                logger.info(f"Plan {plan.plan_id} marked for immediate execution")
                return True
            
            # Check for micro-scalp conditions (special condition)
            if plan.conditions.get("plan_type") == "micro_scalp":
                if not self.micro_scalp_engine:
                    logger.warning(f"Micro-scalp plan {plan.plan_id} requires micro-scalp engine (not available)")
                    return False
                
                try:
                    # Use micro-scalp engine to check conditions
                    result = self.micro_scalp_engine.check_micro_conditions(symbol_norm, plan_id=plan.plan_id)
                    
                    if not result.get('passed'):
                        logger.debug(f"Micro-scalp conditions not met for {symbol_norm}: {result.get('reasons', [])}")
                        return False
                    
                    # Store trade idea in plan for execution
                    trade_idea = result.get('trade_idea')
                    if trade_idea:
                        # Store trade idea in plan conditions for execution
                        plan.conditions['_micro_scalp_trade_idea'] = trade_idea
                        logger.info(f"✅ Micro-scalp conditions met for {symbol_norm}, ready for execution")
                        return True
                    else:
                        # If no trade idea but conditions passed, allow normal execution
                        logger.info(f"✅ Micro-scalp conditions met for {symbol_norm}")
                        return True
                    
                except Exception as e:
                    logger.error(f"Error checking micro-scalp conditions: {e}", exc_info=True)
                    return False
            
            # Check for range scalping confluence (special condition) - takes precedence
            # Phase 1.2: Check range_scalp_confluence first (takes precedence over min_confluence)
            if plan.conditions.get("plan_type") == "range_scalp" or "range_scalp_confluence" in plan.conditions:
                min_confluence = plan.conditions.get("range_scalp_confluence", 80)
                
                try:
                    # Import range scalping analysis
                    from infra.range_scalping_analysis import analyse_range_scalp_opportunity
                    from infra.indicator_bridge import IndicatorBridge
                    from infra.feature_builder_advanced import build_features_advanced
                    
                    logger.debug(f"Checking range scalping confluence for {symbol_norm} (min: {min_confluence})")
                    
                    # Initialize indicator bridge
                    bridge = IndicatorBridge(None)
                    
                    # Get multi-timeframe data
                    all_timeframe_data = bridge.get_multi(symbol_norm)
                    m5_data = all_timeframe_data.get("M5")
                    m15_data = all_timeframe_data.get("M15")
                    h1_data = all_timeframe_data.get("H1")
                    
                    if not all([m5_data, m15_data, h1_data]):
                        logger.warning(f"Insufficient data for range scalping check on {symbol_norm}")
                        return False
                    
                    # Prepare indicators
                    indicators = {
                        "rsi": m5_data.get("indicators", {}).get("rsi", 50),
                        "bb_upper": m5_data.get("indicators", {}).get("bb_upper"),
                        "bb_lower": m5_data.get("indicators", {}).get("bb_lower"),
                        "bb_middle": m5_data.get("indicators", {}).get("bb_middle"),
                        "adx_h1": h1_data.get("indicators", {}).get("adx", 20),
                        "atr_5m": m5_data.get("indicators", {}).get("atr14", 0)
                    }
                    
                    # Get MT5 service for market data
                    from infra.mt5_service import MT5Service
                    mt5_service = MT5Service()
                    
                    # Prepare market_data
                    market_data = {
                        "current_price": current_price,
                        "atr": indicators.get("atr_5m", 0) or 0,
                        "atr_5m": indicators.get("atr_5m", 0) or 0,
                        "m15_df": m15_data.get("df") if m15_data else None,
                        "mt5_service": mt5_service
                    }
                    
                    # Run range scalping analysis (synchronously for now)
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    result = loop.run_until_complete(
                        analyse_range_scalp_opportunity(
                            symbol=symbol_norm,
                            check_risk_filters=True,
                            market_data=market_data,
                            indicators=indicators
                        )
                    )
                    
                    # Extract confluence score from result
                    risk_checks = result.get("risk_checks", {})
                    confluence_score = risk_checks.get("confluence_score", 0)
                    
                    logger.debug(f"Range scalping confluence check: {confluence_score} >= {min_confluence}?")
                    
                    # Check if confluence meets threshold
                    if confluence_score < min_confluence:
                        logger.debug(f"Confluence too low: {confluence_score} < {min_confluence}")
                        return False
                    
                    # Check for structure confirmation if required
                    # Skip CHOCH/BOS checks for forex pairs (only BTC and XAU use these)
                    if plan.conditions.get("structure_confirmation"):
                        if self._is_forex_pair(symbol_norm):
                            logger.debug(f"Skipping structure confirmation (CHOCH/BOS) for forex pair {symbol_norm}")
                            return False  # Don't allow structure confirmation for forex pairs
                        
                        structure_tf = plan.conditions.get("structure_timeframe", "M15")
                        candles = _get_recent_candles(symbol_norm, timeframe=structure_tf, count=100)
                        
                        # Check for structure confirmation based on direction
                        # Structure confirmation can be either CHOCH (reversal) or BOS (continuation)
                        # For BUY: need bullish structure (CHOCH Bull OR BOS Bull)
                        # For SELL: need bearish structure (CHOCH Bear OR BOS Bear)
                        structure_confirmed = False
                        
                        if plan.direction == "BUY":
                            # Check for bullish CHOCH (structure shift to bullish)
                            choch_bull = _detect_choch(candles, "bull")
                            # Check for bullish BOS (uptrend continuation)
                            bos_bull = _detect_bos(candles, "bull")
                            structure_confirmed = choch_bull or bos_bull
                            
                            if not structure_confirmed:
                                logger.debug(f"Structure confirmation not met for BUY: no bullish CHOCH or BOS on {structure_tf}")
                                return False
                            else:
                                structure_type = "CHOCH" if choch_bull else "BOS"
                                logger.debug(f"Structure confirmation met for BUY: {structure_type} detected on {structure_tf}")
                        else:  # SELL
                            # Check for bearish CHOCH (structure shift to bearish)
                            choch_bear = _detect_choch(candles, "bear")
                            # Check for bearish BOS (downtrend continuation)
                            bos_bear = _detect_bos(candles, "bear")
                            structure_confirmed = choch_bear or bos_bear
                            
                            if not structure_confirmed:
                                logger.debug(f"Structure confirmation not met for SELL: no bearish CHOCH or BOS on {structure_tf}")
                                return False
                            else:
                                structure_type = "CHOCH" if choch_bear else "BOS"
                                logger.debug(f"Structure confirmation met for SELL: {structure_type} detected on {structure_tf}")
                    
                    # Check price near entry (already checked above if price_near is in conditions)
                    if "price_near" in plan.conditions:
                        target_price = plan.conditions["price_near"]
                        tolerance = plan.conditions.get("tolerance")
                        if tolerance is None:
                            from infra.tolerance_helper import get_price_tolerance
                            tolerance = get_price_tolerance(plan.symbol)
                        if abs(current_price - target_price) > tolerance:
                            logger.debug(f"Price not near entry: {current_price} vs {target_price} (±{tolerance})")
                            return False
                    
                    logger.info(f"✅ Range scalping conditions met: confluence={confluence_score}, structure confirmed, price near entry")
                    return True
                    
                except Exception as e:
                    logger.error(f"Error checking range scalping confluence: {e}", exc_info=True)
                    return False
            
            # Phase 1.2: Check min_confluence (for non-range-scalping plans)
            # NOTE: This block only runs if range_scalp_confluence is NOT in conditions
            # NOTE: Price conditions (price_near, price_above, price_below) are already
            # checked earlier in this method (lines 1253-1262). If price conditions failed,
            # this code block would not be reached (method would have returned False).
            # Therefore, we only need to check confluence here.
            if "min_confluence" in plan.conditions and "range_scalp_confluence" not in plan.conditions and plan.conditions.get("plan_type") != "range_scalp":
                # Validate conditions dict exists
                if not plan.conditions:
                    logger.warning(f"Plan {plan.plan_id} has empty conditions dict")
                    return False
                
                # Get threshold (default: 60 - suitable for range/compression regimes)
                # Rationale: 60 is a conservative default that avoids noise while allowing
                # reasonable confluence levels for most strategies. ChatGPT should specify
                # threshold based on market regime (60-70 for most, 65-75 for trend continuation).
                min_confluence_threshold = plan.conditions.get("min_confluence")
                
                # Handle None case (shouldn't happen if validation works, but be safe)
                if min_confluence_threshold is None:
                    logger.warning(f"Plan {plan.plan_id}: min_confluence is None, using default 60")
                    min_confluence_threshold = 60
                
                # Validate threshold range and type
                if not isinstance(min_confluence_threshold, (int, float)):
                    logger.warning(f"Invalid min_confluence type for plan {plan.plan_id}: {type(min_confluence_threshold)}, using default 60")
                    min_confluence_threshold = 60
                min_confluence_threshold = max(0, min(100, int(min_confluence_threshold)))  # Clamp to 0-100
                
                try:
                    # Use existing method (with caching) - symbol_norm is already normalized in _check_conditions()
                    # symbol_norm is available from earlier in _check_conditions() method (line 938)
                    confluence_score = self._get_confluence_score(symbol_norm)  # Use normalized symbol
                    
                    # Validate confluence score (should already be 0-100 from _get_confluence_score, but double-check)
                    if not isinstance(confluence_score, (int, float)):
                        logger.error(f"Invalid confluence score type for plan {plan.plan_id}: {confluence_score}")
                        return False
                    confluence_score = max(0, min(100, int(confluence_score)))  # Clamp to 0-100
                    
                    if confluence_score < min_confluence_threshold:
                        logger.debug(
                            f"Plan {plan.plan_id}: Confluence too low: {confluence_score} < {min_confluence_threshold}"
                        )
                        return False
                    
                    logger.info(
                        f"✅ Plan {plan.plan_id}: General confluence condition met: "
                        f"{confluence_score} >= {min_confluence_threshold}"
                    )
                    # Note: Price conditions are already checked (lines 1253-1262)
                    # Other structural conditions (if present) are checked separately
                    # This supports "hybrid mode" - confluence + conditions
                    # Don't return True here - let method continue to check other conditions
                    
                except Exception as e:
                    logger.error(
                        f"Error checking general confluence for plan {plan.plan_id}: {e}",
                        exc_info=True
                    )
                    
                    # ⚠️ CRITICAL: Conditional error handling based on plan type
                    # Determine if confluence is critical for this plan
                    # Check if plan has other structural conditions (hybrid mode)
                    # NOTE: We're checking if other conditions EXIST (not if they pass)
                    # Other conditions are checked later in _check_conditions() method
                    # This determines if confluence is critical (confluence-only) or optional (hybrid)
                    
                    # Validate conditions dict exists before checking
                    if not plan.conditions:
                        logger.warning(f"Plan {plan.plan_id}: Empty conditions dict in error handler")
                        return False
                    
                    has_other_conditions = any([
                        "bb_expansion" in plan.conditions,
                        "structure_confirmation" in plan.conditions,
                        "order_block" in plan.conditions,
                        "choch_bull" in plan.conditions,
                        "choch_bear" in plan.conditions,
                        "bos_bull" in plan.conditions,
                        "bos_bear" in plan.conditions,
                        "fvg_bull" in plan.conditions,
                        "fvg_bear" in plan.conditions,
                        "rejection_wick" in plan.conditions,
                        "liquidity_sweep" in plan.conditions,
                        "breaker_block" in plan.conditions,
                        "mitigation_block_bull" in plan.conditions,
                        "mitigation_block_bear" in plan.conditions,
                        "mss_bull" in plan.conditions,
                        "mss_bear" in plan.conditions,
                    ])
                    
                    if has_other_conditions:
                        # Hybrid mode: Confluence is optional filter
                        # Don't return - let other conditions be checked later in the method
                        # Just log and continue - method will return True/False based on other conditions
                        # Other conditions are checked after this block (around line 2560+)
                        logger.warning(
                            f"Plan {plan.plan_id}: Confluence check failed in hybrid mode, "
                            f"skipping confluence requirement (other conditions will be checked later)"
                        )
                        # Don't return - continue to check other conditions
                        # The method will return True/False based on other conditions at line 2660
                    else:
                        # Confluence-only mode: Confluence is critical, fail closed
                        # If confluence check fails and there are no other conditions,
                        # the plan cannot execute (confluence is the only condition)
                        logger.warning(
                            f"Plan {plan.plan_id}: Confluence check failed in confluence-only mode, "
                            f"blocking execution (confluence is required and no other conditions exist)"
                        )
                        return False  # Fail closed - confluence is required
            
            # Only execute if there are actual conditions to check
            # If no conditions are specified, don't execute automatically
            has_conditions = any([
                "price_above" in plan.conditions,
                "price_below" in plan.conditions,
                "price_near" in plan.conditions,
                "choch_bear" in plan.conditions,
                "choch_bull" in plan.conditions,
                "bos_bear" in plan.conditions,
                "bos_bull" in plan.conditions,
                "rejection_wick" in plan.conditions,
                "time_after" in plan.conditions,
                "time_before" in plan.conditions,
                "min_volatility" in plan.conditions,
                "max_volatility" in plan.conditions,
                "atr_5m_threshold" in plan.conditions,
                "vix_threshold" in plan.conditions,
                "bb_width_threshold" in plan.conditions,
                "bb_squeeze" in plan.conditions,
                "bb_expansion" in plan.conditions,
                "bb_retest" in plan.conditions,
                "zscore" in plan.conditions,
                "atr_stretch" in plan.conditions,
                "atr_multiple" in plan.conditions,
                "spx_up_pct" in plan.conditions,
                "yield_drop" in plan.conditions,
                "correlation_divergence" in plan.conditions,
                "volatility_decay" in plan.conditions,
                "momentum_follow" in plan.conditions,
                "fakeout_sweep" in plan.conditions,
                "flat_vol_hours" in plan.conditions,
                "pattern_evening_morning_star" in plan.conditions,
                "pattern_three_drive" in plan.conditions,
                "inside_bar" in plan.conditions,
                "equal_highs" in plan.conditions,
                "equal_lows" in plan.conditions,
                "execute_immediately" in plan.conditions,
                "range_scalp_confluence" in plan.conditions,
                "structure_confirmation" in plan.conditions,  # Added missing condition
                "min_confluence" in plan.conditions,  # Phase 4.5: Confluence-only mode
                # Volume conditions (Volume Confirmation Implementation)
                "volume_confirmation" in plan.conditions,
                "volume_ratio" in plan.conditions,
                "volume_above" in plan.conditions,
                "volume_spike" in plan.conditions,
                plan.conditions.get("plan_type") == "range_scalp",
                plan.conditions.get("plan_type") == "micro_scalp",
                # Phase 4.5: New SMC strategy conditions
                "order_block" in plan.conditions,
                "breaker_block" in plan.conditions,
                "mitigation_block_bull" in plan.conditions,
                "mitigation_block_bear" in plan.conditions,
                "mss_bull" in plan.conditions,
                "mss_bear" in plan.conditions,
                "pullback_to_mss" in plan.conditions,
                "fvg_bull" in plan.conditions,
                "fvg_bear" in plan.conditions,
                "liquidity_grab_bull" in plan.conditions,
                "liquidity_grab_bear" in plan.conditions,
                "price_in_discount" in plan.conditions,
                "price_in_premium" in plan.conditions,
                "asian_session_high" in plan.conditions,
                "asian_session_low" in plan.conditions,
                "kill_zone_active" in plan.conditions,
            ])
            
            if not has_conditions:
                # Only log once per plan to avoid spam - check if we've already logged this
                if not hasattr(plan, '_no_conditions_logged'):
                    logger.warning(f"Plan {plan.plan_id} has no conditions specified - skipping execution. This plan should be cancelled or updated with conditions.")
                    plan._no_conditions_logged = True
                return False
            
            # M1 Microstructure Validation (Phase 2.1)
            # Note: This runs AFTER higher timeframe conditions (M5/M15) are checked
            # If both m1_choch_bos_combo AND choch_bull/choch_bear are present, BOTH must pass
            # SKIP M1 validation for price-only plans (plans with only price_near + tolerance, no M1/structure conditions)
            has_m1_conditions = any([
                plan.conditions.get('m1_choch'),
                plan.conditions.get('m1_bos'),
                plan.conditions.get('m1_choch_bos_combo'),
                plan.conditions.get('m1_volatility_contracting'),
                plan.conditions.get('m1_volatility_expanding'),
                plan.conditions.get('m1_squeeze_duration'),
                plan.conditions.get('m1_momentum_quality'),
                plan.conditions.get('m1_structure_type'),
                plan.conditions.get('m1_trend_alignment'),
            ])
            has_structure_conditions = any([
                plan.conditions.get('liquidity_sweep'),
                plan.conditions.get('rejection_wick'),
                plan.conditions.get('choch_bull'),
                plan.conditions.get('choch_bear'),
                plan.conditions.get('bos_bull'),
                plan.conditions.get('bos_bear'),
                plan.conditions.get('order_block'),
                plan.conditions.get('inside_bar'),
            ])
            is_price_only = not has_m1_conditions and not has_structure_conditions
            
            if self.m1_analyzer and plan.symbol and not is_price_only:
                m1_validation_passed = self._validate_m1_conditions(plan, symbol_norm)
                if not m1_validation_passed:
                    logger.debug(f"Plan {plan.plan_id}: M1 validation failed (not price-only plan)")
                    return False
            elif is_price_only:
                logger.debug(f"Plan {plan.plan_id}: Skipping M1 validation (price-only plan)")
            else:
                logger.debug(f"Plan {plan.plan_id}: M1 analyzer not available, skipping M1 validation")
            
            # ============================================================================
            # ENHANCED CONTEXTUAL VALIDATION (Phase 1B)
            # ============================================================================
            # This is an ADDITIVE validation layer that runs AFTER existing validation passes.
            # It adds contextual checks based on hierarchical trend analysis:
            # - Counter-trend trade rejection (if confluence < 60%)
            # - Risk adjustment validation (SL/TP ratios for counter-trend)
            # - Liquidity state mismatch rejection (in strong trends)
            #
            # NOTE: This does NOT replace existing validation. All existing checks
            # (price conditions, CHOCH/BOS, etc.) must pass FIRST before these
            # enhanced checks are applied.
            # ============================================================================
            try:
                # Get primary trend from multi-timeframe analysis
                mtf_analysis = self._get_mtf_analysis(plan.symbol)
                if mtf_analysis:
                    # Access recommendation structure (market_bias and trade_opportunities are nested in recommendation)
                    recommendation = mtf_analysis.get("recommendation", {})
                    primary_trend = recommendation.get("market_bias", {}).get("trend", "UNKNOWN")
                    trend_strength = recommendation.get("market_bias", {}).get("strength", "UNKNOWN")
                    trade_opportunity = recommendation.get("trade_opportunities", {})
                    
                    # Skip enhanced validation if no trade opportunity detected
                    if not trade_opportunity or trade_opportunity.get("type") == "NONE":
                        # No trade opportunity, skip enhanced validation
                        pass
                    else:
                        # Validation 1: Primary trend contradiction
                        plan_direction = "BULLISH" if plan.direction == "BUY" else "BEARISH"
                        is_counter_trend = (
                            (primary_trend == "BEARISH" and plan_direction == "BULLISH") or
                            (primary_trend == "BULLISH" and plan_direction == "BEARISH")
                        )
                        
                        if is_counter_trend:
                            # Get confluence score (from existing confluence calculation)
                            confluence_score = self._get_confluence_score(plan.symbol)
                            
                            if confluence_score < 60:
                                logger.warning(
                                    f"Plan {plan.plan_id}: Rejected - Counter-trend trade "
                                    f"(primary trend: {primary_trend}, plan: {plan.direction}) "
                                    f"with low confluence ({confluence_score}% < 60%)"
                                )
                                return False
                            
                            # Validation 2: Check risk adjustments for counter-trend
                            risk_adjustments = trade_opportunity.get("risk_adjustments", {})
                            if risk_adjustments:
                                # Validate SL/TP ratios meet requirements
                                sl_distance = abs(plan.entry_price - plan.stop_loss)
                                tp_distance = abs(plan.take_profit - plan.entry_price)
                                if sl_distance > 0:
                                    rr_ratio = tp_distance / sl_distance
                                    max_rr = risk_adjustments.get("max_risk_rr", 1.0)
                                    if rr_ratio > max_rr:
                                        logger.warning(
                                            f"Plan {plan.plan_id}: Rejected - Counter-trend R:R "
                                            f"({rr_ratio:.2f}:1) exceeds max allowed ({max_rr:.2f}:1)"
                                        )
                                        return False
                        
                        # Validation 3: Liquidity state mismatch
                        if self.m1_analyzer and self.m1_data_fetcher:
                            liquidity_context = self._get_liquidity_context(plan.symbol, plan.entry_price)
                            if liquidity_context:
                                position = liquidity_context.get("position", "unknown")
                                # Reject if plan contradicts liquidity position in strong trends
                                if trend_strength == "STRONG":
                                    if (plan.direction == "BUY" and position == "below_midpoint" and primary_trend == "BEARISH"):
                                        logger.warning(
                                            f"Plan {plan.plan_id}: Rejected - BUY plan below VWAP "
                                            f"in strong bearish trend"
                                        )
                                        return False
                                    elif (plan.direction == "SELL" and position == "above_midpoint" and primary_trend == "BULLISH"):
                                        logger.warning(
                                            f"Plan {plan.plan_id}: Rejected - SELL plan above VWAP "
                                            f"in strong bullish trend"
                                        )
                                        return False
            except Exception as e:
                logger.debug(f"Enhanced validation check failed (non-critical): {e}")
                # Don't block execution if validation check fails (non-critical enhancement)
            
            # ============================================================================
            # Phase 2.1: MTF Alignment Condition Support
            # ============================================================================
            # Check MTF alignment conditions
            if plan.conditions.get("mtf_alignment_score") is not None:
                try:
                    mtf_analysis = self._get_mtf_analysis(plan.symbol)
                    if not mtf_analysis:
                        logger.debug(f"Plan {plan.plan_id}: MTF analysis unavailable")
                        return False
                    
                    # Get alignment score
                    recommendation = mtf_analysis.get("recommendation", {})
                    alignment_score = recommendation.get("alignment_score", 0)
                    
                    min_score = plan.conditions.get("mtf_alignment_score", 60)
                    if alignment_score < min_score:
                        logger.debug(
                            f"Plan {plan.plan_id}: MTF alignment score too low: "
                            f"{alignment_score} < {min_score}"
                        )
                        return False
                except Exception as e:
                    logger.debug(f"Error checking MTF alignment for {plan.plan_id}: {e}")
                    return False
            
            # Check H4/H1 bias conditions
            if plan.conditions.get("h4_bias") or plan.conditions.get("h1_bias"):
                try:
                    mtf_analysis = self._get_mtf_analysis(plan.symbol)
                    if not mtf_analysis:
                        logger.debug(f"Plan {plan.plan_id}: MTF analysis unavailable for bias check")
                        return False
                    
                    timeframes = mtf_analysis.get("timeframes", {})
                    
                    if plan.conditions.get("h4_bias"):
                        required_h4_bias = plan.conditions.get("h4_bias")
                        actual_h4_bias = timeframes.get("H4", {}).get("bias", "NEUTRAL")
                        if actual_h4_bias != required_h4_bias:
                            logger.debug(
                                f"Plan {plan.plan_id}: H4 bias mismatch: "
                                f"{actual_h4_bias} != {required_h4_bias}"
                            )
                            return False
                    
                    if plan.conditions.get("h1_bias"):
                        required_h1_bias = plan.conditions.get("h1_bias")
                        actual_h1_bias = timeframes.get("H1", {}).get("bias", "NEUTRAL")
                        if actual_h1_bias != required_h1_bias:
                            logger.debug(
                                f"Plan {plan.plan_id}: H1 bias mismatch: "
                                f"{actual_h1_bias} != {required_h1_bias}"
                            )
                            return False
                except Exception as e:
                    logger.debug(f"Error checking MTF bias for {plan.plan_id}: {e}")
                    return False
            
            # ============================================================================
            # End Phase 2.1: MTF Alignment Condition Support
            # ============================================================================
            
            # If we get here, both existing AND enhanced validation passed
            logger.info(f"Plan {plan.plan_id}: ✅ ALL CONDITIONS PASSED - Ready for execution")
            return True
            
        except Exception as e:
            logger.error(f"Error checking conditions for plan {plan.plan_id}: {e}")
            return False
    
    def _validate_m1_conditions(self, plan: TradePlan, symbol_norm: str) -> bool:
        """
        Validate M1 microstructure conditions for a trade plan.
        
        Args:
            plan: Trade plan to validate
            symbol_norm: Normalized symbol name
            
        Returns:
            True if M1 conditions are met, False otherwise
        """
        try:
            # Refresh M1 data if stale
            if self.m1_refresh_manager:
                if self.m1_refresh_manager.check_and_refresh_stale(symbol_norm, max_age_seconds=180):
                    logger.debug(f"Refreshed M1 data for {symbol_norm}")
            
            # Performance Optimization: Check cache first (Phase 2.1.1)
            m1_data = self._get_cached_m1_data(symbol_norm)
            
            # Get current price for validation (needed for both cached and fresh data)
            current_price = plan.entry_price  # Default to entry price
            try:
                if self.mt5_service.connect():
                    quote = self.mt5_service.get_quote(symbol_norm)
                    current_price = quote.ask if plan.direction == "BUY" else quote.bid
            except:
                pass  # Use entry price as fallback
            
            if not m1_data:
                # Get M1 data
                if not self.m1_data_fetcher:
                    return True  # Skip M1 validation if fetcher not available
                
                m1_candles = self.m1_data_fetcher.fetch_m1_data(symbol_norm, count=200)
                if not m1_candles or len(m1_candles) < 50:
                    logger.debug(f"Insufficient M1 data for {symbol_norm}, skipping M1 validation")
                    return True  # Don't block execution if M1 data unavailable
                
                # Analyze M1 microstructure
                m1_data = self.m1_analyzer.analyze_microstructure(
                    symbol=symbol_norm,
                    candles=m1_candles,
                    current_price=current_price
                )
                
                # Cache the data
                if m1_data:
                    self._cache_m1_data(symbol_norm, m1_data)
            
            if not m1_data or not m1_data.get('available'):
                logger.debug(f"M1 analysis unavailable for {symbol_norm}, skipping M1 validation")
                return True  # Don't block execution if M1 analysis unavailable
            
            # Check M1-specific conditions
            m1_conditions_met = self._check_m1_conditions(plan, m1_data)
            if not m1_conditions_met:
                logger.debug(f"M1 conditions not met for plan {plan.plan_id}")
                return False
            
            # Enhanced validations (Phase 2.1)
            # Rejection wick validation
            if not self._validate_rejection_wick(plan, m1_data, current_price):
                logger.debug(f"Rejection wick validation failed for plan {plan.plan_id}")
                return False
            
            # VWAP + Microstructure combo validation
            if plan.conditions.get('require_vwap_microstructure_combo', False):
                if not self._validate_vwap_microstructure_combo(plan, m1_data):
                    logger.debug(f"VWAP/Microstructure combo validation failed for plan {plan.plan_id}")
                    return False
            
            # Liquidity sweep detection (informational, doesn't block)
            liquidity_sweep = self._detect_liquidity_sweep(plan, m1_data, current_price)
            if liquidity_sweep:
                logger.info(f"Liquidity sweep detected for {plan.plan_id} - consider tighter stop-loss")
            
            # ============================================================================
            # ISSUE 2: CHOCH Confirmation for Liquidity Sweep Reversal Plans
            # ============================================================================
            # Require CHOCH/BOS confirmation before executing liquidity sweep reversals
            if plan.conditions.get("liquidity_sweep"):
                # 1. Require CHOCH/BOS confirmation
                if plan.direction == "SELL":
                    if not (m1_data.get('choch_bear') or m1_data.get('bos_bear')):
                        logger.debug(
                            f"Plan {plan.plan_id}: Liquidity sweep detected but CHOCH Bear/BOS Bear not confirmed - blocking execution"
                        )
                        return False
                else:  # BUY
                    if not (m1_data.get('choch_bull') or m1_data.get('bos_bull')):
                        logger.debug(
                            f"Plan {plan.plan_id}: Liquidity sweep detected but CHOCH Bull/BOS Bull not confirmed - blocking execution"
                        )
                        return False
                
                # 2. For BTCUSD, require CVD divergence
                if symbol_norm.upper().startswith('BTC'):
                    if self.micro_scalp_engine and hasattr(self.micro_scalp_engine, 'btc_order_flow'):
                        try:
                            cvd_data = self.micro_scalp_engine.btc_order_flow.get_cvd_divergence()
                            if not cvd_data or not cvd_data.get('divergence_detected'):
                                logger.debug(
                                    f"Plan {plan.plan_id}: Liquidity sweep detected but CVD divergence not confirmed for BTCUSD - blocking execution"
                                )
                                return False
                        except Exception as e:
                            logger.debug(f"Error checking CVD divergence for {plan.plan_id}: {e}")
                            # Continue if CVD check fails (order flow may not be available)
            
            # Confidence weighting validation (Phase 2.1.1)
            use_rolling_mean = self.config.get('choch_detection', {}).get('use_rolling_mean', False)
            confidence = self._calculate_m1_confidence(m1_data, symbol_norm, use_rolling_mean=use_rolling_mean)
            
            # Get symbol-specific threshold
            threshold = 60  # Default (reduced from 70%)
            if self.asset_profiles:
                threshold = self.asset_profiles.get_confluence_minimum(symbol_norm)
            
            # Check confidence against threshold
            if confidence < threshold:
                logger.debug(
                    f"Plan {plan.plan_id}: M1 confidence {confidence:.1f} < threshold {threshold} "
                    f"(Symbol: {symbol_norm})"
                )
                return False
            
            # Get session context for logging
            session_context = m1_data.get('session_context', {})
            current_session = session_context.get('session', 'LONDON')
            
            # Check dynamic threshold
            dynamic_threshold = m1_data.get('dynamic_threshold')
            threshold_calc = m1_data.get('threshold_calculation', {})
            
            if dynamic_threshold:
                base_confluence = m1_data.get('microstructure_confluence', {}).get('score', 0)
                if base_confluence < dynamic_threshold:
                    logger.debug(
                        f"Plan {plan.plan_id}: Confluence {base_confluence:.1f} < dynamic threshold {dynamic_threshold:.1f} "
                        f"(Symbol: {symbol_norm}, ATR Ratio: {threshold_calc.get('atr_ratio', 1.0):.2f}, "
                        f"Session: {threshold_calc.get('session', 'UNKNOWN')}, "
                        f"Base: {threshold_calc.get('base_confidence', 60)}, "
                        f"Bias: {threshold_calc.get('session_bias', 1.0):.2f})"
                    )
                    return False
                else:
                    logger.info(
                        f"Plan {plan.plan_id}: Dynamic threshold check passed - "
                        f"Confluence {base_confluence:.1f} >= Threshold {dynamic_threshold:.1f} "
                        f"(ATR: {threshold_calc.get('atr_ratio', 1.0):.2f}x, Session: {threshold_calc.get('session', 'UNKNOWN')})"
                    )
            else:
                # Fallback: Compute dynamic threshold on-the-fly if not in M1 data (Phase 2.3)
                if self.threshold_manager and self.session_manager:
                    try:
                        # Calculate ATR ratio
                        atr_current = m1_data.get('volatility', {}).get('atr', 0)
                        atr_median = m1_data.get('volatility', {}).get('atr_median', atr_current)
                        atr_ratio = atr_current / atr_median if atr_median > 0 else 1.0
                        
                        # Get current session
                        session = self.session_manager.get_current_session()
                        
                        # Compute dynamic threshold
                        dynamic_threshold = self.threshold_manager.compute_threshold(
                            symbol=symbol_norm,
                            session=session,
                            atr_ratio=atr_ratio
                        )
                        
                        base_confluence = m1_data.get('microstructure_confluence', {}).get('score', 0)
                        if base_confluence < dynamic_threshold:
                            logger.debug(
                                f"Plan {plan.plan_id}: Fallback threshold check failed - "
                                f"Confluence {base_confluence:.1f} < Dynamic Threshold {dynamic_threshold:.1f} "
                                f"(ATR: {atr_ratio:.2f}x, Session: {session})"
                            )
                            return False
                        else:
                            logger.info(
                                f"Plan {plan.plan_id}: Fallback dynamic threshold passed - "
                                f"Confluence {base_confluence:.1f} >= Threshold {dynamic_threshold:.1f} "
                                f"(ATR: {atr_ratio:.2f}x, Session: {session})"
                            )
                    except Exception as e:
                        logger.warning(f"Error computing fallback dynamic threshold: {e}")
                        # Continue to next fallback
                        pass
                
                # Final fallback: Session-adjusted threshold if threshold_manager not available
                if self.session_manager:
                    try:
                        session_profile = self.session_manager.get_session_profile(session=current_session, symbol=symbol_norm)
                        session_bias = session_profile.get('session_bias_factor', 1.0)
                        adjusted_threshold = threshold * session_bias
                        base_confluence = m1_data.get('microstructure_confluence', {}).get('score', 0)
                        if base_confluence < adjusted_threshold:
                            logger.debug(
                                f"Plan {plan.plan_id}: Confluence {base_confluence:.1f} < session-adjusted threshold {adjusted_threshold:.1f} "
                                f"(Session: {current_session}, Bias: {session_bias:.2f})"
                            )
                            return False
                    except:
                        pass  # Fallback to default threshold
            
            # Log M1 context (Phase 2.1.1)
            choch_bos = m1_data.get('choch_bos', {})
            base_confluence = m1_data.get('microstructure_confluence', {}).get('score', 0)
            logger.info(
                f"M1 validation passed for {plan.plan_id}: "
                f"CHOCH={choch_bos.get('has_choch', False)}, "
                f"BOS={choch_bos.get('has_bos', False)}, "
                f"Confidence={confidence:.1f}, "
                f"Confluence={base_confluence:.1f}, "
                f"Session={current_session}"
            )
            
            return True
            
        except Exception as e:
            logger.warning(f"Error in M1 validation for plan {plan.plan_id}: {e}")
            return True  # Don't block execution on M1 validation errors
    
    def _get_mtf_analysis(self, symbol: str):
        """Get multi-timeframe analysis for symbol"""
        try:
            # Option 1: Use analyzer passed in __init__ (preferred)
            if hasattr(self, 'mtf_analyzer') and self.mtf_analyzer:
                return self.mtf_analyzer.analyze(symbol)
            
            # Option 2: Lazy initialization (fallback)
            if not hasattr(self, '_mtf_analyzer') or self._mtf_analyzer is None:
                from infra.multi_timeframe_analyzer import MultiTimeframeAnalyzer
                from infra.indicator_bridge import IndicatorBridge
                
                # Need indicator_bridge and mt5_service
                if hasattr(self, 'mt5_service') and self.mt5_service:
                    indicator_bridge = IndicatorBridge(self.mt5_service)
                    self._mtf_analyzer = MultiTimeframeAnalyzer(indicator_bridge, self.mt5_service)
                else:
                    logger.debug("MT5 service not available for MTF analysis")
                    return None
            
            return self._mtf_analyzer.analyze(symbol)
        except Exception as e:
            logger.debug(f"Could not get MTF analysis: {e}")
            return None
    
    def _extract_atr_from_cached_analysis(self, symbol_norm: str) -> float:
        """
        Extract ATR with fallbacks.
        Uses cached analysis data if available, otherwise returns 0.
        Note: This is a synchronous method - does not make API calls.
        """
        try:
            # Check if we have cached analysis data (if system caches it)
            # Otherwise, ATR validation will be skipped (non-critical)
            # For now, return 0 and let the validation be optional
            
            # TODO: If system caches analyse_symbol_full results, extract from cache
            # For immediate implementation, ATR validation will be optional
            return 0.0
        except Exception as e:
            logger.debug(f"Error extracting ATR for {symbol_norm}: {e}")
            return 0.0
    
    def _get_confluence_score(self, symbol: str) -> int:
        """
        Get confluence score with caching to avoid frequent API calls.
        
        Uses existing ConfluenceCalculator via API endpoint or fallback to MTF analysis.
        ⚠️ IMPORTANT: Symbol should be normalized before calling this method.
        """
        # Normalize symbol for consistency (use same normalization as _check_conditions)
        # This ensures cache keys match even if caller passes unnormalized symbol
        # ⚠️ FIX: Always add lowercase 'c' - rstrip removes any existing 'C' or 'c'
        symbol_base = symbol.upper().rstrip('Cc')
        symbol_norm = symbol_base + 'c'  # Always add lowercase 'c' for MT5
        
        now = time.time()
        
        # Thread-safe cache access (lock must exist from __init__)
        with self._confluence_cache_lock:
            # Check cache first
            if symbol_norm in self._confluence_cache:
                score, timestamp = self._confluence_cache[symbol_norm]
                if now - timestamp < self._confluence_cache_ttl:
                    logger.debug(f"Using cached confluence score for {symbol_norm}: {score}")
                    # Update stats (must exist from __init__)
                    self._confluence_cache_stats["hits"] += 1
                    return score
        
        # Calculate fresh (use existing implementation)
        try:
            # Option 1: Use existing confluence API (synchronous)
            response = requests.get(f"http://localhost:8000/api/v1/confluence/{symbol_norm}", timeout=5.0)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                except (ValueError, json.JSONDecodeError) as e:
                    logger.warning(f"Invalid JSON response from confluence API for {symbol_norm}: {e}")
                    raise  # Re-raise to fall through to next try block
                
                # API returns {"confluence_score": float, "grade": str, ...}
                score = data.get("confluence_score", 50)
                # Validate score type and range (0-100)
                if score is None:
                    score = 50
                try:
                    score = int(float(score))  # Handle float scores
                except (ValueError, TypeError):
                    logger.warning(f"Invalid confluence_score type for {symbol_norm}: {type(score)}")
                    score = 50
                score = max(0, min(100, score))  # Clamp to valid range
                
                # Cache the result (thread-safe, lock must exist from __init__)
                # Note: Stats updates are inside lock for thread safety
                with self._confluence_cache_lock:
                    self._confluence_cache[symbol_norm] = (score, now)
                    # Update stats (must exist from __init__) - thread-safe inside lock
                    self._confluence_cache_stats["misses"] += 1
                    self._confluence_cache_stats["api_calls"] += 1  # Only for actual API calls
                logger.debug(f"Cached confluence score for {symbol_norm}: {score}")
                return score
        except Exception as e:
            logger.warning(f"Confluence API call failed for {symbol_norm}: {e}")
        except AttributeError:
            # Handle case where response object doesn't have status_code (connection error, etc.)
            logger.warning(f"Confluence API connection failed for {symbol_norm}")
        else:
            # Handle non-200 status codes
            if hasattr(response, 'status_code'):
                if response.status_code == 404:
                    logger.warning(f"Confluence API endpoint not found for {symbol_norm}")
                else:
                    logger.warning(f"Confluence API returned status {response.status_code} for {symbol_norm}")
        
        try:
            # Option 2: Calculate from MTF analysis alignment score
            mtf_analysis = self._get_mtf_analysis(symbol_norm)
            if mtf_analysis and isinstance(mtf_analysis, dict) and len(mtf_analysis) > 0:
                alignment_score = mtf_analysis.get("alignment_score", 0)
                # Validate alignment_score type
                if alignment_score is None:
                    alignment_score = 0
                try:
                    score = int(float(alignment_score))  # Handle float scores
                except (ValueError, TypeError):
                    logger.warning(f"Invalid alignment_score type for {symbol_norm}: {type(alignment_score)}")
                    score = 0
                # Validate score range (0-100)
                score = max(0, min(100, score))  # Clamp to valid range
                
                # Cache the result (thread-safe, lock must exist from __init__)
                # Note: Stats updates are inside lock for thread safety
                # Note: MTF fallback doesn't increment "api_calls" (it's not an API call)
                with self._confluence_cache_lock:
                    self._confluence_cache[symbol_norm] = (score, now)
                    # Update stats (must exist from __init__) - thread-safe inside lock
                    self._confluence_cache_stats["misses"] += 1  # Cache miss, but not an API call
                return score
        except Exception as e:
            logger.warning(f"MTF analysis fallback failed for {symbol_norm}: {e}")
        
        # Default fallback (don't cache default values)
        # NOTE: Default 50 is used when calculation fails
        # This will cause confluence check to fail if threshold > 50
        # This is correct behavior (fail-safe - better to not execute than execute with invalid data)
        logger.warning(f"Using default confluence score (50) for {symbol_norm} - calculation failed")
        return 50
    
    def _invalidate_confluence_cache(self, symbol: str = None):
        """
        Invalidate confluence cache for symbol (or all if None).
        Useful for forcing fresh calculation when needed.
        """
        # Lock must exist from __init__
        with self._confluence_cache_lock:
            if symbol:
                # Normalize symbol before invalidating
                symbol_base = symbol.upper().rstrip('Cc')
                symbol_norm = symbol_base + 'c'
                self._confluence_cache.pop(symbol_norm, None)
                logger.debug(f"Invalidated confluence cache for {symbol_norm}")
            else:
                self._confluence_cache.clear()
                logger.debug("Invalidated all confluence cache")
    
    def _get_liquidity_context(self, symbol: str, entry_price: float):
        """Get liquidity context (VWAP position, PDH/PDL proximity)"""
        try:
            if self.m1_analyzer and self.m1_data_fetcher:
                # Check if fetch_m1_data method exists
                if not hasattr(self.m1_data_fetcher, 'fetch_m1_data'):
                    logger.debug(f"m1_data_fetcher does not have fetch_m1_data method")
                    return None
                
                m1_candles = self.m1_data_fetcher.fetch_m1_data(symbol, count=200)
                if m1_candles:
                    m1_analysis = self.m1_analyzer.analyze_microstructure(
                        symbol=symbol,
                        candles=m1_candles,
                        current_price=entry_price
                    )
                    if m1_analysis:
                        vwap = m1_analysis.get("vwap", {}).get("value")
                        if vwap:
                            position = "above_midpoint" if entry_price > vwap else "below_midpoint"
                            return {"position": position, "vwap": vwap}
        except AttributeError as e:
            logger.debug(f"m1_data_fetcher.fetch_m1_data not available: {e}")
            return None
        except Exception as e:
            logger.debug(f"Could not get liquidity context: {e}")
        return None
    
    def _check_m1_conditions(self, plan: TradePlan, m1_data: Dict[str, Any]) -> bool:
        """
        Check M1-specific conditions from plan.
        
        Args:
            plan: Trade plan
            m1_data: M1 microstructure analysis data
            
        Returns:
            True if all M1 conditions are met
        """
        conditions = plan.conditions
        
        # Skip M1 CHOCH/BOS checks for forex pairs (only BTC and XAU use these)
        symbol_norm = plan.symbol.upper().replace('C', '')  # Normalize symbol
        if self._is_forex_pair(symbol_norm):
            # For forex pairs, skip CHOCH/BOS checks
            if conditions.get('m1_choch', False) or conditions.get('m1_bos', False) or conditions.get('m1_choch_bos_combo', False):
                logger.debug(f"Skipping M1 CHOCH/BOS checks for forex pair {symbol_norm}")
                return False  # Don't allow M1 CHOCH/BOS conditions for forex pairs
        
        choch_bos = m1_data.get('choch_bos', {})
        
        # M1 CHOCH condition
        if conditions.get('m1_choch', False):
            has_choch = choch_bos.get('has_choch', False)
            choch_confirmed = choch_bos.get('choch_confirmed', False)
            if not (has_choch and choch_confirmed):
                logger.debug(f"M1 CHOCH condition not met: has_choch={has_choch}, confirmed={choch_confirmed}")
                return False
        
        # M1 BOS condition
        if conditions.get('m1_bos', False):
            has_bos = choch_bos.get('has_bos', False)
            if not has_bos:
                logger.debug(f"M1 BOS condition not met")
                return False
        
        # M1 CHOCH + BOS combo
        if conditions.get('m1_choch_bos_combo', False):
            choch_bos_combo = choch_bos.get('choch_bos_combo', False)
            if not choch_bos_combo:
                logger.debug(f"M1 CHOCH+BOS combo condition not met")
                return False
        
        # M1 Volatility conditions
        volatility = m1_data.get('volatility', {})
        if conditions.get('m1_volatility_contracting', False):
            if volatility.get('state') != 'CONTRACTING':
                return False
        
        if conditions.get('m1_volatility_expanding', False):
            if volatility.get('state') != 'EXPANDING':
                return False
        
        if 'm1_squeeze_duration' in conditions:
            squeeze_duration = volatility.get('squeeze_duration', 0)
            if squeeze_duration < conditions['m1_squeeze_duration']:
                return False
        
        # M1 Momentum quality
        if 'm1_momentum_quality' in conditions:
            required_quality = conditions['m1_momentum_quality']
            momentum = m1_data.get('momentum', {})
            actual_quality = momentum.get('quality', 'CHOPPY')
            quality_hierarchy = {'CHOPPY': 0, 'FAIR': 1, 'GOOD': 2, 'EXCELLENT': 3}
            if quality_hierarchy.get(actual_quality, 0) < quality_hierarchy.get(required_quality, 0):
                return False
        
        # M1 Structure type
        if 'm1_structure_type' in conditions:
            structure = m1_data.get('structure', {})
            if structure.get('type') != conditions['m1_structure_type']:
                return False
        
        # M1 Trend alignment
        if 'm1_trend_alignment' in conditions:
            trend_context = m1_data.get('trend_context', {})
            alignment = trend_context.get('alignment', 'WEAK')
            required_alignment = conditions['m1_trend_alignment']
            alignment_hierarchy = {'WEAK': 0, 'MODERATE': 1, 'STRONG': 2}
            if alignment_hierarchy.get(alignment, 0) < alignment_hierarchy.get(required_alignment, 0):
                return False
        
        # M1 Signal summary
        if 'm1_signal_summary' in conditions:
            required_signal = conditions['m1_signal_summary']
            actual_signal = m1_data.get('signal_summary', 'NEUTRAL')
            if actual_signal != required_signal:
                return False
        
        # M1 Rejection wick condition
        if 'm1_rejection_wick' in conditions and conditions['m1_rejection_wick']:
            rejection_wicks = m1_data.get('rejection_wicks', [])
            if not rejection_wicks:
                return False
            # Check if any rejection wick is near entry price
            tolerance = plan.conditions.get('tolerance')
            if tolerance is None:
                from infra.tolerance_helper import get_price_tolerance
                tolerance = get_price_tolerance(plan.symbol)
            # Check if any wick is near entry
            near_entry = any(
                abs(wick.get('price', 0) - plan.entry_price) <= tolerance
                for wick in rejection_wicks
            )
            if not near_entry:
                return False
        
        # M1 Order block condition
        if 'm1_order_block' in conditions and conditions['m1_order_block']:
            order_blocks = m1_data.get('order_blocks', [])
            if not order_blocks:
                return False
            # Check if any order block contains entry price
            tolerance = plan.conditions.get('tolerance')
            if tolerance is None:
                from infra.tolerance_helper import get_price_tolerance
                tolerance = get_price_tolerance(plan.symbol)
            # Check if entry price is within any order block range
            in_order_block = False
            for ob in order_blocks:
                price_range = ob.get('price_range', [])
                if len(price_range) == 2:
                    block_low = min(price_range)
                    block_high = max(price_range)
                    if block_low - tolerance <= plan.entry_price <= block_high + tolerance:
                        in_order_block = True
                        break
            if not in_order_block:
                return False
        
        return True
    
    def _calculate_m1_confidence(
        self,
        m1_data: Dict[str, Any],
        symbol: str,
        use_rolling_mean: bool = False
    ) -> float:
        """
        Calculate M1 confidence score using linear + sigmoid weighting.
        
        Args:
            m1_data: M1 microstructure analysis data
            symbol: Symbol name (for symbol-specific threshold)
            use_rolling_mean: Whether to use rolling mean over last 5 signals
            
        Returns:
            Confidence score (0-100)
        """
        try:
            choch_bos = m1_data.get('choch_bos', {})
            volatility = m1_data.get('volatility', {})
            rejection_wicks = m1_data.get('rejection_wicks', [])
            
            # Component scores
            choch_conf = choch_bos.get('confidence', 0)
            volatility_state = volatility.get('state', 'STABLE')
            volatility_conf = {
                'EXPANDING': 90,
                'CONTRACTING': 60,
                'STABLE': 70
            }.get(volatility_state, 70)
            
            # Rejection wick confidence (average of all wicks)
            rejection_conf = 0
            if rejection_wicks:
                wick_confidences = []
                for wick in rejection_wicks:
                    wick_ratio = wick.get('wick_ratio', 0)
                    body_ratio = wick.get('body_ratio', 0)
                    # Higher wick ratio = higher confidence
                    wick_score = min(100, wick_ratio * 30)  # Scale wick ratio to 0-100
                    # Lower body ratio = higher confidence (more rejection)
                    body_penalty = body_ratio * 20  # Penalize large bodies
                    wick_conf = max(0, wick_score - body_penalty)
                    wick_confidences.append(wick_conf)
                rejection_conf = sum(wick_confidences) / len(wick_confidences) if wick_confidences else 0
            else:
                rejection_conf = 50  # Neutral if no rejection wicks
            
            # Linear weighting (base)
            linear_confidence = (
                0.5 * choch_conf +
                0.3 * volatility_conf +
                0.2 * rejection_conf
            )
            
            # Get symbol-specific threshold
            threshold = 60  # Default (reduced from 70%)
            if self.asset_profiles:
                threshold = self.asset_profiles.get_confluence_minimum(symbol)
            
            # Sigmoid scaling (smooths threshold transition)
            confidence = self._sigmoid_scaling(
                linear_confidence,
                threshold=threshold,
                steepness=0.1
            )
            
            # Debug logging if enabled
            if self.config.get('choch_detection', {}).get('debug_confidence_weights', False):
                logger.debug(
                    f"Confidence weights for {symbol}: "
                    f"choch=0.5*{choch_conf:.1f}, vol=0.3*{volatility_conf:.1f}, "
                    f"rejection=0.2*{rejection_conf:.1f} → linear={linear_confidence:.1f} → "
                    f"sigmoid={confidence:.1f} (threshold={threshold})"
                )
            
            # Rolling mean (optional, smooths microstructure noise)
            if use_rolling_mean:
                if not hasattr(self, '_confidence_history'):
                    self._confidence_history = {}
                if symbol not in self._confidence_history:
                    self._confidence_history[symbol] = []
                
                self._confidence_history[symbol].append(confidence)
                # Keep only last 5
                if len(self._confidence_history[symbol]) > 5:
                    self._confidence_history[symbol] = self._confidence_history[symbol][-5:]
                
                # Return rolling mean
                return sum(self._confidence_history[symbol]) / len(self._confidence_history[symbol])
            
            return confidence
            
        except Exception as e:
            logger.warning(f"Error calculating M1 confidence: {e}")
            return 50  # Default neutral confidence
    
    def _sigmoid_scaling(self, value: float, threshold: float, steepness: float = 0.1) -> float:
        """
        Apply sigmoid scaling to smooth threshold transition.
        
        Args:
            value: Input value
            threshold: Threshold value
            steepness: Steepness parameter (lower = smoother)
            
        Returns:
            Scaled value
        """
        import math
        # Sigmoid function centered at threshold
        x = (value - threshold) / (threshold * steepness)
        sigmoid = 1 / (1 + math.exp(-x))
        # Scale to 0-100 range
        return threshold + (100 - threshold) * sigmoid
    
    def _validate_rejection_wick(self, plan: TradePlan, m1_data: Dict[str, Any], current_price: float) -> bool:
        """
        Validate rejection wick using M1 microstructure (filters fake dojis).
        
        Args:
            plan: Trade plan
            m1_data: M1 microstructure analysis
            current_price: Current price
            
        Returns:
            True if rejection wick is valid
        """
        try:
            rejection_wicks = m1_data.get('rejection_wicks', [])
            if not rejection_wicks:
                # No rejection wicks detected, skip validation
                return True
            
            # Check if any rejection wick is near entry price
            tolerance = plan.conditions.get('tolerance')
            if tolerance is None:
                from infra.tolerance_helper import get_price_tolerance
                tolerance = get_price_tolerance(plan.symbol)
            
            for wick in rejection_wicks:
                wick_price = wick.get('price', 0)
                wick_ratio = wick.get('wick_ratio', 0)
                body_ratio = wick.get('body_ratio', 0)
                
                # Check if wick is near entry price
                if abs(wick_price - plan.entry_price) <= tolerance:
                    # Validate wick quality (filter fake dojis)
                    # Good wick: high wick ratio, low body ratio
                    if wick_ratio >= 2.0 and body_ratio <= 0.5:
                        logger.debug(f"Valid rejection wick detected at {wick_price}")
                        return True
            
            # If plan requires rejection wick but none found near entry
            if plan.conditions.get('m1_rejection_wick', False):
                logger.debug(f"No valid rejection wick near entry price {plan.entry_price}")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error validating rejection wick: {e}")
            return True  # Don't block on validation errors
    
    def _detect_liquidity_sweep(self, plan: TradePlan, m1_data: Dict[str, Any], current_price: float) -> bool:
        """
        Detect liquidity sweep using M1 liquidity zones.
        
        Args:
            plan: Trade plan
            m1_data: M1 microstructure analysis
            current_price: Current price
            
        Returns:
            True if liquidity sweep detected (can improve stop-loss placement)
        """
        try:
            liquidity_zones = m1_data.get('liquidity_zones', [])
            liquidity_state = m1_data.get('liquidity_state', 'AWAY')
            
            # Check if price is near a liquidity zone (potential sweep)
            tolerance = plan.conditions.get('tolerance')
            if tolerance is None:
                from infra.tolerance_helper import get_price_tolerance
                tolerance = get_price_tolerance(plan.symbol)
            
            for zone in liquidity_zones:
                zone_price = zone.get('price', 0)
                zone_type = zone.get('type', '')
                
                # Check if price swept through zone
                if abs(current_price - zone_price) <= tolerance:
                    # Sweep detected - can use tighter stop-loss
                    logger.info(
                        f"Liquidity sweep detected at {zone_type} {zone_price} for {plan.plan_id}. "
                        f"Consider tighter stop-loss (1.5-2 ATR sharper)"
                    )
                    return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error detecting liquidity sweep: {e}")
            return False
    
    def _validate_vwap_microstructure_combo(self, plan: TradePlan, m1_data: Dict[str, Any]) -> bool:
        """
        Validate VWAP + Microstructure combo for enhanced signal confirmation.
        
        Args:
            plan: Trade plan
            m1_data: M1 microstructure analysis
            
        Returns:
            True if VWAP and microstructure align
        """
        try:
            # Get VWAP state from M1 data (if available)
            # Note: VWAP calculation should be done in M1 analyzer
            signal_summary = m1_data.get('signal_summary', 'NEUTRAL')
            structure = m1_data.get('structure', {})
            structure_type = structure.get('type', 'CHOPPY')
            
            # Check if plan direction aligns with microstructure
            if plan.direction == "BUY":
                # Bullish microstructure expected
                if signal_summary != "BULLISH_MICROSTRUCTURE":
                    logger.debug(f"VWAP/Microstructure mismatch: BUY plan but signal is {signal_summary}")
                    return False
                # Structure should be bullish
                if structure_type not in ['HIGHER_HIGH', 'HIGHER_LOW']:
                    logger.debug(f"Structure not bullish: {structure_type}")
                    return False
            elif plan.direction == "SELL":
                # Bearish microstructure expected
                if signal_summary != "BEARISH_MICROSTRUCTURE":
                    logger.debug(f"VWAP/Microstructure mismatch: SELL plan but signal is {signal_summary}")
                    return False
                # Structure should be bearish
                if structure_type not in ['LOWER_LOW', 'LOWER_HIGH']:
                    logger.debug(f"Structure not bearish: {structure_type}")
                    return False
            
            logger.debug(f"VWAP/Microstructure combo validated for {plan.plan_id}")
            return True
            
        except Exception as e:
            logger.warning(f"Error validating VWAP/Microstructure combo: {e}")
            return True  # Don't block on validation errors
    
    def _batch_refresh_m1_data(self):
        """
        Batch refresh M1 data for all active symbols in parallel (Phase 2.1.1).
        
        Performance optimization: Uses asyncio.gather() for parallel refresh.
        """
        if not self.m1_refresh_manager or not self.m1_data_fetcher:
            return
        
        try:
            # Get all unique symbols from pending plans
            active_symbols = set()
            with self.plans_lock:
                plans_list = list(self.plans.values())
            for plan in plans_list:
                if plan.status == "pending" and plan.symbol:
                    symbol_base = plan.symbol.upper().rstrip('Cc')
                    symbol_norm = symbol_base + 'c'
                    active_symbols.add(symbol_norm)
            
            if not active_symbols:
                return
            
            # Check which symbols need refresh
            symbols_to_refresh = []
            for symbol in active_symbols:
                # Check cache first
                cache_age = time.time() - self._m1_cache_timestamps.get(symbol, 0)
                cache_duration = self.config.get('m1_integration', {}).get('cache_duration_seconds', 30)
                
                # Refresh if cache expired or data is stale
                if cache_age > cache_duration or self.m1_refresh_manager.check_and_refresh_stale(symbol, max_age_seconds=180):
                    symbols_to_refresh.append(symbol)
            
            # Batch refresh in parallel
            if symbols_to_refresh:
                import asyncio
                try:
                    asyncio.run(self.m1_refresh_manager.refresh_symbols_batch(symbols_to_refresh))
                    logger.debug(f"Batch refreshed M1 data for {len(symbols_to_refresh)} symbols")
                except Exception as e:
                    logger.warning(f"Error in batch refresh: {e}")
        
        except Exception as e:
            logger.warning(f"Error in batch M1 refresh: {e}")
    
    def _is_m1_signal_stale(self, plan: TradePlan) -> bool:
        """
        Check if M1 signal is stale for a plan (Phase 2.1.1).
        
        Args:
            plan: Trade plan to check
            
        Returns:
            True if signal is stale, False otherwise
        """
        if not self.m1_analyzer or not plan.symbol:
            return False
        
        try:
            # Get cached M1 data or fetch fresh
            symbol_base = plan.symbol.upper().rstrip('Cc')
            symbol_norm = symbol_base + 'c'
            
            # Check cache
            cache_age = time.time() - self._m1_cache_timestamps.get(symbol_norm, 0)
            cache_duration = self.config.get('m1_integration', {}).get('cache_duration_seconds', 30)
            
            if symbol_norm in self._m1_data_cache and cache_age < cache_duration:
                m1_data = self._m1_data_cache[symbol_norm]['data']
            else:
                # Fetch fresh data
                if not self.m1_data_fetcher:
                    return False
                
                m1_candles = self.m1_data_fetcher.fetch_m1_data(symbol_norm, count=200)
                if not m1_candles or len(m1_candles) < 50:
                    return False
                
                m1_data = self.m1_analyzer.analyze_microstructure(
                    symbol=symbol_norm,
                    candles=m1_candles
                )
                
                # Update cache
                self._m1_data_cache[symbol_norm] = {
                    'data': m1_data,
                    'timestamp': time.time(),
                    'last_signal_timestamp': m1_data.get('last_signal_timestamp') if m1_data else None
                }
                self._m1_cache_timestamps[symbol_norm] = time.time()
            
            if not m1_data or not m1_data.get('available'):
                return False
            
            # Check signal age
            signal_age = m1_data.get('signal_age_seconds', 0)
            stale_threshold = self.config.get('m1_integration', {}).get('signal_stale_threshold_seconds', 300)
            
            if signal_age > stale_threshold:
                logger.debug(
                    f"Plan {plan.plan_id}: M1 signal is stale "
                    f"(age: {signal_age:.0f}s > threshold: {stale_threshold}s)"
                )
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking M1 signal staleness: {e}")
            return False
    
    def _get_cached_m1_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get cached M1 data if available and fresh (Phase 2.1.1).
        
        Args:
            symbol: Symbol name
            
        Returns:
            Cached M1 data or None if not available/fresh
        """
        symbol_base = symbol.upper().rstrip('Cc')
        symbol_norm = symbol_base + 'c'
        
        if symbol_norm not in self._m1_data_cache:
            return None
        
        cache_age = time.time() - self._m1_cache_timestamps.get(symbol_norm, 0)
        cache_duration = self.config.get('m1_integration', {}).get('cache_duration_seconds', 30)
        
        if cache_age > cache_duration:
            # Cache expired
            if symbol_norm in self._m1_data_cache:
                del self._m1_data_cache[symbol_norm]
            if symbol_norm in self._m1_cache_timestamps:
                del self._m1_cache_timestamps[symbol_norm]
            return None
        
        return self._m1_data_cache[symbol_norm]['data']
    
    def _get_cached_correlation(self, cache_key: str) -> Optional[Any]:
        """
        Get cached correlation calculation result.
        
        Args:
            cache_key: Cache key (e.g., "dxy_change_BTCUSDc")
        
        Returns:
            Cached result or None if not cached or expired
        """
        with self._correlation_cache_lock:
            if cache_key in self._correlation_cache:
                result, timestamp = self._correlation_cache[cache_key]
                age_seconds = (datetime.now(timezone.utc) - timestamp).total_seconds()
                if age_seconds < self._correlation_cache_ttl:
                    return result
                else:
                    # Expired - remove from cache
                    del self._correlation_cache[cache_key]
            return None
    
    def _cache_correlation(self, cache_key: str, result: Any):
        """
        Cache correlation calculation result.
        
        Args:
            cache_key: Cache key (e.g., "dxy_change_BTCUSDc")
            result: Result to cache
        """
        with self._correlation_cache_lock:
            self._correlation_cache[cache_key] = (result, datetime.now(timezone.utc))
            # Limit cache size (remove oldest entries if > 100)
            if len(self._correlation_cache) > 100:
                # Remove oldest entry (simple FIFO - could be improved with LRU)
                oldest_key = min(self._correlation_cache.keys(), 
                               key=lambda k: self._correlation_cache[k][1])
                del self._correlation_cache[oldest_key]
    
    def _cache_m1_data(self, symbol: str, m1_data: Dict[str, Any]):
        """
        Cache M1 data for performance optimization (Phase 2.1.1).
        
        Args:
            symbol: Symbol name
            m1_data: M1 analysis data
        """
        symbol_base = symbol.upper().rstrip('Cc')
        symbol_norm = symbol_base + 'c'
        
        # Track signal timestamp for change detection
        last_signal_ts = m1_data.get('last_signal_timestamp') if m1_data else None
        if last_signal_ts:
            self._last_signal_timestamps[symbol_norm] = last_signal_ts
        
        self._m1_data_cache[symbol_norm] = {
            'data': m1_data,
            'timestamp': time.time(),
            'last_signal_timestamp': last_signal_ts
        }
        self._m1_cache_timestamps[symbol_norm] = time.time()
    
    def _has_m1_signal_changed(self, plan: TradePlan) -> bool:
        """
        Detect if M1 signal has changed since last check (Phase 2.1.1).
        
        Args:
            plan: Trade plan to check
            
        Returns:
            True if signal changed, False otherwise
        """
        if not self.m1_analyzer or not plan.symbol:
            return False
        
        try:
            symbol_base = plan.symbol.upper().rstrip('Cc')
            symbol_norm = symbol_base + 'c'
            
            # Get current M1 data
            m1_data = self._get_cached_m1_data(symbol_norm)
            if not m1_data:
                return False  # No data to compare
            
            current_signal_ts = m1_data.get('last_signal_timestamp')
            if not current_signal_ts:
                return False
            
            # Compare with last known signal timestamp
            last_known_ts = self._last_signal_timestamps.get(symbol_norm)
            
            if last_known_ts is None:
                # First time seeing this signal
                self._last_signal_timestamps[symbol_norm] = current_signal_ts
                return False
            
            # Signal changed if timestamp is different
            if current_signal_ts != last_known_ts:
                self._last_signal_timestamps[symbol_norm] = current_signal_ts
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error detecting M1 signal change: {e}")
            return False
    
    def _handle_post_execution(
        self,
        plan: TradePlan,
        result: Dict[str, Any],
        executed_price: float,
        symbol_norm: str,
        direction: str,
        lot_size: float
    ) -> None:
        """
        Handle post-execution steps for both market orders and filled pending orders.
        
        This method extracts all post-execution logic from _execute_trade() so it can
        be reused for both market orders and filled pending orders.
        
        Args:
            plan: TradePlan that was executed (status should already be "executed")
            result: Result dict from order execution
            executed_price: Actual execution price
            symbol_norm: Normalized symbol (e.g., "XAUUSDc")
            direction: Trade direction ("BUY" or "SELL")
            lot_size: Trade volume
        """
        ticket = result.get("details", {}).get("ticket")
        if not ticket:
            logger.warning(f"No ticket in result for plan {plan.plan_id} - skipping post-execution")
            return
        
        # Phase 3.1: Store entry delta for order flow flip exit detection
        entry_delta = None
        if plan.symbol.upper().startswith('BTC'):
            try:
                if self.micro_scalp_engine and hasattr(self.micro_scalp_engine, 'btc_order_flow'):
                    btc_flow = self.micro_scalp_engine.btc_order_flow
                    metrics = self._get_btc_order_flow_metrics(plan, window_seconds=30)
                    if metrics:
                        entry_delta = metrics.delta_volume
                        logger.debug(f"Phase 3.1: Stored entry delta {entry_delta:.2f} for ticket {ticket}")
            except Exception as e:
                logger.debug(f"Error getting entry delta for ticket {ticket}: {e}")
        
        # Store entry delta in intelligent exit manager if available
        if entry_delta is not None:
            try:
                # Try to get intelligent exit manager from chatgpt_bot module
                import chatgpt_bot
                if hasattr(chatgpt_bot, 'intelligent_exit_manager'):
                    exit_manager = chatgpt_bot.intelligent_exit_manager
                    if exit_manager and ticket in exit_manager.rules:
                        rule = exit_manager.rules[ticket]
                        if hasattr(rule, 'metadata'):
                            rule.metadata['entry_delta'] = entry_delta
                            logger.info(f"Phase 3.1: Entry delta {entry_delta:.2f} stored in exit rule for ticket {ticket}")
            except Exception as e:
                logger.debug(f"Error storing entry delta in exit manager: {e}")
        
        # Phase 4.5: Record strategy name for performance tracking
        strategy_name = None
        if plan.conditions:
            strategy_name = plan.conditions.get("strategy_type") or plan.conditions.get("strategy")
        
        if strategy_name:
            try:
                # Store strategy name in plan notes for later retrieval when trade closes
                if plan.notes:
                    plan.notes += f" [strategy:{strategy_name}]"
                else:
                    plan.notes = f"[strategy:{strategy_name}]"
                logger.debug(f"Recorded strategy {strategy_name} for plan {plan.plan_id} (will track on close)")
            except Exception as e:
                logger.warning(f"Failed to record strategy for performance tracking: {e}")
                # Don't fail execution if tracking fails
        
        # Get strategy_type from plan conditions (accept both strategy_type and plan_type for compatibility)
        strategy_type = None
        if plan.conditions:
            strategy_type = plan.conditions.get("strategy_type") or plan.conditions.get("plan_type")
        
        # ⚠️ CRITICAL: Registration order matters! Universal Manager must register BEFORE DTMS
        # Check if this is a universal-managed strategy
        try:
            from infra.universal_sl_tp_manager import (
                UniversalDynamicSLTPManager,
                UNIVERSAL_MANAGED_STRATEGIES,
                StrategyType
            )
            
            # Normalize strategy_type to StrategyType enum if it's a string
            strategy_type_enum = None
            if strategy_type:
                if isinstance(strategy_type, str):
                    # Try to match string to enum value
                    for st in StrategyType:
                        if st.value == strategy_type:
                            strategy_type_enum = st
                            break
                elif isinstance(strategy_type, StrategyType):
                    strategy_type_enum = strategy_type
            
            # ⚠️ CRITICAL: Always register with Universal Manager (even without strategy_type)
            # If no strategy_type provided, Universal Manager uses DEFAULT_STANDARD (generic trailing)
            # This ensures ALL trades get proper trailing stop management
            try:
                # Get or create Universal Manager instance
                # Note: In production, this should be a singleton or passed in via __init__
                universal_sl_tp_manager = UniversalDynamicSLTPManager(
                    mt5_service=self.mt5_service
                )
                
                # Register with Universal Manager (strategy_type can be None - will use DEFAULT_STANDARD)
                trade_state = universal_sl_tp_manager.register_trade(
                    ticket=ticket,
                    symbol=symbol_norm,
                    strategy_type=strategy_type_enum,  # Can be None - will use DEFAULT_STANDARD
                    direction=direction,
                    entry_price=executed_price,
                    initial_sl=plan.stop_loss,
                    initial_tp=plan.take_profit,
                    plan_id=plan.plan_id,
                    initial_volume=lot_size
                )
                
                if trade_state:
                    strategy_name = trade_state.strategy_type.value if trade_state.strategy_type else "DEFAULT_STANDARD"
                    logger.info(
                        f"✅ Trade {ticket} registered with Universal SL/TP Manager "
                        f"(strategy: {strategy_name})"
                    )
                else:
                    logger.warning(
                        f"⚠️ Trade {ticket} registration with Universal Manager failed"
                    )
            except Exception as e:
                logger.error(
                    f"❌ Error registering trade {ticket} with Universal Manager: {e}",
                    exc_info=True
                )
            
            # DO NOT register with DTMS - Universal Manager owns this trade
            # Skip DTMS registration below
            if False:  # Changed to always skip DTMS registration
                # Not a universal-managed strategy - register with DTMS (existing behavior)
                # Auto-register to DTMS (one-liner wrapper)
                try:
                    from dtms_integration import auto_register_dtms
                    result_dict = {
                        'symbol': symbol_norm,
                        'direction': direction,
                        'entry_price': executed_price,
                        'volume': lot_size,
                        'stop_loss': plan.stop_loss,
                        'take_profit': plan.take_profit
                    }
                    auto_register_dtms(ticket, result_dict)
                except Exception:
                    pass  # Silent failure
        except ImportError as e:
            logger.warning(
                f"⚠️ Universal SL/TP Manager not available: {e}. "
                f"Falling back to DTMS registration for ticket {ticket}"
            )
            # Fallback to DTMS if Universal Manager not available
            try:
                from dtms_integration import auto_register_dtms
                result_dict = {
                    'symbol': symbol_norm,
                    'direction': direction,
                    'entry_price': executed_price,
                    'volume': lot_size,
                    'stop_loss': plan.stop_loss,
                    'take_profit': plan.take_profit
                }
                auto_register_dtms(ticket, result_dict)
            except Exception:
                pass  # Silent failure
        except Exception as e:
            logger.error(
                f"❌ Error in trade registration logic for ticket {ticket}: {e}",
                exc_info=True
            )
            # Fallback to DTMS on any error
            try:
                from dtms_integration import auto_register_dtms
                result_dict = {
                    'symbol': symbol_norm,
                    'direction': direction,
                    'entry_price': executed_price,
                    'volume': lot_size,
                    'stop_loss': plan.stop_loss,
                    'take_profit': plan.take_profit
                }
                auto_register_dtms(ticket, result_dict)
            except Exception:
                pass  # Silent failure
        
        # M1 Context in Execution Logs (Phase 2.1.1)
        m1_data = None
        if self.m1_analyzer and plan.symbol:
            try:
                symbol_base = plan.symbol.upper().rstrip('Cc')
                symbol_norm_m1 = symbol_base + 'c'
                
                # Get cached M1 data or fetch fresh
                m1_data = self._get_cached_m1_data(symbol_norm_m1)
                if not m1_data and self.m1_data_fetcher:
                    m1_candles = self.m1_data_fetcher.fetch_m1_data(symbol_norm_m1, count=200)
                    if m1_candles and len(m1_candles) >= 50:
                        m1_data = self.m1_analyzer.analyze_microstructure(
                            symbol=symbol_norm_m1,
                            candles=m1_candles
                        )
                
                if m1_data and m1_data.get('available'):
                    confidence = self._calculate_m1_confidence(m1_data, symbol_norm_m1)
                    logger.info(
                        f"M1 context for {plan.plan_id}: "
                        f"Signal={m1_data.get('signal_summary', 'N/A')}, "
                        f"CHOCH={m1_data.get('choch_bos', {}).get('has_choch', False)}, "
                        f"Volatility={m1_data.get('volatility', {}).get('state', 'N/A')}, "
                        f"Confidence={confidence:.1f}%"
                    )
            except Exception as e:
                logger.debug(f"Error logging M1 context: {e}")
        
        # Real-Time Signal Learning: Store signal outcome (Phase 2.2)
        if self.signal_learner and plan.status == 'executed' and m1_data:
            try:
                symbol_base = plan.symbol.upper().rstrip('Cc')
                symbol_norm_signal = symbol_base + 'c'
                
                # Get session from M1 data or session manager
                session = m1_data.get('session_context', {}).get('session', 'UNKNOWN')
                if not session or session == 'UNKNOWN':
                    if self.session_manager:
                        session = self.session_manager.get_current_session()
                
                # Get signal detection timestamp
                signal_detection_timestamp = m1_data.get('signal_detection_timestamp') or m1_data.get('last_signal_timestamp')
                execution_timestamp = datetime.now(timezone.utc)
                
                # Get base confluence
                base_confluence = m1_data.get('microstructure_confluence', {}).get('base_score') or \
                                m1_data.get('microstructure_confluence', {}).get('score', 0)
                
                # Calculate R:R achieved (if we have P&L data)
                rr_achieved = None
                if hasattr(plan, 'pnl') and plan.pnl is not None and plan.stop_loss:
                    risk = abs(plan.entry_price - plan.stop_loss)
                    if risk > 0:
                        rr_achieved = plan.pnl / risk
                
                # Determine signal outcome (will be updated when trade closes)
                # For now, mark as executed
                signal_outcome = "NO_TRADE"  # Will be updated to WIN/LOSS when trade closes
                
                # Store signal outcome
                event_id = self.signal_learner.store_signal_outcome(
                    symbol=symbol_norm_signal,
                    session=session,
                    confluence=base_confluence,
                    signal_outcome=signal_outcome,
                    event_type="CHOCH",  # Default, could be enhanced to detect BOS/CHOCH_BOS_COMBO
                    rr_achieved=rr_achieved,
                    signal_detection_timestamp=signal_detection_timestamp,
                    execution_timestamp=execution_timestamp,
                    base_confluence=base_confluence,
                    volatility_state=m1_data.get('volatility', {}).get('state'),
                    strategy_hint=m1_data.get('strategy_hint'),
                    initial_confidence=m1_data.get('choch_bos', {}).get('confidence'),
                    executed=True,
                    trade_id=str(plan.ticket) if plan.ticket else None
                )
                
                logger.debug(f"Stored signal outcome for {plan.plan_id}: event_id={event_id}")
                
            except Exception as e:
                logger.warning(f"Error storing signal outcome: {e}", exc_info=True)
        
        # Log to journal database with plan_id (NEW: Sync mechanism)
        try:
            from infra.journal_repo import JournalRepo
            import MetaTrader5 as mt5
            journal_repo = JournalRepo()
            
            # Get account info
            account_info = mt5.account_info()
            balance = account_info.balance if account_info else None
            equity = account_info.equity if account_info else None
            
            # Calculate R:R
            rr = None
            if plan.stop_loss and plan.take_profit:
                risk = abs(plan.entry_price - plan.stop_loss)
                reward = abs(plan.take_profit - plan.entry_price)
                rr = reward / risk if risk > 0 else None
            
            # Log trade execution with plan_id
            journal_repo.write_exec({
                "ts": int(datetime.now(timezone.utc).timestamp()),
                "symbol": symbol_norm,
                "side": plan.direction,
                "entry": executed_price,
                "sl": plan.stop_loss,
                "tp": plan.take_profit,
                "lot": lot_size,
                "ticket": ticket,
                "position": ticket,
                "balance": balance,
                "equity": equity,
                "confidence": 100,  # Auto-execution plans are high confidence
                "regime": None,
                "rr": rr,
                "notes": f"Auto-execution plan: {plan.plan_id} | {plan.notes or 'No notes'}",
                "plan_id": plan.plan_id  # NEW: Link to plan
            })
            logger.info(f"📊 Trade logged to journal with plan_id: {plan.plan_id} (ticket: {ticket})")
        except Exception as e:
            logger.warning(f"⚠️ Failed to log trade to journal: {e}", exc_info=True)
            # Don't fail execution if journal logging fails
        
        # Send Discord notification
        self._send_discord_notification(plan, result)
        
        logger.info(f"Post-execution steps completed for plan {plan.plan_id}, ticket: {ticket}")
    
    def _execute_trade(self, plan: TradePlan) -> bool:
        """Execute a trade plan using MT5Service"""
        try:
            # CRITICAL: Verify plan is still pending and atomically update to "executing" to prevent duplicates
            # Use database-level update with WHERE clause to ensure only one thread can mark it as executing
            try:
                with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                    # CRITICAL FIX: Atomically update status from "pending" to "executing" in database
                    # This prevents race conditions where multiple threads see plan as "pending"
                    cursor = conn.execute("""
                        UPDATE trade_plans 
                        SET status = 'executing' 
                        WHERE plan_id = ? AND status = 'pending'
                    """, (plan.plan_id,))
                    
                    if cursor.rowcount == 0:
                        # Plan was not pending (already executed/cancelled/expired)
                        cursor = conn.execute("SELECT status FROM trade_plans WHERE plan_id = ?", (plan.plan_id,))
                        row = cursor.fetchone()
                        status = row[0] if row else "not found"
                        logger.warning(f"Plan {plan.plan_id} status is '{status}' - cannot mark as executing, skipping")
                        return False
                    
                    conn.commit()
                    logger.debug(f"Plan {plan.plan_id} marked as 'executing' in database (prevents duplicate execution)")
            except Exception as e:
                logger.error(f"Error updating plan status to 'executing': {e}")
                # Don't continue if we can't update status - prevents duplicate executions
                return False
            
            # Get or create execution lock for this plan (thread-safe)
            with self.execution_locks_lock:
                if plan.plan_id not in self.execution_locks:
                    self.execution_locks[plan.plan_id] = threading.Lock()
                execution_lock = self.execution_locks[plan.plan_id]
            
            # Try to acquire lock (non-blocking check first)
            if not execution_lock.acquire(blocking=False):
                logger.warning(f"Plan {plan.plan_id} is already being executed - skipping duplicate execution")
                # Note: Database status is "executing" - the other thread will complete it and update to "executed"
                return False
            
            # CRITICAL: Wrap entire execution in try/finally to prevent lock leaks (Phase 0)
            try:
                # Double-check plan is not already executing (thread-safe)
                with self.executing_plans_lock:
                    if plan.plan_id in self.executing_plans:
                        logger.warning(f"Plan {plan.plan_id} already in executing_plans set - skipping")
                        return False
                    
                    # Mark as executing
                    self.executing_plans.add(plan.plan_id)
                
                # Check if this is a micro-scalp plan with a trade idea
                if plan.conditions.get("plan_type") == "micro_scalp" and "_micro_scalp_trade_idea" in plan.conditions:
                    if not self.micro_scalp_engine:
                        logger.error(f"Micro-scalp engine not available for plan {plan.plan_id}")
                        with self.executing_plans_lock:
                            self.executing_plans.discard(plan.plan_id)
                        execution_lock.release()
                        return False
                    
                    try:
                        trade_idea = plan.conditions['_micro_scalp_trade_idea']
                        exec_result = self.micro_scalp_engine.execute_trade_idea(trade_idea)
                        
                        if exec_result.get('ok'):
                            ticket = exec_result.get('ticket')
                            logger.info(f"✅ Micro-scalp trade executed: {ticket}")
                            plan.status = "executed"
                            plan.executed_at = datetime.now(timezone.utc).isoformat()
                            plan.ticket = ticket
                            
                            # Phase 4.5: Record strategy name for performance tracking
                            strategy_name = (
                                plan.conditions.get("strategy_type") or
                                plan.conditions.get("strategy")
                            )
                            if strategy_name:
                                try:
                                    if plan.notes:
                                        plan.notes += f" [strategy:{strategy_name}]"
                                    else:
                                        plan.notes = f"[strategy:{strategy_name}]"
                                    logger.debug(f"Recorded strategy {strategy_name} for micro-scalp plan {plan.plan_id}")
                                except Exception as e:
                                    logger.warning(f"Failed to record strategy for micro-scalp: {e}")
                            
                            self._update_plan_status(plan)
                            with self.executing_plans_lock:
                                self.executing_plans.discard(plan.plan_id)
                            execution_lock.release()
                            return True
                        else:
                            logger.error(f"Micro-scalp execution failed: {exec_result.get('message')}")
                            with self.executing_plans_lock:
                                self.executing_plans.discard(plan.plan_id)
                            execution_lock.release()
                            return False
                    except Exception as e:
                        logger.error(f"Error executing micro-scalp trade: {e}", exc_info=True)
                        with self.executing_plans_lock:
                            self.executing_plans.discard(plan.plan_id)
                        execution_lock.release()
                        return False
                
                # Check if this is part of a bracket trade - cancel the other side
                bracket_id = plan.conditions.get("bracket_trade_id")
                if bracket_id:
                    self._cancel_bracket_other_side(bracket_id, plan.plan_id)
                
                # Check MT5 connection with error recovery
                # If MT5 has been down recently, skip execution to avoid wasting resources
                if self.mt5_last_failure_time:
                    time_since_failure = (datetime.now(timezone.utc) - self.mt5_last_failure_time).total_seconds()
                    if time_since_failure < self.mt5_backoff_seconds:
                        logger.debug(f"MT5 connection failed recently ({time_since_failure:.0f}s ago), skipping execution")
                        with self.executing_plans_lock:
                            self.executing_plans.discard(plan.plan_id)
                        execution_lock.release()
                        return False
                
                # Ensure MT5 is connected
                if not self.mt5_service.connect():
                    self.mt5_connection_failures += 1
                    self.mt5_last_failure_time = datetime.now(timezone.utc)
                    logger.error(f"Failed to connect to MT5 (failure #{self.mt5_connection_failures})")
                    self.executing_plans.discard(plan.plan_id)
                    execution_lock.release()
                    return False
                
                # Reset connection failure tracking on successful connection
                if self.mt5_connection_failures > 0:
                    logger.info(f"MT5 connection restored after {self.mt5_connection_failures} failures")
                    self.mt5_connection_failures = 0
                    self.mt5_last_failure_time = None
                
                # Normalize symbol (MT5Service will handle symbol validation)
                symbol_base = plan.symbol.upper().rstrip('Cc')
                if not plan.symbol.upper().endswith('C'):
                    symbol_norm = symbol_base + 'c'  # lowercase 'c' for MT5
                else:
                    symbol_norm = symbol_base + 'c'  # always use lowercase 'c'
                
                # Try symbol variations if first attempt fails (case sensitivity)
                symbol_variations = [
                    symbol_norm,           # BTCUSDc (preferred)
                    symbol_base + 'C',     # BTCUSDC (uppercase variant)
                    plan.symbol.upper(),   # Original uppercased
                    plan.symbol,           # Original as-is
                ]
                
                # Find valid symbol
                symbol_norm_actual = None
                for sym_var in symbol_variations:
                    try:
                        # Try to get quote - if it works, symbol is valid
                        quote = self.mt5_service.get_quote(sym_var)
                        symbol_norm_actual = sym_var
                        if sym_var != symbol_variations[0]:
                            logger.debug(f"Symbol found as '{sym_var}' instead of '{symbol_variations[0]}'")
                        break
                    except Exception:
                        continue
                
                if symbol_norm_actual is None:
                    logger.error(
                        f"Symbol '{plan.symbol}' not found in MT5 after trying variations: {symbol_variations}"
                    )
                    self.executing_plans.discard(plan.plan_id)
                    execution_lock.release()
                    return False
                
                # Use the actual symbol name that worked
                symbol_norm = symbol_norm_actual
                
                # CRITICAL: Validate current price is still near entry price before execution
                # Price may have moved significantly between condition check and execution
                try:
                    quote = self.mt5_service.get_quote(symbol_norm)
                    current_bid = quote.bid
                    current_ask = quote.ask
                    current_price = current_ask if plan.direction == "BUY" else current_bid
                    
                    # Get base tolerance (will be adjusted for volatility below)
                    base_tolerance = plan.conditions.get("tolerance")
                    if base_tolerance is None:
                        from infra.tolerance_helper import get_price_tolerance
                        base_tolerance = get_price_tolerance(plan.symbol)
                    
                    # CRITICAL: Recalculate volatility-adjusted tolerance to match what was used in zone detection
                    # This ensures buffer check uses the same tolerance that triggered zone entry
                    tolerance = base_tolerance
                    rmag_data = None  # Fetch once, reuse for volatility regime and snapshot
                    volatility_regime = None  # Calculate once, reuse for both BUY and SELL
                    
                    if self.volatility_tolerance_calculator:
                        try:
                            # Get RMAG data if available (from advanced features) - fetch once
                            if hasattr(plan, 'advanced_features') and plan.advanced_features:
                                m5_features = plan.advanced_features.get("M5", {})
                                rmag_data = m5_features.get("rmag", {})
                            
                            # Get ATR (from volatility tolerance calculator's tolerance_calculator)
                            atr = None
                            if hasattr(self.volatility_tolerance_calculator, 'tolerance_calculator'):
                                try:
                                    atr = self.volatility_tolerance_calculator.tolerance_calculator._get_atr(plan.symbol, "M15")
                                except:
                                    pass
                            
                            # Calculate volatility-adjusted tolerance (same as in _check_tolerance_zone_entry)
                            tolerance = self.volatility_tolerance_calculator.calculate_volatility_adjusted_tolerance(
                                symbol=plan.symbol,
                                base_tolerance=base_tolerance,
                                rmag_data=rmag_data,
                                atr=atr,
                                timeframe="M15"
                            )
                            
                            # Enforce maximum tolerance (same as in _check_tolerance_zone_entry)
                            max_tolerance = self._get_max_tolerance(plan.symbol)
                            if tolerance > max_tolerance:
                                tolerance = max_tolerance
                            
                            # Determine volatility regime for buffer selection (reuse rmag_data already fetched)
                            if rmag_data:
                                ema200_atr = abs(rmag_data.get('ema200_atr', 0))
                                if ema200_atr > 2.0:
                                    volatility_regime = "high_vol"
                                elif ema200_atr < 1.0:
                                    volatility_regime = "low_vol"
                        except Exception as e:
                            logger.debug(f"Error calculating volatility-adjusted tolerance in _execute_trade: {e}, using base tolerance")
                    
                    # NEW: Create volatility snapshot AFTER tolerance recalculation (Phase 2.3)
                    # This captures the ACTUAL tolerance used for pre-execution checks
                    # CRITICAL: Must be placed here (after tolerance calc, before buffer checks) to capture correct tolerance
                    if self.volatility_tolerance_calculator:
                        try:
                            # Get smoothed RMAG values (reuse the same values used in tolerance calculation above)
                            # NOTE: rmag_data may be None if advanced_features not available - handle gracefully
                            rmag_ema200_atr_raw = None
                            rmag_ema200_atr_smoothed = None
                            if rmag_data:
                                rmag_ema200_atr_raw = abs(rmag_data.get('ema200_atr', 0))
                                if self.volatility_tolerance_calculator.enable_rmag_smoothing:
                                    # Re-smooth for snapshot (state will be same since we just smoothed it above)
                                    rmag_ema200_atr_smoothed = self.volatility_tolerance_calculator._smooth_rmag(plan.symbol, rmag_ema200_atr_raw)
                                else:
                                    rmag_ema200_atr_smoothed = rmag_ema200_atr_raw
                            
                            # Create volatility snapshot
                            import hashlib
                            from datetime import datetime, timezone
                            
                            volatility_snapshot = {
                                "rmag_ema200_atr_raw": rmag_ema200_atr_raw,
                                "rmag_ema200_atr_smoothed": rmag_ema200_atr_smoothed,  # Actual value used in calculation (None if no RMAG data)
                                "rmag_vwap_atr": abs(rmag_data.get('vwap_atr', 0)) if rmag_data else None,
                                "atr": atr,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "base_tolerance": base_tolerance,
                                "tolerance_applied": tolerance,  # Use tolerance AFTER max enforcement (actual value used)
                                "tolerance_adjustment_pct": ((tolerance - base_tolerance) / base_tolerance * 100) if base_tolerance > 0 else 0,
                                "kill_switch_triggered": getattr(plan, 'kill_switch_triggered', False),
                                "config_version": self._get_config_version()
                            }
                            
                            # Create hash (first 16 chars of SHA256)
                            snapshot_json = json.dumps(volatility_snapshot, sort_keys=True)
                            snapshot_hash = hashlib.sha256(snapshot_json.encode()).hexdigest()[:16]
                            
                            # Store in plan conditions (will be persisted when plan is saved)
                            if not hasattr(plan, 'conditions') or plan.conditions is None:
                                plan.conditions = {}
                            plan.conditions["volatility_snapshot_hash"] = snapshot_hash
                            plan.conditions["volatility_snapshot"] = volatility_snapshot
                            
                            logger.debug(
                                f"Plan {plan.plan_id}: Volatility snapshot created before execution "
                                f"(hash: {snapshot_hash}, RMAG: {volatility_snapshot.get('rmag_ema200_atr_smoothed')}, "
                                f"tolerance: {tolerance:.2f})"
                            )
                        except Exception as e:
                            logger.debug(f"Error creating volatility snapshot: {e}")
                    
                    # NEW: Pre-execution buffer check for BUY orders
                    if plan.direction == "BUY":
                        # volatility_regime already calculated above, reuse it
                        
                        # Calculate buffer (config-driven with volatility awareness)
                        buffer = self._get_execution_buffer(plan.symbol, tolerance, volatility_regime)
                        
                        # Check if ask price exceeds planned entry + buffer
                        max_acceptable_ask = plan.entry_price + buffer
                        
                        if current_ask > max_acceptable_ask:
                            price_excess = current_ask - max_acceptable_ask
                            logger.warning(
                                f"Plan {plan.plan_id}: Pre-execution check FAILED - "
                                f"Ask price ${current_ask:.2f} exceeds planned entry ${plan.entry_price:.2f} + buffer ${buffer:.2f} = ${max_acceptable_ask:.2f} "
                                f"(excess: ${price_excess:.2f}). Rejecting execution."
                            )
                            with self.executing_plans_lock:
                                self.executing_plans.discard(plan.plan_id)
                            execution_lock.release()
                            return False
                    
                    # NEW: Pre-execution buffer check for SELL orders
                    elif plan.direction == "SELL":
                        # volatility_regime already calculated above, reuse it
                        buffer = self._get_execution_buffer(plan.symbol, tolerance, volatility_regime)
                        min_acceptable_bid = plan.entry_price - buffer
                        
                        if current_bid < min_acceptable_bid:
                            price_excess = min_acceptable_bid - current_bid
                            logger.warning(
                                f"Plan {plan.plan_id}: Pre-execution check FAILED - "
                                f"Bid price ${current_bid:.2f} below planned entry ${plan.entry_price:.2f} - buffer ${buffer:.2f} = ${min_acceptable_bid:.2f} "
                                f"(excess: ${price_excess:.2f}). Rejecting execution."
                            )
                            with self.executing_plans_lock:
                                self.executing_plans.discard(plan.plan_id)
                            execution_lock.release()
                            return False
                    
                    # Existing tolerance check (keep for backward compatibility)
                    # NOTE: This check validates the "price_near" condition specifically, which is different from
                    # the buffer checks above. Buffer checks validate entry_price ± buffer, while this validates
                    # price_near ± tolerance. Both serve different purposes and should be kept.
                    if "price_near" in plan.conditions:
                        target_price = plan.conditions["price_near"]
                        price_diff = abs(current_price - target_price)
                        if price_diff > tolerance:
                            logger.warning(
                                f"Price moved too far from entry before execution: "
                                f"current={current_price:.2f}, target={target_price:.2f}, diff={price_diff:.2f}, tolerance={tolerance:.2f}"
                            )
                            with self.executing_plans_lock:
                                self.executing_plans.discard(plan.plan_id)
                            execution_lock.release()
                            return False
                    
                    # Also validate entry_price from plan is reasonable
                    entry_price_diff = abs(current_price - plan.entry_price)
                    max_entry_diff = tolerance  # Use tolerance as max difference
                    if entry_price_diff > max_entry_diff:
                        logger.warning(
                            f"Price moved too far from plan entry before execution: "
                            f"current={current_price:.2f}, planned={plan.entry_price:.2f}, diff={entry_price_diff:.2f}, max={max_entry_diff:.2f}"
                        )
                        with self.executing_plans_lock:
                            self.executing_plans.discard(plan.plan_id)
                        execution_lock.release()
                        return False
                except Exception as e:
                    logger.error(f"Error validating price before execution: {e}")
                    # Continue execution if price validation fails (better to try than skip)
                
                # Phase 2: Calculate SL/TP based on triggered level (if multi-level plan)
                # Get the triggered level_index from plan state (set during condition check)
                triggered_level_index = getattr(plan, '_triggered_level_index', None)
                execution_sl = plan.stop_loss
                execution_tp = plan.take_profit
                execution_entry = plan.entry_price
                
                if triggered_level_index is not None and plan.entry_levels:
                    # Multi-level plan: Use triggered level's SL/TP offsets
                    try:
                        triggered_level = plan.entry_levels[triggered_level_index]
                        if isinstance(triggered_level, dict):
                            level_price = triggered_level.get("price", plan.entry_price)
                            sl_offset = triggered_level.get("sl_offset")
                            tp_offset = triggered_level.get("tp_offset")
                            
                            # Use level price as entry
                            execution_entry = level_price
                            
                            # Calculate SL/TP from offsets if provided
                            if sl_offset is not None:
                                if plan.direction == "BUY":
                                    execution_sl = level_price - abs(sl_offset)
                                else:  # SELL
                                    execution_sl = level_price + abs(sl_offset)
                            
                            if tp_offset is not None:
                                if plan.direction == "BUY":
                                    execution_tp = level_price + abs(tp_offset)
                                else:  # SELL
                                    execution_tp = level_price - abs(tp_offset)
                            
                            logger.info(
                                f"Phase 2: Using triggered level {triggered_level_index} for plan {plan.plan_id}: "
                                f"entry={execution_entry}, sl={execution_sl}, tp={execution_tp}"
                            )
                    except (IndexError, KeyError, TypeError) as e:
                        logger.warning(f"Error processing triggered level {triggered_level_index}: {e}, using plan defaults")
                
                # ============================================================================
                # ISSUE 1: VWAP Overextension Filter for OB Plans
                # ============================================================================
                # Block OB plans if VWAP is already overextended (prevents OB longs in overextended markets)
                if plan.conditions.get("order_block"):
                    try:
                        # Fetch M1 data and analysis for VWAP check
                        if self.m1_data_fetcher and self.m1_analyzer:
                            m1_candles = self.m1_data_fetcher.fetch_m1_data(symbol_norm, count=200)
                            if m1_candles and len(m1_candles) >= 50:
                                # Get M5 candles for HTF validation (use helper function from _check_conditions scope)
                                def _get_recent_candles(symbol, timeframe, count):
                                    """Helper to get recent candles from MT5"""
                                    try:
                                        import MetaTrader5 as mt5
                                        timeframe_map = {
                                            "M1": mt5.TIMEFRAME_M1,
                                            "M5": mt5.TIMEFRAME_M5,
                                            "M15": mt5.TIMEFRAME_M15,
                                            "H1": mt5.TIMEFRAME_H1
                                        }
                                        tf = timeframe_map.get(timeframe.upper(), mt5.TIMEFRAME_M5)
                                        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
                                        return rates if rates is not None else []
                                    except Exception:
                                        return []
                                
                                m5_candles = _get_recent_candles(symbol_norm, "M5", 100)
                                
                                # Normalize candles helper
                                def _normalize_candles(candles):
                                    """Convert numpy array to list of dictionaries"""
                                    if candles is None or len(candles) == 0:
                                        return []
                                    if isinstance(candles[0], dict):
                                        return candles
                                    # Convert numpy structured array to dict
                                    return [
                                        {
                                            'time': int(c[0]),
                                            'open': float(c[1]),
                                            'high': float(c[2]),
                                            'low': float(c[3]),
                                            'close': float(c[4]),
                                            'tick_volume': int(c[5]) if len(c) > 5 else 0
                                        }
                                        for c in candles
                                    ]
                                
                                m5_candles = _normalize_candles(m5_candles)
                                
                                # Analyze M1 microstructure to get VWAP data
                                m1_analysis = self.m1_analyzer.analyze_microstructure(
                                    symbol=symbol_norm,
                                    candles=m1_candles,
                                    current_price=current_price,
                                    higher_timeframe_data={"M5": m5_candles} if m5_candles else None
                                )
                                
                                if m1_analysis and m1_analysis.get('available'):
                                    vwap_data = m1_analysis.get('vwap', {})
                                    vwap_price = vwap_data.get('value')
                                    vwap_std = vwap_data.get('std', 0)
                                    
                                    if vwap_price and vwap_std > 0:
                                        deviation = (current_price - vwap_price) / vwap_std
                                        
                                        # Block BUY if already overextended above VWAP
                                        if plan.direction == "BUY" and deviation > 2.0:
                                            logger.warning(
                                                f"Blocking OB BUY for {plan.plan_id}: VWAP already {deviation:.2f}σ extended "
                                                f"(price={current_price:.2f}, vwap={vwap_price:.2f}, std={vwap_std:.2f})"
                                            )
                                            with self.executing_plans_lock:
                                                self.executing_plans.discard(plan.plan_id)
                                            execution_lock.release()
                                            return False
                                        
                                        # Block SELL if already overextended below VWAP
                                        if plan.direction == "SELL" and deviation < -2.0:
                                            logger.warning(
                                                f"Blocking OB SELL for {plan.plan_id}: VWAP already {deviation:.2f}σ extended "
                                                f"(price={current_price:.2f}, vwap={vwap_price:.2f}, std={vwap_std:.2f})"
                                            )
                                            with self.executing_plans_lock:
                                                self.executing_plans.discard(plan.plan_id)
                                            execution_lock.release()
                                            return False
                    except Exception as e:
                        logger.debug(f"Error checking VWAP overextension for {plan.plan_id}: {e}")
                        # Continue execution if VWAP check fails (better to try than skip)
                
                # ============================================================================
                # ISSUE 3: Session-End Filter
                # ============================================================================
                # Block trades within 30 minutes of session close (prevents low-probability trades near close)
                try:
                    from infra.session_helpers import SessionHelpers
                    
                    current_time = datetime.now(timezone.utc)
                    current_session = SessionHelpers.get_current_session(current_time)
                    
                    # Session end times (UTC)
                    session_ends = {
                        "LONDON": 13,   # 13:00 UTC
                        "NY": 21,       # 21:00 UTC
                        "OVERLAP": 16   # 16:00 UTC
                    }
                    
                    if current_session in session_ends:
                        session_end_hour = session_ends[current_session]
                        current_hour = current_time.hour
                        current_minute = current_time.minute
                        
                        # Calculate minutes until session end
                        if current_hour == session_end_hour:
                            minutes_until_end = 60 - current_minute
                        elif current_hour < session_end_hour:
                            minutes_until_end = (session_end_hour - current_hour) * 60 - current_minute
                        else:
                            minutes_until_end = 0  # Session already ended
                        
                        if minutes_until_end < 30:
                            logger.warning(
                                f"Blocking execution for {plan.plan_id}: Only {minutes_until_end} minutes until {current_session} close"
                            )
                            with self.executing_plans_lock:
                                self.executing_plans.discard(plan.plan_id)
                            execution_lock.release()
                            return False
                except Exception as e:
                    logger.debug(f"Error checking session-end filter for {plan.plan_id}: {e}")
                    # Continue execution if session check fails (better to try than skip)
                    
                # Calculate lot size - always default to 0.01 if volume is 0 or None
                lot_size = plan.volume if plan.volume and plan.volume > 0 else 0.01
                if lot_size != plan.volume:
                    logger.info(f"Plan {plan.plan_id} had volume {plan.volume}, using default 0.01")
                    
                # Determine direction
                direction = "BUY" if plan.direction.upper() == "BUY" else "SELL"
                
                # Sanitize comment for MT5 (MT5Service will use "market" for market orders anyway, but sanitize to be safe)
                from infra.mt5_service import sanitize_mt5_comment
                comment_base = f"Auto executed plan {plan.plan_id}"
                safe_comment = sanitize_mt5_comment(comment_base)
                
                # Phase 2.1: Determine order type (AFTER all pre-execution checks, BEFORE actual order execution)
                order_type_str = self._determine_order_type(plan)
                
                if order_type_str == "market":
                    # Market order: Immediate execution (current behavior)
                    result = self.mt5_service.open_order(
                        symbol=symbol_norm,
                        side=direction,
                        lot=lot_size,
                        sl=execution_sl,
                        tp=execution_tp,
                        comment=safe_comment,
                    )
                else:
                    # Pending order: Place order that will fill when price reaches entry
                    # Get current price for validation (handle errors gracefully)
                    try:
                        quote = self.mt5_service.get_quote(symbol_norm)
                        if not quote or not quote.bid or not quote.ask:
                            logger.error(f"Plan {plan.plan_id}: Failed to get quote for {symbol_norm}")
                            with self.executing_plans_lock:
                                self.executing_plans.discard(plan.plan_id)
                            execution_lock.release()
                            return False
                        current_price = (quote.bid + quote.ask) / 2.0
                    except Exception as e:
                        logger.error(f"Plan {plan.plan_id}: Error getting quote for validation: {e}")
                        with self.executing_plans_lock:
                            self.executing_plans.discard(plan.plan_id)
                        execution_lock.release()
                        return False
                    
                    # Validate entry price is valid for pending order type
                    is_valid, error_msg = self._validate_pending_order_entry(plan, order_type_str, current_price)
                    if not is_valid:
                        logger.error(f"Plan {plan.plan_id}: {error_msg}")
                        with self.executing_plans_lock:
                            self.executing_plans.discard(plan.plan_id)
                        execution_lock.release()
                        return False
                    
                    # CRITICAL: Check if plan was cancelled during validation (race condition protection)
                    with self.plans_lock:
                        if plan.plan_id not in self.plans:
                            logger.warning(f"Plan {plan.plan_id} was cancelled during pending order validation - aborting")
                            with self.executing_plans_lock:
                                self.executing_plans.discard(plan.plan_id)
                            execution_lock.release()
                            return False
                    
                    # Place pending order
                    result = self.mt5_service.pending_order(
                        symbol=symbol_norm,
                        side=direction,
                        entry=plan.entry_price,  # Trigger price for stop/limit
                        sl=execution_sl,
                        tp=execution_tp,
                        lot=lot_size,
                        comment=order_type_str,  # MT5Service uses comment to determine order type
                    )
                    
                    # Check if order placement was successful
                    if not result.get("ok"):
                        error_msg = result.get("message", "Unknown error")
                        logger.error(f"Pending order placement failed for plan {plan.plan_id}: {error_msg}")
                        # Reset status to pending (don't leave as pending_order_placed)
                        plan.status = "pending"
                        plan.pending_order_ticket = None
                        with self.executing_plans_lock:
                            self.executing_plans.discard(plan.plan_id)
                        execution_lock.release()
                        return False
                    
                    # Pending order placed successfully - update plan status
                    pending_ticket = result.get("details", {}).get("ticket")
                    if not pending_ticket:
                        logger.error(f"Pending order placed but no ticket returned for plan {plan.plan_id}")
                        plan.status = "pending"
                        plan.pending_order_ticket = None
                        with self.executing_plans_lock:
                            self.executing_plans.discard(plan.plan_id)
                        execution_lock.release()
                        return False
                    
                    # Update plan status to pending_order_placed (will be monitored by _check_pending_orders)
                    plan.status = "pending_order_placed"
                    plan.pending_order_ticket = pending_ticket
                    
                    # Update database with pending order status
                    self._update_plan_status(plan)
                    
                    # Log success
                    logger.info(
                        f"Pending {order_type_str} order placed for plan {plan.plan_id}: "
                        f"ticket={pending_ticket}, entry={plan.entry_price}, symbol={symbol_norm}"
                    )
                    
                    # Clean up execution tracking
                    with self.executing_plans_lock:
                        self.executing_plans.discard(plan.plan_id)
                    execution_lock.release()
                    
                    # NOTE: Plan remains in memory for monitoring by _check_pending_orders()
                    # Do NOT remove from self.plans - it will be removed when order fills or expires
                    return True
                
                # Check result
                if not result.get("ok"):
                    error_msg = result.get("message", "Unknown error")
                    details = result.get("details", {})
                    retcode = details.get("retcode", "unknown")
                    
                    # Enhanced error diagnostics for common MT5 errors
                    error_context = f"retcode={retcode}, message={error_msg}"
                    if retcode == 10011:
                        # Error 10011: Request processing error (often timeout or market closed)
                        try:
                            import MetaTrader5 as mt5
                            if self.mt5_service.connect():
                                # Check if market is open
                                symbol_info = mt5.symbol_info(symbol_norm)
                                if symbol_info:
                                    trade_mode = symbol_info.trade_mode
                                    if trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
                                        error_context += " (Market trading disabled for symbol)"
                                    elif trade_mode == mt5.SYMBOL_TRADE_MODE_CLOSEONLY:
                                        error_context += " (Market only allows closing positions)"
                                    else:
                                        error_context += " (Possible timeout or broker issue)"
                                else:
                                    error_context += " (Symbol info unavailable)"
                        except Exception as e:
                            logger.debug(f"Could not check market status: {e}")
                        error_context += f" | Symbol: {symbol_norm}, Direction: {direction}, Entry: {plan.entry_price}, SL: {plan.stop_loss}, TP: {plan.take_profit}"
                    
                    logger.error(
                        f"Trade execution failed for plan {plan.plan_id}: {error_context}"
                    )
                    self.executing_plans.discard(plan.plan_id)
                    execution_lock.release()
                    return False
                    
                # Get ticket from result
                ticket = result.get("details", {}).get("ticket")
                if not ticket:
                    logger.error(f"Trade executed but no ticket returned for plan {plan.plan_id}")
                    self.executing_plans.discard(plan.plan_id)
                    execution_lock.release()
                    return False
                
                # Verify SL/TP were actually set after execution
                result_details = result.get("details", {})
                final_sl = result_details.get("final_sl")
                final_tp = result_details.get("final_tp")
                price_executed = result_details.get("price_executed", plan.entry_price)
                
                # Log result details for debugging
                logger.info(f"SL/TP Verification for ticket {ticket}: final_sl={final_sl}, final_tp={final_tp}, price_executed={price_executed}")
                logger.debug(f"Result details keys: {list(result_details.keys())}")
                
                # Also check position directly from MT5 to verify SL/TP
                actual_sl = None
                actual_tp = None
                try:
                    import MetaTrader5 as mt5
                    if self.mt5_service.connect():
                        positions = mt5.positions_get(ticket=ticket)
                        if positions and len(positions) > 0:
                            pos = positions[0]
                            actual_sl = float(getattr(pos, "sl", 0.0) or 0.0)
                            actual_tp = float(getattr(pos, "tp", 0.0) or 0.0)
                            logger.info(f"Position check for ticket {ticket}: actual_sl={actual_sl}, actual_tp={actual_tp}")
                            
                            # Use actual position values if result details don't have them
                            if final_sl is None and actual_sl > 0:
                                final_sl = actual_sl
                            if final_tp is None and actual_tp > 0:
                                final_tp = actual_tp
                except Exception as e:
                    logger.debug(f"Could not check position directly from MT5: {e}")
                
                sl_missing = False
                tp_missing = False
                
                # Check if SL/TP are missing (None or 0)
                if final_sl is None or final_sl == 0:
                    sl_missing = True
                    logger.warning(f"⚠️ SL NOT SET for ticket {ticket} (plan {plan.plan_id}) - final_sl={final_sl}, actual_sl={actual_sl}")
                
                if final_tp is None or final_tp == 0:
                    tp_missing = True
                    logger.warning(f"⚠️ TP NOT SET for ticket {ticket} (plan {plan.plan_id}) - final_tp={final_tp}, actual_tp={actual_tp}")
                
                # If SL or TP are missing, send Discord alert
                if sl_missing or tp_missing:
                    logger.warning(f"⚠️ SL/TP MISSING - Sending Discord alert for ticket {ticket}")
                    try:
                        from discord_notifications import DiscordNotifier
                        discord_notifier = DiscordNotifier()
                        logger.info(f"Discord notifier initialized: enabled={discord_notifier.enabled}")
                        if discord_notifier.enabled:
                            alert_message = f"""🚨 **CRITICAL: SL/TP NOT SET AFTER EXECUTION**

📊 **Plan ID**: {plan.plan_id}
💱 **Symbol**: {plan.symbol}
📈 **Direction**: {plan.direction}
🎫 **Ticket**: {ticket}
💰 **Entry**: {price_executed}
🛡️ **Planned SL**: {plan.stop_loss}
🎯 **Planned TP**: {plan.take_profit}

❌ **Status**:
{'❌ Stop Loss NOT SET' if sl_missing else '✅ Stop Loss: ' + str(final_sl)}
{'❌ Take Profit NOT SET' if tp_missing else '✅ Take Profit: ' + str(final_tp)}

⚠️ **Action Required**: Please manually set SL/TP in MT5 immediately!

⏰ **Time**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"""
                            
                            # Use error alert for critical issues (red color)
                            success = discord_notifier.send_error_alert(
                                error_message=alert_message,
                                component="Auto Execution System"
                            )
                            if success:
                                logger.info(f"✅ Discord alert sent successfully for missing SL/TP on ticket {ticket}")
                            else:
                                logger.error(f"❌ Failed to send Discord alert for missing SL/TP on ticket {ticket}")
                        else:
                            logger.error(f"❌ Discord notifier is not enabled - cannot send alert for ticket {ticket}")
                    except Exception as e:
                        logger.error(f"❌ Error sending Discord alert for missing SL/TP: {e}", exc_info=True)
                    
                # Update plan status (already marked as "executing" in DB, now update to "executed")
                plan.status = "executed"
                plan.executed_at = datetime.now(timezone.utc).isoformat()
                plan.ticket = ticket
                
                # Update database (status already "executing", now update to "executed" with ticket)
                self._update_plan_status(plan)
                
                # Get executed price from result details
                executed_price = result.get("details", {}).get("price_executed") or result.get("details", {}).get("price_requested", 0.0)
                
                # Phase 2.1a: Call post-execution handler (extracts all post-execution logic)
                self._handle_post_execution(
                    plan=plan,
                    result=result,
                    executed_price=executed_price,
                    symbol_norm=symbol_norm,
                    direction=direction,
                    lot_size=lot_size
                )
                
                logger.info(f"Successfully executed trade plan {plan.plan_id}, ticket: {plan.ticket}")
                # Release lock and remove from executing set before returning
                self.executing_plans.discard(plan.plan_id)
                execution_lock.release()
                return True
                
            except Exception as e:
                logger.error(f"Failed to execute trade plan {plan.plan_id}: {e}", exc_info=True)
                # Rollback database status from "executing" to "pending" on error
                try:
                    with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                        conn.execute("UPDATE trade_plans SET status = 'pending' WHERE plan_id = ?", (plan.plan_id,))
                        conn.commit()
                        logger.debug(f"Rolled back plan {plan.plan_id} status to 'pending' after execution failure")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback plan status after execution failure: {rollback_error}")
                # Release lock and remove from executing set on error
                self.executing_plans.discard(plan.plan_id)
                if plan.plan_id in self.execution_locks:
                    try:
                        self.execution_locks[plan.plan_id].release()
                    except Exception:
                        pass
                return False
            
            finally:
                # CRITICAL: Always release lock and clean up executing_plans (Phase 0)
                # This ensures no lock leaks even if an exception occurs
                try:
                    with self.executing_plans_lock:
                        self.executing_plans.discard(plan.plan_id)
                except Exception:
                    pass
                
                try:
                    execution_lock.release()
                except Exception:
                    # Lock may have already been released - that's OK
                    pass
        except Exception as e:
            logger.error(f"Failed to execute trade plan {plan.plan_id} (outer exception): {e}", exc_info=True)
            # Clean up if lock was acquired
            if plan.plan_id in self.executing_plans:
                self.executing_plans.discard(plan.plan_id)
            if plan.plan_id in self.execution_locks:
                try:
                    self.execution_locks[plan.plan_id].release()
                except Exception:
                    pass
            return False
    
    def _send_discord_notification(self, plan: TradePlan, result):
        """Send Discord notification about executed trade"""
        try:
            from discord_notifications import DiscordNotifier
            
            discord_notifier = DiscordNotifier()
            if not discord_notifier.enabled:
                logger.warning("Discord notifications not enabled, skipping notification")
                return
                
            message = f"""🤖 **Auto-Executed Trade Plan**

📊 **Plan ID**: {plan.plan_id}
💱 **Symbol**: {plan.symbol}
📈 **Direction**: {plan.direction}
💰 **Entry**: {plan.entry_price}
🛡️ **SL**: {plan.stop_loss}
🎯 **TP**: {plan.take_profit}
📦 **Volume**: {plan.volume}
🎫 **Ticket**: {plan.ticket}

⏰ **Executed**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
📝 **Notes**: {plan.notes or 'Auto-executed by system'}

✅ **Trade successfully executed!**"""
            
            success = discord_notifier.send_system_alert("AUTO_EXECUTION", message)
            if success:
                logger.info("Discord notification sent successfully")
            else:
                logger.error("Failed to send Discord notification")
                
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")
    
    def _check_pending_orders(self) -> None:
        """
        Check pending orders and update plan status when they fill.
        Called periodically from monitoring loop (every 30 seconds).
        
        Checks all plans with status "pending_order_placed" to see if their
        pending orders have filled, been cancelled, or expired.
        """
        import MetaTrader5 as mt5
        from datetime import datetime, timezone
        
        if not self.mt5_service.connect():
            logger.warning("MT5 not connected - cannot check pending orders")
            return  # Skip check if MT5 not available (will retry on next cycle)
        
        # Get all plans with pending orders (create copy while holding lock to avoid race conditions)
        pending_plan_ids = []
        with self.plans_lock:
            for plan_id, plan in self.plans.items():
                # CRITICAL: Use hasattr check for backward compatibility with old plans
                if (plan.status == "pending_order_placed" and 
                    hasattr(plan, 'pending_order_ticket') and 
                    plan.pending_order_ticket):
                    # Create copy of plan data to avoid race conditions
                    pending_plan_ids.append((plan_id, plan.pending_order_ticket, plan.symbol, plan.direction, plan.entry_price, plan.volume))
        
        if not pending_plan_ids:
            return  # No pending orders to check
        
        logger.debug(f"Checking {len(pending_plan_ids)} pending order(s)")
        
        for plan_id, pending_ticket, symbol, direction, entry_price, volume in pending_plan_ids:
            # Re-acquire plan from memory (it might have been removed/updated)
            with self.plans_lock:
                if plan_id not in self.plans:
                    logger.debug(f"Plan {plan_id} no longer in memory - skipping")
                    continue
                plan = self.plans[plan_id]
                # Verify plan still has pending order (might have been updated)
                # CRITICAL: Use hasattr check for backward compatibility
                if (plan.status != "pending_order_placed" or 
                    not hasattr(plan, 'pending_order_ticket') or 
                    plan.pending_order_ticket != pending_ticket):
                    logger.debug(f"Plan {plan_id} status or ticket changed - skipping")
                    continue
            try:
                # Check if order still exists
                # CRITICAL: orders_get() can return None on error, check for None first
                orders = mt5.orders_get(ticket=pending_ticket)
                
                if orders is None or len(orders) == 0:
                    # Order no longer exists - check if it filled by matching position
                    # CRITICAL: Position tickets are DIFFERENT from order tickets
                    # We need to match by symbol, direction, and entry price
                    symbol_norm = symbol.upper().rstrip('Cc') + 'c'
                    all_positions = mt5.positions_get(symbol=symbol_norm)
                    
                    # CRITICAL: positions_get() can return None on error, check explicitly
                    if all_positions is None:
                        logger.warning(f"MT5 positions_get() returned None for {symbol_norm} - cannot check if order filled")
                        # Continue to next order - will retry on next cycle
                        continue
                    
                    # Match position by symbol, direction, and entry price (within tolerance)
                    matched_positions = []
                    if all_positions:
                        direction_mt5 = mt5.ORDER_TYPE_BUY if direction.upper() == "BUY" else mt5.ORDER_TYPE_SELL
                        # Use symbol-specific tolerance (consider ATR-based tolerance in future)
                        # NOTE: This is a fixed tolerance for position matching. For more accuracy,
                        # consider using the same tolerance calculation as execution system (ATR-based).
                        entry_tolerance = 0.001 if "BTC" in symbol_norm or "XAU" in symbol_norm else 0.0001
                        # Time window: 10 minutes (configurable, increased from 5 minutes)
                        time_window_seconds = 600  # 10 minutes
                        
                        for pos in all_positions:
                            # Defensive checks for position attributes
                            if not hasattr(pos, 'type') or not hasattr(pos, 'price_open') or not hasattr(pos, 'volume') or not hasattr(pos, 'time'):
                                logger.warning(f"Position missing required attributes - skipping")
                                continue
                            
                            if (pos.type == direction_mt5 and 
                                abs(pos.price_open - entry_price) <= entry_tolerance and
                                abs(pos.volume - volume) < 0.001):  # Volume match with small tolerance
                                # Check if position was opened recently
                                try:
                                    pos_time = datetime.fromtimestamp(pos.time, tz=timezone.utc)
                                    time_diff = (datetime.now(timezone.utc) - pos_time).total_seconds()
                                    if time_diff <= time_window_seconds:
                                        matched_positions.append(pos)
                                except (ValueError, OSError) as e:
                                    logger.warning(f"Error parsing position time: {e} - skipping position")
                                    continue
                    
                    # Handle multiple matches (should be rare, but possible)
                    if len(matched_positions) > 1:
                        logger.warning(f"Multiple positions matched for plan {plan_id} - using most recent")
                        # Sort by time (most recent first)
                        matched_positions.sort(key=lambda p: p.time, reverse=True)
                    
                    matched_position = matched_positions[0] if matched_positions else None
                    
                    if matched_position:
                        # Order filled - update plan status
                        # Defensive check for position attributes
                        if not hasattr(matched_position, 'ticket') or not hasattr(matched_position, 'price_open'):
                            logger.error(f"Matched position missing required attributes (ticket/price_open) for plan {plan_id}")
                            continue
                        
                        plan.status = "executed"
                        plan.executed_at = datetime.now(timezone.utc).isoformat()
                        plan.ticket = matched_position.ticket
                        
                        logger.info(f"Pending order {pending_ticket} filled for plan {plan_id} → position {matched_position.ticket}")
                        self._update_plan_status(plan)
                        
                        # CRITICAL: Trigger post-execution steps (same as market orders)
                        # This includes: Universal Manager registration, Discord notifications, journal logging, etc.
                        # Create a result dict similar to what mt5_service.open_order() returns
                        executed_price = matched_position.price_open
                        symbol_norm = symbol.upper().rstrip('Cc') + 'c'
                        
                        # Create mock result dict for post-execution processing
                        result = {
                            "ok": True,
                            "message": "Pending order filled",
                            "details": {
                                "ticket": matched_position.ticket,
                                "price_executed": executed_price,
                                "price_requested": plan.entry_price
                            }
                        }
                        
                        # Call post-execution handler (extract from _execute_trade or create new method)
                        # This should handle:
                        # - Universal Manager/DTMS registration
                        # - M1 context logging
                        # - Signal learning
                        # - Journal logging
                        # - Discord notifications
                        try:
                            # Get lot size and direction from plan
                            lot_size = plan.volume if plan.volume is not None else 0.01
                            direction_str = plan.direction.upper() if plan.direction else "BUY"
                            self._handle_post_execution(plan, result, executed_price, symbol_norm, direction_str, lot_size)
                        except Exception as e:
                            logger.error(f"Error in post-execution handling for filled pending order {plan_id}: {e}", exc_info=True)
                            # Continue even if post-execution fails - trade is already filled
                        
                        # Remove from memory
                        with self.plans_lock:
                            if plan_id in self.plans:
                                del self.plans[plan_id]
                        
                        # Clean up execution locks and other resources
                        # Use symbol from loop (already validated) instead of plan.symbol (might be None)
                        self._cleanup_plan_resources(plan_id, symbol)
                    else:
                        # Order cancelled or expired (not filled)
                        logger.warning(f"Pending order {pending_ticket} no longer exists (cancelled/expired) for plan {plan_id}")
                        plan.status = "cancelled"
                        plan.cancellation_reason = "Pending order cancelled or expired in MT5"
                        self._update_plan_status(plan)
                        
                        # Remove from memory
                        with self.plans_lock:
                            if plan_id in self.plans:
                                del self.plans[plan_id]
                        
                        # Clean up execution locks and other resources
                        # Use symbol from loop (already validated) instead of plan.symbol (might be None)
                        self._cleanup_plan_resources(plan_id, symbol)
                else:
                    # Order still exists - no action needed
                    logger.debug(f"Pending order {pending_ticket} still active for plan {plan_id}")
            except Exception as e:
                logger.error(f"Error checking pending order for plan {plan_id}: {e}", exc_info=True)
    
    def _monitor_loop(self):
        """Main monitoring loop with M1 integration and Phase 2.2 order-flow checks"""
        thread_name = threading.current_thread().name
        logger.info(f"Auto execution system monitoring loop started (thread: {thread_name})")
        
        # Phase 2.2: High-frequency order-flow plan checks
        last_order_flow_check = 0
        order_flow_check_interval = 5  # 5 seconds for order-flow plans
        
        # Phase 4.2: Pending order checks
        last_pending_check = 0
        pending_check_interval = 30  # 30 seconds for pending order checks
        
        try:
            while self.running:
                try:
                    # Phase 6: Log performance metrics periodically
                    try:
                        now_utc = datetime.now(timezone.utc)
                        if (self._metrics_last_log is None or 
                            (now_utc - self._metrics_last_log).total_seconds() >= self._metrics_log_interval):
                            self._log_performance_metrics()
                            self._metrics_last_log = now_utc
                    except Exception as e:
                        logger.debug(f"Error logging performance metrics: {e}")
                    
                    # Performance Optimization: Batch refresh M1 data for all active symbols (Phase 2.1.1)
                    try:
                        if self.config and self.config.get('m1_integration', {}).get('batch_refresh', True):
                            try:
                                self._batch_refresh_m1_data()
                            except Exception as e:
                                logger.warning(f"Error in batch M1 refresh (non-fatal): {e}", exc_info=True)
                                # Continue - M1 refresh is not critical for monitoring
                    except (AttributeError, TypeError) as e:
                        logger.warning(f"Error accessing config for M1 batch refresh (non-fatal): {e}")
                        # Continue - config access failure shouldn't block monitoring
                    
                    # Periodically clean up caches and invalid symbols
                    try:
                        now_utc = datetime.now(timezone.utc)
                    except Exception as e:
                        logger.warning(f"Error getting current time (non-fatal): {e}")
                        # Skip cleanup this iteration if datetime fails
                        now_utc = None
                    
                    if now_utc is not None:
                        try:
                            # Defensive check: ensure last_cache_cleanup is valid
                            if self.last_cache_cleanup is None:
                                self.last_cache_cleanup = now_utc
                            time_since_cleanup = (now_utc - self.last_cache_cleanup).total_seconds()
                        except (TypeError, AttributeError) as e:
                            logger.warning(f"Error calculating cleanup time (non-fatal): {e}")
                            # Reset last_cache_cleanup if it's invalid
                            self.last_cache_cleanup = now_utc
                            time_since_cleanup = float('inf')
                        
                        if time_since_cleanup >= self.cache_cleanup_interval:
                            try:
                                self._periodic_cache_cleanup()
                                # Clean up old volume cache entries
                                self._cleanup_volume_cache()
                                # Clean up old Binance pressure cache entries
                                self._cleanup_binance_pressure_cache()
                                self.last_cache_cleanup = now_utc
                            except Exception as e:
                                logger.warning(f"Error in cache cleanup (non-fatal): {e}", exc_info=True)
                                # Continue - cache cleanup is not critical for monitoring
                    
                    # Phase 2.2: High-frequency check for order-flow plans (every 5 seconds)
                    current_time = time.time()
                    if current_time - last_order_flow_check >= order_flow_check_interval:
                        try:
                            logger.debug(f"Order flow check triggered (interval: {order_flow_check_interval}s)")
                            order_flow_plans = self._get_order_flow_plans()
                            if order_flow_plans:
                                logger.info(
                                    f"Processing {len(order_flow_plans)} order flow plan(s) "
                                    f"(last check: {current_time - last_order_flow_check:.1f}s ago)"
                                )
                                self._check_order_flow_plans_quick(order_flow_plans)
                                # Phase 4.1: Record performance metrics
                                if hasattr(self, 'micro_scalp_engine') and self.micro_scalp_engine:
                                    if hasattr(self.micro_scalp_engine, 'btc_order_flow'):
                                        btc_flow = self.micro_scalp_engine.btc_order_flow
                                        if hasattr(btc_flow, 'performance_monitor') and btc_flow.performance_monitor:
                                            btc_flow.performance_monitor.record_order_flow_check()
                            else:
                                logger.debug("No order flow plans found to check")
                        except Exception as e:
                            logger.error(f"Error in quick order-flow check: {e}", exc_info=True)
                        last_order_flow_check = current_time
                    
                    # Phase 4.2: Check pending orders periodically (every 30 seconds)
                    if current_time - last_pending_check >= pending_check_interval:
                        try:
                            self._check_pending_orders()
                        except Exception as e:
                            logger.error(f"Error checking pending orders: {e}", exc_info=True)
                        last_pending_check = current_time
                    
                    # Periodically reload plans from database to pick up new plans
                    if now_utc is not None:
                        try:
                            # Defensive check: ensure last_plan_reload is valid
                            if self.last_plan_reload is None:
                                self.last_plan_reload = now_utc
                            time_since_reload = (now_utc - self.last_plan_reload).total_seconds()
                        except Exception as e:
                            logger.warning(f"Error calculating reload time (non-fatal): {e}")
                            # Reset last_plan_reload if it's invalid
                            self.last_plan_reload = now_utc
                            # Use a safe default to continue
                            time_since_reload = float('inf')
                        
                        if time_since_reload >= self.plan_reload_interval:
                            logger.debug(f"Reloading plans from database (last reload: {time_since_reload:.0f}s ago)")
                            
                            # CRITICAL: Flush write queue before reloading plans (Phase 0 - Critical Error 4)
                            # This ensures all pending writes are completed before reloading
                            if self.db_write_queue:
                                try:
                                    # Get all plan IDs currently in memory
                                    with self.plans_lock:
                                        plan_ids_to_flush = list(self.plans.keys())
                                    
                                    if plan_ids_to_flush:
                                        logger.debug(f"Flushing write queue for {len(plan_ids_to_flush)} plans before reload")
                                        flush_success = self.db_write_queue.flush_queue_for_plans(
                                            plan_ids_to_flush,
                                            timeout=10.0  # Don't wait too long
                                        )
                                        if not flush_success:
                                            logger.warning("Write queue flush timed out before plan reload - proceeding anyway")
                                except Exception as e:
                                    logger.warning(f"Error flushing write queue before reload: {e} - proceeding anyway")
                            try:
                                new_plans = self._load_plans()
                                # Merge new plans into existing plans (don't overwrite in-memory updates)
                                with self.plans_lock:
                                    for plan_id, new_plan in new_plans.items():
                                        if plan_id not in self.plans:
                                            # New plan - add it
                                            self.plans[plan_id] = new_plan
                                            logger.debug(f"Loaded new plan {plan_id} from database")
                                        # If plan already exists in memory, keep the in-memory version
                                        # (it may have been updated but not yet saved)
                                    # Remove plans that are no longer in database (cancelled/executed elsewhere)
                                    db_plan_ids = set(new_plans.keys())
                                    for plan_id in list(self.plans.keys()):
                                        if plan_id not in db_plan_ids and self.plans[plan_id].status == "pending":
                                            logger.debug(f"Plan {plan_id} no longer in database, removing from memory")
                                            plan_obj = self.plans.get(plan_id)
                                            plan_symbol = getattr(plan_obj, 'symbol', 'unknown') if plan_obj else 'unknown'
                                            del self.plans[plan_id]
                                            # Clean up execution locks and other resources
                                            self._cleanup_plan_resources(plan_id, plan_symbol)
                                self.last_plan_reload = now_utc
                            except Exception as e:
                                logger.error(f"Error reloading plans from database: {e}", exc_info=True)
                    
                    # Check each pending plan (use lock for thread-safe access)
                    try:
                        with self.plans_lock:
                            # Defensive check: ensure self.plans is valid
                            if self.plans is None:
                                logger.warning("self.plans is None, reinitializing...")
                                self.plans = {}
                            plans_to_check = list(self.plans.items())
                    except Exception as e:
                        logger.error(f"Error acquiring plans lock: {e}", exc_info=True)
                        # Skip this iteration if we can't get the lock
                        try:
                            time.sleep(self.check_interval)
                        except Exception as sleep_error:
                            logger.error(f"Error in sleep operation (critical): {sleep_error}")
                            # If sleep fails, use a short delay to avoid tight loop
                            import time as time_module
                            time_module.sleep(1.0)
                        continue
                    
                    # Defensive check: ensure plans_to_check is iterable
                    if plans_to_check is None:
                        logger.warning("plans_to_check is None, skipping plan iteration")
                        plans_to_check = []
                    
                    # Phase 2.2: Get current prices for all symbols (batch) - AFTER getting plans
                    # OPTIMIZATION: Only fetch if there are pending plans and features enabled
                    opt_config = self.config.get('optimized_intervals', {})
                    use_adaptive = opt_config.get('adaptive_intervals', {}).get('enabled', False)
                    use_conditional = opt_config.get('conditional_checks', {}).get('enabled', False)
                    
                    symbol_prices = {}
                    # Phase 2.1: Always use batch price fetching when there are plans to check
                    if plans_to_check:
                        try:
                            symbol_prices = self._get_current_prices_batch()
                            if symbol_prices:
                                logger.debug(f"Batch price fetch: Retrieved prices for {len(symbol_prices)} symbols")
                        except Exception as e:
                            logger.warning(f"Error fetching batch prices (non-fatal): {e}")
                            # Continue with empty dict - plans will use last known prices or skip adaptive checks
                            symbol_prices = {}
                    
                    # Phase 4.6: Parallel condition checking for market orders
                    now_utc = datetime.now(timezone.utc)
                    
                    # Separate order-flow plans from regular plans
                    order_flow_plans = []
                    regular_plans = []
                    
                    for plan_id, plan in plans_to_check:
                        # Skip non-pending plans
                        if plan.status != "pending":
                            continue
                        
                        # Check if plan has order-flow conditions
                        order_flow_conditions = [
                            "delta_positive", "delta_negative",
                            "cvd_rising", "cvd_falling",
                            "cvd_div_bear", "cvd_div_bull",
                            "delta_divergence_bull", "delta_divergence_bear",
                            "absorption_zone_detected"
                        ]
                        has_of_condition = any(plan.conditions.get(cond) for cond in order_flow_conditions)
                        
                        if has_of_condition:
                            order_flow_plans.append((plan_id, plan))
                        else:
                            regular_plans.append((plan_id, plan))
                    
                    # Phase 4.6: Process regular plans in parallel (grouped by priority)
                    if regular_plans:
                        # Filter plans through pre-checks (expiration, cancellation, adaptive intervals, etc.)
                        plans_to_check_parallel = []
                        for plan_id, plan in regular_plans:
                            # Defensive check: ensure plan still exists
                            try:
                                with self.plans_lock:
                                    if plan_id not in self.plans:
                                        continue
                                    plan = self.plans[plan_id]
                            except Exception:
                                continue
                            
                            # Validate plan object
                            if not plan or not hasattr(plan, 'status') or plan.status != "pending":
                                continue
                            
                            # Check expiration
                            if hasattr(plan, 'expires_at') and plan.expires_at:
                                try:
                                    expires_at_dt = datetime.fromisoformat(plan.expires_at.replace('Z', '+00:00'))
                                    if expires_at_dt.tzinfo is None:
                                        expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)
                                    if expires_at_dt < now_utc:
                                        continue  # Skip expired plans
                                except Exception:
                                    pass  # Continue if expiration check fails
                            
                            # Check weekend expiration
                            try:
                                if self._check_weekend_plan_expiration(plan):
                                    continue  # Skip expired weekend plans
                            except Exception:
                                pass
                            
                            # Check cancellation conditions
                            try:
                                cancellation_result = self._check_plan_cancellation_conditions(plan)
                                if cancellation_result and cancellation_result.get('should_cancel'):
                                    continue  # Skip cancelled plans
                            except Exception:
                                pass
                            
                            # Check adaptive intervals and conditional checks
                            symbol_norm = plan.symbol.upper().rstrip('Cc') + 'c'
                            current_price = symbol_prices.get(symbol_norm)
                            
                            # Skip if should be skipped (includes adaptive interval and conditional checks)
                            if self._should_skip_plan(plan, current_price):
                                continue
                            
                            # Additional conditional check
                            if use_conditional and current_price:
                                try:
                                    if not self._should_check_plan(plan, current_price):
                                        continue
                                except Exception:
                                    pass
                            
                            # All pre-checks passed - add to parallel check list
                            plans_to_check_parallel.append(plan)
                        
                        # Group by priority
                        high_priority = []
                        medium_priority = []
                        low_priority = []
                        
                        for plan in plans_to_check_parallel:
                            priority = self._get_plan_priority(plan, symbol_prices.get(plan.symbol.upper().rstrip('Cc') + 'c'))
                            if priority == 1:
                                high_priority.append(plan)
                            elif priority == 2:
                                medium_priority.append(plan)
                            else:
                                low_priority.append(plan)
                        
                        # Process in priority order (high -> medium -> low)
                        all_parallel_plans = high_priority + medium_priority + low_priority
                        
                        if all_parallel_plans:
                            # Check conditions in parallel
                            parallel_results = self._check_conditions_parallel(all_parallel_plans, symbol_prices)
                            
                            # Process results sequentially for execution
                            for plan in all_parallel_plans:
                                plan_id = plan.plan_id
                                conditions_met = parallel_results.get(plan_id, False)
                                
                                # Update last check time
                                with self.plans_lock:
                                    self._plan_last_check[plan_id] = now_utc
                                
                                if conditions_met:
                                    # Conditions met - execute trade
                                    logger.info(f"Conditions met for plan {plan_id}, executing trade")
                                    try:
                                        if self._execute_trade(plan):
                                            # Check plan status to determine if plan should be removed
                                            if plan.status == "executed":
                                                # Market order: Remove plan immediately
                                                with self.plans_lock:
                                                    if plan_id in self.plans:
                                                        del self.plans[plan_id]
                                                self._cleanup_plan_resources(plan_id, plan.symbol)
                                                logger.info(f"Plan {plan_id} executed and removed from memory")
                                            # pending_order_placed plans stay in memory for monitoring
                                    except Exception as e:
                                        logger.error(f"Error executing trade for plan {plan_id}: {e}", exc_info=True)
                    
                    # Phase 4.6: Process order-flow plans sequentially (preserve 5s interval)
                    for plan_id, plan in order_flow_plans:
                        # Defensive check: ensure plan still exists (race condition protection)
                        try:
                            with self.plans_lock:
                                if plan_id not in self.plans:
                                    continue
                                # Re-fetch plan in case it was updated
                                plan = self.plans[plan_id]
                        except Exception as e:
                            logger.warning(f"Error accessing plan {plan_id} (skipping): {e}")
                            continue
                        
                        # Validate plan object
                        if not plan or not hasattr(plan, 'status'):
                            logger.warning(f"Invalid plan object for {plan_id} (skipping)")
                            continue
                        
                        # Phase 4.3: Check expiration for ALL plans (including pending_order_placed) BEFORE status check
                        # This ensures pending orders are also checked for expiration
                        if hasattr(plan, 'expires_at') and plan.expires_at:
                            try:
                                expires_at_dt = datetime.fromisoformat(plan.expires_at.replace('Z', '+00:00'))
                                if expires_at_dt.tzinfo is None:
                                    expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)
                                now_utc_check = datetime.now(timezone.utc)
                                
                                if expires_at_dt < now_utc_check:
                                    # Plan expired - cancel pending order if exists
                                    if (plan.status == "pending_order_placed" and 
                                        hasattr(plan, 'pending_order_ticket') and 
                                        plan.pending_order_ticket):
                                        try:
                                            import MetaTrader5 as mt5
                                            if self.mt5_service.connect():
                                                request = {
                                                    "action": mt5.TRADE_ACTION_REMOVE,
                                                    "order": plan.pending_order_ticket,
                                                }
                                                result = mt5.order_send(request)
                                                if result.retcode == mt5.TRADE_RETCODE_DONE:
                                                    logger.info(f"Cancelled pending order {plan.pending_order_ticket} for expired plan {plan_id}")
                                                else:
                                                    logger.warning(f"Failed to cancel pending order {plan.pending_order_ticket} for expired plan {plan_id}: retcode={result.retcode}")
                                            else:
                                                logger.warning(f"MT5 not connected - cannot cancel pending order for expired plan {plan_id}")
                                        except Exception as e:
                                            logger.error(f"Error cancelling pending order for expired plan {plan_id}: {e}", exc_info=True)
                                    
                                    # Plan expired - update database and remove from memory
                                    plan.status = "expired"
                                    self._update_plan_status(plan)
                                    with self.plans_lock:
                                        if plan_id in self.plans:
                                            del self.plans[plan_id]
                                    # Clean up execution locks and other resources
                                    self._cleanup_plan_resources(plan_id, plan.symbol)
                                    logger.info(f"Plan {plan_id} expired and marked as expired in database")
                                    continue
                            except Exception as e:
                                logger.warning(f"Error checking expiration for plan {plan_id}: {e}")
                                # Continue checking plan if expiration check fails
                        
                        # Phase 4.3: Skip plans that are not "pending" (including pending_order_placed)
                        # pending_order_placed plans are monitored by _check_pending_orders(), not condition checks
                        if plan.status != "pending":
                            continue
                        
                        # Check weekend plan expiration (24h if price not near entry)
                        try:
                            if self._check_weekend_plan_expiration(plan):
                                # Phase 4.3: Weekend plan expired - cancel pending order if exists
                                if (plan.status == "pending_order_placed" and 
                                    hasattr(plan, 'pending_order_ticket') and 
                                    plan.pending_order_ticket):
                                    try:
                                        import MetaTrader5 as mt5
                                        if self.mt5_service.connect():
                                            request = {
                                                "action": mt5.TRADE_ACTION_REMOVE,
                                                "order": plan.pending_order_ticket,
                                            }
                                            result = mt5.order_send(request)
                                            if result.retcode == mt5.TRADE_RETCODE_DONE:
                                                logger.info(f"Cancelled pending order {plan.pending_order_ticket} for weekend expired plan {plan_id}")
                                            else:
                                                logger.warning(f"Failed to cancel pending order {plan.pending_order_ticket} for weekend expired plan {plan_id}: retcode={result.retcode}")
                                        else:
                                            logger.warning(f"MT5 not connected - cannot cancel pending order for weekend expired plan {plan_id}")
                                    except Exception as e:
                                        logger.error(f"Error cancelling pending order for weekend expired plan {plan_id}: {e}", exc_info=True)
                                
                                # Weekend plan expired - update database and remove from memory
                                if hasattr(plan, 'status'):
                                    plan.status = "expired"
                                try:
                                    self._update_plan_status(plan)
                                except Exception as e:
                                    logger.error(f"Error updating weekend expired plan status for {plan_id}: {e}", exc_info=True)
                                
                                try:
                                    with self.plans_lock:
                                        if plan_id in self.plans:
                                            del self.plans[plan_id]
                                except Exception as e:
                                    logger.warning(f"Error removing weekend expired plan {plan_id} from memory: {e}")
                                
                                # Clean up execution locks and other resources
                                plan_symbol = getattr(plan, 'symbol', 'unknown')
                                self._cleanup_plan_resources(plan_id, plan_symbol)
                                logger.info(f"Weekend plan {plan_id} expired (24h + price distance check)")
                                continue
                        except Exception as e:
                            logger.warning(f"Error checking weekend plan expiration for {plan_id}: {e}", exc_info=True)
                            # Continue - weekend expiration check failure shouldn't block monitoring
                        
                        # Phase 3: Check conditional cancellation (after expiration check, before execution check)
                        try:
                            cancellation_result = self._check_plan_cancellation_conditions(plan)
                            if cancellation_result and cancellation_result.get('should_cancel'):
                                # Plan should be cancelled - update database and remove from memory
                                cancellation_reason = cancellation_result.get('reason', 'Conditional cancellation')
                                priority = cancellation_result.get('priority', 'medium')
                                
                                logger.info(f"Plan {plan_id} cancelled ({priority} priority): {cancellation_reason}")
                                
                                # Update plan status with cancellation reason
                                plan.status = "cancelled"
                                plan.cancellation_reason = cancellation_reason
                                
                                try:
                                    self.cancel_plan(plan_id, cancellation_reason)
                                except Exception as e:
                                    logger.error(f"Error cancelling plan {plan_id}: {e}", exc_info=True)
                                
                                # Remove from memory
                                try:
                                    with self.plans_lock:
                                        if plan_id in self.plans:
                                            del self.plans[plan_id]
                                except Exception as e:
                                    logger.warning(f"Error removing cancelled plan {plan_id} from memory: {e}")
                                
                                # Clean up execution locks and other resources
                                plan_symbol = getattr(plan, 'symbol', 'unknown')
                                self._cleanup_plan_resources(plan_id, plan_symbol)
                                continue
                        except Exception as e:
                            logger.warning(f"Error checking cancellation conditions for {plan_id}: {e}", exc_info=True)
                            # Continue - cancellation check failure shouldn't block monitoring
                        
                        # Phase 2.2: Adaptive interval check - AFTER expiration/cancellation checks
                        # CRITICAL: Must happen AFTER expiration/cancellation but BEFORE expensive checks
                        should_skip_due_to_interval = False
                        if use_adaptive:
                            try:
                                symbol_norm = plan.symbol.upper().rstrip('Cc') + 'c'
                                current_price = symbol_prices.get(symbol_norm)
                                
                                if current_price is not None:
                                    # Calculate adaptive interval
                                    interval = self._calculate_adaptive_interval(plan, current_price)
                                    
                                    # Check if enough time has passed since last check
                                    last_check = self._plan_last_check.get(plan_id)
                                if last_check:
                                    time_since_check = (now_utc - last_check).total_seconds()
                                    if time_since_check < interval:
                                        # Not enough time passed - skip this check
                                        should_skip_due_to_interval = True
                                        logger.debug(
                                            f"Adaptive interval: Skipping {plan_id} - "
                                            f"only {time_since_check:.1f}s since last check "
                                            f"(required: {interval}s)"
                                        )
                                    
                                    # Store current price for next iteration (even if skipping)
                                    self._plan_last_price[plan_id] = current_price
                                else:
                                    # Price not available - use last known price if available
                                    current_price = self._plan_last_price.get(plan_id)
                                    if current_price is None:
                                        # No price available - skip adaptive check, continue with normal flow
                                        pass
                            except Exception as e:
                                logger.debug(f"Error in adaptive interval check for {plan_id}: {e}")
                                # Continue with normal check if adaptive check fails
                        
                        if should_skip_due_to_interval:
                            continue  # Skip this plan - not enough time passed
                        
                        # Phase 4: Conditional check - skip if price is too far from entry
                        if use_conditional:
                            try:
                                symbol_norm = plan.symbol.upper().rstrip('Cc') + 'c'
                                current_price = symbol_prices.get(symbol_norm) or self._plan_last_price.get(plan_id)
                                
                                if current_price is not None:
                                    if not self._should_check_plan(plan, current_price):
                                        # Price too far - skip check
                                        # NOTE: Don't update last_check time since we skipped
                                        continue
                            except Exception as e:
                                logger.debug(f"Error in conditional check for {plan_id}: {e}")
                                # Continue with normal check if conditional check fails
                        
                        # Phase 4: Check re-evaluation triggers (after cancellation, before execution)
                        try:
                            if self._should_trigger_re_evaluation(plan):
                                logger.info(f"Plan {plan_id}: Re-evaluation trigger fired, re-evaluating plan")
                                re_eval_result = self._re_evaluate_plan(plan, force=False)
                                
                                # Log re-evaluation result
                                action = re_eval_result.get('action', 'keep')
                                recommendation = re_eval_result.get('recommendation', 'No action needed')
                                logger.debug(f"Plan {plan_id} re-evaluation result: {action} - {recommendation}")
                                
                                # For now, we just track re-evaluation - actual plan updates/replacements
                                # will be implemented in future enhancements
                                # TODO: Implement plan update/replacement logic based on re_eval_result
                        except Exception as e:
                            logger.warning(f"Error checking re-evaluation triggers for {plan_id}: {e}", exc_info=True)
                            # Continue - re-evaluation check failure shouldn't block monitoring
                        
                        # Real-Time M1 Update Detection: Check signal staleness and changes (Phase 2.1.1)
                        try:
                            if self._is_m1_signal_stale(plan):
                                logger.debug(f"Plan {plan_id}: M1 signal is stale, skipping check")
                                continue
                        except Exception as e:
                            logger.debug(f"Error checking M1 signal staleness for {plan_id} (continuing): {e}")
                            # Continue - staleness check failure shouldn't block condition checking
                        
                        # Detect signal changes and re-evaluate if needed
                        try:
                            if self._has_m1_signal_changed(plan):
                                logger.info(f"Plan {plan_id}: M1 signal changed, re-evaluating conditions")
                                # Signal changed - continue to check conditions
                        except Exception as e:
                            logger.debug(f"Error checking M1 signal changes for {plan_id} (continuing): {e}")
                            # Continue - signal change check failure shouldn't block condition checking
                        
                        # Phase 3: Invalidate cache on candle close (before M1 refresh)
                        try:
                            if plan and hasattr(plan, 'symbol') and plan.symbol:
                                symbol_base = plan.symbol.upper().rstrip('Cc')
                                symbol_norm = symbol_base + 'c'
                                self._invalidate_cache_on_candle_close(symbol_norm, 'M1')
                        except Exception as e:
                            symbol_str = getattr(plan, 'symbol', 'unknown') if plan else 'unknown'
                            logger.debug(f"Error invalidating cache on candle close for {symbol_str} (non-fatal): {e}")
                            # Continue - cache invalidation failure shouldn't block condition checking
                        
                        # Refresh M1 data if needed (Phase 2.1.1)
                        try:
                            if self.config and self.config.get('m1_integration', {}).get('refresh_before_check', True):
                                if self.m1_refresh_manager and plan and hasattr(plan, 'symbol') and plan.symbol:
                                    symbol_base = plan.symbol.upper().rstrip('Cc')
                                    symbol_norm = symbol_base + 'c'
                                    stale_threshold = self.config.get('m1_integration', {}).get('stale_threshold_seconds', 180)
                                    self.m1_refresh_manager.check_and_refresh_stale(symbol_norm, max_age_seconds=stale_threshold)
                        except (AttributeError, TypeError) as e:
                            symbol_str = getattr(plan, 'symbol', 'unknown') if plan else 'unknown'
                            logger.debug(f"Error refreshing M1 data for {symbol_str} (non-fatal): {e}")
                            # Continue - M1 refresh failure shouldn't block condition checking
                        except Exception as e:
                            symbol_str = getattr(plan, 'symbol', 'unknown') if plan else 'unknown'
                            logger.debug(f"Error refreshing M1 data for {symbol_str} (non-fatal): {e}")
                            # Continue - M1 refresh failure shouldn't block condition checking
                        
                        # Check conditions
                        plan_was_executed = False
                        try:
                            # Phase 6: Track condition check
                            self._condition_checks_total += 1
                            
                            if self._check_conditions(plan):
                                self._condition_checks_success += 1
                                logger.info(f"Conditions met for plan {plan_id}, executing trade")
                                try:
                                    if self._execute_trade(plan):
                                        # Phase 4.3: Check plan status to determine if plan should be removed
                                        # _execute_trade() sets status to "pending_order_placed" for pending orders
                                        # and "executed" for market orders
                                        if plan.status == "executed":
                                            # Market order: Remove plan immediately (current behavior)
                                            try:
                                                with self.plans_lock:
                                                    if plan_id in self.plans:
                                                        del self.plans[plan_id]
                                                        plan_was_executed = True  # Plan was executed and removed
                                            except Exception as e:
                                                logger.warning(f"Error removing plan {plan_id} from memory: {e}")
                                            
                                            if plan_id in self.execution_failures:
                                                del self.execution_failures[plan_id]
                                            # Clear symbol failure count on successful execution
                                            plan_symbol = getattr(plan, 'symbol', None)
                                            if plan_symbol and plan_symbol in self.invalid_symbols:
                                                del self.invalid_symbols[plan_symbol]
                                            # Clean up execution locks and other resources
                                            self._cleanup_plan_resources(plan_id, plan_symbol or 'unknown')
                                        elif plan.status == "pending_order_placed":
                                            # Pending order: Keep plan in memory, status already updated
                                            # Don't remove - will be monitored until order fills
                                            # Don't set plan_was_executed = True (plan hasn't executed yet, just placed as pending)
                                            logger.debug(f"Plan {plan_id} has pending order - keeping in memory for monitoring")
                                            # Clear execution failures since order was placed successfully
                                            if plan_id in self.execution_failures:
                                                del self.execution_failures[plan_id]
                                        else:
                                            # Unexpected status - log warning but don't remove
                                            logger.warning(f"Plan {plan_id} has unexpected status after execution: {plan.status}")
                                            # Don't set plan_was_executed = True for unexpected status
                                    else:
                                        # Execution failed - track retry count
                                        failure_count = self.execution_failures.get(plan_id, 0) + 1
                                        self.execution_failures[plan_id] = failure_count
                                        
                                        if failure_count >= self.max_execution_retries:
                                            # Too many failures - mark as failed and remove from monitoring
                                            logger.error(f"Plan {plan_id} failed {failure_count} times, marking as failed")
                                            plan.status = "failed"
                                            try:
                                                self._update_plan_status(plan)
                                            except Exception as e:
                                                logger.error(f"Error updating plan status for {plan_id}: {e}", exc_info=True)
                                            
                                            try:
                                                with self.plans_lock:
                                                    if plan_id in self.plans:
                                                        del self.plans[plan_id]
                                            except Exception as e:
                                                logger.warning(f"Error removing failed plan {plan_id} from memory: {e}")
                                            
                                            if plan_id in self.execution_failures:
                                                del self.execution_failures[plan_id]
                                            # Clean up execution locks and other resources
                                            plan_symbol = getattr(plan, 'symbol', 'unknown')
                                            self._cleanup_plan_resources(plan_id, plan_symbol)
                                        else:
                                            logger.warning(f"Failed to execute plan {plan_id} (attempt {failure_count}/{self.max_execution_retries})")
                                except Exception as e:
                                    logger.error(f"Error executing trade for plan {plan_id}: {e}", exc_info=True)
                                    # Track execution error
                                    failure_count = self.execution_failures.get(plan_id, 0) + 1
                                    self.execution_failures[plan_id] = failure_count
                        except Exception as e:
                            logger.error(f"Error checking conditions for plan {plan_id}: {e}", exc_info=True)
                            # Continue to next plan - condition check failure shouldn't kill the thread
                        
                        # Phase 2.2: Update last check time - ONLY if we actually checked the plan
                        # CRITICAL: Only update if:
                        #   1. We didn't skip due to interval or conditional check
                        #   2. Plan still exists (wasn't removed due to successful execution)
                        if use_adaptive and not plan_was_executed:
                            # Only update if we actually performed the check AND plan still exists
                            # (If plan was executed and removed, _cleanup_plan_resources will clean up tracking dicts)
                            try:
                                with self.plans_lock:
                                    if plan_id in self.plans:
                                        self._plan_last_check[plan_id] = now_utc
                            except Exception as e:
                                logger.debug(f"Error updating last check time for {plan_id}: {e}")
                                # Non-critical - continue
                    
                    # Sleep before next check (use Event.wait to allow immediate wake-up on stop)
                    try:
                        # Defensive check: ensure check_interval is valid
                        sleep_duration = self.check_interval if self.check_interval is not None and self.check_interval > 0 else 30.0
                        # Use Event.wait instead of time.sleep to allow immediate wake-up when stopping
                        # This prevents the thread from waiting the full 30s if stop() is called
                        self._stop_event.wait(timeout=sleep_duration)
                        # Clear the event for next iteration
                        self._stop_event.clear()
                    except (TypeError, ValueError) as e:
                        logger.error(f"Error in sleep operation (critical): {e}")
                        # If sleep fails, use default duration to avoid tight loop
                        self._stop_event.wait(timeout=30.0)
                        self._stop_event.clear()
                    except Exception as e:
                        logger.error(f"Unexpected error in sleep operation: {e}")
                        # Fallback to default sleep
                        self._stop_event.wait(timeout=30.0)
                        self._stop_event.clear()
                
                except KeyboardInterrupt:
                    logger.info("Monitor loop received KeyboardInterrupt, stopping...")
                    self.running = False
                    break
                except Exception as e:
                    # Improved exception logging with full context
                    import traceback
                    thread_name = threading.current_thread().name
                    error_details = {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "thread_name": thread_name,
                        "pending_plans": len(self.plans) if hasattr(self, 'plans') else 0,
                        "running": self.running,
                        "check_interval": self.check_interval
                    }
                    logger.error(
                        f"Error in monitoring loop (thread: {thread_name}): {type(e).__name__}: {e}",
                        extra={"error_details": error_details},
                        exc_info=True
                    )
                    logger.error(f"Full traceback:\n{traceback.format_exc()}")
                    
                    # Continue monitoring despite error (unless it's a fatal error)
                    # Sleep before retrying to avoid tight error loops
                    time.sleep(self.check_interval)
        
        except Exception as fatal_error:
            # Fatal error that breaks out of the while loop
            import traceback
            thread_name = threading.current_thread().name
            logger.critical(
                f"FATAL ERROR in monitor loop (thread: {thread_name}): {fatal_error}",
                exc_info=True
            )
            logger.critical(f"Fatal error traceback:\n{traceback.format_exc()}")
            
            # CRITICAL FIX: Don't set self.running = False immediately
            # This allows the health check to detect that the thread died while system should be running
            # and automatically restart it. If we set self.running = False, the health check logic
            # might not restart it properly.
            
            # Log that health check should restart the thread
            logger.error(
                f"Monitor thread died due to fatal error. "
                f"Health check will detect dead thread and attempt to restart "
                f"(restart count: {self.thread_restart_count}/{self.max_thread_restarts})"
            )
            
            # Note: We leave self.running as True (or whatever it was) so the health check
            # can detect the mismatch between self.running and thread status
        
        finally:
            thread_name = threading.current_thread().name
            logger.info(f"Monitor loop exiting (thread: {thread_name}, running: {self.running})")
    
    def start(self):
        """Start the auto execution system"""
        if self.running:
            logger.warning("Auto execution system already running")
            return
        
        # Check if thread is still alive but system thinks it's not running
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("Monitor thread is still alive, but system marked as not running. Restarting...")
            self.running = False
            try:
                self.monitor_thread.join(timeout=2.0)
            except Exception:
                pass
            
        self.running = True
        # Reset stop event for new thread
        self._stop_event.clear()
        
        # Phase 6: Initialize performance metrics
        self._metrics_start_time = datetime.now(timezone.utc)
        self._metrics_last_log = None
        
        # Phase 4.2: Initialize thread pool executor for parallel condition checking
        if self._condition_check_executor is None:
            # Calculate optimal thread pool size: min(4, (os.cpu_count() or 1) + 4) for I/O bound tasks
            cpu_count = os.cpu_count() or 1
            max_workers = min(4, cpu_count + 4)
            self._condition_check_executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ConditionCheck")
            logger.info(f"Phase 4: Thread pool executor initialized with {max_workers} workers")
        
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=False,  # CRITICAL: Non-daemon thread so it doesn't die when main thread exits
            name="AutoExecutionMonitor"
        )
        self.monitor_thread.start()
        self.last_health_check = datetime.now(timezone.utc)
        
        # CRITICAL: Start watchdog thread to continuously monitor health
        self._start_watchdog_thread()
        
        # Phase 3: Start pre-fetch thread if enabled
        opt_config = self.config.get('optimized_intervals', {})
        if opt_config.get('smart_caching', {}).get('enabled', False):
            self.prefetch_thread = threading.Thread(
                target=self._prefetch_data_before_expiry,
                name="AutoExecutionPrefetch",
                daemon=True  # Daemon thread - will exit when main thread exits
            )
            self.prefetch_thread.start()
            logger.info("Smart caching: Pre-fetch thread started")
        
        # Log optimized intervals status
        adaptive_enabled = opt_config.get('adaptive_intervals', {}).get('enabled', False)
        caching_enabled = opt_config.get('smart_caching', {}).get('enabled', False)
        conditional_enabled = opt_config.get('conditional_checks', {}).get('enabled', False)
        batch_enabled = opt_config.get('batch_operations', {}).get('enabled', False)
        
        if adaptive_enabled or caching_enabled or conditional_enabled or batch_enabled:
            logger.info("Optimized intervals system ENABLED:")
            if adaptive_enabled:
                m1_config = opt_config.get('adaptive_intervals', {}).get('plan_type_intervals', {}).get('m1_micro_scalp', {})
                base_interval = m1_config.get('base_interval_seconds', 30)
                logger.info(f"  - Adaptive intervals: ENABLED (M1 base: {base_interval}s)")
            if caching_enabled:
                logger.info("  - Smart caching: ENABLED")
            if conditional_enabled:
                logger.info("  - Conditional checks: ENABLED")
            if batch_enabled:
                logger.info("  - Batch operations: ENABLED")
        else:
            logger.info("Optimized intervals system: DISABLED (enable via config file)")
        
        logger.info(f"Auto execution system started (thread: {self.monitor_thread.name}, daemon: {self.monitor_thread.daemon})")
        logger.info(f"Watchdog thread started for continuous health monitoring")
    
    def _start_watchdog_thread(self):
        """Start watchdog thread that continuously monitors and restarts the monitor thread if it dies"""
        if self.watchdog_thread and self.watchdog_thread.is_alive():
            logger.warning("Watchdog thread already running")
            return
        
        def watchdog_loop():
            """Watchdog loop that continuously checks thread health"""
            thread_name = threading.current_thread().name
            logger.info(f"Watchdog thread started (thread: {thread_name})")
            
            try:
                while self.running:
                    try:
                        # Check health every health_check_interval seconds
                        time.sleep(self.health_check_interval)
                        
                        # Perform health check
                        self._check_thread_health()
                        
                    except Exception as e:
                        logger.error(f"Error in watchdog loop: {e}", exc_info=True)
                        # Continue - watchdog should never die
                        time.sleep(5.0)  # Short sleep before retrying
            except Exception as fatal_error:
                logger.critical(f"FATAL ERROR in watchdog loop: {fatal_error}", exc_info=True)
                # Even on fatal error, try to restart watchdog
                try:
                    if self.running:
                        logger.error("Watchdog thread died but system should be running. Attempting to restart watchdog...")
                        time.sleep(10.0)  # Wait before restarting
                        if self.running:
                            self._start_watchdog_thread()
                except Exception:
                    pass  # If we can't restart, log and give up
        
        self.watchdog_thread = threading.Thread(
            target=watchdog_loop,
            daemon=False,  # CRITICAL: Non-daemon so it doesn't die
            name="AutoExecutionWatchdog"
        )
        self.watchdog_thread.start()
        logger.info("Watchdog thread started successfully")
    
    def stop(self):
        """Stop the auto execution system"""
        logger.info("Stopping auto execution system...")
        self.running = False
        
        # Signal stop event to wake up monitor thread immediately (if it's sleeping)
        try:
            self._stop_event.set()
        except Exception as e:
            logger.debug(f"Error setting stop event: {e}")
        
        # Stop watchdog thread
        if self.watchdog_thread and self.watchdog_thread.is_alive():
            logger.debug("Waiting for watchdog thread to finish...")
            try:
                self.watchdog_thread.join(timeout=2.0)
            except Exception as e:
                logger.debug(f"Error joining watchdog thread: {e}")
        
        if self.monitor_thread:
            # Wait for thread to finish with timeout
            if self.monitor_thread.is_alive():
                logger.debug(f"Waiting for monitor thread to finish (timeout: 5s)...")
                self.monitor_thread.join(timeout=5.0)
                
                if self.monitor_thread.is_alive():
                    logger.warning("Monitor thread did not stop within timeout. Thread will terminate as daemon.")
                    # Force cleanup: mark thread as daemon so it doesn't block shutdown
                    try:
                        self.monitor_thread.daemon = True
                    except Exception as e:
                        logger.debug(f"Error setting thread as daemon: {e}")
                else:
                    logger.debug("Monitor thread stopped successfully")
            else:
                logger.debug("Monitor thread was already dead")
        
        # Phase 3: Stop pre-fetch thread if running
        if hasattr(self, 'prefetch_thread') and self.prefetch_thread and self.prefetch_thread.is_alive():
            logger.debug("Waiting for pre-fetch thread to finish...")
            try:
                self.prefetch_thread.join(timeout=2.0)
            except Exception as e:
                logger.debug(f"Error joining pre-fetch thread: {e}")
        
        # Phase 4.7: Cleanup thread pool executor (BEFORE monitor thread stops)
        if hasattr(self, '_condition_check_executor') and self._condition_check_executor:
            try:
                logger.debug("Shutting down thread pool executor...")
                self._condition_check_executor.shutdown(wait=True, timeout=5.0)
                self._condition_check_executor = None
                logger.debug("Thread pool executor shut down successfully")
            except FutureTimeoutError:
                logger.warning("Thread pool executor shutdown timed out - forcing shutdown")
                # Force shutdown if timeout
                try:
                    self._condition_check_executor.shutdown(wait=False)
                except Exception:
                    pass
                self._condition_check_executor = None
            except Exception as e:
                logger.warning(f"Error shutting down thread pool executor: {e}")
        
        # Phase 3.5: Cleanup database manager
        if hasattr(self, '_db_manager') and self._db_manager:
            try:
                logger.debug("Closing OptimizedSQLiteManager...")
                self._db_manager.close()
                self._db_manager = None
                logger.debug("OptimizedSQLiteManager closed successfully")
            except Exception as e:
                logger.warning(f"Error closing OptimizedSQLiteManager: {e}")
        
        # Reset restart counter on clean stop
        self.thread_restart_count = 0
        logger.info("Auto execution system stopped")
    
    def _check_thread_health(self):
        """Check if monitor thread is alive and restart if needed"""
        try:
            now = datetime.now(timezone.utc)
            
            # Safely check time since last check
            try:
                time_since_check = (now - self.last_health_check).total_seconds()
            except (AttributeError, TypeError) as e:
                logger.warning(f"Error calculating time since last health check: {e}. Resetting.")
                self.last_health_check = now
                time_since_check = float('inf')  # Force check
            
            # Only check health periodically to avoid overhead
            if time_since_check < self.health_check_interval:
                return
            
            self.last_health_check = now
            
            # CRITICAL FIX: Check if system SHOULD be running (self.running == True) but thread is dead
            # This handles cases where fatal errors killed the thread but self.running is still True
            if self.running:
                # System should be running - verify thread is actually alive
                try:
                    thread_dead = self.monitor_thread is None or not self.monitor_thread.is_alive()
                except Exception as e:
                    logger.warning(f"Error checking thread status: {e}")
                    thread_dead = True  # Assume dead if we can't check
                
                if thread_dead:
                    logger.error(
                        "System should be running but thread is dead! "
                        "Thread may have died from a fatal error. Attempting to restart..."
                    )
                    # Don't change self.running - it's already True, just restart the thread
                    self._restart_monitor_thread()
                    return
            
            # Also check if system was marked as not running but thread is still alive (orphaned thread)
            if not self.running:
                try:
                    thread_alive = self.monitor_thread is not None and self.monitor_thread.is_alive()
                    if thread_alive:
                        logger.warning(
                            "System marked as not running but thread is still alive. "
                            "This may indicate a state mismatch. Cleaning up..."
                        )
                        # Thread is orphaned - stop it properly
                        try:
                            if self.monitor_thread:
                                self.monitor_thread.join(timeout=2.0)
                        except Exception as e:
                            logger.debug(f"Error joining orphaned thread: {e}")
                except Exception as e:
                    logger.debug(f"Error checking orphaned thread status: {e}")
                return
            
            # Safely check if thread is None
            if self.monitor_thread is None:
                logger.warning("Monitor thread is None but system is running. Restarting...")
                self._restart_monitor_thread()
                return
            
            # Safely check if thread is alive
            try:
                is_alive = self.monitor_thread.is_alive()
            except Exception as e:
                logger.error(f"Error checking if thread is alive: {e}", exc_info=True)
                is_alive = False  # Assume dead if we can't check
            
            if not is_alive:
                logger.error(
                    f"Monitor thread died! System running={self.running}, thread=None or dead. "
                    f"Restarting... (restart count: {self.thread_restart_count}/{self.max_thread_restarts})"
                )
                # Ensure system is marked as running before restart
                if not self.running:
                    logger.warning("System was marked as not running, but thread died. Resetting to running state.")
                    self.running = True
                self._restart_monitor_thread()
        except Exception as e:
            logger.error(f"Error in health check itself (non-fatal): {e}", exc_info=True)
            # Don't let health check errors kill the system
            # Just log and continue
    
    def _restart_monitor_thread(self):
        """Restart the monitor thread if it died"""
        if self.thread_restart_count >= self.max_thread_restarts:
            logger.error(
                f"Maximum thread restart attempts ({self.max_thread_restarts}) reached. "
                "Stopping auto-execution system. Manual restart required."
            )
            self.running = False
            return
        
        try:
            # Clean up old thread reference
            old_thread = self.monitor_thread
            if old_thread and old_thread.is_alive():
                logger.warning("Old monitor thread still alive, attempting to stop it...")
                self.running = False
                # Signal stop event to wake up old thread immediately
                try:
                    self._stop_event.set()
                except Exception as e:
                    logger.debug(f"Error setting stop event for old thread: {e}")
                try:
                    old_thread.join(timeout=2.0)
                except Exception as e:
                    logger.debug(f"Error joining old thread: {e}")
            
            self.monitor_thread = None
            
            # Reset running flag and start new thread
            self.running = True
            # Reset stop event for restarted thread
            self._stop_event.clear()
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=False,  # CRITICAL: Non-daemon thread so it doesn't die when main thread exits
                name=f"AutoExecutionMonitor-Restart{self.thread_restart_count + 1}"
            )
            self.monitor_thread.start()
            self.thread_restart_count += 1
            self.last_health_check = datetime.now(timezone.utc)
            
            # Ensure watchdog is running (it should be, but verify)
            if not self.watchdog_thread or not self.watchdog_thread.is_alive():
                logger.warning("Watchdog thread not running, restarting...")
                self._start_watchdog_thread()
            
            # Give thread a moment to start
            import time
            time.sleep(0.1)
            
            # Verify thread actually started
            if self.monitor_thread.is_alive():
                logger.info(
                    f"Monitor thread restarted successfully "
                    f"(attempt {self.thread_restart_count}/{self.max_thread_restarts})"
                )
            else:
                logger.error("Monitor thread failed to start after restart attempt")
                self.running = False
        except Exception as e:
            logger.error(f"Failed to restart monitor thread: {e}", exc_info=True)
            self.running = False
    
    def get_status(self, include_all_statuses: bool = False) -> Dict[str, Any]:
        """Get system status"""
        # ALWAYS check thread health before returning status (critical for reliability)
        # This ensures the thread is restarted if it died, even if health_check_interval hasn't passed
        try:
            self._check_thread_health()
        except Exception as e:
            logger.error(f"Error in health check during get_status: {e}", exc_info=True)
        
        # First, check for and mark expired plans in database
        # This ensures expired plans are updated even if monitoring loop hasn't run
        self._check_and_mark_expired_plans()
        
        # Reload plans from database to ensure we have all pending plans
        # This ensures plans created by other processes or after system initialization are included
        with self.plans_lock:
            self.plans = self._load_plans()
        
        plans_list = [asdict(plan) for plan in self.plans.values()]
        
        # If requested, also include non-pending plans (for web interface)
        if include_all_statuses:
            all_plans = self._load_all_plans()
            # Merge with pending plans, avoiding duplicates
            pending_ids = {p.plan_id for p in self.plans.values()}
            for plan in all_plans:
                if plan.plan_id not in pending_ids:
                    plans_list.append(asdict(plan))
        
        # Count ALL pending plans from database (excluding expired ones now)
        # This gives accurate count for monitoring status display
        total_pending_count = 0
        try:
            now_utc = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM trade_plans 
                    WHERE status = 'pending'
                    AND (expires_at IS NULL OR expires_at > ?)
                """, (now_utc,))
                total_pending_count = cursor.fetchone()[0]
        except Exception as e:
            logger.warning(f"Error counting pending plans from database: {e}")
            # Fallback to in-memory count if database query fails
            total_pending_count = len(self.plans)
        
        # Check thread status for status response
        thread_alive = False
        try:
            if self.monitor_thread is not None:
                thread_alive = self.monitor_thread.is_alive()
        except Exception as e:
            logger.debug(f"Error checking thread alive status: {e}")
            thread_alive = False
        
        return {
            "running": self.running,
            "thread_alive": thread_alive,
            "pending_plans": total_pending_count,  # Use database count, not in-memory count
            "check_interval": self.check_interval,
            "plans": plans_list
        }
    
    def _check_and_mark_expired_plans(self) -> None:
        """Check database for expired plans and mark them as expired.
        This is called before loading plans to ensure expired plans are updated
        even if the monitoring loop hasn't run or system was restarted."""
        try:
            now_utc = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(self.db_path, timeout=5.0) as conn:
                # Find all pending plans that have expired
                cursor = conn.execute("""
                    SELECT plan_id, expires_at FROM trade_plans 
                    WHERE status = 'pending'
                    AND expires_at IS NOT NULL
                    AND expires_at <= ?
                """, (now_utc,))
                
                expired_plans = cursor.fetchall()
                
                if expired_plans:
                    logger.info(f"Found {len(expired_plans)} expired plans in database, marking as expired...")
                    for row in expired_plans:
                        plan_id = row[0]
                        expires_at = row[1]
                        try:
                            # Update status to expired
                            conn.execute("""
                                UPDATE trade_plans 
                                SET status = 'expired'
                                WHERE plan_id = ?
                            """, (plan_id,))
                            logger.info(f"Marked plan {plan_id} as expired (expired at {expires_at})")
                        except Exception as e:
                            logger.warning(f"Error marking plan {plan_id} as expired: {e}")
                    
                    conn.commit()
                    logger.info(f"Successfully marked {len(expired_plans)} expired plans in database")
        except Exception as e:
            logger.warning(f"Error checking for expired plans: {e}")
    
    def _load_all_plans(self) -> List[TradePlan]:
        """Load all trade plans from database (any status)"""
        plans = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM trade_plans 
                ORDER BY created_at DESC
                LIMIT 100
            """)
            
            rows = cursor.fetchall()
        
        # Process rows after connection is closed
        for row in rows:
            try:
                plan_id = row[0]
                volume = row[6] if row[6] and row[6] > 0 else 0.01
                conditions_json = row[7]
                
                # Parse JSON with error handling
                try:
                    conditions = json.loads(conditions_json) if conditions_json else {}
                except json.JSONDecodeError as e:
                    logger.warning(f"Skipping plan {plan_id}: Invalid JSON in conditions: {e}")
                    continue
                
                # Handle new columns (profit_loss, exit_price, close_time, close_reason) - indices 15-18
                profit_loss = row[15] if len(row) > 15 else None
                exit_price = row[16] if len(row) > 16 else None
                close_time = row[17] if len(row) > 17 else None
                close_reason = row[18] if len(row) > 18 else None
                # Phase 1: Zone tracking fields - indices 19-21
                zone_entry_tracked = row[19] if len(row) > 19 else False
                zone_entry_time = row[20] if len(row) > 20 else None
                zone_exit_time = row[21] if len(row) > 21 else None
                # Phase 2: Entry levels - index 22
                entry_levels_json = row[22] if len(row) > 22 else None
                entry_levels = None
                if entry_levels_json:
                    try:
                        entry_levels = json.loads(entry_levels_json)
                    except json.JSONDecodeError:
                        pass
                # Phase 3: Cancellation tracking - indices 23-24
                cancellation_reason = row[23] if len(row) > 23 else None
                last_cancellation_check = row[24] if len(row) > 24 else None
                # Phase 4: Re-evaluation tracking - indices 25-27
                last_re_evaluation = row[25] if len(row) > 25 else None
                re_evaluation_count_today = row[26] if len(row) > 26 else 0
                re_evaluation_count_date = row[27] if len(row) > 27 else None
                
                plan = TradePlan(
                    plan_id=plan_id,
                    symbol=row[1],
                    direction=row[2],
                    entry_price=row[3],
                    stop_loss=row[4],
                    take_profit=row[5],
                    volume=volume,
                    conditions=conditions,
                    created_at=row[8],
                    created_by=row[9],
                    status=row[10],
                    expires_at=row[11],
                    executed_at=row[12],
                    ticket=row[13],
                    notes=row[14],
                    profit_loss=profit_loss,
                    exit_price=exit_price,
                    close_time=close_time,
                    close_reason=close_reason,
                    zone_entry_tracked=bool(zone_entry_tracked) if zone_entry_tracked is not None else False,
                    zone_entry_time=zone_entry_time,
                    zone_exit_time=zone_exit_time,
                    entry_levels=entry_levels,
                    cancellation_reason=cancellation_reason,
                    last_cancellation_check=last_cancellation_check,
                    last_re_evaluation=last_re_evaluation,
                    re_evaluation_count_today=re_evaluation_count_today if re_evaluation_count_today is not None else 0,
                    re_evaluation_count_date=re_evaluation_count_date
                )
                plans.append(plan)
            except Exception as e:
                logger.warning(f"Failed to load plan {row[0] if row else 'unknown'}: {e}", exc_info=True)
                    
        return plans

# Global instance
auto_execution_system = None

def get_auto_execution_system() -> AutoExecutionSystem:
    """Get the global auto execution system instance"""
    global auto_execution_system
    if auto_execution_system is None:
        # Try to get M1 components if available
        m1_data_fetcher = None
        m1_analyzer = None
        session_manager = None
        asset_profiles = None
        
        streamer = None
        news_service = None
        mt5_service = None  # Initialize to None
        
        try:
            from infra.m1_data_fetcher import M1DataFetcher
            from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
            from infra.m1_session_volatility_profile import SessionVolatilityProfile
            from infra.m1_asset_profiles import AssetProfileManager
            from infra.m1_threshold_calibrator import SymbolThresholdManager
            from infra.mt5_service import MT5Service
            
            mt5_service = MT5Service()
            asset_profiles = AssetProfileManager("config/asset_profiles.json")
            session_manager = SessionVolatilityProfile(asset_profiles)
            threshold_manager = SymbolThresholdManager("config/threshold_profiles.json")
            
            m1_data_fetcher = M1DataFetcher(data_source=mt5_service, max_candles=200)
            m1_analyzer = M1MicrostructureAnalyzer(
                mt5_service=mt5_service,
                session_manager=session_manager,
                asset_profiles=asset_profiles,
                threshold_manager=threshold_manager
            )
            
            # Try to get streamer from main_api if available
            try:
                import app.main_api as main_api
                if hasattr(main_api, 'multi_tf_streamer'):
                    streamer = main_api.multi_tf_streamer
            except Exception:
                pass
            
            # Try to get news_service from main_api if available
            try:
                import app.main_api as main_api
                if hasattr(main_api, 'news_service'):
                    news_service = main_api.news_service
            except Exception:
                # Fallback: try to create news service
                try:
                    from infra.news_service import NewsService
                    news_service = NewsService()
                except Exception:
                    pass
        except Exception as e:
            # M1 components not available - log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"M1 components not available in get_auto_execution_system(): {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            # Try to create mt5_service even if M1 components fail
            if mt5_service is None:
                try:
                    from infra.mt5_service import MT5Service
                    mt5_service = MT5Service()
                except Exception:
                    pass
        
        # Phase 2.2: Add order flow plan methods
        # These methods are defined below in the class
        
        auto_execution_system = AutoExecutionSystem(
            mt5_service=mt5_service,  # FIXED: Pass mt5_service so micro-scalp engine can initialize
            m1_analyzer=m1_analyzer,
            m1_data_fetcher=m1_data_fetcher,
            session_manager=session_manager,
            asset_profiles=asset_profiles,
            streamer=streamer,  # NEW: Pass streamer for adaptive micro-scalp
            news_service=news_service  # NEW: Pass news_service for adaptive micro-scalp
        )
    return auto_execution_system

def start_auto_execution_system():
    """Start the auto execution system"""
    system = get_auto_execution_system()
    system.start()

def stop_auto_execution_system():
    """Stop the auto execution system"""
    system = get_auto_execution_system()
    system.stop()
