# 🔄 Update ChatGPT with OCO Endpoints

## ✅ openai.yaml Updated

The OpenAPI specification has been updated with **3 new endpoints** for OCO bracket trading:

### New Endpoints Added:

1. **`/mt5/execute_bracket` (POST)**
   - operationId: `executeBracketTrade`
   - Execute a bracket trade with automatic OCO monitoring
   - Places BUY + SELL limit orders at range edges
   - When one fills, the other is automatically cancelled

2. **`/mt5/link_oco` (POST)**
   - operationId: `linkOrdersAsOCO`
   - Link two existing orders as an OCO pair
   - For orders already placed separately

3. **`/oco/status` (GET)**
   - operationId: `getOCOStatus`
   - Check status of all OCO pairs
   - See active monitoring and statistics

### Schema Changes:
- **Total paths:** 22 (was 19)
- **Total schemas:** 25 (was 22)
- **New schemas:**
  - `BracketTradeResponse`
  - `LinkOCOResponse`
  - `OCOStatusResponse`

---

## 🚀 Update ChatGPT Actions

### Step 1: Copy the Updated Schema

1. Open `C:\mt5-gpt\TelegramMoneyBot.v7\openai.yaml`
2. **Copy the ENTIRE file contents** (Ctrl+A, Ctrl+C)

### Step 2: Update ChatGPT

1. Go to your Custom GPT in ChatGPT
2. Click **"Configure"** or **"Edit GPT"**
3. Scroll to **"Actions"** section
4. Click on the existing action
5. Delete the old schema
6. **Paste the new schema** (Ctrl+V)
7. Click **"Save"**

### Step 3: Verify

ChatGPT should now show **22 operations** including:
- ✅ `executeBracketTrade` - Execute OCO bracket trade
- ✅ `linkOrdersAsOCO` - Link existing orders as OCO
- ✅ `getOCOStatus` - Get OCO status
- ...and 19 existing operations

---

## 🎯 What ChatGPT Can Now Do

### Before (Manual Management):
```
User: "Place bracket trade on XAUUSD at 3850 and 3870"

ChatGPT:
1. Calls /mt5/execute twice (BUY + SELL)
2. Both orders placed independently
3. ⚠️ Risk: Both might fill if price whipsaws
4. ⚠️ User must manually cancel opposite order
```

### After (Automatic OCO):
```
User: "Place bracket trade on XAUUSD at 3850 and 3870"

ChatGPT:
1. Calls /mt5/execute_bracket once
2. Both orders placed AND linked as OCO
3. ✅ When one fills, other automatically cancelled
4. ✅ Monitoring happens in background
```

---

## 📊 Example Usage

### Scenario 1: Execute New Bracket Trade

**User asks:**
> "Place a bracket trade on XAUUSD: BUY @ 3850 (SL:3842, TP:3870) and SELL @ 3870 (SL:3878, TP:3850)"

**ChatGPT calls:**
```
POST /mt5/execute_bracket
  ?symbol=XAUUSD
  &buy_entry=3850
  &buy_sl=3842
  &buy_tp=3870
  &sell_entry=3870
  &sell_sl=3878
  &sell_tp=3850
  &reasoning=Range-bound bracket strategy
```

**Response:**
```json
{
  "ok": true,
  "oco_group_id": "OCO_XAUUSDc_1759475330_116375448",
  "buy_order": {"ticket": 116375448, "entry": 3850, ...},
  "sell_order": {"ticket": 116375466, "entry": 3870, ...},
  "message": "Bracket trade created with OCO monitoring"
}
```

**ChatGPT tells user:**
> ✅ Bracket trade executed successfully!
> 
> - BUY @ $3,850 (Ticket #116375448)
> - SELL @ $3,870 (Ticket #116375466)
> 
> OCO monitoring active: When one order fills, the other will be automatically cancelled within 3 seconds.

### Scenario 2: Link Existing Orders

**User asks:**
> "Link my orders 116375448 and 116375466 as OCO"

**ChatGPT calls:**
```
POST /mt5/link_oco
  ?symbol=XAUUSD
  &ticket_a=116375448
  &ticket_b=116375466
```

**Response:**
```json
{
  "ok": true,
  "oco_group_id": "OCO_XAUUSDc_1759475330_116375448",
  "message": "Orders 116375448 and 116375466 linked as OCO pair"
}
```

### Scenario 3: Check OCO Status

**User asks:**
> "Show me my OCO pairs"

**ChatGPT calls:**
```
GET /oco/status
```

**Response:**
```json
{
  "ok": true,
  "monitor_running": true,
  "statistics": {"ACTIVE": 1},
  "active_pairs": [
    {
      "oco_group_id": "OCO_XAUUSDc_...",
      "symbol": "XAUUSDc",
      "order_a": {"ticket": 116375448, "side": "BUY", "entry": 3850},
      "order_b": {"ticket": 116375466, "side": "SELL", "entry": 3870},
      "created_at": "2025-10-03T10:08:50"
    }
  ]
}
```

---

## ⚠️ Important Notes

### Automatic OCO Features:
- ✅ Background monitoring (every 3 seconds)
- ✅ Automatic cancellation when one order fills
- ✅ Persistent across server restarts
- ✅ Full status tracking and statistics

### Limitations:
- ⚠️ Detection window: up to 3 seconds
- ⚠️ Fast markets: both might fill in extreme volatility
- ⚠️ Only works with API-executed or linked orders

---

## ✅ Update Checklist

- [ ] Copy entire `openai.yaml` file
- [ ] Open ChatGPT Custom GPT settings
- [ ] Paste new schema into Actions
- [ ] Save changes
- [ ] Start a **NEW conversation** with GPT
- [ ] Test: "Place a bracket trade on XAUUSD at 3850 and 3870"
- [ ] Verify: ChatGPT calls `executeBracketTrade`
- [ ] Confirm: Orders are linked with OCO monitoring

---

## 🎉 Benefits

**For You:**
- ✅ No manual monitoring required
- ✅ No risk of both orders filling
- ✅ Automated protection for all bracket trades

**For ChatGPT:**
- ✅ Single API call for bracket trades
- ✅ Built-in OCO logic
- ✅ Real-time status checking
- ✅ Better user experience

---

**Update the schema now to enable OCO automation!** 🚀

