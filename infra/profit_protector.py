"""
Intelligent Profit Protection Module
Protects profitable trades using technical analysis warning signals.

Uses a 7-signal framework:
1. Market Structure Shift (CHOCH) - CRITICAL
2. Opposite Order Flow (Engulfing) - CRITICAL
3. Liquidity Target + Rejection - MAJOR
4. Momentum Divergence - MAJOR
5. Dynamic S/R Break - MAJOR
6. Momentum Loss - MINOR
7. Session/Time Shift - MINOR

Scoring System:
- Total Score ≥ 5: EXIT immediately
- Total Score 2-4: TIGHTEN to structure
- Total Score < 2: MONITOR (keep trade)
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class WarningSignal:
    """Individual warning signal."""
    name: str
    weight: int  # 1-3 (1=minor, 2=major, 3=critical)
    description: str
    timestamp: datetime


@dataclass
class ProfitProtectionDecision:
    """Decision on how to protect a profitable trade."""
    action: str  # "monitor", "tighten", "exit"
    reason: str
    warnings: List[WarningSignal]
    total_score: int
    new_sl: Optional[float] = None
    confidence: float = 0.0


class ProfitProtector:
    """
    Intelligent profit protection using technical analysis.
    Only applies to PROFITABLE trades (r_multiple > 0).
    """
    
    def __init__(self):
        # Track last tighten time per ticket to prevent spam
        self._last_tighten_time: Dict[int, float] = {}
        self._tighten_cooldown_seconds = 300  # 5 minutes cooldown
        """Initialize profit protector."""
        logger.info("ProfitProtector initialized - Technical analysis-based profit protection")
    
    def clear_closed_position(self, ticket: int):
        """Remove closed position from cooldown tracker."""
        if ticket in self._last_tighten_time:
            del self._last_tighten_time[ticket]
            logger.debug(f"Cleared cooldown tracker for closed ticket {ticket}")
    
    def analyze_profit_protection(
        self,
        position: Any,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame] = None,
        order_flow: Optional[Dict[str, Any]] = None,
        r_multiple: float = 0.0
    ) -> Optional[ProfitProtectionDecision]:
        """
        Analyze if a profitable trade needs protection.
        
        Args:
            position: MT5 position object
            features: Market features (RSI, MACD, ADX, ATR, structure, etc.)
            bars: Optional OHLCV bars for advanced analysis
            order_flow: Optional order flow data (whale orders, liquidity voids)
            r_multiple: Current R-multiple (profit/loss ratio)
            
        Returns:
            ProfitProtectionDecision if action needed, None otherwise
        """
        # Only protect PROFITABLE trades
        if r_multiple <= 0:
            return None
        
        # Check cooldown to prevent spam tightening
        ticket = position.ticket
        current_time = time.time()
        last_tighten = self._last_tighten_time.get(ticket, 0)
        time_since_last_tighten = current_time - last_tighten
        
        if time_since_last_tighten < self._tighten_cooldown_seconds:
            logger.debug(f"⏸️ Profit protection cooldown for {position.symbol} ticket {ticket} "
                        f"({int(self._tighten_cooldown_seconds - time_since_last_tighten)}s remaining)")
            return None  # Skip analysis during cooldown
        
        direction = "buy" if position.type == mt5.ORDER_TYPE_BUY else "sell"
        entry_price = position.price_open
        current_price = position.price_current
        stop_loss = position.sl
        take_profit = position.tp
        
        warnings = []
        
        # ============================================================================
        # 1. CRITICAL: Market Structure Shift (CHOCH)
        # ============================================================================
        choch_detected = self._detect_structure_break(direction, features, bars)
        if choch_detected:
            warnings.append(WarningSignal(
                name="CHOCH",
                weight=3,
                description="Market structure break detected - trend weakening",
                timestamp=datetime.now()
            ))
            logger.warning(f"🚨 CHOCH detected for {position.symbol} - structure break!")
        
        # ============================================================================
        # 2. CRITICAL: Opposite Order Flow (Engulfing)
        # ============================================================================
        engulfing_detected = self._detect_opposite_engulfing(direction, features, bars)
        if engulfing_detected:
            warnings.append(WarningSignal(
                name="Engulfing",
                weight=3,
                description="Large opposite candle detected - reversal signal",
                timestamp=datetime.now()
            ))
            logger.warning(f"🚨 Opposite engulfing detected for {position.symbol}!")
        
        # ============================================================================
        # 3. MAJOR: Liquidity Target + Rejection
        # ============================================================================
        liquidity_rejection = self._detect_liquidity_rejection(
            position, current_price, take_profit, features, bars
        )
        if liquidity_rejection:
            warnings.append(WarningSignal(
                name="Liquidity rejection",
                weight=2,
                description="Price hit liquidity target and rejected",
                timestamp=datetime.now()
            ))
            logger.warning(f"⚠️ Liquidity rejection for {position.symbol}")
        
        # ============================================================================
        # 4. MAJOR: Momentum Divergence
        # ============================================================================
        divergence_detected = self._detect_divergence(direction, features, bars)
        if divergence_detected:
            warnings.append(WarningSignal(
                name="Divergence",
                weight=2,
                description="RSI/MACD divergence - momentum weakening",
                timestamp=datetime.now()
            ))
            logger.warning(f"⚠️ Momentum divergence for {position.symbol}")
        
        # ============================================================================
        # 5. MAJOR: Dynamic S/R Break
        # ============================================================================
        sr_break = self._detect_sr_break(direction, features, bars)
        if sr_break:
            warnings.append(WarningSignal(
                name="S/R break",
                weight=2,
                description="Dynamic support/resistance broken",
                timestamp=datetime.now()
            ))
            logger.warning(f"⚠️ Dynamic S/R break for {position.symbol}")
        
        # ============================================================================
        # 6. MINOR: Momentum Loss
        # ============================================================================
        momentum_loss = self._detect_momentum_loss(features, bars)
        if momentum_loss:
            warnings.append(WarningSignal(
                name="Momentum loss",
                weight=1,
                description="ATR dropping, smaller candles, weak push",
                timestamp=datetime.now()
            ))
            logger.info(f"ℹ️ Momentum loss for {position.symbol}")
        
        # ============================================================================
        # 7. MINOR: Session/Time Shift
        # ============================================================================
        session_risk = self._detect_session_shift(position)
        if session_risk:
            warnings.append(WarningSignal(
                name="Session shift",
                weight=1,
                description="Risky session change approaching",
                timestamp=datetime.now()
            ))
            logger.info(f"ℹ️ Session shift risk for {position.symbol}")
        
        # ============================================================================
        # 8. MINOR: Order Flow Warnings (Whale Orders)
        # ============================================================================
        if order_flow:
            whale_warning = self._detect_whale_orders(direction, order_flow)
            if whale_warning:
                warnings.append(WarningSignal(
                    name="Whale orders",
                    weight=1,
                    description="Large institutional orders detected opposite direction",
                    timestamp=datetime.now()
                ))
                logger.info(f"ℹ️ Whale order warning for {position.symbol}")
        
        # ============================================================================
        # Calculate Total Score
        # ============================================================================
        total_score = sum(w.weight for w in warnings)
        
        if total_score == 0:
            return None  # No warnings, keep trade as is
        
        # ============================================================================
        # Decision Logic
        # ============================================================================
        
        # CRITICAL: Exit immediately (score ≥ 5)
        if total_score >= 5:
            # Record timestamp for cooldown (even though we're exiting)
            self._last_tighten_time[ticket] = current_time
            
            return ProfitProtectionDecision(
                action="exit",
                reason=f"Profit protect: {', '.join([w.name for w in warnings])}",
                warnings=warnings,
                total_score=total_score,
                confidence=0.85
            )
        
        # MAJOR: Tighten to structure (score 2-4)
        elif total_score >= 2:
            new_sl = self._calculate_structure_sl(
                direction, entry_price, current_price, stop_loss, features, bars
            )
            
            # Only tighten if new SL is significantly better than current
            min_improvement = features.get('atr', 0.001) * 0.3  # 30% of ATR
            sl_improvement = abs(new_sl - stop_loss)
            
            if sl_improvement < min_improvement:
                logger.debug(f"⏸️ SL improvement too small for {position.symbol} ticket {ticket}: "
                           f"{sl_improvement:.5f} < {min_improvement:.5f} (30% ATR)")
                return None  # Skip tightening if improvement is negligible
            
            # Record timestamp for cooldown
            self._last_tighten_time[ticket] = current_time
            
            return ProfitProtectionDecision(
                action="tighten",
                reason=f"Profit protect: tighten ({', '.join([w.name for w in warnings])})",
                warnings=warnings,
                total_score=total_score,
                new_sl=new_sl,
                confidence=0.70
            )
        
        # MINOR: Monitor (score 1)
        else:
            return ProfitProtectionDecision(
                action="monitor",
                reason=f"Profit protect: monitor ({', '.join([w.name for w in warnings])})",
                warnings=warnings,
                total_score=total_score,
                confidence=0.50
            )
    
    # ============================================================================
    # Detection Methods
    # ============================================================================
    
    def _detect_structure_break(
        self,
        direction: str,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> bool:
        """
        Detect CHOCH (Change of Character) - structure break.
        
        For BUY: Price makes a lower low (breaks previous higher low)
        For SELL: Price makes a higher high (breaks previous lower high)
        """
        # Check Binance enrichment structure
        binance_structure = features.get('binance_structure', features.get('price_structure', 'UNKNOWN'))
        
        if direction == "buy":
            # For long, watch for BEARISH structure
            if binance_structure in ['BEARISH', 'BREAKDOWN']:
                return True
        else:
            # For short, watch for BULLISH structure
            if binance_structure in ['BULLISH', 'BREAKOUT']:
                return True
        
        # Fallback: Check for structure invalidation
        structure_invalidations = features.get('structure_invalidations', 0)
        if structure_invalidations >= 2:
            return True
        
        # Check bars for actual higher high/lower low breaks
        if bars is not None and len(bars) >= 10:
            try:
                highs = bars['high'].values[-10:]
                lows = bars['low'].values[-10:]
                
                if direction == "buy":
                    # Check if recent low broke previous higher low
                    recent_low = lows[-1]
                    prev_lows = lows[-5:-1]
                    if len(prev_lows) > 0 and recent_low < min(prev_lows):
                        return True
                else:
                    # Check if recent high broke previous lower high
                    recent_high = highs[-1]
                    prev_highs = highs[-5:-1]
                    if len(prev_highs) > 0 and recent_high > max(prev_highs):
                        return True
            except Exception as e:
                logger.debug(f"Structure break detection error: {e}")
        
        return False
    
    def _detect_opposite_engulfing(
        self,
        direction: str,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> bool:
        """
        Detect large opposite engulfing candle.
        """
        if bars is None or len(bars) < 2:
            return False
        
        try:
            # Get last 2 candles
            prev_candle = bars.iloc[-2]
            curr_candle = bars.iloc[-1]
            
            prev_body = abs(prev_candle['close'] - prev_candle['open'])
            curr_body = abs(curr_candle['close'] - curr_candle['open'])
            
            # Check if current candle is opposite direction and larger
            if direction == "buy":
                # Look for bearish engulfing
                is_bearish = curr_candle['close'] < curr_candle['open']
                is_engulfing = curr_body > prev_body * 1.5
                if is_bearish and is_engulfing:
                    return True
            else:
                # Look for bullish engulfing
                is_bullish = curr_candle['close'] > curr_candle['open']
                is_engulfing = curr_body > prev_body * 1.5
                if is_bullish and is_engulfing:
                    return True
        except Exception as e:
            logger.debug(f"Engulfing detection error: {e}")
        
        return False
    
    def _detect_liquidity_rejection(
        self,
        position: Any,
        current_price: float,
        take_profit: float,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> bool:
        """
        Detect if price hit liquidity target and rejected.
        """
        if take_profit == 0:
            return False
        
        # Check if close to TP (within 20%)
        distance_to_tp = abs(current_price - take_profit)
        total_move = abs(take_profit - position.price_open)
        
        if total_move > 0:
            progress = 1.0 - (distance_to_tp / total_move)
            if progress >= 0.80:  # 80% to TP
                # Check for rejection (long wick)
                if bars is not None and len(bars) >= 1:
                    try:
                        last_candle = bars.iloc[-1]
                        body = abs(last_candle['close'] - last_candle['open'])
                        
                        if position.type == mt5.ORDER_TYPE_BUY:
                            upper_wick = last_candle['high'] - max(last_candle['open'], last_candle['close'])
                            if upper_wick > body * 2:  # Upper wick > 2x body
                                return True
                        else:
                            lower_wick = min(last_candle['open'], last_candle['close']) - last_candle['low']
                            if lower_wick > body * 2:  # Lower wick > 2x body
                                return True
                    except Exception as e:
                        logger.debug(f"Liquidity rejection detection error: {e}")
        
        return False
    
    def _detect_divergence(
        self,
        direction: str,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> bool:
        """
        Detect RSI/MACD divergence.
        """
        # Check if exit detector already flagged divergence
        rsi_div = features.get('rsi_divergence', False)
        macd_div = features.get('macd_divergence', False)
        
        if rsi_div or macd_div:
            return True
        
        # Check RSI manually
        rsi = features.get('rsi', 50)
        if direction == "buy" and rsi > 70:
            # Overbought divergence risk
            return True
        elif direction == "sell" and rsi < 30:
            # Oversold divergence risk
            return True
        
        return False
    
    def _detect_sr_break(
        self,
        direction: str,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> bool:
        """
        Detect dynamic S/R break (EMA, trendline, VWAP).
        """
        # Check EMA breaks
        ema_20 = features.get('ema_20')
        ema_50 = features.get('ema_50')
        
        if bars is not None and len(bars) >= 1:
            try:
                current_close = bars.iloc[-1]['close']
                
                if direction == "buy":
                    # For long, watch for break below EMA
                    if ema_20 and current_close < ema_20:
                        return True
                    if ema_50 and current_close < ema_50:
                        return True
                else:
                    # For short, watch for break above EMA
                    if ema_20 and current_close > ema_20:
                        return True
                    if ema_50 and current_close > ema_50:
                        return True
            except Exception as e:
                logger.debug(f"S/R break detection error: {e}")
        
        return False
    
    def _detect_momentum_loss(
        self,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> bool:
        """
        Detect momentum loss (ATR drop, smaller candles, weak push).
        """
        # Check Binance momentum quality
        momentum_quality = features.get('momentum_quality', 'UNKNOWN')
        if momentum_quality in ['POOR', 'WEAK']:
            return True
        
        # Check ATR drop
        atr = features.get('atr', 0)
        atr_prev = features.get('atr_prev', atr)
        
        if atr_prev > 0:
            atr_change = (atr - atr_prev) / atr_prev
            if atr_change < -0.15:  # 15% ATR drop
                return True
        
        # Check ADX weakness
        adx = features.get('adx', 0)
        if adx < 20:  # Weak trend
            return True
        
        return False
    
    def _detect_session_shift(self, position: Any) -> bool:
        """
        Detect risky session shifts (London close, Friday, etc.).
        """
        now = datetime.utcnow()
        hour = now.hour
        weekday = now.weekday()  # 0=Monday, 6=Sunday
        
        # Friday afternoon (risky for holding)
        if weekday == 4 and hour >= 14:  # Friday after 2 PM UTC
            return True
        
        # London close (15:00-16:00 UTC) - profit taking
        if 15 <= hour < 16:
            return True
        
        return False
    
    def _detect_whale_orders(
        self,
        direction: str,
        order_flow: Dict[str, Any]
    ) -> bool:
        """
        Detect large whale orders in opposite direction.
        """
        whale_count = order_flow.get('whale_count', 0)
        order_flow_signal = order_flow.get('order_flow_signal', 'NEUTRAL')
        
        if direction == "buy" and order_flow_signal == "BEARISH" and whale_count > 0:
            return True
        elif direction == "sell" and order_flow_signal == "BULLISH" and whale_count > 0:
            return True
        
        return False
    
    def _calculate_structure_sl(
        self,
        direction: str,
        entry_price: float,
        current_price: float,
        current_sl: float,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> float:
        """
        Calculate structure-based stop loss for tightening.
        
        Strategy:
        1. Find recent swing low/high
        2. Place SL behind it with small buffer
        3. Ensure it's better than current SL (closer to entry)
        """
        atr = features.get('atr', 0.001)
        buffer = atr * 0.5  # Half ATR buffer
        
        new_sl = current_sl  # Default to current SL
        
        if bars is not None and len(bars) >= 10:
            try:
                if direction == "buy":
                    # For long, find recent swing low
                    lows = bars['low'].values[-10:]
                    recent_swing_low = min(lows[-5:])  # Last 5 bars
                    proposed_sl = recent_swing_low - buffer
                    
                    # Ensure it's better than current SL (higher)
                    if proposed_sl > current_sl:
                        new_sl = proposed_sl
                    else:
                        # Move to breakeven + buffer
                        new_sl = entry_price - buffer
                else:
                    # For short, find recent swing high
                    highs = bars['high'].values[-10:]
                    recent_swing_high = max(highs[-5:])  # Last 5 bars
                    proposed_sl = recent_swing_high + buffer
                    
                    # Ensure it's better than current SL (lower)
                    if proposed_sl < current_sl:
                        new_sl = proposed_sl
                    else:
                        # Move to breakeven + buffer
                        new_sl = entry_price + buffer
            except Exception as e:
                logger.debug(f"Structure SL calculation error: {e}")
                # Fallback: breakeven + buffer
                if direction == "buy":
                    new_sl = entry_price - buffer
                else:
                    new_sl = entry_price + buffer
        else:
            # No bars available, use breakeven + buffer
            if direction == "buy":
                new_sl = entry_price - buffer
            else:
                new_sl = entry_price + buffer
        
        return new_sl

