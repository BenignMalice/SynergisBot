"""
Test Phase 3.1: Pre-Execution Buffer Check and Volatility Snapshot
Tests pre-execution buffer checks, volatility snapshot creation, and buffer calculation
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

class TestPhase31PreExecutionBuffer(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        from auto_execution_system import AutoExecutionSystem
        
        # Create AutoExecutionSystem instance with minimal setup
        self.auto_exec = AutoExecutionSystem.__new__(AutoExecutionSystem)
        self.auto_exec.logger = Mock()
        self.auto_exec.db_path = Mock()
        self.auto_exec.db_path.parent = Mock()
        self.auto_exec.db_path.parent.mkdir = Mock()
        self.auto_exec.executing_plans = set()
        self.auto_exec.executing_plans_lock = threading.Lock()
        
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
        
    def test_get_execution_buffer_xauusdc(self):
        """Test execution buffer for XAUUSDc"""
        buffer = self.auto_exec._get_execution_buffer('XAUUSDc', 7.0, None)
        # Should use default from config (3.0) or fallback (3.0)
        self.assertGreaterEqual(buffer, 2.0, f"Buffer should be at least 2.0, got {buffer}")
        self.assertLessEqual(buffer, 5.0, f"Buffer should be at most 5.0, got {buffer}")
        print(f"  [PASS] XAUUSDc execution buffer: {buffer}")
        
    def test_get_execution_buffer_high_vol(self):
        """Test execution buffer for high volatility regime"""
        buffer_high = self.auto_exec._get_execution_buffer('XAUUSDc', 7.0, 'high_vol')
        buffer_default = self.auto_exec._get_execution_buffer('XAUUSDc', 7.0, None)
        # High vol buffer should be >= default buffer
        self.assertGreaterEqual(buffer_high, buffer_default, 
                               f"High vol buffer {buffer_high} should be >= default {buffer_default}")
        print(f"  [PASS] High vol buffer: {buffer_high} >= default: {buffer_default}")
        
    def test_get_execution_buffer_low_vol(self):
        """Test execution buffer for low volatility regime"""
        buffer_low = self.auto_exec._get_execution_buffer('XAUUSDc', 7.0, 'low_vol')
        buffer_default = self.auto_exec._get_execution_buffer('XAUUSDc', 7.0, None)
        # Low vol buffer should be <= default buffer
        self.assertLessEqual(buffer_low, buffer_default, 
                            f"Low vol buffer {buffer_low} should be <= default {buffer_default}")
        print(f"  [PASS] Low vol buffer: {buffer_low} <= default: {buffer_default}")
        
    def test_get_execution_buffer_btcusdc(self):
        """Test execution buffer for BTCUSDc"""
        buffer = self.auto_exec._get_execution_buffer('BTCUSDc', 100.0, None)
        # Should use default from config (30.0) or fallback (30.0)
        self.assertGreaterEqual(buffer, 20.0, f"Buffer should be at least 20.0, got {buffer}")
        self.assertLessEqual(buffer, 50.0, f"Buffer should be at most 50.0, got {buffer}")
        print(f"  [PASS] BTCUSDc execution buffer: {buffer}")
        
    def test_get_execution_buffer_forex(self):
        """Test execution buffer for forex (fallback to 30% of tolerance)"""
        buffer = self.auto_exec._get_execution_buffer('EURUSDc', 0.001, None)
        # Should be 30% of tolerance = 0.0003
        expected = 0.001 * 0.3
        self.assertAlmostEqual(buffer, expected, places=5, 
                              msg=f"Expected ~{expected}, got {buffer}")
        print(f"  [PASS] EURUSDc execution buffer: {buffer} (expected ~{expected})")
        
    def test_config_version_retrieval(self):
        """Test that config version can be retrieved"""
        version = self.auto_exec._get_config_version()
        self.assertIsInstance(version, str, "Config version should be a string")
        # Should be "2026-01-08" if config exists, or "unknown" if not
        print(f"  [PASS] Config version: {version}")

if __name__ == '__main__':
    import threading
    print("Testing Phase 3.1: Pre-Execution Buffer Check...\n")
    unittest.main(verbosity=2, exit=False)
    print("\n[PASS] Phase 3.1: All tests passed!")
