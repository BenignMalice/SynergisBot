"""
Loss Cut Monitor - Live Trade Loss Management
Integrates LossCutDetector with TradeMonitor for automated loss cutting.

Monitors losing positions and:
1. Detects loss cut signals using 7-category framework
2. Sends Telegram alerts when 3-Strikes Rule triggers
3. Optionally auto-executes loss cuts (manual by default)
4. Logs all loss cut signals to database for analysis
"""

import logging
import MetaTrader5 as mt5
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from infra.loss_cut_detector import (
    LossCutDetector,
    LossCutAnalysis,
    LossCutCategory,
    LossCutUrgency
)

logger = logging.getLogger(__name__)


class LossCutMonitor:
    """
    Monitors losing positions for systematic loss cut signals.
    
    This class works alongside TradeMonitor to detect when losing
    trades should be cut based on professional criteria.
    """
    
    def __init__(
        self,
        mt5_service,
        feature_builder,
        journal_repo=None,
        auto_cut_enabled: bool = False,  # Safety: manual by default
        min_loss_r: float = -0.3,  # Only monitor positions with <= -0.3R loss
        alert_cooldown_minutes: int = 15  # Min time between alerts for same position
    ):
        """
        Initialize loss cut monitor.
        
        Args:
            mt5_service: MT5Service instance
            feature_builder: FeatureBuilder instance for market data
            journal_repo: Optional JournalRepo for logging
            auto_cut_enabled: Whether to auto-execute cuts (False = alerts only)
            min_loss_r: Minimum loss (in R) before monitoring for cuts
            alert_cooldown_minutes: Minimum minutes between alerts for same position
        """
        self.mt5 = mt5_service
        self.feature_builder = feature_builder
        self.journal = journal_repo
        self.auto_cut_enabled = auto_cut_enabled
        self.min_loss_r = min_loss_r
        self.alert_cooldown_minutes = alert_cooldown_minutes
        
        self.detector = LossCutDetector()
        
        # Track last alert time per position
        self.last_alert = {}  # ticket -> timestamp
        
        # Track analysis history
        self.analysis_history = {}  # ticket -> List[LossCutAnalysis]
        
        # Track position entry times (for time-based invalidation)
        self.entry_times = {}  # ticket -> entry_time
        
        logger.info(f"LossCutMonitor initialized (auto_cut={'ON' if auto_cut_enabled else 'OFF'})")
    
    def check_loss_cuts(self, daily_pnl_pct: float = 0.0) -> List[Dict[str, Any]]:
        """
        Check all open positions for loss cut signals.
        
        Args:
            daily_pnl_pct: Current daily P&L percentage
            
        Returns:
            List of loss cut actions taken (for logging/analytics)
        """
        actions = []
        
        try:
            # Get all open positions
            if not self.mt5.connect():
                logger.warning("MT5 not connected, skipping loss cut check")
                return actions
            
            positions = self.mt5.get_positions()
            if not positions:
                return actions
            
            logger.debug(f"Checking {len(positions)} positions for loss cut signals")
            
            for position in positions:
                try:
                    ticket = position.ticket
                    symbol = position.symbol
                    entry_price = position.price_open
                    current_price = position.price_current
                    current_sl = position.sl if position.sl else 0.0
                    direction = "buy" if position.type == 0 else "sell"
                    
                    # Get or set entry time
                    if ticket not in self.entry_times:
                        # Use position open time from MT5
                        self.entry_times[ticket] = datetime.fromtimestamp(position.time)
                    entry_time = self.entry_times[ticket]
                    
                    # Calculate unrealized profit in R
                    risk = abs(entry_price - current_sl) if current_sl > 0 else 0
                    if risk == 0:
                        logger.debug(f"Position {ticket} has no SL, skipping loss cut check")
                        continue
                    
                    if direction == "buy":
                        unrealized_profit = current_price - entry_price
                    else:
                        unrealized_profit = entry_price - current_price
                    
                    unrealized_r = unrealized_profit / risk if risk > 0 else 0
                    
                    # Only monitor losing positions
                    if unrealized_r >= self.min_loss_r:
                        continue
                    
                    # Check alert cooldown
                    last_alert_time = self.last_alert.get(ticket, datetime.min)
                    if datetime.now() - last_alert_time < timedelta(minutes=self.alert_cooldown_minutes):
                        continue
                    
                    # Get market features for analysis
                    try:
                        features = self.feature_builder.build(symbol, ["M5", "M15"])
                        m5_features = features.get("M5", {})
                        m15_features = features.get("M15", {})
                        
                        # Combine features (prioritize M15 for loss cut signals)
                        combined_features = {**m5_features, **m15_features}
                        combined_features["price"] = current_price
                        
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
                    
                    # Determine trade type (for time-based invalidation)
                    # Simple heuristic: if SL is tight (< 0.5% of price), it's a scalp
                    sl_pct = abs(entry_price - current_sl) / entry_price if entry_price > 0 else 0
                    if sl_pct < 0.005:
                        trade_type = "scalp"
                    elif sl_pct < 0.02:
                        trade_type = "intraday"
                    else:
                        trade_type = "swing"
                    
                    # Analyze loss cut signals
                    analysis = self.detector.analyze_loss_cut(
                        direction=direction,
                        entry_price=entry_price,
                        entry_time=entry_time,
                        current_price=current_price,
                        current_sl=current_sl,
                        features=combined_features,
                        bars=bars_df,
                        trade_type=trade_type,
                        daily_pnl_pct=daily_pnl_pct
                    )
                    
                    # Store analysis history
                    if ticket not in self.analysis_history:
                        self.analysis_history[ticket] = []
                    self.analysis_history[ticket].append(analysis)
                    
                    # Only act on significant signals (WARNING or higher)
                    if analysis.urgency == LossCutUrgency.NONE:
                        continue
                    
                    # Log the analysis
                    logger.info(
                        f"Loss cut signal: {symbol} ticket={ticket} | "
                        f"Urgency={analysis.urgency.value} | "
                        f"Strikes={analysis.strikes}/7 | "
                        f"Action={analysis.action} | "
                        f"Confidence={analysis.confidence:.2f} | "
                        f"Loss={analysis.unrealized_r:.2f}R"
                    )
                    
                    # Create action record
                    action = {
                        "ticket": ticket,
                        "symbol": symbol,
                        "direction": direction,
                        "entry_price": entry_price,
                        "current_price": current_price,
                        "unrealized_r": unrealized_r,
                        "urgency": analysis.urgency.value,
                        "strikes": analysis.strikes,
                        "action": analysis.action,
                        "confidence": analysis.confidence,
                        "signals": [
                            {
                                "category": s.category.value,
                                "severity": s.severity,
                                "message": s.message
                            }
                            for s in analysis.signals
                        ],
                        "rationale": analysis.rationale,
                        "time_in_trade_minutes": analysis.time_in_trade_minutes,
                        "timestamp": datetime.now().isoformat(),
                        "executed": False
                    }
                    
                    # Execute action if auto-cut enabled
                    if self.auto_cut_enabled:
                        executed = self._execute_loss_cut_action(
                            position, analysis.action, analysis.rationale
                        )
                        action["executed"] = executed
                    
                    # Update last alert time
                    self.last_alert[ticket] = datetime.now()
                    
                    # Log to journal if available
                    if self.journal:
                        try:
                            self.journal.log_event(
                                event_type="loss_cut_signal",
                                symbol=symbol,
                                ticket=ticket,
                                details={
                                    "urgency": analysis.urgency.value,
                                    "strikes": analysis.strikes,
                                    "action": analysis.action,
                                    "confidence": analysis.confidence,
                                    "signal_count": len(analysis.signals),
                                    "executed": action["executed"]
                                }
                            )
                        except Exception as e:
                            logger.error(f"Failed to log loss cut signal to journal: {e}")
                    
                    actions.append(action)
                    
                except Exception as e:
                    logger.error(f"Error checking loss cut signals for position {position.ticket}: {e}")
                    continue
            
            return actions
            
        except Exception as e:
            logger.error(f"Error in check_loss_cuts: {e}")
            return actions
    
    def _execute_loss_cut_action(
        self,
        position,
        action: str,
        rationale: str
    ) -> bool:
        """
        Execute loss cut action (tighten SL, partial cut, or full cut).
        
        Args:
            position: MT5 position object
            action: Action to take ("tighten_sl", "cut_50", "cut_full")
            rationale: Reason for cut
            
        Returns:
            True if executed successfully, False otherwise
        """
        try:
            ticket = position.ticket
            symbol = position.symbol
            volume = position.volume
            current_price = position.price_current
            current_sl = position.sl if position.sl else 0.0
            direction = "buy" if position.type == 0 else "sell"
            
            # Handle full cut
            if action == "cut_full":
                logger.info(f"Executing {action}: closing full position {symbol} (ticket {ticket})")
                result = self.mt5.close_position(ticket, comment=f"Loss cut: {rationale[:30]}")
                
                if result and result.get("success"):
                    logger.info(f"✅ Full loss cut executed: {symbol} ticket {ticket}")
                    return True
                else:
                    logger.error(f"✗ Loss cut failed: {result}")
                    return False
            
            # Handle 50% cut
            elif action == "cut_50":
                close_volume = round(volume * 0.50, 2)
                
                if close_volume < 0.01:
                    logger.warning(f"Close volume too small: {close_volume}, closing full position instead")
                    result = self.mt5.close_position(ticket, comment=f"Loss cut: {rationale[:30]}")
                else:
                    logger.info(f"Executing {action}: closing 50% ({close_volume} lots) of {symbol} (ticket {ticket})")
                    result = self.mt5.close_position(ticket, volume=close_volume, comment=f"Loss cut 50%: {rationale[:20]}")
                
                if result and result.get("success"):
                    logger.info(f"✅ 50% loss cut executed: {symbol} ticket {ticket}")
                    return True
                else:
                    logger.error(f"✗ Loss cut failed: {result}")
                    return False
            
            # Handle SL tightening
            elif action == "tighten_sl":
                # Get ATR for calculation
                try:
                    features = self.feature_builder.build(symbol, ["M15"])
                    m15_features = features.get("M15", {})
                    atr = m15_features.get("atr_14", 0)
                    
                    if atr == 0 or atr is None:
                        logger.warning(f"No valid ATR for {symbol}, cannot tighten SL")
                        return False
                    
                    # Tighten to breakeven or 0.5x ATR (whichever is tighter)
                    entry_price = position.price_open
                    
                    if direction == "buy":
                        new_sl_be = entry_price  # Breakeven
                        new_sl_atr = current_price - (0.5 * atr)  # 0.5x ATR
                        new_sl = max(new_sl_be, new_sl_atr)  # Tighter of the two
                        
                        # Only move SL up
                        if new_sl <= current_sl:
                            logger.info(f"New SL {new_sl:.5f} not better than current {current_sl:.5f}, skipping")
                            return False
                    else:  # sell
                        new_sl_be = entry_price  # Breakeven
                        new_sl_atr = current_price + (0.5 * atr)  # 0.5x ATR
                        new_sl = min(new_sl_be, new_sl_atr)  # Tighter of the two
                        
                        # Only move SL down
                        if new_sl >= current_sl:
                            logger.info(f"New SL {new_sl:.5f} not better than current {current_sl:.5f}, skipping")
                            return False
                    
                    # Execute SL modification
                    logger.info(f"Executing {action}: tightening SL for {symbol} (ticket {ticket}) from {current_sl:.5f} to {new_sl:.5f}")
                    
                    request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "symbol": symbol,
                        "position": ticket,
                        "sl": new_sl,
                        "tp": position.tp if position.tp else 0.0,
                        "comment": f"Loss cut SL: {rationale[:20]}"
                    }
                    
                    result = mt5.order_send(request)
                    
                    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                        logger.info(f"✅ SL tightened: {symbol} ticket {ticket} SL={new_sl:.5f}")
                        return True
                    else:
                        logger.error(f"✗ SL modification failed: {result}")
                        return False
                    
                except Exception as e:
                    logger.error(f"Error tightening SL: {e}")
                    return False
            
            else:
                logger.warning(f"Unknown action: {action}")
                return False
                
        except Exception as e:
            logger.error(f"Error executing loss cut action: {e}")
            return False
    
    def get_loss_cut_analysis(self, ticket: int) -> Optional[LossCutAnalysis]:
        """Get latest loss cut analysis for a position."""
        history = self.analysis_history.get(ticket, [])
        return history[-1] if history else None
    
    def get_loss_cut_history(self, ticket: int) -> List[LossCutAnalysis]:
        """Get full loss cut analysis history for a position."""
        return self.analysis_history.get(ticket, [])
    
    def format_loss_cut_alert(self, action: Dict[str, Any]) -> str:
        """
        Format loss cut signal as Telegram alert message.
        
        Args:
            action: Loss cut action dictionary
            
        Returns:
            Formatted message string
        """
        symbol = action["symbol"]
        ticket = action["ticket"]
        urgency = action["urgency"]
        strikes = action["strikes"]
        recommended_action = action["action"]
        confidence = action["confidence"]
        unrealized_r = action["unrealized_r"]
        rationale = action["rationale"]
        signals = action["signals"]
        time_in_trade = action["time_in_trade_minutes"]
        
        # Emoji mapping
        urgency_emoji = {
            "warning": "⚠️",
            "caution": "🟠",
            "critical": "🚨"
        }
        
        action_text = {
            "hold": "Hold - Monitor closely",
            "tighten_sl": "Tighten SL to breakeven or 0.5x ATR",
            "cut_50": "CUT 50% of position",
            "cut_full": "CUT FULL POSITION IMMEDIATELY"
        }
        
        # Build message
        msg = f"{urgency_emoji.get(urgency, '⚠️')} **Loss Cut Signal**\n\n"
        msg += f"**{symbol}** (Ticket: {ticket})\n"
        msg += f"Unrealized Loss: **{unrealized_r:.2f}R**\n"
        msg += f"Time in Trade: {time_in_trade} minutes\n\n"
        msg += f"🚨 **Urgency:** {urgency.upper()}\n"
        msg += f"⚡ **Strikes:** {strikes}/7 categories triggered\n"
        msg += f"🎯 **Recommended:** {action_text.get(recommended_action, recommended_action)}\n"
        msg += f"📈 **Confidence:** {confidence*100:.0f}%\n\n"
        msg += f"💡 **Rationale:**\n{rationale}\n\n"
        
        # List signals by category
        if signals:
            msg += f"**Signals Detected ({len(signals)}):**\n"
            for sig in signals[:5]:  # Limit to top 5
                msg += f"• [{sig['category'].upper()}] {sig['message']}\n"
        
        return msg


def check_loss_cuts_async(loss_cut_monitor: LossCutMonitor, daily_pnl_pct: float = 0.0) -> List[Dict[str, Any]]:
    """
    Async wrapper for LossCutMonitor.check_loss_cuts().
    
    Args:
        loss_cut_monitor: LossCutMonitor instance
        daily_pnl_pct: Current daily P&L percentage
        
    Returns:
        List of loss cut actions
    """
    return loss_cut_monitor.check_loss_cuts(daily_pnl_pct)
