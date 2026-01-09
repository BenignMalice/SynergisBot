#!/usr/bin/env python3
"""
Alternative Notification System
Provides notifications when Telegram is not available
"""

import os
import smtplib
import requests
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AlternativeNotifier:
    """Alternative notification system when Telegram is blocked"""
    
    def __init__(self):
        self.email_enabled = False
        self.discord_enabled = False
        self.slack_enabled = False
        
        # Check for email configuration
        if os.getenv("SMTP_SERVER") and os.getenv("EMAIL_USER") and os.getenv("EMAIL_PASSWORD"):
            self.email_enabled = True
            print("✅ Email notifications enabled")
        
        # Check for Discord webhook
        if os.getenv("DISCORD_WEBHOOK_URL"):
            self.discord_enabled = True
            print("✅ Discord notifications enabled")
        
        # Check for Slack webhook
        if os.getenv("SLACK_WEBHOOK_URL"):
            self.slack_enabled = True
            print("✅ Slack notifications enabled")
    
    def send_email_notification(self, subject, message, to_email=None):
        """Send email notification"""
        if not self.email_enabled:
            return False
        
        try:
            # Get email settings
            smtp_server = os.getenv("SMTP_SERVER")
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            email_user = os.getenv("EMAIL_USER")
            email_password = os.getenv("EMAIL_PASSWORD")
            from_email = os.getenv("FROM_EMAIL", email_user)
            
            if not to_email:
                to_email = os.getenv("NOTIFICATION_EMAIL", email_user)
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = to_email
            msg['Subject'] = f"[Synergis Trading] {subject}"
            
            # Add timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            body = f"{message}\n\nTimestamp: {timestamp}\nBot: TelegramMoneyBot v8.0"
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(email_user, email_password)
            text = msg.as_string()
            server.sendmail(from_email, to_email, text)
            server.quit()
            
            print(f"✅ Email notification sent: {subject}")
            return True
            
        except Exception as e:
            print(f"❌ Email notification failed: {e}")
            return False
    
    def send_discord_notification(self, title, message, color=0x00ff00):
        """Send Discord webhook notification"""
        if not self.discord_enabled:
            return False
        
        try:
            webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
            
            # Create Discord embed
            embed = {
                "title": title,
                "description": message,
                "color": color,
                "timestamp": datetime.now().isoformat(),
                "footer": {
                    "text": "MoneyBot"
                }
            }
            
            payload = {
                "embeds": [embed]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            
            if response.status_code == 204:
                print(f"✅ Discord notification sent: {title}")
                return True
            else:
                print(f"❌ Discord notification failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Discord notification failed: {e}")
            return False
    
    def send_slack_notification(self, message, channel=None):
        """Send Slack webhook notification"""
        if not self.slack_enabled:
            return False
        
        try:
            webhook_url = os.getenv("SLACK_WEBHOOK_URL")
            
            payload = {
                "text": f"🤖 Synergis Trading Alert\n{message}",
                "username": "Synergis Trading",
                "icon_emoji": ":robot_face:"
            }
            
            if channel:
                payload["channel"] = channel
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ Slack notification sent")
                return True
            else:
                print(f"❌ Slack notification failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Slack notification failed: {e}")
            return False
    
    def send_notification(self, title, message, notification_type="all"):
        """Send notification through all available channels"""
        success = False
        
        if notification_type in ["all", "email"] and self.email_enabled:
            success |= self.send_email_notification(title, message)
        
        if notification_type in ["all", "discord"] and self.discord_enabled:
            success |= self.send_discord_notification(title, message)
        
        if notification_type in ["all", "slack"] and self.slack_enabled:
            success |= self.send_slack_notification(message)
        
        return success
    
    def send_trade_alert(self, trade_info):
        """Send trade-specific alert"""
        title = f"Trade Alert: {trade_info.get('symbol', 'Unknown')}"
        message = f"""
Symbol: {trade_info.get('symbol', 'Unknown')}
Action: {trade_info.get('action', 'Unknown')}
Price: {trade_info.get('price', 'Unknown')}
Volume: {trade_info.get('volume', 'Unknown')}
Status: {trade_info.get('status', 'Unknown')}
        """.strip()
        
        return self.send_notification(title, message)
    
    def send_system_alert(self, alert_type, message):
        """Send system alert"""
        title = f"System Alert: {alert_type}"
        return self.send_notification(title, message)

def test_notifications():
    """Test all notification methods"""
    notifier = AlternativeNotifier()
    
    print("Testing alternative notifications...")
    print("=" * 40)
    
    # Test email
    if notifier.email_enabled:
        print("Testing email notification...")
        notifier.send_email_notification("Test Alert", "This is a test notification from the trading bot.")
    
    # Test Discord
    if notifier.discord_enabled:
        print("Testing Discord notification...")
        notifier.send_discord_notification("Test Alert", "This is a test notification from the trading bot.")
    
    # Test Slack
    if notifier.slack_enabled:
        print("Testing Slack notification...")
        notifier.send_slack_notification("This is a test notification from the trading bot.")
    
    if not (notifier.email_enabled or notifier.discord_enabled or notifier.slack_enabled):
        print("No notification methods configured.")
        print("Add to .env file:")
        print("  # Email notifications")
        print("  SMTP_SERVER=smtp.gmail.com")
        print("  SMTP_PORT=587")
        print("  EMAIL_USER=your-email@gmail.com")
        print("  EMAIL_PASSWORD=your-app-password")
        print("  NOTIFICATION_EMAIL=recipient@example.com")
        print("")
        print("  # Discord notifications")
        print("  DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...")
        print("")
        print("  # Slack notifications")
        print("  SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...")

if __name__ == "__main__":
    test_notifications()
