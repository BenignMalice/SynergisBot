# 📰 Additional News Data Sources Needed

## 🎯 Current News Infrastructure

### ✅ What You Already Have:

**1. Forex Factory XML Feed**
- **Source:** `http://nfs.faireconomy.media/ff_calendar_thisweek.xml`
- **Script:** `fetch_news_feed.py`
- **Storage:** `data/news_events.json`
- **Update Frequency:** Manual (run `python fetch_news_feed.py`)
- **Coverage:** Weekly economic calendar
- **Data Fields:**
  - Event time (UTC)
  - Event description
  - Impact level (low/medium/high/ultra)
  - Country code
  - Category (macro/crypto)

**2. NewsService Infrastructure**
- **File:** `infra/news_service.py`
- **Features:**
  - News blackout detection
  - Event summaries for ChatGPT
  - Next event timing
  - Category filtering (macro/crypto)

**3. API Endpoints**
- **GET /news/status** - Blackout status + upcoming events
- **GET /news/events** - Detailed event list

---

## 🔥 CRITICAL GAPS & Required Additions

### **Gap #1: Real-Time Event Updates**

**Problem:**
- Forex Factory feed = static weekly XML
- Must run `fetch_news_feed.py` manually
- No auto-updates during trading day
- Miss last-minute changes (event time shifts, cancellations)

**Impact on News Trading:**
- ❌ **CRITICAL** - May prepare for wrong time
- ❌ Miss urgent breaking news (Fed emergency meetings)
- ❌ Trade during cancelled events

---

### **Gap #2: Actual vs Expected vs Previous Data**

**Problem:**
- Current feed only shows event name and time
- **NO actual data** (what NFP number was released?)
- **NO expected data** (what was market expecting?)
- **NO previous data** (what was last month's number?)

**Why This Matters:**
```
Example: NFP Release
❌ Current: "Non-Farm Payrolls at 8:30 AM" (just time)
✅ Needed: 
  - Expected: 175k
  - Actual: 285k
  - Previous: 180k
  - Surprise: +110k (62% beat!) → STRONG TRADE SIGNAL
```

**Impact on News Trading:**
- ❌ **CRITICAL** - Can't determine trade direction
- ❌ Can't measure surprise magnitude (beat vs miss)
- ❌ Can't filter tradeable vs non-tradeable events

---

### **Gap #3: Breaking News & Fed Speeches**

**Problem:**
- Scheduled events only (NFP, CPI, etc.)
- NO unscheduled events:
  - Fed Chair emergency speeches
  - Geopolitical events (wars, sanctions)
  - Corporate earnings surprises (tech stocks → BTC correlation)
  - Crypto-specific breaking news (ETF approvals, hacks)

**Impact on News Trading:**
- ❌ **HIGH** - Blind to market-moving events
- ❌ May trade during breaking news (unexpected volatility)

---

### **Gap #4: News Interpretation & Sentiment**

**Problem:**
- Raw data only (numbers)
- NO instant market interpretation:
  - "Hawkish Fed speech"
  - "Dovish tone despite rate hike"
  - "Market disappointed despite beat"

**Impact on News Trading:**
- ❌ **MEDIUM** - Slower reaction time
- ❌ Miss nuanced interpretations (tone vs headline)

---

### **Gap #5: Historical Event Data**

**Problem:**
- Only current week events
- NO historical database:
  - Past NFP results (trend analysis)
  - Historical volatility patterns
  - Event-specific win rates

**Impact on News Trading:**
- ❌ **MEDIUM** - Can't backtest strategies
- ❌ Can't identify best-performing event types

---

## 🚀 RECOMMENDED NEWS DATA SOURCES

### **Priority 1: Real-Time Calendar with Actual/Expected/Previous**

#### **Option A: Financial Modeling Prep (FMP) - RECOMMENDED (FREE)**

**Why:**
- ✅ **FREE tier** (250 calls/day = 7,500/month!)
- ✅ Actual vs Expected vs Previous
- ✅ Real-time economic calendar
- ✅ No credit card required for free tier
- ✅ Official public API

**API Example:**
```
GET https://financialmodelingprep.com/api/v3/economic_calendar?apikey=YOUR_KEY

Response:
[
  {
    "event": "Nonfarm Payrolls",
    "date": "2025-10-17 08:30:00",
    "country": "US",
    "actual": 285.0,
    "previous": 180.0,
    "change": 105.0,
    "changep": 58.33,  // Surprise %
    "estimate": 175.0,
    "impact": "High"
  }
]
```

**Implementation:**
```python
# fetch_fmp_calendar.py
import requests
import json
from datetime import datetime, timedelta

# Sign up at https://site.financialmodelingprep.com/developer/docs/
API_KEY = "your_api_key_here"  # FREE: 250 calls/day
BASE_URL = "https://financialmodelingprep.com/api/v3"

def fetch_fmp_calendar(days_ahead=7):
    """Fetch economic calendar from Financial Modeling Prep"""
    
    today = datetime.now()
    end_date = today + timedelta(days=days_ahead)
    
    url = f"{BASE_URL}/economic_calendar"
    params = {
        "apikey": API_KEY,
        "from": today.strftime("%Y-%m-%d"),
        "to": end_date.strftime("%Y-%m-%d")
    }
    
    response = requests.get(url, params=params)
    events = response.json()
    
    # Filter high-impact events only
    high_impact = [e for e in events if e.get("impact") == "High"]
    
    # Convert to our format
    formatted_events = []
    for event in high_impact:
        formatted_events.append({
            "time": convert_to_utc(event["date"]),
            "description": event["event"],
            "impact": classify_impact(event),
            "category": "macro",
            "symbols": map_country_to_currency(event["country"]),
            "actual": event.get("actual"),
            "expected": event.get("estimate"),
            "previous": event.get("previous"),
            "surprise_pct": event.get("changep", 0)  # Already calculated!
        })
    
    # Save to data/news_events.json
    save_events(formatted_events)
    print(f"✅ Fetched {len(formatted_events)} high-impact events from FMP")
    
def classify_impact(event):
    """Promote ultra-critical events"""
    ultra_keywords = ["Nonfarm Payrolls", "NFP", "CPI", "Core CPI", "FOMC", "Interest Rate"]
    event_name = event["event"]
    
    if any(kw.lower() in event_name.lower() for kw in ultra_keywords):
        return "ultra"
    return "high"

def map_country_to_currency(country):
    """Map country to currency symbols"""
    mapping = {
        "US": ["USD"],
        "GB": ["GBP"],
        "EU": ["EUR"],
        "JP": ["JPY"],
        "CA": ["CAD"],
        "AU": ["AUD"],
        "NZ": ["NZD"]
    }
    return mapping.get(country, ["ALL"])

def convert_to_utc(date_string):
    """Convert local time to UTC ISO format"""
    # FMP uses EST, convert to UTC
    local_dt = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
    # EST is UTC-5, so add 5 hours
    utc_dt = local_dt + timedelta(hours=5)
    return utc_dt.isoformat() + "Z"

def save_events(events):
    """Save events to news_events.json"""
    import os
    
    # Merge with existing events from Forex Factory
    existing_file = "data/news_events.json"
    existing_events = []
    
    if os.path.exists(existing_file):
        with open(existing_file, 'r') as f:
            existing_events = json.load(f)
    
    # Merge (prefer FMP data for duplicates)
    all_events = events + existing_events
    
    # Remove duplicates by time + event name
    unique_events = {}
    for event in all_events:
        key = f"{event['time']}_{event['description']}"
        unique_events[key] = event
    
    # Sort by time
    sorted_events = sorted(unique_events.values(), key=lambda x: x['time'])
    
    # Save
    os.makedirs("data", exist_ok=True)
    with open(existing_file, 'w') as f:
        json.dump(sorted_events, f, indent=2)
    
    print(f"💾 Saved {len(sorted_events)} total events to {existing_file}")

if __name__ == "__main__":
    fetch_fmp_calendar(days_ahead=7)
```

**Automation (Windows Task Scheduler):**
```batch
# fetch_news_fmp.bat
@echo off
cd C:\mt5-gpt\TelegramMoneyBot.v7
python fetch_fmp_calendar.py
echo FMP calendar updated at %date% %time%
```

**Schedule:** Run every 4 hours (6 AM, 10 AM, 2 PM, 6 PM, 10 PM)

**Free Tier Limits:**
- 250 API calls per day
- 6 calls per day = 1,800/month (well within limit)
- No credit card required

---

#### **Option B: TradingEconomics API (PREMIUM)**

**Why:**
- ✅ Most comprehensive data
- ✅ Historical event database
- ✅ Forecasts from multiple sources
- ✅ Real-time websocket updates
- ❌ PAID only ($19/month minimum)

**API Example:**
```
GET https://api.tradingeconomics.com/calendar/country/united-states?c=YOUR_KEY

Response:
{
  "Date": "2025-10-17T12:30:00",
  "Event": "Non-Farm Payrolls",
  "Actual": 285,
  "Forecast": 175,
  "TEForecast": 180,
  "Previous": 180,
  "Importance": 3,
  "Category": "Labour",
  "Unit": "Thousands"
}
```

**When to Use:**
- If you want historical backtesting (Option A doesn't have this)
- If you want multiple analyst forecasts (consensus)
- If you trade professionally (worth $19/month)

---

#### **Option C: Alpha Vantage (ALTERNATIVE - FREE)**

**Why:**
- ✅ FREE tier (500 calls/day)
- ✅ Economic indicators API
- ✅ Federal Reserve data (FOMC, interest rates)
- ⚠️ No full economic calendar (use for supplemental data)

**API Example:**
```
GET https://www.alphavantage.co/query?function=FEDERAL_FUNDS_RATE&apikey=YOUR_KEY

Response:
{
  "data": [
    {
      "date": "2025-10-01",
      "value": "5.50"
    }
  ]
}
```

**Use Case:** Supplement FMP with Fed-specific data

---

### **Priority 2: Breaking News & Real-Time Alerts**

#### **Option A: Twitter/X API (RECOMMENDED)**

**Why:**
- ✅ Instant breaking news (faster than news sites)
- ✅ Fed speeches, geopolitical events
- ✅ Crypto-specific news (SEC filings, ETF approvals)
- ✅ FREE tier available (Basic plan)

**Key Accounts to Monitor:**
```python
MONITORED_ACCOUNTS = [
    "federalreserve",   # Official Fed
    "federalreserve",   # Fed Chair Powell
    "ecb",              # European Central Bank
    "bankofengland",    # BOE
    "SEC_News",         # SEC (crypto regulations)
    "binance",          # Binance official
    "coinbase",         # Coinbase official
    "Bloomberg",        # Bloomberg Terminal
    "Forexlive",        # Forex news
    "ZeroHedge"         # Financial commentary
]
```

**Implementation:**
```python
# twitter_news_monitor.py
import tweepy
from datetime import datetime

# Twitter API credentials
API_KEY = "your_api_key"
API_SECRET = "your_api_secret"
ACCESS_TOKEN = "your_access_token"
ACCESS_SECRET = "your_access_secret"

# Setup Twitter client
client = tweepy.Client(
    bearer_token="your_bearer_token",
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET
)

class NewsStreamListener(tweepy.StreamingClient):
    def on_tweet(self, tweet):
        # Parse tweet for high-impact keywords
        keywords = ["BREAKING", "NFP", "CPI", "FOMC", "Powell", "rate decision", "emergency"]
        
        if any(kw.lower() in tweet.text.lower() for kw in keywords):
            # Create urgent alert
            alert_data = {
                "time": datetime.now().isoformat() + "Z",
                "description": f"BREAKING: {tweet.text[:200]}",
                "impact": "ultra",
                "category": "breaking",
                "symbols": ["ALL"],
                "source": "Twitter",
                "author": tweet.author_id
            }
            
            # Send to Telegram immediately
            send_telegram_alert(alert_data)
            
            # Log to database
            log_breaking_news(alert_data)

# Start monitoring
stream = NewsStreamListener(bearer_token="your_bearer_token")
stream.filter(follow=MONITORED_ACCOUNT_IDS, threaded=True)
```

**Run as Background Service:**
```python
# main_api.py (add this)
from twitter_news_monitor import start_twitter_monitor

@app.on_event("startup")
async def startup():
    # Start Twitter monitoring in background
    start_twitter_monitor()
```

---

#### **Option B: ForexLive WebSocket**

**Why:**
- ✅ Instant news interpretation (human analysts)
- ✅ "Hawkish" vs "Dovish" classifications
- ✅ Market reaction commentary
- ⚠️ No official API (requires web scraping)

**Implementation:**
```python
# forexlive_scraper.py
import requests
from bs4 import BeautifulSoup
import time

def scrape_forexlive_headlines():
    url = "https://www.forexlive.com/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    
    headlines = soup.find_all("div", class_="headline")
    
    for headline in headlines[:5]:  # Latest 5
        title = headline.find("a").text
        time_posted = headline.find("time").text
        
        # Check for high-impact keywords
        if any(kw in title for kw in ["BREAKING", "NFP", "Powell", "FOMC"]):
            # Create alert
            alert_breaking_news(title, time_posted)

# Run every 30 seconds
while True:
    scrape_forexlive_headlines()
    time.sleep(30)
```

---

### **Priority 3: News Sentiment Analysis**

#### **Option A: OpenAI GPT-4 (Use Your Existing Key)**

**Why:**
- ✅ Already integrated in your system
- ✅ Can interpret complex news
- ✅ Classify "hawkish" vs "dovish"
- ✅ NO additional API needed

**Implementation:**
```python
# news_sentiment_analyzer.py
import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

def analyze_news_sentiment(news_headline, actual, expected):
    """Use GPT-4 to interpret news impact"""
    
    prompt = f"""
You are a forex news analyst. Analyze this economic event and determine its market impact.

Event: {news_headline}
Actual: {actual}
Expected: {expected}

Provide:
1. Sentiment (bullish/bearish/neutral)
2. Magnitude (high/medium/low)
3. Affected symbols (XAUUSD, EURUSD, GBPUSD, BTCUSD)
4. Trade direction (BUY/SELL/HOLD)
5. Confidence (0-100%)

Output JSON format:
{{
  "sentiment": "bullish",
  "magnitude": "high",
  "symbols": ["XAUUSD", "EURUSD"],
  "direction": "SELL",
  "confidence": 85,
  "reasoning": "NFP beat by 62%, strong USD = bearish for gold"
}}
"""
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    
    return response.choices[0].message.content

# Usage
sentiment = analyze_news_sentiment(
    "Non-Farm Payrolls",
    actual="285K",
    expected="175K"
)
```

**Integrate with News Feed:**
```python
# fetch_investing_calendar.py (updated)
for event in events:
    if event["impact"] == "ultra":
        # Use GPT-4 to analyze surprise
        sentiment = analyze_news_sentiment(
            event["event"],
            event["actual"],
            event["expected"]
        )
        
        event["ai_sentiment"] = sentiment
        event["trade_recommendation"] = sentiment["direction"]
```

---

## 📊 Recommended Implementation Plan

### **Phase 1: Critical Upgrades (Week 1)**

**1. Financial Modeling Prep (FMP) API Integration**
```
Priority: 🔥 CRITICAL
Cost: FREE (250 calls/day = 7,500/month)
Time: 2-3 hours
Impact: Actual/Expected/Previous data → enables proper news trading
```

**Steps:**
1. Sign up at https://site.financialmodelingprep.com/developer/docs/ (free tier, no credit card)
2. Get your API key from dashboard
3. Create `fetch_fmp_calendar.py` (see code above)
4. Update `infra/news_service.py` to include actual/expected fields
5. Add Windows Task Scheduler job (run every 4 hours)
6. Test: Run script, verify `data/news_events.json` has new fields

---

**2. OpenAI Sentiment Analysis**
```
Priority: 🔥 CRITICAL
Cost: $0 (using existing key)
Time: 1-2 hours
Impact: Auto-interprets news → gives trade direction
```

**Steps:**
1. Create `news_sentiment_analyzer.py`
2. Integrate with `fetch_investing_calendar.py`
3. Store sentiment in `news_events.json`
4. ChatGPT can now read trade recommendations directly

---

### **Phase 2: Real-Time Alerts (Week 2)**

**3. Twitter/X Breaking News Monitor**
```
Priority: ⭐ HIGH
Cost: FREE (Basic API)
Time: 3-4 hours
Impact: Instant breaking news → prevents blind trading
```

**Steps:**
1. Sign up for Twitter Developer account (free)
2. Create `twitter_news_monitor.py`
3. Run as background service in `main_api.py`
4. Test: Tweet from monitored account, verify Telegram alert

---

### **Phase 3: Advanced Features (Week 3+)**

**4. Historical News Database**
```
Priority: ⭐ MEDIUM
Cost: $19/month (TradingEconomics) or FREE (build your own)
Time: 4-6 hours
Impact: Backtest strategies, optimize entry timing
```

**5. ForexLive Scraper**
```
Priority: ⭐ LOW
Cost: FREE
Time: 2-3 hours
Impact: Human analyst interpretation (nice-to-have)
```

---

## 🔧 Updated Data Structure

### **Current `news_events.json`:**
```json
[
  {
    "time": "2025-10-17T12:30:00Z",
    "description": "Non-Farm Payrolls",
    "impact": "ultra",
    "category": "macro",
    "symbols": ["USD"]
  }
]
```

### **Enhanced `news_events.json`:**
```json
[
  {
    "time": "2025-10-17T12:30:00Z",
    "description": "Non-Farm Payrolls",
    "impact": "ultra",
    "category": "macro",
    "symbols": ["USD"],
    
    // NEW FIELDS (from Investing.com API)
    "actual": "285K",
    "expected": "175K",
    "previous": "180K",
    "surprise_pct": 62.9,
    "unit": "Thousands",
    "volatility": "HIGH",
    
    // NEW FIELDS (from GPT-4 analysis)
    "ai_sentiment": {
      "sentiment": "bullish_usd",
      "magnitude": "high",
      "symbols_affected": ["XAUUSD", "EURUSD", "GBPUSD"],
      "direction": "SELL",  // For XAUUSD
      "confidence": 85,
      "reasoning": "NFP beat by 62%, strong USD = bearish for gold"
    },
    
    // NEW FIELDS (internal tracking)
    "last_updated": "2025-10-17T12:30:15Z",
    "source": "investing.com",
    "triggered": false
  }
]
```

---

## 💰 Cost Summary

| Source | Free Tier | Paid Plan | Recommended |
|--------|-----------|-----------|-------------|
| **Forex Factory XML** | ✅ FREE | N/A | ✅ Keep |
| **Financial Modeling Prep (FMP)** | ✅ 250 calls/day (7,500/mo) | $14/month | ✅ **START HERE** |
| **TradingEconomics API** | ❌ None | $19/month | ⭐ Later |
| **Alpha Vantage** | ✅ 500 calls/day | $49/month | ⭐ Supplement |
| **Twitter/X API** | ✅ Basic (free) | $100/month (Pro) | ✅ FREE tier |
| **OpenAI GPT-4** | ❌ Pay-per-use | ~$0.01-0.03/call | ✅ Already have |

**Total Monthly Cost (Recommended Setup):**
- Phase 1 (Critical): **$0/month** (FMP FREE + OpenAI existing)
- Phase 2 (Real-time): **$0/month** (Twitter FREE)
- Phase 3 (Advanced): **$19/month** (TradingEconomics optional)

---

## ✅ Implementation Checklist

**Phase 1 (Critical - Do First):**
- [ ] Sign up for Financial Modeling Prep (FMP) at https://site.financialmodelingprep.com/developer/docs/
- [ ] Get free API key (250 calls/day, no credit card required)
- [ ] Create `fetch_fmp_calendar.py` (see implementation above)
- [ ] Update `infra/news_service.py` (add actual/expected fields)
- [ ] Create `news_sentiment_analyzer.py` (GPT-4 integration)
- [ ] Set up Windows Task Scheduler (run every 4 hours)
- [ ] Test: Run `python fetch_fmp_calendar.py` manually
- [ ] Verify `data/news_events.json` has actual/expected/surprise_pct fields
- [ ] Update ChatGPT instructions to use actual/expected data

**Phase 2 (Real-Time):**
- [ ] Sign up for Twitter Developer account
- [ ] Create `twitter_news_monitor.py`
- [ ] Integrate with `main_api.py` (background service)
- [ ] Test: Verify Telegram alerts on breaking news
- [ ] Add monitored accounts (Fed, BOE, ECB, Bloomberg)

**Phase 3 (Advanced):**
- [ ] Sign up for TradingEconomics API (optional)
- [ ] Build historical news database
- [ ] Create backtest module
- [ ] Add ForexLive scraper (optional)

---

## 📞 Support & Resources

**API Documentation:**
- Investing.com: https://investing.com/api
- TradingEconomics: https://tradingeconomics.com/api
- Financial Modeling Prep: https://financialmodelingprep.com/developer/docs
- Twitter API: https://developer.twitter.com/en/docs

**Questions?**
Ask ChatGPT:
- "How do I set up Investing.com API for news data?"
- "Show me example of news sentiment analysis with GPT-4"
- "How do I automate news feed updates with Task Scheduler?"

---

**🎯 Bottom Line:**

**Start with Investing.com API (FREE) + OpenAI sentiment analysis (already have key).**

**This gives you 80% of the value for $0/month!**

**Add Twitter monitoring when you're comfortable with news trading basics.**

---

**Document Version:** 1.0  
**Last Updated:** 2025-10-14  
**Status:** Implementation Guide ✅

