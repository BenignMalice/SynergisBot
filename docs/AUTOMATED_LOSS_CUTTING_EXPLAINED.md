# 🔪 Automated Loss Cutting - How It Works

## Quick Answer

**Loss cutting is 100% AUTOMATIC** - it runs in the background **WITHOUT** requiring ChatGPT instruction or user action.

---

## 🤖 How It Works

### Fully Automated System

The loss cutting system (`LossCutter`) is:
- ✅ **Always running** in the background
- ✅ **Fully automatic** - no ChatGPT instruction needed
- ✅ **No user action required** - monitors all positions automatically
- ✅ **Checks every 15 seconds** (fast response to market changes)
- ✅ **Sends Telegram alerts** when it takes action

### Where It Runs

```python
# chatgpt_bot.py (lines 1960-1967)

# Fast loss-cutting check (every 15 seconds - catches quick reversals)
scheduler.add_job(
    check_loss_cuts_async,
    'interval',
    seconds=15,
    args=[app],
    id='fast_loss_cutter',
    max_instances=1
)
```

**This runs automatically when the bot starts!** 🚀

---

## 🎯 What Loss Cutter Monitors

### Multi-Factor Analysis (6 Checks)

#### 1. **R-Multiple Thresholds**
- **-0.5R**: Tightens stop loss (warning zone)
- **-0.8R**: Cuts loss immediately (danger zone)

#### 2. **Confluence Risk Scoring**
- Analyzes trend, momentum, structure alignment
- High confluence against position = early exit

#### 3. **Multi-Timeframe Invalidation**
- Checks if higher timeframe structure broke
- Setup invalidated = exit immediately

#### 4. **Momentum Relapse Detection**
- RSI, MACD, ADX shift against position
- Momentum reversal = exit signal

#### 5. **Wick Reversal Patterns**
- Detects rejection wicks (pin bars, hammers)
- Strong reversal pattern = exit

#### 6. **Time-Decay Backstop**
- If position underwater too long (e.g., 30+ min)
- No recovery = cut loss

---

## 🔍 Decision Process

### Step 1: Calculate R-Multiple
```
R-Multiple = (Current Price - Entry Price) / (Entry Price - Stop Loss)

Example BUY at 3950, SL at 3944:
Current at 3946 → R = -0.67 (losing 67% of risk)
```

### Step 2: Check Thresholds
```
If R ≤ -0.8 → Immediate cut
If R ≤ -0.5 → Tighten SL (warning)
```

### Step 3: Analyze Confluence
```
Exit signals (trend, momentum, structure):
- RSI < 30 (oversold) = -1 point
- MACD bearish cross = -1 point
- Below EMA200 = -1 point

Score ≥ threshold → Cut loss
```

### Step 4: Check Professional Filters
```
Early Exit AI checks:
- Structure collapse detected?
- Breakout quality failed?
→ Override to immediate exit
```

### Step 5: Execute Decision
```
Urgency levels:
1. "immediate" → Close position NOW
2. "tighten_first" → Move SL closer, monitor
3. "monitor" → Keep watching
```

---

## 📱 Telegram Notifications

You receive **automatic Telegram alerts** when loss cutter acts:

### Loss Cut Executed:
```
🔪 Loss Cut Executed

Ticket: 120828675
Symbol: XAUUSD
Reason: Early Exit AI: Structure collapsed - price broke below key support at 3944.50
Confidence: 85.3%
Status: ✅ Position closed at 3946.20
```

### Loss Cut Failed (rare):
```
⚠️ Loss Cut Failed

Ticket: 120828675
Symbol: XAUUSD
Reason: R-threshold -0.85R exceeded with bearish momentum
Error: Spread too wide (5.2 ATR), retrying...
```

### Stop Loss Tightened:
```
⚠️ Stop Loss Tightened

Ticket: 120828675
Symbol: XAUUSD
Old SL: 3944.00
New SL: 3947.50 (tightened by $3.50)
Reason: R-multiple at -0.52R (warning zone)
```

---

## 🆚 Comparison: Loss Cutting vs Intelligent Exits

### 🔪 Loss Cutting (Automatic)
- **Purpose**: Protect losing positions
- **Trigger**: R-multiple thresholds (-0.5R, -0.8R)
- **Action**: Close position or tighten SL
- **Control**: 100% automatic, no user input
- **Monitoring**: Every 15 seconds
- **Applies to**: ALL open positions (always)

### 🎯 Intelligent Exits (100% AUTOMATIC!)
- **Purpose**: Optimize winning positions
- **Trigger**: Percentage-based profit targets (30%, 60%)
- **Action**: Breakeven SL, partial profits, trailing
- **Control**: ✅ AUTOMATIC for all trades (no user action required!)
- **Monitoring**: Every 30 seconds (always active)
- **Applies to**: ALL market trades automatically

**Key Difference**: Both systems are 100% automatic! Loss cutting protects losing positions. Intelligent exits optimize winning positions. No user action required for either!

---

## 🔧 Configuration

### Current Settings (from config.py)

```python
# R-threshold for early exit
POS_EARLY_EXIT_R = -0.5  # Cut at -50% of risk
# Env: POS_EARLY_EXIT_R (default: -0.5)

# Risk score threshold (0.0-1.0, where 1.0 = 100%)
POS_EARLY_EXIT_SCORE = 0.55  # Cut if confluence score ≥ 55%
# Env: POS_EARLY_EXIT_SCORE (default: 0.55)

# Spread cap for closing (relative to ATR)
POS_SPREAD_ATR_CLOSE_CAP = 0.40  # Max 40% of ATR
# Env: POS_SPREAD_ATR_CLOSE_CAP (default: 0.40)

# Time-based backstop
POS_TIME_BACKSTOP_ENABLE = True  # Enable time decay
POS_TIME_BACKSTOP_BARS = 10  # Wait 10 bars before time exit

# Multi-timeframe invalidation
POS_INVALIDATION_EXIT_ENABLE = True  # Check HTF invalidation

# Closing reliability
POS_CLOSE_RETRY_MAX = 3  # Max retry attempts
POS_CLOSE_BACKOFF_MS = "300,600,900"  # Backoff delays (ms)
```

**These settings are automatic - no need to change!**

You can override them by setting environment variables in your `.env` file if needed.

---

## ❓ Common Questions

### Q1: Do I need to tell ChatGPT to monitor my trades?
**A: No!** Loss cutting is automatic for ALL positions from the moment you place them.

### Q2: Can I disable loss cutting?
**A: No** (by design). It's a safety system that protects all positions. If you want more control, use wider stop losses when placing trades.

### Q3: What if I want to "let it run" despite being down?
**A:** The system only cuts at **-0.8R** (80% of your risk). If you set a wider SL, it gives more room. But once structure breaks or confluence is strongly against you, it's protecting your account.

### Q4: Does loss cutting override my stop loss?
**A:** No! It **supplements** your SL:
- If price hits your SL → Normal stop out
- If confluence risk is high before SL → Loss cutter exits early
- **Result**: You lose LESS than your full risk

### Q5: Can I see loss cutting in action?
**A:** Yes! Check your Telegram for alerts:
```
🔪 Loss Cut Executed
⚠️ Stop Loss Tightened
```

### Q6: Is loss cutting the same for Telegram and Custom GPT?
**A:** Yes! Loss cutting is **bot-level**, not interface-level. It monitors ALL positions regardless of how they were placed (Telegram, Custom GPT, or manual).

---

## 🎯 Integration with Other Systems

### System Hierarchy (Order of Operations)

```
1. Loss Cutter (15 sec) → Protects losing positions
   ↓ (cuts early if structure breaks)
   
2. Intelligent Exits (30 sec) → Optimizes winning positions
   ↓ (breakeven, partial, trailing)
   
3. Your Stop Loss/Take Profit → Final backstop
   ↓ (executes if price hits levels)
   
4. Circuit Breaker (2 min) → Account-level protection
   ↓ (halts trading if daily drawdown exceeded)
```

**All systems work together automatically!**

---

## 📊 Example Scenario

### Scenario: Gold BUY Trade Goes Wrong

```
09:00 AM - Trade Placed:
Entry: 3950.00
SL: 3944.00 (risk: 6 points = 1R)
TP: 3962.00 (reward: 12 points = 2R)
R:R = 2:1 ✅

09:05 AM - Price pulls back:
Current: 3947.00 (down $3)
R-Multiple: -0.50R (50% of risk)
📊 Loss Cutter: "Tightening SL to 3946.50"
🔔 Telegram: "⚠️ Stop Loss Tightened"

09:08 AM - Structure breaks:
Current: 3945.50 (down $4.50)
R-Multiple: -0.75R (75% of risk)
📊 Loss Cutter: "Key support broken at 3946.00"
📊 Confluence Score: 72/100 (high exit signal)
🔪 Decision: "IMMEDIATE CUT"
✅ Position closed at 3945.50
🔔 Telegram: "🔪 Loss Cut Executed - Structure collapsed"

Result: Lost $4.50 instead of full $6 SL (saved 25% of risk!)
```

---

## ✅ Summary

### Loss Cutting:
- ✅ **100% Automatic** - runs in background
- ✅ **No ChatGPT instruction needed** - always on
- ✅ **Monitors ALL positions** - regardless of source
- ✅ **Every 15 seconds** - fast response
- ✅ **Telegram alerts** - keeps you informed
- ✅ **Multi-factor analysis** - 6 checks
- ✅ **R-threshold ladder** - -0.5R warn, -0.8R cut
- ✅ **Protects losing trades** - exits before full SL hit
- ✅ **Works with Professional Filters** - Early Exit AI integration
- ✅ **Account-level safety** - can't be disabled

### You Don't Need To:
- ❌ Tell ChatGPT to monitor trades
- ❌ Enable loss cutting manually
- ❌ Check positions constantly
- ❌ Worry about missing structure breaks

### You Just Need To:
- ✅ Place trades (ChatGPT or manual)
- ✅ Check Telegram for alerts
- ✅ Trust the system to protect you

---

**The bot is watching your trades 24/7, even while you sleep!** 🛡️

