# Stop/Limit Order Implementation - What's Needed

## Current System State

### **What Works Now:**
- ✅ **Market Orders**: System executes market orders immediately when conditions are met
- ✅ **MT5Service Support**: `mt5_service.pending_order()` already exists and supports stop/limit orders
- ✅ **Order Type Detection**: MT5Service can determine order type from comment field

### **What's Missing:**
- ❌ **Order Type Check**: Auto-execution system doesn't check `order_type` condition
- ❌ **Pending Order Logic**: System always uses `open_order()` (market orders)
- ❌ **Order Type Mapping**: No logic to map `order_type: "stop"` or `order_type: "limit"` to MT5 order types

---

## Required Changes

### **1. Order Type Detection in `_execute_trade()`**

**Location:** `auto_execution_system.py` → `_execute_trade()` method (around line 9503)

**Current Code:**
```python
# Execute trade using MT5Service (handles all validation, fresh prices, proper filling mode)
result = self.mt5_service.open_order(
    symbol=symbol_norm,
    side=direction,
    lot=lot_size,
    sl=execution_sl,
    tp=execution_tp,
    comment=safe_comment,
)
```

**What Needs to Change:**
- Check `plan.conditions.get("order_type")` or `plan.conditions.get("order_type")`
- If `order_type` is `"market"` or `None` → use `open_order()` (current behavior)
- If `order_type` is `"stop"` or `"limit"` → use `pending_order()` with appropriate type

---

### **2. Order Type Mapping Logic**

**New Function Needed:**
```python
def _determine_order_type(self, plan: TradePlan) -> str:
    """
    Determine MT5 order type based on plan direction and order_type condition.
    
    Returns:
        - "market" → Use open_order() (immediate execution)
        - "buy_stop", "buy_limit", "sell_stop", "sell_limit" → Use pending_order()
    """
    order_type = plan.conditions.get("order_type", "market")
    direction = plan.direction.upper()
    
    if order_type == "market" or order_type is None:
        return "market"
    
    # Map order_type + direction to MT5 pending order type
    if direction == "BUY":
        if order_type == "stop":
            return "buy_stop"  # BUY STOP: Entry above current price
        elif order_type == "limit":
            return "buy_limit"  # BUY LIMIT: Entry below current price
    else:  # SELL
        if order_type == "stop":
            return "sell_stop"  # SELL STOP: Entry below current price
        elif order_type == "limit":
            return "sell_limit"  # SELL LIMIT: Entry above current price
    
    # Default to market if invalid
    return "market"
```

---

### **3. Execution Logic Split**

**What Needs to Change:**

**Current Flow:**
```
Check conditions → All met? → Execute market order immediately
```

**New Flow:**
```
Check conditions → All met? → Check order_type
    ├─ market → Execute market order immediately (current behavior)
    ├─ stop → Place pending stop order (waits for price to reach entry)
    └─ limit → Place pending limit order (waits for price to reach entry)
```

**Implementation:**
```python
# In _execute_trade() method, replace the open_order() call:

order_type_str = self._determine_order_type(plan)

if order_type_str == "market":
    # Current behavior: Immediate market execution
    result = self.mt5_service.open_order(
        symbol=symbol_norm,
        side=direction,
        lot=lot_size,
        sl=execution_sl,
        tp=execution_tp,
        comment=safe_comment,
    )
else:
    # New behavior: Place pending order
    # For pending orders, entry_price is the trigger price
    result = self.mt5_service.pending_order(
        symbol=symbol_norm,
        side=direction,
        entry=plan.entry_price,  # Trigger price for stop/limit
        sl=execution_sl,
        tp=execution_tp,
        lot=lot_size,
        comment=order_type_str,  # MT5Service uses comment to determine order type
    )
```

---

### **4. Validation Logic Changes**

**Current Validation:**
- System checks if price is near entry before executing
- For market orders, this makes sense (execute when price reaches entry)

**New Validation Needed:**
- **Market Orders**: Keep current validation (price must be near entry)
- **Stop Orders**: 
  - BUY STOP: Entry must be **above** current price (valid stop level)
  - SELL STOP: Entry must be **below** current price (valid stop level)
- **Limit Orders**:
  - BUY LIMIT: Entry must be **below** current price (valid limit level)
  - SELL LIMIT: Entry must be **above** current price (valid limit level)

**Example Validation:**
```python
# Before execution, validate order type requirements
if order_type_str != "market":
    quote = self.mt5_service.get_quote(symbol_norm)
    current_price = (quote.bid + quote.ask) / 2.0
    
    if order_type_str == "buy_stop":
        if plan.entry_price <= current_price:
            logger.error(f"BUY STOP entry {plan.entry_price} must be above current {current_price}")
            return False
    elif order_type_str == "sell_stop":
        if plan.entry_price >= current_price:
            logger.error(f"SELL STOP entry {plan.entry_price} must be below current {current_price}")
            return False
    elif order_type_str == "buy_limit":
        if plan.entry_price >= current_price:
            logger.error(f"BUY LIMIT entry {plan.entry_price} must be below current {current_price}")
            return False
    elif order_type_str == "sell_limit":
        if plan.entry_price <= current_price:
            logger.error(f"SELL LIMIT entry {plan.entry_price} must be above current {current_price}")
            return False
```

---

### **5. Plan Status Handling**

**Current Behavior:**
- Plan status: `pending` → `executing` → `executed`

**New Behavior Needed:**
- **Market Orders**: `pending` → `executing` → `executed` (immediate)
- **Pending Orders**: `pending` → `executing` → `pending_order_placed` → `executed` (when order fills)

**Database Changes:**
- May need to track pending order ticket separately from executed position ticket
- Status field may need new value: `"pending_order_placed"` or `"order_pending"`

---

### **6. Monitoring Changes**

**Current Monitoring:**
- System checks conditions every 30 seconds
- When conditions met → execute immediately

**New Monitoring Needed:**
- **Market Orders**: Keep current behavior (execute when conditions met)
- **Pending Orders**: 
  - When conditions met → place pending order
  - Monitor pending order status (check if it filled)
  - Update plan status when order fills or expires

**Additional Monitoring:**
- Check MT5 pending orders to see if they filled
- Handle order expiration (if order doesn't fill before plan expires)
- Handle order cancellation (if conditions change and order should be cancelled)

---

### **7. Condition Checking Logic**

**Current Logic:**
- System checks all conditions before executing
- For market orders, this ensures price is at entry when executing

**New Logic Needed:**
- **Market Orders**: Keep current logic (all conditions must be met before execution)
- **Pending Orders**: 
  - Conditions must be met to **place** the order
  - Order will **fill automatically** when price reaches entry (no need to re-check conditions)
  - However, you may want to cancel pending order if conditions change

**Example:**
```python
# For pending orders, conditions are checked once to place the order
# The order itself handles the price trigger (no need to monitor price continuously)
# But you may want to cancel if other conditions change (e.g., volatility_state changes)
```

---

## Summary of Changes

### **Code Changes Required:**

1. **New Method**: `_determine_order_type(plan)` - Maps order_type condition to MT5 order type
2. **Modified Method**: `_execute_trade(plan)` - Split execution logic (market vs pending)
3. **New Validation**: Check entry price is valid for stop/limit order type
4. **Status Tracking**: Handle `pending_order_placed` status
5. **Monitoring**: Track pending orders and update when they fill

### **Database Changes (Optional):**

- Add `pending_order_ticket` field to track pending order ticket
- Add `order_type` field to store order type (for reference)
- Consider new status: `"pending_order_placed"`

### **Testing Required:**

1. **Market Orders**: Ensure existing behavior still works
2. **Stop Orders**: Test BUY STOP and SELL STOP placement and filling
3. **Limit Orders**: Test BUY LIMIT and SELL LIMIT placement and filling
4. **Validation**: Test invalid entry prices (e.g., BUY STOP below current price)
5. **Monitoring**: Test pending order tracking and status updates

---

## Complexity Assessment

### **Difficulty: Medium**

**Reasons:**
- ✅ MT5Service already supports pending orders (no changes needed there)
- ✅ Core logic is straightforward (if/else based on order_type)
- ⚠️ Requires careful validation (entry price must be valid for order type)
- ⚠️ Requires status tracking changes (pending orders vs executed positions)
- ⚠️ Requires monitoring changes (track pending orders until they fill)

### **Estimated Implementation Time:**
- **Core Logic**: 2-3 hours (order type detection + execution split)
- **Validation**: 1-2 hours (entry price validation for each order type)
- **Status Tracking**: 1-2 hours (database changes + status updates)
- **Monitoring**: 2-3 hours (pending order tracking + fill detection)
- **Testing**: 2-3 hours (comprehensive testing of all order types)
- **Total**: ~8-13 hours

---

## Key Considerations

### **1. Entry Price Validation**
- Stop orders require entry price to be in correct direction from current price
- Limit orders require entry price to be in opposite direction from current price
- Must validate before placing order (MT5 will reject invalid orders)

### **2. Order Expiration**
- Pending orders can expire if plan expires before order fills
- Need to handle order cancellation when plan expires
- Need to handle order cancellation if conditions change

### **3. Order Modification**
- If plan is modified (e.g., SL/TP changed), pending order may need to be modified
- MT5 allows modifying pending orders (change SL/TP, entry price, etc.)
- Need to handle order modification logic

### **4. Order Filling**
- Pending orders fill automatically when price reaches entry
- No need to continuously monitor price (MT5 handles it)
- But need to detect when order filled and update plan status

### **5. Condition Changes**
- If conditions change after pending order is placed, should order be cancelled?
- Example: If `volatility_state` changes from "contracting" to "expanding", cancel order?
- This requires policy decision (when to cancel pending orders)

---

## Recommended Implementation Order

1. **Phase 1: Core Logic** (2-3 hours)
   - Add `_determine_order_type()` method
   - Split `_execute_trade()` to handle market vs pending orders
   - Test with simple stop/limit orders

2. **Phase 2: Validation** (1-2 hours)
   - Add entry price validation for each order type
   - Test invalid entry prices are rejected

3. **Phase 3: Status Tracking** (1-2 hours)
   - Add `pending_order_placed` status
   - Track pending order tickets
   - Update plan status when order fills

4. **Phase 4: Monitoring** (2-3 hours)
   - Add pending order tracking
   - Detect when orders fill
   - Handle order expiration/cancellation

5. **Phase 5: Testing** (2-3 hours)
   - Comprehensive testing of all order types
   - Test edge cases (invalid prices, order expiration, etc.)

---

## Conclusion

**The system CAN be updated to support stop/limit orders**, but it requires:

1. ✅ **Moderate code changes** (~8-13 hours of work)
2. ✅ **MT5Service already supports it** (no changes needed there)
3. ⚠️ **Requires careful validation** (entry price must be valid for order type)
4. ⚠️ **Requires status tracking changes** (pending orders vs executed positions)
5. ⚠️ **Requires monitoring changes** (track pending orders until they fill)

**The good news:** The infrastructure is already there (MT5Service.pending_order()), so it's mainly a matter of wiring it up in the auto-execution system.
