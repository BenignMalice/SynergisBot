"""
Session Rules Engine - Phase 4.2
Applies session-specific filtering and confidence adjustments to trade recommendations.
"""

import logging
from typing import Dict, List, Tuple, Optional, Any

from infra.session_profiles import (
    SessionProfile,
    get_session_profile,
    get_strategy_confidence_adjustment
)


logger = logging.getLogger(__name__)


class SessionRules:
    """
    Apply session-specific rules to filter and adjust trade recommendations.
    """
    
    def __init__(self):
        """Initialize session rules engine."""
        self.enabled = True  # Can be disabled via config
        
    def apply_filters(
        self,
        trade_spec: Dict[str, Any],
        session_info: Dict[str, Any],
        features: Dict[str, Any],
        symbol: str
    ) -> Tuple[bool, List[str]]:
        """
        Apply session-specific filters to determine if trade should proceed.
        
        Args:
            trade_spec: Trade specification with strategy, confidence, etc.
            session_info: Session context (primary_session, is_overlap, etc.)
            features: Market features (ADX, volume, spread, etc.)
            symbol: Trading symbol
            
        Returns:
            (pass: bool, skip_reasons: List[str])
        """
        skip_reasons = []
        
        if not self.enabled:
            return True, []
        
        try:
            # Get session profile
            profile = self._get_profile(session_info)
            strategy = trade_spec.get("strategy", "")
            
            # Check session timing filters
            timing_pass, timing_reasons = self._check_timing_filters(
                profile, session_info
            )
            if not timing_pass:
                skip_reasons.extend(timing_reasons)
                return False, skip_reasons
            
            # Check minimum requirements
            requirements_pass, req_reasons = self._check_requirements(
                profile, strategy, features, symbol
            )
            if not requirements_pass:
                skip_reasons.extend(req_reasons)
                return False, skip_reasons
            
            # Check strategy appropriateness
            strategy_pass, strat_reasons = self._check_strategy_fit(
                profile, strategy, features
            )
            if not strategy_pass:
                skip_reasons.extend(strat_reasons)
                return False, skip_reasons
            
            # All filters passed
            return True, []
            
        except Exception as e:
            logger.error(f"Session filter error: {e}")
            return True, []  # Don't block on errors
    
    def adjust_confidence(
        self,
        confidence: float,
        strategy: str,
        session_info: Dict[str, Any],
        features: Dict[str, Any],
        symbol: str
    ) -> Tuple[float, List[str]]:
        """
        Adjust confidence based on session characteristics.
        
        Args:
            confidence: Base confidence (0-100)
            strategy: Strategy name
            session_info: Session context
            features: Market features
            symbol: Trading symbol
            
        Returns:
            (adjusted_confidence: float, adjustment_reasons: List[str])
        """
        if not self.enabled:
            return confidence, []
        
        try:
            adjustment_reasons = []
            total_adjustment = 0
            
            # Get session profile
            profile = self._get_profile(session_info)
            
            # Base strategy adjustment
            strategy_adj = get_strategy_confidence_adjustment(profile, strategy, symbol)
            if strategy_adj != 0:
                total_adjustment += strategy_adj
                adjustment_reasons.append(
                    f"Session {profile.name} {'+' if strategy_adj > 0 else ''}{strategy_adj} "
                    f"for {strategy}"
                )
            
            # Situational adjustments
            situational_adj, situational_reasons = self._get_situational_adjustments(
                profile, strategy, features, session_info
            )
            total_adjustment += situational_adj
            adjustment_reasons.extend(situational_reasons)
            
            # Apply adjustment
            adjusted = confidence + total_adjustment
            adjusted = max(0, min(100, adjusted))  # Clamp to [0, 100]
            
            return adjusted, adjustment_reasons
            
        except Exception as e:
            logger.error(f"Confidence adjustment error: {e}")
            return confidence, []
    
    def get_session_guardrails(
        self,
        session_info: Dict[str, Any],
        symbol: str
    ) -> Dict[str, Any]:
        """
        Get session-specific guardrails for risk management.
        
        Returns:
            Dictionary with risk parameters
        """
        try:
            profile = self._get_profile(session_info)
            
            # Symbol-specific risk multiplier
            risk_mult = profile.symbol_multipliers.get(symbol, 1.0)
            
            # Lower risk during transitions
            if session_info.get("is_transition", False):
                risk_mult *= 0.7
            
            # Lower risk during thin overlaps
            overlap_type = session_info.get("overlap_type")
            if overlap_type in ["ASIA_LONDON", "NY_ASIA"]:
                risk_mult *= 0.8
            
            return {
                "risk_multiplier": risk_mult,
                "max_spread_atr_pct": profile.max_spread_atr_pct,
                "require_volume": profile.require_volume_for_breakout,
                "require_bos": profile.require_bos_for_trend
            }
            
        except Exception as e:
            logger.error(f"Guardrails error: {e}")
            return {"risk_multiplier": 1.0}
    
    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================
    
    def _get_profile(self, session_info: Dict[str, Any]) -> SessionProfile:
        """Get appropriate session profile."""
        return get_session_profile(
            session=session_info.get("primary_session", "UNKNOWN"),
            is_overlap=session_info.get("is_overlap", False),
            overlap_type=session_info.get("overlap_type"),
            is_transition=session_info.get("is_transition_period", False)
        )
    
    def _check_timing_filters(
        self,
        profile: SessionProfile,
        session_info: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Check if current time is appropriate for trading."""
        skip_reasons = []
        
        minutes_into = session_info.get("minutes_into_session", 0)
        
        # Check if in avoid period
        if minutes_into < profile.avoid_first_minutes:
            skip_reasons.append(
                f"Session {profile.name}: avoid first {profile.avoid_first_minutes} minutes "
                f"(currently {minutes_into} min in)"
            )
            return False, skip_reasons
        
        # Check if near session end (would need session duration)
        # For now, rely on is_transition_period flag
        if session_info.get("is_transition_period", False):
            if profile.avoid_last_minutes > 0:
                skip_reasons.append(
                    f"Session {profile.name}: avoid last {profile.avoid_last_minutes} minutes "
                    f"(transition period)"
                )
                return False, skip_reasons
        
        return True, []
    
    def _check_requirements(
        self,
        profile: SessionProfile,
        strategy: str,
        features: Dict[str, Any],
        symbol: str
    ) -> Tuple[bool, List[str]]:
        """Check if market meets session minimum requirements."""
        skip_reasons = []
        
        # ADX requirement
        if profile.min_adx is not None:
            adx = features.get("adx_14", features.get("adx", 0))
            if adx < profile.min_adx:
                skip_reasons.append(
                    f"Session {profile.name} requires ADX≥{profile.min_adx:.1f}, "
                    f"got {adx:.1f}"
                )
        
        # Volume requirement (for breakouts and volatile strategies)
        if profile.require_volume_for_breakout and strategy in ["breakout", "trend_continuation"]:
            if profile.min_volume_z is not None:
                volume_z = features.get("volume_zscore", 0)
                if volume_z < profile.min_volume_z:
                    skip_reasons.append(
                        f"Session {profile.name} {strategy} requires volume_z≥{profile.min_volume_z:.1f}, "
                        f"got {volume_z:.1f}"
                    )
        
        # Spread requirement
        if profile.max_spread_atr_pct is not None:
            spread_atr_pct = features.get("spread_atr_pct", 0)
            if spread_atr_pct > profile.max_spread_atr_pct:
                skip_reasons.append(
                    f"Session {profile.name} requires spread<{profile.max_spread_atr_pct:.1%}, "
                    f"got {spread_atr_pct:.1%}"
                )
        
        # Bollinger Band width (for range strategies)
        if strategy == "range_fade" and profile.min_bb_width is not None:
            bb_width = features.get("bb_width", 0)
            if bb_width < profile.min_bb_width:
                skip_reasons.append(
                    f"Session {profile.name} range requires BB_width≥{profile.min_bb_width:.3f}, "
                    f"got {bb_width:.3f}"
                )
        
        # BOS requirement for trends
        if profile.require_bos_for_trend and strategy in ["trend_continuation", "trend_pullback"]:
            bos_bull = features.get("bos_bull", False)
            bos_bear = features.get("bos_bear", False)
            if not (bos_bull or bos_bear):
                skip_reasons.append(
                    f"Session {profile.name} {strategy} requires BOS confirmation"
                )
        
        return len(skip_reasons) == 0, skip_reasons
    
    def _check_strategy_fit(
        self,
        profile: SessionProfile,
        strategy: str,
        features: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Check if strategy is appropriate for session."""
        skip_reasons = []
        
        # Hard block for strongly discouraged strategies
        if strategy in profile.discouraged_strategies:
            # Check if there's strong evidence to override
            conf_adj = profile.strategy_confidence_adj.get(strategy, 0)
            if conf_adj <= -20:  # Strong discouragement
                # Allow override with exceptional conditions
                volume_z = features.get("volume_zscore", 0)
                donchian_breakout = features.get("donchian_breakout", False)
                bos = features.get("bos_bull") or features.get("bos_bear")
                
                # ASIA breakout exception
                if profile.name == "ASIA" and strategy == "breakout":
                    if not (volume_z >= 2.0 and donchian_breakout):
                        skip_reasons.append(
                            f"ASIA breakout requires exceptional conditions: "
                            f"volume_z≥2.0 AND Donchian breach "
                            f"(got volume_z={volume_z:.1f}, donchian={donchian_breakout})"
                        )
                # ASIA trend exception
                elif profile.name == "ASIA" and strategy in ["trend_continuation", "trend_pullback"]:
                    if not (volume_z >= 1.8 and bos):
                        skip_reasons.append(
                            f"ASIA {strategy} requires exceptional conditions: "
                            f"volume_z≥1.8 AND BOS "
                            f"(got volume_z={volume_z:.1f}, BOS={bos})"
                        )
        
        # Mid-range discouragement (NY/London)
        if profile.discourage_mid_range:
            range_position = features.get("range_position", 0.5)
            if 0.35 < range_position < 0.65:  # Mid-range
                if strategy in ["trend_pullback", "trend_continuation"]:
                    skip_reasons.append(
                        f"Session {profile.name}: mid-range entry (pos={range_position:.2f}) "
                        f"has reduced edge for {strategy}"
                    )
        
        return len(skip_reasons) == 0, skip_reasons
    
    def _get_situational_adjustments(
        self,
        profile: SessionProfile,
        strategy: str,
        features: Dict[str, Any],
        session_info: Dict[str, Any]
    ) -> Tuple[int, List[str]]:
        """Get additional confidence adjustments based on specific conditions."""
        adjustment = 0
        reasons = []
        
        # BOS bonus (London/NY overlap)
        if profile.name in ["LONDON", "LONDON_NY_OVERLAP"]:
            if features.get("bos_bull") or features.get("bos_bear"):
                if strategy in ["trend_pullback", "trend_continuation"]:
                    adjustment += 10
                    reasons.append("+10 for BOS confirmation in London")
        
        # Spread spike penalty (NY)
        if profile.name == "NY":
            spread_atr_pct = features.get("spread_atr_pct", 0)
            if spread_atr_pct > 0.30:
                adjustment -= 10
                reasons.append(f"-10 for elevated spread ({spread_atr_pct:.1%} ATR)")
        
        # Wick rejection bonus (Asia range-fade)
        if profile.name == "ASIA" and strategy == "range_fade":
            if features.get("wick_rejection_bull") or features.get("wick_rejection_bear"):
                adjustment += 10
                reasons.append("+10 for wick rejection in Asia range")
        
        # Session strength penalty
        session_strength = session_info.get("session_strength", 1.0)
        if session_strength < 0.7:
            penalty = int((0.7 - session_strength) * 20)  # Up to -14
            adjustment -= penalty
            reasons.append(f"-{penalty} for low session strength ({session_strength:.2f})")
        
        # Equal highs/lows bonus (liquidity zones)
        if features.get("eq_high_cluster") or features.get("eq_low_cluster"):
            if strategy in ["trend_pullback", "range_fade"]:
                adjustment += 5
                reasons.append("+5 for equal highs/lows liquidity zone")
        
        # Sweep bonus (post-liquidity grab)
        if features.get("sweep_bull") or features.get("sweep_bear"):
            if strategy in ["trend_pullback", "range_fade"]:
                adjustment += 8
                reasons.append("+8 for post-sweep reversal setup")
        
        return adjustment, reasons


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_session_rules() -> SessionRules:
    """Create session rules instance."""
    return SessionRules()


def check_session_trade(
    trade_spec: Dict[str, Any],
    session_info: Dict[str, Any],
    features: Dict[str, Any],
    symbol: str,
    rules: Optional[SessionRules] = None
) -> Tuple[bool, float, List[str]]:
    """
    Convenience function to check and adjust a trade for session rules.
    
    Returns:
        (pass: bool, adjusted_confidence: float, reasons: List[str])
    """
    if rules is None:
        rules = create_session_rules()
    
    # Apply filters
    pass_filters, skip_reasons = rules.apply_filters(
        trade_spec, session_info, features, symbol
    )
    
    if not pass_filters:
        return False, 0.0, skip_reasons
    
    # Adjust confidence
    adjusted_conf, adj_reasons = rules.adjust_confidence(
        trade_spec.get("confidence", 50),
        trade_spec.get("strategy", ""),
        session_info,
        features,
        symbol
    )
    
    all_reasons = skip_reasons + adj_reasons
    return True, adjusted_conf, all_reasons

