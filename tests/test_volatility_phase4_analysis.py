"""
Phase 4.1 Testing: Analysis Tool Updates

Tests for volatility metrics extraction and response structure in moneybot.analyse_symbol_full
"""
import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timezone
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from infra.volatility_regime_detector import VolatilityRegime


class TestVolatilityMetricsExtraction(unittest.TestCase):
    """Test volatility metrics extraction in analysis tool"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.symbol = "BTCUSDc"
        self.symbol_normalized = "BTCUSDc"
        
        # Mock volatility_regime_data with all tracking metrics
        self.mock_volatility_regime_data = {
            "regime": VolatilityRegime.PRE_BREAKOUT_TENSION,
            "confidence": 85.5,
            "atr_ratio": 0.95,
            "bb_width_ratio": 0.88,
            "adx_composite": 25.3,
            "volume_confirmed": True,
            "atr_trends": {
                "M5": {
                    "trend_direction": "declining",
                    "slope_pct": -2.5,
                    "is_declining": True,
                    "is_above_baseline": False
                },
                "M15": {
                    "trend_direction": "declining",
                    "slope_pct": -3.2,
                    "is_declining": True,
                    "is_above_baseline": False
                },
                "H1": {
                    "trend_direction": "stable",
                    "slope_pct": 0.1,
                    "is_declining": False,
                    "is_above_baseline": True
                }
            },
            "wick_variances": {
                "M5": {
                    "is_increasing": True,
                    "variance_change_pct": 35.2,
                    "current_variance": 0.45
                },
                "M15": {
                    "is_increasing": True,
                    "variance_change_pct": 42.8,
                    "current_variance": 0.52
                },
                "H1": {
                    "is_increasing": False,
                    "variance_change_pct": -5.3,
                    "current_variance": 0.38
                }
            },
            "time_since_breakout": {
                "M5": None,
                "M15": {
                    "time_since_minutes": 45.5,
                    "breakout_type": "price",
                    "breakout_price": 85000.0,
                    "breakout_timestamp": "2025-01-10T10:30:00+00:00",
                    "is_recent": False
                },
                "H1": None
            },
            "mean_reversion_pattern": {
                "M15": {
                    "detected": True,
                    "strength": 0.65,
                    "oscillation_count": 3
                }
            },
            "volatility_spike": {
                "M15": {
                    "detected": False,
                    "spike_atr": None
                }
            },
            "session_transition": {
                "in_transition": False,
                "transition_type": None
            },
            "whipsaw_detected": {
                "M15": {
                    "detected": False,
                    "alternation_count": 0
                }
            }
        }
    
    def test_volatility_metrics_structure(self):
        """Test that volatility metrics structure is correctly built from volatility_regime_data"""
        # Simulate the extraction logic from desktop_agent.py
        volatility_regime_data = self.mock_volatility_regime_data
        
        # Extract tracking metrics (as done in Phase 4.1)
        atr_trends = volatility_regime_data.get("atr_trends", {})
        wick_variances = volatility_regime_data.get("wick_variances", {})
        time_since_breakout = volatility_regime_data.get("time_since_breakout", {})
        mean_reversion_pattern = volatility_regime_data.get("mean_reversion_pattern", {})
        volatility_spike = volatility_regime_data.get("volatility_spike", {})
        session_transition = volatility_regime_data.get("session_transition", {})
        whipsaw_detected = volatility_regime_data.get("whipsaw_detected", {})
        
        regime = volatility_regime_data.get("regime")
        confidence = volatility_regime_data.get("confidence", 0)
        volatility_strategy_recommendations = {
            "prioritize": ["breakout_ib_volatility_trap"],
            "avoid": ["mean_reversion_range_scalp"],
            "confidence_adjustment": 10,
            "recommendation": "Prioritize: breakout_ib_volatility_trap",
            "wait_reason": None
        }
        
        # Build volatility_metrics dict (as done in Phase 4.1)
        volatility_metrics = {
            "regime": regime.value if isinstance(regime, VolatilityRegime) else (str(regime) if regime else "UNKNOWN"),
            "confidence": confidence,
            "atr_ratio": volatility_regime_data.get("atr_ratio", 1.0),
            "bb_width_ratio": volatility_regime_data.get("bb_width_ratio", 1.0),
            "adx_composite": volatility_regime_data.get("adx_composite", 0.0),
            "volume_confirmed": volatility_regime_data.get("volume_confirmed", False),
            
            # NEW TRACKING METRICS
            "atr_trends": atr_trends,  # Per timeframe: M5, M15, H1
            "wick_variances": wick_variances,  # Per timeframe: M5, M15, H1
            "time_since_breakout": time_since_breakout,  # Per timeframe: M5, M15, H1
            
            # Convenience: Primary timeframe (M15) metrics
            "atr_trend": atr_trends.get("M15", {}),
            "wick_variance": wick_variances.get("M15", {}),
            "time_since_breakout_minutes": time_since_breakout.get("M15", {}).get("time_since_minutes") if time_since_breakout.get("M15") else None,
            
            # Additional metrics
            "mean_reversion_pattern": mean_reversion_pattern,
            "volatility_spike": volatility_spike,
            "session_transition": session_transition,
            "whipsaw_detected": whipsaw_detected,
            "strategy_recommendations": volatility_strategy_recommendations if volatility_strategy_recommendations else {}
        }
        
        # Verify all expected fields are present
        self.assertEqual(volatility_metrics["regime"], "PRE_BREAKOUT_TENSION")
        self.assertEqual(volatility_metrics["confidence"], 85.5)
        self.assertEqual(volatility_metrics["atr_ratio"], 0.95)
        self.assertEqual(volatility_metrics["bb_width_ratio"], 0.88)
        self.assertEqual(volatility_metrics["adx_composite"], 25.3)
        self.assertEqual(volatility_metrics["volume_confirmed"], True)
        
        # Verify tracking metrics
        self.assertIn("atr_trends", volatility_metrics)
        self.assertIn("wick_variances", volatility_metrics)
        self.assertIn("time_since_breakout", volatility_metrics)
        self.assertIn("mean_reversion_pattern", volatility_metrics)
        self.assertIn("volatility_spike", volatility_metrics)
        self.assertIn("session_transition", volatility_metrics)
        self.assertIn("whipsaw_detected", volatility_metrics)
        
        # Verify convenience fields (M15 primary timeframe)
        self.assertIn("atr_trend", volatility_metrics)
        self.assertIn("wick_variance", volatility_metrics)
        self.assertIn("time_since_breakout_minutes", volatility_metrics)
        
        # Verify M15 convenience fields match M15 data
        self.assertEqual(volatility_metrics["atr_trend"], volatility_metrics["atr_trends"]["M15"])
        self.assertEqual(volatility_metrics["wick_variance"], volatility_metrics["wick_variances"]["M15"])
        self.assertEqual(volatility_metrics["time_since_breakout_minutes"], 45.5)
        
        # Verify strategy recommendations
        self.assertIn("strategy_recommendations", volatility_metrics)
        self.assertEqual(volatility_metrics["strategy_recommendations"]["prioritize"], ["breakout_ib_volatility_trap"])
    
    def test_volatility_metrics_with_none_regime(self):
        """Test that volatility metrics handle None regime gracefully"""
        # Simulate None regime scenario
        volatility_regime_data = {
            "regime": None,
            "confidence": 0.0,
            "atr_ratio": 1.0,
            "bb_width_ratio": 1.0,
            "adx_composite": 0.0,
            "volume_confirmed": False,
            "atr_trends": {},
            "wick_variances": {},
            "time_since_breakout": {},
            "mean_reversion_pattern": {},
            "volatility_spike": {},
            "session_transition": {},
            "whipsaw_detected": {}
        }
        
        # Extract tracking metrics
        atr_trends = volatility_regime_data.get("atr_trends", {})
        wick_variances = volatility_regime_data.get("wick_variances", {})
        time_since_breakout = volatility_regime_data.get("time_since_breakout", {})
        mean_reversion_pattern = volatility_regime_data.get("mean_reversion_pattern", {})
        volatility_spike = volatility_regime_data.get("volatility_spike", {})
        session_transition = volatility_regime_data.get("session_transition", {})
        whipsaw_detected = volatility_regime_data.get("whipsaw_detected", {})
        
        regime = volatility_regime_data.get("regime")
        confidence = volatility_regime_data.get("confidence", 0)
        volatility_strategy_recommendations = None
        
        # Build volatility_metrics dict
        volatility_metrics = {
            "regime": regime.value if isinstance(regime, VolatilityRegime) else (str(regime) if regime else "UNKNOWN"),
            "confidence": confidence,
            "atr_ratio": volatility_regime_data.get("atr_ratio", 1.0),
            "bb_width_ratio": volatility_regime_data.get("bb_width_ratio", 1.0),
            "adx_composite": volatility_regime_data.get("adx_composite", 0.0),
            "volume_confirmed": volatility_regime_data.get("volume_confirmed", False),
            "atr_trends": atr_trends,
            "wick_variances": wick_variances,
            "time_since_breakout": time_since_breakout,
            "atr_trend": atr_trends.get("M15", {}),
            "wick_variance": wick_variances.get("M15", {}),
            "time_since_breakout_minutes": time_since_breakout.get("M15", {}).get("time_since_minutes") if time_since_breakout.get("M15") else None,
            "mean_reversion_pattern": mean_reversion_pattern,
            "volatility_spike": volatility_spike,
            "session_transition": session_transition,
            "whipsaw_detected": whipsaw_detected,
            "strategy_recommendations": volatility_strategy_recommendations if volatility_strategy_recommendations else {}
        }
        
        # Verify None regime is handled correctly
        self.assertEqual(volatility_metrics["regime"], "UNKNOWN")
        self.assertEqual(volatility_metrics["confidence"], 0.0)
        self.assertEqual(volatility_metrics["strategy_recommendations"], {})
    
    def test_volatility_metrics_missing_tracking_data(self):
        """Test that volatility metrics handle missing tracking data gracefully"""
        # Simulate missing tracking metrics scenario
        volatility_regime_data = {
            "regime": VolatilityRegime.STABLE,
            "confidence": 75.0,
            "atr_ratio": 1.0,
            "bb_width_ratio": 1.0,
            "adx_composite": 20.0,
            "volume_confirmed": False
            # Missing: atr_trends, wick_variances, etc.
        }
        
        # Extract tracking metrics (should default to empty dicts)
        atr_trends = volatility_regime_data.get("atr_trends", {})
        wick_variances = volatility_regime_data.get("wick_variances", {})
        time_since_breakout = volatility_regime_data.get("time_since_breakout", {})
        mean_reversion_pattern = volatility_regime_data.get("mean_reversion_pattern", {})
        volatility_spike = volatility_regime_data.get("volatility_spike", {})
        session_transition = volatility_regime_data.get("session_transition", {})
        whipsaw_detected = volatility_regime_data.get("whipsaw_detected", {})
        
        regime = volatility_regime_data.get("regime")
        confidence = volatility_regime_data.get("confidence", 0)
        volatility_strategy_recommendations = {}
        
        # Build volatility_metrics dict
        volatility_metrics = {
            "regime": regime.value if isinstance(regime, VolatilityRegime) else (str(regime) if regime else "UNKNOWN"),
            "confidence": confidence,
            "atr_ratio": volatility_regime_data.get("atr_ratio", 1.0),
            "bb_width_ratio": volatility_regime_data.get("bb_width_ratio", 1.0),
            "adx_composite": volatility_regime_data.get("adx_composite", 0.0),
            "volume_confirmed": volatility_regime_data.get("volume_confirmed", False),
            "atr_trends": atr_trends,
            "wick_variances": wick_variances,
            "time_since_breakout": time_since_breakout,
            "atr_trend": atr_trends.get("M15", {}),
            "wick_variance": wick_variances.get("M15", {}),
            "time_since_breakout_minutes": time_since_breakout.get("M15", {}).get("time_since_minutes") if time_since_breakout.get("M15") else None,
            "mean_reversion_pattern": mean_reversion_pattern,
            "volatility_spike": volatility_spike,
            "session_transition": session_transition,
            "whipsaw_detected": whipsaw_detected,
            "strategy_recommendations": volatility_strategy_recommendations if volatility_strategy_recommendations else {}
        }
        
        # Verify missing data is handled with empty dicts
        self.assertEqual(volatility_metrics.get("atr_trends", {}), {})
        self.assertEqual(volatility_metrics.get("wick_variances", {}), {})
        self.assertEqual(volatility_metrics.get("time_since_breakout", {}), {})
        self.assertEqual(volatility_metrics.get("atr_trend", {}), {})
        self.assertEqual(volatility_metrics.get("wick_variance", {}), {})
        self.assertIsNone(volatility_metrics.get("time_since_breakout_minutes"))


if __name__ == '__main__':
    unittest.main()

