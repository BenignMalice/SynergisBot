# =====================================
# infra/m1_session_volatility_profile.py
# =====================================
"""
M1 Session Volatility Profile Module

Integrates session detection with M1 microstructure analysis.
Provides session-specific volatility tiers, liquidity timing, and bias factors.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SessionVolatilityProfile:
    """
    Provides session-aware volatility profiles for M1 microstructure analysis.
    
    Integrates with existing session detection systems to provide:
    - Session detection (Asian, London, NY, Overlap, Post-NY)
    - Session-specific volatility tiers
    - Liquidity timing information
    - Session bias factors for confidence adjustment
    """
    
    # Session definitions (UTC-based)
    SESSION_TIMES = {
        "ASIAN": (0, 8),      # 00:00-08:00 UTC
        "LONDON": (8, 13),    # 08:00-13:00 UTC
        "OVERLAP": (13, 16),  # 13:00-16:00 UTC (London-NY overlap)
        "NY": (16, 21),       # 16:00-21:00 UTC
        "POST_NY": (21, 24),  # 21:00-24:00 UTC (late NY / pre-Asian)
    }
    
    # Volatility tiers by session
    VOLATILITY_TIERS = {
        "ASIAN": "LOW",
        "LONDON": "NORMAL",
        "OVERLAP": "HIGH",
        "NY": "NORMAL",
        "POST_NY": "LOW",
    }
    
    # Liquidity timing by session
    LIQUIDITY_TIMING = {
        "ASIAN": "LOW",
        "LONDON": "ACTIVE",
        "OVERLAP": "ACTIVE",
        "NY": "ACTIVE",
        "POST_NY": "MODERATE",
    }
    
    # Typical behavior descriptions
    SESSION_BEHAVIOR = {
        "ASIAN": "Low volatility, range-bound conditions, thin liquidity",
        "LONDON": "High liquidity, strong trends, clean breakouts",
        "OVERLAP": "Peak liquidity, highest volatility, strongest momentum",
        "NY": "Active trading, news-driven moves, strong volume",
        "POST_NY": "Declining liquidity, consolidation, range conditions",
    }
    
    # Best strategy types by session
    BEST_STRATEGY_TYPES = {
        "ASIAN": "RANGE_SCALP",
        "LONDON": "BREAKOUT",
        "OVERLAP": "MOMENTUM_CONTINUATION",
        "NY": "TREND_CONTINUATION",
        "POST_NY": "RANGE_SCALP",
    }
    
    def __init__(self, session_manager=None):
        """
        Initialize Session Volatility Profile.
        
        Args:
            session_manager: Optional existing session manager (e.g., SessionNewsFeatures)
                           If provided, uses it for session detection
        """
        self.session_manager = session_manager
        logger.info("SessionVolatilityProfile initialized")
    
    def get_current_session(self, current_time: Optional[datetime] = None) -> str:
        """
        Get current trading session.
        
        Args:
            current_time: Time to evaluate (defaults to now UTC)
            
        Returns:
            Session name: "ASIAN" | "LONDON" | "NY" | "OVERLAP" | "POST_NY"
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        # Try to use existing session manager if available
        if self.session_manager:
            try:
                # Check if it has get_session_info method
                if hasattr(self.session_manager, 'get_session_info'):
                    session_info = self.session_manager.get_session_info(current_time)
                    primary = session_info.primary_session if hasattr(session_info, 'primary_session') else session_info.get('primary_session')
                    
                    # Check for overlap
                    is_overlap = session_info.is_overlap if hasattr(session_info, 'is_overlap') else session_info.get('is_overlap', False)
                    if is_overlap:
                        return "OVERLAP"
                    
                    # Map to our session names
                    if primary:
                        primary_upper = primary.upper()
                        if 'ASIA' in primary_upper or 'TOKYO' in primary_upper:
                            return "ASIAN"
                        elif 'LONDON' in primary_upper:
                            return "LONDON"
                        elif 'NY' in primary_upper or 'NEW_YORK' in primary_upper:
                            return "NY"
                
                # Check if it has _get_current_session method
                elif hasattr(self.session_manager, '_get_current_session'):
                    session = self.session_manager._get_current_session(current_time)
                    if session:
                        session_upper = session.upper()
                        if 'ASIA' in session_upper or 'TOKYO' in session_upper:
                            return "ASIAN"
                        elif 'LONDON' in session_upper:
                            return "LONDON"
                        elif 'NY' in session_upper or 'NEW_YORK' in session_upper:
                            return "NY"
            except Exception as e:
                logger.debug(f"Error using session_manager: {e}, falling back to time-based detection")
        
        # Fallback to time-based detection
        hour = current_time.hour
        
        if 0 <= hour < 8:
            return "ASIAN"
        elif 8 <= hour < 13:
            return "LONDON"
        elif 13 <= hour < 16:
            return "OVERLAP"
        elif 16 <= hour < 21:
            return "NY"
        else:  # 21 <= hour < 24
            return "POST_NY"
    
    def get_session_profile(
        self,
        session: Optional[str] = None,
        symbol: Optional[str] = None,
        current_time: Optional[datetime] = None
    ) -> Dict[str, any]:
        """
        Get complete session profile with volatility tier, liquidity, and recommendations.
        
        Args:
            session: Session name (if None, detects current session)
            symbol: Symbol name (optional, for symbol-specific adjustments)
            current_time: Time to evaluate (defaults to now UTC)
            
        Returns:
            Dict with:
            - session: str
            - volatility_tier: "LOW" | "NORMAL" | "HIGH" | "VERY_HIGH"
            - liquidity_timing: "ACTIVE" | "MODERATE" | "LOW"
            - typical_behavior: str
            - best_strategy_type: str
            - session_bias_factor: float (0.9-1.1)
        """
        if session is None:
            session = self.get_current_session(current_time)
        
        # Get base profile
        volatility_tier = self.VOLATILITY_TIERS.get(session, "NORMAL")
        liquidity_timing = self.LIQUIDITY_TIMING.get(session, "MODERATE")
        typical_behavior = self.SESSION_BEHAVIOR.get(session, "Normal trading conditions")
        best_strategy_type = self.BEST_STRATEGY_TYPES.get(session, "TREND_CONTINUATION")
        
        # Calculate session bias factor
        session_bias_factor = self.get_session_bias_factor(session, symbol)
        
        return {
            "session": session,
            "volatility_tier": volatility_tier,
            "liquidity_timing": liquidity_timing,
            "typical_behavior": typical_behavior,
            "best_strategy_type": best_strategy_type,
            "session_bias_factor": session_bias_factor,
        }
    
    def get_session_bias_factor(self, session: str, symbol: Optional[str] = None) -> float:
        """
        Get session bias factor for confidence threshold adjustment.
        
        Args:
            session: Session name
            symbol: Symbol name (optional, for symbol-specific adjustments)
            
        Returns:
            Bias factor (0.9-1.1):
            - < 1.0: Looser threshold (more aggressive)
            - 1.0: Neutral
            - > 1.0: Stricter threshold (more conservative)
        """
        # Base bias factors by session
        base_bias = {
            "ASIAN": 0.9,      # Looser (low volatility, range conditions)
            "LONDON": 1.0,     # Neutral
            "OVERLAP": 1.1,    # Stricter (high volatility, need confirmation)
            "NY": 1.0,         # Neutral
            "POST_NY": 0.9,    # Looser (declining liquidity)
        }
        
        bias = base_bias.get(session, 1.0)
        
        # Symbol-specific adjustments
        if symbol:
            symbol_upper = symbol.upper().rstrip('C')
            
            # XAUUSD: Stricter during overlap (high volatility)
            if 'XAU' in symbol_upper and session == "OVERLAP":
                bias *= 1.05  # Slightly stricter
            
            # BTCUSD: Looser during Asian (24/7, active)
            if 'BTC' in symbol_upper and session == "ASIAN":
                bias *= 0.95  # Slightly looser
            
            # Forex: Stricter during Asian (low liquidity)
            if any(fx in symbol_upper for fx in ['EUR', 'GBP', 'USD', 'JPY']) and session == "ASIAN":
                bias *= 1.05  # Slightly stricter
        
        return round(bias, 2)
    
    def get_atr_multiplier_adjustment(self, session: str, symbol: Optional[str] = None) -> float:
        """
        Get ATR multiplier adjustment for session.
        
        Args:
            session: Session name
            symbol: Symbol name (optional)
            
        Returns:
            ATR multiplier adjustment (0.8-1.2)
        """
        # Base adjustments by session
        base_multiplier = {
            "ASIAN": 0.9,      # Lower ATR (less volatility)
            "LONDON": 1.0,     # Normal
            "OVERLAP": 1.1,    # Higher ATR (more volatility)
            "NY": 1.0,         # Normal
            "POST_NY": 0.9,    # Lower ATR
        }
        
        multiplier = base_multiplier.get(session, 1.0)
        
        # Symbol-specific adjustments
        if symbol:
            symbol_upper = symbol.upper().rstrip('C')
            
            # XAUUSD: Higher during overlap
            if 'XAU' in symbol_upper and session == "OVERLAP":
                multiplier *= 1.1
            
            # BTCUSD: Higher overall
            if 'BTC' in symbol_upper:
                multiplier *= 1.2
        
        return round(multiplier, 2)
    
    def get_vwap_stretch_tolerance(self, session: str, symbol: Optional[str] = None) -> float:
        """
        Get VWAP stretch tolerance adjustment for session.
        
        Args:
            session: Session name
            symbol: Symbol name (optional)
            
        Returns:
            VWAP stretch tolerance multiplier (0.8-1.2)
        """
        # Base adjustments by session
        base_tolerance = {
            "ASIAN": 0.9,      # Tighter (less stretch)
            "LONDON": 1.0,     # Normal
            "OVERLAP": 1.1,    # Looser (more stretch allowed)
            "NY": 1.0,         # Normal
            "POST_NY": 0.9,     # Tighter
        }
        
        tolerance = base_tolerance.get(session, 1.0)
        
        # Symbol-specific adjustments
        if symbol:
            symbol_upper = symbol.upper().rstrip('C')
            
            # XAUUSD: Looser during overlap
            if 'XAU' in symbol_upper and session == "OVERLAP":
                tolerance *= 1.1
        
        return round(tolerance, 2)
    
    def is_good_time_to_trade(self, session: Optional[str] = None, symbol: Optional[str] = None) -> bool:
        """
        Check if current session is good for trading.
        
        Args:
            session: Session name (if None, detects current session)
            symbol: Symbol name (optional)
            
        Returns:
            True if good time to trade, False otherwise
        """
        if session is None:
            session = self.get_current_session()
        
        # Generally avoid Asian and Post-NY for most symbols
        if session in ["ASIAN", "POST_NY"]:
            # Exception: BTCUSD trades 24/7
            if symbol and 'BTC' in symbol.upper():
                return True
            return False
        
        return True
    
    def get_session_context(self, symbol: Optional[str] = None) -> Dict[str, any]:
        """
        Get complete session context for M1 analysis.
        
        Args:
            symbol: Symbol name (optional)
            
        Returns:
            Dict with all session-related information
        """
        session = self.get_current_session()
        profile = self.get_session_profile(session=session, symbol=symbol)
        
        return {
            **profile,
            "atr_multiplier_adjustment": self.get_atr_multiplier_adjustment(session, symbol),
            "vwap_stretch_tolerance": self.get_vwap_stretch_tolerance(session, symbol),
            "is_good_time_to_trade": self.is_good_time_to_trade(session, symbol),
        }
    
    def get_session_adjusted_parameters(
        self,
        symbol: str,
        session: Optional[str] = None,
        asset_profiles: Optional[Any] = None
    ) -> Dict[str, float]:
        """
        Get session-adjusted parameters combining asset profile with session adjustments.
        
        This method combines asset-specific base parameters with session multipliers
        to return adjusted min_confluence, ATR_multiplier, and VWAP_tolerance.
        
        Args:
            symbol: Symbol name
            session: Session name (if None, detects current session)
            asset_profiles: AssetProfileManager instance (optional)
            
        Returns:
            Dict with:
            - min_confluence: float (adjusted using session multipliers)
            - atr_multiplier: float (adjusted using session multipliers)
            - vwap_stretch_tolerance: float (adjusted using session multipliers)
            - session_profile: Dict (full session profile)
        """
        if session is None:
            session = self.get_current_session()
        
        session_upper = session.upper()
        
        # Session multipliers (Phase 2.6)
        session_multipliers = {
            'ASIAN': {'confluence': 1.1, 'atr': 0.9, 'vwap': 0.8},  # Stricter, tighter
            'LONDON': {'confluence': 1.0, 'atr': 1.0, 'vwap': 1.0},  # Normal
            'OVERLAP': {'confluence': 0.9, 'atr': 1.2, 'vwap': 1.2},  # More aggressive
            'NY': {'confluence': 1.0, 'atr': 1.0, 'vwap': 1.0},  # Normal
            'POST_NY': {'confluence': 1.1, 'atr': 0.9, 'vwap': 0.8}  # Stricter
        }
        
        multipliers = session_multipliers.get(session_upper, {'confluence': 1.0, 'atr': 1.0, 'vwap': 1.0})
        
        # Get base parameters from asset profile if available
        if asset_profiles:
            try:
                asset_profile = asset_profiles.get_asset_profile(symbol)
                base_confluence = asset_profile.get('confluence_minimum', 70.0)
                atr_range = asset_profile.get('atr_multiplier_range', [0.9, 1.1])
                base_atr = (atr_range[0] + atr_range[1]) / 2.0  # Average
                base_vwap = asset_profile.get('vwap_stretch_tolerance', 1.0)
            except Exception as e:
                logger.warning(f"Error getting asset profile for {symbol}: {e}, using defaults")
                base_confluence = 70.0
                base_atr = 1.0
                base_vwap = 1.0
        else:
            # Default base parameters
            base_confluence = 70.0
            base_atr = 1.0
            base_vwap = 1.0
        
        # Apply session multipliers
        adjusted_min_confluence = base_confluence * multipliers['confluence']
        adjusted_atr_multiplier = base_atr * multipliers['atr']
        adjusted_vwap_tolerance = base_vwap * multipliers['vwap']
        
        # Get full session profile
        session_profile = self.get_session_profile(session=session, symbol=symbol)
        
        return {
            'min_confluence': round(adjusted_min_confluence, 1),
            'atr_multiplier': round(adjusted_atr_multiplier, 2),
            'vwap_stretch_tolerance': round(adjusted_vwap_tolerance, 2),
            'session_profile': session_profile,
            'base_confluence': base_confluence,
            'base_atr_multiplier': base_atr,
            'base_vwap_tolerance': base_vwap,
            'session_multipliers': multipliers
        }

