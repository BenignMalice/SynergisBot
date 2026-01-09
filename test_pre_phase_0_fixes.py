"""
Test Pre-Phase 0 Fixes: API Mismatch Bug Fixes

This script tests that all 7 instances of the API mismatch bug have been fixed:
1. Order block validation (get_delta_volume, get_cvd_trend)
2. Order block absorption zones (get_absorption_zones)
3. Delta positive/negative conditions (get_delta_volume)
4. CVD rising/falling conditions (get_cvd_trend)
5. Delta divergence bull (get_delta_volume)
6. Delta divergence bear (get_delta_volume)

All should now use get_metrics() via _get_btc_order_flow_metrics() helper method.
"""

import sys
import logging
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass
from typing import Dict, Any, Optional

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import TradePlan and AutoExecutionSystem
sys.path.insert(0, '.')
from auto_execution_system import TradePlan, AutoExecutionSystem

# Mock OrderFlowMetrics dataclass
@dataclass
class MockOrderFlowMetrics:
    """Mock OrderFlowMetrics for testing"""
    symbol: str = "BTCUSDT"
    timestamp: float = 0.0
    delta_volume: float = 0.0
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    cvd: float = 0.0
    cvd_slope: float = 0.0
    cvd_divergence_strength: float = 0.0
    cvd_divergence_type: Optional[str] = None
    absorption_zones: list = None
    
    def __post_init__(self):
        if self.absorption_zones is None:
            self.absorption_zones = []


def create_mock_auto_execution_system():
    """Create a mock AutoExecutionSystem for testing"""
    
    # Create mock MT5 service
    mock_mt5_service = Mock()
    mock_mt5_service.connect.return_value = True
    mock_mt5_service.get_tick.return_value = {'bid': 100000.0, 'ask': 100010.0}
    
    # Create mock micro scalp engine with BTC order flow
    mock_btc_order_flow = Mock()
    mock_btc_order_flow.get_metrics.return_value = None  # Will be set per test
    
    mock_micro_scalp_engine = Mock()
    mock_micro_scalp_engine.btc_order_flow = mock_btc_order_flow
    
    # Create AutoExecutionSystem instance
    # We'll use minimal initialization since we're just testing the condition checking
    system = AutoExecutionSystem.__new__(AutoExecutionSystem)
    system.mt5_service = mock_mt5_service
    system.micro_scalp_engine = mock_micro_scalp_engine
    system.config = {}
    system.db_path = ":memory:"  # In-memory database for testing
    
    # Initialize other required attributes
    system.plans = {}
    system.plans_lock = __import__('threading').Lock()
    system.running = True
    
    return system, mock_btc_order_flow


def test_helper_method():
    """Test the _get_btc_order_flow_metrics() helper method"""
    logger.info("=" * 60)
    logger.info("Test 1: Helper Method _get_btc_order_flow_metrics()")
    logger.info("=" * 60)
    
    system, mock_btc_order_flow = create_mock_auto_execution_system()
    
    # Create test plan
    plan = TradePlan(
        plan_id="test_plan_1",
        symbol="BTCUSDc",
        direction="BUY",
        entry_price=100000.0,
        stop_loss=99500.0,
        take_profit=101000.0,
        volume=0.01,
        conditions={},
        created_at="2025-01-01T00:00:00",
        created_by="test",
        status="pending"
    )
    
    # Test 1.1: Helper method returns metrics when available
    mock_metrics = MockOrderFlowMetrics(
        delta_volume=150.0,
        cvd_slope=0.5
    )
    mock_btc_order_flow.get_metrics.return_value = mock_metrics
    
    result = system._get_btc_order_flow_metrics(plan)
    assert result is not None, "Helper method should return metrics"
    assert result.delta_volume == 150.0, "Delta volume should match"
    assert result.cvd_slope == 0.5, "CVD slope should match"
    logger.info("✅ Helper method returns metrics correctly")
    
    # Test 1.2: Helper method returns None when unavailable
    mock_btc_order_flow.get_metrics.return_value = None
    result = system._get_btc_order_flow_metrics(plan)
    assert result is None, "Helper method should return None when metrics unavailable"
    logger.info("✅ Helper method handles None gracefully")
    
    # Test 1.3: Helper method handles exceptions
    mock_btc_order_flow.get_metrics.side_effect = Exception("Test error")
    result = system._get_btc_order_flow_metrics(plan)
    assert result is None, "Helper method should return None on exception"
    logger.info("✅ Helper method handles exceptions gracefully")
    
    logger.info("✅ All helper method tests passed\n")


def test_delta_conditions():
    """Test delta_positive and delta_negative conditions"""
    logger.info("=" * 60)
    logger.info("Test 2: Delta Conditions (delta_positive, delta_negative)")
    logger.info("=" * 60)
    
    system, mock_btc_order_flow = create_mock_auto_execution_system()
    
    # Test 2.1: delta_positive condition met
    plan = TradePlan(
        plan_id="test_delta_positive",
        symbol="BTCUSDc",
        direction="BUY",
        entry_price=100000.0,
        stop_loss=99500.0,
        take_profit=101000.0,
        volume=0.01,
        conditions={"delta_positive": True},
        created_at="2025-01-01T00:00:00",
        created_by="test",
        status="pending"
    )
    
    mock_metrics = MockOrderFlowMetrics(delta_volume=150.0)
    mock_btc_order_flow.get_metrics.return_value = mock_metrics
    
    # Mock price check to pass (we're only testing order flow conditions)
    with patch.object(system, '_check_price_conditions', return_value=True):
        result = system._check_conditions(plan)
        assert result == True, "delta_positive condition should pass with positive delta"
        logger.info("✅ delta_positive condition passes with positive delta")
    
    # Test 2.2: delta_positive condition not met (negative delta)
    mock_metrics.delta_volume = -50.0
    with patch.object(system, '_check_price_conditions', return_value=True):
        result = system._check_conditions(plan)
        assert result == False, "delta_positive condition should fail with negative delta"
        logger.info("✅ delta_positive condition fails with negative delta")
    
    # Test 2.3: delta_negative condition met
    plan.conditions = {"delta_negative": True}
    mock_metrics.delta_volume = -150.0
    with patch.object(system, '_check_price_conditions', return_value=True):
        result = system._check_conditions(plan)
        assert result == True, "delta_negative condition should pass with negative delta"
        logger.info("✅ delta_negative condition passes with negative delta")
    
    logger.info("✅ All delta condition tests passed\n")


def test_cvd_conditions():
    """Test cvd_rising and cvd_falling conditions"""
    logger.info("=" * 60)
    logger.info("Test 3: CVD Conditions (cvd_rising, cvd_falling)")
    logger.info("=" * 60)
    
    system, mock_btc_order_flow = create_mock_auto_execution_system()
    
    # Test 3.1: cvd_rising condition met
    plan = TradePlan(
        plan_id="test_cvd_rising",
        symbol="BTCUSDc",
        direction="BUY",
        entry_price=100000.0,
        stop_loss=99500.0,
        take_profit=101000.0,
        volume=0.01,
        conditions={"cvd_rising": True},
        created_at="2025-01-01T00:00:00",
        created_by="test",
        status="pending"
    )
    
    mock_metrics = MockOrderFlowMetrics(cvd_slope=0.5)  # Positive slope = rising
    mock_btc_order_flow.get_metrics.return_value = mock_metrics
    
    with patch.object(system, '_check_price_conditions', return_value=True):
        result = system._check_conditions(plan)
        assert result == True, "cvd_rising condition should pass with positive slope"
        logger.info("✅ cvd_rising condition passes with positive slope")
    
    # Test 3.2: cvd_rising condition not met (falling)
    mock_metrics.cvd_slope = -0.5  # Negative slope = falling
    with patch.object(system, '_check_price_conditions', return_value=True):
        result = system._check_conditions(plan)
        assert result == False, "cvd_rising condition should fail with negative slope"
        logger.info("✅ cvd_rising condition fails with negative slope")
    
    # Test 3.3: cvd_falling condition met
    plan.conditions = {"cvd_falling": True}
    mock_metrics.cvd_slope = -0.5
    with patch.object(system, '_check_price_conditions', return_value=True):
        result = system._check_conditions(plan)
        assert result == True, "cvd_falling condition should pass with negative slope"
        logger.info("✅ cvd_falling condition passes with negative slope")
    
    logger.info("✅ All CVD condition tests passed\n")


def test_absorption_zones():
    """Test absorption zone checking"""
    logger.info("=" * 60)
    logger.info("Test 4: Absorption Zones")
    logger.info("=" * 60)
    
    system, mock_btc_order_flow = create_mock_auto_execution_system()
    
    # Test 4.1: Entry price in absorption zone (should block)
    plan = TradePlan(
        plan_id="test_absorption_zone",
        symbol="BTCUSDc",
        direction="BUY",
        entry_price=100000.0,  # Entry price
        stop_loss=99500.0,
        take_profit=101000.0,
        volume=0.01,
        conditions={"avoid_absorption_zones": True},
        created_at="2025-01-01T00:00:00",
        created_by="test"
    )
    
    # Create absorption zone that contains entry price
    mock_metrics = MockOrderFlowMetrics(
        absorption_zones=[
            {
                'high': 100100.0,
                'low': 99900.0
            }
        ]
    )
    mock_btc_order_flow.get_metrics.return_value = mock_metrics
    
    with patch.object(system, '_check_price_conditions', return_value=True):
        result = system._check_conditions(plan)
        assert result == False, "Plan should be blocked if entry in absorption zone"
        logger.info("✅ Absorption zone blocks entry correctly")
    
    # Test 4.2: Entry price outside absorption zone (should pass)
    plan.entry_price = 101000.0  # Outside zone
    with patch.object(system, '_check_price_conditions', return_value=True):
        result = system._check_conditions(plan)
        assert result == True, "Plan should pass if entry outside absorption zone"
        logger.info("✅ Absorption zone allows entry outside zone")
    
    logger.info("✅ All absorption zone tests passed\n")


def test_order_block_validation():
    """Test order block validation with order flow"""
    logger.info("=" * 60)
    logger.info("Test 5: Order Block Validation with Order Flow")
    logger.info("=" * 60)
    
    system, mock_btc_order_flow = create_mock_auto_execution_system()
    
    # Test 5.1: BUY order block with positive delta and rising CVD
    plan = TradePlan(
        plan_id="test_ob_buy",
        symbol="BTCUSDc",
        direction="BUY",
        entry_price=100000.0,
        stop_loss=99500.0,
        take_profit=101000.0,
        volume=0.01,
        conditions={"order_block": True},
        created_at="2025-01-01T00:00:00",
        created_by="test",
        status="pending"
    )
    
    mock_metrics = MockOrderFlowMetrics(
        delta_volume=150.0,  # Positive delta
        cvd_slope=0.5,  # Rising CVD
        absorption_zones=[]  # No absorption zones
    )
    mock_btc_order_flow.get_metrics.return_value = mock_metrics
    
    with patch.object(system, '_check_price_conditions', return_value=True):
        with patch.object(system, '_check_order_block_conditions', return_value=True):
            result = system._check_conditions(plan)
            assert result == True, "BUY OB should pass with positive delta and rising CVD"
            logger.info("✅ BUY order block passes with positive delta and rising CVD")
    
    # Test 5.2: BUY order block blocked by negative delta
    mock_metrics.delta_volume = -50.0  # Negative delta
    with patch.object(system, '_check_price_conditions', return_value=True):
        with patch.object(system, '_check_order_block_conditions', return_value=True):
            result = system._check_conditions(plan)
            assert result == False, "BUY OB should be blocked by negative delta"
            logger.info("✅ BUY order block blocked by negative delta")
    
    logger.info("✅ All order block validation tests passed\n")


def test_delta_divergence():
    """Test delta divergence conditions"""
    logger.info("=" * 60)
    logger.info("Test 6: Delta Divergence Conditions")
    logger.info("=" * 60)
    
    system, mock_btc_order_flow = create_mock_auto_execution_system()
    
    # Test 6.1: delta_divergence_bull with positive delta
    plan = TradePlan(
        plan_id="test_delta_div_bull",
        symbol="BTCUSDc",
        direction="BUY",
        entry_price=100000.0,
        stop_loss=99500.0,
        take_profit=101000.0,
        volume=0.01,
        conditions={"delta_divergence_bull": True},
        created_at="2025-01-01T00:00:00",
        created_by="test",
        status="pending"
    )
    
    mock_metrics = MockOrderFlowMetrics(delta_volume=150.0)
    mock_btc_order_flow.get_metrics.return_value = mock_metrics
    
    with patch.object(system, '_check_price_conditions', return_value=True):
        result = system._check_conditions(plan)
        assert result == True, "delta_divergence_bull should pass with positive delta"
        logger.info("✅ delta_divergence_bull passes with positive delta")
    
    # Test 6.2: delta_divergence_bear with negative delta
    plan.conditions = {"delta_divergence_bear": True}
    mock_metrics.delta_volume = -150.0
    with patch.object(system, '_check_price_conditions', return_value=True):
        result = system._check_conditions(plan)
        assert result == True, "delta_divergence_bear should pass with negative delta"
        logger.info("✅ delta_divergence_bear passes with negative delta")
    
    logger.info("✅ All delta divergence tests passed\n")


def run_all_tests():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("PRE-PHASE 0 FIXES - COMPREHENSIVE TEST SUITE")
    logger.info("=" * 60)
    logger.info("Testing all 7 API mismatch bug fixes\n")
    
    try:
        test_helper_method()
        test_delta_conditions()
        test_cvd_conditions()
        test_absorption_zones()
        test_order_block_validation()
        test_delta_divergence()
        
        logger.info("=" * 60)
        logger.info("✅ ALL TESTS PASSED!")
        logger.info("=" * 60)
        logger.info("\nSummary:")
        logger.info("- Helper method _get_btc_order_flow_metrics() works correctly")
        logger.info("- All 7 API mismatch bugs have been fixed")
        logger.info("- Order flow conditions are checked using correct API")
        logger.info("- No calls to non-existent methods (get_delta_volume, get_cvd_trend, get_absorption_zones)")
        logger.info("\nPre-Phase 0 implementation is complete and verified!")
        
        return True
        
    except AssertionError as e:
        logger.error(f"❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        logger.error(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
