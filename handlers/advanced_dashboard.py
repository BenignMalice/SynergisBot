"""
V8 Performance Dashboard Handler
================================

Telegram command handlers for viewing V8 feature performance,
importance scores, and analytics.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import sqlite3
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

DB_PATH = Path("data/advanced_analytics.sqlite")


async def advanced_dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /v8dashboard - Show V8 feature performance dashboard
    """
    try:
        if not DB_PATH.exists():
            await update.message.reply_text(
                "📊 **Advanced Analytics**\n\n"
                "⚠️ No data yet. Place some trades first!\n\n"
                "Advanced features will be tracked automatically for all trades."
            )
            return
        
        # Create inline keyboard with dashboard options
        keyboard = [
            [InlineKeyboardButton("📊 Feature Importance", callback_data="v8_importance")],
            [InlineKeyboardButton("🏆 Top Performing Features", callback_data="v8_top_features")],
            [InlineKeyboardButton("📈 Win Rate by Feature", callback_data="v8_win_rates")],
            [InlineKeyboardButton("💰 R-Multiple Analysis", callback_data="v8_r_analysis")],
            [InlineKeyboardButton("📉 Recent Trades", callback_data="v8_recent_trades")],
            [InlineKeyboardButton("⚙️ Feature Weights", callback_data="v8_weights")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Get summary stats
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Total trades
        cursor.execute("SELECT COUNT(*) FROM advanced_trade_features")
        total_trades = cursor.fetchone()[0]
        
        # Completed trades
        cursor.execute("SELECT COUNT(*) FROM advanced_trade_features WHERE outcome IN ('win', 'loss', 'breakeven')")
        completed_trades = cursor.fetchone()[0]
        
        # Win rate
        cursor.execute("SELECT COUNT(*) FROM advanced_trade_features WHERE outcome = 'win'")
        wins = cursor.fetchone()[0]
        win_rate = (wins / completed_trades * 100) if completed_trades > 0 else 0
        
        # Avg R-multiple
        cursor.execute("SELECT AVG(r_multiple) FROM advanced_trade_features WHERE outcome IN ('win', 'loss')")
        avg_r = cursor.fetchone()[0] or 0
        
        conn.close()
        
        message = (
            "📊 **V8 Performance Dashboard**\n\n"
            f"📈 Total Trades: {total_trades}\n"
            f"✅ Completed: {completed_trades}\n"
            f"🏆 Win Rate: {win_rate:.1f}%\n"
            f"💰 Avg R-Multiple: {avg_r:.2f}R\n\n"
            "Select an option below:"
        )
        
        await update.message.reply_text(message, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error showing Advanced dashboard: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def advanced_dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Advanced dashboard button callbacks"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    try:
        if action == "v8_importance":
            await _show_feature_importance(query)
        elif action == "v8_top_features":
            await _show_top_features(query)
        elif action == "v8_win_rates":
            await _show_win_rates(query)
        elif action == "v8_r_analysis":
            await _show_r_analysis(query)
        elif action == "v8_recent_trades":
            await _show_recent_trades(query)
        elif action == "v8_weights":
            await _show_feature_weights(query)
    except Exception as e:
        logger.error(f"Error handling Advanced dashboard callback: {e}", exc_info=True)
        await query.message.reply_text(f"❌ Error: {str(e)}")


async def _show_feature_importance(query):
    """Show feature importance scores"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT feature_name, importance_score, win_rate, total_trades
        FROM advanced_feature_importance
        ORDER BY importance_score DESC
        LIMIT 10
    """)
    
    features = cursor.fetchall()
    conn.close()
    
    if not features:
        await query.message.reply_text("⚠️ No feature importance data yet. Need at least 10 completed trades.")
        return
    
    message = "📊 **Feature Importance Scores**\n\n"
    message += "Higher score = more predictive of success\n\n"
    
    for i, (name, importance, win_rate, total) in enumerate(features, 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        message += f"{emoji} **{name.replace('_', ' ').title()}**\n"
        message += f"   Score: {importance:.1f}/100 | Win Rate: {win_rate:.1f}% ({total} trades)\n\n"
    
    await query.message.reply_text(message)


async def _show_top_features(query):
    """Show top performing features by win rate"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT feature_name, win_rate, total_trades, avg_r_when_present
        FROM advanced_feature_importance
        WHERE total_trades >= 5
        ORDER BY win_rate DESC
        LIMIT 10
    """)
    
    features = cursor.fetchall()
    conn.close()
    
    if not features:
        await query.message.reply_text("⚠️ Insufficient data. Need at least 5 trades per feature.")
        return
    
    message = "🏆 **Top Performing Features**\n\n"
    
    for i, (name, win_rate, total, avg_r) in enumerate(features, 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        message += f"{emoji} **{name.replace('_', ' ').title()}**\n"
        message += f"   Win Rate: {win_rate:.1f}% | Avg R: {avg_r:.2f}R | Trades: {total}\n\n"
    
    await query.message.reply_text(message)


async def _show_win_rates(query):
    """Show win rates by feature presence"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT feature_name, win_rate, avg_r_when_present, avg_r_when_absent, total_trades
        FROM advanced_feature_importance
        WHERE total_trades >= 5
        ORDER BY (avg_r_when_present - avg_r_when_absent) DESC
        LIMIT 8
    """)
    
    features = cursor.fetchall()
    conn.close()
    
    if not features:
        await query.message.reply_text("⚠️ Insufficient data.")
        return
    
    message = "📈 **Win Rate Impact Analysis**\n\n"
    message += "How features affect trade outcomes:\n\n"
    
    for name, win_rate, r_present, r_absent, total in features:
        r_diff = r_present - r_absent
        impact = "🟢" if r_diff > 0 else "🔴"
        
        message += f"{impact} **{name.replace('_', ' ').title()}**\n"
        message += f"   When present: {r_present:.2f}R | When absent: {r_absent:.2f}R\n"
        message += f"   Impact: {r_diff:+.2f}R | Win rate: {win_rate:.1f}%\n\n"
    
    await query.message.reply_text(message)


async def _show_r_analysis(query):
    """Show R-multiple distribution analysis"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Overall stats
    cursor.execute("""
        SELECT 
            AVG(r_multiple) as avg_r,
            MIN(r_multiple) as min_r,
            MAX(r_multiple) as max_r,
            COUNT(*) as total
        FROM advanced_trade_features
        WHERE outcome IN ('win', 'loss')
    """)
    
    avg_r, min_r, max_r, total = cursor.fetchone()
    
    # Distribution
    cursor.execute("""
        SELECT 
            CASE 
                WHEN r_multiple >= 2.0 THEN '2R+'
                WHEN r_multiple >= 1.0 THEN '1-2R'
                WHEN r_multiple >= 0 THEN '0-1R'
                ELSE 'Loss'
            END as bucket,
            COUNT(*) as count
        FROM advanced_trade_features
        WHERE outcome IN ('win', 'loss')
        GROUP BY bucket
        ORDER BY 
            CASE bucket
                WHEN '2R+' THEN 1
                WHEN '1-2R' THEN 2
                WHEN '0-1R' THEN 3
                ELSE 4
            END
    """)
    
    distribution = cursor.fetchall()
    conn.close()
    
    message = "💰 **R-Multiple Analysis**\n\n"
    message += f"📊 Overall Stats:\n"
    message += f"   Average: {avg_r:.2f}R\n"
    message += f"   Best: {max_r:.2f}R\n"
    message += f"   Worst: {min_r:.2f}R\n"
    message += f"   Total: {total} trades\n\n"
    message += f"📈 Distribution:\n"
    
    for bucket, count in distribution:
        pct = (count / total * 100) if total > 0 else 0
        bar = "█" * int(pct / 5)
        message += f"   {bucket}: {count} ({pct:.1f}%) {bar}\n"
    
    await query.message.reply_text(message)


async def _show_recent_trades(query):
    """Show recent trades with Advanced features"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            ticket, symbol, direction, outcome, r_multiple,
            mtf_total, vol_trend_state, pressure_ratio
        FROM advanced_trade_features
        ORDER BY timestamp DESC
        LIMIT 10
    """)
    
    trades = cursor.fetchall()
    conn.close()
    
    if not trades:
        await query.message.reply_text("⚠️ No trades recorded yet.")
        return
    
    message = "📉 **Recent Trades**\n\n"
    
    for ticket, symbol, direction, outcome, r_mult, mtf, vol_state, pressure in trades:
        outcome_emoji = "✅" if outcome == "win" else "❌" if outcome == "loss" else "⚪" if outcome == "breakeven" else "🔄"
        dir_emoji = "🟢" if direction == "BUY" else "🔴"
        
        message += f"{outcome_emoji} #{ticket} {dir_emoji} {symbol}\n"
        if outcome != "open":
            message += f"   Outcome: {outcome} ({r_mult:.2f}R)\n"
        message += f"   MTF: {mtf or 0}/3 | Vol: {vol_state or 'N/A'}\n\n"
    
    await query.message.reply_text(message)


async def _show_feature_weights(query):
    """Show current feature weights used in risk model"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT feature_name, weight, importance_score, total_trades
        FROM advanced_feature_importance
        ORDER BY weight DESC
        LIMIT 11
    """)
    
    features = cursor.fetchall()
    conn.close()
    
    if not features:
        await query.message.reply_text("⚠️ No feature weights calculated yet.")
        return
    
    message = "⚙️ **Feature Weights**\n\n"
    message += "Current weights used in adaptive risk model:\n\n"
    
    for name, weight, importance, total in features:
        impact = "🔼" if weight > 1.0 else "🔽" if weight < 1.0 else "➡️"
        message += f"{impact} **{name.replace('_', ' ').title()}**\n"
        message += f"   Weight: {weight:.2f}x | Importance: {importance:.1f}/100\n"
        message += f"   Based on {total} trades\n\n"
    
    message += "\n💡 *Weight > 1.0 = increases risk*\n"
    message += "*Weight < 1.0 = decreases risk*"
    
    await query.message.reply_text(message)


# Export handlers
__all__ = ['advanced_dashboard_command', 'advanced_dashboard_callback']

