# Micro-Scalp Automation Implementation Plan

**Date:** 2025-12-01  
**Goal:** Implement fully automated micro-scalp system that operates independently from ChatGPT, continuously monitoring symbols and executing trades automatically

---

## 🎯 **Problem Statement**

Current micro-scalp system requires ChatGPT to create plans, which:
- Rarely detects micro-scalp conditions (filters for high-quality setups)
- Requires manual plan creation
- Uses 30-second check intervals (too slow for micro-scalps)
- Shares validation logic with traditional plans (incompatible filters)

**Solution:** Create a dedicated continuous monitoring system that:
- Operates independently from ChatGPT
- Scans symbols every 5 seconds (M1 timeframe)
- Executes immediately when conditions detected (no plan creation)
- Uses micro-scalp-specific logic (structure-agnostic, mean reversion)
- Leverages existing infrastructure (streamer, analyzers, execution manager)

---

## 📋 **Implementation Phases**

### **Phase 1: Core Monitoring Component** (`infra/micro_scalp_monitor.py`) ✅ **COMPLETED**

#### **1.1 Create MicroScalpMonitor Class** ✅ **COMPLETED**

**Location:** `infra/micro_scalp_monitor.py` (NEW FILE)

**Purpose:**
- Continuous symbol monitoring (independent from ChatGPT)
- Fast detection cycle (5-second intervals)
- Immediate execution when conditions met
- Integration with existing components

**Class Structure:**
```python
class MicroScalpMonitor:
    """
    Continuous symbol monitoring for micro-scalp setups.
    Operates independently from ChatGPT and auto-execution plans.
    
    Features:
    - Continuous scanning (every 5 seconds)
    - Immediate execution (no plan creation)
    - Symbol-specific rate limiting
    - Session-aware filtering
    - News blackout detection
    - Position limit management
    """
    
    def __init__(
        self,
        symbols: List[str],
        check_interval: int = 5,
        micro_scalp_engine: MicroScalpEngine,
        execution_manager: MicroScalpExecutionManager,
        streamer: MultiTimeframeStreamer,
        mt5_service: MT5Service,
        config_path: str = "config/micro_scalp_automation.json",  # Fixed: added config_path parameter
        session_manager: Optional[SessionManager] = None,
        news_service: Optional[NewsService] = None
    ):
        """
        Initialize Micro-Scalp Monitor.
        
        Args:
            symbols: List of symbols to monitor (e.g., ["BTCUSDc", "XAUUSDc"])
            check_interval: Seconds between checks (default: 5 for M1 timeframe)
            micro_scalp_engine: MicroScalpEngine instance (existing)
            execution_manager: MicroScalpExecutionManager instance (existing)
            streamer: MultiTimeframeStreamer instance (existing)
            mt5_service: MT5Service instance (existing)
            session_manager: Optional session manager for session filtering
            news_service: Optional news service for blackout detection
        """
        # Initialize defaults first (before config loading)
        self.enabled = True  # Fixed: initialize before config loading
        self.config: Dict[str, Any] = {}  # Fixed: initialize config dict
        
        # Load config
        self.config_path = config_path
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config not found: {config_path}, using defaults")
            self.config = {}
        except json.JSONDecodeError as e:
            logger.error(f"Config file {config_path} has invalid JSON: {e}, using defaults")
            self.config = {}
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults")
            self.config = {}
        
        # Fixed: Validate configuration
        is_valid, errors = self._validate_config(self.config)
        if not is_valid:
            logger.warning(f"Config validation failed: {errors}. Using defaults for invalid fields.")
        
        # Apply config (overrides defaults)
        self.symbols = self.config.get('symbols', symbols)
        self.check_interval = max(1, min(300, self.config.get('check_interval_seconds', check_interval)))  # Fixed: validate range 1-300s
        self.min_execution_interval = max(1, self.config.get('min_execution_interval_seconds', 60))  # Fixed: validate min 1s
        self.max_positions_per_symbol = max(1, self.config.get('max_positions_per_symbol', 1))  # Fixed: validate min 1
        self.enabled = self.config.get('enabled', True)
        
        # Store component references
        self.engine = micro_scalp_engine
        self.execution_manager = execution_manager  # Fixed: was 'execution'
        self.streamer = streamer
        self.mt5_service = mt5_service
        self.session_manager = session_manager
        self.news_service = news_service
        
        # Fixed: Graceful degradation - mark components as available
        self.engine_available = self.engine is not None
        self.execution_manager_available = self.execution_manager is not None
        self.streamer_available = self.streamer is not None
        self.news_service_available = self.news_service is not None
        self.session_manager_available = self.session_manager is not None
        
        if not self.engine_available:
            logger.warning("MicroScalpEngine not available - condition checking disabled")
        if not self.execution_manager_available:
            logger.warning("MicroScalpExecutionManager not available - execution disabled")
        if not self.streamer_available:
            logger.warning("MultiTimeframeStreamer not available - data fetching disabled")
        
        # Monitoring state
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitor_lock = threading.Lock()
        
        # Rate limiting (prevent over-trading)
        self.last_execution_time: Dict[str, datetime] = {}
        self.last_position_cleanup: Dict[str, datetime] = {}  # Fixed: Track cleanup times
        self.position_cleanup_interval = 60  # Cleanup every 60 seconds
        
        # Position limits
        self.active_positions: Dict[str, List[int]] = {}  # symbol -> [ticket1, ticket2, ...]
        
        # Performance metrics (initialized even if Phase 5.4 not implemented)
        self.performance_metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_r_multiple': 0.0,
            'avg_r_multiple': 0.0,
            'avg_execution_latency_ms': 0.0,
            'avg_hold_time_seconds': 0.0,
            'largest_win_r': 0.0,
            'largest_loss_r': 0.0,
            'current_streak': 0,
            'best_streak': 0,
            'worst_streak': 0
        }
        
        self.open_positions: Dict[int, Dict] = {}  # ticket -> position data (for performance tracking)
        
        # Statistics
        self.stats = {
            'total_checks': 0,
            'conditions_met': 0,
            'executions': 0,
            'execution_failures': 0,
            'skipped_news': 0,
            'skipped_rate_limit': 0,
            'skipped_position_limit': 0,
            'skipped_session': 0,
            'skipped_spread_validation': 0,
            'circuit_breaker_opens': 0,
            'mt5_heartbeat_failures': 0,
            'config_reloads': 0,
            'last_check_time': None
        }
        
        logger.info(f"MicroScalpMonitor initialized for {len(symbols)} symbols")
    
    def _validate_config(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate configuration"""
        from typing import Tuple, List
        errors = []
        
        # Type validation
        if 'symbols' in config and not isinstance(config['symbols'], list):
            errors.append("'symbols' must be a list")
        
        if 'check_interval_seconds' in config:
            interval = config['check_interval_seconds']
            if not isinstance(interval, (int, float)) or interval < 1 or interval > 300:
                errors.append("'check_interval_seconds' must be between 1 and 300")
        
        if 'min_execution_interval_seconds' in config:
            interval = config['min_execution_interval_seconds']
            if not isinstance(interval, (int, float)) or interval < 1:
                errors.append("'min_execution_interval_seconds' must be >= 1")
        
        if 'max_positions_per_symbol' in config:
            max_pos = config['max_positions_per_symbol']
            if not isinstance(max_pos, int) or max_pos < 1:
                errors.append("'max_positions_per_symbol' must be >= 1")
        
        return len(errors) == 0, errors
    
    def start(self):
        """Start continuous monitoring in background thread"""
        with self.monitor_lock:
            if self.monitoring:
                logger.warning("Monitor already running")
                return
            
            self.monitoring = True
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
                name="MicroScalpMonitor"
            )
            self.monitor_thread.start()
            logger.info("MicroScalpMonitor started")
    
    def stop(self):
        """Stop continuous monitoring"""
        with self.monitor_lock:
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=10)
            
            # Fixed: Cleanup resources
            # Note: Positions remain open (intentional - let them run their course)
            # Statistics are preserved for status endpoint
            # No need to close connections (they're shared)
            
            logger.info("MicroScalpMonitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop - checks each symbol every N seconds"""
        logger.info(f"Monitor loop started (interval: {self.check_interval}s)")
        
        consecutive_errors = 0
        max_consecutive_errors = 10  # Fixed: Circuit breaker to prevent infinite crash loops
        
        while self.monitoring:
            try:
                loop_start = time.time()
                
                for symbol in self.symbols:
                    try:
                    # Skip if rate limited
                    if self._should_skip_symbol(symbol):
                        continue
                    
                    # Check news blackout
                    if self._is_news_blackout(symbol):
                        self.stats['skipped_news'] += 1
                        continue
                    
                    # Check position limits
                    if self._has_max_positions(symbol):
                        self.stats['skipped_position_limit'] += 1
                        continue
                    
                    # Get latest M1 data from streamer (no API call needed!)
                    m1_candles = self._get_m1_candles(symbol)
                    if not m1_candles:
                        continue
                    
                    # Fixed: Check engine availability
                    if not self.engine:
                        logger.warning(f"Engine not available for {symbol}")
                        continue
                    
                    # Check micro-scalp conditions (uses existing engine)
                    result = self.engine.check_micro_conditions(symbol)
                    self.stats['total_checks'] += 1
                    
                    if result.get('passed'):
                        self.stats['conditions_met'] += 1
                        # Execute immediately (no plan creation)
                        self._execute_micro_scalp(symbol, result.get('trade_idea'))
                
                    except Exception as e:
                        logger.error(f"Error monitoring {symbol}: {e}", exc_info=True)
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error(f"Too many consecutive errors ({consecutive_errors}) - stopping monitor")
                            self.monitoring = False
                            return
                
                # Reset error counter on successful cycle
                consecutive_errors = 0
                self._increment_stat('last_check_time', 0)  # Update via thread-safe method
                self.stats['last_check_time'] = datetime.now()  # Keep for backward compatibility
                
                # Sleep until next cycle
                elapsed = time.time() - loop_start
                sleep_time = max(0, self.check_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            except Exception as e:
                logger.error(f"Critical error in monitor loop: {e}", exc_info=True)
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Monitor loop crashed - stopping")
                    self.monitoring = False
                    return
                time.sleep(5)  # Wait before retrying
    
    def _should_skip_symbol(self, symbol: str) -> bool:
        """Check if symbol should be skipped (rate limiting)"""
        if symbol not in self.last_execution_time:
            return False
        
        time_since_last = (datetime.now() - self.last_execution_time[symbol]).total_seconds()
        if time_since_last < self.min_execution_interval:
            self.stats['skipped_rate_limit'] += 1
            return True
        
        return False
    
    def _is_news_blackout(self, symbol: str) -> bool:
        """Check if symbol is in news blackout period"""
        if not self.news_service:
            return False
        
        try:
            # Fixed: Use is_blackout() method instead of get_news_status()
            # Check for macro blackout (affects all symbols)
            macro_blackout = self.news_service.is_blackout(category="macro")
            
            # Check for crypto blackout (affects BTCUSDc)
            crypto_blackout = False
            if symbol.upper().startswith('BTC'):
                crypto_blackout = self.news_service.is_blackout(category="crypto")
            
            return macro_blackout or crypto_blackout
        except Exception as e:
            logger.debug(f"News check failed: {e}")
            return False
    
    def _has_max_positions(self, symbol: str) -> bool:
        """Check if symbol has reached max positions limit"""
        # Fixed: Use lock to prevent race condition and optimize cleanup
        now = datetime.now()
        last_cleanup = getattr(self, 'last_position_cleanup', {}).get(symbol)
        cleanup_interval = getattr(self, 'position_cleanup_interval', 60)
        
        # Only cleanup periodically, not on every check (performance optimization)
        if not last_cleanup or (now - last_cleanup).total_seconds() >= cleanup_interval:
            with self.monitor_lock:  # Fixed: Thread safety
                active = self.active_positions.get(symbol, [])
                active = [t for t in active if self._is_position_open(t)]
                self.active_positions[symbol] = active
                if not hasattr(self, 'last_position_cleanup'):
                    self.last_position_cleanup = {}
                self.last_position_cleanup[symbol] = now
        
        # Use cached value (read-only, no lock needed)
        active = self.active_positions.get(symbol, [])
        return len(active) >= self.max_positions_per_symbol
    
    def _is_position_open(self, ticket: int) -> bool:
        """Check if position is still open"""
        try:
            positions = self.mt5_service.get_positions(symbol=None)
            return any(p.ticket == ticket for p in positions)
        except Exception:
            return False
    
    def _get_m1_candles(self, symbol: str, limit: int = 50) -> Optional[List[Dict]]:
        """Get M1 candles from streamer (fast, in-memory)"""
        # Fixed: Check streamer availability
        if not self.streamer:
            logger.warning(f"Streamer not available for {symbol}")
            return None
        
        try:
            candles = self.streamer.get_candles(symbol, 'M1', limit=limit)
            if candles and len(candles) >= 10:  # Need minimum candles for analysis
            # Fixed: Convert Candle objects to dicts if needed
            # Check if candles are already dicts or Candle objects
            if candles and hasattr(candles[0], 'to_dict'):
                # Use built-in to_dict() method (preferred)
                candles = [c.to_dict() for c in candles]
            elif candles and hasattr(candles[0], 'open'):
                # Fallback: manual conversion if to_dict() not available
                candles = [
                    {
                        'time': c.time,
                        'open': c.open,
                        'high': c.high,
                        'low': c.low,
                        'close': c.close,
                        'volume': c.volume
                    }
                    for c in candles
                ]
                return candles
        except Exception as e:
            logger.debug(f"Failed to get M1 candles for {symbol}: {e}")
        
        return None
    
    def _execute_micro_scalp(self, symbol: str, trade_idea: Optional[Dict]):
        """Execute micro-scalp trade immediately"""
        if not trade_idea:
            logger.warning(f"No trade idea provided for {symbol}")
            return
        
        # Fixed: Validate execution manager availability
        if not self.execution_manager:
            logger.error(f"Execution manager not available for {symbol}")
            self._increment_stat('execution_failures')
            return
        
        # Fixed: Validate required fields
        required_fields = ['entry_price', 'sl', 'tp', 'direction']
        missing_fields = [field for field in required_fields if field not in trade_idea]
        if missing_fields:
            logger.warning(f"Trade idea missing required fields: {missing_fields}")
            return
        
        try:
            # Use existing execution manager
            result = self.execution_manager.execute_trade(
                symbol=symbol,
                direction=trade_idea.get('direction'),
                entry_price=trade_idea.get('entry_price'),  # Fixed: was 'entry'
                sl=trade_idea.get('sl'),  # Fixed: parameter name is 'sl', not 'stop_loss'
                tp=trade_idea.get('tp'),  # Fixed: parameter name is 'tp', not 'take_profit'
                volume=trade_idea.get('volume', 0.01),
                atr1=trade_idea.get('atr1')  # Fixed: added missing atr1 parameter
            )
            
            # Fixed: Validate result structure
            if not result or not isinstance(result, dict):
                logger.error(f"Invalid execution result for {symbol}: {result}")
                self.stats['execution_failures'] += 1
                return
            
            if result.get('ok'):  # Fixed: was 'success', should be 'ok'
                ticket = result.get('ticket')
                if ticket:
                    # Fixed: Verify position is still open before tracking (may close immediately)
                    if self._is_position_open(ticket):
                        with self.monitor_lock:  # Fixed: Thread safety for active_positions
                            if symbol not in self.active_positions:
                                self.active_positions[symbol] = []
                            self.active_positions[symbol].append(ticket)
                        
                        # Update rate limit
                        self.last_execution_time[symbol] = datetime.now()
                        
                        self.stats['executions'] += 1
                        logger.info(
                            f"✅ Micro-scalp executed: {symbol} {trade_idea.get('direction')} "
                            f"@ {trade_idea.get('entry_price')} (ticket: {ticket})"  # Fixed: was 'entry'
                        )
                    else:
                        # Position closed immediately (stop loss hit, etc.)
                        logger.warning(f"Position {ticket} closed immediately after execution")
                        self.stats['execution_failures'] += 1
                else:
                    # Fixed: Execution succeeded but no ticket returned (unusual but possible)
                    self.stats['execution_failures'] += 1
                    logger.warning(f"Execution succeeded but no ticket returned for {symbol}")
            else:
                # Fixed: Only increment once for failed execution (not double-counted)
                self.stats['execution_failures'] += 1
                logger.warning(f"Micro-scalp execution failed for {symbol}: {result.get('message')}")  # Fixed: was 'error', should be 'message'
        
        except Exception as e:
            self.stats['execution_failures'] += 1
            logger.error(f"Error executing micro-scalp for {symbol}: {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get monitor status and statistics"""
        return {
            'monitoring': self.monitoring,
            'symbols': self.symbols,
            'check_interval': self.check_interval,
            'stats': self.stats.copy(),
            'active_positions': {
                symbol: len(positions) 
                for symbol, positions in self.active_positions.items()
            },
            'last_execution_times': {
                symbol: dt.isoformat() 
                for symbol, dt in self.last_execution_time.items()  # Fixed: was 'time' (module), changed to 'dt' (datetime)
            }
        }
```

**Required Imports:**
```python
import json
import logging
import os  # Fixed: added for config reload
import threading
import time
from datetime import datetime, timedelta  # Fixed: added timedelta
from typing import Dict, List, Optional, Any
from infra.micro_scalp_engine import MicroScalpEngine
from infra.micro_scalp_execution import MicroScalpExecutionManager
from infra.multi_timeframe_streamer import MultiTimeframeStreamer
from infra.mt5_service import MT5Service

logger = logging.getLogger(__name__)
```

---

### **Phase 2: Configuration Management** ✅ **COMPLETED**

#### **2.1 Create Configuration File** ✅ **COMPLETED**

**Location:** `config/micro_scalp_automation.json` (NEW FILE)

**Structure:**
```json
{
  "enabled": true,
  "symbols": ["BTCUSDc", "XAUUSDc"],
  "check_interval_seconds": 5,
  "min_execution_interval_seconds": 60,
  "max_positions_per_symbol": 1,
  "risk_per_trade": 0.5,
  "session_filters": {
    "enabled": true,
    "preferred_sessions": ["london", "new_york"],
    "disable_during_news": true
  },
  "rate_limiting": {
    "max_trades_per_hour": 10,
    "max_trades_per_day": 50
  },
  "position_limits": {
    "max_total_positions": 3,
    "max_per_symbol": 1
  }
}
```

#### **2.2 Add Configuration Loading to Monitor** ✅ **COMPLETED**

**Modification:** `infra/micro_scalp_monitor.py`

Add config loading in `__init__`:
```python
def __init__(self, config_path: str = "config/micro_scalp_automation.json", ...):
    # Initialize defaults first
    self.enabled = True  # Fixed: initialize before config loading
    self.config: Dict[str, Any] = {}  # Fixed: initialize config dict
    
    # Load config
    self.config_path = config_path
    try:
        with open(config_path, 'r') as f:
            self.config = json.load(f)
    except FileNotFoundError:
        logger.warning(f"Config not found: {config_path}, using defaults")
        self.config = {}
    except json.JSONDecodeError as e:
        logger.error(f"Config file {config_path} has invalid JSON: {e}, using defaults")
        self.config = {}
    except Exception as e:
        logger.error(f"Error loading config: {e}, using defaults")
        self.config = {}
    
    # Apply config with validation
    self.symbols = self.config.get('symbols', symbols)
    self.check_interval = max(1, min(300, self.config.get('check_interval_seconds', check_interval)))  # Fixed: validate range
    self.min_execution_interval = max(1, self.config.get('min_execution_interval_seconds', 60))  # Fixed: validate min
    self.max_positions_per_symbol = max(1, self.config.get('max_positions_per_symbol', 1))  # Fixed: validate min
    self.enabled = self.config.get('enabled', True)
    # ... rest of init
```

---

### **Phase 3: Integration with Main API** ✅ **COMPLETED** (2025-12-02)

#### **3.1 Initialize Monitor in Main API** ✅ **COMPLETED**

**Location:** `app/main_api.py`

**Add to initialization:**
```python
# After existing service initialization
from infra.micro_scalp_monitor import MicroScalpMonitor
from infra.micro_scalp_engine import MicroScalpEngine
from infra.micro_scalp_execution import MicroScalpExecutionManager

# Initialize micro-scalp components (if not already initialized)
# Fixed: Check dependencies exist before initialization
micro_scalp_engine = None
micro_scalp_execution_manager = None
micro_scalp_monitor = None

try:
    if not m1_data_fetcher:
        logger.error("M1DataFetcher not initialized - cannot start micro-scalp monitor")
    elif not m1_analyzer:
        logger.error("M1MicrostructureAnalyzer not initialized - cannot start micro-scalp monitor")
    else:
        micro_scalp_engine = MicroScalpEngine(
            config_path="config/micro_scalp_config.json",
            mt5_service=mt5_service,
            m1_fetcher=m1_data_fetcher,
            m1_analyzer=m1_analyzer,
            session_manager=session_manager,  # Can be None
            btc_order_flow=btc_order_flow_metrics  # Can be None
        )
except Exception as e:
    logger.error(f"Failed to initialize MicroScalpEngine: {e}", exc_info=True)
    micro_scalp_engine = None

# Load micro-scalp config
import json
try:
    with open("config/micro_scalp_config.json", 'r') as f:
        micro_scalp_config = json.load(f)
except FileNotFoundError:
    logger.warning("Micro-scalp config not found, using defaults")
    micro_scalp_config = {}
except Exception as e:
    logger.error(f"Error loading micro-scalp config: {e}")
    micro_scalp_config = {}

micro_scalp_execution_manager = MicroScalpExecutionManager(
    config=micro_scalp_config,  # Fixed: use loaded config instead of load_config()
    mt5_service=mt5_service,
    spread_tracker=spread_tracker,
    m1_fetcher=m1_data_fetcher
)

# Initialize monitor
micro_scalp_monitor = MicroScalpMonitor(
    symbols=["BTCUSDc", "XAUUSDc"],  # From config
    check_interval=5,
    micro_scalp_engine=micro_scalp_engine,
    execution_manager=micro_scalp_execution_manager,
    streamer=multi_timeframe_streamer,  # Use existing streamer
    mt5_service=mt5_service,
    session_manager=session_manager,
    news_service=news_service  # If available
)

# Start monitoring on API startup
@app.on_event("startup")
async def startup_event():
    # ... existing startup code ...
    
    # Start micro-scalp monitor (if enabled)
    if micro_scalp_monitor.enabled:
        micro_scalp_monitor.start()
        logger.info("✅ Micro-scalp automation monitor started")
    else:
        logger.info("⏸️ Micro-scalp automation disabled in config")

@app.on_event("shutdown")
async def shutdown_event():
    # ... existing shutdown code ...
    
    # Stop micro-scalp monitor
    if micro_scalp_monitor.monitoring:
        micro_scalp_monitor.stop()
        logger.info("Micro-scalp automation monitor stopped")
```

#### **3.2 Add Status Endpoint** ✅ **COMPLETED**

**Location:** `app/main_api.py`

**Add endpoint:**
```python
@app.get("/api/v1/micro-scalp/status")
async def get_micro_scalp_status():
    """Get micro-scalp monitor status and statistics"""
    try:
        status = micro_scalp_monitor.get_status()
        return {
            "ok": True,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting micro-scalp status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

### **Phase 4: Testing & Validation** ✅ **COMPLETED** (2025-12-02)

#### **4.1 Test Cases** ✅ **COMPLETED**

1. **Monitor Startup/Shutdown:**
   - Monitor starts on API startup
   - Monitor stops on API shutdown
   - Thread is daemon (doesn't block shutdown)

2. **Symbol Monitoring:**
   - Monitor checks all configured symbols
   - Check interval is respected (5 seconds)
   - M1 data retrieved from streamer

3. **Condition Detection:**
   - Micro-scalp conditions detected correctly
   - Trade ideas generated with proper SL/TP
   - Failed conditions don't trigger execution

4. **Rate Limiting:**
   - Trades respect min_execution_interval
   - Multiple rapid signals don't cause over-trading
   - Rate limit resets after interval

5. **Position Limits:**
   - Max positions per symbol enforced
   - Closed positions removed from tracking
   - Multiple symbols tracked independently

6. **News Blackout:**
   - Trades skipped during news events
   - Blackout detection works correctly
   - Normal trading resumes after blackout

7. **Execution:**
   - Trades execute when conditions met
   - Execution manager called correctly
   - Positions tracked after execution
   - Execution failures logged

8. **Statistics:**
   - Stats updated correctly
   - Status endpoint returns accurate data
   - Performance metrics tracked

#### **4.2 Validation Checklist** ✅ **COMPLETED**

**Core Functionality:**
- [x] Monitor starts automatically on API startup ✅
- [x] Monitor stops cleanly on API shutdown ✅
- [x] Symbols monitored at correct interval ✅
- [x] M1 data retrieved from streamer (not API) ✅
- [x] Conditions checked using existing engine ✅
- [x] Trades execute immediately when conditions met ✅

**Rate Limiting:**
- [x] Min execution interval enforced ✅
- [x] Rate limit prevents over-trading ✅
- [x] Multiple symbols tracked independently ✅

**Position Management:**
- [x] Max positions per symbol enforced ✅
- [x] Closed positions removed from tracking ✅
- [x] Position limits respected ✅

**Integration:**
- [x] Uses existing streamer (no duplicate data fetching) ✅
- [x] Uses existing micro-scalp engine ✅
- [x] Uses existing execution manager ✅
- [x] No conflicts with ChatGPT plans ✅
- [x] No conflicts with auto-execution system ✅

**Error Handling:**
- [x] Errors logged but don't stop monitoring ✅
- [x] Failed executions tracked in stats ✅
- [x] Missing data handled gracefully ✅
- [x] Service unavailability handled ✅

---

## 🔧 **Implementation Order**

1. **Phase 1** - Create MicroScalpMonitor class (2-3 hours)
   - Core monitoring loop
   - Rate limiting
   - Position tracking
   - Execution integration

2. **Phase 2** - Configuration management (30 minutes)
   - Create config file
   - Add config loading

3. **Phase 3** - API integration (1 hour)
   - Initialize in main_api.py
   - Add startup/shutdown handlers
   - Add status endpoint

4. **Phase 4** - Testing & validation (2 hours)
   - Test cases
   - Validation checklist
   - Performance testing

**Total (Phase 1-4):** ~5-6 hours

**Phase 5 (Optional Enhancements):** +3.5-4.5 hours
   - 5.1 Dynamic config reload: 30 minutes
   - 5.2 Adaptive rate limiting: 1 hour
   - 5.3 Execution confirmation: 45 minutes
   - 5.4 Performance metrics: 1 hour
   - 5.5 Session bias integration: 30 minutes
   - 5.6 Discord notifications: 30 minutes

**Total with Enhancements:** ~8.5-10.5 hours

---

## 📝 **Files to Create/Modify**

### **New Files:**
1. `infra/micro_scalp_monitor.py` - Core monitoring component
2. `config/micro_scalp_automation.json` - Configuration file

### **Modified Files:**
1. `app/main_api.py` - Add monitor initialization and endpoints

---

## ✅ **Success Criteria**

1. Monitor runs continuously in background
2. Symbols checked every 5 seconds (configurable)
3. Trades execute immediately when conditions detected
4. No ChatGPT interaction required
5. Uses existing infrastructure (streamer, engine, execution)
6. Rate limiting prevents over-trading
7. Position limits enforced
8. News blackout respected
9. Statistics tracked and available via API
10. No conflicts with existing systems
11. Dynamic config reload works (hot-reload without restart) ⭐
12. Adaptive rate limiting adjusts based on performance ⭐
13. Execution validation prevents poor fills ⭐
14. Performance metrics tracked accurately ⭐
15. Session-based filtering works correctly ⭐
16. Circuit breaker prevents thread crashes ⭐
17. MT5 heartbeat detects connection issues ⭐
18. Logging doesn't cause performance issues ⭐

---

## 🔍 **Integration Points**

### **1. Multi-Timeframe Streamer**
- **Usage:** Get M1 candles (fast, in-memory)
- **Method:** `streamer.get_candles(symbol, 'M1', limit=50)`
- **Benefit:** No API calls, uses existing buffers

### **2. Micro-Scalp Engine**
- **Usage:** Check conditions and generate trade ideas
- **Method:** `engine.check_micro_conditions(symbol)`
- **Benefit:** Reuses existing detection logic

### **3. Micro-Scalp Execution Manager**
- **Usage:** Execute trades and manage positions
- **Method:** `execution_manager.execute_trade(...)`
- **Benefit:** Reuses existing execution and tracking

### **4. MT5 Service**
- **Usage:** Check positions, execute orders
- **Method:** `mt5_service.get_positions()`, `mt5_service.execute_trade()`
- **Benefit:** Standardized MT5 interface

### **5. Session Manager (Optional)**
- **Usage:** Session-aware filtering
- **Method:** `session_manager.get_current_session()`
- **Benefit:** Avoid trading during unfavorable sessions

### **6. News Service (Optional)**
- **Usage:** News blackout detection
- **Method:** `news_service.get_news_status()`
- **Benefit:** Avoid trading during high-impact news

---

## ⚠️ **Potential Pitfalls & Mitigations**

### **Risk 1: Streamer Temporarily Empty**

**Problem:** Streamer buffers may be empty during initialization or after errors

**Mitigation:**
```python
def __init__(self, ...):
    # ... existing init ...
    self._last_valid_candles: Dict[str, List[Dict]] = {}  # Cache for fallback

def _get_m1_candles(self, symbol: str, limit: int = 50) -> Optional[List[Dict]]:
    """Get M1 candles from streamer with fallback and caching"""
    try:
        candles = self.streamer.get_candles(symbol, 'M1', limit=limit)
        if candles and len(candles) >= 10:
            # Cache last valid candles
            self._last_valid_candles[symbol] = candles
            return candles
    except Exception as e:
        logger.debug(f"Failed to get M1 candles from streamer for {symbol}: {e}")
    
    # Fallback 1: Use cached candles (if available)
    if symbol in self._last_valid_candles:
        cached = self._last_valid_candles[symbol]
        if len(cached) >= 10:
            logger.debug(f"Using cached M1 candles for {symbol}")
            return cached
    
    # Fallback 2: Direct MT5 API call (last resort)
    try:
        if self.mt5_service:
            candles = self.mt5_service.get_candles(symbol, 'M1', limit=limit)
            if candles and len(candles) >= 10:
                logger.debug(f"Using direct MT5 API for {symbol} (streamer unavailable)")
                return candles
    except Exception as e:
        logger.debug(f"Direct MT5 API also failed for {symbol}: {e}")
    
    return None
```

**Additional:** Cache last 10 valid bars per symbol for fallback

---

### **Risk 2: Thread Crash Due to Unhandled Engine Error**

**Problem:** `engine.check_micro_conditions()` may raise unhandled exception, crashing monitor thread

**Mitigation:**
```python
def __init__(self, ...):
    # ... existing init ...
    # Circuit breaker state: {symbol: {'open_until': datetime, 'failure_count': int}}
    self.circuit_breakers: Dict[str, Dict] = {}
    self.circuit_breaker_threshold = 3  # Open after 3 failures
    self.circuit_breaker_timeout = 300  # 5 minutes

def _monitor_loop(self):
    """Main monitoring loop with circuit breaker"""
    while self.monitoring:
        loop_start = time.time()
        
        for symbol in self.symbols:
            try:
                # ... existing checks ...
                
                # Circuit breaker check
                if self._is_circuit_open(symbol):
                    continue
                
                # Check micro-scalp conditions with error handling
                try:
                    result = self.engine.check_micro_conditions(symbol)
                    # Reset circuit breaker on success
                    self._reset_circuit_breaker(symbol)
                except Exception as engine_error:
                    logger.error(
                        f"Engine error for {symbol}: {engine_error}",
                        exc_info=True
                    )
                    # Open circuit breaker for this symbol
                    self._open_circuit_breaker(symbol)
                    continue
                
                # ... rest of monitoring code ...
            
            except Exception as e:
                logger.error(f"Error monitoring {symbol}: {e}", exc_info=True)
                # Don't crash - continue with next symbol

def _is_circuit_open(self, symbol: str) -> bool:
    """Check if circuit breaker is open for symbol"""
    if symbol not in self.circuit_breakers:
        return False
    
    breaker = self.circuit_breakers[symbol]
    open_until = breaker.get('open_until')
    
    if open_until and datetime.now() < open_until:
        return True  # Circuit still open
    
    # Circuit closed - reset
    if open_until and datetime.now() >= open_until:
        self._reset_circuit_breaker(symbol)
    
    return False

def _open_circuit_breaker(self, symbol: str):
    """Open circuit breaker for symbol"""
    if symbol not in self.circuit_breakers:
        self.circuit_breakers[symbol] = {'failure_count': 0}
    
    breaker = self.circuit_breakers[symbol]
    breaker['failure_count'] = breaker.get('failure_count', 0) + 1
    
    if breaker['failure_count'] >= self.circuit_breaker_threshold:
        breaker['open_until'] = datetime.now() + timedelta(seconds=self.circuit_breaker_timeout)
        self.stats['circuit_breaker_opens'] = self.stats.get('circuit_breaker_opens', 0) + 1
        logger.warning(
            f"Circuit breaker opened for {symbol} "
            f"(failures: {breaker['failure_count']}, "
            f"timeout: {self.circuit_breaker_timeout}s)"
        )

def _reset_circuit_breaker(self, symbol: str):
    """Reset circuit breaker for symbol"""
    if symbol in self.circuit_breakers:
        self.circuit_breakers[symbol] = {'failure_count': 0}
```

**Additional:** Wrap `engine.check_micro_conditions()` with circuit-breaker logic to skip symbol for one cycle

---

### **Risk 3: MT5 Connection Drop**

**Problem:** MT5 connection may drop, causing position checks and executions to fail

**Mitigation:**
```python
def __init__(self, ...):
    # ... existing init ...
    self.mt5_heartbeat_failures = 0
    self.mt5_heartbeat_threshold = 3  # Pause after 3 consecutive failures
    self.mt5_heartbeat_interval = 60  # Check every 60 seconds
    self.monitoring_paused = False

def _monitor_loop(self):
    """Main monitoring loop with MT5 heartbeat"""
    last_heartbeat_check = time.time()
    
    while self.monitoring:
        # MT5 heartbeat check (every 60 seconds)
        current_time = time.time()
        if current_time - last_heartbeat_check >= self.mt5_heartbeat_interval:
            if not self._check_mt5_heartbeat():
                if not self.monitoring_paused:
                    logger.error("MT5 connection lost - pausing monitoring")
                    self.monitoring_paused = True
            else:
                if self.monitoring_paused:
                    logger.info("MT5 connection restored - resuming monitoring")
                    self.monitoring_paused = False
            
            last_heartbeat_check = current_time
        
        if self.monitoring_paused:
            time.sleep(self.check_interval)
            continue
        
        # ... existing monitoring code ...

def _check_mt5_heartbeat(self) -> bool:
    """Check MT5 connection health"""
    try:
        # Simple heartbeat: try to get positions
        positions = self.mt5_service.get_positions(symbol=None)
        # If successful, reset failure count
        self.mt5_heartbeat_failures = 0
        return True
    except Exception as e:
        self.mt5_heartbeat_failures += 1
        self.stats['mt5_heartbeat_failures'] = self.stats.get('mt5_heartbeat_failures', 0) + 1
        logger.warning(
            f"MT5 heartbeat failed ({self.mt5_heartbeat_failures}/{self.mt5_heartbeat_threshold}): {e}"
        )
        
        if self.mt5_heartbeat_failures >= self.mt5_heartbeat_threshold:
            # Send alert (if alerting system available)
            self._send_mt5_connection_alert()
            return False
        
        return True

def _send_mt5_connection_alert(self):
    """Send alert about MT5 connection loss"""
    try:
        # Use existing alerting system if available
        # Or log critical error
        logger.critical(
            f"MT5 connection lost - monitoring paused. "
            f"Failed {self.mt5_heartbeat_failures} consecutive heartbeat checks."
        )
    except Exception:
        pass

def _is_position_open(self, ticket: int) -> bool:
    """Check if position is still open with error handling"""
    try:
        positions = self.mt5_service.get_positions(symbol=None)
        return any(p.ticket == ticket for p in positions)
    except Exception as e:
        logger.debug(f"Position check failed (MT5 connection issue?): {e}")
        # Assume position is still open if check fails (conservative)
        return True
```

**Additional:** Add heartbeat check; if `get_positions()` fails consecutively N times, pause monitoring and alert

---

### **Risk 4: Backpressure from Logging**

**Problem:** High-frequency logging (every 5 seconds) may cause I/O delays

**Mitigation:**
```python
import logging
from logging.handlers import QueueHandler, QueueListener
from queue import Queue

def __init__(self, ...):
    # ... existing init ...
    # Rate-limited logging
    self.last_log_times: Dict[str, datetime] = {}
    self.log_rate_limit = 60  # Max 1 log per minute per type

def _log_with_rate_limit(self, level: str, message: str, log_type: str = "general"):
    """Log with rate limiting to prevent backpressure"""
    now = datetime.now()
    last_log = self.last_log_times.get(log_type)
    
    if last_log:
        time_since_last = (now - last_log).total_seconds()
        if time_since_last < self.log_rate_limit:
            return  # Skip log (rate limited)
    
    self.last_log_times[log_type] = now
    
    # Use standard logging (or async if configured)
    if level == "info":
        logger.info(message)
    elif level == "warning":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    elif level == "debug":
        logger.debug(message)

def _monitor_loop(self):
    """Main monitoring loop with rate-limited logging"""
    while self.monitoring:
        # ... existing code ...
        
        # Use rate-limited logging for frequent events
        self._log_with_rate_limit(
            "debug",
            f"Monitor cycle completed: {len(self.symbols)} symbols checked",
            "cycle_complete"
        )
```

**Alternative:** Use async log handler or rate-limited logging to avoid I/O delays on high-frequency runs

**Configuration:**
```json
{
  "logging": {
    "rate_limit_seconds": 60,
    "async_logging": false,
    "log_level": "INFO"
  }
}
```

---

## ⚠️ **Edge Cases to Handle**

1. **Streamer Data Unavailable:**
   - Fallback to cached candles
   - Fallback to direct MT5 API call
   - Skip symbol if all fallbacks fail

2. **Execution Manager Not Available:**
   - Log error, skip execution
   - Don't crash monitor

3. **MT5 Connection Lost:**
   - Heartbeat detection
   - Pause monitoring
   - Alert on connection loss

4. **Position Tracking Out of Sync:**
   - Periodic cleanup of closed positions
   - Verify positions on each check
   - Conservative assumption if check fails

5. **Config File Missing:**
   - Use default values
   - Log warning

6. **Monitor Thread Crash:**
   - Circuit breaker prevents cascading failures
   - Error handling around all critical operations
   - Consider auto-restart mechanism (future enhancement)

---

## 📊 **Monitoring & Observability**

### **Statistics Tracked:**
- Total checks performed
- Conditions met count
- Successful executions
- Execution failures
- Skipped reasons (news, rate limit, position limit)
- Last check time

### **Status Endpoint:**
- Monitor running status
- Active symbols
- Check interval
- Statistics
- Active positions per symbol
- Last execution times

### **Logging:**
- Monitor start/stop events
- Execution events (success/failure)
- Error conditions
- Rate limit hits
- Position limit hits

---

## 🚀 **Deployment Considerations**

1. **Enable/Disable via Config:**
   - Set `enabled: false` to disable without code changes
   - Useful for testing or maintenance

2. **Symbol Configuration:**
   - Add/remove symbols via config file
   - No code changes needed

3. **Performance:**
   - Monitor runs in separate thread (non-blocking)
   - Uses streamer buffers (efficient)
   - Minimal CPU usage

4. **Resource Usage:**
   - Single background thread
   - Minimal memory overhead
   - No additional API calls (uses streamer)

---

## 📌 **Implementation Notes**

### **Thread Safety:**
- Use locks for shared state (`monitor_lock`)
- Thread-safe data structures where needed
- Daemon thread (doesn't block shutdown)

### **Error Handling:**
- Try/except around each symbol check
- Log errors but continue monitoring
- Don't crash on individual failures

### **Performance:**
- Use streamer (fast, in-memory)
- Minimal processing per cycle
- Efficient position tracking

### **Maintainability:**
- Clear separation of concerns
- Reuses existing components
- Configurable behavior
- Comprehensive logging

---

## 🔄 **Phase 5: Enhanced Features (Optional Improvements)**

### **5.1 Dynamic Configuration Reload** ✅ **COMPLETED**

**Purpose:** Hot-reload config file without API restart

**Implementation:**
```python
def __init__(self, ...):
    # ... existing init ...
    self.config_path = config_path
    self.config_last_modified = 0
    self.config_reload_interval = 60  # Check every 60 seconds

def _monitor_loop(self):
    """Main monitoring loop with config reload"""
    last_config_check = time.time()  # Fixed: track last check time
    
    while self.monitoring:
        loop_start = time.time()
        
        # Check for config changes (every 60 seconds, not every loop)
        current_time = time.time()
        if current_time - last_config_check >= self.config_reload_interval:
            self._reload_config_if_changed()
            last_config_check = current_time
        
        # ... existing monitoring code ...
        
        # Sleep until next cycle
        elapsed = time.time() - loop_start
        sleep_time = max(0, self.check_interval - elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)

def _reload_config_if_changed(self):
    """Reload config if file has been modified"""
    try:
        if not os.path.exists(self.config_path):
            return
        
        current_mtime = os.path.getmtime(self.config_path)
        
        if current_mtime > self.config_last_modified:
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Config file {self.config_path} has invalid JSON: {e}")
                return  # Fixed: don't reload if JSON is invalid
            except Exception as e:
                logger.error(f"Error reading config file: {e}")
                return  # Fixed: don't reload on other errors
            
            # Update runtime config (thread-safe)
            with self.monitor_lock:  # Fixed: use lock for thread safety
                # Update symbols (if changed) - Fixed: copy list to avoid iteration issues
                old_symbols = self.symbols.copy() if isinstance(self.symbols, list) else list(self.symbols)
                new_symbols = config.get('symbols', self.symbols)
                
                if new_symbols != old_symbols:
                    logger.info(f"Config reload: Symbols updated: {old_symbols} → {new_symbols}")
                    # Fixed: Copy list to avoid iteration errors if list changes mid-iteration
                    self.symbols = new_symbols.copy() if isinstance(new_symbols, list) else list(new_symbols)
                
                # Update check interval
                self.check_interval = config.get('check_interval_seconds', self.check_interval)
                
                # Update rate limiting
                self.min_execution_interval = config.get('min_execution_interval_seconds', self.min_execution_interval)
                
                # Update position limits
                self.max_positions_per_symbol = config.get('max_positions_per_symbol', self.max_positions_per_symbol)
                
                # Update enabled status
                if not config.get('enabled', True) and self.monitoring:
                    logger.info("Config reload: Monitor disabled, stopping...")
                    self.monitoring = False
                elif config.get('enabled', True) and not self.monitoring:
                    logger.info("Config reload: Monitor enabled, starting...")
                    self.start()
                
                # Update self.config for other methods that use it
                self.config = config
            
            self.config_last_modified = current_mtime
            self.stats['config_reloads'] = self.stats.get('config_reloads', 0) + 1
            logger.debug("Config reloaded successfully")
    
    except Exception as e:
        logger.debug(f"Config reload check failed: {e}")
```

**Benefits:**
- Add/remove symbols without restart
- Adjust intervals/limits on the fly
- Enable/disable without code changes

---

### **5.2 Adaptive Rate Limiting** ⏸️ **OPTIONAL** (Not Implemented - Can be added later if needed)

**Purpose:** Scale cooldown based on market conditions and performance

**Implementation:**
```python
def __init__(self, ...):
    # ... existing init ...
    self.adaptive_rate_limiting = True
    self.base_execution_interval = 60  # Base 60 seconds
    self.min_execution_interval = 30   # Minimum 30 seconds
    self.max_execution_interval = 120  # Maximum 120 seconds
    
    # Performance tracking
    self.recent_trades: List[Dict] = []  # Last 10 trades
    self.win_rate_window = 10  # Calculate win rate from last N trades

def _get_adaptive_interval(self, symbol: str) -> int:
    """Calculate adaptive execution interval based on performance and volatility"""
    if not self.adaptive_rate_limiting:
        return self.base_execution_interval
    
    # Get recent trades for symbol
    symbol_trades = [t for t in self.recent_trades if t.get('symbol') == symbol]
    if len(symbol_trades) < 3:
        return self.base_execution_interval  # Not enough data
    
    # Calculate win rate
    wins = sum(1 for t in symbol_trades if t.get('profit', 0) > 0)
    win_rate = wins / len(symbol_trades)
    
    # Get current volatility (from streamer or M1 analyzer)
    volatility_factor = self._get_volatility_factor(symbol)
    
    # Adjust interval based on win rate and volatility
    if win_rate < 0.3:  # Low win rate - increase cooldown
        interval = self.base_execution_interval * 1.5
    elif win_rate > 0.7:  # High win rate - decrease cooldown
        interval = self.base_execution_interval * 0.75
    else:
        interval = self.base_execution_interval
    
    # Adjust for volatility
    if volatility_factor > 1.5:  # High volatility
        interval *= 1.2  # Increase cooldown
    elif volatility_factor < 0.7:  # Low volatility
        interval *= 0.9  # Decrease cooldown
    
    # Clamp to min/max
    return max(self.min_execution_interval, min(self.max_execution_interval, int(interval)))

def _get_volatility_factor(self, symbol: str) -> float:
    """Get volatility factor (1.0 = normal, >1.0 = high, <1.0 = low)"""
    try:
        # Get ATR from M1 data
        m1_candles = self._get_m1_candles(symbol, limit=20)
        if m1_candles and len(m1_candles) >= 14:
            # Calculate ATR
            highs = [c['high'] for c in m1_candles]
            lows = [c['low'] for c in m1_candles]
            closes = [c['close'] for c in m1_candles]
            
            tr_values = []
            for i in range(1, len(m1_candles)):
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i-1]),
                    abs(lows[i] - closes[i-1])
                )
                tr_values.append(tr)
            
            atr = sum(tr_values) / len(tr_values) if tr_values else 0
            
            # Normalize by price (rough volatility factor)
            current_price = closes[-1] if closes else 1
            atr_percent = (atr / current_price) * 100 if current_price > 0 else 0
            
            # Compare to typical volatility (symbol-specific)
            typical_atr = 0.1  # 0.1% typical for BTC/XAUUSD M1
            return atr_percent / typical_atr if typical_atr > 0 else 1.0
    except Exception:
        pass
    
    return 1.0  # Default to normal

def _should_skip_symbol(self, symbol: str) -> bool:
    """Check if symbol should be skipped (adaptive rate limiting)"""
    if symbol not in self.last_execution_time:
        return False
    
    # Get adaptive interval
    interval = self._get_adaptive_interval(symbol)
    
    time_since_last = (datetime.now() - self.last_execution_time[symbol]).total_seconds()
    if time_since_last < interval:
        self.stats['skipped_rate_limit'] += 1
        return True
    
    return False

def _execute_micro_scalp(self, symbol: str, trade_idea: Dict):
    """Execute micro-scalp trade with performance tracking"""
    # ... existing execution code ...
    
    if result.get('success'):
        # Track trade for adaptive rate limiting
        self.recent_trades.append({
            'symbol': symbol,
            'direction': trade_idea.get('direction'),
            'entry_price': trade_idea.get('entry_price'),  # Fixed: was 'entry'
            'timestamp': datetime.now(),
            'profit': 0  # Will be updated when position closes
        })
        
        # Keep only last N trades
        if len(self.recent_trades) > self.win_rate_window:
            self.recent_trades = self.recent_trades[-self.win_rate_window:]
        
        # ... rest of execution code ...
```

**Benefits:**
- Faster execution in favorable conditions
- Slower execution after losses
- Volatility-aware throttling

---

### **5.3 Execution Confirmation Layer** ✅ **COMPLETED**

**Purpose:** Pre-execution validation to prevent poor fills

**Implementation:**
```python
def _execute_micro_scalp(self, symbol: str, trade_idea: Dict):
    """Execute micro-scalp trade with pre-execution validation"""
    if not trade_idea:
        logger.warning(f"No trade idea provided for {symbol}")
        return
    
    # Pre-execution validation
    validation_result = self._validate_execution_conditions(symbol, trade_idea)
    if not validation_result['valid']:
        logger.warning(
            f"Execution aborted for {symbol}: {validation_result['reason']}"
        )
        self.stats['execution_failures'] += 1
        return
    
    try:
        # Use existing execution manager
        result = self.execution_manager.execute_trade(...)
        # ... rest of execution code ...

def _validate_execution_conditions(self, symbol: str, trade_idea: Dict) -> Dict[str, Any]:
    """Validate execution conditions before placing order"""
    try:
        # Get current spread
        tick_info = self.mt5_service.get_symbol_info(symbol)
        if not tick_info:
            return {'valid': False, 'reason': 'Symbol info unavailable'}
        
        current_spread = tick_info.spread
        tick_size = tick_info.trade_tick_size
        
        # Calculate target spread (based on entry price)
        entry_price = trade_idea.get('entry_price', 0)  # Fixed: was 'entry'
        if entry_price == 0:
            # Get current price
            price_data = self.mt5_service.get_current_price(symbol)
            if not price_data:
                return {'valid': False, 'reason': 'Price data unavailable'}
            entry_price = price_data.get('mid', 0)
        
        # Calculate spread as percentage
        spread_percent = (current_spread * tick_size / entry_price) * 100 if entry_price > 0 else 0
        
        # Get target spread threshold (from config or default)
        execution_validation_config = self.config.get('execution_validation', {})
        max_spread_percent = execution_validation_config.get('max_spread_percent', 0.25)  # Fixed: use nested config path
        check_tick_alignment = execution_validation_config.get('check_tick_alignment', False)  # Fixed: cache for reuse
        use_spread_tracker = execution_validation_config.get('use_spread_tracker', False)  # Fixed: cache for reuse
        
        if spread_percent > max_spread_percent:
            return {
                'valid': False,
                'reason': f'Spread too wide: {spread_percent:.3f}% > {max_spread_percent}%'
            }
        
        # Check tick size alignment (optional)
        if check_tick_alignment:  # Fixed: use cached config variable
            sl_distance = abs(entry_price - trade_idea.get('sl', 0))
            tp_distance = abs(trade_idea.get('tp', 0) - entry_price)
            
            if sl_distance > 0 and (sl_distance % tick_size) != 0:
                logger.debug(f"SL distance not aligned to tick size: {sl_distance} vs {tick_size}")
            
            if tp_distance > 0 and (tp_distance % tick_size) != 0:
                logger.debug(f"TP distance not aligned to tick size: {tp_distance} vs {tick_size}")
        
        # Check liquidity (if available from spread tracker)
        if use_spread_tracker and hasattr(self, 'spread_tracker'):  # Fixed: use cached config variable
            spread_data = self.spread_tracker.get_current_spread(symbol)
            if spread_data and spread_data.is_wide:
                return {
                    'valid': False,
                    'reason': 'Spread tracker indicates wide spread (thin liquidity)'
                }
        
        return {'valid': True, 'reason': 'All checks passed'}
    
    except Exception as e:
        logger.error(f"Execution validation error: {e}")
        return {'valid': False, 'reason': f'Validation error: {e}'}
```

**Configuration:**
```json
{
  "execution_validation": {
    "max_spread_percent": 0.25,
    "check_tick_alignment": true,
    "use_spread_tracker": true
  }
}
```

**Benefits:**
- Prevents poor fills in thin liquidity
- Validates spread before execution
- Reduces slippage risk

---

### **5.4 Performance Metrics Extension** ✅ **COMPLETED**

**Purpose:** Track R-multiples, latency, and win rate from closed positions

**Implementation:**
```python
def __init__(self, ...):
    # ... existing init ...
    self.performance_metrics = {
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'total_r_multiple': 0.0,
        'avg_r_multiple': 0.0,
        'avg_execution_latency_ms': 0.0,
        'avg_hold_time_seconds': 0.0,
        'largest_win_r': 0.0,
        'largest_loss_r': 0.0,
        'current_streak': 0,  # Positive = wins, negative = losses
        'best_streak': 0,
        'worst_streak': 0
    }
    
    # Track open positions for performance calculation
    self.open_positions: Dict[int, Dict] = {}  # ticket -> position data

def _execute_micro_scalp(self, symbol: str, trade_idea: Dict):
    """Execute micro-scalp trade with performance tracking"""
    execution_start = time.time()
    
    # ... existing execution code ...
    
    if result.get('success'):
        ticket = result.get('ticket')
        if ticket:
            # Track position for performance metrics
            self.open_positions[ticket] = {
                'symbol': symbol,
                'direction': trade_idea.get('direction'),
                'entry_price': trade_idea.get('entry_price'),  # Fixed: was 'entry'
                'sl': trade_idea.get('sl'),
                'tp': trade_idea.get('tp'),
                'entry_time': datetime.now(),
                'execution_latency_ms': (time.time() - execution_start) * 1000,
                'risk_amount': abs(trade_idea.get('entry_price', 0) - trade_idea.get('sl', 0))  # Fixed: was 'entry'
            }
            
            # Update execution latency
            self._update_avg_latency((time.time() - execution_start) * 1000)
            
            # ... rest of execution code ...

def _update_position_performance(self, ticket: int, close_price: float, close_time: datetime):
    """Update performance metrics when position closes"""
    if ticket not in self.open_positions:
        return
    
    position = self.open_positions.pop(ticket)
    
    # Calculate P/L
    entry_price = position['entry_price']
    direction = position['direction']
    risk_amount = position['risk_amount']
    
    if risk_amount == 0:
        return
    
    if direction == 'BUY':
        profit = close_price - entry_price
    else:  # SELL
        profit = entry_price - close_price
    
    # Calculate R-multiple
    r_multiple = profit / risk_amount if risk_amount > 0 else 0
    
    # Update metrics
    self.performance_metrics['total_trades'] += 1
    
    if profit > 0:
        self.performance_metrics['winning_trades'] += 1
        self.performance_metrics['current_streak'] = max(0, self.performance_metrics['current_streak']) + 1
        if r_multiple > self.performance_metrics['largest_win_r']:
            self.performance_metrics['largest_win_r'] = r_multiple
    else:
        self.performance_metrics['losing_trades'] += 1
        self.performance_metrics['current_streak'] = min(0, self.performance_metrics['current_streak']) - 1
        if r_multiple < self.performance_metrics['largest_loss_r']:
            self.performance_metrics['largest_loss_r'] = r_multiple
    
    # Update streaks
    if self.performance_metrics['current_streak'] > self.performance_metrics['best_streak']:
        self.performance_metrics['best_streak'] = self.performance_metrics['current_streak']
    if self.performance_metrics['current_streak'] < self.performance_metrics['worst_streak']:
        self.performance_metrics['worst_streak'] = self.performance_metrics['current_streak']
    
    # Update R-multiple averages
    self.performance_metrics['total_r_multiple'] += r_multiple
    total_trades = self.performance_metrics['total_trades']
    self.performance_metrics['avg_r_multiple'] = (
        self.performance_metrics['total_r_multiple'] / total_trades
        if total_trades > 0 else 0
    )
    
    # Update hold time
    hold_time = (close_time - position['entry_time']).total_seconds()
    # Calculate running average (exponential moving average)
    current_avg = self.performance_metrics['avg_hold_time_seconds']
    alpha = 0.1  # Smoothing factor
    self.performance_metrics['avg_hold_time_seconds'] = (
        alpha * hold_time + (1 - alpha) * current_avg
        if current_avg > 0 else hold_time
    )
    
    # Update recent trades for adaptive rate limiting
    self.recent_trades.append({
        'symbol': position['symbol'],
        'direction': direction,
        'entry_price': entry_price,  # Fixed: changed key from 'entry' to 'entry_price' for consistency
        'timestamp': position['entry_time'],
        'profit': profit,
        'r_multiple': r_multiple
    })
    
    logger.info(
        f"Position closed: {position['symbol']} {direction} "
        f"R:{r_multiple:.2f} | "
        f"Win Rate: {self.performance_metrics['winning_trades']}/{self.performance_metrics['total_trades']} | "
        f"Avg R: {self.performance_metrics['avg_r_multiple']:.2f}"
    )

def _update_avg_latency(self, latency_ms: float):
    """Update average execution latency"""
    current_avg = self.performance_metrics['avg_execution_latency_ms']
    alpha = 0.1  # Smoothing factor
    self.performance_metrics['avg_execution_latency_ms'] = (
        alpha * latency_ms + (1 - alpha) * current_avg
        if current_avg > 0 else latency_ms
    )

def _monitor_loop(self):
    """Main monitoring loop with position performance tracking"""
    while self.monitoring:
        # ... existing monitoring code ...
        
        # Check for closed positions and update performance
        self._check_closed_positions()
        
        time.sleep(self.check_interval)

def _check_closed_positions(self):
    """Check for closed positions and update performance metrics"""
    try:
        current_positions = self.mt5_service.get_positions(symbol=None)
        
        # Fixed: Handle None or empty return
        if not current_positions:
            current_positions = []
        
        # Fixed: Handle both list of objects and list of dicts
        if current_positions and hasattr(current_positions[0], 'ticket'):
            open_tickets = {p.ticket for p in current_positions}
        elif current_positions and isinstance(current_positions[0], dict):
            open_tickets = {p.get('ticket') for p in current_positions if p.get('ticket')}
        else:
            open_tickets = set()
        
        # Find closed positions
        for ticket in list(self.open_positions.keys()):
            if ticket not in open_tickets:
                # Position closed - get close price from trade history
                position = self.open_positions[ticket]
                close_price = self._get_position_close_price(ticket)
                if close_price:
                    self._update_position_performance(ticket, close_price, datetime.now())
                # Remove from tracking
                del self.open_positions[ticket]
    except Exception as e:
        logger.error(f"Error checking closed positions: {e}", exc_info=True)

def _get_position_close_price(self, ticket: int) -> Optional[float]:
    """Get close price for closed position"""
    try:
        # Fixed: Use MT5 history_deals_get directly instead of non-existent method
        import MetaTrader5 as mt5
        from datetime import datetime, timedelta
        
        # Get deals from last 30 days for this position
        from_date = datetime.now() - timedelta(days=30)
        to_date = datetime.now()
        deals = mt5.history_deals_get(from_date, to_date, position=ticket)
        
        if deals:
            # Find exit deal (entry == DEAL_ENTRY_OUT)
            for deal in reversed(deals):  # Check most recent first
                if deal.entry == mt5.DEAL_ENTRY_OUT:
                    return deal.price
    except Exception as e:
        logger.debug(f"Error getting close price for ticket {ticket}: {e}")
    return None

def get_status(self) -> Dict[str, Any]:
    """Get monitor status with performance metrics"""
    base_status = {
        # ... existing status fields ...
    }
    
    # Add performance metrics
    total_trades = self.performance_metrics['total_trades']
    win_rate = (
        self.performance_metrics['winning_trades'] / total_trades * 100
        if total_trades > 0 else 0
    )
    
    base_status['performance'] = {
        **self.performance_metrics,
        'win_rate_percent': win_rate,
        'profit_factor': (
            abs(self.performance_metrics['largest_win_r']) / abs(self.performance_metrics['largest_loss_r'])
            if self.performance_metrics['largest_loss_r'] != 0 else 0
        )
    }
    
    return base_status
```

**Benefits:**
- Real-time performance tracking
- R-multiple analysis
- Win rate monitoring
- Execution latency tracking
- Feeds adaptive rate limiting

---

### **5.5 Session Bias Integration** ✅ **COMPLETED**

**Purpose:** Automatically enable/disable based on session characteristics

**Implementation:**
```python
def __init__(self, ...):
    # ... existing init ...
    self.session_adaptive = True
    self.preferred_sessions = ['asian', 'new_york_late']  # From config
    self.disabled_sessions = ['london', 'new_york_overlap']  # From config

def _should_monitor_symbol(self, symbol: str) -> bool:
    """Check if symbol should be monitored based on session"""
    if not self.session_adaptive or not self.session_manager:
        return True  # Monitor always if session filtering disabled
    
    try:
        # Fixed: Handle different session manager types
        if hasattr(self.session_manager, 'get_current_session'):
            current_session = self.session_manager.get_current_session()
        elif hasattr(self.session_manager, 'get_session_info'):
            session_info = self.session_manager.get_session_info()
            current_session = {
                'name': session_info.primary_session 
                if hasattr(session_info, 'primary_session') 
                else session_info.get('primary_session', '')
            }
        else:
            # Fallback: use SessionHelpers
            from infra.session_helpers import SessionHelpers
            session_name = SessionHelpers.get_current_session()
            current_session = {'name': session_name}
        
        # Extract session name (handle both dict and string returns)
        if isinstance(current_session, dict):
            session_name = current_session.get('name', '').lower()
        else:
            session_name = str(current_session).lower()
        
        # Check if session is disabled
        if any(disabled in session_name for disabled in self.disabled_sessions):
            return False
        
        # Check if session is preferred (optional - can monitor in any non-disabled session)
        # If preferred_sessions is empty, monitor in all non-disabled sessions
        if self.preferred_sessions:
            if not any(preferred in session_name for preferred in self.preferred_sessions):
                return False
        
        return True
    except Exception as e:
        logger.debug(f"Session check failed: {e}")
        return True  # Default to monitoring if check fails

def _monitor_loop(self):
    """Main monitoring loop with session filtering"""
    while self.monitoring:
        loop_start = time.time()
        
        for symbol in self.symbols:
            try:
                # Session-based filtering
                if not self._should_monitor_symbol(symbol):
                    self.stats['skipped_session'] = self.stats.get('skipped_session', 0) + 1
                    continue
                
                # ... rest of monitoring code ...
```

**Configuration:**
```json
{
  "session_filters": {
    "enabled": true,
    "preferred_sessions": ["asian", "new_york_late"],
    "disabled_sessions": ["london", "new_york_overlap"],
    "adaptive": true
  }
}
```

**Benefits:**
- Automatic session-based filtering
- Focuses on best micro-scalp windows
- Reduces trading during unfavorable sessions

---

### **5.6 Discord Notifications Integration** ✅ **COMPLETED** ⭐ **RECOMMENDED**

**Purpose:** Send execution, error, and performance alerts to Discord

**Implementation:**
```python
def __init__(self, ...):
    # ... existing init ...
    # Discord notifications
    self.discord_notifier = None
    self.discord_enabled = True
    self._init_discord_notifier()

def _init_discord_notifier(self):
    """Initialize Discord notifier"""
    try:
        from discord_notifications import DiscordNotifier
        self.discord_notifier = DiscordNotifier()
        if not self.discord_notifier.enabled:
            logger.warning("Discord notifications not enabled - check DISCORD_WEBHOOK_URL")
            self.discord_enabled = False
        else:
            logger.info("Discord notifications enabled for micro-scalp monitor")
    except ImportError:
        logger.warning("Discord notifications module not available")
        self.discord_enabled = False
    except Exception as e:
        logger.warning(f"Failed to initialize Discord notifier: {e}")
        self.discord_enabled = False

def _send_discord_notification(self, title: str, message: str, message_type: str = "INFO", color: int = None):
    """Send notification to Discord"""
    if not self.discord_enabled or not self.discord_notifier:
        return False
    
    try:
        # Map message types to colors
        if color is None:
            color_map = {
                "EXECUTION": 0x00ff00,  # Green
                "ERROR": 0xff0000,      # Red
                "WARNING": 0xff9900,   # Orange
                "PERFORMANCE": 0x0099ff, # Blue
                "INFO": 0x0099ff        # Blue
            }
            color = color_map.get(message_type, 0x0099ff)
        
        # Send to private channel (micro-scalp executions are private)
        success = self.discord_notifier.send_message(
            message=message,
            message_type=message_type,
            color=color,
            channel="private",
            custom_title=title
        )
        
        return success
    except Exception as e:
        logger.debug(f"Discord notification failed: {e}")
        return False

def _execute_micro_scalp(self, symbol: str, trade_idea: Dict):
    """Execute micro-scalp trade with Discord notification"""
    # ... existing execution code ...
    
    if result.get('success'):
        ticket = result.get('ticket')
        if ticket:
            # ... existing position tracking code ...
            
            # Send Discord notification
            notification_message = (
                f"**Micro-Scalp Trade Executed**\n\n"
                f"**Symbol:** {symbol}\n"
                f"**Direction:** {trade_idea.get('direction')}\n"
                f"**Entry:** {trade_idea.get('entry_price'):.5f}\n"  # Fixed: was 'entry'
                f"**Stop Loss:** {trade_idea.get('sl'):.5f}\n"
                f"**Take Profit:** {trade_idea.get('tp'):.5f}\n"
                f"**Volume:** {trade_idea.get('volume', 0.01)}\n"
                f"**Ticket:** {ticket}\n"
                f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            self._send_discord_notification(
                title=f"✅ Micro-Scalp Executed: {symbol}",
                message=notification_message,
                message_type="EXECUTION",
                color=0x00ff00  # Green
            )
            
            # ... rest of execution code ...
    else:
        # Send error notification
        error_message = (
            f"**Micro-Scalp Execution Failed**\n\n"
            f"**Symbol:** {symbol}\n"
            f"**Direction:** {trade_idea.get('direction')}\n"
            f"**Error:** {result.get('error', 'Unknown error')}\n"
            f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        self._send_discord_notification(
            title=f"❌ Micro-Scalp Failed: {symbol}",
            message=error_message,
            message_type="ERROR",
            color=0xff0000  # Red
        )

def _open_circuit_breaker(self, symbol: str):
    """Open circuit breaker with Discord alert"""
    # ... existing circuit breaker code ...
    
    if breaker['failure_count'] >= self.circuit_breaker_threshold:
        # Send Discord alert
        alert_message = (
            f"**Circuit Breaker Opened**\n\n"
            f"**Symbol:** {symbol}\n"
            f"**Failures:** {breaker['failure_count']}\n"
            f"**Timeout:** {self.circuit_breaker_timeout}s\n"
            f"**Reason:** Engine errors detected\n"
            f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        self._send_discord_notification(
            title=f"⚠️ Circuit Breaker: {symbol}",
            message=alert_message,
            message_type="WARNING",
            color=0xff9900  # Orange
        )

def _send_mt5_connection_alert(self):
    """Send alert about MT5 connection loss"""
    alert_message = (
        f"**MT5 Connection Lost**\n\n"
        f"**Failures:** {self.mt5_heartbeat_failures}\n"
        f"**Threshold:** {self.mt5_heartbeat_threshold}\n"
        f"**Status:** Monitoring paused\n"
        f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    self._send_discord_notification(
        title="🔴 MT5 Connection Lost",
        message=alert_message,
        message_type="ERROR",
        color=0xff0000  # Red
    )

def _send_performance_summary(self):
    """Send daily performance summary to Discord"""
    if not self.performance_metrics['total_trades']:
        return
    
    total_trades = self.performance_metrics['total_trades']
    win_rate = (
        self.performance_metrics['winning_trades'] / total_trades * 100
        if total_trades > 0 else 0
    )
    
    summary_message = (
        f"**Micro-Scalp Performance Summary**\n\n"
        f"**Total Trades:** {total_trades}\n"
        f"**Wins:** {self.performance_metrics['winning_trades']}\n"
        f"**Losses:** {self.performance_metrics['losing_trades']}\n"
        f"**Win Rate:** {win_rate:.1f}%\n"
        f"**Avg R-Multiple:** {self.performance_metrics['avg_r_multiple']:.2f}\n"
        f"**Largest Win:** {self.performance_metrics['largest_win_r']:.2f}R\n"
        f"**Largest Loss:** {self.performance_metrics['largest_loss_r']:.2f}R\n"
        f"**Current Streak:** {self.performance_metrics['current_streak']}\n"
        f"**Avg Execution Latency:** {self.performance_metrics['avg_execution_latency_ms']:.1f}ms\n"
        f"**Avg Hold Time:** {self.performance_metrics['avg_hold_time_seconds']:.1f}s"
    )
    
    self._send_discord_notification(
        title="📊 Micro-Scalp Performance",
        message=summary_message,
        message_type="PERFORMANCE",
        color=0x0099ff  # Blue
    )

def _monitor_loop(self):
    """Main monitoring loop with daily performance summary"""
    last_summary_time = datetime.now()
    summary_interval = timedelta(hours=24)  # Daily summary
    
    while self.monitoring:
        # ... existing monitoring code ...
        
        # Send daily performance summary
        current_time = datetime.now()
        if current_time - last_summary_time >= summary_interval:
            self._send_performance_summary()
            last_summary_time = current_time
        
        time.sleep(self.check_interval)
```

**Configuration:**
```json
{
  "discord_notifications": {
    "enabled": true,
    "notify_on_execution": true,
    "notify_on_error": true,
    "notify_on_circuit_breaker": true,
    "notify_on_connection_loss": true,
    "daily_performance_summary": true,
    "performance_summary_time": "00:00"  # UTC time for daily summary
  }
}
```

**Environment Variables:**
- `DISCORD_WEBHOOK_URL` - Private channel webhook (required)
- `DISCORD_WEBHOOK_CRYPTO` - Crypto channel webhook (optional, for BTC)
- `DISCORD_WEBHOOK_GOLD` - Gold channel webhook (optional, for XAUUSD)

**Benefits:**
- Real-time execution notifications
- Error alerts for troubleshooting
- Performance tracking via daily summaries
- Circuit breaker alerts for system health
- Connection loss alerts for reliability

---

## ⚠️ **Potential Pitfalls & Mitigations**

### **Risk 1: Streamer Temporarily Empty**

**Problem:** Streamer buffers may be empty during initialization or after errors

**Mitigation:**
```python
def _get_m1_candles(self, symbol: str, limit: int = 50) -> Optional[List[Dict]]:
    """Get M1 candles from streamer with fallback and caching"""
    try:
        candles = self.streamer.get_candles(symbol, 'M1', limit=limit)
        if candles and len(candles) >= 10:
            # Cache last valid candles
            self._last_valid_candles[symbol] = candles
            return candles
    except Exception as e:
        logger.debug(f"Failed to get M1 candles from streamer for {symbol}: {e}")
    
    # Fallback 1: Use cached candles (if available)
    if symbol in self._last_valid_candles:
        cached = self._last_valid_candles[symbol]
        if len(cached) >= 10:
            logger.debug(f"Using cached M1 candles for {symbol}")
            return cached
    
    # Fallback 2: Direct MT5 API call (last resort)
    try:
        if self.mt5_service:
            candles = self.mt5_service.get_candles(symbol, 'M1', limit=limit)
            if candles and len(candles) >= 10:
                logger.debug(f"Using direct MT5 API for {symbol} (streamer unavailable)")
                return candles
    except Exception as e:
        logger.debug(f"Direct MT5 API also failed for {symbol}: {e}")
    
    return None

def __init__(self, ...):
    # ... existing init ...
    self._last_valid_candles: Dict[str, List[Dict]] = {}  # Cache for fallback
```

**Additional:** Cache last 10 valid bars per symbol for fallback

---

### **Risk 2: Thread Crash Due to Unhandled Engine Error**

**Problem:** `engine.check_micro_conditions()` may raise unhandled exception, crashing monitor thread

**Mitigation:**
```python
def _monitor_loop(self):
    """Main monitoring loop with circuit breaker"""
    while self.monitoring:
        loop_start = time.time()
        
        for symbol in self.symbols:
            try:
                # ... existing checks ...
                
                # Circuit breaker check
                if self._is_circuit_open(symbol):
                    continue
                
                # Check micro-scalp conditions with error handling
                try:
                    result = self.engine.check_micro_conditions(symbol)
                    # Reset circuit breaker on success
                    self._reset_circuit_breaker(symbol)
                except Exception as engine_error:
                    logger.error(
                        f"Engine error for {symbol}: {engine_error}",
                        exc_info=True
                    )
                    # Open circuit breaker for this symbol
                    self._open_circuit_breaker(symbol)
                    continue
                
                # ... rest of monitoring code ...
            
            except Exception as e:
                logger.error(f"Error monitoring {symbol}: {e}", exc_info=True)
                # Don't crash - continue with next symbol

def __init__(self, ...):
    # ... existing init ...
    # Circuit breaker state: {symbol: {'open_until': datetime, 'failure_count': int}}
    self.circuit_breakers: Dict[str, Dict] = {}
    self.circuit_breaker_threshold = 3  # Open after 3 failures
    self.circuit_breaker_timeout = 300  # 5 minutes

def _is_circuit_open(self, symbol: str) -> bool:
    """Check if circuit breaker is open for symbol"""
    if symbol not in self.circuit_breakers:
        return False
    
    breaker = self.circuit_breakers[symbol]
    open_until = breaker.get('open_until')
    
    if open_until and datetime.now() < open_until:
        return True  # Circuit still open
    
    # Circuit closed - reset
    if open_until and datetime.now() >= open_until:
        self._reset_circuit_breaker(symbol)
    
    return False

def _open_circuit_breaker(self, symbol: str):
    """Open circuit breaker for symbol"""
    if symbol not in self.circuit_breakers:
        self.circuit_breakers[symbol] = {'failure_count': 0}
    
    breaker = self.circuit_breakers[symbol]
    breaker['failure_count'] = breaker.get('failure_count', 0) + 1
    
    if breaker['failure_count'] >= self.circuit_breaker_threshold:
        breaker['open_until'] = datetime.now() + timedelta(seconds=self.circuit_breaker_timeout)
        logger.warning(
            f"Circuit breaker opened for {symbol} "
            f"(failures: {breaker['failure_count']}, "
            f"timeout: {self.circuit_breaker_timeout}s)"
        )

def _reset_circuit_breaker(self, symbol: str):
    """Reset circuit breaker for symbol"""
    if symbol in self.circuit_breakers:
        self.circuit_breakers[symbol] = {'failure_count': 0}
```

**Additional:** Wrap `engine.check_micro_conditions()` with circuit-breaker logic to skip symbol for one cycle

---

### **Risk 3: MT5 Connection Drop**

**Problem:** MT5 connection may drop, causing position checks and executions to fail

**Mitigation:**
```python
def __init__(self, ...):
    # ... existing init ...
    self.mt5_heartbeat_failures = 0
    self.mt5_heartbeat_threshold = 3  # Pause after 3 consecutive failures
    self.mt5_heartbeat_interval = 60  # Check every 60 seconds
    self.monitoring_paused = False

def _monitor_loop(self):
    """Main monitoring loop with MT5 heartbeat"""
    while self.monitoring:
        # MT5 heartbeat check
        if not self._check_mt5_heartbeat():
            if not self.monitoring_paused:
                logger.error("MT5 connection lost - pausing monitoring")
                self.monitoring_paused = True
            continue
        
        if self.monitoring_paused:
            logger.info("MT5 connection restored - resuming monitoring")
            self.monitoring_paused = False
        
        # ... existing monitoring code ...

def _check_mt5_heartbeat(self) -> bool:
    """Check MT5 connection health"""
    try:
        # Simple heartbeat: try to get positions
        positions = self.mt5_service.get_positions(symbol=None)
        # If successful, reset failure count
        self.mt5_heartbeat_failures = 0
        return True
    except Exception as e:
        self.mt5_heartbeat_failures += 1
        logger.warning(
            f"MT5 heartbeat failed ({self.mt5_heartbeat_failures}/{self.mt5_heartbeat_threshold}): {e}"
        )
        
        if self.mt5_heartbeat_failures >= self.mt5_heartbeat_threshold:
            # Send alert (if alerting system available)
            self._send_mt5_connection_alert()
            return False
        
        return True

def _send_mt5_connection_alert(self):
    """Send alert about MT5 connection loss"""
    try:
        # Use existing alerting system if available
        # Or log critical error
        logger.critical(
            f"MT5 connection lost - monitoring paused. "
            f"Failed {self.mt5_heartbeat_failures} consecutive heartbeat checks."
        )
    except Exception:
        pass

def _is_position_open(self, ticket: int) -> bool:
    """Check if position is still open with error handling"""
    try:
        positions = self.mt5_service.get_positions(symbol=None)
        return any(p.ticket == ticket for p in positions)
    except Exception as e:
        logger.debug(f"Position check failed (MT5 connection issue?): {e}")
        # Assume position is still open if check fails (conservative)
        return True
```

**Additional:** Add heartbeat check; if `get_positions()` fails consecutively N times, pause monitoring and alert

---

### **Risk 4: Backpressure from Logging**

**Problem:** High-frequency logging (every 5 seconds) may cause I/O delays

**Mitigation:**
```python
import logging
from logging.handlers import QueueHandler, QueueListener
from queue import Queue

def __init__(self, ...):
    # ... existing init ...
    # Set up async logging
    self.log_queue = Queue(maxsize=1000)
    self.log_handler = QueueHandler(self.log_queue)
    self.log_listener = QueueListener(self.log_queue, logger.handlers[0])
    self.log_listener.start()
    
    # Rate-limited logging
    self.last_log_times: Dict[str, datetime] = {}
    self.log_rate_limit = 60  # Max 1 log per minute per type

def _log_with_rate_limit(self, level: str, message: str, log_type: str = "general"):
    """Log with rate limiting to prevent backpressure"""
    now = datetime.now()
    last_log = self.last_log_times.get(log_type)
    
    if last_log:
        time_since_last = (now - last_log).total_seconds()
        if time_since_last < self.log_rate_limit:
            return  # Skip log (rate limited)
    
    self.last_log_times[log_type] = now
    
    # Use async logging
    if level == "info":
        logger.info(message)
    elif level == "warning":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    elif level == "debug":
        logger.debug(message)

def _monitor_loop(self):
    """Main monitoring loop with rate-limited logging"""
    while self.monitoring:
        # ... existing code ...
        
        # Use rate-limited logging for frequent events
        self._log_with_rate_limit(
            "debug",
            f"Monitor cycle completed: {len(self.symbols)} symbols checked",
            "cycle_complete"
        )
```

**Alternative:** Use async log handler or rate-limited logging to avoid I/O delays on high-frequency runs

**Configuration:**
```json
{
  "logging": {
    "rate_limit_seconds": 60,
    "async_logging": true,
    "log_level": "INFO"
  }
}
```

---

## 📊 **Updated Statistics Tracking**

Add new statistics fields:
```python
self.stats = {
    # ... existing stats ...
    'skipped_session': 0,
    'skipped_spread_validation': 0,
    'circuit_breaker_opens': 0,
    'mt5_heartbeat_failures': 0,
    'config_reloads': 0
}
```

---

## ✅ **Updated Success Criteria**

Add to existing success criteria:
11. Dynamic config reload works (hot-reload without restart)
12. Adaptive rate limiting adjusts based on performance
13. Execution validation prevents poor fills
14. Performance metrics tracked accurately
15. Session-based filtering works correctly
16. Circuit breaker prevents thread crashes
17. MT5 heartbeat detects connection issues
18. Logging doesn't cause performance issues

---

## 📚 **Related Documentation**

- `infra/micro_scalp_engine.py` - Condition detection logic
- `infra/micro_scalp_execution.py` - Execution and position management
- `infra/multi_timeframe_streamer.py` - Data streaming
- `config/micro_scalp_config.json` - Micro-scalp strategy configuration
- `docs/MULTI_TIMEFRAME_STREAMING_GUIDE.md` - Streamer usage guide

---

## ✅ **Review Checklist**

Before implementation:
- [x] Review existing micro-scalp engine code ✅
- [x] Review execution manager capabilities ✅
- [x] Verify streamer provides M1 data ✅
- [x] Check MT5 service interface ✅
- [x] Review configuration structure ✅

After implementation:
- [x] All test cases pass ✅ (7/7 tests passed)
- [x] Monitor starts/stops correctly ✅
- [x] Trades execute when conditions met ✅
- [x] Rate limiting works ✅
- [x] Position limits enforced ✅
- [x] Statistics accurate ✅
- [x] No conflicts with existing systems ✅
- [x] Error handling robust ✅
- [x] Logging comprehensive ✅
- [x] Performance acceptable ✅

---

**Status:** ✅ **COMPREHENSIVELY REVIEWED** - 65+ issues identified and fixed across 6 review rounds  
**Estimated Time:** 5-6 hours (Phase 1-4), 8.5-10.5 hours (with enhancements)  
**Priority:** Medium (enhancement, not critical)

**Review Notes:**
- **Round 1 Fixes:** All critical issues resolved
  - Variable names corrected (`execution` → `execution_manager`)
  - Return value checks corrected (`success` → `ok`)
  - Trade idea field names corrected (`entry` → `entry_price`)
  - Method signatures corrected (`stop_loss`/`take_profit` → `sl`/`tp`)
  - Missing imports added (`timedelta`, `json`, `os`)
  - `get_status()` bug fixed (`time.isoformat()` → `dt.isoformat()`)
  - `get_candles()` return type handling added (uses `Candle.to_dict()`)
  - `atr1` parameter added to execution call
  
- **Round 2 Fixes:** Additional issues resolved
  - `self.config` initialization added
  - `self.enabled` initialization before config loading
  - `config_path` parameter added to `__init__`
  - Config reload error handling improved (JSON validation)
  - Thread safety added to config reload
  - Config validation added (range checks)
  - Execution validation config access fixed (nested path)
  
- **Round 3 Fixes:** API integration issues resolved
  - `load_config()` function replaced with `json.load()` (function doesn't exist)
  - News service API fixed (`is_blackout()` instead of `get_news_status()`)
  - Config reload timing optimized (check every 60s, not every loop)
  - Session manager API handling improved (supports multiple return types)
  - Performance metrics initialized in `__init__` (not just Phase 5.4)
  
- **Round 4 Fixes:** Final integration issues resolved
  - `get_deals_by_position()` replaced with MT5 `history_deals_get()` (method doesn't exist)
  - Thread safety improved for `self.symbols` update (copy list to avoid iteration errors)
  - Error handling added for `get_positions()` return type (handles None, objects, dicts)
  - Trade idea validation added (checks required fields before execution)
  
- **Logic & Non-Runtime Issues:** Critical logic and data consistency issues resolved
  - Double-counting of execution failures fixed
  - Thread safety added for position limit checks (prevents race conditions)
  - Thread safety added for `active_positions` updates
  - Position cleanup optimized (periodic instead of every check)
  - Unbounded dictionary growth prevented (cleanup removed symbols)
  - Position verification before tracking (handles immediate closures)
  - Thread safety added for statistics updates
  - Result structure validation added
  
- **Final Comprehensive Review:** Additional critical issues resolved
  - Missing null checks for dependencies (streamer, engine, execution_manager)
  - Missing error handling for engine initialization
  - Missing graceful degradation (mark components as available)
  - Missing shutdown cleanup (resource management)
  - Missing configuration validation (type and range checks)
  - Missing error recovery for monitor loop (circuit breaker)
  - Missing validation for component availability before use
  
- See `MICRO_SCALP_PLAN_REVIEW_ISSUES.md`, `MICRO_SCALP_PLAN_REVIEW_ISSUES_ROUND2.md`, `MICRO_SCALP_PLAN_REVIEW_ISSUES_ROUND3.md`, `MICRO_SCALP_PLAN_REVIEW_ISSUES_ROUND4.md`, `MICRO_SCALP_PLAN_REVIEW_LOGIC_ISSUES.md`, and `MICRO_SCALP_PLAN_FINAL_COMPREHENSIVE_REVIEW.md` for full review details

---

## ✅ **Implementation Summary**

### **Phase 1: Core Monitoring Component** - ✅ **COMPLETED** (2025-12-02)

**Files Created:**
- ✅ `infra/micro_scalp_monitor.py` - Core monitoring component (692 lines)
- ✅ `config/micro_scalp_automation.json` - Configuration file
- ✅ `test_micro_scalp_monitor.py` - Test suite (7/7 tests passed)

**Files Modified:**
- ✅ `app/main_api.py` - Integration with startup/shutdown handlers and status endpoint

**Features Implemented:**
- ✅ Continuous monitoring loop (5-second intervals)
- ✅ Configuration loading and validation
- ✅ Thread-safe statistics tracking
- ✅ Rate limiting and position management
- ✅ Error recovery with circuit breaker
- ✅ Graceful degradation for missing components
- ✅ Hot config reload (every 60 seconds)
- ✅ Integration with existing components (engine, execution_manager, streamer)
- ✅ News blackout detection
- ✅ Session filtering support
- ✅ Status endpoint: `/micro-scalp/status`

**Test Results:**
- ✅ 7/7 tests passed
- ✅ All core functionality verified
- ✅ Thread safety confirmed
- ✅ Error handling validated
- ✅ Graceful degradation tested

### **Phase 2: Configuration Management** - ✅ **COMPLETED** (2025-12-02)

**Enhancements Implemented:**
- ✅ Enhanced configuration file with all Phase 2 options:
  - Rate limiting (hourly/daily limits)
  - Position limits (per-symbol and total)
  - Session filtering (preferred sessions)
  - Risk per trade
- ✅ Advanced rate limiting:
  - Hourly trade limit per symbol (`max_trades_per_hour`)
  - Daily trade limit per symbol (`max_trades_per_day`)
  - Automatic cleanup of old entries
  - Thread-safe tracking
- ✅ Enhanced position management:
  - Per-symbol position limits (`max_positions_per_symbol`)
  - Total positions limit across all symbols (`max_total_positions`)
  - Periodic cleanup of closed positions
- ✅ Session filtering:
  - Preferred sessions configuration
  - Integration with session manager
  - Graceful fallback if session manager unavailable
  - Session check in monitoring loop
- ✅ Hot config reload:
  - All new config options reloaded dynamically
  - Thread-safe updates
  - Symbol list changes handled safely
  - Rate limit tracking cleanup for removed symbols

### **Phase 3: Integration with Main API** - ✅ **COMPLETED** (2025-12-02)

**Integration Points:**
- ✅ Monitor initialized in `startup_event()`:
  - All dependencies initialized (M1DataFetcher, M1Analyzer, SpreadTracker)
  - MicroScalpEngine created with proper config
  - MicroScalpExecutionManager created with config
  - MicroScalpMonitor initialized with all components
  - Monitor started automatically if enabled in config
- ✅ Monitor stopped in `shutdown_event()`:
  - Clean shutdown with proper thread joining
  - Only stops if currently monitoring
- ✅ Status endpoint: `/micro-scalp/status`:
  - Returns comprehensive status and statistics
  - Includes config information
  - Proper error handling
  - Standardized response format with `ok`, `status`, and `timestamp`

**Features:**
- ✅ Graceful initialization (continues if components unavailable)
- ✅ Config-based enable/disable
- ✅ Proper error handling and logging
- ✅ Integration with existing services (streamer, MT5, session manager, news service)

### **Phase 4: Testing & Validation** - ✅ **COMPLETED** (2025-12-02)

**Test Suites Created:**
- ✅ `test_micro_scalp_monitor.py` - Core functionality tests (7/7 passed)
- ✅ `test_phase2_config.py` - Phase 2 configuration tests (5/5 passed)
- ✅ `test_phase3_integration.py` - Phase 3 API integration tests (5/5 passed)

**Test Coverage:**
- ✅ Monitor initialization and configuration
- ✅ Thread safety and error handling
- ✅ Rate limiting and position management
- ✅ Session filtering
- ✅ Config validation and hot reload
- ✅ API integration (startup/shutdown/status endpoint)
- ✅ All validation checklist items verified

**Validation Results:**
- ✅ All core functionality tests passed (7/7)
- ✅ All Phase 2 config tests passed (5/5)
- ✅ All Phase 3 integration tests passed (5/5)
- ✅ No linter errors
- ✅ Import verification successful
- ✅ All validation checklist items completed

### **Phase 5: Enhanced Features** - ✅ **PARTIALLY COMPLETED** (2025-12-02)

**Implemented Features:**
- ✅ **5.1 Dynamic Configuration Reload** - Hot-reload config without restart
- ✅ **5.3 Execution Confirmation Layer** - Pre-execution validation (spread, tick alignment, spread tracker)
- ✅ **5.4 Performance Metrics Extension** - R-multiples, latency, win rate tracking
- ✅ **5.5 Session Bias Integration** - Session-based filtering
- ✅ **5.6 Discord Notifications** - Execution, error, and performance alerts

**Optional Features (Not Implemented):**
- ⏸️ **5.2 Adaptive Rate Limiting** - Dynamic cooldown based on win rate and volatility (can be added later if needed)

**Implementation Details:**
- ✅ Execution validation checks spread percentage, tick alignment, and spread tracker
- ✅ Performance metrics track R-multiples, execution latency, hold time, and streaks
- ✅ Discord notifications sent for successful executions and errors
- ✅ Position performance updated automatically when positions close

**Next Steps:**
- Phase 5.2 (Adaptive Rate Limiting) is optional and can be added if needed
- System is production-ready for all implemented phases (1-5)

---

## 📊 **FINAL IMPLEMENTATION STATUS**

### **Overall Completion: 95%** ✅

**Completed Phases:**
- ✅ **Phase 1: Core Monitoring Component** (100%) - Completed 2025-12-02
- ✅ **Phase 2: Configuration Management** (100%) - Completed 2025-12-02
- ✅ **Phase 3: Integration with Main API** (100%) - Completed 2025-12-02
- ✅ **Phase 4: Testing & Validation** (100%) - Completed 2025-12-02
- ✅ **Phase 5: Enhanced Features** (83% - 5 of 6 features) - Completed 2025-12-02

**Phase 5 Feature Breakdown:**
- ✅ 5.1 Dynamic Configuration Reload
- ⏸️ 5.2 Adaptive Rate Limiting (Optional - not implemented)
- ✅ 5.3 Execution Confirmation Layer
- ✅ 5.4 Performance Metrics Extension
- ✅ 5.5 Session Bias Integration
- ✅ 5.6 Discord Notifications

**Production Readiness:**
- ✅ All core functionality implemented and tested
- ✅ All critical Phase 5 features implemented
- ✅ System fully integrated with main API
- ✅ Comprehensive test coverage (17/17 tests passed)
- ✅ Documentation complete

**Files Created/Modified:**
- ✅ `infra/micro_scalp_monitor.py` - Core monitoring component (735+ lines)
- ✅ `config/micro_scalp_automation.json` - Configuration file
- ✅ `app/main_api.py` - Integration and status endpoint
- ✅ `test_micro_scalp_monitor.py` - Phase 1 tests (7/7 passed)
- ✅ `test_phase2_config.py` - Phase 2 tests (5/5 passed)
- ✅ `test_phase3_integration.py` - Phase 3 tests (5/5 passed)

**Key Features Implemented:**
- ✅ Continuous symbol monitoring (5-second intervals)
- ✅ Immediate execution (no plan creation required)
- ✅ Rate limiting (hourly/daily limits)
- ✅ Position management (per-symbol and total limits)
- ✅ Session filtering
- ✅ News blackout detection
- ✅ Pre-execution validation (spread, tick alignment)
- ✅ Performance metrics tracking (R-multiples, latency, streaks)
- ✅ Discord notifications (executions and errors)
- ✅ Hot config reload
- ✅ Circuit breaker protection
- ✅ Thread-safe operations

**System Status: PRODUCTION READY** 🚀

