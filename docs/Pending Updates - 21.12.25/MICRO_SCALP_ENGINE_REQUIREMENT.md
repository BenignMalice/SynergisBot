# Micro-Scalp Engine Requirement for Auto-Execution Plans

**Date:** 2025-12-21  
**Question:** Does `infra.micro_scalp_engine` need to be running for the system to monitor and execute micro-scalp auto-execution plans?

---

## Answer: It Depends on Plan Type

There are **two different types** of micro-scalp plans, and they have different requirements:

### 1. **Explicit Micro-Scalp Plans** (`plan_type: "micro_scalp"`)

**Requires:** ✅ **YES - `micro_scalp_engine` MUST be running**

**How Created:**
- Created via `create_micro_scalp_plan()` API
- Has `plan_type: "micro_scalp"` explicitly set in `plan.conditions`

**How They Work:**
- Uses **4-layer validation system** via `MicroScalpEngine.check_micro_conditions()`
- Requires `micro_scalp_engine` to be initialized and available
- If engine is not available, plan will **fail condition checks** with warning:
  ```
  [WARNING] Micro-scalp plan {plan_id} requires micro-scalp engine (not available)
  ```

**Code Location:**
- Condition check: `auto_execution_system.py:3977-4004`
- Execution: `auto_execution_system.py:5447-5457`

**Example Plan:**
```json
{
  "plan_id": "micro_scalp_abc123",
  "conditions": {
    "plan_type": "micro_scalp",  // ← Explicit micro-scalp plan
    "timeframe": "M1",
    "price_near": 4326.0,
    "tolerance": 0.3
  }
}
```

---

### 2. **Detected M1 Micro-Scalp Plans** (`_detect_plan_type()` → `'m1_micro_scalp'`)

**Requires:** ❌ **NO - `micro_scalp_engine` NOT required**

**How Created:**
- Created via `create_trade_plan()` or `create_auto_trade_plan()` with M1 timeframe
- Has micro-scalp-like conditions (liquidity_sweep, order_block, equal_lows/highs, vwap_deviation)
- Automatically detected as `'m1_micro_scalp'` by `_detect_plan_type()`

**How They Work:**
- Uses **standard condition checking** via `_check_conditions()`
- Does NOT require `micro_scalp_engine`
- Uses optimized 10-second intervals (if enabled)
- Works with standard auto-execution logic

**Code Location:**
- Plan type detection: `auto_execution_system.py:2050-2075`
- Condition check: Standard `_check_conditions()` flow (no special micro-scalp handling)

**Example Plan:**
```json
{
  "plan_id": "chatgpt_abc123",
  "conditions": {
    "timeframe": "M1",  // ← M1 timeframe
    "liquidity_sweep": true,  // ← Micro-scalp indicator
    "price_near": 90000.0,
    "tolerance": 50.0
  }
}
// Automatically detected as 'm1_micro_scalp' by _detect_plan_type()
```

---

## Summary Table

| Plan Type | Condition Key | Engine Required? | Validation System | Optimized Intervals? |
|-----------|--------------|------------------|-------------------|---------------------|
| **Explicit Micro-Scalp** | `plan_type: "micro_scalp"` | ✅ **YES** | 4-layer validation (MicroScalpEngine) | ❌ No (uses standard 30s) |
| **Detected M1 Micro-Scalp** | Detected by `_detect_plan_type()` | ❌ **NO** | Standard condition checking | ✅ Yes (10s base interval) |

---

## How to Identify Plan Type

### Check Plan Conditions:
```python
# Explicit micro-scalp plan
if plan.conditions.get("plan_type") == "micro_scalp":
    # Requires micro_scalp_engine
    requires_engine = True

# Detected M1 micro-scalp plan
plan_type = system._detect_plan_type(plan)
if plan_type == "m1_micro_scalp":
    # Does NOT require micro_scalp_engine
    requires_engine = False
```

### Check Database:
```sql
-- Explicit micro-scalp plans
SELECT plan_id FROM trade_plans 
WHERE json_extract(conditions, '$.plan_type') = 'micro_scalp';

-- M1 plans (may be detected as m1_micro_scalp)
SELECT plan_id FROM trade_plans 
WHERE json_extract(conditions, '$.timeframe') = 'M1';
```

---

## Engine Initialization

The `micro_scalp_engine` is initialized in `AutoExecutionSystem.__init__()` if:
- `mt5_service` is available
- `m1_data_fetcher` is available

**Initialization Code:**
```python
# auto_execution_system.py:679-690
if mt5_service and m1_data_fetcher:
    self.micro_scalp_engine = MicroScalpEngine(...)
    logger.info("Micro-scalp engine initialized")
else:
    logger.warning(f"Micro-scalp engine not available: {e}")
```

**If Engine Not Available:**
- Explicit micro-scalp plans (`plan_type: "micro_scalp"`) will **fail condition checks**
- Detected M1 micro-scalp plans will **continue working** with standard condition checking

---

## Optimized 10-Second Intervals

**Important:** The optimized 10-second interval system works with **detected M1 micro-scalp plans** (`'m1_micro_scalp'`), NOT explicit micro-scalp plans.

**Why:**
- `_detect_plan_type()` returns `'m1_micro_scalp'` for M1 plans with micro-scalp indicators
- Adaptive intervals use this detected type to apply 10s base interval
- Explicit `plan_type: "micro_scalp"` plans use standard 30s interval (not optimized)

**To Use Optimized Intervals:**
- Create plans with M1 timeframe and micro-scalp conditions (liquidity_sweep, order_block, etc.)
- Do NOT set `plan_type: "micro_scalp"` explicitly
- System will detect as `'m1_micro_scalp'` and use 10s intervals

---

## Recommendations

### For Optimized 10-Second Intervals:
1. ✅ Create M1 plans with micro-scalp conditions (liquidity_sweep, order_block, vwap_deviation)
2. ✅ Let system auto-detect as `'m1_micro_scalp'`
3. ✅ Use standard condition checking (no engine required)
4. ✅ Benefit from 10s base interval when price is near entry

### For 4-Layer Validation:
1. ✅ Use `create_micro_scalp_plan()` API
2. ✅ Ensure `micro_scalp_engine` is initialized
3. ✅ Plans will use 4-layer validation system
4. ⚠️ Uses standard 30s interval (not optimized 10s)

---

## Troubleshooting

### Issue: Micro-scalp plans not executing

**Check 1: Plan Type**
```python
# Check if plan has explicit plan_type
if plan.conditions.get("plan_type") == "micro_scalp":
    # Requires engine
    if not system.micro_scalp_engine:
        print("ERROR: Engine not available for explicit micro-scalp plan")
```

**Check 2: Engine Status**
```python
# Check if engine is initialized
if system.micro_scalp_engine:
    print("Engine available")
else:
    print("Engine not available - check mt5_service and m1_data_fetcher")
```

**Check 3: Log Messages**
- Look for: `"Micro-scalp plan {plan_id} requires micro-scalp engine (not available)"`
- If present: Engine is required but not available
- Solution: Ensure `mt5_service` and `m1_data_fetcher` are passed to `AutoExecutionSystem`

---

## Conclusion

**For most M1 micro-scalp auto-execution plans:**
- ❌ **NO** - `micro_scalp_engine` is **NOT required**
- Plans detected as `'m1_micro_scalp'` use standard condition checking
- Optimized 10-second intervals work with these plans

**Only for explicit micro-scalp plans:**
- ✅ **YES** - `micro_scalp_engine` **IS required**
- Plans with `plan_type: "micro_scalp"` use 4-layer validation
- Engine must be initialized for these plans to work
