"""
Feature Builder Handler
Provides Telegram commands for testing and managing the feature builder
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

from infra.feature_builder import build_features
from infra.mt5_service import MT5Service
from infra.indicator_bridge import IndicatorBridge
from config import settings

logger = logging.getLogger(__name__)

async def feature_test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test the feature builder with a specific symbol."""
    chat_id = update.effective_chat.id
    
    try:
        # Get symbol from command args
        if not context.args:
            await update.message.reply_text("Usage: /feature_test <symbol>\nExample: /feature_test XAUUSDc")
            return
        
        symbol = context.args[0].upper()
        
        await update.message.reply_text(f"🔍 Testing feature builder for {symbol}...")
        
        # Initialize services
        mt5svc = MT5Service()
        mt5svc.connect()
        bridge = IndicatorBridge(settings.MT5_FILES_DIR)
        
        # Build features
        features = build_features(symbol, mt5svc, bridge)
        
        if not features or features.get("symbol") != symbol:
            await update.message.reply_text(f"❌ Failed to build features for {symbol}")
            return
        
        # Format response
        response = f"✅ *Feature Builder Test - {symbol}*\n\n"
        
        # Show timeframe summary
        timeframes = ["M5", "M15", "M30", "H1", "H4"]
        for tf in timeframes:
            if tf in features:
                tf_data = features[tf]
                bars_count = tf_data.get("bars_count", 0)
                trend_state = tf_data.get("trend_state", "unknown")
                rsi = tf_data.get("rsi_14", 0)
                adx = tf_data.get("adx", 0)
                
                response += f"📊 *{tf}:* {bars_count} bars, {trend_state} trend, RSI: {rsi:.1f}, ADX: {adx:.1f}\n"
        
        # Show cross-timeframe analysis
        cross_tf = features.get("cross_tf", {})
        if cross_tf:
            response += f"\n🔄 *Cross-Timeframe Analysis:*\n"
            response += f"Trend Agreement: {cross_tf.get('trend_agreement', 0):.1%}\n"
            response += f"Trend Consensus: {cross_tf.get('trend_consensus', 'unknown')}\n"
            response += f"Vol Regime: {cross_tf.get('vol_regime_consensus', 'unknown')}\n"
            response += f"RSI Confluence: {cross_tf.get('rsi_confluence', 0):.1%}\n"
        
        # Show pattern summary
        m5_data = features.get("M5", {})
        pattern_flags = m5_data.get("pattern_flags", {})
        if pattern_flags:
            active_patterns = [k for k, v in pattern_flags.items() if v]
            if active_patterns:
                response += f"\n🎯 *Active Patterns (M5):* {', '.join(active_patterns[:5])}\n"
        
        # Show session info
        session = m5_data.get("session", "unknown")
        news_blackout = m5_data.get("news_blackout", False)
        response += f"\n⏰ *Session:* {session}\n"
        response += f"News Blackout: {'Yes' if news_blackout else 'No'}\n"
        
        await update.message.reply_text(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Feature test command failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def feature_compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Compare features across multiple symbols."""
    chat_id = update.effective_chat.id
    
    try:
        # Get symbols from command args
        if not context.args:
            await update.message.reply_text("Usage: /feature_compare <symbol1> <symbol2> [symbol3]...\nExample: /feature_compare XAUUSDc BTCUSDc EURUSDc")
            return
        
        symbols = [s.upper() for s in context.args[:5]]  # Limit to 5 symbols
        
        await update.message.reply_text(f"🔍 Comparing features for {', '.join(symbols)}...")
        
        # Initialize services
        mt5svc = MT5Service()
        mt5svc.connect()
        bridge = IndicatorBridge(settings.MT5_FILES_DIR)
        
        # Build features for each symbol
        all_features = {}
        for symbol in symbols:
            features = build_features(symbol, mt5svc, bridge)
            if features and features.get("symbol") == symbol:
                all_features[symbol] = features
        
        if not all_features:
            await update.message.reply_text("❌ Failed to build features for any symbol")
            return
        
        # Format comparison table
        response = f"📊 *Feature Comparison*\n\n"
        
        # Header
        response += "| Symbol | Trend | RSI | ADX | Vol | Session |\n"
        response += "|--------|-------|-----|-----|-----|----------|\n"
        
        # Data rows
        for symbol, features in all_features.items():
            m5_data = features.get("M5", {})
            trend = m5_data.get("trend_state", "unknown")
            rsi = m5_data.get("rsi_14", 0)
            adx = m5_data.get("adx", 0)
            vol_regime = m5_data.get("vol_regime", "normal")
            session = m5_data.get("session", "unknown")
            
            response += f"| {symbol} | {trend} | {rsi:.1f} | {adx:.1f} | {vol_regime} | {session} |\n"
        
        # Cross-timeframe analysis
        response += f"\n🔄 *Cross-Timeframe Analysis:*\n"
        for symbol, features in all_features.items():
            cross_tf = features.get("cross_tf", {})
            trend_agreement = cross_tf.get("trend_agreement", 0)
            trend_consensus = cross_tf.get("trend_consensus", "unknown")
            response += f"{symbol}: {trend_consensus} ({trend_agreement:.1%} agreement)\n"
        
        await update.message.reply_text(response, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Feature compare command failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def feature_export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export features to JSON for analysis."""
    chat_id = update.effective_chat.id
    
    try:
        # Get symbol from command args
        if not context.args:
            await update.message.reply_text("Usage: /feature_export <symbol>\nExample: /feature_export XAUUSDc")
            return
        
        symbol = context.args[0].upper()
        
        await update.message.reply_text(f"📤 Exporting features for {symbol}...")
        
        # Initialize services
        mt5svc = MT5Service()
        mt5svc.connect()
        bridge = IndicatorBridge(settings.MT5_FILES_DIR)
        
        # Build features
        features = build_features(symbol, mt5svc, bridge)
        
        if not features or features.get("symbol") != symbol:
            await update.message.reply_text(f"❌ Failed to build features for {symbol}")
            return
        
        # Save to file
        import json
        from datetime import datetime
        
        filename = f"features_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = f"data/{filename}"
        
        # Ensure data directory exists
        import os
        os.makedirs("data", exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(features, f, indent=2, default=str)
        
        await update.message.reply_text(f"✅ Features exported to {filename}\n\n📁 File saved in data/ directory")
        
    except Exception as e:
        logger.error(f"Feature export command failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def feature_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show feature builder help."""
    help_text = """
🔧 *Feature Builder Commands*

*Core Commands:*
• `/feature_test <symbol>` - Test feature builder for a symbol
• `/feature_compare <symbol1> <symbol2>...` - Compare features across symbols
• `/feature_export <symbol>` - Export features to JSON file

*Examples:*
• `/feature_test XAUUSDc`
• `/feature_compare XAUUSDc BTCUSDc EURUSDc`
• `/feature_export XAUUSDc`

*What the Feature Builder Provides:*
📊 *Indicators:* EMA, RSI, MACD, ATR, Bollinger Bands, VWAP
🎯 *Patterns:* Candlestick patterns, multi-bar patterns
🏗️ *Structure:* Swing points, S/R levels, ranges, pivots
⚡ *Microstructure:* Spread, slippage, volume analysis
⏰ *Session/News:* Trading sessions, news timing

*Timeframes:* M5, M15, M30, H1, H4
*Cross-TF Analysis:* Trend agreement, momentum confluence, volatility regime

The feature builder provides clean, normalized data for AI analysis without opinions or decisions.
    """
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

def register_feature_builder_handlers(app: Application):
    """Register feature builder command handlers."""
    app.add_handler(CommandHandler("feature_test", feature_test_command))
    app.add_handler(CommandHandler("feature_compare", feature_compare_command))
    app.add_handler(CommandHandler("feature_export", feature_export_command))
    app.add_handler(CommandHandler("feature_help", feature_help_command))
