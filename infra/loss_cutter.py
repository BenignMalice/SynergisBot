"""
Automated Loss-Cutting Module
Implements intelligent early exit logic for losing trades using:
- Confluence risk scoring
- Multi-timeframe invalidation
- Momentum relapse detection
- Wick reversal patterns
- Time-decay backstop
- R-threshold ladder
- Spread/ATR gating
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

import MetaTrader5 as mt5
import pandas as pd

from config import settings
from infra.exit_signal_detector import ExitSignalDetector
from infra.mt5_service import MT5Service
from infra.risk_simulation import simulate as risk_simulate
from infra.profit_protector import ProfitProtector, ProfitProtectionDecision

logger = logging.getLogger(__name__)


@dataclass
class LossCutDecision:
    """Decision on whether to cut a losing trade."""
    should_cut: bool
    reason: str
    urgency: str  # "immediate", "tighten_first", "monitor"
    new_sl: Optional[float] = None  # If tightening first
    confidence: float = 0.0  # 0.0-1.0


class LossCutter:
    """
    Automated loss-cutting system with multi-factor analysis.
    """
    
    def __init__(self, mt5_service: MT5Service):
        """Initialize loss cutter with MT5 service."""
        self.mt5 = mt5_service
        self.exit_detector = ExitSignalDetector()
        self.profit_protector = ProfitProtector()  # NEW: Profit protection module
        self.closing_tickets = set()  # Track tickets being closed to avoid duplicates
        
        # Parse backoff delays
        backoff_str = settings.POS_CLOSE_BACKOFF_MS
        self.backoff_delays = [int(x) / 1000.0 for x in backoff_str.split(',')]
        
        logger.info("LossCutter initialized with config: "
                   f"early_exit_r={settings.POS_EARLY_EXIT_R}, "
                   f"risk_score_threshold={settings.POS_EARLY_EXIT_SCORE}, "
                   f"spread_atr_cap={settings.POS_SPREAD_ATR_CLOSE_CAP}")
    
    def should_cut_loss(
        self,
        position: Any,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame] = None,
        session_volatility: str = "medium",
        order_flow: Optional[Dict[str, Any]] = None
    ) -> LossCutDecision:
        """
        Determine if a position should be cut early or protected.
        
        Args:
            position: MT5 position object
            features: Market features (RSI, MACD, ADX, ATR, etc.)
            bars: Optional OHLCV bars for advanced analysis
            session_volatility: Current session volatility ("low", "medium", "high")
            order_flow: Optional order flow data (whale orders, liquidity voids)
            
        Returns:
            LossCutDecision with action recommendation
        """
        # Calculate R-multiple
        direction = "buy" if position.type == mt5.ORDER_TYPE_BUY else "sell"
        entry_price = position.price_open
        current_price = position.price_current
        stop_loss = position.sl
        take_profit = position.tp
        
        # Calculate R-multiple
        r_multiple = self._calculate_r_multiple(
            direction, entry_price, current_price, stop_loss
        )
        
        # ============================================================================
        # PROFIT PROTECTION (NEW) - Check FIRST for profitable trades
        # ============================================================================
        if r_multiple > 0:
            profit_decision = self.profit_protector.analyze_profit_protection(
                position=position,
                features=features,
                bars=bars,
                order_flow=order_flow,
                r_multiple=r_multiple
            )
            
            if profit_decision:
                if profit_decision.action == "exit":
                    # Exit immediately based on technical warnings
                    logger.warning(f"💰 PROFIT PROTECT EXIT: {position.symbol} "
                                 f"(R={r_multiple:.2f}, Score={profit_decision.total_score}, "
                                 f"Warnings: {profit_decision.reason})")
                    return LossCutDecision(
                        should_cut=True,
                        reason=profit_decision.reason,
                        urgency="immediate",
                        confidence=profit_decision.confidence
                    )
                
                elif profit_decision.action == "tighten":
                    # Tighten SL to structure
                    logger.info(f"💰 PROFIT PROTECT TIGHTEN: {position.symbol} "
                               f"(R={r_multiple:.2f}, Score={profit_decision.total_score}, "
                               f"New SL: {profit_decision.new_sl})")
                    return LossCutDecision(
                        should_cut=False,
                        reason=profit_decision.reason,
                        urgency="tighten_first",
                        new_sl=profit_decision.new_sl,
                        confidence=profit_decision.confidence
                    )
                
                else:  # "monitor"
                    logger.debug(f"💰 PROFIT PROTECT MONITOR: {position.symbol} "
                                f"(R={r_multiple:.2f}, Score={profit_decision.total_score})")
                    # Continue to normal monitoring (don't cut)
        
        # ============================================================================
        # LOSS CUTTING LOGIC (Existing) - Only for LOSING trades
        # ============================================================================
        
        # Get position age in minutes
        position_age_minutes = (time.time() - position.time) / 60
        
        # 1. R-threshold ladder check
        if r_multiple <= settings.POS_EARLY_EXIT_R:
            # Analyze exit signals
            exit_analysis = self.exit_detector.analyze_exit_signals(
                direction, entry_price, current_price, features, bars
            )
            
            # Check confluence risk score
            if exit_analysis.risk_score >= settings.POS_EARLY_EXIT_SCORE:
                # Check spread/ATR gating
                if self._check_spread_atr_gate(position.symbol, features):
                    return LossCutDecision(
                        should_cut=True,
                        reason=f"early_r: R={r_multiple:.2f}, risk_score={exit_analysis.risk_score:.2f}",
                        urgency="immediate",
                        confidence=exit_analysis.risk_score
                    )
        
        # 2. Multi-timeframe invalidation check
        if settings.POS_INVALIDATION_EXIT_ENABLE:
            exit_analysis = self.exit_detector.analyze_exit_signals(
                direction, entry_price, current_price, features, bars
            )
            
            if exit_analysis.structure_invalidations >= 2:
                # Multiple timeframes invalidated
                if self._check_spread_atr_gate(position.symbol, features):
                    return LossCutDecision(
                        should_cut=True,
                        reason=f"invalidation: {exit_analysis.structure_invalidations} TF signals",
                        urgency="immediate",
                        confidence=0.8
                    )
        
        # 3. Momentum relapse check
        exit_analysis = self.exit_detector.analyze_exit_signals(
            direction, entry_price, current_price, features, bars
        )
        
        if exit_analysis.momentum_relapse:
            # Tighten to BE+buffer first
            atr = features.get("atr", 0)
            buffer = atr * 0.3  # 0.3R buffer
            
            if direction == "buy":
                new_sl = entry_price + buffer
            else:
                new_sl = entry_price - buffer
            
            return LossCutDecision(
                should_cut=False,
                reason="momentum_relapse: tighten to BE+0.3R",
                urgency="tighten_first",
                new_sl=new_sl,
                confidence=0.7
            )
        
        # 4. Wick reversal check
        if exit_analysis.wick_reversal:
            # Strong reversal pattern detected
            if r_multiple <= -0.5:
                if self._check_spread_atr_gate(position.symbol, features):
                    return LossCutDecision(
                        should_cut=True,
                        reason="wick_exit: strong reversal pattern",
                        urgency="immediate",
                        confidence=0.75
                    )
        
        # 5. Time-decay backstop
        if settings.POS_TIME_BACKSTOP_ENABLE:
            if self._check_time_decay(position_age_minutes, session_volatility, r_multiple):
                # Position stuck at loss for too long
                if exit_analysis.risk_score >= 0.5:  # Lower threshold for time decay
                    if self._check_spread_atr_gate(position.symbol, features):
                        return LossCutDecision(
                            should_cut=True,
                            reason=f"time_backstop: {position_age_minutes:.0f}min at {r_multiple:.2f}R",
                            urgency="immediate",
                            confidence=0.6
                        )
        
        # 6. Risk simulation veto (only for losing positions)
        if stop_loss > 0 and take_profit > 0:
            atr = features.get("atr", 0)
            if atr > 0:
                sim_result = risk_simulate(entry_price, stop_loss, take_profit, atr)
                expected_r = sim_result.get("expected_r", 0)
                p_hit_sl = sim_result.get("p_hit_sl", 0.5)
                p_hit_tp = sim_result.get("p_hit_tp", 0.5)
                
                # Only apply risk simulation veto if position is losing (R < 0)
                if r_multiple < 0 and expected_r < 0 and p_hit_sl > p_hit_tp * 1.5:
                    # Negative expected R and high probability of hitting SL
                    if self._check_spread_atr_gate(position.symbol, features):
                        return LossCutDecision(
                            should_cut=True,
                            reason=f"risk_sim_neg: E[R]={expected_r:.2f}, P(SL)={p_hit_sl:.2f}",
                            urgency="immediate",
                            confidence=0.7
                        )
        
        # 7. Progressive R-threshold ladder
        if r_multiple <= -0.5:
            # At -0.5R, tighten to BE±buffer
            atr = features.get("atr", 0)
            buffer = atr * 0.2  # 0.2R buffer
            
            if direction == "buy":
                new_sl = entry_price + buffer
            else:
                new_sl = entry_price - buffer
            
            return LossCutDecision(
                should_cut=False,
                reason="r_ladder: -0.5R reached, tighten to BE+0.2R",
                urgency="tighten_first",
                new_sl=new_sl,
                confidence=0.5
            )
        
        # No early exit needed
        return LossCutDecision(
            should_cut=False,
            reason="no_trigger",
            urgency="monitor",
            confidence=0.0
        )
    
    def execute_loss_cut(
        self,
        position: Any,
        reason: str,
        max_retries: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Execute loss cut with retry logic and IOC filling.
        
        Args:
            position: MT5 position object
            reason: Reason for cutting loss
            max_retries: Maximum retry attempts (default from settings)
            
        Returns:
            Tuple of (success, message)
        """
        ticket = position.ticket
        symbol = position.symbol
        
        # Check if already closing
        if ticket in self.closing_tickets:
            return False, "Already closing this position"
        
        # Check if trading is allowed (broker hours)
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logger.error(f"Cannot get symbol info for {symbol}")
            return False, f"Symbol {symbol} not found"
        
        # Check if we can get a valid tick (more reliable than session_deals)
        tick = mt5.symbol_info_tick(symbol)
        if not tick or tick.bid == 0 or tick.ask == 0:
            logger.warning(f"Cannot close {ticket} ({symbol}): No valid tick data (market likely closed)")
            return False, "No valid tick data - market likely closed. Will retry automatically."
        
        # Check tick age (if older than 10 minutes, market is likely closed)
        from datetime import datetime
        tick_time = datetime.fromtimestamp(tick.time)
        tick_age_seconds = (datetime.now() - tick_time).total_seconds()
        if tick_age_seconds > 600:  # 10 minutes
            logger.warning(f"Cannot close {ticket} ({symbol}): Tick data is stale ({tick_age_seconds:.0f}s old)")
            return False, f"Stale tick data ({tick_age_seconds:.0f}s old) - market likely closed. Will retry automatically."
        
        self.closing_tickets.add(ticket)
        
        try:
            max_retries = max_retries or settings.POS_CLOSE_RETRY_MAX
            
            for attempt in range(max_retries):
                # Calculate deviation for this attempt (escalate each retry)
                deviation = self._compute_deviation_points(
                    position.symbol,
                    base_deviation=20,
                    attempt=attempt
                )
                
                # Close position with IOC (Immediate or Cancel)
                # Use sanitized comment (handled by mt5_service.sanitize_mt5_comment)
                comment = f"loss_cut_{reason}"
                
                success, msg = self.mt5.close_position_partial(
                    ticket=ticket,
                    volume=position.volume,
                    deviation=deviation,
                    filling_mode=mt5.ORDER_FILLING_IOC,  # IOC for reliability
                    comment=comment
                )
                
                if success:
                    # Log to database immediately with correct reason
                    try:
                        from infra.journal_repo import JournalRepo
                        journal_repo = JournalRepo()
                        close_price = tick.bid if position.type == 0 else tick.ask
                        
                        # Close the trade in database with loss_cut reason
                        journal_repo.close_trade(
                            ticket=ticket,
                            closed_ts=int(time.time()),
                            exit_price=close_price,
                            close_reason=comment,  # loss_cut_{reason}
                            pnl=position.profit
                        )
                        logger.info(f"📝 Logged loss cut to database: {comment}")
                    except Exception as e:
                        logger.warning(f"Failed to log loss cut to database: {e}")
                    
                    logger.info(f"Loss cut successful for ticket {ticket}: {reason}")
                    return True, f"Closed at attempt {attempt + 1}: {msg}"
                
                # Exponential backoff before retry
                if attempt < max_retries - 1:
                    delay = self.backoff_delays[min(attempt, len(self.backoff_delays) - 1)]
                    logger.warning(f"Loss cut attempt {attempt + 1} failed for {ticket}, "
                                 f"retrying in {delay}s: {msg}")
                    time.sleep(delay)
            
            logger.error(f"Loss cut failed after {max_retries} attempts for {ticket}")
            return False, f"Failed after {max_retries} attempts: {msg}"
            
        finally:
            self.closing_tickets.discard(ticket)
    
    def _calculate_r_multiple(
        self,
        direction: str,
        entry_price: float,
        current_price: float,
        stop_loss: float
    ) -> float:
        """Calculate R-multiple for position."""
        if stop_loss == 0:
            return 0.0
        
        risk = abs(entry_price - stop_loss)
        if risk == 0:
            return 0.0
        
        if direction == "buy":
            pnl = current_price - entry_price
        else:
            pnl = entry_price - current_price
        
        return pnl / risk
    
    def _check_spread_atr_gate(self, symbol: str, features: Dict[str, Any]) -> bool:
        """Check if spread/ATR ratio is acceptable for closing."""
        # Get current spread
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return True  # Allow close if we can't get spread
        
        spread = tick.ask - tick.bid
        atr = features.get("atr", 0)
        
        if atr == 0:
            return True  # Allow close if ATR not available
        
        spread_atr_ratio = spread / atr
        
        # Check if spread is acceptable
        if spread_atr_ratio > settings.POS_SPREAD_ATR_CLOSE_CAP:
            logger.warning(f"Spread/ATR ratio {spread_atr_ratio:.2f} exceeds cap "
                         f"{settings.POS_SPREAD_ATR_CLOSE_CAP} for {symbol}")
            return False
        
        return True
    
    def _check_time_decay(
        self,
        position_age_minutes: int,
        session_volatility: str,
        r_multiple: float
    ) -> bool:
        """Check if position has been at loss for too long."""
        # Adjust threshold based on session volatility
        if session_volatility == "high":
            max_age = 60  # 1 hour for high volatility
        elif session_volatility == "medium":
            max_age = 120  # 2 hours for medium volatility
        else:
            max_age = 180  # 3 hours for low volatility
        
        # Check if position is stuck at loss
        if position_age_minutes > max_age and r_multiple <= 0:
            return True
        
        return False
    
    def _compute_deviation_points(
        self,
        symbol: str,
        base_deviation: int = 20,
        attempt: int = 0
    ) -> int:
        """Compute deviation points with escalation for retries."""
        # Escalate deviation for each retry attempt
        escalation_factor = 1 + (attempt * 0.5)  # 50% increase per attempt
        deviation = int(base_deviation * escalation_factor)
        
        # Cap at reasonable maximum
        return min(deviation, 100)


def create_loss_cutter(mt5_service: MT5Service) -> LossCutter:
    """Factory function to create a LossCutter instance."""
    return LossCutter(mt5_service)
