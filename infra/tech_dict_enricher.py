"""
Tech Dict Enricher - Populate detection results into tech dict

Integrates DetectionSystemManager results into tech dict for strategy selection.
Called after _build_tech_from_bridge() to add detection data.
"""

import logging
from typing import Dict, Optional, Any
import pandas as pd

logger = logging.getLogger(__name__)


def populate_detection_results(
    tech: Dict[str, Any], 
    symbol: str, 
    m5_df: Optional[pd.DataFrame] = None, 
    m15_df: Optional[pd.DataFrame] = None
) -> None:
    """
    Populate tech dict with detection system results.
    Called after _build_tech_from_bridge() to add detection data.
    
    Based on audit findings, integrates:
    - Order Block Detection (M5/M15) - currently only M1 exists
    - FVG Detection (M15) - exists but not integrated
    - CHOCH/BOS Detection (M15) - exists but not integrated
    - Structure Detection - enhance existing inconsistent fields
    - Kill Zone Detection - derive from session
    
    Args:
        tech: Tech dict to populate (modified in place)
        symbol: Trading symbol
        m5_df: Optional M5 DataFrame (for future use)
        m15_df: Optional M15 DataFrame (for future use)
    """
    try:
        from infra.detection_systems import DetectionSystemManager
        detector = DetectionSystemManager()
        
        # Get order block detection (M5) - ⚠️ AUDIT: Currently only M1 exists, needs M5/M15
        ob_result = detector.get_order_block(symbol, timeframe="M5")
        if ob_result:
            # Extract order block data
            ob_bull = ob_result.get("order_block_bull")
            ob_bear = ob_result.get("order_block_bear")
            
            tech.update({
                "order_block_bull": ob_bull,
                "order_block_bear": ob_bear,
                "ob_strength": ob_result.get("ob_strength", 0.5),
                "ob_confluence": ob_result.get("ob_confluence", []),
                "order_block": True if (ob_bull or ob_bear) else False
            })
        
        # Get FVG detection (M15) - ✅ AUDIT: Detection exists in domain/fvg.py
        fvg_result = detector.get_fvg(symbol, timeframe="M15")
        if fvg_result:
            # Normalize to dict format: {"high": float, "low": float, "filled_pct": float}
            fvg_bull = fvg_result.get("fvg_bull")
            fvg_bear = fvg_result.get("fvg_bear")
            
            # Calculate filled_pct if not already calculated
            filled_pct = 0.0
            if fvg_bull and isinstance(fvg_bull, dict):
                filled_pct = fvg_bull.get("filled_pct", 0.0)
            elif fvg_bear and isinstance(fvg_bear, dict):
                filled_pct = fvg_bear.get("filled_pct", 0.0)
            
            tech.update({
                "fvg_bull": fvg_bull,  # Dict format
                "fvg_bear": fvg_bear,  # Dict format
                "fvg_strength": fvg_result.get("fvg_strength", 0.5),
                "fvg_filled_pct": filled_pct,
                "fvg_confluence": fvg_result.get("fvg_confluence", [])
            })
        
        # Get CHOCH/BOS detection (M15) - ✅ AUDIT: Detection exists in domain/market_structure.py
        choch_bos_result = detector.get_choch_bos(symbol, timeframe="M15")
        if choch_bos_result:
            tech.update({
                "choch_bull": choch_bos_result.get("choch_bull", False),
                "choch_bear": choch_bos_result.get("choch_bear", False),
                "bos_bull": choch_bos_result.get("bos_bull", False),
                "bos_bear": choch_bos_result.get("bos_bear", False),
                "structure_strength": choch_bos_result.get("structure_strength", 0.5),
                "bars_since_bos": choch_bos_result.get("bars_since_bos", -1),
                "break_level": choch_bos_result.get("break_level", 0.0)
            })
        
        # Get kill zone detection - ✅ AUDIT: Can derive from session
        kill_zone_result = detector.get_kill_zone(symbol, timeframe="M5")
        if kill_zone_result:
            tech.update({
                "kill_zone_active": kill_zone_result.get("kill_zone_active", False)
            })
        else:
            # Fallback: derive from session if kill_zone detection not available
            session = tech.get("session", "").upper()
            if session in ["LONDON", "NY", "OVERLAP"]:
                tech["kill_zone_active"] = True
            else:
                tech["kill_zone_active"] = False
        
        # Get breaker block detection (M5) - ✅ IMPLEMENTED: Phase 0.2.4.1
        breaker_result = detector.get_breaker_block(symbol, timeframe="M5")
        if breaker_result:
            tech.update({
                "breaker_block_bull": breaker_result.get("breaker_block_bull"),
                "breaker_block_bear": breaker_result.get("breaker_block_bear"),
                "ob_broken": breaker_result.get("ob_broken", False),
                "price_retesting_breaker": breaker_result.get("price_retesting_breaker", False),
                "breaker_block_strength": breaker_result.get("breaker_block_strength", 0.5)
            })
        
        # Get Market Structure Shift detection (M15) - ✅ IMPLEMENTED: Phase 0.2.4.2
        mss_result = detector.get_market_structure_shift(symbol, timeframe="M15")
        if mss_result:
            tech.update({
                "mss_bull": mss_result.get("mss_bull", False),
                "mss_bear": mss_result.get("mss_bear", False),
                "pullback_to_mss": mss_result.get("pullback_to_mss", False),
                "mss_level": mss_result.get("mss_level", 0.0),
                "mss_strength": mss_result.get("mss_strength", 0.5)
            })
        
        # Get mitigation block detection (M5) - ✅ IMPLEMENTED: Phase 0.2.4.3
        mitigation_result = detector.get_mitigation_block(symbol, timeframe="M5")
        if mitigation_result:
            tech.update({
                "mitigation_block_bull": mitigation_result.get("mitigation_block_bull"),
                "mitigation_block_bear": mitigation_result.get("mitigation_block_bear"),
                "structure_broken": mitigation_result.get("structure_broken", False),
                "mitigation_block_strength": mitigation_result.get("mitigation_block_strength", 0.5)
            })
        
        # Get rejection pattern detection (M5) - ✅ IMPLEMENTED: Phase 0.2.4.4
        rejection_result = detector.get_rejection_pattern(symbol, timeframe="M5")
        if rejection_result:
            tech.update({
                "rejection_detected": rejection_result.get("rejection_detected", False),
                "rejection_direction": rejection_result.get("rejection_direction"),
                "rejection_strength": rejection_result.get("rejection_strength", 0.5),
                "liquidity_grab_bull": rejection_result.get("liquidity_grab_bull", False),
                "liquidity_grab_bear": rejection_result.get("liquidity_grab_bear", False)
            })
        
        # Get Fibonacci levels / Premium-Discount Array (M15) - ✅ IMPLEMENTED: Phase 0.2.4.5
        fib_result = detector.get_fibonacci_levels(symbol, timeframe="M15")
        if fib_result:
            tech.update({
                "fib_levels": fib_result.get("fib_levels", {}),
                "price_in_premium": fib_result.get("price_in_premium", False),
                "price_in_discount": fib_result.get("price_in_discount", False),
                "fib_level": fib_result.get("fib_level", 0.0),
                "fib_strength": fib_result.get("fib_strength", 0.5)
            })
        
        # Get session liquidity run detection (M15) - ✅ IMPLEMENTED: Phase 0.2.4.6
        session_liquidity_result = detector.get_session_liquidity(symbol, timeframe="M15")
        if session_liquidity_result:
            tech.update({
                "session_liquidity_run": session_liquidity_result.get("session_liquidity_run", False),
                "asian_session_high": session_liquidity_result.get("asian_session_high"),
                "asian_session_low": session_liquidity_result.get("asian_session_low"),
                "london_session_active": session_liquidity_result.get("london_session_active", False),
                "ny_session_active": session_liquidity_result.get("ny_session_active", False),
                "session_liquidity_strength": session_liquidity_result.get("session_liquidity_strength", 0.5)
            })
        
    except Exception as e:
        logger.warning(f"Failed to populate detection results for {symbol}: {e}")
        # Don't fail - continue without detection results
        # This ensures graceful degradation if detection systems are unavailable

