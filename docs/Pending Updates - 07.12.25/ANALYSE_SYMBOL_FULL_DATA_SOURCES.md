# How `analyse_symbol_full` Gets Data - Technical Details

**Date**: December 8, 2025  
**Question**: Does `analyse_symbol_full` call other tools or get the same data from the same sources?

---

## Answer: Gets Same Data from Same Sources (Not via Tool Calls)

`analyse_symbol_full` **does NOT call** the ChatGPT tool endpoints (`getCurrentPrice`, `getCurrentSession`, `getNewsStatus`), but it **does access the same underlying services** to get the same data.

**Exception**: It **DOES call** `tool_get_multi_timeframe_analysis` internally (line 2470 in `desktop_agent.py`).

---

## Data Sources Breakdown

### 1. Current Price ✅

**Source**: Direct MT5 API call (NOT via `getCurrentPrice` tool)
```python
# desktop_agent.py line 2437-2440
import MetaTrader5 as mt5
tick = mt5.symbol_info_tick(symbol_normalized)
if tick:
    current_price = float(tick.bid)
```

**Same as**: `getCurrentPrice` tool also uses `mt5.symbol_info_tick()` - same source, different access path

**Included in Response**: `response.data.current_price`

---

### 2. Session Information ✅

**Source**: `SessionNewsFeatures.get_session_info()` (internal service, NOT via `getCurrentSession` tool)
```python
# desktop_agent.py line 700-702
from infra.feature_session_news import SessionNewsFeatures
session_features = SessionNewsFeatures()
session_info = session_features.get_session_info()
```

**Same as**: `getCurrentSession` tool also uses `SessionNewsFeatures.get_session_info()` - same source, different access path

**Included in Response**: `response.summary` includes session context (e.g., "🕒 Session: LONDON session · 240min remaining")

---

### 3. News Status ✅

**Source**: `NewsService.get_upcoming_events()` (internal service, NOT via `getNewsStatus` tool)
```python
# desktop_agent.py line 819-824
from infra.news_service import NewsService
news_service = NewsService()
upcoming_events = news_service.get_upcoming_events(limit=5, hours_ahead=24)
```

**Same as**: `getNewsStatus` tool also uses `NewsService.get_upcoming_events()` - same source, different access path

**Included in Response**: News status included in analysis summary

---

### 4. Multi-Timeframe Analysis ✅

**Source**: **Calls `tool_get_multi_timeframe_analysis` internally** (line 2470)
```python
# desktop_agent.py line 2470
smc_data = await tool_get_multi_timeframe_analysis({"symbol": symbol})
smc_layer = smc_data.get("data", {})
```

**This is the ONLY tool call**: `analyse_symbol_full` actually calls `getMultiTimeframeAnalysis` internally, then formats the response with additional layers.

**Included in Response**: `response.data.smc.timeframes` (H4, H1, M30, M15, M5) with CHOCH/BOS per timeframe

---

## Summary Table

| Data | Source | Tool Call? | Same as Tool? |
|------|--------|------------|---------------|
| **Current Price** | MT5 direct (`mt5.symbol_info_tick`) | ❌ No | ✅ Yes - same source |
| **Session Info** | `SessionNewsFeatures.get_session_info()` | ❌ No | ✅ Yes - same source |
| **News Status** | `NewsService.get_upcoming_events()` | ❌ No | ✅ Yes - same source |
| **MTF Analysis** | `tool_get_multi_timeframe_analysis()` | ✅ **YES** | ✅ Yes - actually calls the tool |

---

## Why This Matters

**For ChatGPT Tool Selection:**

1. **Price, Session, News**: `analyse_symbol_full` gets the same data from the same sources, so ChatGPT doesn't need to call these tools separately
2. **MTF Analysis**: `analyse_symbol_full` calls `getMultiTimeframeAnalysis` internally, so ChatGPT doesn't need to call it separately
3. **Result**: ChatGPT should call `analyse_symbol_full` once, not 4 separate tools

**Technical Note:**
- The tool endpoints (`getCurrentPrice`, `getCurrentSession`, `getNewsStatus`) are wrappers around the same services
- `analyse_symbol_full` accesses the services directly (more efficient)
- Both approaches get the same data, but `analyse_symbol_full` is more efficient

---

## Conclusion

**✅ `analyse_symbol_full` includes all the data** that the separate tools provide:
- ✅ Current price (same source as `getCurrentPrice`)
- ✅ Session information (same source as `getCurrentSession`)
- ✅ News status (same source as `getNewsStatus`)
- ✅ Multi-timeframe analysis (actually calls `getMultiTimeframeAnalysis` internally)

**ChatGPT should use `analyse_symbol_full` for general analysis** and NOT call the other tools separately.

---

## Files Updated

1. ✅ `2.UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md` - Updated "Fresh Price Rule" section to clarify `analyse_symbol_full` includes price, session, news, and MTF analysis

