"""
Volatility-Aware Risk Management - Phase 3 Implementation

Adapts position sizing, stop loss, and take profit based on volatility regime.
Implements:
- Volatility-adjusted position sizing (0.5% in volatile, 1.0% in stable)
- Regime confidence as risk dial (modulate sizing by confidence)
- Volatility-adjusted stop loss calculation
- Circuit breakers (daily loss limits, trade cooldowns)
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Import VolatilityRegime from volatility_regime_detector to use extended enum
try:
    from infra.volatility_regime_detector import VolatilityRegime
except ImportError:
    # Fallback enum if import fails (shouldn't happen in production)
    from enum import Enum
    class VolatilityRegime(Enum):
        """Volatility regime classifications (fallback)"""
        STABLE = "STABLE"
        TRANSITIONAL = "TRANSITIONAL"
        VOLATILE = "VOLATILE"
        PRE_BREAKOUT_TENSION = "PRE_BREAKOUT_TENSION"
        POST_BREAKOUT_DECAY = "POST_BREAKOUT_DECAY"
        FRAGMENTED_CHOP = "FRAGMENTED_CHOP"
        SESSION_SWITCH_FLARE = "SESSION_SWITCH_FLARE"


class VolatilityRiskManager:
    """
    Manages risk adjustments based on volatility regime.
    """
    
    # Base risk percentages by regime (% of equity)
    BASE_RISK_STABLE = 1.0  # 1.0% in stable conditions
    BASE_RISK_TRANSITIONAL = 0.75  # 0.75% in transitional conditions
    BASE_RISK_VOLATILE = 0.5  # 0.5% in volatile conditions
    # Phase 6.1: New volatility states
    BASE_RISK_PRE_BREAKOUT_TENSION = 0.85  # 0.85% (slight reduction - potential expansion)
    BASE_RISK_POST_BREAKOUT_DECAY = 0.9  # 0.9% (slight reduction - momentum fading)
    BASE_RISK_FRAGMENTED_CHOP = 0.6  # 0.6% (significant reduction - choppy conditions)
    BASE_RISK_SESSION_SWITCH_FLARE = 0.0  # 0.0% (block trading - wait for stabilization)
    
    # Spread gates (Phase 3.08)
    SPREAD_MULTIPLIER_THRESHOLD = 1.5  # Block if spread > 1.5× baseline
    MAX_SLIPPAGE_PCT = 0.15  # Maximum slippage per trade (≤ 0.15R = 15% of risk)
    
    # Latency-aware triggers
    PRICE_HOLD_DURATION_SECONDS = 1  # Require price to hold beyond trigger for minimum duration
    
    # Confidence adjustment factor
    # Full confidence (100%) = full risk, 70% confidence = 70% of base risk
    CONFIDENCE_FLOOR = 0.7  # Minimum confidence to trade at all
    CONFIDENCE_ADJUSTMENT_FACTOR = 1.0  # Linear scaling from floor to 1.0
    
    # Stop loss multipliers by regime (× ATR)
    SL_MULTIPLIER_STABLE = 1.5  # Tighter stops in stable conditions
    SL_MULTIPLIER_TRANSITIONAL = 1.75  # Slightly wider in transitional
    SL_MULTIPLIER_VOLATILE = 2.0  # Wider stops in volatile conditions
    # Phase 6.2: New volatility states
    SL_MULTIPLIER_PRE_BREAKOUT_TENSION = 1.725  # Slightly wider (1.15× stable) - potential expansion
    SL_MULTIPLIER_POST_BREAKOUT_DECAY = 1.5  # Same as stable (momentum fading, no expansion)
    SL_MULTIPLIER_FRAGMENTED_CHOP = 1.2  # Tighter (0.8× stable) - choppy conditions need tighter SL
    SL_MULTIPLIER_SESSION_SWITCH_FLARE = 0.0  # Block trading (no SL calculation)
    
    # Take profit multipliers by regime (× ATR)
    TP_MULTIPLIER_STABLE = 3.0  # Standard TP in stable
    TP_MULTIPLIER_TRANSITIONAL = 2.5  # Slightly reduced in transitional
    TP_MULTIPLIER_VOLATILE = 2.0  # Reduced TP in volatile (faster exits)
    # Phase 6.2: New volatility states
    TP_MULTIPLIER_PRE_BREAKOUT_TENSION = 3.0  # Same as stable (breakout potential)
    TP_MULTIPLIER_POST_BREAKOUT_DECAY = 2.0  # Reduced (momentum fading - faster exits)
    TP_MULTIPLIER_FRAGMENTED_CHOP = 1.8  # Reduced (choppy conditions - smaller targets)
    TP_MULTIPLIER_SESSION_SWITCH_FLARE = 0.0  # Block trading (no TP calculation)
    
    def __init__(self):
        """Initialize the volatility risk manager"""
        # Daily loss tracking
        self._daily_losses: Dict[str, float] = {}  # symbol -> daily loss
        self._daily_trade_count: Dict[str, int] = {}  # symbol -> trade count
        self._last_loss_time: Dict[str, datetime] = {}  # symbol -> last loss time
        
        # Circuit breaker thresholds
        self.MAX_DAILY_LOSS_PCT = 3.0  # 3% of equity per day
        self.MAX_TRADES_PER_DAY = 3  # Max 3 trades per day in volatile conditions
        self.LOSS_COOLDOWN_MINUTES = 15  # 15-30 min cooldown after loss
    
    def calculate_volatility_adjusted_risk_pct(
        self,
        volatility_regime: Dict[str, Any],
        base_risk_pct: Optional[float] = None
    ) -> float:
        """
        Calculate volatility-adjusted risk percentage.
        
        Args:
            volatility_regime: Detected volatility regime data
            base_risk_pct: Base risk percentage (if None, uses symbol default)
        
        Returns:
            Adjusted risk percentage (% of equity)
        """
        try:
            # Get regime and confidence
            regime = volatility_regime.get("regime")
            confidence = volatility_regime.get("confidence", 100.0)
            
            # Extract regime string
            if isinstance(regime, VolatilityRegime):
                regime_str = regime.value
            elif hasattr(regime, 'value'):
                regime_str = regime.value
            else:
                regime_str = str(regime) if regime else "STABLE"
            
            # Check confidence threshold
            if confidence < self.CONFIDENCE_FLOOR * 100:
                logger.warning(
                    f"Confidence {confidence:.1f}% below threshold "
                    f"({self.CONFIDENCE_FLOOR * 100:.0f}%), using minimum risk"
                )
                # Use minimum risk if confidence too low
                adjusted_risk = self.BASE_RISK_VOLATILE * 0.5
                return adjusted_risk
            
            # Get base risk by regime (regime-specific defaults)
            # Phase 6.1: Handle new volatility states
            if regime_str == "VOLATILE":
                regime_base_risk = self.BASE_RISK_VOLATILE
            elif regime_str == "TRANSITIONAL":
                regime_base_risk = self.BASE_RISK_TRANSITIONAL
            elif regime_str == "PRE_BREAKOUT_TENSION":
                regime_base_risk = self.BASE_RISK_PRE_BREAKOUT_TENSION
            elif regime_str == "POST_BREAKOUT_DECAY":
                regime_base_risk = self.BASE_RISK_POST_BREAKOUT_DECAY
            elif regime_str == "FRAGMENTED_CHOP":
                regime_base_risk = self.BASE_RISK_FRAGMENTED_CHOP
            elif regime_str == "SESSION_SWITCH_FLARE":
                # SESSION_SWITCH_FLARE blocks all trading - return immediately
                logger.warning(
                    f"SESSION_SWITCH_FLARE detected - blocking trade "
                    f"(risk adjusted to 0.0%)"
                )
                return 0.0
            else:  # STABLE (default)
                regime_base_risk = self.BASE_RISK_STABLE
            
            # Use provided base risk if given, otherwise use regime-specific default
            if base_risk_pct is not None:
                # If provided, use it but ensure it respects regime constraints
                # For volatile, don't allow higher than volatile base
                if regime_str == "VOLATILE" and base_risk_pct > regime_base_risk:
                    base_risk = regime_base_risk
                else:
                    base_risk = base_risk_pct
            else:
                base_risk = regime_base_risk
            
            # Adjust by confidence (linear scaling from floor to 1.0)
            # Confidence only reduces risk if below threshold, doesn't increase it
            confidence_factor = max(
                self.CONFIDENCE_FLOOR,
                min(1.0, confidence / 100.0)
            )
            
            # Apply confidence scaling: if confidence is low, reduce risk proportionally
            # But base risk by regime is already set correctly (volatile = 0.5%, stable = 1.0%)
            # So we only scale DOWN if confidence is below 100%
            adjusted_risk = base_risk * confidence_factor
            
            logger.info(
                f"Volatility-adjusted risk: {regime_str} regime, "
                f"confidence {confidence:.1f}%, "
                f"base risk {base_risk:.2f}% -> adjusted {adjusted_risk:.2f}%"
            )
            
            return adjusted_risk
            
        except Exception as e:
            logger.error(f"Error calculating volatility-adjusted risk: {e}", exc_info=True)
            # Fallback to conservative risk
            return self.BASE_RISK_VOLATILE
    
    def calculate_volatility_adjusted_stop_loss(
        self,
        entry_price: float,
        direction: str,
        atr: float,
        volatility_regime: Dict[str, Any]
    ) -> float:
        """
        Calculate volatility-adjusted stop loss.
        
        Args:
            entry_price: Trade entry price
            direction: "BUY" or "SELL"
            atr: Current ATR value
            volatility_regime: Detected volatility regime data
        
        Returns:
            Stop loss price
        """
        try:
            # Get regime
            regime = volatility_regime.get("regime")
            if isinstance(regime, VolatilityRegime):
                regime_str = regime.value
            elif hasattr(regime, 'value'):
                regime_str = regime.value
            else:
                regime_str = str(regime) if regime else "STABLE"
            
            # Get SL multiplier by regime
            # Phase 6.2: Handle new volatility states
            if regime_str == "VOLATILE":
                sl_multiplier = self.SL_MULTIPLIER_VOLATILE
            elif regime_str == "TRANSITIONAL":
                sl_multiplier = self.SL_MULTIPLIER_TRANSITIONAL
            elif regime_str == "PRE_BREAKOUT_TENSION":
                sl_multiplier = self.SL_MULTIPLIER_PRE_BREAKOUT_TENSION
            elif regime_str == "POST_BREAKOUT_DECAY":
                sl_multiplier = self.SL_MULTIPLIER_POST_BREAKOUT_DECAY
            elif regime_str == "FRAGMENTED_CHOP":
                sl_multiplier = self.SL_MULTIPLIER_FRAGMENTED_CHOP
            elif regime_str == "SESSION_SWITCH_FLARE":
                # SESSION_SWITCH_FLARE blocks trading
                logger.warning(
                    f"SESSION_SWITCH_FLARE detected - cannot calculate SL "
                    f"(trading blocked)"
                )
                # Return None or raise exception to block trade
                return None
            else:  # STABLE (default)
                sl_multiplier = self.SL_MULTIPLIER_STABLE
            
            # Calculate stop distance
            stop_distance = atr * sl_multiplier
            
            # Calculate stop price
            if direction.upper() == "BUY":
                stop_loss = entry_price - stop_distance
            else:  # SELL
                stop_loss = entry_price + stop_distance
            
            logger.info(
                f"Volatility-adjusted SL: {regime_str} regime, "
                f"ATR={atr:.5f}, multiplier={sl_multiplier}x, "
                f"distance={stop_distance:.5f}, SL={stop_loss:.5f}"
            )
            
            return stop_loss
            
        except Exception as e:
            logger.error(f"Error calculating volatility-adjusted stop loss: {e}", exc_info=True)
            # Fallback to 2×ATR (conservative)
            stop_distance = atr * 2.0
            if direction.upper() == "BUY":
                return entry_price - stop_distance
            else:
                return entry_price + stop_distance
    
    def calculate_volatility_adjusted_take_profit(
        self,
        entry_price: float,
        stop_loss: float,
        direction: str,
        atr: float,
        volatility_regime: Dict[str, Any],
        target_rr: Optional[float] = None
    ) -> float:
        """
        Calculate volatility-adjusted take profit.
        
        Args:
            entry_price: Trade entry price
            stop_loss: Stop loss price
            direction: "BUY" or "SELL"
            atr: Current ATR value
            volatility_regime: Detected volatility regime data
            target_rr: Target risk:reward ratio (if None, uses regime-based TP)
        
        Returns:
            Take profit price
        """
        try:
            # Calculate stop distance
            if direction.upper() == "BUY":
                stop_distance = entry_price - stop_loss
            else:  # SELL
                stop_distance = stop_loss - entry_price
            
            if stop_distance <= 0:
                logger.warning(f"Invalid stop distance: {stop_distance}")
                stop_distance = atr * 2.0  # Fallback
            
            # If target R:R provided, use that
            if target_rr is not None:
                tp_distance = stop_distance * target_rr
            else:
                # Get regime-based TP multiplier
                regime = volatility_regime.get("regime")
                if isinstance(regime, VolatilityRegime):
                    regime_str = regime.value
                elif hasattr(regime, 'value'):
                    regime_str = regime.value
                else:
                    regime_str = str(regime) if regime else "STABLE"
                
                # Phase 6.2: Handle new volatility states
                if regime_str == "VOLATILE":
                    tp_multiplier = self.TP_MULTIPLIER_VOLATILE
                elif regime_str == "TRANSITIONAL":
                    tp_multiplier = self.TP_MULTIPLIER_TRANSITIONAL
                elif regime_str == "PRE_BREAKOUT_TENSION":
                    tp_multiplier = self.TP_MULTIPLIER_PRE_BREAKOUT_TENSION
                elif regime_str == "POST_BREAKOUT_DECAY":
                    tp_multiplier = self.TP_MULTIPLIER_POST_BREAKOUT_DECAY
                elif regime_str == "FRAGMENTED_CHOP":
                    tp_multiplier = self.TP_MULTIPLIER_FRAGMENTED_CHOP
                elif regime_str == "SESSION_SWITCH_FLARE":
                    # SESSION_SWITCH_FLARE blocks trading
                    logger.warning(
                        f"SESSION_SWITCH_FLARE detected - cannot calculate TP "
                        f"(trading blocked)"
                    )
                    # Return None or raise exception to block trade
                    return None
                else:  # STABLE (default)
                    tp_multiplier = self.TP_MULTIPLIER_STABLE
                
                # Calculate TP distance using ATR-based multiplier
                tp_distance = atr * tp_multiplier
            
            # Calculate TP price
            if direction.upper() == "BUY":
                take_profit = entry_price + tp_distance
            else:  # SELL
                take_profit = entry_price - tp_distance
            
            logger.info(
                f"Volatility-adjusted TP: distance={tp_distance:.5f}, "
                f"TP={take_profit:.5f}"
            )
            
            return take_profit
            
        except Exception as e:
            logger.error(f"Error calculating volatility-adjusted take profit: {e}", exc_info=True)
            # Fallback to 2:1 R:R
            stop_distance = abs(entry_price - stop_loss)
            tp_distance = stop_distance * 2.0
            if direction.upper() == "BUY":
                return entry_price + tp_distance
            else:
                return entry_price - tp_distance
    
    def check_circuit_breakers(
        self,
        symbol: str,
        equity: float,
        current_time: Optional[datetime] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if circuit breakers should prevent trading.
        
        Args:
            symbol: Trading symbol
            equity: Account equity
            current_time: Current timestamp
        
        Returns:
            Tuple of (can_trade, reason_if_blocked)
        """
        if current_time is None:
            current_time = datetime.now()
        
        # Check daily loss limit
        daily_loss = self._daily_losses.get(symbol, 0.0)
        loss_pct = (daily_loss / equity * 100) if equity > 0 else 0.0
        
        if loss_pct >= self.MAX_DAILY_LOSS_PCT:
            return False, f"Daily loss limit reached ({loss_pct:.2f}% >= {self.MAX_DAILY_LOSS_PCT}%)"
        
        # Check trade count limit
        trade_count = self._daily_trade_count.get(symbol, 0)
        if trade_count >= self.MAX_TRADES_PER_DAY:
            return False, f"Daily trade limit reached ({trade_count} >= {self.MAX_TRADES_PER_DAY})"
        
        # Check cooldown after loss
        last_loss_time = self._last_loss_time.get(symbol)
        if last_loss_time:
            time_since_loss = (current_time - last_loss_time).total_seconds() / 60
            if time_since_loss < self.LOSS_COOLDOWN_MINUTES:
                remaining = self.LOSS_COOLDOWN_MINUTES - time_since_loss
                return False, f"Cooldown active ({remaining:.1f} min remaining)"
        
        return True, None
    
    def record_trade(
        self,
        symbol: str,
        pnl: float,
        current_time: Optional[datetime] = None
    ) -> None:
        """
        Record a trade for circuit breaker tracking.
        
        Args:
            symbol: Trading symbol
            pnl: Profit/loss of the trade
            current_time: Current timestamp
        """
        if current_time is None:
            current_time = datetime.now()
        
        # Update daily trade count
        if symbol not in self._daily_trade_count:
            self._daily_trade_count[symbol] = 0
        self._daily_trade_count[symbol] += 1
        
        # Update daily loss if negative
        if pnl < 0:
            if symbol not in self._daily_losses:
                self._daily_losses[symbol] = 0.0
            self._daily_losses[symbol] += abs(pnl)
            self._last_loss_time[symbol] = current_time
        
        # Reset daily counters at midnight (simplified - could be improved)
        # For now, just track per session
        logger.debug(
            f"Trade recorded for {symbol}: PnL={pnl:.2f}, "
            f"Daily loss={self._daily_losses.get(symbol, 0.0):.2f}, "
            f"Trade count={self._daily_trade_count.get(symbol, 0)}"
        )
    
    def reset_daily_counters(self, symbol: Optional[str] = None) -> None:
        """
        Reset daily counters (call at start of new trading day).
        
        Args:
            symbol: Symbol to reset (if None, resets all)
        """
        if symbol:
            self._daily_losses.pop(symbol, None)
            self._daily_trade_count.pop(symbol, None)
            self._last_loss_time.pop(symbol, None)
        else:
            self._daily_losses.clear()
            self._daily_trade_count.clear()
            self._last_loss_time.clear()
        
        logger.info(f"Reset daily counters for {symbol or 'all symbols'}")
    
    def check_spread_gate(
        self,
        symbol: str,
        current_spread: float,
        baseline_spread: Optional[float] = None,
        volatility_regime: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if spread is acceptable for trade execution.
        
        Args:
            symbol: Trading symbol
            current_spread: Current bid-ask spread
            baseline_spread: Baseline/normal spread for this symbol (if None, uses threshold)
            volatility_regime: Detected volatility regime (optional, for adaptive thresholds)
        
        Returns:
            Tuple of (can_trade, reason_if_blocked)
        """
        try:
            # If baseline not provided, use a conservative threshold
            if baseline_spread is None:
                # Estimate baseline from symbol (simplified - in production would use historical data)
                if "BTC" in symbol.upper():
                    baseline_spread = 10.0  # Typical BTC spread
                elif "XAU" in symbol.upper():
                    baseline_spread = 0.5  # Typical Gold spread
                else:  # Forex
                    baseline_spread = 0.0001  # Typical Forex spread
            
            # Calculate threshold
            spread_threshold = baseline_spread * self.SPREAD_MULTIPLIER_THRESHOLD
            
            # In volatile conditions, allow wider spreads (2.0× instead of 1.5×)
            if volatility_regime:
                regime = volatility_regime.get("regime")
                if isinstance(regime, VolatilityRegime):
                    regime_str = regime.value
                elif hasattr(regime, 'value'):
                    regime_str = regime.value
                else:
                    regime_str = str(regime) if regime else "STABLE"
                
                if regime_str == "VOLATILE":
                    spread_threshold = baseline_spread * 2.0  # Wider tolerance in volatile
            
            if current_spread > spread_threshold:
                reason = (
                    f"Spread too wide: {current_spread:.5f} > {spread_threshold:.5f} "
                    f"({baseline_spread:.5f} × {self.SPREAD_MULTIPLIER_THRESHOLD})"
                )
                logger.warning(f"Spread gate blocked trade for {symbol}: {reason}")
                return False, reason
            
            logger.debug(
                f"Spread gate passed for {symbol}: {current_spread:.5f} <= {spread_threshold:.5f}"
            )
            return True, None
            
        except Exception as e:
            logger.error(f"Error checking spread gate: {e}", exc_info=True)
            # Fail open - allow trade if check fails
            return True, None
    
    def calculate_slippage_budget(
        self,
        entry_price: float,
        stop_loss: float,
        direction: str
    ) -> float:
        """
        Calculate maximum acceptable slippage for a trade.
        
        Args:
            entry_price: Intended entry price
            stop_loss: Stop loss price
            direction: "BUY" or "SELL"
        
        Returns:
            Maximum slippage in price units (not percentage)
        """
        try:
            # Calculate risk distance
            if direction.upper() == "BUY":
                risk_distance = entry_price - stop_loss
            else:  # SELL
                risk_distance = stop_loss - entry_price
            
            if risk_distance <= 0:
                logger.warning(f"Invalid risk distance: {risk_distance}")
                return 0.0
            
            # Maximum slippage = 15% of risk (0.15R)
            max_slippage = risk_distance * self.MAX_SLIPPAGE_PCT
            
            logger.debug(
                f"Slippage budget: {max_slippage:.5f} ({self.MAX_SLIPPAGE_PCT * 100:.0f}% of {risk_distance:.5f} risk)"
            )
            return max_slippage
            
        except Exception as e:
            logger.error(f"Error calculating slippage budget: {e}", exc_info=True)
            return 0.0
    
    def check_slippage(
        self,
        intended_price: float,
        actual_fill_price: float,
        direction: str,
        stop_loss: float
    ) -> Tuple[bool, Optional[str], float]:
        """
        Check if actual slippage is within budget.
        
        Args:
            intended_price: Intended entry price
            actual_fill_price: Actual fill price
            direction: "BUY" or "SELL"
            stop_loss: Stop loss price
        
        Returns:
            Tuple of (acceptable, reason_if_unacceptable, slippage_pct_of_risk)
        """
        try:
            # Calculate actual slippage
            if direction.upper() == "BUY":
                slippage = actual_fill_price - intended_price  # Positive = worse
            else:  # SELL
                slippage = intended_price - actual_fill_price  # Positive = worse
            
            # Get slippage budget
            max_slippage = self.calculate_slippage_budget(
                entry_price=intended_price,
                stop_loss=stop_loss,
                direction=direction
            )
            
            # Calculate slippage as % of risk
            if direction.upper() == "BUY":
                risk_distance = intended_price - stop_loss
            else:
                risk_distance = stop_loss - intended_price
            
            slippage_pct_of_risk = (slippage / risk_distance * 100) if risk_distance > 0 else 0
            
            if slippage > max_slippage:
                reason = (
                    f"Slippage exceeds budget: {slippage:.5f} > {max_slippage:.5f} "
                    f"({slippage_pct_of_risk:.1f}% of risk > {self.MAX_SLIPPAGE_PCT * 100:.0f}%)"
                )
                logger.warning(f"Slippage check failed: {reason}")
                return False, reason, slippage_pct_of_risk
            
            logger.info(
                f"Slippage acceptable: {slippage:.5f} ({slippage_pct_of_risk:.1f}% of risk) "
                f"<= budget {max_slippage:.5f}"
            )
            return True, None, slippage_pct_of_risk
            
        except Exception as e:
            logger.error(f"Error checking slippage: {e}", exc_info=True)
            # Fail open - allow trade if check fails
            return True, None, 0.0


def get_volatility_adjusted_lot_size(
    symbol: str,
    entry: float,
    stop_loss: float,
    equity: float,
    volatility_regime: Optional[Dict[str, Any]],
    base_risk_pct: Optional[float] = None,
    tick_value: float = 1.0,
    tick_size: float = 0.01,
    contract_size: float = 100000
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate lot size with volatility-adjusted risk.
    
    This is a convenience function that integrates with the existing lot sizing system.
    
    Args:
        symbol: Trading symbol
        entry: Entry price
        stop_loss: Stop loss price
        equity: Account equity
        volatility_regime: Detected volatility regime data (optional)
        base_risk_pct: Base risk percentage (if None, uses symbol default)
        tick_value: MT5 tick value
        tick_size: MT5 tick size
        contract_size: MT5 contract size
    
    Returns:
        Tuple of (lot_size, metadata_dict)
    """
    from config.lot_sizing import calculate_lot_from_risk, get_default_risk_pct
    
    # Get base risk if not provided
    if base_risk_pct is None:
        base_risk_pct = get_default_risk_pct(symbol)
    
    # Adjust risk based on volatility regime if available
    adjusted_risk_pct = base_risk_pct
    adjustment_reason = "No volatility regime data"
    
    if volatility_regime:
        risk_manager = VolatilityRiskManager()
        adjusted_risk_pct = risk_manager.calculate_volatility_adjusted_risk_pct(
            volatility_regime=volatility_regime,
            base_risk_pct=base_risk_pct
        )
        
        regime = volatility_regime.get("regime")
        if isinstance(regime, VolatilityRegime):
            regime_str = regime.value
        elif hasattr(regime, 'value'):
            regime_str = regime.value
        else:
            regime_str = str(regime) if regime else "UNKNOWN"
        
        confidence = volatility_regime.get("confidence", 0)
        adjustment_reason = f"{regime_str} regime (confidence: {confidence:.1f}%)"
    
    # Calculate lot size using adjusted risk
    lot_size = calculate_lot_from_risk(
        symbol=symbol,
        entry=entry,
        stop_loss=stop_loss,
        equity=equity,
        risk_pct=adjusted_risk_pct,
        tick_value=tick_value,
        tick_size=tick_size,
        contract_size=contract_size
    )
    
    metadata = {
        "base_risk_pct": base_risk_pct,
        "adjusted_risk_pct": adjusted_risk_pct,
        "adjustment_reason": adjustment_reason,
        "volatility_regime": volatility_regime.get("regime").value if volatility_regime and volatility_regime.get("regime") else None
    }
    
    logger.info(
        f"Volatility-adjusted lot sizing for {symbol}: "
        f"Base risk {base_risk_pct:.2f}% -> Adjusted {adjusted_risk_pct:.2f}% "
        f"({adjustment_reason}), Lot size: {lot_size:.2f}"
    )
    
    return lot_size, metadata

