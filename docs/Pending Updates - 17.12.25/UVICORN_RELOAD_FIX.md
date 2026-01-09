# Uvicorn Reload Fix - Preventing Unwanted Server Restarts

## 🚨 Problem

The API server (`app/main_api.py`) was shutting down and restarting unexpectedly without user intervention.

## 🔍 Root Cause

The `--reload` flag in `start_all_services.bat` was watching **all files** for changes, including:
- Database files (`*.db`, `*.sqlite`) that are continuously updated during runtime
- Log files (`*.log`) that are written to constantly
- Data files in the `data/` directory

**The Multi-Timeframe Streamer** continuously writes to `data/multi_tf_candles.db`, which triggered uvicorn's file watcher, causing the server to restart every few seconds.

## ✅ Solution

Added `--reload-exclude` flags to exclude runtime files from the file watcher:

```batch
--reload-exclude "*.db"
--reload-exclude "*.sqlite"
--reload-exclude "*.log"
--reload-exclude "data/*"
--reload-exclude ".cursor/*"
```

This ensures that:
- ✅ Code changes still trigger reload (for development)
- ✅ Database writes don't trigger reload
- ✅ Log file writes don't trigger reload
- ✅ Data file updates don't trigger reload

## 📝 Changes Made

### `start_all_services.bat`

**Before:**
```batch
start "App API (8000)" cmd /k ".venv\Scripts\activate.bat && python -m uvicorn app.main_api:app --host 0.0.0.0 --port 8000 --reload"
```

**After:**
```batch
start "App API (8000)" cmd /k ".venv\Scripts\activate.bat && python -m uvicorn app.main_api:app --host 0.0.0.0 --port 8000 --reload --reload-exclude "*.db" --reload-exclude "*.sqlite" --reload-exclude "*.log" --reload-exclude "data/*" --reload-exclude ".cursor/*""
```

Same change applied to Root API (8010).

## ✅ Result

- ✅ Server no longer restarts when database files are updated
- ✅ Server no longer restarts when log files are written
- ✅ Server still reloads when Python code files change (development feature)
- ✅ Stable server operation without unexpected shutdowns

## 🎯 Files Excluded from Reload

1. **Database files**: `*.db`, `*.sqlite` (e.g., `multi_tf_candles.db`, `journal.sqlite`)
2. **Log files**: `*.log` (e.g., `.cursor/debug.log`)
3. **Data directory**: `data/*` (all files in data directory)
4. **Cursor directory**: `.cursor/*` (debug logs and temp files)

## 💡 Alternative: Remove --reload for Production

If you don't need auto-reload during development, you can remove the `--reload` flag entirely:

```batch
python -m uvicorn app.main_api:app --host 0.0.0.0 --port 8000
```

This is recommended for production environments where you want maximum stability.

