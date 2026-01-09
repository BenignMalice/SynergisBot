#!/usr/bin/env python3
"""
Test Binance Disconnect Fix
============================
This script tests the fix for Binance disconnects when ChatGPT is used.
"""

import asyncio
import logging
import time
from typing import List
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from infra.mt5_service import MT5Service
from infra.mt5_proxy_service import MT5ProxyService, initialize_mt5_proxy, start_mt5_proxy, stop_mt5_proxy
from infra.binance_service_fixed import BinanceServiceFixed, PeriodicOffsetCalibrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BinanceFixTester:
    """Test the Binance disconnect fix"""
    
    def __init__(self):
        self.mt5_service = None
        self.mt5_proxy = None
        self.binance_service = None
        self.calibrator = None
        self.test_symbols = ["btcusdt", "ethusdt", "xauusd"]
        
    async def setup(self):
        """Setup test environment"""
        logger.info("Setting up test environment...")
        
        # Initialize MT5 service
        try:
            self.mt5_service = MT5Service()
            if self.mt5_service.connect():
                logger.info("MT5 service connected")
            else:
                logger.warning("MT5 service connection failed - running without MT5")
                self.mt5_service = None
        except Exception as e:
            logger.warning(f"MT5 service initialization failed: {e}")
            self.mt5_service = None
        
        # Initialize MT5 proxy
        if self.mt5_service:
            self.mt5_proxy = initialize_mt5_proxy(self.mt5_service, update_interval=0.5)
            await start_mt5_proxy()
            logger.info("MT5 proxy started")
        
        # Initialize fixed Binance service
        self.binance_service = BinanceServiceFixed(interval="1m")
        logger.info("Fixed Binance service initialized")
        
        # Initialize periodic calibrator
        if self.mt5_proxy:
            self.calibrator = PeriodicOffsetCalibrator(
                self.binance_service, 
                self.mt5_proxy, 
                interval=1.0
            )
            await self.calibrator.start()
            logger.info("Periodic calibrator started")
    
    async def test_binance_streaming(self):
        """Test Binance streaming without MT5 calls in callback"""
        logger.info("Testing Binance streaming...")
        
        # Start Binance streaming
        await self.binance_service.start(self.test_symbols, background=True)
        
        # Monitor for 30 seconds
        logger.info("Monitoring Binance streams for 30 seconds...")
        start_time = time.time()
        
        while time.time() - start_time < 30:
            await asyncio.sleep(5)
            
            # Get performance stats
            stats = self.binance_service.get_performance_stats()
            logger.info(f"Tick count: {stats['tick_count']}, Max duration: {stats['max_tick_duration']*1000:.2f}ms")
            
            # Get price summary
            prices = self.binance_service.get_price_summary()
            for symbol, data in prices.items():
                logger.info(f"{symbol}: {data['price']} (age: {data['age_seconds']:.1f}s)")
        
        logger.info("Binance streaming test completed")
    
    async def test_chatgpt_simulation(self):
        """Simulate ChatGPT requests while Binance is streaming"""
        logger.info("Testing ChatGPT simulation...")
        
        # Simulate multiple ChatGPT requests
        for i in range(5):
            logger.info(f"Simulating ChatGPT request {i+1}/5...")
            
            # Simulate MT5 calls that ChatGPT would make
            if self.mt5_proxy:
                try:
                    # Simulate account info request
                    account_info = await self.mt5_proxy.get_account_info_async()
                    if account_info:
                        logger.info(f"Account: Balance={account_info[0]}, Equity={account_info[1]}")
                    
                    # Simulate positions request
                    positions = await self.mt5_proxy.get_positions_async()
                    logger.info(f"Positions: {len(positions)}")
                    
                    # Simulate quote requests
                    for symbol in self.test_symbols:
                        mt5_symbol = symbol.replace("usdt", "usdc").upper()
                        quote = await self.mt5_proxy.get_quote_async(mt5_symbol)
                        if quote:
                            logger.info(f"{mt5_symbol}: {quote.bid}/{quote.ask}")
                
                except Exception as e:
                    logger.error(f"MT5 proxy call failed: {e}")
            
            # Wait between requests
            await asyncio.sleep(2)
        
        logger.info("ChatGPT simulation completed")
    
    async def test_performance(self):
        """Test performance metrics"""
        logger.info("Testing performance metrics...")
        
        # Get MT5 proxy stats
        if self.mt5_proxy:
            cache_stats = self.mt5_proxy.get_cache_stats()
            logger.info(f"MT5 Proxy stats: {cache_stats}")
        
        # Get Binance service stats
        binance_stats = self.binance_service.get_performance_stats()
        logger.info(f"Binance service stats: {binance_stats}")
        
        # Check for slow ticks
        if binance_stats['max_tick_duration'] > 0.001:  # 1ms
            logger.warning(f"Slow ticks detected: {binance_stats['max_tick_duration']*1000:.2f}ms")
        else:
            logger.info("Tick processing is fast (good)")
    
    async def cleanup(self):
        """Cleanup test environment"""
        logger.info("Cleaning up test environment...")
        
        if self.calibrator:
            await self.calibrator.stop()
        
        if self.binance_service:
            self.binance_service.stop()
        
        if self.mt5_proxy:
            await stop_mt5_proxy()
        
        logger.info("Cleanup completed")

async def main():
    """Main test function"""
    logger.info("=" * 70)
    logger.info("BINANCE DISCONNECT FIX TEST")
    logger.info("=" * 70)
    
    tester = BinanceFixTester()
    
    try:
        # Setup
        await tester.setup()
        
        # Test 1: Binance streaming
        await tester.test_binance_streaming()
        
        # Test 2: ChatGPT simulation
        await tester.test_chatgpt_simulation()
        
        # Test 3: Performance metrics
        await tester.test_performance()
        
        logger.info("=" * 70)
        logger.info("ALL TESTS COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)
        logger.info("Key improvements:")
        logger.info("  - No MT5 calls in Binance tick callback")
        logger.info("  - Thread-safe MT5 proxy service")
        logger.info("  - Periodic offset calibration")
        logger.info("  - Lightweight tick processing")
        logger.info("  - No more cross-thread MT5 access")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())