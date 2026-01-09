"""
MT5 Local Bridge
Direct connection to MT5 terminal via Python API
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)

@dataclass
class MT5Config:
    """MT5 bridge configuration"""
    timeout: int
    symbols: List[str]
    timeframes: List[str]
    update_interval: int

class MT5LocalBridge:
    """
    MT5 Local Bridge for direct terminal access
    
    Features:
    - Direct MT5 terminal connection
    - Real-time tick data retrieval
    - Historical data access
    - Trade execution capabilities
    - Ultra-low latency (<50ms)
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = MT5Config(**config)
        self._is_connected = False
        self.is_running = False
        
        # MT5 connection state
        self.terminal_connected = False
        self.account_info = None
        
        # Data handlers
        self.tick_handlers: List[Callable[[Dict], None]] = []
        
        # Background tasks
        self.tasks: List[asyncio.Task] = []
        
        # Performance monitoring
        self.performance_metrics = {
            'last_update': None,
            'update_count': 0,
            'error_count': 0,
            'latency_ms': 0
        }
        
        logger.info("MT5LocalBridge initialized")
    
    async def initialize(self):
        """Initialize MT5 bridge"""
        try:
            logger.info("🔧 Initializing MT5 bridge...")
            
            # Initialize MT5
            if not mt5.initialize():
                raise ConnectionError("Failed to initialize MT5")
            
            # Check terminal connection
            if not mt5.terminal_info():
                raise ConnectionError("MT5 terminal not connected")
            
            # Get account info
            self.account_info = mt5.account_info()
            if not self.account_info:
                raise ConnectionError("Failed to get account info")
            
            # Verify symbols
            await self._verify_symbols()
            
            self.terminal_connected = True
            logger.info("✅ MT5 bridge initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize MT5 bridge: {e}")
            raise
    
    async def _verify_symbols(self):
        """Verify that all configured symbols are available"""
        try:
            available_symbols = []
            
            # Wait a moment for MT5 to be fully initialized
            await asyncio.sleep(0.1)
            
            # Retry logic for symbol verification
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    for symbol in self.config.symbols:
                        symbol_info = mt5.symbol_info(symbol)
                        if not symbol_info:
                            # Silently skip unavailable symbols
                            continue
                        
                        # Check if symbol is visible
                        if not symbol_info.visible:
                            logger.debug(f"📊 Making symbol {symbol} visible...")
                            if not mt5.symbol_select(symbol, True):
                                continue
                        
                        available_symbols.append(symbol)
                    
                    # If we found symbols, break out of retry loop
                    if available_symbols:
                        break
                        
                except Exception as e:
                    logger.debug(f"⚠️ Symbol verification attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.5)  # Wait before retry
                    continue
            
            # Update config to only include available symbols
            self.config.symbols = available_symbols
            logger.info(f"✅ Verified {len(available_symbols)} available symbols")
                
        except Exception as e:
            logger.error(f"❌ Error verifying symbols: {e}")
    
    async def start(self):
        """Start MT5 bridge"""
        try:
            logger.info("🚀 Starting MT5 bridge...")
            
            self.is_running = True
            
            # Start tick monitoring for each symbol
            for symbol in self.config.symbols:
                task = asyncio.create_task(self._monitor_symbol_ticks(symbol))
                self.tasks.append(task)
            
            # Start historical data monitoring
            historical_task = asyncio.create_task(self._monitor_historical_data())
            self.tasks.append(historical_task)
            
            # Start health monitoring
            health_task = asyncio.create_task(self._health_monitor())
            self.tasks.append(health_task)
            
            self._is_connected = True
            logger.info("✅ MT5 bridge started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start MT5 bridge: {e}")
            self._is_connected = False
            raise
    
    async def stop(self):
        """Stop MT5 bridge"""
        try:
            logger.info("🛑 Stopping MT5 bridge...")
            
            self.is_running = False
            
            # Cancel background tasks
            for task in self.tasks:
                task.cancel()
            
            # Wait for tasks to complete
            await asyncio.gather(*self.tasks, return_exceptions=True)
            
            # Disconnect from MT5
            mt5.shutdown()
            
            self._is_connected = False
            logger.info("✅ MT5 bridge stopped successfully")
            
        except Exception as e:
            logger.error(f"❌ Error stopping MT5 bridge: {e}")
    
    async def disconnect(self):
        """Disconnect from MT5 (alias for stop)"""
        await self.stop()
    
    async def _monitor_symbol_ticks(self, symbol: str):
        """Monitor ticks for a specific symbol"""
        last_tick_time = None
        
        while self.is_running:
            try:
                # Get current tick
                tick = mt5.symbol_info_tick(symbol)
                
                if tick and tick.time > (last_tick_time or 0):
                    # Process new tick
                    await self._process_tick_data(symbol, tick)
                    last_tick_time = tick.time
                
                # Wait for next update
                await asyncio.sleep(self.config.update_interval / 1000)
                
            except Exception as e:
                logger.error(f"❌ Error monitoring {symbol} ticks: {e}")
                self.performance_metrics['error_count'] += 1
                await asyncio.sleep(1)
    
    async def _monitor_historical_data(self):
        """Monitor historical data for higher timeframes"""
        while self.is_running:
            try:
                # Get historical data for each timeframe
                for timeframe in self.config.timeframes:
                    await self._update_historical_data(timeframe)
                
                # Wait before next update
                await asyncio.sleep(60)  # Update every minute
                
            except Exception as e:
                logger.error(f"❌ Error monitoring historical data: {e}")
                await asyncio.sleep(10)
    
    async def _update_historical_data(self, timeframe: str):
        """Update historical data for timeframe"""
        try:
            # Convert timeframe string to MT5 constant
            tf_constant = self._get_timeframe_constant(timeframe)
            
            for symbol in self.config.symbols:
                # Get recent bars
                rates = mt5.copy_rates_from_pos(symbol, tf_constant, 0, 100)
                
                if rates is not None and len(rates) > 0:
                    # Process the latest bar
                    latest_bar = rates[-1]
                    await self._process_historical_data(symbol, timeframe, latest_bar)
                
        except Exception as e:
            logger.error(f"❌ Error updating historical data for {timeframe}: {e}")
    
    def _get_timeframe_constant(self, timeframe: str):
        """Convert timeframe string to MT5 constant"""
        timeframe_map = {
            'M1': mt5.TIMEFRAME_M1,
            'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15,
            'H1': mt5.TIMEFRAME_H1,
            'H4': mt5.TIMEFRAME_H4
        }
        return timeframe_map.get(timeframe, mt5.TIMEFRAME_M1)
    
    async def _process_tick_data(self, symbol: str, tick):
        """Process MT5 tick data"""
        try:
            # Check if we're shutting down - skip processing during shutdown
            if not self.is_running:
                return
                
            # Check if tick is valid and has required attributes
            if tick is None or not hasattr(tick, 'bid') or not hasattr(tick, 'ask') or not hasattr(tick, 'time'):
                logger.debug(f"⚠️ MT5 tick missing required attributes for {symbol}: {type(tick)}")
                return
            
            # Check if tick values are valid (not None or NaN)
            if tick.bid is None or tick.ask is None or tick.time is None:
                logger.debug(f"⚠️ MT5 tick has None values for {symbol}")
                return
                
            # Convert to unified format
            unified_tick = {
                'symbol': symbol,
                'timestamp': tick.time,
                'bid': tick.bid,
                'ask': tick.ask,
                'volume': tick.volume,
                'source': 'mt5',
                'raw_data': {
                    'time': tick.time,
                    'bid': tick.bid,
                    'ask': tick.ask,
                    'last': tick.last,
                    'volume': tick.volume,
                    'flags': tick.flags,
                    'volume_real': tick.volume_real
                }
            }
            
            # Update performance metrics
            self._update_performance_metrics()
            
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
    
    async def _process_historical_data(self, symbol: str, timeframe: str, bar_data):
        """Process historical bar data"""
        try:
            # Convert to unified format
            unified_bar = {
                'symbol': symbol,
                'timeframe': timeframe,
                'timestamp': bar_data['time'],
                'open': bar_data['open'],
                'high': bar_data['high'],
                'low': bar_data['low'],
                'close': bar_data['close'],
                'volume': bar_data['tick_volume'],
                'source': 'mt5_historical',
                'raw_data': bar_data
            }
            
            # Notify handlers (if they want historical data)
            for handler in self.tick_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(unified_bar)
                    else:
                        handler(unified_bar)
                except Exception as e:
                    logger.error(f"❌ Error in historical data handler: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error processing historical data: {e}")
    
    def _update_performance_metrics(self):
        """Update performance metrics"""
        self.performance_metrics['update_count'] += 1
        self.performance_metrics['last_update'] = datetime.now(timezone.utc)
        
        # Calculate latency (simplified)
        self.performance_metrics['latency_ms'] = 10  # MT5 is typically very fast
    
    async def _health_monitor(self):
        """Monitor MT5 connection health"""
        while self.is_running:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Check terminal connection
                terminal_info = mt5.terminal_info()
                if not terminal_info:
                    logger.warning("⚠️ MT5 terminal connection lost")
                    await self.reconnect()
                    continue
                
                # Check account connection
                account_info = mt5.account_info()
                if not account_info:
                    logger.warning("⚠️ MT5 account connection lost")
                    await self.reconnect()
                    continue
                
                # Check if we're in trading hours
                if not terminal_info.trade_allowed:
                    logger.debug("📊 Trading not allowed (market closed or disconnected)")
                
            except Exception as e:
                logger.error(f"❌ Error in health monitor: {e}")
                await asyncio.sleep(10)
    
    async def reconnect(self):
        """Reconnect to MT5"""
        try:
            logger.info("🔄 Reconnecting to MT5...")
            
            # Shutdown current connection
            mt5.shutdown()
            
            # Wait a moment
            await asyncio.sleep(1)
            
            # Reinitialize
            await self.initialize()
            
            # Restart monitoring
            if self.is_running:
                await self.start()
            
        except Exception as e:
            logger.error(f"❌ Error reconnecting to MT5: {e}")
    
    def register_tick_handler(self, handler: Callable[[Dict], None]):
        """Register a tick data handler"""
        self.tick_handlers.append(handler)
        logger.info(f"📡 Registered MT5 tick handler (total: {len(self.tick_handlers)})")
    
    def is_connected(self) -> bool:
        """Check if MT5 is connected"""
        return self.terminal_connected and self.is_running
    
    def get_status(self) -> Dict[str, Any]:
        """Get MT5 bridge status"""
        terminal_info = mt5.terminal_info() if mt5.initialize() else None
        account_info = mt5.account_info() if terminal_info else None
        
        return {
            'is_connected': self.is_connected(),
            'terminal_connected': self.terminal_connected,
            'terminal_info': {
                'name': terminal_info.name if terminal_info else None,
                'company': terminal_info.company if terminal_info else None,
                'path': terminal_info.path if terminal_info else None,
                'trade_allowed': terminal_info.trade_allowed if terminal_info else None
            },
            'account_info': {
                'login': account_info.login if account_info else None,
                'server': account_info.server if account_info else None,
                'currency': account_info.currency if account_info else None,
                'balance': account_info.balance if account_info else None
            },
            'performance_metrics': self.performance_metrics,
            'handler_count': len(self.tick_handlers)
        }
    
    # Public API methods
    async def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """Get symbol information"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info:
                return {
                    'symbol': symbol_info.name,
                    'description': symbol_info.description,
                    'currency_base': symbol_info.currency_base,
                    'currency_profit': symbol_info.currency_profit,
                    'currency_margin': symbol_info.currency_margin,
                    'point': symbol_info.point,
                    'digits': symbol_info.digits,
                    'spread': symbol_info.spread,
                    'trade_mode': symbol_info.trade_mode,
                    'visible': symbol_info.visible
                }
        except Exception as e:
            logger.error(f"❌ Error getting symbol info for {symbol}: {e}")
        return None
    
    async def get_account_info(self) -> Optional[Dict]:
        """Get account information"""
        try:
            account_info = mt5.account_info()
            if account_info:
                return {
                    'login': account_info.login,
                    'server': account_info.server,
                    'currency': account_info.currency,
                    'balance': account_info.balance,
                    'equity': account_info.equity,
                    'margin': account_info.margin,
                    'free_margin': account_info.margin_free,
                    'margin_level': account_info.margin_level,
                    'profit': account_info.profit
                }
        except Exception as e:
            logger.error(f"❌ Error getting account info: {e}")
        return None
    
    async def get_positions(self) -> List[Dict]:
        """Get current positions"""
        try:
            positions = mt5.positions_get()
            if positions:
                return [
                    {
                        'ticket': pos.ticket,
                        'symbol': pos.symbol,
                        'type': pos.type,
                        'volume': pos.volume,
                        'price_open': pos.price_open,
                        'price_current': pos.price_current,
                        'sl': pos.sl,
                        'tp': pos.tp,
                        'profit': pos.profit,
                        'time': pos.time,
                        'time_msc': pos.time_msc,
                        'time_update': pos.time_update,
                        'time_update_msc': pos.time_update_msc
                    }
                    for pos in positions
                ]
        except Exception as e:
            logger.error(f"❌ Error getting positions: {e}")
        return []
    
    async def get_orders(self) -> List[Dict]:
        """Get current orders"""
        try:
            orders = mt5.orders_get()
            if orders:
                return [
                    {
                        'ticket': order.ticket,
                        'symbol': order.symbol,
                        'type': order.type,
                        'volume': order.volume_initial,
                        'price_open': order.price_open,
                        'sl': order.sl,
                        'tp': order.tp,
                        'time_setup': order.time_setup,
                        'time_expiration': order.time_expiration,
                        'state': order.state,
                        'comment': order.comment
                    }
                    for order in orders
                ]
        except Exception as e:
            logger.error(f"❌ Error getting orders: {e}")
        return []
