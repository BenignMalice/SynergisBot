"""
Exit Monitor - Live Trade Exit Management
Integrates ExitSignalDetector with TradeMonitor for automated profit protection.

Monitors open positions and:
1. Detects exit signals using ExitSignalDetector
2. Sends Telegram alerts when exit conditions are met
3. Optionally auto-executes partial exits or full exits
4. Logs all exit signals to database for analysis
"""

import logging
import threading
import MetaTrader5 as mt5
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from infra.exit_signal_detector import (
    ExitSignalDetector,
    ExitAnalysis,
    ExitPhase,
    ExitUrgency
)
from infra.mt5_service import sanitize_mt5_comment

logger = logging.getLogger(__name__)


class ExitMonitor:
    """
    Monitors open positions for exit signals and manages profit protection.
    
    This class works alongside TradeMonitor to detect when profitable
    trades should be exited to protect profits before reversals.
    """
    
    def __init__(
        self,
        mt5_service,
        feature_builder,
        journal_repo=None,
        auto_exit_enabled: bool = False,  # Safety: manual by default
        min_profit_r: float = 0.5,  # Only monitor positions with >= 0.5R profit
        alert_cooldown_minutes: int = 15  # Min time between alerts for same position
    ):
        """
        Initialize exit monitor.
        
        Args:
            mt5_service: MT5Service instance
            feature_builder: FeatureBuilder instance for market data
            journal_repo: Optional JournalRepo for logging
            auto_exit_enabled: Whether to auto-execute exits (False = alerts only)
            min_profit_r: Minimum profit (in R) before monitoring for exits
            alert_cooldown_minutes: Minimum minutes between alerts for same position
        """
        self.mt5 = mt5_service
        self.feature_builder = feature_builder
        self.journal = journal_repo
        self.auto_exit_enabled = auto_exit_enabled
        self.min_profit_r = min_profit_r
        self.alert_cooldown_minutes = alert_cooldown_minutes
        
        self.detector = ExitSignalDetector()
        
        # Track last alert time per position (thread-safe)
        self.last_alert = {}  # ticket -> timestamp
        self.last_alert_lock = threading.Lock()  # Thread safety for last_alert dictionary
        
        # Track exit analysis history (thread-safe)
        self.analysis_history = {}  # ticket -> List[ExitAnalysis]
        self.analysis_history_lock = threading.Lock()  # Thread safety for analysis_history dictionary
        
        logger.info(f"ExitMonitor initialized (auto_exit={'ON' if auto_exit_enabled else 'OFF'})")
    
    def check_exit_signals(self) -> List[Dict[str, Any]]:
        """
        Check all open positions for exit signals.
        
        Returns:
            List of exit actions taken (for logging/analytics)
        """
        actions = []
        
        try:
            # Get all open positions
            if not self.mt5.connect():
                logger.warning("MT5 not connected, skipping exit signal check")
                return actions
            
            positions = self.mt5.get_positions()
            if not positions:
                return actions
            
            logger.debug(f"Checking {len(positions)} positions for exit signals")
            
            for position in positions:
                try:
                    ticket = position.ticket
                    symbol = position.symbol
                    entry_price = position.price_open
                    current_price = position.price_current
                    current_sl = position.sl if position.sl else 0.0
                    direction = "buy" if position.type == 0 else "sell"
                    
                    # Calculate unrealized profit in R
                    risk = abs(entry_price - current_sl) if current_sl > 0 else 0
                    if risk == 0:
                        logger.debug(f"Position {ticket} has no SL, skipping exit check")
                        continue
                    
                    if direction == "buy":
                        unrealized_profit = current_price - entry_price
                    else:
                        unrealized_profit = entry_price - current_price
                    
                    unrealized_r = unrealized_profit / risk if risk > 0 else 0
                    
                    # Only monitor profitable positions
                    if unrealized_r < self.min_profit_r:
                        continue
                    
                    # Check if this trade is managed by Universal SL/TP Manager or Intelligent Exit Manager
                    # Skip to avoid conflicts (similar to TradeMonitor)
                    from infra.trade_registry import get_trade_state
                    trade_state = get_trade_state(ticket)
                    if trade_state:
                        managed_by = trade_state.managed_by
                        if managed_by in ["universal_sl_tp_manager", "intelligent_exit_manager"]:
                            logger.debug(
                                f"Trade {ticket} is managed by {managed_by}, "
                                f"skipping ExitMonitor exit signal check to avoid conflicts."
                            )
                            continue
                    
                    # Check alert cooldown (thread-safe access)
                    with self.last_alert_lock:
                        last_alert_time = self.last_alert.get(ticket, datetime.min)
                    if datetime.now() - last_alert_time < timedelta(minutes=self.alert_cooldown_minutes):
                        continue
                    
                    # Get market features for analysis
                    try:
                        features = self.feature_builder.build(symbol, ["M5", "M15"])
                        m5_features = features.get("M5", {})
                        m15_features = features.get("M15", {})
                        
                        # Combine features (prioritize M15 for exit signals)
                        combined_features = {**m5_features, **m15_features}
                        
                        # Get bars for advanced analysis
                        bars = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 50)
                        bars_df = None
                        if bars is not None and len(bars) > 0:
                            import pandas as pd
                            bars_df = pd.DataFrame(bars)
                            bars_df['time'] = pd.to_datetime(bars_df['time'], unit='s')
                        
                    except Exception as e:
                        logger.warning(f"Failed to get features for {symbol}: {e}")
                        continue
                    
                    # Analyze exit signals
                    analysis = self.detector.analyze_exit_signals(
                        direction=direction,
                        entry_price=entry_price,
                        current_price=current_price,
                        features=combined_features,
                        bars=bars_df
                    )
                    
                    # Store analysis history (thread-safe access)
                    with self.analysis_history_lock:
                        if ticket not in self.analysis_history:
                            self.analysis_history[ticket] = []
                        self.analysis_history[ticket].append(analysis)
                    
                    # Only act on significant signals
                    if analysis.phase == ExitPhase.NONE:
                        continue
                    
                    # Log the analysis
                    logger.info(
                        f"Exit signal: {symbol} ticket={ticket} | "
                        f"Phase={analysis.phase.value} | "
                        f"Urgency={analysis.urgency.value} | "
                        f"Action={analysis.action} | "
                        f"Confidence={analysis.confidence:.2f} | "
                        f"Signals={len(analysis.signals)}"
                    )
                    
                    # Create action record
                    action = {
                        "ticket": ticket,
                        "symbol": symbol,
                        "direction": direction,
                        "entry_price": entry_price,
                        "current_price": current_price,
                        "unrealized_r": unrealized_r,
                        "phase": analysis.phase.value,
                        "urgency": analysis.urgency.value,
                        "action": analysis.action,
                        "confidence": analysis.confidence,
                        "signals": [
                            {
                                "indicator": s.indicator,
                                "phase": s.phase.value,
                                "strength": s.strength,
                                "message": s.message
                            }
                            for s in analysis.signals
                        ],
                        "rationale": analysis.rationale,
                        "timestamp": datetime.now().isoformat(),
                        "executed": False
                    }
                    
                    # Execute action if auto-exit enabled
                    if self.auto_exit_enabled:
                        executed = self._execute_exit_action(
                            position, analysis.action, analysis.rationale
                        )
                        action["executed"] = executed
                    
                    # Update last alert time (thread-safe access)
                    with self.last_alert_lock:
                        self.last_alert[ticket] = datetime.now()
                    
                    # Log to journal if available
                    if self.journal:
                        try:
                            self.journal.log_event(
                                event_type="exit_signal",
                                symbol=symbol,
                                ticket=ticket,
                                details={
                                    "phase": analysis.phase.value,
                                    "urgency": analysis.urgency.value,
                                    "action": analysis.action,
                                    "confidence": analysis.confidence,
                                    "signal_count": len(analysis.signals),
                                    "executed": action["executed"]
                                }
                            )
                        except Exception as e:
                            logger.error(f"Failed to log exit signal to journal: {e}")
                    
                    actions.append(action)
                    
                except Exception as e:
                    logger.error(f"Error checking exit signals for position {position.ticket}: {e}")
                    continue
            
            return actions
            
        except Exception as e:
            logger.error(f"Error in check_exit_signals: {e}")
            return actions
    
    def _execute_exit_action(
        self,
        position,
        action: str,
        rationale: str
    ) -> bool:
        """
        Execute exit action (tighten trailing stop or full exit).
        
        Args:
            position: MT5 position object
            action: Action to take ("trail_normal", "trail_moderate", "trail_tight", "trail_very_tight", "exit_full")
            rationale: Reason for exit
            
        Returns:
            True if executed successfully, False otherwise
        """
        try:
            ticket = position.ticket
            symbol = position.symbol
            entry_price = position.price_open
            current_price = position.price_current
            current_sl = position.sl if position.sl else 0.0
            direction = "buy" if position.type == 0 else "sell"
            
            # Handle full exit
            if action == "exit_full":
                logger.info(f"Executing {action}: closing full position {symbol} (ticket {ticket})")
                result = self.mt5.close_position(ticket, comment=sanitize_mt5_comment(f"Exit: {rationale}"))
                
                if result and result.get("success"):
                    logger.info(f"✅ Full exit executed: {symbol} ticket {ticket}")
                    return True
                else:
                    logger.error(f"✗ Exit failed: {result}")
                    return False
            
            # Handle trailing stop tightening
            elif action in ["trail_normal", "trail_moderate", "trail_tight", "trail_very_tight"]:
                # Get ATR for trailing calculation
                try:
                    features = self.feature_builder.build(symbol, ["M15"])
                    m15_features = features.get("M15", {})
                    atr = m15_features.get("atr_14", 0)
                    
                    if atr == 0 or atr is None:
                        logger.warning(f"No valid ATR for {symbol}, cannot tighten trailing stop")
                        return False
                    
                    # Determine ATR multiplier based on action
                    atr_multipliers = {
                        "trail_normal": 2.0,
                        "trail_moderate": 1.5,
                        "trail_tight": 1.0,
                        "trail_very_tight": 0.5
                    }
                    atr_mult = atr_multipliers.get(action, 1.5)
                    
                    # Calculate new trailing stop
                    if direction == "buy":
                        new_sl = current_price - (atr * atr_mult)
                        # Only move SL up, never down
                        if new_sl <= current_sl:
                            logger.info(f"New SL {new_sl:.5f} not better than current {current_sl:.5f}, skipping")
                            return False
                    else:  # sell
                        new_sl = current_price + (atr * atr_mult)
                        # Only move SL down, never up
                        if new_sl >= current_sl:
                            logger.info(f"New SL {new_sl:.5f} not better than current {current_sl:.5f}, skipping")
                            return False
                    
                    # Execute SL modification
                    logger.info(f"Executing {action}: tightening SL for {symbol} (ticket {ticket}) from {current_sl:.5f} to {new_sl:.5f} ({atr_mult}x ATR)")
                    
                    request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "symbol": symbol,
                        "position": ticket,
                        "sl": new_sl,
                        "tp": position.tp if position.tp else 0.0,
                        "comment": sanitize_mt5_comment(f"Exit SL: {rationale}")
                    }
                    
                    result = mt5.order_send(request)
                    
                    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                        logger.info(f"✅ Trailing stop tightened: {symbol} ticket {ticket} SL={new_sl:.5f}")
                        return True
                    else:
                        logger.error(f"✗ SL modification failed: {result}")
                        return False
                    
                except Exception as e:
                    logger.error(f"Error calculating trailing stop: {e}")
                    return False
            
            else:
                logger.warning(f"Unknown action: {action}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing exit action: {e}")
            return False
    
    def get_exit_analysis(self, ticket: int) -> Optional[ExitAnalysis]:
        """Get latest exit analysis for a position (thread-safe)."""
        with self.analysis_history_lock:
            history = self.analysis_history.get(ticket, [])
            return history[-1] if history else None
    
    def get_exit_history(self, ticket: int) -> List[ExitAnalysis]:
        """Get full exit analysis history for a position (thread-safe)."""
        with self.analysis_history_lock:
            return self.analysis_history.get(ticket, []).copy()  # Return copy to avoid external modification
    
    def format_exit_alert(self, action: Dict[str, Any]) -> str:
        """
        Format exit signal as Telegram alert message.
        
        Args:
            action: Exit action dictionary
            
        Returns:
            Formatted message string
        """
        symbol = action["symbol"]
        ticket = action["ticket"]
        phase = action["phase"]
        urgency = action["urgency"]
        recommended_action = action["action"]
        confidence = action["confidence"]
        unrealized_r = action["unrealized_r"]
        rationale = action["rationale"]
        signals = action["signals"]
        
        # Emoji mapping
        phase_emoji = {
            "early_warning": "⚠️",
            "exhaustion": "🔶",
            "breakdown": "🔴"
        }
        
        urgency_emoji = {
            "low": "🟡",
            "medium": "🟠",
            "high": "🔴",
            "critical": "🚨"
        }
        
        action_text = {
            "hold": "Hold - Monitor closely",
            "trail_normal": "Maintain trailing stops (2.0x ATR)",
            "trail_moderate": "Tighten stops to 1.5x ATR",
            "trail_tight": "Tighten stops to 1.0x ATR",
            "trail_very_tight": "Tighten stops aggressively (0.5x ATR)",
            "exit_full": "EXIT FULL POSITION (100%)"
        }
        
        # Build message
        msg = f"{phase_emoji.get(phase, '⚠️')} **Exit Signal Detected**\n\n"
        msg += f"**{symbol}** (Ticket: {ticket})\n"
        msg += f"Unrealized Profit: **+{unrealized_r:.2f}R**\n\n"
        msg += f"{urgency_emoji.get(urgency, '🟡')} **Urgency:** {urgency.upper()}\n"
        msg += f"📊 **Phase:** {phase.replace('_', ' ').title()}\n"
        msg += f"🎯 **Recommended:** {action_text.get(recommended_action, recommended_action)}\n"
        msg += f"📈 **Confidence:** {confidence*100:.0f}%\n\n"
        msg += f"💡 **Rationale:**\n{rationale}\n\n"
        
        # List signals
        if signals:
            msg += f"**Signals Detected ({len(signals)}):**\n"
            for sig in signals[:5]:  # Limit to top 5
                msg += f"• {sig['indicator']}: {sig['message']}\n"
        
        return msg


def check_exit_signals_async(exit_monitor: ExitMonitor) -> List[Dict[str, Any]]:
    """
    Async wrapper for ExitMonitor.check_exit_signals().
    
    Args:
        exit_monitor: ExitMonitor instance
        
    Returns:
        List of exit actions
    """
    return exit_monitor.check_exit_signals()
