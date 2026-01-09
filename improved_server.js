const { default: makeWASocket, DisconnectReason, useMultiFileAuthState } = require('@whiskeysockets/baileys');
const express = require('express');
const qr = require('qrcode');
const fs = require('fs');

const app = express();
app.use(express.json());

let socket = null;
let qrCode = null;
let connected = false;
let connectionAttempts = 0;
const maxAttempts = 5;

// Create auth directory
const authDir = './whatsapp_auth';
if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir);
}

async function connectToWhatsApp() {
    try {
        console.log(`Attempting to connect to WhatsApp... (Attempt ${connectionAttempts + 1}/${maxAttempts})`);
        
        const { state, saveCreds } = await useMultiFileAuthState(authDir);
        
        socket = makeWASocket({
            auth: state,
            printQRInTerminal: false, // Disabled to avoid deprecation warning
            browser: ['Trading Bot', 'Chrome', '1.0.0'],
            connectTimeoutMs: 60000,
            keepAliveIntervalMs: 30000,
            retryRequestDelayMs: 250,
            maxMsgRetryCount: 3,
            markOnlineOnConnect: true
        });
        
        socket.ev.on('connection.update', (update) => {
            const { connection, lastDisconnect, qr } = update;
            
            if (qr) {
                qrCode = qr;
                console.log('QR Code generated! Scan with WhatsApp to connect.');
                console.log('Visit: http://localhost:3000/qr');
            }
            
            if (connection === 'close') {
                connected = false;
                qrCode = null;
                
                const shouldReconnect = lastDisconnect?.error?.output?.statusCode !== DisconnectReason.loggedOut;
                
                if (shouldReconnect && connectionAttempts < maxAttempts) {
                    connectionAttempts++;
                    console.log(`Connection closed. Reconnecting in 5 seconds... (${connectionAttempts}/${maxAttempts})`);
                    setTimeout(connectToWhatsApp, 5000);
                } else if (connectionAttempts >= maxAttempts) {
                    console.log('Max reconnection attempts reached. Please restart the server.');
                } else {
                    console.log('Connection closed. Please restart the server.');
                }
            } else if (connection === 'open') {
                connected = true;
                qrCode = null;
                connectionAttempts = 0;
                console.log('✅ WhatsApp connected successfully!');
                console.log('Ready to send messages.');
            }
        });
        
        socket.ev.on('creds.update', saveCreds);
        
        // Handle incoming messages
        socket.ev.on('messages.upsert', (m) => {
            const msg = m.messages[0];
            if (!msg.key.fromMe && m.type === 'notify') {
                console.log('📨 Received message from:', msg.key.remoteJid);
            }
        });
        
    } catch (error) {
        console.error('Connection error:', error.message);
        if (connectionAttempts < maxAttempts) {
            connectionAttempts++;
            console.log(`Retrying in 10 seconds... (${connectionAttempts}/${maxAttempts})`);
            setTimeout(connectToWhatsApp, 10000);
        }
    }
}

// Send message endpoint
app.post('/send', async (req, res) => {
    try {
        const { number, message } = req.body;
        
        if (!connected || !socket) {
            return res.status(500).json({ 
                error: 'WhatsApp not connected',
                message: 'Please scan QR code first or wait for connection'
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
            formattedNumber = '1' + formattedNumber;
        }
        
        const jid = formattedNumber + '@s.whatsapp.net';
        
        // Send message
        await socket.sendMessage(jid, { text: message });
        
        console.log(`📤 Message sent to ${number}`);
        
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

// QR code endpoint
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
    } else if (connected) {
        res.json({ 
            qr: null, 
            connected: true,
            message: 'WhatsApp is connected and ready'
        });
    } else {
        res.json({ 
            qr: null, 
            connected: false,
            message: 'Generating QR code... Please wait'
        });
    }
});

// Status endpoint
app.get('/status', (req, res) => {
    res.json({
        connected: connected,
        qr_available: qrCode !== null,
        attempts: connectionAttempts,
        max_attempts: maxAttempts,
        timestamp: new Date().toISOString()
    });
});

// Test endpoint
app.post('/test', async (req, res) => {
    try {
        const { number } = req.body;
        
        if (!number) {
            return res.status(400).json({ error: 'Phone number required' });
        }
        
        const testMessage = `Trading Bot Test Message

This is a test message from your trading bot's WhatsApp Web API.

If you receive this, WhatsApp notifications are working!

Time: ${new Date().toLocaleString()}
Bot: TelegramMoneyBot v8.0`;

        // Use internal send logic
        if (!connected || !socket) {
            return res.status(500).json({ error: 'WhatsApp not connected' });
        }
        
        let formattedNumber = number.replace(/[^0-9]/g, '');
        if (!formattedNumber.startsWith('1') && formattedNumber.length === 10) {
            formattedNumber = '1' + formattedNumber;
        }
        
        const jid = formattedNumber + '@s.whatsapp.net';
        await socket.sendMessage(jid, { text: testMessage });
        
        res.json({ 
            success: true, 
            message: 'Test message sent successfully',
            to: number
        });
        
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Health check
app.get('/health', (req, res) => {
    res.json({
        status: 'ok',
        connected: connected,
        uptime: process.uptime(),
        timestamp: new Date().toISOString()
    });
});

// Start server
const PORT = 3000;
app.listen(PORT, () => {
    console.log('🚀 WhatsApp Web API server started');
    console.log(`📡 Server running on port ${PORT}`);
    console.log(`🔗 Webhook URL: http://localhost:${PORT}/send`);
    console.log(`📱 QR Code URL: http://localhost:${PORT}/qr`);
    console.log(`📊 Status URL: http://localhost:${PORT}/status`);
    console.log(`🧪 Test URL: http://localhost:${PORT}/test`);
    console.log('');
    console.log('📋 Next steps:');
    console.log('1. Wait for QR code to appear');
    console.log('2. Visit http://localhost:3000/qr');
    console.log('3. Scan QR code with WhatsApp');
    console.log('4. Wait for "WhatsApp connected successfully!" message');
    console.log('');
});

// Connect to WhatsApp
connectToWhatsApp();

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('\n🛑 Shutting down server...');
    process.exit(0);
});
