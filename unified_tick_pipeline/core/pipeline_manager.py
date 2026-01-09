"""
Unified Tick Pipeline Manager
Main orchestrator for the unified tick pipeline system
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import json
import time
from collections import deque
import threading

from .binance_feeds import BinanceFeedManager
from .mt5_bridge import MT5LocalBridge
from .offset_calibrator import OffsetCalibrator
from .m5_volatility_bridge import M5VolatilityBridge
from .dtms_enhancement import DTMSEnhancement
from .chatgpt_integration import ChatGPTIntegration
from .system_coordination import SystemCoordination
from .performance_optimization import PerformanceOptimization
from .database_integration import DatabaseIntegration
from .database_integration import DatabaseType
import sqlite3
from .data_access_layer import DataAccessLayer
from .mt5_m1_streaming import MT5M1Streaming
from .mt5_optimized_data_access import MT5OptimizedDataAccess
from .data_retention import DataRetentionSystem

logger = logging.getLogger(__name__)

@dataclass
class StageTiming:
    """Timing data for a processing stage"""
    stage_name: str
    start_time_ns: int
    end_time_ns: int = 0
    duration_ns: int = 0
    success: bool = True
    error_message: str = ""
    
    def __post_init__(self):
        if self.end_time_ns > 0:
            self.duration_ns = self.end_time_ns - self.start_time_ns

@dataclass
class PipelineTimingStats:
    """Statistics for pipeline timing"""
    total_ticks: int = 0
    stage_timings: Dict[str, List[float]] = field(default_factory=dict)
    stage_errors: Dict[str, int] = field(default_factory=dict)
    total_latency_ns: List[float] = field(default_factory=lambda: deque(maxlen=1000))
    p50_latency_ns: float = 0.0
    p95_latency_ns: float = 0.0
    p99_latency_ns: float = 0.0
    
    def add_stage_timing(self, stage_name: str, duration_ns: float, success: bool = True):
        """Add timing data for a stage"""
        if stage_name not in self.stage_timings:
            self.stage_timings[stage_name] = deque(maxlen=1000)
        
        self.stage_timings[stage_name].append(duration_ns)
        
        if not success:
            self.stage_errors[stage_name] = self.stage_errors.get(stage_name, 0) + 1
    
    def update_latency_stats(self):
        """Update latency statistics"""
        if self.total_latency_ns:
            sorted_latencies = sorted(self.total_latency_ns)
            n = len(sorted_latencies)
            self.p50_latency_ns = sorted_latencies[int(n * 0.5)] if n > 0 else 0.0
            self.p95_latency_ns = sorted_latencies[int(n * 0.95)] if n > 0 else 0.0
            self.p99_latency_ns = sorted_latencies[int(n * 0.99)] if n > 0 else 0.0

class StageTimer:
    """Context manager for timing pipeline stages"""
    
    def __init__(self, pipeline: 'UnifiedTickPipeline', stage_name: str):
        self.pipeline = pipeline
        self.stage_name = stage_name
        self.start_time_ns = 0
        self.timing = None
    
    def __enter__(self):
        self.start_time_ns = time.perf_counter_ns()
        self.timing = StageTiming(
            stage_name=self.stage_name,
            start_time_ns=self.start_time_ns
        )
        return self.timing
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time_ns = time.perf_counter_ns()
        duration_ns = end_time_ns - self.start_time_ns
        
        if self.timing:
            self.timing.end_time_ns = end_time_ns
            self.timing.duration_ns = duration_ns
            self.timing.success = exc_type is None
            
            if exc_type is not None:
                self.timing.error_message = str(exc_val)
        
        # Update pipeline timing stats
        self.pipeline.timing_stats.add_stage_timing(
            self.stage_name, 
            duration_ns, 
            exc_type is None
        )

@dataclass
class TickData:
    """Unified tick data structure"""
    symbol: str
    timestamp_utc: datetime
    bid: float
    ask: float
    mid: float
    volume: float
    source: str  # 'binance' or 'mt5'
    offset_applied: float = 0.0
    raw_data: Optional[Dict] = None

@dataclass
class MarketState:
    """Current market state snapshot"""
    timestamp_utc: datetime
    symbols: Dict[str, Dict[str, Any]]
    volatility_state: Dict[str, str]
    offset_calibrations: Dict[str, float]
    system_health: Dict[str, Any]

class UnifiedTickPipeline:
    """
    Main Unified Tick Pipeline Manager
    
    Orchestrates:
    - Binance WebSocket feeds (BTCUSD, XAUUSD, GBPJPY)
    - MT5 broker integration
    - Offset calibration between feeds
    - Data retention and storage
    - System health monitoring
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._default_config()
        self.is_running = False
        
        # Core components
        self.binance_feeds = BinanceFeedManager(self.config.get('binance', {}))
        self.mt5_bridge = MT5LocalBridge(self.config.get('mt5', {}))
        self.offset_calibrator = OffsetCalibrator(self.config.get('offset', {}))
        self.m5_volatility_bridge = M5VolatilityBridge(self.config.get('m5_volatility', {}))
        self.dtms_enhancement = DTMSEnhancement(self, self.config.get('dtms_enhancement', {}))
        self.chatgpt_integration = ChatGPTIntegration(self, self.config.get('chatgpt_integration', {}))
        self.system_coordination = SystemCoordination(self.config.get('system_coordination', {}))
        self.performance_optimization = PerformanceOptimization(self.config.get('performance_optimization', {}))
        self.database_integration = DatabaseIntegration(self.config.get('database_integration', {}))
        self.data_access_layer = DataAccessLayer(self.config.get('data_access_layer', {}))
        self.mt5_m1_streaming = MT5M1Streaming(self.config.get('mt5_m1_streaming', {}))
        self.mt5_optimized_data_access = MT5OptimizedDataAccess(self.config.get('mt5_optimized_data_access', {}))
        self.data_retention = DataRetentionSystem(self.config.get('data_retention', {}))
        
        # Data streams
        self.tick_buffer: Dict[str, List[TickData]] = {}
        self.market_state: Optional[MarketState] = None
        
        # Subscribers for real-time data
        self.subscribers: List[Callable[[TickData], None]] = []
        
        # Performance monitoring
        self.performance_metrics = {
            'ticks_processed': 0,
            'last_tick_time': None,
            'latency_ms': 0,
            'error_count': 0
        }
        
        # Stage timing system
        self.timing_stats = PipelineTimingStats()
        self.timing_lock = threading.RLock()
        
        logger.info("UnifiedTickPipeline initialized")
    
    def _default_config(self) -> Dict:
        """Default configuration"""
        return {
            'binance': {
                # DISABLED: Using MT5 M1 streaming for BTCUSD instead
                'enabled': False,
                'symbols': [],
                'primary_ws_url': '',
                'mirror_ws_url': '',
                'heartbeat_interval': 60,
                'reconnect_delay': 5,
                'max_reconnect_attempts': 10
            },
            'mt5': {
                'timeout': 5000,
                'symbols': ['EURUSDc', 'GBPUSDc', 'USDJPYc', 'AUDUSDc', 'USDCADc', 'NZDUSDc', 'USDCHFc', 'EURJPYc', 'GBPJPYc', 'AUDJPYc', 'CADJPYc', 'CHFJPYc', 'NZDJPYc', 'EURGBPc', 'EURAUDc', 'EURCHFc', 'EURNZDc', 'GBPAUDc', 'GBPCHFc', 'GBPNZDc', 'AUDCHFc', 'AUDNZDc', 'NZDCHFc', 'CADCHFc', 'AUDCADc', 'NZDCADc', 'EURCADc', 'GBPCADc', 'CHFCADc', 'XAUUSDc', 'XAGUSDc', 'BTCUSDc', 'ETHUSDc', 'LTCUSDc', 'XRPUSDc', 'ADAUSDc', 'DOTUSDc', 'LINKUSDc', 'UNIUSDc', 'AAVEUSDc', 'SUSHIUSDc', 'YFIUSDc', 'COMPUSDc', 'MKRUSDc', 'SNXUSDc', 'CRVUSDc', '1INCHUSDc', 'ALPHAUSDc', 'BALUSDc', 'BANDUSDc', 'BATUSDc', 'BNBUSDc', 'BUSDUSDc', 'CAKEUSDc', 'CELRUSDc', 'CHZUSDc', 'COTIUSDc', 'CROUSDc', 'CTSIUSDc', 'CVCUSDc', 'DASHUSDc', 'DOGEUSDc', 'ENJUSDc', 'EOSUSDc', 'ETCUSDc', 'FILUSDc', 'FLMUSDc', 'FTMUSDc', 'GRTUSDc', 'HBARUSDc', 'HOTUSDc', 'ICXUSDc', 'IOSTUSDc', 'IOTAUSDc', 'KAVAUSDc', 'KNCUSDc', 'KSMUSDc', 'LINAUSDc', 'LRCUSDc', 'LSKUSDc', 'LTOUSDc', 'MANAUSDc', 'MATICUSDc', 'MKRUSDc', 'NANOUSDc', 'NEOUSDc', 'OCEANUSDc', 'OMGUSDc', 'ONEUSDc', 'ONTUSDc', 'QTUMUSDc', 'REEFUSDc', 'RENUSDc', 'RVNUSDc', 'SCUSDc', 'SKLUSDc', 'SNXUSDc', 'SOLUSDc', 'STORJUSDc', 'SUNUSDc', 'SUSHIUSDc', 'SXPUSDc', 'THETAUSDc', 'TWTUSDc', 'UMAUSDc', 'UNIUSDc', 'VETUSDc', 'VTHOUSDc', 'WAVESUSDc', 'WINUSDc', 'XLMUSDc', 'XMRUSDc', 'XRPUSDc', 'XTZUSDc', 'YFIUSDc', 'ZECUSDc', 'ZILUSDc', 'ZRXUSDc'],
                'timeframes': ['M1', 'M5', 'M15', 'H1', 'H4'],
                'update_interval': 1000
            },
            'offset': {
                'calibration_interval': 60,
                'atr_threshold': 0.5,  # 0.5 ATR threshold for price differences
                'max_offset': 10.0,
                'drift_threshold': 2.0,
                'm5_structure_weight': 0.3,  # Weight for M5 structure in reconciliation
                'min_samples_for_calibration': 3,  # Minimum samples needed
                'time_alignment_window': 30  # Seconds for time alignment
            },
            'm5_volatility': {
                'high_vol_threshold': 0.3,  # Threshold for high volatility detection
                'structure_weight': 0.4,     # Weight for structure in majority decision
                'volume_weight': 0.3,       # Weight for volume in volatility calculation
                'price_weight': 0.7,        # Weight for price action in volatility calculation
                'fusion_window': 300,       # Time window for price fusion (5 minutes)
                'volatility_periods': 14     # Number of periods for volatility calculation
            },
            'dtms_enhancement': {
                'reevaluation_interval': 3,   # 3-second reevaluation interval
                'conflict_resolution': {
                    'adjust_stop_loss': 'dtms_override',
                    'adjust_take_profit': 'intelligent_exits_override',
                    'hedge_position': 'dtms_override',
                    'partial_close': 'intelligent_exits_override',
                    'trailing_stop': 'intelligent_exits_override'
                },
                'override_conditions': [
                    'emergency_stop_loss',
                    'high_volatility_stop',
                    'profit_target_reached',
                    'volatility_spike',
                    'structure_break',
                    'high_volatility_hedge',
                    'risk_reduction',
                    'trend_continuation',
                    'volatility_expansion'
                ]
            },
            'chatgpt_integration': {
                'default_access_level': 'read_only',
                'authorization_timeout': 300,  # 5 minutes
                'max_analysis_history': 1000,
                'timeframe_data_retention': 24,  # hours
                'analysis_engines': {
                    'market_structure': True,
                    'volatility_analysis': True,
                    'trend_analysis': True,
                    'support_resistance': True,
                    'momentum_analysis': True,
                    'risk_assessment': True
                },
                'parameter_change_authorization': {
                    'require_manual_approval': True,
                    'notification_method': 'telegram',
                    'approval_timeout': 600  # 10 minutes
                }
            },
            'system_coordination': {
                'resource_monitoring_interval': 5,  # seconds
                'task_processing_interval': 0.1,  # seconds
                'health_monitoring_interval': 30,  # seconds
                'resource_thresholds': {
                    'cpu_high': 80.0,
                    'cpu_critical': 95.0,
                    'memory_high': 85.0,
                    'memory_critical': 95.0,
                    'disk_high': 90.0,
                    'disk_critical': 98.0
                },
                'thread_limits': {
                    'critical': 4,
                    'high': 8,
                    'medium': 12,
                    'low': 6,
                    'deferred': 4
                },
                'defer_conditions': [
                    'cpu_high',
                    'memory_high',
                    'disk_high',
                    'network_issues'
                ]
            },
            'performance_optimization': {
                'optimization_level': 'balanced',  # aggressive, balanced, conservative
                'enable_memory_tracking': True,
                'sleep_detection_enabled': True,
                'gap_fill_enabled': True,
                'max_gap_duration_minutes': 30,
                'cache_cleanup_threshold': 1000,
                'memory_thresholds': {
                    'high': 80.0,
                    'critical': 90.0,
                    'recovery': 70.0
                },
                'cpu_thresholds': {
                    'high': 80.0,
                    'critical': 95.0
                },
                'optimization_intervals': {
                    'aggressive': 30,  # seconds
                    'balanced': 60,    # seconds
                    'conservative': 120  # seconds
                }
            },
            'database_integration': {
                'database_path': 'data/unified_tick_pipeline',
                'connection_pool_size': 10,
                'query_timeout': 30,
                'batch_size': 1000,
                'cache_size': 10000,
                'wal_mode': True,
                'retention_policies': {
                    'tick_data': 7,      # 7 days
                    'm5_candles': 30,    # 30 days
                    'dtms_actions': 90,   # 90 days
                    'chatgpt_analysis': 30,  # 30 days
                    'system_metrics': 7,     # 7 days
                    'performance_logs': 14   # 14 days
                },
                'optimization': {
                    'enable_indexes': True,
                    'enable_vacuum': True,
                    'enable_analyze': True,
                    'enable_reindex': True
                }
            },
                'data_access_layer': {
                    'database_path': 'data/unified_tick_pipeline',
                    'cache_ttl': 300,  # 5 minutes
                    'max_cache_size': 1000,
                    'query_timeout': 30,
                    'access_controls': {
                        'chatgpt': 'read_only',
                        'dtms': 'read_write',
                        'intelligent_exits': 'read_write',
                        'system': 'system',
                        'admin': 'admin'
                    },
                    'performance_monitoring': {
                        'enable_query_logging': True,
                        'enable_performance_tracking': True,
                        'enable_cache_monitoring': True
                    }
                },
                'mt5_m1_streaming': {
                    'symbols': ['EURUSDc', 'GBPUSDc', 'USDJPYc', 'GBPJPYc', 'EURJPYc', 'AUDUSDc', 'USDCADc', 'NZDUSDc', 'USDCHFc', 'AUDCADc', 'AUDCHFc', 'AUDJPYc', 'AUDNZDc', 'CADCHFc', 'CADJPYc', 'CHFJPYc', 'EURAUDc', 'EURCADc', 'EURCHFc', 'EURGBPc', 'EURNZDc', 'GBPAUDc', 'GBPCADc', 'GBPCHFc', 'GBPNZDc', 'NZDCADc', 'NZDCHFc', 'NZDJPYc', 'XAUUSDc'],
                    'update_interval': 1,  # 1 second
                    'buffer_size': 100,
                    'enable_volatility_analysis': True,
                    'enable_structure_analysis': True
                },
                'mt5_optimized_data_access': {
                    'symbols': ['EURUSDc', 'GBPUSDc', 'USDJPYc', 'GBPJPYc', 'EURJPYc', 'AUDUSDc', 'USDCADc', 'NZDUSDc', 'USDCHFc', 'AUDCADc', 'AUDCHFc', 'AUDJPYc', 'AUDNZDc', 'CADCHFc', 'CADJPYc', 'CHFJPYc', 'EURAUDc', 'EURCADc', 'EURCHFc', 'EURGBPc', 'EURNZDc', 'GBPAUDc', 'GBPCADc', 'GBPCHFc', 'GBPNZDc', 'NZDCADc', 'NZDCHFc', 'NZDJPYc', 'XAUUSDc'],
                    'cache_ttl_minutes': 15,  # Cache for 15 minutes
                    'max_cache_size': 1000,   # Maximum cached items
                    'enable_smart_polling': True,
                    'on_demand_timeframes': ['M5', 'M15', 'M30', 'H1', 'H4']
                },
            'data_retention': {
                'tick_buffer_size': 1000,  # Reduced from 10000: ~400KB per symbol (safe for laptops)
                'compression_threshold': 1000,
                'retention_hours': 24,
                'archive_format': 'parquet',
                'enable_database_storage': False  # Disabled: tick data not saved to database
            }
        }
    
    async def start_pipeline(self) -> bool:
        """Start the unified tick pipeline"""
        try:
            logger.info("🚀 Starting Unified Tick Pipeline...")
            
            # Initialize components
            await self._initialize_components()
            
            # Start data feeds
            await self._start_data_feeds()
            
            # Start monitoring tasks
            await self._start_monitoring_tasks()
            
            self.is_running = True
            logger.info("✅ Unified Tick Pipeline started successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start Unified Tick Pipeline: {e}")
            return False
    
    async def stop_pipeline(self) -> bool:
        """Stop the unified tick pipeline"""
        try:
            logger.info("🛑 Stopping Unified Tick Pipeline...")
            
            self.is_running = False
            
            # Stop components
            await self.binance_feeds.stop()
            await self.mt5_bridge.disconnect()
            await self.offset_calibrator.stop()
            await self.m5_volatility_bridge.stop()
            await self.dtms_enhancement.stop()
            await self.chatgpt_integration.stop()
            await self.system_coordination.stop()
            await self.performance_optimization.stop()
            # Stop DB integration first (closes active connections)
            await self.database_integration.stop()
            
            # Run off-peak VACUUM on all pipeline databases using fresh autocommit connections
            try:
                db_dir = self.database_integration.database_path
                for dbt in DatabaseType:
                    db_file = db_dir / f"{dbt.value}.db"
                    try:
                        conn = sqlite3.connect(str(db_file), timeout=30.0, isolation_level=None)
                        conn.execute("VACUUM")
                        conn.close()
                    except Exception as ve:
                        logger.debug(f"VACUUM skipped for {dbt.value}: {ve}")
            except Exception as ve_all:
                logger.debug(f"Off-peak VACUUM pass failed: {ve_all}")
            await self.data_access_layer.stop()
            await self.mt5_m1_streaming.stop()
            await self.mt5_optimized_data_access.stop()
            await self.data_retention.stop()
            
            logger.info("✅ Unified Tick Pipeline stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error stopping Unified Tick Pipeline: {e}")
            return False
    
    async def _initialize_components(self):
        """Initialize all pipeline components"""
        logger.info("🔧 Initializing pipeline components...")
        
        # Initialize data retention first
        await self.data_retention.initialize()
        
        # Initialize MT5 bridge
        await self.mt5_bridge.initialize()
        
        # Initialize offset calibrator
        await self.offset_calibrator.initialize()
        
        # Initialize M5 volatility bridge
        await self.m5_volatility_bridge.initialize()
        
        # Initialize DTMS enhancement
        await self.dtms_enhancement.initialize()
        
        # Initialize ChatGPT integration
        await self.chatgpt_integration.initialize()
        
        # Initialize system coordination
        await self.system_coordination.initialize()
        
        # Initialize performance optimization
        await self.performance_optimization.initialize()
        
        # Initialize database integration
        await self.database_integration.initialize()
        
        # Initialize data access layer
        await self.data_access_layer.initialize()
        
        # Initialize MT5 M1 streaming
        await self.mt5_m1_streaming.initialize()
        
        # Initialize MT5 optimized data access
        await self.mt5_optimized_data_access.initialize()
        
        # Initialize Binance feeds
        await self.binance_feeds.initialize()
        
        logger.info("✅ All components initialized")
    
    async def _start_data_feeds(self):
        """Start all data feeds"""
        logger.info("📡 Starting data feeds...")
        
        # Start Binance feeds
        await self.binance_feeds.start()
        
        # Start MT5 bridge
        await self.mt5_bridge.start()
        
        # Register data handlers
        self.binance_feeds.register_tick_handler(self._handle_binance_tick)
        self.mt5_bridge.register_tick_handler(self._handle_mt5_tick)
        
        logger.info("✅ Data feeds started")
    
    async def _start_monitoring_tasks(self):
        """Start background monitoring tasks"""
        logger.info("📊 Starting monitoring tasks...")
        
        # Start offset calibration task
        asyncio.create_task(self._offset_calibration_loop())
        
        # Start data retention task
        asyncio.create_task(self._data_retention_loop())
        
        # Start MT5 M1 streaming
        await self.mt5_m1_streaming.start()
        
        # Start health monitoring task
        asyncio.create_task(self._health_monitoring_loop())
        
        logger.info("✅ Monitoring tasks started")
    
    async def _handle_binance_tick(self, tick_data: Dict):
        """Handle incoming Binance tick data"""
        total_start_time = time.perf_counter_ns()
        
        try:
            with StageTimer(self, "binance_tick_processing") as timing:
                # Convert to unified format
                unified_tick = TickData(
                    symbol=tick_data['symbol'],
                    timestamp_utc=datetime.fromtimestamp(tick_data['timestamp'] / 1000, tz=timezone.utc),
                    bid=tick_data['bid'],
                    ask=tick_data['ask'],
                    mid=(tick_data['bid'] + tick_data['ask']) / 2,
                    volume=tick_data.get('volume', 0.0),
                    source='binance',
                    raw_data=tick_data
                )
            
            with StageTimer(self, "offset_calibration"):
                # Apply offset calibration
                offset = self.offset_calibrator.get_offset(unified_tick.symbol)
                if offset != 0:
                    unified_tick.bid += offset
                    unified_tick.ask += offset
                    unified_tick.mid += offset
                    unified_tick.offset_applied = offset
            
            with StageTimer(self, "tick_storage"):
                # Store in buffer
                await self._store_tick(unified_tick)
            
            with StageTimer(self, "subscriber_notification"):
                # Notify subscribers
                await self._notify_subscribers(unified_tick)
            
            with StageTimer(self, "performance_update"):
                # Update performance metrics
                self._update_performance_metrics(unified_tick)
            
            # Update total latency
            total_end_time = time.perf_counter_ns()
            total_latency_ns = total_end_time - total_start_time
            with self.timing_lock:
                self.timing_stats.total_latency_ns.append(total_latency_ns)
                self.timing_stats.update_latency_stats()
            
        except Exception as e:
            logger.error(f"❌ Error handling Binance tick: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _handle_mt5_tick(self, tick_data: Dict):
        """Handle incoming MT5 tick data"""
        total_start_time = time.perf_counter_ns()
        
        try:
            # Check if we're shutting down - skip processing during shutdown
            if not self.is_running:
                return
            
            with StageTimer(self, "mt5_tick_validation"):
                # Debug: Log the actual tick_data structure
                logger.debug(f"MT5 tick_data keys: {list(tick_data.keys()) if isinstance(tick_data, dict) else type(tick_data)}")
                
                # Validate tick_data structure
                if not isinstance(tick_data, dict):
                    logger.debug(f"⚠️ MT5 tick_data is not a dictionary: {type(tick_data)}")
                    return
                    
                # Check for required keys
                required_keys = ['symbol', 'timestamp', 'bid', 'ask']
                missing_keys = [key for key in required_keys if key not in tick_data]
                if missing_keys:
                    logger.debug(f"⚠️ MT5 tick_data missing keys: {missing_keys}")
                    return
                
                # Check for None values
                if any(tick_data[key] is None for key in required_keys):
                    logger.debug(f"⚠️ MT5 tick_data has None values")
                    return
            
            with StageTimer(self, "mt5_tick_processing"):
                # Convert to unified format
                unified_tick = TickData(
                    symbol=tick_data['symbol'],
                    timestamp_utc=datetime.fromtimestamp(tick_data['timestamp'], tz=timezone.utc),
                    bid=tick_data['bid'],
                    ask=tick_data['ask'],
                    mid=(tick_data['bid'] + tick_data['ask']) / 2,
                    volume=tick_data.get('volume', 0.0),
                    source='mt5',
                    raw_data=tick_data
                )
            
            with StageTimer(self, "tick_storage"):
                # Store in buffer
                await self._store_tick(unified_tick)
            
            with StageTimer(self, "subscriber_notification"):
                # Notify subscribers
                await self._notify_subscribers(unified_tick)
            
            with StageTimer(self, "performance_update"):
                # Update performance metrics
                self._update_performance_metrics(unified_tick)
            
            # Update total latency
            total_end_time = time.perf_counter_ns()
            total_latency_ns = total_end_time - total_start_time
            with self.timing_lock:
                self.timing_stats.total_latency_ns.append(total_latency_ns)
                self.timing_stats.update_latency_stats()
            
        except Exception as e:
            logger.error(f"❌ Error handling MT5 tick: {e}")
            self.performance_metrics['error_count'] += 1
    
    async def _store_tick(self, tick: TickData):
        """Store tick in buffer and data retention system"""
        # Add to in-memory buffer
        if tick.symbol not in self.tick_buffer:
            self.tick_buffer[tick.symbol] = []
        
        self.tick_buffer[tick.symbol].append(tick)
        
        # Maintain buffer size
        max_buffer_size = self.config['data_retention']['tick_buffer_size']
        if len(self.tick_buffer[tick.symbol]) > max_buffer_size:
            self.tick_buffer[tick.symbol] = self.tick_buffer[tick.symbol][-max_buffer_size:]
        
        # Store in data retention system
        tick_dict = {
            'symbol': tick.symbol,
            'timestamp_utc': tick.timestamp_utc,
            'bid': tick.bid,
            'ask': tick.ask,
            'mid': tick.mid,
            'volume': tick.volume,
            'source': tick.source,
            'offset_applied': tick.offset_applied,
            'raw_data': tick.raw_data
        }
        await self.data_retention.store_tick(tick_dict)
    
    async def _notify_subscribers(self, tick: TickData):
        """Notify all subscribers of new tick data"""
        for subscriber in self.subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(tick)
                else:
                    subscriber(tick)
            except Exception as e:
                logger.error(f"❌ Error notifying subscriber: {e}")
    
    def subscribe(self, callback: Callable[[TickData], None]):
        """Subscribe to tick data updates"""
        self.subscribers.append(callback)
        logger.info(f"📡 New subscriber registered (total: {len(self.subscribers)})")
    
    def subscribe_to_ticks(self, callback: Callable[[TickData], None]):
        """Subscribe to tick data updates (alias for subscribe)"""
        self.subscribe(callback)
    
    def subscribe_to_m5_data(self, callback: Callable[[Dict], None]):
        """Subscribe to M5 volatility data updates"""
        # This would be implemented to forward M5 data from volatility bridge
        pass
    
    def subscribe_to_offset_data(self, callback: Callable[[Dict], None]):
        """Subscribe to offset calibration data updates"""
        # This would be implemented to forward offset data from calibrator
        pass
    
    def unsubscribe(self, callback: Callable[[TickData], None]):
        """Unsubscribe from tick data updates"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
            logger.info(f"📡 Subscriber removed (total: {len(self.subscribers)})")
    
    async def _offset_calibration_loop(self):
        """Background offset calibration loop"""
        while self.is_running:
            try:
                await self.offset_calibrator.calibrate_offsets()
                await asyncio.sleep(self.config['offset']['calibration_interval'])
            except Exception as e:
                logger.error(f"❌ Error in offset calibration: {e}")
                await asyncio.sleep(10)
    
    async def _data_retention_loop(self):
        """Background data retention management loop"""
        # Skip if database storage is disabled (no need to compress)
        if not self.data_retention.config.enable_database_storage:
            logger.info("ℹ️ Data retention loop skipped (database storage disabled)")
            return
        
        while self.is_running:
            try:
                await self.data_retention.process_retention()
                await asyncio.sleep(60)  # Process every minute
            except Exception as e:
                logger.error(f"❌ Error in data retention: {e}")
                await asyncio.sleep(10)
    
    async def _health_monitoring_loop(self):
        """Background health monitoring loop"""
        while self.is_running:
            try:
                await self._update_market_state()
                await self._check_system_health()
                await asyncio.sleep(5)  # Check every 5 seconds
            except Exception as e:
                logger.error(f"❌ Error in health monitoring: {e}")
                await asyncio.sleep(10)
    
    async def _update_market_state(self):
        """Update current market state"""
        try:
            symbols_data = {}
            
            # Get latest data for each symbol
            for symbol in self.tick_buffer:
                if self.tick_buffer[symbol]:
                    latest_tick = self.tick_buffer[symbol][-1]
                    symbols_data[symbol] = {
                        'bid': latest_tick.bid,
                        'ask': latest_tick.ask,
                        'mid': latest_tick.mid,
                        'volume': latest_tick.volume,
                        'source': latest_tick.source,
                        'timestamp': latest_tick.timestamp_utc.isoformat()
                    }
            
            # Get volatility states
            volatility_state = await self._get_volatility_states()
            
            # Get offset calibrations
            offset_calibrations = self.offset_calibrator.get_all_offsets()
            
            # Get system health
            system_health = await self._get_system_health()
            
            self.market_state = MarketState(
                timestamp_utc=datetime.now(timezone.utc),
                symbols=symbols_data,
                volatility_state=volatility_state,
                offset_calibrations=offset_calibrations,
                system_health=system_health
            )
            
        except Exception as e:
            logger.error(f"❌ Error updating market state: {e}")
    
    async def _get_volatility_states(self) -> Dict[str, str]:
        """Get current volatility states for all symbols"""
        volatility_states = {}
        
        for symbol in self.tick_buffer:
            if len(self.tick_buffer[symbol]) > 100:
                # Calculate recent volatility
                recent_ticks = self.tick_buffer[symbol][-100:]
                prices = [tick.mid for tick in recent_ticks]
                
                if len(prices) > 1:
                    price_changes = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
                    avg_change = sum(price_changes) / len(price_changes)
                    
                    if avg_change > 0.01:  # Threshold for high volatility
                        volatility_states[symbol] = 'high'
                    elif avg_change > 0.005:
                        volatility_states[symbol] = 'moderate'
                    else:
                        volatility_states[symbol] = 'low'
                else:
                    volatility_states[symbol] = 'unknown'
            else:
                volatility_states[symbol] = 'insufficient_data'
        
        return volatility_states
    
    async def _get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics"""
        return {
            'is_running': self.is_running,
            'binance_feeds_active': self.binance_feeds.is_connected(),
            'mt5_bridge_active': self.mt5_bridge.is_connected(),
            'offset_calibrator_active': self.offset_calibrator.is_active,
            'data_retention_active': self.data_retention.is_active,
            'performance_metrics': self.performance_metrics,
            'buffer_sizes': {symbol: len(ticks) for symbol, ticks in self.tick_buffer.items()},
            'subscriber_count': len(self.subscribers)
        }
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics (public method)"""
        return await self._get_system_health()
    
    async def _check_system_health(self):
        """Check system health and handle issues"""
        try:
            health = await self._get_system_health()
            
            # Check for critical issues - only reconnect if feeds are enabled
            if not health['binance_feeds_active'] and self.binance_feeds.config.enabled:
                logger.warning("⚠️ Binance feeds disconnected, attempting reconnection...")
                await self.binance_feeds.reconnect()
            elif not health['binance_feeds_active'] and not self.binance_feeds.config.enabled:
                # Binance feeds are disabled, don't try to reconnect
                pass
            
            if not health['mt5_bridge_active']:
                logger.warning("⚠️ MT5 bridge disconnected, attempting reconnection...")
                await self.mt5_bridge.reconnect()
            
            # Check error rate
            if self.performance_metrics['error_count'] > 100:
                logger.warning("⚠️ High error count detected, resetting metrics...")
                self.performance_metrics['error_count'] = 0
            
        except Exception as e:
            logger.error(f"❌ Error checking system health: {e}")
    
    def _update_performance_metrics(self, tick: TickData):
        """Update performance metrics"""
        self.performance_metrics['ticks_processed'] += 1
        self.performance_metrics['last_tick_time'] = tick.timestamp_utc
        
        # Calculate latency
        now = datetime.now(timezone.utc)
        latency = (now - tick.timestamp_utc).total_seconds() * 1000
        self.performance_metrics['latency_ms'] = latency
        
        # Update timing stats
        with self.timing_lock:
            self.timing_stats.total_ticks += 1
    
    # Public API methods
    async def get_tick_data(self, symbol: str, timeframe: str = "M1", hours_back: int = 4) -> List[Dict]:
        """Get tick data for analysis"""
        try:
            if symbol not in self.tick_buffer:
                return []
            
            # Filter by time range
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            recent_ticks = [
                tick for tick in self.tick_buffer[symbol]
                if tick.timestamp_utc >= cutoff_time
            ]
            
            # Convert to dict format
            return [
                {
                    'timestamp': tick.timestamp_utc.isoformat(),
                    'bid': tick.bid,
                    'ask': tick.ask,
                    'mid': tick.mid,
                    'volume': tick.volume,
                    'source': tick.source,
                    'offset_applied': tick.offset_applied
                }
                for tick in recent_ticks
            ]
            
        except Exception as e:
            logger.error(f"❌ Error getting tick data: {e}")
            return []
    
    async def get_current_market_state(self) -> Optional[Dict]:
        """Get current market state"""
        if self.market_state:
            return {
                'timestamp': self.market_state.timestamp_utc.isoformat(),
                'symbols': self.market_state.symbols,
                'volatility_state': self.market_state.volatility_state,
                'offset_calibrations': self.market_state.offset_calibrations,
                'system_health': self.market_state.system_health
            }
        return None
    
    async def get_multi_timeframe_data(self, symbol: str) -> Dict[str, Any]:
        """Get multi-timeframe data for symbol"""
        try:
            # Get M1 data (tick level)
            m1_data = await self.get_tick_data(symbol, "M1", 4)
            
            # Get M5 data (aggregated)
            m5_data = await self.data_retention.get_aggregated_data(symbol, "M5", 12)
            
            # Get M15 data
            m15_data = await self.data_retention.get_aggregated_data(symbol, "M15", 24)
            
            # Get H1 data
            h1_data = await self.data_retention.get_aggregated_data(symbol, "H1", 48)
            
            # Get H4 data
            h4_data = await self.data_retention.get_aggregated_data(symbol, "H4", 168)
            
            return {
                'symbol': symbol,
                'M1': m1_data,
                'M5': m5_data,
                'M15': m15_data,
                'H1': h1_data,
                'H4': h4_data,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting multi-timeframe data: {e}")
            return {}
    
    def get_status(self) -> Dict[str, Any]:
        """Get pipeline status"""
        return {
            'is_running': self.is_running,
            'components': {
                'binance_feeds': self.binance_feeds.get_status(),
                'mt5_bridge': self.mt5_bridge.get_status(),
                'offset_calibrator': self.offset_calibrator.get_status(),
                'm5_volatility_bridge': self.m5_volatility_bridge.get_status(),
                'dtms_enhancement': self.dtms_enhancement.get_status(),
                'chatgpt_integration': self.chatgpt_integration.get_status(),
                'system_coordination': self.system_coordination.get_status(),
                'performance_optimization': self.performance_optimization.get_status(),
                'database_integration': self.database_integration.get_status(),
                'data_access_layer': self.data_access_layer.get_status(),
                'mt5_m1_streaming': self.mt5_m1_streaming.get_status(),
                'mt5_optimized_data_access': self.mt5_optimized_data_access.get_status(),
                'data_retention': self.data_retention.get_status()
            },
            'performance_metrics': self.performance_metrics,
            'buffer_sizes': {symbol: len(ticks) for symbol, ticks in self.tick_buffer.items()},
            'subscriber_count': len(self.subscribers)
        }
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get pipeline status (alias for get_status)"""
        return self.get_status()
    
    def get_timing_statistics(self) -> Dict[str, Any]:
        """Get detailed timing statistics for all pipeline stages"""
        with self.timing_lock:
            stats = {
                'total_ticks': self.timing_stats.total_ticks,
                'stage_timings': {},
                'stage_errors': dict(self.timing_stats.stage_errors),
                'latency_percentiles': {
                    'p50_ns': self.timing_stats.p50_latency_ns,
                    'p95_ns': self.timing_stats.p95_latency_ns,
                    'p99_ns': self.timing_stats.p99_latency_ns,
                    'p50_ms': self.timing_stats.p50_latency_ns / 1_000_000,
                    'p95_ms': self.timing_stats.p95_latency_ns / 1_000_000,
                    'p99_ms': self.timing_stats.p99_latency_ns / 1_000_000
                }
            }
            
            # Calculate stage timing statistics
            for stage_name, timings in self.timing_stats.stage_timings.items():
                if timings:
                    timings_list = list(timings)
                    stats['stage_timings'][stage_name] = {
                        'count': len(timings_list),
                        'avg_ns': sum(timings_list) / len(timings_list),
                        'avg_ms': (sum(timings_list) / len(timings_list)) / 1_000_000,
                        'min_ns': min(timings_list),
                        'max_ns': max(timings_list),
                        'min_ms': min(timings_list) / 1_000_000,
                        'max_ms': max(timings_list) / 1_000_000
                    }
            
            return stats
    
    def get_latest_ticks(self, symbol: str, limit: int = 100) -> List[TickData]:
        """Get latest ticks for a symbol"""
        try:
            if symbol in self.tick_buffer:
                return self.tick_buffer[symbol][-limit:] if limit > 0 else self.tick_buffer[symbol]
            return []
        except Exception as e:
            logger.error(f"❌ Error getting latest ticks for {symbol}: {e}")
            return []
    
    async def get_offset_calibration(self, symbol: str) -> Dict[str, Any]:
        """Get offset calibration for a symbol"""
        try:
            if not self.offset_calibrator:
                return {'success': False, 'error': 'Offset calibrator not available'}
            
            # Get current offset from calibrator
            offset = self.offset_calibrator.get_offset(symbol)
            
            return {
                'success': True,
                'data': {
                    'symbol': symbol,
                    'offset': offset,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'calibrator_active': self.offset_calibrator.is_active
                }
            }
        except Exception as e:
            logger.error(f"❌ Error getting offset calibration for {symbol}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_volatility_analysis(self, symbol: str) -> Dict[str, Any]:
        """Get volatility analysis for a symbol"""
        try:
            if not self.m5_volatility_bridge:
                return {'success': False, 'error': 'M5 Volatility Bridge not available'}
            
            # Get volatility data from M5 bridge
            volatility_data = self.m5_volatility_bridge.get_volatility_analysis(symbol)
            
            return {
                'success': True,
                'data': volatility_data
            }
        except Exception as e:
            logger.error(f"❌ Error getting volatility analysis for {symbol}: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_m5_candles(self, symbol: str, limit: int = 10) -> Dict[str, Any]:
        """Get M5 candles for a symbol"""
        try:
            if not self.m5_volatility_bridge:
                return {'success': False, 'error': 'M5 Volatility Bridge not available'}
            
            # Get M5 candles from bridge
            candles = self.m5_volatility_bridge.get_m5_candles(symbol, limit)
            
            return {
                'success': True,
                'data': candles
            }
        except Exception as e:
            logger.error(f"❌ Error getting M5 candles for {symbol}: {e}")
            return {'success': False, 'error': str(e)}
