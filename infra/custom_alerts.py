"""
Custom Alert Manager for ChatGPT-configured alerts
Handles structure alerts (BOS, CHOCH), price alerts, and indicator alerts
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Types of alerts supported"""
    STRUCTURE = "structure"  # BOS, CHOCH, structure breaks
    PRICE = "price"  # Price crosses a level
    INDICATOR = "indicator"  # RSI, MACD, etc conditions
    ORDER_FLOW = "order_flow"  # Whale activity, liquidity voids
    VOLATILITY = "volatility"  # VIX, ATR changes


class AlertCondition(Enum):
    """Condition operators"""
    EQUALS = "equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"
    DETECTED = "detected"  # For event-based alerts like BOS


@dataclass
class CustomAlert:
    """Represents a custom alert configuration"""
    alert_id: str
    symbol: str
    alert_type: AlertType
    condition: AlertCondition
    description: str  # Human-readable description
    parameters: Dict  # Alert-specific parameters
    created_at: str
    expires_at: Optional[str] = None  # Optional expiry
    enabled: bool = True
    triggered_count: int = 0
    last_triggered: Optional[str] = None
    one_time: bool = True  # Auto-remove after first trigger (default: True)


class CustomAlertManager:
    """Manages custom alerts configured by ChatGPT"""
    
    def __init__(self, storage_file: str = "data/custom_alerts.json"):
        self.storage_file = Path(storage_file)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.alerts: Dict[str, CustomAlert] = {}
        self.load_alerts()
        logger.info(f"CustomAlertManager initialized with {len(self.alerts)} alerts")
    
    def add_alert(self, symbol: str, alert_type: str, condition: str, 
                  description: str, parameters: Dict, expires_hours: Optional[int] = None,
                  one_time: bool = True) -> CustomAlert:
        """
        Add a new custom alert
        
        Examples:
        - BOS Bull on BTCUSD: 
            alert_type="structure", condition="detected", 
            parameters={"pattern": "bos_bull", "timeframe": "M5"}
        - XAUUSD crosses 4100:
            alert_type="price", condition="crosses_above",
            parameters={"price_level": 4100}
        - RSI > 70:
            alert_type="indicator", condition="greater_than",
            parameters={"indicator": "rsi", "value": 70, "timeframe": "H1"}
        """
        try:
            alert_id = f"{symbol}_{alert_type}_{int(datetime.now().timestamp())}"
            
            created_at = datetime.now().isoformat()
            expires_at = None
            if expires_hours:
                from datetime import timedelta
                expires_at = (datetime.now() + timedelta(hours=expires_hours)).isoformat()
            
            alert = CustomAlert(
                alert_id=alert_id,
                symbol=symbol,
                alert_type=AlertType(alert_type),
                condition=AlertCondition(condition),
                description=description,
                parameters=parameters,
                created_at=created_at,
                expires_at=expires_at,
                enabled=True,
                triggered_count=0,
                last_triggered=None,
                one_time=one_time
            )
            
            self.alerts[alert_id] = alert
            self.save_alerts()
            
            logger.info(f"✅ Alert added: {description} ({alert_id})")
            return alert
            
        except Exception as e:
            logger.error(f"Error adding alert: {e}", exc_info=True)
            raise
    
    def remove_alert(self, alert_id: str) -> bool:
        """Remove an alert by ID and save to disk immediately"""
        if alert_id in self.alerts:
            alert = self.alerts[alert_id]
            del self.alerts[alert_id]
            # Save immediately with atomic write
            self.save_alerts()
            # Force filesystem sync to ensure write is complete before returning
            try:
                if self.storage_file.exists():
                    # Open file and force sync to disk (works on Windows and Linux)
                    with open(self.storage_file, 'r') as f:
                        os.fsync(f.fileno())
            except Exception as sync_error:
                logger.warning(f"Could not sync file after delete (non-critical): {sync_error}")
            logger.info(f"🗑️ Alert permanently removed: {alert.description} ({alert_id})")
            return True
        logger.warning(f"Alert not found for removal: {alert_id}")
        return False
    
    def get_alerts_for_symbol(self, symbol: str, enabled_only: bool = True) -> List[CustomAlert]:
        """Get all alerts for a specific symbol"""
        alerts = []
        for alert in self.alerts.values():
            if alert.symbol == symbol:
                if enabled_only and not alert.enabled:
                    continue
                # Check if expired
                if alert.expires_at:
                    if datetime.fromisoformat(alert.expires_at) < datetime.now():
                        continue
                alerts.append(alert)
        return alerts
    
    def get_all_alerts(self, enabled_only: bool = True) -> List[CustomAlert]:
        """Get all alerts"""
        alerts = []
        for alert in self.alerts.values():
            if enabled_only and not alert.enabled:
                continue
            # Check if expired
            if alert.expires_at:
                if datetime.fromisoformat(alert.expires_at) < datetime.now():
                    continue
            alerts.append(alert)
        return alerts
    
    def trigger_alert(self, alert_id: str) -> CustomAlert:
        """Mark an alert as triggered"""
        if alert_id in self.alerts:
            alert = self.alerts[alert_id]
            alert.triggered_count += 1
            alert.last_triggered = datetime.now().isoformat()
            self.save_alerts()
            logger.info(f"🔔 Alert triggered: {alert.description} (#{alert.triggered_count})")
            return alert
        return None
    
    def disable_alert(self, alert_id: str) -> bool:
        """Disable an alert without removing it"""
        if alert_id in self.alerts:
            self.alerts[alert_id].enabled = False
            self.save_alerts()
            return True
        return False
    
    def enable_alert(self, alert_id: str) -> bool:
        """Enable a disabled alert"""
        if alert_id in self.alerts:
            self.alerts[alert_id].enabled = True
            self.save_alerts()
            return True
        return False
    
    def save_alerts(self):
        """Save alerts to JSON file using atomic write to prevent corruption"""
        try:
            data = {}
            for alert_id, alert in self.alerts.items():
                alert_dict = asdict(alert)
                # Convert enums to strings
                alert_dict['alert_type'] = alert.alert_type.value
                alert_dict['condition'] = alert.condition.value
                data[alert_id] = alert_dict
            
            # Use atomic write: write to temp file, then replace (atomic on Windows/Linux)
            json_content = json.dumps(data, indent=2)
            
            # Create temp file in same directory as target file
            temp_file = self.storage_file.parent / f".{self.storage_file.name}.tmp"
            try:
                # Write to temp file
                temp_file.write_text(json_content, encoding='utf-8')
                # Atomic replace (works on both Windows and Linux)
                temp_file.replace(self.storage_file)
                logger.debug(f"Saved {len(self.alerts)} alerts to {self.storage_file}")
            except Exception as write_error:
                # Clean up temp file on error
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except:
                        pass
                raise write_error
        except Exception as e:
            logger.error(f"Error saving alerts: {e}", exc_info=True)
            raise
    
    def load_alerts(self):
        """Load alerts from JSON file"""
        try:
            if not self.storage_file.exists():
                logger.info("No existing alerts file found, starting fresh")
                return
            
            data = json.loads(self.storage_file.read_text())
            
            for alert_id, alert_dict in data.items():
                # Convert string enums back to Enum
                alert_dict['alert_type'] = AlertType(alert_dict['alert_type'])
                alert_dict['condition'] = AlertCondition(alert_dict['condition'])
                
                # Migration: Add one_time field if missing (default: True)
                if 'one_time' not in alert_dict:
                    alert_dict['one_time'] = True
                    logger.info(f"  Migrated alert {alert_id} to one_time=True")
                
                alert = CustomAlert(**alert_dict)
                self.alerts[alert_id] = alert
            
            # Save to persist migration
            if data:
                self.save_alerts()
            
            logger.info(f"Loaded {len(self.alerts)} alerts from {self.storage_file}")
        except Exception as e:
            logger.error(f"Error loading alerts: {e}", exc_info=True)
    
    def cleanup_expired(self) -> int:
        """Remove expired alerts, returns count removed"""
        now = datetime.now()
        expired_ids = []
        
        for alert_id, alert in self.alerts.items():
            if alert.expires_at:
                if datetime.fromisoformat(alert.expires_at) < now:
                    expired_ids.append(alert_id)
        
        for alert_id in expired_ids:
            del self.alerts[alert_id]
        
        if expired_ids:
            self.save_alerts()
            logger.info(f"Cleaned up {len(expired_ids)} expired alerts")
        
        return len(expired_ids)

