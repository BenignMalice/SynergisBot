# Adaptive Intelligent Exit System - Phase 1 MVP Plan

**Last Updated:** 2025-11-03  
**Version:** 1.0  
**Status:** Planning Phase (Not Yet Implemented)

---

## 🎯 Objective

**Problem Statement:**  
When a scalp trade reaches +$8 profit (~0.3R), the system should take profit early. However, current intelligent exits use intraday parameters (30% breakeven, 60% partial), causing scalp trades to miss profit-taking opportunities.

**Solution:**  
Automatically classify trades as **SCALP** vs **INTRADAY** at entry, and apply appropriate exit parameters based on classification.

**Core Philosophy:**  
- **SCALP** → Fast profit capture (25% breakeven, 40% partial, 70% close)
- **INTRADAY** → Profit maximization (30% breakeven, 60% partial, 50% close)

---

## 📋 Phase 1 Scope (MVP)

### ✅ What's Included

1. **Trade Classification at Entry**
   - Simple 3-factor classifier (no complex ML)
   - Classification happens once, at trade open
   - No mid-trade switching (keeps it simple and reliable)

2. **Classification Rules**
   - Stop Loss Size vs. ATR
   - User Comment Keywords
   - Session Strategy (from `getCurrentSession()`)

3. **Adaptive Exit Parameters**
   - SCALP mode: Faster profit capture
   - INTRADAY mode: Standard profit maximization
   - Parameters applied automatically via `enableIntelligentExits()`

4. **Integration Points**
   - Works with existing `IntelligentExitManager`
   - Integrates with `enableIntelligentExits()` tool
   - No changes to core exit logic, only parameter selection

### ❌ What's NOT Included (Future Phases)

- Mid-trade mode switching (Phase 2)
- Volatility Quality Index (VQI) filtering
- Historical Feedback Loop (HFL) self-learning
- Session-specific calibration curves
- Dynamic mode re-evaluation
- Confidence weighting system

---

## 🧮 Classification Logic

### Three-Factor Classifier

The system evaluates three factors to determine trade type:

| Factor | Data Source | SCALP Condition | INTRADAY Condition |
|--------|-------------|-----------------|-------------------|
| **Stop Size vs ATR** | `(entry - stop_loss) / ATR_H1` | ≤ 1.0× ATR | > 1.0× ATR |
| **Comment Keywords** | MT5 trade comment field | Contains "scalp", "scalping", "quick", "fast" | Contains "swing", "hold", "trend", "intraday" |
| **Session Strategy** | `getCurrentSession()` → `strategy` | `strategy == "scalping"` | `strategy == "trend_following"` or `"breakout"` |

### Classification Decision Tree

```
Trade Opened
    │
    ├─> Check Comment Keywords (HIGHEST PRIORITY)
    │   │
    │   ├─> "scalp" keyword found → SCALP
    │   └─> "swing"/"hold" keyword found → INTRADAY
    │
    ├─> If no keywords, check Stop Size vs ATR
    │   │
    │   ├─> Stop ≤ 1.0× ATR → SCALP
    │   └─> Stop > 1.0× ATR → INTRADAY
    │
    └─> If ambiguous, check Session Strategy
        │
        ├─> Session == "scalping" → SCALP
        └─> Session == "trend_following"/"breakout" → INTRADAY
        └─> Default: INTRADAY (conservative)
```

### Classification Examples

| Scenario | Stop Size | Comment | Session | Classification | Reason |
|----------|-----------|---------|---------|-----------------|--------|
| Quick scalp trade | 0.8× ATR | "scalp" | "range_trading" | **SCALP** | Keyword override |
| Swing trade | 2.5× ATR | "swing hold" | "trend_following" | **INTRADAY** | Keyword + size |
| Breakout trade | 1.2× ATR | (none) | "breakout" | **INTRADAY** | Session + size |
| Tight stop trade | 0.9× ATR | (none) | "range_trading" | **SCALP** | Stop size |
| Ambiguous trade | 1.1× ATR | (none) | "range_trading" | **INTRADAY** | Default (conservative) |

---

## ⚙️ Exit Parameter Profiles

### SCALP Mode Parameters

**Philosophy:** Lock profits quickly, protect capital, minimize retrace risk.

| Parameter | SCALP Value | Current (Intraday) | Benefit |
|-----------|-------------|-------------------|---------|
| `breakeven_profit_pct` | **25.0%** (0.25R) | 30.0% (0.30R) | Faster capital protection |
| `partial_profit_pct` | **40.0%** (0.40R) | 60.0% (0.60R) | Earlier profit lock |
| `partial_close_pct` | **70.0%** | 50.0% | Lock more profit, less left to run |
| `trailing_start_pct` | **40.0%** (after partial) | 60.0% | Start trailing sooner |
| `trailing_atr_multiplier` | **0.7×** (tighter) | 1.0× | More aggressive trailing |
| `vix_hybrid_stops` | Active if VIX > 18 | Always active | Same behavior |

### INTRADAY Mode Parameters

**Philosophy:** Maximize profit, let winners run, handle volatility.

| Parameter | INTRADAY Value | Notes |
|-----------|----------------|-------|
| `breakeven_profit_pct` | **30.0%** (0.30R) | Standard (current default) |
| `partial_profit_pct` | **60.0%** (0.60R) | Standard (current default) |
| `partial_close_pct` | **50.0%** | Standard (current default) |
| `trailing_start_pct` | **60.0%** (after partial) | Standard (current default) |
| `trailing_atr_multiplier` | **1.0×** | Standard (current default) |
| `vix_hybrid_stops` | Always active | Standard (current default) |

---

## 🔧 Implementation Requirements

### 1. New Component: `TradeTypeClassifier`

**Location:** `infra/trade_type_classifier.py`

**Responsibilities:**
- Evaluate stop size vs. ATR
- Parse comment keywords
- Fetch session strategy
- Return classification (SCALP or INTRADAY)

**Input:**
- `symbol: str`
- `entry_price: float`
- `stop_loss: float`
- `comment: Optional[str]`
- `session_info: Dict` (from `getCurrentSession()`)

**Output:**
```python
{
    "trade_type": "SCALP" | "INTRADAY",
    "confidence": 0.0-1.0,  # How confident the classification is
    "reasoning": "stop_size <= 1.0 ATR",  # Human-readable explanation
    "factors": {
        "stop_atr_ratio": 0.85,
        "comment_match": "scalp",
        "session_strategy": "scalping"
    }
}
```

**Dependencies:**
- `analyse_symbol_full()` → Get ATR_H1
- `getCurrentSession()` → Get session strategy
- MT5 trade comment field

---

### 2. Integration with `enableIntelligentExits()`

**Location:** `desktop_agent.py` (tool implementation)

**Flow:**
```
User executes trade
    │
    ├─> Trade placed in MT5
    │
    ├─> Auto-enable intelligent exits (if enabled)
    │
    ├─> NEW: TradeTypeClassifier.classify()
    │   │
    │   └─> Returns: { "trade_type": "SCALP", ... }
    │
    ├─> Select exit parameters based on trade_type
    │   │
    │   ├─> SCALP → Use SCALP profile
    │   └─> INTRADAY → Use INTRADAY profile
    │
    └─> Call enableIntelligentExits() with selected parameters
```

**Code Change:**
```python
# In desktop_agent.py, enableIntelligentExits() function

# NEW: Classify trade type
from infra.trade_type_classifier import TradeTypeClassifier

classifier = TradeTypeClassifier(mt5_service, session_service)
classification = classifier.classify(
    symbol=symbol,
    entry_price=entry,
    stop_loss=initial_sl,
    comment=comment,  # From MT5 position comment
    session_info=session_info
)

# Select parameters based on classification
if classification["trade_type"] == "SCALP":
    breakeven_pct = 25.0
    partial_pct = 40.0
    partial_close_pct = 70.0
    trailing_start_pct = 40.0
    trailing_atr_mult = 0.7
else:  # INTRADAY
    breakeven_pct = 30.0
    partial_pct = 60.0
    partial_close_pct = 50.0
    trailing_start_pct = 60.0
    trailing_atr_mult = 1.0

# Apply intelligent exits with selected parameters
intelligent_exit_manager.enable_intelligent_exits(
    ticket=ticket,
    symbol=symbol,
    direction=direction,
    entry=entry,
    initial_sl=initial_sl,
    initial_tp=initial_tp,
    breakeven_profit_pct=breakeven_pct,
    partial_profit_pct=partial_pct,
    partial_close_pct=partial_close_pct,
    trailing_start_pct=trailing_start_pct,
    trailing_atr_multiplier=trailing_atr_mult,
    # ... other params
)
```

---

### 3. Logging and Transparency

**What to Log:**
- Classification result (SCALP/INTRADAY)
- Confidence score
- Reasoning (which factor determined classification)
- Applied exit parameters
- All three factor values (stop/ATR ratio, comment match, session)

**Where to Log:**
- Trade execution logs
- Discord notifications (include classification in message)
- ChatGPT tool response (show classification in confirmation)

**Example Discord Message:**
```
✅ Trade Executed: XAUUSD SELL 0.02 lots @ 2405.50
📊 Trade Type: SCALP (confidence: 0.85)
   └─ Reason: Stop size 0.9× ATR + comment "scalp"
💡 Exit Strategy:
   • Breakeven: +25% profit (0.25R)
   • Partial: +40% profit (0.40R), close 70%
   • Trailing: Starts at +40% with 0.7× ATR
```

---

## ⚠️ Risks & Mitigations

### Risk 1: Wrong Classification

**Impact:** SCALP trade classified as INTRADAY (misses profit) or vice versa (premature exit)

**Mitigation:**
- Use keyword override (highest priority)
- Log confidence score (flag low-confidence classifications)
- Allow manual override via comment keywords
- Conservative default (INTRADAY if ambiguous)

### Risk 2: ATR Calculation Failures

**Impact:** Cannot compute stop/ATR ratio → classification fails

**Mitigation:**
- Fallback to session strategy only
- If session strategy unavailable → default to INTRADAY
- Log warning when ATR unavailable
- Cache ATR value (refresh every 5 minutes)

### Risk 3: Performance Impact

**Impact:** Classification adds latency to trade execution

**Mitigation:**
- Cache ATR and session data (refresh every 60 seconds)
- Run classification asynchronously (don't block execution)
- Timeout protection (if classification > 500ms, use default INTRADAY)
- Minimal API calls (reuse existing `analyse_symbol_full()` data)

### Risk 4: User Confusion

**Impact:** User doesn't understand why trade was classified differently

**Mitigation:**
- Transparent logging (show all three factors)
- Discord message includes reasoning
- ChatGPT explains classification in trade confirmation
- Allow manual override via comment keywords

---

## 🧪 Testing Requirements

### Unit Tests

1. **Classification Logic Tests**
   - Test keyword matching (case-insensitive)
   - Test stop/ATR ratio calculations
   - Test session strategy matching
   - Test priority order (keyword > stop size > session)
   - Test default behavior (ambiguous → INTRADAY)

2. **Parameter Selection Tests**
   - Verify SCALP parameters are correct
   - Verify INTRADAY parameters match current defaults
   - Test parameter mapping logic

3. **Edge Cases**
   - Missing ATR data
   - Missing session data
   - Missing comment
   - Invalid stop size (negative, zero)
   - VIX hybrid stops behavior

### Integration Tests

1. **End-to-End Flow**
   - Place trade with "scalp" comment → verify SCALP classification
   - Place trade with 0.9× ATR stop → verify SCALP classification
   - Place trade with 1.5× ATR stop → verify INTRADAY classification
   - Verify `enableIntelligentExits()` called with correct parameters

2. **Performance Tests**
   - Classification completes in < 500ms
   - No blocking of trade execution
   - Caching works correctly (no excessive API calls)

### Manual Testing Checklist

- [ ] Place scalp trade → Verify SCALP classification in logs
- [ ] Place intraday trade → Verify INTRADAY classification in logs
- [ ] Check Discord message includes classification and reasoning
- [ ] Verify breakeven triggers at correct level (25% vs 30%)
- [ ] Verify partial profit triggers at correct level (40% vs 60%)
- [ ] Verify partial close percentage (70% vs 50%)
- [ ] Test with missing data (ATR unavailable, session unavailable)
- [ ] Test keyword override works

---

## 📊 Success Metrics

### Primary Metrics

1. **Classification Accuracy**
   - Target: > 85% correct classification (validated by user feedback)
   - Measure: User confirms classification matches intent

2. **Profit Capture Improvement**
   - Target: SCALP trades lock profit at +40% vs missing at +60%
   - Measure: Compare profit captured before/after implementation

3. **Performance**
   - Target: Classification adds < 200ms latency
   - Measure: Time from trade execution to intelligent exit enable

### Secondary Metrics

- Classification confidence distribution
- Keyword usage frequency
- Fallback usage (how often default INTRADAY used)
- User override requests

---

## 📈 Metrics Visibility & Reporting

### Overview

To validate classifier performance and identify improvement areas, metrics are collected and displayed through multiple channels.

### Metrics Collected

**Per-Trade Metrics:**
- Classification result (SCALP/INTRADAY/OVERRIDE)
- Confidence score (0.0-1.0)
- Classification latency (milliseconds)
- Factor used (keyword/stop_size/session/default)
- Manual override flag (if applicable)

**Aggregate Metrics (Rolling 100 Trades):**
- Classification distribution (% SCALP vs INTRADAY)
- Confidence distribution (HIGH/MEDIUM/LOW percentages)
- Factor usage breakdown (keyword match %, stop/ATR %, session %)
- Performance stats (avg latency, max latency, timeout count)
- Accuracy tracking (if user feedback provided)

### Where Metrics Are Displayed

#### 1. Daily Summary in Logs

**Trigger:** After every 100 trades classified

**Location:** Application logs (e.g., `logs/moneybot.log`)

**Format:**
```
[CLASSIFICATION METRICS] Last 100 Trades (as of 2025-11-03 14:30:00)
├─ Classification Distribution
│  ├─ SCALP: 42 trades (42%)
│  ├─ INTRADAY: 58 trades (58%)
│  └─ OVERRIDE: 3 trades (3%)
│
├─ Confidence Distribution
│  ├─ HIGH (≥0.7): 68 trades (68%)
│  ├─ MEDIUM (0.4-0.69): 28 trades (28%)
│  └─ LOW (<0.4): 4 trades (4%) → defaulted to INTRADAY
│
├─ Factor Usage
│  ├─ Keyword Match: 35 trades (35%)
│  ├─ Stop/ATR Ratio: 52 trades (52%)
│  ├─ Session Strategy: 13 trades (13%)
│  └─ Default Fallback: 4 trades (4%)
│
├─ Performance
│  ├─ Avg Classification Latency: 145ms
│  ├─ Max Latency: 387ms
│  └─ Timeouts (fallback): 0
│
└─ Accuracy (User Feedback)
   ├─ Correct: 87 trades (87%)
   ├─ Incorrect: 8 trades (8%)
   └─ No Feedback: 5 trades (5%)
```

#### 2. Discord Message - Daily Summary

**Trigger:** Every day at 17:00 UTC

**Location:** Discord private channel (via `discord_notifications.py`)

**Integration:** Uses `DiscordNotifier.send_message()` with message_type="UPDATE"

**Format:** Discord embed with formatted metrics (last 24 hours)

**Example Discord Daily Message:**
```
📊 Trade Classification Metrics - Daily Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 Date: 2025-11-03
🔢 Total Trades (Last 24h): 34

📊 Classification Breakdown:
   🟢 SCALP: 14 trades (41%)
   🔵 INTRADAY: 20 trades (59%)

🎯 Confidence Levels:
   ✅ HIGH (≥0.7): 28 trades (82%)
   ⚠️ MEDIUM (0.4-0.69): 5 trades (15%)
   ❌ LOW (<0.4): 1 trade (3%) → defaulted to INTRADAY

🔍 Classification Factors:
   • Keyword Match: 12 trades (35%)
   • Stop/ATR Ratio: 18 trades (53%)
   • Session Strategy: 4 trades (12%)

⚡ Performance:
   • Avg Latency: 138ms
   • Max Latency: 342ms
   • Timeouts: 0

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

#### 3. Discord Message - Weekly Summary

**Trigger:** Every Sunday at 17:00 UTC

**Location:** Discord private channel (via `discord_notifications.py`)

**Integration:** Uses `DiscordNotifier.send_message()` with message_type="UPDATE"

**Format:** Discord embed with formatted metrics (full week)

**Example Discord Weekly Message:**
```
📊 Trade Classification Metrics - Weekly Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 Period: 2025-10-27 to 2025-11-03 (7 days)
🔢 Total Trades: 247

📊 Classification Breakdown:
   🟢 SCALP: 98 trades (40%)
   🔵 INTRADAY: 149 trades (60%)
   ⚙️ OVERRIDE: 3 trades (1%)

🎯 Confidence Levels:
   ✅ HIGH (≥0.7): 198 trades (80%)
   ⚠️ MEDIUM (0.4-0.69): 42 trades (17%)
   ❌ LOW (<0.4): 7 trades (3%) → defaulted to INTRADAY

🔍 Classification Factors:
   • Keyword Match: 87 trades (35%)
   • Stop/ATR Ratio: 128 trades (52%)
   • Session Strategy: 29 trades (12%)
   • Default Fallback: 7 trades (3%)

⚡ Performance:
   • Avg Latency: 142ms
   • Max Latency: 398ms
   • Timeouts: 0

✅ Accuracy (User Feedback):
   • Correct: 215 trades (87%)
   • Incorrect: 18 trades (7%)
   • No Feedback: 14 trades (6%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Daily Summary Implementation Details:**
- Format as Discord embed with title "Trade Classification Metrics - Daily"
- Use color `0x9b59b6` (purple) for UPDATE message type
- Send to Discord private channel (default)
- Include timestamp in embed footer
- Shows metrics for last 24 hours only
- Trigger automatically at 17:00 UTC daily via scheduled task

**Weekly Summary Implementation Details:**
- Format as Discord embed with title "Trade Classification Metrics - Weekly"
- Use color `0x9b59b6` (purple) for UPDATE message type
- Send to Discord private channel (default)
- Include timestamp in embed footer
- Shows metrics for full week (last 7 days)
- Includes accuracy tracking (if user feedback provided)
- Trigger automatically at 17:00 UTC every Sunday via scheduled task
- Can also be manually triggered via ChatGPT tool

#### 4. Dashboard/CSV Export (Optional - Phase 2)

**Future Enhancement:**
- Real-time dashboard endpoint
- CSV export for analysis
- Historical trend graphs

### Implementation Requirements

**Component:** `infra/classification_metrics.py`

**Responsibilities:**
- Collect per-trade metrics (store in memory or SQLite)
- Calculate aggregate metrics (rolling 100 trades)
- Generate formatted summary strings
- Trigger Discord message generation
- Handle log file writing

**Storage:**
- In-memory counter (reset after 100 trades)
- Optional: SQLite table for historical tracking
- Fields: `timestamp`, `trade_type`, `confidence`, `factor_used`, `latency_ms`, `user_feedback` (optional)

**Integration Points:**
- `TradeTypeClassifier.classify()` → Records classification result
- `enableIntelligentExits()` → Records latency
- Discord notification system → Sends daily (17:00 UTC) and weekly (Sunday 17:00 UTC) summaries
- Logging system → Writes daily summary (after every 100 trades)

**Configuration:**
```python
# config.py
CLASSIFICATION_METRICS_ENABLED: bool = True
CLASSIFICATION_METRICS_DISCORD_DAILY: bool = True     # Daily Discord summary at 17:00 UTC
CLASSIFICATION_METRICS_DISCORD_WEEKLY: bool = True    # Weekly Discord summary (Sunday 17:00 UTC)
CLASSIFICATION_METRICS_LOG_SUMMARY: bool = True       # Daily log summary (after 100 trades)
CLASSIFICATION_METRICS_WINDOW_SIZE: int = 100        # Rolling window size for log summary
CLASSIFICATION_METRICS_DISCORD_DAILY_SCHEDULE: str = "0 17 * * *"   # Daily at 17:00 UTC
CLASSIFICATION_METRICS_DISCORD_WEEKLY_SCHEDULE: str = "0 17 * * 0" # Sunday at 17:00 UTC
```

---

## 🚀 Deployment Strategy

### Phase 1A: Development (Week 1)

1. Create `TradeTypeClassifier` class
2. Implement classification logic
3. Write unit tests
4. Integration with `enableIntelligentExits()`
5. Add logging and transparency
6. Create `classification_metrics.py` component
7. Integrate Discord notification for daily (17:00 UTC) and weekly (Sunday 17:00 UTC) summaries

### Phase 1B: Testing (Week 2)

1. Run integration tests
2. Manual testing checklist
3. Performance validation
4. Edge case testing
5. Documentation review

### Phase 1C: Rollout (Week 3)

1. Deploy to staging environment
2. Monitor for 48 hours (shadow mode - log but don't apply)
3. Enable for 10% of trades (A/B test)
4. Monitor classification accuracy
5. Full rollout if metrics pass

### Rollback Plan

- Feature flag: `ENABLE_TRADE_TYPE_CLASSIFICATION` (default: `False`)
- If issues detected → Disable flag, revert to current behavior
- All trades default to INTRADAY parameters (safe fallback)

---

## 🔮 Future Phases (Not in MVP)

### Phase 2: Dynamic Mode Switching
- Monitor volatility during trade
- Switch SCALP ↔ INTRADAY mid-trade if regime changes
- Conservative thresholds (prevent whipsaw)

### Phase 3: Advanced Classification
- Volatility Quality Index (VQI)
- Confidence weighting system
- Session-specific calibration curves

### Phase 4: Self-Learning
- Historical Feedback Loop (HFL)
- Auto-tune classification thresholds
- Learn from user corrections

---

## 📝 Summary

**What This Solves:**
- ✅ Scalp trades take profit faster (25% breakeven, 40% partial)
- ✅ Intraday trades maintain profit maximization (30% breakeven, 60% partial)
- ✅ Automatic classification based on stop size, keywords, session

**What It Doesn't Do (Yet):**
- ❌ Mid-trade mode switching
- ❌ Self-learning from historical performance
- ❌ Complex volatility quality filtering

**Complexity Level:** **LOW** (MVP focused on simplicity and reliability)

**Implementation Time:** 2-3 weeks (development, testing, rollout)

**Risk Level:** **LOW** (fallback to current behavior always available)

---

## ✅ Decision Points

Before implementation, confirm:

1. **Parameter Values:** Are SCALP parameters (25%/40%/70%) acceptable?
2. **Keyword List:** Should we expand keyword detection beyond "scalp", "swing"?
3. **Session Strategy:** Do we trust `getCurrentSession()` strategy field?
4. **Fallback Behavior:** Is default INTRADAY acceptable when ambiguous?
5. **Performance Budget:** Is < 500ms classification latency acceptable?

---

**Next Steps:**
1. Review and approve this plan
2. Confirm parameter values
3. Begin implementation (Phase 1A)

