# 🚀 Windows Task Scheduler - Quick Start Guide

## ⚡ **FASTEST SETUP (5 Minutes)**

### **Method 1: Using Batch File (Recommended)**

1. **Open Task Scheduler:**
   - Press `Windows + R`
   - Type: `taskschd.msc`
   - Press Enter

2. **Create Basic Task:**
   - Right-click "Task Scheduler Library" → "Create Basic Task"
   - Name: `News Sentiment Enhancement`
   - Click "Next"

3. **Set Trigger:**
   - Select "Daily"
   - Start time: Now
   - Click "Next"

4. **Set Action:**
   - Select "Start a program"
   - Program: `C:\mt5-gpt\TelegramMoneyBot.v7\run_news_sentiment.bat`
   - Start in: `C:\mt5-gpt\TelegramMoneyBot.v7`
   - Click "Next" → "Finish"

5. **Configure Advanced:**
   - Check "Open Properties dialog"
   - **Triggers tab:** Edit trigger → Check "Repeat every 4 hours"
   - **General tab:** Check "Run with highest privileges"
   - Click "OK"

### **Method 2: Using PowerShell (Advanced)**

1. **Create Task with PowerShell:**
   ```powershell
   # Run as Administrator
   $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File C:\mt5-gpt\TelegramMoneyBot.v7\run_news_sentiment.ps1"
   $trigger = New-ScheduledTaskTrigger -Daily -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 4) -RepetitionDuration (New-TimeSpan -Days 365)
   $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
   Register-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -TaskName "News Sentiment Enhancement" -Description "Automatically enhance news events with sentiment analysis"
   ```

---

## ✅ **Verification Steps**

### **1. Test the Script:**
```bash
# Test batch file
C:\mt5-gpt\TelegramMoneyBot.v7\run_news_sentiment.bat

# Test PowerShell script
powershell -ExecutionPolicy Bypass -File C:\mt5-gpt\TelegramMoneyBot.v7\run_news_sentiment.ps1
```

### **2. Check Task Status:**
- Open Task Scheduler
- Find "News Sentiment Enhancement"
- Check "Last Run Result" = 0x0 (success)

### **3. View Logs:**
- Check `news_sentiment.log` file (PowerShell version)
- Check Task Scheduler History tab

---

## 📊 **What Happens Every 4 Hours**

1. **Task Scheduler** runs the automation script
2. **Script** loads existing news events (115 events)
3. **Enhancement** adds sentiment analysis to each event
4. **Save** updated data to `data/news_events.json`
5. **Log** success/failure for monitoring

---

## 🔧 **Troubleshooting**

### **Common Issues:**

| Issue | Solution |
|-------|----------|
| Task not running | Check Python PATH, use full path to python.exe |
| Permission denied | Enable "Run with highest privileges" |
| Script not found | Verify file paths in Task Scheduler |
| Working directory error | Set "Start in" field correctly |

### **Quick Fixes:**

```bash
# Test Python path
python --version

# Test script manually
cd C:\mt5-gpt\TelegramMoneyBot.v7
python fetch_news_sentiment.py

# Check file exists
dir run_news_sentiment.bat
```

---

## 📈 **Monitoring**

### **Task Scheduler Monitoring:**
- **Last Run Time:** When it last executed
- **Last Run Result:** 0x0 = success, 0x1 = error
- **Next Run Time:** When it will run next
- **Status:** Ready/Running/Disabled

### **File Monitoring:**
- **Check:** `data/news_events.json` timestamp
- **Verify:** Enhanced events have sentiment fields
- **Log:** `news_sentiment.log` (PowerShell version)

---

## 🎯 **Expected Results**

### **Every 4 Hours:**
```
Starting News Sentiment Enhancement...
Timestamp: 2025/10/14 22:37:39
SUCCESS: News sentiment enhancement completed!
Timestamp: 2025/10/14 22:37:39
```

### **Enhanced Data:**
```json
{
  "time": "2025-10-12T21:30:00Z",
  "description": "BusinessNZ Services Index",
  "sentiment": "NEUTRAL",
  "trading_implication": "Low impact - minimal market movement expected",
  "risk_level": "LOW",
  "enhanced_at": "2025-10-14T22:37:39.352000"
}
```

---

## 🚀 **Benefits**

✅ **Automated** - Runs every 4 hours without manual intervention
✅ **Reliable** - Windows Task Scheduler is robust and stable
✅ **Monitorable** - Full logging and status tracking
✅ **Scalable** - Easy to add more automation tasks
✅ **Free** - No additional software or services needed

---

## 📝 **Quick Reference**

**Task Name:** News Sentiment Enhancement
**Frequency:** Every 4 hours
**Script:** `run_news_sentiment.bat` or `run_news_sentiment.ps1`
**Working Directory:** `C:\mt5-gpt\TelegramMoneyBot.v7`
**Expected Result:** 0x0 (success)

**To Disable:** Right-click task → "Disable"
**To Modify:** Right-click task → "Properties"
**To Delete:** Right-click task → "Delete"

---

**🎉 Your news trading system is now fully automated! 🚀📰💰**
