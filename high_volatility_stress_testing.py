#!/usr/bin/env python3
"""
High Volatility Stress Testing for TelegramMoneyBot v8.0
Comprehensive stress testing under high volatility market conditions
"""

import asyncio
import json
import logging
import time
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import statistics
from collections import defaultdict, deque
import psutil
import threading
import queue

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VolatilityLevel(Enum):
    """Volatility levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"
    CRITICAL = "critical"

class StressTestType(Enum):
    """Stress test types"""
    PRICE_SPIKE = "price_spike"
    VOLUME_SURGE = "volume_surge"
    SPREAD_WIDENING = "spread_widening"
    MARKET_CRASH = "market_crash"
    FLASH_CRASH = "flash_crash"
    NEWS_EVENT = "news_event"
    LIQUIDITY_CRISIS = "liquidity_crisis"

class SystemResponse(Enum):
    """System response types"""
    NORMAL = "normal"
    DEGRADED = "degraded"
    STRESSED = "stressed"
    OVERLOADED = "overloaded"
    FAILED = "failed"

@dataclass
class VolatilityEvent:
    """Volatility event"""
    event_id: str
    event_type: StressTestType
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    volatility_level: VolatilityLevel
    price_change_percent: float
    volume_multiplier: float
    spread_multiplier: float
    impact_score: float

@dataclass
class SystemMetrics:
    """System metrics during stress test"""
    timestamp: datetime
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    network_usage_percent: float
    latency_ms: float
    throughput_rps: float
    error_rate_percent: float
    queue_depth: int
    processing_time_ms: float

@dataclass
class StressTestResult:
    """Stress test result"""
    test_id: str
    test_type: StressTestType
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    volatility_level: VolatilityLevel
    system_response: SystemResponse
    peak_cpu_usage: float
    peak_memory_usage: float
    peak_latency_ms: float
    min_throughput_rps: float
    max_error_rate: float
    system_stability_score: float
    recovery_time_seconds: float
    events_handled: int
    events_failed: int
    issues_found: List[str]
    recommendations: List[str]
    metrics: List[SystemMetrics]

class HighVolatilityStressTesting:
    """High volatility stress testing system"""
    
    def __init__(self, config_path: str = "high_volatility_stress_config.json"):
        self.config = self._load_config(config_path)
        self.test_results: List[StressTestResult] = []
        self.volatility_events: List[VolatilityEvent] = []
        self.system_metrics: List[SystemMetrics] = []
        self.running = False
        
        # Initialize stress test configurations
        self._initialize_stress_tests()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load high volatility stress testing configuration"""
        default_config = {
            "stress_tests": {
                "price_spike_test": {
                    "test_id": "price_spike_test",
                    "test_type": "price_spike",
                    "duration_minutes": 10,
                    "volatility_level": "high",
                    "price_change_percent": 5.0,
                    "volume_multiplier": 3.0,
                    "spread_multiplier": 2.0,
                    "expected_system_response": "degraded"
                },
                "volume_surge_test": {
                    "test_id": "volume_surge_test",
                    "test_type": "volume_surge",
                    "duration_minutes": 15,
                    "volatility_level": "extreme",
                    "price_change_percent": 2.0,
                    "volume_multiplier": 10.0,
                    "spread_multiplier": 1.5,
                    "expected_system_response": "stressed"
                },
                "spread_widening_test": {
                    "test_id": "spread_widening_test",
                    "test_type": "spread_widening",
                    "duration_minutes": 8,
                    "volatility_level": "high",
                    "price_change_percent": 1.0,
                    "volume_multiplier": 2.0,
                    "spread_multiplier": 5.0,
                    "expected_system_response": "degraded"
                },
                "market_crash_test": {
                    "test_id": "market_crash_test",
                    "test_type": "market_crash",
                    "duration_minutes": 20,
                    "volatility_level": "critical",
                    "price_change_percent": -15.0,
                    "volume_multiplier": 20.0,
                    "spread_multiplier": 10.0,
                    "expected_system_response": "overloaded"
                },
                "flash_crash_test": {
                    "test_id": "flash_crash_test",
                    "test_type": "flash_crash",
                    "duration_minutes": 5,
                    "volatility_level": "critical",
                    "price_change_percent": -25.0,
                    "volume_multiplier": 50.0,
                    "spread_multiplier": 20.0,
                    "expected_system_response": "overloaded"
                },
                "news_event_test": {
                    "test_id": "news_event_test",
                    "test_type": "news_event",
                    "duration_minutes": 30,
                    "volatility_level": "extreme",
                    "price_change_percent": 8.0,
                    "volume_multiplier": 15.0,
                    "spread_multiplier": 3.0,
                    "expected_system_response": "stressed"
                },
                "liquidity_crisis_test": {
                    "test_id": "liquidity_crisis_test",
                    "test_type": "liquidity_crisis",
                    "duration_minutes": 25,
                    "volatility_level": "critical",
                    "price_change_percent": 12.0,
                    "volume_multiplier": 0.1,
                    "spread_multiplier": 15.0,
                    "expected_system_response": "overloaded"
                }
            },
            "volatility_levels": {
                "low": {
                    "volatility_threshold": 0.01,
                    "price_change_range": (-0.5, 0.5),
                    "volume_multiplier_range": (0.5, 1.5),
                    "spread_multiplier_range": (0.8, 1.2)
                },
                "medium": {
                    "volatility_threshold": 0.02,
                    "price_change_range": (-1.0, 1.0),
                    "volume_multiplier_range": (1.0, 2.0),
                    "spread_multiplier_range": (1.0, 1.5)
                },
                "high": {
                    "volatility_threshold": 0.05,
                    "price_change_range": (-3.0, 3.0),
                    "volume_multiplier_range": (2.0, 5.0),
                    "spread_multiplier_range": (1.5, 3.0)
                },
                "extreme": {
                    "volatility_threshold": 0.10,
                    "price_change_range": (-8.0, 8.0),
                    "volume_multiplier_range": (5.0, 15.0),
                    "spread_multiplier_range": (3.0, 8.0)
                },
                "critical": {
                    "volatility_threshold": 0.20,
                    "price_change_range": (-20.0, 20.0),
                    "volume_multiplier_range": (10.0, 50.0),
                    "spread_multiplier_range": (5.0, 20.0)
                }
            },
            "system_thresholds": {
                "cpu_usage_normal": 70.0,
                "cpu_usage_stressed": 85.0,
                "cpu_usage_overloaded": 95.0,
                "memory_usage_normal": 75.0,
                "memory_usage_stressed": 90.0,
                "memory_usage_overloaded": 95.0,
                "latency_normal_ms": 200.0,
                "latency_stressed_ms": 500.0,
                "latency_overloaded_ms": 1000.0,
                "error_rate_normal_percent": 1.0,
                "error_rate_stressed_percent": 5.0,
                "error_rate_overloaded_percent": 10.0
            },
            "monitoring": {
                "metrics_collection_interval": 1.0,
                "system_monitoring_enabled": True,
                "volatility_monitoring_enabled": True,
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
            logger.error(f"Error loading high volatility stress config: {e}")
            return default_config
    
    def _initialize_stress_tests(self):
        """Initialize stress test configurations"""
        try:
            logger.info("Initialized high volatility stress testing configurations")
        except Exception as e:
            logger.error(f"Error initializing stress tests: {e}")
    
    async def run_stress_test(self, test_id: str) -> StressTestResult:
        """Run a specific stress test"""
        try:
            if test_id not in self.config["stress_tests"]:
                raise ValueError(f"Stress test configuration {test_id} not found")
            
            test_config = self.config["stress_tests"][test_id]
            logger.info(f"Starting stress test: {test_id}")
            
            # Initialize test result
            test_result = StressTestResult(
                test_id=test_id,
                test_type=StressTestType(test_config["test_type"]),
                start_time=datetime.now(),
                end_time=datetime.now(),
                duration_seconds=0.0,
                volatility_level=VolatilityLevel(test_config["volatility_level"]),
                system_response=SystemResponse.NORMAL,
                peak_cpu_usage=0.0,
                peak_memory_usage=0.0,
                peak_latency_ms=0.0,
                min_throughput_rps=float('inf'),
                max_error_rate=0.0,
                system_stability_score=0.0,
                recovery_time_seconds=0.0,
                events_handled=0,
                events_failed=0,
                issues_found=[],
                recommendations=[],
                metrics=[]
            )
            
            # Start system monitoring
            monitoring_task = asyncio.create_task(self._monitor_system_metrics(test_id))
            
            # Run the stress test
            await self._execute_stress_test(test_config, test_result)
            
            # Stop monitoring
            monitoring_task.cancel()
            
            # Calculate final metrics
            test_result.end_time = datetime.now()
            test_result.duration_seconds = (test_result.end_time - test_result.start_time).total_seconds()
            
            # Analyze results
            await self._analyze_stress_test_results(test_result)
            
            # Store result
            self.test_results.append(test_result)
            
            logger.info(f"Stress test {test_id} completed: {test_result.system_response.value}")
            return test_result
            
        except Exception as e:
            logger.error(f"Error running stress test {test_id}: {e}")
            raise
    
    async def _execute_stress_test(self, test_config: Dict[str, Any], test_result: StressTestResult):
        """Execute the stress test"""
        try:
            test_type = test_config["test_type"]
            duration_minutes = test_config["duration_minutes"]
            volatility_level = test_config["volatility_level"]
            
            logger.info(f"Executing {test_type} stress test for {duration_minutes} minutes")
            
            # Run test based on type
            if test_type == "price_spike":
                await self._simulate_price_spike(test_config, test_result)
            elif test_type == "volume_surge":
                await self._simulate_volume_surge(test_config, test_result)
            elif test_type == "spread_widening":
                await self._simulate_spread_widening(test_config, test_result)
            elif test_type == "market_crash":
                await self._simulate_market_crash(test_config, test_result)
            elif test_type == "flash_crash":
                await self._simulate_flash_crash(test_config, test_result)
            elif test_type == "news_event":
                await self._simulate_news_event(test_config, test_result)
            elif test_type == "liquidity_crisis":
                await self._simulate_liquidity_crisis(test_config, test_result)
            
        except Exception as e:
            logger.error(f"Error executing stress test: {e}")
            test_result.issues_found.append(f"Stress test execution error: {str(e)}")
    
    async def _simulate_price_spike(self, test_config: Dict[str, Any], test_result: StressTestResult):
        """Simulate price spike stress test"""
        try:
            duration_seconds = test_config["duration_minutes"] * 60
            price_change_percent = test_config["price_change_percent"]
            volume_multiplier = test_config["volume_multiplier"]
            
            logger.info(f"Simulating price spike: {price_change_percent}% change, {volume_multiplier}x volume")
            
            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                # Simulate price spike event
                await self._simulate_volatility_event(
                    StressTestType.PRICE_SPIKE,
                    VolatilityLevel(test_config["volatility_level"]),
                    price_change_percent,
                    volume_multiplier,
                    test_result
                )
                
                # Wait between events
                await asyncio.sleep(np.random.uniform(1, 5))
            
        except Exception as e:
            logger.error(f"Error simulating price spike: {e}")
            test_result.issues_found.append(f"Price spike simulation error: {str(e)}")
    
    async def _simulate_volume_surge(self, test_config: Dict[str, Any], test_result: StressTestResult):
        """Simulate volume surge stress test"""
        try:
            duration_seconds = test_config["duration_minutes"] * 60
            volume_multiplier = test_config["volume_multiplier"]
            
            logger.info(f"Simulating volume surge: {volume_multiplier}x volume")
            
            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                # Simulate volume surge event
                await self._simulate_volatility_event(
                    StressTestType.VOLUME_SURGE,
                    VolatilityLevel(test_config["volatility_level"]),
                    0,  # No price change
                    volume_multiplier,
                    test_result
                )
                
                # Wait between events
                await asyncio.sleep(np.random.uniform(0.5, 2))
            
        except Exception as e:
            logger.error(f"Error simulating volume surge: {e}")
            test_result.issues_found.append(f"Volume surge simulation error: {str(e)}")
    
    async def _simulate_spread_widening(self, test_config: Dict[str, Any], test_result: StressTestResult):
        """Simulate spread widening stress test"""
        try:
            duration_seconds = test_config["duration_minutes"] * 60
            spread_multiplier = test_config["spread_multiplier"]
            
            logger.info(f"Simulating spread widening: {spread_multiplier}x spread")
            
            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                # Simulate spread widening event
                await self._simulate_volatility_event(
                    StressTestType.SPREAD_WIDENING,
                    VolatilityLevel(test_config["volatility_level"]),
                    0,  # No price change
                    1.0,  # No volume change
                    test_result
                )
                
                # Wait between events
                await asyncio.sleep(np.random.uniform(2, 8))
            
        except Exception as e:
            logger.error(f"Error simulating spread widening: {e}")
            test_result.issues_found.append(f"Spread widening simulation error: {str(e)}")
    
    async def _simulate_market_crash(self, test_config: Dict[str, Any], test_result: StressTestResult):
        """Simulate market crash stress test"""
        try:
            duration_seconds = test_config["duration_minutes"] * 60
            price_change_percent = test_config["price_change_percent"]
            volume_multiplier = test_config["volume_multiplier"]
            
            logger.info(f"Simulating market crash: {price_change_percent}% change, {volume_multiplier}x volume")
            
            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                # Simulate market crash event
                await self._simulate_volatility_event(
                    StressTestType.MARKET_CRASH,
                    VolatilityLevel(test_config["volatility_level"]),
                    price_change_percent,
                    volume_multiplier,
                    test_result
                )
                
                # Wait between events
                await asyncio.sleep(np.random.uniform(5, 15))
            
        except Exception as e:
            logger.error(f"Error simulating market crash: {e}")
            test_result.issues_found.append(f"Market crash simulation error: {str(e)}")
    
    async def _simulate_flash_crash(self, test_config: Dict[str, Any], test_result: StressTestResult):
        """Simulate flash crash stress test"""
        try:
            duration_seconds = test_config["duration_minutes"] * 60
            price_change_percent = test_config["price_change_percent"]
            volume_multiplier = test_config["volume_multiplier"]
            
            logger.info(f"Simulating flash crash: {price_change_percent}% change, {volume_multiplier}x volume")
            
            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                # Simulate flash crash event
                await self._simulate_volatility_event(
                    StressTestType.FLASH_CRASH,
                    VolatilityLevel(test_config["volatility_level"]),
                    price_change_percent,
                    volume_multiplier,
                    test_result
                )
                
                # Wait between events
                await asyncio.sleep(np.random.uniform(10, 30))
            
        except Exception as e:
            logger.error(f"Error simulating flash crash: {e}")
            test_result.issues_found.append(f"Flash crash simulation error: {str(e)}")
    
    async def _simulate_news_event(self, test_config: Dict[str, Any], test_result: StressTestResult):
        """Simulate news event stress test"""
        try:
            duration_seconds = test_config["duration_minutes"] * 60
            price_change_percent = test_config["price_change_percent"]
            volume_multiplier = test_config["volume_multiplier"]
            
            logger.info(f"Simulating news event: {price_change_percent}% change, {volume_multiplier}x volume")
            
            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                # Simulate news event
                await self._simulate_volatility_event(
                    StressTestType.NEWS_EVENT,
                    VolatilityLevel(test_config["volatility_level"]),
                    price_change_percent,
                    volume_multiplier,
                    test_result
                )
                
                # Wait between events
                await asyncio.sleep(np.random.uniform(30, 120))
            
        except Exception as e:
            logger.error(f"Error simulating news event: {e}")
            test_result.issues_found.append(f"News event simulation error: {str(e)}")
    
    async def _simulate_liquidity_crisis(self, test_config: Dict[str, Any], test_result: StressTestResult):
        """Simulate liquidity crisis stress test"""
        try:
            duration_seconds = test_config["duration_minutes"] * 60
            volume_multiplier = test_config["volume_multiplier"]
            spread_multiplier = test_config["spread_multiplier"]
            
            logger.info(f"Simulating liquidity crisis: {volume_multiplier}x volume, {spread_multiplier}x spread")
            
            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                # Simulate liquidity crisis event
                await self._simulate_volatility_event(
                    StressTestType.LIQUIDITY_CRISIS,
                    VolatilityLevel(test_config["volatility_level"]),
                    0,  # No price change
                    volume_multiplier,
                    test_result
                )
                
                # Wait between events
                await asyncio.sleep(np.random.uniform(15, 45))
            
        except Exception as e:
            logger.error(f"Error simulating liquidity crisis: {e}")
            test_result.issues_found.append(f"Liquidity crisis simulation error: {str(e)}")
    
    async def _simulate_volatility_event(self, event_type: StressTestType, volatility_level: VolatilityLevel, 
                                       price_change_percent: float, volume_multiplier: float, test_result: StressTestResult):
        """Simulate a volatility event"""
        try:
            # Create volatility event
            event = VolatilityEvent(
                event_id=f"{event_type.value}_{int(time.time())}",
                event_type=event_type,
                start_time=datetime.now(),
                end_time=datetime.now(),
                duration_seconds=0.0,
                volatility_level=volatility_level,
                price_change_percent=price_change_percent,
                volume_multiplier=volume_multiplier,
                spread_multiplier=1.0,
                impact_score=0.0
            )
            
            # Simulate event processing
            start_time = time.time()
            
            # Simulate high-frequency processing
            for _ in range(int(volume_multiplier * 10)):
                # Simulate tick processing
                await asyncio.sleep(np.random.uniform(0.001, 0.01))
                
                # Simulate system stress
                if volatility_level in [VolatilityLevel.EXTREME, VolatilityLevel.CRITICAL]:
                    await asyncio.sleep(np.random.uniform(0.01, 0.05))
            
            # Calculate event metrics
            event.end_time = datetime.now()
            event.duration_seconds = (event.end_time - event.start_time).total_seconds()
            event.impact_score = self._calculate_impact_score(event)
            
            # Store event
            self.volatility_events.append(event)
            test_result.events_handled += 1
            
            # Simulate potential failures
            if np.random.random() < 0.05:  # 5% failure rate
                test_result.events_failed += 1
                test_result.issues_found.append(f"Event processing failed: {event.event_id}")
            
        except Exception as e:
            logger.error(f"Error simulating volatility event: {e}")
            test_result.events_failed += 1
            test_result.issues_found.append(f"Volatility event error: {str(e)}")
    
    def _calculate_impact_score(self, event: VolatilityEvent) -> float:
        """Calculate impact score for volatility event"""
        try:
            # Base impact from volatility level
            volatility_impact = {
                VolatilityLevel.LOW: 0.1,
                VolatilityLevel.MEDIUM: 0.3,
                VolatilityLevel.HIGH: 0.6,
                VolatilityLevel.EXTREME: 0.8,
                VolatilityLevel.CRITICAL: 1.0
            }.get(event.volatility_level, 0.1)
            
            # Price change impact
            price_impact = min(abs(event.price_change_percent) / 10.0, 1.0)
            
            # Volume impact
            volume_impact = min(event.volume_multiplier / 10.0, 1.0)
            
            # Duration impact
            duration_impact = min(event.duration_seconds / 60.0, 1.0)
            
            # Calculate overall impact score
            impact_score = (volatility_impact + price_impact + volume_impact + duration_impact) / 4.0
            
            return min(impact_score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating impact score: {e}")
            return 0.0
    
    async def _monitor_system_metrics(self, test_id: str):
        """Monitor system metrics during stress test"""
        try:
            while True:
                # Collect system metrics
                cpu_usage = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                # Simulate network usage
                network_usage = np.random.uniform(0, 100)
                
                # Simulate latency
                latency_ms = np.random.uniform(50, 500)
                
                # Simulate throughput
                throughput_rps = np.random.uniform(10, 100)
                
                # Simulate error rate
                error_rate = np.random.uniform(0, 5)
                
                # Simulate queue depth
                queue_depth = np.random.randint(0, 1000)
                
                # Simulate processing time
                processing_time_ms = np.random.uniform(10, 200)
                
                # Create metrics
                metrics = SystemMetrics(
                    timestamp=datetime.now(),
                    cpu_usage_percent=cpu_usage,
                    memory_usage_percent=memory.percent,
                    disk_usage_percent=disk.percent,
                    network_usage_percent=network_usage,
                    latency_ms=latency_ms,
                    throughput_rps=throughput_rps,
                    error_rate_percent=error_rate,
                    queue_depth=queue_depth,
                    processing_time_ms=processing_time_ms
                )
                
                # Store metrics
                self.system_metrics.append(metrics)
                
                # Wait for next measurement
                await asyncio.sleep(self.config["monitoring"]["metrics_collection_interval"])
                
        except asyncio.CancelledError:
            # Task was cancelled, which is expected
            pass
        except Exception as e:
            logger.error(f"Error monitoring system metrics: {e}")
    
    async def _analyze_stress_test_results(self, test_result: StressTestResult):
        """Analyze stress test results"""
        try:
            # Get metrics for this test
            test_metrics = [m for m in self.system_metrics 
                           if m.timestamp >= test_result.start_time and m.timestamp <= test_result.end_time]
            
            if not test_metrics:
                test_result.issues_found.append("No system metrics collected")
                return
            
            # Calculate peak metrics
            test_result.peak_cpu_usage = max(m.cpu_usage_percent for m in test_metrics)
            test_result.peak_memory_usage = max(m.memory_usage_percent for m in test_metrics)
            test_result.peak_latency_ms = max(m.latency_ms for m in test_metrics)
            test_result.min_throughput_rps = min(m.throughput_rps for m in test_metrics)
            test_result.max_error_rate = max(m.error_rate_percent for m in test_metrics)
            
            # Calculate system stability score
            test_result.system_stability_score = self._calculate_stability_score(test_metrics)
            
            # Determine system response
            test_result.system_response = self._determine_system_response(test_metrics)
            
            # Calculate recovery time
            test_result.recovery_time_seconds = self._calculate_recovery_time(test_metrics)
            
            # Check against thresholds
            await self._check_stress_thresholds(test_result)
            
            # Store metrics
            test_result.metrics = test_metrics
            
        except Exception as e:
            logger.error(f"Error analyzing stress test results: {e}")
            test_result.issues_found.append(f"Analysis error: {str(e)}")
    
    def _calculate_stability_score(self, metrics: List[SystemMetrics]) -> float:
        """Calculate system stability score"""
        try:
            if not metrics:
                return 0.0
            
            # Calculate stability based on metrics consistency
            cpu_stability = 1.0 - (np.std([m.cpu_usage_percent for m in metrics]) / 100.0)
            memory_stability = 1.0 - (np.std([m.memory_usage_percent for m in metrics]) / 100.0)
            latency_stability = 1.0 - (np.std([m.latency_ms for m in metrics]) / 1000.0)
            
            # Calculate overall stability
            stability_score = (cpu_stability + memory_stability + latency_stability) / 3.0
            
            return max(0.0, min(1.0, stability_score))
            
        except Exception as e:
            logger.error(f"Error calculating stability score: {e}")
            return 0.0
    
    def _determine_system_response(self, metrics: List[SystemMetrics]) -> SystemResponse:
        """Determine system response based on metrics"""
        try:
            if not metrics:
                return SystemResponse.FAILED
            
            # Get average metrics
            avg_cpu = np.mean([m.cpu_usage_percent for m in metrics])
            avg_memory = np.mean([m.memory_usage_percent for m in metrics])
            avg_latency = np.mean([m.latency_ms for m in metrics])
            avg_error_rate = np.mean([m.error_rate_percent for m in metrics])
            
            # Get thresholds
            thresholds = self.config["system_thresholds"]
            
            # Determine response level
            if (avg_cpu >= thresholds["cpu_usage_overloaded"] or 
                avg_memory >= thresholds["memory_usage_overloaded"] or
                avg_latency >= thresholds["latency_overloaded_ms"] or
                avg_error_rate >= thresholds["error_rate_overloaded_percent"]):
                return SystemResponse.OVERLOADED
            elif (avg_cpu >= thresholds["cpu_usage_stressed"] or 
                  avg_memory >= thresholds["memory_usage_stressed"] or
                  avg_latency >= thresholds["latency_stressed_ms"] or
                  avg_error_rate >= thresholds["error_rate_stressed_percent"]):
                return SystemResponse.STRESSED
            elif (avg_cpu >= thresholds["cpu_usage_normal"] or 
                  avg_memory >= thresholds["memory_usage_normal"] or
                  avg_latency >= thresholds["latency_normal_ms"] or
                  avg_error_rate >= thresholds["error_rate_normal_percent"]):
                return SystemResponse.DEGRADED
            else:
                return SystemResponse.NORMAL
            
        except Exception as e:
            logger.error(f"Error determining system response: {e}")
            return SystemResponse.FAILED
    
    def _calculate_recovery_time(self, metrics: List[SystemMetrics]) -> float:
        """Calculate system recovery time"""
        try:
            if not metrics:
                return 0.0
            
            # Find the point where system returns to normal
            thresholds = self.config["system_thresholds"]
            
            for i, metric in enumerate(metrics):
                if (metric.cpu_usage_percent < thresholds["cpu_usage_normal"] and
                    metric.memory_usage_percent < thresholds["memory_usage_normal"] and
                    metric.latency_ms < thresholds["latency_normal_ms"] and
                    metric.error_rate_percent < thresholds["error_rate_normal_percent"]):
                    
                    # Calculate recovery time
                    recovery_time = (metric.timestamp - metrics[0].timestamp).total_seconds()
                    return recovery_time
            
            # If no recovery point found, return total duration
            return (metrics[-1].timestamp - metrics[0].timestamp).total_seconds()
            
        except Exception as e:
            logger.error(f"Error calculating recovery time: {e}")
            return 0.0
    
    async def _check_stress_thresholds(self, test_result: StressTestResult):
        """Check stress test results against thresholds"""
        try:
            thresholds = self.config["system_thresholds"]
            issues = []
            
            # Check CPU usage
            if test_result.peak_cpu_usage > thresholds["cpu_usage_overloaded"]:
                issues.append(f"Peak CPU usage {test_result.peak_cpu_usage:.1f}% exceeds overloaded threshold {thresholds['cpu_usage_overloaded']}%")
            
            # Check memory usage
            if test_result.peak_memory_usage > thresholds["memory_usage_overloaded"]:
                issues.append(f"Peak memory usage {test_result.peak_memory_usage:.1f}% exceeds overloaded threshold {thresholds['memory_usage_overloaded']}%")
            
            # Check latency
            if test_result.peak_latency_ms > thresholds["latency_overloaded_ms"]:
                issues.append(f"Peak latency {test_result.peak_latency_ms:.1f}ms exceeds overloaded threshold {thresholds['latency_overloaded_ms']}ms")
            
            # Check error rate
            if test_result.max_error_rate > thresholds["error_rate_overloaded_percent"]:
                issues.append(f"Max error rate {test_result.max_error_rate:.1f}% exceeds overloaded threshold {thresholds['error_rate_overloaded_percent']}%")
            
            # Check system stability
            if test_result.system_stability_score < 0.7:
                issues.append(f"System stability score {test_result.system_stability_score:.2f} below minimum 0.7")
            
            test_result.issues_found.extend(issues)
            
            # Generate recommendations
            test_result.recommendations = self._generate_stress_recommendations(test_result)
            
        except Exception as e:
            logger.error(f"Error checking stress thresholds: {e}")
            test_result.issues_found.append(f"Threshold check error: {str(e)}")
    
    def _generate_stress_recommendations(self, test_result: StressTestResult) -> List[str]:
        """Generate recommendations based on stress test results"""
        recommendations = []
        
        if test_result.peak_cpu_usage > 90:
            recommendations.append("Consider CPU optimization or horizontal scaling")
        
        if test_result.peak_memory_usage > 90:
            recommendations.append("Consider memory optimization or increasing RAM")
        
        if test_result.peak_latency_ms > 1000:
            recommendations.append("Consider database optimization or caching")
        
        if test_result.max_error_rate > 5:
            recommendations.append("Investigate and fix error sources")
        
        if test_result.system_stability_score < 0.8:
            recommendations.append("Enhance system stability and error handling")
        
        if test_result.recovery_time_seconds > 300:
            recommendations.append("Improve system recovery mechanisms")
        
        if not recommendations:
            recommendations.append("System handled stress test well")
        
        return recommendations
    
    async def run_all_stress_tests(self) -> List[StressTestResult]:
        """Run all stress tests"""
        try:
            results = []
            
            for test_id in self.config["stress_tests"].keys():
                logger.info(f"Running stress test: {test_id}")
                result = await self.run_stress_test(test_id)
                results.append(result)
                
                # Wait between tests
                await asyncio.sleep(60)  # 1 minute between tests
            
            return results
            
        except Exception as e:
            logger.error(f"Error running all stress tests: {e}")
            return []
    
    def get_stress_test_summary(self) -> Dict[str, Any]:
        """Get summary of all stress test results"""
        try:
            if not self.test_results:
                return {"message": "No stress test results available"}
            
            total_tests = len(self.test_results)
            passed_tests = len([r for r in self.test_results if r.system_response in [SystemResponse.NORMAL, SystemResponse.DEGRADED]])
            failed_tests = len([r for r in self.test_results if r.system_response == SystemResponse.FAILED])
            overloaded_tests = len([r for r in self.test_results if r.system_response == SystemResponse.OVERLOADED])
            
            return {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "overloaded_tests": overloaded_tests,
                "pass_rate": (passed_tests / total_tests) * 100 if total_tests > 0 else 0,
                "test_results": [asdict(result) for result in self.test_results]
            }
            
        except Exception as e:
            logger.error(f"Error generating stress test summary: {e}")
            return {}

async def main():
    """Main function for testing high volatility stress testing"""
    stress_tester = HighVolatilityStressTesting()
    
    # Run all stress tests
    results = await stress_tester.run_all_stress_tests()
    
    # Print summary
    summary = stress_tester.get_stress_test_summary()
    print(f"High Volatility Stress Testing Summary: {summary}")

if __name__ == "__main__":
    asyncio.run(main())
