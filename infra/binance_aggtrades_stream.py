"""
Binance Aggregate Trades Stream

Streams large aggregated trades in real-time.
Used for whale detection and institutional order flow analysis.
"""

import asyncio
import json
import websockets
import logging
from typing import Dict, Callable, Optional
from collections import deque
import time

logger = logging.getLogger(__name__)


class BinanceAggTradesStream:
    """
    Real-time aggregate trades streaming from Binance.
    
    AggTrades combine multiple trades into single records,
    making it easier to spot large institutional orders.
    
    Use cases:
    - Whale order detection
    - Institutional positioning
    - Large buy/sell pressure
    - Market impact analysis
    """
    
    def __init__(self, callback: Callable):
        """
        Initialize aggtrades stream.
        
        Args:
            callback: Function to call with trade updates
                     callback(symbol, trade_data)
        """
        self.callback = callback
        self.connections = {}
        self.running = False
        self.tasks = []
        
        logger.info("🐋 BinanceAggTradesStream initialized")
    
    async def connect(self, symbol: str):
        """Connect to aggtrades stream for a single symbol"""
        uri = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@aggTrade"
        
        logger.info(f"🔌 Attempting to connect to {symbol.upper()} aggTrades stream...")
        logger.info(f"   URI: {uri}")
        
        # Check event loop status
        try:
            loop = asyncio.get_event_loop()
            logger.info(f"   Event loop running: {loop.is_running()}")
            logger.info(f"   Current task: {asyncio.current_task()}")
        except Exception as e:
            logger.warning(f"   Could not check event loop: {e}")
        
        retry_count = 0
        max_retries = 3
        
        while self.running and retry_count < max_retries:
            try:
                logger.info(f"   Connecting (attempt {retry_count + 1}/{max_retries})...")
                logger.info(f"   Starting connection with 10s timeout...")
                # Add timeout to prevent hanging
                start_time = time.time()
                try:
                    # Use wait_for to add timeout to connection
                    ws = await asyncio.wait_for(
                        websockets.connect(uri),
                        timeout=10.0
                    )
                    elapsed = time.time() - start_time
                    logger.info(f"   Connection established in {elapsed:.2f}s")
                    async with ws:
                        logger.info(f"🐋 Connected to {symbol.upper()} aggTrades stream")
                        retry_count = 0
                        
                        async for message in ws:
                            if not self.running:
                                break
                            
                            try:
                                data = json.loads(message)
                                
                                # Parse trade data
                                trade = {
                                    "symbol": symbol.upper(),
                                    "timestamp": time.time(),
                                    "trade_id": data.get("a"),
                                    "price": float(data.get("p", 0)),
                                    "quantity": float(data.get("q", 0)),
                                    "buyer_maker": data.get("m", False),  # True if buyer is maker
                                    "trade_time": data.get("T"),
                                    "event_time": data.get("E")
                                }
                                
                                # Calculate USD value
                                trade["usd_value"] = trade["price"] * trade["quantity"]
                                
                                # Determine side (buy or sell from taker perspective)
                                trade["side"] = "SELL" if trade["buyer_maker"] else "BUY"
                                
                                # Log first few trades for debugging
                                if not hasattr(self, '_trade_count'):
                                    self._trade_count = {}
                                if symbol not in self._trade_count:
                                    self._trade_count[symbol] = 0
                                
                                self._trade_count[symbol] += 1
                                if self._trade_count[symbol] <= 3:
                                    logger.debug(f"   📊 Trade #{self._trade_count[symbol]}: {trade['side']} {trade['quantity']:.6f} @ ${trade['price']:,.2f} (${trade['usd_value']:,.2f})")
                                
                                # Call callback with parsed trade
                                await self.callback(symbol.upper(), trade)
                                
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse trade message for {symbol}: {e}")
                            except Exception as e:
                                logger.error(f"Error processing trade for {symbol}: {e}")
                            
                except asyncio.TimeoutError as e:
                    elapsed = time.time() - start_time
                    logger.error(f"❌ Connection timeout for {symbol.upper()} after {elapsed:.2f}s")
                    logger.error(f"   TimeoutError details: {e}")
                    retry_count += 1
                    if retry_count < max_retries:
                        logger.info(f"   Retrying in {2 ** retry_count}s...")
                        await asyncio.sleep(2 ** retry_count)
                    continue
                except Exception as inner_e:
                    elapsed = time.time() - start_time
                    logger.error(f"❌ Inner connection error for {symbol.upper()} after {elapsed:.2f}s: {inner_e}", exc_info=True)
                    retry_count += 1
                    if retry_count < max_retries:
                        await asyncio.sleep(2 ** retry_count)
                    continue
            except websockets.exceptions.ConnectionClosed as e:
                if self.running:
                    retry_count += 1
                    logger.warning(f"⚠️ {symbol.upper()} aggTrades connection closed: {e}, retrying ({retry_count}/{max_retries})...")
                    await asyncio.sleep(2 ** retry_count)
            except websockets.exceptions.InvalidURI as e:
                logger.error(f"❌ {symbol.upper()} aggTrades invalid URI: {e}")
                break  # Don't retry on invalid URI
            except Exception as e:
                if self.running:
                    retry_count += 1
                    logger.error(f"❌ {symbol.upper()} aggTrades error: {e}", exc_info=True)
                    logger.error(f"   Retrying ({retry_count}/{max_retries})...")
                    await asyncio.sleep(2 ** retry_count)
        
        if retry_count >= max_retries:
            logger.error(f"❌ {symbol.upper()} aggTrades stream failed after {max_retries} retries")
    
    async def start(self, symbols: list, background: bool = True):
        """
        Start aggTrades streams for multiple symbols.
        
        Args:
            symbols: List of symbols to stream (e.g., ["btcusdt", "ethusdt"])
            background: If True, runs in background
        """
        self.running = True
        
        logger.info(f"🚀 Starting aggTrades streams for {len(symbols)} symbols")
        
        # Check event loop before creating tasks
        try:
            loop = asyncio.get_event_loop()
            logger.info(f"   Event loop running: {loop.is_running()}")
        except Exception as e:
            logger.warning(f"   Could not check event loop: {e}")
        
        def task_done_callback(task):
            """Log task completion/exception"""
            if task.done():
                # Check if task was cancelled first (calling exception() on cancelled task raises CancelledError)
                if task.cancelled():
                    logger.debug(f"aggTrades stream task cancelled (normal during shutdown)")
                    return
                
                try:
                    exc = task.exception()
                    if exc:
                        logger.error(f"❌ aggTrades stream task failed: {exc}", exc_info=exc)
                    else:
                        logger.info(f"✅ aggTrades stream task completed normally")
                except asyncio.CancelledError:
                    # Task was cancelled - this is normal during shutdown
                    logger.debug(f"aggTrades stream task cancelled (normal during shutdown)")
                except Exception as e:
                    logger.warning(f"Error checking task exception: {e}")
        
        self.tasks = []
        for sym in symbols:
            logger.info(f"   Creating task for {sym.upper()}...")
            task = asyncio.create_task(self.connect(sym))
            task.add_done_callback(task_done_callback)
            self.tasks.append(task)
            logger.info(f"   Task created: {task}, done={task.done()}, cancelled={task.cancelled()}")
        
        if not background:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        else:
            logger.info(f"✅ AggTrades streams running in background")
            logger.info(f"   Total tasks: {len(self.tasks)}")
            # Log task status after a short delay
            async def log_task_status():
                await asyncio.sleep(1.0)
                for i, task in enumerate(self.tasks):
                    # Safely get exception - check cancelled first
                    exc_info = None
                    if task.done() and not task.cancelled():
                        try:
                            exc_info = task.exception()
                        except (asyncio.CancelledError, Exception):
                            exc_info = "N/A (cancelled or error checking)"
                    logger.info(f"   Task {i+1} status: done={task.done()}, cancelled={task.cancelled()}, exception={exc_info}")
            asyncio.create_task(log_task_status())
    
    async def stop_async(self):
        """Stop all aggTrades streams and wait for tasks to complete"""
        logger.info("🛑 Stopping aggTrades streams...")
        self.running = False
        
        # Wait for tasks to complete or timeout
        for i, task in enumerate(self.tasks):
            if not task.done():
                logger.info(f"   Cancelling task {i+1}/{len(self.tasks)}...")
                task.cancel()
                try:
                    # Wait for task to complete cancellation (with timeout)
                    await asyncio.wait_for(task, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"   Task {i+1} did not complete within 5s timeout")
                except asyncio.CancelledError:
                    logger.debug(f"   Task {i+1} cancelled successfully")
                except Exception as e:
                    logger.warning(f"   Task {i+1} exception during cleanup: {e}")
        
        logger.info("✅ AggTrades streams stopped")

    def stop(self):
        """Stop all aggTrades streams (sync wrapper)."""
        self.stop_sync()

    def stop_sync(self):
        """Synchronous stop (backward compatible)."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.stop_async())
            else:
                loop.run_until_complete(self.stop_async())
        except RuntimeError:
            # No event loop, just cancel tasks
            self.running = False
            for task in self.tasks:
                if not task.done():
                    task.cancel()
            logger.info("✅ AggTrades streams stopped (no event loop)")


class WhaleDetector:
    """
    Detect large "whale" orders from aggregate trades.
    
    Features:
    - Large order detection (>$100k, >$500k, >$1M)
    - Buy/sell pressure tracking
    - Institutional positioning
    - Volume spike detection
    """
    
    def __init__(self, history_window: int = 60):
        """
        Initialize whale detector.
        
        Args:
            history_window: Seconds of trade history to keep
        """
        self.trade_history = {}  # symbol -> deque of trades
        self.history_window = history_window
        
        # Whale thresholds (USD value)
        self.thresholds = {
            "small": 50000,    # $50k
            "medium": 100000,  # $100k
            "large": 500000,   # $500k
            "whale": 1000000   # $1M
        }
        
        logger.info(f"🐋 WhaleDetector initialized (window={history_window}s)")
    
    def update(self, symbol: str, trade: Dict):
        """Add new trade to history"""
        if symbol not in self.trade_history:
            self.trade_history[symbol] = deque()
        
        self.trade_history[symbol].append(trade)
        
        # Remove old trades outside window
        cutoff_time = time.time() - self.history_window
        while self.trade_history[symbol] and self.trade_history[symbol][0]["timestamp"] < cutoff_time:
            self.trade_history[symbol].popleft()
    
    def is_whale_order(self, trade: Dict) -> Optional[str]:
        """
        Check if trade is a whale order.
        
        Returns:
            Whale size category or None
        """
        usd_value = trade["usd_value"]
        
        if usd_value >= self.thresholds["whale"]:
            return "whale"
        elif usd_value >= self.thresholds["large"]:
            return "large"
        elif usd_value >= self.thresholds["medium"]:
            return "medium"
        elif usd_value >= self.thresholds["small"]:
            return "small"
        
        return None
    
    def get_recent_whales(self, symbol: str, min_size: str = "medium") -> list:
        """
        Get recent whale orders.
        
        Args:
            symbol: Trading symbol
            min_size: Minimum whale size ("small", "medium", "large", "whale")
        
        Returns:
            List of whale trades
        """
        if symbol not in self.trade_history:
            return []
        
        min_threshold = self.thresholds.get(min_size, self.thresholds["medium"])
        
        whales = []
        for trade in self.trade_history[symbol]:
            if trade["usd_value"] >= min_threshold:
                whale_size = self.is_whale_order(trade)
                whales.append({
                    **trade,
                    "whale_size": whale_size,
                    "age_seconds": time.time() - trade["timestamp"]
                })
        
        return whales
    
    def get_pressure(self, symbol: str, window: int = 30) -> Optional[Dict]:
        """
        Calculate buy/sell pressure from recent trades.
        
        Args:
            symbol: Trading symbol
            window: Time window in seconds
        
        Returns:
            {"buy_volume": X, "sell_volume": Y, "pressure": ratio, "net": net_volume}
        """
        if symbol not in self.trade_history:
            return None
        
        cutoff_time = time.time() - window
        
        buy_volume = 0
        sell_volume = 0
        buy_value = 0
        sell_value = 0
        
        for trade in self.trade_history[symbol]:
            if trade["timestamp"] >= cutoff_time:
                if trade["side"] == "BUY":
                    buy_volume += trade["quantity"]
                    buy_value += trade["usd_value"]
                else:
                    sell_volume += trade["quantity"]
                    sell_value += trade["usd_value"]
        
        total_volume = buy_volume + sell_volume
        if total_volume == 0:
            return None
        
        # Pressure ratio: >1 = bullish, <1 = bearish
        pressure = buy_volume / sell_volume if sell_volume > 0 else (999 if buy_volume > 0 else 1)
        net_volume = buy_volume - sell_volume
        
        return {
            "buy_volume": buy_volume,
            "sell_volume": sell_volume,
            "buy_value": buy_value,
            "sell_value": sell_value,
            "total_volume": total_volume,
            "pressure": pressure,
            "net_volume": net_volume,
            "window_seconds": window,
            "dominant_side": "BUY" if pressure > 1.2 else "SELL" if pressure < 0.8 else "NEUTRAL"
        }
    
    def get_volume_spike(self, symbol: str, current_window: int = 10, baseline_window: int = 60) -> Optional[float]:
        """
        Detect volume spikes.
        
        Compares recent volume to baseline average.
        
        Returns:
            Spike multiplier (e.g., 2.5 = 2.5x normal volume) or None
        """
        if symbol not in self.trade_history:
            return None
        
        now = time.time()
        current_cutoff = now - current_window
        baseline_cutoff = now - baseline_window
        
        current_volume = 0
        baseline_volume = 0
        
        for trade in self.trade_history[symbol]:
            if trade["timestamp"] >= current_cutoff:
                current_volume += trade["quantity"]
            if trade["timestamp"] >= baseline_cutoff:
                baseline_volume += trade["quantity"]
        
        # Calculate average baseline per window
        baseline_per_window = (baseline_volume / baseline_window) * current_window
        
        if baseline_per_window == 0:
            return None
        
        spike_multiplier = current_volume / baseline_per_window
        return spike_multiplier

