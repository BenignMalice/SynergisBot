"""
Dynamic Threshold Tuning Module (Phase 2.3)

SymbolThresholdManager calculates dynamic, adaptive confluence thresholds based on:
- Symbol-specific volatility personality (base_confidence, vol_weight, sess_weight)
- Current trading session (session bias per symbol)
- Real-time ATR ratio (current_ATR / median_ATR)

This prevents fixed thresholds from causing false triggers in choppy markets or
missing entries in high-volatility phases.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class SymbolThresholdManager:
    """
    Dynamic Threshold Tuning Manager
    
    Calculates adaptive confluence thresholds that adjust based on:
    1. Asset's volatility personality (symbol-specific)
    2. Current market session (session bias)
    3. Real-time ATR ratio (volatility state)
    """
    
    def __init__(self, profile_file: str = "config/threshold_profiles.json"):
        """
        Initialize the threshold manager.
        
        Args:
            profile_file: Path to threshold profiles JSON file
        """
        self.profile_file = Path(profile_file)
        self.symbol_profiles: Dict[str, Dict[str, Any]] = {}
        self.session_bias: Dict[str, Dict[str, float]] = {}
        
        self._load_profiles()
        logger.info(f"SymbolThresholdManager initialized with {len(self.symbol_profiles)} symbol profiles")
    
    def _load_profiles(self):
        """Load threshold profiles from JSON file or use defaults"""
        if self.profile_file.exists():
            try:
                with open(self.profile_file, 'r') as f:
                    data = json.load(f)
                    self.symbol_profiles = data.get('symbol_profiles', {})
                    self.session_bias = data.get('session_bias', {})
                logger.info(f"Loaded threshold profiles from {self.profile_file}")
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding threshold profiles JSON: {e}")
                self._set_default_profiles()
        else:
            logger.warning(f"Threshold profiles file not found: {self.profile_file}, using defaults")
            self._set_default_profiles()
    
    def _set_default_profiles(self):
        """Set default threshold profiles"""
        # Symbol-specific profiles: base_confidence, vol_weight, sess_weight
        self.symbol_profiles = {
            "BTCUSD": {
                "base": 75,
                "vol_weight": 0.54,  # Reduced by 10% (from 0.6)
                "sess_weight": 0.36  # Reduced by 10% (from 0.4)
            },
            "XAUUSD": {
                "base": 70,
                "vol_weight": 0.45,  # Reduced by 10% (from 0.5)
                "sess_weight": 0.54  # Reduced by 10% (from 0.6)
            },
            "EURUSD": {
                "base": 65,
                "vol_weight": 0.36,  # Reduced by 10% (from 0.4)
                "sess_weight": 0.63  # Reduced by 10% (from 0.7)
            },
            "GBPUSD": {
                "base": 65,
                "vol_weight": 0.36,  # Reduced by 10% (from 0.4)
                "sess_weight": 0.63  # Reduced by 10% (from 0.7)
            },
            "USDJPY": {
                "base": 65,
                "vol_weight": 0.36,  # Reduced by 10% (from 0.4)
                "sess_weight": 0.63  # Reduced by 10% (from 0.7)
            }
        }
        
        # Session bias matrix: session -> symbol -> bias_factor
        self.session_bias = {
            "ASIAN": {
                "BTCUSD": 0.9,
                "XAUUSD": 0.85,
                "EURUSD": 0.8,
                "GBPUSD": 0.8,
                "USDJPY": 0.8
            },
            "LONDON": {
                "BTCUSD": 1.0,
                "XAUUSD": 1.1,
                "EURUSD": 1.0,
                "GBPUSD": 1.0,
                "USDJPY": 1.0
            },
            "OVERLAP": {
                "BTCUSD": 1.1,
                "XAUUSD": 1.2,
                "EURUSD": 1.1,
                "GBPUSD": 1.1,
                "USDJPY": 1.1
            },
            "NY": {
                "BTCUSD": 1.0,
                "XAUUSD": 1.0,
                "EURUSD": 1.0,
                "GBPUSD": 1.0,
                "USDJPY": 1.0
            },
            "POST_NY": {
                "BTCUSD": 0.95,
                "XAUUSD": 0.9,
                "EURUSD": 0.85,
                "GBPUSD": 0.85,
                "USDJPY": 0.85
            }
        }
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol name by removing 'c' suffix if present and uppercasing."""
        return symbol.upper().rstrip('C')
    
    def get_base_confidence(self, symbol: str) -> float:
        """
        Get base confidence threshold for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Base confidence threshold (default: 70)
        """
        symbol_norm = self._normalize_symbol(symbol)
        profile = self.symbol_profiles.get(symbol_norm, {})
        return profile.get('base', 70.0)
    
    def get_session_bias(self, session: str, symbol: str) -> float:
        """
        Get session bias factor for a symbol.
        
        Args:
            session: Trading session (ASIAN, LONDON, NY, OVERLAP, POST_NY)
            symbol: Trading symbol
            
        Returns:
            Session bias factor (default: 1.0)
        """
        symbol_norm = self._normalize_symbol(symbol)
        session_upper = session.upper()
        
        session_biases = self.session_bias.get(session_upper, {})
        return session_biases.get(symbol_norm, 1.0)
    
    def compute_threshold(
        self,
        symbol: str,
        session: str,
        atr_ratio: float
    ) -> float:
        """
        Compute dynamic threshold based on symbol, session, and ATR ratio.
        
        Formula:
        threshold = base_confidence * (1 + (atr_ratio - 1) * vol_weight) * (session_bias ^ sess_weight)
        
        Args:
            symbol: Trading symbol
            session: Trading session (ASIAN, LONDON, NY, OVERLAP, POST_NY)
            atr_ratio: Current ATR / median ATR (volatility state indicator)
            
        Returns:
            Dynamic threshold (50-95 range)
        """
        symbol_norm = self._normalize_symbol(symbol)
        session_upper = session.upper()
        
        # Get symbol profile
        profile = self.symbol_profiles.get(symbol_norm, {})
        base_confidence = profile.get('base', 70.0)
        vol_weight = profile.get('vol_weight', 0.45)  # Reduced by 10% (from 0.5)
        sess_weight = profile.get('sess_weight', 0.45)  # Reduced by 10% (from 0.5)
        
        # Get session bias
        session_biases = self.session_bias.get(session_upper, {})
        session_bias_factor = session_biases.get(symbol_norm, 1.0)
        
        # Step 1: Volatility adjustment
        # If ATR ratio > 1.0 (high volatility), increase threshold
        # If ATR ratio < 1.0 (low volatility), decrease threshold slightly
        volatility_adjustment = 1 + (atr_ratio - 1) * vol_weight
        threshold_after_vol = base_confidence * volatility_adjustment
        
        # Step 2: Session adjustment
        # Apply session bias with exponential weighting
        threshold_after_session = threshold_after_vol * (session_bias_factor ** sess_weight)
        
        # Clamp to reasonable range (50-95)
        final_threshold = max(50.0, min(95.0, threshold_after_session))
        
        return round(final_threshold, 1)
    
    def get_symbol_profile(self, symbol: str) -> Dict[str, Any]:
        """
        Get full symbol profile.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Symbol profile dict
        """
        symbol_norm = self._normalize_symbol(symbol)
        return self.symbol_profiles.get(symbol_norm, {
            'base': 70.0,
            'vol_weight': 0.45,  # Reduced by 10% (from 0.5)
            'sess_weight': 0.45  # Reduced by 10% (from 0.5)
        })
    
    def get_all_session_biases(self, symbol: str) -> Dict[str, float]:
        """
        Get all session biases for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary mapping session to bias factor
        """
        symbol_norm = self._normalize_symbol(symbol)
        biases = {}
        
        for session, symbol_biases in self.session_bias.items():
            biases[session] = symbol_biases.get(symbol_norm, 1.0)
        
        return biases

