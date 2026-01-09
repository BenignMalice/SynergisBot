"""
Trade Type Classifier
Automatically classifies trades as SCALP vs INTRADAY based on multiple factors.

Uses 3-factor classification:
1. Comment keywords (highest priority) - manual override support
2. Stop size vs ATR ratio
3. Session strategy
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class TradeTypeClassifier:
    """
    Classifies trades as SCALP or INTRADAY based on comment keywords,
    stop size vs ATR ratio, and session strategy.
    """
    
    # SCALP indicator keywords (case-insensitive)
    SCALP_KEYWORDS = [
        "scalp", "scalping", "scalper",
        "micro", "quick", "fast", "rapid",
        "short", "brief", "momentum",
        "quick trade", "fast exit", "take profits"
    ]
    
    # INTRADAY indicator keywords (case-insensitive)
    INTRADAY_KEYWORDS = [
        "swing", "intraday", "hold",
        "position", "trend", "runner",
        "daily", "session", "full target",
        "let it run"
    ]
    
    # Manual override patterns
    FORCE_SCALP_PATTERNS = ["!force:scalp", "!force:SCALP"]
    FORCE_INTRADAY_PATTERNS = ["!force:intraday", "!force:INTRADAY"]
    
    # SCALP session strategies
    SCALP_STRATEGIES = ["scalping", "range_trading"]
    
    # INTRADAY session strategies
    INTRADAY_STRATEGIES = ["trend_following", "breakout", "breakout_and_trend"]
    
    # Classification thresholds
    STOP_ATR_SCALP_THRESHOLD = 1.0  # Stop <= 1.0× ATR = SCALP
    
    def __init__(self, mt5_service=None, session_service=None):
        """
        Initialize classifier.
        
        Args:
            mt5_service: MT5 service for accessing price data (optional)
            session_service: Session analyzer service (optional)
        """
        self.mt5_service = mt5_service
        self.session_service = session_service
    
    def classify(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        comment: Optional[str] = None,
        session_info: Optional[Dict] = None,
        atr_h1: Optional[float] = None,
        volatility_regime: Optional[Dict[str, Any]] = None,
        is_weekend: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Classify trade as SCALP, INTRADAY, or WEEKEND.
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            stop_loss: Stop loss price
            comment: Trade comment (may contain keywords or override flags)
            session_info: Session info dict from getCurrentSession() (optional)
            atr_h1: H1 ATR value (optional, will be fetched if not provided)
            volatility_regime: Volatility regime data (optional)
            is_weekend: Whether weekend profile is active (optional, will be auto-detected if None)
        
        Returns:
            Dict with:
                - trade_type: "SCALP", "INTRADAY", or "WEEKEND"
                - confidence: 0.0-1.0 (how confident the classification is)
                - reasoning: Human-readable explanation
                - factors: Dict with individual factor values
        """
        try:
            # Initialize factors dict
            factors = {
                "stop_atr_ratio": None,
                "comment_match": None,
                "session_strategy": None,
                "manual_override": False,
                "is_weekend": None
            }
            
            # Factor 0: Check if weekend (HIGHEST PRIORITY - before manual override)
            # Weekend classification applies ONLY to BTCUSDc
            if is_weekend is None:
                # Auto-detect weekend status
                try:
                    from infra.weekend_profile_manager import WeekendProfileManager
                    weekend_manager = WeekendProfileManager()
                    is_weekend = weekend_manager.is_weekend_active()
                except Exception as e:
                    logger.debug(f"Could not auto-detect weekend status: {e}")
                    is_weekend = False
            
            factors["is_weekend"] = is_weekend
            
            # Weekend classification: Only for BTCUSDc during weekend hours
            if is_weekend and symbol.upper() in ["BTCUSDc", "BTCUSD"]:
                logger.info(f"Weekend classification: {symbol} trade during weekend hours → WEEKEND")
                return {
                    "trade_type": "WEEKEND",
                    "confidence": 1.0,
                    "reasoning": "Weekend profile active for BTCUSDc",
                    "factors": {**factors, "weekend_detected": True}
                }
            
            # Factor 1: Check for manual override (HIGHEST PRIORITY after weekend check)
            if comment:
                comment_lower = comment.lower()
                
                # Check for force patterns
                for pattern in self.FORCE_SCALP_PATTERNS:
                    if pattern.lower() in comment_lower:
                        logger.info(f"Manual override detected: {pattern} → SCALP")
                        return {
                            "trade_type": "SCALP",
                            "confidence": 1.0,
                            "reasoning": f"Manual override: {pattern}",
                            "factors": {**factors, "manual_override": True, "override_type": "scalp"}
                        }
                
                for pattern in self.FORCE_INTRADAY_PATTERNS:
                    if pattern.lower() in comment_lower:
                        logger.info(f"Manual override detected: {pattern} → INTRADAY")
                        return {
                            "trade_type": "INTRADAY",
                            "confidence": 1.0,
                            "reasoning": f"Manual override: {pattern}",
                            "factors": {**factors, "manual_override": True, "override_type": "intraday"}
                        }
                
                # Check for keyword matches
                for keyword in self.SCALP_KEYWORDS:
                    if keyword in comment_lower:
                        factors["comment_match"] = "scalp"
                        logger.debug(f"Comment keyword match: '{keyword}' → SCALP indicator")
                        break
                
                if not factors["comment_match"]:
                    for keyword in self.INTRADAY_KEYWORDS:
                        if keyword in comment_lower:
                            factors["comment_match"] = "intraday"
                            logger.debug(f"Comment keyword match: '{keyword}' → INTRADAY indicator")
                            break
            
            # Factor 2: Stop size vs ATR ratio
            stop_atr_ratio = None
            if atr_h1 is None:
                # Try to fetch ATR if not provided
                atr_h1 = self._fetch_atr_h1(symbol)
            
            if atr_h1 and atr_h1 > 0:
                stop_size = abs(entry_price - stop_loss)
                
                # Validate stop size is not zero (invalid trade)
                if stop_size <= 0:
                    logger.warning(f"Invalid stop size (stop == entry), cannot calculate ratio")
                    stop_atr_ratio = None
                else:
                    stop_atr_ratio = stop_size / atr_h1
                    factors["stop_atr_ratio"] = stop_atr_ratio
                    logger.debug(f"Stop/ATR ratio: {stop_atr_ratio:.2f} (stop: {stop_size:.5f}, ATR H1: {atr_h1:.5f})")
            else:
                logger.warning(f"ATR H1 not available for {symbol}, skipping stop size classification")
            
            # Factor 3: Session strategy
            # Note: Only auto-fetch if explicitly needed, but preserve None for tests
            # We'll fetch it in _make_classification if needed, but keep original None for factors
            session_info_for_classification = session_info
            if session_info is None:
                # Try to fetch session info for classification (but don't modify factors if it fails)
                session_info_for_classification = self._fetch_session_info()
            
            # Store session strategy in factors only if explicitly provided (not auto-fetched)
            if session_info is not None:  # Only if explicitly provided
                session_strategy = session_info.get("strategy", "")
                factors["session_strategy"] = session_strategy
                logger.debug(f"Session strategy: {session_strategy}")
            else:
                factors["session_strategy"] = None  # Explicitly None if not provided
                logger.debug("Session info not explicitly provided")
            
            # Classification decision tree
            # Use session_info_for_classification (may be auto-fetched) for classification logic
            trade_type, confidence, reasoning = self._make_classification(
                factors, stop_atr_ratio, session_info_for_classification
            )
            
            # Apply volatility-aware classification (Phase 3.09)
            enhanced_trade_type = self._apply_volatility_classification(
                trade_type=trade_type,
                volatility_regime=volatility_regime
            )
            
            # Update reasoning if volatility classification applied
            if enhanced_trade_type != trade_type:
                reasoning = f"{reasoning} (Volatile regime: {enhanced_trade_type})"
            
            return {
                "trade_type": enhanced_trade_type,
                "base_trade_type": trade_type,  # Keep original for reference
                "confidence": confidence,
                "reasoning": reasoning,
                "factors": factors,
                "stop_atr_ratio": stop_atr_ratio,
                "volatility_regime": volatility_regime.get("regime").value if volatility_regime and volatility_regime.get("regime") else None
            }
            
        except Exception as e:
            logger.error(f"Error classifying trade: {e}", exc_info=True)
            # Safe fallback: default to INTRADAY
            return {
                "trade_type": "INTRADAY",
                "confidence": 0.0,
                "reasoning": f"Classification error: {str(e)} → Default to INTRADAY",
                "factors": {
                    "stop_atr_ratio": None,
                    "comment_match": None,
                    "session_strategy": None,
                    "error": str(e)
                }
            }
    
    def _make_classification(
        self,
        factors: Dict[str, Any],
        stop_atr_ratio: Optional[float],
        session_info: Optional[Dict]
    ) -> Tuple[str, float, str]:
        """
        Make classification decision based on factors.
        
        Priority:
        1. Comment keywords (highest priority)
        2. Stop size vs ATR
        3. Session strategy
        4. Default to INTRADAY (conservative)
        
        Returns:
            Tuple of (trade_type, confidence, reasoning)
        """
        # Priority 1: Comment keywords
        if factors["comment_match"] == "scalp":
            confidence = 0.85  # High confidence if keyword match
            return ("SCALP", confidence, "Comment keyword indicates SCALP")
        
        if factors["comment_match"] == "intraday":
            confidence = 0.85  # High confidence if keyword match
            return ("INTRADAY", confidence, "Comment keyword indicates INTRADAY")
        
        # Priority 2: Stop size vs ATR
        if stop_atr_ratio is not None and stop_atr_ratio > 0:
            # Use small epsilon for floating-point comparison to handle precision errors
            epsilon = 1e-9
            if stop_atr_ratio <= (self.STOP_ATR_SCALP_THRESHOLD + epsilon):
                confidence = 0.75  # Good confidence from stop size
                return ("SCALP", confidence, f"Stop size {stop_atr_ratio:.2f}× ATR ≤ {self.STOP_ATR_SCALP_THRESHOLD}× (SCALP threshold)")
            
            if stop_atr_ratio > (self.STOP_ATR_SCALP_THRESHOLD + epsilon):
                confidence = 0.70  # Good confidence from stop size
                return ("INTRADAY", confidence, f"Stop size {stop_atr_ratio:.2f}× ATR > {self.STOP_ATR_SCALP_THRESHOLD}× (INTRADAY threshold)")
        
        # Priority 3: Session strategy
        if session_info:
            session_strategy = session_info.get("strategy", "")
            
            if session_strategy in self.SCALP_STRATEGIES:
                confidence = 0.65  # Moderate confidence from session
                return ("SCALP", confidence, f"Session strategy '{session_strategy}' indicates SCALP")
            
            if session_strategy in self.INTRADAY_STRATEGIES:
                confidence = 0.65  # Moderate confidence from session
                return ("INTRADAY", confidence, f"Session strategy '{session_strategy}' indicates INTRADAY")
        
        # Default: INTRADAY (conservative fallback)
        confidence = 0.50  # Low confidence (ambiguous)
        return ("INTRADAY", confidence, "No clear classification signals → Default to INTRADAY (conservative)")
    
    def _fetch_atr_h1(self, symbol: str) -> Optional[float]:
        """
        Fetch H1 ATR for symbol.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            H1 ATR value or None if unavailable
        """
        try:
            from infra.indicator_bridge import IndicatorBridge
            
            bridge = IndicatorBridge()
            multi_data = bridge.get_multi(symbol)
            
            if "H1" in multi_data:
                h1_data = multi_data["H1"]
                # ATR is stored as 'atr14' in indicators
                indicators = h1_data.get("indicators", {})
                atr = indicators.get("atr14")
                
                if atr and atr > 0:
                    logger.debug(f"Fetched ATR H1 for {symbol}: {atr:.2f}")
                    return float(atr)
            
            logger.warning(f"ATR H1 not found in indicator bridge for {symbol}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching ATR H1 for {symbol}: {e}", exc_info=True)
            return None
    
    def _fetch_session_info(self) -> Optional[Dict]:
        """
        Fetch current session info.
        
        Returns:
            Session info dict or None if unavailable
        """
        try:
            from infra.session_analyzer import SessionAnalyzer
            
            analyzer = SessionAnalyzer()
            session_info = analyzer.get_current_session()
            
            logger.debug(f"Fetched session info: {session_info.get('name')}, strategy: {session_info.get('strategy')}")
            return session_info
            
        except Exception as e:
            logger.error(f"Error fetching session info: {e}", exc_info=True)
            return None
    
    def _apply_volatility_classification(
        self,
        trade_type: str,
        volatility_regime: Optional[Dict[str, Any]]
    ) -> str:
        """
        Apply volatility-aware classification enhancement.
        
        Converts:
        - SCALP → VOLATILE_SCALP (if volatile regime detected)
        - INTRADAY → VOLATILE_INTRADAY (if volatile regime detected)
        
        Args:
            trade_type: Base trade type (SCALP or INTRADAY)
            volatility_regime: Detected volatility regime data (optional)
        
        Returns:
            Enhanced trade type (VOLATILE_SCALP, VOLATILE_INTRADAY, or original)
        """
        if not volatility_regime:
            return trade_type
        
        try:
            regime = volatility_regime.get("regime")
            
            # Extract regime string
            if hasattr(regime, 'value'):
                regime_str = regime.value
            else:
                regime_str = str(regime) if regime else "STABLE"
            
            # Only apply volatile classification if VOLATILE regime detected
            if regime_str == "VOLATILE":
                if trade_type == "SCALP":
                    return "VOLATILE_SCALP"
                elif trade_type == "INTRADAY":
                    return "VOLATILE_INTRADAY"
            
            # Return original classification for STABLE/TRANSITIONAL
            return trade_type
            
        except Exception as e:
            logger.warning(f"Error applying volatility classification: {e}")
            return trade_type

