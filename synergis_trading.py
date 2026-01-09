# File: synergis_trading.py — Complete MT5 Trading System with Discord Notifications
from __future__ import annotations

# Load .env file FIRST, before any other imports
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    print(f"[SYNERGIS_TRADING] Loading .env from: {env_path}")
    load_dotenv(env_path, override=True)
    # Debug: Check if required keys are loaded
    openai_key = os.getenv("OPENAI_API_KEY")
    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
    print(f"[SYNERGIS_TRADING] OPENAI_API_KEY loaded: {'YES' if openai_key else 'NO'}")
    print(f"[SYNERGIS_TRADING] DISCORD_WEBHOOK_URL loaded: {'YES' if discord_webhook else 'NO'}")
else:
    print(f"[SYNERGIS_TRADING] No .env file found at: {env_path}")

import asyncio
import logging
import time
import sys
import threading
from typing import Any
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

# WhatsApp notifications removed - Discord only
WHATSAPP_ENABLED = False

import importlib.util
import sys
# Import config.py directly, not the config package
spec = importlib.util.spec_from_file_location('config_module', 'config.py')
config_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_module)
settings = config_module.settings

from infra.journal_repo import JournalRepo
from infra.position_watcher import PositionWatcher
from infra.mt5_service import MT5Service
from infra.scheduler import history_watcher
from infra.virt_pendings import VirtualPendingManager as PseudoPendingManager
from infra.circuit_breaker import CircuitBreaker

# --- place at very top of synergis_trading.py ---
import faulthandler, threading, time, sys, os

faulthandler.enable()
# Dump all thread stack traces every 20s so we can see where it's waiting
# faulthandler.dump_traceback_later(20, repeat=True)  # Disabled to prevent timeout warnings

def _hb():
    n = 0
    while True:
        try:
            print(f"[HB] alive t={n}s", flush=True)
            n += 5
            time.sleep(5)
        except Exception as e:
            print(f"[HB] Error: {e}", flush=True)
            time.sleep(5)

threading.Thread(target=_hb, daemon=True).start()

# ---- logging (configure FIRST, force override) ----
_level = getattr(
    logging,
    str(getattr(settings, "LOG_LEVEL", "DEBUG")).upper(),  # default DEBUG for testing
    logging.DEBUG,
)

# IMPROVED: Log to both console and file
log_file = os.path.join(os.path.dirname(__file__), "data", "synergis_trading.log")
os.makedirs(os.path.dirname(log_file), exist_ok=True)

# Configure logging with both handlers (UTF-8 for Windows compatibility)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(_level)
console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
# Force UTF-8 encoding for console on Windows
if hasattr(console_handler.stream, 'reconfigure'):
    console_handler.stream.reconfigure(encoding='utf-8')

file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
file_handler.setLevel(_level)
file_handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))

logging.basicConfig(
    level=_level,
    format="[%(levelname)s] %(name)s: %(message)s",
    force=True,
    handlers=[console_handler, file_handler]
)
logger = logging.getLogger(__name__)
logger.info(f"=" * 80)
logger.info(f"Synergis Trading Bot Starting - {time.strftime('%Y-%m-%d %H:%M:%S')}")
logger.info(f"Log file: {log_file}")
logger.info(f"=" * 80)
logger.info(
    "Logging configured at %s",
    logging.getLevelName(logging.getLogger().getEffectiveLevel()),
)

# Notification functions (Discord + WhatsApp)
def notify_discord_trade(symbol, action, price, lot_size, status, profit=None):
    """Send Discord trade notification"""
    if DISCORD_ENABLED:
        try:
            discord_notifier.send_trade_alert(symbol, action, price, lot_size, status, profit)
        except Exception as e:
            logger.warning(f"Discord trade notification failed: {e}")

def notify_discord_system(alert_type, message):
    """Send Discord system notification"""
    if DISCORD_ENABLED:
        try:
            discord_notifier.send_system_alert(alert_type, message)
        except Exception as e:
            logger.warning(f"Discord system notification failed: {e}")

def notify_discord_dtms(ticket, action, reason, price):
    """Send Discord DTMS notification"""
    if DISCORD_ENABLED:
        try:
            discord_notifier.send_dtms_alert(ticket, action, reason, price)
        except Exception as e:
            logger.warning(f"Discord DTMS notification failed: {e}")

def notify_discord_risk(level, message, action):
    """Send Discord risk notification"""
    if DISCORD_ENABLED:
        try:
            discord_notifier.send_risk_alert(level, message, action)
        except Exception as e:
            logger.warning(f"Discord risk notification failed: {e}")

# Unified notification functions (Discord only)
def notify_trade(symbol, action, price, lot_size, status, profit=None):
    """Send trade notification to Discord"""
    notify_discord_trade(symbol, action, price, lot_size, status, profit)

def notify_system(alert_type, message):
    """Send system notification to Discord"""
    notify_discord_system(alert_type, message)

def notify_dtms(ticket, action, reason, price):
    """Send DTMS notification to Discord"""
    notify_discord_dtms(ticket, action, reason, price)

def notify_risk(level, message, action):
    """Send risk notification to Discord"""
    notify_discord_risk(level, message, action)

def main() -> None:
    # ---- sanity checks ----
    openai_key = os.getenv("OPENAI_API_KEY")
    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
    
    if not openai_key:
        logger.warning("OPENAI_API_KEY not set — GPT features will be disabled.")
    if not discord_webhook:
        logger.warning("DISCORD_WEBHOOK_URL not set — Discord notifications will be disabled.")
    
    # ---- core services ----
    journal = JournalRepo(
        db_path=getattr(settings, "JOURNAL_DB_PATH", "./data/journal.sqlite"),
        csv_path=getattr(settings, "JOURNAL_CSV_PATH", "./data/journal_events.csv"),
        csv_enable=getattr(settings, "JOURNAL_CSV_ENABLE", True),
    )
    mt5svc = MT5Service()  # connection handled per call; .connect() is idempotent
    poswatch = PositionWatcher(
        getattr(settings, "POS_STORE_PATH", "./data/positions.json")
    )
    pending_manager = PseudoPendingManager(
        getattr(settings, "PENDINGS_STORE_PATH", "./data/pendings.json")
    )
    circuit = CircuitBreaker(getattr(settings, "CB_STORE_PATH", "./data/circuit.json"))

    # IMPROVED: Ensure MT5 is connected early for Trade Monitor
    logger.info("Connecting to MT5...")
    if not mt5svc.connect():
        logger.error("Failed to connect to MT5 - some features will be unavailable")
        notify_system("MT5_ERROR", "Failed to connect to MT5 - some features will be unavailable")
    else:
        logger.info("✅ MT5 connected successfully")
        notify_system("MT5_CONNECTED", "MT5 connected successfully")
    
    # IMPROVED Phase 4.4: Initialize Trade Monitor for trailing stops
    trade_monitor = None
    if settings.USE_TRAILING_STOPS:
        logger.info("Initializing Trade Monitor for trailing stops...")
        try:
            from infra.trade_monitor import TradeMonitor
            from infra.feature_builder import FeatureBuilder
            from infra.indicator_bridge import IndicatorBridge
            
            logger.info("  → Creating IndicatorBridge...")
            common_files_dir = settings.MT5_FILES_DIR or r"C:\Users\Public\Documents\MetaQuotes\Terminal\Common\Files"
            bridge = IndicatorBridge(common_files_dir)
            
            logger.info("  → Creating FeatureBuilder...")
            feature_builder = FeatureBuilder(mt5svc, bridge)
            
            logger.info("  → Creating TradeMonitor...")
            trade_monitor = TradeMonitor(
                mt5_service=mt5svc,
                feature_builder=feature_builder,
                indicator_bridge=bridge,
                journal_repo=journal
            )
            
            logger.info("  → Scheduling trailing stop checks...")
            trailing_scheduler = BackgroundScheduler()
            trailing_scheduler.add_job(
                trade_monitor.check_trailing_stops,
                'interval',
                seconds=settings.TRAILING_CHECK_INTERVAL,
                id='trailing_stops',
                max_instances=1,
                replace_existing=True
            )
            trailing_scheduler.start()
            
            logger.info(f"✓ Trade monitor started successfully (checks every {settings.TRAILING_CHECK_INTERVAL}s)")
            notify_system("TRADE_MONITOR", f"Trade monitor started (checks every {settings.TRAILING_CHECK_INTERVAL}s)")
        except Exception as e:
            import traceback
            logger.error(f"✗ Failed to start trade monitor: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            logger.warning("⚠️ Trailing stops will NOT be active")
            notify_system("TRADE_MONITOR_ERROR", f"Failed to start trade monitor: {e}")
            trade_monitor = None
    else:
        logger.info("Trailing stops disabled (USE_TRAILING_STOPS=0 in config)")

    # ---- background jobs (JobQueue runs after app.start) ----
    close_watch_interval = int(getattr(settings, "CLOSE_WATCH_INTERVAL", 30))
    
    # IMPROVED: Register signal scanner for automatic high-probability signal detection
    try:
        from infra.signal_scanner import register_signal_scanner
        if getattr(settings, "SIGNAL_SCANNER_ENABLED", True):
            register_signal_scanner(None, mt5svc)  # No app needed for signal scanner
            logger.info("Signal scanner enabled - monitoring for high-probability signals")
            notify_system("SIGNAL_SCANNER", "Signal scanner enabled - monitoring for high-probability signals")
    except Exception as e:
        logger.warning(f"Signal scanner registration failed: {e}")

    # ---- main trading loop ----
    logger.info("Starting main trading loop...")
    notify_system("BOT_START", "Synergis Trading Bot started successfully")
    
    # Create scheduler for background tasks
    scheduler = BackgroundScheduler()
    
    # Schedule all the trading tasks
    def _tick_job():
        logger.info("[JOB _tick_job] tick start")
        try:
            # Create event loop for async functions
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(history_watcher(None, mt5svc, journal, close_watch_interval))
            loop.close()
        except Exception:
            logger.debug("history_watcher failed", exc_info=True)
        finally:
            logger.info("[JOB _tick_job] tick done")

    def _pos_tick():
        logger.info("[JOB _pos_tick] tick start")
        try:
            mt5svc.connect()  # safe to call each tick
            poswatch.poll_once(
                mt5svc,
                journal_repo=journal,
                notifier=None,  # No Telegram notifier
                default_chat_id=None,
            )
        except Exception:
            logger.debug("pos_watch tick failed", exc_info=True)
        finally:
            logger.info("[JOB _pos_tick] tick done")

    def _cb_tick():
        try:
            circuit.daily_rollover_if_needed(journal_repo=journal)
        except Exception:
            logger.debug("circuit daily rollover failed", exc_info=True)

    def _pending_tick():
        logger.info("[JOB _pending_tick] tick start [fallback]")
        try:
            mt5svc.connect()
            pending_manager.poll_once(
                mt5svc,
                None,  # No Telegram notifier
                journal_repo=journal,
                poswatch=poswatch,
                circuit=circuit,
            )
        except Exception:
            logger.debug("Pending tick (fallback) failed", exc_info=True)
        finally:
            logger.info("[JOB _pending_tick] tick done [fallback]")

    # Schedule all jobs
    scheduler.add_job(_tick_job, 'interval', seconds=close_watch_interval, id='_tick_job')
    logger.info(f"[JOB _tick_job] scheduled: every {close_watch_interval}s")
    
    if bool(getattr(settings, "POS_WATCH_ENABLE", True)):
        scheduler.add_job(_pos_tick, 'interval', seconds=max(5, int(getattr(settings, "POS_WATCH_INTERVAL", 20))), id='_pos_tick')
        logger.info(f"[JOB _pos_tick] scheduled: every {max(5, int(getattr(settings, 'POS_WATCH_INTERVAL', 20)))}s")
    
    scheduler.add_job(_cb_tick, 'interval', seconds=120, id='_cb_tick')
    scheduler.add_job(_pending_tick, 'interval', seconds=10, id='_pending_tick')
    
    # Start scheduler
    scheduler.start()
    logger.info("Background scheduler started")
    
    try:
        # Main trading loop
        while True:
            try:
                # Check MT5 connection
                if not mt5svc.connect():
                    logger.warning("MT5 connection lost, attempting to reconnect...")
                    notify_system("MT5_RECONNECT", "MT5 connection lost, attempting to reconnect...")
                    time.sleep(5)
                    continue
                
                # Sleep before next iteration
                time.sleep(close_watch_interval)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                notify_system("BOT_STOP", "Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                notify_system("BOT_ERROR", f"Error in main loop: {e}")
                time.sleep(10)  # Wait before retrying
                
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}")
        notify_system("BOT_FATAL_ERROR", f"Fatal error in main loop: {e}")
        raise
    finally:
        # Shutdown scheduler
        scheduler.shutdown()
        logger.info("Background scheduler stopped")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Fatal error during startup.")
        raise
