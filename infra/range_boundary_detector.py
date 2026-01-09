"""
Range Boundary Detector
Detects session, daily, and dynamic ranges for range scalping strategies.

Implements:
- Range detection (session, daily, dynamic micro-ranges)
- Critical gap calculation (0.15× range zones)
- Range expansion/contraction detection
- Range invalidation detection
- Nested range detection (H1/M15/M5 hierarchy)
- Imbalanced consolidation detection (false ranges)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

from domain.zones import find_swings, Pivot
from domain.market_structure import detect_bos_choch, label_swings, StructurePoint

logger = logging.getLogger(__name__)


@dataclass
class CriticalGapZones:
    """
    Critical gap zones where balance turns into imbalance.
    
    Calculated as 0.15 × range_width from each edge.
    These zones represent high-probability reversal areas.
    """
    upper_zone_start: float  # range_high - 0.15 * range_width
    upper_zone_end: float    # range_high
    lower_zone_start: float  # range_low
    lower_zone_end: float    # range_low + 0.15 * range_width


@dataclass
class RangeStructure:
    """
    Represents a detected trading range.
    
    Used for range scalping entry logic and state persistence.
    """
    range_type: str  # "session", "daily", "dynamic"
    range_high: float
    range_low: float
    range_mid: float  # VWAP (typically)
    range_width_atr: float
    critical_gaps: CriticalGapZones
    touch_count: Dict[str, int] = field(default_factory=dict)
    validated: bool = False  # No BOS/CHOCH inside
    nested_ranges: Optional[Dict[str, 'RangeStructure']] = None
    expansion_state: str = "stable"  # "forming", "expanding", "contracting", "stable"
    invalidation_signals: List[str] = field(default_factory=list)  # Risk flags detected
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to JSON-serializable dict for persistence.
        Required for trade registration and state recovery.
        """
        return {
            "range_type": self.range_type,
            "range_high": self.range_high,
            "range_low": self.range_low,
            "range_mid": self.range_mid,
            "range_width_atr": self.range_width_atr,
            "critical_gaps": {
                "upper_zone_start": self.critical_gaps.upper_zone_start,
                "upper_zone_end": self.critical_gaps.upper_zone_end,
                "lower_zone_start": self.critical_gaps.lower_zone_start,
                "lower_zone_end": self.critical_gaps.lower_zone_end
            },
            "touch_count": self.touch_count,
            "validated": self.validated,
            "nested_ranges": {
                tf: r.to_dict() for tf, r in (self.nested_ranges or {}).items()
            } if self.nested_ranges else None,
            "expansion_state": self.expansion_state,
            "invalidation_signals": self.invalidation_signals
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RangeStructure':
        """Reconstruct from dict (for state recovery)"""
        nested = None
        if "nested_ranges" in data and data["nested_ranges"]:
            nested = {
                tf: cls.from_dict(r_data)
                for tf, r_data in data["nested_ranges"].items()
            }
        
        return cls(
            range_type=data["range_type"],
            range_high=data["range_high"],
            range_low=data["range_low"],
            range_mid=data["range_mid"],
            range_width_atr=data["range_width_atr"],
            critical_gaps=CriticalGapZones(**data["critical_gaps"]),
            touch_count=data.get("touch_count", {}),
            validated=data.get("validated", False),
            nested_ranges=nested,
            expansion_state=data.get("expansion_state", "stable"),
            invalidation_signals=data.get("invalidation_signals", [])
        )


class RangeBoundaryDetector:
    """
    Detects and manages range boundaries for range scalping strategies.
    
    Supports:
    - Session ranges (based on trading session boundaries)
    - Daily ranges (PDH/PDL based)
    - Dynamic micro-ranges (swing-based, local consolidation)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize range boundary detector.
        
        Args:
            config: Optional configuration dict
        """
        self.config = config or {}
        self.critical_gap_multiplier = self.config.get("critical_gap_multiplier", 0.15)
        
    def calculate_critical_gaps(
        self,
        range_high: float,
        range_low: float
    ) -> CriticalGapZones:
        """
        Calculate critical gap zones (0.15× range_width from edges).
        
        Critical gaps are micro-zones where balance turns into imbalance.
        These represent high-probability reversal areas for range scalping.
        
        Args:
            range_high: Upper boundary of range
            range_low: Lower boundary of range
            
        Returns:
            CriticalGapZones with upper and lower zones
        """
        range_width = range_high - range_low
        gap_size = range_width * self.critical_gap_multiplier
        
        return CriticalGapZones(
            upper_zone_start=range_high - gap_size,
            upper_zone_end=range_high,
            lower_zone_start=range_low,
            lower_zone_end=range_low + gap_size
        )
    
    def detect_range(
        self,
        symbol: str,
        timeframe: str,
        range_type: str = "dynamic",
        candles_df: Optional[pd.DataFrame] = None,
        session_high: Optional[float] = None,
        session_low: Optional[float] = None,
        pdh: Optional[float] = None,
        pdl: Optional[float] = None,
        vwap: Optional[float] = None,
        atr: Optional[float] = None,
        session_start_time: Optional[datetime] = None
    ) -> Optional[RangeStructure]:
        """
        Detect range based on type (session, daily, dynamic).
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe for analysis (M5, M15, H1)
            range_type: "session", "daily", or "dynamic"
            candles_df: DataFrame with OHLC data (required for dynamic)
            session_high: Session high price (for session range)
            session_low: Session low price (for session range)
            pdh: Previous day high (for daily range)
            pdl: Previous day low (for daily range)
            vwap: Volume-weighted average price (for range_mid)
            atr: Average True Range (for range_width_atr)
            session_start_time: Optional datetime to filter candles to current session only (for session range)
            
        Returns:
            RangeStructure if range detected, None otherwise
        """
        if range_type == "session":
            return self._detect_session_range(
                symbol, timeframe, session_high, session_low, vwap, atr, candles_df, session_start_time
            )
        elif range_type == "daily":
            return self._detect_daily_range(
                symbol, timeframe, pdh, pdl, vwap, atr
            )
        elif range_type == "dynamic":
            return self._detect_dynamic_range(
                symbol, timeframe, candles_df, vwap, atr
            )
        else:
            logger.warning(f"Unknown range_type: {range_type}")
            return None
    
    def _detect_session_range(
        self,
        symbol: str,
        timeframe: str,
        session_high: Optional[float],
        session_low: Optional[float],
        vwap: Optional[float],
        atr: Optional[float],
        candles_df: Optional[pd.DataFrame] = None,
        session_start_time: Optional[datetime] = None
    ) -> Optional[RangeStructure]:
        """
        Detect session-based range
        
        Args:
            session_start_time: Optional datetime to filter candles to current session only.
                              If not provided and candles_df has datetime index, uses current session estimation.
        """
        if session_high is None or session_low is None:
            logger.warning(f"Cannot detect session range: missing session high/low")
            return None
        
        if vwap is None:
            vwap = (session_high + session_low) / 2.0
        
        if atr is None:
            # Estimate ATR from range width
            range_width = session_high - session_low
            atr = range_width / 3.0  # Rough estimate
        
        critical_gaps = self.calculate_critical_gaps(session_high, session_low)
        
        # Count actual touches from candles if available
        if candles_df is not None and not candles_df.empty:
            # Filter to current session only if session_start_time provided
            touch_counting_df = candles_df
            if session_start_time is not None:
                # Filter DataFrame to only include candles from session start onwards
                if hasattr(candles_df.index, 'tz_localize') or candles_df.index.tz is not None:
                    # Timezone-aware index
                    touch_counting_df = candles_df[candles_df.index >= session_start_time]
                else:
                    # Timezone-naive index - assume UTC
                    # timezone is already imported at top of file
                    session_start_tz = session_start_time
                    if session_start_time.tzinfo is None:
                        session_start_tz = session_start_time.replace(tzinfo=timezone.utc)
                    touch_counting_df = candles_df[candles_df.index >= session_start_tz]
                
                if touch_counting_df.empty:
                    logger.debug(f"No candles found for session starting at {session_start_time}, using full DataFrame")
                    touch_counting_df = candles_df
            
            # Log how many candles we're analyzing
            total_candles = len(candles_df)
            session_candles = len(touch_counting_df) if session_start_time else total_candles
            logger.debug(f"Counting touches: {session_candles}/{total_candles} candles (session-filtered: {session_start_time is not None})")
            
            touch_count_dict = self._count_range_touches(touch_counting_df, session_high, session_low)
            # Convert to expected format (upper_touches/lower_touches instead of high_touches/low_touches)
            touch_count = {
                "total_touches": touch_count_dict.get("total_touches", 0),
                "upper_touches": touch_count_dict.get("high_touches", 0),
                "lower_touches": touch_count_dict.get("low_touches", 0)
            }
        else:
            # Fallback: estimate based on range width
            range_width = session_high - session_low
            estimated = max(2, int(range_width / (atr * 0.2))) if atr > 0 else 2
            touch_count = {
                "total_touches": estimated,
                "upper_touches": estimated // 2,
                "lower_touches": estimated // 2
            }
        
        return RangeStructure(
            range_type="session",
            range_high=session_high,
            range_low=session_low,
            range_mid=vwap,
            range_width_atr=atr,
            critical_gaps=critical_gaps,
            touch_count=touch_count,  # Use calculated/estimated value instead of {}
            validated=False,  # Will be validated by validate_range_integrity()
            nested_ranges=None,
            expansion_state="stable",
            invalidation_signals=[]
        )
    
    def _detect_daily_range(
        self,
        symbol: str,
        timeframe: str,
        pdh: Optional[float],
        pdl: Optional[float],
        vwap: Optional[float],
        atr: Optional[float]
    ) -> Optional[RangeStructure]:
        """Detect daily range based on PDH/PDL"""
        if pdh is None or pdl is None:
            logger.warning(f"Cannot detect daily range: missing PDH/PDL")
            return None
        
        if vwap is None:
            vwap = (pdh + pdl) / 2.0
        
        if atr is None or atr == 0:
            range_width = pdh - pdl
            atr = range_width / 3.0
        
        critical_gaps = self.calculate_critical_gaps(pdh, pdl)
        
        # Estimate touch count from range width (for initial scoring)
        # In a real scenario, this would be calculated from historical touches
        estimated_touches = 2  # Conservative estimate for daily range
        
        return RangeStructure(
            range_type="daily",
            range_high=pdh,
            range_low=pdl,
            range_mid=vwap,
            range_width_atr=atr,
            critical_gaps=critical_gaps,
            touch_count={"total_touches": estimated_touches, "upper_touches": 1, "lower_touches": 1},
            validated=False,
            nested_ranges=None,
            expansion_state="stable",
            invalidation_signals=[]
        )
    
    def _detect_dynamic_range(
        self,
        symbol: str,
        timeframe: str,
        candles_df: Optional[pd.DataFrame],
        vwap: Optional[float],
        atr: Optional[float]
    ) -> Optional[RangeStructure]:
        """Detect dynamic micro-range using swing detection"""
        if candles_df is None or candles_df.empty:
            logger.warning(f"Cannot detect dynamic range: missing candle data")
            return None
        
        # Use find_swings to detect swing highs and lows
        try:
            pivots = find_swings(candles_df, left=3, right=3)
            
            if len(pivots) < 2:
                logger.debug(f"Insufficient pivots ({len(pivots)}) for range detection")
                return None
            
            # Find most recent swing high and low
            swing_highs = [p for p in pivots if p.kind == "H"]
            swing_lows = [p for p in pivots if p.kind == "L"]
            
            if not swing_highs or not swing_lows:
                logger.debug("No swing highs or lows detected")
                return None
            
            # Get most recent swings
            latest_high = max(swing_highs, key=lambda p: p.idx)
            latest_low = max(swing_lows, key=lambda p: p.idx)
            
            range_high = latest_high.price
            range_low = latest_low.price
            
            # Validate range (must have some width)
            range_width = range_high - range_low
            if range_width <= 0:
                logger.debug("Invalid range: high <= low")
                return None
            
            if vwap is None:
                # Calculate approximate VWAP from candles
                typical_prices = (candles_df['high'] + candles_df['low'] + candles_df['close']) / 3
                volumes = candles_df.get('volume', candles_df.get('tick_volume', pd.Series([1] * len(candles_df))))
                vwap = (typical_prices * volumes).sum() / volumes.sum() if volumes.sum() > 0 else (range_high + range_low) / 2
            
            if atr is None:
                # Calculate ATR from candles
                high_low = candles_df['high'] - candles_df['low']
                high_close_prev = abs(candles_df['high'] - candles_df['close'].shift(1))
                low_close_prev = abs(candles_df['low'] - candles_df['close'].shift(1))
                true_range = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
                atr = true_range.tail(14).mean() if len(true_range) >= 14 else range_width / 3.0
            
            critical_gaps = self.calculate_critical_gaps(range_high, range_low)
            
            # For dynamic ranges, limit touch counting to last 48 hours for relevance
            # (older touches don't reflect current range behavior)
            touch_counting_df = candles_df
            if candles_df is not None and not candles_df.empty:
                # timezone is already imported at top of file
                now_utc = datetime.now(timezone.utc)
                cutoff_time = now_utc - timedelta(hours=48)
                
                # Check if DataFrame index is timezone-aware
                index_is_tz_aware = hasattr(candles_df.index, 'tz') and candles_df.index.tz is not None
                
                if index_is_tz_aware:
                    # Timezone-aware index - use timezone-aware cutoff_time
                    touch_counting_df = candles_df[candles_df.index >= cutoff_time]
                else:
                    # Timezone-naive index - convert cutoff_time to naive (assume UTC)
                    cutoff_time_naive = cutoff_time.replace(tzinfo=None)
                    touch_counting_df = candles_df[candles_df.index >= cutoff_time_naive]
                
                if touch_counting_df.empty:
                    logger.debug(f"No candles found in last 48 hours, using full DataFrame")
                    touch_counting_df = candles_df
                
                total_candles = len(candles_df)
                recent_candles = len(touch_counting_df)
                logger.debug(f"Dynamic range touch counting: {recent_candles}/{total_candles} candles (last 48h)")
            
            # Count touches of range boundaries (using filtered DataFrame)
            touch_count = self._count_range_touches(touch_counting_df, range_high, range_low)
            
            return RangeStructure(
                range_type="dynamic",
                range_high=range_high,
                range_low=range_low,
                range_mid=vwap,
                range_width_atr=atr,
                critical_gaps=critical_gaps,
                touch_count=touch_count,
                validated=False,
                nested_ranges=None,
                expansion_state="stable",
                invalidation_signals=[]
            )
            
        except Exception as e:
            logger.error(f"Error detecting dynamic range: {e}", exc_info=True)
            return None
    
    def _count_range_touches(
        self,
        candles_df: pd.DataFrame,
        range_high: float,
        range_low: float,
        tolerance_pct: float = 0.002  # 0.2% tolerance
    ) -> Dict[str, int]:
        """
        Count distinct touch events where price approaches and bounces from range boundaries.
        
        Only counts touches where:
        - Price approaches boundary (within tolerance)
        - Price bounces back (close is inside range or near boundary)
        - Not counting continuous breakouts (close outside range = invalidation, not touch)
        
        Returns:
            Dict with "high_touches", "low_touches", and "total_touches"
        """
        tolerance_high = range_high * tolerance_pct
        tolerance_low = range_low * tolerance_pct
        
        high_touches = 0
        low_touches = 0
        
        prev_high_touched = False
        prev_low_touched = False
        
        for idx, row in candles_df.iterrows():
            high = row['high']
            low = row['low']
            close = row['close']
            
            # Check if high touched upper boundary (within tolerance)
            high_touches_boundary = abs(high - range_high) <= tolerance_high
            
            # Check if price bounced back from upper boundary (close inside range)
            # Allow small overshoot but require close to be near or inside range
            close_inside_range = close <= range_high + tolerance_high
            
            # Only count as touch if:
            # 1. High touched boundary (within tolerance)
            # 2. Close bounced back (not a breakout)
            # 3. This is a new touch event (not consecutive)
            if high_touches_boundary and close_inside_range and not prev_high_touched:
                high_touches += 1
                prev_high_touched = True
            elif not high_touches_boundary:
                prev_high_touched = False
            
            # Check if low touched lower boundary (within tolerance)
            low_touches_boundary = abs(low - range_low) <= tolerance_low
            
            # Check if price bounced back from lower boundary (close inside range)
            close_inside_range_low = close >= range_low - tolerance_low
            
            # Only count as touch if:
            # 1. Low touched boundary (within tolerance)
            # 2. Close bounced back (not a breakout)
            # 3. This is a new touch event (not consecutive)
            if low_touches_boundary and close_inside_range_low and not prev_low_touched:
                low_touches += 1
                prev_low_touched = True
            elif not low_touches_boundary:
                prev_low_touched = False
        
        return {
            "high_touches": high_touches,
            "low_touches": low_touches,
            "total_touches": high_touches + low_touches
        }
    
    def check_range_expansion(
        self,
        range_data: RangeStructure,
        candles_df: Optional[pd.DataFrame] = None,
        bb_width: Optional[float] = None,
        atr: Optional[float] = None,
        historical_atr_avg: Optional[float] = None,
        historical_bb_width_avg: Optional[float] = None
    ) -> str:
        """
        Check if range is expanding, contracting, or stable.
        
        Uses Bollinger Band Width and ATR to detect expansion/contraction.
        
        Args:
            range_data: RangeStructure to analyze
            candles_df: Optional DataFrame with OHLC data for calculation
            bb_width: Optional current BB width (if None, will calculate from candles_df)
            atr: Optional current ATR (if None, will calculate from candles_df)
            historical_atr_avg: Optional historical ATR average for comparison
            historical_bb_width_avg: Optional historical BB width average for comparison
            
        Returns:
            "forming", "expanding", "contracting", or "stable"
        """
        try:
            # Calculate current volatility metrics if not provided
            current_atr = atr
            current_bb_width = bb_width
            
            if candles_df is not None and len(candles_df) >= 20:
                # Calculate ATR if not provided
                if current_atr is None:
                    high_low = candles_df['high'] - candles_df['low']
                    high_close_prev = abs(candles_df['high'] - candles_df['close'].shift(1))
                    low_close_prev = abs(candles_df['low'] - candles_df['close'].shift(1))
                    true_range = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
                    current_atr = true_range.tail(14).mean() if len(true_range) >= 14 else None
                
                # Calculate BB width if not provided
                if current_bb_width is None:
                    bb_period = 20
                    bb_std = 2.0
                    sma = candles_df['close'].rolling(window=bb_period).mean()
                    std = candles_df['close'].rolling(window=bb_period).std()
                    
                    if len(sma) > 0 and len(std) > 0 and not pd.isna(sma.iloc[-1]) and not pd.isna(std.iloc[-1]):
                        bb_upper = sma.iloc[-1] + (std.iloc[-1] * bb_std)
                        bb_lower = sma.iloc[-1] - (std.iloc[-1] * bb_std)
                        current_bb_width = bb_upper - bb_lower
                    else:
                        current_bb_width = None
            
            # Calculate historical averages if not provided
            if candles_df is not None and len(candles_df) >= 40:
                # Calculate historical ATR average (from bars 20-40 periods ago)
                if historical_atr_avg is None and current_atr is not None:
                    high_low = candles_df['high'] - candles_df['low']
                    high_close_prev = abs(candles_df['high'] - candles_df['close'].shift(1))
                    low_close_prev = abs(candles_df['low'] - candles_df['close'].shift(1))
                    true_range = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
                    
                    # Get historical window (20-40 bars ago, or more if available)
                    if len(true_range) >= 40:
                        historical_window = true_range.iloc[-40:-20]
                        historical_atr_avg = historical_window.mean()
                    elif len(true_range) >= 30:
                        historical_window = true_range.iloc[-30:-15]
                        historical_atr_avg = historical_window.mean()
                
                # Calculate historical BB width average
                if historical_bb_width_avg is None and current_bb_width is not None:
                    bb_period = 20
                    bb_std = 2.0
                    bb_widths = []
                    
                    # Calculate BB width for historical windows
                    for i in range(max(bb_period, len(candles_df) - 40), len(candles_df) - 20):
                        if i >= bb_period:
                            window = candles_df.iloc[i - bb_period:i + 1]
                            sma = window['close'].mean()
                            std = window['close'].std()
                            if not pd.isna(sma) and not pd.isna(std):
                                bb_upper = sma + (std * bb_std)
                                bb_lower = sma - (std * bb_std)
                                bb_widths.append(bb_upper - bb_lower)
                    
                    if bb_widths:
                        historical_bb_width_avg = sum(bb_widths) / len(bb_widths)
            
            # Check if range is new (no historical data or range age < 10 bars)
            if historical_atr_avg is None and historical_bb_width_avg is None:
                return "forming"
            
            # Determine expansion state based on volatility comparison
            expansion_signals = []
            contraction_signals = []
            
            # ATR comparison
            if current_atr is not None and historical_atr_avg is not None and historical_atr_avg > 0:
                atr_ratio = current_atr / historical_atr_avg
                if atr_ratio >= 1.2:  # 20% higher = expanding
                    expansion_signals.append("atr")
                elif atr_ratio <= 0.8:  # 20% lower = contracting
                    contraction_signals.append("atr")
            
            # BB width comparison
            if current_bb_width is not None and historical_bb_width_avg is not None and historical_bb_width_avg > 0:
                bb_ratio = current_bb_width / historical_bb_width_avg
                if bb_ratio >= 1.2:  # 20% higher = expanding
                    expansion_signals.append("bb")
                elif bb_ratio <= 0.8:  # 20% lower = contracting
                    contraction_signals.append("bb")
            
            # Determine state based on signals
            if len(expansion_signals) >= 1:  # At least one metric shows expansion
                return "expanding"
            elif len(contraction_signals) >= 1:  # At least one metric shows contraction
                return "contracting"
            else:
                return "stable"  # No significant change
            
        except Exception as e:
            logger.warning(f"Error checking range expansion: {e}")
            return "stable"  # Default to stable on error
    
    def validate_range_integrity(
        self,
        range_data: RangeStructure,
        candles_df: Optional[pd.DataFrame] = None,
        atr: Optional[float] = None,
        structure_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Validate that range has no BOS/CHOCH inside boundaries.
        
        Args:
            range_data: RangeStructure to validate
            candles_df: DataFrame with OHLC data for BOS detection
            atr: Average True Range for BOS threshold
            structure_data: Optional pre-computed structure data (BOS/CHOCH signals)
            
        Returns:
            True if range is valid (no BOS/CHOCH inside), False otherwise
        """
        # If structure_data is provided, use it directly
        if structure_data:
            bos_bull = structure_data.get("bos_bull", False)
            bos_bear = structure_data.get("bos_bear", False)
            break_level = structure_data.get("break_level", 0.0)
            
            # Check if BOS occurred WITHIN range boundaries
            if (bos_bull or bos_bear) and break_level > 0:
                if range_data.range_low <= break_level <= range_data.range_high:
                    logger.debug(f"BOS detected inside range at {break_level} (range: {range_data.range_low}-{range_data.range_high})")
                    return False  # Invalid - BOS inside range means trending, not ranging
        
        # Otherwise, detect BOS from candles
        if candles_df is not None and atr is not None and len(candles_df) >= 10:
            try:
                # Get swings using find_swings
                pivots = find_swings(candles_df, left=3, right=3)
                
                if len(pivots) < 2:
                    return True  # No swings, can't validate
                
                # Convert Pivot objects to StructurePoint via label_swings
                labeled_swings = label_swings(pivots)
                
                if not labeled_swings:
                    return True
                
                # Convert StructurePoint to dict format for detect_bos_choch
                swing_dicts = [
                    {"price": sp.price, "kind": sp.kind, "idx": sp.idx}
                    for sp in labeled_swings
                ]
                
                current_close = float(candles_df["close"].iloc[-1])
                
                # Detect BOS/CHOCH
                bos_result = detect_bos_choch(
                    swing_dicts,
                    current_close,
                    atr,
                    bos_threshold=0.2,
                    sustained_bars=1
                )
                
                # Check if BOS occurred WITHIN range boundaries
                if (bos_result["bos_bull"] or bos_result["bos_bear"]):
                    break_level = bos_result.get("break_level", 0.0)
                    if break_level > 0 and range_data.range_low <= break_level <= range_data.range_high:
                        logger.debug(f"BOS detected inside range at {break_level}")
                        return False  # Invalid - trending, not ranging
                
            except Exception as e:
                logger.warning(f"Error validating range integrity: {e}")
                # Return True (assume valid) on error to avoid false positives
        
        return True  # Valid range (no BOS detected inside)
    
    def detect_nested_ranges(
        self,
        h1_range: Optional[RangeStructure],
        m15_range: Optional[RangeStructure],
        m5_range: Optional[RangeStructure]
    ) -> Optional[Dict[str, RangeStructure]]:
        """
        Detect nested range hierarchy (H1 → M15 → M5).
        
        Returns:
            Dict mapping timeframe to RangeStructure, or None if no nesting detected
        """
        nested = {}
        
        if m15_range:
            nested["M15"] = m15_range
        
        if h1_range and m15_range:
            # Check if M15 range is nested within H1 range
            if (h1_range.range_low <= m15_range.range_low and 
                m15_range.range_high <= h1_range.range_high):
                nested["H1"] = h1_range
        
        if m5_range and m15_range:
            # Check if M5 range is nested within M15 range
            if (m15_range.range_low <= m5_range.range_low and 
                m5_range.range_high <= m15_range.range_high):
                nested["M5"] = m5_range
        
        return nested if nested else None
    
    def check_range_invalidation(
        self,
        range_data: RangeStructure,
        current_price: float,
        candles: List[Dict[str, Any]],
        vwap_slope_pct_atr: Optional[float] = None,
        bb_width_expansion: Optional[float] = None,
        candles_df_m15: Optional[pd.DataFrame] = None,
        atr_m15: Optional[float] = None
    ) -> Tuple[bool, List[str]]:
        """
        Check if range is invalidated (breaking down).
        
        Invalidation Conditions (need 2+):
        1. 2 full candles closed outside range
        2. VWAP slope > threshold (20% of ATR per bar)
        3. BB width expanded > 50%
        4. M15 BOS confirmed (with break level inside or outside range)
        
        Args:
            range_data: RangeStructure to check
            current_price: Current market price
            candles: List of recent candle dicts with 'close' key
            vwap_slope_pct_atr: VWAP momentum as % of ATR per bar (e.g., 0.2 = 20%)
            bb_width_expansion: BB width expansion ratio (e.g., 0.5 = 50% expansion)
            candles_df_m15: Optional M15 DataFrame for BOS detection
            atr_m15: Optional M15 ATR for BOS detection
            
        Returns:
            (is_invalidated, list_of_triggered_signals)
        """
        invalidation_signals = []
        
        # Check 1: 2 candles closed outside range
        candles_outside = 0
        for candle in candles[-2:]:  # Check last 2 candles
            close = candle.get('close', 0)
            if close > range_data.range_high or close < range_data.range_low:
                candles_outside += 1
        
        if candles_outside >= 2:
            invalidation_signals.append("2_candles_outside_range")
        
        # Check 2: VWAP slope (as % of ATR per bar)
        if vwap_slope_pct_atr is not None:
            threshold = 0.2  # 20% of ATR per bar
            if abs(vwap_slope_pct_atr) > threshold:
                invalidation_signals.append("vwap_momentum_high")
        
        # Check 3: BB width expansion
        if bb_width_expansion is not None and bb_width_expansion > 0.5:  # 50% expansion
            invalidation_signals.append("bb_width_expansion")
        
        # Check 4: M15 BOS confirmed (integrated detection)
        if candles_df_m15 is not None and atr_m15 is not None and len(candles_df_m15) >= 10:
            try:
                # Get swings for M15
                m15_pivots = find_swings(candles_df_m15, left=3, right=3)
                
                if len(m15_pivots) >= 2:
                    # Convert to labeled swings
                    m15_labeled = label_swings(m15_pivots)
                    if m15_labeled:
                        # Convert to dict format
                        m15_swing_dicts = [
                            {"price": sp.price, "kind": sp.kind, "idx": sp.idx}
                            for sp in m15_labeled
                        ]
                        
                        m15_close = float(candles_df_m15["close"].iloc[-1])
                        
                        # Detect BOS
                        bos_result = detect_bos_choch(
                            m15_swing_dicts,
                            m15_close,
                            atr_m15,
                            bos_threshold=0.2,
                            sustained_bars=1
                        )
                        
                        # If BOS detected, check if it invalidates the range
                        if bos_result["bos_bull"] or bos_result["bos_bear"]:
                            break_level = bos_result.get("break_level", 0.0)
                            
                            # BOS invalidates range if:
                            # - Break occurred outside range (price broke out), OR
                            # - Break occurred inside range (structure changed)
                            if (break_level > range_data.range_high or 
                                break_level < range_data.range_low or
                                (range_data.range_low <= break_level <= range_data.range_high)):
                                invalidation_signals.append("m15_bos_confirmed")
                                
            except Exception as e:
                logger.warning(f"Error detecting M15 BOS for range invalidation: {e}")
        
        # Need 2+ signals for invalidation
        is_invalidated = len(invalidation_signals) >= 2
        
        return is_invalidated, invalidation_signals
    
    def detect_imbalanced_consolidation(
        self,
        range_data: RangeStructure,
        volume_trend: Dict[str, float],
        vwap_slope_pct_atr: float,
        candles_df: Optional[pd.DataFrame] = None,
        cvd_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Detect imbalanced consolidation (false range / pre-breakout trap).
        
        Red Flags (need 2+):
        1. Volume increasing inside range (15%+ vs 1h average)
        2. VWAP momentum > 10% of ATR per bar
        3. Candle bodies expanding (1.5× recent average)
        4. CVD divergence strength > 60%
        
        Args:
            range_data: RangeStructure to analyze
            volume_trend: Dict with volume metrics (current_vs_1h_avg, etc.)
            vwap_slope_pct_atr: VWAP momentum as % of ATR per bar
            candles_df: Optional DataFrame for candle body and CVD analysis
            cvd_data: Optional pre-calculated CVD data (if None, will calculate from candles_df)
            
        Returns:
            (is_false_range, list_of_red_flags)
        """
        red_flags = []
        
        # Check 1: Volume increase
        volume_increase = volume_trend.get("current_vs_1h_avg", 0)
        if volume_increase > 0.15:  # 15% increase
            red_flags.append("volume_increasing")
        
        # Check 2: VWAP momentum (as % of ATR per bar)
        if abs(vwap_slope_pct_atr) > 0.1:  # 10% of ATR per bar
            red_flags.append("vwap_momentum_high")
        
        # Check 3: Candle body expansion
        if candles_df is not None and len(candles_df) >= 10:
            try:
                # Calculate candle body sizes
                body_sizes = abs(candles_df['close'] - candles_df['open'])
                
                # Recent average (last 5 candles)
                recent_avg = body_sizes.tail(5).mean()
                
                # Older average (candles 10-15 bars ago)
                if len(candles_df) >= 15:
                    older_avg = body_sizes.iloc[-15:-10].mean()
                else:
                    older_avg = body_sizes.head(5).mean() if len(candles_df) >= 10 else recent_avg
                
                # Check if recent candles are 1.5× larger than older average
                if older_avg > 0 and recent_avg > (older_avg * 1.5):
                    red_flags.append("candle_body_expansion")
            except Exception as e:
                logger.debug(f"Error checking candle body expansion: {e}")
        
        # Check 4: CVD divergence (calculate if not provided)
        divergence_strength = 0.0
        if cvd_data:
            divergence_strength = cvd_data.get("divergence_strength", 0)
        elif candles_df is not None and len(candles_df) >= 20:
            # Calculate CVD divergence on-the-fly
            divergence_strength = self._calculate_cvd_divergence(candles_df)
        
        if divergence_strength > 0.6:  # 60%
            red_flags.append("cvd_divergence")
        
        # Need 2+ red flags for false range
        is_false_range = len(red_flags) >= 2
        
        return is_false_range, red_flags
    
    def _calculate_cvd_divergence(self, candles_df: pd.DataFrame) -> float:
        """
        Calculate CVD (Cumulative Volume Delta) divergence strength.
        
        Divergence occurs when price makes higher highs but CVD makes lower highs (bearish),
        or price makes lower lows but CVD makes higher lows (bullish).
        
        Returns:
            Divergence strength (0.0-1.0), where 1.0 = strong divergence
        """
        try:
            if len(candles_df) < 20:
                return 0.0
            
            # Calculate price and volume arrays
            prices = candles_df['close'].to_numpy()
            volumes = candles_df.get('volume', candles_df.get('tick_volume', pd.Series([1] * len(candles_df)))).to_numpy()
            
            # Calculate volume delta (simplified: positive if close > open, negative if close < open)
            price_changes = candles_df['close'] - candles_df['open']
            volume_delta = np.where(price_changes > 0, volumes, 
                                  np.where(price_changes < 0, -volumes, 0))
            
            # Calculate cumulative volume delta (CVD)
            cvd = np.cumsum(volume_delta)
            
            # Analyze last 10 bars for divergence
            recent_prices = prices[-10:]
            recent_cvd = cvd[-10:]
            
            # Find price highs/lows trend
            price_highs = []
            price_lows = []
            for i in range(1, len(recent_prices)):
                if recent_prices[i] > recent_prices[i-1]:
                    price_highs.append((i, recent_prices[i]))
                elif recent_prices[i] < recent_prices[i-1]:
                    price_lows.append((i, recent_prices[i]))
            
            # Find CVD highs/lows trend
            cvd_highs = []
            cvd_lows = []
            for i in range(1, len(recent_cvd)):
                if recent_cvd[i] > recent_cvd[i-1]:
                    cvd_highs.append((i, recent_cvd[i]))
                elif recent_cvd[i] < recent_cvd[i-1]:
                    cvd_lows.append((i, recent_cvd[i]))
            
            # Check for bearish divergence: price making higher highs, CVD making lower highs
            bearish_divergence = False
            if len(price_highs) >= 2 and len(cvd_highs) >= 2:
                price_higher = price_highs[-1][1] > price_highs[-2][1]
                cvd_lower = cvd_highs[-1][1] < cvd_highs[-2][1]
                bearish_divergence = price_higher and cvd_lower
            
            # Check for bullish divergence: price making lower lows, CVD making higher lows
            bullish_divergence = False
            if len(price_lows) >= 2 and len(cvd_lows) >= 2:
                price_lower = price_lows[-1][1] < price_lows[-2][1]
                cvd_higher = cvd_lows[-1][1] > cvd_lows[-2][1]
                bullish_divergence = price_lower and cvd_higher
            
            # Calculate divergence strength based on magnitude
            if bearish_divergence or bullish_divergence:
                # Strength based on how clear the divergence is
                if bearish_divergence:
                    price_change_pct = abs((price_highs[-1][1] - price_highs[-2][1]) / price_highs[-2][1])
                    cvd_change_pct = abs((cvd_highs[-1][1] - cvd_highs[-2][1]) / max(abs(cvd_highs[-2][1]), 1))
                else:
                    price_change_pct = abs((price_lows[-1][1] - price_lows[-2][1]) / price_lows[-2][1])
                    cvd_change_pct = abs((cvd_lows[-1][1] - cvd_lows[-2][1]) / max(abs(cvd_lows[-2][1]), 1))
                
                # Strength is higher if both price and CVD moves are significant
                strength = min(1.0, (price_change_pct + cvd_change_pct) * 10)
                return strength
            
            return 0.0
            
        except Exception as e:
            logger.debug(f"Error calculating CVD divergence: {e}")
            return 0.0

