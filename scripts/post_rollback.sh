#!/bin/bash
# Post-rollback script for TelegramMoneyBot v8.0
# This script runs after rollback to verify and finalize the rollback

set -e  # Exit on any error

ENVIRONMENT=$1
DEPLOYMENT_ID=$2
ROLLBACK_ID=$3

echo "Starting post-rollback script for environment: $ENVIRONMENT, deployment: $DEPLOYMENT_ID"

# Wait for services to start up after rollback
echo "Waiting for services to start up after rollback..."
sleep 30

# Health check function
check_service_health() {
    local service_name=$1
    local health_url=$2
    local max_attempts=30
    local attempt=1
    
    echo "Checking health of $service_name after rollback..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$health_url" > /dev/null 2>&1; then
            echo "$service_name is healthy after rollback"
            return 0
        else
            echo "Attempt $attempt/$max_attempts: $service_name not ready yet..."
            sleep 10
            attempt=$((attempt + 1))
        fi
    done
    
    echo "ERROR: $service_name failed health check after rollback"
    return 1
}

# Check service health after rollback
echo "Performing health checks after rollback..."

# Check main API
if ! check_service_health "Main API" "http://localhost:8000/health"; then
    echo "ERROR: Main API health check failed after rollback"
    exit 1
fi

# Check ChatGPT bot
if ! check_service_health "ChatGPT Bot" "http://localhost:8001/health"; then
    echo "ERROR: ChatGPT Bot health check failed after rollback"
    exit 1
fi

# Check desktop agent
if ! check_service_health "Desktop Agent" "http://localhost:8002/health"; then
    echo "ERROR: Desktop Agent health check failed after rollback"
    exit 1
fi

# Run basic functionality tests
echo "Running basic functionality tests..."
python3 -c "
import requests
import sys

# Test main API endpoints
try:
    # Test health endpoint
    response = requests.get('http://localhost:8000/health', timeout=10)
    if response.status_code != 200:
        print(f'ERROR: Main API health check failed: {response.status_code}')
        sys.exit(1)
    print('Main API health check passed')
    
    # Test other endpoints if available
    endpoints = ['/metrics', '/config', '/status']
    for endpoint in endpoints:
        try:
            response = requests.get(f'http://localhost:8000{endpoint}', timeout=5)
            if response.status_code == 200:
                print(f'Main API {endpoint} endpoint accessible')
            else:
                print(f'WARNING: Main API {endpoint} endpoint returned {response.status_code}')
        except Exception as e:
            print(f'WARNING: Main API {endpoint} endpoint not accessible: {e}')
    
except Exception as e:
    print(f'ERROR: Main API functionality test failed: {e}')
    sys.exit(1)

# Test ChatGPT bot
try:
    response = requests.get('http://localhost:8001/health', timeout=10)
    if response.status_code != 200:
        print(f'ERROR: ChatGPT Bot health check failed: {response.status_code}')
        sys.exit(1)
    print('ChatGPT Bot health check passed')
except Exception as e:
    print(f'ERROR: ChatGPT Bot functionality test failed: {e}')
    sys.exit(1)

# Test desktop agent
try:
    response = requests.get('http://localhost:8002/health', timeout=10)
    if response.status_code != 200:
        print(f'ERROR: Desktop Agent health check failed: {response.status_code}')
        sys.exit(1)
    print('Desktop Agent health check passed')
except Exception as e:
    print(f'ERROR: Desktop Agent functionality test failed: {e}')
    sys.exit(1)

print('All basic functionality tests passed')
"

# Check database integrity after rollback
echo "Checking database integrity after rollback..."
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
            print(f'Database {db_path} integrity check passed after rollback')
        conn.close()
    except Exception as e:
        print(f'ERROR: Database {db_path} check failed after rollback: {e}')
        sys.exit(1)

print('All database integrity checks passed after rollback')
"

# Check system performance after rollback
echo "Checking system performance after rollback..."
python3 -c "
import psutil
import sys

# Check CPU usage
cpu_usage = psutil.cpu_percent(interval=5)
print(f'CPU usage after rollback: {cpu_usage}%')

# Check memory usage
memory = psutil.virtual_memory()
print(f'Memory usage after rollback: {memory.percent}%')

# Check disk usage
disk = psutil.disk_usage('/')
print(f'Disk usage after rollback: {disk.percent}%')

# Check if performance is acceptable
if cpu_usage > 95:
    print(f'WARNING: High CPU usage after rollback: {cpu_usage}%')
elif memory.percent > 95:
    print(f'WARNING: High memory usage after rollback: {memory.percent}%')
elif disk.percent > 95:
    print(f'WARNING: High disk usage after rollback: {disk.percent}%')
else:
    print('System performance is acceptable after rollback')
"

# Update rollback metadata
echo "Updating rollback metadata..."
python3 -c "
import json
import time
from datetime import datetime

# Load existing rollback plan
try:
    with open('rollback_plan_${DEPLOYMENT_ID}.json', 'r') as f:
        plan = json.load(f)
except FileNotFoundError:
    plan = {}

# Update with rollback completion info
plan.update({
    'rollback_completed_at': time.time(),
    'rollback_status': 'completed',
    'health_checks_passed': True,
    'functionality_tests_passed': True,
    'database_integrity_verified': True,
    'performance_acceptable': True
})

# Save updated plan
with open('rollback_plan_${DEPLOYMENT_ID}.json', 'w') as f:
    json.dump(plan, f, indent=2, default=str)

print('Rollback metadata updated')
"

# Clean up rollback marker files
if [ -f "rollback_in_progress_${DEPLOYMENT_ID}.marker" ]; then
    rm "rollback_in_progress_${DEPLOYMENT_ID}.marker"
    echo "Removed rollback marker file"
fi

# Create rollback success marker
echo "$(date)" > "rollback_success_${DEPLOYMENT_ID}.marker"

# Send rollback completion notification
echo "Sending rollback completion notification..."
python3 -c "
import json
import requests
import time

# Slack notification (if webhook is configured)
try:
    webhook_url = 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
    message = {
        'text': f'🔄 Rollback Completed',
        'attachments': [
            {
                'color': 'warning',
                'fields': [
                    {'title': 'Environment', 'value': '$ENVIRONMENT', 'short': True},
                    {'title': 'Deployment ID', 'value': '$DEPLOYMENT_ID', 'short': True},
                    {'title': 'Rollback ID', 'value': '$ROLLBACK_ID', 'short': True},
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

# Log rollback completion
ROLLBACK_LOG="logs/rollbacks/rollback_${DEPLOYMENT_ID}_$(date +%Y%m%d_%H%M%S).log"
echo "Rollback completed at $(date)" >> "$ROLLBACK_LOG"
echo "Environment: $ENVIRONMENT" >> "$ROLLBACK_LOG"
echo "Deployment ID: $DEPLOYMENT_ID" >> "$ROLLBACK_LOG"
echo "Rollback ID: $ROLLBACK_ID" >> "$ROLLBACK_LOG"
echo "Status: SUCCESS" >> "$ROLLBACK_LOG"

echo "Post-rollback script completed successfully"
echo "Environment: $ENVIRONMENT"
echo "Deployment ID: $DEPLOYMENT_ID"
echo "Rollback ID: $ROLLBACK_ID"
echo "Completion timestamp: $(date)"
echo "Rollback log: $ROLLBACK_LOG"

echo "Post-rollback script completed successfully"
