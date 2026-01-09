"""
Structure-Aware Stop Loss Anchoring - Phase 4.4.1
Anchors SL to market structure (swings, FVG, equal highs/lows, sweeps) to avoid premature stop-outs.
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class StructureAnchor:
    """Represents a structure level that can anchor a stop loss."""
    anchor_type: str  # "swing_low", "swing_high", "fvg_edge", "eq_lows", "eq_highs", "sweep_level"
    price: float
    confidence: float  # 0.0-1.0, how reliable is this anchor
    bars_ago: int
    description: str


@dataclass
class StructureSLResult:
    """Result of structure-aware SL calculation."""
    sl_price: float
    anchor_type: str
    anchor_price: float
    buffer_atr: float
    distance_atr: float  # Distance from entry in ATR
    confidence: float
    fallback_used: bool
    rationale: str


class StructureSLCalculator:
    """
    Calculate structure-aware stop losses using Phase 4.1 market structure features.
    Prioritizes: Swings → FVG edges → Equal highs/lows → Sweep levels
    """
    
    def __init__(self, buffer_multiplier: float = 0.1, min_distance_atr: float = 0.4, max_distance_atr: float = 1.5):
        """
        Initialize structure SL calculator.
        
        Args:
            buffer_multiplier: ATR multiplier for buffer beyond structure (default 0.1 = 10%)
            min_distance_atr: Minimum SL distance in ATR (default 0.4)
            max_distance_atr: Maximum SL distance in ATR (default 1.5)
        """
        self.buffer_multiplier = buffer_multiplier
        self.min_distance_atr = min_distance_atr
        self.max_distance_atr = max_distance_atr
    
    def calculate_structure_sl(
        self,
        entry: float,
        direction: str,  # "long" or "short"
        structure_features: Dict[str, Any],
        atr: float,
        current_price: Optional[float] = None
    ) -> StructureSLResult:
        """
        Calculate stop loss anchored to market structure.
        
        Args:
            entry: Entry price
            direction: Trade direction ("long" or "short")
            structure_features: Phase 4.1 structure features from M5 or chosen timeframe
            atr: ATR(14) for the timeframe
            current_price: Current market price (for validation)
            
        Returns:
            StructureSLResult with calculated SL and metadata
        """
        try:
            if current_price is None:
                current_price = entry
            
            # Find all potential anchors
            anchors = self._find_structure_anchors(entry, direction, structure_features, atr)
            
            if not anchors:
                # Fallback to ATR-based SL
                return self._fallback_sl(entry, direction, atr)
            
            # Select best anchor (nearest with highest confidence)
            best_anchor = self._select_best_anchor(anchors, entry, direction)
            
            # Calculate SL with buffer
            buffer = self.buffer_multiplier * atr
            
            if direction == "long":
                sl_price = best_anchor.price - buffer
            else:  # short
                sl_price = best_anchor.price + buffer
            
            # Validate distance
            distance = abs(entry - sl_price)
            distance_atr = distance / atr
            
            # Clamp to min/max distance
            if distance_atr < self.min_distance_atr:
                # Too tight, widen to min
                if direction == "long":
                    sl_price = entry - (self.min_distance_atr * atr)
                else:
                    sl_price = entry + (self.min_distance_atr * atr)
                distance_atr = self.min_distance_atr
                rationale = f"Widened to min {self.min_distance_atr}× ATR (structure too close)"
                
            elif distance_atr > self.max_distance_atr:
                # Too wide, narrow to max
                if direction == "long":
                    sl_price = entry - (self.max_distance_atr * atr)
                else:
                    sl_price = entry + (self.max_distance_atr * atr)
                distance_atr = self.max_distance_atr
                rationale = f"Narrowed to max {self.max_distance_atr}× ATR (structure too far)"
            else:
                rationale = f"Anchored to {best_anchor.anchor_type} at {best_anchor.price:.5f}"
            
            return StructureSLResult(
                sl_price=sl_price,
                anchor_type=best_anchor.anchor_type,
                anchor_price=best_anchor.price,
                buffer_atr=self.buffer_multiplier,
                distance_atr=distance_atr,
                confidence=best_anchor.confidence,
                fallback_used=False,
                rationale=rationale
            )
            
        except Exception as e:
            logger.error(f"Structure SL calculation failed: {e}")
            return self._fallback_sl(entry, direction, atr)
    
    def _find_structure_anchors(
        self,
        entry: float,
        direction: str,
        features: Dict[str, Any],
        atr: float
    ) -> List[StructureAnchor]:
        """Find all valid structure anchors for the given direction."""
        anchors = []
        
        if direction == "long":
            # Look for structure below entry
            
            # 1. Swing lows (highest priority)
            swing_lows = features.get("swing_lows", [])
            for swing in swing_lows[:3]:  # Check last 3 swings
                swing_price = swing.get("price", 0)
                swing_bars = swing.get("bars_ago", 999)
                if swing_price > 0 and swing_price < entry and swing_bars < 50:
                    anchors.append(StructureAnchor(
                        anchor_type="swing_low",
                        price=swing_price,
                        confidence=0.9,  # Highest confidence
                        bars_ago=swing_bars,
                        description=f"Swing low {swing_bars} bars ago"
                    ))
            
            # 2. FVG lower edge
            if features.get("fvg_bull", False):
                fvg_lower = features.get("fvg_zone_lower", 0)
                fvg_bars = features.get("fvg_bars_ago", 999)
                if fvg_lower > 0 and fvg_lower < entry and fvg_bars < 20:
                    anchors.append(StructureAnchor(
                        anchor_type="fvg_edge",
                        price=fvg_lower,
                        confidence=0.85,
                        bars_ago=fvg_bars,
                        description=f"Bullish FVG lower edge {fvg_bars} bars ago"
                    ))
            
            # 3. Equal lows cluster
            if features.get("eq_low_cluster", False):
                eq_low_price = features.get("eq_low_price", 0)
                eq_low_bars = features.get("eq_low_bars_ago", 999)
                if eq_low_price > 0 and eq_low_price < entry and eq_low_bars < 50:
                    anchors.append(StructureAnchor(
                        anchor_type="eq_lows",
                        price=eq_low_price,
                        confidence=0.80,
                        bars_ago=eq_low_bars,
                        description=f"Equal lows at {eq_low_price:.5f}"
                    ))
            
            # 4. Bearish sweep level (liquidity grabbed, then reversed)
            if features.get("sweep_bear", False):
                sweep_price = features.get("sweep_price", 0)
                sweep_bars = features.get("sweep_bars_ago", 999)
                if sweep_price > 0 and sweep_price < entry and sweep_bars < 10:
                    anchors.append(StructureAnchor(
                        anchor_type="sweep_level",
                        price=sweep_price,
                        confidence=0.75,
                        bars_ago=sweep_bars,
                        description=f"Bearish sweep at {sweep_price:.5f}"
                    ))
        
        else:  # short
            # Look for structure above entry
            
            # 1. Swing highs
            swing_highs = features.get("swing_highs", [])
            for swing in swing_highs[:3]:
                swing_price = swing.get("price", 0)
                swing_bars = swing.get("bars_ago", 999)
                if swing_price > 0 and swing_price > entry and swing_bars < 50:
                    anchors.append(StructureAnchor(
                        anchor_type="swing_high",
                        price=swing_price,
                        confidence=0.9,
                        bars_ago=swing_bars,
                        description=f"Swing high {swing_bars} bars ago"
                    ))
            
            # 2. FVG upper edge
            if features.get("fvg_bear", False):
                fvg_upper = features.get("fvg_zone_upper", 0)
                fvg_bars = features.get("fvg_bars_ago", 999)
                if fvg_upper > 0 and fvg_upper > entry and fvg_bars < 20:
                    anchors.append(StructureAnchor(
                        anchor_type="fvg_edge",
                        price=fvg_upper,
                        confidence=0.85,
                        bars_ago=fvg_bars,
                        description=f"Bearish FVG upper edge {fvg_bars} bars ago"
                    ))
            
            # 3. Equal highs cluster
            if features.get("eq_high_cluster", False):
                eq_high_price = features.get("eq_high_price", 0)
                eq_high_bars = features.get("eq_high_bars_ago", 999)
                if eq_high_price > 0 and eq_high_price > entry and eq_high_bars < 50:
                    anchors.append(StructureAnchor(
                        anchor_type="eq_highs",
                        price=eq_high_price,
                        confidence=0.80,
                        bars_ago=eq_high_bars,
                        description=f"Equal highs at {eq_high_price:.5f}"
                    ))
            
            # 4. Bullish sweep level
            if features.get("sweep_bull", False):
                sweep_price = features.get("sweep_price", 0)
                sweep_bars = features.get("sweep_bars_ago", 999)
                if sweep_price > 0 and sweep_price > entry and sweep_bars < 10:
                    anchors.append(StructureAnchor(
                        anchor_type="sweep_level",
                        price=sweep_price,
                        confidence=0.75,
                        bars_ago=sweep_bars,
                        description=f"Bullish sweep at {sweep_price:.5f}"
                    ))
        
        return anchors
    
    def _select_best_anchor(
        self,
        anchors: List[StructureAnchor],
        entry: float,
        direction: str
    ) -> StructureAnchor:
        """
        Select the best anchor from available options.
        Prioritizes: Nearest price + Highest confidence + Most recent
        """
        if not anchors:
            raise ValueError("No anchors available")
        
        # Score each anchor
        scored_anchors = []
        for anchor in anchors:
            distance = abs(entry - anchor.price)
            distance_score = 1.0 / (1.0 + distance)  # Closer = higher score
            
            recency_score = 1.0 / (1.0 + anchor.bars_ago / 20.0)  # More recent = higher score
            
            # Combined score (weighted)
            score = (
                anchor.confidence * 0.4 +  # 40% confidence
                distance_score * 0.4 +      # 40% proximity
                recency_score * 0.2         # 20% recency
            )
            
            scored_anchors.append((score, anchor))
        
        # Sort by score descending
        scored_anchors.sort(key=lambda x: x[0], reverse=True)
        
        return scored_anchors[0][1]  # Return best anchor
    
    def _fallback_sl(self, entry: float, direction: str, atr: float) -> StructureSLResult:
        """Fallback to ATR-based SL when no structure is available."""
        fallback_distance = 0.5  # 0.5× ATR
        
        if direction == "long":
            sl_price = entry - (fallback_distance * atr)
        else:
            sl_price = entry + (fallback_distance * atr)
        
        logger.warning(f"No structure anchors found, using fallback SL: {fallback_distance}× ATR")
        
        return StructureSLResult(
            sl_price=sl_price,
            anchor_type="fallback",
            anchor_price=entry,
            buffer_atr=0.0,
            distance_atr=fallback_distance,
            confidence=0.5,
            fallback_used=True,
            rationale=f"No structure found, fallback to {fallback_distance}× ATR"
        )


def calculate_structure_sl(
    entry: float,
    direction: str,
    structure_features: Dict[str, Any],
    atr: float,
    buffer_multiplier: float = 0.1,
    min_distance_atr: float = 0.4,
    max_distance_atr: float = 1.5
) -> StructureSLResult:
    """
    Convenience function to calculate structure-aware SL.
    
    Args:
        entry: Entry price
        direction: "long" or "short"
        structure_features: Phase 4.1 structure features
        atr: ATR(14)
        buffer_multiplier: Buffer beyond structure (default 0.1 = 10% ATR)
        min_distance_atr: Minimum SL distance (default 0.4)
        max_distance_atr: Maximum SL distance (default 1.5)
        
    Returns:
        StructureSLResult with calculated SL
    """
    calculator = StructureSLCalculator(buffer_multiplier, min_distance_atr, max_distance_atr)
    return calculator.calculate_structure_sl(entry, direction, structure_features, atr)

