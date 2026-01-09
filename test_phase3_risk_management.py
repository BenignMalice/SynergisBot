"""
Test Phase 3: Risk Management & Trade Execution

Tests:
1. Volatility-adjusted position sizing
2. Volatility-adjusted stop loss and take profit
3. Circuit breakers
4. Trade recommendations with Entry/SL/TP
5. Integration with strategy selector
"""

import sys
import logging
from datetime import datetime
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def test_volatility_risk_manager():
    """Test VolatilityRiskManager functionality"""
    logger.info("=" * 80)
    logger.info("TEST 1: Volatility Risk Manager")
    logger.info("=" * 80)
    
    try:
        from infra.volatility_risk_manager import VolatilityRiskManager
        from infra.volatility_regime_detector import VolatilityRegime
        
        risk_manager = VolatilityRiskManager()
        
        # Test 1.1: Volatility-adjusted risk percentage
        logger.info("\n[Test 1.1] Volatility-adjusted risk percentage")
        
        # STABLE regime
        stable_regime = {
            "regime": VolatilityRegime.STABLE,
            "confidence": 85.0
        }
        risk_stable = risk_manager.calculate_volatility_adjusted_risk_pct(
            volatility_regime=stable_regime,
            base_risk_pct=1.0
        )
        logger.info(f"  STABLE regime (confidence 85%): {risk_stable:.2f}% risk")
        assert risk_stable > 0.8, f"Expected > 0.8%, got {risk_stable:.2f}%"
        
        # TRANSITIONAL regime
        transitional_regime = {
            "regime": VolatilityRegime.TRANSITIONAL,
            "confidence": 75.0
        }
        risk_transitional = risk_manager.calculate_volatility_adjusted_risk_pct(
            volatility_regime=transitional_regime,
            base_risk_pct=1.0
        )
        logger.info(f"  TRANSITIONAL regime (confidence 75%): {risk_transitional:.2f}% risk")
        assert risk_transitional < risk_stable, "Transitional should be lower risk than stable"
        
        # VOLATILE regime
        volatile_regime = {
            "regime": VolatilityRegime.VOLATILE,
            "confidence": 90.0
        }
        risk_volatile = risk_manager.calculate_volatility_adjusted_risk_pct(
            volatility_regime=volatile_regime,
            base_risk_pct=1.0
        )
        logger.info(f"  VOLATILE regime (confidence 90%): {risk_volatile:.2f}% risk")
        assert risk_volatile < risk_transitional, "Volatile should be lowest risk"
        assert risk_volatile <= 0.5, f"Expected <= 0.5%, got {risk_volatile:.2f}%"
        
        # Test 1.2: Confidence scaling
        logger.info("\n[Test 1.2] Confidence-based risk scaling")
        low_confidence = {
            "regime": VolatilityRegime.STABLE,
            "confidence": 60.0  # Below threshold
        }
        risk_low_conf = risk_manager.calculate_volatility_adjusted_risk_pct(
            volatility_regime=low_confidence,
            base_risk_pct=1.0
        )
        logger.info(f"  Low confidence (60%): {risk_low_conf:.2f}% risk")
        assert risk_low_conf < risk_stable, "Low confidence should reduce risk"
        
        # Test 1.3: Volatility-adjusted stop loss
        logger.info("\n[Test 1.3] Volatility-adjusted stop loss")
        entry_price = 100.0
        atr = 2.0
        
        sl_stable = risk_manager.calculate_volatility_adjusted_stop_loss(
            entry_price=entry_price,
            direction="BUY",
            atr=atr,
            volatility_regime=stable_regime
        )
        logger.info(f"  STABLE regime SL: {sl_stable:.2f} (distance: {entry_price - sl_stable:.2f})")
        
        sl_volatile = risk_manager.calculate_volatility_adjusted_stop_loss(
            entry_price=entry_price,
            direction="BUY",
            atr=atr,
            volatility_regime=volatile_regime
        )
        logger.info(f"  VOLATILE regime SL: {sl_volatile:.2f} (distance: {entry_price - sl_volatile:.2f})")
        assert sl_volatile < sl_stable, "Volatile should have wider stops"
        
        # Test 1.4: Volatility-adjusted take profit
        logger.info("\n[Test 1.4] Volatility-adjusted take profit")
        stop_loss = sl_stable
        
        tp_stable = risk_manager.calculate_volatility_adjusted_take_profit(
            entry_price=entry_price,
            stop_loss=stop_loss,
            direction="BUY",
            atr=atr,
            volatility_regime=stable_regime
        )
        logger.info(f"  STABLE regime TP: {tp_stable:.2f}")
        
        tp_volatile = risk_manager.calculate_volatility_adjusted_take_profit(
            entry_price=entry_price,
            stop_loss=sl_volatile,
            direction="BUY",
            atr=atr,
            volatility_regime=volatile_regime
        )
        logger.info(f"  VOLATILE regime TP: {tp_volatile:.2f}")
        
        # Test 1.5: Circuit breakers
        logger.info("\n[Test 1.5] Circuit breakers")
        
        # Should allow trading initially
        can_trade, reason = risk_manager.check_circuit_breakers(
            symbol="BTCUSDc",
            equity=10000.0,
            current_time=datetime.now()
        )
        logger.info(f"  Initial check: Can trade = {can_trade}, Reason = {reason}")
        assert can_trade, "Should allow trading initially"
        
        # Record a loss
        risk_manager.record_trade("BTCUSDc", pnl=-300.0)  # 3% loss
        can_trade, reason = risk_manager.check_circuit_breakers(
            symbol="BTCUSDc",
            equity=10000.0,
            current_time=datetime.now()
        )
        logger.info(f"  After 3% loss: Can trade = {can_trade}, Reason = {reason}")
        assert not can_trade, "Should block trading after 3% loss"
        assert "Daily loss limit" in reason, f"Expected loss limit reason, got: {reason}"
        
        # Reset and test trade count
        risk_manager.reset_daily_counters("BTCUSDc")
        for i in range(3):
            risk_manager.record_trade("BTCUSDc", pnl=10.0)  # Small wins
        
        can_trade, reason = risk_manager.check_circuit_breakers(
            symbol="BTCUSDc",
            equity=10000.0,
            current_time=datetime.now()
        )
        logger.info(f"  After 3 trades: Can trade = {can_trade}, Reason = {reason}")
        assert not can_trade, "Should block trading after 3 trades"
        assert "Daily trade limit" in reason, f"Expected trade limit reason, got: {reason}"
        
        logger.info("\n[PASS] Test 1 PASSED: Volatility Risk Manager")
        return True
        
    except Exception as e:
        logger.error(f"\n[FAIL] Test 1 FAILED: {e}", exc_info=True)
        return False


def test_trade_level_calculations():
    """Test trade level calculations in strategy selector"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Trade Level Calculations")
    logger.info("=" * 80)
    
    try:
        from infra.volatility_strategy_selector import VolatilityStrategySelector, VolatilityStrategy
        from infra.volatility_regime_detector import VolatilityRegime
        
        selector = VolatilityStrategySelector()
        
        # Mock volatility regime
        volatile_regime = {
            "regime": VolatilityRegime.VOLATILE,
            "confidence": 85.0,
            "atr_ratio": 1.5
        }
        
        # Mock market data
        market_data = {
            "current_price": 65000.0
        }
        
        # Mock timeframe data
        timeframe_data = {
            "M5": {
                "atr14": 200.0,
                "rsi": 75.0,
                "bb_upper": 65500.0,
                "bb_lower": 64500.0,
                "bb_middle": 65000.0
            },
            "M15": {
                "atr14": 250.0,
                "rsi": 70.0
            },
            "H1": {
                "atr14": 300.0,
                "adx": 30.0
            }
        }
        
        # Test 2.1: Create a strategy score and calculate levels
        logger.info("\n[Test 2.1] Calculate trade levels for Breakout-Continuation strategy")
        
        from infra.volatility_strategy_selector import StrategyScore
        strategy_score = StrategyScore(
            strategy=VolatilityStrategy.BREAKOUT_CONTINUATION,
            score=80.0,
            reasoning="Test strategy",
            entry_conditions={},
            confidence=85.0
        )
        
        # Calculate trade levels
        strategy_with_levels = selector._calculate_trade_levels(
            strategy_score=strategy_score,
            symbol="BTCUSDc",
            volatility_regime=volatile_regime,
            market_data=market_data,
            timeframe_data=timeframe_data
        )
        
        logger.info(f"  Entry: {strategy_with_levels.entry:.2f}")
        logger.info(f"  Stop Loss: {strategy_with_levels.stop_loss:.2f}")
        logger.info(f"  Take Profit: {strategy_with_levels.take_profit:.2f}")
        logger.info(f"  Direction: {strategy_with_levels.direction}")
        logger.info(f"  Risk:Reward: {strategy_with_levels.risk_reward_ratio:.2f}")
        
        assert strategy_with_levels.entry > 0, "Entry should be calculated"
        assert strategy_with_levels.stop_loss > 0, "Stop loss should be calculated"
        assert strategy_with_levels.take_profit > 0, "Take profit should be calculated"
        assert strategy_with_levels.direction in ["BUY", "SELL"], "Direction should be BUY or SELL"
        assert strategy_with_levels.risk_reward_ratio > 0, "R:R should be positive"
        
        # Test 2.2: Verify stop loss is wider in volatile regime
        logger.info("\n[Test 2.2] Verify stop loss width by regime")
        
        stable_regime = {
            "regime": VolatilityRegime.STABLE,
            "confidence": 85.0,
            "atr_ratio": 1.0
        }
        
        strategy_stable = StrategyScore(
            strategy=VolatilityStrategy.BREAKOUT_CONTINUATION,
            score=80.0,
            reasoning="Test strategy",
            entry_conditions={},
            confidence=85.0
        )
        
        strategy_stable = selector._calculate_trade_levels(
            strategy_score=strategy_stable,
            symbol="BTCUSDc",
            volatility_regime=stable_regime,
            market_data=market_data,
            timeframe_data=timeframe_data
        )
        
        sl_distance_volatile = abs(strategy_with_levels.entry - strategy_with_levels.stop_loss)
        sl_distance_stable = abs(strategy_stable.entry - strategy_stable.stop_loss)
        
        logger.info(f"  Volatile SL distance: {sl_distance_volatile:.2f}")
        logger.info(f"  Stable SL distance: {sl_distance_stable:.2f}")
        assert sl_distance_volatile > sl_distance_stable, "Volatile should have wider stops"
        
        logger.info("\n[PASS] Test 2 PASSED: Trade Level Calculations")
        return True
        
    except Exception as e:
        logger.error(f"\n[FAIL] Test 2 FAILED: {e}", exc_info=True)
        return False


def test_volatility_adjusted_lot_sizing():
    """Test volatility-adjusted lot sizing integration"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Volatility-Adjusted Lot Sizing")
    logger.info("=" * 80)
    
    try:
        from infra.volatility_risk_manager import get_volatility_adjusted_lot_size
        from infra.volatility_regime_detector import VolatilityRegime
        
        # Test parameters
        symbol = "BTCUSDc"
        entry = 65000.0
        stop_loss = 64800.0  # 200 point stop
        equity = 10000.0
        base_risk_pct = 1.0
        
        # Test 3.1: STABLE regime (should use full base risk)
        logger.info("\n[Test 3.1] STABLE regime lot sizing")
        stable_regime = {
            "regime": VolatilityRegime.STABLE,
            "confidence": 90.0
        }
        
        lot_stable, metadata_stable = get_volatility_adjusted_lot_size(
            symbol=symbol,
            entry=entry,
            stop_loss=stop_loss,
            equity=equity,
            volatility_regime=stable_regime,
            base_risk_pct=base_risk_pct,
            tick_value=1.0,
            tick_size=0.01,
            contract_size=100000
        )
        
        logger.info(f"  Base risk: {metadata_stable['base_risk_pct']:.2f}%")
        logger.info(f"  Adjusted risk: {metadata_stable['adjusted_risk_pct']:.2f}%")
        logger.info(f"  Lot size: {lot_stable:.4f}")
        assert metadata_stable['adjusted_risk_pct'] >= 0.9, "Stable should use high risk"
        
        # Test 3.2: VOLATILE regime (should reduce risk)
        logger.info("\n[Test 3.2] VOLATILE regime lot sizing")
        volatile_regime = {
            "regime": VolatilityRegime.VOLATILE,
            "confidence": 90.0
        }
        
        lot_volatile, metadata_volatile = get_volatility_adjusted_lot_size(
            symbol=symbol,
            entry=entry,
            stop_loss=stop_loss,
            equity=equity,
            volatility_regime=volatile_regime,
            base_risk_pct=base_risk_pct,
            tick_value=1.0,
            tick_size=0.01,
            contract_size=100000
        )
        
        logger.info(f"  Base risk: {metadata_volatile['base_risk_pct']:.2f}%")
        logger.info(f"  Adjusted risk: {metadata_volatile['adjusted_risk_pct']:.2f}%")
        logger.info(f"  Lot size: {lot_volatile:.4f}")
        assert metadata_volatile['adjusted_risk_pct'] <= 0.5, "Volatile should use low risk"
        assert metadata_volatile['adjusted_risk_pct'] < metadata_stable['adjusted_risk_pct'], "Volatile should have lower adjusted risk than stable"
        
        # Test 3.3: No regime data (should use base risk)
        logger.info("\n[Test 3.3] No regime data (fallback)")
        lot_no_regime, metadata_no_regime = get_volatility_adjusted_lot_size(
            symbol=symbol,
            entry=entry,
            stop_loss=stop_loss,
            equity=equity,
            volatility_regime=None,
            base_risk_pct=base_risk_pct,
            tick_value=1.0,
            tick_size=0.01,
            contract_size=100000
        )
        
        logger.info(f"  Base risk: {metadata_no_regime['base_risk_pct']:.2f}%")
        logger.info(f"  Adjusted risk: {metadata_no_regime['adjusted_risk_pct']:.2f}%")
        logger.info(f"  Lot size: {lot_no_regime:.4f}")
        assert metadata_no_regime['adjusted_risk_pct'] == base_risk_pct, "Should use base risk when no regime"
        
        logger.info("\n[PASS] Test 3 PASSED: Volatility-Adjusted Lot Sizing")
        return True
        
    except Exception as e:
        logger.error(f"\n[FAIL] Test 3 FAILED: {e}", exc_info=True)
        return False


def test_strategy_selection_with_levels():
    """Test strategy selection with trade level calculations"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Strategy Selection with Trade Levels")
    logger.info("=" * 80)
    
    try:
        from infra.volatility_strategy_selector import VolatilityStrategySelector
        from infra.volatility_regime_detector import VolatilityRegime
        
        selector = VolatilityStrategySelector()
        
        # Mock volatile regime
        volatile_regime = {
            "regime": VolatilityRegime.VOLATILE,
            "confidence": 85.0,
            "atr_ratio": 1.6,
            "adx_composite": 32.0,
            "volume_confirmed": True
        }
        
        # Mock market data
        market_data = {
            "current_price": 65000.0
        }
        
        # Mock timeframe data
        timeframe_data = {
            "M5": {
                "atr14": 200.0,
                "atr_50": 130.0,
                "rsi": 75.0,
                "bb_upper": 65500.0,
                "bb_lower": 64500.0,
                "bb_middle": 65000.0,
                "adx": 30.0,
                "volumes": [1000, 1200, 1500, 1800, 2000]
            },
            "M15": {
                "atr14": 250.0,
                "atr_50": 160.0,
                "rsi": 70.0,
                "adx": 28.0
            },
            "H1": {
                "atr14": 300.0,
                "atr_50": 200.0,
                "adx": 32.0,
                "high": [65200.0],
                "low": [64800.0]
            }
        }
        
        # Test 4.1: Select strategy (should include trade levels)
        logger.info("\n[Test 4.1] Select strategy with trade levels")
        
        best_strategy, all_scores = selector.select_strategy(
            symbol="BTCUSDc",
            volatility_regime=volatile_regime,
            market_data=market_data,
            timeframe_data=timeframe_data
        )
        
        if best_strategy:
            logger.info(f"  Selected: {best_strategy.strategy.value}")
            logger.info(f"  Score: {best_strategy.score:.1f}")
            logger.info(f"  Confidence: {best_strategy.confidence:.1f}%")
            
            if best_strategy.entry:
                logger.info(f"  Entry: {best_strategy.entry:.2f}")
                logger.info(f"  Stop Loss: {best_strategy.stop_loss:.2f}")
                logger.info(f"  Take Profit: {best_strategy.take_profit:.2f}")
                logger.info(f"  Direction: {best_strategy.direction}")
                logger.info(f"  Risk:Reward: {best_strategy.risk_reward_ratio:.2f}")
                
                assert best_strategy.entry > 0, "Entry should be calculated"
                assert best_strategy.stop_loss > 0, "Stop loss should be calculated"
                assert best_strategy.take_profit > 0, "Take profit should be calculated"
                assert best_strategy.direction in ["BUY", "SELL"], "Direction should be set"
                assert best_strategy.risk_reward_ratio > 0, "R:R should be positive"
            else:
                logger.warning("  No trade levels calculated (may be expected if score < 75)")
        else:
            logger.info("  No strategy selected (score < 75 threshold)")
        
        logger.info("\n[PASS] Test 4 PASSED: Strategy Selection with Trade Levels")
        return True
        
    except Exception as e:
        logger.error(f"\n[FAIL] Test 4 FAILED: {e}", exc_info=True)
        return False


def main():
    """Run all Phase 3 tests"""
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 3: RISK MANAGEMENT & TRADE EXECUTION - TEST SUITE")
    logger.info("=" * 80 + "\n")
    
    results = []
    
    # Run tests
    results.append(("Volatility Risk Manager", test_volatility_risk_manager()))
    results.append(("Trade Level Calculations", test_trade_level_calculations()))
    results.append(("Volatility-Adjusted Lot Sizing", test_volatility_adjusted_lot_sizing()))
    results.append(("Strategy Selection with Levels", test_strategy_selection_with_levels()))
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        logger.info(f"  {test_name}: {status}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("\n[SUCCESS] ALL TESTS PASSED!")
        return 0
    else:
        logger.error(f"\n[WARNING] {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

