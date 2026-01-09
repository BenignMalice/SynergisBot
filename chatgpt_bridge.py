"""
ChatGPT Bridge Handler
======================

Allows users to interact with ChatGPT directly from Telegram.
ChatGPT can analyze markets, execute trades, and provide insights using its API access.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler
)
import httpx
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Conversation states
CHATTING = 1

# Store conversation history per user
user_conversations = {}

# Import logging infrastructure
try:
    from infra.chatgpt_logger import ChatGPTLogger
    from infra.analytics_logger import AnalyticsLogger
    chatgpt_logger = ChatGPTLogger()
    analytics_logger = AnalyticsLogger()
    logger.info("✅ ChatGPT logging infrastructure loaded")
except Exception as e:
    logger.warning(f"⚠️ Could not load logging infrastructure: {e}")
    chatgpt_logger = None
    analytics_logger = None


def escape_markdown_v2(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2.
    For safe text display, we'll escape ALL special characters.
    """
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


# Helper functions to execute tool calls
async def execute_get_market_data(symbol: str) -> dict:
    """Fetch market data and technical analysis from API"""
    try:
        # Don't normalize here - API handles it
        symbol = symbol.upper()
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Get price
            price_response = await client.get(f"http://localhost:8000/api/v1/price/{symbol}")
            price_data = price_response.json() if price_response.status_code == 200 else {}
            
            # Get technical analysis
            analysis_response = await client.get(f"http://localhost:8000/ai/analysis/{symbol}")
            analysis_data = analysis_response.json() if analysis_response.status_code == 200 else {}
        
        # Combine the data
        result = {
            "symbol": symbol,
            "current_price": price_data.get("mid", 0),
            "bid": price_data.get("bid", 0),
            "ask": price_data.get("ask", 0),
            "spread": price_data.get("spread", 0),
        }
        
        if analysis_data:
            tech = analysis_data.get("technical_analysis", {})
            indicators = tech.get("indicators", {})
            result.update({
                "rsi": indicators.get("rsi", 50),
                "adx": indicators.get("adx", 0),
                "ema20": indicators.get("ema20", 0),
                "ema50": indicators.get("ema50", 0),
                "ema200": indicators.get("ema200", 0),
                "atr14": indicators.get("atr14", 0),
                "market_regime": tech.get("market_regime", "UNKNOWN"),
                "recommendation": tech.get("trade_recommendation", {}).get("direction", "HOLD")
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching market data: {e}", exc_info=True)
        return {"error": str(e)}


async def execute_get_account_balance() -> dict:
    """Fetch MT5 account balance from API"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8000/api/v1/account")
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API returned {response.status_code}"}
            
    except Exception as e:
        logger.error(f"Error fetching account balance: {e}", exc_info=True)
        return {"error": str(e)}


async def execute_trade(
    symbol: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    order_type: str = "market",
    reasoning: str = "ChatGPT recommendation"
) -> dict:
    """Execute a trade via MT5 API"""
    try:
        # Prepare trade signal
        trade_data = {
            "symbol": symbol,
            "timeframe": "H1",  # Default timeframe
            "direction": direction.lower(),
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "order_type": order_type.lower(),
            "confidence": 75,
            "reasoning": reasoning
        }
        
        logger.info(f"Executing trade via API: {trade_data}")
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "http://localhost:8000/mt5/execute",
                json=trade_data
            )
        
        if response.status_code == 200:
            result = response.json()
            return {
                "success": True,
                "message": f"Trade executed successfully! Ticket: {result.get('ticket', 'N/A')}",
                "details": result
            }
        else:
            error_text = response.text
            logger.error(f"Trade execution failed: {response.status_code} - {error_text}")
            return {
                "success": False,
                "error": f"Execution failed: {response.status_code}",
                "details": error_text
            }
            
    except Exception as e:
        logger.error(f"Error executing trade: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def chatgpt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a ChatGPT conversation"""
    logger.info(f"🎯 ChatGPT start called by user {update.effective_user.id}")
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Initialize conversation
    user_conversations[user_id] = {
        "messages": [],
        "started_at": datetime.now().isoformat(),
        "chat_id": chat_id,
        "conversation_id": None  # Will be set after DB logging
    }
    
    # Log conversation start to database
    if chatgpt_logger:
        try:
            conv_id = chatgpt_logger.start_conversation(user_id, chat_id)
            user_conversations[user_id]["conversation_id"] = conv_id
            logger.info(f"✅ Conversation {conv_id} started for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to log conversation start: {e}")
    else:
        logger.info(f"✅ Conversation initialized for user {user_id} (DB logging disabled)")
    
    # Log analytics event
    if analytics_logger:
        try:
            analytics_logger.log_action(user_id, chat_id, "chatgpt_start")
        except Exception as e:
            logger.error(f"Failed to log analytics: {e}")
    
    keyboard = [
        [InlineKeyboardButton("📊 Analyze Market", callback_data="gpt_analyze")],
        [InlineKeyboardButton("💰 Check Balance", callback_data="gpt_balance")],
        [InlineKeyboardButton("📈 Get Recommendation", callback_data="gpt_recommend")],
        [InlineKeyboardButton("🎯 Place Trade", callback_data="gpt_trade")],
        [InlineKeyboardButton("❌ End Chat", callback_data="gpt_end")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 **ChatGPT Trading Assistant**\n\n"
        "I can help you with:\n"
        "• Market analysis\n"
        "• Trade recommendations\n"
        "• Placing trades on MT5\n"
        "• Checking account status\n"
        "• OCO bracket trades\n\n"
        "Just type your message or use the buttons below.\n"
        "Type /endgpt to end the conversation.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    return CHATTING


async def chatgpt_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages to ChatGPT"""
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Check if conversation exists
    if user_id not in user_conversations:
        await update.message.reply_text(
            "⚠️ No active ChatGPT session. Use /chatgpt to start."
        )
        return ConversationHandler.END
    
    # Add user message to history
    user_conversations[user_id]["messages"].append({
        "role": "user",
        "content": user_message,
        "timestamp": datetime.now().isoformat()
    })
    
    # Log user message to database
    if chatgpt_logger:
        try:
            conv_id = user_conversations[user_id].get("conversation_id")
            if conv_id:
                chatgpt_logger.log_message(conv_id, "user", user_message)
        except Exception as e:
            logger.error(f"Failed to log user message: {e}")
    
    # Send "typing" indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        # Pre-fetch data if user is asking about market analysis
        context_data = ""
        user_msg_lower = user_message.lower()
        
        # Check if user wants to PLAN (not execute)
        is_planning = any(word in user_msg_lower for word in ["plan", "setup", "prepare", "set up", "pending"])
        
        if any(word in user_msg_lower for word in ["analyze", "analysis", "price", "market", "xauusd", "btcusd", "recommend", "trade", "setup"]):
            # Fetch current market data
            try:
                await update.message.reply_text("📊 Fetching current market data...")
                
                # Detect symbol (default XAUUSD)
                symbol = "XAUUSD"
                if "btc" in user_msg_lower:
                    symbol = "BTCUSD"
                elif "xau" in user_msg_lower or "gold" in user_msg_lower:
                    symbol = "XAUUSD"
                
                market_data = await execute_get_market_data(symbol)
                
                context_data = (
                    f"\n\n[CURRENT MARKET DATA FOR {symbol}]\n"
                    f"Current Price: ${market_data.get('current_price', 0):.2f}\n"
                    f"Bid: ${market_data.get('bid', 0):.2f}\n"
                    f"Ask: ${market_data.get('ask', 0):.2f}\n"
                    f"RSI: {market_data.get('rsi', 50):.1f}\n"
                    f"ADX: {market_data.get('adx', 0):.1f}\n"
                    f"EMA20: ${market_data.get('ema20', 0):.2f}\n"
                    f"EMA50: ${market_data.get('ema50', 0):.2f}\n"
                    f"EMA200: ${market_data.get('ema200', 0):.2f}\n"
                    f"ATR14: {market_data.get('atr14', 0):.2f}\n"
                    f"Market Regime: {market_data.get('market_regime', 'UNKNOWN')}\n"
                    f"Technical Recommendation: {market_data.get('recommendation', 'HOLD')}\n"
                    f"[END MARKET DATA]\n\n"
                    f"Use these ACTUAL numbers in your analysis. Do not make up numbers."
                )
            except Exception as e:
                logger.error(f"Error pre-fetching market data: {e}", exc_info=True)
        
        if "balance" in user_msg_lower or "account" in user_msg_lower:
            # Fetch account data
            try:
                await update.message.reply_text("💰 Fetching account info...")
                account_data = await execute_get_account_balance()
                
                context_data += (
                    f"\n\n[CURRENT ACCOUNT INFO]\n"
                    f"Balance: ${account_data.get('balance', 0):.2f}\n"
                    f"Equity: ${account_data.get('equity', 0):.2f}\n"
                    f"Free Margin: ${account_data.get('free_margin', 0):.2f}\n"
                    f"Currency: {account_data.get('currency', 'USD')}\n"
                    f"[END ACCOUNT INFO]\n"
                )
            except Exception as e:
                logger.error(f"Error pre-fetching account data: {e}", exc_info=True)
        
        # Get ChatGPT API URL from settings
        api_url = context.bot_data.get("chatgpt_api_url", "https://api.openai.com/v1/chat/completions")
        api_key = context.bot_data.get("openai_api_key")
        
        if not api_key:
            await update.message.reply_text(
                "⚠️ OpenAI API key not configured. Set it with /setgptkey <your-key>"
            )
            return CHATTING
        
        # Build conversation history with dynamic system prompt
        if is_planning:
            system_content = (
                "You are a professional forex trading assistant with direct access to MT5 data.\n\n"
                "CRITICAL: The user wants to PLAN a trade, NOT execute it immediately.\n\n"
                "DO NOT call execute_trade() function under any circumstances.\n"
                "Instead, provide PENDING ORDER recommendations:\n"
                "• For SELL trades above current price → SELL LIMIT\n"
                "• For SELL trades below current price → SELL STOP\n"
                "• For BUY trades below current price → BUY LIMIT\n"
                "• For BUY trades above current price → BUY STOP\n\n"
                "Format like:\n"
                "🔴 **SELL LIMIT XAUUSD** (pending order, not executed)\n"
                "📊 Entry: $3,890.00 (wait for price to reach this level)\n"
                "🛑 SL: $3,900.00\n"
                "🎯 TP: $3,870.00\n"
                "💡 Reason: RSI overbought, wait for retest of resistance\n\n"
                "Tell the user to say 'execute' or 'place it now' when ready.\n"
                "Use emojis: 🟢=BUY 🔴=SELL 📊=Entry 🛑=SL 🎯=TP"
            )
        else:
            system_content = (
                "You are a trading assistant with API access to MT5.\n\n"
                "🚨 CRITICAL: When user says 'execute', 'place', 'enter', 'go ahead', 'do it now':\n"
                "→ YOU MUST CALL execute_trade() function IMMEDIATELY\n"
                "→ DO NOT just describe executing - ACTUALLY CALL THE FUNCTION\n"
                "→ DO NOT say 'Executing now...' without calling execute_trade()\n"
                "→ If you say 'Executing the trade...' you MUST have called execute_trade() first\n\n"
                "IMPORTANT: When users ask about market analysis, prices, or account info:\n"
                "1. ALWAYS use the get_market_data function to fetch REAL current data\n"
                "2. ALWAYS use the get_account_balance function for account info\n"
                "3. Use the ACTUAL numbers from these functions in your response\n"
                "4. ALWAYS clearly state if it's a 🟢 BUY or 🔴 SELL trade\n"
                "5. Provide specific entry, SL, and TP levels with emojis\n\n"
                "TRADE EXECUTION RULES:\n"
                "• When user says 'place it now', 'execute now', 'enter now', 'execute', 'place it', 'proceed' → IMMEDIATELY call execute_trade() with order_type='market'\n"
                "  → First call get_market_data() to get CURRENT PRICE\n"
                "  → Use that current price as entry_price\n"
                "  → Use the SAME symbol from the previous trade recommendation\n"
                "  → DO NOT ask for confirmation, just execute\n"
                "• When user says 'place pending', 'place the pending', 'set pending', 'execute pending', 'place pending trade', 'proceed with pending' → YOU MUST call execute_trade() with:\n"
                "  → Use the SAME symbol, entry, SL, TP from your PREVIOUS recommendation\n"
                "  → For SELL above current price: order_type='sell_limit'\n"
                "  → For SELL below current price: order_type='sell_stop'\n"
                "  → For BUY below current price: order_type='buy_limit'\n"
                "  → For BUY above current price: order_type='buy_stop'\n"
                "  → Use the PLANNED pending order price as entry_price (from your previous message)\n"
                "  → DO NOT fetch new data, DO NOT create new plan, just execute what you already recommended\n"
                "  → DO NOT ask for confirmation, DO NOT refuse, just execute\n"
                "• MANDATORY: When user says any form of 'place' or 'execute', you MUST call execute_trade() IMMEDIATELY\n"
                "• DO NOT SAY 'I cannot execute trades' - YOU CAN! You have the execute_trade() function!\n"
                "• NEVER tell user to place order manually - YOU must place it via execute_trade()\n"
                "• Example: You said 'SELL LIMIT BTCUSD at $123,150', user says 'place pending' → CALL execute_trade(symbol='BTCUSD', direction='sell', entry_price=123150, stop_loss=123300, take_profit=122800, order_type='sell_limit', reasoning='RSI overbought')\n\n"
                "Format trade recommendations like:\n"
                "🔴 **SELL XAUUSD** (market order)\n"
                "📊 Entry: $3,881.43 (current price)\n"
                "🛑 SL: $3,891.00\n"
                "🎯 TP: $3,870.00\n"
                "💡 Reason: RSI 76.29 (overbought), ADX 58.11 (strong trend)\n\n"
                "📋 **Detailed Explanation:**\n"
                "• **Market Context:** Explain the current market regime (trending/ranging), session, and overall direction\n"
                "• **Technical Setup:** Describe the key indicators supporting this trade (RSI, ADX, EMAs, ATR)\n"
                "• **Entry Logic:** Explain WHY this entry price makes sense (support/resistance, retest, breakout)\n"
                "• **Risk Management:** Explain SL placement (structure-based, ATR-based) and TP target (next level, R:R ratio)\n"
                "• **Timing:** Why trade NOW vs waiting (momentum, news, session timing)\n\n"
                "Use emojis: 🟢=BUY 🔴=SELL 📊=Entry 🛑=SL 🎯=TP 💰=Money 📈=Up 📉=Down ⚠️=Warning 📋=Explanation\n\n"
                "Never give generic or placeholder analysis. Always fetch and use real data."
            )
        
        messages = [
            {
                "role": "system",
                "content": system_content
            }
        ]
        
        # Add conversation history (last 10 messages to avoid token limits)
        for i, msg in enumerate(user_conversations[user_id]["messages"][-10:]):
            content = msg["content"]
            # Add context data to the latest user message
            if i == len(user_conversations[user_id]["messages"][-10:]) - 1 and msg["role"] == "user" and context_data:
                content = content + context_data
            
            messages.append({
                "role": msg["role"],
                "content": content
            })
        
        # Define tools (functions) ChatGPT can call
        # If planning, exclude execute_trade tool
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_market_data",
                    "description": "Get current market price and technical analysis for a symbol",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Trading symbol (e.g., XAUUSD, BTCUSD)"
                            }
                        },
                        "required": ["symbol"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_account_balance",
                    "description": "Get MT5 account balance, equity, and margin information",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            }
        ]
        
        # Only add execute_trade tool if NOT planning
        if not is_planning:
            tools.append({
                "type": "function",
                "function": {
                    "name": "execute_trade",
                    "description": "REQUIRED: Execute a trade in MT5. You MUST call this when user says 'execute', 'place', 'enter', 'go ahead', 'do it', 'proceed'. DO NOT just say you're executing - CALL THIS FUNCTION. If you tell the user you're executing a trade, you MUST call this function first.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "Trading symbol (e.g., XAUUSD, BTCUSD)"
                            },
                            "direction": {
                                "type": "string",
                                "enum": ["buy", "sell"],
                                "description": "Trade direction: buy or sell"
                            },
                            "entry_price": {
                                "type": "number",
                                "description": "Entry price for the trade"
                            },
                            "stop_loss": {
                                "type": "number",
                                "description": "Stop loss price"
                            },
                            "take_profit": {
                                "type": "number",
                                "description": "Take profit price"
                            },
                            "order_type": {
                                "type": "string",
                                "enum": ["market", "buy_limit", "sell_limit", "buy_stop", "sell_stop"],
                                "description": "Order type: market (immediate), buy_limit (below price), sell_limit (above price), buy_stop (above price), sell_stop (below price)"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Reason for the trade"
                            }
                        },
                        "required": ["symbol", "direction", "entry_price", "stop_loss", "take_profit"]
                    }
                }
            })
        
        # Call OpenAI API with tools
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "temperature": 0.7,
                    "max_tokens": 500
                }
            )
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"ChatGPT API error: {response.status_code} - {error_text}")
            await update.message.reply_text(
                f"⚠️ ChatGPT API error: {response.status_code}\n{error_text[:200]}"
            )
            return CHATTING
        
        # Extract response
        result = response.json()
        assistant_msg = result["choices"][0]["message"]
        
        # Log the full response for debugging
        logger.info(f"ChatGPT response: {json.dumps(assistant_msg, indent=2)}")
        
        # Check if ChatGPT wants to call a function
        tool_calls = assistant_msg.get("tool_calls")
        # Track whether the initial response included tool calls. We use this flag later
        # to determine if we should attempt inline trade execution parsing.
        had_tool_call = bool(tool_calls)

        if tool_calls:
            logger.info(f"✅ ChatGPT is calling {len(tool_calls)} function(s)")
        else:
            logger.info("ℹ️ ChatGPT returned text response (no function calls)")
        
        if tool_calls:
            # ChatGPT wants to call a function - execute it
            await update.message.reply_text("🔄 Fetching data...")
            
            # Add assistant's tool call message ONCE before processing
            messages.append(assistant_msg)
            
            for tool_call in tool_calls:
                function_name = tool_call["function"]["name"]
                function_args = json.loads(tool_call["function"]["arguments"])
                
                logger.info(f"ChatGPT calling function: {function_name} with args: {function_args}")
                
                # Execute the function
                if function_name == "get_market_data":
                    symbol = function_args.get("symbol", "XAUUSD")
                    await update.message.reply_text(f"📊 Getting {symbol} market data...")
                    function_result = await execute_get_market_data(symbol)
                elif function_name == "get_account_balance":
                    await update.message.reply_text("💰 Getting account balance...")
                    function_result = await execute_get_account_balance()
                elif function_name == "execute_trade":
                    await update.message.reply_text("🔄 Executing trade...")
                    function_result = await execute_trade(
                        symbol=function_args.get("symbol"),
                        direction=function_args.get("direction"),
                        entry_price=function_args.get("entry_price"),
                        stop_loss=function_args.get("stop_loss"),
                        take_profit=function_args.get("take_profit"),
                        order_type=function_args.get("order_type", "market"),
                        reasoning=function_args.get("reasoning", "ChatGPT trade")
                    )
                else:
                    function_result = {"error": "Unknown function"}
                
                logger.info(f"Function result: {json.dumps(function_result, indent=2)}")
                
                # Add the function result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(function_result)
                })
            
            # Call ChatGPT again with the function results
            await update.message.reply_text("🤖 Processing results...")
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response2 = await client.post(
                        api_url,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "gpt-4o-mini",
                            "messages": messages,
                            "temperature": 0.7,
                            "max_tokens": 500
                        }
                    )
                
                if response2.status_code == 200:
                    result2 = response2.json()
                    assistant_message = result2["choices"][0]["message"]["content"]
                else:
                    logger.error(f"Second API call failed: {response2.status_code} - {response2.text}")
                    assistant_message = f"⚠️ Error processing function results: {response2.status_code}"
            except Exception as e2:
                logger.error(f"Second API call exception: {e2}", exc_info=True)
                assistant_message = f"⚠️ Error: {str(e2)}"
        else:
            # Normal text response
            assistant_message = assistant_msg.get("content", "No response")

        # ------------------------------------------------------------------
        # Inline trade execution fallback
        # If ChatGPT returns a normal text response (no tool calls), it may
        # include a code snippet calling execute_trade() instead of using
        # the OpenAI function-call mechanism. We detect such snippets and
        # execute the trade automatically. This prevents trades from being
        # missed when ChatGPT prints Python code instead of invoking the
        # function via tool_calls.
        if not had_tool_call and isinstance(assistant_message, str):
            try:
                executed = False
                # Extract Python code blocks (```python ...``` or ``` ... ```)
                code_blocks = re.findall(r"```(?:python)?\s*([\s\S]*?)```", assistant_message, re.IGNORECASE)
                for code in code_blocks:
                    try:
                        # Parse the code using ast to find function calls
                        tree = ast.parse(code)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "execute_trade":
                                kw_args = {}
                                for kw in node.keywords:
                                    kw_args[kw.arg] = ast.literal_eval(kw.value)
                                required = {"symbol", "direction", "entry_price", "stop_loss", "take_profit"}
                                if required.issubset(kw_args.keys()):
                                    logger.info(f"Executing trade from inline code block with args: {kw_args}")
                                    order_type = kw_args.get("order_type", "market")
                                    reasoning = kw_args.get("reasoning", "ChatGPT trade")
                                    trade_result = await execute_trade(
                                        symbol=kw_args["symbol"],
                                        direction=kw_args["direction"],
                                        entry_price=kw_args["entry_price"],
                                        stop_loss=kw_args["stop_loss"],
                                        take_profit=kw_args["take_profit"],
                                        order_type=order_type,
                                        reasoning=reasoning
                                    )
                                    # Prepend result to assistant message for clarity
                                    result_msg = (
                                        "✅ Executed trade from inline code:\n"
                                        f"{trade_result}\n\n"
                                    )
                                    assistant_message = result_msg + assistant_message
                                    executed = True
                                    break
                        if executed:
                            break
                    except Exception as parse_err:
                        # Skip code blocks that can't be parsed
                        logger.warning(f"Failed to parse code block for inline trade: {parse_err}")

                # Fallback: simple regex detection if no code blocks or trade not executed
                if not executed:
                    match = re.search(r"execute_trade\s*\((.*)\)", assistant_message, re.IGNORECASE | re.DOTALL)
                    if match:
                        args_str = match.group(1)
                        try:
                            dummy_expr = f"f({args_str})"
                            expr_ast = ast.parse(dummy_expr, mode="eval")
                            kw_args = {kw.arg: ast.literal_eval(kw.value) for kw in expr_ast.body.keywords}
                            required = {"symbol", "direction", "entry_price", "stop_loss", "take_profit"}
                            if required.issubset(kw_args.keys()):
                                logger.info(f"Executing trade from inline regex with args: {kw_args}")
                                order_type = kw_args.get("order_type", "market")
                                reasoning = kw_args.get("reasoning", "ChatGPT trade")
                                trade_result = await execute_trade(
                                    symbol=kw_args["symbol"],
                                    direction=kw_args["direction"],
                                    entry_price=kw_args["entry_price"],
                                    stop_loss=kw_args["stop_loss"],
                                    take_profit=kw_args["take_profit"],
                                    order_type=order_type,
                                    reasoning=reasoning
                                )
                                result_msg = (
                                    "✅ Executed trade from inline code:\n"
                                    f"{trade_result}\n\n"
                                )
                                assistant_message = result_msg + assistant_message
                        except Exception as regex_err:
                            logger.warning(f"Failed to parse inline execute_trade via regex: {regex_err}")
            except Exception as inline_err:
                logger.error(f"Error handling inline execute_trade: {inline_err}", exc_info=True)
        
        # Add assistant response to history
        user_conversations[user_id]["messages"].append({
            "role": "assistant",
            "content": assistant_message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Log assistant message to database
        if chatgpt_logger:
            try:
                conv_id = user_conversations[user_id].get("conversation_id")
                if conv_id:
                    # Count tokens (rough estimate)
                    tokens_used = len(assistant_message.split()) * 1.3
                    chatgpt_logger.log_message(conv_id, "assistant", assistant_message, int(tokens_used))
            except Exception as e:
                logger.error(f"Failed to log assistant message: {e}")
        
        # Send response to user (without Markdown to avoid parsing errors)
        await update.message.reply_text(
            f"🤖 ChatGPT:\n\n{assistant_message}"
        )
        
    except Exception as e:
        logger.error(f"ChatGPT bridge error: {e}", exc_info=True)
        await update.message.reply_text(
            f"⚠️ Error communicating with ChatGPT: {str(e)}"
        )
    
    return CHATTING


async def chatgpt_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quick action buttons"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    action = query.data
    
    # Pre-filled prompts for common actions
    prompts = {
        "gpt_analyze": "Analyze the current XAUUSD market and give me a technical breakdown.",
        "gpt_balance": "What's my current MT5 account balance and equity?",
        "gpt_recommend": "Give me a trade recommendation for XAUUSD with entry, SL, and TP.",
        "gpt_trade": "I want to place a trade. What symbols are good right now?",
        "gpt_end": None
    }
    
    if action == "gpt_end":
        return await chatgpt_end(update, context)
    
    prompt = prompts.get(action)
    if not prompt:
        return CHATTING
    
    # Check if conversation exists
    if user_id not in user_conversations:
        await query.message.reply_text(
            "⚠️ No active ChatGPT session. Use /chatgpt to start."
        )
        return ConversationHandler.END
    
    # Show what user "said"
    await query.message.reply_text(f"📝 You: {prompt}")
    
    # Add user message to history
    user_conversations[user_id]["messages"].append({
        "role": "user",
        "content": prompt,
        "timestamp": datetime.now().isoformat()
    })
    
    # Send "typing" indicator
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        # Pre-fetch data if needed
        context_data = ""
        prompt_lower = prompt.lower()
        
        if any(word in prompt_lower for word in ["analyze", "analysis", "price", "market", "xauusd", "btcusd", "recommend", "trade", "setup"]):
            # Fetch current market data
            try:
                await query.message.reply_text("📊 Fetching current market data...")
                
                # Detect symbol (default XAUUSD)
                symbol = "XAUUSD"
                if "btc" in prompt_lower:
                    symbol = "BTCUSD"
                elif "xau" in prompt_lower or "gold" in prompt_lower:
                    symbol = "XAUUSD"
                
                market_data = await execute_get_market_data(symbol)
                
                context_data = (
                    f"\n\n[CURRENT MARKET DATA FOR {symbol}]\n"
                    f"Current Price: ${market_data.get('current_price', 0):.2f}\n"
                    f"Bid: ${market_data.get('bid', 0):.2f}\n"
                    f"Ask: ${market_data.get('ask', 0):.2f}\n"
                    f"RSI: {market_data.get('rsi', 50):.1f}\n"
                    f"ADX: {market_data.get('adx', 0):.1f}\n"
                    f"EMA20: ${market_data.get('ema20', 0):.2f}\n"
                    f"EMA50: ${market_data.get('ema50', 0):.2f}\n"
                    f"EMA200: ${market_data.get('ema200', 0):.2f}\n"
                    f"ATR14: {market_data.get('atr14', 0):.2f}\n"
                    f"Market Regime: {market_data.get('market_regime', 'UNKNOWN')}\n"
                    f"Technical Recommendation: {market_data.get('recommendation', 'HOLD')}\n"
                    f"[END MARKET DATA]\n\n"
                    f"Use these ACTUAL numbers in your analysis. Do not make up numbers."
                )
                
                # Append context to the last message
                user_conversations[user_id]["messages"][-1]["content"] += context_data
                
            except Exception as e:
                logger.error(f"Error pre-fetching market data: {e}", exc_info=True)
        
        if "balance" in prompt_lower or "account" in prompt_lower:
            # Fetch account data
            try:
                await query.message.reply_text("💰 Fetching account info...")
                account_data = await execute_get_account_balance()
                
                context_data += (
                    f"\n\n[CURRENT ACCOUNT INFO]\n"
                    f"Balance: ${account_data.get('balance', 0):.2f}\n"
                    f"Equity: ${account_data.get('equity', 0):.2f}\n"
                    f"Free Margin: ${account_data.get('free_margin', 0):.2f}\n"
                    f"Currency: {account_data.get('currency', 'USD')}\n"
                    f"[END ACCOUNT INFO]\n"
                )
                
                # Append context to the last message
                user_conversations[user_id]["messages"][-1]["content"] += context_data
                
            except Exception as e:
                logger.error(f"Error pre-fetching account data: {e}", exc_info=True)
        
        # Get ChatGPT API settings
        api_url = context.bot_data.get("chatgpt_api_url", "https://api.openai.com/v1/chat/completions")
        api_key = context.bot_data.get("openai_api_key")
        
        if not api_key:
            await query.message.reply_text(
                "⚠️ OpenAI API key not configured. Set it with /setgptkey <your-key>"
            )
            return CHATTING
        
        # Build conversation history
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a professional forex trading assistant integrated with MT5. "
                    "You have access to:\n"
                    "- Real-time market data via /api/v1/price/{symbol}\n"
                    "- Account information via /api/v1/account\n"
                    "- Trade execution via /mt5/execute or /mt5/execute_bracket\n"
                    "- OCO bracket trades for range-bound strategies\n"
                    "- Technical analysis via /ai/analysis/{symbol}\n\n"
                    "When users ask for trades, ALWAYS:\n"
                    "1. Clearly state if it's a 🟢 BUY or 🔴 SELL\n"
                    "2. Provide specific entry, SL, and TP with emojis\n"
                    "3. Ask for confirmation before executing\n\n"
                    "Format: 🟢 **BUY** or 🔴 **SELL** | 📊 Entry | 🛑 SL | 🎯 TP\n"
                    "Be concise and professional."
                )
            }
        ]
        
        # Add conversation history (last 10 messages)
        for msg in user_conversations[user_id]["messages"][-10:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Call OpenAI API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 500
                }
            )
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"ChatGPT API error: {response.status_code} - {error_text}")
            await query.message.reply_text(
                f"⚠️ ChatGPT API error: {response.status_code}\n{error_text[:200]}"
            )
            return CHATTING
        
        # Extract response
        result = response.json()
        assistant_message = result["choices"][0]["message"]["content"]
        
        # Add assistant response to history
        user_conversations[user_id]["messages"].append({
            "role": "assistant",
            "content": assistant_message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Send response to user (without Markdown to avoid parsing errors)
        await query.message.reply_text(
            f"🤖 ChatGPT:\n\n{assistant_message}"
        )
        
    except Exception as e:
        logger.error(f"ChatGPT button error: {e}", exc_info=True)
        await query.message.reply_text(
            f"⚠️ Error: {str(e)}"
        )
    
    return CHATTING


async def chatgpt_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End ChatGPT conversation"""
    user_id = update.effective_user.id
    
    if user_id in user_conversations:
        msg_count = len(user_conversations[user_id]["messages"])
        conv_id = user_conversations[user_id].get("conversation_id")
        
        # Log conversation end to database
        if chatgpt_logger and conv_id:
            try:
                chatgpt_logger.end_conversation(conv_id)
                logger.info(f"✅ Conversation {conv_id} ended for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to log conversation end: {e}")
        
        # Log analytics event
        if analytics_logger:
            try:
                chat_id = user_conversations[user_id].get("chat_id", update.effective_chat.id)
                analytics_logger.log_action(user_id, chat_id, "chatgpt_end", {"message_count": msg_count})
            except Exception as e:
                logger.error(f"Failed to log analytics: {e}")
        
        del user_conversations[user_id]
        
        text = (
            "👋 ChatGPT conversation ended.\n\n"
            f"Messages exchanged: {msg_count}\n"
            "Use /chatgpt to start a new conversation."
        )
    else:
        text = "No active ChatGPT session."
    
    if update.callback_query:
        await update.callback_query.message.reply_text(text)
    else:
        await update.message.reply_text(text)
    
    return ConversationHandler.END


async def chatgpt_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel ChatGPT conversation"""
    return await chatgpt_end(update, context)


async def set_gpt_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set OpenAI API key"""
    if not context.args:
        await update.message.reply_text(
            "Usage: /setgptkey <your-openai-api-key>\n\n"
            "⚠️ Your key will be stored in memory only (not saved to disk).\n\n"
            "Get your key at: https://platform.openai.com/api-keys"
        )
        return
    
    api_key = context.args[0]
    context.bot_data["openai_api_key"] = api_key
    
    # Test the key
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            test_response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Test"}],
                    "max_tokens": 5
                }
            )
            
            if test_response.status_code == 200:
                await update.message.reply_text(
                    "✅ OpenAI API key set and verified!\n\n"
                    "You can now use /chatgpt to start a conversation."
                )
            elif test_response.status_code == 401:
                await update.message.reply_text(
                    "❌ Invalid API key!\n\n"
                    "Please check your key and try again.\n"
                    "Get your key at: https://platform.openai.com/api-keys"
                )
            else:
                await update.message.reply_text(
                    f"⚠️ API key set, but verification returned: {test_response.status_code}\n\n"
                    "You can try /chatgpt anyway."
                )
    except Exception as e:
        logger.error(f"API key test failed: {e}", exc_info=True)
        await update.message.reply_text(
            f"⚠️ API key set, but test failed: {str(e)[:100]}\n\n"
            "You can try /chatgpt anyway."
        )


async def check_gpt_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check ChatGPT bridge status"""
    api_key = context.bot_data.get("openai_api_key")
    
    if api_key:
        masked_key = api_key[:7] + "..." + api_key[-4:] if len(api_key) > 11 else "***"
        status = f"✅ API key set: {masked_key}"
    else:
        status = "❌ No API key set. Use /setgptkey"
    
    active_convs = len(user_conversations)
    
    await update.message.reply_text(
        f"🤖 ChatGPT Bridge Status\n\n"
        f"{status}\n"
        f"Active conversations: {active_convs}\n\n"
        f"Model: gpt-4o-mini\n"
        f"Timeout: 30s\n"
        f"Max tokens: 500"
    )


async def test_chatgpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test if ChatGPT bridge is working"""
    await update.message.reply_text(
        "✅ ChatGPT bridge is loaded!\n\n"
        "Commands:\n"
        "• /chatgpt - Start conversation\n"
        "• /setgptkey <key> - Set API key\n"
        "• /gptstatus - Check status\n"
        "• /testchatgpt - This command"
    )


def register_chatgpt_handlers(application):
    """Register all ChatGPT bridge handlers"""
    
    try:
        # Simple test command first
        application.add_handler(CommandHandler("testchatgpt", test_chatgpt))
        logger.info("ChatGPT test command registered")
        
        # Conversation handler for ChatGPT
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("chatgpt", chatgpt_start)],
            states={
                CHATTING: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, chatgpt_message),
                    CallbackQueryHandler(chatgpt_button, pattern="^gpt_"),
                ],
            },
            fallbacks=[
                CommandHandler("endgpt", chatgpt_cancel),
                CallbackQueryHandler(chatgpt_end, pattern="^gpt_end$")
            ],
            name="chatgpt_conversation",
            persistent=False
        )
        
        application.add_handler(conv_handler)
        logger.info("ChatGPT conversation handler registered")
        
        application.add_handler(CommandHandler("setgptkey", set_gpt_key))
        application.add_handler(CommandHandler("gptstatus", check_gpt_status))
        
        logger.info("ChatGPT bridge handlers registered successfully")
        
    except Exception as e:
        logger.error(f"Failed to register ChatGPT handlers: {e}", exc_info=True)
        raise


async def setgptkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set OpenAI API key"""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: /setgptkey <your-openai-api-key>\n\n"
            "Example:\n"
            "/setgptkey sk-proj-abc123...\n\n"
            "Get your API key from: https://platform.openai.com/api-keys"
        )
        return
    
    # Get the key
    api_key = context.args[0]
    
    # Validate format (basic check)
    if not api_key.startswith('sk-'):
        await update.message.reply_text(
            "⚠️ Invalid API key format. OpenAI keys start with 'sk-'\n"
            "Get your key from: https://platform.openai.com/api-keys"
        )
        return
    
    # Store in bot_data (shared across all users)
    context.bot_data["openai_api_key"] = api_key
    
    logger.info(f"OpenAI API key updated by user {update.effective_user.id}")
    
    await update.message.reply_text(
        "✅ OpenAI API key saved successfully!\n\n"
        "You can now use /chatgpt to start conversations.\n"
        "The key is stored in memory and will be cleared on bot restart.\n\n"
        "💡 Tip: Add OPENAI_API_KEY to your .env file for permanent storage."
    )

