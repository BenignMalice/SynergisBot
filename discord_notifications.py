#!/usr/bin/env python3
"""
Discord Trading Notifications
Send trading alerts via Discord webhooks
"""

import os
import re
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DiscordNotifier:
    def __init__(self):
        self.enabled = False
        self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL")  # Private channel
        self.signals_webhook_url = os.getenv("DISCORD_SIGNALS_WEBHOOK_URL")  # Public trading signals channel
        self.bot_name = os.getenv("DISCORD_BOT_NAME", "Synergis Trading")
        
        if self.webhook_url:
            self.enabled = True
            print("SUCCESS: Discord notifications enabled (private channel)")
        else:
            print("WARNING: Discord webhook URL not configured")
        
        if self.signals_webhook_url:
            print("SUCCESS: Discord signals channel enabled (public trading signals)")
    
    def send_message(self, message, message_type="INFO", color=0x00ff00, channel="private", custom_title=None):
        """
        Send message to Discord (handles long messages by splitting into multiple embeds)
        
        Args:
            message: The message content to send
            message_type: Type of message (used for channel routing and default title)
            color: Discord embed color (hex)
            channel: "private" (default) or "signals". If "signals" and message_type is "ANALYSIS", 
                    sends to public signals channel. Otherwise sends to private channel.
            custom_title: Optional custom title for embed (default: uses message_type)
        """
        # Determine which channel to use
        # If explicitly requested signals channel OR message_type contains "ANALYSIS", use signals channel
        use_signals = (channel == "signals" or "ANALYSIS" in message_type.upper())
        
        # Debug logging
        print(f"DEBUG: Discord routing - channel={channel}, message_type={message_type}, use_signals={use_signals}, signals_webhook_configured={bool(self.signals_webhook_url)}")
        
        if use_signals and self.signals_webhook_url:
            # Route to public signals channel
            webhook_url = self.signals_webhook_url
            channel_name = "signals"
            print(f"✅ Routing to SIGNALS channel: {message_type}")
        elif self.webhook_url:
            # Route to private channel (default)
            webhook_url = self.webhook_url
            channel_name = "private"
            # If signals was requested but not configured, log a warning
            if use_signals:
                print(f"⚠️ WARNING: Signals channel requested but DISCORD_SIGNALS_WEBHOOK_URL not configured. Sending to private channel instead.")
            else:
                print(f"ℹ️ Routing to PRIVATE channel: {message_type}")
        else:
            print(f"WARNING: No Discord webhook configured. Enable at least DISCORD_WEBHOOK_URL.")
            return False
        
        # Preprocess message: convert literal \n to actual newlines and improve formatting
        message = self._format_message(message)
        
        try:
            # Discord embed description limit is 4096 characters
            # For longer messages, split into multiple embeds
            MAX_DESCRIPTION_LENGTH = 4096
            
            embeds = []
            
            if len(message) <= MAX_DESCRIPTION_LENGTH:
                # Message fits in one embed - send as-is
                # Use custom_title if provided, otherwise use message_type
                embed_title = custom_title if custom_title else message_type
                embed = {
                    "title": f"Synergis Trading - {embed_title}",
                    "description": message,  # Full message, no truncation - preserve word-for-word
                    "color": color,
                    "timestamp": datetime.utcnow().isoformat(),
                    "footer": {
                        "text": "MoneyBot"
                    }
                }
                embeds.append(embed)
            else:
                # Message too long - split into multiple embeds
                # Split by lines to preserve formatting
                lines = message.split('\n')
                current_chunk = []
                current_length = 0
                chunk_num = 1
                
                for line in lines:
                    line_length = len(line) + 1  # +1 for newline
                    
                    # If adding this line would exceed limit, create new embed
                    if current_length + line_length > MAX_DESCRIPTION_LENGTH and current_chunk:
                        # Create embed from current chunk
                        chunk_text = '\n'.join(current_chunk)
                        # Use custom_title if provided, otherwise use message_type
                        embed_title_base = custom_title if custom_title else message_type
                        embed = {
                            "title": f"Synergis Trading - {embed_title_base} (Part {chunk_num})" if chunk_num > 1 else f"Synergis Trading - {embed_title_base}",
                            "description": chunk_text,  # Preserve full content, no truncation
                            "color": color,
                            "timestamp": datetime.utcnow().isoformat() if chunk_num == 1 else None,
                            "footer": {
                                "text": f"MoneyBot (Part {chunk_num}/{len(lines)} estimated)"
                            } if chunk_num > 1 else {
                                "text": "MoneyBot"
                            }
                        }
                        embeds.append(embed)
                        
                        # Start new chunk
                        current_chunk = [line]
                        current_length = line_length
                        chunk_num += 1
                    else:
                        # Add line to current chunk
                        current_chunk.append(line)
                        current_length += line_length
                
                # Add final chunk if any remaining
                if current_chunk:
                    chunk_text = '\n'.join(current_chunk)
                    # Use custom_title if provided, otherwise use message_type
                    embed_title_base = custom_title if custom_title else message_type
                    embed = {
                        "title": f"Synergis Trading - {embed_title_base} (Part {chunk_num})" if chunk_num > 1 else f"Synergis Trading - {embed_title_base}",
                        "description": chunk_text,  # Preserve full content, no truncation
                        "color": color,
                        "timestamp": datetime.utcnow().isoformat() if chunk_num == 1 else None,
                        "footer": {
                            "text": f"MoneyBot (Part {chunk_num})"
                        } if chunk_num > 1 else {
                            "text": "MoneyBot"
                        }
                    }
                    embeds.append(embed)
            
            # Send to Discord (can send up to 10 embeds per message)
            data = {
                "username": self.bot_name,
                "embeds": embeds[:10]  # Discord limit: max 10 embeds per message
            }
            
            response = requests.post(webhook_url, json=data, timeout=10)
            
            if response.status_code == 204:
                print(f"SUCCESS: Discord message sent to {channel_name} channel ({message_type}, {len(embeds)} embed(s))")
                return True
            else:
                print(f"FAILED: Discord message failed to {channel_name} channel: {response.status_code}")
                if response.status_code != 204:
                    print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"ERROR: Discord send failed: {e}")
            return False
    
    def _format_message(self, message):
        """
        Format message for Discord: convert literal \n to newlines, add spacing between sections
        """
        # Convert literal \n strings to actual newlines
        message = message.replace('\\n', '\n')
        
        # Remove trailing/leading newlines
        message = message.strip()
        
        # Add spacing between major sections for better readability
        # Sections typically start with emojis or specific markers
        # Add a blank line before sections that start with certain patterns
        
        # Patterns that indicate new sections (emojis, headers, etc.)
        section_patterns = [
            r'^🏛[️]',      # Structure section
            r'^🌍',         # Macro section
            r'^📊',         # Advanced Features section
            r'^💧',         # Liquidity section
            r'^📉',         # Volatility section
            r'^🎯',         # Verdict section
            r'^📝',         # Trade Note section
            r'^➡️',         # Arrow indicators
            r'^📈',         # Trade Outlook section
            r'^🧠',         # Summary section
            r'^🕒',         # Timestamp
            r'^📌',         # Pins/important
        ]
        
        lines = message.split('\n')
        formatted_lines = []
        
        for i, line in enumerate(lines):
            # Add spacing before section headers (except first line)
            if i > 0:
                is_section_start = any(re.match(pattern, line.strip()) for pattern in section_patterns)
                if is_section_start:
                    # Add blank line before section if previous line wasn't already blank
                    if formatted_lines and formatted_lines[-1].strip() != "":
                        formatted_lines.append("")
            
            formatted_lines.append(line)
        
        # Clean up excessive blank lines (max 2 consecutive)
        result = []
        blank_count = 0
        for line in formatted_lines:
            if line.strip() == "":
                blank_count += 1
                if blank_count <= 2:  # Allow max 2 blank lines
                    result.append("")
            else:
                blank_count = 0
                result.append(line)
        
        return '\n'.join(result)
    
    def send_trade_alert(self, symbol, action, price, lot_size, status, profit=None):
        """Send trade alert to Discord"""
        if not self.enabled:
            return False
        
        # Determine color based on action
        color = 0x00ff00 if action == "BUY" else 0xff0000 if action == "SELL" else 0xffff00
        
        # Create trade message
        message = f"**Symbol:** {symbol}\n"
        message += f"**Action:** {action}\n"
        message += f"**Price:** {price}\n"
        message += f"**Lot Size:** {lot_size}\n"
        message += f"**Status:** {status}\n"
        
        if profit:
            message += f"**Profit:** {profit}\n"
        
        return self.send_message(message, "TRADE ALERT", color)
    
    def send_system_alert(self, alert_type, message):
        """Send system alert to Discord"""
        if not self.enabled:
            return False
        
        color = 0x0099ff  # Blue for system alerts
        formatted_message = f"**Alert Type:** {alert_type}\n**Message:** {message}"
        
        return self.send_message(formatted_message, "SYSTEM ALERT", color)
    
    def send_dtms_alert(self, ticket, action, reason, price):
        """Send DTMS alert to Discord"""
        if not self.enabled:
            return False
        
        color = 0xff9900  # Orange for DTMS alerts
        message = f"**Ticket:** {ticket}\n"
        message += f"**Action:** {action}\n"
        message += f"**Reason:** {reason}\n"
        message += f"**Price:** {price}\n"
        
        return self.send_message(message, "DTMS ALERT", color)
    
    def send_risk_alert(self, level, message, action):
        """Send risk alert to Discord"""
        if not self.enabled:
            return False
        
        # Determine color based on risk level
        if level.upper() == "HIGH":
            color = 0xff0000  # Red
        elif level.upper() == "MEDIUM":
            color = 0xff9900  # Orange
        else:
            color = 0xffff00  # Yellow
        
        formatted_message = f"**Level:** {level}\n**Message:** {message}\n**Action:** {action}"
        
        return self.send_message(formatted_message, "RISK ALERT", color)
    
    def send_error_alert(self, error_message, component):
        """Send error alert to Discord"""
        if not self.enabled:
            return False
        
        color = 0xff0000  # Red for errors
        message = f"**Component:** {component}\n**Error:** {error_message}"
        
        return self.send_message(message, "ERROR ALERT", color)

def setup_discord_webhook():
    """Guide user through Discord webhook setup"""
    print("Discord Webhook Setup")
    print("=" * 30)
    print()
    print("To set up Discord notifications:")
    print()
    print("1. Open Discord in your browser or app")
    print("2. Go to your server (or create one)")
    print("3. Right-click on a channel -> 'Edit Channel'")
    print("4. Go to 'Integrations' -> 'Webhooks'")
    print("5. Click 'Create Webhook'")
    print("6. Copy the webhook URL")
    print("7. Add it to your .env file:")
    print()
    print("DISCORD_WEBHOOK_URL=your_webhook_url_here")
    print("DISCORD_SIGNALS_WEBHOOK_URL=your_signals_webhook_url_here  # Optional: for public trading signals channel")
    print("DISCORD_BOT_NAME=Synergis Trading")
    print()
    print("Example webhook URL:")
    print("https://discord.com/api/webhooks/123456789/abcdefghijklmnop")
    print()
    
    webhook_url = input("Enter your Discord webhook URL (or press Enter to skip): ").strip()
    
    if webhook_url:
        # Update .env file
        env_path = Path(".env")
        if not env_path.exists():
            env_path.touch()
        
        with open(env_path, "a") as f:
            f.write(f"\n# Discord Notifications\n")
            f.write(f"DISCORD_WEBHOOK_URL={webhook_url}\n")
            f.write(f"DISCORD_BOT_NAME=Synergis Trading\n")
        
        print("SUCCESS: Discord webhook added to .env file")
        return True
    else:
        print("Skipped Discord setup")
        return False

def test_discord_notifications():
    """Test Discord notifications"""
    print("Testing Discord Notifications...")
    print("=" * 40)
    
    notifier = DiscordNotifier()
    
    if notifier.enabled:
        # Test basic message
        success = notifier.send_message("This is a test message from Synergis Trading!")
        
        if success:
            print("SUCCESS: Discord notifications are working!")
            print("Check your Discord channel for the test message.")
        else:
            print("FAILED: Discord test failed.")
    else:
        print("FAILED: Discord not configured")
        print("Run setup_discord_webhook() to configure")

def example_discord_alerts():
    """Example Discord alerts"""
    print("Example Discord Trading Alerts...")
    print("=" * 40)
    
    notifier = DiscordNotifier()
    
    if notifier.enabled:
        # Example 1: Trade opened
        notifier.send_trade_alert(
            symbol="EURUSD",
            action="BUY",
            price="1.0850",
            lot_size="0.01",
            status="OPENED"
        )
        
        # Example 2: Trade closed with profit
        notifier.send_trade_alert(
            symbol="EURUSD",
            action="SELL",
            price="1.0875",
            lot_size="0.01",
            status="CLOSED",
            profit="+$25.00"
        )
        
        # Example 3: System alert
        notifier.send_system_alert(
            alert_type="BOT_START",
            message="Synergis Trading bot has started successfully"
        )
        
        # Example 4: DTMS alert
        notifier.send_dtms_alert(
            ticket="12345",
            action="STOP_LOSS_UPDATED",
            reason="Price moved in favor",
            price="1.0840"
        )
        
        # Example 5: Risk alert
        notifier.send_risk_alert(
            level="HIGH",
            message="Maximum drawdown reached",
            action="Reducing position size"
        )
        
        print("SUCCESS: Example alerts sent to Discord!")
    else:
        print("FAILED: Discord not configured")

if __name__ == "__main__":
    print("Discord Trading Notifications")
    print("=" * 40)
    
    # Setup Discord webhook
    if setup_discord_webhook():
        print()
        test_discord_notifications()
        print()
        example_discord_alerts()
    else:
        print("Discord setup skipped")
