# File: trade_manager.py
# ----------------------
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, Optional, List, Set, Tuple
import json
from datetime import datetime, timezone

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from config import settings
from infra.mt5_service import MT5Service
from infra.indicator_bridge import IndicatorBridge  # for richer snapshots from your EA

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------------------
# Services
# --------------------------------------------------------------------------------------
mt5svc = MT5Service()
bridge = IndicatorBridge(settings.MT5_FILES_DIR)

# --------------------------------------------------------------------------------------
# Chat registration API (as expected by handlers/charts.py)
# --------------------------------------------------------------------------------------
_REGISTERED_CHATS: Set[int] = set()


def register_chat(chat_id: int) -> None:
    """Register a chat for manager notifications (used by handlers/charts.py)."""
    try:
        _REGISTERED_CHATS.add(int(chat_id))
        logger.info(f"Registered chat {chat_id} for trade manager alerts.")
    except Exception:
        logger.warning("Failed to register chat id: %s", chat_id)


def unregister_chat(chat_id: int) -> None:
    try:
        _REGISTERED_CHATS.discard(int(chat_id))
        logger.info(f"Unregistered chat {chat_id}.")
    except Exception:
        pass


def registered_chats() -> List[int]:
    return list(_REGISTERED_CHATS)


# Convenience aliases (won’t break anything if unused)
def subscribe_chat(chat_id: int) -> None:
    register_chat(chat_id)


def add_chat(chat_id: int) -> None:
    register_chat(chat_id)


def remove_chat(chat_id: int) -> None:
    unregister_chat(chat_id)


def get_registered_chats() -> List[int]:
    return registered_chats()


# --------------------------------------------------------------------------------------
# Messaging helpers
# --------------------------------------------------------------------------------------
async def notify_chat(bot, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id=int(chat_id), text=text)
    except Exception as e:
        logger.warning("notify_chat to %s failed: %s", chat_id, e)


async def broadcast(bot, text: str) -> None:
    for cid in list(_REGISTERED_CHATS):
        try:
            await bot.send_message(chat_id=cid, text=text)
        except Exception as e:
            logger.warning("Broadcast to %s failed: %s", cid, e)


# --------------------------------------------------------------------------------------
# Strict-JSON extractor (brace-balancer; no recursive regex)
# --------------------------------------------------------------------------------------
def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract the first top-level {...} object from arbitrary text using a brace stack.
    Returns a dict or None.
    """
    if not text:
        return None
    # Quick path: pure JSON
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                blob = text[start : i + 1]
                try:
                    obj = json.loads(blob)
                    return obj if isinstance(obj, dict) else None
                except Exception:
                    return None
    return None


# --------------------------------------------------------------------------------------
# Market context helpers
# --------------------------------------------------------------------------------------
def _ensure_symbol(symbol: str) -> None:
    info = mt5.symbol_info(symbol)
    if not info or not info.visible:
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Cannot select '{symbol}' in Market Watch")


def _fetch_rates(symbol: str, timeframe: int, count: int = 300) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No rates for {symbol} tf={timeframe}")
    df = pd.DataFrame(rates)
    if df.empty:
        raise RuntimeError("Empty dataframe")
    return df


def _atr(h: np.ndarray, l: np.ndarray, c: np.ndarray, period: int = 14) -> float:
    prev_c = np.roll(c, 1)
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    return float(pd.Series(tr).rolling(period).mean().iloc[-1])


def _adx(h: np.ndarray, l: np.ndarray, c: np.ndarray, period: int = 14) -> float:
    up = h - np.roll(h, 1)
    dn = np.roll(l, 1) - l
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = np.maximum(
        h - l, np.maximum(np.abs(h - np.roll(c, 1)), np.abs(l - np.roll(c, 1)))
    )
    atr14 = pd.Series(tr).rolling(period).mean().to_numpy()
    plus_di = 100 * (
        pd.Series(plus_dm).rolling(period).mean().to_numpy()
        / np.where(atr14 == 0, 1, atr14)
    )
    minus_di = 100 * (
        pd.Series(minus_dm).rolling(period).mean().to_numpy()
        / np.where(atr14 == 0, 1, atr14)
    )
    dx = (
        100
        * np.abs(plus_di - minus_di)
        / np.where((plus_di + minus_di) == 0, 1, (plus_di + minus_di))
    )
    return float(pd.Series(dx).rolling(period).mean().iloc[-1])


def build_market_ctx(symbol: str) -> Dict[str, Any]:
    """
    Prefer your IndicatorBridge (EA snapshot). If not available yet,
    compute minimal context from MT5 rates.
    """
    try:
        multi = bridge.get_multi(symbol)
        m5 = multi.get("M5", {})
        h1 = multi.get("H1", {})
        last = mt5.symbol_info_tick(symbol)
        price = float(last.ask or last.bid) if last else float(m5.get("close", 0) or 0)

        ctx = {
            "symbol": symbol,
            "price": price,
            "atr_14_m5": float(m5.get("atr_14") or 0),
            "atr_14_h1": float(h1.get("atr_14") or m5.get("atr_14") or 0)
            * (1.0 if h1.get("atr_14") else 3.0),
            "adx_14_m15": float(
                m5.get("adx_14") or 0
            ),  # some bridges place ADX on M5; good enough
            "spread_points": None,
        }
        if last:
            info = mt5.symbol_info(symbol)
            if info and info.point:
                ctx["spread_points"] = abs(float(last.ask - last.bid) / info.point)
        return ctx
    except Exception:
        # Fallback: compute from MT5 data
        _ensure_symbol(symbol)
        df5 = _fetch_rates(symbol, mt5.TIMEFRAME_M5, 200)
        df15 = _fetch_rates(symbol, mt5.TIMEFRAME_M15, 200)
        try:
            df60 = _fetch_rates(symbol, mt5.TIMEFRAME_H1, 200)
            atr_h1 = _atr(
                df60["high"].to_numpy(),
                df60["low"].to_numpy(),
                df60["close"].to_numpy(),
                14,
            )
        except Exception:
            atr_m5 = _atr(
                df5["high"].to_numpy(),
                df5["low"].to_numpy(),
                df5["close"].to_numpy(),
                14,
            )
            atr_h1 = float(atr_m5 * 3.0)

        adx_m15 = _adx(
            df15["high"].to_numpy(),
            df15["low"].to_numpy(),
            df15["close"].to_numpy(),
            14,
        )
        last = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        spread_pts = None
        if last and info and info.point:
            spread_pts = abs(float(last.ask - last.bid) / info.point)

        return {
            "symbol": symbol,
            "price": float(df5["close"].iloc[-1]),
            "atr_14_m5": _atr(
                df5["high"].to_numpy(),
                df5["low"].to_numpy(),
                df5["close"].to_numpy(),
                14,
            ),
            "atr_14_h1": float(atr_h1),
            "adx_14_m15": float(adx_m15),
            "spread_points": spread_pts,
        }


# --------------------------------------------------------------------------------------
# LLM-driven trade management (move SL/TP, breakeven, trail, close_half, close_all)
# --------------------------------------------------------------------------------------
def ask_chatgpt_manage(trade: Dict[str, Any], market: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get a management action in strict JSON. Valid actions:
      hold | move_sl | move_tp | breakeven | trail | close_half | close_all
    Returns: {action:str, new_sl:float|None, new_tp:float|None, reason:str}
    """
    sys = (
        "You are a disciplined intraday trade manager. "
        "Return STRICT JSON only (no markdown). "
        "Keys: action, new_sl, new_tp, reason. "
        "Valid actions: ['hold','move_sl','move_tp','breakeven','trail','close_half','close_all']."
    )
    user = f"""
Trade:
{trade}

Market snapshot:
{market}

Rules:
- If unrealised PnL is meaningfully positive and structure supports it: consider breakeven or trail.
- If thesis is invalidated or risk elevated: consider close_half / close_all.
- If 'breakeven': set new_sl to entry (from trade), leave new_tp null.
Output STRICT JSON only.
"""

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": user},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = (resp.choices[0].message.content or "").strip()
        data = _extract_json_object(content)
        if isinstance(data, dict):
            action = str(data.get("action", "hold")).lower().strip()
            if action not in {
                "hold",
                "move_sl",
                "move_tp",
                "breakeven",
                "trail",
                "close_half",
                "close_all",
            }:
                action = "hold"
            return {
                "action": action,
                "new_sl": data.get("new_sl"),
                "new_tp": data.get("new_tp"),
                "reason": str(data.get("reason", "OK")),
            }
        logger.warning(
            "ask_chatgpt_manage: could not parse JSON; preview: %s",
            content[:240] if content else "<empty>",
        )
    except Exception as e:
        logger.warning("ask_chatgpt_manage fallback due to: %s", e)

    # Safe fallback
    return {
        "action": "hold",
        "new_sl": None,
        "new_tp": None,
        "reason": "Fallback/invalid JSON",
    }


# --------------------------------------------------------------------------------------
# MT5 action helpers (modify SL/TP, partial/total close)
# --------------------------------------------------------------------------------------
def _modify_sltp(
    symbol: str, position_id: int, sl: Optional[float], tp: Optional[float]
) -> Tuple[bool, str]:
    req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": symbol,
        "position": int(position_id),
        "sl": float(sl) if sl is not None else 0.0,
        "tp": float(tp) if tp is not None else 0.0,
        "magic": 424242,
        "comment": "SynergisMgr",
    }
    res = mt5.order_send(req)
    if res is None:
        return False, "order_send returned None"
    return res.retcode == mt5.TRADE_RETCODE_DONE, str(res)


def _close_partial(
    symbol: str, ticket: int, direction: str, volume_open: float, volume_to_close: float
) -> Tuple[bool, str]:
    """
    Close part of a position by sending an opposite deal with reduced volume.
    """
    _ensure_symbol(symbol)
    price_tick = mt5.symbol_info_tick(symbol)
    if not price_tick:
        return False, "No tick data"
    typ = mt5.ORDER_TYPE_SELL if direction.upper() == "BUY" else mt5.ORDER_TYPE_BUY
    price = float(price_tick.bid if typ == mt5.ORDER_TYPE_SELL else price_tick.ask)
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "position": int(ticket),
        "volume": float(volume_to_close),
        "type": typ,
        "price": price,
        "deviation": 50,
        "magic": 424242,
        "comment": "SynergisMgr partial close",
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(req)
    if res is None:
        return False, "order_send returned None"
    return res.retcode == mt5.TRADE_RETCODE_DONE, str(res)


def _close_all(
    symbol: str, ticket: int, direction: str, volume_open: float
) -> Tuple[bool, str]:
    return _close_partial(symbol, ticket, direction, volume_open, volume_open)


def _sanitise_levels(
    direction: str, price: float, sl: Optional[float], tp: Optional[float]
) -> Tuple[Optional[float], Optional[float]]:
    """
    Ensure SL/TP are on the correct side of price; if not, drop the offending one.
    """
    if sl is not None:
        if direction.upper() == "BUY" and sl >= price:
            sl = None
        if direction.upper() == "SELL" and sl <= price:
            sl = None
    if tp is not None:
        if direction.upper() == "BUY" and tp <= price:
            tp = None
        if direction.upper() == "SELL" and tp >= price:
            tp = None
    return sl, tp


# --------------------------------------------------------------------------------------
# Public monitor loop (called by handlers/charts.py)
# --------------------------------------------------------------------------------------
async def monitor_live_trades(bot) -> None:
    """
    Poll open positions, ask the LLM for management decisions, and apply them safely.
    Debounces actions per ticket to avoid spam.
    """
    logger.info("trade_manager: monitor loop started")
    # Ensure MT5 is initialised
    try:
        mt5svc.connect()
    except Exception as e:
        logger.warning(f"MT5 connect warning: {e}")

    last_action_ts: Dict[int, float] = {}  # ticket -> epoch seconds
    MIN_INTERVAL = 30  # seconds between decisions per ticket

    while True:
        try:
            await asyncio.sleep(2)

            positions = mt5.positions_get()
            if not positions:
                continue

            for pos in positions:
                try:
                    ticket = int(pos.ticket)
                    now = asyncio.get_event_loop().time()
                    if (
                        ticket in last_action_ts
                        and (now - last_action_ts[ticket]) < MIN_INTERVAL
                    ):
                        continue  # debounce

                    symbol = str(pos.symbol)
                    volume = float(pos.volume)
                    direction = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                    entry_price = float(pos.price_open)
                    sl_cur = float(pos.sl) if pos.sl else None
                    tp_cur = float(pos.tp) if pos.tp else None

                    # Build market context
                    ctx = build_market_ctx(symbol)
                    price = float(ctx.get("price", 0.0))

                    # Assemble trade dict for the LLM
                    trade_dict = {
                        "ticket": ticket,
                        "symbol": symbol,
                        "direction": direction,
                        "entry": entry_price,
                        "sl": sl_cur,
                        "tp": tp_cur,
                        "volume": volume,
                        "price_now": price,
                        "unrealised_points": (
                            (price - entry_price)
                            if direction == "BUY"
                            else (entry_price - price)
                        ),
                        "atr_14_h1": ctx.get("atr_14_h1"),
                    }

                    decision = ask_chatgpt_manage(trade_dict, ctx)
                    action = decision.get("action", "hold")

                    # Nothing to do
                    if action == "hold":
                        last_action_ts[ticket] = now
                        continue

                    # Compute target levels (sanity check)
                    new_sl = decision.get("new_sl")
                    new_tp = decision.get("new_tp")

                    # Breakeven: SL = entry
                    if action == "breakeven":
                        new_sl = float(entry_price)
                        new_tp = tp_cur  # unchanged

                    # Trail: only move SL in the protective direction
                    if action == "trail" and new_sl is not None:
                        if (
                            direction == "BUY"
                            and sl_cur is not None
                            and new_sl <= sl_cur
                        ):
                            new_sl = None  # do not worsen
                        if (
                            direction == "SELL"
                            and sl_cur is not None
                            and new_sl >= sl_cur
                        ):
                            new_sl = None

                    # Sanitise vs current price (drop illegal levels)
                    new_sl, new_tp = _sanitise_levels(direction, price, new_sl, new_tp)

                    # Execute management
                    ok = True
                    msg = ""
                    if action in ("move_sl", "move_tp", "breakeven", "trail"):
                        if new_sl is None and new_tp is None:
                            ok, msg = False, "No valid SL/TP to modify"
                        else:
                            ok, msg = _modify_sltp(
                                symbol,
                                ticket,
                                new_sl if new_sl is not None else sl_cur,
                                new_tp if new_tp is not None else tp_cur,
                            )

                    elif action == "close_half":
                        vol_to_close = round(volume / 2.0, 2)
                        if vol_to_close <= 0:
                            ok, msg = False, "Volume too small to close half"
                        else:
                            ok, msg = _close_partial(
                                symbol, ticket, direction, volume, vol_to_close
                            )

                    elif action == "close_all":
                        ok, msg = _close_all(symbol, ticket, direction, volume)

                    else:
                        ok, msg = False, f"Unknown action '{action}'"

                    # Record debounce time
                    last_action_ts[ticket] = now

                    # Notify chats
                    human = f"🔧 {symbol} #{ticket} — {action.upper()} {'✅' if ok else '❌'}"
                    details = []
                    if action in ("move_sl", "breakeven", "trail") and (
                        new_sl is not None
                    ):
                        details.append(f"SL→ {new_sl:.2f}")
                    if action in ("move_tp",) and (new_tp is not None):
                        details.append(f"TP→ {new_tp:.2f}")
                    if action in ("close_half", "close_all"):
                        details.append(f"Vol: {volume}")
                    if decision.get("reason"):
                        details.append(f"Why: {decision['reason']}")
                    if msg:
                        details.append(msg)

                    note = human + ("\n• " + "\n• ".join(details) if details else "")
                    await broadcast(bot, note)

                except Exception as inner_e:
                    logger.warning("Manager error on position: %s", inner_e)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Manager loop error: %s", e)
            await asyncio.sleep(2)

    logger.info("trade_manager: monitor loop stopped")
