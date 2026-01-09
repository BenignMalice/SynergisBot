# Monitoring System Update Analysis for Stop/Limit Orders

## Current Monitoring System Behavior

### **Current Flow (Market Orders):**
```
_monitor_loop() runs every 30 seconds:
  1. For each pending plan:
     - Check expiration
     - Check cancellation conditions
     - Check if conditions are met (_check_conditions)
     - If conditions met → _execute_trade() → executes market order immediately
     - Plan status → "executed"
     - Remove plan from memory
```

### **Key Code Location:**
- **File:** `auto_execution_system.py`
- **Method:** `_monitor_loop()` (line ~10028)
- **Execution Point:** Line ~10441-10444
  ```python
  if self._check_conditions(plan):
      if self._execute_trade(plan):
          # Remove plan from memory
          del self.plans[plan_id]
  ```

---

## What Needs to Change for Stop/Limit Orders

### **New Flow (Stop/Limit Orders):**
```
_monitor_loop() runs every 30 seconds:
  1. For each pending plan:
     - Check expiration
     - Check cancellation conditions
     - Check if conditions are met (_check_conditions)
     - If conditions met AND order_type is stop/limit:
       → _execute_trade() → places pending order (doesn't execute immediately)
       → Plan status → "pending_order_placed" (NOT "executed")
       → Keep plan in memory (don't remove)
       → Store pending_order_ticket
  
  2. NEW: Periodic check for pending orders (every 30 seconds):
     - For each plan with status "pending_order_placed":
       → Check MT5 if pending order still exists
       → If order filled → update plan status to "executed", remove from memory
       → If order cancelled/expired → update plan status, remove from memory
```

---

## Required Changes

### **1. Modify `_execute_trade()` Return Behavior**

**Current:**
- Returns `True` if trade executed successfully
- Plan is removed from memory immediately

**New:**
- For market orders: Returns `True` → plan removed (current behavior)
- For stop/limit orders: Returns `True` → plan stays in memory with status "pending_order_placed"

**Code Change:**
```python
# In _monitor_loop(), after _execute_trade():
if self._execute_trade(plan):
    if order_type_str == "market":
        # Market order: Remove plan immediately (current behavior)
        del self.plans[plan_id]
    else:
        # Pending order: Keep plan in memory, status already updated to "pending_order_placed"
        # Don't remove - will be monitored until order fills
        pass
```

---

### **2. Add Pending Order Check Method**

**New Method:** `_check_pending_orders()`

**Location:** `auto_execution_system.py`

**Purpose:** Check all plans with status "pending_order_placed" and see if their pending orders have filled

**Implementation:**
```python
def _check_pending_orders(self) -> None:
    """
    Check pending orders and update plan status when they fill.
    Called periodically from monitoring loop.
    """
    import MetaTrader5 as mt5
    
    if not self.mt5_service.connect():
        return
    
    # Get all plans with pending orders
    pending_plan_ids = []
    with self.plans_lock:
        for plan_id, plan in self.plans.items():
            if plan.status == "pending_order_placed" and plan.pending_order_ticket:
                pending_plan_ids.append((plan_id, plan))
    
    for plan_id, plan in pending_plan_ids:
        try:
            # Check if order still exists
            orders = mt5.orders_get(ticket=plan.pending_order_ticket)
            
            if not orders or len(orders) == 0:
                # Order no longer exists - check if it filled
                positions = mt5.positions_get(ticket=plan.pending_order_ticket)
                
                if positions and len(positions) > 0:
                    # Order filled - update plan status
                    pos = positions[0]
                    plan.status = "executed"
                    plan.executed_at = datetime.now(timezone.utc).isoformat()
                    plan.ticket = pos.ticket
                    
                    logger.info(f"Pending order {plan.pending_order_ticket} filled for plan {plan_id}")
                    self._update_plan_status(plan)
                    
                    # Remove from memory
                    with self.plans_lock:
                        if plan_id in self.plans:
                            del self.plans[plan_id]
                else:
                    # Order cancelled or expired
                    logger.warning(f"Pending order {plan.pending_order_ticket} no longer exists (may be cancelled)")
                    plan.status = "cancelled"
                    self._update_plan_status(plan)
                    
                    # Remove from memory
                    with self.plans_lock:
                        if plan_id in self.plans:
                            del self.plans[plan_id]
        except Exception as e:
            logger.error(f"Error checking pending order for plan {plan_id}: {e}")
```

---

### **3. Integrate Pending Order Check into Monitoring Loop**

**Location:** `_monitor_loop()` method

**Integration Point:** After checking all pending plans, before sleep

**Code Addition:**
```python
# In _monitor_loop(), after checking all plans:
# Check pending orders (every 30 seconds, same as condition checks)
if time.time() - last_pending_check > 30:
    try:
        self._check_pending_orders()
    except Exception as e:
        logger.error(f"Error checking pending orders: {e}", exc_info=True)
    last_pending_check = time.time()
```

**Initialize tracking variable:**
```python
# At start of _monitor_loop():
last_pending_check = 0  # Track last time we checked pending orders
```

---

### **4. Handle Plan Expiration for Pending Orders**

**Current:** Plans with status "pending" are checked for expiration

**New:** Plans with status "pending_order_placed" also need expiration handling

**Code Change:**
```python
# In _monitor_loop(), expiration check section:
if plan.status in ["pending", "pending_order_placed"]:  # Add "pending_order_placed"
    if hasattr(plan, 'expires_at') and plan.expires_at:
        # ... existing expiration logic ...
        
        # If plan has pending order, cancel it
        if plan.status == "pending_order_placed" and plan.pending_order_ticket:
            try:
                import MetaTrader5 as mt5
                if self.mt5_service.connect():
                    request = {
                        "action": mt5.TRADE_ACTION_REMOVE,
                        "order": plan.pending_order_ticket,
                    }
                    result = mt5.order_send(request)
                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                        logger.info(f"Cancelled pending order {plan.pending_order_ticket} for expired plan {plan_id}")
                    else:
                        logger.warning(f"Failed to cancel pending order {plan.pending_order_ticket}: {result.retcode}")
            except Exception as e:
                logger.error(f"Error cancelling pending order for expired plan {plan_id}: {e}")
```

---

### **5. Handle Plan Cancellation for Pending Orders**

**Location:** `cancel_plan()` method

**Code Addition:**
```python
# In cancel_plan() method:
if plan.pending_order_ticket:
    # Cancel pending order in MT5
    try:
        import MetaTrader5 as mt5
        if self.mt5_service.connect():
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": plan.pending_order_ticket,
            }
            result = mt5.order_send(request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Cancelled pending order {plan.pending_order_ticket} for plan {plan_id}")
            else:
                logger.warning(f"Failed to cancel pending order {plan.pending_order_ticket}: {result.retcode}")
    except Exception as e:
        logger.error(f"Error cancelling pending order for plan {plan_id}: {e}")
```

---

## Summary of Monitoring System Changes

### **Changes Required:**

1. ✅ **Modify `_execute_trade()` handling** - Don't remove plan from memory for pending orders
2. ✅ **Add `_check_pending_orders()` method** - Check if pending orders filled
3. ✅ **Integrate pending order check into `_monitor_loop()`** - Call periodically
4. ✅ **Update expiration handling** - Cancel pending orders when plan expires
5. ✅ **Update cancellation handling** - Cancel pending orders when plan cancelled

### **What Stays the Same:**

- ✅ Condition checking logic (unchanged)
- ✅ Expiration checking logic (just add pending order cancellation)
- ✅ Cancellation checking logic (just add pending order cancellation)
- ✅ Plan reloading logic (unchanged)
- ✅ Main loop structure (unchanged)

---

## Performance Considerations

### **Additional Overhead:**

1. **Pending Order Check:**
   - Frequency: Every 30 seconds (same as condition checks)
   - MT5 API calls: `orders_get()` + `positions_get()` per pending order
   - Impact: Minimal (only checks plans with pending orders)

2. **Memory Usage:**
   - Plans with pending orders stay in memory longer
   - Impact: Minimal (plans are removed once order fills or expires)

3. **Database Writes:**
   - Additional status updates when orders fill
   - Impact: Minimal (same as current execution updates)

---

## Testing Requirements

### **Test Scenarios:**

1. ✅ Place stop order → verify plan stays in memory with "pending_order_placed" status
2. ✅ Wait for order to fill → verify plan status updates to "executed" and plan removed
3. ✅ Place limit order → verify same behavior
4. ✅ Cancel plan with pending order → verify order cancelled in MT5
5. ✅ Expire plan with pending order → verify order cancelled in MT5
6. ✅ Multiple pending orders → verify all checked correctly
7. ✅ Order fills after plan expiration → verify proper handling

---

## Conclusion

**YES, the monitoring system DOES need updating**, but the changes are **additive** rather than **replacement**:

- ✅ **Add** pending order checking logic
- ✅ **Modify** execution handling to keep pending orders in memory
- ✅ **Update** expiration/cancellation to handle pending orders
- ✅ **Keep** all existing monitoring logic intact

The changes are **moderate** in complexity and **low** in risk since they don't change existing market order behavior.
