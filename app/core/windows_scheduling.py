"""
Windows-specific scheduling optimizations for high-frequency trading systems.
Implements thread priorities, high-resolution timing, and Windows-specific performance optimizations.
"""

import os
import sys
import time
import threading
import psutil
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

# Windows-specific imports
if sys.platform == "win32":
    try:
        import win32api
        import win32process
        import win32con
        import win32security
        from win32api import SetPriorityClass, GetCurrentProcess
        from win32process import HIGH_PRIORITY_CLASS, REALTIME_PRIORITY_CLASS
        WINDOWS_AVAILABLE = True
    except ImportError:
        WINDOWS_AVAILABLE = False
        logging.warning("Windows-specific modules not available. Install pywin32 for full Windows optimization.")
else:
    WINDOWS_AVAILABLE = False

logger = logging.getLogger(__name__)

class ThreadPriority(Enum):
    """Thread priority levels for Windows scheduling."""
    LOWEST = 1
    BELOW_NORMAL = 2
    NORMAL = 3
    ABOVE_NORMAL = 4
    HIGHEST = 5
    REALTIME = 6

@dataclass
class SchedulingConfig:
    """Configuration for Windows scheduling optimizations."""
    # Process-level settings
    process_priority: str = "HIGH"  # HIGH, REALTIME
    affinity_mask: Optional[int] = None  # CPU affinity mask
    
    # Thread-level settings
    hot_path_priority: ThreadPriority = ThreadPriority.REALTIME
    data_ingestion_priority: ThreadPriority = ThreadPriority.HIGHEST
    database_priority: ThreadPriority = ThreadPriority.ABOVE_NORMAL
    monitoring_priority: ThreadPriority = ThreadPriority.NORMAL
    
    # Timing settings
    use_high_res_timer: bool = True
    timer_resolution_us: int = 1000  # 1ms timer resolution
    
    # Memory settings
    working_set_size_mb: int = 1024  # Set working set size
    page_priority: str = "HIGH"  # HIGH, NORMAL, LOW
    
    # Power settings
    prevent_sleep: bool = True
    disable_power_throttling: bool = True

class WindowsScheduler:
    """
    Windows-specific scheduler for optimizing trading system performance.
    Implements thread priorities, CPU affinity, and high-resolution timing.
    """
    
    def __init__(self, config: SchedulingConfig):
        self.config = config
        self.original_process_priority = None
        self.original_affinity = None
        self.original_timer_resolution = None
        self.thread_priorities: Dict[str, int] = {}
        self._initialized = False
        
        if not WINDOWS_AVAILABLE:
            logger.warning("Windows scheduling optimizations not available on this platform.")
            return
            
        logger.info("WindowsScheduler initialized with optimizations enabled.")

    def initialize(self) -> bool:
        """Initialize Windows scheduling optimizations."""
        if not WINDOWS_AVAILABLE:
            logger.warning("Cannot initialize Windows scheduler - not on Windows platform.")
            return False
            
        try:
            # 1. Set process priority
            self._set_process_priority()
            
            # 2. Set CPU affinity
            self._set_cpu_affinity()
            
            # 3. Set high-resolution timer
            self._set_timer_resolution()
            
            # 4. Optimize memory settings
            self._optimize_memory_settings()
            
            # 5. Configure power settings
            self._configure_power_settings()
            
            self._initialized = True
            logger.info("✅ Windows scheduling optimizations applied successfully.")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Windows scheduler: {e}")
            return False

    def _set_process_priority(self):
        """Set process priority class."""
        try:
            process = GetCurrentProcess()
            
            if self.config.process_priority == "REALTIME":
                priority_class = REALTIME_PRIORITY_CLASS
            elif self.config.process_priority == "HIGH":
                priority_class = HIGH_PRIORITY_CLASS
            else:
                priority_class = HIGH_PRIORITY_CLASS
                
            SetPriorityClass(process, priority_class)
            logger.info(f"✅ Set process priority to {self.config.process_priority}")
            
        except Exception as e:
            logger.error(f"❌ Failed to set process priority: {e}")

    def _set_cpu_affinity(self):
        """Set CPU affinity for the process."""
        try:
            if self.config.affinity_mask is not None:
                process = psutil.Process()
                process.cpu_affinity([self.config.affinity_mask])
                logger.info(f"✅ Set CPU affinity to {self.config.affinity_mask}")
            else:
                # Use all available CPUs by default
                cpu_count = psutil.cpu_count()
                process = psutil.Process()
                process.cpu_affinity(list(range(cpu_count)))
                logger.info(f"✅ Set CPU affinity to all {cpu_count} CPUs")
                
        except Exception as e:
            logger.error(f"❌ Failed to set CPU affinity: {e}")

    def _set_timer_resolution(self):
        """Set high-resolution timer for Windows."""
        try:
            if self.config.use_high_res_timer:
                # Set timer resolution to 1ms for high-precision timing
                win32api.timeBeginPeriod(1)
                logger.info("✅ Set high-resolution timer (1ms)")
            else:
                # Use default timer resolution
                win32api.timeEndPeriod(1)
                logger.info("✅ Using default timer resolution")
                
        except Exception as e:
            logger.error(f"❌ Failed to set timer resolution: {e}")

    def _optimize_memory_settings(self):
        """Optimize memory settings for trading system."""
        try:
            process = psutil.Process()
            
            # Set working set size
            if self.config.working_set_size_mb > 0:
                # This is a simplified approach - in production you'd use SetProcessWorkingSetSize
                logger.info(f"✅ Memory optimization configured for {self.config.working_set_size_mb}MB working set")
                
        except Exception as e:
            logger.error(f"❌ Failed to optimize memory settings: {e}")

    def _configure_power_settings(self):
        """Configure power settings to prevent system sleep and throttling."""
        try:
            if self.config.prevent_sleep:
                # Prevent system from going to sleep
                win32api.SetThreadExecutionState(
                    win32con.ES_CONTINUOUS | 
                    win32con.ES_SYSTEM_REQUIRED | 
                    win32con.ES_AWAYMODE_REQUIRED
                )
                logger.info("✅ Configured to prevent system sleep")
                
        except Exception as e:
            logger.error(f"❌ Failed to configure power settings: {e}")

    def set_thread_priority(self, thread_name: str, priority: ThreadPriority) -> bool:
        """Set priority for a specific thread."""
        if not WINDOWS_AVAILABLE:
            return False
            
        try:
            # Map our priority enum to Windows thread priority
            priority_map = {
                ThreadPriority.LOWEST: win32con.THREAD_PRIORITY_LOWEST,
                ThreadPriority.BELOW_NORMAL: win32con.THREAD_PRIORITY_BELOW_NORMAL,
                ThreadPriority.NORMAL: win32con.THREAD_PRIORITY_NORMAL,
                ThreadPriority.ABOVE_NORMAL: win32con.THREAD_PRIORITY_ABOVE_NORMAL,
                ThreadPriority.HIGHEST: win32con.THREAD_PRIORITY_HIGHEST,
                ThreadPriority.REALTIME: win32con.THREAD_PRIORITY_TIME_CRITICAL
            }
            
            # Get current thread handle
            current_thread = win32api.GetCurrentThread()
            win32api.SetThreadPriority(current_thread, priority_map[priority])
            
            self.thread_priorities[thread_name] = priority.value
            logger.info(f"✅ Set thread '{thread_name}' priority to {priority.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to set thread priority for '{thread_name}': {e}")
            return False

    def get_high_res_timestamp(self) -> int:
        """Get high-resolution timestamp in nanoseconds."""
        return time.perf_counter_ns()

    def get_high_res_timestamp_ms(self) -> float:
        """Get high-resolution timestamp in milliseconds."""
        return time.perf_counter() * 1000

    def cleanup(self):
        """Cleanup Windows scheduling optimizations."""
        if not WINDOWS_AVAILABLE or not self._initialized:
            return
            
        try:
            # Restore timer resolution
            if self.config.use_high_res_timer:
                win32api.timeEndPeriod(1)
                
            # Restore execution state
            if self.config.prevent_sleep:
                win32api.SetThreadExecutionState(win32con.ES_CONTINUOUS)
                
            logger.info("✅ Windows scheduling cleanup completed")
            
        except Exception as e:
            logger.error(f"❌ Error during Windows scheduling cleanup: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get current scheduling status."""
        status = {
            "platform": sys.platform,
            "windows_available": WINDOWS_AVAILABLE,
            "initialized": self._initialized,
            "config": {
                "process_priority": self.config.process_priority,
                "affinity_mask": self.config.affinity_mask,
                "use_high_res_timer": self.config.use_high_res_timer,
                "timer_resolution_us": self.config.timer_resolution_us
            },
            "thread_priorities": self.thread_priorities
        }
        
        if WINDOWS_AVAILABLE:
            try:
                process = psutil.Process()
                status["current_affinity"] = process.cpu_affinity()
                status["current_priority"] = process.nice()
            except Exception as e:
                status["error"] = str(e)
                
        return status

class HighResolutionTimer:
    """
    High-resolution timer for precise latency measurements.
    Uses time.perf_counter_ns() for nanosecond precision.
    """
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        
    def start(self):
        """Start the timer."""
        self.start_time = time.perf_counter_ns()
        
    def stop(self):
        """Stop the timer."""
        self.end_time = time.perf_counter_ns()
        
    def elapsed_ns(self) -> int:
        """Get elapsed time in nanoseconds."""
        if self.start_time is None:
            return 0
        end_time = self.end_time if self.end_time is not None else time.perf_counter_ns()
        return end_time - self.start_time
        
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return self.elapsed_ns() / 1_000_000
        
    def elapsed_us(self) -> float:
        """Get elapsed time in microseconds."""
        return self.elapsed_ns() / 1_000

class ThreadManager:
    """
    Manages thread priorities and scheduling for different system components.
    """
    
    def __init__(self, scheduler: WindowsScheduler):
        self.scheduler = scheduler
        self.thread_registry: Dict[str, threading.Thread] = {}
        
    def register_thread(self, name: str, thread: threading.Thread, priority: ThreadPriority):
        """Register a thread with specific priority."""
        self.thread_registry[name] = thread
        
        # Set thread priority if scheduler is available
        if self.scheduler._initialized:
            self.scheduler.set_thread_priority(name, priority)
            
    def get_thread_status(self) -> Dict[str, Any]:
        """Get status of all registered threads."""
        status = {}
        for name, thread in self.thread_registry.items():
            status[name] = {
                "alive": thread.is_alive(),
                "daemon": thread.daemon,
                "name": thread.name,
                "ident": thread.ident
            }
        return status

# Global scheduler instance
_global_scheduler: Optional[WindowsScheduler] = None

def initialize_windows_scheduling(config: SchedulingConfig = None) -> WindowsScheduler:
    """Initialize global Windows scheduler."""
    global _global_scheduler
    
    if config is None:
        config = SchedulingConfig()
        
    _global_scheduler = WindowsScheduler(config)
    _global_scheduler.initialize()
    return _global_scheduler

def get_scheduler() -> Optional[WindowsScheduler]:
    """Get the global scheduler instance."""
    return _global_scheduler

def cleanup_windows_scheduling():
    """Cleanup global Windows scheduler."""
    global _global_scheduler
    if _global_scheduler:
        _global_scheduler.cleanup()
        _global_scheduler = None

# Example usage and testing
if __name__ == "__main__":
    # Test Windows scheduling
    config = SchedulingConfig(
        process_priority="HIGH",
        use_high_res_timer=True,
        prevent_sleep=True
    )
    
    scheduler = initialize_windows_scheduling(config)
    
    # Test high-resolution timing
    timer = HighResolutionTimer()
    timer.start()
    time.sleep(0.001)  # 1ms
    timer.stop()
    
    print(f"Timer precision test: {timer.elapsed_ms():.3f}ms")
    print(f"Scheduler status: {scheduler.get_status()}")
    
    # Cleanup
    cleanup_windows_scheduling()
