# TelegramMoneyBot v8.0 - User Manual

## 📖 Table of Contents
1. [System Overview](#system-overview)
2. [Getting Started](#getting-started)
3. [Core Features](#core-features)
4. [Trading Operations](#trading-operations)
5. [Monitoring & Alerts](#monitoring--alerts)
6. [Configuration](#configuration)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Features](#advanced-features)
9. [API Reference](#api-reference)
10. [Support](#support)

## 🚀 System Overview

TelegramMoneyBot v8.0 is an advanced AI-powered trading system that combines:
- **Multi-Timeframe Analysis**: H4→H1→M30→M15→M5→M1 hierarchical market analysis
- **Smart Money Concepts (SMC)**: CHOCH, BOS, Order Blocks, Liquidity analysis
- **M1 Execution Filters**: VWAP reclaim/loss, volume delta spike, ATR ratio, spread filter
- **Dynamic Trade Management**: Automated trade protection and intelligent exits
- **Real-time Monitoring**: Comprehensive system health and performance tracking

### Key Capabilities
- ✅ **12 Currency Pairs**: BTCUSDc, XAUUSDc, EURUSDc, GBPUSDc, USDJPYc, USDCHFc, AUDUSDc, USDCADc, NZDUSDc, EURJPYc, GBPJPYc, EURGBPc
- ✅ **Advanced AI Analysis**: GPT-4 powered market structure detection
- ✅ **Risk Management**: Dynamic stops, position sizing, circuit breakers
- ✅ **Performance Monitoring**: Real-time metrics and alerting
- ✅ **Shadow Mode**: Safe testing of new features alongside production

## 🏁 Getting Started

### Prerequisites
- Windows 10/11
- MetaTrader 5 (MT5) installed and configured
- Python 3.9+ with required packages
- Telegram Bot Token
- OpenAI API Key

### Installation
1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd TelegramMoneyBot.v7
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

4. **Initialize databases**
   ```bash
   python scripts/init_databases.py
   ```

### First Run
1. **Start the system**
   ```bash
   python trade_bot.py
   ```

2. **Verify components**
   - Check MT5 connection
   - Verify Telegram bot
   - Confirm database initialization

3. **Test trading**
   - Start with paper trading mode
   - Monitor system performance
   - Review trade decisions

## 🎯 Core Features

### Multi-Timeframe Analysis
The system analyzes market structure across multiple timeframes:

- **H4**: Primary trend direction
- **H1**: Major structure levels
- **M30**: Intermediate structure
- **M15**: Short-term structure
- **M5**: Entry confirmation
- **M1**: Execution precision

### Smart Money Concepts (SMC)
- **Break of Structure (BOS)**: Trend continuation signals
- **Change of Character (CHOCH)**: Trend reversal signals
- **Order Blocks**: Institutional order zones
- **Liquidity Analysis**: Support/resistance identification

### M1 Execution Filters
- **VWAP Reclaim/Loss**: Price relative to volume-weighted average
- **Volume Delta Spike**: Unusual volume activity
- **ATR Ratio**: Volatility-based filtering
- **Spread Filter**: Market condition assessment

## 📈 Trading Operations

### Starting a Trading Session
1. **Launch the system**
   ```bash
   python trade_bot.py
   ```

2. **Check system status**
   - Verify all components are green
   - Confirm market data feeds
   - Check risk parameters

3. **Begin analysis**
   - System automatically scans all configured pairs
   - Analyzes market structure
   - Identifies trading opportunities

### Trade Execution
The system automatically:
- Identifies high-probability setups
- Applies M1 confirmation filters
- Executes trades with proper risk management
- Manages positions dynamically

### Position Management
- **Dynamic Stops**: Adjusts stop-loss based on market structure
- **Partial Scaling**: Takes profits at key levels
- **Risk Controls**: Circuit breakers and position limits
- **Intelligent Exits**: AI-powered exit decisions

## 🔔 Monitoring & Alerts

### System Health Dashboard
Access real-time system status:
- Component health
- Performance metrics
- Trade statistics
- Alert notifications

### Alert Types
- **System Alerts**: Component failures, connectivity issues
- **Trading Alerts**: Trade executions, risk warnings
- **Performance Alerts**: Latency issues, resource usage
- **Market Alerts**: Volatility spikes, news events

### Monitoring Endpoints
- **Health Check**: `/health` - System status
- **Metrics**: `/metrics` - Performance data
- **Alerts**: `/alerts` - Active alerts
- **Trades**: `/trades` - Trade history

## ⚙️ Configuration

### Symbol Configuration
Each trading pair has optimized parameters:
```json
{
  "symbol": "BTCUSDc",
  "asset_type": "crypto",
  "vwap": {
    "session_anchor": "24h",
    "sigma_window": 60
  },
  "atr": {
    "period": 14,
    "multiplier": 1.5
  },
  "risk": {
    "max_lot_size": 0.01,
    "max_drawdown": 0.05
  }
}
```

### Risk Parameters
- **Position Sizing**: Maximum lot size per trade
- **Drawdown Limits**: Maximum acceptable loss
- **Circuit Breakers**: Automatic trading suspension
- **Staleness Controls**: Data quality monitoring

### Performance Tuning
- **Latency Targets**: <200ms p95 response time
- **Memory Usage**: <100MB for ring buffers
- **CPU Usage**: <80% under normal load
- **Database Performance**: <50ms query time

## 🔧 Troubleshooting

### Common Issues

#### System Won't Start
1. **Check dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Verify configuration**
   ```bash
   python scripts/validate_config.py
   ```

3. **Check logs**
   ```bash
   tail -f logs/system.log
   ```

#### MT5 Connection Issues
1. **Verify MT5 is running**
2. **Check account credentials**
3. **Confirm symbol availability**
4. **Test connection manually**

#### Telegram Bot Issues
1. **Verify bot token**
2. **Check bot permissions**
3. **Confirm webhook configuration**
4. **Test bot manually**

#### Database Issues
1. **Check database files**
2. **Verify permissions**
3. **Run database repair**
4. **Check disk space**

### Performance Issues

#### High Latency
1. **Check system resources**
2. **Review network connectivity**
3. **Optimize database queries**
4. **Adjust buffer sizes**

#### Memory Usage
1. **Monitor ring buffer usage**
2. **Check for memory leaks**
3. **Optimize data structures**
4. **Restart if necessary**

#### CPU Usage
1. **Check concurrent processes**
2. **Optimize algorithms**
3. **Adjust thread priorities**
4. **Review Numba performance**

### Recovery Procedures

#### System Recovery
1. **Stop all processes**
2. **Check system health**
3. **Restart components**
4. **Verify functionality**

#### Data Recovery
1. **Check backup files**
2. **Restore from backup**
3. **Verify data integrity**
4. **Resume operations**

## 🚀 Advanced Features

### Shadow Mode
Test new features safely:
- Run alongside production
- Compare performance
- Validate improvements
- Gradual rollout

### Decision Tracing
Track AI decisions:
- Feature vectors
- Decision hashes
- Performance analysis
- Error debugging

### Hot-Path Architecture
Optimized for speed:
- Ring buffers
- Async processing
- Memory-first design
- Sub-millisecond latency

### Multi-Symbol Optimization
Automatic parameter tuning:
- Win rate tracking
- Profit factor analysis
- Sharpe ratio monitoring
- Dynamic adjustment

## 📚 API Reference

### Core Endpoints

#### Health Check
```http
GET /health
```
Returns system health status

#### Metrics
```http
GET /metrics
```
Returns performance metrics

#### Configuration
```http
GET /config/{symbol}
POST /config/{symbol}
```
Manage symbol configuration

#### Shadow Mode
```http
GET /shadow/status
POST /shadow/enable
POST /shadow/disable
```
Control shadow mode

### Trading Endpoints

#### Trade History
```http
GET /trades
GET /trades/{symbol}
```
Retrieve trade history

#### Position Status
```http
GET /positions
GET /positions/{symbol}
```
Check current positions

#### Risk Metrics
```http
GET /risk
GET /risk/{symbol}
```
View risk metrics

### Monitoring Endpoints

#### System Status
```http
GET /status
GET /status/{component}
```
Component status

#### Alerts
```http
GET /alerts
POST /alerts/acknowledge
```
Alert management

#### Performance
```http
GET /performance
GET /performance/{metric}
```
Performance data

## 🆘 Support

### Documentation
- **User Manual**: This document
- **API Reference**: `/docs` endpoint
- **Configuration Guide**: `config/README.md`
- **Troubleshooting**: `docs/TROUBLESHOOTING.md`

### Getting Help
1. **Check logs**: `logs/system.log`
2. **Review documentation**: This manual
3. **Run diagnostics**: `python scripts/diagnostics.py`
4. **Contact support**: [Support Information]

### System Requirements
- **OS**: Windows 10/11
- **RAM**: 8GB minimum, 16GB recommended
- **CPU**: 4 cores minimum, 8 cores recommended
- **Storage**: 10GB free space
- **Network**: Stable internet connection

### Performance Expectations
- **Latency**: <200ms p95
- **Uptime**: >99.5%
- **Accuracy**: >80% win rate
- **Risk**: <5% maximum drawdown

---

**Version**: 8.0  
**Last Updated**: 2025-01-21  
**Support**: [Contact Information]
