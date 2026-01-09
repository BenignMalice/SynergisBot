"""
Order Flow Service

High-level service for order book depth and whale detection.
Integrates depth streams, aggtrades, and order flow analysis.
"""

import asyncio
import logging
from typing import Dict, List, Optional
from infra.binance_depth_stream import BinanceDepthStream, OrderBookAnalyzer
from infra.binance_aggtrades_stream import BinanceAggTradesStream, WhaleDetector
from infra.order_flow_analyzer import OrderFlowAnalyzer

logger = logging.getLogger(__name__)


class OrderFlowService:
    """
    Unified service for order flow analysis.
    
    Combines:
    - Order book depth streaming
    - Aggregate trades streaming  
    - Whale detection
    - Order flow signal generation
    """
    
    def __init__(self):
        """Initialize order flow service"""
        # Create analyzer (contains depth + whale analyzers)
        self.analyzer = OrderFlowAnalyzer()
        
        # Create streams with callbacks
        self.depth_stream = BinanceDepthStream(callback=self._on_depth_update)
        self.trades_stream = BinanceAggTradesStream(callback=self._on_trade_update)
        
        # Track running state
        self.running = False
        self.symbols = []
        
        logger.info("📊 OrderFlowService initialized")
    
    async def _on_depth_update(self, symbol: str, depth: Dict):
        """Callback for depth updates"""
        self.analyzer.update_depth(symbol, depth)
    
    async def _on_trade_update(self, symbol: str, trade: Dict):
        """Callback for trade updates"""
        self.analyzer.update_trade(symbol, trade)
    
    async def start(self, symbols: List[str], background: bool = True):
        """
        Start order flow streams for symbols.
        
        Args:
            symbols: List of symbols to monitor (e.g., ["btcusdt", "xauusd"])
            background: Run in background (non-blocking)
        """
        if self.running:
            logger.warning("⚠️ Order flow service already running - stopping existing streams first")
            # Stop existing streams before restarting
            await self.stop_async()
            # Give tasks time to complete
            await asyncio.sleep(1.0)
        
        self.running = True
        self.symbols = symbols
        
        logger.info(f"🚀 Starting order flow service for {len(symbols)} symbols")
        logger.info(f"   Symbols: {', '.join([s.upper() for s in symbols])}")
        
        # Start depth stream
        await self.depth_stream.start(symbols, background=True)
        
        # Start trades stream
        await self.trades_stream.start(symbols, background=True)
        
        logger.info("✅ Order flow service started")
        logger.info("   📊 Depth stream: Active (20 levels @ 100ms)")
        logger.info("   🐋 AggTrades stream: Active (whale detection enabled)")
    
    async def stop_async(self):
        """Stop all order flow streams and wait for tasks to complete"""
        logger.info("🛑 Stopping order flow service...")
        
        self.running = False
        
        # Stop streams and wait for them to complete
        await self.depth_stream.stop_async()
        await self.trades_stream.stop_async()
        
        logger.info("✅ Order flow service stopped")

    def stop(self):
        """Stop all order flow streams (sync wrapper)."""
        self.stop_sync()
    
    def stop_sync(self):
        """Synchronous stop (for backward compatibility)"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, create a task
                asyncio.create_task(self.stop_async())
            else:
                # If loop is not running, run it
                loop.run_until_complete(self.stop_async())
        except RuntimeError:
            # No event loop, just stop synchronously
            self.running = False
            self.depth_stream.stop_sync()
            self.trades_stream.stop_sync()
            logger.info("✅ Order flow service stopped (no event loop)")
    
    def get_order_flow_signal(self, symbol: str) -> Optional[Dict]:
        """
        Get order flow signal for a symbol.
        
        Returns:
            Signal dict or None if no data available
        """
        return self.analyzer.get_order_flow_signal(symbol)
    
    def get_signal_summary(self, symbol: str) -> str:
        """
        Get formatted order flow summary.
        
        Returns:
            Human-readable summary string
        """
        return self.analyzer.format_signal_summary(symbol)
    
    def get_order_book_imbalance(self, symbol: str) -> Optional[float]:
        """Get current order book imbalance ratio"""
        return self.analyzer.depth_analyzer.calculate_imbalance(symbol)
    
    def get_recent_whales(self, symbol: str, min_size: str = "medium") -> List[Dict]:
        """Get recent whale orders"""
        return self.analyzer.whale_detector.get_recent_whales(symbol, min_size)
    
    def get_liquidity_voids(self, symbol: str) -> List[Dict]:
        """Get detected liquidity voids"""
        return self.analyzer.depth_analyzer.detect_liquidity_voids(symbol)
    
    def get_buy_sell_pressure(self, symbol: str, window: int = 30) -> Optional[Dict]:
        """Get buy/sell pressure for time window"""
        return self.analyzer.whale_detector.get_pressure(symbol, window)
    
    def print_status(self):
        """Print order flow service status"""
        if not self.running:
            logger.info("⚠️ Order flow service not running")
            return
        
        logger.info("=" * 70)
        logger.info("📊 ORDER FLOW SERVICE STATUS")
        logger.info("=" * 70)
        
        for symbol in self.symbols:
            try:
                signal = self.get_order_flow_signal(symbol)
                
                if not signal or not signal.get("signal"):
                    logger.info(f"⚠️ {symbol.upper()}: No data yet")
                    continue
                
                # Get metrics safely
                imbalance = signal.get("order_book", {}).get("imbalance", 0) if signal.get("order_book") else None
                whale_count = signal.get("whale_activity", {}).get("total_whales", 0) if signal.get("whale_activity") else 0
                pressure = signal.get("pressure", {}).get("dominant_side", "N/A") if signal.get("pressure") else "N/A"
                voids = len(signal.get("liquidity_voids", []))
                
                # Status emoji
                if signal["signal"] == "BULLISH":
                    emoji = "🟢"
                elif signal["signal"] == "BEARISH":
                    emoji = "🔴"
                else:
                    emoji = "⚪"
                
                logger.info(f"{emoji} {symbol.upper()}")
                logger.info(f"   Signal: {signal['signal']} ({signal.get('confidence', 0):.0f}%)")
                if imbalance is not None:
                    logger.info(f"   Imbalance: {imbalance:.2f}")
                logger.info(f"   Whales (60s): {whale_count}")
                logger.info(f"   Pressure: {pressure}")
                logger.info(f"   Liquidity Voids: {voids}")
            except Exception as e:
                logger.warning(f"⚠️ {symbol.upper()}: Status check error - {e}")
        
        logger.info("=" * 70)

