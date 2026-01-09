# Synergis Trading Bot - Full MT5 Integration with Discord Notifications

## 🚀 Overview

The **Synergis Trading Bot** is a complete trading system that replaces Telegram with Discord notifications while maintaining full MT5 integration and all trading functionality. This bot provides:

- **Full MT5 Integration** - Real trading with MetaTrader 5
- **Discord Notifications** - All alerts sent to your Discord channel
- **Complete Trading Features** - All original functionality preserved
- **No Telegram Dependency** - Solves connection issues

## 📁 Files Created

### Core Trading Bot
- **`synergis_trading.py`** - Main trading bot with Discord notifications
- **`synergis_trading_cli.py`** - Command-line interface for easy management
- **`test_synergis_bot.py`** - Test script to verify all components

### Key Features
- ✅ **MT5 Connection** - Full MetaTrader 5 integration
- ✅ **Discord Notifications** - All trading alerts via Discord
- ✅ **Position Monitoring** - Real-time position tracking
- ✅ **Trade Management** - Stop loss, take profit, trailing stops
- ✅ **Journal System** - Complete trade logging
- ✅ **Circuit Breaker** - Risk management
- ✅ **Signal Scanner** - Automatic signal detection
- ✅ **Trailing Stops** - Advanced trade management

## 🛠️ Setup Instructions

### 1. Environment Variables
Ensure your `.env` file contains:
```env
# Required
OPENAI_API_KEY=your_openai_key
DISCORD_WEBHOOK_URL=your_discord_webhook_url

# Optional (for full functionality)
MT5_WINDOW_TITLE=Exness
USE_TRAILING_STOPS=1
TRAILING_CHECK_INTERVAL=15
```

### 2. Discord Setup
1. Create a Discord webhook in your server
2. Add the webhook URL to your `.env` file
3. Test notifications with: `python -c "from synergis_trading_cli import test_discord_notifications; test_discord_notifications()"`

### 3. MT5 Setup
1. Ensure MetaTrader 5 is running
2. Login to your trading account
3. Test connection with: `python -c "from synergis_trading_cli import check_mt5_connection; check_mt5_connection()"`

## 🚀 Usage

### Command Line Interface
```bash
python synergis_trading_cli.py
```

**Menu Options:**
1. **Start Trading Bot** - Run the full trading system
2. **Check MT5 Connection** - Verify MT5 connectivity
3. **View Active Positions** - See current trades
4. **View Trading History** - Check past trades
5. **Test Discord Notifications** - Verify Discord alerts
6. **View System Status** - Check all components
7. **Exit** - Close the interface

### Direct Bot Execution
```bash
python synergis_trading.py
```

### Test All Components
```bash
python test_synergis_bot.py
```

## 📊 System Status

### Current Status (Verified)
- ✅ **OpenAI API Key**: Set
- ✅ **Discord Webhook**: Set
- ✅ **MT5 Connection**: Connected
- ✅ **Data Directory**: Exists
- ✅ **Positions File**: Yes
- ✅ **Journal Database**: Yes
- ✅ **Pendings File**: Yes

## 🔧 Technical Details

### Architecture
- **Base**: `trade_bot.py` (original Telegram bot)
- **Modifications**: Replaced Telegram with Discord
- **MT5 Integration**: Full MetaTrader 5 support
- **Notifications**: Discord webhooks for all alerts

### Key Components
1. **MT5Service** - MetaTrader 5 connection and trading
2. **PositionWatcher** - Real-time position monitoring
3. **JournalRepo** - Trade logging and history
4. **CircuitBreaker** - Risk management
5. **DiscordNotifier** - All notification delivery

### Trading Features
- **Real Trading** - Actual MT5 order execution
- **Position Management** - Stop loss, take profit, trailing stops
- **Risk Management** - Circuit breaker, position sizing
- **Signal Detection** - Automatic high-probability signals
- **Multi-timeframe Analysis** - Advanced market analysis

## 📱 Discord Notifications

### Alert Types
- **Trade Alerts** - Buy/sell executions
- **System Alerts** - Bot status, errors, connections
- **DTMS Alerts** - Dynamic trade management
- **Risk Alerts** - Risk management warnings

### Example Messages
```
TRADE ALERT
Symbol: EURUSD
Action: BUY
Price: 1.0850
Lot Size: 0.01
Status: OPENED

SYSTEM ALERT: MT5_CONNECTED
MT5 connected successfully
```

## 🎯 Benefits

### vs Original Telegram Bot
- ✅ **No Connection Issues** - Discord is more reliable
- ✅ **Same Functionality** - All features preserved
- ✅ **Better Notifications** - Rich Discord formatting
- ✅ **Easier Setup** - No Telegram bot configuration
- ✅ **More Reliable** - No API timeouts

### vs Simulated Bots
- ✅ **Real Trading** - Actual MT5 integration
- ✅ **Real Money** - Live trading capabilities
- ✅ **Real Data** - Live market data
- ✅ **Real Results** - Actual profit/loss

## 🔍 Troubleshooting

### Common Issues
1. **MT5 Connection Failed**
   - Ensure MT5 is running and logged in
   - Check account permissions
   - Verify terminal is not in demo mode

2. **Discord Notifications Not Working**
   - Check webhook URL in `.env`
   - Verify Discord server permissions
   - Test with: `python -c "from synergis_trading_cli import test_discord_notifications; test_discord_notifications()"`

3. **Bot Not Starting**
   - Check all dependencies installed
   - Verify `.env` file configuration
   - Run test script: `python test_synergis_bot.py`

## 📈 Next Steps

1. **Start Trading** - Run `python synergis_trading_cli.py` and select option 1
2. **Monitor Discord** - Watch for trading alerts in your Discord channel
3. **Check Positions** - Use option 3 to view active trades
4. **Review History** - Use option 4 to see trading performance

## 🎉 Success!

Your **Synergis Trading Bot** is now fully operational with:
- ✅ Full MT5 integration
- ✅ Discord notifications
- ✅ Complete trading functionality
- ✅ No Telegram dependency

**Ready to trade! 🚀📈**
