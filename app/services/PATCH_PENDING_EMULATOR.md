# Patch: Emulated Pending Orders for Cent Accounts

This patch adds **software-emulated pending orders** for brokers/accounts that do **not** support broker-side pending orders (e.g., Exness Cent).

## What you get
- A new module: `app/services/pending_emulator.py`
- SQLite-backed storage for virtual pendings
- A trigger loop: converts a virtual pending into a **market order** the moment price crosses the entry within a **slippage tolerance**.
- Telegram notifications (optional; uses `send_trade_alert` if available).

## How to wire it

### 1) Install the module
The file is already created at:
```
app/services/pending_emulator.py
```

### 2) Schedule the trigger loop
In your `trade_manager.py` (or the background loop you already run), add:

```python
# --- top of file ---
from app.services.pending_emulator import check_and_trigger

# --- inside your scheduler / loop (every 5–15 seconds recommended) ---
processed = check_and_trigger(db_path="data/bot.sqlite", notify=True)
if processed:
    logger.info("Virtual pending sweep processed: %s", processed)
```

If you use APScheduler:
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler(timezone="UTC")
scheduler.add_job(lambda: check_and_trigger("data/bot.sqlite", True), "interval", seconds=10, id="virt_pending")
scheduler.start()
```

### 3) Offer a UI path in Telegram
Instead of a real **Pending** button, show **Arm at Entry (Emulated)**. On tap, insert a `VirtualPending` record:

```python
from app.services.pending_emulator import VirtualPending, create_virtual_pending
import time

# example inside a callback handler
vp = VirtualPending(
    id=None,
    symbol=symbol,          # e.g., "XAUUSDc" (ensure suffix!)
    side="BUY",             # or "SELL"
    entry=entry_price,
    sl=sl_price,
    tp=tp_price,
    volume=volume_lots,
    order_kind="STOP",      # or "LIMIT"
    slippage_pts=30,        # allow 30 points slippage (adjust to your broker)
    expiry_ts=int(time.time()) + 60*45,  # 45 minutes expiry
    comment="signal-123"
)
pending_id = create_virtual_pending(vp, db_path="data/bot.sqlite")
await reply.reply_text(f"🧭 Armed virtual pending (#{pending_id}): {symbol} {vp.side} @ {vp.entry}")
```

### 4) Ensure symbol suffix handling
Before creating a virtual pending, make sure your symbol is the **cent** variant (e.g., `XAUUSDc`). If unsure, add a helper that appends `c` if the `symbol_info` exists only with that suffix.

### 5) Journalling
When a virtual pending **fills** or **expires**, it’s logged inside SQLite. You can mirror to CSV from your existing journal module if desired.

## Safety & behaviour
- **Fill logic** uses market orders at tick price when entry is crossed.
- **Slippage tolerance** is expressed in points (broker digits).
- Orders **expire** automatically if `expiry_ts` is set and reached.
- If order placement fails, the pending is set to **CANCELLED** with a reason, and you get a Telegram notification (if configured).

## Configuration knobs
- `slippage_pts` per pending (recommend broker-specific defaults)
- `expiry_ts` per pending (default None for no expiry)
- Scheduler interval (10–15 seconds is a good starting point)
