"""
Adaptive Take Profit - Phase 4.4.2
Dynamically adjusts TP based on momentum state to capture runners or exit early when momentum fades.
"""

import logging
from typing import Dict, Any
from dataclasses import dataclass

from infra.momentum_detector import MomentumState, MomentumDetector, detect_momentum

logger = logging.getLogger(__name__)


@dataclass
class AdaptiveTPResult:
    """Result of adaptive TP calculation."""
    base_tp: float
    adaptive_tp: float
    momentum_state: str
    extension_factor: float
    base_rr: float
    adaptive_rr: float
    clamped: bool
    rationale: str


class AdaptiveTPCalculator:
    """
    Calculate adaptive take profit levels based on momentum.
    Strong momentum → Extend TP (capture runners)
    Fading momentum → Reduce TP (exit early)
    """
    
    def __init__(
        self,
        strong_extension: float = 1.5,    # Extend TP by 50%
        fading_reduction: float = 0.7,    # Reduce TP by 30%
        min_rr: float = 1.2,               # Minimum RR
        max_rr: float = 4.0                # Maximum RR
    ):
        """
        Initialize adaptive TP calculator.
        
        Args:
            strong_extension: Extension factor for strong momentum (1.5 = +50%)
            fading_reduction: Reduction factor for fading momentum (0.7 = -30%)
            min_rr: Minimum R:R ratio
            max_rr: Maximum R:R ratio
        """
        self.strong_extension = strong_extension
        self.fading_reduction = fading_reduction
        self.min_rr = min_rr
        self.max_rr = max_rr
        self.momentum_detector = MomentumDetector()
    
    def calculate_adaptive_tp(
        self,
        entry: float,
        sl: float,
        base_rr: float,
        direction: str,  # "long" or "short"
        features: Dict[str, Any]
    ) -> AdaptiveTPResult:
        """
        Calculate adaptive take profit based on momentum.
        
        Args:
            entry: Entry price
            sl: Stop loss price
            base_rr: Base risk:reward ratio (e.g., 2.0)
            direction: Trade direction ("long" or "short")
            features: Market features for momentum detection
            
        Returns:
            AdaptiveTPResult with base and adaptive TP levels
        """
        try:
            # Calculate base TP
            risk = abs(entry - sl)
            
            if direction == "long":
                base_tp = entry + (base_rr * risk)
            else:  # short
                base_tp = entry - (base_rr * risk)
            
            # Detect momentum
            momentum = self.momentum_detector.detect_momentum(features)
            
            # Determine extension factor
            if momentum.state == MomentumState.STRONG:
                extension_factor = self.strong_extension
            elif momentum.state == MomentumState.FADING:
                extension_factor = self.fading_reduction
            else:  # normal
                extension_factor = 1.0
            
            # Calculate adaptive TP
            if direction == "long":
                adaptive_tp = entry + (base_rr * extension_factor * risk)
            else:
                adaptive_tp = entry - (base_rr * extension_factor * risk)
            
            # Calculate adaptive RR
            adaptive_rr = base_rr * extension_factor
            
            # Clamp to min/max RR
            clamped = False
            if adaptive_rr < self.min_rr:
                adaptive_rr = self.min_rr
                if direction == "long":
                    adaptive_tp = entry + (adaptive_rr * risk)
                else:
                    adaptive_tp = entry - (adaptive_rr * risk)
                clamped = True
            elif adaptive_rr > self.max_rr:
                adaptive_rr = self.max_rr
                if direction == "long":
                    adaptive_tp = entry + (adaptive_rr * risk)
                else:
                    adaptive_tp = entry - (adaptive_rr * risk)
                clamped = True
            
            # Build rationale
            rationale = self._build_rationale(
                momentum, base_rr, adaptive_rr, extension_factor, clamped
            )
            
            return AdaptiveTPResult(
                base_tp=base_tp,
                adaptive_tp=adaptive_tp,
                momentum_state=momentum.state.value,
                extension_factor=extension_factor,
                base_rr=base_rr,
                adaptive_rr=adaptive_rr,
                clamped=clamped,
                rationale=rationale
            )
            
        except Exception as e:
            logger.error(f"Adaptive TP calculation failed: {e}")
            # Fallback to base TP
            return AdaptiveTPResult(
                base_tp=base_tp if 'base_tp' in locals() else entry,
                adaptive_tp=base_tp if 'base_tp' in locals() else entry,
                momentum_state="normal",
                extension_factor=1.0,
                base_rr=base_rr,
                adaptive_rr=base_rr,
                clamped=False,
                rationale="Error in adaptive TP, using base TP"
            )
    
    def _build_rationale(
        self,
        momentum: Any,
        base_rr: float,
        adaptive_rr: float,
        extension_factor: float,
        clamped: bool
    ) -> str:
        """Build rationale for adaptive TP."""
        if momentum.state == MomentumState.STRONG:
            msg = f"Extended TP {base_rr:.1f}R → {adaptive_rr:.1f}R (×{extension_factor:.2f}) - {momentum.rationale}"
        elif momentum.state == MomentumState.FADING:
            msg = f"Reduced TP {base_rr:.1f}R → {adaptive_rr:.1f}R (×{extension_factor:.2f}) - {momentum.rationale}"
        else:
            msg = f"Standard TP {base_rr:.1f}R (normal momentum)"
        
        if clamped:
            msg += f" [clamped to {self.min_rr:.1f}-{self.max_rr:.1f}R range]"
        
        return msg


def calculate_adaptive_tp(
    entry: float,
    sl: float,
    base_rr: float,
    direction: str,
    features: Dict[str, Any],
    strong_extension: float = 1.5,
    fading_reduction: float = 0.7,
    min_rr: float = 1.2,
    max_rr: float = 4.0
) -> AdaptiveTPResult:
    """
    Convenience function to calculate adaptive TP.
    
    Args:
        entry: Entry price
        sl: Stop loss price
        base_rr: Base risk:reward ratio
        direction: Trade direction ("long" or "short")
        features: Market features for momentum detection
        strong_extension: Extension factor for strong momentum
        fading_reduction: Reduction factor for fading momentum
        min_rr: Minimum RR
        max_rr: Maximum RR
        
    Returns:
        AdaptiveTPResult with calculated TP levels
    """
    calculator = AdaptiveTPCalculator(strong_extension, fading_reduction, min_rr, max_rr)
    return calculator.calculate_adaptive_tp(entry, sl, base_rr, direction, features)

