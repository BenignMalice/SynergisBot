"""
Test Phase 2: Multiple Entry Levels Implementation
Tests multi-level entry support, validation, zone detection, and execution logic
"""

import sys
import os
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class TradePlan:
    """Minimal TradePlan for testing"""
    plan_id: str
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float
    conditions: dict
    created_at: str
    created_by: str
    status: str
    zone_entry_tracked: Optional[bool] = False
    zone_entry_time: Optional[str] = None
    zone_exit_time: Optional[str] = None
    entry_levels: Optional[List[Dict[str, Any]]] = None

def check_tolerance_zone_entry(plan: TradePlan, current_price: float, previous_in_zone: Optional[bool] = None) -> tuple[bool, Optional[int], bool]:
    """
    Check tolerance zone entry for a plan (Phase 1 + Phase 2).
    Standalone version for testing.
    """
    # Get tolerance from conditions or use default
    tolerance = plan.conditions.get("tolerance")
    if tolerance is None:
        # Default tolerance based on symbol
        if "BTC" in plan.symbol.upper():
            tolerance = 200.0  # BTC default
        elif "XAU" in plan.symbol.upper() or "GOLD" in plan.symbol.upper():
            tolerance = 5.0  # XAU default
        else:
            tolerance = 0.0003  # Forex default
    
    # Check if plan has entry_levels (Phase 2) or single entry_price
    entry_levels = plan.entry_levels or plan.conditions.get("entry_levels")
    
    if entry_levels and isinstance(entry_levels, list) and len(entry_levels) > 0:
        # Multi-level support (Phase 2)
        # Check each level in priority order (array order)
        for level_idx, level in enumerate(entry_levels):
            if isinstance(level, dict):
                level_price = level.get("price", plan.entry_price)
            else:
                level_price = level if isinstance(level, (int, float)) else plan.entry_price
            
            # Calculate zone bounds for this level
            if plan.direction == "BUY":
                zone_upper = level_price + tolerance
                zone_lower = level_price - tolerance
                in_zone = zone_lower <= current_price <= zone_upper
            else:  # SELL
                zone_upper = level_price + tolerance
                zone_lower = level_price - tolerance
                in_zone = zone_lower <= current_price <= zone_upper
            
            if in_zone:
                # Price is in zone for this level
                # Check if this is a new entry (was outside, now inside)
                entry_detected = previous_in_zone is False if previous_in_zone is not None else True
                return (True, level_idx, entry_detected)
        
        # No level is in zone
        return (False, None, False)
    else:
        # Single entry_price (current implementation)
        entry_price = plan.entry_price
        
        # Calculate zone bounds
        if plan.direction == "BUY":
            zone_upper = entry_price + tolerance
            zone_lower = entry_price - tolerance
            in_zone = zone_lower <= current_price <= zone_upper
        else:  # SELL
            zone_upper = entry_price + tolerance
            zone_lower = entry_price - tolerance
            in_zone = zone_lower <= current_price <= zone_upper
        
        # Check if this is a new entry (was outside, now inside)
        entry_detected = previous_in_zone is False if previous_in_zone is not None else True
        
        return (in_zone, None, entry_detected)

def test_1_multi_level_zone_detection():
    """Test 1: Multi-level zone entry detection"""
    logger.info("=" * 60)
    logger.info("TEST 1: Multi-Level Zone Entry Detection")
    logger.info("=" * 60)
    
    try:
        # Test BUY plan with 3 entry levels
        buy_plan = TradePlan(
            plan_id="test_multi_buy",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"tolerance": 100.0},
            created_at="2025-12-18T00:00:00Z",
            created_by="test",
            status="pending",
            entry_levels=[
                {"price": 49900.0, "weight": 1.0},
                {"price": 50000.0, "weight": 1.0},
                {"price": 50100.0, "weight": 1.0}
            ]
        )
        
        # Price at first level (should trigger level 0)
        in_zone, level_idx, entry_detected = check_tolerance_zone_entry(
            buy_plan, 49950.0, previous_in_zone=False
        )
        assert in_zone, "Price 49950 should be in zone for level 0 (49900)"
        assert level_idx == 0, f"Should trigger level 0, got {level_idx}"
        assert entry_detected, "Should detect entry"
        
        # Price at second level (should trigger level 1)
        in_zone, level_idx, entry_detected = check_tolerance_zone_entry(
            buy_plan, 50050.0, previous_in_zone=False
        )
        assert in_zone, "Price 50050 should be in zone for level 1 (50000)"
        assert level_idx == 1, f"Should trigger level 1, got {level_idx}"
        
        # Price at third level (should trigger level 2)
        in_zone, level_idx, entry_detected = check_tolerance_zone_entry(
            buy_plan, 50150.0, previous_in_zone=False
        )
        assert in_zone, "Price 50150 should be in zone for level 2 (50100)"
        assert level_idx == 2, f"Should trigger level 2, got {level_idx}"
        
        # Price outside all levels (should not trigger)
        in_zone, level_idx, entry_detected = check_tolerance_zone_entry(
            buy_plan, 50300.0, previous_in_zone=False
        )
        assert not in_zone, "Price 50300 should be outside all zones"
        assert level_idx is None, "Should not trigger any level"
        
        logger.info("✅ TEST 1 PASSED: Multi-level zone entry detection successful")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 1 FAILED: {e}", exc_info=True)
        return False

def test_2_level_priority_order():
    """Test 2: Level priority order (first level to enter zone triggers)"""
    logger.info("=" * 60)
    logger.info("TEST 2: Level Priority Order")
    logger.info("=" * 60)
    
    try:
        # Test BUY plan with overlapping levels
        buy_plan = TradePlan(
            plan_id="test_priority",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"tolerance": 150.0},  # Wide tolerance to create overlap
            created_at="2025-12-18T00:00:00Z",
            created_by="test",
            status="pending",
            entry_levels=[
                {"price": 49900.0, "weight": 1.0},  # Level 0
                {"price": 50000.0, "weight": 1.0},  # Level 1
                {"price": 50100.0, "weight": 1.0}   # Level 2
            ]
        )
        
        # Price that could match multiple levels (should match first in array order)
        # Price 50000 is within tolerance of level 0 (49900 ± 150 = 49750-50050)
        in_zone, level_idx, entry_detected = check_tolerance_zone_entry(
            buy_plan, 50000.0, previous_in_zone=False
        )
        assert in_zone, "Price 50000 should be in zone"
        assert level_idx == 0, f"Should trigger level 0 (first in array), got {level_idx}"
        
        logger.info("✅ TEST 2 PASSED: Level priority order correct")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 2 FAILED: {e}", exc_info=True)
        return False

def test_3_sell_direction_levels():
    """Test 3: SELL direction with multiple levels"""
    logger.info("=" * 60)
    logger.info("TEST 3: SELL Direction Multi-Level")
    logger.info("=" * 60)
    
    try:
        # Test SELL plan with 3 entry levels
        sell_plan = TradePlan(
            plan_id="test_multi_sell",
            symbol="BTCUSDc",
            direction="SELL",
            entry_price=50000.0,
            stop_loss=51000.0,
            take_profit=49000.0,
            volume=0.01,
            conditions={"tolerance": 100.0},
            created_at="2025-12-18T00:00:00Z",
            created_by="test",
            status="pending",
            entry_levels=[
                {"price": 50100.0, "weight": 1.0},  # Highest level
                {"price": 50000.0, "weight": 1.0},  # Middle level
                {"price": 49900.0, "weight": 1.0}   # Lowest level
            ]
        )
        
        # Price at first level (should trigger level 0)
        in_zone, level_idx, entry_detected = check_tolerance_zone_entry(
            sell_plan, 50150.0, previous_in_zone=False
        )
        assert in_zone, "Price 50150 should be in zone for level 0 (50100)"
        assert level_idx == 0, f"Should trigger level 0, got {level_idx}"
        
        # Price at second level (should trigger level 1)
        # Note: 50050 is within tolerance of level 0 (50100 ± 100 = 50000-50200)
        # So it will trigger level 0 first (priority order)
        # To test level 1, use a price that's only in level 1's zone
        in_zone, level_idx, entry_detected = check_tolerance_zone_entry(
            sell_plan, 50000.0, previous_in_zone=False
        )
        assert in_zone, "Price 50000 should be in zone for level 1 (50000)"
        # 50000 is exactly at level 1, but also within tolerance of level 0
        # So it triggers level 0 first (array order priority)
        assert level_idx == 0, f"Should trigger level 0 (first in array), got {level_idx}"
        
        # Test level 1 with a price that's only in its zone
        # Level 1: 50000 ± 100 = 49900-50100
        # Level 0: 50100 ± 100 = 50000-50200
        # Use 49950 which is only in level 1's zone
        in_zone, level_idx, entry_detected = check_tolerance_zone_entry(
            sell_plan, 49950.0, previous_in_zone=False
        )
        assert in_zone, "Price 49950 should be in zone for level 1 (50000)"
        assert level_idx == 1, f"Should trigger level 1, got {level_idx}"
        
        # Price at third level (should trigger level 2)
        # Level 2: 49900 ± 100 = 49800-50000
        # Level 1: 50000 ± 100 = 49900-50100
        # Use 49850 which is only in level 2's zone
        in_zone, level_idx, entry_detected = check_tolerance_zone_entry(
            sell_plan, 49850.0, previous_in_zone=False
        )
        assert in_zone, "Price 49850 should be in zone for level 2 (49900)"
        assert level_idx == 2, f"Should trigger level 2, got {level_idx}"
        
        logger.info("✅ TEST 3 PASSED: SELL direction multi-level detection successful")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 3 FAILED: {e}", exc_info=True)
        return False

def test_4_entry_levels_validation():
    """Test 4: Entry levels validation logic"""
    logger.info("=" * 60)
    logger.info("TEST 4: Entry Levels Validation")
    logger.info("=" * 60)
    
    try:
        # Test validation scenarios (simulated)
        test_cases = [
            {
                "name": "Valid levels",
                "levels": [
                    {"price": 49900.0, "weight": 1.0},
                    {"price": 50000.0, "weight": 1.0}
                ],
                "should_pass": True
            },
            {
                "name": "Levels with offsets",
                "levels": [
                    {"price": 49900.0, "sl_offset": 100.0, "tp_offset": 200.0},
                    {"price": 50000.0, "sl_offset": 100.0, "tp_offset": 200.0}
                ],
                "should_pass": True
            },
            {
                "name": "Missing price",
                "levels": [
                    {"weight": 1.0},  # Missing price
                    {"price": 50000.0}
                ],
                "should_pass": False
            },
            {
                "name": "Invalid price (negative)",
                "levels": [
                    {"price": -100.0},
                    {"price": 50000.0}
                ],
                "should_pass": False
            },
            {
                "name": "Invalid offset (negative)",
                "levels": [
                    {"price": 50000.0, "sl_offset": -100.0}
                ],
                "should_pass": False
            }
        ]
        
        # Note: Full validation is in chatgpt_auto_execution_integration.py
        # This test verifies the structure and basic validation logic
        for test_case in test_cases:
            levels = test_case["levels"]
            has_price = all("price" in level for level in levels)
            prices_valid = all(
                isinstance(level.get("price"), (int, float)) and level.get("price") > 0
                for level in levels
                if "price" in level
            )
            # Check offsets are valid (if provided)
            offsets_valid = all(
                (level.get("sl_offset") is None or (isinstance(level.get("sl_offset"), (int, float)) and level.get("sl_offset") > 0)) and
                (level.get("tp_offset") is None or (isinstance(level.get("tp_offset"), (int, float)) and level.get("tp_offset") > 0))
                for level in levels
            )
            
            all_valid = has_price and prices_valid and offsets_valid
            
            if test_case["should_pass"]:
                assert all_valid, f"Test '{test_case['name']}' should pass validation"
            else:
                # For negative tests, at least one validation should fail
                assert not all_valid, f"Test '{test_case['name']}' should fail validation"
        
        logger.info("✅ TEST 4 PASSED: Entry levels validation logic correct")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 4 FAILED: {e}", exc_info=True)
        return False

def test_5_sl_tp_calculation():
    """Test 5: SL/TP calculation based on triggered level"""
    logger.info("=" * 60)
    logger.info("TEST 5: SL/TP Calculation from Triggered Level")
    logger.info("=" * 60)
    
    try:
        # Simulate SL/TP calculation logic
        def calculate_sl_tp(plan: TradePlan, triggered_level_index: int, current_price: float):
            """Simulate SL/TP calculation from triggered level"""
            if not plan.entry_levels or triggered_level_index is None:
                return plan.stop_loss, plan.take_profit
            
            triggered_level = plan.entry_levels[triggered_level_index]
            level_price = triggered_level.get("price", plan.entry_price)
            sl_offset = triggered_level.get("sl_offset")
            tp_offset = triggered_level.get("tp_offset")
            
            execution_sl = plan.stop_loss
            execution_tp = plan.take_profit
            execution_entry = level_price
            
            if sl_offset is not None:
                if plan.direction == "BUY":
                    execution_sl = level_price - abs(sl_offset)
                else:  # SELL
                    execution_sl = level_price + abs(sl_offset)
            
            if tp_offset is not None:
                if plan.direction == "BUY":
                    execution_tp = level_price + abs(tp_offset)
                else:  # SELL
                    execution_tp = level_price - abs(tp_offset)
            
            return execution_entry, execution_sl, execution_tp
        
        # Test BUY plan with level-specific offsets
        buy_plan = TradePlan(
            plan_id="test_sl_tp",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"tolerance": 100.0},
            created_at="2025-12-18T00:00:00Z",
            created_by="test",
            status="pending",
            entry_levels=[
                {"price": 49900.0, "sl_offset": 500.0, "tp_offset": 1000.0},
                {"price": 50000.0, "sl_offset": 600.0, "tp_offset": 1200.0}
            ]
        )
        
        # Trigger level 0
        entry, sl, tp = calculate_sl_tp(buy_plan, 0, 49950.0)
        assert entry == 49900.0, f"Entry should be level price 49900.0, got {entry}"
        assert sl == 49400.0, f"SL should be 49900 - 500 = 49400, got {sl}"
        assert tp == 50900.0, f"TP should be 49900 + 1000 = 50900, got {tp}"
        
        # Trigger level 1
        entry, sl, tp = calculate_sl_tp(buy_plan, 1, 50050.0)
        assert entry == 50000.0, f"Entry should be level price 50000.0, got {entry}"
        assert sl == 49400.0, f"SL should be 50000 - 600 = 49400, got {sl}"
        assert tp == 51200.0, f"TP should be 50000 + 1200 = 51200, got {tp}"
        
        # Test SELL plan
        sell_plan = TradePlan(
            plan_id="test_sl_tp_sell",
            symbol="BTCUSDc",
            direction="SELL",
            entry_price=50000.0,
            stop_loss=51000.0,
            take_profit=49000.0,
            volume=0.01,
            conditions={"tolerance": 100.0},
            created_at="2025-12-18T00:00:00Z",
            created_by="test",
            status="pending",
            entry_levels=[
                {"price": 50100.0, "sl_offset": 500.0, "tp_offset": 1000.0}
            ]
        )
        
        # Trigger level 0 for SELL
        entry, sl, tp = calculate_sl_tp(sell_plan, 0, 50150.0)
        assert entry == 50100.0, f"Entry should be level price 50100.0, got {entry}"
        assert sl == 50600.0, f"SL should be 50100 + 500 = 50600, got {sl}"
        assert tp == 49100.0, f"TP should be 50100 - 1000 = 49100, got {tp}"
        
        logger.info("✅ TEST 5 PASSED: SL/TP calculation from triggered level successful")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 5 FAILED: {e}", exc_info=True)
        return False

def test_6_fallback_to_single_entry():
    """Test 6: Fallback to single entry when entry_levels not provided"""
    logger.info("=" * 60)
    logger.info("TEST 6: Fallback to Single Entry")
    logger.info("=" * 60)
    
    try:
        # Test plan without entry_levels (should use entry_price)
        single_plan = TradePlan(
            plan_id="test_single",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"tolerance": 100.0},
            created_at="2025-12-18T00:00:00Z",
            created_by="test",
            status="pending",
            entry_levels=None  # No multi-level
        )
        
        # Price in zone (should work like single entry)
        in_zone, level_idx, entry_detected = check_tolerance_zone_entry(
            single_plan, 50050.0, previous_in_zone=False
        )
        assert in_zone, "Price should be in zone for single entry"
        assert level_idx is None, "Level index should be None for single entry"
        
        logger.info("✅ TEST 6 PASSED: Fallback to single entry works correctly")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 6 FAILED: {e}", exc_info=True)
        return False

def run_all_tests():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("PHASE 2: MULTIPLE ENTRY LEVELS IMPLEMENTATION TESTS (STANDALONE)")
    logger.info("=" * 60)
    
    # Run tests
    tests = [
        test_1_multi_level_zone_detection,
        test_2_level_priority_order,
        test_3_sell_direction_levels,
        test_4_entry_levels_validation,
        test_5_sl_tp_calculation,
        test_6_fallback_to_single_entry
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            logger.error(f"Test {test.__name__} raised exception: {e}", exc_info=True)
            results.append(False)
    
    # Summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    for i, (test, result) in enumerate(zip(tests, results), 1):
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"Test {i}: {test.__name__}: {status}")
    
    logger.info("=" * 60)
    logger.info(f"Total: {passed}/{total} tests passed ({passed*100//total}%)")
    logger.info("=" * 60)
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

