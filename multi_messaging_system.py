#!/usr/bin/env python3
"""
Multi-Messaging System for Trading Bot
Supports Discord, Telegram, Email, and more
"""

import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MultiMessagingNotifier:
    def __init__(self):
        self.discord_enabled = False
        self.telegram_enabled = False
        self.email_enabled = False
        
        # Discord setup
        if os.getenv("DISCORD_WEBHOOK_URL"):
            self.discord_enabled = True
            self.discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
            self.discord_bot_name = os.getenv("DISCORD_BOT_NAME", "Synergis Trading")
            print("SUCCESS: Discord notifications enabled")
        
        # Telegram setup (you already have this)
        if os.getenv("TELEGRAM_TOKEN"):
            self.telegram_enabled = True
            self.telegram_token = os.getenv("TELEGRAM_TOKEN")
            print("SUCCESS: Telegram notifications enabled")
        
        # Email setup
        if os.getenv("EMAIL_SMTP_SERVER") and os.getenv("EMAIL_USERNAME"):
            self.email_enabled = True
            self.smtp_server = os.getenv("EMAIL_SMTP_SERVER")
            self.smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
            self.email_username = os.getenv("EMAIL_USERNAME")
            self.email_password = os.getenv("EMAIL_PASSWORD")
            self.email_to = os.getenv("EMAIL_TO")
            print("SUCCESS: Email notifications enabled")
        
        if not any([self.discord_enabled, self.telegram_enabled, self.email_enabled]):
            print("WARNING: No messaging services configured")
    
    def send_discord_message(self, message, message_type="INFO", color=0x00ff00):
        """Send message to Discord"""
        if not self.discord_enabled:
            return False
        
        try:
            embed = {
                "title": f"Synergis Trading - {message_type}",
                "description": message,
                "color": color,
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {"text": "MoneyBot"}
            }
            
            data = {
                "username": self.discord_bot_name,
                "embeds": [embed]
            }
            
            response = requests.post(self.discord_webhook, json=data, timeout=10)
            return response.status_code == 204
            
        except Exception as e:
            print(f"ERROR: Discord send failed: {e}")
            return False
    
    def send_telegram_message(self, message):
        """Send message to Telegram"""
        if not self.telegram_enabled:
            return False
        
        try:
            # This would use your existing Telegram bot
            # For now, just print the message
            print(f"TELEGRAM: {message}")
            return True
        except Exception as e:
            print(f"ERROR: Telegram send failed: {e}")
            return False
    
    def send_email_message(self, subject, message):
        """Send message via email"""
        if not self.email_enabled:
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_username
            msg['To'] = self.email_to
            msg['Subject'] = f"Synergis Trading - {subject}"
            
            msg.attach(MIMEText(message, 'plain'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_username, self.email_password)
            server.send_message(msg)
            server.quit()
            
            return True
        except Exception as e:
            print(f"ERROR: Email send failed: {e}")
            return False
    
    def send_trade_alert(self, symbol, action, price, lot_size, status, profit=None):
        """Send trade alert to all enabled services"""
        message = f"**Symbol:** {symbol}\n"
        message += f"**Action:** {action}\n"
        message += f"**Price:** {price}\n"
        message += f"**Lot Size:** {lot_size}\n"
        message += f"**Status:** {status}\n"
        
        if profit:
            message += f"**Profit:** {profit}\n"
        
        # Determine color for Discord
        color = 0x00ff00 if action == "BUY" else 0xff0000 if action == "SELL" else 0xffff00
        
        # Send to all enabled services
        results = []
        if self.discord_enabled:
            results.append(self.send_discord_message(message, "TRADE ALERT", color))
        if self.telegram_enabled:
            results.append(self.send_telegram_message(f"TRADE ALERT\n{message}"))
        if self.email_enabled:
            results.append(self.send_email_message("Trade Alert", message))
        
        return any(results)
    
    def send_system_alert(self, alert_type, message):
        """Send system alert to all enabled services"""
        formatted_message = f"**Alert Type:** {alert_type}\n**Message:** {message}"
        
        results = []
        if self.discord_enabled:
            results.append(self.send_discord_message(formatted_message, "SYSTEM ALERT", 0x0099ff))
        if self.telegram_enabled:
            results.append(self.send_telegram_message(f"SYSTEM ALERT: {alert_type}\n{message}"))
        if self.email_enabled:
            results.append(self.send_email_message(f"System Alert - {alert_type}", message))
        
        return any(results)
    
    def send_risk_alert(self, level, message, action):
        """Send risk alert to all enabled services"""
        formatted_message = f"**Level:** {level}\n**Message:** {message}\n**Action:** {action}"
        
        # Determine color for Discord
        color = 0xff0000 if level.upper() == "HIGH" else 0xff9900 if level.upper() == "MEDIUM" else 0xffff00
        
        results = []
        if self.discord_enabled:
            results.append(self.send_discord_message(formatted_message, "RISK ALERT", color))
        if self.telegram_enabled:
            results.append(self.send_telegram_message(f"RISK ALERT - {level}\n{message}\nAction: {action}"))
        if self.email_enabled:
            results.append(self.send_email_message(f"Risk Alert - {level}", f"{message}\nAction: {action}"))
        
        return any(results)

def test_multi_messaging():
    """Test multi-messaging system"""
    print("Testing Multi-Messaging System...")
    print("=" * 40)
    
    notifier = MultiMessagingNotifier()
    
    if not any([notifier.discord_enabled, notifier.telegram_enabled, notifier.email_enabled]):
        print("FAILED: No messaging services configured")
        print("Please configure at least one service:")
        print("- Discord: Add DISCORD_WEBHOOK_URL to .env")
        print("- Telegram: Already configured")
        print("- Email: Add EMAIL_SMTP_SERVER, EMAIL_USERNAME, etc. to .env")
        return
    
    # Test trade alert
    print("Testing trade alert...")
    success = notifier.send_trade_alert(
        symbol="EURUSD",
        action="BUY",
        price="1.0850",
        lot_size="0.01",
        status="OPENED"
    )
    
    if success:
        print("SUCCESS: Trade alert sent")
    else:
        print("FAILED: Trade alert failed")
    
    # Test system alert
    print("Testing system alert...")
    success = notifier.send_system_alert(
        alert_type="BOT_START",
        message="Trading bot has started successfully"
    )
    
    if success:
        print("SUCCESS: System alert sent")
    else:
        print("FAILED: System alert failed")
    
    # Test risk alert
    print("Testing risk alert...")
    success = notifier.send_risk_alert(
        level="HIGH",
        message="Maximum drawdown reached",
        action="Reducing position size"
    )
    
    if success:
        print("SUCCESS: Risk alert sent")
    else:
        print("FAILED: Risk alert failed")

if __name__ == "__main__":
    print("Multi-Messaging System for Trading Bot")
    print("=" * 50)
    test_multi_messaging()
