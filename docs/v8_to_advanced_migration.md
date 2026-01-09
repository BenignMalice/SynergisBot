# V8 → Advanced Terminology Migration Summary

## Completed Files ✅

### 1. decision_engine.py
- Updated `rec_out["v8"]` → `rec_out["advanced"]`
- Updated comments "v8 features" → "advanced features"
- Updated anchor tags `V8_FEATURES_GUARDS` → `ADVANCED_FEATURES_GUARDS`

### 2. desktop_agent.py
- Updated all variable names: `v8_adjusted` → `advanced_adjusted`
- Updated data keys: `v8_rmag_stretch` → `advanced_rmag_stretch`
- Updated user messages: "V8 Insights" → "Advanced Insights"
- Updated comments: "LOG V8 ANALYTICS" → "LOG ADVANCED ANALYTICS"

### 3. handlers/chatgpt_bridge.py
- Updated API response key: `result["v8"]` → `result["advanced"]`
- Updated all ChatGPT instructions (33 occurrences)
- "V8-ENHANCED" → "ADVANCED-ENHANCED"
- "V8-ADAPTIVE" → "ADVANCED-ADAPTIVE"
- "v8_insights" → "advanced_insights"
- "v8_summary" → "advanced_summary"

## Remaining Files to Update 📝

### Critical Priority (API/Core Logic):

**app/main_api.py** (5 references):
- Line 835: Comment "V8-adjusted percentages" → "Advanced-adjusted percentages"
- Line 3028: Docstring "Get V8 Advanced" → "Get Advanced"
- Line 3093: Comment "Enhanced with V8" → "Enhanced with Advanced"
- Line 3101: Comment "V8: Institutional" → "Advanced: Institutional"
- Line 3118: Comment "Initialize analyzer with V8" → "Initialize analyzer with Advanced"
- Line 3125: Variable `v8_summary` → `advanced_summary`

**infra/intelligent_exit_manager.py** (7 references):
- Line 284: Docstring "Calculate adaptive trigger levels based on V8"
- Line 290: Return doc "advanced_factors: List of V8 factors"
- Line 460: "Dict with rule and V8 adjustment details"
- Line 463: Comment "Calculate V8-adjusted triggers"
- Line 519: Log message "Failed to log V8 rule"
- Line 527: Log message "V8-adjusted"
- Line 529: Log message "V8 factors"

**chatgpt_bot.py** (5 references):
- Line 454: Comment "Calculate trigger prices for notification (using V8-adjusted percentages)"
- Line 462: Comment "Use V8-adjusted trigger percentages"
- Line 469: Comment "Build V8 adjustment message"
- Line 480: Message text "V8 Adjusted: {advanced_breakeven_pct}"
- Line 2652: Log "Base: X → V8: Y"

**infra/feature_builder_advanced.py** (2 references):
- Line 2: Module docstring "Feature Builder v8" → "Feature Builder Advanced"
- Line 778: Comment "Convenience function to build v8 features"

**infra/advanced_analytics.py** (7 references):
- Line 2: Module docstring "V8 Feature Analytics"
- Line 5: Docstring "Tracks V8 feature performance"
- Line 164: Comment "Tracks V8 feature values"
- Line 182: Log "V8 analytics database initialized"
- Line 184: Log error "Error initializing V8 analytics"
- Line 206: Comment "advanced_features: V8 feature dict"
- **Class name: `V8FeatureTracker`** → Consider renaming to `AdvancedFeatureTracker` (Breaking change!)

### Medium Priority (Infrastructure):

**infra/multi_timeframe_analyzer.py** (7 references):
- Line 15: Comment "Enhanced with V8 Advanced Technical Features"
- Line 24: Comment "V8 Enhancement:"
- Line 37: Docstring "Perform complete multi-timeframe analysis with V8 enhancement"
- Line 47: Return doc "V8 advanced indicators and insights"
- Line 424: Comment "Enhanced with V8 confidence adjustments"

**infra/conversation_logger.py** (2 references):
- Line 76: SQL column comment "JSON: V8 enrichment fields"
- Line 225: Parameter doc "advanced_features: Dict with V8 enrichment fields"

**infra/gpt_orchestrator.py** (2 references):
- Line 14: Comment "Binance + MT5 + V8 + OrderFlow"
- Line 97: Parameter doc "advanced_features: V8 indicators (optional)"

**infra/gpt_reasoner.py** (4 references):
- Line 32: Comment "V8 indicators"
- Line 73: Parameter doc "advanced_features: V8 indicator features (optional)"
- Line 174: Comment "V8 indicator warnings (especially RMAG >2σ)"
- Line 247: Section header "## V8 Indicators (Institutional Grade)"

**infra/gpt_validator.py** (3 references):
- Line 81: Parameter doc "advanced_features: V8 indicators"
- Line 247: Section header "## V8 Institutional Indicators"
- Line 349: Example reasoning "V8 clean"

**infra/trade_close_logger.py** (4 references):
- Line 243: Comment "UPDATE V8 ANALYTICS (NEW)"
- Line 274: Comment "Update V8 analytics"
- Line 284: Log "Updated V8 analytics for ticket"
- Line 287: Log debug "Could not update V8 analytics"

**infra/price_cache.py** (1 reference):
- Line 8: Comment "Fast retrieval for V8 indicators"

**handlers/advanced_dashboard.py** (5 references):
- Line 2: Module docstring "V8 Performance Dashboard Handler"
- Line 5: Description "Telegram command handlers for viewing V8 feature performance"
- Line 23: Command description "/v8dashboard - Show V8 feature performance dashboard"
- Line 69: Message "📊 **V8 Performance Dashboard**"
- **Command name: `/v8dashboard`** → Consider `/advanceddashboard` or `/dashboard`

### Low Priority (Tests):

**tests/test_advanced_features.py** (2 references):
- Line 2: Module docstring "Unit Tests for V8 Advanced Technical Features"
- Line 374: Print "V8 ADVANCED TECHNICAL FEATURES - UNIT TEST SUITE"

**tests/test_advanced_exits.py** (2 references):
- Line 161: Assertion message "No V8 factors should be applied"
- Line 227: Print "✅ ALL V8 EXIT TESTS PASSED!"

## Breaking Changes ⚠️

### API Response Keys (Already Updated):
- ✅ `decision_engine.py:835` - `rec_out["v8"]` → `rec_out["advanced"]`
- ✅ `handlers/chatgpt_bridge.py:574` - `result["v8"]` → `result["advanced"]`

### Class Names (Needs Discussion):
- `infra/advanced_analytics.py` - `V8FeatureTracker` class
  - Used in: desktop_agent.py, trade_close_logger.py
  - **Recommendation**: Keep class name for backward compatibility, just update docstrings

### Command Names (Needs Discussion):
- `/v8dashboard` command in handlers/advanced_dashboard.py
  - **Recommendation**: Add alias `/advanceddashboard` but keep `/v8dashboard` for compatibility

## Schema Updates Needed:

**openai.yaml**:
- Update all `v8` field references to `advanced`
- Update tool descriptions
- Update response schemas

## Migration Strategy:

1. ✅ **Phase 1** - Core API keys (COMPLETED)
   - decision_engine.py
   - desktop_agent.py
   - handlers/chatgpt_bridge.py

2. **Phase 2** - API Layer (IN PROGRESS)
   - app/main_api.py
   - infra/intelligent_exit_manager.py
   - chatgpt_bot.py

3. **Phase 3** - Infrastructure
   - All infra/* modules
   - handlers/advanced_dashboard.py

4. **Phase 4** - Tests & Documentation
   - tests/*
   - All .md documentation files

5. **Phase 5** - Schema & Config
   - openai.yaml
   - Any JSON config files

## Testing After Migration:

1. Run test suite: `python test_advanced_features.py`
2. Test API endpoints: Check `/api/v1/features/advanced/{symbol}`
3. Test ChatGPT integration: Verify advanced features appear correctly
4. Test intelligent exits: Verify Advanced-adjusted percentages work
5. Check logs: Ensure no "V8" references in new log entries

## Notes:

- All user-facing V8 references have been updated to "Advanced"
- Internal code comments updated for consistency
- Log messages updated to reflect new terminology
- ChatGPT instructions comprehensively updated
- API data keys migrated (breaking change for external consumers)
