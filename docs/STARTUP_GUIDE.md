# TelegramMoneyBot v8.0 - Startup Guide

## 🚀 **Quick Start (Recommended)**

### **Option 1: Automated Startup**
```bash
# Start the complete system automatically
python start_full_system.py
```
This will start all components in the correct order with monitoring.

### **Option 2: Manual Startup (Step by Step)**

#### **Step 1: Prerequisites**
```bash
# Install dependencies
pip install -r requirements.txt

# Create directories
mkdir logs data backups temp

# Set up environment variables
cp .env.example .env
# Edit .env with your actual credentials
```

#### **Step 2: Start Core System (Required)**
```bash
# 1. Main trading engine
python trade_bot.py

# 2. Hot-path processing
python desktop_agent.py

# 3. API server
python app/main_api.py

# 4. Telegram bot interface
python chatgpt_bot.py
```

#### **Step 3: Start Monitoring (Optional but Recommended)**
```bash
# Production monitoring
python production_monitoring_dashboard.py

# Alerting system
python production_alerting_system.py

# Log aggregation
python log_aggregation_analysis.py

# Performance metrics
python performance_metrics_collection.py
```

## 📋 **Required Files and Order**

### **Core System Files (Required)**
1. **trade_bot.py** - Main trading engine
2. **desktop_agent.py** - Hot-path processing
3. **app/main_api.py** - API server
4. **chatgpt_bot.py** - Telegram interface

### **Supporting Files (Optional)**
- **production_monitoring_dashboard.py** - Monitoring dashboard
- **production_alerting_system.py** - Alerting system
- **log_aggregation_analysis.py** - Log analysis
- **performance_metrics_collection.py** - Performance metrics

### **Configuration Files (Required)**
- **config/settings.py** - Main configuration
- **config/symbols/*.json** - Symbol configurations
- **monitoring_*_config.json** - Monitoring configurations
- **.env** - Environment variables

## 🔧 **System Architecture**

### **Core Components:**
- **Trading Engine** (trade_bot.py) - AI analysis and trade execution
- **Hot-Path Processing** (desktop_agent.py) - Real-time data processing
- **API Server** (app/main_api.py) - REST endpoints
- **Telegram Interface** (chatgpt_bot.py) - User interaction

### **Monitoring Systems:**
- **Dashboard** - Real-time system monitoring
- **Alerting** - Notification system
- **Log Aggregation** - Log analysis
- **Performance Metrics** - System performance tracking

## 🚨 **Important Notes**

### **Environment Variables Required:**
```bash
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_BOT_CHAT_ID=your_chat_id
OPENAI_API_KEY=your_openai_api_key
MT5_LOGIN=your_mt5_login
MT5_PASSWORD=your_mt5_password
MT5_SERVER=your_mt5_server
```

### **System Requirements:**
- Python 3.9+
- 8GB+ RAM
- 10GB+ disk space
- Windows 10/11
- MetaTrader 5 installed

### **Startup Order:**
1. **trade_bot.py** (Main trading engine)
2. **desktop_agent.py** (Hot-path processing)
3. **app/main_api.py** (API server)
4. **chatgpt_bot.py** (Telegram interface)
5. **Monitoring systems** (Optional)

## 🔍 **Verification**

### **Check System Status:**
```bash
# Check if all processes are running
python validate_production_readiness.py

# Monitor system health
python monitor_production_deployment.py
```

### **Health Checks:**
- **Trading System**: Check trade_bot.py logs
- **Hot-Path**: Check desktop_agent.py logs
- **API Server**: Check app/main_api.py logs
- **Telegram Bot**: Check chatgpt_bot.py logs
- **Monitoring**: Check monitoring system logs

## 🛑 **Shutdown**

### **Graceful Shutdown:**
```bash
# Press Ctrl+C in each terminal
# Or use the automated shutdown in start_full_system.py
```

### **Emergency Shutdown:**
```bash
# Stop all Python processes
taskkill /f /im python.exe
```

## 📊 **Monitoring**

### **System Health:**
- **Dashboard**: http://localhost:8080/health
- **Metrics**: http://localhost:8080/metrics
- **Alerts**: http://localhost:8080/alerts

### **Log Files:**
- **System Logs**: logs/system.log
- **Trading Logs**: logs/trading.log
- **Performance Logs**: logs/performance.log

## 🆘 **Troubleshooting**

### **Common Issues:**
1. **Missing Environment Variables** - Check .env file
2. **MT5 Connection Issues** - Verify MT5 is running and logged in
3. **Telegram Bot Issues** - Check bot token and permissions
4. **Database Issues** - Check database files and permissions

### **Support:**
- **Documentation**: docs/documentation_training/
- **Troubleshooting**: docs/documentation_training/TROUBLESHOOTING_GUIDE.md
- **User Manual**: docs/documentation_training/USER_MANUAL.md

---

**Version**: 8.0  
**Last Updated**: 2025-01-21  
**Status**: Production Ready
