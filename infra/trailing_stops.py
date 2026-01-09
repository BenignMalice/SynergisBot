"""
Momentum-Aware Trailing Stops - Phase 4.4.3
Intelligently trails stops based on momentum state and market structure.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from infra.momentum_detector import MomentumState, MomentumDetector

logger = logging.getLogger(__name__)


@dataclass
class TrailingStopResult:
    """Result of trailing stop calculation."""
    new_sl: float
    trail_method: str  # "wide" | "standard" | "tight" | "no_trail"
    momentum_state: str
    unrealized_r: float
    trail_distance_atr: float
    structure_anchor: Optional[str]
    trailed: bool  # Whether SL was actually moved
    rationale: str


class TrailingStopCalculator:
    """
    Calculate momentum-aware trailing stops.
    Wide trail when momentum strong, tight trail when fading, standard otherwise.
    Integrates with Phase 4.1 structure features for anchor points.
    """
    
    def __init__(
        self,
        trigger_r: float = 1.0,           # Only trail after 1R profit
        wide_trail_atr: float = 2.0,      # Wide trail: 2× ATR below current
        standard_trail_atr: float = 1.5,  # Standard trail: 1.5× ATR below current
        tight_trail_r: float = 0.5,       # Tight trail: Breakeven + 0.5R
        min_trail_distance: float = 0.3   # Min distance to trail (× ATR)
    ):
        """
        Initialize trailing stop calculator.
        
        Args:
            trigger_r: Minimum profit (in R) before trailing starts
            wide_trail_atr: ATR multiplier for wide trail (strong momentum)
            standard_trail_atr: ATR multiplier for standard trail (normal momentum)
            tight_trail_r: R multiplier for tight trail (fading momentum)
            min_trail_distance: Minimum distance to trail (× ATR)
        """
        self.trigger_r = trigger_r
        self.wide_trail_atr = wide_trail_atr
        self.standard_trail_atr = standard_trail_atr
        self.tight_trail_r = tight_trail_r
        self.min_trail_distance = min_trail_distance
        self.momentum_detector = MomentumDetector()
    
    def calculate_trailing_stop(
        self,
        entry: float,
        current_sl: float,
        current_price: float,
        direction: str,  # "long" or "short"
        atr: float,
        features: Dict[str, Any],
        structure: Optional[Dict[str, Any]] = None
    ) -> TrailingStopResult:
        """
        Calculate new trailing stop based on momentum and structure.
        
        Args:
            entry: Entry price
            current_sl: Current stop loss
            current_price: Current market price
            direction: Trade direction ("long" or "short")
            atr: ATR(14) for the timeframe
            features: Market features for momentum detection
            structure: Optional Phase 4.1 structure features for anchoring
            
        Returns:
            TrailingStopResult with new SL and details
        """
        try:
            # Calculate unrealized profit in R
            risk = abs(entry - current_sl)
            if direction == "long":
                unrealized_profit = current_price - entry
            else:  # short
                unrealized_profit = entry - current_price
            
            unrealized_r = unrealized_profit / risk if risk > 0 else 0.0
            
            # Check if we should trail (must be above trigger)
            if unrealized_r < self.trigger_r:
                return TrailingStopResult(
                    new_sl=current_sl,
                    trail_method="no_trail",
                    momentum_state="n/a",
                    unrealized_r=unrealized_r,
                    trail_distance_atr=0.0,
                    structure_anchor=None,
                    trailed=False,
                    rationale=f"No trail: profit {unrealized_r:.2f}R < trigger {self.trigger_r}R"
                )
            
            # Detect momentum
            momentum = self.momentum_detector.detect_momentum(features)
            
            # Calculate new SL based on momentum
            if momentum.state == MomentumState.STRONG:
                # Wide trail - let it run
                new_sl, trail_method, distance = self._calculate_wide_trail(
                    current_price, direction, atr, structure
                )
            elif momentum.state == MomentumState.FADING:
                # Tight trail - lock in profit
                new_sl, trail_method, distance = self._calculate_tight_trail(
                    entry, current_sl, risk, direction
                )
            else:  # NORMAL
                # Standard trail
                new_sl, trail_method, distance = self._calculate_standard_trail(
                    current_price, direction, atr, structure
                )
            
            # Validate: never trail backwards (worse than current SL)
            if direction == "long":
                if new_sl <= current_sl:
                    new_sl = current_sl
                    trailed = False
                else:
                    trailed = True
            else:  # short
                if new_sl >= current_sl:
                    new_sl = current_sl
                    trailed = False
                else:
                    trailed = True
            
            # Check minimum trail distance
            trail_distance = abs(new_sl - current_sl)
            min_trail = self.min_trail_distance * atr
            
            if trailed and trail_distance < min_trail:
                # Too small to trail
                new_sl = current_sl
                trailed = False
                rationale = f"Trail distance {trail_distance:.5f} < min {min_trail:.5f}, keeping current SL"
            else:
                if trailed:
                    rationale = f"{trail_method.capitalize()} trail: SL {current_sl:.5f} → {new_sl:.5f} ({momentum.state.value} momentum)"
                else:
                    rationale = f"No improvement: {trail_method} would give {new_sl:.5f} (current {current_sl:.5f})"
            
            # Find structure anchor if used
            structure_anchor = self._identify_structure_anchor(new_sl, structure, direction) if structure and trailed else None
            
            return TrailingStopResult(
                new_sl=new_sl,
                trail_method=trail_method,
                momentum_state=momentum.state.value,
                unrealized_r=unrealized_r,
                trail_distance_atr=distance,
                structure_anchor=structure_anchor,
                trailed=trailed,
                rationale=rationale
            )
            
        except Exception as e:
            logger.error(f"Trailing stop calculation failed: {e}")
            return TrailingStopResult(
                new_sl=current_sl,
                trail_method="error",
                momentum_state="unknown",
                unrealized_r=0.0,
                trail_distance_atr=0.0,
                structure_anchor=None,
                trailed=False,
                rationale=f"Error in trailing stop calculation: {e}"
            )
    
    def _calculate_wide_trail(
        self,
        current_price: float,
        direction: str,
        atr: float,
        structure: Optional[Dict[str, Any]]
    ) -> tuple[float, str, float]:
        """Calculate wide trail for strong momentum."""
        # Use SuperTrend band or Keltner upper/lower if available
        if structure:
            if direction == "long" and structure.get("supertrend_band"):
                return structure["supertrend_band"], "wide_structure", self.wide_trail_atr
            elif direction == "short" and structure.get("supertrend_band"):
                return structure["supertrend_band"], "wide_structure", self.wide_trail_atr
        
        # Fallback to ATR-based
        if direction == "long":
            new_sl = current_price - (self.wide_trail_atr * atr)
        else:
            new_sl = current_price + (self.wide_trail_atr * atr)
        
        return new_sl, "wide", self.wide_trail_atr
    
    def _calculate_standard_trail(
        self,
        current_price: float,
        direction: str,
        atr: float,
        structure: Optional[Dict[str, Any]]
    ) -> tuple[float, str, float]:
        """Calculate standard trail for normal momentum."""
        # Use EMA20 or standard ATR trail
        if structure:
            ema20 = structure.get("ema20")
            if ema20:
                if direction == "long" and ema20 < current_price:
                    return ema20, "standard_ema20", self.standard_trail_atr
                elif direction == "short" and ema20 > current_price:
                    return ema20, "standard_ema20", self.standard_trail_atr
        
        # Fallback to ATR-based
        if direction == "long":
            new_sl = current_price - (self.standard_trail_atr * atr)
        else:
            new_sl = current_price + (self.standard_trail_atr * atr)
        
        return new_sl, "standard", self.standard_trail_atr
    
    def _calculate_tight_trail(
        self,
        entry: float,
        current_sl: float,
        risk: float,
        direction: str
    ) -> tuple[float, str, float]:
        """Calculate tight trail for fading momentum."""
        # Move to breakeven + 0.5R
        if direction == "long":
            new_sl = entry + (self.tight_trail_r * risk)
        else:
            new_sl = entry - (self.tight_trail_r * risk)
        
        return new_sl, "tight", self.tight_trail_r
    
    def _identify_structure_anchor(
        self,
        sl_price: float,
        structure: Dict[str, Any],
        direction: str
    ) -> Optional[str]:
        """Identify which structure feature the SL is near."""
        tolerance = 0.0001  # 0.01%
        
        # Check various structure anchors
        if structure.get("ema20"):
            if abs(sl_price - structure["ema20"]) / sl_price < tolerance:
                return "ema20"
        
        if structure.get("supertrend_band"):
            if abs(sl_price - structure["supertrend_band"]) / sl_price < tolerance:
                return "supertrend"
        
        # Check swings
        if direction == "long":
            swings = structure.get("swing_lows", [])
            for swing in swings[:2]:
                if abs(sl_price - swing.get("price", 0)) / sl_price < tolerance:
                    return "swing_low"
        else:
            swings = structure.get("swing_highs", [])
            for swing in swings[:2]:
                if abs(sl_price - swing.get("price", 0)) / sl_price < tolerance:
                    return "swing_high"
        
        # Check FVG
        if direction == "long" and structure.get("fvg_bull"):
            fvg_lower = structure.get("fvg_zone_lower", 0)
            if abs(sl_price - fvg_lower) / sl_price < tolerance:
                return "fvg_edge"
        elif direction == "short" and structure.get("fvg_bear"):
            fvg_upper = structure.get("fvg_zone_upper", 0)
            if abs(sl_price - fvg_upper) / sl_price < tolerance:
                return "fvg_edge"
        
        return None


def calculate_trailing_stop(
    entry: float,
    current_sl: float,
    current_price: float,
    direction: str,
    atr: float,
    features: Dict[str, Any],
    structure: Optional[Dict[str, Any]] = None,
    trigger_r: float = 1.0,
    wide_trail_atr: float = 2.0,
    standard_trail_atr: float = 1.5,
    tight_trail_r: float = 0.5
) -> TrailingStopResult:
    """
    Convenience function to calculate trailing stop.
    
    Args:
        entry: Entry price
        current_sl: Current stop loss
        current_price: Current market price
        direction: Trade direction ("long" or "short")
        atr: ATR(14)
        features: Market features for momentum detection
        structure: Optional structure features for anchoring
        trigger_r: Minimum profit before trailing (default 1.0R)
        wide_trail_atr: Wide trail multiplier (default 2.0)
        standard_trail_atr: Standard trail multiplier (default 1.5)
        tight_trail_r: Tight trail multiplier (default 0.5R)
        
    Returns:
        TrailingStopResult with new SL
    """
    calculator = TrailingStopCalculator(trigger_r, wide_trail_atr, standard_trail_atr, tight_trail_r)
    return calculator.calculate_trailing_stop(entry, current_sl, current_price, direction, atr, features, structure)

