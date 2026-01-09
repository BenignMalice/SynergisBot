"""
Standalone Binance Feed Launcher
Starts Binance streaming service in background for testing or standalone use.

Usage:
    python start_binance_feed.py
    
    Or with custom symbols:
    python start_binance_feed.py btcusdt ethusdt xauusd
"""

import asyncio
import logging
import sys
import signal
import codecs

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from infra.binance_service import BinanceService
from infra.mt5_service import MT5Service

logger = logging.getLogger(__name__)

# Global service instance for graceful shutdown
service = None


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\n🛑 Shutdown signal received...")
    if service:
        service.stop()
    sys.exit(0)


async def main(symbols=None):
    """
    Main entry point for standalone Binance feed.
    
    Args:
        symbols: List of symbols to stream (default: btcusdt, ethusdt, xauusd)
    """
    global service
    
    # Default symbols
    if not symbols:
        symbols = ["btcusdt", "ethusdt", "xauusd"]
    
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║                  BINANCE STREAMING SERVICE                           ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print(f"📡 Streaming: {', '.join(s.upper() for s in symbols)}")
    print(f"⏱️  Interval: 1m candles")
    print(f"💾 Cache: Last 1000 ticks per symbol")
    print(f"\nPress Ctrl+C to stop\n")
    print("="*70 + "\n")
    
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Initialize MT5 service
    try:
        mt5_service = MT5Service()
        if mt5_service.connect():
            logger.info("✅ MT5 connected - will track price offsets")
        else:
            logger.warning("⚠️ MT5 connection failed - running without offset tracking")
            mt5_service = None
    except Exception as e:
        logger.warning(f"⚠️ MT5 initialization failed: {e}")
        mt5_service = None
    
    # Initialize Binance service
    service = BinanceService(interval="1m")
    if mt5_service:
        service.set_mt5_service(mt5_service)
    
    # Start streaming
    await service.start(symbols, background=False)  # Run in foreground (blocking)
    
    # Wait a moment for initial data
    await asyncio.sleep(3)
    
    # Print status every 30 seconds
    while True:
        await asyncio.sleep(30)
        service.print_status()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Parse command line arguments
    symbols = sys.argv[1:] if len(sys.argv) > 1 else None
    
    # Run
    try:
        asyncio.run(main(symbols))
    except KeyboardInterrupt:
        print("\n👋 Binance feed stopped")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

