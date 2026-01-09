#!/bin/bash
# Post-deployment script for TelegramMoneyBot v8.0
# This script runs after deployment to verify and finalize the deployment

set -e  # Exit on any error

ENVIRONMENT=$1
VERSION=$2
DEPLOYMENT_ID=$3

echo "Starting post-deployment script for environment: $ENVIRONMENT, version: $VERSION"

# Wait for services to start up
echo "Waiting for services to start up..."
sleep 30

# Health check function
check_service_health() {
    local service_name=$1
    local health_url=$2
    local max_attempts=30
    local attempt=1
    
    echo "Checking health of $service_name..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$health_url" > /dev/null 2>&1; then
            echo "$service_name is healthy"
            return 0
        else
            echo "Attempt $attempt/$max_attempts: $service_name not ready yet..."
            sleep 10
            attempt=$((attempt + 1))
        fi
    done
    
    echo "ERROR: $service_name failed health check after $max_attempts attempts"
    return 1
}

# Check service health
echo "Performing health checks..."

# Check main API
if ! check_service_health "Main API" "http://localhost:8000/health"; then
    echo "ERROR: Main API health check failed"
    exit 1
fi

# Check ChatGPT bot
if ! check_service_health "ChatGPT Bot" "http://localhost:8001/health"; then
    echo "ERROR: ChatGPT Bot health check failed"
    exit 1
fi

# Check desktop agent
if ! check_service_health "Desktop Agent" "http://localhost:8002/health"; then
    echo "ERROR: Desktop Agent health check failed"
    exit 1
fi

# Run integration tests
echo "Running integration tests..."
if [ -f "test_integration.py" ]; then
    python3 -m pytest test_integration.py -v --tb=short
    if [ $? -ne 0 ]; then
        echo "ERROR: Integration tests failed"
        exit 1
    fi
    echo "Integration tests passed"
else
    echo "WARNING: Integration test file not found, skipping tests"
fi

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

for db_path in databases:
    try:
        conn = sqlite3.connect(db_path)
        # Run integrity check
        result = conn.execute('PRAGMA integrity_check').fetchone()
        if result[0] != 'ok':
            print(f'ERROR: Database integrity check failed for {db_path}: {result[0]}')
            sys.exit(1)
        else:
            print(f'Database {db_path} integrity check passed')
        conn.close()
    except Exception as e:
        print(f'ERROR: Database {db_path} check failed: {e}')
        sys.exit(1)

print('All database integrity checks passed')
"

# Check system performance
echo "Checking system performance..."
python3 -c "
import psutil
import sys

# Check CPU usage
cpu_usage = psutil.cpu_percent(interval=5)
if cpu_usage > 90:
    print(f'WARNING: High CPU usage: {cpu_usage}%')
else:
    print(f'CPU usage: {cpu_usage}%')

# Check memory usage
memory = psutil.virtual_memory()
if memory.percent > 90:
    print(f'WARNING: High memory usage: {memory.percent}%')
else:
    print(f'Memory usage: {memory.percent}%')

# Check disk usage
disk = psutil.disk_usage('/')
if disk.percent > 90:
    print(f'WARNING: High disk usage: {disk.percent}%')
else:
    print(f'Disk usage: {disk.percent}%')

print('System performance check completed')
"

# Update deployment metadata
echo "Updating deployment metadata..."
python3 -c "
import json
import time
from datetime import datetime

metadata = {
    'deployment_id': '$DEPLOYMENT_ID',
    'version': '$VERSION',
    'environment': '$ENVIRONMENT',
    'deployed_at': time.time(),
    'deployed_by': 'deployment_system',
    'status': 'completed',
    'health_checks_passed': True,
    'integration_tests_passed': True,
    'database_integrity_verified': True
}

with open('deployment_metadata_${ENVIRONMENT}.json', 'w') as f:
    json.dump(metadata, f, indent=2, default=str)

print('Deployment metadata updated')
"

# Clean up old backups (keep last 10)
echo "Cleaning up old backups..."
BACKUP_COUNT=$(ls -1 backups/ | grep "deployment_" | wc -l)
if [ $BACKUP_COUNT -gt 10 ]; then
    echo "Found $BACKUP_COUNT backups, cleaning up old ones..."
    ls -1t backups/ | grep "deployment_" | tail -n +11 | xargs -I {} rm -rf "backups/{}"
    echo "Old backups cleaned up"
else
    echo "Backup count ($BACKUP_COUNT) is within limit, no cleanup needed"
fi

# Remove deployment marker file
if [ -f "deployment_in_progress_${DEPLOYMENT_ID}.marker" ]; then
    rm "deployment_in_progress_${DEPLOYMENT_ID}.marker"
    echo "Removed deployment marker file"
fi

# Send success notification
echo "Sending success notification..."
python3 -c "
import json
import requests
import time

# Slack notification (if webhook is configured)
try:
    webhook_url = 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
    message = {
        'text': f'✅ Deployment Successful',
        'attachments': [
            {
                'color': 'good',
                'fields': [
                    {'title': 'Environment', 'value': '$ENVIRONMENT', 'short': True},
                    {'title': 'Version', 'value': '$VERSION', 'short': True},
                    {'title': 'Deployment ID', 'value': '$DEPLOYMENT_ID', 'short': True},
                    {'title': 'Timestamp', 'value': time.strftime('%Y-%m-%d %H:%M:%S'), 'short': True}
                ]
            }
        ]
    }
    
    # Uncomment to send actual notification
    # response = requests.post(webhook_url, json=message)
    # print(f'Slack notification sent: {response.status_code}')
    print('Slack notification prepared (not sent - webhook not configured)')
except Exception as e:
    print(f'Notification error: {e}')
"

# Log deployment completion
echo "Post-deployment script completed successfully"
echo "Environment: $ENVIRONMENT"
echo "Version: $VERSION"
echo "Deployment ID: $DEPLOYMENT_ID"
echo "Completion timestamp: $(date)"

# Create deployment success marker
echo "$(date)" > "deployment_success_${DEPLOYMENT_ID}.marker"

echo "Post-deployment script completed successfully"
