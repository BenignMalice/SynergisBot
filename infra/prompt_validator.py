"""
Prompt Validator - Phase 2
JSON validation and auto-repair system for prompt router outputs
Ensures consistent, valid trade specifications from AI analysis
"""

import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Result of validation process"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    repaired_data: Optional[Dict[str, Any]]
    validation_score: float

class PromptValidator:
    """
    IMPROVED: Validates and auto-repairs prompt router outputs.
    Ensures JSON schema compliance and business rule validation.
    """
    
    def __init__(self):
        self.schemas = self._load_validation_schemas()
        self.repair_rules = self._load_repair_rules()
        
    def validate_response(self, response: Dict[str, Any], strategy: str,
                         context: Dict[str, Any], template_config: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """Validate and optionally repair AI response."""
        try:
            errors = []
            warnings = []
            repaired_data = None

            # IMPROVED: Template-absent guard - explicit failure if template_config missing
            if template_config is None:
                logger.error(f"template_config required for validation - strategy: {strategy}")
                return ValidationResult(
                    is_valid=False,
                    errors=["template_config required for validation"],
                    warnings=[],
                    repaired_data=None,
                    validation_score=0.0
                )

            # JSON schema validation
            schema_errors = self._validate_schema(response, strategy)
            errors.extend(schema_errors)
            
            # Business rule validation
            business_errors = self._validate_business_rules(response, strategy, context, template_config)
            errors.extend(business_errors)
            
            # Auto-repair if possible
            if errors and self._can_repair(response, strategy):
                repaired_data = self._repair_response(response, strategy, context)
                if repaired_data:
                    # Re-validate repaired data (schema + business rules)
                    repair_schema_errors = self._validate_schema(repaired_data, strategy)
                    if not repair_schema_errors:
                        # Run business rule validation on repaired data
                        repair_business_errors = self._validate_business_rules(repaired_data, strategy, context, template_config)
                        if not repair_business_errors:
                            # Repaired response is fully valid
                            errors = []
                            warnings.append("Response was auto-repaired")
                        else:
                            # Repaired response still has business rule errors
                            errors = repair_business_errors
                    else:
                        # Repaired response fails schema validation
                        errors.extend(repair_schema_errors)
            
            # Calculate validation score
            validation_score = self._calculate_validation_score(response, errors, warnings)
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                repaired_data=repaired_data,
                validation_score=validation_score
            )
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                errors=[f"Validation error: {e}"],
                warnings=[],
                repaired_data=None,
                validation_score=0.0
            )
    
    def _validate_schema(self, response: Dict[str, Any], strategy: str) -> List[str]:
        """Validate JSON schema compliance."""
        errors = []
        
        try:
            # Required fields
            required_fields = ["strategy", "order_type", "entry", "sl", "tp", "rr", "confidence", "rationale", "tags"]
            for field in required_fields:
                if field not in response:
                    errors.append(f"Missing required field: {field}")
            
            # Data type validation
            if "entry" in response and not isinstance(response["entry"], (int, float)):
                errors.append("Entry must be numeric")
            if "sl" in response and not isinstance(response["sl"], (int, float)):
                errors.append("SL must be numeric")
            if "tp" in response and not isinstance(response["tp"], (int, float)):
                errors.append("TP must be numeric")
            if "rr" in response and not isinstance(response["rr"], (int, float)):
                errors.append("RR must be numeric")
            
            # Range validation
            if "rr" in response and isinstance(response["rr"], (int, float)):
                if response["rr"] < 0:
                    errors.append("RR must be positive")
                if response["rr"] > 10:
                    errors.append("RR seems too high")
            
            # Confidence validation
            if "confidence" in response and isinstance(response["confidence"], dict):
                for key, value in response["confidence"].items():
                    if not isinstance(value, (int, float)) or value < 0 or value > 100:
                        errors.append(f"Confidence {key} must be 0-100")
            
            return errors
            
        except Exception as e:
            errors.append(f"Schema validation error: {e}")
            return errors
    
    def _validate_business_rules(self, response: Dict[str, Any], strategy: str,
                              context: Dict[str, Any], template_config: Optional[Dict[str, Any]] = None) -> List[str]:
        """Validate business rule compliance."""
        errors = []

        # IMPROVED: Additional guard for template_config (shouldn't be needed due to main guard)
        if template_config is None:
            logger.error(f"template_config required for business rule validation - strategy: {strategy}")
            return ["template_config required for business rule validation"]

        try:
            order_type = response.get("order_type", "")
            entry = response.get("entry", 0)
            sl = response.get("sl", 0)
            tp = response.get("tp", 0)
            rr = response.get("rr", 0)
            
            # IMPROVED: Template config is single source of truth
            if template_config:
                min_rr = template_config.get("min_rr", 1.0)
                max_rr = template_config.get("max_rr", 10.0)
                valid_order_types = template_config.get("order_types", [])
                
                # RR validation using template config (SSOT)
                if rr < min_rr:
                    errors.append(f"RR too low: {rr} < {min_rr}")
                if rr > max_rr:
                    errors.append(f"RR too high: {rr} > {max_rr}")
                
                # Order type validation using template config (SSOT)
                if order_type not in valid_order_types and order_type != "skip":
                    errors.append(f"Invalid order type {order_type} for strategy {strategy}")
                    logger.debug(f"Order type validation failed: {order_type} not in {valid_order_types}")
                else:
                    logger.debug(f"Order type validation passed: {order_type} in {valid_order_types}")
            # Note: Template config is now required - no fallback to internal schemas
            # This ensures single source of truth for all validation rules
            
            # IMPROVED: Always run strategy-specific validation for additional checks
            if strategy == "trend_pullback":
                strategy_errors = self._validate_trend_pullback(response, context)
                errors.extend(strategy_errors)
                logger.debug(f"Trend pullback validation errors: {strategy_errors}")
            elif strategy == "range_fade":
                strategy_errors = self._validate_range_fade(response, context)
                errors.extend(strategy_errors)
                logger.debug(f"Range fade validation errors: {strategy_errors}")
            elif strategy == "breakout":
                strategy_errors = self._validate_breakout(response, context)
                errors.extend(strategy_errors)
                logger.debug(f"Breakout validation errors: {strategy_errors}")
            
            # IMPROVED: Validate HOLD/skip orders don't have contradictory trade levels
            if order_type == "skip" or strategy == "hold":
                # HOLD recommendations shouldn't have actual trade levels
                # If they do, ensure they're at least geometrically consistent
                if entry > 0 and sl > 0 and tp > 0:
                    # Check for impossible geometry (TP on wrong side of SL)
                    if sl < entry and tp < sl:  # Sell but TP below SL
                        errors.append(f"HOLD/skip with invalid geometry: TP ({tp}) below SL ({sl}) for sell structure")
                    elif sl > entry and tp > sl:  # Buy but TP above SL
                        errors.append(f"HOLD/skip with invalid geometry: TP ({tp}) above SL ({sl}) for buy structure")
            
            # Order type validation
            if order_type != "skip":
                if not self._validate_order_type_logic(order_type, entry, sl, tp):
                    errors.append("Invalid order type logic")
            
            # IMPROVED: Geometry and structure validation
            geometry_errors = self._validate_geometry(response, context)
            errors.extend(geometry_errors)
            
            # IMPROVED: Cost validation
            cost_errors = self._validate_costs(response, context)
            errors.extend(cost_errors)

            # IMPROVED: News and session validation
            session_errors = self._validate_session_news(response, context)
            errors.extend(session_errors)

            # IMPROVED: RR vs geometry recompute after fixes
            rr_recompute_errors = self._validate_rr_vs_geometry(response, context, template_config)
            errors.extend(rr_recompute_errors)

            return errors
            
        except Exception as e:
            errors.append(f"Business rule validation error: {e}")
            return errors
    
    def _validate_costs(self, response: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """Validate execution costs and guardrails."""
        errors = []
        
        try:
            # FIXED: Context is the features dict directly, not wrapped
            m5_data = context.get("M5", {})
            spread_atr_pct = m5_data.get("spread_atr_pct", 0.0)
            execution_quality = m5_data.get("execution_quality", "unknown")
            
            # IMPROVED: EV-aware cost gating with RR consideration
            entry = response.get("entry", 0)
            tp = response.get("tp", 0)
            rr = response.get("rr", 0)
            
            if entry > 0 and tp > 0 and rr > 0:
                # Calculate expected slippage (proxy from recent data)
                expected_slippage_atr_pct = m5_data.get("expected_slippage_atr_pct", 0.05)  # 5% default
                
                # Calculate total cost as % of planned RR
                total_cost_atr_pct = spread_atr_pct + expected_slippage_atr_pct
                cost_rr_ratio = total_cost_atr_pct / rr if rr > 0 else 1.0
                
                # EV erosion check: single hard threshold to avoid ambiguity
                # FIXED: Use 20% as the ONLY threshold for cost errors (no secondary spread check)
                if cost_rr_ratio > 0.20:
                    errors.append(f"Costs too high: {cost_rr_ratio:.1%} of planned RR (spread: {spread_atr_pct:.1%}, slippage: {expected_slippage_atr_pct:.1%})")
            
            # Execution quality validation
            if execution_quality == "poor":
                errors.append("Poor execution quality detected")
            
            return errors
            
        except Exception as e:
            errors.append(f"Cost validation error: {e}")
            return errors
    
    def _validate_session_news(self, response: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """
        Validate session and news constraints.
        IMPROVED Phase 4.2: Enhanced with standardized sessions and Phase 4.1 structure checks.
        """
        errors = []
        
        try:
            # FIXED: Context is the features dict directly, not wrapped
            m5_data = context.get("M5", {})
            news_blackout = m5_data.get("news_blackout", False)
            session = m5_data.get("session", "unknown").upper()  # Normalize to uppercase
            
            # News blackout validation
            if news_blackout and response.get("order_type") != "skip":
                errors.append("Trading during news blackout period")
            
            # IMPROVED Phase 4.2: Enhanced session-mirrored rules
            strategy = response.get("strategy", "")
            order_type = response.get("order_type", "")

            if order_type == "skip":
                return errors  # Skip validation for skip orders

            # Range fade session rules (Phase 4.2 enhanced)
            if strategy == "range_fade":
                if session in ["NY", "LONDON"]:
                    bb_width = m5_data.get("bb_width", 0.0)
                    if session == "LONDON" and bb_width < 0.03:
                        errors.append("Range too narrow for LONDON session (require bb_width >= 0.03)")
                    elif session == "NY" and bb_width < 0.03:
                        errors.append("Range too narrow for NY session (require bb_width >= 0.03)")
                    # Additional NY post-news caution
                    if session == "NY" and news_blackout:
                        errors.append("Range fade blocked in NY during news events")
                    # Mid-range entry check
                    range_position = m5_data.get("range_position", 0.5)
                    if 0.35 < range_position < 0.65:
                        errors.append("Mid-range entry (0.35-0.65) has no edge in NY/LONDON")
                elif session == "ASIA":
                    # Range fade preferred in Asia
                    bb_width = m5_data.get("bb_width", 0.0)
                    if bb_width < 0.02:
                        errors.append("Range too narrow for ASIA session (require bb_width >= 0.02)")
                    # Check for unexpected breakout conditions
                    volume_zscore = m5_data.get("volume_zscore", 0.0)
                    if volume_zscore > 2.0:
                        errors.append("Volume spike detected in ASIA - consider breakout instead")

            # Breakout session rules (Phase 4.2 enhanced)
            elif strategy == "breakout":
                if session == "ASIA":
                    # Breakout in Asia requires exceptional conditions
                    volume_zscore = m5_data.get("volume_zscore", 0.0)
                    donchian_breach = m5_data.get("donchian_breach", False)
                    if volume_zscore < 2.0 or not donchian_breach:
                        errors.append(
                            f"Breakout in ASIA requires volume_z >= 2.0 AND Donchian breach "
                            f"(got volume_z={volume_zscore:.1f}, donchian={donchian_breach})"
                        )
                elif session in ["LONDON", "NY"]:
                    # Breakout preferred in major sessions
                    volume_zscore = m5_data.get("volume_zscore", 0.0)
                    if volume_zscore < 1.0:
                        errors.append(f"Breakout in {session} requires volume_z >= 1.0 (got {volume_zscore:.1f})")
                    # London open spread spike check
                    if session == "LONDON":
                        spread_atr_pct = m5_data.get("spread_atr_pct", 0.0)
                        if spread_atr_pct > 0.30:
                            errors.append(f"High spread in LONDON session ({spread_atr_pct:.1%} ATR)")

            # Trend pullback session rules (Phase 4.2 enhanced)
            elif strategy == "trend_pullback":
                if session == "ASIA":
                    # Trend pullback requires exceptional conditions in Asia
                    volume_zscore = m5_data.get("volume_zscore", 0.0)
                    bos = m5_data.get("bos_bull") or m5_data.get("bos_bear")
                    if volume_zscore < 1.8 or not bos:
                        errors.append(
                            f"Trend in ASIA requires volume_z >= 1.8 AND BOS "
                            f"(got volume_z={volume_zscore:.1f}, BOS={bos})"
                        )
                elif session == "NY":
                    # NY requires BOS for trend continuation
                    bos = m5_data.get("bos_bull") or m5_data.get("bos_bear")
                    if not bos:
                        errors.append("Trend continuation in NY requires BOS confirmation (reversals common)")
                    # NY post-news caution
                    if news_blackout:
                        errors.append("Trend pullback blocked in NY during news events")
                # Mid-range entry check for London/NY
                if session in ["LONDON", "NY"]:
                    range_position = m5_data.get("range_position", 0.5)
                    if 0.35 < range_position < 0.65:
                        errors.append(f"Mid-range entry in {session} reduces edge for trend trades")
            
            # Phase 4.1 Structure validation (sanity checks)
            # These are not hard blocks, but warnings for consistency
            warnings = self._validate_phase4_1_structures(m5_data, strategy)
            # Add warnings as soft errors (could be warnings instead if we had that)
            # For now, we skip adding them as hard errors
            
            return errors
            
        except Exception as e:
            errors.append(f"Session/news validation error: {e}")
            return errors
    
    def _validate_phase4_1_structures(self, m5_data: Dict[str, Any], strategy: str) -> List[str]:
        """
        Validate Phase 4.1 structure features for consistency.
        IMPROVED Phase 4.2: Soft checks for structure alignment.
        
        Returns:
            List of warnings (not hard errors)
        """
        warnings = []
        
        try:
            # Check for conflicting structure signals
            bos_bull = m5_data.get("bos_bull", False)
            bos_bear = m5_data.get("bos_bear", False)
            choch_bull = m5_data.get("choch_bull", False)
            choch_bear = m5_data.get("choch_bear", False)
            
            # Conflicting structure signals
            if (bos_bull and bos_bear) or (choch_bull and choch_bear):
                warnings.append("Conflicting BOS/CHOCH signals detected")
            
            # Sweep without follow-through (edge case)
            sweep_bull = m5_data.get("sweep_bull", False)
            sweep_bear = m5_data.get("sweep_bear", False)
            wick_rejection_bull = m5_data.get("wick_rejection_bull", False)
            wick_rejection_bear = m5_data.get("wick_rejection_bear", False)
            
            # Sweep without rejection is less reliable
            if sweep_bull and not wick_rejection_bull:
                warnings.append("Bullish sweep without rejection (weaker signal)")
            if sweep_bear and not wick_rejection_bear:
                warnings.append("Bearish sweep without rejection (weaker signal)")
            
            return warnings
            
        except Exception as e:
            return [f"Structure validation warning: {e}"]
    
    def _validate_geometry(self, response: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """Validate order geometry and structure rules."""
        errors = []
        
        try:
            order_type = response.get("order_type", "")
            entry = response.get("entry", 0)
            sl = response.get("sl", 0)
            tp = response.get("tp", 0)
            
            if order_type == "skip":
                return errors  # Skip validation for skip orders
            
            # Get current price and ATR for validation
            m5_data = context.get("M5", {})
            current_price = m5_data.get("close", 0)
            atr_14 = m5_data.get("atr_14", 0)

            if current_price == 0 or atr_14 == 0:
                # IMPROVED: Add warning for missing M5 data dependencies
                missing_data = []
                if current_price == 0:
                    missing_data.append("current_price")
                if atr_14 == 0:
                    missing_data.append("ATR_14")
                errors.append(f"Insufficient price/ATR context for geometry validation - missing: {', '.join(missing_data)}")
                return errors  # Skip if no price data
            
            # Stop vs Limit semantics validation
            if order_type in ["buy_stop", "sell_stop"]:
                # Stops must be beyond current price
                if order_type == "buy_stop" and entry <= current_price:
                    errors.append("Buy stop must be above current price")
                elif order_type == "sell_stop" and entry >= current_price:
                    errors.append("Sell stop must be below current price")
                    
            elif order_type in ["buy_limit", "sell_limit"]:
                # Limits must be into pullbacks (opposite direction)
                if order_type == "buy_limit" and entry >= current_price:
                    errors.append("Buy limit must be below current price")
                elif order_type == "sell_limit" and entry <= current_price:
                    errors.append("Sell limit must be above current price")
            
            # SL floor validation - must be at least 0.4×ATR away
            sl_distance_atr = abs(entry - sl) / atr_14 if atr_14 > 0 else 0
            if sl_distance_atr < 0.4:
                errors.append(f"SL too close: {sl_distance_atr:.2f}×ATR (minimum 0.4×ATR)")
            
            # Optional: Swing level validation if available
            swing_validation_errors = self._validate_swing_levels(response, context)
            errors.extend(swing_validation_errors)
            
            return errors
            
        except Exception as e:
            errors.append(f"Geometry validation error: {e}")
            return errors
    
    def _validate_rr_vs_geometry(self, response: Dict[str, Any], context: Dict[str, Any], template_config: Optional[Dict[str, Any]] = None) -> List[str]:
        """Validate that RR is still valid after geometry fixes."""
        errors = []

        try:
            order_type = response.get("order_type", "")
            entry = response.get("entry", 0)
            sl = response.get("sl", 0)
            tp = response.get("tp", 0)
            rr = response.get("rr", 0)

            if order_type == "skip" or entry == 0 or sl == 0 or tp == 0:
                return errors  # Skip validation for skip orders or invalid values

            # Get current price and ATR for validation
            m5_data = context.get("M5", {})
            current_price = m5_data.get("close", 0)
            atr_14 = m5_data.get("atr_14", 0)

            if current_price == 0 or atr_14 == 0:
                # IMPROVED: Add warning for missing M5 data dependencies
                missing_data = []
                if current_price == 0:
                    missing_data.append("current_price")
                if atr_14 == 0:
                    missing_data.append("ATR_14")
                errors.append(f"Insufficient price/ATR context for RR validation - missing: {', '.join(missing_data)}")
                return errors  # Skip if no price data

            # Recalculate actual RR based on entry, SL, TP
            if order_type in ["buy_stop", "buy_limit"]:
                actual_risk = abs(entry - sl)
                actual_reward = abs(tp - entry)
            elif order_type in ["sell_stop", "sell_limit"]:
                actual_risk = abs(entry - sl)
                actual_reward = abs(tp - entry)
            else:
                return errors  # Unknown order type

            if actual_risk == 0:
                return errors  # Avoid division by zero

            actual_rr = actual_reward / actual_risk

            # Check against template config if available
            if template_config:
                min_rr = template_config.get("min_rr", 1.0)
                if actual_rr < min_rr:
                    errors.append(f"Actual RR {actual_rr:.2f} < template minimum {min_rr} after geometry validation")

            # Additional check: ensure RR is reasonable (> 0.5 even without template)
            if actual_rr < 0.5:
                errors.append(f"Actual RR {actual_rr:.2f} is too low (< 0.5)")

            return errors

        except Exception as e:
            errors.append(f"RR vs geometry validation error: {e}")
            return errors

    def _validate_swing_levels(self, response: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """Validate SL against swing levels if available."""
        errors = []
        
        try:
            order_type = response.get("order_type", "")
            entry = response.get("entry", 0)
            sl = response.get("sl", 0)
            
            if order_type == "skip":
                return errors
            
            # Get swing levels from context
            swing_highs = context.get("swing_highs", [])
            swing_lows = context.get("swing_lows", [])
            
            if not swing_highs and not swing_lows:
                return errors  # No swing data available
            
            # Check if SL is beyond nearest swing with buffer
            buffer_atr = 0.1  # 0.1×ATR buffer beyond swing
            m5_data = context.get("M5", {})
            atr_14 = m5_data.get("atr_14", 0)
            buffer_distance = buffer_atr * atr_14 if atr_14 > 0 else 0
            
            if order_type in ["buy_stop", "buy_limit"]:
                # For buy orders, SL should be below nearest swing low
                if swing_lows:
                    nearest_swing_low = max(swing_lows)
                    if sl > nearest_swing_low - buffer_distance:
                        errors.append(f"SL too close to swing low: {sl} vs {nearest_swing_low}")
                        
            elif order_type in ["sell_stop", "sell_limit"]:
                # For sell orders, SL should be above nearest swing high
                if swing_highs:
                    nearest_swing_high = min(swing_highs)
                    if sl < nearest_swing_high + buffer_distance:
                        errors.append(f"SL too close to swing high: {sl} vs {nearest_swing_high}")
            
            return errors
            
        except Exception as e:
            errors.append(f"Swing level validation error: {e}")
            return errors
    
    def _validate_trend_pullback(self, response: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """Validate trend pullback specific rules."""
        errors = []
        
        order_type = response.get("order_type", "")
        if order_type not in ["buy_stop", "sell_stop", "skip"]:
            errors.append("Trend pullback must use stop orders or skip")
        
        # FIXED: Context is the features dict directly, not wrapped
        cross_tf = context.get("cross_tf", {})
        trend_agreement = cross_tf.get("trend_agreement", 0.0)
        
        if trend_agreement < 0.6 and order_type != "skip":
            errors.append("Insufficient trend agreement for trend pullback")
        
        return errors
    
    def _validate_range_fade(self, response: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """Validate range fade specific rules."""
        errors = []
        
        order_type = response.get("order_type", "")
        if order_type not in ["buy_limit", "sell_limit", "skip"]:
            errors.append("Range fade must use limit orders or skip")
        
        # FIXED: Context is the features dict directly, not wrapped
        m5_data = context.get("M5", {})
        adx = m5_data.get("adx", 0.0)
        
        if adx > 20 and order_type != "skip":
            errors.append("ADX too high for range fade")
        
        return errors
    
    def _validate_breakout(self, response: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        """Validate breakout specific rules."""
        errors = []
        
        order_type = response.get("order_type", "")
        if order_type not in ["buy_stop", "sell_stop", "skip"]:
            errors.append("Breakout must use stop orders or skip")
        
        # FIXED: Context is the features dict directly, not wrapped
        m5_data = context.get("M5", {})
        adx = m5_data.get("adx", 0.0)
        
        if adx < 25 and order_type != "skip":
            errors.append("ADX too low for breakout")
        
        return errors
    
    def _validate_order_type_logic(self, order_type: str, entry: float, sl: float, tp: float) -> bool:
        """Validate order type logic."""
        if order_type in ["buy_stop", "buy_limit"]:
            return sl < entry < tp
        elif order_type in ["sell_stop", "sell_limit"]:
            return tp < entry < sl
        else:
            return True  # Skip is always valid
    
    def _can_repair(self, response: Dict[str, Any], strategy: str) -> bool:
        """Check if response can be auto-repaired."""
        try:
            # Check if basic structure exists
            required_fields = ["strategy", "order_type", "entry", "sl", "tp", "rr"]
            has_basic_structure = all(field in response for field in required_fields)
            
            # Check if values are numeric
            numeric_fields = ["entry", "sl", "tp", "rr"]
            has_numeric_values = all(
                isinstance(response.get(field), (int, float)) 
                for field in numeric_fields
            )
            
            return has_basic_structure and has_numeric_values
            
        except Exception:
            return False
    
    def _repair_response(self, response: Dict[str, Any], strategy: str, 
                        context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Auto-repair response if possible."""
        try:
            repaired = response.copy()
            
            # Repair missing fields
            if "confidence" not in repaired:
                repaired["confidence"] = {
                    "overall": 50,
                    "trend": 50,
                    "pattern": 50,
                    "volume": 50,
                    "regime_fit": 50
                }
            
            if "rationale" not in repaired:
                repaired["rationale"] = "Auto-repaired response"
            
            if "tags" not in repaired:
                repaired["tags"] = ["auto_repaired"]
            
            # Repair order type if invalid
            strategy = repaired.get("strategy", "")
            order_type = repaired.get("order_type", "")
            
            if strategy == "trend_pullback" and order_type not in ["buy_stop", "sell_stop", "skip"]:
                repaired["order_type"] = "skip"
            elif strategy == "range_fade" and order_type not in ["buy_limit", "sell_limit", "skip"]:
                repaired["order_type"] = "skip"
            elif strategy == "breakout" and order_type not in ["buy_stop", "sell_stop", "skip"]:
                repaired["order_type"] = "skip"
            
            # Repair RR if invalid
            rr = repaired.get("rr", 0)
            if rr < 1.0:
                repaired["rr"] = 1.5
            elif rr > 5.0:
                repaired["rr"] = 3.0
            
            # Repair confidence values
            confidence = repaired.get("confidence", {})
            for key in ["overall", "trend", "pattern", "volume", "regime_fit"]:
                if key not in confidence:
                    confidence[key] = 50
                elif not isinstance(confidence[key], (int, float)):
                    confidence[key] = 50
                elif confidence[key] < 0:
                    confidence[key] = 0
                elif confidence[key] > 100:
                    confidence[key] = 100
            
            repaired["confidence"] = confidence
            
            return repaired
            
        except Exception as e:
            logger.error(f"Auto-repair failed: {e}")
            return None
    
    def _calculate_validation_score(self, response: Dict[str, Any], errors: List[str],
                                 warnings: List[str]) -> float:
        """Calculate validation score (0-100) with enhanced incentives."""
        try:
            base_score = 100.0

            # Deduct for errors
            base_score -= len(errors) * 20.0

            # Deduct for warnings
            base_score -= len(warnings) * 5.0

            # IMPROVED: Enhanced validation score incentives with granular thresholds
            order_type = response.get("order_type", "")
            entry = response.get("entry", 0)
            sl = response.get("sl", 0)
            tp = response.get("tp", 0)
            rr = response.get("rr", 0)

            # Bonus for complete confidence scores (existing)
            confidence = response.get("confidence", {})
            if isinstance(confidence, dict):
                confidence_fields = ["overall", "trend", "pattern", "volume", "regime_fit"]
                complete_confidence = sum(1 for field in confidence_fields if field in confidence)
                base_score += complete_confidence * 2.0

            # Bonus for good RR (> 2.0)
            if rr > 2.0:
                base_score += 5.0

            # Enhanced SL distance incentives (good risk management)
            if entry > 0 and sl > 0:
                sl_distance = abs(entry - sl)
                sl_distance_pct = sl_distance / entry * 100

                if sl_distance_pct >= 0.4:  # Meets minimum ATR requirement
                    base_score += 2.0
                elif sl_distance_pct >= 0.3:  # Above basic requirement
                    base_score += 1.0
                elif sl_distance_pct < 0.2:  # Too tight (penalty)
                    base_score -= 2.0

            # Enhanced cost-aware incentives
            if entry > 0 and sl > 0:
                # Calculate cost efficiency (would need spread data for full calculation)
                # For now, use RR as a proxy for cost efficiency
                if 1.5 <= rr <= 3.0:  # Sweet spot for cost efficiency
                    base_score += 2.0

            # Penalty for very high RR (> 5.0) - might be unrealistic
            if rr > 5.0:
                base_score -= 5.0

            # Penalty for very low RR (< 1.2) - poor risk management
            if rr < 1.2 and rr > 0:
                base_score -= 3.0

            # IMPROVED: Additional validation score nudges for sharper ranking
            # Bonus for very good SL distance (>= 0.5×ATR)
            if entry > 0 and sl > 0:
                sl_distance = abs(entry - sl)
                if entry > 0:
                    sl_distance_pct = sl_distance / entry * 100
                    if sl_distance_pct >= 0.5:  # Excellent SL distance
                        base_score += 2.0

            # Bonus for low costs (would need spread/slippage data for full calculation)
            # For now, bonus for moderate RR that suggests reasonable costs
            if 1.8 <= rr <= 2.5:  # Optimal range for cost efficiency
                base_score += 1.0

            # NEW: Bonus when (spread+slip)/RR < 10% (excellent cost efficiency)
            # Note: This would need actual spread/slippage data for full calculation

            # NEW: Penalty when SL distance is between 0.4× and 0.5× ATR (legal but fragile)
            if entry > 0 and sl > 0:
                sl_distance = abs(entry - sl)
                if entry > 0:
                    sl_distance_pct = sl_distance / entry * 100
                    if 0.4 <= sl_distance_pct < 0.5:  # Legal but fragile SL distance
                        base_score -= 2.0

            return max(0.0, min(100.0, base_score))
            
        except Exception:
            return 0.0
    
    def _load_validation_schemas(self) -> Dict[str, Any]:
        """Load validation schemas for different strategies."""
        return {
            "trend_pullback": {
                "required_fields": ["strategy", "order_type", "entry", "sl", "tp", "rr", "confidence", "rationale", "tags"],
                "order_types": ["buy_stop", "sell_stop", "skip"],
                "min_rr": 1.8,
                "max_rr": 3.0
            },
            "range_fade": {
                "required_fields": ["strategy", "order_type", "entry", "sl", "tp", "rr", "confidence", "rationale", "tags"],
                "order_types": ["buy_limit", "sell_limit", "skip"],
                "min_rr": 1.5,
                "max_rr": 2.5
            },
            "breakout": {
                "required_fields": ["strategy", "order_type", "entry", "sl", "tp", "rr", "confidence", "rationale", "tags"],
                "order_types": ["buy_stop", "sell_stop", "skip"],
                "min_rr": 2.0,
                "max_rr": 4.0
            }
        }
    
    def _load_repair_rules(self) -> Dict[str, Any]:
        """Load auto-repair rules."""
        return {
            "default_confidence": {
                "overall": 50,
                "trend": 50,
                "pattern": 50,
                "volume": 50,
                "regime_fit": 50
            },
            "default_rr": 1.5,
            "max_rr": 5.0,
            "min_rr": 1.0
        }


def create_prompt_validator() -> PromptValidator:
    """Factory function to create prompt validator instance."""
    return PromptValidator()
