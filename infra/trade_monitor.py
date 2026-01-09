"""
Trade Monitor - Phase 4.4 Integration
Background job to manage trailing stops for open positions
"""

import logging
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TradeMonitor:
    """
    Monitor open positions and manage trailing stops.
    
    This class is responsible for:
    - Checking open positions periodically
    - Detecting momentum state for each position
    - Calculating and applying trailing stops
    - Logging all actions for analytics
    """
    
    def __init__(self, mt5_service, feature_builder, indicator_bridge=None, journal_repo=None):
        """
        Initialize trade monitor.
        
        Args:
            mt5_service: MT5Service instance for position management
            feature_builder: FeatureBuilder instance for momentum detection
            indicator_bridge: Optional IndicatorBridge for fallback ATR calculation
            journal_repo: Optional JournalRepo for logging actions
        """
        self.mt5 = mt5_service
        self.feature_builder = feature_builder
        self.bridge = indicator_bridge  # For fallback ATR calculation
        self.journal = journal_repo
        
        # Track SL updates to avoid thrashing
        self.last_update = {}  # ticket -> last_update_time
        self._update_lock = threading.Lock()  # Thread safety for last_update dictionary
        self.min_update_interval = 30  # Minimum seconds between SL updates for same position
        
        logger.info("TradeMonitor initialized")
    
    def check_trailing_stops(self) -> List[Dict[str, Any]]:
        """
        Check all open positions and update trailing stops if needed.
        
        Returns:
            List of actions taken (for logging/analytics)
        """
        actions = []
        
        try:
            # Import here to avoid circular dependency
            from infra.trailing_stops import calculate_trailing_stop
            from infra.momentum_detector import detect_momentum
            from config import settings
            
            # Check if trailing stops are enabled
            if not settings.USE_TRAILING_STOPS:
                return actions
            
            # Get all open positions from MT5
            if not self.mt5.connect():
                logger.warning("MT5 not connected, skipping trailing stop check")
                return actions
            
            positions = self.mt5.get_positions()
            if not positions:
                return actions
            
            logger.debug(f"Checking {len(positions)} positions for trailing stops")
            
            for position in positions:
                try:
                    ticket = position.ticket
                    symbol = position.symbol
                    entry_price = position.price_open
                    current_sl = position.sl if position.sl else 0.0
                    direction = "buy" if position.type == 0 else "sell"  # 0=BUY, 1=SELL in MT5
                    
                    # Get current price
                    current_price = position.price_current
                    if not current_price or current_price == 0:
                        logger.warning(f"No current price for {symbol} ticket={ticket}")
                        continue
                    
                    # Check if we updated this position recently (thread-safe)
                    with self._update_lock:
                        last_update_time = self.last_update.get(ticket, 0)
                        if (datetime.now().timestamp() - last_update_time) < self.min_update_interval:
                            continue  # Too soon to update again
                    
                    # Check if trade is managed by Universal SL/TP Manager (skip to avoid conflicts)
                    try:
                        from infra.trade_registry import get_trade_state
                        trade_state = get_trade_state(ticket)
                        if trade_state and trade_state.managed_by == "universal_sl_tp_manager":
                            logger.debug(f"Trade {ticket} managed by Universal SL/TP Manager, skipping TradeMonitor")
                            continue
                    except Exception as e:
                        logger.debug(f"Could not check trade registry for trade {ticket}: {e}")
                        # Continue with TradeMonitor if check fails
                    
                    # Get ATR directly from MT5 for trailing stop calculation
                    try:
                        # First try feature builder
                        features = self.feature_builder.build(symbol, ["M5"])
                        m5_features = features.get("M5", {})
                        atr = m5_features.get("atr_14", 0)
                        
                        # If feature builder failed, calculate ATR directly from MT5
                        if atr == 0 or atr is None:
                            # Get M5 bars from MT5 directly
                            bars = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 50)
                            if bars is not None and len(bars) >= 14:
                                # Calculate ATR manually
                                high_low = bars['high'][1:] - bars['low'][1:]
                                high_close = np.abs(bars['high'][1:] - bars['close'][:-1])
                                low_close = np.abs(bars['low'][1:] - bars['close'][:-1])
                                tr = np.maximum(high_low, np.maximum(high_close, low_close))
                                atr = np.mean(tr[-14:]) if len(tr) >= 14 else 0
                                if atr > 0:
                                    logger.debug(f"Calculated MT5 direct ATR for {symbol}: {atr:.2f}")
                        
                        if atr == 0 or atr is None or (isinstance(atr, float) and pd.isna(atr)):
                            logger.warning(f"No valid ATR for {symbol}, skipping trailing stop")
                            continue
                            
                    except Exception as e:
                        logger.warning(f"ATR calculation failed for {symbol}: {e}")
                        continue
                    
                    # Detect momentum
                    momentum_analysis = detect_momentum(m5_features)
                    momentum_state = momentum_analysis.state
                    momentum_score = momentum_analysis.score
                    momentum_rationale = momentum_analysis.rationale
                    
                    # If no initial SL, use a fallback (shouldn't happen in normal operation)
                    if current_sl == 0:
                        if direction == "buy":
                            initial_sl = entry_price - (1.5 * atr)
                        else:
                            initial_sl = entry_price + (1.5 * atr)
                        logger.warning(f"Position {ticket} has no SL, using fallback: {initial_sl:.5f}")
                    else:
                        initial_sl = current_sl
                    
                    # Calculate new trailing SL
                    result = calculate_trailing_stop(
                        entry=entry_price,
                        current_sl=initial_sl,
                        current_price=current_price,
                        direction=direction,
                        atr=atr,
                        features=m5_features,
                        structure=None  # Could pass structure features if available
                    )
                    
                    # If SL should be updated
                    if result.trailed:
                        # Ensure we're actually improving the SL
                        if direction == "buy" and result.new_sl <= current_sl:
                            logger.debug(f"Trailing SL for {symbol} would move backwards (buy), skipping")
                            continue
                        if direction == "sell" and result.new_sl >= current_sl:
                            logger.debug(f"Trailing SL for {symbol} would move backwards (sell), skipping")
                            continue
                        
                        # Update MT5 position
                        success = self._modify_position_sl(
                            ticket=ticket,
                            new_sl=result.new_sl,
                            current_tp=position.tp
                        )
                        
                        if success:
                            # Record action
                            action = {
                                "timestamp": datetime.now().isoformat(),
                                "ticket": ticket,
                                "symbol": symbol,
                                "action": result.trail_method,
                                "old_sl": current_sl,
                                "new_sl": result.new_sl,
                                "current_price": current_price,
                                "profit_r": result.unrealized_r,
                                "momentum": result.momentum_state,
                                "momentum_score": momentum_score,
                                "rationale": result.rationale
                            }
                            actions.append(action)
                            
                            # Update last update time (thread-safe)
                            with self._update_lock:
                                self.last_update[ticket] = datetime.now().timestamp()
                            
                            logger.info(
                                f"Trailing stop updated: {symbol} ticket={ticket}, "
                                f"{result.action}, SL {current_sl:.5f} → {result.new_sl:.5f} "
                                f"(profit={result.profit_r:.2f}R, momentum={momentum_state})"
                            )
                            
                            # Log to journal if available
                            if self.journal:
                                try:
                                    self.journal.add_event({
                                        "event_type": "trailing_stop_update",
                                        "ticket": ticket,
                                        "symbol": symbol,
                                        "action": result.action,
                                        "old_sl": current_sl,
                                        "new_sl": result.new_sl,
                                        "profit_r": result.profit_r,
                                        "momentum": momentum_state,
                                        "rationale": result.rationale
                                    })
                                except Exception as e:
                                    logger.warning(f"Failed to log trailing stop to journal: {e}")
                        else:
                            logger.error(f"Failed to update trailing stop for {symbol} ticket={ticket}")
                
                except Exception as e:
                    logger.error(f"Error checking position {position.ticket if hasattr(position, 'ticket') else 'unknown'}: {e}")
                    continue
            
            return actions
        
        except Exception as e:
            logger.error(f"Trade monitor check failed: {e}")
            return actions
    
    def _modify_position_sl(self, ticket: int, new_sl: float, current_tp: float) -> bool:
        """
        Modify position SL in MT5.
        
        Args:
            ticket: Position ticket number
            new_sl: New stop loss level
            current_tp: Current take profit (keep unchanged)
            
        Returns:
            True if modification was successful
        """
        try:
            # Verify position still exists before modifying (handles closed positions)
            import MetaTrader5 as mt5
            verify_pos = mt5.positions_get(ticket=ticket)
            if not verify_pos or len(verify_pos) == 0:
                logger.debug(f"Position {ticket} was closed, cannot modify SL")
                # Clean up tracking
                with self._update_lock:
                    self.last_update.pop(ticket, None)
                return False
            
            # Use MT5Service's modify method if available
            if hasattr(self.mt5, 'modify_position'):
                return self.mt5.modify_position(
                    ticket=ticket,
                    new_sl=new_sl,
                    new_tp=current_tp
                )
            else:
                # Fallback: use direct MT5 modification
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": ticket,
                    "sl": new_sl,
                    "tp": current_tp
                }
                
                result = mt5.order_send(request)
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    return True
                else:
                    error_msg = result.comment if result else "No result"
                    logger.error(f"MT5 modification failed: {error_msg}")
                    return False
                    
        except Exception as e:
            logger.error(f"Position modification error: {e}")
            return False
    
    def get_position_summary(self) -> Dict[str, Any]:
        """
        Get summary of all open positions with trailing status.
        
        Returns:
            Dictionary with position summary and trailing stats
        """
        try:
            if not self.mt5.connect():
                return {"error": "MT5 not connected"}
            
            positions = self.mt5.get_positions()
            if not positions:
                return {"open_positions": 0, "positions": []}
            
            summary = {
                "open_positions": len(positions),
                "positions": []
            }
            
            for position in positions:
                try:
                    entry = position.price_open
                    current = position.price_current
                    sl = position.sl if position.sl else 0
                    direction = "buy" if position.type == 0 else "sell"
                    
                    # Calculate profit in R
                    if sl != 0:
                        risk = abs(entry - sl)
                        if risk > 0:
                            profit = current - entry if direction == "buy" else entry - current
                            profit_r = profit / risk
                        else:
                            profit_r = 0
                    else:
                        profit_r = 0
                    
                    # Check if trailing is active
                    last_update = self.last_update.get(position.ticket, 0)
                    trailing_active = last_update > 0
                    
                    pos_info = {
                        "ticket": position.ticket,
                        "symbol": position.symbol,
                        "direction": direction,
                        "entry": entry,
                        "current_price": current,
                        "sl": sl,
                        "profit_r": profit_r,
                        "trailing_active": trailing_active,
                        "last_update": datetime.fromtimestamp(last_update).isoformat() if last_update > 0 else None
                    }
                    
                    summary["positions"].append(pos_info)
                    
                except Exception as e:
                    logger.warning(f"Error summarizing position: {e}")
                    continue
            
            return summary
            
        except Exception as e:
            logger.error(f"Position summary failed: {e}")
            return {"error": str(e)}

