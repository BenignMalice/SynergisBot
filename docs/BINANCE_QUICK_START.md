# 🚀 Binance Integration - Quick Start Guide

**Time to get running: 2 minutes**

---

## 📋 Prerequisites

✅ You already have:
- TelegramMoneyBot.v7 installed
- MT5 connected and working
- Python 3.8+ with required packages

✅ What's new (already installed):
- `websockets` library (for Binance streams)
- Phase 2 components (already built and tested)

---

## 🎯 Option 1: Start Desktop Agent (Recommended)

**This automatically starts Binance + Phone Control:**

```powershell
cd c:\mt5-gpt\TelegramMoneyBot.v7
python desktop_agent.py
```

**What happens:**
1. ✅ Connects to MT5
2. ✅ Starts Binance streams (7 symbols: BTC, XAU, EUR/USD, GBP/USD, USD/JPY, GBP/JPY, EUR/JPY)
3. ✅ Begins offset calibration
4. ✅ Connects to command hub
5. ✅ Ready for phone commands

**You'll see:**
```
🤖 TelegramMoneyBot Desktop Agent - STARTING
🔧 Initializing services...
✅ MT5Service connected
📡 Starting Binance streaming service...
✅ Binance streams started for: BTCUSDT, XAUUSD, EURUSD, GBPUSD, USDJPY, GBPJPY, EURJPY
✅ Circuit Breaker initialized
✅ Exposure Guard initialized
✅ Signal Pre-Filter initialized
🔌 Connected to command hub
✅ Authenticated with hub - ready to receive commands
```

---

## 🎯 Option 2: Test First

**Run tests to verify everything works:**

```powershell
cd c:\mt5-gpt\TelegramMoneyBot.v7
python test_phase2.py
```

**Expected result:**
```
✅ Passed: 5
❌ Failed: 0
🎉 ALL TESTS PASSED!
```

---

## 🎯 Option 3: Standalone Binance Feed

**Run Binance stream without phone control:**

```powershell
cd c:\mt5-gpt\TelegramMoneyBot.v7
python start_binance_feed.py
```

**Or with custom symbols:**
```powershell
python start_binance_feed.py btcusdt ethusdt xauusd gbpusd eurusd
```

---

## 📱 Using From Your Phone

### 1. Check Feed Health

In ChatGPT (Custom GPT), say:

```
"Check Binance feed status"
```

**You'll get:**
```
📡 Binance Feed Status - All Symbols

Total Symbols: 7
✅ Healthy: 7
⚠️ Warning: 0
🔴 Critical: 0

✅ BTCUSDT: Offset +3.2 pips
✅ XAUUSD: Offset +0.5 pips
✅ EURUSD: Offset -0.2 pips
✅ GBPUSD: Offset +0.8 pips
✅ USDJPY: Offset -0.1 pips
✅ GBPJPY: Offset +1.2 pips
✅ EURJPY: Offset +0.3 pips
```

### 2. Analyse with Binance Data

```
"Analyse BTCUSD"
```

Desktop agent will:
- Pull MT5 data
- Check Binance feed health
- Run analysis
- Return recommendation

### 3. Execute with Safety Checks

```
"Execute this trade"
```

Desktop agent will:
- ✅ Validate feed health
- ✅ Check circuit breaker
- ✅ Check exposure limits
- ✅ Validate offset (<100 pips)
- ✅ Check spread (<3x normal)
- ✅ Verify confidence (≥70%)
- ✅ Adjust prices for MT5 offset
- ✅ Execute if all checks pass

---

## 🔧 Customization

### Change Monitored Symbols

Edit `desktop_agent.py` (line ~1231):

```python
# Current symbols (already configured):
symbols_to_stream = [
    "btcusdt",   # Bitcoin
    "xauusd",    # Gold
    "eurusd",    # Euro/Dollar
    "gbpusd",    # Pound/Dollar
    "usdjpy",    # Dollar/Yen
    "gbpjpy",    # Pound/Yen
    "eurjpy"     # Euro/Yen
]

# To add more (like Ethereum):
symbols_to_stream.append("ethusdt")
```

### Change Safety Thresholds

Edit `app/engine/signal_prefilter.py`:

```python
# Change minimum confidence
min_confidence=70  # Change to 75 or 80 for stricter

# Or in desktop_agent.py (line ~1264):
registry.signal_prefilter = SignalPreFilter(
    binance_service=registry.binance_service,
    circuit_breaker=registry.circuit_breaker,
    exposure_guard=registry.exposure_guard,
    min_confidence=80  # Increase for stricter validation
)
```

### Change Offset Limits

Edit `infra/feed_validator.py`:

```python
# Change max offset
max_offset=100.0  # Change to 150.0 for more tolerance

# Or in initialization:
validator = FeedValidator(max_offset=150.0)
```

---

## 🚨 Troubleshooting

### Problem: "Binance feed not running"

**Solution:**
```powershell
# Kill any existing agent
# Then restart:
python desktop_agent.py
```

### Problem: "Offset not calibrated"

**Solution:**
- Wait 15-30 seconds after startup
- System needs 10-15 ticks to calculate offset
- Will use Binance prices as-is until calibrated

### Problem: "Feed health critical"

**Solution:**
1. Check MT5 is running
2. Verify internet connection
3. Wait 30 seconds for feed to stabilize

### Problem: "Trade blocked by safety filter"

**Solution:**
- This is working as intended!
- Check the reason (confidence, offset, spread, etc.)
- Fix the issue or wait for better conditions

---

## 📊 Status Commands

### Check Everything

In terminal (while agent running):

```python
# In Python console or add to desktop_agent.py
registry.binance_service.print_status()
```

**Output:**
```
╔══════════════════════════════════════════════════════╗
║           BINANCE SERVICE STATUS                     ║
╚══════════════════════════════════════════════════════╝
Running: ✅ YES
Symbols: BTCUSDT, ETHUSDT, XAUUSD
Connected: 3/3

✅ BTCUSDT      | Ticks:  850 | Age:   2.5s | Offset: +3.2
✅ ETHUSDT      | Ticks:  720 | Age:   3.1s | Offset: -1.8
✅ XAUUSD       | Ticks:  690 | Age:   2.8s | Offset: +0.5
```

---

## 🎓 What Each File Does

| File | Purpose | When to Use |
|------|---------|-------------|
| `desktop_agent.py` | Main agent with Binance + Phone Control | **START THIS** for full system |
| `start_binance_feed.py` | Standalone Binance stream | Testing or monitoring only |
| `test_phase2.py` | Integration tests | Verify after changes |
| `test_phase1.py` | Component tests | Debug specific issues |
| `infra/binance_service.py` | High-level Binance API | Import for custom scripts |
| `app/engine/signal_prefilter.py` | Safety validation | Customize thresholds |

---

## ✅ Verification Checklist

After starting, verify:

- [ ] Desktop agent shows "✅ Binance streams started"
- [ ] Desktop agent shows "✅ Connected to command hub"
- [ ] Phone command "Check Binance feed" works
- [ ] Status shows "Healthy" for all symbols
- [ ] Offset is calibrated (not "N/A")
- [ ] Test execution validates correctly

---

## 🎯 Quick Commands Reference

```powershell
# Start full system
python desktop_agent.py

# Run tests
python test_phase2.py

# Standalone Binance feed
python start_binance_feed.py

# With custom symbols
python start_binance_feed.py btcusdt ethusdt xauusd gbpusd
```

---

## 📚 More Info

- **Full documentation:** `PHASE2_BINANCE_INTEGRATION_COMPLETE.md`
- **Upgrade plan:** `BINANCE_STREAMING_UPGRADE_PLAN.md`
- **Phone control:** `PHONE_CONTROL_QUICKSTART.md`

---

**That's it! You're ready to trade with Binance data integration.** 🚀

**Questions?** Run `python test_phase2.py` to verify everything is working.

