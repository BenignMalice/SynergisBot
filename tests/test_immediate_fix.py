#!/usr/bin/env python3
"""
Test Immediate Binance Fix
==========================
This script tests the immediate fix by simulating ChatGPT usage
while monitoring Binance connection stability.
"""

import asyncio
import logging
import time
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from infra.mt5_service import MT5Service
from infra.binance_service import BinanceService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ImmediateFixTester:
    """Test the immediate fix for Binance disconnects"""
    
    def __init__(self):
        self.mt5_service = None
        self.binance_service = None
        self.test_symbols = ["btcusdt", "ethusdt", "xauusd"]
        self.disconnect_count = 0
        self.start_time = None
        
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
        
        # Initialize Binance service (with fix applied)
        self.binance_service = BinanceService(interval="1m")
        if self.mt5_service:
            self.binance_service.set_mt5_service(self.mt5_service)
        
        logger.info("Test environment setup complete")
    
    async def test_binance_stability(self):
        """Test Binance streaming stability"""
        logger.info("Testing Binance streaming stability...")
        
        # Start Binance streaming
        await self.binance_service.start(self.test_symbols, background=True)
        
        # Monitor for 60 seconds
        logger.info("Monitoring Binance streams for 60 seconds...")
        self.start_time = time.time()
        
        while time.time() - self.start_time < 60:
            await asyncio.sleep(10)
            
            # Check if service is still running
            if not self.binance_service.running:
                self.disconnect_count += 1
                logger.warning(f"Binance service disconnected! Count: {self.disconnect_count}")
            
            # Log status
            elapsed = time.time() - self.start_time
            logger.info(f"Elapsed: {elapsed:.1f}s, Disconnects: {self.disconnect_count}")
        
        logger.info("Binance stability test completed")
    
    async def test_chatgpt_simulation(self):
        """Simulate ChatGPT requests while Binance is streaming"""
        logger.info("Testing ChatGPT simulation...")
        
        # Simulate multiple ChatGPT requests
        for i in range(10):
            logger.info(f"Simulating ChatGPT request {i+1}/10...")
            
            # Simulate MT5 calls that ChatGPT would make
            if self.mt5_service:
                try:
                    # Simulate account info request
                    account_info = self.mt5_service.account_bal_eq()
                    if account_info:
                        logger.info(f"Account: Balance={account_info[0]}, Equity={account_info[1]}")
                    
                    # Simulate positions request
                    positions = self.mt5_service.list_positions()
                    logger.info(f"Positions: {len(positions)}")
                    
                    # Simulate quote requests
                    for symbol in self.test_symbols:
                        mt5_symbol = symbol.replace("usdt", "usdc").upper()
                        try:
                            quote = self.mt5_service.get_quote(mt5_symbol)
                            if quote:
                                logger.info(f"{mt5_symbol}: {quote.bid}/{quote.ask}")
                        except:
                            pass  # Ignore quote errors
                
                except Exception as e:
                    logger.error(f"MT5 call failed: {e}")
            
            # Check for disconnects
            if not self.binance_service.running:
                self.disconnect_count += 1
                logger.warning(f"Disconnect detected during ChatGPT simulation! Count: {self.disconnect_count}")
            
            # Wait between requests
            await asyncio.sleep(2)
        
        logger.info("ChatGPT simulation completed")
    
    async def test_performance(self):
        """Test performance metrics"""
        logger.info("Testing performance metrics...")
        
        # Get Binance service stats
        if hasattr(self.binance_service, 'get_performance_stats'):
            stats = self.binance_service.get_performance_stats()
            logger.info(f"Binance service stats: {stats}")
        
        # Check for disconnects
        if self.disconnect_count > 0:
            logger.warning(f"Total disconnects: {self.disconnect_count}")
        else:
            logger.info("No disconnects detected - fix appears to be working!")
    
    async def cleanup(self):
        """Cleanup test environment"""
        logger.info("Cleaning up test environment...")
        
        if self.binance_service:
            self.binance_service.stop()
        
        logger.info("Cleanup completed")

async def main():
    """Main test function"""
    logger.info("=" * 70)
    logger.info("IMMEDIATE BINANCE FIX TEST")
    logger.info("=" * 70)
    
    tester = ImmediateFixTester()
    
    try:
        # Setup
        await tester.setup()
        
        # Test 1: Binance stability
        await tester.test_binance_stability()
        
        # Test 2: ChatGPT simulation
        await tester.test_chatgpt_simulation()
        
        # Test 3: Performance metrics
        await tester.test_performance()
        
        logger.info("=" * 70)
        if tester.disconnect_count == 0:
            logger.info("SUCCESS - NO DISCONNECTS DETECTED!")
            logger.info("The immediate fix appears to be working correctly.")
        else:
            logger.warning(f"WARNING - {tester.disconnect_count} DISCONNECTS DETECTED!")
            logger.warning("The fix may need further investigation.")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
