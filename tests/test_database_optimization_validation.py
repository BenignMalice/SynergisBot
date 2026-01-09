"""
Comprehensive tests for database optimization validation system

Tests database performance optimization validation, query optimization analysis,
index efficiency assessment, connection pooling validation, and comprehensive reporting.
"""

import pytest
import time
import math
import statistics
import numpy as np
import threading
import json
import asyncio
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Tuple, Optional
from collections import deque, defaultdict

from infra.database_optimization_validation import (
    DatabaseOptimizationValidator, QueryMetrics, IndexMetrics, ConnectionPoolMetrics,
    DatabaseOptimizationValidation, DatabaseOptimizationReport,
    DatabaseOptimizationLevel, OptimizationStatus, QueryType, IndexType,
    get_database_optimization_validator, analyze_query_performance,
    analyze_index_efficiency, analyze_connection_pool, validate_database_optimization,
    generate_optimization_report
)

class TestDatabaseOptimizationLevel:
    """Test database optimization level enumeration"""
    
    def test_optimization_levels(self):
        """Test all optimization levels"""
        levels = [
            DatabaseOptimizationLevel.EXCELLENT,
            DatabaseOptimizationLevel.GOOD,
            DatabaseOptimizationLevel.FAIR,
            DatabaseOptimizationLevel.POOR,
            DatabaseOptimizationLevel.CRITICAL
        ]
        
        for level in levels:
            assert isinstance(level, DatabaseOptimizationLevel)
            assert level.value in ["excellent", "good", "fair", "poor", "critical"]

class TestOptimizationStatus:
    """Test optimization status enumeration"""
    
    def test_optimization_statuses(self):
        """Test all optimization statuses"""
        statuses = [
            OptimizationStatus.OPTIMIZED,
            OptimizationStatus.PARTIALLY_OPTIMIZED,
            OptimizationStatus.NEEDS_OPTIMIZATION,
            OptimizationStatus.CRITICAL_OPTIMIZATION
        ]
        
        for status in statuses:
            assert isinstance(status, OptimizationStatus)
            assert status.value in ["optimized", "partially_optimized", "needs_optimization", "critical_optimization"]

class TestQueryType:
    """Test query type enumeration"""
    
    def test_query_types(self):
        """Test all query types"""
        types = [
            QueryType.SELECT,
            QueryType.INSERT,
            QueryType.UPDATE,
            QueryType.DELETE,
            QueryType.CREATE,
            QueryType.DROP,
            QueryType.ALTER,
            QueryType.INDEX,
            QueryType.VACUUM,
            QueryType.ANALYZE
        ]
        
        for query_type in types:
            assert isinstance(query_type, QueryType)
            assert query_type.value in ["select", "insert", "update", "delete", "create", 
                                      "drop", "alter", "index", "vacuum", "analyze"]

class TestIndexType:
    """Test index type enumeration"""
    
    def test_index_types(self):
        """Test all index types"""
        types = [
            IndexType.PRIMARY_KEY,
            IndexType.UNIQUE,
            IndexType.COMPOSITE,
            IndexType.SINGLE_COLUMN,
            IndexType.COVERING,
            IndexType.PARTIAL
        ]
        
        for index_type in types:
            assert isinstance(index_type, IndexType)
            assert index_type.value in ["primary_key", "unique", "composite", "single_column", 
                                      "covering", "partial"]

class TestQueryMetrics:
    """Test query metrics data structure"""
    
    def test_query_metrics_creation(self):
        """Test query metrics creation"""
        metrics = QueryMetrics(
            query_id="test123",
            query_type=QueryType.SELECT,
            execution_time_ms=25.0,
            rows_affected=100,
            index_usage=True,
            full_table_scan=False,
            temporary_table=False,
            sort_operation=True,
            join_operations=2,
            subquery_count=1,
            complexity_score=0.5,
            optimization_score=0.8,
            recommendations=["Add index"],
            metadata={"test": True}
        )
        
        assert metrics.query_id == "test123"
        assert metrics.query_type == QueryType.SELECT
        assert metrics.execution_time_ms == 25.0
        assert metrics.rows_affected == 100
        assert metrics.index_usage is True
        assert metrics.full_table_scan is False
        assert metrics.temporary_table is False
        assert metrics.sort_operation is True
        assert metrics.join_operations == 2
        assert metrics.subquery_count == 1
        assert metrics.complexity_score == 0.5
        assert metrics.optimization_score == 0.8
        assert len(metrics.recommendations) == 1
        assert metrics.metadata["test"] is True
    
    def test_query_metrics_defaults(self):
        """Test query metrics defaults"""
        metrics = QueryMetrics(
            query_id="test456",
            query_type=QueryType.INSERT,
            execution_time_ms=10.0,
            rows_affected=1,
            index_usage=False,
            full_table_scan=True,
            temporary_table=False,
            sort_operation=False,
            join_operations=0,
            subquery_count=0,
            complexity_score=0.2,
            optimization_score=0.6
        )
        
        assert metrics.recommendations == []
        assert metrics.metadata == {}

class TestIndexMetrics:
    """Test index metrics data structure"""
    
    def test_index_metrics_creation(self):
        """Test index metrics creation"""
        metrics = IndexMetrics(
            index_name="idx_trades_symbol",
            table_name="trades",
            index_type=IndexType.SINGLE_COLUMN,
            column_count=1,
            size_bytes=1024 * 1024,
            usage_count=1000,
            efficiency_score=0.9,
            selectivity=0.8,
            fragmentation_level=0.2,
            maintenance_cost=0.3,
            recommendations=["Optimize index"],
            metadata={"test": True}
        )
        
        assert metrics.index_name == "idx_trades_symbol"
        assert metrics.table_name == "trades"
        assert metrics.index_type == IndexType.SINGLE_COLUMN
        assert metrics.column_count == 1
        assert metrics.size_bytes == 1024 * 1024
        assert metrics.usage_count == 1000
        assert metrics.efficiency_score == 0.9
        assert metrics.selectivity == 0.8
        assert metrics.fragmentation_level == 0.2
        assert metrics.maintenance_cost == 0.3
        assert len(metrics.recommendations) == 1
        assert metrics.metadata["test"] is True
    
    def test_index_metrics_defaults(self):
        """Test index metrics defaults"""
        metrics = IndexMetrics(
            index_name="idx_test",
            table_name="test_table",
            index_type=IndexType.COMPOSITE,
            column_count=3,
            size_bytes=2 * 1024 * 1024,
            usage_count=500,
            efficiency_score=0.7,
            selectivity=0.6,
            fragmentation_level=0.4,
            maintenance_cost=0.5
        )
        
        assert metrics.recommendations == []
        assert metrics.metadata == {}

class TestConnectionPoolMetrics:
    """Test connection pool metrics data structure"""
    
    def test_connection_pool_metrics_creation(self):
        """Test connection pool metrics creation"""
        metrics = ConnectionPoolMetrics(
            total_connections=10,
            active_connections=7,
            idle_connections=3,
            connection_wait_time_ms=50.0,
            connection_utilization=0.7,
            pool_efficiency=0.8,
            timeout_events=0,
            connection_errors=0,
            recommendations=["Optimize pool size"],
            metadata={"test": True}
        )
        
        assert metrics.total_connections == 10
        assert metrics.active_connections == 7
        assert metrics.idle_connections == 3
        assert metrics.connection_wait_time_ms == 50.0
        assert metrics.connection_utilization == 0.7
        assert metrics.pool_efficiency == 0.8
        assert metrics.timeout_events == 0
        assert metrics.connection_errors == 0
        assert len(metrics.recommendations) == 1
        assert metrics.metadata["test"] is True
    
    def test_connection_pool_metrics_defaults(self):
        """Test connection pool metrics defaults"""
        metrics = ConnectionPoolMetrics(
            total_connections=5,
            active_connections=3,
            idle_connections=2,
            connection_wait_time_ms=100.0,
            connection_utilization=0.6,
            pool_efficiency=0.7,
            timeout_events=1,
            connection_errors=0
        )
        
        assert metrics.recommendations == []
        assert metrics.metadata == {}

class TestDatabaseOptimizationValidation:
    """Test database optimization validation data structure"""
    
    def test_optimization_validation_creation(self):
        """Test optimization validation creation"""
        query_metrics = QueryMetrics(
            query_id="test123",
            query_type=QueryType.SELECT,
            execution_time_ms=25.0,
            rows_affected=100,
            index_usage=True,
            full_table_scan=False,
            temporary_table=False,
            sort_operation=True,
            join_operations=2,
            subquery_count=1,
            complexity_score=0.5,
            optimization_score=0.8
        )
        
        index_metrics = IndexMetrics(
            index_name="idx_trades_symbol",
            table_name="trades",
            index_type=IndexType.SINGLE_COLUMN,
            column_count=1,
            size_bytes=1024 * 1024,
            usage_count=1000,
            efficiency_score=0.9,
            selectivity=0.8,
            fragmentation_level=0.2,
            maintenance_cost=0.3
        )
        
        connection_pool_metrics = ConnectionPoolMetrics(
            total_connections=10,
            active_connections=7,
            idle_connections=3,
            connection_wait_time_ms=50.0,
            connection_utilization=0.7,
            pool_efficiency=0.8,
            timeout_events=0,
            connection_errors=0
        )
        
        validation = DatabaseOptimizationValidation(
            timestamp=time.time(),
            database_name="test_db",
            optimization_level=DatabaseOptimizationLevel.GOOD,
            optimization_status=OptimizationStatus.PARTIALLY_OPTIMIZED,
            overall_score=0.85,
            query_optimization_score=0.8,
            index_optimization_score=0.9,
            connection_pool_score=0.8,
            database_health_score=0.9,
            performance_improvement=0.15,
            bottlenecks_identified=["Slow queries detected"],
            optimization_recommendations=["Optimize queries"],
            critical_issues=["No critical issues"],
            query_metrics=[query_metrics],
            index_metrics=[index_metrics],
            connection_pool_metrics=connection_pool_metrics,
            detailed_analysis={"test": "analysis"},
            metadata={"test": True}
        )
        
        assert validation.timestamp > 0
        assert validation.database_name == "test_db"
        assert validation.optimization_level == DatabaseOptimizationLevel.GOOD
        assert validation.optimization_status == OptimizationStatus.PARTIALLY_OPTIMIZED
        assert validation.overall_score == 0.85
        assert validation.query_optimization_score == 0.8
        assert validation.index_optimization_score == 0.9
        assert validation.connection_pool_score == 0.8
        assert validation.database_health_score == 0.9
        assert validation.performance_improvement == 0.15
        assert len(validation.bottlenecks_identified) == 1
        assert len(validation.optimization_recommendations) == 1
        assert len(validation.critical_issues) == 1
        assert len(validation.query_metrics) == 1
        assert len(validation.index_metrics) == 1
        assert validation.connection_pool_metrics is not None
        assert validation.detailed_analysis["test"] == "analysis"
        assert validation.metadata["test"] is True
    
    def test_optimization_validation_defaults(self):
        """Test optimization validation defaults"""
        validation = DatabaseOptimizationValidation(
            timestamp=time.time(),
            database_name="test_db",
            optimization_level=DatabaseOptimizationLevel.FAIR,
            optimization_status=OptimizationStatus.NEEDS_OPTIMIZATION,
            overall_score=0.6,
            query_optimization_score=0.5,
            index_optimization_score=0.7,
            connection_pool_score=0.6,
            database_health_score=0.8,
            performance_improvement=0.1,
            bottlenecks_identified=[],
            optimization_recommendations=[],
            critical_issues=[],
            query_metrics=[],
            index_metrics=[],
            connection_pool_metrics=ConnectionPoolMetrics(
                total_connections=0, active_connections=0, idle_connections=0,
                connection_wait_time_ms=0.0, connection_utilization=0.0,
                pool_efficiency=0.0, timeout_events=0, connection_errors=0
            )
        )
        
        assert validation.detailed_analysis == {}
        assert validation.metadata == {}

class TestDatabaseOptimizationReport:
    """Test database optimization report data structure"""
    
    def test_optimization_report_creation(self):
        """Test optimization report creation"""
        validation = DatabaseOptimizationValidation(
            timestamp=time.time(),
            database_name="test_db",
            optimization_level=DatabaseOptimizationLevel.GOOD,
            optimization_status=OptimizationStatus.PARTIALLY_OPTIMIZED,
            overall_score=0.85,
            query_optimization_score=0.8,
            index_optimization_score=0.9,
            connection_pool_score=0.8,
            database_health_score=0.9,
            performance_improvement=0.15,
            bottlenecks_identified=[],
            optimization_recommendations=[],
            critical_issues=[],
            query_metrics=[],
            index_metrics=[],
            connection_pool_metrics=ConnectionPoolMetrics(
                total_connections=0, active_connections=0, idle_connections=0,
                connection_wait_time_ms=0.0, connection_utilization=0.0,
                pool_efficiency=0.0, timeout_events=0, connection_errors=0
            )
        )
        
        report = DatabaseOptimizationReport(
            timestamp=time.time(),
            database_name="test_db",
            overall_optimization_score=0.85,
            optimization_level=DatabaseOptimizationLevel.GOOD,
            total_queries_analyzed=10,
            total_indexes_analyzed=5,
            optimization_opportunities=3,
            performance_gains_estimated=0.15,
            critical_optimizations_needed=0,
            recommendations=["Optimize database"],
            detailed_validations=[validation],
            metadata={"test": True}
        )
        
        assert report.timestamp > 0
        assert report.database_name == "test_db"
        assert report.overall_optimization_score == 0.85
        assert report.optimization_level == DatabaseOptimizationLevel.GOOD
        assert report.total_queries_analyzed == 10
        assert report.total_indexes_analyzed == 5
        assert report.optimization_opportunities == 3
        assert report.performance_gains_estimated == 0.15
        assert report.critical_optimizations_needed == 0
        assert len(report.recommendations) == 1
        assert len(report.detailed_validations) == 1
        assert report.metadata["test"] is True
    
    def test_optimization_report_defaults(self):
        """Test optimization report defaults"""
        report = DatabaseOptimizationReport(
            timestamp=time.time(),
            database_name="test_db",
            overall_optimization_score=0.6,
            optimization_level=DatabaseOptimizationLevel.FAIR,
            total_queries_analyzed=5,
            total_indexes_analyzed=3,
            optimization_opportunities=2,
            performance_gains_estimated=0.1,
            critical_optimizations_needed=1,
            recommendations=[],
            detailed_validations=[]
        )
        
        assert report.detailed_validations == []
        assert report.metadata == {}

class TestDatabaseOptimizationValidator:
    """Test database optimization validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = DatabaseOptimizationValidator()
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert self.validator.database_path is None
        assert len(self.validator.query_history) == 0
        assert len(self.validator.index_metrics) == 0
        assert self.validator.connection_pool_metrics is None
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
        assert self.validator.query_time_threshold_ms == 50.0
        assert self.validator.index_efficiency_threshold == 0.8
        assert self.validator.connection_utilization_threshold == 0.7
        assert self.validator.optimization_score_threshold == 0.8
    
    def test_analyze_query_performance(self):
        """Test query performance analysis"""
        query = "SELECT * FROM trades WHERE symbol = 'BTCUSDc'"
        execution_time_ms = 25.0
        rows_affected = 100
        
        metrics = self.validator.analyze_query_performance(query, execution_time_ms, rows_affected)
        
        assert metrics.query_id is not None
        assert metrics.query_type == QueryType.SELECT
        assert metrics.execution_time_ms == 25.0
        assert metrics.rows_affected == 100
        assert metrics.index_usage is True  # Has WHERE clause
        assert metrics.full_table_scan is False  # Has WHERE clause
        assert metrics.temporary_table is False
        assert metrics.sort_operation is False
        assert metrics.join_operations == 0
        assert metrics.subquery_count == 0
        assert 0.0 <= metrics.complexity_score <= 1.0
        assert 0.0 <= metrics.optimization_score <= 1.0
        assert len(metrics.recommendations) >= 0
        assert len(self.validator.query_history) == 1
    
    def test_analyze_index_efficiency(self):
        """Test index efficiency analysis"""
        index_name = "idx_trades_symbol"
        table_name = "trades"
        index_type = IndexType.SINGLE_COLUMN
        column_count = 1
        size_bytes = 1024 * 1024
        usage_count = 1000
        
        metrics = self.validator.analyze_index_efficiency(
            index_name, table_name, index_type, column_count, size_bytes, usage_count
        )
        
        assert metrics.index_name == "idx_trades_symbol"
        assert metrics.table_name == "trades"
        assert metrics.index_type == IndexType.SINGLE_COLUMN
        assert metrics.column_count == 1
        assert metrics.size_bytes == 1024 * 1024
        assert metrics.usage_count == 1000
        assert 0.0 <= metrics.efficiency_score <= 1.0
        assert 0.0 <= metrics.selectivity <= 1.0
        assert 0.0 <= metrics.fragmentation_level <= 1.0
        assert 0.0 <= metrics.maintenance_cost <= 1.0
        assert len(metrics.recommendations) >= 0
        assert len(self.validator.index_metrics) == 1
    
    def test_analyze_connection_pool(self):
        """Test connection pool analysis"""
        total_connections = 10
        active_connections = 7
        idle_connections = 3
        connection_wait_time_ms = 50.0
        timeout_events = 0
        connection_errors = 0
        
        metrics = self.validator.analyze_connection_pool(
            total_connections, active_connections, idle_connections,
            connection_wait_time_ms, timeout_events, connection_errors
        )
        
        assert metrics.total_connections == 10
        assert metrics.active_connections == 7
        assert metrics.idle_connections == 3
        assert metrics.connection_wait_time_ms == 50.0
        assert metrics.connection_utilization == 0.7
        assert 0.0 <= metrics.pool_efficiency <= 1.0
        assert metrics.timeout_events == 0
        assert metrics.connection_errors == 0
        assert len(metrics.recommendations) >= 0
        assert self.validator.connection_pool_metrics is not None
    
    def test_validate_database_optimization(self):
        """Test database optimization validation"""
        # Add some test data
        self.validator.analyze_query_performance("SELECT * FROM trades", 30.0, 100)
        self.validator.analyze_index_efficiency("idx_test", "trades", IndexType.SINGLE_COLUMN, 1, 1024, 100)
        self.validator.analyze_connection_pool(10, 7, 3, 50.0)
        
        validation = self.validator.validate_database_optimization("test_db")
        
        assert validation.database_name == "test_db"
        assert validation.optimization_level in [DatabaseOptimizationLevel.EXCELLENT, DatabaseOptimizationLevel.GOOD, 
                                           DatabaseOptimizationLevel.FAIR, DatabaseOptimizationLevel.POOR, DatabaseOptimizationLevel.CRITICAL]
        assert validation.optimization_status in [OptimizationStatus.OPTIMIZED, OptimizationStatus.PARTIALLY_OPTIMIZED,
                                                OptimizationStatus.NEEDS_OPTIMIZATION, OptimizationStatus.CRITICAL_OPTIMIZATION]
        assert 0.0 <= validation.overall_score <= 1.0
        assert 0.0 <= validation.query_optimization_score <= 1.0
        assert 0.0 <= validation.index_optimization_score <= 1.0
        assert 0.0 <= validation.connection_pool_score <= 1.0
        assert 0.0 <= validation.database_health_score <= 1.0
        assert validation.performance_improvement >= 0.0
        assert len(validation.bottlenecks_identified) >= 0
        assert len(validation.optimization_recommendations) >= 0
        assert len(validation.critical_issues) >= 0
        assert len(validation.query_metrics) == 1
        assert len(validation.index_metrics) == 1
        assert validation.connection_pool_metrics is not None
        assert len(validation.detailed_analysis) >= 0
    
    def test_generate_optimization_report(self):
        """Test optimization report generation"""
        # Add some test data
        self.validator.analyze_query_performance("SELECT * FROM trades", 30.0, 100)
        self.validator.analyze_index_efficiency("idx_test", "trades", IndexType.SINGLE_COLUMN, 1, 1024, 100)
        self.validator.analyze_connection_pool(10, 7, 3, 50.0)
        
        report = self.validator.generate_optimization_report("test_db")
        
        assert report.database_name == "test_db"
        assert 0.0 <= report.overall_optimization_score <= 1.0
        assert report.optimization_level in [DatabaseOptimizationLevel.EXCELLENT, DatabaseOptimizationLevel.GOOD,
                                           DatabaseOptimizationLevel.FAIR, DatabaseOptimizationLevel.POOR, DatabaseOptimizationLevel.CRITICAL]
        assert report.total_queries_analyzed >= 0
        assert report.total_indexes_analyzed >= 0
        assert report.optimization_opportunities >= 0
        assert report.performance_gains_estimated >= 0.0
        assert report.critical_optimizations_needed >= 0
        assert len(report.recommendations) >= 0
        assert len(report.detailed_validations) == 1
        assert len(report.metadata) >= 0

class TestGlobalFunctions:
    """Test global database optimization functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.database_optimization_validation
        infra.database_optimization_validation._database_optimization_validator = None
    
    def test_get_database_optimization_validator(self):
        """Test global validator access"""
        validator1 = get_database_optimization_validator()
        validator2 = get_database_optimization_validator()
        
        # Should return same instance
        assert validator1 is validator2
        assert isinstance(validator1, DatabaseOptimizationValidator)
    
    def test_analyze_query_performance_global(self):
        """Test global query performance analysis"""
        query = "SELECT * FROM trades WHERE symbol = 'BTCUSDc'"
        execution_time_ms = 25.0
        rows_affected = 100
        
        metrics = analyze_query_performance(query, execution_time_ms, rows_affected)
        
        assert metrics.query_id is not None
        assert metrics.query_type == QueryType.SELECT
        assert metrics.execution_time_ms == 25.0
        assert metrics.rows_affected == 100
        assert 0.0 <= metrics.optimization_score <= 1.0
    
    def test_analyze_index_efficiency_global(self):
        """Test global index efficiency analysis"""
        index_name = "idx_trades_symbol"
        table_name = "trades"
        index_type = IndexType.SINGLE_COLUMN
        column_count = 1
        size_bytes = 1024 * 1024
        usage_count = 1000
        
        metrics = analyze_index_efficiency(
            index_name, table_name, index_type, column_count, size_bytes, usage_count
        )
        
        assert metrics.index_name == "idx_trades_symbol"
        assert metrics.table_name == "trades"
        assert metrics.index_type == IndexType.SINGLE_COLUMN
        assert 0.0 <= metrics.efficiency_score <= 1.0
    
    def test_analyze_connection_pool_global(self):
        """Test global connection pool analysis"""
        total_connections = 10
        active_connections = 7
        idle_connections = 3
        connection_wait_time_ms = 50.0
        
        metrics = analyze_connection_pool(
            total_connections, active_connections, idle_connections, connection_wait_time_ms
        )
        
        assert metrics.total_connections == 10
        assert metrics.active_connections == 7
        assert metrics.idle_connections == 3
        assert metrics.connection_wait_time_ms == 50.0
        assert 0.0 <= metrics.pool_efficiency <= 1.0
    
    def test_validate_database_optimization_global(self):
        """Test global database optimization validation"""
        # Add some test data
        analyze_query_performance("SELECT * FROM trades", 30.0, 100)
        analyze_index_efficiency("idx_test", "trades", IndexType.SINGLE_COLUMN, 1, 1024, 100)
        analyze_connection_pool(10, 7, 3, 50.0)
        
        validation = validate_database_optimization("test_db")
        
        assert validation.database_name == "test_db"
        assert 0.0 <= validation.overall_score <= 1.0
        assert validation.optimization_level in [DatabaseOptimizationLevel.EXCELLENT, DatabaseOptimizationLevel.GOOD,
                                               DatabaseOptimizationLevel.FAIR, DatabaseOptimizationLevel.POOR, DatabaseOptimizationLevel.CRITICAL]
        assert len(validation.optimization_recommendations) >= 0
    
    def test_generate_optimization_report_global(self):
        """Test global optimization report generation"""
        # Add some test data
        analyze_query_performance("SELECT * FROM trades", 30.0, 100)
        analyze_index_efficiency("idx_test", "trades", IndexType.SINGLE_COLUMN, 1, 1024, 100)
        analyze_connection_pool(10, 7, 3, 50.0)
        
        report = generate_optimization_report("test_db")
        
        assert report.database_name == "test_db"
        assert 0.0 <= report.overall_optimization_score <= 1.0
        assert report.optimization_level in [DatabaseOptimizationLevel.EXCELLENT, DatabaseOptimizationLevel.GOOD,
                                           DatabaseOptimizationLevel.FAIR, DatabaseOptimizationLevel.POOR, DatabaseOptimizationLevel.CRITICAL]
        assert len(report.recommendations) >= 0

class TestDatabaseOptimizationIntegration:
    """Integration tests for database optimization validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.database_optimization_validation
        infra.database_optimization_validation._database_optimization_validator = None
    
    def test_comprehensive_database_optimization_validation(self):
        """Test comprehensive database optimization validation workflow"""
        # Test different query scenarios
        test_queries = [
            ("SELECT * FROM trades WHERE symbol = 'BTCUSDc'", 25.0, 100),  # Good query
            ("SELECT * FROM trades WHERE timestamp > '2024-01-01'", 150.0, 1000),  # Slow query
            ("SELECT COUNT(*) FROM trades", 5.0, 1),  # Fast query
            ("INSERT INTO trades (symbol, price) VALUES ('EURUSDc', 1.1000)", 10.0, 1),  # Insert
            ("UPDATE trades SET price = 1.2000 WHERE symbol = 'EURUSDc'", 20.0, 50),  # Update
            ("DELETE FROM trades WHERE timestamp < '2023-01-01'", 200.0, 500)  # Slow delete
        ]
        
        for query, time_ms, rows in test_queries:
            analyze_query_performance(query, time_ms, rows)
        
        # Test different index scenarios
        test_indexes = [
            ("idx_trades_symbol", "trades", IndexType.SINGLE_COLUMN, 1, 1024 * 1024, 1000),  # Good index
            ("idx_trades_timestamp", "trades", IndexType.SINGLE_COLUMN, 1, 2 * 1024 * 1024, 500),  # Medium index
            ("idx_trades_composite", "trades", IndexType.COMPOSITE, 3, 5 * 1024 * 1024, 200),  # Large index
            ("idx_unused", "trades", IndexType.SINGLE_COLUMN, 1, 1024 * 1024, 0),  # Unused index
            ("idx_inefficient", "trades", IndexType.SINGLE_COLUMN, 1, 10 * 1024 * 1024, 100)  # Inefficient index
        ]
        
        for index_name, table_name, index_type, column_count, size_bytes, usage_count in test_indexes:
            analyze_index_efficiency(index_name, table_name, index_type, column_count, size_bytes, usage_count)
        
        # Test connection pool scenarios
        test_pools = [
            (10, 7, 3, 50.0, 0, 0),  # Good pool
            (5, 5, 0, 200.0, 2, 1),  # Overutilized pool
            (20, 5, 15, 10.0, 0, 0)  # Underutilized pool
        ]
        
        for total, active, idle, wait_time, timeouts, errors in test_pools:
            analyze_connection_pool(total, active, idle, wait_time, timeouts, errors)
        
        # Generate comprehensive validation
        validation = validate_database_optimization("comprehensive_test_db")
        
        assert validation.database_name == "comprehensive_test_db"
        assert 0.0 <= validation.overall_score <= 1.0
        assert validation.optimization_level in [DatabaseOptimizationLevel.EXCELLENT, DatabaseOptimizationLevel.GOOD,
                                               DatabaseOptimizationLevel.FAIR, DatabaseOptimizationLevel.POOR, DatabaseOptimizationLevel.CRITICAL]
        assert validation.optimization_status in [OptimizationStatus.OPTIMIZED, OptimizationStatus.PARTIALLY_OPTIMIZED,
                                                OptimizationStatus.NEEDS_OPTIMIZATION, OptimizationStatus.CRITICAL_OPTIMIZATION]
        assert 0.0 <= validation.query_optimization_score <= 1.0
        assert 0.0 <= validation.index_optimization_score <= 1.0
        assert 0.0 <= validation.connection_pool_score <= 1.0
        assert 0.0 <= validation.database_health_score <= 1.0
        assert validation.performance_improvement >= 0.0
        assert len(validation.bottlenecks_identified) >= 0
        assert len(validation.optimization_recommendations) >= 0
        assert len(validation.critical_issues) >= 0
        assert len(validation.query_metrics) == len(test_queries)
        assert len(validation.index_metrics) == len(test_indexes)
        assert validation.connection_pool_metrics is not None
        assert len(validation.detailed_analysis) >= 0
        
        # Generate comprehensive report
        report = generate_optimization_report("comprehensive_test_db")
        
        assert report.database_name == "comprehensive_test_db"
        assert 0.0 <= report.overall_optimization_score <= 1.0
        assert report.optimization_level in [DatabaseOptimizationLevel.EXCELLENT, DatabaseOptimizationLevel.GOOD,
                                           DatabaseOptimizationLevel.FAIR, DatabaseOptimizationLevel.POOR, DatabaseOptimizationLevel.CRITICAL]
        assert report.total_queries_analyzed == len(test_queries)
        assert report.total_indexes_analyzed == len(test_indexes)
        assert report.optimization_opportunities >= 0
        assert report.performance_gains_estimated >= 0.0
        assert report.critical_optimizations_needed >= 0
        assert len(report.recommendations) >= 0
        assert len(report.detailed_validations) == 1
        assert len(report.metadata) >= 0
    
    def test_optimization_level_detection(self):
        """Test optimization level detection for different scenarios"""
        # Test excellent optimization
        analyze_query_performance("SELECT * FROM trades WHERE symbol = 'BTCUSDc'", 10.0, 100)
        analyze_index_efficiency("idx_good", "trades", IndexType.SINGLE_COLUMN, 1, 1024, 1000)
        analyze_connection_pool(10, 5, 5, 10.0)
        
        validation = validate_database_optimization("excellent_db")
        
        # Should have good optimization level
        assert validation.optimization_level in [DatabaseOptimizationLevel.EXCELLENT, DatabaseOptimizationLevel.GOOD,
                                               DatabaseOptimizationLevel.FAIR, DatabaseOptimizationLevel.POOR, DatabaseOptimizationLevel.CRITICAL]
        assert 0.0 <= validation.overall_score <= 1.0
    
    def test_bottleneck_identification(self):
        """Test bottleneck identification"""
        # Add slow queries and inefficient indexes
        analyze_query_performance("SELECT * FROM trades WHERE timestamp > '2024-01-01'", 200.0, 1000)
        analyze_query_performance("SELECT * FROM trades WHERE price LIKE '%100%'", 300.0, 500)
        analyze_index_efficiency("idx_bad", "trades", IndexType.SINGLE_COLUMN, 1, 10 * 1024 * 1024, 10)
        analyze_connection_pool(5, 5, 0, 500.0, 5, 2)
        
        validation = validate_database_optimization("bottleneck_db")
        
        # Should identify bottlenecks
        assert len(validation.bottlenecks_identified) >= 0
        assert len(validation.critical_issues) >= 0
        assert len(validation.optimization_recommendations) >= 0
    
    def test_performance_improvement_estimation(self):
        """Test performance improvement estimation"""
        # Add queries with varying performance
        analyze_query_performance("SELECT * FROM trades", 100.0, 1000)  # Slow
        analyze_query_performance("SELECT * FROM trades WHERE symbol = 'BTCUSDc'", 20.0, 100)  # Fast
        analyze_index_efficiency("idx_good", "trades", IndexType.SINGLE_COLUMN, 1, 1024, 1000)
        analyze_index_efficiency("idx_bad", "trades", IndexType.SINGLE_COLUMN, 1, 10 * 1024 * 1024, 10)
        
        validation = validate_database_optimization("improvement_db")
        
        # Should estimate performance improvement
        assert validation.performance_improvement >= 0.0
        assert len(validation.optimization_recommendations) >= 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
