"""
Data Access Layer for Unified Tick Pipeline
Efficient APIs for ChatGPT, DTMS, and Intelligent Exits to query historical and real-time data
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import json
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

class QueryType(Enum):
    """Query types for different data access patterns"""
    REAL_TIME = "real_time"
    HISTORICAL = "historical"
    AGGREGATED = "aggregated"
    ANALYTICAL = "analytical"
    PERFORMANCE = "performance"

class DataSource(Enum):
    """Data sources for queries"""
    TICK_DATA = "tick_data"
    M5_CANDLES = "m5_candles"
    DTMS_ACTIONS = "dtms_actions"
    CHATGPT_ANALYSIS = "chatgpt_analysis"
    SYSTEM_METRICS = "system_metrics"
    PERFORMANCE_LOGS = "performance_logs"

class AccessLevel(Enum):
    """Access levels for different components"""
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    ADMIN = "admin"
    SYSTEM = "system"

@dataclass
class QueryRequest:
    """Query request structure"""
    query_type: QueryType
    data_source: DataSource
    access_level: AccessLevel
    parameters: Dict[str, Any]
    filters: Optional[Dict[str, Any]] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    order_by: Optional[str] = None
    group_by: Optional[str] = None

@dataclass
class QueryResponse:
    """Query response structure"""
    success: bool
    data: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    cache_hit: bool = False

class DataAccessLayer:
    """
    Data Access Layer for Unified Tick Pipeline
    
    Features:
    - Efficient APIs for ChatGPT, DTMS, and Intelligent Exits
    - Query optimization and caching
    - Access control and authorization
    - Real-time and historical data access
    - Performance monitoring and optimization
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_active = False
        
        # Database connections
        self.connections: Dict[str, sqlite3.Connection] = {}
        self.database_path = Path(self.config.get('database_path', 'data/unified_tick_pipeline'))
        
        # Query cache
        self.query_cache: Dict[str, Tuple[datetime, Any]] = {}
        self.cache_ttl = self.config.get('cache_ttl', 300)  # 5 minutes
        self.max_cache_size = self.config.get('max_cache_size', 1000)
        
        # Access control
        self.access_controls: Dict[str, AccessLevel] = {
            'chatgpt': AccessLevel.READ_ONLY,
            'dtms': AccessLevel.READ_WRITE,
            'intelligent_exits': AccessLevel.READ_WRITE,
            'system': AccessLevel.SYSTEM,
            'admin': AccessLevel.ADMIN
        }
        
        # Performance metrics
        self.performance_metrics = {
            'queries_executed': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'average_query_time': 0.0,
            'total_query_time': 0.0,
            'error_count': 0,
            'access_denied': 0,
            'optimized_queries': 0
        }
        
        logger.info("DataAccessLayer initialized")
    
    async def initialize(self):
        """Initialize data access layer"""
        try:
            logger.info("🔧 Initializing data access layer...")
            
            # Create database connections
            await self._create_database_connections()
            
            # Initialize query cache
            await self._initialize_query_cache()
            
            # Start maintenance tasks
            await self._start_maintenance_tasks()
            
            self.is_active = True
            logger.info("✅ Data access layer initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize data access layer: {e}")
            raise
    
    async def stop(self):
        """Stop data access layer"""
        try:
            logger.info("🛑 Stopping data access layer...")
            self.is_active = False
            
            # Close database connections
            for conn in self.connections.values():
                conn.close()
            
            self.connections.clear()
            logger.info("✅ Data access layer stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping data access layer: {e}")
    
    async def _create_database_connections(self):
        """Create database connections"""
        try:
            for data_source in DataSource:
                db_path = self.database_path / f"{data_source.value}.db"
                
                if db_path.exists():
                    conn = sqlite3.connect(str(db_path), check_same_thread=False)
                    conn.row_factory = sqlite3.Row  # Enable column access by name
                    self.connections[data_source.value] = conn
                    
            logger.info("✅ Database connections created")
            
        except Exception as e:
            logger.error(f"❌ Error creating database connections: {e}")
    
    async def _initialize_query_cache(self):
        """Initialize query cache"""
        try:
            # Clear existing cache
            self.query_cache.clear()
            logger.info("✅ Query cache initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing query cache: {e}")
    
    async def _start_maintenance_tasks(self):
        """Start maintenance tasks"""
        try:
            # Start cache cleanup task
            asyncio.create_task(self._cache_cleanup_task())
            
            # Start performance monitoring task
            asyncio.create_task(self._performance_monitoring_task())
            
            logger.info("✅ Maintenance tasks started")
            
        except Exception as e:
            logger.error(f"❌ Error starting maintenance tasks: {e}")
    
    async def _cache_cleanup_task(self):
        """Cache cleanup task"""
        while self.is_active:
            try:
                current_time = datetime.now(timezone.utc)
                
                # Remove expired cache entries
                expired_keys = []
                for key, (timestamp, _) in self.query_cache.items():
                    if (current_time - timestamp).total_seconds() > self.cache_ttl:
                        expired_keys.append(key)
                
                for key in expired_keys:
                    del self.query_cache[key]
                
                # Limit cache size
                if len(self.query_cache) > self.max_cache_size:
                    # Remove oldest entries
                    sorted_items = sorted(self.query_cache.items(), key=lambda x: x[1][0])
                    excess_count = len(self.query_cache) - self.max_cache_size
                    for key, _ in sorted_items[:excess_count]:
                        del self.query_cache[key]
                
                # Sleep for 5 minutes
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"❌ Error in cache cleanup task: {e}")
                await asyncio.sleep(60)  # 1 minute on error
    
    async def _performance_monitoring_task(self):
        """Performance monitoring task"""
        while self.is_active:
            try:
                # Update performance metrics
                if self.performance_metrics['queries_executed'] > 0:
                    self.performance_metrics['average_query_time'] = (
                        self.performance_metrics['total_query_time'] / 
                        self.performance_metrics['queries_executed']
                    )
                
                # Sleep for 1 minute
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"❌ Error in performance monitoring task: {e}")
                await asyncio.sleep(30)  # 30 seconds on error
    
    # Public API methods
    async def execute_query(self, request: QueryRequest, component: str) -> QueryResponse:
        """Execute a query request"""
        start_time = datetime.now(timezone.utc)
        
        try:
            # Check access control
            if not self._check_access_control(component, request.access_level):
                self.performance_metrics['access_denied'] += 1
                return QueryResponse(
                    success=False,
                    data=[],
                    metadata={},
                    error="Access denied",
                    execution_time_ms=0.0
                )
            
            # Check cache first
            cache_key = self._generate_cache_key(request)
            if cache_key in self.query_cache:
                timestamp, cached_data = self.query_cache[cache_key]
                if (datetime.now(timezone.utc) - timestamp).total_seconds() < self.cache_ttl:
                    self.performance_metrics['cache_hits'] += 1
                    return QueryResponse(
                        success=True,
                        data=cached_data,
                        metadata={'cache_hit': True},
                        execution_time_ms=0.0,
                        cache_hit=True
                    )
            
            # Execute query
            result = await self._execute_database_query(request)
            
            # Cache result
            self.query_cache[cache_key] = (datetime.now(timezone.utc), result)
            self.performance_metrics['cache_misses'] += 1
            
            # Update performance metrics
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self.performance_metrics['queries_executed'] += 1
            self.performance_metrics['total_query_time'] += execution_time
            
            return QueryResponse(
                success=True,
                data=result,
                metadata={'cache_hit': False},
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            logger.error(f"❌ Error executing query: {e}")
            self.performance_metrics['error_count'] += 1
            
            return QueryResponse(
                success=False,
                data=[],
                metadata={},
                error=str(e),
                execution_time_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
    
    def _check_access_control(self, component: str, required_level: AccessLevel) -> bool:
        """Check access control for component"""
        try:
            component_level = self.access_controls.get(component, AccessLevel.READ_ONLY)
            
            # Define access hierarchy
            access_hierarchy = {
                AccessLevel.READ_ONLY: 1,
                AccessLevel.READ_WRITE: 2,
                AccessLevel.ADMIN: 3,
                AccessLevel.SYSTEM: 4
            }
            
            return access_hierarchy.get(component_level, 1) >= access_hierarchy.get(required_level, 1)
            
        except Exception as e:
            logger.error(f"❌ Error checking access control: {e}")
            return False
    
    def _generate_cache_key(self, request: QueryRequest) -> str:
        """Generate cache key for request"""
        try:
            key_data = {
                'query_type': request.query_type.value,
                'data_source': request.data_source.value,
                'parameters': request.parameters,
                'filters': request.filters,
                'limit': request.limit,
                'offset': request.offset,
                'order_by': request.order_by,
                'group_by': request.group_by
            }
            
            return json.dumps(key_data, sort_keys=True)
            
        except Exception as e:
            logger.error(f"❌ Error generating cache key: {e}")
            return str(hash(str(request)))
    
    async def _execute_database_query(self, request: QueryRequest) -> List[Dict[str, Any]]:
        """Execute database query"""
        try:
            conn = self.connections.get(request.data_source.value)
            if not conn:
                raise Exception(f"Database connection not found for {request.data_source.value}")
            
            # Build SQL query
            sql_query = self._build_sql_query(request)
            
            # Execute query
            cursor = conn.cursor()
            cursor.execute(sql_query['sql'], sql_query['params'])
            
            # Fetch results
            rows = cursor.fetchall()
            
            # Convert to list of dictionaries
            result = []
            for row in rows:
                result.append(dict(row))
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error executing database query: {e}")
            raise
    
    def _build_sql_query(self, request: QueryRequest) -> Dict[str, Any]:
        """Build SQL query from request"""
        try:
            # Base table name
            table_name = request.data_source.value
            
            # Build SELECT clause
            select_clause = "SELECT *"
            if request.parameters.get('columns'):
                select_clause = f"SELECT {', '.join(request.parameters['columns'])}"
            
            # Build WHERE clause
            where_clause = ""
            params = []
            
            if request.filters:
                conditions = []
                for key, value in request.filters.items():
                    if isinstance(value, list):
                        placeholders = ', '.join(['?' for _ in value])
                        conditions.append(f"{key} IN ({placeholders})")
                        params.extend(value)
                    else:
                        conditions.append(f"{key} = ?")
                        params.append(value)
                
                if conditions:
                    where_clause = f"WHERE {' AND '.join(conditions)}"
            
            # Build ORDER BY clause
            order_clause = ""
            if request.order_by:
                order_clause = f"ORDER BY {request.order_by}"
            
            # Build GROUP BY clause
            group_clause = ""
            if request.group_by:
                group_clause = f"GROUP BY {request.group_by}"
            
            # Build LIMIT clause
            limit_clause = ""
            if request.limit:
                limit_clause = f"LIMIT {request.limit}"
                if request.offset:
                    limit_clause = f"LIMIT {request.offset}, {request.limit}"
            
            # Build complete query
            sql_parts = [select_clause, f"FROM {table_name}"]
            
            if where_clause:
                sql_parts.append(where_clause)
            
            if group_clause:
                sql_parts.append(group_clause)
            
            if order_clause:
                sql_parts.append(order_clause)
            
            if limit_clause:
                sql_parts.append(limit_clause)
            
            sql_query = ' '.join(sql_parts)
            
            return {
                'sql': sql_query,
                'params': params
            }
            
        except Exception as e:
            logger.error(f"❌ Error building SQL query: {e}")
            raise
    
    # Specialized query methods for different components
    async def get_tick_data(self, symbol: str, start_time: datetime, end_time: datetime, 
                           component: str, limit: int = 1000) -> QueryResponse:
        """Get tick data for a symbol within time range"""
        request = QueryRequest(
            query_type=QueryType.HISTORICAL,
            data_source=DataSource.TICK_DATA,
            access_level=AccessLevel.READ_ONLY,
            parameters={'columns': ['symbol', 'timestamp_utc', 'bid', 'ask', 'mid', 'volume', 'source']},
            filters={
                'symbol': symbol,
                'timestamp_utc': f"BETWEEN '{start_time.isoformat()}' AND '{end_time.isoformat()}'"
            },
            limit=limit,
            order_by='timestamp_utc DESC'
        )
        
        return await self.execute_query(request, component)
    
    async def get_m5_candles(self, symbol: str, start_time: datetime, end_time: datetime, 
                            component: str, limit: int = 1000) -> QueryResponse:
        """Get M5 candles for a symbol within time range"""
        request = QueryRequest(
            query_type=QueryType.HISTORICAL,
            data_source=DataSource.M5_CANDLES,
            access_level=AccessLevel.READ_ONLY,
            parameters={'columns': ['symbol', 'timestamp_utc', 'open', 'high', 'low', 'close', 'volume', 'volatility_score']},
            filters={
                'symbol': symbol,
                'timestamp_utc': f"BETWEEN '{start_time.isoformat()}' AND '{end_time.isoformat()}'"
            },
            limit=limit,
            order_by='timestamp_utc DESC'
        )
        
        return await self.execute_query(request, component)
    
    async def get_dtms_actions(self, ticket: int, component: str) -> QueryResponse:
        """Get DTMS actions for a specific ticket"""
        request = QueryRequest(
            query_type=QueryType.HISTORICAL,
            data_source=DataSource.DTMS_ACTIONS,
            access_level=AccessLevel.READ_WRITE,
            parameters={'columns': ['action_id', 'ticket', 'symbol', 'action_type', 'status', 'timestamp_utc']},
            filters={'ticket': ticket},
            order_by='timestamp_utc DESC'
        )
        
        return await self.execute_query(request, component)
    
    async def get_chatgpt_analysis(self, symbol: str, analysis_type: str, component: str, 
                                  limit: int = 100) -> QueryResponse:
        """Get ChatGPT analysis for a symbol and analysis type"""
        request = QueryRequest(
            query_type=QueryType.ANALYTICAL,
            data_source=DataSource.CHATGPT_ANALYSIS,
            access_level=AccessLevel.READ_ONLY,
            parameters={'columns': ['request_id', 'symbol', 'analysis_type', 'result', 'confidence_score', 'timestamp_utc']},
            filters={
                'symbol': symbol,
                'analysis_type': analysis_type
            },
            limit=limit,
            order_by='timestamp_utc DESC'
        )
        
        return await self.execute_query(request, component)
    
    async def get_system_metrics(self, metric_type: str, component: str, 
                                start_time: datetime, end_time: datetime) -> QueryResponse:
        """Get system metrics for a specific type and time range"""
        request = QueryRequest(
            query_type=QueryType.PERFORMANCE,
            data_source=DataSource.SYSTEM_METRICS,
            access_level=AccessLevel.READ_ONLY,
            parameters={'columns': ['metric_type', 'component', 'value', 'unit', 'timestamp_utc']},
            filters={
                'metric_type': metric_type,
                'timestamp_utc': f"BETWEEN '{start_time.isoformat()}' AND '{end_time.isoformat()}'"
            },
            order_by='timestamp_utc DESC'
        )
        
        return await self.execute_query(request, component)
    
    async def get_performance_logs(self, log_level: str, component: str, 
                                  start_time: datetime, end_time: datetime, 
                                  limit: int = 1000) -> QueryResponse:
        """Get performance logs for a specific level and time range"""
        request = QueryRequest(
            query_type=QueryType.PERFORMANCE,
            data_source=DataSource.PERFORMANCE_LOGS,
            access_level=AccessLevel.READ_ONLY,
            parameters={'columns': ['log_level', 'component', 'message', 'timestamp_utc']},
            filters={
                'log_level': log_level,
                'timestamp_utc': f"BETWEEN '{start_time.isoformat()}' AND '{end_time.isoformat()}'"
            },
            limit=limit,
            order_by='timestamp_utc DESC'
        )
        
        return await self.execute_query(request, component)
    
    # Real-time data access methods
    async def get_latest_tick(self, symbol: str, component: str) -> QueryResponse:
        """Get latest tick data for a symbol"""
        request = QueryRequest(
            query_type=QueryType.REAL_TIME,
            data_source=DataSource.TICK_DATA,
            access_level=AccessLevel.READ_ONLY,
            parameters={'columns': ['symbol', 'timestamp_utc', 'bid', 'ask', 'mid', 'volume', 'source']},
            filters={'symbol': symbol},
            limit=1,
            order_by='timestamp_utc DESC'
        )
        
        return await self.execute_query(request, component)
    
    async def get_latest_m5_candle(self, symbol: str, component: str) -> QueryResponse:
        """Get latest M5 candle for a symbol"""
        request = QueryRequest(
            query_type=QueryType.REAL_TIME,
            data_source=DataSource.M5_CANDLES,
            access_level=AccessLevel.READ_ONLY,
            parameters={'columns': ['symbol', 'timestamp_utc', 'open', 'high', 'low', 'close', 'volume', 'volatility_score']},
            filters={'symbol': symbol},
            limit=1,
            order_by='timestamp_utc DESC'
        )
        
        return await self.execute_query(request, component)
    
    # Aggregated data access methods
    async def get_volatility_summary(self, symbol: str, component: str, 
                                    start_time: datetime, end_time: datetime) -> QueryResponse:
        """Get volatility summary for a symbol"""
        request = QueryRequest(
            query_type=QueryType.AGGREGATED,
            data_source=DataSource.M5_CANDLES,
            access_level=AccessLevel.READ_ONLY,
            parameters={
                'columns': [
                    'symbol',
                    'AVG(volatility_score) as avg_volatility',
                    'MAX(volatility_score) as max_volatility',
                    'MIN(volatility_score) as min_volatility',
                    'COUNT(*) as candle_count'
                ]
            },
            filters={
                'symbol': symbol,
                'timestamp_utc': f"BETWEEN '{start_time.isoformat()}' AND '{end_time.isoformat()}'"
            },
            group_by='symbol'
        )
        
        return await self.execute_query(request, component)
    
    async def get_trading_volume_summary(self, symbol: str, component: str, 
                                        start_time: datetime, end_time: datetime) -> QueryResponse:
        """Get trading volume summary for a symbol"""
        request = QueryRequest(
            query_type=QueryType.AGGREGATED,
            data_source=DataSource.TICK_DATA,
            access_level=AccessLevel.READ_ONLY,
            parameters={
                'columns': [
                    'symbol',
                    'SUM(volume) as total_volume',
                    'AVG(volume) as avg_volume',
                    'MAX(volume) as max_volume',
                    'COUNT(*) as tick_count'
                ]
            },
            filters={
                'symbol': symbol,
                'timestamp_utc': f"BETWEEN '{start_time.isoformat()}' AND '{end_time.isoformat()}'"
            },
            group_by='symbol'
        )
        
        return await self.execute_query(request, component)
    
    def get_status(self) -> Dict[str, Any]:
        """Get data access layer status"""
        return {
            'is_active': self.is_active,
            'database_connections': len(self.connections),
            'cache_size': len(self.query_cache),
            'cache_ttl': self.cache_ttl,
            'max_cache_size': self.max_cache_size,
            'access_controls': {k: v.value for k, v in self.access_controls.items()},
            'performance_metrics': self.performance_metrics,
            'available_data_sources': [ds.value for ds in DataSource],
            'available_query_types': [qt.value for qt in QueryType]
        }
