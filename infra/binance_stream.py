"""
Binance WebSocket Stream Client
Streams real-time price data from Binance (no account/API key required).

Supports:
- Kline/Candlestick data (1m, 5m, 15m, 1h, 4h)
- Order book depth (optional, Phase 2)
- Aggregated trades (optional, Phase 2)

Usage:
    stream = BinanceStream(["btcusdt", "ethusdt"], callback=on_tick)
    await stream.start_all()
"""

import asyncio
import json
import websockets
import logging
from typing import Callable, Dict, List, Optional
from datetime import datetime
import time
import sys
import codecs

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except:
        pass

logger = logging.getLogger(__name__)


class BinanceStream:
    """
    Real-time Binance WebSocket stream for kline data.
    Updates every ~1 second with latest OHLCV.
    
    No authentication required - public data stream.
    """
    
    def __init__(
        self,
        symbols: List[str],
        callback: Callable,
        interval: str = "1m",
        reconnect_delay: int = 5
    ):
        """
        Args:
            symbols: List of symbol names (e.g., ["btcusdt", "ethusdt"])
            callback: Async function to call with each tick
            interval: Kline interval (1m, 5m, 15m, 1h, 4h)
            reconnect_delay: Seconds to wait before reconnecting on error
        """
        self.symbols = [s.lower() for s in symbols]
        self.callback = callback
        self.interval = interval
        self.reconnect_delay = reconnect_delay
        self.connections = {}
        self.running = False
        
    async def connect(self, symbol: str):
        """
        Connect to Binance WebSocket for a single symbol.
        Automatically reconnects on disconnect.
        """
        uri = f"wss://stream.binance.com:9443/ws/{symbol}@kline_{self.interval}"
        retry_count = 0
        
        while self.running:
            try:
                logger.info(f"📡 Connecting to Binance stream: {symbol}")
                logger.info(f"   URI: {uri}")
                logger.info("   Starting connection with 10s timeout...")

                start_time = time.time()
                ws = await asyncio.wait_for(
                    websockets.connect(uri),
                    timeout=10.0
                )

                elapsed = time.time() - start_time

                async with ws:
                    logger.info(f"✅ Connected to {symbol} stream (in {elapsed:.2f}s)")
                    self.connections[symbol] = ws
                    retry_count = 0
                    
                    async for msg in ws:
                        if not self.running:
                            break
                            
                        try:
                            data = json.loads(msg)
                            if 'k' in data:
                                tick = self._parse_kline(symbol, data['k'])
                                await self.callback(tick)
                        except Exception as e:
                            logger.error(f"❌ Error parsing message for {symbol}: {e}")
                            
            except asyncio.TimeoutError:
                retry_count += 1
                logger.error(f"❌ Connection timeout for {symbol} after 10s (attempt {retry_count})")
            except websockets.exceptions.ConnectionClosed:
                retry_count += 1
                logger.warning(f"⚠️ Connection closed for {symbol}, reconnecting... (attempt {retry_count})")
            except websockets.exceptions.InvalidURI as e:
                logger.error(f"❌ Invalid URI for {symbol}: {e}")
                break
            except Exception as e:
                retry_count += 1
                logger.error(f"❌ Error in {symbol} stream: {e}")
            finally:
                if symbol in self.connections:
                    del self.connections[symbol]
                    
            if self.running:
                delay = min(self.reconnect_delay * (2 ** max(retry_count - 1, 0)), 60)
                logger.info(f"⏳ Reconnecting {symbol} in {delay}s...")
                await asyncio.sleep(delay)
                
    def _parse_kline(self, symbol: str, kline: dict) -> dict:
        """
        Parse raw Binance kline data into clean tick format.
        
        Returns:
            {
                "symbol": "BTCUSDT",
                "timestamp": 1234567890,
                "price": 112150.5,
                "open": 112100.0,
                "high": 112200.0,
                "low": 112050.0,
                "close": 112150.5,
                "volume": 45.67,
                "is_closed": False
            }
        """
        return {
            "symbol": symbol.upper(),
            "timestamp": int(kline['t']) // 1000,  # Convert to seconds
            "price": float(kline['c']),  # Current close
            "open": float(kline['o']),
            "high": float(kline['h']),
            "low": float(kline['l']),
            "close": float(kline['c']),
            "volume": float(kline['v']),
            "is_closed": kline['x'],  # True when candle closes
            "interval": self.interval
        }
        
    async def start_all(self):
        """
        Start streaming for all symbols.
        Runs until stop() is called.
        """
        self.running = True
        logger.info(f"🚀 Starting Binance streams for {len(self.symbols)} symbols")
        
        tasks = [self.connect(symbol) for symbol in self.symbols]
        await asyncio.gather(*tasks, return_exceptions=True)
        
    def stop(self):
        """
        Stop all streams gracefully.
        """
        logger.info("🛑 Stopping Binance streams...")
        self.running = False
        
        for symbol, ws in self.connections.items():
            try:
                asyncio.create_task(ws.close())
            except:
                pass
                
        self.connections.clear()
        logger.info("✅ All Binance streams stopped")
        
    def is_connected(self, symbol: str = None) -> bool:
        """
        Check if stream is connected.
        
        Args:
            symbol: Check specific symbol, or None to check if any stream is connected
        """
        if symbol:
            return symbol.lower() in self.connections
        return len(self.connections) > 0


class BinanceStreamEnhanced(BinanceStream):
    """
    Enhanced Binance stream with order book depth and aggregated trades.
    
    Usage for Phase 2+ (optional):
        stream = BinanceStreamEnhanced(
            ["btcusdt"],
            callback=on_tick,
            enable_depth=True,
            enable_aggtrades=True
        )
    """
    
    def __init__(
        self,
        symbols: List[str],
        callback: Callable,
        interval: str = "1m",
        enable_depth: bool = False,
        enable_aggtrades: bool = False,
        **kwargs
    ):
        super().__init__(symbols, callback, interval, **kwargs)
        self.enable_depth = enable_depth
        self.enable_aggtrades = enable_aggtrades
        
    async def connect_multi_stream(self, symbol: str):
        """
        Connect to multiple streams for a symbol (kline + depth + aggtrades).
        Phase 2 feature - not yet implemented.
        """
        # TODO: Implement combined stream in Phase 2
        # Combined stream format: wss://stream.binance.com:9443/stream?streams=btcusdt@kline_1m/btcusdt@depth20/btcusdt@aggTrade
        await self.connect(symbol)


# Example usage
async def example_usage():
    """
    Example of how to use BinanceStream.
    """
    
    async def on_tick(tick: dict):
        """Callback function for each price update"""
        print(f"[{tick['symbol']}] Price: ${tick['price']:,.2f} | Volume: {tick['volume']:.2f}")
        
    # Create stream for BTC and ETH
    stream = BinanceStream(
        symbols=["btcusdt", "ethusdt"],
        callback=on_tick,
        interval="1m"
    )
    
    # Start streaming (runs until Ctrl+C)
    try:
        await stream.start_all()
    except KeyboardInterrupt:
        stream.stop()
        print("\n👋 Stream stopped")


if __name__ == "__main__":
    # Run example
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🧪 Testing Binance Stream")
    print("Press Ctrl+C to stop\n")
    
    asyncio.run(example_usage())



