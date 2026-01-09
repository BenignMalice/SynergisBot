# DATABASE VERIFICATION GUIDE
**Purpose:** Verify what was actually saved to the database for the bracket trade plan (bracket_64ae94df)

⚠️ **NOTE:** This document is a historical reference for bracket trade verification. Bracket trades are deprecated - use `moneybot.create_multiple_auto_plans` to create two independent plans instead.

---

## QUICK VERIFICATION STEPS

### Option 1: Check via Web Interface
1. Navigate to: `http://localhost:8010/auto-execution/view`
2. Look for plans with:
   - Symbol: `BTCUSDc`
   - Bracket ID: `bracket_64ae94df`
   - Entry: `91,600` (BUY) and `89,800` (SELL)
3. Click on each plan to view full details including conditions

### Option 2: Check via Database Query

**If using SQLite:**
```sql
-- Find the bracket trade plans
SELECT 
    id,
    symbol,
    direction,
    entry_price,
    stop_loss,
    take_profit,
    volume,
    conditions,
    strategy_type,
    bracket_trade_id,
    created_at,
    expires_at
FROM auto_execution_plans
WHERE bracket_trade_id = 'bracket_64ae94df'
ORDER BY direction;
```

**If using PostgreSQL/MySQL:**
```sql
-- Find the bracket trade plans
SELECT 
    id,
    symbol,
    direction,
    entry_price,
    stop_loss,
    take_profit,
    volume,
    conditions::text as conditions_json,
    strategy_type,
    bracket_trade_id,
    created_at,
    expires_at
FROM auto_execution_plans
WHERE bracket_trade_id = 'bracket_64ae94df'
ORDER BY direction;
```

---

## WHAT TO VERIFY

### 1. Basic Plan Parameters

**BUY Plan Should Have:**
- `symbol`: `BTCUSDc`
- `direction`: `BUY`
- `entry_price`: `91600`
- `stop_loss`: `90950`
- `take_profit`: `93200`
- `volume`: `0.01`
- `strategy_type`: `breakout_ib_volatility_trap`
- `bracket_trade_id`: `bracket_64ae94df`

**SELL Plan Should Have:**
- `symbol`: `BTCUSDc`
- `direction`: `SELL`
- `entry_price`: `89800`
- `stop_loss`: `90450`
- `take_profit`: `88200`
- `volume`: `0.01`
- `strategy_type`: `breakout_ib_volatility_trap`
- `bracket_trade_id`: `bracket_64ae94df`

---

### 2. Conditions Object (CRITICAL CHECK)

**Expected Conditions Structure:**

**BUY Plan Conditions:**
```json
{
  "bb_expansion": true,
  "price_above": 91600,
  "price_near": 91600,
  "tolerance": 150
}
```

**SELL Plan Conditions:**
```json
{
  "bb_expansion": true,
  "price_below": 89800,
  "price_near": 89800,
  "tolerance": 150
}
```

**⚠️ CRITICAL VERIFICATION POINTS:**

1. **Does BUY plan have `price_above: 91600`?**
   - ✅ YES → Correct
   - ❌ NO → Missing required field (per knowledge docs line 887-890)

2. **Does SELL plan have `price_below: 89800`?**
   - ✅ YES → Correct
   - ❌ NO → Missing required field (per knowledge docs line 887-890)

3. **Does both plans have `price_near` matching entry?**
   - ✅ YES → Correct
   - ❌ NO → Missing proximity check

4. **Does both plans have `tolerance: 150`?**
   - ✅ YES → Correct
   - ❌ NO → Missing tolerance

5. **Does both plans have `bb_expansion: true`?**
   - ✅ YES → Correct
   - ❌ NO → Missing volatility expansion condition

---

### 3. Database Schema Check

**If you have access to the database schema, verify:**

**Table:** `auto_execution_plans`

**Key Columns:**
- `id` (primary key)
- `symbol` (string)
- `direction` (enum: BUY/SELL)
- `entry_price` (decimal)
- `stop_loss` (decimal)
- `take_profit` (decimal)
- `volume` (decimal)
- `conditions` (JSON/JSONB)
- `strategy_type` (string)
- `bracket_trade_id` (string, nullable)
- `created_at` (timestamp)
- `expires_at` (timestamp)
- `status` (enum: pending/executed/cancelled)

---

## EXPECTED vs ACTUAL COMPARISON

### What ChatGPT Reported:
```
Parameter          BUY Plan    SELL Plan
Symbol             BTCUSDc     BTCUSDc
Direction          BUY         SELL
Entry Price        91,600      89,800
Stop Loss          90,950      90,450
Take Profit        93,200      88,200
Strategy Type      breakout_ib_volatility_trap
Volume             0.01        0.01
Bracket ID         bracket_64ae94df
Conditions         bb_expansion=true, price_near, tolerance=150
```

### What Should Be in Database:

**BUY Plan Conditions:**
```json
{
  "bb_expansion": true,
  "price_above": 91600,
  "price_near": 91600,
  "tolerance": 150
}
```

**SELL Plan Conditions:**
```json
{
  "bb_expansion": true,
  "price_below": 89800,
  "price_near": 89800,
  "tolerance": 150
}
```

---

## VERIFICATION CHECKLIST

- [ ] Both plans exist in database
- [ ] Both plans have same `bracket_trade_id`
- [ ] BUY plan has `entry_price = 91600`
- [ ] SELL plan has `entry_price = 89800`
- [ ] Both plans have `strategy_type = 'breakout_ib_volatility_trap'`
- [ ] Both plans have `volume = 0.01`
- [ ] BUY plan conditions include `price_above: 91600`
- [ ] SELL plan conditions include `price_below: 89800`
- [ ] Both plans have `price_near` matching their entry
- [ ] Both plans have `tolerance: 150`
- [ ] Both plans have `bb_expansion: true`
- [ ] Plans are linked (one cancels other on execution)

---

## IF CONDITIONS ARE MISSING

**If `price_above`/`price_below` are missing:**

1. **Impact:** Plans may not execute correctly
2. **Reason:** Knowledge docs require these fields for breakout strategies (line 887-890)
3. **Fix:** Update the conditions in the database or recreate the plans

**SQL Update Example (if needed):**
```sql
-- Update BUY plan conditions
UPDATE auto_execution_plans
SET conditions = jsonb_set(
    conditions,
    '{price_above}',
    '91600'::jsonb
)
WHERE bracket_trade_id = 'bracket_64ae94df' 
  AND direction = 'BUY';

-- Update SELL plan conditions
UPDATE auto_execution_plans
SET conditions = jsonb_set(
    conditions,
    '{price_below}',
    '89800'::jsonb
)
WHERE bracket_trade_id = 'bracket_64ae94df' 
  AND direction = 'SELL';
```

---

## API ENDPOINT CHECK

**If you have API access, check:**

```bash
# Get all plans for bracket
curl http://localhost:8010/api/auto-execution/plans?bracket_trade_id=bracket_64ae94df

# Get specific plan
curl http://localhost:8010/api/auto-execution/plans/{plan_id}
```

---

## REPORTING RESULTS

After verification, report:

1. **What was actually saved?**
   - List all fields from database
   - Include full conditions JSON

2. **What's missing?**
   - Compare to expected structure
   - Note any discrepancies

3. **Are plans correctly linked?**
   - Do both share same `bracket_trade_id`?
   - Will one cancel the other on execution?

4. **Recommendations:**
   - Should plans be updated?
   - Are conditions sufficient for execution?

---

## NEXT STEPS

1. Run the database query
2. Compare actual vs expected
3. Report findings
4. If conditions are missing, decide whether to:
   - Update existing plans
   - Recreate plans with correct conditions
   - Update knowledge docs if requirements are unclear

