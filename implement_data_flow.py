#!/usr/bin/env python3
"""
Implement Data Flow from Binance to Database
Creates a working data flow system that stores streaming data
"""

import asyncio
import sqlite3
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import websockets
import aiohttp
import time

logger = logging.getLogger(__name__)

class DataFlowManager:
    """
    Manages data flow from Binance to database
    """
    
    def __init__(self, db_path: str = 'unified_tick_pipeline.db'):
        self.db_path = db_path
        self.is_running = False
        self.websocket = None
        self.db_connection = None
        
        # Performance metrics
        self.metrics = {
            'ticks_received': 0,
            'ticks_stored': 0,
            'errors': 0,
            'last_tick_time': None,
            'start_time': None
        }
        
        # Symbols to monitor
        self.symbols = ['BTCUSDT', 'ETHUSDT']
        
        logger.info("DataFlowManager initialized")
    
    async def start(self) -> bool:
        """Start the data flow system"""
        try:
            logger.info("🚀 Starting data flow system...")
            
            # Initialize database
            if not await self._initialize_database():
                logger.error("❌ Database initialization failed")
                return False
            
            # Start WebSocket connection
            if not await self._start_websocket():
                logger.error("❌ WebSocket connection failed")
                return False
            
            self.is_running = True
            self.metrics['start_time'] = datetime.now(timezone.utc)
            logger.info("✅ Data flow system started")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start data flow system: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the data flow system"""
        try:
            logger.info("🛑 Stopping data flow system...")
            
            self.is_running = False
            
            if self.websocket:
                await self.websocket.close()
            
            if self.db_connection:
                self.db_connection.close()
            
            logger.info("✅ Data flow system stopped")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error stopping data flow system: {e}")
            return False
    
    async def _initialize_database(self) -> bool:
        """Initialize database connection"""
        try:
            logger.info("🗄️ Initializing database connection...")
            
            # Test database connection
            self.db_connection = sqlite3.connect(self.db_path, timeout=30)
            cursor = self.db_connection.cursor()
            
            # Check if tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            if not tables:
                logger.error("❌ No tables found in database")
                return False
            
            logger.info("✅ Database connection initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            return False
    
    async def _start_websocket(self) -> bool:
        """Start WebSocket connection to Binance"""
        try:
            logger.info("📡 Starting WebSocket connection...")
            
            # Create WebSocket URL
            streams = [f"{symbol.lower()}@ticker" for symbol in self.symbols]
            url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"
            
            logger.info(f"🔗 Connecting to: {url}")
            
            # Connect to WebSocket
            self.websocket = await websockets.connect(
                url,
                ping_interval=30,
                ping_timeout=120,
                close_timeout=60,
                open_timeout=120
            )
            
            # Start receiving data
            asyncio.create_task(self._receive_data())
            
            logger.info("✅ WebSocket connection established")
            return True
            
        except Exception as e:
            logger.error(f"❌ WebSocket connection failed: {e}")
            return False
    
    async def _receive_data(self):
        """Receive data from WebSocket"""
        try:
            async for message in self.websocket:
                if not self.is_running:
                    break
                
                try:
                    # Parse message
                    data = json.loads(message)
                    
                    # Extract tick data
                    tick_data = self._extract_tick_data(data)
                    if tick_data:
                        # Store in database
                        await self._store_tick_data(tick_data)
                        
                        # Update metrics
                        self.metrics['ticks_received'] += 1
                        self.metrics['last_tick_time'] = datetime.now(timezone.utc)
                        
                        # Log every 10 ticks
                        if self.metrics['ticks_received'] % 10 == 0:
                            logger.info(f"📊 Received {self.metrics['ticks_received']} ticks")
                
                except json.JSONDecodeError as e:
                    logger.error(f"❌ JSON decode error: {e}")
                    self.metrics['errors'] += 1
                except Exception as e:
                    logger.error(f"❌ Error processing message: {e}")
                    self.metrics['errors'] += 1
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("⚠️ WebSocket connection closed")
        except Exception as e:
            logger.error(f"❌ WebSocket error: {e}")
    
    def _extract_tick_data(self, data: Dict) -> Optional[Dict]:
        """Extract tick data from WebSocket message"""
        try:
            stream = data.get('stream', '')
            if '@' not in stream:
                return None
            
            symbol = stream.split('@')[0].upper()
            tick_data = data.get('data', {})
            
            return {
                'symbol': symbol,
                'price': float(tick_data.get('c', 0)),
                'volume': float(tick_data.get('v', 0)),
                'timestamp': datetime.now(timezone.utc),
                'source': 'binance',
                'bid': float(tick_data.get('b', 0)),
                'ask': float(tick_data.get('a', 0)),
                'spread': float(tick_data.get('a', 0)) - float(tick_data.get('b', 0))
            }
            
        except Exception as e:
            logger.error(f"❌ Error extracting tick data: {e}")
            return None
    
    async def _store_tick_data(self, tick_data: Dict) -> bool:
        """Store tick data in database"""
        try:
            if not self.db_connection:
                return False
            
            cursor = self.db_connection.cursor()
            
            # Insert tick data
            cursor.execute("""
                INSERT INTO unified_ticks 
                (symbol, price, volume, timestamp, source, bid, ask, spread)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tick_data['symbol'],
                tick_data['price'],
                tick_data['volume'],
                tick_data['timestamp'],
                tick_data['source'],
                tick_data['bid'],
                tick_data['ask'],
                tick_data['spread']
            ))
            
            self.db_connection.commit()
            self.metrics['ticks_stored'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error storing tick data: {e}")
            self.metrics['errors'] += 1
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        return {
            'is_running': self.is_running,
            'metrics': self.metrics,
            'symbols': self.symbols,
            'database_connected': self.db_connection is not None,
            'websocket_connected': self.websocket is not None
        }
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            if not self.db_connection:
                return {'error': 'Database not connected'}
            
            cursor = self.db_connection.cursor()
            
            # Get total tick count
            cursor.execute("SELECT COUNT(*) FROM unified_ticks")
            total_ticks = cursor.fetchone()[0]
            
            # Get tick count by symbol
            symbol_counts = {}
            for symbol in self.symbols:
                cursor.execute("SELECT COUNT(*) FROM unified_ticks WHERE symbol = ?", (symbol,))
                symbol_counts[symbol] = cursor.fetchone()[0]
            
            # Get latest tick
            cursor.execute("""
                SELECT symbol, price, timestamp 
                FROM unified_ticks 
                ORDER BY timestamp DESC 
                LIMIT 1
            """)
            latest_tick = cursor.fetchone()
            
            return {
                'total_ticks': total_ticks,
                'symbol_counts': symbol_counts,
                'latest_tick': {
                    'symbol': latest_tick[0] if latest_tick else None,
                    'price': latest_tick[1] if latest_tick else None,
                    'timestamp': latest_tick[2] if latest_tick else None
                }
            }
            
        except Exception as e:
            return {'error': str(e)}

# Test the data flow system
async def test_data_flow():
    """Test the data flow system"""
    print("🔧 TESTING DATA FLOW SYSTEM")
    print("=" * 50)
    
    # Create data flow manager
    manager = DataFlowManager()
    
    # Start the system
    success = await manager.start()
    
    if success:
        print("✅ Data flow system started successfully")
        
        # Let it run for 30 seconds
        print("⏳ Collecting data for 30 seconds...")
        await asyncio.sleep(30)
        
        # Check status
        status = manager.get_status()
        print(f"📊 Status: {status}")
        
        # Check database stats
        stats = manager.get_database_stats()
        print(f"📈 Database stats: {stats}")
        
        # Stop the system
        await manager.stop()
        print("✅ Data flow system stopped")
    else:
        print("❌ Data flow system startup failed")

if __name__ == "__main__":
    asyncio.run(test_data_flow())
