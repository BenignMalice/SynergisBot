"""
Phase 5 Tests for Knowledge Document Updates

Tests that knowledge documents have been correctly updated with tick_metrics:
- New document 24.TICK_MICROSTRUCTURE_METRICS_EMBEDDING.md exists
- Existing documents updated with tick_metrics references
- All sections properly formatted and integrated
"""

import unittest
import sys
from pathlib import Path
import re

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestNewKnowledgeDocument(unittest.TestCase):
    """Tests for new document 24.TICK_MICROSTRUCTURE_METRICS_EMBEDDING.md"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.doc_path = project_root / "docs" / "ChatGPT Knowledge Documents Updated - 06.12.25" / "ChatGPT Version" / "24.TICK_MICROSTRUCTURE_METRICS_EMBEDDING.md"
        self.assertTrue(self.doc_path.exists(), "24.TICK_MICROSTRUCTURE_METRICS_EMBEDDING.md not found")
        
        with open(self.doc_path, 'r', encoding='utf-8') as f:
            self.content = f.read()
    
    def test_document_exists(self):
        """Test that the new document exists"""
        self.assertTrue(self.doc_path.exists())
        self.assertGreater(len(self.content), 0)
    
    def test_has_purpose_section(self):
        """Test that PURPOSE section exists"""
        self.assertIn("## PURPOSE", self.content)
        self.assertIn("tick-derived microstructure metrics", self.content)
        self.assertIn("moneybot.analyse_symbol_full", self.content)
    
    def test_has_system_hierarchy(self):
        """Test that SYSTEM HIERARCHY section exists"""
        self.assertIn("## SYSTEM HIERARCHY", self.content)
        self.assertIn("KNOWLEDGE_DOC_EMBEDDING", self.content)
        self.assertIn("ORDER_FLOW_AND_ABSORPTION_FRAMEWORK_EMBEDDING", self.content)
    
    def test_has_data_structure(self):
        """Test that DATA STRUCTURE section exists with timeframes"""
        self.assertIn("## DATA STRUCTURE", self.content)
        self.assertIn("Available Timeframes", self.content)
        self.assertIn("M5", self.content)
        self.assertIn("M15", self.content)
        self.assertIn("H1", self.content)
        self.assertIn("previous_hour", self.content)
        self.assertIn("previous_day", self.content)
    
    def test_has_field_reference(self):
        """Test that field reference table exists"""
        self.assertIn("Field Reference", self.content)
        self.assertIn("realized_volatility", self.content)
        self.assertIn("volatility_ratio", self.content)
        self.assertIn("delta_volume", self.content)
        self.assertIn("cvd", self.content)
        self.assertIn("cvd_slope", self.content)
        self.assertIn("dominant_side", self.content)
        self.assertIn("spread", self.content)
        self.assertIn("absorption", self.content)
        self.assertIn("tick_rate", self.content)
        self.assertIn("trade_tick_ratio", self.content)
    
    def test_has_interpretation_rules(self):
        """Test that interpretation rules section exists"""
        self.assertIn("## INTERPRETATION RULES", self.content)
        self.assertIn("Volatility Regime Enhancement", self.content)
        self.assertIn("Order Flow Validation", self.content)
        self.assertIn("Absorption Zone Integration", self.content)
        self.assertIn("Spread-Based Risk Adjustment", self.content)
        self.assertIn("Data Quality Awareness", self.content)
    
    def test_has_confluence_integration(self):
        """Test that confluence integration section exists"""
        self.assertIn("## CONFLUENCE INTEGRATION", self.content)
        self.assertIn("Tick Metrics Confluence Contribution", self.content)
        self.assertIn("Old Weights (without tick_metrics)", self.content)
        self.assertIn("New Weights (with tick_metrics)", self.content)
        self.assertIn("Tick Factor Calculations", self.content)
    
    def test_has_display_format(self):
        """Test that display format section exists"""
        self.assertIn("## DISPLAY FORMAT (MANDATORY)", self.content)
        self.assertIn("TICK MICROSTRUCTURE:", self.content)
    
    def test_has_fallback_behavior(self):
        """Test that fallback behavior section exists"""
        self.assertIn("## FALLBACK BEHAVIOR", self.content)
        self.assertIn("tick_metrics is null", self.content)
        self.assertIn("data_available == false", self.content)
        self.assertIn("previous_day_loading == true", self.content)
    
    def test_has_priority_hierarchy(self):
        """Test that priority hierarchy section exists"""
        self.assertIn("## PRIORITY HIERARCHY FOR ORDER FLOW DATA", self.content)
        self.assertIn("tick_metrics", self.content)
        self.assertIn("btc_order_flow_metrics", self.content)
        self.assertIn("order_flow", self.content)


class TestOrderFlowDocumentUpdate(unittest.TestCase):
    """Tests for 20.ORDER_FLOW_AND_ABSORPTION_FRAMEWORK_EMBEDDING.md updates"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.doc_path = project_root / "docs" / "ChatGPT Knowledge Documents Updated - 06.12.25" / "ChatGPT Version" / "20.ORDER_FLOW_AND_ABSORPTION_FRAMEWORK_EMBEDDING.md"
        self.assertTrue(self.doc_path.exists(), "20.ORDER_FLOW_AND_ABSORPTION_FRAMEWORK_EMBEDDING.md not found")
        
        with open(self.doc_path, 'r', encoding='utf-8') as f:
            self.content = f.read()
    
    def test_has_enhanced_data_source_section(self):
        """Test that Enhanced Data Source section exists"""
        self.assertIn("### Enhanced Data Source: `tick_metrics` (All Symbols) NEW", self.content)
        self.assertIn("response.data.tick_metrics", self.content)
    
    def test_has_tick_metrics_fields(self):
        """Test that tick_metrics fields are documented"""
        self.assertIn("delta_volume", self.content)
        self.assertIn("cvd", self.content)
        self.assertIn("cvd_slope", self.content)
        self.assertIn("absorption.count", self.content)
        self.assertIn("absorption.zones", self.content)
        self.assertIn("absorption.avg_strength", self.content)
    
    def test_has_priority_hierarchy_update(self):
        """Test that priority hierarchy is updated"""
        self.assertIn("Priority Hierarchy Update", self.content)
        # Check that tick_metrics is listed first
        tick_pos = self.content.find("tick_metrics (if available)")
        btc_pos = self.content.find("btc_order_flow_metrics (BTC only)")
        order_pos = self.content.find("order_flow (all symbols)")
        
        self.assertGreater(tick_pos, 0, "tick_metrics not found in priority hierarchy")
        self.assertGreater(btc_pos, 0, "btc_order_flow_metrics not found")
        self.assertGreater(order_pos, 0, "order_flow not found")
        self.assertLess(tick_pos, btc_pos, "tick_metrics should come before btc_order_flow_metrics")
        self.assertLess(btc_pos, order_pos, "btc_order_flow_metrics should come before order_flow")
    
    def test_placement_after_btc_section(self):
        """Test that tick_metrics section is placed after BTC section"""
        btc_section = self.content.find("⚠️ IMPORTANT**: This tool is BTC-only")
        tick_section = self.content.find("Enhanced Data Source: `tick_metrics`")
        
        self.assertGreater(btc_section, 0, "BTC section not found")
        self.assertGreater(tick_section, 0, "tick_metrics section not found")
        self.assertGreater(tick_section, btc_section, "tick_metrics section should come after BTC section")


class TestVolatilityDocumentUpdate(unittest.TestCase):
    """Tests for 8.VOLATILITY_REGIME_STRATEGIES_EMBEDDING.md updates"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.doc_path = project_root / "docs" / "ChatGPT Knowledge Documents Updated - 06.12.25" / "ChatGPT Version" / "8.VOLATILITY_REGIME_STRATEGIES_EMBEDDING.md"
        self.assertTrue(self.doc_path.exists(), "8.VOLATILITY_REGIME_STRATEGIES_EMBEDDING.md not found")
        
        with open(self.doc_path, 'r', encoding='utf-8') as f:
            self.content = f.read()
    
    def test_has_tick_based_volatility_section(self):
        """Test that tick-based volatility enhancement section exists"""
        self.assertIn("# 2.5. TICK-BASED VOLATILITY ENHANCEMENT NEW", self.content)
    
    def test_has_tick_volatility_integration(self):
        """Test that tick_volatility_integration section exists"""
        self.assertIn("tick_volatility_integration:", self.content)
        self.assertIn("tick_metrics.realized_volatility", self.content)
        self.assertIn("tick_metrics.volatility_ratio", self.content)
        self.assertIn("3-5x faster", self.content)
    
    def test_has_volatility_regime_with_ticks(self):
        """Test that volatility_regime_with_ticks section exists"""
        self.assertIn("volatility_regime_with_ticks:", self.content)
        self.assertIn("LOW_COMPRESSION:", self.content)
        self.assertIn("EXPANDING_BREAKOUT:", self.content)
        self.assertIn("HIGH_EXTREME:", self.content)
        self.assertIn("tick_indicators:", self.content)
    
    def test_has_tick_volatility_override(self):
        """Test that tick_volatility_override section exists"""
        self.assertIn("tick_volatility_override:", self.content)
        self.assertIn("tick_metrics takes priority", self.content)
        self.assertIn("Note contradiction", self.content)
        self.assertIn("Adjust confidence by -10%", self.content)
    
    def test_placement_before_section_3(self):
        """Test that section is placed before section 3"""
        tick_section = self.content.find("# 2.5. TICK-BASED VOLATILITY ENHANCEMENT NEW")
        section_3 = self.content.find("# 3. VOLATILITY ↔ STRUCTURE RULES")
        
        self.assertGreater(tick_section, 0, "Tick-based volatility section not found")
        self.assertGreater(section_3, 0, "Section 3 not found")
        self.assertLess(tick_section, section_3, "Tick-based section should come before section 3")


class TestConfluenceDocumentUpdate(unittest.TestCase):
    """Tests for 23.CONFLUENCE_CALCULATION_EMBEDDING.md updates"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.doc_path = project_root / "docs" / "ChatGPT Knowledge Documents Updated - 06.12.25" / "ChatGPT Version" / "23.CONFLUENCE_CALCULATION_EMBEDDING.md"
        self.assertTrue(self.doc_path.exists(), "23.CONFLUENCE_CALCULATION_EMBEDDING.md not found")
        
        with open(self.doc_path, 'r', encoding='utf-8') as f:
            self.content = f.read()
    
    def test_has_tick_microstructure_factors_section(self):
        """Test that Tick Microstructure Factors section exists"""
        self.assertIn("## Tick Microstructure Factors (When Available) NEW", self.content)
    
    def test_has_factors_when_tick_metrics_available(self):
        """Test that factors_when_tick_metrics_available section exists"""
        self.assertIn("factors_when_tick_metrics_available:", self.content)
        self.assertIn("tick_volatility_alignment:", self.content)
        self.assertIn("tick_flow_confirmation:", self.content)
        self.assertIn("absorption_risk_penalty:", self.content)
    
    def test_has_weight_rebalancing(self):
        """Test that weight_rebalancing section exists"""
        self.assertIn("weight_rebalancing:", self.content)
        self.assertIn("when_tick_metrics_available:", self.content)
        self.assertIn("when_tick_metrics_unavailable:", self.content)
        self.assertIn("Reduce trend_alignment from 30% to 25%", self.content)
        self.assertIn("Reduce momentum_alignment from 25% to 20%", self.content)
        self.assertIn("Reduce support_resistance from 25% to 20%", self.content)
        self.assertIn("Reduce volatility_health from 10% to 5%", self.content)
        self.assertIn("Total remains 100%", self.content)
    
    def test_has_factor_calculations(self):
        """Test that factor calculations are documented"""
        self.assertIn("volatility_ratio in optimal range", self.content)
        self.assertIn("cvd_slope + structure aligned", self.content)
        self.assertIn("absorption.count == 0", self.content)
    
    def test_placement_after_m5_m15_h1_section(self):
        """Test that section is placed after M5/M15/H1 section"""
        m5_section = self.content.find("## M5, M15, H1 Timeframes")
        tick_section = self.content.find("## Tick Microstructure Factors")
        score_section = self.content.find("# SCORE_INTERPRETATION")
        
        self.assertGreater(m5_section, 0, "M5/M15/H1 section not found")
        self.assertGreater(tick_section, 0, "Tick Microstructure Factors section not found")
        self.assertGreater(score_section, 0, "SCORE_INTERPRETATION section not found")
        self.assertGreater(tick_section, m5_section, "Tick section should come after M5/M15/H1 section")
        self.assertLess(tick_section, score_section, "Tick section should come before SCORE_INTERPRETATION")


class TestKnowledgeDocumentUpdate(unittest.TestCase):
    """Tests for 1.KNOWLEDGE_DOC_EMBEDDING.md updates"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.doc_path = project_root / "docs" / "ChatGPT Knowledge Documents Updated - 06.12.25" / "ChatGPT Version" / "1.KNOWLEDGE_DOC_EMBEDDING.md"
        self.assertTrue(self.doc_path.exists(), "1.KNOWLEDGE_DOC_EMBEDDING.md not found")
        
        with open(self.doc_path, 'r', encoding='utf-8') as f:
            self.content = f.read()
    
    def test_has_tick_microstructure_rule(self):
        """Test that Tick Microstructure Data Usage rule exists"""
        self.assertIn("### RULE: Tick Microstructure Data Usage NEW", self.content)
    
    def test_has_mandatory_requirements(self):
        """Test that all 5 mandatory requirements are present"""
        self.assertIn("MUST use for volatility assessment", self.content)
        self.assertIn("MUST use for flow validation", self.content)
        self.assertIn("MUST check absorption zones", self.content)
        self.assertIn("MUST note spread conditions", self.content)
        self.assertIn("MUST rebalance confluence weights", self.content)
    
    def test_has_volatility_assessment_details(self):
        """Test that volatility assessment details are present"""
        self.assertIn("tick_metrics.realized_volatility is more accurate than ATR", self.content)
        self.assertIn("tick_metrics.volatility_ratio detects regime changes faster", self.content)
    
    def test_has_flow_validation_details(self):
        """Test that flow validation details are present"""
        self.assertIn("tick_metrics.delta_volume validates CHOCH/BOS", self.content)
        self.assertIn("tick_metrics.cvd_slope confirms or contradicts structure", self.content)
    
    def test_has_absorption_zones_details(self):
        """Test that absorption zones details are present"""
        self.assertIn("tick_metrics.absorption.zones are reversal warning levels", self.content)
        self.assertIn("Entry near absorption zone requires explicit acknowledgment", self.content)
    
    def test_has_spread_conditions_details(self):
        """Test that spread conditions details are present"""
        self.assertIn("tick_metrics.spread.std > 1.5 x mean", self.content)
        self.assertIn("elevated execution risk", self.content)
    
    def test_has_confluence_rebalancing_reference(self):
        """Test that confluence rebalancing reference is present"""
        self.assertIn("CONFLUENCE_CALCULATION_EMBEDDING", self.content)
    
    def test_has_fallback_behavior(self):
        """Test that fallback behavior is documented"""
        self.assertIn("If tick_metrics is null", self.content)
        self.assertIn("Tick microstructure data unavailable", self.content)
        self.assertIn("use original confluence weights", self.content)
    
    def test_placement_after_priority_hierarchy(self):
        """Test that rule is placed after Data Field Priority Hierarchy"""
        priority_section = self.content.find("### RULE: Data Field Priority Hierarchy")
        tick_rule = self.content.find("### RULE: Tick Microstructure Data Usage NEW")
        instruction_section = self.content.find("### RULE: Instruction Precedence")
        
        self.assertGreater(priority_section, 0, "Priority hierarchy section not found")
        self.assertGreater(tick_rule, 0, "Tick microstructure rule not found")
        self.assertGreater(instruction_section, 0, "Instruction precedence section not found")
        self.assertGreater(tick_rule, priority_section, "Tick rule should come after priority hierarchy")
        self.assertLess(tick_rule, instruction_section, "Tick rule should come before instruction precedence")


class TestDocumentIntegration(unittest.TestCase):
    """Tests for cross-document integration and consistency"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.docs_dir = project_root / "docs" / "ChatGPT Knowledge Documents Updated - 06.12.25" / "ChatGPT Version"
        
        # Read all relevant documents
        self.tick_doc = self.docs_dir / "24.TICK_MICROSTRUCTURE_METRICS_EMBEDDING.md"
        self.order_flow_doc = self.docs_dir / "20.ORDER_FLOW_AND_ABSORPTION_FRAMEWORK_EMBEDDING.md"
        self.volatility_doc = self.docs_dir / "8.VOLATILITY_REGIME_STRATEGIES_EMBEDDING.md"
        self.confluence_doc = self.docs_dir / "23.CONFLUENCE_CALCULATION_EMBEDDING.md"
        self.knowledge_doc = self.docs_dir / "1.KNOWLEDGE_DOC_EMBEDDING.md"
        
        with open(self.tick_doc, 'r', encoding='utf-8') as f:
            self.tick_content = f.read()
        with open(self.order_flow_doc, 'r', encoding='utf-8') as f:
            self.order_flow_content = f.read()
        with open(self.volatility_doc, 'r', encoding='utf-8') as f:
            self.volatility_content = f.read()
        with open(self.confluence_doc, 'r', encoding='utf-8') as f:
            self.confluence_content = f.read()
        with open(self.knowledge_doc, 'r', encoding='utf-8') as f:
            self.knowledge_content = f.read()
    
    def test_consistent_priority_hierarchy(self):
        """Test that priority hierarchy is consistent across documents"""
        # Check that tick_metrics is consistently prioritized
        self.assertIn("tick_metrics", self.tick_content)
        self.assertIn("tick_metrics", self.order_flow_content)
        self.assertIn("tick_metrics", self.knowledge_content)
    
    def test_consistent_field_names(self):
        """Test that field names are consistent across documents"""
        # Check key fields are mentioned consistently
        self.assertIn("delta_volume", self.tick_content)
        self.assertIn("delta_volume", self.order_flow_content)
        
        self.assertIn("cvd_slope", self.tick_content)
        self.assertIn("cvd_slope", self.order_flow_content)
        self.assertIn("cvd_slope", self.confluence_content)
        
        self.assertIn("volatility_ratio", self.tick_content)
        self.assertIn("volatility_ratio", self.volatility_content)
        self.assertIn("volatility_ratio", self.confluence_content)
    
    def test_references_to_other_documents(self):
        """Test that documents reference each other correctly"""
        # Tick doc should reference other docs
        self.assertIn("ORDER_FLOW_AND_ABSORPTION_FRAMEWORK_EMBEDDING", self.tick_content)
        self.assertIn("VOLATILITY_REGIME_STRATEGIES_EMBEDDING", self.tick_content)
        self.assertIn("CONFLUENCE_CALCULATION_EMBEDDING", self.tick_content)
        
        # Knowledge doc should reference confluence doc
        self.assertIn("CONFLUENCE_CALCULATION_EMBEDDING", self.knowledge_content)
    
    def test_weight_rebalancing_consistency(self):
        """Test that weight rebalancing is consistent between documents"""
        # Check that both documents mention the same weight changes
        self.assertIn("30% to 25%", self.confluence_content)
        self.assertIn("25% to 20%", self.confluence_content)
        self.assertIn("10% to 5%", self.confluence_content)
        self.assertIn("Total remains 100%", self.confluence_content)


def run_tests():
    """Run all Phase 5 tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestNewKnowledgeDocument))
    suite.addTests(loader.loadTestsFromTestCase(TestOrderFlowDocumentUpdate))
    suite.addTests(loader.loadTestsFromTestCase(TestVolatilityDocumentUpdate))
    suite.addTests(loader.loadTestsFromTestCase(TestConfluenceDocumentUpdate))
    suite.addTests(loader.loadTestsFromTestCase(TestKnowledgeDocumentUpdate))
    suite.addTests(loader.loadTestsFromTestCase(TestDocumentIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 70)
    print("Phase 5 Knowledge Document Updates Tests")
    print("=" * 70)
    print()
    
    success = run_tests()
    
    print()
    print("=" * 70)
    if success:
        print("All Phase 5 tests passed!")
    else:
        print("Some tests failed. Check output above.")
    print("=" * 70)
    
    sys.exit(0 if success else 1)

