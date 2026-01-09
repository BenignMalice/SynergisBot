# 🕒 Windows Task Scheduler Setup for News Trading Automation

## 📋 **Overview**

This guide will help you set up Windows Task Scheduler to automatically run the news sentiment enhancement process every 4 hours, keeping your news data fresh and up-to-date.

---

## 🎯 **What We're Automating**

**Script:** `fetch_news_sentiment.py`
**Frequency:** Every 4 hours
**Purpose:** Automatically enhance news events with sentiment analysis
**Result:** Always up-to-date news data with trading implications

---

## 🚀 **Step-by-Step Setup**

### **Step 1: Open Task Scheduler**

1. **Press `Windows + R`** to open Run dialog
2. **Type:** `taskschd.msc`
3. **Press Enter** to open Task Scheduler

### **Step 2: Create Basic Task**

1. **Right-click** on "Task Scheduler Library" in the left panel
2. **Select:** "Create Basic Task..."
3. **Name:** `News Sentiment Enhancement`
4. **Description:** `Automatically enhance news events with sentiment analysis every 4 hours`
5. **Click:** "Next"

### **Step 3: Set Trigger (When to Run)**

1. **Select:** "Daily"
2. **Click:** "Next"
3. **Start date:** Today's date
4. **Start time:** Current time (or preferred time)
5. **Recur every:** `1 days`
6. **Click:** "Next"

### **Step 4: Set Action (What to Run)**

1. **Select:** "Start a program"
2. **Click:** "Next"
3. **Program/script:** `python`
4. **Add arguments:** `fetch_news_sentiment.py`
5. **Start in:** `C:\mt5-gpt\TelegramMoneyBot.v7`
6. **Click:** "Next"

### **Step 5: Advanced Settings (Important!)**

1. **Check:** "Open the Properties dialog for this task when I click Finish"
2. **Click:** "Finish"

### **Step 6: Configure Advanced Properties**

#### **General Tab:**
- **Check:** "Run whether user is logged on or not"
- **Check:** "Run with highest privileges"
- **Configure for:** Windows 10/11

#### **Triggers Tab:**
1. **Select** the trigger you just created
2. **Click:** "Edit"
3. **Check:** "Repeat task every:" `4 hours`
4. **For a duration of:** `Indefinitely`
5. **Check:** "Enabled"
6. **Click:** "OK"

#### **Actions Tab:**
- **Verify** the action is correct:
  - **Program:** `python`
  - **Arguments:** `fetch_news_sentiment.py`
  - **Start in:** `C:\mt5-gpt\TelegramMoneyBot.v7`

#### **Conditions Tab:**
- **Uncheck:** "Start the task only if the computer is on AC power"
- **Uncheck:** "Stop if the computer switches to battery power"
- **Check:** "Start the task only if the following network connection is available:" → "Any connection"

#### **Settings Tab:**
- **Check:** "Allow task to be run on demand"
- **Check:** "Run task as soon as possible after a scheduled start is missed"
- **Check:** "If the running task does not end when requested, force it to stop"
- **If the task fails, restart every:** `1 minute`
- **Attempt to restart up to:** `3 times`

### **Step 7: Test the Task**

1. **Right-click** on your task in Task Scheduler
2. **Select:** "Run"
3. **Check** the "Last Run Result" column
4. **Should show:** "0x0" (success) or "0x1" (error)

---

## 🔧 **Alternative: PowerShell Script Method**

If you prefer a more robust approach, create a PowerShell wrapper:

### **Create `run_news_sentiment.ps1`:**

```powershell
# run_news_sentiment.ps1
Set-Location "C:\mt5-gpt\TelegramMoneyBot.v7"
python fetch_news_sentiment.py
```

### **Task Scheduler Setup for PowerShell:**

1. **Program/script:** `powershell.exe`
2. **Add arguments:** `-ExecutionPolicy Bypass -File "C:\mt5-gpt\TelegramMoneyBot.v7\run_news_sentiment.ps1"`
3. **Start in:** `C:\mt5-gpt\TelegramMoneyBot.v7`

---

## 📊 **Monitoring and Troubleshooting**

### **Check Task Status:**

1. **Open Task Scheduler**
2. **Navigate to:** Task Scheduler Library
3. **Find:** "News Sentiment Enhancement"
4. **Check columns:**
   - **Last Run Time:** When it last ran
   - **Last Run Result:** 0x0 = success, 0x1 = error
   - **Next Run Time:** When it will run next

### **View Task History:**

1. **Right-click** on your task
2. **Select:** "Properties"
3. **Go to:** "History" tab
4. **View:** Detailed execution logs

### **Common Issues & Solutions:**

#### **Issue 1: Task Not Running**
- **Check:** Python is in system PATH
- **Solution:** Use full path to python.exe
- **Example:** `C:\Python311\python.exe`

#### **Issue 2: Permission Errors**
- **Check:** "Run with highest privileges" is enabled
- **Check:** User account has proper permissions

#### **Issue 3: Working Directory Issues**
- **Check:** "Start in" field is set correctly
- **Verify:** Path exists and is accessible

#### **Issue 4: Script Not Found**
- **Check:** File path is correct
- **Verify:** `fetch_news_sentiment.py` exists in the directory

---

## 🎯 **Expected Behavior**

### **Every 4 Hours, the Task Will:**

1. **Run:** `python fetch_news_sentiment.py`
2. **Load:** Existing news events from Forex Factory
3. **Enhance:** Events with sentiment analysis
4. **Save:** Updated data to `data/news_events.json`
5. **Log:** Success/failure in Task Scheduler

### **What You'll See:**

```
2025-10-14 22:30:00 - INFO - Starting news sentiment enhancement...
2025-10-14 22:30:00 - INFO - Loaded 115 existing events
2025-10-14 22:30:00 - INFO - Enhanced 115 events with sentiment analysis
2025-10-14 22:30:00 - INFO - SUCCESS: News sentiment enhancement completed!
```

---

## ✅ **Verification Steps**

### **1. Manual Test:**
```bash
cd C:\mt5-gpt\TelegramMoneyBot.v7
python fetch_news_sentiment.py
```

### **2. Check Output:**
- Should see "SUCCESS: News sentiment enhancement completed!"
- Check `data/news_events.json` for updated timestamps

### **3. Task Scheduler Test:**
- Right-click task → "Run"
- Check "Last Run Result" = 0x0
- Verify next run time is set

---

## 🚀 **Benefits of Automation**

✅ **Always Fresh Data** - News sentiment updated every 4 hours
✅ **No Manual Work** - Runs automatically in background
✅ **Reliable** - Windows Task Scheduler is robust
✅ **Scalable** - Can add more tasks easily
✅ **Monitorable** - Full logging and history

---

## 📝 **Quick Reference**

**Task Name:** News Sentiment Enhancement
**Frequency:** Every 4 hours
**Script:** `fetch_news_sentiment.py`
**Working Directory:** `C:\mt5-gpt\TelegramMoneyBot.v7`
**Expected Result:** 0x0 (success)

**To Disable:** Right-click task → "Disable"
**To Modify:** Right-click task → "Properties"
**To Delete:** Right-click task → "Delete"

---

**🎉 Your news trading system will now automatically stay updated with fresh sentiment analysis! 🚀📰💰**
