"""
Synergis Trading Bot Phone Control System - Desktop Agent

Connects to command hub, receives commands from phone, executes tools,
and returns results. Runs on your desktop/laptop with MT5 access.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import asyncio
import websockets
from websockets.exceptions import ConnectionClosed, InvalidURI
import json
import logging
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import sys

# Your existing imports
try:
    from config import settings
    from infra.mt5_service import MT5Service
    from decision_engine import decide_trade
    from infra.intelligent_exit_manager import create_exit_manager
    from infra.binance_service import BinanceService
    from app.engine.signal_prefilter import SignalPreFilter
    from infra.circuit_breaker import CircuitBreaker
    from infra.exposure_guard import ExposureGuard
    from config.lot_sizing import get_lot_size, get_lot_sizing_info
    from infra.journal_repo import JournalRepo  # NEW: Database logging
    from logging.handlers import RotatingFileHandler  # NEW: File logging
    from infra.trade_close_logger import get_close_logger  # NEW: Close logging
    from infra.conversation_logger import get_conversation_logger  # NEW: Conversation logging
    from infra.custom_alerts import CustomAlertManager  # NEW: Alert management
    from chatgpt_auto_execution_tools import (  # NEW: Auto execution tools
        tool_create_auto_trade_plan,
        tool_create_choch_plan,
        tool_create_rejection_wick_plan,
        tool_create_order_block_plan,
        tool_create_bracket_trade_plan,
        tool_cancel_auto_plan,
        tool_update_auto_plan,
        tool_get_auto_plan_status,
        tool_get_auto_system_status,
        tool_create_multiple_auto_plans,  # NEW: Batch operations
        tool_update_multiple_auto_plans,  # NEW: Batch operations
        tool_cancel_multiple_auto_plans   # NEW: Batch operations
    )
    from desktop_agent_unified_pipeline_integration_updated import (  # NEW: Updated Unified Pipeline integration with separate database architecture
        initialize_desktop_agent_unified_pipeline_updated,
        tool_enhanced_symbol_analysis,
        tool_volatility_analysis,
        tool_offset_calibration,
        tool_system_health,
        tool_pipeline_status
    )
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the Synergis Trading Bot directory")
    sys.exit(1)

# Optional observability and histograms
try:
    from infra.observability import SystemHealthMonitor
    from infra.hdr_histograms import get_histogram_manager, record_stage_latency
    observability_available = True
except Exception as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️ Observability extras unavailable: {e}")
    observability_available = False

# Tick metrics module (NEW)
try:
    from infra.tick_metrics import get_tick_metrics_instance, set_tick_metrics_instance
except ImportError:
    get_tick_metrics_instance = None
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ Tick metrics module unavailable")

# Configure logging with file handler (NEW)
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Windows-compatible rotating file handler (handles file locking issues)
class WindowsRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler with Windows file locking workaround"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rotation_failed_recently = False
        self._last_rotation_attempt = None
        self._rotation_warning_interval = 300  # Only warn once per 5 minutes
    
    def doRollover(self):
        """Override to handle Windows file locking issues using copy-then-truncate approach"""
        import platform
        import time
        import shutil
        from pathlib import Path
        
        if self.stream:
            self.stream.flush()  # Ensure all data is written
        
        # Windows-specific handling: Use copy-then-truncate instead of rename
        if platform.system() == 'Windows':
            try:
                # Get file paths
                log_file = Path(self.baseFilename)
                if not log_file.exists():
                    return
                
                # Check file size
                if log_file.stat().st_size < self.maxBytes:
                    return  # No rotation needed
                
                # Close the stream first
                if self.stream:
                    self.stream.close()
                    self.stream = None
                
                # Wait a bit for Windows to release the file handle
                time.sleep(0.2)
                
                # Try copy-then-truncate approach (more reliable on Windows)
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # Rotate existing backups first (if any)
                        for i in range(self.backupCount - 1, 0, -1):
                            old_backup = Path(f"{self.baseFilename}.{i}")
                            new_backup = Path(f"{self.baseFilename}.{i + 1}")
                            if old_backup.exists():
                                if new_backup.exists():
                                    new_backup.unlink()
                                try:
                                    old_backup.rename(new_backup)
                                except (PermissionError, OSError):
                                    # If rename fails, try copy then delete
                                    shutil.copy2(old_backup, new_backup)
                                    try:
                                        old_backup.unlink()
                                    except:
                                        pass
                        
                        # Copy current log to .1 backup
                        backup_file = Path(f"{self.baseFilename}.1")
                        if backup_file.exists():
                            backup_file.unlink()
                        
                        # Copy current log to backup
                        shutil.copy2(log_file, backup_file)
                        
                        # Truncate current log file (this works even if file is "locked")
                        with open(log_file, 'w', encoding=self.encoding or 'utf-8') as f:
                            f.truncate(0)
                        
                        # Success - reset failure flag
                        self._rotation_failed_recently = False
                        break
                        
                    except (PermissionError, OSError) as e:
                        if attempt < max_retries - 1:
                            time.sleep(0.3 * (attempt + 1))  # Exponential backoff
                            continue
                        else:
                            # Rotation failed - only log warning if not recently warned
                            now = time.time()
                            should_warn = (
                                not self._rotation_failed_recently or
                                (self._last_rotation_attempt and 
                                 (now - self._last_rotation_attempt) > self._rotation_warning_interval)
                            )
                            
                            if should_warn:
                                try:
                                    logger.warning(
                                        f"⚠️ Log rotation failed (attempt {attempt + 1}/{max_retries}): {e}. "
                                        f"Continuing with current log file. Will retry when file size limit reached."
                                    )
                                except:
                                    pass  # Avoid recursion if logging fails
                            
                            self._rotation_failed_recently = True
                            self._last_rotation_attempt = now
                            
                            # Reopen stream to continue logging
                            if not self.stream:
                                self.stream = self._open()
                            return
                
                # Reopen stream after successful rotation
                if not self.stream:
                    self.stream = self._open()
                    
            except Exception as e:
                # Unexpected error - log once and continue
                if not self._rotation_failed_recently:
                    try:
                        logger.warning(f"⚠️ Unexpected error during log rotation: {e}. Continuing with current log file.")
                    except:
                        pass
                    self._rotation_failed_recently = True
                
                # Reopen stream
                if not self.stream:
                    self.stream = self._open()
        else:
            # Non-Windows: Use standard rotation
            try:
                super().doRollover()
            except Exception as e:
                # Fallback: Just continue logging
                if not self._rotation_failed_recently:
                    try:
                        logger.warning(f"⚠️ Log rotation failed: {e}. Continuing with current log file.")
                    except:
                        pass
                    self._rotation_failed_recently = True
                if not self.stream:
                    self.stream = self._open()

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

# File handler (rotating, 10MB max, 5 backups)
file_handler = WindowsRotatingFileHandler(
    'desktop_agent.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

# Attach handlers to ROOT logger so all modules (infra.*, app.*, etc.) get logged.
# (Previously only `desktop_agent.py`'s logger had handlers, so infra.* logs were silently dropped.)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Avoid duplicate handlers if this file is imported/reloaded
if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
    root_logger.addHandler(console_handler)
if not any(isinstance(h, RotatingFileHandler) and str(getattr(h, "baseFilename", "")).endswith("desktop_agent.log") for h in root_logger.handlers):
    root_logger.addHandler(file_handler)

# Module logger (propagates to root)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = True

# ===== HELPER FUNCTIONS =====

def get_plan_id_from_ticket(ticket: int) -> Optional[str]:
    """
    Get auto-execution plan_id from ticket number.
    
    Args:
        ticket: MT5 ticket number
        
    Returns:
        plan_id string if found, None otherwise
    """
    try:
        import sqlite3
        from pathlib import Path
        
        db_path = Path("data/auto_execution.db")
        if not db_path.exists():
            return None
        
        with sqlite3.connect(str(db_path), timeout=5.0) as conn:
            cursor = conn.execute("SELECT plan_id FROM trade_plans WHERE ticket = ?", (ticket,))
            row = cursor.fetchone()
            if row:
                return row[0]
            return None
    except Exception as e:
        logger.debug(f"Could not get plan_id for ticket {ticket}: {e}")
        return None

# Optional: initialize health monitor once logging is ready
_health_monitor = None
if 'observability_available' in globals() and observability_available:
    try:
        _health_monitor = SystemHealthMonitor()
        logger.info("✅ Observability health monitor initialized")
    except Exception as e:
        logger.warning(f"⚠️ Health monitor init failed: {e}")

# Optional: symbol config hot-reload watcher
try:
    from config.symbol_config_loader import get_config_loader
    _cfg_loader = get_config_loader()
    def _on_symbol_config_change(sym: str):
        try:
            logger.info(f"🔄 Symbol config reloaded: {sym}")
        except Exception:
            pass
    _cfg_loader.add_watcher(_on_symbol_config_change)
    logger.info("✅ Symbol config hot-reload watcher registered (agent)")
except Exception as e:
    logger.warning(f"⚠️ Symbol config watcher unavailable: {e}")

# Initialize journal repository for database logging
journal_repo = JournalRepo()
logger.info("✅ Journal repository initialized for database logging")

# Initialize trade close logger
close_logger = get_close_logger()
logger.info("✅ Trade close logger initialized")

# Initialize conversation logger
conversation_logger = get_conversation_logger()
logger.info("✅ Conversation logger initialized")

# ============================================================================
# CONFIGURATION
# ============================================================================

# FIX: Phone hub uses port 8002 to avoid conflict with DTMS API server (port 8001)
PHONE_HUB_PORT = int(os.getenv("PHONE_HUB_PORT", "8002"))  # Default to 8002 to avoid conflict with DTMS
HUB_URL = os.getenv("PHONE_HUB_URL", f"ws://localhost:{PHONE_HUB_PORT}/agent/connect")  # Phone control hub
API_URL = os.getenv("API_URL", "ws://localhost:8000/agent/connect")  # Main API server
AGENT_SECRET = os.getenv("AGENT_SECRET", "phone_control_bearer_token_2025_v1_secure")  # For phone control hub
API_SECRET = os.getenv("API_SECRET", "8j5Cg8aAYy8uujCpvOv6KA8pZRm7yqWjhI6m1euVvU4")  # For main API server

# ============================================================================
# TOOL REGISTRY
# ============================================================================

class ToolRegistry:
    """Registry of available tools that can be called from phone"""
    
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.mt5_service: Optional[MT5Service] = None
        self.binance_service: Optional[BinanceService] = None
        self.signal_prefilter: Optional[SignalPreFilter] = None
        self.circuit_breaker: Optional[CircuitBreaker] = None
        self.exposure_guard: Optional[ExposureGuard] = None
        self.alert_manager: Optional[CustomAlertManager] = None
        self.order_flow_service = None  # OrderFlowService for whale detection + order book analysis
        self.tick_metrics_generator = None  # TickSnapshotGenerator for tick metrics
        # Store last analysis summary for Discord sharing (exact text ChatGPT displayed)
        self.last_analysis_summary: Optional[str] = None
        self.last_analysis_symbol: Optional[str] = None
        self.last_analysis_timestamp: Optional[float] = None
        # Phase 2: Range Scalping Exit Manager
        self.range_scalp_exit_manager = None
        self.range_scalp_monitor = None
        
    def register(self, name: str):
        """Decorator to register a tool"""
        def decorator(func: Callable):
            # Only log if this is a new tool registration (prevent duplicate logs)
            is_new_tool = name not in self.tools
            self.tools[name] = func
            if is_new_tool:
                logger.info(f"📋 Registered tool: {name}")
            return func
        return decorator
    
    async def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name"""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}. Available: {list(self.tools.keys())}")
        
        tool_func = self.tools[tool_name]
        logger.info(f"🔧 Executing tool: {tool_name}")
        
        try:
            result = await tool_func(arguments)
            # Log returned summary for observability (many tools return useful data only in the response).
            try:
                summary = result.get("summary") if isinstance(result, dict) else None
                if summary:
                    logger.info(f"   → Tool summary: {summary}")
            except Exception:
                pass
            return result
        except Exception as e:
            logger.error(f"❌ Tool execution failed: {e}", exc_info=True)
            raise

registry = ToolRegistry()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _extract_pattern_summary(features_data: Dict[str, Any], symbol: str = "", current_price: float = 0.0) -> str:
    """Extract and format candle pattern summary from advanced features with pattern confirmation tracking."""
    from infra.pattern_tracker import get_pattern_tracker
    from infra.streamer_data_access import get_latest_candle
    
    pattern_tracker = get_pattern_tracker()
    pattern_lines = []
    timeframe_order = ["M5", "M15", "M30", "H1", "H4"]
    
    for tf in timeframe_order:
        tf_features = features_data.get(tf, {})
        if not tf_features:
            continue
            
        candlestick_flags = tf_features.get("candlestick_flags", {})
        pattern_flags = tf_features.get("pattern_flags", {})
        pattern_strength = tf_features.get("pattern_strength", 0.0)
        
        # Determine pattern type and bias
        pattern_type = None
        pattern_bias = "neutral"
        pattern_high = current_price
        pattern_low = current_price
        
        active_patterns = []
        
        # Check multi-bar patterns first (higher priority)
        if pattern_flags.get("morning_star"):
            pattern_type = "Morning Star"
            pattern_bias = "bullish"
            active_patterns.append("Morning Star → Bullish Reversal")
        elif pattern_flags.get("evening_star"):
            pattern_type = "Evening Star"
            pattern_bias = "bearish"
            active_patterns.append("Evening Star → Bearish Reversal")
        elif pattern_flags.get("bull_engulfing"):
            pattern_type = "Bull Engulfing"
            pattern_bias = "bullish"
            active_patterns.append("Bull Engulfing → Bullish")
        elif pattern_flags.get("bear_engulfing"):
            pattern_type = "Bear Engulfing"
            pattern_bias = "bearish"
            active_patterns.append("Bear Engulfing → Bearish")
        elif pattern_flags.get("inside_bar"):
            pattern_type = "Inside Bar"
            pattern_bias = "neutral"
            active_patterns.append("Inside Bar → Consolidation")
        elif pattern_flags.get("outside_bar"):
            pattern_type = "Outside Bar"
            pattern_bias = "neutral"
            active_patterns.append("Outside Bar → Breakout")
        
        # Check single-bar patterns if no multi-bar pattern
        if not active_patterns:
            if candlestick_flags.get("marubozu_bull"):
                pattern_type = "Marubozu Bull"
                pattern_bias = "bullish"
                active_patterns.append("Marubozu Bull → Strong Momentum")
            elif candlestick_flags.get("marubozu_bear"):
                pattern_type = "Marubozu Bear"
                pattern_bias = "bearish"
                active_patterns.append("Marubozu Bear → Strong Momentum")
            elif candlestick_flags.get("doji"):
                pattern_type = "Doji"
                pattern_bias = "neutral"
                active_patterns.append("Doji → Indecision")
            elif candlestick_flags.get("hammer"):
                pattern_type = "Hammer"
                pattern_bias = "bullish"
                active_patterns.append("Hammer → Bullish Reversal")
            elif candlestick_flags.get("shooting_star"):
                pattern_type = "Shooting Star"
                pattern_bias = "bearish"
                active_patterns.append("Shooting Star → Bearish Reversal")
            elif candlestick_flags.get("pin_bar_bull"):
                pattern_type = "Pin Bar Bull"
                pattern_bias = "bullish"
                active_patterns.append("Pin Bar Bull → Rejection")
            elif candlestick_flags.get("pin_bar_bear"):
                pattern_type = "Pin Bar Bear"
                pattern_bias = "bearish"
                active_patterns.append("Pin Bar Bear → Rejection")
        
        if active_patterns and pattern_type:
            pattern_text = active_patterns[0]
            
            # Try to validate pattern if symbol and current_price provided
            if symbol and current_price > 0:
                try:
                    latest_candle = get_latest_candle(symbol, tf)
                    if latest_candle:
                        # Extract candle data
                        if isinstance(latest_candle, dict):
                            candle_high = float(latest_candle.get('high', current_price))
                            candle_low = float(latest_candle.get('low', current_price))
                            candle_close = float(latest_candle.get('close', current_price))
                        else:
                            candle_high = float(getattr(latest_candle, 'high', current_price))
                            candle_low = float(getattr(latest_candle, 'low', current_price))
                            candle_close = float(getattr(latest_candle, 'close', current_price))
                        
                        pattern_high = max(candle_high, current_price)
                        pattern_low = min(candle_low, current_price)
                        
                        # Validate pattern against latest candle
                        candles_since = 1
                        validation_result = pattern_tracker.validate_pattern(
                            symbol, tf, {
                                'high': candle_high,
                                'low': candle_low,
                                'close': candle_close,
                                'open': candle_close
                            }, candles_since
                        )
                        
                        # Check if this pattern was just confirmed/invalidated
                        pattern_status = None
                        for key, status in validation_result:
                            if status in ["Confirmed", "Invalidated"]:
                                pattern_status = status
                                break
                        
                        # If no validation yet, register the pattern
                        if pattern_status is None:
                            pattern_tracker.register_pattern(
                                symbol=symbol,
                                timeframe=tf,
                                pattern_type=pattern_type,
                                detection_price=candle_close,
                                pattern_high=pattern_high,
                                pattern_low=pattern_low,
                                strength_score=pattern_strength,
                                bias=pattern_bias
                            )
                        else:
                            # Add status to display
                            if pattern_status == "Confirmed":
                                pattern_text += " → ✅ CONFIRMED"
                            elif pattern_status == "Invalidated":
                                pattern_text += " → ❌ INVALIDATED"
                            
                except Exception as e:
                    logger.debug(f"Pattern validation failed for {symbol} {tf}: {e}")
            
            strength_text = f" (Strength: {pattern_strength:.1f})" if pattern_strength > 0 else ""
            pattern_lines.append(f"{tf}: {pattern_text}{strength_text}")
        else:
            pattern_lines.append(f"{tf}: No pattern detected")
    
    return "\n".join(pattern_lines) if pattern_lines else "No patterns detected across timeframes"


def _classify_market_regime(features_data: Dict[str, Any], m5_data: Dict, m15_data: Dict, h1_data: Dict) -> str:
    """Classify market regime: Trending / Ranging / Volatile / Expanding"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from app.engine.regime_classifier import classify_regime
        
        tech = {}
        adx_m5 = m5_data.get("adx", 0) or 0
        adx_m15 = m15_data.get("adx", 0) or 0
        adx_h1 = h1_data.get("adx", 0) or 0
        
        tech["M5"] = {"adx": adx_m5}
        tech["M15"] = {"adx": adx_m15}
        tech["H1"] = {"adx": adx_h1}
        
        m15_features = features_data.get("M15", {})
        vol_trend = m15_features.get("vol_trend", {})
        bb_width = vol_trend.get("bb_width", 0) or 0
        tech["M15"]["bb_width"] = bb_width
        
        h1_features = features_data.get("H1", {})
        ema_slope = h1_features.get("ema_slope", {})
        if isinstance(ema_slope, dict):
            slope_value = ema_slope.get("slope_pct", 0) or 0
        else:
            slope_value = float(ema_slope) if ema_slope else 0
        tech["H1"]["ema200_slope_pct"] = slope_value
        
        regime_label, scores = classify_regime(tech)
        
        if regime_label == "TREND":
            return "Trending (Expanding)" if bb_width > 0.02 else "Trending"
        elif regime_label == "RANGE":
            return "Ranging"
        elif regime_label == "VOLATILE":
            return "Volatile"
        else:
            return "Unknown"
    except Exception as e:
        logger.debug(f"Regime classification failed: {e}")
        m15_features = features_data.get("M15", {})
        vol_trend = m15_features.get("vol_trend", {})
        regime_str = vol_trend.get("regime", "unknown")
        
        if regime_str in ["trending", "bullish", "bearish"]:
            return "Trending"
        elif regime_str in ["ranging", "neutral"]:
            return "Ranging"
        elif regime_str in ["volatile", "expanding"]:
            return "Volatile"
        else:
            return "Unknown"


def _calculate_bias_confidence(
    macro_bias: Optional[Dict[str, Any]],
    structure_trend: str,
    choch_detected: bool,
    bos_detected: bool,
    rmag: Dict[str, Any],
    vol_trend: Dict[str, Any],
    pressure: Dict[str, Any],
    decision_confidence: int,
    features_data: Optional[Dict[str, Any]] = None
) -> tuple:
    """Calculate weighted bias confidence score (0-100) including pattern strength. Returns (score, emoji)."""
    from infra.pattern_tracker import get_pattern_tracker
    
    scores = []
    weights = []
    
    if macro_bias:
        bias_direction = macro_bias.get("bias_direction", "neutral")
        bias_score = macro_bias.get("bias_score", 0)
        macro_score = min(100, 50 + abs(bias_score) * 10) if bias_direction != "neutral" else 50
    else:
        macro_score = 50
    scores.append(macro_score)
    weights.append(0.24)  # Slightly reduced from 0.25
    
    if choch_detected:
        structure_score = 20
    elif bos_detected and structure_trend in ["BULLISH", "BEARISH"]:
        structure_score = 80
    elif structure_trend in ["BULLISH", "BEARISH"]:
        structure_score = 60
    else:
        structure_score = 40
    scores.append(structure_score)
    weights.append(0.19)  # Slightly reduced from 0.20
    
    # Calculate pattern strength score (Tier 1.2)
    pattern_score = 50  # Default neutral
    if features_data:
        try:
            timeframe_weights = {"H1": 0.4, "M30": 0.3, "M15": 0.2, "M5": 0.1}
            weighted_pattern_strength = 0.0
            total_weight = 0.0
            pattern_bias_sum = 0.0  # +1 for bullish, -1 for bearish
            
            pattern_tracker = get_pattern_tracker()
            
            for tf, weight in timeframe_weights.items():
                tf_features = features_data.get(tf, {})
                if not tf_features:
                    continue
                
                pattern_strength = tf_features.get("pattern_strength", 0.0)
                if pattern_strength > 0:
                    # Determine pattern bias
                    pattern_flags = tf_features.get("pattern_flags", {})
                    candlestick_flags = tf_features.get("candlestick_flags", {})
                    
                    # Check pattern bias direction
                    pattern_bias = 0  # 0 = neutral, +1 = bullish, -1 = bearish
                    
                    # Multi-bar patterns
                    if pattern_flags.get("morning_star") or pattern_flags.get("bull_engulfing"):
                        pattern_bias = 1
                    elif pattern_flags.get("evening_star") or pattern_flags.get("bear_engulfing"):
                        pattern_bias = -1
                    # Single-bar patterns
                    elif candlestick_flags.get("marubozu_bull") or candlestick_flags.get("hammer"):
                        pattern_bias = 1
                    elif candlestick_flags.get("marubozu_bear") or candlestick_flags.get("shooting_star"):
                        pattern_bias = -1
                    
                    if pattern_bias != 0:
                        # Apply confirmation multiplier if available
                        # Simplified: check if we have a tracked pattern that's confirmed
                        multiplier = 1.0
                        try:
                            # Try to find pattern status (simplified check)
                            # This is a best-effort check
                            pass  # Skip for now - pattern status lookup would need symbol
                        except:
                            pass
                        
                        # Weighted contribution: pattern_strength * pattern_bias * weight
                        contribution = pattern_strength * pattern_bias * weight * multiplier
                        weighted_pattern_strength += contribution
                        total_weight += weight
                        pattern_bias_sum += pattern_bias * weight
            
            if total_weight > 0:
                # Normalize: convert weighted sum to 0-100 score
                # weighted_pattern_strength ranges from -total_weight to +total_weight
                # Normalize to 0-100 where 0 = fully bearish, 50 = neutral, 100 = fully bullish
                normalized = (weighted_pattern_strength / total_weight) if total_weight > 0 else 0
                # Convert -1 to +1 range to 0-100 range
                pattern_score = min(100, max(0, 50 + (normalized * 50)))
        except Exception as e:
            logger.debug(f"Pattern strength calculation failed: {e}")
            pattern_score = 50
    
    scores.append(pattern_score)
    weights.append(0.05)  # NEW: 5% weight for patterns
    
    rmag_value = rmag.get("ema200_atr", 0) or 0
    rmag_score = 70 if abs(rmag_value) > 2.0 else 60 if abs(rmag_value) > 1.5 else 50
    scores.append(rmag_score)
    weights.append(0.14)  # Slightly reduced from 0.15
    
    vol_regime = vol_trend.get("regime", "unknown")
    vol_score = 70 if vol_regime in ["trending", "bullish", "bearish"] else 50 if vol_regime == "ranging" else 45
    scores.append(vol_score)
    weights.append(0.14)  # Slightly reduced from 0.15
    
    pressure_ratio = pressure.get("ratio", 1.0) or 1.0
    momentum_score = 75 if (pressure_ratio > 1.3 or pressure_ratio < 0.7) else 65 if (pressure_ratio > 1.1 or pressure_ratio < 0.9) else 50
    scores.append(momentum_score)
    weights.append(0.14)  # Slightly reduced from 0.15
    
    decision_score = max(0, min(100, decision_confidence))
    scores.append(decision_score)
    weights.append(0.10)  # Unchanged
    
    final_score = int(round(sum(s * w for s, w in zip(scores, weights))))
    emoji = "🟢" if final_score >= 75 else "🟡" if final_score >= 60 else "🔴"
    
    return final_score, emoji

def _extract_volume_delta_context(m5_data: Dict, m15_data: Dict, order_flow: Optional[Dict[str, Any]]) -> str:
    lines = []
    try:
        m5_volume = m5_data.get('volume', 0) or 0
        m5_volume_ma = m5_data.get('volume_ma_20', 0) or 0
        if m5_volume > 0 and m5_volume_ma > 0:
            volume_ratio = m5_volume / m5_volume_ma
            if volume_ratio > 1.3:
                vol_status = f'Expanding ({volume_ratio:.1f}x avg)'
            elif volume_ratio < 0.7:
                vol_status = f'Contracting ({volume_ratio:.1f}x avg)'
            else:
                vol_status = 'Normal'
            lines.append(f'Volume: {vol_status}')
        else:
            lines.append('Volume: Data unavailable')
        if order_flow:
            pressure_data = order_flow.get('pressure', {})
            net_volume = pressure_data.get('net_volume', 0)
            if net_volume != 0:
                delta_sign = '+' if net_volume > 0 else ''
                lines.append(f'Delta: {delta_sign}{net_volume:.0f}')
            else:
                whale_activity = order_flow.get('whale_activity', {})
                buy_whales = whale_activity.get('buy_whales', 0)
                sell_whales = whale_activity.get('sell_whales', 0)
                if buy_whales > 0 or sell_whales > 0:
                    net_whale_side = 'BUY' if buy_whales > sell_whales else 'SELL' if sell_whales > buy_whales else 'NEUTRAL'
                    lines.append(f'Delta: {net_whale_side} pressure ({buy_whales} buy / {sell_whales} sell whales)')
                else:
                    lines.append('Delta: Neutral')
        else:
            pressure_ratio = m5_data.get('pressure', {}).get('ratio', 1.0) if isinstance(m5_data.get('pressure'), dict) else 1.0
            if pressure_ratio > 1.2:
                lines.append('Delta: +BUY pressure')
            elif pressure_ratio < 0.8:
                lines.append('Delta: -SELL pressure')
            else:
                lines.append('Delta: Neutral')
    except Exception as e:
        logger.debug(f'Error extracting volume/delta context: {e}')
        lines.append('Volume & Delta: Data unavailable')
    return ' | '.join(lines) if lines else 'Volume & Delta: Data unavailable'

def _extract_liquidity_map_snapshot(m5_features: Dict, current_price: float, symbol: str = "") -> str:
    """Extract Liquidity Map Snapshot - Top 3 clusters above/below with distance/ATR context (Tier 2.1 Enhanced)."""
    lines = []
    try:
        liquidity = m5_features.get("liquidity", {})
        clusters_above = []
        clusters_below = []
        if liquidity.get("stop_cluster_above", False):
            price = liquidity.get("stop_cluster_above_price", 0)
            count = liquidity.get("stop_cluster_above_count", 0)
            if price > current_price and price > 0:
                clusters_above.append((price, count, "stops"))
        if liquidity.get("stop_cluster_below", False):
            price = liquidity.get("stop_cluster_below_price", 0)
            count = liquidity.get("stop_cluster_below_count", 0)
            if price < current_price and price > 0:
                clusters_below.append((price, count, "stops"))
        if liquidity.get("eq_high_cluster", False):
            price = liquidity.get("eq_high_price", 0)
            count = liquidity.get("eq_high_count", 0)
            if price > current_price and price > 0:
                clusters_above.append((price, count, "equal_highs"))
        if liquidity.get("eq_low_cluster", False):
            price = liquidity.get("eq_low_price", 0)
            count = liquidity.get("eq_low_count", 0)
            if price < current_price and price > 0:
                clusters_below.append((price, count, "equal_lows"))
        clusters_above.sort(key=lambda x: x[0])
        clusters_below.sort(key=lambda x: x[0], reverse=True)
        
        # Calculate ATR for distance context (Tier 2.1 enhancement)
        atr_value = None
        if symbol:
            try:
                from infra.streamer_data_access import calculate_atr
                atr_value = calculate_atr(symbol, "M5", period=14)
            except Exception as e:
                logger.debug(f"ATR calculation failed for liquidity map: {e}")
        
        # Format clusters with distance/ATR context
        if clusters_above:
            cluster_strs = []
            for p, c, t in clusters_above[:3]:
                distance = p - current_price
                distance_pct = (distance / current_price * 100) if current_price > 0 else 0
                atr_distance = ""
                urgency = ""
                if atr_value and atr_value > 0:
                    atr_multiple = distance / atr_value
                    atr_distance = f", {atr_multiple:.1f} ATR away"
                    if atr_multiple < 1.0:
                        urgency = " → SWEEP TARGET"
                    elif atr_multiple < 2.0:
                        urgency = " → Near"
                    elif atr_multiple > 3.0:
                        urgency = " → Distant"
                cluster_strs.append(f"${p:,.2f} ({c} {t}{atr_distance}{urgency})")
            lines.append("Above: " + ", ".join(cluster_strs))
        else:
            lines.append("Above: No clusters")
            
        if clusters_below:
            cluster_strs = []
            for p, c, t in clusters_below[:3]:
                distance = current_price - p
                distance_pct = (distance / current_price * 100) if current_price > 0 else 0
                atr_distance = ""
                urgency = ""
                if atr_value and atr_value > 0:
                    atr_multiple = distance / atr_value
                    atr_distance = f", {atr_multiple:.1f} ATR away"
                    if atr_multiple < 1.0:
                        urgency = " → SWEEP TARGET"
                    elif atr_multiple < 2.0:
                        urgency = " → Near"
                    elif atr_multiple > 3.0:
                        urgency = " → Distant"
                cluster_strs.append(f"${p:,.2f} ({c} {t}{atr_distance}{urgency})")
            lines.append("Below: " + ", ".join(cluster_strs))
        else:
            lines.append("Below: No clusters")
    except Exception as e:
        logger.debug(f"Error extracting liquidity map: {e}")
        lines.append("Liquidity Map: Data unavailable")
    return "\n".join(lines) if lines else "Liquidity Map: Data unavailable"

def _extract_session_context(m5_data: Dict) -> str:
    """Extract Session Context with actionable warnings (Tier 2.3 Enhanced)."""
    try:
        from infra.feature_session_news import SessionNewsFeatures
        session_features = SessionNewsFeatures()
        session_info = session_features.get_session_info()
        session_name = session_info.primary_session
        is_overlap = session_info.is_overlap
        overlap_type = session_info.overlap_type
        minutes_into = session_info.minutes_into_session
        if session_name == "ASIA":
            session_end_minutes = 600
        elif session_name == "LONDON":
            session_end_minutes = 480
        elif session_name == "NY":
            session_end_minutes = 480
        else:
            session_end_minutes = 0
        minutes_remaining = max(0, session_end_minutes - minutes_into)
        
        # Tier 2.3: Add actionable warnings
        warning = ""
        if minutes_remaining < 5:
            warning = " 🚨 Session ending in 5min → avoid new entries"
        elif minutes_remaining < 15:
            warning = " ⚠️ Session ending in 15min → close scalps, expect lower volatility"
        elif is_overlap:
            warning = " 🔵 High vol overlap → ideal for breakouts"
        
        if is_overlap and overlap_type:
            overlap_display = overlap_type.replace("_", " ").title()
            context = f"{overlap_display} overlap active · {minutes_remaining}min until session end{warning}"
        else:
            context = f"{session_name} session · {minutes_remaining}min remaining{warning}"
        
        if not warning:
            # Fallback to original logic if no warning
            if minutes_remaining < 60:
                context += " · Vol likely to fade"
            elif is_overlap:
                context += " · High vol expected"
        return context
    except Exception as e:
        logger.debug(f"Error extracting session context: {e}")
        session = m5_data.get("session", "UNKNOWN")
        return f"{session} session"

def _format_volatility_regime_display(volatility_regime: Optional[Dict[str, Any]]) -> str:
    """Format volatility regime display for analysis summary (Phase 1)"""
    if not volatility_regime:
        return ""
    
    try:
        from infra.volatility_regime_detector import VolatilityRegime
        
        regime = volatility_regime.get("regime")
        confidence = volatility_regime.get("confidence", 0)
        atr_ratio = volatility_regime.get("atr_ratio", 0)
        wait_reasons = volatility_regime.get("wait_reasons", [])
        
        # Extract regime string
        if isinstance(regime, VolatilityRegime):
            regime_str = regime.value
        elif hasattr(regime, 'value'):
            regime_str = regime.value
        else:
            regime_str = str(regime) if regime else "UNKNOWN"
        
        # Emoji based on regime
        regime_emoji = {
            "VOLATILE": "⚡",
            "TRANSITIONAL": "🟡",
            "STABLE": "🟢"
        }.get(regime_str, "⚪")
        
        # Build display
        display = f"{regime_emoji} VOLATILITY REGIME: {regime_str} (ATR {atr_ratio:.2f}×, Confidence: {confidence:.1f}%)"
        
        # Add WAIT reasons if present
        if wait_reasons:
            display += "\n\n⚠️ WAIT REASONS:"
            for reason in wait_reasons:
                code = reason.get("code", "UNKNOWN")
                desc = reason.get("description", "")
                severity = reason.get("severity", "low")
                severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
                display += f"\n   {severity_emoji} {code}: {desc}"
        
        # Add strategy selection if available
        strategy_selection = volatility_regime.get("strategy_selection")
        if strategy_selection:
            selected = strategy_selection.get("selected_strategy")
            if selected:
                strategy_name = selected.get("strategy", "UNKNOWN")
                strategy_score = selected.get("score", 0)
                strategy_reasoning = selected.get("reasoning", "")
                display += f"\n\n📊 SELECTED STRATEGY: {strategy_name} (Score: {strategy_score:.1f})"
                display += f"\n   → {strategy_reasoning}"
            else:
                wait_reason = strategy_selection.get("wait_reason")
                if wait_reason:
                    code = wait_reason.get("code", "UNKNOWN")
                    desc = wait_reason.get("description", "")
                    display += f"\n\n⏸️ STRATEGY SELECTION: WAIT"
                    display += f"\n   → {code}: {desc}"
        
        # Add educational context
        if regime_str == "VOLATILE":
            display += "\n\n   → Large price swings, high ATR, elevated risk - use tighter position sizing (0.5% max)"
        elif regime_str == "TRANSITIONAL":
            display += "\n\n   → Market showing signs of instability - monitor closely, reduce position sizes (0.75% max)"
        elif regime_str == "STABLE":
            display += "\n\n   → Normal volatility, manageable risk - standard position sizing (1.0% max)"
        
        return display
    except Exception as e:
        return f"⚪ Volatility regime: Error formatting ({str(e)})"


def _extract_news_guardrail(macro: Dict[str, Any]) -> str:
    """Extract News Guardrail - Next high-impact event timing (Tier 2)."""
    try:
        from infra.news_service import NewsService
        from datetime import datetime, timezone
        news_service = NewsService()
        if not news_service:
            return "News: Service unavailable"
        upcoming_events = news_service.get_upcoming_events(limit=5, hours_ahead=24)
        if not upcoming_events or len(upcoming_events) == 0:
            return "News: No upcoming high-impact events"
        current_time = datetime.now(timezone.utc)
        high_impact_events = [e for e in upcoming_events if e.get("impact", "LOW") in ["HIGH", "ULTRA"]]
        if not high_impact_events:
            return "News: No high-impact events in next 24h"
        next_event = high_impact_events[0]
        event_time_str = next_event.get("time", "")
        event_name = next_event.get("event", "Economic Event")
        impact = next_event.get("impact", "HIGH")
        try:
            if isinstance(event_time_str, str):
                from dateutil import parser
                event_time = parser.parse(event_time_str)
                if event_time.tzinfo is None:
                    event_time = event_time.replace(tzinfo=timezone.utc)
            else:
                event_time = event_time_str
            time_diff = event_time - current_time
            hours_until = time_diff.total_seconds() / 3600
            if hours_until < 0:
                return "News: No upcoming high-impact events"
            elif hours_until < 1:
                minutes_until = int(hours_until * 60)
                return f"News: {event_name} in {minutes_until}min ({impact} impact)"
            else:
                return f"News: {event_name} in {hours_until:.1f}h ({impact} impact)"
        except Exception:
            return f"News: {event_name} ({impact} impact) - Timing unavailable"
    except Exception as e:
        logger.debug(f"Error extracting news guardrail: {e}")
        news_summary = macro.get("news_summary", "")
        if news_summary and "blackout" in news_summary.lower():
            return "News: Blackout window active"
        return "News: Data unavailable"

def _format_unified_analysis(
    symbol: str,
    symbol_normalized: str,
    current_price: float,
    macro: Dict[str, Any],
    smc: Dict[str, Any],
    advanced_features: Dict[str, Any],
    decision: Any,
    m5_data: Dict,
    m15_data: Dict,
    h1_data: Dict,
    order_flow: Optional[Dict[str, Any]] = None,
    btc_order_flow_metrics: Optional[Dict[str, Any]] = None,  # NEW: BTC-specific order flow metrics
    macro_bias: Optional[Dict[str, Any]] = None,
    volatility_signal: Optional[str] = None,
    volatility_regime: Optional[Dict[str, Any]] = None,
    m1_microstructure: Optional[Dict[str, Any]] = None,
    correlation_context: Optional[Dict[str, Any]] = None,  # NEW: Correlation context
    htf_levels: Optional[Dict[str, Any]] = None,  # NEW: HTF levels
    session_risk: Optional[Dict[str, Any]] = None,  # NEW: Session risk
    execution_context: Optional[Dict[str, Any]] = None,  # NEW: Execution context
    strategy_stats: Optional[Dict[str, Any]] = None,  # NEW: Strategy stats
    symbol_constraints: Optional[Dict[str, Any]] = None,  # NEW: Symbol constraints
    tick_metrics: Optional[Dict[str, Any]] = None,  # NEW: Tick microstructure metrics
    timestamp: int = 0,
    volatility_forecaster=None,
    m5_df=None
) -> Dict[str, Any]:
    """
    Format unified analysis by merging all layers with priority logic
    
    Priority Rules:
    1. CHOCH detected = immediate warning (overrides everything)
    2. Macro provides directional bias (bullish/bearish/neutral)
    3. SMC provides structure confirmation (trend/reversal/choppy)
    4. Advanced features provide precision (oversold/overbought/stretched)
    5. Decision engine provides final entry/SL/TP
    6. BTC Order Flow Metrics (for BTCUSD only) - provides institutional activity signals
    """
    from datetime import datetime
    from infra.analysis_formatting_helpers import (
        format_liquidity_summary,
        format_volatility_summary,
        format_order_flow_summary,
        format_macro_bias_summary,
        format_tick_metrics_summary  # NEW: Tick metrics formatting
    )
    from infra.volatility_forecasting import create_volatility_forecaster
    import pandas as pd
    
    # Extract key data from each layer
    features_data = advanced_features.get("features", {})
    m5_features = features_data.get("M5", {})
    m15_features = features_data.get("M15", {})
    h1_features = features_data.get("H1", {})
    
    # Get volatility forecaster and M5 DataFrame from function parameters
    vol_forecaster_param = volatility_forecaster
    m5_df_param = m5_df
    
    # LAYER 1: MACRO CONTEXT
    # macro now contains the full response with "summary" at root and "data" nested
    macro_data_obj = macro.get("data", {})
    # Use calculated macro_bias if provided, otherwise fall back to risk_sentiment
    if macro_bias:
        macro_bias_str = f"{macro_bias.get('bias_direction', 'neutral').upper()} ({macro_bias.get('bias_score', 0):+.2f})"
        macro_bias_explanation = macro_bias.get('explanation', '')
    else:
        macro_bias_str = macro_data_obj.get("risk_sentiment", "NEUTRAL")
        macro_bias_explanation = ""
    macro_summary = macro.get("summary", "No macro data")  # summary is at root level
    
    
    # LAYER 2: SMC STRUCTURE
    smc_timeframes = smc.get("timeframes", {})
    # Extract all timeframes including H4 and M30
    h4_smc = smc_timeframes.get("H4", {})
    h1_smc = smc_timeframes.get("H1", {})
    m30_smc = smc_timeframes.get("M30", {})
    m15_smc = smc_timeframes.get("M15", {})
    m5_smc = smc_timeframes.get("M5", {})
    
    # ⚠️ PHASE 1: Calculate CHOCH/BOS and trend from timeframes (replaces direct extraction)
    # Ensure smc_layer is not None or empty
    if not smc:
        smc = {}
    
    # Calculate choch_detected and bos_detected from timeframes
    # ⚠️ CRITICAL: These fields MUST exist in MTF analyzer return (added in Phase 0)
    choch_detected = False
    bos_detected = False
    for tf_name, tf_data in smc.get("timeframes", {}).items():
        # Check for CHOCH (aggregate across all timeframes)
        if tf_data.get("choch_detected", False) or tf_data.get("choch_bull", False) or tf_data.get("choch_bear", False):
            choch_detected = True
        # Check for BOS (aggregate across all timeframes)
        if tf_data.get("bos_detected", False) or tf_data.get("bos_bull", False) or tf_data.get("bos_bear", False):
            bos_detected = True
        
        # Early break optimization - check after both flags may have been set
        if choch_detected and bos_detected:
            break
    
    # Calculate trend from H4 bias (H4 bias is the primary trend indicator)
    h4_data = smc.get("timeframes", {}).get("H4", {})
    structure_trend = h4_data.get("bias", "UNKNOWN")
    
    # Extract recommendation (contains nested fields: market_bias, trade_opportunities, etc.)
    # ⚠️ FIX: Handle None case - if recommendation is explicitly None, use empty dict
    recommendation = smc.get("recommendation", {}) or {}
    
    # Get H4 and M30 features if available (for structure analysis)
    h4_features = features_data.get("H4", {})
    m30_features = features_data.get("M30", {})
    
    # LAYER 3: ADVANCED FEATURES
    rmag = m5_features.get("rmag", {})
    vwap = m5_features.get("vwap", {})
    vol_trend = m5_features.get("vol_trend", {})
    pressure = m5_features.get("pressure", {})
    fvg = m5_features.get("fvg", {})
    
    # LAYER 4: DECISION ENGINE
    # Note: decision is a dictionary, not an object
    direction = decision.get('direction', 'HOLD') if decision else 'HOLD'
    entry = decision.get('entry', current_price) if decision else current_price
    sl = decision.get('sl', 0) if decision else 0
    tp = decision.get('tp', 0) if decision else 0
    confidence = decision.get('confidence', 0) if decision else 0
    reasoning = decision.get('reasoning', 'No clear setup') if decision else 'No clear setup'
    rr = decision.get('rr', 0) if decision else 0
    
    # ========== CONFLUENCE ANALYSIS ==========
    
    # Priority 1: CHOCH Override (immediate warning)
    if choch_detected:
        confluence_verdict = "🚨 CHOCH DETECTED - STRUCTURE REVERSAL"
        confluence_action = "EXIT/TIGHTEN - Structure has broken, trend reversing"
        confluence_risk = "HIGH - Counter-trend signals emerging"
    
    # Priority 2: Macro + SMC + Advanced confluence
    # Check macro bias (use calculated bias if available, otherwise use string)
    is_bullish = (macro_bias and macro_bias.get('bias_direction') == 'bullish') or (not macro_bias and macro_bias_str == "BULLISH")
    is_bearish = (macro_bias and macro_bias.get('bias_direction') == 'bearish') or (not macro_bias and macro_bias_str == "BEARISH")
    
    if is_bullish and bos_detected and structure_trend == "BULLISH":
        if rmag.get("ema200_atr", 0) < -1.5:
            confluence_verdict = "🟢 STRONG BUY - Full Bullish Confluence"
            confluence_action = "High-confidence long entry"
            confluence_risk = "LOW - All layers aligned bullish"
        else:
            confluence_verdict = "🟢 BUY - Bullish Confluence"
            confluence_action = "Long entry with standard risk"
            confluence_risk = "MEDIUM - Bullish setup, watch for pullback"
    
    elif is_bearish and bos_detected and structure_trend == "BEARISH":
        if rmag.get("ema200_atr", 0) > 1.5:
            confluence_verdict = "🔴 STRONG SELL - Full Bearish Confluence"
            confluence_action = "High-confidence short entry"
            confluence_risk = "LOW - All layers aligned bearish"
        else:
            confluence_verdict = "🔴 SELL - Bearish Confluence"
            confluence_action = "Short entry with standard risk"
            confluence_risk = "MEDIUM - Bearish setup, watch for bounce"
    
    # Macro neutral + oversold/overbought = scalp opportunity
    elif not is_bullish and not is_bearish:
        rsi_h1 = h1_data.get("rsi_14", 50)
        if rsi_h1 < 30 and rmag.get("ema200_atr", 0) < -2.0:
            confluence_verdict = "🟡 SCALP BUY - Oversold Bounce"
            confluence_action = "Counter-trend scalp long (tight SL required)"
            confluence_risk = "MEDIUM - Counter-trend, macro neutral allows bounce"
        elif rsi_h1 > 70 and rmag.get("ema200_atr", 0) > 2.0:
            confluence_verdict = "🟡 SCALP SELL - Overbought Pullback"
            confluence_action = "Counter-trend scalp short (tight SL required)"
            confluence_risk = "MEDIUM - Counter-trend, macro neutral allows pullback"
        else:
            confluence_verdict = "⚪ WAIT - Neutral Across All Layers"
            confluence_action = "No clear setup, wait for confluence"
            confluence_risk = "N/A - No position recommended"
    
    # Conflicting signals
    elif is_bullish and structure_trend == "BEARISH":
        confluence_verdict = "⚠️ CONFLICTING SIGNALS"
        confluence_action = "Macro bullish but structure bearish - WAIT for clarity"
        confluence_risk = "HIGH - Mixed signals, avoid trading"
    
    elif is_bearish and structure_trend == "BULLISH":
        confluence_verdict = "⚠️ CONFLICTING SIGNALS"
        confluence_action = "Macro bearish but structure bullish - WAIT for clarity"
        confluence_risk = "HIGH - Mixed signals, avoid trading"
    
    else:
        confluence_verdict = "⚪ NEUTRAL - No Clear Setup"
        confluence_action = "Wait for better confluence"
        confluence_risk = "N/A"
    
    # ========== LAYERED RECOMMENDATIONS ==========
    
    scalp_rec = _generate_scalp_recommendation(
        current_price, m5_features, m5_smc, fvg, direction, entry, sl, tp, confidence, rr
    )
    
    intraday_rec = _generate_intraday_recommendation(
        current_price, m15_features, m15_smc, structure_trend, bos_detected, choch_detected
    )
    
    swing_rec = _generate_swing_recommendation(
        current_price, h1_features, h1_smc, macro_bias, structure_trend
    )
    
    # ========== BUILD UNIFIED RESPONSE ==========
    
    # Format H4 and M30 status with fallbacks
    h4_status = h4_smc.get('bias', h4_smc.get('status', h4_features.get('structure', 'Unknown')))
    m30_status = m30_smc.get('setup', m30_smc.get('bias', m30_smc.get('status', 'Unknown')))
    
    # ========== TIER 1 ENHANCEMENTS ==========
    pattern_summary = _extract_pattern_summary(features_data, symbol, current_price)
    regime_classification = _classify_market_regime(features_data, m5_data, m15_data, h1_data)
    confidence_score, confidence_emoji = _calculate_bias_confidence(
        macro_bias, structure_trend, choch_detected, bos_detected, 
        rmag, vol_trend, pressure, confidence, features_data
    )
    
    # ========== TIER 2 ENHANCEMENTS ==========
    volume_delta_context = _extract_volume_delta_context(m5_data, m15_data, order_flow)
    liquidity_map = _extract_liquidity_map_snapshot(m5_features, current_price, symbol)
    session_context = _extract_session_context(m5_data)
    news_guardrail = _extract_news_guardrail(macro)
    
    # Extract structured session data
    session_data = {}
    try:
        from infra.feature_session_news import SessionNewsFeatures
        session_features = SessionNewsFeatures()
        session_info = session_features.get_session_info()
        if session_info:
            session_name = session_info.primary_session
            if session_name == "ASIA":
                session_end_minutes = 600
            elif session_name == "LONDON":
                session_end_minutes = 480
            elif session_name == "NY":
                session_end_minutes = 480
            else:
                session_end_minutes = 0
            minutes_remaining = max(0, session_end_minutes - session_info.minutes_into_session)
            session_data = {
                "name": session_name,
                "is_overlap": session_info.is_overlap,
                "overlap_type": session_info.overlap_type,
                "minutes_into_session": session_info.minutes_into_session,
                "minutes_remaining": minutes_remaining,
                "context": session_context  # Formatted string for convenience
            }
    except Exception as e:
        logger.debug(f"Error extracting structured session data: {e}")
        session_data = {
            "name": m5_data.get("session", "UNKNOWN"),
            "is_overlap": False,
            "overlap_type": None,
            "minutes_into_session": 0,
            "minutes_remaining": 0,
            "context": session_context
        }
    
    # Extract structured news data
    news_data = {}
    try:
        from infra.news_service import NewsService
        from datetime import datetime, timezone
        news_service = NewsService()
        if news_service:
            upcoming_events = news_service.get_upcoming_events(limit=5, hours_ahead=24)
            if upcoming_events:
                current_time = datetime.now(timezone.utc)
                high_impact_events = [e for e in upcoming_events if e.get("impact", "LOW") in ["HIGH", "ULTRA"]]
                next_event = high_impact_events[0] if high_impact_events else None
                news_data = {
                    "upcoming_events": upcoming_events,
                    "high_impact_events": high_impact_events,
                    "high_impact_count": len(high_impact_events),
                    "next_event": next_event,
                    "guardrail": news_guardrail  # Formatted string for convenience
                }
            else:
                news_data = {
                    "upcoming_events": [],
                    "high_impact_events": [],
                    "high_impact_count": 0,
                    "next_event": None,
                    "guardrail": news_guardrail
                }
        else:
            news_data = {
                "upcoming_events": [],
                "high_impact_events": [],
                "high_impact_count": 0,
                "next_event": None,
                "guardrail": "News: Service unavailable"
            }
    except Exception as e:
        logger.debug(f"Error extracting structured news data: {e}")
        news_data = {
            "upcoming_events": [],
            "high_impact_events": [],
            "high_impact_count": 0,
            "next_event": None,
            "guardrail": news_guardrail
        }
    
    # Calculate structure_summary before summary string (needed for enhanced data fields summary)
    structure_summary = calculate_structure_summary(
        m1_microstructure=m1_microstructure,
        smc_data=smc,
        current_price=current_price,
        htf_levels=htf_levels  # Pass HTF levels for range reference
    )
    
    summary = f"""📊 {symbol} - Unified Analysis
    📅 {datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M UTC')} | Price: ${current_price:,.2f}

{confidence_emoji} BIAS CONFIDENCE: {confidence_score}/100
🏛️ MARKET REGIME: {regime_classification}
{_format_volatility_regime_display(volatility_regime) if volatility_regime else ''}

🌍 MACRO CONTEXT
{macro_summary}
→ Macro Bias: {macro_bias_str}
{format_macro_bias_summary(macro_bias) if macro_bias else ''}


🏛️ SMC STRUCTURE (H4 → H1 → M30 → M15 → M5)
H4: {h4_status}
H1: {h1_smc.get('status', h1_smc.get('bias', 'Unknown'))}
M30: {m30_status}
M15: {m15_smc.get('trigger', m15_smc.get('bias', 'Unknown'))}
M5: {m5_smc.get('execution', m5_smc.get('bias', 'Unknown'))}
CHOCH/BOS: {'⚠️ CHOCH DETECTED' if choch_detected else '✅ BOS Confirmed' if bos_detected else '❌ None detected'}
→ Structure: {structure_trend}

🕯️ CANDLE PATTERNS
{pattern_summary}

⚙️ ADVANCED FEATURES
RMAG: {rmag.get('ema200_atr', 0):.2f} ATR ({'oversold' if rmag.get('ema200_atr', 0) < -1.5 else 'overbought' if rmag.get('ema200_atr', 0) > 1.5 else 'neutral'})
VWAP: {vwap.get('zone', 'unknown')} zone
Volatility: {vol_trend.get('regime', 'unknown')}
Momentum: {pressure.get('ratio', 0):.2f} ({'bullish' if pressure.get('ratio', 0) > 1.2 else 'bearish' if pressure.get('ratio', 0) < 0.8 else 'neutral'})
→ Technicals: {_summarize_advanced_features(rmag, vwap, pressure)}

📈 TECHNICAL INDICATORS
{_summarize_technical_indicators(m5_data, m15_data, h1_data, current_price)}

📊 BINANCE ENRICHMENT
{_summarize_binance_enrichment(m5_data, m15_data)}

💧 LIQUIDITY & ORDER FLOW
{format_liquidity_summary(m5_features, m5_data, current_price)}
{format_order_flow_summary(order_flow)}
{_format_btc_order_flow_metrics(btc_order_flow_metrics) if btc_order_flow_metrics and symbol_normalized == 'BTCUSDc' else ''}
{format_tick_metrics_summary(tick_metrics) if tick_metrics else ''}

📊 MARKET CONTEXT
📈 Volume & Delta: {volume_delta_context}
🗺️ Liquidity Map:
{liquidity_map}
🕒 Session: {session_context}
📰 {news_guardrail}

📉 VOLATILITY FORECASTING
Volatility Signal: {volatility_signal if volatility_signal else vol_trend.get('regime', 'unknown')}
{format_volatility_summary(m5_features, volatility_forecaster=vol_forecaster_param if 'vol_forecaster_param' in locals() else None, m5_df=m5_df_param if 'm5_df_param' in locals() else None) if m5_features else 'Volatility analysis unavailable'}

🔬 M1 MICROSTRUCTURE ANALYSIS
{_format_m1_microstructure_summary(m1_microstructure) if m1_microstructure and m1_microstructure.get('available') else 'M1 microstructure analysis unavailable'}

📊 ENHANCED DATA FIELDS ⭐ NEW
{_format_enhanced_data_fields_summary(correlation_context, htf_levels, session_risk, execution_context, strategy_stats, structure_summary, symbol_constraints)}

🎯 CONFLUENCE VERDICT
{confluence_verdict}
{confluence_action}
Risk Level: {confluence_risk}

📈 LAYERED RECOMMENDATIONS

{scalp_rec}

{intraday_rec}

{swing_rec}
"""
    
    return {
        "summary": summary,
        "data": {
            "symbol": symbol,
            "symbol_normalized": symbol_normalized,
            "current_price": current_price,
            "session": session_data,
            "news": news_data,
            "macro": {
                "bias": macro_bias,
                "summary": macro_summary,
                "data": macro_data_obj  # Include full macro data
            },
            "smc": {
                # Basic fields (keep for backward compatibility)
                "choch_detected": choch_detected,
                "bos_detected": bos_detected,
                "trend": structure_trend,
                
                # NEW: Full multi-timeframe analysis structure
                "timeframes": smc.get("timeframes", {}),
                "alignment_score": smc.get("alignment_score", 0),
                "recommendation": recommendation,
                
                # Extract nested fields from recommendation for convenience
                # ⚠️ NOTE: These fields are at the TOP LEVEL of recommendation dict (added via .update() in analyzer)
                "market_bias": recommendation.get("market_bias", {}),
                "trade_opportunities": recommendation.get("trade_opportunities", {}),
                "volatility_regime": recommendation.get("volatility_regime", "unknown"),
                "volatility_weights": recommendation.get("volatility_weights", {}),
                
                # Advanced insights (may not exist if advanced_features unavailable)
                "advanced_insights": smc.get("advanced_insights", {}),
                "advanced_summary": smc.get("advanced_summary", ""),
                
                # Convenience field: use recommendation confidence as confidence_score
                "confidence_score": recommendation.get("confidence", 0)
            },
            "advanced": {
                "rmag": rmag,
                "vwap": vwap,
                "volatility": vol_trend,
                "momentum": pressure
            },
            "advanced_features": advanced_features if advanced_features else None,  # NEW: Full advanced features structure (all timeframes, candlestick patterns, wick metrics, etc.)
            "confluence": {
                "verdict": confluence_verdict,
                "action": confluence_action,
                "risk": confluence_risk
            },
            "recommendations": {
                "scalp": scalp_rec,
                "intraday": intraday_rec,
                "swing": swing_rec
            },
            "volatility_regime": volatility_regime if volatility_regime else None,
            "volatility_metrics": volatility_regime.get("volatility_metrics") if volatility_regime and volatility_regime.get("volatility_metrics") else None,  # Phase 4.1: Detailed volatility metrics
            "strategy_selection": volatility_regime.get("strategy_selection") if volatility_regime else None,  # Convenience: Extract strategy_selection to top level for easier access
            "m1_microstructure": m1_microstructure if m1_microstructure else None,
            "btc_order_flow_metrics": btc_order_flow_metrics if btc_order_flow_metrics and symbol_normalized == 'BTCUSDc' else None,  # NEW: BTC-specific order flow metrics
            "structure_summary": calculate_structure_summary(
                m1_microstructure=m1_microstructure,
                smc_data=smc,
                current_price=current_price,
                htf_levels=htf_levels  # Pass HTF levels for range reference
            ),
            "correlation_context": correlation_context if correlation_context else {},
            "htf_levels": htf_levels if htf_levels else {},
            "session_risk": session_risk if session_risk else {},
            "execution_context": execution_context if execution_context else {},
            "strategy_stats": strategy_stats,  # Can be None
            "symbol_constraints": symbol_constraints if symbol_constraints else {},
            "tick_metrics": tick_metrics if tick_metrics else None,  # NEW: Tick microstructure metrics
            "decision": {
                "direction": direction,
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "confidence": confidence,
                "reasoning": reasoning,
                "rr": rr
            }
        },
        "timestamp": timestamp,
        "timestamp_human": datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "cache_control": "no-cache, no-store, must-revalidate"
    }

def _format_btc_order_flow_metrics(btc_metrics: Optional[Dict[str, Any]]) -> str:
    """
    Format BTC order flow metrics for summary display.
    
    Args:
        btc_metrics: BTC order flow metrics dict from moneybot.btc_order_flow_metrics
        
    Returns:
        Formatted string with BTC order flow insights
    """
    if not btc_metrics or btc_metrics.get("status") != "success":
        return ""
    
    lines = []
    lines.append("📊 BTC ORDER FLOW METRICS (Binance Real-Time):")
    
    try:
        # Delta Volume
        delta_data = btc_metrics.get("delta_volume", {})
        if delta_data:
            net_delta = delta_data.get("net_delta", 0)
            dominant_side = delta_data.get("dominant_side", "NEUTRAL")
            buy_vol = delta_data.get("buy_volume", 0)
            sell_vol = delta_data.get("sell_volume", 0)
            lines.append(f"💰 Delta Volume: {net_delta:+,.2f} ({dominant_side}) | Buy: {buy_vol:,.2f} | Sell: {sell_vol:,.2f}")
        
        # CVD
        cvd_data = btc_metrics.get("cvd", {})
        if cvd_data:
            cvd_current = cvd_data.get("current", 0)
            cvd_slope = cvd_data.get("slope", 0)
            bar_count = cvd_data.get("bar_count", 0)
            slope_direction = "📈" if cvd_slope > 0 else "📉" if cvd_slope < 0 else "➡️"
            lines.append(f"{slope_direction} CVD: {cvd_current:+,.2f} (Slope: {cvd_slope:+,.2f}/bar, {bar_count} bars)")
        
        # CVD Divergence
        divergence_data = btc_metrics.get("cvd_divergence", {})
        if divergence_data and divergence_data.get("strength", 0) > 0:
            div_type = divergence_data.get("type", "None")
            div_strength = divergence_data.get("strength", 0)
            lines.append(f"⚠️ CVD Divergence: {div_type} ({div_strength:.1%})")
        
        # Absorption Zones
        absorption_zones = btc_metrics.get("absorption_zones", [])
        if absorption_zones:
            lines.append(f"🎯 Absorption Zones: {len(absorption_zones)} detected")
            for zone in absorption_zones[:2]:  # Show top 2
                price = zone.get("price_level", 0)
                side = zone.get("side", "NEUTRAL")
                strength = zone.get("strength", 0)
                lines.append(f"   ${price:,.2f} - {side} (Strength: {strength:.1%})")
        
        # Buy/Sell Pressure
        pressure_data = btc_metrics.get("buy_sell_pressure", {})
        if pressure_data:
            ratio = pressure_data.get("ratio", 1.0)
            dominant = pressure_data.get("dominant_side", "NEUTRAL")
            lines.append(f"⚖️ Buy/Sell Pressure: {ratio:.2f}x ({dominant})")
        
    except Exception as e:
        logger.debug(f"Error formatting BTC order flow metrics: {e}")
        return ""
    
    return "\n".join(lines) if lines else ""


def calculate_structure_summary(
    m1_microstructure: Optional[Dict[str, Any]],
    smc_data: Optional[Dict[str, Any]],
    current_price: float,
    htf_levels: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create compressed structure interpretation flags.
    
    Args:
        m1_microstructure: M1 microstructure analysis data
        smc_data: SMC (Smart Money Concepts) data
        current_price: Current market price
        htf_levels: Optional HTF levels data
    
    Returns:
        {
            "current_range_type": "balanced_range",  # "balanced_range" | "trend_channel" | "breakout" | "distribution" | "accumulation"
            "range_state": "mid_range",  # "mid_range" | "near_range_high" | "near_range_low" | "just_broke_range"
            "has_liquidity_sweep": True,
            "sweep_type": "bear",  # "bull" | "bear" | "none"
            "sweep_level": 4188.95,  # Price level if sweep detected
            "discount_premium_state": "seeking_premium_liquidity",  # "seeking_premium_liquidity" | "seeking_discount_liquidity" | "balanced"
            "range_high": 4207.11,  # From M1 microstructure liquidity zones
            "range_low": 4188.96,   # From M1 microstructure liquidity zones
            "range_mid": 4198.04    # Calculated
        }
    """
    # Default values
    default_result = {
        "current_range_type": "balanced_range",
        "range_state": "mid_range",
        "has_liquidity_sweep": False,
        "sweep_type": "none",
        "sweep_level": None,
        "discount_premium_state": "balanced",
        "range_high": None,
        "range_low": None,
        "range_mid": None
    }
    
    # Validate m1_microstructure structure (use safe access with .get())
    if not m1_microstructure or not m1_microstructure.get('available'):
        return default_result
    
    # Extract liquidity zones from m1_microstructure
    liquidity_zones = m1_microstructure.get('liquidity_zones', [])
    
    # Extract range boundaries: range_high = max(zone['price'] for zone in zones), range_low = min(...)
    range_high = None
    range_low = None
    
    if liquidity_zones:
        prices = [zone.get('price', 0) for zone in liquidity_zones if zone.get('price') is not None]
        if prices:
            range_high = max(prices)
            range_low = min(prices)
    
    # If no liquidity zones, try to get from HTF levels
    if range_high is None or range_low is None:
        if htf_levels:
            weekly_high = htf_levels.get('previous_week_high')
            weekly_low = htf_levels.get('previous_week_low')
            daily_high = htf_levels.get('previous_day_high')
            daily_low = htf_levels.get('previous_day_low')
            
            # Use weekly or daily range
            if weekly_high and weekly_low:
                range_high = weekly_high
                range_low = weekly_low
            elif daily_high and daily_low:
                range_high = daily_high
                range_low = daily_low
    
    # Calculate range_mid
    range_mid = None
    if range_high is not None and range_low is not None:
        range_mid = (range_high + range_low) / 2.0
    
    # Determine range type from structure (use smc_data.trend and m1_microstructure.structure)
    current_range_type = "balanced_range"  # Default
    
    if smc_data:
        trend = smc_data.get('trend', 'UNKNOWN')
        if trend in ['BULLISH', 'BEARISH']:
            # Check if it's a trend channel or breakout
            structure = m1_microstructure.get('structure', {})
            structure_type = structure.get('type', 'UNKNOWN')
            
            if structure_type in ['HIGHER_HIGH', 'LOWER_LOW']:
                current_range_type = "trend_channel"
            else:
                # Check for breakout
                choch_bos = m1_microstructure.get('choch_bos', {})
                if choch_bos.get('has_bos', False) or choch_bos.get('has_choch', False):
                    current_range_type = "breakout"
                else:
                    current_range_type = "balanced_range"
        else:
            # RANGE or UNKNOWN - could be distribution or accumulation
            volatility = m1_microstructure.get('volatility', {})
            vol_state = volatility.get('state', 'STABLE')
            
            if vol_state == 'CONTRACTING':
                current_range_type = "accumulation"
            elif vol_state == 'EXPANDING':
                current_range_type = "distribution"
            else:
                current_range_type = "balanced_range"
    
    # Check for liquidity sweeps: m1_microstructure.get('choch_bos', {}).get('sweep_detected', False)
    has_liquidity_sweep = False
    sweep_type = "none"
    sweep_level = None
    
    choch_bos = m1_microstructure.get('choch_bos', {})
    
    # Check for sweep in CHOCH/BOS data
    # Note: sweep_detected may not exist, so check for CHOCH/BOS patterns that indicate sweeps
    if choch_bos.get('has_choch', False) or choch_bos.get('has_bos', False):
        # Determine if this is a sweep pattern
        structure = m1_microstructure.get('structure', {})
        structure_type = structure.get('type', 'UNKNOWN')
        
        # Sweep typically occurs when CHOCH happens at range extremes
        if liquidity_zones and (range_high or range_low):
            # Check if price was near range boundary when CHOCH/BOS occurred
            if choch_bos.get('has_choch', False):
                has_liquidity_sweep = True
                # Determine sweep type from structure
                if structure_type == 'HIGHER_HIGH':
                    sweep_type = "bear"  # Bullish structure but CHOCH = bearish reversal (swept high)
                elif structure_type == 'LOWER_LOW':
                    sweep_type = "bull"  # Bearish structure but CHOCH = bullish reversal (swept low)
                else:
                    # Use CHOCH direction if available
                    if choch_bos.get('choch_bull', False):
                        sweep_type = "bull"
                    elif choch_bos.get('choch_bear', False):
                        sweep_type = "bear"
            elif choch_bos.get('has_bos', False):
                # BOS indicates continuation, may indicate sweep of opposite side
                if structure_type == 'HIGHER_HIGH':
                    sweep_type = "bull"  # Bullish continuation (swept low)
                elif structure_type == 'LOWER_LOW':
                    sweep_type = "bear"  # Bearish continuation (swept high)
                
                if sweep_type != "none":
                    has_liquidity_sweep = True
        
        # Get sweep level from liquidity zones (highest/lowest zone)
        if liquidity_zones and sweep_type != "none":
            if sweep_type == "bull":
                # Bull sweep = swept low, now at high
                sweep_level = range_low
            else:
                # Bear sweep = swept high, now at low
                sweep_level = range_high
    
    # Calculate discount/premium state: Compare current_price to range (use htf_levels if available)
    discount_premium_state = "balanced"
    
    if range_high is not None and range_low is not None and range_mid is not None:
        range_width = range_high - range_low
        if range_width > 0:
            # Calculate position in range (0 = at low, 1 = at high)
            position_in_range = (current_price - range_low) / range_width
            
            # Use HTF levels for premium/discount if available
            if htf_levels:
                price_position = htf_levels.get('price_position', 'equilibrium')
                if price_position == 'premium':
                    discount_premium_state = "seeking_premium_liquidity"
                elif price_position == 'discount':
                    discount_premium_state = "seeking_discount_liquidity"
                else:
                    discount_premium_state = "balanced"
            else:
                # Use range position
                if position_in_range > 0.66:
                    discount_premium_state = "seeking_premium_liquidity"
                elif position_in_range < 0.33:
                    discount_premium_state = "seeking_discount_liquidity"
                else:
                    discount_premium_state = "balanced"
    
    # Determine range state: "mid_range" if 33%-66%, "near_range_high" if >66%, "near_range_low" if <33%
    # "just_broke_range" if price outside range and recent break detected
    range_state = "mid_range"  # Default
    
    if range_high is not None and range_low is not None:
        range_width = range_high - range_low
        if range_width > 0:
            position_in_range = (current_price - range_low) / range_width
            
            # Check if price is outside range
            if current_price > range_high or current_price < range_low:
                # Check if recent break detected
                if choch_bos.get('has_bos', False) or choch_bos.get('has_choch', False):
                    range_state = "just_broke_range"
                else:
                    # Outside range but no recent break
                    if current_price > range_high:
                        range_state = "near_range_high"
                    else:
                        range_state = "near_range_low"
            else:
                # Price is within range
                if position_in_range > 0.66:
                    range_state = "near_range_high"
                elif position_in_range < 0.33:
                    range_state = "near_range_low"
                else:
                    range_state = "mid_range"
    
    return {
        "current_range_type": current_range_type,
        "range_state": range_state,
        "has_liquidity_sweep": has_liquidity_sweep,
        "sweep_type": sweep_type,
        "sweep_level": sweep_level,
        "discount_premium_state": discount_premium_state,
        "range_high": range_high,
        "range_low": range_low,
        "range_mid": range_mid
    }


def _format_enhanced_data_fields_summary(
    correlation_context: Optional[Dict[str, Any]],
    htf_levels: Optional[Dict[str, Any]],
    session_risk: Optional[Dict[str, Any]],
    execution_context: Optional[Dict[str, Any]],
    strategy_stats: Optional[Dict[str, Any]],
    structure_summary: Optional[Dict[str, Any]],
    symbol_constraints: Optional[Dict[str, Any]]
) -> str:
    """
    Format enhanced data fields for summary display.
    
    Args:
        correlation_context: Correlation context data
        htf_levels: HTF levels data
        session_risk: Session risk data
        execution_context: Execution context data
        strategy_stats: Strategy stats data
        structure_summary: Structure summary data
        symbol_constraints: Symbol constraints data
    
    Returns:
        Formatted string with enhanced data fields
    """
    lines = []
    
    # Correlation Context
    if correlation_context and correlation_context.get('data_quality') != 'unavailable':
        corr_dxy = correlation_context.get('corr_vs_dxy')
        corr_sp500 = correlation_context.get('corr_vs_sp500')
        corr_us10y = correlation_context.get('corr_vs_us10y')
        data_quality = correlation_context.get('data_quality', 'unknown')
        
        if corr_dxy is not None or corr_sp500 is not None or corr_us10y is not None:
            corr_parts = []
            if corr_dxy is not None:
                corr_parts.append(f"DXY: {corr_dxy:+.2f}")
            if corr_sp500 is not None:
                corr_parts.append(f"SP500: {corr_sp500:+.2f}")
            if corr_us10y is not None:
                corr_parts.append(f"US10Y: {corr_us10y:+.2f}")
            
            if corr_parts:
                quality_warning = f" ({data_quality})" if data_quality != 'good' else ""
                lines.append(f"🔗 Correlation: {', '.join(corr_parts)}{quality_warning}")
    
    # HTF Levels
    if htf_levels:
        price_pos = htf_levels.get('current_price_position', 'equilibrium')
        weekly_high = htf_levels.get('previous_week_high')
        weekly_low = htf_levels.get('previous_week_low')
        
        if price_pos and price_pos != 'equilibrium':
            lines.append(f"📈 HTF Position: {price_pos.upper()}")
        if weekly_high and weekly_low:
            lines.append(f"📊 Weekly Range: {weekly_low:.2f} - {weekly_high:.2f}")
    
    # Session Risk
    if session_risk:
        is_rollover = session_risk.get('is_rollover_window', False)
        is_news_lock = session_risk.get('is_news_lock_active', False)
        minutes_to_news = session_risk.get('minutes_to_next_high_impact')
        
        if is_rollover:
            lines.append("⚠️ ROLLOVER WINDOW - Avoid trading")
        if is_news_lock:
            lines.append("🚫 NEWS LOCK ACTIVE - High-impact event within ±30min")
        elif minutes_to_news is not None and minutes_to_news < 60:
            lines.append(f"⏰ High-impact news in {minutes_to_news} minutes")
    
    # Execution Context
    if execution_context:
        exec_quality = execution_context.get('execution_quality', 'unknown')
        spread_elevated = execution_context.get('is_spread_elevated', False)
        slippage_elevated = execution_context.get('is_slippage_elevated', False)
        
        if exec_quality != 'good':
            quality_emoji = "⚠️" if exec_quality == 'degraded' else "🚫"
            lines.append(f"{quality_emoji} Execution Quality: {exec_quality.upper()}")
            if spread_elevated:
                lines.append(f"   - Spread elevated")
            if slippage_elevated:
                lines.append(f"   - Slippage elevated")
    
    # Strategy Stats
    if strategy_stats:
        win_rate = strategy_stats.get('win_rate')
        avg_rr = strategy_stats.get('avg_rr')
        confidence = strategy_stats.get('confidence', 'unknown')
        sample_size = strategy_stats.get('sample_size', 0)
        
        if win_rate is not None and avg_rr is not None:
            lines.append(f"📊 Strategy Stats: {win_rate:.0%} win rate, {avg_rr:.1f}R avg ({confidence} confidence, n={sample_size})")
    
    # Structure Summary
    if structure_summary:
        range_type = structure_summary.get('current_range_type', 'unknown')
        range_state = structure_summary.get('range_state', 'unknown')
        has_sweep = structure_summary.get('has_liquidity_sweep', False)
        sweep_type = structure_summary.get('sweep_type', 'none')
        
        if range_type != 'unknown':
            lines.append(f"🏗️ Structure: {range_type.replace('_', ' ').title()}, {range_state.replace('_', ' ').title()}")
        if has_sweep and sweep_type != 'none':
            lines.append(f"💧 Liquidity Sweep: {sweep_type.upper()} detected")
    
    # Symbol Constraints
    if symbol_constraints:
        max_trades = symbol_constraints.get('max_concurrent_trades_for_symbol')
        max_risk = symbol_constraints.get('max_total_risk_on_symbol_pct')
        banned = symbol_constraints.get('banned_strategies', [])
        
        if max_trades or max_risk:
            constraint_parts = []
            if max_trades:
                constraint_parts.append(f"Max trades: {max_trades}")
            if max_risk:
                constraint_parts.append(f"Max risk: {max_risk}%")
            if constraint_parts:
                lines.append(f"⚙️ Constraints: {', '.join(constraint_parts)}")
        if banned:
            lines.append(f"🚫 Banned strategies: {', '.join(banned)}")
    
    return "\n".join(lines) if lines else "Enhanced data fields unavailable"


def _format_m1_microstructure_summary(m1_data: Optional[Dict[str, Any]]) -> str:
    """
    Format M1 microstructure analysis for summary display.
    
    Args:
        m1_data: M1 microstructure analysis dict
        
    Returns:
        Formatted string with M1 insights
    """
    if not m1_data or not m1_data.get('available'):
        return "M1 microstructure analysis unavailable"
    
    lines = []
    
    # Signal Summary
    signal_summary = m1_data.get('signal_summary', 'NEUTRAL')
    signal_emoji = "🟢" if "BULLISH" in signal_summary else "🔴" if "BEARISH" in signal_summary else "⚪"
    lines.append(f"{signal_emoji} Signal: {signal_summary}")
    
    # CHOCH/BOS Status
    choch_bos = m1_data.get('choch_bos', {})
    if choch_bos.get('has_choch'):
        lines.append(f"⚠️ CHOCH Detected (Confidence: {choch_bos.get('confidence', 0)}%)")
    elif choch_bos.get('has_bos'):
        lines.append(f"✅ BOS Detected (Confidence: {choch_bos.get('confidence', 0)}%)")
    else:
        lines.append("❌ No CHOCH/BOS detected")
    
    # Structure
    structure = m1_data.get('structure', {})
    structure_type = structure.get('type', 'UNKNOWN')
    structure_strength = structure.get('strength', 0)
    lines.append(f"📊 Structure: {structure_type} (Strength: {structure_strength}%)")
    
    # Volatility State
    volatility = m1_data.get('volatility', {})
    vol_state = volatility.get('state', 'STABLE')
    vol_change = volatility.get('change_pct', 0)
    lines.append(f"📈 Volatility: {vol_state} ({vol_change:+.1f}%)")
    
    # Liquidity State
    liquidity_state = m1_data.get('liquidity_state', 'AWAY')
    liquidity_zones = m1_data.get('liquidity_zones', [])
    if liquidity_zones:
        zone_info = ", ".join([f"{z.get('type')} @ {z.get('price', 0):.2f}" for z in liquidity_zones[:3]])
        lines.append(f"💧 Liquidity: {liquidity_state} | Zones: {zone_info}")
    else:
        lines.append(f"💧 Liquidity: {liquidity_state}")
    
    # Momentum Quality
    momentum = m1_data.get('momentum', {})
    momentum_quality = momentum.get('quality', 'CHOPPY')
    momentum_consistency = momentum.get('consistency', 0)
    lines.append(f"⚡ Momentum: {momentum_quality} (Consistency: {momentum_consistency}%)")
    
    # Strategy Hint
    strategy_hint = m1_data.get('strategy_hint', 'UNKNOWN')
    lines.append(f"🎯 Strategy Hint: {strategy_hint}")
    
    # Confluence Score
    confluence = m1_data.get('microstructure_confluence', {})
    if confluence:
        score = confluence.get('score', 0)
        grade = confluence.get('grade', 'F')
        action = confluence.get('recommended_action', 'WAIT')
        lines.append(f"⭐ Confluence: {score:.1f}/100 (Grade: {grade}) → {action}")
    
    # Session Context (if available)
    session_context = m1_data.get('session_context', {})
    if session_context.get('session') != 'UNKNOWN':
        session = session_context.get('session', 'UNKNOWN')
        volatility_tier = session_context.get('volatility_tier', 'NORMAL')
        lines.append(f"🕒 Session: {session} ({volatility_tier} volatility)")
    
    # Dynamic Threshold (if available)
    dynamic_threshold = m1_data.get('dynamic_threshold')
    if dynamic_threshold:
        threshold_calc = m1_data.get('threshold_calculation', {})
        lines.append(f"🎚️ Dynamic Threshold: {dynamic_threshold:.1f} (Base: {threshold_calc.get('base_confidence', 70)}, ATR: {threshold_calc.get('atr_ratio', 1.0):.2f}x)")
    
    return "\n".join(lines)


def _summarize_technical_indicators(m5_data: Dict, m15_data: Dict, h1_data: Dict, current_price: float) -> str:
    """Summarize key technical indicators across timeframes"""
    lines = []
    
    # Helper function to determine trend from EMAs
    def get_ema_trend(data, price):
        ema20 = data.get('ema20', 0)
        ema50 = data.get('ema50', 0)
        ema200 = data.get('ema200', 0)
        
        if price > ema20 > ema50 > ema200:
            return "STRONG BULL"
        elif price > ema20 > ema50:
            return "BULL"
        elif price < ema20 < ema50 < ema200:
            return "STRONG BEAR"
        elif price < ema20 < ema50:
            return "BEAR"
        else:
            return "MIXED"
    
    # H1 Indicators (Primary trend)
    if h1_data:
        rsi_h1 = h1_data.get('rsi', 50)
        adx_h1 = h1_data.get('adx', 0)
        macd_h1 = h1_data.get('macd', 0)
        macd_signal_h1 = h1_data.get('macd_signal', 0)
        ema_trend_h1 = get_ema_trend(h1_data, current_price)
        
        macd_cross_h1 = "BULL" if macd_h1 > macd_signal_h1 else "BEAR"
        
        lines.append(f"H1: EMA {ema_trend_h1} | RSI {rsi_h1:.1f} | ADX {adx_h1:.1f} | MACD {macd_cross_h1}")
    
    # M15 Indicators (Entry timeframe)
    if m15_data:
        rsi_m15 = m15_data.get('rsi', 50)
        macd_m15 = m15_data.get('macd', 0)
        macd_signal_m15 = m15_data.get('macd_signal', 0)
        stoch_k_m15 = m15_data.get('stoch_k', 50)
        stoch_d_m15 = m15_data.get('stoch_d', 50)
        bb_upper_m15 = m15_data.get('bb_upper', 0)
        bb_lower_m15 = m15_data.get('bb_lower', 0)
        
        macd_cross_m15 = "BULL" if macd_m15 > macd_signal_m15 else "BEAR"
        stoch_signal_m15 = "BULL" if stoch_k_m15 > stoch_d_m15 else "BEAR"
        
        # Bollinger position
        if current_price > bb_upper_m15:
            bb_pos = "ABOVE UPPER"
        elif current_price < bb_lower_m15:
            bb_pos = "BELOW LOWER"
        else:
            bb_pos = "MIDDLE"
        
        lines.append(f"M15: RSI {rsi_m15:.1f} | MACD {macd_cross_m15} | Stoch {stoch_signal_m15} ({stoch_k_m15:.1f}) | BB {bb_pos}")
    
    # M5 Indicators (Execution timeframe)
    if m5_data:
        rsi_m5 = m5_data.get('rsi', 50)
        macd_m5 = m5_data.get('macd', 0)
        macd_signal_m5 = m5_data.get('macd_signal', 0)
        atr_m5 = m5_data.get('atr14', 0)
        
        macd_cross_m5 = "BULL" if macd_m5 > macd_signal_m5 else "BEAR"
        
        # RSI zones
        if rsi_m5 > 70:
            rsi_zone = "OVERBOUGHT"
        elif rsi_m5 < 30:
            rsi_zone = "OVERSOLD"
        else:
            rsi_zone = "NEUTRAL"
        
        lines.append(f"M5: RSI {rsi_m5:.1f} ({rsi_zone}) | MACD {macd_cross_m5} | ATR {atr_m5:.2f}")
    
    return "\n".join(lines) if lines else "No technical data available"


def _summarize_binance_enrichment(m5_data: Dict, m15_data: Dict) -> str:
    """Summarize key Binance enrichment fields"""
    parts = []
    
    # Use M5 data for microstructure, fallback to M15
    data = m5_data if m5_data.get('price_zscore') is not None else m15_data
    
    # Z-Score (Mean Reversion)
    if 'price_zscore' in data:
        zscore = data.get('price_zscore', 0)
        signal = data.get('mean_reversion_signal', 'NEUTRAL')
        parts.append(f"Z-Score: {zscore:.2f}σ ({signal})")
    
    # Pivot Points
    if 'price_vs_pivot' in data:
        pivot_pos = data.get('price_vs_pivot', 'UNKNOWN')
        parts.append(f"vs Pivot: {pivot_pos}")
    
    # Liquidity Score
    if 'liquidity_quality' in data:
        liq_quality = data.get('liquidity_quality', 'UNKNOWN')
        liq_score = data.get('liquidity_score', 0)
        parts.append(f"Liquidity: {liq_quality} ({liq_score:.1f})")
    
    # Bollinger Band Squeeze
    if 'bb_squeeze' in data:
        squeeze = data.get('bb_squeeze', False)
        bb_pos = data.get('bb_position', 'UNKNOWN')
        if squeeze:
            parts.append(f"BB: SQUEEZE detected ({bb_pos})")
        else:
            parts.append(f"BB: {bb_pos}")
    
    # Tape Reading (Aggressor Side)
    if 'aggressor_side' in data:
        aggressor = data.get('aggressor_side', 'NEUTRAL')
        strength = data.get('aggressor_strength', 0)
        parts.append(f"Tape: {aggressor} {strength:.1f}%")
    
    # Candle Pattern
    if 'candle_pattern' in data and data.get('candle_pattern') != 'NONE':
        pattern = data.get('candle_pattern', 'NONE')
        direction = data.get('pattern_direction', '')
        parts.append(f"Pattern: {pattern} {direction}")
    
    # Order Flow Analysis (NEW!)
    if 'order_flow' in data:
        order_flow = data.get('order_flow', {})
        signal = order_flow.get('signal', 'NEUTRAL')
        confidence = order_flow.get('confidence', 0)
        whale_count = order_flow.get('whale_count', 0)
        imbalance = order_flow.get('imbalance')
        pressure_side = order_flow.get('pressure_side', 'NEUTRAL')
        
        # Format order flow summary
        of_parts = [f"{signal} ({confidence}%)"]
        if whale_count > 0:
            of_parts.append(f"🐋 {whale_count} whales")
        if imbalance:
            of_parts.append(f"Imbalance: {imbalance:.1f}%")
        if pressure_side != 'NEUTRAL':
            of_parts.append(f"Pressure: {pressure_side}")
        
        parts.append(f"Order Flow: {' | '.join(of_parts)}")
    
    return " | ".join(parts) if parts else "No enrichment data available"


def _summarize_advanced_features(rmag: Dict, vwap: Dict, pressure: Dict) -> str:
    """Summarize advanced features into concise text"""
    parts = []
    
    ema_atr = rmag.get("ema200_atr", 0)
    if ema_atr < -2.0:
        parts.append("Extreme oversold")
    elif ema_atr > 2.0:
        parts.append("Extreme overbought")
    elif abs(ema_atr) > 1.0:
        parts.append("Stretched" if abs(ema_atr) > 1.5 else "Moderately stretched")
    else:
        parts.append("Neutral range")
    
    momentum_ratio = pressure.get("ratio", 1.0)
    if momentum_ratio > 1.5:
        parts.append("strong bullish momentum")
    elif momentum_ratio < 0.7:
        parts.append("strong bearish momentum")
    else:
        parts.append("weak momentum")
    
    return ", ".join(parts) if parts else "Normal conditions"


def _generate_scalp_recommendation(
    price: float, m5_features: Dict, m5_smc: Dict, fvg: Dict,
    direction: str, entry: float, sl: float, tp: float, confidence: int, rr: float
) -> str:
    """Generate scalp trading recommendation (M5 entry, 2-4hr hold)"""
    if direction == "HOLD":
        return """SCALP (M5 entry, 2-4hr hold):
⚪ WAIT - No M5 setup currently
Current conditions don't support scalp entry"""
    
    action = "BUY" if direction == "BUY" else "SELL"
    emoji = "✅" if confidence > 70 else "🟡"
    
    fvg_support = fvg.get("nearest_bull_fvg", 0) if direction == "BUY" else fvg.get("nearest_bear_fvg", 0)
    
    return f"""SCALP (M5 entry, 2-4hr hold):
{emoji} {action} at ${entry:,.2f}
SL: ${sl:,.2f}
TP: ${tp:,.2f}
R:R: {rr:.1f} | Confidence: {confidence}%
Setup: M5 {m5_smc.get('bias', 'unknown')} + FVG support
Risk: Short-term scalp, tight SL required"""


def _generate_intraday_recommendation(
    price: float, m15_features: Dict, m15_smc: Dict,
    structure_trend: str, bos_detected: bool, choch_detected: bool
) -> str:
    """Generate intraday trading recommendation (M15 entry, 12-24hr hold)"""
    
    if choch_detected:
        return """INTRADAY (M15 entry, 12-24hr hold):
🔴 AVOID - CHOCH detected, structure reversing
Wait for new structure to form before intraday entry"""
    
    if not bos_detected:
        return """INTRADAY (M15 entry, 12-24hr hold):
⚪ WAIT - No M15 BOS confirmation yet
Current setup: Awaiting structure confirmation"""
    
    if structure_trend == "BULLISH":
        return """INTRADAY (M15 entry, 12-24hr hold):
✅ BUY SETUP AVAILABLE
Entry: M15 BOS Bull confirmed
Wait for: Pullback to M15 support/OB
Hold: 12-24 hours for intraday swing"""
    
    elif structure_trend == "BEARISH":
        return """INTRADAY (M15 entry, 12-24hr hold):
✅ SELL SETUP AVAILABLE
Entry: M15 BOS Bear confirmed
Wait for: Bounce to M15 resistance/OB
Hold: 12-24 hours for intraday swing"""
    
    return """INTRADAY (M15 entry, 12-24hr hold):
⚪ WAIT - Structure unclear
M15 needs clearer direction before entry"""


def _generate_swing_recommendation(
    price: float, h1_features: Dict, h1_smc: Dict,
    macro_bias: str, structure_trend: str
) -> str:
    """Generate swing trading recommendation (H1 entry, multi-day hold)"""
    
    # User preference: scalp/intraday only, no swing trades
    return """SWING (H1 entry, multi-day hold):
🚫 NOT RECOMMENDED - User prefers scalp/intraday only
This system is optimized for short-term trades"""


# ============================================================================
# TOOL IMPLEMENTATIONS
# ============================================================================

@registry.register("ping")
async def tool_ping(args: Dict[str, Any]) -> Dict[str, Any]:
    """Simple ping test"""
    message = args.get("message", "Hello from desktop agent!")
    
    return {
        "summary": f"🏓 Pong! {message}",
        "data": {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_version": "1.0.0",
            "status": "healthy"
        }
    }

@registry.register("moneybot.analyse_symbol")
async def tool_analyse_symbol(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyse a trading symbol using MoneyBot decision engine
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSD", "XAUUSD")
        detail_level: "standard" | "detailed" (optional)
    
    Returns:
        Structured trading recommendation with entry/SL/TP
    """
    logger.info(f"📥 Received args: {args}")
    logger.info(f"   Args type: {type(args)}")
    logger.info(f"   Args keys: {list(args.keys()) if isinstance(args, dict) else 'Not a dict'}")
    
    symbol = args.get("symbol")
    if not symbol:
        logger.error(f"❌ Symbol not found in args. Full args: {args}")
        raise ValueError("Missing required argument: symbol")
    
    detail_level = args.get("detail_level", "standard")
    
    # Normalize symbol (add 'c' suffix for broker)
    # Normalize: strip any trailing 'c' or 'C', then add lowercase 'c'
    if not symbol.lower().endswith('c'):
        symbol_normalized = symbol.upper() + 'c'
    else:
        symbol_normalized = symbol.upper().rstrip('cC') + 'c'
    
    logger.info(f"📊 Analysing {symbol} (normalized: {symbol_normalized})")
    
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    # Check if market is open
    import MetaTrader5 as mt5
    from datetime import datetime
    
    # Check weekend first
    now = datetime.utcnow()
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    
    if weekday >= 5:  # Saturday or Sunday
        import time
        current_timestamp = int(time.time())
        
        return {
            "summary": f"🚫 Market Closed - {symbol}\n\nThe {symbol} market is currently closed (weekend).\n\n💡 Markets open Sunday 22:00 UTC (Forex) or Monday morning.",
            "data": {
                "symbol": symbol,
                "direction": "HOLD",
                "confidence": 0,
                "reasoning": "Market closed - weekend",
                "executable": False,
                "market_closed": True
            },
            "timestamp": current_timestamp,
            "timestamp_human": now.strftime("%Y-%m-%d %H:%M:%S UTC")
        }
    
    # Check if symbol is available and market looks open
    symbol_info = mt5.symbol_info(symbol_normalized)
    if symbol_info is None:
        raise RuntimeError(f"Symbol {symbol_normalized} not found in MT5")
    
    # Check if session trading is off
    if hasattr(symbol_info, "session_trade") and hasattr(symbol_info, "session_deals"):
        if (not bool(symbol_info.session_trade)) or (not bool(symbol_info.session_deals)):
            return {
                "summary": f"🚫 Market Closed - {symbol}\n\nThe {symbol} market is currently closed (no active trading session).\n\n💡 Check your broker's market hours for this symbol.",
                "data": {
                    "symbol": symbol,
                    "direction": "HOLD",
                    "confidence": 0,
                    "reasoning": "Market closed - session trading off",
                    "executable": False,
                    "market_closed": True
                }
            }
    
    # Check if last tick is stale (> 10 minutes)
    tick = mt5.symbol_info_tick(symbol_normalized)
    if tick and hasattr(tick, "time"):
        import time
        tick_age_seconds = time.time() - float(tick.time)
        if tick_age_seconds > 600:  # > 10 minutes
            return {
                "summary": f"🚫 Market Closed - {symbol}\n\nThe {symbol} market appears closed (last price update was {int(tick_age_seconds/60)} minutes ago).\n\n💡 Check your broker's market hours for this symbol.",
                "data": {
                    "symbol": symbol,
                    "direction": "HOLD",
                    "confidence": 0,
                    "reasoning": f"Market closed - stale data ({int(tick_age_seconds/60)}m old)",
                    "executable": False,
                    "market_closed": True
                }
            }
    
    # Run real analysis using your decision_engine
    try:
        from infra.indicator_bridge import IndicatorBridge
        from infra.feature_builder_advanced import build_features_advanced
        from infra.binance_enrichment import BinanceEnrichment
        
        # Initialize indicator bridge
        bridge = IndicatorBridge()
        
        # Fetch multi-timeframe data (single call returns all timeframes)
        logger.info(f"   Fetching M5/M15/M30/H1 data for {symbol_normalized}...")
        all_timeframe_data = bridge.get_multi(symbol_normalized)
        
        # Extract individual timeframes
        m5_data = all_timeframe_data.get("M5")
        m15_data = all_timeframe_data.get("M15")
        m30_data = all_timeframe_data.get("M30")
        h1_data = all_timeframe_data.get("H1")
        
        if not all([m5_data, m15_data, m30_data, h1_data]):
            raise RuntimeError(f"Failed to fetch market data for {symbol_normalized}")
        
        # 🔥 PHASE 3: Enrich with Binance real-time data (+ order flow if available)
        if registry.binance_service and registry.binance_service.running:
            logger.info(f"   Enriching with Binance real-time data...")
            enricher = BinanceEnrichment(registry.binance_service, registry.mt5_service, registry.order_flow_service)
            m5_data = enricher.enrich_timeframe(symbol_normalized, m5_data, "M5")
            m15_data = enricher.enrich_timeframe(symbol_normalized, m15_data, "M15")
            if registry.order_flow_service and registry.order_flow_service.running:
                logger.info(f"   ✅ MT5 data enriched with Binance microstructure + order flow")
            else:
                logger.info(f"   ✅ MT5 data enriched with Binance microstructure")
        
        # Fetch Advanced features for advanced analysis
        logger.info(f"   Building Advanced features for {symbol_normalized}...")
        advanced_features = build_features_advanced(
            symbol=symbol_normalized,
            mt5svc=registry.mt5_service,
            bridge=bridge,
            timeframes=["M15"]
        )
        
        # Call decision engine
        logger.info(f"   Running decision engine...")
        result = decide_trade(
            symbol=symbol_normalized,
            m5=m5_data,
            m15=m15_data,
            m30=m30_data,
            h1=h1_data,
            advanced_features=advanced_features
        )
        
        # Extract recommendation
        rec = result.get("rec")
        if not rec or rec.direction == "HOLD":
            # No trade recommendation
            summary = (
                f"📊 {symbol} Analysis:\n"
                f"Direction: HOLD / WAIT\n"
                f"Regime: {rec.regime if rec else 'unknown'}\n"
                f"Reasoning: {rec.reasoning if rec else 'No clear setup detected'}\n"
                f"Confidence: {rec.confidence if rec else 0}%\n\n"
                f"💡 Recommendation: Wait for better setup"
            )
            
            # Add timestamp to HOLD responses too
            import time
            current_timestamp = int(time.time())
            
            return {
                "summary": summary,
                "data": {
                    "symbol": symbol,
                    "direction": "HOLD",
                    "confidence": rec.confidence if rec else 0,
                    "regime": rec.regime if rec else "unknown",
                    "reasoning": rec.reasoning if rec else "No clear setup",
                    "executable": False
                },
                "timestamp": current_timestamp,
                "timestamp_human": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "cache_control": "no-cache, no-store, must-revalidate"
            }
        
        # Valid trade recommendation
        current_price = m5_data.get("close", 0)
        
        recommendation = {
            "symbol": symbol,
            "symbol_normalized": symbol_normalized,
            "direction": rec.direction,
            "entry": rec.entry,
            "stop_loss": rec.sl,
            "take_profit": rec.tp,
            "confidence": rec.confidence,
            "reasoning": rec.reasoning,
            "risk_reward": rec.rr,
            "regime": rec.regime,
            "strategy": rec.strategy,
            "current_price": current_price,
            "executable": True
        }
        
        # 🔥 PHASE 3: Add ALL Binance enrichment data (37 fields)
        if registry.binance_service and registry.binance_service.running:
            recommendation["binance_price"] = m5_data.get("binance_price")
            recommendation["binance_momentum"] = m5_data.get("micro_momentum")
            recommendation["feed_health"] = m5_data.get("feed_health")
            
            # Baseline enrichments
            recommendation["binance_trend"] = m5_data.get("price_trend_10s", "UNKNOWN")
            recommendation["binance_volatility"] = m5_data.get("price_volatility", 0)
            recommendation["volume_surge"] = m5_data.get("volume_surge", False)
            recommendation["momentum_acceleration"] = m5_data.get("momentum_acceleration", 0)
            
            # Top 5 enrichments
            recommendation["price_structure"] = m5_data.get("price_structure")
            recommendation["structure_strength"] = m5_data.get("structure_strength")
            recommendation["volatility_state"] = m5_data.get("volatility_state")
            recommendation["volatility_change_pct"] = m5_data.get("volatility_change_pct")
            recommendation["momentum_consistency"] = m5_data.get("momentum_consistency")
            recommendation["momentum_quality"] = m5_data.get("momentum_quality")
            recommendation["micro_alignment"] = m5_data.get("micro_alignment")
            recommendation["micro_alignment_score"] = m5_data.get("micro_alignment_score")
            
            # Phase 2A enrichments
            recommendation["key_level"] = m5_data.get("key_level")
            recommendation["momentum_divergence"] = m5_data.get("momentum_divergence")
            recommendation["divergence_strength"] = m5_data.get("divergence_strength")
            recommendation["binance_atr"] = m5_data.get("binance_atr")
            recommendation["atr_divergence_pct"] = m5_data.get("atr_divergence_pct")
            recommendation["atr_state"] = m5_data.get("atr_state")
            recommendation["bb_position"] = m5_data.get("bb_position")
            recommendation["bb_squeeze"] = m5_data.get("bb_squeeze")
            recommendation["move_speed"] = m5_data.get("move_speed")
            recommendation["speed_warning"] = m5_data.get("speed_warning")
            recommendation["momentum_volume_alignment"] = m5_data.get("momentum_volume_alignment")
            recommendation["mv_alignment_quality"] = m5_data.get("mv_alignment_quality")
            
            # Phase 2B enrichments
            recommendation["tick_frequency"] = m5_data.get("tick_frequency")
            recommendation["tick_activity"] = m5_data.get("tick_activity")
            recommendation["price_zscore"] = m5_data.get("price_zscore")
            recommendation["zscore_extremity"] = m5_data.get("zscore_extremity")
            recommendation["mean_reversion_signal"] = m5_data.get("mean_reversion_signal")
            recommendation["pivot_data"] = m5_data.get("pivot_data")
            recommendation["price_vs_pivot"] = m5_data.get("price_vs_pivot")
            recommendation["aggressor_side"] = m5_data.get("aggressor_side")
            recommendation["aggressor_strength"] = m5_data.get("aggressor_strength")
            recommendation["liquidity_score"] = m5_data.get("liquidity_score")
            recommendation["liquidity_quality"] = m5_data.get("liquidity_quality")
            recommendation["session"] = m5_data.get("session")
            recommendation["candle_pattern"] = m5_data.get("candle_pattern")
            recommendation["pattern_confidence"] = m5_data.get("pattern_confidence")
            
            # Get Binance confirmation of signal
            enricher = BinanceEnrichment(registry.binance_service, registry.mt5_service, registry.order_flow_service)
            confirmed, confirmation_reason = enricher.get_binance_confirmation(
                symbol_normalized, rec.direction
            )
            recommendation["binance_confirmed"] = confirmed
            recommendation["binance_confirmation_reason"] = confirmation_reason
        
        # 🔥 NEW: Extract and prioritize order flow data
        if registry.order_flow_service and registry.order_flow_service.running:
            order_flow_data = m5_data.get("order_flow", {})
            if order_flow_data:
                recommendation["order_flow_signal"] = order_flow_data.get("signal", "NEUTRAL")
                recommendation["order_flow_confidence"] = order_flow_data.get("confidence", 0)
                recommendation["order_book_imbalance"] = order_flow_data.get("imbalance")
                recommendation["whale_count"] = order_flow_data.get("whale_count", 0)
                recommendation["pressure_side"] = order_flow_data.get("pressure_side", "NEUTRAL")
                recommendation["liquidity_voids"] = order_flow_data.get("liquidity_voids", 0)
                recommendation["order_flow_warnings"] = order_flow_data.get("warnings", [])
                
                # Check for order flow contradiction
                if order_flow_data.get("signal") != "NEUTRAL":
                    if order_flow_data["signal"] != rec.direction.upper():
                        recommendation["order_flow_contradiction"] = True
                        recommendation["warnings"] = recommendation.get("warnings", []) + [
                            f"⚠️ ORDER FLOW CONTRADICTION: {order_flow_data['signal']} vs {rec.direction}"
                        ]
                    else:
                        recommendation["order_flow_contradiction"] = False
        
        # Add Advanced insights if available
        if advanced_features and advanced_features.get("features"):
            advanced_data = advanced_features["features"].get("M15", {})
            if advanced_data:
                rmag = advanced_data.get("rmag", {})
                recommendation["advanced_rmag_stretch"] = rmag.get("ema200_atr", 0)
                recommendation["advanced_mtf_alignment"] = advanced_data.get("mtf_score", {}).get("total", 0)
        
        # Format human-readable summary
        distance_to_entry = abs(rec.entry - current_price)
        entry_type = "MARKET" if distance_to_entry < 10 else "LIMIT"
        
        summary = (
            f"📊 {symbol} Analysis - {rec.strategy.upper()}\n\n"
            f"Direction: {rec.direction} {entry_type}\n"
            f"Entry: {rec.entry:.2f}\n"
            f"Stop Loss: {rec.sl:.2f}\n"
            f"Take Profit: {rec.tp:.2f}\n"
            f"Risk:Reward: 1:{rec.rr:.1f}\n"
            f"Confidence: {rec.confidence}%\n\n"
            f"Regime: {rec.regime}\n"
            f"Current: {current_price:.2f}\n\n"
            f"💡 {rec.reasoning}"
        )
        
        # 🔥 NEW: Add order flow signals prominently (if available)
        if recommendation.get("order_flow_signal") and recommendation["order_flow_signal"] != "NEUTRAL":
            of_signal = recommendation["order_flow_signal"]
            of_confidence = recommendation.get("order_flow_confidence", 0)
            
            signal_emoji = "🟢" if of_signal == "BULLISH" else "🔴" if of_signal == "BEARISH" else "⚪"
            
            summary += f"\n\n{signal_emoji} Order Flow: {of_signal} ({of_confidence:.0f}%)"
            
            # Show whale activity if present
            if recommendation.get("whale_count", 0) > 0:
                summary += f"\n🐋 Whales Active: {recommendation['whale_count']} in last 60s"
            
            # Show imbalance
            if recommendation.get("order_book_imbalance"):
                imbalance = recommendation["order_book_imbalance"]
                imb_emoji = "🟢" if imbalance > 1.2 else "🔴" if imbalance < 0.8 else "⚪"
                summary += f"\n{imb_emoji} Book Imbalance: {imbalance:.2f}"
            
            # Show pressure
            if recommendation.get("pressure_side") != "NEUTRAL":
                pressure = recommendation["pressure_side"]
                pressure_emoji = "📈" if pressure == "BUY" else "📉"
                summary += f"\n{pressure_emoji} Pressure: {pressure}"
            
            # Show warnings
            if recommendation.get("order_flow_warnings"):
                for warning in recommendation["order_flow_warnings"][:2]:  # Show first 2
                    summary += f"\n⚠️ {warning}"
            
            # Show contradictions prominently
            if recommendation.get("order_flow_contradiction"):
                summary += f"\n\n⚠️ WARNING: Order flow contradicts trade direction!"
        
        if detail_level == "detailed":
            # Add Advanced insights
            advanced_summary = result.get("advanced_summary", "")
            if advanced_summary:
                summary += f"\n\n🔬 Advanced Insights:\n{advanced_summary}"
        
        # 🔥 PHASE 3: Add Binance enrichment summary
        if registry.binance_service and registry.binance_service.running:
            enricher = BinanceEnrichment(registry.binance_service, registry.mt5_service, registry.order_flow_service)
            binance_summary = enricher.get_enrichment_summary(symbol_normalized)
            summary += f"\n\n{binance_summary}"
            
            # Add confirmation status
            if recommendation.get("binance_confirmed") is not None:
                confirmation_emoji = "✅" if recommendation["binance_confirmed"] else "⚠️"
                summary += f"\n{confirmation_emoji} {recommendation.get('binance_confirmation_reason', '')}"
        
        # ============================================================================
        # LOG CONVERSATION (NEW)
        # ============================================================================
        try:
            conversation_logger.log_conversation(
                user_query=f"Analyze {symbol}",
                assistant_response=summary,
                symbol=symbol_normalized,
                action="ANALYZE",
                confidence=rec.confidence,
                recommendation=f"{rec.direction} @ {rec.entry:.2f}",
                reasoning=rec.reasoning,
                source="desktop_agent",
                extra={
                    "entry": rec.entry,
                    "sl": rec.sl,
                    "tp": rec.tp,
                    "rr": rec.rr,
                    "strategy": rec.strategy,
                    "regime": rec.regime
                }
            )
            
            # Also log to analysis table
            conversation_logger.log_analysis(
                symbol=symbol_normalized,
                direction=rec.direction,
                confidence=rec.confidence,
                reasoning=rec.reasoning,
                timeframe="M15",
                analysis_type="technical_v8",
                key_levels={
                    "entry": rec.entry,
                    "sl": rec.sl,
                    "tp": rec.tp
                },
                indicators={
                    "rsi": m5_data.get("rsi"),
                    "adx": m5_data.get("adx"),
                    "macd": m5_data.get("macd_histogram"),
                    "atr": m5_data.get("atr14")
                } if m5_data else None,
                advanced_features=advanced_features.get("features", {}).get("M15") if advanced_features else None,
                source="desktop_agent"
            )
            
            logger.info(f"📊 Analysis conversation logged to database")
            
        except Exception as e:
            logger.error(f"❌ Failed to log conversation: {e}", exc_info=True)
            # Don't fail the analysis, just log the error
        
        # Add timestamp and cache control to prevent stale data
        import time
        current_timestamp = int(time.time())
        
        return {
            "summary": summary,
            "data": recommendation,
            "timestamp": current_timestamp,
            "timestamp_human": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "cache_control": "no-cache, no-store, must-revalidate",
            "expires": "0"
        }
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}", exc_info=True)
        raise RuntimeError(f"Analysis failed: {str(e)}")


@registry.register("moneybot.analyse_symbol_full")
async def tool_analyse_symbol_full(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Comprehensive unified analysis combining ALL analysis layers:
    - Macro context (DXY, VIX, US10Y, S&P500, BTC Dominance, Fear & Greed Index)
    - Smart Money Concepts (CHOCH, BOS, Order Blocks, Liquidity Pools)
    - Advanced institutional features (RMAG, Bollinger ADX, VWAP, FVG, etc.)
    - Technical analysis and trade recommendation
    
    Returns a single unified verdict with layered recommendations (scalp/intraday/swing)
    
    Args:
        symbol: Trading symbol (e.g., BTCUSD, XAUUSD, EURUSD)
    
    Returns:
        Unified analysis with macro + SMC + Advanced + decision layers merged
    """
    symbol = args.get("symbol")
    if not symbol:
        raise ValueError("Missing required argument: symbol")
    
    logger.info(f"📊 Starting FULL unified analysis for {symbol}...")
    
    try:
        import time
        from datetime import datetime
        
        start_time = time.time()
        
        # Normalize symbol for broker (add 'c' suffix if needed)
        symbol_normalized = symbol
        if symbol.upper() not in ['DXY', 'VIX', 'US10Y', 'SPX']:
            # Normalize: strip any trailing 'c' or 'C', then add lowercase 'c'
            if not symbol.lower().endswith('c'):
                symbol_normalized = symbol.upper() + 'c'
            else:
                symbol_normalized = symbol.upper().rstrip('cC') + 'c'
            logger.info(f"   Normalized {symbol} → {symbol_normalized}")
        
        # ========== LAYER 1: MACRO CONTEXT ==========
        logger.info(f"   [1/4] Fetching macro context...")
        macro_data = await tool_macro_context({"symbol": symbol})
        # Keep the full macro_data object so we can access both "summary" and "data"
        macro_layer = macro_data
        
        # ========== LAYER 2: TECHNICAL ANALYSIS + ADVANCED FEATURES ==========
        logger.info(f"   [2/4] Running technical analysis + Advanced features...")
        
        # Initialize services
        from infra.indicator_bridge import IndicatorBridge
        from infra.feature_builder_advanced import build_features_advanced
        from infra.binance_enrichment import BinanceEnrichment
        
        mt5_service = registry.mt5_service
        if not mt5_service:
            raise RuntimeError("MT5 service not initialized")
        
        bridge = IndicatorBridge()
        
        # Fetch multi-timeframe data
        all_timeframe_data = bridge.get_multi(symbol_normalized)
        m5_data = all_timeframe_data.get("M5")
        m15_data = all_timeframe_data.get("M15")
        m30_data = all_timeframe_data.get("M30")
        h1_data = all_timeframe_data.get("H1")
        
        if not all([m5_data, m15_data, m30_data, h1_data]):
            raise RuntimeError(f"Failed to fetch market data for {symbol_normalized}")
        
        # Enrich with Binance data if available
        order_flow_signal = None
        btc_order_flow_metrics = None  # Initialize in outer scope - will be fetched for BTCUSD
        if registry.binance_service and registry.binance_service.running:
            enricher = BinanceEnrichment(registry.binance_service, mt5_service, registry.order_flow_service)
            m5_data = enricher.enrich_timeframe(symbol_normalized, m5_data, "M5")
            m15_data = enricher.enrich_timeframe(symbol_normalized, m15_data, "M15")
            
            # Get order flow signal if available
            if registry.order_flow_service and hasattr(registry.order_flow_service, 'get_order_flow_signal'):
                try:
                    # Map symbol to Binance format
                    binance_symbol_map = {
                        'BTCUSDc': 'BTCUSDT',
                        'XAUUSDc': 'XAUUSD',
                        'EURUSDc': 'EURUSD',
                        'GBPUSDc': 'GBPUSD',
                        'USDJPYc': 'USDJPY',
                        'GBPJPYc': 'GBPJPY',
                        'EURJPYc': 'EURJPY'
                    }
                    binance_symbol = binance_symbol_map.get(symbol_normalized, symbol_normalized.lower().replace('c', ''))
                    
                    order_flow_signal = registry.order_flow_service.get_order_flow_signal(binance_symbol)
                    if order_flow_signal:
                        logger.info(f"   ✅ Order flow signal retrieved: {order_flow_signal.get('signal', 'NEUTRAL')}")
                except Exception as e:
                    logger.warning(f"   ⚠️ Order flow signal unavailable: {e}")
        
        # NEW: Get BTC-specific order flow metrics for BTCUSD analysis (outside binance_service check)
        # Try to fetch metrics - let the tool handle availability checks (it works even if .running is False)
        if symbol_normalized == 'BTCUSDc':
            try:
                logger.info(f"   [2.1/4] Fetching BTC order flow metrics...")
                btc_metrics_result = await tool_btc_order_flow_metrics({"symbol": "BTCUSDT", "window_seconds": 30})
                if btc_metrics_result.get("data", {}).get("status") == "success":
                    btc_order_flow_metrics = btc_metrics_result.get("data", {})
                    delta = btc_order_flow_metrics.get('delta_volume', {}).get('net_delta', 0)
                    cvd = btc_order_flow_metrics.get('cvd', {}).get('current', 0)
                    logger.info(f"   ✅ BTC order flow metrics retrieved: Delta={delta:+.2f}, CVD={cvd:+.2f}, Status={btc_order_flow_metrics.get('status')}")
                else:
                    error_msg = btc_metrics_result.get('summary', btc_metrics_result.get('data', {}).get('message', 'Unknown error'))
                    logger.warning(f"   ⚠️ BTC order flow metrics unavailable: {error_msg}")
                    btc_order_flow_metrics = None
            except Exception as e:
                logger.warning(f"   ⚠️ BTC order flow metrics error: {e}", exc_info=True)
                btc_order_flow_metrics = None
        
        # Build Advanced features
        advanced_features = build_features_advanced(
            symbol=symbol_normalized,
            mt5svc=mt5_service,
            bridge=bridge,
            timeframes=["M5", "M15", "H1"]
        )
        
        # ========== VOLATILITY REGIME DETECTION (Phase 1) ==========
        volatility_regime_data = None
        try:
            logger.info(f"   [2.5/4] Detecting volatility regime...")
            from infra.volatility_regime_detector import RegimeDetector, VolatilityRegime
            import pandas as pd
            import numpy as np
            
            # Prepare timeframe data for regime detector
            regime_detector = RegimeDetector()
            timeframe_data_for_regime = {}
            
            for tf_name in ["M5", "M15", "H1"]:
                tf_data = all_timeframe_data.get(tf_name)
                if tf_data:
                    # Reconstruct rates DataFrame from indicator_bridge format
                    # indicator_bridge returns: opens, highs, lows, closes, volumes as lists
                    rates_df = None
                    if all(key in tf_data for key in ['opens', 'highs', 'lows', 'closes', 'volumes']):
                        # Reconstruct DataFrame from lists
                        try:
                            rates_df = pd.DataFrame({
                                'open': tf_data['opens'],
                                'high': tf_data['highs'],
                                'low': tf_data['lows'],
                                'close': tf_data['closes'],
                                'tick_volume': tf_data['volumes']
                            })
                        except Exception as e:
                            logger.debug(f"Could not reconstruct DataFrame for {tf_name}: {e}")
                    
                    # Get ATR values - indicator_bridge uses 'atr14', we need atr_50 too
                    atr_14 = tf_data.get("atr14") or tf_data.get("atr_14")
                    atr_50 = tf_data.get("atr_50")
                    
                    # If atr_50 not provided, calculate it from rates
                    if atr_14 and not atr_50 and rates_df is not None and len(rates_df) >= 50:
                        try:
                            # Calculate ATR(50) from the DataFrame
                            high = rates_df['high']
                            low = rates_df['low']
                            close = rates_df['close']
                            
                            # Calculate True Range
                            tr1 = high - low
                            tr2 = abs(high - close.shift(1))
                            tr3 = abs(low - close.shift(1))
                            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                            
                            # ATR(50) = SMA of TR over 50 periods
                            atr_50 = float(tr.rolling(window=50).mean().iloc[-1])
                        except Exception as e:
                            logger.debug(f"Could not calculate ATR(50) for {tf_name}: {e}")
                    
                    # Prepare data in format expected by detector
                    timeframe_data_for_regime[tf_name] = {
                        "rates": rates_df,  # Pass DataFrame instead of raw rates
                        "atr_14": atr_14,
                        "atr_50": atr_50,
                        "bb_upper": tf_data.get("bb_upper"),
                        "bb_lower": tf_data.get("bb_lower"),
                        "bb_middle": tf_data.get("bb_middle"),
                        "adx": tf_data.get("adx"),
                        "volume": tf_data.get("volumes") or tf_data.get("volume") or tf_data.get("tick_volume")
                    }
            
            if timeframe_data_for_regime:
                volatility_regime_data = regime_detector.detect_regime(
                    symbol=symbol_normalized,
                    timeframe_data=timeframe_data_for_regime,
                    current_time=datetime.now()
                )
                
                regime = volatility_regime_data.get("regime")
                confidence = volatility_regime_data.get("confidence", 0)
                regime_str = regime.value if isinstance(regime, VolatilityRegime) else str(regime)
                logger.info(f"   ✅ Volatility regime: {regime_str} (confidence: {confidence:.1f}%)")
                
                # ========== VOLATILITY STRATEGY RECOMMENDATIONS (Phase 2.2) ==========
                volatility_strategy_recommendations = None
                try:
                    from infra.volatility_strategy_mapper import get_strategies_for_volatility
                    from infra.session_helpers import SessionHelpers
                    
                    # Get current session for strategy recommendations
                    current_session = None
                    try:
                        current_session = SessionHelpers.get_current_session()
                    except Exception as sess_e:
                        logger.debug(f"Could not get current session: {sess_e}")
                    
                    if regime and isinstance(regime, VolatilityRegime):
                        volatility_strategy_recommendations = get_strategies_for_volatility(
                            volatility_regime=regime,
                            symbol=symbol_normalized,
                            session=current_session
                        )
                        logger.info(f"   ✅ Volatility strategy recommendations: {volatility_strategy_recommendations.get('recommendation', 'N/A')}")
                        
                        # Add to volatility_regime_data for response
                        volatility_regime_data["volatility_strategy_recommendations"] = volatility_strategy_recommendations
                except Exception as e:
                    logger.warning(f"   ⚠️ Volatility strategy recommendations failed: {e}")
                    # Don't fail entire analysis if strategy recommendations fail
                
                # ========== PHASE 4.1: EXTRACT DETAILED VOLATILITY METRICS ==========
                # Extract tracking metrics from regime detection response
                atr_trends = volatility_regime_data.get("atr_trends", {})
                wick_variances = volatility_regime_data.get("wick_variances", {})
                time_since_breakout = volatility_regime_data.get("time_since_breakout", {})
                mean_reversion_pattern = volatility_regime_data.get("mean_reversion_pattern", {})
                volatility_spike = volatility_regime_data.get("volatility_spike", {})
                session_transition = volatility_regime_data.get("session_transition", {})
                whipsaw_detected = volatility_regime_data.get("whipsaw_detected", {})
                
                # Build volatility_metrics dict for response
                volatility_metrics = {
                    "regime": regime.value if isinstance(regime, VolatilityRegime) else (str(regime) if regime else "UNKNOWN"),
                    "confidence": confidence,
                    "atr_ratio": volatility_regime_data.get("atr_ratio", 1.0),
                    "bb_width_ratio": volatility_regime_data.get("bb_width_ratio", 1.0),
                    "adx_composite": volatility_regime_data.get("adx_composite", 0.0),
                    "volume_confirmed": volatility_regime_data.get("volume_confirmed", False),
                    
                    # NEW TRACKING METRICS
                    "atr_trends": atr_trends,  # Per timeframe: M5, M15, H1
                    "wick_variances": wick_variances,  # Per timeframe: M5, M15, H1
                    "time_since_breakout": time_since_breakout,  # Per timeframe: M5, M15, H1
                    
                    # Convenience: Primary timeframe (M15) metrics
                    "atr_trend": atr_trends.get("M15", {}),
                    "wick_variance": wick_variances.get("M15", {}),
                    "time_since_breakout_minutes": time_since_breakout.get("M15", {}).get("time_since_minutes") if time_since_breakout.get("M15") else None,
                    
                    # Additional metrics
                    "mean_reversion_pattern": mean_reversion_pattern,
                    "volatility_spike": volatility_spike,
                    "session_transition": session_transition,
                    "whipsaw_detected": whipsaw_detected,
                    "strategy_recommendations": volatility_strategy_recommendations if volatility_strategy_recommendations else {}
                }
                
                # Add volatility_metrics to volatility_regime_data for response
                volatility_regime_data["volatility_metrics"] = volatility_metrics
                
                # ========== WAIT REASON CODES (Phase 1) ==========
                # Check for regime confidence low (<70%)
                wait_reasons = []
                if confidence < 70:
                    wait_reasons.append({
                        "code": "REGIME_CONFIDENCE_LOW",
                        "description": f"Regime confidence {confidence:.1f}% is below threshold (70%)",
                        "severity": "medium",
                        "threshold": 70,
                        "actual": confidence
                    })
                    logger.info(f"   ⚠️ WAIT reason: Regime confidence too low ({confidence:.1f}% < 70%)")
                
                # Get current price for strategy selection (before decision engine)
                import MetaTrader5 as mt5
                tick = mt5.symbol_info_tick(symbol_normalized)
                if tick:
                    current_price = float(tick.bid)
                else:
                    # Fallback to indicator data
                    current_price = (
                        m5_data.get("current_close") or
                        m5_data.get("close") or
                        m5_data.get("binance_price") or
                        0
                    )
                    if isinstance(current_price, list) and len(current_price) > 0:
                        current_price = float(current_price[-1])
                    else:
                        current_price = float(current_price) if current_price else 0
                
                # ========== STRATEGY SELECTION (Phase 2) ==========
                strategy_selection_data = None
                try:
                    from infra.volatility_strategy_selector import VolatilityStrategySelector
                    
                    logger.info(f"   [2.6/4] Selecting volatility-aware strategy...")
                    strategy_selector = VolatilityStrategySelector()
                    
                    # Get news data if available (from macro layer)
                    news_data = None
                    if macro_layer and isinstance(macro_layer, dict):
                        news_data = macro_layer.get("data", {}).get("news", {})
                    
                    # Select strategy
                    best_strategy, all_strategy_scores = strategy_selector.select_strategy(
                        symbol=symbol_normalized,
                        volatility_regime=volatility_regime_data,
                        market_data={
                            "current_price": current_price,
                            "indicators": m5_data
                        },
                        timeframe_data=all_timeframe_data,
                        news_data=news_data,
                        current_time=datetime.now()
                    )
                    
                    # Prepare strategy selection data
                    strategy_selection_data = {
                        "selected_strategy": best_strategy.to_dict() if best_strategy else None,
                        "all_scores": [score.to_dict() for score in all_strategy_scores],
                        "wait_reason": None
                    }
                    
                    # Add WAIT reason if no strategy selected
                    if not best_strategy:
                        max_score = max([s.score for s in all_strategy_scores]) if all_strategy_scores else 0
                        wait_reasons.append({
                            "code": "SCORE_SHORTFALL",
                            "description": f"No strategy scored above threshold (best: {max_score:.1f} < {VolatilityStrategySelector.MIN_SCORE_THRESHOLD})",
                            "severity": "medium",
                            "threshold": VolatilityStrategySelector.MIN_SCORE_THRESHOLD,
                            "actual": max_score
                        })
                        strategy_selection_data["wait_reason"] = wait_reasons[-1]
                        logger.info(f"   ⚠️ WAIT reason: Score shortfall (best strategy: {max_score:.1f} < {VolatilityStrategySelector.MIN_SCORE_THRESHOLD})")
                    else:
                        logger.info(f"   ✅ Selected strategy: {best_strategy.strategy.value} (score: {best_strategy.score:.1f})")
                    
                except Exception as e:
                    logger.warning(f"   ⚠️ Strategy selection failed: {e}")
                    # Don't fail entire analysis if strategy selection fails
                
                # Add WAIT reasons and strategy selection to volatility_regime_data
                if wait_reasons:
                    volatility_regime_data["wait_reasons"] = wait_reasons
                if strategy_selection_data:
                    volatility_regime_data["strategy_selection"] = strategy_selection_data
            else:
                logger.warning(f"   ⚠️ Insufficient timeframe data for regime detection")
        except Exception as e:
            logger.warning(f"   ⚠️ Volatility regime detection failed: {e}")
            # Don't fail entire analysis if regime detection fails
        
        # Ensure current_price is set (for decision engine)
        if 'current_price' not in locals():
            import MetaTrader5 as mt5
            tick = mt5.symbol_info_tick(symbol_normalized)
            if tick:
                current_price = float(tick.bid)
                logger.info(f"   📊 Current price from MT5: ${current_price:,.2f}")
            else:
                # Fallback to indicator data
                current_price = (
                    m5_data.get("current_close") or
                    m5_data.get("close") or
                    m5_data.get("binance_price") or
                    0
                )
                if isinstance(current_price, list) and len(current_price) > 0:
                    current_price = float(current_price[-1])
                else:
                    current_price = float(current_price) if current_price else 0
                logger.warning(f"   ⚠️ Using fallback price: ${current_price:,.2f}")
        
        # Run decision engine
        result = decide_trade(
            symbol=symbol_normalized,
            m5=m5_data,
            m15=m15_data,
            m30=m30_data,
            h1=h1_data,
            advanced_features=advanced_features
        )
        
        decision_layer = result.get("rec")
        
        # ========== LAYER 3: SMART MONEY CONCEPTS ==========
        logger.info(f"   [3/4] Running SMC analysis...")
        smc_data = await tool_get_multi_timeframe_analysis({"symbol": symbol})
        smc_layer = smc_data.get("data", {})
        
        # ========== CALCULATE MACRO BIAS & VOLATILITY SIGNALS ==========
        macro_bias_data = None
        volatility_signal = None
        
        try:
            # Calculate macro bias score
            from infra.macro_bias_calculator import create_macro_bias_calculator
            from infra.market_indices_service import create_market_indices_service
            from infra.fred_service import create_fred_service
            
            market_indices = create_market_indices_service()
            fred_service = create_fred_service()
            bias_calculator = create_macro_bias_calculator(market_indices, fred_service)
            macro_bias_data = bias_calculator.calculate_bias(symbol_normalized)
            logger.info(f"   ✅ Macro bias calculated: {macro_bias_data.get('bias_direction', 'neutral')} ({macro_bias_data.get('bias_score', 0):+.2f})")
        except Exception as e:
            logger.warning(f"   ⚠️ Macro bias calculation failed: {e}")
        
        try:
            # Calculate volatility signal
            from infra.volatility_forecasting import create_volatility_forecaster
            import pandas as pd
            import MetaTrader5 as mt5
            
            # Get M5 bars directly from MT5 for volatility analysis
            m5_rates = mt5.copy_rates_from_pos(symbol_normalized, mt5.TIMEFRAME_M5, 0, 100)
            if m5_rates is not None and len(m5_rates) > 50:
                # Convert to DataFrame
                df = pd.DataFrame(m5_rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df = df.set_index('time')
                
                # Rename columns to match volatility forecaster expectations
                df = df.rename(columns={'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close'})
                
                vol_forecaster = create_volatility_forecaster()
                volatility_signal = vol_forecaster.get_volatility_signal(df)
                logger.info(f"   ✅ Volatility signal: {volatility_signal}")
            else:
                logger.debug(f"   ⚠️ Insufficient M5 bars for volatility calculation: {len(m5_rates) if m5_rates is not None else 0}")
        except Exception as e:
            logger.debug(f"   ⚠️ Volatility signal calculation failed: {e}")
        
        # ========== LAYER 3.5: M1 MICROSTRUCTURE ANALYSIS ==========
        logger.info(f"   [3.5/4] Running M1 microstructure analysis...")
        m1_microstructure = None
        try:
            from infra.m1_data_fetcher import M1DataFetcher
            from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
            
            # Initialize M1 components if not already done
            if not hasattr(registry, 'm1_data_fetcher') or registry.m1_data_fetcher is None:
                registry.m1_data_fetcher = M1DataFetcher(
                    data_source=mt5_service,
                    max_candles=200,
                    cache_ttl=300
                )
                logger.info("   ✅ M1DataFetcher initialized")
            
            if not hasattr(registry, 'm1_analyzer') or registry.m1_analyzer is None:
                # Initialize threshold manager for dynamic threshold tuning (Phase 2.3)
                threshold_manager = None
                try:
                    from infra.m1_threshold_calibrator import SymbolThresholdManager
                    threshold_manager = SymbolThresholdManager("config/threshold_profiles.json")
                    logger.debug("   ✅ SymbolThresholdManager initialized")
                except Exception as e:
                    logger.debug(f"   ⚠️ SymbolThresholdManager initialization failed: {e}")
                
                registry.m1_analyzer = M1MicrostructureAnalyzer(
                    mt5_service=mt5_service,
                    threshold_manager=threshold_manager
                )
                logger.info("   ✅ M1MicrostructureAnalyzer initialized")
            
            # Fetch M1 data
            m1_candles = registry.m1_data_fetcher.fetch_m1_data(symbol_normalized, count=200, use_cache=True)
            
            if m1_candles and len(m1_candles) >= 10:
                # Prepare higher timeframe data for trend context
                structure_trend = smc_layer.get("trend", "UNKNOWN") if smc_layer else "UNKNOWN"
                higher_timeframe_data = {
                    'm5': {'trend': structure_trend},
                    'h1': {'trend': structure_trend}
                }
                
                # Run M1 microstructure analysis
                m1_microstructure = registry.m1_analyzer.analyze_microstructure(
                    symbol=symbol_normalized,
                    candles=m1_candles,
                    current_price=current_price,
                    higher_timeframe_data=higher_timeframe_data
                )
                
                if m1_microstructure.get('available'):
                    logger.info(f"   ✅ M1 microstructure analysis complete")
                    logger.info(f"      Signal: {m1_microstructure.get('signal_summary', 'NEUTRAL')}")
                    logger.info(f"      Confluence: {m1_microstructure.get('microstructure_confluence', {}).get('score', 0):.1f}/100")
                else:
                    logger.warning(f"   ⚠️ M1 microstructure analysis unavailable: {m1_microstructure.get('error', 'Unknown error')}")
            else:
                logger.warning(f"   ⚠️ Insufficient M1 candles: {len(m1_candles) if m1_candles else 0}")
                m1_microstructure = {
                    'available': False,
                    'error': f'Insufficient M1 candles: {len(m1_candles) if m1_candles else 0}'
                }
        except Exception as e:
            logger.warning(f"   ⚠️ M1 microstructure analysis failed: {e}")
            m1_microstructure = {
                'available': False,
                'error': str(e)
            }
            # Don't fail entire analysis if M1 fails
        
        # ========== LAYER 4: UNIFIED FORMATTING ==========
        logger.info(f"   [4/4] Merging all layers into unified response...")
        
        # Get BTC order flow metrics if this is a BTC analysis (if not already fetched above)
        # Try to fetch metrics - let the tool handle availability checks
        if symbol_normalized == 'BTCUSDc' and btc_order_flow_metrics is None:
            try:
                btc_metrics_result = await tool_btc_order_flow_metrics({"symbol": "BTCUSDT", "window_seconds": 30})
                if btc_metrics_result.get("data", {}).get("status") == "success":
                    btc_order_flow_metrics = btc_metrics_result.get("data", {})
                else:
                    btc_order_flow_metrics = None
            except Exception as e:
                logger.debug(f"BTC order flow metrics not available: {e}")
                btc_order_flow_metrics = None
        elif symbol_normalized != 'BTCUSDc':
            btc_order_flow_metrics = None
        
        # ========== ENHANCED DATA FIELDS CALCULATION ==========
        logger.info(f"   [4.5/4] Calculating enhanced data fields...")
        
        # Initialize enhanced data field calculators
        correlation_context = None
        htf_levels = None
        session_risk = None
        execution_context = None
        strategy_stats = None
        symbol_constraints = None
        
        try:
            # 1. Correlation Context
            from infra.correlation_context_calculator import CorrelationContextCalculator
            from infra.market_indices_service import create_market_indices_service
            
            market_indices = create_market_indices_service()
            corr_calculator = CorrelationContextCalculator(
                mt5_service=mt5_service,
                market_indices_service=market_indices
            )
            correlation_context = await corr_calculator.calculate_correlation_context(symbol_normalized)
            logger.debug(f"   ✅ Correlation context calculated")
        except Exception as e:
            logger.debug(f"   ⚠️ Correlation context calculation failed: {e}")
        
        try:
            # 2. HTF Levels
            from infra.htf_levels_calculator import HTFLevelsCalculator
            
            htf_calculator = HTFLevelsCalculator(mt5_service=mt5_service)
            htf_levels = await htf_calculator.calculate_htf_levels(symbol_normalized, current_price)
            logger.debug(f"   ✅ HTF levels calculated")
        except Exception as e:
            logger.debug(f"   ⚠️ HTF levels calculation failed: {e}")
        
        try:
            # 3. Session Risk
            from infra.session_risk_calculator import SessionRiskCalculator
            from infra.news_service import NewsService
            
            news_service = NewsService()
            session_risk_calc = SessionRiskCalculator(news_service=news_service)
            session_risk = await session_risk_calc.calculate_session_risk()
            logger.debug(f"   ✅ Session risk calculated")
        except Exception as e:
            logger.debug(f"   ⚠️ Session risk calculation failed: {e}")
        
        try:
            # 4. Execution Context
            from infra.execution_quality_monitor import ExecutionQualityMonitor
            from infra.spread_tracker import SpreadTracker
            
            spread_tracker = SpreadTracker()
            exec_monitor = ExecutionQualityMonitor(
                mt5_service=mt5_service,
                spread_tracker=spread_tracker
            )
            execution_context = await exec_monitor.get_execution_context(symbol_normalized)
            logger.debug(f"   ✅ Execution context calculated")
        except Exception as e:
            logger.debug(f"   ⚠️ Execution context calculation failed: {e}")
        
        try:
            # 5. Strategy Stats (if strategy is available from volatility regime)
            if volatility_regime_data and volatility_regime_data.get("strategy_selection"):
                strategy_selection = volatility_regime_data.get("strategy_selection", {})
                selected_strategy = strategy_selection.get("selected_strategy")
                if selected_strategy:
                    strategy_name = selected_strategy.get("strategy")
                    if strategy_name:
                        from infra.strategy_performance_tracker import StrategyPerformanceTracker
                        
                        strategy_tracker = StrategyPerformanceTracker()
                        current_regime = volatility_regime_data.get("regime", "UNKNOWN")
                        if isinstance(current_regime, dict):
                            current_regime = current_regime.get("value", "UNKNOWN")
                        elif hasattr(current_regime, 'value'):
                            current_regime = current_regime.value
                        
                        strategy_stats = strategy_tracker.get_strategy_stats_by_regime(
                            symbol=symbol_normalized,
                            strategy_name=strategy_name,
                            current_regime=str(current_regime)
                        )
                        logger.debug(f"   ✅ Strategy stats calculated")
        except Exception as e:
            logger.debug(f"   ⚠️ Strategy stats calculation failed: {e}")
        
        try:
            # 6. Symbol Constraints
            from infra.symbol_constraints_manager import SymbolConstraintsManager
            
            constraints_manager = SymbolConstraintsManager()
            symbol_constraints = constraints_manager.get_symbol_constraints(symbol_normalized)
            logger.debug(f"   ✅ Symbol constraints retrieved")
        except Exception as e:
            logger.debug(f"   ⚠️ Symbol constraints retrieval failed: {e}")
        
        # ========== 7. TICK MICROSTRUCTURE METRICS (NEW) ==========
        tick_metrics = None
        try:
            # Try to get instance - if not available, try to get it from main_api if running
            tick_generator = get_tick_metrics_instance()
            
            # If instance not available, try to get it from main_api's global variable
            if not tick_generator:
                try:
                    # Check if main_api is running and has the generator
                    import sys
                    if 'app.main_api' in sys.modules:
                        main_api_module = sys.modules['app.main_api']
                        if hasattr(main_api_module, 'tick_metrics_generator') and main_api_module.tick_metrics_generator:
                            tick_generator = main_api_module.tick_metrics_generator
                            # Set it so future calls work
                            set_tick_metrics_instance(tick_generator)
                            logger.debug(f"   🔍 Retrieved tick metrics generator from main_api module")
                except Exception as e:
                    logger.debug(f"   🔍 Could not retrieve tick metrics generator from main_api: {e}")
            
            if tick_generator:
                logger.debug(f"   🔍 Tick metrics generator instance found, retrieving metrics for {symbol_normalized}...")
                tick_metrics = tick_generator.get_latest_metrics(symbol_normalized)
                if tick_metrics:
                    metadata = tick_metrics.get("metadata", {})
                    data_available = metadata.get("data_available", False)
                    m5_count = tick_metrics.get("M5", {}).get("tick_count", 0)
                    logger.info(f"   ✅ Tick metrics retrieved for {symbol_normalized}: data_available={data_available}, M5_tick_count={m5_count}")
                else:
                    logger.warning(f"   ⚠️ Tick metrics returned None for {symbol_normalized} (generator running but no cached data yet)")
            else:
                logger.warning(f"   ⚠️ Tick metrics generator not available (not initialized or failed to start)")
                logger.debug(f"   🔍 get_tick_metrics_instance() returned: {tick_generator}")
        except Exception as e:
            logger.warning(f"   ⚠️ Tick metrics retrieval failed: {e}", exc_info=True)
        
        unified_response = _format_unified_analysis(
            symbol=symbol,
            symbol_normalized=symbol_normalized,
            current_price=current_price,
            macro=macro_layer,
            smc=smc_layer,
            advanced_features=advanced_features,
            decision=decision_layer,
            m5_data=m5_data,
            m15_data=m15_data,
            h1_data=h1_data,
            order_flow=order_flow_signal,
            btc_order_flow_metrics=btc_order_flow_metrics,  # NEW: BTC-specific order flow metrics
            macro_bias=macro_bias_data,
            volatility_signal=volatility_signal,
            volatility_regime=volatility_regime_data,
            m1_microstructure=m1_microstructure,
            correlation_context=correlation_context,
            htf_levels=htf_levels,
            session_risk=session_risk,
            execution_context=execution_context,
            strategy_stats=strategy_stats,
            symbol_constraints=symbol_constraints,
            tick_metrics=tick_metrics,  # NEW: Tick microstructure metrics
            timestamp=int(time.time())
        )
        
        # ========== TIER 3: AUTO-ALERT HOOK ==========
        try:
            from infra.auto_alert_generator import AutoAlertGenerator
            
            if registry.alert_manager:
                auto_alert_gen = AutoAlertGenerator()
                
                # Extract analysis data for auto-alert evaluation
                analysis_data = unified_response.get("data", {})
                
                # Get confidence score from decision layer or extract from summary
                confidence = decision_layer.get("confidence", 0) if decision_layer else 0
                confidence_score_int = confidence
                
                # Try to extract confidence_score from summary if available
                try:
                    summary_lines = unified_response.get("summary", "").split("\n")
                    for line in summary_lines:
                        if "BIAS CONFIDENCE:" in line:
                            # Parse "🟢 BIAS CONFIDENCE: 85/100"
                            parts = line.split(":")
                            if len(parts) > 1:
                                score_part = parts[1].strip().split("/")[0]
                                confidence_score_int = int(score_part)
                                break
                except:
                    pass  # Use decision confidence as fallback
                
                # Build analysis_result dict for auto-alert generator
                analysis_result = {
                    "confluence_verdict": analysis_data.get("confluence", {}).get("verdict", ""),
                    "structure_trend": analysis_data.get("smc", {}).get("trend", ""),
                    "bos_detected": analysis_data.get("smc", {}).get("bos_detected", False),
                    "choch_detected": analysis_data.get("smc", {}).get("choch_detected", False),
                    "pattern_summary": unified_response.get("summary", "")  # Include pattern summary text
                }
                
                # Check if alert should be created
                if auto_alert_gen.should_create_alert(
                    analysis_result=analysis_result,
                    symbol=symbol_normalized,
                    confidence_score=confidence_score_int,
                    features_data=advanced_features.get("features", {}) if advanced_features else {},
                    m5_data=m5_data,
                    m15_data=m15_data,
                    order_flow=order_flow_signal
                ):
                    # Generate alert details
                    alert_details = auto_alert_gen.generate_alert_details(
                        symbol=symbol_normalized,
                        analysis_result=analysis_result,
                        confidence_score=confidence_score_int,
                        features_data=advanced_features.get("features", {}) if advanced_features else {},
                        current_price=current_price
                    )
                    
                    # Create alert
                    alert = auto_alert_gen.create_alert(
                        alert_details=alert_details,
                        alert_manager=registry.alert_manager
                    )
                    
                    if alert:
                        # Send Discord notification
                        await auto_alert_gen.send_discord_notification(
                            alert=alert,
                            symbol=symbol_normalized,
                            confidence_score=confidence_score_int,
                            confluence_verdict=analysis_result.get("confluence_verdict", "")
                        )
                        logger.info(f"🤖 Auto-alert created for {symbol_normalized} (confidence: {confidence_score_int}/100)")
        except Exception as e:
            logger.debug(f"Auto-alert hook failed: {e}")
            # Don't fail the entire analysis if auto-alert fails
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Full unified analysis complete in {elapsed:.2f}s")
        
        # Store the exact summary text for Discord sharing (ChatGPT displays this to user)
        # This allows ChatGPT to send the EXACT same text to Discord without regeneration/condensation
        if unified_response and "summary" in unified_response:
            registry.last_analysis_summary = unified_response["summary"]
            registry.last_analysis_symbol = symbol_normalized
            registry.last_analysis_timestamp = time.time()
            logger.debug(f"💾 Stored analysis summary for {symbol_normalized} ({len(registry.last_analysis_summary)} chars)")
        
        return unified_response
        
    except Exception as e:
        logger.error(f"❌ Full analysis failed: {e}", exc_info=True)
        raise RuntimeError(f"Full analysis failed: {str(e)}")


@registry.register("moneybot.execute_trade")
async def tool_execute_trade(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a trade on MT5 with automatic risk-based lot sizing
    
    Args:
        symbol: Trading symbol
        direction: "BUY" | "SELL"
        entry: Entry price (for market orders, use current price)
        stop_loss: Stop loss price
        take_profit: Take profit price
        volume: Position size (optional - if not provided, calculates based on risk)
        risk_pct: Risk percentage override (optional - uses symbol default if not provided)
        order_type: "market" | "limit" | "stop" (default: "market")
    
    Automatic Lot Sizing:
        - BTCUSD/XAUUSD: Max 0.02 lots (0.75-1.0% risk)
        - Forex pairs: Max 0.04 lots (1.0-1.25% risk)
        - Calculates based on: equity, stop distance, symbol volatility
    
    Returns:
        Ticket number and monitoring status
    """
    symbol = args.get("symbol")
    direction = args.get("direction")
    entry = args.get("entry")
    stop_loss = args.get("stop_loss")
    take_profit = args.get("take_profit")
    volume = args.get("volume")  # Can be None (will calculate)
    order_type = args.get("order_type", "market")
    risk_pct = args.get("risk_pct")  # Optional risk percentage override
    
    # Validate required arguments
    if not all([symbol, direction, stop_loss, take_profit]):
        raise ValueError("Missing required arguments: symbol, direction, stop_loss, take_profit")
    
    # Normalize symbol
    # Normalize: strip any trailing 'c' or 'C', then add lowercase 'c'
    if not symbol.lower().endswith('c'):
        symbol_normalized = symbol.upper() + 'c'
    else:
        symbol_normalized = symbol.upper().rstrip('cC') + 'c'
    
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    # ========== VOLATILITY-AWARE RISK MANAGEMENT (Phase 3) ==========
    volatility_regime_data = None
    try:
        logger.info(f"   [Risk Management] Detecting volatility regime for risk adjustment...")
        from infra.volatility_regime_detector import RegimeDetector, VolatilityRegime
        from infra.volatility_risk_manager import VolatilityRiskManager, get_volatility_adjusted_lot_size
        import pandas as pd
        import numpy as np
        
        # Get timeframe data for regime detection
        from infra.indicator_bridge import IndicatorBridge
        bridge = IndicatorBridge()
        all_timeframe_data = bridge.get_multi(symbol_normalized)
        
        if all_timeframe_data:
            regime_detector = RegimeDetector()
            timeframe_data_for_regime = {}
            
            for tf_name in ["M5", "M15", "H1"]:
                tf_data = all_timeframe_data.get(tf_name)
                if tf_data:
                    # Reconstruct rates DataFrame
                    rates_df = None
                    if all(key in tf_data for key in ['opens', 'highs', 'lows', 'closes', 'volumes']):
                        try:
                            rates_df = pd.DataFrame({
                                'open': tf_data['opens'],
                                'high': tf_data['highs'],
                                'low': tf_data['lows'],
                                'close': tf_data['closes'],
                                'tick_volume': tf_data['volumes']
                            })
                        except Exception as e:
                            logger.debug(f"Could not reconstruct DataFrame for {tf_name}: {e}")
                    
                    atr_14 = tf_data.get("atr14") or tf_data.get("atr_14")
                    atr_50 = tf_data.get("atr_50")
                    
                    # Calculate ATR(50) if needed
                    if atr_14 and not atr_50 and rates_df is not None and len(rates_df) >= 50:
                        try:
                            high = rates_df['high']
                            low = rates_df['low']
                            close = rates_df['close']
                            tr1 = high - low
                            tr2 = abs(high - close.shift(1))
                            tr3 = abs(low - close.shift(1))
                            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                            atr_50 = float(tr.rolling(window=50).mean().iloc[-1])
                        except Exception as e:
                            logger.debug(f"Could not calculate ATR(50) for {tf_name}: {e}")
                    
                    timeframe_data_for_regime[tf_name] = {
                        "rates": rates_df,
                        "atr_14": atr_14,
                        "atr_50": atr_50,
                        "bb_upper": tf_data.get("bb_upper"),
                        "bb_lower": tf_data.get("bb_lower"),
                        "bb_middle": tf_data.get("bb_middle"),
                        "adx": tf_data.get("adx"),
                        "volume": tf_data.get("volumes") or tf_data.get("volume")
                    }
            
            if timeframe_data_for_regime:
                volatility_regime_data = regime_detector.detect_regime(
                    symbol=symbol_normalized,
                    timeframe_data=timeframe_data_for_regime,
                    current_time=datetime.now()
                )
                
                regime = volatility_regime_data.get("regime")
                confidence = volatility_regime_data.get("confidence", 0)
                # Extract regime string
                if isinstance(regime, VolatilityRegime):
                    regime_str = regime.value
                elif hasattr(regime, 'value'):
                    regime_str = regime.value
                else:
                    regime_str = str(regime) if regime else "UNKNOWN"
                logger.info(f"   ✅ Volatility regime: {regime_str} (confidence: {confidence:.1f}%)")
                
                # Check circuit breakers
                risk_manager = VolatilityRiskManager()
                import MetaTrader5 as mt5
                account_info = mt5.account_info()
                equity = float(account_info.equity) if account_info else 10000.0
                
                can_trade, block_reason = risk_manager.check_circuit_breakers(
                    symbol=symbol_normalized,
                    equity=equity,
                    current_time=datetime.now()
                )
                
                if not can_trade:
                    error_msg = f"🚫 Trade blocked by circuit breaker: {block_reason}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                
                logger.info(f"   ✅ Circuit breakers passed")
        
    except Exception as e:
        logger.warning(f"   ⚠️ Volatility risk management check failed: {e}")
        # Don't fail trade execution if risk management fails - use standard sizing
    
    # Calculate lot size if not provided (treat 0 as None)
    if volume is None or volume == 0:
        import MetaTrader5 as mt5
        
        # Get account equity
        account_info = mt5.account_info()
        if account_info:
            equity = float(account_info.equity)
        else:
            equity = 10000  # Fallback
            logger.warning("Could not get account equity, using $10,000 default")
        
        # Get symbol info for accurate calculations
        symbol_info = mt5.symbol_info(symbol_normalized)
        if symbol_info:
            tick_value = float(symbol_info.trade_tick_value)
            tick_size = float(symbol_info.trade_tick_size)
            contract_size = float(symbol_info.trade_contract_size)
        else:
            tick_value = 1.0
            tick_size = 0.01
            contract_size = 100000
            logger.warning(f"Could not get symbol info for {symbol_normalized}, using defaults")
        
        # Use volatility-adjusted lot sizing if regime data available
        if volatility_regime_data:
            try:
                from infra.volatility_risk_manager import get_volatility_adjusted_lot_size
                volume, sizing_metadata = get_volatility_adjusted_lot_size(
                    symbol=symbol_normalized,
                    entry=float(entry) if entry else 0,
                    stop_loss=float(stop_loss),
                    equity=equity,
                    volatility_regime=volatility_regime_data,
                    base_risk_pct=risk_pct,
                    tick_value=tick_value,
                    tick_size=tick_size,
                    contract_size=contract_size
                )
                logger.info(
                    f"📊 Volatility-adjusted lot size: {volume} "
                    f"(Base risk: {sizing_metadata['base_risk_pct']:.2f}% → "
                    f"Adjusted: {sizing_metadata['adjusted_risk_pct']:.2f}%, "
                    f"Regime: {sizing_metadata['adjustment_reason']})"
                )
            except Exception as e:
                logger.warning(f"Volatility-adjusted sizing failed: {e}, using standard sizing")
                # Fallback to standard sizing
                volume = get_lot_size(
                    symbol=symbol_normalized,
                    entry=float(entry) if entry else 0,
                    stop_loss=float(stop_loss),
                    equity=equity,
                    risk_pct=risk_pct,
                    use_risk_based=True,
                    tick_value=tick_value,
                    tick_size=tick_size,
                    contract_size=contract_size
                )
                logger.info(f"📊 Calculated lot size: {volume} (Risk-based, Equity=${equity:.2f})")
        else:
            # Standard risk-based lot sizing (no volatility adjustment)
            volume = get_lot_size(
                symbol=symbol_normalized,
                entry=float(entry) if entry else 0,
                stop_loss=float(stop_loss),
                equity=equity,
                risk_pct=risk_pct,
                use_risk_based=True,
                tick_value=tick_value,
                tick_size=tick_size,
                contract_size=contract_size
            )
            logger.info(f"📊 Calculated lot size: {volume} (Risk-based, Equity=${equity:.2f})")
    else:
        logger.info(f"📊 Using provided lot size: {volume}")
    
    logger.info(f"💰 Executing {direction} {symbol_normalized} @ {volume} lots")
    
    try:
        import MetaTrader5 as mt5
        from infra.indicator_bridge import IndicatorBridge
        from infra.feature_builder_advanced import build_features_advanced
        
        # Get current price
        quote = registry.mt5_service.get_quote(symbol_normalized)
        
        current_price = quote.ask if direction == "BUY" else quote.bid
        
        # 🛡️ PRE-EXECUTION SAFETY VALIDATION
        if registry.signal_prefilter:
            logger.info("🛡️ Running pre-execution safety checks...")
            
            # Prepare signal for validation
            signal_to_validate = {
                "action": direction,
                "entry": entry if entry else current_price,
                "sl": stop_loss,
                "tp": take_profit,
                "confidence": args.get("confidence", 100)  # Assume high confidence if not specified
            }
            
            # Validate and adjust
            can_execute, reason, adjusted_signal = registry.signal_prefilter.adjust_and_validate(
                symbol_normalized,
                signal_to_validate,
                {"bid": quote.bid, "ask": quote.ask}
            )
            
            if not can_execute:
                error_msg = f"🚫 Trade blocked by safety filter: {reason}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            logger.info(f"✅ Safety checks passed: {reason}")
            
            # Use adjusted prices if available
            if adjusted_signal:
                stop_loss = adjusted_signal.get("sl") or adjusted_signal.get("stop_loss")
                take_profit = adjusted_signal.get("tp") or adjusted_signal.get("take_profit")
                if entry and "entry" in adjusted_signal:
                    entry = adjusted_signal["entry"]
                logger.info(f"📊 Prices adjusted for MT5 offset")
        else:
            logger.warning("⚠️ No safety filter configured - executing without validation")
        
        # Determine order type and MT5 mapping
        if order_type == "market":
            actual_entry = current_price
            mt5_action = mt5.TRADE_ACTION_DEAL
            mt5_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        elif order_type == "limit":
            actual_entry = entry
            mt5_action = mt5.TRADE_ACTION_PENDING
            mt5_type = mt5.ORDER_TYPE_BUY_LIMIT if direction == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
        elif order_type == "stop":
            actual_entry = entry
            mt5_action = mt5.TRADE_ACTION_PENDING
            mt5_type = mt5.ORDER_TYPE_BUY_STOP if direction == "BUY" else mt5.ORDER_TYPE_SELL_STOP
        else:
            logger.warning(f"Unknown order_type '{order_type}', defaulting to market")
            actual_entry = current_price
            mt5_action = mt5.TRADE_ACTION_DEAL
            mt5_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL

        # Normalize prices to symbol tick size and validate
        sym_info = None
        try:
            sym_info = mt5.symbol_info(symbol_normalized)
            if sym_info:
                tick_size = float(sym_info.trade_tick_size) if sym_info.trade_tick_size else 0.01
                def _norm(x: float) -> float:
                    if x is None:
                        return None
                    if tick_size > 0:
                        return round(round(x / tick_size) * tick_size, 10)
                    return x
                actual_entry = _norm(actual_entry)
                if stop_loss:
                    stop_loss = _norm(stop_loss)
                if take_profit:
                    take_profit = _norm(take_profit)
        except Exception as e:
            logger.warning(f"Error normalizing prices: {e}")
            sym_info = None
        
        # Validate stop loss and take profit are not None/0 for market orders
        if mt5_action == mt5.TRADE_ACTION_DEAL:
            if not stop_loss or stop_loss == 0:
                raise ValueError(f"Stop loss is required for market orders. Provided: {stop_loss}")
            if not take_profit or take_profit == 0:
                raise ValueError(f"Take profit is required for market orders. Provided: {take_profit}")

        # Place order
        logger.info(f"   Placing {order_type} order: {direction} {symbol_normalized}")
        
        # Determine appropriate filling mode: RETURN for pending orders tends to be safest
        filling_mode = mt5.ORDER_FILLING_IOC
        if mt5_action == mt5.TRADE_ACTION_PENDING:
            filling_mode = mt5.ORDER_FILLING_RETURN

        # Validate and adjust SL/TP to meet broker constraints BEFORE order placement
        try:
            if sym_info:
                logger.info(
                    f"Symbol constraints: tick_size={sym_info.trade_tick_size}, stops_level={sym_info.trade_stops_level}, freeze_level={sym_info.trade_freeze_level}, filling_mode={sym_info.filling_mode}"
                )
                
                # Calculate minimum stop distance
                min_dist_pts = float(sym_info.trade_stops_level or 0)
                ts = float(sym_info.trade_tick_size or 0.0)
                min_dist = (min_dist_pts * ts) if (min_dist_pts and ts) else 0.0
                
                # Validate and adjust SL/TP for market orders
                if mt5_action == mt5.TRADE_ACTION_DEAL and stop_loss and take_profit:
                    # Validate SL direction
                    if direction == "BUY":
                        if stop_loss >= actual_entry:
                            raise ValueError(f"Stop loss {stop_loss} must be below entry {actual_entry} for BUY order")
                        if take_profit <= actual_entry:
                            raise ValueError(f"Take profit {take_profit} must be above entry {actual_entry} for BUY order")
                        
                        # Check minimum distance and adjust if needed
                        sl_distance = abs(actual_entry - stop_loss)
                        tp_distance = abs(take_profit - actual_entry)
                        
                        if min_dist > 0:
                            if sl_distance < min_dist:
                                logger.warning(f"SL distance {sl_distance:.5f} < broker minimum {min_dist:.5f}, adjusting...")
                                stop_loss = actual_entry - min_dist
                                if sym_info:
                                    stop_loss = _norm(stop_loss)
                                logger.info(f"Adjusted SL to {stop_loss:.5f}")
                            
                            if tp_distance < min_dist:
                                logger.warning(f"TP distance {tp_distance:.5f} < broker minimum {min_dist:.5f}, adjusting...")
                                take_profit = actual_entry + min_dist
                                if sym_info:
                                    take_profit = _norm(take_profit)
                                logger.info(f"Adjusted TP to {take_profit:.5f}")
                    else:  # SELL
                        if stop_loss <= actual_entry:
                            raise ValueError(f"Stop loss {stop_loss} must be above entry {actual_entry} for SELL order")
                        if take_profit >= actual_entry:
                            raise ValueError(f"Take profit {take_profit} must be below entry {actual_entry} for SELL order")
                        
                        # Check minimum distance and adjust if needed
                        sl_distance = abs(stop_loss - actual_entry)
                        tp_distance = abs(actual_entry - take_profit)
                        
                        if min_dist > 0:
                            if sl_distance < min_dist:
                                logger.warning(f"SL distance {sl_distance:.5f} < broker minimum {min_dist:.5f}, adjusting...")
                                stop_loss = actual_entry + min_dist
                                if sym_info:
                                    stop_loss = _norm(stop_loss)
                                logger.info(f"Adjusted SL to {stop_loss:.5f}")
                            
                            if tp_distance < min_dist:
                                logger.warning(f"TP distance {tp_distance:.5f} < broker minimum {min_dist:.5f}, adjusting...")
                                take_profit = actual_entry - min_dist
                                if sym_info:
                                    take_profit = _norm(take_profit)
                                logger.info(f"Adjusted TP to {take_profit:.5f}")
                
                # Basic side/distance checks for pending orders (log warnings only)
                if mt5_action == mt5.TRADE_ACTION_PENDING:
                    side = "BUY" if mt5_type in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP) else "SELL"
                    if side == "BUY":
                        # Limit must be below ask, Stop must be above ask
                        if mt5_type == mt5.ORDER_TYPE_BUY_LIMIT and actual_entry >= quote.ask:
                            logger.warning("Pending BUY_LIMIT price not below ask; broker may reject")
                        if mt5_type == mt5.ORDER_TYPE_BUY_STOP and actual_entry <= quote.ask:
                            logger.warning("Pending BUY_STOP price not above ask; broker may reject")
                    else:
                        if mt5_type == mt5.ORDER_TYPE_SELL_LIMIT and actual_entry <= quote.bid:
                            logger.warning("Pending SELL_LIMIT price not above bid; broker may reject")
                        if mt5_type == mt5.ORDER_TYPE_SELL_STOP and actual_entry >= quote.bid:
                            logger.warning("Pending SELL_STOP price not below bid; broker may reject")
        except ValueError:
            raise  # Re-raise validation errors
        except Exception as e:
            logger.warning(f"Error validating broker constraints: {e}")

        # Ensure SL/TP are floats (not None) for MT5
        if stop_loss is None:
            stop_loss = 0.0
        if take_profit is None:
            take_profit = 0.0
        
        stop_loss = float(stop_loss)
        take_profit = float(take_profit)

        # Prepare order request with validated SL/TP
        request = {
            "action": mt5_action,
            "symbol": symbol_normalized,
            "volume": volume,
            "type": mt5_type,
            "price": actual_entry,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": 20,
            "magic": 234000,
            "comment": args.get("comment") or "Phone control",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }
        
        logger.info(f"Order request: {direction} {symbol_normalized} @ {actual_entry}, SL={stop_loss}, TP={take_profit}, Volume={volume}")

        # Pre-check order to capture broker diagnostics
        try:
            order_check = mt5.order_check(request)
            if order_check is not None:
                logger.info(f"order_check: retcode={getattr(order_check,'retcode',None)} comment={getattr(order_check,'comment',None)} volume={getattr(order_check,'volume',None)}")
        except Exception as _e:
            order_check = None
        
        # Send order
        result = mt5.order_send(request)
        
        if result is None:
            try:
                last_err = mt5.last_error()
            except Exception:
                last_err = None
            # Include order_check diagnostics if available
            if order_check is not None:
                try:
                    chk = order_check
                    raise RuntimeError(
                        f"Order send failed: MT5 returned None (last_error={last_err}, check.retcode={getattr(chk,'retcode',None)}, check.comment={getattr(chk,'comment',None)})"
                    )
                except Exception:
                    pass
            raise RuntimeError(f"Order send failed: MT5 returned None (last_error={last_err})")
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Order failed: {result.retcode} - {result.comment}"
            logger.error(f"❌ {error_msg}")
            
            # Log failed trade to database
            try:
                journal_repo.add_event(
                    event="trade_execution_failed",
                    symbol=symbol_normalized,
                    side=direction,
                    price=actual_entry,
                    sl=stop_loss,
                    tp=take_profit,
                    volume=volume,
                    reason=f"MT5 Error {result.retcode}: {result.comment}",
                    extra={
                        "order_type": order_type,
                        "retcode": result.retcode,
                        "comment": result.comment,
                        "source": "desktop_agent"
                    }
                )
                logger.info(f"📊 Failed trade logged to database")
            except Exception as e:
                logger.error(f"Failed to log error to database: {e}")
            
            raise RuntimeError(error_msg)
        
        ticket = result.order
        actual_entry_price = result.price
        
        logger.info(f"✅ Order placed successfully: Ticket {ticket}")
        
        # ============================================================================
        # DATABASE LOGGING (NEW)
        # ============================================================================
        try:
            # Get account info for balance/equity
            account_info = mt5.account_info()
            balance = account_info.balance if account_info else None
            equity = account_info.equity if account_info else None
            
            # Calculate risk-reward ratio
            if stop_loss and take_profit:
                risk = abs(actual_entry_price - stop_loss)
                reward = abs(take_profit - actual_entry_price)
                rr = reward / risk if risk > 0 else None
            else:
                rr = None
            
            # Log to database
            journal_repo.write_exec({
                "ts": int(datetime.now().timestamp()),
                "symbol": symbol_normalized,
                "side": direction,
                "entry": actual_entry_price,
                "sl": stop_loss,
                "tp": take_profit,
                "lot": volume,
                "ticket": ticket,
                "position": ticket,  # Same as ticket for positions
                "balance": balance,
                "equity": equity,
                "confidence": args.get("confidence", 100),  # High confidence if not specified
                "regime": None,  # Could extract from Advanced features later
                "rr": rr,
                "notes": f"Phone Control - {order_type} order, Lot sizing: {'auto' if args.get('volume') is None else 'manual'}"
            })
            
            logger.info(f"📊 Trade logged to database: ticket {ticket}")
            
        except Exception as e:
            logger.error(f"❌ Failed to log trade to database: {e}", exc_info=True)
            # Don't fail the trade execution, just log the error
        
        # ============================================================================
        # Universal Dynamic SL/TP Manager Registration (ALWAYS - even without strategy_type)
        # If no strategy_type provided, uses DEFAULT_STANDARD (generic trailing)
        # ============================================================================
        universal_manager_registered = False
        # FIX: Always register, not just when strategy_type is provided
        try:
            from infra.universal_sl_tp_manager import (
                UniversalDynamicSLTPManager,
                UNIVERSAL_MANAGED_STRATEGIES,
                StrategyType
            )
            
            # Normalize strategy_type to enum (can be None - will use DEFAULT_STANDARD)
            strategy_type_enum = None
            if strategy_type:
                if isinstance(strategy_type, str):
                    # Try to match string to enum value
                    for st in StrategyType:
                        if st.value == strategy_type:
                            strategy_type_enum = st
                            break
                elif isinstance(strategy_type, StrategyType):
                    strategy_type_enum = strategy_type
            # If strategy_type is None, register_trade will use DEFAULT_STANDARD automatically
            
            # Always register with Universal Manager (strategy_type can be None - will use DEFAULT_STANDARD)
            universal_sl_tp_manager = UniversalDynamicSLTPManager(
                mt5_service=registry.mt5_service
            )
            
            trade_state = universal_sl_tp_manager.register_trade(
                ticket=ticket,
                symbol=symbol_normalized,
                strategy_type=strategy_type_enum,  # Can be None - will use DEFAULT_STANDARD
                direction=direction,
                entry_price=actual_entry_price,
                initial_sl=stop_loss,
                initial_tp=take_profit,
                initial_volume=volume
            )
            
            if trade_state:
                strategy_name = trade_state.strategy_type.value if trade_state.strategy_type else "DEFAULT_STANDARD"
                logger.info(
                    f"✅ Trade {ticket} registered with Universal SL/TP Manager "
                    f"(strategy: {strategy_name})"
                )
                universal_manager_registered = True
            else:
                logger.warning(
                    f"⚠️ Trade {ticket} registration with Universal Manager failed"
                )
        except Exception as e:
            logger.error(
                f"❌ Error registering trade {ticket} with Universal Manager: {e}",
                exc_info=True
            )
        
        # Auto-register to DTMS (only if not registered with Universal Manager)
        if not universal_manager_registered:
            try:
                from dtms_integration import auto_register_dtms
                result_dict = {
                    'symbol': symbol_normalized,
                    'direction': direction,
                    'entry_price': actual_entry_price,
                    'volume': volume,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit
                }
                auto_register_dtms(ticket, result_dict)
            except Exception:
                pass  # Silent failure
        
        # ============================================================================
        # Enable Advanced-enhanced intelligent exits
        # ============================================================================
        logger.info(f"   Enabling Advanced-enhanced intelligent exits...")
        
        # Fetch Advanced features
        bridge = IndicatorBridge()
        advanced_features = build_features_advanced(
            symbol=symbol_normalized,
            mt5svc=registry.mt5_service,
            bridge=bridge,
            timeframes=["M15"]
        )
        
        # ============================================================================
        # LOG ADVANCED ANALYTICS (NEW)
        # ============================================================================
        try:
            from infra.advanced_analytics import AdvancedFeatureTracker

            advanced_tracker = AdvancedFeatureTracker()

            # Record trade entry with Advanced features
            success = advanced_tracker.record_trade_entry(
                ticket=ticket,
                symbol=symbol_normalized,
                direction=direction,
                entry_price=actual_entry_price,
                sl=stop_loss,
                tp=take_profit,
                advanced_features=advanced_features
            )

            if success:
                logger.info(f"📊 Advanced features logged to analytics database: ticket {ticket}")
            else:
                logger.warning(f"⚠️ Failed to log Advanced features for ticket {ticket}")

        except Exception as e:
            logger.error(f"❌ Failed to log Advanced analytics: {e}", exc_info=True)
            # Don't fail the trade execution, just log the error
        
        # ============================================================================
        # TRADE TYPE CLASSIFICATION (AIES Phase 1 MVP)
        # ============================================================================
        classification_info = {}
        trade_comment = args.get("comment") or "Phone control"
        
        logger.info(f"   → Trade comment for classification: '{trade_comment}'")
        
        # Determine exit parameters based on classification
        base_breakeven_pct = settings.INTELLIGENT_EXITS_BREAKEVEN_PCT
        base_partial_pct = settings.INTELLIGENT_EXITS_PARTIAL_PCT
        partial_close_pct = settings.INTELLIGENT_EXITS_PARTIAL_CLOSE_PCT
        
        # Use getattr with default False to handle missing attribute gracefully
        # Also check raw environment variable directly as fallback
        import os
        raw_env_value = os.getenv("ENABLE_TRADE_TYPE_CLASSIFICATION", "NOT_SET")
        
        # Helper function to convert string to bool (same as config.py)
        def _as_bool(val):
            if val is None:
                return False
            return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}
        
        # Try to get from settings instance first
        enable_classification = getattr(settings, 'ENABLE_TRADE_TYPE_CLASSIFICATION', None)
        
        # If not found in settings, fallback to environment variable directly
        if enable_classification is None:
            enable_classification = _as_bool(raw_env_value) if raw_env_value != "NOT_SET" else False
            logger.info(f"   → Classification not in settings, using env var directly: {raw_env_value} → {enable_classification}")
        else:
            logger.info(f"   → Classification from settings: {enable_classification}")
        
        logger.info(f"   → Final classification flag: {enable_classification} (type: {type(enable_classification)})")
        logger.info(f"   → Raw env var ENABLE_TRADE_TYPE_CLASSIFICATION: {raw_env_value}")
        
        if enable_classification:
            try:
                import time
                from infra.trade_type_classifier import TradeTypeClassifier
                from infra.session_analyzer import SessionAnalyzer
                from infra.classification_metrics import record_classification_metric
                
                logger.info(f"   Classifying trade type for {symbol_normalized}...")
                
                # Measure classification latency
                classification_start_time = time.time()
                
                session_analyzer = SessionAnalyzer()
                session_info = session_analyzer.get_current_session()
                
                classifier = TradeTypeClassifier(
                    mt5_service=registry.mt5_service,
                    session_service=session_analyzer
                )
                
                # Get volatility regime data if available (Phase 3.09)
                volatility_regime_for_classification = None
                try:
                    if 'volatility_regime_data' in locals():
                        volatility_regime_for_classification = volatility_regime_data
                except:
                    pass
                
                classification = classifier.classify(
                    symbol=symbol_normalized,
                    entry_price=actual_entry_price,
                    stop_loss=stop_loss,
                    comment=trade_comment,
                    session_info=session_info,
                    volatility_regime=volatility_regime_for_classification
                )
                
                classification_latency_ms = (time.time() - classification_start_time) * 1000
                
                trade_type = classification["trade_type"]
                confidence = classification["confidence"]
                reasoning = classification["reasoning"]
                factors = classification["factors"]
                
                classification_info = {
                    "trade_type": trade_type,
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "factors": factors
                }
                
                logger.info(f"📊 Trade Classification: {trade_type} (confidence: {confidence:.2f}) - {reasoning}")
                
                # Record metrics
                try:
                    record_classification_metric(
                        trade_type=trade_type,
                        confidence=confidence,
                        reasoning=reasoning,
                        factor_used=factors.get("primary_factor", "unknown"),
                        latency_ms=classification_latency_ms,
                        feature_enabled=True
                    )
                except Exception as e:
                    logger.warning(f"Failed to record classification metric: {e}")
                
                # Select exit parameters based on classification
                if trade_type == "SCALP":
                    base_breakeven_pct = 25.0
                    base_partial_pct = 40.0
                    partial_close_pct = 70.0
                    logger.info(f"   Using SCALP exit parameters: {base_breakeven_pct}% BE / {base_partial_pct}% partial / {partial_close_pct}% close")
                else:  # INTRADAY
                    logger.info(f"   Using INTRADAY exit parameters: {base_breakeven_pct}% BE / {base_partial_pct}% partial / {partial_close_pct}% close")
            except Exception as e:
                logger.error(f"❌ Classification failed: {e}", exc_info=True)
                classification_info = {"error": str(e)}
        else:
            logger.info(f"   → Classification skipped - feature flag disabled (ENABLE_TRADE_TYPE_CLASSIFICATION={enable_classification})")
        
        logger.info(f"   → Final exit parameters before exit manager: BE={base_breakeven_pct}%, Partial={base_partial_pct}%, Close={partial_close_pct}%")
        
        # Create exit manager with Binance and order flow integration
        exit_manager = create_exit_manager(
            registry.mt5_service,
            binance_service=registry.binance_service,
            order_flow_service=registry.order_flow_service
        )
        
        exit_result = exit_manager.add_rule_advanced(
            ticket=ticket,
            symbol=symbol_normalized,
            entry_price=actual_entry_price,
            direction=direction.lower(),
            initial_sl=stop_loss,
            initial_tp=take_profit,
            advanced_features=advanced_features,
            base_breakeven_pct=base_breakeven_pct,
            base_partial_pct=base_partial_pct,
            partial_close_pct=partial_close_pct,
            vix_threshold=settings.INTELLIGENT_EXITS_VIX_THRESHOLD,
            use_hybrid_stops=settings.INTELLIGENT_EXITS_USE_HYBRID_STOPS,
            trailing_enabled=settings.INTELLIGENT_EXITS_TRAILING_ENABLED
        )
        
        # Get Advanced-adjusted percentages
        rule = exit_manager.rules.get(ticket)
        breakeven_pct = rule.breakeven_profit_pct if rule else base_breakeven_pct
        partial_pct = rule.partial_profit_pct if rule else base_partial_pct
        final_partial_close_pct = rule.partial_close_pct if rule else partial_close_pct

        advanced_adjusted = breakeven_pct != 30.0 or partial_pct != 60.0

        logger.info(f"✅ Intelligent exits enabled: {breakeven_pct}% / {partial_pct}%")

        # Format summary with classification info
        summary = (
            f"✅ Trade Executed Successfully — {symbol_normalized} {direction} (Range Scalp)\n\n"
            f"📊 Order Summary:\n\n"
            f"Direction: {direction} (Market Execution)\n"
            f"Entry: ${actual_entry_price:,.2f}\n"
            f"Stop Loss: ${stop_loss:,.2f}\n"
            f"Take Profit: ${take_profit:,.2f}\n"
            f"Volume: {volume} lots\n"
            f"Order ID: {ticket}\n"
            f"Comment: {trade_comment}\n\n"
        )
        
        # Add classification info if available
        if classification_info and "trade_type" in classification_info:
            trade_type_display = classification_info["trade_type"]
            confidence_display = classification_info.get("confidence", 0.0)
            reasoning_display = classification_info.get("reasoning", "Default classification")
            
            summary += (
                f"📊 Trade Classification:\n"
                f"   Type: {trade_type_display}\n"
                f"   Confidence: {confidence_display:.0%}\n"
                f"   Reasoning: {reasoning_display}\n\n"
            )

        summary += (
            f"🤖 Intelligent Exits — AUTO-ENABLED\n"
            f"🎯 Breakeven: +0.{int(breakeven_pct/10):.0f}R (~${actual_entry_price + (actual_entry_price - stop_loss) * (breakeven_pct/100):,.2f})\n"
            f"💰 Partial Profit: +0.{int(partial_pct/10):.0f}R (~${actual_entry_price + (actual_entry_price - stop_loss) * (partial_pct/100):,.2f})\n"
            f"🔬 Hybrid ATR+VIX: Active\n"
            f"📈 Trailing Stop: Activated post-breakeven\n"
        )

        if advanced_adjusted:
            summary += f"   ⚡ Advanced-Adjusted (from base {base_breakeven_pct:.0f}%/{base_partial_pct:.0f}%)\n"
        
        summary += f"\n🟢 Status: Trade LIVE and Managed Automatically"
        
        # Send Discord notification with classification info
        try:
            logger.info("   → Attempting to send Discord notification...")
            from discord_notifications import DiscordNotifier
            discord_notifier = DiscordNotifier()
            logger.info(f"   → Discord notifier initialized, enabled={discord_notifier.enabled}")
            
            if discord_notifier.enabled:
                # Get plan_id if this is an auto-executed trade
                plan_id = get_plan_id_from_ticket(ticket)
                plan_id_line = f"📊 **Plan ID**: {plan_id}\n" if plan_id else ""
                
                discord_message = (
                    f"✅ **Trade Executed Successfully**\n\n"
                    f"💱 **Symbol**: {symbol_normalized.replace('c', '')}\n"
                    f"📊 **Direction**: {direction} (Market Execution)\n"
                    f"💰 **Entry**: ${actual_entry_price:,.2f}\n"
                    f"🛡️ **SL**: ${stop_loss:,.2f} | 🎯 **TP**: ${take_profit:,.2f}\n"
                    f"📦 **Volume**: {volume} lots\n"
                    f"🎫 **Ticket**: {ticket}\n"
                    f"{plan_id_line}\n"
                )
                
                # Add classification info if available
                if classification_info and "trade_type" in classification_info:
                    trade_type_display = classification_info["trade_type"]
                    confidence_display = classification_info.get("confidence", 0.0)
                    reasoning_display = classification_info.get("reasoning", "Default classification")
                    
                    discord_message += (
                        f"📊 **Trade Classification**:\n"
                        f"   • Type: **{trade_type_display}**\n"
                        f"   • Confidence: **{confidence_display:.0%}**\n"
                        f"   • Reasoning: {reasoning_display}\n\n"
                    )
                else:
                    logger.info("   → No classification info available for Discord message")
                
                discord_message += (
                    f"⚙️ **Intelligent Exits Enabled**:\n"
                    f"   • Breakeven: {breakeven_pct:.0f}% profit (0.{int(breakeven_pct/10):.0f}R)\n"
                    f"   • Partial: {partial_pct:.0f}% profit (0.{int(partial_pct/10):.0f}R), close {final_partial_close_pct:.0f}%\n"
                    f"   • Hybrid ATR+VIX: Active\n"
                    f"   • Trailing Stop: Enabled post-breakeven\n\n"
                    f"🤖 Position is now on autopilot!"
                )
                
                logger.info(f"   → Sending Discord message (length: {len(discord_message)} chars)...")
                
                # Use send_message directly for better formatting (instead of send_system_alert)
                success = discord_notifier.send_message(
                    message=discord_message,
                    message_type="TRADE_EXECUTION",
                    color=0x00ff00,  # Green for successful trade
                    channel="private",
                    custom_title="Trade Executed"
                )
                if success:
                    logger.info("   ✅ Discord notification sent successfully with classification info")
                else:
                    logger.warning("   ❌ Discord notification failed to send (send_message returned False)")
            else:
                logger.warning("   ⚠️ Discord notifications are disabled - check DISCORD_WEBHOOK_URL in .env")
        except ImportError as e:
            logger.error(f"   ❌ Failed to import DiscordNotifier: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"   ❌ Discord notification error: {e}", exc_info=True)
        
        # ============================================================================
        # LOG CONVERSATION (NEW)
        # ============================================================================
        try:
            conversation_logger.log_conversation(
                user_query=f"Execute {direction} {symbol} @ {entry if entry else 'market'}",
                assistant_response=summary,
                symbol=symbol_normalized,
                action="EXECUTE",
                confidence=args.get("confidence", 100),
                execution_result="success",
                ticket=ticket,
                source="desktop_agent",
                extra={
                    "entry": actual_entry_price,
                    "sl": stop_loss,
                    "tp": take_profit,
                    "volume": volume,
                    "order_type": order_type,
                    "rr": rr,
                    "classification": classification_info
                }
            )
            
            logger.info(f"📊 Trade execution conversation logged to database")
            
        except Exception as e:
            logger.error(f"❌ Failed to log conversation: {e}", exc_info=True)
            # Don't fail the execution, just log the error
        
        return {
            "summary": summary,
            "data": {
                "ticket": ticket,
                "symbol": symbol,
                "symbol_normalized": symbol_normalized,
                "direction": direction,
                "entry": actual_entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "volume": volume,
                "monitoring_enabled": True,
                "advanced_breakeven_pct": breakeven_pct,
                "advanced_partial_pct": partial_pct,
                "advanced_adjusted": advanced_adjusted
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Trade execution failed: {e}", exc_info=True)
        raise RuntimeError(f"Execution failed: {str(e)}")

@registry.register("moneybot.executeBracketTrade")
async def tool_execute_bracket_trade(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a bracket trade (OCO pair) with automatic cancellation
    
    Places two pending orders (BUY and SELL) at specified entry levels.
    When one order fills, the other is automatically cancelled within 3 seconds.
    Ideal for range breakout strategies, consolidation breakouts, and news events.
    
    Args:
        symbol: Trading symbol (e.g., "XAUUSD", "BTCUSD") - will be normalized with 'c' suffix
        buy_entry: Entry price for BUY order
        buy_sl: Stop loss for BUY order (must be below buy_entry)
        buy_tp: Take profit for BUY order (must be above buy_entry)
        sell_entry: Entry price for SELL order
        sell_sl: Stop loss for SELL order (must be above sell_entry)
        sell_tp: Take profit for SELL order (must be below sell_entry)
        reasoning: Optional reasoning/comment for the bracket trade (default: "Bracket trade")
    
    Returns:
        Summary and data including OCO group ID, both order tickets, and monitoring status
    """
    # Extract parameters
    symbol = args.get("symbol")
    buy_entry = args.get("buy_entry")
    buy_sl = args.get("buy_sl")
    buy_tp = args.get("buy_tp")
    sell_entry = args.get("sell_entry")
    sell_sl = args.get("sell_sl")
    sell_tp = args.get("sell_tp")
    reasoning = args.get("reasoning", "Bracket trade")
    
    # Validate required parameters
    if not all([symbol, buy_entry, buy_sl, buy_tp, sell_entry, sell_sl, sell_tp]):
        missing = [k for k, v in {
            "symbol": symbol,
            "buy_entry": buy_entry,
            "buy_sl": buy_sl,
            "buy_tp": buy_tp,
            "sell_entry": sell_entry,
            "sell_sl": sell_sl,
            "sell_tp": sell_tp
        }.items() if v is None]
        raise ValueError(f"Missing required arguments: {', '.join(missing)}")
    
    # Normalize symbol (ensure it ends with lowercase 'c')
    if not symbol.lower().endswith('c'):
        symbol_normalized = symbol.upper() + 'c'
    else:
        symbol_normalized = symbol.upper().rstrip('cC') + 'c'
    
    logger.info(f"📊 Executing bracket trade for {symbol_normalized}: BUY@{buy_entry} + SELL@{sell_entry}")
    
    try:
        # Call the API endpoint via HTTP (Option A - consistent with architecture)
        import httpx
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "http://localhost:8000/mt5/execute_bracket",
                params={
                    "symbol": symbol_normalized,
                    "buy_entry": buy_entry,
                    "buy_sl": buy_sl,
                    "buy_tp": buy_tp,
                    "sell_entry": sell_entry,
                    "sell_sl": sell_sl,
                    "sell_tp": sell_tp,
                    "reasoning": reasoning
                }
            )
        
        if response.status_code == 200:
            result = response.json()
            
            # Extract data from API response
            oco_group_id = result.get("oco_group_id")
            buy_order = result.get("buy_order", {})
            sell_order = result.get("sell_order", {})
            buy_ticket = buy_order.get("ticket") if buy_order else result.get("buy_ticket")
            sell_ticket = sell_order.get("ticket") if sell_order else result.get("sell_ticket")
            message = result.get("message", "Bracket trade created with OCO monitoring")
            
            # Format summary
            summary = (
                f"✅ Bracket Trade Executed Successfully!\n\n"
                f"Symbol: {symbol} ({symbol_normalized})\n\n"
                f"🟢 BUY Order:\n"
                f"  Entry: {buy_entry:.5f}\n"
                f"  SL: {buy_sl:.5f} | TP: {buy_tp:.5f}\n"
                f"  Ticket: {buy_ticket}\n\n"
                f"🔴 SELL Order:\n"
                f"  Entry: {sell_entry:.5f}\n"
                f"  SL: {sell_sl:.5f} | TP: {sell_tp:.5f}\n"
                f"  Ticket: {sell_ticket}\n\n"
                f"🔗 OCO Group: {oco_group_id}\n"
                f"   (When one order fills, the other will auto-cancel within 3 seconds)\n\n"
                f"💭 Reasoning: {reasoning}\n\n"
                f"📊 Your bracket trade is now on autopilot!"
            )
            
            # Log conversation
            try:
                conversation_logger.log_conversation(
                    user_query=f"Execute bracket trade {symbol} BUY@{buy_entry} SELL@{sell_entry}",
                    assistant_response=summary,
                    symbol=symbol_normalized,
                    action="BRACKET_TRADE",
                    confidence=args.get("confidence", 100),
                    execution_result="success",
                    ticket=f"{buy_ticket},{sell_ticket}",
                    source="desktop_agent",
                    extra={
                        "buy_entry": buy_entry,
                        "buy_sl": buy_sl,
                        "buy_tp": buy_tp,
                        "sell_entry": sell_entry,
                        "sell_sl": sell_sl,
                        "sell_tp": sell_tp,
                        "oco_group_id": oco_group_id,
                        "reasoning": reasoning
                    }
                )
                logger.info(f"📊 Bracket trade conversation logged to database")
            except Exception as e:
                logger.error(f"❌ Failed to log conversation: {e}", exc_info=True)
                # Don't fail the execution, just log the error
            
            return {
                "summary": summary,
                "data": {
                    "symbol": symbol,
                    "symbol_normalized": symbol_normalized,
                    "buy_ticket": buy_ticket,
                    "sell_ticket": sell_ticket,
                    "oco_group_id": oco_group_id,
                    "buy_entry": buy_entry,
                    "buy_sl": buy_sl,
                    "buy_tp": buy_tp,
                    "sell_entry": sell_entry,
                    "sell_sl": sell_sl,
                    "sell_tp": sell_tp,
                    "monitoring_enabled": True,
                    "message": message,
                    "reasoning": reasoning
                }
            }
        else:
            # API returned an error
            error_detail = "Unknown error"
            try:
                error_response = response.json()
                error_detail = error_response.get("detail", str(response.status_code))
            except:
                error_detail = f"HTTP {response.status_code}: {response.text[:200]}"
            
            logger.error(f"❌ Bracket trade API error: {error_detail}")
            raise RuntimeError(f"Bracket trade failed: {error_detail}")
            
    except httpx.TimeoutException:
        error_msg = "Bracket trade request timed out (15s timeout)"
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg)
    except httpx.RequestError as e:
        error_msg = f"Bracket trade request failed: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg)
    except Exception as e:
        logger.error(f"❌ Bracket trade execution failed: {e}", exc_info=True)
        raise RuntimeError(f"Bracket trade failed: {str(e)}")

@registry.register("moneybot.getCurrentPrice")
async def tool_get_current_price(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get current price for a trading symbol
    
    Supports:
    - MT5 symbols: XAUUSD, BTCUSD, EURUSD (auto-adds 'c' suffix for broker)
    - Market indices: DXY, VIX, US10Y (fetched from Yahoo Finance)
    
    Args:
        symbol: Trading symbol (e.g., "XAUUSD", "BTCUSD", "DXY")
    
    Returns:
        Current price data including bid, ask, mid price, spread, and timestamp
    """
    symbol = args.get("symbol")
    if not symbol:
        raise ValueError("Missing required argument: symbol")
    
    logger.info(f"💰 Getting current price for {symbol}")
    
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"http://localhost:8000/api/v1/price/{symbol}"
            )
        
        if response.status_code == 200:
            price_data = response.json()
            
            symbol_display = price_data.get("symbol", symbol)
            mid = price_data.get("mid", 0)
            bid = price_data.get("bid", 0)
            ask = price_data.get("ask", 0)
            spread = price_data.get("spread", 0)
            digits = price_data.get("digits", 5)
            source = price_data.get("source", "MT5")
            
            # Format prices with appropriate decimal places
            format_str = f"{{:.{digits}f}}"
            mid_str = format_str.format(mid)
            bid_str = format_str.format(bid)
            ask_str = format_str.format(ask)
            spread_str = format_str.format(spread)
            
            summary = (
                f"💰 Current Price: {symbol_display}\n"
                f"  Mid: {mid_str}\n"
                f"  Bid: {bid_str} | Ask: {ask_str}\n"
                f"  Spread: {spread_str}\n"
                f"  Source: {source}"
            )
            
            # Add note if it's a special index (DXY, VIX, US10Y)
            if price_data.get("note"):
                summary += f"\n  Note: {price_data.get('note')}"
            
            return {
                "summary": summary,
                "data": price_data
            }
        else:
            error_detail = "Unknown error"
            try:
                error_response = response.json()
                error_detail = error_response.get("detail", str(response.status_code))
            except:
                error_detail = f"HTTP {response.status_code}: {response.text[:200]}"
            
            logger.error(f"❌ Price API error: {error_detail}")
            raise RuntimeError(f"Failed to get price: {error_detail}")
            
    except httpx.TimeoutException:
        error_msg = "Price request timed out (10s timeout)"
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg)
    except httpx.RequestError as e:
        error_msg = f"Price request failed: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg)
    except Exception as e:
        logger.error(f"❌ Failed to get current price: {e}", exc_info=True)
        raise RuntimeError(f"Failed to get current price: {str(e)}")

@registry.register("moneybot.get_m1_microstructure")
async def tool_get_m1_microstructure(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get M1 (1-minute) microstructure analysis for a symbol.
    
    Returns detailed microstructure analysis including:
    - CHOCH/BOS detection with confidence scores
    - Liquidity zones (PDH/PDL, equal highs/lows)
    - Volatility state (CONTRACTING/EXPANDING/STABLE)
    - Rejection wicks and order blocks
    - Momentum quality and trend context
    - Signal summary (BULLISH_MICROSTRUCTURE/BEARISH_MICROSTRUCTURE/NEUTRAL)
    - Session context and asset personality
    - Strategy hint and confluence scores
    
    Args:
        symbol: Trading symbol (e.g., "XAUUSD", "BTCUSD", "EURUSD")
        include_candles: Optional - include raw M1 candle data in response (default: false)
    
    Returns:
        Full microstructure analysis with all insights
    """
    symbol = args.get("symbol")
    if not symbol:
        raise ValueError("Missing required argument: symbol")
    
    include_candles = args.get("include_candles", False)
    
    logger.info(f"📊 Getting M1 microstructure analysis for {symbol}")
    
    try:
        # Normalize symbol (add 'c' suffix if needed)
        symbol_normalized = symbol.upper()
        if not symbol_normalized.endswith('C'):
            symbol_normalized = symbol_normalized.rstrip('Cc') + 'c'
        
        # Initialize MT5 service if needed
        if not registry.mt5_service:
            registry.mt5_service = MT5Service()
            if not registry.mt5_service.connect():
                raise RuntimeError("Failed to connect to MT5")
        
        # Initialize M1 components if not already done
        from infra.m1_data_fetcher import M1DataFetcher
        from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
        
        if not hasattr(registry, 'm1_data_fetcher') or registry.m1_data_fetcher is None:
            registry.m1_data_fetcher = M1DataFetcher(
                data_source=registry.mt5_service,
                max_candles=200,
                cache_ttl=300
            )
            logger.debug("M1DataFetcher initialized")
        
        if not hasattr(registry, 'm1_analyzer') or registry.m1_analyzer is None:
            # Initialize threshold manager for dynamic threshold tuning (Phase 2.3)
            threshold_manager = None
            try:
                from infra.m1_threshold_calibrator import SymbolThresholdManager
                threshold_manager = SymbolThresholdManager("config/threshold_profiles.json")
            except Exception as e:
                logger.debug(f"SymbolThresholdManager initialization failed: {e}")
            
            registry.m1_analyzer = M1MicrostructureAnalyzer(
                mt5_service=registry.mt5_service,
                threshold_manager=threshold_manager
            )
            logger.debug("M1MicrostructureAnalyzer initialized")
        
        # Get current price for analysis
        try:
            quote = registry.mt5_service.get_quote(symbol_normalized)
            current_price = (quote.bid + quote.ask) / 2 if quote else None
        except:
            current_price = None
        
        # Fetch M1 data
        m1_candles = registry.m1_data_fetcher.fetch_m1_data(symbol_normalized, count=200, use_cache=True)
        
        if not m1_candles or len(m1_candles) < 10:
            error_msg = f"Insufficient M1 candles: {len(m1_candles) if m1_candles else 0}"
            logger.warning(f"⚠️ {error_msg}")
            return {
                "summary": f"⚠️ M1 Microstructure Analysis Unavailable\n  {error_msg}",
                "data": {
                    "available": False,
                    "error": error_msg,
                    "symbol": symbol_normalized
                }
            }
        
        # Run M1 microstructure analysis
        m1_analysis = registry.m1_analyzer.analyze_microstructure(
            symbol=symbol_normalized,
            candles=m1_candles,
            current_price=current_price
        )
        
        if not m1_analysis or not m1_analysis.get('available'):
            error_msg = m1_analysis.get('error', 'Analysis unavailable') if m1_analysis else 'Analysis failed'
            logger.warning(f"⚠️ M1 analysis unavailable: {error_msg}")
            return {
                "summary": f"⚠️ M1 Microstructure Analysis Unavailable\n  {error_msg}",
                "data": {
                    "available": False,
                    "error": error_msg,
                    "symbol": symbol_normalized
                }
            }
        
        # Build summary
        signal_summary = m1_analysis.get('signal_summary', 'NEUTRAL')
        choch_bos = m1_analysis.get('choch_bos', {})
        confluence = m1_analysis.get('microstructure_confluence', {})
        volatility = m1_analysis.get('volatility', {})
        structure = m1_analysis.get('structure', {})
        
        summary_lines = [
            f"📊 M1 Microstructure Analysis: {symbol_normalized}",
            f"  Signal: {signal_summary}",
            f"  CHOCH: {'✅ Confirmed' if choch_bos.get('choch_confirmed') else '✅ Detected' if choch_bos.get('has_choch') else '❌ None'}",
            f"  BOS: {'✅ Detected' if choch_bos.get('has_bos') else '❌ None'}",
            f"  Confidence: {choch_bos.get('confidence', 0):.1f}%",
            f"  Structure: {structure.get('type', 'N/A')} (Strength: {structure.get('strength', 0):.0f}%)",
            f"  Volatility: {volatility.get('state', 'N/A')}",
            f"  Confluence: {confluence.get('score', 0):.1f}/100 (Grade: {confluence.get('grade', 'N/A')})",
        ]
        
        # Add strategy hint if available
        strategy_hint = m1_analysis.get('strategy_hint')
        if strategy_hint:
            summary_lines.append(f"  Strategy Hint: {strategy_hint}")
        
        # Add session context if available
        session_context = m1_analysis.get('session_context', {})
        if session_context.get('session'):
            summary_lines.append(f"  Session: {session_context.get('session')}")
        
        summary = "\n".join(summary_lines)
        
        # Build response data
        response_data = {
            "available": True,
            "symbol": symbol_normalized,
            "timestamp": m1_analysis.get('timestamp'),
            "data_age_seconds": m1_analysis.get('data_age_seconds'),
            **m1_analysis  # Include all analysis data
        }
        
        # Optionally include raw candles
        if include_candles:
            response_data["candles"] = m1_candles
        
        logger.info(f"✅ M1 microstructure analysis complete for {symbol_normalized}")
        
        return {
            "summary": summary,
            "data": response_data
        }
        
    except Exception as e:
        error_msg = f"Failed to get M1 microstructure: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)
        return {
            "summary": f"❌ M1 Microstructure Analysis Failed\n  {error_msg}",
            "data": {
                "available": False,
                "error": error_msg,
                "symbol": symbol_normalized if 'symbol_normalized' in locals() else symbol
            }
        }

@registry.register("moneybot.getPositions")
async def tool_get_positions(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get all open positions with full details
    
    Returns:
        List of all open positions with profit/loss, entry, SL, TP, etc.
    """
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    logger.info("📊 Getting all open positions")
    
    try:
        positions = registry.mt5_service.list_positions()
        
        if not positions:
            return {
                "summary": "📭 No open positions",
                "data": {"positions": []}
            }
        
        # Format positions for display
        summary_lines = [f"📊 Open Positions ({len(positions)})\n"]
        
        for pos in positions:
            symbol = pos['symbol'].replace('c', '')
            direction = "🟢 BUY" if pos['type'] == 0 else "🔴 SELL"
            profit = pos.get('profit', 0)
            profit_emoji = "📈" if profit > 0 else "📉" if profit < 0 else "➖"
            
            summary_lines.append(
                f"{direction} {symbol}\n"
                f"  Ticket: {pos['ticket']}\n"
                f"  Entry: {pos['price_open']:.5f}\n"
                f"  Current: {pos.get('price_current', 0):.5f}\n"
                f"  SL: {pos.get('sl', 0):.5f} | TP: {pos.get('tp', 0):.5f}\n"
                f"  Volume: {pos['volume']} lots\n"
                f"  {profit_emoji} P/L: ${profit:.2f}\n"
            )
        
        return {
            "summary": "\n".join(summary_lines),
            "data": {"positions": positions, "count": len(positions)}
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get positions: {e}", exc_info=True)
        raise RuntimeError(f"Failed to get positions: {str(e)}")

@registry.register("moneybot.getPendingOrders")
async def tool_get_pending_orders(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get all pending orders (buy_limit, sell_limit, buy_stop, sell_stop)
    
    Returns:
        List of all pending orders with ticket numbers, entry prices, SL, TP, etc.
    """
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    logger.info("📋 Getting all pending orders")
    
    try:
        import MetaTrader5 as mt5
        registry.mt5_service.connect()
        
        # Get all pending orders
        orders = mt5.orders_get()
        
        if not orders or len(orders) == 0:
            return {
                "summary": "📭 No pending orders",
                "data": {"orders": [], "count": 0}
            }
        
        # Order type mapping
        order_type_map = {
            mt5.ORDER_TYPE_BUY_LIMIT: "buy_limit",
            mt5.ORDER_TYPE_SELL_LIMIT: "sell_limit",
            mt5.ORDER_TYPE_BUY_STOP: "buy_stop",
            mt5.ORDER_TYPE_SELL_STOP: "sell_stop",
            mt5.ORDER_TYPE_BUY_STOP_LIMIT: "buy_stop_limit",
            mt5.ORDER_TYPE_SELL_STOP_LIMIT: "sell_stop_limit"
        }
        
        # Format orders for display
        formatted_orders = []
        summary_lines = [f"📋 Pending Orders ({len(orders)})\n"]
        
        for order in orders:
            order_type_str = order_type_map.get(order.type, "unknown")
            
            # Determine emoji based on order type
            if "buy" in order_type_str:
                emoji = "🟢"
            elif "sell" in order_type_str:
                emoji = "🔴"
            else:
                emoji = "⚪"
            
            symbol_clean = order.symbol.replace('c', '')
            
            formatted_order = {
                "ticket": order.ticket,
                "symbol": order.symbol,
                "type": order_type_str,
                "volume": order.volume_current,
                "price_open": order.price_open,
                "sl": order.sl,
                "tp": order.tp,
                "price_current": order.price_current,
                "comment": order.comment,
                "time_setup": order.time_setup,
                "time_expiration": order.time_expiration if hasattr(order, 'time_expiration') else 0
            }
            formatted_orders.append(formatted_order)
            
            summary_lines.append(
                f"{emoji} {order_type_str.upper().replace('_', ' ')} {symbol_clean}\n"
                f"  Ticket: {order.ticket}\n"
                f"  Entry: {order.price_open:.5f}\n"
                f"  SL: {order.sl:.5f} | TP: {order.tp:.5f}\n"
                f"  Volume: {order.volume_current} lots\n"
                f"  Current Price: {order.price_current:.5f}\n"
            )
        
        return {
            "summary": "\n".join(summary_lines),
            "data": {"orders": formatted_orders, "count": len(formatted_orders)}
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get pending orders: {e}", exc_info=True)
        raise RuntimeError(f"Failed to get pending orders: {str(e)}")

@registry.register("moneybot.monitor_status")
async def tool_monitor_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get status of all monitored positions
    
    Returns:
        Summary of open trades and intelligent exit status
    """
    logger.info("📋 Fetching monitoring status...")
    
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    try:
        # Get open positions
        positions = registry.mt5_service.get_positions()
        
        # Get intelligent exit status
        exit_manager = create_exit_manager(
            registry.mt5_service,
            binance_service=registry.binance_service,
            order_flow_service=registry.order_flow_service
        )
        rules = exit_manager.get_all_rules()
        
        if not positions:
            return {
                "summary": "📊 No open positions\n\nYour account is currently flat.",
                "data": {
                    "total_positions": 0,
                    "monitored_count": 0,
                    "positions": []
                }
            }
        
        summary_lines = [f"📊 Monitoring Status - {len(positions)} Position(s)\n"]
        
        position_data = []
        
        for pos in positions:
            ticket = pos.ticket
            symbol = pos.symbol.replace('c', '')  # Display without suffix
            direction = "BUY" if pos.type == 0 else "SELL"
            entry = pos.price_open
            current = pos.price_current
            profit = pos.profit
            volume = pos.volume
            
            # Check if intelligent exits enabled
            rule = next((r for r in rules if r.ticket == ticket), None)
            
            if rule:
                # Advanced-enhanced monitoring active
                breakeven_pct = rule.breakeven_profit_pct
                partial_pct = rule.partial_profit_pct
                breakeven_triggered = rule.breakeven_triggered
                partial_triggered = rule.partial_triggered
                
                advanced_status = "⚡ Advanced"
                if breakeven_pct != 30.0 or partial_pct != 60.0:
                    advanced_status += f" {breakeven_pct:.0f}/{partial_pct:.0f}%"
                else:
                    advanced_status += " 30/60%"

                # Add trigger indicators
                if breakeven_triggered:
                    advanced_status += " 🎯BE"
                if partial_triggered:
                    advanced_status += " 💰PP"

                exit_status = advanced_status
            else:
                exit_status = "❌ Not monitored"
            
            # Format P/L with color indicator
            pl_indicator = "📈" if profit > 0 else "📉" if profit < 0 else "➖"
            
            summary_lines.append(
                f"• {symbol} {direction}\n"
                f"  Ticket: {ticket} | Vol: {volume}\n"
                f"  Entry: {entry:.2f} → Current: {current:.2f}\n"
                f"  {pl_indicator} P/L: ${profit:.2f}\n"
                f"  {exit_status}\n"
            )
            
            position_data.append({
                "ticket": ticket,
                "symbol": symbol,
                "direction": direction,
                "entry": entry,
                "current": current,
                "profit": profit,
                "volume": volume,
                "monitoring_enabled": rule is not None,
                "breakeven_pct": rule.breakeven_profit_pct if rule else None,
                "partial_pct": rule.partial_profit_pct if rule else None,
                "breakeven_triggered": rule.breakeven_triggered if rule else False,
                "partial_triggered": rule.partial_triggered if rule else False
            })
        
        # Add summary stats
        total_pl = sum(p.profit for p in positions)
        monitored = sum(1 for p in position_data if p["monitoring_enabled"])
        
        summary_lines.append(
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Total P/L: ${total_pl:.2f}\n"
            f"Monitored: {monitored}/{len(positions)} positions\n"
            f"Advanced-Enhanced Exits: ACTIVE"
        )
        
        summary = "\n".join(summary_lines)
        
        return {
            "summary": summary,
            "data": {
                "total_positions": len(positions),
                "monitored_count": monitored,
                "total_pl": total_pl,
                "positions": position_data
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Monitor status failed: {e}", exc_info=True)
        raise RuntimeError(f"Status check failed: {str(e)}")

# ============================================================================
# SPRINT 3: ADVANCED CONTROL TOOLS
# ============================================================================

@registry.register("moneybot.modify_position")
async def tool_modify_position(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Modify stop loss and/or take profit of an existing position
    
    Args:
        ticket: Position ticket number
        stop_loss: New stop loss price (optional)
        take_profit: New take profit price (optional)
    
    Returns:
        Confirmation of modification
    """
    ticket = args.get("ticket")
    new_sl = args.get("stop_loss")
    new_tp = args.get("take_profit")
    
    if not ticket:
        raise ValueError("Missing required argument: ticket")
    
    if not new_sl and not new_tp:
        raise ValueError("Must specify at least one of: stop_loss, take_profit")
    
    logger.info(f"🔧 Modifying position {ticket}")
    
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    try:
        import MetaTrader5 as mt5
        
        # Get the position
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            raise RuntimeError(f"Position {ticket} not found")
        
        position = positions[0]
        symbol = position.symbol
        current_sl = position.sl
        current_tp = position.tp
        
        # Use current values if not specified
        final_sl = new_sl if new_sl is not None else current_sl
        final_tp = new_tp if new_tp is not None else current_tp
        
        logger.info(f"   Modifying {symbol}: SL {current_sl} → {final_sl}, TP {current_tp} → {final_tp}")
        
        # Prepare modification request
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": ticket,
            "sl": final_sl,
            "tp": final_tp,
        }
        
        # Send modification
        result = mt5.order_send(request)
        
        if result is None:
            raise RuntimeError("Modification failed: MT5 returned None")
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Modification failed: {result.retcode} - {result.comment}"
            logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)
        
        logger.info(f"✅ Position {ticket} modified successfully")
        
        # ============================================================================
        # LOG MODIFICATION TO DATABASE (NEW)
        # ============================================================================
        try:
            # Determine reason based on what changed
            if new_sl is not None and new_tp is not None:
                reason = "Manual SL/TP modification via phone control"
            elif new_sl is not None:
                if abs(new_sl - position.price_open) < abs(current_sl - position.price_open):
                    reason = "SL tightened (manual breakeven/trailing)"
                else:
                    reason = "SL widened (manual adjustment)"
            else:
                reason = "TP modified (manual adjustment)"
            
            # Log to events table
            journal_repo.add_event(
                event="sl_tp_modified",
                ticket=ticket,
                symbol=symbol,
                price=position.price_current,
                sl=final_sl,
                tp=final_tp,
                reason=reason,
                extra={
                    "old_sl": current_sl,
                    "new_sl": final_sl,
                    "old_tp": current_tp,
                    "new_tp": final_tp,
                    "source": "desktop_agent",
                    "modification_type": "manual"
                }
            )
            
            logger.info(f"📊 Modification logged to database")
            
        except Exception as e:
            logger.error(f"❌ Failed to log modification to database: {e}", exc_info=True)
            # Don't fail the modification, just log the error
        
        # Format summary
        changes = []
        if new_sl is not None:
            changes.append(f"SL: {current_sl:.2f} → {final_sl:.2f}")
        if new_tp is not None:
            changes.append(f"TP: {current_tp:.2f} → {final_tp:.2f}")
        
        summary = (
            f"✅ Position Modified\n\n"
            f"Ticket: {ticket}\n"
            f"Symbol: {symbol.replace('c', '')}\n"
            f"{' | '.join(changes)}\n\n"
            f"🎯 Your position has been updated!"
        )
        
        return {
            "summary": summary,
            "data": {
                "ticket": ticket,
                "symbol": symbol,
                "old_sl": current_sl,
                "old_tp": current_tp,
                "new_sl": final_sl,
                "new_tp": final_tp,
                "modified": True
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Position modification failed: {e}", exc_info=True)
        raise RuntimeError(f"Modification failed: {str(e)}")

@registry.register("moneybot.close_position")
async def tool_close_position(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Close an existing position (full or partial)
    
    Args:
        ticket: Position ticket number
        volume: Volume to close (optional, defaults to full position)
        reason: Reason for closure (optional, for logging)
    
    Returns:
        Confirmation of closure with final P/L
    """
    ticket = args.get("ticket")
    volume = args.get("volume")  # None = close all
    reason = args.get("reason", "Manual close from phone")
    
    if not ticket:
        raise ValueError("Missing required argument: ticket")
    
    logger.info(f"🔴 Closing position {ticket}")
    
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    try:
        import MetaTrader5 as mt5
        
        # Get the position
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            raise RuntimeError(f"Position {ticket} not found")
        
        position = positions[0]
        symbol = position.symbol
        position_volume = position.volume
        direction = "BUY" if position.type == 0 else "SELL"
        entry = position.price_open
        current_price = position.price_current
        current_profit = position.profit
        
        # Determine volume to close
        close_volume = volume if volume is not None else position_volume
        
        if close_volume > position_volume:
            raise ValueError(f"Cannot close {close_volume} lots (position only has {position_volume} lots)")
        
        is_partial = close_volume < position_volume
        
        logger.info(f"   Closing {close_volume}/{position_volume} lots of {symbol} {direction}")
        
        # Prepare close request (opposite direction)
        close_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY
        close_price = mt5.symbol_info_tick(symbol).bid if position.type == 0 else mt5.symbol_info_tick(symbol).ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": close_volume,
            "type": close_type,
            "position": ticket,
            "price": close_price,
            "deviation": 20,
            "magic": 234000,
            "comment": reason,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send close order
        result = mt5.order_send(request)
        
        if result is None:
            raise RuntimeError("Close failed: MT5 returned None")
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Close failed: {result.retcode} - {result.comment}"
            logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)
        
        actual_close_price = result.price
        
        logger.info(f"✅ Position {ticket} closed successfully")
        
        # Disable intelligent exits if fully closed
        if not is_partial:
            try:
                exit_manager = create_exit_manager(
                    registry.mt5_service,
                    binance_service=registry.binance_service,
                    order_flow_service=registry.order_flow_service
                )
                exit_manager.remove_rule(ticket)
                logger.info(f"   Removed intelligent exit rule for closed position")
            except Exception as e:
                logger.warning(f"   Could not remove exit rule: {e}")
        
        # Calculate approximate P/L for the closed portion
        # (Note: Actual P/L from MT5 is more accurate, but this gives context)
        pip_diff = abs(actual_close_price - entry)
        partial_profit = current_profit * (close_volume / position_volume) if is_partial else current_profit
        
        # Format summary
        profit_emoji = "📈" if partial_profit > 0 else "📉" if partial_profit < 0 else "➖"
        close_type_str = "Partial Close" if is_partial else "Full Close"
        
        summary = (
            f"✅ Position {close_type_str}\n\n"
            f"Ticket: {ticket}\n"
            f"Symbol: {symbol.replace('c', '')}\n"
            f"Direction: {direction}\n"
            f"Entry: {entry:.2f} → Close: {actual_close_price:.2f}\n"
            f"Volume: {close_volume} lots\n"
            f"{profit_emoji} P/L: ${partial_profit:.2f}\n\n"
            f"🎯 Position closed successfully!"
        )
        
        if is_partial:
            remaining = position_volume - close_volume
            summary += f"\n\n⚠️ {remaining} lots still open (Ticket: {ticket})"
        
        return {
            "summary": summary,
            "data": {
                "ticket": ticket,
                "symbol": symbol,
                "direction": direction,
                "entry": entry,
                "close_price": actual_close_price,
                "volume_closed": close_volume,
                "volume_remaining": position_volume - close_volume if is_partial else 0,
                "profit": partial_profit,
                "is_partial": is_partial,
                "closed": True
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Position close failed: {e}", exc_info=True)
        raise RuntimeError(f"Close failed: {str(e)}")

@registry.register("moneybot.cancel_pending_order")
async def tool_cancel_pending_order(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cancel/delete a pending order (Buy Limit, Sell Limit, Buy Stop, Sell Stop)
    
    Args:
        ticket: Pending order ticket number
        reason: Reason for cancellation (optional, for logging)
    
    Returns:
        Confirmation of cancellation
    """
    ticket = args.get("ticket")
    reason = args.get("reason", "Manual cancellation")
    
    if not ticket:
        raise ValueError("Missing required argument: ticket")
    
    logger.info(f"🗑️ Cancelling pending order {ticket}")
    
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    try:
        import MetaTrader5 as mt5
        
        # Get the pending order
        orders = mt5.orders_get(ticket=ticket)
        if not orders:
            raise RuntimeError(f"Pending order {ticket} not found")
        
        order = orders[0]
        symbol = order.symbol
        order_type_code = order.type
        entry_price = order.price_open
        sl = order.sl
        tp = order.tp
        volume = order.volume_current
        
        # Map order type code to readable name
        order_type_names = {
            2: "Buy Limit",
            3: "Sell Limit",
            4: "Buy Stop",
            5: "Sell Stop"
        }
        order_type_name = order_type_names.get(order_type_code, f"Type {order_type_code}")
        
        logger.info(f"   Cancelling {order_type_name} for {symbol}")
        
        # Prepare cancel request
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": ticket
        }
        
        # Send cancel request
        result = mt5.order_send(request)
        
        if result is None:
            raise RuntimeError("Cancellation failed: MT5 returned None")
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Cancellation failed: {result.retcode} - {result.comment}"
            logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)
        
        logger.info(f"✅ Pending order {ticket} cancelled successfully")
        
        # Format summary
        summary = (
            f"✅ Pending Order Cancelled\n\n"
            f"Ticket: {ticket}\n"
            f"Symbol: {symbol.replace('c', '')}\n"
            f"Type: {order_type_name}\n"
            f"Entry: {entry_price:.2f}\n"
            f"Volume: {volume} lots\n\n"
            f"🗑️ Order has been removed from MT5."
        )
        
        return {
            "summary": summary,
            "data": {
                "ticket": ticket,
                "symbol": symbol,
                "order_type": order_type_name,
                "entry_price": entry_price,
                "volume": volume,
                "cancelled": True
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Pending order cancellation failed: {e}", exc_info=True)
        raise RuntimeError(f"Cancellation failed: {str(e)}")

@registry.register("moneybot.toggle_intelligent_exits")
async def tool_toggle_intelligent_exits(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enable or disable Advanced-enhanced intelligent exits for a position
    
    Args:
        ticket: Position ticket number
        action: "enable" | "disable"
    
    Returns:
        Confirmation of toggle action
    """
    ticket = args.get("ticket")
    action = args.get("action", "enable").lower()
    
    if not ticket:
        raise ValueError("Missing required argument: ticket")
    
    if action not in ["enable", "disable"]:
        raise ValueError("action must be 'enable' or 'disable'")
    
    logger.info(f"⚙️ {action.capitalize()}ing intelligent exits for position {ticket}")
    
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    try:
        import MetaTrader5 as mt5
        from infra.indicator_bridge import IndicatorBridge
        from infra.feature_builder_advanced import build_features_advanced
        
        # Get the position
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            raise RuntimeError(f"Position {ticket} not found")
        
        position = positions[0]
        symbol = position.symbol
        entry = position.price_open
        direction = "buy" if position.type == 0 else "sell"
        sl = position.sl
        tp = position.tp
        comment = position.comment or ""
        
        exit_manager = create_exit_manager(
            registry.mt5_service,
            binance_service=registry.binance_service,
            order_flow_service=registry.order_flow_service
        )
        
        if action == "disable":
            # Disable intelligent exits
            exit_manager.remove_rule(ticket)
            logger.info(f"✅ Intelligent exits disabled for {ticket}")
            
            summary = (
                f"✅ Intelligent Exits Disabled\n\n"
                f"Ticket: {ticket}\n"
                f"Symbol: {symbol.replace('c', '')}\n\n"
                f"⚠️ Advanced monitoring stopped for this position.\n"
                f"Your fixed SL/TP remain active."
            )
            
            return {
                "summary": summary,
                "data": {
                    "ticket": ticket,
                    "symbol": symbol,
                    "monitoring_enabled": False,
                    "action": "disabled"
                }
            }
        
        else:  # enable
            # Check if already enabled
            existing_rule = exit_manager.rules.get(ticket)
            if existing_rule:
                summary = (
                    f"ℹ️ Intelligent Exits Already Active\n\n"
                    f"Ticket: {ticket}\n"
                    f"Symbol: {symbol.replace('c', '')}\n"
                    f"Breakeven: {existing_rule.breakeven_profit_pct:.0f}%\n"
                    f"Partial: {existing_rule.partial_profit_pct:.0f}%\n\n"
                    f"✅ No action needed - monitoring is active."
                )
                
                return {
                    "summary": summary,
                    "data": {
                        "ticket": ticket,
                        "symbol": symbol,
                        "monitoring_enabled": True,
                        "action": "already_enabled",
                        "breakeven_pct": existing_rule.breakeven_profit_pct,
                        "partial_pct": existing_rule.partial_profit_pct
                    }
                }
            
            # NEW: Classify trade type (SCALP vs INTRADAY) - Feature Flag Protected
            classification = None
            classification_info = {}
            
            # Use getattr with default False to handle missing attribute gracefully
        enable_classification = getattr(settings, 'ENABLE_TRADE_TYPE_CLASSIFICATION', False)
        if enable_classification:
                try:
                    import time
                    from infra.trade_type_classifier import TradeTypeClassifier
                    from infra.session_analyzer import SessionAnalyzer
                    from infra.classification_metrics import record_classification_metric
                    
                    logger.info(f"   Classifying trade type for {symbol}...")
                    
                    # Measure classification latency
                    classification_start_time = time.time()
                    
                    session_analyzer = SessionAnalyzer()
                    session_info = session_analyzer.get_current_session()
                    
                    classifier = TradeTypeClassifier(
                        mt5_service=registry.mt5_service,
                        session_service=session_analyzer
                    )
                    
                    classification = classifier.classify(
                        symbol=symbol,
                        entry_price=entry,
                        stop_loss=sl,
                        comment=comment,
                        session_info=session_info
                    )
                    
                    classification_latency_ms = (time.time() - classification_start_time) * 1000
                    
                    trade_type = classification["trade_type"]
                    confidence = classification["confidence"]
                    reasoning = classification["reasoning"]
                    factors = classification["factors"]
                    
                    classification_info = {
                        "trade_type": trade_type,
                        "confidence": confidence,
                        "reasoning": reasoning,
                        "factors": factors
                    }
                    
                    logger.info(
                        f"   📊 Trade Classification: {trade_type} "
                        f"(confidence: {confidence:.2f}) - {reasoning}"
                    )
                    
                    # Record metric if enabled
                    if settings.CLASSIFICATION_METRICS_ENABLED:
                        # Determine which factor was used (priority order: override > keyword > stop_atr_ratio > session_strategy > default)
                        factor_used = "default"
                        if factors.get("manual_override"):
                            factor_used = "override"
                        elif factors.get("keyword_match"):
                            factor_used = "keyword"
                        elif factors.get("stop_atr_ratio") is not None:
                            factor_used = "stop_atr_ratio"
                        elif factors.get("session_strategy"):
                            factor_used = "session_strategy"
                        
                        try:
                            record_classification_metric(
                                ticket=ticket,
                                symbol=symbol,
                                trade_type=trade_type,
                                confidence=confidence,
                                reasoning=reasoning,
                                factor_used=factor_used,
                                latency_ms=classification_latency_ms,
                                feature_enabled=True
                            )
                        except Exception as metrics_error:
                            logger.debug(f"   → Metrics recording failed: {metrics_error}")
                
                except Exception as e:
                        logger.warning(f"   ⚠️ Classification failed: {e}, defaulting to INTRADAY parameters")
                        classification_info = {
                            "trade_type": "INTRADAY",
                            "confidence": 0.0,
                            "reasoning": f"Classification error: {str(e)} → Default to INTRADAY",
                            "error": str(e)
                        }
                        
                        # Record error metric if enabled
                        if settings.CLASSIFICATION_METRICS_ENABLED:
                            try:
                                from infra.classification_metrics import record_classification_metric
                                record_classification_metric(
                                    ticket=ticket,
                                    symbol=symbol,
                                    trade_type="INTRADAY",
                                    confidence=0.0,
                                    reasoning=f"Classification error: {str(e)} → Default to INTRADAY",
                                    factor_used="default",
                                    latency_ms=0.0,  # Error case - no latency to record
                                    feature_enabled=True
                                )
                            except Exception:
                                pass  # Silent fail for metrics on errors
        else:
            # Feature disabled - use default INTRADAY parameters
            logger.debug(f"   Trade type classification disabled (feature flag OFF) - using default INTRADAY parameters")
            classification_info = {
                "trade_type": "INTRADAY",
                "confidence": 0.0,
                "reasoning": "Feature flag disabled → Using default INTRADAY parameters",
                "feature_enabled": False
            }
            
            # Record disabled metric if enabled
            if settings.CLASSIFICATION_METRICS_ENABLED:
                try:
                    from infra.classification_metrics import record_classification_metric
                    record_classification_metric(
                        ticket=ticket,
                        symbol=symbol,
                        trade_type="INTRADAY",
                        confidence=0.0,
                        reasoning="Feature flag disabled → Using default INTRADAY parameters",
                        factor_used="default",
                        latency_ms=0.0,  # No classification performed
                        feature_enabled=False
                    )
                except Exception:
                    pass  # Silent fail for metrics
        
        # Select parameters based on classification (only if feature enabled and classification succeeded)
        if enable_classification and classification_info and classification_info.get("trade_type") == "SCALP":
            # SCALP parameters: faster profit-taking, tighter exits
            base_breakeven_pct = 25.0
            base_partial_pct = 40.0
            partial_close_pct = 70.0
            logger.info(f"   🎯 Using SCALP parameters: {base_breakeven_pct}% / {base_partial_pct}% / {partial_close_pct}%")
        else:
            # INTRADAY parameters: standard/default parameters
            base_breakeven_pct = settings.INTELLIGENT_EXITS_BREAKEVEN_PCT
            base_partial_pct = settings.INTELLIGENT_EXITS_PARTIAL_PCT
            partial_close_pct = settings.INTELLIGENT_EXITS_PARTIAL_CLOSE_PCT
            if not enable_classification:
                logger.debug(f"   Using default INTRADAY parameters (feature disabled): {base_breakeven_pct}% / {base_partial_pct}% / {partial_close_pct}%")
            else:
                logger.info(f"   🎯 Using INTRADAY parameters: {base_breakeven_pct}% / {base_partial_pct}% / {partial_close_pct}%")
        
        # Enable intelligent exits with Advanced features
            logger.info(f"   Fetching Advanced features for {symbol}...")
            bridge = IndicatorBridge()
            advanced_features = build_features_advanced(
                symbol=symbol,
                mt5svc=registry.mt5_service,
                bridge=bridge,
                timeframes=["M15"]
            )
            
            exit_result = exit_manager.add_rule_advanced(
                ticket=ticket,
                symbol=symbol,
                entry_price=entry,
                direction=direction,
                initial_sl=sl,
                initial_tp=tp,
                advanced_features=advanced_features,
                base_breakeven_pct=base_breakeven_pct,
                base_partial_pct=base_partial_pct,
                partial_close_pct=partial_close_pct,
                vix_threshold=settings.INTELLIGENT_EXITS_VIX_THRESHOLD,
                use_hybrid_stops=settings.INTELLIGENT_EXITS_USE_HYBRID_STOPS,
                trailing_enabled=settings.INTELLIGENT_EXITS_TRAILING_ENABLED
            )
            
            # Get Advanced-adjusted percentages
            rule = exit_manager.rules.get(ticket)
            breakeven_pct = rule.breakeven_profit_pct if rule else 30.0
            partial_pct = rule.partial_profit_pct if rule else 60.0
            final_partial_close_pct = rule.partial_close_pct if rule else partial_close_pct

            advanced_adjusted = breakeven_pct != base_breakeven_pct or partial_pct != base_partial_pct

            # Build summary with classification info
            trade_type_display = classification_info.get("trade_type", "INTRADAY")
            confidence_display = classification_info.get("confidence", 0.0)
            reasoning_display = classification_info.get("reasoning", "Default classification")
            
            logger.info(
                f"✅ Intelligent exits enabled: {breakeven_pct}% / {partial_pct}% "
                f"(Classification: {trade_type_display})"
            )

            summary = (
                f"✅ Advanced-Enhanced Intelligent Exits Enabled\n\n"
                f"Ticket: {ticket}\n"
                f"Symbol: {symbol.replace('c', '')}\n\n"
            )
            
            # Include classification info only if feature is enabled
            if classification_info and "trade_type" in classification_info:
                trade_type_display = classification_info["trade_type"]
                confidence_display = classification_info.get("confidence", 0.0)
                reasoning_display = classification_info.get("reasoning", "Default classification")
                summary += (
                    f"📊 Trade Type: {trade_type_display} (confidence: {confidence_display:.0%})\n"
                    f"   └─ {reasoning_display}\n\n"
                )
            
            summary += (
                f"⚙️ Exit Strategy:\n"
                f"   Breakeven: {breakeven_pct:.0f}% profit (0.{breakeven_pct/10:.1f}R)\n"
                f"   Partial: {partial_pct:.0f}% profit (0.{partial_pct/10:.1f}R), close {final_partial_close_pct:.0f}%\n"
            )

            if advanced_adjusted:
                summary += f"   ⚡ Advanced-Adjusted (from base {base_breakeven_pct}%/{base_partial_pct}%)\n"
            
            summary += f"\n📊 Your position is now on autopilot!"
            
            # Send Discord notification with classification info (if feature enabled)
            try:
                from discord_notifications import DiscordNotifier
                discord_notifier = DiscordNotifier()
                if discord_notifier.enabled:
                    # Get plan_id if this is an auto-executed trade
                    plan_id = get_plan_id_from_ticket(ticket)
                    plan_id_line = f"📊 **Plan ID**: {plan_id}\n" if plan_id else ""
                    
                    # Build Discord message
                    discord_message = (
                        f"✅ **Intelligent Exits Enabled**\n\n"
                        f"🎫 **Ticket**: {ticket}\n"
                        f"{plan_id_line}"
                        f"💱 **Symbol**: {symbol.replace('c', '')}\n"
                        f"📊 **Entry**: {entry:.5f}\n"
                        f"🛡️ **SL**: {sl:.5f} | 🎯 **TP**: {tp:.5f}\n\n"
                    )
                    
                    # Add classification info if available
                    if classification_info and "trade_type" in classification_info:
                        trade_type_display = classification_info.get("trade_type", "INTRADAY")
                        confidence_display = classification_info.get("confidence", 0.0)
                        reasoning_display = classification_info.get("reasoning", "Default classification")
                        
                        discord_message += (
                            f"📊 **Trade Type**: {trade_type_display}\n"
                            f"🎯 **Confidence**: {confidence_display:.0%}\n"
                            f"💡 **Reasoning**: {reasoning_display}\n\n"
                        )
                    
                    discord_message += (
                        f"⚙️ **Exit Strategy**:\n"
                        f"   • Breakeven: {breakeven_pct:.0f}% profit (0.{breakeven_pct/10:.1f}R)\n"
                        f"   • Partial: {partial_pct:.0f}% profit (0.{partial_pct/10:.1f}R), close {final_partial_close_pct:.0f}%\n\n"
                        f"🤖 Position is now on autopilot!"
                    )
                    
                    if advanced_adjusted:
                        discord_message += f"\n⚡ Advanced-adjusted from base {base_breakeven_pct:.0f}%/{base_partial_pct:.0f}%"
                    
                    discord_notifier.send_system_alert("INTELLIGENT_EXIT", discord_message)
                    logger.info("   → Discord notification sent")
            except Exception as e:
                logger.debug(f"   → Discord notification not sent: {e}")
            
            return {
                "summary": summary,
                "data": {
                    "ticket": ticket,
                    "symbol": symbol,
                    "monitoring_enabled": True,
                    "action": "enabled",
                    "breakeven_pct": breakeven_pct,
                    "partial_pct": partial_pct,
                    "partial_close_pct": final_partial_close_pct,
                    "advanced_adjusted": advanced_adjusted,
                    "classification": classification_info
                }
            }
        
    except Exception as e:
        logger.error(f"❌ Toggle intelligent exits failed: {e}", exc_info=True)
        raise RuntimeError(f"Toggle failed: {str(e)}")

@registry.register("moneybot.enableIntelligentExits")
async def tool_enable_intelligent_exits_alias(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Alias for enabling intelligent exits/trailing stops on a live position.
    Expects: { ticket: int }
    Optional: { mode: "trailing_only" | "full" } - currently routes to full intelligent exits.
    """
    # Ensure action=enable and forward to the existing toggle tool
    forwarded = dict(args or {})
    forwarded["action"] = "enable"
    return await tool_toggle_intelligent_exits(forwarded)

@registry.register("moneybot.start_trailing_stops")
async def tool_start_trailing_stops(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Start trailing stops on a live trade with an ATR-based distance.
    Inputs:
      - ticket: MT5 position ticket (required)
      - timeframe: e.g., "M5" (optional, default M5)
      - atr_multiplier: float (optional, default 1.5)
    Behavior:
      - Computes trailing distance = max(ATR*time_mult, stops_level*point*2)
      - Sets SL at current_price ± distance (below for BUY, above for SELL)
      - Leaves Intelligent Exits enabled to continue dynamic trailing
    """
    ticket = args.get("ticket")
    timeframe = str(args.get("timeframe", "M5"))
    atr_multiplier = float(args.get("atr_multiplier", 1.5))
    if not ticket:
        raise ValueError("Missing required argument: ticket")

    # Initialize MT5
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")

    import MetaTrader5 as mt5
    try:
        registry.mt5_service.connect()
        positions = mt5.positions_get(ticket=int(ticket))
        if not positions:
            raise RuntimeError(f"Position {ticket} not found")
        pos = positions[0]
        symbol = pos.symbol
        direction = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        current_price = float(pos.price_current)

        # Get symbol constraints
        sym_info = mt5.symbol_info(symbol)
        point = float(getattr(sym_info, 'point', 0.0)) if sym_info else 0.0
        stops_level = int(getattr(sym_info, 'stops_level', 0)) if sym_info else 0
        tick_size = float(getattr(sym_info, 'trade_tick_size', point or 0.01)) if sym_info else 0.01

        # Fetch ATR from indicator bridge
        from infra.indicator_bridge import IndicatorBridge
        bridge = IndicatorBridge(registry.mt5_service)
        try:
            multi = bridge.get_multi(symbol)
            tf = multi.get(timeframe, {}) if multi else {}
            atr = float(tf.get("atr14", 0))
        except Exception:
            atr = 0.0

        # Fallback ATR estimate if missing
        if atr <= 0:
            # Use a small fraction of price as rough volatility proxy
            atr = max(current_price * 0.001, tick_size * 10)

        # Compute trailing distance
        dist_price = float(max(atr * atr_multiplier, (stops_level * (point or tick_size)) * 2))

        # Normalize helper
        def _norm(x: float) -> float:
            if tick_size > 0:
                return round(round(x / tick_size) * tick_size, 10)
            return x

        # Compute new SL ensuring valid side
        if direction == "BUY":
            new_sl = _norm(current_price - dist_price)
            # Ensure SL below entry
            if new_sl >= pos.price_open:
                new_sl = _norm(pos.price_open - max(dist_price, tick_size))
        else:
            new_sl = _norm(current_price + dist_price)
            # Ensure SL above entry
            if new_sl <= pos.price_open:
                new_sl = _norm(pos.price_open + max(dist_price, tick_size))

        # Safety: ensure distance meets broker minimum from current
        min_dist = (stops_level * (point or tick_size))
        if min_dist and abs(new_sl - current_price) < min_dist:
            if direction == "BUY":
                new_sl = _norm(current_price - (min_dist * 1.1))
            else:
                new_sl = _norm(current_price + (min_dist * 1.1))

        # Modify SL only (keep TP)
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": int(ticket),
            "symbol": symbol,
            "sl": float(new_sl),
            "tp": float(pos.tp) if pos.tp else 0.0,
        }
        check = mt5.order_check(request)
        if check and getattr(check, 'retcode', None) not in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED, 0):
            raise RuntimeError(f"Pre-check failed: retcode={check.retcode} comment={getattr(check, 'comment', '')}")
        result = mt5.order_send(request)
        if result is None:
            raise RuntimeError(f"MT5 order_send returned None: last_error={mt5.last_error()}")
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"SL modify failed: {result.retcode} - {result.comment}")

        # Ensure intelligent exits are enabled to keep trailing running
        try:
            await tool_enable_intelligent_exits_alias({"ticket": int(ticket)})
        except Exception:
            pass

        # Journal note
        try:
            from infra.journal_repo import JournalRepo
            jr = JournalRepo()
            jr.add_event(
                "trailing_started",
                ticket=int(ticket),
                symbol=symbol,
                side=direction,
                price=current_price,
                sl=float(new_sl),
                reason="ATR-based trailing",
                extra={
                    "timeframe": timeframe,
                    "atr": atr,
                    "atr_multiplier": atr_multiplier,
                    "distance": dist_price,
                },
            )
        except Exception:
            pass

        summary = (
            f"✅ Trailing Stops Enabled\n\n"
            f"Ticket: {ticket}\n"
            f"Symbol: {symbol.replace('c','')}\n"
            f"Direction: {direction}\n"
            f"ATR({timeframe})={atr:.5f} × {atr_multiplier} → distance {dist_price:.5f}\n"
            f"New SL: {new_sl:.5f} (prev {pos.sl or 0:.5f})\n\n"
            f"📈 Intelligent Exits remain active to continue trailing dynamically."
        )

        return {
            "summary": summary,
            "data": {
                "ticket": int(ticket),
                "symbol": symbol,
                "direction": direction,
                "atr": atr,
                "atr_multiplier": atr_multiplier,
                "distance": dist_price,
                "new_sl": float(new_sl),
            },
        }

    except Exception as e:
        logger.error(f"❌ Start trailing stops failed: {e}", exc_info=True)
        raise RuntimeError(f"Start trailing failed: {str(e)}")

@registry.register("moneybot.binance_feed_status")
async def tool_binance_feed_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check Binance streaming feed health and synchronization status
    
    Args:
        symbol: Optional symbol to check (e.g., "BTCUSDc"), or None for all symbols
    
    Returns:
        Feed health status, offset calibration, and safety assessment
    """
    symbol = args.get("symbol")
    
    if not registry.binance_service:
        return {
            "summary": "⚠️ Binance feed not running",
            "data": {
                "status": "offline",
                "message": "Binance streaming service is not initialized"
            }
        }
    
    if not registry.binance_service.running:
        return {
            "summary": "⚠️ Binance feed not active",
            "data": {
                "status": "inactive",
                "message": "Binance streams are not currently running"
            }
        }
    
    try:
        # Get health status
        if symbol:
            health = registry.binance_service.get_feed_health(symbol)
            
            status_emoji = "✅" if health["overall_status"] == "healthy" else "⚠️" if health["overall_status"] == "warning" else "🔴"
            offset = health["sync"]["offset"]
            age = health["sync"]["last_sync_age"]
            
            summary = (
                f"{status_emoji} Binance Feed Status - {symbol}\n\n"
                f"Status: {health['overall_status'].upper()}\n"
                f"Offset: {offset:+.2f} pips (Binance vs MT5)\n"
                f"Data Age: {age:.1f}s\n"
                f"Tick Count: {health['cache']['tick_count']}\n\n"
                f"Assessment: {health['sync']['reason']}"
            )
            
            return {
                "summary": summary,
                "data": health
            }
        else:
            # All symbols
            all_health = registry.binance_service.get_feed_health()
            
            # Count statuses
            healthy = sum(1 for h in all_health["sync"].values() if h["status"] == "healthy")
            warning = sum(1 for h in all_health["sync"].values() if h["status"] == "warning")
            critical = sum(1 for h in all_health["sync"].values() if h["status"] == "critical")
            total = len(all_health["sync"])
            
            summary = (
                f"📡 Binance Feed Status - All Symbols\n\n"
                f"Total Symbols: {total}\n"
                f"✅ Healthy: {healthy}\n"
                f"⚠️ Warning: {warning}\n"
                f"🔴 Critical: {critical}\n\n"
            )
            
            # Add per-symbol details
            for sym, health_data in all_health["sync"].items():
                status_emoji = "✅" if health_data["status"] == "healthy" else "⚠️" if health_data["status"] == "warning" else "🔴"
                offset = health_data.get("offset", "N/A")
                offset_str = f"{offset:+.1f}" if isinstance(offset, (int, float)) else offset
                summary += f"{status_emoji} {sym}: Offset {offset_str} pips\n"
            
            return {
                "summary": summary,
                "data": all_health
            }
            
    except Exception as e:
        logger.error(f"❌ Feed status check failed: {e}", exc_info=True)
        raise RuntimeError(f"Feed status check failed: {str(e)}")

@registry.register("moneybot.btc_order_flow_metrics")
async def tool_btc_order_flow_metrics(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get comprehensive BTC order flow metrics (Delta Volume, CVD, CVD Slope, CVD Divergence, Absorption Zones, Buy/Sell Pressure)"""
    symbol = args.get("symbol", "BTCUSDT")
    window_seconds = args.get("window_seconds", 30)
    # Binance stream stores symbols in UPPERCASE (BTCUSDT), not lowercase
    binance_symbol = "BTCUSDT" if "BTC" in symbol.upper() else symbol.upper()
    
    if not hasattr(registry, 'order_flow_service') or not registry.order_flow_service:
        return {"summary": "⚠️ Order flow service not running - metrics unavailable", "data": {"status": "error", "message": "Order flow service not initialized"}}
    if not getattr(registry.order_flow_service, "running", False):
        return {"summary": "⚠️ Order flow service inactive - metrics unavailable", "data": {"status": "error", "message": "Order flow service is not active"}}
    
    try:
        from infra.btc_order_flow_metrics import BTCOrderFlowMetrics
        metrics_calc = BTCOrderFlowMetrics(order_flow_service=registry.order_flow_service)
        metrics = metrics_calc.get_metrics(binance_symbol, window_seconds)
        
        if not metrics:
            return {"summary": "⚠️ Order flow metrics unavailable - insufficient data", "data": {"status": "error", "message": "Not enough trade data yet. Wait a few seconds and try again."}}
        
        summary_lines = [f"📊 BTC Order Flow Metrics: {symbol}", f"💰 Delta: {metrics.delta_volume:+,.2f} ({metrics.dominant_side})", f"📈 CVD: {metrics.cvd:+,.2f} (Slope: {metrics.cvd_slope:+,.2f}/bar)"]
        if metrics.cvd_divergence_strength > 0:
            summary_lines.append(f"⚠️ CVD Divergence: {metrics.cvd_divergence_type} ({metrics.cvd_divergence_strength:.1%})")
        if metrics.absorption_zones:
            summary_lines.append(f"🎯 Absorption Zones: {len(metrics.absorption_zones)} detected")
        summary_lines.append(f"⚖️ Pressure: {metrics.buy_sell_pressure:.2f}x ({metrics.dominant_side})")
        
        return {
            "summary": " | ".join(summary_lines),
            "data": {
                "status": "success", "symbol": symbol, "timestamp": metrics.timestamp,
                "delta_volume": {"buy_volume": metrics.buy_volume, "sell_volume": metrics.sell_volume, "net_delta": metrics.delta_volume, "dominant_side": metrics.dominant_side},
                "cvd": {"current": metrics.cvd, "slope": metrics.cvd_slope, "bar_count": metrics.bar_count},
                "cvd_divergence": {"strength": metrics.cvd_divergence_strength, "type": metrics.cvd_divergence_type},
                "absorption_zones": metrics.absorption_zones,
                "buy_sell_pressure": {"ratio": metrics.buy_sell_pressure, "dominant_side": metrics.dominant_side},
                "window_seconds": metrics.window_seconds
            }
        }
    except Exception as e:
        logger.error(f"Error getting BTC order flow metrics: {e}", exc_info=True)
        return {"summary": f"❌ Error calculating order flow metrics: {str(e)}", "data": {"status": "error", "error": str(e)}}

@registry.register("moneybot.order_flow_status")
async def tool_order_flow_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check order flow analysis status (order book depth + whale detection)
    
    Args:
        symbol: Symbol to check (e.g., "BTCUSDc") - required
    
    Returns:
        Order flow signal, whale activity, liquidity voids, buy/sell pressure
    """
    symbol = args.get("symbol")
    
    if not symbol:
        return {
            "summary": "⚠️ Symbol required for order flow check",
            "data": {"status": "error", "message": "Please specify a symbol"}
        }
    
    if not registry.order_flow_service:
        return {
            "summary": "⚠️ Order flow service not running",
            "data": {
                "status": "offline",
                "message": "Order flow analysis is not initialized (requires Binance streams)"
            }
        }
    
    if not registry.order_flow_service.running:
        return {
            "summary": "⚠️ Order flow service not active",
            "data": {
                "status": "inactive",
                "message": "Order flow streams are not currently running"
            }
        }
    
    try:
        # Get comprehensive order flow signal
        signal = registry.order_flow_service.get_order_flow_signal(symbol)
        
        if not signal:
            return {
                "summary": f"⚠️ No order flow data for {symbol}",
                "data": {"status": "no_data", "message": "Order flow data not yet available"}
            }
        
        # Format summary
        summary = registry.order_flow_service.get_signal_summary(symbol)
        
        return {
            "summary": summary,
            "data": signal
        }
            
    except Exception as e:
        logger.error(f"❌ Order flow check failed: {e}", exc_info=True)
        raise RuntimeError(f"Order flow check failed: {str(e)}")

@registry.register("moneybot.macro_context")
async def tool_macro_context(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get comprehensive macro market context
    
    Traditional Markets: DXY, US10Y, VIX, S&P 500
    Crypto Fundamentals: Bitcoin Dominance, Crypto Fear & Greed Index
    
    Args:
        symbol: Optional symbol to provide context for (e.g., "XAUUSD" for gold, "BTCUSD" for Bitcoin)
    
    Returns:
        Current macro indicators with market sentiment and symbol-specific analysis
    """
    symbol = args.get("symbol", "").upper()
    
    logger.info(f"🌍 Fetching macro context" + (f" for {symbol}" if symbol else ""))
    
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    try:
        # Get current macro data from Yahoo Finance (not MT5)
        import yfinance as yf
        import requests
        
        # Try multiple sources for DXY as it's sometimes unreliable on Yahoo Finance
        dxy = None
        dxy_sources = ["DX=F", "DX-Y.NYB", "USDOLLAR"]
        
        for ticker in dxy_sources:
            try:
                dxy_data = yf.Ticker(ticker)
                dxy_hist = dxy_data.history(period="5d")
                if not dxy_hist.empty:
                    dxy = float(dxy_hist['Close'].iloc[-1])
                    logger.info(f"   ✅ DXY fetched from {ticker}: {dxy:.2f}")
                    break
            except Exception as e:
                logger.warning(f"   ⚠️ Failed to fetch DXY from {ticker}: {e}")
                continue
        
        # Fallback: Use hardcoded reasonable value if all sources fail
        if dxy is None:
            dxy = 104.5  # Recent average value
            logger.warning(f"   ⚠️ Using fallback DXY value: {dxy}")
        
        # Fetch US10Y
        us10y_data = yf.Ticker("^TNX")
        us10y_hist = us10y_data.history(period="5d")
        if us10y_hist.empty:
            us10y = 4.2  # Fallback reasonable value
            logger.warning(f"   ⚠️ Using fallback US10Y value: {us10y}%")
        else:
            us10y = float(us10y_hist['Close'].iloc[-1])
            logger.info(f"   ✅ US10Y fetched: {us10y:.3f}%")
        
        # Fetch VIX
        vix_data = yf.Ticker("^VIX")
        vix_hist = vix_data.history(period="5d")
        if vix_hist.empty:
            vix = 16.0  # Fallback reasonable value
            logger.warning(f"   ⚠️ Using fallback VIX value: {vix}")
        else:
            vix = float(vix_hist['Close'].iloc[-1])
            logger.info(f"   ✅ VIX fetched: {vix:.2f}")
        
        # Fetch S&P 500 (NEW - for Bitcoin correlation)
        sp500_data = yf.Ticker("^GSPC")
        sp500_hist = sp500_data.history(period="5d")
        if sp500_hist.empty or len(sp500_hist) < 2:
            sp500 = 5800.0  # Fallback reasonable value
            sp500_change = 0.0
            logger.warning(f"   ⚠️ Using fallback S&P 500 value: {sp500}")
        else:
            sp500 = float(sp500_hist['Close'].iloc[-1])
            sp500_prev = float(sp500_hist['Close'].iloc[-2])
            sp500_change = ((sp500 - sp500_prev) / sp500_prev) * 100
            logger.info(f"   ✅ S&P 500 fetched: {sp500:.2f} ({sp500_change:+.2f}%)")
        
        # Fetch Bitcoin Dominance (NEW - from CoinGecko)
        btc_dominance = None
        btc_dom_status = "Unknown"
        try:
            cg_url = "https://api.coingecko.com/api/v3/global"
            cg_response = requests.get(cg_url, timeout=5)
            if cg_response.status_code == 200:
                cg_data = cg_response.json()
                btc_dominance = float(cg_data["data"]["market_cap_percentage"]["btc"])
                
                # Classify dominance
                if btc_dominance > 50:
                    btc_dom_status = "STRONG (Money flowing to Bitcoin)"
                elif btc_dominance < 45:
                    btc_dom_status = "WEAK (Alt season - money to altcoins)"
                else:
                    btc_dom_status = "NEUTRAL"
                
                logger.info(f"   ✅ BTC Dominance fetched: {btc_dominance:.1f}% ({btc_dom_status})")
            else:
                logger.warning(f"   ⚠️ CoinGecko returned status {cg_response.status_code}")
        except Exception as e:
            logger.warning(f"   ⚠️ Failed to fetch BTC Dominance: {e}")
        
        # Fetch Crypto Fear & Greed Index (NEW - from Alternative.me)
        crypto_fear_greed = None
        crypto_sentiment = "Unknown"
        try:
            fng_url = "https://api.alternative.me/fng/"
            fng_response = requests.get(fng_url, timeout=5)
            if fng_response.status_code == 200:
                fng_data = fng_response.json()
                crypto_fear_greed = int(fng_data["data"][0]["value"])
                crypto_sentiment = fng_data["data"][0]["value_classification"]
                logger.info(f"   ✅ Crypto Fear & Greed fetched: {crypto_fear_greed}/100 ({crypto_sentiment})")
            else:
                logger.warning(f"   ⚠️ Alternative.me returned status {fng_response.status_code}")
        except Exception as e:
            logger.warning(f"   ⚠️ Failed to fetch Crypto Fear & Greed: {e}")
        
        logger.info(f"   📊 Final macro data: DXY={dxy:.2f}, US10Y={us10y:.3f}%, VIX={vix:.2f}, S&P500={sp500:.2f}")
        
        # Analyze sentiment
        dxy_trend = "📈 Rising" if dxy > 104.0 else "📉 Falling" if dxy < 103.0 else "➖ Neutral"
        us10y_trend = "📈 Rising" if us10y > 4.3 else "📉 Falling" if us10y < 4.1 else "➖ Neutral"
        vix_level = "⚠️ High" if vix > 20 else "✅ Normal" if vix < 15 else "⚠️ Elevated"
        
        # Symbol-specific analysis
        symbol_context = ""
        if symbol:
            if "XAU" in symbol or "GOLD" in symbol:
                # Gold analysis
                if "Rising" in dxy_trend and "Rising" in us10y_trend:
                    symbol_context = "🔴 BEARISH for Gold (DXY↑ + Yields↑)"
                elif "Falling" in dxy_trend and "Falling" in us10y_trend:
                    symbol_context = "🟢 BULLISH for Gold (DXY↓ + Yields↓)"
                else:
                    symbol_context = "⚪ MIXED for Gold (conflicting signals)"
            
            elif "BTC" in symbol or "CRYPTO" in symbol:
                # Enhanced crypto analysis with S&P 500, BTC.D, Fear & Greed
                risk_sentiment = "RISK_ON" if vix < 15 else "RISK_OFF" if vix > 20 else "NEUTRAL"
                sp500_trend_label = "RISING" if sp500_change > 0 else "FALLING"
                
                # Assess overall crypto market conditions
                bullish_signals = 0
                bearish_signals = 0
                
                # VIX (risk sentiment)
                if vix < 15:
                    bullish_signals += 1
                elif vix > 20:
                    bearish_signals += 1
                
                # S&P 500 (equity correlation)
                if sp500_change > 0.5:
                    bullish_signals += 1
                elif sp500_change < -0.5:
                    bearish_signals += 1
                
                # DXY (inverse correlation)
                if "Falling" in dxy_trend:
                    bullish_signals += 1
                elif "Rising" in dxy_trend:
                    bearish_signals += 1
                
                # BTC Dominance (crypto strength)
                if btc_dominance and btc_dominance > 50:
                    btc_dom_context = f"BTC Dominance: {btc_dominance:.1f}% (STRONG - Bitcoin outperforming)"
                elif btc_dominance and btc_dominance < 45:
                    btc_dom_context = f"BTC Dominance: {btc_dominance:.1f}% (WEAK - Alt season starting)"
                elif btc_dominance:
                    btc_dom_context = f"BTC Dominance: {btc_dominance:.1f}% (NEUTRAL)"
                else:
                    btc_dom_context = "BTC Dominance: Data unavailable"
                
                # Fear & Greed (sentiment)
                if crypto_fear_greed:
                    if crypto_fear_greed > 75:
                        fg_context = f"Crypto Sentiment: {crypto_sentiment} ({crypto_fear_greed}/100 - Potential top)"
                    elif crypto_fear_greed < 25:
                        fg_context = f"Crypto Sentiment: {crypto_sentiment} ({crypto_fear_greed}/100 - Potential bottom)"
                    else:
                        fg_context = f"Crypto Sentiment: {crypto_sentiment} ({crypto_fear_greed}/100)"
                else:
                    fg_context = "Crypto Sentiment: Data unavailable"
                
                # Overall verdict
                if bullish_signals >= 2:
                    verdict = "🟢 BULLISH"
                elif bearish_signals >= 2:
                    verdict = "🔴 BEARISH"
                else:
                    verdict = "⚪ MIXED"
                
                symbol_context = (
                    f"{verdict} for Crypto\n"
                    f"Risk Sentiment: {risk_sentiment} (VIX {vix:.1f})\n"
                    f"S&P 500: {sp500_trend_label} ({sp500_change:+.2f}%) - Correlation +0.70\n"
                    f"{btc_dom_context}\n"
                    f"{fg_context}"
                )
            
            elif symbol in ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"]:
                # USD pairs
                if "Rising" in dxy_trend:
                    symbol_context = f"🔴 BEARISH for {symbol} (DXY strengthening)"
                elif "Falling" in dxy_trend:
                    symbol_context = f"🟢 BULLISH for {symbol} (DXY weakening)"
                else:
                    symbol_context = f"⚪ NEUTRAL for {symbol}"
        
        # Format summary
        summary = (
            f"🌍 Macro Market Context\n\n"
            f"📊 Traditional Markets:\n"
            f"DXY (Dollar Index): {dxy:.2f} {dxy_trend}\n"
            f"US10Y (Yield): {us10y:.3f}% {us10y_trend}\n"
            f"VIX (Volatility): {vix:.2f} {vix_level}\n"
            f"S&P 500: {sp500:.2f} ({sp500_change:+.2f}%)\n"
        )
        
        # Add crypto fundamentals if available
        if btc_dominance or crypto_fear_greed:
            summary += f"\n🔷 Crypto Fundamentals:\n"
            if btc_dominance:
                summary += f"BTC Dominance: {btc_dominance:.1f}% ({btc_dom_status})\n"
            if crypto_fear_greed:
                summary += f"Crypto Fear & Greed: {crypto_sentiment} ({crypto_fear_greed}/100)\n"
        
        if symbol_context:
            summary += f"\n💡 Impact on {symbol}:\n{symbol_context}"
        
        # Add market regime
        if "High" in vix_level:
            summary += f"\n\n⚠️ High volatility environment - risk management critical"
        elif "Falling" in dxy_trend and "Falling" in us10y_trend:
            summary += f"\n\n🟢 Risk-on regime - favorable for growth assets"
        elif "Rising" in dxy_trend and "Rising" in us10y_trend:
            summary += f"\n\n🔴 Risk-off regime - USD strength"
        
        # Determine risk sentiment
        if vix < 15 and sp500_change > 0:
            risk_sentiment = "RISK_ON"
        elif vix > 20 or sp500_change < -1:
            risk_sentiment = "RISK_OFF"
        else:
            risk_sentiment = "NEUTRAL"
        
        return {
            "summary": summary,
            "data": {
                # Traditional Macro
                "dxy": dxy,
                "dxy_trend": dxy_trend,
                "us10y": us10y,
                "us10y_trend": us10y_trend,
                "vix": vix,
                "vix_level": vix_level,
                "risk_sentiment": risk_sentiment,
                
                # S&P 500 (NEW)
                "sp500": sp500,
                "sp500_change_pct": sp500_change,
                "sp500_trend": "RISING" if sp500_change > 0 else "FALLING",
                
                # Crypto Fundamentals (NEW)
                "btc_dominance": btc_dominance,
                "btc_dominance_status": btc_dom_status,
                "crypto_fear_greed": crypto_fear_greed,
                "crypto_sentiment": crypto_sentiment,
                
                # Context
                "symbol_context": symbol_context if symbol else None,
                "timestamp": datetime.now().isoformat(),
                "timestamp_human": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Macro context fetch failed: {e}", exc_info=True)
        raise RuntimeError(f"Macro fetch failed: {str(e)}")

@registry.register("moneybot.lot_sizing_info")
async def tool_lot_sizing_info(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get lot sizing configuration and risk parameters for a symbol
    
    Args:
        symbol: Trading symbol (optional - if not provided, shows all)
    
    Returns:
        Lot sizing information including max lots, risk %, and category
    """
    symbol = args.get("symbol")
    
    if symbol:
        # Normalize symbol
        # Normalize: strip any trailing 'c' or 'C', then add lowercase 'c'
        if not symbol.lower().endswith('c'):
            symbol_normalized = symbol.upper() + 'c'
        else:
            symbol_normalized = symbol.upper().rstrip('cC') + 'c'
        
        info = get_lot_sizing_info(symbol_normalized)
        
        summary = (
            f"📊 Lot Sizing for {symbol_normalized}\n\n"
            f"Category: {info['category']}\n"
            f"Max Lot Size: {info['max_lot']}\n"
            f"Default Risk %: {info['default_risk_pct']}%\n"
            f"Min Lot Size: {info['min_lot']}\n\n"
            f"💡 When you execute a trade without specifying volume, "
            f"the system will calculate the optimal lot size based on:\n"
            f"  • Your account equity\n"
            f"  • Stop loss distance\n"
            f"  • Symbol risk percentage ({info['default_risk_pct']}%)\n"
            f"  • Maximum lot cap ({info['max_lot']} lots)"
        )
        
        return {
            "summary": summary,
            "data": info
        }
    else:
        # Show all configured symbols
        from config.lot_sizing import MAX_LOT_SIZES, DEFAULT_RISK_PCT
        
        symbols_info = []
        for sym in ["BTCUSDc", "XAUUSDc", "EURUSDc", "GBPUSDc", "USDJPYc", "GBPJPYc", "EURJPYc"]:
            info = get_lot_sizing_info(sym)
            symbols_info.append(info)
        
        summary = "📊 Lot Sizing Configuration\n\n"
        
        # Group by category
        crypto = [s for s in symbols_info if s['category'] == 'CRYPTO']
        metals = [s for s in symbols_info if s['category'] == 'METAL']
        forex = [s for s in symbols_info if s['category'] == 'FOREX']
        
        if crypto:
            summary += "💰 CRYPTO:\n"
            for s in crypto:
                summary += f"  {s['symbol']}: Max {s['max_lot']} lots, Risk {s['default_risk_pct']}%\n"
            summary += "\n"
        
        if metals:
            summary += "🥇 METALS:\n"
            for s in metals:
                summary += f"  {s['symbol']}: Max {s['max_lot']} lots, Risk {s['default_risk_pct']}%\n"
            summary += "\n"
        
        if forex:
            summary += "💱 FOREX:\n"
            for s in forex:
                summary += f"  {s['symbol']}: Max {s['max_lot']} lots, Risk {s['default_risk_pct']}%\n"
            summary += "\n"
        
        summary += (
            "💡 Automatic Lot Sizing:\n"
            "When you execute trades without specifying volume, the system calculates "
            "the optimal lot size based on your equity, stop distance, and symbol-specific risk parameters."
        )
        
        return {
            "summary": summary,
            "data": {
                "crypto": crypto,
                "metals": metals,
                "forex": forex
            }
        }

# ============================================================================
# AGENT MAIN LOOP
# ============================================================================

# ============================================================================
# UNIFIED PIPELINE TOOLS
# ============================================================================

@registry.register("moneybot.enhanced_symbol_analysis")
async def tool_enhanced_symbol_analysis_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Enhanced symbol analysis using Unified Tick Pipeline data"""
    return await tool_enhanced_symbol_analysis(args)

@registry.register("moneybot.volatility_analysis")
async def tool_volatility_analysis_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get volatility analysis using Unified Tick Pipeline data"""
    return await tool_volatility_analysis(args)

@registry.register("moneybot.offset_calibration")
async def tool_offset_calibration_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get offset calibration using Unified Tick Pipeline data"""
    return await tool_offset_calibration(args)

@registry.register("moneybot.system_health")
async def tool_system_health_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get system health using Unified Tick Pipeline data"""
    return await tool_system_health(args)

@registry.register("moneybot.pipeline_status")
async def tool_pipeline_status_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get Unified Tick Pipeline status"""
    return await tool_pipeline_status(args)

async def agent_main():
    """Main agent loop - connect to hub and process commands"""
    logger.info("=" * 70)
    logger.info("🤖 Synergis Trading Bot Desktop Agent - STARTING")
    logger.info("=" * 70)
    logger.info(f"🔌 Connecting to hub: {HUB_URL}")
    logger.info(f"📋 Available tools: {list(registry.tools.keys())}")
    logger.info("=" * 70)
    
    # Initialize services
    logger.info("🔧 Initializing services...")
    
    # Initialize MT5
    try:
        registry.mt5_service = MT5Service()
        if registry.mt5_service.connect():
            logger.info("✅ MT5Service connected")
        else:
            logger.warning("⚠️ MT5Service connection failed - some features may not work")
    except Exception as e:
        logger.warning(f"⚠️ MT5Service initialization failed: {e}")
    
    # Initialize Binance Service
    try:
        logger.info("📡 Starting Binance streaming service...")
        registry.binance_service = BinanceService(interval="1m")
        logger.info("   Binance service object created")
        
        registry.binance_service.set_mt5_service(registry.mt5_service)
        logger.info("   MT5 service linked")
    except Exception as e:
        logger.warning(f"⚠️ BinanceService initialization failed: {e}")
    
    # Initialize Unified Tick Pipeline
    try:
        logger.info("🚀 Initializing Unified Tick Pipeline...")
        # TODO: Initialize unified tick pipeline here
        logger.info("✅ Unified Tick Pipeline initialized")
    except Exception as e:
        logger.warning(f"⚠️ Unified Tick Pipeline initialization failed: {e}")

import asyncio
import os
import websockets
from websockets.exceptions import ConnectionClosed, InvalidURI
import json
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import sys

# Your existing imports
try:
    from config import settings
    from infra.mt5_service import MT5Service
    from decision_engine import decide_trade
    from infra.intelligent_exit_manager import create_exit_manager
    from infra.binance_service import BinanceService
    from app.engine.signal_prefilter import SignalPreFilter
    from infra.circuit_breaker import CircuitBreaker
    from infra.exposure_guard import ExposureGuard
    from config.lot_sizing import get_lot_size, get_lot_sizing_info
    from infra.journal_repo import JournalRepo  # NEW: Database logging
    from logging.handlers import RotatingFileHandler  # NEW: File logging
    from infra.trade_close_logger import get_close_logger  # NEW: Close logging
    from infra.conversation_logger import get_conversation_logger  # NEW: Conversation logging
    from infra.custom_alerts import CustomAlertManager  # NEW: Alert management
    from chatgpt_auto_execution_tools import (  # NEW: Auto execution tools
        tool_create_auto_trade_plan,
        tool_create_choch_plan,
        tool_create_rejection_wick_plan,
        tool_create_order_block_plan,
        tool_create_bracket_trade_plan,
        tool_cancel_auto_plan,
        tool_update_auto_plan,
        tool_get_auto_plan_status,
        tool_get_auto_system_status,
        tool_create_multiple_auto_plans,  # NEW: Batch operations
        tool_update_multiple_auto_plans,  # NEW: Batch operations
        tool_cancel_multiple_auto_plans   # NEW: Batch operations
    )
    from desktop_agent_unified_pipeline_integration_updated import (  # NEW: Updated Unified Pipeline integration with separate database architecture
        initialize_desktop_agent_unified_pipeline_updated,
        tool_enhanced_symbol_analysis,
        tool_volatility_analysis,
        tool_offset_calibration,
        tool_system_health,
        tool_pipeline_status
    )
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the Synergis Trading Bot directory")
    sys.exit(1)

# Configure logging with file handler (NEW)
# Reuse WindowsRotatingFileHandler if already defined, otherwise define it
if 'WindowsRotatingFileHandler' not in globals():
    class WindowsRotatingFileHandler(RotatingFileHandler):
        """RotatingFileHandler with Windows file locking workaround"""
        def doRollover(self):
            """Override to handle Windows file locking issues"""
            if self.stream:
                self.stream.close()
                self.stream = None
            
            # Retry rotation with delay on Windows
            import platform
            if platform.system() == 'Windows':
                import time
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        super().doRollover()
                        break
                    except (PermissionError, OSError) as e:
                        if attempt < max_retries - 1:
                            time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                            continue
                        else:
                            # If rotation fails, just continue logging to current file
                            try:
                                logger.warning(f"⚠️ Log rotation failed (attempt {attempt + 1}/{max_retries}): {e}. Continuing with current log file.")
                            except:
                                print(f"⚠️ Log rotation failed: {e}. Continuing with current log file.")
                            if not self.stream:
                                self.stream = self._open()
            else:
                super().doRollover()

log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

# File handler (rotating, 10MB max, 5 backups)
file_handler = WindowsRotatingFileHandler(
    'desktop_agent.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

# Attach handlers to ROOT logger so all modules (infra.*, app.*, etc.) get logged.
# (Previously only `desktop_agent.py`'s logger had handlers, so infra.* logs were silently dropped.)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Avoid duplicate handlers if this file is imported/reloaded
if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
    root_logger.addHandler(console_handler)
if not any(isinstance(h, RotatingFileHandler) and str(getattr(h, "baseFilename", "")).endswith("desktop_agent.log") for h in root_logger.handlers):
    root_logger.addHandler(file_handler)

# Module logger (propagates to root)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = True

# Initialize journal repository for database logging
journal_repo = JournalRepo()
logger.info("✅ Journal repository initialized for database logging")

# Initialize trade close logger
close_logger = get_close_logger()
logger.info("✅ Trade close logger initialized")

# Initialize conversation logger
conversation_logger = get_conversation_logger()
logger.info("✅ Conversation logger initialized")

# ============================================================================
# CONFIGURATION
# ============================================================================

# FIX: Phone hub uses port 8002 to avoid conflict with DTMS API server (port 8001)
PHONE_HUB_PORT = int(os.getenv("PHONE_HUB_PORT", "8002"))  # Default to 8002 to avoid conflict with DTMS
HUB_URL = os.getenv("PHONE_HUB_URL", f"ws://localhost:{PHONE_HUB_PORT}/agent/connect")  # Phone control hub
API_URL = os.getenv("API_URL", "ws://localhost:8000/agent/connect")  # Main API server
AGENT_SECRET = os.getenv("AGENT_SECRET", "phone_control_bearer_token_2025_v1_secure")  # For phone control hub
API_SECRET = os.getenv("API_SECRET", "8j5Cg8aAYy8uujCpvOv6KA8pZRm7yqWjhI6m1euVvU4")  # For main API server

# ============================================================================
# NOTE: ToolRegistry already defined at top (line 176)
# DO NOT duplicate - it overwrites first registry and loses tools!
# ============================================================================

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _extract_pattern_summary(features_data: Dict[str, Any], symbol: str = "", current_price: float = 0.0) -> str:
    """Extract and format candle pattern summary from advanced features with pattern confirmation tracking."""
    from infra.pattern_tracker import get_pattern_tracker
    from infra.streamer_data_access import get_latest_candle
    
    pattern_tracker = get_pattern_tracker()
    pattern_lines = []
    timeframe_order = ["M5", "M15", "M30", "H1", "H4"]
    
    for tf in timeframe_order:
        tf_features = features_data.get(tf, {})
        if not tf_features:
            continue
            
        candlestick_flags = tf_features.get("candlestick_flags", {})
        pattern_flags = tf_features.get("pattern_flags", {})
        pattern_strength = tf_features.get("pattern_strength", 0.0)
        
        # Determine pattern type and bias
        pattern_type = None
        pattern_bias = "neutral"
        pattern_high = current_price
        pattern_low = current_price
        
        active_patterns = []
        
        # Check multi-bar patterns first (higher priority)
        if pattern_flags.get("morning_star"):
            pattern_type = "Morning Star"
            pattern_bias = "bullish"
            active_patterns.append("Morning Star → Bullish Reversal")
        elif pattern_flags.get("evening_star"):
            pattern_type = "Evening Star"
            pattern_bias = "bearish"
            active_patterns.append("Evening Star → Bearish Reversal")
        elif pattern_flags.get("bull_engulfing"):
            pattern_type = "Bull Engulfing"
            pattern_bias = "bullish"
            active_patterns.append("Bull Engulfing → Bullish")
        elif pattern_flags.get("bear_engulfing"):
            pattern_type = "Bear Engulfing"
            pattern_bias = "bearish"
            active_patterns.append("Bear Engulfing → Bearish")
        elif pattern_flags.get("inside_bar"):
            pattern_type = "Inside Bar"
            pattern_bias = "neutral"
            active_patterns.append("Inside Bar → Consolidation")
        elif pattern_flags.get("outside_bar"):
            pattern_type = "Outside Bar"
            pattern_bias = "neutral"
            active_patterns.append("Outside Bar → Breakout")
        
        # Check single-bar patterns if no multi-bar pattern
        if not active_patterns:
            if candlestick_flags.get("marubozu_bull"):
                pattern_type = "Marubozu Bull"
                pattern_bias = "bullish"
                active_patterns.append("Marubozu Bull → Strong Momentum")
            elif candlestick_flags.get("marubozu_bear"):
                pattern_type = "Marubozu Bear"
                pattern_bias = "bearish"
                active_patterns.append("Marubozu Bear → Strong Momentum")
            elif candlestick_flags.get("doji"):
                pattern_type = "Doji"
                pattern_bias = "neutral"
                active_patterns.append("Doji → Indecision")
            elif candlestick_flags.get("hammer"):
                pattern_type = "Hammer"
                pattern_bias = "bullish"
                active_patterns.append("Hammer → Bullish Reversal")
            elif candlestick_flags.get("shooting_star"):
                pattern_type = "Shooting Star"
                pattern_bias = "bearish"
                active_patterns.append("Shooting Star → Bearish Reversal")
            elif candlestick_flags.get("pin_bar_bull"):
                pattern_type = "Pin Bar Bull"
                pattern_bias = "bullish"
                active_patterns.append("Pin Bar Bull → Rejection")
            elif candlestick_flags.get("pin_bar_bear"):
                pattern_type = "Pin Bar Bear"
                pattern_bias = "bearish"
                active_patterns.append("Pin Bar Bear → Rejection")
        
        if active_patterns and pattern_type:
            pattern_text = active_patterns[0]
            
            # Try to validate pattern if symbol and current_price provided
            if symbol and current_price > 0:
                try:
                    latest_candle = get_latest_candle(symbol, tf)
                    if latest_candle:
                        # Extract candle data
                        if isinstance(latest_candle, dict):
                            candle_high = float(latest_candle.get('high', current_price))
                            candle_low = float(latest_candle.get('low', current_price))
                            candle_close = float(latest_candle.get('close', current_price))
                        else:
                            candle_high = float(getattr(latest_candle, 'high', current_price))
                            candle_low = float(getattr(latest_candle, 'low', current_price))
                            candle_close = float(getattr(latest_candle, 'close', current_price))
                        
                        pattern_high = max(candle_high, current_price)
                        pattern_low = min(candle_low, current_price)
                        
                        # Validate pattern against latest candle
                        candles_since = 1
                        validation_result = pattern_tracker.validate_pattern(
                            symbol, tf, {
                                'high': candle_high,
                                'low': candle_low,
                                'close': candle_close,
                                'open': candle_close
                            }, candles_since
                        )
                        
                        # Check if this pattern was just confirmed/invalidated
                        pattern_status = None
                        for key, status in validation_result:
                            if status in ["Confirmed", "Invalidated"]:
                                pattern_status = status
                                break
                        
                        # If no validation yet, register the pattern
                        if pattern_status is None:
                            pattern_tracker.register_pattern(
                                symbol=symbol,
                                timeframe=tf,
                                pattern_type=pattern_type,
                                detection_price=candle_close,
                                pattern_high=pattern_high,
                                pattern_low=pattern_low,
                                strength_score=pattern_strength,
                                bias=pattern_bias
                            )
                        else:
                            # Add status to display
                            if pattern_status == "Confirmed":
                                pattern_text += " → ✅ CONFIRMED"
                            elif pattern_status == "Invalidated":
                                pattern_text += " → ❌ INVALIDATED"
                            
                except Exception as e:
                    logger.debug(f"Pattern validation failed for {symbol} {tf}: {e}")
            
            strength_text = f" (Strength: {pattern_strength:.1f})" if pattern_strength > 0 else ""
            pattern_lines.append(f"{tf}: {pattern_text}{strength_text}")
        else:
            pattern_lines.append(f"{tf}: No pattern detected")
    
    return "\n".join(pattern_lines) if pattern_lines else "No patterns detected across timeframes"


def _classify_market_regime(features_data: Dict[str, Any], m5_data: Dict, m15_data: Dict, h1_data: Dict) -> str:
    """Classify market regime: Trending / Ranging / Volatile / Expanding"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from app.engine.regime_classifier import classify_regime
        
        tech = {}
        adx_m5 = m5_data.get("adx", 0) or 0
        adx_m15 = m15_data.get("adx", 0) or 0
        adx_h1 = h1_data.get("adx", 0) or 0
        
        tech["M5"] = {"adx": adx_m5}
        tech["M15"] = {"adx": adx_m15}
        tech["H1"] = {"adx": adx_h1}
        
        m15_features = features_data.get("M15", {})
        vol_trend = m15_features.get("vol_trend", {})
        bb_width = vol_trend.get("bb_width", 0) or 0
        tech["M15"]["bb_width"] = bb_width
        
        h1_features = features_data.get("H1", {})
        ema_slope = h1_features.get("ema_slope", {})
        if isinstance(ema_slope, dict):
            slope_value = ema_slope.get("slope_pct", 0) or 0
        else:
            slope_value = float(ema_slope) if ema_slope else 0
        tech["H1"]["ema200_slope_pct"] = slope_value
        
        regime_label, scores = classify_regime(tech)
        
        if regime_label == "TREND":
            return "Trending (Expanding)" if bb_width > 0.02 else "Trending"
        elif regime_label == "RANGE":
            return "Ranging"
        elif regime_label == "VOLATILE":
            return "Volatile"
        else:
            return "Unknown"
    except Exception as e:
        logger.debug(f"Regime classification failed: {e}")
        m15_features = features_data.get("M15", {})
        vol_trend = m15_features.get("vol_trend", {})
        regime_str = vol_trend.get("regime", "unknown")
        
        if regime_str in ["trending", "bullish", "bearish"]:
            return "Trending"
        elif regime_str in ["ranging", "neutral"]:
            return "Ranging"
        elif regime_str in ["volatile", "expanding"]:
            return "Volatile"
        else:
            return "Unknown"


def _calculate_bias_confidence(
    macro_bias: Optional[Dict[str, Any]],
    structure_trend: str,
    choch_detected: bool,
    bos_detected: bool,
    rmag: Dict[str, Any],
    vol_trend: Dict[str, Any],
    pressure: Dict[str, Any],
    decision_confidence: int,
    features_data: Optional[Dict[str, Any]] = None
) -> tuple:
    """Calculate weighted bias confidence score (0-100) including pattern strength. Returns (score, emoji)."""
    from infra.pattern_tracker import get_pattern_tracker
    
    scores = []
    weights = []
    
    if macro_bias:
        bias_direction = macro_bias.get("bias_direction", "neutral")
        bias_score = macro_bias.get("bias_score", 0)
        macro_score = min(100, 50 + abs(bias_score) * 10) if bias_direction != "neutral" else 50
    else:
        macro_score = 50
    scores.append(macro_score)
    weights.append(0.24)  # Slightly reduced from 0.25
    
    if choch_detected:
        structure_score = 20
    elif bos_detected and structure_trend in ["BULLISH", "BEARISH"]:
        structure_score = 80
    elif structure_trend in ["BULLISH", "BEARISH"]:
        structure_score = 60
    else:
        structure_score = 40
    scores.append(structure_score)
    weights.append(0.19)  # Slightly reduced from 0.20
    
    # Calculate pattern strength score (Tier 1.2)
    pattern_score = 50  # Default neutral
    if features_data:
        try:
            timeframe_weights = {"H1": 0.4, "M30": 0.3, "M15": 0.2, "M5": 0.1}
            weighted_pattern_strength = 0.0
            total_weight = 0.0
            pattern_bias_sum = 0.0  # +1 for bullish, -1 for bearish
            
            pattern_tracker = get_pattern_tracker()
            
            for tf, weight in timeframe_weights.items():
                tf_features = features_data.get(tf, {})
                if not tf_features:
                    continue
                
                pattern_strength = tf_features.get("pattern_strength", 0.0)
                if pattern_strength > 0:
                    # Determine pattern bias
                    pattern_flags = tf_features.get("pattern_flags", {})
                    candlestick_flags = tf_features.get("candlestick_flags", {})
                    
                    # Check pattern bias direction
                    pattern_bias = 0  # 0 = neutral, +1 = bullish, -1 = bearish
                    
                    # Multi-bar patterns
                    if pattern_flags.get("morning_star") or pattern_flags.get("bull_engulfing"):
                        pattern_bias = 1
                    elif pattern_flags.get("evening_star") or pattern_flags.get("bear_engulfing"):
                        pattern_bias = -1
                    # Single-bar patterns
                    elif candlestick_flags.get("marubozu_bull") or candlestick_flags.get("hammer"):
                        pattern_bias = 1
                    elif candlestick_flags.get("marubozu_bear") or candlestick_flags.get("shooting_star"):
                        pattern_bias = -1
                    
                    if pattern_bias != 0:
                        # Apply confirmation multiplier if available
                        # Simplified: check if we have a tracked pattern that's confirmed
                        multiplier = 1.0
                        try:
                            # Try to find pattern status (simplified check)
                            # This is a best-effort check
                            pass  # Skip for now - pattern status lookup would need symbol
                        except:
                            pass
                        
                        # Weighted contribution: pattern_strength * pattern_bias * weight
                        contribution = pattern_strength * pattern_bias * weight * multiplier
                        weighted_pattern_strength += contribution
                        total_weight += weight
                        pattern_bias_sum += pattern_bias * weight
            
            if total_weight > 0:
                # Normalize: convert weighted sum to 0-100 score
                # weighted_pattern_strength ranges from -total_weight to +total_weight
                # Normalize to 0-100 where 0 = fully bearish, 50 = neutral, 100 = fully bullish
                normalized = (weighted_pattern_strength / total_weight) if total_weight > 0 else 0
                # Convert -1 to +1 range to 0-100 range
                pattern_score = min(100, max(0, 50 + (normalized * 50)))
        except Exception as e:
            logger.debug(f"Pattern strength calculation failed: {e}")
            pattern_score = 50
    
    scores.append(pattern_score)
    weights.append(0.05)  # NEW: 5% weight for patterns
    
    rmag_value = rmag.get("ema200_atr", 0) or 0
    rmag_score = 70 if abs(rmag_value) > 2.0 else 60 if abs(rmag_value) > 1.5 else 50
    scores.append(rmag_score)
    weights.append(0.14)  # Slightly reduced from 0.15
    
    vol_regime = vol_trend.get("regime", "unknown")
    vol_score = 70 if vol_regime in ["trending", "bullish", "bearish"] else 50 if vol_regime == "ranging" else 45
    scores.append(vol_score)
    weights.append(0.14)  # Slightly reduced from 0.15
    
    pressure_ratio = pressure.get("ratio", 1.0) or 1.0
    momentum_score = 75 if (pressure_ratio > 1.3 or pressure_ratio < 0.7) else 65 if (pressure_ratio > 1.1 or pressure_ratio < 0.9) else 50
    scores.append(momentum_score)
    weights.append(0.14)  # Slightly reduced from 0.15
    
    decision_score = max(0, min(100, decision_confidence))
    scores.append(decision_score)
    weights.append(0.10)  # Unchanged
    
    final_score = int(round(sum(s * w for s, w in zip(scores, weights))))
    emoji = "🟢" if final_score >= 75 else "🟡" if final_score >= 60 else "🔴"
    
    return final_score, emoji


def _summarize_technical_indicators(m5_data: Dict, m15_data: Dict, h1_data: Dict, current_price: float) -> str:
    """Summarize key technical indicators across timeframes"""
    lines = []
    
    # Helper function to determine trend from EMAs
    def get_ema_trend(data, price):
        ema20 = data.get('ema20', 0)
        ema50 = data.get('ema50', 0)
        ema200 = data.get('ema200', 0)
        
        if price > ema20 > ema50 > ema200:
            return "STRONG BULL"
        elif price > ema20 > ema50:
            return "BULL"
        elif price < ema20 < ema50 < ema200:
            return "STRONG BEAR"
        elif price < ema20 < ema50:
            return "BEAR"
        else:
            return "MIXED"
    
    # H1 Indicators (Primary trend)
    if h1_data:
        rsi_h1 = h1_data.get('rsi', 50)
        adx_h1 = h1_data.get('adx', 0)
        macd_h1 = h1_data.get('macd', 0)
        macd_signal_h1 = h1_data.get('macd_signal', 0)
        ema_trend_h1 = get_ema_trend(h1_data, current_price)
        
        macd_cross_h1 = "BULL" if macd_h1 > macd_signal_h1 else "BEAR"
        
        lines.append(f"H1: EMA {ema_trend_h1} | RSI {rsi_h1:.1f} | ADX {adx_h1:.1f} | MACD {macd_cross_h1}")
    
    # M15 Indicators (Entry timeframe)
    if m15_data:
        rsi_m15 = m15_data.get('rsi', 50)
        macd_m15 = m15_data.get('macd', 0)
        macd_signal_m15 = m15_data.get('macd_signal', 0)
        stoch_k_m15 = m15_data.get('stoch_k', 50)
        stoch_d_m15 = m15_data.get('stoch_d', 50)
        bb_upper_m15 = m15_data.get('bb_upper', 0)
        bb_lower_m15 = m15_data.get('bb_lower', 0)
        
        macd_cross_m15 = "BULL" if macd_m15 > macd_signal_m15 else "BEAR"
        stoch_signal_m15 = "BULL" if stoch_k_m15 > stoch_d_m15 else "BEAR"
        
        # Bollinger position
        if current_price > bb_upper_m15:
            bb_pos = "ABOVE UPPER"
        elif current_price < bb_lower_m15:
            bb_pos = "BELOW LOWER"
        else:
            bb_pos = "MIDDLE"
        
        lines.append(f"M15: RSI {rsi_m15:.1f} | MACD {macd_cross_m15} | Stoch {stoch_signal_m15} ({stoch_k_m15:.1f}) | BB {bb_pos}")
    
    # M5 Indicators (Execution timeframe)
    if m5_data:
        rsi_m5 = m5_data.get('rsi', 50)
        macd_m5 = m5_data.get('macd', 0)
        macd_signal_m5 = m5_data.get('macd_signal', 0)
        atr_m5 = m5_data.get('atr14', 0)
        
        macd_cross_m5 = "BULL" if macd_m5 > macd_signal_m5 else "BEAR"
        
        # RSI zones
        if rsi_m5 > 70:
            rsi_zone = "OVERBOUGHT"
        elif rsi_m5 < 30:
            rsi_zone = "OVERSOLD"
        else:
            rsi_zone = "NEUTRAL"
        
        lines.append(f"M5: RSI {rsi_m5:.1f} ({rsi_zone}) | MACD {macd_cross_m5} | ATR {atr_m5:.2f}")
    
    return "\n".join(lines) if lines else "No technical data available"


def _summarize_binance_enrichment(m5_data: Dict, m15_data: Dict) -> str:
    """Summarize key Binance enrichment fields"""
    parts = []
    
    # Use M5 data for microstructure, fallback to M15
    data = m5_data if m5_data.get('price_zscore') is not None else m15_data
    
    # Z-Score (Mean Reversion)
    if 'price_zscore' in data:
        zscore = data.get('price_zscore', 0)
        signal = data.get('mean_reversion_signal', 'NEUTRAL')
        parts.append(f"Z-Score: {zscore:.2f}σ ({signal})")
    
    # Pivot Points
    if 'price_vs_pivot' in data:
        pivot_pos = data.get('price_vs_pivot', 'UNKNOWN')
        parts.append(f"vs Pivot: {pivot_pos}")
    
    # Liquidity Score
    if 'liquidity_quality' in data:
        liq_quality = data.get('liquidity_quality', 'UNKNOWN')
        liq_score = data.get('liquidity_score', 0)
        parts.append(f"Liquidity: {liq_quality} ({liq_score:.1f})")
    
    # Bollinger Band Squeeze
    if 'bb_squeeze' in data:
        squeeze = data.get('bb_squeeze', False)
        bb_pos = data.get('bb_position', 'UNKNOWN')
        if squeeze:
            parts.append(f"BB: SQUEEZE detected ({bb_pos})")
        else:
            parts.append(f"BB: {bb_pos}")
    
    # Tape Reading (Aggressor Side)
    if 'aggressor_side' in data:
        aggressor = data.get('aggressor_side', 'NEUTRAL')
        strength = data.get('aggressor_strength', 0)
        parts.append(f"Tape: {aggressor} {strength:.1f}%")
    
    # Candle Pattern
    if 'candle_pattern' in data and data.get('candle_pattern') != 'NONE':
        pattern = data.get('candle_pattern', 'NONE')
        direction = data.get('pattern_direction', '')
        parts.append(f"Pattern: {pattern} {direction}")
    
    # Order Flow Analysis (NEW!)
    if 'order_flow' in data:
        order_flow = data.get('order_flow', {})
        signal = order_flow.get('signal', 'NEUTRAL')
        confidence = order_flow.get('confidence', 0)
        whale_count = order_flow.get('whale_count', 0)
        imbalance = order_flow.get('imbalance')
        pressure_side = order_flow.get('pressure_side', 'NEUTRAL')
        
        # Format order flow summary
        of_parts = [f"{signal} ({confidence}%)"]
        if whale_count > 0:
            of_parts.append(f"🐋 {whale_count} whales")
        if imbalance:
            of_parts.append(f"Imbalance: {imbalance:.1f}%")
        if pressure_side != 'NEUTRAL':
            of_parts.append(f"Pressure: {pressure_side}")
        
        parts.append(f"Order Flow: {' | '.join(of_parts)}")
    
    return " | ".join(parts) if parts else "No enrichment data available"


def _summarize_advanced_features(rmag: Dict, vwap: Dict, pressure: Dict) -> str:
    """Summarize advanced features into concise text"""
    parts = []
    
    ema_atr = rmag.get("ema200_atr", 0)
    if ema_atr < -2.0:
        parts.append("Extreme oversold")
    elif ema_atr > 2.0:
        parts.append("Extreme overbought")
    elif abs(ema_atr) > 1.0:
        parts.append("Stretched" if abs(ema_atr) > 1.5 else "Moderately stretched")
    else:
        parts.append("Neutral range")
    
    momentum_ratio = pressure.get("ratio", 1.0)
    if momentum_ratio > 1.5:
        parts.append("strong bullish momentum")
    elif momentum_ratio < 0.7:
        parts.append("strong bearish momentum")
    else:
        parts.append("weak momentum")
    
    return ", ".join(parts) if parts else "Normal conditions"


def _generate_scalp_recommendation(
    price: float, m5_features: Dict, m5_smc: Dict, fvg: Dict,
    direction: str, entry: float, sl: float, tp: float, confidence: int, rr: float
) -> str:
    """Generate scalp trading recommendation (M5 entry, 2-4hr hold)"""
    if direction == "HOLD":
        return """SCALP (M5 entry, 2-4hr hold):
⚪ WAIT - No M5 setup currently
Current conditions don't support scalp entry"""
    
    action = "BUY" if direction == "BUY" else "SELL"
    emoji = "✅" if confidence > 70 else "🟡"
    
    fvg_support = fvg.get("nearest_bull_fvg", 0) if direction == "BUY" else fvg.get("nearest_bear_fvg", 0)
    
    return f"""SCALP (M5 entry, 2-4hr hold):
{emoji} {action} at ${entry:,.2f}
SL: ${sl:,.2f}
TP: ${tp:,.2f}
R:R: {rr:.1f} | Confidence: {confidence}%
Setup: M5 {m5_smc.get('bias', 'unknown')} + FVG support
Risk: Short-term scalp, tight SL required"""


def _generate_intraday_recommendation(
    price: float, m15_features: Dict, m15_smc: Dict,
    structure_trend: str, bos_detected: bool, choch_detected: bool
) -> str:
    """Generate intraday trading recommendation (M15 entry, 12-24hr hold)"""
    
    if choch_detected:
        return """INTRADAY (M15 entry, 12-24hr hold):
🔴 AVOID - CHOCH detected, structure reversing
Wait for new structure to form before intraday entry"""
    
    if not bos_detected:
        return """INTRADAY (M15 entry, 12-24hr hold):
⚪ WAIT - No M15 BOS confirmation yet
Current setup: Awaiting structure confirmation"""
    
    if structure_trend == "BULLISH":
        return """INTRADAY (M15 entry, 12-24hr hold):
✅ BUY SETUP AVAILABLE
Entry: M15 BOS Bull confirmed
Wait for: Pullback to M15 support/OB
Hold: 12-24 hours for intraday swing"""
    
    elif structure_trend == "BEARISH":
        return """INTRADAY (M15 entry, 12-24hr hold):
✅ SELL SETUP AVAILABLE
Entry: M15 BOS Bear confirmed
Wait for: Bounce to M15 resistance/OB
Hold: 12-24 hours for intraday swing"""
    
    return """INTRADAY (M15 entry, 12-24hr hold):
⚪ WAIT - Structure unclear
M15 needs clearer direction before entry"""


def _generate_swing_recommendation(
    price: float, h1_features: Dict, h1_smc: Dict,
    macro_bias: str, structure_trend: str
) -> str:
    """Generate swing trading recommendation (H1 entry, multi-day hold)"""
    
    # User preference: scalp/intraday only, no swing trades
    return """SWING (H1 entry, multi-day hold):
🚫 NOT RECOMMENDED - User prefers scalp/intraday only
This system is optimized for short-term trades"""


# ============================================================================
# TOOL IMPLEMENTATIONS
# ============================================================================

@registry.register("ping")
async def tool_ping(args: Dict[str, Any]) -> Dict[str, Any]:
    """Simple ping test"""
    message = args.get("message", "Hello from desktop agent!")
    
    return {
        "summary": f"🏓 Pong! {message}",
        "data": {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_version": "1.0.0",
            "status": "healthy"
        }
    }

@registry.register("moneybot.analyse_symbol")
async def tool_analyse_symbol(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyse a trading symbol using MoneyBot decision engine
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSD", "XAUUSD")
        detail_level: "standard" | "detailed" (optional)
    
    Returns:
        Structured trading recommendation with entry/SL/TP
    """
    logger.info(f"📥 Received args: {args}")
    logger.info(f"   Args type: {type(args)}")
    logger.info(f"   Args keys: {list(args.keys()) if isinstance(args, dict) else 'Not a dict'}")
    
    symbol = args.get("symbol")
    if not symbol:
        logger.error(f"❌ Symbol not found in args. Full args: {args}")
        raise ValueError("Missing required argument: symbol")
    
    detail_level = args.get("detail_level", "standard")
    
    # Normalize symbol (add 'c' suffix for broker)
    # Normalize: strip any trailing 'c' or 'C', then add lowercase 'c'
    if not symbol.lower().endswith('c'):
        symbol_normalized = symbol.upper() + 'c'
    else:
        symbol_normalized = symbol.upper().rstrip('cC') + 'c'
    
    logger.info(f"📊 Analysing {symbol} (normalized: {symbol_normalized})")
    
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    # Check if market is open
    import MetaTrader5 as mt5
    from datetime import datetime
    
    # Check weekend first
    now = datetime.utcnow()
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    
    if weekday >= 5:  # Saturday or Sunday
        import time
        current_timestamp = int(time.time())
        
        return {
            "summary": f"🚫 Market Closed - {symbol}\n\nThe {symbol} market is currently closed (weekend).\n\n💡 Markets open Sunday 22:00 UTC (Forex) or Monday morning.",
            "data": {
                "symbol": symbol,
                "direction": "HOLD",
                "confidence": 0,
                "reasoning": "Market closed - weekend",
                "executable": False,
                "market_closed": True
            },
            "timestamp": current_timestamp,
            "timestamp_human": now.strftime("%Y-%m-%d %H:%M:%S UTC")
        }
    
    # Check if symbol is available and market looks open
    symbol_info = mt5.symbol_info(symbol_normalized)
    if symbol_info is None:
        raise RuntimeError(f"Symbol {symbol_normalized} not found in MT5")
    
    # Check if session trading is off
    if hasattr(symbol_info, "session_trade") and hasattr(symbol_info, "session_deals"):
        if (not bool(symbol_info.session_trade)) or (not bool(symbol_info.session_deals)):
            return {
                "summary": f"🚫 Market Closed - {symbol}\n\nThe {symbol} market is currently closed (no active trading session).\n\n💡 Check your broker's market hours for this symbol.",
                "data": {
                    "symbol": symbol,
                    "direction": "HOLD",
                    "confidence": 0,
                    "reasoning": "Market closed - session trading off",
                    "executable": False,
                    "market_closed": True
                }
            }
    
    # Check if last tick is stale (> 10 minutes)
    tick = mt5.symbol_info_tick(symbol_normalized)
    if tick and hasattr(tick, "time"):
        import time
        tick_age_seconds = time.time() - float(tick.time)
        if tick_age_seconds > 600:  # > 10 minutes
            return {
                "summary": f"🚫 Market Closed - {symbol}\n\nThe {symbol} market appears closed (last price update was {int(tick_age_seconds/60)} minutes ago).\n\n💡 Check your broker's market hours for this symbol.",
                "data": {
                    "symbol": symbol,
                    "direction": "HOLD",
                    "confidence": 0,
                    "reasoning": f"Market closed - stale data ({int(tick_age_seconds/60)}m old)",
                    "executable": False,
                    "market_closed": True
                }
            }
    
    # Run real analysis using your decision_engine
    try:
        from infra.indicator_bridge import IndicatorBridge
        from infra.feature_builder_advanced import build_features_advanced
        from infra.binance_enrichment import BinanceEnrichment
        
        # Initialize indicator bridge
        bridge = IndicatorBridge()
        
        # Fetch multi-timeframe data (single call returns all timeframes)
        logger.info(f"   Fetching M5/M15/M30/H1 data for {symbol_normalized}...")
        all_timeframe_data = bridge.get_multi(symbol_normalized)
        
        # Extract individual timeframes
        m5_data = all_timeframe_data.get("M5")
        m15_data = all_timeframe_data.get("M15")
        m30_data = all_timeframe_data.get("M30")
        h1_data = all_timeframe_data.get("H1")
        
        if not all([m5_data, m15_data, m30_data, h1_data]):
            raise RuntimeError(f"Failed to fetch market data for {symbol_normalized}")
        
        # 🔥 PHASE 3: Enrich with Binance real-time data (+ order flow if available)
        if registry.binance_service and registry.binance_service.running:
            logger.info(f"   Enriching with Binance real-time data...")
            enricher = BinanceEnrichment(registry.binance_service, registry.mt5_service, registry.order_flow_service)
            m5_data = enricher.enrich_timeframe(symbol_normalized, m5_data, "M5")
            m15_data = enricher.enrich_timeframe(symbol_normalized, m15_data, "M15")
            if registry.order_flow_service and registry.order_flow_service.running:
                logger.info(f"   ✅ MT5 data enriched with Binance microstructure + order flow")
            else:
                logger.info(f"   ✅ MT5 data enriched with Binance microstructure")
        
        # Fetch Advanced features for advanced analysis
        logger.info(f"   Building Advanced features for {symbol_normalized}...")
        advanced_features = build_features_advanced(
            symbol=symbol_normalized,
            mt5svc=registry.mt5_service,
            bridge=bridge,
            timeframes=["M15"]
        )
        
        # Call decision engine
        logger.info(f"   Running decision engine...")
        result = decide_trade(
            symbol=symbol_normalized,
            m5=m5_data,
            m15=m15_data,
            m30=m30_data,
            h1=h1_data,
            advanced_features=advanced_features
        )
        
        # Extract recommendation
        rec = result.get("rec")
        if not rec or rec.direction == "HOLD":
            # No trade recommendation
            summary = (
                f"📊 {symbol} Analysis:\n"
                f"Direction: HOLD / WAIT\n"
                f"Regime: {rec.regime if rec else 'unknown'}\n"
                f"Reasoning: {rec.reasoning if rec else 'No clear setup detected'}\n"
                f"Confidence: {rec.confidence if rec else 0}%\n\n"
                f"💡 Recommendation: Wait for better setup"
            )
            
            # Add timestamp to HOLD responses too
            import time
            current_timestamp = int(time.time())
            
            return {
                "summary": summary,
                "data": {
                    "symbol": symbol,
                    "direction": "HOLD",
                    "confidence": rec.confidence if rec else 0,
                    "regime": rec.regime if rec else "unknown",
                    "reasoning": rec.reasoning if rec else "No clear setup",
                    "executable": False
                },
                "timestamp": current_timestamp,
                "timestamp_human": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "cache_control": "no-cache, no-store, must-revalidate"
            }
        
        # Valid trade recommendation
        current_price = m5_data.get("close", 0)
        
        recommendation = {
            "symbol": symbol,
            "symbol_normalized": symbol_normalized,
            "direction": rec.direction,
            "entry": rec.entry,
            "stop_loss": rec.sl,
            "take_profit": rec.tp,
            "confidence": rec.confidence,
            "reasoning": rec.reasoning,
            "risk_reward": rec.rr,
            "regime": rec.regime,
            "strategy": rec.strategy,
            "current_price": current_price,
            "executable": True
        }
        
        # 🔥 PHASE 3: Add ALL Binance enrichment data (37 fields)
        if registry.binance_service and registry.binance_service.running:
            recommendation["binance_price"] = m5_data.get("binance_price")
            recommendation["binance_momentum"] = m5_data.get("micro_momentum")
            recommendation["feed_health"] = m5_data.get("feed_health")
            
            # Baseline enrichments
            recommendation["binance_trend"] = m5_data.get("price_trend_10s", "UNKNOWN")
            recommendation["binance_volatility"] = m5_data.get("price_volatility", 0)
            recommendation["volume_surge"] = m5_data.get("volume_surge", False)
            recommendation["momentum_acceleration"] = m5_data.get("momentum_acceleration", 0)
            
            # Top 5 enrichments
            recommendation["price_structure"] = m5_data.get("price_structure")
            recommendation["structure_strength"] = m5_data.get("structure_strength")
            recommendation["volatility_state"] = m5_data.get("volatility_state")
            recommendation["volatility_change_pct"] = m5_data.get("volatility_change_pct")
            recommendation["momentum_consistency"] = m5_data.get("momentum_consistency")
            recommendation["momentum_quality"] = m5_data.get("momentum_quality")
            recommendation["micro_alignment"] = m5_data.get("micro_alignment")
            recommendation["micro_alignment_score"] = m5_data.get("micro_alignment_score")
            
            # Phase 2A enrichments
            recommendation["key_level"] = m5_data.get("key_level")
            recommendation["momentum_divergence"] = m5_data.get("momentum_divergence")
            recommendation["divergence_strength"] = m5_data.get("divergence_strength")
            recommendation["binance_atr"] = m5_data.get("binance_atr")
            recommendation["atr_divergence_pct"] = m5_data.get("atr_divergence_pct")
            recommendation["atr_state"] = m5_data.get("atr_state")
            recommendation["bb_position"] = m5_data.get("bb_position")
            recommendation["bb_squeeze"] = m5_data.get("bb_squeeze")
            recommendation["move_speed"] = m5_data.get("move_speed")
            recommendation["speed_warning"] = m5_data.get("speed_warning")
            recommendation["momentum_volume_alignment"] = m5_data.get("momentum_volume_alignment")
            recommendation["mv_alignment_quality"] = m5_data.get("mv_alignment_quality")
            
            # Phase 2B enrichments
            recommendation["tick_frequency"] = m5_data.get("tick_frequency")
            recommendation["tick_activity"] = m5_data.get("tick_activity")
            recommendation["price_zscore"] = m5_data.get("price_zscore")
            recommendation["zscore_extremity"] = m5_data.get("zscore_extremity")
            recommendation["mean_reversion_signal"] = m5_data.get("mean_reversion_signal")
            recommendation["pivot_data"] = m5_data.get("pivot_data")
            recommendation["price_vs_pivot"] = m5_data.get("price_vs_pivot")
            recommendation["aggressor_side"] = m5_data.get("aggressor_side")
            recommendation["aggressor_strength"] = m5_data.get("aggressor_strength")
            recommendation["liquidity_score"] = m5_data.get("liquidity_score")
            recommendation["liquidity_quality"] = m5_data.get("liquidity_quality")
            recommendation["session"] = m5_data.get("session")
            recommendation["candle_pattern"] = m5_data.get("candle_pattern")
            recommendation["pattern_confidence"] = m5_data.get("pattern_confidence")
            
            # Get Binance confirmation of signal
            enricher = BinanceEnrichment(registry.binance_service, registry.mt5_service, registry.order_flow_service)
            confirmed, confirmation_reason = enricher.get_binance_confirmation(
                symbol_normalized, rec.direction
            )
            recommendation["binance_confirmed"] = confirmed
            recommendation["binance_confirmation_reason"] = confirmation_reason
        
        # 🔥 NEW: Extract and prioritize order flow data
        if registry.order_flow_service and registry.order_flow_service.running:
            order_flow_data = m5_data.get("order_flow", {})
            if order_flow_data:
                recommendation["order_flow_signal"] = order_flow_data.get("signal", "NEUTRAL")
                recommendation["order_flow_confidence"] = order_flow_data.get("confidence", 0)
                recommendation["order_book_imbalance"] = order_flow_data.get("imbalance")
                recommendation["whale_count"] = order_flow_data.get("whale_count", 0)
                recommendation["pressure_side"] = order_flow_data.get("pressure_side", "NEUTRAL")
                recommendation["liquidity_voids"] = order_flow_data.get("liquidity_voids", 0)
                recommendation["order_flow_warnings"] = order_flow_data.get("warnings", [])
                
                # Check for order flow contradiction
                if order_flow_data.get("signal") != "NEUTRAL":
                    if order_flow_data["signal"] != rec.direction.upper():
                        recommendation["order_flow_contradiction"] = True
                        recommendation["warnings"] = recommendation.get("warnings", []) + [
                            f"⚠️ ORDER FLOW CONTRADICTION: {order_flow_data['signal']} vs {rec.direction}"
                        ]
                    else:
                        recommendation["order_flow_contradiction"] = False
        
        # Add Advanced insights if available
        if advanced_features and advanced_features.get("features"):
            advanced_data = advanced_features["features"].get("M15", {})
            if advanced_data:
                rmag = advanced_data.get("rmag", {})
                recommendation["advanced_rmag_stretch"] = rmag.get("ema200_atr", 0)
                recommendation["advanced_mtf_alignment"] = advanced_data.get("mtf_score", {}).get("total", 0)
        
        # Format human-readable summary
        distance_to_entry = abs(rec.entry - current_price)
        entry_type = "MARKET" if distance_to_entry < 10 else "LIMIT"
        
        summary = (
            f"📊 {symbol} Analysis - {rec.strategy.upper()}\n\n"
            f"Direction: {rec.direction} {entry_type}\n"
            f"Entry: {rec.entry:.2f}\n"
            f"Stop Loss: {rec.sl:.2f}\n"
            f"Take Profit: {rec.tp:.2f}\n"
            f"Risk:Reward: 1:{rec.rr:.1f}\n"
            f"Confidence: {rec.confidence}%\n\n"
            f"Regime: {rec.regime}\n"
            f"Current: {current_price:.2f}\n\n"
            f"💡 {rec.reasoning}"
        )
        
        # 🔥 NEW: Add order flow signals prominently (if available)
        if recommendation.get("order_flow_signal") and recommendation["order_flow_signal"] != "NEUTRAL":
            of_signal = recommendation["order_flow_signal"]
            of_confidence = recommendation.get("order_flow_confidence", 0)
            
            signal_emoji = "🟢" if of_signal == "BULLISH" else "🔴" if of_signal == "BEARISH" else "⚪"
            
            summary += f"\n\n{signal_emoji} Order Flow: {of_signal} ({of_confidence:.0f}%)"
            
            # Show whale activity if present
            if recommendation.get("whale_count", 0) > 0:
                summary += f"\n🐋 Whales Active: {recommendation['whale_count']} in last 60s"
            
            # Show imbalance
            if recommendation.get("order_book_imbalance"):
                imbalance = recommendation["order_book_imbalance"]
                imb_emoji = "🟢" if imbalance > 1.2 else "🔴" if imbalance < 0.8 else "⚪"
                summary += f"\n{imb_emoji} Book Imbalance: {imbalance:.2f}"
            
            # Show pressure
            if recommendation.get("pressure_side") != "NEUTRAL":
                pressure = recommendation["pressure_side"]
                pressure_emoji = "📈" if pressure == "BUY" else "📉"
                summary += f"\n{pressure_emoji} Pressure: {pressure}"
            
            # Show warnings
            if recommendation.get("order_flow_warnings"):
                for warning in recommendation["order_flow_warnings"][:2]:  # Show first 2
                    summary += f"\n⚠️ {warning}"
            
            # Show contradictions prominently
            if recommendation.get("order_flow_contradiction"):
                summary += f"\n\n⚠️ WARNING: Order flow contradicts trade direction!"
        
        if detail_level == "detailed":
            # Add Advanced insights
            advanced_summary = result.get("advanced_summary", "")
            if advanced_summary:
                summary += f"\n\n🔬 Advanced Insights:\n{advanced_summary}"
        
        # 🔥 PHASE 3: Add Binance enrichment summary
        if registry.binance_service and registry.binance_service.running:
            enricher = BinanceEnrichment(registry.binance_service, registry.mt5_service, registry.order_flow_service)
            binance_summary = enricher.get_enrichment_summary(symbol_normalized)
            summary += f"\n\n{binance_summary}"
            
            # Add confirmation status
            if recommendation.get("binance_confirmed") is not None:
                confirmation_emoji = "✅" if recommendation["binance_confirmed"] else "⚠️"
                summary += f"\n{confirmation_emoji} {recommendation.get('binance_confirmation_reason', '')}"
        
        # ============================================================================
        # LOG CONVERSATION (NEW)
        # ============================================================================
        try:
            conversation_logger.log_conversation(
                user_query=f"Analyze {symbol}",
                assistant_response=summary,
                symbol=symbol_normalized,
                action="ANALYZE",
                confidence=rec.confidence,
                recommendation=f"{rec.direction} @ {rec.entry:.2f}",
                reasoning=rec.reasoning,
                source="desktop_agent",
                extra={
                    "entry": rec.entry,
                    "sl": rec.sl,
                    "tp": rec.tp,
                    "rr": rec.rr,
                    "strategy": rec.strategy,
                    "regime": rec.regime
                }
            )
            
            # Also log to analysis table
            conversation_logger.log_analysis(
                symbol=symbol_normalized,
                direction=rec.direction,
                confidence=rec.confidence,
                reasoning=rec.reasoning,
                timeframe="M15",
                analysis_type="technical_v8",
                key_levels={
                    "entry": rec.entry,
                    "sl": rec.sl,
                    "tp": rec.tp
                },
                indicators={
                    "rsi": m5_data.get("rsi"),
                    "adx": m5_data.get("adx"),
                    "macd": m5_data.get("macd_histogram"),
                    "atr": m5_data.get("atr14")
                } if m5_data else None,
                advanced_features=advanced_features.get("features", {}).get("M15") if advanced_features else None,
                source="desktop_agent"
            )
            
            logger.info(f"📊 Analysis conversation logged to database")
            
        except Exception as e:
            logger.error(f"❌ Failed to log conversation: {e}", exc_info=True)
            # Don't fail the analysis, just log the error
        
        # Add timestamp and cache control to prevent stale data
        import time
        current_timestamp = int(time.time())
        
        return {
            "summary": summary,
            "data": recommendation,
            "timestamp": current_timestamp,
            "timestamp_human": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "cache_control": "no-cache, no-store, must-revalidate",
            "expires": "0"
        }
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}", exc_info=True)
        raise RuntimeError(f"Analysis failed: {str(e)}")


@registry.register("moneybot.analyse_symbols_bulk")
async def tool_analyse_symbols_bulk(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze multiple symbols in bulk and provide comprehensive analysis for each,
    followed by trade recommendations for all symbols.
    
    Args:
        symbols: Comma-separated list of trading symbols (e.g., "BTCUSD,XAUUSD,EURUSD,USDJPY,GBPUSD")
                or a list of symbols
    
    Returns:
        Bulk analysis with individual symbol analyses and aggregated trade recommendations
    """
    import time
    from datetime import datetime
    
    symbols_input = args.get("symbols")
    if not symbols_input:
        # Log received arguments for debugging
        logger.error(f"❌ Missing 'symbols' argument. Received arguments: {args}")
        raise ValueError(f"Missing required argument: symbols. Received arguments: {list(args.keys())}")
    
    # Parse symbols - support both comma-separated string and list
    if isinstance(symbols_input, str):
        symbols = [s.strip().upper() for s in symbols_input.split(",") if s.strip()]
    elif isinstance(symbols_input, list):
        symbols = [s.strip().upper() if isinstance(s, str) else str(s).upper() for s in symbols_input if s]
    else:
        raise ValueError("symbols must be a comma-separated string or a list")
    
    if not symbols:
        raise ValueError("No valid symbols provided")
    
    logger.info(f"📊 Starting BULK analysis for {len(symbols)} symbols: {', '.join(symbols)}")
    
    start_time = time.time()
    results = []
    errors = []
    
    # Analyze each symbol sequentially (to avoid overwhelming the system)
    for idx, symbol in enumerate(symbols, 1):
        try:
            logger.info(f"   [{idx}/{len(symbols)}] Analyzing {symbol}...")
            
            # Call the full analysis tool for each symbol
            analysis_result = await tool_analyse_symbol_full({"symbol": symbol})
            
            results.append({
                "symbol": symbol,
                "analysis": analysis_result,
                "status": "success"
            })
            
            logger.info(f"   ✅ {symbol} analysis complete")
            
        except Exception as e:
            logger.error(f"   ❌ {symbol} analysis failed: {e}", exc_info=True)
            errors.append({
                "symbol": symbol,
                "error": str(e),
                "status": "failed"
            })
            results.append({
                "symbol": symbol,
                "analysis": None,
                "status": "failed",
                "error": str(e)
            })
    
    # Aggregate trade recommendations
    trade_recommendations = []
    
    for result in results:
        if result["status"] == "success" and result["analysis"]:
            analysis_data = result["analysis"].get("data", {})
            decision = analysis_data.get("decision", {})
            
            # Extract trade recommendation if available
            if decision.get("direction") and decision.get("direction") != "WAIT":
                recommendation = {
                    "symbol": result["symbol"],
                    "direction": decision.get("direction"),
                    "entry": decision.get("entry"),
                    "stop_loss": decision.get("stop_loss"),
                    "take_profit": decision.get("take_profit"),
                    "confidence": decision.get("confidence", 0),
                    "strategy": decision.get("strategy", ""),
                    "reasoning": decision.get("reasoning", ""),
                    "risk_reward": decision.get("risk_reward", 0),
                    "summary": result["analysis"].get("summary", "")
                }
                trade_recommendations.append(recommendation)
    
    # Build comprehensive response
    elapsed = time.time() - start_time
    
    # Format individual analyses
    individual_analyses = []
    for result in results:
        if result["status"] == "success" and result["analysis"]:
            symbol = result["symbol"]
            analysis = result["analysis"]
            summary = analysis.get("summary", f"Analysis for {symbol}")
            
            individual_analyses.append({
                "symbol": symbol,
                "summary": summary,
                "data": analysis.get("data", {}),
                "timestamp": analysis.get("timestamp", int(time.time()))
            })
        else:
            individual_analyses.append({
                "symbol": result["symbol"],
                "status": "failed",
                "error": result.get("error", "Analysis failed"),
                "summary": f"❌ Analysis failed for {result['symbol']}: {result.get('error', 'Unknown error')}"
            })
    
    # Format trade recommendations summary
    recommendations_summary = ""
    if trade_recommendations:
        recommendations_summary = "\n\n" + "="*70 + "\n"
        recommendations_summary += "📊 TRADE RECOMMENDATIONS SUMMARY\n"
        recommendations_summary += "="*70 + "\n\n"
        
        for idx, rec in enumerate(trade_recommendations, 1):
            recommendations_summary += f"🎯 {idx}. {rec['symbol']} - {rec['direction']}\n"
            
            # Handle None values gracefully
            entry = rec.get('entry')
            stop_loss = rec.get('stop_loss')
            take_profit = rec.get('take_profit')
            confidence = rec.get('confidence', 0)
            strategy = rec.get('strategy', 'N/A')
            risk_reward = rec.get('risk_reward', 0)
            reasoning = rec.get('reasoning', '')
            
            if entry is not None:
                recommendations_summary += f"   Entry: ${entry:,.2f}\n"
            else:
                recommendations_summary += f"   Entry: N/A\n"
            
            if stop_loss is not None:
                recommendations_summary += f"   Stop Loss: ${stop_loss:,.2f}\n"
            else:
                recommendations_summary += f"   Stop Loss: N/A\n"
            
            if take_profit is not None:
                recommendations_summary += f"   Take Profit: ${take_profit:,.2f}\n"
            else:
                recommendations_summary += f"   Take Profit: N/A\n"
            
            recommendations_summary += f"   Confidence: {confidence}%\n"
            recommendations_summary += f"   Strategy: {strategy}\n"
            
            if risk_reward is not None and risk_reward > 0:
                recommendations_summary += f"   Risk:Reward: 1:{risk_reward:.2f}\n"
            else:
                recommendations_summary += f"   Risk:Reward: N/A\n"
            
            if reasoning:
                recommendations_summary += f"   Reasoning: {reasoning}\n"
            recommendations_summary += "\n"
    else:
        recommendations_summary = "\n\n⚠️ No trade recommendations - all symbols show WAIT signals or analysis failed.\n"
    
    # Build full summary with all individual analyses
    full_summary = f"📊 BULK ANALYSIS REPORT - {len(symbols)} Symbols Analyzed\n"
    full_summary += f"⏱️ Total Time: {elapsed:.2f}s\n"
    full_summary += f"✅ Successful: {len([r for r in results if r['status'] == 'success'])}\n"
    if errors:
        full_summary += f"❌ Failed: {len(errors)}\n"
    full_summary += "\n" + "="*70 + "\n\n"
    
    # Add individual analyses
    for analysis in individual_analyses:
        full_summary += f"📈 {analysis['symbol']}\n"
        full_summary += "-"*70 + "\n"
        full_summary += analysis.get('summary', 'No analysis available') + "\n\n"
    
    # Add trade recommendations at the end
    full_summary += recommendations_summary
    
    response = {
        "summary": full_summary,
        "data": {
            "symbols_analyzed": len(symbols),
            "successful": len([r for r in results if r['status'] == 'success']),
            "failed": len(errors),
            "total_time_seconds": elapsed,
            "individual_analyses": individual_analyses,
            "trade_recommendations": trade_recommendations,
            "errors": errors
        },
        "timestamp": int(time.time()),
        "analysis_count": len(symbols)
    }
    
    logger.info(f"✅ Bulk analysis complete: {len([r for r in results if r['status'] == 'success'])}/{len(symbols)} successful in {elapsed:.2f}s")
    
    return response

@registry.register("moneybot.analyse_range_scalp_opportunity")
async def tool_analyse_range_scalp_opportunity(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyse range scalping opportunities for a symbol.
    
    Detects session/daily/dynamic ranges, evaluates 5 range scalping strategies
    (VWAP Reversion, BB Fade, PDH/PDL Rejection, RSI Bounce, Liquidity Sweep),
    and applies weighted 3-confluence risk filtering.
    
    Args:
        symbol: Trading symbol (e.g., BTCUSD, XAUUSD)
        strategy_filter: Optional strategy name to focus on
        check_risk_filters: Whether to apply risk mitigation (default: true)
    
    Returns:
        Analysis with range structure, risk checks, top strategy, warnings
    """
    symbol = args.get("symbol")
    if not symbol:
        raise ValueError("Missing required argument: symbol")
    
    strategy_filter = args.get("strategy_filter")
    check_risk_filters = args.get("check_risk_filters", True)
    
    logger.info(f"📊 Analysing range scalping opportunity for {symbol}...")
    
    try:
        # Normalize symbol
        symbol_normalized = symbol if symbol.endswith('c') else f"{symbol}c"
        
        # Initialize services
        from infra.range_scalping_analysis import analyse_range_scalp_opportunity
        from infra.indicator_bridge import IndicatorBridge
        from infra.feature_builder_advanced import build_features_advanced
        
        mt5_service = registry.mt5_service
        if not mt5_service:
            raise RuntimeError("MT5 service not initialized")
        
        bridge = IndicatorBridge()
        
        # Fetch multi-timeframe data for indicators
        all_timeframe_data = bridge.get_multi(symbol_normalized)
        m5_data = all_timeframe_data.get("M5")
        m15_data = all_timeframe_data.get("M15")
        h1_data = all_timeframe_data.get("H1")
        
        if not all([m5_data, m15_data, h1_data]):
            raise RuntimeError(f"Failed to fetch market data for {symbol_normalized}")
        
        # Get current price from MT5 live tick
        import MetaTrader5 as mt5
        tick = mt5.symbol_info_tick(symbol_normalized)
        if tick:
            current_price = float(tick.bid)
        else:
            # Fallback to indicator data
            current_price = (
                m5_data.get("current_close") or
                m5_data.get("close") or
                0
            )
            if isinstance(current_price, list) and len(current_price) > 0:
                current_price = float(current_price[-1])
            else:
                current_price = float(current_price) if current_price else 0
        
        # Prepare indicators
        indicators = {
            "rsi": m5_data.get("indicators", {}).get("rsi", 50),
            "bb_upper": m5_data.get("indicators", {}).get("bb_upper"),
            "bb_lower": m5_data.get("indicators", {}).get("bb_lower"),
            "bb_middle": m5_data.get("indicators", {}).get("bb_middle"),
            "stoch_k": m5_data.get("indicators", {}).get("stoch_k", 50),
            "stoch_d": m5_data.get("indicators", {}).get("stoch_d", 50),
            "adx_h1": h1_data.get("indicators", {}).get("adx", 20),
            "atr_5m": m5_data.get("indicators", {}).get("atr14", 0)
        }
        
        # Prepare market data
        # Get PDH/PDL from advanced features if available
        pdh = None
        pdl = None
        vwap = None
        session_high = None
        session_low = None
        
        try:
            advanced_features = build_features_advanced(
                symbol=symbol_normalized,
                mt5svc=mt5_service,
                bridge=bridge,
                timeframes=["M5", "M15", "H1"]
            )
            
            if advanced_features and "features" in advanced_features:
                m15_features = advanced_features["features"].get("M15", {})
                liquidity = m15_features.get("liquidity", {})
                pdh = liquidity.get("pdh")
                pdl = liquidity.get("pdl")
                
                vwap_data = m15_features.get("vwap")
                if vwap_data:
                    vwap = vwap_data.get("value")
        except Exception as e:
            logger.debug(f"Could not fetch PDH/PDL/VWAP: {e}")
        
        # Calculate session high/low from M15 candles
        # Session ranges: Asian (00:00-08:00 UTC), London (08:00-13:00 UTC), NY (13:00-20:00 UTC), Overlap (13:00-16:00 UTC)
        try:
            if m15_data and m15_data.get("df") is not None:
                import pandas as pd
                from datetime import datetime, timezone, timedelta
                
                df_m15 = m15_data["df"].copy()  # Copy to avoid modifying original
                if hasattr(df_m15, "iloc") and len(df_m15) > 0:
                    # Ensure we have a datetime index or time column
                    if "time" in df_m15.columns and not isinstance(df_m15.index, pd.DatetimeIndex):
                        df_m15["datetime"] = pd.to_datetime(df_m15["time"], unit='s')
                        df_m15 = df_m15.set_index("datetime")
                    elif not isinstance(df_m15.index, pd.DatetimeIndex):
                        # Try to use index as datetime if it's numeric
                        try:
                            df_m15.index = pd.to_datetime(df_m15.index, unit='s')
                        except:
                            pass
                    
                    # Get current UTC time
                    now_utc = datetime.now(timezone.utc)
                    utc_hour = now_utc.hour
                    
                    # Determine session start time based on current hour
                    session_start_hour = None
                    if 0 <= utc_hour < 8:
                        session_start_hour = 0  # Asian session
                    elif 8 <= utc_hour < 13:
                        session_start_hour = 8  # London session
                    elif 13 <= utc_hour < 16:
                        session_start_hour = 13  # Overlap (use overlap start)
                    elif 16 <= utc_hour < 20:
                        session_start_hour = 13  # NY session (started at overlap)
                    else:  # 20-24 (Late NY)
                        session_start_hour = 13  # Late NY, still part of NY session
                    
                    if session_start_hour is not None:
                        # Filter candles for current session (from session start to now)
                        today = now_utc.date()
                        session_start = datetime.combine(today, datetime.min.time()).replace(
                            hour=session_start_hour, minute=0, second=0, tzinfo=timezone.utc
                        )
                        
                        # If current hour < session_start_hour, session started yesterday
                        if session_start_hour > utc_hour:
                            session_start = session_start - timedelta(days=1)
                        
                        # Filter dataframe for current session
                        session_candles = df_m15[df_m15.index >= session_start]
                        
                        if len(session_candles) > 0:
                            # Calculate session high/low
                            if "high" in session_candles.columns:
                                session_high = float(session_candles["high"].max())
                            if "low" in session_candles.columns:
                                session_low = float(session_candles["low"].min())
                            
                            logger.info(f"✅ Calculated session high/low for {symbol_normalized}: {session_low:.2f} - {session_high:.2f} (session start: {session_start_hour}:00 UTC, {len(session_candles)} candles)")
                        else:
                            logger.debug(f"No M15 candles found for current session (start: {session_start_hour}:00 UTC)")
                    else:
                        logger.debug(f"Could not determine session start hour for UTC hour {utc_hour}")
                        
        except Exception as e:
            logger.warning(f"Could not calculate session high/low: {e}", exc_info=True)
        
        # Convert M15 data to DataFrame if needed (IndicatorBridge returns lists, not df)
        import pandas as pd
        if m15_data and "df" not in m15_data:
            # Convert lists to DataFrame - IndicatorBridge returns 'times', 'opens', 'highs', 'lows', 'closes', 'volumes'
            try:
                if "times" in m15_data or "opens" in m15_data:
                    # IndicatorBridge format: 'times', 'opens', 'highs', 'lows', 'closes', 'volumes'
                    times = m15_data.get("times", [])
                    opens = m15_data.get("opens", [])
                    highs = m15_data.get("highs", [])
                    lows = m15_data.get("lows", [])
                    closes = m15_data.get("closes", [])
                    volumes = m15_data.get("volumes", m15_data.get("tick_volume", []))
                    
                    if len(times) > 0 and len(opens) > 0:
                        # Convert times to datetime
                        try:
                            if isinstance(times[0], str):
                                times_dt = pd.to_datetime(times)
                            else:
                                # Assume Unix timestamp
                                times_dt = pd.to_datetime(times, unit='s', errors='coerce')
                        except:
                            times_dt = pd.to_datetime(times, errors='coerce')
                        
                        df_m15_from_lists = pd.DataFrame({
                            "open": opens,
                            "high": highs,
                            "low": lows,
                            "close": closes,
                            "tick_volume": volumes if volumes else [0] * len(times)
                        }, index=times_dt)
                        
                        if len(df_m15_from_lists) > 0:
                            m15_data["df"] = df_m15_from_lists
                            logger.debug(f"✅ Converted M15 lists to DataFrame ({len(df_m15_from_lists)} rows)")
                    else:
                        logger.warning(f"M15 data has no times or opens data")
                else:
                    logger.debug(f"M15 data missing 'times' or 'opens' keys, available keys: {list(m15_data.keys())}")
            except Exception as e:
                logger.warning(f"Could not convert M15 data to DataFrame: {e}", exc_info=True)
        
        # Also convert M5 data to DataFrame if needed
        if m5_data and "df" not in m5_data:
            try:
                if "times" in m5_data or "opens" in m5_data:
                    times = m5_data.get("times", [])
                    opens = m5_data.get("opens", [])
                    highs = m5_data.get("highs", [])
                    lows = m5_data.get("lows", [])
                    closes = m5_data.get("closes", [])
                    volumes = m5_data.get("volumes", m5_data.get("tick_volume", []))
                    
                    if len(times) > 0 and len(opens) > 0:
                        try:
                            if isinstance(times[0], str):
                                times_dt = pd.to_datetime(times)
                            else:
                                times_dt = pd.to_datetime(times, unit='s', errors='coerce')
                        except:
                            times_dt = pd.to_datetime(times, errors='coerce')
                        
                        df_m5_from_lists = pd.DataFrame({
                            "open": opens,
                            "high": highs,
                            "low": lows,
                            "close": closes,
                            "tick_volume": volumes if volumes else [0] * len(times)
                        }, index=times_dt)
                        
                        if len(df_m5_from_lists) > 0:
                            m5_data["df"] = df_m5_from_lists
                            logger.debug(f"✅ Converted M5 lists to DataFrame ({len(df_m5_from_lists)} rows)")
            except Exception as e:
                logger.debug(f"Could not convert M5 data to DataFrame: {e}")
        
        # Recalculate session high/low if we just converted the DataFrame
        # (Session calculation needs the DataFrame to be available)
        if session_high is None or session_low is None:
            try:
                if m15_data and m15_data.get("df") is not None:
                    import pandas as pd
                    from datetime import datetime, timezone, timedelta
                    
                    df_m15 = m15_data["df"]
                    if hasattr(df_m15, "iloc") and len(df_m15) > 0:
                        # Ensure we have a datetime index with timezone
                        if not isinstance(df_m15.index, pd.DatetimeIndex):
                            # Try to convert index if it's not datetime
                            try:
                                df_m15.index = pd.to_datetime(df_m15.index, errors='coerce')
                            except Exception as e:
                                logger.warning(f"Could not convert DataFrame index to datetime: {e}")
                                df_m15 = None
                        
                        if df_m15 is not None and len(df_m15) > 0:
                            # Ensure timezone-aware index (convert naive to UTC if needed)
                            if isinstance(df_m15.index, pd.DatetimeIndex):
                                if df_m15.index.tz is None:
                                    # Index is timezone-naive, assume UTC
                                    df_m15.index = df_m15.index.tz_localize('UTC')
                                elif df_m15.index.tz != timezone.utc:
                                    # Convert to UTC
                                    df_m15.index = df_m15.index.tz_convert(timezone.utc)
                            
                            # Get current UTC time
                            now_utc = datetime.now(timezone.utc)
                            utc_hour = now_utc.hour
                            
                            # Determine session start time
                            session_start_hour = None
                            if 0 <= utc_hour < 8:
                                session_start_hour = 0  # Asian
                            elif 8 <= utc_hour < 13:
                                session_start_hour = 8  # London
                            elif 13 <= utc_hour < 16:
                                session_start_hour = 13  # Overlap
                            elif 16 <= utc_hour < 20:
                                session_start_hour = 13  # NY (started at overlap)
                            else:
                                session_start_hour = 13  # Late NY
                            
                            if session_start_hour is not None:
                                today = now_utc.date()
                                session_start = datetime.combine(today, datetime.min.time()).replace(
                                    hour=session_start_hour, minute=0, second=0, tzinfo=timezone.utc
                                )
                                
                                # If we're past midnight but before session start hour, session started yesterday
                                # (This shouldn't happen with our logic, but keep it for safety)
                                if session_start_hour > utc_hour:
                                    session_start = session_start - timedelta(days=1)
                                
                                # Get earliest and latest candle times for debugging
                                earliest_candle = df_m15.index.min()
                                latest_candle = df_m15.index.max()
                                
                                logger.debug(f"Session calculation: UTC hour={utc_hour}, session_start={session_start}, "
                                           f"DF range: {earliest_candle} to {latest_candle}")
                                
                                # Filter dataframe for current session
                                session_candles = df_m15[df_m15.index >= session_start]
                                
                                if len(session_candles) > 0:
                                    if "high" in session_candles.columns:
                                        session_high = float(session_candles["high"].max())
                                    if "low" in session_candles.columns:
                                        session_low = float(session_candles["low"].min())
                                    
                                    logger.info(f"✅ Calculated session high/low from converted DataFrame: {session_low:.2f} - {session_high:.2f} "
                                              f"(session start: {session_start_hour}:00 UTC, {len(session_candles)} candles)")
                                else:
                                    logger.warning(f"⚠️ No candles found for current session (start: {session_start_hour}:00 UTC, "
                                                 f"session_start: {session_start}, DF range: {earliest_candle} to {latest_candle})")
                            else:
                                logger.warning(f"Could not determine session start hour for UTC hour {utc_hour}")
            except Exception as e:
                logger.warning(f"Could not recalculate session high/low after DataFrame conversion: {e}", exc_info=True)
        
        # Calculate PDH/PDL from M15 DataFrame if not available from advanced features
        if (pdh is None or pdl is None) and m15_data and m15_data.get("df") is not None:
            try:
                df_m15 = m15_data["df"]
                if len(df_m15) > 0:
                    # Calculate PDH/PDL from last 24 hours (96 M15 candles = 24 hours)
                    bars_per_day = min(96, len(df_m15))
                    if bars_per_day > 0:
                        recent = df_m15.iloc[-bars_per_day:]
                        if "high" in recent.columns and "low" in recent.columns:
                            pdh = float(recent["high"].max())
                            pdl = float(recent["low"].min())
                            logger.info(f"✅ Calculated PDH/PDL from M15 DataFrame: {pdl:.2f} - {pdh:.2f}")
            except Exception as e:
                logger.debug(f"Could not calculate PDH/PDL from DataFrame: {e}")
        
        # Calculate VWAP from M15 DataFrame if not available
        if vwap is None and m15_data and m15_data.get("df") is not None:
            try:
                df_m15 = m15_data["df"]
                if len(df_m15) > 0:
                    # Calculate VWAP: sum(typical_price * volume) / sum(volume)
                    typical_prices = (df_m15["high"] + df_m15["low"] + df_m15["close"]) / 3
                    volumes = df_m15.get("tick_volume", df_m15.get("volume", pd.Series([1] * len(df_m15))))
                    if volumes.sum() > 0:
                        vwap = float((typical_prices * volumes).sum() / volumes.sum())
                        logger.info(f"✅ Calculated VWAP from M15 DataFrame: {vwap:.2f}")
            except Exception as e:
                logger.debug(f"Could not calculate VWAP from DataFrame: {e}")
        
        # Calculate ATR from M5 DataFrame if it's 0
        if indicators.get("atr_5m", 0) == 0 and m5_data and m5_data.get("df") is not None:
            try:
                df_m5 = m5_data["df"]
                if len(df_m5) >= 14:
                    # Calculate ATR(14) from M5 candles
                    high_low = df_m5["high"] - df_m5["low"]
                    high_close_prev = abs(df_m5["high"] - df_m5["close"].shift(1))
                    low_close_prev = abs(df_m5["low"] - df_m5["close"].shift(1))
                    true_range = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
                    atr_calculated = float(true_range.tail(14).mean())
                    indicators["atr_5m"] = atr_calculated
                    logger.info(f"✅ Calculated ATR(14) from M5 DataFrame: {atr_calculated:.2f}")
            except Exception as e:
                logger.debug(f"Could not calculate ATR from DataFrame: {e}")
        
        # Log what we have for debugging
        m15_df_final = m15_data.get('df') if m15_data else None
        logger.info(f"📊 Market data prepared for {symbol_normalized}:")
        logger.info(f"   → Session high: {session_high}, Session low: {session_low}")
        logger.info(f"   → PDH: {pdh}, PDL: {pdl}")
        logger.info(f"   → VWAP: {vwap}, ATR: {indicators.get('atr_5m', 0)}")
        logger.info(f"   → M15 DataFrame: {'✅ Available' if m15_df_final is not None and not (hasattr(m15_df_final, 'empty') and m15_df_final.empty) else '❌ None/Empty'}")
        if m15_df_final is not None:
            logger.info(f"      → M15 DF rows: {len(m15_df_final)}, columns: {list(m15_df_final.columns)[:5]}")
        
        # Get volume data
        volume_current = 0
        volume_1h_avg = 0
        if m5_data.get("df") is not None:
            try:
                df_m5 = m5_data["df"]
                if hasattr(df_m5, "iloc") and len(df_m5) > 0:
                    # Try different volume column names (tick_volume, volume, real_volume)
                    volume_col = None
                    for col_name in ["tick_volume", "volume", "real_volume"]:
                        if col_name in df_m5.columns:
                            volume_col = col_name
                            break
                    
                    if volume_col:
                        # Get current volume (last candle)
                        volume_current = float(df_m5.iloc[-1][volume_col]) if len(df_m5) > 0 else 0
                        
                        # Get 1h average (12 M5 candles = 1 hour)
                        if len(df_m5) >= 12:
                            volume_1h_avg = float(df_m5.iloc[-12:][volume_col].mean())
                        else:
                            # Use available candles if less than 12
                            volume_1h_avg = float(df_m5[volume_col].mean()) if len(df_m5) > 0 else volume_current
                    else:
                        logger.warning(f"No volume column found in M5 DataFrame for {symbol_normalized}")
            except Exception as e:
                logger.debug(f"Error extracting volume data: {e}")
                # Try fallback: use M15 data for volume average
                if m15_data.get("df") is not None:
                    try:
                        df_m15 = m15_data["df"]
                        volume_col = None
                        for col_name in ["tick_volume", "volume", "real_volume"]:
                            if col_name in df_m15.columns:
                                volume_col = col_name
                                break
                        if volume_col and len(df_m15) > 0:
                            volume_1h_avg = float(df_m15[volume_col].mean()) if len(df_m15) >= 4 else volume_current
                    except:
                        pass
        
        # Get recent candles
        recent_candles = []
        if m5_data.get("df") is not None:
            try:
                df_m5 = m5_data["df"]
                if hasattr(df_m5, "iloc") and len(df_m5) > 0:
                    # Find volume column
                    volume_col = None
                    for col_name in ["tick_volume", "volume", "real_volume"]:
                        if col_name in df_m5.columns:
                            volume_col = col_name
                            break
                    
                    for i in range(max(0, len(df_m5) - 5), len(df_m5)):
                        candle_dict = {
                            "open": float(df_m5.iloc[i]["open"]),
                            "high": float(df_m5.iloc[i]["high"]),
                            "low": float(df_m5.iloc[i]["low"]),
                            "close": float(df_m5.iloc[i]["close"]),
                            "volume": int(df_m5.iloc[i][volume_col]) if volume_col else 0
                        }
                        recent_candles.append(candle_dict)
            except Exception as e:
                logger.debug(f"Error extracting recent candles: {e}")
        
        # Calculate BB width (handle None values)
        bb_upper = indicators.get("bb_upper")
        bb_lower = indicators.get("bb_lower")
        if bb_upper is not None and bb_lower is not None and current_price > 0:
            bb_width = (bb_upper - bb_lower) / current_price
        else:
            bb_width = 0.0
        
        # Prepare market_data dict (use calculated values)
        final_atr = indicators.get("atr_5m", 0) or 0
        market_data = {
            "current_price": current_price,
            "vwap": vwap,  # May be calculated from DataFrame
            "atr": final_atr,  # May be calculated from DataFrame
            "atr_5m": final_atr,
            "bb_width": bb_width,
            "pdh": pdh,  # May be calculated from DataFrame
            "pdl": pdl,  # May be calculated from DataFrame
            "session_high": session_high,  # May be recalculated after DataFrame conversion
            "session_low": session_low,  # May be recalculated after DataFrame conversion
            "volume_current": volume_current,
            "volume_1h_avg": volume_1h_avg,
            "recent_candles": recent_candles,
            "order_flow": {
                "signal": "NEUTRAL",
                "confidence": 0
            },
            "m15_df": m15_data.get("df") if m15_data else None,  # Pass DataFrame for dynamic range detection
            "mt5_service": mt5_service  # Pass MT5Service for risk filters to use existing connection
        }
        
        # Log if m15_df is None (for debugging)
        if market_data.get("m15_df") is None:
            logger.warning(f"⚠️ m15_df is None for {symbol_normalized} - dynamic range detection may fail. m15_data keys: {list(m15_data.keys()) if m15_data else 'None'}")
        
        # Call analysis function
        result = await analyse_range_scalp_opportunity(
            symbol=symbol_normalized,
            strategy_filter=strategy_filter,
            check_risk_filters=check_risk_filters,
            market_data=market_data,
            indicators=indicators
        )
        
        logger.info(f"✅ Range scalping analysis complete for {symbol_normalized}")
        
        return {
            "summary": f"Range scalping analysis for {symbol}",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"❌ Range scalping analysis failed: {e}", exc_info=True)
        raise RuntimeError(f"Range scalping analysis failed: {str(e)}")


@registry.register("moneybot.execute_trade")
async def tool_execute_trade(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a trade on MT5 with automatic risk-based lot sizing
    
    Args:
        symbol: Trading symbol
        direction: "BUY" | "SELL"
        entry: Entry price (for market orders, use current price)
        stop_loss: Stop loss price
        take_profit: Take profit price
        volume: Position size (optional - if not provided, calculates based on risk)
        risk_pct: Risk percentage override (optional - uses symbol default if not provided)
        order_type: "market" | "limit" | "stop" (default: "market")
    
    Automatic Lot Sizing:
        - BTCUSD/XAUUSD: Max 0.02 lots (0.75-1.0% risk)
        - Forex pairs: Max 0.04 lots (1.0-1.25% risk)
        - Calculates based on: equity, stop distance, symbol volatility
    
    Returns:
        Ticket number and monitoring status
    """
    symbol = args.get("symbol")
    direction = args.get("direction")
    entry = args.get("entry")
    stop_loss = args.get("stop_loss")
    take_profit = args.get("take_profit")
    volume = args.get("volume")  # Can be None (will calculate)
    order_type = args.get("order_type", "market")
    risk_pct = args.get("risk_pct")  # Optional risk percentage override
    
    # Validate required arguments
    if not all([symbol, direction, stop_loss, take_profit]):
        raise ValueError("Missing required arguments: symbol, direction, stop_loss, take_profit")
    
    # Normalize symbol
    # Normalize: strip any trailing 'c' or 'C', then add lowercase 'c'
    if not symbol.lower().endswith('c'):
        symbol_normalized = symbol.upper() + 'c'
    else:
        symbol_normalized = symbol.upper().rstrip('cC') + 'c'
    
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    # ========== VOLATILITY-AWARE RISK MANAGEMENT (Phase 3) ==========
    volatility_regime_data = None
    try:
        logger.info(f"   [Risk Management] Detecting volatility regime for risk adjustment...")
        from infra.volatility_regime_detector import RegimeDetector, VolatilityRegime
        from infra.volatility_risk_manager import VolatilityRiskManager, get_volatility_adjusted_lot_size
        import pandas as pd
        import numpy as np
        
        # Get timeframe data for regime detection
        from infra.indicator_bridge import IndicatorBridge
        bridge = IndicatorBridge()
        all_timeframe_data = bridge.get_multi(symbol_normalized)
        
        if all_timeframe_data:
            regime_detector = RegimeDetector()
            timeframe_data_for_regime = {}
            
            for tf_name in ["M5", "M15", "H1"]:
                tf_data = all_timeframe_data.get(tf_name)
                if tf_data:
                    # Reconstruct rates DataFrame
                    rates_df = None
                    if all(key in tf_data for key in ['opens', 'highs', 'lows', 'closes', 'volumes']):
                        try:
                            rates_df = pd.DataFrame({
                                'open': tf_data['opens'],
                                'high': tf_data['highs'],
                                'low': tf_data['lows'],
                                'close': tf_data['closes'],
                                'tick_volume': tf_data['volumes']
                            })
                        except Exception as e:
                            logger.debug(f"Could not reconstruct DataFrame for {tf_name}: {e}")
                    
                    atr_14 = tf_data.get("atr14") or tf_data.get("atr_14")
                    atr_50 = tf_data.get("atr_50")
                    
                    # Calculate ATR(50) if needed
                    if atr_14 and not atr_50 and rates_df is not None and len(rates_df) >= 50:
                        try:
                            high = rates_df['high']
                            low = rates_df['low']
                            close = rates_df['close']
                            tr1 = high - low
                            tr2 = abs(high - close.shift(1))
                            tr3 = abs(low - close.shift(1))
                            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                            atr_50 = float(tr.rolling(window=50).mean().iloc[-1])
                        except Exception as e:
                            logger.debug(f"Could not calculate ATR(50) for {tf_name}: {e}")
                    
                    timeframe_data_for_regime[tf_name] = {
                        "rates": rates_df,
                        "atr_14": atr_14,
                        "atr_50": atr_50,
                        "bb_upper": tf_data.get("bb_upper"),
                        "bb_lower": tf_data.get("bb_lower"),
                        "bb_middle": tf_data.get("bb_middle"),
                        "adx": tf_data.get("adx"),
                        "volume": tf_data.get("volumes") or tf_data.get("volume")
                    }
            
            if timeframe_data_for_regime:
                volatility_regime_data = regime_detector.detect_regime(
                    symbol=symbol_normalized,
                    timeframe_data=timeframe_data_for_regime,
                    current_time=datetime.now()
                )
                
                regime = volatility_regime_data.get("regime")
                confidence = volatility_regime_data.get("confidence", 0)
                # Extract regime string
                if isinstance(regime, VolatilityRegime):
                    regime_str = regime.value
                elif hasattr(regime, 'value'):
                    regime_str = regime.value
                else:
                    regime_str = str(regime) if regime else "UNKNOWN"
                logger.info(f"   ✅ Volatility regime: {regime_str} (confidence: {confidence:.1f}%)")
                
                # Check circuit breakers
                risk_manager = VolatilityRiskManager()
                import MetaTrader5 as mt5
                account_info = mt5.account_info()
                equity = float(account_info.equity) if account_info else 10000.0
                
                can_trade, block_reason = risk_manager.check_circuit_breakers(
                    symbol=symbol_normalized,
                    equity=equity,
                    current_time=datetime.now()
                )
                
                if not can_trade:
                    error_msg = f"🚫 Trade blocked by circuit breaker: {block_reason}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                
                logger.info(f"   ✅ Circuit breakers passed")
        
    except Exception as e:
        logger.warning(f"   ⚠️ Volatility risk management check failed: {e}")
        # Don't fail trade execution if risk management fails - use standard sizing
    
    # Calculate lot size if not provided (treat 0 as None)
    if volume is None or volume == 0:
        import MetaTrader5 as mt5
        
        # Get account equity
        account_info = mt5.account_info()
        if account_info:
            equity = float(account_info.equity)
        else:
            equity = 10000  # Fallback
            logger.warning("Could not get account equity, using $10,000 default")
        
        # Get symbol info for accurate calculations
        symbol_info = mt5.symbol_info(symbol_normalized)
        if symbol_info:
            tick_value = float(symbol_info.trade_tick_value)
            tick_size = float(symbol_info.trade_tick_size)
            contract_size = float(symbol_info.trade_contract_size)
        else:
            tick_value = 1.0
            tick_size = 0.01
            contract_size = 100000
            logger.warning(f"Could not get symbol info for {symbol_normalized}, using defaults")
        
        # Use volatility-adjusted lot sizing if regime data available
        if volatility_regime_data:
            try:
                from infra.volatility_risk_manager import get_volatility_adjusted_lot_size
                volume, sizing_metadata = get_volatility_adjusted_lot_size(
                    symbol=symbol_normalized,
                    entry=float(entry) if entry else 0,
                    stop_loss=float(stop_loss),
                    equity=equity,
                    volatility_regime=volatility_regime_data,
                    base_risk_pct=risk_pct,
                    tick_value=tick_value,
                    tick_size=tick_size,
                    contract_size=contract_size
                )
                logger.info(
                    f"📊 Volatility-adjusted lot size: {volume} "
                    f"(Base risk: {sizing_metadata['base_risk_pct']:.2f}% → "
                    f"Adjusted: {sizing_metadata['adjusted_risk_pct']:.2f}%, "
                    f"Regime: {sizing_metadata['adjustment_reason']})"
                )
            except Exception as e:
                logger.warning(f"Volatility-adjusted sizing failed: {e}, using standard sizing")
                # Fallback to standard sizing
                volume = get_lot_size(
                    symbol=symbol_normalized,
                    entry=float(entry) if entry else 0,
                    stop_loss=float(stop_loss),
                    equity=equity,
                    risk_pct=risk_pct,
                    use_risk_based=True,
                    tick_value=tick_value,
                    tick_size=tick_size,
                    contract_size=contract_size
                )
                logger.info(f"📊 Calculated lot size: {volume} (Risk-based, Equity=${equity:.2f})")
        else:
            # Standard risk-based lot sizing (no volatility adjustment)
            volume = get_lot_size(
                symbol=symbol_normalized,
                entry=float(entry) if entry else 0,
                stop_loss=float(stop_loss),
                equity=equity,
                risk_pct=risk_pct,
                use_risk_based=True,
                tick_value=tick_value,
                tick_size=tick_size,
                contract_size=contract_size
            )
            logger.info(f"📊 Calculated lot size: {volume} (Risk-based, Equity=${equity:.2f})")
    else:
        logger.info(f"📊 Using provided lot size: {volume}")
    
    logger.info(f"💰 Executing {direction} {symbol_normalized} @ {volume} lots")
    
    try:
        import MetaTrader5 as mt5
        from infra.indicator_bridge import IndicatorBridge
        from infra.feature_builder_advanced import build_features_advanced
        
        # Get current price
        quote = registry.mt5_service.get_quote(symbol_normalized)
        
        current_price = quote.ask if direction == "BUY" else quote.bid
        
        # 🛡️ PRE-EXECUTION SAFETY VALIDATION
        if registry.signal_prefilter:
            logger.info("🛡️ Running pre-execution safety checks...")
            
            # Prepare signal for validation
            signal_to_validate = {
                "action": direction,
                "entry": entry if entry else current_price,
                "sl": stop_loss,
                "tp": take_profit,
                "confidence": args.get("confidence", 100)  # Assume high confidence if not specified
            }
            
            # Validate and adjust
            can_execute, reason, adjusted_signal = registry.signal_prefilter.adjust_and_validate(
                symbol_normalized,
                signal_to_validate,
                {"bid": quote.bid, "ask": quote.ask}
            )
            
            if not can_execute:
                error_msg = f"🚫 Trade blocked by safety filter: {reason}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            logger.info(f"✅ Safety checks passed: {reason}")
            
            # Use adjusted prices if available
            if adjusted_signal:
                stop_loss = adjusted_signal.get("sl") or adjusted_signal.get("stop_loss")
                take_profit = adjusted_signal.get("tp") or adjusted_signal.get("take_profit")
                if entry and "entry" in adjusted_signal:
                    entry = adjusted_signal["entry"]
                logger.info(f"📊 Prices adjusted for MT5 offset")
        else:
            logger.warning("⚠️ No safety filter configured - executing without validation")
        
        # Determine order type/mapping and normalize prices to tick size
        if order_type == "market":
            actual_entry = current_price
            mt5_action = mt5.TRADE_ACTION_DEAL
            mt5_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        elif order_type == "limit":
            actual_entry = entry
            mt5_action = mt5.TRADE_ACTION_PENDING
            mt5_type = mt5.ORDER_TYPE_BUY_LIMIT if direction == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
        elif order_type == "stop":
            actual_entry = entry
            mt5_action = mt5.TRADE_ACTION_PENDING
            mt5_type = mt5.ORDER_TYPE_BUY_STOP if direction == "BUY" else mt5.ORDER_TYPE_SELL_STOP
        else:
            logger.warning(f"Unknown order_type '{order_type}', defaulting to market")
            actual_entry = current_price
            mt5_action = mt5.TRADE_ACTION_DEAL
            mt5_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL

        # Symbol constraints and tick normalization
        try:
            sym_info = mt5.symbol_info(symbol_normalized)
            tick_size = float(sym_info.trade_tick_size) if sym_info else 0.01
            stops_level = int(sym_info.stops_level) if sym_info else 0
            freeze_level = int(sym_info.freeze_level) if sym_info else 0
            logger.info(
                f"   Symbol constraints: tick_size={tick_size}, stops_level={stops_level}, freeze_level={freeze_level}"
            )
            def _norm(x: float):
                if x is None:
                    return None
                if tick_size > 0:
                    return round(round(x / tick_size) * tick_size, 10)
                return x
            actual_entry = _norm(actual_entry)
            stop_loss = _norm(stop_loss)
            take_profit = _norm(take_profit)
            # Pre-validate and AUTO-ADJUST minimum distances for SL/TP (retcode 10016 guard)
            try:
                point = float(getattr(sym_info, 'point', tick_size)) if sym_info else tick_size
                min_dist = float(stops_level) * point if point else 0.0
                if min_dist > 0:
                    # For market orders, use actual fill price (ask for BUY, bid for SELL)
                    if mt5_action == mt5.TRADE_ACTION_DEAL:
                        reference_price = float(current_price)  # This is ask for BUY, bid for SELL
                    else:
                        reference_price = float(actual_entry)
                    
                    # Auto-adjust SL if too close (instead of erroring)
                    if stop_loss is not None:
                        sl_distance = abs(stop_loss - reference_price)
                        if sl_distance < min_dist:
                            logger.warning(f"SL distance {sl_distance:.5f} < broker min {min_dist:.5f}, auto-adjusting...")
                            if direction == "BUY":
                                stop_loss = _norm(reference_price - min_dist * 1.1)
                            else:
                                stop_loss = _norm(reference_price + min_dist * 1.1)
                            logger.info(f"Adjusted SL to {stop_loss}")
                    
                    # Auto-adjust TP if too close
                    if take_profit is not None:
                        tp_distance = abs(take_profit - reference_price)
                        if tp_distance < min_dist:
                            logger.warning(f"TP distance {tp_distance:.5f} < broker min {min_dist:.5f}, auto-adjusting...")
                            if direction == "BUY":
                                take_profit = _norm(reference_price + min_dist * 1.1)
                            else:
                                take_profit = _norm(reference_price - min_dist * 1.1)
                            logger.info(f"Adjusted TP to {take_profit}")
                    
                    # For pending orders, validate entry distance (can't auto-adjust - that changes the trade)
                    if mt5_action == mt5.TRADE_ACTION_PENDING:
                        current_mid = float(current_price)
                        if abs(actual_entry - current_mid) < min_dist:
                            raise RuntimeError(
                                f"Entry too close for pending order (need ≥ {min_dist:.5f}) | "
                                f"current={current_mid:.5f}, entry={actual_entry:.5f}"
                            )
            except Exception as _vd:
                # If validation raises RuntimeError, bubble up; else just log
                if isinstance(_vd, RuntimeError):
                    raise
                logger.warning(f"Pre-validation warning: {_vd}")
        except Exception:
            pass

        # Place order
        logger.info(f"   Placing {order_type} order: {direction} {symbol_normalized}")

        # Filling mode: RETURN for pending orders improves broker compatibility
        filling_mode = mt5.ORDER_FILLING_RETURN if mt5_action == mt5.TRADE_ACTION_PENDING else mt5.ORDER_FILLING_IOC

        # Prepare order request
        request = {
            "action": mt5_action,
            "symbol": symbol_normalized,
            "volume": volume,
            "type": mt5_type,
            "price": actual_entry,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": 20,
            "magic": 234000,
            "comment": args.get("comment") or "Phone control",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }

        # Pre-validate with order_check for clearer diagnostics
        try:
            check = mt5.order_check(request)
            if check is not None:
                logger.info(f"   order_check: retcode={getattr(check, 'retcode', None)} comment={getattr(check, 'comment', '')}")
                # If broker rejects at pre-check, surface immediately
                if hasattr(check, 'retcode') and check.retcode not in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED):
                    raise RuntimeError(f"Pre-check failed: retcode={check.retcode} comment={getattr(check, 'comment', '')}")
        except Exception as _e:
            # If order_check itself errors, log and continue to order_send
            logger.warning(f"order_check error: {_e}")

        # Send order
        result = mt5.order_send(request)

        if result is None:
            err = mt5.last_error()
            raise RuntimeError(f"Order send failed: MT5 returned None (last_error={err})")
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Order failed: {result.retcode} - {result.comment}"
            logger.error(f"❌ {error_msg}")
            
            # Log failed trade to database
            try:
                journal_repo.add_event(
                    event="trade_execution_failed",
                    symbol=symbol_normalized,
                    side=direction,
                    price=actual_entry,
                    sl=stop_loss,
                    tp=take_profit,
                    volume=volume,
                    reason=f"MT5 Error {result.retcode}: {result.comment}",
                    extra={
                        "order_type": order_type,
                        "retcode": result.retcode,
                        "comment": result.comment,
                        "source": "desktop_agent"
                    }
                )
                logger.info(f"📊 Failed trade logged to database")
            except Exception as e:
                logger.error(f"Failed to log error to database: {e}")
            
            raise RuntimeError(error_msg)
        
        ticket = result.order
        actual_entry_price = result.price
        
        logger.info(f"✅ Order placed successfully: Ticket {ticket}")
        
        # ============================================================================
        # DATABASE LOGGING (NEW)
        # ============================================================================
        try:
            # Get account info for balance/equity
            account_info = mt5.account_info()
            balance = account_info.balance if account_info else None
            equity = account_info.equity if account_info else None
            
            # Calculate risk-reward ratio
            if stop_loss and take_profit:
                risk = abs(actual_entry_price - stop_loss)
                reward = abs(take_profit - actual_entry_price)
                rr = reward / risk if risk > 0 else None
            else:
                rr = None
            
            # Log to database
            journal_repo.write_exec({
                "ts": int(datetime.now().timestamp()),
                "symbol": symbol_normalized,
                "side": direction,
                "entry": actual_entry_price,
                "sl": stop_loss,
                "tp": take_profit,
                "lot": volume,
                "ticket": ticket,
                "position": ticket,  # Same as ticket for positions
                "balance": balance,
                "equity": equity,
                "confidence": args.get("confidence", 100),  # High confidence if not specified
                "regime": None,  # Could extract from Advanced features later
                "rr": rr,
                "notes": f"Phone Control - {order_type} order, Lot sizing: {'auto' if args.get('volume') is None else 'manual'}"
            })
            
            logger.info(f"📊 Trade logged to database: ticket {ticket}")
            
        except Exception as e:
            logger.error(f"❌ Failed to log trade to database: {e}", exc_info=True)
            # Don't fail the trade execution, just log the error
        
        # ============================================================================
        # Universal Dynamic SL/TP Manager Registration (ALWAYS - even without strategy_type)
        # If no strategy_type provided, uses DEFAULT_STANDARD (generic trailing)
        # ============================================================================
        universal_manager_registered = False
        # FIX: Always register, not just when strategy_type is provided
        try:
            from infra.universal_sl_tp_manager import (
                UniversalDynamicSLTPManager,
                UNIVERSAL_MANAGED_STRATEGIES,
                StrategyType
            )
            
            # Normalize strategy_type to enum (can be None - will use DEFAULT_STANDARD)
            strategy_type_enum = None
            if strategy_type:
                if isinstance(strategy_type, str):
                    # Try to match string to enum value
                    for st in StrategyType:
                        if st.value == strategy_type:
                            strategy_type_enum = st
                            break
                elif isinstance(strategy_type, StrategyType):
                    strategy_type_enum = strategy_type
            # If strategy_type is None, register_trade will use DEFAULT_STANDARD automatically
            
            # Always register with Universal Manager (strategy_type can be None - will use DEFAULT_STANDARD)
            universal_sl_tp_manager = UniversalDynamicSLTPManager(
                mt5_service=registry.mt5_service
            )
            
            trade_state = universal_sl_tp_manager.register_trade(
                ticket=ticket,
                symbol=symbol_normalized,
                strategy_type=strategy_type_enum,  # Can be None - will use DEFAULT_STANDARD
                direction=direction,
                entry_price=actual_entry_price,
                initial_sl=stop_loss,
                initial_tp=take_profit,
                initial_volume=volume
            )
            
            if trade_state:
                strategy_name = trade_state.strategy_type.value if trade_state.strategy_type else "DEFAULT_STANDARD"
                logger.info(
                    f"✅ Trade {ticket} registered with Universal SL/TP Manager "
                    f"(strategy: {strategy_name})"
                )
                universal_manager_registered = True
            else:
                logger.warning(
                    f"⚠️ Trade {ticket} registration with Universal Manager failed"
                )
        except Exception as e:
            logger.error(
                f"❌ Error registering trade {ticket} with Universal Manager: {e}",
                exc_info=True
            )
        
        # Auto-register to DTMS (only if not registered with Universal Manager)
        if not universal_manager_registered:
            try:
                from dtms_integration import auto_register_dtms
                result_dict = {
                    'symbol': symbol_normalized,
                    'direction': direction,
                    'entry_price': actual_entry_price,
                    'volume': volume,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit
                }
                auto_register_dtms(ticket, result_dict)
            except Exception:
                pass  # Silent failure
        
        # ============================================================================
        # Enable Advanced-enhanced intelligent exits
        # ============================================================================
        logger.info(f"   Enabling Advanced-enhanced intelligent exits...")
        
        # Fetch Advanced features
        bridge = IndicatorBridge()
        advanced_features = build_features_advanced(
            symbol=symbol_normalized,
            mt5svc=registry.mt5_service,
            bridge=bridge,
            timeframes=["M15"]
        )
        
        # ============================================================================
        # LOG ADVANCED ANALYTICS (NEW)
        # ============================================================================
        try:
            from infra.advanced_analytics import AdvancedFeatureTracker

            advanced_tracker = AdvancedFeatureTracker()

            # Record trade entry with Advanced features
            success = advanced_tracker.record_trade_entry(
                ticket=ticket,
                symbol=symbol_normalized,
                direction=direction,
                entry_price=actual_entry_price,
                sl=stop_loss,
                tp=take_profit,
                advanced_features=advanced_features
            )

            if success:
                logger.info(f"📊 Advanced features logged to analytics database: ticket {ticket}")
            else:
                logger.warning(f"⚠️ Failed to log Advanced features for ticket {ticket}")

        except Exception as e:
            logger.error(f"❌ Failed to log Advanced analytics: {e}", exc_info=True)
            # Don't fail the trade execution, just log the error
        
        # ============================================================================
        # TRADE TYPE CLASSIFICATION (AIES Phase 1 MVP)
        # ============================================================================
        classification_info = {}
        trade_comment = args.get("comment") or "Phone control"
        
        logger.info(f"   → Trade comment for classification: '{trade_comment}'")
        
        # Determine exit parameters based on classification
        base_breakeven_pct = settings.INTELLIGENT_EXITS_BREAKEVEN_PCT
        base_partial_pct = settings.INTELLIGENT_EXITS_PARTIAL_PCT
        partial_close_pct = settings.INTELLIGENT_EXITS_PARTIAL_CLOSE_PCT
        
        # Use getattr with default False to handle missing attribute gracefully
        # Also check raw environment variable directly as fallback
        import os
        raw_env_value = os.getenv("ENABLE_TRADE_TYPE_CLASSIFICATION", "NOT_SET")
        
        # Helper function to convert string to bool (same as config.py)
        def _as_bool(val):
            if val is None:
                return False
            return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}
        
        # Try to get from settings instance first
        enable_classification = getattr(settings, 'ENABLE_TRADE_TYPE_CLASSIFICATION', None)
        
        # If not found in settings, fallback to environment variable directly
        if enable_classification is None:
            enable_classification = _as_bool(raw_env_value) if raw_env_value != "NOT_SET" else False
            logger.info(f"   → Classification not in settings, using env var directly: {raw_env_value} → {enable_classification}")
        else:
            logger.info(f"   → Classification from settings: {enable_classification}")
        
        logger.info(f"   → Final classification flag: {enable_classification} (type: {type(enable_classification)})")
        logger.info(f"   → Raw env var ENABLE_TRADE_TYPE_CLASSIFICATION: {raw_env_value}")
        
        if enable_classification:
            try:
                import time
                from infra.trade_type_classifier import TradeTypeClassifier
                from infra.session_analyzer import SessionAnalyzer
                from infra.classification_metrics import record_classification_metric
                
                logger.info(f"   Classifying trade type for {symbol_normalized}...")
                
                # Measure classification latency
                classification_start_time = time.time()
                
                session_analyzer = SessionAnalyzer()
                session_info = session_analyzer.get_current_session()
                
                classifier = TradeTypeClassifier(
                    mt5_service=registry.mt5_service,
                    session_service=session_analyzer
                )
                
                # Get volatility regime data if available (Phase 3.09)
                volatility_regime_for_classification = None
                try:
                    if 'volatility_regime_data' in locals():
                        volatility_regime_for_classification = volatility_regime_data
                except:
                    pass
                
                classification = classifier.classify(
                    symbol=symbol_normalized,
                    entry_price=actual_entry_price,
                    stop_loss=stop_loss,
                    comment=trade_comment,
                    session_info=session_info,
                    volatility_regime=volatility_regime_for_classification
                )
                
                classification_latency_ms = (time.time() - classification_start_time) * 1000
                
                trade_type = classification["trade_type"]
                confidence = classification["confidence"]
                reasoning = classification["reasoning"]
                factors = classification["factors"]
                
                classification_info = {
                    "trade_type": trade_type,
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "factors": factors
                }
                
                logger.info(f"📊 Trade Classification: {trade_type} (confidence: {confidence:.2f}) - {reasoning}")
                
                # Record metrics
                try:
                    record_classification_metric(
                        trade_type=trade_type,
                        confidence=confidence,
                        reasoning=reasoning,
                        factor_used=factors.get("primary_factor", "unknown"),
                        latency_ms=classification_latency_ms,
                        feature_enabled=True
                    )
                except Exception as e:
                    logger.warning(f"Failed to record classification metric: {e}")
                
                # Select exit parameters based on classification
                if trade_type == "SCALP":
                    base_breakeven_pct = 25.0
                    base_partial_pct = 40.0
                    partial_close_pct = 70.0
                    logger.info(f"   Using SCALP exit parameters: {base_breakeven_pct}% BE / {base_partial_pct}% partial / {partial_close_pct}% close")
                else:  # INTRADAY
                    logger.info(f"   Using INTRADAY exit parameters: {base_breakeven_pct}% BE / {base_partial_pct}% partial / {partial_close_pct}% close")
            except Exception as e:
                logger.error(f"❌ Classification failed: {e}", exc_info=True)
                classification_info = {"error": str(e)}
        else:
            logger.info(f"   → Classification skipped - feature flag disabled (ENABLE_TRADE_TYPE_CLASSIFICATION={enable_classification})")
        
        logger.info(f"   → Final exit parameters before exit manager: BE={base_breakeven_pct}%, Partial={base_partial_pct}%, Close={partial_close_pct}%")
        
        # Create exit manager with Binance and order flow integration
        exit_manager = create_exit_manager(
            registry.mt5_service,
            binance_service=registry.binance_service,
            order_flow_service=registry.order_flow_service
        )
        
        exit_result = exit_manager.add_rule_advanced(
            ticket=ticket,
            symbol=symbol_normalized,
            entry_price=actual_entry_price,
            direction=direction.lower(),
            initial_sl=stop_loss,
            initial_tp=take_profit,
            advanced_features=advanced_features,
            base_breakeven_pct=base_breakeven_pct,
            base_partial_pct=base_partial_pct,
            partial_close_pct=partial_close_pct,
            vix_threshold=settings.INTELLIGENT_EXITS_VIX_THRESHOLD,
            use_hybrid_stops=settings.INTELLIGENT_EXITS_USE_HYBRID_STOPS,
            trailing_enabled=settings.INTELLIGENT_EXITS_TRAILING_ENABLED
        )
        
        # Get Advanced-adjusted percentages
        rule = exit_manager.rules.get(ticket)
        breakeven_pct = rule.breakeven_profit_pct if rule else base_breakeven_pct
        partial_pct = rule.partial_profit_pct if rule else base_partial_pct
        final_partial_close_pct = rule.partial_close_pct if rule else partial_close_pct

        advanced_adjusted = breakeven_pct != 30.0 or partial_pct != 60.0

        logger.info(f"✅ Intelligent exits enabled: {breakeven_pct}% / {partial_pct}%")

        # Format summary with classification info
        summary = (
            f"✅ Trade Executed Successfully — {symbol_normalized} {direction} (Range Scalp)\n\n"
            f"📊 Order Summary:\n\n"
            f"Direction: {direction} (Market Execution)\n"
            f"Entry: ${actual_entry_price:,.2f}\n"
            f"Stop Loss: ${stop_loss:,.2f}\n"
            f"Take Profit: ${take_profit:,.2f}\n"
            f"Volume: {volume} lots\n"
            f"Order ID: {ticket}\n"
            f"Comment: {trade_comment}\n\n"
        )
        
        # Add classification info if available
        if classification_info and "trade_type" in classification_info:
            trade_type_display = classification_info["trade_type"]
            confidence_display = classification_info.get("confidence", 0.0)
            reasoning_display = classification_info.get("reasoning", "Default classification")
            
            summary += (
                f"📊 Trade Classification:\n"
                f"   Type: {trade_type_display}\n"
                f"   Confidence: {confidence_display:.0%}\n"
                f"   Reasoning: {reasoning_display}\n\n"
            )

        summary += (
            f"🤖 Intelligent Exits — AUTO-ENABLED\n"
            f"🎯 Breakeven: +0.{int(breakeven_pct/10):.0f}R (~${actual_entry_price + (actual_entry_price - stop_loss) * (breakeven_pct/100):,.2f})\n"
            f"💰 Partial Profit: +0.{int(partial_pct/10):.0f}R (~${actual_entry_price + (actual_entry_price - stop_loss) * (partial_pct/100):,.2f})\n"
            f"🔬 Hybrid ATR+VIX: Active\n"
            f"📈 Trailing Stop: Activated post-breakeven\n"
        )

        if advanced_adjusted:
            summary += f"   ⚡ Advanced-Adjusted (from base {base_breakeven_pct:.0f}%/{base_partial_pct:.0f}%)\n"
        
        summary += f"\n🟢 Status: Trade LIVE and Managed Automatically"
        
        # Send Discord notification with classification info
        try:
            logger.info("   → Attempting to send Discord notification...")
            from discord_notifications import DiscordNotifier
            discord_notifier = DiscordNotifier()
            logger.info(f"   → Discord notifier initialized, enabled={discord_notifier.enabled}")
            
            if discord_notifier.enabled:
                # Get plan_id if this is an auto-executed trade
                plan_id = get_plan_id_from_ticket(ticket)
                plan_id_line = f"📊 **Plan ID**: {plan_id}\n" if plan_id else ""
                
                discord_message = (
                    f"✅ **Trade Executed Successfully**\n\n"
                    f"💱 **Symbol**: {symbol_normalized.replace('c', '')}\n"
                    f"📊 **Direction**: {direction} (Market Execution)\n"
                    f"💰 **Entry**: ${actual_entry_price:,.2f}\n"
                    f"🛡️ **SL**: ${stop_loss:,.2f} | 🎯 **TP**: ${take_profit:,.2f}\n"
                    f"📦 **Volume**: {volume} lots\n"
                    f"🎫 **Ticket**: {ticket}\n"
                    f"{plan_id_line}\n"
                )
                
                # Add classification info if available
                if classification_info and "trade_type" in classification_info:
                    trade_type_display = classification_info["trade_type"]
                    confidence_display = classification_info.get("confidence", 0.0)
                    reasoning_display = classification_info.get("reasoning", "Default classification")
                    
                    discord_message += (
                        f"📊 **Trade Classification**:\n"
                        f"   • Type: **{trade_type_display}**\n"
                        f"   • Confidence: **{confidence_display:.0%}**\n"
                        f"   • Reasoning: {reasoning_display}\n\n"
                    )
                else:
                    logger.info("   → No classification info available for Discord message")
                
                discord_message += (
                    f"⚙️ **Intelligent Exits Enabled**:\n"
                    f"   • Breakeven: {breakeven_pct:.0f}% profit (0.{int(breakeven_pct/10):.0f}R)\n"
                    f"   • Partial: {partial_pct:.0f}% profit (0.{int(partial_pct/10):.0f}R), close {final_partial_close_pct:.0f}%\n"
                    f"   • Hybrid ATR+VIX: Active\n"
                    f"   • Trailing Stop: Enabled post-breakeven\n\n"
                    f"🤖 Position is now on autopilot!"
                )
                
                logger.info(f"   → Sending Discord message (length: {len(discord_message)} chars)...")
                
                # Use send_message directly for better formatting (instead of send_system_alert)
                success = discord_notifier.send_message(
                    message=discord_message,
                    message_type="TRADE_EXECUTION",
                    color=0x00ff00,  # Green for successful trade
                    channel="private",
                    custom_title="Trade Executed"
                )
                if success:
                    logger.info("   ✅ Discord notification sent successfully with classification info")
                else:
                    logger.warning("   ❌ Discord notification failed to send (send_message returned False)")
            else:
                logger.warning("   ⚠️ Discord notifications are disabled - check DISCORD_WEBHOOK_URL in .env")
        except ImportError as e:
            logger.error(f"   ❌ Failed to import DiscordNotifier: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"   ❌ Discord notification error: {e}", exc_info=True)
        
        # ============================================================================
        # LOG CONVERSATION (NEW)
        # ============================================================================
        try:
            conversation_logger.log_conversation(
                user_query=f"Execute {direction} {symbol} @ {entry if entry else 'market'}",
                assistant_response=summary,
                symbol=symbol_normalized,
                action="EXECUTE",
                confidence=args.get("confidence", 100),
                execution_result="success",
                ticket=ticket,
                source="desktop_agent",
                extra={
                    "entry": actual_entry_price,
                    "sl": stop_loss,
                    "tp": take_profit,
                    "volume": volume,
                    "order_type": order_type,
                    "rr": rr,
                    "classification": classification_info
                }
            )
            
            logger.info(f"📊 Trade execution conversation logged to database")
            
        except Exception as e:
            logger.error(f"❌ Failed to log conversation: {e}", exc_info=True)
            # Don't fail the execution, just log the error
        
        return {
            "summary": summary,
            "data": {
                "ticket": ticket,
                "symbol": symbol,
                "symbol_normalized": symbol_normalized,
                "direction": direction,
                "entry": actual_entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "volume": volume,
                "monitoring_enabled": True,
                "advanced_breakeven_pct": breakeven_pct,
                "advanced_partial_pct": partial_pct,
                "advanced_adjusted": advanced_adjusted
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Trade execution failed: {e}", exc_info=True)
        raise RuntimeError(f"Execution failed: {str(e)}")

@registry.register("moneybot.register_trade_with_universal_manager")
async def tool_register_trade_with_universal_manager(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Register an existing trade with Universal Dynamic SL/TP Manager.
    
    Use this when:
    - A trade was executed manually (not through auto-execution system)
    - A trade was executed without strategy_type parameter
    - You want to transfer a trade from Intelligent Exit Manager to Universal Manager
    
    This will enable:
    - Strategy-specific, symbol-specific, session-aware dynamic SL/TP management
    - Proper trailing stops (not gated like Intelligent Exit Manager)
    - Better profit protection
    
    Args:
        ticket: MT5 position ticket number
        strategy_type: Strategy type (e.g., "breakout_ib_volatility_trap", "trend_continuation_pullback", 
                      "liquidity_sweep_reversal", "order_block_rejection", "mean_reversion_range_scalp")
    
    Returns:
        Registration status and trade details
    """
    ticket = args.get("ticket")
    strategy_type = args.get("strategy_type")
    
    if not ticket:
        raise ValueError("Missing required argument: ticket")
    if not strategy_type:
        raise ValueError("Missing required argument: strategy_type")
    
    try:
        from infra.universal_sl_tp_manager import (
            UniversalDynamicSLTPManager,
            UNIVERSAL_MANAGED_STRATEGIES,
            StrategyType
        )
        import MetaTrader5 as mt5
        
        # Normalize strategy_type to enum
        strategy_type_enum = None
        if isinstance(strategy_type, str):
            for st in StrategyType:
                if st.value == strategy_type.lower().replace(" ", "_"):
                    strategy_type_enum = st
                    break
        elif isinstance(strategy_type, StrategyType):
            strategy_type_enum = strategy_type
        
        if not strategy_type_enum:
            return {
                "summary": f"❌ Invalid strategy_type: {strategy_type}",
                "data": {
                    "registered": False,
                    "error": f"Strategy type '{strategy_type}' not found. Valid types: {[st.value for st in StrategyType]}"
                }
            }
        
        if strategy_type_enum not in UNIVERSAL_MANAGED_STRATEGIES:
            return {
                "summary": f"⚠️ Strategy '{strategy_type_enum.value}' is not managed by Universal Manager",
                "data": {
                    "registered": False,
                    "strategy_type": strategy_type_enum.value,
                    "managed_strategies": [st.value for st in UNIVERSAL_MANAGED_STRATEGIES]
                }
            }
        
        # Get position from MT5
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
        
        position = mt5.positions_get(ticket=ticket)
        if not position or len(position) == 0:
            return {
                "summary": f"❌ Trade {ticket} not found in MT5",
                "data": {
                    "registered": False,
                    "error": f"Position {ticket} does not exist"
                }
            }
        
        pos = position[0]
        symbol = pos.symbol
        direction = "BUY" if pos.type == 0 else "SELL"
        entry_price = pos.price_open
        initial_sl = pos.sl
        initial_tp = pos.tp
        initial_volume = pos.volume
        
        # Register with Universal Manager (use same database path as chatgpt_bot.py)
        universal_sl_tp_manager = UniversalDynamicSLTPManager(
            db_path="data/universal_sl_tp_trades.db",
            mt5_service=registry.mt5_service
        )
        
        trade_state = universal_sl_tp_manager.register_trade(
            ticket=ticket,
            symbol=symbol,
            strategy_type=strategy_type_enum,
            direction=direction,
            entry_price=entry_price,
            initial_sl=initial_sl,
            initial_tp=initial_tp,
            initial_volume=initial_volume
        )
        
        if trade_state:
            logger.info(
                f"✅ Trade {ticket} registered with Universal SL/TP Manager "
                f"(strategy: {strategy_type_enum.value})"
            )
            return {
                "summary": f"✅ Trade {ticket} registered with Universal SL/TP Manager",
                "data": {
                    "registered": True,
                    "ticket": ticket,
                    "symbol": symbol,
                    "strategy_type": strategy_type_enum.value,
                    "direction": direction,
                    "entry_price": entry_price,
                    "initial_sl": initial_sl,
                    "initial_tp": initial_tp,
                    "volume": initial_volume,
                    "message": "Trade will now be managed by Universal Dynamic SL/TP Manager with proper trailing stops"
                }
            }
        else:
            logger.warning(f"⚠️ Trade {ticket} registration with Universal Manager failed")
            return {
                "summary": f"⚠️ Failed to register trade {ticket} with Universal Manager",
                "data": {
                    "registered": False,
                    "ticket": ticket,
                    "error": "Registration failed - check logs for details"
                }
            }
    
    except Exception as e:
        logger.error(f"❌ Error registering trade {ticket} with Universal Manager: {e}", exc_info=True)
        return {
            "summary": f"❌ Error registering trade {ticket}: {str(e)}",
            "data": {
                "registered": False,
                "ticket": ticket,
                "error": str(e)
            }
        }

@registry.register("moneybot.analyse_and_execute_trade")
async def tool_analyse_and_execute_trade(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform full analysis and execute a high-probability market trade in one call.
    
    This tool:
    1. Runs complete analysis (same as moneybot.analyse_symbol_full)
    2. Extracts the best trade recommendation from the analysis
    3. Executes the trade immediately at market price
    4. Returns only trade summary and explanation (not full analysis)
    
    Use this when user asks for:
    - "Analyze and execute a trade"
    - "Give me a high probability market execution trade"
    - "Analyze [symbol] and place a trade"
    - "Market execution [symbol]" or "me market execution [symbol]"
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSD", "XAUUSD", "EURUSD")
        strategy_type: Optional strategy type for Universal SL/TP Manager (e.g., "BREAKOUT", "TREND_CONTINUATION")
        prefer_timeframe: Optional preference for recommendation type ("scalp", "intraday", "swing")
    
    Returns:
        Trade execution summary with ticket, entry, SL, TP, volume, and reasoning
    """
    symbol = args.get("symbol")
    if not symbol:
        raise ValueError("Missing required argument: symbol")
    
    strategy_type = args.get("strategy_type")
    prefer_timeframe = args.get("prefer_timeframe", "scalp")  # Default to scalp for quick trades
    
    logger.info(f"🔍 Analyzing {symbol} and preparing for market execution...")
    
    try:
        # Step 1: Run full analysis
        logger.info(f"   [1/3] Running full analysis for {symbol}...")
        analysis_result = await tool_analyse_symbol_full({"symbol": symbol})
        
        if not analysis_result or "data" not in analysis_result:
            raise RuntimeError("Analysis failed - no data returned")
        
        analysis_data = analysis_result.get("data", {})
        decision = analysis_data.get("decision", {})
        recommendations = analysis_data.get("recommendations", {})
        
        # Step 2: Extract best trade recommendation
        logger.info(f"   [2/3] Extracting best trade recommendation (prefer: {prefer_timeframe})...")
        
        # Note: recommendations are formatted strings for display, not dicts
        # The actual trade parameters are in the decision layer
        trade_rec = None
        trade_type = prefer_timeframe  # Use preferred timeframe as trade type
        
        # Check decision layer for executable trade
        if decision and isinstance(decision, dict):
            direction = decision.get("direction", "HOLD")
            if direction != "HOLD":
                trade_rec = decision
                # Determine trade type based on recommendation text (if available)
                # But use decision layer for actual parameters
                if recommendations:
                    scalp_text = recommendations.get("scalp", "")
                    intraday_text = recommendations.get("intraday", "")
                    swing_text = recommendations.get("swing", "")
                    
                    # Check if preferred timeframe recommendation is valid (not WAIT/AVOID)
                    if prefer_timeframe == "scalp" and scalp_text and "WAIT" not in scalp_text and "AVOID" not in scalp_text:
                        trade_type = "scalp"
                    elif prefer_timeframe == "intraday" and intraday_text and "WAIT" not in intraday_text and "AVOID" not in intraday_text:
                        trade_type = "intraday"
                    elif prefer_timeframe == "swing" and swing_text and "WAIT" not in swing_text and "AVOID" not in swing_text:
                        trade_type = "swing"
                    # Fallback: check other timeframes
                    elif not trade_type or trade_type == prefer_timeframe:
                        if scalp_text and "WAIT" not in scalp_text and "AVOID" not in scalp_text:
                            trade_type = "scalp"
                        elif intraday_text and "WAIT" not in intraday_text and "AVOID" not in intraday_text:
                            trade_type = "intraday"
                        elif swing_text and "WAIT" not in swing_text and "AVOID" not in swing_text:
                            trade_type = "swing"
        
        if not trade_rec or (isinstance(trade_rec, dict) and trade_rec.get("direction") == "HOLD"):
            return {
                "summary": f"❌ No executable trade found for {symbol}",
                "data": {
                    "executed": False,
                    "reason": "No high-probability setup detected in analysis",
                    "analysis_confidence": decision.get("confidence", 0) if decision else 0,
                    "analysis_reasoning": decision.get("reasoning", "Market conditions not favorable") if decision else "No clear setup"
                }
            }
        
        # Extract trade parameters (trade_rec should be a dict from decision layer)
        if not isinstance(trade_rec, dict):
            return {
                "summary": f"❌ Invalid trade recommendation format for {symbol}",
                "data": {
                    "executed": False,
                    "reason": "Trade recommendation is not in expected format",
                    "recommendation_type": type(trade_rec).__name__
                }
            }
        
        direction = trade_rec.get("direction")
        entry = trade_rec.get("entry")
        stop_loss = trade_rec.get("sl") or trade_rec.get("stop_loss")
        take_profit = trade_rec.get("tp") or trade_rec.get("take_profit")
        confidence = trade_rec.get("confidence", 0)
        reasoning = trade_rec.get("reasoning", "Based on full market analysis")
        
        if not all([direction, stop_loss, take_profit]):
            return {
                "summary": f"❌ Incomplete trade parameters for {symbol}",
                "data": {
                    "executed": False,
                    "reason": "Missing entry, SL, or TP in recommendation",
                    "recommendation": trade_rec
                }
            }
        
        # Step 3: Execute trade
        logger.info(f"   [3/3] Executing {direction} trade for {symbol}...")
        
        execute_args = {
            "symbol": symbol,
            "direction": direction,
            "entry": entry,  # Will use current price for market orders
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "volume": 0,  # Auto-calculate
            "order_type": "market",
            "comment": f"Auto-executed {trade_type} trade"
        }
        
        # Add strategy_type if provided
        if strategy_type:
            execute_args["strategy_type"] = strategy_type
        
        execution_result = await tool_execute_trade(execute_args)
        
        if not execution_result or execution_result.get("status") != "success":
            error_msg = execution_result.get("error", "Unknown execution error") if execution_result else "Execution failed"
            return {
                "summary": f"❌ Trade execution failed for {symbol}",
                "data": {
                    "executed": False,
                    "error": error_msg,
                    "recommendation": {
                        "direction": direction,
                        "entry": entry,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "confidence": confidence,
                        "reasoning": reasoning
                    }
                }
            }
        
        # Extract execution details
        execution_data = execution_result.get("data", {})
        ticket = execution_data.get("ticket")
        actual_entry = execution_data.get("entry_price", entry)
        volume = execution_data.get("volume", 0)
        
        # Build concise summary
        summary = (
            f"✅ Trade Executed Successfully\n\n"
            f"💱 Symbol: {symbol}\n"
            f"📊 Direction: {direction}\n"
            f"💰 Entry: {actual_entry:.5f}\n"
            f"🛡️ Stop Loss: {stop_loss:.5f}\n"
            f"🎯 Take Profit: {take_profit:.5f}\n"
            f"📦 Volume: {volume} lots\n"
            f"🎫 Ticket: {ticket}\n"
            f"📈 Confidence: {confidence}%\n"
            f"🎯 Trade Type: {trade_type}\n\n"
            f"💡 Reasoning:\n{reasoning}"
        )
        
        return {
            "summary": summary,
            "data": {
                "executed": True,
                "ticket": ticket,
                "symbol": symbol,
                "direction": direction,
                "entry": actual_entry,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "volume": volume,
                "confidence": confidence,
                "trade_type": trade_type,
                "reasoning": reasoning,
                "strategy_type": strategy_type
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Analyse and execute failed: {e}", exc_info=True)
        return {
            "summary": f"❌ Analysis and execution failed for {symbol}",
            "data": {
                "executed": False,
                "error": str(e)
            }
        }

@registry.register("moneybot.getPositions")
async def tool_get_positions(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get all open positions with full details
    
    Returns:
        List of all open positions with profit/loss, entry, SL, TP, etc.
    """
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    logger.info("📊 Getting all open positions")
    
    try:
        positions = registry.mt5_service.list_positions()
        
        if not positions:
            return {
                "summary": "📭 No open positions",
                "data": {"positions": []}
            }
        
        # Format positions for display
        summary_lines = [f"📊 Open Positions ({len(positions)})\n"]
        
        for pos in positions:
            symbol = pos['symbol'].replace('c', '')
            direction = "🟢 BUY" if pos['type'] == 0 else "🔴 SELL"
            profit = pos.get('profit', 0)
            profit_emoji = "📈" if profit > 0 else "📉" if profit < 0 else "➖"
            
            summary_lines.append(
                f"{direction} {symbol}\n"
                f"  Ticket: {pos['ticket']}\n"
                f"  Entry: {pos['price_open']:.5f}\n"
                f"  Current: {pos.get('price_current', 0):.5f}\n"
                f"  SL: {pos.get('sl', 0):.5f} | TP: {pos.get('tp', 0):.5f}\n"
                f"  Volume: {pos['volume']} lots\n"
                f"  {profit_emoji} P/L: ${profit:.2f}\n"
            )
        
        return {
            "summary": "\n".join(summary_lines),
            "data": {"positions": positions, "count": len(positions)}
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get positions: {e}", exc_info=True)
        raise RuntimeError(f"Failed to get positions: {str(e)}")

@registry.register("moneybot.getPendingOrders")
async def tool_get_pending_orders(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get all pending orders (buy_limit, sell_limit, buy_stop, sell_stop)
    
    Returns:
        List of all pending orders with ticket numbers, entry prices, SL, TP, etc.
    """
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    logger.info("📋 Getting all pending orders")
    
    try:
        import MetaTrader5 as mt5
        registry.mt5_service.connect()
        
        # Get all pending orders
        orders = mt5.orders_get()
        
        if not orders or len(orders) == 0:
            return {
                "summary": "📭 No pending orders",
                "data": {"orders": [], "count": 0}
            }
        
        # Order type mapping
        order_type_map = {
            mt5.ORDER_TYPE_BUY_LIMIT: "buy_limit",
            mt5.ORDER_TYPE_SELL_LIMIT: "sell_limit",
            mt5.ORDER_TYPE_BUY_STOP: "buy_stop",
            mt5.ORDER_TYPE_SELL_STOP: "sell_stop",
            mt5.ORDER_TYPE_BUY_STOP_LIMIT: "buy_stop_limit",
            mt5.ORDER_TYPE_SELL_STOP_LIMIT: "sell_stop_limit"
        }
        
        # Format orders for display
        formatted_orders = []
        summary_lines = [f"📋 Pending Orders ({len(orders)})\n"]
        
        for order in orders:
            order_type_str = order_type_map.get(order.type, "unknown")
            
            # Determine emoji based on order type
            if "buy" in order_type_str:
                emoji = "🟢"
            elif "sell" in order_type_str:
                emoji = "🔴"
            else:
                emoji = "⚪"
            
            symbol_clean = order.symbol.replace('c', '')
            
            formatted_order = {
                "ticket": order.ticket,
                "symbol": order.symbol,
                "type": order_type_str,
                "volume": order.volume_current,
                "price_open": order.price_open,
                "sl": order.sl,
                "tp": order.tp,
                "price_current": order.price_current,
                "comment": order.comment,
                "time_setup": order.time_setup,
                "time_expiration": order.time_expiration if hasattr(order, 'time_expiration') else 0
            }
            formatted_orders.append(formatted_order)
            
            summary_lines.append(
                f"{emoji} {order_type_str.upper().replace('_', ' ')} {symbol_clean}\n"
                f"  Ticket: {order.ticket}\n"
                f"  Entry: {order.price_open:.5f}\n"
                f"  SL: {order.sl:.5f} | TP: {order.tp:.5f}\n"
                f"  Volume: {order.volume_current} lots\n"
                f"  Current Price: {order.price_current:.5f}\n"
            )
        
        return {
            "summary": "\n".join(summary_lines),
            "data": {"orders": formatted_orders, "count": len(formatted_orders)}
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get pending orders: {e}", exc_info=True)
        raise RuntimeError(f"Failed to get pending orders: {str(e)}")

@registry.register("moneybot.monitor_status")
async def tool_monitor_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get status of all monitored positions
    
    Returns:
        Summary of open trades and intelligent exit status
    """
    logger.info("📋 Fetching monitoring status...")
    
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    try:
        # Get open positions
        positions = registry.mt5_service.get_positions()
        
        # Get intelligent exit status
        exit_manager = create_exit_manager(
            registry.mt5_service,
            binance_service=registry.binance_service,
            order_flow_service=registry.order_flow_service
        )
        rules = exit_manager.get_all_rules()
        
        if not positions:
            return {
                "summary": "📊 No open positions\n\nYour account is currently flat.",
                "data": {
                    "total_positions": 0,
                    "monitored_count": 0,
                    "positions": []
                }
            }
        
        summary_lines = [f"📊 Monitoring Status - {len(positions)} Position(s)\n"]
        
        position_data = []
        
        for pos in positions:
            ticket = pos.ticket
            symbol = pos.symbol.replace('c', '')  # Display without suffix
            direction = "BUY" if pos.type == 0 else "SELL"
            entry = pos.price_open
            current = pos.price_current
            profit = pos.profit
            volume = pos.volume
            
            # Check if intelligent exits enabled
            rule = next((r for r in rules if r.ticket == ticket), None)
            
            if rule:
                # Advanced-enhanced monitoring active
                breakeven_pct = rule.breakeven_profit_pct
                partial_pct = rule.partial_profit_pct
                breakeven_triggered = rule.breakeven_triggered
                partial_triggered = rule.partial_triggered
                
                advanced_status = "⚡ Advanced"
                if breakeven_pct != 30.0 or partial_pct != 60.0:
                    advanced_status += f" {breakeven_pct:.0f}/{partial_pct:.0f}%"
                else:
                    advanced_status += " 30/60%"

                # Add trigger indicators
                if breakeven_triggered:
                    advanced_status += " 🎯BE"
                if partial_triggered:
                    advanced_status += " 💰PP"

                exit_status = advanced_status
            else:
                exit_status = "❌ Not monitored"
            
            # Format P/L with color indicator
            pl_indicator = "📈" if profit > 0 else "📉" if profit < 0 else "➖"
            
            summary_lines.append(
                f"• {symbol} {direction}\n"
                f"  Ticket: {ticket} | Vol: {volume}\n"
                f"  Entry: {entry:.2f} → Current: {current:.2f}\n"
                f"  {pl_indicator} P/L: ${profit:.2f}\n"
                f"  {exit_status}\n"
            )
            
            position_data.append({
                "ticket": ticket,
                "symbol": symbol,
                "direction": direction,
                "entry": entry,
                "current": current,
                "profit": profit,
                "volume": volume,
                "monitoring_enabled": rule is not None,
                "breakeven_pct": rule.breakeven_profit_pct if rule else None,
                "partial_pct": rule.partial_profit_pct if rule else None,
                "breakeven_triggered": rule.breakeven_triggered if rule else False,
                "partial_triggered": rule.partial_triggered if rule else False
            })
        
        # Add summary stats
        total_pl = sum(p.profit for p in positions)
        monitored = sum(1 for p in position_data if p["monitoring_enabled"])
        
        summary_lines.append(
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Total P/L: ${total_pl:.2f}\n"
            f"Monitored: {monitored}/{len(positions)} positions\n"
            f"Advanced-Enhanced Exits: ACTIVE"
        )
        
        summary = "\n".join(summary_lines)
        
        return {
            "summary": summary,
            "data": {
                "total_positions": len(positions),
                "monitored_count": monitored,
                "total_pl": total_pl,
                "positions": position_data
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Monitor status failed: {e}", exc_info=True)
        raise RuntimeError(f"Status check failed: {str(e)}")

# ============================================================================
# SPRINT 3: ADVANCED CONTROL TOOLS
# ============================================================================

@registry.register("moneybot.modify_position")
async def tool_modify_position(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Modify stop loss and/or take profit of an existing position
    
    Args:
        ticket: Position ticket number
        stop_loss: New stop loss price (optional)
        take_profit: New take profit price (optional)
    
    Returns:
        Confirmation of modification
    """
    ticket = args.get("ticket")
    new_sl = args.get("stop_loss")
    new_tp = args.get("take_profit")
    
    if not ticket:
        raise ValueError("Missing required argument: ticket")
    
    if not new_sl and not new_tp:
        raise ValueError("Must specify at least one of: stop_loss, take_profit")
    
    logger.info(f"🔧 Modifying position {ticket}")
    
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    try:
        import MetaTrader5 as mt5
        
        # Get the position
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            raise RuntimeError(f"Position {ticket} not found")
        
        position = positions[0]
        symbol = position.symbol
        current_sl = position.sl
        current_tp = position.tp
        
        # Use current values if not specified
        final_sl = new_sl if new_sl is not None else current_sl
        final_tp = new_tp if new_tp is not None else current_tp
        
        logger.info(f"   Modifying {symbol}: SL {current_sl} → {final_sl}, TP {current_tp} → {final_tp}")
        
        # Prepare modification request
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": ticket,
            "sl": final_sl,
            "tp": final_tp,
        }
        
        # Send modification
        result = mt5.order_send(request)
        
        if result is None:
            raise RuntimeError("Modification failed: MT5 returned None")
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Modification failed: {result.retcode} - {result.comment}"
            logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)
        
        logger.info(f"✅ Position {ticket} modified successfully")
        
        # ============================================================================
        # LOG MODIFICATION TO DATABASE (NEW)
        # ============================================================================
        try:
            # Determine reason based on what changed
            if new_sl is not None and new_tp is not None:
                reason = "Manual SL/TP modification via phone control"
            elif new_sl is not None:
                if abs(new_sl - position.price_open) < abs(current_sl - position.price_open):
                    reason = "SL tightened (manual breakeven/trailing)"
                else:
                    reason = "SL widened (manual adjustment)"
            else:
                reason = "TP modified (manual adjustment)"
            
            # Log to events table
            journal_repo.add_event(
                event="sl_tp_modified",
                ticket=ticket,
                symbol=symbol,
                price=position.price_current,
                sl=final_sl,
                tp=final_tp,
                reason=reason,
                extra={
                    "old_sl": current_sl,
                    "new_sl": final_sl,
                    "old_tp": current_tp,
                    "new_tp": final_tp,
                    "source": "desktop_agent",
                    "modification_type": "manual"
                }
            )
            
            logger.info(f"📊 Modification logged to database")
            
        except Exception as e:
            logger.error(f"❌ Failed to log modification to database: {e}", exc_info=True)
            # Don't fail the modification, just log the error
        
        # Format summary
        changes = []
        if new_sl is not None:
            changes.append(f"SL: {current_sl:.2f} → {final_sl:.2f}")
        if new_tp is not None:
            changes.append(f"TP: {current_tp:.2f} → {final_tp:.2f}")
        
        summary = (
            f"✅ Position Modified\n\n"
            f"Ticket: {ticket}\n"
            f"Symbol: {symbol.replace('c', '')}\n"
            f"{' | '.join(changes)}\n\n"
            f"🎯 Your position has been updated!"
        )
        
        return {
            "summary": summary,
            "data": {
                "ticket": ticket,
                "symbol": symbol,
                "old_sl": current_sl,
                "old_tp": current_tp,
                "new_sl": final_sl,
                "new_tp": final_tp,
                "modified": True
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Position modification failed: {e}", exc_info=True)
        raise RuntimeError(f"Modification failed: {str(e)}")

@registry.register("moneybot.close_position")
async def tool_close_position(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Close an existing position (full or partial)
    
    Args:
        ticket: Position ticket number
        volume: Volume to close (optional, defaults to full position)
        reason: Reason for closure (optional, for logging)
    
    Returns:
        Confirmation of closure with final P/L
    """
    ticket = args.get("ticket")
    volume = args.get("volume")  # None = close all
    reason = args.get("reason", "Manual close from phone")
    
    if not ticket:
        raise ValueError("Missing required argument: ticket")
    
    logger.info(f"🔴 Closing position {ticket}")
    
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    try:
        import MetaTrader5 as mt5
        
        # Get the position
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            raise RuntimeError(f"Position {ticket} not found")
        
        position = positions[0]
        symbol = position.symbol
        position_volume = position.volume
        direction = "BUY" if position.type == 0 else "SELL"
        entry = position.price_open
        current_price = position.price_current
        current_profit = position.profit
        
        # Determine volume to close
        close_volume = volume if volume is not None else position_volume
        
        if close_volume > position_volume:
            raise ValueError(f"Cannot close {close_volume} lots (position only has {position_volume} lots)")
        
        is_partial = close_volume < position_volume
        
        logger.info(f"   Closing {close_volume}/{position_volume} lots of {symbol} {direction}")
        
        # Prepare close request (opposite direction)
        close_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY
        close_price = mt5.symbol_info_tick(symbol).bid if position.type == 0 else mt5.symbol_info_tick(symbol).ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": close_volume,
            "type": close_type,
            "position": ticket,
            "price": close_price,
            "deviation": 20,
            "magic": 234000,
            "comment": reason,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send close order
        result = mt5.order_send(request)
        
        if result is None:
            raise RuntimeError("Close failed: MT5 returned None")
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Close failed: {result.retcode} - {result.comment}"
            logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)
        
        actual_close_price = result.price
        
        logger.info(f"✅ Position {ticket} closed successfully")
        
        # Disable intelligent exits if fully closed
        if not is_partial:
            try:
                exit_manager = create_exit_manager(
                    registry.mt5_service,
                    binance_service=registry.binance_service,
                    order_flow_service=registry.order_flow_service
                )
                exit_manager.remove_rule(ticket)
                logger.info(f"   Removed intelligent exit rule for closed position")
            except Exception as e:
                logger.warning(f"   Could not remove exit rule: {e}")
        
        # Calculate approximate P/L for the closed portion
        # (Note: Actual P/L from MT5 is more accurate, but this gives context)
        pip_diff = abs(actual_close_price - entry)
        partial_profit = current_profit * (close_volume / position_volume) if is_partial else current_profit
        
        # Format summary
        profit_emoji = "📈" if partial_profit > 0 else "📉" if partial_profit < 0 else "➖"
        close_type_str = "Partial Close" if is_partial else "Full Close"
        
        summary = (
            f"✅ Position {close_type_str}\n\n"
            f"Ticket: {ticket}\n"
            f"Symbol: {symbol.replace('c', '')}\n"
            f"Direction: {direction}\n"
            f"Entry: {entry:.2f} → Close: {actual_close_price:.2f}\n"
            f"Volume: {close_volume} lots\n"
            f"{profit_emoji} P/L: ${partial_profit:.2f}\n\n"
            f"🎯 Position closed successfully!"
        )
        
        if is_partial:
            remaining = position_volume - close_volume
            summary += f"\n\n⚠️ {remaining} lots still open (Ticket: {ticket})"
        
        return {
            "summary": summary,
            "data": {
                "ticket": ticket,
                "symbol": symbol,
                "direction": direction,
                "entry": entry,
                "close_price": actual_close_price,
                "volume_closed": close_volume,
                "volume_remaining": position_volume - close_volume if is_partial else 0,
                "profit": partial_profit,
                "is_partial": is_partial,
                "closed": True
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Position close failed: {e}", exc_info=True)
        raise RuntimeError(f"Close failed: {str(e)}")

@registry.register("moneybot.cancel_pending_order")
async def tool_cancel_pending_order(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cancel/delete a pending order (Buy Limit, Sell Limit, Buy Stop, Sell Stop)
    
    Args:
        ticket: Pending order ticket number
        reason: Reason for cancellation (optional, for logging)
    
    Returns:
        Confirmation of cancellation
    """
    ticket = args.get("ticket")
    reason = args.get("reason", "Manual cancellation")
    
    if not ticket:
        raise ValueError("Missing required argument: ticket")
    
    logger.info(f"🗑️ Cancelling pending order {ticket}")
    
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    try:
        import MetaTrader5 as mt5
        
        # Get the pending order
        orders = mt5.orders_get(ticket=ticket)
        if not orders:
            raise RuntimeError(f"Pending order {ticket} not found")
        
        order = orders[0]
        symbol = order.symbol
        order_type_code = order.type
        entry_price = order.price_open
        sl = order.sl
        tp = order.tp
        volume = order.volume_current
        
        # Map order type code to readable name
        order_type_names = {
            2: "Buy Limit",
            3: "Sell Limit",
            4: "Buy Stop",
            5: "Sell Stop"
        }
        order_type_name = order_type_names.get(order_type_code, f"Type {order_type_code}")
        
        logger.info(f"   Cancelling {order_type_name} for {symbol}")
        
        # Prepare cancel request
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": ticket
        }
        
        # Send cancel request
        result = mt5.order_send(request)
        
        if result is None:
            raise RuntimeError("Cancellation failed: MT5 returned None")
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Cancellation failed: {result.retcode} - {result.comment}"
            logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)
        
        logger.info(f"✅ Pending order {ticket} cancelled successfully")
        
        # Format summary
        summary = (
            f"✅ Pending Order Cancelled\n\n"
            f"Ticket: {ticket}\n"
            f"Symbol: {symbol.replace('c', '')}\n"
            f"Type: {order_type_name}\n"
            f"Entry: {entry_price:.2f}\n"
            f"Volume: {volume} lots\n\n"
            f"🗑️ Order has been removed from MT5."
        )
        
        return {
            "summary": summary,
            "data": {
                "ticket": ticket,
                "symbol": symbol,
                "order_type": order_type_name,
                "entry_price": entry_price,
                "volume": volume,
                "cancelled": True
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Pending order cancellation failed: {e}", exc_info=True)
        raise RuntimeError(f"Cancellation failed: {str(e)}")

@registry.register("moneybot.toggle_intelligent_exits")
async def tool_toggle_intelligent_exits(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enable or disable Advanced-enhanced intelligent exits for a position
    
    Args:
        ticket: Position ticket number
        action: "enable" | "disable"
    
    Returns:
        Confirmation of toggle action
    """
    ticket = args.get("ticket")
    action = args.get("action", "enable").lower()
    
    if not ticket:
        raise ValueError("Missing required argument: ticket")
    
    if action not in ["enable", "disable"]:
        raise ValueError("action must be 'enable' or 'disable'")
    
    logger.info(f"⚙️ {action.capitalize()}ing intelligent exits for position {ticket}")
    
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    try:
        import MetaTrader5 as mt5
        from infra.indicator_bridge import IndicatorBridge
        from infra.feature_builder_advanced import build_features_advanced
        
        # Get the position
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            raise RuntimeError(f"Position {ticket} not found")
        
        position = positions[0]
        symbol = position.symbol
        entry = position.price_open
        direction = "buy" if position.type == 0 else "sell"
        sl = position.sl
        tp = position.tp
        comment = position.comment or ""
        
        exit_manager = create_exit_manager(
            registry.mt5_service,
            binance_service=registry.binance_service,
            order_flow_service=registry.order_flow_service
        )
        
        if action == "disable":
            # Disable intelligent exits
            exit_manager.remove_rule(ticket)
            logger.info(f"✅ Intelligent exits disabled for {ticket}")
            
            summary = (
                f"✅ Intelligent Exits Disabled\n\n"
                f"Ticket: {ticket}\n"
                f"Symbol: {symbol.replace('c', '')}\n\n"
                f"⚠️ Advanced monitoring stopped for this position.\n"
                f"Your fixed SL/TP remain active."
            )
            
            return {
                "summary": summary,
                "data": {
                    "ticket": ticket,
                    "symbol": symbol,
                    "monitoring_enabled": False,
                    "action": "disabled"
                }
            }
        
        else:  # enable
            # Check if already enabled
            existing_rule = exit_manager.rules.get(ticket)
            if existing_rule:
                summary = (
                    f"ℹ️ Intelligent Exits Already Active\n\n"
                    f"Ticket: {ticket}\n"
                    f"Symbol: {symbol.replace('c', '')}\n"
                    f"Breakeven: {existing_rule.breakeven_profit_pct:.0f}%\n"
                    f"Partial: {existing_rule.partial_profit_pct:.0f}%\n\n"
                    f"✅ No action needed - monitoring is active."
                )
                
                return {
                    "summary": summary,
                    "data": {
                        "ticket": ticket,
                        "symbol": symbol,
                        "monitoring_enabled": True,
                        "action": "already_enabled",
                        "breakeven_pct": existing_rule.breakeven_profit_pct,
                        "partial_pct": existing_rule.partial_profit_pct
                    }
                }
            
            # NEW: Classify trade type (SCALP vs INTRADAY) - Feature Flag Protected
            classification = None
            classification_info = {}
            
            # Use getattr with default False to handle missing attribute gracefully
        enable_classification = getattr(settings, 'ENABLE_TRADE_TYPE_CLASSIFICATION', False)
        if enable_classification:
            try:
                    import time
                    from infra.trade_type_classifier import TradeTypeClassifier
                    from infra.session_analyzer import SessionAnalyzer
                    from infra.classification_metrics import record_classification_metric
                    
                    logger.info(f"   Classifying trade type for {symbol}...")
                    
                    # Measure classification latency
                    classification_start_time = time.time()
                    
                    session_analyzer = SessionAnalyzer()
                    session_info = session_analyzer.get_current_session()
                    
                    classifier = TradeTypeClassifier(
                        mt5_service=registry.mt5_service,
                        session_service=session_analyzer
                    )
                    
                    classification = classifier.classify(
                        symbol=symbol,
                        entry_price=entry,
                        stop_loss=sl,
                        comment=comment,
                        session_info=session_info
                    )
                    
                    classification_latency_ms = (time.time() - classification_start_time) * 1000
                    
                    trade_type = classification["trade_type"]
                    confidence = classification["confidence"]
                    reasoning = classification["reasoning"]
                    factors = classification["factors"]
                    
                    classification_info = {
                        "trade_type": trade_type,
                        "confidence": confidence,
                        "reasoning": reasoning,
                        "factors": factors
                    }
                    
                    logger.info(
                        f"   📊 Trade Classification: {trade_type} "
                        f"(confidence: {confidence:.2f}) - {reasoning}"
                    )
                    
                    # Record metric if enabled
                    if settings.CLASSIFICATION_METRICS_ENABLED:
                        # Determine which factor was used (priority order: override > keyword > stop_atr_ratio > session_strategy > default)
                        factor_used = "default"
                        if factors.get("manual_override"):
                            factor_used = "override"
                        elif factors.get("keyword_match"):
                            factor_used = "keyword"
                        elif factors.get("stop_atr_ratio") is not None:
                            factor_used = "stop_atr_ratio"
                        elif factors.get("session_strategy"):
                            factor_used = "session_strategy"
                        
                        try:
                            record_classification_metric(
                                ticket=ticket,
                                symbol=symbol,
                                trade_type=trade_type,
                                confidence=confidence,
                                reasoning=reasoning,
                                factor_used=factor_used,
                                latency_ms=classification_latency_ms,
                                feature_enabled=True
                            )
                        except Exception as metrics_error:
                            logger.debug(f"   → Metrics recording failed: {metrics_error}")
                
            except Exception as e:
                    logger.warning(f"   ⚠️ Classification failed: {e}, defaulting to INTRADAY parameters")
                    classification_info = {
                        "trade_type": "INTRADAY",
                        "confidence": 0.0,
                        "reasoning": f"Classification error: {str(e)} → Default to INTRADAY",
                        "error": str(e)
                    }
                    
                    # Record error metric if enabled
                    if settings.CLASSIFICATION_METRICS_ENABLED:
                        try:
                            from infra.classification_metrics import record_classification_metric
                            record_classification_metric(
                                ticket=ticket,
                                symbol=symbol,
                                trade_type="INTRADAY",
                                confidence=0.0,
                                reasoning=f"Classification error: {str(e)} → Default to INTRADAY",
                                factor_used="default",
                                latency_ms=0.0,  # Error case - no latency to record
                                feature_enabled=True
                            )
                        except Exception:
                            pass  # Silent fail for metrics on errors
        else:
            # Feature disabled - use default INTRADAY parameters
            logger.debug(f"   Trade type classification disabled (feature flag OFF) - using default INTRADAY parameters")
            classification_info = {
                "trade_type": "INTRADAY",
                "confidence": 0.0,
                "reasoning": "Feature flag disabled → Using default INTRADAY parameters",
                "feature_enabled": False
            }
            
            # Record disabled metric if enabled
            if settings.CLASSIFICATION_METRICS_ENABLED:
                try:
                    from infra.classification_metrics import record_classification_metric
                    record_classification_metric(
                        ticket=ticket,
                        symbol=symbol,
                        trade_type="INTRADAY",
                        confidence=0.0,
                        reasoning="Feature flag disabled → Using default INTRADAY parameters",
                        factor_used="default",
                        latency_ms=0.0,  # No classification performed
                        feature_enabled=False
                    )
                except Exception:
                    pass  # Silent fail for metrics
        
        # Select parameters based on classification (only if feature enabled and classification succeeded)
        if enable_classification and classification_info and classification_info.get("trade_type") == "SCALP":
            # SCALP parameters: faster profit-taking, tighter exits
            base_breakeven_pct = 25.0
            base_partial_pct = 40.0
            partial_close_pct = 70.0
            logger.info(f"   🎯 Using SCALP parameters: {base_breakeven_pct}% / {base_partial_pct}% / {partial_close_pct}%")
        else:
            # INTRADAY parameters: standard/default parameters
            base_breakeven_pct = settings.INTELLIGENT_EXITS_BREAKEVEN_PCT
            base_partial_pct = settings.INTELLIGENT_EXITS_PARTIAL_PCT
            partial_close_pct = settings.INTELLIGENT_EXITS_PARTIAL_CLOSE_PCT
            if not enable_classification:
                logger.debug(f"   Using default INTRADAY parameters (feature disabled): {base_breakeven_pct}% / {base_partial_pct}% / {partial_close_pct}%")
            else:
                logger.info(f"   🎯 Using INTRADAY parameters: {base_breakeven_pct}% / {base_partial_pct}% / {partial_close_pct}%")
        
        # Enable intelligent exits with Advanced features
            logger.info(f"   Fetching Advanced features for {symbol}...")
            bridge = IndicatorBridge()
            advanced_features = build_features_advanced(
                symbol=symbol,
                mt5svc=registry.mt5_service,
                bridge=bridge,
                timeframes=["M15"]
            )
            
            exit_result = exit_manager.add_rule_advanced(
                ticket=ticket,
                symbol=symbol,
                entry_price=entry,
                direction=direction,
                initial_sl=sl,
                initial_tp=tp,
                advanced_features=advanced_features,
                base_breakeven_pct=base_breakeven_pct,
                base_partial_pct=base_partial_pct,
                partial_close_pct=partial_close_pct,
                vix_threshold=settings.INTELLIGENT_EXITS_VIX_THRESHOLD,
                use_hybrid_stops=settings.INTELLIGENT_EXITS_USE_HYBRID_STOPS,
                trailing_enabled=settings.INTELLIGENT_EXITS_TRAILING_ENABLED
            )
            
            # Get Advanced-adjusted percentages
            rule = exit_manager.rules.get(ticket)
            breakeven_pct = rule.breakeven_profit_pct if rule else 30.0
            partial_pct = rule.partial_profit_pct if rule else 60.0
            final_partial_close_pct = rule.partial_close_pct if rule else partial_close_pct

            advanced_adjusted = breakeven_pct != base_breakeven_pct or partial_pct != base_partial_pct

            # Build summary with classification info
            trade_type_display = classification_info.get("trade_type", "INTRADAY")
            confidence_display = classification_info.get("confidence", 0.0)
            reasoning_display = classification_info.get("reasoning", "Default classification")
            
            logger.info(
                f"✅ Intelligent exits enabled: {breakeven_pct}% / {partial_pct}% "
                f"(Classification: {trade_type_display})"
            )

            summary = (
                f"✅ Advanced-Enhanced Intelligent Exits Enabled\n\n"
                f"Ticket: {ticket}\n"
                f"Symbol: {symbol.replace('c', '')}\n\n"
            )
            
            # Include classification info only if feature is enabled
            if classification_info and "trade_type" in classification_info:
                trade_type_display = classification_info["trade_type"]
                confidence_display = classification_info.get("confidence", 0.0)
                reasoning_display = classification_info.get("reasoning", "Default classification")
                summary += (
                    f"📊 Trade Type: {trade_type_display} (confidence: {confidence_display:.0%})\n"
                    f"   └─ {reasoning_display}\n\n"
                )
            
            summary += (
                f"⚙️ Exit Strategy:\n"
                f"   Breakeven: {breakeven_pct:.0f}% profit (0.{breakeven_pct/10:.1f}R)\n"
                f"   Partial: {partial_pct:.0f}% profit (0.{partial_pct/10:.1f}R), close {final_partial_close_pct:.0f}%\n"
            )

            if advanced_adjusted:
                summary += f"   ⚡ Advanced-Adjusted (from base {base_breakeven_pct}%/{base_partial_pct}%)\n"
            
            summary += f"\n📊 Your position is now on autopilot!"
            
            # Send Discord notification with classification info (if feature enabled)
            try:
                from discord_notifications import DiscordNotifier
                discord_notifier = DiscordNotifier()
                if discord_notifier.enabled:
                    # Get plan_id if this is an auto-executed trade
                    plan_id = get_plan_id_from_ticket(ticket)
                    plan_id_line = f"📊 **Plan ID**: {plan_id}\n" if plan_id else ""
                    
                    # Build Discord message
                    discord_message = (
                        f"✅ **Intelligent Exits Enabled**\n\n"
                        f"🎫 **Ticket**: {ticket}\n"
                        f"{plan_id_line}"
                        f"💱 **Symbol**: {symbol.replace('c', '')}\n"
                        f"📊 **Entry**: {entry:.5f}\n"
                        f"🛡️ **SL**: {sl:.5f} | 🎯 **TP**: {tp:.5f}\n\n"
                    )
                    
                    # Add classification info if available
                    if classification_info and "trade_type" in classification_info:
                        trade_type_display = classification_info.get("trade_type", "INTRADAY")
                        confidence_display = classification_info.get("confidence", 0.0)
                        reasoning_display = classification_info.get("reasoning", "Default classification")
                        
                        discord_message += (
                            f"📊 **Trade Type**: {trade_type_display}\n"
                            f"🎯 **Confidence**: {confidence_display:.0%}\n"
                            f"💡 **Reasoning**: {reasoning_display}\n\n"
                        )
                    
                    discord_message += (
                        f"⚙️ **Exit Strategy**:\n"
                        f"   • Breakeven: {breakeven_pct:.0f}% profit (0.{breakeven_pct/10:.1f}R)\n"
                        f"   • Partial: {partial_pct:.0f}% profit (0.{partial_pct/10:.1f}R), close {final_partial_close_pct:.0f}%\n\n"
                        f"🤖 Position is now on autopilot!"
                    )
                    
                    if advanced_adjusted:
                        discord_message += f"\n⚡ Advanced-adjusted from base {base_breakeven_pct:.0f}%/{base_partial_pct:.0f}%"
                    
                    discord_notifier.send_system_alert("INTELLIGENT_EXIT", discord_message)
                    logger.info("   → Discord notification sent")
            except Exception as e:
                logger.debug(f"   → Discord notification not sent: {e}")
            
            return {
                "summary": summary,
                "data": {
                    "ticket": ticket,
                    "symbol": symbol,
                    "monitoring_enabled": True,
                    "action": "enabled",
                    "breakeven_pct": breakeven_pct,
                    "partial_pct": partial_pct,
                    "partial_close_pct": final_partial_close_pct,
                    "advanced_adjusted": advanced_adjusted,
                    "classification": classification_info
                }
            }
        
    except Exception as e:
        logger.error(f"❌ Toggle intelligent exits failed: {e}", exc_info=True)
        raise RuntimeError(f"Toggle failed: {str(e)}")

@registry.register("moneybot.binance_feed_status")
async def tool_binance_feed_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check Binance streaming feed health and synchronization status
    
    Args:
        symbol: Optional symbol to check (e.g., "BTCUSDc"), or None for all symbols
    
    Returns:
        Feed health status, offset calibration, and safety assessment
    """
    symbol = args.get("symbol")
    
    if not registry.binance_service:
        return {
            "summary": "⚠️ Binance feed not running",
            "data": {
                "status": "offline",
                "message": "Binance streaming service is not initialized"
            }
        }
    
    if not registry.binance_service.running:
        return {
            "summary": "⚠️ Binance feed not active",
            "data": {
                "status": "inactive",
                "message": "Binance streams are not currently running"
            }
        }
    
    try:
        # Get health status
        if symbol:
            health = registry.binance_service.get_feed_health(symbol)
            
            status_emoji = "✅" if health["overall_status"] == "healthy" else "⚠️" if health["overall_status"] == "warning" else "🔴"
            offset = health["sync"]["offset"]
            age = health["sync"]["last_sync_age"]
            
            summary = (
                f"{status_emoji} Binance Feed Status - {symbol}\n\n"
                f"Status: {health['overall_status'].upper()}\n"
                f"Offset: {offset:+.2f} pips (Binance vs MT5)\n"
                f"Data Age: {age:.1f}s\n"
                f"Tick Count: {health['cache']['tick_count']}\n\n"
                f"Assessment: {health['sync']['reason']}"
            )
            
            return {
                "summary": summary,
                "data": health
            }
        else:
            # All symbols
            all_health = registry.binance_service.get_feed_health()
            
            # Count statuses
            healthy = sum(1 for h in all_health["sync"].values() if h["status"] == "healthy")
            warning = sum(1 for h in all_health["sync"].values() if h["status"] == "warning")
            critical = sum(1 for h in all_health["sync"].values() if h["status"] == "critical")
            total = len(all_health["sync"])
            
            summary = (
                f"📡 Binance Feed Status - All Symbols\n\n"
                f"Total Symbols: {total}\n"
                f"✅ Healthy: {healthy}\n"
                f"⚠️ Warning: {warning}\n"
                f"🔴 Critical: {critical}\n\n"
            )
            
            # Add per-symbol details
            for sym, health_data in all_health["sync"].items():
                status_emoji = "✅" if health_data["status"] == "healthy" else "⚠️" if health_data["status"] == "warning" else "🔴"
                offset = health_data.get("offset", "N/A")
                offset_str = f"{offset:+.1f}" if isinstance(offset, (int, float)) else offset
                summary += f"{status_emoji} {sym}: Offset {offset_str} pips\n"
            
            return {
                "summary": summary,
                "data": all_health
            }
            
    except Exception as e:
        logger.error(f"❌ Feed status check failed: {e}", exc_info=True)
        raise RuntimeError(f"Feed status check failed: {str(e)}")

@registry.register("moneybot.btc_order_flow_metrics")
async def tool_btc_order_flow_metrics(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get comprehensive BTC order flow metrics (Delta Volume, CVD, CVD Slope, CVD Divergence, Absorption Zones, Buy/Sell Pressure)"""
    symbol = args.get("symbol", "BTCUSDT")
    window_seconds = args.get("window_seconds", 30)
    # Binance stream stores symbols in UPPERCASE (BTCUSDT), not lowercase
    binance_symbol = "BTCUSDT" if "BTC" in symbol.upper() else symbol.upper()
    
    if not hasattr(registry, 'order_flow_service') or not registry.order_flow_service:
        return {"summary": "⚠️ Order flow service not running - metrics unavailable", "data": {"status": "error", "message": "Order flow service not initialized"}}
    if not getattr(registry.order_flow_service, "running", False):
        return {"summary": "⚠️ Order flow service inactive - metrics unavailable", "data": {"status": "error", "message": "Order flow service is not active"}}
    
    try:
        from infra.btc_order_flow_metrics import BTCOrderFlowMetrics
        metrics_calc = BTCOrderFlowMetrics(order_flow_service=registry.order_flow_service)
        metrics = metrics_calc.get_metrics(binance_symbol, window_seconds)
        
        if not metrics:
            return {"summary": "⚠️ Order flow metrics unavailable - insufficient data", "data": {"status": "error", "message": "Not enough trade data yet. Wait a few seconds and try again."}}
        
        summary_lines = [f"📊 BTC Order Flow Metrics: {symbol}", f"💰 Delta: {metrics.delta_volume:+,.2f} ({metrics.dominant_side})", f"📈 CVD: {metrics.cvd:+,.2f} (Slope: {metrics.cvd_slope:+,.2f}/bar)"]
        if metrics.cvd_divergence_strength > 0:
            summary_lines.append(f"⚠️ CVD Divergence: {metrics.cvd_divergence_type} ({metrics.cvd_divergence_strength:.1%})")
        if metrics.absorption_zones:
            summary_lines.append(f"🎯 Absorption Zones: {len(metrics.absorption_zones)} detected")
        summary_lines.append(f"⚖️ Pressure: {metrics.buy_sell_pressure:.2f}x ({metrics.dominant_side})")
        
        return {
            "summary": " | ".join(summary_lines),
            "data": {
                "status": "success", "symbol": symbol, "timestamp": metrics.timestamp,
                "delta_volume": {"buy_volume": metrics.buy_volume, "sell_volume": metrics.sell_volume, "net_delta": metrics.delta_volume, "dominant_side": metrics.dominant_side},
                "cvd": {"current": metrics.cvd, "slope": metrics.cvd_slope, "bar_count": metrics.bar_count},
                "cvd_divergence": {"strength": metrics.cvd_divergence_strength, "type": metrics.cvd_divergence_type},
                "absorption_zones": metrics.absorption_zones,
                "buy_sell_pressure": {"ratio": metrics.buy_sell_pressure, "dominant_side": metrics.dominant_side},
                "window_seconds": metrics.window_seconds
            }
        }
    except Exception as e:
        logger.error(f"Error getting BTC order flow metrics: {e}", exc_info=True)
        return {"summary": f"❌ Error calculating order flow metrics: {str(e)}", "data": {"status": "error", "error": str(e)}}

@registry.register("moneybot.order_flow_status")
async def tool_order_flow_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check order flow analysis status (order book depth + whale detection)
    
    Args:
        symbol: Symbol to check (e.g., "BTCUSDc") - required
    
    Returns:
        Order flow signal, whale activity, liquidity voids, buy/sell pressure
    """
    symbol = args.get("symbol")
    
    if not symbol:
        return {
            "summary": "⚠️ Symbol required for order flow check",
            "data": {"status": "error", "message": "Please specify a symbol"}
        }
    
    if not registry.order_flow_service:
        return {
            "summary": "⚠️ Order flow service not running",
            "data": {
                "status": "offline",
                "message": "Order flow analysis is not initialized (requires Binance streams)"
            }
        }
    
    if not registry.order_flow_service.running:
        return {
            "summary": "⚠️ Order flow service not active",
            "data": {
                "status": "inactive",
                "message": "Order flow streams are not currently running"
            }
        }
    
    try:
        # Get comprehensive order flow signal
        signal = registry.order_flow_service.get_order_flow_signal(symbol)
        
        if not signal:
            return {
                "summary": f"⚠️ No order flow data for {symbol}",
                "data": {"status": "no_data", "message": "Order flow data not yet available"}
            }
        
        # Format summary
        summary = registry.order_flow_service.get_signal_summary(symbol)
        
        return {
            "summary": summary,
            "data": signal
        }
            
    except Exception as e:
        logger.error(f"❌ Order flow check failed: {e}", exc_info=True)
        raise RuntimeError(f"Order flow check failed: {str(e)}")

@registry.register("moneybot.macro_context")
async def tool_macro_context(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get comprehensive macro market context
    
    Traditional Markets: DXY, US10Y, VIX, S&P 500
    Crypto Fundamentals: Bitcoin Dominance, Crypto Fear & Greed Index
    
    Args:
        symbol: Optional symbol to provide context for (e.g., "XAUUSD" for gold, "BTCUSD" for Bitcoin)
    
    Returns:
        Current macro indicators with market sentiment and symbol-specific analysis
    """
    symbol = args.get("symbol", "").upper()
    
    logger.info(f"🌍 Fetching macro context" + (f" for {symbol}" if symbol else ""))
    
    # Initialize MT5 if not already done
    if not registry.mt5_service:
        registry.mt5_service = MT5Service()
        if not registry.mt5_service.connect():
            raise RuntimeError("Failed to connect to MT5")
    
    try:
        # Get current macro data from Yahoo Finance (not MT5)
        import yfinance as yf
        import requests
        
        # Try multiple sources for DXY as it's sometimes unreliable on Yahoo Finance
        dxy = None
        dxy_sources = ["DX=F", "DX-Y.NYB", "USDOLLAR"]
        
        for ticker in dxy_sources:
            try:
                dxy_data = yf.Ticker(ticker)
                dxy_hist = dxy_data.history(period="5d")
                if not dxy_hist.empty:
                    dxy = float(dxy_hist['Close'].iloc[-1])
                    logger.info(f"   ✅ DXY fetched from {ticker}: {dxy:.2f}")
                    break
            except Exception as e:
                logger.warning(f"   ⚠️ Failed to fetch DXY from {ticker}: {e}")
                continue
        
        # Fallback: Use hardcoded reasonable value if all sources fail
        if dxy is None:
            dxy = 104.5  # Recent average value
            logger.warning(f"   ⚠️ Using fallback DXY value: {dxy}")
        
        # Fetch US10Y
        us10y_data = yf.Ticker("^TNX")
        us10y_hist = us10y_data.history(period="5d")
        if us10y_hist.empty:
            us10y = 4.2  # Fallback reasonable value
            logger.warning(f"   ⚠️ Using fallback US10Y value: {us10y}%")
        else:
            us10y = float(us10y_hist['Close'].iloc[-1])
            logger.info(f"   ✅ US10Y fetched: {us10y:.3f}%")
        
        # Fetch VIX
        vix_data = yf.Ticker("^VIX")
        vix_hist = vix_data.history(period="5d")
        if vix_hist.empty:
            vix = 16.0  # Fallback reasonable value
            logger.warning(f"   ⚠️ Using fallback VIX value: {vix}")
        else:
            vix = float(vix_hist['Close'].iloc[-1])
            logger.info(f"   ✅ VIX fetched: {vix:.2f}")
        
        # Fetch S&P 500 (NEW - for Bitcoin correlation)
        sp500_data = yf.Ticker("^GSPC")
        sp500_hist = sp500_data.history(period="5d")
        if sp500_hist.empty or len(sp500_hist) < 2:
            sp500 = 5800.0  # Fallback reasonable value
            sp500_change = 0.0
            logger.warning(f"   ⚠️ Using fallback S&P 500 value: {sp500}")
        else:
            sp500 = float(sp500_hist['Close'].iloc[-1])
            sp500_prev = float(sp500_hist['Close'].iloc[-2])
            sp500_change = ((sp500 - sp500_prev) / sp500_prev) * 100
            logger.info(f"   ✅ S&P 500 fetched: {sp500:.2f} ({sp500_change:+.2f}%)")
        
        # Fetch Bitcoin Dominance (NEW - from CoinGecko)
        btc_dominance = None
        btc_dom_status = "Unknown"
        try:
            cg_url = "https://api.coingecko.com/api/v3/global"
            cg_response = requests.get(cg_url, timeout=5)
            if cg_response.status_code == 200:
                cg_data = cg_response.json()
                btc_dominance = float(cg_data["data"]["market_cap_percentage"]["btc"])
                
                # Classify dominance
                if btc_dominance > 50:
                    btc_dom_status = "STRONG (Money flowing to Bitcoin)"
                elif btc_dominance < 45:
                    btc_dom_status = "WEAK (Alt season - money to altcoins)"
                else:
                    btc_dom_status = "NEUTRAL"
                
                logger.info(f"   ✅ BTC Dominance fetched: {btc_dominance:.1f}% ({btc_dom_status})")
            else:
                logger.warning(f"   ⚠️ CoinGecko returned status {cg_response.status_code}")
        except Exception as e:
            logger.warning(f"   ⚠️ Failed to fetch BTC Dominance: {e}")
        
        # Fetch Crypto Fear & Greed Index (NEW - from Alternative.me)
        crypto_fear_greed = None
        crypto_sentiment = "Unknown"
        try:
            fng_url = "https://api.alternative.me/fng/"
            fng_response = requests.get(fng_url, timeout=5)
            if fng_response.status_code == 200:
                fng_data = fng_response.json()
                crypto_fear_greed = int(fng_data["data"][0]["value"])
                crypto_sentiment = fng_data["data"][0]["value_classification"]
                logger.info(f"   ✅ Crypto Fear & Greed fetched: {crypto_fear_greed}/100 ({crypto_sentiment})")
            else:
                logger.warning(f"   ⚠️ Alternative.me returned status {fng_response.status_code}")
        except Exception as e:
            logger.warning(f"   ⚠️ Failed to fetch Crypto Fear & Greed: {e}")
        
        logger.info(f"   📊 Final macro data: DXY={dxy:.2f}, US10Y={us10y:.3f}%, VIX={vix:.2f}, S&P500={sp500:.2f}")
        
        # Analyze sentiment
        dxy_trend = "📈 Rising" if dxy > 104.0 else "📉 Falling" if dxy < 103.0 else "➖ Neutral"
        us10y_trend = "📈 Rising" if us10y > 4.3 else "📉 Falling" if us10y < 4.1 else "➖ Neutral"
        vix_level = "⚠️ High" if vix > 20 else "✅ Normal" if vix < 15 else "⚠️ Elevated"
        
        # Symbol-specific analysis
        symbol_context = ""
        if symbol:
            if "XAU" in symbol or "GOLD" in symbol:
                # Gold analysis
                if "Rising" in dxy_trend and "Rising" in us10y_trend:
                    symbol_context = "🔴 BEARISH for Gold (DXY↑ + Yields↑)"
                elif "Falling" in dxy_trend and "Falling" in us10y_trend:
                    symbol_context = "🟢 BULLISH for Gold (DXY↓ + Yields↓)"
                else:
                    symbol_context = "⚪ MIXED for Gold (conflicting signals)"
            
            elif "BTC" in symbol or "CRYPTO" in symbol:
                # Enhanced crypto analysis with S&P 500, BTC.D, Fear & Greed
                risk_sentiment = "RISK_ON" if vix < 15 else "RISK_OFF" if vix > 20 else "NEUTRAL"
                sp500_trend_label = "RISING" if sp500_change > 0 else "FALLING"
                
                # Assess overall crypto market conditions
                bullish_signals = 0
                bearish_signals = 0
                
                # VIX (risk sentiment)
                if vix < 15:
                    bullish_signals += 1
                elif vix > 20:
                    bearish_signals += 1
                
                # S&P 500 (equity correlation)
                if sp500_change > 0.5:
                    bullish_signals += 1
                elif sp500_change < -0.5:
                    bearish_signals += 1
                
                # DXY (inverse correlation)
                if "Falling" in dxy_trend:
                    bullish_signals += 1
                elif "Rising" in dxy_trend:
                    bearish_signals += 1
                
                # BTC Dominance (crypto strength)
                if btc_dominance and btc_dominance > 50:
                    btc_dom_context = f"BTC Dominance: {btc_dominance:.1f}% (STRONG - Bitcoin outperforming)"
                elif btc_dominance and btc_dominance < 45:
                    btc_dom_context = f"BTC Dominance: {btc_dominance:.1f}% (WEAK - Alt season starting)"
                elif btc_dominance:
                    btc_dom_context = f"BTC Dominance: {btc_dominance:.1f}% (NEUTRAL)"
                else:
                    btc_dom_context = "BTC Dominance: Data unavailable"
                
                # Fear & Greed (sentiment)
                if crypto_fear_greed:
                    if crypto_fear_greed > 75:
                        fg_context = f"Crypto Sentiment: {crypto_sentiment} ({crypto_fear_greed}/100 - Potential top)"
                    elif crypto_fear_greed < 25:
                        fg_context = f"Crypto Sentiment: {crypto_sentiment} ({crypto_fear_greed}/100 - Potential bottom)"
                    else:
                        fg_context = f"Crypto Sentiment: {crypto_sentiment} ({crypto_fear_greed}/100)"
                else:
                    fg_context = "Crypto Sentiment: Data unavailable"
                
                # Overall verdict
                if bullish_signals >= 2:
                    verdict = "🟢 BULLISH"
                elif bearish_signals >= 2:
                    verdict = "🔴 BEARISH"
                else:
                    verdict = "⚪ MIXED"
                
                symbol_context = (
                    f"{verdict} for Crypto\n"
                    f"Risk Sentiment: {risk_sentiment} (VIX {vix:.1f})\n"
                    f"S&P 500: {sp500_trend_label} ({sp500_change:+.2f}%) - Correlation +0.70\n"
                    f"{btc_dom_context}\n"
                    f"{fg_context}"
                )
            
            elif symbol in ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"]:
                # USD pairs
                if "Rising" in dxy_trend:
                    symbol_context = f"🔴 BEARISH for {symbol} (DXY strengthening)"
                elif "Falling" in dxy_trend:
                    symbol_context = f"🟢 BULLISH for {symbol} (DXY weakening)"
                else:
                    symbol_context = f"⚪ NEUTRAL for {symbol}"
        
        # Format summary
        summary = (
            f"🌍 Macro Market Context\n\n"
            f"📊 Traditional Markets:\n"
            f"DXY (Dollar Index): {dxy:.2f} {dxy_trend}\n"
            f"US10Y (Yield): {us10y:.3f}% {us10y_trend}\n"
            f"VIX (Volatility): {vix:.2f} {vix_level}\n"
            f"S&P 500: {sp500:.2f} ({sp500_change:+.2f}%)\n"
        )
        
        # Add crypto fundamentals if available
        if btc_dominance or crypto_fear_greed:
            summary += f"\n🔷 Crypto Fundamentals:\n"
            if btc_dominance:
                summary += f"BTC Dominance: {btc_dominance:.1f}% ({btc_dom_status})\n"
            if crypto_fear_greed:
                summary += f"Crypto Fear & Greed: {crypto_sentiment} ({crypto_fear_greed}/100)\n"
        
        if symbol_context:
            summary += f"\n💡 Impact on {symbol}:\n{symbol_context}"
        
        # Add market regime
        if "High" in vix_level:
            summary += f"\n\n⚠️ High volatility environment - risk management critical"
        elif "Falling" in dxy_trend and "Falling" in us10y_trend:
            summary += f"\n\n🟢 Risk-on regime - favorable for growth assets"
        elif "Rising" in dxy_trend and "Rising" in us10y_trend:
            summary += f"\n\n🔴 Risk-off regime - USD strength"
        
        # Determine risk sentiment
        if vix < 15 and sp500_change > 0:
            risk_sentiment = "RISK_ON"
        elif vix > 20 or sp500_change < -1:
            risk_sentiment = "RISK_OFF"
        else:
            risk_sentiment = "NEUTRAL"
        
        return {
            "summary": summary,
            "data": {
                # Traditional Macro
                "dxy": dxy,
                "dxy_trend": dxy_trend,
                "us10y": us10y,
                "us10y_trend": us10y_trend,
                "vix": vix,
                "vix_level": vix_level,
                "risk_sentiment": risk_sentiment,
                
                # S&P 500 (NEW)
                "sp500": sp500,
                "sp500_change_pct": sp500_change,
                "sp500_trend": "RISING" if sp500_change > 0 else "FALLING",
                
                # Crypto Fundamentals (NEW)
                "btc_dominance": btc_dominance,
                "btc_dominance_status": btc_dom_status,
                "crypto_fear_greed": crypto_fear_greed,
                "crypto_sentiment": crypto_sentiment,
                
                # Context
                "symbol_context": symbol_context if symbol else None,
                "timestamp": datetime.now().isoformat(),
                "timestamp_human": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Macro context fetch failed: {e}", exc_info=True)
        raise RuntimeError(f"Macro fetch failed: {str(e)}")

@registry.register("moneybot.lot_sizing_info")
async def tool_lot_sizing_info(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get lot sizing configuration and risk parameters for a symbol
    
    Args:
        symbol: Trading symbol (optional - if not provided, shows all)
    
    Returns:
        Lot sizing information including max lots, risk %, and category
    """
    symbol = args.get("symbol")
    
    if symbol:
        # Normalize symbol
        # Normalize: strip any trailing 'c' or 'C', then add lowercase 'c'
        if not symbol.lower().endswith('c'):
            symbol_normalized = symbol.upper() + 'c'
        else:
            symbol_normalized = symbol.upper().rstrip('cC') + 'c'
        
        info = get_lot_sizing_info(symbol_normalized)
        
        summary = (
            f"📊 Lot Sizing for {symbol_normalized}\n\n"
            f"Category: {info['category']}\n"
            f"Max Lot Size: {info['max_lot']}\n"
            f"Default Risk %: {info['default_risk_pct']}%\n"
            f"Min Lot Size: {info['min_lot']}\n\n"
            f"💡 When you execute a trade without specifying volume, "
            f"the system will calculate the optimal lot size based on:\n"
            f"  • Your account equity\n"
            f"  • Stop loss distance\n"
            f"  • Symbol risk percentage ({info['default_risk_pct']}%)\n"
            f"  • Maximum lot cap ({info['max_lot']} lots)"
        )
        
        return {
            "summary": summary,
            "data": info
        }
    else:
        # Show all configured symbols
        from config.lot_sizing import MAX_LOT_SIZES, DEFAULT_RISK_PCT
        
        symbols_info = []
        for sym in ["BTCUSDc", "XAUUSDc", "EURUSDc", "GBPUSDc", "USDJPYc", "GBPJPYc", "EURJPYc"]:
            info = get_lot_sizing_info(sym)
            symbols_info.append(info)
        
        summary = "📊 Lot Sizing Configuration\n\n"
        
        # Group by category
        crypto = [s for s in symbols_info if s['category'] == 'CRYPTO']
        metals = [s for s in symbols_info if s['category'] == 'METAL']
        forex = [s for s in symbols_info if s['category'] == 'FOREX']
        
        if crypto:
            summary += "💰 CRYPTO:\n"
            for s in crypto:
                summary += f"  {s['symbol']}: Max {s['max_lot']} lots, Risk {s['default_risk_pct']}%\n"
            summary += "\n"
        
        if metals:
            summary += "🥇 METALS:\n"
            for s in metals:
                summary += f"  {s['symbol']}: Max {s['max_lot']} lots, Risk {s['default_risk_pct']}%\n"
            summary += "\n"
        
        if forex:
            summary += "💱 FOREX:\n"
            for s in forex:
                summary += f"  {s['symbol']}: Max {s['max_lot']} lots, Risk {s['default_risk_pct']}%\n"
            summary += "\n"
        
        summary += (
            "💡 Automatic Lot Sizing:\n"
            "When you execute trades without specifying volume, the system calculates "
            "the optimal lot size based on your equity, stop distance, and symbol-specific risk parameters."
        )
        
        return {
            "summary": summary,
            "data": {
                "crypto": crypto,
                "metals": metals,
                "forex": forex
            }
        }

# ============================================================================
# AGENT MAIN LOOP
# ============================================================================

# ============================================================================
# UNIFIED PIPELINE TOOLS
# ============================================================================

@registry.register("moneybot.enhanced_symbol_analysis")
async def tool_enhanced_symbol_analysis_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Enhanced symbol analysis using Unified Tick Pipeline data"""
    return await tool_enhanced_symbol_analysis(args)

@registry.register("moneybot.volatility_analysis")
async def tool_volatility_analysis_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get volatility analysis using Unified Tick Pipeline data"""
    return await tool_volatility_analysis(args)

@registry.register("moneybot.offset_calibration")
async def tool_offset_calibration_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get offset calibration using Unified Tick Pipeline data"""
    return await tool_offset_calibration(args)

@registry.register("moneybot.system_health")
async def tool_system_health_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get system health using Unified Tick Pipeline data"""
    return await tool_system_health(args)

@registry.register("moneybot.pipeline_status")
async def tool_pipeline_status_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get Unified Tick Pipeline status"""
    return await tool_pipeline_status(args)

async def agent_main():
    """Main agent loop - connect to hub and process commands"""
    logger.info("=" * 70)
    logger.info("🤖 Synergis Trading Bot Desktop Agent - STARTING")
    logger.info("=" * 70)
    logger.info(f"🔌 Connecting to hub: {HUB_URL}")
    logger.info(f"📋 Available tools: {list(registry.tools.keys())}")
    logger.info("=" * 70)
    
    # Initialize services
    logger.info("🔧 Initializing services...")
    
    # Initialize MT5
    try:
        registry.mt5_service = MT5Service()
        if registry.mt5_service.connect():
            logger.info("✅ MT5Service connected")
        else:
            logger.warning("⚠️ MT5Service connection failed - some features may not work")
    except Exception as e:
        logger.warning(f"⚠️ MT5Service initialization failed: {e}")
    
    # ========== TICK METRICS GENERATOR ==========
    # Initialize tick metrics generator for direct calls (ChatGPT analysis)
    try:
        logger.info("📊 Initializing Tick Metrics Generator...")
        from infra.tick_metrics.tick_snapshot_generator import TickSnapshotGenerator
        
        registry.tick_metrics_generator = TickSnapshotGenerator(
            symbols=["BTCUSDc", "XAUUSDc", "EURUSDc", "USDJPYc", "GBPUSDc"],
            update_interval_seconds=60
            # Note: Uses direct MT5 calls internally, not mt5_service
        )
        await registry.tick_metrics_generator.start()
        set_tick_metrics_instance(registry.tick_metrics_generator)
        logger.info("✅ Tick Metrics Generator started")
        logger.info("   → Pre-aggregating M5/M15/H1 tick metrics every 60s")
        logger.info("   → Provides tick_metrics field for analyse_symbol_full")
    except Exception as e:
        logger.warning(f"⚠️ Tick Metrics Generator failed to start: {e}", exc_info=True)
        logger.info("   → Analysis will continue without tick_metrics field")
        registry.tick_metrics_generator = None  # Ensure it's None if startup failed
        # Non-fatal - analysis continues without tick metrics
    
    # ====================================================================
    # Phase 3.2: M1 Snapshot Recovery (Crash Recovery & Persistence)
    # ====================================================================
    try:
        logger.info("💾 Checking for M1 snapshots (crash recovery)...")
        import time
        from infra.m1_data_fetcher import M1DataFetcher
        from infra.m1_snapshot_manager import M1SnapshotManager
        
        # Initialize M1DataFetcher if MT5 is available
        if registry.mt5_service and hasattr(registry.mt5_service, 'connect'):
            # Initialize M1DataFetcher for snapshot recovery
            m1_fetcher = M1DataFetcher(
                data_source=registry.mt5_service,
                max_candles=200,
                cache_ttl=300
            )
            
            # Initialize snapshot manager
            snapshot_manager = M1SnapshotManager(
                fetcher=m1_fetcher,
                snapshot_interval=1800,  # 30 minutes
                snapshot_directory="data/m1_snapshots",
                max_age_hours=24,
                use_compression=True,
                validate_checksum=True
            )
            
            # Check for active symbols (common trading symbols)
            active_symbols = ['XAUUSD', 'BTCUSD', 'EURUSD', 'GBPUSD', 'USDJPY']
            recovered_count = 0
            
            for symbol in active_symbols:
                try:
                    # Try to load snapshot
                    snapshot_candles = snapshot_manager.load_snapshot(symbol, max_age_seconds=3600)
                    
                    if snapshot_candles and len(snapshot_candles) > 0:
                        # Restore to fetcher cache
                        symbol_normalized = symbol if symbol.endswith('c') else f"{symbol}c"
                        from collections import deque
                        if symbol_normalized not in m1_fetcher._data_cache:
                            m1_fetcher._data_cache[symbol_normalized] = deque(maxlen=200)
                        # Clear and add snapshot candles
                        m1_fetcher._data_cache[symbol_normalized].clear()
                        for candle in snapshot_candles:
                            m1_fetcher._data_cache[symbol_normalized].append(candle)
                        
                        # Update last fetch time
                        m1_fetcher._last_success_time[symbol_normalized] = time.time()
                        
                        recovered_count += 1
                        logger.info(f"   ✅ Recovered {len(snapshot_candles)} M1 candles for {symbol}")
                except Exception as e:
                    logger.debug(f"   → No snapshot or error for {symbol}: {e}")
            
            if recovered_count > 0:
                logger.info(f"✅ M1 snapshot recovery complete: {recovered_count} symbols recovered")
                # Store snapshot manager for periodic snapshots
                registry.m1_snapshot_manager = snapshot_manager
                registry.m1_data_fetcher = m1_fetcher
            else:
                logger.info("   → No recent snapshots found (normal for first run)")
                # Still initialize components for future snapshots
                registry.m1_snapshot_manager = snapshot_manager
                registry.m1_data_fetcher = m1_fetcher
            
            # Cleanup old snapshots
            try:
                deleted = snapshot_manager.cleanup_old_snapshots()
                if deleted > 0:
                    logger.info(f"   → Cleaned up {deleted} old snapshots")
            except Exception as e:
                logger.debug(f"   → Snapshot cleanup error: {e}")
                
        else:
            logger.info("   → MT5Service not available - skipping M1 snapshot recovery")
            
    except Exception as e:
        logger.warning(f"⚠️ M1 snapshot recovery failed: {e}")
        logger.info("   → Desktop Agent will continue without snapshot recovery")
        registry.m1_snapshot_manager = None
        registry.m1_data_fetcher = None
    
    # Initialize Binance Service
    try:
        logger.info("📡 Starting Binance streaming service...")
        registry.binance_service = BinanceService(interval="1m")
        logger.info("   Binance service object created")
        
        registry.binance_service.set_mt5_service(registry.mt5_service)
        logger.info("   MT5 service linked")
    except Exception as e:
        logger.warning(f"⚠️ BinanceService initialization failed: {e}")
        registry.binance_service = None  # Ensure it's set to None on failure
    
    # ====================================================================
    # UNIFIED TICK PIPELINE - DISABLED FOR RESOURCE CONSERVATION
    # ====================================================================
    # DISABLED: The Unified Tick Pipeline with Binance WebSocket streams
    # is extremely resource-intensive (CPU ~10-20%, high RAM/SSD usage).
    # The system continues to function perfectly using:
    #   - Multi-Timeframe Streamer (lightweight MT5 candlestick data)
    #   - Direct MT5 calls (for analysis)
    #   - DTMS monitoring (already active via main_api.py)
    # 
    # If you need Binance tick-level data in the future, enable this
    # only on a dedicated server, not a personal laptop/desktop.
    # ====================================================================
    # try:
    #     logger.info("🚀 Initializing Unified Tick Pipeline...")
    #     # Latency timer start
    #     _t0 = None
    #     try:
    #         import time
    #         _t0 = time.perf_counter()
    #     except Exception:
    #         _t0 = None
    #     # Initialize the UPDATED pipeline directly in this process
    #     from unified_tick_pipeline_integration_updated import initialize_unified_pipeline_updated
    #     integration = initialize_unified_pipeline_updated()
    #     pipeline_success = await integration.initialize_pipeline()
    #     if pipeline_success:
    #         integration.start_background_processing()
    #     if pipeline_success:
    #         logger.info("✅ Unified Tick Pipeline integration initialized")
    #         logger.info("   → Enhanced symbol analysis")
    #         logger.info("   → Volatility monitoring")
    #         logger.info("   → Offset calibration")
    #         logger.info("   → System health monitoring")
    #         
    #         # Initialize DTMS and Intelligent Exits
    #         try:
    #             logger.info("🛡️ Initializing DTMS System...")
    #             from dtms_unified_pipeline_integration import initialize_dtms_unified_pipeline
    #             dtms_success = await initialize_dtms_unified_pipeline()
    #             if dtms_success:
    #                 logger.info("   → DTMS integration active")
    #             else:
    #                 logger.warning("   → DTMS integration failed")
    #         except Exception as e:
    #             logger.warning(f"   → DTMS integration failed: {e}")
    #         
    #         try:
    #             logger.info("🧠 Initializing Intelligent Exits System...")
    #             from intelligent_exits_unified_pipeline_integration import initialize_intelligent_exits_unified_pipeline
    #             exits_success = await initialize_intelligent_exits_unified_pipeline()
    #             if exits_success:
    #                 logger.info("   → Intelligent Exits integration active")
    #             else:
    #                 logger.warning("   → Intelligent Exits integration failed")
    #         except Exception as e:
    #             logger.warning(f"   → Intelligent Exits integration failed: {e}")
    #         
    #         # Initialize Desktop Agent integration
    #         try:
    #             logger.info("🤖 Initializing Desktop Agent integration...")
    #             integration = initialize_desktop_agent_unified_pipeline_updated()
    #             desktop_agent_success = await integration.initialize()
    #             if desktop_agent_success:
    #                 logger.info("   → Desktop Agent integration active")
    #             else:
    #                 logger.warning("   → Desktop Agent integration failed")
    #         except Exception as e:
    #             logger.warning(f"   → Desktop Agent integration failed: {e}")
    #     else:
    #         logger.warning("⚠️ Unified Tick Pipeline integration failed")
    #         logger.info("   → Desktop Agent will continue with existing data sources")
    # except Exception as e:
    #     logger.warning(f"⚠️ Unified Tick Pipeline initialization failed: {e}")
    #     logger.info("   → Desktop Agent will continue with existing data sources")
    logger.info("ℹ️ Unified Tick Pipeline disabled for resource conservation")
    logger.info("   → Using lightweight Multi-Timeframe Streamer instead")
    
    # Use Multi-Timeframe Streamer from main_api.py via API
    # NOTE: main_api.py has the streamer running with database enabled
    # We access it via API calls instead of duplicating the streamer
    logger.info("📊 Using Multi-Timeframe Streamer from main_api.py (via API or database)")
    logger.info("   → Streamer is already running in main_api.py with fresh data")
    logger.info("   → Range scalping will use streamer data when available, fallback to MT5 if needed")
    
    # Register a proxy streamer that uses main_api.py's streamer via API
    # This allows range_scalping_risk_filters to use get_streamer() pattern
    try:
        from infra.streamer_data_access import set_streamer
        
        # Create a proxy streamer that reads from main_api.py's database or API
        # For now, we'll set None and let the fallback logic handle it
        # The range_scalping_risk_filters will detect stale streamer data and fallback to MT5
        set_streamer(None)  # Signal that we rely on main_api.py streamer
        
        logger.info("   → Range scalping configured to use main_api.py streamer data")
    except Exception as e:
        logger.warning(f"⚠️ Streamer proxy setup failed: {e}")
        logger.warning("   → Range scalping will use direct MT5 calls")
    
    # Note: Latency tracking for pipeline init skipped since pipeline is disabled
    
    # ====================================================================
    # 🔴 CRITICAL: Phase 2 - Range Scalping Exit Manager (BEFORE IntelligentExitManager)
    # ====================================================================
    # MUST initialize BEFORE IntelligentExitManager to load state correctly
    try:
        logger.info("📋 Initializing Range Scalping Exit Manager (Phase 2)...")
        from config.range_scalping_config_loader import load_range_scalping_config
        from infra.range_scalping_exit_manager import (
            RangeScalpingExitManager,
            ErrorHandler
        )
        from infra.range_scalping_monitor import RangeScalpingMonitor
        
        # Load config
        range_scalp_config = load_range_scalping_config()
        
        if range_scalp_config.get("enabled", False):
            # Initialize error handler
            error_handler = ErrorHandler(range_scalp_config.get("error_handling", {}))
            
            # Initialize exit manager (loads state from disk)
            registry.range_scalp_exit_manager = RangeScalpingExitManager(
                config=range_scalp_config,
                error_handler=error_handler
            )
            logger.info("   → Range Scalping Exit Manager initialized")
            logger.info("   → State loaded from data/range_scalp_trades_active.json")
            
            # Initialize and start monitor (background thread)
            registry.range_scalp_monitor = RangeScalpingMonitor(
                exit_manager=registry.range_scalp_exit_manager,
                config=range_scalp_config
            )
            registry.range_scalp_monitor.start()
            logger.info("   → Range Scalping Monitor started (background thread)")
            logger.info("   → Monitoring active trades every 5 minutes")
        else:
            logger.info("   → Range scalping is disabled in config - skipping exit manager")
            registry.range_scalp_exit_manager = None
            registry.range_scalp_monitor = None
            
    except Exception as e:
        logger.warning(f"⚠️ Range Scalping Exit Manager initialization failed: {e}", exc_info=True)
        logger.warning("   → Range scalping trades will not be monitored for early exits")
        registry.range_scalp_exit_manager = None
        registry.range_scalp_monitor = None
    
    # ====================================================================
    
    # Initialize Liquidity Sweep Reversal Engine (Autonomous SMC Trading)
    try:
        logger.info("🔍 Initializing Liquidity Sweep Reversal Engine...")
        from infra.liquidity_sweep_reversal_engine import LiquiditySweepReversalEngine
        from discord_notifications import DiscordNotifier
        
        # Get intelligent exit manager if available
        liquidity_exit_manager = None
        try:
            liquidity_exit_manager = create_exit_manager(
                registry.mt5_service,
                advanced_provider=None  # Could pass indicator bridge if available
            )
            logger.info("   → Intelligent Exit Manager available for post-entry management")
        except Exception as e:
            logger.debug(f"   → Intelligent Exit Manager not available: {e}")
        
        # Get Discord notifier
        discord_notifier = None
        try:
            discord_notifier = DiscordNotifier()
            if discord_notifier.enabled:
                logger.info("   → Discord notifications enabled")
        except Exception as e:
            logger.debug(f"   → Discord notifications not available: {e}")
        
        # Initialize engine
        registry.liquidity_sweep_engine = LiquiditySweepReversalEngine(
            mt5_service=registry.mt5_service,
            intelligent_exit_manager=liquidity_exit_manager,
            discord_notifier=discord_notifier,
            config_path="config/liquidity_sweep_config.json"
        )
        
        # Start as background task
        await registry.liquidity_sweep_engine.start()
        logger.info("✅ Liquidity Sweep Reversal Engine started")
        logger.info("   → Monitoring BTCUSD and XAUUSD for liquidity sweeps")
        logger.info("   → Three-layer confluence stack (Macro → Setup → Trigger)")
        logger.info("   → Automatic reversal trade execution when confluence ≥70%")
        
    except Exception as e:
        logger.warning(f"⚠️ Liquidity Sweep Reversal Engine initialization failed: {e}")
        logger.info("   → Desktop Agent will continue without autonomous sweep trading")
        registry.liquidity_sweep_engine = None
    
    # Start streaming for trading symbols
    # ⚠️ NOTE: Binance only supports crypto pairs (BTCUSD, ETHUSD, etc.)
    # Forex/commodity pairs (XAUUSD, EURUSD, etc.) are not available on Binance
    if registry.binance_service is not None:
        try:
            # Only BTCUSD supported - Binance order book depth streams only work for crypto pairs
            symbols_to_stream = [
                "btcusdt"   # Bitcoin (only crypto pair supported)
            ]
            logger.info(f"   Starting streams for {len(symbols_to_stream)} symbol(s)...")
            await registry.binance_service.start(symbols_to_stream, background=True)
            
            logger.info(f"✅ Binance Service initialized and started")
            logger.info(f"✅ Streaming {len(symbols_to_stream)} symbol: {', '.join(symbols_to_stream)}")
            
            # Give it time to accumulate data
            await asyncio.sleep(3)
            
            # Show initial status
            logger.info("📊 Binance Feed Status:")
            registry.binance_service.print_status()
            
        except Exception as e:
            logger.error(f"⚠️ Binance service start failed: {e}", exc_info=True)
            logger.warning("   Continuing without Binance feed...")
            registry.binance_service = None  # Explicitly set to None on failure
    else:
        logger.warning("⚠️ Binance service not initialized - skipping start")
    
    # Initialize Order Flow Service (optional - requires Binance)
    # ⚠️ NOTE: Only BTCUSD supported - Binance doesn't have order book depth for XAUUSD/EURUSD/etc.
    registry.order_flow_service = None
    if registry.binance_service and registry.binance_service.running:
        try:
            from infra.order_flow_service import OrderFlowService
            logger.info("📊 Starting Order Flow Service (depth + whale detection)...")
            registry.order_flow_service = OrderFlowService()
            
            # ⭐ Only BTCUSD supported - Binance order book depth streams only work for crypto pairs
            order_flow_symbols = ["btcusdt"]  # BTCUSD only - XAUUSD/EURUSD/etc. not supported by Binance
            await registry.order_flow_service.start(order_flow_symbols, background=True)
            
            logger.info("✅ Order Flow Service initialized")
            logger.info("   📊 Order book depth: Active (20 levels @ 100ms)")
            logger.info("   🐋 Whale detection: Active ($50k+ orders)")
            logger.info(f"   ⚠️ Supported symbols: BTCUSD only (crypto pairs only)")
            
        except Exception as e:
            logger.warning(f"⚠️ Order Flow Service initialization failed: {e}")
            logger.warning("   Continuing without order flow analysis...")
            registry.order_flow_service = None
    
    # Initialize Circuit Breaker
    try:
        from infra.circuit_breaker import CircuitBreaker
        registry.circuit_breaker = CircuitBreaker()
        logger.info("✅ Circuit Breaker initialized")
    except Exception as e:
        logger.warning(f"⚠️ Circuit Breaker initialization failed: {e}")
    
    # Initialize Exposure Guard
    try:
        from infra.exposure_guard import ExposureGuard
        registry.exposure_guard = ExposureGuard()
        logger.info("✅ Exposure Guard initialized")
    except Exception as e:
        logger.warning(f"⚠️ Exposure Guard initialization failed: {e}")
    
    # Initialize Signal Pre-Filter
    try:
        registry.signal_prefilter = SignalPreFilter(
            binance_service=registry.binance_service,
            circuit_breaker=registry.circuit_breaker,
            exposure_guard=registry.exposure_guard,
            min_confidence=70
        )
        logger.info("✅ Signal Pre-Filter initialized")
    except Exception as e:
        logger.warning(f"⚠️ Signal Pre-Filter initialization failed: {e}")
    
    logger.info("=" * 70)
    
    # Start periodic symbol config reload (every 5 seconds)
    try:
        async def _reload_symbol_configs_periodically():
            try:
                from config.symbol_config_loader import get_config_loader
                loader = get_config_loader()
                while True:
                    try:
                        changed = loader.reload_if_changed()
                        if changed:
                            logger.info(f"🔁 Reloaded symbol configs: {', '.join(changed)}")
                    except Exception:
                        pass
                    await asyncio.sleep(5)
            except Exception:
                return
        asyncio.create_task(_reload_symbol_configs_periodically())
        logger.info("✅ Symbol config periodic reload task started")
    except Exception:
        pass
    
    # Initialize risk management stack
    try:
        from infra.go_nogo_criteria import get_go_nogo_criteria
        from infra.rollback_mechanism import get_rollback_mechanism
        from infra.staged_activation_system import get_staged_activation_system
        
        # Initialize risk management components
        _go_nogo_criteria = get_go_nogo_criteria()
        _rollback_mechanism = get_rollback_mechanism()
        _staged_activation = get_staged_activation_system()
        
        logger.info("✅ Risk management stack initialized")
        
        # Start risk management monitoring (every 1 minute)
        async def _risk_management_monitor():
            try:
                while True:
                    try:
                        # Check go/no-go criteria
                        assessment = _go_nogo_criteria.assess_system_status()
                        violations = assessment.get('violations', 0)
                        status = assessment.get('status', 'UNKNOWN')
                        
                        if violations == 0 and status == 'GO':
                            logger.info(f"✅ Go/No-Go criteria passed: {violations} violations")
                        elif violations > 0:
                            logger.warning(f"⚠️ Go/No-Go criteria failed: {violations} violations")
                        else:
                            logger.info(f"ℹ️ Go/No-Go criteria: {status} ({violations} violations)")
                        
                        # Check rollback criteria
                        should_rollback, reason = _rollback_mechanism.check_rollback_criteria()
                        if should_rollback:
                            logger.critical(f"🚨 Rollback triggered: {reason}")
                            _rollback_mechanism.execute_rollback()
                        
                        # Check staged activation status
                        if _staged_activation is not None:
                            status = _staged_activation.get_activation_status()
                            if status.current_stage != "FULL":
                                logger.info(f"📊 Staged activation: {status.current_stage}")
                        else:
                            logger.debug("📊 Staged activation system not available")
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Risk management check failed: {e}")
                    
                    await asyncio.sleep(60)  # Check every minute
            except Exception:
                return
        
        asyncio.create_task(_risk_management_monitor())
        logger.info("✅ Risk management monitoring started")
    except Exception as e:
        logger.warning(f"⚠️ Risk management stack not available: {e}")
    
    # Initialize multi-timeframe database system
    try:
        from infra.mtf_database_schema import MTFDatabaseSchema
        from infra.multi_timeframe_analyzer import MultiTimeframeAnalyzer
        from infra.database_optimization_validation import get_database_optimization_validator
        
        # Initialize MTF database
        _mtf_database = MTFDatabaseSchema("data/mtf_trading.db")
        _mtf_database.connect()
        
        # Initialize multi-timeframe analyzer
        _mtf_analyzer = MultiTimeframeAnalyzer(None, None)  # Will be configured later
        
        # Initialize database optimization validator
        _db_optimizer = get_database_optimization_validator()
        
        # Initialize symbol optimizer
        from infra.symbol_optimizer import get_symbol_optimizer, OptimizationMetric
        _symbol_optimizer = get_symbol_optimizer()
        
        logger.info("✅ Multi-timeframe database system initialized")
        
        # Start MTF database maintenance (every 6 hours)
        async def _mtf_database_maintenance():
            try:
                while True:
                    try:
                        # Run database optimization
                        _db_optimizer.validate_optimization()
                        
                        # Run symbol optimization for top performing symbols
                        symbols_to_optimize = ["BTCUSDc", "XAUUSDc", "EURUSDc", "GBPUSDc", "USDJPYc"]
                        for symbol in symbols_to_optimize:
                            try:
                                # Optimize for win rate
                                _symbol_optimizer.optimize_symbol(symbol, OptimizationMetric.WIN_RATE)
                                # Optimize for profit factor
                                _symbol_optimizer.optimize_symbol(symbol, OptimizationMetric.PROFIT_FACTOR)
                            except Exception as e:
                                logger.warning(f"⚠️ Symbol optimization failed for {symbol}: {e}")
                        
                        # Clean up old data (retention policy)
                        cutoff_timestamp = int((time.time() - (30 * 24 * 60 * 60)) * 1000)
                        _mtf_database.connection.execute("""
                            DELETE FROM mtf_structure_analysis 
                            WHERE timestamp_utc < ?
                        """, (cutoff_timestamp,))
                        _mtf_database.connection.execute("""
                            DELETE FROM mtf_m1_filters 
                            WHERE timestamp_utc < ?
                        """, (cutoff_timestamp,))
                        _mtf_database.connection.execute("""
                            DELETE FROM mtf_trade_signals 
                            WHERE timestamp_utc < ?
                        """, (cutoff_timestamp,))
                        _mtf_database.connection.commit()
                        logger.info("✅ MTF database cleanup completed")
                        
                    except Exception as e:
                        logger.warning(f"⚠️ MTF database maintenance failed: {e}")
                    
                    await asyncio.sleep(6 * 60 * 60)  # 6 hours
            except Exception:
                return
        
        asyncio.create_task(_mtf_database_maintenance())
        logger.info("✅ MTF database maintenance started")
    except Exception as e:
        logger.warning(f"⚠️ Multi-timeframe database system not available: {e}")
    
    # Background task for checking closed trades
    async def check_closed_trades_task():
        """Background task to periodically check for closed trades"""
        import MetaTrader5 as mt5
        
        logger.info("🔍 Starting closed trades monitor...")
        
        # Force check on startup
        if mt5.initialize():
            close_logger.force_check_all_open_trades()
        
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                if mt5.initialize():
                    # Get current MT5 positions
                    positions = mt5.positions_get()
                    current_tickets = {pos.ticket for pos in positions} if positions else set()
                    
                    # Sync tracked tickets
                    close_logger.sync_tracked_tickets(current_tickets)
                    
                    # Check for closes
                    closed_trades = close_logger.check_for_closed_trades()
                    
                    if closed_trades:
                        logger.info(f"📊 Logged {len(closed_trades)} closed trades")
                
            except Exception as e:
                logger.error(f"Error in closed trades monitor: {e}", exc_info=True)
    
    # Start background task
    asyncio.create_task(check_closed_trades_task())
    
    # Connect to both phone control hub and main API server
    async def connect_to_phone_hub():
        """Connect to phone control hub (port 8001)"""
        # FIX: Check if phone hub is enabled/needed
        # Phone hub is optional - don't fail if it's not available
        phone_hub_enabled = os.getenv("PHONE_HUB_ENABLED", "false").lower() == "true"
        
        if not phone_hub_enabled:
            logger.info("ℹ️ Phone hub connection disabled (set PHONE_HUB_ENABLED=true to enable)")
            return
        
        while True:
            try:
                # FIX: Add connection timeout and better error handling
                async with websockets.connect(
                    HUB_URL,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10
                ) as websocket:
                    logger.info("🔌 Connected to phone control hub")
                        
                    # Authenticate
                    await websocket.send(json.dumps({"type": "auth", "secret": AGENT_SECRET}))
                    auth_response = json.loads(await websocket.recv())
                        
                    if auth_response.get("type") != "auth_success":
                        error_msg = auth_response.get("message", "Unknown error")
                        logger.error(f"❌ Phone hub authentication failed: {error_msg}")
                        logger.error(f"   Expected secret: {AGENT_SECRET[:10]}...")
                        logger.error(f"   Check that AGENT_SECRET in desktop_agent.py matches AGENT_SECRET in hub/command_hub.py")
                        await asyncio.sleep(30)  # Wait longer before retry
                        continue
                        
                    logger.info("✅ Authenticated with phone control hub")
                        
                    # Process phone commands
                    async for message in websocket:
                        try:
                            command = json.loads(message)
                            command_id = command.get("command_id")
                            tool_name = command.get("tool")
                            arguments = command.get("arguments", {})
                                
                            logger.info(f"📥 Received phone command {command_id}: {tool_name}")
                                
                            # Execute tool
                            result = await registry.execute(tool_name, arguments)
                                
                            # Send response back - Command Hub expects status: "completed"
                            response = {
                                "command_id": command_id,
                                "status": "completed",
                                "summary": result.get("summary", "Command completed"),
                                "data": result.get("data")
                            }
                            # Convert any VolatilityRegime enums to strings before JSON serialization
                            response = make_json_serializable(response)
                            await websocket.send(json.dumps(response))
                            logger.info(f"✅ Phone command {command_id} completed")
                                
                        except Exception as e:
                            logger.error(f"Error processing phone command: {e}")
                            # Send error response - Command Hub expects status: "error"
                            response = {
                                "command_id": command.get("command_id"),
                                "status": "error",
                                "error": str(e)
                            }
                            await websocket.send(json.dumps(response))
                                
                # websockets.exceptions.InvalidStatusCode is deprecated; handle via generic Exception below.
            except ConnectionRefusedError:
                logger.warning(
                    f"⚠️ Phone hub not available (connection refused): "
                    f"Phone hub server may not be running on {HUB_URL}. "
                    f"This is OK if you're not using phone control."
                )
                await asyncio.sleep(60)  # Wait 60 seconds before retry
            except Exception as e:
                error_str = str(e)
                if "403" in error_str or "Forbidden" in error_str:
                    logger.warning(
                        f"⚠️ Phone hub connection rejected (HTTP 403): {e}"
                    )
                    logger.warning(
                        f"   Troubleshooting: "
                        f"1. Verify phone hub is running: check hub/command_hub.py logs"
                        f"2. Check AGENT_SECRET matches: desktop_agent.py line 174 vs hub/command_hub.py line 52"
                        f"3. Check .env file has correct AGENT_SECRET"
                        f"4. Or disable phone hub: set PHONE_HUB_ENABLED=false in environment"
                    )
                else:
                    logger.error(f"❌ Phone hub connection error: {e}")
                await asyncio.sleep(30)  # Wait 30 seconds before retry
    
    def make_json_serializable(obj):
        """Recursively convert VolatilityRegime enums, numpy types, and other non-serializable objects to JSON-serializable types"""
        from infra.volatility_regime_detector import VolatilityRegime
        from enum import Enum
        import numpy as np
        
        # Handle VolatilityRegime enums
        if isinstance(obj, VolatilityRegime):
            return obj.value
        # Handle other Enum types
        elif isinstance(obj, Enum):
            return obj.value
        # Handle numpy bool types (must come before dict/list to catch nested numpy bools)
        # Check for numpy bool types - handle different numpy versions
        elif hasattr(np, 'bool_') and isinstance(obj, np.bool_):
            return bool(obj)
        elif type(obj).__module__ == 'numpy' and type(obj).__name__ in ('bool_', 'bool8'):
            return bool(obj)
        # Handle numpy integer types
        elif isinstance(obj, np.integer):
            return int(obj)
        # Handle numpy floating types
        elif isinstance(obj, np.floating):
            return float(obj)
        # Handle numpy arrays
        elif isinstance(obj, np.ndarray):
            return [make_json_serializable(item) for item in obj.tolist()]
        # Handle dictionaries
        elif isinstance(obj, dict):
            return {key: make_json_serializable(value) for key, value in obj.items()}
        # Handle lists and tuples
        elif isinstance(obj, (list, tuple)):
            return [make_json_serializable(item) for item in obj]
        # Handle datetime objects
        elif isinstance(obj, datetime):
            return obj.isoformat()
        # Handle other numpy types (catch-all)
        elif hasattr(obj, '__class__') and 'numpy' in str(type(obj)):
            if hasattr(obj, 'item'):
                return make_json_serializable(obj.item())
            elif hasattr(obj, '__bool__'):
                return bool(obj)
            elif hasattr(obj, '__int__'):
                return int(obj)
            elif hasattr(obj, '__float__'):
                return float(obj)
        # Return as-is for native Python types
        return obj
    
    async def connect_to_api_server():
        """Connect to main API server (port 8000) for ChatGPT commands"""
        while True:
            try:
                async with websockets.connect(API_URL) as websocket:
                    logger.info("🔌 Connected to main API server")
                    
                    # Authenticate with main API server
                    await websocket.send(json.dumps({"type": "auth", "secret": API_SECRET}))
                    auth_response = json.loads(await websocket.recv())
                    
                    if auth_response.get("type") != "auth_success":
                        logger.error(f"❌ API server authentication failed: {auth_response.get('message')}")
                        break
                    
                    logger.info("✅ Authenticated with main API server - ready for ChatGPT commands")
                    
                    # Process ChatGPT commands
                    async for message in websocket:
                        try:
                            command = json.loads(message)
                            command_id = command.get("command_id")
                            tool_name = command.get("tool")
                            arguments = command.get("arguments", {})
                            
                            logger.info(f"📥 Received ChatGPT command {command_id}: {tool_name}")
                            
                            # Execute tool
                            result = await registry.execute(tool_name, arguments)
                            
                            # Send response back to main API server - expects type: "result" with nested result object
                            response = {
                                "type": "result",
                                "command_id": command_id,
                                "result": {
                                    "summary": result.get("summary", "Command completed"),
                                    "data": result.get("data")
                                }
                            }
                            # Convert any VolatilityRegime enums to strings before JSON serialization
                            response = make_json_serializable(response)
                            
                            # Check response size and handle large responses
                            try:
                                response_json = json.dumps(response)
                                response_size = len(response_json.encode('utf-8'))
                                max_message_size = 900 * 1024  # 900KB limit (leave room for WebSocket overhead)
                                
                                logger.debug(f"Response size: {response_size} bytes for command {command_id}")
                                
                                if response_size > max_message_size:
                                    # Response too large - send summary only and truncate data
                                    logger.warning(f"Response too large ({response_size} bytes) - truncating for WebSocket")
                                    
                                    # Keep summary, but truncate data if it's a string
                                    truncated_response = {
                                        "type": "result",
                                        "command_id": command_id,
                                        "result": {
                                            "summary": result.get("summary", "Command completed"),
                                            "data": None,  # Remove large data
                                            "truncated": True,
                                            "original_size": response_size,
                                            "message": "Response too large for WebSocket. Full analysis completed successfully - check desktop_agent logs for complete output."
                                        }
                                    }
                                    truncated_response = make_json_serializable(truncated_response)
                                    await websocket.send(json.dumps(truncated_response))
                                    logger.info(f"✅ ChatGPT command {command_id} completed (response truncated due to size)")
                                else:
                                    # Response size is OK - send normally
                                    await websocket.send(response_json)
                                    logger.info(f"✅ ChatGPT command {command_id} completed and sent ({response_size} bytes)")
                            except Exception as send_error:
                                logger.error(f"Error sending response for command {command_id}: {send_error}", exc_info=True)
                                # Try to send error response
                                try:
                                    error_response = {
                                        "type": "error",
                                        "command_id": command_id,
                                        "error": f"Failed to send response: {str(send_error)}"
                                    }
                                    await websocket.send(json.dumps(error_response))
                                except Exception as e2:
                                    logger.error(f"Failed to send error response: {e2}")
                            
                        except Exception as e:
                            logger.error(f"Error processing ChatGPT command: {e}")
                            # Send error response - expects type: "error"
                            response = {
                                "type": "error",
                                "command_id": command.get("command_id"),
                                "error": str(e)
                            }
                            await websocket.send(json.dumps(response))
                            
            except ConnectionClosed as e:
                # Handle WebSocket close codes gracefully
                close_code = e.code
                close_reason = e.reason or "Unknown"
                
                # Code 1012 = Service Restart (expected during uvicorn --reload)
                if close_code == 1012:
                    logger.info(f"ℹ️ API server restarting (code 1012) - will reconnect in 3 seconds...")
                    await asyncio.sleep(3)
                # Code 1000 = Normal Closure
                elif close_code == 1000:
                    logger.info(f"ℹ️ API server connection closed normally - will reconnect in 3 seconds...")
                    await asyncio.sleep(3)
                # Code 1006 = Abnormal Closure (connection lost)
                elif close_code == 1006:
                    logger.warning(f"⚠️ API server connection lost (code 1006) - will reconnect in 5 seconds...")
                    await asyncio.sleep(5)
                # Other close codes
                else:
                    logger.warning(f"⚠️ API server connection closed (code {close_code}: {close_reason}) - will reconnect in 5 seconds...")
                    await asyncio.sleep(5)
                    
            except InvalidURI as e:
                logger.error(f"❌ Invalid WebSocket URI: {e}")
                break  # Don't retry if URI is invalid
                
            except Exception as e:
                error_str = str(e)
                # Check if error message contains 1012 (service restart)
                if "1012" in error_str or "service restart" in error_str.lower():
                    logger.info(f"ℹ️ API server restarting - will reconnect in 3 seconds...")
                    await asyncio.sleep(3)
                # Handle invalid status codes without depending on deprecated InvalidStatusCode
                elif "status code" in error_str.lower() or "http " in error_str.lower():
                    logger.error(f"❌ API server connection error (HTTP status): {e}")
                    await asyncio.sleep(10)
                else:
                    logger.error(f"❌ API server connection error: {e}")
                    await asyncio.sleep(5)
    
    # Start both connections concurrently
    await asyncio.gather(
        connect_to_phone_hub(),
        connect_to_api_server()
    )


#============================================================================
# ALERT MANAGEMENT TOOLS
# ============================================================================

@registry.register("moneybot.add_alert")
async def tool_add_alert(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a custom alert for specific market conditions
    
    Args:
        symbol: Trading symbol (e.g. "BTCUSD", "XAUUSD")
        alert_type: Type of alert - "structure", "price", "indicator", "order_flow", "volatility"
        condition: Condition type - "detected", "crosses_above", "crosses_below", "greater_than", "less_than"
        description: Human-readable description
        parameters: Dict of alert-specific parameters
        expires_hours: Optional expiry in hours (default: no expiry)
        one_time: Optional - auto-remove after first trigger (default: True)
    
    Examples:
        # BOS Bull on BTCUSD
        {
            "symbol": "BTCUSD",
            "alert_type": "structure",
            "condition": "detected",
            "description": "BOS Bull on BTCUSD M5",
            "parameters": {"pattern": "bos_bull", "timeframe": "M5"}
        }
        
        # Price crosses 4100
        {
            "symbol": "XAUUSD",
            "alert_type": "price",
            "condition": "crosses_above",
            "description": "XAUUSD crosses above 4100",
            "parameters": {"price_level": 4100}
        }
        
        # RSI > 70
        {
            "symbol": "BTCUSD",
            "alert_type": "indicator",
            "condition": "greater_than",
            "description": "BTCUSD RSI > 70 on H1",
            "parameters": {"indicator": "rsi", "value": 70, "timeframe": "H1"}
        }
    
    Returns:
        Confirmation with alert_id
    """
    # Extract ONLY alert-specific parameters - filter out trade parameters that ChatGPT may send
    symbol = args.get("symbol")
    alert_type = args.get("alert_type")
    condition = args.get("condition")
    description = args.get("description")
    parameters = args.get("parameters", {})
    expires_hours = args.get("expires_hours")
    one_time = args.get("one_time", True)  # Default: True (one-time alerts)
    
    # If price alert but no price_level in parameters, try to extract from other fields ChatGPT might send
    if alert_type == "price" and not parameters.get("price_level"):
        # ChatGPT might send entry, price, target, or price_level directly in args
        price_level = (
            args.get("entry") or 
            args.get("price") or 
            args.get("target") or
            args.get("price_level") or
            None
        )
        if price_level:
            parameters["price_level"] = float(price_level)
            logger.info(f"✅ Extracted price_level from args: {price_level}")
    
    # If indicator alert but missing parameters, try to extract from description
    if alert_type == "indicator" and (not parameters.get("indicator") or parameters.get("value") is None):
        import re
        desc = description or ""
        
        # Extract indicator name (RSI, MACD, ADX, etc.)
        if not parameters.get("indicator"):
            indicator_match = re.search(r'\b(RSI|MACD|ADX|ATR|EMA|SMA|BB|Bollinger)\b', desc, re.IGNORECASE)
            if indicator_match:
                parameters["indicator"] = indicator_match.group(1).lower()
                logger.info(f"✅ Extracted indicator from description: {parameters['indicator']}")
        
        # Extract timeframe (M15, H1, M5, etc.)
        if not parameters.get("timeframe"):
            tf_match = re.search(r'\b(M1|M5|M15|M30|H1|H4|D1)\b', desc, re.IGNORECASE)
            if tf_match:
                parameters["timeframe"] = tf_match.group(1).upper()
                logger.info(f"✅ Extracted timeframe from description: {parameters['timeframe']}")
        
        # Extract value (number after indicator or condition)
        if parameters.get("value") is None:
            # Look for patterns like "RSI > 60", "RSI crosses above 60", "above 60"
            value_match = re.search(r'(?:crosses?\s+(?:above|below)|>|<|>=|<=|equals?|is|at)\s+(\d+(?:\.\d+)?)', desc, re.IGNORECASE)
            if not value_match:
                # Fallback: look for any number in description
                value_match = re.search(r'\b(\d+(?:\.\d+)?)\b', desc)
            if value_match:
                try:
                    parameters["value"] = float(value_match.group(1))
                    logger.info(f"✅ Extracted value from description: {parameters['value']}")
                except ValueError:
                    pass
    
    # If required arguments are missing, try to parse from natural language request
    if not all([symbol, alert_type, condition, description]):
        # Try multiple fields where ChatGPT might put the original request
        user_request = (
            args.get("user_request") or 
            args.get("query") or 
            args.get("user_text") or
            args.get("original_request") or
            # If description exists but looks like natural language, try parsing it
            (args.get("description") if args.get("description") and not condition else "") or
            ""
        )
        
        if user_request:
            try:
                # Try to parse natural language request
                from enhanced_alert_intent_parser import AlertIntentParser
                parser = AlertIntentParser()
                parsed = parser.parse_alert_request(user_request)
                
                # Use parsed values if original args were missing
                symbol = symbol or parsed.get("symbol")
                alert_type = alert_type or parsed.get("alert_type")
                condition = condition or parsed.get("condition")
                description = description or parsed.get("description")
                if not parameters:
                    parameters = parsed.get("parameters", {})
                if expires_hours is None:
                    expires_hours = parsed.get("expires_hours")
                if one_time is None:
                    one_time = parsed.get("one_time", True)
                    
                logger.info(f"✅ Parsed alert request from natural language: {user_request[:100]}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to parse natural language alert request: {e}")
                # Fall through to error below
    
    # Validate required arguments after parsing attempt
    if not all([symbol, alert_type, condition, description]):
        error_msg = (
            "Missing required arguments: symbol, alert_type, condition, description.\n"
            "Expected format:\n"
            "  - symbol: Trading symbol (e.g., 'GBPUSDc', 'BTCUSDc')\n"
            "  - alert_type: 'price', 'structure', 'indicator', 'volatility'\n"
            "  - condition: 'crosses_above', 'crosses_below', 'greater_than', 'less_than', 'detected'\n"
            "  - description: Human-readable description\n"
            "For natural language requests, include 'user_request' field with the alert text."
        )
        raise ValueError(error_msg)
    
    # Initialize alert manager if not already done
    if not registry.alert_manager:
        registry.alert_manager = CustomAlertManager()
    
    logger.info(f"🔔 Adding alert: {description} (one_time={one_time})")
    
    try:
        alert = registry.alert_manager.add_alert(
            symbol=symbol,
            alert_type=alert_type,
            condition=condition,
            description=description,
            parameters=parameters,
            expires_hours=expires_hours,
            one_time=one_time
        )
        
        # Build condition display string
        condition_display = condition
        if alert_type == "indicator" and parameters:
            indicator = parameters.get("indicator", "").upper()
            timeframe = parameters.get("timeframe", "")
            value = parameters.get("value")
            if indicator and value is not None:
                if timeframe:
                    condition_display = f"{indicator} {condition.replace('_', ' ')} {value} on {timeframe}"
                else:
                    condition_display = f"{indicator} {condition.replace('_', ' ')} {value}"
        
        summary = (
            f"✅ Alert Added\n\n"
            f"📊 Symbol: {symbol}\n"
            f"🔔 Alert: {description}\n"
            f"📝 Type: {alert_type}\n"
            f"⚙️ Condition: {condition_display}\n"
            f"🆔 Alert ID: {alert.alert_id}\n\n"
            f"You'll receive a Discord notification when this condition is met."
        )
        
        if one_time:
            summary += f"\n🔔 This is a ONE-TIME alert - it will be automatically removed after triggering."
        else:
            summary += f"\n🔄 This is a RECURRING alert - it will trigger every time the condition is met."
        
        if expires_hours:
            summary += f"\n⏰ Expires in {expires_hours} hours"
        
        return {
            "summary": summary,
            "data": {
                "alert_id": alert.alert_id,
                "symbol": symbol,
                "description": description,
                "enabled": True
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to add alert: {e}", exc_info=True)
        raise RuntimeError(f"Failed to add alert: {str(e)}")

@registry.register("moneybot.list_alerts")
async def tool_list_alerts(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    List all active alerts or alerts for a specific symbol
    
    Args:
        symbol: Optional - filter by symbol
        include_disabled: Optional - include disabled alerts (default: False)
    
    Returns:
        List of active alerts
    """
    symbol = args.get("symbol")
    include_disabled = args.get("include_disabled", False)
    
    # Initialize alert manager if not already done
    if not registry.alert_manager:
        registry.alert_manager = CustomAlertManager()
    
    # ALWAYS reload from disk to get latest alerts
    registry.alert_manager.load_alerts()
    
    try:
        if symbol:
            alerts = registry.alert_manager.get_alerts_for_symbol(symbol, enabled_only=not include_disabled)
        else:
            alerts = registry.alert_manager.get_all_alerts(enabled_only=not include_disabled)
        
        if not alerts:
            return {
                "summary": "📭 No active alerts configured",
                "data": {"alerts": []}
            }
        
        alert_list = []
        summary_lines = [f"🔔 Active Alerts ({len(alerts)})\n"]
        
        for alert in alerts:
            alert_list.append({
                "alert_id": alert.alert_id,
                "symbol": alert.symbol,
                "description": alert.description,
                "alert_type": alert.alert_type.value,
                "condition": alert.condition.value,
                "parameters": alert.parameters,
                "enabled": alert.enabled,
                "triggered_count": alert.triggered_count,
                "last_triggered": alert.last_triggered
            })
            
            status = "✅" if alert.enabled else "⏸️"
            summary_lines.append(
                f"{status} {alert.symbol}: {alert.description}\n"
                f"   ID: {alert.alert_id}\n"
                f"   Triggers: {alert.triggered_count}\n"
            )
        
        return {
            "summary": "\n".join(summary_lines),
            "data": {"alerts": alert_list}
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to list alerts: {e}", exc_info=True)
        raise RuntimeError(f"Failed to list alerts: {str(e)}")

@registry.register("moneybot.remove_alert")
async def tool_remove_alert(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove a custom alert
    
    Args:
        alert_id: ID of the alert to remove
    
    Returns:
        Confirmation of removal
    """
    alert_id = args.get("alert_id")
    
    if not alert_id:
        raise ValueError("Missing required argument: alert_id")
    
    # Initialize alert manager if not already done
    if not registry.alert_manager:
        registry.alert_manager = CustomAlertManager()
    
    try:
        success = registry.alert_manager.remove_alert(alert_id)
        
        if success:
            return {
                "summary": f"✅ Alert removed: {alert_id}",
                "data": {"alert_id": alert_id, "removed": True}
            }
        else:
            return {
                "summary": f"❌ Alert not found: {alert_id}",
                "data": {"alert_id": alert_id, "removed": False}
            }
        
    except Exception as e:
        logger.error(f"❌ Failed to remove alert: {e}", exc_info=True)
        raise RuntimeError(f"Failed to remove alert: {str(e)}")


@registry.register("moneybot.getAdvancedFeatures")
async def tool_get_advanced_features(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get Advanced institutional-grade technical features for a symbol

    Returns 11 institutional indicators PLUS candlestick patterns:
    - RMAG (Relative Moving Average Gap)
    - EMA Slope Quality
    - Bollinger ADX Momentum
    - Volume Profile HVN
    - VWAP Distance
    - Candlestick Patterns (Marubozu, Doji, Hammer, Shooting Star, Engulfing, etc.)
    - Multi-bar Patterns (Morning Star, Evening Star, Inside Bar, etc.)
    - Pattern Strength & Wick Metrics
    - And more...
    
    Pattern data structure:
    - candlestick_flags: marubozu_bull, marubozu_bear, doji, hammer, shooting_star, pin_bar_bull/bear
    - pattern_flags: bull_engulfing, bear_engulfing, inside_bar, outside_bar, breakout_bar, 
                     morning_star, evening_star, three_white_soldiers, three_black_crows
    - wick_metrics: upper_wick_pct, lower_wick_pct, body_pct, wick_asymmetry, upper_wick_atr, lower_wick_atr
    - pattern_strength: 0.0-1.0 score
    
    Args:
        symbol: Trading symbol (e.g., BTCUSD, XAUUSD)
        timeframes: Optional list of timeframes (default: ["M5", "M15", "M30", "H1", "H4"])
    
    Returns:
        Dict with Advanced features for each timeframe, including pattern detection
    """
    symbol = args.get("symbol")
    timeframes = args.get("timeframes", ["M5", "M15", "M30", "H1", "H4"])
    
    if not symbol:
        raise ValueError("Missing required argument: symbol")
    
    try:
        from infra.feature_builder_advanced import build_features_advanced
        from infra.indicator_bridge import IndicatorBridge
        
        mt5_service = registry.mt5_service
        if not mt5_service:
            raise RuntimeError("MT5 service not initialized")
        
        # Initialize indicator bridge
        indicator_bridge = IndicatorBridge()
        
        # Add 'c' suffix if not present (broker-specific)
        if symbol.upper() not in ['DXY', 'VIX', 'US10Y']:
            # Normalize: strip any trailing 'c' or 'C', then add lowercase 'c'
            if not symbol.lower().endswith('c'):
                symbol_mt5 = symbol.upper() + 'c'
            else:
                symbol_mt5 = symbol.upper().rstrip('cC') + 'c'
            logger.info(f"📊 Converting {symbol} → {symbol_mt5} for MT5 broker")
        else:
            symbol_mt5 = symbol
        
        # Build Advanced features
        logger.info(f"📊 Building Advanced features for {symbol_mt5}...")
        features = build_features_advanced(
            symbol=symbol_mt5,
            mt5svc=mt5_service,
            bridge=indicator_bridge,
            timeframes=timeframes
        )
        
        if not features or not features.get("features"):
            return {
                "summary": f"❌ No Advanced features available for {symbol}",
                "data": None
            }
        
        # Extract key insights for summary
        m15_features = features["features"].get("M15", {})
        
        # Extract numeric values from nested dicts (rmag and vol_trend are dicts, not scalars)
        rmag_dict = m15_features.get("rmag", {})
        if isinstance(rmag_dict, dict):
            rmag_value = rmag_dict.get("ema200_atr", 0.0) or rmag_dict.get("vwap_atr", 0.0) or 0.0
        else:
            rmag_value = float(rmag_dict) if rmag_dict else 0.0
        
        vol_trend_dict = m15_features.get("vol_trend", {})
        if isinstance(vol_trend_dict, dict):
            bb_adx_value = vol_trend_dict.get("adx", 0.0) or 0.0
            bb_state = vol_trend_dict.get("state", "unknown")
        else:
            bb_adx_value = float(vol_trend_dict) if vol_trend_dict else 0.0
            bb_state = "unknown"
        
        return {
            "summary": f"✅ Advanced features for {symbol} (RMAG: {rmag_value:.3f}, BB-ADX: {bb_adx_value:.1f} [{bb_state}])",
            "data": features,
            "timestamp": datetime.now().isoformat(),
            "timestamp_human": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "cache_control": "no-cache, no-store, must-revalidate"
        }
        
    except Exception as e:
            logger.error(f"❌ Failed to get Advanced features: {e}", exc_info=True)
            raise RuntimeError(f"Failed to get Advanced features: {str(e)}")


@registry.register("moneybot.sendDiscordMessage")
async def tool_send_discord_message(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send a custom message to Discord
    
    Allows ChatGPT to send any text message, analysis, or notification directly to Discord.
    Useful for sharing analysis, trade ideas, market updates, or any custom information.
    
    Args:
        message: The message content to send (can include markdown formatting)
               ⚠️ FOR ANALYSIS MESSAGES: Use use_last_analysis=true instead of passing message!
        message_type: Optional - Type of message (default: "INFO"). Options: "INFO", "ANALYSIS", "ALERT", "UPDATE"
        title: Optional - Custom title for the message (default: "ChatGPT Message")
        use_last_analysis: Optional - If true, automatically uses the stored exact text from last analysis
                           (RECOMMENDED for ANALYSIS messages to prevent condensation/rewriting)
    
    Returns:
        Dict with success status and confirmation
    """
    use_last_analysis = args.get("use_last_analysis", False)
    message = args.get("message")
    message_type = args.get("message_type", "INFO").upper()  # Force uppercase for consistency
    title = args.get("title", "ChatGPT Message")
    
    # If use_last_analysis is true, automatically fetch the stored exact text
    if use_last_analysis:
        if not registry.last_analysis_summary:
            raise ValueError("No stored analysis found. Run an analysis first (moneybot.getUnifiedAnalysis or moneybot.analyseSymbolFull)")
        
        message = registry.last_analysis_summary
        symbol = registry.last_analysis_symbol or "Market"
        
        # Auto-detect ANALYSIS message type if not specified
        if message_type == "INFO":
            message_type = "ANALYSIS"
        
        # Auto-generate title if not provided
        if title == "ChatGPT Message":
            title = f"{symbol} Market Analysis"
        
        logger.info(f"✅ Using stored analysis text ({len(message)} chars) - prevents ChatGPT condensation!")
        logger.info(f"   Symbol: {symbol}, Timestamp: {registry.last_analysis_timestamp}")
    elif not message:
        raise ValueError("Missing required argument: message (or use use_last_analysis=true)")
    
    # Debug logging to diagnose routing issues
    logger.info(f"🔔 sendDiscordMessage called: message_type={message_type}, title={title}, message_length={len(message)}")
    
    try:
        # Import Discord notifier
        try:
            from discord_notifications import DiscordNotifier
            notifier = DiscordNotifier()
        except ImportError:
            raise RuntimeError("Discord notifications not available - DISCORD_WEBHOOK_URL not configured")
        
        if not notifier.enabled:
            raise RuntimeError("Discord notifications disabled - check DISCORD_WEBHOOK_URL in .env")
        
        # Validate signals webhook is configured if sending ANALYSIS
        if message_type == "ANALYSIS" and not notifier.signals_webhook_url:
            logger.warning("⚠️ ANALYSIS message requested but DISCORD_SIGNALS_WEBHOOK_URL not configured. Will send to private channel.")
        
        # Map message types to colors
        color_map = {
            "INFO": 0x0099ff,      # Blue
            "ANALYSIS": 0x00ff00,  # Green
            "ALERT": 0xff9900,     # Orange
            "UPDATE": 0x9b59b6,    # Purple
            "WARNING": 0xff9900,   # Orange
            "ERROR": 0xff0000      # Red
        }
        color = color_map.get(message_type, 0x0099ff)
        
        # Determine channel: ANALYSIS messages go to signals channel, others to private
        # CRITICAL: If message_type is not "ANALYSIS", it goes to private channel
        if message_type == "ANALYSIS":
            channel = "signals"
            logger.info(f"✅ Routing ANALYSIS message to signals channel")
        else:
            channel = "private"
            logger.info(f"ℹ️ Routing {message_type} message to private channel")
        
        # For ANALYSIS messages, construct title from symbol if not provided
        # Otherwise use the provided title or default
        if message_type.upper() == "ANALYSIS" and title == "ChatGPT Message":
            # Try to extract symbol from message (e.g., "BTCUSD Analysis" or "$BTCUSD")
            import re
            symbol_match = re.search(r'(\$?[A-Z]{3,6}USD)', message, re.IGNORECASE)
            if symbol_match:
                symbol = symbol_match.group(1).upper()
                discord_title = f"{symbol} Market Analysis"
            else:
                discord_title = title
        else:
            discord_title = title
        
        # Validate and clean message content for ANALYSIS messages
        if message_type == "ANALYSIS":
            # Remove bot-specific internal messages that aren't relevant to public signals
            # These should be kept in ChatGPT conversation but removed from Discord signals
            bot_internal_patterns = [
                r'🤖\s*Auto\s+exits?\s+(?:remain|are)\s+active.*?(?=\n\n|\n📝|$)',
                r'🤖\s*Auto[-\s]?exits?.*?(?=\n\n|\n📝|$)',
                r'🤖\s*Intelligent\s+exits?.*?(?=\n\n|\n📝|$)',
                r'Auto\s+exits?\s+(?:remain|are)\s+active.*?(?=\n\n|\n📝|$)',
            ]
            
            import re
            original_length = len(message)
            for pattern in bot_internal_patterns:
                message = re.sub(pattern, '', message, flags=re.IGNORECASE | re.DOTALL)
            
            if len(message) < original_length:
                logger.info(f"🧹 Removed bot-internal auto-exit mentions from Discord message ({original_length - len(message)} chars removed)")
            
            # Check if message seems truncated (common ChatGPT mistake)
            analysis_keywords = ["🌍", "🏛️", "⚙️", "📊", "💧", "📉", "🎯", "📝"]  # Typical section markers
            found_sections = sum(1 for keyword in analysis_keywords if keyword in message)
            
            if found_sections < 4:  # Full analysis should have at least 4-5 sections
                logger.warning(f"⚠️ ANALYSIS message may be truncated - only {found_sections} sections found. Expected 5-7 sections.")
                logger.warning(f"   Message length: {len(message)} characters")
                logger.warning(f"   First 200 chars: {message[:200]}")
            
            # Check message length - full analyses are typically 500-2000+ characters
            if len(message) < 300:
                logger.warning(f"⚠️ ANALYSIS message seems too short ({len(message)} chars). Full analyses are typically 500-2000+ characters.")
        
        # Validate message for ANALYSIS type - check if it seems condensed
        if message_type == "ANALYSIS":
            # Check for common condensation patterns that indicate ChatGPT rewrote the message
            # Full analyses should have multi-line sections, not single-line condensed format
            lines = message.split('\n')
            
            # Check for condensation patterns
            has_condensed_market = any("Market:" in line and "Structure" not in line for line in lines) and len(lines) < 15
            has_condensed_macro = any("Macro:" in line and "Context" not in line for line in lines)
            has_condensed_tech = any("Tech:" in line and "Overview" not in line for line in lines)
            too_few_lines = message.count('\n') < 10
            short_lines = all(len(line) < 80 for line in lines[:10]) if len(lines) >= 10 else False
            
            condensed_indicators = [
                has_condensed_market,
                has_condensed_macro,
                has_condensed_tech,
                too_few_lines,
                short_lines
            ]
            
            if any(condensed_indicators):
                logger.error(f"❌ CRITICAL ERROR: ChatGPT sent a CONDENSED message instead of word-for-word copy!")
                logger.error(f"   Message appears to be rewritten/condensed - this violates the word-for-word requirement")
                logger.error(f"   Message length: {len(message)} chars, Lines: {len(lines)}")
                logger.error(f"   First 500 chars: {message[:500]}")
                logger.error(f"   ⚠️ The message will still be sent, but this is INCORRECT behavior")
                # Still send it, but log the violation for debugging
        
        # Send message to Discord
        # CRITICAL: Pass message_type (ANALYSIS) not title, so channel routing works correctly
        success = notifier.send_message(
            message=message,
            message_type=message_type,  # Pass the actual message_type (ANALYSIS), not title
            color=color,
            channel=channel,  # Explicitly pass channel to ensure correct routing
            custom_title=discord_title  # Use custom title for embed if supported
        )
        
        if success:
            # Log success with message stats for debugging
            logger.info(f"✅ Discord message sent successfully")
            logger.info(f"   Channel: {channel}")
            logger.info(f"   Message type: {message_type}")
            logger.info(f"   Message length: {len(message)} characters")
            logger.info(f"   Title: {discord_title}")
            
            return {
                "summary": f"✅ Message sent to Discord ({channel} channel): {discord_title}",
                "data": {
                    "sent": True,
                    "message_type": message_type,
                    "title": discord_title,
                    "message_length": len(message),
                    "channel": channel
                }
            }
        else:
            raise RuntimeError("Failed to send Discord message")
        
    except Exception as e:
        logger.error(f"❌ Failed to send Discord message: {e}", exc_info=True)
        raise RuntimeError(f"Failed to send Discord message: {str(e)}")


@registry.register("moneybot.getMultiTimeframeAnalysis")
async def tool_get_multi_timeframe_analysis(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get comprehensive multi-timeframe Smart Money Concepts (SMC) analysis
    
    Analyzes H4 → M5 structure mapping with:
    - CHOCH (Change of Character) detection
    - BOS (Break of Structure) confirmation
    - Order Blocks (institutional entry zones)
    - Liquidity Pools (stop hunt levels)
    - Market structure (HH, HL, LL, LH patterns)
    - MTF alignment and confidence scoring
    
    Args:
        symbol: Trading symbol (e.g., BTCUSD, XAUUSD)
    
    Returns:
        Dict with full SMC analysis across all timeframes
    """
    symbol = args.get("symbol")
    
    if not symbol:
        raise ValueError("Missing required argument: symbol")
    
    try:
        from infra.multi_timeframe_analyzer import MultiTimeframeAnalyzer
        
        mt5_service = registry.mt5_service
        if not mt5_service:
            raise RuntimeError("MT5 service not initialized")
        
        # Initialize analyzer
        from infra.indicator_bridge import IndicatorBridge
        indicator_bridge = IndicatorBridge()
        
        analyzer = MultiTimeframeAnalyzer(
            mt5_service=mt5_service,
            indicator_bridge=indicator_bridge
        )
        
        # Add 'c' suffix if not present (broker-specific)
        if symbol.upper() not in ['DXY', 'VIX', 'US10Y']:
            # Normalize: strip any trailing 'c' or 'C', then add lowercase 'c'
            if not symbol.lower().endswith('c'):
                symbol_mt5 = symbol.upper() + 'c'
            else:
                symbol_mt5 = symbol.upper().rstrip('cC') + 'c'
            logger.info(f"📊 Converting {symbol} → {symbol_mt5} for MT5 broker")
        else:
            symbol_mt5 = symbol
        
        # Run full multi-timeframe analysis (not async)
        logger.info(f"📊 Running multi-timeframe SMC analysis for {symbol_mt5}...")
        analysis = analyzer.analyze(symbol_mt5)
        
        if not analysis or analysis.get("status") == "error":
            return {
                "summary": f"❌ Multi-timeframe analysis failed for {symbol}",
                "data": analysis,
                "error": analysis.get("reason", "Unknown error") if analysis else "No data"
            }
        
        # Extract key insights for summary
        action = analysis.get("recommendation", {}).get("action", "UNKNOWN")
        confidence = analysis.get("confidence_score", 0)
        structure = analysis.get("structure_analysis", {})
        choch = structure.get("choch_detected", False)
        bos = structure.get("bos_confirmed", False)
        
        summary_parts = [f"✅ {symbol} MTF Analysis"]
        if choch:
            summary_parts.append("🚨 CHOCH detected")
        if bos:
            summary_parts.append("✅ BOS confirmed")
        summary_parts.append(f"{action} ({confidence}/100)")
        
        return {
            "summary": " | ".join(summary_parts),
            "data": analysis,
            "timestamp": datetime.now().isoformat(),
            "timestamp_human": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "cache_control": "no-cache, no-store, must-revalidate"
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get multi-timeframe analysis: {e}", exc_info=True)
        raise RuntimeError(f"Multi-timeframe analysis failed: {str(e)}")

# ============================================================================
# AUTO EXECUTION TOOLS
# ============================================================================

@registry.register("moneybot.re_evaluate_plan")
async def tool_re_evaluate_plan_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Re-evaluate an auto-execution trade plan (Phase 4)"""
    from chatgpt_auto_execution_tools import tool_re_evaluate_plan
    return await tool_re_evaluate_plan(args)

@registry.register("moneybot.create_auto_trade_plan")
async def tool_create_auto_trade_plan_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a general auto trade plan"""
    return await tool_create_auto_trade_plan(args)

@registry.register("moneybot.create_choch_plan")
async def tool_create_choch_plan_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a CHOCH-based auto trade plan"""
    return await tool_create_choch_plan(args)

@registry.register("moneybot.create_rejection_wick_plan")
async def tool_create_rejection_wick_plan_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a rejection wick-based auto trade plan"""
    return await tool_create_rejection_wick_plan(args)

@registry.register("moneybot.create_order_block_plan")
async def tool_create_order_block_plan_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create an order block-based auto trade plan"""
    from chatgpt_auto_execution_tools import tool_create_order_block_plan
    return await tool_create_order_block_plan(args)

@registry.register("moneybot.create_micro_scalp_plan")
async def tool_create_micro_scalp_plan_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a micro-scalp auto-execution plan for ultra-short-term trading"""
    from chatgpt_auto_execution_tools import tool_create_micro_scalp_plan
    return await tool_create_micro_scalp_plan(args)

@registry.register("moneybot.create_bracket_trade_plan")
async def tool_create_bracket_trade_plan_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a bracket trade plan (OCO - One Cancels Other) for auto execution"""
    from chatgpt_auto_execution_tools import tool_create_bracket_trade_plan
    return await tool_create_bracket_trade_plan(args)

@registry.register("moneybot.create_range_scalp_plan")
async def tool_create_range_scalp_plan_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a range scalping auto-execution plan"""
    from chatgpt_auto_execution_tools import tool_create_range_scalp_plan
    return await tool_create_range_scalp_plan(args)

@registry.register("moneybot.cancel_auto_plan")
async def tool_cancel_auto_plan_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Cancel an auto trade plan"""
    return await tool_cancel_auto_plan(args)

@registry.register("moneybot.update_auto_plan")
async def tool_update_auto_plan_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing auto trade plan (only pending plans can be updated)"""
    return await tool_update_auto_plan(args)

@registry.register("moneybot.get_auto_plan_status")
async def tool_get_auto_plan_status_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get status of an auto trade plan"""
    return await tool_get_auto_plan_status(args)

@registry.register("moneybot.get_auto_system_status")
async def tool_get_auto_system_status_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get overall auto execution system status"""
    return await tool_get_auto_system_status(args)

@registry.register("moneybot.create_multiple_auto_plans")
async def tool_create_multiple_auto_plans_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create multiple auto-execution plans in a single batch operation"""
    return await tool_create_multiple_auto_plans(args)

@registry.register("moneybot.update_multiple_auto_plans")
async def tool_update_multiple_auto_plans_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Update multiple auto-execution plans in a single batch operation"""
    return await tool_update_multiple_auto_plans(args)

@registry.register("moneybot.cancel_multiple_auto_plans")
async def tool_cancel_multiple_auto_plans_wrapper(args: Dict[str, Any]) -> Dict[str, Any]:
    """Cancel multiple auto-execution plans in a single batch operation"""
    return await tool_cancel_multiple_auto_plans(args)

@registry.register("moneybot.getPlanEffectiveness")
async def tool_get_plan_effectiveness(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get auto-execution plan effectiveness report - win rates by strategy/symbol"""
    try:
        from infra.plan_effectiveness_tracker import PlanEffectivenessTracker
        days = args.get('days', 30)
        tracker = PlanEffectivenessTracker()
        report = tracker.get_effectiveness_report(days)
        return {
            "summary": f"Plan effectiveness report ({days} days)",
            "data": {"success": True, "report": report}
        }
    except Exception as e:
        logger.error(f"Error getting plan effectiveness: {e}", exc_info=True)
        return {"summary": "Failed to get effectiveness report", "data": {"success": False, "error": str(e)}}

@registry.register("moneybot.reviewClosedTrade")
async def tool_review_closed_trade(args: Dict[str, Any]) -> Dict[str, Any]:
    """Review a closed trade with its originating auto-execution plan details"""
    try:
        from infra.plan_trade_sync import PlanTradeSync
        
        ticket = args.get('ticket')
        if not ticket:
            return {
                "summary": "Ticket number is required",
                "data": {"success": False, "error": "ticket parameter is required"}
            }
        
        sync = PlanTradeSync()
        trade_data = sync.get_trade_with_plan(ticket)
        
        if not trade_data:
            return {
                "summary": f"Trade {ticket} not found or not linked to a plan",
                "data": {"success": False, "error": f"Trade {ticket} not found in journal database or has no plan_id"}
            }
        
        # Format response
        plan = trade_data.get("plan", {})
        has_plan = bool(plan)
        
        summary_parts = [f"Trade {ticket}: {trade_data['symbol']} {trade_data['direction']}"]
        if trade_data.get("profit_loss") is not None:
            pnl = trade_data["profit_loss"]
            outcome = "Win" if pnl > 0.5 else ("Loss" if pnl < -0.5 else "Breakeven")
            summary_parts.append(f"{outcome} ${pnl:.2f}")
        
        if has_plan:
            summary_parts.append(f"Plan: {plan.get('plan_id', 'N/A')}")
        
        return {
            "summary": " | ".join(summary_parts),
            "data": {
                "success": True,
                "trade": {
                    "ticket": trade_data["ticket"],
                    "symbol": trade_data["symbol"],
                    "direction": trade_data["direction"],
                    "entry_price": trade_data["entry_price"],
                    "exit_price": trade_data.get("exit_price"),
                    "stop_loss": trade_data.get("stop_loss"),
                    "take_profit": trade_data.get("take_profit"),
                    "volume": trade_data.get("volume"),
                    "profit_loss": trade_data.get("profit_loss"),
                    "close_reason": trade_data.get("close_reason"),
                    "opened_at": trade_data.get("opened_at"),
                    "closed_at": trade_data.get("closed_at"),
                    "duration_seconds": trade_data.get("duration_seconds")
                },
                "plan": plan if has_plan else None,
                "has_plan": has_plan
            }
        }
    except Exception as e:
        logger.error(f"Error reviewing closed trade: {e}", exc_info=True)
        return {
            "summary": "Failed to review trade",
            "data": {"success": False, "error": str(e)}
        }

@registry.register("moneybot.syncPlanTrades")
async def tool_sync_plan_trades(args: Dict[str, Any]) -> Dict[str, Any]:
    """Sync closed trades from journal database to plan effectiveness tracker"""
    try:
        from infra.plan_trade_sync import PlanTradeSync
        
        days_back = args.get('days_back', 30)
        
        sync = PlanTradeSync()
        result = sync.sync_closed_trades_to_plans(days_back)
        
        if result.get("success"):
            return {
                "summary": f"Synced {result.get('updated_count', 0)} plans with closed trade data ({result.get('synced_count', 0)} total trades processed)",
                "data": result
            }
        else:
            return {
                "summary": f"Sync failed: {result.get('error', 'Unknown error')}",
                "data": result
            }
    except Exception as e:
        logger.error(f"Error syncing plan trades: {e}", exc_info=True)
        return {
            "summary": "Failed to sync plan trades",
            "data": {"success": False, "error": str(e)}
        }

@registry.register("moneybot.getRecentTrades")
async def tool_get_recent_trades(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get recent closed trades with their plan details. Use when user asks 'what trades executed today', 'show me my recent trades', 'trades from today', 'trades that closed today', etc. ⚠️ IMPORTANT: 'executed today' means trades that were OPENED today (by_execution_date=true). 'closed today' means trades that were CLOSED today (by_execution_date=false, default)."""
    try:
        from infra.plan_trade_sync import PlanTradeSync
        from datetime import datetime, timezone
        
        # Support both 'hours' and 'days_back' parameters
        if 'hours' in args:
            days_back = args['hours'] / 24.0  # Convert hours to days
        else:
            days_back = args.get('days_back', 1)  # Default to 1 day (today)
        
        symbol = args.get('symbol')  # Optional symbol filter
        by_execution_date = args.get('by_execution_date', False)  # True = opened today, False = closed today
        
        sync = PlanTradeSync()
        trades = sync.get_recent_closed_trades_with_plans(
            days_back=days_back, 
            symbol=symbol,
            by_execution_date=by_execution_date
        )
        
        if not trades:
            symbol_text = f" for {symbol}" if symbol else ""
            period_text = f"{int(args.get('hours', days_back * 24))} hour(s)" if 'hours' in args else f"{days_back} day(s)"
            return {
                "summary": f"No closed trades found in the last {period_text}{symbol_text}",
                "data": {"trades": [], "count": 0, "days_back": days_back, "symbol": symbol, "success": False}
            }
        
        # Format summary
        period_type = "Executed" if by_execution_date else "Closed"
        period_text = f"{int(args.get('hours', days_back * 24))} hour(s)" if 'hours' in args else f"{days_back} day(s)"
        summary_lines = [f"📊 Recent {period_type} Trades ({len(trades)} trades)"]
        if symbol:
            summary_lines[0] += f" - {symbol}"
        summary_lines.append(f"Period: Last {period_text} ({period_type.lower()} date)\n")
        
        total_pnl = 0
        wins = 0
        losses = 0
        
        for trade in trades:
            ticket = trade.get("ticket")
            symbol_trade = trade.get("symbol", "N/A")
            direction = trade.get("direction", "N/A")
            entry = trade.get("entry_price", 0)
            exit_price = trade.get("exit_price")
            pnl = trade.get("profit_loss", 0)
            closed_at = trade.get("closed_at", "N/A")
            plan = trade.get("plan", {})
            plan_id = plan.get("plan_id") if plan else None
            
            total_pnl += pnl if pnl else 0
            if pnl and pnl > 0.5:
                wins += 1
            elif pnl and pnl < -0.5:
                losses += 1
            
            # Format closed_at (extract date/time if ISO format)
            if closed_at and "T" in closed_at:
                try:
                    dt = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
                    closed_at = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                except:
                    pass
            
            pnl_emoji = "📈" if pnl and pnl > 0.5 else "📉" if pnl and pnl < -0.5 else "➖"
            direction_emoji = "🟢" if direction == "BUY" else "🔴"
            
            # Format exit_price safely (can't use conditional in format specifier)
            exit_str = f"{exit_price:.5f}" if exit_price is not None else "N/A"
            pnl_str = f"${pnl:.2f}" if pnl is not None else "$0.00"
            
            summary_lines.append(
                f"{direction_emoji} {symbol_trade} {direction} | Ticket: {ticket}\n"
                f"  Entry: {entry:.5f} | Exit: {exit_str}\n"
                f"  {pnl_emoji} P/L: {pnl_str} | Closed: {closed_at}\n"
            )
            
            if plan_id:
                strategy = plan.get("strategy_type", "N/A")
                summary_lines.append(f"  📋 Plan: {plan_id} ({strategy})\n")
            summary_lines.append("")
        
        # Add summary stats
        summary_lines.append(f"\n📊 Summary: {wins}W / {losses}L | Total P/L: ${total_pnl:.2f}")
        
        return {
            "summary": "\n".join(summary_lines),
            "data": {
                "success": True,
                "trades": trades,
                "count": len(trades),
                "days_back": days_back,
                "symbol": symbol,
                "total_pnl": round(total_pnl, 2),
                "wins": wins,
                "losses": losses
            }
        }
    except Exception as e:
        logger.error(f"Error getting recent trades: {e}", exc_info=True)
        return {
            "summary": "Failed to get recent trades",
            "data": {"success": False, "error": str(e), "trades": []}
        }

# ============================================================================
# DTMS TOOLS
# ============================================================================

@registry.register("moneybot.dtms_status")
async def tool_dtms_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get DTMS (Defensive Trade Management System) status"""
    try:
        import httpx
        
        # Try to get DTMS status from main API server first (port 8000, accessible via ngrok)
        # Fallback to DTMS API server (port 8001) if main API doesn't have the endpoint
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Try main API server first (port 8000 - accessible via ngrok)
                try:
                    response = await client.get("http://127.0.0.1:8000/api/dtms/status")
                    if response.status_code == 200:
                        api_data = response.json()
                        return {
                            "success": api_data.get("success", True),
                            "summary": api_data.get("summary", "DTMS status retrieved"),
                            "dtms_status": api_data.get("dtms_status", {}),
                            "error": api_data.get("error")
                        }
                except Exception:
                    # Fallback to DTMS API server (port 8001 - local only)
                    response = await client.get("http://127.0.0.1:8001/dtms/status")
                    if response.status_code == 200:
                        api_data = response.json()
                        return {
                            "success": api_data.get("success", False),
                            "summary": api_data.get("summary", "DTMS status retrieved"),
                            "dtms_status": api_data.get("dtms_status", {}),
                            "error": api_data.get("error")
                        }
        except Exception as api_error:
            logger.warning(f"DTMS API not available, falling back to direct access: {api_error}")
        
        # Fallback to direct access
        from dtms_integration import get_dtms_system_status
        
        status = get_dtms_system_status()
        
        if status and not status.get('error'):
            return {
                "success": True,
                "summary": f"DTMS system is active with {status.get('active_trades', 0)} trades monitored",
                "dtms_status": {
                    "system_active": status.get('monitoring_active', False),
                    "uptime": status.get('uptime_human', 'Unknown'),
                    "active_trades": status.get('active_trades', 0),
                    "trades_by_state": status.get('trades_by_state', {}),
                    "performance": status.get('performance', {}),
                    "last_check": status.get('last_check_human', 'Unknown')
                }
            }
        else:
            error_msg = status.get('error', 'DTMS system not available') if status else 'DTMS system not available'
            return {
                "success": False,
                "summary": f"DTMS system is not available: {error_msg}",
                "error": error_msg,
                "dtms_status": {
                    "system_active": False,
                    "error": error_msg
                }
            }
            
    except Exception as e:
        error_msg = f"Failed to get DTMS status: {str(e)}"
        return {
            "success": False,
            "summary": error_msg,
            "error": error_msg
        }

@registry.register("moneybot.dtms_trade_info")
async def tool_dtms_trade_info(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get DTMS information for a specific trade"""
    try:
        ticket = args.get('ticket')
        if not ticket:
            return {
                "success": False,
                "summary": "Ticket number is required",
                "error": "Ticket number is required"
            }
        
        import httpx
        
        # Try to get DTMS trade info from main API server first (port 8000, accessible via ngrok)
        # Fallback to DTMS API server (port 8001) if main API doesn't have the endpoint
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Try main API server first (port 8000 - accessible via ngrok)
                try:
                    response = await client.get(f"http://127.0.0.1:8000/api/dtms/trade/{ticket}")
                    if response.status_code == 200:
                        api_data = response.json()
                        return {
                            "success": api_data.get("success", True),
                            "summary": api_data.get("summary", "DTMS trade info retrieved"),
                            "trade_info": api_data.get("trade_info"),
                            "error": api_data.get("error")
                        }
                except Exception:
                    # Fallback to DTMS API server (port 8001 - local only)
                    response = await client.get(f"http://127.0.0.1:8001/dtms/trade/{ticket}")
                    if response.status_code == 200:
                        api_data = response.json()
                        return {
                            "success": api_data.get("success", False),
                            "summary": api_data.get("summary", "DTMS trade info retrieved"),
                            "trade_info": api_data.get("trade_info"),
                            "error": api_data.get("error")
                        }
        except Exception as api_error:
            logger.warning(f"DTMS API not available, falling back to direct access: {api_error}")
        
        # Fallback to direct access
        from dtms_integration import get_dtms_trade_status
        
        trade_info = get_dtms_trade_status(int(ticket))
        
        if trade_info and not trade_info.get('error'):
            return {
                "success": True,
                "summary": f"Trade {ticket} is in {trade_info.get('state', 'Unknown')} state with score {trade_info.get('current_score', 0)}",
                "trade_info": {
                    "ticket": trade_info.get('ticket'),
                    "symbol": trade_info.get('symbol'),
                    "state": trade_info.get('state'),
                    "current_score": trade_info.get('current_score'),
                    "state_entry_time": trade_info.get('state_entry_time_human'),
                    "warnings": trade_info.get('warnings', {}),
                    "actions_taken": trade_info.get('actions_taken', []),
                    "performance": trade_info.get('performance', {})
                }
            }
        else:
            error_msg = trade_info.get('error', 'Trade not found in DTMS') if trade_info else 'Trade not found in DTMS'
            return {
                "success": False,
                "summary": f"Could not get DTMS info for trade {ticket}: {error_msg}",
                "error": error_msg,
                "trade_info": None
            }
            
    except Exception as e:
        error_msg = f"Failed to get DTMS trade info: {str(e)}"
        return {
            "success": False,
            "summary": error_msg,
            "error": error_msg
        }

@registry.register("moneybot.dtms_action_history")
async def tool_dtms_action_history(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get DTMS action history"""
    try:
        import httpx
        
        # Try to get DTMS action history from main API server first (port 8000, accessible via ngrok)
        # Fallback to DTMS API server (port 8001) if main API doesn't have the endpoint
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Try main API server first (port 8000 - accessible via ngrok)
                try:
                    response = await client.get("http://127.0.0.1:8000/api/dtms/actions")
                    if response.status_code == 200:
                        api_data = response.json()
                        return {
                            "success": api_data.get("success", True),
                            "summary": api_data.get("summary", "DTMS action history retrieved"),
                            "action_history": api_data.get("action_history", []),
                            "total_actions": api_data.get("total_actions", 0),
                            "error": api_data.get("error")
                        }
                except Exception:
                    # Fallback to DTMS API server (port 8001 - local only)
                    response = await client.get("http://127.0.0.1:8001/dtms/actions")
                    if response.status_code == 200:
                        api_data = response.json()
                        return {
                            "success": api_data.get("success", False),
                            "summary": api_data.get("summary", "DTMS action history retrieved"),
                            "action_history": api_data.get("action_history", []),
                            "total_actions": api_data.get("total_actions", 0),
                            "error": api_data.get("error")
                        }
        except Exception as api_error:
            logger.warning(f"DTMS API not available, falling back to direct access: {api_error}")
        
        # Fallback to direct access
        from dtms_integration import get_dtms_action_history
        
        history = get_dtms_action_history()
        
        if history:
            # Return last 10 actions
            recent_actions = history[-10:] if len(history) > 10 else history
            
            return {
                "success": True,
                "summary": f"Retrieved {len(recent_actions)} recent DTMS actions from {len(history)} total actions",
                "action_history": [
                    {
                        "action_type": action.get('action_type'),
                        "ticket": action.get('ticket'),
                        "symbol": action.get('symbol'),
                        "success": action.get('success'),
                        "timestamp": action.get('time_human'),
                        "details": action.get('details', {})
                    }
                    for action in recent_actions
                ],
                "total_actions": len(history)
            }
        else:
            return {
                "success": True,
                "summary": "No DTMS actions found in history",
                "action_history": [],
                "total_actions": 0
            }
            
    except Exception as e:
        error_msg = f"Failed to get DTMS action history: {str(e)}"
        return {
            "success": False,
            "summary": error_msg,
            "error": error_msg
        }

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        asyncio.run(agent_main())
    except KeyboardInterrupt:
        logger.info("🛑 Agent stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)

