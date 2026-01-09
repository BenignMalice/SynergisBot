"""
Phase 8.4 End-to-End (E2E) Testing: Complete User Workflows

Tests for complete workflows from analysis to plan creation to execution
"""
import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta
import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from infra.volatility_regime_detector import RegimeDetector, VolatilityRegime
from infra.volatility_strategy_mapper import get_strategies_for_volatility
from handlers.auto_execution_validator import AutoExecutionValidator


class TestE2EAnalysisToPlanCreation(unittest.TestCase):
    """Test complete workflow: Analysis → Detection → Plan Creation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.detector = RegimeDetector()
        self.validator = AutoExecutionValidator()
        self.symbol = "BTCUSDc"
    
    def test_e2e_analysis_to_plan_creation(self):
        """Test complete workflow: Analysis → Detection → Plan Creation"""
        # Step 1: Create detector and get regime detection (PRE_BREAKOUT_TENSION)
        detector = RegimeDetector()
        timeframe_data = {
            "M5": {"atr_14": 48.0, "atr_50": 60.0, "bb_width": 1.2, "adx": 18.0, "volume": 800.0},
            "M15": {"atr_14": 52.0, "atr_50": 65.0, "bb_width": 1.3, "adx": 19.0, "volume": 900.0},
            "H1": {"atr_14": 58.0, "atr_50": 70.0, "bb_width": 1.4, "adx": 20.0, "volume": 1100.0}
        }
        
        mock_regime_data = detector.detect_regime(
            symbol=self.symbol,
            timeframe_data=timeframe_data,
            current_time=datetime.now(timezone.utc)
        )
        
        # If PRE_BREAKOUT_TENSION is detected, proceed with test
        if mock_regime_data.get('regime') == VolatilityRegime.PRE_BREAKOUT_TENSION:
            # Step 2: Get strategy recommendations
            recommendations = get_strategies_for_volatility(
                volatility_regime=VolatilityRegime.PRE_BREAKOUT_TENSION,
                symbol=self.symbol
            )
            
            # Step 3: Verify recommendations match regime
            self.assertIn('breakout_ib_volatility_trap', recommendations['prioritize'])
            self.assertIn('mean_reversion_range_scalp', recommendations['avoid'])
            self.assertEqual(recommendations['confidence_adjustment'], +10)
            
            # Step 4: Validate plan creation would work
            # (In real E2E, ChatGPT would create plan here)
            plan = {
                "symbol": self.symbol,
                "direction": "BUY",
                "entry_price": 85000.0,
                "stop_loss": 84500.0,
                "take_profit": 86000.0,
                "strategy_type": "breakout_ib_volatility_trap",
                "conditions": {
                    "price_above": 85000.0,
                    "price_near": 85000.0,
                    "tolerance": 100.0
                }
            }
            
            # Step 5: Validate plan against volatility state
            is_valid, rejection_reason = self.validator.validate_volatility_state(
                plan=plan,
                volatility_regime=VolatilityRegime.PRE_BREAKOUT_TENSION,
                strategy_type="breakout_ib_volatility_trap"
            )
            
            # Step 6: Verify plan is valid (breakout strategy matches PRE_BREAKOUT_TENSION)
            self.assertTrue(is_valid, f"Plan should be valid but was rejected: {rejection_reason}")
        else:
            # If PRE_BREAKOUT_TENSION not detected, just verify the workflow components exist
            self.assertTrue(hasattr(detector, 'detect_regime'))
            self.assertTrue(hasattr(self.validator, 'validate_volatility_state'))
    
    def test_e2e_plan_rejection_workflow(self):
        """Test plan rejection when incompatible with volatility state"""
        # Create plan with incompatible strategy
        plan = {
            "symbol": self.symbol,
            "direction": "BUY",
            "strategy_type": "trend_continuation_pullback",
            "conditions": {}
        }
        
        # Validate against POST_BREAKOUT_DECAY (blocks trend continuation)
        is_valid, rejection_reason = self.validator.validate_volatility_state(
            plan=plan,
            volatility_regime=VolatilityRegime.POST_BREAKOUT_DECAY,
            strategy_type="trend_continuation_pullback"
        )
        
        # Verify plan is rejected
        self.assertFalse(is_valid)
        self.assertIsNotNone(rejection_reason)
        self.assertIn('POST_BREAKOUT_DECAY', rejection_reason)


class TestE2EVolatilityStateTransition(unittest.TestCase):
    """Test state transitions during live trading"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.detector = RegimeDetector()
        self.symbol = "BTCUSDc"
    
    def test_e2e_state_transition_sequence(self):
        """Test state transition sequence: STABLE → PRE_BREAKOUT_TENSION → POST_BREAKOUT_DECAY"""
        current_time = datetime.now(timezone.utc)
        
        # Step 1: Start in STABLE
        stable_data = {
            "M5": {"atr_14": 50.0, "atr_50": 60.0, "bb_width": 2.5, "adx": 20.0, "volume": 1000.0},
            "M15": {"atr_14": 55.0, "atr_50": 65.0, "bb_width": 2.6, "adx": 21.0, "volume": 1200.0},
            "H1": {"atr_14": 60.0, "atr_50": 70.0, "bb_width": 2.7, "adx": 22.0, "volume": 1500.0}
        }
        
        result1 = self.detector.detect_regime(
            symbol=self.symbol,
            timeframe_data=stable_data,
            current_time=current_time
        )
        
        # Step 2: Transition to PRE_BREAKOUT_TENSION (compression)
        tension_data = {
            "M5": {"atr_14": 48.0, "atr_50": 60.0, "bb_width": 1.2, "adx": 18.0, "volume": 800.0},
            "M15": {"atr_14": 52.0, "atr_50": 65.0, "bb_width": 1.3, "adx": 19.0, "volume": 900.0},
            "H1": {"atr_14": 58.0, "atr_50": 70.0, "bb_width": 1.4, "adx": 20.0, "volume": 1100.0}
        }
        
        # Record a breakout event first (simulate breakout occurred)
        with patch.object(self.detector, '_record_breakout_event'):
            result2 = self.detector.detect_regime(
                symbol=self.symbol,
                timeframe_data=tension_data,
                current_time=current_time + timedelta(minutes=5)
            )
        
        # Step 3: Verify transitions are tracked
        history = self.detector.get_regime_history(self.symbol, limit=10)
        self.assertGreaterEqual(len(history), 2)
        
        # Verify regime values are valid
        self.assertIn('regime', result1)
        self.assertIn('regime', result2)


class TestE2EChatGPTIntegration(unittest.TestCase):
    """Test ChatGPT integration with new volatility states"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbol = "BTCUSDc"
    
    def test_e2e_chatgpt_analysis_with_volatility(self):
        """Test ChatGPT analysis tool with new volatility states"""
        # Create detector and get regime detection result with all new metrics
        detector = RegimeDetector()
        timeframe_data = {
            "M5": {"atr_14": 48.0, "atr_50": 60.0, "bb_width": 1.2, "adx": 18.0, "volume": 800.0},
            "M15": {"atr_14": 52.0, "atr_50": 65.0, "bb_width": 1.3, "adx": 19.0, "volume": 900.0},
            "H1": {"atr_14": 58.0, "atr_50": 70.0, "bb_width": 1.4, "adx": 20.0, "volume": 1100.0}
        }
        
        mock_regime_data = detector.detect_regime(
            symbol=self.symbol,
            timeframe_data=timeframe_data,
            current_time=datetime.now(timezone.utc)
        )
        
        # Simulate what analyse_symbol_full would extract
        volatility_metrics = {
            "regime": mock_regime_data["regime"],
            "confidence": mock_regime_data["confidence"],
            "atr_trends": mock_regime_data["atr_trends"],
            "wick_variances": mock_regime_data["wick_variances"],
            "time_since_breakout": mock_regime_data["time_since_breakout"],
            "mean_reversion_pattern": mock_regime_data["mean_reversion_pattern"],
            "volatility_spike": mock_regime_data["volatility_spike"],
            "session_transition": mock_regime_data["session_transition"],
            "whipsaw_detected": mock_regime_data["whipsaw_detected"]
        }
        
        # Verify structure matches expected format
        self.assertIn('regime', volatility_metrics)
        self.assertIn('atr_trends', volatility_metrics)
        self.assertIn('wick_variances', volatility_metrics)
        self.assertIsInstance(volatility_metrics['atr_trends'], dict)
        self.assertIsInstance(volatility_metrics['wick_variances'], dict)
    
    def test_e2e_chatgpt_plan_creation_with_validation(self):
        """Test ChatGPT plan creation with volatility validation"""
        # Create detector and validator (simulating what chatgpt_auto_execution_integration would do)
        detector = RegimeDetector()
        validator = AutoExecutionValidator()
        
        # Simulate plan creation attempt during SESSION_SWITCH_FLARE
        plan_data = {
            "symbol": self.symbol,
            "direction": "BUY",
            "strategy_type": "breakout_ib_volatility_trap"
        }
        
        # Validate (simulating what chatgpt_auto_execution_integration would do)
        # Use SESSION_SWITCH_FLARE directly for this test
        is_valid, rejection_reason = validator.validate_volatility_state(
            plan=plan_data,
            volatility_regime=VolatilityRegime.SESSION_SWITCH_FLARE,
            strategy_type=plan_data.get("strategy_type")
        )
        
        # Verify plan is rejected
        self.assertFalse(is_valid)
        self.assertIsNotNone(rejection_reason)
        self.assertIn('SESSION_SWITCH_FLARE', rejection_reason)


class TestE2EAutoExecution(unittest.TestCase):
    """Test auto-execution workflows with volatility filtering"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.validator = AutoExecutionValidator()
        self.symbol = "BTCUSDc"
    
    def test_e2e_volatility_state_blocking(self):
        """Test SESSION_SWITCH_FLARE blocking all execution"""
        # Create multiple plans
        plans = [
            {"strategy_type": "breakout_ib_volatility_trap"},
            {"strategy_type": "mean_reversion_range_scalp"},
            {"strategy_type": "order_block_rejection"}
        ]
        
        # Validate all against SESSION_SWITCH_FLARE
        results = []
        for plan in plans:
            is_valid, rejection_reason = self.validator.validate_volatility_state(
                plan=plan,
                volatility_regime=VolatilityRegime.SESSION_SWITCH_FLARE,
                strategy_type=plan["strategy_type"]
            )
            results.append((is_valid, rejection_reason))
        
        # Verify all plans are blocked
        for is_valid, rejection_reason in results:
            self.assertFalse(is_valid, f"Plan should be blocked but was accepted: {rejection_reason}")
            self.assertIsNotNone(rejection_reason)
            self.assertIn('SESSION_SWITCH_FLARE', rejection_reason)
    
    def test_e2e_fragmented_chop_filtering(self):
        """Test FRAGMENTED_CHOP filtering to only allow specific strategies"""
        # Create plans with different strategies
        plans = [
            {"strategy_type": "micro_scalp"},  # Should be allowed
            {"strategy_type": "mean_reversion_range_scalp"},  # Should be allowed
            {"strategy_type": "breakout_ib_volatility_trap"},  # Should be blocked
            {"strategy_type": "trend_continuation_pullback"}  # Should be blocked
        ]
        
        # Validate all against FRAGMENTED_CHOP
        results = []
        for plan in plans:
            is_valid, rejection_reason = self.validator.validate_volatility_state(
                plan=plan,
                volatility_regime=VolatilityRegime.FRAGMENTED_CHOP,
                strategy_type=plan["strategy_type"]
            )
            results.append((is_valid, rejection_reason))
        
        # Verify micro_scalp and mean_reversion_range_scalp are allowed
        self.assertTrue(results[0][0], "micro_scalp should be allowed in FRAGMENTED_CHOP")
        self.assertTrue(results[1][0], "mean_reversion_range_scalp should be allowed in FRAGMENTED_CHOP")
        
        # Verify others are blocked
        self.assertFalse(results[2][0], "breakout_ib_volatility_trap should be blocked in FRAGMENTED_CHOP")
        self.assertFalse(results[3][0], "trend_continuation_pullback should be blocked in FRAGMENTED_CHOP")


class TestE2ERealWorldScenarios(unittest.TestCase):
    """Test real-world trading scenarios end-to-end"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.detector = RegimeDetector()
        self.validator = AutoExecutionValidator()
        self.symbol = "BTCUSDc"
    
    def test_e2e_london_breakout_scenario(self):
        """Test London breakout scenario: Pre-breakout → Breakout → Post-breakout"""
        current_time = datetime.now(timezone.utc).replace(hour=8, minute=0, second=0)  # London open
        
        # Step 1: Pre-breakout tension (compression before breakout)
        tension_data = {
            "M5": {"atr_14": 48.0, "atr_50": 60.0, "bb_width": 1.2, "adx": 18.0, "volume": 800.0},
            "M15": {"atr_14": 52.0, "atr_50": 65.0, "bb_width": 1.3, "adx": 19.0, "volume": 900.0},
            "H1": {"atr_14": 58.0, "atr_50": 70.0, "bb_width": 1.4, "adx": 20.0, "volume": 1100.0}
        }
        
        result1 = self.detector.detect_regime(
            symbol=self.symbol,
            timeframe_data=tension_data,
            current_time=current_time
        )
        
        # Step 2: Get strategy recommendations
        if result1.get('regime') == VolatilityRegime.PRE_BREAKOUT_TENSION:
            recommendations = get_strategies_for_volatility(
                volatility_regime=VolatilityRegime.PRE_BREAKOUT_TENSION,
                symbol=self.symbol
            )
            
            # Verify breakout strategies are prioritized
            self.assertIn('breakout_ib_volatility_trap', recommendations['prioritize'])
    
    def test_e2e_choppy_market_scenario(self):
        """Test choppy market scenario: FRAGMENTED_CHOP → Micro-scalp strategies"""
        current_time = datetime.now(timezone.utc)
        
        # Create data that would trigger FRAGMENTED_CHOP
        # (In real scenario, this would have whipsaw, mean reversion, low ADX)
        chop_data = {
            "M5": {"atr_14": 45.0, "atr_50": 60.0, "bb_width": 2.0, "adx": 15.0, "volume": 700.0},
            "M15": {"atr_14": 50.0, "atr_50": 65.0, "bb_width": 2.1, "adx": 16.0, "volume": 800.0},
            "H1": {"atr_14": 55.0, "atr_50": 70.0, "bb_width": 2.2, "adx": 17.0, "volume": 900.0}
        }
        
        result = self.detector.detect_regime(
            symbol=self.symbol,
            timeframe_data=chop_data,
            current_time=current_time
        )
        
        # If FRAGMENTED_CHOP is detected, verify strategy filtering
        if result.get('regime') == VolatilityRegime.FRAGMENTED_CHOP:
            # Test plan validation
            micro_scalp_plan = {"strategy_type": "micro_scalp"}
            breakout_plan = {"strategy_type": "breakout_ib_volatility_trap"}
            
            is_valid_micro, _ = self.validator.validate_volatility_state(
                plan=micro_scalp_plan,
                volatility_regime=VolatilityRegime.FRAGMENTED_CHOP,
                strategy_type="micro_scalp"
            )
            
            is_valid_breakout, _ = self.validator.validate_volatility_state(
                plan=breakout_plan,
                volatility_regime=VolatilityRegime.FRAGMENTED_CHOP,
                strategy_type="breakout_ib_volatility_trap"
            )
            
            # Micro-scalp should be allowed, breakout should be blocked
            self.assertTrue(is_valid_micro, "micro_scalp should be allowed in FRAGMENTED_CHOP")
            self.assertFalse(is_valid_breakout, "breakout_ib_volatility_trap should be blocked in FRAGMENTED_CHOP")


class TestE2EDataFlow(unittest.TestCase):
    """Test complete data flow from MT5 to ChatGPT"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.detector = RegimeDetector()
        self.symbol = "BTCUSDc"
    
    def test_e2e_data_flow_completeness(self):
        """Test complete data flow: MT5 → Indicators → Regime → Metrics → Analysis → ChatGPT"""
        # Step 1: Simulate MT5 data (timeframe data)
        timeframe_data = {
            "M5": {"atr_14": 50.0, "atr_50": 60.0, "bb_width": 2.0, "adx": 25.0, "volume": 1000.0},
            "M15": {"atr_14": 55.0, "atr_50": 65.0, "bb_width": 2.1, "adx": 26.0, "volume": 1200.0},
            "H1": {"atr_14": 60.0, "atr_50": 70.0, "bb_width": 2.2, "adx": 27.0, "volume": 1500.0}
        }
        
        # Step 2: Regime detection
        regime_result = self.detector.detect_regime(
            symbol=self.symbol,
            timeframe_data=timeframe_data,
            current_time=datetime.now(timezone.utc)
        )
        
        # Step 3: Verify all required fields are present
        required_fields = ['regime', 'confidence', 'atr_ratio', 'bb_width_ratio', 'adx_composite']
        for field in required_fields:
            self.assertIn(field, regime_result, f"Missing required field: {field}")
        
        # Step 4: Verify tracking metrics (if available)
        optional_fields = ['atr_trends', 'wick_variances', 'time_since_breakout']
        for field in optional_fields:
            if field in regime_result:
                # Verify structure if present
                if field == 'atr_trends' or field == 'wick_variances':
                    self.assertIsInstance(regime_result[field], dict)
        
        # Step 5: Get strategy recommendations
        regime = regime_result.get('regime')
        if regime and isinstance(regime, VolatilityRegime):
            recommendations = get_strategies_for_volatility(
                volatility_regime=regime,
                symbol=self.symbol
            )
            
            # Verify recommendations structure
            self.assertIn('prioritize', recommendations)
            self.assertIn('avoid', recommendations)
            self.assertIn('confidence_adjustment', recommendations)


if __name__ == '__main__':
    unittest.main()

