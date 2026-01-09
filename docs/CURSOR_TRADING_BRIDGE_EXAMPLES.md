# Cursor Trading Bridge - Usage Examples

This document shows concrete examples of how Cursor's AI agent would interact with your trading bot using the hybrid approach.

## Architecture Overview

```
User Request → Cursor Agent → cursor_trading_bridge.py → desktop_agent.py → Trading Bot
                (me)           (bridge module)          (tool registry)    (MT5/DB)
```

## Example 1: Market Analysis Request

### User Request:
```
"Analyze BTCUSD and give me a trade recommendation"
```

### Cursor Agent Response (What I Would Do):

I would use the bridge module like this:

```python
from cursor_trading_bridge import recommend

# Analyze and get recommendation
result = await recommend("BTCUSD")
```

### What Happens Behind the Scenes:

1. **Cursor Agent (me)** calls `recommend("BTCUSD")`
2. **Bridge** calls `desktop_agent.registry.execute("moneybot.analyse_symbol_full", ...)`
3. **Desktop Agent** executes the full analysis tool
4. **Trading Bot** fetches:
   - Current price from MT5
   - Market structure analysis
   - VWAP calculations
   - Liquidity zones
   - Order blocks
   - Confluence scoring
5. **Response flows back** through the chain
6. **Cursor Agent** formats and presents to user

### Example Response I Would Give:

```
Based on my analysis of BTCUSD:

📊 Current Market State:
- Price: $88,250
- Regime: Compression (Range-bound)
- VWAP: $88,180 (slightly above price)

🎯 Trade Recommendation:
- Direction: BUY
- Entry: $88,050 (liquidity sweep zone)
- Stop Loss: $87,980
- Take Profit: $88,120
- Risk/Reward: 1:1.0
- Confidence: 75/100

📝 Reasoning:
- Price is near lower range boundary
- M1 liquidity sweep forming
- VWAP deviation suggests mean reversion opportunity
- Confluence score: 88/100 (Grade A)

Would you like me to:
1. Create an auto-execution plan for this?
2. Execute the trade immediately?
3. Get more detailed analysis?
```

---

## Example 2: Multi-Symbol Analysis

### User Request:
```
"Compare BTCUSD and XAUUSD - which has better setup right now?"
```

### Cursor Agent Code:

```python
from cursor_trading_bridge import recommend
import asyncio

async def compare_symbols():
    btc = await recommend("BTCUSD")
    gold = await recommend("XAUUSD")
    
    # Compare confidence scores
    btc_conf = btc.get("recommendation", {}).get("confidence", 0)
    gold_conf = gold.get("recommendation", {}).get("confidence", 0)
    
    return {
        "btc": btc,
        "gold": gold,
        "better_setup": "BTCUSD" if btc_conf > gold_conf else "XAUUSD"
    }

result = asyncio.run(compare_symbols())
```

### Example Response:

```
📊 Symbol Comparison:

BTCUSD:
- Confidence: 75/100
- Setup: BUY at $88,050
- Risk/Reward: 1:1.0
- Regime: Compression

XAUUSD:
- Confidence: 88/100
- Setup: SELL at $4,345
- Risk/Reward: 1:1.2
- Regime: Mean Reversion

🏆 Better Setup: XAUUSD (higher confidence, better R/R)

Would you like me to create auto-execution plans for both?
```

---

## Example 3: Trade Execution Request

### User Request:
```
"Execute a BUY trade on BTCUSD at current price with 50 pip SL and 100 pip TP"
```

### Cursor Agent Code:

```python
from cursor_trading_bridge import get_bridge

bridge = get_bridge()

# Get current price first
price_data = await bridge.get_current_price("BTCUSD")
current_price = price_data.get("data", {}).get("bid", 0)

# Calculate SL and TP
sl = current_price - 50 * 0.0001  # 50 pips for BTCUSD
tp = current_price + 100 * 0.0001  # 100 pips

# Execute
result = await bridge.execute_trade(
    symbol="BTCUSD",
    direction="BUY",
    entry_price=current_price,
    stop_loss=sl,
    take_profit=tp,
    order_type="market"
)
```

### Example Response:

```
✅ Trade Executed Successfully!

- Symbol: BTCUSD
- Direction: BUY
- Entry: $88,250 (market)
- Stop Loss: $88,200 (50 pips)
- Take Profit: $88,350 (100 pips)
- Ticket: 176137866
- Volume: 0.01 lots

Trade is now active. I'll monitor it and can update you on status.
```

---

## Example 4: Auto-Execution Plan Creation

### User Request:
```
"Create an auto-execution plan for XAUUSD BUY at 4337 with SL 4335 and TP 4343, 
trigger when price sweeps liquidity and VWAP flattens"
```

### Cursor Agent Code:

```python
from cursor_trading_bridge import get_bridge

bridge = get_bridge()

result = await bridge.create_auto_plan(
    symbol="XAUUSD",
    direction="BUY",
    entry=4337.0,
    sl=4335.0,
    tp=4343.0,
    conditions={
        "liquidity_sweep": True,
        "vwap_slope_max": 0.0001,  # VWAP must be flat
        "confluence_min": 60,
        "timeframe": "M1"
    }
)
```

### Example Response:

```
✅ Auto-Execution Plan Created!

Plan ID: chatgpt_abc12345
- Symbol: XAUUSD
- Direction: BUY
- Entry: $4,337.0
- Stop Loss: $4,335.0
- Take Profit: $4,343.0
- Timeframe: M1

Trigger Conditions:
✓ Liquidity sweep detected
✓ VWAP slope < 0.0001 (flat)
✓ Confluence ≥ 60

Status: Pending (monitoring every 10 seconds)
Expiry: 2 hours from now

The plan will automatically execute when all conditions are met.
```

---

## Example 5: Trade Review and Analysis

### User Request:
```
"Review my closed trades from today and analyze what went well"
```

### Cursor Agent Code:

```python
from cursor_trading_bridge import get_bridge

bridge = get_bridge()

# Get recent trades
trades = await bridge.get_recent_trades(days_back=1)

# Analyze results
wins = [t for t in trades.get("trades", []) if t.get("profit_loss", 0) > 0]
losses = [t for t in trades.get("trades", []) if t.get("profit_loss", 0) <= 0]

total_pnl = sum(t.get("profit_loss", 0) for t in trades.get("trades", []))
win_rate = len(wins) / len(trades.get("trades", [])) * 100 if trades.get("trades") else 0
```

### Example Response:

```
📊 Today's Trade Review (Dec 22, 2025):

Total Trades: 8
Wins: 5 (62.5%)
Losses: 3 (37.5%)
Net P/L: +$6.21

✅ Best Trade:
- Plan: chatgpt_7a77af5c
- Symbol: BTCUSD
- Direction: SELL
- P/L: +$2.45
- Entry: $88,390 | Exit: $88,300
- Strategy: Micro Liquidity Sweep

❌ Worst Trade:
- Plan: chatgpt_96eb2ed6
- Symbol: BTCUSD
- Direction: SELL
- P/L: -$1.20
- Entry: $88,420 | Exit: $88,480 (SL hit)
- Strategy: VWAP Break Trap

📈 Insights:
- Micro liquidity sweeps performed best (3/3 wins)
- VWAP break traps struggled in compression (1/2 losses)
- M1 timeframe trades had higher win rate (4/5 wins)

Would you like me to:
1. Review a specific trade in detail?
2. Adjust auto-execution plan conditions based on these results?
3. Create new plans using the winning strategies?
```

---

## Example 6: Real-Time Market Monitoring

### User Request:
```
"Monitor BTCUSD and alert me when a good setup forms"
```

### Cursor Agent Code:

```python
from cursor_trading_bridge import recommend
import asyncio
import time

async def monitor_symbol(symbol, min_confidence=70):
    """Monitor symbol and alert when good setup appears"""
    while True:
        result = await recommend(symbol)
        
        confidence = result.get("recommendation", {}).get("confidence", 0)
        
        if confidence >= min_confidence:
            print(f"🎯 Good setup detected for {symbol}!")
            print(f"Confidence: {confidence}/100")
            print(f"Direction: {result['recommendation']['direction']}")
            print(f"Entry: {result['recommendation']['entry']}")
            # Break or continue based on user preference
            break
        
        await asyncio.sleep(30)  # Check every 30 seconds

# Run monitoring
asyncio.run(monitor_symbol("BTCUSD", min_confidence=75))
```

### Example Response:

```
🔍 Monitoring BTCUSD for setups (confidence ≥ 75)...

[30s later]
- Current confidence: 65/100 (compression, waiting for trigger)

[60s later]
- Current confidence: 72/100 (liquidity forming)

[90s later]
🎯 Good setup detected for BTCUSD!

Confidence: 78/100
Direction: BUY
Entry: $88,050
Stop Loss: $87,980
Take Profit: $88,120

Reasoning: Liquidity sweep completed, VWAP flattened, confluence 88/100

Would you like me to create an auto-execution plan?
```

---

## Example 7: Strategy Backtesting Request

### User Request:
```
"Analyze how VWAP deviation trades performed this week"
```

### Cursor Agent Code:

```python
from cursor_trading_bridge import get_bridge

bridge = get_bridge()

# Get trades from last week
trades = await bridge.get_recent_trades(days_back=7)

# Filter for VWAP deviation strategy
vwap_trades = [
    t for t in trades.get("trades", [])
    if "VWAP" in t.get("strategy", "") or "vwap" in t.get("notes", "").lower()
]

# Calculate stats
vwap_pnl = sum(t.get("profit_loss", 0) for t in vwap_trades)
vwap_wins = len([t for t in vwap_trades if t.get("profit_loss", 0) > 0])
vwap_total = len(vwap_trades)
```

### Example Response:

```
📊 VWAP Deviation Strategy Analysis (Last 7 Days):

Total Trades: 12
Wins: 7 (58.3%)
Losses: 5 (41.7%)
Net P/L: +$4.50

📈 Performance by Symbol:
- BTCUSD: +$2.10 (4 trades, 75% win rate)
- XAUUSD: +$2.40 (8 trades, 50% win rate)

⏰ Best Timeframe:
- M5: +$3.20 (6 trades, 67% win rate)
- M1: +$1.30 (6 trades, 50% win rate)

💡 Recommendations:
- VWAP deviation works better on M5 timeframe
- BTCUSD shows stronger mean reversion than XAUUSD
- Consider increasing confluence threshold to 70+ for XAUUSD

Should I create optimized auto-execution plans based on these findings?
```

---

## Example 8: Interactive Trade Planning

### User Request:
```
"I want to trade XAUUSD. Help me plan the trade step by step"
```

### Cursor Agent Response Flow:

```
Step 1: Let me analyze XAUUSD current market conditions...

[Analyzing...]

📊 Current Market Analysis:
- Price: $4,340.50
- Regime: Mean Reversion (Range-bound)
- VWAP: $4,339.20
- Structure: Bullish (higher highs, higher lows)

Step 2: Based on the analysis, I recommend:

🎯 BUY Setup:
- Entry: $4,337.0 (liquidity zone)
- Stop Loss: $4,335.0 (below recent low)
- Take Profit: $4,343.0 (resistance zone)
- Risk/Reward: 1:3.0

Step 3: Trigger Conditions:
- Wait for price to sweep $4,337.0 liquidity
- Confirm VWAP slope < 0.0001 (flat)
- Ensure confluence ≥ 60

Step 4: Would you like me to:
A) Create an auto-execution plan with these conditions?
B) Execute immediately at market price?
C) Adjust any parameters first?

[Waiting for your choice...]
```

---

## Key Differences: ChatGPT vs Cursor Agent

### ChatGPT Integration (Current):
- **Interface**: REST API via ngrok
- **Communication**: HTTP requests/responses
- **Speed**: ~2-5 seconds per request
- **Context**: Limited to conversation history
- **Use Case**: High-level analysis, recommendations, trade review

### Cursor Agent Integration (Hybrid Approach):
- **Interface**: Direct Python function calls
- **Communication**: In-process function calls
- **Speed**: ~100-500ms per request (10x faster)
- **Context**: Full codebase access, can read/write files
- **Use Case**: 
  - Real-time monitoring
  - Automated analysis scripts
  - Code-level trade logic
  - File-based data analysis
  - Integration with other tools

---

## Implementation Notes

1. **Bridge Module**: `cursor_trading_bridge.py` provides simple async functions
2. **Direct Access**: Cursor agent can call these functions directly in code
3. **Error Handling**: Bridge handles unavailable desktop_agent gracefully
4. **Async Support**: All functions are async for non-blocking operations
5. **Type Hints**: Full type hints for better IDE support

---

## Next Steps

To use this in Cursor:

1. **Import the bridge**:
   ```python
   from cursor_trading_bridge import recommend, analyze, execute
   ```

2. **Use in your requests**:
   - "Analyze BTCUSD" → I'll call `recommend("BTCUSD")`
   - "Execute trade" → I'll call `execute(...)`
   - "Review trades" → I'll call `get_recent_trades()`

3. **I'll handle the rest**:
   - Format responses
   - Handle errors
   - Provide recommendations
   - Create plans or execute trades

The bridge makes it seamless - you just ask naturally, and I'll use the trading bot tools automatically!
