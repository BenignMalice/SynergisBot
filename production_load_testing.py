#!/usr/bin/env python3
"""
Production Load Testing System for TelegramMoneyBot v8.0
Comprehensive load testing, performance validation, and production readiness assessment
"""

import asyncio
import json
import time
import logging
import psutil
import threading
import requests
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import concurrent.futures
import statistics
import numpy as np
from collections import defaultdict, deque

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LoadTestType(Enum):
    """Load test types"""
    STRESS = "stress"
    SPIKE = "spike"
    VOLUME = "volume"
    ENDURANCE = "endurance"
    SCALABILITY = "scalability"

class TestResult(Enum):
    """Test result status"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    CRITICAL = "critical"

class PerformanceMetric(Enum):
    """Performance metrics"""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_USAGE = "disk_usage"
    NETWORK_USAGE = "network_usage"
    ERROR_RATE = "error_rate"
    RESPONSE_TIME = "response_time"

@dataclass
class LoadTestConfig:
    """Load test configuration"""
    test_id: str
    test_type: LoadTestType
    duration_minutes: int
    concurrent_users: int
    ramp_up_minutes: int
    ramp_down_minutes: int
    target_endpoints: List[str]
    expected_latency_ms: float
    expected_throughput_rps: float
    max_cpu_usage: float
    max_memory_usage: float
    max_error_rate: float

@dataclass
class PerformanceMeasurement:
    """Performance measurement"""
    timestamp: datetime
    metric: PerformanceMetric
    value: float
    unit: str
    component: str
    test_id: str

@dataclass
class LoadTestResult:
    """Load test result"""
    test_id: str
    test_type: LoadTestType
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_latency_ms: float
    throughput_rps: float
    peak_cpu_usage: float
    peak_memory_usage: float
    peak_disk_usage: float
    error_rate: float
    result: TestResult
    issues_found: List[str]
    recommendations: List[str]

class ProductionLoadTesting:
    """Production load testing and validation system"""
    
    def __init__(self, config_path: str = "load_testing_config.json"):
        self.config = self._load_config(config_path)
        self.test_configs: Dict[str, LoadTestConfig] = {}
        self.measurements: List[PerformanceMeasurement] = []
        self.test_results: List[LoadTestResult] = []
        self.running = False
        
        # Initialize test configurations
        self._initialize_test_configs()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load load testing configuration"""
        default_config = {
            "load_tests": {
                "stress_test": {
                    "test_id": "stress_test",
                    "test_type": "stress",
                    "duration_minutes": 30,
                    "concurrent_users": 100,
                    "ramp_up_minutes": 5,
                    "ramp_down_minutes": 5,
                    "target_endpoints": [
                        "http://localhost:8000/health",
                        "http://localhost:8000/api/trading/status",
                        "http://localhost:8000/api/analysis/btcusdc"
                    ],
                    "expected_latency_ms": 200.0,
                    "expected_throughput_rps": 100.0,
                    "max_cpu_usage": 80.0,
                    "max_memory_usage": 85.0,
                    "max_error_rate": 1.0
                },
                "spike_test": {
                    "test_id": "spike_test",
                    "test_type": "spike",
                    "duration_minutes": 15,
                    "concurrent_users": 500,
                    "ramp_up_minutes": 2,
                    "ramp_down_minutes": 2,
                    "target_endpoints": [
                        "http://localhost:8000/health",
                        "http://localhost:8000/api/trading/status"
                    ],
                    "expected_latency_ms": 500.0,
                    "expected_throughput_rps": 200.0,
                    "max_cpu_usage": 90.0,
                    "max_memory_usage": 90.0,
                    "max_error_rate": 5.0
                },
                "volume_test": {
                    "test_id": "volume_test",
                    "test_type": "volume",
                    "duration_minutes": 60,
                    "concurrent_users": 50,
                    "ramp_up_minutes": 10,
                    "ramp_down_minutes": 10,
                    "target_endpoints": [
                        "http://localhost:8000/api/trading/status",
                        "http://localhost:8000/api/analysis/btcusdc",
                        "http://localhost:8000/api/analysis/xauusdc"
                    ],
                    "expected_latency_ms": 150.0,
                    "expected_throughput_rps": 50.0,
                    "max_cpu_usage": 70.0,
                    "max_memory_usage": 75.0,
                    "max_error_rate": 0.5
                },
                "endurance_test": {
                    "test_id": "endurance_test",
                    "test_type": "endurance",
                    "duration_minutes": 480,
                    "concurrent_users": 25,
                    "ramp_up_minutes": 30,
                    "ramp_down_minutes": 30,
                    "target_endpoints": [
                        "http://localhost:8000/health",
                        "http://localhost:8000/api/trading/status"
                    ],
                    "expected_latency_ms": 200.0,
                    "expected_throughput_rps": 25.0,
                    "max_cpu_usage": 60.0,
                    "max_memory_usage": 70.0,
                    "max_error_rate": 0.1
                },
                "scalability_test": {
                    "test_id": "scalability_test",
                    "test_type": "scalability",
                    "duration_minutes": 45,
                    "concurrent_users": 200,
                    "ramp_up_minutes": 15,
                    "ramp_down_minutes": 15,
                    "target_endpoints": [
                        "http://localhost:8000/api/trading/status",
                        "http://localhost:8000/api/analysis/btcusdc"
                    ],
                    "expected_latency_ms": 300.0,
                    "expected_throughput_rps": 100.0,
                    "max_cpu_usage": 85.0,
                    "max_memory_usage": 80.0,
                    "max_error_rate": 2.0
                }
            },
            "performance_thresholds": {
                "latency_p95_ms": 200.0,
                "latency_p99_ms": 500.0,
                "max_latency_ms": 1000.0,
                "min_throughput_rps": 10.0,
                "max_cpu_usage_percent": 85.0,
                "max_memory_usage_percent": 85.0,
                "max_disk_usage_percent": 90.0,
                "max_error_rate_percent": 1.0
            },
            "monitoring": {
                "metrics_collection_interval": 1.0,
                "system_monitoring_enabled": True,
                "database_monitoring_enabled": True,
                "network_monitoring_enabled": True,
                "alert_on_threshold_breach": True
            }
        }
        
        try:
            if Path(config_path).exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
                # Merge with defaults
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
            else:
                # Save default config
                with open(config_path, 'w') as f:
                    json.dump(default_config, f, indent=2)
                return default_config
        except Exception as e:
            logger.error(f"Error loading load testing config: {e}")
            return default_config
    
    def _initialize_test_configs(self):
        """Initialize test configurations"""
        try:
            for test_id, test_data in self.config["load_tests"].items():
                test_config = LoadTestConfig(
                    test_id=test_data["test_id"],
                    test_type=LoadTestType(test_data["test_type"]),
                    duration_minutes=test_data["duration_minutes"],
                    concurrent_users=test_data["concurrent_users"],
                    ramp_up_minutes=test_data["ramp_up_minutes"],
                    ramp_down_minutes=test_data["ramp_down_minutes"],
                    target_endpoints=test_data["target_endpoints"],
                    expected_latency_ms=test_data["expected_latency_ms"],
                    expected_throughput_rps=test_data["expected_throughput_rps"],
                    max_cpu_usage=test_data["max_cpu_usage"],
                    max_memory_usage=test_data["max_memory_usage"],
                    max_error_rate=test_data["max_error_rate"]
                )
                self.test_configs[test_id] = test_config
            
            logger.info(f"Initialized {len(self.test_configs)} load test configurations")
            
        except Exception as e:
            logger.error(f"Error initializing test configurations: {e}")
    
    async def run_load_test(self, test_id: str) -> LoadTestResult:
        """Run a specific load test"""
        try:
            if test_id not in self.test_configs:
                raise ValueError(f"Test configuration {test_id} not found")
            
            test_config = self.test_configs[test_id]
            logger.info(f"Starting load test: {test_id}")
            
            # Initialize test result
            test_result = LoadTestResult(
                test_id=test_id,
                test_type=test_config.test_type,
                start_time=datetime.now(),
                end_time=datetime.now(),
                duration_seconds=0.0,
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                average_latency_ms=0.0,
                p95_latency_ms=0.0,
                p99_latency_ms=0.0,
                max_latency_ms=0.0,
                throughput_rps=0.0,
                peak_cpu_usage=0.0,
                peak_memory_usage=0.0,
                peak_disk_usage=0.0,
                error_rate=0.0,
                result=TestResult.PASSED,
                issues_found=[],
                recommendations=[]
            )
            
            # Start system monitoring
            monitoring_task = asyncio.create_task(self._monitor_system_performance(test_id))
            
            # Run the load test
            await self._execute_load_test(test_config, test_result)
            
            # Stop monitoring
            monitoring_task.cancel()
            
            # Calculate final metrics
            test_result.end_time = datetime.now()
            test_result.duration_seconds = (test_result.end_time - test_result.start_time).total_seconds()
            
            # Analyze results
            await self._analyze_test_results(test_result)
            
            # Store result
            self.test_results.append(test_result)
            
            logger.info(f"Load test {test_id} completed: {test_result.result.value}")
            return test_result
            
        except Exception as e:
            logger.error(f"Error running load test {test_id}: {e}")
            raise
    
    async def _execute_load_test(self, test_config: LoadTestConfig, test_result: LoadTestResult):
        """Execute the load test"""
        try:
            # Calculate ramp-up and ramp-down steps
            ramp_up_steps = test_config.ramp_up_minutes * 60  # seconds
            ramp_down_steps = test_config.ramp_down_minutes * 60  # seconds
            steady_state_duration = (test_config.duration_minutes - test_config.ramp_up_minutes - test_config.ramp_down_minutes) * 60
            
            # Ramp-up phase
            logger.info(f"Ramping up to {test_config.concurrent_users} users over {test_config.ramp_up_minutes} minutes")
            await self._ramp_up_users(test_config, ramp_up_steps, test_result)
            
            # Steady state phase
            logger.info(f"Running steady state for {test_config.duration_minutes - test_config.ramp_up_minutes - test_config.ramp_down_minutes} minutes")
            await self._steady_state_test(test_config, steady_state_duration, test_result)
            
            # Ramp-down phase
            logger.info(f"Ramping down over {test_config.ramp_down_minutes} minutes")
            await self._ramp_down_users(test_config, ramp_down_steps, test_result)
            
        except Exception as e:
            logger.error(f"Error executing load test: {e}")
            raise
    
    async def _ramp_up_users(self, test_config: LoadTestConfig, duration_seconds: int, test_result: LoadTestResult):
        """Ramp up concurrent users"""
        try:
            steps = 10  # Number of ramp-up steps
            users_per_step = test_config.concurrent_users // steps
            step_duration = duration_seconds // steps
            
            for step in range(steps):
                current_users = users_per_step * (step + 1)
                logger.info(f"Ramp-up step {step + 1}/{steps}: {current_users} users")
                
                # Create user tasks
                tasks = []
                for user_id in range(current_users):
                    task = asyncio.create_task(self._simulate_user(test_config, user_id, test_result))
                    tasks.append(task)
                
                # Wait for step duration
                await asyncio.sleep(step_duration)
                
                # Cancel tasks (they will be recreated in next step)
                for task in tasks:
                    if not task.done():
                        task.cancel()
                
        except Exception as e:
            logger.error(f"Error in ramp-up phase: {e}")
    
    async def _steady_state_test(self, test_config: LoadTestConfig, duration_seconds: int, test_result: LoadTestResult):
        """Run steady state test"""
        try:
            # Create all user tasks
            tasks = []
            for user_id in range(test_config.concurrent_users):
                task = asyncio.create_task(self._simulate_user(test_config, user_id, test_result))
                tasks.append(task)
            
            # Wait for steady state duration
            await asyncio.sleep(duration_seconds)
            
            # Cancel all tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            
        except Exception as e:
            logger.error(f"Error in steady state test: {e}")
    
    async def _ramp_down_users(self, test_config: LoadTestConfig, duration_seconds: int, test_result: LoadTestResult):
        """Ramp down concurrent users"""
        try:
            steps = 10  # Number of ramp-down steps
            users_per_step = test_config.concurrent_users // steps
            step_duration = duration_seconds // steps
            
            for step in range(steps):
                current_users = test_config.concurrent_users - (users_per_step * step)
                logger.info(f"Ramp-down step {step + 1}/{steps}: {current_users} users")
                
                # Create user tasks
                tasks = []
                for user_id in range(current_users):
                    task = asyncio.create_task(self._simulate_user(test_config, user_id, test_result))
                    tasks.append(task)
                
                # Wait for step duration
                await asyncio.sleep(step_duration)
                
                # Cancel tasks
                for task in tasks:
                    if not task.done():
                        task.cancel()
                
        except Exception as e:
            logger.error(f"Error in ramp-down phase: {e}")
    
    async def _simulate_user(self, test_config: LoadTestConfig, user_id: int, test_result: LoadTestResult):
        """Simulate a single user"""
        try:
            while True:
                # Select random endpoint
                endpoint = np.random.choice(test_config.target_endpoints)
                
                # Make request
                start_time = time.time()
                try:
                    response = requests.get(endpoint, timeout=10)
                    latency_ms = (time.time() - start_time) * 1000
                    
                    if response.status_code == 200:
                        test_result.successful_requests += 1
                    else:
                        test_result.failed_requests += 1
                    
                    # Record latency
                    test_result.average_latency_ms = (test_result.average_latency_ms + latency_ms) / 2
                    test_result.max_latency_ms = max(test_result.max_latency_ms, latency_ms)
                    
                except Exception as e:
                    test_result.failed_requests += 1
                    logger.debug(f"Request failed for user {user_id}: {e}")
                
                test_result.total_requests += 1
                
                # Wait between requests (simulate user think time)
                await asyncio.sleep(np.random.uniform(0.1, 2.0))
                
        except asyncio.CancelledError:
            # Task was cancelled, which is expected
            pass
        except Exception as e:
            logger.error(f"Error simulating user {user_id}: {e}")
    
    async def _monitor_system_performance(self, test_id: str):
        """Monitor system performance during test"""
        try:
            while True:
                # Collect system metrics
                cpu_usage = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                # Record measurements
                current_time = datetime.now()
                
                self.measurements.append(PerformanceMeasurement(
                    timestamp=current_time,
                    metric=PerformanceMetric.CPU_USAGE,
                    value=cpu_usage,
                    unit="percent",
                    component="system",
                    test_id=test_id
                ))
                
                self.measurements.append(PerformanceMeasurement(
                    timestamp=current_time,
                    metric=PerformanceMetric.MEMORY_USAGE,
                    value=memory.percent,
                    unit="percent",
                    component="system",
                    test_id=test_id
                ))
                
                self.measurements.append(PerformanceMeasurement(
                    timestamp=current_time,
                    metric=PerformanceMetric.DISK_USAGE,
                    value=disk.percent,
                    unit="percent",
                    component="system",
                    test_id=test_id
                ))
                
                # Wait for next measurement
                await asyncio.sleep(self.config["monitoring"]["metrics_collection_interval"])
                
        except asyncio.CancelledError:
            # Task was cancelled, which is expected
            pass
        except Exception as e:
            logger.error(f"Error monitoring system performance: {e}")
    
    async def _analyze_test_results(self, test_result: LoadTestResult):
        """Analyze test results and determine pass/fail"""
        try:
            # Calculate throughput
            test_result.throughput_rps = test_result.total_requests / test_result.duration_seconds
            
            # Calculate error rate
            test_result.error_rate = (test_result.failed_requests / test_result.total_requests) * 100 if test_result.total_requests > 0 else 0
            
            # Calculate percentiles
            latencies = [m.value for m in self.measurements if m.metric == PerformanceMetric.LATENCY and m.test_id == test_result.test_id]
            if latencies:
                test_result.p95_latency_ms = np.percentile(latencies, 95)
                test_result.p99_latency_ms = np.percentile(latencies, 99)
            
            # Get peak resource usage
            cpu_measurements = [m.value for m in self.measurements if m.metric == PerformanceMetric.CPU_USAGE and m.test_id == test_result.test_id]
            memory_measurements = [m.value for m in self.measurements if m.metric == PerformanceMetric.MEMORY_USAGE and m.test_id == test_result.test_id]
            disk_measurements = [m.value for m in self.measurements if m.metric == PerformanceMetric.DISK_USAGE and m.test_id == test_result.test_id]
            
            test_result.peak_cpu_usage = max(cpu_measurements) if cpu_measurements else 0
            test_result.peak_memory_usage = max(memory_measurements) if memory_measurements else 0
            test_result.peak_disk_usage = max(disk_measurements) if disk_measurements else 0
            
            # Check against thresholds
            thresholds = self.config["performance_thresholds"]
            issues = []
            
            # Check latency
            if test_result.p95_latency_ms > thresholds["latency_p95_ms"]:
                issues.append(f"P95 latency {test_result.p95_latency_ms:.2f}ms exceeds threshold {thresholds['latency_p95_ms']}ms")
            
            if test_result.p99_latency_ms > thresholds["latency_p99_ms"]:
                issues.append(f"P99 latency {test_result.p99_latency_ms:.2f}ms exceeds threshold {thresholds['latency_p99_ms']}ms")
            
            # Check throughput
            if test_result.throughput_rps < thresholds["min_throughput_rps"]:
                issues.append(f"Throughput {test_result.throughput_rps:.2f} RPS below minimum {thresholds['min_throughput_rps']} RPS")
            
            # Check resource usage
            if test_result.peak_cpu_usage > thresholds["max_cpu_usage_percent"]:
                issues.append(f"Peak CPU usage {test_result.peak_cpu_usage:.2f}% exceeds threshold {thresholds['max_cpu_usage_percent']}%")
            
            if test_result.peak_memory_usage > thresholds["max_memory_usage_percent"]:
                issues.append(f"Peak memory usage {test_result.peak_memory_usage:.2f}% exceeds threshold {thresholds['max_memory_usage_percent']}%")
            
            # Check error rate
            if test_result.error_rate > thresholds["max_error_rate_percent"]:
                issues.append(f"Error rate {test_result.error_rate:.2f}% exceeds threshold {thresholds['max_error_rate_percent']}%")
            
            # Determine result
            if not issues:
                test_result.result = TestResult.PASSED
            elif len(issues) <= 2:
                test_result.result = TestResult.WARNING
            else:
                test_result.result = TestResult.FAILED
            
            test_result.issues_found = issues
            
            # Generate recommendations
            test_result.recommendations = self._generate_recommendations(test_result)
            
        except Exception as e:
            logger.error(f"Error analyzing test results: {e}")
    
    def _generate_recommendations(self, test_result: LoadTestResult) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        if test_result.peak_cpu_usage > 80:
            recommendations.append("Consider CPU optimization or horizontal scaling")
        
        if test_result.peak_memory_usage > 80:
            recommendations.append("Consider memory optimization or increasing RAM")
        
        if test_result.p95_latency_ms > 200:
            recommendations.append("Consider database optimization or caching")
        
        if test_result.error_rate > 1:
            recommendations.append("Investigate and fix error sources")
        
        if test_result.throughput_rps < 50:
            recommendations.append("Consider performance tuning or infrastructure upgrades")
        
        if not recommendations:
            recommendations.append("System performance is within acceptable limits")
        
        return recommendations
    
    async def run_all_load_tests(self) -> List[LoadTestResult]:
        """Run all configured load tests"""
        try:
            results = []
            
            for test_id in self.test_configs.keys():
                logger.info(f"Running load test: {test_id}")
                result = await self.run_load_test(test_id)
                results.append(result)
                
                # Wait between tests
                await asyncio.sleep(60)  # 1 minute between tests
            
            return results
            
        except Exception as e:
            logger.error(f"Error running all load tests: {e}")
            return []
    
    def get_test_summary(self) -> Dict[str, Any]:
        """Get summary of all test results"""
        try:
            if not self.test_results:
                return {"message": "No test results available"}
            
            total_tests = len(self.test_results)
            passed_tests = len([r for r in self.test_results if r.result == TestResult.PASSED])
            failed_tests = len([r for r in self.test_results if r.result == TestResult.FAILED])
            warning_tests = len([r for r in self.test_results if r.result == TestResult.WARNING])
            
            return {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "warning_tests": warning_tests,
                "pass_rate": (passed_tests / total_tests) * 100 if total_tests > 0 else 0,
                "test_results": [asdict(result) for result in self.test_results]
            }
            
        except Exception as e:
            logger.error(f"Error generating test summary: {e}")
            return {}

async def main():
    """Main function for testing load testing system"""
    load_tester = ProductionLoadTesting()
    
    # Run all load tests
    results = await load_tester.run_all_load_tests()
    
    # Print summary
    summary = load_tester.get_test_summary()
    print(f"Load Testing Summary: {summary}")

if __name__ == "__main__":
    asyncio.run(main())
