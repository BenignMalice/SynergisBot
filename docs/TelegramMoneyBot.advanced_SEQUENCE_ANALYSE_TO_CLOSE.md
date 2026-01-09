# TelegramMoneyBot.v8 — End-to-End Lifecycle
**Flow:** `/analyse → plan → approve → MT5 execute → monitor → trail/close → journal`

Below are two Mermaid sequence diagrams:
1) **High-Level** user journey.
2) **Detailed** module-level interactions specific to your v8 architecture (handlers, infra, engine, guards, MT5, monitors, journal).

---

## 1) High-Level Sequence

```mermaid
sequenceDiagram
    autonumber
    actor U as User (Telegram)
    participant TG as Telegram Bot
    participant ENG as Decision Engine
    participant GPT as OpenAI Service
    participant MT5 as MT5 Service
    participant MON as Monitors/Scheduler
    participant JR as Journal/DB

    U->>TG: /analyse SYMBOL TF
    TG->>ENG: build_context(symbol, timeframe)
    ENG->>ENG: indicators + patterns + regime + risk
    ENG->>GPT: request narrative + plan + critique
    GPT-->>ENG: structured plan (entry/SL/TP/reasoning)
    ENG-->>TG: plan + inline buttons (Execute / Make Pending / Ignore)

    U->>TG: tap "Execute" (or "Make Pending")
    TG->>ENG: final guardrails check (session/spread/news/exposure)
    ENG->>MT5: place order (market or pending/OCO)
    MT5-->>TG: execution result (ticket, price, slippage)

    TG->>JR: log trade (CSV/SQLite)

    Note over MON,MT5: Background
    MON->>MT5: poll/subscribe positions & orders
    MON->>ENG: evaluate trail logic / adaptive TP
    ENG->>MT5: modify SL/TP / close if needed
    MT5-->>JR: record updates (SL/TP changes, close reason)

    MT5-->>TG: alerts (filled/canceled/SL/TP hit)
    JR-->>TG: periodic summaries / reports
```

---

## 2) Detailed Module-Level Sequence

```mermaid
sequenceDiagram
    autonumber
    actor U as User (Telegram)
    participant H as handlers/trading.py
    participant SEL as app/engine/strategy_selector.py
    participant LOGIC as app/engine/strategy_logic.py
    participant ENG as decision_engine.py
    participant RB as infra/indicator_bridge.py
    participant GR as infra/guardrails.py (exposure/news/spread)
    participant RM as app/engine/risk_model.py
    participant GPT as infra/openai_service.py
    participant MT5 as infra/mt5_service.py
    participant SCH as infra/scheduler.py (monitors)
    participant JR as infra/journal_repo.py

    U->>H: /analyse SYMBOL TF
    H->>ENG: analyse_trade(symbol, timeframe)
    ENG->>RB: fetch bars + compute indicators (ATR, EMA, RSI, MACD...)
    ENG->>LOGIC: detect patterns + market structure
    ENG->>SEL: select strategy (regime + session + config)
    SEL-->>ENG: chosen_strategy (with overrides)
    ENG->>RM: size calc + SL/TP sizing (ATR/structure)
    ENG->>GR: pre-trade guardrails (session, news window, spread, exposure)
    GR-->>ENG: allowed / blocked (+reasons)

    alt allowed
        ENG->>GPT: build prompt (context + tech + plan skeleton)
        GPT-->>ENG: structured plan (entry, SL, TP, confidence, reasoning)
        ENG-->>H: plan payload + inline buttons
    else blocked
        ENG-->>H: decline + reason
    end

    U->>H: tap "Execute" (or "Make Pending / Arm OCO")
    H->>ENG: confirm_and_execute(plan_id)
    ENG->>GR: final guardrails re-check (cooldowns, exposure)
    GR-->>ENG: ok

    alt Market order
        ENG->>MT5: open_market(symbol, volume, sl, tp)
    else Pending/OCO
        ENG->>MT5: place_pending(symbol, stop/limit, sl, tp, expiry)
        ENG->>MT5: optional OCO twin (opposite side)
    end
    MT5-->>ENG: result (ticket, price, slippage, error?)
    ENG-->>H: execution result (success/failure)
    H->>JR: journal_open(trade record)

    par Background Monitor
        SCH->>MT5: poll open positions + orders
        SCH->>ENG: evaluate trailing/adaptive TP logic
        ENG->>MT5: modify_position(sl/tp) or close_position(reason)
        MT5-->>JR: journal_update(modify/close with reason TP/SL/manual)
        MT5-->>H: alert: fill/cancel/sl/tp + optional Acknowledge
    and Pending Watch
        SCH->>MT5: check pending expiries/fills
        SCH->>H: notify fill/cancel
        H->>JR: journal_update(pending status)
    end
```

---

### Notes
- **Guardrails**: combine session windows, news blackouts, spread thresholds, exposure caps, and cooldowns.
- **Risk Model**: converts confidence/context → position size and RR, aligns SL/TP with ATR and structure.
- **Strategy Selector/Logic**: switches filters and overrides per strategy & market regime.
- **Indicator Bridge**: prefers native MT5 handles; falls back to pandas/numpy when needed.
- **Journal Repo**: writes to CSV/SQLite and supports summaries (daily/weekly).

