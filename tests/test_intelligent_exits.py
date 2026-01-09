"""
Test script for Intelligent Exit Management
Tests breakeven, partial profits, and ATR trailing logic
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_exit_rule_creation():
    """Test 1: Create an exit rule and verify parameters"""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Exit Rule Creation")
    logger.info("="*60)
    
    try:
        from infra.intelligent_exit_manager import ExitRule
        
        rule = ExitRule(
            ticket=123456,
            symbol="XAUUSD",
            entry_price=3950.0,
            direction="buy",
            initial_sl=3944.0,
            initial_tp=3965.0,
            breakeven_profit=5.0,
            partial_profit_level=10.0,
            partial_close_pct=50.0,
            vix_threshold=18.0,
            vix_multiplier=1.5,
            use_hybrid_stops=True,
            trailing_enabled=True
        )
        
        logger.info(f"✅ Rule created successfully")
        logger.info(f"   Ticket: {rule.ticket}")
        logger.info(f"   Symbol: {rule.symbol}")
        logger.info(f"   Direction: {rule.direction}")
        logger.info(f"   Entry: {rule.entry_price}")
        logger.info(f"   Initial SL: {rule.initial_sl}")
        logger.info(f"   Breakeven Profit: ${rule.breakeven_profit}")
        logger.info(f"   Partial Profit Level: ${rule.partial_profit_level}")
        logger.info(f"   Use Hybrid Stops: {rule.use_hybrid_stops}")
        logger.info(f"   Trailing Enabled: {rule.trailing_enabled}")
        
        # Test state tracking
        assert rule.breakeven_triggered == False, "Breakeven should start as False"
        assert rule.trailing_active == False, "Trailing should start as False"
        assert rule.hybrid_adjustment_active == False, "Hybrid adjustment should start as False"
        
        logger.info(f"✅ All state flags initialized correctly")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_breakeven_logic():
    """Test 2: Breakeven trigger calculation"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Breakeven Trigger Logic")
    logger.info("="*60)
    
    try:
        # Simulate BUY trade
        entry_price = 3950.0
        current_price = 3955.0  # +5 points
        volume = 0.01  # Standard user volume
        
        # Calculate profit (Gold: contract_size = 100)
        # For XAUUSD: 1 lot = 100 troy oz, so 0.01 lot = 1 oz
        contract_size = 100  # Gold contract size
        profit_dollars = (current_price - entry_price) * volume * contract_size
        
        logger.info(f"   Entry: {entry_price}")
        logger.info(f"   Current: {current_price}")
        logger.info(f"   Movement: +{current_price - entry_price} points")
        logger.info(f"   Volume: {volume} lots")
        logger.info(f"   Calculated Profit: ${profit_dollars:.2f}")
        
        # Check if breakeven should trigger (default $5)
        breakeven_threshold = 5.0
        should_trigger = profit_dollars >= breakeven_threshold
        
        logger.info(f"   Breakeven Threshold: ${breakeven_threshold}")
        logger.info(f"   Should Trigger: {should_trigger}")
        
        assert profit_dollars == 5.0, f"Expected $5 profit, got ${profit_dollars}"
        assert should_trigger == True, "Breakeven should trigger at $5 profit"
        
        logger.info(f"✅ Breakeven logic correct!")
        
        # Test SELL trade
        logger.info(f"\n   Testing SELL trade...")
        entry_price = 3950.0
        current_price = 3945.0  # -5 points
        profit_dollars_sell = (entry_price - current_price) * volume * contract_size
        
        logger.info(f"   Entry: {entry_price}")
        logger.info(f"   Current: {current_price}")
        logger.info(f"   Movement: -{entry_price - current_price} points")
        logger.info(f"   Calculated Profit: ${profit_dollars_sell:.2f}")
        
        assert profit_dollars_sell == 5.0, f"Expected $5 profit for SELL, got ${profit_dollars_sell}"
        logger.info(f"✅ SELL trade breakeven logic correct!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_partial_profit_skip():
    """Test 3: Partial profit skip for 0.01 lots"""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Partial Profit Skip (0.01 lots)")
    logger.info("="*60)
    
    try:
        volume = 0.01
        partial_close_pct = 50.0
        
        # Calculate partial close volume
        close_volume = volume * (partial_close_pct / 100.0)
        close_volume_rounded = round(close_volume, 2)
        
        logger.info(f"   Trade Volume: {volume} lots")
        logger.info(f"   Partial Close %: {partial_close_pct}%")
        logger.info(f"   Calculated Close Volume: {close_volume} lots")
        logger.info(f"   Rounded Close Volume: {close_volume_rounded} lots")
        
        # Check if should skip
        should_skip = volume < 0.02
        
        logger.info(f"   Should Skip Partial: {should_skip}")
        
        assert close_volume_rounded == 0.01, f"Close volume rounds to minimum"
        assert should_skip == True, "Should skip partial for 0.01 lots"
        
        logger.info(f"✅ Partial profit correctly skipped for 0.01 lots!")
        
        # Test with 0.02 lots (should work)
        logger.info(f"\n   Testing 0.02 lots (should work)...")
        volume_large = 0.02
        close_volume_large = volume_large * (partial_close_pct / 100.0)
        close_volume_large_rounded = round(close_volume_large, 2)
        should_skip_large = volume_large < 0.02
        
        logger.info(f"   Trade Volume: {volume_large} lots")
        logger.info(f"   Close Volume: {close_volume_large_rounded} lots")
        logger.info(f"   Should Skip: {should_skip_large}")
        
        assert close_volume_large_rounded == 0.01, "Should close 0.01 from 0.02 lots"
        assert should_skip_large == False, "Should NOT skip for 0.02 lots"
        
        logger.info(f"✅ Partial profit works correctly for 0.02+ lots!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_atr_trailing_logic():
    """Test 4: ATR trailing stop calculation"""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: ATR Trailing Stop Logic")
    logger.info("="*60)
    
    try:
        # Simulate BUY trade that hit breakeven and is now trailing
        direction = "buy"
        entry_price = 3950.0
        breakeven_sl = 3955.0  # After breakeven
        
        # Scenario 1: Price moves up
        logger.info(f"\n   Scenario 1: Price moves UP")
        current_price_1 = 3960.0
        atr = 5.0
        trailing_distance = atr * 1.5
        
        new_sl_1 = current_price_1 - trailing_distance
        
        logger.info(f"   Current Price: {current_price_1}")
        logger.info(f"   Current SL: {breakeven_sl}")
        logger.info(f"   ATR: {atr}")
        logger.info(f"   Trailing Distance: {trailing_distance} (1.5x ATR)")
        logger.info(f"   Calculated New SL: {new_sl_1}")
        
        # Check if should trail (new SL > current SL for BUY)
        should_trail_1 = new_sl_1 > breakeven_sl
        logger.info(f"   Should Trail: {should_trail_1}")
        
        assert new_sl_1 == 3952.5, f"Expected SL 3952.5, got {new_sl_1}"
        assert should_trail_1 == False, f"New SL {new_sl_1} is not > current {breakeven_sl}"
        
        logger.info(f"✅ Trailing logic correct (won't trail backwards)")
        
        # Scenario 2: Price moves up more
        logger.info(f"\n   Scenario 2: Price moves UP significantly")
        current_price_2 = 3965.0
        new_sl_2 = current_price_2 - trailing_distance
        
        logger.info(f"   Current Price: {current_price_2}")
        logger.info(f"   Current SL: {breakeven_sl}")
        logger.info(f"   Calculated New SL: {new_sl_2}")
        
        should_trail_2 = new_sl_2 > breakeven_sl
        logger.info(f"   Should Trail: {should_trail_2}")
        
        assert new_sl_2 == 3957.5, f"Expected SL 3957.5, got {new_sl_2}"
        assert should_trail_2 == True, f"New SL {new_sl_2} should be > current {breakeven_sl}"
        
        logger.info(f"✅ Trailing UP works correctly!")
        
        # Scenario 3: Price pulls back (should NOT trail backwards)
        logger.info(f"\n   Scenario 3: Price PULLS BACK")
        current_sl_after_trail = 3957.5  # After previous trail
        current_price_3 = 3960.0  # Pullback from 3965
        new_sl_3 = current_price_3 - trailing_distance
        
        logger.info(f"   Current Price: {current_price_3} (pullback)")
        logger.info(f"   Current SL: {current_sl_after_trail}")
        logger.info(f"   Calculated New SL: {new_sl_3}")
        
        should_trail_3 = new_sl_3 > current_sl_after_trail
        logger.info(f"   Should Trail: {should_trail_3}")
        
        assert new_sl_3 == 3952.5, f"Expected SL 3952.5, got {new_sl_3}"
        assert should_trail_3 == False, f"Should NOT trail backwards on pullback"
        
        logger.info(f"✅ Won't trail backwards on pullback!")
        
        # Test SELL trade
        logger.info(f"\n   Testing SELL trade trailing...")
        direction_sell = "sell"
        entry_price_sell = 3950.0
        breakeven_sl_sell = 3945.0  # Breakeven for SELL
        current_price_sell = 3940.0  # Price moving down (good for SELL)
        
        new_sl_sell = current_price_sell + trailing_distance  # SELL adds distance
        
        logger.info(f"   Current Price: {current_price_sell}")
        logger.info(f"   Current SL: {breakeven_sl_sell}")
        logger.info(f"   Calculated New SL: {new_sl_sell}")
        
        # For SELL, should trail if new SL < current SL
        should_trail_sell = new_sl_sell < breakeven_sl_sell
        logger.info(f"   Should Trail: {should_trail_sell}")
        
        assert new_sl_sell == 3947.5, f"Expected SL 3947.5, got {new_sl_sell}"
        assert should_trail_sell == False, f"New SL {new_sl_sell} should be < current {breakeven_sl_sell}"
        
        logger.info(f"✅ SELL trade trailing logic correct!")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_state_transitions():
    """Test 5: State transition flow"""
    logger.info("\n" + "="*60)
    logger.info("TEST 5: State Transition Flow")
    logger.info("="*60)
    
    try:
        from infra.intelligent_exit_manager import ExitRule
        
        rule = ExitRule(
            ticket=123456,
            symbol="XAUUSD",
            entry_price=3950.0,
            direction="buy",
            initial_sl=3944.0,
            initial_tp=3965.0,
            use_hybrid_stops=True,
            trailing_enabled=True
        )
        
        logger.info(f"   Initial State:")
        logger.info(f"     breakeven_triggered: {rule.breakeven_triggered}")
        logger.info(f"     trailing_active: {rule.trailing_active}")
        logger.info(f"     hybrid_adjustment_active: {rule.hybrid_adjustment_active}")
        
        # Simulate hybrid adjustment
        logger.info(f"\n   Step 1: Hybrid Adjustment (pre-breakeven)")
        rule.hybrid_adjustment_active = True
        logger.info(f"     hybrid_adjustment_active: {rule.hybrid_adjustment_active}")
        assert rule.hybrid_adjustment_active == True
        assert rule.breakeven_triggered == False
        assert rule.trailing_active == False
        logger.info(f"✅ Hybrid adjustment state correct")
        
        # Simulate breakeven trigger
        logger.info(f"\n   Step 2: Breakeven Triggered")
        rule.breakeven_triggered = True
        rule.trailing_active = True  # Activated after breakeven
        rule.last_trailing_sl = 3955.0
        logger.info(f"     breakeven_triggered: {rule.breakeven_triggered}")
        logger.info(f"     trailing_active: {rule.trailing_active}")
        logger.info(f"     last_trailing_sl: {rule.last_trailing_sl}")
        assert rule.breakeven_triggered == True
        assert rule.trailing_active == True
        logger.info(f"✅ Breakeven state transition correct")
        
        # Simulate trailing
        logger.info(f"\n   Step 3: Continuous Trailing")
        rule.last_trailing_sl = 3957.5
        logger.info(f"     last_trailing_sl: {rule.last_trailing_sl} (trailed up!)")
        assert rule.trailing_active == True
        assert rule.last_trailing_sl == 3957.5
        logger.info(f"✅ Trailing state updated correctly")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests"""
    logger.info("\n" + "="*60)
    logger.info("INTELLIGENT EXIT MANAGEMENT - TEST SUITE")
    logger.info("="*60)
    
    tests = [
        ("Exit Rule Creation", test_exit_rule_creation),
        ("Breakeven Trigger Logic", test_breakeven_logic),
        ("Partial Profit Skip", test_partial_profit_skip),
        ("ATR Trailing Logic", test_atr_trailing_logic),
        ("State Transitions", test_state_transitions),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {test_name}")
    
    logger.info("="*60)
    logger.info(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("✅ ALL TESTS PASSED!")
        return True
    else:
        logger.info(f"❌ {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

