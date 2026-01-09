# Automated Loss-Cutting System

## Overview

The automated loss-cutting system implements intelligent early exit logic for losing trades using multi-factor analysis. It combines confluence risk scoring, multi-timeframe invalidation, momentum relapse detection, wick reversal patterns, time-decay backstop, R-threshold ladder, and spread/ATR gating to make informed decisions about cutting losses early.

## Key Features

### 1. Confluence Risk Scoring (0-1 scale)
- Analyzes momentum factors (RSI, MACD, ADX)
- Evaluates volatility factors (ATR, Bollinger Bands)
- Assesses volume factors (VWAP, volume divergence)
- Computes weighted risk score for early exit decisions

### 2. Multi-Timeframe Invalidation
- Detects EMA stack flips (price vs EMA20, EMA20 vs EMA50)
- Identifies SAR flips
- Monitors Heikin Ashi color changes
- Requires cross-TF agreement (M5 + M15; optional H1)

### 3. Momentum Relapse Logic
- ADX rollover from high
- RSI cross of 50
- MACD histogram shrinking
- Triggers tighten-to-BE-first, then full exit

### 4. Wick Reversal Detection
- Long opposing wicks at strong S/R levels
- Rejection patterns at resistance (long) or support (short)
- Context-aware (near BB edges, VWAP, S/R zones)

### 5. R-Threshold Ladder
- **-0.5R**: Tighten to BE ± 0.2R buffer
- **-0.8R**: Early exit if risk score ≥ threshold
- Progressive actions based on loss magnitude

### 6. Spread/ATR Gating
- Only closes when spread/ATR < cap (default 0.40)
- During high spread, tightens SL first
- Defers market close until spread normalizes

### 7. Time-Decay Backstop
- Session-aware thresholds:
  - High volatility: 60 minutes
  - Medium volatility: 120 minutes
  - Low volatility: 180 minutes
- Closes if trade stays ≤ 0R for N bars/mins

### 8. Reliable Closing
- Uses IOC (Immediate or Cancel) filling mode
- Retry logic with exponential backoff (300ms, 600ms, 900ms)
- Escalates deviation each retry
- Records per-ticket "closing" flag to avoid duplicates

## Configuration

All configuration options are in `config.py`:

```python
# Early exit thresholds
POS_EARLY_EXIT_R = -0.8  # R-multiple threshold for early exit
POS_EARLY_EXIT_SCORE = 0.65  # Confluence risk score threshold

# Time-based backstop
POS_TIME_BACKSTOP_ENABLE = True
POS_TIME_BACKSTOP_BARS = 10  # Bars to wait before time decay

# Multi-timeframe invalidation
POS_INVALIDATION_EXIT_ENABLE = True

# Spread/ATR gating
POS_SPREAD_ATR_CLOSE_CAP = 0.40  # Max spread/ATR ratio for closing

# Closing reliability
POS_CLOSE_RETRY_MAX = 3  # Max retry attempts
POS_CLOSE_BACKOFF_MS = "300,600,900"  # Exponential backoff delays
```

## Usage Example

### Basic Integration

```python
from infra.loss_cutter import LossCutter
from infra.mt5_service import MT5Service

# Initialize
mt5_service = MT5Service()
mt5_service.connect()
loss_cutter = LossCutter(mt5_service)

# Check if position should be cut
position = mt5.positions_get(ticket=12345)[0]
features = {
    "rsi": 75,
    "adx": 25,
    "macd_hist": 0.005,
    "atr": 10.0,
    "close": 2000.0,
    "ema20": 1995,
    "ema50": 1990,
    "ema200": 1980,
    "sar": 1985,
    # ... other features
}

decision = loss_cutter.should_cut_loss(
    position=position,
    features=features,
    bars=bars_df,  # Optional OHLCV DataFrame
    session_volatility="medium"
)

if decision.should_cut:
    print(f"Cutting loss: {decision.reason}")
    print(f"Urgency: {decision.urgency}")
    print(f"Confidence: {decision.confidence:.2f}")
    
    # Execute the loss cut
    success, msg = loss_cutter.execute_loss_cut(
        position=position,
        reason=decision.reason
    )
    
    if success:
        print(f"Loss cut successful: {msg}")
    else:
        print(f"Loss cut failed: {msg}")
        
elif decision.urgency == "tighten_first":
    print(f"Tightening SL to {decision.new_sl:.2f}")
    # Modify position SL
    mt5_service.modify_position(
        ticket=position.ticket,
        sl=decision.new_sl
    )
```

### Integration with Position Monitoring

```python
import time
from datetime import datetime

def monitor_positions():
    """Monitor all open positions for loss-cutting opportunities."""
    while True:
        positions = mt5.positions_get()
        
        for position in positions:
            # Get market features
            features = get_market_features(position.symbol)
            bars = get_ohlcv_bars(position.symbol, "M5", 50)
            
            # Determine session volatility
            session = get_current_session()
            session_volatility = get_session_volatility(session)
            
            # Check for loss-cutting opportunity
            decision = loss_cutter.should_cut_loss(
                position=position,
                features=features,
                bars=bars,
                session_volatility=session_volatility
            )
            
            # Take action based on decision
            if decision.should_cut and decision.urgency == "immediate":
                # Cut loss immediately
                success, msg = loss_cutter.execute_loss_cut(
                    position=position,
                    reason=decision.reason
                )
                log_journal_event(
                    ticket=position.ticket,
                    event="loss_cut",
                    reason=decision.reason,
                    confidence=decision.confidence
                )
                
            elif decision.urgency == "tighten_first":
                # Tighten stop loss first
                mt5_service.modify_position(
                    ticket=position.ticket,
                    sl=decision.new_sl
                )
                log_journal_event(
                    ticket=position.ticket,
                    event="sl_tightened",
                    new_sl=decision.new_sl,
                    reason=decision.reason
                )
        
        time.sleep(30)  # Check every 30 seconds
```

## Journal Reason Codes

The system logs the following reason codes for journal tracking:

- `early_r`: Early exit due to R-threshold + high risk score
- `invalidation`: Multi-timeframe invalidation detected
- `momentum_relapse`: ADX rollover + RSI cross + MACD shrink
- `wick_exit`: Long opposing wick reversal pattern
- `time_backstop`: Position stuck at loss for too long
- `risk_sim_neg`: Negative expected R from risk simulation

## Measurement & Tuning

Track the following metrics to tune thresholds:

1. **Close Attempts**: Number of retry attempts per close
2. **Success Rate**: Percentage of successful closes
3. **Slippage**: Difference between expected and actual close price
4. **Deviation Used**: Deviation points used for each close
5. **Reason Distribution**: Frequency of each reason code
6. **Win Rate by Reason**: Win rate for positions NOT cut vs those cut
7. **Average R Saved**: Average R saved by cutting early

## Testing

Run the comprehensive test suite:

```bash
python test_loss_cutter.py
```

The test suite verifies:
- ✓ Confluence risk scoring (0-1 scale)
- ✓ Multi-timeframe invalidation detection
- ✓ Momentum relapse logic (ADX + RSI + MACD)
- ✓ Wick reversal pattern detection
- ✓ R-threshold ladder (-0.5R, -0.8R)
- ✓ Spread/ATR gating
- ✓ Time-decay backstop
- ✓ Reliable closing with IOC + retries

## Best Practices

1. **Start Conservative**: Begin with higher thresholds (e.g., -1.0R, 0.75 risk score) and tighten based on results
2. **Monitor Spread**: Ensure spread/ATR cap is appropriate for your broker
3. **Session Awareness**: Adjust time-decay thresholds for different sessions
4. **Journal Everything**: Log all decisions for post-trade analysis
5. **Backtest First**: Test on historical data before live deployment
6. **Gradual Rollout**: Start with small position sizes
7. **Review Weekly**: Analyze reason codes and adjust thresholds

## Troubleshooting

### Issue: Too many false exits
- **Solution**: Increase `POS_EARLY_EXIT_SCORE` threshold (e.g., 0.70 → 0.75)
- **Solution**: Require more invalidation signals (modify code to require 3+ instead of 2+)

### Issue: Not cutting losses fast enough
- **Solution**: Decrease `POS_EARLY_EXIT_R` threshold (e.g., -0.8R → -0.6R)
- **Solution**: Lower `POS_EARLY_EXIT_SCORE` threshold (e.g., 0.65 → 0.60)

### Issue: High spread preventing closes
- **Solution**: Increase `POS_SPREAD_ATR_CLOSE_CAP` (e.g., 0.40 → 0.50)
- **Solution**: Implement spread-aware tightening logic

### Issue: Retries failing
- **Solution**: Increase `POS_CLOSE_RETRY_MAX` (e.g., 3 → 5)
- **Solution**: Adjust backoff delays for your broker's latency

## Future Enhancements

Potential improvements for future versions:

1. **Machine Learning**: Train ML model on historical outcomes
2. **Adaptive Thresholds**: Auto-adjust based on recent performance
3. **Correlation Analysis**: Consider correlated positions
4. **News Integration**: Tighten during high-impact news
5. **Volatility Clustering**: Detect regime changes
6. **Position Sizing**: Adjust future sizes based on cut frequency

## Support

For issues or questions:
1. Check the test suite: `python test_loss_cutter.py`
2. Review logs in `data/journal_events.csv`
3. Analyze reason code distribution
4. Verify configuration in `config.py`
