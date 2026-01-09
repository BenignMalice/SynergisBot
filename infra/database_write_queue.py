"""
Database Write Queue - Phase 0 Implementation
Provides thread-safe database write operations with completion tracking,
priority queuing, persistence, and error recovery.
"""

import sqlite3
import threading
import queue
import logging
import time
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
import os

logger = logging.getLogger(__name__)


class OperationStatus(Enum):
    """Operation status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class OperationPriority(Enum):
    """Operation priority enumeration"""
    HIGH = 1      # Status updates (executed, cancelled)
    MEDIUM = 2    # Zone state updates
    LOW = 3       # Re-evaluation updates


@dataclass
class DatabaseOperation:
    """Represents a database write operation"""
    operation_id: str
    operation_type: str  # "update_status", "update_zone_state", "cancel_plan", "replace_plan", etc.
    plan_id: Optional[str]
    priority: OperationPriority
    data: Dict[str, Any]  # Operation-specific data
    created_at: str
    retry_count: int = 0
    max_retries: int = 3
    status: OperationStatus = OperationStatus.PENDING
    error: Optional[str] = None
    completed_at: Optional[str] = None


class DatabaseWriteQueue:
    """
    Thread-safe database write queue with single writer thread.
    
    Features:
    - Bounded priority queue (maxsize=1000)
    - Operation completion tracking (futures)
    - Queue persistence to disk
    - Operation validation before queuing
    - Retry logic for transient errors
    - Queue monitoring and health checks
    - Writer thread restart on failure
    """
    
    def __init__(
        self,
        db_path: str,
        queue_maxsize: int = 1000,
        writer_timeout: float = 30.0,
        retry_delay_base: float = 1.0,
        persistence_path: Optional[str] = None
    ):
        """
        Initialize database write queue.
        
        Args:
            db_path: Path to SQLite database
            queue_maxsize: Maximum queue size (default 1000)
            writer_timeout: Timeout for writer thread operations (default 30s)
            retry_delay_base: Base delay for exponential backoff (default 1s)
            persistence_path: Path to persistence file (default: data/db_write_queue.json)
        """
        self.db_path = db_path
        self.queue_maxsize = queue_maxsize
        self.writer_timeout = writer_timeout
        self.retry_delay_base = retry_delay_base
        
        # Priority queue: (priority, timestamp, operation)
        # Lower priority number = higher priority
        self._queue = queue.PriorityQueue(maxsize=queue_maxsize)
        
        # Operation tracking
        self._operations: Dict[str, DatabaseOperation] = {}
        self._operations_lock = threading.Lock()
        
        # Completion futures: operation_id -> (event, result, error)
        self._completion_futures: Dict[str, tuple] = {}
        self._futures_lock = threading.Lock()
        
        # Writer thread
        self._writer_thread: Optional[threading.Thread] = None
        self._writer_running = False
        self._writer_lock = threading.Lock()
        
        # Queue persistence
        if persistence_path is None:
            persistence_path = os.path.join("data", "db_write_queue.json")
        self.persistence_path = Path(persistence_path)
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self._stats = {
            "total_queued": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_retried": 0,
            "queue_size": 0,
            "writer_restarts": 0
        }
        self._stats_lock = threading.Lock()
        
        # Counter for queue items to break ties (prevents comparing DatabaseOperation objects)
        self._queue_counter = 0
        self._counter_lock = threading.Lock()
        
        # Start writer thread
        self.start()
        
        # Load persisted operations on startup
        self._load_persisted_operations()
    
    def _get_next_counter(self) -> int:
        """Get next counter value for queue items (thread-safe)"""
        with self._counter_lock:
            self._queue_counter += 1
            return self._queue_counter
    
    def start(self) -> None:
        """Start the writer thread"""
        with self._writer_lock:
            if self._writer_running:
                logger.warning("Writer thread already running")
                return
            
            self._writer_running = True
            self._writer_thread = threading.Thread(
                target=self._writer_loop,
                name="DatabaseWriteQueue-Writer",
                daemon=False  # Non-daemon to persist after main thread exits
            )
            self._writer_thread.start()
            logger.info("Database write queue writer thread started")
    
    def stop(self, timeout: float = 30.0) -> None:
        """Stop the writer thread and flush queue"""
        logger.info("Stopping database write queue...")
        
        with self._writer_lock:
            self._writer_running = False
        
        # Wait for writer thread to finish
        if self._writer_thread and self._writer_thread.is_alive():
            self._writer_thread.join(timeout=timeout)
            if self._writer_thread.is_alive():
                logger.warning("Writer thread did not stop within timeout")
        
        # Persist remaining operations
        self._persist_operations()
        
        logger.info("Database write queue stopped")
    
    def queue_operation(
        self,
        operation_type: str,
        plan_id: Optional[str],
        data: Dict[str, Any],
        priority: OperationPriority = OperationPriority.MEDIUM,
        wait_for_completion: bool = False,
        timeout: float = 30.0
    ) -> str:
        """
        Queue a database write operation.
        
        Args:
            operation_type: Type of operation (e.g., "update_status", "update_zone_state")
            plan_id: Plan ID if operation is plan-specific
            data: Operation-specific data
            priority: Operation priority (default MEDIUM)
            wait_for_completion: Whether to wait for operation to complete
            timeout: Timeout for waiting (default 30s)
        
        Returns:
            operation_id: Unique operation ID
        
        Raises:
            queue.Full: If queue is full and operation is low priority
        """
        # Validate operation before queuing
        if not self._validate_operation(operation_type, plan_id, data):
            raise ValueError(f"Invalid operation: {operation_type} for plan {plan_id}")
        
        # Generate operation ID
        operation_id = str(uuid.uuid4())
        
        # Create operation
        operation = DatabaseOperation(
            operation_id=operation_id,
            operation_type=operation_type,
            plan_id=plan_id,
            priority=priority,
            data=data,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        # Get counter for this operation
        counter = self._get_next_counter()
        
        # Try to queue (non-blocking for high priority, blocking for others)
        try:
            if priority == OperationPriority.HIGH:
                # High priority: non-blocking, raise if full
                self._queue.put_nowait((priority.value, time.time(), counter, operation))
            else:
                # Medium/Low priority: blocking with timeout
                try:
                    self._queue.put((priority.value, time.time(), counter, operation), timeout=1.0)
                except queue.Full:
                    # Queue full - drop low priority, raise for medium
                    if priority == OperationPriority.LOW:
                        logger.warning(f"Queue full, dropping low priority operation: {operation_type}")
                        return operation_id  # Return ID but operation is dropped
                    else:
                        raise queue.Full(f"Queue full, cannot queue {operation_type} operation")
        except queue.Full:
            # For high priority, try to make room by dropping low priority items
            if priority == OperationPriority.HIGH:
                self._drop_low_priority_items(1)
                try:
                    self._queue.put_nowait((priority.value, time.time(), counter, operation))
                except queue.Full:
                    raise queue.Full(f"Queue full even after dropping low priority items")
            else:
                raise
        
        # Track operation
        with self._operations_lock:
            self._operations[operation_id] = operation
        
        # Create completion future
        completion_event = threading.Event()
        with self._futures_lock:
            self._completion_futures[operation_id] = (completion_event, None, None)
        
        # Update statistics
        with self._stats_lock:
            self._stats["total_queued"] += 1
            self._stats["queue_size"] = self._queue.qsize()
        
        # Persist operation
        self._persist_operation(operation)
        
        logger.debug(f"Queued operation {operation_id}: {operation_type} for plan {plan_id}")
        
        # Wait for completion if requested
        if wait_for_completion:
            self.wait_for_operation(operation_id, timeout=timeout)
        
        return operation_id
    
    def wait_for_operation(self, operation_id: str, timeout: float = 30.0) -> bool:
        """
        Wait for an operation to complete.
        
        Args:
            operation_id: Operation ID to wait for
            timeout: Maximum time to wait (default 30s)
        
        Returns:
            True if operation completed successfully, False if failed or timed out
        """
        with self._futures_lock:
            if operation_id not in self._completion_futures:
                logger.warning(f"Operation {operation_id} not found in futures")
                return False
            
            completion_event, result, error = self._completion_futures[operation_id]
        
        # Wait for completion
        if completion_event.wait(timeout=timeout):
            # Operation completed
            with self._futures_lock:
                _, result, error = self._completion_futures.get(operation_id, (None, None, None))
            
            if error:
                logger.warning(f"Operation {operation_id} failed: {error}")
                return False
            return True
        else:
            # Timeout
            logger.warning(f"Operation {operation_id} timed out after {timeout}s")
            return False
    
    def wait_for_plan_writes(self, plan_id: str, timeout: float = 30.0) -> bool:
        """
        Wait for all pending writes for a specific plan to complete.
        
        Args:
            plan_id: Plan ID to wait for
            timeout: Maximum time to wait (default 30s)
        
        Returns:
            True if all operations completed, False if timeout or failure
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Find pending operations for this plan
            pending_ops = []
            with self._operations_lock:
                for op_id, op in self._operations.items():
                    if op.plan_id == plan_id and op.status in [OperationStatus.PENDING, OperationStatus.PROCESSING]:
                        pending_ops.append(op_id)
            
            if not pending_ops:
                # No pending operations
                return True
            
            # Wait for each operation (with remaining timeout)
            remaining_timeout = timeout - (time.time() - start_time)
            if remaining_timeout <= 0:
                break
            
            for op_id in pending_ops:
                if not self.wait_for_operation(op_id, timeout=min(remaining_timeout, 5.0)):
                    return False
                remaining_timeout = timeout - (time.time() - start_time)
                if remaining_timeout <= 0:
                    break
        
        # Check if any operations are still pending
        with self._operations_lock:
            for op_id, op in self._operations.items():
                if op.plan_id == plan_id and op.status in [OperationStatus.PENDING, OperationStatus.PROCESSING]:
                    logger.warning(f"Plan {plan_id} still has pending operations after timeout")
                    return False
        
        return True
    
    def flush_queue_for_plans(self, plan_ids: list[str], timeout: float = 30.0) -> bool:
        """
        Flush queue for specific plans (wait for all their operations to complete).
        
        Args:
            plan_ids: List of plan IDs to flush
            timeout: Maximum time to wait (default 30s)
        
        Returns:
            True if all operations completed, False if timeout
        """
        start_time = time.time()
        
        for plan_id in plan_ids:
            remaining_timeout = timeout - (time.time() - start_time)
            if remaining_timeout <= 0:
                logger.warning(f"Timeout flushing queue for plans")
                return False
            
            if not self.wait_for_plan_writes(plan_id, timeout=remaining_timeout):
                return False
        
        return True
    
    def get_operation_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get operation status"""
        with self._operations_lock:
            operation = self._operations.get(operation_id)
            if not operation:
                return None
            
            return {
                "operation_id": operation.operation_id,
                "operation_type": operation.operation_type,
                "plan_id": operation.plan_id,
                "status": operation.status.value,
                "retry_count": operation.retry_count,
                "error": operation.error,
                "created_at": operation.created_at,
                "completed_at": operation.completed_at
            }
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        with self._stats_lock:
            stats = self._stats.copy()
            stats["queue_size"] = self._queue.qsize()
            stats["pending_operations"] = len([
                op for op in self._operations.values()
                if op.status in [OperationStatus.PENDING, OperationStatus.PROCESSING]
            ])
            return stats
    
    def _validate_operation(self, operation_type: str, plan_id: Optional[str], data: Dict[str, Any]) -> bool:
        """Validate operation before queuing"""
        # Basic validation
        if not operation_type:
            return False
        
        # Operation-specific validation
        if operation_type == "update_status":
            if not plan_id or "status" not in data:
                return False
        elif operation_type == "update_zone_state":
            if not plan_id:
                return False
        elif operation_type == "cancel_plan":
            if not plan_id:
                return False
        elif operation_type == "replace_plan":
            if "old_plan_id" not in data or "new_plan_data" not in data:
                return False
        
        return True
    
    def _drop_low_priority_items(self, count: int) -> int:
        """Drop low priority items from queue to make room"""
        dropped = 0
        temp_items = []
        
        # Remove items from queue
        while not self._queue.empty() and dropped < count:
            try:
                priority, timestamp, counter, operation = self._queue.get_nowait()
                if operation.priority == OperationPriority.LOW:
                    dropped += 1
                    logger.debug(f"Dropped low priority operation: {operation.operation_type}")
                else:
                    temp_items.append((priority, timestamp, counter, operation))
            except queue.Empty:
                break
        
        # Put non-dropped items back
        for item in temp_items:
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                break
        
        return dropped
    
    def _writer_loop(self) -> None:
        """Main writer thread loop"""
        logger.info("Database write queue writer thread started")
        
        while self._writer_running:
            try:
                # Get operation from queue (with timeout to check _writer_running)
                try:
                    priority, timestamp, counter, operation = self._queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Process operation
                self._process_operation(operation)
                
                # Update statistics
                with self._stats_lock:
                    self._stats["queue_size"] = self._queue.qsize()
                
            except Exception as e:
                logger.error(f"Error in writer loop: {e}", exc_info=True)
                # Continue loop - don't let errors kill the thread
                time.sleep(1.0)
        
        logger.info("Database write queue writer thread stopped")
    
    def _process_operation(self, operation: DatabaseOperation) -> None:
        """Process a single database operation"""
        operation_id = operation.operation_id
        
        # Update status to processing
        with self._operations_lock:
            operation.status = OperationStatus.PROCESSING
        
        try:
            # Execute operation
            success = self._execute_operation(operation)
            
            if success:
                # Operation completed
                with self._operations_lock:
                    operation.status = OperationStatus.COMPLETED
                    operation.completed_at = datetime.now(timezone.utc).isoformat()
                
                # Update completion future
                with self._futures_lock:
                    if operation_id in self._completion_futures:
                        event, _, _ = self._completion_futures[operation_id]
                        self._completion_futures[operation_id] = (event, True, None)
                        event.set()
                
                # Update statistics
                with self._stats_lock:
                    self._stats["total_completed"] += 1
                
                # Remove from persistence (completed)
                self._remove_persisted_operation(operation_id)
                
                logger.debug(f"Operation {operation_id} completed: {operation.operation_type}")
            
            else:
                # Operation failed - retry or mark as failed
                if operation.retry_count < operation.max_retries:
                    # Retry
                    operation.retry_count += 1
                    operation.status = OperationStatus.RETRYING
                    
                    # Exponential backoff
                    delay = self.retry_delay_base * (2 ** (operation.retry_count - 1))
                    time.sleep(delay)
                    
                    # Re-queue operation
                    try:
                        counter = self._get_next_counter()
                        self._queue.put_nowait((operation.priority.value, time.time(), counter, operation))
                    except queue.Full:
                        # Queue full - mark as failed
                        operation.status = OperationStatus.FAILED
                        operation.error = "Queue full during retry"
                    
                    with self._stats_lock:
                        self._stats["total_retried"] += 1
                    
                    logger.warning(f"Operation {operation_id} retrying ({operation.retry_count}/{operation.max_retries})")
                
                else:
                    # Max retries exceeded - mark as failed
                    with self._operations_lock:
                        operation.status = OperationStatus.FAILED
                        operation.error = "Max retries exceeded"
                    
                    # Update completion future
                    with self._futures_lock:
                        if operation_id in self._completion_futures:
                            event, _, _ = self._completion_futures[operation_id]
                            error_msg = operation.error or "Operation failed"
                            self._completion_futures[operation_id] = (event, False, error_msg)
                            event.set()
                    
                    # Update statistics
                    with self._stats_lock:
                        self._stats["total_failed"] += 1
                    
                    logger.error(f"Operation {operation_id} failed after {operation.max_retries} retries: {operation.operation_type}")
        
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error processing operation {operation_id}: {e}", exc_info=True)
            
            with self._operations_lock:
                operation.status = OperationStatus.FAILED
                operation.error = str(e)
            
            # Update completion future
            with self._futures_lock:
                if operation_id in self._completion_futures:
                    event, _, _ = self._completion_futures[operation_id]
                    self._completion_futures[operation_id] = (event, False, str(e))
                    event.set()
            
            with self._stats_lock:
                self._stats["total_failed"] += 1
    
    def _execute_operation(self, operation: DatabaseOperation) -> bool:
        """Execute a database operation"""
        try:
            if operation.operation_type == "update_status":
                return self._execute_update_status(operation)
            elif operation.operation_type == "update_zone_state":
                return self._execute_update_zone_state(operation)
            elif operation.operation_type == "cancel_plan":
                return self._execute_cancel_plan(operation)
            elif operation.operation_type == "replace_plan":
                return self._execute_replace_plan(operation)
            else:
                logger.error(f"Unknown operation type: {operation.operation_type}")
                return False
        
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                # Database locked - transient error, will retry
                logger.warning(f"Database locked during {operation.operation_type}: {e}")
                return False
            else:
                # Other operational error - permanent
                logger.error(f"Database operational error during {operation.operation_type}: {e}")
                operation.error = str(e)
                return False
        
        except Exception as e:
            # Other errors - permanent
            logger.error(f"Error executing {operation.operation_type}: {e}", exc_info=True)
            operation.error = str(e)
            return False
    
    def _execute_update_status(self, operation: DatabaseOperation) -> bool:
        """Execute update_status operation"""
        plan_id = operation.plan_id
        data = operation.data
        
        with sqlite3.connect(self.db_path, timeout=self.writer_timeout) as conn:
            updates = []
            params = []
            
            if "status" in data:
                updates.append("status = ?")
                params.append(data["status"])
            
            if "executed_at" in data:
                updates.append("executed_at = ?")
                params.append(data["executed_at"])
            
            if "ticket" in data:
                updates.append("ticket = ?")
                params.append(data["ticket"])
            
            if "cancellation_reason" in data:
                updates.append("cancellation_reason = ?")
                params.append(data["cancellation_reason"])
            
            if "kill_switch_triggered" in data:
                updates.append("kill_switch_triggered = ?")
                params.append(1 if data["kill_switch_triggered"] else 0)
            
            # Phase 3.7: Handle pending_order_ticket
            if "pending_order_ticket" in data:
                updates.append("pending_order_ticket = ?")
                params.append(data["pending_order_ticket"])
            
            if not updates:
                return True  # Nothing to update
            
            params.append(plan_id)
            
            query = f"UPDATE trade_plans SET {', '.join(updates)} WHERE plan_id = ?"
            conn.execute(query, params)
            conn.commit()
            
            return True
    
    def _execute_update_zone_state(self, operation: DatabaseOperation) -> bool:
        """Execute update_zone_state operation"""
        plan_id = operation.plan_id
        data = operation.data
        
        with sqlite3.connect(self.db_path, timeout=self.writer_timeout) as conn:
            updates = []
            params = []
            
            if "zone_entry_tracked" in data:
                updates.append("zone_entry_tracked = ?")
                params.append(data["zone_entry_tracked"])
            
            if "zone_entry_time" in data:
                updates.append("zone_entry_time = ?")
                params.append(data["zone_entry_time"])
            
            if "zone_exit_time" in data:
                updates.append("zone_exit_time = ?")
                params.append(data["zone_exit_time"])
            
            if "level_zone_entry" in data:
                updates.append("level_zone_entry = ?")
                params.append(json.dumps(data["level_zone_entry"]))
            
            if not updates:
                return True  # Nothing to update
            
            params.append(plan_id)
            
            query = f"UPDATE trade_plans SET {', '.join(updates)} WHERE plan_id = ?"
            conn.execute(query, params)
            conn.commit()
            
            return True
    
    def _execute_cancel_plan(self, operation: DatabaseOperation) -> bool:
        """Execute cancel_plan operation"""
        plan_id = operation.plan_id
        data = operation.data
        
        with sqlite3.connect(self.db_path, timeout=self.writer_timeout) as conn:
            updates = ["status = ?"]
            params = ["cancelled"]
            
            if "cancellation_reason" in data:
                updates.append("cancellation_reason = ?")
                params.append(data["cancellation_reason"])
            
            params.append(plan_id)
            
            query = f"UPDATE trade_plans SET {', '.join(updates)} WHERE plan_id = ?"
            conn.execute(query, params)
            conn.commit()
            
            return True
    
    def _execute_replace_plan(self, operation: DatabaseOperation) -> bool:
        """Execute replace_plan operation (composite - atomic)"""
        data = operation.data
        old_plan_id = data["old_plan_id"]
        new_plan_data = data["new_plan_data"]
        
        # Use transaction for atomicity
        with sqlite3.connect(self.db_path, timeout=self.writer_timeout) as conn:
            try:
                # 1. Create new plan
                conn.execute("""
                    INSERT INTO trade_plans 
                    (plan_id, symbol, direction, entry_price, stop_loss, take_profit, volume, 
                     conditions, created_at, created_by, status, expires_at, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_plan_data["plan_id"],
                    new_plan_data["symbol"],
                    new_plan_data["direction"],
                    new_plan_data["entry_price"],
                    new_plan_data["stop_loss"],
                    new_plan_data["take_profit"],
                    new_plan_data["volume"],
                    json.dumps(new_plan_data["conditions"]),
                    new_plan_data.get("created_at", datetime.now(timezone.utc).isoformat()),
                    new_plan_data.get("created_by", "system"),
                    "pending",
                    new_plan_data.get("expires_at"),
                    new_plan_data.get("notes")
                ))
                
                # 2. Link plans (if linking data provided)
                if "link_data" in data:
                    link_data = data["link_data"]
                    # Update new plan with original_plan_id
                    if "original_plan_id" in link_data:
                        conn.execute("""
                            UPDATE trade_plans SET original_plan_id = ? WHERE plan_id = ?
                        """, (link_data["original_plan_id"], new_plan_data["plan_id"]))
                    
                    # Update old plan with replacement_plan_id
                    conn.execute("""
                        UPDATE trade_plans SET replacement_plan_id = ? WHERE plan_id = ?
                    """, (new_plan_data["plan_id"], old_plan_id))
                
                # 3. Cancel old plan
                conn.execute("""
                    UPDATE trade_plans SET status = 'replaced', cancellation_reason = 'Replaced by new plan'
                    WHERE plan_id = ?
                """, (old_plan_id,))
                
                # Commit transaction
                conn.commit()
                return True
            
            except Exception as e:
                # Rollback on error
                conn.rollback()
                raise
    
    def _persist_operation(self, operation: DatabaseOperation) -> None:
        """Persist operation to disk"""
        try:
            # Load existing operations
            persisted_ops = self._load_persisted_operations_dict()
            
            # Add/update operation
            persisted_ops[operation.operation_id] = {
                "operation_id": operation.operation_id,
                "operation_type": operation.operation_type,
                "plan_id": operation.plan_id,
                "priority": operation.priority.value,
                "data": operation.data,
                "created_at": operation.created_at,
                "retry_count": operation.retry_count,
                "max_retries": operation.max_retries,
                "status": operation.status.value
            }
            
            # Save to disk
            with open(self.persistence_path, 'w') as f:
                json.dump(persisted_ops, f, indent=2)
        
        except Exception as e:
            logger.warning(f"Failed to persist operation {operation.operation_id}: {e}")
    
    def _remove_persisted_operation(self, operation_id: str) -> None:
        """Remove operation from persistence"""
        try:
            persisted_ops = self._load_persisted_operations_dict()
            persisted_ops.pop(operation_id, None)
            
            with open(self.persistence_path, 'w') as f:
                json.dump(persisted_ops, f, indent=2)
        
        except Exception as e:
            logger.warning(f"Failed to remove persisted operation {operation_id}: {e}")
    
    def _load_persisted_operations_dict(self) -> Dict[str, Any]:
        """Load persisted operations as dictionary"""
        if not self.persistence_path.exists():
            return {}
        
        try:
            with open(self.persistence_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load persisted operations: {e}")
            return {}
    
    def _load_persisted_operations(self) -> None:
        """Load persisted operations on startup and replay"""
        persisted_ops = self._load_persisted_operations_dict()
        
        if not persisted_ops:
            return
        
        logger.info(f"Loading {len(persisted_ops)} persisted operations on startup")
        
        for op_id, op_data in persisted_ops.items():
            # Skip if already completed
            if op_data.get("status") == "completed":
                continue
            
            # Recreate operation
            operation = DatabaseOperation(
                operation_id=op_data["operation_id"],
                operation_type=op_data["operation_type"],
                plan_id=op_data.get("plan_id"),
                priority=OperationPriority(op_data["priority"]),
                data=op_data["data"],
                created_at=op_data["created_at"],
                retry_count=op_data.get("retry_count", 0),
                max_retries=op_data.get("max_retries", 3),
                status=OperationStatus(op_data.get("status", "pending"))
            )
            
            # Re-queue operation
            try:
                counter = self._get_next_counter()
                self._queue.put_nowait((operation.priority.value, time.time(), counter, operation))
                
                # Track operation
                with self._operations_lock:
                    self._operations[operation.operation_id] = operation
                
                # Create completion future
                completion_event = threading.Event()
                with self._futures_lock:
                    self._completion_futures[operation.operation_id] = (completion_event, None, None)
                
                logger.debug(f"Re-queued persisted operation: {operation.operation_id}")
            
            except queue.Full:
                logger.warning(f"Queue full, cannot replay operation {operation.operation_id}")
    
    def _persist_operations(self) -> None:
        """Persist all pending operations"""
        try:
            persisted_ops = {}
            
            with self._operations_lock:
                for op_id, op in self._operations.items():
                    if op.status in [OperationStatus.PENDING, OperationStatus.PROCESSING, OperationStatus.RETRYING]:
                        persisted_ops[op_id] = {
                            "operation_id": op.operation_id,
                            "operation_type": op.operation_type,
                            "plan_id": op.plan_id,
                            "priority": op.priority.value,
                            "data": op.data,
                            "created_at": op.created_at,
                            "retry_count": op.retry_count,
                            "max_retries": op.max_retries,
                            "status": op.status.value
                        }
            
            with open(self.persistence_path, 'w') as f:
                json.dump(persisted_ops, f, indent=2)
            
            logger.info(f"Persisted {len(persisted_ops)} operations")
        
        except Exception as e:
            logger.error(f"Failed to persist operations: {e}", exc_info=True)
    
    def check_writer_health(self) -> Dict[str, Any]:
        """Check writer thread health"""
        with self._writer_lock:
            is_alive = self._writer_thread is not None and self._writer_thread.is_alive()
            is_running = self._writer_running
        
        health = {
            "writer_thread_alive": is_alive,
            "writer_running": is_running,
            "queue_size": self._queue.qsize(),
            "pending_operations": len([
                op for op in self._operations.values()
                if op.status in [OperationStatus.PENDING, OperationStatus.PROCESSING]
            ])
        }
        
        # Restart writer if dead but should be running
        if not is_alive and is_running:
            logger.warning("Writer thread is dead but should be running - restarting")
            with self._stats_lock:
                self._stats["writer_restarts"] += 1
            self.start()
            health["writer_restarted"] = True
        
        return health

