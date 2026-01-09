"""
HDR Histogram Implementation for Performance Monitoring

This module implements High Dynamic Range (HDR) histograms for measuring
latency distributions and queue depth metrics across different pipeline stages.
Provides p50, p95, p99 percentiles for comprehensive performance analysis.

Key Features:
- Per-stage latency histograms (ingestion, processing, database, etc.)
- Per-queue depth histograms (tick_queue, feature_queue, db_queue, etc.)
- Automatic histogram management and memory optimization
- Real-time percentile calculations
- Thread-safe operations for concurrent access
"""

import time
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
from collections import defaultdict, deque
import json
import math
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class HistogramType(Enum):
    """Types of histograms for different metrics"""
    LATENCY = "latency"
    QUEUE_DEPTH = "queue_depth"
    THROUGHPUT = "throughput"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"

class PipelineStage(Enum):
    """Pipeline stages for latency measurement"""
    TICK_INGESTION = "tick_ingestion"
    DATA_NORMALIZATION = "data_normalization"
    FEATURE_CALCULATION = "feature_calculation"
    DATABASE_WRITE = "database_write"
    DECISION_ENGINE = "decision_engine"
    TRADE_EXECUTION = "trade_execution"
    ALERT_PROCESSING = "alert_processing"

class QueueType(Enum):
    """Queue types for depth monitoring"""
    TICK_QUEUE = "tick_queue"
    FEATURE_QUEUE = "feature_queue"
    DATABASE_QUEUE = "database_queue"
    DECISION_QUEUE = "decision_queue"
    ALERT_QUEUE = "alert_queue"

@dataclass
class HistogramConfig:
    """Configuration for histogram parameters"""
    min_value: float = 0.0
    max_value: float = 3600000.0  # 1 hour in milliseconds
    precision: int = 2  # Number of significant digits
    max_samples: int = 100000  # Maximum samples to keep
    window_size: int = 1000  # Rolling window size
    auto_cleanup: bool = True
    cleanup_interval_ms: int = 60000  # 1 minute

@dataclass
class PercentileStats:
    """Statistics for percentile calculations"""
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    p99_9: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0
    mean: float = 0.0
    count: int = 0

@dataclass
class StageMetrics:
    """Metrics for a specific pipeline stage"""
    stage: PipelineStage
    latency_histogram: 'HDRHistogram'
    throughput_histogram: 'HDRHistogram'
    error_count: int = 0
    success_count: int = 0
    last_update: float = field(default_factory=time.time)

@dataclass
class QueueMetrics:
    """Metrics for a specific queue"""
    queue_type: QueueType
    depth_histogram: 'HDRHistogram'
    processing_time_histogram: 'HDRHistogram'
    overflow_count: int = 0
    underflow_count: int = 0
    last_update: float = field(default_factory=time.time)

class HDRHistogram:
    """High Dynamic Range Histogram implementation"""
    
    def __init__(self, config: HistogramConfig):
        self.config = config
        self.buckets = defaultdict(int)
        self.samples = deque(maxlen=config.max_samples)
        self.lock = threading.RLock()
        self.last_cleanup = time.time()
        
    def record_value(self, value: float) -> None:
        """Record a value in the histogram"""
        with self.lock:
            # Clamp value to valid range
            value = max(self.config.min_value, min(self.config.max_value, value))
            
            # Calculate bucket index
            bucket = self._get_bucket_index(value)
            self.buckets[bucket] += 1
            
            # Add to samples for rolling window
            self.samples.append(value)
            
            # Auto-cleanup if needed
            if self.config.auto_cleanup:
                self._maybe_cleanup()
    
    def _get_bucket_index(self, value: float) -> int:
        """Get bucket index for a value"""
        if value <= 0:
            return 0
        
        # Use logarithmic bucketing for better precision at low values
        log_value = math.log10(value)
        bucket = int(log_value * (10 ** self.config.precision))
        return max(0, bucket)
    
    def _maybe_cleanup(self) -> None:
        """Cleanup old data if needed"""
        current_time = time.time()
        if current_time - self.last_cleanup > (self.config.cleanup_interval_ms / 1000.0):
            self._cleanup()
            self.last_cleanup = current_time
    
    def _cleanup(self) -> None:
        """Cleanup old histogram data"""
        # Keep only recent samples
        if len(self.samples) > self.config.window_size:
            # Remove oldest samples
            samples_to_remove = len(self.samples) - self.config.window_size
            for _ in range(samples_to_remove):
                if self.samples:
                    self.samples.popleft()
        
        # Rebuild buckets from remaining samples
        self.buckets.clear()
        for sample in self.samples:
            bucket = self._get_bucket_index(sample)
            self.buckets[bucket] += 1
    
    def get_percentiles(self) -> PercentileStats:
        """Calculate percentile statistics"""
        with self.lock:
            if not self.samples:
                return PercentileStats()
            
            sorted_samples = sorted(self.samples)
            count = len(sorted_samples)
            
            if count == 0:
                return PercentileStats()
            
            # Calculate percentiles
            p50_idx = int(count * 0.5)
            p95_idx = int(count * 0.95)
            p99_idx = int(count * 0.99)
            p99_9_idx = int(count * 0.999)
            
            return PercentileStats(
                p50=sorted_samples[p50_idx] if p50_idx < count else sorted_samples[-1],
                p95=sorted_samples[p95_idx] if p95_idx < count else sorted_samples[-1],
                p99=sorted_samples[p99_idx] if p99_idx < count else sorted_samples[-1],
                p99_9=sorted_samples[p99_9_idx] if p99_9_idx < count else sorted_samples[-1],
                min_value=min(sorted_samples),
                max_value=max(sorted_samples),
                mean=sum(sorted_samples) / count,
                count=count
            )
    
    def get_bucket_distribution(self) -> Dict[int, int]:
        """Get bucket distribution for analysis"""
        with self.lock:
            return dict(self.buckets)
    
    def reset(self) -> None:
        """Reset histogram data"""
        with self.lock:
            self.buckets.clear()
            self.samples.clear()
            self.last_cleanup = time.time()

class HDRHistogramManager:
    """Manager for all HDR histograms in the system"""
    
    def __init__(self):
        self.stage_metrics: Dict[PipelineStage, StageMetrics] = {}
        self.queue_metrics: Dict[QueueType, QueueMetrics] = {}
        self.lock = threading.RLock()
        self.config = HistogramConfig()
        
        # Initialize all stage metrics
        self._initialize_stage_metrics()
        self._initialize_queue_metrics()
    
    def _initialize_stage_metrics(self) -> None:
        """Initialize metrics for all pipeline stages"""
        for stage in PipelineStage:
            latency_histogram = HDRHistogram(self.config)
            throughput_histogram = HDRHistogram(self.config)
            
            self.stage_metrics[stage] = StageMetrics(
                stage=stage,
                latency_histogram=latency_histogram,
                throughput_histogram=throughput_histogram
            )
    
    def _initialize_queue_metrics(self) -> None:
        """Initialize metrics for all queue types"""
        for queue_type in QueueType:
            depth_histogram = HDRHistogram(self.config)
            processing_time_histogram = HDRHistogram(self.config)
            
            self.queue_metrics[queue_type] = QueueMetrics(
                queue_type=queue_type,
                depth_histogram=depth_histogram,
                processing_time_histogram=processing_time_histogram
            )
    
    def record_stage_latency(self, stage: PipelineStage, latency_ms: float) -> None:
        """Record latency for a pipeline stage"""
        with self.lock:
            if stage in self.stage_metrics:
                self.stage_metrics[stage].latency_histogram.record_value(latency_ms)
                self.stage_metrics[stage].last_update = time.time()
    
    def record_stage_throughput(self, stage: PipelineStage, throughput_per_sec: float) -> None:
        """Record throughput for a pipeline stage"""
        with self.lock:
            if stage in self.stage_metrics:
                self.stage_metrics[stage].throughput_histogram.record_value(throughput_per_sec)
                self.stage_metrics[stage].last_update = time.time()
    
    def record_stage_success(self, stage: PipelineStage) -> None:
        """Record successful operation for a stage"""
        with self.lock:
            if stage in self.stage_metrics:
                self.stage_metrics[stage].success_count += 1
                self.stage_metrics[stage].last_update = time.time()
    
    def record_stage_error(self, stage: PipelineStage) -> None:
        """Record error for a stage"""
        with self.lock:
            if stage in self.stage_metrics:
                self.stage_metrics[stage].error_count += 1
                self.stage_metrics[stage].last_update = time.time()
    
    def record_queue_depth(self, queue_type: QueueType, depth: int) -> None:
        """Record queue depth"""
        with self.lock:
            if queue_type in self.queue_metrics:
                self.queue_metrics[queue_type].depth_histogram.record_value(float(depth))
                self.queue_metrics[queue_type].last_update = time.time()
    
    def record_queue_processing_time(self, queue_type: QueueType, processing_time_ms: float) -> None:
        """Record queue processing time"""
        with self.lock:
            if queue_type in self.queue_metrics:
                self.queue_metrics[queue_type].processing_time_histogram.record_value(processing_time_ms)
                self.queue_metrics[queue_type].last_update = time.time()
    
    def record_queue_overflow(self, queue_type: QueueType) -> None:
        """Record queue overflow"""
        with self.lock:
            if queue_type in self.queue_metrics:
                self.queue_metrics[queue_type].overflow_count += 1
                self.queue_metrics[queue_type].last_update = time.time()
    
    def record_queue_underflow(self, queue_type: QueueType) -> None:
        """Record queue underflow"""
        with self.lock:
            if queue_type in self.queue_metrics:
                self.queue_metrics[queue_type].underflow_count += 1
                self.queue_metrics[queue_type].last_update = time.time()
    
    def get_stage_latency_percentiles(self, stage: PipelineStage) -> PercentileStats:
        """Get latency percentiles for a stage"""
        with self.lock:
            if stage in self.stage_metrics:
                return self.stage_metrics[stage].latency_histogram.get_percentiles()
            return PercentileStats()
    
    def get_stage_throughput_percentiles(self, stage: PipelineStage) -> PercentileStats:
        """Get throughput percentiles for a stage"""
        with self.lock:
            if stage in self.stage_metrics:
                return self.stage_metrics[stage].throughput_histogram.get_percentiles()
            return PercentileStats()
    
    def get_queue_depth_percentiles(self, queue_type: QueueType) -> PercentileStats:
        """Get queue depth percentiles"""
        with self.lock:
            if queue_type in self.queue_metrics:
                return self.queue_metrics[queue_type].depth_histogram.get_percentiles()
            return PercentileStats()
    
    def get_queue_processing_time_percentiles(self, queue_type: QueueType) -> PercentileStats:
        """Get queue processing time percentiles"""
        with self.lock:
            if queue_type in self.queue_metrics:
                return self.queue_metrics[queue_type].processing_time_histogram.get_percentiles()
            return PercentileStats()
    
    def get_all_stage_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics for all stages"""
        with self.lock:
            result = {}
            
            for stage, metrics in self.stage_metrics.items():
                latency_stats = metrics.latency_histogram.get_percentiles()
                throughput_stats = metrics.throughput_histogram.get_percentiles()
                
                result[stage.value] = {
                    'latency': {
                        'p50': latency_stats.p50,
                        'p95': latency_stats.p95,
                        'p99': latency_stats.p99,
                        'p99_9': latency_stats.p99_9,
                        'min': latency_stats.min_value,
                        'max': latency_stats.max_value,
                        'mean': latency_stats.mean,
                        'count': latency_stats.count
                    },
                    'throughput': {
                        'p50': throughput_stats.p50,
                        'p95': throughput_stats.p95,
                        'p99': throughput_stats.p99,
                        'p99_9': throughput_stats.p99_9,
                        'min': throughput_stats.min_value,
                        'max': throughput_stats.max_value,
                        'mean': throughput_stats.mean,
                        'count': throughput_stats.count
                    },
                    'success_count': metrics.success_count,
                    'error_count': metrics.error_count,
                    'error_rate': metrics.error_count / max(1, metrics.success_count + metrics.error_count),
                    'last_update': metrics.last_update
                }
            
            return result
    
    def get_all_queue_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics for all queues"""
        with self.lock:
            result = {}
            
            for queue_type, metrics in self.queue_metrics.items():
                depth_stats = metrics.depth_histogram.get_percentiles()
                processing_time_stats = metrics.processing_time_histogram.get_percentiles()
                
                result[queue_type.value] = {
                    'depth': {
                        'p50': depth_stats.p50,
                        'p95': depth_stats.p95,
                        'p99': depth_stats.p99,
                        'p99_9': depth_stats.p99_9,
                        'min': depth_stats.min_value,
                        'max': depth_stats.max_value,
                        'mean': depth_stats.mean,
                        'count': depth_stats.count
                    },
                    'processing_time': {
                        'p50': processing_time_stats.p50,
                        'p95': processing_time_stats.p95,
                        'p99': processing_time_stats.p99,
                        'p99_9': processing_time_stats.p99_9,
                        'min': processing_time_stats.min_value,
                        'max': processing_time_stats.max_value,
                        'mean': processing_time_stats.mean,
                        'count': processing_time_stats.count
                    },
                    'overflow_count': metrics.overflow_count,
                    'underflow_count': metrics.underflow_count,
                    'last_update': metrics.last_update
                }
            
            return result
    
    def get_system_summary(self) -> Dict[str, Any]:
        """Get overall system performance summary"""
        with self.lock:
            stage_metrics = self.get_all_stage_metrics()
            queue_metrics = self.get_all_queue_metrics()
            
            # Calculate overall system latency
            all_latencies = []
            for stage_data in stage_metrics.values():
                if stage_data['latency']['count'] > 0:
                    all_latencies.append(stage_data['latency']['p95'])
            
            overall_p95_latency = max(all_latencies) if all_latencies else 0.0
            
            # Calculate overall queue health
            queue_health = {}
            for queue_type, queue_data in queue_metrics.items():
                if queue_data['depth']['count'] > 0:
                    queue_health[queue_type] = {
                        'avg_depth': queue_data['depth']['mean'],
                        'max_depth': queue_data['depth']['max'],
                        'overflow_rate': queue_data['overflow_count'] / max(1, queue_data['depth']['count'])
                    }
            
            return {
                'overall_p95_latency': overall_p95_latency,
                'stage_count': len(stage_metrics),
                'queue_count': len(queue_metrics),
                'queue_health': queue_health,
                'timestamp': time.time()
            }
    
    def reset_all_metrics(self) -> None:
        """Reset all histogram data"""
        with self.lock:
            for metrics in self.stage_metrics.values():
                metrics.latency_histogram.reset()
                metrics.throughput_histogram.reset()
                metrics.error_count = 0
                metrics.success_count = 0
            
            for metrics in self.queue_metrics.values():
                metrics.depth_histogram.reset()
                metrics.processing_time_histogram.reset()
                metrics.overflow_count = 0
                metrics.underflow_count = 0

# Global histogram manager instance
_histogram_manager: Optional[HDRHistogramManager] = None

def get_histogram_manager() -> HDRHistogramManager:
    """Get global histogram manager instance"""
    global _histogram_manager
    if _histogram_manager is None:
        _histogram_manager = HDRHistogramManager()
    return _histogram_manager

def record_stage_latency(stage: PipelineStage, latency_ms: float) -> None:
    """Record latency for a pipeline stage"""
    manager = get_histogram_manager()
    manager.record_stage_latency(stage, latency_ms)

def record_stage_throughput(stage: PipelineStage, throughput_per_sec: float) -> None:
    """Record throughput for a pipeline stage"""
    manager = get_histogram_manager()
    manager.record_stage_throughput(stage, throughput_per_sec)

def record_stage_success(stage: PipelineStage) -> None:
    """Record successful operation for a stage"""
    manager = get_histogram_manager()
    manager.record_stage_success(stage)

def record_stage_error(stage: PipelineStage) -> None:
    """Record error for a stage"""
    manager = get_histogram_manager()
    manager.record_stage_error(stage)

def record_queue_depth(queue_type: QueueType, depth: int) -> None:
    """Record queue depth"""
    manager = get_histogram_manager()
    manager.record_queue_depth(queue_type, depth)

def record_queue_processing_time(queue_type: QueueType, processing_time_ms: float) -> None:
    """Record queue processing time"""
    manager = get_histogram_manager()
    manager.record_queue_processing_time(queue_type, processing_time_ms)

def get_stage_latency_percentiles(stage: PipelineStage) -> PercentileStats:
    """Get latency percentiles for a stage"""
    manager = get_histogram_manager()
    return manager.get_stage_latency_percentiles(stage)

def get_queue_depth_percentiles(queue_type: QueueType) -> PercentileStats:
    """Get queue depth percentiles"""
    manager = get_histogram_manager()
    return manager.get_queue_depth_percentiles(queue_type)

def get_system_summary() -> Dict[str, Any]:
    """Get overall system performance summary"""
    manager = get_histogram_manager()
    return manager.get_system_summary()

if __name__ == "__main__":
    # Example usage
    import random
    
    # Record some sample data
    for _ in range(1000):
        # Simulate latency data
        latency = random.uniform(1, 100)  # 1-100ms
        record_stage_latency(PipelineStage.TICK_INGESTION, latency)
        
        # Simulate queue depth data
        depth = random.randint(0, 50)
        record_queue_depth(QueueType.TICK_QUEUE, depth)
    
    # Get metrics
    latency_stats = get_stage_latency_percentiles(PipelineStage.TICK_INGESTION)
    print(f"Latency percentiles: p50={latency_stats.p50:.2f}ms, p95={latency_stats.p95:.2f}ms, p99={latency_stats.p99:.2f}ms")
    
    depth_stats = get_queue_depth_percentiles(QueueType.TICK_QUEUE)
    print(f"Queue depth percentiles: p50={depth_stats.p50:.1f}, p95={depth_stats.p95:.1f}, p99={depth_stats.p99:.1f}")
    
    # Get system summary
    summary = get_system_summary()
    print(f"System summary: {json.dumps(summary, indent=2)}")
