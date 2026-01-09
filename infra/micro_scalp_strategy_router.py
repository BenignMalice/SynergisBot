"""
Micro-Scalp Strategy Router

Selects appropriate strategy based on regime detection results.
Handles fallback to edge-based strategy when no regime is detected.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MicroScalpStrategyRouter:
    """
    Routes to appropriate strategy based on regime detection.
    
    Strategy Priority:
    1. VWAP Reversion - Highest priority if detected (confidence ≥ threshold)
    2. Range Scalp - Second priority if detected (confidence ≥ threshold)
    3. Balanced Zone - Third priority if detected (confidence ≥ threshold)
    4. Edge Based - Fallback if no regime detected or confidence < threshold
    """
    
    def __init__(self, config: Dict[str, Any], 
                 regime_detector,
                 m1_analyzer=None):
        """
        Initialize Strategy Router.
        
        Args:
            config: Configuration dict
            regime_detector: MicroScalpRegimeDetector instance
            m1_analyzer: Optional M1MicrostructureAnalyzer (for quick confluence check)
        """
        self.config = config
        self.regime_detector = regime_detector
        self.m1_analyzer = m1_analyzer
    
    def select_strategy(self, snapshot: Dict[str, Any], 
                       regime_result: Dict[str, Any]) -> str:
        """
        Select strategy based on regime detection result.
        
        Args:
            snapshot: Market data snapshot
            regime_result: Result from MicroScalpRegimeDetector.detect_regime()
        
        Returns:
            Strategy name: 'vwap_reversion', 'range_scalp', 'balanced_zone', or 'edge_based'
        """
        regime = regime_result.get('regime')
        confidence = regime_result.get('confidence', 0)
        
        # Use strategy-specific threshold from detection result
        min_confidence = regime_result.get('min_confidence_threshold', 60)
        
        # Check if regime detection is enabled
        if not self.config.get('regime_detection', {}).get('enabled', True):
            logger.debug("Regime detection disabled, using edge-based fallback")
            return 'edge_based'
        
        # ENHANCED: Confluence pre-check (suggested improvement #5)
        # If confluence is too low, fallback to edge-based even if regime detected
        confluence_pre_check = self.config.get('regime_detection', {}).get('confluence_pre_check', {})
        if confluence_pre_check.get('enabled', False):
            min_confluence = confluence_pre_check.get('min_confluence', 5.0)
            
            # Quick confluence check using M1 analyzer if available
            if self.m1_analyzer:
                try:
                    symbol = snapshot.get('symbol', '')
                    candles = snapshot.get('candles', [])
                    
                    if candles:
                        analysis = self.m1_analyzer.analyze_microstructure(symbol, candles)
                        # Get a quick confluence estimate (simplified)
                        # This is a pre-check, not the full confluence calculation
                        quick_confluence = self._estimate_quick_confluence(analysis, snapshot)
                        
                        if quick_confluence < min_confluence:
                            logger.debug(
                                f"Confluence pre-check failed: {quick_confluence:.1f} < {min_confluence}, "
                                f"using edge-based fallback despite regime {regime}"
                            )
                            return 'edge_based'
                except Exception as e:
                    logger.debug(f"Error in confluence pre-check: {e}")
        
        # If confidence too low, fallback
        if confidence < min_confidence:
            logger.debug(
                f"Regime confidence {confidence} < {min_confidence}, using edge-based fallback"
            )
            return 'edge_based'
        
        # Strategy priority ordering
        if regime == 'vwap_reversion' or regime == 'VWAP_REVERSION':
            return 'vwap_reversion'
        elif regime == 'range_scalp' or regime == 'RANGE':
            return 'range_scalp'
        elif regime == 'balanced_zone' or regime == 'BALANCED_ZONE':
            return 'balanced_zone'
        else:
            logger.debug(f"Unknown regime '{regime}', using edge-based fallback")
            return 'edge_based'
    
    def _estimate_quick_confluence(self, analysis: Dict[str, Any], 
                                   snapshot: Dict[str, Any]) -> float:
        """
        Quick confluence estimate for pre-check (not full calculation).
        
        This is a simplified check to avoid routing to a strategy that will
        likely fail the full confluence check.
        
        Returns:
            Estimated confluence score (0-8 scale, simplified)
        """
        try:
            score = 0.0
            
            # Check for CHOCH/BOS
            choch_bos = analysis.get('choch_bos', {})
            if choch_bos.get('has_choch', False) or choch_bos.get('choch_confirmed', False):
                score += 1.0
            
            # Check for liquidity zones
            liquidity_zones = analysis.get('liquidity_zones', {})
            if liquidity_zones.get('equal_highs_detected', False):
                score += 0.5
            if liquidity_zones.get('equal_lows_detected', False):
                score += 0.5
            
            # Check VWAP proximity
            vwap = snapshot.get('vwap', 0)
            current_price = snapshot.get('current_price', 0)
            if vwap > 0 and current_price > 0:
                vwap_std = snapshot.get('vwap_std', 0)
                if vwap_std > 0:
                    deviation = abs(current_price - vwap) / vwap_std
                    if deviation >= 2.0:  # 2σ deviation
                        score += 1.0
            
            # Check volume
            candles = snapshot.get('candles', [])
            if len(candles) >= 11:
                last_volume = candles[-1].get('volume', 0)
                recent_volumes = [c.get('volume', 0) for c in candles[-11:-1]]
                avg_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 0
                if avg_volume > 0 and last_volume >= avg_volume * 1.3:
                    score += 0.5
            
            return score
        except Exception as e:
            logger.debug(f"Error estimating quick confluence: {e}")
            return 0.0

