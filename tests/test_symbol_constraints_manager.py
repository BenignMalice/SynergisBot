"""
Unit tests for SymbolConstraintsManager
"""

import unittest
import json
import tempfile
import os
from pathlib import Path

# Import the manager
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.symbol_constraints_manager import SymbolConstraintsManager


class TestSymbolConstraintsManager(unittest.TestCase):
    """Test cases for SymbolConstraintsManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create temporary config file
        self.temp_config = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_config_path = self.temp_config.name
        self.temp_config.close()
        
        # Write test config
        test_config = {
            "XAUUSD": {
                "max_concurrent_trades_for_symbol": 2,
                "max_total_risk_on_symbol_pct": 3.0,
                "allowed_strategies": ["INSIDE_BAR_VOLATILITY_TRAP"],
                "risk_profile": "normal",
                "banned_strategies": ["SWING_TREND_FOLLOWING"],
                "max_position_size_pct": 5.0
            },
            "BTCUSD": {
                "max_concurrent_trades_for_symbol": 1,
                "max_total_risk_on_symbol_pct": 2.0,
                "allowed_strategies": [],
                "risk_profile": "conservative",
                "banned_strategies": [],
                "max_position_size_pct": 3.0
            }
        }
        
        with open(self.temp_config_path, 'w') as f:
            json.dump(test_config, f)
        
        self.manager = SymbolConstraintsManager(config_path=self.temp_config_path)
    
    def tearDown(self):
        """Clean up test fixtures"""
        if os.path.exists(self.temp_config_path):
            os.unlink(self.temp_config_path)
    
    def test_initialization(self):
        """Test manager initialization"""
        self.assertIsNotNone(self.manager)
        self.assertIsNotNone(self.manager.constraints)
    
    def test_get_symbol_constraints_existing(self):
        """Test getting constraints for existing symbol"""
        constraints = self.manager.get_symbol_constraints("XAUUSD")
        
        self.assertIsNotNone(constraints)
        self.assertEqual(constraints["max_concurrent_trades_for_symbol"], 2)
        self.assertEqual(constraints["max_total_risk_on_symbol_pct"], 3.0)
        self.assertEqual(constraints["risk_profile"], "normal")
        self.assertIn("INSIDE_BAR_VOLATILITY_TRAP", constraints["allowed_strategies"])
        self.assertIn("SWING_TREND_FOLLOWING", constraints["banned_strategies"])
    
    def test_get_symbol_constraints_with_c_suffix(self):
        """Test getting constraints with 'c' suffix"""
        constraints = self.manager.get_symbol_constraints("XAUUSDc")
        
        # Should match XAUUSD
        self.assertEqual(constraints["max_concurrent_trades_for_symbol"], 2)
        self.assertEqual(constraints["risk_profile"], "normal")
    
    def test_get_symbol_constraints_defaults(self):
        """Test getting constraints for non-existent symbol (should return defaults)"""
        constraints = self.manager.get_symbol_constraints("UNKNOWN")
        
        self.assertIsNotNone(constraints)
        self.assertEqual(constraints["max_concurrent_trades_for_symbol"], 2)  # Default
        self.assertEqual(constraints["max_total_risk_on_symbol_pct"], 3.0)  # Default
        self.assertEqual(constraints["risk_profile"], "normal")  # Default
        self.assertEqual(constraints["allowed_strategies"], [])  # Default (all allowed)
        self.assertEqual(constraints["banned_strategies"], [])  # Default
    
    def test_is_strategy_allowed_allowed(self):
        """Test strategy allowed check - strategy in allowed list"""
        result = self.manager.is_strategy_allowed("XAUUSD", "INSIDE_BAR_VOLATILITY_TRAP")
        self.assertTrue(result)
    
    def test_is_strategy_allowed_banned(self):
        """Test strategy allowed check - strategy in banned list"""
        result = self.manager.is_strategy_allowed("XAUUSD", "SWING_TREND_FOLLOWING")
        self.assertFalse(result)
    
    def test_is_strategy_allowed_empty_allowed_list(self):
        """Test strategy allowed check - empty allowed list means all allowed"""
        result = self.manager.is_strategy_allowed("BTCUSD", "ANY_STRATEGY")
        self.assertTrue(result)  # Empty allowed list = all allowed
    
    def test_is_strategy_allowed_not_in_allowed_list(self):
        """Test strategy allowed check - strategy not in allowed list (when list is non-empty)"""
        result = self.manager.is_strategy_allowed("XAUUSD", "UNKNOWN_STRATEGY")
        self.assertFalse(result)  # Not in allowed list
    
    def test_get_max_concurrent_trades(self):
        """Test getting max concurrent trades"""
        result = self.manager.get_max_concurrent_trades("XAUUSD")
        self.assertEqual(result, 2)
        
        result = self.manager.get_max_concurrent_trades("BTCUSD")
        self.assertEqual(result, 1)
        
        result = self.manager.get_max_concurrent_trades("UNKNOWN")
        self.assertEqual(result, 2)  # Default
    
    def test_get_max_risk_pct(self):
        """Test getting max risk percentage"""
        result = self.manager.get_max_risk_pct("XAUUSD")
        self.assertEqual(result, 3.0)
        
        result = self.manager.get_max_risk_pct("BTCUSD")
        self.assertEqual(result, 2.0)
        
        result = self.manager.get_max_risk_pct("UNKNOWN")
        self.assertEqual(result, 3.0)  # Default
    
    def test_get_risk_profile(self):
        """Test getting risk profile"""
        result = self.manager.get_risk_profile("XAUUSD")
        self.assertEqual(result, "normal")
        
        result = self.manager.get_risk_profile("BTCUSD")
        self.assertEqual(result, "conservative")
        
        result = self.manager.get_risk_profile("UNKNOWN")
        self.assertEqual(result, "normal")  # Default
    
    def test_load_constraints_missing_file(self):
        """Test loading constraints when file doesn't exist"""
        manager = SymbolConstraintsManager(config_path="nonexistent.json")
        
        # Should use defaults
        constraints = manager.get_symbol_constraints("ANY_SYMBOL")
        self.assertEqual(constraints["max_concurrent_trades_for_symbol"], 2)
    
    def test_load_constraints_invalid_json(self):
        """Test loading constraints with invalid JSON"""
        # Write invalid JSON
        with open(self.temp_config_path, 'w') as f:
            f.write("invalid json {")
        
        manager = SymbolConstraintsManager(config_path=self.temp_config_path)
        
        # Should use defaults
        constraints = manager.get_symbol_constraints("ANY_SYMBOL")
        self.assertEqual(constraints["max_concurrent_trades_for_symbol"], 2)
    
    def test_reload_constraints(self):
        """Test reloading constraints"""
        # Get initial constraints
        initial = self.manager.get_symbol_constraints("XAUUSD")
        self.assertEqual(initial["max_concurrent_trades_for_symbol"], 2)
        
        # Update config file
        updated_config = {
            "XAUUSD": {
                "max_concurrent_trades_for_symbol": 5,
                "max_total_risk_on_symbol_pct": 3.0,
                "allowed_strategies": [],
                "risk_profile": "normal",
                "banned_strategies": [],
                "max_position_size_pct": 5.0
            }
        }
        
        with open(self.temp_config_path, 'w') as f:
            json.dump(updated_config, f)
        
        # Reload
        self.manager.reload_constraints()
        
        # Check updated value
        updated = self.manager.get_symbol_constraints("XAUUSD")
        self.assertEqual(updated["max_concurrent_trades_for_symbol"], 5)


if __name__ == '__main__':
    unittest.main()

