"""
Phase 1 Integration Test
Tests all Phase 1 components working together.

Tests:
1. Binance stream connectivity
2. Price cache storage
3. Price sync manager offset calculation
4. Feed validator safety checks
5. End-to-end: Binance → Cache → Sync → Validate

Usage:
    python test_phase1.py
"""

import asyncio
import logging
import sys
import codecs
import time

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from infra.binance_stream import BinanceStream
from infra.price_cache import PriceCache
from infra.price_sync_manager import PriceSyncManager
from infra.feed_validator import FeedValidator

logger = logging.getLogger(__name__)


class Phase1Tester:
    """
    Integration test for Phase 1 components.
    """
    
    def __init__(self):
        self.cache = PriceCache(max_ticks=1000)
        self.sync_manager = PriceSyncManager(calibration_window=60)
        self.feed_validator = FeedValidator(max_offset=100)
        self.stream = None
        
        self.tick_count = 0
        self.test_results = []
        
    async def on_tick(self, tick: dict):
        """
        Callback for each Binance tick.
        Simulates the full pipeline:
        1. Store in cache
        2. Calculate offset (mock MT5 price)
        3. Validate safety
        """
        self.tick_count += 1
        symbol = tick['symbol']
        binance_price = tick['price']
        
        # Step 1: Update cache
        self.cache.update(symbol, tick)
        
        # Step 2: Simulate MT5 price (add random offset)
        # In real use, you'd get this from MT5Service
        import random
        simulated_offset = random.uniform(-80, 80)  # ±80 pips
        mt5_price = binance_price - simulated_offset
        mt5_bid = mt5_price - 2.5  # Simulate spread
        mt5_ask = mt5_price + 2.5
        
        # Step 3: Update sync manager
        self.sync_manager.update_offset(symbol, binance_price, mt5_price)
        
        # Step 4: Validate safety
        offset = self.sync_manager.get_current_offset(symbol)
        is_safe, reason = self.feed_validator.validate_execution_safety(
            symbol=symbol,
            binance_price=binance_price,
            mt5_bid=mt5_bid,
            mt5_ask=mt5_ask,
            offset=offset
        )
        
        # Log every 10th tick
        if self.tick_count % 10 == 0:
            print(f"\n📊 Tick #{self.tick_count} - {symbol}")
            print(f"  Binance: ${binance_price:,.2f}")
            print(f"  MT5 (sim): ${mt5_price:,.2f}")
            offset_str = f"{offset:.2f}" if offset is not None else "N/A"
            print(f"  Offset: {offset_str} pips")
            print(f"  Safety: {'✅ SAFE' if is_safe else f'⚠️ UNSAFE - {reason}'}")
            
            # Print summaries every 30 ticks
            if self.tick_count % 30 == 0:
                self.print_summaries()
                
    def print_summaries(self):
        """
        Print summary of all components.
        """
        print("\n" + "="*70)
        print(f"📈 PHASE 1 STATUS (Tick #{self.tick_count})")
        print("="*70)
        
        self.cache.print_summary()
        self.sync_manager.print_summary()
        self.feed_validator.print_summary()
        
    async def run_test(self, duration_seconds: int = 60):
        """
        Run integration test for specified duration.
        
        Args:
            duration_seconds: How long to run the test
        """
        print("\n🚀 Starting Phase 1 Integration Test")
        print(f"⏱️  Duration: {duration_seconds} seconds")
        print(f"📡 Streaming: BTCUSDT, ETHUSDT")
        print("\nPress Ctrl+C to stop early\n")
        print("="*70 + "\n")
        
        # Create stream
        self.stream = BinanceStream(
            symbols=["btcusdt", "ethusdt"],
            callback=self.on_tick,
            interval="1m"
        )
        
        # Start streaming with timeout
        try:
            await asyncio.wait_for(
                self.stream.start_all(),
                timeout=duration_seconds
            )
        except asyncio.TimeoutError:
            print(f"\n⏱️  Test duration reached ({duration_seconds}s)")
        except KeyboardInterrupt:
            print("\n⌨️  Interrupted by user")
        finally:
            self.stream.stop()
            
        # Final summary
        print("\n" + "="*70)
        print("✅ PHASE 1 TEST COMPLETE")
        print("="*70)
        print(f"Total Ticks Processed: {self.tick_count}")
        print()
        
        self.print_summaries()
        
        # Test signal adjustment
        self.test_signal_adjustment()
        
    def test_signal_adjustment(self):
        """
        Test signal price adjustment for MT5 execution.
        """
        print("\n" + "="*70)
        print("🧪 TESTING SIGNAL ADJUSTMENT")
        print("="*70 + "\n")
        
        # Mock signal from GPT (Binance prices)
        mock_signal = {
            "symbol": "BTCUSDT",
            "action": "BUY",
            "entry": 112150.0,
            "sl": 112000.0,
            "tp": 112400.0,
            "confidence": 85
        }
        
        print("Original Signal (Binance prices):")
        print(f"  Entry: ${mock_signal['entry']:,.2f}")
        print(f"  SL: ${mock_signal['sl']:,.2f}")
        print(f"  TP: ${mock_signal['tp']:,.2f}\n")
        
        # Adjust for MT5
        adjusted = self.sync_manager.adjust_signal_for_mt5("BTCUSDT", mock_signal)
        
        print("Adjusted Signal (MT5 prices):")
        print(f"  Entry: ${adjusted['entry']:,.2f}")
        print(f"  SL: ${adjusted['sl']:,.2f}")
        print(f"  TP: ${adjusted['tp']:,.2f}")
        print(f"  Offset Applied: {adjusted.get('_offset_applied', 'N/A'):.2f} pips\n")
        
        # Validate adjusted signal
        is_safe, reason = self.feed_validator.validate_execution_safety(
            symbol="BTCUSDT",
            binance_price=mock_signal['entry'],
            mt5_bid=adjusted['entry'] - 2.5,
            mt5_ask=adjusted['entry'] + 2.5,
            offset=adjusted.get('_offset_applied')
        )
        
        print(f"Validation: {'✅ SAFE TO EXECUTE' if is_safe else f'⚠️ UNSAFE - {reason}'}")
        print("="*70 + "\n")


async def main():
    """
    Main test entry point.
    """
    tester = Phase1Tester()
    
    # Run test for 60 seconds (or until Ctrl+C)
    await tester.run_test(duration_seconds=60)
    
    print("👋 Test complete!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                  PHASE 1 INTEGRATION TEST                            ║
║                                                                      ║
║  Tests:                                                              ║
║    1. ✅ Binance Stream      - Real-time price data                  ║
║    2. ✅ Price Cache         - Tick storage & retrieval              ║
║    3. ✅ Price Sync Manager  - Offset calibration                    ║
║    4. ✅ Feed Validator      - Safety checks                         ║
║    5. ✅ End-to-End Pipeline - Full integration                      ║
║                                                                      ║
║  This test will run for 60 seconds. Press Ctrl+C to stop early.     ║
╚══════════════════════════════════════════════════════════════════════╝
""")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        raise



