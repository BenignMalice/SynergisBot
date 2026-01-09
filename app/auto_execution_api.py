"""
Auto Execution API Endpoints
Provides API endpoints for ChatGPT to create and manage trade plans.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, validator
from typing import Dict, Any, Optional, List
import logging
from chatgpt_auto_execution_integration import get_chatgpt_auto_execution
from auto_execution_system import get_auto_execution_system
from infra.tolerance_helper import get_price_tolerance

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auto-execution", tags=["Auto Execution"])

# Dependency to verify API key
def verify_api_key():
    # TODO: Implement API key verification
    return True

class TradePlanRequest(BaseModel):
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float = 0.01
    conditions: Optional[Dict[str, Any]] = None
    expires_hours: int = 24
    notes: Optional[str] = None
    entry_levels: Optional[List[Dict[str, Any]]] = None  # Phase 2: Multi-level entry support

class CHOCHPlanRequest(BaseModel):
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float = 0.01
    choch_type: str = "bear"  # "bear" or "bull"
    price_tolerance: Optional[float] = None  # Auto-calculated based on symbol if None
    expires_hours: int = 24
    notes: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None  # Additional conditions (e.g., m1_choch_bos_combo, min_volatility, bb_width_threshold)

class RejectionWickPlanRequest(BaseModel):
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float = 0.01
    price_tolerance: Optional[float] = None  # Auto-calculated based on symbol if None
    expires_hours: int = 24
    notes: Optional[str] = None

class PriceBreakoutPlanRequest(BaseModel):
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float = 0.01
    breakout_type: str = "above"  # "above" or "below"
    expires_hours: int = 24
    notes: Optional[str] = None

class MicroScalpPlanRequest(BaseModel):
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float = 0.01
    expires_hours: int = 2  # Default 2 hours for micro-scalps (ultra-short-term)
    notes: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None  # Optional conditions from ChatGPT

class RangeScalpPlanRequest(BaseModel):
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float = 0.01
    min_confluence: int = 80  # Minimum confluence score required
    price_tolerance: Optional[float] = None  # Auto-calculated if None
    expires_hours: int = 8  # Default 8 hours for range scalping
    notes: Optional[str] = None

class OrderBlockPlanRequest(BaseModel):
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float = 0.01
    order_block_type: str = "auto"  # "bull", "bear", or "auto"
    min_validation_score: int = 60  # Minimum validation score (0-100)
    price_tolerance: Optional[float] = None  # Auto-calculated if None
    expires_hours: int = 24
    notes: Optional[str] = None

class BracketTradePlanRequest(BaseModel):
    symbol: str
    buy_entry: float
    buy_sl: float
    buy_tp: float
    sell_entry: float
    sell_sl: float
    sell_tp: float
    volume: float = 0.01
    conditions: Optional[Dict[str, Any]] = None  # Optional conditions for both sides
    expires_hours: int = 24
    notes: Optional[str] = None

@router.post("/create-plan", dependencies=[Depends(verify_api_key)])
async def create_trade_plan(request: TradePlanRequest):
    """Create a general trade plan for auto execution"""
    try:
        logger.info(f"Received create-plan request: symbol={request.symbol}, direction={request.direction}, entry={request.entry_price}")
        
        auto_execution = get_chatgpt_auto_execution()
        logger.debug(f"Auto-execution instance retrieved: {type(auto_execution)}")
        
        result = auto_execution.create_trade_plan(
            symbol=request.symbol,
            direction=request.direction,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            volume=request.volume,
            conditions=request.conditions,
            expires_hours=request.expires_hours,
            notes=request.notes,
            entry_levels=request.entry_levels  # Phase 2: Multi-level entry support
        )
        
        logger.info(f"Plan creation result: success={result.get('success')}, plan_id={result.get('plan_id')}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error creating trade plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create trade plan: {str(e)}")

@router.post("/create-choch-plan", dependencies=[Depends(verify_api_key)])
async def create_choch_plan(request: CHOCHPlanRequest):
    """Create a CHOCH-based trade plan for auto execution"""
    try:
        auto_execution = get_chatgpt_auto_execution()
        
        # Auto-calculate tolerance if not provided
        price_tolerance = request.price_tolerance
        if price_tolerance is None:
            price_tolerance = get_price_tolerance(request.symbol)
        
        result = auto_execution.create_choch_plan(
            symbol=request.symbol,
            direction=request.direction,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            volume=request.volume,
            choch_type=request.choch_type,
            price_tolerance=price_tolerance,
            expires_hours=request.expires_hours,
            notes=request.notes,
            additional_conditions=request.conditions  # Pass additional conditions
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create CHOCH plan: {str(e)}")

@router.post("/create-rejection-wick-plan", dependencies=[Depends(verify_api_key)])
async def create_rejection_wick_plan(request: RejectionWickPlanRequest):
    """Create a rejection wick-based trade plan for auto execution"""
    try:
        auto_execution = get_chatgpt_auto_execution()
        
        # Auto-calculate tolerance if not provided
        price_tolerance = request.price_tolerance
        if price_tolerance is None:
            price_tolerance = get_price_tolerance(request.symbol)
        
        result = auto_execution.create_rejection_wick_plan(
            symbol=request.symbol,
            direction=request.direction,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            volume=request.volume,
            price_tolerance=price_tolerance,
            expires_hours=request.expires_hours,
            notes=request.notes
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create rejection wick plan: {str(e)}")

@router.post("/create-price-breakout-plan", dependencies=[Depends(verify_api_key)])
async def create_price_breakout_plan(request: PriceBreakoutPlanRequest):
    """Create a price breakout-based trade plan for auto execution"""
    try:
        auto_execution = get_chatgpt_auto_execution()
        
        result = auto_execution.create_price_breakout_plan(
            symbol=request.symbol,
            direction=request.direction,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            volume=request.volume,
            breakout_type=request.breakout_type,
            expires_hours=request.expires_hours,
            notes=request.notes
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create price breakout plan: {str(e)}")

@router.post("/create-micro-scalp-plan", dependencies=[Depends(verify_api_key)])
async def create_micro_scalp_plan(request: MicroScalpPlanRequest):
    """Create a micro-scalp auto-execution plan for ultra-short-term trading"""
    try:
        auto_execution = get_chatgpt_auto_execution()
        
        result = auto_execution.create_micro_scalp_plan(
            symbol=request.symbol,
            direction=request.direction,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            volume=request.volume,
            expires_hours=request.expires_hours,
            notes=request.notes,
            conditions=request.conditions
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create micro-scalp plan: {str(e)}")

@router.post("/create-range-scalp-plan", dependencies=[Depends(verify_api_key)])
async def create_range_scalp_plan(request: RangeScalpPlanRequest):
    """Create a range scalping auto-execution plan"""
    try:
        auto_execution = get_chatgpt_auto_execution()
        
        result = auto_execution.create_range_scalp_plan(
            symbol=request.symbol,
            direction=request.direction,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            volume=request.volume,
            min_confluence=request.min_confluence,
            price_tolerance=request.price_tolerance,
            expires_hours=request.expires_hours,
            notes=request.notes
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create range scalp plan: {str(e)}")

@router.post("/create-order-block-plan", dependencies=[Depends(verify_api_key)])
async def create_order_block_plan(request: OrderBlockPlanRequest):
    """Create an order block-based trade plan for auto execution"""
    try:
        auto_execution = get_chatgpt_auto_execution()
        
        # Auto-calculate tolerance if not provided
        price_tolerance = request.price_tolerance
        if price_tolerance is None:
            price_tolerance = get_price_tolerance(request.symbol)
        
        result = auto_execution.create_order_block_plan(
            symbol=request.symbol,
            direction=request.direction,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            volume=request.volume,
            order_block_type=request.order_block_type,
            min_validation_score=request.min_validation_score,
            price_tolerance=price_tolerance,
            expires_hours=request.expires_hours,
            notes=request.notes
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create order block plan: {str(e)}")

@router.post("/create-bracket-trade-plan", dependencies=[Depends(verify_api_key)])
async def create_bracket_trade_plan(request: BracketTradePlanRequest):
    """Create a bracket trade plan (OCO - One Cancels Other) for auto execution"""
    try:
        auto_execution = get_chatgpt_auto_execution()
        
        result = auto_execution.create_bracket_trade_plan(
            symbol=request.symbol,
            buy_entry=request.buy_entry,
            buy_sl=request.buy_sl,
            buy_tp=request.buy_tp,
            sell_entry=request.sell_entry,
            sell_sl=request.sell_sl,
            sell_tp=request.sell_tp,
            volume=request.volume,
            conditions=request.conditions,
            expires_hours=request.expires_hours,
            notes=request.notes
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create bracket trade plan: {str(e)}")

@router.post("/cancel-plan/{plan_id}", dependencies=[Depends(verify_api_key)])
async def cancel_plan(plan_id: str):
    """Cancel a trade plan (optimized for fast response)"""
    try:
        auto_execution = get_chatgpt_auto_execution()
        
        # Cancel plan (now optimized to minimize lock time)
        result = auto_execution.cancel_plan(plan_id)
        
        if result:
            return {"success": True, "message": f"Plan {plan_id} cancelled successfully"}
        else:
            # Plan may not exist or already cancelled - still return success
            # (idempotent operation)
            return {"success": True, "message": f"Plan {plan_id} not found or already cancelled"}
        
    except Exception as e:
        logger.error(f"Error cancelling plan {plan_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cancel plan: {str(e)}")

class UpdatePlanRequest(BaseModel):
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    volume: Optional[float] = None
    conditions: Optional[Dict[str, Any]] = None
    expires_hours: Optional[int] = None
    notes: Optional[str] = None

# Batch operation request models
class BatchCreatePlanRequest(BaseModel):
    plans: List[Dict[str, Any]]  # Use Dict for flexibility with different plan types
    symbols: Optional[str] = None  # Optional top-level symbol (used if plan doesn't have symbol field)
    min_confluence: Optional[int] = None  # Optional top-level min_confluence (for backward compatibility)
    price_tolerance: Optional[float] = None  # Optional top-level price_tolerance (for backward compatibility)
    
    @validator('plans')
    def validate_plans_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('plans array cannot be empty')
        if len(v) > 20:
            raise ValueError('plans array cannot exceed 20 items')
        return v

class BatchUpdatePlanRequest(BaseModel):
    updates: List[Dict[str, Any]]
    
    @validator('updates')
    def validate_updates_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('updates array cannot be empty')
        return v

class BatchCancelPlanRequest(BaseModel):
    plan_ids: List[str]
    
    @validator('plan_ids')
    def validate_plan_ids_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('plan_ids array cannot be empty')
        return v

@router.post("/update-plan/{plan_id}", dependencies=[Depends(verify_api_key)])
async def update_plan(plan_id: str, request: UpdatePlanRequest):
    """Update an existing trade plan (only pending plans can be updated)"""
    try:
        auto_execution = get_chatgpt_auto_execution()
        
        result = auto_execution.update_plan(
            plan_id=plan_id,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            volume=request.volume,
            conditions=request.conditions,
            expires_hours=request.expires_hours,
            notes=request.notes
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update plan: {str(e)}")

@router.get("/status", dependencies=[Depends(verify_api_key)])
async def get_status(plan_id: Optional[str] = None, ticket: Optional[int] = None, include_all: bool = False):
    """Get status of trade plans (default: pending only). Can query by plan_id or ticket number."""
    try:
        auto_execution = get_chatgpt_auto_execution()
        
        # If ticket is provided, look up plan_id first
        if ticket and not plan_id:
            import sqlite3
            from pathlib import Path
            db_path = Path("data/auto_execution.db")
            if db_path.exists():
                with sqlite3.connect(str(db_path), timeout=5.0) as conn:
                    cursor = conn.execute("SELECT plan_id FROM trade_plans WHERE ticket = ?", (ticket,))
                    row = cursor.fetchone()
                    if row:
                        plan_id = row[0]
                    else:
                        return {
                            "success": False,
                            "message": f"No auto-execution plan found for ticket {ticket}"
                        }
            else:
                return {
                    "success": False,
                    "message": "Database not found"
                }
        
        result = auto_execution.get_plan_status(plan_id=plan_id, include_all_statuses=include_all)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@router.get("/system-status", dependencies=[Depends(verify_api_key)])
async def get_system_status():
    """Get auto execution system status"""
    try:
        auto_system = get_auto_execution_system()
        
        status = auto_system.get_status()
        
        return {
            "success": True,
            "system_status": status
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system status: {str(e)}")

@router.get("/plan/{plan_id}/zone-status", dependencies=[Depends(verify_api_key)])
async def get_plan_zone_status(plan_id: str):
    """Get tolerance zone status for a specific plan (Phase 1)"""
    try:
        auto_system = get_auto_execution_system()
        
        # Get plan
        plan = auto_system.get_plan_by_id(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
        
        # Get zone status
        zone_status = auto_system.get_plan_zone_status(plan)
        
        if not zone_status.get("success"):
            raise HTTPException(
                status_code=500,
                detail=zone_status.get("error", "Failed to get zone status")
            )
        
        return {
            "success": True,
            "zone_status": zone_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get zone status: {str(e)}")

@router.get("/plan/{plan_id}/cancellation-status", dependencies=[Depends(verify_api_key)])
async def get_plan_cancellation_status(plan_id: str):
    """Get cancellation status for a specific plan (Phase 3)"""
    try:
        auto_system = get_auto_execution_system()
        auto_execution = get_chatgpt_auto_execution()
        
        # Get plan
        plan = auto_system.get_plan_by_id(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
        
        # Calculate cancellation risk
        cancellation_info = auto_execution._calculate_cancellation_risk(plan)
        
        return {
            "success": True,
            "plan_id": plan_id,
            "status": plan.status,
            "cancellation_reason": getattr(plan, 'cancellation_reason', None),
            "last_cancellation_check": getattr(plan, 'last_cancellation_check', None),
            "cancellation_risk": cancellation_info.get("risk", 0.0) if cancellation_info else 0.0,
            "cancellation_reasons": cancellation_info.get("reasons", []) if cancellation_info else [],
            "cancellation_priority": cancellation_info.get("priority") if cancellation_info else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cancellation status: {str(e)}")

@router.get("/plan/{plan_id}/re-evaluation-status", dependencies=[Depends(verify_api_key)])
async def get_plan_re_evaluation_status(plan_id: str):
    """Get re-evaluation status for a specific plan (Phase 4)"""
    try:
        auto_system = get_auto_execution_system()
        
        # Get plan
        plan = auto_system.get_plan_by_id(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
        
        # Get re-evaluation status
        re_eval_status = auto_system.get_plan_re_evaluation_status(plan)
        
        if not re_eval_status.get("success"):
            raise HTTPException(
                status_code=500,
                detail=re_eval_status.get("error", "Failed to get re-evaluation status")
            )
        
        return {
            "success": True,
            "plan_id": plan_id,
            "re_evaluation_status": re_eval_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get re-evaluation status: {str(e)}")

@router.post("/plan/{plan_id}/re-evaluate", dependencies=[Depends(verify_api_key)])
async def re_evaluate_plan(plan_id: str, force: bool = False):
    """Manually trigger re-evaluation of a plan (Phase 4)"""
    try:
        auto_system = get_auto_execution_system()
        
        # Get plan
        plan = auto_system.get_plan_by_id(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
        
        # Re-evaluate plan
        result = auto_system._re_evaluate_plan(plan, force=force)
        
        return {
            "success": True,
            "plan_id": plan_id,
            "re_evaluation_result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to re-evaluate plan: {str(e)}")

@router.get("/metrics", dependencies=[Depends(verify_api_key)])
async def get_metrics():
    """Get auto execution system metrics (Phase 1)"""
    try:
        auto_system = get_auto_execution_system()
        
        # Get system status
        status = auto_system.get_status(include_all_statuses=True)
        
        # Calculate metrics
        plans = status.get("plans", [])
        
        # Zone metrics
        plans_in_zone = 0
        plans_with_zone_entry = 0
        total_price_distance = 0.0
        plans_with_distance = 0
        
        for plan_dict in plans:
            # Check if plan has zone tracking
            if plan_dict.get("zone_entry_tracked"):
                plans_with_zone_entry += 1
            
            # Try to get zone status for pending plans
            if plan_dict.get("status") == "pending":
                try:
                    plan = auto_system.get_plan_by_id(plan_dict.get("plan_id"))
                    if plan:
                        zone_status = auto_system.get_plan_zone_status(plan)
                        if zone_status.get("success"):
                            if zone_status.get("in_tolerance_zone"):
                                plans_in_zone += 1
                            
                            distance = zone_status.get("price_distance_from_entry")
                            if distance is not None:
                                total_price_distance += distance
                                plans_with_distance += 1
                except Exception as e:
                    logger.debug(f"Error getting zone status for metrics: {e}")
        
        avg_price_distance = (
            total_price_distance / plans_with_distance
            if plans_with_distance > 0
            else 0.0
        )
        
        # Write queue metrics (if available)
        queue_stats = {}
        if auto_system.db_write_queue:
            queue_stats = auto_system.db_write_queue.get_queue_stats()
        
        return {
            "success": True,
            "metrics": {
                "total_plans": len(plans),
                "pending_plans": status.get("pending_plans", 0),
                "plans_in_tolerance_zone": plans_in_zone,
                "plans_with_zone_entry": plans_with_zone_entry,
                "average_price_distance_from_entry": avg_price_distance,
                "write_queue": queue_stats
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

# Batch operation endpoints
@router.post("/create-plans", dependencies=[Depends(verify_api_key)])
async def create_multiple_plans(request: BatchCreatePlanRequest):
    """Create multiple trade plans in a single batch operation"""
    try:
        auto_execution = get_chatgpt_auto_execution()
        
        # Check if auto execution system is available
        if not auto_execution or not auto_execution.auto_system:
            logger.error("Auto execution system not available")
            raise HTTPException(
                status_code=503,
                detail="Auto execution system not available. System may be initializing or restarting."
            )
        
        results = []
        successful = 0
        failed = 0
        
        # Valid plan types mapping
        VALID_PLAN_TYPES = {
            "auto_trade": "create_trade_plan",
            "choch": "create_choch_plan",
            "rejection_wick": "create_rejection_wick_plan",
            "order_block": "create_order_block_plan",
            "range_scalp": "create_range_scalp_plan",
            "micro_scalp": "create_micro_scalp_plan"
        }
        
        # Process each plan sequentially
        for index, plan in enumerate(request.plans):
            plan_type = plan.get("plan_type")
            # Get symbol from plan, or fall back to top-level symbols field
            symbol = plan.get("symbol") or request.symbols or ""
            
            # Validate symbol is present
            if not symbol:
                results.append({
                    "index": index,
                    "status": "failed",
                    "error": "symbol is required (provide in plan or in top-level 'symbols' field)",
                    "plan_type": plan_type,
                    "symbol": None
                })
                failed += 1
                logger.warning(f"Plan {index}: Missing symbol")
                continue
            
            # Validate plan_type
            if not plan_type:
                results.append({
                    "index": index,
                    "status": "failed",
                    "error": "plan_type is required",
                    "plan_type": None,
                    "symbol": symbol
                })
                failed += 1
                logger.warning(f"Plan {index}: Missing plan_type")
                continue
            
            if plan_type not in VALID_PLAN_TYPES:
                valid_types = ", ".join(VALID_PLAN_TYPES.keys())
                results.append({
                    "index": index,
                    "status": "failed",
                    "error": f"Invalid plan_type: {plan_type}. Valid types: {valid_types}",
                    "plan_type": plan_type,
                    "symbol": symbol
                })
                failed += 1
                logger.warning(f"Plan {index}: Invalid plan_type '{plan_type}'")
                continue
            
            # Route to appropriate creation method
            try:
                method_name = VALID_PLAN_TYPES[plan_type]
                method = getattr(auto_execution, method_name)
                
                # Extract parameters based on plan_type
                # Handle parameter name mapping: ChatGPT may send "entry" but endpoint expects "entry_price"
                entry_price = plan.get("entry_price") or plan.get("entry")
                
                # Extract entry_levels if present
                entry_levels = plan.get("entry_levels")
                
                if plan_type == "auto_trade":
                    result = method(
                        symbol=symbol,  # Use extracted symbol (from plan or top-level)
                        direction=plan.get("direction"),
                        entry_price=entry_price,
                        stop_loss=plan.get("stop_loss"),
                        take_profit=plan.get("take_profit"),
                        volume=plan.get("volume", 0.01),
                        conditions=plan.get("conditions"),
                        expires_hours=plan.get("expires_hours", 24),
                        notes=plan.get("notes"),
                        entry_levels=entry_levels  # Phase 2: Multi-level entry support
                    )
                elif plan_type == "choch":
                    result = method(
                        symbol=symbol,  # Use extracted symbol
                        direction=plan.get("direction"),
                        entry_price=entry_price,
                        stop_loss=plan.get("stop_loss"),
                        take_profit=plan.get("take_profit"),
                        volume=plan.get("volume", 0.01),
                        choch_type=plan.get("choch_type", "bear"),
                        price_tolerance=plan.get("price_tolerance") or request.price_tolerance,
                        expires_hours=plan.get("expires_hours", 24),
                        notes=plan.get("notes"),
                        additional_conditions=plan.get("conditions"),
                        entry_levels=entry_levels  # Phase 2: Multi-level entry support
                    )
                elif plan_type == "rejection_wick":
                    result = method(
                        symbol=symbol,  # Use extracted symbol
                        direction=plan.get("direction"),
                        entry_price=entry_price,
                        stop_loss=plan.get("stop_loss"),
                        take_profit=plan.get("take_profit"),
                        volume=plan.get("volume", 0.01),
                        price_tolerance=plan.get("price_tolerance") or request.price_tolerance,
                        expires_hours=plan.get("expires_hours", 24),
                        notes=plan.get("notes"),
                        entry_levels=entry_levels,  # Phase 2: Multi-level entry support
                        additional_conditions=plan.get("conditions")  # Merge conditions from request
                    )
                elif plan_type == "order_block":
                    result = method(
                        symbol=symbol,  # Use extracted symbol
                        direction=plan.get("direction"),
                        entry_price=entry_price,
                        stop_loss=plan.get("stop_loss"),
                        take_profit=plan.get("take_profit"),
                        volume=plan.get("volume", 0.01),
                        order_block_type=plan.get("order_block_type", "auto"),
                        min_validation_score=plan.get("min_validation_score", 60),
                        price_tolerance=plan.get("price_tolerance") or request.price_tolerance,
                        expires_hours=plan.get("expires_hours", 24),
                        notes=plan.get("notes"),
                        entry_levels=entry_levels  # Phase 2: Multi-level entry support
                    )
                elif plan_type == "range_scalp":
                    result = method(
                        symbol=symbol,  # Use extracted symbol
                        direction=plan.get("direction"),
                        entry_price=entry_price,
                        stop_loss=plan.get("stop_loss"),
                        take_profit=plan.get("take_profit"),
                        volume=plan.get("volume", 0.01),
                        min_confluence=plan.get("min_confluence") or request.min_confluence or 80,
                        price_tolerance=plan.get("price_tolerance") or request.price_tolerance,
                        expires_hours=plan.get("expires_hours", 8),
                        notes=plan.get("notes"),
                        entry_levels=entry_levels  # Phase 2: Multi-level entry support
                    )
                elif plan_type == "micro_scalp":
                    result = method(
                        symbol=symbol,  # Use extracted symbol
                        direction=plan.get("direction"),
                        entry_price=entry_price,
                        stop_loss=plan.get("stop_loss"),
                        take_profit=plan.get("take_profit"),
                        volume=plan.get("volume", 0.01),
                        expires_hours=plan.get("expires_hours", 2),
                        notes=plan.get("notes"),
                        conditions=plan.get("conditions"),
                        entry_levels=entry_levels  # Phase 2: Multi-level entry support
                    )
                
                # Log creation attempt
                logger.info(f"Plan {index} ({plan_type}): symbol={symbol}, direction={plan.get('direction')}, success={result.get('success')}")
                
                # Process result
                if result.get("success"):
                    results.append({
                        "index": index,
                        "status": "created",
                        "plan_id": result.get("plan_id"),
                        "plan_type": plan_type,
                        "symbol": symbol,
                        "direction": plan.get("direction")
                    })
                    successful += 1
                else:
                    error_msg = result.get("message", "Unknown error")
                    results.append({
                        "index": index,
                        "status": "failed",
                        "error": error_msg,
                        "plan_type": plan_type,
                        "symbol": symbol
                    })
                    failed += 1
                    logger.warning(f"Plan {index} ({plan_type}): Failed - {error_msg}")
                    
            except HTTPException as e:
                # Handle HTTPException from individual methods
                error_msg = e.detail if hasattr(e, 'detail') else str(e)
                results.append({
                    "index": index,
                    "status": "failed",
                    "error": error_msg,
                    "plan_type": plan_type,
                    "symbol": symbol
                })
                failed += 1
                logger.error(f"Plan {index} ({plan_type}): HTTPException - {error_msg}", exc_info=True)
            except Exception as e:
                # Handle any other exceptions
                error_msg = str(e)
                results.append({
                    "index": index,
                    "status": "failed",
                    "error": error_msg,
                    "plan_type": plan_type,
                    "symbol": symbol
                })
                failed += 1
                logger.error(f"Plan {index} ({plan_type}): Exception - {error_msg}", exc_info=True)
        
        total = len(request.plans)
        logger.info(f"Batch create completed: total={total}, successful={successful}, failed={failed}")
        
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "results": results
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        error_msg = str(e)
        error_lower = error_msg.lower()
        
        # Check for specific error conditions
        if "locked" in error_lower or "database is locked" in error_lower:
            logger.error(f"Database locked during batch create: {e}", exc_info=True)
            raise HTTPException(
                status_code=503,
                detail=(
                    "Database is currently locked (likely during rollover/rebalancing/phase sync). "
                    "Please retry in a few seconds. If this persists, the system may be performing maintenance."
                )
            )
        elif "queue" in error_lower and ("full" in error_lower or "locked" in error_lower):
            logger.error(f"Queue issue during batch create: {e}", exc_info=True)
            raise HTTPException(
                status_code=503,
                detail=(
                    "Execution queue is currently full or locked (likely during phase sync or maintenance). "
                    "Please retry in a few seconds."
                )
            )
        else:
            logger.error(f"Error in batch create endpoint: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process batch create: {error_msg}"
            )

@router.post("/update-plans", dependencies=[Depends(verify_api_key)])
async def update_multiple_plans(request: BatchUpdatePlanRequest):
    """Update multiple trade plans in a single batch operation"""
    try:
        auto_execution = get_chatgpt_auto_execution()
        results = []
        successful = 0
        failed = 0
        
        # Track original order before deduplication
        original_order = {}  # Maps plan_id to list of original indices
        deduplicated_updates = []
        
        # Deduplicate updates (keep last update for each plan_id)
        seen_plan_ids = {}
        for idx, update in enumerate(request.updates):
            plan_id = update.get("plan_id")
            if not plan_id:
                # Missing plan_id - will be handled in validation
                deduplicated_updates.append((idx, update))
                continue
            
            if plan_id in seen_plan_ids:
                # Duplicate found - keep the last one
                logger.warning(f"Duplicate plan_id found: {plan_id}, keeping last update")
                # Remove previous occurrence
                deduplicated_updates = [item for item in deduplicated_updates if item[1].get("plan_id") != plan_id]
            
            seen_plan_ids[plan_id] = idx
            if plan_id not in original_order:
                original_order[plan_id] = []
            original_order[plan_id].append(idx)
            deduplicated_updates.append((idx, update))
        
        # Process each update sequentially
        for original_idx, update in deduplicated_updates:
            plan_id = update.get("plan_id")
            
            # Validate plan_id exists
            if not plan_id:
                results.append({
                    "plan_id": None,
                    "status": "failed",
                    "error": "plan_id is required"
                })
                failed += 1
                logger.warning(f"Update {original_idx}: Missing plan_id")
                continue
            
            # Validate at least one update field is provided
            update_fields = ["entry_price", "stop_loss", "take_profit", "volume", "conditions", "expires_hours", "notes"]
            has_update_field = any(field in update for field in update_fields)
            
            if not has_update_field:
                results.append({
                    "plan_id": plan_id,
                    "status": "failed",
                    "error": "At least one update field must be provided (entry_price, stop_loss, take_profit, volume, conditions, expires_hours, or notes)"
                })
                failed += 1
                logger.warning(f"Update {original_idx} ({plan_id}): No update fields provided")
                continue
            
            try:
                # Call update_plan method
                result = auto_execution.update_plan(
                    plan_id=plan_id,
                    entry_price=update.get("entry_price"),
                    stop_loss=update.get("stop_loss"),
                    take_profit=update.get("take_profit"),
                    volume=update.get("volume"),
                    conditions=update.get("conditions"),
                    expires_hours=update.get("expires_hours"),
                    notes=update.get("notes")
                )
                
                # Log update attempt
                logger.info(f"Update {original_idx} ({plan_id}): success={result.get('success')}")
                
                # Process result
                if result.get("success"):
                    results.append({
                        "plan_id": plan_id,
                        "status": "updated"
                    })
                    successful += 1
                else:
                    error_msg = result.get("message", "Unknown error")
                    results.append({
                        "plan_id": plan_id,
                        "status": "failed",
                        "error": error_msg
                    })
                    failed += 1
                    logger.warning(f"Update {original_idx} ({plan_id}): Failed - {error_msg}")
                    
            except HTTPException as e:
                error_msg = e.detail if hasattr(e, 'detail') else str(e)
                results.append({
                    "plan_id": plan_id,
                    "status": "failed",
                    "error": error_msg
                })
                failed += 1
                logger.error(f"Update {original_idx} ({plan_id}): HTTPException - {error_msg}", exc_info=True)
            except Exception as e:
                error_msg = str(e)
                results.append({
                    "plan_id": plan_id,
                    "status": "failed",
                    "error": error_msg
                })
                failed += 1
                logger.error(f"Update {original_idx} ({plan_id}): Exception - {error_msg}", exc_info=True)
        
        # Sort results by original order (use first occurrence index)
        def get_sort_key(result_item):
            plan_id = result_item.get("plan_id")
            if plan_id and plan_id in original_order and original_order[plan_id]:
                return original_order[plan_id][0]
            return 999999
        
        results_sorted = sorted(results, key=get_sort_key)
        
        total = len(request.updates)
        logger.info(f"Batch update completed: total={total}, successful={successful}, failed={failed}")
        
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "results": results_sorted
        }
        
    except Exception as e:
        logger.error(f"Error in batch update endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process batch update: {str(e)}")

@router.post("/cancel-plans", dependencies=[Depends(verify_api_key)])
async def cancel_multiple_plans(request: BatchCancelPlanRequest):
    """Cancel multiple trade plans in a single batch operation"""
    try:
        auto_execution = get_chatgpt_auto_execution()
        results = []
        successful = 0
        failed = 0
        
        # Track original order before deduplication
        original_order = {}  # Maps plan_id to list of original indices
        deduplicated_plan_ids = []
        seen_plan_ids = {}
        
        # Deduplicate plan_ids (keep first occurrence)
        for idx, plan_id in enumerate(request.plan_ids):
            if plan_id in seen_plan_ids:
                # Duplicate found - skip it but track original position
                logger.warning(f"Duplicate plan_id found: {plan_id}, skipping duplicate")
                if plan_id not in original_order:
                    original_order[plan_id] = []
                original_order[plan_id].append(idx)
                continue
            
            seen_plan_ids[plan_id] = idx
            if plan_id not in original_order:
                original_order[plan_id] = []
            original_order[plan_id].append(idx)
            deduplicated_plan_ids.append((idx, plan_id))
        
        # Process each cancellation sequentially
        for original_idx, plan_id in deduplicated_plan_ids:
            try:
                # Call cancel_plan method
                result = auto_execution.cancel_plan(plan_id)
                
                # Log cancellation attempt
                logger.info(f"Cancel {original_idx} ({plan_id}): result={result}")
                
                # cancel_plan returns dict with {"success": bool, "message": str}
                # Since it's idempotent, we count both success=True and success=False (not found/already cancelled) as success
                if result.get("success"):
                    results.append({
                        "plan_id": plan_id,
                        "status": "cancelled"
                    })
                    successful += 1
                else:
                    # Plan not found or already cancelled - still count as success (idempotent)
                    results.append({
                        "plan_id": plan_id,
                        "status": "cancelled"  # Already cancelled, so status is "cancelled"
                    })
                    successful += 1
                    logger.info(f"Cancel {original_idx} ({plan_id}): Already cancelled or not found (idempotent)")
                    
            except HTTPException as e:
                error_msg = e.detail if hasattr(e, 'detail') else str(e)
                results.append({
                    "plan_id": plan_id,
                    "status": "failed",
                    "error": error_msg
                })
                failed += 1
                logger.error(f"Cancel {original_idx} ({plan_id}): HTTPException - {error_msg}", exc_info=True)
            except Exception as e:
                error_msg = str(e)
                results.append({
                    "plan_id": plan_id,
                    "status": "failed",
                    "error": error_msg
                })
                failed += 1
                logger.error(f"Cancel {original_idx} ({plan_id}): Exception - {error_msg}", exc_info=True)
        
        # Sort results by original order (use first occurrence index)
        def get_sort_key(result_item):
            plan_id = result_item.get("plan_id")
            if plan_id and plan_id in original_order and original_order[plan_id]:
                return original_order[plan_id][0]
            return 999999
        
        results_sorted = sorted(results, key=get_sort_key)
        
        total = len(request.plan_ids)
        logger.info(f"Batch cancel completed: total={total}, successful={successful}, failed={failed}")
        
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "results": results_sorted
        }
        
    except Exception as e:
        logger.error(f"Error in batch cancel endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process batch cancel: {str(e)}")
