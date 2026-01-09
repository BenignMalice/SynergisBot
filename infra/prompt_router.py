"""
Prompt Router - Phase 2
Intelligent routing system that matches market regime to appropriate strategy templates
Ensures GPT reasons within the right strategy context for consistent, disciplined trading
IMPROVED: Phase 4.2 - Integrated session-aware filtering and confidence adjustment
"""

import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

# Import required classes for type hints
from infra.prompt_templates import PromptTemplate
from infra.prompt_validator import ValidationResult

# IMPROVED Phase 4.2: Session rules integration
from infra.session_rules import SessionRules
from infra.feature_session_news import SessionNewsFeatures

logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    """Market regime classifications"""
    TREND = "trend"
    RANGE = "range"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"

class SessionType(Enum):
    """Trading session types"""
    ASIA = "asia"
    LONDON = "london"
    NEW_YORK = "new_york"
    OVERLAP = "overlap"
    CLOSED = "closed"

@dataclass
class RouterContext:
    """Context information for prompt routing"""
    symbol: str
    regime: MarketRegime
    session: SessionType
    features: Dict[str, Any]
    guardrails: Dict[str, Any]
    timestamp: datetime

@dataclass
class TradeSpec:
    """Validated trade specification from router"""
    strategy: str
    order_type: str
    entry: float
    sl: float
    tp: float
    rr: float
    confidence: Dict[str, int]
    rationale: str
    tags: List[str]
    template_version: str
    regime_fit: int

@dataclass
class DecisionOutcome:
    """Complete decision outcome with skip reasons for analytics"""
    status: str  # "ok" | "skip"
    trade_spec: Optional[TradeSpec]
    skip_reasons: List[str]
    template_name: str
    template_version: str
    regime: str
    session: str
    validation_score: float
    timestamp: datetime
    # IMPROVED: Session tag for analytics/metrics splitting
    session_tag: str  # For journal/metrics: "asia", "london", "ny", "overlap", "closed"
    # IMPROVED: Decision tags for effortless dashboard grouping
    decision_tags: List[str]  # e.g., ["session=NY", "template=breakout_v2", "regime=VOLATILE"]

class PromptRouter:
    """
    IMPROVED: Intelligent prompt routing system for regime-aware trading.
    Routes market conditions to appropriate strategy templates and validates outputs.
    Phase 4.2: Now includes session-aware filtering and confidence adjustment.
    """
    
    def __init__(self, session_rules_enabled: bool = True):
        self.template_manager = self._create_template_manager()
        self.validator = self._create_validator()
        self.regime_classifier = self._create_regime_classifier()
        
        # IMPROVED Phase 4.2: Session-aware decision making
        self.session_rules_enabled = session_rules_enabled
        self.session_rules = SessionRules() if session_rules_enabled else None
        self.session_features = SessionNewsFeatures()
        self.session_detector = self._create_session_detector()
        
    def route_and_analyze(self, symbol: str, features: Dict[str, Any], 
                         guardrails: Dict[str, Any]) -> DecisionOutcome:
        """
        Main routing function: analyzes market context and routes to appropriate template.
        Returns DecisionOutcome with trade specification or skip reasons for analytics.
        """
        try:
            # Create routing context
            context = self._create_context(symbol, features, guardrails)
            
            # Select appropriate template
            template = self._select_template(context)
            if not template:
                # IMPROVED: Unknown regime handling - always skip to avoid bias toward trend in chop
                if context.regime == MarketRegime.UNKNOWN:
                    skip_reason = f"Unknown regime detected for {context.session.value} session - skipping to avoid bias toward trend in choppy conditions"
                    logger.info(f"Router: Skipping due to unknown regime in {context.session.value} session")
                else:
                    skip_reason = f"No suitable template for {context.regime.value} regime in {context.session.value} session"

                return DecisionOutcome(
                    status="skip",
                    trade_spec=None,
                    skip_reasons=[skip_reason],
                    template_name="none",
                    template_version="none",
                    regime=context.regime.value,
                    session=context.session.value,
                    validation_score=0.0,
                    timestamp=context.timestamp,
                    session_tag=context.session.value,
                    decision_tags=[f"session={context.session.value}", f"regime={context.regime.value}"]
                )
            
            # IMPROVED: Template health check before use
            template_errors = self.template_manager.validate_template(template)
            if template_errors:
                error_details = f"Template health check failed for {template.name} v{template.version}: {', '.join(template_errors)}"
                logger.warning(error_details)

                # Enhanced analytics: surface template errors to journal/metrics
                skip_reasons = [error_details]
                return DecisionOutcome(
                    status="skip",
                    trade_spec=None,
                    skip_reasons=skip_reasons,
                    template_name=template.name,
                    template_version=template.version,
                    regime=context.regime.value,
                    session=context.session.value,
                    validation_score=0.0,
                    timestamp=context.timestamp,
                    session_tag=context.session.value,
                    decision_tags=[f"session={context.session.value}", f"template={template.name}", f"regime={context.regime.value}", "template_health_fail"]
                )

            # Generate prompt with features
            prompt = self._generate_prompt(template, context)

            # Send to LLM and validate response
            trade_spec, validation_result = self._execute_and_validate(prompt, template, context)
            
            if trade_spec and validation_result.is_valid:
                # IMPROVED Phase 4.2: Apply session-specific filters and confidence adjustments
                if self.session_rules_enabled and self.session_rules:
                    # Get comprehensive session info
                    session_info = self._get_session_info_dict(context)
                    
                    # Convert trade_spec to dict for session rules
                    trade_dict = {
                        "strategy": trade_spec.strategy,
                        "order_type": trade_spec.order_type,
                        "confidence": trade_spec.confidence.get("overall", 50)
                    }
                    
                    # Apply session filters
                    pass_filters, filter_reasons = self.session_rules.apply_filters(
                        trade_dict, session_info, context.features.get("M5", {}), symbol
                    )
                    
                    if not pass_filters:
                        logger.info(f"Router: Trade blocked by session filters: {filter_reasons}")
                        return DecisionOutcome(
                            status="skip",
                            trade_spec=None,
                            skip_reasons=filter_reasons,
                            template_name=template.name,
                            template_version=template.version,
                            regime=context.regime.value,
                            session=context.session.value,
                            validation_score=validation_result.validation_score,
                            timestamp=context.timestamp,
                            session_tag=context.session.value,
                            decision_tags=[f"session={context.session.value}", f"template={template.name}", f"regime={context.regime.value}", "session_filter_block"]
                        )
                    
                    # Adjust confidence based on session
                    adjusted_confidence, adj_reasons = self.session_rules.adjust_confidence(
                        trade_dict["confidence"], trade_spec.strategy, session_info, 
                        context.features.get("M5", {}), symbol
                    )
                    
                    # Update trade_spec confidence
                    if adjusted_confidence != trade_dict["confidence"]:
                        original_overall = trade_spec.confidence.get("overall", 50)
                        trade_spec.confidence["overall"] = int(adjusted_confidence)
                        logger.info(f"Router: Session adjusted confidence {original_overall} -> {adjusted_confidence}: {adj_reasons}")
                
                logger.info(f"Router: {symbol} -> {template.name} -> {trade_spec.strategy}")
                return DecisionOutcome(
                    status="ok",
                    trade_spec=trade_spec,
                    skip_reasons=[],
                    template_name=template.name,
                    template_version=template.version,
                    regime=context.regime.value,
                    session=context.session.value,
                    validation_score=validation_result.validation_score,
                    timestamp=context.timestamp,
                    session_tag=context.session.value,
                    decision_tags=[f"session={context.session.value}", f"template={template.name}", f"regime={context.regime.value}"]
                )
            else:
                # FIXED: Bubble validation errors (including M5 missing data warnings) to skip_reasons
                skip_reasons = validation_result.errors if validation_result else ["Validation failed"]
                
                # Also include validation warnings (e.g., auto-repair, missing data) for analytics
                if validation_result and validation_result.warnings:
                    skip_reasons.extend([f"Warning: {w}" for w in validation_result.warnings])
                
                logger.debug(f"Router: No valid trade for {symbol} using {template.name}: {skip_reasons}")
                return DecisionOutcome(
                    status="skip",
                    trade_spec=None,
                    skip_reasons=skip_reasons,
                    template_name=template.name,
                    template_version=template.version,
                    regime=context.regime.value,
                    session=context.session.value,
                    validation_score=validation_result.validation_score if validation_result else 0.0,
                    timestamp=context.timestamp,
                    session_tag=context.session.value,
                    decision_tags=[f"session={context.session.value}", f"template={template.name}", f"regime={context.regime.value}"]
                )
                
        except Exception as e:
            logger.error(f"Prompt router failed for {symbol}: {e}")
            return DecisionOutcome(
                status="skip",
                trade_spec=None,
                skip_reasons=[f"Router error: {e}"],
                template_name="error",
                template_version="error",
                regime="unknown",
                session="unknown",
                validation_score=0.0,
                timestamp=datetime.now(),
                session_tag="unknown",
                decision_tags=["error"]  # FIXED: Required field for exception path
            )
    
    def _create_context(self, symbol: str, features: Dict[str, Any], 
                       guardrails: Dict[str, Any]) -> RouterContext:
        """Create routing context from features and guardrails."""
        try:
            # FIXED: Normalize guardrail flag names and inject into features
            # Ensure news_blackout is available in M5 context for validator
            if "M5" not in features:
                features["M5"] = {}
            features["M5"]["news_blackout"] = guardrails.get("news_block", False) or guardrails.get("news_blackout", False)
            
            # Classify market regime
            regime = self._classify_regime(features)
            
            # Detect session
            session = self._detect_session(features)
            
            return RouterContext(
                symbol=symbol,
                regime=regime,
                session=session,
                features=features,
                guardrails=guardrails,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Context creation failed: {e}")
            return RouterContext(
                symbol=symbol,
                regime=MarketRegime.UNKNOWN,
                session=SessionType.CLOSED,
                features=features,
                guardrails=guardrails,
                timestamp=datetime.now()
            )
    
    def _classify_regime(self, features: Dict[str, Any]) -> MarketRegime:
        """Classify market regime based on feature analysis with improved precedence."""
        try:
            # Get cross-timeframe analysis
            cross_tf = features.get("cross_tf", {})
            trend_consensus = cross_tf.get("trend_consensus", "mixed")
            vol_regime = cross_tf.get("vol_regime_consensus", "normal")
            
            # Get individual timeframe data
            m5_data = features.get("M5", {})
            h1_data = features.get("H1", {})
            
            adx_m5 = m5_data.get("adx", 0.0)
            adx_h1 = h1_data.get("adx", 0.0)
            bb_width = m5_data.get("bb_width", 0.0)
            atr_ratio = m5_data.get("atr_ratio", 1.0)
            
            # IMPROVED: Regime classification with proper precedence
            # 1. Strong trend takes precedence unless volatility is extreme
            if trend_consensus in ["up", "down"] and max(adx_m5, adx_h1) >= 25:
                # Only classify as volatile if ATR ratio is very high AND volatility regime is high
                if vol_regime == "high" and atr_ratio > 1.5:
                    return MarketRegime.VOLATILE
                else:
                    return MarketRegime.TREND
            
            # 2. Moderate trend with decent ADX
            elif trend_consensus in ["up", "down"] and max(adx_m5, adx_h1) >= 20:
                return MarketRegime.TREND
            
            # 3. High volatility with breakout conditions
            elif vol_regime == "high" and atr_ratio > 1.3:
                return MarketRegime.VOLATILE
            
            # 4. Range conditions
            elif bb_width < 0.02 or max(adx_m5, adx_h1) < 15:
                return MarketRegime.RANGE
            
            # 5. Default to unknown
            else:
                return MarketRegime.UNKNOWN
                
        except Exception:
            return MarketRegime.UNKNOWN
    
    def _detect_session(self, features: Dict[str, Any]) -> SessionType:
        """Detect current trading session."""
        try:
            m5_data = features.get("M5", {})
            session = m5_data.get("session", "unknown").lower()
            
            if "asia" in session or "tokyo" in session:
                return SessionType.ASIA
            elif "london" in session:
                return SessionType.LONDON
            elif "new_york" in session or "ny" in session:
                return SessionType.NEW_YORK
            elif "overlap" in session:
                return SessionType.OVERLAP
            else:
                return SessionType.CLOSED
                
        except Exception:
            return SessionType.CLOSED
    
    def _select_template(self, context: RouterContext) -> Optional[PromptTemplate]:
        """Select appropriate prompt template based on context with session awareness."""
        try:
            regime = context.regime
            session = context.session
            
            # IMPROVED: Session-aware template selection
            if regime == MarketRegime.TREND:
                # Trend pullback works best in London/NY sessions
                if session in [SessionType.LONDON, SessionType.NEW_YORK, SessionType.OVERLAP]:
                    return self.template_manager.get_active_template("trend_pullback")
                else:
                    # Asia session - be more conservative
                    return self.template_manager.get_active_template("trend_pullback")
                    
            elif regime == MarketRegime.RANGE:
                # Range fade works best in Asia session
                if session == SessionType.ASIA:
                    return self.template_manager.get_active_template("range_fade")
                elif session in [SessionType.LONDON, SessionType.NEW_YORK]:
                    # NY session with high vol - lean skip unless range is wide
                    m5_data = context.features.get("M5", {})
                    bb_width = m5_data.get("bb_width", 0.0)
                    if bb_width > 0.03:  # Wide range
                        return self.template_manager.get_active_template("range_fade")
                    else:
                        return None  # Skip narrow ranges in NY
                else:
                    return self.template_manager.get_active_template("range_fade")
                    
            elif regime == MarketRegime.VOLATILE:
                # Breakout works best in London/NY/overlap
                if session in [SessionType.LONDON, SessionType.NEW_YORK, SessionType.OVERLAP]:
                    return self.template_manager.get_active_template("breakout")
                elif session == SessionType.ASIA:
                    # Asia session - require stronger volume/momentum
                    m5_data = context.features.get("M5", {})
                    volume_zscore = m5_data.get("volume_zscore", 0.0)
                    if volume_zscore > 1.5:  # Strong volume spike
                        return self.template_manager.get_active_template("breakout")
                    else:
                        return None  # Skip weak breakouts in Asia
                else:
                    return self.template_manager.get_active_template("breakout")
            else:
                # IMPROVED: Always skip on unknown regime to avoid bias toward trend in chop
                # Unknown regime means unclear market conditions - better to skip than assume trend
                return None
                
        except Exception as e:
            logger.error(f"Template selection failed: {e}")
            return None
    
    def _generate_prompt(self, template: PromptTemplate, context: RouterContext) -> str:
        """Generate complete prompt with features, guardrails, and session context."""
        try:
            # Extract features for JSON injection with guardrails
            features_json = self._format_features_for_prompt(context.features, context.guardrails, context.session)
            
            # Build complete prompt
            prompt = template.template.format(
                FEATURES_JSON=features_json,
                SYMBOL=context.symbol,
                SESSION=context.session.value.upper(),
                REGIME=context.regime.value.upper()
            )
            
            return prompt
            
        except Exception as e:
            logger.error(f"Prompt generation failed: {e}")
            return ""
    
    def _format_features_for_prompt(self, features: Dict[str, Any], guardrails: Dict[str, Any], session: SessionType) -> str:
        """Format features as JSON string for prompt injection with guardrails and session context."""
        try:
            # Create a clean feature summary for the prompt
            # IMPROVED: Add current_price explicitly for clarity and future non-M5 checks
            m5_data = features.get("M5", {})
            current_price = m5_data.get("close", 0.0)

            feature_summary = {
                "symbol": features.get("symbol", ""),
                "timestamp": features.get("timestamp", ""),
                "current_price": current_price,
                "session": session.value,
                "cross_tf": features.get("cross_tf", {}),
                "M5": self._summarize_timeframe(m5_data),
                "M15": self._summarize_timeframe(features.get("M15", {})),
                "H1": self._summarize_timeframe(features.get("H1", {})),
                "H4": self._summarize_timeframe(features.get("H4", {})),
                "guardrails": {
                    "news_blackout": guardrails.get("news_block", False),
                    "spread_atr_pct": m5_data.get("spread_atr_pct", 0.0),
                    "execution_quality": m5_data.get("execution_quality", "unknown"),
                    "exposure_limit": guardrails.get("exposure_limit", False)
                }
            }
            
            return json.dumps(feature_summary, indent=2)
            
        except Exception as e:
            logger.error(f"Feature formatting failed: {e}")
            return "{}"
    
    def _summarize_timeframe(self, tf_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a clean summary of timeframe data for prompts."""
        try:
            return {
                "trend_state": tf_data.get("trend_state", "mixed"),
                "rsi_14": tf_data.get("rsi_14", 50.0),
                "adx": tf_data.get("adx", 0.0),
                "ema_alignment": tf_data.get("ema_alignment", False),
                "atr_14": tf_data.get("atr_14", 0.0),
                "bb_width": tf_data.get("bb_width", 0.0),
                "pattern_flags": tf_data.get("pattern_flags", {}),
                "candlestick_flags": tf_data.get("candlestick_flags", {}),
                "session": tf_data.get("session", "unknown"),
                "news_blackout": tf_data.get("news_blackout", False)
            }
        except Exception:
            return {}
    
    def _execute_and_validate(self, prompt: str, template: PromptTemplate, 
                             context: RouterContext) -> Tuple[Optional[TradeSpec], Optional[ValidationResult]]:
        """Execute prompt and validate response using PromptValidator."""
        try:
            # This would integrate with your OpenAI service
            # For now, we'll simulate the LLM call
            response = self._call_llm(prompt)
            
            if not response:
                return None, None
            
            # IMPROVED: Use PromptValidator with template config
            template_config = {
                "min_rr": template.min_rr,
                "max_rr": template.max_rr,
                "order_types": template.order_types,
                "validation_rules": template.validation_rules
            }
            
            validation_result = self.validator.validate_response(
                response, template.strategy, context.features, template_config
            )
            
            if validation_result.is_valid:
                # Use original or repaired data
                data_to_use = validation_result.repaired_data or response
                trade_spec = self._create_trade_spec(data_to_use, template, context)
                return trade_spec, validation_result
            else:
                logger.debug(f"Validation failed for {context.symbol}: {validation_result.errors}")
                return None, validation_result
            
        except Exception as e:
            logger.error(f"LLM execution failed: {e}")
            return None, None
    
    def _create_trade_spec(self, response: Dict[str, Any], template: PromptTemplate, 
                          context: RouterContext) -> TradeSpec:
        """Create TradeSpec from validated response."""
        try:
            return TradeSpec(
                strategy=response.get("strategy", template.strategy),
                order_type=response.get("order_type", "skip"),
                entry=float(response.get("entry", 0)),
                sl=float(response.get("sl", 0)),
                tp=float(response.get("tp", 0)),
                rr=float(response.get("rr", 0)),
                confidence=response.get("confidence", {}),
                rationale=response.get("rationale", ""),
                tags=response.get("tags", []),
                template_version=template.version,
                regime_fit=response.get("confidence", {}).get("regime_fit", 0)
            )
        except Exception as e:
            logger.error(f"TradeSpec creation failed: {e}")
            raise
    
    def _call_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call LLM with prompt (placeholder for OpenAI integration)."""
        try:
            # IMPROVED: Add simulation path for unit tests
            # Check if we're in simulation mode (for testing)
            if hasattr(self, '_simulation_mode') and self._simulation_mode:
                return self._simulate_llm_response(prompt)

            # This would integrate with your existing OpenAI service
            # For now, return None to indicate no LLM integration yet
            return None

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    def _simulate_llm_response(self, prompt: str) -> Dict[str, Any]:
        """Simulate LLM response for testing purposes."""
        try:
            # Parse the prompt to determine strategy context
            if "TRENDING" in prompt or "trend" in prompt.lower():
                return {
                    "strategy": "trend_pullback",
                    "order_type": "buy_stop",
                    "entry": 102.5,
                    "sl": 100.0,
                    "tp": 107.5,
                    "rr": 2.0,
                    "confidence": {
                        "overall": 75,
                        "trend": 80,
                        "pattern": 70,
                        "volume": 75,
                        "regime_fit": 80
                    },
                    "rationale": "Simulated trend pullback response",
                    "tags": ["EMA_align", "ADX>20", "trend_pullback"]
                }
            elif "RANGING" in prompt or "range" in prompt.lower():
                return {
                    "strategy": "range_fade",
                    "order_type": "buy_limit",
                    "entry": 99.0,
                    "sl": 97.0,
                    "tp": 102.0,
                    "rr": 1.5,
                    "confidence": {
                        "overall": 65,
                        "range": 70,
                        "pattern": 60,
                        "volume": 65,
                        "regime_fit": 70
                    },
                    "rationale": "Simulated range fade response",
                    "tags": ["ADX<20", "RangeFade", "wick_rejections"]
                }
            else:  # Breakout
                return {
                    "strategy": "breakout",
                    "order_type": "buy_stop",
                    "entry": 105.0,
                    "sl": 102.0,
                    "tp": 112.0,
                    "rr": 2.5,
                    "confidence": {
                        "overall": 70,
                        "breakout": 75,
                        "volume": 70,
                        "pattern": 65,
                        "regime_fit": 75
                    },
                    "rationale": "Simulated breakout response",
                    "tags": ["ADX>25", "BreakoutBar", "VolumeSpike"]
                }

        except Exception as e:
            logger.error(f"LLM simulation failed: {e}")
            return None

    def enable_simulation_mode(self) -> None:
        """Enable simulation mode for testing."""
        self._simulation_mode = True
    
    def _get_session_info_dict(self, context: RouterContext) -> Dict[str, Any]:
        """
        Get comprehensive session info dictionary for session rules.
        IMPROVED Phase 4.2: Extract and standardize session context.
        """
        try:
            # Get session info from features or build it
            m5_data = context.features.get("M5", {})
            session = m5_data.get("session", "UNKNOWN").upper()
            
            # Try to get enhanced session info if available
            session_info = self.session_features.get_session_info()
            
            # Build session info dict
            return {
                "primary_session": session_info.primary_session if hasattr(session_info, 'primary_session') else session,
                "is_overlap": session_info.is_overlap if hasattr(session_info, 'is_overlap') else False,
                "overlap_type": session_info.overlap_type if hasattr(session_info, 'overlap_type') else None,
                "minutes_into_session": m5_data.get("session_minutes", 0),
                "session_strength": m5_data.get("session_strength", 0.7),
                "is_transition_period": session_info.is_transition_period if hasattr(session_info, 'is_transition_period') else False,
                "is_weekend": m5_data.get("is_weekend", False),
                "is_market_open": m5_data.get("is_market_open", True)
            }
            
        except Exception as e:
            logger.error(f"Session info extraction failed: {e}")
            # Return safe default
            return {
                "primary_session": "UNKNOWN",
                "is_overlap": False,
                "overlap_type": None,
                "minutes_into_session": 0,
                "session_strength": 0.7,
                "is_transition_period": False,
                "is_weekend": False,
                "is_market_open": True
            }

    def disable_simulation_mode(self) -> None:
        """Disable simulation mode."""
        self._simulation_mode = False
    
    
    def _create_template_manager(self):
        """Create template manager instance."""
        from infra.prompt_templates import create_template_manager
        return create_template_manager()
    
    def _create_validator(self):
        """Create validator instance."""
        from infra.prompt_validator import create_prompt_validator
        return create_prompt_validator()
    
    
    def _create_regime_classifier(self) -> Any:
        """Create regime classification system integrated with existing classifier."""
        try:
            from app.engine.regime_classifier import RegimeClassifier
            classifier = RegimeClassifier()
            logger.info("Regime classifier initialized successfully")
            return classifier
        except ImportError:
            logger.debug("RegimeClassifier not found, using built-in classification")
            return None
        except Exception as e:
            logger.warning(f"Failed to initialize regime classifier: {e}, using built-in classification")
            return None

    def _create_session_detector(self) -> Any:
        """Create session detection system integrated with SessionNewsFeatures."""
        try:
            # We already have self.session_features which provides session detection
            # No separate detector needed - we use SessionNewsFeatures directly
            logger.info("Session detector initialized (using SessionNewsFeatures)")
            return self.session_features
        except Exception as e:
            logger.warning(f"Failed to initialize session detector: {e}")
            return None


def create_prompt_router(session_rules_enabled: bool = True) -> PromptRouter:
    """
    Factory function to create prompt router instance.
    IMPROVED Phase 4.2: Accepts session_rules_enabled flag.
    """
    return PromptRouter(session_rules_enabled=session_rules_enabled)
