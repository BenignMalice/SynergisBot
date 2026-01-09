"""
Price Alert System
Monitors prices and sends Telegram notifications when targets are hit
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import threading
import time

logger = logging.getLogger(__name__)

class PriceAlert:
    def __init__(
        self,
        alert_id: str,
        symbol: str,
        alert_type: str,  # "above" or "below"
        target_price: float,
        message: str,
        created_at: str,
        triggered: bool = False,
        triggered_at: Optional[str] = None
    ):
        self.alert_id = alert_id
        self.symbol = symbol
        self.alert_type = alert_type
        self.target_price = target_price
        self.message = message
        self.created_at = created_at
        self.triggered = triggered
        self.triggered_at = triggered_at

    def to_dict(self):
        return {
            "alert_id": self.alert_id,
            "symbol": self.symbol,
            "alert_type": self.alert_type,
            "target_price": self.target_price,
            "message": self.message,
            "created_at": self.created_at,
            "triggered": self.triggered,
            "triggered_at": self.triggered_at
        }

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


class PriceAlertManager:
    def __init__(self, storage_file: str = "data/price_alerts.json"):
        self.storage_file = Path(storage_file)
        self.alerts: Dict[str, PriceAlert] = {}
        self.monitoring = False
        self.monitor_thread = None
        self._load_alerts()
        logger.info("PriceAlertManager initialized")

    def _load_alerts(self):
        """Load alerts from JSON file"""
        if self.storage_file.exists():
            try:
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    for alert_data in data.get("alerts", []):
                        alert = PriceAlert.from_dict(alert_data)
                        self.alerts[alert.alert_id] = alert
                logger.info(f"Loaded {len(self.alerts)} price alerts")
            except Exception as e:
                logger.error(f"Error loading alerts: {e}")
        else:
            # Create empty file
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
            self._save_alerts()

    def _save_alerts(self):
        """Save alerts to JSON file"""
        try:
            data = {
                "alerts": [alert.to_dict() for alert in self.alerts.values()],
                "last_updated": datetime.now().isoformat()
            }
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving alerts: {e}")

    def create_alert(
        self,
        symbol: str,
        alert_type: str,
        target_price: float,
        message: str
    ) -> PriceAlert:
        """Create a new price alert"""
        alert_id = f"{symbol}_{alert_type}_{target_price}_{int(time.time())}"
        alert = PriceAlert(
            alert_id=alert_id,
            symbol=symbol,
            alert_type=alert_type,
            target_price=target_price,
            message=message,
            created_at=datetime.now().isoformat()
        )
        self.alerts[alert_id] = alert
        self._save_alerts()
        logger.info(f"Created alert: {symbol} {alert_type} {target_price}")
        return alert

    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert"""
        if alert_id in self.alerts:
            del self.alerts[alert_id]
            self._save_alerts()
            logger.info(f"Deleted alert: {alert_id}")
            return True
        return False

    def get_active_alerts(self, symbol: Optional[str] = None) -> List[PriceAlert]:
        """Get all active (non-triggered) alerts, optionally filtered by symbol"""
        alerts = [a for a in self.alerts.values() if not a.triggered]
        if symbol:
            alerts = [a for a in alerts if a.symbol.upper() == symbol.upper()]
        return alerts

    def get_all_alerts(self) -> List[PriceAlert]:
        """Get all alerts (including triggered ones)"""
        return list(self.alerts.values())

    def check_alert(self, alert: PriceAlert, current_price: float) -> bool:
        """Check if alert condition is met"""
        if alert.triggered:
            return False
        
        if alert.alert_type == "above" and current_price >= alert.target_price:
            return True
        elif alert.alert_type == "below" and current_price <= alert.target_price:
            return True
        return False

    def trigger_alert(self, alert: PriceAlert, current_price: float):
        """Mark alert as triggered"""
        alert.triggered = True
        alert.triggered_at = datetime.now().isoformat()
        self._save_alerts()
        logger.info(f"Alert triggered: {alert.symbol} {alert.alert_type} {alert.target_price} (current: {current_price})")

    def monitor_prices(self, mt5_service, telegram_bot=None, check_interval: int = 60):
        """
        Monitor prices and trigger alerts
        
        Args:
            mt5_service: MT5 service instance for price fetching
            telegram_bot: Telegram bot instance for notifications
            check_interval: Seconds between price checks (default 60)
        """
        self.monitoring = True
        logger.info(f"Starting price monitoring (interval: {check_interval}s)")
        
        while self.monitoring:
            try:
                active_alerts = self.get_active_alerts()
                
                if not active_alerts:
                    time.sleep(check_interval)
                    continue
                
                # Group alerts by symbol to minimize API calls
                symbols_to_check = set(alert.symbol for alert in active_alerts)
                
                for symbol in symbols_to_check:
                    try:
                        # Normalize symbol for MT5
                        mt5_symbol = symbol.upper()
                        if not mt5_symbol.endswith('c'):
                            mt5_symbol = mt5_symbol + 'c'
                        
                        # Get current price
                        mt5_service.connect()
                        quote = mt5_service.get_quote(mt5_symbol)
                        
                        if not quote:
                            logger.warning(f"No quote available for {symbol}")
                            continue
                        
                        current_price = (quote.bid + quote.ask) / 2
                        
                        # Check all alerts for this symbol
                        symbol_alerts = [a for a in active_alerts if a.symbol == symbol]
                        
                        for alert in symbol_alerts:
                            if self.check_alert(alert, current_price):
                                # Alert triggered!
                                self.trigger_alert(alert, current_price)
                                
                                # Send Telegram notification
                                if telegram_bot:
                                    try:
                                        notification = (
                                            f"🔔 **Price Alert Triggered!**\n\n"
                                            f"**{alert.symbol}**: ${current_price:.3f}\n"
                                            f"**Condition**: Price {alert.alert_type} ${alert.target_price:.3f}\n\n"
                                            f"📝 {alert.message}\n\n"
                                            f"⏰ Triggered: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                        )
                                        telegram_bot.send_message(notification)
                                        logger.info(f"Sent Telegram notification for {alert.alert_id}")
                                    except Exception as e:
                                        logger.error(f"Error sending Telegram notification: {e}")
                    
                    except Exception as e:
                        logger.error(f"Error checking price for {symbol}: {e}")
                
                time.sleep(check_interval)
            
            except Exception as e:
                logger.error(f"Error in price monitoring loop: {e}")
                time.sleep(check_interval)
        
        logger.info("Price monitoring stopped")

    def start_monitoring(self, mt5_service, telegram_bot=None, check_interval: int = 60):
        """Start monitoring in background thread"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("Monitoring already running")
            return
        
        self.monitor_thread = threading.Thread(
            target=self.monitor_prices,
            args=(mt5_service, telegram_bot, check_interval),
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("Price monitoring started in background thread")

    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Price monitoring stopped")


# Global instance
_alert_manager = None

def get_alert_manager() -> PriceAlertManager:
    """Get or create global alert manager instance"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = PriceAlertManager()
    return _alert_manager

