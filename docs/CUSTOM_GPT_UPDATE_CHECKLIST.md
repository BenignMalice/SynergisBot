# 🔄 Custom GPT Configuration Update Checklist

**Date:** 2025-10-13  
**Issue:** Lot sizing fix documentation updates  
**Status:** ✅ Code deployed, documentation updated

---

## ✅ Files Updated (Automatic)

These files are **on your laptop** and automatically used by the system:

### 1. **openai.yaml** ✅ Already Correct
- **Location:** `C:\mt5-gpt\TelegramMoneyBot.v7\openai.yaml`
- **Status:** ✅ Already has correct documentation
- **Line 133:** `"Trade volume in lots (OPTIONAL - if not provided, system auto-calculates based on risk. BTCUSD/XAUUSD max 0.02, Forex max 0.04)"`
- **Line 170:** Example shows volume omitted with comment about auto-calculation
- **Action:** ✅ No changes needed

### 2. **ChatGPT_Knowledge_Lot_Sizing.md** ✅ Updated
- **Location:** `C:\mt5-gpt\TelegramMoneyBot.v7\ChatGPT_Knowledge_Lot_Sizing.md`
- **Status:** ✅ Updated with clarification that `volume: 0` works
- **Changes:**
  - Added "Option 2" showing `volume: 0` as valid
  - Updated decision tree to mention both approaches
- **Action:** ✅ Complete

---

## ⚠️ Manual Update Required (Custom GPT Portal)

You **must** manually update the Custom GPT knowledge files in the OpenAI portal:

### **Step 1: Access Custom GPT Editor**
1. Go to: https://chat.openai.com/gpts/editor/
2. Select: **"Forex Trade Analyst"** (your Custom GPT)
3. Click: **"Configure"** tab

---

### **Step 2: Update Knowledge Files**

#### **Option A: Upload Updated File (Recommended)**
1. Click **"Knowledge"** section
2. Find existing `ChatGPT_Knowledge_Lot_Sizing.md` (if present)
3. Delete old version
4. Click **"Upload files"**
5. Upload the updated file from: 
   ```
   C:\mt5-gpt\TelegramMoneyBot.v7\ChatGPT_Knowledge_Lot_Sizing.md
   ```
6. Verify file appears in knowledge list

#### **Option B: Verify Existing (If Uncertain)**
If you're not sure if you already uploaded this file:

1. Check if `ChatGPT_Knowledge_Lot_Sizing.md` appears in knowledge list
2. If **YES** → Delete and re-upload updated version
3. If **NO** → Just upload it fresh

---

### **Step 3: Verify Other Knowledge Files**

Make sure these are also uploaded (if not already):

| File | Status | Action |
|------|--------|--------|
| `ChatGPT_Knowledge_Smart_Money_Concepts.md` | Should exist | Verify present |
| `ChatGPT_Knowledge_All_Enrichments.md` | Should exist | Verify present |
| `ChatGPT_Knowledge_Lot_Sizing.md` | **MUST UPDATE** | Delete old, upload new |
| `CUSTOM_GPT_INSTRUCTIONS_CONCISE_SMC.md` | In Instructions | Not in Knowledge |

---

### **Step 4: Save and Test**

1. Click **"Save"** in top-right corner
2. Wait for "Saved" confirmation
3. Click **"Preview"** to test

**Test it:**
```
You: "Execute BUY XAUUSD at market"
```

**Expected:**
- Custom GPT should call `moneybot.execute_trade`
- Arguments should have `volume: 0` or no volume field
- Response should show calculated lot size (e.g., 0.02 lots)

---

## 📋 Quick Verification

### **Check 1: OpenAPI Schema**
✅ `openai.yaml` line 133 says "OPTIONAL - if not provided, system auto-calculates"

### **Check 2: Knowledge Document**
✅ `ChatGPT_Knowledge_Lot_Sizing.md` shows both options (omit or set to 0)

### **Check 3: Custom GPT Portal**
⚠️ **YOU MUST DO THIS:**
- [ ] Logged into https://chat.openai.com/gpts/editor/
- [ ] Selected "Forex Trade Analyst"
- [ ] Went to Configure → Knowledge
- [ ] Uploaded updated `ChatGPT_Knowledge_Lot_Sizing.md`
- [ ] Saved changes
- [ ] Tested with a trade execution

---

## 🎯 Why This Matters

**Before Update:**
- Custom GPT might have been confused about whether to include volume
- Old knowledge might have said "always omit volume"
- Didn't clarify that `volume: 0` is valid

**After Update:**
- ✅ Clarifies that BOTH omitting and setting to 0 work
- ✅ Explains that 0 means "calculate for me"
- ✅ Shows explicit examples of both approaches

**Result:**
- Custom GPT will consistently trigger auto-calculation
- No more confusion about volume parameter
- Consistent 0.02/0.04 lot sizing for all trades

---

## 🆘 Troubleshooting

### **Issue: Custom GPT still uses 0.01 lots**

**Cause:** Knowledge file not updated in portal

**Fix:**
1. Delete old `ChatGPT_Knowledge_Lot_Sizing.md` from Custom GPT
2. Upload new version from your laptop
3. Save and test again

---

### **Issue: Can't find knowledge section**

**Steps:**
1. Go to https://chat.openai.com/gpts/editor/
2. Click on your "Forex Trade Analyst" GPT
3. Click "Configure" tab (not "Preview")
4. Scroll down to "Knowledge" section
5. You should see file upload area

---

### **Issue: Upload fails**

**Try:**
1. File must be < 512KB (this one is ~3KB, so OK)
2. Must be `.md` extension
3. Check if you have too many files (max 20)
4. If at limit, delete unused old files first

---

## ✅ Final Checklist

Before closing this task:

- [x] ✅ Code updated (`desktop_agent.py` + `app/main_api.py`)
- [x] ✅ Services restarted
- [x] ✅ `openai.yaml` verified (already correct)
- [x] ✅ `ChatGPT_Knowledge_Lot_Sizing.md` updated
- [ ] ⚠️ **YOU MUST DO:** Upload to Custom GPT portal
- [ ] ⚠️ **YOU MUST DO:** Test with live trade execution

---

**Once you've uploaded the knowledge file to the Custom GPT portal, you're done!** 🎉

