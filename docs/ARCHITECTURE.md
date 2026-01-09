# System Architecture

## ChatGPT System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         USER                                │
│                    (via Telegram)                           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Messages & Commands
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   chatgpt_bot.py                            │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │   Start    │  │    Help    │  │  SetGPTKey │           │
│  │  Handler   │  │  Handler   │  │   Handler  │           │
│  └────────────┘  └────────────┘  └────────────┘           │
│                                                              │
│  ┌──────────────────────────────────────────────┐          │
│  │     handlers/chatgpt_bridge.py               │          │
│  │                                               │          │
│  │  • Conversation Management                   │          │
│  │  • Message Routing                           │          │
│  │  • Context Tracking                          │          │
│  │  • Pre-fetch Market Data                     │          │
│  └──────────────────────────────────────────────┘          │
└────────────┬─────────────────────┬───────────────────────────┘
             │                     │
             │ API Calls           │ ChatGPT API
             │                     │
┌────────────▼─────────┐  ┌────────▼────────────┐
│   MT5 API Server     │  │   OpenAI ChatGPT    │
│  (app/main_api.py)   │  │                     │
│                      │  │  • GPT-4o-mini      │
│  • FastAPI Server    │  │  • Function Calling │
│  • Port 8000         │  │  • Conversation AI  │
│  • REST Endpoints    │  └─────────────────────┘
│                      │
│  Endpoints:          │
│  • /health           │
│  • /api/v1/price     │
│  • /ai/analysis      │
│  • /mt5/execute      │
│  • /api/v1/account   │
└──────────┬───────────┘
           │
           │ MT5 API Calls
           │
┌──────────▼───────────┐
│   MT5 Services       │
│                      │
│  ┌────────────────┐  │
│  │ MT5Service     │  │
│  │ • connect()    │  │
│  │ • get_price()  │  │
│  │ • execute()    │  │
│  └────────────────┘  │
│                      │
│  ┌────────────────┐  │
│  │IndicatorBridge │  │
│  │ • get_multi()  │  │
│  │ • RSI, EMA     │  │
│  │ • ATR, ADX     │  │
│  └────────────────┘  │
│                      │
│  ┌────────────────┐  │
│  │OpenAIService   │  │
│  │ • recommend()  │  │
│  │ • analyze()    │  │
│  └────────────────┘  │
└──────────┬───────────┘
           │
           │ MetaTrader5 API
           │
┌──────────▼───────────┐
│   MetaTrader 5       │
│   Terminal           │
│                      │
│  • Live Prices       │
│  • Execute Trades    │
│  • Account Info      │
│  • Position Mgmt     │
└──────────────────────┘
```

---

## Data Flow

### Example: "Give me a trade recommendation for XAUUSD"

```
1. User sends message via Telegram
   │
   ▼
2. chatgpt_bot.py receives message
   │
   ▼
3. chatgpt_bridge.py detects trade keywords
   │
   ▼
4. Pre-fetch: Call API /api/v1/price/XAUUSD
   │   → MT5Service.get_price()
   │   → MT5 Terminal
   │   ← Current price: $3,863.82
   │
   ▼
5. Pre-fetch: Call API /ai/analysis/XAUUSD
   │   → IndicatorBridge.get_multi()
   │   → MT5 Terminal (fetch OHLC data)
   │   ← RSI, EMA, ATR, etc.
   │   → OpenAIService.recommend()
   │   → ChatGPT API (analysis)
   │   ← Trade recommendation
   │
   ▼
6. Append market data to user message
   │   Original: "Give me a trade recommendation"
   │   Enhanced: "Give me a trade recommendation
   │             [CURRENT MARKET DATA]
   │             Price: $3,863.82
   │             RSI: 50.0
   │             Market Regime: RANGE
   │             Recommendation: HOLD"
   │
   ▼
7. Send enhanced message to ChatGPT API
   │   → OpenAI GPT-4o-mini
   │   ← AI response with real data
   │
   ▼
8. Send ChatGPT response to user via Telegram
   │
   ▼
9. User sees: "Based on current market data at $3,863.82..."
```

---

## Component Details

### 1. **chatgpt_bot.py**
- **Purpose:** Main entry point
- **Responsibilities:**
  - Initialize Telegram bot
  - Register handlers
  - Manage bot lifecycle
  - Error handling
- **Dependencies:**
  - `python-telegram-bot`
  - `handlers/chatgpt_bridge.py`
  - `.env` configuration

### 2. **handlers/chatgpt_bridge.py**
- **Purpose:** ChatGPT integration logic
- **Responsibilities:**
  - Manage conversation state
  - Pre-fetch market data
  - Call OpenAI API
  - Handle tool calls
  - Format responses
- **Dependencies:**
  - `httpx` (async HTTP)
  - `openai` (ChatGPT API)
  - MT5 API endpoints

### 3. **app/main_api.py**
- **Purpose:** REST API server
- **Responsibilities:**
  - Expose MT5 functionality
  - Handle price queries
  - Execute trades
  - Provide AI analysis
  - Health checks
- **Dependencies:**
  - `fastapi`
  - `uvicorn`
  - `infra/mt5_service.py`
  - `infra/indicator_bridge.py`
  - `infra/openai_service.py`

### 4. **infra/mt5_service.py**
- **Purpose:** MT5 connection & operations
- **Responsibilities:**
  - Connect to MT5
  - Fetch prices
  - Execute orders
  - Get account info
  - Symbol management
- **Dependencies:**
  - `MetaTrader5` library

### 5. **infra/indicator_bridge.py**
- **Purpose:** Technical indicators
- **Responsibilities:**
  - Fetch OHLC data
  - Calculate RSI, EMA, ATR, ADX
  - Multi-timeframe analysis
- **Dependencies:**
  - `MetaTrader5`
  - `pandas`
  - `numpy`

### 6. **infra/openai_service.py**
- **Purpose:** AI-powered analysis
- **Responsibilities:**
  - Call ChatGPT for trade recommendations
  - Generate market analysis
  - Provide reasoning for trades
- **Dependencies:**
  - `openai` library
  - API key from `.env`

---

## API Endpoints

### Core Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/api/v1/price/{symbol}` | GET | Get current price |
| `/api/v1/account` | GET | Get account info |
| `/mt5/execute` | POST | Execute trade |
| `/mt5/execute_bracket` | POST | Execute OCO bracket |

### AI Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ai/analysis/{symbol}` | GET | ChatGPT analysis |
| `/ml/patterns/{symbol}` | GET | Pattern recognition |
| `/ai/exits/{symbol}` | GET | Exit strategies |

### Management Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/risk/metrics` | GET | Risk metrics |
| `/market/analysis/{symbol}` | GET | Market analysis |
| `/health/status` | GET | Detailed health |

---

## Security Considerations

### API Keys
- **OpenAI API Key:**
  - Stored in `.env` or set via `/setgptkey`
  - Stored in `bot_data` (in-memory)
  - Cleared on bot restart
  
- **Telegram Bot Token:**
  - Must be in `.env`
  - Never expose publicly
  
### API Server
- **Local by default:** `localhost:8000`
- **ngrok tunnel:** For external access
- **No authentication:** Add auth for production

### Recommendations
1. Never commit `.env` to git
2. Use ngrok auth for production
3. Implement API key authentication
4. Rate limit API endpoints
5. Log all trade executions

---

## Scalability

### Current Design
- ✅ Single user (you)
- ✅ Local deployment
- ✅ Direct MT5 connection

### For Multi-User
- ❌ No user isolation
- ❌ No per-user API keys
- ❌ No rate limiting
- ❌ Shared MT5 account

### To Scale
1. Add user authentication
2. Implement per-user API keys
3. Add database for user data
4. Deploy to cloud (AWS, GCP, Azure)
5. Use Redis for session management
6. Implement WebSocket for real-time

---

## Performance

### Bottlenecks
1. **MT5 API calls** - Slowest part (~500-1000ms)
2. **ChatGPT API** - Moderate (~1-3s)
3. **Network latency** - Minimal (local)

### Optimizations
1. ✅ Pre-fetch market data (implemented)
2. ✅ Async HTTP calls (using `httpx`)
3. ❌ Caching (not implemented)
4. ❌ Connection pooling (not implemented)

### Typical Response Times
- Simple price query: ~500ms
- Full AI analysis: ~2-5s
- Trade execution: ~1-2s

---

## Monitoring

### Logs
- **chatgpt_bot.py:** Console output
- **main_api.py:** uvicorn logs
- **ngrok:** Dashboard at `http://localhost:4040`

### Health Checks
- API: `http://localhost:8000/health`
- Detailed: `http://localhost:8000/health/status`

### Metrics to Monitor
- Response times
- Error rates
- API call counts
- Trade execution success rate

---

## Deployment

### Local (Current)
```
Windows PC
├── chatgpt_bot.py (Python process)
├── main_api.py (uvicorn server)
├── ngrok (tunnel)
└── MT5 Terminal
```

### Cloud (Future)
```
Cloud Server (AWS/GCP)
├── Docker container
│   ├── chatgpt_bot.py
│   ├── main_api.py
│   └── nginx reverse proxy
├── MT5 in VPS
└── Database (PostgreSQL)
```

---

## Future Enhancements

### Short Term
- [ ] Add caching for market data
- [ ] Implement retry logic
- [ ] Add more error handling
- [ ] Improve logging

### Medium Term
- [ ] Multi-user support
- [ ] Database integration
- [ ] WebSocket for real-time
- [ ] Mobile app

### Long Term
- [ ] Cloud deployment
- [ ] Auto-scaling
- [ ] Advanced ML models
- [ ] Portfolio management

---

**For more details, see:**
- `CHATGPT_SYSTEM.md` - User guide
- `SYSTEM_COMPARISON.md` - Feature comparison
- `QUICK_START.md` - Getting started

