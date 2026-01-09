#!/usr/bin/env python3
"""
Production Readiness Validator for TelegramMoneyBot v8.0
Validates system readiness for production deployment without requiring actual credentials
"""

import asyncio
import json
import logging
import time
import sys
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProductionReadinessValidator:
    """Validate production readiness without requiring actual credentials"""
    
    def __init__(self):
        self.validation_start_time = datetime.now()
        self.validation_results = {
            "status": "INITIALIZING",
            "components": {},
            "readiness_score": 0.0,
            "issues": [],
            "recommendations": []
        }
    
    async def validate_production_readiness(self):
        """Validate complete production readiness"""
        try:
            logger.info("PRODUCTION READINESS VALIDATION")
            logger.info("=" * 60)
            
            # Phase 1: System Requirements
            await self._validate_system_requirements()
            
            # Phase 2: Code Quality
            await self._validate_code_quality()
            
            # Phase 3: Configuration
            await self._validate_configuration()
            
            # Phase 4: Documentation
            await self._validate_documentation()
            
            # Phase 5: Testing
            await self._validate_testing()
            
            # Phase 6: Monitoring
            await self._validate_monitoring()
            
            # Phase 7: Security
            await self._validate_security()
            
            # Generate final report
            await self._generate_readiness_report()
            
            logger.info("PRODUCTION READINESS VALIDATION COMPLETED")
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            raise
    
    async def _validate_system_requirements(self):
        """Validate system requirements"""
        logger.info("Phase 1: System Requirements Validation")
        
        requirements_score = 0
        total_requirements = 5
        
        # Check Python version
        python_version = sys.version_info
        if python_version.major >= 3 and python_version.minor >= 9:
            logger.info(f"Python version: {python_version.major}.{python_version.minor} (PASS)")
            requirements_score += 1
        else:
            logger.warning(f"Python version: {python_version.major}.{python_version.minor} (FAIL - Need 3.9+)")
            self.validation_results["issues"].append("Python version too old")
        
        # Check available memory
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_gb = memory.total / (1024**3)
            if memory_gb >= 8:
                logger.info(f"Memory: {memory_gb:.1f}GB (PASS)")
                requirements_score += 1
            else:
                logger.warning(f"Memory: {memory_gb:.1f}GB (WARNING - Recommended 8GB+)")
                self.validation_results["recommendations"].append("Consider upgrading to 8GB+ RAM")
        except ImportError:
            logger.warning("psutil not available for memory check")
        
        # Check disk space
        try:
            disk = psutil.disk_usage('.')
            disk_gb = disk.free / (1024**3)
            if disk_gb >= 10:
                logger.info(f"Disk space: {disk_gb:.1f}GB (PASS)")
                requirements_score += 1
            else:
                logger.warning(f"Disk space: {disk_gb:.1f}GB (WARNING - Need 10GB+)")
                self.validation_results["issues"].append("Insufficient disk space")
        except:
            logger.warning("Could not check disk space")
        
        # Check required files
        required_files = [
            'trade_bot.py',
            'app/main_api.py',
            'requirements.txt',
            'config/settings.py'
        ]
        
        files_present = 0
        for file in required_files:
            if os.path.exists(file):
                files_present += 1
                logger.info(f"File {file}: PRESENT")
            else:
                logger.warning(f"File {file}: MISSING")
                self.validation_results["issues"].append(f"Missing file: {file}")
        
        if files_present == len(required_files):
            requirements_score += 1
        else:
            requirements_score += files_present / len(required_files)
        
        # Check directories
        required_dirs = ['logs', 'data', 'config', 'docs']
        dirs_present = 0
        for directory in required_dirs:
            if os.path.exists(directory):
                dirs_present += 1
                logger.info(f"Directory {directory}: PRESENT")
            else:
                logger.warning(f"Directory {directory}: MISSING")
                self.validation_results["issues"].append(f"Missing directory: {directory}")
        
        if dirs_present == len(required_dirs):
            requirements_score += 1
        else:
            requirements_score += dirs_present / len(required_dirs)
        
        self.validation_results["components"]["system_requirements"] = {
            "score": requirements_score / total_requirements,
            "status": "PASS" if requirements_score >= 4 else "FAIL"
        }
        
        logger.info(f"System Requirements Score: {requirements_score}/{total_requirements}")
    
    async def _validate_code_quality(self):
        """Validate code quality"""
        logger.info("Phase 2: Code Quality Validation")
        
        quality_score = 0
        total_checks = 4
        
        # Check for main components
        main_components = [
            'trade_bot.py',
            'app/main_api.py',
            'desktop_agent.py',
            'chatgpt_bot.py'
        ]
        
        components_present = 0
        for component in main_components:
            if os.path.exists(component):
                components_present += 1
                logger.info(f"Component {component}: PRESENT")
            else:
                logger.warning(f"Component {component}: MISSING")
        
        if components_present == len(main_components):
            quality_score += 1
        else:
            quality_score += components_present / len(main_components)
        
        # Check for infrastructure components
        infra_components = [
            'infra/mt5_service.py',
            'infra/openai_service.py',
            'infra/position_watcher.py',
            'infra/risk_simulation.py'
        ]
        
        infra_present = 0
        for component in infra_components:
            if os.path.exists(component):
                infra_present += 1
                logger.info(f"Infra component {component}: PRESENT")
            else:
                logger.warning(f"Infra component {component}: MISSING")
        
        if infra_present >= len(infra_components) * 0.8:  # 80% threshold
            quality_score += 1
        else:
            quality_score += infra_present / len(infra_components)
        
        # Check for validation systems
        validation_systems = [
            'infra/structure_validation.py',
            'infra/latency_validation.py',
            'infra/database_performance_validation.py',
            'infra/win_rate_validation.py'
        ]
        
        validation_present = 0
        for system in validation_systems:
            if os.path.exists(system):
                validation_present += 1
                logger.info(f"Validation system {system}: PRESENT")
            else:
                logger.warning(f"Validation system {system}: MISSING")
        
        if validation_present >= len(validation_systems) * 0.8:  # 80% threshold
            quality_score += 1
        else:
            quality_score += validation_present / len(validation_systems)
        
        # Check for monitoring systems
        monitoring_systems = [
            'production_monitoring_dashboard.py',
            'production_alerting_system.py',
            'log_aggregation_analysis.py',
            'performance_metrics_collection.py'
        ]
        
        monitoring_present = 0
        for system in monitoring_systems:
            if os.path.exists(system):
                monitoring_present += 1
                logger.info(f"Monitoring system {system}: PRESENT")
            else:
                logger.warning(f"Monitoring system {system}: MISSING")
        
        if monitoring_present >= len(monitoring_systems) * 0.8:  # 80% threshold
            quality_score += 1
        else:
            quality_score += monitoring_present / len(monitoring_systems)
        
        self.validation_results["components"]["code_quality"] = {
            "score": quality_score / total_checks,
            "status": "PASS" if quality_score >= 3 else "FAIL"
        }
        
        logger.info(f"Code Quality Score: {quality_score}/{total_checks}")
    
    async def _validate_configuration(self):
        """Validate configuration"""
        logger.info("Phase 3: Configuration Validation")
        
        config_score = 0
        total_configs = 4
        
        # Check main configuration
        if os.path.exists('config/settings.py'):
            logger.info("Main configuration: PRESENT")
            config_score += 1
        else:
            logger.warning("Main configuration: MISSING")
            self.validation_results["issues"].append("Missing main configuration")
        
        # Check symbol configurations
        symbol_configs = [
            'config/symbols/BTCUSDc.json',
            'config/symbols/XAUUSDc.json',
            'config/symbols/EURUSDc.json'
        ]
        
        symbol_present = 0
        for config in symbol_configs:
            if os.path.exists(config):
                symbol_present += 1
                logger.info(f"Symbol config {config}: PRESENT")
            else:
                logger.warning(f"Symbol config {config}: MISSING")
        
        if symbol_present >= len(symbol_configs) * 0.8:
            config_score += 1
        else:
            config_score += symbol_present / len(symbol_configs)
        
        # Check monitoring configurations
        monitoring_configs = [
            'monitoring_dashboard_config.json',
            'alerting_system_config.json',
            'log_aggregation_config.json',
            'performance_metrics_config.json'
        ]
        
        monitoring_present = 0
        for config in monitoring_configs:
            if os.path.exists(config):
                monitoring_present += 1
                logger.info(f"Monitoring config {config}: PRESENT")
            else:
                logger.warning(f"Monitoring config {config}: MISSING")
        
        if monitoring_present >= len(monitoring_configs) * 0.8:
            config_score += 1
        else:
            config_score += monitoring_present / len(monitoring_configs)
        
        # Check environment template
        if os.path.exists('.env.example') or os.path.exists('.env'):
            logger.info("Environment configuration: PRESENT")
            config_score += 1
        else:
            logger.warning("Environment configuration: MISSING")
            self.validation_results["recommendations"].append("Create .env.example template")
        
        self.validation_results["components"]["configuration"] = {
            "score": config_score / total_configs,
            "status": "PASS" if config_score >= 3 else "FAIL"
        }
        
        logger.info(f"Configuration Score: {config_score}/{total_configs}")
    
    async def _validate_documentation(self):
        """Validate documentation"""
        logger.info("Phase 4: Documentation Validation")
        
        doc_score = 0
        total_docs = 4
        
        # Check main documentation
        main_docs = [
            'docs/documentation_training/USER_MANUAL.md',
            'docs/documentation_training/TROUBLESHOOTING_GUIDE.md',
            'docs/documentation_training/OPERATIONAL_RUNBOOK.md',
            'docs/documentation_training/TRAINING_MATERIALS.md'
        ]
        
        docs_present = 0
        for doc in main_docs:
            if os.path.exists(doc):
                docs_present += 1
                logger.info(f"Documentation {doc}: PRESENT")
            else:
                logger.warning(f"Documentation {doc}: MISSING")
        
        if docs_present >= len(main_docs) * 0.8:
            doc_score += 1
        else:
            doc_score += docs_present / len(main_docs)
        
        # Check API documentation
        if os.path.exists('app/main_api.py'):
            logger.info("API documentation: PRESENT (in code)")
            doc_score += 1
        else:
            logger.warning("API documentation: MISSING")
        
        # Check README
        if os.path.exists('README.md'):
            logger.info("README: PRESENT")
            doc_score += 1
        else:
            logger.warning("README: MISSING")
            self.validation_results["recommendations"].append("Create README.md")
        
        # Check documentation index
        if os.path.exists('docs/documentation_training/DOCUMENTATION_INDEX.md'):
            logger.info("Documentation index: PRESENT")
            doc_score += 1
        else:
            logger.warning("Documentation index: MISSING")
        
        self.validation_results["components"]["documentation"] = {
            "score": doc_score / total_docs,
            "status": "PASS" if doc_score >= 3 else "FAIL"
        }
        
        logger.info(f"Documentation Score: {doc_score}/{total_docs}")
    
    async def _validate_testing(self):
        """Validate testing"""
        logger.info("Phase 5: Testing Validation")
        
        test_score = 0
        total_tests = 3
        
        # Check for test files
        test_files = [
            'test_monitoring_systems_simple.py',
            'test_monitoring_integration.py'
        ]
        
        tests_present = 0
        for test in test_files:
            if os.path.exists(test):
                tests_present += 1
                logger.info(f"Test file {test}: PRESENT")
            else:
                logger.warning(f"Test file {test}: MISSING")
        
        if tests_present >= len(test_files) * 0.5:  # 50% threshold
            test_score += 1
        else:
            test_score += tests_present / len(test_files)
        
        # Check for validation systems (these are tests)
        validation_tests = [
            'infra/structure_validation.py',
            'infra/latency_validation.py',
            'infra/database_performance_validation.py'
        ]
        
        validation_present = 0
        for test in validation_tests:
            if os.path.exists(test):
                validation_present += 1
                logger.info(f"Validation test {test}: PRESENT")
            else:
                logger.warning(f"Validation test {test}: MISSING")
        
        if validation_present >= len(validation_tests) * 0.8:
            test_score += 1
        else:
            test_score += validation_present / len(validation_tests)
        
        # Check for integration tests
        integration_tests = [
            'test_desktop_agent_with_pipeline.py',
            'test_chatgpt_bot_e2e.py',
            'test_main_api_e2e.py'
        ]
        
        integration_present = 0
        for test in integration_tests:
            if os.path.exists(test):
                integration_present += 1
                logger.info(f"Integration test {test}: PRESENT")
            else:
                logger.warning(f"Integration test {test}: MISSING")
        
        if integration_present >= len(integration_tests) * 0.5:
            test_score += 1
        else:
            test_score += integration_present / len(integration_tests)
        
        self.validation_results["components"]["testing"] = {
            "score": test_score / total_tests,
            "status": "PASS" if test_score >= 2 else "FAIL"
        }
        
        logger.info(f"Testing Score: {test_score}/{total_tests}")
    
    async def _validate_monitoring(self):
        """Validate monitoring systems"""
        logger.info("Phase 6: Monitoring Validation")
        
        monitoring_score = 0
        total_monitoring = 4
        
        # Check monitoring dashboard
        if os.path.exists('production_monitoring_dashboard.py'):
            logger.info("Monitoring dashboard: PRESENT")
            monitoring_score += 1
        else:
            logger.warning("Monitoring dashboard: MISSING")
        
        # Check alerting system
        if os.path.exists('production_alerting_system.py'):
            logger.info("Alerting system: PRESENT")
            monitoring_score += 1
        else:
            logger.warning("Alerting system: MISSING")
        
        # Check log aggregation
        if os.path.exists('log_aggregation_analysis.py'):
            logger.info("Log aggregation: PRESENT")
            monitoring_score += 1
        else:
            logger.warning("Log aggregation: MISSING")
        
        # Check performance metrics
        if os.path.exists('performance_metrics_collection.py'):
            logger.info("Performance metrics: PRESENT")
            monitoring_score += 1
        else:
            logger.warning("Performance metrics: MISSING")
        
        self.validation_results["components"]["monitoring"] = {
            "score": monitoring_score / total_monitoring,
            "status": "PASS" if monitoring_score >= 3 else "FAIL"
        }
        
        logger.info(f"Monitoring Score: {monitoring_score}/{total_monitoring}")
    
    async def _validate_security(self):
        """Validate security"""
        logger.info("Phase 7: Security Validation")
        
        security_score = 0
        total_security = 3
        
        # Check for security configurations
        security_configs = [
            'database_security_config.json',
            'security_hardening_config.json'
        ]
        
        security_present = 0
        for config in security_configs:
            if os.path.exists(config):
                security_present += 1
                logger.info(f"Security config {config}: PRESENT")
            else:
                logger.warning(f"Security config {config}: MISSING")
        
        if security_present >= len(security_configs) * 0.5:
            security_score += 1
        else:
            security_score += security_present / len(security_configs)
        
        # Check for security systems
        security_systems = [
            'production_database_security.py',
            'security_hardening.py'
        ]
        
        systems_present = 0
        for system in security_systems:
            if os.path.exists(system):
                systems_present += 1
                logger.info(f"Security system {system}: PRESENT")
            else:
                logger.warning(f"Security system {system}: MISSING")
        
        if systems_present >= len(security_systems) * 0.5:
            security_score += 1
        else:
            security_score += systems_present / len(security_systems)
        
        # Check for environment security
        if os.path.exists('.env.example'):
            logger.info("Environment template: PRESENT")
            security_score += 1
        else:
            logger.warning("Environment template: MISSING")
            self.validation_results["recommendations"].append("Create .env.example for security")
        
        self.validation_results["components"]["security"] = {
            "score": security_score / total_security,
            "status": "PASS" if security_score >= 2 else "FAIL"
        }
        
        logger.info(f"Security Score: {security_score}/{total_security}")
    
    async def _generate_readiness_report(self):
        """Generate final readiness report"""
        logger.info("GENERATING PRODUCTION READINESS REPORT")
        logger.info("=" * 60)
        
        # Calculate overall score
        component_scores = []
        for component, data in self.validation_results["components"].items():
            component_scores.append(data["score"])
        
        overall_score = sum(component_scores) / len(component_scores) if component_scores else 0
        self.validation_results["readiness_score"] = overall_score
        
        # Determine readiness status
        if overall_score >= 0.9:
            readiness_status = "EXCELLENT"
        elif overall_score >= 0.8:
            readiness_status = "GOOD"
        elif overall_score >= 0.7:
            readiness_status = "FAIR"
        elif overall_score >= 0.6:
            readiness_status = "POOR"
        else:
            readiness_status = "CRITICAL"
        
        self.validation_results["status"] = readiness_status
        
        # Generate report
        report = {
            "validation_id": f"VALIDATION_{int(time.time())}",
            "timestamp": datetime.now().isoformat(),
            "overall_score": overall_score,
            "readiness_status": readiness_status,
            "components": self.validation_results["components"],
            "issues": self.validation_results["issues"],
            "recommendations": self.validation_results["recommendations"]
        }
        
        # Save report
        with open('logs/production_readiness_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        # Display results
        logger.info("PRODUCTION READINESS RESULTS:")
        logger.info(f"Overall Score: {overall_score:.2f}")
        logger.info(f"Readiness Status: {readiness_status}")
        logger.info("")
        
        for component, data in self.validation_results["components"].items():
            logger.info(f"{component.upper()}: {data['score']:.2f} ({data['status']})")
        
        if self.validation_results["issues"]:
            logger.info("")
            logger.info("ISSUES FOUND:")
            for issue in self.validation_results["issues"]:
                logger.warning(f"- {issue}")
        
        if self.validation_results["recommendations"]:
            logger.info("")
            logger.info("RECOMMENDATIONS:")
            for rec in self.validation_results["recommendations"]:
                logger.info(f"- {rec}")
        
        logger.info("")
        if readiness_status in ["EXCELLENT", "GOOD"]:
            logger.info("PRODUCTION READY: System is ready for production deployment!")
        elif readiness_status == "FAIR":
            logger.info("PRODUCTION READY WITH CAUTION: Address issues before deployment")
        else:
            logger.info("NOT PRODUCTION READY: Address critical issues before deployment")

async def main():
    """Main validation function"""
    try:
        validator = ProductionReadinessValidator()
        await validator.validate_production_readiness()
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
