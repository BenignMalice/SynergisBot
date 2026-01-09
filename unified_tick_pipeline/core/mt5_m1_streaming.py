"""
MT5 M1 Streaming Enhancement
High-frequency M1 data streaming for forex pairs to improve DTMS and Intelligent Exits
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
import MetaTrader5 as mt5
import pandas as pd

logger = logging.getLogger(__name__)

@dataclass
class M1StreamingConfig:
    """M1 streaming configuration"""
    symbols: List[str] = None
    update_interval: int = 1  # 1 second
    buffer_size: int = 100
    enable_volatility_analysis: bool = True
    enable_structure_analysis: bool = True
    
    def __post_init__(self):
        if self.symbols is None:
            self.symbols = ['BTCUSDc']  # Default to BTCUSDc for M1 streaming

class MT5M1Streaming:
    """
    MT5 M1 Streaming for Enhanced DTMS and Intelligent Exits
    
    Features:
    - High-frequency M1 data streaming for forex pairs
    - Real-time volatility analysis
    - Structure analysis for DTMS decisions
    - Enhanced data for Intelligent Exits
    - Optimized for forex trading systems
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = M1StreamingConfig(**config)
        self.is_running = False
        self.is_connected = False
        
        # M1 data buffers
        self.m1_buffers: Dict[str, List[Dict]] = {}
        self.last_m1_times: Dict[str, datetime] = {}
        
        # Data handlers
        self.m1_handlers: List[Callable[[str, Dict], None]] = []
        self.volatility_handlers: List[Callable[[str, Dict], None]] = []
        self.structure_handlers: List[Callable[[str, Dict], None]] = []
        
        # Background tasks
        self.tasks: List[asyncio.Task] = []
        
        # Performance metrics
        self.performance_metrics = {
            'm1_candles_processed': 0,
            'volatility_calculations': 0,
            'structure_analyses': 0,
            'error_count': 0,
            'last_update': None
        }
        
        logger.info("MT5M1Streaming initialized")
    
    async def initialize(self) -> bool:
        """Initialize M1 streaming"""
        try:
            logger.info("🚀 Initializing MT5 M1 Streaming...")
            
            # Initialize MT5 connection
            if not mt5.initialize():
                logger.error("❌ MT5 initialization failed")
                return False
            
            # Initialize M1 buffers for each symbol
            for symbol in self.config.symbols:
                self.m1_buffers[symbol] = []
                self.last_m1_times[symbol] = datetime.now(timezone.utc)
            
            logger.info(f"✅ M1 streaming initialized for {len(self.config.symbols)} symbols")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error initializing M1 streaming: {e}")
            return False
    
    async def start(self):
        """Start M1 streaming"""
        try:
            logger.info("🚀 Starting MT5 M1 streaming...")
            
            self.is_running = True
            
            # Start M1 monitoring for each symbol
            for symbol in self.config.symbols:
                task = asyncio.create_task(self._monitor_m1_data(symbol))
                self.tasks.append(task)
            
            # Start volatility analysis
            if self.config.enable_volatility_analysis:
                volatility_task = asyncio.create_task(self._volatility_analysis_loop())
                self.tasks.append(volatility_task)
            
            # Start structure analysis
            if self.config.enable_structure_analysis:
                structure_task = asyncio.create_task(self._structure_analysis_loop())
                self.tasks.append(structure_task)
            
            self.is_connected = True
            logger.info("✅ MT5 M1 streaming started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start M1 streaming: {e}")
    
    async def stop(self):
        """Stop M1 streaming"""
        try:
            logger.info("🛑 Stopping MT5 M1 streaming...")
            
            self.is_running = False
            
            # Cancel all tasks
            for task in self.tasks:
                task.cancel()
            
            await asyncio.gather(*self.tasks, return_exceptions=True)
            
            # Disconnect from MT5
            mt5.shutdown()
            
            self.is_connected = False
            logger.info("✅ MT5 M1 streaming stopped successfully")
            
        except Exception as e:
            logger.error(f"❌ Error stopping M1 streaming: {e}")
    
    async def _monitor_m1_data(self, symbol: str):
        """Monitor M1 data for a specific symbol"""
        try:
            while self.is_running:
                # Get M1 candles
                m1_candles = await self._get_m1_candles(symbol)
                
                if m1_candles:
                    # Process new M1 data
                    await self._process_m1_data(symbol, m1_candles)
                
                # Wait for next update
                await asyncio.sleep(self.config.update_interval)
                
        except Exception as e:
            logger.error(f"❌ Error monitoring M1 data for {symbol}: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _get_m1_candles(self, symbol: str) -> List[Dict]:
        """Get M1 candles for a symbol"""
        try:
            # Get current time
            current_time = datetime.now(timezone.utc)
            
            # Get M1 candles from last update
            last_time = self.last_m1_times.get(symbol, current_time - timedelta(minutes=5))
            
            # Request M1 data
            rates = mt5.copy_rates_from(symbol, mt5.TIMEFRAME_M1, last_time, 100)
            
            if rates is None or len(rates) == 0:
                return []
            
            # Convert to list of dictionaries
            candles = []
            for rate in rates:
                candle = {
                    'symbol': symbol,
                    'time': datetime.fromtimestamp(rate['time'], tz=timezone.utc),
                    'open': rate['open'],
                    'high': rate['high'],
                    'low': rate['low'],
                    'close': rate['close'],
                    'volume': rate['tick_volume'],
                    'spread': rate['spread'],
                    'real_volume': rate['real_volume']
                }
                candles.append(candle)
            
            # Update last time
            if candles:
                self.last_m1_times[symbol] = candles[-1]['time']
            
            return candles
            
        except Exception as e:
            logger.error(f"❌ Error getting M1 candles for {symbol}: {e}")
            return []
    
    async def _process_m1_data(self, symbol: str, candles: List[Dict]):
        """Process M1 data for a symbol"""
        try:
            # Add to buffer
            self.m1_buffers[symbol].extend(candles)
            
            # Keep buffer size manageable
            if len(self.m1_buffers[symbol]) > self.config.buffer_size:
                self.m1_buffers[symbol] = self.m1_buffers[symbol][-self.config.buffer_size:]
            
            # Update performance metrics
            self.performance_metrics['m1_candles_processed'] += len(candles)
            self.performance_metrics['last_update'] = datetime.now(timezone.utc)
            
            # Notify handlers
            for handler in self.m1_handlers:
                try:
                    handler(symbol, candles)
                except Exception as e:
                    logger.error(f"❌ Error in M1 handler: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error processing M1 data for {symbol}: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _volatility_analysis_loop(self):
        """Continuous volatility analysis"""
        while self.is_running:
            try:
                for symbol in self.config.symbols:
                    if symbol in self.m1_buffers and len(self.m1_buffers[symbol]) >= 20:
                        # Calculate volatility
                        volatility_data = await self._calculate_volatility(symbol)
                        
                        if volatility_data:
                            # Notify volatility handlers
                            for handler in self.volatility_handlers:
                                try:
                                    handler(symbol, volatility_data)
                                except Exception as e:
                                    logger.error(f"❌ Error in volatility handler: {e}")
                
                # Wait before next analysis
                await asyncio.sleep(5)  # Analyze every 5 seconds
                
            except Exception as e:
                logger.error(f"❌ Error in volatility analysis loop: {e}")
                await asyncio.sleep(10)
    
    async def _structure_analysis_loop(self):
        """Continuous structure analysis"""
        while self.is_running:
            try:
                for symbol in self.config.symbols:
                    if symbol in self.m1_buffers and len(self.m1_buffers[symbol]) >= 50:
                        # Analyze structure
                        structure_data = await self._analyze_structure(symbol)
                        
                        if structure_data:
                            # Notify structure handlers
                            for handler in self.structure_handlers:
                                try:
                                    handler(symbol, structure_data)
                                except Exception as e:
                                    logger.error(f"❌ Error in structure handler: {e}")
                
                # Wait before next analysis
                await asyncio.sleep(10)  # Analyze every 10 seconds
                
            except Exception as e:
                logger.error(f"❌ Error in structure analysis loop: {e}")
                await asyncio.sleep(15)
    
    async def _calculate_volatility(self, symbol: str) -> Optional[Dict]:
        """Calculate volatility for a symbol"""
        try:
            candles = self.m1_buffers[symbol][-20:]  # Last 20 M1 candles
            
            if len(candles) < 20:
                return None
            
            # Calculate ATR (Average True Range)
            atr_values = []
            for i in range(1, len(candles)):
                high = candles[i]['high']
                low = candles[i]['low']
                prev_close = candles[i-1]['close']
                
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                atr_values.append(tr)
            
            atr = sum(atr_values) / len(atr_values)
            
            # Calculate price volatility
            closes = [c['close'] for c in candles]
            price_changes = [abs(closes[i] - closes[i-1]) for i in range(1, len(closes))]
            avg_price_change = sum(price_changes) / len(price_changes)
            
            # Calculate volatility score
            volatility_score = (atr / closes[-1]) * 100  # Percentage
            
            volatility_data = {
                'symbol': symbol,
                'timestamp': datetime.now(timezone.utc),
                'atr': atr,
                'volatility_score': volatility_score,
                'avg_price_change': avg_price_change,
                'candle_count': len(candles),
                'timeframe': 'M1'
            }
            
            self.performance_metrics['volatility_calculations'] += 1
            return volatility_data
            
        except Exception as e:
            logger.error(f"❌ Error calculating volatility for {symbol}: {e}")
            return None
    
    async def _analyze_structure(self, symbol: str) -> Optional[Dict]:
        """Analyze market structure for a symbol"""
        try:
            candles = self.m1_buffers[symbol][-50:]  # Last 50 M1 candles
            
            if len(candles) < 50:
                return None
            
            # Find recent highs and lows
            highs = [c['high'] for c in candles]
            lows = [c['low'] for c in candles]
            
            recent_high = max(highs[-20:])  # Highest in last 20 candles
            recent_low = min(lows[-20:])    # Lowest in last 20 candles
            
            # Calculate support and resistance levels
            resistance_levels = []
            support_levels = []
            
            for i in range(10, len(candles)):
                if candles[i]['high'] == recent_high:
                    resistance_levels.append(candles[i]['high'])
                if candles[i]['low'] == recent_low:
                    support_levels.append(candles[i]['low'])
            
            # Determine trend direction
            first_half = candles[:25]
            second_half = candles[25:]
            
            first_avg = sum(c['close'] for c in first_half) / len(first_half)
            second_avg = sum(c['close'] for c in second_half) / len(second_half)
            
            trend_direction = 'bullish' if second_avg > first_avg else 'bearish'
            trend_strength = abs(second_avg - first_avg) / first_avg * 100
            
            structure_data = {
                'symbol': symbol,
                'timestamp': datetime.now(timezone.utc),
                'recent_high': recent_high,
                'recent_low': recent_low,
                'resistance_levels': resistance_levels,
                'support_levels': support_levels,
                'trend_direction': trend_direction,
                'trend_strength': trend_strength,
                'candle_count': len(candles),
                'timeframe': 'M1'
            }
            
            self.performance_metrics['structure_analyses'] += 1
            return structure_data
            
        except Exception as e:
            logger.error(f"❌ Error analyzing structure for {symbol}: {e}")
            return None
    
    def add_m1_handler(self, handler: Callable[[str, Dict], None]):
        """Add M1 data handler"""
        self.m1_handlers.append(handler)
    
    def add_volatility_handler(self, handler: Callable[[str, Dict], None]):
        """Add volatility analysis handler"""
        self.volatility_handlers.append(handler)
    
    def add_structure_handler(self, handler: Callable[[str, Dict], None]):
        """Add structure analysis handler"""
        self.structure_handlers.append(handler)
    
    def get_m1_data(self, symbol: str, limit: int = 50) -> List[Dict]:
        """Get M1 data for a symbol"""
        if symbol in self.m1_buffers:
            return self.m1_buffers[symbol][-limit:] if limit > 0 else self.m1_buffers[symbol]
        return []
    
    def get_volatility_data(self, symbol: str) -> Optional[Dict]:
        """Get latest volatility data for a symbol"""
        # This would be implemented to return cached volatility data
        return None
    
    def get_structure_data(self, symbol: str) -> Optional[Dict]:
        """Get latest structure data for a symbol"""
        # This would be implemented to return cached structure data
        return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get M1 streaming status"""
        return {
            'is_running': self.is_running,
            'is_connected': self.is_connected,
            'symbols': self.config.symbols,
            'buffer_sizes': {symbol: len(buffer) for symbol, buffer in self.m1_buffers.items()},
            'performance_metrics': self.performance_metrics,
            'handlers': {
                'm1_handlers': len(self.m1_handlers),
                'volatility_handlers': len(self.volatility_handlers),
                'structure_handlers': len(self.structure_handlers)
            }
        }
