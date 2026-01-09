# TelegramMoneyBot.v8 — System Overview

_Generated: 2025-10-11T07:31:28_

## High-Level Architecture


- **Telegram Interface (handlers/...)**: Command and callback handlers, inline buttons, and UX flows.
- **Decision & Strategy Engine (app/engine, decision_engine.py, strategy_logic.py)**: Combines indicators, candlestick patterns, regime classification, risk model, and strategy filters to produce **trade plans**.
- **OpenAI/ChatGPT (infra/openai_service.py, handlers/trading.py, etc.)**: LLM-assisted narrative analysis, critique, and recommendation formatting.
- **MT5 Integration (infra/mt5_service.py)**: Broker connectivity (Exness), quotes/ATR, order open/modify/close, pending/OCO support.
- **Monitoring & Scheduler (infra/scheduler.py, watchers)**: Scans for setups, monitors live trades and pendings, trails SL/TP, sends Telegram alerts.
- **Guardrails/Exposure/News (infra/guardrails.py, exposure_guard, news service)**: Blocks risky trades, respects sessions/news/spread/cooldowns.
- **Journal & Reports (infra/journal_repo.py, journal/...)**: CSV/SQLite logs, performance stats, summaries.

## Telegram Commands & Callbacks (detected)

### `chatgpt_bot.py`

- **CallbackQueryHandler**: `chatgpt_button`
- **CallbackQueryHandler**: `menu_button_handler`
- **CommandHandler**: `chatgpt`
- **CommandHandler**: `circuit`
- **CommandHandler**: `dashboard`
- **CommandHandler**: `endgpt`
- **CommandHandler**: `help`
- **CommandHandler**: `journal`
- **CommandHandler**: `menu`
- **CommandHandler**: `setgptkey`
- **CommandHandler**: `start`
- **CommandHandler**: `status`
- **CommandHandler**: `watch`
- **MessageHandler**: `chatgpt_message`

### `chatgpt_bridge.py`

- **CallbackQueryHandler**: `chatgpt_button`
- **CallbackQueryHandler**: `chatgpt_end`
- **CommandHandler**: `chatgpt`
- **CommandHandler**: `endgpt`
- **CommandHandler**: `gptstatus`
- **CommandHandler**: `setgptkey`
- **CommandHandler**: `testchatgpt`
- **MessageHandler**: `chatgpt_message`

### `handlers/chatgpt_bridge.py`

- **CallbackQueryHandler**: `chatgpt_button`
- **CallbackQueryHandler**: `chatgpt_end`
- **CommandHandler**: `chatgpt`
- **CommandHandler**: `endgpt`
- **CommandHandler**: `gptstatus`
- **CommandHandler**: `setgptkey`
- **CommandHandler**: `testchatgpt`
- **MessageHandler**: `chatgpt_message`

### `handlers/circuit.py`

- **CommandHandler**: `circuit`
- **CommandHandler**: `resume`

### `handlers/feature_builder.py`

- **CommandHandler**: `feature_compare`
- **CommandHandler**: `feature_export`
- **CommandHandler**: `feature_help`
- **CommandHandler**: `feature_test`

### `handlers/help.py`

- **CommandHandler**: `help`
- **CommandHandler**: `start`

### `handlers/journal.py`

- **CommandHandler**: `journal`
- **CommandHandler**: `pnl`

### `handlers/menu.py`

- **CallbackQueryHandler**: `menu_router`
- **CallbackQueryHandler**: `noop_button`
- **CallbackQueryHandler**: `pending_menu_router`
- **CallbackQueryHandler**: `trade_menu_router`
- **CommandHandler**: `menu`
- **CommandHandler**: `start`
- **CommandHandler**: `status`

### `handlers/pending.bak.py`

- **CallbackQueryHandler**: `pending_callbacks`
- **CommandHandler**: `pending`
- **CommandHandler**: `pendings`

### `handlers/pending.py`

- **CallbackQueryHandler**: `pending_callbacks`
- **CommandHandler**: `pending`
- **CommandHandler**: `pendings`

### `handlers/prompt_router.py`

- **CommandHandler**: `router_status`
- **CommandHandler**: `router_templates`
- **CommandHandler**: `router_test`
- **CommandHandler**: `router_validate`

### `handlers/signal_scanner.py`

- **CallbackQueryHandler**: `signal_callback_handler`
- **CommandHandler**: `signal_config`
- **CommandHandler**: `signal_status`
- **CommandHandler**: `signal_test`

### `handlers/status.py`

- **CommandHandler**: `status`

### `handlers/trading.py`

- **CallbackQueryHandler**: `exec_callback`
- **CallbackQueryHandler**: `pending_callbacks`
- **CommandHandler**: `analyse`
- **CommandHandler**: `critic`
- **CommandHandler**: `monitor`
- **CommandHandler**: `trade`

### `trade_bot.py`

- **CallbackQueryHandler**: `button_router`
- **CommandHandler**: `debugjobs`
- **CommandHandler**: `loadcharts`
- **CommandHandler**: `trade`

## OpenAI/ChatGPT Usage

- `app/main_api.py` — models: (unspecified), calls: (heuristic)
- `chatgpt_bot.py` — models: (unspecified), calls: (heuristic)
- `chatgpt_bridge.py` — models: (unspecified), calls: (heuristic)
- `handlers/chatgpt_bridge.py` — models: (unspecified), calls: (heuristic)
- `infra/openai_service.py` — models: (unspecified), calls: Completion
- `infra/prompt_router.py` — models: (unspecified), calls: (heuristic)
- `main_api.py` — models: (unspecified), calls: (heuristic)
- `trade_manager.py` — models: (unspecified), calls: chat.completions.create

LLM is typically used to:
- Convert raw technical/fundamental context into a narrative recommendation.
- Produce a structured plan (entry, SL, TP, reasoning) and a critique pass.

## MT5 Integration Points

- `app/main_api.py` — ops: login, positions_get, orders_get, order_send, symbol_info_tick, shutdown
- `app/services/oco_tracker.py` — ops: orders_get, order_send
- `app/services/pending_emulator.py` — ops: symbol_info_tick
- `chatgpt_bot.py` — ops: initialize, positions_get, shutdown
- `check_mt5_dxy.py` — ops: initialize, symbol_info_tick, shutdown
- `check_symbol.py` — ops: initialize, symbol_info_tick, shutdown
- `handlers/pending.bak.py` — ops: copy_rates_range
- `handlers/pending.py` — ops: copy_rates_range
- `handlers/status.py` — ops: positions_get
- `handlers/trading.py` — ops: positions_get, orders_get, order_send, symbol_info_tick
- `indicator_bridge.py` — ops: 
- `infra/exit_monitor.py` — ops: order_send
- `infra/exposure_guard.py` — ops: positions_get
- `infra/formatting.py` — ops: 
- `infra/guardrails.py` — ops: 
- `infra/indicator_bridge.py` — ops: initialize, symbol_info_tick
- `infra/indicator_bridge_fixed.py` — ops: initialize, symbol_info_tick
- `infra/indicator_bridge_original.py` — ops: 
- `infra/intelligent_exit_manager.py` — ops: initialize, positions_get, order_send
- `infra/loss_cut_monitor.py` — ops: order_send
- `infra/loss_cutter.py` — ops: symbol_info_tick
- `infra/mt5_service.py` — ops: initialize, positions_get, order_send, symbol_info_tick
- `infra/position_watcher.py` — ops: positions_get
- `infra/price_utils.py` — ops: 
- `infra/pseudo_pendings.py` — ops: copy_rates_range
- `infra/trade_monitor.py` — ops: order_send
- `main_api.py` — ops: login, shutdown
- `technical_analysis.py` — ops: initialize
- `technical_analysis_fixed.py` — ops: initialize
- `technical_analysis_original.py` — ops: 
- `test_trailing_live.py` — ops: initialize, positions_get, shutdown
- `tools/wick_tuner.py` — ops: initialize, shutdown
- `trade_manager.py` — ops: positions_get, order_send, symbol_info_tick

## Indicators / Strategy Files

- `app/engine/regime_classifier.py` — EMA, ADX
- `app/engine/risk_model.py` — ATR, ADX
- `app/engine/strategy_logic.bak.py` — ATR, EMA, RSI, ADX
- `app/engine/strategy_logic.py` — ATR, EMA, RSI, ADX
- `app/engine/volatile_strategies.py` — ATR, EMA, MACD, VWAP, ADX
- `app/main_api.py` — ATR, EMA, RSI, ADX
- `chatgpt_bot.py` — ATR, RSI, ADX
- `chatgpt_bridge.py` — ATR, RSI, ADX
- `config.py` — ATR, EMA, RSI, ADX
- `config/settings.py` — ATR
- `decision_engine.py` — ATR, EMA, RSI, ADX
- `domain/breakout_quality.py` — ATR
- `domain/candle_stats.py` — ATR, Bollinger
- `domain/confluence.py` — EMA, ADX
- `domain/fvg.py` — ATR
- `domain/levels.py` — ATR
- `domain/liquidity.py` — ATR
- `domain/market_structure.py` — ATR
- `domain/patterns.py` — ATR
- `domain/rules.py` — EMA, ADX
- `domain/support_resistance.py` — ATR
- `domain/zones.py` — Pivot
- `handlers/chatgpt_bridge.py` — ATR, EMA, RSI, ADX
- `handlers/feature_builder.py` — ATR, EMA, MACD, RSI, Bollinger, VWAP, ADX
- `handlers/menu.py` — RSI, ADX
- `handlers/pending.bak.py` — ATR
- `handlers/pending.py` — ATR, VWAP, Pivot, ADX
- `handlers/prompt_router.py` — ADX
- `handlers/reco_modes.py` — ADX
- `handlers/trading.py` — ATR, EMA, RSI, ADX
- `indicator_bridge.py` — ATR, EMA, MACD, RSI, Stochastic, VWAP, Pivot, ADX
- `infra/bandit_autoupdate.py` — RSI
- `infra/confluence_calculator.py` — ATR, MACD, RSI
- `infra/exit_monitor.py` — ATR
- `infra/exit_signal_detector.py` — ATR, EMA, MACD, RSI, Bollinger, VWAP, Pivot, ADX
- `infra/feature_builder.py` — ATR, MACD, RSI
- `infra/feature_builder_fast.py` — EMA, ADX
- `infra/feature_indicators.py` — ATR, EMA, MACD, RSI, Bollinger, VWAP
- `infra/feature_microstructure.py` — ATR
- `infra/feature_patterns.py` — ATR
- `infra/feature_structure.py` — ATR, Pivot
- `infra/guardrails.py` — ATR
- `infra/indicator_bridge.py` — ATR, MACD, RSI, Bollinger, Stochastic, ADX
- `infra/indicator_bridge_fixed.py` — ATR, MACD, RSI, Bollinger, Stochastic, ADX
- `infra/indicator_bridge_original.py` — ATR, EMA, RSI, VWAP, Pivot, ADX
- `infra/intelligent_exit_logger.py` — ATR
- `infra/intelligent_exit_manager.py` — ATR
- `infra/loss_cut_detector.py` — ATR, MACD, RSI, Bollinger, ADX
- `infra/loss_cut_monitor.py` — ATR
- `infra/loss_cutter.py` — ATR, MACD, RSI, ADX
- `infra/momentum_detector.py` — ATR, MACD
- `infra/multi_timeframe_analyzer.py` — EMA, MACD, RSI, ADX
- `infra/oco_brackets.py` — ATR, Bollinger, ADX
- `infra/openai_service.py` — ATR, EMA, RSI, Bollinger, VWAP, Pivot, ADX
- `infra/position_watcher.py` — ATR, ADX
- `infra/professional_filters.py` — ATR, MACD, RSI, ADX
- `infra/prompt_router.py` — ATR, ADX
- `infra/prompt_templates.py` — ATR, MACD, ADX
- `infra/prompt_validator.py` — ATR, ADX
- `infra/pseudo_pendings.py` — ATR
- `infra/risk_simulation.py` — ATR
- `infra/session_profiles.py` — ATR
- `infra/session_rules.py` — ATR, Bollinger, ADX
- `infra/signal_scanner.py` — RSI, ADX
- `infra/strategy_map.py` — ADX
- `infra/strategy_selector.py` — ADX
- `infra/structure_sl.py` — ATR
- `infra/threshold_tuner.py` — ATR, ADX
- `infra/trade_monitor.py` — ATR
- `infra/trade_setup_watcher.py` — ATR, EMA, MACD, RSI, ADX
- `infra/trailing_stops.py` — ATR
- `infra/virt_pendings.py` — EMA, VWAP, Pivot
- `main_api.py` — ATR, EMA, RSI, ADX
- `technical_analysis.py` — ATR, MACD, RSI, Bollinger, ADX
- `technical_analysis_fixed.py` — ATR, MACD, RSI, Bollinger, ADX
- `technical_analysis_original.py` — ATR, Bollinger, ADX
- `test_api_btc.py` — ATR, RSI, ADX
- `test_exit_monitor.py` — ATR, RSI, VWAP, ADX
- `test_intelligent_exits.py` — ATR
- `test_loss_cut_detector.py` — ATR, MACD, RSI, ADX
- `test_trailing_live.py` — ATR, EMA, MACD
- `tests/test_adaptive_tp.py` — ATR, MACD
- `tests/test_oco_brackets.py` — ATR, ADX
- `tests/test_phase4_1_structure_toolkit.py` — ATR
- `tests/test_phase4_5_integration.py` — ATR, ADX
- `tests/test_structure_sl.py` — ATR
- `tests/test_trailing_stops.py` — ATR
- `tests/validate_phase4_1_live.py` — ATR
- `tools/wick_tuner.py` — ATR, EMA
- `trade_manager.py` — ADX

## Schedulers / Monitoring

- `app/main_api.py` — scheduler/async loop
- `chatgpt_bot.py` — scheduler/async loop
- `handlers/charts.py` — scheduler/async loop
- `infra/pseudo_pendings.py` — scheduler/async loop
- `infra/virt_pendings.py` — scheduler/async loop
- `main_api.py` — scheduler/async loop
- `trade_bot.py` — scheduler/async loop

## Journaling / Storage

- `app/services/oco_tracker.py` — journal/storage
- `app/services/pending_emulator.py` — journal/storage
- `infra/ab_testing.py` — journal/storage
- `infra/analytics_logger.py` — journal/storage
- `infra/chatgpt_logger.py` — journal/storage
- `infra/dashboard_queries.py` — journal/storage
- `infra/intelligent_exit_logger.py` — journal/storage
- `infra/journal_repo.py` — journal/storage
- `infra/memory_store.py` — journal/storage
- `infra/ml_exporter.py` — journal/storage
- `infra/recommendation_logger.py` — journal/storage
- `infra/recommendation_tracker.py` — journal/storage
- `infra/virt_pendings.py` — journal/storage
- `scripts/migrate_expiry_ts.py` — journal/storage
- `test_database_logging.py` — journal/storage
- `tools/wick_tuner.py` — journal/storage

## End-to-End Flow (Mermaid)


```mermaid
flowchart LR
  user[User on Telegram] -->|/analyse, buttons| handlers[Telegram Handlers]
  handlers --> engine[Decision & Strategy Engine]
  engine --> tech[Indicators & Patterns]
  engine --> risk[Risk Model & Guardrails]
  engine -->|plan| gpt[OpenAI Analysis/Critique]
  gpt -->|narrative + structured plan| handlers
  handlers -->|execute/arm OCO| mt5[MT5 Service]
  mt5 --> journal[Journal (CSV/SQLite)]
  sched[Scheduler/Monitors] --> engine
  sched --> mt5
  sched --> handlers
```
