"""
Latency Validation System

This module implements a comprehensive latency validation system to ensure
the trading system meets the <200ms p95 latency target on test hardware.

Key Features:
- Real-time latency measurement and monitoring
- P50, P95, P99 percentile analysis
- Stage-by-stage latency breakdown
- Hardware performance validation
- Latency trend analysis and alerting
- Performance optimization recommendations
"""

import time
import json
import logging
import threading
import statistics
import numpy as np
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import hashlib
import psutil
import os
import platform

logger = logging.getLogger(__name__)

class LatencyStage(Enum):
    """Latency measurement stages"""
    TICK_INGESTION = "tick_ingestion"
    DATA_NORMALIZATION = "data_normalization"
    VWAP_CALCULATION = "vwap_calculation"
    ATR_CALCULATION = "atr_calculation"
    DELTA_ANALYSIS = "delta_analysis"
    STRUCTURE_DETECTION = "structure_detection"
    FILTER_PROCESSING = "filter_processing"
    DECISION_MAKING = "decision_making"
    ORDER_PROCESSING = "order_processing"
    DATABASE_WRITE = "database_write"

class LatencyLevel(Enum):
    """Latency level classifications"""
    EXCELLENT = "excellent"  # <50ms p95
    GOOD = "good"  # 50-100ms p95
    ACCEPTABLE = "acceptable"  # 100-200ms p95
    POOR = "poor"  # >200ms p95

class HardwareType(Enum):
    """Hardware type classifications"""
    HIGH_END = "high_end"  # >16GB RAM, >8 cores, SSD
    MID_RANGE = "mid_range"  # 8-16GB RAM, 4-8 cores, SSD
    LOW_END = "low_end"  # <8GB RAM, <4 cores, HDD

@dataclass
class LatencyMeasurement:
    """Individual latency measurement"""
    timestamp: float
    stage: LatencyStage
    duration_ms: float
    symbol: str
    thread_id: int
    cpu_usage: float
    memory_usage: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class LatencyStats:
    """Latency statistics for a stage"""
    stage: LatencyStage
    count: int = 0
    min_ms: float = 0.0
    max_ms: float = 0.0
    mean_ms: float = 0.0
    median_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    std_dev_ms: float = 0.0
    recent_trend: str = "stable"  # improving, stable, degrading

@dataclass
class HardwareProfile:
    """Hardware profile information"""
    cpu_count: int
    cpu_freq_mhz: float
    memory_gb: float
    disk_type: str
    os_type: str
    python_version: str
    hardware_type: HardwareType
    performance_score: float

class LatencyTimer:
    """High-precision latency timer"""
    
    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.stage: Optional[LatencyStage] = None
        self.symbol: Optional[str] = None
        self.metadata: Dict[str, Any] = {}
    
    def start(self, stage: LatencyStage, symbol: str = "", **metadata) -> None:
        """Start timing a latency measurement"""
        self.stage = stage
        self.symbol = symbol
        self.metadata = metadata
        self.start_time = time.perf_counter_ns()
        self.end_time = None
    
    def stop(self) -> float:
        """Stop timing and return duration in milliseconds"""
        if self.start_time is None:
            return 0.0
        
        self.end_time = time.perf_counter_ns()
        duration_ns = self.end_time - self.start_time
        duration_ms = duration_ns / 1_000_000.0
        
        return duration_ms
    
    def get_measurement(self) -> Optional[LatencyMeasurement]:
        """Get latency measurement if timing is complete"""
        if self.start_time is None or self.stage is None:
            return None
        
        # Calculate duration if not already stopped
        if self.end_time is None:
            self.end_time = time.perf_counter_ns()
        
        duration_ns = self.end_time - self.start_time
        duration_ms = duration_ns / 1_000_000.0
        
        return LatencyMeasurement(
            timestamp=time.time(),
            stage=self.stage,
            duration_ms=duration_ms,
            symbol=self.symbol or "",
            thread_id=threading.get_ident(),
            cpu_usage=psutil.cpu_percent(),
            memory_usage=psutil.virtual_memory().percent,
            metadata=self.metadata
        )

class LatencyCollector:
    """Latency data collector and analyzer"""
    
    def __init__(self, max_measurements: int = 10000):
        self.max_measurements = max_measurements
        self.measurements: Dict[LatencyStage, deque] = defaultdict(
            lambda: deque(maxlen=max_measurements)
        )
        self.stage_stats: Dict[LatencyStage, LatencyStats] = {}
        self.lock = threading.RLock()
        self.start_time = time.time()
    
    def add_measurement(self, measurement: LatencyMeasurement) -> None:
        """Add a latency measurement"""
        with self.lock:
            self.measurements[measurement.stage].append(measurement)
            self._update_stage_stats(measurement.stage)
    
    def _update_stage_stats(self, stage: LatencyStage) -> None:
        """Update statistics for a stage"""
        if stage not in self.measurements or not self.measurements[stage]:
            return
        
        measurements = list(self.measurements[stage])
        durations = [m.duration_ms for m in measurements]
        
        if not durations:
            return
        
        # Calculate basic statistics
        count = len(durations)
        min_ms = min(durations)
        max_ms = max(durations)
        mean_ms = statistics.mean(durations)
        median_ms = statistics.median(durations)
        std_dev_ms = statistics.stdev(durations) if len(durations) > 1 else 0.0
        
        # Calculate percentiles
        sorted_durations = sorted(durations)
        p50_ms = np.percentile(sorted_durations, 50)
        p95_ms = np.percentile(sorted_durations, 95)
        p99_ms = np.percentile(sorted_durations, 99)
        
        # Calculate trend
        recent_trend = self._calculate_trend(stage)
        
        self.stage_stats[stage] = LatencyStats(
            stage=stage,
            count=count,
            min_ms=min_ms,
            max_ms=max_ms,
            mean_ms=mean_ms,
            median_ms=median_ms,
            p50_ms=p50_ms,
            p95_ms=p95_ms,
            p99_ms=p99_ms,
            std_dev_ms=std_dev_ms,
            recent_trend=recent_trend
        )
    
    def _calculate_trend(self, stage: LatencyStage) -> str:
        """Calculate recent trend for a stage"""
        if stage not in self.measurements or len(self.measurements[stage]) < 10:
            return "stable"
        
        measurements = list(self.measurements[stage])
        recent_measurements = measurements[-10:]  # Last 10 measurements
        older_measurements = measurements[-20:-10] if len(measurements) >= 20 else measurements[:-10]
        
        if not older_measurements:
            return "stable"
        
        recent_avg = statistics.mean([m.duration_ms for m in recent_measurements])
        older_avg = statistics.mean([m.duration_ms for m in older_measurements])
        
        if recent_avg < older_avg * 0.9:  # 10% improvement
            return "improving"
        elif recent_avg > older_avg * 1.1:  # 10% degradation
            return "degrading"
        else:
            return "stable"
    
    def get_stage_stats(self, stage: LatencyStage) -> Optional[LatencyStats]:
        """Get statistics for a specific stage"""
        return self.stage_stats.get(stage)
    
    def get_all_stats(self) -> Dict[LatencyStage, LatencyStats]:
        """Get statistics for all stages"""
        return self.stage_stats.copy()
    
    def get_overall_stats(self) -> LatencyStats:
        """Get overall latency statistics"""
        all_durations = []
        for stage_measurements in self.measurements.values():
            all_durations.extend([m.duration_ms for m in stage_measurements])
        
        if not all_durations:
            return LatencyStats(stage=LatencyStage.TICK_INGESTION)
        
        # Calculate overall statistics
        count = len(all_durations)
        min_ms = min(all_durations)
        max_ms = max(all_durations)
        mean_ms = statistics.mean(all_durations)
        median_ms = statistics.median(all_durations)
        std_dev_ms = statistics.stdev(all_durations) if len(all_durations) > 1 else 0.0
        
        # Calculate percentiles
        sorted_durations = sorted(all_durations)
        p50_ms = np.percentile(sorted_durations, 50)
        p95_ms = np.percentile(sorted_durations, 95)
        p99_ms = np.percentile(sorted_durations, 99)
        
        return LatencyStats(
            stage=LatencyStage.TICK_INGESTION,  # Use as overall
            count=count,
            min_ms=min_ms,
            max_ms=max_ms,
            mean_ms=mean_ms,
            median_ms=median_ms,
            p50_ms=p50_ms,
            p95_ms=p95_ms,
            p99_ms=p99_ms,
            std_dev_ms=std_dev_ms,
            recent_trend="stable"
        )

class HardwareProfiler:
    """Hardware profiling and analysis"""
    
    def __init__(self):
        self.profile: Optional[HardwareProfile] = None
        self._profile_hardware()
    
    def _profile_hardware(self) -> None:
        """Profile the current hardware"""
        # CPU information
        cpu_count = psutil.cpu_count(logical=True)
        cpu_freq = psutil.cpu_freq()
        cpu_freq_mhz = cpu_freq.max if cpu_freq else 0.0
        
        # Memory information
        memory = psutil.virtual_memory()
        memory_gb = memory.total / (1024**3)
        
        # Disk information
        disk_type = "SSD" if self._is_ssd() else "HDD"
        
        # OS information
        os_type = platform.system()
        python_version = platform.python_version()
        
        # Determine hardware type
        hardware_type = self._classify_hardware(cpu_count, memory_gb, disk_type)
        
        # Calculate performance score
        performance_score = self._calculate_performance_score(
            cpu_count, cpu_freq_mhz, memory_gb, disk_type
        )
        
        self.profile = HardwareProfile(
            cpu_count=cpu_count,
            cpu_freq_mhz=cpu_freq_mhz,
            memory_gb=memory_gb,
            disk_type=disk_type,
            os_type=os_type,
            python_version=python_version,
            hardware_type=hardware_type,
            performance_score=performance_score
        )
    
    def _is_ssd(self) -> bool:
        """Check if the system has SSD storage"""
        try:
            # Check for SSD indicators
            for disk in psutil.disk_partitions():
                if disk.fstype and 'ntfs' in disk.fstype.lower():
                    # On Windows, check if it's likely an SSD
                    return True  # Simplified check
            return False
        except:
            return False  # Assume HDD if can't determine
    
    def _classify_hardware(self, cpu_count: int, memory_gb: float, disk_type: str) -> HardwareType:
        """Classify hardware type"""
        if memory_gb >= 16 and cpu_count >= 8 and disk_type == "SSD":
            return HardwareType.HIGH_END
        elif memory_gb >= 8 and cpu_count >= 4:
            return HardwareType.MID_RANGE
        else:
            return HardwareType.LOW_END
    
    def _calculate_performance_score(self, cpu_count: int, cpu_freq_mhz: float, 
                                   memory_gb: float, disk_type: str) -> float:
        """Calculate hardware performance score (0-100)"""
        # CPU score (0-40 points)
        cpu_score = min(40, (cpu_count * cpu_freq_mhz / 1000) * 0.1)
        
        # Memory score (0-30 points)
        memory_score = min(30, memory_gb * 2)
        
        # Disk score (0-30 points)
        disk_score = 30 if disk_type == "SSD" else 10
        
        return min(100, cpu_score + memory_score + disk_score)
    
    def get_profile(self) -> HardwareProfile:
        """Get hardware profile"""
        return self.profile

class LatencyValidator:
    """Main latency validation system"""
    
    def __init__(self, target_p95_ms: float = 200.0):
        self.target_p95_ms = target_p95_ms
        self.collector = LatencyCollector()
        self.hardware_profiler = HardwareProfiler()
        self.timers: Dict[str, LatencyTimer] = {}
        self.lock = threading.RLock()
        self.start_time = time.time()
    
    def start_timer(self, timer_id: str, stage: LatencyStage, 
                   symbol: str = "", **metadata) -> None:
        """Start a latency timer"""
        with self.lock:
            if timer_id not in self.timers:
                self.timers[timer_id] = LatencyTimer()
            
            self.timers[timer_id].start(stage, symbol, **metadata)
    
    def stop_timer(self, timer_id: str) -> Optional[LatencyMeasurement]:
        """Stop a latency timer and get measurement"""
        with self.lock:
            if timer_id not in self.timers:
                return None
            
            measurement = self.timers[timer_id].get_measurement()
            if measurement:
                self.collector.add_measurement(measurement)
            
            return measurement
    
    def measure_latency(self, stage: LatencyStage, symbol: str = "", 
                       **metadata) -> 'LatencyContext':
        """Context manager for measuring latency"""
        return LatencyContext(self, stage, symbol, **metadata)
    
    def validate_latency_target(self) -> Dict[str, Any]:
        """Validate if system meets latency targets"""
        overall_stats = self.collector.get_overall_stats()
        stage_stats = self.collector.get_all_stats()
        hardware_profile = self.hardware_profiler.get_profile()
        
        # Check if p95 meets target
        meets_target = overall_stats.p95_ms <= self.target_p95_ms
        
        # Determine latency level
        if overall_stats.p95_ms < 50:
            latency_level = LatencyLevel.EXCELLENT
        elif overall_stats.p95_ms < 100:
            latency_level = LatencyLevel.GOOD
        elif overall_stats.p95_ms < 200:
            latency_level = LatencyLevel.ACCEPTABLE
        else:
            latency_level = LatencyLevel.POOR
        
        # Analyze stage performance
        stage_analysis = {}
        for stage, stats in stage_stats.items():
            stage_analysis[stage.value] = {
                'p95_ms': stats.p95_ms,
                'meets_target': stats.p95_ms <= self.target_p95_ms,
                'trend': stats.recent_trend,
                'count': stats.count
            }
        
        # Generate recommendations
        recommendations = self._generate_recommendations(overall_stats, stage_stats, hardware_profile)
        
        return {
            'overall_p95_ms': overall_stats.p95_ms,
            'target_p95_ms': self.target_p95_ms,
            'meets_target': meets_target,
            'latency_level': latency_level.value,
            'overall_stats': asdict(overall_stats),
            'stage_analysis': stage_analysis,
            'hardware_profile': asdict(hardware_profile),
            'recommendations': recommendations,
            'uptime_seconds': time.time() - self.start_time
        }
    
    def _generate_recommendations(self, overall_stats: LatencyStats, 
                                stage_stats: Dict[LatencyStage, LatencyStats],
                                hardware_profile: HardwareProfile) -> List[str]:
        """Generate performance recommendations"""
        recommendations = []
        
        # Overall latency recommendations
        if overall_stats.p95_ms > self.target_p95_ms:
            recommendations.append(f"Overall p95 latency ({overall_stats.p95_ms:.1f}ms) exceeds target ({self.target_p95_ms}ms)")
        
        # Stage-specific recommendations
        for stage, stats in stage_stats.items():
            if stats.p95_ms > self.target_p95_ms:
                recommendations.append(f"{stage.value} stage p95 latency ({stats.p95_ms:.1f}ms) exceeds target")
            
            if stats.recent_trend == "degrading":
                recommendations.append(f"{stage.value} stage showing degrading performance trend")
        
        # Hardware-specific recommendations
        if hardware_profile.hardware_type == HardwareType.LOW_END:
            recommendations.append("Hardware is low-end. Consider upgrading for better performance")
        
        if hardware_profile.performance_score < 50:
            recommendations.append("Hardware performance score is low. Consider system optimization")
        
        # Memory recommendations
        if hardware_profile.memory_gb < 8:
            recommendations.append("Low memory detected. Consider increasing RAM")
        
        # CPU recommendations
        if hardware_profile.cpu_count < 4:
            recommendations.append("Low CPU core count. Consider upgrading CPU")
        
        return recommendations
    
    def get_latency_report(self) -> Dict[str, Any]:
        """Get comprehensive latency report"""
        return self.validate_latency_target()

class LatencyContext:
    """Context manager for latency measurement"""
    
    def __init__(self, validator: LatencyValidator, stage: LatencyStage, 
                 symbol: str = "", **metadata):
        self.validator = validator
        self.stage = stage
        self.symbol = symbol
        self.metadata = metadata
        self.timer_id = f"{stage.value}_{int(time.time() * 1000)}"
    
    def __enter__(self):
        self.validator.start_timer(self.timer_id, self.stage, self.symbol, **self.metadata)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.validator.stop_timer(self.timer_id)

# Global latency validator
_latency_validator: Optional[LatencyValidator] = None

def get_latency_validator() -> LatencyValidator:
    """Get global latency validator instance"""
    global _latency_validator
    if _latency_validator is None:
        _latency_validator = LatencyValidator()
    return _latency_validator

def measure_latency(stage: LatencyStage, symbol: str = "", **metadata) -> LatencyContext:
    """Measure latency for a stage"""
    validator = get_latency_validator()
    return validator.measure_latency(stage, symbol, **metadata)

def validate_latency_target() -> Dict[str, Any]:
    """Validate latency targets"""
    validator = get_latency_validator()
    return validator.validate_latency_target()

def get_latency_report() -> Dict[str, Any]:
    """Get latency report"""
    validator = get_latency_validator()
    return validator.get_latency_report()

if __name__ == "__main__":
    # Example usage
    validator = get_latency_validator()
    
    # Measure latency for different stages
    with measure_latency(LatencyStage.TICK_INGESTION, "BTCUSDc"):
        time.sleep(0.001)  # Simulate work
    
    with measure_latency(LatencyStage.VWAP_CALCULATION, "BTCUSDc"):
        time.sleep(0.005)  # Simulate work
    
    with measure_latency(LatencyStage.DECISION_MAKING, "BTCUSDc"):
        time.sleep(0.002)  # Simulate work
    
    # Get latency report
    report = get_latency_report()
    
    print(f"Latency Validation Report:")
    print(f"Overall P95 Latency: {report['overall_p95_ms']:.2f}ms")
    print(f"Target P95 Latency: {report['target_p95_ms']}ms")
    print(f"Meets Target: {report['meets_target']}")
    print(f"Latency Level: {report['latency_level']}")
    
    if report['recommendations']:
        print("\nRecommendations:")
        for rec in report['recommendations']:
            print(f"- {rec}")
