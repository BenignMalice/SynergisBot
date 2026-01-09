"""
Production Deployment Strategy for Unified Tick Pipeline

This module implements a comprehensive deployment strategy with staging environment,
gradual rollout, and monitoring for production deployment.
"""

import asyncio
import logging
import time
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import shutil
import subprocess
import docker
import requests
import psutil

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# DEPLOYMENT CONFIGURATION
# ============================================================================

class DeploymentConfig:
    """Configuration for deployment strategy"""
    
    # Environment settings
    STAGING_ENV = "staging"
    PRODUCTION_ENV = "production"
    
    # Deployment phases
    PHASES = [
        "infrastructure_setup",
        "staging_deployment",
        "staging_validation",
        "production_preparation",
        "gradual_rollout",
        "monitoring_setup",
        "production_validation"
    ]
    
    # Rollout percentages
    ROLLOUT_PERCENTAGES = [10, 25, 50, 75, 100]
    
    # Monitoring thresholds
    MAX_RESPONSE_TIME = 5.0
    MAX_ERROR_RATE = 0.05
    MAX_CPU_USAGE = 80.0
    MAX_MEMORY_USAGE = 80.0
    
    # Health check intervals
    HEALTH_CHECK_INTERVAL = 30
    MONITORING_INTERVAL = 60

# ============================================================================
# DEPLOYMENT FRAMEWORK
# ============================================================================

class DeploymentManager:
    """Deployment manager with staging and production support"""
    
    def __init__(self):
        self.current_environment = None
        self.deployment_status = {}
        self.monitoring_active = False
        self.rollout_percentage = 0
        
    async def deploy_unified_pipeline(self) -> bool:
        """Deploy Unified Tick Pipeline to production"""
        logger.info("🚀 Starting Unified Tick Pipeline Deployment...")
        
        try:
            # Run deployment phases
            for phase in DeploymentConfig.PHASES:
                logger.info(f"📋 Deployment Phase: {phase}")
                
                phase_result = await self._execute_phase(phase)
                
                if phase_result:
                    logger.info(f"✅ Phase {phase} completed successfully")
                    self.deployment_status[phase] = "completed"
                else:
                    logger.error(f"❌ Phase {phase} failed")
                    self.deployment_status[phase] = "failed"
                    
                    # Attempt rollback if possible
                    if phase in ["staging_deployment", "gradual_rollout"]:
                        logger.info(f"🔄 Attempting rollback for phase {phase}")
                        rollback_result = await self._rollback_phase(phase)
                        if rollback_result:
                            logger.info(f"✅ Rollback successful for phase {phase}")
                        else:
                            logger.error(f"❌ Rollback failed for phase {phase}")
                            return False
                    else:
                        logger.error(f"❌ No rollback available for phase {phase}")
                        return False
            
            # Final validation
            final_result = await self._final_deployment_validation()
            
            if final_result:
                logger.info("🎉 Unified Tick Pipeline deployment completed successfully!")
                return True
            else:
                logger.error("❌ Final deployment validation failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Deployment failed: {e}")
            return False
    
    async def _execute_phase(self, phase: str) -> bool:
        """Execute a specific deployment phase"""
        try:
            if phase == "infrastructure_setup":
                return await self._setup_infrastructure()
            elif phase == "staging_deployment":
                return await self._deploy_to_staging()
            elif phase == "staging_validation":
                return await self._validate_staging()
            elif phase == "production_preparation":
                return await self._prepare_production()
            elif phase == "gradual_rollout":
                return await self._gradual_rollout()
            elif phase == "monitoring_setup":
                return await self._setup_monitoring()
            elif phase == "production_validation":
                return await self._validate_production()
            else:
                logger.error(f"Unknown deployment phase: {phase}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Phase {phase} execution failed: {e}")
            return False
    
    async def _setup_infrastructure(self) -> bool:
        """Setup infrastructure for deployment"""
        try:
            logger.info("🏗️ Setting up infrastructure...")
            
            # Create necessary directories
            directories = [
                "data/unified_tick_pipeline",
                "logs",
                "backups",
                "monitoring"
            ]
            
            for directory in directories:
                os.makedirs(directory, exist_ok=True)
                logger.info(f"✅ Created directory: {directory}")
            
            # Setup Docker if available
            try:
                docker_client = docker.from_env()
                logger.info("✅ Docker client available")
            except Exception:
                logger.warning("⚠️ Docker not available, using local deployment")
            
            # Setup monitoring directories
            monitoring_dirs = [
                "monitoring/metrics",
                "monitoring/logs",
                "monitoring/alerts"
            ]
            
            for directory in monitoring_dirs:
                os.makedirs(directory, exist_ok=True)
                logger.info(f"✅ Created monitoring directory: {directory}")
            
            logger.info("✅ Infrastructure setup completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Infrastructure setup failed: {e}")
            return False
    
    async def _deploy_to_staging(self) -> bool:
        """Deploy to staging environment"""
        try:
            logger.info("🚀 Deploying to staging environment...")
            
            # Set staging environment
            self.current_environment = DeploymentConfig.STAGING_ENV
            
            # Initialize staging pipeline
            from unified_tick_pipeline_integration import initialize_unified_pipeline
            
            start_time = time.time()
            result = await initialize_unified_pipeline()
            initialization_time = time.time() - start_time
            
            if result and initialization_time < 30:
                logger.info(f"✅ Staging deployment completed ({initialization_time:.2f}s)")
                return True
            else:
                logger.error(f"❌ Staging deployment failed ({initialization_time:.2f}s)")
                return False
                
        except Exception as e:
            logger.error(f"❌ Staging deployment failed: {e}")
            return False
    
    async def _validate_staging(self) -> bool:
        """Validate staging deployment"""
        try:
            logger.info("🔍 Validating staging deployment...")
            
            # Test core functionality
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if not pipeline:
                logger.error("❌ Pipeline not available in staging")
                return False
            
            # Test pipeline status
            status = await pipeline.get_pipeline_status()
            if not status:
                logger.error("❌ Pipeline status not available in staging")
                return False
            
            # Test system health
            health = pipeline.get_system_health()
            if not health:
                logger.error("❌ System health not available in staging")
                return False
            
            # Test data feeds
            if hasattr(pipeline, 'binance_feeds'):
                binance_status = pipeline.binance_feeds.get_status()
                if not binance_status.get('is_connected', False):
                    logger.error("❌ Binance feeds not connected in staging")
                    return False
            
            if hasattr(pipeline, 'mt5_bridge'):
                mt5_status = pipeline.mt5_bridge.get_status()
                if not mt5_status.get('is_connected', False):
                    logger.error("❌ MT5 bridge not connected in staging")
                    return False
            
            logger.info("✅ Staging validation completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Staging validation failed: {e}")
            return False
    
    async def _prepare_production(self) -> bool:
        """Prepare for production deployment"""
        try:
            logger.info("🔧 Preparing for production deployment...")
            
            # Create production configuration
            production_config = {
                "environment": "production",
                "monitoring": {
                    "enabled": True,
                    "interval": 60,
                    "thresholds": {
                        "response_time": 5.0,
                        "error_rate": 0.05,
                        "cpu_usage": 80.0,
                        "memory_usage": 80.0
                    }
                },
                "logging": {
                    "level": "INFO",
                    "file": "logs/production.log",
                    "max_size": "100MB",
                    "backup_count": 5
                },
                "backup": {
                    "enabled": True,
                    "interval": "daily",
                    "retention": "30 days"
                }
            }
            
            # Save production configuration
            with open("config/production.json", "w") as f:
                json.dump(production_config, f, indent=2)
            
            logger.info("✅ Production preparation completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Production preparation failed: {e}")
            return False
    
    async def _gradual_rollout(self) -> bool:
        """Perform gradual rollout to production"""
        try:
            logger.info("📈 Starting gradual rollout...")
            
            for percentage in DeploymentConfig.ROLLOUT_PERCENTAGES:
                logger.info(f"📊 Rollout percentage: {percentage}%")
                
                # Simulate gradual rollout
                self.rollout_percentage = percentage
                
                # Test at current percentage
                rollout_result = await self._test_rollout_percentage(percentage)
                
                if rollout_result:
                    logger.info(f"✅ Rollout at {percentage}% successful")
                    
                    # Wait before next percentage
                    if percentage < 100:
                        await asyncio.sleep(30)  # Wait 30 seconds between rollouts
                else:
                    logger.error(f"❌ Rollout at {percentage}% failed")
                    return False
            
            logger.info("✅ Gradual rollout completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Gradual rollout failed: {e}")
            return False
    
    async def _test_rollout_percentage(self, percentage: int) -> bool:
        """Test rollout at specific percentage"""
        try:
            # Simulate testing at rollout percentage
            logger.info(f"🧪 Testing rollout at {percentage}%...")
            
            # Test core functionality
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if not pipeline:
                logger.error(f"❌ Pipeline not available at {percentage}% rollout")
                return False
            
            # Test response time
            start_time = time.time()
            status = await pipeline.get_pipeline_status()
            response_time = time.time() - start_time
            
            if response_time > DeploymentConfig.MAX_RESPONSE_TIME:
                logger.error(f"❌ Response time too high at {percentage}% rollout: {response_time:.2f}s")
                return False
            
            # Test system resources
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_usage = psutil.virtual_memory().percent
            
            if cpu_usage > DeploymentConfig.MAX_CPU_USAGE:
                logger.error(f"❌ CPU usage too high at {percentage}% rollout: {cpu_usage}%")
                return False
            
            if memory_usage > DeploymentConfig.MAX_MEMORY_USAGE:
                logger.error(f"❌ Memory usage too high at {percentage}% rollout: {memory_usage}%")
                return False
            
            logger.info(f"✅ Rollout test passed at {percentage}%")
            return True
            
        except Exception as e:
            logger.error(f"❌ Rollout test failed at {percentage}%: {e}")
            return False
    
    async def _setup_monitoring(self) -> bool:
        """Setup monitoring for production"""
        try:
            logger.info("📊 Setting up monitoring...")
            
            # Create monitoring configuration
            monitoring_config = {
                "enabled": True,
                "interval": DeploymentConfig.MONITORING_INTERVAL,
                "thresholds": {
                    "response_time": DeploymentConfig.MAX_RESPONSE_TIME,
                    "error_rate": DeploymentConfig.MAX_ERROR_RATE,
                    "cpu_usage": DeploymentConfig.MAX_CPU_USAGE,
                    "memory_usage": DeploymentConfig.MAX_MEMORY_USAGE
                },
                "alerts": {
                    "email": True,
                    "webhook": True,
                    "log": True
                }
            }
            
            # Save monitoring configuration
            with open("monitoring/config.json", "w") as f:
                json.dump(monitoring_config, f, indent=2)
            
            # Start monitoring
            self.monitoring_active = True
            asyncio.create_task(self._monitoring_loop())
            
            logger.info("✅ Monitoring setup completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Monitoring setup failed: {e}")
            return False
    
    async def _monitoring_loop(self):
        """Monitoring loop for production"""
        while self.monitoring_active:
            try:
                # Monitor system health
                await self._check_system_health()
                
                # Monitor pipeline health
                await self._check_pipeline_health()
                
                # Monitor performance metrics
                await self._check_performance_metrics()
                
                # Wait for next monitoring cycle
                await asyncio.sleep(DeploymentConfig.MONITORING_INTERVAL)
                
            except Exception as e:
                logger.error(f"❌ Monitoring loop error: {e}")
                await asyncio.sleep(DeploymentConfig.MONITORING_INTERVAL)
    
    async def _check_system_health(self):
        """Check system health"""
        try:
            # Check CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            if cpu_usage > DeploymentConfig.MAX_CPU_USAGE:
                logger.warning(f"⚠️ High CPU usage: {cpu_usage}%")
            
            # Check memory usage
            memory_usage = psutil.virtual_memory().percent
            if memory_usage > DeploymentConfig.MAX_MEMORY_USAGE:
                logger.warning(f"⚠️ High memory usage: {memory_usage}%")
            
            # Check disk usage
            disk_usage = psutil.disk_usage('/').percent
            if disk_usage > 90:
                logger.warning(f"⚠️ High disk usage: {disk_usage}%")
            
        except Exception as e:
            logger.error(f"❌ System health check failed: {e}")
    
    async def _check_pipeline_health(self):
        """Check pipeline health"""
        try:
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if not pipeline:
                logger.error("❌ Pipeline not available for health check")
                return
            
            # Check pipeline status
            status = await pipeline.get_pipeline_status()
            if not status:
                logger.error("❌ Pipeline status not available")
                return
            
            # Check system health
            health = pipeline.get_system_health()
            if not health:
                logger.error("❌ Pipeline health not available")
                return
            
            # Log health status
            logger.info(f"📊 Pipeline health: {health}")
            
        except Exception as e:
            logger.error(f"❌ Pipeline health check failed: {e}")
    
    async def _check_performance_metrics(self):
        """Check performance metrics"""
        try:
            # Check response time
            start_time = time.time()
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if pipeline:
                status = await pipeline.get_pipeline_status()
                response_time = time.time() - start_time
                
                if response_time > DeploymentConfig.MAX_RESPONSE_TIME:
                    logger.warning(f"⚠️ High response time: {response_time:.2f}s")
                else:
                    logger.info(f"📊 Response time: {response_time:.2f}s")
            
        except Exception as e:
            logger.error(f"❌ Performance metrics check failed: {e}")
    
    async def _validate_production(self) -> bool:
        """Validate production deployment"""
        try:
            logger.info("🔍 Validating production deployment...")
            
            # Test core functionality
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if not pipeline:
                logger.error("❌ Pipeline not available in production")
                return False
            
            # Test pipeline status
            status = await pipeline.get_pipeline_status()
            if not status:
                logger.error("❌ Pipeline status not available in production")
                return False
            
            # Test system health
            health = pipeline.get_system_health()
            if not health:
                logger.error("❌ System health not available in production")
                return False
            
            # Test data feeds
            if hasattr(pipeline, 'binance_feeds'):
                binance_status = pipeline.binance_feeds.get_status()
                if not binance_status.get('is_connected', False):
                    logger.error("❌ Binance feeds not connected in production")
                    return False
            
            if hasattr(pipeline, 'mt5_bridge'):
                mt5_status = pipeline.mt5_bridge.get_status()
                if not mt5_status.get('is_connected', False):
                    logger.error("❌ MT5 bridge not connected in production")
                    return False
            
            # Test performance
            start_time = time.time()
            status = await pipeline.get_pipeline_status()
            response_time = time.time() - start_time
            
            if response_time > DeploymentConfig.MAX_RESPONSE_TIME:
                logger.error(f"❌ Production response time too high: {response_time:.2f}s")
                return False
            
            logger.info("✅ Production validation completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Production validation failed: {e}")
            return False
    
    async def _final_deployment_validation(self) -> bool:
        """Final validation of deployment"""
        try:
            logger.info("🔍 Final deployment validation...")
            
            # Check all phases completed
            total_phases = len(DeploymentConfig.PHASES)
            completed_phases = sum(1 for status in self.deployment_status.values() if status == "completed")
            
            if completed_phases != total_phases:
                logger.error(f"❌ Not all phases completed: {completed_phases}/{total_phases}")
                return False
            
            # Test overall system functionality
            from unified_tick_pipeline_integration import get_unified_pipeline
            
            pipeline = get_unified_pipeline()
            if not pipeline:
                logger.error("❌ Final validation failed: Pipeline not available")
                return False
            
            # Test basic functionality
            status = await pipeline.get_pipeline_status()
            if not status:
                logger.error("❌ Final validation failed: Pipeline status not available")
                return False
            
            # Test monitoring
            if not self.monitoring_active:
                logger.error("❌ Final validation failed: Monitoring not active")
                return False
            
            logger.info("✅ Final deployment validation passed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Final deployment validation failed: {e}")
            return False
    
    async def _rollback_phase(self, phase: str) -> bool:
        """Rollback a specific phase"""
        try:
            logger.info(f"🔄 Rolling back phase: {phase}")
            
            # Stop monitoring if active
            if self.monitoring_active:
                self.monitoring_active = False
                logger.info("✅ Monitoring stopped")
            
            # Reset rollout percentage
            self.rollout_percentage = 0
            
            # Reset deployment status
            self.deployment_status[phase] = "rolled_back"
            
            logger.info(f"✅ Rollback completed for phase {phase}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Rollback failed for phase {phase}: {e}")
            return False

# ============================================================================
# DEPLOYMENT RUNNER
# ============================================================================

async def deploy_unified_pipeline():
    """Deploy Unified Tick Pipeline to production"""
    manager = DeploymentManager()
    result = await manager.deploy_unified_pipeline()
    return result

if __name__ == "__main__":
    # Deploy Unified Tick Pipeline
    result = asyncio.run(deploy_unified_pipeline())
    exit(0 if result else 1)
