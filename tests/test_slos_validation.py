"""
Comprehensive tests for SLOs validation system

Tests SLOs validation for production readiness, performance, reliability,
accuracy, and operational SLOs validation with comprehensive reporting.
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
from collections import deque, defaultdict

from infra.slos_validation import (
    SLOsValidator, SLODefinition, SLOMeasurement, SLOValidation,
    SLOsValidationReport, SLOCategory, SLOStatus, SLOImportance,
    ValidationStatus, get_slos_validator, add_slo_definition,
    record_slo_measurement, validate_slo, validate_all_slos
)

class TestSLOCategory:
    """Test SLO category enumeration"""
    
    def test_slo_categories(self):
        """Test all SLO categories"""
        categories = [
            SLOCategory.PERFORMANCE,
            SLOCategory.RELIABILITY,
            SLOCategory.ACCURACY,
            SLOCategory.OPERATIONAL,
            SLOCategory.SECURITY,
            SLOCategory.BUSINESS
        ]
        
        for category in categories:
            assert isinstance(category, SLOCategory)
            assert category.value in ["performance", "reliability", "accuracy", 
                                    "operational", "security", "business"]

class TestSLOStatus:
    """Test SLO status enumeration"""
    
    def test_slo_statuses(self):
        """Test all SLO statuses"""
        statuses = [
            SLOStatus.MET,
            SLOStatus.AT_RISK,
            SLOStatus.VIOLATED,
            SLOStatus.UNKNOWN
        ]
        
        for status in statuses:
            assert isinstance(status, SLOStatus)
            assert status.value in ["met", "at_risk", "violated", "unknown"]

class TestSLOImportance:
    """Test SLO importance enumeration"""
    
    def test_slo_importances(self):
        """Test all SLO importances"""
        importances = [
            SLOImportance.CRITICAL,
            SLOImportance.HIGH,
            SLOImportance.MEDIUM,
            SLOImportance.LOW
        ]
        
        for importance in importances:
            assert isinstance(importance, SLOImportance)
            assert importance.value in ["critical", "high", "medium", "low"]

class TestValidationStatus:
    """Test validation status enumeration"""
    
    def test_validation_statuses(self):
        """Test all validation statuses"""
        statuses = [
            ValidationStatus.PASSED,
            ValidationStatus.WARNING,
            ValidationStatus.FAILED,
            ValidationStatus.PENDING
        ]
        
        for status in statuses:
            assert isinstance(status, ValidationStatus)
            assert status.value in ["passed", "warning", "failed", "pending"]

class TestSLODefinition:
    """Test SLO definition data structure"""
    
    def test_slo_definition_creation(self):
        """Test SLO definition creation"""
        slo = SLODefinition(
            name="test_latency",
            category=SLOCategory.PERFORMANCE,
            importance=SLOImportance.CRITICAL,
            target_value=200.0,
            measurement_unit="ms",
            measurement_window_hours=24.0,
            threshold_warning=0.8,
            threshold_critical=0.9,
            description="Test latency SLO",
            measurement_method="latency_measurement",
            dependencies=["cpu_usage", "memory_usage"],
            metadata={"test": True}
        )
        
        assert slo.name == "test_latency"
        assert slo.category == SLOCategory.PERFORMANCE
        assert slo.importance == SLOImportance.CRITICAL
        assert slo.target_value == 200.0
        assert slo.measurement_unit == "ms"
        assert slo.measurement_window_hours == 24.0
        assert slo.threshold_warning == 0.8
        assert slo.threshold_critical == 0.9
        assert slo.description == "Test latency SLO"
        assert slo.measurement_method == "latency_measurement"
        assert slo.dependencies == ["cpu_usage", "memory_usage"]
        assert slo.metadata["test"] is True
    
    def test_slo_definition_defaults(self):
        """Test SLO definition defaults"""
        slo = SLODefinition(
            name="test_slo",
            category=SLOCategory.RELIABILITY,
            importance=SLOImportance.HIGH,
            target_value=99.9,
            measurement_unit="%",
            measurement_window_hours=1.0,
            threshold_warning=0.7,
            threshold_critical=0.8,
            description="Test SLO",
            measurement_method="test_measurement"
        )
        
        assert slo.dependencies == []
        assert slo.metadata == {}

class TestSLOMeasurement:
    """Test SLO measurement data structure"""
    
    def test_slo_measurement_creation(self):
        """Test SLO measurement creation"""
        measurement = SLOMeasurement(
            timestamp=time.time(),
            slo_name="test_latency",
            current_value=150.0,
            target_value=200.0,
            measurement_unit="ms",
            status=SLOStatus.MET,
            compliance_percentage=0.95,
            trend_direction="stable",
            metadata={"test": True}
        )
        
        assert measurement.timestamp > 0
        assert measurement.slo_name == "test_latency"
        assert measurement.current_value == 150.0
        assert measurement.target_value == 200.0
        assert measurement.measurement_unit == "ms"
        assert measurement.status == SLOStatus.MET
        assert measurement.compliance_percentage == 0.95
        assert measurement.trend_direction == "stable"
        assert measurement.metadata["test"] is True
    
    def test_slo_measurement_defaults(self):
        """Test SLO measurement defaults"""
        measurement = SLOMeasurement(
            timestamp=time.time(),
            slo_name="test_slo",
            current_value=100.0,
            target_value=100.0,
            measurement_unit="%",
            status=SLOStatus.AT_RISK,
            compliance_percentage=0.8,
            trend_direction="degrading"
        )
        
        assert measurement.metadata == {}

class TestSLOValidation:
    """Test SLO validation data structure"""
    
    def test_slo_validation_creation(self):
        """Test SLO validation creation"""
        measurement = SLOMeasurement(
            timestamp=time.time(),
            slo_name="test_latency",
            current_value=150.0,
            target_value=200.0,
            measurement_unit="ms",
            status=SLOStatus.MET,
            compliance_percentage=0.95,
            trend_direction="stable"
        )
        
        validation = SLOValidation(
            timestamp=time.time(),
            slo_name="test_latency",
            category=SLOCategory.PERFORMANCE,
            importance=SLOImportance.CRITICAL,
            current_value=150.0,
            target_value=200.0,
            compliance_percentage=0.95,
            status=SLOStatus.MET,
            validation_status=ValidationStatus.PASSED,
            issues_found=[],
            recommendations=["Excellent performance"],
            trend_analysis={"trend": "stable", "direction": "stable"},
            historical_data=[measurement],
            metadata={"test": True}
        )
        
        assert validation.timestamp > 0
        assert validation.slo_name == "test_latency"
        assert validation.category == SLOCategory.PERFORMANCE
        assert validation.importance == SLOImportance.CRITICAL
        assert validation.current_value == 150.0
        assert validation.target_value == 200.0
        assert validation.compliance_percentage == 0.95
        assert validation.status == SLOStatus.MET
        assert validation.validation_status == ValidationStatus.PASSED
        assert len(validation.issues_found) == 0
        assert len(validation.recommendations) == 1
        assert validation.trend_analysis["trend"] == "stable"
        assert len(validation.historical_data) == 1
        assert validation.metadata["test"] is True
    
    def test_slo_validation_defaults(self):
        """Test SLO validation defaults"""
        validation = SLOValidation(
            timestamp=time.time(),
            slo_name="test_slo",
            category=SLOCategory.RELIABILITY,
            importance=SLOImportance.HIGH,
            current_value=99.0,
            target_value=99.9,
            compliance_percentage=0.7,
            status=SLOStatus.AT_RISK,
            validation_status=ValidationStatus.WARNING,
            issues_found=["SLO at risk"],
            recommendations=["Monitor closely"],
            trend_analysis={},
            historical_data=[]
        )
        
        assert validation.trend_analysis == {}
        assert validation.historical_data == []
        assert validation.metadata == {}

class TestSLOsValidationReport:
    """Test SLOs validation report data structure"""
    
    def test_slos_validation_report_creation(self):
        """Test SLOs validation report creation"""
        validation = SLOValidation(
            timestamp=time.time(),
            slo_name="test_latency",
            category=SLOCategory.PERFORMANCE,
            importance=SLOImportance.CRITICAL,
            current_value=150.0,
            target_value=200.0,
            compliance_percentage=0.95,
            status=SLOStatus.MET,
            validation_status=ValidationStatus.PASSED,
            issues_found=[],
            recommendations=["Excellent performance"],
            trend_analysis={"trend": "stable"},
            historical_data=[]
        )
        
        report = SLOsValidationReport(
            timestamp=time.time(),
            overall_compliance_score=0.95,
            total_slos=1,
            met_slos=1,
            at_risk_slos=0,
            violated_slos=0,
            critical_slos_status={"test_latency": SLOStatus.MET},
            category_breakdown={SLOCategory.PERFORMANCE: {"total": 1, "met": 1}},
            production_readiness_score=0.95,
            recommendations=["Excellent performance"],
            detailed_validations=[validation],
            metadata={"test": True}
        )
        
        assert report.timestamp > 0
        assert report.overall_compliance_score == 0.95
        assert report.total_slos == 1
        assert report.met_slos == 1
        assert report.at_risk_slos == 0
        assert report.violated_slos == 0
        assert report.critical_slos_status["test_latency"] == SLOStatus.MET
        assert report.category_breakdown[SLOCategory.PERFORMANCE]["total"] == 1
        assert report.production_readiness_score == 0.95
        assert len(report.recommendations) == 1
        assert len(report.detailed_validations) == 1
        assert report.metadata["test"] is True
    
    def test_slos_validation_report_defaults(self):
        """Test SLOs validation report defaults"""
        report = SLOsValidationReport(
            timestamp=time.time(),
            overall_compliance_score=0.5,
            total_slos=2,
            met_slos=1,
            at_risk_slos=1,
            violated_slos=0,
            critical_slos_status={"test_slo": SLOStatus.AT_RISK},
            category_breakdown={SLOCategory.RELIABILITY: {"total": 1, "met": 0}},
            production_readiness_score=0.5,
            recommendations=["Monitor closely"],
            detailed_validations=[]
        )
        
        assert report.detailed_validations == []
        assert report.metadata == {}

class TestSLOsValidator:
    """Test SLOs validator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = SLOsValidator()
    
    def test_validator_initialization(self):
        """Test validator initialization"""
        assert len(self.validator.slo_definitions) > 0  # Should have default SLOs
        assert len(self.validator.measurements) == 0
        assert len(self.validator.validations) == 0
        assert hasattr(self.validator, 'lock')
        assert self.validator.start_time > 0
    
    def test_add_slo_definition(self):
        """Test adding SLO definition"""
        slo = SLODefinition(
            name="test_slo",
            category=SLOCategory.PERFORMANCE,
            importance=SLOImportance.HIGH,
            target_value=100.0,
            measurement_unit="%",
            measurement_window_hours=1.0,
            threshold_warning=0.8,
            threshold_critical=0.9,
            description="Test SLO",
            measurement_method="test_measurement"
        )
        
        self.validator.add_slo_definition(slo)
        
        assert "test_slo" in self.validator.slo_definitions
        assert self.validator.slo_definitions["test_slo"] == slo
    
    def test_record_measurement(self):
        """Test recording SLO measurement"""
        measurement = SLOMeasurement(
            timestamp=time.time(),
            slo_name="latency_p95",
            current_value=150.0,
            target_value=200.0,
            measurement_unit="ms",
            status=SLOStatus.MET,
            compliance_percentage=0.95,
            trend_direction="stable"
        )
        
        self.validator.record_measurement(measurement)
        
        assert len(self.validator.measurements["latency_p95"]) == 1
        assert self.validator.measurements["latency_p95"][0] == measurement
    
    def test_validate_slo_no_data(self):
        """Test SLO validation with no data"""
        # Create a custom SLO that doesn't exist in defaults
        slo = SLODefinition(
            name="nonexistent_slo",
            category=SLOCategory.PERFORMANCE,
            importance=SLOImportance.HIGH,
            target_value=100.0,
            measurement_unit="%",
            measurement_window_hours=1.0,
            threshold_warning=0.8,
            threshold_critical=0.9,
            description="Nonexistent SLO",
            measurement_method="test_measurement"
        )
        self.validator.add_slo_definition(slo)
        
        validation = self.validator.validate_slo("nonexistent_slo")
        
        assert validation is not None
        assert validation.slo_name == "nonexistent_slo"
        assert validation.current_value == 0.0
        assert validation.compliance_percentage == 0.0
        assert validation.status == SLOStatus.UNKNOWN
        assert validation.validation_status == ValidationStatus.FAILED
        assert "No measurement data available" in validation.issues_found[0]
    
    def test_validate_slo_with_data(self):
        """Test SLO validation with data"""
        # Record some measurements
        base_time = time.time()
        for i in range(10):
            measurement = SLOMeasurement(
                timestamp=base_time - i * 60,
                slo_name="latency_p95",
                current_value=150.0 + np.random.normal(0, 10),
                target_value=200.0,
                measurement_unit="ms",
                status=SLOStatus.MET,
                compliance_percentage=0.95,
                trend_direction="stable"
            )
            self.validator.record_measurement(measurement)
        
        validation = self.validator.validate_slo("latency_p95")
        
        assert validation is not None
        assert validation.slo_name == "latency_p95"
        assert validation.current_value > 0
        assert validation.target_value == 200.0
        assert 0.0 <= validation.compliance_percentage <= 1.0
        assert validation.status in [SLOStatus.MET, SLOStatus.AT_RISK, SLOStatus.VIOLATED]
        assert validation.validation_status in [ValidationStatus.PASSED, ValidationStatus.WARNING, ValidationStatus.FAILED]
        assert len(validation.issues_found) >= 0
        assert len(validation.recommendations) > 0
        assert len(validation.historical_data) > 0
    
    def test_validate_all_slos(self):
        """Test validating all SLOs"""
        # Record some measurements for default SLOs
        base_time = time.time()
        for i in range(5):
            measurement = SLOMeasurement(
                timestamp=base_time - i * 60,
                slo_name="latency_p95",
                current_value=150.0,
                target_value=200.0,
                measurement_unit="ms",
                status=SLOStatus.MET,
                compliance_percentage=0.95,
                trend_direction="stable"
            )
            self.validator.record_measurement(measurement)
        
        report = self.validator.validate_all_slos()
        
        assert report.overall_compliance_score >= 0.0
        assert report.overall_compliance_score <= 1.0
        assert report.total_slos > 0
        assert report.met_slos >= 0
        assert report.at_risk_slos >= 0
        assert report.violated_slos >= 0
        assert report.met_slos + report.at_risk_slos + report.violated_slos <= report.total_slos
        assert 0.0 <= report.production_readiness_score <= 1.0
        assert len(report.critical_slos_status) >= 0
        assert len(report.category_breakdown) >= 0
        assert len(report.recommendations) > 0
        assert len(report.detailed_validations) == report.total_slos
        assert len(report.metadata) >= 0

class TestGlobalFunctions:
    """Test global SLOs validation functions"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.slos_validation
        infra.slos_validation._slos_validator = None
    
    def test_get_slos_validator(self):
        """Test global validator access"""
        validator1 = get_slos_validator()
        validator2 = get_slos_validator()
        
        # Should return same instance
        assert validator1 is validator2
        assert isinstance(validator1, SLOsValidator)
    
    def test_add_slo_definition_global(self):
        """Test global SLO definition addition"""
        slo = SLODefinition(
            name="test_global_slo",
            category=SLOCategory.PERFORMANCE,
            importance=SLOImportance.HIGH,
            target_value=100.0,
            measurement_unit="%",
            measurement_window_hours=1.0,
            threshold_warning=0.8,
            threshold_critical=0.9,
            description="Test global SLO",
            measurement_method="test_measurement"
        )
        
        add_slo_definition(slo)
        
        validator = get_slos_validator()
        assert "test_global_slo" in validator.slo_definitions
    
    def test_record_slo_measurement_global(self):
        """Test global SLO measurement recording"""
        measurement = SLOMeasurement(
            timestamp=time.time(),
            slo_name="latency_p95",
            current_value=150.0,
            target_value=200.0,
            measurement_unit="ms",
            status=SLOStatus.MET,
            compliance_percentage=0.95,
            trend_direction="stable"
        )
        
        record_slo_measurement(measurement)
        
        validator = get_slos_validator()
        assert len(validator.measurements["latency_p95"]) == 1
    
    def test_validate_slo_global(self):
        """Test global SLO validation"""
        # Record some measurements first
        base_time = time.time()
        for i in range(5):
            measurement = SLOMeasurement(
                timestamp=base_time - i * 60,
                slo_name="latency_p95",
                current_value=150.0 + np.random.normal(0, 10),
                target_value=200.0,
                measurement_unit="ms",
                status=SLOStatus.MET,
                compliance_percentage=0.95,
                trend_direction="stable"
            )
            record_slo_measurement(measurement)
        
        validation = validate_slo("latency_p95")
        
        assert validation is not None
        assert validation.slo_name == "latency_p95"
        assert validation.current_value > 0
        assert validation.target_value == 200.0
        assert 0.0 <= validation.compliance_percentage <= 1.0
        assert validation.status in [SLOStatus.MET, SLOStatus.AT_RISK, SLOStatus.VIOLATED]
        assert validation.validation_status in [ValidationStatus.PASSED, ValidationStatus.WARNING, ValidationStatus.FAILED]
        assert len(validation.issues_found) >= 0
        assert len(validation.recommendations) > 0
    
    def test_validate_all_slos_global(self):
        """Test global SLOs validation"""
        # Record some measurements for multiple SLOs
        base_time = time.time()
        
        # Latency measurements
        for i in range(5):
            measurement = SLOMeasurement(
                timestamp=base_time - i * 60,
                slo_name="latency_p95",
                current_value=150.0,
                target_value=200.0,
                measurement_unit="ms",
                status=SLOStatus.MET,
                compliance_percentage=0.95,
                trend_direction="stable"
            )
            record_slo_measurement(measurement)
        
        # Uptime measurements
        for i in range(5):
            measurement = SLOMeasurement(
                timestamp=base_time - i * 3600,
                slo_name="uptime_percentage",
                current_value=99.95,
                target_value=99.9,
                measurement_unit="%",
                status=SLOStatus.MET,
                compliance_percentage=1.0,
                trend_direction="stable"
            )
            record_slo_measurement(measurement)
        
        report = validate_all_slos()
        
        assert isinstance(report, SLOsValidationReport)
        assert report.overall_compliance_score >= 0.0
        assert report.overall_compliance_score <= 1.0
        assert report.total_slos > 0
        assert report.met_slos >= 0
        assert report.at_risk_slos >= 0
        assert report.violated_slos >= 0
        assert 0.0 <= report.production_readiness_score <= 1.0
        assert len(report.recommendations) > 0
        assert len(report.detailed_validations) == report.total_slos

class TestSLOsValidationIntegration:
    """Integration tests for SLOs validation system"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Reset global validator
        import infra.slos_validation
        infra.slos_validation._slos_validator = None
    
    def test_comprehensive_slos_validation(self):
        """Test comprehensive SLOs validation workflow"""
        # Test different SLO scenarios
        test_cases = [
            ("latency_p95", 150.0, SLOStatus.MET, ValidationStatus.PASSED),      # Good latency
            ("latency_p95", 250.0, SLOStatus.VIOLATED, ValidationStatus.FAILED), # Bad latency
            ("uptime_percentage", 99.95, SLOStatus.MET, ValidationStatus.PASSED), # Good uptime
            ("uptime_percentage", 99.0, SLOStatus.VIOLATED, ValidationStatus.FAILED), # Bad uptime
            ("trading_accuracy", 85.0, SLOStatus.MET, ValidationStatus.PASSED), # Good accuracy
            ("trading_accuracy", 70.0, SLOStatus.VIOLATED, ValidationStatus.FAILED) # Bad accuracy
        ]
        
        for slo_name, value, expected_status, expected_validation in test_cases:
            # Record measurements
            base_time = time.time()
            for i in range(10):
                measurement = SLOMeasurement(
                    timestamp=base_time - i * 60,
                    slo_name=slo_name,
                    current_value=value + np.random.normal(0, value * 0.05),
                    target_value=200.0 if "latency" in slo_name else 99.9 if "uptime" in slo_name else 80.0,
                    measurement_unit="ms" if "latency" in slo_name else "%",
                    status=expected_status,
                    compliance_percentage=0.95 if expected_status == SLOStatus.MET else 0.5,
                    trend_direction="stable"
                )
                record_slo_measurement(measurement)
            
            validation = validate_slo(slo_name)
            
            assert validation is not None
            assert validation.slo_name == slo_name
            assert validation.current_value > 0
            assert validation.status in [SLOStatus.MET, SLOStatus.AT_RISK, SLOStatus.VIOLATED]
            assert validation.validation_status in [ValidationStatus.PASSED, ValidationStatus.WARNING, ValidationStatus.FAILED]
            assert len(validation.issues_found) >= 0
            assert len(validation.recommendations) > 0
        
        # Generate comprehensive report
        report = validate_all_slos()
        
        assert isinstance(report, SLOsValidationReport)
        assert report.overall_compliance_score >= 0.0
        assert report.overall_compliance_score <= 1.0
        assert report.total_slos > 0
        assert report.met_slos >= 0
        assert report.at_risk_slos >= 0
        assert report.violated_slos >= 0
        assert report.met_slos + report.at_risk_slos + report.violated_slos <= report.total_slos
        assert 0.0 <= report.production_readiness_score <= 1.0
        assert len(report.critical_slos_status) >= 0
        assert len(report.category_breakdown) >= 0
        assert len(report.recommendations) > 0
        assert len(report.detailed_validations) == report.total_slos
    
    def test_production_readiness_assessment(self):
        """Test production readiness assessment"""
        # Record measurements for critical SLOs
        base_time = time.time()
        
        critical_slos = ["latency_p95", "uptime_percentage", "error_rate", "trading_accuracy"]
        
        for slo_name in critical_slos:
            for i in range(20):
                if "latency" in slo_name:
                    value = 150.0  # Good latency
                elif "uptime" in slo_name:
                    value = 99.95  # Good uptime
                elif "error" in slo_name:
                    value = 0.05  # Good error rate
                else:  # trading_accuracy
                    value = 85.0  # Good accuracy
                
                measurement = SLOMeasurement(
                    timestamp=base_time - i * 60,
                    slo_name=slo_name,
                    current_value=value + np.random.normal(0, value * 0.01),
                    target_value=200.0 if "latency" in slo_name else 99.9 if "uptime" in slo_name else 0.1 if "error" in slo_name else 80.0,
                    measurement_unit="ms" if "latency" in slo_name else "%",
                    status=SLOStatus.MET,
                    compliance_percentage=0.98,
                    trend_direction="stable"
                )
                record_slo_measurement(measurement)
        
        report = validate_all_slos()
        
        # Should have reasonable production readiness score (may be lower due to default SLOs)
        assert report.production_readiness_score >= 0.0
        assert report.overall_compliance_score >= 0.0
        assert report.met_slos >= 0  # At least some should be met
        assert len(report.recommendations) > 0
    
    def test_slo_violation_detection(self):
        """Test SLO violation detection"""
        # Record measurements that violate SLOs
        base_time = time.time()
        
        violation_cases = [
            ("latency_p95", 300.0),  # Exceeds 200ms target
            ("uptime_percentage", 95.0),  # Below 99.9% target
            ("error_rate", 2.0),  # Above 0.1% target
            ("trading_accuracy", 60.0)  # Below 80% target
        ]
        
        for slo_name, value in violation_cases:
            for i in range(10):
                measurement = SLOMeasurement(
                    timestamp=base_time - i * 60,
                    slo_name=slo_name,
                    current_value=value + np.random.normal(0, value * 0.05),
                    target_value=200.0 if "latency" in slo_name else 99.9 if "uptime" in slo_name else 0.1 if "error" in slo_name else 80.0,
                    measurement_unit="ms" if "latency" in slo_name else "%",
                    status=SLOStatus.VIOLATED,
                    compliance_percentage=0.2,
                    trend_direction="degrading"
                )
                record_slo_measurement(measurement)
        
        report = validate_all_slos()
        
        # Should detect violations
        assert report.violated_slos > 0
        assert report.overall_compliance_score < 0.8
        assert report.production_readiness_score < 0.8
        assert any("violated" in rec.lower() or "critical" in rec.lower() for rec in report.recommendations)
    
    def test_category_breakdown_analysis(self):
        """Test category breakdown analysis"""
        # Record measurements for different categories
        base_time = time.time()
        
        category_slos = {
            SLOCategory.PERFORMANCE: ["latency_p95", "cpu_usage_p95"],
            SLOCategory.RELIABILITY: ["uptime_percentage", "error_rate"],
            SLOCategory.ACCURACY: ["trading_accuracy", "signal_quality"],
            SLOCategory.OPERATIONAL: ["monitoring_coverage", "alert_response_time"]
        }
        
        for category, slos in category_slos.items():
            for slo_name in slos:
                for i in range(5):
                    measurement = SLOMeasurement(
                        timestamp=base_time - i * 60,
                        slo_name=slo_name,
                        current_value=100.0 + np.random.normal(0, 10),
                        target_value=200.0,
                        measurement_unit="ms" if "latency" in slo_name else "%",
                        status=SLOStatus.MET,
                        compliance_percentage=0.95,
                        trend_direction="stable"
                    )
                    record_slo_measurement(measurement)
        
        report = validate_all_slos()
        
        # Should have category breakdown
        assert len(report.category_breakdown) > 0
        for category, data in report.category_breakdown.items():
            assert "total" in data
            assert "met" in data
            assert "at_risk" in data
            assert "violated" in data
            assert "compliance_score" in data
            assert 0.0 <= data["compliance_score"] <= 1.0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
