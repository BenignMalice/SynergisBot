#!/bin/bash
# Pre-deployment script for TelegramMoneyBot v8.0
# This script runs before deployment to prepare the environment

set -e  # Exit on any error

ENVIRONMENT=$1
VERSION=$2
DEPLOYMENT_ID=$3

echo "Starting pre-deployment script for environment: $ENVIRONMENT, version: $VERSION"

# Create logs directory
mkdir -p logs
mkdir -p backups

# Check system requirements
echo "Checking system requirements..."

# Check available disk space (minimum 2GB)
AVAILABLE_SPACE=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
if [ "$AVAILABLE_SPACE" -lt 2 ]; then
    echo "ERROR: Insufficient disk space. Available: ${AVAILABLE_SPACE}GB, Required: 2GB"
    exit 1
fi

# Check available memory (minimum 4GB)
AVAILABLE_MEMORY=$(free -g | awk 'NR==2 {print $7}')
if [ "$AVAILABLE_MEMORY" -lt 4 ]; then
    echo "WARNING: Low available memory. Available: ${AVAILABLE_MEMORY}GB, Recommended: 4GB"
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.8.0"
if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "ERROR: Python version $PYTHON_VERSION is below required version $REQUIRED_VERSION"
    exit 1
fi

# Check required Python packages
echo "Checking Python dependencies..."
python3 -c "
import sys
required_packages = [
    'fastapi', 'uvicorn', 'sqlite3', 'asyncio', 'pandas', 'numpy',
    'MetaTrader5', 'requests', 'websockets', 'psutil'
]
missing_packages = []
for package in required_packages:
    try:
        __import__(package)
    except ImportError:
        missing_packages.append(package)

if missing_packages:
    print(f'ERROR: Missing required packages: {missing_packages}')
    sys.exit(1)
else:
    print('All required packages are available')
"

# Check database connectivity
echo "Checking database connectivity..."
for db in data/unified_tick_pipeline.db data/analysis_data.db data/system_logs.db; do
    if [ -f "$db" ]; then
        python3 -c "
import sqlite3
try:
    conn = sqlite3.connect('$db')
    conn.execute('SELECT 1')
    conn.close()
    print('Database $db is accessible')
except Exception as e:
    print(f'ERROR: Database $db is not accessible: {e}')
    exit(1)
"
    else
        echo "WARNING: Database file $db not found"
    fi
done

# Check if services are running (for production)
if [ "$ENVIRONMENT" = "production" ]; then
    echo "Checking if services are running..."
    
    # Check main API
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "Main API is running"
    else
        echo "WARNING: Main API is not responding"
    fi
    
    # Check ChatGPT bot
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo "ChatGPT bot is running"
    else
        echo "WARNING: ChatGPT bot is not responding"
    fi
    
    # Check desktop agent
    if curl -s http://localhost:8002/health > /dev/null 2>&1; then
        echo "Desktop agent is running"
    else
        echo "WARNING: Desktop agent is not responding"
    fi
fi

# Create backup directory for this deployment
BACKUP_DIR="backups/deployment_${DEPLOYMENT_ID}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Created backup directory: $BACKUP_DIR"

# Backup current configuration
echo "Backing up current configuration..."
cp -r config/ "$BACKUP_DIR/" 2>/dev/null || echo "No config directory to backup"
cp *.json "$BACKUP_DIR/" 2>/dev/null || echo "No JSON config files to backup"

# Backup current code
echo "Backing up current code..."
cp -r app/ "$BACKUP_DIR/" 2>/dev/null || echo "No app directory to backup"
cp -r infra/ "$BACKUP_DIR/" 2>/dev/null || echo "No infra directory to backup"
cp -r domain/ "$BACKUP_DIR/" 2>/dev/null || echo "No domain directory to backup"
cp -r handlers/ "$BACKUP_DIR/" 2>/dev/null || echo "No handlers directory to backup"
cp *.py "$BACKUP_DIR/" 2>/dev/null || echo "No Python files to backup"

# Backup databases
echo "Backing up databases..."
mkdir -p "$BACKUP_DIR/databases"
for db in data/*.db data/*.sqlite; do
    if [ -f "$db" ]; then
        cp "$db" "$BACKUP_DIR/databases/"
        echo "Backed up database: $db"
    fi
done

# Set environment variables
export DEPLOYMENT_ID="$DEPLOYMENT_ID"
export ENVIRONMENT="$ENVIRONMENT"
export VERSION="$VERSION"
export BACKUP_DIR="$BACKUP_DIR"

# Log pre-deployment status
echo "Pre-deployment script completed successfully"
echo "Environment: $ENVIRONMENT"
echo "Version: $VERSION"
echo "Deployment ID: $DEPLOYMENT_ID"
echo "Backup directory: $BACKUP_DIR"
echo "Timestamp: $(date)"

# Create deployment marker file
echo "$(date)" > "deployment_in_progress_${DEPLOYMENT_ID}.marker"

echo "Pre-deployment script completed successfully"
