# TelegramMoneyBot.v8 – Module Map

_Generated: 2025-10-11T07:26:42_

## Top-Level Layout

- **infra**: 68 files
- **(root)**: 35 files
- **handlers**: 16 files
- **domain**: 13 files
- **tests**: 11 files
- **app**: 10 files
- **scripts**: 2 files
- **config**: 1 files
- **tools**: 1 files

## Detected Roles

- **infrastructure-service**: 68 files
- **entrypoint**: 20 files
- **telegram-handlers**: 16 files
- **module**: 14 files
- **domain-logic**: 13 files
- **tests**: 11 files
- **decision-engine**: 6 files
- **fastapi-app**: 5 files
- **telegram-bot**: 3 files
- **configuration**: 1 files

## High-Level Dependency Graph (Mermaid)

```mermaid
flowchart LR
  "a.engine.regime_classifier" --> "i.strategy_map"
  "a.engine.risk_sizing" --> "a.engine.strategy_logic"
  "a.engine.strategy_logic" --> "config"
  "a.engine.strategy_logic" --> "d.market_structure"
  "a.engine.strategy_logic" --> "d.patterns"
  "a.engine.strategy_logic" --> "i.formatting"
  "a.engine.strategy_logic" --> "i.strategy_map"
  "a.engine.strategy_logic.bak" --> "config"
  "a.engine.strategy_logic.bak" --> "d.market_structure"
  "a.engine.strategy_logic.bak" --> "d.patterns"
  "a.engine.strategy_logic.bak" --> "i.formatting"
  "a.engine.strategy_logic.bak" --> "i.strategy_map"
  "a.main_api" --> "a.engine.regime_classifier"
  "a.main_api" --> "a.services.oco_tracker"
  "a.main_api" --> "config"
  "a.main_api" --> "d.patterns"
  "a.main_api" --> "i.confluence_calculator"
  "a.main_api" --> "i.indicator_bridge"
  "a.main_api" --> "i.intelligent_exit_logger"
  "a.main_api" --> "i.intelligent_exit_manager"
  "a.main_api" --> "i.journal_repo"
  "a.main_api" --> "i.market_indices_service"
  "a.main_api" --> "i.mt5_service"
  "a.main_api" --> "i.multi_timeframe_analyzer"
  "a.main_api" --> "i.news_service"
  "a.main_api" --> "i.openai_service"
  "a.main_api" --> "i.price_alerts"
  "a.main_api" --> "i.recommendation_tracker"
  "a.main_api" --> "i.session_analyzer"
  "a.services.oco_tracker" --> "i.journal_repo"
  "a.services.pending_emulator" --> "i.mt5_service"
  "chatgpt_bot" --> "config"
  "chatgpt_bot" --> "h.chatgpt_bridge"
  "chatgpt_bot" --> "i.analytics_logger"
  "chatgpt_bot" --> "i.chatgpt_logger"
  "chatgpt_bot" --> "i.dashboard_queries"
  "chatgpt_bot" --> "i.exit_monitor"
  "chatgpt_bot" --> "i.feature_builder"
  "chatgpt_bot" --> "i.indicator_bridge"
  "chatgpt_bot" --> "i.intelligent_exit_manager"
  "chatgpt_bot" --> "i.journal_repo"
  "chatgpt_bot" --> "i.loss_cutter"
  "chatgpt_bot" --> "i.mt5_service"
  "chatgpt_bot" --> "i.news_service"
  "chatgpt_bot" --> "i.professional_filters"
  "chatgpt_bot" --> "i.recommendation_tracker"
  "chatgpt_bot" --> "i.session_analyzer"
  "chatgpt_bot" --> "i.trade_monitor"
  "chatgpt_bot" --> "i.trade_setup_watcher"
  "decision_engine" --> "config"
  "decision_engine" --> "d.breakout_quality"
  "decision_engine" --> "d.candle_stats"
  "decision_engine" --> "d.candles"
  "decision_engine" --> "d.confluence"
  "decision_engine" --> "d.levels"
  "decision_engine" --> "d.liquidity"
  "decision_engine" --> "d.market_structure"
  "decision_engine" --> "d.patterns"
  "decision_engine" --> "d.zones"
  "decision_engine" --> "i.oco_brackets"
  "decision_engine" --> "i.price_utils"
  "diagnose_dxy_symbols" --> "config"
  "d.zones" --> "config"
  "h.charts" --> "config"
  "h.charts" --> "i.chart_arranger"
  "h.charts" --> "trade_manager"
  "h.chatgpt_bridge" --> "i.alpha_vantage_service"
  "h.chatgpt_bridge" --> "i.analytics_logger"
  "h.chatgpt_bridge" --> "i.chatgpt_logger"
  "h.chatgpt_bridge" --> "i.market_indices_service"
  "h.chatgpt_bridge" --> "i.news_service"
  "h.chatgpt_bridge" --> "i.recommendation_tracker"
  "h.feature_builder" --> "config"
  "h.feature_builder" --> "i.feature_builder"
  "h.feature_builder" --> "i.indicator_bridge"
  "h.feature_builder" --> "i.mt5_service"
  "h.menu" --> "h.charts"
  "h.menu" --> "h.help"
  "h.menu" --> "h.pending"
  "h.menu" --> "h.status"
  "h.menu" --> "h.trading"
  "h.pending" --> "config"
  "h.pending" --> "d.breakout_quality"
  "h.pending" --> "d.liquidity"
  "h.pending" --> "d.market_structure"
  "h.pending" --> "d.zones"
  "h.pending" --> "h.menu"
  "h.pending" --> "h.trading"
  "h.pending" --> "i.bandit_autoupdate"
  "h.pending" --> "i.formatting"
  "h.pending" --> "i.indicator_bridge"
  "h.pending" --> "i.journal_repo"
  "h.pending" --> "i.mt5_service"
  "h.pending" --> "i.news_service"
  "h.pending" --> "i.openai_service"
  "h.pending" --> "i.strategy_map"
  "h.pending" --> "i.virt_pendings"
  "h.pending.bak" --> "config"
  "h.pending.bak" --> "d.breakout_quality"
  "h.pending.bak" --> "d.liquidity"
  "h.pending.bak" --> "d.market_structure"
  "h.pending.bak" --> "d.zones"
  "h.pending.bak" --> "h.menu"
  "h.pending.bak" --> "h.trading"
  "h.pending.bak" --> "i.bandit_autoupdate"
  "h.pending.bak" --> "i.formatting"
  "h.pending.bak" --> "i.indicator_bridge"
  "h.pending.bak" --> "i.journal_repo"
  "h.pending.bak" --> "i.mt5_service"
  "h.pending.bak" --> "i.news_service"
  "h.pending.bak" --> "i.openai_service"
  "h.pending.bak" --> "i.strategy_map"
  "h.pending.bak" --> "i.virt_pendings"
  "h.prompt_router" --> "i.prompt_router"
  "h.reco_modes" --> "config"
  "h.signal_scanner" --> "config"
  "h.signal_scanner" --> "i.indicator_bridge"
  "h.signal_scanner" --> "i.openai_service"
  "h.signal_scanner" --> "i.signal_scanner"
  "h.status" --> "i.mt5_service"
  "h.status" --> "i.pseudo_pendings"
  "h.trading" --> "a.engine.risk_model"
  "h.trading" --> "a.engine.strategy_logic"
  "h.trading" --> "config"
  "h.trading" --> "decision_engine"
  "h.trading" --> "d.candles"
  "h.trading" --> "d.rules"
  "h.trading" --> "h.menu"
  "h.trading" --> "i.bandit_autoupdate"
  "h.trading" --> "i.chart_arranger"
  "h.trading" --> "i.confidence_calibrator"
  "h.trading" --> "i.exposure_guard"
  "h.trading" --> "i.feature_builder"
  "h.trading" --> "i.formatting"
  "h.trading" --> "i.guardrails"
  "h.trading" --> "i.indicator_bridge"
  "h.trading" --> "i.journal_repo"
  "h.trading" --> "i.memory_store"
  "h.trading" --> "i.mt5_service"
  "h.trading" --> "i.news_service"
  "h.trading" --> "i.openai_service"
  "h.trading" --> "i.postmortem"
  "h.trading" --> "i.risk_simulation"
  "h.trading" --> "i.strategy_selector"
  "h.trading" --> "i.threshold_tuner"
  "i.adaptive_tp" --> "i.momentum_detector"
  "i.alpha_vantage_service" --> "config"
  "i.bandit_autoupdate" --> "config"
  "i.bandit_autoupdate" --> "i.strategy_selector"
  "i.circuit_breaker" --> "config"
  "i.dxy_service" --> "config"
  "i.exposure_guard" --> "config"
  "i.feature_builder" --> "config"
  "i.feature_builder" --> "i.feature_indicators"
  "i.feature_builder" --> "i.feature_microstructure"
  "i.feature_builder" --> "i.feature_patterns"
  "i.feature_builder" --> "i.feature_session_news"
  "i.feature_builder" --> "i.feature_structure"
  "i.feature_builder" --> "i.indicator_bridge"
  "i.feature_builder" --> "i.mt5_service"
  "i.feature_builder_fast" --> "i.indicator_bridge"
  "i.feature_builder_fast" --> "i.mt5_service"
  "i.feature_structure" --> "d.candle_stats"
  "i.feature_structure" --> "d.fvg"
  "i.feature_structure" --> "d.liquidity"
  "i.feature_structure" --> "d.market_structure"
  "i.guardrails" --> "config"
  "i.guardrails" --> "i.exposure_guard"
  "i.guardrails" --> "i.mt5_service"
  "i.guardrails" --> "i.news_service"
  "i.intelligent_exit_manager" --> "i.intelligent_exit_logger"
  "i.intelligent_exit_manager" --> "i.market_indices_service"
  "i.journal_repo" --> "config"
  "i.loss_cutter" --> "config"
  "i.loss_cutter" --> "i.exit_signal_detector"
  "i.loss_cutter" --> "i.mt5_service"
  "i.loss_cutter" --> "i.risk_simulation"
  "i.mt5_service" --> "config"
  "i.mt5_service" --> "i.indicator_bridge"
  "i.mt5_service" --> "i.professional_filters"
  "i.news_service" --> "config"
  "i.openai_service" --> "config"
  "i.openai_service" --> "i.adaptive_tp"
  "i.openai_service" --> "i.guardrails"
  "i.openai_service" --> "i.prompt_router"
  "i.openai_service" --> "i.risk_simulation"
  "i.openai_service" --> "i.structure_sl"
  "i.position_watcher" --> "config"
  "i.position_watcher" --> "i.indicator_bridge"
  "i.position_watcher" --> "i.mt5_service"
  "i.prompt_router" --> "a.engine.regime_classifier"
  "i.prompt_router" --> "i.feature_session_news"
  "i.prompt_router" --> "i.prompt_templates"
  "i.prompt_router" --> "i.prompt_validator"
  "i.prompt_router" --> "i.session_rules"
  "i.pseudo_pendings" --> "config"
  "i.pseudo_pendings" --> "i.circuit_breaker"
  "i.pseudo_pendings" --> "i.exposure_guard"
  "i.pseudo_pendings" --> "i.journal_repo"
  "i.pseudo_pendings" --> "i.mt5_service"
  "i.scheduler" --> "config"
  "i.signal_scanner" --> "config"
  "i.signal_scanner" --> "decision_engine"
  "i.signal_scanner" --> "i.feature_builder"
  "i.signal_scanner" --> "i.indicator_bridge"
  "i.signal_scanner" --> "i.mt5_service"
  "i.signal_scanner" --> "i.openai_service"
  "i.signal_scanner" --> "i.strategy_selector"
  "i.strategy_selector" --> "a.engine.regime_classifier"
  "i.strategy_selector" --> "a.engine.strategy_logic"
  "i.strategy_selector" --> "config"
  "i.strategy_selector" --> "i.memory_store"
  "i.trade_monitor" --> "config"
  "i.trade_monitor" --> "i.momentum_detector"
  "i.trade_monitor" --> "i.trailing_stops"
  "i.trade_setup_watcher" --> "config"
  "i.trailing_stops" --> "i.momentum_detector"
  "i.virt_pendings" --> "config"
  "i.virt_pendings" --> "i.indicator_bridge"
  "i.virt_pendings" --> "i.mt5_service"
  "main_api" --> "a.engine.regime_classifier"
  "main_api" --> "a.services.oco_tracker"
  "main_api" --> "config"
  "main_api" --> "d.patterns"
  "main_api" --> "i.indicator_bridge"
  "main_api" --> "i.journal_repo"
  "main_api" --> "i.market_indices_service"
  "main_api" --> "i.mt5_service"
  "main_api" --> "i.openai_service"
  "main_api" --> "i.recommendation_tracker"
  "test_analyzer_debug" --> "i.indicator_bridge"
  "test_analyzer_direct" --> "i.indicator_bridge"
  "test_api_startup" --> "a.main_api"
  "test_api_startup" --> "config"
  "test_api_startup" --> "i.journal_repo"
  "test_api_startup" --> "i.mt5_service"
  "test_database_logging" --> "i.ab_testing"
  "test_database_logging" --> "i.analytics_logger"
  "test_database_logging" --> "i.chatgpt_logger"
  "test_database_logging" --> "i.dashboard_queries"
  "test_database_logging" --> "i.ml_exporter"
  "test_database_logging" --> "i.recommendation_logger"
  "test_dxy_integration" --> "config"
  "test_indicator_bridge_direct" --> "i.indicator_bridge"
  "test_intelligent_exits" --> "i.intelligent_exit_manager"
  "test_trailing_live" --> "i.indicator_bridge"
  "test_trailing_live" --> "i.momentum_detector"
  "test_trailing_live" --> "i.mt5_service"
  "test_us10y" --> "i.market_indices_service"
  "tests.test_adaptive_tp" --> "i.momentum_detector"
  "tests.test_phase4_1_integration" --> "i.feature_structure"
  "tests.test_phase4_1_structure_toolkit" --> "d.liquidity"
  "tests.test_phase4_1_structure_toolkit" --> "d.market_structure"
  "tests.test_phase4_2_integration" --> "i.prompt_router"
  "tests.test_phase4_5_integration" --> "config"
  "tests.test_phase4_5_integration" --> "h.trading"
  "tests.test_phase4_5_integration" --> "i.adaptive_tp"
  "tests.test_phase4_5_integration" --> "i.momentum_detector"
  "tests.test_phase4_5_integration" --> "i.oco_brackets"
  "tests.test_phase4_5_integration" --> "i.openai_service"
  "tests.test_phase4_5_integration" --> "i.structure_sl"
  "tests.test_phase4_5_integration" --> "i.trade_monitor"
  "tests.test_phase4_5_integration" --> "i.trailing_stops"
  "tests.validate_phase4_1_live" --> "i.feature_builder"
  "tests.validate_phase4_1_live" --> "i.indicator_bridge"
  "tests.validate_phase4_1_live" --> "i.mt5_service"
  "trade_bot" --> "config"
  "trade_bot" --> "h.charts"
  "trade_bot" --> "h.chatgpt_bridge"
  "trade_bot" --> "h.circuit"
  "trade_bot" --> "h.errors"
  "trade_bot" --> "h.feature_builder"
  "trade_bot" --> "h.help"
  "trade_bot" --> "h.journal"
  "trade_bot" --> "h.menu"
  "trade_bot" --> "h.pending"
  "trade_bot" --> "h.prompt_router"
  "trade_bot" --> "h.signal_scanner"
  "trade_bot" --> "h.trading"
  "trade_bot" --> "i.circuit_breaker"
  "trade_bot" --> "i.feature_builder"
  "trade_bot" --> "i.indicator_bridge"
  "trade_bot" --> "i.journal_repo"
  "trade_bot" --> "i.mt5_service"
  "trade_bot" --> "i.position_watcher"
  "trade_bot" --> "i.scheduler"
  "trade_bot" --> "i.signal_scanner"
  "trade_bot" --> "i.trade_monitor"
  "trade_bot" --> "i.virt_pendings"
  "trade_manager" --> "config"
  "trade_manager" --> "i.indicator_bridge"
  "trade_manager" --> "i.mt5_service"
```

## Notable Entrypoints & Services (heuristic)

- **Entrypoints**:
  - `app/engine/strategy_logic.bak.py`
  - `app/engine/strategy_logic.py`
  - `app/main_api.py`
  - `chatgpt_bot.py`
  - `check_symbol.py`
  - `collect_code.py`
  - `debug_indicator_bridge.py`
  - `fetch_news_feed.py`
  - `main_api.py`
  - `scripts/migrate_expiry_ts.py`
  - `scripts/migrate_pendings_json.py`
  - `test_analyzer_debug.py`
  - `test_analyzer_direct.py`
  - `test_api_btc.py`
  - `test_api_debug.py`
  - `test_api_final.py`
  - `test_database_logging.py`
  - `test_enhancements.py`
  - `test_exit_monitor.py`
  - `test_indicator_bridge_direct.py`
  - … (+18 more)
- **FastAPI apps/routers**:
  - `app/main_api.py`
  - `app/services/oco_tracker.py`
  - `main_api.py`
  - `test_api_startup.py`
  - `test_price_alerts.py`
- **Telegram bot modules**:
  - `chatgpt_bot.py`
  - `chatgpt_bridge.py`
  - `handlers/charts.py`
  - `handlers/chatgpt_bridge.py`
  - `handlers/circuit.py`
  - `handlers/errors.py`
  - `handlers/feature_builder.py`
  - `handlers/help.py`
  - `handlers/journal.py`
  - `handlers/menu.py`
  - `handlers/pending.bak.py`
  - `handlers/pending.py`
  - `handlers/prompt_router.py`
  - `handlers/signal_scanner.py`
  - `handlers/status.py`
  - `handlers/trading.py`
  - `infra/scheduler.py`
  - `trade_bot.py`
- **MetaTrader/MT5 integrations**:
  - `app/main_api.py`
  - `app/services/oco_tracker.py`
  - `app/services/pending_emulator.py`
  - `chatgpt_bot.py`
  - `check_mt5_dxy.py`
  - `check_symbol.py`
  - `debug_indicator_bridge.py`
  - `handlers/chatgpt_bridge.py`
  - `handlers/feature_builder.py`
  - `handlers/pending.bak.py`
  - `handlers/pending.py`
  - `handlers/status.py`
  - `handlers/trading.py`
  - `indicator_bridge.py`
  - `infra/exit_monitor.py`
  - `infra/exposure_guard.py`
  - `infra/feature_builder.py`
  - `infra/feature_builder_fast.py`
  - `infra/formatting.py`
  - `infra/guardrails.py`
  - … (+27 more)
- **Database-related modules**:
  - `app/services/oco_tracker.py`
  - `app/services/pending_emulator.py`
  - `infra/ab_testing.py`
  - `infra/analytics_logger.py`
  - `infra/chatgpt_logger.py`
  - `infra/dashboard_queries.py`
  - `infra/intelligent_exit_logger.py`
  - `infra/journal_repo.py`
  - `infra/memory_store.py`
  - `infra/ml_exporter.py`
  - `infra/recommendation_logger.py`
  - `infra/recommendation_tracker.py`
  - `infra/virt_pendings.py`
  - `scripts/migrate_expiry_ts.py`
  - `test_database_logging.py`
- **Schedulers/cron**:
  - `app/main_api.py`
  - `chatgpt_bot.py`
  - `handlers/pending.bak.py`
  - `handlers/pending.py`
  - `infra/scheduler.py`
  - `main_api.py`
  - `tests/test_phase4_5_integration.py`
  - `trade_bot.py`

## How to Read This Map
- **module_edges.csv**: directed edges of internal imports (`source -> target`).
- **module_inventory.csv**: every module with role guess and tags.
- **Mermaid graph**: paste into a Mermaid viewer (or GitHub Markdown) to visualize dependencies.
