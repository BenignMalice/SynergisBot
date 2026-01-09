# Auto-Execution System - File Structure

## Core System Files

### 1. **`auto_execution_system.py`** ⭐ MAIN CORE FILE
- **Purpose**: Core monitoring and execution engine
- **Key Components**:
  - `TradePlan` dataclass - Plan data structure
  - `AutoExecutionSystem` class - Main monitoring system
  - Database operations (SQLite)
  - Condition checking logic
  - Trade execution logic
  - M1 microstructure integration
  - Thread safety and resource management
- **Dependencies**: 
  - `infra.mt5_service` - MT5 connection
  - `infra.tolerance_helper` - Price tolerance calculation
  - M1 analyzer, refresh manager, data fetcher (optional)

### 2. **`chatgpt_auto_execution_integration.py`**
- **Purpose**: ChatGPT integration layer
- **Key Functions**:
  - `create_trade_plan()` - General plan creation
  - `create_choch_plan()` - CHOCH-specific plans
  - `create_rejection_wick_plan()` - Rejection wick plans
  - `create_order_block_plan()` - Order block plans
  - `create_range_scalp_plan()` - Range scalping plans
  - `create_bracket_trade_plan()` - Bracket trade plans
  - `create_micro_scalp_plan()` - Micro-scalp plans
  - `cancel_plan()` - Cancel plans
  - `get_plan_status()` - Get plan status
- **Dependencies**: 
  - `auto_execution_system` (imports `TradePlan`, `get_auto_execution_system`)
  - `infra.tolerance_helper`

### 3. **`chatgpt_auto_execution_tools.py`**
- **Purpose**: Async tool functions for ChatGPT to call via HTTP
- **Key Functions**:
  - `tool_create_auto_trade_plan()` - HTTP wrapper for plan creation
  - `tool_create_choch_plan()` - HTTP wrapper for CHOCH plans
  - `tool_create_rejection_wick_plan()` - HTTP wrapper for rejection wick plans
  - `tool_create_order_block_plan()` - HTTP wrapper for order block plans
  - `tool_create_bracket_trade_plan()` - HTTP wrapper for bracket trades
  - `tool_create_range_scalp_plan()` - HTTP wrapper for range scalping
  - `tool_create_micro_scalp_plan()` - HTTP wrapper for micro-scalp
- **Dependencies**: 
  - `httpx` - Async HTTP client
  - `infra.tolerance_helper`

### 4. **`app/auto_execution_api.py`**
- **Purpose**: FastAPI REST API endpoints
- **Key Endpoints**:
  - `POST /auto-execution/plan` - Create general plan
  - `POST /auto-execution/choch` - Create CHOCH plan
  - `POST /auto-execution/rejection-wick` - Create rejection wick plan
  - `POST /auto-execution/order-block` - Create order block plan
  - `POST /auto-execution/bracket` - Create bracket trade
  - `POST /auto-execution/range-scalp` - Create range scalp plan
  - `GET /auto-execution/status` - Get system status
  - `DELETE /auto-execution/plan/{plan_id}` - Cancel plan
- **Dependencies**: 
  - `chatgpt_auto_execution_integration`
  - `auto_execution_system`
  - `infra.tolerance_helper`

## Integration Files

### 5. **`desktop_agent.py`**
- **Purpose**: Main ChatGPT agent that uses auto-execution tools
- **Integration Points**:
  - Imports `chatgpt_auto_execution_tools` functions
  - Registers tools with ChatGPT tool registry
  - Makes tools available to ChatGPT for plan creation
- **Key Sections**:
  - Tool imports (lines ~40, ~5848)
  - Tool registration (lines ~13081-13117)

### 6. **`main_api.py`** and **`app/main_api.py`**
- **Purpose**: Web interface and API server
- **Integration Points**:
  - Includes `auto_execution_router` from `app/auto_execution_api.py`
  - Web interface at `/auto-execution/view` for viewing plans
  - Status endpoints for monitoring
- **Key Endpoints**:
  - `GET /auto-execution/view` - Web UI for viewing plans
  - `GET /api/auto-execution/status` - System status
  - `POST /api/auto-execution/cancel/{plan_id}` - Cancel plan
  - `POST /api/range-scalp-plan` - Create range scalp plan

## Supporting Infrastructure Files

### 7. **`infra/tolerance_helper.py`**
- **Purpose**: Calculate price tolerance based on symbol type
- **Used By**: 
  - `chatgpt_auto_execution_integration.py`
  - `chatgpt_auto_execution_tools.py`
  - `app/auto_execution_api.py`
- **Function**: `get_price_tolerance(symbol)` - Returns tolerance (BTC=100, XAU=5, Forex=0.001)

### 8. **`infra/mt5_service.py`**
- **Purpose**: MT5 connection and trade execution
- **Used By**: 
  - `auto_execution_system.py` (for executing trades)
- **Key Methods**:
  - `connect()` - Connect to MT5
  - `get_quote()` - Get current price
  - `open_order()` - Execute trade

### 9. **`infra/range_scalping_analysis.py`**
- **Purpose**: Range scalping analysis for `range_scalp_confluence` condition
- **Used By**: 
  - `auto_execution_system.py` (in `_check_conditions()`)
- **Function**: `analyse_range_scalp_opportunity()` - Calculates confluence score

### 10. **`infra/range_scalping_risk_filters.py`**
- **Purpose**: Risk filters for range scalping
- **Used By**: 
  - `infra/range_scalping_analysis.py`
- **Function**: Validates range scalping opportunities

### 11. **`infra/discord_alert_dispatcher.py`**
- **Purpose**: Detects market conditions and sends Discord alerts
- **Relationship**: 
  - Alerts trigger ChatGPT to create auto-execution plans
  - Not directly integrated, but alerts are the source of many plans

### 12. **M1 Microstructure Integration** (Optional)
- **`infra/m1_microstructure_analyzer.py`** - M1 analysis
- **`infra/m1_data_fetcher.py`** - M1 data fetching
- **`infra/m1_refresh_manager.py`** - M1 data refresh management
- **Used By**: 
  - `auto_execution_system.py` (for M1 condition validation)

## Configuration Files

### 13. **`openai.yaml`**
- **Purpose**: ChatGPT tool definitions and instructions
- **Key Sections**:
  - Tool definitions for auto-execution functions
  - Instructions for when/how to create plans
  - Alert-to-condition mapping
  - Multi-timeframe guidance

### 14. **`docs/ChatGPT Knowledge Documents/AUTO_EXECUTION_CHATGPT_KNOWLEDGE.md`**
- **Purpose**: Comprehensive knowledge base for ChatGPT
- **Content**:
  - How auto-execution works
  - Available tools and parameters
  - Condition types and usage
  - Best practices and examples

## Database Files

### 15. **`data/auto_execution.db`**
- **Purpose**: SQLite database storing all trade plans
- **Schema**: `trade_plans` table with columns:
  - `plan_id`, `symbol`, `direction`, `entry_price`, `stop_loss`, `take_profit`
  - `volume`, `conditions` (JSON), `created_at`, `created_by`
  - `status`, `expires_at`, `executed_at`, `ticket`, `notes`

## Documentation Files

### 16. **Issue Tracking & Fix Documentation**:
- `AUTO_EXECUTION_SYSTEM_ISSUES.md` - Initial issues found
- `AUTO_EXECUTION_ADDITIONAL_ISSUES.md` - Additional issues
- `AUTO_EXECUTION_FINAL_ISSUES.md` - Final issues
- `AUTO_EXECUTION_FIXES_IMPLEMENTED.md` - Fixes summary
- `AUTO_EXECUTION_ALL_FIXES_COMPLETE.md` - All fixes complete
- `AUTO_EXECUTION_MONITORING_ISSUES.md` - Monitoring issues
- `AUTO_EXECUTION_MONITORING_FIXES_IMPLEMENTED.md` - Monitoring fixes

### 17. **Other Documentation**:
- `STRUCTURE_CONFIRMATION_EXPLANATION.md` - Explains `structure_confirmation` condition
- `docs/AUTO_EXECUTION_SYSTEM_COMPLETE.md` - System overview
- `docs/AUTO_EXECUTION_CHATGPT_INSTRUCTIONS.md` - ChatGPT instructions

## Test Files

### 18. **`test_range_scalp_auto_execution.py`**
- **Purpose**: Tests for range scalping auto-execution

### 19. **`integrate_auto_execution.py`**
- **Purpose**: Integration script (may be legacy)

## Data Flow

```
ChatGPT Request
    ↓
desktop_agent.py (tool registration)
    ↓
chatgpt_auto_execution_tools.py (HTTP call)
    ↓
app/auto_execution_api.py (API endpoint)
    ↓
chatgpt_auto_execution_integration.py (business logic)
    ↓
auto_execution_system.py (plan storage)
    ↓
data/auto_execution.db (persistence)
    ↓
auto_execution_system.py (monitoring loop)
    ↓
infra/mt5_service.py (trade execution)
```

## Key Dependencies

### External Libraries:
- `sqlite3` - Database
- `threading` - Thread safety
- `MetaTrader5` - MT5 connection
- `httpx` - HTTP client (for tools)
- `fastapi` - API framework
- `pydantic` - Data validation

### Internal Modules:
- `infra.mt5_service` - MT5 operations
- `infra.tolerance_helper` - Price tolerance
- `infra.range_scalping_analysis` - Range analysis
- `infra.m1_microstructure_analyzer` - M1 analysis (optional)
- `infra.m1_data_fetcher` - M1 data (optional)
- `infra.m1_refresh_manager` - M1 refresh (optional)

## Summary

**Total Files**: ~19 core files + documentation

**Core System**: 4 files
- `auto_execution_system.py` (main engine)
- `chatgpt_auto_execution_integration.py` (integration layer)
- `chatgpt_auto_execution_tools.py` (HTTP tools)
- `app/auto_execution_api.py` (REST API)

**Integration**: 2 files
- `desktop_agent.py` (ChatGPT integration)
- `main_api.py` / `app/main_api.py` (Web interface)

**Supporting**: 6+ infrastructure files
- Tolerance helper, MT5 service, range scalping, M1 integration, etc.

**Configuration**: 2 files
- `openai.yaml` (ChatGPT config)
- Knowledge documents

**Database**: 1 file
- `data/auto_execution.db` (SQLite)

