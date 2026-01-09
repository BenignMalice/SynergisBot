"""
Prompt Templates - Phase 2
Strategy-specific prompt templates for regime-aware trading
Ensures consistent, disciplined AI analysis within appropriate strategy contexts
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class PromptTemplate:
    """Prompt template definition"""
    name: str
    version: str
    strategy: str
    regime: str
    order_types: List[str]
    min_rr: float
    max_rr: float
    template: str
    validation_rules: Dict[str, Any]
    created_at: datetime

class PromptTemplateManager:
    """
    IMPROVED: Manages strategy-specific prompt templates.
    Provides versioning, validation, and template selection for regime-aware trading.
    """
    
    def __init__(self):
        self.templates = self._load_default_templates()
        self.active_versions = self._load_active_versions()
        
    def get_template(self, strategy: str, version: Optional[str] = None) -> Optional[PromptTemplate]:
        """Get prompt template for strategy and version."""
        try:
            if version:
                template_key = f"{strategy}_{version}"
            else:
                template_key = self.active_versions.get(strategy, f"{strategy}_v1")
            
            template_data = self.templates.get(template_key)
            if template_data:
                return PromptTemplate(**template_data)
            return None
            
        except Exception as e:
            logger.error(f"Template retrieval failed for {strategy}: {e}")
            return None
    
    def list_templates(self, strategy: Optional[str] = None) -> List[PromptTemplate]:
        """List available templates, optionally filtered by strategy."""
        try:
            templates = []
            for key, data in self.templates.items():
                if not strategy or data["strategy"] == strategy:
                    templates.append(PromptTemplate(**data))
            return templates
            
        except Exception as e:
            logger.error(f"Template listing failed: {e}")
            return []
    
    def get_rule_config(self, strategy: str, version: Optional[str] = None) -> Dict[str, Any]:
        """Get rule configuration for strategy and version."""
        try:
            template = self.get_template(strategy, version)
            if template:
                return {
                    "min_rr": template.min_rr,
                    "max_rr": template.max_rr,
                    "order_types": template.order_types,
                    "validation_rules": template.validation_rules
                }
            return {}
            
        except Exception as e:
            logger.error(f"Rule config retrieval failed for {strategy}: {e}")
            return {}
    
    def get_active_template(self, strategy: str) -> Optional[PromptTemplate]:
        """Get active template for strategy."""
        try:
            version = self.active_versions.get(strategy)
            if version:
                return self.get_template(strategy, version)
            return None
            
        except Exception as e:
            logger.error(f"Active template retrieval failed for {strategy}: {e}")
            return None
    
    def validate_template(self, template: PromptTemplate) -> List[str]:
        """Validate template structure and rules."""
        errors = []
        
        try:
            # Check required fields
            if not template.name:
                errors.append("Template name is required")
            if not template.strategy:
                errors.append("Template strategy is required")
            if not template.template:
                errors.append("Template content is required")
            
            # Check order types
            if not template.order_types:
                errors.append("Order types must be specified")
            
            # Check RR bounds
            if template.min_rr <= 0:
                errors.append("Min RR must be positive")
            if template.max_rr <= template.min_rr:
                errors.append("Max RR must be greater than min RR")
            
            # Check template content
            if "{FEATURES_JSON}" not in template.template:
                errors.append("Template must include {FEATURES_JSON} placeholder")
            
            # IMPROVED: Check for Enhanced Analysis Rules tokens
            enhanced_rules_tokens = [
                "cross_tf",  # Cross-timeframe analysis
                "spread_atr_pct",  # Cost validation
                "news_blackout",  # News filtering
                "execution_quality",  # Execution constraints
                "confluence",  # Multi-timeframe agreement
                "regime_fit"  # Strategy-regime alignment
            ]
            
            missing_tokens = []
            for token in enhanced_rules_tokens:
                if token not in template.template:
                    missing_tokens.append(token)
            
            if missing_tokens:
                errors.append(f"Missing Enhanced Analysis Rules tokens: {missing_tokens}")
            
            # Check RR bounds are reasonable
            if template.min_rr < 1.0:
                errors.append(f"Min RR too low: {template.min_rr} (recommended >= 1.0)")
            if template.max_rr > 10.0:
                errors.append(f"Max RR too high: {template.max_rr} (recommended <= 10.0)")
            
            # Check order types are valid
            valid_order_types = ["buy_stop", "sell_stop", "buy_limit", "sell_limit", "skip"]
            invalid_types = [ot for ot in template.order_types if ot not in valid_order_types]
            if invalid_types:
                errors.append(f"Invalid order types: {invalid_types}")

            # IMPROVED: Regex-based RR language detection for robust matching
            import re
            template_text = template.template.lower()

            # Format min_rr for regex patterns
            min_rr_str = str(template.min_rr)
            min_rr_formatted = f"{template.min_rr:.1f}"

            # Use regex for flexible pattern matching
            rr_patterns = [
                # Exact number matches with various symbols
                rf"rr\s*[≥>=]+\s*{re.escape(min_rr_str)}",
                rf"risk\s+reward\s*[≥>=]+\s*{re.escape(min_rr_str)}",
                rf"reward\s*:\s*risk\s*[≥>=]+\s*{re.escape(min_rr_str)}",
                # At least/minimum with number
                rf"at\s+least\s+{re.escape(min_rr_str)}\s*[×x]",
                rf"minimum\s+{re.escape(min_rr_str)}\s*[×x]",
                # Flexible number matching (1.8, 1.80, etc.)
                rf"rr\s*[≥>=]+\s*{re.escape(min_rr_formatted)}",
                rf"at\s+least\s+{re.escape(min_rr_formatted)}\s*[×x]",
                # Common phrases that indicate RR requirements
                r"rr\s*[≥>=]+",
                r"at\s+least",
                r"minimum\s+rr",
                r"reward.*risk.*ratio"
            ]

            # Check if any pattern matches
            has_rr_language = any(re.search(pattern, template_text) for pattern in rr_patterns)

            # Also check for the specific numeric value (more flexible)
            specific_rr_patterns = [
                rf"[≥>=]\s*{re.escape(min_rr_str)}",
                rf"[≥>=]\s*{re.escape(min_rr_formatted)}",
                rf"{re.escape(min_rr_str)}\s*[×x]",
                rf"{re.escape(min_rr_formatted)}\s*[×x]"
            ]
            has_specific_rr = any(re.search(pattern, template_text) for pattern in specific_rr_patterns)

            if not has_rr_language or not has_specific_rr:
                errors.append(f"Template should mention RR requirement (RR ≥ {template.min_rr}) - found basic RR language: {has_rr_language}, specific value: {has_specific_rr}")

            return errors
            
        except Exception as e:
            errors.append(f"Validation error: {e}")
            return errors
    
    def _load_default_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load default prompt templates."""
        return {
            "trend_pullback_v1": {
                "name": "Trend Pullback Template v1",
                "version": "v1",
                "strategy": "trend_pullback",
                "regime": "trend",
                "order_types": ["buy_stop", "sell_stop"],
                "min_rr": 1.8,
                "max_rr": 3.0,
                "template": self._get_trend_pullback_v1(),
                "validation_rules": {
                    "min_adx": 20,
                    "require_ema_alignment": True,
                    "require_volume_confirmation": True
                },
                "created_at": datetime.now()
            },
            "trend_pullback_v2": {
                "name": "Trend Pullback Template v2",
                "version": "v2",
                "strategy": "trend_pullback",
                "regime": "trend",
                "order_types": ["buy_stop", "sell_stop"],
                "min_rr": 1.8,
                "max_rr": 3.0,
                "template": self._get_trend_pullback_v2(),
                "validation_rules": {
                    "min_adx": 20,
                    "require_ema_alignment": True,
                    "require_volume_confirmation": True,
                    "require_pattern_confirmation": True
                },
                "created_at": datetime.now()
            },
            "range_fade_v1": {
                "name": "Range Fade Template v1",
                "version": "v1",
                "strategy": "range_fade",
                "regime": "range",
                "order_types": ["buy_limit", "sell_limit"],
                "min_rr": 1.5,
                "max_rr": 2.5,
                "template": self._get_range_fade_v1(),
                "validation_rules": {
                    "max_adx": 20,
                    "require_range_confirmation": True,
                    "require_wick_rejection": True
                },
                "created_at": datetime.now()
            },
            "range_fade_v2": {
                "name": "Range Fade Template v2",
                "version": "v2",
                "strategy": "range_fade",
                "regime": "range",
                "order_types": ["buy_limit", "sell_limit"],
                "min_rr": 1.5,
                "max_rr": 2.5,
                "template": self._get_range_fade_v2(),
                "validation_rules": {
                    "max_adx": 20,
                    "require_range_confirmation": True,
                    "require_wick_rejection": True,
                    "require_session_awareness": True
                },
                "created_at": datetime.now()
            },
            "breakout_v1": {
                "name": "Breakout Template v1",
                "version": "v1",
                "strategy": "breakout",
                "regime": "volatile",
                "order_types": ["buy_stop", "sell_stop"],
                "min_rr": 2.0,
                "max_rr": 4.0,
                "template": self._get_breakout_v1(),
                "validation_rules": {
                    "min_adx": 25,
                    "require_volume_spike": True,
                    "require_breakout_bar": True
                },
                "created_at": datetime.now()
            },
            "breakout_v2": {
                "name": "Breakout Template v2",
                "version": "v2",
                "strategy": "breakout",
                "regime": "volatile",
                "order_types": ["buy_stop", "sell_stop"],
                "min_rr": 2.0,
                "max_rr": 4.0,
                "template": self._get_breakout_v2(),
                "validation_rules": {
                    "min_adx": 25,
                    "require_volume_spike": True,
                    "require_breakout_bar": True,
                    "require_momentum_confirmation": True
                },
                "created_at": datetime.now()
            }
        }
    
    def _load_active_versions(self) -> Dict[str, str]:
        """Load active template versions."""
        return {
            "trend_pullback": "v2",
            "range_fade": "v2", 
            "breakout": "v2"
        }
    
    def _get_trend_pullback_v1(self) -> str:
        """Trend pullback template v1."""
        return """You are a trading analyst. The market is in a STRONG TRENDING regime.

Inputs (multi-timeframe snapshot provided below):
{FEATURES_JSON}

Task:
Identify if a TREND PULLBACK trade is valid. Output STRICT JSON only:

{{
  "strategy": "trend_pullback",
  "order_type": "buy_stop|sell_stop|skip",
  "entry": <float>,
  "sl": <float>,
  "tp": <float>,
  "rr": <float>,
  "confidence": {{
    "overall": <0-100>,
    "trend": <0-100>,
    "pattern": <0-100>,
    "volume": <0-100>,
    "regime_fit": <0-100>
  }},
  "rationale": "Briefly explain using trend alignment, structure, and session.",
  "tags": ["EMA_align", "ADX>20", "trend_pullback"]
}}

Rules:
- Only use stop orders (buy_stop in uptrend, sell_stop in downtrend).
- SL must be below/above recent swing or ≥0.4×ATR.
- TP must be at least 1.8× risk (RR ≥ 1.8).
- If conditions are weak, output "skip" with rationale."""
    
    def _get_trend_pullback_v2(self) -> str:
        """Trend pullback template v2 with enhanced analysis."""
        return """You are a trading analyst specializing in scalp/intraday trading. The market is in a STRONG TRENDING regime.

TRADING CONSTRAINTS:
- ONLY scalp or day trades (close within same session)
- Maximum position size: 0.01 lots
- Focus on M5/M15 timeframes for entries

Inputs (multi-timeframe snapshot provided below):
{FEATURES_JSON}

Task:
Identify if a TREND PULLBACK trade is valid. Output STRICT JSON only:

{{
  "strategy": "trend_pullback",
  "order_type": "buy_stop|sell_stop|skip",
  "entry": <float>,
  "sl": <float>,
  "tp": <float>,
  "rr": <float>,
  "confidence": {{
    "overall": <0-100>,
    "trend": <0-100>,
    "pattern": <0-100>,
    "volume": <0-100>,
    "regime_fit": <0-100>
  }},
  "rationale": "Briefly explain using trend alignment, structure, and session.",
  "tags": ["EMA_align", "ADX>20", "trend_pullback"]
}}

Enhanced Analysis Rules:
- Use cross_tf.trend_agreement > 0.6 for strong trend confirmation
- Require cross_tf.rsi_confluence > 0.5 for momentum validation
- Check pattern_flags for entry confirmation (bull_engulfing, hammer, etc.)
- Validate swing_highs/swing_lows for structure breaks
- Check spread_atr_pct < 0.25 for good execution conditions
- IMPROVED Phase 4.2: Session-specific guidance for trend pullbacks:
  * LONDON session: Base +10 confidence (high liquidity, clean trends)
    - First 30 minutes: Reduce confidence by 10 (avoid false breakouts)
    - BOS confirmation: Add +10 confidence (structure break validated)
    - Mid-range entry (0.35-0.65): Reduce confidence by 15 (no edge)
  * NY session: Base +0 confidence (volatility, reversals common)
    - Require BOS for trend continuation (bos_bull or bos_bear = True)
    - Spread spike (>30% ATR): Reduce confidence by 10
    - Post-news window: Check news_blackout flag, skip if True
  * ASIA session: Base -10 confidence (thin liquidity, weak trends)
    - Reduce confidence by 15 if trend_strength < 0.7 (unreliable)
    - Require volume_zscore >= 1.8 AND BOS for any trend trade
  * LONDON-NY overlap (13:00-16:00 UTC): Base +15 confidence (peak liquidity)
  * Transition periods: Reduce confidence by 10 (session handoff uncertainty)
- Phase 4.1 Structure features (bonus scoring):
  * Equal highs/lows cluster (eq_high_cluster/eq_low_cluster): +5 confidence
  * Sweep detected (sweep_bull/sweep_bear): +8 confidence (post-liquidity grab)
  * Fair Value Gap (fvg_bull/fvg_bear): +6 confidence if pullback into FVG
  * Wick rejection (wick_rejection_bull/bear): +5 confidence at key levels
- Consider session_strength (0.0-1.0) for timing quality
- Check news_blackout for trading restrictions
- Validate execution_quality for trade feasibility

Rules:
- Only use stop orders (buy_stop in uptrend, sell_stop in downtrend).
- SL must be below/above recent swing or ≥0.4×ATR.
- TP must be at least 1.8× risk (RR ≥ 1.8).
- If conditions are weak, output "skip" with rationale."""
    
    def _get_range_fade_v1(self) -> str:
        """Range fade template v1."""
        return """You are a trading analyst. The market is in a RANGING regime.

Inputs (multi-timeframe snapshot provided below):
{FEATURES_JSON}

Task:
Identify if a RANGE FADE trade is valid. Output STRICT JSON only:

{{
  "strategy": "range_fade",
  "order_type": "buy_limit|sell_limit|skip",
  "entry": <float>,
  "sl": <float>,
  "tp": <float>,
  "rr": <float>,
  "confidence": {{
    "overall": <0-100>,
    "range": <0-100>,
    "pattern": <0-100>,
    "volume": <0-100>,
    "regime_fit": <0-100>
  }},
  "rationale": "Briefly explain using range edges, wicks, and session.",
  "tags": ["ADX<20", "RangeFade", "wick_rejections"]
}}

Rules:
- Only use limit orders at range edges (buy at support, sell at resistance).
- SL must be beyond the range boundary or ≥0.3×ATR.
- TP = mid-range or opposite edge with RR ≥ 1.5.
- Skip if breakout or high-impact news within 30m."""
    
    def _get_range_fade_v2(self) -> str:
        """Range fade template v2 with enhanced analysis."""
        return """You are a trading analyst specializing in scalp/intraday trading. The market is in a RANGING regime.

TRADING CONSTRAINTS:
- ONLY scalp or day trades (close within same session)
- Maximum position size: 0.01 lots
- Focus on M5/M15 timeframes for entries

Inputs (multi-timeframe snapshot provided below):
{FEATURES_JSON}

Task:
Identify if a RANGE FADE trade is valid. Output STRICT JSON only:

{{
  "strategy": "range_fade",
  "order_type": "buy_limit|sell_limit|skip",
  "entry": <float>,
  "sl": <float>,
  "tp": <float>,
  "rr": <float>,
  "confidence": {{
    "overall": <0-100>,
    "range": <0-100>,
    "pattern": <0-100>,
    "volume": <0-100>,
    "regime_fit": <0-100>
  }},
  "rationale": "Briefly explain using range edges, wicks, and session.",
  "tags": ["ADX<20", "RangeFade", "wick_rejections"]
}}

Enhanced Analysis Rules:
- Use cross_tf.vol_regime_consensus = "normal" for range confirmation
- Check range_position and near_range_high/low for edge proximity
- Analyze wick_metrics for rejection strength and asymmetry
- Use support_levels/resistance_levels for key level identification
- Check spread_atr_pct < 0.25 for good execution conditions
- IMPROVED Phase 4.2: Session-specific guidance for range fades:
  * ASIA session: Base +15 confidence (thin liquidity, defined ranges, mean reversion)
    - Require bb_width >= 0.02 for decent range width
    - Wick rejection bonus: +10 confidence (strong rejection at edges)
    - Well-defined range edges preferred
  * LONDON session: Base -20 confidence (breakouts common, avoid ranges)
    - Only allow if bb_width >= 0.03 (wide, confirmed range)
    - High ADX (>20): Reduce confidence by 20 (trend forming, avoid fade)
  * NY session: Base -15 confidence (volatility, reversals, erratic)
    - Require bb_width >= 0.03 AND no news within 45min
    - Mid-range entry: Skip (no edge in choppy NY ranges)
  * LONDON-NY overlap: Base -25 confidence (peak momentum, ranges break)
  * Transition periods: Base +5 confidence (quieter handoff periods)
- Phase 4.1 Structure features (bonus scoring):
  * Equal highs/lows cluster: +5 confidence (resting liquidity at edges)
  * Sweep + rejection: +10 confidence (liquidity grab then reversal)
  * Fair Value Gap at range edge: +6 confidence (magnet for mean reversion)
  * Wick rejection: +10 confidence (strong rejection signal)
- Check execution_quality for trade feasibility
- Check news_blackout for trading restrictions
- Validate confluence for multi-timeframe agreement

Rules:
- Only use limit orders at range edges (buy at support, sell at resistance).
- SL must be beyond the range boundary or ≥0.3×ATR.
- TP = mid-range or opposite edge with RR ≥ 1.5.
- Skip if breakout or high-impact news within 30m."""
    
    def _get_breakout_v1(self) -> str:
        """Breakout template v1."""
        return """You are a trading analyst. The market is in a VOLATILE BREAKOUT regime.

Inputs (multi-timeframe snapshot provided below):
{FEATURES_JSON}

Task:
Identify if a BREAKOUT trade is valid. Output STRICT JSON only:

{{
  "strategy": "breakout",
  "order_type": "buy_stop|sell_stop|skip",
  "entry": <float>,
  "sl": <float>,
  "tp": <float>,
  "rr": <float>,
  "confidence": {{
    "overall": <0-100>,
    "breakout": <0-100>,
    "volume": <0-100>,
    "pattern": <0-100>,
    "regime_fit": <0-100>
  }},
  "rationale": "Briefly explain using breakout bar, volume, and session.",
  "tags": ["ADX>25", "BreakoutBar", "VolumeSpike"]
}}

Rules:
- Only use stop orders (above resistance for buy, below support for sell).
- SL must be below/above breakout candle wick or ≥0.5×ATR.
- TP must be ≥2.0× risk (RR ≥ 2.0) with option to trail if momentum expands.
- Avoid trading if spread %ATR is too high."""
    
    def _get_breakout_v2(self) -> str:
        """Breakout template v2 with enhanced analysis."""
        return """You are a trading analyst specializing in scalp/intraday trading. The market is in a VOLATILE BREAKOUT regime.

TRADING CONSTRAINTS:
- ONLY scalp or day trades (close within same session)
- Maximum position size: 0.01 lots
- Focus on M5/M15 timeframes for entries
- OCO brackets ONLY for breakout situations at key zones

Inputs (multi-timeframe snapshot provided below):
{FEATURES_JSON}

Task:
Identify if a BREAKOUT trade is valid. Output STRICT JSON only:

{{
  "strategy": "breakout",
  "order_type": "buy_stop|sell_stop|skip",
  "entry": <float>,
  "sl": <float>,
  "tp": <float>,
  "rr": <float>,
  "confidence": {{
    "overall": <0-100>,
    "breakout": <0-100>,
    "volume": <0-100>,
    "pattern": <0-100>,
    "regime_fit": <0-100>
  }},
  "rationale": "Briefly explain using breakout bar, volume, and session.",
  "tags": ["ADX>25", "BreakoutBar", "VolumeSpike"]
}}

Enhanced Analysis Rules:
- Use cross_tf.vol_regime_consensus = "high" for volatility confirmation
- Check pattern_flags for breakout patterns (outside_bar, breakout_bar)
- Analyze volume_zscore and volume_spike for confirmation
- Use swing_highs/swing_lows for breakout level identification
- IMPROVED Phase 4.2: Session-specific guidance for breakouts:
  * LONDON session: Base +10 confidence (high volume, clean breakouts)
    - First 30 minutes: Reduce confidence by 10 (false breakouts common)
    - Volume confirmation: Require volume_zscore >= 1.0
    - BOS confirmation: +10 confidence (structure validated)
  * NY session: Base +5 confidence (volatility supports breakouts)
    - Require volume_zscore >= 1.0 for confirmation
    - Spread spike (>30% ATR): Reduce confidence by 10
    - Post-news breakouts: Validate with momentum (MACD hist > 0)
  * ASIA session: Base -20 confidence (thin volume, false breakouts)
    - Require volume_zscore >= 2.0 AND Donchian breach (exceptional conditions)
    - Without both: Skip (insufficient liquidity)
  * LONDON-NY overlap (13:00-16:00 UTC): Base +15 confidence (peak liquidity, best breakouts)
  * Transition periods: Reduce confidence by 15 (uncertain liquidity)
- Phase 4.1 Structure features (bonus scoring):
  * Equal highs/lows sweep: +8 confidence (liquidity grabbed before breakout)
  * BOS/CHOCH confirmed: +10 confidence (market structure validated)
  * Fair Value Gap post-breakout: +6 confidence (retest zone identified)
  * Strong wick asymmetry: +5 confidence (momentum directional)
- Consider session overlap periods for enhanced liquidity
- Check execution_quality and wick_quality for trade feasibility
- Validate spread_atr_pct < 0.25 for good execution conditions
- Check news_blackout for trading restrictions
- Validate confluence for multi-timeframe agreement

Rules:
- Only use stop orders (above resistance for buy, below support for sell).
- SL must be below/above breakout candle wick or ≥0.5×ATR.
- TP must be ≥2.0× risk (RR ≥ 2.0) with option to trail if momentum expands.
- Avoid trading if spread %ATR is too high."""


def create_template_manager() -> PromptTemplateManager:
    """Factory function to create template manager instance."""
    return PromptTemplateManager()
