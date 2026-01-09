# =====================================
# infra/m1_asset_profiles.py
# =====================================
"""
M1 Asset Profile Manager Module

Manages asset-specific volatility personalities, preferred strategies, and behavior patterns.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class AssetProfileManager:
    """
    Manages asset-specific profiles for M1 microstructure analysis.
    
    Provides:
    - Asset-specific volatility personalities
    - Preferred strategies per asset and session
    - Behavior patterns and traits
    - Auto-execution thresholds
    """
    
    def __init__(self, profile_file: Optional[str] = None):
        """
        Initialize Asset Profile Manager.
        
        Args:
            profile_file: Path to asset profiles JSON file
                         Defaults to "config/asset_profiles.json"
        """
        if profile_file is None:
            # Default to config/asset_profiles.json relative to project root
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            profile_file = os.path.join(project_root, "config", "asset_profiles.json")
        
        self.profile_file = profile_file
        self.profiles: Dict[str, Dict[str, Any]] = {}
        
        # Load profiles
        self._load_profiles()
        
        logger.info(f"AssetProfileManager initialized with {len(self.profiles)} profiles")
    
    def _load_profiles(self):
        """Load asset profiles from JSON file."""
        try:
            if os.path.exists(self.profile_file):
                with open(self.profile_file, 'r') as f:
                    self.profiles = json.load(f)
                logger.info(f"Loaded {len(self.profiles)} asset profiles from {self.profile_file}")
            else:
                logger.warning(f"Asset profiles file not found: {self.profile_file}, using defaults")
                self.profiles = self._get_default_profiles()
        except Exception as e:
            logger.error(f"Error loading asset profiles: {e}", exc_info=True)
            self.profiles = self._get_default_profiles()
    
    def _get_default_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Get default asset profiles if file not found."""
        return {
            "XAUUSD": {
                "primary_sessions": ["LONDON", "NY", "OVERLAP"],
                "volatility_personality": "HIGH_VOLATILITY",
                "atr_multiplier_range": [1.0, 1.2],
                "confluence_minimum": 75,
                "vwap_stretch_tolerance": 1.5,
                "preferred_strategies": {
                    "LONDON": ["BREAKOUT", "CHOCH_CONTINUATION"],
                    "NY": ["VWAP_FADE", "PULLBACK_SCALP"],
                    "OVERLAP": ["MOMENTUM_CONTINUATION", "BOS_BREAKOUT"]
                },
                "behavior_traits": [
                    "Sharp liquidity sweeps near PDH/PDL",
                    "Reacts strongly to VWAP and liquidity zones"
                ],
                "weekend_trading": False
            },
            "BTCUSD": {
                "primary_sessions": ["ASIAN", "LONDON", "NY", "OVERLAP"],
                "volatility_personality": "VERY_HIGH_VOLATILITY",
                "atr_multiplier_range": [1.5, 2.0],
                "confluence_minimum": 85,
                "vwap_stretch_tolerance": 2.5,
                "preferred_strategies": {
                    "ASIAN": ["TREND_SCALP"],
                    "LONDON": ["BREAKOUT", "MOMENTUM"],
                    "NY": ["TREND_SCALP"],
                    "OVERLAP": ["MOMENTUM_CONTINUATION"]
                },
                "behavior_traits": [
                    "High volatility, less structured order flow",
                    "Spikes near session transitions"
                ],
                "weekend_trading": True
            },
            "EURUSD": {
                "primary_sessions": ["LONDON", "NY"],
                "volatility_personality": "MODERATE_VOLATILITY",
                "atr_multiplier_range": [0.8, 1.0],
                "confluence_minimum": 70,
                "vwap_stretch_tolerance": 1.0,
                "preferred_strategies": {
                    "LONDON": ["TREND", "BREAKOUT"],
                    "NY": ["FADE", "REVERSAL"]
                },
                "behavior_traits": [
                    "Strong structural confluence with DXY",
                    "Mean reversion efficient during NY close"
                ],
                "weekend_trading": False
            }
        }
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol name (remove 'c' suffix if present).
        
        Args:
            symbol: Symbol name
            
        Returns:
            Normalized symbol (without 'c' suffix)
        """
        if symbol.endswith('c'):
            return symbol[:-1]
        return symbol
    
    def get_asset_profile(self, symbol: str) -> Dict[str, Any]:
        """
        Get complete asset profile for a symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Dict with:
            - symbol: str
            - primary_sessions: List[str]
            - volatility_personality: str
            - atr_multiplier_range: List[float]
            - confluence_minimum: float
            - vwap_stretch_tolerance: float
            - preferred_strategies: Dict[str, List[str]]
            - behavior_traits: List[str]
            - weekend_trading: bool
        """
        normalized_symbol = self._normalize_symbol(symbol).upper()
        
        profile = self.profiles.get(normalized_symbol, {})
        
        if not profile:
            # Return default profile for unknown symbols
            logger.debug(f"No profile found for {symbol}, using defaults")
            return {
                "symbol": normalized_symbol,
                "primary_sessions": ["LONDON", "NY"],
                "volatility_personality": "MODERATE_VOLATILITY",
                "atr_multiplier_range": [0.9, 1.1],
                "confluence_minimum": 70,
                "vwap_stretch_tolerance": 1.0,
                "preferred_strategies": {
                    "LONDON": ["TREND", "BREAKOUT"],
                    "NY": ["TREND", "BREAKOUT"]
                },
                "behavior_traits": [],
                "weekend_trading": False
            }
        
        # Add symbol to profile
        profile["symbol"] = normalized_symbol
        
        return profile
    
    def get_preferred_strategies(self, symbol: str, session: str) -> List[str]:
        """
        Get preferred strategies for symbol in session.
        
        Args:
            symbol: Symbol name
            session: Session name (ASIAN, LONDON, NY, OVERLAP, POST_NY)
            
        Returns:
            List of preferred strategy names
        """
        profile = self.get_asset_profile(symbol)
        preferred_strategies = profile.get("preferred_strategies", {})
        
        # Get strategies for session
        strategies = preferred_strategies.get(session.upper(), [])
        
        # If no strategies for session, return default
        if not strategies:
            # Try to get from primary sessions
            primary_sessions = profile.get("primary_sessions", [])
            if primary_sessions:
                # Use first primary session's strategies
                first_session = primary_sessions[0]
                strategies = preferred_strategies.get(first_session, ["TREND_CONTINUATION"])
            else:
                strategies = ["TREND_CONTINUATION"]
        
        return strategies
    
    def get_atr_multiplier(self, symbol: str) -> float:
        """
        Get ATR multiplier for symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            ATR multiplier (XAUUSD: 1.0-1.2, BTCUSD: 1.5-2.0, Forex: 0.8-1.0)
            Returns average of range
        """
        profile = self.get_asset_profile(symbol)
        atr_range = profile.get("atr_multiplier_range", [0.9, 1.1])
        
        # Return average of range
        return (atr_range[0] + atr_range[1]) / 2.0
    
    def get_confluence_minimum(self, symbol: str) -> float:
        """
        Get minimum confluence for auto-execution.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Minimum confluence (XAUUSD: 75, BTCUSD: 85, Forex: 70)
        """
        profile = self.get_asset_profile(symbol)
        return profile.get("confluence_minimum", 70)
    
    def get_vwap_stretch_tolerance(self, symbol: str) -> float:
        """
        Get VWAP stretch tolerance for symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            VWAP stretch tolerance (XAUUSD: 1.5, BTCUSD: 2.5, Forex: 1.0)
        """
        profile = self.get_asset_profile(symbol)
        return profile.get("vwap_stretch_tolerance", 1.0)
    
    def is_weekend_trading(self, symbol: str) -> bool:
        """
        Check if symbol trades on weekends.
        
        Args:
            symbol: Symbol name
            
        Returns:
            True if trades on weekends, False otherwise
        """
        profile = self.get_asset_profile(symbol)
        return profile.get("weekend_trading", False)
    
    def is_session_active_for_symbol(self, symbol: str, session: str) -> bool:
        """
        Check if session is active for symbol.
        
        Args:
            symbol: Symbol name
            session: Session name
            
        Returns:
            True if session is active for symbol, False otherwise
        """
        profile = self.get_asset_profile(symbol)
        primary_sessions = profile.get("primary_sessions", [])
        
        # BTCUSD trades 24/7
        normalized_symbol = self._normalize_symbol(symbol).upper()
        if "BTC" in normalized_symbol:
            return True
        
        return session.upper() in [s.upper() for s in primary_sessions]
    
    def get_volatility_personality(self, symbol: str) -> str:
        """
        Get volatility personality for symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Volatility personality (HIGH_VOLATILITY, VERY_HIGH_VOLATILITY, MODERATE_VOLATILITY)
        """
        profile = self.get_asset_profile(symbol)
        return profile.get("volatility_personality", "MODERATE_VOLATILITY")
    
    def get_behavior_traits(self, symbol: str) -> List[str]:
        """
        Get behavior traits for symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            List of behavior trait descriptions
        """
        profile = self.get_asset_profile(symbol)
        return profile.get("behavior_traits", [])
    
    def is_signal_valid_for_asset(self, symbol: str, analysis: Dict[str, Any]) -> bool:
        """
        Check if signal is valid for asset based on profile.
        
        Args:
            symbol: Symbol name
            analysis: M1 analysis result
            
        Returns:
            True if signal is valid for asset, False otherwise
        """
        profile = self.get_asset_profile(symbol)
        
        # Check confluence minimum
        confluence = analysis.get("microstructure_confluence", {}).get("score", 0)
        confluence_min = profile.get("confluence_minimum", 70)
        
        if confluence < confluence_min:
            return False
        
        # Check volatility personality match
        volatility_state = analysis.get("volatility", {}).get("state", "STABLE")
        volatility_personality = profile.get("volatility_personality", "MODERATE_VOLATILITY")
        
        # Very high volatility assets need expanding/contracting states
        if volatility_personality == "VERY_HIGH_VOLATILITY":
            if volatility_state == "STABLE":
                return False  # Too calm for high volatility asset
        
        return True
    
    def get_profile_summary(self, symbol: str) -> str:
        """
        Get human-readable profile summary.
        
        Args:
            symbol: Symbol name
            
        Returns:
            Summary string
        """
        profile = self.get_asset_profile(symbol)
        
        volatility = profile.get("volatility_personality", "MODERATE_VOLATILITY")
        atr_mult = self.get_atr_multiplier(symbol)
        confluence_min = self.get_confluence_minimum(symbol)
        vwap_stretch = self.get_vwap_stretch_tolerance(symbol)
        sessions = ", ".join(profile.get("primary_sessions", []))
        
        return (
            f"{symbol}: {volatility}, "
            f"ATR: {atr_mult:.1f}x, "
            f"Confluence: {confluence_min}, "
            f"VWAP: ±{vwap_stretch}σ, "
            f"Sessions: {sessions}"
        )

