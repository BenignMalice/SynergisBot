# ADAPTIVE AUTO-EXECUTION PLAN TESTING GUIDE

## PURPOSE
Comprehensive testing guide for verifying ChatGPT integration with adaptive auto-execution plan features (Phase 1-4).

---

## PRE-TESTING CHECKLIST

### 1. Verify Knowledge Documents Are Uploaded
- ✅ `22.ADAPTIVE_AUTO_EXECUTION_FEATURES.md` - Combined document (Phase 1-4: Tolerance Zones, Multi-Level Entry, Conditional Cancellation, Plan Re-Evaluation)
- ✅ `7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md` - Main knowledge document (updated with all phases)

### 2. Verify Tools Are Available
- ✅ `moneybot.create_auto_trade_plan` - Updated with Phase 1-4 information
- ✅ `moneybot.get_auto_plan_status` - Updated with cancellation and re-evaluation fields
- ✅ `moneybot.re_evaluate_plan` - New tool for Phase 4
- ✅ `moneybot.get_plan_zone_status` - Optional tool for Phase 1

### 3. Verify System Is Running
- ✅ Main API server running (port 8000)
- ✅ Auto-execution system monitoring active
- ✅ Database accessible

---

## PHASE 1: TOLERANCE ZONE EXECUTION TESTING

### Test 1.1: ChatGPT Awareness of Tolerance Zones
**Prompt:**
```
"Explain how tolerance zones work in auto-execution plans. What happens when price enters a tolerance zone?"
```

**Expected Response:**
- Mentions tolerance creates an execution zone (not exact price)
- Explains zone entry detection
- Mentions zone entry tracking
- References tolerance recommendations per symbol

**Verification:**
- ChatGPT should reference `22.ADAPTIVE_AUTO_EXECUTION_FEATURES.md` (Part 1: Tolerance Zone Execution) or mention tolerance zone concepts
- Should explain BUY executes at/below (entry + tolerance), SELL at/above (entry - tolerance)

**Example Successful Response:**
ChatGPT correctly explains:
- Tolerance zone is an execution band (not exact price)
- Zone entry detection and tracking (`zone_entry_tracked = true`)
- Single execution per entry event, re-entry allowed
- Symbol-specific tolerance recommendations (BTCUSDc: 100-300 pts, XAUUSDc: 2-7 pts, FX: 2-5 pips)
- BUY triggers at/below upper bound, SELL at/above lower bound

---

### Test 1.2: Create Plan with Tolerance Zone
**Prompt:**
```
"Create an auto-execution plan for BTCUSDc SELL at 50000 with SL 50500, TP 49000, volume 0.01. Use a tolerance of 200 points."
```

**Expected Behavior:**
- Plan created successfully
- Tolerance value (200) included in conditions
- ChatGPT mentions zone execution behavior
- ChatGPT may identify and add required strategy-specific conditions (e.g., `liquidity_sweep: true` for liquidity_sweep_reversal strategy)

**Verification:**
- Check plan in database: `SELECT plan_id, conditions, zone_entry_tracked FROM trade_plans WHERE plan_id = 'chatgpt_...'`
- Verify `conditions` JSON contains `"tolerance": 200`
- Verify `zone_entry_tracked` field exists in database (will be 0/false for new plans)
- If plan creation initially fails, ChatGPT should identify missing conditions and fix them
- **Quick verification script:** Run `python verify_plan_tolerance.py` (script provided in project root)

**Example Successful Response:**
ChatGPT correctly:
- Identifies missing strategy-specific conditions (e.g., `liquidity_sweep: true`)
- Adds required conditions to the plan
- Includes tolerance (200 points) in conditions
- Creates plan successfully with tolerance zone: 49,800-50,200
- Explains zone execution behavior (executes once per entry event, may retry on re-entry)

---

### Test 1.3: Check Zone Status
**Prompt:**
```
"Check the zone status for plan [plan_id]"
```

**Expected Response:**
- ChatGPT uses `moneybot.get_plan_zone_status` or `moneybot.get_auto_plan_status`
- Returns zone status information (in_zone, zone_entry_time, price_distance_from_entry)
- Explains zone bounds, current price position, and zone state

**Verification:**
- API endpoint: `GET http://localhost:8000/auto-execution/plan/{plan_id}/zone-status`
- Should return zone status fields

**Example Successful Response:**
ChatGPT correctly:
- Uses `moneybot.get_auto_plan_status` tool with plan_id
- Displays zone bounds (e.g., 49,800 - 50,200 with ±200 tolerance)
- Shows current price and zone state (inside/outside zone)
- Calculates and displays distance to entry zone
- Indicates if zone entry has been detected yet
- Explains execution state and when plan will trigger

---

## PHASE 2: MULTI-LEVEL ENTRY TESTING

### Test 2.1: ChatGPT Awareness of Multi-Level Entry
**Prompt:**
```
"Can I create an auto-execution plan with multiple entry levels? How does it work?"
```

**Expected Response:**
- Mentions `entry_levels` parameter (NOT multiple separate plans)
- Explains that `entry_levels` is an array within a SINGLE plan
- Explains execution on first level that enters zone
- Mentions level priority (array order)
- References `22.ADAPTIVE_AUTO_EXECUTION_FEATURES.md` (Part 2: Multi-Level Entry Strategy)
- Clarifies: Single plan with multiple entry levels, NOT multiple separate plans

**Verification:**
- ChatGPT should explain multi-level entry concept
- Should mention when to use multiple levels (order blocks, liquidity sweeps, etc.)
- **CRITICAL:** Must understand `entry_levels` is a parameter in `moneybot.create_auto_trade_plan`, NOT separate plans
- **CRITICAL:** Must understand plan executes ONCE when FIRST level enters zone (not multiple times for each level)
- **CRITICAL:** Must understand full volume executes at triggered level (weight is optional, not used for volume allocation in Phase 2)

**Common Misunderstandings:**
- ❌ **WRONG:** Creating multiple separate plans (using `moneybot.create_multiple_auto_plans`)
- ✅ **CORRECT:** Single plan with `entry_levels` array parameter in `moneybot.create_auto_trade_plan`
- ❌ **WRONG:** "Each level executes independently with proportional volume based on weight"
- ✅ **CORRECT:** "Plan executes ONCE when first level enters zone, with full volume at that level"
- ❌ **WRONG:** "Weight determines volume allocation" (Phase 2 doesn't support partial fills)
- ✅ **CORRECT:** "Weight is optional and not used for volume allocation in Phase 2 - full volume executes at triggered level"
- ❌ **WRONG:** "Each level acts as a micro-plan under the parent plan"
- ✅ **CORRECT:** "Single plan with multiple entry levels - executes once at first level"
- ❌ **WRONG:** "Partial positions may be entered automatically" or "laddered fills (partial entries)"
- ✅ **CORRECT:** "FULL position executes ONCE when first level enters zone"
- ❌ **WRONG:** "Each entry uses its defined weight to size the position"
- ✅ **CORRECT:** "Full plan volume executes at triggered level, weight is not used"
- ❌ **WRONG:** "If price hits level 1 and bounces, you're 50% filled. If it later dips into level 2, it fills another 30%"
- ✅ **CORRECT:** "When level 1 enters zone, FULL volume executes at level 1. Plan stops. Levels 2 and 3 are never executed."
- ❌ **WRONG:** "Once all defined levels are executed, the plan is marked complete"
- ✅ **CORRECT:** "Plan executes once at first level and stops - other levels are never executed"
- ❌ **WRONG:** "The system will scale in automatically as price reaches each zone"
- ✅ **CORRECT:** "Executes once at first level - does NOT scale in"

**Example Correct Response:**
ChatGPT should explain:
- `entry_levels` is an optional parameter in `moneybot.create_auto_trade_plan`
- **Correct Structure:** `[{"price": 50000, "weight": 1.0, "sl_offset": 300, "tp_offset": 600}, {"price": 50100, ...}]`
- **NOT:** `{"entry": 50000, "stop_loss": 51000, "take_profit": 49000, "tolerance": 150, "volume": 0.01}` ❌
- Single plan executes ONCE when FIRST level enters tolerance zone (not multiple times for each level)
- Plan executes with FULL volume at the triggered level (weight is optional, not used for volume allocation in Phase 2)
- Each level uses `price` (not `entry`), `sl_offset`/`tp_offset` (not absolute SL/TP)
- Tolerance is at plan level (in `conditions`), NOT per level
- Volume is at plan level, NOT per level
- System tracks which level triggered execution

**Common Misunderstanding:**
- ❌ **WRONG:** "Each level executes independently with proportional volume based on weight"
- ✅ **CORRECT:** "Plan executes ONCE when first level enters zone, with full volume at that level"

---

### Test 2.2: Create Multi-Level Plan
**Prompt:**
```
"Create an auto-execution plan for BTCUSDc BUY with 3 entry levels: 50000, 50100, 50200. Use SL offset 300 points and TP offset 600 points for all levels. Volume 0.01."
```

**Expected Behavior:**
- Plan created with `entry_levels` array
- Each level has `price`, `weight` (optional), `sl_offset`, `tp_offset`
- ChatGPT confirms multi-level plan created
- **CRITICAL:** Structure must be `[{"price": 50000, "sl_offset": 300, "tp_offset": 600}, ...]` NOT `[{"entry": 50000, "stop_loss": 51000, ...}]`

**Verification:**
- Check database: `SELECT entry_levels FROM trade_plans WHERE plan_id = 'chatgpt_...'`
- Verify `entry_levels` JSON contains array with 3 levels
- Verify each level has `price` field (not `entry`)
- Verify each level has `sl_offset` and `tp_offset` (not absolute `stop_loss`/`take_profit`)
- Verify levels are sorted (ascending for BUY)

---

### Test 2.3: Verify Level Priority
**Prompt:**
```
"Which entry level will execute first in my multi-level plan [plan_id]?"
```

**Expected Response:**
- ChatGPT explains first level in array executes first
- Mentions level priority based on array order
- Explains execution uses SL/TP from triggered level

**Verification:**
- Check plan execution logic when price approaches levels
- Verify system uses triggered level's SL/TP offsets

---

## PHASE 3: CONDITIONAL CANCELLATION TESTING

### Test 3.1: ChatGPT Awareness of Cancellation
**Prompt:**
```
"When are auto-execution plans automatically cancelled? What conditions trigger cancellation?"
```

**Expected Response:**
- Mentions price distance cancellation (symbol-specific thresholds) - ✅ FULLY IMPLEMENTED
- Mentions time-based cancellation (>24h old + price distance) - ✅ FULLY IMPLEMENTED
- Mentions cancellation risk (0-1 scale)
- References `22.ADAPTIVE_AUTO_EXECUTION_FEATURES.md` (Part 3: Conditional Cancellation)
- ⚠️ **CRITICAL:** Should NOT mention the following as active cancellation conditions (they are NOT implemented):
  - Session switch cancellation, "Session Switch Flare", session transition
  - News blackout cancellation, high-impact event cancellation
  - Volatility regime changes, volatility-structure alignment cancellation
  - Symbol constraint breach cancellation, max concurrent trades exceeded
  - CHOCH/BOS invalidation cancellation
  - Server restart cleanup, duplicate plan detection, data integrity failure cancellation
- ⚠️ **NOTE:** Structure cancellation and condition invalidation are enabled but placeholders (TODOs) - ChatGPT should mention they're not fully implemented

**Verification:**
- ChatGPT should explain cancellation conditions
- Should mention cancellation_risk and cancellation_reasons fields
- Should NOT describe unimplemented cancellation conditions as active

**Example of WRONG Response (ChatGPT describing unimplemented features):**
- ❌ "Session about to switch (London → NYO) → may trigger auto-cancel"
- ❌ "Volatility expansion detected — execution conditions may be re-evaluated"
- ❌ "News blackout: None detected for Gold"
- ❌ "Session alignment: Session about to switch → may trigger auto-cancel"

**Example of CORRECT Response:**
- ✅ "Cancellation risk based on: Price distance from entry (currently X.XX% away, threshold: Y.YY%), Time since creation (X.X hours, max: 24h), Expiry time remaining (X.X hours)"
- ✅ "Price distance cancellation: Currently X.XX% away from entry (threshold: Y.YY%) - risk level: [low/medium/high]"
- ✅ "Time-based cancellation: Plan is X.X hours old, price is Y.YY% away from entry - risk level: [low/medium/high]"

---

### Test 3.2: Check Cancellation Risk
**Prompt:**
```
"Check the cancellation risk for plan [plan_id]. Is it likely to be cancelled?"
```

**Expected Response:**
- ChatGPT uses `moneybot.get_auto_plan_status`
- Returns cancellation_risk, cancellation_reasons, cancellation_priority
- Explains risk level (high/medium/low)

**Verification:**
- API endpoint: `GET http://localhost:8000/auto-execution/plan/{plan_id}/cancellation-status`
- Should return cancellation risk information
- Risk >0.8 indicates high cancellation risk
- ChatGPT should ONLY mention price distance and time-based cancellation
- ChatGPT should NOT mention session switches, news blackout, volatility regime changes, etc.

**Example Successful Response:**
ChatGPT correctly:
- Uses `moneybot.get_auto_plan_status` tool
- Only mentions price distance cancellation (threshold: 0.5% for BTCUSDc, 0.3% for XAUUSDc, 0.2% for Forex)
- Only mentions time-based cancellation (>24h old + >0.3% away)
- Explains cancellation risk based on: age, expiry time remaining, price distance from entry
- Does NOT mention: session switches, news blackout, volatility regime changes, structure breaks, symbol constraints, CHOCH/BOS invalidation
- Provides numerical risk assessment (0.0-1.0 scale) with correct interpretation
- Example: "Cancellation risk: LOW (<10%). Plan will only auto-cancel if: (1) It reaches expiry (~24h after creation), or (2) Price moves >0.5% away from entry zone before next check."

---

### Test 3.3: Create Plan Far from Current Price
**Prompt:**
```
"Create an auto-execution plan for BTCUSDc BUY at 60000 (current price is around 50000). SL 60500, TP 59000, volume 0.01."
```

**Expected Behavior:**
- Plan created successfully
- ChatGPT may warn about price distance
- Plan should show high cancellation risk (>0.8)

**Verification:**
- Check cancellation status after plan creation
- Verify cancellation_risk is high (>0.8) due to price distance
- Plan may be auto-cancelled if price moves >0.5% away (BTCUSDc threshold)

---

## PHASE 4: RE-EVALUATION TESTING

### Test 4.1: ChatGPT Awareness of Re-evaluation
**Prompt:**
```
"How does plan re-evaluation work? When are plans automatically re-evaluated?"
```

**Expected Response:**
- Mentions price movement trigger (0.2% default) - ✅ FULLY IMPLEMENTED
- Mentions time-based trigger (4 hours default) - ✅ FULLY IMPLEMENTED
- Mentions cooldown (60 minutes) and daily limit (6 per day)
- References `22.ADAPTIVE_AUTO_EXECUTION_FEATURES.md` (Part 4: Plan Re-Evaluation)
- ⚠️ **CRITICAL:** Should NOT mention the following as active re-evaluation triggers (they are NOT implemented):
  - Session switch trigger, session transition re-evaluation
  - Price distance check every 5 minutes (this is for CANCELLATION, not re-evaluation)
  - Volatility regime change trigger (DISABLED in config)
  - Structure change trigger (placeholder only)
  - News check trigger, news blackout trigger
  - Hourly re-evaluation (WRONG - it's every 4 hours)
  - "Re-evaluation runs every 5-60 minutes depending on trigger" (WRONG - only 2 triggers implemented)

**Verification:**
- ChatGPT should explain re-evaluation triggers
- Should mention re_evaluation_available, last_re_evaluation fields
- Should NOT describe unimplemented re-evaluation triggers as active

**Example of WRONG Response (ChatGPT describing unimplemented features):**
- ❌ "Re-evaluation is triggered by: Price Distance Check (every 5 min), Session Switch, Volatility Regime Change, Structural Invalidation, Time-Based Re-Eval (hourly)"
- ❌ "Re-evaluation frequency: Every 5-60 minutes depending on trigger"
- ❌ "Session switch triggers re-evaluation when market transitions between sessions"
- ❌ "Volatility regime change triggers re-evaluation when volatility expands or contracts"

**Example of CORRECT Response:**
- ✅ "Re-evaluation triggers: Price movement (>0.2% from entry) or time-based (every 4 hours)"
- ✅ "Price movement trigger: Price moves >0.2% from entry → triggers re-evaluation"
- ✅ "Time-based trigger: Plan age >= 4 hours → triggers re-evaluation"
- ✅ "Re-evaluation cooldown: 60 minutes between re-evaluations"
- ✅ "Daily limit: 6 re-evaluations per plan per day"
- ✅ "Re-evaluation check interval: Every 30 minutes (checks if triggers have fired)"

---

### Test 4.2: Check Re-evaluation Status
**Prompt:**
```
"Check the re-evaluation status for plan [plan_id]. Can it be re-evaluated?"
```

**Expected Response:**
- ChatGPT uses `moneybot.get_auto_plan_status`
- Returns last_re_evaluation, re_evaluation_count_today, re_evaluation_cooldown_remaining, re_evaluation_available
- Explains if re-evaluation is available

**Verification:**
- API endpoint: `GET http://localhost:8000/auto-execution/plan/{plan_id}/re-evaluation-status`
- Should return re-evaluation status information
- re_evaluation_available should be true/false based on cooldown and daily limit

---

### Test 4.3: Manual Re-evaluation
**Prompt:**
```
"Re-evaluate plan [plan_id]. Force the re-evaluation even if it's in cooldown."
```

**Expected Behavior:**
- ChatGPT uses `moneybot.re_evaluate_plan` tool
- Passes force=true parameter
- Returns action, recommendation, available status

**Verification:**
- API endpoint: `POST http://localhost:8000/auto-execution/plan/{plan_id}/re-evaluate?force=true`
- Should return re-evaluation result
- Should update last_re_evaluation timestamp

---

## INTEGRATED TESTING SCENARIOS

### Scenario 1: Complete Adaptive Plan Creation
**Prompt:**
```
"Create an adaptive auto-execution plan for XAUUSDc SELL at 2650 with:
- Multiple entry levels: 2650, 2655, 2660
- Tolerance zone: 5 points
- SL offset: 10 points per level
- TP offset: 20 points per level
- Volume: 0.01
- Strategy: order_block_rejection"
```

**Expected Behavior:**
- Plan created with all adaptive features
- ChatGPT mentions tolerance zone execution
- ChatGPT mentions multi-level entry
- ChatGPT mentions cancellation and re-evaluation awareness

**Verification:**
- Check database for all fields populated
- Verify entry_levels array structure
- Verify tolerance in conditions
- Check plan status includes all Phase 1-4 fields

---

### Scenario 2: Plan Status Check (All Phases)
**Prompt:**
```
"Get the complete status for plan [plan_id]. Include zone status, cancellation risk, and re-evaluation status."
```

**Expected Response:**
- ChatGPT uses `moneybot.get_auto_plan_status`
- Returns all Phase 1-4 fields:
  - Zone status (in_tolerance_zone, zone_entry_tracked, zone_entry_time)
  - Cancellation status (cancellation_risk, cancellation_reasons, cancellation_priority)
  - Re-evaluation status (last_re_evaluation, re_evaluation_count_today, re_evaluation_available)

**Verification:**
- API response includes all fields
- ChatGPT explains each field's meaning

---

### Scenario 3: Plan Update with Adaptive Features
**Prompt:**
```
"Update plan [plan_id] to add a second entry level at 2655 with SL offset 12 points and TP offset 25 points."
```

**Expected Behavior:**
- ChatGPT uses `moneybot.update_auto_plan` or explains plan update
- Mentions entry_levels parameter
- Confirms multi-level entry support

**Verification:**
- Check database for updated entry_levels
- Verify new level added to array

---

## VERIFICATION CHECKLIST

### Knowledge Document Access
- [ ] ChatGPT references tolerance zone execution concepts
- [ ] ChatGPT references multi-level entry strategy
- [ ] ChatGPT references conditional cancellation
- [ ] ChatGPT references plan re-evaluation

### Tool Usage
- [ ] ChatGPT uses `moneybot.create_auto_trade_plan` with tolerance parameter
- [ ] ChatGPT uses `moneybot.create_auto_trade_plan` with entry_levels parameter
- [ ] ChatGPT uses `moneybot.get_auto_plan_status` and mentions cancellation/re-evaluation fields
- [ ] ChatGPT uses `moneybot.re_evaluate_plan` for manual re-evaluation
- [ ] ChatGPT uses `moneybot.get_plan_zone_status` (optional) for zone status

### Plan Creation
- [ ] Plans created with tolerance in conditions
- [ ] Plans created with entry_levels array
- [ ] Plans include all Phase 1-4 fields in database

### Plan Status
- [ ] Status includes zone tracking fields
- [ ] Status includes cancellation risk and reasons
- [ ] Status includes re-evaluation tracking fields

### System Behavior
- [ ] Zone entry detection working
- [ ] Multi-level execution working
- [ ] Cancellation conditions checking
- [ ] Re-evaluation triggers working

---

## TROUBLESHOOTING

### ChatGPT Doesn't Know About Features
**Issue:** ChatGPT doesn't mention tolerance zones, multi-level entry, etc.

**Solutions:**
1. Verify knowledge documents are uploaded to ChatGPT Custom GPT
2. Check `openai.yaml` has updated tool descriptions
3. Ask ChatGPT to "search your knowledge base for tolerance zone execution"
4. Restart ChatGPT conversation to reload knowledge

### Tools Not Available
**Issue:** ChatGPT says tool doesn't exist or can't use it.

**Solutions:**
1. Verify `openai.yaml` is updated and uploaded
2. Check Custom GPT Actions configuration
3. Verify API server is running and accessible
4. Check ngrok tunnel is active (if using)

### Plans Not Created Correctly
**Issue:** Plans created but missing adaptive features.

**Solutions:**
1. Check ChatGPT includes parameters in tool call
2. Verify API endpoint receives correct parameters
3. Check database for field values
4. Review plan creation logs

### Status Fields Missing
**Issue:** Plan status doesn't include Phase 1-4 fields.

**Solutions:**
1. Verify database has all columns (run migrations)
2. Check API endpoint returns all fields
3. Verify `chatgpt_auto_execution_integration.py` includes fields in response
4. Check plan was created after Phase 1-4 implementation

---

## TESTING COMMANDS REFERENCE

### Direct API Testing (Bypass ChatGPT)
```bash
# Create plan with tolerance (Phase 1)
curl -X POST http://localhost:8000/auto-execution/create-plan \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDc","direction":"SELL","entry_price":50000,"stop_loss":50500,"take_profit":49000,"volume":0.01,"conditions":{"price_near":50000,"tolerance":200}}'

# Create multi-level plan (Phase 2)
curl -X POST http://localhost:8000/auto-execution/create-plan \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDc","direction":"BUY","entry_price":50000,"stop_loss":49700,"take_profit":50600,"volume":0.01,"entry_levels":[{"price":50000,"weight":1.0,"sl_offset":300,"tp_offset":600},{"price":50100,"weight":1.0,"sl_offset":300,"tp_offset":600}]}'

# Create plan with all adaptive features (Phase 1-4)
curl -X POST http://localhost:8000/auto-execution/create-plan \
  -H "Content-Type: application/json" \
  -d '{"symbol":"XAUUSDc","direction":"SELL","entry_price":2650,"stop_loss":2660,"take_profit":2630,"volume":0.01,"conditions":{"price_near":2650,"tolerance":5},"entry_levels":[{"price":2650,"weight":1.0,"sl_offset":10,"tp_offset":20},{"price":2655,"weight":1.0,"sl_offset":10,"tp_offset":20}],"expires_hours":24}'

# Get plan status (includes all Phase 1-4 fields)
curl "http://localhost:8000/auto-execution/status?plan_id=chatgpt_abc123"

# Get plan status by ticket number
curl "http://localhost:8000/auto-execution/status?ticket=123456789"

# Get all pending plans
curl "http://localhost:8000/auto-execution/status?include_all=true"

# Get zone status (Phase 1)
curl "http://localhost:8000/auto-execution/plan/chatgpt_abc123/zone-status"

# Get cancellation status (Phase 3)
curl "http://localhost:8000/auto-execution/plan/chatgpt_abc123/cancellation-status"

# Get re-evaluation status (Phase 4)
curl "http://localhost:8000/auto-execution/plan/chatgpt_abc123/re-evaluation-status"

# Manual re-evaluation (Phase 4)
curl -X POST "http://localhost:8000/auto-execution/plan/chatgpt_abc123/re-evaluate?force=false"

# Force re-evaluation (bypass cooldown and daily limit)
curl -X POST "http://localhost:8000/auto-execution/plan/chatgpt_abc123/re-evaluate?force=true"

# Update plan
curl -X POST http://localhost:8000/auto-execution/update-plan/chatgpt_abc123 \
  -H "Content-Type: application/json" \
  -d '{"entry_price":50100,"stop_loss":49800,"take_profit":50700}'

# Cancel plan
curl -X POST http://localhost:8000/auto-execution/cancel-plan/chatgpt_abc123

# Get system status
curl http://localhost:8000/auto-execution/system-status

# Get metrics
curl http://localhost:8000/auto-execution/metrics
```

**Note:** 
- API endpoints use `/auto-execution` prefix (router prefix)
- Parameter name is `entry_price` (not `entry`) for create-plan endpoint
- All endpoints require API key verification (currently placeholder, but header may be needed in production)
- For multi-level plans, use `entry_levels` array with `price`, `weight`, `sl_offset`, `tp_offset` fields
- `entry_price` is still required even when using `entry_levels` (used as primary entry for validation)

---

## SUCCESS CRITERIA

### Phase 1 (Tolerance Zones)
- ✅ ChatGPT understands tolerance creates execution zone
- ✅ ChatGPT recommends appropriate tolerance values per symbol
- ✅ Plans execute when price enters tolerance zone
- ✅ Zone entry tracking works correctly

### Phase 2 (Multi-Level Entry)
- ✅ ChatGPT understands multi-level entry concept
- ✅ ChatGPT can create plans with entry_levels parameter
- ✅ System executes on first level that enters zone
- ✅ SL/TP calculated from triggered level

### Phase 3 (Conditional Cancellation)
- ✅ ChatGPT understands cancellation conditions
- ✅ ChatGPT can check cancellation risk
- ✅ System auto-cancels plans when conditions met
- ✅ Cancellation reasons tracked correctly

### Phase 4 (Re-evaluation)
- ✅ ChatGPT understands re-evaluation triggers
- ✅ ChatGPT can check re-evaluation status
- ✅ ChatGPT can manually trigger re-evaluation
- ✅ System auto-re-evaluates plans when triggers fire

---

## NEXT STEPS AFTER TESTING

1. **Document Issues:** Note any ChatGPT misunderstandings or tool usage issues
2. **Update Knowledge:** If ChatGPT doesn't understand concepts, update knowledge documents
3. **Refine Prompts:** Adjust tool descriptions in `openai.yaml` if needed
4. **Monitor Usage:** Track how ChatGPT uses adaptive features in production

---

**Last Updated:** 2025-12-18  
**Status:** Ready for Testing

