#!/usr/bin/env python3
"""
Standalone ChatGPT Discord Bot
Connects Discord with ChatGPT and MT5 API
Now includes: Trade Monitor, Signal Scanner, Circuit Breaker, Enhanced Logging
"""

import os
import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
import httpx
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

# Discord notifications
try:
    from discord_notifications import DiscordNotifier
    discord_notifier = DiscordNotifier()
    DISCORD_ENABLED = True
    print("SUCCESS: Discord notifications enabled")
except ImportError as e:
    DISCORD_ENABLED = False
    print(f"WARNING: Discord notifications disabled: {e}")

# Load environment variables
load_dotenv()

# Configure basic logging (will be enhanced in setup_file_logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ===== HELPER FUNCTIONS =====

def format_discord_message(text: str) -> str:
    """Format text for Discord messages."""
    if not text:
        return ""
    # Discord uses different markdown, so we'll keep it simple
    return text

def escape_markdown(text: str) -> str:
    """Escape special characters for Discord markdown."""
    if not text:
        return ""
    # Discord markdown is less strict, so we'll just return the text
    return text

def get_plan_id_from_ticket(ticket: int) -> str:
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


# Import logging infrastructure
try:
    from infra.analytics_logger import AnalyticsLogger
    analytics_logger = AnalyticsLogger()
    logger.info("✅ Analytics logger loaded")
except Exception as e:
    logger.warning(f"⚠️ Could not load analytics logger: {e}")
    analytics_logger = None

# Import trade close logger (NEW)
try:
    from infra.trade_close_logger import get_close_logger
    logger.info("✅ Trade close logger available")
except Exception as e:
    logger.warning(f"⚠️ Could not load trade close logger: {e}")
    get_close_logger = None

# Import custom alert system (NEW)
try:
    from infra.custom_alerts import CustomAlertManager
    from infra.alert_monitor import AlertMonitor
    logger.info("✅ Custom alert system available")
except Exception as e:
    logger.warning(f"⚠️ Could not load custom alert system: {e}")
    CustomAlertManager = None
    AlertMonitor = None


# Import staged activation system (safe, optional)
try:
    from infra.staged_activation_system import (
        StagedActivationConfig,
        start_staged_activation,
        stop_staged_activation,
        get_position_size_multiplier,
        record_trade as staged_record_trade,
        record_performance_metric as staged_record_metric,
        get_activation_status as get_staged_activation_status,
    )
    logger.info("✅ Staged activation system available")
except Exception as e:
    logger.warning(f"⚠️ Could not load staged activation system: {e}")
    StagedActivationConfig = None
    start_staged_activation = None
    stop_staged_activation = None
    get_position_size_multiplier = None
    staged_record_trade = None
    staged_record_metric = None
    get_staged_activation_status = None

# Import decision traces (safe, optional)
try:
    from infra.decision_traces import get_trace_manager
    logger.info("✅ Decision trace manager available")
except Exception as e:
    logger.warning(f"⚠️ Could not load decision trace manager: {e}")
    get_trace_manager = None

# Optional symbol config loader (hot-reload)
try:
    from config.symbol_config_loader import get_config_loader
    _symbol_config_available = True
except Exception as e:
    logger.warning(f"⚠️ Could not load symbol config loader: {e}")
    _symbol_config_available = False


def setup_file_logging():
    """
    Configure file logging with rotation.
    Creates two log files:
    - chatgpt_bot.log: All logs (INFO and above)
    - errors.log: Errors only (ERROR and above)
    """
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Main log file handler (10MB max, 5 backups)
    main_handler = RotatingFileHandler(
        log_dir / "chatgpt_bot.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    main_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    main_handler.setLevel(logging.INFO)
    
    # Error log file handler (5MB max, 3 backups)
    error_handler = RotatingFileHandler(
        log_dir / "errors.log",
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n'
        'Location: %(pathname)s:%(lineno)d'
    ))
    error_handler.setLevel(logging.ERROR)
    
    # Add handlers to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(main_handler)
    root_logger.addHandler(error_handler)
    
    logger.info("✅ File logging initialized")
    logger.info(f"   → Main log: {log_dir / 'chatgpt_bot.log'}")
    logger.info(f"   → Error log: {log_dir / 'errors.log'}")

# Import ChatGPT handler
from handlers.chatgpt_bridge import (
    chatgpt_start,
    chatgpt_message,
    chatgpt_button,
    chatgpt_end,
    setgptkey_command,
    CHATTING,
    user_conversations
)

# Global scheduler for background jobs
scheduler = None
# Discord notifications enabled via DISCORD_ENABLED flag
trade_monitor = None  # TradeMonitor for trailing stops
exit_monitor = None  # ExitMonitor for profit protection
intelligent_exit_manager = None  # IntelligentExitManager for breakeven/partial profits/VIX adjustments
binance_service = None  # BinanceService for real-time streaming + 37 enrichment fields
order_flow_service = None  # OrderFlowService for whale detection + order book analysis
# Dedicated event loop thread for OrderFlowService (Binance websockets need a loop that stays alive)
order_flow_loop = None
order_flow_thread = None
loss_cutter_instance = None  # LossCutter with persistent ProfitProtector for cooldown tracking
# loss_cut_monitor removed - using enhanced automated loss-cutting system
chatgpt_logger = None  # ChatGPT conversation logger
tracked_positions = set()  # Track positions where intelligent exits have been enabled
tracked_dtms_positions = set()  # Track positions where DTMS protection has been enabled
auto_execution_system = None  # Auto execution system for monitoring and executing trade plans
dtms_engine = None  # DTMS (Defensive Trade Management System) for advanced position protection
universal_sl_tp_manager = None  # Universal Dynamic SL/TP Manager for strategy-aware trade management


# ===== BACKGROUND MONITORING FUNCTIONS =====

# PHASE 5: DTMS monitoring cycle removed - using API server instead
# DTMS monitoring is now handled by dtms_api_server.py (port 8001)
# This function is kept for backward compatibility but does nothing
async def run_dtms_monitoring_cycle(app):
    """Run DTMS monitoring cycle - PHASE 5: Disabled (using API server)"""
    # DTMS monitoring is now handled by dtms_api_server.py
    # No local monitoring needed
    pass
    
    # OLD CODE (commented out for rollback):
    # global dtms_engine
    # 
    # try:
    #     if dtms_engine is None:
    #         return
    #     
    #     # Import DTMS monitoring function
    #     from dtms_integration import run_dtms_monitoring_cycle as dtms_cycle
    #     
    #     # Run DTMS monitoring cycle
    #     await dtms_cycle()
    #     
    # except Exception as e:
    #     logger.error(f"❌ DTMS monitoring cycle failed: {e}")
    #     import traceback
    #     logger.debug(traceback.format_exc())

async def check_trailing_stops_async():
    """Async wrapper for TradeMonitor.check_trailing_stops()"""
    global trade_monitor
    if trade_monitor:
        try:
            # Run sync function in executor to avoid blocking
            import asyncio
            loop = asyncio.get_event_loop()
            actions = await loop.run_in_executor(None, trade_monitor.check_trailing_stops)
            if actions:
                logger.info(f"Trailing stops: {len(actions)} actions taken")
        except Exception as e:
            logger.error(f"Error checking trailing stops: {e}")


async def auto_enable_intelligent_exits_async():
    """Auto-enable Intelligent Exits for any newly opened positions (covers non-OCO fills)."""
    global tracked_positions
    try:
        import os
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("http://localhost:8000/api/v1/positions")
            if resp.status_code != 200:
                return
            positions = resp.json().get("positions", []) or []
            if not positions:
                return
            # Phone hub dispatch endpoint and token
            phone_token = os.getenv("PHONE_BEARER_TOKEN", "phone_control_bearer_token_2025_v1_secure")
            headers = {"Authorization": f"Bearer {phone_token}"}
            for pos in positions:
                ticket = int(pos.get("ticket")) if pos.get("ticket") else None
                if not ticket:
                    continue
                if ticket in tracked_positions:
                    continue
                # Enable via desktop agent tool alias
                payload = {
                    "tool": "moneybot.enableIntelligentExits",
                    "arguments": {"ticket": ticket},
                    "timeout": 60,
                }
                try:
                    r = await client.post(
                        "http://localhost:8000/dispatch",
                        headers=headers,
                        json=payload,
                    )
                    if r.status_code == 200:
                        tracked_positions.add(ticket)
                        logger.info(f"✅ Intelligent Exits auto-enabled for ticket {ticket}")
                    else:
                        logger.warning(f"IE auto-enable failed for {ticket}: {r.status_code} {r.text}")
                except Exception as e:
                    logger.warning(f"IE auto-enable exception for {ticket}: {e}")
    except Exception as e:
        logger.error(f"Error in auto_enable_intelligent_exits_async: {e}")


async def auto_enable_dtms_protection_async():
    """Auto-enroll newly opened positions into DTMS via API server."""
    # PHASE 5: Updated to use API server instead of local engine
    # This function already uses API (calls http://localhost:8001/dtms/trade/enable)
    global tracked_dtms_positions
    # dtms_engine check removed - API server handles everything
    try:
        # PHASE 5: Monitoring is handled by API server, no local start needed
        # OLD CODE (commented out for rollback):
        # global dtms_engine
        # if not dtms_engine:
        #     return
        # try:
        #     started = dtms_engine.start_monitoring()
        #     if started:
        #         logger.info("✅ DTMS monitoring started")
        # except Exception:
        #     pass
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("http://localhost:8000/api/v1/positions")
            if resp.status_code != 200:
                return
            positions = resp.json().get("positions", []) or []
            for pos in positions:
                ticket = int(pos.get("ticket")) if pos.get("ticket") else None
                if not ticket or ticket in tracked_dtms_positions:
                    continue
                symbol = pos.get("symbol")
                direction = "BUY" if str(pos.get("type")).upper() in ("0", "BUY") else "SELL"
                entry_price = float(pos.get("price_open", 0) or 0)
                volume = float(pos.get("volume", 0) or 0)
                sl = pos.get("sl")
                tp = pos.get("tp")
                try:
                    # Enable DTMS in the API server process so the website sees it
                    form = {
                        "ticket": str(ticket)
                    }
                    # Optional extras if API supports them in future
                    # form.update({"symbol": symbol, "direction": direction, "entry_price": str(entry_price), "volume": str(volume)})
                    resp2 = await client.post(
                        "http://localhost:8001/dtms/trade/enable",
                        data=form,
                        headers={"Content-Type": "application/x-www-form-urlencoded"}
                    )
                    if resp2.status_code == 200 and (resp2.json().get("success")):
                        tracked_dtms_positions.add(ticket)
                        logger.info(f"✅ DTMS protection auto-enabled via API for ticket {ticket}")
                    else:
                        logger.warning(f"DTMS API enable failed for {ticket}: {resp2.status_code} {resp2.text}")
                except Exception as e:
                    logger.warning(f"DTMS auto-enroll API error for {ticket}: {e}")
    except Exception as e:
        logger.error(f"Error in auto_enable_dtms_protection_async: {e}")


async def check_exit_signals_async():
    """Check for exit signals and send Discord alerts"""
    global exit_monitor
    if not exit_monitor:
        return
    
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        
        # Run exit signal check in executor
        actions = await loop.run_in_executor(None, exit_monitor.check_exit_signals)
        
        if actions:
            logger.info(f"Exit signals: {len(actions)} detected")
            
            # Send Discord alerts for each exit signal
            for action in actions:
                try:
                    message = exit_monitor.format_exit_alert(action)
                    if DISCORD_ENABLED:
                        discord_notifier.send_system_alert("EXIT_SIGNAL", message)
                    logger.info(f"📤 Exit alert sent for ticket {action['ticket']}")
                except Exception as e:
                    logger.error(f"Failed to send exit alert: {e}")
    
    except Exception as e:
        logger.error(f"Error checking exit signals: {e}")


async def check_intelligent_exits_async():
    """Check for intelligent exit management (breakeven, partial profits, VIX adjustments)"""
    global intelligent_exit_manager
    if not intelligent_exit_manager:
        return
    
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        
        # Run intelligent exit check in executor
        actions = await loop.run_in_executor(None, intelligent_exit_manager.check_exits)
        
        if actions:
            logger.info(f"Intelligent exits: {len(actions)} actions taken")
            
            # Send Discord alerts for each action
            for action in actions:
                try:
                    action_type = action.get("action")
                    symbol = action.get("symbol")
                    ticket = action.get("ticket")
                    
                    if action_type == "breakeven":
                        emoji = "🎯"
                        message = (
                            f"{emoji} *Breakeven SL Set*\n\n"
                            f"Ticket: {ticket}\n"
                            f"Symbol: {symbol}\n"
                            f"Old SL: {action.get('old_sl', 0):.5f}\n"
                            f"New SL: {action.get('new_sl', 0):.5f}\n\n"
                            f"✅ Position now risk-free!"
                        )
                    elif action_type == "partial_profit":
                        emoji = "💰"
                        message = (
                            f"{emoji} *Partial Profit Taken*\n\n"
                            f"Ticket: {ticket}\n"
                            f"Symbol: {symbol}\n"
                            f"Closed Volume: {action.get('closed_volume', 0):.2f} lots\n"
                            f"Remaining: {action.get('remaining_volume', 0):.2f} lots\n"
                            f"Profit: ~${action.get('realized_profit', 0):.2f}\n\n"
                            f"✅ Letting runner ride!"
                        )
                    elif action_type == "vix_adjustment":
                        emoji = "⚠️"
                        message = (
                            f"{emoji} *VIX Spike - SL Widened*\n\n"
                            f"Ticket: {ticket}\n"
                            f"Symbol: {symbol}\n"
                            f"VIX: {action.get('vix_price', 0):.2f}\n"
                            f"Old SL: {action.get('old_sl', 0):.5f}\n"
                            f"New SL: {action.get('new_sl', 0):.5f}\n\n"
                            f"⚡ Stop widened for volatility"
                        )
                    elif action_type == "hybrid_adjustment":
                        emoji = "🔬"
                        details = action.get('details', {})
                        atr = details.get('atr', 0)
                        vix_mult = details.get('vix_multiplier', 1.0)
                        vix_price = action.get('vix_price', 0)
                        message = (
                            f"{emoji} *Hybrid ATR+VIX Adjustment*\n\n"
                            f"Ticket: {ticket}\n"
                            f"Symbol: {symbol}\n"
                            f"Old SL: {action.get('old_sl', 0):.5f}\n"
                            f"New SL: {action.get('new_sl', 0):.5f}\n\n"
                            f"📊 ATR: {atr:.3f}\n"
                            f"⚡ VIX: {vix_price if vix_price else 'Normal'}\n"
                            f"🔢 Multiplier: {vix_mult:.2f}x\n\n"
                            f"✅ Stop adjusted for market conditions"
                        )
                    elif action_type == "trailing_stop":
                        emoji = "📈"
                        details = action.get('details', {})
                        atr = details.get('atr', 0)
                        distance = details.get('trailing_distance', 0)
                        current_price = details.get('price', 0)
                        message = (
                            f"{emoji} *ATR Trailing Stop*\n\n"
                            f"Ticket: {ticket}\n"
                            f"Symbol: {symbol}\n"
                            f"Price: {current_price:.5f}\n"
                            f"Old SL: {action.get('old_sl', 0):.5f}\n"
                            f"New SL: {action.get('new_sl', 0):.5f}\n\n"
                            f"📊 ATR: {atr:.3f}\n"
                            f"📏 Distance: {distance:.3f}\n\n"
                            f"✅ Stop trailed with price movement"
                        )
                    elif action_type == "position_closed":
                        # Enhanced closure notification with detailed information
                        closure_reason = action.get('closure_reason', 'Unknown')
                        manual_closure = action.get('manual_closure', False)
                        closed_unmonitored = action.get('closed_unmonitored', False)
                        actions_executed = action.get('actions_executed', 'None')
                        final_pl = action.get('final_pl', 0)
                        entry_price = action.get('entry_price', 0)
                        exit_price = action.get('exit_price', 0)
                        direction = action.get('direction', 'unknown')
                        
                        # Choose emoji based on closure type and P/L
                        if final_pl > 0:
                            pl_emoji = "💚"
                        elif final_pl < 0:
                            pl_emoji = "🔴"
                        else:
                            pl_emoji = "⚪"
                        
                        if closed_unmonitored:
                            emoji = "⚠️"
                            status_msg = "CLOSED BEFORE MONITORING"
                            explanation = (
                                "\n\n⚠️ *Critical:* This position closed before intelligent exits could monitor it.\n"
                                "Possible causes:\n"
                                "• Bot was offline/restarting when position closed\n"
                                "• Position hit SL/TP immediately after opening\n"
                                "• Very short-lived trade"
                            )
                        elif manual_closure and actions_executed == "None":
                            emoji = "🟡"
                            status_msg = "MANUAL CLOSURE"
                            explanation = (
                                "\n\n🟡 *Notice:* Position closed manually before intelligent exits could execute.\n"
                                f"• The position was being monitored\n"
                                f"• No protection actions had triggered yet"
                            )
                        elif manual_closure and actions_executed != "None":
                            emoji = "🔵"
                            status_msg = "MANUAL CLOSURE (Protected)"
                            explanation = (
                                f"\n\n🔵 *Info:* Position closed manually after intelligent exits were active.\n"
                                f"• Actions taken: {actions_executed}"
                            )
                        else:
                            emoji = "✅"
                            status_msg = closure_reason.upper()
                            explanation = (
                                f"\n\n✅ Position closed via {closure_reason}.\n"
                                f"• Intelligent actions: {actions_executed}"
                            )
                        
                        message = (
                            f"{emoji} *{status_msg}*\n\n"
                            f"Ticket: {ticket}\n"
                            f"Symbol: {symbol}\n"
                            f"Direction: {direction.upper()}\n"
                            f"Entry: {entry_price:.5f}\n"
                            f"Exit: {exit_price:.5f}\n"
                            f"P/L: {pl_emoji} ${final_pl:.2f}\n"
                            f"{explanation}"
                        )
                    elif action.get("type") == "whale_alert":
                        # NEW: Whale order alert from Order Flow Service
                        emoji = "🐋"
                        severity = action.get("severity", "HIGH")
                        whale_side = action.get("whale_side", "UNKNOWN")
                        reason = action.get("reason", "")
                        executed_actions = action.get("executed_actions", [])
                        recommendation = action.get("recommendation", "")
                        
                        executed_msg = ""
                        if executed_actions:
                            action_list = []
                            if "sl_tightened" in executed_actions:
                                action_list.append("SL tightened")
                            if "partial_exit" in executed_actions:
                                action_list.append("Partial exit")
                            if action_list:
                                executed_msg = f"\n\n✅ *AUTO-EXECUTED: {', '.join(action_list)}*"
                        
                        message = (
                            f"{emoji} *{severity}: Large {whale_side} Whale Detected*\n\n"
                            f"Ticket: {ticket}\n"
                            f"Symbol: {symbol}\n"
                            f"Whale Order: {reason}{executed_msg}\n\n"
                            f"⚠️ {recommendation}\n\n"
                            f"💡 *This large institutional order may impact price movement*\n"
                            f"📊 Automatic protection actions executed to protect position"
                        )
                    elif action.get("type") == "whale_sl_tightened":
                        # NEW: Auto-tightened SL due to whale
                        emoji = "🐋"
                        old_sl = action.get("old_sl", 0)
                        new_sl = action.get("new_sl", 0)
                        severity = action.get("severity", "HIGH")
                        message = (
                            f"{emoji} *SL Auto-Tightened ({severity} Whale)*\n\n"
                            f"Ticket: {ticket}\n"
                            f"Symbol: {symbol}\n"
                            f"Old SL: {old_sl:.5f}\n"
                            f"New SL: {new_sl:.5f}\n\n"
                            f"✅ Stop loss tightened automatically due to large institutional order"
                        )
                    elif action.get("type") == "void_warning":
                        # NEW: Liquidity void warning from Order Flow Service
                        emoji = "⚠️"
                        void_range = action.get("void_range", "")
                        distance_pct = action.get("distance_pct", 0)
                        severity = action.get("severity", 1.0)
                        executed_actions = action.get("executed_actions", [])
                        recommendation = action.get("recommendation", "")
                        
                        executed_msg = ""
                        if executed_actions:
                            if "full_close" in executed_actions:
                                executed_msg = "\n\n✅ *AUTO-EXECUTED: Position fully closed*"
                            elif "partial_exit" in executed_actions:
                                executed_msg = "\n\n✅ *AUTO-EXECUTED: Partial exit taken*"
                        
                        message = (
                            f"{emoji} *Liquidity Void Ahead*\n\n"
                            f"Ticket: {ticket}\n"
                            f"Symbol: {symbol}\n"
                            f"Void Range: {void_range}\n"
                            f"Distance: {distance_pct:.3f}%\n"
                            f"Severity: {severity:.1f}x normal{executed_msg}\n\n"
                            f"⚠️ Thin order book zone detected\n"
                            f"💡 {recommendation}\n\n"
                            f"📊 *Price may gap through void - partial exit protects against slippage*"
                        )
                    else:
                        message = f"🔔 Exit action: {action_type or action.get('type', 'unknown')}"
                    
                    if DISCORD_ENABLED:
                        discord_notifier.send_system_alert("INTELLIGENT_EXIT", message)
                    
                    # Log with proper action type identifier
                    log_action_type = action_type or action.get("type", "unknown")
                    logger.info(f"📤 Intelligent exit alert sent for ticket {ticket}: {log_action_type}")
                except Exception as e:
                    logger.error(f"Failed to send intelligent exit alert: {e}")
    
    except Exception as e:
        logger.error(f"Error checking intelligent exits: {e}")


async def auto_enable_dtms_protection_async():
    """Automatically enable DTMS protection for all new positions via API"""
    global tracked_dtms_positions
    
    try:
        import MetaTrader5 as mt5
        import httpx
        
        # Get open positions
        positions = mt5.positions_get()
        if not positions:
            return
        
        for position in positions:
            ticket = position.ticket
            
            # Check if already tracked by DTMS
            if ticket in tracked_dtms_positions:
                continue
            
            # Extract position details
            symbol = position.symbol
            entry_price = position.price_open
            volume = position.volume
            sl = position.sl
            tp = position.tp
            direction = "BUY" if position.type == mt5.ORDER_TYPE_BUY else "SELL"
            
            # Enable DTMS for ALL positions (even without SL/TP)
            try:
                # Use DTMS API to enable protection
                async with httpx.AsyncClient(timeout=10.0) as client:
                    dtms_data = {
                        "symbol": symbol,
                        "direction": direction,
                        "entry": entry_price,
                        "stop_loss": sl if sl > 0 else None,
                        "take_profit": tp if tp > 0 else None,
                        "volume": volume,
                        "ticket": ticket,
                        "action": "enable"
                    }
                    
                    # Try to enable DTMS via API
                    response = await client.post(
                        "http://localhost:8001/dtms/trade/enable",
                        json=dtms_data
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("success"):
                            tracked_dtms_positions.add(ticket)
                            
                            # Send Discord notification
                            if DISCORD_ENABLED:
                                discord_notifier.send_system_alert("DTMS_PROTECTION", 
                                    f"DTMS Protection Auto-Enabled\n\n"
                                    f"Ticket: {ticket}\n"
                                    f"Symbol: {symbol}\n"
                                    f"Direction: {direction}\n"
                                    f"Entry: {entry_price:.5f}\n\n"
                                    f"DTMS Protection Active:\n"
                                    f"• State Machine Monitoring\n"
                                    f"• Adaptive Risk Management\n"
                                    f"• Automated Defensive Actions\n\n"
                                    f"Your position is under institutional-grade protection!"
                                )
                            
                            logger.info(f"✅ Auto-enabled DTMS protection for ticket {ticket} ({symbol})")
                        else:
                            logger.warning(f"DTMS API returned success=False for ticket {ticket}: {result.get('error', 'Unknown error')}")
                    else:
                        logger.warning(f"DTMS API returned status {response.status_code} for ticket {ticket}")
                
            except Exception as e:
                logger.error(f"Failed to auto-enable DTMS protection for ticket {ticket}: {e}")
        
        # Clean up tracked positions that are no longer open
        open_tickets = {p.ticket for p in positions}
        closed_tickets = tracked_dtms_positions - open_tickets
        if closed_tickets:
            tracked_dtms_positions.difference_update(closed_tickets)
            logger.debug(f"Removed {len(closed_tickets)} closed positions from DTMS tracking")
    
    except Exception as e:
        logger.error(f"Error in auto-enable DTMS protection: {e}")

async def auto_enable_intelligent_exits_async():
    """Automatically enable intelligent exits for all new positions"""
    global intelligent_exit_manager, tracked_positions
    if not intelligent_exit_manager:
        return
    
    try:
        from config import settings
        
        # Check if auto-enable is enabled
        if not settings.INTELLIGENT_EXITS_AUTO_ENABLE:
            return
        
        import asyncio
        import MetaTrader5 as mt5
        
        # Get open positions
        positions = mt5.positions_get()
        if not positions:
            return
        
        for position in positions:
            ticket = position.ticket
            
            # Check if rule actually exists in the manager (in case it was disabled via API)
            if ticket in tracked_positions:
                # Verify the rule still exists
                if not intelligent_exit_manager.rules.get(ticket):
                    # Rule was removed but ticket is still in tracked_positions
                    logger.debug(f"Ticket {ticket} was in tracked_positions but rule doesn't exist - removing from tracking")
                    tracked_positions.discard(ticket)
                else:
                    # Rule exists and is tracked, skip
                    continue
            
            # Extract position details
            symbol = position.symbol
            entry_price = position.price_open
            current_price = position.price_current
            sl = position.sl
            tp = position.tp
            direction = "buy" if position.type == mt5.ORDER_TYPE_BUY else "sell"
            
            # Skip positions without SL or TP
            if sl == 0 or tp == 0:
                logger.debug(f"Skipping ticket {ticket} - no SL or TP set")
                continue
            
            # Phase 8: Trade Type Classification (if enabled)
            base_breakeven_pct = settings.INTELLIGENT_EXITS_BREAKEVEN_PCT
            base_partial_pct = settings.INTELLIGENT_EXITS_PARTIAL_PCT
            partial_close_pct = settings.INTELLIGENT_EXITS_PARTIAL_CLOSE_PCT
            classification_info = {}
            
            try:
                from config import settings as config_settings
                enable_classification = getattr(config_settings, 'ENABLE_TRADE_TYPE_CLASSIFICATION', True)
                
                if enable_classification:
                    from infra.trade_type_classifier import TradeTypeClassifier
                    from infra.session_detector import get_current_session
                    from infra.weekend_profile_manager import WeekendProfileManager
                    
                    # Get session info
                    session_info = None
                    try:
                        session_info = get_current_session()
                    except Exception:
                        pass
                    
                    # Check if weekend is active
                    weekend_manager = WeekendProfileManager()
                    is_weekend = weekend_manager.is_weekend_active() and symbol.upper() in ["BTCUSDc", "BTCUSD"]
                    
                    # Get position comment for classification
                    comment = getattr(position, 'comment', None) or ''
                    
                    # Classify trade type
                    classifier = TradeTypeClassifier(mt5_service, None)  # session_service not needed if session_info provided
                    classification = classifier.classify(
                        symbol=symbol,
                        entry_price=entry_price,
                        stop_loss=sl,
                        comment=comment,
                        session_info=session_info,
                        is_weekend=is_weekend and symbol.upper() in ["BTCUSDc", "BTCUSD"]  # NEW
                    )
                    
                    trade_type = classification.get("trade_type", "INTRADAY")
                    confidence = classification.get("confidence", 0.0)
                    reasoning = classification.get("reasoning", "Default classification")
                    
                    classification_info = {
                        "trade_type": trade_type,
                        "confidence": confidence,
                        "reasoning": reasoning,
                        "factors": classification.get("factors", {})
                    }
                    
                    # Set base parameters based on classification
                    if trade_type == "WEEKEND":
                        base_breakeven_pct = 25.0
                        base_partial_pct = 50.0  # Weekend-specific
                        partial_close_pct = 60.0  # Weekend-specific
                        trailing_start_pct = 50.0  # Weekend-specific
                        trailing_atr_mult = 1.2  # Weekend-specific
                        vix_threshold = 20.0  # Weekend-specific
                        logger.info(f"📊 Trade Classification: WEEKEND (confidence: {confidence:.2f}) - Using 25%/50% base triggers")
                    elif trade_type == "SCALP":
                        base_breakeven_pct = 25.0
                        base_partial_pct = 40.0
                        partial_close_pct = 70.0
                        trailing_start_pct = 40.0
                        trailing_atr_mult = 0.7
                        vix_threshold = 18.0
                        logger.info(f"📊 Trade Classification: SCALP (confidence: {confidence:.2f}) - Using 25%/40% base triggers")
                    else:  # INTRADAY
                        base_breakeven_pct = 30.0
                        base_partial_pct = 60.0
                        partial_close_pct = 50.0
                        trailing_start_pct = 60.0
                        trailing_atr_mult = 1.0
                        vix_threshold = 18.0
                        logger.info(f"📊 Trade Classification: INTRADAY (confidence: {confidence:.2f}) - Using 30%/60% base triggers")
                    
                    logger.info(f"   Classification reasoning: {reasoning}")
                else:
                    logger.debug(f"Trade classification disabled (ENABLE_TRADE_TYPE_CLASSIFICATION={enable_classification})")
            except Exception as e:
                logger.warning(f"Trade classification failed for ticket {ticket}: {e}")
                # Continue with default values
            
            # Fetch Advanced features for adaptive exit management
            advanced_features = None
            advanced_adjustments = None
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as client:
                    v8_response = await client.get(f"http://localhost:8000/api/v1/features/advanced/{symbol}")
                    if v8_response.status_code == 200:
                        advanced_features = v8_response.json()
                        logger.debug(f"Fetched Advanced features for {symbol}")
                    else:
                        logger.warning(f"Failed to fetch Advanced features for {symbol}: {v8_response.status_code}")
            except Exception as e:
                logger.warning(f"Error fetching Advanced features for {symbol}: {e}")
            
            # Add classification info to advanced_features for transition logic
            if advanced_features is None:
                advanced_features = {}
            if classification_info:
                advanced_features["classification"] = classification_info
            
            # Add Advanced-enhanced intelligent exit rule (with classification-based base parameters)
            try:
                result = intelligent_exit_manager.add_rule_advanced(
                    ticket=ticket,
                    symbol=symbol,
                    entry_price=entry_price,
                    direction=direction,
                    initial_sl=sl,
                    initial_tp=tp,
                    advanced_features=advanced_features,
                    base_breakeven_pct=base_breakeven_pct,  # Use classification-based value
                    base_partial_pct=base_partial_pct,  # Use classification-based value
                    partial_close_pct=partial_close_pct,  # Use classification-based value
                    vix_threshold=vix_threshold if 'vix_threshold' in locals() else settings.INTELLIGENT_EXITS_VIX_THRESHOLD,  # Use classification-based value
                    use_hybrid_stops=settings.INTELLIGENT_EXITS_USE_HYBRID_STOPS,
                    trailing_enabled=settings.INTELLIGENT_EXITS_TRAILING_ENABLED,
                    trailing_atr_multiplier=trailing_atr_mult if 'trailing_atr_mult' in locals() else None  # NEW: Weekend support
                )
                
                advanced_adjustments = result.get("advanced_adjustments", {})
                rule = result.get("rule")
                
                # Mark as tracked
                tracked_positions.add(ticket)
                
                # Calculate trigger prices for notification (using Advanced-adjusted percentages)
                if direction == "buy":
                    potential_profit = tp - entry_price
                    risk = entry_price - sl
                else:
                    potential_profit = entry_price - tp
                    risk = sl - entry_price

                # Use Advanced-adjusted trigger percentages
                advanced_breakeven_pct = advanced_adjustments.get("breakeven_pct", settings.INTELLIGENT_EXITS_BREAKEVEN_PCT)
                advanced_partial_pct = advanced_adjustments.get("partial_pct", settings.INTELLIGENT_EXITS_PARTIAL_PCT)

                breakeven_price = entry_price + (potential_profit * advanced_breakeven_pct / 100.0) if direction == "buy" else entry_price - (potential_profit * advanced_breakeven_pct / 100.0)
                partial_price = entry_price + (potential_profit * advanced_partial_pct / 100.0) if direction == "buy" else entry_price - (potential_profit * advanced_partial_pct / 100.0)

                # Build Advanced adjustment message
                advanced_message = ""
                if advanced_adjustments and advanced_adjustments.get("advanced_factors"):
                    advanced_reasoning = advanced_adjustments.get("reasoning", "")
                    advanced_factors = ", ".join(advanced_adjustments.get("advanced_factors", []))
                    base_breakeven = advanced_adjustments.get("base_breakeven_pct", settings.INTELLIGENT_EXITS_BREAKEVEN_PCT)
                    base_partial = advanced_adjustments.get("base_partial_pct", settings.INTELLIGENT_EXITS_PARTIAL_PCT)

                    advanced_message = (
                        f"\n\n🔬 *Advanced-Enhanced Exits Active*\n"
                        f"Base: {base_breakeven:.0f}% / {base_partial:.0f}%\n"
                        f"Advanced Adjusted: {advanced_breakeven_pct:.0f}% / {advanced_partial_pct:.0f}%\n"
                        f"Factors: {advanced_factors}\n"
                        f"Reason: {advanced_reasoning}"
                    )
                
                # Send Discord notification
                if DISCORD_ENABLED:
                    # Get plan_id if this is an auto-executed trade
                    plan_id = get_plan_id_from_ticket(ticket)
                    plan_id_line = f"📊 Plan ID: {plan_id}\n" if plan_id else ""
                    
                    discord_notifier.send_system_alert(
                        "Intelligent Exits Auto-Enabled",
                        f"Ticket: {ticket}\n"
                        f"{plan_id_line}"
                        f"Symbol: {symbol}\n"
                        f"Direction: {direction.upper()}\n"
                        f"Entry: {entry_price:.5f}\n\n"
                        f"📊 Auto-Management Active:\n"
                        f"• 🎯 Breakeven: {breakeven_price:.5f} (at {advanced_breakeven_pct:.0f}% to TP)\n"
                        f"• 💰 Partial: {partial_price:.5f} (at {advanced_partial_pct:.0f}% to TP)\n"
                        f"• 🔬 Hybrid ATR+VIX: {'ON' if settings.INTELLIGENT_EXITS_USE_HYBRID_STOPS else 'OFF'}\n"
                        f"• 📈 ATR Trailing: {'ON' if settings.INTELLIGENT_EXITS_TRAILING_ENABLED else 'OFF'}"
                        f"{advanced_message}\n\n"
                        f"Your position is on autopilot! 🚀"
                )
                
                logger.info(f"✅ Auto-enabled Advanced-enhanced intelligent exits for ticket {ticket} ({symbol})")
                
            except Exception as e:
                logger.error(f"Failed to auto-enable intelligent exits for ticket {ticket}: {e}")
        
        # Clean up tracked positions that are no longer open
        open_tickets = {p.ticket for p in positions}
        closed_tickets = tracked_positions - open_tickets
        if closed_tickets:
            tracked_positions.difference_update(closed_tickets)
            logger.debug(f"Removed {len(closed_tickets)} closed positions from tracking")
    
    except Exception as e:
        logger.error(f"Error in auto-enable intelligent exits: {e}")


async def check_closed_trades_async():
    """Check for manually closed trades and log them to database (NEW)"""
    global get_close_logger
    if not get_close_logger:
        return
    
    try:
        import MetaTrader5 as mt5
        
        # Initialize MT5
        if not mt5.initialize():
            return
        
        # Get close logger instance
        close_logger = get_close_logger()
        
        # Get current MT5 positions
        positions = mt5.positions_get()
        current_tickets = {pos.ticket for pos in positions} if positions else set()
        
        # Sync tracked tickets
        close_logger.sync_tracked_tickets(current_tickets)
        
        # Check for closes
        closed_trades = close_logger.check_for_closed_trades()
        
        if closed_trades:
            logger.info(f"📊 Detected and logged {len(closed_trades)} closed trades")
            
            # Send Telegram notifications for closed trades
            for trade in closed_trades:
                try:
                    close_reason = trade['close_reason']
                    profit = trade['profit']
                    
                    # Determine emoji based on profit
                    if profit > 0:
                        emoji = "💰"
                        result = "Profit"
                    elif profit < 0:
                        emoji = "📉"
                        result = "Loss"
                    else:
                        emoji = "⚪"
                        result = "Breakeven"
                    
                    # Format close reason
                    if close_reason == "stop_loss":
                        reason_text = "🛑 Stop Loss Hit"
                    elif close_reason == "take_profit":
                        reason_text = "🎯 Take Profit Hit"
                    elif close_reason.startswith("profit_protect"):
                        reason_text = f"💰 Profit Protected ({close_reason})"
                    elif close_reason.startswith("loss_cut"):
                        reason_text = f"🔪 Loss Cut ({close_reason})"
                    elif close_reason == "manual":
                        reason_text = "✋ Manual Close"
                    else:
                        reason_text = f"📊 {close_reason.replace('_', ' ').title()}"
                    
                    # Get plan_id if this is an auto-executed trade
                    plan_id = get_plan_id_from_ticket(trade['ticket'])
                    plan_id_line = f"📊 Plan ID: {plan_id}\n" if plan_id else ""
                    
                    alert_text = (
                        f"{emoji} *Trade Closed - {result}*\n\n"
                        f"Ticket: {trade['ticket']}\n"
                        f"{plan_id_line}"
                        f"Symbol: {trade['symbol']}\n"
                        f"Close Price: {trade['close_price']:.5f}\n"
                        f"Profit/Loss: ${profit:.2f}\n"
                        f"Reason: {reason_text}\n\n"
                        f"📊 Logged to database"
                    )
                    
                    if DISCORD_ENABLED:
                        discord_notifier.send_system_alert("Trade Alert", alert_text)
                
                except Exception as e:
                    logger.error(f"Error sending close notification for {trade['ticket']}: {e}")
    
    except Exception as e:
        logger.error(f"Error checking closed trades: {e}", exc_info=True)


async def check_loss_cuts_async():
    """Check for loss cut signals using enhanced automated loss-cutting system with Binance enrichment"""
    global binance_service, order_flow_service, loss_cutter_instance
    if not binance_service or not order_flow_service or not loss_cutter_instance:
        return
    
    try:
        import asyncio
        import MetaTrader5 as mt5
        import pandas as pd
        from infra.loss_cutter import LossCutter
        from infra.mt5_service import MT5Service
        from infra.indicator_bridge import IndicatorBridge
        from infra.session_analyzer import SessionAnalyzer
        from infra.professional_filters import ProfessionalFilters
        
        # Initialize services
        mt5_service = MT5Service()
        if not mt5_service.connect():
            return
        
        # Use global loss_cutter instance to preserve ProfitProtector cooldown state
        if loss_cutter_instance is None:
            loss_cutter_instance = LossCutter(mt5_service)
            logger.info("✅ LossCutter instance created (will persist for cooldown tracking)")
        
        loss_cutter = loss_cutter_instance
        indicator_bridge = IndicatorBridge(None)
        session_analyzer = SessionAnalyzer()
        professional_filters = ProfessionalFilters()
        
        # Initialize Binance enrichment if available
        binance_enrichment = None
        if binance_service and order_flow_service:
            from infra.binance_enrichment import BinanceEnrichment
            binance_enrichment = BinanceEnrichment(binance_service, order_flow_service)
        
        # Get open positions
        positions = mt5.positions_get()
        if not positions:
            return
            
        for position in positions:
            try:
                # Get market features for the position
                symbol = position.symbol
                direction = "buy" if position.type == mt5.ORDER_TYPE_BUY else "sell"
                
                # Get multi-timeframe data
                bars = indicator_bridge.get_multi(symbol)
                if not bars or 'M5' not in bars:
                    continue
                    
                # Extract features from M5 timeframe
                m5_data = bars['M5']
                
                # Enrich with Binance data (37 fields) if available
                if binance_enrichment:
                    m5_data = binance_enrichment.enrich_timeframe(symbol, m5_data, 'M5')
                    
                # Calculate technical indicators (IndicatorBridge returns scalars, not lists)
                features = {
                    'rsi': float(m5_data.get('rsi', 50)),
                    'adx': float(m5_data.get('adx', 20)),
                    'macd_hist': float(m5_data.get('macd_histogram', 0)),
                    'atr': float(m5_data.get('atr14', 10)),
                    'close': float(position.price_current),
                    'ema20': float(m5_data.get('ema20', position.price_current)),
                    'ema50': float(m5_data.get('ema50', position.price_current)),
                    'ema200': float(m5_data.get('ema200', position.price_current)),
                    'sar': float(m5_data.get('sar', position.price_current)),
                    'vwap': float(m5_data.get('vwap', position.price_current)),
                    'bb_upper': float(m5_data.get('bb_upper', position.price_current)),
                    'bb_lower': float(m5_data.get('bb_lower', position.price_current)),
                    'volume': float(m5_data.get('volume_sma', 1000)),
                    'volume_ma': float(m5_data.get('volume_sma', 1000)),
                    # Add Binance enrichment fields for enhanced loss cutting
                    'binance_momentum': m5_data.get('momentum_quality', 'UNKNOWN'),
                    'binance_volatility': m5_data.get('volatility_state', 'UNKNOWN'),
                    'binance_structure': m5_data.get('price_structure', 'UNKNOWN'),
                    'order_flow_signal': m5_data.get('order_flow_signal', 'NEUTRAL'),
                    'whale_count': m5_data.get('whale_count', 0),
                    'liquidity_voids': m5_data.get('liquidity_voids', 0),
                }
                
                # Add previous values for momentum analysis (use current as prev for now)
                # TODO: Store historical values for proper momentum tracking
                features['rsi_prev'] = features['rsi']
                features['adx_prev'] = features['adx']
                features['macd_hist_prev'] = features['macd_hist']
                    
                # Get current session and volatility
                session = session_analyzer.get_current_session()
                session_volatility = "medium"  # Default, could be enhanced
                
                # Create bars DataFrame for wick analysis
                bars_df = None
                if 'opens' in m5_data and 'highs' in m5_data and 'lows' in m5_data and 'closes' in m5_data:
                    # IndicatorBridge returns lists with keys 'opens', 'highs', 'lows', 'closes'
                    bars_df = pd.DataFrame({
                        'open': m5_data['opens'],
                        'high': m5_data['highs'],
                        'low': m5_data['lows'],
                        'close': m5_data['closes'],
                        'tick_volume': m5_data.get('volumes', [1000] * len(m5_data['opens']))
                    })
                
                # Check professional filters for early exit
                early_exit_check = professional_filters.check_for_early_exit(
                    position=position,
                    features=features,
                    bars=bars_df
                )
                
                # Prepare order flow data for profit protection
                order_flow_data = {
                    'whale_count': features.get('whale_count', 0),
                    'order_flow_signal': features.get('order_flow_signal', 'NEUTRAL'),
                    'liquidity_voids': features.get('liquidity_voids', 0),
                }
                
                # Check for loss cut decision (includes profit protection for profitable trades)
                decision = loss_cutter.should_cut_loss(
                    position=position,
                    features=features,
                    bars=bars_df,
                    session_volatility=session_volatility,
                    order_flow=order_flow_data
                )
                
                # Override with early exit if structure collapsed
                if not early_exit_check.passed and early_exit_check.action == "exit_early":
                    decision.should_cut = True
                    decision.reason = f"Early Exit AI: {early_exit_check.reason}"
                    decision.urgency = "immediate"
                    decision.confidence = early_exit_check.confidence
                
                # Handle tightening (profit protection or momentum relapse)
                if decision.urgency == "tighten_first" and decision.new_sl:
                    # Tighten stop loss to structure/breakeven
                    try:
                        result = mt5_service.modify_position_sl_tp(
                            ticket=position.ticket,
                            symbol=position.symbol,
                            sl=decision.new_sl,
                            tp=position.tp if position.tp > 0 else None
                        )
                        
                        if result and result.get('ok'):
                            # Escape special Markdown characters in reason
                            safe_reason = escape_markdown(decision.reason)
                            
                            if DISCORD_ENABLED:
                                discord_notifier.send_system_alert(
                                    "Stop Loss Tightened",
                                     f"Ticket: {position.ticket}\n"
                                     f"Symbol: {position.symbol}\n"
                                     f"Reason: {safe_reason}\n"
                                     f"New SL: {decision.new_sl:.5f}\n"
                                     f"Confidence: {decision.confidence:.1%}\n\n"
                                    f"💡 Position protected - monitoring continues."
                            )
                            logger.info(f"🛡️ SL tightened for ticket {position.ticket}: {decision.reason}")
                        else:
                            logger.warning(f"⚠️ Failed to tighten SL for ticket {position.ticket}")
                    except Exception as e:
                        logger.error(f"Error tightening SL for ticket {position.ticket}: {e}")
                
                elif decision.should_cut and decision.urgency == "immediate":
                    # Execute loss cut (or profit protection exit)
                    success, msg = loss_cutter.execute_loss_cut(
                        position=position,
                        reason=decision.reason
                    )
                    
                    if success:
                        # Determine if it's profit protection or loss cut
                        is_profit_protect = "profit_protect" in decision.reason.lower()
                        
                        # Enhanced notification with Binance data
                        safe_reason = escape_markdown(decision.reason)
                        safe_msg = escape_markdown(msg)
                        
                        if is_profit_protect:
                            alert_text = (
                                f"💰 *Profit Protected - Position Closed*\n\n"
                                f"Ticket: {position.ticket}\n"
                                f"Symbol: {position.symbol}\n"
                                f"Reason: {safe_reason}\n"
                                f"Confidence: {decision.confidence:.1%}\n"
                                f"Status: ✅ {safe_msg}\n"
                            )
                        else:
                            alert_text = (
                                f"🔪 *Loss Cut Executed*\n\n"
                                f"Ticket: {position.ticket}\n"
                                f"Symbol: {position.symbol}\n"
                                f"Reason: {safe_reason}\n"
                                f"Confidence: {decision.confidence:.1%}\n"
                                f"Status: ✅ {safe_msg}\n"
                            )
                        
                        # Add Binance enrichment context if available
                        if binance_enrichment and features.get('binance_momentum') != 'UNKNOWN':
                            alert_text += (
                                f"\n📊 *Market Context:*\n"
                                f"  Structure: {features.get('binance_structure', 'N/A')}\n"
                                f"  Volatility: {features.get('binance_volatility', 'N/A')}\n"
                                f"  Momentum: {features.get('binance_momentum', 'N/A')}\n"
                                f"  Order Flow: {features.get('order_flow_signal', 'NEUTRAL')}\n"
                            )
                            
                            if features.get('whale_count', 0) > 0:
                                alert_text += f"  🐋 Whales: {features['whale_count']} detected\n"
                            
                            if features.get('liquidity_voids', 0) > 0:
                                alert_text += f"  ⚠️ Liquidity Voids: {features['liquidity_voids']}\n"
                        
                        if DISCORD_ENABLED:
                            discord_notifier.send_system_alert("Trade Alert", alert_text)
                        logger.info(f"✅ Loss cut executed for ticket {position.ticket}: {decision.reason}")
                    else:
                        # Determine if it's a broker hours issue or real failure
                        is_broker_hours = "broker trading hours" in msg.lower() or "session deals" in msg.lower()
                        
                        safe_reason = escape_markdown(decision.reason)
                        safe_msg = escape_markdown(msg)
                        
                        if is_broker_hours:
                            # Broker hours - less alarming message
                            if DISCORD_ENABLED:
                                discord_notifier.send_system_alert(
                                    "Loss Cut Delayed",
                                     f"Ticket: {position.ticket}\n"
                                     f"Symbol: {position.symbol}\n"
                                     f"Reason: {safe_reason}\n"
                                     f"Status: Broker trading hours (session deals disabled)\n\n"
                                     f"💡 Will retry automatically when broker opens.\n"
                                    f"Position is protected by stop loss."
                            )
                            logger.warning(f"⏸️ Loss cut delayed for ticket {position.ticket}: Broker trading hours")
                        else:
                            # Real failure - send alert
                            if DISCORD_ENABLED:
                                discord_notifier.send_system_alert(
                                    "Loss Cut Failed",
                                     f"Ticket: {position.ticket}\n"
                                     f"Symbol: {position.symbol}\n"
                                     f"Reason: {safe_reason}\n"
                                     f"Error: {safe_msg}\n\n"
                                    f"⚠️ Manual intervention may be required."
                            )
                            logger.error(f"❌ Loss cut failed for ticket {position.ticket}: {msg}")
                        
                elif decision.urgency == "tighten_first":
                    # Tighten stop loss first
                    try:
                        result = mt5_service.modify_position_sl_tp(
                            ticket=position.ticket,
                            symbol=position.symbol,
                            sl=decision.new_sl
                        )
                        
                        if result and result.get('ok'):
                            safe_reason = escape_markdown(decision.reason)
                            
                            # Discord notification (replaced Telegram)
                            if DISCORD_ENABLED:
                                discord_notifier.send_system_alert(
                                    "Stop Loss Tightened",
                                    f"Ticket: {position.ticket}\n"
                                    f"Symbol: {position.symbol}\n"
                                    f"New SL: {decision.new_sl:.5f}\n"
                                    f"Reason: {safe_reason}"
                                )
                            logger.info(f"🎯 SL tightened for ticket {position.ticket} to {decision.new_sl}")
                    except Exception as e:
                        logger.error(f"Failed to tighten SL for {position.ticket}: {e}")
                        
            except Exception as e:
                logger.error(f"Error processing position {position.ticket}: {e}")
    
    except Exception as e:
        logger.error(f"Error checking loss cuts: {e}")


async def check_trade_setups_async():
    """Check for trade setup conditions and send alerts when met"""
    # Check for trade setup conditions
    
    try:
        from infra.trade_setup_watcher import TradeSetupWatcher
        from infra.mt5_service import MT5Service
        from infra.indicator_bridge import IndicatorBridge
        from infra.session_analyzer import SessionAnalyzer
        from config import settings
        
        # Initialize services
        config = settings
        if not config.SETUP_WATCHER_ENABLE:
            return
            
        mt5_service = MT5Service()
        if not mt5_service.connect():
            return
            
        setup_watcher = TradeSetupWatcher(config)
        indicator_bridge = IndicatorBridge(None)
        session_analyzer = SessionAnalyzer()
        
        # Get symbols to monitor (you can customize this list)
        # Note: Use correct symbol names with 'c' suffix if required by your broker
        symbols_to_monitor = ['XAUUSDc', 'BTCUSDc', 'EURUSDc', 'GBPUSDc', 'USDJPYc']
        
        for symbol in symbols_to_monitor:
            try:
                # Check for BUY setup
                buy_alert = await setup_watcher.watch_setup(
                    symbol=symbol,
                    action='BUY',
                    min_confidence=config.SETUP_WATCHER_MIN_CONFIDENCE
                )
                
                if buy_alert:
                    # Send BUY alert
                    if DISCORD_ENABLED:
                        discord_notifier.send_system_alert("BUY Setup Alert", buy_alert.message)
                    logger.info(f"🎯 BUY setup alert sent for {symbol}: {buy_alert.confidence}% confidence")
                
                # Check for SELL setup
                sell_alert = await setup_watcher.watch_setup(
                    symbol=symbol,
                    action='SELL',
                    min_confidence=config.SETUP_WATCHER_MIN_CONFIDENCE
                )
                
                if sell_alert:
                    # Send SELL alert
                    if DISCORD_ENABLED:
                        discord_notifier.send_system_alert("SELL Setup Alert", sell_alert.message)
                    logger.info(f"🎯 SELL setup alert sent for {symbol}: {sell_alert.confidence}% confidence")
                    
            except Exception as e:
                logger.error(f"Error checking setup for {symbol}: {e}")
    
    except Exception as e:
        logger.error(f"Error checking trade setups: {e}")


async def update_recommendation_outcomes():
    """
    Background task: Check for closed trades and update recommendation outcomes
    
    This function:
    1. Gets pending recommendations (executed but no outcome)
    2. Checks MT5 history for closed deals matching those tickets
    3. Updates the recommendation database with outcomes
    """
    try:
        from infra.recommendation_tracker import RecommendationTracker
        import MetaTrader5 as mt5
        from datetime import datetime, timedelta
        
        tracker = RecommendationTracker()
        
        # Get pending recommendations
        pending = tracker.get_pending_recommendations()
        if not pending:
            return
        
        logger.info(f"Checking outcomes for {len(pending)} pending recommendations")
        
        # Connect to MT5
        if not mt5.initialize():
            logger.error("Failed to initialize MT5 for outcome tracking")
            return
        
        # Check each pending recommendation
        for rec in pending:
            ticket = rec.get("mt5_ticket")
            if not ticket:
                continue
            
            # Check if this position is still open
            position = mt5.positions_get(ticket=ticket)
            if position and len(position) > 0:
                # Still open, skip
                continue
            
            # Position closed, check history
            # Get deals from the last 30 days
            now = datetime.now()
            from_date = now - timedelta(days=30)
            
            # Get history deals for this ticket
            deals = mt5.history_deals_get(from_date, now, position=ticket)
            
            if not deals or len(deals) == 0:
                # No deals found, might be a pending order that was cancelled
                # Check orders history
                orders = mt5.history_orders_get(from_date, now, position=ticket)
                if orders and len(orders) > 0:
                    order = orders[-1]
                    # Check if order was cancelled
                    if order.state == mt5.ORDER_STATE_CANCELED:
                        tracker.update_outcome(
                            mt5_ticket=ticket,
                            outcome="cancelled",
                            exit_time=datetime.fromtimestamp(order.time_done)
                        )
                        logger.info(f"Marked ticket {ticket} as cancelled")
                continue
            
            # Find the exit deal (entry=1 means OUT)
            exit_deal = None
            for deal in deals:
                if deal.entry == 1:  # OUT
                    exit_deal = deal
                    break
            
            if not exit_deal:
                continue
            
            # Calculate outcome
            profit = exit_deal.profit
            outcome = "win" if profit > 0 else ("loss" if profit < 0 else "breakeven")
            
            # Update recommendation
            tracker.update_outcome(
                mt5_ticket=ticket,
                outcome=outcome,
                exit_price=exit_deal.price,
                exit_time=datetime.fromtimestamp(exit_deal.time),
                profit_loss=profit
            )
            
            logger.info(f"✅ Updated outcome for ticket {ticket}: {outcome.upper()}, P/L: ${profit:.2f}")
        
        mt5.shutdown()
        
    except Exception as e:
        logger.error(f"Error updating recommendation outcomes: {e}", exc_info=True)


async def check_positions():
    """Background task: Check open positions and trail stops"""
    # Check open positions and trail stops
    
    try:
        # Update recommendation outcomes for closed trades
        try:
            await update_recommendation_outcomes()
        except Exception as e:
            logger.debug(f"Error updating recommendation outcomes: {e}", exc_info=True)
        
        # Auto-enable intelligent exits for new positions (if enabled in config)
        try:
            await auto_enable_intelligent_exits_async()
        except Exception as e:
            logger.debug(f"Error auto-enabling intelligent exits: {e}", exc_info=True)
        
        # Auto-enable DTMS protection for new positions
        try:
            await auto_enable_dtms_protection_async()
        except Exception as e:
            logger.debug(f"Error auto-enabling DTMS protection: {e}", exc_info=True)
        
        # Check trailing stops first
        try:
            await check_trailing_stops_async()
        except Exception as e:
            logger.debug(f"Error checking trailing stops: {e}", exc_info=True)
        
        # Check intelligent exits (breakeven, partial profits, VIX adjustments)
        try:
            await check_intelligent_exits_async()
        except Exception as e:
            logger.debug(f"Error checking intelligent exits: {e}", exc_info=True)
        
        # Check exit signals for profit protection
        try:
            await check_exit_signals_async()
        except Exception as e:
            logger.debug(f"Error checking exit signals: {e}", exc_info=True)
        
        # Check loss cut signals for losing positions (DISABLED - Use only intelligent exits)
        # await check_loss_cuts_async(app)  # DISABLED to prevent premature closures
        
        # Get open positions for P&L alerts
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Get open positions
                response = await client.get("http://localhost:8000/api/v1/positions")
                if response.status_code != 200:
                    logger.debug(f"Failed to get positions: HTTP {response.status_code}")
                    return
                
                positions = response.json().get("positions", [])
                if not positions:
                    return
                
                # Check each position for trailing stop updates
                for pos in positions:
                    ticket = pos.get("ticket")
                    symbol = pos.get("symbol")
                    profit = pos.get("profit", 0)
                    pnl_pct = pos.get("pnl_percent", 0)
                    
                    # Alert on significant P&L changes
                    if abs(pnl_pct) >= 2.0:  # 2% or more
                        emoji = "📈" if profit > 0 else "📉"
                        if DISCORD_ENABLED:
                            try:
                                discord_notifier.send_system_alert(
                                    "Position Update",
                                    f"{emoji} Ticket: {ticket}\n"
                                    f"Symbol: {symbol}\n"
                                    f"P&L: ${profit:.2f} ({pnl_pct:+.1f}%)"
                                )
                            except Exception as e:
                                logger.debug(f"Error sending Discord alert: {e}", exc_info=True)
        except Exception as e:
            logger.debug(f"Error getting positions for alerts: {e}", exc_info=True)
    
    except Exception as e:
        # Catch-all for any unexpected errors
        logger.error(f"Error checking positions: {e}", exc_info=True)


async def scan_for_signals():
    """Background task: Scan markets for trade signals with Binance enrichment"""
    global binance_service, order_flow_service
    if not binance_service or not order_flow_service:
        return
    
    try:
        # Import settings to get scanner configuration
        from config import settings as cfg_settings
        
        # Get symbols from config/settings.py (defaults to XAUUSDc, BTCUSDc, EURUSDc, USDJPYc)
        try:
            import importlib
            bot_settings = importlib.import_module("config.settings")
            symbols = getattr(bot_settings, "SIGNAL_SCANNER_SYMBOLS", ["XAUUSDc", "BTCUSDc", "EURUSDc", "USDJPYc"])
            min_confidence = getattr(bot_settings, "SIGNAL_SCANNER_MIN_CONFIDENCE", 75)
        except Exception as e:
            logger.warning(f"Could not load SIGNAL_SCANNER_SYMBOLS from config/settings.py: {e}")
            symbols = ["XAUUSDc", "BTCUSDc", "EURUSDc", "USDJPYc"]
            min_confidence = 75
        
        logger.debug(f"Signal scanner checking: {symbols} (min confidence: {min_confidence}%)")
        
        # Use direct analysis with Binance enrichment if available
        if binance_service and order_flow_service:
            from infra.mt5_service import MT5Service
            from infra.indicator_bridge import IndicatorBridge
            from infra.binance_enrichment import BinanceEnrichment
            from decision_engine import decide_trade
            
            mt5_svc = MT5Service()
            if not mt5_svc.connect():
                logger.warning("MT5 connection failed in signal scanner")
                return
            
            bridge = IndicatorBridge()
            enrichment = BinanceEnrichment(binance_service, order_flow_service)
            
            for symbol in symbols:
                try:
                    # Get MT5 data
                    multi = bridge.get_multi(symbol)
                    if not multi or 'M5' not in multi:
                        continue
                    
                    # Enrich with Binance data (37 fields)
                    m5_enriched = enrichment.enrich_timeframe(symbol, multi.get('M5', {}), 'M5')
                    m15_enriched = enrichment.enrich_timeframe(symbol, multi.get('M15', {}), 'M15')
                    m30_enriched = enrichment.enrich_timeframe(symbol, multi.get('M30', {}), 'M30')
                    h1_enriched = enrichment.enrich_timeframe(symbol, multi.get('H1', {}), 'H1')
                    
                    # Run decision engine
                    rec = decide_trade(symbol, m5_enriched, m15_enriched, m30_enriched, h1_enriched)
                    
                    direction = rec.get("direction", "HOLD")
                    confidence = rec.get("confidence", 0)
                    
                    # Only alert on high-confidence signals
                    if direction != "HOLD" and confidence >= min_confidence:
                        emoji = "🟢" if direction == "BUY" else "🔴"
                        entry = rec.get("entry", 0)
                        sl = rec.get("sl", 0)
                        tp = rec.get("tp", 0)
                        reason = rec.get("reasoning", "Technical setup")
                        
                        # Extract key Binance enrichment fields
                        price_structure = m5_enriched.get("price_structure", "N/A")
                        volatility_state = m5_enriched.get("volatility_state", "N/A")
                        momentum_quality = m5_enriched.get("momentum_quality", "N/A")
                        order_flow_signal = m5_enriched.get("order_flow_signal", "NEUTRAL")
                        whale_count = m5_enriched.get("whale_count", 0)
                        
                        logger.info(f"📡 Signal found: {direction} {symbol} @ {confidence}% confidence")
                        logger.info(f"   Binance: {price_structure}, {volatility_state}, {momentum_quality}, Whales: {whale_count}")
                        
                        # Enhanced alert with Binance data
                        alert_text = (
                            f"🔔 *Signal Alert!*\n\n"
                            f"{emoji} **{direction} {symbol}**\n"
                            f"📊 Entry: ${entry:.2f}\n"
                            f"🛑 SL: ${sl:.2f}\n"
                            f"🎯 TP: ${tp:.2f}\n"
                            f"💡 {reason}\n"
                            f"📈 Confidence: {confidence}%\n\n"
                            f"🎯 *Setup Quality:*\n"
                            f"  Structure: {price_structure}\n"
                            f"  Volatility: {volatility_state}\n"
                            f"  Momentum: {momentum_quality}\n"
                            f"  Order Flow: {order_flow_signal}\n"
                        )
                        
                        if whale_count > 0:
                            alert_text += f"  🐋 Whales: {whale_count} detected\n"
                        
                        if DISCORD_ENABLED:
                            discord_notifier.send_system_alert("Trade Alert", alert_text)
                        
                except Exception as e:
                    logger.error(f"Error scanning {symbol}: {e}")
                    continue
        else:
            # Fallback to API endpoint if Binance not available
            async with httpx.AsyncClient(timeout=15.0) as client:
                for symbol in symbols:
                    # Get AI analysis
                    response = await client.get(f"http://localhost:8000/ai/analysis/{symbol}")
                    if response.status_code != 200:
                        logger.debug(f"Signal scanner: {symbol} returned {response.status_code}")
                        continue
                    
                    data = response.json()
                    tech = data.get("technical_analysis", {})
                    rec = tech.get("trade_recommendation", {})
                    
                    direction = rec.get("direction", "HOLD")
                    confidence = rec.get("confidence", 0)
                    
                    # Only alert on high-confidence signals
                    if direction != "HOLD" and confidence >= min_confidence:
                        emoji = "🟢" if direction == "BUY" else "🔴"
                        entry = rec.get("entry_price", 0)
                        sl = rec.get("stop_loss", 0)
                        tp = rec.get("take_profit", 0)
                        reason = rec.get("reasoning", "Technical setup")
                        
                        logger.info(f"📡 Signal found: {direction} {symbol} @ {confidence}% confidence")
                        
                        if DISCORD_ENABLED:
                            discord_notifier.send_system_alert(
                                "Signal Alert",
                                f"{emoji} {direction} {symbol}\n"
                                f"📊 Entry: ${entry:.2f}\n"
                                f"🛑 SL: ${sl:.2f}\n"
                                f"🎯 TP: ${tp:.2f}\n"
                                f"💡 {reason}\n"
                                f"📈 Confidence: {confidence}%"
                            )
    
    except Exception as e:
        logger.error(f"Error scanning for signals: {e}")


async def check_custom_alerts():
    """Background task: Check custom alerts and send notifications"""
    try:
        # Check if alert monitor is available
        if not AlertMonitor:
            return
        
        # Check all alerts
        if not alert_monitor:
            return
        triggered = await alert_monitor.check_all_alerts()
        
        if not triggered:
            return
        
        # Send Discord notifications for triggered alerts
        for alert, context in triggered:
            try:
                # Build notification message
                emoji_map = {
                    "structure": "🏗️",
                    "price": "💰",
                    "indicator": "📊",
                    "order_flow": "🌊",
                    "volatility": "📈"
                }
                
                emoji = emoji_map.get(alert.alert_type.value, "🔔")
                
                # Check if one-time alert
                alert_type_text = "🔔 ONE-TIME ALERT" if alert.one_time else "🔄 RECURRING ALERT"
                
                message = (
                    f"{emoji} *Alert Triggered!* {alert_type_text}\n\n"
                    f"🎯 **{alert.description}**\n"
                    f"📊 Symbol: {alert.symbol}\n"
                    f"⏰ Triggered: #{alert.triggered_count}\n\n"
                )
                
                # Add context-specific details
                if context:
                    if "current_price" in context:
                        message += f"💵 Current Price: ${context['current_price']:.2f}\n"
                    if "target_price" in context:
                        message += f"🎯 Target: ${context['target_price']:.2f}\n"
                    if "indicator" in context:
                        message += f"📊 {context['indicator']}: {context['current_value']:.2f}\n"
                    if "structure_type" in context:
                        message += f"🏗️ Pattern: {context['structure_type']}\n"
                    if "timeframe" in context:
                        message += f"⏱️ Timeframe: {context['timeframe']}\n"
                
                # Add auto-removal notice for one-time alerts
                if alert.one_time:
                    message += f"\n🗑️ This alert has been automatically removed."
                
                # Send Discord notification
                if DISCORD_ENABLED:
                    discord_notifier.send_system_alert("Custom Alert", message)
                else:
                    logger.warning("Discord notifications disabled - alert triggered but not sent")
                
                logger.info(f"✅ Alert notification sent via Discord: {alert.description}")
                
            except Exception as e:
                logger.error(f"Error sending alert notification: {e}")
        
    except Exception as e:
        logger.error(f"Error checking custom alerts: {e}")

async def check_circuit_breaker():
    """Background task: Check circuit breaker status"""
    # Check circuit breaker status
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8000/risk/metrics")
            if response.status_code != 200:
                return
            
            data = response.json()
            daily_loss = data.get("daily_loss_pct", 0)
            is_paused = data.get("circuit_breaker_active", False)
            
            # Alert if approaching danger zone (80% of max loss)
            if abs(daily_loss) >= 2.4:  # 80% of 3% max
                # Discord notification (replaced Telegram)
                if DISCORD_ENABLED:
                    discord_notifier.send_system_alert(
                        "Risk Warning",
                        f"⚠️ Daily Loss: {daily_loss:.1f}%\n"
                        f"Approaching circuit breaker limit (3%)\n"
                        f"Status: {'🔴 PAUSED' if is_paused else '🟡 Active'}"
                    )
    
    except Exception as e:
        logger.error(f"Error checking circuit breaker: {e}", exc_info=True)


# ===== COMMAND HANDLERS =====
# Telegram command handlers removed - using Discord instead
# All command functionality is now handled through Discord notifications
# All Telegram command handlers removed - using Discord instead

# All Telegram command handlers removed - using Discord instead

def main():
    """Start the bot"""
    global scheduler, trade_monitor, exit_monitor, intelligent_exit_manager, chatgpt_logger, binance_service, order_flow_service, auto_execution_system, dtms_engine, universal_sl_tp_manager
    
    # Setup file logging FIRST (before any other operations)
    setup_file_logging()
    
    # Check Discord webhook URL
    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not discord_webhook:
        logger.warning("DISCORD_WEBHOOK_URL not found in .env file - Discord notifications will be disabled")
    else:
        logger.info("✅ Discord webhook URL found - notifications enabled")
    
    # Get OpenAI key (optional - can be set via /setgptkey)
    openai_key = os.getenv("OPENAI_API_KEY")
    
    logger.info("🤖 Starting ChatGPT Discord Bot with Background Monitoring...")

    # Initialize staged activation (optional, non-blocking)
    try:
        if StagedActivationConfig and start_staged_activation:
            sa_config = StagedActivationConfig()
            start_staged_activation(sa_config)
            logger.info("✅ Staged activation system started (initial 50% sizing)")
    except Exception as e:
        logger.warning(f"⚠️ Could not start staged activation system: {e}")
    
    # Fetch latest news events at startup
    try:
        from infra.news_service import get_news_service
        news_service = get_news_service()
        if news_service:
            # Skip async fetch at startup - will be handled by scheduler
            logger.info("✅ News service initialized")
    except Exception as e:
        logger.warning(f"⚠️ Could not fetch news events: {e}")
    
    # Initialize monitoring systems
    try:
        # Initialize MT5 service and feature builder first
        from infra.mt5_service import MT5Service
        from infra.feature_builder import FeatureBuilder
        from infra.indicator_bridge import IndicatorBridge
        
        mt5_service = MT5Service()
        if not mt5_service.connect():
            logger.warning("⚠️ MT5 connection failed - some features may be limited")
        
        # Initialize indicator bridge for feature builder
        indicator_bridge = IndicatorBridge()
        feature_builder = FeatureBuilder(mt5_service, indicator_bridge)
        
        # Initialize trade monitor with required arguments
        from infra.trade_monitor import TradeMonitor
        trade_monitor = TradeMonitor(mt5_service, feature_builder)
        logger.info("✅ Trade monitor initialized")
        
        # Initialize exit monitor with required arguments
        from infra.exit_monitor import ExitMonitor
        exit_monitor = ExitMonitor(mt5_service, feature_builder)
        logger.info("✅ Exit monitor initialized")
        
        # Initialize ChatGPT logger
        from infra.chatgpt_logger import ChatGPTLogger
        chatgpt_logger = ChatGPTLogger()
        logger.info("✅ ChatGPT logger initialized")
        
        # Initialize Binance service
        from infra.binance_service import BinanceService
        binance_service = BinanceService()
        logger.info("✅ Binance service initialized")
        
        # Initialize and start order flow service for BTCUSD whale detection
        from infra.order_flow_service import OrderFlowService
        global order_flow_service
        global order_flow_loop, order_flow_thread
        
        # Check if service already exists and is running
        if order_flow_service is not None and hasattr(order_flow_service, 'running') and order_flow_service.running:
            logger.info("✅ Order Flow Service already running - skipping reinitialization")
        else:
            # Stop existing service if it exists but isn't running properly
            if order_flow_service is not None:
                logger.info("⚠️ Existing Order Flow Service found but not running - stopping before reinitialization")
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(order_flow_service.stop())
                    else:
                        loop.run_until_complete(order_flow_service.stop())
                except Exception as e:
                    logger.warning(f"   Error stopping existing service: {e}")
                order_flow_service = None
            
            try:
                order_flow_service = OrderFlowService()
            except Exception as e:
                logger.warning(f"⚠️ Order Flow Service initialization failed: {e}", exc_info=True)
                logger.warning("   Continuing without order flow analysis...")
                order_flow_service = None

            if order_flow_service is not None:
                # Register in global registry IMMEDIATELY (before async start) for AutoExecutionSystem access
                # This ensures the service is available even if async start fails
                try:
                    from desktop_agent import registry
                    registry.order_flow_service = order_flow_service
                    logger.info("   → Order Flow Service registered in global registry (before start)")
                    # Verify registration succeeded
                    if hasattr(registry, 'order_flow_service') and registry.order_flow_service == order_flow_service:
                        logger.info("   ✅ Registration verified - service is accessible from registry")
                    else:
                        logger.error("   ❌ Registration failed - service not found in registry after assignment")
                except ImportError as e:
                    logger.error(f"❌ Could not import desktop_agent.registry: {e}")
                    logger.error("   AutoExecutionSystem will not be able to access order flow metrics")
                    logger.error("   This is a critical error - order flow plans will not execute")
                except Exception as e:
                    logger.error(f"❌ Could not register Order Flow Service in registry: {e}", exc_info=True)
                    logger.error("   AutoExecutionSystem will not be able to access order flow metrics")
                    logger.error("   This is a critical error - order flow plans will not execute")

                # Start order flow service on a dedicated persistent event loop.
                # IMPORTANT: Previously we created a new event loop, ran start(), then closed it.
                # That immediately destroyed the background websocket tasks ("Task was destroyed but it is pending!")
                import asyncio
                import threading
                import atexit
                import concurrent.futures

                async def start_order_flow():
                    try:
                        # ⭐ Only BTCUSD supported - Binance order book depth streams only work for crypto pairs
                        order_flow_symbols = ["btcusdt"]  # BTCUSD only
                        await order_flow_service.start(order_flow_symbols, background=True)
                        logger.info("✅ Order Flow Service started")
                        logger.info("   📊 Order book depth: Active (20 levels @ 100ms)")
                        logger.info("   🐋 Whale detection: Active ($50k+ orders)")
                        logger.info(f"   ⚠️ Supported symbols: BTCUSD only (crypto pairs only)")
                        
                        # Re-register in global registry after start (ensure it's still there)
                        try:
                            from desktop_agent import registry
                            registry.order_flow_service = order_flow_service
                            logger.info("   → Order Flow Service re-registered in global registry (after start)")
                            # Verify registration and running status
                            if hasattr(registry, 'order_flow_service') and registry.order_flow_service == order_flow_service:
                                if hasattr(order_flow_service, 'running') and order_flow_service.running:
                                    logger.info("   ✅ Service is registered and running - AutoExecutionSystem can access it")
                                else:
                                    logger.warning("   ⚠️ Service is registered but not marked as running")
                            else:
                                logger.error("   ❌ Re-registration failed - service not found in registry")
                        except ImportError as e:
                            logger.error(f"❌ Could not import desktop_agent.registry for re-registration: {e}")
                        except Exception as e:
                            logger.error(f"❌ Could not re-register Order Flow Service in registry: {e}", exc_info=True)
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to start Order Flow Service: {e}")
                        logger.warning("   (This is normal if Binance service is not running)")
                        # Set running to False if start failed
                        order_flow_service.running = False
            
            def _run_order_flow_loop(loop: asyncio.AbstractEventLoop):
                asyncio.set_event_loop(loop)
                loop.run_forever()

            # Ensure the order-flow loop thread exists and stays alive
            if order_flow_loop is None or order_flow_loop.is_closed() or order_flow_thread is None or not order_flow_thread.is_alive():
                order_flow_loop = asyncio.new_event_loop()
                order_flow_thread = threading.Thread(
                    target=_run_order_flow_loop,
                    args=(order_flow_loop,),
                    name="OrderFlowLoop",
                    daemon=True,
                )
                order_flow_thread.start()

                # Best-effort cleanup on process exit
                def _shutdown_order_flow():
                    try:
                        if order_flow_service is not None and hasattr(order_flow_service, "running") and order_flow_service.running:
                            try:
                                asyncio.run_coroutine_threadsafe(order_flow_service.stop_async(), order_flow_loop).result(timeout=5.0)
                            except Exception:
                                pass
                        if order_flow_loop is not None and not order_flow_loop.is_closed():
                            order_flow_loop.call_soon_threadsafe(order_flow_loop.stop)
                    except Exception:
                        pass

                atexit.register(_shutdown_order_flow)

            # Run the async startup inside the persistent loop thread
            try:
                fut = asyncio.run_coroutine_threadsafe(start_order_flow(), order_flow_loop)
                fut.result(timeout=30.0)
            except concurrent.futures.TimeoutError:
                logger.error("❌ Order Flow Service start timed out (30s) - loop thread may be blocked")
            except Exception as e:
                logger.error(f"❌ Order Flow Service start failed: {e}", exc_info=True)
            
            # Final verification: Ensure service is accessible from both registry and module
            try:
                from desktop_agent import registry
                if hasattr(registry, 'order_flow_service') and registry.order_flow_service == order_flow_service:
                    if hasattr(order_flow_service, 'running') and order_flow_service.running:
                        logger.info("✅ Order Flow Service fully initialized and accessible:")
                        logger.info(f"   - Registry: ✅ Available (symbols: {getattr(order_flow_service, 'symbols', 'unknown')})")
                        logger.info(f"   - Module: ✅ Available (chatgpt_bot.order_flow_service)")
                        logger.info("   - AutoExecutionSystem can now access order flow metrics")
                    else:
                        logger.warning("⚠️ Order Flow Service registered but not running")
                else:
                    logger.error("❌ Order Flow Service not found in registry after initialization")
            except Exception as e:
                logger.error(f"❌ Could not verify Order Flow Service registration: {e}", exc_info=True)
        
        # Initialize auto execution system (optional)
        try:
            # Prefer project root module
            from auto_execution_system import AutoExecutionSystem
            
            # Try to get M1 components if available (for order block plans)
            m1_data_fetcher = None
            m1_analyzer = None
            session_manager = None
            asset_profiles = None
            threshold_manager = None
            
            try:
                from infra.m1_data_fetcher import M1DataFetcher
                from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
                from infra.m1_session_volatility_profile import SessionVolatilityProfile
                from infra.m1_asset_profiles import AssetProfileManager
                from infra.m1_threshold_calibrator import SymbolThresholdManager
                
                # Initialize M1 components
                m1_data_fetcher = M1DataFetcher(data_source=mt5_service, max_candles=200)
                asset_profiles = AssetProfileManager("config/asset_profiles.json")
                session_manager = SessionVolatilityProfile()  # No asset_profiles parameter
                threshold_manager = SymbolThresholdManager("config/threshold_profiles.json")
                
                m1_analyzer = M1MicrostructureAnalyzer(
                    mt5_service=mt5_service,
                    session_manager=session_manager,
                    asset_profiles=asset_profiles,
                    threshold_manager=threshold_manager
                )
                
                logger.info("✅ M1 components initialized for auto execution system")
            except Exception as e:
                import traceback
                logger.error(f"⚠️ M1 components not available for auto execution: {e}")
                logger.debug(f"Traceback: {traceback.format_exc()}")
                # Continue without M1 components - order block plans will be skipped
            
            # Use global variable to ensure it's accessible everywhere
            global auto_execution_system
            auto_execution_system = AutoExecutionSystem(
                mt5_service=mt5_service,
                m1_analyzer=m1_analyzer,
                m1_data_fetcher=m1_data_fetcher,
                session_manager=session_manager,
                asset_profiles=asset_profiles
            )
            
            # Set as global instance in auto_execution_system module so get_auto_execution_system() uses it
            import auto_execution_system as aes_module
            aes_module.auto_execution_system = auto_execution_system
            
            # Verify M1 components are set
            if auto_execution_system.m1_analyzer and auto_execution_system.m1_data_fetcher:
                logger.info("✅ Auto execution system initialized with M1 components")
            else:
                logger.warning(f"⚠️ Auto execution system initialized but M1 components missing: m1_analyzer={auto_execution_system.m1_analyzer}, m1_data_fetcher={auto_execution_system.m1_data_fetcher}")
            
            # Initialize auto-execution outcome tracker (Phase 2: Database storage)
            try:
                from infra.auto_execution_outcome_tracker import AutoExecutionOutcomeTracker
                from chatgpt_auto_execution_integration import get_chatgpt_auto_execution
                
                auto_execution_integration = get_chatgpt_auto_execution()
                outcome_tracker = AutoExecutionOutcomeTracker(auto_execution_integration.auto_system)
                
                # Add background task to scheduler (will be added later when scheduler is initialized)
                global _outcome_tracker
                _outcome_tracker = outcome_tracker
                logger.info("✅ Auto-execution outcome tracker initialized (will start with scheduler)")
            except Exception as e:
                logger.warning(f"⚠️ Auto-execution outcome tracker initialization failed: {e}")
                logger.warning("   → Profit/loss data will still be available via MT5 queries")
        except ImportError:
            try:
                import importlib
                _mod = importlib.import_module("infra.auto_execution_system")
                auto_execution_system = getattr(_mod, "AutoExecutionSystem")()
                # Set global instance
                import auto_execution_system as aes_module
                aes_module.auto_execution_system = auto_execution_system
                logger.info("✅ Auto execution system initialized (infra)")
            except Exception:
                logger.warning("⚠️ Auto execution system not available")
                auto_execution_system = None
        
        # PHASE 5: DTMS initialization removed - using API server instead
        # DTMS is now initialized only in dtms_api_server.py (port 8001)
        # All DTMS operations route through API server
        # Keep dtms_engine = None for backward compatibility
        dtms_engine = None
        logger.info("ℹ️ DTMS initialization skipped - using API server (port 8001) instead")
        
        # OLD CODE (commented out for rollback):
        # try:
        #     # Use dtms_integration to set global _dtms_engine (required for auto_register_dtms)
        #     from dtms_integration import initialize_dtms, start_dtms_monitoring, get_dtms_engine
        #     global dtms_engine
        #     
        #     # Initialize DTMS (sets global _dtms_engine in dtms_integration.py)
        #     dtms_init_success = initialize_dtms(
        #         mt5_service=mt5_service,
        #         binance_service=binance_service,  # Use existing binance_service if available
        #         telegram_service=None,
        #         order_flow_service=order_flow_service  # NEW: Pass OrderFlowService for BTCUSD
        #     )
        #     
        #     if dtms_init_success:
        #         # Start monitoring
        #         start_dtms_monitoring()
        #         # Get the engine instance (from global)
        #         dtms_engine = get_dtms_engine()
        #         if dtms_engine:
        #             logger.info("✅ DTMS engine initialized and monitoring started")
        #         else:
        #             logger.warning("⚠️ DTMS initialized but engine instance unavailable")
        #     else:
        #         logger.warning("⚠️ DTMS initialization failed")
        #         dtms_engine = None
        # except Exception as e:
        #     logger.warning(f"⚠️ DTMS engine not available: {e}")
        #     dtms_engine = None
        
        # Initialize Intelligent Exit Manager (if available)
        try:
            global intelligent_exit_manager
            from infra.intelligent_exit_manager import create_exit_manager, AdvancedProviderWrapper
            
            # Wrap indicator_bridge to provide Advanced features
            advanced_provider = AdvancedProviderWrapper(
                indicator_bridge=indicator_bridge,
                mt5_service=mt5_service
            )
            
            intelligent_exit_manager = create_exit_manager(
                mt5_service,
                binance_service=binance_service,
                order_flow_service=order_flow_service,
                advanced_provider=advanced_provider  # Use wrapper instead of raw indicator_bridge
            )
            logger.info("✅ Intelligent Exit Manager initialized with Advanced Provider")
        except Exception as e:
            intelligent_exit_manager = None
            logger.warning(f"⚠️ Intelligent Exit Manager not available: {e}")
        
        # Initialize custom alerts monitor (if available)
        try:
            global alert_monitor
            if AlertMonitor and CustomAlertManager:
                # Get M1 components if available (for order block detection)
                m1_data_fetcher = None
                m1_analyzer = None
                session_manager = None
                
                try:
                    from infra.m1_data_fetcher import M1DataFetcher
                    from infra.m1_microstructure_analyzer import M1MicrostructureAnalyzer
                    from infra.m1_session_volatility_profile import SessionVolatilityProfile
                    from infra.m1_asset_profiles import AssetProfileManager
                    from infra.m1_threshold_calibrator import SymbolThresholdManager
                    
                    # Initialize M1 components
                    m1_data_fetcher = M1DataFetcher(data_source=mt5_service, max_candles=200)
                    asset_profiles = AssetProfileManager()
                    session_manager = SessionVolatilityProfile()  # No asset_profiles parameter
                    threshold_manager = SymbolThresholdManager("config/threshold_profiles.json")
                    m1_analyzer = M1MicrostructureAnalyzer(
                        mt5_service=mt5_service,
                        session_manager=session_manager,
                        asset_profiles=asset_profiles,
                        threshold_manager=threshold_manager
                    )
                    logger.info("✅ M1 components initialized for alert monitor")
                except Exception as e:
                    import traceback
                    logger.error(f"❌ M1 components not available for alert monitor: {e}")
                    logger.debug(f"Traceback: {traceback.format_exc()}")
                
                alert_monitor = AlertMonitor(
                    CustomAlertManager(), 
                    mt5_service,
                    m1_data_fetcher=m1_data_fetcher,
                    m1_analyzer=m1_analyzer,
                    session_manager=session_manager
                )
                logger.info("✅ Alert monitor initialized with M1 microstructure support")
            else:
                alert_monitor = None
        except Exception as e:
            alert_monitor = None
            logger.warning(f"⚠️ Alert monitor not available: {e}")
        # Start DTMS monitoring automatically when available
        # PHASE 5: DTMS monitoring start removed - using API server instead
        # OLD CODE (commented out for rollback):
        # try:
        #     if dtms_engine:
        #         dtms_engine.start_monitoring()
        # except Exception as e:
        #     logger.warning(f"⚠️ Could not start DTMS monitoring: {e}")
                
    except Exception as e:
        logger.error(f"❌ Failed to initialize monitoring systems: {e}")
        return
    
    # Start Auto Execution System monitoring
    try:
        from integrate_auto_execution import start_auto_execution_integration
        start_auto_execution_integration()
        logger.info("✅ Auto Execution System monitoring started")
    except Exception as e:
        logger.warning(f"⚠️ Could not start Auto Execution System monitoring: {e}")
    
    # Initialize Universal Dynamic SL/TP Manager
    try:
        from infra.universal_sl_tp_manager import UniversalDynamicSLTPManager
        from infra.mt5_service import MT5Service
        
        # Get or create MT5 service
        mt5_service = None
        try:
            mt5_service = MT5Service()
        except Exception as e:
            logger.warning(f"Could not create MT5Service for Universal Manager: {e}")
        
        # Initialize Universal Manager
        universal_sl_tp_manager = UniversalDynamicSLTPManager(
            db_path="data/universal_sl_tp_trades.db",
            mt5_service=mt5_service,
            config_path="config/universal_sl_tp_config.json"
        )
        
        # Recover trades on startup
        try:
            universal_sl_tp_manager.recover_trades_on_startup()
            logger.info("✅ Universal Dynamic SL/TP Manager initialized and trades recovered")
        except Exception as e:
            logger.warning(f"⚠️ Trade recovery failed: {e}")
            logger.info("✅ Universal Dynamic SL/TP Manager initialized (recovery skipped)")
    except ImportError as e:
        logger.warning(f"⚠️ Universal Dynamic SL/TP Manager not available: {e}")
        universal_sl_tp_manager = None
    except Exception as e:
        logger.warning(f"⚠️ Could not initialize Universal Dynamic SL/TP Manager: {e}")
        universal_sl_tp_manager = None

    # Start background scheduler (use regular scheduler for non-async context)
    scheduler = BackgroundScheduler()
    
    # Add background tasks with proper async handling
    def run_async_job(async_func):
        """Wrapper to run async functions in the scheduler"""
        import asyncio
        import inspect
        try:
            # Check if async_func is already a coroutine or a coroutine function
            if inspect.iscoroutine(async_func):
                # It's already a coroutine, await it
                coro = async_func
            elif inspect.iscoroutinefunction(async_func):
                # It's a coroutine function, call it to get the coroutine
                coro = async_func()
            else:
                # Not async, just call it
                async_func()
                return
                
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(coro)
        except Exception as e:
            func_name = getattr(async_func, '__name__', str(async_func))
            logger.error(f"Error in async job {func_name}: {e}", exc_info=True)
        finally:
            try:
                loop.close()
            except:
                pass
    
    scheduler.add_job(
        lambda: run_async_job(check_exit_signals_async),
        'interval',
        seconds=30,
        id='exit_signals'
    )
    
    scheduler.add_job(
        lambda: run_async_job(check_intelligent_exits_async),
        'interval',
        seconds=60,
        id='intelligent_exits'
    )
    
    scheduler.add_job(
        lambda: run_async_job(auto_enable_dtms_protection_async),
        'interval',
        seconds=120,
        id='dtms_protection'
    )
    
    # PHASE 5: DTMS monitoring scheduler job removed - using API server instead
    # DTMS monitoring is now handled by dtms_api_server.py (port 8001)
    # No local scheduler job needed
    # OLD CODE (commented out for rollback):
    # if dtms_engine:
    #     async def dtms_monitoring_cycle_async():
    #         """Run DTMS monitoring cycle (called by scheduler every 30 seconds)"""
    #         global dtms_engine
    #         try:
    #             logger.info("🔄 DTMS monitoring cycle scheduler job triggered")
    #             if dtms_engine is None:
    #                 logger.warning("⚠️ DTMS engine is None in scheduler job")
    #                 return
    #             
    #             from dtms_integration import run_dtms_monitoring_cycle as dtms_cycle
    #             logger.debug(f"Calling run_dtms_monitoring_cycle - engine: {dtms_engine}, monitoring_active: {getattr(dtms_engine, 'monitoring_active', 'unknown')}")
        #             await dtms_cycle()
        #         except Exception as e:
        #             logger.error(f"DTMS monitoring cycle error: {e}", exc_info=True)
        # 
        #     scheduler.add_job(
        #         lambda: run_async_job(dtms_monitoring_cycle_async),
        #         'interval',
        #         seconds=30,
        #         id='dtms_monitoring'
        #     )
        #     logger.info("✅ DTMS monitoring background task scheduled (every 30 seconds)")
    
    scheduler.add_job(
        lambda: run_async_job(auto_enable_intelligent_exits_async),
        'interval',
        seconds=180,
        id='intelligent_exits_auto'
    )
    
    scheduler.add_job(
        lambda: run_async_job(check_closed_trades_async),
        'interval',
        seconds=60,
        id='closed_trades'
    )
    
    scheduler.add_job(
        lambda: run_async_job(check_loss_cuts_async),
        'interval',
        seconds=45,
        id='loss_cuts'
    )
    
    scheduler.add_job(
        lambda: run_async_job(check_trade_setups_async),
        'interval',
        seconds=300,
        id='trade_setups'
    )
    
    scheduler.add_job(
        lambda: run_async_job(check_positions),
        'interval',
        seconds=30,
        id='positions'
    )
    
    scheduler.add_job(
        lambda: run_async_job(scan_for_signals),
        'interval',
        seconds=300,
        id='signal_scan'
    )
    
    scheduler.add_job(
        lambda: run_async_job(check_custom_alerts),
        'interval',
        seconds=60,
        id='custom_alerts'
    )
    
    scheduler.add_job(
        lambda: run_async_job(check_circuit_breaker),
        'interval',
        seconds=120,
        id='circuit_breaker'
    )
    
    # Add Universal Dynamic SL/TP Manager monitoring
    if universal_sl_tp_manager:
        def monitor_universal_trades():
            """Monitor all trades with Universal Dynamic SL/TP Manager"""
            try:
                if universal_sl_tp_manager:
                    universal_sl_tp_manager.monitor_all_trades()
            except Exception as e:
                logger.error(f"Error in Universal SL/TP monitoring: {e}", exc_info=True)
        
        scheduler.add_job(
            monitor_universal_trades,
            'interval',
            seconds=30,  # Monitor every 30 seconds
            id='universal_sl_tp_monitoring'
        )
        logger.info("✅ Universal Dynamic SL/TP Manager monitoring scheduled (every 30s)")
    
    # Add auto-execution outcome tracker background task (Phase 2: Database storage)
    if auto_execution_system:
        try:
            from infra.auto_execution_outcome_tracker import AutoExecutionOutcomeTracker
            from chatgpt_auto_execution_integration import get_chatgpt_auto_execution
            
            auto_execution_integration = get_chatgpt_auto_execution()
            outcome_tracker = AutoExecutionOutcomeTracker(auto_execution_integration.auto_system)
            
            async def run_outcome_tracker():
                await outcome_tracker.start(interval_seconds=300)  # Check every 5 minutes
            
            scheduler.add_job(
                lambda: run_async_job(run_outcome_tracker),
                'interval',
                seconds=300,
                id='auto_execution_outcome_tracker',
                max_instances=1
            )
            logger.info("✅ Auto-execution outcome tracker scheduled (checks every 5 minutes)")
        except Exception as e:
            logger.warning(f"⚠️ Auto-execution outcome tracker scheduling failed: {e}")
            logger.warning("   → Profit/loss data will still be available via MT5 queries")
    
    # Add CME gap detection and auto-plan creation (Phase 4: CME Gap Auto-Execution)
    try:
        from infra.cme_gap_detector import CMEGapDetector
        from infra.weekend_profile_manager import WeekendProfileManager
        from infra.mt5_service import MT5Service
        
        weekend_manager = WeekendProfileManager()
        mt5_service = MT5Service()
        gap_detector = CMEGapDetector(mt5_service=mt5_service)
        
        async def check_cme_gap_and_create_plan():
            """Check for CME gap and auto-create reversion plan if gap > 0.5%"""
            try:
                # Only check during weekend hours (Sunday 00:00 - Monday 03:00 UTC)
                if not weekend_manager.is_weekend_active():
                    return
                
                # Only check on Sunday (when gap is most relevant)
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                if now.weekday() != 6:  # Not Sunday
                    return
                
                # Check for gap in BTCUSDc
                symbol = "BTCUSDc"
                gap_info = gap_detector.detect_gap(symbol)
                
                if not gap_info or not gap_info.get("should_trade", False):
                    logger.debug(f"No significant CME gap detected for {symbol} (gap: {gap_info.get('gap_pct', 0):.2f}% if available)")
                    return
                
                # Gap detected - create reversion plan
                gap_pct = gap_info.get("gap_pct", 0)
                gap_direction = gap_info.get("gap_direction", "up")
                friday_close = gap_info.get("friday_close")
                sunday_open = gap_info.get("sunday_open")
                target_price = gap_info.get("target_price")
                
                logger.info(
                    f"CME gap detected for {symbol}: {gap_pct:.2f}% {gap_direction} "
                    f"(Friday: {friday_close:.2f}, Sunday: {sunday_open:.2f}, Target: {target_price:.2f})"
                )
                
                # Determine direction: BUY if gap down, SELL if gap up
                direction = "BUY" if gap_direction == "down" else "SELL"
                
                # Calculate entry, SL, TP
                # Entry: Current price (or Sunday open)
                entry_price = sunday_open
                
                # Stop Loss: Beyond Friday range extreme (use Friday close ± 1% for safety)
                if direction == "BUY":
                    stop_loss = friday_close * 0.99  # 1% below Friday close
                else:
                    stop_loss = friday_close * 1.01  # 1% above Friday close
                
                # Take Profit: 80% gap fill target
                take_profit = target_price
                
                # Create auto-execution plan via API
                import httpx
                import os
                API_BASE_URL = os.getenv("AUTO_EXECUTION_API_URL", "http://localhost:8000")
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{API_BASE_URL}/auto-execution/create-plan",
                        json={
                            "symbol": symbol,
                            "direction": direction,
                            "entry_price": entry_price,
                            "stop_loss": stop_loss,
                            "take_profit": take_profit,
                            "volume": 0.01,  # Default volume
                            "conditions": {
                                "session": "Weekend",
                                "min_confluence": 70,  # Weekend default
                                "price_near": entry_price,
                                "tolerance": 100.0  # Default tolerance for BTC
                            },
                            "expires_hours": 24,  # Weekend plan expiration
                            "notes": f"CME Gap Reversion Plan: {gap_pct:.2f}% {gap_direction} gap detected. Target: 80% gap fill."
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        plan_id = data.get("plan_id", "Unknown")
                        logger.info(f"✅ CME gap reversion plan created: {plan_id} ({direction} {symbol} @ {entry_price:.2f})")
                    else:
                        logger.warning(f"Failed to create CME gap reversion plan: {response.status_code} - {response.text}")
                        
            except Exception as e:
                logger.error(f"Error in CME gap detection and plan creation: {e}", exc_info=True)
        
        # Schedule CME gap check: Run every hour during weekend (Sunday 00:00 - Monday 03:00 UTC)
        scheduler.add_job(
            lambda: run_async_job(check_cme_gap_and_create_plan),
            'interval',
            hours=1,  # Check every hour during weekend
            id='cme_gap_detection',
            max_instances=1
        )
        logger.info("✅ CME gap detection scheduled (checks every hour during weekend)")
    except Exception as e:
        logger.warning(f"⚠️ CME gap detection scheduling failed: {e}")
        logger.warning("   → CME gap reversion plans will not be auto-created")
    
    # Add weekend transition check (every hour)
    try:
        if intelligent_exit_manager:
            def check_weekend_transition():
                """Check if weekend ended and transition trades to weekday parameters"""
                try:
                    intelligent_exit_manager.transition_weekend_trades_to_weekday()
                except Exception as e:
                    logger.error(f"Error in weekend transition check: {e}", exc_info=True)
            
            scheduler.add_job(
                lambda: run_async_job(check_weekend_transition),
                'interval',
                hours=1,
                id='weekend_transition_check',
                max_instances=1
            )
            logger.info("✅ Weekend transition check scheduled (every hour)")
    except Exception as e:
        logger.warning(f"⚠️ Weekend transition scheduling failed: {e}")
        logger.warning("   → Weekend trades will transition on system restart")
    
    # Start scheduler
    scheduler.start()
    logger.info("✅ Background scheduler started")
    
    # Log monitoring status
    logger.info("📊 Background Monitoring Active:")
    logger.info("   → Exit Signals: every 30s")
    logger.info("   → Intelligent Exits: every 60s")
    logger.info("   → DTMS Protection: every 2 min")
    logger.info("   → Intelligent Exits Auto: every 3 min")
    logger.info("   → Closed Trades: every 60s")
    logger.info("   → Loss Cuts: every 45s")
    if universal_sl_tp_manager:
        logger.info("   → Universal SL/TP Monitoring: every 30s")
    logger.info("   → Trade Setups: every 5 min")
    logger.info("   → Positions: every 30s")
    logger.info("   → Signal Scanner: every 5 min")
    logger.info("   → Circuit Breaker: every 2 min")
    logger.info("   → Custom Alerts: every 60s")
    if trade_monitor:
        logger.info("   → TradeMonitor: Active (momentum-aware trailing stops)")
    if exit_monitor:
        logger.info("   → ExitMonitor: Active (profit protection & exit signals)")
    logger.info("   → Automated Loss-Cutting: Active (enhanced multi-factor analysis)")
    
    # Keep the program running
    try:
        logger.info("🚀 ChatGPT Discord Bot is now running! Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down ChatGPT Discord Bot...")
        if scheduler:
            scheduler.shutdown()
        logger.info("✅ Shutdown complete")


if __name__ == "__main__":
    main()
