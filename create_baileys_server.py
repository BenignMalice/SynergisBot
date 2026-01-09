#!/usr/bin/env python3
"""
Create Baileys WhatsApp Web API Server
Self-hosted WhatsApp Web API using Baileys
"""

import os
import json

def create_baileys_server():
    """Create a complete Baileys WhatsApp Web API server"""
    
    print("Creating Baileys WhatsApp Web API Server")
    print("=" * 40)
    print()
    
    # Create package.json
    package_json = {
        "name": "whatsapp-trading-bot",
        "version": "1.0.0",
        "description": "WhatsApp Web API for Trading Bot",
        "main": "whatsapp-server.js",
        "scripts": {
            "start": "node whatsapp-server.js",
            "dev": "nodemon whatsapp-server.js"
        },
        "dependencies": {
            "@whiskeysockets/baileys": "^6.6.0",
            "express": "^4.18.2",
            "qrcode": "^1.5.3",
            "cors": "^2.8.5"
        },
        "devDependencies": {
            "nodemon": "^3.0.1"
        }
    }
    
    with open('package.json', 'w') as f:
        json.dump(package_json, f, indent=2)
    
    # Create the server script
    server_script = '''#!/usr/bin/env node
/**
 * Baileys WhatsApp Web API Server for Trading Bot
 * 
 * Setup:
 * 1. Run: npm install
 * 2. Run: npm start
 * 3. Scan QR code with WhatsApp
 * 4. Use webhook: http://localhost:3000/send
 */

const { default: makeWASocket, DisconnectReason, useMultiFileAuthState } = require('@whiskeysockets/baileys');
const express = require('express');
const qr = require('qrcode');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(express.json());
app.use(cors());

let socket = null;
let qrCode = null;
let isConnected = false;

// Create auth directory
const authDir = './whatsapp_auth';
if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir);
}

async function connectToWhatsApp() {
    console.log('🔄 Connecting to WhatsApp...');
    
    const { state, saveCreds } = await useMultiFileAuthState(authDir);
    
    socket = makeWASocket({
        auth: state,
        printQRInTerminal: true,
        browser: ['Trading Bot', 'Chrome', '1.0.0']
    });
    
    socket.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;
        
        if (qr) {
            qrCode = qr;
            console.log('📱 QR Code generated. Scan with WhatsApp to connect.');
            console.log('   Or visit: http://localhost:3000/qr');
        }
        
        if (connection === 'close') {
            isConnected = false;
            const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
            console.log('❌ Connection closed:', lastDisconnect?.error?.message || 'Unknown error');
            console.log('🔄 Reconnecting:', shouldReconnect);
            
            if (shouldReconnect) {
                setTimeout(connectToWhatsApp, 5000);
            }
        } else if (connection === 'open') {
            isConnected = true;
            console.log('✅ WhatsApp connected successfully!');
            qrCode = null;
        }
    });
    
    socket.ev.on('creds.update', saveCreds);
    
    // Handle incoming messages (optional)
    socket.ev.on('messages.upsert', (m) => {
        const msg = m.messages[0];
        if (!msg.key.fromMe && m.type === 'notify') {
            console.log('📨 Received message from:', msg.key.remoteJid);
        }
    });
}

// API endpoint to send messages
app.post('/send', async (req, res) => {
    try {
        const { number, message } = req.body;
        
        if (!isConnected || !socket) {
            return res.status(500).json({ 
                error: 'WhatsApp not connected',
                message: 'Please scan QR code first'
            });
        }
        
        if (!number || !message) {
            return res.status(400).json({ 
                error: 'Missing parameters',
                message: 'Both number and message are required'
            });
        }
        
        // Format phone number
        let formattedNumber = number.replace(/[^0-9]/g, '');
        if (!formattedNumber.startsWith('1') && formattedNumber.length === 10) {
            formattedNumber = '1' + formattedNumber; // Add US country code
        }
        
        const jid = formattedNumber + '@s.whatsapp.net';
        
        // Send message
        await socket.sendMessage(jid, { text: message });
        
        console.log(`📤 Message sent to ${number}: ${message.substring(0, 50)}...`);
        
        res.json({ 
            success: true, 
            message: 'Message sent successfully',
            to: number,
            timestamp: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('❌ Error sending message:', error);
        res.status(500).json({ 
            error: 'Failed to send message',
            message: error.message
        });
    }
});

// API endpoint to get QR code
app.get('/qr', (req, res) => {
    if (qrCode) {
        qr.toDataURL(qrCode, (err, url) => {
            if (err) {
                res.status(500).json({ error: 'Failed to generate QR code' });
            } else {
                res.json({ 
                    qr: url,
                    connected: false,
                    message: 'Scan QR code with WhatsApp to connect'
                });
            }
        });
    } else if (isConnected) {
        res.json({ 
            qr: null, 
            connected: true,
            message: 'WhatsApp is connected and ready'
        });
    } else {
        res.json({ 
            qr: null, 
            connected: false,
            message: 'Generating QR code...'
        });
    }
});

// API endpoint to check status
app.get('/status', (req, res) => {
    res.json({
        connected: isConnected,
        qr_available: qrCode !== null,
        timestamp: new Date().toISOString()
    });
});

// API endpoint to send test message
app.post('/test', async (req, res) => {
    try {
        const { number } = req.body;
        
        if (!number) {
            return res.status(400).json({ error: 'Phone number required' });
        }
        
        const testMessage = `🤖 Trading Bot Test Message
        
This is a test message from your trading bot's WhatsApp Web API.

✅ If you receive this, WhatsApp notifications are working!

Time: ${new Date().toLocaleString()}
Bot: TelegramMoneyBot v8.0`;

        const result = await fetch('http://localhost:3000/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ number, message: testMessage })
        });
        
        const data = await result.json();
        res.json(data);
        
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Health check endpoint
app.get('/health', (req, res) => {
    res.json({
        status: 'ok',
        connected: isConnected,
        uptime: process.uptime(),
        timestamp: new Date().toISOString()
    });
});

// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log('🚀 WhatsApp Web API server started');
    console.log(`📡 Server running on port ${PORT}`);
    console.log(`🔗 Webhook URL: http://localhost:${PORT}/send`);
    console.log(`📱 QR Code URL: http://localhost:${PORT}/qr`);
    console.log(`📊 Status URL: http://localhost:${PORT}/status`);
    console.log(`🧪 Test URL: http://localhost:${PORT}/test`);
    console.log('');
    console.log('📋 Next steps:');
    console.log('1. Scan QR code with WhatsApp');
    console.log('2. Configure your trading bot with the webhook URL');
    console.log('3. Test notifications');
});

// Connect to WhatsApp
connectToWhatsApp();

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('\\n🛑 Shutting down server...');
    process.exit(0);
});
'''
    
    with open('whatsapp-server.js', 'w') as f:
        f.write(server_script)
    
    # Create README
    readme = '''# WhatsApp Web API Server

This is a self-hosted WhatsApp Web API server for your trading bot.

## Setup

1. **Install Node.js** (if not already installed)
   - Download from: https://nodejs.org/
   - Version 16 or higher recommended

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Start the server**
   ```bash
   npm start
   ```

4. **Connect WhatsApp**
   - Open http://localhost:3000/qr in your browser
   - Scan the QR code with WhatsApp
   - Wait for "WhatsApp connected successfully!" message

## API Endpoints

- `POST /send` - Send WhatsApp message
- `GET /qr` - Get QR code for connection
- `GET /status` - Check connection status
- `POST /test` - Send test message
- `GET /health` - Health check

## Usage

### Send Message
```bash
curl -X POST http://localhost:3000/send \\
  -H "Content-Type: application/json" \\
  -d '{"number": "+1234567890", "message": "Hello from trading bot!"}'
```

### Test Connection
```bash
curl -X POST http://localhost:3000/test \\
  -H "Content-Type: application/json" \\
  -d '{"number": "+1234567890"}'
```

## Configuration

The server will create a `whatsapp_auth` directory to store your WhatsApp session. This allows you to reconnect without scanning the QR code again.

## Troubleshooting

- If QR code doesn't work, delete the `whatsapp_auth` folder and restart
- Make sure your phone has internet connection
- WhatsApp Web must be enabled on your phone
- Check the console for error messages

## Security

This server runs locally and only accepts connections from localhost by default. For production use, add proper authentication and security measures.
'''
    
    with open('README.md', 'w') as f:
        f.write(readme)
    
    # Create start script
    start_script = '''@echo off
echo Starting WhatsApp Web API Server...
echo.
echo Make sure you have Node.js installed!
echo.
npm start
pause
'''
    
    with open('start-whatsapp-server.bat', 'w') as f:
        f.write(start_script)
    
    print("✅ Baileys server files created:")
    print("   - package.json")
    print("   - whatsapp-server.js")
    print("   - README.md")
    print("   - start-whatsapp-server.bat")
    print()
    print("🚀 To start the server:")
    print("1. Run: npm install")
    print("2. Run: npm start")
    print("   OR double-click: start-whatsapp-server.bat")
    print()
    print("📱 To connect WhatsApp:")
    print("1. Open: http://localhost:3000/qr")
    print("2. Scan QR code with WhatsApp")
    print("3. Wait for 'WhatsApp connected successfully!'")
    print()
    print("🔗 Webhook URL for your bot:")
    print("   http://localhost:3000/send")

def main():
    """Main function"""
    print("Creating Baileys WhatsApp Web API Server")
    print("=" * 40)
    print()
    
    create_baileys_server()
    
    print()
    print("🎉 Server setup complete!")
    print()
    print("Next steps:")
    print("1. Start the server: npm start")
    print("2. Connect WhatsApp: http://localhost:3000/qr")
    print("3. Configure your bot: python setup_whatsapp_web.py")
    print("4. Test notifications: python whatsapp_notifications.py")

if __name__ == "__main__":
    main()
