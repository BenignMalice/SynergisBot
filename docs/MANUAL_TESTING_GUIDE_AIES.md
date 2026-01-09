# Manual Testing Guide - AIES Phase 1 MVP

## Prerequisites

Before starting manual testing, verify:

1. ✅ Feature flag enabled: `ENABLE_TRADE_TYPE_CLASSIFICATION=1` in `.env`
2. ✅ System restarted after enabling feature flag
3. ✅ Metrics collection enabled: `CLASSIFICATION_METRICS_ENABLED=1` (default: enabled)
4. ✅ Discord notifications configured (if testing Task 25)
5. ✅ MT5 connected and symbol data available
6. ✅ At least one open position or ability to open test positions

---

## Task 21: Test Manual Override

### Test Case 21.1: Force SCALP Classification

**Steps:**
1. Open a position with comment containing `!force:scalp`
   - Example: `"pythoncls"`
   - Or: `"Short EURUSD !force:scalp"`
2. Enable intelligent exits via ChatGPT:
   ```
   Enable intelligent exits for ticket <TICKET>
   ```
3. **Expected Results:**
   - Classification: `SCALP` (confidence: 1.0 or very high)
   - Reasoning: Contains "Manual override: !force:scalp"
   - Exit Parameters: 25% breakeven / 40% partial / 70% close
   - Log message: `📊 Trade Classification: SCALP (confidence: 1.00) - Manual override: !force:scalp`

**Verification Checklist:**
- [ ] Classification result shows `SCALP`
- [ ] Confidence is 1.0 (or ≥0.95)
- [ ] Reasoning mentions manual override
- [ ] Exit parameters are 25%/40%/70%
- [ ] Discord notification (if enabled) shows SCALP classification

---

### Test Case 21.2: Force INTRADAY Classification

**Steps:**
1. Open a position with comment containing `!force:intraday`
   - Example: `"Long USDJPY swing !force:intraday"`
   - Or: `"Buy BTCUSD trend !force:intraday"`
2. Enable intelligent exits via ChatGPT:
   ```
   Enable intelligent exits for ticket <TICKET>
   ```
3. **Expected Results:**
   - Classification: `INTRADAY` (confidence: 1.0 or very high)
   - Reasoning: Contains "Manual override: !force:intraday"
   - Exit Parameters: 30% breakeven / 60% partial / 50% close
   - Log message: `📊 Trade Classification: INTRADAY (confidence: 1.00) - Manual override: !force:intraday`

**Verification Checklist:**
- [ ] Classification result shows `INTRADAY`
- [ ] Confidence is 1.0 (or ≥0.95)
- [ ] Reasoning mentions manual override
- [ ] Exit parameters are 30%/60%/50%
- [ ] Discord notification (if enabled) shows INTRADAY classification

---

### Test Case 21.3: Override Priority Test

**Steps:**
1. Open a position with conflicting signals:
   - Comment: `"scalp trade"` (keyword suggests SCALP)
   - Stop size: 2.5× ATR (suggests INTRADAY)
   - But add: `!force:scalp`
2. Enable intelligent exits
3. **Expected Results:**
   - Classification: `SCALP` (manual override takes priority)
   - Exit Parameters: 25%/40%/70% (SCALP parameters)

**Verification:**
- [ ] Manual override wins over keyword/ATR/session strategy
- [ ] Exit parameters match override classification

---

## Task 22: Test Edge Cases

### Test Case 22.1: Missing ATR Data

**Steps:**
1. Enable intelligent exits on a position where ATR H1 is unavailable
2. **Expected Results:**
   - Classification should still work (falls back to keyword or session strategy)
   - Reasoning mentions "ATR data unavailable"
   - Defaults to INTRADAY if no other factors available
   - No crashes or errors

**Verification:**
- [ ] System handles missing ATR gracefully
- [ ] Classification completes (may be INTRADAY with low confidence)
- [ ] Logs show appropriate fallback message

---

### Test Case 22.2: Missing Session Data

**Steps:**
1. Enable intelligent exits when session info is unavailable
2. **Expected Results:**
   - Classification uses keyword or stop/ATR ratio instead
   - Reasoning mentions "Session data unavailable"
   - No crashes

**Verification:**
- [ ] System handles missing session data gracefully
- [ ] Classification uses available factors (keyword/ATR)
- [ ] Logs show appropriate fallback message

---

### Test Case 22.3: Missing Comment

**Steps:**
1. Open position with empty or missing comment
2. Enable intelligent exits
3. **Expected Results:**
   - Classification uses stop/ATR ratio or session strategy
   - Reasoning explains which factor was used
   - Defaults to INTRADAY if ambiguous

**Verification:**
- [ ] System handles missing comment
- [ ] Classification uses stop size or session strategy
- [ ] No errors related to comment parsing

---

### Test Case 22.4: Invalid Stop Size

**Steps:**
1. Open position where stop_loss == entry_price (zero stop size)
2. Enable intelligent exits
3. **Expected Results:**
   - System detects invalid stop size
   - Classification defaults to INTRADAY
   - Reasoning: "Invalid stop size (stop == entry), cannot calculate ratio → Default to INTRADAY"
   - Confidence: Low (0.3 or less)

**Verification:**
- [ ] Invalid stop size detected
- [ ] Safe fallback to INTRADAY
- [ ] Logs show warning about invalid stop

---

### Test Case 22.5: Very Small Stop Size

**Steps:**
1. Open position with stop size < 0.1× ATR (very tight stop)
2. Enable intelligent exits
3. **Expected Results:**
   - Classification: `SCALP`
   - Reasoning: Mentions very small stop size
   - Exit Parameters: 25%/40%/70%

**Verification:**
- [ ] Very small stops classified as SCALP
- [ ] Appropriate exit parameters applied

---

## Task 23: Manual Scalp Trade Verification

### Test Scenario: Real Scalp Trade

**Prerequisites:**
- Open a position that is clearly a scalp trade:
  - Small stop loss (<1.0× ATR)
  - Comment contains "scalp" or related keywords
  - Or session strategy is "scalping" or "range_trading"

**Steps:**
1. Open position with scalp characteristics:
   ```
   Symbol: XAUUSD (or any active symbol)
   Entry: Current market price
   Stop: Tight stop (<1.0× ATR)
   Comment: "Scalp trade" or "Range scalp"
   ```
2. Enable intelligent exits:
   ```
   Enable intelligent exits for ticket <TICKET>
   ```
3. **Verify Results:**

   **A. Classification Output:**
   - ✅ Trade Type: `SCALP`
   - ✅ Confidence: ≥0.7 (ideally ≥0.8)
   - ✅ Reasoning: Explains why it's classified as SCALP

   **B. Exit Parameters Applied:**
   - ✅ Breakeven: 25% profit (0.25R)
   - ✅ Partial: 40% profit (0.40R), close 70%
   - ✅ Verify these are actually set in the exit manager

   **C. Log Verification:**
   ```
   📊 Trade Classification: SCALP (confidence: 0.85) - Keyword match: "scalp" in comment
   🎯 Using SCALP parameters: 25.0% / 40.0% / 70.0%
   ✅ Intelligent exits enabled: <breakeven>% / <partial>%
   ```

   **D. Discord Notification (if enabled):**
   - Contains "Trade Type: SCALP"
   - Shows confidence level
   - Shows reasoning
   - Shows exit strategy parameters

**Success Criteria:**
- [ ] Classification is SCALP
- [ ] Confidence ≥0.7
- [ ] Exit parameters are 25%/40%/70%
- [ ] Logs show correct classification
- [ ] Discord notification includes classification info (if enabled)
- [ ] Metrics recorded (check via metrics API or logs)

---

## Task 24: Manual Intraday Trade Verification

### Test Scenario: Real Intraday Trade

**Prerequisites:**
- Open a position that is clearly an intraday trade:
  - Larger stop loss (>1.0× ATR)
  - Comment contains "swing", "trend", or intraday keywords
  - Or session strategy is "trend_following" or "breakout_and_trend"

**Steps:**
1. Open position with intraday characteristics:
   ```
   Symbol: EURUSD (or any active symbol)
   Entry: Current market price
   Stop: Wider stop (>1.5× ATR)
   Comment: "Swing trade" or "Trend following"
   ```
2. Enable intelligent exits:
   ```
   Enable intelligent exits for ticket <TICKET>
   ```
3. **Verify Results:**

   **A. Classification Output:**
   - ✅ Trade Type: `INTRADAY`
   - ✅ Confidence: ≥0.7 (ideally ≥0.8)
   - ✅ Reasoning: Explains why it's classified as INTRADAY

   **B. Exit Parameters Applied:**
   - ✅ Breakeven: 30% profit (0.30R)
   - ✅ Partial: 60% profit (0.60R), close 50%
   - ✅ Verify these match your configured defaults

   **C. Log Verification:**
   ```
   📊 Trade Classification: INTRADAY (confidence: 0.80) - Stop size (1.5× ATR) indicates intraday
   🎯 Using INTRADAY parameters: 30.0% / 60.0% / 50.0%
   ✅ Intelligent exits enabled: <breakeven>% / <partial>%
   ```

   **D. Discord Notification (if enabled):**
   - Contains "Trade Type: INTRADAY"
   - Shows confidence level
   - Shows reasoning
   - Shows exit strategy parameters

**Success Criteria:**
- [ ] Classification is INTRADAY
- [ ] Confidence ≥0.7
- [ ] Exit parameters are 30%/60%/50% (or your configured defaults)
- [ ] Logs show correct classification
- [ ] Discord notification includes classification info (if enabled)
- [ ] Metrics recorded

---

## Task 25: Verify Discord Notifications in Production

### Test Case 25.1: Discord Notification Format

**Steps:**
1. Enable intelligent exits on any position (SCALP or INTRADAY)
2. Check Discord channel for notification
3. **Expected Discord Message Format:**

   ```
   ✅ **Intelligent Exits Enabled**
   
   🎫 **Ticket**: 123456
   💱 **Symbol**: XAUUSD
   📊 **Entry**: 2400.50
   🛡️ **SL**: 2395.00 | 🎯 **TP**: 2410.00
   
   📊 **Trade Type**: SCALP
   🎯 **Confidence**: 85%
   💡 **Reasoning**: Keyword match: "scalp" in comment
   
   ⚙️ **Exit Strategy**:
      • Breakeven: 25% profit (0.25R)
      • Partial: 40% profit (0.40R), close 70%
   
   🤖 Position is now on autopilot!
   ```

**Verification Checklist:**
- [ ] Discord notification received
- [ ] Contains all required fields (ticket, symbol, entry, SL, TP)
- [ ] Contains classification section (Trade Type, Confidence, Reasoning)
- [ ] Contains exit strategy section with correct parameters
- [ ] Formatting is clean and readable
- [ ] No duplicate notifications

---

### Test Case 25.2: Discord Notification for SCALP Trade

**Steps:**
1. Enable intelligent exits on a SCALP-classified trade
2. Verify Discord notification shows:
   - Trade Type: `SCALP`
   - Exit parameters: 25%/40%/70%

**Verification:**
- [ ] Classification correctly displayed as SCALP
- [ ] Exit parameters match SCALP profile (25%/40%/70%)

---

### Test Case 25.3: Discord Notification for INTRADAY Trade

**Steps:**
1. Enable intelligent exits on an INTRADAY-classified trade
2. Verify Discord notification shows:
   - Trade Type: `INTRADAY`
   - Exit parameters: 30%/60%/50% (or configured defaults)

**Verification:**
- [ ] Classification correctly displayed as INTRADAY
- [ ] Exit parameters match INTRADAY profile (30%/60%/50%)

---

### Test Case 25.4: Discord Notification When Feature Disabled

**Steps:**
1. Temporarily set `ENABLE_TRADE_TYPE_CLASSIFICATION=0` in `.env`
2. Restart system
3. Enable intelligent exits on a position
4. **Expected Results:**
   - Discord notification does NOT include classification section
   - Shows exit strategy section with standard parameters
   - No errors or crashes

**Verification:**
- [ ] Notification received but without classification info
- [ ] Standard exit parameters shown
- [ ] No errors in logs

---

## Testing Workflow

### Recommended Test Order:

1. **Task 21** (Manual Override) - Quick verification of override functionality
2. **Task 22** (Edge Cases) - Verify robustness and error handling
3. **Task 23** (Scalp Trade) - Real-world SCALP classification test
4. **Task 24** (Intraday Trade) - Real-world INTRADAY classification test
5. **Task 25** (Discord) - Verify notification format and content

### Testing Checklist Summary:

After completing all tasks, verify:
- [ ] Manual overrides work correctly
- [ ] Edge cases handled gracefully
- [ ] SCALP trades classified correctly with proper exit parameters
- [ ] INTRADAY trades classified correctly with proper exit parameters
- [ ] Discord notifications include all required classification information
- [ ] Metrics are being collected (check logs or metrics endpoint)
- [ ] No crashes or errors during testing
- [ ] System performance acceptable (classification latency < 500ms)

---

## Troubleshooting

### Issue: Classification not showing in Discord

**Check:**
- Feature flag is enabled (`ENABLE_TRADE_TYPE_CLASSIFICATION=1`)
- System restarted after enabling flag
- Discord webhook URL is configured
- Check logs for Discord notification errors

### Issue: Wrong classification result

**Check:**
- Review reasoning in logs to understand why
- Verify stop size calculation (check ATR data)
- Check comment for keywords
- Check session strategy

### Issue: Wrong exit parameters applied

**Check:**
- Classification result matches expected type (SCALP/INTRADAY)
- Exit manager actually applied the parameters
- Check logs for parameter selection logic

### Issue: Metrics not being recorded

**Check:**
- `CLASSIFICATION_METRICS_ENABLED=1` in config
- Check logs for metrics recording errors
- Verify metrics instance is initialized

---

## Post-Testing Verification

After completing all manual tests:

1. **Review Logs:**
   - Check for any errors or warnings
   - Verify all classifications were recorded
   - Check metrics collection is working

2. **Review Metrics:**
   - Check aggregate metrics (if available)
   - Verify classification breakdown
   - Check latency statistics

3. **Review Discord:**
   - Verify all notifications were sent
   - Check formatting consistency
   - Verify classification info accuracy

4. **Document Results:**
   - Note any issues found
   - Record classification accuracy
   - Document any edge cases discovered

---

## Success Criteria

✅ **All tasks pass if:**
- Manual overrides work as expected
- Edge cases handled without crashes
- SCALP trades get SCALP parameters (25%/40%/70%)
- INTRADAY trades get INTRADAY parameters (30%/60%/50%)
- Discord notifications include classification info
- Metrics are being collected
- No critical errors in logs
- System performance acceptable (< 500ms latency)

---

## Notes

- All manual testing should be done in a test/demo account if possible
- Monitor system resources during testing (CPU, memory)
- Keep logs accessible for review
- Take screenshots of Discord notifications for documentation
- Record test results in this document or a separate test log

