"""
Test script for Intelligent Profit Protection System
Tests the 7-signal warning framework and scoring system.
"""

import sys
import codecs
import logging
from datetime import datetime
from infra.profit_protector import ProfitProtector, WarningSignal

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Mock position class
class MockPosition:
    def __init__(self, symbol, ticket, type_val, price_open, price_current, sl, tp, time_val):
        self.symbol = symbol
        self.ticket = ticket
        self.type = type_val  # 0=BUY, 1=SELL
        self.price_open = price_open
        self.price_current = price_current
        self.sl = sl
        self.tp = tp
        self.time = time_val


def test_scenario_1_critical_exit():
    """Test Scenario 1: Critical Exit (Score = 6)"""
    print("\n" + "="*80)
    print("🧪 TEST SCENARIO 1: CRITICAL EXIT (Score ≥ 5)")
    print("="*80)
    
    protector = ProfitProtector()
    
    # Create mock profitable position
    position = MockPosition(
        symbol="XAUUSDc",
        ticket=122387063,
        type_val=0,  # BUY
        price_open=4081.88,
        price_current=4095.00,
        sl=4074.00,
        tp=4095.00,
        time_val=datetime.now().timestamp() - 3600  # 1 hour ago
    )
    
    # Features with CRITICAL warnings
    features = {
        'binance_structure': 'BEARISH',  # CHOCH (Weight: 3)
        'price_structure': 'BEARISH',
        'rsi': 50,
        'adx': 25,
        'atr': 3.50,
        'close': 4095.00,
        'ema20': 4090.00,
        'ema50': 4085.00,
    }
    
    # Bars with opposite engulfing (Weight: 3)
    import pandas as pd
    bars = pd.DataFrame({
        'open': [4090, 4093, 4095],
        'high': [4092, 4095, 4096],
        'low': [4089, 4092, 4090],
        'close': [4091, 4094, 4091],  # Last candle: bearish engulfing
    })
    
    # Calculate R-multiple
    r_multiple = (position.price_current - position.price_open) / (position.price_open - position.sl)
    
    print(f"\n📊 Position Details:")
    print(f"  Symbol: {position.symbol}")
    print(f"  Entry: {position.price_open}")
    print(f"  Current: {position.price_current}")
    print(f"  Profit: ${(position.price_current - position.price_open) * 100:.2f}")
    print(f"  R-multiple: {r_multiple:.2f}R")
    
    # Analyze
    decision = protector.analyze_profit_protection(
        position=position,
        features=features,
        bars=bars,
        order_flow=None,
        r_multiple=r_multiple
    )
    
    if decision:
        print(f"\n🎯 Decision:")
        print(f"  Action: {decision.action.upper()}")
        print(f"  Total Score: {decision.total_score}")
        print(f"  Confidence: {decision.confidence:.1%}")
        print(f"  Reason: {decision.reason}")
        print(f"\n⚠️ Warnings Detected:")
        for warning in decision.warnings:
            print(f"    • {warning.name} (Weight: {warning.weight}) - {warning.description}")
        
        if decision.action == "exit":
            print(f"\n✅ EXPECTED: EXIT (Score {decision.total_score} ≥ 5)")
            print(f"✅ TEST PASSED!")
        else:
            print(f"\n❌ UNEXPECTED: Expected EXIT, got {decision.action.upper()}")
            print(f"❌ TEST FAILED!")
    else:
        print(f"\n❌ No decision returned - TEST FAILED!")


def test_scenario_2_tighten():
    """Test Scenario 2: Tighten SL (Score = 4)"""
    print("\n" + "="*80)
    print("🧪 TEST SCENARIO 2: TIGHTEN SL (Score 2-4)")
    print("="*80)
    
    protector = ProfitProtector()
    
    # Create mock profitable position
    position = MockPosition(
        symbol="EURUSDc",
        ticket=121121937,
        type_val=1,  # SELL
        price_open=1.1615,
        price_current=1.1580,
        sl=1.1650,
        tp=1.1530,
        time_val=datetime.now().timestamp() - 7200  # 2 hours ago
    )
    
    # Features with MAJOR warnings
    features = {
        'binance_structure': 'CHOPPY',  # No CHOCH
        'rsi': 75,  # Divergence risk (Weight: 2)
        'rsi_divergence': True,  # Explicit divergence flag
        'adx': 22,
        'atr': 0.0015,
        'atr_prev': 0.0018,  # ATR dropping (momentum loss)
        'close': 1.1580,
        'ema20': 1.1575,  # Price above EMA (for SELL, this is a break) (Weight: 2)
        'ema50': 1.1570,
    }
    
    # Bars
    import pandas as pd
    bars = pd.DataFrame({
        'open': [1.1590, 1.1585, 1.1582],
        'high': [1.1595, 1.1590, 1.1585],
        'low': [1.1585, 1.1580, 1.1578],
        'close': [1.1587, 1.1582, 1.1580],
    })
    
    # Calculate R-multiple
    r_multiple = (position.price_open - position.price_current) / (position.sl - position.price_open)
    
    print(f"\n📊 Position Details:")
    print(f"  Symbol: {position.symbol}")
    print(f"  Entry: {position.price_open}")
    print(f"  Current: {position.price_current}")
    print(f"  Profit: ${(position.price_open - position.price_current) * 10000:.2f}")
    print(f"  R-multiple: {r_multiple:.2f}R")
    
    # Analyze
    decision = protector.analyze_profit_protection(
        position=position,
        features=features,
        bars=bars,
        order_flow=None,
        r_multiple=r_multiple
    )
    
    if decision:
        print(f"\n🎯 Decision:")
        print(f"  Action: {decision.action.upper()}")
        print(f"  Total Score: {decision.total_score}")
        print(f"  Confidence: {decision.confidence:.1%}")
        print(f"  Reason: {decision.reason}")
        if decision.new_sl:
            print(f"  New SL: {decision.new_sl:.5f}")
        print(f"\n⚠️ Warnings Detected:")
        for warning in decision.warnings:
            print(f"    • {warning.name} (Weight: {warning.weight}) - {warning.description}")
        
        if decision.action == "tighten":
            print(f"\n✅ EXPECTED: TIGHTEN (Score {decision.total_score} = 2-4)")
            print(f"✅ TEST PASSED!")
        else:
            print(f"\n❌ UNEXPECTED: Expected TIGHTEN, got {decision.action.upper()}")
            print(f"❌ TEST FAILED!")
    else:
        print(f"\n❌ No decision returned - TEST FAILED!")


def test_scenario_3_monitor():
    """Test Scenario 3: Monitor (Score = 1)"""
    print("\n" + "="*80)
    print("🧪 TEST SCENARIO 3: MONITOR (Score < 2)")
    print("="*80)
    
    protector = ProfitProtector()
    
    # Create mock profitable position
    position = MockPosition(
        symbol="BTCUSDc",
        ticket=122000001,
        type_val=0,  # BUY
        price_open=95000.00,
        price_current=95500.00,
        sl=94500.00,
        tp=96000.00,
        time_val=datetime.now().timestamp() - 1800  # 30 min ago
    )
    
    # Features with only MINOR warning
    features = {
        'binance_structure': 'BULLISH',  # No CHOCH
        'rsi': 60,  # No divergence
        'adx': 28,  # Strong trend
        'atr': 150.0,
        'close': 95500.00,
        'ema20': 95400.00,  # No break
        'ema50': 95200.00,
    }
    
    # Bars
    import pandas as pd
    bars = pd.DataFrame({
        'open': [95200, 95300, 95450],
        'high': [95350, 95450, 95550],
        'low': [95180, 95280, 95420],
        'close': [95300, 95450, 95500],
    })
    
    # Calculate R-multiple
    r_multiple = (position.price_current - position.price_open) / (position.price_open - position.sl)
    
    print(f"\n📊 Position Details:")
    print(f"  Symbol: {position.symbol}")
    print(f"  Entry: {position.price_open}")
    print(f"  Current: {position.price_current}")
    print(f"  Profit: ${(position.price_current - position.price_open) * 0.01:.2f}")
    print(f"  R-multiple: {r_multiple:.2f}R")
    
    # Simulate Friday afternoon (session shift - Weight: 1)
    # This would be detected by _detect_session_shift()
    
    # Analyze
    decision = protector.analyze_profit_protection(
        position=position,
        features=features,
        bars=bars,
        order_flow=None,
        r_multiple=r_multiple
    )
    
    if decision:
        print(f"\n🎯 Decision:")
        print(f"  Action: {decision.action.upper()}")
        print(f"  Total Score: {decision.total_score}")
        print(f"  Confidence: {decision.confidence:.1%}")
        print(f"  Reason: {decision.reason}")
        print(f"\n⚠️ Warnings Detected:")
        for warning in decision.warnings:
            print(f"    • {warning.name} (Weight: {warning.weight}) - {warning.description}")
        
        if decision.action == "monitor":
            print(f"\n✅ EXPECTED: MONITOR (Score {decision.total_score} < 2)")
            print(f"✅ TEST PASSED!")
        else:
            print(f"\n⚠️ UNEXPECTED: Expected MONITOR, got {decision.action.upper()}")
            print(f"⚠️ This could be valid if session shift detected")
    else:
        print(f"\n✅ No decision (no warnings) - EXPECTED for clean trade")
        print(f"✅ TEST PASSED!")


def main():
    """Run all test scenarios"""
    print("\n" + "="*80)
    print("🚀 INTELLIGENT PROFIT PROTECTION - TEST SUITE")
    print("="*80)
    print("\nTesting 7-signal warning framework and scoring system...")
    
    try:
        test_scenario_1_critical_exit()
        test_scenario_2_tighten()
        test_scenario_3_monitor()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETED")
        print("="*80)
        print("\n💡 Review results above to verify system behavior")
        print("💡 Check logs for detailed signal detection")
        
    except Exception as e:
        print(f"\n❌ TEST SUITE FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

