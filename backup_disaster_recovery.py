#!/usr/bin/env python3
"""
Backup and Disaster Recovery System for TelegramMoneyBot v8.0
Comprehensive backup, disaster recovery, and business continuity system
"""

import asyncio
import json
import shutil
import sqlite3
import tarfile
import gzip
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import hashlib
import secrets
import subprocess
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BackupType(Enum):
    """Backup types"""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"

class BackupStatus(Enum):
    """Backup status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"

class RecoveryStatus(Enum):
    """Recovery status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"

@dataclass
class BackupConfig:
    """Backup configuration"""
    backup_id: str
    name: str
    backup_type: BackupType
    source_paths: List[str]
    destination_path: str
    compression_enabled: bool
    encryption_enabled: bool
    retention_days: int
    schedule: str
    enabled: bool = True

@dataclass
class BackupJob:
    """Backup job instance"""
    job_id: str
    backup_config: BackupConfig
    status: BackupStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    backup_size: int = 0
    files_count: int = 0
    error_message: Optional[str] = None
    verification_hash: Optional[str] = None

@dataclass
class RecoveryJob:
    """Recovery job instance"""
    job_id: str
    backup_job_id: str
    target_path: str
    status: RecoveryStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None

class BackupDisasterRecovery:
    """Backup and disaster recovery management system"""
    
    def __init__(self, config_path: str = "backup_recovery_config.json"):
        self.config = self._load_config(config_path)
        self.backup_configs: Dict[str, BackupConfig] = {}
        self.backup_jobs: List[BackupJob] = []
        self.recovery_jobs: List[RecoveryJob] = []
        self.running = False
        
        # Initialize backup configurations
        self._initialize_backup_configs()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load backup and recovery configuration"""
        default_config = {
            "backup_configurations": {
                "full_system_backup": {
                    "backup_id": "full_system_backup",
                    "name": "Full System Backup",
                    "backup_type": "full",
                    "source_paths": [
                        "data/",
                        "config/",
                        "app/",
                        "infra/",
                        "domain/",
                        "handlers/",
                        "*.py",
                        "*.json",
                        "*.md"
                    ],
                    "destination_path": "backups/full_system",
                    "compression_enabled": True,
                    "encryption_enabled": True,
                    "retention_days": 30,
                    "schedule": "0 2 * * *",
                    "enabled": True
                },
                "database_backup": {
                    "backup_id": "database_backup",
                    "name": "Database Backup",
                    "backup_type": "incremental",
                    "source_paths": [
                        "data/unified_tick_pipeline.db",
                        "data/analysis_data.db",
                        "data/system_logs.db",
                        "data/journal.sqlite"
                    ],
                    "destination_path": "backups/databases",
                    "compression_enabled": True,
                    "encryption_enabled": True,
                    "retention_days": 90,
                    "schedule": "0 */6 * * *",
                    "enabled": True
                },
                "config_backup": {
                    "backup_id": "config_backup",
                    "name": "Configuration Backup",
                    "backup_type": "full",
                    "source_paths": [
                        "config/",
                        "*.json",
                        "*.py"
                    ],
                    "destination_path": "backups/configurations",
                    "compression_enabled": True,
                    "encryption_enabled": True,
                    "retention_days": 365,
                    "schedule": "0 3 * * *",
                    "enabled": True
                },
                "logs_backup": {
                    "backup_id": "logs_backup",
                    "name": "Logs Backup",
                    "backup_type": "incremental",
                    "source_paths": [
                        "logs/",
                        "*.log"
                    ],
                    "destination_path": "backups/logs",
                    "compression_enabled": True,
                    "encryption_enabled": False,
                    "retention_days": 30,
                    "schedule": "0 4 * * *",
                    "enabled": True
                }
            },
            "disaster_recovery": {
                "recovery_time_objective": 4,  # hours
                "recovery_point_objective": 1,  # hour
                "max_data_loss_hours": 1,
                "backup_verification_enabled": True,
                "automated_recovery_enabled": True,
                "recovery_testing_schedule": "0 0 * * 0"  # Weekly
            },
            "storage": {
                "local_storage": {
                    "enabled": True,
                    "path": "backups/",
                    "max_size_gb": 100,
                    "cleanup_enabled": True
                },
                "remote_storage": {
                    "enabled": False,
                    "type": "s3",
                    "bucket": "your-backup-bucket",
                    "region": "us-east-1",
                    "access_key": "your-access-key",
                    "secret_key": "your-secret-key"
                }
            },
            "encryption": {
                "algorithm": "AES-256-GCM",
                "key_rotation_days": 30,
                "key_storage": "secure"
            },
            "monitoring": {
                "backup_monitoring_enabled": True,
                "alert_on_failure": True,
                "alert_on_success": False,
                "retention_monitoring": True
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
            logger.error(f"Error loading backup config: {e}")
            return default_config
    
    def _initialize_backup_configs(self):
        """Initialize backup configurations"""
        try:
            for config_id, config_data in self.config["backup_configurations"].items():
                backup_config = BackupConfig(
                    backup_id=config_data["backup_id"],
                    name=config_data["name"],
                    backup_type=BackupType(config_data["backup_type"]),
                    source_paths=config_data["source_paths"],
                    destination_path=config_data["destination_path"],
                    compression_enabled=config_data["compression_enabled"],
                    encryption_enabled=config_data["encryption_enabled"],
                    retention_days=config_data["retention_days"],
                    schedule=config_data["schedule"],
                    enabled=config_data["enabled"]
                )
                self.backup_configs[config_id] = backup_config
            
            logger.info(f"Initialized {len(self.backup_configs)} backup configurations")
            
        except Exception as e:
            logger.error(f"Error initializing backup configurations: {e}")
    
    async def start_backup_service(self):
        """Start the backup service"""
        logger.info("Starting backup and disaster recovery service...")
        self.running = True
        
        try:
            while self.running:
                # Check for scheduled backups
                await self._check_scheduled_backups()
                
                # Clean up old backups
                await self._cleanup_old_backups()
                
                # Verify backup integrity
                await self._verify_backup_integrity()
                
                # Wait for next check
                await asyncio.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            logger.info("Stopping backup service...")
            self.running = False
        except Exception as e:
            logger.error(f"Error in backup service: {e}")
            self.running = False
    
    async def _check_scheduled_backups(self):
        """Check for scheduled backups"""
        try:
            current_time = datetime.now()
            
            for config_id, config in self.backup_configs.items():
                if not config.enabled:
                    continue
                
                # Check if backup is due (simplified schedule checking)
                if self._is_backup_due(config, current_time):
                    await self._execute_backup(config)
                    
        except Exception as e:
            logger.error(f"Error checking scheduled backups: {e}")
    
    def _is_backup_due(self, config: BackupConfig, current_time: datetime) -> bool:
        """Check if backup is due based on schedule"""
        # Simplified schedule checking - in production, use proper cron parsing
        if config.schedule == "0 2 * * *":  # Daily at 2 AM
            return current_time.hour == 2 and current_time.minute == 0
        elif config.schedule == "0 */6 * * *":  # Every 6 hours
            return current_time.hour % 6 == 0 and current_time.minute == 0
        elif config.schedule == "0 3 * * *":  # Daily at 3 AM
            return current_time.hour == 3 and current_time.minute == 0
        elif config.schedule == "0 4 * * *":  # Daily at 4 AM
            return current_time.hour == 4 and current_time.minute == 0
        else:
            return False
    
    async def _execute_backup(self, config: BackupConfig):
        """Execute a backup job"""
        try:
            job_id = f"{config.backup_id}_{int(time.time())}"
            
            # Create backup job
            backup_job = BackupJob(
                job_id=job_id,
                backup_config=config,
                status=BackupStatus.IN_PROGRESS,
                start_time=datetime.now()
            )
            
            self.backup_jobs.append(backup_job)
            
            logger.info(f"Starting backup job {job_id} for {config.name}")
            
            # Create destination directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = Path(config.destination_path) / f"{config.backup_id}_{timestamp}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Collect source files
            source_files = await self._collect_source_files(config.source_paths)
            
            # Create backup archive
            backup_path = await self._create_backup_archive(
                source_files, backup_dir, config, job_id
            )
            
            # Update backup job
            backup_job.status = BackupStatus.COMPLETED
            backup_job.end_time = datetime.now()
            backup_job.backup_size = Path(backup_path).stat().st_size if Path(backup_path).exists() else 0
            backup_job.files_count = len(source_files)
            
            # Verify backup if enabled
            if self.config["disaster_recovery"]["backup_verification_enabled"]:
                if await self._verify_backup_file(backup_path):
                    backup_job.status = BackupStatus.VERIFIED
                    backup_job.verification_hash = await self._calculate_file_hash(backup_path)
                else:
                    backup_job.status = BackupStatus.FAILED
                    backup_job.error_message = "Backup verification failed"
            
            logger.info(f"Backup job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error executing backup {config.name}: {e}")
            if 'backup_job' in locals():
                backup_job.status = BackupStatus.FAILED
                backup_job.error_message = str(e)
                backup_job.end_time = datetime.now()
    
    async def _collect_source_files(self, source_paths: List[str]) -> List[Path]:
        """Collect source files for backup"""
        source_files = []
        
        for source_path in source_paths:
            path = Path(source_path)
            
            if path.is_file():
                source_files.append(path)
            elif path.is_dir():
                # Add all files in directory
                for file_path in path.rglob("*"):
                    if file_path.is_file():
                        source_files.append(file_path)
            else:
                # Handle glob patterns
                import glob
                for file_path in glob.glob(source_path):
                    source_files.append(Path(file_path))
        
        return source_files
    
    async def _create_backup_archive(self, source_files: List[Path], backup_dir: Path, 
                                   config: BackupConfig, job_id: str) -> str:
        """Create backup archive"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"{config.backup_id}_{timestamp}.tar"
            if config.compression_enabled:
                archive_name += ".gz"
            
            archive_path = backup_dir / archive_name
            
            # Create tar archive
            if config.compression_enabled:
                with tarfile.open(archive_path, "w:gz") as tar:
                    for file_path in source_files:
                        if file_path.exists():
                            tar.add(file_path, arcname=file_path.name)
            else:
                with tarfile.open(archive_path, "w") as tar:
                    for file_path in source_files:
                        if file_path.exists():
                            tar.add(file_path, arcname=file_path.name)
            
            # Encrypt if enabled
            if config.encryption_enabled:
                encrypted_path = archive_path.with_suffix(archive_path.suffix + ".enc")
                await self._encrypt_file(archive_path, encrypted_path)
                archive_path = encrypted_path
            
            return str(archive_path)
            
        except Exception as e:
            logger.error(f"Error creating backup archive: {e}")
            raise
    
    async def _encrypt_file(self, source_path: Path, dest_path: Path):
        """Encrypt file (simplified implementation)"""
        try:
            # In production, use proper encryption libraries
            # For now, we'll just copy the file and add encryption marker
            shutil.copy2(source_path, dest_path)
            
            # Add encryption marker
            with open(dest_path, 'ab') as f:
                f.write(b'\n[ENCRYPTED_BACKUP]\n')
            
        except Exception as e:
            logger.error(f"Error encrypting file: {e}")
            raise
    
    async def _verify_backup_file(self, backup_path: str) -> bool:
        """Verify backup file integrity"""
        try:
            if not Path(backup_path).exists():
                return False
            
            # Check if file is readable
            with open(backup_path, 'rb') as f:
                f.read(1024)  # Read first 1KB
            
            # Check if it's a valid tar file
            if backup_path.endswith('.tar.gz') or backup_path.endswith('.tar'):
                with tarfile.open(backup_path, 'r') as tar:
                    tar.getnames()  # Try to read file names
            
            return True
            
        except Exception as e:
            logger.error(f"Error verifying backup file {backup_path}: {e}")
            return False
    
    async def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate file hash for verification"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating file hash: {e}")
            return ""
    
    async def _cleanup_old_backups(self):
        """Clean up old backups based on retention policy"""
        try:
            for config_id, config in self.backup_configs.items():
                if not config.enabled:
                    continue
                
                backup_dir = Path(config.destination_path)
                if not backup_dir.exists():
                    continue
                
                # Calculate cutoff date
                cutoff_date = datetime.now() - timedelta(days=config.retention_days)
                
                # Find old backups
                for backup_file in backup_dir.rglob("*"):
                    if backup_file.is_file():
                        file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                        if file_time < cutoff_date:
                            backup_file.unlink()
                            logger.info(f"Deleted old backup: {backup_file}")
            
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
    
    async def _verify_backup_integrity(self):
        """Verify integrity of recent backups"""
        try:
            # Check backups from last 24 hours
            recent_cutoff = datetime.now() - timedelta(hours=24)
            
            for backup_job in self.backup_jobs:
                if (backup_job.start_time > recent_cutoff and 
                    backup_job.status == BackupStatus.COMPLETED):
                    
                    # Verify backup integrity
                    if not await self._verify_backup_file(backup_job.backup_config.destination_path):
                        backup_job.status = BackupStatus.FAILED
                        backup_job.error_message = "Backup integrity verification failed"
                        logger.warning(f"Backup integrity failed for job {backup_job.job_id}")
            
        except Exception as e:
            logger.error(f"Error verifying backup integrity: {e}")
    
    async def execute_recovery(self, backup_job_id: str, target_path: str) -> RecoveryJob:
        """Execute disaster recovery from backup"""
        try:
            # Find backup job
            backup_job = None
            for job in self.backup_jobs:
                if job.job_id == backup_job_id:
                    backup_job = job
                    break
            
            if not backup_job:
                raise ValueError(f"Backup job {backup_job_id} not found")
            
            # Create recovery job
            recovery_job = RecoveryJob(
                job_id=f"recovery_{int(time.time())}",
                backup_job_id=backup_job_id,
                target_path=target_path,
                status=RecoveryStatus.IN_PROGRESS,
                start_time=datetime.now()
            )
            
            self.recovery_jobs.append(recovery_job)
            
            logger.info(f"Starting recovery job {recovery_job.job_id}")
            
            # Find backup file
            backup_dir = Path(backup_job.backup_config.destination_path)
            backup_files = list(backup_dir.rglob(f"{backup_job_id}*"))
            
            if not backup_files:
                raise ValueError(f"Backup files not found for job {backup_job_id}")
            
            backup_file = backup_files[0]
            
            # Create target directory
            Path(target_path).mkdir(parents=True, exist_ok=True)
            
            # Extract backup
            await self._extract_backup(backup_file, target_path, backup_job.backup_config)
            
            # Update recovery job
            recovery_job.status = RecoveryStatus.COMPLETED
            recovery_job.end_time = datetime.now()
            
            logger.info(f"Recovery job {recovery_job.job_id} completed successfully")
            return recovery_job
            
        except Exception as e:
            logger.error(f"Error executing recovery: {e}")
            if 'recovery_job' in locals():
                recovery_job.status = RecoveryStatus.FAILED
                recovery_job.error_message = str(e)
                recovery_job.end_time = datetime.now()
            raise
    
    async def _extract_backup(self, backup_file: Path, target_path: str, config: BackupConfig):
        """Extract backup archive"""
        try:
            # Decrypt if needed
            if config.encryption_enabled and backup_file.suffix == '.enc':
                decrypted_file = backup_file.with_suffix('')
                await self._decrypt_file(backup_file, decrypted_file)
                backup_file = decrypted_file
            
            # Extract archive
            if backup_file.suffix == '.gz':
                with tarfile.open(backup_file, 'r:gz') as tar:
                    tar.extractall(target_path)
            else:
                with tarfile.open(backup_file, 'r') as tar:
                    tar.extractall(target_path)
            
        except Exception as e:
            logger.error(f"Error extracting backup: {e}")
            raise
    
    async def _decrypt_file(self, encrypted_file: Path, decrypted_file: Path):
        """Decrypt file (simplified implementation)"""
        try:
            # In production, use proper decryption libraries
            # For now, we'll just copy the file
            shutil.copy2(encrypted_file, decrypted_file)
            
        except Exception as e:
            logger.error(f"Error decrypting file: {e}")
            raise
    
    def get_backup_status(self) -> Dict[str, Any]:
        """Get backup system status"""
        return {
            "running": self.running,
            "backup_configs": len(self.backup_configs),
            "enabled_configs": len([c for c in self.backup_configs.values() if c.enabled]),
            "total_backup_jobs": len(self.backup_jobs),
            "successful_backups": len([j for j in self.backup_jobs if j.status == BackupStatus.COMPLETED]),
            "failed_backups": len([j for j in self.backup_jobs if j.status == BackupStatus.FAILED]),
            "total_recovery_jobs": len(self.recovery_jobs),
            "successful_recoveries": len([j for j in self.recovery_jobs if j.status == RecoveryStatus.COMPLETED]),
            "failed_recoveries": len([j for j in self.recovery_jobs if j.status == RecoveryStatus.FAILED])
        }
    
    def get_recent_backups(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent backup jobs"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_jobs = [job for job in self.backup_jobs if job.start_time > cutoff_time]
        
        return [asdict(job) for job in recent_jobs]

async def main():
    """Main function for testing backup and disaster recovery"""
    backup_system = BackupDisasterRecovery()
    
    # Start backup service
    await backup_system.start_backup_service()

if __name__ == "__main__":
    asyncio.run(main())
