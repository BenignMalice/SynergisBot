# VPS Deployment Guide - MoneyBot Trading System

**Last Updated:** December 13, 2025  
**Purpose:** Comprehensive guide for deploying MoneyBot trading system on a VPS with optimal performance and reliability.

---

## 📋 Table of Contents

1. [Hardware Specifications](#hardware-specifications)
2. [Network Requirements](#network-requirements)
3. [Operating System](#operating-system)
4. [Reliability Considerations](#reliability-considerations)
5. [Deployment Checklist](#deployment-checklist)
6. [Monitoring & Maintenance](#monitoring--maintenance)
7. [VPS Provider Recommendations](#vps-provider-recommendations)

---

## 🖥️ Hardware Specifications

### **Minimum Requirements** (Basic Setup)

| Component | Specification | Rationale |
|-----------|--------------|-----------|
| **CPU** | 2 vCPU cores (2.0+ GHz) | Handles Python processes, MT5 connection, FastAPI server |
| **RAM** | 4 GB | Python runtime, MT5 data, SQLite database, web server |
| **Storage** | 40 GB SSD | OS, Python packages, logs, database, MT5 data |
| **Network** | 100 Mbps | Real-time data, API calls, Discord webhooks |

### **Recommended Specifications** (Production)

| Component | Specification | Rationale |
|-----------|--------------|-----------|
| **CPU** | 4 vCPU cores (3.0+ GHz) | Better concurrency for multiple monitoring loops |
| **RAM** | 8 GB | Comfortable headroom for spikes, caching, multiple symbols |
| **Storage** | 80 GB SSD | More log retention, historical data, backups |
| **Network** | 1 Gbps | Lower latency for MT5, faster API responses |

### **Optimal Specifications** (High-Frequency Trading)

| Component | Specification | Rationale |
|-----------|--------------|-----------|
| **CPU** | 6-8 vCPU cores (3.5+ GHz) | Maximum concurrency, micro-scalp monitoring (10-15s intervals) |
| **RAM** | 16 GB | Large symbol coverage, extensive historical data, caching |
| **Storage** | 160 GB NVMe SSD | Fastest I/O for database, MT5 tick data, real-time logs |
| **Network** | 10 Gbps | Ultra-low latency for MT5 execution, minimal slippage |

### **Resource Usage Breakdown**

```
Typical Memory Usage:
├── Python Runtime:          ~200-300 MB
├── MT5 Connection:          ~100-200 MB
├── FastAPI Server:          ~150-250 MB
├── Auto-Execution System:  ~100-150 MB
├── Intelligent Exit Manager: ~80-120 MB
├── SQLite Database:        ~50-100 MB
├── Logs & Caching:         ~200-500 MB
└── System Overhead:        ~500-1000 MB
─────────────────────────────────────────
Total:                      ~1.5-2.5 GB (minimum)
                            ~3-5 GB (recommended)
```

---

## 🌐 Network Requirements

### **Critical Network Metrics**

| Metric | Requirement | Impact |
|--------|-------------|--------|
| **Latency to MT5 Broker** | < 50ms | Execution speed, slippage |
| **Latency to Discord API** | < 100ms | Alert delivery |
| **Uptime** | 99.9%+ | System availability |
| **Bandwidth** | 10+ Mbps sustained | Data streaming, API calls |
| **DDoS Protection** | Recommended | Prevent service disruption |

### **Geographic Location**

**Priority Order:**
1. **Same region as MT5 broker** (lowest latency for execution)
2. **Same region as Discord API** (fast alert delivery)
3. **Major data center hub** (better peering, redundancy)

**Recommended Locations:**
- **Europe:** London, Frankfurt, Amsterdam (for European brokers)
- **US:** New York, Chicago (for US brokers)
- **Asia:** Singapore, Tokyo (for Asian brokers)

### **Network Configuration**

```bash
# Test MT5 broker latency
ping -c 10 your-broker-server.com

# Test Discord API latency
ping -c 10 discord.com

# Test general connectivity
curl -w "@-" -o /dev/null -s https://www.google.com <<'EOF'
     time_namelookup:  %{time_namelookup}\n
        time_connect:  %{time_connect}\n
     time_appconnect:  %{time_appconnect}\n
    time_pretransfer:  %{time_pretransfer}\n
       time_redirect:  %{time_redirect}\n
  time_starttransfer:  %{time_starttransfer}\n
                     ----------\n
          time_total:  %{time_total}\n
EOF
```

---

## 💻 Operating System

### **⚠️ CRITICAL: Windows Required for MT5**

**Important:** The `MetaTrader5` Python library requires the **MT5 terminal application** to be installed and running. MT5 is a **Windows-only application**, which means:

- ❌ **Linux cannot run MT5 natively**
- ⚠️ **Wine (Linux compatibility layer) is unreliable** for MT5 in production
- ✅ **Windows Server is REQUIRED** for reliable MT5 operation

### **Recommended: Windows Server 2022 or Windows Server 2019**

**Why Windows Server:**
- ✅ Native MT5 terminal support
- ✅ Official MetaTrader5 Python library compatibility
- ✅ Reliable execution and connection stability
- ✅ No compatibility layer overhead
- ✅ Full feature support (all MT5 functions work)

**Windows Server Options:**

| Version | Pros | Cons | Recommendation |
|---------|------|------|----------------|
| **Windows Server 2022** | Latest, best security | Higher cost | ✅ **Recommended** |
| **Windows Server 2019** | Stable, well-tested | Older | ✅ Good alternative |
| **Windows Server 2016** | Lower cost | End of support soon | ⚠️ Not recommended |
| **Windows 11 Pro** | Lower cost | Not server-grade | ⚠️ Acceptable for testing |

### **Alternative: Linux with Wine (NOT RECOMMENDED)**

**⚠️ Warning:** Running MT5 via Wine on Linux is:
- ❌ Unreliable (connection drops, crashes)
- ❌ Not officially supported by MetaQuotes
- ❌ Performance issues
- ❌ Potential execution delays
- ⚠️ Only suitable for testing, not production

**If you must use Linux + Wine:**

```bash
# 1. Install Wine
sudo apt update
sudo apt install -y wine64 wine64-tools winetricks

# 2. Install MT5 via Wine (manual process)
# Download MT5 installer, run via Wine
wine mt5setup.exe

# 3. Configure Wine for MT5
winetricks vcrun2019  # Visual C++ runtime
winetricks dotnet48   # .NET Framework (if needed)

# 4. Test MT5 connection
# (Expect potential issues)
```

**Recommendation:** Use Windows Server instead.

### **Windows Server Configuration Checklist**

```powershell
# 1. Update Windows
Install-WindowsUpdate -AcceptAll -AutoReboot

# 2. Install Python 3.10+
# Download from python.org or use winget
winget install Python.Python.3.11

# 3. Install Git
winget install Git.Git

# 4. Configure Windows Firewall
New-NetFirewallRule -DisplayName "MoneyBot FastAPI" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow

# 5. Configure timezone (critical for trading)
Set-TimeZone -Id "UTC"

# 6. Install MT5 Terminal
# Download from broker or MetaQuotes website
# Install to default location: C:\Program Files\MetaTrader 5

# 7. Configure MT5 Auto-Login
# Set up MT5 to auto-login on startup
# Configure in MT5: Tools → Options → Server → Auto-login

# 8. Install Windows Updates
# Ensure all security updates are installed
```

### **Windows Server Service Configuration**

```powershell
# Create service using NSSM (Non-Sucking Service Manager)
# Download NSSM from: https://nssm.cc/download

# Install service
nssm install MoneyBot "C:\Python311\python.exe" "C:\MoneyBot\chatgpt_bot.py"
nssm set MoneyBot AppDirectory "C:\MoneyBot"
nssm set MoneyBot DisplayName "MoneyBot Trading System"
nssm set MoneyBot Description "Automated trading system with MT5 integration"
nssm set MoneyBot Start SERVICE_AUTO_START
nssm set MoneyBot AppStdout "C:\MoneyBot\logs\service.log"
nssm set MoneyBot AppStderr "C:\MoneyBot\logs\service_error.log"

# Start service
nssm start MoneyBot

# Check status
nssm status MoneyBot
```

### **Linux Alternative (If You Must)**

If you absolutely cannot use Windows, consider:

1. **Windows VM on Linux Host**
   - Run Windows Server in a VM (VMware, VirtualBox, KVM)
   - Better isolation than Wine
   - Still some overhead

2. **Dual Boot**
   - Boot Windows for trading, Linux for other tasks
   - Not suitable for 24/7 operation

3. **Separate Windows VPS**
   - Run MT5 on Windows VPS
   - Run Python bot on Linux VPS
   - Communicate via API (requires custom integration)

---

## 🔒 Reliability Considerations

### **1. Uptime & Availability**

#### **Service Management**
```bash
# Use systemd for service management
sudo systemctl enable moneybot
sudo systemctl start moneybot
sudo systemctl status moneybot

# Auto-restart on failure
[Service]
Restart=always
RestartSec=10
StartLimitInterval=200
StartLimitBurst=5
```

#### **Process Monitoring**
```bash
# Install supervisor or systemd for auto-restart
# Monitor with health checks
# Set up alerts for service failures
```

### **2. Data Persistence**

#### **Database Backups**
```bash
# Daily SQLite backups
0 2 * * * /usr/local/bin/backup_moneybot_db.sh

# Backup script example:
#!/bin/bash
BACKUP_DIR="/backups/moneybot"
DATE=$(date +%Y%m%d_%H%M%S)
cp /path/to/moneybot.db "$BACKUP_DIR/moneybot_$DATE.db"
# Keep last 30 days
find "$BACKUP_DIR" -name "moneybot_*.db" -mtime +30 -delete
```

#### **Configuration Backups**
```bash
# Backup .env, config files, logs
tar -czf /backups/moneybot_config_$(date +%Y%m%d).tar.gz \
    /path/to/.env \
    /path/to/config/ \
    /path/to/logs/
```

### **3. Error Recovery**

#### **Circuit Breakers**
- ✅ Already implemented in Intelligent Exit Manager
- ✅ MT5 connection retry logic
- ✅ API call retries with exponential backoff

#### **Health Checks**
```python
# Implement health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "mt5_connected": mt5_service.is_connected(),
        "auto_execution_active": auto_execution_system.is_running(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
```

### **4. Logging & Monitoring**

#### **Log Management**
```bash
# Configure logrotate
/path/to/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 user group
}
```

#### **Monitoring Tools**
- **htop/iotop**: Resource monitoring
- **netstat/ss**: Network monitoring
- **journalctl**: System logs
- **Prometheus + Grafana**: Advanced monitoring (optional)
- **Sentry**: Error tracking (optional)

### **5. Security**

#### **SSH Hardening**
```bash
# Disable password authentication
PasswordAuthentication no
PubkeyAuthentication yes

# Change default port (optional)
Port 2222

# Limit login attempts
MaxAuthTries 3
```

#### **Firewall Rules**
```bash
# Only allow necessary ports
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 8000/tcp  # FastAPI (if needed)
```

#### **Fail2Ban**
```bash
# Protect against brute force
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### **6. MT5 Connection Reliability**

#### **Connection Monitoring**
- ✅ Auto-reconnect on disconnect
- ✅ Connection health checks
- ✅ Fallback mechanisms

#### **Network Redundancy**
- Consider multiple network interfaces
- Use VPN as backup (if broker allows)
- Monitor MT5 connection latency

---

## ✅ Deployment Checklist

### **Pre-Deployment**

- [ ] Choose VPS provider and location
- [ ] Select appropriate hardware specs
- [ ] Verify network latency to MT5 broker
- [ ] Set up SSH key authentication
- [ ] Configure firewall rules
- [ ] Install OS and dependencies

### **Application Setup**

- [ ] Clone repository
- [ ] Create Python virtual environment
- [ ] Install dependencies (`pip install -r requirements.txt`)
- [ ] Configure `.env` file with credentials
- [ ] Test MT5 connection
- [ ] Verify database initialization
- [ ] Test auto-execution system
- [ ] Configure logging

### **Service Configuration**

- [ ] Create systemd service file
- [ ] Enable auto-start on boot
- [ ] Configure auto-restart on failure
- [ ] Set up log rotation
- [ ] Configure backup scripts
- [ ] Test service restart

### **Monitoring Setup**

- [ ] Set up health check endpoint
- [ ] Configure alert notifications (Discord/Email)
- [ ] Test error reporting
- [ ] Verify log collection
- [ ] Set up resource monitoring

### **Security Hardening**

- [ ] Disable password SSH authentication
- [ ] Configure firewall
- [ ] Set up fail2ban
- [ ] Review file permissions
- [ ] Secure `.env` file (600 permissions)
- [ ] Enable automatic security updates

### **Testing**

- [ ] Test MT5 connection stability
- [ ] Test auto-execution plan creation
- [ ] Test plan monitoring and execution
- [ ] Test intelligent exit system
- [ ] Test Discord alerts
- [ ] Test error recovery
- [ ] Load test (if applicable)

---

## 📊 Monitoring & Maintenance

### **Daily Checks**

```bash
# Check service status
sudo systemctl status moneybot

# Check logs for errors
tail -n 100 /path/to/logs/moneybot.log | grep -i error

# Check MT5 connection
# (via health check endpoint or logs)

# Check disk space
df -h

# Check memory usage
free -h
```

### **Weekly Maintenance**

- Review logs for patterns
- Check database size
- Verify backups are running
- Review error rates
- Check resource usage trends

### **Monthly Maintenance**

- Update system packages
- Review and rotate old logs
- Analyze performance metrics
- Review security logs
- Test disaster recovery procedures

---

## 🏢 VPS Provider Recommendations

### **Budget Tier** ($5-15/month)

| Provider | Specs | Price | Notes |
|----------|-------|-------|-------|
| **DigitalOcean** | 2 vCPU, 4GB RAM, 80GB SSD | $24/mo | Excellent docs, good performance |
| **Vultr** | 2 vCPU, 4GB RAM, 80GB SSD | $24/mo | Good global coverage |
| **Linode** | 2 vCPU, 4GB RAM, 80GB SSD | $24/mo | Reliable, good support |
| **Hetzner** | 2 vCPU, 4GB RAM, 40GB SSD | €8.29/mo | Best value, EU-based |

### **Production Tier** ($20-50/month)

| Provider | Specs | Price | Notes |
|----------|-------|-------|-------|
| **DigitalOcean** | 4 vCPU, 8GB RAM, 160GB SSD | $48/mo | Recommended for production |
| **AWS Lightsail** | 4 vCPU, 8GB RAM, 160GB SSD | $40/mo | AWS ecosystem integration |
| **Vultr** | 4 vCPU, 8GB RAM, 160GB SSD | $48/mo | Good performance |
| **Hetzner** | 4 vCPU, 8GB RAM, 160GB SSD | €16.90/mo | Excellent value |

### **High-Performance Tier** ($50-100/month)

| Provider | Specs | Price | Notes |
|----------|-------|-------|-------|
| **DigitalOcean** | 8 vCPU, 16GB RAM, 320GB NVMe | $192/mo | Premium performance |
| **AWS EC2** | c6i.xlarge (4 vCPU, 8GB) | ~$150/mo | Enterprise-grade |
| **Hetzner** | 8 vCPU, 16GB RAM, 320GB NVMe | €33.90/mo | Best value for specs |

### **Windows VPS Provider Comparison**

| Feature | Vultr | DigitalOcean | AWS | Azure | Contabo |
|---------|-------|-------------|-----|-------|---------|
| **Windows Support** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Ease of Use** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Performance** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Value** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Support** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **Global Coverage** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

### **Windows VPS Provider Recommendations**

**Budget Tier ($20-40/month):**
- **Contabo** - Windows Server 2022, 4 vCPU, 8GB RAM, 200GB SSD - €19.99/mo
- **Vultr** - Windows Server 2022, 2 vCPU, 4GB RAM, 80GB SSD - $24/mo

**Production Tier ($40-80/month):**
- **Vultr** - Windows Server 2022, 4 vCPU, 8GB RAM, 160GB SSD - $48/mo ✅ **Recommended**
- **DigitalOcean** - Windows Server 2022, 4 vCPU, 8GB RAM, 160GB SSD - $48/mo
- **AWS Lightsail** - Windows Server 2022, 4 vCPU, 8GB RAM, 160GB SSD - $40/mo

**High-Performance Tier ($80-150/month):**
- **Vultr** - Windows Server 2022, 8 vCPU, 16GB RAM, 320GB NVMe - $96/mo
- **AWS EC2** - Windows Server 2022, c6i.xlarge (4 vCPU, 8GB) - ~$150/mo
- **Azure** - Windows Server 2022, Standard_D4s_v3 (4 vCPU, 16GB) - ~$120/mo

### **Recommendation**

**For Most Users:**
- **Vultr Windows VPS** - Best balance of price, performance, and Windows support ✅
- **Contabo** - Best value if budget is tight

**For Production:**
- **Vultr** or **DigitalOcean** - Good Windows support, reliable, good performance

**For High-Frequency:**
- **Vultr** (dedicated) or **AWS EC2** - Maximum performance with Windows

---

## 🚀 Quick Start Commands

### **Initial Windows VPS Setup**

```powershell
# 1. Connect to VPS via RDP
# Use Remote Desktop Connection (mstsc.exe)
# Enter VPS IP address and credentials

# 2. Install Python 3.11+
# Download from python.org or use winget
winget install Python.Python.3.11

# 3. Install Git
winget install Git.Git

# 4. Clone repository
cd C:\
git clone https://github.com/your-repo/moneybot.git
cd moneybot

# 5. Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# 6. Install dependencies
pip install -r requirements.txt

# 7. Install MT5 Terminal
# Download MT5 installer from broker or MetaQuotes
# Install to: C:\Program Files\MetaTrader 5
# Configure auto-login in MT5 settings

# 8. Configure environment
copy .env.example .env
notepad .env  # Edit with your credentials

# 9. Test MT5 connection
python -c "from infra.mt5_service import MT5Service; s = MT5Service(); print('Connected:', s.connect())"
```

### **Create Windows Service (Using NSSM)**

```powershell
# 1. Download NSSM
# Visit: https://nssm.cc/download
# Extract to: C:\nssm

# 2. Install service
cd C:\nssm\win64
.\nssm.exe install MoneyBot "C:\Python311\python.exe" "C:\moneybot\chatgpt_bot.py"

# 3. Configure service
.\nssm.exe set MoneyBot AppDirectory "C:\moneybot"
.\nssm.exe set MoneyBot DisplayName "MoneyBot Trading System"
.\nssm.exe set MoneyBot Description "Automated trading system with MT5 integration"
.\nssm.exe set MoneyBot Start SERVICE_AUTO_START
.\nssm.exe set MoneyBot AppStdout "C:\moneybot\logs\service.log"
.\nssm.exe set MoneyBot AppStderr "C:\moneybot\logs\service_error.log"

# 4. Set environment variables (if needed)
.\nssm.exe set MoneyBot AppEnvironmentExtra "PATH=C:\moneybot\venv\Scripts"

# 5. Start service
.\nssm.exe start MoneyBot

# 6. Check status
.\nssm.exe status MoneyBot

# 7. View logs
Get-Content "C:\moneybot\logs\service.log" -Tail 50
```

### **Alternative: Task Scheduler (Simpler, Less Reliable)**

```powershell
# Create scheduled task that runs on startup
$action = New-ScheduledTaskAction -Execute "C:\Python311\python.exe" -Argument "C:\moneybot\chatgpt_bot.py" -WorkingDirectory "C:\moneybot"
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName "MoneyBot" -Action $action -Trigger $trigger -Principal $principal -Description "MoneyBot Trading System"
```

### **Linux Setup (If Using Wine - NOT RECOMMENDED)**

```bash
# 1. Connect to VPS
ssh root@your-vps-ip

# 2. Install Wine and dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install -y wine64 wine64-tools winetricks

# 3. Install MT5 via Wine (manual, unreliable)
# Download MT5 installer
wget https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe
wine mt5setup.exe

# 4. Configure Wine for MT5
winetricks vcrun2019 dotnet48

# 5. Install Python and dependencies (same as Windows)
# ... (rest of setup similar to Windows)

# ⚠️ WARNING: MT5 via Wine is unreliable. Use Windows VPS instead.
```

---

## 📝 Additional Notes

### **Time Synchronization**

Critical for trading systems - ensure NTP is configured:

```bash
sudo timedatectl set-ntp true
sudo timedatectl status
```

### **Resource Limits**

Consider setting resource limits to prevent runaway processes:

```bash
# Edit limits.conf
sudo nano /etc/security/limits.conf

# Add:
moneybot soft nofile 65536
moneybot hard nofile 65536
```

### **Backup Strategy**

1. **Database**: Daily SQLite backups
2. **Configuration**: Weekly `.env` and config backups
3. **Logs**: Rotate daily, keep 30 days
4. **Off-site**: Consider cloud storage (S3, Backblaze) for critical backups

---

## 🆘 Troubleshooting

### **Common Issues**

1. **MT5 Connection Fails**
   - Check firewall rules
   - Verify broker server address
   - Check network connectivity

2. **High Memory Usage**
   - Review log sizes
   - Check for memory leaks
   - Increase VPS RAM if needed

3. **Service Won't Start**
   - Check logs: `journalctl -u moneybot -n 50`
   - Verify Python path
   - Check file permissions

4. **Slow Execution**
   - Check CPU usage
   - Review network latency
   - Optimize database queries

---

**Last Updated:** December 13, 2025  
**Version:** 1.0

