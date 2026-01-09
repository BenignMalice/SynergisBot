"""
Binance WebSocket Feed Manager
Handles dual Binance feeds with redundancy and failover
"""

import asyncio
import websockets
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any
import aiohttp
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class BinanceConfig:
    """Binance feed configuration"""
    enabled: bool = False
    symbols: List[str] = None
    primary_ws_url: str = ""
    mirror_ws_url: str = ""
    heartbeat_interval: int = 60
    reconnect_delay: int = 5
    max_reconnect_attempts: int = 10

class BinanceFeedManager:
    """
    Manages Binance WebSocket feeds with dual-layer redundancy
    
    Features:
    - Primary and mirror WebSocket connections
    - Automatic failover and reconnection
    - Heartbeat monitoring
    - Latency detection and switching
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = BinanceConfig(**config)
        self._is_connected = False
        self.is_running = False
        
        # WebSocket connections
        self.primary_ws: Optional[websockets.WebSocketServerProtocol] = None
        self.mirror_ws: Optional[websockets.WebSocketServerProtocol] = None
        
        # Connection state
        self.primary_connected = False
        self.mirror_connected = False
        self.active_connection = None
        self._is_connected = False
        
        # Performance monitoring
        self.performance_metrics = {
            'primary_latency': 0,
            'mirror_latency': 0,
            'last_heartbeat': None,
            'reconnect_count': 0,
            'error_count': 0
        }
        
        # Data handlers
        self.tick_handlers: List[Callable[[Dict], None]] = []
        
        # Background tasks
        self.tasks: List[asyncio.Task] = []
        
        logger.info("BinanceFeedManager initialized")
    
    async def initialize(self):
        """Initialize the Binance feed manager"""
        try:
            logger.info("🔧 Initializing Binance feed manager...")
            
            # Validate configuration
            if not self.config.symbols:
                raise ValueError("No symbols configured for Binance feeds")
            
            # Create WebSocket URLs
            self.primary_urls = self._create_websocket_urls(self.config.primary_ws_url)
            self.mirror_urls = self._create_websocket_urls(self.config.mirror_ws_url)
            
            logger.info(f"✅ Binance feed manager initialized for symbols: {self.config.symbols}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Binance feed manager: {e}")
            raise
    
    def _create_websocket_urls(self, base_url: str) -> Dict[str, str]:
        """Create WebSocket URLs for all symbols"""
        urls = {}
        
        for symbol in self.config.symbols:
            # Convert symbol to Binance format
            binance_symbol = self._convert_symbol_to_binance(symbol)
            stream_name = f"{binance_symbol.lower()}@ticker"
            urls[symbol] = f"{base_url}{stream_name}"
        
        return urls
    
    def _convert_symbol_to_binance(self, symbol: str) -> str:
        """Convert trading symbol to Binance format"""
        symbol_mapping = {
            'BTCUSDT': 'btcusdt',
            'ETHUSDT': 'ethusdt',
            'XAUUSDT': 'xauusdt'  # This doesn't exist on Binance
        }
        return symbol_mapping.get(symbol, symbol.lower())
    
    async def start(self):
        """Start Binance feeds"""
        try:
            # Check if Binance feeds are enabled
            if not self.config.enabled:
                logger.info("📴 Binance feeds disabled - skipping initialization")
                return
            
            # Check if symbols are configured
            if not self.config.symbols or len(self.config.symbols) == 0:
                logger.warning("⚠️ No symbols configured for Binance feeds")
                return
            
            logger.info("🚀 Starting Binance feeds...")
            
            self.is_running = True
            
            # Start primary connection
            primary_task = asyncio.create_task(self._start_primary_connection())
            self.tasks.append(primary_task)
            
            # Start mirror connection
            mirror_task = asyncio.create_task(self._start_mirror_connection())
            self.tasks.append(mirror_task)
            
            # Start heartbeat monitoring
            heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
            self.tasks.append(heartbeat_task)
            
            # Start latency monitoring
            latency_task = asyncio.create_task(self._latency_monitor())
            self.tasks.append(latency_task)
            
            self._is_connected = True
            logger.info("✅ Binance feeds started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Binance feeds: {e}")
            self._is_connected = False
            raise
    
    async def stop(self):
        """Stop Binance feeds"""
        try:
            logger.info("🛑 Stopping Binance feeds...")
            
            self.is_running = False
            
            # Close WebSocket connections
            if self.primary_ws:
                await self.primary_ws.close()
            if self.mirror_ws:
                await self.mirror_ws.close()
            
            # Cancel background tasks
            for task in self.tasks:
                task.cancel()
            
            # Wait for tasks to complete
            await asyncio.gather(*self.tasks, return_exceptions=True)
            
            self._is_connected = False
            logger.info("✅ Binance feeds stopped successfully")
            
        except Exception as e:
            logger.error(f"❌ Error stopping Binance feeds: {e}")
    
    async def _start_primary_connection(self):
        """Start primary WebSocket connection"""
        reconnect_attempts = 0
        
        while self.is_running and reconnect_attempts < self.config.max_reconnect_attempts:
            try:
                logger.info("🔗 Starting primary Binance connection...")
                
                # Create combined stream URL
                streams = []
                for symbol in self.config.symbols:
                    binance_symbol = self._convert_symbol_to_binance(symbol)
                    streams.append(f"{binance_symbol.lower()}@ticker")
                
                # Use combined stream URL
                combined_url = f"{self.config.primary_ws_url}{'/'.join(streams)}"
                logger.info(f"🔗 Connecting to: {combined_url}")
                
                try:
                    self.primary_ws = await websockets.connect(
                        combined_url,
                        ping_interval=self.config.heartbeat_interval,
                        ping_timeout=120,  # Increased timeout
                        close_timeout=60,  # Increased timeout
                        open_timeout=120,  # Increased timeout
                        max_size=2**20,    # 1MB max message size
                        max_queue=1000     # Max queued messages
                    )
                    
                    # Start receiving data
                    await self._handle_primary_connection()
                    self.primary_connected = True
                    reconnect_attempts = 0  # Reset on successful connection
                    
                except websockets.exceptions.InvalidURI as e:
                    logger.error(f"❌ Invalid URI: {e}")
                    reconnect_attempts += 1
                except websockets.exceptions.ConnectionClosed as e:
                    logger.warning(f"⚠️ Primary connection closed: {e}")
                    self.primary_connected = False
                    reconnect_attempts += 1
                except asyncio.TimeoutError as e:
                    logger.error(f"❌ Primary connection timeout: {e}")
                    reconnect_attempts += 1
                except Exception as e:
                    logger.error(f"❌ Primary connection failed: {e}")
                    reconnect_attempts += 1
                    self.performance_metrics['reconnect_count'] += 1
                
            except Exception as e:
                logger.error(f"❌ Primary connection error: {e}")
                reconnect_attempts += 1
                self.performance_metrics['reconnect_count'] += 1
                
                if self.is_running:
                    # Exponential backoff with jitter
                    delay = min(self.config.reconnect_delay * (2 ** reconnect_attempts), 120)
                    jitter = asyncio.get_event_loop().time() % 5  # Add up to 5 seconds jitter
                    total_delay = delay + jitter
                    logger.info(f"⏳ Waiting {total_delay:.1f} seconds before reconnection attempt {reconnect_attempts + 1}")
                    await asyncio.sleep(total_delay)
    
    async def _start_mirror_connection(self):
        """Start mirror WebSocket connection"""
        reconnect_attempts = 0
        
        while self.is_running and reconnect_attempts < self.config.max_reconnect_attempts:
            try:
                logger.info("🔗 Starting mirror Binance connection...")
                
                # Connect to all symbol streams
                for symbol, url in self.mirror_urls.items():
                    try:
                        self.mirror_ws = await websockets.connect(
                            url,
                            ping_interval=self.config.heartbeat_interval,
                            ping_timeout=120,  # Increased timeout
                            close_timeout=60,  # Increased timeout
                            open_timeout=120,  # Increased timeout
                            max_size=2**20,    # 1MB max message size
                            max_queue=1000     # Max queued messages
                        )
                        
                        # Start receiving data
                        await self._handle_mirror_connection(symbol)
                        
                    except Exception as e:
                        logger.error(f"❌ Mirror connection failed for {symbol}: {e}")
                        continue
                
                # If we get here, connection was successful
                self.mirror_connected = True
                reconnect_attempts = 0  # Reset on successful connection
                
            except Exception as e:
                logger.error(f"❌ Mirror connection error: {e}")
                reconnect_attempts += 1
                self.performance_metrics['reconnect_count'] += 1
                
                if self.is_running:
                    # Exponential backoff with jitter
                    delay = min(self.config.reconnect_delay * (2 ** reconnect_attempts), 120)
                    jitter = asyncio.get_event_loop().time() % 5  # Add up to 5 seconds jitter
                    total_delay = delay + jitter
                    logger.info(f"⏳ Waiting {total_delay:.1f} seconds before reconnection attempt {reconnect_attempts + 1}")
                    await asyncio.sleep(total_delay)
    
    async def _handle_primary_connection(self):
        """Handle primary connection data"""
        try:
            async for message in self.primary_ws:
                if not self.is_running:
                    break
                
                try:
                    data = json.loads(message)
                    # Extract symbol from stream name
                    stream = data.get('stream', '')
                    symbol = self._extract_symbol_from_stream(stream)
                    if symbol:
                        await self._process_tick_data(symbol, data, 'primary')
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSON decode error in primary connection: {e}")
                    continue
                except Exception as e:
                    logger.error(f"❌ Error processing primary data: {e}")
                    continue
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("⚠️ Primary connection closed")
            self.primary_connected = False
        except Exception as e:
            logger.error(f"❌ Primary connection error: {e}")
            self.primary_connected = False
    
    def _extract_symbol_from_stream(self, stream: str) -> Optional[str]:
        """Extract symbol from stream name"""
        try:
            # Stream format: btcusdt@ticker
            symbol_part = stream.split('@')[0].upper()
            # Convert back to our symbol format
            for symbol in self.config.symbols:
                if self._convert_symbol_to_binance(symbol).lower() == symbol_part.lower():
                    return symbol
            return None
        except Exception:
            return None
    
    async def _handle_mirror_connection(self, symbol: str):
        """Handle mirror connection data"""
        try:
            async for message in self.mirror_ws:
                if not self.is_running:
                    break
                
                try:
                    data = json.loads(message)
                    await self._process_tick_data(symbol, data, 'mirror')
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSON decode error in mirror connection: {e}")
                    continue
                except Exception as e:
                    logger.error(f"❌ Error processing mirror data: {e}")
                    continue
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("⚠️ Mirror connection closed")
            self.mirror_connected = False
        except Exception as e:
            logger.error(f"❌ Mirror connection error: {e}")
            self.mirror_connected = False
    
    async def _process_tick_data(self, symbol: str, data: Dict, source: str):
        """Process incoming tick data"""
        try:
            # Extract tick information
            if 'data' in data:
                tick_data = data['data']
            else:
                tick_data = data
            
            # Convert to unified format
            unified_tick = {
                'symbol': symbol,
                'timestamp': tick_data.get('T', int(datetime.now().timestamp() * 1000)),
                'bid': float(tick_data.get('b', 0)),
                'ask': float(tick_data.get('a', 0)),
                'volume': float(tick_data.get('q', 0)),
                'source': f'binance_{source}',
                'raw_data': tick_data
            }
            
            # Update performance metrics
            self._update_performance_metrics(unified_tick, source)
            
            # Notify handlers
            for handler in self.tick_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(unified_tick)
                    else:
                        handler(unified_tick)
                except Exception as e:
                    logger.error(f"❌ Error in tick handler: {e}")
                    self.performance_metrics['error_count'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error processing tick data: {e}")
            self.performance_metrics['error_count'] += 1
    
    def _update_performance_metrics(self, tick_data: Dict, source: str):
        """Update performance metrics"""
        current_time = datetime.now(timezone.utc)
        tick_time = datetime.fromtimestamp(tick_data['timestamp'] / 1000, tz=timezone.utc)
        latency = (current_time - tick_time).total_seconds() * 1000
        
        if source == 'primary':
            self.performance_metrics['primary_latency'] = latency
        else:
            self.performance_metrics['mirror_latency'] = latency
        
        self.performance_metrics['last_heartbeat'] = current_time
    
    async def _heartbeat_monitor(self):
        """Monitor connection health and handle reconnections"""
        while self.is_running:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                
                # Check if we need to reconnect
                if not self.primary_connected and not self.mirror_connected:
                    logger.warning("⚠️ All connections lost, attempting reconnection...")
                    await self.reconnect()
                elif not self.primary_connected:
                    logger.warning("⚠️ Primary connection lost, attempting reconnection...")
                    await self._start_primary_connection()
                elif not self.mirror_connected:
                    logger.warning("⚠️ Mirror connection lost, attempting reconnection...")
                    await self._start_mirror_connection()
                
            except Exception as e:
                logger.error(f"❌ Error in heartbeat monitor: {e}")
                await asyncio.sleep(10)
    
    async def _latency_monitor(self):
        """Monitor latency and switch to best connection"""
        while self.is_running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Compare latencies and switch if needed
                primary_latency = self.performance_metrics['primary_latency']
                mirror_latency = self.performance_metrics['mirror_latency']
                
                if primary_latency > 0 and mirror_latency > 0:
                    # Switch to connection with lower latency
                    if mirror_latency < primary_latency * 0.8:  # 20% better
                        logger.info(f"🔄 Switching to mirror connection (latency: {mirror_latency:.2f}ms vs {primary_latency:.2f}ms)")
                        self.active_connection = 'mirror'
                    elif primary_latency < mirror_latency * 0.8:
                        logger.info(f"🔄 Switching to primary connection (latency: {primary_latency:.2f}ms vs {mirror_latency:.2f}ms)")
                        self.active_connection = 'primary'
                
            except Exception as e:
                logger.error(f"❌ Error in latency monitor: {e}")
                await asyncio.sleep(10)
    
    async def reconnect(self):
        """Reconnect all feeds"""
        try:
            logger.info("🔄 Reconnecting Binance feeds...")
            
            # Stop current connections
            if self.primary_ws:
                await self.primary_ws.close()
            if self.mirror_ws:
                await self.mirror_ws.close()
            
            # Reset connection states
            self.primary_connected = False
            self.mirror_connected = False
            
            # Restart connections
            await self.start()
            
        except Exception as e:
            logger.error(f"❌ Error reconnecting: {e}")
    
    def register_tick_handler(self, handler: Callable[[Dict], None]):
        """Register a tick data handler"""
        self.tick_handlers.append(handler)
        logger.info(f"📡 Registered tick handler (total: {len(self.tick_handlers)})")
    
    def is_connected(self) -> bool:
        """Check if any connection is active"""
        return self.primary_connected or self.mirror_connected
    
    def get_status(self) -> Dict[str, Any]:
        """Get connection status"""
        return {
            'is_connected': self.is_connected(),
            'primary_connected': self.primary_connected,
            'mirror_connected': self.mirror_connected,
            'active_connection': self.active_connection,
            'performance_metrics': self.performance_metrics,
            'handler_count': len(self.tick_handlers)
        }
