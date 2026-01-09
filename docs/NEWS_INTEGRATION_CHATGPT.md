# News Integration with ChatGPT Bot - Implementation Summary

## ✅ What Was Added

### 1. **Automatic News Fetching at Bot Startup**

The bot now automatically fetches the latest news events from Forex Factory when it starts.

**Location**: `chatgpt_bot.py` → `main()` function

**Implementation**:
```python
# Fetch latest news events at startup
logger.info("📰 Fetching latest news events...")
try:
    import subprocess
    result = subprocess.run(
        ["python", "fetch_news_feed.py"],
        capture_output=True,
        text=True,
        timeout=30
    )
    if result.returncode == 0:
        logger.info("✅ News events updated successfully")
        if result.stdout:
            logger.info(f"   {result.stdout.strip()}")
    else:
        logger.warning(f"⚠️ News fetch failed: {result.stderr}")
except Exception as e:
    logger.warning(f"⚠️ Could not fetch news events: {e}")
    logger.info("   → Bot will continue with existing news data")
```

**What it does**:
- Runs `fetch_news_feed.py` at bot startup
- Fetches latest events from Forex Factory XML feed
- Updates `data/news_events.json`
- Logs success/failure
- Bot continues even if news fetch fails (uses existing data)

---

### 2. **News Context in ChatGPT Conversations**

ChatGPT now receives news awareness context in every conversation.

**Location**: `handlers/chatgpt_bridge.py` → `chatgpt_message()` function

**Implementation**:
```python
# Add news context to system prompt
news_context = ""
try:
    from infra.news_service import NewsService
    from datetime import datetime
    
    ns = NewsService()
    now = datetime.utcnow()
    
    # Get news summary for next 12 hours
    news_summary = ns.summary_for_prompt(category="macro", now=now, hours_ahead=12)
    crypto_summary = ns.summary_for_prompt(category="crypto", now=now, hours_ahead=12)
    
    # Check if in blackout
    macro_blackout = ns.is_blackout(category="macro", now=now)
    crypto_blackout = ns.is_blackout(category="crypto", now=now)
    
    if news_summary or crypto_summary or macro_blackout or crypto_blackout:
        news_context = "\n\n📰 **NEWS AWARENESS:**\n"
        
        if macro_blackout:
            news_context += "⚠️ **MACRO NEWS BLACKOUT ACTIVE** - High-impact forex/commodities event nearby. Trade with caution or wait.\n"
        if crypto_blackout:
            news_context += "⚠️ **CRYPTO NEWS BLACKOUT ACTIVE** - High-impact crypto event nearby. Trade with caution or wait.\n"
        
        if news_summary:
            news_context += f"📊 Upcoming Macro Events (12h): {news_summary}\n"
        if crypto_summary:
            news_context += f"₿ Upcoming Crypto Events (12h): {crypto_summary}\n"
        
        if macro_blackout or crypto_blackout:
            news_context += "\n💡 **Recommendation:** Consider waiting until after the event or use tighter stops.\n"
except Exception as e:
    logger.warning(f"Could not load news context: {e}")

messages = [
    {
        "role": "system",
        "content": system_content + news_context  # Added to system prompt
    }
]
```

**What it does**:
- Checks for upcoming news events (next 12 hours)
- Detects if currently in news blackout window
- Adds news context to ChatGPT's system prompt
- ChatGPT can now factor news into recommendations

---

## 📊 Example Scenarios

### Scenario 1: Normal Trading (No News)

**User**: "Give me a trade for XAUUSD"

**ChatGPT receives**:
```
System Prompt: You are a trading assistant...
[No news context added - clear to trade]
```

**ChatGPT responds**:
```
🟢 **BUY XAUUSD**
📊 Entry: $3,925.00
🛑 SL: $3,915.00
🎯 TP: $3,945.00
💡 Reason: RSI 45 (neutral), ADX 35 (trending), price above EMA20
```

---

### Scenario 2: News Blackout Active (NFP in 30 minutes)

**User**: "Give me a trade for XAUUSD"

**ChatGPT receives**:
```
System Prompt: You are a trading assistant...

📰 **NEWS AWARENESS:**
⚠️ **MACRO NEWS BLACKOUT ACTIVE** - High-impact forex/commodities event nearby. Trade with caution or wait.
📊 Upcoming Macro Events (12h): 14:30 Non-Farm Payrolls (ultra)

💡 **Recommendation:** Consider waiting until after the event or use tighter stops.
```

**ChatGPT responds**:
```
⚠️ **News Alert: Non-Farm Payrolls in 30 minutes**

I recommend **WAITING** until after the NFP release (14:30 UTC).

**Why?**
• NFP is an ultra-high impact event
• Expected volatility: 50-100+ pips in seconds
• Current blackout window: 60 min before, 90 min after
• Risk of stop-hunting and whipsaws

**Alternative:**
If you MUST trade now, use:
• Tighter stops (0.5R instead of 1R)
• Smaller position size (50% of normal)
• Wider TP targets (wait for post-NFP move)

**Best Action:** Wait 2 hours for volatility to settle.
```

---

### Scenario 3: Upcoming News (CPI in 4 hours)

**User**: "Give me a trade for EURUSD"

**ChatGPT receives**:
```
System Prompt: You are a trading assistant...

📰 **NEWS AWARENESS:**
📊 Upcoming Macro Events (12h): 12:30 CPI m/m (ultra) | 14:00 Fed Minutes (high)
```

**ChatGPT responds**:
```
🟢 **BUY EURUSD**
📊 Entry: $1.0850
🛑 SL: $1.0840
🎯 TP: $1.0870

💡 **Reason:** RSI 42 (oversold), price bouncing from EMA50 support

⚠️ **News Alert:**
• CPI release in 4 hours (12:30 UTC) - ultra-high impact
• Recommend closing before 11:30 UTC or using tight trailing stop
• Volatility expected to spike after CPI

**Trade Plan:**
1. Enter now while market is calm
2. Trail stop to breakeven at +10 pips
3. Consider closing 1 hour before CPI if not at TP
```

---

### Scenario 4: Crypto News (Bitcoin ETF Decision)

**User**: "Give me a trade for BTCUSD"

**ChatGPT receives**:
```
System Prompt: You are a trading assistant...

📰 **NEWS AWARENESS:**
⚠️ **CRYPTO NEWS BLACKOUT ACTIVE** - High-impact crypto event nearby. Trade with caution or wait.
₿ Upcoming Crypto Events (12h): 10:30 Bitcoin ETF Decision (crypto)

💡 **Recommendation:** Consider waiting until after the event or use tighter stops.
```

**ChatGPT responds**:
```
⚠️ **Crypto News Alert: Bitcoin ETF Decision in 15 minutes**

**Recommendation: WAIT**

**Why?**
• ETF decisions cause 5-10% swings in minutes
• Current blackout: 15 min before, 30 min after
• High risk of liquidation cascades

**Post-Event Strategy:**
• Wait 30-60 minutes after announcement
• Look for clear direction (breakout/breakdown)
• Trade the follow-through move, not the initial spike

**If Approved:** Look for BUY on pullback
**If Rejected:** Look for SELL on bounce
```

---

## 🔧 Configuration

### Blackout Windows

Configured in `config/settings.py`:

```python
# High impact events (e.g., CPI, employment data)
NEWS_HIGH_IMPACT_BEFORE_MIN = 30  # 30 min before
NEWS_HIGH_IMPACT_AFTER_MIN = 30   # 30 min after

# Ultra high impact events (e.g., NFP, Fed decisions)
NEWS_ULTRA_HIGH_BEFORE_MIN = 60   # 1 hour before
NEWS_ULTRA_HIGH_AFTER_MIN = 90    # 1.5 hours after

# Crypto events
NEWS_CRYPTO_BEFORE_MIN = 15       # 15 min before
NEWS_CRYPTO_AFTER_MIN = 30        # 30 min after
```

### News Fetch Frequency

- **At bot startup**: Automatic
- **Manual update**: Run `python fetch_news_feed.py`
- **Recommended**: Set up a daily cron job or Windows Task Scheduler

---

## 📝 Startup Logs

When you start the bot, you'll see:

```
🤖 Starting ChatGPT Telegram Bot with Background Monitoring...
📰 Fetching latest news events...
Fetching news feed from http://nfs.faireconomy.media/ff_calendar_thisweek.xml
Saved 127 events to data/news_events.json
✅ News events updated successfully
   Saved 127 events to data/news_events.json
✅ ChatGPT conversation logger initialized
...
```

---

## 🎯 Benefits

### 1. **Automatic News Awareness**
- No manual news checking required
- ChatGPT automatically knows about upcoming events
- Reduces risk of trading into high-impact news

### 2. **Context-Aware Recommendations**
- ChatGPT factors news into trade timing
- Suggests waiting or tighter stops during blackouts
- Provides post-event trading strategies

### 3. **Always Up-to-Date**
- News fetched at every bot startup
- Uses latest Forex Factory data
- No stale event data

### 4. **Graceful Degradation**
- If news fetch fails, bot continues with existing data
- If NewsService fails, conversations continue without news context
- No breaking errors

---

## 🔍 Testing

### Test 1: Check News Fetch at Startup

```bash
python chatgpt_bot.py
```

**Expected output**:
```
📰 Fetching latest news events...
✅ News events updated successfully
   Saved 127 events to data/news_events.json
```

### Test 2: Ask ChatGPT During News Blackout

**Setup**: Manually edit `data/news_events.json` to add an event in 30 minutes:
```json
{
  "time": "2025-10-06T12:30:00Z",  # 30 min from now
  "description": "Test NFP",
  "impact": "ultra",
  "category": "macro",
  "symbols": ["USD"]
}
```

**Test**: Ask ChatGPT for a trade on XAUUSD

**Expected**: ChatGPT warns about upcoming NFP and recommends waiting

### Test 3: Check News Context in Logs

Enable debug logging in `handlers/chatgpt_bridge.py`:
```python
logger.info(f"News context added: {news_context}")
```

---

## 📚 Related Files

| File | Purpose |
|------|---------|
| `chatgpt_bot.py` | Fetches news at startup |
| `handlers/chatgpt_bridge.py` | Adds news to ChatGPT context |
| `infra/news_service.py` | Core news service |
| `fetch_news_feed.py` | Fetches events from Forex Factory |
| `data/news_events.json` | Stores news events |
| `config/settings.py` | Blackout window configuration |

---

## 🚀 Status

✅ **News fetching at startup** - Implemented  
✅ **News context in ChatGPT** - Implemented  
✅ **Blackout detection** - Active  
✅ **Upcoming events summary** - Active  
✅ **Graceful error handling** - Implemented  

---

**Implementation Complete!** 🎉

ChatGPT now has full news awareness and will automatically warn users about high-impact events, suggest waiting during blackouts, and provide context-aware trading recommendations.
