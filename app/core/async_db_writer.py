"""
Async Database Writer with Circuit Breaker
High-performance async database writer that never blocks the hot path
"""

import asyncio
import aiosqlite
import logging
import time
import threading
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class BreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit is open, blocking operations
    HALF_OPEN = "half_open"  # Testing if service is back

class BreakerType(Enum):
    """Types of circuit breakers"""
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    QUEUE_DEPTH = "queue_depth"
    MEMORY_USAGE = "memory_usage"
    DISK_SPACE = "disk_space"

@dataclass
class BreakerConfig:
    """Configuration for circuit breakers"""
    breaker_type: BreakerType
    threshold: float
    window_size: int = 100  # Number of samples to consider
    timeout_seconds: int = 60  # How long to keep breaker open
    enabled: bool = True

@dataclass
class BreakerStatus:
    """Status of a circuit breaker"""
    state: BreakerState = BreakerState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    next_attempt_time: float = 0.0
    total_requests: int = 0
    recent_failures: deque = field(default_factory=lambda: deque(maxlen=100))

@dataclass
class WriteOperation:
    """Database write operation"""
    operation_type: str  # 'insert', 'update', 'delete', 'batch'
    table_name: str
    data: Dict[str, Any]
    timestamp_ns: int
    priority: int = 0  # Higher priority = more important
    retry_count: int = 0
    max_retries: int = 3

class AsyncDBWriter:
    """
    High-performance async database writer with circuit breakers
    Never blocks the hot path - all I/O is async and batched
    """
    
    def __init__(self, db_path: str, config: Optional[Dict[str, Any]] = None):
        self.db_path = db_path
        self.config = config or self._default_config()
        
        # Write queue and batching
        self.write_queue = asyncio.Queue(maxsize=self.config['max_queue_size'])
        self.batch_size = self.config['batch_size']
        self.batch_timeout_ms = self.config['batch_timeout_ms']
        
        # Circuit breakers
        self.breakers: Dict[BreakerType, BreakerStatus] = {
            breaker_type: BreakerStatus() 
            for breaker_type in BreakerType
        }
        self.breaker_configs: Dict[BreakerType, BreakerConfig] = {
            BreakerType.LATENCY: BreakerConfig(
                BreakerType.LATENCY, 
                threshold=200.0,  # 200ms threshold
                window_size=50
            ),
            BreakerType.ERROR_RATE: BreakerConfig(
                BreakerType.ERROR_RATE,
                threshold=0.1,  # 10% error rate
                window_size=100
            ),
            BreakerType.QUEUE_DEPTH: BreakerConfig(
                BreakerType.QUEUE_DEPTH,
                threshold=0.8,  # 80% of max queue size
                window_size=10
            ),
            BreakerType.MEMORY_USAGE: BreakerConfig(
                BreakerType.MEMORY_USAGE,
                threshold=0.9,  # 90% memory usage
                window_size=5
            ),
            BreakerType.DISK_SPACE: BreakerConfig(
                BreakerType.DISK_SPACE,
                threshold=0.95,  # 95% disk usage
                window_size=5
            )
        }
        
        # Performance tracking
        self.stats = {
            'total_writes': 0,
            'successful_writes': 0,
            'failed_writes': 0,
            'queue_overflows': 0,
            'breaker_triggers': 0,
            'avg_latency_ms': 0.0,
            'max_latency_ms': 0.0,
            'current_queue_size': 0
        }
        
        # Thread safety
        self.lock = threading.RLock()
        self.running = False
        self.writer_task: Optional[asyncio.Task] = None
        
        # Health monitoring
        self.health_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        logger.info(f"AsyncDBWriter initialized for {db_path}")
    
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration"""
        return {
            'max_queue_size': 10000,
            'batch_size': 100,
            'batch_timeout_ms': 100,
            'connection_pool_size': 5,
            'sqlite_optimizations': {
                'journal_mode': 'WAL',
                'synchronous': 'NORMAL',
                'temp_store': 'MEMORY',
                'cache_size': -100000,  # 100MB cache
                'mmap_size': 268435456,  # 256MB mmap
                'page_size': 4096
            },
            'retry_config': {
                'max_retries': 3,
                'retry_delay_ms': 100,
                'exponential_backoff': True
            }
        }
    
    async def start(self):
        """Start the async database writer"""
        if self.running:
            logger.warning("AsyncDBWriter already running")
            return
        
        self.running = True
        
        # Start the writer task
        self.writer_task = asyncio.create_task(self._writer_loop())
        
        # Start health monitoring
        asyncio.create_task(self._health_monitoring_loop())
        
        logger.info("AsyncDBWriter started")
    
    async def stop(self):
        """Stop the async database writer"""
        if not self.running:
            return
        
        self.running = False
        
        # Wait for writer task to complete
        if self.writer_task:
            await self.writer_task
        
        # Process remaining queue items
        await self._drain_queue()
        
        logger.info("AsyncDBWriter stopped")
    
    async def write_async(self, operation: WriteOperation) -> bool:
        """
        Queue a write operation asynchronously
        Returns True if queued successfully, False if circuit breaker is open
        """
        # Check circuit breakers
        if not self._check_breakers():
            self.stats['breaker_triggers'] += 1
            logger.warning("Circuit breaker is open, dropping write operation")
            return False
        
        try:
            # Add to queue
            await self.write_queue.put(operation)
            self.stats['total_writes'] += 1
            self.stats['current_queue_size'] = self.write_queue.qsize()
            
            return True
            
        except asyncio.QueueFull:
            self.stats['queue_overflows'] += 1
            logger.warning("Write queue is full, dropping operation")
            return False
    
    def write_sync(self, operation: WriteOperation) -> bool:
        """
        Queue a write operation synchronously (non-blocking)
        Returns True if queued successfully, False otherwise
        """
        # Check circuit breakers
        if not self._check_breakers():
            self.stats['breaker_triggers'] += 1
            return False
        
        try:
            # Try to put in queue without blocking
            self.write_queue.put_nowait(operation)
            self.stats['total_writes'] += 1
            self.stats['current_queue_size'] = self.write_queue.qsize()
            
            return True
            
        except asyncio.QueueFull:
            self.stats['queue_overflows'] += 1
            return False
    
    def _check_breakers(self) -> bool:
        """Check if any circuit breakers are open"""
        current_time = time.time()
        
        for breaker_type, status in self.breakers.items():
            config = self.breaker_configs[breaker_type]
            
            if not config.enabled:
                continue
            
            # Check if breaker should be reset
            if status.state == BreakerState.OPEN:
                if current_time >= status.next_attempt_time:
                    status.state = BreakerState.HALF_OPEN
                    logger.info(f"Circuit breaker {breaker_type.value} moved to HALF_OPEN")
            
            # Check breaker conditions
            if status.state == BreakerState.OPEN:
                return False
            
            # Check specific breaker conditions
            if self._should_trigger_breaker(breaker_type, status, config):
                status.state = BreakerState.OPEN
                status.last_failure_time = current_time
                status.next_attempt_time = current_time + config.timeout_seconds
                logger.warning(f"Circuit breaker {breaker_type.value} triggered")
                return False
        
        return True
    
    def _should_trigger_breaker(self, breaker_type: BreakerType, status: BreakerStatus, config: BreakerConfig) -> bool:
        """Check if a specific breaker should trigger"""
        if len(status.recent_failures) < config.window_size:
            return False
        
        if breaker_type == BreakerType.ERROR_RATE:
            failure_rate = len(status.recent_failures) / max(status.total_requests, 1)
            return failure_rate > config.threshold
        
        elif breaker_type == BreakerType.QUEUE_DEPTH:
            queue_ratio = self.stats['current_queue_size'] / self.config['max_queue_size']
            return queue_ratio > config.threshold
        
        elif breaker_type == BreakerType.LATENCY:
            if status.recent_failures:
                avg_latency = sum(status.recent_failures) / len(status.recent_failures)
                return avg_latency > config.threshold
        
        elif breaker_type == BreakerType.MEMORY_USAGE:
            # This would need system monitoring integration
            return False
        
        elif breaker_type == BreakerType.DISK_SPACE:
            # This would need system monitoring integration
            return False
        
        return False
    
    async def _writer_loop(self):
        """Main writer loop - processes queued operations"""
        batch = []
        last_batch_time = time.perf_counter_ns()
        
        while self.running:
            try:
                # Try to get operations with timeout
                try:
                    operation = await asyncio.wait_for(
                        self.write_queue.get(), 
                        timeout=self.batch_timeout_ms / 1000.0
                    )
                    batch.append(operation)
                except asyncio.TimeoutError:
                    # Timeout - process batch if we have operations
                    if batch:
                        await self._process_batch(batch)
                        batch = []
                        last_batch_time = time.perf_counter_ns()
                    continue
                
                # Check if we should process batch
                current_time = time.perf_counter_ns()
                should_process = (
                    len(batch) >= self.batch_size or
                    (current_time - last_batch_time) >= (self.batch_timeout_ms * 1_000_000)
                )
                
                if should_process:
                    await self._process_batch(batch)
                    batch = []
                    last_batch_time = current_time
                
            except Exception as e:
                logger.error(f"Error in writer loop: {e}")
                await asyncio.sleep(0.1)  # Brief pause on error
    
    async def _process_batch(self, batch: List[WriteOperation]):
        """Process a batch of write operations"""
        if not batch:
            return
        
        start_time = time.perf_counter_ns()
        
        try:
            # Group operations by table for efficiency
            operations_by_table = {}
            for op in batch:
                if op.table_name not in operations_by_table:
                    operations_by_table[op.table_name] = []
                operations_by_table[op.table_name].append(op)
            
            # Execute operations
            conn = await self._get_connection()
            try:
                for table_name, operations in operations_by_table.items():
                    await self._execute_table_operations(conn, table_name, operations)
                
                await conn.commit()
            finally:
                await conn.close()
            
            # Update statistics
            self.stats['successful_writes'] += len(batch)
            
            # Update circuit breaker status
            end_time = time.perf_counter_ns()
            latency_ms = (end_time - start_time) / 1_000_000
            self._update_breaker_stats(latency_ms, True)
            
        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            self.stats['failed_writes'] += len(batch)
            self._update_breaker_stats(0, False)
    
    async def _execute_table_operations(self, conn: aiosqlite.Connection, table_name: str, operations: List[WriteOperation]):
        """Execute operations for a specific table"""
        for operation in operations:
            try:
                if operation.operation_type == 'insert':
                    await self._execute_insert(conn, table_name, operation.data)
                elif operation.operation_type == 'update':
                    await self._execute_update(conn, table_name, operation.data)
                elif operation.operation_type == 'delete':
                    await self._execute_delete(conn, table_name, operation.data)
                elif operation.operation_type == 'batch':
                    await self._execute_batch(conn, table_name, operation.data)
                
            except Exception as e:
                logger.error(f"Error executing {operation.operation_type} for {table_name}: {e}")
                # Retry logic could be added here
    
    async def _execute_insert(self, conn: aiosqlite.Connection, table_name: str, data: Dict[str, Any]):
        """Execute insert operation"""
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data.keys()])
        values = list(data.values())
        
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        await conn.execute(query, values)
    
    async def _execute_update(self, conn: aiosqlite.Connection, table_name: str, data: Dict[str, Any]):
        """Execute update operation"""
        # This would need more sophisticated logic for WHERE clauses
        # For now, simplified implementation
        pass
    
    async def _execute_delete(self, conn: aiosqlite.Connection, table_name: str, data: Dict[str, Any]):
        """Execute delete operation"""
        # This would need more sophisticated logic for WHERE clauses
        # For now, simplified implementation
        pass
    
    async def _execute_batch(self, conn: aiosqlite.Connection, table_name: str, data: Dict[str, Any]):
        """Execute batch operation"""
        # This would handle bulk operations
        pass
    
    async def _get_connection(self) -> aiosqlite.Connection:
        """Get optimized database connection"""
        conn = await aiosqlite.connect(self.db_path)
        
        # Apply SQLite optimizations
        optimizations = self.config['sqlite_optimizations']
        for pragma, value in optimizations.items():
            await conn.execute(f"PRAGMA {pragma}={value}")
        
        return conn
    
    def _update_breaker_stats(self, latency_ms: float, success: bool):
        """Update circuit breaker statistics"""
        for breaker_type, status in self.breakers.items():
            status.total_requests += 1
            
            if not success:
                status.failure_count += 1
                status.recent_failures.append(time.time())
            else:
                if breaker_type == BreakerType.LATENCY:
                    status.recent_failures.append(latency_ms)
    
    async def _health_monitoring_loop(self):
        """Monitor system health and update circuit breakers"""
        while self.running:
            try:
                # Update memory usage breaker
                await self._check_memory_usage()
                
                # Update disk space breaker
                await self._check_disk_space()
                
                # Notify health callbacks
                health_data = {
                    'queue_size': self.stats['current_queue_size'],
                    'success_rate': self.stats['successful_writes'] / max(self.stats['total_writes'], 1),
                    'breaker_states': {bt.value: bs.state.value for bt, bs in self.breakers.items()}
                }
                
                for callback in self.health_callbacks:
                    try:
                        callback(health_data)
                    except Exception as e:
                        logger.error(f"Health callback error: {e}")
                
                await asyncio.sleep(1.0)  # Check every second
                
            except Exception as e:
                logger.error(f"Error in health monitoring: {e}")
                await asyncio.sleep(5.0)
    
    async def _check_memory_usage(self):
        """Check system memory usage"""
        try:
            import psutil
            memory_percent = psutil.virtual_memory().percent / 100.0
            
            status = self.breakers[BreakerType.MEMORY_USAGE]
            if memory_percent > self.breaker_configs[BreakerType.MEMORY_USAGE].threshold:
                status.recent_failures.append(memory_percent)
            else:
                status.recent_failures.append(0.0)  # Success
                
        except ImportError:
            pass  # psutil not available
        except Exception as e:
            logger.error(f"Error checking memory usage: {e}")
    
    async def _check_disk_space(self):
        """Check disk space usage"""
        try:
            import shutil
            total, used, free = shutil.disk_usage(self.db_path)
            disk_percent = used / total
            
            status = self.breakers[BreakerType.DISK_SPACE]
            if disk_percent > self.breaker_configs[BreakerType.DISK_SPACE].threshold:
                status.recent_failures.append(disk_percent)
            else:
                status.recent_failures.append(0.0)  # Success
                
        except Exception as e:
            logger.error(f"Error checking disk space: {e}")
    
    async def _drain_queue(self):
        """Drain remaining operations from queue"""
        logger.info("Draining write queue...")
        
        while not self.write_queue.empty():
            try:
                operation = self.write_queue.get_nowait()
                # Process remaining operations
                await self._process_batch([operation])
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.error(f"Error draining queue: {e}")
    
    def add_health_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add health monitoring callback"""
        self.health_callbacks.append(callback)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get writer statistics"""
        with self.lock:
            return {
                'stats': dict(self.stats),
                'breakers': {
                    bt.value: {
                        'state': bs.state.value,
                        'failure_count': bs.failure_count,
                        'total_requests': bs.total_requests
                    }
                    for bt, bs in self.breakers.items()
                },
                'config': self.config
            }
    
    def get_breaker_status(self) -> Dict[str, Any]:
        """Get circuit breaker status"""
        return {
            breaker_type.value: {
                'state': status.state.value,
                'failure_count': status.failure_count,
                'total_requests': status.total_requests,
                'last_failure_time': status.last_failure_time,
                'next_attempt_time': status.next_attempt_time
            }
            for breaker_type, status in self.breakers.items()
        }
