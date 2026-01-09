#!/bin/bash
# Pre-rollback script for TelegramMoneyBot v8.0
# This script runs before rollback to prepare the environment

set -e  # Exit on any error

ENVIRONMENT=$1
DEPLOYMENT_ID=$2
ROLLBACK_REASON=$3

echo "Starting pre-rollback script for environment: $ENVIRONMENT, deployment: $DEPLOYMENT_ID"
echo "Rollback reason: $ROLLBACK_REASON"

# Create rollback logs directory
mkdir -p logs/rollbacks
ROLLBACK_LOG="logs/rollbacks/rollback_${DEPLOYMENT_ID}_$(date +%Y%m%d_%H%M%S).log"

# Log rollback start
echo "Rollback started at $(date)" > "$ROLLBACK_LOG"
echo "Environment: $ENVIRONMENT" >> "$ROLLBACK_LOG"
echo "Deployment ID: $DEPLOYMENT_ID" >> "$ROLLBACK_LOG"
echo "Reason: $ROLLBACK_REASON" >> "$ROLLBACK_LOG"

# Check if rollback is necessary
echo "Checking if rollback is necessary..."

# Check if services are responding
SERVICES_DOWN=0
for service in "Main API:8000" "ChatGPT Bot:8001" "Desktop Agent:8002"; do
    service_name=$(echo $service | cut -d: -f1)
    port=$(echo $service | cut -d: -f2)
    
    if ! curl -s "http://localhost:$port/health" > /dev/null 2>&1; then
        echo "WARNING: $service_name is not responding"
        SERVICES_DOWN=$((SERVICES_DOWN + 1))
    else
        echo "$service_name is responding"
    fi
done

# Check system resources
echo "Checking system resources..."
python3 -c "
import psutil
import sys

# Check CPU usage
cpu_usage = psutil.cpu_percent(interval=5)
print(f'CPU usage: {cpu_usage}%')

# Check memory usage
memory = psutil.virtual_memory()
print(f'Memory usage: {memory.percent}%')

# Check disk usage
disk = psutil.disk_usage('/')
print(f'Disk usage: {disk.percent}%')

# Determine if rollback is needed based on resource usage
if cpu_usage > 95 or memory.percent > 95 or disk.percent > 95:
    print('ERROR: Critical resource usage detected, rollback recommended')
    sys.exit(1)
else:
    print('System resources are within acceptable limits')
"

# Check database integrity
echo "Checking database integrity..."
python3 -c "
import sqlite3
import sys

databases = [
    'data/unified_tick_pipeline.db',
    'data/analysis_data.db', 
    'data/system_logs.db',
    'data/journal.sqlite'
]

corrupted_dbs = []
for db_path in databases:
    try:
        conn = sqlite3.connect(db_path)
        result = conn.execute('PRAGMA integrity_check').fetchone()
        if result[0] != 'ok':
            corrupted_dbs.append(db_path)
            print(f'WARNING: Database {db_path} may be corrupted: {result[0]}')
        else:
            print(f'Database {db_path} integrity check passed')
        conn.close()
    except Exception as e:
        corrupted_dbs.append(db_path)
        print(f'ERROR: Database {db_path} check failed: {e}')

if corrupted_dbs:
    print(f'ERROR: {len(corrupted_dbs)} databases may be corrupted, rollback recommended')
    sys.exit(1)
else:
    print('All database integrity checks passed')
"

# Find backup for rollback
echo "Looking for backup for deployment $DEPLOYMENT_ID..."
BACKUP_DIR=$(find backups -name "deployment_${DEPLOYMENT_ID}_*" -type d | head -1)

if [ -z "$BACKUP_DIR" ]; then
    echo "ERROR: No backup found for deployment $DEPLOYMENT_ID"
    echo "Available backups:"
    ls -la backups/ | grep "deployment_" || echo "No deployment backups found"
    exit 1
fi

echo "Found backup directory: $BACKUP_DIR"

# Verify backup integrity
echo "Verifying backup integrity..."
if [ ! -d "$BACKUP_DIR" ]; then
    echo "ERROR: Backup directory $BACKUP_DIR does not exist"
    exit 1
fi

# Check if backup contains required files
REQUIRED_FILES=("app" "infra" "config")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -e "$BACKUP_DIR/$file" ]; then
        echo "WARNING: Required backup file/directory $file not found in $BACKUP_DIR"
    else
        echo "Backup file/directory $file found"
    fi
done

# Check if backup databases exist
if [ -d "$BACKUP_DIR/databases" ]; then
    echo "Backup databases found:"
    ls -la "$BACKUP_DIR/databases/"
else
    echo "WARNING: No backup databases found"
fi

# Create rollback plan
echo "Creating rollback plan..."
ROLLBACK_PLAN="rollback_plan_${DEPLOYMENT_ID}.json"
python3 -c "
import json
import time
from datetime import datetime

plan = {
    'rollback_id': 'rollback_${DEPLOYMENT_ID}',
    'deployment_id': '$DEPLOYMENT_ID',
    'environment': '$ENVIRONMENT',
    'reason': '$ROLLBACK_REASON',
    'backup_directory': '$BACKUP_DIR',
    'created_at': time.time(),
    'steps': [
        'Stop current services',
        'Restore code from backup',
        'Restore configuration from backup',
        'Restore databases from backup',
        'Start services',
        'Verify rollback success'
    ],
    'estimated_duration_minutes': 15
}

with open('$ROLLBACK_PLAN', 'w') as f:
    json.dump(plan, f, indent=2, default=str)

print('Rollback plan created: $ROLLBACK_PLAN')
"

# Set environment variables for rollback
export ROLLBACK_ID="rollback_${DEPLOYMENT_ID}"
export BACKUP_DIR="$BACKUP_DIR"
export ROLLBACK_LOG="$ROLLBACK_LOG"
export ROLLBACK_PLAN="$ROLLBACK_PLAN"

# Log pre-rollback status
echo "Pre-rollback script completed successfully" >> "$ROLLBACK_LOG"
echo "Backup directory: $BACKUP_DIR" >> "$ROLLBACK_LOG"
echo "Rollback plan: $ROLLBACK_PLAN" >> "$ROLLBACK_LOG"

# Create rollback marker file
echo "$(date)" > "rollback_in_progress_${DEPLOYMENT_ID}.marker"

echo "Pre-rollback script completed successfully"
echo "Backup directory: $BACKUP_DIR"
echo "Rollback plan: $ROLLBACK_PLAN"
echo "Rollback log: $ROLLBACK_LOG"
echo "Timestamp: $(date)"
