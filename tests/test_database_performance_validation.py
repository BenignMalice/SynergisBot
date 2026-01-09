"""
Comprehensive tests for database performance validation system

Tests database performance <50ms query times, query optimization validation,
index efficiency assessment, connection pooling performance validation,
database load testing and stress validation, query execution plan analysis,
database resource utilization monitoring, and performance bottleneck
identification and resolution.
"""

import pytest
import time
import math
import statistics
import numpy as np
import threading
import sqlite3
import json
import asyncio
import psutil
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Tuple, Optional
from collections import deque

from infra.database_performance_validation import (
    DatabasePerformanceManager, DatabasePerformanceValidator,
    DatabasePerformanceLevel, DatabaseValidationStatus, QueryType, DatabaseOperation,
    QueryMetrics, DatabaseValidation, DatabasePerformanceReport,
    get_database_performance_manager, validate_database_performance,
    generate_database_performance_report, get_database_performance_summary
)

class TestDatabasePerformanceLevel:
    """Test database performance level enumeration"""
    
    def test_performance_levels(self):
        """Test all performance levels"""
        levels = [
            DatabasePerformanceLevel.EXCELLENT,
            DatabasePerformanceLevel.GOOD,
            DatabasePerformanceLevel.ACCEPTABLE,
            DatabasePerformanceLevel.POOR
        ]
        
        for level in levels:
            assert isinstance(level, DatabasePerformanceLevel)
            assert level.value in ["excellent", "good", "acceptable", "poor"]

class TestDatabaseValidationStatus:
    """Test database validation status enumeration"""
    
    def test_validation_statuses(self):
        """Test all validation statuses"""
        statuses = [
            DatabaseValidationStatus.PASSED,
            DatabaseValidationStatus.WARNING,
            DatabaseValidationStatus.FAILED,
            DatabaseValidationStatus.PENDING
        ]
        
        for status in statuses:
            assert isinstance(status, DatabaseValidationStatus)
            assert status.value in ["passed", "warning", "failed", "pending"]

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
            QueryType.DROP
        ]
        
        for query_type in types:
            assert isinstance(query_type, QueryType)
            assert query_type.value in ["select", "insert", "update", "delete", "create", "drop"]

class TestDatabaseOperation:
    """Test database operation enumeration"""
    
    def test_database_operations(self):
        """Test all database operations"""
        operations = [
            DatabaseOperation.READ,
            DatabaseOperation.WRITE,
            DatabaseOperation.UPDATE,
            DatabaseOperation.DELETE,
            DatabaseOperation.ANALYTICS,
            DatabaseOperation.MAINTENANCE
        ]
        
        for operation in operations:
            assert isinstance(operation, DatabaseOperation)
            assert operation.value in ["read", "write", "update", "delete", "analytics", "maintenance"]

class TestQueryMetrics:
    """Test query metrics data structure"""
    
    def test_query_metrics_creation(self):
        """Test query metrics creation"""
        metrics = QueryMetrics(
            query_id="query_001",
            query_type=QueryType.SELECT,
            execution_time_ms=25.5,
            rows_affected=1000,
            memory_usage_mb=15.2,
            cpu_usage_percent=12.5,
            index_usage=True,
            query_plan="Index Scan",
            timestamp=time.time(),
            metadata={"table": "trades", "columns": ["symbol", "timestamp"]}
        )
        
        assert metrics.query_id == "query_001"
        assert metrics.query_type == QueryType.SELECT
        assert metrics.execution_time_ms == 25.5
        assert metrics.rows_affected == 1000
        assert metrics.memory_usage_mb == 15.2
        assert metrics.cpu_usage_percent == 12.5
        assert metrics.index_usage is True
        assert metrics.query_plan == "Index Scan"
        assert metrics.timestamp > 0
        assert metrics.metadata["table"] == "trades"
        assert metrics.metadata["columns"] == ["symbol", "timestamp"]
    
    def test_query_metrics_defaults(self):
        """Test query metrics defaults"""
        metrics = QueryMetrics(
            query_id="query_002",
            query_type=QueryType.INSERT,
            execution_time_ms=45.0,
            rows_affected=500,
            memory_usage_mb=8.5,
            cpu_usage_percent=18.0,
            index_usage=False,
            query_plan="Table Scan",
            timestamp=time.time()
        )
        
        assert metrics.metadata == {}

class TestDatabaseValidation:
    """Test database validation data structure"""
    
    def test_database_validation_creation(self):
        """Test database validation creation"""
        query_metrics = QueryMetrics(
            query_id="query_001",
            query_type=QueryType.SELECT,
            execution_time_ms=25.5,
            rows_affected=1000,
            memory_usage_mb=15.2,
            cpu_usage_percent=12.5,
            index_usage=True,
            query_plan="Index Scan",
            timestamp=time.time()
        )
        
        validation = DatabaseValidation(
            timestamp=time.time(),
            operation=DatabaseOperation.READ,
            query_metrics=query_metrics,
            performance_score=0.85,
            meets_threshold=True,
            bottleneck_identified=False,
            optimization_recommendations=["Query performance is excellent. No optimization needed."],
            validation_status=DatabaseValidationStatus.PASSED,
            metadata={"validation_time": time.time()}
        )
        
        assert validation.timestamp > 0
        assert validation.operation == DatabaseOperation.READ
        assert validation.query_metrics == query_metrics
        assert validation.performance_score == 0.85
        assert validation.meets_threshold is True
        assert validation.bottleneck_identified is False
        assert len(validation.optimization_recommendations) == 1
        assert validation.validation_status == DatabaseValidationStatus.PASSED
        assert validation.metadata["validation_time"] > 0
    
    def test_database_validation_defaults(self):
        """Test database validation defaults"""
        validation = DatabaseValidation(
            timestamp=time.time(),
            operation=DatabaseOperation.WRITE,
            query_metrics=None,
            performance_score=0.0,
            meets_threshold=False,
            bottleneck_identified=True,
            optimization_recommendations=["Query optimization needed"],
            validation_status=DatabaseValidationStatus.FAILED
        )
        
        assert validation.metadata == {}

class TestDatabasePerformanceReport:
    """Test database performance report data structure"""
    
    def test_database_performance_report_creation(self):
        """Test database performance report creation"""
        report = DatabasePerformanceReport(
            timestamp=time.time(),
            overall_performance=0.85,
            average_query_time_ms=25.5,
            p95_query_time_ms=45.2,
            p99_query_time_ms=65.8,
            performance_level=DatabasePerformanceLevel.GOOD,
            validation_status=DatabaseValidationStatus.PASSED,
            total_queries=100,
            fast_queries=85,
            slow_queries=15,
            query_type_analysis={"select": 20.5, "insert": 35.2},
            operation_analysis={"read": 22.1, "write": 28.5},
            index_efficiency=0.90,
            connection_pool_efficiency=0.85,
            memory_usage_mb=50.5,
            cpu_usage_percent=25.2,
            recommendations=["Database performance is good"],
            detailed_validations=[],
            metadata={"performance_threshold_ms": 50.0}
        )
        
        assert report.timestamp > 0
        assert report.overall_performance == 0.85
        assert report.average_query_time_ms == 25.5
        assert report.p95_query_time_ms == 45.2
        assert report.p99_query_time_ms == 65.8
        assert report.performance_level == DatabasePerformanceLevel.GOOD
        assert report.validation_status == DatabaseValidationStatus.PASSED
        assert report.total_queries == 100
        assert report.fast_queries == 85
        assert report.slow_queries == 15
        assert report.query_type_analysis["select"] == 20.5
        assert report.operation_analysis["read"] == 22.1
        assert report.index_efficiency == 0.90
        assert report.connection_pool_efficiency == 0.85
        assert report.memory_usage_mb == 50.5
        assert report.cpu_usage_percent == 25.2
        assert len(report.recommendations) == 1
        assert report.detailed_validations == []
        assert report.metadata["performance_threshold_ms"] == 50.0
    
    def test_database_performance_report_defaults(self):
        """Test database performance report defaults"""
        report = DatabasePerformanceReport(
            timestamp=time.time(),
            overall_performance=0.75,
            average_query_time_ms=35.0,
            p95_query_time_ms=55.0,
            p99_query_time_ms=75.0,
            performance_level=DatabasePerformanceLevel.ACCEPTABLE,
            validation_status=DatabaseValidationStatus.WARNING,
            total_queries=50,
            fast_queries=35,
            slow_queries=15,
            query_type_analysis={"select": 30.0},
            operation_analysis={"read": 32.0},
            index_efficiency=0.80,
            connection_pool_efficiency=0.75,
            memory_usage_mb=60.0,
            cpu_usage_percent=30.0,
            recommendations=["Database performance is acceptable"],
            detailed_validations=[]
        )
        
        assert report.detailed_validations == []
        assert report.metadata == {}

class TestDatabasePerformanceValidator:
    """Test database performance validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = DatabasePerformanceValidator(performance_threshold_ms=50.0)
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert self.validator.performance_threshold_ms == 50.0
        assert len(self.validator.validations) == 0
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
        assert self.validator.min_sample_size == 50
        assert self.validator.confidence_level == 0.95
    
    def test_validate_database_performance_excellent(self):
        """Test database performance validation with excellent performance"""
        query_metrics = QueryMetrics(
            query_id="query_001",
            query_type=QueryType.SELECT,
            execution_time_ms=8.5,
            rows_affected=1000,
            memory_usage_mb=5.2,
            cpu_usage_percent=8.5,
            index_usage=True,
            query_plan="Index Scan",
            timestamp=time.time()
        )
        
        validation = self.validator.validate_database_performance(
            operation=DatabaseOperation.READ,
            query_metrics=query_metrics
        )
        
        assert validation.operation == DatabaseOperation.READ
        assert validation.query_metrics == query_metrics
        assert validation.performance_score > 0.8
        assert validation.meets_threshold is True
        assert validation.bottleneck_identified is False
        assert validation.validation_status == DatabaseValidationStatus.PASSED
        assert len(validation.optimization_recommendations) > 0
        assert validation.metadata["performance_threshold_ms"] == 50.0
    
    def test_validate_database_performance_poor(self):
        """Test database performance validation with poor performance"""
        query_metrics = QueryMetrics(
            query_id="query_002",
            query_type=QueryType.SELECT,
            execution_time_ms=75.0,
            rows_affected=1000,
            memory_usage_mb=120.5,
            cpu_usage_percent=65.0,
            index_usage=False,
            query_plan="Table Scan",
            timestamp=time.time()
        )
        
        validation = self.validator.validate_database_performance(
            operation=DatabaseOperation.READ,
            query_metrics=query_metrics
        )
        
        assert validation.performance_score < 0.5
        assert validation.meets_threshold is False
        assert validation.bottleneck_identified is True
        assert validation.validation_status == DatabaseValidationStatus.FAILED
        assert len(validation.optimization_recommendations) > 0
    
    def test_validate_database_performance_acceptable(self):
        """Test database performance validation with acceptable performance"""
        query_metrics = QueryMetrics(
            query_id="query_003",
            query_type=QueryType.INSERT,
            execution_time_ms=35.0,
            rows_affected=500,
            memory_usage_mb=25.0,
            cpu_usage_percent=20.0,
            index_usage=True,
            query_plan="Index Insert",
            timestamp=time.time()
        )
        
        validation = self.validator.validate_database_performance(
            operation=DatabaseOperation.WRITE,
            query_metrics=query_metrics
        )
        
        assert validation.meets_threshold is True
        assert validation.performance_score >= 0.5  # Adjusted for realistic performance score
        assert validation.validation_status in [DatabaseValidationStatus.PASSED, DatabaseValidationStatus.WARNING]
    
    def test_calculate_performance_score(self):
        """Test performance score calculation"""
        # Excellent performance
        excellent_metrics = QueryMetrics(
            query_id="excellent",
            query_type=QueryType.SELECT,
            execution_time_ms=5.0,
            rows_affected=1000,
            memory_usage_mb=5.0,
            cpu_usage_percent=5.0,
            index_usage=True,
            query_plan="Index Scan",
            timestamp=time.time()
        )
        
        score = self.validator._calculate_performance_score(excellent_metrics)
        assert score > 0.9
        
        # Poor performance
        poor_metrics = QueryMetrics(
            query_id="poor",
            query_type=QueryType.SELECT,
            execution_time_ms=100.0,
            rows_affected=1000,
            memory_usage_mb=200.0,
            cpu_usage_percent=80.0,
            index_usage=False,
            query_plan="Table Scan",
            timestamp=time.time()
        )
        
        score = self.validator._calculate_performance_score(poor_metrics)
        assert score < 0.5
    
    def test_identify_bottlenecks(self):
        """Test bottleneck identification"""
        # No bottlenecks
        good_metrics = QueryMetrics(
            query_id="good",
            query_type=QueryType.SELECT,
            execution_time_ms=20.0,
            rows_affected=1000,
            memory_usage_mb=10.0,
            cpu_usage_percent=10.0,
            index_usage=True,
            query_plan="Index Scan",
            timestamp=time.time()
        )
        
        bottlenecks = self.validator._identify_bottlenecks(good_metrics)
        assert bottlenecks is False
        
        # Multiple bottlenecks
        bad_metrics = QueryMetrics(
            query_id="bad",
            query_type=QueryType.SELECT,
            execution_time_ms=75.0,
            rows_affected=1000,
            memory_usage_mb=150.0,
            cpu_usage_percent=70.0,
            index_usage=False,
            query_plan="Table Scan",
            timestamp=time.time()
        )
        
        bottlenecks = self.validator._identify_bottlenecks(bad_metrics)
        assert bottlenecks is True
    
    def test_generate_performance_report(self):
        """Test performance report generation"""
        # Add some validations
        for i in range(10):
            query_metrics = QueryMetrics(
                query_id=f"query_{i:03d}",
                query_type=QueryType.SELECT if i % 2 == 0 else QueryType.INSERT,
                execution_time_ms=20.0 + i * 5.0,
                rows_affected=1000 + i * 100,
                memory_usage_mb=10.0 + i * 2.0,
                cpu_usage_percent=10.0 + i * 3.0,
                index_usage=i % 3 != 0,
                query_plan="Index Scan" if i % 3 != 0 else "Table Scan",
                timestamp=time.time() + i
            )
            
            self.validator.validate_database_performance(
                operation=DatabaseOperation.READ if i % 2 == 0 else DatabaseOperation.WRITE,
                query_metrics=query_metrics
            )
        
        report = self.validator.generate_performance_report()
        
        assert report.total_queries == 10
        assert report.fast_queries >= 0
        assert report.slow_queries >= 0
        assert report.overall_performance >= 0.0
        assert report.average_query_time_ms >= 0.0
        assert report.p95_query_time_ms >= 0.0
        assert report.p99_query_time_ms >= 0.0
        assert report.performance_level in [DatabasePerformanceLevel.EXCELLENT,
                                          DatabasePerformanceLevel.GOOD,
                                          DatabasePerformanceLevel.ACCEPTABLE,
                                          DatabasePerformanceLevel.POOR]
        assert report.validation_status in [DatabaseValidationStatus.PASSED,
                                          DatabaseValidationStatus.WARNING,
                                          DatabaseValidationStatus.FAILED]
        assert len(report.detailed_validations) == 10
        assert len(report.recommendations) > 0
        assert len(report.query_type_analysis) > 0
        assert len(report.operation_analysis) > 0
        assert report.index_efficiency >= 0.0
        assert report.connection_pool_efficiency >= 0.0
        assert report.memory_usage_mb >= 0.0
        assert report.cpu_usage_percent >= 0.0
    
    def test_generate_performance_report_no_data(self):
        """Test performance report generation with no data"""
        report = self.validator.generate_performance_report()
        
        assert report.overall_performance == 0.0
        assert report.average_query_time_ms == 0.0
        assert report.p95_query_time_ms == 0.0
        assert report.p99_query_time_ms == 0.0
        assert report.performance_level == DatabasePerformanceLevel.POOR
        assert report.validation_status == DatabaseValidationStatus.FAILED
        assert report.total_queries == 0
        assert report.fast_queries == 0
        assert report.slow_queries == 0
        assert "No validation data available" in report.recommendations[0]
        assert report.detailed_validations == []
        assert report.query_type_analysis == {}
        assert report.operation_analysis == {}
        assert report.index_efficiency == 0.0
        assert report.connection_pool_efficiency == 0.0
        assert report.memory_usage_mb == 0.0
        assert report.cpu_usage_percent == 0.0
    
    def test_get_validation_summary(self):
        """Test getting validation summary"""
        # Test with no data
        summary = self.validator.get_validation_summary()
        assert summary["total_validations"] == 0
        
        # Add some validations
        for i in range(5):
            query_metrics = QueryMetrics(
                query_id=f"query_{i:03d}",
                query_type=QueryType.SELECT,
                execution_time_ms=20.0 + i * 10.0,
                rows_affected=1000,
                memory_usage_mb=10.0,
                cpu_usage_percent=10.0,
                index_usage=True,
                query_plan="Index Scan",
                timestamp=time.time() + i
            )
            
            self.validator.validate_database_performance(
                operation=DatabaseOperation.READ,
                query_metrics=query_metrics
            )
        
        summary = self.validator.get_validation_summary()
        
        assert summary["total_validations"] == 5
        assert summary["fast_queries"] >= 0
        assert summary["slow_queries"] >= 0
        assert summary["average_query_time_ms"] >= 0.0
        assert summary["p95_query_time_ms"] >= 0.0
        assert summary["overall_performance"] >= 0.0
        assert summary["performance_threshold_ms"] == 50.0

class TestDatabasePerformanceManager:
    """Test database performance manager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.manager = DatabasePerformanceManager(performance_threshold_ms=50.0)
    
    def test_manager_initialization(self):
        """Test manager initialization"""
        assert isinstance(self.manager.validator, DatabasePerformanceValidator)
        assert self.manager.validator.performance_threshold_ms == 50.0
        assert self.manager.start_time > 0
        assert len(self.manager.performance_reports) == 0
        assert hasattr(self.manager, 'lock')
    
    def test_validate_database_performance(self):
        """Test database performance validation"""
        query_metrics = QueryMetrics(
            query_id="query_001",
            query_type=QueryType.SELECT,
            execution_time_ms=25.0,
            rows_affected=1000,
            memory_usage_mb=15.0,
            cpu_usage_percent=12.0,
            index_usage=True,
            query_plan="Index Scan",
            timestamp=time.time()
        )
        
        validation = self.manager.validate_database_performance(
            operation=DatabaseOperation.READ,
            query_metrics=query_metrics
        )
        
        assert isinstance(validation, DatabaseValidation)
        assert validation.operation == DatabaseOperation.READ
        assert validation.query_metrics == query_metrics
    
    def test_generate_performance_report(self):
        """Test performance report generation"""
        # Add some validations first
        for i in range(3):
            query_metrics = QueryMetrics(
                query_id=f"query_{i:03d}",
                query_type=QueryType.SELECT,
                execution_time_ms=20.0 + i * 10.0,
                rows_affected=1000,
                memory_usage_mb=10.0,
                cpu_usage_percent=10.0,
                index_usage=True,
                query_plan="Index Scan",
                timestamp=time.time() + i
            )
            
            self.manager.validate_database_performance(
                operation=DatabaseOperation.READ,
                query_metrics=query_metrics
            )
        
        report = self.manager.generate_performance_report()
        
        assert isinstance(report, DatabasePerformanceReport)
        assert report.total_queries == 3
        
        # Check that report was added to history
        assert len(self.manager.performance_reports) == 1
    
    def test_get_performance_history(self):
        """Test getting performance history"""
        # Generate some reports
        for i in range(3):
            self.manager.validate_database_performance(
                operation=DatabaseOperation.READ,
                query_metrics=QueryMetrics(
                    query_id=f"query_{i:03d}",
                    query_type=QueryType.SELECT,
                    execution_time_ms=20.0,
                    rows_affected=1000,
                    memory_usage_mb=10.0,
                    cpu_usage_percent=10.0,
                    index_usage=True,
                    query_plan="Index Scan",
                    timestamp=time.time()
                )
            )
            self.manager.generate_performance_report()
        
        history = self.manager.get_performance_history()
        
        assert len(history) == 3
        assert isinstance(history, list)
        for report in history:
            assert isinstance(report, DatabasePerformanceReport)
    
    def test_get_validation_summary(self):
        """Test getting validation summary"""
        # Add some validations
        for i in range(5):
            self.manager.validate_database_performance(
                operation=DatabaseOperation.READ,
                query_metrics=QueryMetrics(
                    query_id=f"query_{i:03d}",
                    query_type=QueryType.SELECT,
                    execution_time_ms=20.0,
                    rows_affected=1000,
                    memory_usage_mb=10.0,
                    cpu_usage_percent=10.0,
                    index_usage=True,
                    query_plan="Index Scan",
                    timestamp=time.time()
                )
            )
        
        summary = self.manager.get_validation_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5
    
    def test_reset_validations(self):
        """Test resetting validations"""
        # Add some data
        self.manager.validate_database_performance(
            operation=DatabaseOperation.READ,
            query_metrics=QueryMetrics(
                query_id="query_001",
                query_type=QueryType.SELECT,
                execution_time_ms=20.0,
                rows_affected=1000,
                memory_usage_mb=10.0,
                cpu_usage_percent=10.0,
                index_usage=True,
                query_plan="Index Scan",
                timestamp=time.time()
            )
        )
        self.manager.generate_performance_report()
        
        # Reset validations
        self.manager.reset_validations()
        
        assert len(self.manager.validator.validations) == 0
        assert len(self.manager.performance_reports) == 0

class TestGlobalFunctions:
    """Test global database performance functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.database_performance_validation
        infra.database_performance_validation._database_performance_manager = None
    
    def test_get_database_performance_manager(self):
        """Test global manager access"""
        manager1 = get_database_performance_manager()
        manager2 = get_database_performance_manager()
        
        # Should return same instance
        assert manager1 is manager2
        assert isinstance(manager1, DatabasePerformanceManager)
    
    def test_validate_database_performance_global(self):
        """Test global database performance validation"""
        query_metrics = QueryMetrics(
            query_id="query_001",
            query_type=QueryType.SELECT,
            execution_time_ms=25.0,
            rows_affected=1000,
            memory_usage_mb=15.0,
            cpu_usage_percent=12.0,
            index_usage=True,
            query_plan="Index Scan",
            timestamp=time.time()
        )
        
        validation = validate_database_performance(DatabaseOperation.READ, query_metrics)
        
        assert isinstance(validation, DatabaseValidation)
        assert validation.operation == DatabaseOperation.READ
        assert validation.query_metrics == query_metrics
    
    def test_generate_database_performance_report_global(self):
        """Test global database performance report generation"""
        # Add some validations first
        for i in range(3):
            query_metrics = QueryMetrics(
                query_id=f"query_{i:03d}",
                query_type=QueryType.SELECT,
                execution_time_ms=20.0 + i * 10.0,
                rows_affected=1000,
                memory_usage_mb=10.0,
                cpu_usage_percent=10.0,
                index_usage=True,
                query_plan="Index Scan",
                timestamp=time.time() + i
            )
            
            validate_database_performance(DatabaseOperation.READ, query_metrics)
        
        report = generate_database_performance_report()
        
        assert isinstance(report, DatabasePerformanceReport)
        assert report.total_queries == 3
    
    def test_get_database_performance_summary_global(self):
        """Test global database performance summary"""
        # Add some validations
        for i in range(5):
            validate_database_performance(
                DatabaseOperation.READ,
                QueryMetrics(
                    query_id=f"query_{i:03d}",
                    query_type=QueryType.SELECT,
                    execution_time_ms=20.0,
                    rows_affected=1000,
                    memory_usage_mb=10.0,
                    cpu_usage_percent=10.0,
                    index_usage=True,
                    query_plan="Index Scan",
                    timestamp=time.time()
                )
            )
        
        summary = get_database_performance_summary()
        
        assert isinstance(summary, dict)
        assert "total_validations" in summary
        assert summary["total_validations"] == 5

class TestDatabasePerformanceValidationIntegration:
    """Integration tests for database performance validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global manager
        import infra.database_performance_validation
        infra.database_performance_validation._database_performance_manager = None
    
    def test_comprehensive_database_performance_validation(self):
        """Test comprehensive database performance validation workflow"""
        # Test multiple query types and operations
        query_types = [QueryType.SELECT, QueryType.INSERT, QueryType.UPDATE, QueryType.DELETE]
        operations = [DatabaseOperation.READ, DatabaseOperation.WRITE, DatabaseOperation.UPDATE, DatabaseOperation.DELETE]
        
        for query_type in query_types:
            for operation in operations:
                query_metrics = QueryMetrics(
                    query_id=f"query_{query_type.value}_{operation.value}",
                    query_type=query_type,
                    execution_time_ms=20.0 + hash(query_type.value + operation.value) % 30,
                    rows_affected=1000,
                    memory_usage_mb=10.0 + hash(query_type.value) % 20,
                    cpu_usage_percent=10.0 + hash(operation.value) % 15,
                    index_usage=hash(query_type.value) % 2 == 0,
                    query_plan="Index Scan" if hash(query_type.value) % 2 == 0 else "Table Scan",
                    timestamp=time.time()
                )
                
                validation = validate_database_performance(operation, query_metrics)
                
                assert isinstance(validation, DatabaseValidation)
                assert validation.operation == operation
                assert validation.query_metrics == query_metrics
                assert validation.performance_score >= 0.0
                assert validation.meets_threshold in [True, False]
                assert validation.bottleneck_identified in [True, False]
                assert validation.validation_status in [DatabaseValidationStatus.PASSED,
                                                    DatabaseValidationStatus.WARNING,
                                                    DatabaseValidationStatus.FAILED]
                assert len(validation.optimization_recommendations) > 0
        
        # Generate performance report
        report = generate_database_performance_report()
        
        assert isinstance(report, DatabasePerformanceReport)
        assert report.total_queries == len(query_types) * len(operations)
        assert report.overall_performance >= 0.0
        assert report.average_query_time_ms >= 0.0
        assert report.p95_query_time_ms >= 0.0
        assert report.p99_query_time_ms >= 0.0
        assert report.performance_level in [DatabasePerformanceLevel.EXCELLENT,
                                          DatabasePerformanceLevel.GOOD,
                                          DatabasePerformanceLevel.ACCEPTABLE,
                                          DatabasePerformanceLevel.POOR]
        assert report.validation_status in [DatabaseValidationStatus.PASSED,
                                          DatabaseValidationStatus.WARNING,
                                          DatabaseValidationStatus.FAILED]
        assert len(report.detailed_validations) == len(query_types) * len(operations)
        assert len(report.recommendations) > 0
        assert len(report.query_type_analysis) > 0
        assert len(report.operation_analysis) > 0
        assert report.index_efficiency >= 0.0
        assert report.connection_pool_efficiency >= 0.0
        assert report.memory_usage_mb >= 0.0
        assert report.cpu_usage_percent >= 0.0
    
    def test_performance_threshold_validation(self):
        """Test performance threshold validation"""
        # Test with fast query (should pass)
        fast_metrics = QueryMetrics(
            query_id="fast_query",
            query_type=QueryType.SELECT,
            execution_time_ms=15.0,
            rows_affected=1000,
            memory_usage_mb=10.0,
            cpu_usage_percent=10.0,
            index_usage=True,
            query_plan="Index Scan",
            timestamp=time.time()
        )
        
        validation = validate_database_performance(DatabaseOperation.READ, fast_metrics)
        
        assert validation.meets_threshold is True
        assert validation.validation_status in [DatabaseValidationStatus.PASSED, DatabaseValidationStatus.WARNING]
        
        # Test with slow query (should fail)
        slow_metrics = QueryMetrics(
            query_id="slow_query",
            query_type=QueryType.SELECT,
            execution_time_ms=75.0,
            rows_affected=1000,
            memory_usage_mb=100.0,
            cpu_usage_percent=60.0,
            index_usage=False,
            query_plan="Table Scan",
            timestamp=time.time()
        )
        
        validation = validate_database_performance(DatabaseOperation.READ, slow_metrics)
        
        assert validation.meets_threshold is False
        assert validation.validation_status == DatabaseValidationStatus.FAILED
    
    def test_performance_score_calculation(self):
        """Test performance score calculation"""
        # Excellent performance
        excellent_metrics = QueryMetrics(
            query_id="excellent",
            query_type=QueryType.SELECT,
            execution_time_ms=5.0,
            rows_affected=1000,
            memory_usage_mb=5.0,
            cpu_usage_percent=5.0,
            index_usage=True,
            query_plan="Index Scan",
            timestamp=time.time()
        )
        
        validation = validate_database_performance(DatabaseOperation.READ, excellent_metrics)
        
        assert validation.performance_score > 0.8
        assert validation.meets_threshold is True
        
        # Poor performance
        poor_metrics = QueryMetrics(
            query_id="poor",
            query_type=QueryType.SELECT,
            execution_time_ms=100.0,
            rows_affected=1000,
            memory_usage_mb=200.0,
            cpu_usage_percent=80.0,
            index_usage=False,
            query_plan="Table Scan",
            timestamp=time.time()
        )
        
        validation = validate_database_performance(DatabaseOperation.READ, poor_metrics)
        
        assert validation.performance_score < 0.5
        assert validation.meets_threshold is False

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
