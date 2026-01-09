"""
Exit Signal Detector - Profit Protection Module
Detects trend exhaustion signals to exit profitable trades before reversals.

Uses a 3-phase exit framework:
- Phase 1: Early Warning (RSI divergence, ADX flattening, volume divergence)
- Phase 2: Exhaustion Confirmed (ATR drop, Bollinger re-entry, VWAP flattening)
- Phase 3: Momentum Breakdown (EMA20 break, SAR flip, Heikin Ashi color change)
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ExitPhase(str, Enum):
    """Exit signal phases."""
    NONE = "none"  # No exit signals
    EARLY_WARNING = "early_warning"  # Phase 1: Monitor closely
    EXHAUSTION = "exhaustion"  # Phase 2: Take partial profits
    BREAKDOWN = "breakdown"  # Phase 3: Exit fully


class ExitUrgency(str, Enum):
    """Exit urgency levels."""
    NONE = "none"  # No action needed
    LOW = "low"  # Monitor, trail stops
    MEDIUM = "medium"  # Take 25-50% profits
    HIGH = "high"  # Take 50-75% profits
    CRITICAL = "critical"  # Exit fully


@dataclass
class ExitSignal:
    """Individual exit signal."""
    indicator: str  # e.g., "RSI_divergence", "ADX_rollover"
    phase: ExitPhase
    strength: float  # 0.0-1.0
    message: str
    timestamp: datetime


@dataclass
class ExitAnalysis:
    """Complete exit analysis for a position."""
    phase: ExitPhase
    urgency: ExitUrgency
    confidence: float  # 0.0-1.0 (how confident we are in the exit signal)
    signals: List[ExitSignal]
    
    # Phase-specific signal counts
    early_warning_count: int
    exhaustion_count: int
    breakdown_count: int
    
    # Recommended action
    action: str  # "hold", "trail_tight", "partial_25", "partial_50", "partial_75", "exit_full"
    rationale: str
    
    # Indicator category breakdown
    momentum_signals: int  # RSI, MACD, Williams %R, CMO
    volatility_signals: int  # ATR, Bollinger, Donchian
    
    # Enhanced loss-cutting fields
    risk_score: float  # 0.0-1.0 confluence risk score
    structure_invalidations: int  # Multi-timeframe invalidation count
    momentum_relapse: bool  # ADX rollover + RSI cross + MACD shrink
    wick_reversal: bool  # Long opposing wicks at S/R
    time_decay: bool  # Time-based backstop triggered
    volume_signals: int  # VWAP, Volume Osc, A/D


class ExitSignalDetector:
    """
    Detects exit signals for open positions using trend exhaustion indicators.
    
    This class analyzes market data to identify when a profitable trade
    is approaching exhaustion and should be exited to protect profits.
    """
    
    def __init__(
        self,
        # Phase 1 thresholds (Early Warning)
        adx_rollover_threshold: float = 40.0,
        rsi_divergence_lookback: int = 5,
        volume_divergence_threshold: float = 0.15,
        
        # Phase 2 thresholds (Exhaustion)
        atr_drop_threshold: float = 0.20,  # 20% ATR drop
        bb_reentry_confirm_bars: int = 1,
        vwap_flatten_threshold: float = 0.0005,
        
        # Phase 3 thresholds (Breakdown)
        ema_break_confirm_bars: int = 1,
        sar_flip_confirm: bool = True,
        
        # Confluence requirements
        min_signals_for_warning: int = 2,
        min_signals_for_exhaustion: int = 2,
        min_signals_for_breakdown: int = 1,
    ):
        """
        Initialize exit signal detector.
        
        Args:
            adx_rollover_threshold: ADX level above which rollover is significant
            rsi_divergence_lookback: Bars to look back for divergence
            volume_divergence_threshold: Min volume drop for divergence signal
            atr_drop_threshold: Min ATR drop percentage for exhaustion
            bb_reentry_confirm_bars: Bars to confirm BB re-entry
            vwap_flatten_threshold: VWAP slope threshold for flattening
            ema_break_confirm_bars: Bars to confirm EMA break
            sar_flip_confirm: Whether to require SAR flip confirmation
            min_signals_for_warning: Min signals for early warning phase
            min_signals_for_exhaustion: Min signals for exhaustion phase
            min_signals_for_breakdown: Min signals for breakdown phase
        """
        self.adx_rollover_threshold = adx_rollover_threshold
        self.rsi_divergence_lookback = rsi_divergence_lookback
        self.volume_divergence_threshold = volume_divergence_threshold
        self.atr_drop_threshold = atr_drop_threshold
        self.bb_reentry_confirm_bars = bb_reentry_confirm_bars
        self.vwap_flatten_threshold = vwap_flatten_threshold
        self.ema_break_confirm_bars = ema_break_confirm_bars
        self.sar_flip_confirm = sar_flip_confirm
        self.min_signals_for_warning = min_signals_for_warning
        self.min_signals_for_exhaustion = min_signals_for_exhaustion
        self.min_signals_for_breakdown = min_signals_for_breakdown
        
        logger.info("ExitSignalDetector initialized")
    
    def analyze_exit_signals(
        self,
        direction: str,  # "buy" or "sell"
        entry_price: float,
        current_price: float,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame] = None
    ) -> ExitAnalysis:
        """
        Analyze all exit signals for a position.
        
        Args:
            direction: Trade direction ("buy" or "sell")
            entry_price: Entry price
            current_price: Current market price
            features: Market features (RSI, MACD, ADX, ATR, etc.)
            bars: Optional OHLCV bars for advanced analysis
            
        Returns:
            ExitAnalysis with phase, urgency, and recommended action
        """
        signals = []
        
        # Phase 1: Early Warning Signals
        signals.extend(self._detect_momentum_exhaustion(direction, features, bars))
        signals.extend(self._detect_volume_divergence(direction, features, bars))
        
        # Phase 2: Exhaustion Signals
        signals.extend(self._detect_volatility_exhaustion(direction, features, bars))
        signals.extend(self._detect_bb_reentry(direction, current_price, features, bars))
        signals.extend(self._detect_vwap_exhaustion(direction, current_price, features, bars))
        
        # Phase 3: Breakdown Signals
        signals.extend(self._detect_ema_break(direction, current_price, features, bars))
        signals.extend(self._detect_sar_flip(direction, current_price, features))
        signals.extend(self._detect_structure_break(direction, features, bars))
        
        # Count signals by phase
        early_warning_count = sum(1 for s in signals if s.phase == ExitPhase.EARLY_WARNING)
        exhaustion_count = sum(1 for s in signals if s.phase == ExitPhase.EXHAUSTION)
        breakdown_count = sum(1 for s in signals if s.phase == ExitPhase.BREAKDOWN)
        
        # Count signals by category
        momentum_signals = sum(1 for s in signals if any(x in s.indicator for x in ["RSI", "MACD", "ADX", "Williams", "CMO"]))
        volatility_signals = sum(1 for s in signals if any(x in s.indicator for x in ["ATR", "BB", "Donchian", "Volatility"]))
        volume_signals = sum(1 for s in signals if any(x in s.indicator for x in ["Volume", "VWAP", "A/D"]))
        structure_signals = sum(1 for s in signals if any(x in s.indicator for x in ["EMA", "SAR", "Fractal", "Pivot"]))
        
        # Determine phase based on signal counts
        phase = self._determine_phase(early_warning_count, exhaustion_count, breakdown_count)
        
        # Determine urgency and action
        urgency, action, rationale = self._determine_action(
            phase, early_warning_count, exhaustion_count, breakdown_count,
            momentum_signals, volatility_signals, volume_signals
        )
        
        # Calculate confidence (0.0-1.0)
        confidence = self._calculate_confidence(signals, phase)
        
        # Calculate enhanced loss-cutting features
        risk_score = self._calculate_confluence_risk_score(direction, features, bars)
        structure_invalidations = self._detect_multi_timeframe_invalidation(direction, features, bars)
        momentum_relapse = self._detect_momentum_relapse(direction, features)
        wick_reversal = self._detect_wick_reversal(direction, features, bars)
        
        # Time decay (would need position age and session info - placeholder for now)
        time_decay = False  # Will be calculated in position_watcher.py
        
        return ExitAnalysis(
            phase=phase,
            urgency=urgency,
            confidence=confidence,
            signals=signals,
            early_warning_count=early_warning_count,
            exhaustion_count=exhaustion_count,
            breakdown_count=breakdown_count,
            action=action,
            rationale=rationale,
            momentum_signals=momentum_signals,
            volatility_signals=volatility_signals,
            volume_signals=volume_signals,
            risk_score=risk_score,
            structure_invalidations=structure_invalidations,
            momentum_relapse=momentum_relapse,
            wick_reversal=wick_reversal,
            time_decay=time_decay
        )
    
    def _detect_momentum_exhaustion(
        self,
        direction: str,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> List[ExitSignal]:
        """Detect momentum exhaustion signals (Phase 1)."""
        signals = []
        
        # 1. ADX Rollover
        adx = features.get("adx", 0)
        adx_prev = features.get("adx_prev", adx)
        
        if adx > self.adx_rollover_threshold and adx < adx_prev:
            strength = min(1.0, (adx - adx_prev) / 10.0)  # Normalize
            signals.append(ExitSignal(
                indicator="ADX_rollover",
                phase=ExitPhase.EARLY_WARNING,
                strength=strength,
                message=f"ADX rolling down from {adx:.1f} (was {adx_prev:.1f})",
                timestamp=datetime.now()
            ))
        
        # 2. RSI Divergence
        if bars is not None and len(bars) >= self.rsi_divergence_lookback:
            rsi_div = self._detect_rsi_divergence(direction, bars)
            if rsi_div:
                signals.append(ExitSignal(
                    indicator="RSI_divergence",
                    phase=ExitPhase.EARLY_WARNING,
                    strength=0.8,
                    message=f"RSI divergence detected ({direction} position)",
                    timestamp=datetime.now()
                ))
        
        # 3. MACD Histogram Shrinking
        macd_hist = features.get("macd_hist", 0)
        macd_hist_prev = features.get("macd_hist_prev", macd_hist)
        
        if direction == "buy" and macd_hist > 0 and macd_hist < macd_hist_prev:
            strength = min(1.0, abs(macd_hist_prev - macd_hist) / abs(macd_hist_prev) if macd_hist_prev != 0 else 0)
            signals.append(ExitSignal(
                indicator="MACD_deceleration",
                phase=ExitPhase.EARLY_WARNING,
                strength=strength,
                message=f"MACD histogram shrinking (bullish momentum fading)",
                timestamp=datetime.now()
            ))
        elif direction == "sell" and macd_hist < 0 and macd_hist > macd_hist_prev:
            strength = min(1.0, abs(macd_hist - macd_hist_prev) / abs(macd_hist_prev) if macd_hist_prev != 0 else 0)
            signals.append(ExitSignal(
                indicator="MACD_deceleration",
                phase=ExitPhase.EARLY_WARNING,
                strength=strength,
                message=f"MACD histogram shrinking (bearish momentum fading)",
                timestamp=datetime.now()
            ))
        
        return signals
    
    def _detect_volume_divergence(
        self,
        direction: str,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> List[ExitSignal]:
        """Detect volume divergence (Phase 1)."""
        signals = []
        
        if bars is None or len(bars) < 5:
            return signals
        
        # Check if volume is declining while price continues trending
        recent_bars = bars.tail(5)
        
        if direction == "buy":
            # Price making higher highs but volume declining
            price_trend = recent_bars['close'].iloc[-1] > recent_bars['close'].iloc[0]
            volume_trend = recent_bars['tick_volume'].iloc[-1] < recent_bars['tick_volume'].iloc[0]
            
            # Convert to float to avoid integer overflow, check for division by zero
            volume_start = float(recent_bars['tick_volume'].iloc[0])
            volume_end = float(recent_bars['tick_volume'].iloc[-1])
            
            if volume_start > 0:
                volume_drop = (volume_start - volume_end) / volume_start
            else:
                volume_drop = 0.0
            
            if price_trend and volume_trend and volume_drop > self.volume_divergence_threshold:
                signals.append(ExitSignal(
                    indicator="Volume_divergence",
                    phase=ExitPhase.EARLY_WARNING,
                    strength=min(1.0, volume_drop),
                    message=f"Volume declining {volume_drop*100:.1f}% while price rising (distribution)",
                    timestamp=datetime.now()
                ))
        
        elif direction == "sell":
            # Price making lower lows but volume declining
            price_trend = recent_bars['close'].iloc[-1] < recent_bars['close'].iloc[0]
            volume_trend = recent_bars['tick_volume'].iloc[-1] < recent_bars['tick_volume'].iloc[0]
            
            # Convert to float to avoid integer overflow, check for division by zero
            volume_start = float(recent_bars['tick_volume'].iloc[0])
            volume_end = float(recent_bars['tick_volume'].iloc[-1])
            
            if volume_start > 0:
                volume_drop = (volume_start - volume_end) / volume_start
            else:
                volume_drop = 0.0
            
            if price_trend and volume_trend and volume_drop > self.volume_divergence_threshold:
                signals.append(ExitSignal(
                    indicator="Volume_divergence",
                    phase=ExitPhase.EARLY_WARNING,
                    strength=min(1.0, volume_drop),
                    message=f"Volume declining {volume_drop*100:.1f}% while price falling (exhaustion)",
                    timestamp=datetime.now()
                ))
        
        return signals
    
    def _detect_volatility_exhaustion(
        self,
        direction: str,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> List[ExitSignal]:
        """Detect volatility exhaustion (Phase 2)."""
        signals = []
        
        # ATR Compression
        atr = features.get("atr_14", 0)
        atr_prev = features.get("atr_14_prev", atr)
        
        if atr_prev > 0:
            atr_drop = (atr_prev - atr) / atr_prev
            if atr_drop > self.atr_drop_threshold:
                signals.append(ExitSignal(
                    indicator="ATR_compression",
                    phase=ExitPhase.EXHAUSTION,
                    strength=min(1.0, atr_drop / self.atr_drop_threshold),
                    message=f"ATR dropped {atr_drop*100:.1f}% (volatility exhaustion)",
                    timestamp=datetime.now()
                ))
        
        return signals
    
    def _detect_bb_reentry(
        self,
        direction: str,
        current_price: float,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> List[ExitSignal]:
        """Detect Bollinger Band re-entry (Phase 2)."""
        signals = []
        
        bb_upper = features.get("bb_upper", 0)
        bb_lower = features.get("bb_lower", 0)
        bb_mid = features.get("bb_mid", 0)
        
        if bb_upper == 0 or bb_lower == 0:
            return signals
        
        if direction == "buy":
            # Was above upper band, now closed back inside
            if bars is not None and len(bars) >= 2:
                prev_close = bars['close'].iloc[-2]
                if prev_close > bb_upper and current_price < bb_upper:
                    signals.append(ExitSignal(
                        indicator="BB_reentry",
                        phase=ExitPhase.EXHAUSTION,
                        strength=0.9,
                        message=f"Price closed back inside upper BB (exhaustion)",
                        timestamp=datetime.now()
                    ))
        
        elif direction == "sell":
            # Was below lower band, now closed back inside
            if bars is not None and len(bars) >= 2:
                prev_close = bars['close'].iloc[-2]
                if prev_close < bb_lower and current_price > bb_lower:
                    signals.append(ExitSignal(
                        indicator="BB_reentry",
                        phase=ExitPhase.EXHAUSTION,
                        strength=0.9,
                        message=f"Price closed back inside lower BB (exhaustion)",
                        timestamp=datetime.now()
                    ))
        
        return signals
    
    def _detect_vwap_exhaustion(
        self,
        direction: str,
        current_price: float,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> List[ExitSignal]:
        """Detect VWAP exhaustion (Phase 2)."""
        signals = []
        
        # VWAP flattening or reverting
        vwap = features.get("vwap", 0)
        vwap_prev = features.get("vwap_prev", vwap)
        
        if vwap > 0 and vwap_prev > 0:
            vwap_slope = (vwap - vwap_prev) / vwap_prev
            
            if direction == "buy":
                # VWAP slope flattening or turning down
                if abs(vwap_slope) < self.vwap_flatten_threshold or vwap_slope < 0:
                    signals.append(ExitSignal(
                        indicator="VWAP_flatten",
                        phase=ExitPhase.EXHAUSTION,
                        strength=0.7,
                        message=f"VWAP flattening (institutional profit-taking)",
                        timestamp=datetime.now()
                    ))
            
            elif direction == "sell":
                # VWAP slope flattening or turning up
                if abs(vwap_slope) < self.vwap_flatten_threshold or vwap_slope > 0:
                    signals.append(ExitSignal(
                        indicator="VWAP_flatten",
                        phase=ExitPhase.EXHAUSTION,
                        strength=0.7,
                        message=f"VWAP flattening (institutional covering)",
                        timestamp=datetime.now()
                    ))
        
        return signals
    
    def _detect_ema_break(
        self,
        direction: str,
        current_price: float,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> List[ExitSignal]:
        """Detect EMA20 break (Phase 3)."""
        signals = []
        
        ema20 = features.get("ema20", 0)
        
        if ema20 == 0:
            return signals
        
        if direction == "buy" and current_price < ema20:
            signals.append(ExitSignal(
                indicator="EMA20_break",
                phase=ExitPhase.BREAKDOWN,
                strength=1.0,
                message=f"Price broke below EMA20 (momentum breakdown)",
                timestamp=datetime.now()
            ))
        
        elif direction == "sell" and current_price > ema20:
            signals.append(ExitSignal(
                indicator="EMA20_break",
                phase=ExitPhase.BREAKDOWN,
                strength=1.0,
                message=f"Price broke above EMA20 (momentum breakdown)",
                timestamp=datetime.now()
            ))
        
        return signals
    
    def _detect_sar_flip(
        self,
        direction: str,
        current_price: float,
        features: Dict[str, Any]
    ) -> List[ExitSignal]:
        """Detect Parabolic SAR flip (Phase 3)."""
        signals = []
        
        sar = features.get("sar", 0)
        
        if sar == 0:
            return signals
        
        if direction == "buy" and current_price < sar:
            signals.append(ExitSignal(
                indicator="SAR_flip",
                phase=ExitPhase.BREAKDOWN,
                strength=1.0,
                message=f"Parabolic SAR flipped (trend reversal)",
                timestamp=datetime.now()
            ))
        
        elif direction == "sell" and current_price > sar:
            signals.append(ExitSignal(
                indicator="SAR_flip",
                phase=ExitPhase.BREAKDOWN,
                strength=1.0,
                message=f"Parabolic SAR flipped (trend reversal)",
                timestamp=datetime.now()
            ))
        
        return signals
    
    def _detect_structure_break(
        self,
        direction: str,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> List[ExitSignal]:
        """Detect structural breakdown signals (Phase 3)."""
        signals = []
        
        # Heikin Ashi color change (if available)
        ha_color = features.get("ha_color", None)
        ha_color_prev = features.get("ha_color_prev", None)
        
        if ha_color and ha_color_prev:
            if direction == "buy" and ha_color == "red" and ha_color_prev == "green":
                signals.append(ExitSignal(
                    indicator="HA_color_flip",
                    phase=ExitPhase.BREAKDOWN,
                    strength=0.9,
                    message=f"Heikin Ashi color flipped to red (trend breakdown)",
                    timestamp=datetime.now()
                ))
            elif direction == "sell" and ha_color == "green" and ha_color_prev == "red":
                signals.append(ExitSignal(
                    indicator="HA_color_flip",
                    phase=ExitPhase.BREAKDOWN,
                    strength=0.9,
                    message=f"Heikin Ashi color flipped to green (trend breakdown)",
                    timestamp=datetime.now()
                ))
        
        return signals
    
    def _detect_rsi_divergence(self, direction: str, bars: pd.DataFrame) -> bool:
        """Detect RSI divergence."""
        if 'rsi' not in bars.columns or len(bars) < self.rsi_divergence_lookback:
            return False
        
        recent = bars.tail(self.rsi_divergence_lookback)
        
        if direction == "buy":
            # Bearish divergence: price higher highs, RSI lower highs
            price_hh = recent['high'].iloc[-1] > recent['high'].iloc[0]
            rsi_lh = recent['rsi'].iloc[-1] < recent['rsi'].iloc[0]
            return price_hh and rsi_lh
        
        elif direction == "sell":
            # Bullish divergence: price lower lows, RSI higher lows
            price_ll = recent['low'].iloc[-1] < recent['low'].iloc[0]
            rsi_hl = recent['rsi'].iloc[-1] > recent['rsi'].iloc[0]
            return price_ll and rsi_hl
        
        return False
    
    def _determine_phase(
        self,
        early_warning_count: int,
        exhaustion_count: int,
        breakdown_count: int
    ) -> ExitPhase:
        """Determine overall exit phase based on signal counts."""
        if breakdown_count >= self.min_signals_for_breakdown:
            return ExitPhase.BREAKDOWN
        elif exhaustion_count >= self.min_signals_for_exhaustion:
            return ExitPhase.EXHAUSTION
        elif early_warning_count >= self.min_signals_for_warning:
            return ExitPhase.EARLY_WARNING
        else:
            return ExitPhase.NONE
    
    def _determine_action(
        self,
        phase: ExitPhase,
        early_warning_count: int,
        exhaustion_count: int,
        breakdown_count: int,
        momentum_signals: int,
        volatility_signals: int,
        volume_signals: int
    ) -> Tuple[ExitUrgency, str, str]:
        """Determine urgency, action, and rationale."""
        
        # Phase 3: Breakdown - Exit immediately (CRITICAL) or tighten aggressively (HIGH)
        if phase == ExitPhase.BREAKDOWN:
            if breakdown_count >= 2:
                return (
                    ExitUrgency.CRITICAL,
                    "exit_full",
                    f"Multiple breakdown signals ({breakdown_count}) - trend reversal confirmed, exit 100%"
                )
            else:
                return (
                    ExitUrgency.HIGH,
                    "trail_very_tight",
                    f"Breakdown signal detected - tighten stops aggressively (0.5x ATR or breakeven+0.3R)"
                )
        
        # Phase 2: Exhaustion - Tighten trailing stops (no partial profits for 0.01 lots)
        elif phase == ExitPhase.EXHAUSTION:
            # Check for confluence (2 out of 3 categories)
            category_count = sum([
                1 if momentum_signals > 0 else 0,
                1 if volatility_signals > 0 else 0,
                1 if volume_signals > 0 else 0
            ])
            
            if category_count >= 2:
                return (
                    ExitUrgency.HIGH,
                    "trail_tight",
                    f"Exhaustion confirmed across {category_count} indicator categories - tighten stops to 1.0x ATR"
                )
            else:
                return (
                    ExitUrgency.MEDIUM,
                    "trail_moderate",
                    f"Exhaustion signals detected - tighten stops to 1.5x ATR"
                )
        
        # Phase 1: Early Warning - Monitor and trail normally
        elif phase == ExitPhase.EARLY_WARNING:
            if early_warning_count >= 3:
                return (
                    ExitUrgency.MEDIUM,
                    "trail_moderate",
                    f"Multiple early warnings ({early_warning_count}) - tighten stops to 1.5x ATR"
                )
            else:
                return (
                    ExitUrgency.LOW,
                    "trail_normal",
                    f"Early warning signals - maintain normal trailing stops (2.0x ATR)"
                )
        
        # No signals
        else:
            return (
                ExitUrgency.NONE,
                "hold",
                "No exit signals - trend remains intact"
            )
    
    def _calculate_confidence(self, signals: List[ExitSignal], phase: ExitPhase) -> float:
        """Calculate confidence score (0.0-1.0) based on signal strength and confluence."""
        if not signals:
            return 0.0
        
        # Weight by signal strength
        avg_strength = sum(s.strength for s in signals) / len(signals)
        
        # Bonus for signal count (more signals = higher confidence)
        signal_count_bonus = min(0.3, len(signals) * 0.1)
        
        # Bonus for phase progression (breakdown > exhaustion > warning)
        phase_bonus = {
            ExitPhase.BREAKDOWN: 0.3,
            ExitPhase.EXHAUSTION: 0.2,
            ExitPhase.EARLY_WARNING: 0.1,
            ExitPhase.NONE: 0.0
        }[phase]
        
        confidence = min(1.0, avg_strength + signal_count_bonus + phase_bonus)
        return confidence

    def _calculate_confluence_risk_score(
        self,
        direction: str,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> float:
        """Calculate 0-1 confluence risk score for early exit decisions."""
        risk_factors = []
        
        # 1. Momentum factors (RSI, MACD, ADX)
        rsi = features.get("rsi", 50)
        adx = features.get("adx", 20)
        macd_hist = features.get("macd_hist", 0)
        
        # RSI momentum
        if direction == "buy":
            rsi_risk = max(0, (rsi - 70) / 30)  # Overbought risk
        else:
            rsi_risk = max(0, (30 - rsi) / 30)  # Oversold risk
        risk_factors.append(("rsi_momentum", rsi_risk, 0.25))
        
        # ADX momentum
        adx_risk = max(0, (50 - adx) / 30) if adx < 50 else 0  # Weak trend risk
        risk_factors.append(("adx_momentum", adx_risk, 0.20))
        
        # MACD momentum
        macd_risk = abs(macd_hist) / 0.01 if abs(macd_hist) < 0.01 else 1.0  # Shrinking histogram
        risk_factors.append(("macd_momentum", macd_risk, 0.15))
        
        # 2. Volatility factors (ATR, Bollinger Bands)
        atr = features.get("atr", 0)
        bb_upper = features.get("bb_upper", 0)
        bb_lower = features.get("bb_lower", 0)
        current_price = features.get("close", 0)
        
        # ATR compression
        atr_risk = max(0, (0.5 - atr/current_price) / 0.5) if current_price > 0 else 0
        risk_factors.append(("atr_compression", atr_risk, 0.15))
        
        # Bollinger Band position
        if bb_upper > 0 and bb_lower > 0 and current_price > 0:
            bb_position = (current_price - bb_lower) / (bb_upper - bb_lower)
            bb_risk = max(0, abs(bb_position - 0.5) * 2)  # Distance from middle
            risk_factors.append(("bb_position", bb_risk, 0.10))
        
        # 3. Volume factors (VWAP, Volume divergence)
        vwap = features.get("vwap", 0)
        volume = features.get("volume", 0)
        volume_ma = features.get("volume_ma", volume)
        
        # VWAP divergence
        if vwap > 0 and current_price > 0:
            vwap_risk = abs(current_price - vwap) / vwap
            risk_factors.append(("vwap_divergence", min(vwap_risk, 1.0), 0.10))
        
        # Volume divergence
        if volume_ma > 0:
            volume_risk = max(0, (volume_ma - volume) / volume_ma)
            risk_factors.append(("volume_divergence", volume_risk, 0.05))
        
        # Calculate weighted risk score
        total_weight = sum(weight for _, _, weight in risk_factors)
        if total_weight == 0:
            return 0.0
        
        weighted_risk = sum(risk * weight for _, risk, weight in risk_factors)
        return min(1.0, weighted_risk / total_weight)

    def _detect_multi_timeframe_invalidation(
        self,
        direction: str,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> int:
        """Count multi-timeframe invalidation signals."""
        invalidation_count = 0
        
        # EMA stack analysis
        ema20 = features.get("ema20", 0)
        ema50 = features.get("ema50", 0)
        ema200 = features.get("ema200", 0)
        current_price = features.get("close", 0)
        
        if all(price > 0 for price in [ema20, ema50, ema200, current_price]):
            # Check EMA stack flip
            if direction == "buy":
                # For long position, check if price breaks below EMA20
                if current_price < ema20:
                    invalidation_count += 1
                # Check if EMA20 crosses below EMA50
                if ema20 < ema50:
                    invalidation_count += 1
            else:
                # For short position, check if price breaks above EMA20
                if current_price > ema20:
                    invalidation_count += 1
                # Check if EMA20 crosses above EMA50
                if ema20 > ema50:
                    invalidation_count += 1
        
        # SAR flip detection
        sar = features.get("sar", 0)
        if sar > 0 and current_price > 0:
            if direction == "buy" and current_price < sar:
                invalidation_count += 1
            elif direction == "sell" and current_price > sar:
                invalidation_count += 1
        
        # Heikin Ashi color flip (if available)
        ha_color = features.get("ha_color", "")
        if ha_color:
            if direction == "buy" and ha_color == "red":
                invalidation_count += 1
            elif direction == "sell" and ha_color == "green":
                invalidation_count += 1
        
        return invalidation_count

    def _detect_momentum_relapse(
        self,
        direction: str,
        features: Dict[str, Any]
    ) -> bool:
        """Detect momentum relapse: ADX rollover + RSI cross + MACD shrink."""
        adx = features.get("adx", 0)
        adx_prev = features.get("adx_prev", adx)
        rsi = features.get("rsi", 50)
        rsi_prev = features.get("rsi_prev", rsi)
        macd_hist = features.get("macd_hist", 0)
        macd_hist_prev = features.get("macd_hist_prev", macd_hist)
        
        # ADX rollover from high
        adx_rollover = adx > 30 and adx < adx_prev
        
        # RSI cross of 50
        rsi_cross = False
        if direction == "buy":
            rsi_cross = rsi_prev > 50 and rsi < 50
        else:
            rsi_cross = rsi_prev < 50 and rsi > 50
        
        # MACD histogram shrinking
        macd_shrink = abs(macd_hist) < abs(macd_hist_prev)
        
        return adx_rollover and rsi_cross and macd_shrink

    def _detect_wick_reversal(
        self,
        direction: str,
        features: Dict[str, Any],
        bars: Optional[pd.DataFrame]
    ) -> bool:
        """Detect long opposing wicks at strong S/R levels."""
        if bars is None or len(bars) < 2:
            return False
        
        current_bar = bars.iloc[-1]
        prev_bar = bars.iloc[-2]
        
        # Calculate wick lengths
        current_upper_wick = current_bar['high'] - max(current_bar['open'], current_bar['close'])
        current_lower_wick = min(current_bar['open'], current_bar['close']) - current_bar['low']
        prev_upper_wick = prev_bar['high'] - max(prev_bar['open'], prev_bar['close'])
        prev_lower_wick = min(prev_bar['open'], prev_bar['close']) - prev_bar['low']
        
        # Check for long opposing wicks
        if direction == "buy":
            # Long upper wick (rejection at resistance)
            return (current_upper_wick > current_lower_wick * 2 and 
                    current_upper_wick > prev_upper_wick)
        else:
            # Long lower wick (rejection at support)
            return (current_lower_wick > current_upper_wick * 2 and 
                    current_lower_wick > prev_lower_wick)

    def _detect_time_decay(
        self,
        position_age_minutes: int,
        session_volatility: str
    ) -> bool:
        """Detect time-based decay backstop."""
        # Adjust thresholds based on session
        if session_volatility == "high":
            max_age = 60  # 1 hour for high volatility
        elif session_volatility == "medium":
            max_age = 120  # 2 hours for medium volatility
        else:
            max_age = 180  # 3 hours for low volatility
        
        return position_age_minutes > max_age


def detect_exit_signals(
    direction: str,
    entry_price: float,
    current_price: float,
    features: Dict[str, Any],
    bars: Optional[pd.DataFrame] = None
) -> ExitAnalysis:
    """
    Convenience function to detect exit signals.
    
    Args:
        direction: Trade direction ("buy" or "sell")
        entry_price: Entry price
        current_price: Current market price
        features: Market features dictionary
        bars: Optional OHLCV bars
        
    Returns:
        ExitAnalysis with phase, urgency, and recommended action
    """
    detector = ExitSignalDetector()
    return detector.analyze_exit_signals(direction, entry_price, current_price, features, bars)
