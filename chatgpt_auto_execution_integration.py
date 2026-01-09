"""
ChatGPT Auto Execution Integration
Allows ChatGPT to create trade plans that are monitored and executed automatically.
"""

import json
import uuid
import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple, List
from auto_execution_system import get_auto_execution_system, TradePlan
from infra.tolerance_helper import get_price_tolerance
from infra.mt5_service import MT5Service

logger = logging.getLogger(__name__)

class ChatGPTAutoExecution:
    """Integration between ChatGPT and auto execution system"""
    
    def __init__(self):
        try:
            self.auto_system = get_auto_execution_system()
            logger.info("ChatGPTAutoExecution initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ChatGPTAutoExecution: {e}", exc_info=True)
            raise
    
    def create_trade_plan(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        volume: float = 0.01,
        conditions: Dict[str, Any] = None,
        expires_hours: int = 24,
        notes: str = None,
        plan_id: Optional[str] = None,
        entry_levels: Optional[List[Dict[str, Any]]] = None  # Phase 2: Multi-level entry support
    ) -> Dict[str, Any]:
        """Create a trade plan for auto execution"""
        
        try:
            # Ensure auto_system is available
            if not hasattr(self, 'auto_system') or self.auto_system is None:
                logger.warning("Auto-execution system not initialized, attempting to reinitialize...")
                self.auto_system = get_auto_execution_system()
        except Exception as e:
            logger.error(f"Failed to get auto-execution system: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Auto-execution system not available: {str(e)}",
                "plan_id": None
            }
        
        # Normalize symbol - ensure it has 'c' suffix for broker symbols
        symbol_upper = symbol.upper()
        symbol_base = symbol_upper.rstrip('C').rstrip('c')
        symbol_normalized = symbol_base + 'c'
        
        # Generate unique plan ID if not provided
        if not plan_id:
            plan_id = f"chatgpt_{uuid.uuid4().hex[:8]}"
        
        # Set expiration time (use UTC for consistency)
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).isoformat()
        
        # Store original volume to check if auto-calculation should be used
        # This MUST be done BEFORE volume is defaulted to 0.01
        original_volume = volume
        
        # Validate original_volume is not negative (edge case)
        if original_volume is not None and original_volume < 0:
            logger.warning(f"Negative volume provided: {original_volume}, treating as None for auto-calculation")
            original_volume = None
        
        # Ensure volume defaults to 0.01 if not specified or is 0
        if volume is None or volume == 0:
            volume = 0.01
            logger.info(f"Volume not specified or is 0, defaulting to 0.01 for plan {symbol_normalized}")
        
        # Validate and fix conditions
        if conditions:
            conditions, validation_errors = self._validate_and_fix_conditions(conditions, symbol_normalized, entry_price, notes)
            
            if validation_errors:
                error_msg = "Invalid conditions detected:\n" + "\n".join(f"  - {err}" for err in validation_errors)
                logger.error(f"Plan creation failed for {symbol_normalized}: {error_msg}")
                return {
                    "success": False,
                    "message": error_msg,
                    "plan_id": None
                }
        
        # If no conditions provided, add default price_near condition
        # This ensures plans can actually execute automatically
        if not conditions or len(conditions) == 0:
            # Auto-calculate tolerance based on symbol type
            tolerance = get_price_tolerance(symbol_normalized)
            
            conditions = {
                "price_near": entry_price,
                "tolerance": tolerance
            }
        
        # If conditions have price_near but no tolerance, add it
        if conditions and "price_near" in conditions and "tolerance" not in conditions:
            conditions["tolerance"] = get_price_tolerance(symbol_normalized)
        
        # ========== VOLATILITY STATE VALIDATION (Phase 3) ==========
        try:
            from infra.volatility_regime_detector import RegimeDetector, VolatilityRegime
            from handlers.auto_execution_validator import AutoExecutionValidator
            
            regime_detector = RegimeDetector()
            current_regime = regime_detector.get_current_regime(symbol_normalized)
            
            if current_regime:
                # Get strategy_type from conditions or extract from notes
                strategy_type = conditions.get("strategy_type") if conditions else None
                if not strategy_type and notes:
                    # Try to extract strategy_type from notes (e.g., "[strategy:breakout_ib_volatility_trap]")
                    match = re.search(r'\[strategy:(\w+)\]', notes)
                    if match:
                        strategy_type = match.group(1)
                
                # Validate against volatility state
                validator = AutoExecutionValidator()
                is_valid, rejection_reason = validator.validate_volatility_state(
                    plan={
                        "conditions": conditions,
                        "notes": notes
                    },
                    volatility_regime=current_regime,
                    strategy_type=strategy_type
                )
                
                if not is_valid:
                    logger.warning(f"Plan rejected due to volatility state: {rejection_reason}")
                    return {
                        "success": False,
                        "message": f"Plan rejected: {rejection_reason}",
                        "volatility_state": current_regime.value,
                        "plan_id": None
                    }
        except Exception as e:
            logger.warning(f"Volatility state validation failed (non-critical): {e}")
            # Don't fail plan creation if validation fails - allow plan to proceed
            # This ensures system continues to work even if volatility detection is unavailable
        
        # If conditions include structure conditions (choch_bull, choch_bear, rejection_wick)
        # but no timeframe is specified, try to extract it from notes
        if conditions and (conditions.get("choch_bull") or conditions.get("choch_bear") or conditions.get("rejection_wick")):
            # Check if timeframe is already specified
            if not (conditions.get("timeframe") or conditions.get("structure_tf") or conditions.get("tf")):
                # Try to extract timeframe from notes
                timeframe = None
                if notes:
                    # Look for common timeframe patterns: M1, M5, M15, M30, H1, H4, D1
                    # Case insensitive, can be standalone or part of words like "M15 BOS"
                    tf_pattern = r'\b(M1|M5|M15|M30|H1|H4|D1)\b'
                    matches = re.findall(tf_pattern, notes.upper())
                    if matches:
                        timeframe = matches[-1]  # Use last match (most recent mention)
                        logger.info(f"Extracted timeframe '{timeframe}' from notes for plan {plan_id}")
                
                if timeframe:
                    conditions["timeframe"] = timeframe
                else:
                    # Default to M5 if no timeframe found
                    conditions["timeframe"] = "M5"
                    logger.warning(f"No timeframe specified for structure condition in plan {plan_id}, defaulting to M5")
        
        # Phase 2: Validate and process entry_levels if provided
        processed_entry_levels = None
        if entry_levels:
            processed_entry_levels = self._validate_and_process_entry_levels(
                entry_levels, direction, entry_price, stop_loss, take_profit, symbol_normalized
            )
            if processed_entry_levels is None:
                return {
                    "success": False,
                    "message": "Invalid entry_levels: validation failed. Check that all levels have 'price' field and prices are reasonable.",
                    "plan_id": None
                }
        
        # ========== DYNAMIC LOT SIZING (Based on Confidence) ==========
        # Check original_volume to determine if auto-calculation should be used
        # This preserves the distinction between "not provided" and "explicitly set to 0.01"
        # IMPORTANT: Use FINAL conditions after all validation/fixing steps
        if original_volume is None or original_volume == 0 or original_volume == 0.01:
            try:
                from infra.lot_size_calculator import LotSizeCalculator
                
                calculator = LotSizeCalculator()
                # Use FINAL conditions (after all validation/fixing)
                # Handle None conditions gracefully
                conditions_for_calc = conditions if conditions is not None else {}
                calculated_lot_size, confidence = calculator.calculate_plan_lot_size(
                    symbol=symbol_normalized,
                    conditions=conditions_for_calc,  # Final conditions after all validation
                    base_lot_size=0.01
                )
                
                # Validate calculated values
                if calculated_lot_size <= 0:
                    raise ValueError(f"Invalid calculated lot size: {calculated_lot_size}")
                if confidence < 0 or confidence > 1:
                    raise ValueError(f"Invalid confidence score: {confidence}")
                
                # Use calculated lot size
                volume = calculated_lot_size
                
                # Add confidence info to notes if not already present
                # Check if confidence info already exists to avoid duplication
                confidence_marker = "[Confidence:"
                if notes and confidence_marker in notes:
                    # Replace existing confidence info
                    import re
                    notes = re.sub(r'\s*\[Confidence:[^\]]+\]', '', notes).strip()
                
                if notes:
                    notes += f" [Confidence: {confidence:.0%}, Auto Lot: {volume}]"
                else:
                    notes = f"Confidence: {confidence:.0%}, Auto Lot: {volume}"
                
                logger.info(
                    f"Auto-calculated lot size for plan {plan_id}: {volume} "
                    f"(confidence: {confidence:.2f}, conditions: {len(conditions_for_calc)} conditions)"
                )
            except ImportError as e:
                logger.warning(f"Dynamic lot sizing module not available (non-critical): {e}, using default volume")
                # Fall back to default volume if module not available
                if volume is None or volume == 0:
                    volume = 0.01
            except (ValueError, TypeError) as e:
                logger.warning(f"Dynamic lot sizing calculation error (non-critical): {e}, using default volume")
                # Fall back to default volume if calculation fails
                if volume is None or volume == 0:
                    volume = 0.01
            except Exception as e:
                logger.warning(f"Dynamic lot sizing failed (non-critical): {e}, using default volume", exc_info=True)
                # Fall back to default volume if calculation fails
                if volume is None or volume == 0:
                    volume = 0.01
        else:
            # Volume was explicitly provided (> 0.01), use it (user override)
            logger.info(f"Using explicit volume {volume} for plan {plan_id} (user override)")
        
        # Create trade plan
        plan = TradePlan(
            plan_id=plan_id,
            symbol=symbol_normalized,  # Use normalized symbol with 'c' suffix
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            volume=volume,
            conditions=conditions,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="chatgpt",
            status="pending",
            expires_at=expires_at,
            notes=notes,
            entry_levels=processed_entry_levels  # Phase 2: Multi-level entry support
        )
        
        # Add to auto execution system
        success = self.auto_system.add_plan(plan)
        
        if success:
            return {
                "success": True,
                "plan_id": plan_id,
                "message": f"Trade plan created successfully. System will monitor conditions and execute automatically.",
                "plan_details": {
                    "symbol": symbol_normalized,  # Return normalized symbol
                    "direction": direction,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "volume": volume,
                    "conditions": conditions,
                    "expires_at": expires_at,
                    "notes": notes
                }
            }
        else:
            return {
                "success": False,
                "message": "Failed to create trade plan"
            }
    
    def _validate_and_fix_conditions(
        self,
        conditions: Dict[str, Any],
        symbol: str,
        entry_price: float,
        notes: Optional[str] = None
    ) -> Tuple[Dict[str, Any], List[str]]:
        """
        Validate and fix condition format.
        Returns: (fixed_conditions, list_of_errors)
        """
        errors = []
        fixed_conditions = conditions.copy()
        
        # Check for old trigger_type/trigger_value format
        if "trigger_type" in fixed_conditions or "trigger_value" in fixed_conditions:
            errors.append(
                "Invalid condition format: 'trigger_type'/'trigger_value' detected. "
                "Use direct conditions instead:\n"
                "  - For CHOCH: Use 'choch_bull': true or 'choch_bear': true\n"
                "  - For Rejection Wick: Use 'rejection_wick': true\n"
                "  - For Order Block: Use 'order_block': true\n"
                "Example: {'choch_bull': true, 'timeframe': 'M5', 'price_near': entry_price}"
            )
            return fixed_conditions, errors
        
        # Check for invalid condition names
        # Note: range_scalp_confluence, structure_confirmation, and plan_type are valid for range scalping plans
        # They are added automatically by create_range_scalp_plan and should be allowed
        # Note: bos_bull, bos_bear, choch_bull, choch_bear are all valid separate conditions
        # - CHOCH (Change of Character) = reversal (breaks second-to-last swing)
        # - BOS (Break of Structure) = continuation (breaks last swing)
        invalid_conditions = {
            "price_retests_ob_level": (None, "Invalid condition 'price_retests_ob_level'. Use 'order_block': true with 'price_near' instead"),
            "vwap_support_resistance": (None, "Invalid condition 'vwap_support_resistance'. Use 'vwap_deviation': true instead"),
            "momentum_continuation": (None, "Invalid condition 'momentum_continuation'. Use 'ema_slope': true with 'ema_slope_direction' instead"),
            "confluence": (None, "Invalid condition 'confluence'. For range scalping, use 'moneybot.create_range_scalp_plan' instead"),
            # Allow range_scalp_confluence, structure_confirmation, and plan_type - they are valid for range scalping plans
            # "range_scalp_confluence": (None, "Invalid condition 'range_scalp_confluence'. Use 'moneybot.create_range_scalp_plan' instead"),
            # "structure_confirmation": (None, "Invalid condition 'structure_confirmation'. Use 'choch_bull': true or 'choch_bear': true instead"),
            # "plan_type": (None, "Invalid condition 'plan_type'. This is not a valid condition"),
        }
        
        for invalid_key, (correct_key, error_msg) in invalid_conditions.items():
            if invalid_key in fixed_conditions:
                if correct_key:
                    # Auto-fix: replace with correct condition
                    fixed_conditions[correct_key] = fixed_conditions.pop(invalid_key)
                    logger.info(f"Auto-fixed condition: {invalid_key} -> {correct_key}")
                else:
                    # Remove invalid condition
                    fixed_conditions.pop(invalid_key)
                    errors.append(error_msg)
        
        # Check for ema_slope_direction without ema_slope
        if "ema_slope_direction" in fixed_conditions and "ema_slope" not in fixed_conditions:
            fixed_conditions["ema_slope"] = True
            logger.info("Auto-fixed: Added 'ema_slope': true (required when using 'ema_slope_direction')")
        
        # Check for invalid volatility_state values
        if "volatility_state" in fixed_conditions:
            vol_state = fixed_conditions["volatility_state"]
            if isinstance(vol_state, str):
                vol_upper = vol_state.upper()
                valid_states = ["EXPANDING", "CONTRACTING", "STABLE"]
                if vol_upper not in valid_states:
                    # Try to map common invalid values
                    if "EXPAND" in vol_upper or "STRONG" in vol_upper or "TREND" in vol_upper:
                        fixed_conditions["volatility_state"] = "EXPANDING"
                        logger.info(f"Auto-fixed volatility_state: '{vol_state}' -> 'EXPANDING'")
                    elif "CONTRACT" in vol_upper:
                        fixed_conditions["volatility_state"] = "CONTRACTING"
                        logger.info(f"Auto-fixed volatility_state: '{vol_state}' -> 'CONTRACTING'")
                    else:
                        errors.append(
                            f"Invalid volatility_state value: '{vol_state}'. "
                            f"Must be one of: {', '.join(valid_states)}"
                        )
        
        # Check for order_block without order_block_type
        if fixed_conditions.get("order_block") and "order_block_type" not in fixed_conditions:
            fixed_conditions["order_block_type"] = "auto"
            logger.info("Auto-fixed: Added 'order_block_type': 'auto' (required when using 'order_block')")
        
        # Check for structure conditions without timeframe
        structure_conditions = ["choch_bull", "choch_bear", "rejection_wick"]
        has_structure = any(fixed_conditions.get(c) for c in structure_conditions)
        if has_structure and "timeframe" not in fixed_conditions and "structure_tf" not in fixed_conditions:
            # Try to extract from notes
            timeframe = None
            if notes:
                tf_pattern = r'\b(M1|M5|M15|M30|H1|H4|D1)\b'
                matches = re.findall(tf_pattern, notes.upper())
                if matches:
                    timeframe = matches[-1]
            
            if timeframe:
                fixed_conditions["timeframe"] = timeframe
                logger.info(f"Auto-fixed: Added 'timeframe': '{timeframe}' (extracted from notes)")
            else:
                errors.append(
                    "Structure conditions (choch_bull, choch_bear, rejection_wick) require 'timeframe' or 'structure_tf'. "
                    "Add 'timeframe': 'M5' (or M1, M15, M30, H1, H4, D1)"
                )
        
        # ========== NEW: Strategy-specific validation and auto-fix ==========
        strategy_type = fixed_conditions.get("strategy_type")
        
        if strategy_type == "breaker_block":
            # Auto-fix: Add breaker_block condition if missing
            if "breaker_block" not in fixed_conditions or not fixed_conditions.get("breaker_block"):
                fixed_conditions["breaker_block"] = True
                logger.info("Auto-fixed: Added 'breaker_block': true (required for breaker_block strategy)")
            
            # Remove incorrect detection flags if present (these are checked dynamically, not stored in conditions)
            if "ob_broken" in fixed_conditions:
                fixed_conditions.pop("ob_broken")
                logger.info("Removed 'ob_broken' from conditions (checked dynamically by detection system)")
            if "price_retesting_breaker" in fixed_conditions:
                fixed_conditions.pop("price_retesting_breaker")
                logger.info("Removed 'price_retesting_breaker' from conditions (checked dynamically by detection system)")
        
        elif strategy_type == "order_block_rejection":
            # Verify order_block exists (order_block_type auto-fix already handled above)
            if "order_block" not in fixed_conditions or not fixed_conditions.get("order_block"):
                errors.append(
                    "Missing required condition: order_block: true (required for order_block_rejection strategy). "
                    "Add 'order_block': true to conditions."
                )
        
        elif strategy_type == "liquidity_sweep_reversal":
            if "liquidity_sweep" not in fixed_conditions or not fixed_conditions.get("liquidity_sweep"):
                errors.append(
                    "Missing required condition: liquidity_sweep: true (required for liquidity_sweep_reversal strategy). "
                    "Add 'liquidity_sweep': true to conditions."
                )
            if "price_below" not in fixed_conditions and "price_above" not in fixed_conditions:
                errors.append(
                    "Missing required condition: price_below or price_above (required for liquidity sweep detection). "
                    "Add 'price_below': [level] or 'price_above': [level] to conditions."
                )
            if "timeframe" not in fixed_conditions and "structure_tf" not in fixed_conditions:
                # Try to extract from notes first (already handled above for structure conditions)
                # If still missing after extraction attempt, add error
                if "timeframe" not in fixed_conditions and "structure_tf" not in fixed_conditions:
                    errors.append(
                        "Missing required condition: timeframe or structure_tf (required for liquidity sweep detection). "
                        "Add 'timeframe': 'M5' (or M1, M15, etc.) to conditions."
                    )
        
        # Check for structure conditions that require timeframe (including liquidity_sweep)
        structure_conditions_all = ["choch_bull", "choch_bear", "rejection_wick", "liquidity_sweep"]
        has_structure_all = any(fixed_conditions.get(c) for c in structure_conditions_all)
        if has_structure_all:
            # Check for timeframe or structure_tf (system accepts both)
            has_timeframe = "timeframe" in fixed_conditions or "structure_tf" in fixed_conditions
            if not has_timeframe:
                # Try to extract from notes (already attempted above)
                # If still missing after extraction, add error
                if "timeframe" not in fixed_conditions and "structure_tf" not in fixed_conditions:
                    errors.append(
                        "Structure conditions (choch_bull, choch_bear, rejection_wick, liquidity_sweep) require 'timeframe' or 'structure_tf'. "
                        "Add 'timeframe': 'M5' (or M1, M15, M30, H1, H4, D1)"
                    )
        
        # Remove incorrect detection flags from conditions (these should NOT be stored)
        # These flags come from detection system results, not condition inputs
        detection_flags_to_remove = ["ob_broken", "price_retesting_breaker"]
        for flag in detection_flags_to_remove:
            if flag in fixed_conditions:
                fixed_conditions.pop(flag)
                logger.info(f"Removed '{flag}' from conditions (this is a detection result, not a condition input)")
        
        # WARNING (not error): Recommend price_near for better execution control
        # But don't block if price_above/price_below exist
        has_price_condition = any([
            "price_near" in fixed_conditions,
            "price_above" in fixed_conditions,
            "price_below" in fixed_conditions
        ])
        
        if not has_price_condition:
            # This is a warning, not an error - some plans might not need price conditions
            # But log it for visibility
            logger.warning(
                f"Plan missing price conditions (price_near, price_above, or price_below). "
                f"Execution may be imprecise. Consider adding price_near: {entry_price} with tolerance."
            )
        
        # Special handling for micro_scalp and range_scalp (they have different requirements)
        plan_type = fixed_conditions.get("plan_type")
        if plan_type == "micro_scalp":
            # Micro-scalp uses 4-layer validation system - conditions are optional
            # Don't validate standard conditions for micro-scalp
            pass
        elif plan_type == "range_scalp":
            # Range scalp plans should have range_scalp_confluence
            # But this is usually auto-added by create_range_scalp_plan
            if "range_scalp_confluence" not in fixed_conditions:
                logger.warning(
                    "Range scalp plan missing range_scalp_confluence. "
                    "This should be auto-added by create_range_scalp_plan."
                )
        
        # Check for indicators (old format)
        if "indicators" in fixed_conditions:
            errors.append(
                "Invalid condition format: 'indicators' object detected. "
                "Use direct conditions instead:\n"
                "  - For RSI: Not yet supported as a condition\n"
                "  - For Volume: Not yet supported as a condition\n"
                "Remove 'indicators' and use structure/price conditions instead"
            )
        
        return fixed_conditions, errors
    
    def create_choch_plan(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        volume: float = 0.01,
        choch_type: str = "bear",  # "bear" or "bull"
        price_tolerance: Optional[float] = None,
        expires_hours: int = 24,
        notes: str = None,
        additional_conditions: Optional[Dict[str, Any]] = None,  # Additional conditions to merge
        entry_levels: Optional[List[Dict[str, Any]]] = None  # Phase 2: Multi-level entry support
    ) -> Dict[str, Any]:
        """Create a CHOCH-based trade plan"""
        
        # Auto-calculate tolerance if not provided
        if price_tolerance is None:
            price_tolerance = get_price_tolerance(symbol)
        
        # Start with base conditions
        conditions = {
            "price_near": entry_price,
            "tolerance": price_tolerance
        }
        
        # Add choch condition if not already in additional_conditions
        if additional_conditions:
            # Check if choch_bull or choch_bear is already specified
            if "choch_bull" in additional_conditions or "choch_bear" in additional_conditions:
                # Use the choch condition from additional_conditions
                if "choch_bull" in additional_conditions:
                    conditions["choch_bull"] = additional_conditions["choch_bull"]
                if "choch_bear" in additional_conditions:
                    conditions["choch_bear"] = additional_conditions["choch_bear"]
            else:
                # Add choch condition based on choch_type
                conditions[f"choch_{choch_type}"] = True
            
            # Merge all additional conditions (will overwrite price_near/tolerance if specified, which is fine)
            conditions.update(additional_conditions)
            logger.info(f"Merged {len(additional_conditions)} additional conditions into CHOCH plan")
        else:
            # No additional conditions, just add choch condition
            conditions[f"choch_{choch_type}"] = True
        
        return self.create_trade_plan(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            volume=volume,
            conditions=conditions,
            expires_hours=expires_hours,
            notes=notes or f"CHOCH {choch_type.upper()} detection plan",
            entry_levels=entry_levels  # Phase 2: Multi-level entry support
        )
    
    def create_rejection_wick_plan(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        volume: float = 0.01,
        price_tolerance: Optional[float] = None,
        expires_hours: int = 24,
        notes: str = None,
        entry_levels: Optional[List[Dict[str, Any]]] = None,  # Phase 2: Multi-level entry support
        additional_conditions: Optional[Dict[str, Any]] = None  # Additional conditions to merge
    ) -> Dict[str, Any]:
        """Create a rejection wick-based trade plan"""
        
        # Auto-calculate tolerance if not provided
        if price_tolerance is None:
            price_tolerance = get_price_tolerance(symbol)
        
        # Start with base conditions
        conditions = {
            "rejection_wick": True,
            "price_near": entry_price,
            "tolerance": price_tolerance
        }
        
        # Merge additional conditions if provided (preserves timeframe, liquidity_sweep, choch_bear, etc.)
        if additional_conditions:
            # Merge all additional conditions (will overwrite price_near/tolerance if specified, which is fine)
            conditions.update(additional_conditions)
            logger.info(f"Merged {len(additional_conditions)} additional conditions into rejection wick plan")
        
        return self.create_trade_plan(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            volume=volume,
            conditions=conditions,
            expires_hours=expires_hours,
            notes=notes or "Rejection wick detection plan",
            entry_levels=entry_levels  # Phase 2: Multi-level entry support
        )
    
    def create_bracket_trade_plan(
        self,
        symbol: str,
        buy_entry: float,
        buy_sl: float,
        buy_tp: float,
        sell_entry: float,
        sell_sl: float,
        sell_tp: float,
        volume: float = 0.01,
        conditions: Dict[str, Any] = None,
        expires_hours: int = 24,
        notes: str = None
    ) -> Dict[str, Any]:
        """
        Create a bracket trade auto-execution plan (OCO - One Cancels Other).
        
        Creates two separate trade plans (BUY and SELL) that monitor conditions.
        When one plan executes, the other is automatically cancelled.
        Ideal for range breakouts, consolidation patterns, and news events.
        
        Args:
            symbol: Trading symbol
            buy_entry: Entry price for BUY order
            buy_sl: Stop loss for BUY order
            buy_tp: Take profit for BUY order
            sell_entry: Entry price for SELL order
            sell_sl: Stop loss for SELL order
            sell_tp: Take profit for SELL order
            volume: Position size for both orders (default: 0.01)
            conditions: Market conditions to monitor (applied to both plans)
            expires_hours: Plan expiry in hours (default: 24)
            notes: Plan description
            
        Returns:
            Dict with both plan IDs and bracket trade info
        """
        # Ensure volume defaults to 0.01 if not specified or is 0
        if volume is None or volume == 0:
            volume = 0.01
            logger.info(f"Volume not specified or is 0 for bracket trade, defaulting to 0.01")
        
        # Generate bracket trade ID
        bracket_id = f"bracket_{uuid.uuid4().hex[:8]}"
        
        # Normalize symbol - ensure it has 'c' suffix for broker symbols
        symbol_upper = symbol.upper()
        symbol_base = symbol_upper.rstrip('C').rstrip('c')
        symbol_normalized = symbol_base + 'c'
        
        # Default conditions if not provided
        if not conditions:
            # Default: price breakout conditions
            buy_tolerance = get_price_tolerance(symbol_normalized)
            sell_tolerance = get_price_tolerance(symbol_normalized)
            
            conditions = {
                "price_above": buy_entry,  # For BUY plan
                "price_below": sell_entry,  # For SELL plan
                "price_near": (buy_entry + sell_entry) / 2,  # Midpoint for monitoring
                "tolerance": max(buy_tolerance, sell_tolerance)
            }
        
        # Create BUY plan
        buy_conditions = conditions.copy()
        buy_conditions["price_above"] = buy_entry
        # Remove price_below from BUY plan (contradictory condition)
        buy_conditions.pop("price_below", None)
        # Set price_near to BUY entry (not midpoint) for proper execution control
        buy_conditions["price_near"] = buy_entry
        buy_conditions["bracket_trade_id"] = bracket_id
        buy_conditions["bracket_side"] = "buy"
        
        buy_plan = self.create_trade_plan(
            symbol=symbol_normalized,  # Use normalized symbol
            direction="BUY",
            entry_price=buy_entry,
            stop_loss=buy_sl,
            take_profit=buy_tp,
            volume=volume,
            conditions=buy_conditions,
            expires_hours=expires_hours,
            notes=(notes or "Bracket trade BUY") + f" (Bracket: {bracket_id})"
        )
        
        # Create SELL plan
        sell_conditions = conditions.copy()
        sell_conditions["price_below"] = sell_entry
        # Remove price_above from SELL plan (contradictory condition)
        sell_conditions.pop("price_above", None)
        # Set price_near to SELL entry (not midpoint) for proper execution control
        sell_conditions["price_near"] = sell_entry
        sell_conditions["bracket_trade_id"] = bracket_id
        sell_conditions["bracket_side"] = "sell"
        
        sell_plan = self.create_trade_plan(
            symbol=symbol_normalized,  # Use normalized symbol
            direction="SELL",
            entry_price=sell_entry,
            stop_loss=sell_sl,
            take_profit=sell_tp,
            volume=volume,
            conditions=sell_conditions,
            expires_hours=expires_hours,
            notes=(notes or "Bracket trade SELL") + f" (Bracket: {bracket_id})"
        )
        
        return {
            "success": True,
            "bracket_trade_id": bracket_id,
            "buy_plan_id": buy_plan.get("plan_id"),
            "sell_plan_id": sell_plan.get("plan_id"),
            "message": f"Bracket trade plan created: {bracket_id}. When one side executes, the other will be cancelled automatically.",
            "buy_plan": buy_plan,
            "sell_plan": sell_plan
        }
    
    def create_order_block_plan(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        volume: float = 0.01,
        order_block_type: str = "auto",  # "bull", "bear", or "auto"
        min_validation_score: int = 60,  # Minimum validation score (0-100)
        price_tolerance: Optional[float] = None,
        expires_hours: int = 24,
        notes: str = None,
        entry_levels: Optional[List[Dict[str, Any]]] = None  # Phase 2: Multi-level entry support
    ) -> Dict[str, Any]:
        """
        Create an order block-based trade plan.
        
        Monitors for institutional order blocks (OB) with comprehensive 10-parameter validation:
        - Anchor candle identification
        - Displacement/structure shift (mandatory)
        - FVG presence
        - Volume spike confirmation
        - Liquidity grab detection
        - Session context validation
        - Higher timeframe alignment
        - Structural context
        - Order block freshness
        - VWAP + liquidity confluence
        
        Args:
            symbol: Trading symbol
            direction: "BUY" or "SELL"
            entry_price: Entry price (typically near expected OB zone)
            stop_loss: Stop loss price
            take_profit: Take profit price
            volume: Position size (default: 0.01)
            order_block_type: "bull", "bear", or "auto" (auto-detect direction)
            min_validation_score: Minimum validation score required (default: 60/100)
            price_tolerance: Price tolerance for entry (auto-calculated if None)
            expires_hours: Plan expiry in hours (default: 24)
            notes: Optional plan description
        """
        
        # Auto-calculate tolerance if not provided
        if price_tolerance is None:
            price_tolerance = get_price_tolerance(symbol)
        
        conditions = {
            "order_block": True,
            "order_block_type": order_block_type.lower(),  # "bull", "bear", or "auto"
            "min_validation_score": min_validation_score,
            "price_near": entry_price,
            "tolerance": price_tolerance,
            "timeframe": "M1"  # Order blocks are primarily M1 with M5 validation
        }
        
        return self.create_trade_plan(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            volume=volume,
            conditions=conditions,
            expires_hours=expires_hours,
            notes=notes or f"Order block {order_block_type.upper()} detection plan (M1-M5 validated, min score: {min_validation_score})",
            entry_levels=entry_levels  # Phase 2: Multi-level entry support
        )
    
    def create_price_breakout_plan(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        volume: float = 0.01,
        breakout_type: str = "above",  # "above" or "below"
        expires_hours: int = 24,
        notes: str = None
    ) -> Dict[str, Any]:
        """Create a price breakout-based trade plan"""
        
        if breakout_type == "above":
            conditions = {
                "price_above": entry_price
            }
        else:
            conditions = {
                "price_below": entry_price
            }
        
        return self.create_trade_plan(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            volume=volume,
            conditions=conditions,
            expires_hours=expires_hours,
            notes=notes or f"Price {breakout_type} breakout plan"
        )
    
    def create_micro_scalp_plan(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        volume: float = 0.01,
        expires_hours: int = 2,  # Shorter expiry for micro-scalps (2 hours default)
        notes: str = None,
        conditions: Optional[Dict[str, Any]] = None,  # Optional conditions from ChatGPT
        entry_levels: Optional[List[Dict[str, Any]]] = None  # Phase 2: Multi-level entry support
    ) -> Dict[str, Any]:
        """
        Create a micro-scalp auto-execution plan.
        
        Micro-scalps are ultra-short-term trades targeting small, quick moves:
        - XAUUSD: $1-2 moves with SL $0.50-$1.20, TP $1-$2.50
        - BTCUSD: $5-20 moves with SL $5-$10, TP $10-$25
        
        The plan uses a 4-layer validation system:
        1. Pre-Trade Filters (volatility, spread)
        2. Location Filter (must be at "EDGE")
        3. Candle Signal Checklist (primary + secondary)
        4. Confluence Score (≥5 to trade, ≥7 for A+ setup)
        
        Args:
            symbol: Trading symbol (must be BTCUSDc or XAUUSDc)
            direction: "BUY" or "SELL"
            entry_price: Expected entry price
            stop_loss: Stop loss (should be ultra-tight per symbol rules)
            take_profit: Take profit (should be ultra-tight per symbol rules)
            volume: Trade volume (default: 0.01)
            expires_hours: Plan expiration in hours (default: 2 for micro-scalps)
            notes: Optional notes/reasoning
        
        Returns:
            Dict with plan_id and status
        """
        # Generate unique plan ID
        plan_id = f"micro_scalp_{uuid.uuid4().hex[:8]}"
        
        # Set expiration time (use UTC for consistency)
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).isoformat()
        
        # Ensure volume defaults to 0.01 if not specified or is 0
        if not volume or volume <= 0:
            volume = 0.01
        
        # Normalize symbol - preserve lowercase 'c' suffix
        symbol_upper = symbol.upper()
        # Remove any trailing 'C' or 'c' and add lowercase 'c'
        symbol_base = symbol_upper.rstrip('C').rstrip('c')
        symbol_norm = symbol_base + 'c'
        
        # Validate symbol is supported
        supported_symbols = ['BTCUSDc', 'XAUUSDc']
        if symbol_norm not in supported_symbols:
            return {
                "success": False,
                "plan_id": None,
                "message": f"Symbol {symbol_norm} not supported for micro-scalps. Supported: {supported_symbols}",
                "error": "UNSUPPORTED_SYMBOL"
            }
        
        # Validate SL/TP distances - check broker minimum first, then apply micro-scalp limits
        sl_distance = abs(entry_price - stop_loss)
        tp_distance = abs(take_profit - entry_price)
        
        # Get broker minimum stop distance (broker requirement)
        broker_min_distance = None
        try:
            mt5_service = MT5Service()
            symbol_meta = mt5_service.symbol_meta(symbol_norm)
            stops_level_points = symbol_meta.get("stops_level_points", 0.0)
            point = symbol_meta.get("point", 0.0)
            if stops_level_points > 0 and point > 0:
                broker_min_distance = stops_level_points * point
                logger.info(f"Broker minimum stop distance for {symbol_norm}: {broker_min_distance:.2f}")
        except Exception as e:
            logger.warning(f"Could not get broker minimum stop distance for {symbol_norm}: {e}")
        
        # Get symbol-specific rules (from config)
        symbol_key = symbol_norm.lower().rstrip('c')
        if symbol_key == 'xauusd':
            config_min_sl = 0.50
            config_max_sl = 1.20
            config_min_tp = 1.00
            config_max_tp = 2.50
        elif symbol_key == 'btcusd':
            config_min_sl = 5.0
            config_max_sl = 10.0
            config_min_tp = 10.0
            config_max_tp = 25.0
        else:
            config_min_sl = 0.0
            config_max_sl = float('inf')
            config_min_tp = 0.0
            config_max_tp = float('inf')
        
        # Adjust limits based on broker requirements
        # If broker requires larger minimum, use that as the floor
        # Allow up to 3x broker minimum to keep micro-scalps relatively tight but broker-compatible
        if broker_min_distance and broker_min_distance > 0:
            # Use broker minimum as the absolute minimum (with 10% buffer for safety)
            broker_min_sl = broker_min_distance * 1.1
            broker_min_tp = broker_min_distance * 1.1
            
            # If broker minimum is larger than config minimum, we need to be more permissive
            # This handles cases where broker restrictions prevent ultra-tight micro-scalps
            if broker_min_distance > config_min_sl:
                # Broker requires larger minimum - be more permissive but still keep it relatively tight
                min_sl = broker_min_sl  # Use broker minimum as floor
                min_tp = broker_min_tp
                # Allow up to 3x broker minimum (keeps micro-scalps tight but broker-compatible)
                # For BTCUSDc: if broker requires 100, allow 100-300 (still tight for micro-scalp)
                max_sl = broker_min_distance * 3.0
                max_tp = broker_min_distance * 3.0
                logger.info(f"Broker requires larger minimum ({broker_min_distance:.2f}) than config ({config_min_sl:.2f}) - using broker-aware limits: SL [{min_sl:.2f}, {max_sl:.2f}], TP [{min_tp:.2f}, {max_tp:.2f}]")
            else:
                # Broker minimum is smaller or equal - use config limits (they're tighter)
                min_sl = max(broker_min_sl, config_min_sl)
                min_tp = max(broker_min_tp, config_min_tp)
                max_sl = config_max_sl
                max_tp = config_max_tp
                logger.info(f"Using config limits (broker min {broker_min_distance:.2f} <= config min {config_min_sl:.2f}): SL [{min_sl:.2f}, {max_sl:.2f}], TP [{min_tp:.2f}, {max_tp:.2f}]")
        else:
            # Fallback to config limits if broker info unavailable
            min_sl = config_min_sl
            max_sl = config_max_sl
            min_tp = config_min_tp
            max_tp = config_max_tp
            logger.warning(f"Broker minimum distance unavailable for {symbol_norm}, using config limits")
        
        # Validate SL/TP distances - REJECT if outside broker-aware limits
        if sl_distance > max_sl:
            return {
                "success": False,
                "plan_id": None,
                "message": f"Micro-scalp SL distance {sl_distance:.2f} exceeds maximum {max_sl:.2f} for {symbol_norm}. {'Broker minimum: ' + str(broker_min_distance) + '. ' if broker_min_distance else ''}Micro-scalps require tight SL/TP. Calculate: SL distance = |entry_price - stop_loss|. For {symbol_norm}, SL must be between ${min_sl:.2f} and ${max_sl:.2f}.",
                "error": "SL_TOO_WIDE"
            }
        if sl_distance < min_sl:
            return {
                "success": False,
                "plan_id": None,
                "message": f"Micro-scalp SL distance {sl_distance:.2f} is below minimum {min_sl:.2f} for {symbol_norm}. {'Broker requires minimum: ' + str(broker_min_distance) + '. ' if broker_min_distance else ''}For {symbol_norm}, SL must be between ${min_sl:.2f} and ${max_sl:.2f}.",
                "error": "SL_TOO_TIGHT"
            }
        if tp_distance > max_tp:
            return {
                "success": False,
                "plan_id": None,
                "message": f"Micro-scalp TP distance {tp_distance:.2f} exceeds maximum {max_tp:.2f} for {symbol_norm}. {'Broker minimum: ' + str(broker_min_distance) + '. ' if broker_min_distance else ''}Micro-scalps require tight SL/TP. Calculate: TP distance = |take_profit - entry_price|. For {symbol_norm}, TP must be between ${min_tp:.2f} and ${max_tp:.2f}.",
                "error": "TP_TOO_WIDE"
            }
        if tp_distance < min_tp:
            return {
                "success": False,
                "plan_id": None,
                "message": f"Micro-scalp TP distance {tp_distance:.2f} is below minimum {min_tp:.2f} for {symbol_norm}. {'Broker requires minimum: ' + str(broker_min_distance) + '. ' if broker_min_distance else ''}For {symbol_norm}, TP must be between ${min_tp:.2f} and ${max_tp:.2f}.",
                "error": "TP_TOO_TIGHT"
            }
        
        # Create base conditions for micro-scalp plan
        base_conditions = {
            "plan_type": "micro_scalp",
            "timeframe": "M1",  # Micro-scalps use M1 timeframe
        }
        
        # Merge with any conditions passed from ChatGPT (preserve choch_bull/bear, price_near, etc.)
        if conditions:
            # Merge ChatGPT conditions with base conditions (ChatGPT conditions take precedence)
            merged_conditions = {**base_conditions, **conditions}
        else:
            merged_conditions = base_conditions
        
        # The micro-scalp engine will handle all condition checking via 4-layer validation
        # But we preserve conditions for display/debugging in the web interface
        
        # For micro-scalp plans, skip condition validation (micro-scalp engine handles it)
        # But we still want to preserve the conditions for display
        # Create plan directly without going through create_trade_plan's validation
        # which might strip out micro-scalp specific conditions
        
        # Generate unique plan ID (already done above)
        # Set expiration time (already done above)
        
        # Process entry_levels if provided (Phase 2: Multi-level entry support)
        processed_entry_levels = None
        if entry_levels:
            processed_entry_levels = self._validate_and_process_entry_levels(
                entry_levels, direction, entry_price, stop_loss, take_profit, symbol_norm
            )
            if processed_entry_levels is None:
                return {
                    "success": False,
                    "plan_id": None,
                    "message": "Invalid entry_levels: validation failed. Check that all levels have 'price' field and prices are reasonable.",
                    "error": "INVALID_ENTRY_LEVELS"
                }
        
        # Create trade plan directly
        plan = TradePlan(
            plan_id=plan_id,
            symbol=symbol_norm,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            volume=volume,
            conditions=merged_conditions,  # Use merged conditions (preserves ChatGPT conditions)
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="chatgpt",
            status="pending",
            expires_at=expires_at,
            notes=notes or f"Micro-scalp plan for {symbol_norm} - Ultra-short-term trade targeting small moves",
            entry_levels=processed_entry_levels  # Phase 2: Multi-level entry support
        )
        
        # Add to auto execution system
        success = self.auto_system.add_plan(plan)
        
        if success:
            return {
                "success": True,
                "plan_id": plan_id,
                "message": f"Micro-scalp plan created successfully. System will monitor conditions and execute automatically.",
                "plan_details": {
                    "symbol": symbol_norm,
                    "direction": direction,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "volume": volume,
                    "conditions": merged_conditions,
                    "expires_at": expires_at,
                    "notes": notes or f"Micro-scalp plan for {symbol_norm} - Ultra-short-term trade targeting small moves"
                }
            }
        else:
            return {
                "success": False,
                "plan_id": None,
                "message": "Failed to create micro-scalp plan"
            }

    def create_range_scalp_plan(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        volume: float = 0.01,
        min_confluence: int = 80,
        price_tolerance: float = None,
        expires_hours: int = 8,
        notes: str = None,
        entry_levels: Optional[List[Dict[str, Any]]] = None  # Phase 2: Multi-level entry support
    ) -> Dict[str, Any]:
        """
        Create a range scalping auto-execution plan.
        
        Monitors for:
        - Range scalping confluence score >= min_confluence (default: 80, weekend: 70)
        - Structure confirmation (CHOCH/BOS) on M15
        - Price near entry zone
        
        Args:
            symbol: Trading symbol
            direction: "BUY" or "SELL"
            entry_price: Entry price for the range scalp
            stop_loss: Stop loss price
            take_profit: Take profit price
            volume: Position size (default: 0.01)
            min_confluence: Minimum confluence score required (default: 80, weekend: 70)
            price_tolerance: Price tolerance for entry (auto-calculated if None)
            expires_hours: Plan expiry in hours (default: 8 for range scalping)
            notes: Optional plan description
        """
        
        # Check if weekend is active for BTCUSDc
        is_weekend = False
        if symbol.upper() in ["BTCUSDc", "BTCUSD"]:
            try:
                from infra.weekend_profile_manager import WeekendProfileManager
                weekend_manager = WeekendProfileManager()
                is_weekend = weekend_manager.is_weekend_active()
            except Exception as e:
                logger.debug(f"Could not check weekend status: {e}")
        
        # Auto-calculate tolerance based on symbol if not provided
        if price_tolerance is None:
            price_tolerance = get_price_tolerance(symbol)
        
        # Range scalping conditions
        conditions = {
            "range_scalp_confluence": min_confluence,  # Monitor for confluence >= this
            "structure_confirmation": True,  # Require CHOCH (reversal) or BOS (continuation) confirmation on structure_timeframe
            "structure_timeframe": "M15",  # M15 timeframe for structure
            "price_near": entry_price,
            "tolerance": price_tolerance,
            "plan_type": "range_scalp"  # Mark as range scalping plan
        }
        
        # Add weekend session marker if weekend is active
        if is_weekend:
            conditions["session"] = "Weekend"
            logger.info(f"Weekend mode active - adding session='Weekend' to range scalp plan conditions")
        
        return self.create_trade_plan(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            volume=volume,
            conditions=conditions,
            expires_hours=expires_hours,
            notes=notes or f"Range scalping {direction} plan (confluence >= {min_confluence})",
            entry_levels=entry_levels  # Phase 2: Multi-level entry support
        )
    
    def cancel_plan(self, plan_id: str) -> Dict[str, Any]:
        """Cancel a trade plan"""
        success = self.auto_system.cancel_plan(plan_id)
        
        if success:
            return {
                "success": True,
                "message": f"Trade plan {plan_id} cancelled successfully"
            }
        else:
            return {
                "success": False,
                "message": f"Failed to cancel trade plan {plan_id}"
            }
    
    def get_plan_status(self, plan_id: str = None, include_all_statuses: bool = False) -> Dict[str, Any]:
        """Get status of trade plans (default: pending only)"""
        status = self.auto_system.get_status(include_all_statuses=include_all_statuses)
        
        if plan_id:
            # Get specific plan status
            # First check in-memory plans (pending only)
            plan = self.auto_system.plans.get(plan_id)
            # If not found, query database (for executed/cancelled/expired plans)
            if not plan:
                plan = self.auto_system.get_plan_by_id(plan_id)
            if plan:
                # Phase 1: Get zone status
                zone_status = self.auto_system.get_plan_zone_status(plan)
                
                plan_dict = {
                    "plan_id": plan.plan_id,
                    "symbol": plan.symbol,
                    "direction": plan.direction,
                    "entry_price": plan.entry_price,
                    "stop_loss": plan.stop_loss,
                    "take_profit": plan.take_profit,
                    "volume": plan.volume,
                    "status": plan.status,
                    "created_at": plan.created_at,
                    "expires_at": plan.expires_at,
                    "executed_at": plan.executed_at,
                    "ticket": plan.ticket,
                    "notes": plan.notes
                }
                
                # Add profit/loss fields for executed/closed plans (always include, even if None)
                if hasattr(plan, 'profit_loss'):
                    plan_dict["profit_loss"] = plan.profit_loss
                if hasattr(plan, 'exit_price'):
                    plan_dict["exit_price"] = plan.exit_price
                if hasattr(plan, 'close_time'):
                    plan_dict["close_time"] = plan.close_time
                if hasattr(plan, 'close_reason'):
                    plan_dict["close_reason"] = plan.close_reason
                
                # Add conditions for all plans (needed for review)
                if hasattr(plan, 'conditions'):
                    plan_dict["conditions"] = plan.conditions
                
                # Phase 1: Add zone status fields
                if zone_status.get("success"):
                    plan_dict["in_tolerance_zone"] = zone_status.get("in_tolerance_zone", False)
                    plan_dict["zone_entry_tracked"] = zone_status.get("zone_entry_tracked", False)
                    plan_dict["zone_entry_time"] = zone_status.get("zone_entry_time")
                    plan_dict["zone_exit_time"] = zone_status.get("zone_exit_time")
                    plan_dict["price_distance_from_entry"] = zone_status.get("price_distance_from_entry")
                
                # Phase 3: Add cancellation status fields
                if hasattr(plan, 'cancellation_reason'):
                    plan_dict["cancellation_reason"] = plan.cancellation_reason
                if hasattr(plan, 'last_cancellation_check'):
                    plan_dict["last_cancellation_check"] = plan.last_cancellation_check
                
                # Calculate cancellation risk if plan is pending
                if plan.status == "pending":
                    cancellation_info = self._calculate_cancellation_risk(plan)
                    if cancellation_info:
                        plan_dict["cancellation_risk"] = cancellation_info.get("risk", 0.0)
                        plan_dict["cancellation_reasons"] = cancellation_info.get("reasons", [])
                        plan_dict["cancellation_priority"] = cancellation_info.get("priority", None)
                
                # Phase 4: Add re-evaluation status fields
                if plan.status == "pending":
                    re_eval_status = self.auto_system.get_plan_re_evaluation_status(plan)
                    if re_eval_status.get("success"):
                        plan_dict["last_re_evaluation"] = re_eval_status.get("last_re_evaluation")
                        plan_dict["re_evaluation_count_today"] = re_eval_status.get("re_evaluation_count_today", 0)
                        plan_dict["re_evaluation_cooldown_remaining"] = re_eval_status.get("re_evaluation_cooldown_remaining", 0)
                        plan_dict["re_evaluation_available"] = re_eval_status.get("re_evaluation_available", False)
                
                return {
                    "success": True,
                    "plan": plan_dict
                }
            else:
                return {
                    "success": False,
                    "message": f"Plan {plan_id} not found"
                }
        else:
            # Get all plans status
            def _get(p, key, default=None):
                try:
                    # Try to get as attribute first (for TradePlan dataclass objects)
                    value = getattr(p, key, None)
                    if value is not None:
                        return value
                except Exception:
                    pass
                
                # Fallback to dict access
                try:
                    if isinstance(p, dict):
                        value = p.get(key, default)
                        return value if value is not None else default
                except Exception:
                    pass
                
                return default
            return {
                "success": True,
                "system_status": status,
                "plans": [
                    {
                        "plan_id": _get(plan, "plan_id"),
                        "symbol": _get(plan, "symbol"),
                        "direction": _get(plan, "direction"),
                        "entry_price": _get(plan, "entry_price"),
                        "stop_loss": _get(plan, "stop_loss"),
                        "take_profit": _get(plan, "take_profit"),
                        "volume": _get(plan, "volume"),
                        "status": _get(plan, "status"),
                        "created_at": _get(plan, "created_at"),
                        "expires_at": _get(plan, "expires_at"),
                        "executed_at": _get(plan, "executed_at"),
                        "ticket": _get(plan, "ticket"),
                        "notes": _get(plan, "notes"),
                        "conditions": _get(plan, "conditions"),
                        # Phase 3: Add cancellation fields
                        "cancellation_reason": _get(plan, "cancellation_reason"),
                        "last_cancellation_check": _get(plan, "last_cancellation_check"),
                        # Phase 4: Add re-evaluation fields
                        "last_re_evaluation": _get(plan, "last_re_evaluation"),
                        "re_evaluation_count_today": _get(plan, "re_evaluation_count_today", 0),
                        "re_evaluation_available": _get(plan, "re_evaluation_available", False),
                    }
                    for plan in (status.get("plans", []) if isinstance(status, dict) else [])
                ]
            }

    def update_plan(
        self,
        plan_id: str,
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        volume: Optional[float] = None,
        conditions: Optional[Dict[str, Any]] = None,
        expires_hours: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an existing trade plan"""
        try:
            # Get existing plan to validate
            existing_plan = self.auto_system.get_plan_by_id(plan_id)
            if not existing_plan:
                return {
                    "success": False,
                    "message": f"Plan {plan_id} not found"
                }
            
            if existing_plan.status != 'pending':
                return {
                    "success": False,
                    "message": f"Cannot update plan {plan_id}: status is '{existing_plan.status}' (only 'pending' plans can be updated)"
                }
            
            # If conditions are provided, validate them
            if conditions:
                conditions, validation_errors = self._validate_and_fix_conditions(
                    conditions, 
                    existing_plan.symbol, 
                    entry_price or existing_plan.entry_price,
                    notes or existing_plan.notes
                )
                
                if validation_errors:
                    return {
                        "success": False,
                        "message": "Invalid conditions detected:\n" + "\n".join(f"  - {err}" for err in validation_errors)
                    }
            
            # Update the plan
            success = self.auto_system.update_plan(
                plan_id=plan_id,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                volume=volume,
                conditions=conditions,
                expires_hours=expires_hours,
                notes=notes
            )
            
            if success:
                # Get updated plan
                updated_plan = self.auto_system.get_plan_by_id(plan_id)
                return {
                    "success": True,
                    "message": f"Plan {plan_id} updated successfully",
                    "plan_id": plan_id,
                    "plan_details": {
                        "symbol": updated_plan.symbol,
                        "direction": updated_plan.direction,
                        "entry_price": updated_plan.entry_price,
                        "stop_loss": updated_plan.stop_loss,
                        "take_profit": updated_plan.take_profit,
                        "volume": updated_plan.volume,
                        "conditions": updated_plan.conditions,
                        "status": updated_plan.status,
                        "expires_at": updated_plan.expires_at,
                        "notes": updated_plan.notes
                    }
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to update plan {plan_id}"
                }
                
        except Exception as e:
            logger.error(f"Error updating plan {plan_id}: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Error updating plan: {str(e)}"
            }

    def _validate_and_process_entry_levels(
        self,
        entry_levels: List[Dict[str, Any]],
        direction: str,
        base_entry_price: float,
        base_stop_loss: float,
        base_take_profit: float,
        symbol: str
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Validate and process entry_levels for Phase 2 multi-level support.
        
        Args:
            entry_levels: List of level dicts with 'price' (required) and optional 'sl_offset', 'tp_offset', 'weight'
            direction: Trade direction (BUY or SELL)
            base_entry_price: Base entry price (used as fallback)
            base_stop_loss: Base stop loss (used if offsets not provided)
            base_take_profit: Base take profit (used if offsets not provided)
            symbol: Symbol for tolerance calculation
        
        Returns:
            Processed entry_levels list or None if validation fails
        """
        try:
            if not isinstance(entry_levels, list) or len(entry_levels) == 0:
                logger.error("entry_levels must be a non-empty list")
                return None
            
            if len(entry_levels) > 10:
                logger.warning(f"Too many entry levels ({len(entry_levels)}), limiting to 10")
                entry_levels = entry_levels[:10]
            
            processed_levels = []
            seen_prices = set()
            
            for idx, level in enumerate(entry_levels):
                if not isinstance(level, dict):
                    logger.error(f"Level {idx} must be a dict, got {type(level)}")
                    return None
                
                # Extract price (required)
                level_price = level.get("price")
                if level_price is None:
                    # Try to use base_entry_price as fallback for first level
                    if idx == 0:
                        level_price = base_entry_price
                        logger.info(f"Level {idx} missing 'price', using base_entry_price {base_entry_price}")
                    else:
                        logger.error(f"Level {idx} missing required 'price' field")
                        return None
                
                # Validate price is numeric and positive
                try:
                    level_price = float(level_price)
                    if level_price <= 0:
                        logger.error(f"Level {idx} price must be positive, got {level_price}")
                        return None
                except (ValueError, TypeError):
                    logger.error(f"Level {idx} price must be numeric, got {type(level_price)}")
                    return None
                
                # Check for duplicate prices (within tolerance)
                from infra.tolerance_helper import get_price_tolerance
                tolerance = get_price_tolerance(symbol)
                is_duplicate = False
                for seen_price in seen_prices:
                    if abs(level_price - seen_price) < tolerance * 0.5:  # 50% of tolerance = too close
                        is_duplicate = True
                        logger.warning(f"Level {idx} price {level_price} too close to existing level {seen_price} (within {tolerance * 0.5}), skipping")
                        break
                
                if is_duplicate:
                    continue
                
                seen_prices.add(level_price)
                
                # Extract optional fields
                sl_offset = level.get("sl_offset")
                tp_offset = level.get("tp_offset")
                weight = level.get("weight", 1.0)  # Default weight is 1.0
                
                # Validate offsets if provided
                # Offsets should be positive (distance), but we accept negative and convert to positive
                # The execution code uses abs() anyway, so this is just for clarity
                if sl_offset is not None:
                    try:
                        sl_offset = float(sl_offset)
                        if sl_offset == 0:
                            logger.error(f"Level {idx} sl_offset cannot be zero")
                            return None
                        # Convert negative to positive (distance is always positive)
                        if sl_offset < 0:
                            logger.warning(f"Level {idx} sl_offset is negative ({sl_offset}), converting to positive")
                            sl_offset = abs(sl_offset)
                    except (ValueError, TypeError):
                        logger.error(f"Level {idx} sl_offset must be numeric, got {type(sl_offset)}")
                        return None
                
                if tp_offset is not None:
                    try:
                        tp_offset = float(tp_offset)
                        if tp_offset == 0:
                            logger.error(f"Level {idx} tp_offset cannot be zero")
                            return None
                        # Convert negative to positive (distance is always positive)
                        # Note: For SELL, tp_offset below entry would be negative, but we want positive distance
                        if tp_offset < 0:
                            logger.warning(f"Level {idx} tp_offset is negative ({tp_offset}), converting to positive")
                            tp_offset = abs(tp_offset)
                    except (ValueError, TypeError):
                        logger.error(f"Level {idx} tp_offset must be numeric, got {type(tp_offset)}")
                        return None
                
                # Validate weight
                try:
                    weight = float(weight)
                    if weight <= 0:
                        logger.warning(f"Level {idx} weight must be positive, defaulting to 1.0")
                        weight = 1.0
                except (ValueError, TypeError):
                    logger.warning(f"Level {idx} weight must be numeric, defaulting to 1.0")
                    weight = 1.0
                
                # Build processed level
                processed_level = {
                    "price": level_price,
                    "weight": weight
                }
                
                if sl_offset is not None:
                    processed_level["sl_offset"] = sl_offset
                if tp_offset is not None:
                    processed_level["tp_offset"] = tp_offset
                
                processed_levels.append(processed_level)
            
            if len(processed_levels) == 0:
                logger.error("No valid entry levels after processing")
                return None
            
            # Sort levels by price (ascending for BUY, descending for SELL)
            # This ensures priority order (first in array = first to check)
            if direction == "BUY":
                processed_levels.sort(key=lambda x: x["price"])
            else:  # SELL
                processed_levels.sort(key=lambda x: x["price"], reverse=True)
            
            logger.info(f"Processed {len(processed_levels)} entry levels for {direction} plan")
            return processed_levels
            
        except Exception as e:
            logger.error(f"Error validating entry_levels: {e}", exc_info=True)
            return None
    
    def _calculate_cancellation_risk(self, plan) -> Optional[Dict[str, Any]]:
        """
        Calculate cancellation risk for a plan (Phase 3).
        
        Returns:
            Dict with 'risk' (0-1), 'reasons' (list), 'priority' (str) or None if not applicable
        """
        try:
            # Only calculate for pending plans
            if plan.status != "pending":
                return None
            
            # Check cancellation conditions
            cancellation_result = self.auto_system._check_plan_cancellation_conditions(plan)
            
            if cancellation_result and cancellation_result.get('should_cancel'):
                # Plan should be cancelled - high risk
                priority = cancellation_result.get('priority', 'medium')
                reason = cancellation_result.get('reason', 'Conditional cancellation')
                
                # Map priority to risk score
                priority_risk_map = {
                    'high': 1.0,
                    'medium': 0.7,
                    'low': 0.4
                }
                risk = priority_risk_map.get(priority, 0.5)
                
                return {
                    'risk': risk,
                    'reasons': [reason],
                    'priority': priority
                }
            else:
                # Check for potential cancellation reasons (lower risk)
                reasons = []
                risk = 0.0
                
                # Check price distance (if available)
                try:
                    zone_status = self.auto_system.get_plan_zone_status(plan)
                    if zone_status.get("success"):
                        distance = zone_status.get("price_distance_from_entry")
                        if distance is not None:
                            # Get threshold for symbol
                            adaptive_config = getattr(self.auto_system, '_adaptive_config', {})
                            if isinstance(adaptive_config, dict) and 'cancellation_rules' in adaptive_config:
                                thresholds = adaptive_config.get('cancellation_rules', {}).get('price_distance_thresholds', {})
                                symbol_key = plan.symbol.upper()
                                threshold_pct = thresholds.get(symbol_key, thresholds.get(symbol_key.rstrip('Cc') + 'c', thresholds.get('default', 0.5)))
                                
                                # Calculate risk based on distance relative to threshold
                                if distance > threshold_pct * 0.8:  # 80% of threshold
                                    risk = min(0.5, (distance / threshold_pct) * 0.5)
                                    reasons.append(f"Price is {distance:.2f}% away from entry (threshold: {threshold_pct}%)")
                except Exception as e:
                    logger.debug(f"Error calculating price distance risk: {e}")
                
                # Check plan age
                try:
                    created_at_dt = datetime.fromisoformat(plan.created_at.replace('Z', '+00:00'))
                    if created_at_dt.tzinfo is None:
                        created_at_dt = created_at_dt.replace(tzinfo=timezone.utc)
                    now_utc = datetime.now(timezone.utc)
                    plan_age_hours = (now_utc - created_at_dt).total_seconds() / 3600.0
                    
                    if plan_age_hours > 20:  # Close to 24h threshold
                        age_risk = min(0.3, (plan_age_hours / 24.0) * 0.3)
                        risk = max(risk, age_risk)
                        reasons.append(f"Plan is {plan_age_hours:.1f}h old (may expire soon)")
                except Exception as e:
                    logger.debug(f"Error calculating age risk: {e}")
                
                if risk > 0.0:
                    return {
                        'risk': risk,
                        'reasons': reasons,
                        'priority': None  # No immediate cancellation
                    }
                else:
                    return None
                    
        except Exception as e:
            logger.debug(f"Error calculating cancellation risk: {e}")
            return None

# Global instance
chatgpt_auto_execution = ChatGPTAutoExecution()

def get_chatgpt_auto_execution() -> ChatGPTAutoExecution:
    """Get the global ChatGPT auto execution instance"""
    return chatgpt_auto_execution
