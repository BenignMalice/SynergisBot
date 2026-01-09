"""
Signal Scanner Command Handlers
Manual control and monitoring of the automatic signal detection system
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from config import settings

logger = logging.getLogger(__name__)

async def signal_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    IMPROVED: Show signal scanner status and configuration.
    """
    try:
        chat_id = update.effective_chat.id
        
        # Get current configuration
        enabled = getattr(settings, "SIGNAL_SCANNER_ENABLED", True)
        symbols = getattr(settings, "SIGNAL_SCANNER_SYMBOLS", ["XAUUSDc", "BTCUSDc"])
        interval = getattr(settings, "SIGNAL_SCANNER_INTERVAL", 300)
        min_confidence = getattr(settings, "SIGNAL_SCANNER_MIN_CONFIDENCE", 75)
        min_rr = getattr(settings, "SIGNAL_SCANNER_MIN_RR", 1.5)
        cooldown = getattr(settings, "SIGNAL_SCANNER_COOLDOWN", 30)
        max_per_hour = getattr(settings, "SIGNAL_SCANNER_MAX_PER_HOUR", 3)
        
        # Check if scanner is running
        jobs = [job.name for job in context.application.job_queue.jobs()]
        scanner_running = "_signal_scanner" in jobs
        
        status_emoji = "🟢" if enabled and scanner_running else "🔴"
        
        message = (
            f"{status_emoji} **Signal Scanner Status**\n\n"
            f"**Status:** {'Active' if enabled and scanner_running else 'Inactive'}\n"
            f"**Symbols:** {', '.join(symbols)}\n"
            f"**Scan Interval:** {interval}s ({interval//60} minutes)\n"
            f"**Min Confidence:** {min_confidence}%\n"
            f"**Min R:R Ratio:** {min_rr}\n"
            f"**Cooldown:** {cooldown} minutes\n"
            f"**Max Signals/Hour:** {max_per_hour}\n\n"
            f"**What it does:**\n"
            f"• Scans {len(symbols)} symbols every {interval//60} minutes\n"
            f"• Only sends notifications for signals ≥{min_confidence}% confidence\n"
            f"• Filters out low R:R ratios (<{min_rr})\n"
            f"• Rate limits to {max_per_hour} signals per hour\n"
            f"• Respects {cooldown}-minute cooldown between signals\n\n"
            f"**Commands:**\n"
            f"• `/signal_test` - Test scanner on current symbols\n"
            f"• `/signal_config` - Modify scanner settings\n"
        )
        
        # Create buttons
        buttons = [
            [
                InlineKeyboardButton("🧪 Test Scanner", callback_data="signal_test"),
                InlineKeyboardButton("⚙️ Configure", callback_data="signal_config")
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="signal_status"),
                InlineKeyboardButton("📊 View Jobs", callback_data="debugjobs")
            ]
        ]
        
        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.debug(f"Signal status command failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def signal_test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    IMPROVED: Test signal scanner on current symbols.
    """
    try:
        chat_id = update.effective_chat.id
        await update.message.reply_text("🧪 Testing signal scanner...")
        
        # Get services
        mt5svc = context.application.bot_data.get("mt5svc")
        if not mt5svc:
            await update.message.reply_text("❌ MT5Service not available")
            return
            
        from infra.signal_scanner import SignalScanner
        from infra.indicator_bridge import IndicatorBridge
        from infra.openai_service import OpenAIService
        
        # Initialize scanner
        bridge = IndicatorBridge(settings.MT5_FILES_DIR)
        oai = OpenAIService(settings.OPENAI_API_KEY, settings.OPENAI_MODEL)
        scanner = SignalScanner(mt5svc, bridge, oai)
        
        # Get symbols to test
        symbols = getattr(settings, "SIGNAL_SCANNER_SYMBOLS", ["XAUUSDc", "BTCUSDc"])
        
        results = []
        for symbol in symbols:
            try:
                signal = await scanner.scan_symbol(symbol)
                if signal:
                    results.append(f"✅ {symbol}: {signal['direction']} (Confidence: {signal['confidence']}%)")
                else:
                    results.append(f"❌ {symbol}: No signal found")
            except Exception as e:
                results.append(f"⚠️ {symbol}: Error - {str(e)[:50]}")
        
        # Send results
        message = "🧪 **Signal Scanner Test Results**\n\n" + "\n".join(results)
        await update.message.reply_text(message, parse_mode="Markdown")
        
    except Exception as e:
        logger.debug(f"Signal test command failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def signal_config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    IMPROVED: Configure signal scanner settings.
    """
    try:
        message = (
            "⚙️ **Signal Scanner Configuration**\n\n"
            "**Current Settings:**\n"
            f"• Symbols: {getattr(settings, 'SIGNAL_SCANNER_SYMBOLS', [])}\n"
            f"• Interval: {getattr(settings, 'SIGNAL_SCANNER_INTERVAL', 300)}s\n"
            f"• Min Confidence: {getattr(settings, 'SIGNAL_SCANNER_MIN_CONFIDENCE', 75)}%\n"
            f"• Min R:R: {getattr(settings, 'SIGNAL_SCANNER_MIN_RR', 1.5)}\n"
            f"• Cooldown: {getattr(settings, 'SIGNAL_SCANNER_COOLDOWN', 30)} min\n"
            f"• Max/Hour: {getattr(settings, 'SIGNAL_SCANNER_MAX_PER_HOUR', 3)}\n\n"
            "**To modify settings:**\n"
            "Edit `config/settings.py` and restart the bot.\n\n"
            "**Available Settings:**\n"
            "• `SIGNAL_SCANNER_ENABLED` - Enable/disable scanner\n"
            "• `SIGNAL_SCANNER_SYMBOLS` - List of symbols to scan\n"
            "• `SIGNAL_SCANNER_INTERVAL` - Scan interval in seconds\n"
            "• `SIGNAL_SCANNER_MIN_CONFIDENCE` - Minimum confidence %\n"
            "• `SIGNAL_SCANNER_MIN_RR` - Minimum risk:reward ratio\n"
            "• `SIGNAL_SCANNER_COOLDOWN` - Cooldown between signals (minutes)\n"
            "• `SIGNAL_SCANNER_MAX_PER_HOUR` - Rate limiting\n"
        )
        
        await update.message.reply_text(message, parse_mode="Markdown")
        
    except Exception as e:
        logger.debug(f"Signal config command failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def signal_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    IMPROVED: Handle signal scanner callback queries.
    """
    try:
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "signal_status":
            # Refresh status
            await signal_status_command(update, context)
            
        elif data == "signal_test":
            # Run test
            await signal_test_command(update, context)
            
        elif data == "signal_config":
            # Show config
            await signal_config_command(update, context)
            
        elif data == "debugjobs":
            # Show all jobs
            jobs = [job.name for job in context.application.job_queue.jobs()]
            await query.edit_message_text(f"📊 **Active Jobs:**\n\n" + "\n".join(f"• {job}" for job in jobs))
            
    except Exception as e:
        logger.debug(f"Signal callback handler failed: {e}")


def register_signal_handlers(app):
    """
    IMPROVED: Register signal scanner command handlers.
    """
    try:
        # Add command handlers
        app.add_handler(CommandHandler("signal_status", signal_status_command))
        app.add_handler(CommandHandler("signal_test", signal_test_command))
        app.add_handler(CommandHandler("signal_config", signal_config_command))
        
        # Add callback handler
        app.add_handler(CallbackQueryHandler(signal_callback_handler, pattern=r"^signal_|^debugjobs$"))
        
        logger.info("Signal scanner handlers registered")
        
    except Exception as e:
        logger.warning(f"Signal scanner handler registration failed: {e}")
