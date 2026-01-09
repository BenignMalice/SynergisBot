"""
Phase 4 Tests for OpenAI Schema Updates

Tests that openai.yaml has been correctly updated with tick_metrics documentation:
- Tool description section includes tick metrics
- Enhanced Data Fields section includes tick_metrics field
- Missing data acknowledgment includes tick_metrics
- YAML syntax is valid
"""

import unittest
import sys
import yaml
from pathlib import Path
import re

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestOpenAISchemaUpdates(unittest.TestCase):
    """Tests for OpenAI schema updates"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.yaml_path = project_root / "openai.yaml"
        self.assertTrue(self.yaml_path.exists(), "openai.yaml file not found")
        
        # Read YAML file
        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            self.yaml_content = f.read()
    
    def test_yaml_syntax_valid(self):
        """Test that YAML syntax is valid"""
        try:
            with open(self.yaml_path, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)
            self.assertTrue(True, "YAML syntax is valid")
        except yaml.YAMLError as e:
            self.fail(f"YAML syntax error: {e}")
    
    def test_tick_metrics_in_tool_description(self):
        """Test that tick metrics is mentioned in tool description section"""
        # Should be after "M1 Microstructure Analysis"
        self.assertIn("Tick Microstructure Metrics", self.yaml_content)
        self.assertIn("Pre-aggregated tick-level analytics", self.yaml_content)
        self.assertIn("M5/M15/H1 timeframe metrics", self.yaml_content)
        self.assertIn("realized volatility", self.yaml_content)
        self.assertIn("delta volume", self.yaml_content)
        self.assertIn("CVD slope", self.yaml_content)
        self.assertIn("Previous hour summary", self.yaml_content)
        self.assertIn("Previous day baseline", self.yaml_content)
        self.assertIn("Data refreshed every 60 seconds", self.yaml_content)
        self.assertIn("MT5 true tick data", self.yaml_content)
    
    def test_tick_metrics_in_enhanced_data_fields(self):
        """Test that tick_metrics field is documented in Enhanced Data Fields section"""
        # Should be after symbol_constraints
        self.assertIn("tick_metrics: {...}|null", self.yaml_content)
        self.assertIn("Tick-derived microstructure metrics", self.yaml_content)
        self.assertIn("Contains M5, M15, H1, previous_hour, previous_day", self.yaml_content)
        self.assertIn("Background generator not running", self.yaml_content)
    
    def test_tick_metrics_field_documentation(self):
        """Test that all tick_metrics fields are documented"""
        # Check for field descriptions
        self.assertIn("realized_volatility:", self.yaml_content)
        self.assertIn("volatility_ratio:", self.yaml_content)
        self.assertIn("delta_volume:", self.yaml_content)
        self.assertIn("cvd:", self.yaml_content)
        self.assertIn("cvd_slope:", self.yaml_content)
        self.assertIn("dominant_side:", self.yaml_content)
        self.assertIn("spread:", self.yaml_content)
        self.assertIn("absorption:", self.yaml_content)
        self.assertIn("tick_rate:", self.yaml_content)
        self.assertIn("liquidity_voids:", self.yaml_content)
        self.assertIn("trade_tick_ratio:", self.yaml_content)
    
    def test_tick_metrics_interpretation_guidance(self):
        """Test that interpretation guidance is included"""
        self.assertIn("TICK METRICS INTERPRETATION:", self.yaml_content)
        self.assertIn("Use tick_metrics.M5 for execution-level precision", self.yaml_content)
        self.assertIn("Use tick_metrics.M15 for setup validation", self.yaml_content)
        self.assertIn("Use tick_metrics.H1 for session context", self.yaml_content)
        self.assertIn("Use tick_metrics.previous_hour", self.yaml_content)
        self.assertIn("Use tick_metrics.previous_day", self.yaml_content)
        self.assertIn("cvd_slope confirms or contradicts CHOCH/BOS validity", self.yaml_content)
        self.assertIn("absorption zones indicate potential reversal traps", self.yaml_content)
        self.assertIn("realized_volatility is more precise than ATR", self.yaml_content)
    
    def test_tick_metrics_in_missing_data_acknowledgment(self):
        """Test that tick_metrics is included in missing data acknowledgment"""
        # Should be in the step-by-step process
        self.assertIn("Check response.data.tick_metrics == null", self.yaml_content)
        self.assertIn("Tick microstructure metrics unavailable", self.yaml_content)
        self.assertIn("ATR-based volatility estimates", self.yaml_content)
        
        # Should be in examples
        self.assertIn("Example 6: if response.data.tick_metrics == null", self.yaml_content)
    
    def test_tick_metrics_after_symbol_constraints(self):
        """Test that tick_metrics appears after symbol_constraints in Enhanced Data Fields"""
        # Find positions of both fields
        symbol_constraints_pos = self.yaml_content.find("symbol_constraints:")
        tick_metrics_pos = self.yaml_content.find("tick_metrics:")
        
        # tick_metrics should come after symbol_constraints
        self.assertGreater(symbol_constraints_pos, 0, "symbol_constraints not found")
        self.assertGreater(tick_metrics_pos, 0, "tick_metrics not found")
        self.assertGreater(tick_metrics_pos, symbol_constraints_pos, 
                          "tick_metrics should appear after symbol_constraints")
    
    def test_tick_metrics_after_m1_microstructure(self):
        """Test that tick_metrics appears after M1 Microstructure in tool description"""
        # Find positions
        m1_pos = self.yaml_content.find("M1 Microstructure Analysis")
        tick_metrics_pos = self.yaml_content.find("Tick Microstructure Metrics")
        
        self.assertGreater(m1_pos, 0, "M1 Microstructure Analysis not found")
        self.assertGreater(tick_metrics_pos, 0, "Tick Microstructure Metrics not found")
        self.assertGreater(tick_metrics_pos, m1_pos,
                          "Tick Microstructure Metrics should appear after M1 Microstructure Analysis")
    
    def test_complete_field_coverage(self):
        """Test that all expected fields are documented"""
        expected_fields = [
            "realized_volatility",
            "volatility_ratio",
            "delta_volume",
            "cvd",
            "cvd_slope",
            "dominant_side",
            "spread",
            "absorption",
            "tick_rate",
            "liquidity_voids",
            "trade_tick_ratio"
        ]
        
        for field in expected_fields:
            # Check that field is mentioned in the documentation
            self.assertIn(field, self.yaml_content.lower() or field, 
                         f"Field '{field}' not found in documentation")
    
    def test_timeframe_coverage(self):
        """Test that all timeframes are mentioned"""
        expected_timeframes = ["M5", "M15", "H1", "previous_hour", "previous_day"]
        
        for tf in expected_timeframes:
            self.assertIn(tf, self.yaml_content, 
                         f"Timeframe '{tf}' not found in documentation")


class TestOpenAISchemaStructure(unittest.TestCase):
    """Tests for YAML structure and formatting"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.yaml_path = project_root / "openai.yaml"
        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            self.yaml_content = f.read()
            self.lines = self.yaml_content.split('\n')
    
    def test_no_duplicate_tick_metrics_sections(self):
        """Test that tick_metrics is not duplicated"""
        # Count occurrences of "tick_metrics:" (should be in Enhanced Data Fields section)
        tick_metrics_count = self.yaml_content.count("tick_metrics:")
        # Should appear once in the field definition
        self.assertGreaterEqual(tick_metrics_count, 1, 
                               "tick_metrics should appear at least once")
        # Should not appear too many times (indicating duplication)
        self.assertLessEqual(tick_metrics_count, 5, 
                            "tick_metrics appears too many times (possible duplication)")
    
    def test_consistent_formatting(self):
        """Test that formatting is consistent with other fields"""
        # Check that tick_metrics follows the same pattern as other fields
        # Should have "# - tick_metrics:" pattern like other enhanced data fields
        self.assertIn("# - tick_metrics:", self.yaml_content)
        
        # Should have interpretation comments
        self.assertIn("#   TICK METRICS INTERPRETATION:", self.yaml_content)
    
    def test_proper_indentation(self):
        """Test that indentation is correct"""
        # Find tick_metrics line
        for i, line in enumerate(self.lines):
            if "tick_metrics:" in line and "# - tick_metrics:" in line:
                # Should be at same indentation level as other enhanced data fields
                # Check that it starts with "# - " (comment with dash)
                self.assertTrue(line.strip().startswith("# - tick_metrics:"),
                               f"Line {i+1}: tick_metrics should start with '# - tick_metrics:'")
                break
        else:
            self.fail("tick_metrics field definition not found")


def run_tests():
    """Run all Phase 4 tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestOpenAISchemaUpdates))
    suite.addTests(loader.loadTestsFromTestCase(TestOpenAISchemaStructure))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 70)
    print("Phase 4 OpenAI Schema Updates Tests")
    print("=" * 70)
    print()
    
    success = run_tests()
    
    print()
    print("=" * 70)
    if success:
        print("All Phase 4 tests passed!")
    else:
        print("Some tests failed. Check output above.")
    print("=" * 70)
    
    sys.exit(0 if success else 1)

