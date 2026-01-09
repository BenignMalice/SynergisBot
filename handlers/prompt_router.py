"""
Prompt Router Handlers - Phase 2
Telegram command handlers for prompt router management and testing
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from infra.prompt_router import create_prompt_router
from infra.prompt_templates import create_template_manager
from infra.prompt_validator import create_prompt_validator

logger = logging.getLogger(__name__)

async def router_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show prompt router status and configuration."""
    try:
        router = create_prompt_router()
        template_manager = create_template_manager()
        
        # Get available templates
        templates = template_manager.list_templates()
        template_count = len(templates)
        
        # Get active versions
        active_versions = template_manager.active_versions
        
        message = f"🎛️ **Prompt Router Status**\n\n"
        message += f"📊 **Templates Available:** {template_count}\n"
        message += f"🔄 **Active Versions:**\n"
        
        for strategy, version in active_versions.items():
            message += f"  • {strategy}: {version}\n"
        
        message += f"\n📋 **Available Templates:**\n"
        for template in templates:
            message += f"  • {template.name} ({template.version})\n"
        
        message += f"\n✅ **Router Status:** Active and Ready"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Router status failed: {e}")
        await update.message.reply_text(f"❌ Router status failed: {e}")

async def router_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test prompt router with sample data."""
    try:
        symbol = context.args[0] if context.args else "XAUUSDc"
        
        # Create sample feature data
        sample_features = {
            "symbol": symbol,
            "timestamp": "2025-01-01T12:00:00Z",
            "cross_tf": {
                "trend_agreement": 0.8,
                "trend_consensus": "up",
                "rsi_confluence": 0.7,
                "vol_regime_consensus": "normal"
            },
            "M5": {
                "trend_state": "up",
                "rsi_14": 65.0,
                "adx": 28.0,
                "ema_alignment": True,
                "atr_14": 15.0,
                "bb_width": 0.02,
                "pattern_flags": {
                    "bull_engulfing": True,
                    "hammer": False
                },
                "candlestick_flags": {
                    "marubozu": False,
                    "doji": False
                },
                "session": "london",
                "news_blackout": False
            },
            "M15": {
                "trend_state": "up",
                "rsi_14": 62.0,
                "adx": 25.0,
                "ema_alignment": True
            },
            "H1": {
                "trend_state": "up",
                "rsi_14": 58.0,
                "adx": 22.0,
                "ema_alignment": True
            }
        }
        
        # Create sample guardrails
        sample_guardrails = {
            "news_block": False,
            "spread_limit": 0.5,
            "exposure_limit": False
        }
        
        # Test router
        router = create_prompt_router()
        trade_spec = router.route_and_analyze(symbol, sample_features, sample_guardrails)
        
        if trade_spec:
            message = f"🧪 **Router Test Results**\n\n"
            message += f"📊 **Symbol:** {symbol}\n"
            message += f"🎯 **Strategy:** {trade_spec.strategy}\n"
            message += f"📋 **Order Type:** {trade_spec.order_type}\n"
            message += f"💰 **Entry:** {trade_spec.entry}\n"
            message += f"🛡️ **SL:** {trade_spec.sl}\n"
            message += f"🎯 **TP:** {trade_spec.tp}\n"
            message += f"📈 **RR:** {trade_spec.rr:.2f}\n"
            message += f"🎯 **Confidence:** {trade_spec.confidence}\n"
            message += f"📝 **Rationale:** {trade_spec.rationale}\n"
            message += f"🏷️ **Tags:** {', '.join(trade_spec.tags)}\n"
            message += f"📋 **Template:** {trade_spec.template_version}\n"
            message += f"🎯 **Regime Fit:** {trade_spec.regime_fit}%"
        else:
            message = f"🧪 **Router Test Results**\n\n"
            message += f"📊 **Symbol:** {symbol}\n"
            message += f"❌ **Result:** No valid trade found\n"
            message += f"💡 **Reason:** Router could not find suitable trade setup"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Router test failed: {e}")
        await update.message.reply_text(f"❌ Router test failed: {e}")

async def router_templates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List available prompt templates."""
    try:
        template_manager = create_template_manager()
        templates = template_manager.list_templates()
        
        message = f"📋 **Available Prompt Templates**\n\n"
        
        # Group by strategy
        strategies = {}
        for template in templates:
            strategy = template.strategy
            if strategy not in strategies:
                strategies[strategy] = []
            strategies[strategy].append(template)
        
        for strategy, template_list in strategies.items():
            message += f"🎯 **{strategy.upper()}**\n"
            for template in template_list:
                message += f"  • {template.name} ({template.version})\n"
                message += f"    Order Types: {', '.join(template.order_types)}\n"
                message += f"    RR Range: {template.min_rr}-{template.max_rr}\n"
                message += f"    Regime: {template.regime}\n\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Template listing failed: {e}")
        await update.message.reply_text(f"❌ Template listing failed: {e}")

async def router_validate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test prompt validator with sample data."""
    try:
        validator = create_prompt_validator()
        
        # Sample valid response
        valid_response = {
            "strategy": "trend_pullback",
            "order_type": "buy_stop",
            "entry": 1950.0,
            "sl": 1945.0,
            "tp": 1960.0,
            "rr": 2.0,
            "confidence": {
                "overall": 75,
                "trend": 80,
                "pattern": 70,
                "volume": 75,
                "regime_fit": 85
            },
            "rationale": "Strong uptrend with pullback to EMA20",
            "tags": ["EMA_align", "ADX>20", "trend_pullback"]
        }
        
        # Sample invalid response
        invalid_response = {
            "strategy": "trend_pullback",
            "order_type": "buy_limit",  # Wrong order type
            "entry": 1950.0,
            "sl": 1955.0,  # Wrong SL logic
            "tp": 1960.0,
            "rr": 0.5,  # Too low RR
            "confidence": {
                "overall": 75
            },
            "rationale": "Test response"
        }
        
        # Test validation
        valid_result = validator.validate_response(valid_response, "trend_pullback", {})
        invalid_result = validator.validate_response(invalid_response, "trend_pullback", {})
        
        message = f"🔍 **Validator Test Results**\n\n"
        message += f"✅ **Valid Response:**\n"
        message += f"  • Valid: {valid_result.is_valid}\n"
        message += f"  • Score: {valid_result.validation_score:.1f}\n"
        message += f"  • Errors: {len(valid_result.errors)}\n"
        message += f"  • Warnings: {len(valid_result.warnings)}\n\n"
        
        message += f"❌ **Invalid Response:**\n"
        message += f"  • Valid: {invalid_result.is_valid}\n"
        message += f"  • Score: {invalid_result.validation_score:.1f}\n"
        message += f"  • Errors: {len(invalid_result.errors)}\n"
        message += f"  • Warnings: {len(invalid_result.warnings)}\n\n"
        
        if invalid_result.errors:
            message += f"🚨 **Errors Found:**\n"
            for error in invalid_result.errors[:3]:  # Show first 3 errors
                message += f"  • {error}\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Validator test failed: {e}")
        await update.message.reply_text(f"❌ Validator test failed: {e}")

def register_prompt_router_handlers(app):
    """Register prompt router command handlers."""
    try:
        from handlers.help import DESCRIPTIONS
        
        # Add command descriptions
        DESCRIPTIONS.update({
            "router_status": "Show prompt router status and configuration",
            "router_test": "Test prompt router with sample data",
            "router_templates": "List available prompt templates",
            "router_validate": "Test prompt validator with sample data"
        })
        
        # Register handlers
        app.add_handler(CommandHandler("router_status", router_status))
        app.add_handler(CommandHandler("router_test", router_test))
        app.add_handler(CommandHandler("router_templates", router_templates))
        app.add_handler(CommandHandler("router_validate", router_validate))
        
        logger.info("Prompt router handlers registered")
        
    except Exception as e:
        logger.error(f"Prompt router handler registration failed: {e}")
