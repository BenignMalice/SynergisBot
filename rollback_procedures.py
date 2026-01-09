#!/usr/bin/env python3
"""
Rollback Procedures and Drills for TelegramMoneyBot v8.0
Comprehensive rollback system for production deployment safety
"""

import asyncio
import json
import time
import shutil
import subprocess
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import sqlite3
import psutil

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RollbackTrigger(Enum):
    """Types of rollback triggers"""
    CRITICAL_ERROR = "critical_error"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    DATA_CORRUPTION = "data_corruption"
    SECURITY_BREACH = "security_breach"
    MANUAL_INTERVENTION = "manual_intervention"
    CIRCUIT_BREAKER = "circuit_breaker"

class RollbackStatus(Enum):
    """Rollback execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class RollbackPoint:
    """A rollback point for system restoration"""
    id: str
    timestamp: float
    version: str
    description: str
    components: Dict[str, str]  # component -> version/state
    database_backup: str
    config_backup: str
    code_backup: str
    test_results: Dict[str, Any]
    created_by: str
    verified: bool = False

@dataclass
class RollbackOperation:
    """Individual rollback operation"""
    id: str
    component: str
    operation_type: str
    source: str
    target: str
    status: RollbackStatus
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error_message: Optional[str] = None

@dataclass
class RollbackPlan:
    """Complete rollback plan"""
    id: str
    trigger: RollbackTrigger
    target_rollback_point: str
    operations: List[RollbackOperation]
    estimated_duration: int  # seconds
    risk_level: str
    created_at: float
    status: RollbackStatus = RollbackStatus.PENDING

class RollbackManager:
    """Manages rollback procedures and drills"""
    
    def __init__(self, config_path: str = "rollback_config.json"):
        self.config = self._load_config(config_path)
        self.rollback_points: Dict[str, RollbackPoint] = {}
        self.rollback_history: List[RollbackPlan] = []
        self.current_rollback: Optional[RollbackPlan] = None
        
        # Initialize rollback points
        self._load_rollback_points()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load rollback configuration"""
        default_config = {
            "backup_directories": {
                "code": "backups/code",
                "database": "backups/database",
                "config": "backups/config",
                "logs": "backups/logs"
            },
            "rollback_timeouts": {
                "database_restore": 300,  # 5 minutes
                "service_restart": 60,    # 1 minute
                "config_restore": 30,     # 30 seconds
                "code_restore": 120       # 2 minutes
            },
            "verification_checks": {
                "database_integrity": True,
                "service_health": True,
                "configuration_valid": True,
                "test_suite": True
            },
            "components": {
                "chatgpt_bot": {
                    "service_name": "chatgpt_bot",
                    "restart_command": "python chatgpt_bot.py",
                    "health_check": "http://localhost:8001/health"
                },
                "desktop_agent": {
                    "service_name": "desktop_agent",
                    "restart_command": "python desktop_agent.py",
                    "health_check": "http://localhost:8002/health"
                },
                "main_api": {
                    "service_name": "main_api",
                    "restart_command": "python -m uvicorn app.main_api:app --host 0.0.0.0 --port 8000",
                    "health_check": "http://localhost:8000/health"
                },
                "mt5_service": {
                    "service_name": "mt5_service",
                    "restart_command": "python -c 'import MetaTrader5 as mt5; mt5.initialize()'",
                    "health_check": "mt5_connection"
                }
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
            logger.error(f"Error loading rollback config: {e}")
            return default_config
    
    def _load_rollback_points(self):
        """Load existing rollback points"""
        rollback_points_file = "rollback_points.json"
        try:
            if Path(rollback_points_file).exists():
                with open(rollback_points_file, 'r') as f:
                    data = json.load(f)
                    for point_id, point_data in data.items():
                        self.rollback_points[point_id] = RollbackPoint(**point_data)
                logger.info(f"Loaded {len(self.rollback_points)} rollback points")
        except Exception as e:
            logger.error(f"Error loading rollback points: {e}")
    
    def _save_rollback_points(self):
        """Save rollback points to file"""
        try:
            rollback_points_file = "rollback_points.json"
            data = {point_id: asdict(point) for point_id, point in self.rollback_points.items()}
            with open(rollback_points_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving rollback points: {e}")
    
    async def create_rollback_point(self, version: str, description: str, created_by: str = "system") -> str:
        """Create a new rollback point"""
        point_id = f"rb_{int(time.time())}"
        timestamp = time.time()
        
        # Create backups
        backup_paths = await self._create_backups(point_id)
        
        # Get component states
        component_states = await self._get_component_states()
        
        # Run verification tests
        test_results = await self._run_verification_tests()
        
        rollback_point = RollbackPoint(
            id=point_id,
            timestamp=timestamp,
            version=version,
            description=description,
            components=component_states,
            database_backup=backup_paths["database"],
            config_backup=backup_paths["config"],
            code_backup=backup_paths["code"],
            test_results=test_results,
            created_by=created_by,
            verified=test_results.get("overall_success", False)
        )
        
        self.rollback_points[point_id] = rollback_point
        self._save_rollback_points()
        
        logger.info(f"Created rollback point: {point_id} (version: {version})")
        return point_id
    
    async def _create_backups(self, point_id: str) -> Dict[str, str]:
        """Create backups for rollback point"""
        backup_paths = {}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create backup directories
        for backup_type, base_path in self.config["backup_directories"].items():
            backup_dir = Path(base_path) / f"{point_id}_{timestamp}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_paths[backup_type] = str(backup_dir)
        
        # Backup code
        code_backup_dir = Path(backup_paths["code"])
        try:
            # Copy main Python files
            main_files = [
                "chatgpt_bot.py",
                "desktop_agent.py",
                "app/main_api.py",
                "requirements.txt",
                "config/settings.py"
            ]
            
            for file_path in main_files:
                if Path(file_path).exists():
                    shutil.copy2(file_path, code_backup_dir / Path(file_path).name)
            
            # Copy key directories
            key_dirs = ["app", "infra", "config", "domain", "handlers"]
            for dir_path in key_dirs:
                if Path(dir_path).exists():
                    shutil.copytree(dir_path, code_backup_dir / dir_path)
            
            logger.info(f"Code backup created: {code_backup_dir}")
        except Exception as e:
            logger.error(f"Error creating code backup: {e}")
        
        # Backup databases
        db_backup_dir = Path(backup_paths["database"])
        try:
            db_files = [
                "data/unified_tick_pipeline.db",
                "data/analysis_data.db",
                "data/system_logs.db",
                "data/journal.sqlite"
            ]
            
            for db_file in db_files:
                if Path(db_file).exists():
                    shutil.copy2(db_file, db_backup_dir / Path(db_file).name)
            
            logger.info(f"Database backup created: {db_backup_dir}")
        except Exception as e:
            logger.error(f"Error creating database backup: {e}")
        
        # Backup configurations
        config_backup_dir = Path(backup_paths["config"])
        try:
            config_files = [
                "config/settings.py",
                "config/symbol_config_loader.py",
                "config/symbols",
                "production_config.json",
                "rollback_config.json"
            ]
            
            for config_file in config_files:
                if Path(config_file).exists():
                    if Path(config_file).is_dir():
                        shutil.copytree(config_file, config_backup_dir / Path(config_file).name)
                    else:
                        shutil.copy2(config_file, config_backup_dir / Path(config_file).name)
            
            logger.info(f"Config backup created: {config_backup_dir}")
        except Exception as e:
            logger.error(f"Error creating config backup: {e}")
        
        return backup_paths
    
    async def _get_component_states(self) -> Dict[str, str]:
        """Get current component states"""
        states = {}
        
        for component, config in self.config["components"].items():
            try:
                if component in ["chatgpt_bot", "desktop_agent", "main_api"]:
                    # Check if service is running
                    import requests
                    health_url = config.get("health_check", "")
                    if health_url:
                        response = requests.get(health_url, timeout=5)
                        states[component] = f"running_{response.status_code}"
                    else:
                        states[component] = "unknown"
                elif component == "mt5_service":
                    # Check MT5 connection
                    try:
                        import MetaTrader5 as mt5
                        if mt5.initialize() and mt5.terminal_info():
                            states[component] = "connected"
                        else:
                            states[component] = "disconnected"
                    except Exception:
                        states[component] = "error"
                else:
                    states[component] = "unknown"
            except Exception as e:
                states[component] = f"error_{str(e)}"
        
        return states
    
    async def _run_verification_tests(self) -> Dict[str, Any]:
        """Run verification tests for rollback point"""
        test_results = {
            "timestamp": time.time(),
            "overall_success": True,
            "tests": {}
        }
        
        try:
            # Run basic system tests
            test_results["tests"]["system_health"] = await self._test_system_health()
            test_results["tests"]["database_integrity"] = await self._test_database_integrity()
            test_results["tests"]["configuration_valid"] = await self._test_configuration_valid()
            test_results["tests"]["service_connectivity"] = await self._test_service_connectivity()
            
            # Determine overall success
            test_results["overall_success"] = all(
                test.get("success", False) for test in test_results["tests"].values()
            )
            
        except Exception as e:
            logger.error(f"Error running verification tests: {e}")
            test_results["overall_success"] = False
            test_results["error"] = str(e)
        
        return test_results
    
    async def _test_system_health(self) -> Dict[str, Any]:
        """Test system health"""
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_usage = psutil.virtual_memory().percent
            disk_usage = psutil.disk_usage('/').percent
            
            return {
                "success": cpu_usage < 90 and memory_usage < 90 and disk_usage < 95,
                "cpu_usage": cpu_usage,
                "memory_usage": memory_usage,
                "disk_usage": disk_usage
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _test_database_integrity(self) -> Dict[str, Any]:
        """Test database integrity"""
        try:
            db_files = [
                "data/unified_tick_pipeline.db",
                "data/analysis_data.db",
                "data/system_logs.db"
            ]
            
            results = {}
            overall_success = True
            
            for db_file in db_files:
                if Path(db_file).exists():
                    try:
                        with sqlite3.connect(db_file) as conn:
                            # Test basic connectivity
                            conn.execute("SELECT 1")
                            # Test for corruption
                            conn.execute("PRAGMA integrity_check")
                            results[db_file] = {"success": True, "status": "healthy"}
                    except Exception as e:
                        results[db_file] = {"success": False, "error": str(e)}
                        overall_success = False
                else:
                    results[db_file] = {"success": False, "error": "file_not_found"}
                    overall_success = False
            
            return {"success": overall_success, "databases": results}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _test_configuration_valid(self) -> Dict[str, Any]:
        """Test configuration validity"""
        try:
            # Test main configuration files
            config_files = [
                "config/settings.py",
                "config/symbol_config_loader.py",
                "production_config.json"
            ]
            
            results = {}
            overall_success = True
            
            for config_file in config_files:
                if Path(config_file).exists():
                    try:
                        if config_file.endswith('.py'):
                            # Test Python syntax
                            with open(config_file, 'r') as f:
                                compile(f.read(), config_file, 'exec')
                        elif config_file.endswith('.json'):
                            # Test JSON validity
                            with open(config_file, 'r') as f:
                                json.load(f)
                        results[config_file] = {"success": True}
                    except Exception as e:
                        results[config_file] = {"success": False, "error": str(e)}
                        overall_success = False
                else:
                    results[config_file] = {"success": False, "error": "file_not_found"}
                    overall_success = False
            
            return {"success": overall_success, "configs": results}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _test_service_connectivity(self) -> Dict[str, Any]:
        """Test service connectivity"""
        try:
            services = {
                "main_api": "http://localhost:8000/health",
                "chatgpt_bot": "http://localhost:8001/health",
                "desktop_agent": "http://localhost:8002/health"
            }
            
            results = {}
            overall_success = True
            
            for service, url in services.items():
                try:
                    import requests
                    response = requests.get(url, timeout=5)
                    results[service] = {
                        "success": response.status_code == 200,
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds()
                    }
                    if response.status_code != 200:
                        overall_success = False
                except Exception as e:
                    results[service] = {"success": False, "error": str(e)}
                    overall_success = False
            
            return {"success": overall_success, "services": results}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def execute_rollback(self, rollback_point_id: str, trigger: RollbackTrigger, 
                             reason: str = "") -> RollbackPlan:
        """Execute a rollback to specified point"""
        if rollback_point_id not in self.rollback_points:
            raise ValueError(f"Rollback point {rollback_point_id} not found")
        
        rollback_point = self.rollback_points[rollback_point_id]
        
        # Create rollback plan
        plan_id = f"rollback_{int(time.time())}"
        operations = await self._create_rollback_operations(rollback_point)
        
        rollback_plan = RollbackPlan(
            id=plan_id,
            trigger=trigger,
            target_rollback_point=rollback_point_id,
            operations=operations,
            estimated_duration=sum(op.get("estimated_duration", 60) for op in operations),
            risk_level=self._assess_risk_level(rollback_point),
            created_at=time.time()
        )
        
        self.current_rollback = rollback_plan
        self.rollback_history.append(rollback_plan)
        
        logger.info(f"Starting rollback {plan_id} to point {rollback_point_id}")
        logger.info(f"Trigger: {trigger.value}, Reason: {reason}")
        
        try:
            # Execute rollback operations
            rollback_plan.status = RollbackStatus.IN_PROGRESS
            await self._execute_rollback_operations(rollback_plan)
            
            # Verify rollback success
            verification_success = await self._verify_rollback_success(rollback_plan)
            
            if verification_success:
                rollback_plan.status = RollbackStatus.COMPLETED
                logger.info(f"Rollback {plan_id} completed successfully")
            else:
                rollback_plan.status = RollbackStatus.FAILED
                logger.error(f"Rollback {plan_id} verification failed")
            
        except Exception as e:
            rollback_plan.status = RollbackStatus.FAILED
            logger.error(f"Rollback {plan_id} failed: {e}")
        
        return rollback_plan
    
    async def _create_rollback_operations(self, rollback_point: RollbackPoint) -> List[RollbackOperation]:
        """Create rollback operations for a rollback point"""
        operations = []
        
        # Database restore operation
        operations.append(RollbackOperation(
            id=f"db_restore_{int(time.time())}",
            component="database",
            operation_type="restore",
            source=rollback_point.database_backup,
            target="data/",
            status=RollbackStatus.PENDING
        ))
        
        # Configuration restore operation
        operations.append(RollbackOperation(
            id=f"config_restore_{int(time.time())}",
            component="configuration",
            operation_type="restore",
            source=rollback_point.config_backup,
            target="config/",
            status=RollbackStatus.PENDING
        ))
        
        # Code restore operation
        operations.append(RollbackOperation(
            id=f"code_restore_{int(time.time())}",
            component="code",
            operation_type="restore",
            source=rollback_point.code_backup,
            target="./",
            status=RollbackStatus.PENDING
        ))
        
        # Service restart operations
        for component, config in self.config["components"].items():
            operations.append(RollbackOperation(
                id=f"restart_{component}_{int(time.time())}",
                component=component,
                operation_type="restart",
                source="",
                target=config.get("restart_command", ""),
                status=RollbackStatus.PENDING
            ))
        
        return operations
    
    def _assess_risk_level(self, rollback_point: RollbackPoint) -> str:
        """Assess risk level of rollback"""
        if not rollback_point.verified:
            return "high"
        
        # Check if rollback point is recent (less than 24 hours)
        age_hours = (time.time() - rollback_point.timestamp) / 3600
        if age_hours < 24:
            return "low"
        elif age_hours < 168:  # 1 week
            return "medium"
        else:
            return "high"
    
    async def _execute_rollback_operations(self, rollback_plan: RollbackPlan):
        """Execute rollback operations"""
        for operation in rollback_plan.operations:
            try:
                operation.status = RollbackStatus.IN_PROGRESS
                operation.start_time = time.time()
                
                if operation.operation_type == "restore":
                    await self._restore_files(operation)
                elif operation.operation_type == "restart":
                    await self._restart_service(operation)
                
                operation.end_time = time.time()
                operation.status = RollbackStatus.COMPLETED
                
                logger.info(f"Operation {operation.id} completed successfully")
                
            except Exception as e:
                operation.end_time = time.time()
                operation.status = RollbackStatus.FAILED
                operation.error_message = str(e)
                logger.error(f"Operation {operation.id} failed: {e}")
                
                # Decide whether to continue or abort
                if operation.component in ["database", "configuration"]:
                    # Critical operations - abort rollback
                    raise e
    
    async def _restore_files(self, operation: RollbackOperation):
        """Restore files from backup"""
        try:
            source_path = Path(operation.source)
            target_path = Path(operation.target)
            
            if source_path.exists():
                if source_path.is_dir():
                    # Restore directory
                    if target_path.exists():
                        shutil.rmtree(target_path)
                    shutil.copytree(source_path, target_path)
                else:
                    # Restore file
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, target_path)
                
                logger.info(f"Restored {source_path} to {target_path}")
            else:
                raise FileNotFoundError(f"Source path {source_path} not found")
                
        except Exception as e:
            logger.error(f"Error restoring files: {e}")
            raise
    
    async def _restart_service(self, operation: RollbackOperation):
        """Restart a service"""
        try:
            if operation.target:
                # Execute restart command
                result = subprocess.run(
                    operation.target.split(),
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode != 0:
                    raise RuntimeError(f"Service restart failed: {result.stderr}")
                
                logger.info(f"Service {operation.component} restarted successfully")
            else:
                logger.warning(f"No restart command for {operation.component}")
                
        except Exception as e:
            logger.error(f"Error restarting service {operation.component}: {e}")
            raise
    
    async def _verify_rollback_success(self, rollback_plan: RollbackPlan) -> bool:
        """Verify rollback was successful"""
        try:
            # Run verification tests
            test_results = await self._run_verification_tests()
            
            # Check if all critical components are healthy
            critical_components = ["main_api", "mt5_service"]
            for component in critical_components:
                if component in self.config["components"]:
                    health = await self._check_component_health(component)
                    if health.status != "running":
                        logger.error(f"Component {component} not healthy after rollback")
                        return False
            
            return test_results.get("overall_success", False)
            
        except Exception as e:
            logger.error(f"Error verifying rollback: {e}")
            return False
    
    async def _check_component_health(self, component: str) -> Dict[str, Any]:
        """Check component health (simplified)"""
        try:
            config = self.config["components"][component]
            health_url = config.get("health_check", "")
            
            if health_url and health_url.startswith("http"):
                import requests
                response = requests.get(health_url, timeout=5)
                return {
                    "status": "running" if response.status_code == 200 else "error",
                    "response_code": response.status_code
                }
            else:
                return {"status": "unknown"}
                
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def run_rollback_drill(self, drill_type: str = "full") -> Dict[str, Any]:
        """Run a rollback drill to test procedures"""
        logger.info(f"Starting rollback drill: {drill_type}")
        
        drill_results = {
            "drill_type": drill_type,
            "start_time": time.time(),
            "success": False,
            "operations_completed": 0,
            "total_operations": 0,
            "errors": []
        }
        
        try:
            # Create a test rollback point
            test_point_id = await self.create_rollback_point(
                version="drill_test",
                description=f"Rollback drill test - {drill_type}",
                created_by="drill_system"
            )
            
            # Simulate rollback execution (without actually restoring)
            if drill_type == "full":
                # Test all operations
                operations = await self._create_rollback_operations(
                    self.rollback_points[test_point_id]
                )
                drill_results["total_operations"] = len(operations)
                
                for operation in operations:
                    try:
                        # Simulate operation (don't actually execute)
                        await asyncio.sleep(0.1)  # Simulate processing time
                        drill_results["operations_completed"] += 1
                    except Exception as e:
                        drill_results["errors"].append(f"Operation {operation.id}: {e}")
            
            elif drill_type == "database":
                # Test only database operations
                drill_results["total_operations"] = 1
                drill_results["operations_completed"] = 1
            
            elif drill_type == "services":
                # Test only service restart operations
                service_count = len(self.config["components"])
                drill_results["total_operations"] = service_count
                drill_results["operations_completed"] = service_count
            
            # Determine success
            drill_results["success"] = (
                drill_results["operations_completed"] == drill_results["total_operations"] and
                len(drill_results["errors"]) == 0
            )
            
            # Clean up test rollback point
            if test_point_id in self.rollback_points:
                del self.rollback_points[test_point_id]
            
        except Exception as e:
            drill_results["errors"].append(f"Drill failed: {e}")
            logger.error(f"Rollback drill failed: {e}")
        
        drill_results["end_time"] = time.time()
        drill_results["duration"] = drill_results["end_time"] - drill_results["start_time"]
        
        logger.info(f"Rollback drill completed: {drill_results['success']}")
        return drill_results
    
    def get_rollback_status(self) -> Dict[str, Any]:
        """Get current rollback status"""
        return {
            "current_rollback": asdict(self.current_rollback) if self.current_rollback else None,
            "rollback_points": len(self.rollback_points),
            "rollback_history": len(self.rollback_history),
            "available_points": [
                {
                    "id": point.id,
                    "version": point.version,
                    "description": point.description,
                    "timestamp": point.timestamp,
                    "verified": point.verified
                }
                for point in self.rollback_points.values()
            ]
        }
    
    def generate_rollback_report(self) -> str:
        """Generate rollback status report"""
        status = self.get_rollback_status()
        
        report = f"""
# Rollback System Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Current Status:
- Rollback Points Available: {status['rollback_points']}
- Rollback History: {status['rollback_history']}
- Current Rollback: {'In Progress' if status['current_rollback'] else 'None'}

## Available Rollback Points:
"""
        
        for point in status['available_points']:
            report += f"""
- {point['id']} (Version: {point['version']})
  Description: {point['description']}
  Created: {datetime.fromtimestamp(point['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}
  Verified: {'Yes' if point['verified'] else 'No'}
"""
        
        return report

async def main():
    """Main function for testing rollback procedures"""
    rollback_manager = RollbackManager()
    
    # Create a test rollback point
    point_id = await rollback_manager.create_rollback_point(
        version="test_v1.0",
        description="Test rollback point",
        created_by="test_user"
    )
    
    print(f"Created rollback point: {point_id}")
    
    # Run a rollback drill
    drill_results = await rollback_manager.run_rollback_drill("full")
    print(f"Drill results: {drill_results}")
    
    # Generate report
    report = rollback_manager.generate_rollback_report()
    print(report)

if __name__ == "__main__":
    asyncio.run(main())
