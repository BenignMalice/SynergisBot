# Trade Analysis Speed Optimization Guide

**Current Speed:** 5-6 seconds per analysis  
**Target Speed:** 1-3 seconds per analysis

---

## ⚡ **Option 1: Use Faster OpenAI Model (RECOMMENDED)**

### **Quick Fix - Change Model in `.env` file:**
```env
# FAST: 1-2 seconds, good quality, cheapest
OPENAI_MODEL=gpt-4o-mini

# BALANCED: 2-3 seconds, best quality
OPENAI_MODEL=gpt-4o

# SLOW: 5-6 seconds, reasoning model (current)
OPENAI_MODEL=gpt-5-thinking
```

**Impact:** Reduces analysis time from **5-6s → 1-2s** (70% faster!)

**Trade-offs:**
- `gpt-4o-mini`: Fastest, cheapest, slightly less sophisticated reasoning
- `gpt-4o`: Best balance of speed and quality
- `gpt-5-thinking`: Slowest but provides detailed reasoning (current)

---

## 🔧 **Option 2: Disable Critic (Double Speed)**

The bot currently runs:
1. **Gate Analysis** (rule-based, <1s)
2. **LLM Recommendation** (GPT call, 5-6s)
3. **Critic Review** (another GPT call, 5-6s)

**Total: 10-12 seconds**

### Disable Critic:
Add to `.env`:
```env
# Skip the critic review step (not recommended for live trading)
USE_CRITIC=0
```

**Impact:** Reduces total time from **10-12s → 5-6s**

**⚠️ Warning:** The critic catches bad trades. Only disable for testing!

---

## 🚀 **Option 3: Parallel Processing (Advanced)** ✅ IMPLEMENTED

Run the Prompt Router and Fallback LLM in parallel, use whichever finishes first.

**Now Available!** Enable in `.env`:
```env
USE_PARALLEL_ANALYSIS=1        # Run Router + Fallback concurrently
PARALLEL_TIMEOUT=15.0          # Maximum wait time (seconds)
```

**How it Works:**
1. Both Router and Fallback start analyzing simultaneously
2. First successful result wins
3. Other task is cancelled
4. If both fail, returns error gracefully

**Example Timeline:**
```
Without Parallel:
Router (attempt 1) → 5s → fails
Fallback → 6s → success
TOTAL: 11 seconds

With Parallel:
Router + Fallback (both start)
Fallback finishes first → 6s → success
Router cancelled
TOTAL: 6 seconds (45% faster!)
```

**Impact:** Reduces worst-case time by **30-40%**

**When to Use:**
- ✓ Volatile markets (Router might skip, fallback slower)
- ✓ Want maximum reliability + speed
- ⚠️ Uses more resources (2× API calls if both complete)

---

## 📊 **Option 4: Fast Feature Computation** ✅ IMPLEMENTED

The full Feature Builder computes 200+ indicators across 4 timeframes, which takes ~2 seconds.

**Now Available!** Enable lightweight features in `.env`:
```env
USE_FAST_FEATURES=1            # Use FastFeatureBuilder (75% faster)
```

**What's Included (Fast Mode):**

✅ **Keep (Essential):**
- Price data (OHLC)
- Core EMAs (20, 50, 200)
- ATR, ADX, RSI
- Bollinger Bands (upper, middle, lower, width)
- Volume
- Regime classification

❌ **Skip (Expensive):**
- Pattern detection (200+ patterns)
- Structure analysis (FVG, liquidity sweeps, BOS/CHOCH)
- Microstructure features
- Cross-timeframe correlations
- Session overlap calculations

**Speed Comparison:**
```
┌─────────────────┬──────────┬─────────────────┐
│ Mode            │ Time     │ Features        │
├─────────────────┼──────────┼─────────────────┤
│ Full Features   │ ~2.0s    │ 200+ indicators │
│ Fast Features   │ ~0.5s    │ ~20 essentials  │
└─────────────────┴──────────┴─────────────────┘
```

**Impact:** Reduces pre-processing from **~2s → ~0.5s (75% faster!)**

**Trade-off:** Less context for decision-making (good for quick scans, not deep analysis)

**When to Use:**
- ✓ Signal scanning across multiple symbols
- ✓ Real-time position monitoring
- ✓ Development/testing iterations
- ✗ Detailed trade entry analysis (use full features)

---

## 🎯 **Recommended Setup for Speed:**

### **Setup 1: Live Trading (Balanced Speed + Quality)** ⭐ RECOMMENDED
```env
# Model
OPENAI_MODEL=gpt-4o                 # 2-3s per call, excellent quality

# Core Features
USE_PROMPT_ROUTER=1                 # Optimized templates
SESSION_RULES_ENABLED=1             # Filter bad trades early
USE_CRITIC=1                        # Keep safety checks

# Advanced Speed (Optional)
USE_PARALLEL_ANALYSIS=0             # Disabled (costs more API calls)
USE_FAST_FEATURES=0                 # Full features for quality
```
**Total Time: ~4-6 seconds**  
**Quality: Excellent**  
**Cost: $$**

---

### **Setup 2: Aggressive Speed (Testing/Scanning)** 🚀 FASTEST
```env
# Model
OPENAI_MODEL=gpt-4o-mini            # 1-2s per call

# Core Features
USE_PROMPT_ROUTER=1                 # Optimized templates
SESSION_RULES_ENABLED=1             # Filter bad trades early
USE_CRITIC=0                        # Skip for speed (testing only!)

# Advanced Speed
USE_PARALLEL_ANALYSIS=1             # Run Router + Fallback in parallel
USE_FAST_FEATURES=1                 # Lightweight computation
PARALLEL_TIMEOUT=10.0               # Shorter timeout
```
**Total Time: ~1-2 seconds** 🔥  
**Quality: Good (sufficient for testing)**  
**Cost: $ (cheapest)**

---

### **Setup 3: Maximum Reliability (Volatile Markets)** 💪
```env
# Model
OPENAI_MODEL=gpt-4o                 # Best quality

# Core Features
USE_PROMPT_ROUTER=1                 # Try Router first
SESSION_RULES_ENABLED=1             # Session filtering
USE_CRITIC=1                        # Full validation

# Advanced Speed
USE_PARALLEL_ANALYSIS=1             # Fallback ready immediately
USE_FAST_FEATURES=0                 # Full features for accuracy
PARALLEL_TIMEOUT=15.0               # Generous timeout
```
**Total Time: ~4-6 seconds (but never fails)**  
**Quality: Excellent + Reliable**  
**Cost: $$$ (highest, but worth it for reliability)**

---

## 📈 **Speed Comparison:**

| Configuration | Analysis Time | Quality | Cost | Use Case |
|--------------|---------------|---------|------|----------|
| **Current** (gpt-5-thinking + critic + full features) | 10-12s | Best | $$$$ | Deep analysis |
| **Setup 1** (gpt-4o + critic + full features) ⭐ | 4-6s | Excellent | $$$ | Live trading |
| **Setup 2** (gpt-4o-mini + fast + parallel) 🚀 | 1-2s | Good | $ | Testing/scanning |
| **Setup 3** (gpt-4o + parallel + full) 💪 | 4-6s | Excellent | $$$$ | Volatile markets |

### **Cumulative Speed Gains:**

```
Starting Point (Current): 10-12 seconds
↓ Switch to gpt-4o              → 4-6s    (50% faster) ✓
↓ + Fast Features               → 2.5-4s  (75% faster) ✓✓
↓ + Parallel Analysis           → 2-3s    (80% faster) ✓✓✓
```

**Maximum possible speedup: 80-85% (10s → 2s)** 🎉

---

## 🛠️ **How to Apply:**

1. **Edit your `.env` file** in the project root
2. **Add or change:** `OPENAI_MODEL=gpt-4o-mini`
3. **Restart the bot:** `python trade_bot.py`
4. **Test:** Run `/trade XAUUSD` and measure the time

---

## 💡 **Pro Tip:**

Monitor the logs to see actual timing:
```
[INFO] infra.prompt_router: Router analysis completed in 1.2s
[INFO] infra.openai_service: LLM recommendation completed in 2.1s
[INFO] infra.openai_service: Critic review completed in 1.8s
```

The "openai-processing-ms" header in the logs shows the actual OpenAI API processing time:
```
openai-processing-ms: 5778  ← This is 5.8 seconds!
```

---

## ✅ **Next Steps:**

1. **Test `gpt-4o-mini` first** (easiest, biggest impact)
2. **If quality drops, try `gpt-4o`** (balanced option)
3. **Consider disabling critic** only for development/testing
4. **Profile the bot** to find other bottlenecks (MT5 connection, feature computation)

---

**Questions?**
- Check current model: Look at logs for `[INFO] infra.openai_service: Using model: gpt-...`
- Test different models: Add `OPENAI_MODEL=` to `.env` and restart
- Monitor quality: Compare recommendations between models on the same symbol

