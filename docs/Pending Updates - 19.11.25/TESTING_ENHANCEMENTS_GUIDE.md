# Testing Guide - Plan Enhancement Recommendations

## Overview

This guide helps you test whether ChatGPT correctly includes the recommended enhancements (M1 validation and volatility filters) when creating trade plans, and whether the auto-execution system properly handles them.

---

## Test 1: ChatGPT Plan Creation Test

### Purpose
Verify ChatGPT includes recommended conditions when creating plans.

### Steps

1. **Start ChatGPT conversation** (via Telegram or desktop agent)

2. **Test CHOCH Plan Creation:**
   ```
   User: "Create a CHOCH Bull plan for BTCUSD at 84000, SL 83800, TP 84500"
   ```

3. **Expected Result:**
   - Plan should include:
     - ✅ `choch_bull: true`
     - ✅ `timeframe: "M5"` (or M15)
     - ✅ `price_near: 84000`
     - ✅ `tolerance: 100` (for BTCUSD)
     - ⭐ `m1_choch_bos_combo: true` (RECOMMENDED)
     - ⭐ `min_volatility: 0.5` (RECOMMENDED)
     - ⭐ `bb_width_threshold: 2.5` (RECOMMENDED)

4. **Check Plan in Database:**
   ```python
   # Run this script to check plan conditions
   python check_plan_conditions.py <plan_id>
   ```

5. **Verify Conditions:**
   - Open plan in web interface: `http://localhost:8010/auto-execution/view`
   - Check that conditions JSON includes all recommended fields

### Success Criteria
- ✅ ChatGPT includes `m1_choch_bos_combo: true` for CHOCH plans
- ✅ ChatGPT includes `min_volatility: 0.5` and `bb_width_threshold: 2.5` for all plans
- ✅ Plan is created successfully in database

---

## Test 2: Auto-Execution System Condition Checking

### Purpose
Verify the auto-execution system properly validates the new conditions.

### Steps

1. **Create Test Plan with All Conditions:**
   ```python
   # Create test script: test_enhanced_plan.py
   from chatgpt_auto_execution_integration import ChatGPTAutoExecution
   
   auto_exec = ChatGPTAutoExecution()
   
   plan = auto_exec.create_trade_plan(
       symbol="BTCUSD",
       direction="BUY",
       entry_price=84000.0,
       stop_loss=83800.0,
       take_profit=84500.0,
       volume=0.01,
       conditions={
           "choch_bull": True,
           "timeframe": "M5",
           "price_near": 84000.0,
           "tolerance": 100.0,
           "m1_choch_bos_combo": True,  # M1 validation
           "min_volatility": 0.5,        # Volatility filter
           "bb_width_threshold": 2.5    # BB width filter
       },
       expires_hours=1,  # Short expiry for testing
       notes="Test plan with all enhancements"
   )
   
   print(f"Plan created: {plan['plan_id']}")
   print(f"Conditions: {plan['conditions']}")
   ```

2. **Run Test Script:**
   ```bash
   python test_enhanced_plan.py
   ```

3. **Monitor Auto-Execution Logs:**
   ```bash
   # Watch logs for condition checking
   # Look for messages like:
   # - "M1 validation passed for plan..."
   # - "Volatility too low: ATR X < 0.5"
   # - "BB width check: X > 2.5"
   ```

4. **Check System Status:**
   ```python
   # Check if plan is being monitored
   from auto_execution_system import AutoExecutionSystem
   
   auto_sys = AutoExecutionSystem()
   status = auto_sys.get_system_status()
   print(f"Pending plans: {status['pending_plans']}")
   ```

### Success Criteria
- ✅ Plan is created and stored in database
- ✅ Auto-execution system loads plan successfully
- ✅ System checks M1 validation condition
- ✅ System checks volatility thresholds
- ✅ System checks BB width threshold
- ✅ No errors in logs

---

## Test 3: Condition Validation Test

### Purpose
Verify each condition type works independently.

### Test Script: `test_condition_validation.py`

```python
"""
Test individual condition validation
"""
import sqlite3
import json
from pathlib import Path
from auto_execution_system import AutoExecutionSystem, TradePlan
from datetime import datetime

db_path = Path("data/auto_execution.db")

def test_m1_validation_condition():
    """Test M1 validation condition"""
    print("\n=== Testing M1 Validation Condition ===")
    
    # Create test plan with M1 validation
    plan = TradePlan(
        plan_id="test_m1_validation",
        symbol="BTCUSD",
        direction="BUY",
        entry_price=84000.0,
        stop_loss=83800.0,
        take_profit=84500.0,
        volume=0.01,
        conditions={
            "choch_bull": True,
            "timeframe": "M5",
            "m1_choch_bos_combo": True
        },
        created_at=datetime.now().isoformat(),
        created_by="test",
        status="pending"
    )
    
    # Initialize auto execution system
    from infra.mt5_service import MT5Service
    from infra.m1_data_fetcher import M1DataFetcher
    from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
    
    mt5_service = MT5Service()
    mt5_service.connect()
    
    m1_fetcher = M1DataFetcher(data_source=mt5_service, max_candles=200)
    m1_analyzer = M1MicrostructureAnalyzer()
    
    auto_sys = AutoExecutionSystem(
        mt5_service=mt5_service,
        m1_data_fetcher=m1_fetcher,
        m1_analyzer=m1_analyzer
    )
    
    # Test condition checking
    result = auto_sys._check_conditions(plan)
    print(f"M1 Validation Test Result: {result}")
    
    return result

def test_volatility_conditions():
    """Test volatility filter conditions"""
    print("\n=== Testing Volatility Filter Conditions ===")
    
    plan = TradePlan(
        plan_id="test_volatility",
        symbol="BTCUSD",
        direction="BUY",
        entry_price=84000.0,
        stop_loss=83800.0,
        take_profit=84500.0,
        volume=0.01,
        conditions={
            "price_near": 84000.0,
            "tolerance": 100.0,
            "min_volatility": 0.5,
            "bb_width_threshold": 2.5
        },
        created_at=datetime.now().isoformat(),
        created_by="test",
        status="pending"
    )
    
    from infra.mt5_service import MT5Service
    mt5_service = MT5Service()
    mt5_service.connect()
    
    auto_sys = AutoExecutionSystem(mt5_service=mt5_service)
    
    result = auto_sys._check_conditions(plan)
    print(f"Volatility Filter Test Result: {result}")
    
    return result

def test_combined_conditions():
    """Test all conditions together"""
    print("\n=== Testing Combined Conditions ===")
    
    plan = TradePlan(
        plan_id="test_combined",
        symbol="BTCUSD",
        direction="BUY",
        entry_price=84000.0,
        stop_loss=83800.0,
        take_profit=84500.0,
        volume=0.01,
        conditions={
            "choch_bull": True,
            "timeframe": "M5",
            "price_near": 84000.0,
            "tolerance": 100.0,
            "m1_choch_bos_combo": True,
            "min_volatility": 0.5,
            "bb_width_threshold": 2.5
        },
        created_at=datetime.now().isoformat(),
        created_by="test",
        status="pending"
    )
    
    from infra.mt5_service import MT5Service
    from infra.m1_data_fetcher import M1DataFetcher
    from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
    
    mt5_service = MT5Service()
    mt5_service.connect()
    
    m1_fetcher = M1DataFetcher(data_source=mt5_service, max_candles=200)
    m1_analyzer = M1MicrostructureAnalyzer()
    
    auto_sys = AutoExecutionSystem(
        mt5_service=mt5_service,
        m1_data_fetcher=m1_fetcher,
        m1_analyzer=m1_analyzer
    )
    
    result = auto_sys._check_conditions(plan)
    print(f"Combined Conditions Test Result: {result}")
    
    return result

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Plan Enhancement Conditions")
    print("=" * 60)
    
    try:
        test_m1_validation_condition()
        test_volatility_conditions()
        test_combined_conditions()
        
        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
```

### Run Test:
```bash
python test_condition_validation.py
```

### Success Criteria
- ✅ M1 validation condition is checked
- ✅ Volatility conditions are checked
- ✅ Combined conditions work together
- ✅ No errors during condition checking

---

## Test 4: ChatGPT Integration Test

### Purpose
Test end-to-end: ChatGPT creates plan → System monitors → Conditions checked

### Steps

1. **Create Plan via ChatGPT:**
   ```
   User: "Create a CHOCH Bull plan for BTCUSD at current price with SL 200 points below and TP 500 points above. Include M1 validation and volatility filters."
   ```

2. **Verify Plan Created:**
   - Check Telegram response for plan ID
   - Verify plan appears in web interface

3. **Check Plan Conditions:**
   ```python
   # Quick check script
   import sqlite3
   import json
   from pathlib import Path
   
   db_path = Path("data/auto_execution.db")
   plan_id = "chatgpt_xxxxx"  # From ChatGPT response
   
   with sqlite3.connect(db_path) as conn:
       cursor = conn.execute(
           "SELECT conditions FROM trade_plans WHERE plan_id = ?",
           (plan_id,)
       )
       row = cursor.fetchone()
       if row:
           conditions = json.loads(row[0])
           print("Plan Conditions:")
           print(json.dumps(conditions, indent=2))
           
           # Check for recommended conditions
           has_m1 = conditions.get("m1_choch_bos_combo", False)
           has_vol = conditions.get("min_volatility") is not None
           has_bb = conditions.get("bb_width_threshold") is not None
           
           print(f"\n✅ M1 Validation: {has_m1}")
           print(f"✅ Min Volatility: {has_vol}")
           print(f"✅ BB Width Threshold: {has_bb}")
   ```

4. **Monitor Execution:**
   - Watch logs for condition checks
   - Verify system doesn't execute until all conditions met

### Success Criteria
- ✅ ChatGPT creates plan with recommended conditions
- ✅ Plan is stored correctly in database
- ✅ Auto-execution system monitors plan
- ✅ Conditions are checked every 30 seconds
- ✅ Plan only executes when all conditions met

---

## Test 5: Manual Database Verification

### Purpose
Verify existing plans and check if enhancements are applied

### Script: `check_all_plans_conditions.py`

```python
"""
Check all pending plans for recommended enhancements
"""
import sqlite3
import json
from pathlib import Path

db_path = Path("data/auto_execution.db")

if not db_path.exists():
    print(f"Database not found: {db_path}")
    exit(1)

with sqlite3.connect(db_path) as conn:
    cursor = conn.execute("""
        SELECT plan_id, symbol, direction, conditions, notes
        FROM trade_plans
        WHERE status = 'pending'
        ORDER BY created_at DESC
    """)
    
    plans = cursor.fetchall()
    
    print("=" * 80)
    print("PENDING PLANS - ENHANCEMENT CHECK")
    print("=" * 80)
    print()
    
    for plan_id, symbol, direction, conditions_json, notes in plans:
        conditions = json.loads(conditions_json) if conditions_json else {}
        
        print(f"Plan ID: {plan_id}")
        print(f"Symbol: {symbol} | Direction: {direction}")
        
        # Check for CHOCH plans
        is_choch = conditions.get("choch_bull") or conditions.get("choch_bear")
        
        # Check enhancements
        has_m1 = conditions.get("m1_choch_bos_combo", False)
        has_min_vol = conditions.get("min_volatility") is not None
        has_bb = conditions.get("bb_width_threshold") is not None
        
        print(f"  CHOCH Plan: {is_choch}")
        print(f"  ⭐ M1 Validation: {has_m1} {'✅' if has_m1 or not is_choch else '❌ MISSING'}")
        print(f"  ⭐ Min Volatility: {has_min_vol} {'✅' if has_min_vol else '❌ MISSING'}")
        print(f"  ⭐ BB Width Threshold: {has_bb} {'✅' if has_bb else '❌ MISSING'}")
        
        if notes:
            print(f"  Notes: {notes[:60]}...")
        
        print()
    
    print("=" * 80)
    print(f"Total pending plans: {len(plans)}")
    print("=" * 80)
```

### Run:
```bash
python check_all_plans_conditions.py
```

---

## Test 6: Live Monitoring Test

### Purpose
Monitor a real plan execution with enhanced conditions

### Steps

1. **Create Test Plan:**
   - Use ChatGPT to create a CHOCH plan with explicit request for enhancements
   - Example: "Create a CHOCH Bull plan for BTCUSD with M1 validation and volatility filters"

2. **Monitor Logs:**
   ```bash
   # Watch auto-execution logs
   # Look for condition check messages every 30 seconds
   ```

3. **Check Condition Status:**
   - M1 validation: Should show "M1 validation passed" or "M1 confidence X < threshold"
   - Volatility: Should show "Volatility too low" or "ATR X < 0.5" if conditions not met
   - BB Width: Should show "BB width check: X > 2.5"

4. **Verify Execution:**
   - Plan should only execute when ALL conditions are met
   - Check Discord/Telegram notification on execution

---

## Quick Test Checklist

- [ ] **Test 1**: ChatGPT creates plan with recommended conditions
- [ ] **Test 2**: Auto-execution system loads and validates plan
- [ ] **Test 3**: Individual condition validation works
- [ ] **Test 4**: End-to-end ChatGPT → System → Execution flow
- [ ] **Test 5**: Database verification of all plans
- [ ] **Test 6**: Live monitoring of plan execution

---

## Expected Behavior

### When Conditions Are Met:
- ✅ Plan executes automatically
- ✅ Discord/Telegram notification sent
- ✅ Plan status changes to "executed"

### When Conditions Are NOT Met:
- ⏸️ Plan remains "pending"
- 📊 Logs show which condition failed
- 🔄 System continues monitoring every 30 seconds

---

## Troubleshooting

### Issue: ChatGPT doesn't include recommended conditions
**Solution**: Check `openai.yaml` was updated correctly. Restart ChatGPT bot.

### Issue: Auto-execution system errors on condition check
**Solution**: Check logs for specific error. Verify M1 analyzer and data fetcher are initialized.

### Issue: Plan never executes
**Solution**: 
- Check logs for condition failures
- Verify M1 data is available
- Check volatility thresholds are appropriate for current market conditions
- Verify BB width threshold is reasonable

---

*Testing Guide Created: 2025-11-22*

