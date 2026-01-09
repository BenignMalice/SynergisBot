# Confluence Score Dashboard - Multi-Timeframe Display

**Date**: December 15, 2025  
**Status**: 📋 **PLAN READY FOR IMPLEMENTATION**  
**Priority**: **MEDIUM**

---

## Feature Overview

Add a real-time confluence score dashboard on the auto-execution view page (`/auto-execution/view`) that displays multi-timeframe confluence scores for XAUUSDc and BTCUSDc across M1, M5, M15, and H1 timeframes.

**User Story**: As a trader, I want to quickly see confluence scores across multiple timeframes for my primary symbols (XAUUSDc and BTCUSDc) so I can assess trade setup quality at a glance without leaving the auto-execution page.

---

## Current State Analysis

### Existing Infrastructure

1. **Backend API** (`app/main_api.py` line ~4486):
   - Endpoint: `/api/v1/confluence/{symbol}`
   - Returns: Single composite score (0-100) with grade and factors
   - Implementation: Uses `ConfluenceCalculator.calculate_confluence()`

2. **Confluence Calculator** (`infra/confluence_calculator.py`):
   - Method: `calculate_confluence(symbol: str) -> Dict`
   - Calculates weighted composite score across M5, M15, M30, H1, H4
   - Factors: Trend alignment, momentum, support/resistance, volume, volatility
   - **Limitation**: Returns single composite score, not per-timeframe breakdown

3. **UI Location** (`app/main_api.py` line ~1377-1417):
   - TradingView widgets for XAUUSD and BTCUSD
   - Dark theme styling (#0f172a background, #24324a borders)

4. **M1 Data**:
   - Available via `M1MicrostructureAnalyzer` (different calculation method)
   - Uses microstructure analysis, not standard MTF indicators
   - May require separate endpoint or special handling

---

## Implementation Plan

### Phase 1: Backend API Enhancement

#### 1.1 Extend ConfluenceCalculator

**File**: `infra/confluence_calculator.py`

**Add Method**:
```python
def calculate_confluence_per_timeframe(self, symbol: str) -> Dict[str, Dict]:
    """
    Calculate confluence score for each timeframe separately
    
    Returns:
        {
            "M1": {"score": 75, "grade": "B", "factors": {...}, "available": True},
            "M5": {"score": 82, "grade": "A", "factors": {...}, "available": True},
            "M15": {"score": 78, "grade": "B", "factors": {...}, "available": True},
            "H1": {"score": 85, "grade": "A", "factors": {...}, "available": True}
        }
    """
```

**Implementation Details**:
- Extract timeframe-specific data from `indicator_bridge.get_multi(symbol)`
- For M5, M15, H1: Use existing factor calculation methods per timeframe
- For M1: Use `M1MicrostructureAnalyzer.calculate_microstructure_confluence()` if available
- Return `"available": False` if timeframe data is missing
- Each timeframe gets its own grade (A/B/C/D/F) based on score

**Challenges**:
- M1 uses different calculation (microstructure vs MTF indicators)
- Need to handle missing timeframes gracefully
- May need to cache M1 data separately

#### 1.2 Create New API Endpoint

**File**: `app/main_api.py` (after line ~4507)

**Endpoint**: `/api/v1/confluence/multi-timeframe/{symbol}`

**Response Format**:
```json
{
  "symbol": "XAUUSDc",
  "timeframes": {
    "M1": {
      "score": 75,
      "grade": "B",
      "available": true,
      "factors": {
        "trend_alignment": 70,
        "momentum_alignment": 80,
        "support_resistance": 75,
        "volume_confirmation": 60,
        "volatility_health": 80
      }
    },
    "M5": {
      "score": 82,
      "grade": "A",
      "available": true,
      "factors": {...}
    },
    "M15": {
      "score": 78,
      "grade": "B",
      "available": true,
      "factors": {...}
    },
    "H1": {
      "score": 85,
      "grade": "A",
      "available": true,
      "factors": {...}
    }
  },
  "timestamp": "2025-12-15T10:30:00Z",
  "cache_age_seconds": 0
}
```

**Error Handling**:
- If symbol not found: Return 404 with error message
- If data unavailable: Return timeframes with `"available": false`
- If calculation error: Return 500 with error details

#### 1.3 Optional: Batch Endpoint

**Endpoint**: `/api/v1/confluence/multi-timeframe?symbols=XAUUSDc,BTCUSDc`

**Benefits**:
- Single request for both symbols
- Reduced network overhead
- Better performance

**Response Format**:
```json
{
  "results": {
    "XAUUSDc": { /* per-timeframe data */ },
    "BTCUSDc": { /* per-timeframe data */ }
  },
  "timestamp": "2025-12-15T10:30:00Z"
}
```

---

### Phase 2: Frontend UI Implementation

#### 2.1 UI Component Location

**File**: `app/main_api.py` (around line ~1377-1417, where TradingView widgets are)

**Placement**: Above or below TradingView tickers

#### 2.2 HTML Structure

```html
<div class="confluence-dashboard" style="background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #24324a; margin-bottom: 20px;">
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
    <h3 style="margin: 0; color: #e6edf3; font-size: 18px;">Multi-Timeframe Confluence</h3>
    <button id="refreshConfluence" style="padding: 6px 12px; border-radius: 6px; border: 1px solid #2b3b57; background: #1b2a44; color: #e6edf3; cursor: pointer;">
      Refresh
    </button>
  </div>
  
  <div class="confluence-symbols" style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
    <!-- XAUUSDc Block -->
    <div class="confluence-symbol-block" data-symbol="XAUUSDc">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <span style="color: #90c0ff; font-weight: bold; font-size: 16px;">XAUUSDc</span>
        <button class="show-confluence-btn" data-symbol="XAUUSDc" style="padding: 4px 8px; border-radius: 4px; border: 1px solid #2b3b57; background: #1b2a44; color: #e6edf3; cursor: pointer; font-size: 12px;">
          Show Confluence
        </button>
      </div>
      <div class="confluence-results" data-symbol="XAUUSDc" style="display: none; margin-top: 8px;">
        <!-- Results table will be inserted here -->
      </div>
    </div>
    
    <!-- BTCUSDc Block -->
    <div class="confluence-symbol-block" data-symbol="BTCUSDc">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <span style="color: #90c0ff; font-weight: bold; font-size: 16px;">BTCUSDc</span>
        <button class="show-confluence-btn" data-symbol="BTCUSDc" style="padding: 4px 8px; border-radius: 4px; border: 1px solid #2b3b57; background: #1b2a44; color: #e6edf3; cursor: pointer; font-size: 12px;">
          Show Confluence
        </button>
      </div>
      <div class="confluence-results" data-symbol="BTCUSDc" style="display: none; margin-top: 8px;">
        <!-- Results table will be inserted here -->
      </div>
    </div>
  </div>
</div>
```

#### 2.3 JavaScript Implementation

**Location**: In the `<script>` section of `/auto-execution/view` endpoint

**Functions**:
```javascript
// Fetch confluence data for a symbol
async function fetchConfluenceData(symbol) {
  try {
    const response = await fetch(`/api/v1/confluence/multi-timeframe/${symbol}`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error(`Error fetching confluence for ${symbol}:`, error);
    return null;
  }
}

// Render confluence table
function renderConfluenceTable(symbol, data) {
  const resultsDiv = document.querySelector(`.confluence-results[data-symbol="${symbol}"]`);
  if (!resultsDiv || !data || !data.timeframes) {
    return;
  }
  
  let html = '<table style="width: 100%; border-collapse: collapse; font-size: 13px;">';
  html += '<thead><tr style="border-bottom: 1px solid #24324a;">';
  html += '<th style="text-align: left; padding: 6px; color: #90c0ff;">Timeframe</th>';
  html += '<th style="text-align: center; padding: 6px; color: #90c0ff;">Score</th>';
  html += '<th style="text-align: center; padding: 6px; color: #90c0ff;">Grade</th>';
  html += '<th style="text-align: left; padding: 6px; color: #90c0ff;">Visual</th>';
  html += '</tr></thead><tbody>';
  
  const timeframes = ['M1', 'M5', 'M15', 'H1'];
  timeframes.forEach(tf => {
    const tfData = data.timeframes[tf];
    if (!tfData || !tfData.available) {
      html += `<tr><td>${tf}</td><td colspan="3" style="text-align: center; color: #9fb0c3;">N/A</td></tr>`;
      return;
    }
    
    const score = Math.round(tfData.score);
    const grade = tfData.grade;
    const color = getScoreColor(score);
    const gradeColor = getGradeColor(grade);
    const barWidth = Math.round((score / 100) * 100);
    
    html += `<tr style="border-bottom: 1px solid #24324a;">`;
    html += `<td style="padding: 6px; color: #e6edf3;">${tf}</td>`;
    html += `<td style="text-align: center; padding: 6px; color: ${color}; font-weight: bold;">${score}</td>`;
    html += `<td style="text-align: center; padding: 6px; color: ${gradeColor}; font-weight: bold;">${grade}</td>`;
    html += `<td style="padding: 6px;"><div style="background: #0f172a; border: 1px solid #24324a; border-radius: 4px; height: 20px; position: relative;">`;
    html += `<div style="background: ${color}; height: 100%; width: ${barWidth}%; border-radius: 4px; transition: width 0.3s;"></div></div></td>`;
    html += `</tr>`;
  });
  
  html += '</tbody></table>';
  html += `<div style="margin-top: 8px; font-size: 11px; color: #9fb0c3; text-align: right;">Updated: ${new Date(data.timestamp).toLocaleTimeString()}</div>`;
  
  resultsDiv.innerHTML = html;
  resultsDiv.style.display = 'block';
}

// Color coding helpers
function getScoreColor(score) {
  if (score >= 80) return '#22c55e'; // Green
  if (score >= 60) return '#eab308'; // Yellow
  return '#ef4444'; // Red
}

function getGradeColor(grade) {
  if (grade === 'A') return '#22c55e';
  if (grade === 'B') return '#eab308';
  if (grade === 'C') return '#f59e0b';
  if (grade === 'D') return '#f97316';
  return '#ef4444'; // F
}

// Button click handler
document.addEventListener('click', async (e) => {
  if (e.target.classList.contains('show-confluence-btn')) {
    const symbol = e.target.dataset.symbol;
    const resultsDiv = document.querySelector(`.confluence-results[data-symbol="${symbol}"]`);
    const button = e.target;
    
    // Toggle display
    if (resultsDiv.style.display === 'none' || !resultsDiv.style.display) {
      // Show loading state
      button.textContent = 'Loading...';
      button.disabled = true;
      resultsDiv.innerHTML = '<div style="text-align: center; color: #9fb0c3; padding: 12px;">Loading...</div>';
      resultsDiv.style.display = 'block';
      
      // Fetch data
      const data = await fetchConfluenceData(symbol);
      
      if (data) {
        renderConfluenceTable(symbol, data);
        button.textContent = 'Hide Confluence';
      } else {
        resultsDiv.innerHTML = '<div style="text-align: center; color: #ef4444; padding: 12px;">Error loading data</div>';
        button.textContent = 'Show Confluence';
      }
      
      button.disabled = false;
    } else {
      resultsDiv.style.display = 'none';
      button.textContent = 'Show Confluence';
    }
  }
});

// Refresh all button
document.addEventListener('click', async (e) => {
  if (e.target.id === 'refreshConfluence') {
    const buttons = document.querySelectorAll('.show-confluence-btn');
    buttons.forEach(async (btn) => {
      if (btn.textContent === 'Hide Confluence') {
        const symbol = btn.dataset.symbol;
        btn.textContent = 'Loading...';
        btn.disabled = true;
        
        const data = await fetchConfluenceData(symbol);
        if (data) {
          renderConfluenceTable(symbol, data);
        }
        
        btn.disabled = false;
      }
    });
  }
});
```

---

### Phase 3: M1 Special Handling

#### 3.1 M1 Confluence Calculation

**File**: `infra/m1_microstructure_analyzer.py` (if method exists) or create new method

**Approach**:
- Check if `M1MicrostructureAnalyzer.calculate_microstructure_confluence()` exists
- If not, create wrapper method that:
  - Fetches M1 data via `m1_data_fetcher.fetch_m1_data(symbol, count=200)`
  - Analyzes microstructure via `m1_analyzer.analyze_microstructure()`
  - Calculates confluence score based on:
    - VWAP proximity
    - Edge location
    - Candle signals
    - Volume confirmation
    - Volatility state

**Integration**:
- In `ConfluenceCalculator.calculate_confluence_per_timeframe()`:
  - For M1: Call M1-specific calculation
  - For M5/M15/H1: Use existing factor calculations per timeframe

---

### Phase 4: Caching Strategy

#### 4.1 Backend Caching

**Location**: `ConfluenceCalculator` class

**Implementation**:
```python
from functools import lru_cache
from datetime import datetime, timedelta

class ConfluenceCalculator:
    def __init__(self, indicator_bridge):
        self.indicator_bridge = indicator_bridge
        self._cache = {}  # {symbol: (data, timestamp)}
        self._cache_ttl = 30  # seconds
    
    def calculate_confluence_per_timeframe(self, symbol: str) -> Dict:
        # Check cache
        if symbol in self._cache:
            data, timestamp = self._cache[symbol]
            if (datetime.utcnow() - timestamp).total_seconds() < self._cache_ttl:
                return data
        
        # Calculate fresh
        result = self._calculate_per_timeframe(symbol)
        
        # Update cache
        self._cache[symbol] = (result, datetime.utcnow())
        return result
```

**Cache TTL**: 30 seconds (balance between freshness and performance)

---

### Phase 5: Error Handling & Edge Cases

#### 5.1 Missing Timeframes

**Handling**:
- Return `"available": false` for missing timeframes
- Display "N/A" in UI
- Don't block other timeframes from displaying

#### 5.2 M1 Data Unavailable

**Handling**:
- Check if M1 analyzer is active
- If not, return M1 with `"available": false`
- Log warning but don't fail entire request

#### 5.3 API Errors

**Handling**:
- Try-catch in JavaScript
- Display user-friendly error message
- Allow retry without page refresh

#### 5.4 Symbol Not Found

**Handling**:
- Return 404 with clear error message
- UI shows "Symbol not found" message

---

## Visual Design Specifications

### Color Scheme (Match Existing Theme)

- **Background**: `#0f172a` (dark blue)
- **Borders**: `#24324a` (medium blue)
- **Text Primary**: `#e6edf3` (light gray)
- **Text Secondary**: `#9fb0c3` (medium gray)
- **Accent**: `#90c0ff` (light blue)
- **Score Colors**:
  - Green (≥80): `#22c55e`
  - Yellow (60-79): `#eab308`
  - Red (<60): `#ef4444`

### Layout

```
┌─────────────────────────────────────────────────────┐
│ Multi-Timeframe Confluence          [Refresh]        │
├─────────────────────────────────────────────────────┤
│                                                       │
│  ┌──────────────────┐  ┌──────────────────┐        │
│  │ XAUUSDc          │  │ BTCUSDc          │        │
│  │ [Show Confluence]│  │ [Show Confluence]│        │
│  │                  │  │                  │        │
│  │ Timeframe |Score |  │ Timeframe |Score │        │
│  │ M1        | 75 B │  │ M1        | 65 C │        │
│  │ M5        | 82 A │  │ M5        | 78 B │        │
│  │ M15       | 78 B │  │ M15       | 72 B │        │
│  │ H1        | 85 A │  │ H1        | 75 B │        │
│  └──────────────────┘  └──────────────────┘        │
└─────────────────────────────────────────────────────┘
```

---

## Testing Checklist

### Backend Tests

- [ ] Test `/api/v1/confluence/multi-timeframe/XAUUSDc` returns correct structure
- [ ] Test all timeframes (M1, M5, M15, H1) are included
- [ ] Test missing timeframe handling (returns `"available": false`)
- [ ] Test M1 calculation when M1 analyzer is available
- [ ] Test M1 calculation when M1 analyzer is unavailable
- [ ] Test caching (same request within 30s returns cached data)
- [ ] Test error handling (invalid symbol, calculation errors)
- [ ] Test batch endpoint (if implemented)

### Frontend Tests

- [ ] Test button click toggles display
- [ ] Test loading state shows while fetching
- [ ] Test table renders correctly with all timeframes
- [ ] Test color coding (green/yellow/red based on score)
- [ ] Test "N/A" display for unavailable timeframes
- [ ] Test error message display on API failure
- [ ] Test refresh button updates all visible tables
- [ ] Test responsive layout (mobile/tablet)

### Integration Tests

- [ ] Test end-to-end: Click button → Fetch data → Display table
- [ ] Test with both symbols (XAUUSDc and BTCUSDc)
- [ ] Test with missing M1 data
- [ ] Test with all timeframes available
- [ ] Test cache behavior (second request uses cache)

---

## Performance Considerations

1. **Caching**: 30-second cache reduces API calls
2. **Lazy Loading**: Only fetch when user clicks "Show Confluence"
3. **Batch Endpoint**: Optional batch endpoint reduces requests
4. **Async Loading**: Non-blocking UI updates

---

## Future Enhancements (Optional)

1. **Auto-Refresh**: Option to auto-refresh every 30-60 seconds
2. **Historical View**: Show score trends over time
3. **Factor Breakdown**: Expandable rows showing individual factors
4. **Comparison Mode**: Side-by-side comparison of symbols
5. **Alerts**: Notify when confluence score crosses thresholds
6. **Export**: Export confluence data to CSV/JSON

---

## Implementation Order

1. ✅ **Phase 1.1**: Extend `ConfluenceCalculator` with per-timeframe method
2. ✅ **Phase 1.2**: Create new API endpoint `/api/v1/confluence/multi-timeframe/{symbol}`
3. ✅ **Phase 3**: Implement M1 special handling
4. ✅ **Phase 4**: Add caching
5. ✅ **Phase 2**: Implement frontend UI
6. ✅ **Phase 5**: Add error handling
7. ✅ **Testing**: Run all test cases
8. ✅ **Phase 1.3**: Optional batch endpoint

---

## Success Criteria

- [ ] Users can click "Show Confluence" button for XAUUSDc and BTCUSDc
- [ ] Table displays scores for M1, M5, M15, H1 timeframes
- [ ] Scores are color-coded (green/yellow/red)
- [ ] Grades (A/B/C/D/F) are displayed
- [ ] Missing timeframes show "N/A"
- [ ] Data refreshes correctly
- [ ] Performance is acceptable (< 1 second load time)
- [ ] Error handling works gracefully

---

**Status**: ✅ **READY FOR IMPLEMENTATION**
