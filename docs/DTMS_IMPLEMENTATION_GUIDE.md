# DTMS Implementation Guide
## Defensive Trade Management System

### Overview

The DTMS (Defensive Trade Management System) is a comprehensive, institutional-grade trade management system designed to protect trading positions through adaptive monitoring, intelligent state management, and automated defensive actions.

### Architecture

```
DTMS System Architecture
├── Core Components
│   ├── Data Manager (Rolling Windows & Incremental Fetch)
│   ├── Regime Classifier (Market State Detection)
│   ├── Signal Scorer (Hierarchical Weighted Scoring)
│   ├── State Machine (FSM Logic & Transitions)
│   ├── Action Executor (Trade Actions)
│   └── DTMS Engine (Main Orchestrator)
├── Integration Layer
│   ├── MT5 Adapter
│   ├── Binance Adapter
│   └── Telegram Adapter
└── Configuration
    ├── Adaptive Thresholds
    ├── Signal Weights
    └── State Transitions
```

### Key Features

#### 1. **Adaptive Monitoring**
- **Fast Check**: 30-second intervals for critical signals
- **Deep Check**: 15-minute intervals for comprehensive analysis
- **Event-Driven**: Triggers deep checks on significant market moves
- **Cooldown Management**: Prevents excessive deep checks

#### 2. **Market Regime Classification**
- **Session Detection**: Asian, London, NY, Overlap
- **Volatility Classification**: Low, Normal, High (based on ATR ratio)
- **Structure Classification**: Range, Trend (based on Bollinger Band width)
- **Adaptive Thresholds**: Adjusts sensitivity based on market conditions

#### 3. **Hierarchical Signal Scoring**
- **Structure Signals (±3)**: BOS/CHOCH - highest authority
- **VWAP + Volume (±2)**: Institutional flow signals
- **Momentum (±2)**: RSI + MACD trend strength
- **EMA Alignment (±1.5)**: Trend context
- **Delta Pressure (±1)**: Order flow pressure
- **Candle Conviction (±0.5 to ±2)**: Micro confirmation

#### 4. **State Machine Management**
- **HEALTHY**: Normal monitoring, trail SL on BOS
- **WARNING_L1**: Tighten SL, start flat timer
- **WARNING_L2**: Partial close 50%, move SL to breakeven
- **HEDGED**: Hedge opened, maintain net risk ≤ 0
- **RECOVERING**: BOS resumed, re-add position
- **CLOSED**: Trade closed (terminal state)

#### 5. **Automated Actions**
- **SL Adjustments**: Tighten, move to breakeven
- **Partial Closes**: Risk reduction at key levels
- **Hedge Management**: Open/close opposite positions
- **Position Recovery**: Re-add closed positions on BOS resume

### Installation & Setup

#### 1. **File Structure**
```
dtms/
├── dtms_config.py                 # Configuration and settings
├── dtms_core/
│   ├── __init__.py
│   ├── data_manager.py           # Rolling windows & data management
│   ├── regime_classifier.py      # Market regime detection
│   ├── signal_scorer.py          # Hierarchical signal scoring
│   ├── state_machine.py          # FSM logic & transitions
│   ├── action_executor.py        # Trade action execution
│   └── dtms_engine.py            # Main orchestrator
├── dtms_integration/
│   ├── __init__.py
│   ├── mt5_adapter.py            # MT5 service wrapper
│   ├── binance_adapter.py        # Binance service wrapper
│   └── telegram_adapter.py       # Telegram service wrapper
├── dtms_integration.py           # Main integration interface
├── test_dtms_system.py           # Comprehensive test suite
└── DTMS_IMPLEMENTATION_GUIDE.md  # This documentation
```

#### 2. **Dependencies**
```python
# Core dependencies
import pandas as pd
import numpy as np
import logging
import time
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

# External services (existing in your bot)
# - MT5 service
# - Binance service (optional)
# - Telegram service (optional)
```

#### 3. **Integration with Existing Bot**

```python
# In your main bot startup
from dtms_integration import initialize_dtms, start_dtms_monitoring

# Initialize DTMS
initialize_dtms(mt5_service, binance_service, telegram_service)
start_dtms_monitoring()

# In your main monitoring loop
from dtms_integration import run_dtms_monitoring_cycle

async def main_monitoring_loop():
    while True:
        # Your existing monitoring code
        await your_existing_monitoring()
        
        # DTMS monitoring cycle
        await run_dtms_monitoring_cycle()
        
        await asyncio.sleep(30)  # 30-second cycle
```

#### 4. **Adding Trades to DTMS**

```python
from dtms_integration import add_trade_to_dtms

# After placing a trade
ticket = mt5_service.place_order(...)
if ticket:
    add_trade_to_dtms(
        ticket=ticket,
        symbol="BTCUSD",
        direction="BUY",
        entry_price=100.0,
        volume=0.1,
        stop_loss=99.0,
        take_profit=102.0
    )
```

#### 5. **Removing Trades from DTMS**

```python
from dtms_integration import remove_trade_from_dtms

# When closing a trade
remove_trade_from_dtms(ticket)
```

### Configuration

#### 1. **Adaptive Thresholds**
```python
# Base thresholds per symbol
vwap_base = {
    'XAUUSD': 0.001,     # 0.10%
    'BTCUSDT': 0.002,    # 0.20%
    'EURUSD': 0.0005,    # 0.05%
    'GBPUSD': 0.0005,    # 0.05%
    'USDJPY': 0.0007,    # 0.07%
    'GBPJPY': 0.0007,    # 0.07%
    'EURJPY': 0.0007,    # 0.07%
}

# Session multipliers
session_multipliers = {
    'Asian': 1.5,        # Higher threshold (ignore noise)
    'London': 1.0,       # Base sensitivity
    'NY': 0.8,           # Faster reaction
    'Overlap': 0.7       # Most sensitive
}

# Volatility multipliers
volatility_multipliers = {
    'low': 1.4,          # Low vol → need stronger move
    'normal': 1.0,       # Base multiplier
    'high': 0.8          # High vol → react faster
}
```

#### 2. **Signal Weights**
```python
# Base signal weights
SIGNAL_WEIGHTS = {
    'structure': 3.0,           # BOS/CHOCH - highest authority
    'vwap_volume': 2.0,         # VWAP flip + volume flip
    'momentum': 2.0,            # RSI + MACD momentum
    'ema_alignment': 1.5,       # EMA50 vs EMA200 slope
    'delta_pressure': 1.0,      # Order flow delta
    'candle_conviction': 1.0    # Conviction bar patterns
}

# Adaptive weights for different market regimes
ADAPTIVE_WEIGHTS = {
    'RANGE': {
        'structure': 0.7,       # Structure less reliable in ranges
        'vwap_volume': 1.3,     # VWAP more important in ranges
        'momentum': 1.0,
        'ema_alignment': 0.8,
        'delta_pressure': 1.2,
        'candle_conviction': 1.1
    },
    'HIGH_VOLATILITY': {
        'structure': 1.2,       # Structure more reliable in high vol
        'vwap_volume': 0.9,
        'momentum': 0.8,        # Momentum signals more noisy
        'ema_alignment': 1.0,
        'delta_pressure': 1.1,
        'candle_conviction': 0.9
    }
}
```

#### 3. **State Transitions**
```python
# State transition thresholds
state_transitions = {
    'HEALTHY_to_WARNING_L1': -2,
    'WARNING_L1_to_WARNING_L2': -4,
    'WARNING_L2_to_HEDGED': -6,
    'hedge_confluence_trigger': -6,  # Score <= -6 OR (VWAP flip + volume flip)
    'recovery_hysteresis': {
        'WARNING_L1_to_HEALTHY': 0,    # Need score >= 0
        'WARNING_L2_to_WARNING_L1': -2  # Need score >= -2
    }
}
```

### Usage Examples

#### 1. **Basic Integration**
```python
# Initialize DTMS
from dtms_integration import initialize_dtms, start_dtms_monitoring

initialize_dtms(mt5_service, binance_service, telegram_service)
start_dtms_monitoring()

# Add trade to monitoring
add_trade_to_dtms(12345, "BTCUSD", "BUY", 100.0, 0.1)

# Check system status
status = get_dtms_system_status()
print(f"Active trades: {status['active_trades']}")
```

#### 2. **Advanced Configuration**
```python
# Custom configuration
from dtms_config import DTMSConfig

custom_config = DTMSConfig()
custom_config.thresholds['vwap_base']['BTCUSD'] = 0.003  # 0.30%
custom_config.adaptive_multipliers['session']['Asian'] = 2.0  # Higher threshold

# Use custom config
from dtms_core.dtms_engine import DTMSEngine

engine = DTMSEngine(mt5_service, binance_service, telegram_service)
engine.config = custom_config
```

#### 3. **Monitoring and Alerts**
```python
# Get trade status
trade_status = get_dtms_trade_status(12345)
print(f"State: {trade_status['state']}")
print(f"Score: {trade_status['current_score']}")
print(f"Warnings: {trade_status['warnings']}")

# Get action history
actions = get_dtms_action_history(12345)
for action in actions:
    print(f"Action: {action['action_type']}, Success: {action['success']}")
```

### Testing

#### 1. **Run Test Suite**
```bash
python test_dtms_system.py
```

#### 2. **Test Coverage**
- Data Manager: Rolling windows, VWAP calculation, data integrity
- Regime Classifier: Session detection, volatility classification, structure detection
- Signal Scorer: Hierarchical scoring, adaptive weights, confluence detection
- State Machine: State transitions, warning counters, timers
- Action Executor: Trade actions, MT5 integration, notifications
- DTMS Engine: End-to-end monitoring, performance metrics

#### 3. **Performance Tests**
- Signal scoring: 10 operations in <1 second
- State machine: 50 trade updates in <2 seconds
- Memory usage: Efficient rolling windows
- CPU usage: Optimized calculations

### Monitoring & Maintenance

#### 1. **System Health**
```python
# Get comprehensive system status
status = get_dtms_system_status()

print(f"Monitoring Active: {status['monitoring_active']}")
print(f"Uptime: {status['uptime_human']}")
print(f"Active Trades: {status['active_trades']}")
print(f"Performance: {status['performance']}")
print(f"Data Health: {status['data_health']}")
```

#### 2. **Performance Metrics**
- Fast checks per hour
- Deep checks per hour
- Actions executed
- State transitions
- Data integrity status

#### 3. **Logging**
```python
# DTMS uses standard Python logging
import logging

# Set log level
logging.getLogger('dtms_core').setLevel(logging.DEBUG)

# Log files
# - dtms_data.log: Data management operations
# - dtms_signals.log: Signal scoring and analysis
# - dtms_states.log: State machine transitions
# - dtms_actions.log: Action execution
```

### Troubleshooting

#### 1. **Common Issues**

**Issue**: DTMS not monitoring trades
**Solution**: Check if `start_dtms_monitoring()` was called and `monitoring_active` is True

**Issue**: No state transitions occurring
**Solution**: Verify signal scoring is working and thresholds are appropriate

**Issue**: Actions not executing
**Solution**: Check MT5 service connection and action executor logs

**Issue**: High CPU usage
**Solution**: Adjust monitoring intervals or reduce number of monitored trades

#### 2. **Debug Mode**
```python
# Enable debug logging
import logging
logging.getLogger('dtms_core').setLevel(logging.DEBUG)
logging.getLogger('dtms_integration').setLevel(logging.DEBUG)

# Check system status
status = get_dtms_system_status()
print(f"System Status: {status}")
```

#### 3. **Performance Optimization**
- Reduce monitoring frequency for non-critical trades
- Use cached indicators where possible
- Optimize data window sizes
- Monitor memory usage

### Advanced Features

#### 1. **Custom Signal Weights**
```python
# Override signal weights for specific conditions
from dtms_core.signal_scorer import DTMSSignalScorer

scorer = DTMSSignalScorer()
scorer.base_weights['structure'] = 4.0  # Increase structure weight
scorer.base_weights['momentum'] = 1.5   # Decrease momentum weight
```

#### 2. **Custom State Transitions**
```python
# Override state transition thresholds
from dtms_core.state_machine import DTMSStateMachine

state_machine = DTMSStateMachine()
state_machine.config.state_transitions['HEALTHY_to_WARNING_L1'] = -1.5  # More sensitive
```

#### 3. **Custom Actions**
```python
# Add custom action types
from dtms_core.action_executor import DTMSActionExecutor

class CustomActionExecutor(DTMSActionExecutor):
    def _execute_custom_action(self, action, trade_data):
        # Custom action implementation
        pass
```

### Security & Risk Management

#### 1. **Safety Rails**
- Daily loss limits
- Hourly loss limits
- Maximum consecutive stops
- News blackout periods
- Spread protection
- Data integrity checks

#### 2. **Position Limits**
- Maximum open positions
- Maximum position size
- Maximum risk per trade
- Maximum daily risk

#### 3. **Error Handling**
- Graceful degradation
- Automatic recovery
- Error notifications
- Fallback mechanisms

### Future Enhancements

#### 1. **Machine Learning Integration**
- Adaptive threshold learning
- Pattern recognition
- Predictive state transitions
- Risk assessment models

#### 2. **Advanced Analytics**
- Performance attribution
- Risk decomposition
- Correlation analysis
- Stress testing

#### 3. **Multi-Asset Support**
- Cross-asset correlation
- Portfolio-level risk management
- Asset allocation optimization
- Diversification metrics

### Conclusion

The DTMS system provides a robust, institutional-grade framework for defensive trade management. Its adaptive monitoring, intelligent state management, and automated actions help protect trading positions while maintaining flexibility for different market conditions.

The system is designed to be:
- **Modular**: Easy to integrate with existing systems
- **Configurable**: Adaptable to different trading styles
- **Scalable**: Handles multiple trades efficiently
- **Reliable**: Comprehensive error handling and recovery
- **Transparent**: Detailed logging and monitoring

For support or questions, refer to the test suite and logging output for detailed diagnostics.
