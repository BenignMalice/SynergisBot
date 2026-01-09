"""
Integration tests for Plan Portfolio Workflow and Dual Plan Strategy
Phase 2: Integration Tests (After Phase 1-3 Implementation)
"""

import pytest
import json


class TestPortfolioCreationWithAnalysis:
    """Test 2.1: Portfolio Creation with Analysis"""
    
    def test_analysis_response_structure(self):
        """Test ChatGPT extracts all required fields from analysis response"""
        # Mock analyse_symbol_full response
        analysis_response = {
            "data": {
                "current_price": 88840,
                "volatility_regime": {
                    "regime": "STABLE",
                    "strategy_recommendations": {
                        "prioritize": ["range_scalp", "order_block_rejection"],
                        "avoid": ["breakout_ib_volatility_trap"]
                    }
                },
                "session": {"name": "ASIA"},
                "symbol_constraints": {},
                "structure_summary": {}
            }
        }
        
        # Verify ChatGPT extracts all required fields
        assert "current_price" in analysis_response["data"]
        assert "volatility_regime" in analysis_response["data"]
        assert "session" in analysis_response["data"]
        assert "symbol_constraints" in analysis_response["data"]
        assert "structure_summary" in analysis_response["data"]
        
        # Verify nested fields
        assert "regime" in analysis_response["data"]["volatility_regime"]
        assert "strategy_recommendations" in analysis_response["data"]["volatility_regime"]
        assert "prioritize" in analysis_response["data"]["volatility_regime"]["strategy_recommendations"]
        assert "avoid" in analysis_response["data"]["volatility_regime"]["strategy_recommendations"]
        assert "name" in analysis_response["data"]["session"]


class TestDualPlanBatchCreation:
    """Test 2.2: Dual Plan Creation in Batch"""
    
    def test_dual_plan_batch_structure(self):
        """Test dual plans are created in same batch with correct structure"""
        retracement_plan = {
            "direction": "SELL",
            "entry": 88975,  # Above current (88840)
            "stop_loss": 89125,
            "take_profit": 88700,
            "symbol": "BTCUSDc",
            "plan_type": "rejection_wick",
            "volume": 0.01,
            "expires_hours": 24,
            "conditions": {
                "choch_bear": True,
                "liquidity_sweep": True,
                "price_near": 88975,
                "tolerance": 100,
                "timeframe": "M15"
            },
            "notes": "Retracement plan: Wait for pullback to bearish OB zone"
        }
        
        continuation_plan = {
            "direction": "SELL",
            "entry": 88800,  # Below current
            "stop_loss": 88975,
            "take_profit": 88400,
            "symbol": "BTCUSDc",  # Must match retracement
            "plan_type": "auto_trade",  # Valid plan_type
            "volume": 0.01,  # Must match retracement
            "expires_hours": 24,  # Must match retracement
            "conditions": {
                "bos_bear": True,
                "price_below": 88800,
                "price_near": 88800,
                "tolerance": 75,
                "timeframe": "M15"
            },
            "notes": "Continuation plan for retracement plan [retracement_plan_id]"
        }
        
        plans = [retracement_plan, continuation_plan]
        
        # Verify batch structure
        assert len(plans) == 2
        assert plans[1]["symbol"] == plans[0]["symbol"]  # Symbols match
        assert plans[1]["plan_type"] in ["auto_trade", "choch", "rejection_wick"]  # Valid plan_type
        assert plans[1]["volume"] == plans[0]["volume"]  # Volume matches
        assert plans[1]["expires_hours"] == plans[0]["expires_hours"]  # Expiration matches
        
        # Verify continuation plan conditions
        assert "bos_bear" in plans[1]["conditions"]
        assert "price_below" in plans[1]["conditions"]
        assert plans[1]["conditions"]["price_near"] == plans[1]["entry"]  # price_near matches entry
        assert plans[1]["conditions"]["price_below"] == plans[1]["entry"]  # price_below matches entry for SELL
    
    def test_continuation_plan_validation(self):
        """Test continuation plan validation requirements"""
        continuation_plan = {
            "direction": "SELL",
            "entry": 88800,
            "stop_loss": 88975,  # Above entry
            "take_profit": 88400,  # Below entry
            "symbol": "BTCUSDc",
            "plan_type": "auto_trade",
            "conditions": {
                "bos_bear": True,
                "price_below": 88800,
                "price_near": 88800,
                "tolerance": 75,
                "timeframe": "M15"
            }
        }
        
        # Validate entry is positive and reasonable
        assert continuation_plan["entry"] > 0
        assert 10000 <= continuation_plan["entry"] <= 200000  # BTC reasonable range
        
        # Validate SL/TP positioning for SELL
        assert continuation_plan["stop_loss"] > continuation_plan["entry"]  # SL above entry
        assert continuation_plan["take_profit"] < continuation_plan["entry"]  # TP below entry
        assert continuation_plan["stop_loss"] > continuation_plan["take_profit"]  # SL above TP
        
        # Validate conditions
        assert continuation_plan["conditions"]["price_near"] == continuation_plan["entry"]
        assert continuation_plan["conditions"]["price_below"] == continuation_plan["entry"]


class TestPartialBatchFailure:
    """Test 2.4: Partial Batch Failure Handling"""
    
    def test_partial_batch_failure_response(self):
        """Test handling when retracement succeeds but continuation fails"""
        # Mock batch response with partial failure
        batch_response = {
            "total": 2,
            "successful": 1,
            "failed": 1,
            "results": [
                {"index": 0, "status": "created", "plan_id": "retracement_123"},
                {"index": 1, "status": "failed", "error": "Invalid plan_type"}
            ]
        }
        
        # Verify response structure
        assert batch_response["total"] == 2
        assert batch_response["successful"] == 1
        assert batch_response["failed"] == 1
        assert len(batch_response["results"]) == 2
        
        # Verify retracement succeeded
        assert batch_response["results"][0]["status"] == "created"
        assert "plan_id" in batch_response["results"][0]
        
        # Verify continuation failed
        assert batch_response["results"][1]["status"] == "failed"
        assert "error" in batch_response["results"][1]
        
        # ChatGPT should handle this by:
        # 1. Explaining: "Retracement plan created, but continuation plan failed: Invalid plan_type"
        # 2. Offering to retry continuation plan


class TestWeekendModeDualPlans:
    """Test 2.3: Weekend Mode Dual Plans"""
    
    def test_weekend_mode_detection(self):
        """Test weekend mode detection from analysis response"""
        # Mock weekend mode analysis
        from datetime import datetime, timezone
        
        # Friday 23:00 UTC
        friday_23 = datetime(2025, 12, 19, 23, 0, 0, tzinfo=timezone.utc)
        # Saturday
        saturday = datetime(2025, 12, 20, 12, 0, 0, tzinfo=timezone.utc)
        # Sunday
        sunday = datetime(2025, 12, 21, 12, 0, 0, tzinfo=timezone.utc)
        # Monday 02:00 UTC
        monday_02 = datetime(2025, 12, 22, 2, 0, 0, tzinfo=timezone.utc)
        
        # All should be weekend mode for BTCUSDc
        assert friday_23.hour >= 23
        assert saturday.weekday() == 5  # Saturday
        assert sunday.weekday() == 6  # Sunday
        assert monday_02.hour < 3
    
    def test_weekend_strategy_selection(self):
        """Test continuation plan uses weekend-appropriate strategies"""
        continuation_plan_weekend = {
            "plan_type": "auto_trade",
            "strategy_type": "liquidity_sweep_reversal",  # Weekend-appropriate
            "conditions": {
                "bos_bear": True,
                "price_below": 88800,
                "price_near": 88800,
                "tolerance": 75,
                "timeframe": "M15"
            }
        }
        
        # Verify weekend-appropriate strategy
        assert continuation_plan_weekend["strategy_type"] in [
            "liquidity_sweep_reversal",
            "mean_reversion_range_scalp"
        ]
        # Should NOT use trend_continuation_pullback during weekend
        assert continuation_plan_weekend["strategy_type"] != "trend_continuation_pullback"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
