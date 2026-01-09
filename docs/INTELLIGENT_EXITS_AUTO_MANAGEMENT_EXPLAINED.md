# 🤖 Intelligent Exits: Auto-Management Explained

## 🎯 **Your Question Answered:**

> **"Are exit rules automatically placed in intelligent_exits.json when trade goes live or must I tell ChatGPT to set rule? If rule goes live and I want ChatGPT to adjust the rule, does this occur?"**

---

## ✅ **AUTOMATIC RULE CREATION (No ChatGPT Required!)**

### **🔄 100% Automatic System:**

**Rules are created AUTOMATICALLY when trades go live - no ChatGPT interaction needed!**

### **1. For Market Orders (Immediate):**
```
You place trade → System automatically creates rule → Rule saved to intelligent_exits.json
```

**Location**: `app/main_api.py` - `/mt5/execute` endpoint
- **When**: Immediately after successful trade execution
- **How**: Checks `INTELLIGENT_EXITS_AUTO_ENABLE = True` in config
- **Result**: Rule automatically added to `data/intelligent_exits.json`

### **2. For Pending Orders (When Triggered):**
```
Pending order triggers → System detects new position → Rule automatically created
```

**Location**: `chatgpt_bot.py` - `auto_enable_intelligent_exits_async()` function
- **When**: Every 30 seconds, scans MT5 for new positions
- **How**: Detects positions without existing rules
- **Result**: Rule automatically added to `data/intelligent_exits.json`

### **3. On Bot Restart (Recovery):**
```
Bot restarts → Loads existing rules → Scans MT5 → Auto-enables for any missing positions
```

**Location**: `chatgpt_bot.py` - startup position check
- **When**: Every time the bot starts
- **How**: Loads `data/intelligent_exits.json` and compares with MT5 positions
- **Result**: Missing rules automatically created

---

## 📊 **Rule Storage & Management**

### **Storage File**: `data/intelligent_exits.json`
```json
{
  "121696501": {
    "ticket": 121696501,
    "symbol": "BTCUSD",
    "entry_price": 112300.0,
    "direction": "buy",
    "initial_sl": 111600.0,
    "initial_tp": 113600.0,
    "breakeven_profit_pct": 30.0,
    "partial_profit_pct": 60.0,
    "partial_close_pct": 50.0,
    "vix_threshold": 18.0,
    "trailing_enabled": true,
    "created_at": "2025-10-15T10:46:24.950Z",
    "breakeven_triggered": false,
    "partial_triggered": false,
    "trailing_active": false
  }
}
```

### **Automatic Monitoring**: Every 30 seconds
- **Breakeven**: Moves SL to entry at 30% of potential profit
- **Partial Profits**: Closes 50% at 60% of potential profit (skipped for 0.01 lots)
- **ATR Trailing**: 1.5× ATR trailing distance after breakeven
- **VIX Protection**: Widens stops if VIX > 18

---

## 🔧 **ChatGPT Rule Adjustments**

### **✅ YES - ChatGPT CAN Adjust Rules!**

**ChatGPT has full access to modify intelligent exit rules through the API:**

### **1. View Current Rules:**
```
ChatGPT: "Show intelligent exit status"
```
**Result**: Displays all active rules with current settings

### **2. Adjust Specific Rule:**
```
ChatGPT: "Adjust intelligent exits for ticket 121696501 - set breakeven to 20% and partial to 40%"
```
**Result**: Updates the rule in `data/intelligent_exits.json`

### **3. Disable/Enable Rules:**
```
ChatGPT: "Disable intelligent exits for ticket 121696501"
ChatGPT: "Enable intelligent exits for ticket 121696501"
```
**Result**: Toggles rule monitoring

### **4. Modify Advanced Settings:**
```
ChatGPT: "Set VIX threshold to 15 for ticket 121696501"
ChatGPT: "Enable hybrid stops for ticket 121696501"
```
**Result**: Updates advanced rule parameters

---

## 🎯 **API Endpoints Available to ChatGPT**

### **1. View Status:**
- **Endpoint**: `GET /mt5/intelligent_exits/status`
- **Purpose**: Show all active rules and their current settings

### **2. Modify Rules:**
- **Endpoint**: `POST /mt5/intelligent_exits/modify`
- **Purpose**: Adjust breakeven %, partial %, VIX threshold, etc.

### **3. Enable/Disable:**
- **Endpoint**: `POST /mt5/intelligent_exits/toggle`
- **Purpose**: Turn rules on/off for specific tickets

### **4. Advanced Adjustments:**
- **Endpoint**: `POST /mt5/intelligent_exits/advanced`
- **Purpose**: Modify advanced features like hybrid stops, trailing settings

---

## 📈 **Example: Your BTCUSD Trade**

### **Automatic Creation (Already Happened):**
```
✅ Rule created automatically when trade went live
✅ Saved to data/intelligent_exits.json
✅ Monitoring active every 30 seconds
✅ Breakeven: 30% of potential profit
✅ Partial: 60% of potential profit (skipped for 0.01 lots)
✅ Trailing: 1.5× ATR after breakeven
```

### **ChatGPT Adjustments (Available Now):**
```
ChatGPT: "Show intelligent exit status for my BTCUSD trade"
→ Shows current rule settings

ChatGPT: "Adjust BTCUSD intelligent exits - set breakeven to 20%"
→ Updates rule to 20% breakeven trigger

ChatGPT: "Disable partial profits for BTCUSD"
→ Skips partial profits (already disabled for 0.01 lots)

ChatGPT: "Set VIX threshold to 15 for BTCUSD"
→ Updates VIX protection level
```

---

## 🎉 **Summary: Fully Automated + ChatGPT Adjustable**

### **✅ What's Automatic:**
- **Rule Creation**: ✅ Automatic when trades go live
- **Rule Storage**: ✅ Automatic in `data/intelligent_exits.json`
- **Rule Monitoring**: ✅ Automatic every 30 seconds
- **Rule Recovery**: ✅ Automatic on bot restart

### **✅ What ChatGPT Can Do:**
- **View Rules**: ✅ Show current settings
- **Adjust Rules**: ✅ Modify percentages, thresholds
- **Enable/Disable**: ✅ Turn rules on/off
- **Advanced Settings**: ✅ Modify VIX, hybrid stops, trailing

### **✅ Your BTCUSD Trade:**
- **Rule**: ✅ Already created automatically
- **Monitoring**: ✅ Active every 30 seconds
- **Protection**: ✅ Breakeven + trailing (partials skipped for 0.01 lots)
- **Adjustable**: ✅ ChatGPT can modify anytime

**Result: Your trade is fully protected with intelligent exits, and ChatGPT can adjust the rules anytime you want!**
