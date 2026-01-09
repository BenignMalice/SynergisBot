"""
Unit tests for Phase 2: Correlation Conditions
Tests for spx_up_pct, yield_drop, and correlation_divergence conditions
"""
import unittest
import sys
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from auto_execution_system import AutoExecutionSystem, TradePlan


class TestSPXChangeCondition(unittest.TestCase):
    """Test SPX percentage change condition detection"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Mock quote object - code accesses quote.bid and quote.ask
        class MockQuote:
            def __init__(self):
                self.bid = 91000.0
                self.ask = 91010.0
        
        self.mt5_service = Mock()
        self.mt5_service.connect.return_value = True
        self.mt5_service.get_quote = Mock(return_value=MockQuote())
        
        # Mock correlation calculator
        self.mock_correlation_calculator = Mock()
        self.mock_correlation_calculator.calculate_spx_change_pct = AsyncMock(return_value=0.6)  # 0.6% change
        
        # Mock database write queue to avoid blocking
        with patch('infra.database_write_queue.DatabaseWriteQueue'):
            with patch.object(AutoExecutionSystem, '_load_plans', return_value={}):
                self.auto_exec = AutoExecutionSystem(
                    db_path=self.db_path,
                    mt5_service=self.mt5_service
                )
                # Set db_write_queue to None to avoid cleanup issues
                self.auto_exec.db_write_queue = None
                # Set correlation calculator
                self.auto_exec.correlation_calculator = self.mock_correlation_calculator
        
        # Create test plan
        self.plan = TradePlan(
            plan_id="test_spx_up_pct",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=91000.0,
            stop_loss=90900.0,
            take_profit=91200.0,
            volume=0.01,
            conditions={
                "spx_up_pct": 0.5,
                "correlation_asset": "SPX",
                "spx_change_window": 60,
                "price_near": 91000.0,
                "timeframe": "M15"
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        try:
            if hasattr(self, 'auto_exec') and hasattr(self.auto_exec, 'db_write_queue') and self.auto_exec.db_write_queue:
                self.auto_exec.db_write_queue.stop()
        except:
            pass
        try:
            if hasattr(self, 'db_path') and Path(self.db_path).exists():
                Path(self.db_path).unlink()
        except:
            pass
    
    def test_condition_met_spx_above_threshold(self):
        """Test successful condition: SPX change above threshold"""
        # Mock SPX change to be 0.6% (above 0.5% threshold)
        self.mock_correlation_calculator.calculate_spx_change_pct = AsyncMock(return_value=0.6)
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertTrue(result)
    
    def test_condition_not_met_spx_below_threshold(self):
        """Test failure case: SPX change below threshold"""
        # Mock SPX change to be 0.3% (below 0.5% threshold)
        self.mock_correlation_calculator.calculate_spx_change_pct = AsyncMock(return_value=0.3)
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    def test_condition_not_met_wrong_correlation_asset(self):
        """Test failure case: wrong correlation_asset"""
        self.plan.conditions["correlation_asset"] = "DXY"
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    def test_condition_not_met_data_unavailable(self):
        """Test failure case: SPX data unavailable"""
        # Mock SPX change to return None (data unavailable)
        self.mock_correlation_calculator.calculate_spx_change_pct = AsyncMock(return_value=None)
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    def test_caching_behavior(self):
        """Test that SPX change is cached"""
        # Mock SPX change
        self.mock_correlation_calculator.calculate_spx_change_pct = AsyncMock(return_value=0.6)
        
        # First call should calculate
        result1 = self.auto_exec._check_conditions(self.plan)
        self.assertTrue(result1)
        
        # Verify calculate_spx_change_pct was called
        self.mock_correlation_calculator.calculate_spx_change_pct.assert_called_once()
        
        # Reset mock call count
        self.mock_correlation_calculator.calculate_spx_change_pct.reset_mock()
        
        # Second call should use cache (should not call calculate again)
        result2 = self.auto_exec._check_conditions(self.plan)
        self.assertTrue(result2)
        
        # Verify calculate_spx_change_pct was NOT called again (cached)
        self.mock_correlation_calculator.calculate_spx_change_pct.assert_not_called()
    
    def test_different_threshold_values(self):
        """Test with different threshold values"""
        # Test with higher threshold (0.8%)
        self.plan.conditions["spx_up_pct"] = 0.8
        self.mock_correlation_calculator.calculate_spx_change_pct = AsyncMock(return_value=0.6)
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)  # 0.6% < 0.8%
        
        # Test with lower threshold (0.3%)
        self.plan.conditions["spx_up_pct"] = 0.3
        result = self.auto_exec._check_conditions(self.plan)
        self.assertTrue(result)  # 0.6% >= 0.3%


class TestUS10YYieldChangeCondition(unittest.TestCase):
    """Test US10Y yield drop condition detection"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Mock quote object - code accesses quote.bid and quote.ask
        class MockQuote:
            def __init__(self):
                self.bid = 91000.0
                self.ask = 91010.0
        
        self.mt5_service = Mock()
        self.mt5_service.connect.return_value = True
        self.mt5_service.get_quote = Mock(return_value=MockQuote())
        
        # Mock correlation calculator
        self.mock_correlation_calculator = Mock()
        self.mock_correlation_calculator.calculate_us10y_yield_change = AsyncMock(return_value=-0.06)  # -6 bps drop
        
        # Mock database write queue to avoid blocking
        with patch('infra.database_write_queue.DatabaseWriteQueue'):
            with patch.object(AutoExecutionSystem, '_load_plans', return_value={}):
                self.auto_exec = AutoExecutionSystem(
                    db_path=self.db_path,
                    mt5_service=self.mt5_service
                )
                # Set db_write_queue to None to avoid cleanup issues
                self.auto_exec.db_write_queue = None
                # Set correlation calculator
                self.auto_exec.correlation_calculator = self.mock_correlation_calculator
        
        # Create test plan
        self.plan = TradePlan(
            plan_id="test_yield_drop",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=91000.0,
            stop_loss=90900.0,
            take_profit=91200.0,
            volume=0.01,
            conditions={
                "yield_drop": 0.05,
                "correlation_asset": "US10Y",
                "yield_change_window": 60,
                "price_near": 91000.0,
                "timeframe": "M15"
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        try:
            if hasattr(self, 'auto_exec') and hasattr(self.auto_exec, 'db_write_queue') and self.auto_exec.db_write_queue:
                self.auto_exec.db_write_queue.stop()
        except:
            pass
        try:
            if hasattr(self, 'db_path') and Path(self.db_path).exists():
                Path(self.db_path).unlink()
        except:
            pass
    
    def test_condition_met_yield_drop_above_threshold(self):
        """Test successful condition: yield drop above threshold"""
        # Mock yield change to be -0.06 (6 bps drop, above 5 bps threshold)
        self.mock_correlation_calculator.calculate_us10y_yield_change = AsyncMock(return_value=-0.06)
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertTrue(result)
    
    def test_condition_not_met_yield_drop_below_threshold(self):
        """Test failure case: yield drop below threshold"""
        # Mock yield change to be -0.03 (3 bps drop, below 5 bps threshold)
        self.mock_correlation_calculator.calculate_us10y_yield_change = AsyncMock(return_value=-0.03)
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    def test_condition_not_met_yield_increase(self):
        """Test failure case: yield increased (not a drop)"""
        # Mock yield change to be positive (yield increased)
        self.mock_correlation_calculator.calculate_us10y_yield_change = AsyncMock(return_value=0.05)
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    def test_condition_not_met_wrong_correlation_asset(self):
        """Test failure case: wrong correlation_asset"""
        self.plan.conditions["correlation_asset"] = "DXY"
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    def test_condition_not_met_data_unavailable(self):
        """Test failure case: US10Y data unavailable"""
        # Mock yield change to return None (data unavailable)
        self.mock_correlation_calculator.calculate_us10y_yield_change = AsyncMock(return_value=None)
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    def test_caching_behavior(self):
        """Test that US10Y yield change is cached"""
        # Mock yield change
        self.mock_correlation_calculator.calculate_us10y_yield_change = AsyncMock(return_value=-0.06)
        
        # First call should calculate
        result1 = self.auto_exec._check_conditions(self.plan)
        self.assertTrue(result1)
        
        # Verify calculate_us10y_yield_change was called
        self.mock_correlation_calculator.calculate_us10y_yield_change.assert_called_once()
        
        # Reset mock call count
        self.mock_correlation_calculator.calculate_us10y_yield_change.reset_mock()
        
        # Second call should use cache (should not call calculate again)
        result2 = self.auto_exec._check_conditions(self.plan)
        self.assertTrue(result2)
        
        # Verify calculate_us10y_yield_change was NOT called again (cached)
        self.mock_correlation_calculator.calculate_us10y_yield_change.assert_not_called()
    
    def test_different_threshold_values(self):
        """Test with different threshold values"""
        # Test with higher threshold (0.08 = 8 bps)
        self.plan.conditions["yield_drop"] = 0.08
        self.mock_correlation_calculator.calculate_us10y_yield_change = AsyncMock(return_value=-0.06)
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)  # 6 bps < 8 bps
        
        # Test with lower threshold (0.03 = 3 bps)
        self.plan.conditions["yield_drop"] = 0.03
        result = self.auto_exec._check_conditions(self.plan)
        self.assertTrue(result)  # 6 bps >= 3 bps


class TestCorrelationDivergenceCondition(unittest.TestCase):
    """Test DXY correlation divergence condition detection"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Mock quote object - code accesses quote.bid and quote.ask
        class MockQuote:
            def __init__(self):
                self.bid = 91000.0
                self.ask = 91010.0
        
        self.mt5_service = Mock()
        self.mt5_service.connect.return_value = True
        self.mt5_service.get_quote = Mock(return_value=MockQuote())
        self.mt5_service.get_bars = Mock(return_value=None)  # Will be mocked per test
        
        # Mock correlation calculator
        self.mock_correlation_calculator = Mock()
        self.mock_correlation_calculator.detect_dxy_divergence = AsyncMock(return_value={
            "divergence_detected": True,
            "correlation": -0.7,
            "dxy_direction": "down",
            "symbol_direction": "up",
            "data_quality": "good"
        })
        
        # Mock database write queue to avoid blocking
        with patch('infra.database_write_queue.DatabaseWriteQueue'):
            with patch.object(AutoExecutionSystem, '_load_plans', return_value={}):
                self.auto_exec = AutoExecutionSystem(
                    db_path=self.db_path,
                    mt5_service=self.mt5_service
                )
                # Set db_write_queue to None to avoid cleanup issues
                self.auto_exec.db_write_queue = None
                # Set correlation calculator
                self.auto_exec.correlation_calculator = self.mock_correlation_calculator
        
        # Create test plan
        self.plan = TradePlan(
            plan_id="test_correlation_divergence",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=91000.0,
            stop_loss=90900.0,
            take_profit=91200.0,
            volume=0.01,
            conditions={
                "correlation_divergence": True,
                "correlation_asset": "DXY",
                "divergence_threshold": -0.5,
                "divergence_window": 60,
                "price_near": 91000.0,
                "timeframe": "M15"
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        try:
            if hasattr(self, 'auto_exec') and hasattr(self.auto_exec, 'db_write_queue') and self.auto_exec.db_write_queue:
                self.auto_exec.db_write_queue.stop()
        except:
            pass
        try:
            if hasattr(self, 'db_path') and Path(self.db_path).exists():
                Path(self.db_path).unlink()
        except:
            pass
    
    def test_condition_met_strong_divergence(self):
        """Test successful condition: strong divergence detected"""
        # Mock divergence with strong negative correlation
        self.mock_correlation_calculator.detect_dxy_divergence = AsyncMock(return_value={
            "divergence_detected": True,
            "correlation": -0.7,
            "dxy_direction": "down",
            "symbol_direction": "up",
            "data_quality": "good"
        })
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertTrue(result)
    
    def test_condition_not_met_weak_divergence(self):
        """Test failure case: weak divergence (correlation not negative enough)"""
        # Mock divergence with weak negative correlation
        self.mock_correlation_calculator.detect_dxy_divergence = AsyncMock(return_value={
            "divergence_detected": False,
            "correlation": -0.3,
            "dxy_direction": "down",
            "symbol_direction": "up",
            "data_quality": "good"
        })
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    def test_condition_not_met_positive_correlation(self):
        """Test failure case: positive correlation (no divergence)"""
        # Mock positive correlation (no divergence)
        self.mock_correlation_calculator.detect_dxy_divergence = AsyncMock(return_value={
            "divergence_detected": False,
            "correlation": 0.5,
            "dxy_direction": "up",
            "symbol_direction": "up",
            "data_quality": "good"
        })
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    def test_condition_not_met_wrong_correlation_asset(self):
        """Test failure case: wrong correlation_asset"""
        self.plan.conditions["correlation_asset"] = "SPX"
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    def test_condition_not_met_data_unavailable(self):
        """Test failure case: divergence data unavailable"""
        # Mock data unavailable
        self.mock_correlation_calculator.detect_dxy_divergence = AsyncMock(return_value={
            "divergence_detected": False,
            "correlation": None,
            "dxy_direction": None,
            "symbol_direction": None,
            "data_quality": "unavailable"
        })
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    def test_condition_not_met_direction_mismatch_buy(self):
        """Test failure case: direction mismatch for BUY (DXY up, symbol down)"""
        # Mock divergence but wrong direction for BUY
        self.mock_correlation_calculator.detect_dxy_divergence = AsyncMock(return_value={
            "divergence_detected": True,
            "correlation": -0.7,
            "dxy_direction": "up",
            "symbol_direction": "down",
            "data_quality": "good"
        })
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    def test_condition_not_met_direction_mismatch_sell(self):
        """Test failure case: direction mismatch for SELL (DXY down, symbol up)"""
        # Change plan to SELL
        self.plan.direction = "SELL"
        
        # Mock divergence but wrong direction for SELL
        self.mock_correlation_calculator.detect_dxy_divergence = AsyncMock(return_value={
            "divergence_detected": True,
            "correlation": -0.7,
            "dxy_direction": "down",
            "symbol_direction": "up",
            "data_quality": "good"
        })
        
        result = self.auto_exec._check_conditions(self.plan)
        self.assertFalse(result)
    
    def test_caching_behavior(self):
        """Test that divergence result is cached"""
        # Mock divergence
        self.mock_correlation_calculator.detect_dxy_divergence = AsyncMock(return_value={
            "divergence_detected": True,
            "correlation": -0.7,
            "dxy_direction": "down",
            "symbol_direction": "up",
            "data_quality": "good"
        })
        
        # First call should calculate
        result1 = self.auto_exec._check_conditions(self.plan)
        self.assertTrue(result1)
        
        # Verify detect_dxy_divergence was called
        self.mock_correlation_calculator.detect_dxy_divergence.assert_called_once()
        
        # Reset mock call count
        self.mock_correlation_calculator.detect_dxy_divergence.reset_mock()
        
        # Second call should use cache (should not call detect again)
        result2 = self.auto_exec._check_conditions(self.plan)
        self.assertTrue(result2)
        
        # Verify detect_dxy_divergence was NOT called again (cached)
        self.mock_correlation_calculator.detect_dxy_divergence.assert_not_called()


class TestCorrelationAssetRouting(unittest.TestCase):
    """Test correlation_asset parameter validation and routing (Phase 5)"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        # Mock quote object
        class MockQuote:
            def __init__(self):
                self.bid = 91000.0
                self.ask = 91010.0
        
        self.mt5_service = Mock()
        self.mt5_service.connect.return_value = True
        self.mt5_service.get_quote = Mock(return_value=MockQuote())
        
        # Mock correlation calculator
        self.mock_correlation_calculator = Mock()
        self.mock_correlation_calculator.calculate_spx_change_pct = AsyncMock(return_value=0.6)
        self.mock_correlation_calculator.calculate_us10y_yield_change = AsyncMock(return_value=-0.06)
        
        # Mock database write queue to avoid blocking
        with patch('infra.database_write_queue.DatabaseWriteQueue'):
            with patch.object(AutoExecutionSystem, '_load_plans', return_value={}):
                self.auto_exec = AutoExecutionSystem(
                    db_path=self.db_path,
                    mt5_service=self.mt5_service
                )
                # Set db_write_queue to None to avoid cleanup issues
                self.auto_exec.db_write_queue = None
                # Set correlation calculator
                self.auto_exec.correlation_calculator = self.mock_correlation_calculator
    
    def tearDown(self):
        """Clean up test fixtures"""
        try:
            if hasattr(self, 'auto_exec') and hasattr(self.auto_exec, 'db_write_queue') and self.auto_exec.db_write_queue:
                self.auto_exec.db_write_queue.stop()
        except:
            pass
        try:
            if hasattr(self, 'db_path') and Path(self.db_path).exists():
                Path(self.db_path).unlink()
        except:
            pass
    
    @patch('auto_execution_system.mt5')
    def test_correlation_asset_spx_without_condition(self, mock_mt5):
        """Test failure: correlation_asset=SPX but no spx_up_pct condition"""
        # Create plan with correlation_asset but missing condition
        plan = TradePlan(
            plan_id="test_spx_missing_condition",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=91000.0,
            stop_loss=90900.0,
            take_profit=91200.0,
            volume=0.01,
            conditions={
                "correlation_asset": "SPX",  # Asset specified
                # Missing: "spx_up_pct": 0.5
                "price_near": 91000.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        mock_mt5.copy_rates_from_pos.return_value = []
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    def test_correlation_asset_us10y_without_condition(self, mock_mt5):
        """Test failure: correlation_asset=US10Y but no yield_drop condition"""
        # Create plan with correlation_asset but missing condition
        plan = TradePlan(
            plan_id="test_us10y_missing_condition",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=91000.0,
            stop_loss=90900.0,
            take_profit=91200.0,
            volume=0.01,
            conditions={
                "correlation_asset": "US10Y",  # Asset specified
                # Missing: "yield_drop": 0.05
                "price_near": 91000.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        mock_mt5.copy_rates_from_pos.return_value = []
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(plan)
        self.assertFalse(result)
    
    @patch('auto_execution_system.mt5')
    def test_correlation_asset_unknown(self, mock_mt5):
        """Test failure: unknown correlation_asset value"""
        # Create plan with unknown correlation_asset
        plan = TradePlan(
            plan_id="test_unknown_asset",
            symbol="BTCUSDc",
            direction="BUY",
            entry_price=91000.0,
            stop_loss=90900.0,
            take_profit=91200.0,
            volume=0.01,
            conditions={
                "correlation_asset": "UNKNOWN",  # Unknown asset
                "price_near": 91000.0
            },
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="test",
            status="pending"
        )
        
        mock_mt5.copy_rates_from_pos.return_value = []
        mock_mt5.TIMEFRAME_M15 = 16385
        
        result = self.auto_exec._check_conditions(plan)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()

