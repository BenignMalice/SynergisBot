# What `moneybot.analyse_symbol_full` Includes Internally

**Date**: December 8, 2025  
**Question**: Does `analyse_symbol_full` include `getCurrentPrice`, `getCurrentSession`, and `getNewsStatus` data?

---

## ✅ **Answer: YES - All Included Internally**

When ChatGPT calls `moneybot.analyse_symbol_full`, it **automatically includes** all the data from:
- ✅ `getCurrentPrice` (via MT5 direct fetch)
- ✅ `getCurrentSession` (via `SessionNewsFeatures`)
- ✅ `getNewsStatus` (via `NewsService`)
- ✅ `macro_context` (via `tool_macro_context`)

**ChatGPT does NOT need to call these tools separately** - they're all included in the response.

---

## 📊 **What's Included in `analyse_symbol_full` Response**

### **1. Current Price** ✅
**Source**: Fetched directly from MT5 (not via `getCurrentPrice` tool)
```python
# Line 2393-2395 in desktop_agent.py
tick = mt5.symbol_info_tick(symbol_normalized)
if tick:
    current_price = float(tick.bid)
```

**Included in Response**:
- `response.data.current_price` - Current bid price
- Also used throughout analysis for distance calculations, entry/SL/TP

---

### **2. Session Information** ✅
**Source**: `SessionNewsFeatures.get_session_info()` (internal)
```python
# Line 697-741 in desktop_agent.py
def _extract_session_context(m5_data: Dict) -> str:
    from infra.feature_session_news import SessionNewsFeatures
    session_features = SessionNewsFeatures()
    session_info = session_features.get_session_info()
    session_name = session_info.primary_session
    # ... extracts session details
```

**Included in Response**:
- `response.summary` includes: `🕒 Session: {session_context}`
- Session name (ASIA, LONDON, NY, WEEKEND, CRYPTO)
- Overlap information
- Minutes into session / remaining
- Session warnings (ending soon, etc.)

**Example Output**:
```
🕒 Session: LONDON session · 240min remaining
```

---

### **3. News Status** ✅
**Source**: `NewsService.get_upcoming_events()` (internal)
```python
# Line 816-827 in desktop_agent.py
def _extract_news_guardrail(macro: Dict[str, Any]) -> str:
    from infra.news_service import NewsService
    news_service = NewsService()
    upcoming_events = news_service.get_upcoming_events(limit=5, hours_ahead=24)
    # ... formats news warnings
```

**Included in Response**:
- `response.summary` includes: `📰 {news_guardrail}`
- Upcoming macro events (next 24 hours)
- Upcoming crypto events
- Risk level (LOW, MEDIUM, HIGH)
- Recommendations (e.g., "CAUTION - Upcoming events: Japanese GDP")

**Example Output**:
```
📰 CAUTION - Upcoming events: 12:48 [BREAKING] investingLive Asia-pacific market news wrap: Japanese GDP on (high). Consider tighter stops or smaller positions.
```

---

### **4. Macro Context** ✅
**Source**: `tool_macro_context()` (called internally)
```python
# Line 2067 in desktop_agent.py
macro_data = await tool_macro_context({"symbol": symbol})
```

**Included in Response**:
- `response.data.macro` - Full macro data object
- DXY, US10Y, VIX, S&P 500
- BTC Dominance, Crypto Fear & Greed Index
- Symbol-specific macro analysis
- Macro bias score

**Example Output**:
```
🌍 Macro Context:
DXY 98.86 📉 Falling · US10Y 4.10% ➖ Neutral · VIX 17.44 ⚠️ Elevated · S&P500 +0.26%
BTC Dominance 57.8% 🔵 Strong inflow · Fear & Greed = 33 (Fear)
→ Mixed sentiment: neutral risk tone, crypto slightly risk-off
```

---

## 🔍 **What ChatGPT Did (Redundant but Not Wrong)**

In the user's example, ChatGPT called:
1. ✅ `getCurrentPrice` - **REDUNDANT** (included in `analyse_symbol_full`)
2. ✅ `getCurrentSession` - **REDUNDANT** (included in `analyse_symbol_full`)
3. ✅ `getNewsStatus` - **REDUNDANT** (included in `analyse_symbol_full`)
4. ❌ `getMultiTimeframeAnalysis` - **WRONG TOOL** (should have used `analyse_symbol_full`)

**Why This Happened**:
- ChatGPT may have been trying to gather data before analysis
- Or it may not have realized `analyse_symbol_full` includes everything
- The tool selection guidance may not be clear enough

---

## ✅ **Correct Usage**

**When user asks "Analyse XAUUSD":**

**✅ CORRECT**:
```json
{
  "tool": "moneybot.analyse_symbol_full",
  "arguments": {
    "symbol": "XAUUSD"
  }
}
```

**Response includes**:
- ✅ Current price (from MT5)
- ✅ Session information (from SessionNewsFeatures)
- ✅ News status (from NewsService)
- ✅ Macro context (from tool_macro_context)
- ✅ Volatility regime detection (with advanced states)
- ✅ Detailed volatility metrics
- ✅ Strategy recommendations
- ✅ SMC analysis
- ✅ Advanced features
- ✅ M1 microstructure
- ✅ Complete unified analysis

**❌ INCORRECT** (What ChatGPT did):
```json
// Step 1: getCurrentPrice - REDUNDANT
// Step 2: getCurrentSession - REDUNDANT
// Step 3: getNewsStatus - REDUNDANT
// Step 4: getMultiTimeframeAnalysis - WRONG TOOL
```

---

## 📋 **Summary**

| Data | Included in `analyse_symbol_full`? | Source |
|------|-------------------------------------|--------|
| **Current Price** | ✅ **YES** | MT5 direct fetch (line 2393) |
| **Session Info** | ✅ **YES** | `SessionNewsFeatures` (line 697) |
| **News Status** | ✅ **YES** | `NewsService` (line 816) |
| **Macro Context** | ✅ **YES** | `tool_macro_context` (line 2067) |
| **Volatility Regime** | ✅ **YES** | `RegimeDetector` (line 2155) |
| **Volatility Metrics** | ✅ **YES** | `RegimeDetector.detect_regime()` |
| **Strategy Recommendations** | ✅ **YES** | `volatility_strategy_mapper` (line 2230) |

---

## 🎯 **Recommendation**

**Update tool descriptions to clarify**:
- `analyse_symbol_full` includes ALL data (price, session, news, macro, volatility, etc.)
- ChatGPT should NOT call `getCurrentPrice`, `getCurrentSession`, or `getNewsStatus` separately
- These tools are only needed if user specifically requests JUST that data without full analysis

**Update `openai.yaml`**:
```yaml
analyseSymbolFull:
  description: "🎯 MANDATORY: Use this tool when user asks to 'analyze [symbol]' or requests general market analysis. ⚡ INCLUDES EVERYTHING: Current price (from MT5), session information, news status, macro context, volatility regime detection, detailed volatility metrics, strategy recommendations, SMC analysis, advanced features, M1 microstructure, and complete unified analysis. ⚠️ DO NOT call getCurrentPrice, getCurrentSession, or getNewsStatus separately - they're all included in this response."
```

---

**Conclusion**: `analyse_symbol_full` is a **complete all-in-one analysis tool** - no separate calls needed! ✅

