"""
Test Order Flow Integration

Verifies:
1. Depth stream connectivity
2. AggTrades stream connectivity
3. Order flow analyzer signals
4. Whale detection
5. Liquidity void detection
6. Integration with BinanceEnrichment
"""

import asyncio
import sys
import codecs
import logging
import time

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    try:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass

from infra.order_flow_service import OrderFlowService
from infra.binance_service import BinanceService
from infra.binance_enrichment import BinanceEnrichment

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


async def test_order_flow():
    """Test order flow integration"""
    
    logger.info("=" * 70)
    logger.info("🧪 TESTING ORDER FLOW INTEGRATION")
    logger.info("=" * 70)
    
    # Test symbols
    test_symbols = ["btcusdt", "xauusd"]
    
    # ===========================================
    # TEST 1: Initialize Order Flow Service
    # ===========================================
    logger.info("\n📊 TEST 1: Initialize Order Flow Service")
    logger.info("-" * 70)
    
    try:
        order_flow_service = OrderFlowService()
        logger.info("✅ OrderFlowService created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create OrderFlowService: {e}")
        return
    
    # ===========================================
    # TEST 2: Start Streams
    # ===========================================
    logger.info("\n📊 TEST 2: Start Order Flow Streams")
    logger.info("-" * 70)
    
    try:
        await order_flow_service.start(test_symbols, background=True)
        logger.info("✅ Order flow streams started")
        
        # Wait for data to accumulate
        logger.info("⏳ Waiting 10 seconds for data accumulation...")
        await asyncio.sleep(10)
        
    except Exception as e:
        logger.error(f"❌ Failed to start streams: {e}")
        order_flow_service.stop()
        return
    
    # ===========================================
    # TEST 3: Check Order Book Imbalance
    # ===========================================
    logger.info("\n📊 TEST 3: Check Order Book Imbalance")
    logger.info("-" * 70)
    
    for symbol in test_symbols:
        try:
            imbalance = order_flow_service.get_order_book_imbalance(symbol.upper())
            if imbalance:
                imb_emoji = "🟢" if imbalance > 1.2 else "🔴" if imbalance < 0.8 else "⚪"
                logger.info(f"{imb_emoji} {symbol.upper()}: Imbalance = {imbalance:.2f}")
                
                if imbalance > 1.2:
                    logger.info(f"   📈 Bullish pressure ({(imbalance - 1) * 100:+.1f}% more bids)")
                elif imbalance < 0.8:
                    logger.info(f"   📉 Bearish pressure ({(1 - imbalance) * 100:.1f}% more asks)")
                else:
                    logger.info(f"   ⚖️ Balanced order book")
            else:
                logger.warning(f"⚠️ {symbol.upper()}: No imbalance data yet")
        except Exception as e:
            logger.error(f"❌ {symbol.upper()}: Imbalance check failed - {e}")
    
    # ===========================================
    # TEST 4: Check Whale Activity
    # ===========================================
    logger.info("\n📊 TEST 4: Check Whale Activity (Last 60s)")
    logger.info("-" * 70)
    
    for symbol in test_symbols:
        try:
            whales = order_flow_service.get_recent_whales(symbol.upper(), min_size="medium")
            if whales:
                logger.info(f"🐋 {symbol.upper()}: {len(whales)} whale order(s) detected")
                
                # Show top 3
                for i, whale in enumerate(whales[:3], 1):
                    side_emoji = "🟢" if whale["side"] == "BUY" else "🔴"
                    logger.info(
                        f"   {i}. {side_emoji} {whale['side']} "
                        f"${whale['usd_value']:,.0f} @ {whale['price']:.2f} "
                        f"({whale['whale_size']} - {whale['age_seconds']:.0f}s ago)"
                    )
            else:
                logger.info(f"⚪ {symbol.upper()}: No whale orders detected")
        except Exception as e:
            logger.error(f"❌ {symbol.upper()}: Whale detection failed - {e}")
    
    # ===========================================
    # TEST 5: Check Liquidity Voids
    # ===========================================
    logger.info("\n📊 TEST 5: Check Liquidity Voids")
    logger.info("-" * 70)
    
    for symbol in test_symbols:
        try:
            voids = order_flow_service.get_liquidity_voids(symbol.upper())
            if voids:
                logger.warning(f"⚠️ {symbol.upper()}: {len(voids)} liquidity void(s) detected")
                
                # Show voids
                for i, void in enumerate(voids, 1):
                    logger.warning(
                        f"   {i}. {void['side'].upper()} void: "
                        f"{void['price_from']:.2f} → {void['price_to']:.2f} "
                        f"(severity: {void['severity']:.1f}x)"
                    )
            else:
                logger.info(f"✅ {symbol.upper()}: No liquidity voids (healthy order book)")
        except Exception as e:
            logger.error(f"❌ {symbol.upper()}: Void detection failed - {e}")
    
    # ===========================================
    # TEST 6: Check Buy/Sell Pressure
    # ===========================================
    logger.info("\n📊 TEST 6: Check Buy/Sell Pressure (Last 30s)")
    logger.info("-" * 70)
    
    for symbol in test_symbols:
        try:
            pressure = order_flow_service.get_buy_sell_pressure(symbol.upper(), window=30)
            if pressure:
                pressure_emoji = "🟢" if pressure["dominant_side"] == "BUY" else "🔴" if pressure["dominant_side"] == "SELL" else "⚪"
                logger.info(
                    f"{pressure_emoji} {symbol.upper()}: {pressure['dominant_side']} "
                    f"(ratio: {pressure['pressure']:.2f})"
                )
                logger.info(f"   Buy Volume: {pressure['buy_volume']:.4f} (${pressure['buy_value']:,.0f})")
                logger.info(f"   Sell Volume: {pressure['sell_volume']:.4f} (${pressure['sell_value']:,.0f})")
                logger.info(f"   Net: {pressure['net_volume']:+.4f}")
            else:
                logger.warning(f"⚠️ {symbol.upper()}: No pressure data yet")
        except Exception as e:
            logger.error(f"❌ {symbol.upper()}: Pressure check failed - {e}")
    
    # ===========================================
    # TEST 7: Get Comprehensive Order Flow Signal
    # ===========================================
    logger.info("\n📊 TEST 7: Comprehensive Order Flow Signal")
    logger.info("-" * 70)
    
    for symbol in test_symbols:
        try:
            signal = order_flow_service.get_order_flow_signal(symbol.upper())
            if signal:
                signal_emoji = "🟢" if signal["signal"] == "BULLISH" else "🔴" if signal["signal"] == "BEARISH" else "⚪"
                logger.info(f"\n{signal_emoji} {symbol.upper()}: {signal['signal']} ({signal['confidence']:.0f}% confidence)")
                
                # Order book
                if signal.get("order_book"):
                    ob = signal["order_book"]
                    logger.info(f"   📊 Order Book Imbalance: {ob['imbalance']:.2f}")
                    logger.info(f"   💰 Total Liquidity: ${ob['total_liquidity']:,.0f}")
                
                # Whale activity
                if signal.get("whale_activity"):
                    wa = signal["whale_activity"]
                    logger.info(f"   🐋 Whales: {wa['total_whales']} (Buy: {wa['buy_whales']}, Sell: {wa['sell_whales']})")
                
                # Pressure
                if signal.get("pressure"):
                    pr = signal["pressure"]
                    logger.info(f"   💪 Pressure: {pr['dominant_side']} (ratio: {pr['pressure_ratio']:.2f})")
                
                # Warnings
                if signal.get("warnings"):
                    logger.warning(f"   ⚠️ Warnings:")
                    for warning in signal["warnings"]:
                        logger.warning(f"      • {warning}")
            else:
                logger.warning(f"⚠️ {symbol.upper()}: No comprehensive signal yet")
        except Exception as e:
            logger.error(f"❌ {symbol.upper()}: Signal generation failed - {e}")
    
    # ===========================================
    # TEST 8: Print Formatted Summary
    # ===========================================
    logger.info("\n📊 TEST 8: Formatted Order Flow Summary")
    logger.info("-" * 70)
    
    for symbol in test_symbols:
        try:
            summary = order_flow_service.get_signal_summary(symbol.upper())
            logger.info(f"\n{summary}")
        except Exception as e:
            logger.error(f"❌ {symbol.upper()}: Summary generation failed - {e}")
    
    # ===========================================
    # TEST 9: Integration with Binance Service
    # ===========================================
    logger.info("\n📊 TEST 9: Integration with Binance Service")
    logger.info("-" * 70)
    
    try:
        # Start Binance service
        binance_service = BinanceService(interval="1m")
        await binance_service.start(test_symbols, background=True)
        logger.info("✅ Binance service started")
        
        # Wait for data
        await asyncio.sleep(5)
        
        # Create enricher with order flow
        enricher = BinanceEnrichment(binance_service, mt5_service=None, order_flow_service=order_flow_service)
        logger.info("✅ BinanceEnrichment with order flow created")
        
        # Get enrichment summary
        for symbol in test_symbols:
            summary = enricher.get_enrichment_summary(symbol.upper())
            logger.info(f"\n{summary}")
        
        # Stop binance service
        binance_service.stop()
        
    except Exception as e:
        logger.error(f"❌ Binance integration test failed: {e}")
    
    # ===========================================
    # TEST 10: Status Check
    # ===========================================
    logger.info("\n📊 TEST 10: Service Status")
    logger.info("-" * 70)
    
    try:
        order_flow_service.print_status()
    except Exception as e:
        logger.error(f"❌ Status check failed: {e}")
    
    # ===========================================
    # CLEANUP
    # ===========================================
    logger.info("\n🛑 Stopping order flow service...")
    order_flow_service.stop()
    
    logger.info("\n" + "=" * 70)
    logger.info("✅ ALL TESTS COMPLETED")
    logger.info("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(test_order_flow())
    except KeyboardInterrupt:
        logger.info("\n⚠️ Test interrupted by user")
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)

