"""
Loss Cut Detector - Systematic Loss Management
Detects when to cut losing trades based on professional criteria, not emotion.

Uses 7 categories to determine when "the reason for entry is no longer true":
1. Structural Invalidation - Setup's market structure breaks
2. Momentum Failure - Loss of energy/trend
3. Volatility Expansion - Regime shift against position
4. Confluence Breakdown - Indicators no longer agree
5. Time-Based Invalidation - Trade not performing
6. Risk/Reward & Equity - Portfolio protection
7. Sentiment/News Shock - External macro reversal

Uses "3-Strikes Rule": If 3 out of 7 categories turn negative → exit immediately
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class LossCutCategory(str, Enum):
    """Loss cut trigger categories."""
    STRUCTURE = "structure"  # Structural invalidation
    MOMENTUM = "momentum"  # Momentum failure
    VOLATILITY = "volatility"  # Volatility expansion against position
    CONFLUENCE = "confluence"  # Indicator agreement breakdown
    TIME = "time"  # Trade stagnation
    RISK = "risk"  # Risk/equity limits
    SENTIMENT = "sentiment"  # News/macro shock


class LossCutUrgency(str, Enum):
    """Loss cut urgency levels."""
    NONE = "none"  # No cut needed
    WARNING = "warning"  # 1 strike
    CAUTION = "caution"  # 2 strikes
    CRITICAL = "critical"  # 3+ strikes - cut immediately


@dataclass
class LossCutSignal:
    """Individual loss cut signal."""
    category: LossCutCategory
    severity: float  # 0.0-1.0
    message: str
    timestamp: datetime


@dataclass
class LossCutAnalysis:
    """Complete loss cut analysis for a position."""
    urgency: LossCutUrgency
    strikes: int  # Number of categories triggered (0-7)
    confidence: float  # 0.0-1.0
    signals: List[LossCutSignal]
    
    # Category breakdown
    structure_broken: bool
    momentum_failed: bool
    volatility_spike: bool
    confluence_broken: bool
    time_expired: bool
    risk_exceeded: bool
    sentiment_shock: bool
    
    # Recommended action
    action: str  # "hold", "tighten_sl", "cut_50", "cut_full"
    rationale: str
    
    # Trade metrics
    unrealized_r: float
    time_in_trade_minutes: int


class LossCutDetector:
    """
    Detects when to cut losing trades systematically.
    
    This class analyzes positions in drawdown to determine if the
    original trade thesis is still valid or should be exited.
    """
    
    def __init__(
        self,
        # Structure thresholds
        structure_break_confirm_bars: int = 1,
        
        # Momentum thresholds
        adx_weak_threshold: float = 20.0,
        rsi_failure_threshold: float = 10.0,  # RSI drop from peak
        macd_flip_confirm: bool = True,
        
        # Volatility thresholds
        atr_spike_multiplier: float = 2.0,  # 2x ATR = volatility break
        bb_expansion_threshold: float = 1.5,
        
        # Confluence thresholds
        min_confluence_indicators: int = 3,  # Min indicators for confluence
        confluence_break_threshold: float = 0.67,  # 67% must break
        
        # Time thresholds (minutes)
        scalp_timeout: int = 15,  # 3-5 M5 candles
        intraday_timeout: int = 240,  # 4 hours
        swing_timeout: int = 480,  # 8 hours
        
        # Risk thresholds
        max_loss_r: float = -1.5,  # Max -1.5R before forced cut
        max_daily_loss_pct: float = 0.05,  # 5% daily loss limit
        
        # 3-Strikes Rule
        strikes_for_warning: int = 1,
        strikes_for_caution: int = 2,
        strikes_for_critical: int = 3,
    ):
        """
        Initialize loss cut detector.
        
        Args:
            structure_break_confirm_bars: Bars to confirm structure break
            adx_weak_threshold: ADX below this = no trend
            rsi_failure_threshold: RSI drop from peak for failure
            macd_flip_confirm: Require MACD flip confirmation
            atr_spike_multiplier: Candle size vs ATR for volatility break
            bb_expansion_threshold: BB width expansion for regime shift
            min_confluence_indicators: Min indicators for confluence check
            confluence_break_threshold: % of indicators that must break
            scalp_timeout: Minutes before scalp trade is stagnant
            intraday_timeout: Minutes before intraday trade is stagnant
            swing_timeout: Minutes before swing trade is stagnant
            max_loss_r: Max loss in R before forced cut
            max_daily_loss_pct: Max daily loss % before forced cut
            strikes_for_warning: Strikes for warning level
            strikes_for_caution: Strikes for caution level
            strikes_for_critical: Strikes for critical level
        """
        self.structure_break_confirm_bars = structure_break_confirm_bars
        self.adx_weak_threshold = adx_weak_threshold
        self.rsi_failure_threshold = rsi_failure_threshold
        self.macd_flip_confirm = macd_flip_confirm
        self.atr_spike_multiplier = atr_spike_multiplier
        self.bb_expansion_threshold = bb_expansion_threshold
        self.min_confluence_indicators = min_confluence_indicators
        self.confluence_break_threshold = confluence_break_threshold
        self.scalp_timeout = scalp_timeout
        self.intraday_timeout = intraday_timeout
        self.swing_timeout = swing_timeout
        self.max_loss_r = max_loss_r
        self.max_daily_loss_pct = max_daily_loss_pct
        self.strikes_for_warning = strikes_for_warning
        self.strikes_for_caution = strikes_for_caution
        self.strikes_for_critical = strikes_for_critical
        
        logger.info("LossCutDetector initialized")
    
    def analyze_loss_cut(
        self,
        direction: str,  # "buy" or "sell"
        entry_price: float,
        entry_time: datetime,
        current_price: float,
        current_sl: float,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame] = None,
        trade_type: str = "intraday",  # "scalp", "intraday", "swing"
        daily_pnl_pct: float = 0.0  # Current daily P&L %
    ) -> LossCutAnalysis:
        """
        Analyze whether a losing trade should be cut.
        
        Args:
            direction: Trade direction ("buy" or "sell")
            entry_price: Entry price
            entry_time: Entry timestamp
            current_price: Current market price
            current_sl: Current stop loss
            features: Market features (RSI, MACD, ADX, ATR, etc.)
            bars: Optional OHLCV bars for advanced analysis
            trade_type: Trade type ("scalp", "intraday", "swing")
            daily_pnl_pct: Current daily P&L percentage
            
        Returns:
            LossCutAnalysis with urgency, strikes, and recommended action
        """
        signals = []
        
        # Calculate unrealized R
        risk = abs(entry_price - current_sl) if current_sl > 0 else 0
        if direction == "buy":
            unrealized_profit = current_price - entry_price
        else:
            unrealized_profit = entry_price - current_price
        
        unrealized_r = unrealized_profit / risk if risk > 0 else 0.0
        
        # Calculate time in trade
        time_in_trade = datetime.now() - entry_time
        time_in_trade_minutes = int(time_in_trade.total_seconds() / 60)
        
        # Only analyze losing trades
        if unrealized_r >= 0:
            return LossCutAnalysis(
                urgency=LossCutUrgency.NONE,
                strikes=0,
                confidence=0.0,
                signals=[],
                structure_broken=False,
                momentum_failed=False,
                volatility_spike=False,
                confluence_broken=False,
                time_expired=False,
                risk_exceeded=False,
                sentiment_shock=False,
                action="hold",
                rationale="Position in profit - no loss cut needed",
                unrealized_r=unrealized_r,
                time_in_trade_minutes=time_in_trade_minutes
            )
        
        # 1. Check Structural Invalidation
        structure_signals = self._check_structure_break(direction, current_price, features, bars)
        signals.extend(structure_signals)
        
        # 2. Check Momentum Failure
        momentum_signals = self._check_momentum_failure(direction, features, bars)
        signals.extend(momentum_signals)
        
        # 3. Check Volatility Expansion
        volatility_signals = self._check_volatility_spike(direction, current_price, features, bars)
        signals.extend(volatility_signals)
        
        # 4. Check Confluence Breakdown
        confluence_signals = self._check_confluence_breakdown(direction, features)
        signals.extend(confluence_signals)
        
        # 5. Check Time-Based Invalidation
        time_signals = self._check_time_expiration(trade_type, time_in_trade_minutes, unrealized_r)
        signals.extend(time_signals)
        
        # 6. Check Risk/Equity Limits
        risk_signals = self._check_risk_limits(unrealized_r, daily_pnl_pct)
        signals.extend(risk_signals)
        
        # 7. Check Sentiment/News Shock (placeholder - would need news feed)
        sentiment_signals = self._check_sentiment_shock(features)
        signals.extend(sentiment_signals)
        
        # Count strikes (unique categories triggered)
        categories_triggered = set(s.category for s in signals)
        strikes = len(categories_triggered)
        
        # Determine category flags
        structure_broken = LossCutCategory.STRUCTURE in categories_triggered
        momentum_failed = LossCutCategory.MOMENTUM in categories_triggered
        volatility_spike = LossCutCategory.VOLATILITY in categories_triggered
        confluence_broken = LossCutCategory.CONFLUENCE in categories_triggered
        time_expired = LossCutCategory.TIME in categories_triggered
        risk_exceeded = LossCutCategory.RISK in categories_triggered
        sentiment_shock = LossCutCategory.SENTIMENT in categories_triggered
        
        # Determine urgency based on 3-Strikes Rule
        urgency, action, rationale = self._determine_action(
            strikes, unrealized_r, structure_broken, risk_exceeded,
            categories_triggered, signals
        )
        
        # Calculate confidence
        confidence = self._calculate_confidence(signals, strikes, unrealized_r)
        
        return LossCutAnalysis(
            urgency=urgency,
            strikes=strikes,
            confidence=confidence,
            signals=signals,
            structure_broken=structure_broken,
            momentum_failed=momentum_failed,
            volatility_spike=volatility_spike,
            confluence_broken=confluence_broken,
            time_expired=time_expired,
            risk_exceeded=risk_exceeded,
            sentiment_shock=sentiment_shock,
            action=action,
            rationale=rationale,
            unrealized_r=unrealized_r,
            time_in_trade_minutes=time_in_trade_minutes
        )
    
    def _check_structure_break(
        self,
        direction: str,
        current_price: float,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> List[LossCutSignal]:
        """Check for structural invalidation."""
        signals = []
        
        # EMA20 break (momentum spine)
        ema20 = features.get("ema20", 0)
        if ema20 > 0:
            if direction == "buy" and current_price < ema20:
                signals.append(LossCutSignal(
                    category=LossCutCategory.STRUCTURE,
                    severity=0.9,
                    message=f"Price broke below EMA20 ({ema20:.2f}) - structure invalid",
                    timestamp=datetime.now()
                ))
            elif direction == "sell" and current_price > ema20:
                signals.append(LossCutSignal(
                    category=LossCutCategory.STRUCTURE,
                    severity=0.9,
                    message=f"Price broke above EMA20 ({ema20:.2f}) - structure invalid",
                    timestamp=datetime.now()
                ))
        
        # Swing low/high break (if bars available)
        if bars is not None and len(bars) >= 5:
            recent_bars = bars.tail(5)
            if direction == "buy":
                swing_low = recent_bars['low'].min()
                if current_price < swing_low:
                    signals.append(LossCutSignal(
                        category=LossCutCategory.STRUCTURE,
                        severity=1.0,
                        message=f"Price broke below swing low ({swing_low:.2f}) - trend invalidated",
                        timestamp=datetime.now()
                    ))
            else:  # sell
                swing_high = recent_bars['high'].max()
                if current_price > swing_high:
                    signals.append(LossCutSignal(
                        category=LossCutCategory.STRUCTURE,
                        severity=1.0,
                        message=f"Price broke above swing high ({swing_high:.2f}) - trend invalidated",
                        timestamp=datetime.now()
                    ))
        
        return signals
    
    def _check_momentum_failure(
        self,
        direction: str,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> List[LossCutSignal]:
        """Check for momentum failure."""
        signals = []
        
        # ADX weak (no trend)
        adx = features.get("adx", 0)
        if adx > 0 and adx < self.adx_weak_threshold:
            signals.append(LossCutSignal(
                category=LossCutCategory.MOMENTUM,
                severity=0.7,
                message=f"ADX dropped to {adx:.1f} (below {self.adx_weak_threshold}) - no trend",
                timestamp=datetime.now()
            ))
        
        # MACD histogram flip
        macd_hist = features.get("macd_hist", 0)
        if self.macd_flip_confirm:
            if direction == "buy" and macd_hist < 0:
                signals.append(LossCutSignal(
                    category=LossCutCategory.MOMENTUM,
                    severity=0.8,
                    message=f"MACD histogram flipped negative ({macd_hist:.4f}) - momentum reversed",
                    timestamp=datetime.now()
                ))
            elif direction == "sell" and macd_hist > 0:
                signals.append(LossCutSignal(
                    category=LossCutCategory.MOMENTUM,
                    severity=0.8,
                    message=f"MACD histogram flipped positive ({macd_hist:.4f}) - momentum reversed",
                    timestamp=datetime.now()
                ))
        
        # RSI failure (if bars available)
        if bars is not None and 'rsi' in bars.columns and len(bars) >= 5:
            recent_rsi = bars['rsi'].tail(5)
            rsi_peak = recent_rsi.max() if direction == "buy" else recent_rsi.min()
            rsi_current = recent_rsi.iloc[-1]
            
            if direction == "buy" and (rsi_peak - rsi_current) > self.rsi_failure_threshold:
                signals.append(LossCutSignal(
                    category=LossCutCategory.MOMENTUM,
                    severity=0.7,
                    message=f"RSI dropped {rsi_peak - rsi_current:.1f} points from peak - momentum fading",
                    timestamp=datetime.now()
                ))
            elif direction == "sell" and (rsi_current - rsi_peak) > self.rsi_failure_threshold:
                signals.append(LossCutSignal(
                    category=LossCutCategory.MOMENTUM,
                    severity=0.7,
                    message=f"RSI rose {rsi_current - rsi_peak:.1f} points from low - momentum fading",
                    timestamp=datetime.now()
                ))
        
        return signals
    
    def _check_volatility_spike(
        self,
        direction: str,
        current_price: float,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> List[LossCutSignal]:
        """Check for volatility expansion against position."""
        signals = []
        
        atr = features.get("atr_14", 0)
        
        # Check last candle size vs ATR
        if bars is not None and len(bars) >= 2 and atr > 0:
            last_candle = bars.iloc[-1]
            candle_range = abs(last_candle['high'] - last_candle['low'])
            
            if candle_range > (atr * self.atr_spike_multiplier):
                # Check if candle is against our position
                candle_direction = "bearish" if last_candle['close'] < last_candle['open'] else "bullish"
                
                if (direction == "buy" and candle_direction == "bearish") or \
                   (direction == "sell" and candle_direction == "bullish"):
                    signals.append(LossCutSignal(
                        category=LossCutCategory.VOLATILITY,
                        severity=1.0,
                        message=f"Volatility spike against position: {candle_range:.2f} ({candle_range/atr:.1f}x ATR) - regime shift",
                        timestamp=datetime.now()
                    ))
        
        # Bollinger Band expansion
        bb_upper = features.get("bb_upper", 0)
        bb_lower = features.get("bb_lower", 0)
        bb_mid = features.get("bb_mid", 0)
        
        if bb_upper > 0 and bb_lower > 0 and bb_mid > 0:
            bb_width = bb_upper - bb_lower
            bb_width_prev = features.get("bb_width_prev", bb_width)
            
            if bb_width_prev > 0 and (bb_width / bb_width_prev) > self.bb_expansion_threshold:
                signals.append(LossCutSignal(
                    category=LossCutCategory.VOLATILITY,
                    severity=0.8,
                    message=f"Bollinger Bands expanding {(bb_width/bb_width_prev - 1)*100:.1f}% - volatility regime change",
                    timestamp=datetime.now()
                ))
        
        return signals
    
    def _check_confluence_breakdown(
        self,
        direction: str,
        features: Dict[str, Any]
    ) -> List[LossCutSignal]:
        """Check for confluence breakdown (indicators no longer agree)."""
        signals = []
        
        # Check key indicators
        indicators_checked = 0
        indicators_broken = 0
        
        # RSI
        rsi = features.get("rsi", 50)
        if rsi > 0:
            indicators_checked += 1
            if direction == "buy" and rsi < 45:
                indicators_broken += 1
            elif direction == "sell" and rsi > 55:
                indicators_broken += 1
        
        # EMA20
        ema20 = features.get("ema20", 0)
        current_price = features.get("price", 0)
        if ema20 > 0 and current_price > 0:
            indicators_checked += 1
            if direction == "buy" and current_price < ema20:
                indicators_broken += 1
            elif direction == "sell" and current_price > ema20:
                indicators_broken += 1
        
        # ADX
        adx = features.get("adx", 0)
        if adx > 0:
            indicators_checked += 1
            if adx < 25:
                indicators_broken += 1
        
        # MACD
        macd_hist = features.get("macd_hist", 0)
        if macd_hist != 0:
            indicators_checked += 1
            if direction == "buy" and macd_hist < 0:
                indicators_broken += 1
            elif direction == "sell" and macd_hist > 0:
                indicators_broken += 1
        
        # Check if confluence is broken
        if indicators_checked >= self.min_confluence_indicators:
            break_ratio = indicators_broken / indicators_checked
            if break_ratio >= self.confluence_break_threshold:
                signals.append(LossCutSignal(
                    category=LossCutCategory.CONFLUENCE,
                    severity=break_ratio,
                    message=f"Confluence breakdown: {indicators_broken}/{indicators_checked} indicators against position ({break_ratio*100:.0f}%)",
                    timestamp=datetime.now()
                ))
        
        return signals
    
    def _check_time_expiration(
        self,
        trade_type: str,
        time_in_trade_minutes: int,
        unrealized_r: float
    ) -> List[LossCutSignal]:
        """Check for time-based invalidation (trade not performing)."""
        signals = []
        
        # Determine timeout based on trade type
        timeout_map = {
            "scalp": self.scalp_timeout,
            "intraday": self.intraday_timeout,
            "swing": self.swing_timeout
        }
        timeout = timeout_map.get(trade_type, self.intraday_timeout)
        
        # If trade is in drawdown and time expired
        if time_in_trade_minutes > timeout and unrealized_r < -0.3:
            signals.append(LossCutSignal(
                category=LossCutCategory.TIME,
                severity=0.6,
                message=f"Trade stagnant for {time_in_trade_minutes} min (timeout: {timeout} min) with {unrealized_r:.2f}R loss - not performing",
                timestamp=datetime.now()
            ))
        
        return signals
    
    def _check_risk_limits(
        self,
        unrealized_r: float,
        daily_pnl_pct: float
    ) -> List[LossCutSignal]:
        """Check for risk/equity limit breaches."""
        signals = []
        
        # Max loss per trade
        if unrealized_r < self.max_loss_r:
            signals.append(LossCutSignal(
                category=LossCutCategory.RISK,
                severity=1.0,
                message=f"Position loss {unrealized_r:.2f}R exceeds max loss limit ({self.max_loss_r}R) - forced cut",
                timestamp=datetime.now()
            ))
        
        # Daily loss limit
        if daily_pnl_pct < -self.max_daily_loss_pct:
            signals.append(LossCutSignal(
                category=LossCutCategory.RISK,
                severity=1.0,
                message=f"Daily loss {daily_pnl_pct*100:.1f}% exceeds limit ({self.max_daily_loss_pct*100:.1f}%) - portfolio protection",
                timestamp=datetime.now()
            ))
        
        return signals
    
    def _check_sentiment_shock(
        self,
        features: Dict[str, Any]
    ) -> List[LossCutSignal]:
        """Check for sentiment/news shock (placeholder for news feed integration)."""
        signals = []
        
        # This would integrate with news feed / sentiment API
        # For now, check for extreme volatility as proxy
        atr = features.get("atr_14", 0)
        atr_prev = features.get("atr_14_prev", atr)
        
        if atr_prev > 0 and (atr / atr_prev) > 2.0:
            signals.append(LossCutSignal(
                category=LossCutCategory.SENTIMENT,
                severity=0.7,
                message=f"ATR doubled ({atr/atr_prev:.1f}x) - possible news shock or sentiment shift",
                timestamp=datetime.now()
            ))
        
        return signals
    
    def _determine_action(
        self,
        strikes: int,
        unrealized_r: float,
        structure_broken: bool,
        risk_exceeded: bool,
        categories_triggered: set,
        signals: List[LossCutSignal]
    ) -> Tuple[LossCutUrgency, str, str]:
        """Determine urgency, action, and rationale based on strikes."""
        
        # CRITICAL: Immediate cut conditions
        if risk_exceeded or strikes >= self.strikes_for_critical:
            if structure_broken or risk_exceeded:
                return (
                    LossCutUrgency.CRITICAL,
                    "cut_full",
                    f"CRITICAL: {strikes} strikes detected - trade thesis invalidated, cut immediately"
                )
            else:
                return (
                    LossCutUrgency.CRITICAL,
                    "cut_50",
                    f"CRITICAL: {strikes} strikes detected - cut 50% and tighten SL on remainder"
                )
        
        # CAUTION: 2 strikes
        elif strikes >= self.strikes_for_caution:
            if unrealized_r < -0.8:
                return (
                    LossCutUrgency.CAUTION,
                    "cut_50",
                    f"CAUTION: {strikes} strikes + {unrealized_r:.2f}R loss - cut 50% to reduce exposure"
                )
            else:
                return (
                    LossCutUrgency.CAUTION,
                    "tighten_sl",
                    f"CAUTION: {strikes} strikes detected - tighten SL to breakeven or 0.5x ATR"
                )
        
        # WARNING: 1 strike
        elif strikes >= self.strikes_for_warning:
            return (
                LossCutUrgency.WARNING,
                "tighten_sl",
                f"WARNING: {strikes} strike detected - monitor closely and tighten SL"
            )
        
        # No strikes
        else:
            return (
                LossCutUrgency.NONE,
                "hold",
                "No critical loss cut signals - position within acceptable parameters"
            )
    
    def _calculate_confidence(
        self,
        signals: List[LossCutSignal],
        strikes: int,
        unrealized_r: float
    ) -> float:
        """Calculate confidence score for loss cut recommendation."""
        if not signals:
            return 0.0
        
        # Base confidence on signal severity
        avg_severity = sum(s.severity for s in signals) / len(signals)
        
        # Bonus for multiple strikes
        strike_bonus = min(0.3, strikes * 0.1)
        
        # Bonus for deeper losses
        loss_bonus = min(0.2, abs(unrealized_r) * 0.1) if unrealized_r < 0 else 0
        
        confidence = min(1.0, avg_severity + strike_bonus + loss_bonus)
        return confidence


def analyze_loss_cut(
    direction: str,
    entry_price: float,
    entry_time: datetime,
    current_price: float,
    current_sl: float,
    features: Dict[str, Any],
    bars: Optional[pd.DataFrame] = None,
    trade_type: str = "intraday",
    daily_pnl_pct: float = 0.0
) -> LossCutAnalysis:
    """
    Convenience function to analyze loss cut signals.
    
    Args:
        direction: Trade direction ("buy" or "sell")
        entry_price: Entry price
        entry_time: Entry timestamp
        current_price: Current market price
        current_sl: Current stop loss
        features: Market features dictionary
        bars: Optional OHLCV bars
        trade_type: Trade type ("scalp", "intraday", "swing")
        daily_pnl_pct: Current daily P&L percentage
        
    Returns:
        LossCutAnalysis with urgency, strikes, and recommended action
    """
    detector = LossCutDetector()
    return detector.analyze_loss_cut(
        direction, entry_price, entry_time, current_price, current_sl,
        features, bars, trade_type, daily_pnl_pct
    )
