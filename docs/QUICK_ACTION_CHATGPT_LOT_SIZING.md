# 🚀 Quick Action - Update ChatGPT for Lot Sizing

## ⏱️ 3-Minute Update

### **1️⃣ Update Instructions** (1 min)

1. Open **Forex Trade Analyst** Custom GPT
2. Click **Configure** → **Instructions**
3. Copy/paste from: `CUSTOM_GPT_INSTRUCTIONS.md`
4. Click **Save**

**Character count:** 6,655 / 8,000 ✅

---

### **2️⃣ Upload Knowledge** (1 min)

1. In **Configure** → **Knowledge**
2. Click **Upload files**
3. Upload: `ChatGPT_Knowledge_Lot_Sizing.md`
4. Click **Save**

---

### **3️⃣ Update Actions** (1 min)

1. In **Configure** → **Actions**
2. Copy/paste from: `openai.yaml`
3. Click **Save**

---

## 🧪 Test (30 seconds)

**On your phone:**
```
check lot sizing configuration
```

**Expected:**
```
📊 Lot Sizing Configuration

💰 CRYPTO:
  BTCUSDc: Max 0.02 lots, Risk 0.75%

🥇 METALS:
  XAUUSDc: Max 0.02 lots, Risk 1.0%

💱 FOREX:
  EURUSDc: Max 0.04 lots, Risk 1.25%
  ...
```

**Then test execution:**
```
analyse btcusd
execute
```

**Expected:**
```
✅ Trade Executed
Lot Size: 0.02 (auto-calculated based on 0.75% risk)
```

---

## ✅ Done!

ChatGPT now:
- ✅ Auto-calculates lot sizes
- ✅ Uses 0.02 for BTC/XAU
- ✅ Uses 0.04 for Forex
- ✅ Can check configuration

---

**Full details:** `CHATGPT_LOT_SIZING_UPDATE.md` 📄

