"""
Session Profiles - Phase 4.2
Defines trading characteristics and rules for each market session.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class TradingSession(str, Enum):
    """Standard trading sessions (UTC-based)."""
    ASIA = "ASIA"
    LONDON = "LONDON"
    NY = "NY"
    UNKNOWN = "UNKNOWN"


class SessionOverlap(str, Enum):
    """Session overlap periods."""
    LONDON_NY = "LONDON_NY"  # 13:00-16:00 UTC - Peak liquidity
    ASIA_LONDON = "ASIA_LONDON"  # 08:00-09:00 UTC - Transitional
    NY_ASIA = "NY_ASIA"  # 21:00-22:00 UTC - Thin, transitional
    NONE = "NONE"


@dataclass
class SessionProfile:
    """
    Trading profile for a specific market session.
    Defines preferred strategies, filters, and confidence adjustments.
    """
    name: str
    description: str
    
    # Strategy preferences
    preferred_strategies: List[str] = field(default_factory=list)
    discouraged_strategies: List[str] = field(default_factory=list)
    
    # Minimum requirements (None = no requirement)
    min_adx: Optional[float] = None
    min_volume_z: Optional[float] = None
    max_spread_atr_pct: Optional[float] = None
    min_bb_width: Optional[float] = None
    
    # Confidence adjustments
    base_confidence_adj: int = 0  # Base adjustment for this session
    strategy_confidence_adj: Dict[str, int] = field(default_factory=dict)
    
    # Time-based filters
    avoid_first_minutes: int = 0  # Skip first X minutes of session
    avoid_last_minutes: int = 0   # Skip last X minutes of session
    
    # Symbol-specific confidence multipliers
    symbol_multipliers: Dict[str, float] = field(default_factory=dict)
    
    # Additional flags
    require_bos_for_trend: bool = False  # Require BOS for trend continuation
    require_volume_for_breakout: bool = False  # Require volume confirmation
    discourage_mid_range: bool = False  # Reduce confidence for mid-range entries


# ============================================================================
# LONDON SESSION PROFILE
# ============================================================================
LONDON_PROFILE = SessionProfile(
    name="LONDON",
    description="High liquidity FX session, clean trends, strong breakouts",
    
    # Prefer trend and breakout strategies
    preferred_strategies=["trend_pullback", "breakout", "trend_continuation"],
    discouraged_strategies=["range_fade"],
    
    # Minimum requirements
    min_adx=20.0,  # Require trend strength
    min_volume_z=0.0,  # Require positive volume
    max_spread_atr_pct=0.20,  # Spread < 20% ATR
    
    # Confidence adjustments
    base_confidence_adj=0,  # Neutral base
    strategy_confidence_adj={
        "trend_pullback": +10,  # Favor trend strategies
        "breakout": +10,
        "trend_continuation": +10,
        "range_fade": -20  # Discourage ranges
    },
    
    # Time filters
    avoid_first_minutes=30,  # Skip first 30min (chop/false breakouts)
    avoid_last_minutes=15,   # Skip last 15min before NY open
    
    # Symbol preferences
    symbol_multipliers={
        "EURUSD": 1.2,   # Excellent in London
        "GBPUSD": 1.2,
        "XAUUSD": 1.1,
        "BTCUSD": 0.9    # Less predictable
    },
    
    # Additional flags
    require_bos_for_trend=False,  # BOS helpful but not required
    require_volume_for_breakout=True,
    discourage_mid_range=True
)


# ============================================================================
# NEW YORK SESSION PROFILE
# ============================================================================
NY_PROFILE = SessionProfile(
    name="NY",
    description="High volatility, reversals common, institutional flow",
    
    # All strategies viable but with caution
    preferred_strategies=["breakout", "range_fade"],
    discouraged_strategies=[],  # None explicitly discouraged
    
    # Minimum requirements
    min_volume_z=0.5,  # Require moderate volume
    max_spread_atr_pct=0.30,  # Allow slightly higher spread (volatility)
    min_bb_width=0.03,  # For range-fade, require width
    
    # Confidence adjustments
    base_confidence_adj=0,
    strategy_confidence_adj={
        "breakout": +5,  # Slight favor
        "range_fade": +5,  # If conditions met
        "trend_continuation": -10  # Reversals common
    },
    
    # Time filters
    avoid_first_minutes=0,   # NY open is tradeable
    avoid_last_minutes=30,   # Skip last 30min (thin)
    
    # Symbol preferences
    symbol_multipliers={
        "XAUUSD": 1.2,   # Excellent in NY
        "BTCUSD": 1.1,
        "EURUSD": 1.0,
        "GBPUSD": 0.9    # Can be choppy
    },
    
    # Additional flags
    require_bos_for_trend=True,  # Need confirmation for trends
    require_volume_for_breakout=True,
    discourage_mid_range=True  # Mid-range = no edge
)


# ============================================================================
# ASIA SESSION PROFILE
# ============================================================================
ASIA_PROFILE = SessionProfile(
    name="ASIA",
    description="Thin liquidity, defined ranges, mean reversion",
    
    # Strongly prefer range strategies
    preferred_strategies=["range_fade"],
    discouraged_strategies=["breakout", "trend_continuation"],
    
    # Stricter requirements
    min_volume_z=1.5,  # High volume required for breakouts
    max_spread_atr_pct=0.25,
    min_bb_width=0.02,  # Decent range width
    
    # Confidence adjustments
    base_confidence_adj=-5,  # Slightly negative base (thin liquidity)
    strategy_confidence_adj={
        "range_fade": +15,  # Strongly favor
        "breakout": -20,    # Strongly discourage
        "trend_continuation": -15,
        "trend_pullback": -10
    },
    
    # Time filters
    avoid_first_minutes=60,  # Skip first hour (thin)
    avoid_last_minutes=60,   # Skip last hour before London
    
    # Symbol preferences
    symbol_multipliers={
        "EURUSD": 0.8,   # Less predictable
        "GBPUSD": 0.7,
        "XAUUSD": 0.9,
        "BTCUSD": 0.6    # Very risky in Asia
    },
    
    # Additional flags
    require_bos_for_trend=True,
    require_volume_for_breakout=True,
    discourage_mid_range=False  # Range trading is the game
)


# ============================================================================
# OVERLAP PROFILES
# ============================================================================
LONDON_NY_OVERLAP_PROFILE = SessionProfile(
    name="LONDON_NY_OVERLAP",
    description="Peak liquidity period, all strategies viable",
    
    # All strategies good
    preferred_strategies=["trend_pullback", "breakout", "trend_continuation"],
    discouraged_strategies=[],
    
    # Standard requirements
    min_adx=18.0,  # Slightly relaxed
    min_volume_z=0.0,
    max_spread_atr_pct=0.20,
    
    # Confidence adjustments
    base_confidence_adj=+5,  # Positive base (peak liquidity)
    strategy_confidence_adj={
        "trend_pullback": +10,
        "breakout": +10,
        "trend_continuation": +5
    },
    
    # Time filters
    avoid_first_minutes=0,
    avoid_last_minutes=0,
    
    # Symbol preferences
    symbol_multipliers={
        "EURUSD": 1.3,   # Best time for EUR
        "GBPUSD": 1.3,
        "XAUUSD": 1.2,
        "BTCUSD": 1.0
    },
    
    require_bos_for_trend=False,
    require_volume_for_breakout=True,
    discourage_mid_range=True
)


TRANSITION_PROFILE = SessionProfile(
    name="TRANSITION",
    description="Session transition period, reduced confidence",
    
    # Be more selective
    preferred_strategies=["range_fade"],
    discouraged_strategies=["breakout", "trend_continuation"],
    
    # Stricter requirements
    min_adx=25.0,  # Need strong trend
    min_volume_z=1.0,
    max_spread_atr_pct=0.20,
    
    # Confidence adjustments
    base_confidence_adj=-10,  # Negative base (uncertainty)
    strategy_confidence_adj={
        "range_fade": 0,
        "breakout": -15,
        "trend_continuation": -15,
        "trend_pullback": -10
    },
    
    # Time filters
    avoid_first_minutes=0,
    avoid_last_minutes=0,
    
    # Symbol preferences (all reduced)
    symbol_multipliers={
        "EURUSD": 0.8,
        "GBPUSD": 0.8,
        "XAUUSD": 0.9,
        "BTCUSD": 0.7
    },
    
    require_bos_for_trend=True,
    require_volume_for_breakout=True,
    discourage_mid_range=True
)


# ============================================================================
# PROFILE REGISTRY
# ============================================================================
SESSION_PROFILES: Dict[str, SessionProfile] = {
    TradingSession.LONDON: LONDON_PROFILE,
    TradingSession.NY: NY_PROFILE,
    TradingSession.ASIA: ASIA_PROFILE,
    SessionOverlap.LONDON_NY: LONDON_NY_OVERLAP_PROFILE,
    "TRANSITION": TRANSITION_PROFILE,
    TradingSession.UNKNOWN: TRANSITION_PROFILE,  # Use cautious profile
}


def get_session_profile(
    session: str,
    is_overlap: bool = False,
    overlap_type: Optional[str] = None,
    is_transition: bool = False
) -> SessionProfile:
    """
    Get the appropriate session profile based on current conditions.
    
    Args:
        session: Primary session (ASIA, LONDON, NY)
        is_overlap: Whether in overlap period
        overlap_type: Type of overlap if applicable
        is_transition: Whether in transition period (first/last minutes)
        
    Returns:
        SessionProfile for the current conditions
    """
    # Transition periods use cautious profile
    if is_transition:
        return SESSION_PROFILES["TRANSITION"]
    
    # Overlap periods
    if is_overlap and overlap_type:
        if overlap_type == SessionOverlap.LONDON_NY:
            return SESSION_PROFILES[SessionOverlap.LONDON_NY]
        # Other overlaps use transition profile
        return SESSION_PROFILES["TRANSITION"]
    
    # Standard sessions
    session_key = session.upper() if session else TradingSession.UNKNOWN
    return SESSION_PROFILES.get(session_key, SESSION_PROFILES[TradingSession.UNKNOWN])


def get_strategy_confidence_adjustment(
    profile: SessionProfile,
    strategy: str,
    symbol: str
) -> int:
    """
    Calculate total confidence adjustment for a strategy in current session.
    
    Returns:
        Confidence adjustment (-50 to +50)
    """
    # Base session adjustment
    adjustment = profile.base_confidence_adj
    
    # Strategy-specific adjustment
    adjustment += profile.strategy_confidence_adj.get(strategy, 0)
    
    # Symbol multiplier (affects magnitude)
    symbol_mult = profile.symbol_multipliers.get(symbol, 1.0)
    adjustment = int(adjustment * symbol_mult)
    
    # Clamp to reasonable range
    return max(-50, min(50, adjustment))

