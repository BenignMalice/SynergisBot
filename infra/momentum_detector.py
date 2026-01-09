"""
Momentum Detector - Phase 4.4.2
Detects momentum state (strong/normal/fading) for adaptive TP and trailing stops.
"""

import logging
from typing import Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MomentumState(str, Enum):
    """Momentum state classifications."""
    STRONG = "strong"  # Expanding momentum - extend TP
    NORMAL = "normal"  # Steady momentum - standard TP
    FADING = "fading"  # Contracting momentum - reduce TP / tighten trail


@dataclass
class MomentumAnalysis:
    """Result of momentum analysis."""
    state: MomentumState
    score: int  # -3 to +3, higher = stronger momentum
    macd_score: int  # -1, 0, +1
    range_score: int  # -1, 0, +1
    volume_score: int  # -1, 0, +1
    atr_score: int  # 0 or +1
    confidence: float  # 0.0-1.0
    rationale: str


class MomentumDetector:
    """
    Detect momentum state using MACD, range expansion, volume, and ATR.
    Used for adaptive TP and momentum-aware trailing stops.
    """
    
    def __init__(
        self,
        macd_slope_strong: float = 0.2,
        macd_slope_weak: float = -0.1,
        range_expansion_strong: float = 1.2,
        range_contraction_weak: float = 0.8,
        volume_strong: float = 1.0,
        volume_weak: float = 0.0,
        atr_expansion: float = 1.15
    ):
        """
        Initialize momentum detector with thresholds.
        
        Args:
            macd_slope_strong: MACD histogram slope threshold for strong momentum
            macd_slope_weak: MACD histogram slope threshold for weak momentum
            range_expansion_strong: Range ratio threshold for expansion
            range_contraction_weak: Range ratio threshold for contraction
            volume_strong: Volume z-score threshold for strong
            volume_weak: Volume z-score threshold for weak
            atr_expansion: ATR ratio threshold for expansion
        """
        self.macd_slope_strong = macd_slope_strong
        self.macd_slope_weak = macd_slope_weak
        self.range_expansion_strong = range_expansion_strong
        self.range_contraction_weak = range_contraction_weak
        self.volume_strong = volume_strong
        self.volume_weak = volume_weak
        self.atr_expansion = atr_expansion
    
    def detect_momentum(self, features: Dict[str, Any]) -> MomentumAnalysis:
        """
        Detect current momentum state from market features.
        
        Args:
            features: Market features (MACD, range, volume, ATR)
            
        Returns:
            MomentumAnalysis with state and scoring breakdown
        """
        try:
            # Extract features
            macd_hist = features.get("macd_hist", 0.0)
            macd_hist_prev = features.get("macd_hist_prev", macd_hist)
            macd_hist_prev2 = features.get("macd_hist_prev2", macd_hist_prev)
            
            range_current = features.get("range_current", 1.0)
            range_median = features.get("range_median_20", 1.0)
            
            volume_z = features.get("volume_zscore", 0.0)
            
            atr_5 = features.get("atr_5", 1.0)
            atr_14 = features.get("atr_14", 1.0)
            
            # Calculate MACD histogram slope (3-bar)
            macd_slope = self._calculate_macd_slope(macd_hist, macd_hist_prev, macd_hist_prev2)
            
            # Calculate range ratio
            range_ratio = range_current / range_median if range_median > 0 else 1.0
            
            # Calculate ATR ratio
            atr_ratio = atr_5 / atr_14 if atr_14 > 0 else 1.0
            
            # Score each component
            macd_score = self._score_macd(macd_slope)
            range_score = self._score_range(range_ratio)
            volume_score = self._score_volume(volume_z)
            atr_score = self._score_atr(atr_ratio)
            
            # Total score
            total_score = macd_score + range_score + volume_score + atr_score
            
            # Determine state
            if total_score >= 2:
                state = MomentumState.STRONG
                confidence = min(1.0, 0.6 + (total_score / 10.0))
            elif total_score <= -2:
                state = MomentumState.FADING
                confidence = min(1.0, 0.6 + (abs(total_score) / 10.0))
            else:
                state = MomentumState.NORMAL
                confidence = 0.7
            
            # Build rationale
            rationale = self._build_rationale(macd_slope, range_ratio, volume_z, atr_ratio, state)
            
            return MomentumAnalysis(
                state=state,
                score=total_score,
                macd_score=macd_score,
                range_score=range_score,
                volume_score=volume_score,
                atr_score=atr_score,
                confidence=confidence,
                rationale=rationale
            )
            
        except Exception as e:
            logger.error(f"Momentum detection failed: {e}")
            return MomentumAnalysis(
                state=MomentumState.NORMAL,
                score=0,
                macd_score=0,
                range_score=0,
                volume_score=0,
                atr_score=0,
                confidence=0.5,
                rationale="Error in momentum detection, defaulting to normal"
            )
    
    def _calculate_macd_slope(self, current: float, prev: float, prev2: float) -> float:
        """Calculate 3-bar MACD histogram slope."""
        # Simple linear regression slope over 3 points
        # Using positions: 0, 1, 2 and values: prev2, prev, current
        # Slope = (3*Σxy - ΣxΣy) / (3*Σx² - (Σx)²)
        # Simplified for 3 points (0,1,2): slope = (current - prev2) / 2
        slope = (current - prev2) / 2.0
        return slope
    
    def _score_macd(self, slope: float) -> int:
        """Score MACD histogram slope."""
        if slope > self.macd_slope_strong:
            return +1  # Strong positive momentum
        elif slope < self.macd_slope_weak:
            return -1  # Weak/fading momentum
        else:
            return 0   # Normal momentum
    
    def _score_range(self, ratio: float) -> int:
        """Score range expansion/contraction."""
        if ratio > self.range_expansion_strong:
            return +1  # Range expanding
        elif ratio < self.range_contraction_weak:
            return -1  # Range contracting
        else:
            return 0   # Normal range
    
    def _score_volume(self, z_score: float) -> int:
        """Score volume activity."""
        if z_score > self.volume_strong:
            return +1  # High volume
        elif z_score < self.volume_weak:
            return -1  # Low volume
        else:
            return 0   # Normal volume
    
    def _score_atr(self, ratio: float) -> int:
        """Score ATR expansion (only positive)."""
        if ratio > self.atr_expansion:
            return +1  # ATR expanding (volatility increasing)
        else:
            return 0   # Normal or contracting ATR
    
    def _build_rationale(
        self,
        macd_slope: float,
        range_ratio: float,
        volume_z: float,
        atr_ratio: float,
        state: MomentumState
    ) -> str:
        """Build human-readable rationale for momentum state."""
        reasons = []
        
        if macd_slope > self.macd_slope_strong:
            reasons.append(f"MACD slope +{macd_slope:.2f}")
        elif macd_slope < self.macd_slope_weak:
            reasons.append(f"MACD slope {macd_slope:.2f}")
        
        if range_ratio > self.range_expansion_strong:
            reasons.append(f"Range expanding {range_ratio:.2f}×")
        elif range_ratio < self.range_contraction_weak:
            reasons.append(f"Range contracting {range_ratio:.2f}×")
        
        if volume_z > self.volume_strong:
            reasons.append(f"Volume high (z={volume_z:.1f})")
        elif volume_z < self.volume_weak:
            reasons.append(f"Volume low (z={volume_z:.1f})")
        
        if atr_ratio > self.atr_expansion:
            reasons.append(f"ATR expanding {atr_ratio:.2f}×")
        
        if reasons:
            return f"{state.value.capitalize()} momentum: {', '.join(reasons)}"
        else:
            return f"{state.value.capitalize()} momentum (neutral indicators)"


def detect_momentum(features: Dict[str, Any]) -> MomentumAnalysis:
    """
    Convenience function to detect momentum state.
    
    Args:
        features: Market features dictionary
        
    Returns:
        MomentumAnalysis with state and details
    """
    detector = MomentumDetector()
    return detector.detect_momentum(features)

