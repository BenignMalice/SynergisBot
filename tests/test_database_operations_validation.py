"""
Comprehensive tests for database operations validation system

Tests database operations validation for all trade operations, data integrity
validation, transaction consistency validation, performance validation, error
handling validation, and comprehensive reporting.
"""

import pytest
import time
import math
import statistics
import numpy as np
import threading
import json
import asyncio
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Tuple, Optional
from collections import deque

from infra.database_operations_validation import (
    DatabaseOperationsValidator, DatabaseOperation, DataIntegrityCheck,
    DatabaseValidation, DatabaseOperationsReport,
    DatabaseOperationType, DatabaseValidationStatus, DataIntegrityLevel,
    TransactionConsistency, get_database_operations_validator,
    validate_database_operation, run_data_integrity_check,
    generate_database_operations_report
)

class TestDatabaseOperationType:
    """Test database operation type enumeration"""
    
    def test_database_operation_types(self):
        """Test all database operation types"""
        types = [
            DatabaseOperationType.TRADE_CREATE,
            DatabaseOperationType.TRADE_UPDATE,
            DatabaseOperationType.TRADE_CLOSE,
            DatabaseOperationType.POSITION_OPEN,
            DatabaseOperationType.POSITION_UPDATE,
            DatabaseOperationType.POSITION_CLOSE,
            DatabaseOperationType.ORDER_PLACE,
            DatabaseOperationType.ORDER_UPDATE,
            DatabaseOperationType.ORDER_CANCEL,
            DatabaseOperationType.ORDER_FILL,
            DatabaseOperationType.DATA_INSERT,
            DatabaseOperationType.DATA_UPDATE,
            DatabaseOperationType.DATA_DELETE,
            DatabaseOperationType.DATA_QUERY
        ]
        
        for op_type in types:
            assert isinstance(op_type, DatabaseOperationType)
            assert op_type.value in ["trade_create", "trade_update", "trade_close",
                                    "position_open", "position_update", "position_close",
                                    "order_place", "order_update", "order_cancel",
                                    "order_fill", "data_insert", "data_update",
                                    "data_delete", "data_query"]

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

class TestDataIntegrityLevel:
    """Test data integrity level enumeration"""
    
    def test_data_integrity_levels(self):
        """Test all data integrity levels"""
        levels = [
            DataIntegrityLevel.EXCELLENT,
            DataIntegrityLevel.GOOD,
            DataIntegrityLevel.FAIR,
            DataIntegrityLevel.POOR,
            DataIntegrityLevel.CRITICAL
        ]
        
        for level in levels:
            assert isinstance(level, DataIntegrityLevel)
            assert level.value in ["excellent", "good", "fair", "poor", "critical"]

class TestTransactionConsistency:
    """Test transaction consistency enumeration"""
    
    def test_transaction_consistency_levels(self):
        """Test all transaction consistency levels"""
        levels = [
            TransactionConsistency.CONSISTENT,
            TransactionConsistency.MOSTLY_CONSISTENT,
            TransactionConsistency.INCONSISTENT,
            TransactionConsistency.CRITICAL
        ]
        
        for level in levels:
            assert isinstance(level, TransactionConsistency)
            assert level.value in ["consistent", "mostly_consistent", "inconsistent", "critical"]

class TestDatabaseOperation:
    """Test database operation data structure"""
    
    def test_database_operation_creation(self):
        """Test database operation creation"""
        operation = DatabaseOperation(
            operation_id="op_001",
            operation_type=DatabaseOperationType.TRADE_CREATE,
            timestamp=time.time(),
            symbol="BTCUSDT",
            table_name="trades",
            operation_data={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "volume": 0.1,
                "price": 50000.0
            },
            execution_time_ms=25.5,
            success=True,
            error_message=None,
            transaction_id="tx_001",
            metadata={"source": "mt5"}
        )
        
        assert operation.operation_id == "op_001"
        assert operation.operation_type == DatabaseOperationType.TRADE_CREATE
        assert operation.timestamp > 0
        assert operation.symbol == "BTCUSDT"
        assert operation.table_name == "trades"
        assert operation.operation_data["symbol"] == "BTCUSDT"
        assert operation.execution_time_ms == 25.5
        assert operation.success is True
        assert operation.error_message is None
        assert operation.transaction_id == "tx_001"
        assert operation.metadata["source"] == "mt5"
    
    def test_database_operation_defaults(self):
        """Test database operation defaults"""
        operation = DatabaseOperation(
            operation_id="op_002",
            operation_type=DatabaseOperationType.TRADE_UPDATE,
            timestamp=time.time(),
            symbol="ETHUSDT",
            table_name="trades",
            operation_data={"trade_id": "123", "price": 3000.0},
            execution_time_ms=15.0,
            success=False,
            error_message="Database error"
        )
        
        assert operation.transaction_id is None
        assert operation.metadata == {}

class TestDataIntegrityCheck:
    """Test data integrity check data structure"""
    
    def test_data_integrity_check_creation(self):
        """Test data integrity check creation"""
        check = DataIntegrityCheck(
            check_id="check_001",
            table_name="trades",
            check_type="comprehensive",
            timestamp=time.time(),
            integrity_score=0.85,
            issues_found=["Minor inconsistencies"],
            recommendations=["Review data validation"],
            metadata={"check_duration_ms": 150}
        )
        
        assert check.check_id == "check_001"
        assert check.table_name == "trades"
        assert check.check_type == "comprehensive"
        assert check.timestamp > 0
        assert check.integrity_score == 0.85
        assert len(check.issues_found) == 1
        assert len(check.recommendations) == 1
        assert check.metadata["check_duration_ms"] == 150
    
    def test_data_integrity_check_defaults(self):
        """Test data integrity check defaults"""
        check = DataIntegrityCheck(
            check_id="check_002",
            table_name="positions",
            check_type="basic",
            timestamp=time.time(),
            integrity_score=0.90,
            issues_found=[],
            recommendations=[]
        )
        
        assert check.metadata == {}

class TestDatabaseValidation:
    """Test database validation data structure"""
    
    def test_database_validation_creation(self):
        """Test database validation creation"""
        validation = DatabaseValidation(
            timestamp=time.time(),
            operation_id="op_001",
            operation_type=DatabaseOperationType.TRADE_CREATE,
            validation_status=DatabaseValidationStatus.PASSED,
            data_integrity_score=0.85,
            transaction_consistency=TransactionConsistency.CONSISTENT,
            performance_score=0.90,
            error_handling_score=0.95,
            overall_score=0.88,
            issues_found=[],
            recommendations=["Operation performed well"],
            metadata={"db_path": "data/bot.sqlite"}
        )
        
        assert validation.timestamp > 0
        assert validation.operation_id == "op_001"
        assert validation.operation_type == DatabaseOperationType.TRADE_CREATE
        assert validation.validation_status == DatabaseValidationStatus.PASSED
        assert validation.data_integrity_score == 0.85
        assert validation.transaction_consistency == TransactionConsistency.CONSISTENT
        assert validation.performance_score == 0.90
        assert validation.error_handling_score == 0.95
        assert validation.overall_score == 0.88
        assert len(validation.issues_found) == 0
        assert len(validation.recommendations) == 1
        assert validation.metadata["db_path"] == "data/bot.sqlite"
    
    def test_database_validation_defaults(self):
        """Test database validation defaults"""
        validation = DatabaseValidation(
            timestamp=time.time(),
            operation_id="op_002",
            operation_type=DatabaseOperationType.TRADE_UPDATE,
            validation_status=DatabaseValidationStatus.WARNING,
            data_integrity_score=0.70,
            transaction_consistency=TransactionConsistency.MOSTLY_CONSISTENT,
            performance_score=0.75,
            error_handling_score=0.80,
            overall_score=0.73,
            issues_found=["Minor issues"],
            recommendations=["Review implementation"]
        )
        
        assert validation.metadata == {}

class TestDatabaseOperationsReport:
    """Test database operations report data structure"""
    
    def test_database_operations_report_creation(self):
        """Test database operations report creation"""
        report = DatabaseOperationsReport(
            timestamp=time.time(),
            overall_validation_score=0.85,
            total_operations=100,
            successful_operations=85,
            failed_operations=15,
            data_integrity_level=DataIntegrityLevel.GOOD,
            transaction_consistency=TransactionConsistency.MOSTLY_CONSISTENT,
            average_performance_ms=45.5,
            error_rate=0.15,
            operation_type_analysis={"trade_create_score": 0.88},
            data_integrity_analysis={"average_integrity_score": 0.85},
            performance_analysis={"average_execution_time_ms": 45.5},
            error_analysis={"average_error_handling_score": 0.80},
            recommendations=["Database operations need improvement"],
            detailed_validations=[],
            metadata={"db_path": "data/bot.sqlite"}
        )
        
        assert report.timestamp > 0
        assert report.overall_validation_score == 0.85
        assert report.total_operations == 100
        assert report.successful_operations == 85
        assert report.failed_operations == 15
        assert report.data_integrity_level == DataIntegrityLevel.GOOD
        assert report.transaction_consistency == TransactionConsistency.MOSTLY_CONSISTENT
        assert report.average_performance_ms == 45.5
        assert report.error_rate == 0.15
        assert report.operation_type_analysis["trade_create_score"] == 0.88
        assert report.data_integrity_analysis["average_integrity_score"] == 0.85
        assert report.performance_analysis["average_execution_time_ms"] == 45.5
        assert report.error_analysis["average_error_handling_score"] == 0.80
        assert len(report.recommendations) == 1
        assert report.detailed_validations == []
        assert report.metadata["db_path"] == "data/bot.sqlite"
    
    def test_database_operations_report_defaults(self):
        """Test database operations report defaults"""
        report = DatabaseOperationsReport(
            timestamp=time.time(),
            overall_validation_score=0.70,
            total_operations=50,
            successful_operations=35,
            failed_operations=15,
            data_integrity_level=DataIntegrityLevel.FAIR,
            transaction_consistency=TransactionConsistency.INCONSISTENT,
            average_performance_ms=75.0,
            error_rate=0.30,
            operation_type_analysis={"trade_update_score": 0.70},
            data_integrity_analysis={"average_integrity_score": 0.70},
            performance_analysis={"average_execution_time_ms": 75.0},
            error_analysis={"average_error_handling_score": 0.65},
            recommendations=["Database operations need improvement"],
            detailed_validations=[]
        )
        
        assert report.metadata == {}

class TestDatabaseOperationsValidator:
    """Test database operations validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = DatabaseOperationsValidator(db_path="test.db")
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert self.validator.db_path == "test.db"
        assert len(self.validator.validations) == 0
        assert len(self.validator.operations) == 0
        assert len(self.validator.integrity_checks) == 0
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
    
    def test_validate_database_operation_success(self):
        """Test successful database operation validation"""
        operation = DatabaseOperation(
            operation_id="op_001",
            operation_type=DatabaseOperationType.TRADE_CREATE,
            timestamp=time.time(),
            symbol="BTCUSDT",
            table_name="trades",
            operation_data={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "volume": 0.1,
                "price": 50000.0
            },
            execution_time_ms=25.5,
            success=True,
            transaction_id="tx_001"
        )
        
        validation = self.validator.validate_database_operation(operation)
        
        assert validation.operation_id == "op_001"
        assert validation.operation_type == DatabaseOperationType.TRADE_CREATE
        assert validation.validation_status in [DatabaseValidationStatus.PASSED,
                                              DatabaseValidationStatus.WARNING,
                                              DatabaseValidationStatus.FAILED]
        assert 0.0 <= validation.data_integrity_score <= 1.0
        assert validation.transaction_consistency in [TransactionConsistency.CONSISTENT,
                                                    TransactionConsistency.MOSTLY_CONSISTENT,
                                                    TransactionConsistency.INCONSISTENT,
                                                    TransactionConsistency.CRITICAL]
        assert 0.0 <= validation.performance_score <= 1.0
        assert 0.0 <= validation.error_handling_score <= 1.0
        assert 0.0 <= validation.overall_score <= 1.0
        assert len(validation.issues_found) >= 0
        assert len(validation.recommendations) > 0
        assert validation.metadata["db_path"] == "test.db"
    
    def test_validate_database_operation_failure(self):
        """Test failed database operation validation"""
        operation = DatabaseOperation(
            operation_id="op_002",
            operation_type=DatabaseOperationType.TRADE_UPDATE,
            timestamp=time.time(),
            symbol="ETHUSDT",
            table_name="trades",
            operation_data={"trade_id": "123"},
            execution_time_ms=150.0,
            success=False,
            error_message="Database connection failed"
        )
        
        validation = self.validator.validate_database_operation(operation)
        
        assert validation.operation_id == "op_002"
        assert validation.operation_type == DatabaseOperationType.TRADE_UPDATE
        assert validation.validation_status in [DatabaseValidationStatus.WARNING,
                                              DatabaseValidationStatus.FAILED]
        assert 0.0 <= validation.data_integrity_score <= 1.0
        assert validation.transaction_consistency in [TransactionConsistency.INCONSISTENT,
                                                    TransactionConsistency.CRITICAL]
        assert 0.0 <= validation.performance_score <= 1.0
        assert 0.0 <= validation.error_handling_score <= 1.0
        assert 0.0 <= validation.overall_score <= 1.0
        assert len(validation.issues_found) > 0
        assert len(validation.recommendations) > 0
    
    def test_validate_database_operation_slow_performance(self):
        """Test slow performance database operation validation"""
        operation = DatabaseOperation(
            operation_id="op_003",
            operation_type=DatabaseOperationType.DATA_QUERY,
            timestamp=time.time(),
            symbol="ADAUSDT",
            table_name="trades",
            operation_data={"query": "SELECT * FROM trades"},
            execution_time_ms=1200.0,  # Very slow
            success=True,
            transaction_id="tx_003"
        )
        
        validation = self.validator.validate_database_operation(operation)
        
        assert validation.operation_id == "op_003"
        assert validation.operation_type == DatabaseOperationType.DATA_QUERY
        assert validation.validation_status in [DatabaseValidationStatus.WARNING,
                                              DatabaseValidationStatus.FAILED]
        assert 0.0 <= validation.performance_score <= 1.0
        assert any("Performance issues" in issue or "Very slow operation" in issue for issue in validation.issues_found)
        assert len(validation.recommendations) > 0
    
    def test_run_data_integrity_check(self):
        """Test data integrity check"""
        check = self.validator.run_data_integrity_check("trades")
        
        assert check.check_id.startswith("integrity_trades_")
        assert check.table_name == "trades"
        assert check.check_type == "comprehensive"
        assert check.timestamp > 0
        assert 0.0 <= check.integrity_score <= 1.0
        assert isinstance(check.issues_found, list)
        assert isinstance(check.recommendations, list)
        assert "check_duration_ms" in check.metadata
        
        # Check that integrity check was added to validator
        assert len(self.validator.integrity_checks) == 1
        assert self.validator.integrity_checks[0] == check
    
    def test_generate_validation_report(self):
        """Test validation report generation"""
        # Add some validations first
        for i in range(5):
            operation = DatabaseOperation(
                operation_id=f"op_{i:03d}",
                operation_type=DatabaseOperationType.TRADE_CREATE,
                timestamp=time.time() + i,
                symbol=f"SYMBOL{i}",
                table_name="trades",
                operation_data={
                    "symbol": f"SYMBOL{i}",
                    "side": "BUY",
                    "volume": 0.1 + i * 0.05,
                    "price": 50000.0 + i * 1000.0
                },
                execution_time_ms=25.0 + i * 10.0,
                success=i % 4 != 0,  # Some failures
                transaction_id=f"tx_{i:03d}" if i % 2 == 0 else None
            )
            
            self.validator.validate_database_operation(operation)
        
        report = self.validator.generate_validation_report()
        
        assert report.total_operations == 5
        assert report.successful_operations >= 0
        assert report.failed_operations >= 0
        assert report.successful_operations + report.failed_operations == 5
        assert report.overall_validation_score >= 0.0
        assert report.data_integrity_level in [DataIntegrityLevel.EXCELLENT,
                                             DataIntegrityLevel.GOOD,
                                             DataIntegrityLevel.FAIR,
                                             DataIntegrityLevel.POOR,
                                             DataIntegrityLevel.CRITICAL]
        assert report.transaction_consistency in [TransactionConsistency.CONSISTENT,
                                                TransactionConsistency.MOSTLY_CONSISTENT,
                                                TransactionConsistency.INCONSISTENT,
                                                TransactionConsistency.CRITICAL]
        assert report.average_performance_ms >= 0.0
        assert 0.0 <= report.error_rate <= 1.0
        assert len(report.detailed_validations) == 5
        assert len(report.recommendations) > 0
        assert len(report.operation_type_analysis) > 0
        assert len(report.data_integrity_analysis) > 0
        assert len(report.performance_analysis) > 0
        assert len(report.error_analysis) > 0
        assert report.metadata["db_path"] == "test.db"
    
    def test_generate_validation_report_no_data(self):
        """Test validation report generation with no data"""
        report = self.validator.generate_validation_report()
        
        assert report.overall_validation_score == 0.0
        assert report.total_operations == 0
        assert report.successful_operations == 0
        assert report.failed_operations == 0
        assert report.data_integrity_level == DataIntegrityLevel.CRITICAL
        assert report.transaction_consistency == TransactionConsistency.CRITICAL
        assert report.average_performance_ms == 0.0
        assert report.error_rate == 1.0
        assert report.operation_type_analysis == {}
        assert report.data_integrity_analysis == {}
        assert report.performance_analysis == {}
        assert report.error_analysis == {}
        assert "No validation data available" in report.recommendations[0]
        assert report.detailed_validations == []
        assert report.metadata["error"] == "No validation data available"

class TestGlobalFunctions:
    """Test global database operations validation functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.database_operations_validation
        infra.database_operations_validation._database_operations_validator = None
    
    def test_get_database_operations_validator(self):
        """Test global validator access"""
        validator1 = get_database_operations_validator()
        validator2 = get_database_operations_validator()
        
        # Should return same instance
        assert validator1 is validator2
        assert isinstance(validator1, DatabaseOperationsValidator)
    
    def test_validate_database_operation_global(self):
        """Test global database operation validation"""
        operation = DatabaseOperation(
            operation_id="op_001",
            operation_type=DatabaseOperationType.TRADE_CREATE,
            timestamp=time.time(),
            symbol="BTCUSDT",
            table_name="trades",
            operation_data={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "volume": 0.1,
                "price": 50000.0
            },
            execution_time_ms=25.5,
            success=True,
            transaction_id="tx_001"
        )
        
        validation = validate_database_operation(operation)
        
        assert isinstance(validation, DatabaseValidation)
        assert validation.operation_id == "op_001"
        assert validation.operation_type == DatabaseOperationType.TRADE_CREATE
        assert validation.validation_status in [DatabaseValidationStatus.PASSED,
                                              DatabaseValidationStatus.WARNING,
                                              DatabaseValidationStatus.FAILED]
        assert 0.0 <= validation.data_integrity_score <= 1.0
        assert validation.transaction_consistency in [TransactionConsistency.CONSISTENT,
                                                    TransactionConsistency.MOSTLY_CONSISTENT,
                                                    TransactionConsistency.INCONSISTENT,
                                                    TransactionConsistency.CRITICAL]
        assert 0.0 <= validation.performance_score <= 1.0
        assert 0.0 <= validation.error_handling_score <= 1.0
        assert 0.0 <= validation.overall_score <= 1.0
        assert len(validation.issues_found) >= 0
        assert len(validation.recommendations) > 0
    
    def test_run_data_integrity_check_global(self):
        """Test global data integrity check"""
        check = run_data_integrity_check("trades")
        
        assert isinstance(check, DataIntegrityCheck)
        assert check.table_name == "trades"
        assert check.check_type == "comprehensive"
        assert check.timestamp > 0
        assert 0.0 <= check.integrity_score <= 1.0
        assert isinstance(check.issues_found, list)
        assert isinstance(check.recommendations, list)
        assert "check_duration_ms" in check.metadata
    
    def test_generate_database_operations_report_global(self):
        """Test global database operations report generation"""
        # Add some validations first
        for i in range(3):
            operation = DatabaseOperation(
                operation_id=f"op_{i:03d}",
                operation_type=DatabaseOperationType.TRADE_CREATE,
                timestamp=time.time() + i,
                symbol=f"SYMBOL{i}",
                table_name="trades",
                operation_data={
                    "symbol": f"SYMBOL{i}",
                    "side": "BUY",
                    "volume": 0.1 + i * 0.05,
                    "price": 50000.0 + i * 1000.0
                },
                execution_time_ms=25.0 + i * 10.0,
                success=i % 2 == 0,
                transaction_id=f"tx_{i:03d}" if i % 2 == 0 else None
            )
            
            validate_database_operation(operation)
        
        report = generate_database_operations_report()
        
        assert isinstance(report, DatabaseOperationsReport)
        assert report.total_operations == 3

class TestDatabaseOperationsValidationIntegration:
    """Integration tests for database operations validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.database_operations_validation
        infra.database_operations_validation._database_operations_validator = None
    
    def test_comprehensive_database_operations_validation(self):
        """Test comprehensive database operations validation workflow"""
        # Test different operation types and scenarios
        test_cases = [
            (DatabaseOperationType.TRADE_CREATE, True, 25.0, "tx_001"),
            (DatabaseOperationType.TRADE_UPDATE, True, 15.0, "tx_002"),
            (DatabaseOperationType.TRADE_CLOSE, False, 100.0, None),
            (DatabaseOperationType.POSITION_OPEN, True, 30.0, "tx_003"),
            (DatabaseOperationType.ORDER_PLACE, True, 20.0, "tx_004"),
            (DatabaseOperationType.ORDER_CANCEL, False, 200.0, None),
            (DatabaseOperationType.DATA_INSERT, True, 10.0, "tx_005"),
            (DatabaseOperationType.DATA_QUERY, True, 50.0, "tx_006")
        ]
        
        for operation_type, success, execution_time, transaction_id in test_cases:
            operation = DatabaseOperation(
                operation_id=f"op_{operation_type.value}",
                operation_type=operation_type,
                timestamp=time.time(),
                symbol="BTCUSDT",
                table_name="trades",
                operation_data={
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "volume": 0.1,
                    "price": 50000.0
                },
                execution_time_ms=execution_time,
                success=success,
                error_message="Database error" if not success else None,
                transaction_id=transaction_id
            )
            
            validation = validate_database_operation(operation)
            
            assert isinstance(validation, DatabaseValidation)
            assert validation.operation_id == f"op_{operation_type.value}"
            assert validation.operation_type == operation_type
            assert validation.validation_status in [DatabaseValidationStatus.PASSED,
                                                  DatabaseValidationStatus.WARNING,
                                                  DatabaseValidationStatus.FAILED]
            assert 0.0 <= validation.data_integrity_score <= 1.0
            assert validation.transaction_consistency in [TransactionConsistency.CONSISTENT,
                                                        TransactionConsistency.MOSTLY_CONSISTENT,
                                                        TransactionConsistency.INCONSISTENT,
                                                        TransactionConsistency.CRITICAL]
            assert 0.0 <= validation.performance_score <= 1.0
            assert 0.0 <= validation.error_handling_score <= 1.0
            assert 0.0 <= validation.overall_score <= 1.0
            assert len(validation.issues_found) >= 0
            assert len(validation.recommendations) > 0
        
        # Generate validation report
        report = generate_database_operations_report()
        
        assert isinstance(report, DatabaseOperationsReport)
        assert report.total_operations == len(test_cases)
        assert report.overall_validation_score >= 0.0
        assert report.data_integrity_level in [DataIntegrityLevel.EXCELLENT,
                                             DataIntegrityLevel.GOOD,
                                             DataIntegrityLevel.FAIR,
                                             DataIntegrityLevel.POOR,
                                             DataIntegrityLevel.CRITICAL]
        assert report.transaction_consistency in [TransactionConsistency.CONSISTENT,
                                                TransactionConsistency.MOSTLY_CONSISTENT,
                                                TransactionConsistency.INCONSISTENT,
                                                TransactionConsistency.CRITICAL]
        assert report.average_performance_ms >= 0.0
        assert 0.0 <= report.error_rate <= 1.0
        assert len(report.detailed_validations) == len(test_cases)
        assert len(report.recommendations) > 0
        assert len(report.operation_type_analysis) > 0
        assert len(report.data_integrity_analysis) > 0
        assert len(report.performance_analysis) > 0
        assert len(report.error_analysis) > 0
    
    def test_data_integrity_validation(self):
        """Test data integrity validation"""
        # Test with good data integrity
        good_operation = DatabaseOperation(
            operation_id="good_op",
            operation_type=DatabaseOperationType.TRADE_CREATE,
            timestamp=time.time(),
            symbol="BTCUSDT",
            table_name="trades",
            operation_data={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "volume": 0.1,
                "price": 50000.0
            },
            execution_time_ms=25.0,
            success=True,
            transaction_id="tx_good"
        )
        
        validation = validate_database_operation(good_operation)
        
        assert validation.data_integrity_score >= 0.0
        assert validation.transaction_consistency in [TransactionConsistency.CONSISTENT,
                                                    TransactionConsistency.MOSTLY_CONSISTENT]
        
        # Test with poor data integrity
        poor_operation = DatabaseOperation(
            operation_id="poor_op",
            operation_type=DatabaseOperationType.TRADE_CREATE,
            timestamp=time.time(),
            symbol="BTCUSDT",
            table_name="trades",
            operation_data={
                "symbol": "BTCUSDT",
                "side": "BUY",
                "volume": -0.1,  # Invalid volume
                "price": -50000.0  # Invalid price
            },
            execution_time_ms=200.0,
            success=False,
            error_message="Invalid data"
        )
        
        validation = validate_database_operation(poor_operation)
        
        assert validation.data_integrity_score < 0.8
        assert validation.transaction_consistency in [TransactionConsistency.INCONSISTENT,
                                                    TransactionConsistency.CRITICAL]
    
    def test_performance_validation(self):
        """Test performance validation"""
        # Test fast operation
        fast_operation = DatabaseOperation(
            operation_id="fast_op",
            operation_type=DatabaseOperationType.DATA_QUERY,
            timestamp=time.time(),
            symbol="BTCUSDT",
            table_name="trades",
            operation_data={"query": "SELECT * FROM trades LIMIT 10"},
            execution_time_ms=5.0,  # Very fast
            success=True,
            transaction_id="tx_fast"
        )
        
        validation = validate_database_operation(fast_operation)
        
        assert validation.performance_score >= 0.9
        
        # Test slow operation
        slow_operation = DatabaseOperation(
            operation_id="slow_op",
            operation_type=DatabaseOperationType.DATA_QUERY,
            timestamp=time.time(),
            symbol="BTCUSDT",
            table_name="trades",
            operation_data={"query": "SELECT * FROM trades"},
            execution_time_ms=1500.0,  # Very slow
            success=True,
            transaction_id="tx_slow"
        )
        
        validation = validate_database_operation(slow_operation)
        
        assert validation.performance_score < 0.5
        assert any("Performance issues" in issue or "Very slow operation" in issue for issue in validation.issues_found)
    
    def test_error_handling_validation(self):
        """Test error handling validation"""
        # Test with good error handling
        good_error_operation = DatabaseOperation(
            operation_id="good_error_op",
            operation_type=DatabaseOperationType.TRADE_CREATE,
            timestamp=time.time(),
            symbol="BTCUSDT",
            table_name="trades",
            operation_data={"symbol": "BTCUSDT"},
            execution_time_ms=25.0,
            success=False,
            error_message="Detailed error message with specific information about the failure"
        )
        
        validation = validate_database_operation(good_error_operation)
        
        assert validation.error_handling_score >= 0.7
        
        # Test with poor error handling
        poor_error_operation = DatabaseOperation(
            operation_id="poor_error_op",
            operation_type=DatabaseOperationType.TRADE_CREATE,
            timestamp=time.time(),
            symbol="BTCUSDT",
            table_name="trades",
            operation_data={"symbol": "BTCUSDT"},
            execution_time_ms=25.0,
            success=False,
            error_message="Error"  # Very brief error message
        )
        
        validation = validate_database_operation(poor_error_operation)
        
        assert validation.error_handling_score < 0.7

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
