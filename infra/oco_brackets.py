"""
OCO (One-Cancels-Other) Brackets - Phase 4.4.4
Places bidirectional breakout entries around consolidation; whichever fills cancels the other.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConsolidationDetection:
    """Result of consolidation detection."""
    is_consolidation: bool
    range_high: float
    range_low: float
    range_width: float
    range_width_atr: float
    bb_width: float
    adx: float
    confidence: float
    rationale: str


@dataclass
class OCOBracketResult:
    """Result of OCO bracket calculation."""
    is_valid: bool
    
    # Buy side
    buy_stop: float
    buy_sl: float
    buy_tp: float
    buy_rr: float
    
    # Sell side
    sell_stop: float
    sell_sl: float
    sell_tp: float
    sell_rr: float
    
    # Metadata
    range_high: float
    range_low: float
    bracket_distance_atr: float
    expiry_minutes: int
    consolidation_confidence: float
    rationale: str
    skip_reasons: list


class OCOBracketCalculator:
    """
    Calculate OCO bracket orders for breakout trading.
    Places both buy stop and sell stop around consolidation; whichever fills cancels the other.
    """
    
    def __init__(
        self,
        bracket_distance_atr: float = 0.2,    # Distance from range edge
        sl_distance_atr: float = 1.0,         # SL distance from entry
        min_rr: float = 2.0,                   # Minimum risk:reward
        max_rr: float = 3.0,                   # Maximum risk:reward
        min_range_width_atr: float = 0.5,     # Min range width to avoid tiny ranges
        max_spread_atr_pct: float = 0.20,     # Max spread (20% of ATR)
        default_expiry_minutes: int = 90      # Default expiry time
    ):
        """
        Initialize OCO bracket calculator.
        
        Args:
            bracket_distance_atr: Distance from range edge to place stop (× ATR)
            sl_distance_atr: Stop loss distance from entry (× ATR)
            min_rr: Minimum risk:reward ratio
            max_rr: Maximum risk:reward ratio
            min_range_width_atr: Minimum range width (× ATR) to avoid tiny ranges
            max_spread_atr_pct: Maximum spread as % of ATR
            default_expiry_minutes: Default expiry time in minutes
        """
        self.bracket_distance_atr = bracket_distance_atr
        self.sl_distance_atr = sl_distance_atr
        self.min_rr = min_rr
        self.max_rr = max_rr
        self.min_range_width_atr = min_range_width_atr
        self.max_spread_atr_pct = max_spread_atr_pct
        self.default_expiry_minutes = default_expiry_minutes
    
    def calculate_oco_bracket(
        self,
        features: Dict[str, Any],
        atr: float,
        session: str = "UNKNOWN",
        symbol: str = ""
    ) -> OCOBracketResult:
        """
        Calculate OCO bracket orders if consolidation is detected.
        
        Args:
            features: Market features (for consolidation detection)
            atr: ATR(14) for sizing
            session: Current trading session
            symbol: Trading symbol
            
        Returns:
            OCOBracketResult with bracket levels or skip reasons
        """
        try:
            skip_reasons = []
            
            # 1. Detect consolidation
            consolidation = self._detect_consolidation(features, atr)
            
            if not consolidation.is_consolidation:
                skip_reasons.append(consolidation.rationale)
                return self._create_invalid_result(skip_reasons, consolidation)
            
            # 2. Validate session (only London/NY)
            if session not in ["LONDON", "NY", "LONDON_NY"]:
                skip_reasons.append(f"OCO brackets only in London/NY sessions (current: {session})")
                return self._create_invalid_result(skip_reasons, consolidation)
            
            # 3. Check spread
            spread_atr_pct = features.get("spread_atr_pct", 0.0)
            if spread_atr_pct > self.max_spread_atr_pct:
                skip_reasons.append(f"Spread too high: {spread_atr_pct:.1%} > {self.max_spread_atr_pct:.1%}")
                return self._create_invalid_result(skip_reasons, consolidation)
            
            # 4. Check for existing pending orders
            has_pending = features.get("has_pending_orders", False)
            if has_pending:
                skip_reasons.append("Already have pending orders active")
                return self._create_invalid_result(skip_reasons, consolidation)
            
            # 5. Check news blackout
            news_blackout = features.get("news_blackout", False)
            if news_blackout:
                skip_reasons.append("News blackout period")
                return self._create_invalid_result(skip_reasons, consolidation)
            
            # 6. Calculate bracket levels
            range_high = consolidation.range_high
            range_low = consolidation.range_low
            range_width = consolidation.range_width
            
            # Buy side (above resistance)
            buy_stop = range_high + (self.bracket_distance_atr * atr)
            # SL must clear the range low with buffer (BELOW range)
            min_buy_sl_distance = range_width + (self.bracket_distance_atr * atr) + (0.3 * atr)
            buy_sl_calc = buy_stop - (self.sl_distance_atr * atr)
            buy_sl_safe = buy_stop - min_buy_sl_distance
            # FIXED: Use MAX to ensure SL is further from entry (wider, safer)
            buy_sl = max(buy_sl_calc, buy_sl_safe)  # CRITICAL FIX: was min(), now max()
            buy_risk = abs(buy_stop - buy_sl)
            buy_tp = buy_stop + (self.min_rr * buy_risk)  # Use min RR for conservative target
            buy_rr = abs(buy_tp - buy_stop) / buy_risk if buy_risk > 0 else 0
            
            # Sell side (below support)
            sell_stop = range_low - (self.bracket_distance_atr * atr)
            # SL must clear the range high with buffer (ABOVE range)
            min_sell_sl_distance = range_width + (self.bracket_distance_atr * atr) + (0.3 * atr)
            sell_sl_calc = sell_stop + (self.sl_distance_atr * atr)
            sell_sl_safe = sell_stop + min_sell_sl_distance
            # FIXED: Use MIN to ensure SL is further from entry (wider, safer)
            sell_sl = min(sell_sl_calc, sell_sl_safe)  # CRITICAL FIX: was max(), now min()
            sell_risk = abs(sell_sl - sell_stop)
            sell_tp = sell_stop - (self.min_rr * sell_risk)
            sell_rr = abs(sell_stop - sell_tp) / sell_risk if sell_risk > 0 else 0
            
            # 7. Validate geometry - FIXED: Correct logic for SL placement
            # BUY SL must be BELOW range low (sell_sl < buy_stop < range_high and buy_sl < range_low)
            if buy_sl > range_low:
                skip_reasons.append(f"Buy SL {buy_sl:.5f} not below range low {range_low:.5f} (would be inside or above range)")
                return self._create_invalid_result(skip_reasons, consolidation)
            
            # SELL SL must be ABOVE range high (buy_sl > sell_stop > range_low and sell_sl > range_high)
            if sell_sl < range_high:
                skip_reasons.append(f"Sell SL {sell_sl:.5f} not above range high {range_high:.5f} (would be inside or below range)")
                return self._create_invalid_result(skip_reasons, consolidation)
            
            # 8. Calculate expiry
            expiry_minutes = self._calculate_expiry(session, features)
            
            # Build rationale
            rationale = (
                f"OCO bracket: Range {range_low:.5f}-{range_high:.5f} "
                f"({consolidation.range_width_atr:.2f}× ATR), "
                f"confidence {consolidation.confidence:.0%}, "
                f"expiry {expiry_minutes}min"
            )
            
            return OCOBracketResult(
                is_valid=True,
                buy_stop=buy_stop,
                buy_sl=buy_sl,
                buy_tp=buy_tp,
                buy_rr=buy_rr,
                sell_stop=sell_stop,
                sell_sl=sell_sl,
                sell_tp=sell_tp,
                sell_rr=sell_rr,
                range_high=range_high,
                range_low=range_low,
                bracket_distance_atr=self.bracket_distance_atr,
                expiry_minutes=expiry_minutes,
                consolidation_confidence=consolidation.confidence,
                rationale=rationale,
                skip_reasons=[]
            )
            
        except Exception as e:
            logger.error(f"OCO bracket calculation failed: {e}")
            return self._create_invalid_result([f"Calculation error: {e}"], None)
    
    def _detect_consolidation(self, features: Dict[str, Any], atr: float) -> ConsolidationDetection:
        """
        Detect if market is in consolidation (range-bound).
        
        Criteria:
        - Low ADX (< 25)
        - Narrow Bollinger Bands (< 0.03)
        - Recent highs/lows within tight range
        """
        try:
            # Get features
            adx = features.get("adx_14", features.get("adx", 0))
            bb_width = features.get("bb_width", 0)
            
            # Get recent highs/lows (last 20 bars)
            highs = features.get("recent_highs", [])
            lows = features.get("recent_lows", [])
            
            # If we don't have explicit highs/lows, try to extract from OHLC
            if not highs or not lows:
                # Try to get from close price and volatility estimate
                close = features.get("close", 0)
                if close > 0 and atr > 0:
                    # Estimate range as close ± 1.5× ATR
                    range_high = close + (1.0 * atr)
                    range_low = close - (1.0 * atr)
                else:
                    return ConsolidationDetection(
                        is_consolidation=False,
                        range_high=0,
                        range_low=0,
                        range_width=0,
                        range_width_atr=0,
                        bb_width=bb_width,
                        adx=adx,
                        confidence=0,
                        rationale="Insufficient data for range detection"
                    )
            else:
                range_high = max(highs) if highs else 0
                range_low = min(lows) if lows else 0
            
            range_width = abs(range_high - range_low)
            range_width_atr = range_width / atr if atr > 0 else 0
            
            # Score consolidation
            score = 0
            reasons = []
            
            # ADX score (lower = more consolidation)
            if adx < 20:
                score += 2
                reasons.append(f"ADX {adx:.1f} < 20")
            elif adx < 25:
                score += 1
                reasons.append(f"ADX {adx:.1f} < 25")
            else:
                reasons.append(f"ADX {adx:.1f} too high (trending)")
            
            # Bollinger Band width score (narrower = more consolidation)
            if bb_width < 0.02:
                score += 2
                reasons.append(f"BB width {bb_width:.3f} < 0.02")
            elif bb_width < 0.03:
                score += 1
                reasons.append(f"BB width {bb_width:.3f} < 0.03")
            else:
                reasons.append(f"BB width {bb_width:.3f} too wide")
            
            # Range width validation
            if range_width_atr < self.min_range_width_atr:
                score = 0  # Override - range too small
                reasons.append(f"Range {range_width_atr:.2f}× ATR < min {self.min_range_width_atr}")
            elif range_width_atr > 3.0:
                score = 0  # Override - range too large
                reasons.append(f"Range {range_width_atr:.2f}× ATR > 3.0 (too wide)")
            else:
                score += 1
                reasons.append(f"Range {range_width_atr:.2f}× ATR acceptable")
            
            # Determine if consolidation
            is_consolidation = score >= 3
            confidence = min(1.0, score / 5.0)
            
            rationale_text = "Consolidation " if is_consolidation else "No consolidation: "
            rationale_text += ", ".join(reasons)
            
            return ConsolidationDetection(
                is_consolidation=is_consolidation,
                range_high=range_high,
                range_low=range_low,
                range_width=range_width,
                range_width_atr=range_width_atr,
                bb_width=bb_width,
                adx=adx,
                confidence=confidence,
                rationale=rationale_text
            )
            
        except Exception as e:
            logger.error(f"Consolidation detection failed: {e}")
            return ConsolidationDetection(
                is_consolidation=False,
                range_high=0,
                range_low=0,
                range_width=0,
                range_width_atr=0,
                bb_width=0,
                adx=0,
                confidence=0,
                rationale=f"Detection error: {e}"
            )
    
    def _calculate_expiry(self, session: str, features: Dict[str, Any]) -> int:
        """Calculate expiry time based on session and market conditions."""
        # Base expiry
        expiry = self.default_expiry_minutes
        
        # Adjust by session
        if session == "LONDON_NY":
            # Peak liquidity, can wait longer
            expiry = 90
        elif session == "LONDON":
            expiry = 75
        elif session == "NY":
            expiry = 60
        else:
            expiry = 60  # Conservative for other sessions
        
        # Check time to session end
        minutes_to_session_end = features.get("minutes_to_session_end", 999)
        if minutes_to_session_end < expiry:
            # Don't extend beyond session
            expiry = max(30, minutes_to_session_end)
        
        return expiry
    
    def _create_invalid_result(
        self,
        skip_reasons: list,
        consolidation: Optional[ConsolidationDetection]
    ) -> OCOBracketResult:
        """Create an invalid OCO bracket result with skip reasons."""
        return OCOBracketResult(
            is_valid=False,
            buy_stop=0,
            buy_sl=0,
            buy_tp=0,
            buy_rr=0,
            sell_stop=0,
            sell_sl=0,
            sell_tp=0,
            sell_rr=0,
            range_high=consolidation.range_high if consolidation else 0,
            range_low=consolidation.range_low if consolidation else 0,
            bracket_distance_atr=self.bracket_distance_atr,
            expiry_minutes=0,
            consolidation_confidence=consolidation.confidence if consolidation else 0,
            rationale="OCO bracket not suitable",
            skip_reasons=skip_reasons
        )


def calculate_oco_bracket(
    features: Dict[str, Any],
    atr: float,
    session: str = "UNKNOWN",
    symbol: str = "",
    bracket_distance_atr: float = 0.2,
    sl_distance_atr: float = 1.0,
    min_rr: float = 2.0,
    min_range_width_atr: float = 0.5
) -> OCOBracketResult:
    """
    Convenience function to calculate OCO bracket.
    
    Args:
        features: Market features
        atr: ATR(14)
        session: Current session
        symbol: Trading symbol
        bracket_distance_atr: Distance from range edge
        sl_distance_atr: SL distance from entry
        min_rr: Minimum RR
        min_range_width_atr: Minimum range width
        
    Returns:
        OCOBracketResult with bracket levels or skip reasons
    """
    calculator = OCOBracketCalculator(
        bracket_distance_atr=bracket_distance_atr,
        sl_distance_atr=sl_distance_atr,
        min_rr=min_rr,
        min_range_width_atr=min_range_width_atr
    )
    return calculator.calculate_oco_bracket(features, atr, session, symbol)

