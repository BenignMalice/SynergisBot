#!/usr/bin/env python3
"""
Deployment Scripts for TelegramMoneyBot v8.0
Automated deployment and rollback scripts for production
"""

import asyncio
import json
import subprocess
import shutil
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import psutil
import requests
import sqlite3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeploymentStatus(Enum):
    """Deployment status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"

class ServiceStatus(Enum):
    """Service status"""
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    UNKNOWN = "unknown"

@dataclass
class DeploymentConfig:
    """Deployment configuration"""
    version: str
    environment: str
    services: Dict[str, Dict[str, Any]]
    databases: List[str]
    backup_enabled: bool = True
    rollback_enabled: bool = True
    health_check_timeout: int = 300
    deployment_timeout: int = 1800

@dataclass
class ServiceInfo:
    """Service information"""
    name: str
    status: ServiceStatus
    pid: Optional[int] = None
    port: Optional[int] = None
    health_url: Optional[str] = None
    restart_count: int = 0
    last_restart: Optional[float] = None

@dataclass
class DeploymentResult:
    """Deployment result"""
    deployment_id: str
    status: DeploymentStatus
    start_time: float
    end_time: Optional[float] = None
    services_deployed: List[str] = None
    services_failed: List[str] = None
    error_message: Optional[str] = None
    rollback_performed: bool = False

class DeploymentManager:
    """Manages deployment operations"""
    
    def __init__(self, config_path: str = "deployment_config.json"):
        self.config = self._load_config(config_path)
        self.services: Dict[str, ServiceInfo] = {}
        self.deployment_history: List[DeploymentResult] = []
        self.current_deployment: Optional[DeploymentResult] = None
        
        # Initialize service tracking
        self._initialize_services()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load deployment configuration"""
        default_config = {
            "environments": {
                "production": {
                    "host": "localhost",
                    "port_base": 8000,
                    "backup_enabled": True,
                    "rollback_enabled": True,
                    "health_check_timeout": 300,
                    "deployment_timeout": 1800
                },
                "staging": {
                    "host": "staging.localhost",
                    "port_base": 9000,
                    "backup_enabled": True,
                    "rollback_enabled": True,
                    "health_check_timeout": 180,
                    "deployment_timeout": 900
                }
            },
            "services": {
                "main_api": {
                    "command": "python -m uvicorn app.main_api:app --host 0.0.0.0 --port {port}",
                    "port_offset": 0,
                    "health_endpoint": "/health",
                    "restart_command": "python -m uvicorn app.main_api:app --host 0.0.0.0 --port {port}",
                    "stop_command": "pkill -f 'uvicorn app.main_api'",
                    "required": True
                },
                "chatgpt_bot": {
                    "command": "python chatgpt_bot.py",
                    "port_offset": 1,
                    "health_endpoint": "/health",
                    "restart_command": "python chatgpt_bot.py",
                    "stop_command": "pkill -f 'chatgpt_bot.py'",
                    "required": True
                },
                "desktop_agent": {
                    "command": "python desktop_agent.py",
                    "port_offset": 2,
                    "health_endpoint": "/health",
                    "restart_command": "python desktop_agent.py",
                    "stop_command": "pkill -f 'desktop_agent.py'",
                    "required": True
                }
            },
            "databases": [
                "data/unified_tick_pipeline.db",
                "data/analysis_data.db",
                "data/system_logs.db",
                "data/journal.sqlite"
            ],
            "backup_directories": {
                "code": "backups/code",
                "database": "backups/database",
                "config": "backups/config"
            },
            "deployment_scripts": {
                "pre_deploy": "scripts/pre_deploy.sh",
                "post_deploy": "scripts/post_deploy.sh",
                "pre_rollback": "scripts/pre_rollback.sh",
                "post_rollback": "scripts/post_rollback.sh"
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
            logger.error(f"Error loading deployment config: {e}")
            return default_config
    
    def _initialize_services(self):
        """Initialize service tracking"""
        for service_name in self.config["services"].keys():
            self.services[service_name] = ServiceInfo(
                name=service_name,
                status=ServiceStatus.UNKNOWN
            )
    
    async def deploy(self, version: str, environment: str = "production", 
                    force: bool = False) -> DeploymentResult:
        """Deploy a new version"""
        deployment_id = f"deploy_{int(time.time())}"
        
        # Create deployment result
        self.current_deployment = DeploymentResult(
            deployment_id=deployment_id,
            status=DeploymentStatus.IN_PROGRESS,
            start_time=time.time(),
            services_deployed=[],
            services_failed=[]
        )
        
        self.deployment_history.append(self.current_deployment)
        
        logger.info(f"Starting deployment {deployment_id} (version: {version}, environment: {environment})")
        
        try:
            # Pre-deployment checks
            if not await self._pre_deployment_checks(version, environment, force):
                self.current_deployment.status = DeploymentStatus.FAILED
                self.current_deployment.error_message = "Pre-deployment checks failed"
                return self.current_deployment
            
            # Create backup
            if self.config["environments"][environment]["backup_enabled"]:
                await self._create_backup(deployment_id, environment)
            
            # Stop services
            await self._stop_services(environment)
            
            # Deploy code
            await self._deploy_code(version, environment)
            
            # Update configuration
            await self._update_configuration(version, environment)
            
            # Start services
            await self._start_services(version, environment)
            
            # Health checks
            if not await self._health_checks(environment):
                logger.error("Health checks failed, initiating rollback")
                await self._rollback_deployment(deployment_id, environment)
                self.current_deployment.status = DeploymentStatus.ROLLED_BACK
                return self.current_deployment
            
            # Post-deployment tasks
            await self._post_deployment_tasks(version, environment)
            
            # Mark deployment as completed
            self.current_deployment.status = DeploymentStatus.COMPLETED
            self.current_deployment.end_time = time.time()
            
            logger.info(f"Deployment {deployment_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Deployment {deployment_id} failed: {e}")
            self.current_deployment.status = DeploymentStatus.FAILED
            self.current_deployment.error_message = str(e)
            self.current_deployment.end_time = time.time()
            
            # Attempt rollback if enabled
            if self.config["environments"][environment]["rollback_enabled"]:
                try:
                    await self._rollback_deployment(deployment_id, environment)
                    self.current_deployment.rollback_performed = True
                except Exception as rollback_error:
                    logger.error(f"Rollback failed: {rollback_error}")
        
        return self.current_deployment
    
    async def _pre_deployment_checks(self, version: str, environment: str, force: bool) -> bool:
        """Run pre-deployment checks"""
        logger.info("Running pre-deployment checks...")
        
        try:
            # Check if version exists
            if not await self._check_version_exists(version):
                logger.error(f"Version {version} not found")
                return False
            
            # Check system resources
            if not await self._check_system_resources():
                logger.error("Insufficient system resources")
                return False
            
            # Check database connectivity
            if not await self._check_database_connectivity():
                logger.error("Database connectivity check failed")
                return False
            
            # Check if services are running (unless force)
            if not force and not await self._check_services_running():
                logger.error("Services are not running properly")
                return False
            
            # Run pre-deployment script
            if not await self._run_deployment_script("pre_deploy", environment):
                logger.error("Pre-deployment script failed")
                return False
            
            logger.info("Pre-deployment checks passed")
            return True
            
        except Exception as e:
            logger.error(f"Pre-deployment checks failed: {e}")
            return False
    
    async def _check_version_exists(self, version: str) -> bool:
        """Check if version exists"""
        # In a real implementation, this would check a version repository
        # For now, we'll assume the version exists
        return True
    
    async def _check_system_resources(self) -> bool:
        """Check system resources"""
        try:
            # Check CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            if cpu_usage > 90:
                logger.warning(f"High CPU usage: {cpu_usage}%")
                return False
            
            # Check memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                logger.warning(f"High memory usage: {memory.percent}%")
                return False
            
            # Check disk space
            disk = psutil.disk_usage('/')
            if disk.percent > 90:
                logger.warning(f"High disk usage: {disk.percent}%")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking system resources: {e}")
            return False
    
    async def _check_database_connectivity(self) -> bool:
        """Check database connectivity"""
        try:
            for db_path in self.config["databases"]:
                if Path(db_path).exists():
                    with sqlite3.connect(db_path) as conn:
                        conn.execute("SELECT 1")
                else:
                    logger.warning(f"Database file not found: {db_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Database connectivity check failed: {e}")
            return False
    
    async def _check_services_running(self) -> bool:
        """Check if services are running"""
        try:
            for service_name, service_config in self.config["services"].items():
                if service_config.get("required", False):
                    port = self._get_service_port(service_name)
                    health_url = f"http://localhost:{port}{service_config.get('health_endpoint', '/health')}"
                    
                    try:
                        response = requests.get(health_url, timeout=5)
                        if response.status_code != 200:
                            logger.warning(f"Service {service_name} health check failed")
                            return False
                    except Exception:
                        logger.warning(f"Service {service_name} is not responding")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking services: {e}")
            return False
    
    async def _run_deployment_script(self, script_type: str, environment: str) -> bool:
        """Run deployment script"""
        try:
            script_path = self.config["deployment_scripts"].get(script_type)
            if not script_path or not Path(script_path).exists():
                logger.info(f"No {script_type} script found, skipping")
                return True
            
            # Make script executable
            Path(script_path).chmod(0o755)
            
            # Run script
            result = subprocess.run(
                [script_path, environment],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                logger.error(f"{script_type} script failed: {result.stderr}")
                return False
            
            logger.info(f"{script_type} script completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error running {script_type} script: {e}")
            return False
    
    async def _create_backup(self, deployment_id: str, environment: str):
        """Create backup before deployment"""
        logger.info("Creating backup...")
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create backup directories
            for backup_type, base_path in self.config["backup_directories"].items():
                backup_dir = Path(base_path) / f"{deployment_id}_{timestamp}"
                backup_dir.mkdir(parents=True, exist_ok=True)
                
                if backup_type == "code":
                    # Backup code files
                    code_files = [
                        "chatgpt_bot.py",
                        "desktop_agent.py",
                        "app/main_api.py",
                        "requirements.txt"
                    ]
                    
                    for file_path in code_files:
                        if Path(file_path).exists():
                            shutil.copy2(file_path, backup_dir / Path(file_path).name)
                    
                    # Backup directories
                    dirs_to_backup = ["app", "infra", "config", "domain", "handlers"]
                    for dir_path in dirs_to_backup:
                        if Path(dir_path).exists():
                            shutil.copytree(dir_path, backup_dir / dir_path)
                
                elif backup_type == "database":
                    # Backup databases
                    for db_path in self.config["databases"]:
                        if Path(db_path).exists():
                            shutil.copy2(db_path, backup_dir / Path(db_path).name)
                
                elif backup_type == "config":
                    # Backup configuration files
                    config_files = [
                        "config/settings.py",
                        "deployment_config.json",
                        "production_config.json"
                    ]
                    
                    for config_file in config_files:
                        if Path(config_file).exists():
                            shutil.copy2(config_file, backup_dir / Path(config_file).name)
            
            logger.info("Backup created successfully")
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            raise
    
    async def _stop_services(self, environment: str):
        """Stop all services"""
        logger.info("Stopping services...")
        
        for service_name, service_config in self.config["services"].items():
            try:
                stop_command = service_config.get("stop_command")
                if stop_command:
                    result = subprocess.run(
                        stop_command.split(),
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    if result.returncode == 0:
                        logger.info(f"Service {service_name} stopped")
                    else:
                        logger.warning(f"Service {service_name} stop command failed: {result.stderr}")
                
                # Update service status
                self.services[service_name].status = ServiceStatus.STOPPED
                
            except Exception as e:
                logger.error(f"Error stopping service {service_name}: {e}")
    
    async def _deploy_code(self, version: str, environment: str):
        """Deploy new code"""
        logger.info(f"Deploying code version {version}...")
        
        try:
            # In a real implementation, this would:
            # 1. Download the version from a repository
            # 2. Extract the code
            # 3. Replace existing files
            
            # For now, we'll simulate the deployment
            await asyncio.sleep(2)  # Simulate deployment time
            
            logger.info("Code deployment completed")
            
        except Exception as e:
            logger.error(f"Error deploying code: {e}")
            raise
    
    async def _update_configuration(self, version: str, environment: str):
        """Update configuration for new version"""
        logger.info("Updating configuration...")
        
        try:
            # Update environment-specific configuration
            env_config = self.config["environments"][environment]
            
            # Update service ports
            for service_name, service_config in self.config["services"].items():
                port_offset = service_config.get("port_offset", 0)
                port = env_config["port_base"] + port_offset
                service_config["port"] = port
            
            logger.info("Configuration updated")
            
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            raise
    
    async def _start_services(self, version: str, environment: str):
        """Start all services"""
        logger.info("Starting services...")
        
        for service_name, service_config in self.config["services"].items():
            try:
                port = self._get_service_port(service_name)
                command = service_config["command"].format(port=port)
                
                # Start service
                process = subprocess.Popen(
                    command.split(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Update service info
                self.services[service_name].pid = process.pid
                self.services[service_name].port = port
                self.services[service_name].status = ServiceStatus.RUNNING
                self.services[service_name].last_restart = time.time()
                
                logger.info(f"Service {service_name} started (PID: {process.pid}, Port: {port})")
                
                # Add to deployed services
                if self.current_deployment:
                    self.current_deployment.services_deployed.append(service_name)
                
            except Exception as e:
                logger.error(f"Error starting service {service_name}: {e}")
                if self.current_deployment:
                    self.current_deployment.services_failed.append(service_name)
    
    def _get_service_port(self, service_name: str) -> int:
        """Get service port"""
        service_config = self.config["services"][service_name]
        port_offset = service_config.get("port_offset", 0)
        environment = "production"  # Default environment
        port_base = self.config["environments"][environment]["port_base"]
        return port_base + port_offset
    
    async def _health_checks(self, environment: str) -> bool:
        """Run health checks on all services"""
        logger.info("Running health checks...")
        
        timeout = self.config["environments"][environment]["health_check_timeout"]
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            all_healthy = True
            
            for service_name, service_config in self.config["services"].items():
                if service_config.get("required", False):
                    if not await self._check_service_health(service_name):
                        all_healthy = False
                        break
            
            if all_healthy:
                logger.info("All services are healthy")
                return True
            
            await asyncio.sleep(10)  # Wait 10 seconds before retry
        
        logger.error("Health checks timed out")
        return False
    
    async def _check_service_health(self, service_name: str) -> bool:
        """Check individual service health"""
        try:
            service_config = self.config["services"][service_name]
            port = self._get_service_port(service_name)
            health_url = f"http://localhost:{port}{service_config.get('health_endpoint', '/health')}"
            
            response = requests.get(health_url, timeout=5)
            return response.status_code == 200
            
        except Exception as e:
            logger.warning(f"Health check failed for {service_name}: {e}")
            return False
    
    async def _post_deployment_tasks(self, version: str, environment: str):
        """Run post-deployment tasks"""
        logger.info("Running post-deployment tasks...")
        
        try:
            # Run post-deployment script
            await self._run_deployment_script("post_deploy", environment)
            
            # Update deployment metadata
            await self._update_deployment_metadata(version, environment)
            
            logger.info("Post-deployment tasks completed")
            
        except Exception as e:
            logger.error(f"Error in post-deployment tasks: {e}")
            raise
    
    async def _update_deployment_metadata(self, version: str, environment: str):
        """Update deployment metadata"""
        try:
            metadata = {
                "version": version,
                "environment": environment,
                "deployed_at": time.time(),
                "deployed_by": "deployment_system",
                "services": {name: asdict(service) for name, service in self.services.items()}
            }
            
            metadata_file = f"deployment_metadata_{environment}.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            
        except Exception as e:
            logger.error(f"Error updating deployment metadata: {e}")
    
    async def _rollback_deployment(self, deployment_id: str, environment: str):
        """Rollback deployment"""
        logger.info(f"Rolling back deployment {deployment_id}...")
        
        try:
            # Run pre-rollback script
            await self._run_deployment_script("pre_rollback", environment)
            
            # Stop current services
            await self._stop_services(environment)
            
            # Restore from backup
            await self._restore_from_backup(deployment_id, environment)
            
            # Start services
            await self._start_services("previous", environment)
            
            # Run post-rollback script
            await self._run_deployment_script("post_rollback", environment)
            
            logger.info("Rollback completed")
            
        except Exception as e:
            logger.error(f"Error during rollback: {e}")
            raise
    
    async def _restore_from_backup(self, deployment_id: str, environment: str):
        """Restore from backup"""
        logger.info("Restoring from backup...")
        
        try:
            # Find the most recent backup for this deployment
            backup_dirs = []
            for backup_type, base_path in self.config["backup_directories"].items():
                backup_base = Path(base_path)
                if backup_base.exists():
                    for backup_dir in backup_base.iterdir():
                        if backup_dir.name.startswith(deployment_id):
                            backup_dirs.append(backup_dir)
            
            if not backup_dirs:
                logger.error("No backup found for rollback")
                return
            
            # Use the most recent backup
            latest_backup = max(backup_dirs, key=lambda x: x.stat().st_mtime)
            
            # Restore files
            for backup_dir in backup_dirs:
                if backup_dir.name.endswith("_code"):
                    # Restore code files
                    for file_path in backup_dir.rglob("*"):
                        if file_path.is_file():
                            relative_path = file_path.relative_to(backup_dir)
                            target_path = Path(relative_path)
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(file_path, target_path)
                
                elif backup_dir.name.endswith("_database"):
                    # Restore databases
                    for file_path in backup_dir.iterdir():
                        if file_path.is_file():
                            target_path = Path(file_path.name)
                            shutil.copy2(file_path, target_path)
            
            logger.info("Restore from backup completed")
            
        except Exception as e:
            logger.error(f"Error restoring from backup: {e}")
            raise
    
    def get_deployment_status(self) -> Dict[str, Any]:
        """Get current deployment status"""
        if not self.current_deployment:
            return {"status": "no_active_deployment"}
        
        return {
            "deployment_id": self.current_deployment.deployment_id,
            "status": self.current_deployment.status.value,
            "start_time": self.current_deployment.start_time,
            "end_time": self.current_deployment.end_time,
            "duration": (self.current_deployment.end_time or time.time()) - self.current_deployment.start_time,
            "services_deployed": self.current_deployment.services_deployed,
            "services_failed": self.current_deployment.services_failed,
            "rollback_performed": self.current_deployment.rollback_performed,
            "error_message": self.current_deployment.error_message
        }
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            name: {
                "status": service.status.value,
                "pid": service.pid,
                "port": service.port,
                "restart_count": service.restart_count,
                "last_restart": service.last_restart
            }
            for name, service in self.services.items()
        }
    
    def generate_deployment_report(self) -> str:
        """Generate deployment report"""
        if not self.current_deployment:
            return "No active deployment"
        
        status = self.get_deployment_status()
        service_status = self.get_service_status()
        
        report = f"""
# Deployment Report
Deployment ID: {status['deployment_id']}
Status: {status['status'].upper()}
Start Time: {datetime.fromtimestamp(status['start_time']).strftime('%Y-%m-%d %H:%M:%S')}
End Time: {datetime.fromtimestamp(status['end_time']).strftime('%Y-%m-%d %H:%M:%S') if status['end_time'] else 'In Progress'}
Duration: {status['duration']:.2f} seconds

## Services Deployed: {len(status['services_deployed'])}
{', '.join(status['services_deployed'])}

## Services Failed: {len(status['services_failed'])}
{', '.join(status['services_failed']) if status['services_failed'] else 'None'}

## Service Status:
"""
        
        for name, status in service_status.items():
            report += f"- {name}: {status['status'].upper()}"
            if status['pid']:
                report += f" (PID: {status['pid']}, Port: {status['port']})"
            report += "\n"
        
        if status['error_message']:
            report += f"\n## Error Message:\n{status['error_message']}\n"
        
        if status['rollback_performed']:
            report += "\n## Rollback: PERFORMED\n"
        
        return report

async def main():
    """Main function for testing deployment scripts"""
    manager = DeploymentManager()
    
    # Deploy version v8.0.0
    result = await manager.deploy("v8.0.0", "production")
    
    print(f"Deployment result: {result.status.value}")
    print(f"Services deployed: {result.services_deployed}")
    print(f"Services failed: {result.services_failed}")
    
    # Generate report
    report = manager.generate_deployment_report()
    print(report)

if __name__ == "__main__":
    asyncio.run(main())
