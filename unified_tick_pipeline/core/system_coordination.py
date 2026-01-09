"""
System Coordination for Unified Tick Pipeline
Hierarchical control matrix and thread prioritization for system coordination
"""

import asyncio
import logging
import psutil
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor
import queue

logger = logging.getLogger(__name__)

class SystemPriority(Enum):
    """System priority levels"""
    CRITICAL = 1    # Critical system operations (data feeds, safety)
    HIGH = 2        # High priority operations (DTMS, trading)
    MEDIUM = 3     # Medium priority operations (analysis, monitoring)
    LOW = 4        # Low priority operations (logging, cleanup)
    DEFERRED = 5   # Deferred operations (background tasks)

class ResourceType(Enum):
    """Resource types for monitoring"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    THREADS = "threads"

class SystemState(Enum):
    """System operational states"""
    NORMAL = "normal"
    HIGH_LOAD = "high_load"
    CRITICAL = "critical"
    RECOVERY = "recovery"
    MAINTENANCE = "maintenance"

@dataclass
class ResourceMetrics:
    """System resource metrics"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_io: Dict[str, float]
    thread_count: int
    timestamp: datetime

@dataclass
class TaskRequest:
    """Task execution request"""
    task_id: str
    priority: SystemPriority
    resource_type: ResourceType
    estimated_duration: float  # seconds
    callback: Callable
    parameters: Dict[str, Any]
    deadline: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class ControlMatrixEntry:
    """Hierarchical control matrix entry"""
    component: str
    priority: SystemPriority
    resource_allocation: Dict[ResourceType, float]
    max_concurrent_tasks: int
    defer_conditions: List[str]
    escalation_threshold: float

class SystemCoordination:
    """
    System Coordination for Unified Tick Pipeline
    
    Features:
    - Hierarchical control matrix for action prioritization
    - Thread prioritization and CPU load management
    - Deferred analysis during high load conditions
    - Resource monitoring and automatic adjustments
    - System health monitoring and recovery
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_active = False
        
        # System state
        self.current_state = SystemState.NORMAL
        self.resource_metrics: List[ResourceMetrics] = []
        self.task_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.active_tasks: Dict[str, TaskRequest] = {}
        
        # Thread management
        self.thread_pools: Dict[SystemPriority, ThreadPoolExecutor] = {}
        self.thread_limits: Dict[SystemPriority, int] = {
            SystemPriority.CRITICAL: 4,
            SystemPriority.HIGH: 8,
            SystemPriority.MEDIUM: 12,
            SystemPriority.LOW: 6,
            SystemPriority.DEFERRED: 4
        }
        
        # Control matrix
        self.control_matrix: Dict[str, ControlMatrixEntry] = {}
        self._initialize_control_matrix()
        
        # Resource thresholds
        self.resource_thresholds = {
            'cpu_high': 85.0,  # Increased from 80% to 85%
            'cpu_critical': 98.0,  # Increased from 95% to 98% to reduce false positives
            'memory_high': 85.0,
            'memory_critical': 95.0,
            'disk_high': 98.0,  # Increased to 98% to reduce false positives
            'disk_critical': 99.0  # Only trigger at 99% disk usage
        }
        
        # Performance metrics
        self.performance_metrics = {
            'tasks_processed': 0,
            'tasks_deferred': 0,
            'tasks_failed': 0,
            'resource_adjustments': 0,
            'state_transitions': 0,
            'error_count': 0,
            'average_task_duration': 0.0,
            'cpu_utilization': 0.0,
            'memory_utilization': 0.0
        }
        
        logger.info("SystemCoordination initialized")
    
    async def initialize(self):
        """Initialize system coordination"""
        try:
            logger.info("🔧 Initializing system coordination...")
            
            # Initialize thread pools
            await self._initialize_thread_pools()
            
            # Start resource monitoring
            await self._start_resource_monitoring()
            
            # Start task processing
            await self._start_task_processing()
            
            # Start system health monitoring
            await self._start_system_health_monitoring()
            
            self.is_active = True
            logger.info("✅ System coordination initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize system coordination: {e}")
            raise
    
    async def stop(self):
        """Stop system coordination"""
        try:
            logger.info("🛑 Stopping system coordination...")
            self.is_active = False
            
            # Shutdown thread pools
            for pool in self.thread_pools.values():
                pool.shutdown(wait=True)
            
            logger.info("✅ System coordination stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping system coordination: {e}")
    
    def _initialize_control_matrix(self):
        """Initialize hierarchical control matrix"""
        self.control_matrix = {
            'data_feeds': ControlMatrixEntry(
                component='data_feeds',
                priority=SystemPriority.CRITICAL,
                resource_allocation={
                    ResourceType.CPU: 0.3,
                    ResourceType.MEMORY: 0.2,
                    ResourceType.NETWORK: 0.8
                },
                max_concurrent_tasks=2,
                defer_conditions=['cpu_high', 'network_issues'],
                escalation_threshold=0.9
            ),
            'dtms_enhancement': ControlMatrixEntry(
                component='dtms_enhancement',
                priority=SystemPriority.HIGH,
                resource_allocation={
                    ResourceType.CPU: 0.25,
                    ResourceType.MEMORY: 0.15,
                    ResourceType.THREADS: 0.3
                },
                max_concurrent_tasks=3,
                defer_conditions=['cpu_high', 'memory_high'],
                escalation_threshold=0.8
            ),
            'chatgpt_integration': ControlMatrixEntry(
                component='chatgpt_integration',
                priority=SystemPriority.MEDIUM,
                resource_allocation={
                    ResourceType.CPU: 0.2,
                    ResourceType.MEMORY: 0.3,
                    ResourceType.THREADS: 0.2
                },
                max_concurrent_tasks=5,
                defer_conditions=['cpu_high', 'memory_high', 'disk_high'],
                escalation_threshold=0.7
            ),
            'data_retention': ControlMatrixEntry(
                component='data_retention',
                priority=SystemPriority.MEDIUM,
                resource_allocation={
                    ResourceType.CPU: 0.15,
                    ResourceType.MEMORY: 0.2,
                    ResourceType.DISK: 0.6
                },
                max_concurrent_tasks=4,
                defer_conditions=['disk_high', 'memory_high'],
                escalation_threshold=0.6
            ),
            'offset_calibrator': ControlMatrixEntry(
                component='offset_calibrator',
                priority=SystemPriority.LOW,
                resource_allocation={
                    ResourceType.CPU: 0.1,
                    ResourceType.MEMORY: 0.1,
                    ResourceType.THREADS: 0.1
                },
                max_concurrent_tasks=2,
                defer_conditions=['cpu_high'],
                escalation_threshold=0.5
            ),
            'm5_volatility_bridge': ControlMatrixEntry(
                component='m5_volatility_bridge',
                priority=SystemPriority.LOW,
                resource_allocation={
                    ResourceType.CPU: 0.1,
                    ResourceType.MEMORY: 0.15,
                    ResourceType.THREADS: 0.1
                },
                max_concurrent_tasks=2,
                defer_conditions=['cpu_high', 'memory_high'],
                escalation_threshold=0.5
            )
        }
    
    async def _initialize_thread_pools(self):
        """Initialize thread pools for different priority levels"""
        try:
            for priority in SystemPriority:
                max_workers = self.thread_limits[priority]
                self.thread_pools[priority] = ThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix=f"{priority.name.lower()}_pool"
                )
            
            logger.info("✅ Thread pools initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing thread pools: {e}")
    
    async def _start_resource_monitoring(self):
        """Start resource monitoring"""
        try:
            # Start resource monitoring task
            asyncio.create_task(self._resource_monitoring_loop())
            
            logger.info("✅ Resource monitoring started")
            
        except Exception as e:
            logger.error(f"❌ Error starting resource monitoring: {e}")
    
    async def _start_task_processing(self):
        """Start task processing"""
        try:
            # Start task processing task
            asyncio.create_task(self._task_processing_loop())
            
            logger.info("✅ Task processing started")
            
        except Exception as e:
            logger.error(f"❌ Error starting task processing: {e}")
    
    async def _start_system_health_monitoring(self):
        """Start system health monitoring"""
        try:
            # Start system health monitoring task
            asyncio.create_task(self._system_health_monitoring_loop())
            
            logger.info("✅ System health monitoring started")
            
        except Exception as e:
            logger.error(f"❌ Error starting system health monitoring: {e}")
    
    async def _resource_monitoring_loop(self):
        """Resource monitoring loop"""
        while self.is_active:
            try:
                # Collect resource metrics
                metrics = await self._collect_resource_metrics()
                self.resource_metrics.append(metrics)
                
                # Keep only recent metrics (last 100)
                if len(self.resource_metrics) > 100:
                    self.resource_metrics = self.resource_metrics[-100:]
                
                # Update performance metrics
                self.performance_metrics['cpu_utilization'] = metrics.cpu_percent
                self.performance_metrics['memory_utilization'] = metrics.memory_percent
                
                # Check for resource thresholds
                await self._check_resource_thresholds(metrics)
                
                await asyncio.sleep(5)  # Monitor every 5 seconds
                
            except Exception as e:
                logger.error(f"❌ Error in resource monitoring loop: {e}")
                await asyncio.sleep(1)
    
    async def _collect_resource_metrics(self) -> ResourceMetrics:
        """Collect current resource metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Network I/O
            network_io = psutil.net_io_counters()
            network_io_dict = {
                'bytes_sent': network_io.bytes_sent,
                'bytes_recv': network_io.bytes_recv,
                'packets_sent': network_io.packets_sent,
                'packets_recv': network_io.packets_recv
            }
            
            # Thread count
            thread_count = threading.active_count()
            
            return ResourceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_percent=disk_percent,
                network_io=network_io_dict,
                thread_count=thread_count,
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"❌ Error collecting resource metrics: {e}")
            return ResourceMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                disk_percent=0.0,
                network_io={},
                thread_count=0,
                timestamp=datetime.now(timezone.utc)
            )
    
    async def _check_resource_thresholds(self, metrics: ResourceMetrics):
        """Check resource thresholds and adjust system state"""
        try:
            # Check CPU thresholds
            if metrics.cpu_percent >= self.resource_thresholds['cpu_critical']:
                await self._handle_critical_cpu_load()
            elif metrics.cpu_percent >= self.resource_thresholds['cpu_high']:
                await self._handle_high_cpu_load()
            
            # Check memory thresholds
            if metrics.memory_percent >= self.resource_thresholds['memory_critical']:
                await self._handle_critical_memory_load()
            elif metrics.memory_percent >= self.resource_thresholds['memory_high']:
                await self._handle_high_memory_load()
            
            # Check disk thresholds
            if metrics.disk_percent >= self.resource_thresholds['disk_critical']:
                await self._handle_critical_disk_load()
            elif metrics.disk_percent >= self.resource_thresholds['disk_high']:
                await self._handle_high_disk_load()
            
        except Exception as e:
            logger.error(f"❌ Error checking resource thresholds: {e}")
    
    async def _handle_critical_cpu_load(self):
        """Handle critical CPU load"""
        try:
            # Add cooldown to prevent rapid state changes
            import time
            current_time = time.time()
            last_critical = self.performance_metrics.get('last_critical_cpu', 0)
            
            if current_time - last_critical < 120:  # 2 minutes cooldown
                logger.debug("⏳ Critical CPU handling on cooldown, skipping...")
                return
            
            self.performance_metrics['last_critical_cpu'] = current_time
            
            if self.current_state != SystemState.CRITICAL:
                self.current_state = SystemState.CRITICAL
                self.performance_metrics['state_transitions'] += 1
                logger.warning("🚨 Critical CPU load detected - entering critical state")
                
                # Defer all non-critical tasks
                await self._defer_non_critical_tasks()
                
                # Implement aggressive CPU reduction
                await self._aggressive_cpu_reduction()
                
        except Exception as e:
            logger.error(f"❌ Error handling critical CPU load: {e}")
    
    async def _aggressive_cpu_reduction(self):
        """Aggressive CPU reduction measures"""
        try:
            logger.info("🔧 Implementing aggressive CPU reduction...")
            
            # Increase all sleep intervals significantly
            if hasattr(self, 'monitoring_interval'):
                self.monitoring_interval = min(self.monitoring_interval * 2, 15.0)
                logger.debug(f"📉 Increased monitoring interval to {self.monitoring_interval}s")
            
            # Reduce task processing frequency
            if hasattr(self, 'task_processor'):
                self.task_processor.processing_interval = min(
                    self.task_processor.processing_interval * 2, 20.0
                )
                logger.debug(f"📉 Increased task processing interval to {self.task_processor.processing_interval}s")
            
            # Force garbage collection
            import gc
            gc.collect()
            logger.debug("🧹 Forced garbage collection")
            
        except Exception as e:
            logger.error(f"❌ Error in aggressive CPU reduction: {e}")
    
    async def _handle_high_cpu_load(self):
        """Handle high CPU load"""
        try:
            if self.current_state == SystemState.NORMAL:
                self.current_state = SystemState.HIGH_LOAD
                self.performance_metrics['state_transitions'] += 1
                logger.warning("⚠️ High CPU load detected - entering high load state")
                
                # Defer medium and low priority tasks
                await self._defer_medium_low_priority_tasks()
                
        except Exception as e:
            logger.error(f"❌ Error handling high CPU load: {e}")
    
    async def _handle_critical_memory_load(self):
        """Handle critical memory load"""
        try:
            logger.warning("🚨 Critical memory load detected")
            
            # Trigger memory cleanup
            await self._trigger_memory_cleanup()
            
        except Exception as e:
            logger.error(f"❌ Error handling critical memory load: {e}")
    
    async def _handle_high_memory_load(self):
        """Handle high memory load"""
        try:
            logger.warning("⚠️ High memory load detected")
            
            # Trigger memory optimization
            await self._trigger_memory_optimization()
            
        except Exception as e:
            logger.error(f"❌ Error handling high memory load: {e}")
    
    async def _handle_critical_disk_load(self):
        """Handle critical disk load"""
        try:
            logger.warning("🚨 Critical disk load detected")
            
            # Trigger disk cleanup
            await self._trigger_disk_cleanup()
            
        except Exception as e:
            logger.error(f"❌ Error handling critical disk load: {e}")
    
    async def _handle_high_disk_load(self):
        """Handle high disk load"""
        try:
            # Check if we recently ran disk optimization (cooldown of 5 minutes)
            import time
            current_time = time.time()
            last_optimization = self.performance_metrics.get('last_disk_optimization', 0)
            
            if current_time - last_optimization < 300:  # 5 minutes cooldown
                logger.debug("⏳ Disk optimization on cooldown, skipping...")
                return
            
            logger.warning("⚠️ High disk load detected")
            
            # Update last optimization time
            self.performance_metrics['last_disk_optimization'] = current_time
            
            # Trigger disk optimization
            await self._trigger_disk_optimization()
            
        except Exception as e:
            logger.error(f"❌ Error handling high disk load: {e}")
    
    async def _defer_non_critical_tasks(self):
        """Defer all non-critical tasks"""
        try:
            # Defer all tasks except CRITICAL priority
            for task_id, task in list(self.active_tasks.items()):
                if task.priority != SystemPriority.CRITICAL:
                    await self._defer_task(task_id)
            
            self.performance_metrics['tasks_deferred'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error deferring non-critical tasks: {e}")
    
    async def _defer_medium_low_priority_tasks(self):
        """Defer medium and low priority tasks"""
        try:
            # Defer MEDIUM and LOW priority tasks
            for task_id, task in list(self.active_tasks.items()):
                if task.priority in [SystemPriority.MEDIUM, SystemPriority.LOW]:
                    await self._defer_task(task_id)
            
            self.performance_metrics['tasks_deferred'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error deferring medium/low priority tasks: {e}")
    
    async def _defer_task(self, task_id: str):
        """Defer a specific task"""
        try:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                
                # Move task to deferred queue
                task.priority = SystemPriority.DEFERRED
                self.task_queue.put((task.priority.value, task_id, task))
                
                # Remove from active tasks
                del self.active_tasks[task_id]
                
                logger.debug(f"📋 Task {task_id} deferred")
                
        except Exception as e:
            logger.error(f"❌ Error deferring task {task_id}: {e}")
    
    async def _task_processing_loop(self):
        """Task processing loop"""
        while self.is_active:
            try:
                # Process tasks from queue
                if not self.task_queue.empty():
                    priority, task_id, task = self.task_queue.get_nowait()
                    
                    # Check if task can be executed based on current system state
                    if await self._can_execute_task(task):
                        await self._execute_task(task)
                    else:
                        # Put task back in queue
                        self.task_queue.put((priority, task_id, task))
                
                await asyncio.sleep(0.1)  # Small delay to prevent busy waiting
                
            except Exception as e:
                logger.error(f"❌ Error in task processing loop: {e}")
                await asyncio.sleep(1)
    
    async def _can_execute_task(self, task: TaskRequest) -> bool:
        """Check if task can be executed based on current system state"""
        try:
            # Check system state
            if self.current_state == SystemState.CRITICAL and task.priority != SystemPriority.CRITICAL:
                return False
            
            if self.current_state == SystemState.HIGH_LOAD and task.priority in [SystemPriority.MEDIUM, SystemPriority.LOW]:
                return False
            
            # Check resource availability
            if not await self._check_resource_availability(task):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking task execution capability: {e}")
            return False
    
    async def _check_resource_availability(self, task: TaskRequest) -> bool:
        """Check if resources are available for task execution"""
        try:
            if not self.resource_metrics:
                return True
            
            current_metrics = self.resource_metrics[-1]
            
            # Check CPU availability
            if current_metrics.cpu_percent > 90:
                return False
            
            # Check memory availability
            if current_metrics.memory_percent > 90:
                return False
            
            # Check thread availability
            if current_metrics.thread_count > 50:  # Arbitrary limit
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking resource availability: {e}")
            return False
    
    async def _execute_task(self, task: TaskRequest):
        """Execute a task"""
        try:
            start_time = time.time()
            
            # Add to active tasks
            self.active_tasks[task.task_id] = task
            
            # Execute task in appropriate thread pool
            pool = self.thread_pools[task.priority]
            future = pool.submit(self._run_task, task)
            
            # Wait for completion with timeout
            try:
                result = future.result(timeout=task.estimated_duration * 2)
                
                # Calculate duration
                duration = time.time() - start_time
                self.performance_metrics['average_task_duration'] = (
                    (self.performance_metrics['average_task_duration'] * self.performance_metrics['tasks_processed'] + duration) /
                    (self.performance_metrics['tasks_processed'] + 1)
                )
                
                # Remove from active tasks
                if task.task_id in self.active_tasks:
                    del self.active_tasks[task.task_id]
                
                self.performance_metrics['tasks_processed'] += 1
                
            except Exception as e:
                logger.error(f"❌ Task {task.task_id} failed: {e}")
                self.performance_metrics['tasks_failed'] += 1
                
                # Retry if within limits
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    self.task_queue.put((task.priority.value, task.task_id, task))
                else:
                    logger.error(f"❌ Task {task.task_id} exceeded max retries")
            
        except Exception as e:
            logger.error(f"❌ Error executing task {task.task_id}: {e}")
            self.performance_metrics['error_count'] += 1
    
    def _run_task(self, task: TaskRequest):
        """Run a task (synchronous)"""
        try:
            # Execute the task callback
            if asyncio.iscoroutinefunction(task.callback):
                # Handle async callbacks
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(task.callback(**task.parameters))
                finally:
                    loop.close()
            else:
                # Handle sync callbacks
                return task.callback(**task.parameters)
                
        except Exception as e:
            logger.error(f"❌ Error running task {task.task_id}: {e}")
            raise
    
    async def _system_health_monitoring_loop(self):
        """System health monitoring loop"""
        while self.is_active:
            try:
                # Check system health
                await self._check_system_health()
                
                # Adjust system parameters based on health
                await self._adjust_system_parameters()
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"❌ Error in system health monitoring loop: {e}")
                await asyncio.sleep(5)
    
    async def _check_system_health(self):
        """Check overall system health"""
        try:
            if not self.resource_metrics:
                return
            
            # Get recent metrics (last 5 minutes)
            recent_metrics = [m for m in self.resource_metrics 
                            if (datetime.now(timezone.utc) - m.timestamp).total_seconds() < 300]
            
            if not recent_metrics:
                return
            
            # Calculate average metrics
            avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
            avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
            avg_disk = sum(m.disk_percent for m in recent_metrics) / len(recent_metrics)
            
            # Determine system state based on averages
            if avg_cpu < 50 and avg_memory < 70 and avg_disk < 80:
                if self.current_state != SystemState.NORMAL:
                    self.current_state = SystemState.NORMAL
                    self.performance_metrics['state_transitions'] += 1
                    logger.info("✅ System returned to normal state")
            
        except Exception as e:
            logger.error(f"❌ Error checking system health: {e}")
    
    async def _adjust_system_parameters(self):
        """Adjust system parameters based on current state"""
        try:
            if self.current_state == SystemState.CRITICAL:
                # Reduce thread limits for all pools
                for priority in SystemPriority:
                    if priority != SystemPriority.CRITICAL:
                        self.thread_limits[priority] = max(1, self.thread_limits[priority] // 2)
                
                self.performance_metrics['resource_adjustments'] += 1
                
            elif self.current_state == SystemState.HIGH_LOAD:
                # Reduce thread limits for medium/low priority pools
                for priority in [SystemPriority.MEDIUM, SystemPriority.LOW]:
                    self.thread_limits[priority] = max(1, self.thread_limits[priority] // 2)
                
                self.performance_metrics['resource_adjustments'] += 1
                
        except Exception as e:
            logger.error(f"❌ Error adjusting system parameters: {e}")
    
    # Resource cleanup methods
    async def _trigger_memory_cleanup(self):
        """Trigger memory cleanup"""
        try:
            logger.info("🧹 Triggering memory cleanup...")
            # Implementation would trigger garbage collection, cache cleanup, etc.
            import gc
            gc.collect()
            
        except Exception as e:
            logger.error(f"❌ Error triggering memory cleanup: {e}")
    
    async def _trigger_memory_optimization(self):
        """Trigger memory optimization"""
        try:
            logger.info("🔧 Triggering memory optimization...")
            # Implementation would optimize memory usage
            
        except Exception as e:
            logger.error(f"❌ Error triggering memory optimization: {e}")
    
    async def _trigger_disk_cleanup(self):
        """Trigger disk cleanup"""
        try:
            logger.info("🧹 Triggering disk cleanup...")
            # Implementation would clean up temporary files, logs, etc.
            
        except Exception as e:
            logger.error(f"❌ Error triggering disk cleanup: {e}")
    
    async def _trigger_disk_optimization(self):
        """Trigger disk optimization"""
        try:
            logger.info("🔧 Triggering disk optimization...")
            
            # Clean old log files (keep last 3 days)
            await self._cleanup_old_logs()
            
            # Clean old database records (keep last 7 days)
            await self._cleanup_old_database_records()
            
            # Vacuum databases to reclaim space
            await self._vacuum_databases()
            
            logger.info("✅ Disk optimization completed")
            
        except Exception as e:
            logger.error(f"❌ Error triggering disk optimization: {e}")
    
    async def _cleanup_old_logs(self):
        """Clean old log files"""
        try:
            from pathlib import Path
            from datetime import datetime, timedelta
            
            data_dir = Path("data")
            cutoff_date = datetime.now() - timedelta(days=3)
            
            log_files = list(data_dir.rglob("*.log*"))
            cleaned_count = 0
            
            for log_file in log_files:
                try:
                    file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if file_time < cutoff_date:
                        log_file.unlink()
                        cleaned_count += 1
                except Exception:
                    continue
            
            if cleaned_count > 0:
                logger.info(f"🧹 Cleaned {cleaned_count} old log files")
                
        except Exception as e:
            logger.error(f"Error cleaning logs: {e}")
    
    async def _cleanup_old_database_records(self):
        """Clean old database records"""
        try:
            import sqlite3
            from pathlib import Path
            from datetime import datetime, timedelta
            
            cutoff_timestamp = int((datetime.now() - timedelta(days=7)).timestamp())
            
            # Clean tick data database
            tick_db = Path("data/unified_tick_pipeline/tick_data.db")
            if tick_db.exists():
                conn = sqlite3.connect(str(tick_db))
                cursor = conn.cursor()
                
                # Clean old tick records
                cursor.execute("DELETE FROM unified_ticks WHERE timestamp_utc < ?", (cutoff_timestamp,))
                deleted_count = cursor.rowcount
                
                if deleted_count > 0:
                    logger.info(f"🧹 Cleaned {deleted_count:,} old tick records")
                
                conn.commit()
                conn.close()
                
        except Exception as e:
            logger.error(f"Error cleaning database records: {e}")
    
    async def _vacuum_databases(self):
        """Vacuum databases to reclaim space"""
        try:
            import sqlite3
            from pathlib import Path
            
            # List of databases to vacuum
            databases = [
                "data/unified_tick_pipeline/tick_data.db",
                "data/bot.sqlite",
                "data/journal.sqlite",
                "data/recommendations.sqlite"
            ]
            
            for db_path in databases:
                db_file = Path(db_path)
                if db_file.exists():
                    try:
                        conn = sqlite3.connect(str(db_file))
                        cursor = conn.cursor()
                        cursor.execute("VACUUM")
                        conn.close()
                        logger.info(f"🧹 Vacuumed {db_path}")
                    except Exception:
                        continue
                        
        except Exception as e:
            logger.error(f"Error vacuuming databases: {e}")
    
    # Public API methods
    async def submit_task(self, task: TaskRequest) -> bool:
        """Submit a task for execution"""
        try:
            # Add task to queue
            self.task_queue.put((task.priority.value, task.task_id, task))
            
            logger.debug(f"📋 Task {task.task_id} submitted with priority {task.priority.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error submitting task {task.task_id}: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get system coordination status"""
        return {
            'is_active': self.is_active,
            'current_state': self.current_state.value,
            'active_tasks': len(self.active_tasks),
            'queued_tasks': self.task_queue.qsize(),
            'thread_pools': {
                priority.name: {
                    'max_workers': self.thread_limits[priority],
                    'active_threads': pool._threads if hasattr(pool, '_threads') else 0
                } for priority, pool in self.thread_pools.items()
            },
            'control_matrix_entries': len(self.control_matrix),
            'resource_thresholds': self.resource_thresholds,
            'performance_metrics': self.performance_metrics,
            'recent_metrics': self.resource_metrics[-5:] if self.resource_metrics else []
        }
