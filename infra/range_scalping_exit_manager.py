"""
Range Scalping Exit Manager
Separate exit manager for range scalping trades (independent from IntelligentExitManager).

Handles early exits, breakeven management, and range invalidation monitoring.
Fixed 0.01 lot size - no partial profits, exit full position early if conditions deteriorate.
"""

from __future__ import annotations  # Enable postponed evaluation of annotations

import threading
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple, List, Any
from enum import Enum
from dataclasses import dataclass, asdict

import MetaTrader5 as mt5

from infra.range_boundary_detector import RangeStructure

logger = logging.getLogger(__name__)


# 🔴 CRITICAL: Error Handling Configuration
ERROR_HANDLING = {
    "range_detection_fails": {
        "action": "skip_trade",
        "log_level": "warning",
        "notify_user": True,
        "reason": "Insufficient data for range detection",
        "severity": "high"
    },
    "mt5_connection_lost": {
        "action": "retry_connection",
        "max_retries": 3,
        "retry_interval": 5,
        "fallback": "alert_user",
        "continue_monitoring": True,
        "severity": "critical"
    },
    "exit_order_fails": {
        "action": "retry_with_slippage",
        "max_slippage_pct": 0.15,
        "max_retries": 3,
        "retry_interval": 2,
        "fallback": "alert_user_manual_close",
        "severity": "high"
    },
    "data_source_unavailable": {
        "action": "use_last_known_data",
        "max_age_minutes": 15,
        "fallback": "skip_check",
        "log_warning": True,
        "severity": "medium"
    },
    "order_execution_fails": {
        "action": "retry_execution",
        "max_retries": 2,
        "retry_interval": 1,
        "fallback": "skip_trade",
        "notify_user": True,
        "severity": "high"
    },
    "price_validation_fails": {
        "action": "skip_trade",
        "log_level": "info",
        "notify_user": True,
        "reason": "Price moved beyond acceptable slippage",
        "severity": "medium"
    },
    "state_save_failed": {
        "action": "log_error",
        "log_level": "error",
        "notify_user": True,
        "severity": "high"
    },
    "state_load_failed": {
        "action": "log_error",
        "log_level": "error",
        "notify_user": True,
        "severity": "critical"
    },
    "range_invalidation_during_trade": {
        "action": "exit_immediately",
        "log_level": "warning",
        "notify_user": True,
        "severity": "high"
    },
    "monitoring_error": {
        "action": "log_error",
        "log_level": "warning",
        "severity": "medium"
    }
}


class ErrorSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "warning"
    INFO = "info"


@dataclass
class ErrorEvent:
    error_type: str
    severity: ErrorSeverity
    timestamp: datetime
    context: Dict[str, Any]
    message: str


@dataclass
class ExitSignal:
    """Exit signal with priority and reason"""
    priority: str  # "critical", "high", "medium", "low"
    reason: str
    action: str  # "exit_immediately", "exit_if_unprofitable", "exit_at_profit", "move_sl_to_breakeven"
    message: str
    min_profit_r: Optional[float] = None  # Minimum profit in R to execute
    exit_at_profit_r: Optional[float] = None  # Exit at this profit level if specified


class ErrorHandler:
    """Centralized error handling with severity classification"""
    
    def __init__(self, config: Dict):
        self.config = config
        from collections import deque
        self.error_history: deque = deque(maxlen=100)
        self.critical_error_window: deque = deque(maxlen=10)
        self.disabled = False
        self.max_critical_per_hour = config.get("max_critical_errors_per_hour", 3)
    
    def classify_severity(self, error_type: str, context: Dict) -> ErrorSeverity:
        """Classify error by severity (CRITICAL/HIGH/MEDIUM/INFO)"""
        severity_map = {
            "mt5_connection_lost": ErrorSeverity.CRITICAL,
            "state_corruption": ErrorSeverity.CRITICAL,
            "orphaned_trades": ErrorSeverity.CRITICAL,
            "state_load_failed": ErrorSeverity.CRITICAL,
            "exit_order_fails": ErrorSeverity.HIGH,
            "range_invalidation_during_trade": ErrorSeverity.HIGH,
            "state_save_failed": ErrorSeverity.HIGH,
            "range_detection_fails": ErrorSeverity.HIGH,
            "order_execution_fails": ErrorSeverity.HIGH,
            "data_stale_warning": ErrorSeverity.MEDIUM,
            "data_source_unavailable": ErrorSeverity.MEDIUM,
            "monitoring_error": ErrorSeverity.MEDIUM,
            "price_validation_fails": ErrorSeverity.MEDIUM,
            "breakeven_moved": ErrorSeverity.INFO
        }
        return severity_map.get(error_type, ErrorSeverity.MEDIUM)
    
    def handle_error(self, error_type: str, context: Dict) -> Dict[str, Any]:
        """Handle error with severity classification and auto-disable triggers"""
        if self.disabled:
            return {"action_taken": "ignored_disabled", "success": False, "should_continue": False}
        
        severity = self.classify_severity(error_type, context)
        error_event = ErrorEvent(
            error_type=error_type,
            severity=severity,
            timestamp=datetime.now(timezone.utc),
            context=context,
            message=context.get("message", f"Error: {error_type}")
        )
        
        self.error_history.append(error_event)
        if severity == ErrorSeverity.CRITICAL:
            self.critical_error_window.append(error_event)
            self._check_auto_disable()
        
        # Route based on severity (log, alert, etc.)
        config = ERROR_HANDLING.get(error_type, {})
        
        # Log based on severity
        message = context.get("message", f"Error: {error_type}")
        if severity == ErrorSeverity.CRITICAL:
            logger.critical(f"🚨 {message}")
        elif severity == ErrorSeverity.HIGH:
            logger.error(f"❌ {message}")
        elif severity == ErrorSeverity.MEDIUM:
            logger.warning(f"⚠️ {message}")
        else:
            logger.info(f"ℹ️ {message}")
        
        return {
            "action_taken": config.get("action", "log_error"),
            "severity": severity.value,
            "success": False,
            "message": message,
            "should_continue": severity != ErrorSeverity.CRITICAL
        }
    
    def _check_auto_disable(self):
        """Auto-disable if critical error threshold exceeded"""
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)
        critical_in_last_hour = [
            e for e in self.critical_error_window 
            if e.timestamp > one_hour_ago
        ]
        
        if len(critical_in_last_hour) >= self.max_critical_per_hour:
            self.disabled = True
            logger.critical(
                f"🚨 AUTO-DISABLE: {len(critical_in_last_hour)} critical errors in last hour"
            )


class RangeScalpingExitManager:
    """
    SEPARATE exit manager for range scalping trades (independent from IntelligentExitManager).
    
    🔴 CRITICAL IMPLEMENTATION REQUIREMENTS:
    - Thread-safe state mutations (state_lock, save_lock)
    - Persistent state tracking (range_scalp_trades_active.json)
    - Initialization order: Load state BEFORE IntelligentExitManager initializes
    - Error handling with severity classification
    
    Since position size is fixed 0.01, no partial profits.
    Instead, exit full position early if conditions deteriorate.
    
    NOTE: This manager ONLY handles range scalping trades. IntelligentExitManager
    will skip trades tagged with trade_type="range_scalp".
    """
    
    def __init__(self, config: Dict, error_handler: ErrorHandler):
        self.active_trades: Dict[int, Dict] = {}
        self.storage_file = Path("data/range_scalp_trades_active.json")
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)  # Ensure data/ directory exists
        self.last_save_time = None
        self.save_interval = 300  # Save every 5 minutes OR after state change
        self.config = config
        self.error_handler = error_handler
        
        # 🔴 CRITICAL: Thread safety locks
        self.state_lock = threading.Lock()  # Protects active_trades dict
        self.save_lock = threading.Lock()   # Protects JSON file writes
        
        # Load exit config from separate file
        exit_config_file = Path("config/range_scalping_exit_config.json")
        if exit_config_file.exists():
            try:
                with open(exit_config_file, 'r') as f:
                    self.exit_config = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load exit config: {e}, using defaults")
                self.exit_config = {}
        else:
            logger.warning(f"Exit config file not found at {exit_config_file}, using defaults")
            self.exit_config = {}
        
        # Extract exit config sections
        self.early_exit_rules = self.exit_config.get("early_exit_rules", {})
        self.breakeven_config = self.exit_config.get("breakeven_management", {})
        
        # Load state on initialization
        self._load_state()
    
    def register_trade(
        self,
        ticket: int,
        symbol: str,
        strategy: str,
        range_data: RangeStructure,
        entry_price: float,
        sl: float,
        tp: float,
        entry_time: datetime
    ):
        """
        🔴 CRITICAL: Register new range scalp trade for monitoring (THREAD SAFE).
        
        MUST be called immediately after trade execution to enable monitoring.
        """
        logger.info(f"Registering trade {ticket}: starting registration...")
        # Serialize range_data first (outside lock to minimize lock time)
        try:
            range_dict = range_data.to_dict()  # Serialize using to_dict()
            logger.info(f"Registering trade {ticket}: range_data serialized ({len(range_dict)} keys)")
        except Exception as e:
            logger.error(f"Failed to serialize range_data for trade {ticket}: {e}", exc_info=True)
            raise
        
        # Store trade data (with lock)
        logger.info(f"Registering trade {ticket}: acquiring state_lock...")
        with self.state_lock:
            logger.info(f"Registering trade {ticket}: state_lock acquired, storing trade data...")
            self.active_trades[ticket] = {
                "ticket": ticket,
                "symbol": symbol,
                "strategy": strategy,
                "range_data": range_dict,
                "entry_price": entry_price,
                "sl": sl,
                "tp": tp,
                "entry_time": entry_time.isoformat(),
                "exit_manager_state": "active",
                "breakeven_moved": False,
                "last_range_check": entry_time.isoformat(),
                "last_state_change": entry_time.isoformat()
            }
            logger.info(f"Registering trade {ticket}: trade data stored in memory")
        
        # Call _save_state AFTER releasing state_lock (prevents deadlock)
        logger.info(f"Registering trade {ticket}: state_lock released, calling _save_state...")
        self._save_state(force=True)  # Save immediately
        logger.info(f"Registering trade {ticket}: _save_state completed")
        
        logger.info(
            f"✅ Registered range scalp trade {ticket} ({symbol}, {strategy}) "
            f"entry={entry_price}, sl={sl}, tp={tp}"
        )
    
    def update_trade_state(self, ticket: int, state_updates: Dict):
        """Update trade state - THREAD SAFE"""
        with self.state_lock:
            if ticket not in self.active_trades:
                logger.warning(f"Attempted to update non-existent trade {ticket}")
                return
            
            self.active_trades[ticket].update(state_updates)
            self.active_trades[ticket]["last_state_change"] = datetime.now(timezone.utc).isoformat()
            self._save_state(force=True)
    
    def unregister_trade(self, ticket: int):
        """Remove trade from monitoring - THREAD SAFE"""
        with self.state_lock:
            if ticket in self.active_trades:
                symbol = self.active_trades[ticket].get("symbol", "unknown")
                del self.active_trades[ticket]
                self._save_state(force=True)
                logger.info(f"Unregistered range scalp trade {ticket} ({symbol})")
    
    def get_active_trades_copy(self) -> Dict[int, Dict]:
        """Get a copy of active trades (thread-safe)"""
        with self.state_lock:
            return dict(self.active_trades)
    
    def _save_state(self, force: bool = False):
        """
        🔴 CRITICAL: Save state to disk (THREAD SAFE).
        
        Saves if:
        - force=True (immediate save after state change)
        - OR >5 minutes since last save (periodic backup)
        """
        # Quick check without lock
        if not force:
            now = datetime.now(timezone.utc)
            if self.last_save_time and (now - self.last_save_time).total_seconds() < self.save_interval:
                return
        
        # Serialize state (with lock, but minimize lock time)
        with self.state_lock:
            state_copy = dict(self.active_trades)  # Copy to minimize lock time
            current_count = len(state_copy)
        
        # Write to disk (separate lock for file I/O)
        logger.info(f"_save_state: acquiring save_lock for {self.storage_file}...")
        with self.save_lock:
            logger.info(f"_save_state: save_lock acquired, preparing state data...")
            try:
                state_data = {
                    "version": "1.0",
                    "last_saved": datetime.now(timezone.utc).isoformat(),
                    "trades": state_copy
                }
                
                # Atomic write (temp file → rename to prevent corruption)
                temp_file = self.storage_file.with_suffix('.tmp')
                logger.info(f"_save_state: writing to temp file {temp_file}...")
                with open(temp_file, 'w') as f:
                    json.dump(state_data, f, indent=2, default=str)
                logger.info(f"_save_state: temp file written, renaming to {self.storage_file}...")
                temp_file.replace(self.storage_file)  # Atomic rename
                logger.info(f"_save_state: atomic rename completed")
                
                self.last_save_time = datetime.now(timezone.utc)
                logger.info(f"_save_state: Saved {current_count} active range scalp trades to {self.storage_file}")
                
            except Exception as e:
                self.error_handler.handle_error("state_save_failed", {
                    "message": f"Failed to save trade state: {e}",
                    "error": str(e)
                })
                logger.error(f"Failed to save trade state: {e}", exc_info=True)
    
    def _load_state(self):
        """
        🔴 CRITICAL: Load active trades on startup.
        
        MUST be called BEFORE IntelligentExitManager initializes.
        Cross-checks with open MT5 positions to ensure consistency.
        """
        if not self.storage_file.exists():
            logger.info(f"No existing state file found at {self.storage_file}")
            return
        
        try:
            with open(self.storage_file, 'r') as f:
                state = json.load(f)
            
            loaded_count = 0
            removed_count = 0
            
            # Get all open positions from MT5
            try:
                mt5_positions = mt5.positions_get()
                mt5_tickets = {pos.ticket for pos in mt5_positions} if mt5_positions else set()
            except Exception as e:
                logger.warning(f"Failed to get MT5 positions during state load: {e}")
                mt5_tickets = set()
            
            # Verify each trade still exists in MT5
            with self.state_lock:
                for ticket_str, trade_data in state.get("trades", {}).items():
                    ticket = int(ticket_str)
                    
                    if ticket in mt5_tickets:
                        # Trade exists in MT5, restore to monitoring
                        self.active_trades[ticket] = trade_data
                        loaded_count += 1
                        logger.info(
                            f"✅ Restored range scalp trade {ticket} "
                            f"({trade_data.get('symbol', 'unknown')}) to monitoring"
                        )
                    else:
                        # Trade no longer exists in MT5 (closed externally or error)
                        removed_count += 1
                        logger.warning(
                            f"⚠️ Trade {ticket} in state file but not in MT5 - "
                            f"removing from monitoring"
                        )
            
            if loaded_count > 0:
                logger.info(f"Recovered {loaded_count} active range scalp trades on startup")
            if removed_count > 0:
                logger.warning(f"Removed {removed_count} stale trades from state file")
                self._save_state(force=True)  # Save cleaned state
            
            last_saved_str = state.get("last_saved")
            if last_saved_str:
                try:
                    self.last_save_time = datetime.fromisoformat(last_saved_str.replace('Z', '+00:00'))
                except:
                    self.last_save_time = datetime.now(timezone.utc)
            else:
                self.last_save_time = datetime.now(timezone.utc)
            
        except Exception as e:
            self.error_handler.handle_error("state_load_failed", {
                "message": f"Failed to load trade state: {e}",
                "error": str(e),
                "severity": "critical"
            })
            logger.error(f"Failed to load trade state: {e}", exc_info=True)
    
    def get_active_ticket_list(self) -> List[int]:
        """Get list of active tickets (for IntelligentExitManager skip list)"""
        with self.state_lock:
            return list(self.active_trades.keys())
    
    def check_early_exit_conditions(
        self,
        trade: Dict,
        current_price: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        time_in_trade: float,  # minutes
        range_data: RangeStructure,
        market_data: Dict
    ) -> Optional[ExitSignal]:
        """
        Check if trade should exit early due to deteriorating conditions.
        
        Priority-based exit triggers (process in descending priority order):
        
        PRIORITY: CRITICAL (immediate exit)
        1. Range Invalidation Detected (M15 BOS confirmed)
           - Exit immediately, regardless of profit
        
        PRIORITY: HIGH (exit unless profit > 0.8R)
        2. Range Invalidation (2 candles closed outside range)
        3. Range Invalidation (VWAP momentum > threshold % of ATR per bar)
        
        PRIORITY: MEDIUM (exit if profit < 0.3R)
        4. Range Invalidation (BB width expanded > 50%)
        
        PRIORITY: HIGH (best effort SL move)
        5. Quick Move to +0.5R (Risk Off)
           - Attempt to move SL to breakeven (best effort - log warning if fails)
           - If price retraces to breakeven → exit (quick profit secured)
        
        PRIORITY: MEDIUM
        6. Slow Grind After 1 Hour
           - Trade open > 60 minutes
           - Price hasn't reached TP
           - Price hasn't moved > 0.3R from entry
           → Exit early (stagnation = energy loss)
        
        PRIORITY: LOW (exit at current profit)
        7. Strong Divergence Detected
           - Order flow diverging against position
           - CVD showing hidden distribution
           - Tape pressure shifting
           → Exit at current profit (preserve gain, min 0.1R profit required)
        
        8. Opposite Order Flow
           - Buyers fading when in long position
           - Sellers fading when in short position
           → Close at ~0.6R if profitable, exit if losing
        
        Returns: ExitSignal with priority, or None
        """
        # Calculate profit in R
        direction = "BUY" if entry_price < current_price else "SELL"
        if direction == "BUY":
            profit_pips = current_price - entry_price
            risk_pips = entry_price - stop_loss
        else:
            profit_pips = entry_price - current_price
            risk_pips = stop_loss - entry_price
        
        profit_r = profit_pips / risk_pips if risk_pips > 0 else 0
        
        # PRIORITY: CRITICAL - M15 BOS confirmed
        on_range_invalidation = self.early_exit_rules.get("on_range_invalidation", {})
        if on_range_invalidation.get("enabled", True):
            if market_data.get("m15_bos_confirmed", False):
                return ExitSignal(
                    priority="critical",
                    reason="m15_bos_confirmed",
                    action="exit_immediately",
                    message="M15 BOS confirmed - range invalidated, exit immediately"
                )
        
        # PRIORITY: HIGH - Range invalidation (2 candles outside)
        if market_data.get("range_invalidated", False):
            invalidation_signals = market_data.get("invalidation_signals", [])
            if "2_candles_outside_range" in invalidation_signals:
                # Exit unless profit > 0.8R
                if profit_r < 0.8:
                    return ExitSignal(
                        priority="high",
                        reason="2_candles_outside_range",
                        action="exit_immediately",
                        message="2 candles closed outside range - exit unless profit > 0.8R"
                    )
            
            # VWAP momentum high
            if "vwap_momentum_high" in invalidation_signals:
                if profit_r < 0.8:
                    return ExitSignal(
                        priority="high",
                        reason="vwap_momentum_high",
                        action="exit_immediately",
                        message="VWAP momentum high - exit unless profit > 0.8R"
                    )
        
        # PRIORITY: MEDIUM - BB width expansion
        if market_data.get("range_invalidated", False):
            invalidation_signals = market_data.get("invalidation_signals", [])
            if "bb_width_expansion" in invalidation_signals:
                # Exit if profit < 0.3R
                if profit_r < 0.3:
                    return ExitSignal(
                        priority="medium",
                        reason="bb_width_expansion",
                        action="exit_immediately",
                        message="BB width expanded >50% - exit if profit < 0.3R"
                    )
        
        # PRIORITY: HIGH - Quick move to +0.5R
        quick_move_rule = self.early_exit_rules.get("quick_move_to_05r", {})
        if quick_move_rule.get("enabled", True):
            profit_threshold_r = quick_move_rule.get("profit_threshold_r", 0.5)
            time_threshold_minutes = quick_move_rule.get("time_threshold_minutes", 30)
            
            if profit_r >= profit_threshold_r and time_in_trade <= time_threshold_minutes:
                # Try to move SL to breakeven
                be_sl = self.calculate_breakeven_stop(
                    entry_price, direction, current_price,
                    market_data.get("effective_atr", 0), trade.get("symbol", "")
                )
                
                if be_sl:
                    return ExitSignal(
                        priority="high",
                        reason="quick_move_to_05r",
                        action="move_sl_to_breakeven",
                        message=f"Quick move to +{profit_threshold_r}R - move SL to breakeven",
                        min_profit_r=profit_threshold_r
                    )
                
                # If breakeven move fails, check if price retraces
                if quick_move_rule.get("exit_if_retrace_to_be", True):
                    # Check if price retraced to entry (or breakeven)
                    if direction == "BUY" and current_price <= entry_price:
                        return ExitSignal(
                            priority="high",
                            reason="breakeven_retrace",
                            action="exit_immediately",
                            message="Price retraced to breakeven after quick move"
                        )
                    elif direction == "SELL" and current_price >= entry_price:
                        return ExitSignal(
                            priority="high",
                            reason="breakeven_retrace",
                            action="exit_immediately",
                            message="Price retraced to breakeven after quick move"
                        )
        
        # PRIORITY: MEDIUM - Stagnation after 1 hour
        stagnant_rule = self.early_exit_rules.get("stagnant_after_1h", {})
        if stagnant_rule.get("enabled", True):
            time_threshold = stagnant_rule.get("time_threshold_minutes", 60)
            min_profit_requirement = stagnant_rule.get("min_profit_requirement_r", 0.3)
            
            if time_in_trade >= time_threshold:
                # Check if price moved significantly
                if abs(profit_r) < min_profit_requirement:
                    # Check if TP reached
                    tp_reached = False
                    if direction == "BUY" and current_price >= take_profit:
                        tp_reached = True
                    elif direction == "SELL" and current_price <= take_profit:
                        tp_reached = True
                    
                    if not tp_reached:
                        return ExitSignal(
                            priority="medium",
                            reason="stagnation_energy_loss",
                            action="exit_early",
                            message=f"Trade stagnant after {time_threshold} min - exit early (energy loss)"
                        )
        
        # PRIORITY: LOW - Strong divergence
        divergence_rule = self.early_exit_rules.get("strong_divergence", {})
        if divergence_rule.get("enabled", True):
            cvd_divergence = market_data.get("cvd_divergence_strength", 0)
            threshold = divergence_rule.get("cvd_divergence_threshold", 0.7)
            min_profit = divergence_rule.get("min_profit_to_exit_r", 0.1)
            
            if cvd_divergence >= threshold and profit_r >= min_profit:
                return ExitSignal(
                    priority="low",
                    reason="strong_divergence",
                    action="exit_at_current_profit",
                    message="Strong divergence detected - exit at current profit",
                    min_profit_r=min_profit
                )
        
        # PRIORITY: LOW - Opposite order flow
        opposite_flow_rule = self.early_exit_rules.get("opposite_order_flow", {})
        if opposite_flow_rule.get("enabled", True):
            tape_pressure_shift = market_data.get("tape_pressure_shift", 0)
            threshold = opposite_flow_rule.get("tape_pressure_shift_threshold", 0.6)
            exit_at_profit_r = opposite_flow_rule.get("exit_at_profit_r", 0.6)
            exit_if_losing = opposite_flow_rule.get("exit_if_losing", True)
            
            # Check if order flow shifted against position
            if direction == "BUY" and tape_pressure_shift <= -threshold:
                # Bearish pressure
                if profit_r >= exit_at_profit_r:
                    return ExitSignal(
                        priority="low",
                        reason="opposite_order_flow",
                        action="exit_early",
                        message=f"Opposite order flow detected - exit at {exit_at_profit_r}R if profitable",
                        exit_at_profit_r=exit_at_profit_r
                    )
                elif exit_if_losing and profit_r < 0:
                    return ExitSignal(
                        priority="low",
                        reason="opposite_order_flow",
                        action="exit_early",
                        message="Opposite order flow detected - exit if losing"
                    )
            elif direction == "SELL" and tape_pressure_shift >= threshold:
                # Bullish pressure
                if profit_r >= exit_at_profit_r:
                    return ExitSignal(
                        priority="low",
                        reason="opposite_order_flow",
                        action="exit_early",
                        message=f"Opposite order flow detected - exit at {exit_at_profit_r}R if profitable",
                        exit_at_profit_r=exit_at_profit_r
                    )
                elif exit_if_losing and profit_r < 0:
                    return ExitSignal(
                        priority="low",
                        reason="opposite_order_flow",
                        action="exit_early",
                        message="Opposite order flow detected - exit if losing"
                    )
        
        return None  # No exit signal
    
    def calculate_breakeven_stop(
        self,
        entry_price: float,
        direction: str,
        current_price: float,
        effective_atr: float,
        symbol: str
    ) -> Optional[float]:
        """
        Calculate breakeven stop loss (entry ± small buffer).
        Buffer = 0.1 × Effective ATR to avoid noise.
        
        Returns: Breakeven SL price, or None if:
        - MT5 rejects modification (too close to price)
        - Minimum distance not met
        
        (Best effort - logs warning if cannot set)
        """
        if not self.breakeven_config.get("enabled", True):
            return None
        
        buffer_atr_mult = self.breakeven_config.get("buffer_atr_multiplier", 0.1)
        buffer = effective_atr * buffer_atr_mult if effective_atr > 0 else entry_price * 0.0001  # Fallback 0.01%
        
        if direction == "BUY":
            breakeven_sl = entry_price + buffer
            # Must be below current price
            if breakeven_sl >= current_price:
                return None
        else:  # SELL
            breakeven_sl = entry_price - buffer
            # Must be above current price
            if breakeven_sl <= current_price:
                return None
        
        # Check minimum distance from current price (MT5 requirement)
        # Typical MT5 minimum stop distance is ~10-20 points for most pairs
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info:
                min_stop_distance = symbol_info.trade_stops_level * symbol_info.point
                current_distance = abs(current_price - breakeven_sl)
                
                if current_distance < min_stop_distance:
                    logger.warning(
                        f"Breakeven SL {breakeven_sl} too close to current price "
                        f"{current_price} (min distance: {min_stop_distance})"
                    )
                    return None
        except Exception as e:
            logger.debug(f"Could not check MT5 stop distance for {symbol}: {e}")
            # Continue anyway - let MT5 reject if needed
        
        return breakeven_sl
    
    def check_reentry_allowed(
        self,
        exit_reason: str,
        minutes_since_exit: int,
        cooldown_minutes: int = 15
    ) -> bool:
        """
        Check if re-entry is allowed after early exit.
        
        Re-entry allowed for:
        - "stagnation_energy_loss" → Allow if range still valid
        - "breakeven_retrace" → Allow if range still valid
        
        Re-entry blocked for:
        - "range_invalidation" → Block until new range forms
        - "opposite_order_flow" → Respect cooldown
        - All other reasons → Respect cooldown
        
        Returns: True if re-entry allowed
        """
        reentry_config = self.config.get("reentry_logic", {})
        if not reentry_config.get("enabled", True):
            return False
        
        allowed_reasons = reentry_config.get("allowed_exit_reasons", [])
        blocked_reasons = reentry_config.get("blocked_exit_reasons", [])
        cooldown = reentry_config.get("cooldown_minutes", cooldown_minutes)
        
        if exit_reason in blocked_reasons:
            return False
        
        if exit_reason in allowed_reasons:
            # Still need to check if range is valid (caller should verify)
            return True
        
        # Default: respect cooldown
        return minutes_since_exit >= cooldown
    
    def check_range_invalidation_during_trade(
        self,
        range_data: RangeStructure,
        recent_candles: List[Dict[str, Any]],
        current_price: float
    ) -> Tuple[bool, List[str]]:
        """
        Continuously check if range is invalidated during open trade.
        If invalidated → immediate exit signal.
        
        Uses RangeBoundaryDetector.check_range_invalidation() method.
        """
        try:
            from infra.range_boundary_detector import RangeBoundaryDetector
            
            range_detector = RangeBoundaryDetector(self.config.get("range_detection", {}))
            
            # Get market data for invalidation check
            market_data = {}
            
            # Check VWAP slope if available
            if recent_candles and len(recent_candles) >= 5:
                # Calculate VWAP momentum
                from infra.range_scalping_risk_filters import RangeScalpingRiskFilters
                risk_filters = RangeScalpingRiskFilters(self.config)
                
                # Get VWAP values from candles
                typical_prices = [
                    (c['high'] + c['low'] + c['close']) / 3 
                    for c in recent_candles[-10:]
                ]
                volumes = [c.get('volume', c.get('tick_volume', 1)) for c in recent_candles[-10:]]
                
                cumulative_pv = 0
                cumulative_v = 0
                vwap_values = []
                for tp, vol in zip(typical_prices, volumes):
                    cumulative_pv += tp * vol
                    cumulative_v += vol
                    if cumulative_v > 0:
                        vwap_values.append(cumulative_pv / cumulative_v)
                
                if len(vwap_values) >= 5 and range_data.range_width_atr > 0:
                    vwap_slope_pct = risk_filters.calculate_vwap_momentum(
                        vwap_values[-5:],
                        range_data.range_width_atr,
                        range_data.range_mid,
                        bars=5
                    )
                    market_data["vwap_slope_pct_atr"] = vwap_slope_pct
            
            # Check BB width expansion if available
            # (Would need BB calculation - simplified for now)
            
            # Check for M15 BOS (would need structure data)
            # (Simplified - caller should provide this)
            
            # Call range detector
            is_invalidated, invalidation_signals = range_detector.check_range_invalidation(
                range_data=range_data,
                current_price=current_price,
                candles=recent_candles,
                vwap_slope_pct_atr=market_data.get("vwap_slope_pct_atr"),
                bb_width_expansion=None,  # Would need calculation
                candles_df_m15=None,  # Would need M15 candles
                atr_m15=None
            )
            
            return is_invalidated, invalidation_signals
            
        except Exception as e:
            logger.error(f"Error checking range invalidation during trade: {e}", exc_info=True)
            self.error_handler.handle_error("range_invalidation_during_trade", {
                "message": f"Error checking range invalidation: {e}",
                "error": str(e)
            })
            return False, []
    
    def execute_exit(self, ticket: int, exit_signal: ExitSignal) -> bool:
        """
        Execute exit order based on exit signal.
        
        Returns: True if exit successful, False otherwise
        """
        with self.state_lock:
            if ticket not in self.active_trades:
                logger.warning(f"Attempted to exit non-existent trade {ticket}")
                return False
            
            trade = self.active_trades[ticket]
        
        symbol = trade.get("symbol", "")
        
        try:
            # Get position from MT5
            position = mt5.positions_get(ticket=ticket)
            if not position:
                logger.warning(f"Position {ticket} not found in MT5")
                self.unregister_trade(ticket)
                return False
            
            position = position[0]
            
            if exit_signal.action == "exit_immediately":
                # Close position
                result = mt5.order_send({
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": position.volume,
                    "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                    "position": ticket,
                    "deviation": 20,
                    "magic": 0,
                    "comment": f"Range scalp exit: {exit_signal.reason}",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC
                })
                
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"✅ Exited range scalp trade {ticket}: {exit_signal.message}")
                    self.unregister_trade(ticket)
                    return True
                else:
                    error_msg = mt5.last_error()
                    logger.error(f"❌ Failed to exit trade {ticket}: {error_msg}")
                    self.error_handler.handle_error("exit_order_fails", {
                        "ticket": ticket,
                        "message": f"Exit order failed: {error_msg}",
                        "retcode": result.retcode if result else None
                    })
                    return False
            
            elif exit_signal.action == "move_sl_to_breakeven":
                # Move stop loss to breakeven
                # Get effective ATR from trade data or calculate
                effective_atr = trade.get("effective_atr", 0)
                if effective_atr == 0:
                    # Fallback: use range_width_atr from range_data
                    range_data_dict = trade.get("range_data", {})
                    effective_atr = range_data_dict.get("range_width_atr", 0)
                
                be_sl = self.calculate_breakeven_stop(
                    trade["entry_price"],
                    "BUY" if position.type == mt5.ORDER_TYPE_BUY else "SELL",
                    position.price_current,
                    effective_atr,
                    symbol
                )
                
                if be_sl:
                    result = mt5.order_send({
                        "action": mt5.TRADE_ACTION_SLTP,
                        "symbol": symbol,
                        "position": ticket,
                        "sl": be_sl,
                        "tp": position.tp,
                        "deviation": 20,
                        "magic": 0,
                        "type_time": mt5.ORDER_TIME_GTC
                    })
                    
                    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                        logger.info(f"✅ Moved SL to breakeven for trade {ticket}")
                        self.update_trade_state(ticket, {"breakeven_moved": True})
                        return True
                    else:
                        error_msg = mt5.last_error()
                        logger.warning(f"⚠️ Failed to move SL to breakeven for {ticket}: {error_msg}")
                        # Best effort - continue monitoring
                        return False
                else:
                    logger.warning(f"⚠️ Could not calculate breakeven SL for {ticket}")
                    return False
            
            else:
                logger.warning(f"Unknown exit action: {exit_signal.action}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing exit for trade {ticket}: {e}", exc_info=True)
            self.error_handler.handle_error("exit_order_fails", {
                "ticket": ticket,
                "message": f"Error executing exit: {e}",
                "error": str(e)
            })
            return False

