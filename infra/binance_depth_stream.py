"""
Binance Order Book Depth Stream

Streams 20-level order book depth at 100ms intervals.
Used for liquidity analysis, support/resistance, and void detection.
"""

import asyncio
import json
import websockets
import logging
from typing import Dict, Callable, Optional
from collections import deque
import time

logger = logging.getLogger(__name__)


class BinanceDepthStream:
    """
    Real-time order book depth streaming from Binance.
    
    Provides 20 levels of bids and asks, updated every 100ms.
    Used for:
    - Liquidity void detection
    - Support/resistance identification
    - Order book pressure analysis
    - Institutional positioning
    """
    
    def __init__(self, callback: Callable):
        """
        Initialize depth stream.
        
        Args:
            callback: Function to call with depth updates
                     callback(symbol, depth_data)
        """
        self.callback = callback
        self.connections = {}
        self.running = False
        self.tasks = []
        
        logger.info("📊 BinanceDepthStream initialized")
    
    async def connect(self, symbol: str):
        """Connect to depth stream for a single symbol"""
        # Binance depth stream - 20 levels @ 100ms
        uri = f"wss://stream.binance.com:9443/ws/{symbol.lower()}@depth20@100ms"
        
        retry_count = 0
        max_retries = 3
        
        while self.running and retry_count < max_retries:
            try:
                async with websockets.connect(uri) as ws:
                    logger.info(f"📊 Connected to {symbol.upper()} depth stream")
                    retry_count = 0  # Reset on successful connection
                    
                    async for message in ws:
                        if not self.running:
                            break
                        
                        try:
                            data = json.loads(message)
                            
                            # Parse depth data
                            depth = {
                                "symbol": symbol.upper(),
                                "timestamp": time.time(),
                                "bids": [[float(price), float(qty)] for price, qty in data.get("bids", [])],
                                "asks": [[float(price), float(qty)] for price, qty in data.get("asks", [])],
                                "last_update_id": data.get("lastUpdateId")
                            }
                            
                            # Call callback with parsed depth
                            await self.callback(symbol.upper(), depth)
                            
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse depth message for {symbol}: {e}")
                        except Exception as e:
                            logger.error(f"Error processing depth for {symbol}: {e}")
                            
            except websockets.exceptions.ConnectionClosed:
                if self.running:
                    retry_count += 1
                    logger.warning(f"⚠️ {symbol.upper()} depth connection closed, retrying ({retry_count}/{max_retries})...")
                    await asyncio.sleep(2 ** retry_count)  # Exponential backoff
            except Exception as e:
                if self.running:
                    retry_count += 1
                    logger.error(f"❌ {symbol.upper()} depth error: {e}, retrying ({retry_count}/{max_retries})...")
                    await asyncio.sleep(2 ** retry_count)
        
        if retry_count >= max_retries:
            logger.error(f"❌ {symbol.upper()} depth stream failed after {max_retries} retries")
    
    async def start(self, symbols: list, background: bool = True):
        """
        Start depth streams for multiple symbols.
        
        Args:
            symbols: List of symbols to stream (e.g., ["btcusdt", "ethusdt"])
            background: If True, runs in background (returns immediately)
        """
        self.running = True
        
        logger.info(f"🚀 Starting depth streams for {len(symbols)} symbols")
        
        # Create connection tasks
        self.tasks = [asyncio.create_task(self.connect(sym)) for sym in symbols]
        
        if not background:
            # Wait for all tasks (blocking)
            await asyncio.gather(*self.tasks)
        else:
            # Return immediately, tasks run in background
            logger.info(f"✅ Depth streams running in background")
    
    async def stop_async(self):
        """Stop all depth streams and wait for tasks to complete"""
        logger.info("🛑 Stopping depth streams...")
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
        
        logger.info("✅ Depth streams stopped")

    def stop(self):
        """Stop all depth streams (sync wrapper)."""
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
            logger.info("✅ Depth streams stopped (no event loop)")


class OrderBookAnalyzer:
    """
    Analyze order book depth for trading signals.
    
    Features:
    - Liquidity void detection
    - Order book imbalance
    - Support/resistance levels
    - Bid/ask pressure
    """
    
    def __init__(self, history_size: int = 10):
        """
        Initialize analyzer.
        
        Args:
            history_size: Number of depth snapshots to keep per symbol
        """
        self.depth_history = {}  # symbol -> deque of depth snapshots
        self.history_size = history_size
        
        logger.info(f"📊 OrderBookAnalyzer initialized (history={history_size})")
    
    def update(self, symbol: str, depth: Dict):
        """Update depth history for a symbol"""
        if symbol not in self.depth_history:
            self.depth_history[symbol] = deque(maxlen=self.history_size)
        
        self.depth_history[symbol].append(depth)
    
    def get_latest_depth(self, symbol: str) -> Optional[Dict]:
        """Get latest depth snapshot"""
        if symbol in self.depth_history and len(self.depth_history[symbol]) > 0:
            return self.depth_history[symbol][-1]
        return None
    
    def calculate_imbalance(self, symbol: str, levels: int = 5) -> Optional[float]:
        """
        Calculate bid/ask imbalance ratio.
        
        Imbalance > 1.0: More bids (bullish pressure)
        Imbalance < 1.0: More asks (bearish pressure)
        
        Args:
            symbol: Trading symbol
            levels: Number of levels to analyze (default 5)
        
        Returns:
            Imbalance ratio (bid_volume / ask_volume) or None
        """
        depth = self.get_latest_depth(symbol)
        if not depth:
            return None
        
        bids = depth["bids"][:levels]
        asks = depth["asks"][:levels]
        
        bid_volume = sum(qty for _, qty in bids)
        ask_volume = sum(qty for _, qty in asks)
        
        if ask_volume == 0:
            return None
        
        return bid_volume / ask_volume
    
    def detect_liquidity_voids(self, symbol: str, threshold: float = 2.0) -> list:
        """
        Detect liquidity voids in order book.
        
        A void occurs when gap between price levels > threshold * avg gap.
        
        Args:
            symbol: Trading symbol
            threshold: Multiplier for average gap (2.0 = 2x normal)
        
        Returns:
            List of void zones: [{"side": "bid/ask", "price_from": X, "price_to": Y, "gap": Z}]
        """
        depth = self.get_latest_depth(symbol)
        if not depth:
            return []
        
        voids = []
        
        # Check bids for voids (descending prices)
        bids = depth["bids"]
        if len(bids) >= 3:
            gaps = [bids[i][0] - bids[i+1][0] for i in range(len(bids)-1)]
            avg_gap = sum(gaps) / len(gaps) if gaps else 0
            
            for i, gap in enumerate(gaps):
                if gap > threshold * avg_gap and avg_gap > 0:
                    voids.append({
                        "side": "bid",
                        "price_from": bids[i+1][0],
                        "price_to": bids[i][0],
                        "gap": gap,
                        "severity": gap / avg_gap
                    })
        
        # Check asks for voids (ascending prices)
        asks = depth["asks"]
        if len(asks) >= 3:
            gaps = [asks[i+1][0] - asks[i][0] for i in range(len(asks)-1)]
            avg_gap = sum(gaps) / len(gaps) if gaps else 0
            
            for i, gap in enumerate(gaps):
                if gap > threshold * avg_gap and avg_gap > 0:
                    voids.append({
                        "side": "ask",
                        "price_from": asks[i][0],
                        "price_to": asks[i+1][0],
                        "gap": gap,
                        "severity": gap / avg_gap
                    })
        
        return voids
    
    def get_total_liquidity(self, symbol: str, levels: int = 10) -> Optional[Dict]:
        """
        Get total liquidity in order book.
        
        Returns:
            {"bid_liquidity": X, "ask_liquidity": Y, "total": Z} or None
        """
        depth = self.get_latest_depth(symbol)
        if not depth:
            return None
        
        bids = depth["bids"][:levels]
        asks = depth["asks"][:levels]
        
        bid_liquidity = sum(price * qty for price, qty in bids)
        ask_liquidity = sum(price * qty for price, qty in asks)
        
        return {
            "bid_liquidity": bid_liquidity,
            "ask_liquidity": ask_liquidity,
            "total": bid_liquidity + ask_liquidity,
            "imbalance": bid_liquidity / ask_liquidity if ask_liquidity > 0 else None
        }
    
    def get_best_bid_ask(self, symbol: str) -> Optional[Dict]:
        """Get best bid and ask prices with spread"""
        depth = self.get_latest_depth(symbol)
        if not depth or not depth["bids"] or not depth["asks"]:
            return None
        
        best_bid = depth["bids"][0][0]
        best_ask = depth["asks"][0][0]
        spread = best_ask - best_bid
        spread_pct = (spread / best_bid) * 100 if best_bid > 0 else 0
        
        return {
            "bid": best_bid,
            "ask": best_ask,
            "spread": spread,
            "spread_pct": spread_pct
        }
    
    def detect_imbalance_with_direction(self, symbol: str, levels: int = 5, threshold: float = 1.5) -> Optional[Dict]:
        """
        Phase III: Detect order book imbalance with direction.
        
        Args:
            symbol: Trading symbol
            levels: Number of levels to analyze (default 5)
            threshold: Imbalance threshold ratio (default 1.5 = 1.5:1)
        
        Returns:
            {
                "imbalance_detected": bool,
                "imbalance_ratio": float,
                "imbalance_direction": "buy" | "sell" | None,
                "bid_volume": float,
                "ask_volume": float
            } or None
        """
        imbalance_ratio = self.calculate_imbalance(symbol, levels)
        if imbalance_ratio is None:
            return None
        
        depth = self.get_latest_depth(symbol)
        if not depth:
            return None
        
        bids = depth["bids"][:levels]
        asks = depth["asks"][:levels]
        bid_volume = sum(qty for _, qty in bids)
        ask_volume = sum(qty for _, qty in asks)
        
        # Detect imbalance if ratio exceeds threshold
        imbalance_detected = imbalance_ratio >= threshold or imbalance_ratio <= (1.0 / threshold)
        
        # Determine direction
        if imbalance_ratio >= threshold:
            direction = "buy"  # Buy-side imbalance (more bids)
        elif imbalance_ratio <= (1.0 / threshold):
            direction = "sell"  # Sell-side imbalance (more asks)
        else:
            direction = None
        
        return {
            "imbalance_detected": imbalance_detected,
            "imbalance_ratio": imbalance_ratio,
            "imbalance_direction": direction,
            "bid_volume": bid_volume,
            "ask_volume": ask_volume
        }
    
    def detect_spoofing(self, symbol: str, min_order_size_usd: float = 10000.0, max_lifetime_seconds: float = 5.0) -> Optional[Dict]:
        """
        Phase III: Detect spoofing using snapshot comparison method.
        
        Compares order book snapshots to detect large orders that disappear quickly.
        This is a proxy for spoofing (not perfect but workable).
        
        Args:
            symbol: Trading symbol
            min_order_size_usd: Minimum order size in USD to consider (default $10k)
            max_lifetime_seconds: Maximum lifetime in seconds for order to be considered spoofing (default 5s)
        
        Returns:
            {
                "spoof_detected": bool,
                "spoof_events": int,  # Number of spoof events detected
                "largest_spoof_size_usd": float,
                "cancellation_rate": float  # Orders disappearing per second
            } or None
        """
        if symbol not in self.depth_history or len(self.depth_history[symbol]) < 2:
            return None
        
        history = list(self.depth_history[symbol])
        if len(history) < 2:
            return None
        
        # Compare last 2-5 snapshots (assuming 1-2 second intervals)
        snapshots_to_compare = min(5, len(history))
        recent_snapshots = history[-snapshots_to_compare:]
        
        spoof_events = []
        total_cancellations = 0
        
        # Compare consecutive snapshots
        for i in range(1, len(recent_snapshots)):
            prev_snapshot = recent_snapshots[i-1]
            curr_snapshot = recent_snapshots[i]
            
            # Extract large orders from previous snapshot
            prev_bids = {price: qty for price, qty in prev_snapshot.get("bids", [])}
            prev_asks = {price: qty for price, qty in prev_snapshot.get("asks", [])}
            
            curr_bids = {price: qty for price, qty in curr_snapshot.get("bids", [])}
            curr_asks = {price: qty for price, qty in curr_snapshot.get("asks", [])}
            
            # Find large orders that disappeared
            # Use mid price to estimate USD value
            mid_price = (prev_snapshot.get("bids", [[0]])[0][0] + prev_snapshot.get("asks", [[0]])[0][0]) / 2
            
            # Check bids
            for price, qty in prev_bids.items():
                order_size_usd = price * qty * mid_price  # Approximate USD value
                if order_size_usd >= min_order_size_usd:
                    # Check if order disappeared or significantly reduced
                    if price not in curr_bids or curr_bids[price] < qty * 0.5:  # Reduced by >50%
                        spoof_events.append({
                            "side": "bid",
                            "price": price,
                            "size_usd": order_size_usd,
                            "lifetime_seconds": i  # Approximate (1-2 seconds per snapshot)
                        })
                        total_cancellations += 1
            
            # Check asks
            for price, qty in prev_asks.items():
                order_size_usd = price * qty * mid_price
                if order_size_usd >= min_order_size_usd:
                    if price not in curr_asks or curr_asks[price] < qty * 0.5:
                        spoof_events.append({
                            "side": "ask",
                            "price": price,
                            "size_usd": order_size_usd,
                            "lifetime_seconds": i
                        })
                        total_cancellations += 1
        
        # Filter spoof events by lifetime
        spoof_events_filtered = [e for e in spoof_events if e["lifetime_seconds"] <= max_lifetime_seconds]
        
        spoof_detected = len(spoof_events_filtered) > 0
        
        # Calculate cancellation rate (orders per second)
        # Assume snapshots are 1-2 seconds apart
        time_window = len(recent_snapshots) * 1.5  # Approximate seconds
        cancellation_rate = total_cancellations / time_window if time_window > 0 else 0
        
        largest_spoof = max([e["size_usd"] for e in spoof_events_filtered], default=0.0)
        
        return {
            "spoof_detected": spoof_detected,
            "spoof_events": len(spoof_events_filtered),
            "largest_spoof_size_usd": largest_spoof,
            "cancellation_rate": cancellation_rate
        }
    
    def calculate_rebuild_speed(self, symbol: str, window_seconds: int = 20) -> Optional[Dict]:
        """
        Phase III: Calculate bid/ask rebuild and decay speeds.
        
        Tracks depth changes over time to measure liquidity rebuild/decay rates.
        
        Args:
            symbol: Trading symbol
            window_seconds: Time window in seconds (default 20)
        
        Returns:
            {
                "bid_rebuild_speed": float,  # Orders per second
                "ask_decay_speed": float,  # Orders per second
                "bid_depth_change": float,
                "ask_depth_change": float,
                "liquidity_rebuild_confirmed": bool  # rebuild > decay by >0.2 for >30 seconds
            } or None
        """
        if symbol not in self.depth_history or len(self.depth_history[symbol]) < 2:
            return None
        
        history = list(self.depth_history[symbol])
        if len(history) < 2:
            return None
        
        # Use last N snapshots (assuming 1-2 second intervals)
        snapshots_to_use = min(10, len(history))
        recent_snapshots = history[-snapshots_to_use:]
        
        # Calculate depth changes
        oldest_snapshot = recent_snapshots[0]
        newest_snapshot = recent_snapshots[-1]
        
        # Calculate total depth (sum of top 5 levels)
        def get_depth(snapshot, side: str, levels: int = 5):
            orders = snapshot.get(side, [])[:levels]
            return sum(qty for _, qty in orders)
        
        old_bid_depth = get_depth(oldest_snapshot, "bids", 5)
        new_bid_depth = get_depth(newest_snapshot, "bids", 5)
        bid_depth_change = new_bid_depth - old_bid_depth
        
        old_ask_depth = get_depth(oldest_snapshot, "asks", 5)
        new_ask_depth = get_depth(newest_snapshot, "asks", 5)
        ask_depth_change = new_ask_depth - old_ask_depth
        
        # Calculate speeds (orders per second)
        # Assume snapshots are 1-2 seconds apart
        time_elapsed = (snapshots_to_use - 1) * 1.5  # Approximate seconds
        if time_elapsed == 0:
            return None
        
        bid_rebuild_speed = bid_depth_change / time_elapsed if bid_depth_change > 0 else 0.0
        ask_decay_speed = abs(ask_depth_change) / time_elapsed if ask_depth_change < 0 else 0.0
        
        # Check if rebuild confirmed (rebuild > decay by >0.2 for >30 seconds)
        # For now, check if current window shows this pattern
        # In production, would track over 30+ seconds
        liquidity_rebuild_confirmed = (
            bid_rebuild_speed > ask_decay_speed and
            (bid_rebuild_speed - ask_decay_speed) > 0.2 and
            time_elapsed >= 10  # At least 10 seconds of data
        )
        
        return {
            "bid_rebuild_speed": bid_rebuild_speed,
            "ask_decay_speed": ask_decay_speed,
            "bid_depth_change": bid_depth_change,
            "ask_depth_change": ask_depth_change,
            "liquidity_rebuild_confirmed": liquidity_rebuild_confirmed,
            "time_window_seconds": time_elapsed
        }

