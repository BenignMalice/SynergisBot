# News Integration Guide

## 📰 Overview

Yes, you **DO have news integration** with your trading bot! The `NewsService` provides news-awareness functionality to help avoid trading during high-impact news events and to inform trading decisions.

---

## 🎯 What It Does

### 1. **News Blackout Detection**
Prevents trading during high-impact news events by checking if you're within a "blackout window" (minutes before/after the event).

### 2. **News Summaries for AI**
Provides upcoming news event summaries to ChatGPT/AI for context-aware trade recommendations.

### 3. **Event Categorization**
- **Macro**: Forex/commodities news (NFP, CPI, Fed decisions, etc.)
- **Crypto**: Crypto-specific events (Bitcoin ETF, regulatory news, etc.)

### 4. **Impact Levels**
- **Low**: Minor economic indicators
- **Medium**: Moderate impact events
- **High**: Major economic releases (CPI, employment data)
- **Ultra**: Critical events (NFP, Fed rate decisions, core CPI)
- **Crypto**: Crypto-specific high-impact events

---

## 🔧 How It Works

### Architecture

```
fetch_news_feed.py (Manual/Cron)
    ↓
Fetches from Forex Factory XML feed
    ↓
Parses & categorizes events
    ↓
Saves to data/news_events.json
    ↓
NewsService (infra/news_service.py)
    ↓
Loads events on demand
    ↓
Used by:
    ├─→ handlers/trading.py (trade_command)
    └─→ ChatGPT system prompts
```

---

## 📂 Key Files

### 1. **News Service** (`infra/news_service.py`)
Core service that provides:
- `summary_for_prompt()`: Returns upcoming news summary for AI
- `is_blackout()`: Checks if within news blackout window
- `next_event_time()`: Gets next scheduled event
- `summarise_events()`: Lists events within a time window

### 2. **News Events Data** (`data/news_events.json`)
JSON file containing all scheduled news events:
```json
[
  {
    "time": "2025-08-17T22:30:00Z",
    "description": "Non-Farm Payrolls",
    "impact": "ultra",
    "category": "macro",
    "symbols": ["USD"]
  },
  {
    "time": "2025-08-18T12:30:00Z",
    "description": "CPI m/m",
    "impact": "ultra",
    "category": "macro",
    "symbols": ["USD"]
  }
]
```

### 3. **News Fetcher** (`fetch_news_feed.py`)
Script to fetch and update news events from Forex Factory:
```python
# Fetches from Forex Factory weekly XML feed
FEED_URL = "http://nfs.faireconomy.media/ff_calendar_thisweek.xml"

# Saves to data/news_events.json
NEWS_EVENTS_JSON = os.path.join(BASE_DIR, "data", "news_events.json")
```

### 4. **Configuration** (`config/settings.py`)
Blackout window settings:
```python
# News integration
NEWS_EVENTS_PATH = "data/news_events.json"

# High impact events (e.g., employment data)
NEWS_HIGH_IMPACT_BEFORE_MIN = 30  # 30 min before
NEWS_HIGH_IMPACT_AFTER_MIN = 30   # 30 min after

# Ultra high impact events (e.g., NFP, Fed decisions)
NEWS_ULTRA_HIGH_BEFORE_MIN = 60   # 1 hour before
NEWS_ULTRA_HIGH_AFTER_MIN = 90    # 1.5 hours after

# Crypto events
NEWS_CRYPTO_BEFORE_MIN = 15       # 15 min before
NEWS_CRYPTO_AFTER_MIN = 30        # 30 min after
```

---

## 🚀 Usage

### 1. **Update News Events** (Manual)

Run the news fetcher script to update events:

```bash
python fetch_news_feed.py
```

**Output**:
```
Fetching news feed from http://nfs.faireconomy.media/ff_calendar_thisweek.xml
Saved 127 events to data/news_events.json
```

**Recommended**: Run this **weekly** (or set up a cron job) to keep events up-to-date.

---

### 2. **Automatic Integration in Trading**

The news service is **automatically integrated** into the `/trade` command:

```python
# In handlers/trading.py (trade_command function)
try:
    ns = NewsService()
    # Determine category by symbol
    category = "crypto" if ("BTC" in sym or "ETH" in sym) else "macro"
    now_dt = datetime.utcnow()
    
    # Get news summaries for AI context
    tech["news_events"] = ns.summarise_events(
        category=category, now=now_dt, window_min=30
    )
    tech["news_summary"] = ns.summary_for_prompt(
        category=category, now=now_dt, hours_ahead=12
    )
    
    # Check if in news blackout
    tech["news_block"] = ns.is_blackout(category=category, now=now_dt)
except Exception:
    # If NewsService fails, continue without news data
    pass
```

**What this does**:
1. Checks if you're within a news blackout window
2. Provides upcoming news summary to the AI
3. AI can factor news into trade recommendations

---

### 3. **News Blackout Behavior**

When `news_block = True`:
- The AI is informed there's a high-impact news event nearby
- Trade recommendations may be more conservative
- The system suggests waiting until after the event

**Example AI prompt context**:
```
News Summary (next 12h): 14:30 Non-Farm Payrolls (ultra) | 16:00 Fed Minutes (high)
News Blackout: True (within 60 min of ultra-high impact event)
```

---

## 📊 Example Scenarios

### Scenario 1: Trading Before NFP

**Time**: 13:30 UTC (1 hour before NFP at 14:30)

```python
ns = NewsService()
is_blackout = ns.is_blackout(category="macro", now=datetime(2025, 8, 17, 13, 30))
# Returns: True (within 60 min before ultra-high event)

summary = ns.summary_for_prompt(category="macro", now=datetime(2025, 8, 17, 13, 30), hours_ahead=2)
# Returns: "14:30 Non-Farm Payrolls (ultra)"
```

**AI Response**:
```
⚠️ News Alert: Non-Farm Payrolls in 1 hour (ultra-high impact)
Recommendation: HOLD - Wait for NFP release and volatility to settle
```

---

### Scenario 2: Trading After Event

**Time**: 16:00 UTC (1.5 hours after NFP)

```python
is_blackout = ns.is_blackout(category="macro", now=datetime(2025, 8, 17, 16, 0))
# Returns: False (90 min after ultra-high event = outside blackout)

summary = ns.summary_for_prompt(category="macro", now=datetime(2025, 8, 17, 16, 0), hours_ahead=12)
# Returns: "" (no upcoming high-impact events)
```

**AI Response**:
```
✅ Clear to trade - No major news events in next 12 hours
🟢 BUY XAUUSD @ 3925 | SL: 3915 | TP: 3945
```

---

### Scenario 3: Crypto Trading

**Time**: 10:00 UTC (Bitcoin ETF decision at 10:30)

```python
ns = NewsService()
is_blackout = ns.is_blackout(category="crypto", now=datetime(2025, 8, 17, 10, 0))
# Returns: True (within 15 min before crypto event)

summary = ns.summary_for_prompt(category="crypto", now=datetime(2025, 8, 17, 10, 0), hours_ahead=2)
# Returns: "10:30 Bitcoin ETF Decision (crypto)"
```

**AI Response**:
```
⚠️ Crypto News Alert: Bitcoin ETF Decision in 30 minutes
Recommendation: HOLD - High volatility expected
```

---

## 🔧 Customization

### 1. **Adjust Blackout Windows**

Edit `config/settings.py`:

```python
# More conservative (wider blackout windows)
NEWS_HIGH_IMPACT_BEFORE_MIN = 60  # 1 hour before
NEWS_HIGH_IMPACT_AFTER_MIN = 60   # 1 hour after

NEWS_ULTRA_HIGH_BEFORE_MIN = 120  # 2 hours before
NEWS_ULTRA_HIGH_AFTER_MIN = 180   # 3 hours after
```

### 2. **Add Custom Events**

Manually edit `data/news_events.json`:

```json
[
  {
    "time": "2025-10-10T14:00:00Z",
    "description": "Custom Event - Earnings Call",
    "impact": "high",
    "category": "macro",
    "symbols": ["USD"]
  }
]
```

### 3. **Change News Feed Source**

Edit `fetch_news_feed.py`:

```python
# Use a different feed (e.g., Financial Modeling Prep API)
FEED_URL = "https://financialmodelingprep.com/api/v3/economic_calendar?apikey=YOUR_KEY"
```

---

## 🤖 Integration with ChatGPT Bot

### Current Status

**NOT directly integrated** with `chatgpt_bot.py` yet. The news service is currently only used in:
- `handlers/trading.py` (the `/trade` command)
- FastAPI analysis endpoints

### How to Integrate with ChatGPT Bot

Add news awareness to ChatGPT conversations:

<function_calls>
<invoke name="read_file">
<parameter name="target_file">handlers/chatgpt_bridge.py
