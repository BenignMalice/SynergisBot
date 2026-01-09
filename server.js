const { default: makeWASocket, useMultiFileAuthState } = require('@whiskeysockets/baileys');
const express = require('express');
const qr = require('qrcode');

const app = express();
app.use(express.json());

let socket = null;
let qrCode = null;
let connected = false;

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('./auth');
    
    socket = makeWASocket({
        auth: state,
        printQRInTerminal: true
    });
    
    socket.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;
        
        if (qr) {
            qrCode = qr;
            console.log('QR Code generated. Scan with WhatsApp.');
        }
        
        if (connection === 'close') {
            connected = false;
            console.log('Connection closed. Reconnecting...');
            setTimeout(connectToWhatsApp, 5000);
        } else if (connection === 'open') {
            connected = true;
            console.log('WhatsApp connected!');
            qrCode = null;
        }
    });
    
    socket.ev.on('creds.update', saveCreds);
}

// Send message endpoint
app.post('/send', async (req, res) => {
    try {
        const { number, message } = req.body;
        
        if (!connected || !socket) {
            return res.status(500).json({ error: 'WhatsApp not connected' });
        }
        
        if (!number || !message) {
            return res.status(400).json({ error: 'Number and message required' });
        }
        
        const jid = number.replace(/[^0-9]/g, '') + '@s.whatsapp.net';
        await socket.sendMessage(jid, { text: message });
        
        res.json({ success: true, message: 'Sent' });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// QR code endpoint
app.get('/qr', (req, res) => {
    if (qrCode) {
        qr.toDataURL(qrCode, (err, url) => {
            if (err) {
                res.status(500).json({ error: 'QR generation failed' });
            } else {
                res.json({ qr: url });
            }
        });
    } else {
        res.json({ qr: null, connected: connected });
    }
});

// Status endpoint
app.get('/status', (req, res) => {
    res.json({ connected: connected });
});

const PORT = 3000;
app.listen(PORT, () => {
    console.log('Server running on port', PORT);
    console.log('Webhook: http://localhost:3000/send');
    console.log('QR Code: http://localhost:3000/qr');
});

connectToWhatsApp();
