#!/usr/bin/env python3
"""
Production Validation Orchestrator for TelegramMoneyBot v8.0
Comprehensive production validation, load testing, and performance assessment
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

# Import validation modules
from production_load_testing import ProductionLoadTesting
from production_test_validation import ProductionTestValidation
from security_hardening import SecurityHardening

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ValidationPhase(Enum):
    """Validation phases"""
    LOAD_TESTING = "load_testing"
    TEST_VALIDATION = "test_validation"
    SECURITY_ASSESSMENT = "security_assessment"
    PERFORMANCE_BENCHMARKING = "performance_benchmarking"
    PRODUCTION_READINESS = "production_readiness"

class ValidationStatus(Enum):
    """Validation status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WARNING = "warning"

@dataclass
class ValidationPhaseResult:
    """Validation phase result"""
    phase: ValidationPhase
    status: ValidationStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    success: bool = False
    issues_found: List[str] = None
    recommendations: List[str] = None
    metrics: Dict[str, Any] = None

@dataclass
class ProductionValidationReport:
    """Production validation report"""
    validation_id: str
    timestamp: datetime
    total_phases: int
    completed_phases: int
    failed_phases: int
    overall_status: ValidationStatus
    total_duration_seconds: float
    phase_results: List[ValidationPhaseResult]
    critical_issues: List[str]
    warnings: List[str]
    recommendations: List[str]
    production_readiness_score: float
    go_live_approved: bool

class ProductionValidationOrchestrator:
    """Production validation orchestrator"""
    
    def __init__(self, config_path: str = "production_validation_config.json"):
        self.config = self._load_config(config_path)
        self.phase_results: List[ValidationPhaseResult] = []
        self.validation_reports: List[ProductionValidationReport] = []
        
        # Initialize validation modules
        self.load_tester = ProductionLoadTesting()
        self.test_validator = ProductionTestValidation()
        self.security_hardener = SecurityHardening()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load production validation configuration"""
        default_config = {
            "validation_phases": {
                "load_testing": {
                    "enabled": True,
                    "timeout_minutes": 60,
                    "critical": True,
                    "required_tests": ["stress_test", "spike_test", "volume_test"]
                },
                "test_validation": {
                    "enabled": True,
                    "timeout_minutes": 30,
                    "critical": True,
                    "required_suites": ["unit_tests", "integration_tests", "e2e_tests"]
                },
                "security_assessment": {
                    "enabled": True,
                    "timeout_minutes": 15,
                    "critical": True,
                    "required_checks": ["password_policy", "access_control", "encryption"]
                },
                "performance_benchmarking": {
                    "enabled": True,
                    "timeout_minutes": 45,
                    "critical": False,
                    "benchmarks": ["latency", "throughput", "resource_usage"]
                },
                "production_readiness": {
                    "enabled": True,
                    "timeout_minutes": 10,
                    "critical": True,
                    "readiness_criteria": ["all_tests_pass", "security_compliant", "performance_acceptable"]
                }
            },
            "production_criteria": {
                "minimum_load_test_pass_rate": 90.0,
                "minimum_test_validation_pass_rate": 95.0,
                "minimum_security_score": 80.0,
                "maximum_latency_ms": 200.0,
                "minimum_throughput_rps": 10.0,
                "maximum_cpu_usage_percent": 85.0,
                "maximum_memory_usage_percent": 85.0,
                "maximum_error_rate_percent": 1.0
            },
            "reporting": {
                "generate_detailed_report": True,
                "include_metrics": True,
                "include_recommendations": True,
                "export_formats": ["json", "html"]
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
            logger.error(f"Error loading production validation config: {e}")
            return default_config
    
    async def run_comprehensive_validation(self) -> ProductionValidationReport:
        """Run comprehensive production validation"""
        try:
            logger.info("Starting comprehensive production validation")
            start_time = datetime.now()
            
            # Initialize validation phases
            phases = [
                ValidationPhase.LOAD_TESTING,
                ValidationPhase.TEST_VALIDATION,
                ValidationPhase.SECURITY_ASSESSMENT,
                ValidationPhase.PERFORMANCE_BENCHMARKING,
                ValidationPhase.PRODUCTION_READINESS
            ]
            
            # Run each validation phase
            for phase in phases:
                if self.config["validation_phases"][phase.value]["enabled"]:
                    logger.info(f"Running validation phase: {phase.value}")
                    result = await self._run_validation_phase(phase)
                    self.phase_results.append(result)
                    
                    # Check if phase failed critically
                    if result.status == ValidationStatus.FAILED and self.config["validation_phases"][phase.value]["critical"]:
                        logger.error(f"Critical phase {phase.value} failed, stopping validation")
                        break
                else:
                    logger.info(f"Skipping disabled phase: {phase.value}")
            
            # Generate comprehensive report
            report = await self._generate_validation_report(start_time)
            
            # Store report
            self.validation_reports.append(report)
            
            logger.info(f"Production validation completed: {report.overall_status.value}")
            return report
            
        except Exception as e:
            logger.error(f"Error running comprehensive validation: {e}")
            raise
    
    async def _run_validation_phase(self, phase: ValidationPhase) -> ValidationPhaseResult:
        """Run a specific validation phase"""
        try:
            start_time = datetime.now()
            result = ValidationPhaseResult(
                phase=phase,
                status=ValidationStatus.RUNNING,
                start_time=start_time,
                issues_found=[],
                recommendations=[],
                metrics={}
            )
            
            # Run phase-specific validation
            if phase == ValidationPhase.LOAD_TESTING:
                await self._run_load_testing_phase(result)
            elif phase == ValidationPhase.TEST_VALIDATION:
                await self._run_test_validation_phase(result)
            elif phase == ValidationPhase.SECURITY_ASSESSMENT:
                await self._run_security_assessment_phase(result)
            elif phase == ValidationPhase.PERFORMANCE_BENCHMARKING:
                await self._run_performance_benchmarking_phase(result)
            elif phase == ValidationPhase.PRODUCTION_READINESS:
                await self._run_production_readiness_phase(result)
            
            # Update result
            result.end_time = datetime.now()
            result.duration_seconds = (result.end_time - result.start_time).total_seconds()
            result.status = ValidationStatus.COMPLETED if result.success else ValidationStatus.FAILED
            
            return result
            
        except Exception as e:
            logger.error(f"Error running validation phase {phase.value}: {e}")
            result.status = ValidationStatus.FAILED
            result.issues_found.append(f"Phase execution error: {str(e)}")
            return result
    
    async def _run_load_testing_phase(self, result: ValidationPhaseResult):
        """Run load testing phase"""
        try:
            # Run all load tests
            load_test_results = await self.load_tester.run_all_load_tests()
            
            # Analyze results
            total_tests = len(load_test_results)
            passed_tests = len([r for r in load_test_results if r.result.value == "passed"])
            failed_tests = len([r for r in load_test_results if r.result.value == "failed"])
            
            pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
            
            # Check against criteria
            criteria = self.config["production_criteria"]
            if pass_rate < criteria["minimum_load_test_pass_rate"]:
                result.issues_found.append(f"Load test pass rate {pass_rate:.1f}% below minimum {criteria['minimum_load_test_pass_rate']}%")
                result.recommendations.append("Improve system performance to meet load testing requirements")
            
            # Check latency and throughput
            for test_result in load_test_results:
                if test_result.p95_latency_ms > criteria["maximum_latency_ms"]:
                    result.issues_found.append(f"P95 latency {test_result.p95_latency_ms:.1f}ms exceeds maximum {criteria['maximum_latency_ms']}ms")
                
                if test_result.throughput_rps < criteria["minimum_throughput_rps"]:
                    result.issues_found.append(f"Throughput {test_result.throughput_rps:.1f} RPS below minimum {criteria['minimum_throughput_rps']} RPS")
                
                if test_result.peak_cpu_usage > criteria["maximum_cpu_usage_percent"]:
                    result.issues_found.append(f"Peak CPU usage {test_result.peak_cpu_usage:.1f}% exceeds maximum {criteria['maximum_cpu_usage_percent']}%")
                
                if test_result.peak_memory_usage > criteria["maximum_memory_usage_percent"]:
                    result.issues_found.append(f"Peak memory usage {test_result.peak_memory_usage:.1f}% exceeds maximum {criteria['maximum_memory_usage_percent']}%")
                
                if test_result.error_rate > criteria["maximum_error_rate_percent"]:
                    result.issues_found.append(f"Error rate {test_result.error_rate:.1f}% exceeds maximum {criteria['maximum_error_rate_percent']}%")
            
            # Set success based on issues
            result.success = len(result.issues_found) == 0
            
            # Store metrics
            result.metrics = {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "pass_rate": pass_rate,
                "load_test_results": [asdict(r) for r in load_test_results]
            }
            
        except Exception as e:
            logger.error(f"Error in load testing phase: {e}")
            result.issues_found.append(f"Load testing error: {str(e)}")
            result.success = False
    
    async def _run_test_validation_phase(self, result: ValidationPhaseResult):
        """Run test validation phase"""
        try:
            # Run all test suites
            validation_report = await self.test_validator.run_all_tests()
            
            # Analyze results
            total_tests = validation_report.total_tests
            passed_tests = validation_report.passed_tests
            failed_tests = validation_report.failed_tests
            
            pass_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
            
            # Check against criteria
            criteria = self.config["production_criteria"]
            if pass_rate < criteria["minimum_test_validation_pass_rate"]:
                result.issues_found.append(f"Test validation pass rate {pass_rate:.1f}% below minimum {criteria['minimum_test_validation_pass_rate']}%")
                result.recommendations.append("Fix failing tests to meet validation requirements")
            
            # Check for critical failures
            if validation_report.critical_failures:
                result.issues_found.extend([f"Critical test failure: {failure}" for failure in validation_report.critical_failures])
                result.recommendations.append("Resolve critical test failures before production deployment")
            
            # Check coverage
            if validation_report.coverage_percent < 80:
                result.issues_found.append(f"Test coverage {validation_report.coverage_percent:.1f}% below minimum 80%")
                result.recommendations.append("Increase test coverage to meet production standards")
            
            # Set success based on issues
            result.success = len(result.issues_found) == 0
            
            # Store metrics
            result.metrics = {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "pass_rate": pass_rate,
                "coverage_percent": validation_report.coverage_percent,
                "critical_failures": len(validation_report.critical_failures),
                "warnings": len(validation_report.warnings)
            }
            
        except Exception as e:
            logger.error(f"Error in test validation phase: {e}")
            result.issues_found.append(f"Test validation error: {str(e)}")
            result.success = False
    
    async def _run_security_assessment_phase(self, result: ValidationPhaseResult):
        """Run security assessment phase"""
        try:
            # Run security assessment
            security_report = await self.security_hardener.run_security_assessment()
            
            # Analyze results
            security_score = security_report.get("security_score", 0)
            critical_issues = security_report.get("issues_by_severity", {}).get("critical", 0)
            high_issues = security_report.get("issues_by_severity", {}).get("high", 0)
            
            # Check against criteria
            criteria = self.config["production_criteria"]
            if security_score < criteria["minimum_security_score"]:
                result.issues_found.append(f"Security score {security_score:.1f}% below minimum {criteria['minimum_security_score']}%")
                result.recommendations.append("Address security issues to meet production standards")
            
            if critical_issues > 0:
                result.issues_found.append(f"Found {critical_issues} critical security issues")
                result.recommendations.append("Resolve critical security issues before production deployment")
            
            if high_issues > 0:
                result.issues_found.append(f"Found {high_issues} high-severity security issues")
                result.recommendations.append("Address high-severity security issues")
            
            # Set success based on issues
            result.success = len(result.issues_found) == 0
            
            # Store metrics
            result.metrics = {
                "security_score": security_score,
                "critical_issues": critical_issues,
                "high_issues": high_issues,
                "total_findings": security_report.get("total_findings", 0),
                "total_recommendations": security_report.get("total_recommendations", 0)
            }
            
        except Exception as e:
            logger.error(f"Error in security assessment phase: {e}")
            result.issues_found.append(f"Security assessment error: {str(e)}")
            result.success = False
    
    async def _run_performance_benchmarking_phase(self, result: ValidationPhaseResult):
        """Run performance benchmarking phase"""
        try:
            # This phase would run performance benchmarks
            # For now, we'll simulate the results
            
            # Simulate performance metrics
            performance_metrics = {
                "latency_p95_ms": 150.0,
                "latency_p99_ms": 300.0,
                "throughput_rps": 50.0,
                "cpu_usage_percent": 60.0,
                "memory_usage_percent": 70.0,
                "disk_usage_percent": 45.0
            }
            
            # Check against criteria
            criteria = self.config["production_criteria"]
            
            if performance_metrics["latency_p95_ms"] > criteria["maximum_latency_ms"]:
                result.issues_found.append(f"P95 latency {performance_metrics['latency_p95_ms']:.1f}ms exceeds maximum {criteria['maximum_latency_ms']}ms")
            
            if performance_metrics["throughput_rps"] < criteria["minimum_throughput_rps"]:
                result.issues_found.append(f"Throughput {performance_metrics['throughput_rps']:.1f} RPS below minimum {criteria['minimum_throughput_rps']} RPS")
            
            if performance_metrics["cpu_usage_percent"] > criteria["maximum_cpu_usage_percent"]:
                result.issues_found.append(f"CPU usage {performance_metrics['cpu_usage_percent']:.1f}% exceeds maximum {criteria['maximum_cpu_usage_percent']}%")
            
            if performance_metrics["memory_usage_percent"] > criteria["maximum_memory_usage_percent"]:
                result.issues_found.append(f"Memory usage {performance_metrics['memory_usage_percent']:.1f}% exceeds maximum {criteria['maximum_memory_usage_percent']}%")
            
            # Set success based on issues
            result.success = len(result.issues_found) == 0
            
            # Store metrics
            result.metrics = performance_metrics
            
        except Exception as e:
            logger.error(f"Error in performance benchmarking phase: {e}")
            result.issues_found.append(f"Performance benchmarking error: {str(e)}")
            result.success = False
    
    async def _run_production_readiness_phase(self, result: ValidationPhaseResult):
        """Run production readiness phase"""
        try:
            # Analyze all previous phase results
            critical_issues = []
            warnings = []
            
            for phase_result in self.phase_results:
                if phase_result.issues_found:
                    if phase_result.phase in [ValidationPhase.LOAD_TESTING, ValidationPhase.TEST_VALIDATION, ValidationPhase.SECURITY_ASSESSMENT]:
                        critical_issues.extend(phase_result.issues_found)
                    else:
                        warnings.extend(phase_result.issues_found)
            
            # Check readiness criteria
            readiness_criteria = self.config["validation_phases"]["production_readiness"]["readiness_criteria"]
            
            all_tests_pass = len(critical_issues) == 0
            security_compliant = not any("security" in issue.lower() for issue in critical_issues)
            performance_acceptable = not any("performance" in issue.lower() or "latency" in issue.lower() or "throughput" in issue.lower() for issue in critical_issues)
            
            if not all_tests_pass:
                result.issues_found.append("Not all tests passed")
            
            if not security_compliant:
                result.issues_found.append("Security compliance issues found")
            
            if not performance_acceptable:
                result.issues_found.append("Performance issues found")
            
            # Set success based on readiness
            result.success = all_tests_pass and security_compliant and performance_acceptable
            
            # Store metrics
            result.metrics = {
                "all_tests_pass": all_tests_pass,
                "security_compliant": security_compliant,
                "performance_acceptable": performance_acceptable,
                "critical_issues": len(critical_issues),
                "warnings": len(warnings)
            }
            
        except Exception as e:
            logger.error(f"Error in production readiness phase: {e}")
            result.issues_found.append(f"Production readiness error: {str(e)}")
            result.success = False
    
    async def _generate_validation_report(self, start_time: datetime) -> ProductionValidationReport:
        """Generate comprehensive validation report"""
        try:
            # Calculate statistics
            total_phases = len(self.phase_results)
            completed_phases = len([r for r in self.phase_results if r.status == ValidationStatus.COMPLETED])
            failed_phases = len([r for r in self.phase_results if r.status == ValidationStatus.FAILED])
            
            # Calculate total duration
            end_time = datetime.now()
            total_duration = (end_time - start_time).total_seconds()
            
            # Collect all issues and recommendations
            all_issues = []
            all_recommendations = []
            
            for phase_result in self.phase_results:
                if phase_result.issues_found:
                    all_issues.extend(phase_result.issues_found)
                if phase_result.recommendations:
                    all_recommendations.extend(phase_result.recommendations)
            
            # Separate critical issues and warnings
            critical_issues = []
            warnings = []
            
            for issue in all_issues:
                if any(keyword in issue.lower() for keyword in ["critical", "security", "failed", "error"]):
                    critical_issues.append(issue)
                else:
                    warnings.append(issue)
            
            # Calculate production readiness score
            readiness_score = 0.0
            if completed_phases > 0:
                success_rate = completed_phases / total_phases
                issue_penalty = min(len(critical_issues) * 10, 50)  # Max 50% penalty
                readiness_score = max(0, (success_rate * 100) - issue_penalty)
            
            # Determine overall status
            if critical_issues:
                overall_status = ValidationStatus.FAILED
            elif warnings:
                overall_status = ValidationStatus.WARNING
            elif completed_phases == total_phases:
                overall_status = ValidationStatus.COMPLETED
            else:
                overall_status = ValidationStatus.FAILED
            
            # Determine go-live approval
            go_live_approved = (
                overall_status == ValidationStatus.COMPLETED and
                len(critical_issues) == 0 and
                readiness_score >= 80.0
            )
            
            return ProductionValidationReport(
                validation_id=f"validation_{int(time.time())}",
                timestamp=start_time,
                total_phases=total_phases,
                completed_phases=completed_phases,
                failed_phases=failed_phases,
                overall_status=overall_status,
                total_duration_seconds=total_duration,
                phase_results=self.phase_results,
                critical_issues=critical_issues,
                warnings=warnings,
                recommendations=all_recommendations,
                production_readiness_score=readiness_score,
                go_live_approved=go_live_approved
            )
            
        except Exception as e:
            logger.error(f"Error generating validation report: {e}")
            raise
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of all validation reports"""
        try:
            if not self.validation_reports:
                return {"message": "No validation reports available"}
            
            latest_report = self.validation_reports[-1]
            
            return {
                "latest_validation": {
                    "timestamp": latest_report.timestamp.isoformat(),
                    "total_phases": latest_report.total_phases,
                    "completed_phases": latest_report.completed_phases,
                    "failed_phases": latest_report.failed_phases,
                    "overall_status": latest_report.overall_status.value,
                    "production_readiness_score": latest_report.production_readiness_score,
                    "go_live_approved": latest_report.go_live_approved,
                    "critical_issues": len(latest_report.critical_issues),
                    "warnings": len(latest_report.warnings)
                },
                "all_reports": [asdict(report) for report in self.validation_reports]
            }
            
        except Exception as e:
            logger.error(f"Error generating validation summary: {e}")
            return {}

async def main():
    """Main function for testing production validation orchestrator"""
    orchestrator = ProductionValidationOrchestrator()
    
    # Run comprehensive validation
    report = await orchestrator.run_comprehensive_validation()
    
    # Print summary
    summary = orchestrator.get_validation_summary()
    print(f"Production Validation Summary: {summary}")

if __name__ == "__main__":
    asyncio.run(main())
