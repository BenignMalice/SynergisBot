<!-- Copilot instructions for AI coding agents — MoneyBot v2.7 -->

# Quick Context (what this repo is)
- Multi-service trading system integrating MT5, Binance enrichment, DTMS and ChatGPT-driven tools.
- Key entry points: `desktop_agent.py` (phone/custom-gpt tool runner), `chatgpt_bot.py` (discord/telegram AI bot), `app/main_api.py` (FastAPI main server), `dtms_api_server.py` (DTMS HTTP API).

# High-level architecture notes (read these first)
- Services communicate mostly via HTTP/WS and local databases: API server on port `8000`, command hub `8001`, DTMS API `8002`.
- There is a deliberate "separate database architecture": writers are split by process. See `database_access_manager.py` for the authoritative mapping (which process may write which DB).
- Real-time / microstructure features live in `infra/` modules (e.g., `infra/binance_service.py`, `infra/order_flow_service.py`, `infra/m1_*`).
- Heavy tick-level unified pipeline is intentionally disabled in this repo (see `docs/README.md` and `docs` notes). Use the Multi-Timeframe Streamer (`infra/multi_timeframe_streamer.py`) for lightweight M5/M15/H1 data.

# Developer workflows & commands
- Run the API server (development):
  - `python -m uvicorn app.main_api:app --host 0.0.0.0 --port 8000 --reload`
- Run key processes (Windows):
  - `python desktop_agent.py` — exposes tools over the phone hub and executes trade tools.
  - `python chatgpt_bot.py` — starts ChatGPT/Discord/monitoring background jobs.
  - `python dtms_api_server.py` — DTMS API (port 8002).
  - Use `start_all_services.bat` to launch recommended set of processes in separate windows.
- Tests: run `pytest` at repo root (there are many infra tests under `tests/`).

# Project-specific conventions & patterns (important for edits)
- Tool registration pattern: register phone/GPT-exposed functions with `@registry.register("tool.name")` in `desktop_agent.py` and `chatgpt_auto_execution_tools.py`.
- Symbol naming: broker-compatible symbols use a trailing `c` suffix (examples: `BTCUSDc`, `XAUUSDc`). Normalization logic is in `desktop_agent.py` (look for `.upper().rstrip('cC') + 'c'`).
- Database writes are restricted by process. If you add or change a writer, update `database_access_manager.py` to avoid locking/permission issues.
- Logging: use existing logger setup (see `desktop_agent.py` & `chatgpt_bot.py`) — file handlers use rotating logs in `data/logs` and `desktop_agent.log`.
- Async scheduling: `chatgpt_bot.py` uses a `BackgroundScheduler` wrapper that runs async jobs via an event loop helper — prefer adding background tasks there or use FastAPI lifespan events in `app/main_api.py`.

# Integration points & external dependencies
- MT5: `infra/mt5_service.py` centralizes all MT5 interactions. Prefer this service for MT5 calls rather than direct `MetaTrader5` usage.
- Binance & Order Flow: `infra/binance_service.py`, `infra/binance_enrichment.py`, `infra/order_flow_service.py` — many analyses expect 37 enrichment fields; guard feature usage if Binance service is unavailable.
- DTMS: DTMS lifecycle and engine access live in `dtms_integration.py` and `dtms_api_server.py` (use `start_dtms_monitoring()` and `get_dtms_engine()` to introspect runtime state).
- Conversation & analytics logging: `infra/conversation_logger`, `infra/analytics_logger` — chat analysis is stored to conversation DBs; security-conscious changes should preserve logging fields.

# Code patterns to mirror in PRs
- Keep functions resilient: many modules expect best-effort imports (see multiple try/except import blocks). Follow that pattern when adding optional integrations.
- When changing trading logic, attach human-readable summaries into the `conversation_logger` (see usage in `desktop_agent.py`) so analysis remains auditable.
- Use existing config and feature loaders (`config/settings.py`, `config/symbol_config_loader.py`) for runtime knobs; avoid hardcoding thresholds in modules.

# Quick pointers to find important code
- Decision logic: `decision_engine.py` — MTF scoring, SR postprocess `apply_sr_postprocess()`, and recommendation formatting.
- Tools & phone hub: `desktop_agent.py` (tool registry + execute flow) and `hub/command_hub.py` (WebSocket routes).
- Database policy: `database_access_manager.py` — MUST be consulted before adding DB writes.
- DTMS exposed endpoints: `dtms_api_server.py` (status, enable trade, engine info).
- Streamer & heavy feeds: `infra/multi_timeframe_streamer.py` & `infra/binance_*` files — be careful changing these; unified tick pipeline is disabled in docs.

# Safety & reviewer checklist for PRs
- Does the change respect DB writer roles in `database_access_manager.py`?
- If introducing long-running background work, register it via FastAPI lifespan or the `BackgroundScheduler` wrapper used in `chatgpt_bot.py`.
- If calling MT5 from background threads, use `infra/mt5_service.py` (handles connect/initialize) — avoid direct global MT5.initialize calls in new threads.
- If adding a new tool callable from phone/GPT, expose via `registry.register(...)` and add API dispatch tests.
- Keep `.env` secrets out of commits; update README docs for new required env vars.

# Where to update docs & tests when changing behavior
- Update `docs/README.md` when adding major features or service ports.
- Add tests under `tests/` to cover decision outputs, SR postprocessing (`decision_engine.py`), and tool dispatch routes.

# If anything here is unclear
- Tell me which area you want expanded (architecture, run commands, or examples) and I will update the file.
