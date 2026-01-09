# 🔄 Bot Update Checklist - Telegram + Custom GPT

## ⚠️ ALWAYS Update BOTH Interfaces!

When adding new features or data sources, you must update:
1. ✅ **Telegram Bot Interface** (`chatgpt_bridge.py`)
2. ✅ **Custom GPT API Interface** (`main_api.py` + `openai.yaml`)

---

## 📋 Telegram Bot Interface Updates

### File: `handlers/chatgpt_bridge.py`

#### 1. Add Function Implementation
```python
async def execute_get_your_feature(params) -> dict:
    """
    Fetch your feature data
    """
    try:
        # Your implementation here
        return result
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"error": str(e)}
```

#### 2. Add Tool Definition
```python
tools = [
    # ... existing tools ...
    {
        "type": "function",
        "function": {
            "name": "get_your_feature",
            "description": "What this function does",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "Parameter description"
                    }
                },
                "required": ["param1"]
            }
        }
    }
]
```

#### 3. Add Function Handler
```python
# In the function execution block
elif function_name == "get_your_feature":
    await update.message.reply_text("📊 Fetching data...")
    param1 = function_args.get("param1")
    function_result = await execute_get_your_feature(param1)
```

#### 4. Update System Prompt
```python
system_content = (
    # ... existing content ...
    "🆕 YOUR NEW FEATURE:\n"
    "• get_your_feature(param1): Description of what it does\n"
    "  - When to use it\n"
    "  - What it returns\n"
    "  - Example usage\n\n"
)
```

---

## 📋 Custom GPT API Interface Updates

### File: `main_api.py`

#### 1. Add REST API Endpoint
```python
@app.get("/api/v1/your_feature/{param}")
async def get_your_feature(param: str):
    """Get your feature data"""
    try:
        # Your implementation here
        return {
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### File: `openai.yaml`

#### 2. Add OpenAPI Spec
```yaml
paths:
  /api/v1/your_feature/{param}:
    get:
      operationId: getYourFeature
      summary: Brief description
      description: Detailed description of what this does
      tags:
        - YourCategory
      parameters:
        - name: param
          in: path
          required: true
          schema:
            type: string
          description: Parameter description
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: object
                properties:
                  data:
                    type: object
                  timestamp:
                    type: string
```

---

## 🎯 Real Example: DXY/VIX Integration

### ✅ Telegram Bot (chatgpt_bridge.py)

**1. Function Implementation:**
```python
async def execute_get_market_indices() -> dict:
    from infra.market_indices_service import create_market_indices_service
    indices = create_market_indices_service()
    return indices.get_market_context()
```

**2. Tool Definition:**
```python
{
    "type": "function",
    "function": {
        "name": "get_market_indices",
        "description": "Get DXY & VIX from Yahoo Finance",
        "parameters": {"type": "object", "properties": {}}
    }
}
```

**3. Function Handler:**
```python
elif function_name == "get_market_indices":
    await update.message.reply_text("📊 Fetching DXY & VIX...")
    function_result = await execute_get_market_indices()
```

**4. System Prompt:**
```python
"🌍 MARKET INDICES:\n"
"• get_market_indices(): Get real-time DXY & VIX\n"
"  - ALWAYS call before USD pair trades\n"
```

### ✅ Custom GPT API (main_api.py)

**1. API Endpoint:**
```python
@app.get("/api/v1/price/{symbol}")
async def get_current_price(symbol: str):
    # Special handling for DXY
    if symbol.upper() in ['DXY', 'DXYC']:
        from infra.market_indices_service import create_market_indices_service
        indices = create_market_indices_service()
        dxy_data = indices.get_dxy()
        return {
            "symbol": "DXY",
            "bid": dxy_data['price'],
            "ask": dxy_data['price'],
            "mid": dxy_data['price'],
            "source": "Yahoo Finance"
        }
    # ... normal MT5 handling ...
```

**2. OpenAPI Spec:**
Already exists at `/api/v1/price/{symbol}` - no update needed since we enhanced existing endpoint.

---

## ✅ Update Checklist Template

When adding a new feature:

### Telegram Bot (`chatgpt_bridge.py`):
- [ ] Add `async def execute_get_*()` function
- [ ] Add tool definition to `tools` array
- [ ] Add `elif function_name ==` handler
- [ ] Update system prompt with usage instructions
- [ ] Test in Telegram: `/chatgpt` then ask for feature

### Custom GPT API (`main_api.py`):
- [ ] Add `@app.get/post("/api/v1/...")` endpoint
- [ ] Add proper error handling
- [ ] Test endpoint: `curl http://localhost:8000/api/v1/...`

### OpenAPI Spec (`openai.yaml`):
- [ ] Add path definition under `paths:`
- [ ] Add operation details (operationId, summary, description)
- [ ] Add parameters and response schemas
- [ ] Sync with Custom GPT if needed

### Testing:
- [ ] Test in Telegram bot
- [ ] Test via API (`curl` or browser)
- [ ] Test in Custom GPT
- [ ] Verify both interfaces return same data

---

## 🚨 Common Mistakes to Avoid

1. ❌ **Only updating Telegram bot**
   - Custom GPT won't work → "Error talking to connector"
   
2. ❌ **Only updating API endpoint**
   - Telegram bot can't access feature
   
3. ❌ **Forgetting to restart services**
   - Telegram: restart `chatgpt_bot.py`
   - API: restart uvicorn server
   - ngrok: ensure tunnel is running

4. ❌ **Not updating OpenAPI spec**
   - Custom GPT won't know new endpoint exists
   - Must sync `openai.yaml` to Custom GPT Actions

---

## 🔄 Restart Procedure

After making updates:

### 1. Restart Telegram Bot
```bash
# Stop current bot (Ctrl+C)
python chatgpt_bot.py
```

### 2. Restart API Server
```bash
# Stop current server (Ctrl+C)
python -m uvicorn main_api:app --reload --host 0.0.0.0 --port 8000
```

### 3. Ensure ngrok is Running
```bash
ngrok http 8000
```

### 4. Update Custom GPT Actions (if openai.yaml changed)
1. Go to Custom GPT settings
2. Navigate to Actions
3. Paste updated `openai.yaml` content
4. Save

---

## 📊 Interface Comparison

| Feature | Telegram Bot | Custom GPT API |
|---------|-------------|----------------|
| **File** | `handlers/chatgpt_bridge.py` | `main_api.py` |
| **Format** | Python async functions | REST API endpoints |
| **Calls** | Direct function calls in conversation | HTTP requests via ngrok |
| **Spec** | Tools array in code | `openai.yaml` OpenAPI spec |
| **Testing** | `/chatgpt` in Telegram | Browser or curl |
| **Restart** | `chatgpt_bot.py` | uvicorn server |

---

## ✅ Summary

**Golden Rule:**
> When you update functionality, ALWAYS update BOTH Telegram bot AND Custom GPT API!

**Quick Check:**
- ✅ Does feature work in Telegram?
- ✅ Does feature work in Custom GPT?
- ✅ Both return same data?

**If answer is NO to any:**
→ You forgot to update one interface!

---

## 🎯 Example Updates

### Data Source Changes (like DXY):
- ✅ Telegram: Add `get_market_indices()` function
- ✅ API: Update `/api/v1/price/DXY` to fetch from Yahoo Finance

### New Analysis Tool:
- ✅ Telegram: Add tool + handler + system prompt
- ✅ API: Add new endpoint in `main_api.py`
- ✅ OpenAPI: Add path in `openai.yaml`

### Function Behavior Change:
- ✅ Telegram: Update `execute_*` function
- ✅ API: Update corresponding endpoint
- ✅ Test both interfaces

**Keep them in sync, always!** 🔄

