# Response Structure Analysis - What's Actually Included

**Date**: December 8, 2025  
**Question**: Are price, session, news, and MTF analysis included in the structured response data that ChatGPT receives?

---

## Current Status

### ✅ **Included in Structured Data**

1. **Current Price**: ✅ `response.data.current_price` (line 1161)
2. **MTF Analysis**: ✅ `response.data.smc.timeframes` (line 1174)
3. **Macro Data**: ✅ `response.data.macro.data` (line 1165)

### ⚠️ **Only in Summary Text (NOT in Structured Data)**

1. **Session Information**: ⚠️ Only in `response.summary` text (line 1132: `🕒 Session: {session_context}`)
2. **News Status**: ⚠️ Only in `response.summary` text (line 1133: `📰 {news_guardrail}`)

---

## Problem

**ChatGPT can read the summary text**, but structured data is better for:
- Programmatic access
- Reliable field extraction
- Consistent behavior
- Tool usage validation

**If session and news are only in summary text**, ChatGPT might:
- Miss the data if it focuses on structured fields
- Have difficulty extracting specific values
- Need to parse text instead of accessing fields directly

---

## Solution: Add Session and News to Structured Data

Add these fields to the `response.data` structure in `_format_unified_analysis`:

```python
return {
    "summary": summary,
    "data": {
        "symbol": symbol,
        "symbol_normalized": symbol_normalized,
        "current_price": current_price,
        
        # ✅ NEW: Add session information
        "session": {
            "name": session_info.primary_session if session_info else "UNKNOWN",
            "is_overlap": session_info.is_overlap if session_info else False,
            "overlap_type": session_info.overlap_type if session_info else None,
            "minutes_into_session": session_info.minutes_into_session if session_info else 0,
            "minutes_remaining": minutes_remaining if session_info else 0,
            "context": session_context  # Formatted string for convenience
        },
        
        # ✅ NEW: Add news status
        "news": {
            "upcoming_events": upcoming_events if upcoming_events else [],
            "next_event": next_event if next_event else None,
            "high_impact_count": len(high_impact_events) if high_impact_events else 0,
            "guardrail": news_guardrail  # Formatted string for convenience
        },
        
        "macro": {
            "bias": macro_bias,
            "summary": macro_summary,
            "data": macro_data_obj
        },
        "smc": {
            # ... existing fields ...
        },
        # ... rest of data ...
    }
}
```

---

## Implementation Steps

1. **Extract session info** in `_format_unified_analysis`:
   - Call `SessionNewsFeatures.get_session_info()` (already done in `_extract_session_context`)
   - Store structured session data

2. **Extract news info** in `_format_unified_analysis`:
   - Call `NewsService.get_upcoming_events()` (already done in `_extract_news_guardrail`)
   - Store structured news data

3. **Add to return structure**:
   - Add `"session"` dict to `response.data`
   - Add `"news"` dict to `response.data`

4. **Update knowledge documents**:
   - Document `response.data.session` structure
   - Document `response.data.news` structure

5. **Update openai.yaml**:
   - Document session and news fields in tool schema

---

## Verification

After implementation, verify:
- ✅ `response.data.session.name` is accessible
- ✅ `response.data.session.minutes_remaining` is accessible
- ✅ `response.data.news.upcoming_events` is accessible
- ✅ `response.data.news.next_event` is accessible
- ✅ ChatGPT can access these fields programmatically

