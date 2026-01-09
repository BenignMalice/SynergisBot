"""
Test SELL Trailing Stop Logic Correction

Verifies that:
1. For SELL trades, SL never moves UP (would reduce profit)
2. For SELL trades, SL only moves DOWN (locks in more profit)
3. Trailing activates correctly when price moves down enough
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dataclasses import dataclass
from typing import Optional, Dict
from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager, TradeState

@dataclass
class MockTradeState:
    """Mock TradeState for testing"""
    ticket: int
    symbol: str
    direction: str
    entry_price: float
    initial_sl: float
    current_sl: Optional[float]
    current_price: float
    breakeven_triggered: bool = True
    resolved_trailing_rules: Dict = None
    
    def __post_init__(self):
        if self.resolved_trailing_rules is None:
            self.resolved_trailing_rules = {
                "trailing_enabled": True,
                "trailing_method": "atr_basic",
                "atr_multiplier": 1.5,
                "atr_timeframe": "M15",
                "fallback_trailing_methods": ["fixed_distance", "percentage"]
            }

def test_sell_trailing_never_moves_up():
    """Test that SELL trailing stop never moves SL UP (would reduce profit)"""
    print("\n" + "="*70)
    print("TEST 1: SELL Trailing Stop Never Moves SL UP")
    print("="*70)
    
    manager = UniversalDynamicSLTPManager()
    
    # Create mock trade state
    trade_state = MockTradeState(
        ticket=999999,
        symbol="XAUUSDc",
        direction="SELL",
        entry_price=4324.02,
        initial_sl=4350.00,
        current_sl=4318.79,  # Current SL locks in ~$5 profit
        current_price=4317.23,  # Price moved down (profit)
        breakeven_triggered=True
    )
    
    # Mock ATR to return a value
    original_get_atr = manager._get_current_atr
    def mock_get_atr(symbol, timeframe, period=14):
        return 6.5  # ~9.75 points trailing distance (6.5 * 1.5)
    manager._get_current_atr = mock_get_atr
    
    # Mock MT5 to return price
    import MetaTrader5 as mt5
    original_symbol_info_tick = mt5.symbol_info_tick
    class MockTick:
        def __init__(self, price):
            self.bid = price
            self.ask = price
    def mock_symbol_info_tick(symbol):
        return MockTick(trade_state.current_price)
    mt5.symbol_info_tick = mock_symbol_info_tick
    
    # Convert to TradeState
    real_trade_state = TradeState(
        ticket=trade_state.ticket,
        symbol=trade_state.symbol,
        strategy_type="test",
        direction=trade_state.direction,
        session="test",
        resolved_trailing_rules=trade_state.resolved_trailing_rules,
        managed_by="test",
        entry_price=trade_state.entry_price,
        initial_sl=trade_state.initial_sl,
        initial_tp=0.0,
        current_price=trade_state.current_price,
        current_sl=trade_state.current_sl,
        breakeven_triggered=trade_state.breakeven_triggered
    )
    
    try:
        # Calculate ideal trailing SL
        rules = trade_state.resolved_trailing_rules
        ideal_sl = manager._get_atr_based_sl(
            real_trade_state,
            rules,
            rules.get("atr_multiplier", 1.5),
            rules.get("atr_timeframe", "M15")
        )
    finally:
        # Restore original functions
        manager._get_current_atr = original_get_atr
        mt5.symbol_info_tick = original_symbol_info_tick
    
    print(f"\nEntry Price: {trade_state.entry_price:.2f}")
    print(f"Current SL: {trade_state.current_sl:.2f} (locks in ~$5 profit)")
    print(f"Current Price: {trade_state.current_price:.2f} (moved down = profit)")
    print(f"Trailing Distance: ~9.75 points")
    ideal_sl_str = f"{ideal_sl:.2f}" if ideal_sl is not None else "None"
    print(f"Ideal Trailing SL: {ideal_sl_str}")
    
    if ideal_sl:
        print(f"\nSL Change: {trade_state.current_sl:.2f} -> {ideal_sl:.2f}")
        if ideal_sl > trade_state.current_sl:
            print("[FAIL] System tried to move SL UP (would reduce profit!)")
            print(f"   If SL moved to {ideal_sl:.2f} and price hit it:")
            print(f"   Profit = {trade_state.entry_price:.2f} - {ideal_sl:.2f} = "
                  f"{trade_state.entry_price - ideal_sl:.2f} (LOSS!)")
            return False
        else:
            print("[PASS] System correctly moves SL DOWN (locks in more profit)")
            return True
    else:
        print("\n[PASS] System correctly rejected moving SL UP")
        print("   (Ideal SL would be higher than current, which would reduce profit)")
        return True

def test_sell_trailing_moves_down_when_price_moves_down():
    """Test that SELL trailing stop moves SL DOWN when price moves down enough"""
    print("\n" + "="*70)
    print("TEST 2: SELL Trailing Stop Moves SL DOWN (Locks in More Profit)")
    print("="*70)
    
    manager = UniversalDynamicSLTPManager()
    
    # Create mock trade state where price has moved down significantly
    trade_state = MockTradeState(
        ticket=999998,
        symbol="XAUUSDc",
        direction="SELL",
        entry_price=4324.02,
        initial_sl=4350.00,
        current_sl=4318.79,  # Current SL
        current_price=4308.00,  # Price moved down significantly (more profit)
        breakeven_triggered=True
    )
    
    # Mock ATR
    original_get_atr = manager._get_current_atr
    def mock_get_atr(symbol, timeframe, period=14):
        return 6.5
    manager._get_current_atr = mock_get_atr
    
    # Mock MT5 to return price
    import MetaTrader5 as mt5
    original_symbol_info_tick = mt5.symbol_info_tick
    class MockTick:
        def __init__(self, price):
            self.bid = price
            self.ask = price
    def mock_symbol_info_tick(symbol):
        return MockTick(trade_state.current_price)
    mt5.symbol_info_tick = mock_symbol_info_tick
    
    # Convert to TradeState
    real_trade_state = TradeState(
        ticket=trade_state.ticket,
        symbol=trade_state.symbol,
        strategy_type="test",
        direction=trade_state.direction,
        session="test",
        resolved_trailing_rules=trade_state.resolved_trailing_rules,
        managed_by="test",
        entry_price=trade_state.entry_price,
        initial_sl=trade_state.initial_sl,
        initial_tp=0.0,
        current_price=trade_state.current_price,
        current_sl=trade_state.current_sl,
        breakeven_triggered=trade_state.breakeven_triggered
    )
    
    try:
        # Calculate ideal trailing SL
        rules = trade_state.resolved_trailing_rules
        ideal_sl = manager._get_atr_based_sl(
            real_trade_state,
            rules,
            rules.get("atr_multiplier", 1.5),
            rules.get("atr_timeframe", "M15")
        )
    finally:
        # Restore original functions
        manager._get_current_atr = original_get_atr
        mt5.symbol_info_tick = original_symbol_info_tick
    
    print(f"\nEntry Price: {trade_state.entry_price:.2f}")
    print(f"Current SL: {trade_state.current_sl:.2f}")
    print(f"Current Price: {trade_state.current_price:.2f} (moved down significantly)")
    print(f"Trailing Distance: ~9.75 points")
    ideal_sl_str = f"{ideal_sl:.2f}" if ideal_sl is not None else "None"
    print(f"Ideal Trailing SL: {ideal_sl_str}")
    
    if ideal_sl:
        print(f"\nSL Change: {trade_state.current_sl:.2f} -> {ideal_sl:.2f}")
        if ideal_sl < trade_state.current_sl:
            print("[PASS] System correctly moves SL DOWN (locks in more profit)")
            profit_locked = trade_state.entry_price - ideal_sl
            print(f"   Profit locked in: {profit_locked:.2f} points")
            return True
        else:
            print("[FAIL] System should move SL DOWN but didn't")
            return False
    else:
        print("\n[FAIL] System rejected trailing when it should have allowed it")
        return False

def test_sell_trailing_profit_protection():
    """Test that SELL trailing stop protects profit correctly"""
    print("\n" + "="*70)
    print("TEST 3: SELL Trailing Stop Protects Profit")
    print("="*70)
    
    manager = UniversalDynamicSLTPManager()
    
    # Scenario: Price moved down, but ideal SL would reduce profit
    trade_state = MockTradeState(
        ticket=999997,
        symbol="XAUUSDc",
        direction="SELL",
        entry_price=4324.02,
        initial_sl=4350.00,
        current_sl=4318.79,  # Locks in ~$5 profit
        current_price=4317.23,  # Price moved down
        breakeven_triggered=True
    )
    
    # Mock ATR
    original_get_atr = manager._get_current_atr
    def mock_get_atr(symbol, timeframe, period=14):
        return 6.5
    manager._get_current_atr = mock_get_atr
    
    # Mock MT5 to return price
    import MetaTrader5 as mt5
    original_symbol_info_tick = mt5.symbol_info_tick
    class MockTick:
        def __init__(self, price):
            self.bid = price
            self.ask = price
    def mock_symbol_info_tick(symbol):
        return MockTick(trade_state.current_price)
    mt5.symbol_info_tick = mock_symbol_info_tick
    
    # Convert to TradeState
    real_trade_state = TradeState(
        ticket=trade_state.ticket,
        symbol=trade_state.symbol,
        strategy_type="test",
        direction=trade_state.direction,
        session="test",
        resolved_trailing_rules=trade_state.resolved_trailing_rules,
        managed_by="test",
        entry_price=trade_state.entry_price,
        initial_sl=trade_state.initial_sl,
        initial_tp=0.0,
        current_price=trade_state.current_price,
        current_sl=trade_state.current_sl,
        breakeven_triggered=trade_state.breakeven_triggered
    )
    
    try:
        # Calculate ideal trailing SL
        rules = trade_state.resolved_trailing_rules
        ideal_sl = manager._get_atr_based_sl(
            real_trade_state,
            rules,
            rules.get("atr_multiplier", 1.5),
            rules.get("atr_timeframe", "M15")
        )
    finally:
        # Restore original functions
        manager._get_current_atr = original_get_atr
        mt5.symbol_info_tick = original_symbol_info_tick
    
    current_profit = trade_state.entry_price - trade_state.current_sl
    if ideal_sl:
        potential_profit = trade_state.entry_price - ideal_sl
    else:
        potential_profit = current_profit
    
    print(f"\nEntry Price: {trade_state.entry_price:.2f}")
    print(f"Current SL: {trade_state.current_sl:.2f}")
    print(f"Current Profit Locked: {current_profit:.2f} points")
    
    if ideal_sl:
        print(f"Ideal Trailing SL: {ideal_sl:.2f}")
        print(f"Potential Profit: {potential_profit:.2f} points")
        
        if ideal_sl > trade_state.current_sl:
            print("\n❌ FAIL: System would reduce profit!")
            print(f"   Current profit: {current_profit:.2f} points")
            print(f"   Potential profit: {potential_profit:.2f} points")
            print(f"   Loss: {current_profit - potential_profit:.2f} points")
            return False
        else:
            print("\n✅ PASS: System protects profit")
            print(f"   Current profit: {current_profit:.2f} points")
            print(f"   New profit: {potential_profit:.2f} points")
            print(f"   Gain: {potential_profit - current_profit:.2f} points")
            return True
    else:
        print(f"\n[PASS] System correctly rejected change that would reduce profit")
        print(f"   Profit remains protected at: {current_profit:.2f} points")
        return True

if __name__ == "__main__":
    print("\n" + "="*70)
    print("SELL TRAILING STOP LOGIC TEST")
    print("="*70)
    print("\nTesting corrected logic:")
    print("  - SELL trailing stops should NEVER move SL UP")
    print("  - SELL trailing stops should ONLY move SL DOWN")
    print("  - This protects profit instead of reducing it")
    print("="*70)
    
    results = []
    
    # Run tests
    results.append(("Never Moves SL UP", test_sell_trailing_never_moves_up()))
    results.append(("Moves SL DOWN When Appropriate", test_sell_trailing_moves_down_when_price_moves_down()))
    results.append(("Protects Profit", test_sell_trailing_profit_protection()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] ALL TESTS PASSED - SELL trailing stop logic is correct!")
    else:
        print("\n[ERROR] SOME TESTS FAILED - Review the logic")
    
    print("="*70 + "\n")
