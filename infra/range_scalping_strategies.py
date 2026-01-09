"""
Range Scalping Strategies
Implements 5 core range scalping strategies with R:R-based targets.

Strategies:
1. VWAP Mean Reversion - Price far from VWAP + RSI extreme
2. Bollinger Band Fade - Price touches BB edge + RSI extreme + volume decreasing
3. PDH/PDL Rejection - Price sweeps PDH/PDL + rejection wick + closes inside
4. RSI Bounce - RSI + Stochastic extremes for micro scalps
5. Liquidity Sweep Reversal - Sweep beyond PDH/PDL + immediate reversal + order flow
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional, List, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import numpy as np

from infra.range_boundary_detector import RangeStructure

logger = logging.getLogger(__name__)


@dataclass
class EntrySignal:
    """Entry signal for a range scalping strategy"""
    strategy_name: str
    direction: str  # "BUY" or "SELL"
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: int  # 0-100
    confluence_score: int  # 0-100
    reason: str
    r_r_ratio: float
    lot_size: float = 0.01  # Fixed for range scalps


class BaseRangeScalpingStrategy(ABC):
    """
    Base class for all range scalping strategies.
    
    Each strategy must implement:
    - check_entry_conditions() - Determine if entry conditions are met
    - calculate_stop_loss() - ATR-based or structure-based SL
    - calculate_take_profit() - R:R-based with session adjustment
    """
    
    def __init__(self, config: Dict, rr_config: Dict):
        self.config = config
        self.rr_config = rr_config
        self.strategy_name = self.__class__.__name__.replace("Strategy", "").lower()
        
        # Get R:R config for this strategy
        self.rr_targets = rr_config.get("strategy_rr", {}).get(self.strategy_name, {})
        self.min_rr = self.rr_targets.get("min", 1.0)
        self.target_rr = self.rr_targets.get("target", 1.2)
        self.max_rr = self.rr_targets.get("max", 1.5)
        self.default_stop_atr_mult = self.rr_targets.get("default_stop_atr_mult", 0.8)
        self.default_tp_atr_mult = self.rr_targets.get("default_tp_atr_mult", 1.0)
    
    @abstractmethod
    def check_entry_conditions(
        self,
        symbol: str,
        range_data: RangeStructure,
        current_price: float,
        indicators: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> Optional[EntrySignal]:
        """
        Check if entry conditions are met for this strategy.
        
        Returns: EntrySignal if conditions met, None otherwise
        """
        pass
    
    def calculate_stop_loss(
        self,
        entry_price: float,
        direction: str,
        effective_atr: float,
        range_data: RangeStructure,
        session_adjustments: Optional[Dict] = None
    ) -> float:
        """
        Calculate stop loss using ATR-based or structure-based method.
        
        Args:
            entry_price: Entry price
            direction: "BUY" or "SELL"
            effective_atr: Effective ATR for volatility scaling
            range_data: Range structure for context
            session_adjustments: Session-based adjustments from RR config
        
        Returns: Stop loss price
        """
        stop_tightener = 1.0
        if session_adjustments:
            stop_tightener = session_adjustments.get("stop_tightener", 1.0)
        
        stop_atr_mult = self.default_stop_atr_mult * stop_tightener
        
        stop_distance = effective_atr * stop_atr_mult
        
        if direction == "BUY":
            return entry_price - stop_distance
        else:  # SELL
            return entry_price + stop_distance
    
    def calculate_take_profit(
        self,
        entry_price: float,
        direction: str,
        stop_loss: float,
        effective_atr: float,
        session_adjustments: Optional[Dict] = None
    ) -> float:
        """
        Calculate take profit using R:R-based method with session adjustment.
        
        Args:
            entry_price: Entry price
            direction: "BUY" or "SELL"
            stop_loss: Stop loss price
            effective_atr: Effective ATR
            session_adjustments: Session-based adjustments from RR config
        
        Returns: Take profit price
        """
        # Calculate SL distance
        if direction == "BUY":
            sl_distance = entry_price - stop_loss
        else:
            sl_distance = stop_loss - entry_price
        
        # Calculate TP distance using target R:R with session multiplier
        rr_mult = 1.0
        max_rr = float('inf')
        if session_adjustments:
            rr_mult = session_adjustments.get("rr_multiplier", 1.0)
            max_rr = session_adjustments.get("max_rr", float('inf'))
        
        adjusted_target_rr = self.target_rr * rr_mult
        
        # Apply max R:R limit if specified
        adjusted_target_rr = min(adjusted_target_rr, max_rr)
        
        tp_distance = sl_distance * adjusted_target_rr
        
        if direction == "BUY":
            return entry_price + tp_distance
        else:  # SELL
            return entry_price - tp_distance
    
    def _calculate_rsi(self, closes: pd.Series, period: int = 14) -> float:
        """Calculate RSI"""
        if len(closes) < period + 1:
            return 50.0  # Neutral
        
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])
    
    def _calculate_stochastic(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_period: int = 14,
        d_period: int = 3
    ) -> Tuple[float, float]:
        """Calculate Stochastic %K and %D"""
        if len(high) < k_period:
            return 50.0, 50.0  # Neutral
        
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        stoch_k = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        stoch_d = stoch_k.rolling(window=d_period).mean()
        
        return float(stoch_k.iloc[-1]), float(stoch_d.iloc[-1])
    
    def _calculate_bollinger_bands(
        self,
        close: pd.Series,
        period: int = 20,
        std_dev: float = 2.0
    ) -> Dict[str, float]:
        """Calculate Bollinger Bands"""
        if len(close) < period:
            return {
                "upper": close.iloc[-1] * 1.02,
                "middle": close.iloc[-1],
                "lower": close.iloc[-1] * 0.98,
                "width": 0.04
            }
        
        middle = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        width = (upper - lower) / middle
        
        return {
            "upper": float(upper.iloc[-1]),
            "middle": float(middle.iloc[-1]),
            "lower": float(lower.iloc[-1]),
            "width": float(width.iloc[-1])
        }


class VWAPMeanReversionStrategy(BaseRangeScalpingStrategy):
    """
    VWAP Mean Reversion Strategy
    
    Entry Conditions:
    - Price far from VWAP (>0.5% or >0.75 ATR)
    - RSI extreme (<30 for BUY, >70 for SELL)
    - Price oscillating around VWAP (confirmed range environment)
    
    Best for: Asian session, post-NY session
    """
    
    def check_entry_conditions(
        self,
        symbol: str,
        range_data: RangeStructure,
        current_price: float,
        indicators: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> Optional[EntrySignal]:
        """Check VWAP mean reversion entry conditions"""
        if not self.config.get("strategies", {}).get("vwap_reversion", {}).get("enabled", True):
            return None
        
        vwap = range_data.range_mid
        rsi = indicators.get("rsi", 50.0)
        effective_atr = market_data.get("effective_atr", range_data.range_width_atr)
        
        # Check if price is far from VWAP
        distance_from_vwap = abs(current_price - vwap)
        distance_atr = distance_from_vwap / effective_atr if effective_atr > 0 else 0
        distance_pct = distance_from_vwap / vwap if vwap > 0 else 0
        
        # Entry threshold: >0.5% OR >0.75 ATR from VWAP
        price_far_enough = (distance_pct > 0.005) or (distance_atr > 0.75)
        
        if not price_far_enough:
            return None
        
        # Check RSI extremes
        direction = None
        if rsi < 30 and current_price < vwap:
            # Oversold and below VWAP → BUY (mean reversion up)
            direction = "BUY"
        elif rsi > 70 and current_price > vwap:
            # Overbought and above VWAP → SELL (mean reversion down)
            direction = "SELL"
        
        if not direction:
            return None
        
        # Calculate entry, SL, TP
        entry_price = current_price
        stop_loss = self.calculate_stop_loss(
            entry_price, direction, effective_atr, range_data
        )
        take_profit = self.calculate_take_profit(
            entry_price, direction, stop_loss, effective_atr
        )
        
        # Calculate R:R
        if direction == "BUY":
            sl_distance = entry_price - stop_loss
            tp_distance = take_profit - entry_price
        else:
            sl_distance = stop_loss - entry_price
            tp_distance = entry_price - take_profit
        
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
        
        # Confidence based on distance and RSI extreme
        confidence = min(100, int(
            30 +  # Base
            (distance_atr * 20) +  # Distance bonus (up to 20 points)
            (abs(30 - rsi) if direction == "BUY" else abs(rsi - 70)) * 0.5  # RSI extreme bonus
        ))
        
        return EntrySignal(
            strategy_name="vwap_reversion",
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            confluence_score=confidence,  # Will be updated by scorer
            reason=f"VWAP mean reversion: {direction} at {distance_pct:.2%} from VWAP, RSI={rsi:.1f}",
            r_r_ratio=rr_ratio
        )


class BollingerBandFadeStrategy(BaseRangeScalpingStrategy):
    """
    Bollinger Band Fade Strategy
    
    Entry Conditions:
    - Price touches BB upper/lower edge
    - RSI extreme (<30 or >70)
    - Volume decreasing (compression signal)
    
    Best for: Low ADX environments, compression zones
    """
    
    def check_entry_conditions(
        self,
        symbol: str,
        range_data: RangeStructure,
        current_price: float,
        indicators: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> Optional[EntrySignal]:
        """Check Bollinger Band fade entry conditions"""
        if not self.config.get("strategies", {}).get("bb_fade", {}).get("enabled", True):
            return None
        
        # Get BB data
        bb_upper = indicators.get("bb_upper")
        bb_lower = indicators.get("bb_lower")
        bb_middle = indicators.get("bb_middle")
        
        if not all([bb_upper, bb_lower, bb_middle]):
            return None
        
        rsi = indicators.get("rsi", 50.0)
        volume_current = market_data.get("volume_current", 0)
        volume_avg = market_data.get("volume_1h_avg", 1)
        volume_decreasing = volume_current < volume_avg * 0.9 if volume_avg > 0 else False
        
        # Check if price is at BB edge (within 0.1% tolerance)
        tolerance = 0.001
        at_upper = abs(current_price - bb_upper) / bb_upper <= tolerance
        at_lower = abs(current_price - bb_lower) / bb_lower <= tolerance
        
        direction = None
        if at_lower and rsi < 30:
            # At lower band, oversold → BUY (fade from lower edge)
            direction = "BUY"
        elif at_upper and rsi > 70:
            # At upper band, overbought → SELL (fade from upper edge)
            direction = "SELL"
        
        if not direction:
            return None
        
        # Volume should be decreasing for better fade signal
        if not volume_decreasing:
            # Still allow but lower confidence
            pass
        
        effective_atr = market_data.get("effective_atr", range_data.range_width_atr)
        session_adjustments = market_data.get("session_adjustments")
        
        # Calculate entry, SL, TP
        entry_price = current_price
        stop_loss = self.calculate_stop_loss(
            entry_price, direction, effective_atr, range_data, session_adjustments
        )
        take_profit = self.calculate_take_profit(
            entry_price, direction, stop_loss, effective_atr, session_adjustments
        )
        
        # Calculate R:R
        if direction == "BUY":
            sl_distance = entry_price - stop_loss
            tp_distance = take_profit - entry_price
        else:
            sl_distance = stop_loss - entry_price
            tp_distance = entry_price - take_profit
        
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
        
        # Confidence based on RSI extreme and volume
        confidence = min(100, int(
            40 +  # Base
            (abs(30 - rsi) if direction == "BUY" else abs(rsi - 70)) * 0.4 +  # RSI bonus
            (20 if volume_decreasing else 0)  # Volume bonus
        ))
        
        return EntrySignal(
            strategy_name="bb_fade",
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            confluence_score=confidence,
            reason=f"BB fade: {direction} at {'lower' if direction == 'BUY' else 'upper'} band, RSI={rsi:.1f}, volume={'decreasing' if volume_decreasing else 'stable'}",
            r_r_ratio=rr_ratio
        )


class PDHPDLRejectionStrategy(BaseRangeScalpingStrategy):
    """
    PDH/PDL Rejection Strategy
    
    Entry Conditions:
    - Price sweeps PDH/PDL (liquidity grab)
    - Rejection wick forms (closes inside range)
    - Order flow confirmation (optional)
    
    Best for: Quiet sessions, London mid-session
    """
    
    def check_entry_conditions(
        self,
        symbol: str,
        range_data: RangeStructure,
        current_price: float,
        indicators: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> Optional[EntrySignal]:
        """Check PDH/PDL rejection entry conditions"""
        if not self.config.get("strategies", {}).get("pdh_pdl_rejection", {}).get("enabled", True):
            return None
        
        # Get PDH/PDL from market data
        pdh = market_data.get("pdh")
        pdl = market_data.get("pdl")
        
        if not pdh or not pdl:
            return None
        
        # Get recent candles to check for sweep + rejection
        recent_candles = market_data.get("recent_candles", [])
        if len(recent_candles) < 2:
            return None
        
        # Check latest candle for rejection wick
        latest = recent_candles[-1]
        prev = recent_candles[-2] if len(recent_candles) >= 2 else latest
        
        # Check for PDH sweep + rejection (SELL signal)
        direction = None
        
        # PDH sweep: price exceeded PDH in previous candle but closed below
        if prev.get("high", 0) > pdh * 1.001:  # 0.1% tolerance for sweep
            if latest.get("close", 0) < pdh:
                # Rejection wick: long upper wick relative to body
                body_size = abs(latest.get("close", 0) - latest.get("open", 0))
                upper_wick = latest.get("high", 0) - max(latest.get("close", 0), latest.get("open", 0))
                if upper_wick > body_size * 1.5:  # Wick > 1.5x body
                    direction = "SELL"
        
        # PDL sweep: price exceeded PDL in previous candle but closed above
        if prev.get("low", 0) < pdl * 0.999:  # 0.1% tolerance for sweep
            if latest.get("close", 0) > pdl:
                # Rejection wick: long lower wick relative to body
                body_size = abs(latest.get("close", 0) - latest.get("open", 0))
                lower_wick = min(latest.get("close", 0), latest.get("open", 0)) - latest.get("low", 0)
                if lower_wick > body_size * 1.5:  # Wick > 1.5x body
                    direction = "BUY"
        
        if not direction:
            return None
        
        # Verify price closes inside range after sweep
        if direction == "SELL":
            if latest.get("close", 0) > range_data.range_high:
                return None  # Closed outside range
        else:  # BUY
            if latest.get("close", 0) < range_data.range_low:
                return None  # Closed outside range
        
        effective_atr = market_data.get("effective_atr", range_data.range_width_atr)
        session_adjustments = market_data.get("session_adjustments")
        
        # Calculate entry, SL, TP
        entry_price = current_price
        stop_loss = self.calculate_stop_loss(
            entry_price, direction, effective_atr, range_data, session_adjustments
        )
        take_profit = self.calculate_take_profit(
            entry_price, direction, stop_loss, effective_atr, session_adjustments
        )
        
        # Calculate R:R
        if direction == "BUY":
            sl_distance = entry_price - stop_loss
            tp_distance = take_profit - entry_price
        else:
            sl_distance = stop_loss - entry_price
            tp_distance = entry_price - take_profit
        
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
        
        # Confidence based on wick size and sweep clarity
        wick_ratio = (upper_wick if direction == "SELL" else lower_wick) / body_size if body_size > 0 else 0
        confidence = min(100, int(
            50 +  # Base
            (min(wick_ratio, 3.0) * 10) +  # Wick size bonus (up to 30 points)
            20  # Sweep confirmed bonus
        ))
        
        return EntrySignal(
            strategy_name="pdh_pdl_rejection",
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            confluence_score=confidence,
            reason=f"PDH/PDL rejection: {direction} after {'PDH' if direction == 'SELL' else 'PDL'} sweep with rejection wick",
            r_r_ratio=rr_ratio
        )


class RSIBounceStrategy(BaseRangeScalpingStrategy):
    """
    RSI Bounce Strategy
    
    Entry Conditions:
    - RSI < 30 + Stochastic < 20 (oversold) → BUY
    - RSI > 70 + Stochastic > 80 (overbought) → SELL
    
    Best for: Post-NY session, micro scalps
    """
    
    def check_entry_conditions(
        self,
        symbol: str,
        range_data: RangeStructure,
        current_price: float,
        indicators: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> Optional[EntrySignal]:
        """Check RSI bounce entry conditions"""
        if not self.config.get("strategies", {}).get("rsi_bounce", {}).get("enabled", True):
            return None
        
        rsi = indicators.get("rsi", 50.0)
        stoch_k = indicators.get("stoch_k", 50.0)
        stoch_d = indicators.get("stoch_d", 50.0)
        
        direction = None
        
        # Oversold: RSI < 30 AND Stochastic < 20
        if rsi < 30 and stoch_k < 20 and stoch_d < 20:
            direction = "BUY"
        # Overbought: RSI > 70 AND Stochastic > 80
        elif rsi > 70 and stoch_k > 80 and stoch_d > 80:
            direction = "SELL"
        
        if not direction:
            return None
        
        effective_atr = market_data.get("effective_atr", range_data.range_width_atr)
        session_adjustments = market_data.get("session_adjustments")
        
        # Calculate entry, SL, TP
        entry_price = current_price
        stop_loss = self.calculate_stop_loss(
            entry_price, direction, effective_atr, range_data, session_adjustments
        )
        take_profit = self.calculate_take_profit(
            entry_price, direction, stop_loss, effective_atr, session_adjustments
        )
        
        # Calculate R:R
        if direction == "BUY":
            sl_distance = entry_price - stop_loss
            tp_distance = take_profit - entry_price
        else:
            sl_distance = stop_loss - entry_price
            tp_distance = entry_price - take_profit
        
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
        
        # Confidence based on how extreme RSI/Stochastic are
        if direction == "BUY":
            rsi_extreme = 30 - rsi  # How oversold (0-30 range)
            stoch_extreme = 20 - min(stoch_k, stoch_d)  # How oversold (0-20 range)
        else:
            rsi_extreme = rsi - 70  # How overbought (0-30 range)
            stoch_extreme = min(stoch_k, stoch_d) - 80  # How overbought (0-20 range)
        
        confidence = min(100, int(
            60 +  # Base (higher base for confirmed extremes)
            (rsi_extreme * 0.8) +  # RSI extreme bonus
            (stoch_extreme * 0.4)  # Stochastic extreme bonus
        ))
        
        return EntrySignal(
            strategy_name="rsi_bounce",
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            confluence_score=confidence,
            reason=f"RSI bounce: {direction} with RSI={rsi:.1f}, Stoch K={stoch_k:.1f}, D={stoch_d:.1f}",
            r_r_ratio=rr_ratio
        )


class LiquiditySweepReversalStrategy(BaseRangeScalpingStrategy):
    """
    Liquidity Sweep Reversal Strategy
    
    Entry Conditions:
    - Price sweeps beyond PDH/PDL (liquidity grab)
    - Immediate reversal (opposite candle closes inside)
    - Order flow confirmation (optional but preferred)
    
    Best for: High-probability reversals, requires strong confluence
    """
    
    def check_entry_conditions(
        self,
        symbol: str,
        range_data: RangeStructure,
        current_price: float,
        indicators: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> Optional[EntrySignal]:
        """Check liquidity sweep reversal entry conditions"""
        if not self.config.get("strategies", {}).get("liquidity_sweep", {}).get("enabled", True):
            return None
        
        # Get PDH/PDL
        pdh = market_data.get("pdh")
        pdl = market_data.get("pdl")
        
        if not pdh or not pdl:
            return None
        
        # Get recent candles
        recent_candles = market_data.get("recent_candles", [])
        if len(recent_candles) < 3:
            return None
        
        # Check for sweep + immediate reversal
        latest = recent_candles[-1]
        prev = recent_candles[-2]
        prev2 = recent_candles[-3] if len(recent_candles) >= 3 else prev
        
        direction = None
        
        # PDH sweep + reversal: Price exceeded PDH but reversed
        if prev.get("high", 0) > pdh * 1.002:  # Sweep beyond PDH (0.2% buffer)
            # Immediate reversal: next candle closes below PDH
            if latest.get("close", 0) < pdh:
                # Strong reversal: opposite color candle or long wick
                is_reversal_candle = (
                    latest.get("close", 0) < latest.get("open", 0) or  # Bearish candle
                    (latest.get("high", 0) - max(latest.get("close", 0), latest.get("open", 0))) > 
                    abs(latest.get("close", 0) - latest.get("open", 0)) * 1.5  # Long upper wick
                )
                if is_reversal_candle:
                    direction = "SELL"
        
        # PDL sweep + reversal: Price exceeded PDL but reversed
        if prev.get("low", 0) < pdl * 0.998:  # Sweep beyond PDL (0.2% buffer)
            # Immediate reversal: next candle closes above PDL
            if latest.get("close", 0) > pdl:
                # Strong reversal: opposite color candle or long wick
                is_reversal_candle = (
                    latest.get("close", 0) > latest.get("open", 0) or  # Bullish candle
                    (min(latest.get("close", 0), latest.get("open", 0)) - latest.get("low", 0)) >
                    abs(latest.get("close", 0) - latest.get("open", 0)) * 1.5  # Long lower wick
                )
                if is_reversal_candle:
                    direction = "BUY"
        
        if not direction:
            return None
        
        # Optional: Order flow confirmation
        order_flow_confirmed = False
        if market_data.get("order_flow_signal"):
            of_signal = market_data["order_flow_signal"]
            if direction == "BUY" and of_signal.get("signal") in ["BULLISH", "STRONG_BUY"]:
                order_flow_confirmed = True
            elif direction == "SELL" and of_signal.get("signal") in ["BEARISH", "STRONG_SELL"]:
                order_flow_confirmed = True
        
        effective_atr = market_data.get("effective_atr", range_data.range_width_atr)
        session_adjustments = market_data.get("session_adjustments")
        
        # Calculate entry, SL, TP
        entry_price = current_price
        stop_loss = self.calculate_stop_loss(
            entry_price, direction, effective_atr, range_data, session_adjustments
        )
        take_profit = self.calculate_take_profit(
            entry_price, direction, stop_loss, effective_atr, session_adjustments
        )
        
        # Calculate R:R
        if direction == "BUY":
            sl_distance = entry_price - stop_loss
            tp_distance = take_profit - entry_price
        else:
            sl_distance = stop_loss - entry_price
            tp_distance = entry_price - take_profit
        
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
        
        # Confidence: Higher for liquidity sweeps (typically strong setups)
        confidence = min(100, int(
            70 +  # Base (high base for liquidity sweeps)
            (20 if order_flow_confirmed else 0) +  # Order flow bonus
            10  # Sweep confirmed bonus
        ))
        
        return EntrySignal(
            strategy_name="liquidity_sweep",
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            confluence_score=confidence,
            reason=f"Liquidity sweep reversal: {direction} after {'PDH' if direction == 'SELL' else 'PDL'} sweep{' (OF confirmed)' if order_flow_confirmed else ''}",
            r_r_ratio=rr_ratio
        )

