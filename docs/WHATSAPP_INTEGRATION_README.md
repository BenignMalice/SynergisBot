# WhatsApp Trading Bot Integration

## 🚀 Quick Start

### 1. Start WhatsApp Server
```bash
node simple_whatsapp_server.js
```

### 2. Test WhatsApp Notifications
```bash
python whatsapp_trading_example.py
```

### 3. Start Trading Bot with WhatsApp
```bash
python start_trading_bot_with_whatsapp.py
```

## 📱 What You'll Receive

Your WhatsApp will receive:
- **Trade Alerts**: When trades are opened/closed
- **System Alerts**: Bot startup, errors, status updates
- **DTMS Alerts**: Defensive Trade Management System notifications
- **Risk Alerts**: Risk management warnings and actions

## 🔧 Configuration

Your `.env` file should contain:
```
# WhatsApp Web API
WHATSAPP_WEB_API_URL=http://localhost:3000/send
WHATSAPP_TO_NUMBER=+1234567890
```

## 📋 Available Functions

In your trading bot, you can use:

```python
# Trade notifications
notify_whatsapp_trade(symbol, action, price, lot_size, status, profit=None)

# System notifications
notify_whatsapp_system(alert_type, message)

# DTMS notifications
notify_whatsapp_dtms(ticket, action, reason, price)

# Risk notifications
notify_whatsapp_risk(level, message, action)
```

## 🧪 Testing

Test individual components:
```bash
# Test WhatsApp server
curl http://localhost:3000/status

# Test WhatsApp notifications
python whatsapp_notifications.py

# Test trading integration
python whatsapp_trading_integration.py
```

## 🔍 Troubleshooting

### WhatsApp Server Issues
- Make sure Node.js is installed
- Check if port 3000 is available
- Restart the server if needed

### Notification Issues
- Verify `.env` file configuration
- Check WhatsApp server is running
- Test with the example scripts

### Connection Issues
- The simple server simulates WhatsApp for testing
- For real WhatsApp, you'll need to set up a proper WhatsApp Business API

## 📁 Files Created

- `simple_whatsapp_server.js` - WhatsApp Web API server
- `whatsapp_trading_integration.py` - Core integration functions
- `whatsapp_trading_example.py` - Usage examples
- `start_trading_bot_with_whatsapp.py` - Combined startup script
- `whatsapp_qr.html` - QR code display page

## 🎯 Next Steps

1. **Test the integration** with the example scripts
2. **Start your trading bot** with WhatsApp notifications
3. **Monitor your WhatsApp** for trading alerts
4. **Customize notifications** for your specific needs

## 💡 Pro Tips

- Keep your phone nearby for instant trading alerts
- Use different alert types for different priority levels
- Test notifications before live trading
- Monitor the server logs for any issues

---

**Note**: This is a simulated WhatsApp server for testing. For production use, you'll need to set up a proper WhatsApp Business API or use a service like Twilio.
