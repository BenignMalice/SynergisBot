"""
Comprehensive tests for HDR histogram system

Tests histogram creation, value recording, percentile calculations,
stage metrics, queue metrics, and system performance monitoring.
"""

import pytest
import time
import threading
import random
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from infra.hdr_histograms import (
    HDRHistogram, HDRHistogramManager, HistogramConfig, PercentileStats,
    PipelineStage, QueueType, HistogramType,
    get_histogram_manager, record_stage_latency, record_stage_throughput,
    record_stage_success, record_stage_error, record_queue_depth,
    record_queue_processing_time, get_stage_latency_percentiles,
    get_queue_depth_percentiles, get_system_summary
)

class TestHistogramConfig:
    """Test histogram configuration"""
    
    def test_histogram_config_creation(self):
        """Test histogram configuration creation"""
        config = HistogramConfig(
            min_value=0.0,
            max_value=1000.0,
            precision=2,
            max_samples=10000,
            window_size=1000,
            auto_cleanup=True,
            cleanup_interval_ms=60000
        )
        
        assert config.min_value == 0.0
        assert config.max_value == 1000.0
        assert config.precision == 2
        assert config.max_samples == 10000
        assert config.window_size == 1000
        assert config.auto_cleanup is True
        assert config.cleanup_interval_ms == 60000
    
    def test_histogram_config_defaults(self):
        """Test histogram configuration defaults"""
        config = HistogramConfig()
        
        assert config.min_value == 0.0
        assert config.max_value == 3600000.0  # 1 hour
        assert config.precision == 2
        assert config.max_samples == 100000
        assert config.window_size == 1000
        assert config.auto_cleanup is True
        assert config.cleanup_interval_ms == 60000

class TestPercentileStats:
    """Test percentile statistics"""
    
    def test_percentile_stats_creation(self):
        """Test percentile statistics creation"""
        stats = PercentileStats(
            p50=25.0,
            p95=100.0,
            p99=250.0,
            p99_9=500.0,
            min_value=1.0,
            max_value=1000.0,
            mean=50.0,
            count=100
        )
        
        assert stats.p50 == 25.0
        assert stats.p95 == 100.0
        assert stats.p99 == 250.0
        assert stats.p99_9 == 500.0
        assert stats.min_value == 1.0
        assert stats.max_value == 1000.0
        assert stats.mean == 50.0
        assert stats.count == 100
    
    def test_percentile_stats_defaults(self):
        """Test percentile statistics defaults"""
        stats = PercentileStats()
        
        assert stats.p50 == 0.0
        assert stats.p95 == 0.0
        assert stats.p99 == 0.0
        assert stats.p99_9 == 0.0
        assert stats.min_value == 0.0
        assert stats.max_value == 0.0
        assert stats.mean == 0.0
        assert stats.count == 0

class TestHDRHistogram:
    """Test HDR histogram functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.config = HistogramConfig(
            min_value=0.0,
            max_value=1000.0,
            precision=2,
            max_samples=1000,
            window_size=100,
            auto_cleanup=False  # Disable for testing
        )
        self.histogram = HDRHistogram(self.config)
    
    def test_histogram_initialization(self):
        """Test histogram initialization"""
        assert self.histogram.config == self.config
        assert len(self.histogram.buckets) == 0
        assert len(self.histogram.samples) == 0
        assert hasattr(self.histogram.lock, 'acquire')  # Check it's a lock-like object
    
    def test_record_value(self):
        """Test value recording"""
        # Record some values
        values = [1.0, 5.0, 10.0, 25.0, 50.0, 100.0]
        for value in values:
            self.histogram.record_value(value)
        
        assert len(self.histogram.samples) == len(values)
        assert len(self.histogram.buckets) > 0
    
    def test_record_value_clamping(self):
        """Test value clamping to valid range"""
        # Record values outside range
        self.histogram.record_value(-10.0)  # Below min
        self.histogram.record_value(2000.0)  # Above max
        
        # Values should be clamped
        assert len(self.histogram.samples) == 2
        assert all(0.0 <= sample <= 1000.0 for sample in self.histogram.samples)
    
    def test_get_percentiles_empty(self):
        """Test percentile calculation with empty histogram"""
        stats = self.histogram.get_percentiles()
        
        assert stats.p50 == 0.0
        assert stats.p95 == 0.0
        assert stats.p99 == 0.0
        assert stats.p99_9 == 0.0
        assert stats.min_value == 0.0
        assert stats.max_value == 0.0
        assert stats.mean == 0.0
        assert stats.count == 0
    
    def test_get_percentiles_single_value(self):
        """Test percentile calculation with single value"""
        self.histogram.record_value(50.0)
        stats = self.histogram.get_percentiles()
        
        assert stats.p50 == 50.0
        assert stats.p95 == 50.0
        assert stats.p99 == 50.0
        assert stats.p99_9 == 50.0
        assert stats.min_value == 50.0
        assert stats.max_value == 50.0
        assert stats.mean == 50.0
        assert stats.count == 1
    
    def test_get_percentiles_multiple_values(self):
        """Test percentile calculation with multiple values"""
        # Record values in ascending order
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        for value in values:
            self.histogram.record_value(value)
        
        stats = self.histogram.get_percentiles()
        
        assert stats.count == 10
        assert stats.min_value == 1.0
        assert stats.max_value == 10.0
        assert stats.mean == 5.5
        # For 10 values, p50 should be the 6th value (index 5) = 6.0
        assert stats.p50 == 6.0  # 6th value for 10 elements
        assert stats.p95 == 10.0  # 95th percentile (index 9)
        assert stats.p99 == 10.0  # 99th percentile (index 9)
    
    def test_get_bucket_distribution(self):
        """Test bucket distribution"""
        values = [1.0, 10.0, 100.0, 1000.0]
        for value in values:
            self.histogram.record_value(value)
        
        distribution = self.histogram.get_bucket_distribution()
        
        assert isinstance(distribution, dict)
        assert len(distribution) > 0
        assert all(isinstance(bucket, int) for bucket in distribution.keys())
        assert all(isinstance(count, int) for count in distribution.values())
    
    def test_reset(self):
        """Test histogram reset"""
        # Add some data
        for i in range(10):
            self.histogram.record_value(float(i))
        
        assert len(self.histogram.samples) == 10
        assert len(self.histogram.buckets) > 0
        
        # Reset
        self.histogram.reset()
        
        assert len(self.histogram.samples) == 0
        assert len(self.histogram.buckets) == 0
    
    def test_thread_safety(self):
        """Test thread safety of histogram operations"""
        def record_values():
            for i in range(100):
                self.histogram.record_value(float(i))
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=record_values)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should have recorded 500 values (5 threads * 100 values each)
        assert len(self.histogram.samples) == 500

class TestHDRHistogramManager:
    """Test HDR histogram manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.manager = HDRHistogramManager()
    
    def test_manager_initialization(self):
        """Test manager initialization"""
        assert len(self.manager.stage_metrics) == len(PipelineStage)
        assert len(self.manager.queue_metrics) == len(QueueType)
        
        # Check all stages are initialized
        for stage in PipelineStage:
            assert stage in self.manager.stage_metrics
            assert isinstance(self.manager.stage_metrics[stage].latency_histogram, HDRHistogram)
            assert isinstance(self.manager.stage_metrics[stage].throughput_histogram, HDRHistogram)
        
        # Check all queues are initialized
        for queue_type in QueueType:
            assert queue_type in self.manager.queue_metrics
            assert isinstance(self.manager.queue_metrics[queue_type].depth_histogram, HDRHistogram)
            assert isinstance(self.manager.queue_metrics[queue_type].processing_time_histogram, HDRHistogram)
    
    def test_record_stage_latency(self):
        """Test stage latency recording"""
        stage = PipelineStage.TICK_INGESTION
        latency = 25.5
        
        self.manager.record_stage_latency(stage, latency)
        
        # Check that latency was recorded
        stats = self.manager.get_stage_latency_percentiles(stage)
        assert stats.count == 1
        assert stats.p50 == latency
    
    def test_record_stage_throughput(self):
        """Test stage throughput recording"""
        stage = PipelineStage.FEATURE_CALCULATION
        throughput = 100.0
        
        self.manager.record_stage_throughput(stage, throughput)
        
        # Check that throughput was recorded
        stats = self.manager.get_stage_throughput_percentiles(stage)
        assert stats.count == 1
        assert stats.p50 == throughput
    
    def test_record_stage_success_error(self):
        """Test stage success/error recording"""
        stage = PipelineStage.DATABASE_WRITE
        
        # Record successes
        for _ in range(10):
            self.manager.record_stage_success(stage)
        
        # Record errors
        for _ in range(2):
            self.manager.record_stage_error(stage)
        
        metrics = self.manager.stage_metrics[stage]
        assert metrics.success_count == 10
        assert metrics.error_count == 2
    
    def test_record_queue_depth(self):
        """Test queue depth recording"""
        queue_type = QueueType.TICK_QUEUE
        depth = 15
        
        self.manager.record_queue_depth(queue_type, depth)
        
        # Check that depth was recorded
        stats = self.manager.get_queue_depth_percentiles(queue_type)
        assert stats.count == 1
        assert stats.p50 == depth
    
    def test_record_queue_processing_time(self):
        """Test queue processing time recording"""
        queue_type = QueueType.FEATURE_QUEUE
        processing_time = 5.5
        
        self.manager.record_queue_processing_time(queue_type, processing_time)
        
        # Check that processing time was recorded
        stats = self.manager.get_queue_processing_time_percentiles(queue_type)
        assert stats.count == 1
        assert stats.p50 == processing_time
    
    def test_record_queue_overflow_underflow(self):
        """Test queue overflow/underflow recording"""
        queue_type = QueueType.DATABASE_QUEUE
        
        # Record overflows
        for _ in range(5):
            self.manager.record_queue_overflow(queue_type)
        
        # Record underflows
        for _ in range(2):
            self.manager.record_queue_underflow(queue_type)
        
        metrics = self.manager.queue_metrics[queue_type]
        assert metrics.overflow_count == 5
        assert metrics.underflow_count == 2
    
    def test_get_all_stage_metrics(self):
        """Test getting all stage metrics"""
        # Record some data
        stage = PipelineStage.TICK_INGESTION
        self.manager.record_stage_latency(stage, 25.0)
        self.manager.record_stage_throughput(stage, 100.0)
        self.manager.record_stage_success(stage)
        
        metrics = self.manager.get_all_stage_metrics()
        
        assert isinstance(metrics, dict)
        assert stage.value in metrics
        
        stage_data = metrics[stage.value]
        assert 'latency' in stage_data
        assert 'throughput' in stage_data
        assert 'success_count' in stage_data
        assert 'error_count' in stage_data
        assert 'error_rate' in stage_data
        assert 'last_update' in stage_data
        
        assert stage_data['latency']['count'] == 1
        assert stage_data['throughput']['count'] == 1
        assert stage_data['success_count'] == 1
        assert stage_data['error_count'] == 0
    
    def test_get_all_queue_metrics(self):
        """Test getting all queue metrics"""
        # Record some data
        queue_type = QueueType.TICK_QUEUE
        self.manager.record_queue_depth(queue_type, 10)
        self.manager.record_queue_processing_time(queue_type, 5.0)
        self.manager.record_queue_overflow(queue_type)
        
        metrics = self.manager.get_all_queue_metrics()
        
        assert isinstance(metrics, dict)
        assert queue_type.value in metrics
        
        queue_data = metrics[queue_type.value]
        assert 'depth' in queue_data
        assert 'processing_time' in queue_data
        assert 'overflow_count' in queue_data
        assert 'underflow_count' in queue_data
        assert 'last_update' in queue_data
        
        assert queue_data['depth']['count'] == 1
        assert queue_data['processing_time']['count'] == 1
        assert queue_data['overflow_count'] == 1
        assert queue_data['underflow_count'] == 0
    
    def test_get_system_summary(self):
        """Test system summary generation"""
        # Record some data across multiple stages and queues
        self.manager.record_stage_latency(PipelineStage.TICK_INGESTION, 25.0)
        self.manager.record_stage_latency(PipelineStage.DATABASE_WRITE, 50.0)
        self.manager.record_queue_depth(QueueType.TICK_QUEUE, 10)
        self.manager.record_queue_depth(QueueType.FEATURE_QUEUE, 5)
        
        summary = self.manager.get_system_summary()
        
        assert isinstance(summary, dict)
        assert 'overall_p95_latency' in summary
        assert 'stage_count' in summary
        assert 'queue_count' in summary
        assert 'queue_health' in summary
        assert 'timestamp' in summary
        
        assert summary['stage_count'] == len(PipelineStage)
        assert summary['queue_count'] == len(QueueType)
        assert summary['overall_p95_latency'] >= 0.0
    
    def test_reset_all_metrics(self):
        """Test resetting all metrics"""
        # Record some data
        stage = PipelineStage.TICK_INGESTION
        queue_type = QueueType.TICK_QUEUE
        
        self.manager.record_stage_latency(stage, 25.0)
        self.manager.record_stage_success(stage)
        self.manager.record_queue_depth(queue_type, 10)
        self.manager.record_queue_overflow(queue_type)
        
        # Verify data exists
        assert self.manager.stage_metrics[stage].latency_histogram.get_percentiles().count > 0
        assert self.manager.stage_metrics[stage].success_count > 0
        assert self.manager.queue_metrics[queue_type].depth_histogram.get_percentiles().count > 0
        assert self.manager.queue_metrics[queue_type].overflow_count > 0
        
        # Reset all metrics
        self.manager.reset_all_metrics()
        
        # Verify data is reset
        assert self.manager.stage_metrics[stage].latency_histogram.get_percentiles().count == 0
        assert self.manager.stage_metrics[stage].success_count == 0
        assert self.manager.queue_metrics[queue_type].depth_histogram.get_percentiles().count == 0
        assert self.manager.queue_metrics[queue_type].overflow_count == 0

class TestGlobalFunctions:
    """Test global histogram functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.hdr_histograms
        infra.hdr_histograms._histogram_manager = None
    
    def test_get_histogram_manager(self):
        """Test global histogram manager access"""
        manager1 = get_histogram_manager()
        manager2 = get_histogram_manager()
        
        # Should return same instance
        assert manager1 is manager2
        assert isinstance(manager1, HDRHistogramManager)
    
    def test_record_stage_latency_global(self):
        """Test global stage latency recording"""
        stage = PipelineStage.TICK_INGESTION
        latency = 30.0
        
        record_stage_latency(stage, latency)
        
        stats = get_stage_latency_percentiles(stage)
        assert stats.count == 1
        assert stats.p50 == latency
    
    def test_record_stage_throughput_global(self):
        """Test global stage throughput recording"""
        stage = PipelineStage.FEATURE_CALCULATION
        throughput = 150.0
        
        record_stage_throughput(stage, throughput)
        
        # Get manager and check
        manager = get_histogram_manager()
        stats = manager.get_stage_throughput_percentiles(stage)
        assert stats.count == 1
        assert stats.p50 == throughput
    
    def test_record_stage_success_error_global(self):
        """Test global stage success/error recording"""
        stage = PipelineStage.DATABASE_WRITE
        
        record_stage_success(stage)
        record_stage_success(stage)
        record_stage_error(stage)
        
        manager = get_histogram_manager()
        metrics = manager.stage_metrics[stage]
        assert metrics.success_count == 2
        assert metrics.error_count == 1
    
    def test_record_queue_depth_global(self):
        """Test global queue depth recording"""
        queue_type = QueueType.TICK_QUEUE
        depth = 20
        
        record_queue_depth(queue_type, depth)
        
        stats = get_queue_depth_percentiles(queue_type)
        assert stats.count == 1
        assert stats.p50 == depth
    
    def test_record_queue_processing_time_global(self):
        """Test global queue processing time recording"""
        queue_type = QueueType.FEATURE_QUEUE
        processing_time = 8.5
        
        record_queue_processing_time(queue_type, processing_time)
        
        manager = get_histogram_manager()
        stats = manager.get_queue_processing_time_percentiles(queue_type)
        assert stats.count == 1
        assert stats.p50 == processing_time
    
    def test_get_system_summary_global(self):
        """Test global system summary"""
        # Record some data
        record_stage_latency(PipelineStage.TICK_INGESTION, 25.0)
        record_queue_depth(QueueType.TICK_QUEUE, 15)
        
        summary = get_system_summary()
        
        assert isinstance(summary, dict)
        assert 'overall_p95_latency' in summary
        assert 'stage_count' in summary
        assert 'queue_count' in summary
        assert 'queue_health' in summary
        assert 'timestamp' in summary

class TestHistogramIntegration:
    """Integration tests for histogram system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.hdr_histograms
        infra.hdr_histograms._histogram_manager = None
    
    def test_comprehensive_metrics_collection(self):
        """Test comprehensive metrics collection across all components"""
        # Record latency data for all stages
        for stage in PipelineStage:
            for _ in range(10):
                latency = random.uniform(1, 100)
                record_stage_latency(stage, latency)
        
        # Record throughput data for all stages
        for stage in PipelineStage:
            for _ in range(10):
                throughput = random.uniform(10, 1000)
                record_stage_throughput(stage, throughput)
        
        # Record queue depth data for all queues
        for queue_type in QueueType:
            for _ in range(10):
                depth = random.randint(0, 50)
                record_queue_depth(queue_type, depth)
        
        # Record processing time data for all queues
        for queue_type in QueueType:
            for _ in range(10):
                processing_time = random.uniform(1, 50)
                record_queue_processing_time(queue_type, processing_time)
        
        # Get system summary
        summary = get_system_summary()
        
        assert summary['stage_count'] == len(PipelineStage)
        assert summary['queue_count'] == len(QueueType)
        assert summary['overall_p95_latency'] > 0.0
        
        # Verify all stages have data
        manager = get_histogram_manager()
        stage_metrics = manager.get_all_stage_metrics()
        
        for stage in PipelineStage:
            assert stage.value in stage_metrics
            stage_data = stage_metrics[stage.value]
            assert stage_data['latency']['count'] == 10
            assert stage_data['throughput']['count'] == 10
        
        # Verify all queues have data
        queue_metrics = manager.get_all_queue_metrics()
        
        for queue_type in QueueType:
            assert queue_type.value in queue_metrics
            queue_data = queue_metrics[queue_type.value]
            assert queue_data['depth']['count'] == 10
            assert queue_data['processing_time']['count'] == 10
    
    def test_percentile_accuracy(self):
        """Test percentile calculation accuracy"""
        # Create known data set
        values = list(range(1, 101))  # 1 to 100
        
        for value in values:
            record_stage_latency(PipelineStage.TICK_INGESTION, float(value))
        
        stats = get_stage_latency_percentiles(PipelineStage.TICK_INGESTION)
        
        # Check percentiles are reasonable
        assert stats.count == 100
        assert stats.min_value == 1.0
        assert stats.max_value == 100.0
        assert stats.mean == 50.5
        assert 45.0 <= stats.p50 <= 55.0  # Should be around 50
        assert 90.0 <= stats.p95 <= 100.0  # Should be around 95
        assert 95.0 <= stats.p99 <= 100.0  # Should be around 99
    
    def test_concurrent_access(self):
        """Test concurrent access to histogram system"""
        def record_data():
            for _ in range(100):
                stage = random.choice(list(PipelineStage))
                queue_type = random.choice(list(QueueType))
                
                record_stage_latency(stage, random.uniform(1, 100))
                record_queue_depth(queue_type, random.randint(0, 50))
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=record_data)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify data was recorded
        manager = get_histogram_manager()
        stage_metrics = manager.get_all_stage_metrics()
        queue_metrics = manager.get_all_queue_metrics()
        
        # Should have data from all stages and queues
        assert len(stage_metrics) == len(PipelineStage)
        assert len(queue_metrics) == len(QueueType)
        
        # Check that some data was recorded
        total_latency_count = sum(
            stage_data['latency']['count'] 
            for stage_data in stage_metrics.values()
        )
        total_depth_count = sum(
            queue_data['depth']['count'] 
            for queue_data in queue_metrics.values()
        )
        
        assert total_latency_count > 0
        assert total_depth_count > 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
