# Auto-Execution Monitoring System Issues

## Critical Issues

### 1. Memory Leak: Execution Locks Not Cleaned Up
**Location**: `_execute_trade()`, `_monitor_loop()`

**Issue**: The `execution_locks` dictionary grows indefinitely. When plans are deleted (executed, expired, cancelled), their locks are never removed from the dictionary.

**Impact**: 
- Memory usage grows over time
- Dictionary lookup becomes slower with many entries
- Potential resource leak

**Fix**: Clean up execution locks when plans are removed:
```python
# In _monitor_loop() and _execute_trade(), after deleting plan:
if plan_id in self.execution_locks:
    del self.execution_locks[plan_id]
```

### 2. Memory Leak: Invalid Symbols Dictionary Not Cleaned Up
**Location**: `_check_conditions()`, `_monitor_loop()`

**Issue**: The `invalid_symbols` dictionary tracks symbols that fail validation, but entries are never removed even after successful execution or when plans are deleted.

**Impact**:
- Memory usage grows over time
- Symbols that become valid again are still marked as invalid
- No mechanism to retry symbols after a cooldown period

**Fix**: 
- Add cleanup when plans are removed
- Add cooldown mechanism to retry invalid symbols after a period
- Clear invalid_symbols entry on successful execution

### 3. Memory Leak: M1 Data Cache Not Fully Cleaned
**Location**: `_get_m1_data()`, `_batch_refresh_m1_data()`

**Issue**: The M1 data cache (`_m1_data_cache`, `_m1_cache_timestamps`, `_last_signal_timestamps`) grows indefinitely. While there's some cleanup in `_get_m1_data()` for stale entries, symbols are never removed when plans are deleted.

**Impact**:
- Memory usage grows over time
- Cache contains data for symbols that are no longer being monitored

**Fix**: 
- Periodically clean up cache entries for symbols that have no active plans
- Add cache size limit with LRU eviction

### 4. Memory Leak: Confidence History Not Cleaned
**Location**: `_calculate_m1_confidence()`

**Issue**: The `_confidence_history` dictionary keeps confidence history per symbol but never removes entries when symbols are no longer monitored.

**Impact**:
- Memory usage grows over time
- Dictionary lookup becomes slower

**Fix**: Clean up confidence history when plans are removed or periodically remove entries for symbols with no active plans.

## Medium Priority Issues

### 5. Race Condition: Plan Deletion During Check
**Location**: `_monitor_loop()`

**Issue**: Plans are copied to `plans_to_check` list while holding the lock, but then checked outside the lock. If a plan is deleted between the copy and the check, it could cause issues (though the code checks `plan.status != "pending"` which should handle this).

**Impact**: 
- Potential KeyError if plan is deleted between copy and access
- Inconsistent state

**Fix**: Add defensive checks or keep lock during iteration (but this might cause performance issues).

### 6. Thread Safety: Execution Locks Dictionary Access
**Location**: `_execute_trade()`

**Issue**: The `execution_locks` dictionary is accessed and modified without a lock:
```python
if plan.plan_id not in self.execution_locks:
    self.execution_locks[plan.plan_id] = threading.Lock()
```

**Impact**: 
- Potential race condition if multiple threads try to create locks simultaneously
- Dictionary corruption (unlikely but possible)

**Fix**: Protect `execution_locks` dictionary access with a lock or use `threading.Lock()` with a lock factory pattern.

### 7. Database Lock Timeout Handling
**Location**: Multiple database operations

**Issue**: Database operations use a 5.0 second timeout, but if the database is locked for longer (e.g., by another process), operations might fail silently or with unclear error messages.

**Impact**:
- Plans might not be saved/updated if database is locked
- Error messages might not be clear

**Fix**: 
- Add retry logic for database lock errors
- Improve error messages
- Consider using WAL mode for better concurrency

### 8. MT5 Connection State Tracking
**Location**: `_check_conditions()`, `_execute_trade()`

**Issue**: MT5 connection state is checked but not always properly tracked if connection drops during execution. The `mt5_connection_failures` counter might not accurately reflect the current state.

**Impact**:
- Connection failures might not be properly tracked
- Backoff mechanism might not work correctly

**Fix**: 
- Add connection health check before critical operations
- Improve connection state tracking
- Add connection retry with exponential backoff

## Low Priority Issues

### 9. Symbol Normalization Edge Cases
**Location**: `_check_conditions()`, `_execute_trade()`

**Issue**: Complex symbol normalization logic might have edge cases for unusual symbol names (e.g., symbols with multiple 'C' characters, symbols with special characters).

**Impact**:
- Some symbols might not be normalized correctly
- Execution might fail for edge case symbols

**Fix**: 
- Add comprehensive symbol normalization tests
- Handle edge cases explicitly
- Log normalization attempts for debugging

### 10. Error Recovery in Monitoring Loop
**Location**: `_monitor_loop()`

**Issue**: If an exception occurs in the monitoring loop, it's caught and logged, but the loop continues. This might cause some plans to be skipped in that iteration.

**Impact**:
- Plans might not be checked in the iteration where an error occurs
- Errors might be silently swallowed

**Fix**: 
- Add more granular error handling
- Track which plans were checked successfully
- Add metrics for monitoring loop health

### 11. Plan Reload Race Condition
**Location**: `_monitor_loop()`

**Issue**: When reloading plans from the database, there's a potential race condition where a plan could be added/removed while the reload is happening.

**Impact**:
- Plans might be missed or duplicated
- Inconsistent state between database and memory

**Fix**: 
- Use database transactions for atomic reload
- Add version checking for plans
- Improve merge logic

### 12. M1 Data Staleness Check
**Location**: `_is_m1_signal_stale()`, `_has_m1_signal_changed()`

**Issue**: The staleness check might not accurately reflect when M1 data is truly stale, especially if the refresh manager is not working correctly.

**Impact**:
- Plans might be skipped unnecessarily
- Stale data might be used

**Fix**: 
- Improve staleness detection
- Add fallback mechanisms
- Better integration with refresh manager

## Recommendations

1. **Immediate**: Fix memory leaks (#1, #2, #3, #4) - these will cause issues over time
2. **Short-term**: Fix thread safety issues (#6) and improve error handling (#10)
3. **Long-term**: Add comprehensive monitoring and metrics, improve database concurrency (#7)

## Testing Recommendations

1. **Memory Leak Test**: Run system for extended period and monitor memory usage
2. **Concurrency Test**: Test with multiple plans executing simultaneously
3. **Database Lock Test**: Test behavior when database is locked by another process
4. **Symbol Normalization Test**: Test with various symbol formats
5. **Error Recovery Test**: Test behavior when various errors occur in monitoring loop

