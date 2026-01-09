"""
SLOs (Service Level Objectives) Validation System

This module implements a comprehensive validation system to ensure all SLOs
are met in production, including performance, reliability, accuracy, and
operational SLOs validation.

Key Features:
- Comprehensive SLOs validation for production readiness
- Performance SLOs validation (latency, throughput, resource usage)
- Reliability SLOs validation (uptime, availability, error rates)
- Accuracy SLOs validation (trading accuracy, signal quality)
- Operational SLOs validation (monitoring, alerting, recovery)
- Automated SLOs compliance reporting
- Production readiness assessment
- SLOs violation detection and alerting
"""

import time
import math
import statistics
import numpy as np
import threading
import json
import asyncio
import hashlib
import logging
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

class SLOCategory(Enum):
    """SLO category types"""
    PERFORMANCE = "performance"  # Latency, throughput, resource usage
    RELIABILITY = "reliability"  # Uptime, availability, error rates
    ACCURACY = "accuracy"  # Trading accuracy, signal quality
    OPERATIONAL = "operational"  # Monitoring, alerting, recovery
    SECURITY = "security"  # Security, compliance, audit
    BUSINESS = "business"  # Revenue, costs, ROI

class SLOStatus(Enum):
    """SLO status types"""
    MET = "met"  # SLO is being met
    AT_RISK = "at_risk"  # SLO is at risk of violation
    VIOLATED = "violated"  # SLO has been violated
    UNKNOWN = "unknown"  # SLO status unknown

class SLOImportance(Enum):
    """SLO importance levels"""
    CRITICAL = "critical"  # Critical SLO - must be met
    HIGH = "high"  # High importance SLO
    MEDIUM = "medium"  # Medium importance SLO
    LOW = "low"  # Low importance SLO

class ValidationStatus(Enum):
    """Validation status"""
    PASSED = "passed"  # Validation passed
    WARNING = "warning"  # Validation passed with warnings
    FAILED = "failed"  # Validation failed
    PENDING = "pending"  # Validation pending

@dataclass
class SLODefinition:
    """SLO definition data structure"""
    name: str
    category: SLOCategory
    importance: SLOImportance
    target_value: float
    measurement_unit: str
    measurement_window_hours: float
    threshold_warning: float  # Warning threshold (e.g., 0.8 for 80%)
    threshold_critical: float  # Critical threshold (e.g., 0.9 for 90%)
    description: str
    measurement_method: str
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SLOMeasurement:
    """SLO measurement data structure"""
    timestamp: float
    slo_name: str
    current_value: float
    target_value: float
    measurement_unit: str
    status: SLOStatus
    compliance_percentage: float
    trend_direction: str  # "improving", "stable", "degrading"
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SLOValidation:
    """SLO validation result"""
    timestamp: float
    slo_name: str
    category: SLOCategory
    importance: SLOImportance
    current_value: float
    target_value: float
    compliance_percentage: float
    status: SLOStatus
    validation_status: ValidationStatus
    issues_found: List[str]
    recommendations: List[str]
    trend_analysis: Dict[str, Any]
    historical_data: List[SLOMeasurement]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SLOsValidationReport:
    """SLOs validation report"""
    timestamp: float
    overall_compliance_score: float
    total_slos: int
    met_slos: int
    at_risk_slos: int
    violated_slos: int
    critical_slos_status: Dict[str, SLOStatus]
    category_breakdown: Dict[SLOCategory, Dict[str, Any]]
    production_readiness_score: float
    recommendations: List[str]
    detailed_validations: List[SLOValidation]
    metadata: Dict[str, Any] = field(default_factory=dict)

class SLOsValidator:
    """SLOs validator for comprehensive production validation"""
    
    def __init__(self):
        self.slo_definitions: Dict[str, SLODefinition] = {}
        self.measurements: Dict[str, List[SLOMeasurement]] = defaultdict(list)
        self.validations: List[SLOValidation] = []
        self.lock = threading.RLock()
        self.start_time = time.time()
        
        # Initialize default SLOs
        self._initialize_default_slos()
    
    def _initialize_default_slos(self):
        """Initialize default SLOs for trading system"""
        default_slos = [
            # Performance SLOs
            SLODefinition(
                name="latency_p95",
                category=SLOCategory.PERFORMANCE,
                importance=SLOImportance.CRITICAL,
                target_value=200.0,
                measurement_unit="ms",
                measurement_window_hours=24.0,
                threshold_warning=0.8,
                threshold_critical=0.9,
                description="P95 latency must be <200ms",
                measurement_method="latency_measurement"
            ),
            SLODefinition(
                name="throughput_orders_per_second",
                category=SLOCategory.PERFORMANCE,
                importance=SLOImportance.HIGH,
                target_value=100.0,
                measurement_unit="orders/sec",
                measurement_window_hours=1.0,
                threshold_warning=0.7,
                threshold_critical=0.8,
                description="Order processing throughput",
                measurement_method="throughput_measurement"
            ),
            SLODefinition(
                name="cpu_usage_p95",
                category=SLOCategory.PERFORMANCE,
                importance=SLOImportance.MEDIUM,
                target_value=80.0,
                measurement_unit="%",
                measurement_window_hours=1.0,
                threshold_warning=0.8,
                threshold_critical=0.9,
                description="CPU usage P95 <80%",
                measurement_method="resource_measurement"
            ),
            SLODefinition(
                name="memory_usage_p95",
                category=SLOCategory.PERFORMANCE,
                importance=SLOImportance.MEDIUM,
                target_value=85.0,
                measurement_unit="%",
                measurement_window_hours=1.0,
                threshold_warning=0.8,
                threshold_critical=0.9,
                description="Memory usage P95 <85%",
                measurement_method="resource_measurement"
            ),
            
            # Reliability SLOs
            SLODefinition(
                name="uptime_percentage",
                category=SLOCategory.RELIABILITY,
                importance=SLOImportance.CRITICAL,
                target_value=99.9,
                measurement_unit="%",
                measurement_window_hours=24.0,
                threshold_warning=0.95,
                threshold_critical=0.99,
                description="System uptime >99.9%",
                measurement_method="uptime_measurement"
            ),
            SLODefinition(
                name="error_rate",
                category=SLOCategory.RELIABILITY,
                importance=SLOImportance.CRITICAL,
                target_value=0.1,
                measurement_unit="%",
                measurement_window_hours=1.0,
                threshold_warning=0.5,
                threshold_critical=1.0,
                description="Error rate <0.1%",
                measurement_method="error_rate_measurement"
            ),
            SLODefinition(
                name="data_loss_percentage",
                category=SLOCategory.RELIABILITY,
                importance=SLOImportance.HIGH,
                target_value=0.01,
                measurement_unit="%",
                measurement_window_hours=24.0,
                threshold_warning=0.5,
                threshold_critical=1.0,
                description="Data loss <0.01%",
                measurement_method="data_loss_measurement"
            ),
            
            # Accuracy SLOs
            SLODefinition(
                name="trading_accuracy",
                category=SLOCategory.ACCURACY,
                importance=SLOImportance.CRITICAL,
                target_value=80.0,
                measurement_unit="%",
                measurement_window_hours=24.0,
                threshold_warning=0.75,
                threshold_critical=0.8,
                description="Trading accuracy >80%",
                measurement_method="trading_accuracy_measurement"
            ),
            SLODefinition(
                name="signal_quality",
                category=SLOCategory.ACCURACY,
                importance=SLOImportance.HIGH,
                target_value=75.0,
                measurement_unit="%",
                measurement_window_hours=24.0,
                threshold_warning=0.7,
                threshold_critical=0.75,
                description="Signal quality >75%",
                measurement_method="signal_quality_measurement"
            ),
            SLODefinition(
                name="false_signal_reduction",
                category=SLOCategory.ACCURACY,
                importance=SLOImportance.HIGH,
                target_value=80.0,
                measurement_unit="%",
                measurement_window_hours=24.0,
                threshold_warning=0.7,
                threshold_critical=0.8,
                description="False signal reduction >80%",
                measurement_method="false_signal_measurement"
            ),
            
            # Operational SLOs
            SLODefinition(
                name="monitoring_coverage",
                category=SLOCategory.OPERATIONAL,
                importance=SLOImportance.HIGH,
                target_value=100.0,
                measurement_unit="%",
                measurement_window_hours=24.0,
                threshold_warning=0.95,
                threshold_critical=0.98,
                description="Monitoring coverage 100%",
                measurement_method="monitoring_measurement"
            ),
            SLODefinition(
                name="alert_response_time",
                category=SLOCategory.OPERATIONAL,
                importance=SLOImportance.HIGH,
                target_value=5.0,
                measurement_unit="minutes",
                measurement_window_hours=24.0,
                threshold_warning=0.8,
                threshold_critical=0.9,
                description="Alert response time <5 minutes",
                measurement_method="alert_response_measurement"
            ),
            SLODefinition(
                name="recovery_time",
                category=SLOCategory.OPERATIONAL,
                importance=SLOImportance.CRITICAL,
                target_value=10.0,
                measurement_unit="minutes",
                measurement_window_hours=24.0,
                threshold_warning=0.8,
                threshold_critical=0.9,
                description="Recovery time <10 minutes",
                measurement_method="recovery_time_measurement"
            )
        ]
        
        for slo in default_slos:
            self.slo_definitions[slo.name] = slo
    
    def add_slo_definition(self, slo: SLODefinition) -> None:
        """Add SLO definition"""
        with self.lock:
            self.slo_definitions[slo.name] = slo
    
    def record_measurement(self, measurement: SLOMeasurement) -> None:
        """Record SLO measurement"""
        with self.lock:
            self.measurements[measurement.slo_name].append(measurement)
            
            # Keep only recent measurements (last 7 days)
            cutoff_time = time.time() - (7 * 24 * 3600)
            self.measurements[measurement.slo_name] = [
                m for m in self.measurements[measurement.slo_name]
                if m.timestamp >= cutoff_time
            ]
    
    def validate_slo(self, slo_name: str) -> Optional[SLOValidation]:
        """Validate specific SLO"""
        if slo_name not in self.slo_definitions:
            return None
        
        slo_def = self.slo_definitions[slo_name]
        measurements = self.measurements.get(slo_name, [])
        
        if not measurements:
            return self._create_empty_validation(slo_def)
        
        # Calculate current compliance
        recent_measurements = self._get_recent_measurements(measurements, slo_def.measurement_window_hours)
        
        if not recent_measurements:
            return self._create_empty_validation(slo_def)
        
        # Calculate compliance percentage
        compliance_percentage = self._calculate_compliance_percentage(recent_measurements, slo_def)
        
        # Determine SLO status
        status = self._determine_slo_status(compliance_percentage, slo_def)
        
        # Determine validation status
        validation_status = self._determine_validation_status(status, slo_def.importance)
        
        # Generate issues and recommendations
        issues_found = self._identify_issues(slo_def, compliance_percentage, status)
        recommendations = self._generate_recommendations(slo_def, compliance_percentage, status)
        
        # Analyze trends
        trend_analysis = self._analyze_trends(measurements)
        
        validation = SLOValidation(
            timestamp=time.time(),
            slo_name=slo_name,
            category=slo_def.category,
            importance=slo_def.importance,
            current_value=recent_measurements[-1].current_value if recent_measurements else 0.0,
            target_value=slo_def.target_value,
            compliance_percentage=compliance_percentage,
            status=status,
            validation_status=validation_status,
            issues_found=issues_found,
            recommendations=recommendations,
            trend_analysis=trend_analysis,
            historical_data=recent_measurements,
            metadata={
                "measurement_window_hours": slo_def.measurement_window_hours,
                "measurement_count": len(recent_measurements),
                "validation_time": time.time()
            }
        )
        
        with self.lock:
            self.validations.append(validation)
        
        return validation
    
    def validate_all_slos(self) -> SLOsValidationReport:
        """Validate all SLOs and generate comprehensive report"""
        with self.lock:
            validations = []
            
            for slo_name in self.slo_definitions:
                validation = self.validate_slo(slo_name)
                if validation:
                    validations.append(validation)
            
            # Calculate overall metrics
            total_slos = len(validations)
            met_slos = sum(1 for v in validations if v.status == SLOStatus.MET)
            at_risk_slos = sum(1 for v in validations if v.status == SLOStatus.AT_RISK)
            violated_slos = sum(1 for v in validations if v.status == SLOStatus.VIOLATED)
            
            # Calculate overall compliance score
            overall_compliance_score = met_slos / total_slos if total_slos > 0 else 0.0
            
            # Calculate production readiness score
            production_readiness_score = self._calculate_production_readiness_score(validations)
            
            # Analyze critical SLOs
            critical_slos_status = {
                v.slo_name: v.status for v in validations
                if v.importance == SLOImportance.CRITICAL
            }
            
            # Category breakdown
            category_breakdown = self._analyze_category_breakdown(validations)
            
            # Generate recommendations
            recommendations = self._generate_overall_recommendations(validations)
            
            return SLOsValidationReport(
                timestamp=time.time(),
                overall_compliance_score=overall_compliance_score,
                total_slos=total_slos,
                met_slos=met_slos,
                at_risk_slos=at_risk_slos,
                violated_slos=violated_slos,
                critical_slos_status=critical_slos_status,
                category_breakdown=category_breakdown,
                production_readiness_score=production_readiness_score,
                recommendations=recommendations,
                detailed_validations=validations,
                metadata={
                    "validation_duration": time.time() - self.start_time,
                    "total_measurements": sum(len(self.measurements[name]) for name in self.measurements)
                }
            )
    
    def _create_empty_validation(self, slo_def: SLODefinition) -> SLOValidation:
        """Create empty validation when no data available"""
        return SLOValidation(
            timestamp=time.time(),
            slo_name=slo_def.name,
            category=slo_def.category,
            importance=slo_def.importance,
            current_value=0.0,
            target_value=slo_def.target_value,
            compliance_percentage=0.0,
            status=SLOStatus.UNKNOWN,
            validation_status=ValidationStatus.FAILED,
            issues_found=[f"No measurement data available for {slo_def.name}"],
            recommendations=[f"Collect measurement data for {slo_def.name}"],
            trend_analysis={},
            historical_data=[],
            metadata={
                "measurement_window_hours": slo_def.measurement_window_hours,
                "measurement_count": 0,
                "validation_time": time.time()
            }
        )
    
    def _get_recent_measurements(self, measurements: List[SLOMeasurement], window_hours: float) -> List[SLOMeasurement]:
        """Get recent measurements within window"""
        cutoff_time = time.time() - (window_hours * 3600)
        return [m for m in measurements if m.timestamp >= cutoff_time]
    
    def _calculate_compliance_percentage(self, measurements: List[SLOMeasurement], slo_def: SLODefinition) -> float:
        """Calculate compliance percentage"""
        if not measurements:
            return 0.0
        
        # For most SLOs, we want to be below the target (e.g., latency <200ms)
        # For some SLOs, we want to be above the target (e.g., uptime >99.9%)
        if slo_def.name in ["uptime_percentage", "trading_accuracy", "signal_quality", 
                           "false_signal_reduction", "monitoring_coverage"]:
            # Higher is better
            compliant_measurements = sum(1 for m in measurements if m.current_value >= slo_def.target_value)
        else:
            # Lower is better
            compliant_measurements = sum(1 for m in measurements if m.current_value <= slo_def.target_value)
        
        return compliant_measurements / len(measurements)
    
    def _determine_slo_status(self, compliance_percentage: float, slo_def: SLODefinition) -> SLOStatus:
        """Determine SLO status based on compliance"""
        if compliance_percentage >= slo_def.threshold_critical:
            return SLOStatus.MET
        elif compliance_percentage >= slo_def.threshold_warning:
            return SLOStatus.AT_RISK
        else:
            return SLOStatus.VIOLATED
    
    def _determine_validation_status(self, slo_status: SLOStatus, importance: SLOImportance) -> ValidationStatus:
        """Determine validation status"""
        if slo_status == SLOStatus.MET:
            return ValidationStatus.PASSED
        elif slo_status == SLOStatus.AT_RISK:
            if importance == SLOImportance.CRITICAL:
                return ValidationStatus.WARNING
            else:
                return ValidationStatus.PASSED
        else:  # VIOLATED
            if importance == SLOImportance.CRITICAL:
                return ValidationStatus.FAILED
            else:
                return ValidationStatus.WARNING
    
    def _identify_issues(self, slo_def: SLODefinition, compliance_percentage: float, status: SLOStatus) -> List[str]:
        """Identify SLO issues"""
        issues = []
        
        if status == SLOStatus.VIOLATED:
            issues.append(f"SLO {slo_def.name} is violated (compliance: {compliance_percentage:.1%})")
        elif status == SLOStatus.AT_RISK:
            issues.append(f"SLO {slo_def.name} is at risk (compliance: {compliance_percentage:.1%})")
        
        if compliance_percentage < 0.5:
            issues.append(f"Very low compliance for {slo_def.name}")
        
        if slo_def.importance == SLOImportance.CRITICAL and status != SLOStatus.MET:
            issues.append(f"Critical SLO {slo_def.name} is not being met")
        
        return issues
    
    def _generate_recommendations(self, slo_def: SLODefinition, compliance_percentage: float, status: SLOStatus) -> List[str]:
        """Generate SLO recommendations"""
        recommendations = []
        
        if status == SLOStatus.VIOLATED:
            recommendations.append(f"Immediate action required for {slo_def.name}")
            recommendations.append(f"Investigate root cause of {slo_def.name} violation")
        elif status == SLOStatus.AT_RISK:
            recommendations.append(f"Monitor {slo_def.name} closely")
            recommendations.append(f"Consider preventive measures for {slo_def.name}")
        
        if compliance_percentage < 0.8:
            recommendations.append(f"Optimize {slo_def.name} performance")
        
        if slo_def.importance == SLOImportance.CRITICAL and status != SLOStatus.MET:
            recommendations.append(f"Prioritize fixing critical SLO {slo_def.name}")
        
        if status == SLOStatus.MET:
            recommendations.append(f"Excellent performance for {slo_def.name}")
        
        return recommendations
    
    def _analyze_trends(self, measurements: List[SLOMeasurement]) -> Dict[str, Any]:
        """Analyze SLO trends"""
        if len(measurements) < 2:
            return {"trend": "insufficient_data", "direction": "unknown"}
        
        values = [m.current_value for m in measurements]
        
        # Calculate trend using linear regression
        x = np.arange(len(values))
        y = np.array(values)
        
        n = len(x)
        sum_x = np.sum(x)
        sum_y = np.sum(y)
        sum_xy = np.sum(x * y)
        sum_x2 = np.sum(x * x)
        
        if n * sum_x2 - sum_x * sum_x == 0:
            slope = 0
        else:
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        
        # Determine trend direction
        if slope > 0.1:
            direction = "degrading"
        elif slope < -0.1:
            direction = "improving"
        else:
            direction = "stable"
        
        return {
            "trend": direction,
            "direction": direction,
            "slope": slope,
            "volatility": np.std(values) / np.mean(values) if np.mean(values) > 0 else 0,
            "measurement_count": len(measurements)
        }
    
    def _calculate_production_readiness_score(self, validations: List[SLOValidation]) -> float:
        """Calculate production readiness score"""
        if not validations:
            return 0.0
        
        # Weight by importance
        weights = {
            SLOImportance.CRITICAL: 4.0,
            SLOImportance.HIGH: 3.0,
            SLOImportance.MEDIUM: 2.0,
            SLOImportance.LOW: 1.0
        }
        
        total_weight = 0.0
        weighted_score = 0.0
        
        for validation in validations:
            weight = weights.get(validation.importance, 1.0)
            total_weight += weight
            
            if validation.status == SLOStatus.MET:
                weighted_score += weight * 1.0
            elif validation.status == SLOStatus.AT_RISK:
                weighted_score += weight * 0.7
            elif validation.status == SLOStatus.VIOLATED:
                weighted_score += weight * 0.3
            else:  # UNKNOWN
                weighted_score += weight * 0.0
        
        return weighted_score / total_weight if total_weight > 0 else 0.0
    
    def _analyze_category_breakdown(self, validations: List[SLOValidation]) -> Dict[SLOCategory, Dict[str, Any]]:
        """Analyze SLOs by category"""
        category_data = defaultdict(lambda: {
            "total": 0,
            "met": 0,
            "at_risk": 0,
            "violated": 0,
            "unknown": 0,
            "compliance_score": 0.0
        })
        
        for validation in validations:
            category = validation.category
            category_data[category]["total"] += 1
            
            if validation.status == SLOStatus.MET:
                category_data[category]["met"] += 1
            elif validation.status == SLOStatus.AT_RISK:
                category_data[category]["at_risk"] += 1
            elif validation.status == SLOStatus.VIOLATED:
                category_data[category]["violated"] += 1
            else:
                category_data[category]["unknown"] += 1
        
        # Calculate compliance scores
        for category, data in category_data.items():
            if data["total"] > 0:
                data["compliance_score"] = data["met"] / data["total"]
        
        return dict(category_data)
    
    def _generate_overall_recommendations(self, validations: List[SLOValidation]) -> List[str]:
        """Generate overall recommendations"""
        recommendations = []
        
        # Count violations by importance
        critical_violations = sum(1 for v in validations 
                                if v.importance == SLOImportance.CRITICAL and v.status == SLOStatus.VIOLATED)
        high_violations = sum(1 for v in validations 
                            if v.importance == SLOImportance.HIGH and v.status == SLOStatus.VIOLATED)
        
        if critical_violations > 0:
            recommendations.append(f"CRITICAL: {critical_violations} critical SLOs violated - immediate action required")
        
        if high_violations > 0:
            recommendations.append(f"HIGH: {high_violations} high-priority SLOs violated - address soon")
        
        # Category-specific recommendations
        category_violations = defaultdict(int)
        for validation in validations:
            if validation.status == SLOStatus.VIOLATED:
                category_violations[validation.category] += 1
        
        for category, count in category_violations.items():
            if count > 0:
                recommendations.append(f"Focus on {category.value} category: {count} SLOs violated")
        
        # Overall health
        met_count = sum(1 for v in validations if v.status == SLOStatus.MET)
        total_count = len(validations)
        
        if met_count == total_count:
            recommendations.append("Excellent! All SLOs are being met")
        elif met_count / total_count >= 0.8:
            recommendations.append("Good performance - most SLOs are being met")
        else:
            recommendations.append("Performance issues detected - review SLO violations")
        
        return recommendations

# Global SLOs validator
_slos_validator: Optional[SLOsValidator] = None

def get_slos_validator() -> SLOsValidator:
    """Get global SLOs validator instance"""
    global _slos_validator
    if _slos_validator is None:
        _slos_validator = SLOsValidator()
    return _slos_validator

def add_slo_definition(slo: SLODefinition) -> None:
    """Add SLO definition"""
    validator = get_slos_validator()
    validator.add_slo_definition(slo)

def record_slo_measurement(measurement: SLOMeasurement) -> None:
    """Record SLO measurement"""
    validator = get_slos_validator()
    validator.record_measurement(measurement)

def validate_slo(slo_name: str) -> Optional[SLOValidation]:
    """Validate specific SLO"""
    validator = get_slos_validator()
    return validator.validate_slo(slo_name)

def validate_all_slos() -> SLOsValidationReport:
    """Validate all SLOs and generate comprehensive report"""
    validator = get_slos_validator()
    return validator.validate_all_slos()

if __name__ == "__main__":
    # Example usage
    validator = get_slos_validator()
    
    # Record some example measurements
    current_time = time.time()
    
    # Latency measurements
    for i in range(100):
        measurement = SLOMeasurement(
            timestamp=current_time - i * 60,
            slo_name="latency_p95",
            current_value=150.0 + np.random.normal(0, 20),
            target_value=200.0,
            measurement_unit="ms",
            status=SLOStatus.MET,
            compliance_percentage=0.95,
            trend_direction="stable"
        )
        record_slo_measurement(measurement)
    
    # Uptime measurements
    for i in range(24):
        measurement = SLOMeasurement(
            timestamp=current_time - i * 3600,
            slo_name="uptime_percentage",
            current_value=99.95 + np.random.normal(0, 0.01),
            target_value=99.9,
            measurement_unit="%",
            status=SLOStatus.MET,
            compliance_percentage=1.0,
            trend_direction="stable"
        )
        record_slo_measurement(measurement)
    
    # Validate all SLOs
    report = validate_all_slos()
    
    print(f"SLOs Validation Report:")
    print(f"Overall Compliance Score: {report.overall_compliance_score:.2%}")
    print(f"Total SLOs: {report.total_slos}")
    print(f"Met SLOs: {report.met_slos}")
    print(f"At Risk SLOs: {report.at_risk_slos}")
    print(f"Violated SLOs: {report.violated_slos}")
    print(f"Production Readiness Score: {report.production_readiness_score:.2%}")
    
    print("\nCritical SLOs Status:")
    for slo_name, status in report.critical_slos_status.items():
        print(f"- {slo_name}: {status.value}")
    
    print("\nRecommendations:")
    for rec in report.recommendations:
        print(f"- {rec}")
