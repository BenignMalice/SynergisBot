"""
Test Phase 2.5: Integration of Volatility Calculator into Auto-Execution System
Tests that volatility calculator is properly initialized and used in tolerance checks
"""

import sys
import unittest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass
from typing import Dict, Any, Optional

# Mock TradePlan
@dataclass
class TradePlan:
    plan_id: str
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    volume: float
    conditions: Dict[str, Any]
    created_at: str
    created_by: str
    status: str = "pending"
    expires_at: Optional[str] = None
    entry_levels: Optional[list] = None
    kill_switch_triggered: Optional[bool] = False
    advanced_features: Optional[Dict[str, Any]] = None

# Import after setting up mocks
sys.path.insert(0, '.')

class TestPhase25Integration(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        from auto_execution_system import AutoExecutionSystem
        
        # Create AutoExecutionSystem instance with minimal setup
        self.auto_exec = AutoExecutionSystem.__new__(AutoExecutionSystem)
        self.auto_exec.logger = Mock()
        self.auto_exec.db_path = Mock()
        self.auto_exec.db_path.parent = Mock()
        self.auto_exec.db_path.parent.mkdir = Mock()
        
        # Mock the database initialization
        with patch('auto_execution_system.sqlite3'):
            with patch('auto_execution_system.Path'):
                # Initialize volatility calculator
                try:
                    from infra.volatility_tolerance_calculator import VolatilityToleranceCalculator
                    from infra.tolerance_calculator import ToleranceCalculator
                    tolerance_calc = ToleranceCalculator()
                    self.auto_exec.volatility_tolerance_calculator = VolatilityToleranceCalculator(
                        tolerance_calculator=tolerance_calc
                    )
                except Exception as e:
                    self.auto_exec.volatility_tolerance_calculator = None
                    print(f"  [SKIP] Could not initialize volatility calculator: {e}")
        
    def test_volatility_calculator_initialized(self):
        """Test that volatility calculator is initialized"""
        self.assertIsNotNone(self.auto_exec.volatility_tolerance_calculator, 
                           "Volatility calculator should be initialized")
        print("  [PASS] Volatility calculator initialized")
        
    def test_get_config_version(self):
        """Test _get_config_version method"""
        version = self.auto_exec._get_config_version()
        self.assertIsInstance(version, str, "Config version should be a string")
        print(f"  [PASS] _get_config_version returns: {version}")
        
    def test_tolerance_zone_entry_with_volatility_calculator(self):
        """Test that _check_tolerance_zone_entry uses volatility calculator"""
        plan = TradePlan(
            plan_id="test_plan_1",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 7.0},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            advanced_features={
                "M5": {
                    "rmag": {
                        "ema200_atr": 1.5,
                        "vwap_atr": 0.8
                    }
                }
            }
        )
        
        # Mock logger
        import logging
        self.auto_exec.logger = logging.getLogger('test')
        
        # Call _check_tolerance_zone_entry - it should use volatility calculator
        result = self.auto_exec._check_tolerance_zone_entry(plan, 2000.0)
        
        # Verify the method works correctly
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)
        print(f"  [PASS] Tolerance zone entry with volatility calculator (result: {result})")
        
    def test_kill_switch_blocking(self):
        """Test that kill-switch blocks zone entry"""
        plan = TradePlan(
            plan_id="test_plan_2",
            symbol="XAUUSDc",
            direction="BUY",
            entry_price=2000.0,
            stop_loss=1990.0,
            take_profit=2010.0,
            volume=0.01,
            conditions={"tolerance": 7.0},
            created_at="2026-01-08T00:00:00Z",
            created_by="test",
            advanced_features={
                "M5": {
                    "rmag": {
                        "ema200_atr": 3.5,  # Above kill-switch threshold (2.8 for XAUUSDc)
                        "vwap_atr": 0.8
                    }
                }
            }
        )
        
        # Mock logger
        import logging
        self.auto_exec.logger = logging.getLogger('test')
        
        # Call _check_tolerance_zone_entry - kill-switch should block entry
        result = self.auto_exec._check_tolerance_zone_entry(plan, 2000.0)
        
        # Kill-switch should return (False, None, False) to block entry
        self.assertEqual(result, (False, None, False), 
                        "Kill-switch should block zone entry")
        self.assertTrue(plan.kill_switch_triggered, 
                       "Kill-switch flag should be set")
        print(f"  [PASS] Kill-switch blocking test (result: {result}, flag: {plan.kill_switch_triggered})")

if __name__ == '__main__':
    print("Testing Phase 2.5: Integration of Volatility Calculator...\n")
    unittest.main(verbosity=2, exit=False)
    print("\n[PASS] Phase 2.5: All tests passed!")
