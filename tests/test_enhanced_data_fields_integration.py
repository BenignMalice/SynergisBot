"""
Integration tests for Enhanced Data Fields in analyse_symbol_full.

This test suite validates that all enhanced data fields are properly integrated
into the analyse_symbol_full response structure.
"""

import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
from typing import Dict, Any, Optional


class TestEnhancedDataFieldsIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for enhanced data fields in analyse_symbol_full."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.symbol = "XAUUSD"
        self.symbol_normalized = "XAUUSDc"
        
    async def test_analyse_symbol_full_includes_all_enhanced_fields(self):
        """Test that analyse_symbol_full includes all 7 enhanced data fields."""
        # Mock the tool function
        with patch('desktop_agent.registry') as mock_registry:
            # Setup mock services
            mock_registry.mt5_service = Mock()
            mock_registry.market_indices_service = Mock()
            mock_registry.spread_tracker = Mock()
            mock_registry.strategy_performance_tracker = Mock()
            mock_registry.symbol_constraints_manager = Mock()
            
            # Import the tool function
            from desktop_agent import tool_analyse_symbol_full
            
            # Mock all the calculation services
            with patch('desktop_agent.CorrelationContextCalculator') as mock_corr, \
                 patch('desktop_agent.GeneralOrderFlowMetrics') as mock_order_flow, \
                 patch('desktop_agent.HTFLevelsCalculator') as mock_htf, \
                 patch('desktop_agent.SessionRiskCalculator') as mock_session, \
                 patch('desktop_agent.ExecutionQualityMonitor') as mock_exec, \
                 patch('desktop_agent.StrategyPerformanceTracker') as mock_strat, \
                 patch('desktop_agent.SymbolConstraintsManager') as mock_constraints, \
                 patch('desktop_agent.calculate_structure_summary') as mock_structure:
                
                # Setup mock return values
                mock_corr_instance = Mock()
                mock_corr_instance.calculate_correlation_context = AsyncMock(return_value={
                    "dxy_correlation": -0.75,
                    "sp500_correlation": 0.15,
                    "us10y_correlation": -0.60,
                    "btc_correlation": 0.25,
                    "conflict_detected": False,
                    "dominant_driver": "DXY",
                    "data_quality": "good"
                })
                mock_corr.return_value = mock_corr_instance
                
                mock_order_flow_instance = Mock()
                mock_order_flow_instance.calculate_general_order_flow = AsyncMock(return_value={
                    "cvd": 1250.5,
                    "cvd_slope": 0.15,
                    "aggressor_ratio": 0.65,
                    "imbalance_score": 0.45,
                    "large_trade_count": 12,
                    "data_quality": "proxy"
                })
                mock_order_flow.return_value = mock_order_flow_instance
                
                mock_htf_instance = Mock()
                mock_htf_instance.calculate_htf_levels = AsyncMock(return_value={
                    "weekly_open": 2600.0,
                    "monthly_open": 2580.0,
                    "previous_week_high": 2620.0,
                    "previous_week_low": 2580.0,
                    "previous_day_high": 2610.0,
                    "previous_day_low": 2590.0,
                    "premium_zone": 2615.0,
                    "discount_zone": 2585.0,
                    "price_position": "premium",
                    "range_reference": "weekly_range",
                    "data_quality": "good"
                })
                mock_htf.return_value = mock_htf_instance
                
                mock_session_instance = Mock()
                mock_session_instance.calculate_session_risk = AsyncMock(return_value={
                    "in_rollover_window": False,
                    "next_rollover_utc": "2025-12-12T00:00:00Z",
                    "in_news_lock": False,
                    "next_high_impact_event": None,
                    "event_proximity_hours": None,
                    "session_volatility_profile": "normal",
                    "risk_level": "low",
                    "data_quality": "good"
                })
                mock_session.return_value = mock_session_instance
                
                mock_exec_instance = Mock()
                mock_exec_instance.get_execution_context = AsyncMock(return_value={
                    "current_spread_pips": 1.2,
                    "median_spread_pips": 1.5,
                    "spread_quality": "excellent",
                    "spread_vs_median_pct": -20.0,
                    "slippage_estimate_pips": 0.3,
                    "median_slippage_pips": 0.4,
                    "slippage_quality": "good",
                    "execution_quality_score": 85,
                    "data_quality": "good"
                })
                mock_exec.return_value = mock_exec_instance
                
                mock_strat_instance = Mock()
                mock_strat_instance.get_strategy_stats_by_regime = AsyncMock(return_value={
                    "strategy_name": "LIQUIDITY_SWEEP_REVERSAL",
                    "regime_filter": "HIGH_VOLATILITY",
                    "win_rate_pct": 68.0,
                    "avg_rr_ratio": 2.1,
                    "max_drawdown_pct": 8.0,
                    "sample_size": 45,
                    "confidence_level": "high"
                })
                mock_strat.return_value = mock_strat_instance
                
                mock_constraints_instance = Mock()
                mock_constraints_instance.get_symbol_constraints = Mock(return_value={
                    "max_concurrent_trades_for_symbol": 1,
                    "max_total_risk_on_symbol_pct": 2.0,
                    "allowed_strategies": ["LIQUIDITY_SWEEP_REVERSAL"],
                    "banned_strategies": ["SWING_TREND_FOLLOWING"],
                    "risk_profile": "conservative",
                    "max_position_size_pct": 3.0
                })
                mock_constraints.return_value = mock_constraints_instance
                
                mock_structure.return_value = {
                    "current_range_type": "balanced_range",
                    "range_state": "mid_range",
                    "has_liquidity_sweep": False,
                    "sweep_type": "none",
                    "sweep_level": None,
                    "discount_premium_state": "balanced",
                    "range_high": 2620.0,
                    "range_low": 2580.0,
                    "range_mid": 2600.0
                }
                
                # Mock other required dependencies
                with patch('desktop_agent.getMultiTimeframeAnalysis') as mock_mtf, \
                     patch('desktop_agent.get_advanced_features') as mock_adv, \
                     patch('desktop_agent.get_m1_microstructure') as mock_m1, \
                     patch('desktop_agent.get_macro_context') as mock_macro, \
                     patch('desktop_agent.get_session_analysis') as mock_sess, \
                     patch('desktop_agent.get_news_context') as mock_news:
                    
                    # Setup mock return values for dependencies
                    mock_mtf.return_value = {
                        "timeframes": {},
                        "alignment_score": 50,
                        "recommendation": {"action": "WAIT", "confidence": 50},
                        "market_bias": {"trend": "NEUTRAL", "strength": "WEAK"}
                    }
                    mock_adv.return_value = {"features": {}}
                    mock_m1.return_value = {"available": True, "structure": {}}
                    mock_macro.return_value = {"bias": "NEUTRAL", "summary": "Test"}
                    mock_sess.return_value = {"name": "London", "is_overlap": False}
                    mock_news.return_value = {"upcoming_events": []}
                    
                    # Call the tool function
                    args = {"symbol": self.symbol}
                    result = await tool_analyse_symbol_full(args)
                    
                    # Validate response structure
                    self.assertIn("data", result)
                    data = result["data"]
                    
                    # Validate all 7 enhanced data fields are present
                    self.assertIn("correlation_context", data, "correlation_context missing")
                    self.assertIn("htf_levels", data, "htf_levels missing")
                    self.assertIn("session_risk", data, "session_risk missing")
                    self.assertIn("execution_context", data, "execution_context missing")
                    self.assertIn("strategy_stats", data, "strategy_stats missing")
                    self.assertIn("structure_summary", data, "structure_summary missing")
                    self.assertIn("symbol_constraints", data, "symbol_constraints missing")
                    
                    # Validate correlation_context structure
                    corr_ctx = data["correlation_context"]
                    self.assertIn("dxy_correlation", corr_ctx)
                    self.assertIn("data_quality", corr_ctx)
                    
                    # Validate htf_levels structure
                    htf = data["htf_levels"]
                    self.assertIn("weekly_open", htf)
                    self.assertIn("price_position", htf)
                    self.assertIn("data_quality", htf)
                    
                    # Validate session_risk structure
                    session = data["session_risk"]
                    self.assertIn("in_rollover_window", session)
                    self.assertIn("risk_level", session)
                    self.assertIn("data_quality", session)
                    
                    # Validate execution_context structure
                    exec_ctx = data["execution_context"]
                    self.assertIn("current_spread_pips", exec_ctx)
                    self.assertIn("execution_quality_score", exec_ctx)
                    self.assertIn("data_quality", exec_ctx)
                    
                    # Validate strategy_stats (can be None)
                    strat_stats = data["strategy_stats"]
                    if strat_stats is not None:
                        self.assertIn("strategy_name", strat_stats)
                        self.assertIn("win_rate_pct", strat_stats)
                    
                    # Validate structure_summary structure
                    structure = data["structure_summary"]
                    self.assertIn("current_range_type", structure)
                    self.assertIn("range_state", structure)
                    
                    # Validate symbol_constraints structure
                    constraints = data["symbol_constraints"]
                    self.assertIn("max_concurrent_trades_for_symbol", constraints)
                    self.assertIn("risk_profile", constraints)
                    
                    # Validate summary includes enhanced data fields section
                    self.assertIn("summary", result)
                    summary = result["summary"]
                    self.assertIn("ENHANCED DATA FIELDS", summary.upper())
    
    async def test_enhanced_fields_handle_unavailable_data(self):
        """Test that enhanced fields handle unavailable data gracefully."""
        with patch('desktop_agent.registry') as mock_registry:
            mock_registry.mt5_service = Mock()
            mock_registry.market_indices_service = Mock()
            
            from desktop_agent import tool_analyse_symbol_full
            
            with patch('desktop_agent.CorrelationContextCalculator') as mock_corr, \
                 patch('desktop_agent.GeneralOrderFlowMetrics') as mock_order_flow, \
                 patch('desktop_agent.HTFLevelsCalculator') as mock_htf, \
                 patch('desktop_agent.SessionRiskCalculator') as mock_session, \
                 patch('desktop_agent.ExecutionQualityMonitor') as mock_exec, \
                 patch('desktop_agent.StrategyPerformanceTracker') as mock_strat, \
                 patch('desktop_agent.SymbolConstraintsManager') as mock_constraints, \
                 patch('desktop_agent.calculate_structure_summary') as mock_structure:
                
                # Setup mocks to return unavailable data
                mock_corr_instance = Mock()
                mock_corr_instance.calculate_correlation_context = AsyncMock(return_value=None)
                mock_corr.return_value = mock_corr_instance
                
                mock_order_flow_instance = Mock()
                mock_order_flow_instance.calculate_general_order_flow = AsyncMock(return_value={
                    "data_quality": "unavailable"
                })
                mock_order_flow.return_value = mock_order_flow_instance
                
                mock_htf_instance = Mock()
                mock_htf_instance.calculate_htf_levels = AsyncMock(return_value=None)
                mock_htf.return_value = mock_htf_instance
                
                mock_session_instance = Mock()
                mock_session_instance.calculate_session_risk = AsyncMock(return_value={
                    "data_quality": "unavailable"
                })
                mock_session.return_value = mock_session_instance
                
                mock_exec_instance = Mock()
                mock_exec_instance.get_execution_context = AsyncMock(return_value=None)
                mock_exec.return_value = mock_exec_instance
                
                mock_strat_instance = Mock()
                mock_strat_instance.get_strategy_stats_by_regime = AsyncMock(return_value=None)
                mock_strat.return_value = mock_strat_instance
                
                mock_constraints_instance = Mock()
                mock_constraints_instance.get_symbol_constraints = Mock(return_value={})
                mock_constraints.return_value = mock_constraints_instance
                
                mock_structure.return_value = {}
                
                # Mock other dependencies
                with patch('desktop_agent.getMultiTimeframeAnalysis') as mock_mtf, \
                     patch('desktop_agent.get_advanced_features') as mock_adv, \
                     patch('desktop_agent.get_m1_microstructure') as mock_m1, \
                     patch('desktop_agent.get_macro_context') as mock_macro, \
                     patch('desktop_agent.get_session_analysis') as mock_sess, \
                     patch('desktop_agent.get_news_context') as mock_news:
                    
                    mock_mtf.return_value = {
                        "timeframes": {},
                        "alignment_score": 50,
                        "recommendation": {"action": "WAIT", "confidence": 50},
                        "market_bias": {"trend": "NEUTRAL", "strength": "WEAK"}
                    }
                    mock_adv.return_value = {"features": {}}
                    mock_m1.return_value = {"available": False}
                    mock_macro.return_value = {"bias": "NEUTRAL", "summary": "Test"}
                    mock_sess.return_value = {"name": "London", "is_overlap": False}
                    mock_news.return_value = {"upcoming_events": []}
                    
                    args = {"symbol": self.symbol}
                    result = await tool_analyse_symbol_full(args)
                    
                    # Validate that fields are still present but empty/None
                    data = result["data"]
                    self.assertIn("correlation_context", data)
                    self.assertIn("htf_levels", data)
                    self.assertIn("session_risk", data)
                    self.assertIn("execution_context", data)
                    self.assertIn("strategy_stats", data)  # Can be None
                    self.assertIn("structure_summary", data)
                    self.assertIn("symbol_constraints", data)
                    
                    # Validate empty dicts or None are returned
                    self.assertEqual(data["correlation_context"], {})
                    self.assertEqual(data["htf_levels"], {})
                    self.assertEqual(data["execution_context"], {})
                    self.assertIsNone(data["strategy_stats"])  # Can be None
    
    async def test_enhanced_fields_in_summary_text(self):
        """Test that enhanced data fields are included in summary text."""
        with patch('desktop_agent.registry') as mock_registry:
            mock_registry.mt5_service = Mock()
            mock_registry.market_indices_service = Mock()
            
            from desktop_agent import tool_analyse_symbol_full
            
            with patch('desktop_agent.CorrelationContextCalculator') as mock_corr, \
                 patch('desktop_agent.GeneralOrderFlowMetrics') as mock_order_flow, \
                 patch('desktop_agent.HTFLevelsCalculator') as mock_htf, \
                 patch('desktop_agent.SessionRiskCalculator') as mock_session, \
                 patch('desktop_agent.ExecutionQualityMonitor') as mock_exec, \
                 patch('desktop_agent.StrategyPerformanceTracker') as mock_strat, \
                 patch('desktop_agent.SymbolConstraintsManager') as mock_constraints, \
                 patch('desktop_agent.calculate_structure_summary') as mock_structure:
                
                # Setup mocks with valid data
                mock_corr_instance = Mock()
                mock_corr_instance.calculate_correlation_context = AsyncMock(return_value={
                    "dxy_correlation": -0.75,
                    "data_quality": "good"
                })
                mock_corr.return_value = mock_corr_instance
                
                mock_order_flow_instance = Mock()
                mock_order_flow_instance.calculate_general_order_flow = AsyncMock(return_value={
                    "cvd": 1250.5,
                    "data_quality": "proxy"
                })
                mock_order_flow.return_value = mock_order_flow_instance
                
                mock_htf_instance = Mock()
                mock_htf_instance.calculate_htf_levels = AsyncMock(return_value={
                    "weekly_open": 2600.0,
                    "price_position": "premium",
                    "data_quality": "good"
                })
                mock_htf.return_value = mock_htf_instance
                
                mock_session_instance = Mock()
                mock_session_instance.calculate_session_risk = AsyncMock(return_value={
                    "risk_level": "low",
                    "data_quality": "good"
                })
                mock_session.return_value = mock_session_instance
                
                mock_exec_instance = Mock()
                mock_exec_instance.get_execution_context = AsyncMock(return_value={
                    "execution_quality_score": 85,
                    "data_quality": "good"
                })
                mock_exec.return_value = mock_exec_instance
                
                mock_strat_instance = Mock()
                mock_strat_instance.get_strategy_stats_by_regime = AsyncMock(return_value=None)
                mock_strat.return_value = mock_strat_instance
                
                mock_constraints_instance = Mock()
                mock_constraints_instance.get_symbol_constraints = Mock(return_value={
                    "max_concurrent_trades_for_symbol": 1
                })
                mock_constraints.return_value = mock_constraints_instance
                
                mock_structure.return_value = {
                    "current_range_type": "balanced_range"
                }
                
                # Mock other dependencies
                with patch('desktop_agent.getMultiTimeframeAnalysis') as mock_mtf, \
                     patch('desktop_agent.get_advanced_features') as mock_adv, \
                     patch('desktop_agent.get_m1_microstructure') as mock_m1, \
                     patch('desktop_agent.get_macro_context') as mock_macro, \
                     patch('desktop_agent.get_session_analysis') as mock_sess, \
                     patch('desktop_agent.get_news_context') as mock_news:
                    
                    mock_mtf.return_value = {
                        "timeframes": {},
                        "alignment_score": 50,
                        "recommendation": {"action": "WAIT", "confidence": 50},
                        "market_bias": {"trend": "NEUTRAL", "strength": "WEAK"}
                    }
                    mock_adv.return_value = {"features": {}}
                    mock_m1.return_value = {"available": True, "structure": {}}
                    mock_macro.return_value = {"bias": "NEUTRAL", "summary": "Test"}
                    mock_sess.return_value = {"name": "London", "is_overlap": False}
                    mock_news.return_value = {"upcoming_events": []}
                    
                    args = {"symbol": self.symbol}
                    result = await tool_analyse_symbol_full(args)
                    
                    # Validate summary includes enhanced data fields section
                    self.assertIn("summary", result)
                    summary = result["summary"].upper()
                    
                    # Check for enhanced data fields section
                    self.assertIn("ENHANCED DATA FIELDS", summary)
                    # Check for key field mentions
                    self.assertTrue(
                        "CORRELATION" in summary or 
                        "HTF" in summary or 
                        "SESSION RISK" in summary or
                        "EXECUTION" in summary or
                        "STRUCTURE" in summary or
                        "CONSTRAINTS" in summary,
                        "Summary should mention at least one enhanced field"
                    )


if __name__ == "__main__":
    unittest.main()

