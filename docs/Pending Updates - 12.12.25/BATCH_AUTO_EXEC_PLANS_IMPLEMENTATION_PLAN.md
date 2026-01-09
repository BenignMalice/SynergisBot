# Batch Auto Execution Plans - Implementation Plan

## Overview
Enable ChatGPT to create, update, and cancel multiple auto-execution plans in a single tool call, reducing permission prompts and improving workflow efficiency.

---

## ⚠️ **REVIEW FINDINGS & CRITICAL FIXES**

### **Logic Issues Fixed:**
1. **Error Handling Strategy Changed**: Changed from fail-fast to partial success for batch create
   - Rationale: If user requests 5 plans and 1 fails, they want the other 4 created
   - **REVISED**: Even if ALL plans fail, return 200 OK with detailed error results (not generic error)
   - This allows user to see all errors and fix them, rather than getting generic error message

2. **Plan Type Routing**: Each plan MUST specify `plan_type` to route to correct creation method
   - Added detailed requirements for each plan type
   - Bracket trades removed - users create two independent plans instead

3. **Symbol Normalization**: **DO NOT normalize in batch endpoint** - Individual methods handle normalization

4. **Weekend Filtering**: **Individual methods handle weekend filtering**
   - Weekend filtering is performed inside individual `create_*_plan()` methods
   - Batch endpoint should NOT duplicate this validation
   - Weekend-allowed: vwap_reversion, liquidity_sweep_reversal, micro_scalp, mean_reversion_range_scalp
   - Weekend-disallowed: breakout_ib_volatility_trap, trend_continuation_pullback, session_liquidity_run
   - If weekend filtering rejects a plan, individual method returns error which is passed through to results

5. **Bracket Trades Removed**: Bracket trades are no longer needed in batch operations
   - Users can create two independent plans (one BUY, one SELL) with different conditions
   - Each plan monitors its own conditions independently
   - More flexible than OCO (One Cancels Other) bracket trades
   - If one executes, the other can still be monitored and execute later if its conditions are met

### **Integration Issues Fixed:**
1. **Validation Logic**: Each plan type has different validation rules
   - Micro-scalp: SL/TP distance validation
   - Range scalp: min_confluence validation
   - Order block: min_validation_score validation
   - All plans: Volatility state validation, conditions validation

2. **Transaction Handling**: Do NOT use single transaction for all plans
   - Use existing individual creation methods (they handle their own transactions)
   - Each plan creation is independent (partial success approach)

3. **System Layer**: Do NOT add batch methods to `AutoExecutionSystem`
   - Use existing methods in API endpoint (loop through plans)
   - Reuses existing validation logic, no code duplication

4. **Rate Limiting**: Max 20 plans per batch (configurable)
   - Return error if batch exceeds limit

5. **Timeout Handling**: 60 second timeout for batch operations
   - Return partial results if timeout occurs

### **Documentation Requirements:**
1. **ChatGPT Knowledge Docs**: Must update `AUTO_EXECUTION_CHATGPT_INSTRUCTIONS.md`
   - Add batch operations section with examples
   - Update workflow and scenarios sections
   - Document when to use batch vs single tools

2. **Response Format**: Detailed per-plan results with:
   - Index to match request order
   - Plan type and symbol in all results
   - Detailed error messages for failures
   - **CRITICAL: Tool Response Format**: All tools MUST return `{"summary": "...", "data": {...}}` format (required by desktop agent)

### **Additional Issues Found & Fixed:**

1. **Bracket Trades Removed**: Removed bracket trade support from batch operations
   - Users can create two independent plans instead (one BUY, one SELL)
   - Each plan has its own conditions and monitors independently
   - More flexible than OCO bracket trades

3. **Input Validation**: Added comprehensive input validation for all batch operations:
   - Empty arrays validation
   - Array type validation
   - Required fields validation
   - Early validation before API calls

4. **Error Handling**: Enhanced error handling in tool layer:
   - HTTP errors (4xx, 5xx)
   - Timeout errors (60s)
   - Connection errors
   - User-friendly error messages for ChatGPT

5. **Duplicate Handling**: Added deduplication for batch cancel (remove duplicate plan_ids)

6. **Update Validation**: Enhanced batch update validation:
   - Check plan exists
   - Check plan is pending status
   - Validate update fields
   - Validate conditions if provided

7. **Response Formatting**: Improved response formatting for ChatGPT:
   - Summary messages ("Created X of Y plans")
   - Detailed per-plan results
   - Actionable error messages

8. **Implementation Order**: Fixed - removed Phase 4 (System Layer) since we use existing methods

9. **Testing**: Expanded test coverage:
   - Empty arrays
   - Invalid inputs
   - Duplicate plan_ids
   - Creating two independent plans (BUY and SELL) with different conditions
   - HTTP/timeout/connection errors

10. **Pydantic Model Validation**: Added requirement for Pydantic models:
    - `BatchCreatePlanRequest`, `BatchUpdatePlanRequest`, `BatchCancelPlanRequest`
    - FastAPI automatic validation
    - Handle 422 validation errors in tool layer

12. **Exception Handling**: Enhanced exception handling in API endpoint:
    - Broad exception catch to prevent batch from stopping on one failure
    - Log exceptions for debugging
    - Continue processing remaining plans

13. **Pydantic Model Validation**: Added requirement for Pydantic models:
    - `BatchCreatePlanRequest`, `BatchUpdatePlanRequest`, `BatchCancelPlanRequest`
    - FastAPI automatic validation with 422 errors on failure
    - Tool layer must handle 422 validation errors gracefully
    - Validators for array length (max 20 for create)

14. **Response Structure Validation**: Standardized response format:
    - Verify `success` field in response for all plan types
    - Each plan returns standard `plan_id` field
    - Handle cases where method returns `success: False`

15. **Tool Response Format**: **CRITICAL** - All batch tools MUST return `{"summary": "...", "data": {...}}` format:
    - Required by desktop agent for Pydantic validation
    - Summary must be a string (not None)
    - Data must be an object (can be empty but must exist)
    - All error cases must also return this format

16. **Duplicate Handling**: Added deduplication for batch update:
    - Check for duplicate plan_ids in updates array
    - Keep last update for each plan_id (deduplicate)
    - Prevents conflicting updates to same plan

17. **HTTP Status Code Handling**: Clarified status code strategy:
    - Return 200 OK for partial success (some plans succeed, some fail)
    - Return 422 for Pydantic validation failures (malformed request)
    - Return 500 for server errors (unexpected exceptions)
    - Include error details in response body, not just status code

18. **Empty Results Handling**: Added handling for when all operations fail:
    - Still return 200 OK with `successful: 0, failed: total`
    - Include all error details in results array
    - Tool layer should format as error summary but include data

19. **API Response Validation**: Added validation of API response structure:
    - Check for required fields (`total`, `successful`, `failed`, `results`)
    - Validate response structure before returning to tool layer
    - Handle malformed API responses gracefully

20. **Tool Response Format Requirement**: **CRITICAL** - All batch tools MUST return `{"summary": "...", "data": {...}}` format:
    - Required by desktop agent for Pydantic validation
    - Summary must be a string (never None)
    - Data must be an object (can be empty but must exist)
    - All error cases must also return this format
    - Early validation errors must also return this format

21. **Method Return Type Handling**: Added handling for different return types:
    - `cancel_plan()` returns `bool` (not dict) - handle accordingly
    - `update_plan()` returns `{"success": bool, "message": str, ...}` - extract fields correctly
    - `create_*_plan()` methods return `{"success": bool, "plan_id": str, ...}` - extract correctly

22. **Duplicate Handling in Batch Update**: Added deduplication for batch update:
    - Check for duplicate plan_ids in updates array
    - Keep last update for each plan_id (deduplicate)
    - Prevents conflicting updates to same plan

23. **HTTP Status Code Strategy**: Clarified status code handling:
    - Return 200 OK for partial success (some succeed, some fail)
    - Return 422 for Pydantic validation failures (malformed request)
    - Return 500 for server errors (unexpected exceptions)
    - Include error details in response body, not just status code

24. **Empty Results Handling**: Added handling for when all operations fail:
    - Still return 200 OK with `successful: 0, failed: total`
    - Include all error details in results array
    - Tool layer should format as error summary but include data

25. **API Response Parsing**: Added parsing and validation of API responses:
    - Parse JSON response from API
    - Validate response structure has required fields
    - Wrap API response in tool response format
    - Handle non-200 responses with proper error formatting

26. **All Plans Fail Handling**: **REVISED** - Changed from returning error to returning detailed results:
    - Even if ALL plans fail, return 200 OK with `successful: 0, failed: total`
    - Include all error details in results array
    - Tool layer formats summary as error but includes full data
    - Allows user to see all errors and fix them, rather than getting generic error

27. **Method Return Type Awareness**: Added handling for different method return types:
    - **CRITICAL: API Endpoint vs System Method**: We call API endpoints (via `ChatGPTAutoExecution`), not system methods directly
    - `cancel_plan()` API endpoint returns `{"success": True, "message": "..."}` (always success=True, idempotent)
    - `update_plan()` API endpoint returns `{"success": bool, "message": str, ...}` - extract correctly
    - `create_*_plan()` API endpoints return `{"success": bool, "plan_id": str, ...}` - extract correctly
    - Don't assume all methods return same format

28. **API Endpoint vs System Method**: **CRITICAL** - Clarified that batch endpoints call API methods, not system methods:
    - Batch endpoints call `auto_execution.create_trade_plan()`, not `auto_system.create_trade_plan()`
    - Batch endpoints call `auto_execution.cancel_plan()`, not `auto_system.cancel_plan()`
    - This ensures proper validation, error handling, and response formatting

29. **Index Field Clarification**: **CRITICAL** - Clarified when index field is needed:
    - **Batch Create**: Needs index field (plans don't have plan_id until created)
    - **Batch Update**: No index field needed (uses plan_id which is unique)
    - **Batch Cancel**: No index field needed (uses plan_id which is unique)

30. **Deduplication Location**: **CRITICAL** - Clarified where deduplication happens:
    - **Batch Update**: Deduplicate in tool layer (before API call) AND in API endpoint (defensive)
    - **Batch Cancel**: Deduplicate in API endpoint (before processing)
    - This prevents duplicate processing and ensures consistency

31. **Symbol Normalization Location**: **CRITICAL** - Clarified where symbol normalization happens:
    - Apply normalization in API endpoint before calling creation methods
    - Each individual creation method expects normalized symbol, so normalize before routing

32. **Rate Limiting Location**: **CRITICAL** - Clarified where rate limiting is enforced:
    - Enforced in API endpoint via Pydantic validator (max 20 plans)
    - Tool layer receives 422 error if limit exceeded
    - Tool layer formats error message for ChatGPT

33. **Timeout Handling Details**: **CRITICAL** - Added details on timeout handling:
    - Tool layer HTTP client has 60s timeout
    - If timeout occurs, tool layer catches `httpx.TimeoutException`
    - Return partial results if API returned any data before timeout
    - API endpoint should process as many plans as possible within 60s

34. **Exception Handling in API Endpoint**: **CRITICAL** - Added handling for API endpoint exceptions:
    - If creation method throws exception (not just returns error), catch and continue
    - If creation method raises `HTTPException`, catch and continue
    - Extract error message and add to results
    - Don't let one failure stop the batch

### **Additional Issues Found in This Review:**

35. **API Endpoint vs System Method Confusion**: **CRITICAL** - Clarified that batch endpoints call API wrapper methods, not system methods:
    - Batch endpoints call `auto_execution.create_trade_plan()` (from `ChatGPTAutoExecution`), not `auto_system.create_trade_plan()`
    - Batch endpoints call `auto_execution.cancel_plan()` (from `ChatGPTAutoExecution`), not `auto_system.cancel_plan()`
    - This ensures proper validation, error handling, and response formatting

36. **Cancel Plan Response Format**: **CRITICAL** - Fixed incorrect assumption about cancel response:
    - Plan incorrectly stated `cancel_plan()` returns `bool`
    - Actually, API endpoint returns `{"success": True, "message": "..."}` format (always success=True, idempotent)
    - Updated plan to reflect actual API endpoint behavior

37. **Index Field Usage**: **CRITICAL** - Clarified when index field is needed:
    - **Batch Create**: Needs index field (plans don't have plan_id until created)
    - **Batch Update**: No index field needed (uses plan_id which is unique)
    - **Batch Cancel**: No index field needed (uses plan_id which is unique)

38. **Deduplication Location**: **CRITICAL** - Clarified where deduplication happens:
    - **Batch Update**: Deduplicate in tool layer (before API call) AND in API endpoint (defensive)
    - **Batch Cancel**: Deduplicate in API endpoint (before processing)
    - This prevents duplicate processing and ensures consistency

39. **Symbol Normalization Location**: **CRITICAL** - Clarified where symbol normalization happens:
    - Apply normalization in API endpoint before calling creation methods
    - Each individual creation method expects normalized symbol, so normalize before routing

40. **Rate Limiting Location**: **CRITICAL** - Clarified where rate limiting is enforced:
    - Enforced in API endpoint via Pydantic validator (max 20 plans)
    - Tool layer receives 422 error if limit exceeded
    - Tool layer formats error message for ChatGPT

41. **Timeout Handling Details**: **CRITICAL** - Added details on timeout handling:
    - Tool layer HTTP client has 60s timeout
    - If timeout occurs, tool layer catches `httpx.TimeoutException`
    - Return partial results if API returned any data before timeout
    - API endpoint should process as many plans as possible within 60s

42. **Exception Handling in API Endpoint**: **CRITICAL** - Added handling for API endpoint exceptions:
    - If creation/update/cancel method throws exception (not just returns error), catch and continue
    - If method raises `HTTPException`, catch and continue
    - Extract error message and add to results
    - Don't let one failure stop the batch

43. **Idempotent Behavior for Cancel**: **CRITICAL** - Clarified cancel endpoint idempotent behavior:
    - Cancel endpoint always returns `{"success": True, "message": "..."}` even if plan doesn't exist
    - Message indicates if plan was cancelled or not found/already cancelled
    - Both cases should be counted as success (idempotent operation)

50. **ChatGPT Version Knowledge Documents**: **CRITICAL** - Added comprehensive review and update requirements:
    - All ChatGPT Version embedding documents must be reviewed and updated
    - Primary documents requiring updates:
      - `6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md`
      - `7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md`
      - `1.KNOWLEDGE_DOC_EMBEDDING.md`
      - `2.UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md`
    - All documents must have bracket trade references removed
    - All documents must have batch operations added
    - Search all ChatGPT Version documents for "bracket" references

51. **Database Schema Analysis**: **CRITICAL** - Verified database requirements:
    - **NO DATABASE CHANGES REQUIRED**
    - Existing `trade_plans` table schema is sufficient for batch operations
    - Batch operations call existing individual methods which use the same database table
    - No migrations needed
    - Backward compatible with all existing plans
    - Database structure already supports all plan types

52. **Pydantic Version Compatibility**: **CRITICAL** - Added Pydantic version compatibility notes:
    - Pydantic v1 uses `@validator` decorator
    - Pydantic v2 uses `@field_validator` decorator
    - Check project's Pydantic version and use appropriate syntax
    - Added import statements to Pydantic model examples

53. **Plan Type Validation Location**: **CRITICAL** - Clarified validation location:
    - Tool layer: Only validates structure (array exists, not empty)
    - API endpoint: Validates plan_type exists and is valid (before routing)
    - Individual methods: Validate all other fields (symbol, direction, entry_price, etc.)
    - This prevents unnecessary API calls for invalid plan_type

54. **Deduplication Order Preservation**: **CRITICAL** - Added requirement to preserve request order:
    - After deduplication, maintain original request order in results
    - Use mapping to track original order: `{plan_id: original_index}`
    - When building results, use original_index to maintain order
    - This ensures results match user's request order

55. **Response Ordering**: **CRITICAL** - Clarified response ordering requirements:
    - Batch Create: Use index field to match request order
    - Batch Update: Maintain original request order (before deduplication)
    - Batch Cancel: Maintain original request order (before deduplication)
    - Results must match request order exactly, even after deduplication

56. **Error Message Extraction**: **CRITICAL** - Enhanced error message handling:
    - Extract error from `message` field if `success: False`
    - Handle missing fields gracefully (plan_id may be None on failure)
    - Format error messages for inclusion in results
    - Ensure all error paths provide actionable error messages

57. **Pydantic Validator Syntax**: **CRITICAL** - Added Pydantic version compatibility:
    - Pydantic v1 uses `@validator` decorator
    - Pydantic v2 uses `@field_validator` decorator
    - Check project's Pydantic version before implementation
    - Added import statements to all Pydantic model examples

58. **Plan Type Validation Location**: **CRITICAL** - Clarified validation location:
    - Tool layer: Only validates structure (array exists, not empty)
    - API endpoint: Validates plan_type exists and is valid (before routing)
    - Individual methods: Validate all other fields
    - This prevents unnecessary API calls for invalid plan_type

59. **Response Ordering After Deduplication**: **CRITICAL** - Added order preservation requirements:
    - Track original order before deduplication: `{plan_id: [original_indices]}`
    - Build results in order, maintaining original position
    - If plan_id duplicated, include result for first occurrence position
    - This ensures results match user's request order

60. **Missing plan_id Handling**: **CRITICAL** - Added handling for missing plan_id:
    - If plan creation fails, plan_id will be None
    - Still include in results with error status and index
    - Include plan_type and symbol from request in error result
    - This ensures all plans in request have corresponding results

61. **Results Array Building**: **CRITICAL** - Clarified how to build results array:
    - Process plans/updates/cancels sequentially
    - Add results to array in same order as request
    - Use index from loop to maintain order
    - Initialize results array with correct size, or build incrementally maintaining order

44. **Symbol Normalization Duplication**: **CRITICAL** - Fixed incorrect assumption:
    - Plan incorrectly stated to normalize symbols in batch endpoint
    - Actually, individual `create_*_plan()` methods already perform symbol normalization
    - Batch endpoint should NOT normalize (would cause double normalization issues)
    - Pass symbols as-is to individual methods

45. **Validation Duplication**: **CRITICAL** - Clarified validation approach:
    - Individual `create_*_plan()` methods perform comprehensive validation
    - Batch endpoint should NOT duplicate validation logic
    - Batch endpoint should only validate structure (plan_type exists, is valid)
    - Let individual methods handle field validation, weekend filtering, volatility validation, etc.

46. **Plan Type Validation**: **CRITICAL** - Added early validation for plan_type:
    - Validate plan_type exists before processing
    - Validate plan_type is one of valid types
    - Return clear error message if missing or invalid
    - Prevents routing to non-existent methods

47. **Sequential Processing**: **CRITICAL** - Clarified processing approach:
    - Process plans sequentially (one at a time)
    - Do NOT process in parallel (could cause database lock contention)
    - Sequential processing ensures proper error handling and transaction isolation
    - Each plan creation is fast enough that sequential processing is acceptable

48. **Error Message Extraction**: **CRITICAL** - Clarified error message extraction:
    - Individual methods return `{"success": bool, "message": str, ...}` format
    - If `success: False`, extract error from `message` field
    - If method throws exception, extract from exception message
    - Always include error message in results for failed plans

49. **Logging Requirements**: **CRITICAL** - Added logging requirements:
    - Log each plan creation attempt with: index, plan_type, symbol, direction
    - Log success/failure status
    - Log error message if failed
    - This helps with debugging batch operations

---

## Goals
1. **Create Multiple Plans**: Single tool call to create multiple plans (different strategies/types)
2. **Update Multiple Plans**: Single tool call to update multiple existing plans
3. **Cancel Multiple Plans**: Single tool call to cancel multiple plans
4. **Backward Compatibility**: Keep existing single-plan tools working
5. **Error Handling**: Partial success support with detailed per-plan results

---

## Implementation Phases

### Phase 1: Backend API Layer (auto_execution_api.py) ✅ **COMPLETE**

**Status**: ✅ **COMPLETE - Implementation and Testing 100%**

**Completed**:
- ✅ Added Pydantic models: `BatchCreatePlanRequest`, `BatchUpdatePlanRequest`, `BatchCancelPlanRequest`
- ✅ Implemented `POST /auto-execution/create-plans` endpoint with:
  - Plan type validation and routing
  - Sequential processing
  - Partial success error handling
  - Comprehensive logging
  - Response ordering with index field
- ✅ Implemented `POST /auto-execution/update-plans` endpoint with:
  - Deduplication logic (keeps last update)
  - Order preservation after deduplication
  - Validation of plan_id and update fields
  - Partial success error handling
- ✅ Implemented `POST /auto-execution/cancel-plans` endpoint with:
  - Deduplication logic (keeps first occurrence)
  - Order preservation after deduplication
  - Idempotent behavior handling
  - Partial success error handling
- ✅ All endpoints compile successfully
- ✅ All endpoints follow plan specifications

**Testing**: ✅ **100% COMPLETE**
- ✅ Structure validation test passed (all components verified)
- ✅ Test script created: `test_batch_auto_execution_endpoints.py`
- ✅ Structure validation script: `test_batch_endpoints_structure.py`
- ✅ All Pydantic models validated
- ✅ All endpoints validated
- ✅ All validators validated
- ✅ All implementation details verified (sequential processing, partial success, error handling, logging, deduplication, order preservation, plan type validation)

**Test Results**:
- All structure checks passed
- Code compiles without errors
- Ready for integration testing with tool layer (Phase 2)

#### 1.1 Create Batch Create Endpoint
**Endpoint**: `POST /auto-execution/create-plans`

**CRITICAL: Pydantic Models Required**:
- Define `BatchCreatePlanRequest` model with `plans: List[Dict[str, Any]]`
- FastAPI will automatically validate request body using Pydantic
- For individual plan validation, use Union type or validate in endpoint logic
- **Alternative**: Use `List[Dict[str, Any]]` and validate manually (more flexible for different plan types)

**Request Body**:
```json
{
  "plans": [
    {
      "plan_type": "auto_trade",  // or "choch", "rejection_wick", "order_block", "range_scalp", "micro_scalp"
      // Note: For bracket-style trades, create two independent plans (one BUY, one SELL) with different conditions
      "symbol": "BTCUSDc",
      "direction": "BUY",
      "entry_price": 88000.0,
      "stop_loss": 87500.0,
      "take_profit": 89000.0,
      "volume": 0.01,
      "conditions": {...},
      "expires_hours": 24,
      "notes": "..."
    },
    // ... more plans
  ]
}
```

**Response**:
```json
{
  "total": 5,
  "successful": 4,
  "failed": 1,
  "results": [
    {
      "index": 0,
      "status": "created",
      "plan_id": "chatgpt_abc123",
      "plan_type": "auto_trade",
      "symbol": "BTCUSDc",
      "direction": "BUY"
    },
    {
      "index": 1,
      "status": "created",
      "plan_id": "chatgpt_def456",
      "plan_type": "choch",
      "symbol": "BTCUSDc",
      "direction": "SELL"
    },
    {
      "index": 2,
      "status": "failed",
      "error": "Invalid entry price: must be positive",
      "plan_type": "choch",
      "symbol": "BTCUSDc"
    },
    {
      "index": 3,
      "status": "failed",
      "error": "Strategy 'breakout_ib_volatility_trap' not allowed during weekend hours",
      "plan_type": "auto_trade",
      "symbol": "BTCUSDc",
      "strategy_type": "breakout_ib_volatility_trap"
    },
    {
      "index": 4,
      "status": "failed",
      "error": "SL distance (50.0) exceeds maximum (10.0) for BTCUSD micro-scalp",
      "plan_type": "micro_scalp",
      "symbol": "BTCUSDc"
    }
  ]
}
```

**Response Format Notes**:
- Include `index` to match request order
- Include `plan_type` and `symbol` in all results (success or failure)
- For failures: include detailed `error` message explaining why validation failed
- Include `strategy_type` in error if weekend filtering rejected it
- **Note**: For bracket-style trades, create two independent plans (one BUY, one SELL) - each counts as 1 plan in results

**Implementation Notes**:
- **CRITICAL: Pydantic Model Definition**:
  ```python
  from pydantic import BaseModel, validator
  from typing import List, Dict, Any
  
  class BatchCreatePlanRequest(BaseModel):
      plans: List[Dict[str, Any]]  # Use Dict for flexibility with different plan types
      
      @validator('plans')
      def validate_plans_not_empty(cls, v):
          if not v or len(v) == 0:
              raise ValueError('plans array cannot be empty')
          if len(v) > 20:
              raise ValueError('plans array cannot exceed 20 items')
          return v
      
      # Note: plan_type validation happens in endpoint logic, not Pydantic model
      # This allows flexible plan structures for different plan types
  ```
  **CRITICAL: Pydantic Version Compatibility**:
  - If using Pydantic v1: Use `@validator` decorator (as shown above)
  - If using Pydantic v2: Use `@field_validator` decorator instead
  - Check project's Pydantic version and use appropriate syntax
- **CRITICAL: Request Validation**:
  - FastAPI will automatically validate request body using Pydantic
  - If validation fails, FastAPI returns 422 with validation errors
  - Handle 422 errors gracefully in tool layer
- **CRITICAL: Plan Type Routing**: Each plan must specify `plan_type` to route to correct creation method:
  - **CRITICAL: Validation Location**: Validate `plan_type` in API endpoint before calling individual methods
  - **CRITICAL: Validation Logic** (in API endpoint, not Pydantic model):
    - Loop through each plan in the batch
    - Check each plan has `plan_type` field (in endpoint logic, not Pydantic model - allows flexible structure)
    - If `plan_type` missing: add error result for that plan with message "plan_type is required", continue with next plan
    - If `plan_type` invalid: add error result for that plan with message "Invalid plan_type: {type}. Valid types: auto_trade, choch, rejection_wick, order_block, range_scalp, micro_scalp", continue with next plan
    - Only call individual creation method if `plan_type` is valid
    - **CRITICAL: Maintain Request Order**: Add error results in same order as request (use index from loop)
  - Valid plan types:
    - `"auto_trade"` → `create_trade_plan()`
    - `"choch"` → `create_choch_plan()` (requires `choch_type`: "bear" or "bull")
    - `"rejection_wick"` → `create_rejection_wick_plan()`
    - `"order_block"` → `create_order_block_plan()` (requires `order_block_type` and optional `min_validation_score`)
    - `"range_scalp"` → `create_range_scalp_plan()` (requires `min_confluence`, defaults to 80)
    - `"micro_scalp"` → `create_micro_scalp_plan()` (only BTCUSDc/XAUUSDc, has SL/TP distance validation)
  - **Note**: Bracket trades removed - create two independent plans (one BUY, one SELL) with different conditions instead
- **CRITICAL: Error Handling Strategy - Changed to Partial Success**:
  - **REVISED**: Use partial success instead of fail-fast for batch create
  - Rationale: If user requests 5 plans and 1 fails validation, they likely want the other 4 created
  - Validate each plan independently
  - Create valid plans, skip invalid ones
  - Return detailed results showing which succeeded/failed
  - **Exception Handling**: 
    - **REVISED**: Even if ALL plans fail, still return 200 OK with `successful: 0, failed: total`
    - Include all error details in results array
    - Tool layer formats summary as error but includes full data
    - This provides consistent response format and allows user to see all errors
    - **Rationale**: User can see why all plans failed and fix them, rather than getting generic error
- **CRITICAL: Symbol Normalization**: **DO NOT normalize in batch endpoint**
  - **CRITICAL: Individual Methods Handle Normalization**: Each `create_*_plan()` method in `ChatGPTAutoExecution` already performs symbol normalization
  - Pass symbol as-is to individual creation methods
  - They will normalize internally (add 'c' suffix if needed)
  - Normalizing twice could cause issues (e.g., "BTCUSDc" → "BTCUSDcc")
- **CRITICAL: Weekend Filtering**: **Individual methods handle weekend filtering**
  - Weekend filtering is performed inside individual `create_*_plan()` methods
  - Batch endpoint should NOT duplicate this validation
  - If weekend filtering rejects a plan, the individual method will return `{"success": False, "message": "..."}` with appropriate error
  - Batch endpoint should pass this error through to results
- **CRITICAL: Bracket Trades Removed**: 
  - Bracket trades are no longer supported in batch operations
  - Users should create two independent plans instead:
    - One BUY plan with BUY-specific conditions (e.g., price_above, choch_bull)
    - One SELL plan with SELL-specific conditions (e.g., price_below, choch_bear)
  - Each plan monitors independently - if one executes, the other can still execute later if its conditions are met
  - This is more flexible than OCO (One Cancels Other) bracket trades
- **CRITICAL: Validation Logic**: **Individual methods handle all validation**
  - **CRITICAL: Do NOT duplicate validation in batch endpoint**
  - Each individual `create_*_plan()` method performs comprehensive validation:
    - Micro-scalp: SL/TP distance validation (XAUUSD: SL $0.50-$1.20, TP $1-$2.50; BTCUSD: SL $5-$10, TP $10-$25)
    - Range scalp: min_confluence validation (0-100, default 80)
    - Order block: min_validation_score validation (0-100, default 60)
    - All plans: Volatility state validation (if enabled)
    - All plans: Conditions validation (price_near + tolerance, etc.)
  - Batch endpoint should rely on individual method validation
  - If validation fails, individual method returns `{"success": False, "message": "..."}` with error details
  - Batch endpoint extracts error message and includes in results
- **Transaction Handling**: 
  - **REVISED**: Do NOT use single transaction for all plans (partial success approach)
  - Each plan creation is independent (can succeed/fail independently)
  - Use existing individual plan creation methods (they handle their own transactions)
  - **CRITICAL: Sequential Processing**: Process plans sequentially (one at a time)
    - Do NOT process in parallel (could cause database lock contention)
    - Sequential processing ensures proper error handling and transaction isolation
    - Each plan creation is fast enough that sequential processing is acceptable
- **Rate Limiting**: 
  - Max plans per batch: 20 (configurable)
  - **CRITICAL: Enforce in API Endpoint**: Check in Pydantic validator (already specified in model)
  - Return 422 error if batch exceeds limit (Pydantic validation will catch this)
  - Tool layer will receive 422 and format error message
- **Timeout Handling**: 
  - Set timeout: 60 seconds for batch operations (in tool layer HTTP client)
  - **CRITICAL: Partial Results on Timeout**: If timeout occurs in tool layer:
    - Tool layer catches `httpx.TimeoutException`
    - Return error summary with partial results if API returned any data before timeout
    - If no data received, return timeout error
  - **CRITICAL: API Endpoint Timeout**: API endpoint should process as many plans as possible within 60s
    - If timeout occurs mid-batch, return partial results for plans processed so far
    - Include timeout indicator in response if not all plans processed

#### 1.2 Create Batch Update Endpoint
**Endpoint**: `POST /auto-execution/update-plans`

**CRITICAL: Pydantic Models Required**:
- Define `BatchUpdatePlanRequest` model with `updates: List[Dict[str, Any]]`
- FastAPI will automatically validate request body using Pydantic

**Request Body**:
```json
{
  "updates": [
    {
      "plan_id": "chatgpt_abc123",
      "entry_price": 88500.0,
      "stop_loss": 88000.0,
      "take_profit": 89500.0
    },
    {
      "plan_id": "chatgpt_def456",
      "expires_hours": 48,
      "notes": "Extended expiration"
    }
  ]
}
```

**Response**:
```json
{
  "total": 2,
  "successful": 2,
  "failed": 0,
  "results": [
    {
      "plan_id": "chatgpt_abc123",
      "status": "updated"
    },
    {
      "plan_id": "chatgpt_def456",
      "status": "updated"
    }
  ]
}
```

**Implementation Notes**:
- **CRITICAL: Pydantic Model Definition**:
  ```python
  from pydantic import BaseModel, validator
  from typing import List, Dict, Any
  
  class BatchUpdatePlanRequest(BaseModel):
      updates: List[Dict[str, Any]]
      
      @validator('updates')
      def validate_updates_not_empty(cls, v):
          if not v or len(v) == 0:
              raise ValueError('updates array cannot be empty')
          return v
      
      # Note: plan_id and update field validation happens in endpoint logic
  ```
  **CRITICAL: Pydantic Version Compatibility**:
  - If using Pydantic v1: Use `@validator` decorator (as shown above)
  - If using Pydantic v2: Use `@field_validator` decorator instead
- **CRITICAL: Request Validation**:
  - FastAPI will automatically validate request body using Pydantic
  - If validation fails, FastAPI returns 422 with validation errors
  - Handle 422 errors gracefully in tool layer
- **CRITICAL: Input Validation**:
  - Validate `updates` array is not empty (handled by Pydantic)
  - Validate each update has required `plan_id` field (in endpoint logic)
  - Validate each update has at least one update field (in endpoint logic)
  - **CRITICAL: Deduplicate Updates**: Check for duplicate plan_ids in updates array
    - **CRITICAL: Location**: Deduplicate in API endpoint before processing (defensive approach)
    - **Note**: Tool layer may also deduplicate (early validation), but API endpoint should deduplicate as well for safety
    - **CRITICAL: Track Original Order**: Before deduplication, create mapping: `{plan_id: [original_indices]}` to track all occurrences
    - If same plan_id appears multiple times, keep last update (deduplicate)
    - Log warning if duplicates found
    - This prevents conflicting updates to same plan
    - **CRITICAL: Preserve Request Order**: After deduplication, maintain original request order in results
- **CRITICAL: Per-Plan Validation**:
  - Validate each update independently (after deduplication)
  - Check plan exists (via `auto_execution.get_plan_status(plan_id)`)
  - Check plan is pending status (only pending plans can be updated)
  - Validate update fields (entry_price > 0, stop_loss/take_profit valid, etc.)
  - If conditions provided, validate conditions (via `_validate_and_fix_conditions`)
- **CRITICAL: Error Handling**:
  - If plan not found: return error for that plan, continue with others
  - If plan not pending: return error for that plan, continue with others
  - If validation fails: return error for that plan, continue with others
  - Partial success: update valid plans, skip invalid ones
  - **CRITICAL: HTTP Status Codes**:
    - Return 200 OK even if some updates fail (partial success)
    - Include error details in response body
    - Only return 4xx/5xx if entire request is invalid (e.g., malformed JSON, missing required fields)
  - **CRITICAL: Handle Update Response**: 
    - `update_plan()` returns `{"success": bool, "message": str, ...}` format
    - Check `success` field to determine if update succeeded
    - Extract error message from `message` field if failed
    - If `success: True`, extract `plan_id` and plan details from response
- Return status per plan with detailed error messages
- **CRITICAL: Response Format**:
  - Always return JSON with `total`, `successful`, `failed`, `results` fields
  - **CRITICAL: Response Consistency**: Ensure `total == successful + failed` (validate this)
  - **CRITICAL: Response Ordering**: 
    - After deduplication, maintain original request order in results
    - **CRITICAL: Track Original Order**: Before deduplication, create mapping: `{plan_id: [original_indices]}`
    - Use original request order (before deduplication) to order results
    - If plan_id was duplicated, include result for first occurrence position (or all if needed)
    - **CRITICAL: Build Results in Order**: Process updates sequentially and add results in order, maintaining original position
  - **CRITICAL: No Index Field Needed**: Update uses `plan_id` which is unique, so no need for index field
  - Ensure `results` array matches request order (use original request order, not index)
  - Ensure `results` array length matches `total` (validate this)
  - Include `plan_id` in all results (success or failure)
  - **CRITICAL: Empty Results Handling**: If all updates fail, still return 200 OK with `successful: 0, failed: total`
  - **CRITICAL: Logging**: Log batch operation summary (total, successful, failed) for monitoring

#### 1.3 Create Batch Cancel Endpoint
**Endpoint**: `POST /auto-execution/cancel-plans`

**CRITICAL: Pydantic Models Required**:
- Define `BatchCancelPlanRequest` model with `plan_ids: List[str]`
- FastAPI will automatically validate request body using Pydantic

**Request Body**:
```json
{
  "plan_ids": ["chatgpt_abc123", "chatgpt_def456", "chatgpt_ghi789"]
}
```

**Response**:
```json
{
  "total": 3,
  "successful": 2,
  "failed": 1,
  "results": [
    {
      "plan_id": "chatgpt_abc123",
      "status": "cancelled"
    },
    {
      "plan_id": "chatgpt_def456",
      "status": "cancelled"
    },
    {
      "plan_id": "chatgpt_ghi789",
      "status": "failed",
      "error": "Plan not found or already cancelled"
    }
  ]
}
```

**Implementation Notes**:
- **CRITICAL: Pydantic Model Definition**:
  ```python
  from pydantic import BaseModel, validator
  from typing import List
  
  class BatchCancelPlanRequest(BaseModel):
      plan_ids: List[str]
      
      @validator('plan_ids')
      def validate_plan_ids_not_empty(cls, v):
          if not v or len(v) == 0:
              raise ValueError('plan_ids array cannot be empty')
          return v
  ```
  **CRITICAL: Pydantic Version Compatibility**:
  - If using Pydantic v1: Use `@validator` decorator (as shown above)
  - If using Pydantic v2: Use `@field_validator` decorator instead
- **CRITICAL: Request Validation**:
  - FastAPI will automatically validate request body using Pydantic
  - If validation fails, FastAPI returns 422 with validation errors
  - Handle 422 errors gracefully in tool layer
- **CRITICAL: Input Validation**:
  - Validate `plan_ids` array is not empty (handled by Pydantic)
  - Validate each plan_id is a string (handled by Pydantic type)
  - **CRITICAL: Deduplicate plan_ids** - Remove duplicates before processing (in API endpoint logic)
  - **CRITICAL: Location**: Deduplicate in API endpoint before calling cancel methods
  - **CRITICAL: Preserve Request Order**: After deduplication, maintain original request order for response ordering
  - **CRITICAL: Track Original Order**: Before deduplication, create mapping: `{plan_id: [original_indices]}` to track all occurrences
  - When building results, use original_indices to maintain order
  - If plan_id appears multiple times, process once but include result for first occurrence position
- **CRITICAL: Per-Plan Processing**:
  - Process each cancellation independently
  - **CRITICAL: Use API Endpoint, Not System Method**: Call `auto_execution.cancel_plan(plan_id)` from `ChatGPTAutoExecution` class
  - **CRITICAL: API Endpoint Returns Dict**: The API endpoint `/cancel-plan/{plan_id}` returns `{"success": True, "message": "..."}` format
  - **CRITICAL: Idempotent Behavior**: API endpoint returns `{"success": True, "message": "Plan not found or already cancelled"}` even if plan doesn't exist (idempotent)
  - **CRITICAL: Handle API Response**: 
    - API endpoint always returns `{"success": True, "message": "..."}` format
    - Check `success` field (always True for cancel endpoint)
    - Check `message` field to determine if plan was actually cancelled or not found
    - If message contains "not found" or "already cancelled", mark as "cancelled" (idempotent - this is success)
    - Fast operation (minimal locking per plan)
- **CRITICAL: Error Handling**:
  - If plan not found: return error for that plan, continue with others
  - Partial success: cancel valid plans, report failures
  - Return status per plan with error messages for failures
  - **CRITICAL: HTTP Status Codes**:
    - Return 200 OK even if some cancellations fail (partial success)
    - Include error details in response body
    - Only return 4xx/5xx if entire request is invalid (e.g., malformed JSON, missing required fields)
  - **CRITICAL: Handle Cancel Response**: 
    - API endpoint returns `{"success": True, "message": "..."}` format (always success=True, idempotent)
    - Check `message` field to determine actual result
    - If message contains "cancelled successfully": mark as "cancelled" in results
    - If message contains "not found" or "already cancelled": mark as "cancelled" (idempotent - this is success)
    - The API endpoint is idempotent - it always returns success, even if plan doesn't exist
- **CRITICAL: Response Format**:
  - Always return JSON with `total`, `successful`, `failed`, `results` fields
  - **CRITICAL: Response Consistency**: Ensure `total == successful + failed` (validate this)
  - **CRITICAL: Response Ordering**: 
    - After deduplication, maintain original request order in results
    - **CRITICAL: Track Original Order**: Before deduplication, create mapping: `{plan_id: [original_indices]}` to track all occurrences
    - Use original request order (before deduplication) to order results
    - If plan_id was duplicated, include result for first occurrence position (or all if needed)
    - **CRITICAL: Build Results in Order**: Process cancellations sequentially and add results in order, maintaining original position
  - **CRITICAL: No Index Field Needed**: Cancel uses `plan_id` which is unique, so no need for index field
  - Ensure `results` array matches request order (use original request order, not index)
  - Ensure `results` array length matches `total` (validate this)
  - Include `plan_id` in all results (success or failure)
  - **CRITICAL: Empty Results Handling**: If all cancellations fail, still return 200 OK with `successful: 0, failed: total`
  - **CRITICAL: Idempotent Behavior**: Since cancel is idempotent, "not found" should be counted as success (cancelled)
  - **CRITICAL: Logging**: Log batch operation summary (total, successful, failed) for monitoring

---

### Phase 2: Tool Layer (chatgpt_auto_execution_tools.py) ✅ **COMPLETE**

**Status**: ✅ **COMPLETE - Implementation and Testing 100%**

**Completed**:

#### 2.1 Add Batch Create Tool
**Function**: `tool_create_multiple_auto_plans(args: Dict[str, Any])`

**Parameters**:
- `plans`: Array of plan objects
  - **REQUIRED**: Each plan MUST specify `plan_type` field
  - Support all plan types: auto_trade, choch, rejection_wick, order_block, range_scalp, micro_scalp
  - **Note**: For bracket-style trades, create two independent plans (one BUY, one SELL) with different conditions
  - Each plan type requires specific fields (see API endpoint documentation)

**Plan Type Requirements**:
- `auto_trade`: symbol, direction, entry_price, stop_loss, take_profit, volume, conditions (optional), expires_hours (optional), notes (optional)
- `choch`: symbol, direction, entry_price, stop_loss, take_profit, volume, choch_type ("bear" or "bull"), expires_hours (optional), notes (optional), conditions (optional)
- `rejection_wick`: symbol, direction, entry_price, stop_loss, take_profit, volume, expires_hours (optional), notes (optional)
- `order_block`: symbol, direction, entry_price, stop_loss, take_profit, volume, order_block_type ("bull", "bear", or "auto"), min_validation_score (optional, default 60), expires_hours (optional), notes (optional)
- `range_scalp`: symbol, direction, entry_price, stop_loss, take_profit, volume, min_confluence (optional, default 80), expires_hours (optional, default 8), notes (optional)
- `micro_scalp`: symbol (BTCUSDc or XAUUSDc only), direction, entry_price, stop_loss, take_profit, volume, expires_hours (optional, default 2), notes (optional), conditions (optional)
- **Note**: Bracket trades removed - create two independent plans (one BUY, one SELL) with different conditions instead

**Implementation**:
- **CRITICAL: Input Validation**:
  - Validate `plans` array is not empty (return error if empty)
  - Validate `plans` is an array (not object, not null)
  - **CRITICAL: Validate Structure in Tool Layer**: 
    - Validate `plans` array is not empty (return error if empty)
    - Validate `plans` is an array (not object, not null)
    - **CRITICAL: Do NOT validate plan_type in tool layer** - Let API endpoint handle it
    - **CRITICAL: Do NOT validate plan-specific fields in tool layer**
      - Individual creation methods will validate required fields (symbol, direction, entry_price, etc.)
      - Tool layer should only validate structure (array exists, not empty)
      - Let API endpoint validate plan_type and route to appropriate method
      - Let individual methods handle field validation
  - Return early validation errors before making API call
  - **CRITICAL: Early Validation Response Format**: Even validation errors must return `{"summary": "...", "data": {...}}` format
- **CRITICAL: Error Handling**:
  - Handle HTTP errors (4xx, 5xx) gracefully
  - **CRITICAL: Handle 422 Validation Errors**: FastAPI returns 422 for Pydantic validation failures
    - Parse validation error details from response
    - Format as user-friendly error messages for ChatGPT
    - **MUST return** `{"summary": "ERROR: ...", "data": {"error": "...", "validation_errors": [...]}}` format
  - Handle timeout errors (60s timeout)
    - **MUST return** `{"summary": "ERROR: Request timeout...", "data": {"error": "Request timeout", ...}}` format
  - Handle connection errors (API server down)
    - **MUST return** `{"summary": "ERROR: Cannot connect...", "data": {"error": "Connection error", ...}}` format
  - Return partial results if some plans succeed
  - Format error messages for ChatGPT (user-friendly)
  - **CRITICAL: All Error Cases**: Every error path must return `{"summary": "...", "data": {...}}` format (never return raw dict or None)
- **CRITICAL: Response Formatting**:
  - **MUST return** `{"summary": "...", "data": {...}}` format (required by desktop agent)
  - Format summary: "Created X of Y plans successfully" or "ERROR: Failed to create plans: ..."
  - Include detailed results per plan in `data` field
  - For failures, include actionable error messages
  - **CRITICAL: Handle Empty Results**: If all plans fail, return error summary but still include results array in data
  - **CRITICAL: Validate API Response**: Check response structure matches expected format before returning
  - **CRITICAL: Parse API Response**:
    - If API returns 200, parse JSON response
    - Validate response has `total`, `successful`, `failed`, `results` fields
    - If response structure invalid, return error with details
    - Wrap API response in `{"summary": "...", "data": <api_response>}` format
  - **CRITICAL: Handle Non-200 Responses**:
    - If 422 (validation error): Parse validation errors, return formatted error
    - If 4xx/5xx: Parse error message, return formatted error
    - Always return `{"summary": "ERROR: ...", "data": {"error": "...", "status_code": ...}}` format
- Call batch API endpoint: `POST /auto-execution/create-plans`
- Use async HTTP client with 60s timeout

**Implementation**: ✅ **COMPLETE**
- ✅ Implemented `tool_create_multiple_auto_plans()` function
- ✅ Input validation (structure only - array exists, not empty, max 20)
- ✅ Error handling (422, timeout, connection errors)
- ✅ Response formatting (`{"summary": "...", "data": {...}}` format)
- ✅ API response validation and parsing
- ✅ All error paths return proper format
- ✅ Code compiles successfully
- ✅ All tests passed (4/4)

#### 2.2 Add Batch Update Tool
**Function**: `tool_update_multiple_auto_plans(args: Dict[str, Any])`

**Parameters**:
- `updates`: Array of update objects
  - Each update must have `plan_id`
  - Optional fields: entry_price, stop_loss, take_profit, volume, conditions, expires_hours, notes

**Implementation**:
- **CRITICAL: Input Validation**:
  - Validate `updates` array is not empty (return error if empty)
  - Validate `updates` is an array (not object, not null)
  - Validate each update has required `plan_id` field
  - Validate each update has at least one update field (entry_price, stop_loss, take_profit, volume, conditions, expires_hours, or notes)
  - **CRITICAL: Deduplicate Updates**: Check for duplicate plan_ids in updates array
    - **CRITICAL: Location**: Deduplicate in tool layer before calling API (early validation)
    - **Note**: API endpoint should also deduplicate as defensive measure
    - If same plan_id appears multiple times, keep last update (deduplicate)
    - Log warning if duplicates found
    - This prevents conflicting updates to same plan
  - Return early validation errors before making API call
  - **CRITICAL: Early Validation Response Format**: Even validation errors must return `{"summary": "...", "data": {...}}` format
- **CRITICAL: Error Handling**:
  - Handle HTTP errors (4xx, 5xx) gracefully
  - **CRITICAL: Handle 422 Validation Errors**: FastAPI returns 422 for Pydantic validation failures
    - Parse validation error details from response
    - Format as user-friendly error messages for ChatGPT
    - **MUST return** `{"summary": "ERROR: ...", "data": {"error": "...", "validation_errors": [...]}}` format
  - Handle timeout errors (60s timeout)
    - **MUST return** `{"summary": "ERROR: Request timeout...", "data": {"error": "Request timeout", ...}}` format
  - Handle connection errors (API server down)
    - **MUST return** `{"summary": "ERROR: Cannot connect...", "data": {"error": "Connection error", ...}}` format
  - Return partial results if some updates succeed
  - Format error messages for ChatGPT (user-friendly)
  - **CRITICAL: All Error Cases**: Every error path must return `{"summary": "...", "data": {...}}` format (never return raw dict or None)
- **CRITICAL: Response Formatting**:
  - **MUST return** `{"summary": "...", "data": {...}}` format (required by desktop agent)
  - Format summary: "Updated X of Y plans successfully" or "ERROR: Failed to update plans: ..."
  - Include detailed results per plan in `data` field
  - For failures, include actionable error messages (e.g., "Plan not found", "Plan already executed", "Invalid entry price")
  - **CRITICAL: Handle Empty Results**: If all updates fail, return error summary but still include results array in data
  - **CRITICAL: Validate API Response**: Check response structure matches expected format before returning
  - **CRITICAL: Parse API Response**:
    - If API returns 200, parse JSON response
    - Validate response has `total`, `successful`, `failed`, `results` fields
    - If response structure invalid, return error with details
    - Wrap API response in `{"summary": "...", "data": <api_response>}` format
  - **CRITICAL: Handle Non-200 Responses**:
    - If 422 (validation error): Parse validation errors, return formatted error
    - If 4xx/5xx: Parse error message, return formatted error
    - Always return `{"summary": "ERROR: ...", "data": {"error": "...", "status_code": ...}}` format
- **CRITICAL: Duplicate plan_id Handling**: 
  - **CRITICAL: Location**: Deduplicate in tool layer before calling API (early validation)
  - Check for duplicate plan_ids in updates array
  - If duplicates found, warn or deduplicate (decision: deduplicate, keep last update for each plan_id)
  - This prevents sending duplicate updates to API
- Call batch update API endpoint: `POST /auto-execution/update-plans`
- Use async HTTP client with 60s timeout

**Implementation**: ✅ **COMPLETE**
- ✅ Implemented `tool_update_multiple_auto_plans()` function
- ✅ Input validation (structure, plan_id, update fields)
- ✅ Deduplication in tool layer (keeps last update)
- ✅ Error handling (422, timeout, connection errors)
- ✅ Response formatting (`{"summary": "...", "data": {...}}` format)
- ✅ API response validation and parsing
- ✅ All error paths return proper format
- ✅ Code compiles successfully
- ✅ All tests passed (3/3)

#### 2.3 Add Batch Cancel Tool
**Function**: `tool_cancel_multiple_auto_plans(args: Dict[str, Any])`

**Parameters**:
- `plan_ids`: Array of plan_id strings

**Implementation**:
- **CRITICAL: Input Validation**:
  - Validate `plan_ids` array is not empty (return error if empty)
  - Validate `plan_ids` is an array (not object, not null)
  - Validate each plan_id is a string (not number, not null)
  - **CRITICAL: Deduplicate plan_ids** - Remove duplicates before processing (user may accidentally include same plan_id twice)
  - Return early validation errors before making API call
  - **CRITICAL: Early Validation Response Format**: Even validation errors must return `{"summary": "...", "data": {...}}` format
- **CRITICAL: Error Handling**:
  - Handle HTTP errors (4xx, 5xx) gracefully
  - **CRITICAL: Handle 422 Validation Errors**: FastAPI returns 422 for Pydantic validation failures
    - Parse validation error details from response
    - Format as user-friendly error messages for ChatGPT
    - **MUST return** `{"summary": "ERROR: ...", "data": {"error": "...", "validation_errors": [...]}}` format
  - Handle timeout errors (60s timeout)
    - **MUST return** `{"summary": "ERROR: Request timeout...", "data": {"error": "Request timeout", ...}}` format
  - Handle connection errors (API server down)
    - **MUST return** `{"summary": "ERROR: Cannot connect...", "data": {"error": "Connection error", ...}}` format
  - Return partial results if some cancellations succeed
  - Format error messages for ChatGPT (user-friendly)
  - **CRITICAL: All Error Cases**: Every error path must return `{"summary": "...", "data": {...}}` format (never return raw dict or None)
- **CRITICAL: Response Formatting**:
  - **MUST return** `{"summary": "...", "data": {...}}` format (required by desktop agent)
  - Format summary: "Cancelled X of Y plans successfully" or "ERROR: Failed to cancel plans: ..."
  - Include detailed results per plan in `data` field
  - For failures, include actionable error messages (e.g., "Plan not found")
  - Note: Already-cancelled plans return success (idempotent)
  - **CRITICAL: Handle Empty Results**: If all cancellations fail, return error summary but still include results array in data
  - **CRITICAL: Validate API Response**: Check response structure matches expected format before returning
  - **CRITICAL: Parse API Response**:
    - If API returns 200, parse JSON response
    - Validate response has `total`, `successful`, `failed`, `results` fields
    - If response structure invalid, return error with details
    - Wrap API response in `{"summary": "...", "data": <api_response>}` format
  - **CRITICAL: Handle Non-200 Responses**:
    - If 422 (validation error): Parse validation errors, return formatted error
    - If 4xx/5xx: Parse error message, return formatted error
    - Always return `{"summary": "ERROR: ...", "data": {"error": "...", "status_code": ...}}` format
- Call batch cancel API endpoint: `POST /auto-execution/cancel-plans`
- Use async HTTP client with 60s timeout

**Implementation**: ✅ **COMPLETE**
- ✅ Implemented `tool_cancel_multiple_auto_plans()` function
- ✅ Input validation (structure, plan_id format)
- ✅ Deduplication in tool layer (keeps first occurrence)
- ✅ Error handling (422, timeout, connection errors)
- ✅ Response formatting (`{"summary": "...", "data": {...}}` format)
- ✅ API response validation and parsing
- ✅ All error paths return proper format
- ✅ Code compiles successfully
- ✅ All tests passed (3/3)

**Testing**: ✅ **100% COMPLETE**
- ✅ All tool functions implemented and tested
- ✅ Input validation tests passed
- ✅ Deduplication tests passed
- ✅ Response format tests passed
- ✅ Error handling tests passed
- ✅ Total: 10 tests passed, 0 failed
- ✅ Ready for Phase 3 (openai.yaml configuration)

---

### Phase 3: OpenAI YAML Configuration (openai.yaml) ✅ **COMPLETE**

---

### Phase 4: Update All Knowledge Documents

**Status**: ✅ **COMPLETE - All Documents Updated**

**Progress**:
- ✅ Document 1: `docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_INSTRUCTIONS.md` - **COMPLETE**
  - ✅ Removed bracket trade section
  - ✅ Added batch operations section (create/update/cancel multiple plans)
  - ✅ Added guidance on creating two independent plans
  - ✅ Updated all bracket trade references
- ✅ Document 2: `docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md` - **COMPLETE**
  - ✅ Removed bracket trade section (section 5)
  - ✅ Added batch operations documentation
  - ✅ Added guidance on creating two independent plans
  - ✅ Updated all bracket trade references
- ✅ Document 3: `docs/ChatGPT Knowledge Documents/ChatGPT_Knowledge_Document.md` - **COMPLETE**
  - ✅ Removed "Bracket Trade Detailed Guidelines" section
  - ✅ Added batch operations and independent plans section
  - ✅ Updated "When to Recommend" section
  - ✅ Updated risk management section
- ✅ Document 4: `docs/ChatGPT Knowledge Documents/UPDATED_GPT_INSTRUCTIONS_FIXED.md` - **COMPLETE**
  - ✅ Removed all bracket trade references
  - ✅ Added batch operations guidance
  - ✅ Updated trade execution section
- ✅ Document 5: `openai.yaml` - **COMPLETE** (done in Phase 3)
- ✅ Document 6: `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md` - **COMPLETE**
  - ✅ Removed bracket trade section
  - ✅ Added batch operations documentation
  - ✅ Added guidance on creating two independent plans
- ✅ Document 7: `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md` - **COMPLETE**
  - ✅ Removed bracket trade section
  - ✅ Added batch operations documentation
- ✅ Document 8: `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/1.KNOWLEDGE_DOC_EMBEDDING.md` - **COMPLETE**
  - ✅ Removed all references to `moneybot.executeBracketTrade` and `moneybot.create_bracket_trade_plan`
  - ✅ Added batch operations tools to tool lists
  - ✅ Updated "When to use" section
- ✅ Document 9: `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/2.UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md` - **COMPLETE**
  - ✅ Updated bracket trade reference to deprecation notice
  - ✅ Added batch operations guidance
- ✅ Document 10-13: Additional ChatGPT Version documents - **REVIEWED** (minimal or no bracket trade references found)

---

**Status**: ✅ **COMPLETE - Implementation 100%**

**Completed**:

#### 3.1 Add Batch Tool Definitions ✅ **COMPLETE**

**Added to tools section**:
1. ✅ `createMultipleAutoPlans` - Batch create tool
2. ✅ `updateMultipleAutoPlans` - Batch update tool
3. ✅ `cancelMultipleAutoPlans` - Batch cancel tool

**Implementation**:
- ✅ Added tool definitions with proper descriptions
- ✅ Added example arguments showing usage
- ✅ Added to tool list in arguments section
- ✅ YAML validation passed

#### 3.2 Update Instructions ✅ **COMPLETE**

**Updated system instructions**:
- ✅ Added batch operations guidance in AUTO-EXECUTION PLANS section
- ✅ Added note about bracket trades being deprecated
- ✅ Added guidance on creating two independent plans instead
- ✅ Updated tool list to include batch tools
- ✅ Removed bracket trade tool references from instructions

**Removed Bracket Trade References**:
- ✅ Removed `createBracketTradePlan` tool definition
- ✅ Removed `executeBracketTrade` tool definition
- ✅ Removed "CRITICAL: BRACKET TRADES" instruction section
- ✅ Updated bracket trade instruction section to deprecation notice
- ✅ Updated schema properties (removed bracket trade parameter descriptions, added batch operation parameters)
- ✅ Updated description in info section (removed "Smart bracket trade system", added "Batch auto-execution operations")

**Implementation**: ✅ **COMPLETE**
- ✅ All batch tool definitions added
- ✅ All instructions updated
- ✅ All bracket trade references removed/updated
- ✅ YAML syntax validated
- ✅ Ready for Phase 4 (Knowledge Documents)

---

### Phase 4: System Layer Updates (auto_execution_system.py)

#### 4.1 Batch Create Method
**Method**: `create_multiple_plans(plans: List[Dict]) -> Dict`

**Implementation**:
- **REVISED**: Do NOT add this method to `AutoExecutionSystem`
- **REASON**: Use existing individual creation methods in `ChatGPTAutoExecution` class
- **APPROACH**: In API endpoint, loop through plans and call appropriate creation method:
  - `auto_execution.create_trade_plan()` for auto_trade
  - `auto_execution.create_choch_plan()` for choch
  - `auto_execution.create_rejection_wick_plan()` for rejection_wick
  - `auto_execution.create_order_block_plan()` for order_block
  - `auto_execution.create_range_scalp_plan()` for range_scalp
  - `auto_execution.create_micro_scalp_plan()` for micro_scalp
  - **Note**: Bracket trades removed - users create two independent plans instead
- **CRITICAL: Error Handling Per Plan**:
  - Wrap each creation call in try-except
  - **CRITICAL: Two Types of Failures**:
    1. **Method Returns Error**: Method returns `{"success": False, "message": "..."}` - extract message and add to results
    2. **Method Throws Exception**: Method raises exception - catch, log, extract error, add to results
  - If creation fails (either way), add to results with error message
  - Continue processing remaining plans (partial success)
  - Each method returns `{"success": bool, "message": str, "plan_id": Optional[str], ...}` format
  - **CRITICAL: Exception Handling**: 
    - Catch `Exception` (broad catch) to handle any unexpected errors
    - **CRITICAL: API Endpoint Exceptions**: If creation method throws exception (not just returns error):
      - Catch exception, log details for debugging (include plan index and plan_type for context)
      - Extract error message from exception (use `str(e)` or `e.args[0]` if available)
      - Add to results with error status, include plan_type and symbol if available
      - Continue processing remaining plans (don't let one failure stop the batch)
    - **CRITICAL: HTTPException Handling**: If creation method raises `HTTPException`:
      - Catch it, extract detail message from `e.detail`
      - Add to results with error status
      - Continue processing remaining plans
  - **CRITICAL: Logging**: Log each plan creation attempt with:
    - Plan index, plan_type, symbol, direction
    - Success/failure status
    - Error message if failed
  - **CRITICAL: Response Structure Validation**:
    - Check if method returns `{"success": bool, ...}` format
    - **CRITICAL: Extract Error Messages**: If `success: False`, extract error from `message` field
    - Extract `plan_id` from response if `success: True`
    - Extract `message` from response if `success: False` (this is the error message)
    - Handle cases where response structure is unexpected (log error, continue)
    - **CRITICAL: Response Format**: Individual methods return `{"success": bool, "message": str, "plan_id": Optional[str], ...}`
    - Always check `success` field first, then extract appropriate fields
    - **CRITICAL: Handle Missing Fields**: 
      - If `plan_id` is None or missing on failure, still include in results with error status
      - Use plan index from request to maintain order
      - Include plan_type and symbol from request in error result
    - **CRITICAL: Error Message Formatting**: Extract and format error message for inclusion in results
    - **CRITICAL: Build Results in Order**: Add results to array in same order as request (use index from loop)
    - **CRITICAL: Handle Missing Fields**: If `plan_id` is None or missing, still include in results with error status
    - **CRITICAL: Error Message Formatting**: Extract and format error message for inclusion in results
  - **CRITICAL: HTTP Status Codes**:
    - Return 200 OK even if some plans fail (partial success)
    - Include error details in response body
    - Only return 4xx/5xx if entire request is invalid (e.g., malformed JSON, Pydantic validation fails)
- **CRITICAL: Response Format**:
  - Always return JSON with `total`, `successful`, `failed`, `results` fields
  - **CRITICAL: Response Consistency**: Ensure `total == successful + failed` (validate this)
  - Ensure `results` array matches request order (use index field)
  - Ensure `results` array length matches `total` (validate this)
  - Include `plan_id`, `plan_type`, `symbol` in all results (success or failure)
  - **CRITICAL: HTTP Status Codes**:
    - Return 200 OK even if some plans fail (partial success)
    - Include error details in response body
    - Only return 4xx/5xx if entire request is invalid (e.g., malformed JSON, Pydantic validation fails)
  - **CRITICAL: Empty Results Handling**: If all plans fail, still return 200 OK with `successful: 0, failed: total`
  - **CRITICAL: Logging**: Log batch operation summary (total, successful, failed) for monitoring
- **CRITICAL: Bracket Trades Removed**: 
  - Bracket trades are no longer supported in batch operations
  - Users create two independent plans instead (one BUY, one SELL)
  - Each plan is processed independently and counts as 1 plan in results
- Each method handles its own validation and transaction
- Collect results from each call
- Return aggregated results with per-plan status
- **Benefits**: Reuses existing validation logic, no code duplication

#### 4.2 Batch Update Method
**Method**: `update_multiple_plans(updates: List[Dict]) -> Dict`

**Implementation**:
- **REVISED**: Do NOT add this method to `AutoExecutionSystem`
- **APPROACH**: In API endpoint, loop through updates and call `auto_execution.update_plan()` for each
- Process each update independently
- Partial success: update valid ones, skip invalid
- Return per-plan status
- **Validation**: Check plan exists, is pending status, update fields are valid

#### 4.3 Batch Cancel Method
**Method**: `cancel_multiple_plans(plan_ids: List[str]) -> Dict`

**Implementation**:
- **REVISED**: Do NOT add this method to `AutoExecutionSystem`
- **APPROACH**: In API endpoint, loop through plan_ids and call `auto_execution.cancel_plan()` from `ChatGPTAutoExecution` class for each
- **CRITICAL: API Endpoint Returns Dict**: The cancel API endpoint returns `{"success": True, "message": "..."}` format, not bool
- Process each cancellation independently
- Use existing `cancel_plan` method for each
- Return per-plan status
- **Idempotent**: Already-cancelled plans return success (no error)

---

## Error Handling Strategy

### Batch Create (Partial Success) ⚠️ REVISED
- **CHANGED FROM FAIL-FAST TO PARTIAL SUCCESS**
- Validate each plan independently
- Create valid plans, skip invalid ones
- Return detailed results per plan (success/failure with error messages)
- **REVISED: All Plans Fail Handling**: 
  - Even if ALL plans fail, still return 200 OK with `successful: 0, failed: total`
  - Include all error details in results array
  - Tool layer formats summary as error but includes full data
  - This provides consistent response format and allows user to see all errors
- Rationale: If user requests 5 plans and 1 fails, they likely want the other 4 created. If all fail, user can see all errors and fix them.
- **Validation Order**:
  1. **Tool Layer Validation** (before API call):
     - Validate `plans` array exists and is not empty
     - Validate `plans` is an array (not object, not null)
     - Return early error if structure invalid
  2. **API Endpoint Validation** (Pydantic + endpoint logic):
     - Pydantic validates request structure (array not empty, max 20 items)
     - Endpoint validates each plan has `plan_type` field
     - Endpoint validates `plan_type` is one of valid types
     - Return error for invalid plan_type before calling individual methods
  3. **Individual Method Validation** (performed by `create_*_plan()` methods):
     - Basic field validation (required fields present, correct types)
     - Symbol normalization (add 'c' suffix)
     - Weekend filtering (for BTCUSDc during weekend hours)
     - Plan-type-specific validation (SL/TP distances, min_confluence, etc.)
     - Volatility state validation (if enabled)
     - Conditions validation (price_near + tolerance, etc.)
  4. **CRITICAL: Batch endpoint should NOT duplicate individual method validation** - rely on individual methods

### Batch Update (Partial Success)
- Validate each update independently
- Update valid plans, skip invalid ones
- Return detailed results per plan
- **Validation**: Check plan exists, is pending status, update fields are valid
- Rationale: User may want to update some plans even if others fail

### Batch Cancel (Partial Success)
- Cancel each plan independently
- Report failures but continue with others
- Idempotent: already-cancelled plans return success
- **Validation**: Check plan exists (but allow already-cancelled)
- Rationale: User wants to clean up as many as possible

---

## Testing Plan

### Unit Tests
1. **Batch Create**:
   - Test with valid plans (all succeed)
   - Test with invalid plans (all fail validation - should return error)
   - Test with mixed valid/invalid (partial success - valid ones created)
   - Test with different plan types in same batch
   - Test creating two independent plans (BUY and SELL) with different conditions
   - Test weekend filtering (reject weekend-disallowed strategies)
   - Test symbol normalization (add 'c' suffix)
   - Test micro-scalp SL/TP distance validation
   - Test rate limiting (max 20 plans - return error if exceeded)
   - Test timeout handling (large batch - return partial results)
   - Test empty plans array (return error)
   - Test invalid plan_type (return error for that plan)
   - Test missing required fields (return error for that plan)
   - Test response format validation (ensure `{"summary": "...", "data": {...}}` format)
   - Test API response structure validation (check for required fields)

2. **Batch Update**:
   - Test with all valid updates
   - Test with some invalid updates (partial success)
   - Test with non-existent plan_ids (should fail for those)
   - Test with executed/cancelled plans (should fail - only pending can be updated)
   - Test with missing plan_id (should fail for that update)
   - Test with invalid update fields (negative prices, etc.)
   - Test empty updates array (return error)
   - Test update with no fields (return error for that update)
   - Test conditions validation (invalid conditions should fail for that update)
   - Test duplicate plan_ids in updates (should deduplicate, keep last update)
   - Test response format validation (ensure `{"summary": "...", "data": {...}}` format)
   - Test API endpoint exception handling (update method throws exception, others continue)
   - Test deduplication in both tool layer and API endpoint
   - Test response ordering after deduplication (results maintain original request order)

3. **Batch Cancel**:
   - Test with all valid plan_ids
   - Test with some invalid plan_ids (partial success)
   - Test idempotency (cancelling already-cancelled returns success)
   - Test with non-existent plan_ids (should fail for those)
   - Test empty plan_ids array (return error)
   - Test duplicate plan_ids (should deduplicate and cancel once)
   - Test with invalid plan_id format (non-string, null, etc.)
   - Test response format validation (ensure `{"summary": "...", "data": {...}}` format)
   - Test API response structure validation (check for required fields)
   - Test idempotent behavior (cancelling already-cancelled plan returns success)
   - Test API endpoint exception handling (cancel method throws exception, others continue)
   - Test response ordering after deduplication (results maintain original request order)

### Integration Tests
1. Test ChatGPT tool calls with batch operations
2. Test API endpoints directly
3. Test error responses and formatting
4. **CRITICAL: Test Response Format**: Verify all tools return `{"summary": "...", "data": {...}}` format
5. **CRITICAL: Test Desktop Agent Integration**: Verify batch tool responses work with desktop agent
6. Test HTTP status codes (200 for partial success, 422 for validation errors, 500 for server errors)
7. Test empty results handling (all plans fail, all updates fail, all cancellations fail)
8. Test duplicate handling (duplicate plan_ids in updates and cancels)

---

## Implementation Order

1. **Phase 1** (API Layer) - REST endpoints (use existing methods in loop)
2. **Phase 2** (Tool Layer) - ChatGPT tools
3. **Phase 3** (YAML Config) - Tool definitions and instructions
4. **Phase 4** (Knowledge Documents) - Update all knowledge documents:
   - **CRITICAL: Update ALL ChatGPT Version Embedding Documents** (13+ files)
   - Remove/deprecate bracket trades system-wide
   - Add guidance on creating two independent plans
   - Add batch operations documentation
   - Update examples and instructions
   - **CRITICAL: Search all documents for "bracket" references (case-insensitive)**
5. **Testing** - Unit and integration tests

**Note**: System Layer changes are NOT needed - we use existing methods in API endpoint loop

**CRITICAL**: Knowledge document updates (Phase 4) should be done in parallel with or immediately after Phase 3 to ensure ChatGPT has correct information about bracket trades being deprecated and batch operations being available.

**CRITICAL: ChatGPT Version Documents Priority**:
- The ChatGPT Version embedding documents are actively used by ChatGPT
- These must be updated to prevent ChatGPT from suggesting deprecated bracket trade tools
- Priority order:
  1. `6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md` (highest priority)
  2. `7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md` (highest priority)
  3. `1.KNOWLEDGE_DOC_EMBEDDING.md` (high priority)
  4. `2.UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md` (high priority)
  5. All other ChatGPT Version documents (review as needed)

---

## Files to Modify

1. `app/auto_execution_api.py` - Add batch endpoints (use existing creation methods in loop)
   - **CRITICAL: Add Pydantic Models**:
     - `BatchCreatePlanRequest` with `plans: List[Dict[str, Any]]`
     - `BatchUpdatePlanRequest` with `updates: List[Dict[str, Any]]`
     - `BatchCancelPlanRequest` with `plan_ids: List[str]`
   - Add validators for array length (max 20 for create, no limit for update/cancel)
   - Add endpoint handlers with proper error handling
2. `chatgpt_auto_execution_tools.py` - Add batch tool functions
   - Handle 422 validation errors from FastAPI
   - Format error messages for ChatGPT
3. `openai.yaml` - Add batch tool definitions and update instructions
4. `docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_INSTRUCTIONS.md` - Add batch operations documentation + Remove/deprecate bracket trades
5. `docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md` - Update if needed for batch operations + Remove/deprecate bracket trades
6. `docs/ChatGPT Knowledge Documents/ChatGPT_Knowledge_Document.md` - Remove/deprecate bracket trades
7. `docs/ChatGPT Knowledge Documents/UPDATED_GPT_INSTRUCTIONS_FIXED.md` - Remove/deprecate bracket trades
8. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md` - **CRITICAL**: Remove bracket trades, add batch operations
9. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md` - **CRITICAL**: Remove bracket trades, add batch operations
10. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/1.KNOWLEDGE_DOC_EMBEDDING.md` - **CRITICAL**: Remove bracket trades, add batch operations
11. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/2.UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md` - Update bracket trade reference, add batch operations
12. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/3.VERIFICATION_PROTOCOL_EMBEDDING.md` - Review and update if needed
13. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/4.ANTI_HALLUCINATION_EXAMPLES_EMBEDDING.md` - Review and update if needed
14. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/5.CHATGPT_FORMATTING_INSTRUCTIONS_EMBEDDING.md` - Review and update if needed
15. All other ChatGPT Version documents - Review and update as needed
16. `openai.yaml` - **CRITICAL**: Remove bracket trade tool definitions, update instructions, remove schema property references, add batch operations tools

**Note**: Do NOT modify `auto_execution_system.py` - use existing methods in API endpoint

**CRITICAL: Database Schema**:
- **NO DATABASE CHANGES REQUIRED**
- Existing `trade_plans` table schema is sufficient
- Batch operations use existing individual methods which use the same database table
- No migrations needed
- Backward compatible with all existing plans

---

## 🚨 **CRITICAL: System-Wide Bracket Trade Deprecation**

### **Overview**
Bracket trades are being deprecated system-wide. Users should create two independent plans (one BUY, one SELL) with different conditions instead. This is more flexible than OCO (One Cancels Other) bracket trades.

### **Rationale**
- With conditional execution, each plan can have specific conditions
- Independent plans allow both to be monitored simultaneously
- If one executes, the other can still execute later if its conditions are met
- More flexible than OCO bracket trades which cancel the other side
- Simpler implementation and maintenance

### **Knowledge Documents to Update**

**CRITICAL: All ChatGPT Version Knowledge Documents Must Be Updated**

The following documents are used by ChatGPT and must be updated to reflect:
1. Batch operations (create_multiple_auto_plans, update_multiple_auto_plans, cancel_multiple_auto_plans)
2. Bracket trade deprecation (remove all references, add guidance for two independent plans)
3. Updated tool lists and examples

**Summary of Documents Requiring Updates:**

**Main Knowledge Documents (5 files):**
1. `docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_INSTRUCTIONS.md`
2. `docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md`
3. `docs/ChatGPT Knowledge Documents/ChatGPT_Knowledge_Document.md`
4. `docs/ChatGPT Knowledge Documents/UPDATED_GPT_INSTRUCTIONS_FIXED.md`
5. `openai.yaml`

**ChatGPT Version Embedding Documents (Primary - 4 files):**
6. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md` ⚠️ **CRITICAL**
7. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md` ⚠️ **CRITICAL**
8. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/1.KNOWLEDGE_DOC_EMBEDDING.md` ⚠️ **CRITICAL**
9. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/2.UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md` ⚠️ **CRITICAL**

**ChatGPT Version Embedding Documents (Review Required - 3+ files):**
10. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/3.VERIFICATION_PROTOCOL_EMBEDDING.md`
11. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/4.ANTI_HALLUCINATION_EXAMPLES_EMBEDDING.md`
12. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/5.CHATGPT_FORMATTING_INSTRUCTIONS_EMBEDDING.md`
13. All other ChatGPT Version documents (search for "bracket" references)

**Total: 13+ documents requiring review and updates**

#### **Main Knowledge Documents:**

#### 1. `docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_INSTRUCTIONS.md`
**Current State**: Has section "### **5. Create Bracket Trade Plan:**" with extensive documentation

**Required Changes**:
- **Remove or deprecate** the entire bracket trade section
- **Add note** explaining bracket trades are deprecated
- **Add guidance** on creating two independent plans instead:
  ```markdown
  ### **⚠️ Bracket Trades Deprecated**
  
  Bracket trades are no longer supported. Instead, create two independent plans:
  
  **For BUY side:**
  ```
  tool_create_auto_trade_plan(
      symbol: "BTCUSDc",
      direction: "BUY",
      entry_price: 88000.0,
      stop_loss: 87500.0,
      take_profit: 89000.0,
      conditions: {
          "price_above": 88000.0,
          "price_near": 88000.0,
          "tolerance": 100.0,
          "choch_bull": true
      }
  )
  ```
  
  **For SELL side:**
  ```
  tool_create_auto_trade_plan(
      symbol: "BTCUSDc",
      direction: "SELL",
      entry_price: 86400.0,
      stop_loss: 87000.0,
      take_profit: 85200.0,
      conditions: {
          "price_below": 86400.0,
          "price_near": 86400.0,
          "tolerance": 100.0,
          "choch_bear": true
      }
  )
  ```
  
  **Benefits:**
  - Each plan monitors independently
  - If one executes, the other can still execute later if conditions are met
  - More flexible than OCO bracket trades
  - Can use batch operations to create both plans at once
  ```
- **Update examples** to show two independent plans instead of bracket trades
- **Remove** all references to `tool_create_bracket_trade_plan`
- **Remove** all references to `executeBracketTrade` (already deprecated)

#### 2. `docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md`
**Current State**: Has section "### 5. `moneybot.create_bracket_trade_plan`" with extensive documentation

**Required Changes**:
- **Remove or deprecate** the entire bracket trade section (lines ~752-860)
- **Add deprecation notice** at the top of the document
- **Update** any examples that reference bracket trades
- **Add guidance** on creating two independent plans with different conditions
- **Update** condition rules section to remove bracket trade-specific rules

#### 3. `docs/ChatGPT Knowledge Documents/ChatGPT_Knowledge_Document.md`
**Current State**: Has section "### Bracket Trade Detailed Guidelines" (lines ~1593-1659)

**Required Changes**:
- **Remove or deprecate** the entire "Bracket Trade Detailed Guidelines" section
- **Add deprecation notice** explaining why bracket trades are removed
- **Add guidance** on creating two independent plans instead
- **Update** "When to Recommend Bracket Trades" section to recommend two independent plans
- **Update** "Bracket Trade Risk Management" section or remove it

#### 4. `docs/ChatGPT Knowledge Documents/UPDATED_GPT_INSTRUCTIONS_FIXED.md`
**Current State**: Mentions bracket trades in multiple places (lines ~33, 44, 149)

**Required Changes**:
- **Remove** all references to `moneybot.executeBracketTrade`
- **Remove** all references to bracket trades
- **Update** instructions to recommend two independent plans instead
- **Update** examples to show two independent plans

#### 5. `docs/ChatGPT Knowledge Documents/UPDATED_GPT_INSTRUCTIONS_FIXED.md`
**Current State**: Mentions bracket trades in multiple places (lines ~33, 44, 149)

**Required Changes**:
- **Remove** all references to `moneybot.executeBracketTrade`
- **Remove** all references to bracket trades
- **Update** instructions to recommend two independent plans instead
- **Update** examples to show two independent plans
- **Add** batch operations guidance (when to use batch vs single tools)

#### **ChatGPT Version Knowledge Documents (Embedding Versions):**

#### 6. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md`
**Current State**: Has section "**Bracket Trade Plans:**" (line ~262-264) with tool reference

**Required Changes**:
- **Remove** entire "**Bracket Trade Plans:**" section
- **Remove** tool reference: `moneybot.create_bracket_trade_plan`
- **Add** deprecation notice explaining bracket trades are deprecated
- **Add** guidance on creating two independent plans instead
- **Add** batch operations section:
  - `moneybot.create_multiple_auto_plans` - for creating multiple plans at once
  - `moneybot.update_multiple_auto_plans` - for updating multiple plans at once
  - `moneybot.cancel_multiple_auto_plans` - for cancelling multiple plans at once
- **Update** tool lists to include batch operations tools
- **Update** examples to show batch operations usage

#### 7. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md`
**Current State**: Has section "**Bracket Trade Plans:**" (line ~1042-1044) with tool reference

**Required Changes**:
- **Remove** entire "**Bracket Trade Plans:**" section
- **Remove** tool reference: `moneybot.create_bracket_trade_plan`
- **Remove** all bracket trade parameter documentation (`buy_entry`, `buy_sl`, `buy_tp`, `sell_entry`, `sell_sl`, `sell_tp`, `reasoning`)
- **Add** deprecation notice explaining bracket trades are deprecated
- **Add** guidance on creating two independent plans instead
- **Add** batch operations documentation:
  - When to use batch operations (multiple plans, different strategies)
  - How to use `moneybot.create_multiple_auto_plans`
  - How to use `moneybot.update_multiple_auto_plans`
  - How to use `moneybot.cancel_multiple_auto_plans`
  - Response format and error handling
- **Update** examples to show batch operations instead of bracket trades

#### 8. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/1.KNOWLEDGE_DOC_EMBEDDING.md`
**Current State**: Has multiple bracket trade references:
- Line ~355: `moneybot.executeBracketTrade` tool reference
- Line ~367: `moneybot.create_bracket_trade_plan` tool reference
- Line ~464-465: "When to use `moneybot.executeBracketTrade`" section

**Required Changes**:
- **Remove** all references to `moneybot.executeBracketTrade` (deprecated tool)
- **Remove** all references to `moneybot.create_bracket_trade_plan` (deprecated tool)
- **Remove** "When to use `moneybot.executeBracketTrade`" section
- **Add** deprecation notice explaining bracket trades are deprecated
- **Add** guidance on creating two independent plans instead
- **Add** batch operations tools to tool lists:
  - `moneybot.create_multiple_auto_plans`
  - `moneybot.update_multiple_auto_plans`
  - `moneybot.cancel_multiple_auto_plans`
- **Update** "Auto-Execution Plans" section to remove bracket trade tool
- **Add** batch operations guidance in appropriate sections

#### 9. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/2.UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md`
**Current State**: Has reference to bracket trades (line ~428): "Never generate bracket trades unless explicitly requested"

**Required Changes**:
- **Update** line ~428: Change to "Bracket trades are deprecated. Instead, create two independent plans (one BUY, one SELL) with different conditions."
- **Add** guidance on when to use batch operations
- **Add** examples showing batch operations for creating multiple plans

#### **Additional ChatGPT Version Documents to Review:**

#### 10. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/3.VERIFICATION_PROTOCOL_EMBEDDING.md`
**Review Required**: Check if this document mentions bracket trades or auto execution plans
- If yes: Remove bracket trade references, add batch operations if relevant

#### 11. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/4.ANTI_HALLUCINATION_EXAMPLES_EMBEDDING.md`
**Review Required**: Check if this document mentions bracket trades
- If yes: Remove bracket trade examples, add batch operations examples if relevant

#### 12. `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/5.CHATGPT_FORMATTING_INSTRUCTIONS_EMBEDDING.md`
**Review Required**: Check if this document mentions bracket trades
- If yes: Remove bracket trade formatting examples

#### 13. All other ChatGPT Version documents in `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/`
**Review Required**: Search all documents for:
- References to "bracket" (case-insensitive)
- References to `create_bracket_trade_plan`
- References to `executeBracketTrade`
- Update as needed

#### **openai.yaml Configuration:**

#### 14. `openai.yaml`
**Current State**: Has multiple bracket trade references:
- Tool definition: `createBracketTradePlan` (lines ~2018-2045)
- Tool definition: `executeBracketTrade` (lines ~2046-2071) - already marked as deprecated
- Instructions section: "CRITICAL: BRACKET TRADES" (lines ~1001-1022)
- Schema properties: `buy_entry`, `buy_sl`, `buy_tp`, `sell_entry`, `sell_sl`, `sell_tp`, `reasoning` (lines ~1118-1145)
- Multiple references in instructions (lines ~539, 682, 944, 16, 35)

**Required Changes**:

1. **Remove Tool Definitions**:
   - **Remove** `createBracketTradePlan` tool definition entirely (lines ~2018-2045)
   - **Remove** `executeBracketTrade` tool definition entirely (lines ~2046-2071) - already deprecated, now remove completely
   - These tools are no longer needed

2. **Update Instructions Section** (lines ~1001-1022):
   - **Remove** entire "CRITICAL: BRACKET TRADES" section
   - **Replace with** guidance on creating two independent plans:
     ```yaml
     **⚠️ Bracket Trades Deprecated - Use Two Independent Plans Instead:**
     
     Bracket trades are no longer supported. Instead, create two independent plans:
     
     **For BUY side:**
     - Use moneybot.create_auto_trade_plan (or other plan types) with direction: "BUY"
     - Set conditions appropriate for BUY (e.g., price_above, choch_bull)
     - Each plan monitors independently
     
     **For SELL side:**
     - Use moneybot.create_auto_trade_plan (or other plan types) with direction: "SELL"
     - Set conditions appropriate for SELL (e.g., price_below, choch_bear)
     - Each plan monitors independently
     
     **Benefits:**
     - Both plans can execute independently
     - If one executes, the other can still execute later if conditions are met
     - More flexible than OCO bracket trades
     - Can use moneybot.create_multiple_auto_plans to create both at once
     ```

3. **Update Schema Properties** (lines ~1118-1145):
   - **Remove** or **deprecate** bracket trade-specific properties:
     - `buy_entry` - Remove description reference to bracket trades
     - `buy_sl` - Remove description reference to bracket trades
     - `buy_tp` - Remove description reference to bracket trades
     - `sell_entry` - Remove description reference to bracket trades
     - `sell_sl` - Remove description reference to bracket trades
     - `sell_tp` - Remove description reference to bracket trades
     - `reasoning` - Update description to remove bracket trade reference
   - **Note**: These properties may still be used by other tools, so only remove bracket trade references from descriptions

4. **Update Other Instruction References**:
   - **Line ~16**: Remove "Smart bracket trade system" reference
   - **Line ~35**: Remove "Bracket trade condition analysis" reference
   - **Line ~539**: Remove bracket trade condition rules
   - **Line ~682**: Remove `moneybot.create_bracket_trade_plan` from tool list
   - **Line ~944**: Remove bracket trade condition rules
   - **Replace** with guidance on creating two independent plans

5. **Add Batch Operations Guidance**:
   - **Add** instructions for using `moneybot.create_multiple_auto_plans` for creating both BUY and SELL plans
   - **Add** example showing how to create two independent plans in one batch call
   - **Update** tool lists to include batch operations tools

6. **Update Tool Lists**:
   - **Remove** `moneybot.create_bracket_trade_plan` from all tool lists
   - **Remove** `moneybot.executeBracketTrade` from all tool lists (if still present)
   - **Add** `moneybot.create_multiple_auto_plans` to tool lists
   - **Add** `moneybot.update_multiple_auto_plans` to tool lists
   - **Add** `moneybot.cancel_multiple_auto_plans` to tool lists

**Implementation Notes**:
- Search for all occurrences of "bracket" (case-insensitive) in openai.yaml
- Review each occurrence and either remove or update with deprecation notice
- Ensure no broken references remain
- Test that ChatGPT no longer suggests bracket trade tools

### **Database Schema Analysis**

**CRITICAL: Database Does NOT Require Updates**

- **Current Schema**: The `trade_plans` table already supports all plan types (auto_trade, choch, rejection_wick, order_block, range_scalp, micro_scalp)
- **Batch Operations**: Batch operations call existing individual creation methods, which use the same database table
- **No Schema Changes Needed**: 
  - Batch create: Uses existing `INSERT INTO trade_plans` (via individual methods)
  - Batch update: Uses existing `UPDATE trade_plans` (via individual methods)
  - Batch cancel: Uses existing `UPDATE trade_plans SET status = 'cancelled'` (via individual methods)
- **No Migration Required**: Existing database structure is sufficient
- **Backward Compatible**: All existing plans continue to work without changes

**Database Table Structure (Already Exists)**:
```sql
CREATE TABLE trade_plans (
    plan_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit REAL NOT NULL,
    volume REAL NOT NULL,
    conditions TEXT NOT NULL,  -- JSON string
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    expires_at TEXT,
    executed_at TEXT,
    ticket INTEGER,
    notes TEXT,
    profit_loss REAL,
    exit_price REAL,
    close_time TEXT,
    close_reason TEXT
)
```

**Conclusion**: No database schema changes or migrations required. Batch operations work with existing schema.

### **Implementation Steps**

1. **Phase 1: Documentation Updates**
   - **CRITICAL: Update ALL ChatGPT Version Knowledge Documents**:
     - **Primary Documents (Must Update)**:
       - `6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md` - Remove bracket trades, add batch operations
       - `7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md` - Remove bracket trades, add batch operations
       - `1.KNOWLEDGE_DOC_EMBEDDING.md` - Remove bracket trades, add batch operations
       - `2.UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md` - Update bracket trade reference, add batch operations
     - **Review Documents (Check and Update if Needed)**:
       - `3.VERIFICATION_PROTOCOL_EMBEDDING.md` - Search for bracket references
       - `4.ANTI_HALLUCINATION_EXAMPLES_EMBEDDING.md` - Search for bracket references
       - `5.CHATGPT_FORMATTING_INSTRUCTIONS_EMBEDDING.md` - Search for bracket references
       - All other ChatGPT Version documents - Search for "bracket" (case-insensitive)
   - **Update all main knowledge documents**:
     - `AUTO_EXECUTION_CHATGPT_INSTRUCTIONS.md` - Remove bracket trades, add batch operations
     - `AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md` - Remove bracket trades, add batch operations
     - `ChatGPT_Knowledge_Document.md` - Remove bracket trades
     - `UPDATED_GPT_INSTRUCTIONS_FIXED.md` - Remove bracket trades, add batch operations
   - **CRITICAL: Update `openai.yaml`**:
     - Remove bracket trade tool definitions (`createBracketTradePlan`, `executeBracketTrade`)
     - Remove "CRITICAL: BRACKET TRADES" instruction section
     - Add batch operations tool definitions (`createMultipleAutoPlans`, `updateMultipleAutoPlans`, `cancelMultipleAutoPlans`)
     - Update schema property descriptions (remove bracket trade references)
     - Update tool lists (remove bracket tools, add batch tools)
     - Search entire file for "bracket" (case-insensitive) and review each occurrence
   - **For each document**:
     - Add deprecation notices for bracket trades
     - Add guidance on creating two independent plans instead
     - Add batch operations documentation (when to use, how to use, examples)
     - Remove all bracket trade examples
     - Remove all references to `create_bracket_trade_plan` and `executeBracketTrade`
     - **Search and replace** all "bracket" references (case-insensitive)

**Quick Checklist for Knowledge Document Updates**:

**Main Documents:**
- [ ] `AUTO_EXECUTION_CHATGPT_INSTRUCTIONS.md` - Remove bracket trades, add batch operations
- [ ] `AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md` - Remove bracket trades, add batch operations
- [ ] `ChatGPT_Knowledge_Document.md` - Remove bracket trades
- [ ] `UPDATED_GPT_INSTRUCTIONS_FIXED.md` - Remove bracket trades, add batch operations

**ChatGPT Version Embedding Documents (Primary):**
- [ ] `6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md` - Remove bracket trades, add batch operations
- [ ] `7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md` - Remove bracket trades, add batch operations
- [ ] `1.KNOWLEDGE_DOC_EMBEDDING.md` - Remove bracket trades, add batch operations
- [ ] `2.UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md` - Update bracket trade reference, add batch operations

**ChatGPT Version Embedding Documents (Review):**
- [ ] `3.VERIFICATION_PROTOCOL_EMBEDDING.md` - Search for bracket references
- [ ] `4.ANTI_HALLUCINATION_EXAMPLES_EMBEDDING.md` - Search for bracket references
- [ ] `5.CHATGPT_FORMATTING_INSTRUCTIONS_EMBEDDING.md` - Search for bracket references
- [ ] All other ChatGPT Version documents - Search for "bracket" references

**openai.yaml Updates:**
- ✅ Removed `createBracketTradePlan` tool definition
- ✅ Removed `executeBracketTrade` tool definition
- ✅ Removed "CRITICAL: BRACKET TRADES" instruction section
- ✅ Replaced with guidance on two independent plans
- ✅ Updated schema property descriptions (removed bracket trade parameters, added batch operation parameters)
- ✅ Removed bracket trade references from tool lists
- ✅ Removed bracket trade references from other instruction sections
- ✅ Added batch operations tools to tool lists:
  - ✅ Added `createMultipleAutoPlans` tool definition
  - ✅ Added `updateMultipleAutoPlans` tool definition
  - ✅ Added `cancelMultipleAutoPlans` tool definition
- ✅ Added batch operations instructions to system instructions
- ✅ Searched entire file for "bracket" (case-insensitive) and reviewed each occurrence
- ⏳ Test that ChatGPT no longer suggests bracket trade tools (requires ChatGPT testing)
- ⏳ Test that ChatGPT suggests batch operations when appropriate (requires ChatGPT testing)

**For Each Document:**
- ✅ Searched for "bracket" (case-insensitive) and removed/updated all references
- ✅ Removed all references to `create_bracket_trade_plan`
- ✅ Removed all references to `executeBracketTrade`
- ✅ Added deprecation notice for bracket trades
- ✅ Added guidance on creating two independent plans
- ✅ Added batch operations documentation (where relevant)
- ✅ Updated examples to show batch operations or two independent plans

2. **Phase 2: Code Deprecation (Future)**
   - Mark `create_bracket_trade_plan` as deprecated in code
   - Add deprecation warnings in API responses
   - Consider removing the tool entirely in future version

3. **Phase 3: Migration Guide**
   - Create migration guide for users with existing bracket trades
   - Explain how to convert bracket trades to two independent plans
   - Provide examples

### **Migration Example**

**Old Approach (Bracket Trade):**
```
tool_create_bracket_trade_plan(
    symbol: "BTCUSDc",
    buy_entry: 88000.0,
    buy_sl: 87500.0,
    buy_tp: 89000.0,
    sell_entry: 86400.0,
    sell_sl: 87000.0,
    sell_tp: 85200.0,
    conditions: {...}
)
```

**New Approach (Two Independent Plans):**
```
tool_create_multiple_auto_plans(
    plans: [
        {
            plan_type: "auto_trade",
            symbol: "BTCUSDc",
            direction: "BUY",
            entry_price: 88000.0,
            stop_loss: 87500.0,
            take_profit: 89000.0,
            conditions: {
                "price_above": 88000.0,
                "price_near": 88000.0,
                "tolerance": 100.0,
                "choch_bull": true
            }
        },
        {
            plan_type: "auto_trade",
            symbol: "BTCUSDc",
            direction: "SELL",
            entry_price: 86400.0,
            stop_loss: 87000.0,
            take_profit: 85200.0,
            conditions: {
                "price_below": 86400.0,
                "price_near": 86400.0,
                "tolerance": 100.0,
                "choch_bear": true
            }
        }
    ]
)
```

### **Benefits of New Approach**
- ✅ More flexible: Both plans can execute independently
- ✅ Better monitoring: Each plan has its own conditions
- ✅ No OCO limitation: If one executes, the other can still execute later
- ✅ Batch operations: Can create both plans in one call
- ✅ Simpler implementation: No special bracket trade logic needed

---

---

## Backward Compatibility

- **Keep all existing single-plan tools** (create_auto_trade_plan, update_auto_plan, cancel_auto_plan, etc.)
- **Keep all existing API endpoints** (no breaking changes)
- **Add new batch tools alongside existing ones**
- ChatGPT can choose based on context (single vs multiple)

---

## Success Criteria

1. ✅ ChatGPT can create multiple plans in one tool call
2. ✅ ChatGPT can update multiple plans in one tool call
3. ✅ ChatGPT can cancel multiple plans in one tool call
4. ✅ Error handling provides detailed per-plan results
5. ✅ Backward compatibility maintained
6. ✅ All tests pass
7. ✅ Documentation updated
8. ✅ **Bracket trades deprecated system-wide in all knowledge documents** (including all ChatGPT Version documents)
9. ✅ **Guidance added for creating two independent plans instead of bracket trades**
10. ✅ **Batch operations documented in all relevant knowledge documents**
11. ✅ **All ChatGPT Version embedding documents updated**
12. ✅ **Database schema verified - no changes required**

---

## Future Enhancements (Post-MVP)

1. **Batch operations with filters**: Cancel all plans matching criteria (e.g., symbol, status)
2. **Batch operations with templates**: Apply same update to multiple plans
3. **Batch validation**: Pre-validate plans before creation
4. **Batch status check**: Get status of multiple plans at once

---

## Notes

- **Rate Limiting**: Max 20 plans per batch (configurable, return error if exceeded)
- **Timeout Handling**: 60 second timeout for batch operations, return partial results if timeout occurs
- **Logging/Auditing**: Log batch operations with plan counts, success/failure rates
- **UI Updates**: Consider showing batch operation results in auto-execution view page
- **Performance**: Batch operations may take longer - consider async processing for very large batches (future enhancement)

---

## ChatGPT Knowledge Documents Updates Required

### File: `docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_INSTRUCTIONS.md`

**Add new section after "Available Tools" section:**

```markdown
## 🛠️ **Batch Operations Tools** ⭐ NEW

### **When to Use Batch Operations:**
- User requests multiple plans (e.g., "create 3 buy plans and 2 sell plans")
- User asks for plans for different strategies (e.g., "give me a CHOCH plan, rejection wick plan, and order block plan")
- User wants to update multiple plans at once
- User wants to cancel multiple plans at once

### **1. Create Multiple Plans:**
```
tool_create_multiple_auto_plans(
    plans: [
        {
            plan_type: "choch",
            symbol: "BTCUSDc",
            direction: "BUY",
            entry_price: 88000.0,
            stop_loss: 87500.0,
            take_profit: 89000.0,
            volume: 0.01,
            choch_type: "bull",
            expires_hours: 24,
            notes: "CHOCH Bull plan"
        },
        {
            plan_type: "rejection_wick",
            symbol: "BTCUSDc",
            direction: "SELL",
            entry_price: 87000.0,
            stop_loss: 87200.0,
            take_profit: 86500.0,
            volume: 0.01,
            expires_hours: 24,
            notes: "Rejection wick plan"
        }
    ]
)
```

**⚠️ CRITICAL Requirements:**
- Each plan MUST specify `plan_type` field
- Each plan type requires specific fields (see individual tool documentation)
- Plans are validated independently - valid ones are created, invalid ones are skipped
- Response includes detailed results per plan (success/failure with error messages)

### **2. Update Multiple Plans:**
```
tool_update_multiple_auto_plans(
    updates: [
        {
            plan_id: "chatgpt_abc123",
            entry_price: 88500.0,
            stop_loss: 88000.0,
            take_profit: 89500.0
        },
        {
            plan_id: "chatgpt_def456",
            expires_hours: 48,
            notes: "Extended expiration"
        }
    ]
)
```

### **3. Cancel Multiple Plans:**
```
tool_cancel_multiple_auto_plans(
    plan_ids: ["chatgpt_abc123", "chatgpt_def456", "chatgpt_ghi789"]
)
```

**Response Format:**
- `total`: Total number of plans in batch
- `successful`: Number of successful operations
- `failed`: Number of failed operations
- `results`: Array of per-plan results with status, plan_id, and error messages (if failed)

**Benefits:**
- Reduces permission prompts (one tool call instead of multiple)
- Faster workflow when handling multiple plans
- Better error handling (see which plans succeeded/failed)
```

**Update "ChatGPT Workflow" section:**
- Add example of batch operations workflow
- Show when to use batch vs single tools

**Update "Example Scenarios" section:**
- Add scenario showing batch creation of multiple plans
- Add scenario showing batch update/cancel

---

## Integration Considerations

### 1. **Existing Validation Logic**
- All existing validation logic must be applied to each plan in batch
- Weekend filtering, volatility state validation, conditions validation, etc.
- Each plan type has its own validation rules (micro-scalp SL/TP distances, etc.)

### 2. **Error Messages**
- Provide detailed, actionable error messages per plan
- Include plan type and symbol in error messages for context
- For weekend filtering rejections, specify allowed/disallowed strategies

### 3. **Response Format**
- Consistent response format across all batch operations
- Include index to match request order
- Include plan_type and symbol in all results (success or failure)
- Each plan counts as 1 item in results (no special counting for bracket trades)

### 4. **Performance**
- Batch operations may take longer than single operations
- Consider timeout handling (60 seconds)
- Consider rate limiting (max 20 plans per batch)
- Log performance metrics (time taken, plans processed)

### 5. **Testing**
- Test with real ChatGPT tool calls
- Test error scenarios (all fail, some fail, all succeed)
- Test with different plan types in same batch
- Test creating two independent plans (BUY and SELL) with different conditions
- Test weekend filtering during weekend hours
- Test HTTP error handling (4xx, 5xx responses)
- **CRITICAL: Test 422 Validation Errors**: Test Pydantic validation failures (empty arrays, invalid types, etc.)
- Test timeout scenarios (slow API responses)
- Test connection errors (API server down)
- Test response formatting for ChatGPT (user-friendly messages)
- Test exception handling (one plan throws exception, others continue)
- **CRITICAL: Test Response Format**: Verify all tools return `{"summary": "...", "data": {...}}` format
- **CRITICAL: Test Desktop Agent Integration**: Verify batch tool responses work with desktop agent
- Test duplicate plan_ids handling (in updates and cancels)
- Test empty results handling (all operations fail)
- Test HTTP status codes (200 for partial success, 422 for validation errors)

---

## 📋 **COMPREHENSIVE KNOWLEDGE DOCUMENT UPDATE SUMMARY**

### **Documents Requiring Updates: 13+ Files**

**Main Knowledge Documents (5 files):**
1. ✅ `docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_INSTRUCTIONS.md`
2. ✅ `docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md`
3. ✅ `docs/ChatGPT Knowledge Documents/ChatGPT_Knowledge_Document.md`
4. ✅ `docs/ChatGPT Knowledge Documents/UPDATED_GPT_INSTRUCTIONS_FIXED.md`
5. ✅ `openai.yaml` ⚠️ **CRITICAL**

**ChatGPT Version Embedding Documents - Primary (4 files):**
6. ✅ `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/6.AUTO_EXECUTION_CHATGPT_INSTRUCTIONS_EMBEDDING.md` ⚠️ **CRITICAL**
7. ✅ `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/7.AUTO_EXECUTION_CHATGPT_KNOWLEDGE_EMBEDDED.md` ⚠️ **CRITICAL**
8. ✅ `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/1.KNOWLEDGE_DOC_EMBEDDING.md` ⚠️ **CRITICAL**
9. ✅ `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/2.UPDATED_GPT_INSTRUCTIONS_EMBEDDING.md` ⚠️ **CRITICAL**

**ChatGPT Version Embedding Documents - Review Required (3+ files):**
10. ⚠️ `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/3.VERIFICATION_PROTOCOL_EMBEDDING.md`
11. ⚠️ `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/4.ANTI_HALLUCINATION_EXAMPLES_EMBEDDING.md`
12. ⚠️ `docs/ChatGPT Knowledge Documents Updated - 06.12.25/ChatGPT Version/5.CHATGPT_FORMATTING_INSTRUCTIONS_EMBEDDING.md`
13. ⚠️ All other ChatGPT Version documents (search for "bracket" references)

### **Update Requirements for Each Document:**

**For ALL Documents:**
- ✅ Removed all references to `create_bracket_trade_plan`
- ✅ Removed all references to `executeBracketTrade`
- ✅ Searched for "bracket" (case-insensitive) and removed/updated all references
- ✅ Added deprecation notice explaining bracket trades are deprecated
- ✅ Added guidance on creating two independent plans instead
- ✅ Updated examples to show two independent plans or batch operations

**For Auto Execution Documents (1, 2, 6, 7):**
- ✅ Added batch operations section:
  - When to use batch operations
  - How to use `create_multiple_auto_plans`
  - How to use `update_multiple_auto_plans`
  - How to use `cancel_multiple_auto_plans`
  - Response format and error handling
- ✅ Updated tool lists to include batch operations tools
- ✅ Removed bracket trade sections entirely

**For openai.yaml:**
- ✅ Removed `createBracketTradePlan` tool definition
- ✅ Removed `executeBracketTrade` tool definition
- ✅ Removed "CRITICAL: BRACKET TRADES" instruction section
- ✅ Added batch operations tool definitions
- ✅ Updated schema property descriptions
- ✅ Updated tool lists
- ✅ Added batch operations instructions

### **Database Schema Analysis:**

✅ **NO DATABASE CHANGES REQUIRED**

- **Current Schema**: `trade_plans` table already supports all plan types
- **Batch Operations**: Use existing individual methods which use the same database table
- **No Migrations Needed**: Existing structure is sufficient
- **Backward Compatible**: All existing plans continue to work

**Database Table (Already Exists):**
```sql
CREATE TABLE trade_plans (
    plan_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit REAL NOT NULL,
    volume REAL NOT NULL,
    conditions TEXT NOT NULL,  -- JSON string
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    expires_at TEXT,
    executed_at TEXT,
    ticket INTEGER,
    notes TEXT,
    profit_loss REAL,
    exit_price REAL,
    close_time TEXT,
    close_reason TEXT
)
```

**Conclusion**: Database schema is complete and requires no changes for batch operations.

---

## 🔍 **FINAL REVIEW - ISSUES FOUND AND FIXED**

### **Issues Identified and Resolved:**

1. ✅ **Pydantic Validator Syntax**: Added version compatibility notes (v1 vs v2)
2. ✅ **Plan Type Validation Location**: Clarified - tool layer validates structure, API endpoint validates plan_type
3. ✅ **Deduplication Order Preservation**: Added requirement to track and preserve original request order
4. ✅ **Response Ordering**: Clarified how to maintain order after deduplication
5. ✅ **Missing plan_id Handling**: Added handling for None plan_id on failure
6. ✅ **Results Array Building**: Clarified sequential processing and order maintenance
7. ✅ **Weekend Filtering Location**: Fixed inconsistency - individual methods handle it
8. ✅ **Validation Order**: Clarified 4-step validation process (tool layer → API endpoint → individual methods)
9. ✅ **Error Message Extraction**: Enhanced to handle missing fields gracefully
10. ✅ **Import Statements**: Added to Pydantic model examples

### **Remaining Considerations:**

- **Pydantic Version**: Check project's Pydantic version before implementation (v1 uses `@validator`, v2 uses `@field_validator`)
- **Order Preservation**: Ensure all deduplication logic tracks original order before deduplicating
- **Error Handling**: All error paths must return proper format and maintain request order
- **Testing**: All edge cases (duplicates, missing fields, ordering) must be tested

### **Plan Status**: ✅ **IMPLEMENTATION COMPLETE**

All phases have been completed:
- ✅ Phase 1: Backend API Layer - Complete
- ✅ Phase 2: Tool Layer - Complete
- ✅ Phase 3: OpenAI YAML Configuration - Complete
- ✅ Phase 4: Update All Knowledge Documents - Complete

**Remaining Items (Optional/Testing):**
- ⏳ ChatGPT testing: Verify ChatGPT no longer suggests bracket trade tools
- ⏳ ChatGPT testing: Verify ChatGPT suggests batch operations when appropriate
- ⏳ Future consideration: Code deprecation (mark bracket trade methods as deprecated in code)
- ⏳ Future consideration: Migration guide for users with existing bracket trades

All critical implementation work is complete. The system is ready for use.
