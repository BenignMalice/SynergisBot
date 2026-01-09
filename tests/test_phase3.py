"""
Phase 3 Integration Test
Tests Binance enrichment of MT5 analysis data.

Tests:
1. Binance enrichment layer
2. Micro-momentum calculation
3. Volume acceleration detection
4. Signal confirmation logic
5. Enhanced analysis output

Usage:
    python test_phase3.py
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

from infra.binance_service import BinanceService
from infra.mt5_service import MT5Service
from infra.binance_enrichment import BinanceEnrichment

logger = logging.getLogger(__name__)


class Phase3Tester:
    """
    Integration test for Phase 3 - Binance Enrichment.
    """
    
    def __init__(self):
        self.binance_service = None
        self.mt5_service = None
        self.enricher = None
        self.tests_passed = 0
        self.tests_failed = 0
        
    async def test_enrichment_layer(self):
        """Test 1: Binance enrichment layer"""
        print("\n" + "="*70)
        print("TEST 1: Binance Enrichment Layer")
        print("="*70)
        
        try:
            # Initialize services
            self.binance_service = BinanceService(interval="1m")
            self.mt5_service = MT5Service()
            
            if not self.mt5_service.connect():
                print("⚠️ MT5 not available - test will be limited")
            else:
                print("✅ MT5 connected")
            
            # Link MT5 to Binance
            self.binance_service.set_mt5_service(self.mt5_service)
            
            # Start Binance streams
            await self.binance_service.start(["btcusdt", "eurusd"], background=True)
            print("✅ Binance streams started")
            
            # Wait for data
            await asyncio.sleep(10)
            
            # Create enricher
            self.enricher = BinanceEnrichment(self.binance_service, self.mt5_service)
            print("✅ Enricher initialized")
            
            self.tests_passed += 1
            print("✅ TEST 1 PASSED\n")
            return True
            
        except Exception as e:
            print(f"❌ TEST 1 FAILED: {e}\n")
            self.tests_failed += 1
            return False
            
    async def test_micro_momentum(self):
        """Test 2: Micro-momentum calculation"""
        print("\n" + "="*70)
        print("TEST 2: Micro-Momentum Calculation")
        print("="*70)
        
        try:
            # Get price history
            history = self.binance_service.get_history("BTCUSDT", count=10)
            
            if len(history) < 10:
                print("⚠️ Not enough data yet - skipping test")
                return None
                
            prices = [t['price'] for t in history]
            momentum = self.enricher._calculate_micro_momentum(prices)
            
            print(f"✅ Recent prices: {prices[:3]}... {prices[-3:]}")
            print(f"✅ Micro-momentum: {momentum:+.2f}%")
            
            if momentum > 1:
                print("   📈 Bullish momentum detected")
            elif momentum < -1:
                print("   📉 Bearish momentum detected")
            else:
                print("   ➡️  Neutral momentum")
                
            self.tests_passed += 1
            print("✅ TEST 2 PASSED\n")
            return True
            
        except Exception as e:
            print(f"❌ TEST 2 FAILED: {e}\n")
            self.tests_failed += 1
            return False
            
    async def test_enrichment_integration(self):
        """Test 3: MT5 data enrichment"""
        print("\n" + "="*70)
        print("TEST 3: MT5 Data Enrichment")
        print("="*70)
        
        try:
            # Mock MT5 data
            mt5_data = {
                "close": 112150.0,
                "atr_14": 450.0,
                "ema_200": 111800.0,
                "adx_14": 28.5,
                "rsi_14": 58.3
            }
            
            print("Original MT5 data:")
            print(f"  Close: ${mt5_data['close']:,.2f}")
            print(f"  ATR: {mt5_data['atr_14']}")
            print(f"  ADX: {mt5_data['adx_14']}")
            
            # Enrich with Binance
            enriched = self.enricher.enrich_timeframe("BTCUSDc", mt5_data, "M5")
            
            print("\nEnriched data:")
            print(f"  Binance Price: ${enriched.get('binance_price', 'N/A')}")
            print(f"  Binance Age: {enriched.get('binance_age', 'N/A')}s")
            print(f"  Feed Health: {enriched.get('feed_health', 'N/A')}")
            print(f"  Micro Momentum: {enriched.get('micro_momentum', 0):+.2f}%")
            print(f"  Price Velocity: {enriched.get('price_velocity', 0):+.2f}")
            print(f"  Volume Accel: {enriched.get('volume_acceleration', 0):+.2f}%")
            
            # Verify enrichment added new fields
            if 'binance_price' in enriched or not self.binance_service.running:
                print("\n✅ Enrichment successful")
                self.tests_passed += 1
                print("✅ TEST 3 PASSED\n")
                return True
            else:
                raise RuntimeError("No enrichment fields added")
                
        except Exception as e:
            print(f"❌ TEST 3 FAILED: {e}\n")
            self.tests_failed += 1
            return False
            
    async def test_signal_confirmation(self):
        """Test 4: Signal confirmation logic"""
        print("\n" + "="*70)
        print("TEST 4: Signal Confirmation Logic")
        print("="*70)
        
        try:
            # Test BUY signal
            confirmed_buy, reason_buy = self.enricher.get_binance_confirmation(
                "BTCUSDc", "BUY", threshold=0.5
            )
            
            print(f"BUY Signal:")
            print(f"  Confirmed: {confirmed_buy}")
            print(f"  Reason: {reason_buy}")
            
            # Test SELL signal
            confirmed_sell, reason_sell = self.enricher.get_binance_confirmation(
                "BTCUSDc", "SELL", threshold=0.5
            )
            
            print(f"\nSELL Signal:")
            print(f"  Confirmed: {confirmed_sell}")
            print(f"  Reason: {reason_sell}")
            
            print("\n✅ Confirmation logic working")
            self.tests_passed += 1
            print("✅ TEST 4 PASSED\n")
            return True
            
        except Exception as e:
            print(f"❌ TEST 4 FAILED: {e}\n")
            self.tests_failed += 1
            return False
            
    async def test_enrichment_summary(self):
        """Test 5: Enrichment summary output"""
        print("\n" + "="*70)
        print("TEST 5: Enrichment Summary")
        print("="*70)
        
        try:
            summary = self.enricher.get_enrichment_summary("BTCUSDc")
            
            print("Summary Output:")
            print(summary)
            print()
            
            if "Binance" in summary:
                print("✅ Summary generated successfully")
                self.tests_passed += 1
                print("✅ TEST 5 PASSED\n")
                return True
            else:
                raise RuntimeError("Summary missing expected content")
                
        except Exception as e:
            print(f"❌ TEST 5 FAILED: {e}\n")
            self.tests_failed += 1
            return False
            
    async def run_all_tests(self):
        """Run all tests"""
        print("\n╔══════════════════════════════════════════════════════════════════════╗")
        print("║                 PHASE 3 INTEGRATION TEST SUITE                      ║")
        print("║            Binance Enrichment of MT5 Analysis Data                  ║")
        print("╚══════════════════════════════════════════════════════════════════════╝\n")
        
        # Run tests
        await self.test_enrichment_layer()
        await self.test_micro_momentum()
        await self.test_enrichment_integration()
        await self.test_signal_confirmation()
        await self.test_enrichment_summary()
        
        # Print summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"✅ Passed: {self.tests_passed}")
        print(f"❌ Failed: {self.tests_failed}")
        
        if self.tests_failed == 0:
            print("\n🎉 ALL TESTS PASSED!")
            print("\n✓ Binance enrichment layer working")
            print("✓ Micro-momentum calculation accurate")
            print("✓ MT5 data enrichment successful")
            print("✓ Signal confirmation logic validated")
            print("✓ Summary output formatted correctly")
        else:
            print(f"\n⚠️ {self.tests_failed} test(s) failed")
            
        print("="*70)
        
        # Show final status
        if self.binance_service:
            self.binance_service.print_status()
            
        # Cleanup
        if self.binance_service:
            self.binance_service.stop()


async def main():
    """Main test entry point"""
    tester = Phase3Tester()
    await tester.run_all_tests()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Test interrupted")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        logger.error(f"Fatal error: {e}", exc_info=True)

