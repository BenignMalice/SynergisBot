# File: trade_bot.py — slim bootstrap (modular wiring) [HARDENED INIT]
from __future__ import annotations

# Load .env file FIRST, before any other imports
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    print(f"[TRADE_BOT] Loading .env from: {env_path}")
    load_dotenv(env_path, override=True)
    # Debug: Check if TELEGRAM_TOKEN is loaded
    token = os.getenv("TELEGRAM_TOKEN")
    print(f"[TRADE_BOT] TELEGRAM_TOKEN loaded: {'YES' if token else 'NO'}")
    if token:
        print(f"[TRADE_BOT] Token length: {len(token)}")
else:
    print(f"[TRADE_BOT] No .env file found at: {env_path}")

import asyncio
import logging
from typing import Any

from telegram.ext import (
    ApplicationBuilder,
    AIORateLimiter,
    CommandHandler,
    CallbackQueryHandler,
    Application,
)

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

# --- place at very top of trade_bot.py ---
import faulthandler, threading, time, sys, os

# Free WhatsApp notifications
try:
    from simple_free_whatsapp import SimpleFreeWhatsApp
    whatsapp_notifier = SimpleFreeWhatsApp()
    WHATSAPP_ENABLED = True
    print("SUCCESS: Free WhatsApp notifications enabled")
except ImportError as e:
    WHATSAPP_ENABLED = False
    print(f"WARNING: Free WhatsApp notifications disabled: {e}")


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
log_file = os.path.join(os.path.dirname(__file__), "data", "bot.log")
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
    force=True,  # <- ensures this wins even if something configured earlier
    handlers=[console_handler, file_handler]
)
logger = logging.getLogger(__name__)
logger.info(f"=" * 80)
logger.info(f"TelegramMoneyBot Starting - {time.strftime('%Y-%m-%d %H:%M:%S')}")
logger.info(f"Log file: {log_file}")
logger.info(f"=" * 80)
logger.info(
    "Logging configured at %s",
    logging.getLevelName(logging.getLogger().getEffectiveLevel()),
)
print(
    f"[PRINT] root effective level = {logging.getLevelName(logging.getLogger().getEffectiveLevel())}"
)

# Optional error handler registration (support singular/plural)
try:
    from handlers.errors import register_error_handler as _register_errors
except Exception:
    try:
        from handlers.errors import register_error_handlers as _register_errors
    except Exception:
        _register_errors = None  # continue without a custom error handler



def notify_whatsapp_trade(symbol, action, price, lot_size, status, profit=None):
    """Send free WhatsApp trade notification"""
    if WHATSAPP_ENABLED:
        try:
            whatsapp_notifier.send_trade_alert(symbol, action, price, lot_size, status, profit)
        except Exception as e:
            logger.warning(f"Free WhatsApp trade notification failed: {e}")

def notify_whatsapp_system(alert_type, message):
    """Send free WhatsApp system notification"""
    if WHATSAPP_ENABLED:
        try:
            whatsapp_notifier.send_system_alert(alert_type, message)
        except Exception as e:
            logger.warning(f"Free WhatsApp system notification failed: {e}")

def notify_whatsapp_dtms(ticket, action, reason, price):
    """Send free WhatsApp DTMS notification"""
    if WHATSAPP_ENABLED:
        try:
            whatsapp_notifier.send_dtms_alert(ticket, action, reason, price)
        except Exception as e:
            logger.warning(f"Free WhatsApp DTMS notification failed: {e}")

def notify_whatsapp_risk(level, message, action):
    """Send free WhatsApp risk notification"""
    if WHATSAPP_ENABLED:
        try:
            whatsapp_notifier.send_risk_alert(level, message, action)
        except Exception as e:
            logger.warning(f"Free WhatsApp risk notification failed: {e}")

def main() -> None:
    # ---- sanity checks ----
    # Use os.getenv() directly since we loaded the .env file at the top
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not telegram_token:
        raise RuntimeError("Missing TELEGRAM_TOKEN in environment.")
    if not openai_key:
        logger.warning("OPENAI_API_KEY not set — GPT features will be disabled.")
    
    # ---- network connectivity check ----
    try:
        import requests
        response = requests.get("https://api.telegram.org", timeout=5)
        logger.info("✅ Telegram API connectivity confirmed")
    except requests.exceptions.ConnectTimeout:
        logger.warning("⚠️ Telegram API connection timeout - bot may have limited functionality")
        logger.warning("   This could be due to network restrictions or firewall blocking")
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ Telegram API connectivity issue: {e}")
        logger.warning("   Bot will continue but may not be able to receive messages")

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
    
    # IMPROVED Phase 4.4: Initialize Trade Monitor for trailing stops
    trade_monitor = None
    if settings.USE_TRAILING_STOPS:
        logger.info("Initializing Trade Monitor for trailing stops...")
        try:
            from infra.trade_monitor import TradeMonitor
            from infra.feature_builder import FeatureBuilder
            from infra.indicator_bridge import IndicatorBridge
            from apscheduler.schedulers.background import BackgroundScheduler
            
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
        except Exception as e:
            import traceback
            logger.error(f"✗ Failed to start trade monitor: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            logger.warning("⚠️ Trailing stops will NOT be active")
            trade_monitor = None
    else:
        logger.info("Trailing stops disabled (USE_TRAILING_STOPS=0 in config)")

    # Import handlers only after logging is configured
    from handlers.circuit import register_circuit_handlers
    from handlers.menu import register_menu_handlers
    from handlers.trading import register_trading_handlers
    from handlers.charts import loadcharts_menu, button_router
    from handlers.journal import register_journal_handlers
    from handlers.pending import register_pending_handlers
    from handlers.help import register_help_handlers

    # ---- post_init hook (SAFE place to use app.bot / job_queue) ----
    async def _post_init(app: Application) -> None:
        try:
            # Add timeout and retry logic for get_me
            import asyncio
            me = await asyncio.wait_for(app.bot.get_me(), timeout=30.0)
            logger.info("Bot ready: @%s (id=%s)", me.username, me.id)
        except asyncio.TimeoutError:
            logger.warning("⚠️ Telegram API timeout - bot may not be fully functional")
            logger.warning("   This could be due to network issues or Telegram API being blocked")
        except Exception as e:
            logger.warning(f"⚠️ get_me failed during post_init: {e}")
            logger.warning("   Bot will continue but may have limited functionality")
        # Ensure /help menu sync after initialization
        try:
            register_help_handlers(app, sync_menu=True)
            logger.info("/help menu sync scheduled")
        except Exception:
            logger.debug(
                "register_help_handlers(sync_menu=True) failed in post_init",
                exc_info=True,
            )
        logger.info("Building application...")

    # ---- telegram app ----
    # Try to configure proxy if available
    proxy_url = os.getenv("TELEGRAM_PROXY") or os.getenv("PROXY_URL")
    
    app_builder = ApplicationBuilder().token(telegram_token).rate_limiter(AIORateLimiter())
    
    # Add proxy if configured
    if proxy_url:
        try:
            from telegram.request import HTTPXRequest
            import httpx
            proxy_client = httpx.AsyncClient(proxies=proxy_url)
            request = HTTPXRequest(connection_pool_size=8, proxy=proxy_url)
            app_builder = app_builder.request(request)
            logger.info(f"✅ Using proxy for Telegram: {proxy_url}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to configure proxy {proxy_url}: {e}")
    
    # Try alternative base URL if main API is blocked
    base_url = os.getenv("TELEGRAM_BASE_URL")
    if base_url:
        try:
            app_builder = app_builder.base_url(base_url)
            logger.info(f"✅ Using alternative Telegram API: {base_url}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to set base URL {base_url}: {e}")
    
    app = app_builder.post_init(_post_init).build()
    logger.info("Application built.")
    
    
    # Discord fallback if Telegram fails
    try:
        from discord_notifications import DiscordNotifier
        discord_notifier = DiscordNotifier()
        if discord_notifier.enabled:
            discord_notifier.send_system_alert("BOT_START", "Trading bot started (Telegram unavailable)")
    except Exception as e:
        logger.warning(f"Discord fallback failed: {e}")
    
    logger.info("Application built.")

    # Share services via bot_data for handlers
    app.bot_data["poswatch"] = poswatch
    app.bot_data["mt5svc"] = mt5svc
    app.bot_data["journal"] = journal  # some modules read this
    app.bot_data["journal_repo"] = journal  # others read this name
    app.bot_data["pending_manager"] = pending_manager
    app.bot_data["circuit"] = circuit

    # ---- handlers ----
    logger.info("Registering handlers...")

    # ChatGPT Bridge
    try:
        from handlers.chatgpt_bridge import register_chatgpt_handlers
        register_chatgpt_handlers(app)
        logger.info("ChatGPT bridge registered")
    except Exception:
        logger.error("Failed to register ChatGPT bridge", exc_info=True)

    # 👉 Commands FIRST (group 0): /trade, /critic, /pending, /pendings, /journal, /status, /help, etc.
    # (register_trading_handlers should register /trade; if it takes a group arg, pass group=0)
    try:
        register_trading_handlers(
            app, journal
        )  # ensure this registers CommandHandler("trade", ...)
    except TypeError:
        # If your function signature accepts a group, prefer group=0:
        register_trading_handlers(app, journal)

    # === ANCHOR: HANDLERS_REGISTER_START ===
    register_journal_handlers(app, journal, settings)

    # Guard to prevent double registration (hot reloads / multiple build paths)
    if not app.bot_data.get("__pending_handlers_registered__", False):
        register_pending_handlers(app, pending_manager, journal)
        app.bot_data["__pending_handlers_registered__"] = True
        logger.info("Pending handlers registered (once).")
    else:
        logger.warning("Pending handlers already registered; skipping.")
    # === ANCHOR: HANDLERS_REGISTER_END ===

    register_circuit_handlers(app, circuit, journal)

    # /loadcharts command is also a command → keep in group 0
    app.add_handler(CommandHandler("loadcharts", loadcharts_menu), group=0)

    # 👉 Menu callbacks LATER (group 1), so they never pre-empt commands
    register_menu_handlers(app, commands_group=0, callbacks_group=1)

    # Charts/menu callbacks router belongs with other callbacks (group 1)
    app.add_handler(
        CallbackQueryHandler(
            button_router,
            pattern=r"^(loadcharts(?:\|.*)?|run_manager(?:\|.*)?|back_to_menu(?:\|.*)?)$",
        ),
        group=1,
    )

    # Dump handlers per group for sanity
    def _dump_handlers():
        from telegram.ext import ConversationHandler
        out = {}
        for grp, handlers in app.handlers.items():
            handler_names = []
            for h in handlers:
                if isinstance(h, ConversationHandler):
                    handler_names.append(f"ConversationHandler({h.name})")
                else:
                    handler_names.append(getattr(h.callback, "__name__", str(h.callback)))
            out[grp] = handler_names
        return out

    logger.info("Handlers registered by group: %s", _dump_handlers())

    # ---- error handlers (optional) ----
    if _register_errors:
        _register_errors(app)
    else:
        logger.info("No custom error handler registered (handlers.errors not found).")

    # === ANCHOR: DEBUG_JOBS_CMD_START ===
    async def debug_jobs(update, context):
        jobs = [j.name for j in context.application.job_queue.jobs()]
        await (update.message or update.callback_query.message).reply_text(
            f"Jobs: {jobs}"
        )

    app.add_handler(CommandHandler("debugjobs", debug_jobs), group=0)
    # === ANCHOR: DEBUG_JOBS_CMD_END ===

    # IMPROVED: Register signal scanner handlers
    try:
        from handlers.signal_scanner import register_signal_handlers
        register_signal_handlers(app)
    except Exception as e:
        logger.warning(f"Signal scanner handlers registration failed: {e}")

    # IMPROVED: Register feature builder handlers
    try:
        from handlers.feature_builder import register_feature_builder_handlers
        register_feature_builder_handlers(app)
        logger.info("Feature builder handlers registered")
    except Exception as e:
        logger.warning(f"Feature builder handlers registration failed: {e}")
    
    # IMPROVED: Register prompt router handlers
    try:
        from handlers.prompt_router import register_prompt_router_handlers
        register_prompt_router_handlers(app)
        logger.info("Prompt router handlers registered")
    except Exception as e:
        logger.warning(f"Prompt router handlers registration failed: {e}")

    # ---- notifiers/adapters ----
    def _notify_sync(chat_id: int, text: str) -> Any:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(app.bot.send_message(chat_id=chat_id, text=text))
        except RuntimeError:
            asyncio.get_event_loop().create_task(
                app.bot.send_message(chat_id=chat_id, text=text)
            )

    # ---- background jobs (JobQueue runs after app.start) ----
    close_watch_interval = int(getattr(settings, "CLOSE_WATCH_INTERVAL", 30))
    
    # IMPROVED: Register signal scanner for automatic high-probability signal detection
    try:
        from infra.signal_scanner import register_signal_scanner
        if getattr(settings, "SIGNAL_SCANNER_ENABLED", True):
            register_signal_scanner(app, mt5svc)
            logger.info("Signal scanner enabled - monitoring for high-probability signals")
    except Exception as e:
        logger.warning(f"Signal scanner registration failed: {e}")

    async def _tick_job(_ctx):
        logger.info("[JOB _tick_job] tick start")
        try:
            await history_watcher(app, mt5svc, journal, close_watch_interval)
        except Exception:
            logger.debug("history_watcher failed", exc_info=True)
        finally:
            logger.info("[JOB _tick_job] tick done")

    app.job_queue.run_repeating(
        _tick_job,
        interval=close_watch_interval,
        first=10,
        name="_tick_job",
    )
    logger.info(
        "[JOB _tick_job] scheduled: every %ss, first in %ss",
        close_watch_interval,
        10,
    )

    if bool(getattr(settings, "POS_WATCH_ENABLE", True)):

        # === ANCHOR: POSWATCH_TICK_BODY_START ===
        async def _pos_tick(_ctx):
            logger.info("[JOB _pos_tick] tick start")
            try:
                mt5svc.connect()  # safe to call each tick
                default_chat_id = app.bot_data.get("poswatch_last_chat_id") or getattr(
                    settings, "DEFAULT_NOTIFY_CHAT_ID", None
                )
                logger.debug("[JOB _pos_tick] default_chat_id=%s", default_chat_id)
                # poll_once accepts default_chat_id (PositionWatcher.poll_once signature updated)
                poswatch.poll_once(
                    mt5svc,
                    journal_repo=journal,
                    notifier=_notify_sync,
                    default_chat_id=default_chat_id,
                )
            except Exception:
                logger.debug("pos_watch tick failed", exc_info=True)
            finally:
                logger.info("[JOB _pos_tick] tick done")

        # === ANCHOR: POSWATCH_TICK_BODY_END ===

        app.job_queue.run_repeating(
            _pos_tick,
            interval=max(5, int(getattr(settings, "POS_WATCH_INTERVAL", 20))),
            first=12,
            name="_pos_tick",
        )
        logger.info(
            "[JOB _pos_tick] scheduled: every %ss, first in %ss",
            max(5, int(getattr(settings, "POS_WATCH_INTERVAL", 20))),
            12,
        )

    async def _cb_tick(_ctx):
        try:
            circuit.daily_rollover_if_needed(journal_repo=journal)
        except Exception:
            logger.debug("circuit daily rollover failed", exc_info=True)

    app.job_queue.run_repeating(_cb_tick, interval=120, first=15, name="_cb_tick")

    # 4) Fallback pending tick (handlers.pending normally schedules its own)
    try:
        existing = [j for j in app.job_queue.jobs() if j.name == "_pending_tick"]

        if not existing:

            async def _pending_tick_bridge(_ctx):
                logger.info("[JOB _pending_tick] tick start [fallback]")
                try:
                    mt5svc.connect()
                    pending_manager.poll_once(
                        mt5svc,
                        _notify_sync,
                        journal_repo=journal,
                        poswatch=poswatch,
                        circuit=circuit,
                    )
                except Exception:
                    logger.debug("Pending tick (fallback) failed", exc_info=True)
                finally:
                    logger.info("[JOB _pending_tick] tick done [fallback]")

            app.job_queue.run_repeating(
                _pending_tick_bridge, interval=10, first=7, name="_pending_tick"
            )
            logger.info(
                "[JOB _pending_tick] scheduled (fallback): every %ss, first in %ss",
                10,
                7,
            )
        else:
            logger.info("[JOB _pending_tick] already scheduled by handlers.pending")
    except Exception:
        logger.debug("Could not verify/schedule _pending_tick", exc_info=True)

    # ---- lift-off ----
    logger.info("Bot starting…")
    try:
        # Add timeout and error handling for polling
        import time
        logger.info("Waiting 5 seconds before starting polling to avoid conflicts...")
        time.sleep(5)
        
        app.run_polling(
            drop_pending_updates=True,
            timeout=30,  # Increase timeout to 30 seconds
            bootstrap_retries=5,  # Retry connection 5 times
            close_loop=False  # Don't close the loop on errors
        )
    except Exception as e:
        logger.error(f"Error during bot startup: {e}")
        if "ExtBot is not properly initialized" in str(e):
            logger.warning(
                "PTB init bug encountered. Falling back to manual initialize/start."
            )
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(app.initialize())
                loop.run_until_complete(app.start())
                logger.info("Polling started (manual). Press Ctrl+C to stop.")
                try:
                    loop.run_forever()
                except KeyboardInterrupt:
                    pass
                finally:
                    loop.run_until_complete(app.stop())
            finally:
                loop.close()
        elif "timeout" in str(e).lower():
            logger.error("Timeout error detected. This might be due to network issues or Telegram API problems.")
            logger.info("Try checking your internet connection and Telegram API status.")
        else:
            raise


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Fatal error during startup.")
        raise
