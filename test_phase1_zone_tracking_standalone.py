"""
Test Phase 1: Wider Tolerance Zones Implementation (Standalone)
Tests zone entry detection logic without importing full system
"""

import sys
import os
from dataclasses import dataclass
from typing import Optional

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

def check_tolerance_zone_entry(plan: TradePlan, current_price: float, previous_in_zone: Optional[bool] = None) -> tuple[bool, Optional[int], bool]:
    """
    Check tolerance zone entry for a plan (Phase 1).
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

def test_1_zone_entry_detection():
    """Test 1: Zone entry detection for BUY and SELL plans"""
    logger.info("=" * 60)
    logger.info("TEST 1: Zone Entry Detection")
    logger.info("=" * 60)
    
    try:
        # Test BUY plan
        buy_plan = TradePlan(
            plan_id="test_buy_zone",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"price_near": 50000.0, "tolerance": 100.0},
            created_at="2025-12-18T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Price within zone (should be in zone)
        in_zone, level_idx, entry_detected = check_tolerance_zone_entry(
            buy_plan, 50050.0, previous_in_zone=False
        )
        assert in_zone, "Price 50050 should be in zone for entry 50000 with tolerance 100"
        assert entry_detected, "Should detect entry when previous was False"
        
        # Price at upper bound (should be in zone)
        in_zone, _, _ = check_tolerance_zone_entry(
            buy_plan, 50100.0, previous_in_zone=False
        )
        assert in_zone, "Price 50100 (entry + tolerance) should be in zone"
        
        # Price outside zone (should not be in zone)
        in_zone, _, _ = check_tolerance_zone_entry(
            buy_plan, 50200.0, previous_in_zone=False
        )
        assert not in_zone, "Price 50200 should be outside zone"
        
        # Test SELL plan
        sell_plan = TradePlan(
            plan_id="test_sell_zone",
            symbol="BTCUSDc",
            direction="SELL",
            entry_price=50000.0,
            stop_loss=51000.0,
            take_profit=49000.0,
            volume=0.01,
            conditions={"price_near": 50000.0, "tolerance": 100.0},
            created_at="2025-12-18T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Price within zone (should be in zone)
        in_zone, _, entry_detected = check_tolerance_zone_entry(
            sell_plan, 49950.0, previous_in_zone=False
        )
        assert in_zone, "Price 49950 should be in zone for SELL entry 50000 with tolerance 100"
        assert entry_detected, "Should detect entry when previous was False"
        
        # Price at lower bound (should be in zone)
        in_zone, _, _ = check_tolerance_zone_entry(
            sell_plan, 49900.0, previous_in_zone=False
        )
        assert in_zone, "Price 49900 (entry - tolerance) should be in zone"
        
        logger.info("✅ TEST 1 PASSED: Zone entry detection successful")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 1 FAILED: {e}", exc_info=True)
        return False

def test_2_zone_entry_not_detected_when_already_in_zone():
    """Test 2: Zone entry should not be detected if already in zone"""
    logger.info("=" * 60)
    logger.info("TEST 2: Zone Entry Not Detected When Already In Zone")
    logger.info("=" * 60)
    
    try:
        test_plan = TradePlan(
            plan_id="test_no_duplicate_entry",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"price_near": 50000.0, "tolerance": 100.0},
            created_at="2025-12-18T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # First entry (previous was False)
        in_zone, _, entry_detected = check_tolerance_zone_entry(
            test_plan, 50050.0, previous_in_zone=False
        )
        assert in_zone, "Price should be in zone"
        assert entry_detected, "Should detect entry when previous was False"
        
        # Second check (previous was True - already in zone)
        in_zone, _, entry_detected = check_tolerance_zone_entry(
            test_plan, 50050.0, previous_in_zone=True
        )
        assert in_zone, "Price should still be in zone"
        assert not entry_detected, "Should NOT detect entry when already in zone"
        
        logger.info("✅ TEST 2 PASSED: Zone entry not detected when already in zone")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 2 FAILED: {e}", exc_info=True)
        return False

def test_3_zone_bounds_calculation():
    """Test 3: Zone bounds calculation for different directions"""
    logger.info("=" * 60)
    logger.info("TEST 3: Zone Bounds Calculation")
    logger.info("=" * 60)
    
    try:
        # BUY plan: zone should be entry_price ± tolerance
        buy_plan = TradePlan(
            plan_id="test_buy_bounds",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"price_near": 50000.0, "tolerance": 100.0},
            created_at="2025-12-18T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # Test boundary conditions
        # Lower bound: entry - tolerance = 49900
        in_zone, _, _ = check_tolerance_zone_entry(
            buy_plan, 49900.0, previous_in_zone=False
        )
        assert in_zone, "Lower bound (entry - tolerance) should be in zone"
        
        # Upper bound: entry + tolerance = 50100
        in_zone, _, _ = check_tolerance_zone_entry(
            buy_plan, 50100.0, previous_in_zone=False
        )
        assert in_zone, "Upper bound (entry + tolerance) should be in zone"
        
        # Just outside lower bound
        in_zone, _, _ = check_tolerance_zone_entry(
            buy_plan, 49899.0, previous_in_zone=False
        )
        assert not in_zone, "Just below lower bound should be outside zone"
        
        # Just outside upper bound
        in_zone, _, _ = check_tolerance_zone_entry(
            buy_plan, 50101.0, previous_in_zone=False
        )
        assert not in_zone, "Just above upper bound should be outside zone"
        
        logger.info("✅ TEST 3 PASSED: Zone bounds calculation successful")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 3 FAILED: {e}", exc_info=True)
        return False

def test_4_zone_re_entry_detection():
    """Test 4: Zone re-entry detection after exit"""
    logger.info("=" * 60)
    logger.info("TEST 4: Zone Re-entry Detection")
    logger.info("=" * 60)
    
    try:
        test_plan = TradePlan(
            plan_id="test_re_entry",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51000.0,
            volume=0.01,
            conditions={"price_near": 50000.0, "tolerance": 100.0},
            created_at="2025-12-18T00:00:00Z",
            created_by="test",
            status="pending"
        )
        
        # First entry
        in_zone, _, entry_detected = check_tolerance_zone_entry(
            test_plan, 50050.0, previous_in_zone=False
        )
        assert in_zone and entry_detected, "Should detect first entry"
        
        # Price exits zone
        in_zone, _, _ = check_tolerance_zone_entry(
            test_plan, 50200.0, previous_in_zone=True
        )
        assert not in_zone, "Price should be outside zone"
        
        # Price re-enters zone
        in_zone, _, entry_detected = check_tolerance_zone_entry(
            test_plan, 50050.0, previous_in_zone=False
        )
        assert in_zone, "Price should be back in zone"
        assert entry_detected, "Should detect re-entry when previous was False"
        
        logger.info("✅ TEST 4 PASSED: Zone re-entry detection successful")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 4 FAILED: {e}", exc_info=True)
        return False

def run_all_tests():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("PHASE 1: WIDER TOLERANCE ZONES IMPLEMENTATION TESTS (STANDALONE)")
    logger.info("=" * 60)
    
    # Run tests
    tests = [
        test_1_zone_entry_detection,
        test_2_zone_entry_not_detected_when_already_in_zone,
        test_3_zone_bounds_calculation,
        test_4_zone_re_entry_detection
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

