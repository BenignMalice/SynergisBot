"""
ChatGPT Auto Execution Tools
Tools for ChatGPT to create and manage auto-executing trade plans.
"""

import asyncio
import os
from typing import Dict, Any, Optional, Tuple, Union
import json
import urllib.parse
import urllib.request
import urllib.error
from infra.tolerance_helper import get_price_tolerance

# API base URL - configurable via environment variable
# Use IPv4 loopback by default to avoid Windows IPv6 localhost (::1) resolution issues
# when the server is bound to 0.0.0.0.
API_BASE_URL = os.getenv("AUTO_EXECUTION_API_URL", "http://127.0.0.1:8000")


def _build_url(url: str, params: Optional[Dict[str, Any]] = None) -> str:
    if not params:
        return url
    # Drop None values and convert to strings for urlencode
    clean = {k: str(v) for k, v in params.items() if v is not None}
    if not clean:
        return url
    joiner = "&" if ("?" in url) else "?"
    return url + joiner + urllib.parse.urlencode(clean)


async def _http_request_json(
    method: str,
    url: str,
    *,
    json_body: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout_seconds: float = 30.0,
) -> Tuple[int, str, Optional[Union[Dict[str, Any], list]]]:
    """
    HTTP helper that prefers httpx (if installed) and falls back to stdlib urllib.
    Returns (status_code, response_text, parsed_json_or_none).
    """
    final_url = _build_url(url, params=params)
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update({str(k): str(v) for k, v in headers.items()})

    # Prefer httpx if available
    try:
        import httpx  # type: ignore
    except ModuleNotFoundError:
        httpx = None  # type: ignore

    if httpx is not None:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.request(method.upper(), final_url, json=json_body, headers=hdrs)
            text = resp.text
            parsed = None
            ct = resp.headers.get("content-type", "")
            if ct.startswith("application/json"):
                try:
                    parsed = resp.json()
                except Exception:
                    parsed = None
            return int(resp.status_code), text, parsed

    # Fallback: stdlib urllib (run in thread to avoid blocking event loop)
    def _do_urllib() -> Tuple[int, str, Optional[Union[Dict[str, Any], list]]]:
        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
        req = urllib.request.Request(final_url, data=data, headers=hdrs, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                status = int(getattr(resp, "status", resp.getcode()))
                raw = resp.read()
                text = raw.decode("utf-8", errors="replace")
                parsed = None
                ct = resp.headers.get("content-type", "")
                if ct.startswith("application/json"):
                    try:
                        parsed = json.loads(text)
                    except Exception:
                        parsed = None
                return status, text, parsed
        except urllib.error.HTTPError as e:
            status = int(e.code)
            raw = e.read() if hasattr(e, "read") else b""
            text = raw.decode("utf-8", errors="replace")
            parsed = None
            ct = ""
            try:
                ct = e.headers.get("content-type", "")
            except Exception:
                ct = ""
            if ct.startswith("application/json"):
                try:
                    parsed = json.loads(text)
                except Exception:
                    parsed = None
            return status, text, parsed

    return await asyncio.to_thread(_do_urllib)

async def tool_create_auto_trade_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a trade plan that will be monitored and executed automatically when conditions are met"""
    
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Weekend strategy filtering (BTCUSDc ONLY)
        symbol = args.get("symbol", "").upper()
        if symbol in ["BTCUSDc", "BTCUSD"]:
            try:
                from infra.weekend_profile_manager import WeekendProfileManager
                weekend_manager = WeekendProfileManager()
                is_weekend = weekend_manager.is_weekend_active()
                
                if is_weekend:
                    # Weekend active - filter strategies
                    strategy_type = args.get("strategy_type")
                    
                    # Weekend-allowed strategies
                    weekend_allowed = [
                        "vwap_reversion",
                        "liquidity_sweep_reversal",
                        "micro_scalp",
                        "mean_reversion_range_scalp"  # Note: auto-adds structure_confirmation
                    ]
                    
                    # Weekend-disallowed strategies
                    weekend_disallowed = [
                        "breakout_ib_volatility_trap",
                        "trend_continuation_pullback",
                        "session_liquidity_run"  # London Breakout equivalent
                    ]
                    
                    if strategy_type:
                        if strategy_type in weekend_disallowed:
                            return {
                                "summary": f"ERROR: Strategy '{strategy_type}' is not allowed during weekend hours. Allowed strategies: {', '.join(weekend_allowed)}",
                                "data": {
                                    "error": f"Strategy '{strategy_type}' disabled during weekend",
                                    "allowed_strategies": weekend_allowed,
                                    "disallowed_strategies": weekend_disallowed
                                }
                            }
                        
                        if strategy_type not in weekend_allowed:
                            logger.warning(
                                f"Strategy '{strategy_type}' not in weekend-allowed list. "
                                f"Allowed: {weekend_allowed}. Proceeding with caution."
                            )
            except Exception as e:
                logger.warning(f"Error checking weekend status for strategy filtering: {e}")
                # Continue if weekend check fails
        
        # Convert trigger_type/trigger_value to conditions format if present
        conditions = args.get("conditions", {})
        
        # Handle trigger_type and trigger_value parameters (ChatGPT may send these instead of conditions)
        trigger_type = args.get("trigger_type")
        trigger_value = args.get("trigger_value")
        
        if trigger_type and trigger_value and not conditions:
            entry_price = args.get("entry") or args.get("entry_price")
            symbol = args.get("symbol", "").upper()
            # Remove 'c' suffix if present for tolerance calculation
            symbol_base = symbol.rstrip('C')
            
            # Convert to proper conditions format
            if trigger_type.lower() == "structure":
                if trigger_value.upper() in ["CHOCH_BULL", "BOS_BULL", "CHANGE_OF_CHARACTER_BULL"]:
                    conditions["choch_bull"] = True
                    conditions["timeframe"] = args.get("timeframe", "M5")
                    # Add price_near condition with appropriate tolerance
                    tolerance = get_price_tolerance(symbol_base)
                    conditions["price_near"] = entry_price
                    conditions["tolerance"] = tolerance
                elif trigger_value.upper() in ["CHOCH_BEAR", "BOS_BEAR", "CHANGE_OF_CHARACTER_BEAR"]:
                    conditions["choch_bear"] = True
                    conditions["timeframe"] = args.get("timeframe", "M5")
                    # Add price_near condition
                    tolerance = get_price_tolerance(symbol_base)  # Use symbol_base for consistency
                    conditions["price_near"] = entry_price
                    conditions["tolerance"] = tolerance
            elif trigger_type.lower() == "rejection_wick":
                conditions["rejection_wick"] = True
                conditions["timeframe"] = args.get("timeframe", "M5")
                tolerance = get_price_tolerance(symbol)
                conditions["price_near"] = entry_price
                conditions["tolerance"] = tolerance
            elif trigger_type.lower() == "price":
                if trigger_value.upper() in ["ABOVE", "BREAKOUT_ABOVE"]:
                    conditions["price_above"] = entry_price
                elif trigger_value.upper() in ["BELOW", "BREAKOUT_BELOW"]:
                    conditions["price_below"] = entry_price
                else:
                    # Default to price_near
                    tolerance = get_price_tolerance(symbol)
                    conditions["price_near"] = entry_price
                    conditions["tolerance"] = tolerance
        
        # Extract strategy_type if provided (for Universal SL/TP Manager)
        strategy_type = args.get("strategy_type")
        if strategy_type:
            # Add strategy_type to conditions so it's available during execution
            conditions["strategy_type"] = strategy_type
        
        # Handle min_confluence parameter (for all strategies)
        # Phase 3.1: Updated with comprehensive validation
        min_confluence = args.get("min_confluence")
        if min_confluence is not None:
            # ⚠️ VALIDATION: Check if range_scalp_confluence already exists in conditions
            # Check conditions dict FIRST (before checking strategy_type)
            if "range_scalp_confluence" in conditions:
                logger.warning(
                    f"Plan has both range_scalp_confluence and min_confluence. "
                    f"Using range_scalp_confluence (takes precedence). min_confluence will be ignored."
                )
                # Don't add min_confluence if range_scalp_confluence exists
                # range_scalp_confluence takes precedence
            else:
                try:
                    # Validate and convert to int (with error handling)
                    min_confluence = int(min_confluence)
                    # Clamp to valid range (0-100)
                    min_confluence = max(0, min(100, min_confluence))
                except (ValueError, TypeError) as e:
                    raise ValueError(
                        f"min_confluence must be an integer between 0 and 100, got: {min_confluence} (type: {type(min_confluence).__name__})"
                    )
                
                # ⚠️ CRITICAL: Check if price condition exists (required for ALL plans with min_confluence)
                # This includes both confluence-only and hybrid mode plans
                # Price conditions ensure execution happens at the right price level
                has_price_condition = any([
                    "price_near" in conditions,
                    "price_above" in conditions,
                    "price_below" in conditions
                ])
                
                if not has_price_condition:
                    raise ValueError(
                        "Plans with min_confluence require at least one price condition "
                        "(price_near, price_above, or price_below). "
                        "Confluence alone is not sufficient - you must specify an entry price level. "
                        "This applies to both confluence-only and hybrid mode plans."
                    )
                
                # ⚠️ VALIDATION: Check for contradictory price conditions
                # Having both price_above and price_below is contradictory (can't be both above and below)
                if "price_above" in conditions and "price_below" in conditions:
                    price_above = conditions.get("price_above")
                    price_below = conditions.get("price_below")
                    # Both conditions present is contradictory regardless of values
                    raise ValueError(
                        f"Contradictory price conditions: Cannot have both price_above ({price_above}) and price_below ({price_below}). "
                        f"Use only one directional price condition (price_above OR price_below, not both)."
                    )
                
                # ⚠️ VALIDATION: Validate price condition values
                entry_price = args.get("entry") or args.get("entry_price")
                if "price_near" in conditions:
                    price_near = conditions.get("price_near")
                    if price_near is None or price_near <= 0:
                        raise ValueError(f"price_near must be a positive number, got: {price_near}")
                    
                    if entry_price:
                        # Check if price_near matches entry_price (within reasonable tolerance)
                        tolerance = conditions.get("tolerance")
                        if tolerance is None:
                            symbol_base = (args.get("symbol") or "").upper().rstrip('Cc')
                            tolerance = get_price_tolerance(symbol_base)
                        
                        if abs(price_near - entry_price) > tolerance * 2:  # Allow some flexibility
                            logger.warning(
                                f"price_near ({price_near}) differs significantly from entry_price ({entry_price}). "
                                f"Consider using entry_price for price_near."
                            )
                    
                    # Check tolerance is provided or can be calculated
                    if "tolerance" not in conditions:
                        logger.warning("price_near specified but tolerance not provided - will be auto-calculated")
                
                # ⚠️ VALIDATION: Warn for very high thresholds
                if min_confluence >= 90:
                    logger.warning(
                        f"min_confluence={min_confluence} is very high (>=90). "
                        f"This may prevent execution in most market conditions. "
                        f"Consider using 60-75 for most strategies."
                    )
                
                # ⚠️ NOTE: min_confluence = 0 is allowed but not recommended
                # It effectively disables the confluence check (allows any confluence)
                if min_confluence == 0:
                    logger.warning(
                        "min_confluence=0 means no minimum confluence required. "
                        "Consider using a minimum threshold (e.g., 40-50) to filter out very low confluence."
                    )
                
                # ⚠️ NOTE: Check conditions dict FIRST (already done above), then fall back to strategy_type
                # For range scalping plans, use range_scalp_confluence
                if strategy_type == "mean_reversion_range_scalp" or "range_scalp" in str(strategy_type).lower():
                    conditions["range_scalp_confluence"] = min_confluence
                    conditions["plan_type"] = "range_scalp"
                    # Also add structure confirmation for range scalping
                    if "structure_confirmation" not in conditions:
                        conditions["structure_confirmation"] = True
                        conditions["structure_timeframe"] = args.get("structure_timeframe", "M15")
                else:
                    # For other strategies, use generic min_confluence
                    conditions["min_confluence"] = min_confluence
                    # Note: System will now monitor this for all plan types
                    logger.info(
                        f"Added min_confluence={min_confluence} to plan conditions "
                        f"(strategy: {strategy_type})"
                    )
        
        # Handle volume conditions (Volume Confirmation Implementation)
        volume_confirmation = conditions.get("volume_confirmation")
        volume_ratio = conditions.get("volume_ratio")
        volume_above = conditions.get("volume_above")
        volume_spike = conditions.get("volume_spike")
        
        if any([volume_confirmation, volume_ratio, volume_above, volume_spike]):
            # Validate timeframe (if provided)
            volume_tf = conditions.get("timeframe") or args.get("timeframe") or args.get("prefer_timeframe")
            if volume_tf:
                # Supported timeframes for volume calculations
                supported_timeframes = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"}
                volume_tf_upper = str(volume_tf).upper()
                
                if volume_tf_upper not in supported_timeframes:
                    raise ValueError(
                        f"Unsupported timeframe '{volume_tf}' for volume conditions. "
                        f"Supported timeframes: {', '.join(sorted(supported_timeframes))}. "
                        f"Please use one of the supported timeframes (e.g., M5, M15, H1)."
                    )
            
            # Validate volume condition values
            if volume_above is not None:
                try:
                    volume_above = float(volume_above)
                    if volume_above < 0:
                        raise ValueError(f"volume_above must be non-negative, got: {volume_above}")
                except (ValueError, TypeError) as e:
                    raise ValueError(f"volume_above must be a non-negative number, got: {volume_above} (type: {type(volume_above).__name__})")
            
            if volume_ratio is not None:
                try:
                    volume_ratio = float(volume_ratio)
                    if volume_ratio <= 0:
                        raise ValueError(f"volume_ratio must be positive, got: {volume_ratio}")
                except (ValueError, TypeError) as e:
                    raise ValueError(f"volume_ratio must be a positive number, got: {volume_ratio} (type: {type(volume_ratio).__name__})")
            
            # Warn about potentially contradictory combinations
            volume_condition_count = sum([
                1 if volume_confirmation else 0,
                1 if volume_ratio else 0,
                1 if volume_above else 0,
                1 if volume_spike else 0
            ])
            
            if volume_condition_count > 2:
                logger.warning(
                    f"Multiple volume conditions specified ({volume_condition_count}). "
                    f"All must pass for execution. Consider using fewer conditions for clarity."
                )
            
            # Warn if volume_above and volume_ratio might conflict
            if volume_above and volume_ratio:
                logger.warning(
                    f"Both volume_above ({volume_above}) and volume_ratio ({volume_ratio}) specified. "
                    f"Both must pass. Ensure these conditions are compatible."
                )
            
            # Note: volume_confirmation and volume_spike are compatible
            if volume_confirmation and volume_spike:
                logger.debug(
                    f"Both volume_confirmation and volume_spike specified. "
                    f"volume_confirmation will use spike for non-BTCUSD symbols."
                )
        
        # Add weekend session marker to conditions if weekend is active (for expiration logic)
        symbol = args.get("symbol", "").upper()
        if symbol in ["BTCUSDc", "BTCUSD"]:
            try:
                from infra.weekend_profile_manager import WeekendProfileManager
                weekend_manager = WeekendProfileManager()
                if weekend_manager.is_weekend_active():
                    conditions["session"] = "Weekend"
                    logger.info(f"Weekend mode active - marking plan with session='Weekend'")
            except Exception as e:
                logger.debug(f"Could not check weekend status: {e}")
        
        url = f"{API_BASE_URL}/auto-execution/create-plan"
        payload = {
            "symbol": args.get("symbol"),
            "direction": args.get("direction"),
            "entry_price": args.get("entry") or args.get("entry_price"),
            "stop_loss": args.get("stop_loss"),
            "take_profit": args.get("take_profit"),
            "volume": args.get("volume", 0.01),
            "conditions": conditions,
            "expires_hours": args.get("expires_hours", 24),
            "notes": args.get("notes") or args.get("reasoning")
        }
        
        logger.info(f"Calling auto-execution API: {url}")
        logger.debug(f"Request payload: {payload}")
        
        try:
            status_code, text, parsed = await _http_request_json(
                "POST", url, json_body=payload, timeout_seconds=30.0
            )
        except Exception as e:
            logger.error(f"HTTP error calling {url}: {e}", exc_info=True)
            return {
                "summary": f"ERROR: Failed to call auto-execution API: {str(e)}",
                "data": {"error": str(e), "url": url},
            }

        logger.info(f"API response status: {status_code}")

        if status_code == 200:
            data = parsed if parsed is not None else {}
            logger.info(f"Plan created successfully: {data.get('plan_id') if isinstance(data, dict) else None}")
            return {
                "summary": f"SUCCESS: Auto Trade Plan Created: {data.get('plan_id', 'Unknown') if isinstance(data, dict) else 'Unknown'}",
                "data": data,
            }

        error_detail = None
        if isinstance(parsed, dict):
            error_detail = parsed.get("detail")
        if not error_detail:
            error_detail = text

        logger.error(f"API returned error status {status_code}: {error_detail}")
        return {
            "summary": f"ERROR: Failed to create auto trade plan: {status_code} - {error_detail}",
            "data": {"error": error_detail, "status_code": status_code},
        }
                
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error creating auto trade plan: {e}", exc_info=True)
        return {
            "summary": f"ERROR: Error creating auto trade plan: {str(e)}",
            "data": {"error": str(e), "traceback": traceback.format_exc()}
        }

async def tool_create_choch_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a CHOCH-based trade plan for auto execution"""
    
    try:
        # Extract additional conditions if provided (e.g., m1_choch_bos_combo, min_volatility, bb_width_threshold)
        # ChatGPT may pass conditions as a nested object OR as top-level fields
        conditions = args.get("conditions", {})
        
        # Also check for condition fields at top level (ChatGPT sometimes passes them directly)
        condition_fields = [
            "m1_choch_bos_combo", "min_volatility", "bb_width_threshold", 
            "volatility_state", "ema_slope", "timeframe"
        ]
        for field in condition_fields:
            if field in args and field not in conditions:
                conditions[field] = args[field]
        
        # Determine choch_type from conditions, explicit parameter, or direction
        choch_type = args.get("choch_type")
        
        # First, check if choch_bull or choch_bear is in conditions
        if not choch_type:
            if conditions.get("choch_bull"):
                choch_type = "bull"
            elif conditions.get("choch_bear"):
                choch_type = "bear"
            else:
                # Infer from direction: BUY -> bull, SELL -> bear
                direction = args.get("direction", "").upper()
                choch_type = "bull" if direction == "BUY" else "bear"
        elif choch_type not in ["bull", "bear"]:
            # Handle if choch_type is True/False or other format
            if choch_type is True or str(choch_type).lower() == "true":
                choch_type = "bull" if args.get("direction", "").upper() == "BUY" else "bear"
            else:
                choch_type = "bear"  # Default
        
        url = f"{API_BASE_URL}/auto-execution/create-choch-plan"
        payload = {
            "symbol": args.get("symbol"),
            "direction": args.get("direction"),
            "entry_price": args.get("entry") or args.get("entry_price"),
            "stop_loss": args.get("stop_loss"),
            "take_profit": args.get("take_profit"),
            "volume": args.get("volume", 0.01),
            "choch_type": choch_type,
            "price_tolerance": args.get("price_tolerance") or get_price_tolerance(args.get("symbol", "")),
            "expires_hours": args.get("expires_hours", 24),
            "notes": args.get("notes") or args.get("reasoning"),
            "conditions": conditions if conditions else None,
        }

        status_code, text, parsed = await _http_request_json("POST", url, json_body=payload, timeout_seconds=30.0)

        if status_code == 200:
            data = parsed if parsed is not None else {}
            return {"summary": f"SUCCESS: CHOCH Plan Created: {data.get('plan_id', 'Unknown') if isinstance(data, dict) else 'Unknown'}", "data": data}

        return {"summary": f"ERROR: Failed to create CHOCH plan: {status_code}", "data": {"error": text}}
                
    except Exception as e:
        return {
            "summary": f"ERROR: Error creating CHOCH plan: {str(e)}",
            "data": {"error": str(e)}
        }

async def tool_create_rejection_wick_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a rejection wick-based trade plan for auto execution"""
    
    try:
        url = f"{API_BASE_URL}/auto-execution/create-rejection-wick-plan"
        payload = {
            "symbol": args.get("symbol"),
            "direction": args.get("direction"),
            "entry_price": args.get("entry") or args.get("entry_price"),
            "stop_loss": args.get("stop_loss"),
            "take_profit": args.get("take_profit"),
            "volume": args.get("volume", 0.01),
            "price_tolerance": args.get("price_tolerance") or get_price_tolerance(args.get("symbol", "")),
            "expires_hours": args.get("expires_hours", 24),
            "notes": args.get("notes") or args.get("reasoning"),
        }
        status_code, text, parsed = await _http_request_json("POST", url, json_body=payload, timeout_seconds=30.0)
        if status_code == 200:
            data = parsed if parsed is not None else {}
            return {"summary": f"SUCCESS: Rejection Wick Plan Created: {data.get('plan_id', 'Unknown') if isinstance(data, dict) else 'Unknown'}", "data": data}
        return {"summary": f"ERROR: Failed to create rejection wick plan: {status_code}", "data": {"error": text}}
                
    except Exception as e:
        return {
            "summary": f"ERROR: Error creating rejection wick plan: {str(e)}",
            "data": {"error": str(e)}
        }

async def tool_create_order_block_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create an order block-based trade plan for auto execution"""
    
    try:
        url = f"{API_BASE_URL}/auto-execution/create-order-block-plan"
        payload = {
            "symbol": args.get("symbol"),
            "direction": args.get("direction"),
            "entry_price": args.get("entry") or args.get("entry_price"),
            "stop_loss": args.get("stop_loss"),
            "take_profit": args.get("take_profit"),
            "volume": args.get("volume", 0.01),
            "order_block_type": args.get("order_block_type", "auto"),
            "min_validation_score": args.get("min_validation_score", 60),
            "price_tolerance": args.get("price_tolerance") or get_price_tolerance(args.get("symbol", "")),
            "expires_hours": args.get("expires_hours", 24),
            "notes": args.get("notes") or args.get("reasoning"),
        }
        status_code, text, parsed = await _http_request_json("POST", url, json_body=payload, timeout_seconds=30.0)
        if status_code == 200:
            data = parsed if parsed is not None else {}
            return {"summary": f"SUCCESS: Order Block Plan Created: {data.get('plan_id', 'Unknown') if isinstance(data, dict) else 'Unknown'}", "data": data}
        return {"summary": f"ERROR: Failed to create order block plan: {status_code}", "data": {"error": text}}
                
    except Exception as e:
        return {
            "summary": f"ERROR: Error creating order block plan: {str(e)}",
            "data": {"error": str(e)}
        }

async def tool_create_bracket_trade_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a bracket trade plan (OCO - One Cancels Other) for auto execution"""
    
    try:
        url = f"{API_BASE_URL}/auto-execution/create-bracket-trade-plan"
        payload = {
            "symbol": args.get("symbol"),
            "buy_entry": args.get("buy_entry"),
            "buy_sl": args.get("buy_sl"),
            "buy_tp": args.get("buy_tp"),
            "sell_entry": args.get("sell_entry"),
            "sell_sl": args.get("sell_sl"),
            "sell_tp": args.get("sell_tp"),
            "volume": args.get("volume", 0.01),
            "conditions": args.get("conditions"),
            "expires_hours": args.get("expires_hours", 24),
            "notes": args.get("notes") or args.get("reasoning"),
        }
        status_code, text, parsed = await _http_request_json("POST", url, json_body=payload, timeout_seconds=30.0)
        if status_code == 200:
            data = parsed if parsed is not None else {}
            if isinstance(data, dict):
                summary = (
                    f"SUCCESS: Bracket Trade Plan Created: {data.get('bracket_trade_id', 'Unknown')} "
                    f"(BUY: {data.get('buy_plan_id')}, SELL: {data.get('sell_plan_id')})"
                )
            else:
                summary = "SUCCESS: Bracket Trade Plan Created"
            return {"summary": summary, "data": data}
        return {"summary": f"ERROR: Failed to create bracket trade plan: {status_code}", "data": {"error": text}}
                
    except Exception as e:
        return {
            "summary": f"ERROR: Error creating bracket trade plan: {str(e)}",
            "data": {"error": str(e)}
        }

async def tool_create_micro_scalp_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a micro-scalp auto-execution plan for ultra-short-term trading"""
    
    try:
        # Extract conditions if provided (ChatGPT may pass choch_bull/bear, price_near, etc.)
        conditions = args.get("conditions", {})
        
        url = f"{API_BASE_URL}/auto-execution/create-micro-scalp-plan"
        payload = {
            "symbol": args.get("symbol"),
            "direction": args.get("direction"),
            "entry_price": args.get("entry") or args.get("entry_price"),
            "stop_loss": args.get("stop_loss"),
            "take_profit": args.get("take_profit"),
            "volume": args.get("volume", 0.01),
            "expires_hours": args.get("expires_hours", 2),
            "notes": args.get("notes") or args.get("reasoning"),
            "conditions": conditions if conditions else None,
        }
        status_code, text, parsed = await _http_request_json("POST", url, json_body=payload, timeout_seconds=30.0)
        if status_code == 200:
            data = parsed if parsed is not None else {}
            return {"summary": f"SUCCESS: Micro-Scalp Plan Created: {data.get('plan_id', 'Unknown') if isinstance(data, dict) else 'Unknown'}", "data": data}
        return {"summary": f"ERROR: Failed to create micro-scalp plan: {status_code}", "data": {"error": text}}
                
    except Exception as e:
        return {
            "summary": f"ERROR: Error creating micro-scalp plan: {str(e)}",
            "data": {"error": str(e)}
        }

async def tool_create_range_scalp_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a range scalping auto-execution plan.
    
    ⚠️ WEEKEND MODE NOTE: This tool auto-adds structure_confirmation for range scalping.
    For confluence-only weekend plans, use tool_create_auto_trade_plan with NON-range strategies
    (e.g., 'vwap_reversion', 'liquidity_sweep_reversal') instead.
    """
    
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Weekend strategy filtering (BTCUSDc ONLY)
        symbol = args.get("symbol", "").upper()
        if symbol in ["BTCUSDc", "BTCUSD"]:
            try:
                from infra.weekend_profile_manager import WeekendProfileManager
                weekend_manager = WeekendProfileManager()
                is_weekend = weekend_manager.is_weekend_active()
                
                if is_weekend:
                    logger.info("Weekend mode active - range scalping allowed (but note: auto-adds structure_confirmation)")
            except Exception as e:
                logger.debug(f"Could not check weekend status: {e}")
        # Support multiple parameter name variations
        # entry_price: entry, entry_price, buy_entry, sell_entry
        entry_price = (
            args.get("entry") or 
            args.get("entry_price") or 
            args.get("buy_entry") or 
            args.get("sell_entry")
        )
        
        # stop_loss: stop_loss, buy_sl, sell_sl, sl
        stop_loss = (
            args.get("stop_loss") or 
            args.get("buy_sl") or 
            args.get("sell_sl") or
            args.get("sl")
        )
        
        # take_profit: take_profit, buy_tp, sell_tp, tp
        take_profit = (
            args.get("take_profit") or 
            args.get("buy_tp") or 
            args.get("sell_tp") or
            args.get("tp")
        )
        
        # Check if weekend is active and adjust defaults accordingly
        symbol = args.get("symbol", "").upper()
        notes = args.get("notes") or args.get("reasoning") or ""
        is_weekend = False
        if symbol in ["BTCUSDc", "BTCUSD"]:
            try:
                from infra.weekend_profile_manager import WeekendProfileManager
                weekend_manager = WeekendProfileManager()
                is_weekend = weekend_manager.is_weekend_active()
                if is_weekend:
                    if notes:
                        notes += " [Weekend Plan]"
                    else:
                        notes = "[Weekend Plan]"
                    logger.info(f"Weekend mode active - marking range scalp plan as weekend")
            except Exception as e:
                logger.debug(f"Could not check weekend status: {e}")
        
        # Use weekend default confluence (70) if weekend is active and user didn't specify
        default_confluence = 70 if is_weekend else 80
        min_confluence = args.get("min_confluence")
        if min_confluence is None:
            min_confluence = default_confluence
            logger.info(f"Using default confluence for {'weekend' if is_weekend else 'weekday'} plan: {min_confluence}")
        
        url = f"{API_BASE_URL}/auto-execution/create-range-scalp-plan"
        payload = {
            "symbol": args.get("symbol"),
            "direction": args.get("direction"),
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "volume": args.get("volume", 0.01),
            "min_confluence": min_confluence,
            "price_tolerance": args.get("price_tolerance"),
            "expires_hours": args.get("expires_hours", 8),
            "notes": notes,
        }
        status_code, text, parsed = await _http_request_json("POST", url, json_body=payload, timeout_seconds=30.0)
        if status_code == 200:
            data = parsed if parsed is not None else {}
            return {
                "summary": f"SUCCESS: Range Scalping Plan Created: {data.get('plan_id', 'Unknown') if isinstance(data, dict) else 'Unknown'}",
                "data": data,
            }
        return {"summary": f"ERROR: Failed to create range scalp plan: {status_code}", "data": {"error": text}}
                
    except Exception as e:
        return {
            "summary": f"ERROR: Error creating range scalp plan: {str(e)}",
            "data": {"error": str(e)}
        }

async def tool_cancel_auto_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    """Cancel an auto-executing trade plan"""
    
    try:
        plan_id = args.get("plan_id")
        if not plan_id:
            return {
                "success": False,
                "error": "plan_id is required"
            }
            
        # Use longer timeout for cancellation (60s) as it may need to wait for locks
        url = f"{API_BASE_URL}/auto-execution/cancel-plan/{plan_id}"
        status_code, text, parsed = await _http_request_json("POST", url, json_body=None, timeout_seconds=60.0)
        if status_code == 200:
            data = parsed if parsed is not None else {}
            return {"summary": f"SUCCESS: Auto Plan Cancelled: {args.get('plan_id', 'Unknown')}", "data": data}
        return {"summary": f"ERROR: Failed to cancel plan: {status_code}", "data": {"error": text}}
                
    except Exception as e:
        return {
            "summary": f"ERROR: Error cancelling plan: {str(e)}",
            "data": {"error": str(e)}
        }

async def tool_update_auto_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing auto-executing trade plan (only pending plans can be updated)"""
    
    try:
        plan_id = args.get("plan_id")
        if not plan_id:
            return {
                "success": False,
                "error": "❌ ERROR: plan_id is REQUIRED but was not provided. You MUST include the plan_id (e.g., 'chatgpt_0ea79233') when updating a plan. To find the plan_id, first use moneybot.get_auto_plan_status to list all plans and identify the correct plan_id for the plan you want to update.",
                "summary": "ERROR: plan_id is required. Use moneybot.get_auto_plan_status to find plan IDs."
            }
        
        # Build request payload with only provided fields
        payload = {}
        
        if "entry_price" in args or "entry" in args:
            payload["entry_price"] = args.get("entry_price") or args.get("entry")
        
        if "stop_loss" in args or "sl" in args:
            payload["stop_loss"] = args.get("stop_loss") or args.get("sl")
        
        if "take_profit" in args or "tp" in args:
            payload["take_profit"] = args.get("take_profit") or args.get("tp")
        
        if "volume" in args:
            payload["volume"] = args.get("volume")
        
        if "conditions" in args:
            payload["conditions"] = args.get("conditions")
        
        if "expires_hours" in args:
            payload["expires_hours"] = args.get("expires_hours")
        
        if "notes" in args:
            payload["notes"] = args.get("notes")
        
        if not payload:
            return {
                "success": False,
                "error": "No update fields provided. Provide at least one of: entry_price, stop_loss, take_profit, volume, conditions, expires_hours, notes"
            }
        
        url = f"{API_BASE_URL}/auto-execution/update-plan/{plan_id}"
        status_code, text, parsed = await _http_request_json("POST", url, json_body=payload, timeout_seconds=30.0)
        if status_code == 200:
            data = parsed if parsed is not None else {}
            if isinstance(data, dict) and data.get("success"):
                return {"summary": f"SUCCESS: Auto Plan Updated: {plan_id}", "data": data}
            if isinstance(data, dict):
                return {"summary": f"ERROR: {data.get('message', 'Failed to update plan')}", "data": data}
            return {"summary": "ERROR: Failed to update plan", "data": {"error": text}}
        error_data = parsed if parsed is not None else {"error": text}
        return {"summary": f"ERROR: Failed to update plan: {status_code}", "data": error_data}
                
    except Exception as e:
        return {
            "summary": f"ERROR: Error updating plan: {str(e)}",
            "data": {"error": str(e)}
        }

async def tool_get_auto_plan_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get status of auto-executing trade plans. Can query by plan_id or ticket number."""
    
    try:
        plan_id = args.get("plan_id")
        ticket = args.get("ticket")
        
        # Validate that only one identifier is provided
        if plan_id and ticket:
            return {
                "summary": "ERROR: Provide either plan_id OR ticket, not both",
                "data": {"error": "Cannot specify both plan_id and ticket"}
            }
        
        url = f"{API_BASE_URL}/auto-execution/status"
        params = {"plan_id": plan_id, "ticket": ticket}
        status_code, text, parsed = await _http_request_json("GET", url, params=params, timeout_seconds=30.0)

        if status_code == 200:
            data = parsed if isinstance(parsed, dict) else {}
            if plan_id or ticket:
                plan_data = data.get("plan", {}) if isinstance(data, dict) else {}
                if plan_data:
                    plan_status = plan_data.get("status", "Unknown")
                    plan_id_found = plan_data.get("plan_id", "Unknown")
                    symbol = plan_data.get("symbol", "Unknown")
                    direction = plan_data.get("direction", "Unknown")
                    ticket_found = plan_data.get("ticket")

                    summary = f"Plan {plan_id_found}: {symbol} {direction} - Status: {plan_status}"
                    if ticket_found:
                        summary += f" (Ticket: {ticket_found})"
                    return {"summary": summary, "data": data}
                return {
                    "summary": "Plan not found" + (f" for ticket {ticket}" if ticket else f" for plan_id {plan_id}"),
                    "data": data,
                }

            plans = data.get("plans", []) if isinstance(data, dict) else []
            return {"summary": f"Auto Plans: {len(plans)} active plans", "data": data}

        return {"summary": f"ERROR: Failed to get plan status: {status_code}", "data": {"error": text}}
                
    except Exception as e:
        return {
            "summary": f"ERROR: Error getting plan status: {str(e)}",
            "data": {"error": str(e)}
        }

async def tool_get_auto_system_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get auto execution system status"""
    
    try:
        url = f"{API_BASE_URL}/auto-execution/system-status"
        status_code, text, parsed = await _http_request_json("GET", url, timeout_seconds=30.0)
        if status_code == 200:
            data = parsed if parsed is not None else {}
            if isinstance(data, dict):
                summary = f"Auto System: {data.get('status', 'Unknown')} - {data.get('pending_plans', 0)} plans"
            else:
                summary = "Auto System: OK"
            return {"summary": summary, "data": data}
        return {"summary": f"ERROR: Failed to get system status: {status_code}", "data": {"error": text}}
                
    except Exception as e:
        return {
            "summary": f"ERROR: Error getting system status: {str(e)}",
            "data": {"error": str(e)}
        }

# Batch operation tools
async def tool_create_multiple_auto_plans(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create multiple auto-executing trade plans in a single batch operation"""
    
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # CRITICAL: Input validation - structure only
        plans = args.get("plans")
        
        if plans is None:
            return {
                "summary": "ERROR: 'plans' parameter is required",
                "data": {
                    "error": "plans parameter is required",
                    "validation_errors": ["plans array is required"]
                }
            }
        
        if not isinstance(plans, list):
            return {
                "summary": "ERROR: 'plans' must be an array",
                "data": {
                    "error": "plans must be an array",
                    "validation_errors": [f"plans must be an array, got {type(plans).__name__}"]
                }
            }
        
        if len(plans) == 0:
            return {
                "summary": "ERROR: 'plans' array cannot be empty",
                "data": {
                    "error": "plans array cannot be empty",
                    "validation_errors": ["plans array must contain at least one plan"]
                }
            }
        
        if len(plans) > 20:
            return {
                "summary": "ERROR: 'plans' array cannot exceed 20 items",
                "data": {
                    "error": "plans array cannot exceed 20 items",
                    "validation_errors": [f"plans array has {len(plans)} items, maximum is 20"]
                }
            }
        
        # Call batch create API endpoint
        url = f"{API_BASE_URL}/auto-execution/create-plans"
        payload = {"plans": plans}
        
        logger.info(f"Calling batch create API: {url} with {len(plans)} plans")
        
        status_code, text, parsed = await _http_request_json("POST", url, json_body=payload, timeout_seconds=60.0)

        logger.info(f"Batch create API response status: {status_code}")

        if status_code == 200:
            data = parsed if isinstance(parsed, dict) else {}

            if not all(field in data for field in ["total", "successful", "failed", "results"]):
                return {
                    "summary": "ERROR: Invalid API response structure",
                    "data": {"error": "API response missing required fields", "response": data},
                }

            total = data.get("total", 0)
            successful = data.get("successful", 0)
            failed = data.get("failed", 0)

            if successful == total:
                summary = f"SUCCESS: Created {successful} of {total} plans successfully"
            elif successful > 0:
                summary = f"PARTIAL SUCCESS: Created {successful} of {total} plans ({failed} failed)"
            else:
                summary = f"ERROR: Failed to create all {total} plans"

            return {"summary": summary, "data": data}

        if status_code == 422:
            validation_errors = []
            if isinstance(parsed, dict) and "detail" in parsed:
                detail = parsed.get("detail")
                if isinstance(detail, list):
                    validation_errors = [str(err) for err in detail]
                else:
                    validation_errors = [str(detail)]
            if validation_errors:
                return {
                    "summary": f"ERROR: Validation failed: {', '.join(validation_errors[:3])}",
                    "data": {"error": "Validation error", "validation_errors": validation_errors, "status_code": 422},
                }
            return {"summary": "ERROR: Validation failed (422)", "data": {"error": text, "status_code": 422}}

        error_detail = None
        if isinstance(parsed, dict):
            error_detail = parsed.get("detail")
        if not error_detail:
            error_detail = text

        # Handle specific error cases
        if status_code == 503:
            # Service unavailable - likely database/queue locked
            error_summary = (
                f"Service temporarily unavailable (status {status_code}): "
                f"The execution queue may be locked during rollover/rebalancing/phase sync. "
                f"Please retry in a few seconds."
            )
        elif status_code >= 500:
            # Server error
            error_summary = (
                f"Server error (status {status_code}): {error_detail}. "
                f"This may be due to database locking or queue issues. Please retry."
            )
        else:
            error_summary = f"Failed to create plans: {status_code} - {error_detail}"
        
        logger.error(f"Batch create API returned error status {status_code}: {error_detail}")
        return {
            "summary": f"ERROR: {error_summary}",
            "data": {
                "error": error_detail,
                "status_code": status_code,
                "retry_recommended": status_code in [503, 500, 502, 504]
            },
        }
                
    except Exception as e:
        import traceback
        logger.error(f"Unexpected error in batch create: {e}", exc_info=True)
        return {
            "summary": f"ERROR: Error creating plans: {str(e)}",
            "data": {
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        }

async def tool_update_multiple_auto_plans(args: Dict[str, Any]) -> Dict[str, Any]:
    """Update multiple auto-executing trade plans in a single batch operation"""
    
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # CRITICAL: Input validation
        updates = args.get("updates")
        
        if updates is None:
            return {
                "summary": "ERROR: 'updates' parameter is required",
                "data": {
                    "error": "updates parameter is required",
                    "validation_errors": ["updates array is required"]
                }
            }
        
        if not isinstance(updates, list):
            return {
                "summary": "ERROR: 'updates' must be an array",
                "data": {
                    "error": "updates must be an array",
                    "validation_errors": [f"updates must be an array, got {type(updates).__name__}"]
                }
            }
        
        if len(updates) == 0:
            return {
                "summary": "ERROR: 'updates' array cannot be empty",
                "data": {
                    "error": "updates array cannot be empty",
                    "validation_errors": ["updates array must contain at least one update"]
                }
            }
        
        # CRITICAL: Deduplicate updates (keep last update for each plan_id)
        seen_plan_ids = {}
        deduplicated_updates = []
        
        for update in updates:
            plan_id = update.get("plan_id")
            if plan_id and plan_id in seen_plan_ids:
                logger.warning(f"Duplicate plan_id found in updates: {plan_id}, keeping last update")
                # Remove previous occurrence
                deduplicated_updates = [u for u in deduplicated_updates if u.get("plan_id") != plan_id]
            
            if plan_id:
                seen_plan_ids[plan_id] = True
            deduplicated_updates.append(update)
        
        if len(deduplicated_updates) < len(updates):
            logger.info(f"Deduplicated {len(updates)} updates to {len(deduplicated_updates)} unique updates")
        
        # Call batch update API endpoint
        url = f"{API_BASE_URL}/auto-execution/update-plans"
        payload = {"updates": deduplicated_updates}
        
        logger.info(f"Calling batch update API: {url} with {len(deduplicated_updates)} updates")
        
        status_code, text, parsed = await _http_request_json("POST", url, json_body=payload, timeout_seconds=60.0)

        logger.info(f"Batch update API response status: {status_code}")

        if status_code == 200:
            data = parsed if isinstance(parsed, dict) else {}
            if not all(field in data for field in ["total", "successful", "failed", "results"]):
                return {
                    "summary": "ERROR: Invalid API response structure",
                    "data": {"error": "API response missing required fields", "response": data},
                }

            total = data.get("total", 0)
            successful = data.get("successful", 0)
            failed = data.get("failed", 0)

            if successful == total:
                summary = f"SUCCESS: Updated {successful} of {total} plans successfully"
            elif successful > 0:
                summary = f"PARTIAL SUCCESS: Updated {successful} of {total} plans ({failed} failed)"
            else:
                summary = f"ERROR: Failed to update all {total} plans"

            return {"summary": summary, "data": data}

        if status_code == 422:
            validation_errors = []
            if isinstance(parsed, dict) and "detail" in parsed:
                detail = parsed.get("detail")
                if isinstance(detail, list):
                    validation_errors = [str(err) for err in detail]
                else:
                    validation_errors = [str(detail)]
            if validation_errors:
                return {
                    "summary": f"ERROR: Validation failed: {', '.join(validation_errors[:3])}",
                    "data": {"error": "Validation error", "validation_errors": validation_errors, "status_code": 422},
                }
            return {"summary": "ERROR: Validation failed (422)", "data": {"error": text, "status_code": 422}}

        error_detail = None
        if isinstance(parsed, dict):
            error_detail = parsed.get("detail")
        if not error_detail:
            error_detail = text

        logger.error(f"Batch update API returned error status {status_code}: {error_detail}")
        return {
            "summary": f"ERROR: Failed to update plans: {status_code} - {error_detail}",
            "data": {"error": error_detail, "status_code": status_code},
        }
                
    except Exception as e:
        import traceback
        logger.error(f"Unexpected error in batch update: {e}", exc_info=True)
        return {
            "summary": f"ERROR: Error updating plans: {str(e)}",
            "data": {
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        }

async def tool_re_evaluate_plan(args: Dict[str, Any]) -> Dict[str, Any]:
    """Re-evaluate an auto-execution trade plan based on current market conditions (Phase 4)"""
    
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        plan_id = args.get("plan_id")
        if not plan_id:
            return {
                "summary": "ERROR: plan_id is required",
                "data": {"error": "plan_id parameter is required"}
            }
        
        force = args.get("force", False)
        
        url = f"{API_BASE_URL}/auto-execution/plan/{plan_id}/re-evaluate"
        status_code, text, parsed = await _http_request_json(
            "POST",
            url,
            params={"force": force},
            headers={"X-API-Key": "chatgpt"},
            timeout_seconds=30.0,
        )

        if status_code == 200 and isinstance(parsed, dict):
            result = parsed
            re_eval_result = result.get("re_evaluation_result", {}) if isinstance(result, dict) else {}

            action = re_eval_result.get("action", "keep")
            recommendation = re_eval_result.get("recommendation", "No action needed")
            available = re_eval_result.get("available", False)

            summary = f"Plan {plan_id} re-evaluation: {str(action).upper()}\n{recommendation}"
            if not available and not force:
                summary += "\n⚠️ Re-evaluation not available (in cooldown or daily limit reached). Use force=true to bypass."

            return {
                "summary": summary,
                "data": {
                    "plan_id": plan_id,
                    "action": action,
                    "recommendation": recommendation,
                    "available": available,
                    "last_re_evaluation": re_eval_result.get("last_re_evaluation"),
                    "re_evaluation_count_today": re_eval_result.get("re_evaluation_count_today", 0),
                },
            }

        if status_code == 404:
            return {"summary": f"ERROR: Plan {plan_id} not found", "data": {"error": f"Plan {plan_id} not found"}}

        logger.error(f"Re-evaluation API error: {status_code} - {text}")
        return {"summary": f"ERROR: Failed to re-evaluate plan: {text[:200]}", "data": {"error": text, "status_code": status_code}}
                
    except Exception as e:
        logger.error(f"Error re-evaluating plan: {e}", exc_info=True)
        return {
            "summary": f"ERROR: Failed to re-evaluate plan: {str(e)}",
            "data": {"error": str(e)}
        }

async def tool_cancel_multiple_auto_plans(args: Dict[str, Any]) -> Dict[str, Any]:
    """Cancel multiple auto-executing trade plans in a single batch operation"""
    
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # CRITICAL: Input validation
        plan_ids = args.get("plan_ids")
        
        if plan_ids is None:
            return {
                "summary": "ERROR: 'plan_ids' parameter is required",
                "data": {
                    "error": "plan_ids parameter is required",
                    "validation_errors": ["plan_ids array is required"]
                }
            }
        
        if not isinstance(plan_ids, list):
            return {
                "summary": "ERROR: 'plan_ids' must be an array",
                "data": {
                    "error": "plan_ids must be an array",
                    "validation_errors": [f"plan_ids must be an array, got {type(plan_ids).__name__}"]
                }
            }
        
        if len(plan_ids) == 0:
            return {
                "summary": "ERROR: 'plan_ids' array cannot be empty",
                "data": {
                    "error": "plan_ids array cannot be empty",
                    "validation_errors": ["plan_ids array must contain at least one plan_id"]
                }
            }
        
        # CRITICAL: Deduplicate plan_ids (keep first occurrence)
        seen_plan_ids = set()
        deduplicated_plan_ids = []
        
        for plan_id in plan_ids:
            if not isinstance(plan_id, str):
                logger.warning(f"Invalid plan_id type: {type(plan_id).__name__}, skipping")
                continue
            
            if plan_id not in seen_plan_ids:
                seen_plan_ids.add(plan_id)
                deduplicated_plan_ids.append(plan_id)
            else:
                logger.warning(f"Duplicate plan_id found: {plan_id}, skipping duplicate")
        
        if len(deduplicated_plan_ids) < len(plan_ids):
            logger.info(f"Deduplicated {len(plan_ids)} plan_ids to {len(deduplicated_plan_ids)} unique plan_ids")
        
        if len(deduplicated_plan_ids) == 0:
            return {
                "summary": "ERROR: No valid plan_ids after deduplication",
                "data": {
                    "error": "No valid plan_ids provided",
                    "validation_errors": ["All plan_ids were invalid or duplicates"]
                }
            }
        
        # Call batch cancel API endpoint
        url = f"{API_BASE_URL}/auto-execution/cancel-plans"
        payload = {"plan_ids": deduplicated_plan_ids}
        
        logger.info(f"Calling batch cancel API: {url} with {len(deduplicated_plan_ids)} plan_ids")
        
        status_code, text, parsed = await _http_request_json("POST", url, json_body=payload, timeout_seconds=60.0)

        logger.info(f"Batch cancel API response status: {status_code}")

        if status_code == 200:
            data = parsed if isinstance(parsed, dict) else {}
            if not all(field in data for field in ["total", "successful", "failed", "results"]):
                return {
                    "summary": "ERROR: Invalid API response structure",
                    "data": {"error": "API response missing required fields", "response": data},
                }

            total = data.get("total", 0)
            successful = data.get("successful", 0)
            failed = data.get("failed", 0)

            if successful == total:
                summary = f"SUCCESS: Cancelled {successful} of {total} plans successfully"
            elif successful > 0:
                summary = f"PARTIAL SUCCESS: Cancelled {successful} of {total} plans ({failed} failed)"
            else:
                summary = f"ERROR: Failed to cancel all {total} plans"

            return {"summary": summary, "data": data}

        if status_code == 422:
            validation_errors = []
            if isinstance(parsed, dict) and "detail" in parsed:
                detail = parsed.get("detail")
                if isinstance(detail, list):
                    validation_errors = [str(err) for err in detail]
                else:
                    validation_errors = [str(detail)]
            if validation_errors:
                return {
                    "summary": f"ERROR: Validation failed: {', '.join(validation_errors[:3])}",
                    "data": {"error": "Validation error", "validation_errors": validation_errors, "status_code": 422},
                }
            return {"summary": "ERROR: Validation failed (422)", "data": {"error": text, "status_code": 422}}

        error_detail = None
        if isinstance(parsed, dict):
            error_detail = parsed.get("detail")
        if not error_detail:
            error_detail = text

        logger.error(f"Batch cancel API returned error status {status_code}: {error_detail}")
        return {
            "summary": f"ERROR: Failed to cancel plans: {status_code} - {error_detail}",
            "data": {"error": error_detail, "status_code": status_code},
        }
                
    except Exception as e:
        import traceback
        logger.error(f"Unexpected error in batch cancel: {e}", exc_info=True)
        return {
            "summary": f"ERROR: Error cancelling plans: {str(e)}",
            "data": {
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        }
