#!/usr/bin/env python3
"""
Production Deployment Monitor for TelegramMoneyBot v8.0
Real-time monitoring of production deployment and system health
"""

import asyncio
import json
import logging
import time
import psutil
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import sys
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProductionDeploymentMonitor:
    """Monitor production deployment in real-time"""
    
    def __init__(self):
        self.monitoring_start_time = datetime.now()
        self.monitoring_data = {
            "system_health": {},
            "performance_metrics": {},
            "deployment_status": {},
            "alerts": [],
            "errors": []
        }
        self.alert_thresholds = {
            "cpu_usage": 80.0,
            "memory_usage": 90.0,
            "disk_usage": 85.0,
            "latency_ms": 200.0,
            "error_rate": 5.0
        }
    
    async def start_monitoring(self):
        """Start production monitoring"""
        try:
            logger.info("📊 Starting Production Deployment Monitoring")
            logger.info("=" * 60)
            
            # Start monitoring loop
            await self._monitoring_loop()
            
        except Exception as e:
            logger.error(f"❌ Monitoring failed: {e}")
            raise
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        logger.info("🔄 Starting monitoring loop...")
        
        while True:
            try:
                # Collect system metrics
                await self._collect_system_metrics()
                
                # Check deployment status
                await self._check_deployment_status()
                
                # Validate system health
                await self._validate_system_health()
                
                # Check for alerts
                await self._check_alerts()
                
                # Generate monitoring report
                await self._generate_monitoring_report()
                
                # Wait before next check
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except KeyboardInterrupt:
                logger.info("🛑 Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Monitoring error: {e}")
                await asyncio.sleep(5)  # Wait before retry
    
    async def _collect_system_metrics(self):
        """Collect system performance metrics"""
        try:
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('.')
            disk_usage = (disk.used / disk.total) * 100
            
            # Network stats
            network = psutil.net_io_counters()
            
            # Process stats
            process = psutil.Process()
            process_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            self.monitoring_data["performance_metrics"] = {
                "timestamp": datetime.now().isoformat(),
                "cpu_usage_percent": cpu_usage,
                "memory_usage_percent": memory_usage,
                "disk_usage_percent": disk_usage,
                "process_memory_mb": process_memory,
                "network_bytes_sent": network.bytes_sent,
                "network_bytes_recv": network.bytes_recv
            }
            
            logger.info(f"📊 Metrics: CPU {cpu_usage:.1f}%, Memory {memory_usage:.1f}%, Disk {disk_usage:.1f}%")
            
        except Exception as e:
            logger.error(f"❌ Error collecting metrics: {e}")
    
    async def _check_deployment_status(self):
        """Check deployment status"""
        try:
            # Check if main processes are running
            processes = {
                "trading_system": self._check_process("trade_bot.py"),
                "monitoring_dashboard": self._check_process("production_monitoring_dashboard.py"),
                "api_server": self._check_process("app/main_api.py")
            }
            
            # Check database connectivity
            db_status = await self._check_database_status()
            
            # Check MT5 connection
            mt5_status = await self._check_mt5_status()
            
            # Check Telegram bot
            telegram_status = await self._check_telegram_status()
            
            self.monitoring_data["deployment_status"] = {
                "timestamp": datetime.now().isoformat(),
                "processes": processes,
                "database": db_status,
                "mt5": mt5_status,
                "telegram": telegram_status,
                "overall_status": "HEALTHY" if all(processes.values()) else "DEGRADED"
            }
            
            status = "HEALTHY" if all(processes.values()) else "DEGRADED"
            logger.info(f"🔍 Deployment Status: {status}")
            
        except Exception as e:
            logger.error(f"❌ Error checking deployment status: {e}")
    
    def _check_process(self, process_name: str) -> bool:
        """Check if a process is running"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if process_name in ' '.join(proc.info['cmdline'] or []):
                    return True
            return False
        except Exception:
            return False
    
    async def _check_database_status(self) -> Dict[str, Any]:
        """Check database status"""
        try:
            import sqlite3
            
            # Check main database
            main_db_status = "HEALTHY"
            if os.path.exists('data/bot.sqlite'):
                conn = sqlite3.connect('data/bot.sqlite')
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
                table_count = cursor.fetchone()[0]
                conn.close()
            else:
                main_db_status = "NOT_FOUND"
                table_count = 0
            
            # Check journal database
            journal_db_status = "HEALTHY"
            if not os.path.exists('data/journal.sqlite'):
                journal_db_status = "NOT_FOUND"
            
            return {
                "main_database": main_db_status,
                "journal_database": journal_db_status,
                "table_count": table_count,
                "overall": "HEALTHY" if main_db_status == "HEALTHY" else "DEGRADED"
            }
            
        except Exception as e:
            return {"overall": "ERROR", "error": str(e)}
    
    async def _check_mt5_status(self) -> Dict[str, Any]:
        """Check MT5 status"""
        try:
            import MetaTrader5 as mt5
            
            if not mt5.initialize():
                return {"status": "NOT_CONNECTED", "error": "MT5 initialization failed"}
            
            account_info = mt5.account_info()
            if account_info is None:
                return {"status": "NO_ACCOUNT", "error": "Account info not available"}
            
            symbols = mt5.symbols_get()
            symbol_count = len(symbols) if symbols else 0
            
            mt5.shutdown()
            
            return {
                "status": "CONNECTED",
                "account": account_info.login,
                "symbols": symbol_count,
                "overall": "HEALTHY"
            }
            
        except Exception as e:
            return {"status": "ERROR", "error": str(e), "overall": "DEGRADED"}
    
    async def _check_telegram_status(self) -> Dict[str, Any]:
        """Check Telegram bot status"""
        try:
            token = os.getenv('TELEGRAM_TOKEN')
            if not token:
                return {"status": "NO_TOKEN", "overall": "DEGRADED"}
            
            url = f"https://api.telegram.org/bot{token}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                bot_info = response.json()
                if bot_info.get('ok'):
                    return {
                        "status": "CONNECTED",
                        "bot_name": bot_info['result']['first_name'],
                        "overall": "HEALTHY"
                    }
                else:
                    return {"status": "API_ERROR", "overall": "DEGRADED"}
            else:
                return {"status": "HTTP_ERROR", "code": response.status_code, "overall": "DEGRADED"}
                
        except Exception as e:
            return {"status": "ERROR", "error": str(e), "overall": "DEGRADED"}
    
    async def _validate_system_health(self):
        """Validate overall system health"""
        try:
            metrics = self.monitoring_data.get("performance_metrics", {})
            deployment = self.monitoring_data.get("deployment_status", {})
            
            # Check performance thresholds
            health_issues = []
            
            cpu_usage = metrics.get("cpu_usage_percent", 0)
            if cpu_usage > self.alert_thresholds["cpu_usage"]:
                health_issues.append(f"High CPU usage: {cpu_usage:.1f}%")
            
            memory_usage = metrics.get("memory_usage_percent", 0)
            if memory_usage > self.alert_thresholds["memory_usage"]:
                health_issues.append(f"High memory usage: {memory_usage:.1f}%")
            
            disk_usage = metrics.get("disk_usage_percent", 0)
            if disk_usage > self.alert_thresholds["disk_usage"]:
                health_issues.append(f"High disk usage: {disk_usage:.1f}%")
            
            # Check deployment status
            if deployment.get("overall_status") != "HEALTHY":
                health_issues.append("Deployment status not healthy")
            
            # Determine overall health
            if not health_issues:
                overall_health = "HEALTHY"
            elif len(health_issues) <= 2:
                overall_health = "DEGRADED"
            else:
                overall_health = "CRITICAL"
            
            self.monitoring_data["system_health"] = {
                "timestamp": datetime.now().isoformat(),
                "overall_health": overall_health,
                "issues": health_issues,
                "metrics_status": "GOOD" if not health_issues else "WARNING"
            }
            
            logger.info(f"🏥 System Health: {overall_health}")
            if health_issues:
                for issue in health_issues:
                    logger.warning(f"⚠️ {issue}")
            
        except Exception as e:
            logger.error(f"❌ Error validating system health: {e}")
    
    async def _check_alerts(self):
        """Check for alert conditions"""
        try:
            metrics = self.monitoring_data.get("performance_metrics", {})
            health = self.monitoring_data.get("system_health", {})
            
            alerts = []
            
            # Performance alerts
            cpu_usage = metrics.get("cpu_usage_percent", 0)
            if cpu_usage > self.alert_thresholds["cpu_usage"]:
                alerts.append({
                    "type": "PERFORMANCE",
                    "severity": "WARNING",
                    "message": f"High CPU usage: {cpu_usage:.1f}%",
                    "timestamp": datetime.now().isoformat()
                })
            
            memory_usage = metrics.get("memory_usage_percent", 0)
            if memory_usage > self.alert_thresholds["memory_usage"]:
                alerts.append({
                    "type": "PERFORMANCE",
                    "severity": "WARNING", 
                    "message": f"High memory usage: {memory_usage:.1f}%",
                    "timestamp": datetime.now().isoformat()
                })
            
            # Health alerts
            if health.get("overall_health") == "CRITICAL":
                alerts.append({
                    "type": "SYSTEM",
                    "severity": "CRITICAL",
                    "message": "System health is critical",
                    "timestamp": datetime.now().isoformat()
                })
            
            # Store alerts
            self.monitoring_data["alerts"] = alerts
            
            # Log alerts
            for alert in alerts:
                if alert["severity"] == "CRITICAL":
                    logger.error(f"🚨 {alert['message']}")
                else:
                    logger.warning(f"⚠️ {alert['message']}")
            
        except Exception as e:
            logger.error(f"❌ Error checking alerts: {e}")
    
    async def _generate_monitoring_report(self):
        """Generate monitoring report"""
        try:
            monitoring_duration = datetime.now() - self.monitoring_start_time
            
            report = {
                "monitoring_id": f"MONITOR_{int(time.time())}",
                "start_time": self.monitoring_start_time.isoformat(),
                "current_time": datetime.now().isoformat(),
                "duration_minutes": monitoring_duration.total_seconds() / 60,
                "system_health": self.monitoring_data.get("system_health", {}),
                "performance_metrics": self.monitoring_data.get("performance_metrics", {}),
                "deployment_status": self.monitoring_data.get("deployment_status", {}),
                "active_alerts": len(self.monitoring_data.get("alerts", [])),
                "overall_status": "HEALTHY" if not self.monitoring_data.get("alerts") else "ALERTS_ACTIVE"
            }
            
            # Save report every 5 minutes
            if int(time.time()) % 300 == 0:  # Every 5 minutes
                with open(f'logs/monitoring_report_{int(time.time())}.json', 'w') as f:
                    json.dump(report, f, indent=2)
                
                logger.info("📊 Monitoring report saved")
            
        except Exception as e:
            logger.error(f"❌ Error generating monitoring report: {e}")

async def main():
    """Main monitoring function"""
    try:
        monitor = ProductionDeploymentMonitor()
        await monitor.start_monitoring()
        
    except KeyboardInterrupt:
        logger.info("🛑 Monitoring stopped by user")
    except Exception as e:
        logger.error(f"❌ Monitoring failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
