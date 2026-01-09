# Phone Hub Port Change - Port 8001 → 8002
**Date:** 2025-12-17  
**Status:** ✅ **CHANGED**

---

## 🔍 **Issue**

**Port Conflict:**
- DTMS API server uses port **8001**
- Phone hub was also trying to use port **8001**
- DTMS API server was running first, blocking phone hub
- WebSocket connection failed with HTTP 403

---

## ✅ **Solution**

**Changed Phone Hub Port:**
- Phone hub now uses port **8002** by default
- Configurable via `PHONE_HUB_PORT` environment variable
- No more port conflicts

---

## 📊 **Port Configuration**

| Service | Port | Configurable | Default |
|---------|------|-------------|---------|
| **DTMS API Server** | 8001 | ❌ No | 8001 |
| **Phone Hub** | 8002 | ✅ Yes (`PHONE_HUB_PORT`) | 8002 |
| **Main API Server** | 8000 | ❌ No | 8000 |

---

## 🔧 **Changes Made**

### **1. desktop_agent.py**
```python
# Before:
HUB_URL = os.getenv("PHONE_HUB_URL", "ws://localhost:8001/agent/connect")

# After:
PHONE_HUB_PORT = int(os.getenv("PHONE_HUB_PORT", "8002"))
HUB_URL = os.getenv("PHONE_HUB_URL", f"ws://localhost:{PHONE_HUB_PORT}/agent/connect")
```

### **2. hub/command_hub.py**
```python
# Before:
uvicorn.run(app, host="0.0.0.0", port=8001)

# After:
phone_hub_port = int(os.getenv("PHONE_HUB_PORT", "8002"))
uvicorn.run(app, host="0.0.0.0", port=phone_hub_port)
```

---

## 🚀 **How to Use**

### **Start Phone Hub:**
```bash
# Default port (8002)
python -m uvicorn hub.command_hub:app --host 0.0.0.0 --port 8002

# Or use environment variable
set PHONE_HUB_PORT=8002
python hub/command_hub.py
```

### **Start Desktop Agent:**
```bash
# Will automatically use port 8002
python desktop_agent.py
```

### **Expose via ngrok:**
```bash
# Use port 8002 (not 8001)
ngrok http 8002
```

---

## ✅ **Result**

- ✅ No more port conflicts
- ✅ Phone hub uses port 8002
- ✅ DTMS API server uses port 8001
- ✅ Both can run simultaneously

**No more HTTP 403 errors!** 🚀

