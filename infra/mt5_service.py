# =====================================
# infra/mt5_service.py
# =====================================
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any

import MetaTrader5 as mt5

from config import settings

logger = logging.getLogger(__name__)


def sanitize_mt5_comment(comment: str, max_length: int = 31) -> str:
    """
    Sanitize a comment string for MT5 order_send.
    
    MT5 is very strict about comments. Only alphanumeric and basic chars allowed.
    Removes: []():=,<>-_@ and spaces
    
    Args:
        comment: The raw comment string
        max_length: Maximum length (default 31 for MT5)
    
    Returns:
        Sanitized comment string safe for MT5
    """
    if not comment:
        return ""
    
    # Remove ALL special characters that MT5 might reject
    # Keep only: letters, numbers, and maybe dot/slash
    sanitized = (comment
                 .replace(":", "")
                 .replace("[", "")
                 .replace("]", "")
                 .replace("(", "")
                 .replace(")", "")
                 .replace("=", "")
                 .replace(",", "")
                 .replace("<", "")
                 .replace(">", "")
                 .replace("-", "")
                 .replace("_", "")
                 .replace("@", "")
                 .replace(" ", ""))  # Remove spaces too
    
    # Truncate to max length
    return sanitized[:max_length]


@dataclass
class Quote:
    bid: float
    ask: float


class MT5Service:
    def __init__(self):
        self._connected = False

    # ---------- connection / basics ----------
    def connect(self) -> bool:
        """
        Connect to MT5 terminal.
        Returns True if connected successfully, False otherwise.
        """
        if self._connected:
            return True
        try:
            if not mt5.initialize():
                logger.error(f"MT5 initialize failed: {mt5.last_error()}")
                return False
            self._connected = True
            logger.info("MT5 connected successfully")
            return True
        except Exception as e:
            logger.error(f"MT5 connection error: {e}")
            return False

    def ensure_symbol(self, symbol: str) -> None:
        """Ensure symbol is available in MT5, raise RuntimeError if not"""
        try:
            if not symbol:
                raise ValueError("Symbol cannot be empty")
            
            info = mt5.symbol_info(symbol)
            if info is None:
                raise RuntimeError(f"Symbol not found: {symbol}")
            if not info.visible:
                if not mt5.symbol_select(symbol, True):
                    raise RuntimeError(f"Cannot select symbol: {symbol}")
        except RuntimeError:
            raise  # Re-raise RuntimeError as-is
        except Exception as e:
            raise RuntimeError(f"Error ensuring symbol {symbol}: {e}") from e

    def get_quote(self, symbol: str) -> Quote:
        """Get current quote for symbol, raise RuntimeError if unavailable"""
        try:
            if not symbol:
                raise ValueError("Symbol cannot be empty")
            
            t = mt5.symbol_info_tick(symbol)
            if t is None:
                raise RuntimeError(f"No tick for {symbol}")
            
            try:
                bid = float(t.bid)
                ask = float(t.ask)
            except (ValueError, TypeError, AttributeError) as e:
                raise RuntimeError(f"Invalid tick data for {symbol}: {e}")
            
            return Quote(bid, ask)
        except RuntimeError:
            raise  # Re-raise RuntimeError as-is
        except Exception as e:
            raise RuntimeError(f"Error getting quote for {symbol}: {e}") from e

    def account_bal_eq(self) -> Tuple[Optional[float], Optional[float]]:
        ai = mt5.account_info()
        if ai is None:
            return None, None
        return float(ai.balance), float(ai.equity)

    # ---------- symbol meta / maths ----------
    def symbol_meta(self, symbol: str) -> Dict[str, float]:
        info = mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"symbol_meta: no info for {symbol}")
        meta = {
            "digits": int(info.digits),
            "point": float(info.point),
            "stops_level_points": float(getattr(info, "trade_stops_level", 0) or getattr(info, "stops_level", 0) or 0.0),
            "freeze_level_points": float(getattr(info, "trade_freeze_level", 0) or getattr(info, "freeze_level", 0) or 0.0),
            "volume_min": float(info.volume_min or 0.01),
            "volume_max": float(info.volume_max or 100.0),
            "volume_step": float(info.volume_step or 0.01),
            "contract_size": float(
                getattr(info, "trade_contract_size", 0.0)
                or getattr(info, "contract_size", 0.0)
                or 0.0
            ),
            "trade_tick_size": float(getattr(info, "trade_tick_size", 0.0) or 0.0),
            "trade_tick_value": float(getattr(info, "trade_tick_value", 0.0) or 0.0),
        }
        return meta

    @staticmethod
    def _round_price_by_digits(price: float, digits: int) -> float:
        try:
            p = float(price)
            fmt = f"%.{max(0, int(digits))}f"
            return float(fmt % p)
        except Exception:
            return price

    def normalise_lot(self, symbol: str, lot: float) -> float:
        meta = self.symbol_meta(symbol)
        step = meta["volume_step"]
        vmin = meta["volume_min"]
        vmax = meta["volume_max"]
        try:
            lot = float(lot)
        except Exception:
            lot = vmin
        # Round to nearest step
        if step > 0:
            lot = round(lot / step) * step
        # Clamp
        if lot < vmin:
            lot = vmin
        if lot > vmax:
            lot = vmax
        # Avoid negative/zero
        lot = max(vmin, lot)
        # Normalise to step again to avoid float drift
        if step > 0:
            lot = round(lot / step) * step
        return float(lot)

    def _split_lots(self, symbol: str, lot: float) -> List[float]:
        meta = self.symbol_meta(symbol)
        vmax = meta["volume_max"]
        step = meta["volume_step"]
        if lot <= vmax:
            return [self.normalise_lot(symbol, lot)]
        remaining = lot
        chunks: List[float] = []
        while remaining > 0:
            chunk = min(vmax, remaining)
            # step normalise each chunk
            if step > 0:
                chunk = round(chunk / step) * step
            chunk = max(step or 0.01, chunk)
            chunks.append(self.normalise_lot(symbol, chunk))
            remaining = max(0.0, remaining - chunk)
            if len(chunks) >= int(getattr(settings, "SPLIT_MAX_ORDERS", 3)):
                break
        return [c for c in chunks if c > 0]

    def risk_to_lot(
        self, symbol: str, entry: float, sl: float, risk_pct: float
    ) -> float:
        """
        Convert risk % of equity to lot size using MT5's tick maths.

        lot = cash_risk / (ticks * tick_value)

        Notes:
        - On *cent* accounts (e.g., currency='USC'), account equity is in cents,
          while many brokers report tick_value in *USD*. We scale equity by 0.01
          unless settings.RISK_ACCOUNT_SCALE overrides it.
        - Adds an optional hard cap via settings.RISK_LOT_HARD_CAP for safety.
        - Emits debug logs to help diagnose broker meta quirks.
        """
        ai = mt5.account_info()
        bal = float(getattr(ai, "balance", 0.0) or 0.0) if ai else 0.0
        eq = float(getattr(ai, "equity", 0.0) or bal)
        currency = (getattr(ai, "currency", "") or "").upper()

        # Scale equity for cent accounts: USC, EUC, GBC etc.
        default_scale = 0.01 if currency.endswith("C") else 1.0
        equity_scale = float(getattr(settings, "RISK_ACCOUNT_SCALE", default_scale))
        equity = eq * equity_scale

        if equity <= 0:
            return float(getattr(settings, "DEFAULT_LOT_SIZE", 0.01))

        try:
            risk_pct = float(risk_pct)
        except Exception:
            risk_pct = float(getattr(settings, "RISK_DEFAULT_PCT", 1.0))

        cash_risk = max(0.0, equity * (risk_pct / 100.0))

        meta = self.symbol_meta(symbol)
        ttv = float(meta.get("trade_tick_value") or 0.0)
        tts = float(meta.get("trade_tick_size") or 0.0)
        point = float(meta.get("point") or 0.0)
        contract = float(meta.get("contract_size") or 0.0)

        dist = abs(float(entry) - float(sl))
        if dist <= 0:
            return float(getattr(settings, "DEFAULT_LOT_SIZE", 0.01))

        # Preferred path: broker-provided tick maths
        if ttv > 0 and tts > 0:
            ticks = dist / tts
            risk_per_lot = ticks * ttv
        else:
            # Fallback approximation if broker metadata is incomplete
            dollars_per_point = contract if contract > 0 else 1.0
            risk_per_lot = dist / max(point, 1e-9) * dollars_per_point

        if risk_per_lot <= 0:
            return float(getattr(settings, "DEFAULT_LOT_SIZE", 0.01))

        lot = cash_risk / risk_per_lot

        # Safety cap (optional)
        cap = float(getattr(settings, "RISK_LOT_HARD_CAP", 0.0))
        if cap > 0:
            lot = min(lot, cap)

        # Normalise to broker rules
        lot = self.normalise_lot(symbol, lot)

        logger.debug(
            "risk_to_lot: cur=%s equity_raw=%.2f scale=%.4f equity=%.2f risk_pct=%.2f dist=%.5f tts=%.8f ttv=%.6f risk_per_lot=%.6f lot=%.4f",
            currency,
            eq,
            equity_scale,
            equity,
            risk_pct,
            dist,
            tts,
            ttv,
            risk_per_lot,
            lot,
        )
        return max(0.0, float(lot))

    @staticmethod
    def _normalize_price(symbol: str, price: Optional[float]) -> float:
        if price is None:
            return 0.0
        si = mt5.symbol_info(symbol)
        if not si:
            return float(price)
        digits = int(getattr(si, "digits", 5) or 5)
        try:
            return round(float(price), digits)
        except Exception:
            return float(price)

        # --- NEW: pending order sender ---

    def pending_order(
        self,
        symbol: str,
        side: str,
        entry: float,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        lot: Optional[float] = None,
        comment: str = "",
    ) -> dict:
        """
        Place a pending order (limit/stop). 'comment' must be one of:
        {'buy_stop','buy_limit','sell_stop','sell_limit'} to choose type.
        """
        try:
            self.connect()
            self.ensure_symbol(symbol)
        except Exception as e:
            return {
                "ok": False,
                "message": f"connection/symbol error: {e}",
                "details": {},
            }

        mode = (comment or "").lower().strip()
        mapping = {
            "buy_stop": mt5.ORDER_TYPE_BUY_STOP,
            "buy_limit": mt5.ORDER_TYPE_BUY_LIMIT,
            "sell_stop": mt5.ORDER_TYPE_SELL_STOP,
            "sell_limit": mt5.ORDER_TYPE_SELL_LIMIT,
        }
        if mode not in mapping:
            return {
                "ok": False,
                "message": f"invalid pending type: {mode}",
                "details": {},
            }

        # Normalize numbers to broker precision
        entry = self._normalize_price(symbol, entry)
        sl_n = self._normalize_price(symbol, sl) if sl is not None else 0.0
        tp_n = self._normalize_price(symbol, tp) if tp is not None else 0.0
        vol = float(lot or getattr(settings, "DEFAULT_LOT_SIZE", 0.01))

        # Enforce minimum distances (broker stop level)
        meta = self.symbol_meta(symbol)
        point = float(meta.get("point", 0.0) or 0.0)
        stops_points = float(meta.get("stops_level_points", 0.0) or 0.0)
        min_dist = stops_points * point
        try:
            q = self.get_quote(symbol)
            cur = (q.ask + q.bid) / 2.0
        except Exception:
            cur = entry

        # Entry must be sufficiently away from current price
        if min_dist > 0 and abs(entry - cur) < min_dist:
            # Nudge entry to satisfy min distance depending on side/type
            is_buy = side.lower().startswith("b")
            is_limit = mode.endswith("limit")
            if is_buy and is_limit:
                entry = cur - (min_dist * 1.1)
            elif is_buy and not is_limit:  # buy_stop
                entry = cur + (min_dist * 1.1)
            elif (not is_buy) and is_limit:
                entry = cur + (min_dist * 1.1)
            else:  # sell_stop
                entry = cur - (min_dist * 1.1)
            entry = self._normalize_price(symbol, entry)

        # SL/TP relative to entry must also respect min distance
        if sl is not None and min_dist > 0 and abs(entry - sl_n) < min_dist:
            if side.lower().startswith("b"):
                sl_n = entry - (min_dist * 1.1)
            else:
                sl_n = entry + (min_dist * 1.1)
            sl_n = self._normalize_price(symbol, sl_n)
        if tp is not None and min_dist > 0 and abs(entry - tp_n) < min_dist:
            if side.lower().startswith("b"):
                tp_n = entry + (min_dist * 1.1)
            else:
                tp_n = entry - (min_dist * 1.1)
            tp_n = self._normalize_price(symbol, tp_n)

        # Reasonable defaults; adjust if broker rejects
        deviation = int(getattr(settings, "MAX_DEVIATION", 20))
        type_time = mt5.ORDER_TIME_GTC
        type_filling = mt5.ORDER_FILLING_RETURN

        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "type": mapping[mode],
            "volume": vol,
            "price": entry,
            "sl": sl_n,
            "tp": tp_n,
            "deviation": deviation,
            "type_time": type_time,
            "type_filling": type_filling,
            "comment": mode,
        }

        result = mt5.order_send(request)
        ok = bool(result and result.retcode == mt5.TRADE_RETCODE_DONE)

        details = {
            "ticket": getattr(result, "order", None),
            "price_requested": entry,
            "price": entry,  # for consistency with your message renderer
            "sl": sl_n if sl else None,
            "tp": tp_n if tp else None,
            "volume": vol,
            "position": None,  # pending order -> no position yet
            "final_position": None,
        }
        msg = getattr(result, "comment", "") if result else "no result"
        return {"ok": ok, "message": msg, "details": details, "parts": []}

    # ---------- slippage / deviation ----------
    def compute_deviation_points(self, symbol: str, q: Quote) -> int:
        """
        Dynamic deviation in *points* based on current spread:
            deviation = clamp( base + per*spread_points, base .. cap )
        """
        try:
            meta = self.symbol_meta(symbol)
            point = float(meta["point"])
            spread_points = int(abs(q.ask - q.bid) / max(point, 1e-9))
            base = int(getattr(settings, "DEVIATION_POINTS_BASE", 10))
            per = float(getattr(settings, "DEVIATION_POINTS_PER_SPREAD", 0.5))
            cap = int(getattr(settings, "DEVIATION_POINTS_MAX", 50))
            dev = int(min(cap, max(base, base + per * spread_points)))
            return max(0, dev)
        except Exception:
            return int(getattr(settings, "DEFAULT_DEVIATION", 10))

    # ---------- internal helpers: readback / enforce ----------
    def _readback_position(
        self,
        *,
        symbol: str,
        ticket_hint: Optional[int],
        magic: int,
        wait_ms: int = 1200,
    ) -> Optional[object]:
        """
        Try to resolve a position object after a DEAL.
        Priority:
          1) positions_get(ticket=ticket_hint)
          2) most recent position for symbol with matching magic
          3) most recent position for symbol
        Polls briefly because some servers are a bit slow to surface the position.
        """
        deadline = time.time() + (wait_ms / 1000.0)
        while time.time() < deadline:
            try:
                if ticket_hint:
                    pos = mt5.positions_get(ticket=int(ticket_hint))
                    if pos and len(pos) >= 1:
                        return pos[0]
            except Exception:
                pass
            try:
                cur = mt5.positions_get(symbol=symbol) or []
                if cur:
                    # prefer matching magic
                    cur_sorted = sorted(
                        cur, key=lambda p: getattr(p, "time", 0), reverse=True
                    )
                    for p in cur_sorted:
                        if int(getattr(p, "magic", 0)) == int(magic):
                            return p
                    return cur_sorted[0]
            except Exception:
                pass
            time.sleep(0.08)
        return None

    def _enforce_levels_if_needed(
        self,
        *,
        symbol: str,
        pos_ticket: Optional[int],
        sl_send: Optional[float],
        tp_send: Optional[float],
    ) -> Tuple[Optional[float], Optional[float], Optional[int]]:
        """
        Ensure SL/TP exist on the final position. If missing or on wrong side, set them.
        Returns (final_sl, final_tp, final_position_ticket)
        """
        magic = int(getattr(settings, "MT5_MAGIC", 0))
        pos_obj = self._readback_position(
            symbol=symbol, ticket_hint=pos_ticket, magic=magic
        )

        if not pos_obj:
            return None, None, None

        # Extract current values
        cur_sl = float(getattr(pos_obj, "sl", 0.0) or 0.0)
        cur_tp = float(getattr(pos_obj, "tp", 0.0) or 0.0)
        pos_side = int(getattr(pos_obj, "type", 0))  # 0=BUY, 1=SELL
        px_open = float(getattr(pos_obj, "price_open", 0.0) or 0.0)
        ticket = int(getattr(pos_obj, "ticket", 0))

        # Decide desired values
        want_sl = sl_send if sl_send is not None else (cur_sl if cur_sl > 0 else None)
        want_tp = tp_send if tp_send is not None else (cur_tp if cur_tp > 0 else None)

        def _wrong_side(
            side_is_buy: bool, slv: Optional[float], tpv: Optional[float]
        ) -> Tuple[bool, bool]:
            bad_sl = False
            bad_tp = False
            if slv is not None:
                bad_sl = (side_is_buy and slv >= px_open) or (
                    (not side_is_buy) and slv <= px_open
                )
            if tpv is not None:
                bad_tp = (side_is_buy and tpv <= px_open) or (
                    (not side_is_buy) and tpv >= px_open
                )
            return bad_sl, bad_tp

        bad_sl, bad_tp = _wrong_side(pos_side == 0, want_sl, want_tp)

        # If either missing or wrong, try to set
        need_set = False
        if want_sl is not None and (cur_sl <= 0 or bad_sl):
            need_set = True
        if want_tp is not None and (cur_tp <= 0 or bad_tp):
            need_set = True

        if need_set:
            try:
                res_mod = self.modify_position_sl_tp(
                    ticket=ticket, symbol=symbol, sl=want_sl, tp=want_tp
                )
                if not res_mod.get("ok"):
                    logger.error(f"modify_position_sl_tp failed for ticket {ticket}: {res_mod}")
                    # Log detailed error for debugging
                    error_msg = res_mod.get("message", "Unknown error")
                    retcode = res_mod.get("details", {}).get("retcode", "unknown")
                    logger.error(f"  Error details: retcode={retcode}, message={error_msg}")
            except Exception:
                logger.debug("modify_position_sl_tp raised", exc_info=True)

            # Re-read
            try:
                pos2 = mt5.positions_get(ticket=ticket)
                if pos2 and len(pos2) >= 1:
                    pos_obj = pos2[0]
                    cur_sl = float(getattr(pos_obj, "sl", 0.0) or 0.0)
                    cur_tp = float(getattr(pos_obj, "tp", 0.0) or 0.0)
            except Exception:
                pass

        final_sl = cur_sl if cur_sl > 0 else (want_sl if want_sl is not None else None)
        final_tp = cur_tp if cur_tp > 0 else (want_tp if want_tp is not None else None)
        return final_sl, final_tp, ticket

    # ---------- order sending ----------
    def market_order(
        self,
        symbol: str,
        side: str,
        lot: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        comment: str = "",
        risk_pct: Optional[float] = None,
        skip_filters: bool = False,  # Allow bypassing filters if needed
    ) -> dict:
        """
        Send a market order. If risk_pct is provided or lot is None, compute lot via risk %.
        Always normalises lot to broker rules. Splits large sizes if needed.
        
        NEW: Includes professional pre-volatility and correlation filters (can be bypassed with skip_filters=True)

        Enriched return:
          details = {
            ticket, position, price_requested, price_executed,
            sl (requested_ok_side or None), tp (requested_ok_side or None),
            final_sl, final_tp, final_position, volume, retcode, comment
          }
        """
        self.ensure_symbol(symbol)
        q = self.get_quote(symbol)
        meta = self.symbol_meta(symbol)
        digits = int(meta["digits"])
        
        # 🚨 PROFESSIONAL FILTERS - Run before execution
        if not skip_filters:
            try:
                from infra.professional_filters import ProfessionalFilters
                from infra.indicator_bridge import IndicatorBridge
                
                filters = ProfessionalFilters()
                indicator_bridge = IndicatorBridge(None)
                
                # Get M5 data for volatility check
                multi_data = indicator_bridge.get_multi(symbol)
                m5_data = multi_data.get('M5', {}) if multi_data else {}
                # Calculate spread from ask and bid (MT5 Quote object doesn't have spread attribute)
                spread_points = abs(q.ask - q.bid) / meta.get('point', 0.00001) if meta.get('point', 0.00001) > 0 else 0
                features = {
                    'atr': m5_data.get('atr', 10.0),
                    'spread': float(spread_points * meta.get('point', 0.00001))
                }
                
                # Run filters
                filter_results = filters.run_all_filters(
                    symbol=symbol,
                    direction=side.lower(),
                    entry_price=q.ask if str(side).lower().startswith("b") else q.bid,
                    features=features,
                    check_volatility=True,
                    check_correlation=True
                )
                
                # Block/delay if filters fail
                if not filter_results["overall_passed"]:
                    action = filter_results["recommended_action"]
                    warnings = " | ".join(filter_results["warnings"])
                    logger.warning(f"Professional filters {action}: {warnings}")
                    
                    if action == "block":
                        return {
                            "ok": False,
                            "retcode": 10050,  # Custom code for filter rejection
                            "comment": f"Blocked by filters: {warnings}",
                            "ticket": 0,
                            "filter_warnings": filter_results["warnings"]
                        }
                    elif action == "delay":
                        # Log warning but allow (could implement retry logic here)
                        logger.warning(f"Filter warning (allowing): {warnings}")
                
            except Exception as e:
                logger.warning(f"Professional filters error (allowing trade): {e}")

        is_buy = str(side).lower().startswith("b")
        price_req = q.ask if is_buy else q.bid

        # SAFETY: Require SL/TP for all market orders (unless explicitly allowed)
        require_sl_tp = getattr(settings, "REQUIRE_SL_TP_FOR_MARKET_ORDERS", True)
        if require_sl_tp:
            if sl is None or sl == 0:
                return {
                    "ok": False,
                    "message": "Stop loss (SL) is required for market orders. Provide a valid SL price.",
                    "details": {"retcode": 10051}
                }
            if tp is None or tp == 0:
                return {
                    "ok": False,
                    "message": "Take profit (TP) is required for market orders. Provide a valid TP price.",
                    "details": {"retcode": 10052}
                }

        # Compute lot by risk if requested/needed
        if lot is None or risk_pct is not None:
            if sl is None:
                lot = float(getattr(settings, "DEFAULT_LOT_SIZE", 0.01))
            else:
                lot = self.risk_to_lot(
                    symbol,
                    price_req,
                    float(sl),
                    float(risk_pct or getattr(settings, "RISK_DEFAULT_PCT", 1.0)),
                )

        # Normalise lots / splitting
        lots = self._split_lots(symbol, float(lot))

        # Broker min stop distance (include freeze level and spread buffer)
        point = float(meta.get("point", 0.0) or 0.0)
        stops_points = float(meta.get("stops_level_points", 0.0) or 0.0)
        freeze_points = float(meta.get("freeze_level_points", 0.0) or 0.0)
        spread_points = int(abs(q.ask - q.bid) / max(point, 1e-9))
        extra_points = int(getattr(settings, "STOPS_EXTRA_POINTS", 2))
        # If broker reports no stops/freeze, do not add spread buffer
        if (stops_points + freeze_points) <= 0:
            required_points = 0
        else:
            # Some brokers enforce (stops + freeze); add half-spread buffer and a tiny cushion
            required_points = int(max(0, stops_points + freeze_points) + max(0, spread_points // 2) + extra_points)
        min_dist = required_points * point
        logger.debug(
            "stops_calc: symbol=%s point=%.8f stops_pts=%.2f freeze_pts=%.2f spread_pts=%d required_pts=%d min_dist=%.8f",
            symbol, point, stops_points, freeze_points, spread_points, required_points, min_dist
        )

        # CRITICAL FIX: Validate SL/TP sides and distance; adjust if too close
        def _validate_level(level: Optional[float], which: str) -> Optional[float]:
            if level is None:
                return None
            lvl = self._round_price_by_digits(float(level), digits)
            if which == "sl":
                if (is_buy and lvl >= price_req) or (not is_buy and lvl <= price_req):
                    logger.error(f"CRITICAL: Invalid SL (wrong side of price): {lvl} for {side.upper()} @ {price_req}")
                    raise ValueError(f"Invalid SL: {lvl} is on wrong side of entry {price_req} for {side}")
            if which == "tp":
                if (is_buy and lvl <= price_req) or (not is_buy and lvl >= price_req):
                    logger.error(f"CRITICAL: Invalid TP (wrong side of price): {lvl} for {side.upper()} @ {price_req}")
                    raise ValueError(f"Invalid TP: {lvl} is on wrong side of entry {price_req} for {side}")

            # Enforce broker minimum stop distance if available
            if min_dist and min_dist > 0:
                dist = abs(price_req - lvl)
                if dist < min_dist:
                    # Nudge level to satisfy min distance
                    adjust = (min_dist * 1.05)
                    lvl = price_req - adjust if (which == "sl" and is_buy) else (
                          price_req + adjust if (which == "sl" and not is_buy) else (
                          price_req + adjust if (which == "tp" and is_buy) else price_req - adjust))
                    lvl = self._round_price_by_digits(lvl, digits)
            return lvl

        # Store original SL/TP values before validation (needed for post-fill setting)
        original_sl = sl
        original_tp = tp
        original_entry = price_req  # Store requested price as reference for distance calculation
        
        # CRITICAL: If SL or TP are provided but invalid, reject the entire order
        try:
            sl_send = _validate_level(sl, "sl")
            tp_send = _validate_level(tp, "tp")
        except ValueError as e:
            # If SL/TP invalid due to wrong side, drop levels and place market order first,
            # then attempt to set SL/TP after fill using original values (will recalculate based on actual entry)
            logger.warning(f"Invalid SL/TP provided ({e}); placing market order without SL/TP and will try to set after fill using original values.")
            sl_send = None
            tp_send = None
            # Keep original values for post-fill setting (will be recalculated based on actual execution price)

        order_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        deviation = self.compute_deviation_points(symbol, q)
        magic = int(getattr(settings, "MT5_MAGIC", 0))

        results = []
        for chunk in lots:
            vol = self.normalise_lot(symbol, float(chunk))
            
            # MT5 comment field is extremely picky - use simple hardcoded value
            # The comment parameter is used to detect order type (buy_limit, etc)
            # For market orders, just use "market"
            safe_comment = "market"
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": vol,
                "type": order_type,
                "price": price_req,
                "deviation": deviation,
                "magic": magic,
                "type_filling": mt5.ORDER_FILLING_IOC,  # Changed from FOK to IOC for better compatibility
                "comment": safe_comment,
            }
            if sl_send is not None:
                request["sl"] = sl_send
            if tp_send is not None:
                request["tp"] = tp_send

            logger.info(f"Sending order request: {request}")
            res = mt5.order_send(request)
            
            if res is None:
                last_error = mt5.last_error()
                logger.error(f"order_send returned None! MT5 last_error: {last_error}")
                logger.info(f"order_send result: {res}")
                results.append(
                    {"ok": False, "message": "order_send returned None", "details": {}}
                )
                continue

            ok = res.retcode == mt5.TRADE_RETCODE_DONE
            # Executed price is often in res.price; we also confirm from position readback
            price_exec = float(getattr(res, "price", 0.0) or price_req)
            pos_id_hint = getattr(res, "position", None)
            order_ticket = getattr(res, "order", None)

            # Enforce SL/TP post-fill & read final values
            final_sl, final_tp, final_pos_ticket = (None, None, None)
            try:
                # If SL/TP were invalid and set to None, recalculate based on actual execution price
                sl_to_enforce = sl_send
                tp_to_enforce = tp_send
                
                if sl_send is None and original_sl is not None:
                    # Recalculate SL based on actual execution price
                    # Calculate distance from original entry to original SL, then apply to actual entry
                    if not is_buy:  # SELL - SL must be above entry
                        # Original: entry=original_entry, SL=original_sl (should be above)
                        # If original_sl < original_entry, it was wrong - calculate as if it should be above
                        if original_sl > original_entry:
                            # Original SL was above entry (correct), preserve distance
                            sl_distance = original_sl - original_entry
                        else:
                            # Original SL was below entry (wrong), calculate distance anyway
                            sl_distance = abs(original_sl - original_entry)
                        # For SELL, SL should be above entry, so add distance
                        sl_to_enforce = price_exec + sl_distance
                        sl_to_enforce = self._round_price_by_digits(sl_to_enforce, digits)
                        logger.info(f"Recalculated SL for SELL: {original_sl} -> {sl_to_enforce} (entry: {price_exec}, distance: {sl_distance:.5f})")
                    else:  # BUY - SL must be below entry
                        # Original: entry=original_entry, SL=original_sl (should be below)
                        if original_sl < original_entry:
                            # Original SL was below entry (correct), preserve distance
                            sl_distance = original_entry - original_sl
                        else:
                            # Original SL was above entry (wrong), calculate distance anyway
                            sl_distance = abs(original_sl - original_entry)
                        # For BUY, SL should be below entry, so subtract distance
                        sl_to_enforce = price_exec - sl_distance
                        sl_to_enforce = self._round_price_by_digits(sl_to_enforce, digits)
                        logger.info(f"Recalculated SL for BUY: {original_sl} -> {sl_to_enforce} (entry: {price_exec}, distance: {sl_distance:.5f})")
                
                if tp_send is None and original_tp is not None:
                    # Recalculate TP based on actual execution price
                    if not is_buy:  # SELL - TP must be below entry
                        # Original: entry=original_entry, TP=original_tp (should be below)
                        if original_tp < original_entry:
                            # Original TP was below entry (correct), preserve distance
                            tp_distance = original_entry - original_tp
                        else:
                            # Original TP was above entry (wrong), calculate distance anyway
                            tp_distance = abs(original_tp - original_entry)
                        # For SELL, TP should be below entry, so subtract distance
                        tp_to_enforce = price_exec - tp_distance
                        tp_to_enforce = self._round_price_by_digits(tp_to_enforce, digits)
                        logger.info(f"Recalculated TP for SELL: {original_tp} -> {tp_to_enforce} (entry: {price_exec}, distance: {tp_distance:.5f})")
                    else:  # BUY - TP must be above entry
                        # Original: entry=original_entry, TP=original_tp (should be above)
                        if original_tp > original_entry:
                            # Original TP was above entry (correct), preserve distance
                            tp_distance = original_tp - original_entry
                        else:
                            # Original TP was below entry (wrong), calculate distance anyway
                            tp_distance = abs(original_entry - original_tp)
                        # For BUY, TP should be above entry, so add distance
                        tp_to_enforce = price_exec + tp_distance
                        tp_to_enforce = self._round_price_by_digits(tp_to_enforce, digits)
                        logger.info(f"Recalculated TP for BUY: {original_tp} -> {tp_to_enforce} (entry: {price_exec}, distance: {tp_distance:.5f})")
                
                final_sl, final_tp, final_pos_ticket = self._enforce_levels_if_needed(
                    symbol=symbol,
                    pos_ticket=int(pos_id_hint) if pos_id_hint else None,
                    sl_send=sl_to_enforce,
                    tp_send=tp_to_enforce,
                )
                # If we resolved a position, use its open price as the best executed price
                try:
                    if final_pos_ticket:
                        pos_obj = mt5.positions_get(ticket=int(final_pos_ticket))
                        if pos_obj and len(pos_obj) >= 1:
                            price_exec = float(
                                getattr(pos_obj[0], "price_open", price_exec)
                                or price_exec
                            )
                            # Verify SL/TP were actually set on the position
                            pos_sl = float(getattr(pos_obj[0], "sl", 0.0) or 0.0)
                            pos_tp = float(getattr(pos_obj[0], "tp", 0.0) or 0.0)
                            
                            # Update final_sl and final_tp with actual position values
                            if pos_sl > 0:
                                final_sl = pos_sl
                            if pos_tp > 0:
                                final_tp = pos_tp
                            
                            # Log warning if SL/TP are still missing
                            if (sl_to_enforce is not None and pos_sl == 0) or (tp_to_enforce is not None and pos_tp == 0):
                                logger.warning(
                                    f"⚠️ SL/TP verification failed for ticket {final_pos_ticket}: "
                                    f"Attempted SL={sl_to_enforce}, Actual SL={pos_sl}, "
                                    f"Attempted TP={tp_to_enforce}, Actual TP={pos_tp}"
                                )
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"post-fill enforcement failed: {e}", exc_info=True)
                # Log what we tried to set
                if 'sl_to_enforce' in locals() and 'tp_to_enforce' in locals():
                    if sl_to_enforce is not None or tp_to_enforce is not None:
                        logger.error(f"  Attempted to set SL={sl_to_enforce}, TP={tp_to_enforce} for ticket {order_ticket}")

            details = {
                "ticket": order_ticket,
                "position": getattr(res, "position", None),
                "final_position": final_pos_ticket,
                "price_requested": price_req,
                "price_executed": price_exec,
                "sl": sl_send,
                "tp": tp_send,
                "final_sl": final_sl,
                "final_tp": final_tp,
                "volume": vol,
                "retcode": res.retcode,
                "comment": getattr(res, "comment", ""),
            }
            results.append(
                {"ok": ok, "message": getattr(res, "comment", ""), "details": details}
            )

        any_ok = any(r["ok"] for r in results)
        msg = "; ".join([r["message"] for r in results])
        last_details = results[-1]["details"] if results else {}
        return {"ok": any_ok, "message": msg, "details": last_details, "parts": results}

    def open_order(
        self,
        symbol: str,
        side: str,
        entry: Optional[float] = None,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
        lot: Optional[float] = None,
        risk_pct: Optional[float] = None,
        comment: str = "",
    ) -> dict:
        """
        Unified entry:
        - Market by default (backwards compatible with existing callers)
        - If comment ∈ {buy_stop,buy_limit,sell_stop,sell_limit}, send a pending order at 'entry'
        """
        mode = (comment or "").lower().strip()
        if mode in {"buy_stop", "buy_limit", "sell_stop", "sell_limit"}:
            if entry is None:
                return {
                    "ok": False,
                    "message": "entry required for pending order",
                    "details": {},
                }
            return self.pending_order(
                symbol=symbol,
                side=side,
                entry=float(entry),
                sl=sl,
                tp=tp,
                lot=lot,
                comment=mode,
            )

        # Fallback: original behavior (market order)
        return self.market_order(
            symbol=symbol,
            side=side,
            lot=lot,
            sl=sl,
            tp=tp,
            comment=comment,
            risk_pct=risk_pct,
        )

    # ---------- NEW: positions helpers ----------
    def list_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Return a list of open positions as plain dicts.
        """
        if symbol:
            cur = mt5.positions_get(symbol=symbol)
        else:
            cur = mt5.positions_get()
        out: List[Dict] = []
        if not cur:
            return out
        for p in cur:
            out.append(
                {
                    "ticket": int(getattr(p, "ticket", 0)),
                    "symbol": str(getattr(p, "symbol", "")),
                    "type": int(getattr(p, "type", 0)),  # 0=BUY,1=SELL
                    "volume": float(getattr(p, "volume", 0.0)),
                    "price_open": float(getattr(p, "price_open", 0.0)),
                    "price_current": float(getattr(p, "price_current", 0.0)),
                    "sl": (
                        float(getattr(p, "sl", 0.0)) if getattr(p, "sl", 0.0) else 0.0
                    ),
                    "tp": (
                        float(getattr(p, "tp", 0.0)) if getattr(p, "tp", 0.0) else 0.0
                    ),
                    "profit": float(getattr(p, "profit", 0.0)),
                    "swap": float(getattr(p, "swap", 0.0)),
                    "comment": str(getattr(p, "comment", "")),
                    "magic": int(getattr(p, "magic", 0)),
                    "time": int(getattr(p, "time", 0)),
                }
            )
        return out
    
    def get_positions(self, symbol: Optional[str] = None):
        """
        Get open positions as raw MT5 objects (for TradeMonitor compatibility).
        Returns list of position objects with attributes like .ticket, .symbol, .price_current, etc.
        """
        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()
        return list(positions) if positions else []

    def modify_position_sl_tp(
        self,
        ticket: int,
        *,
        symbol: str,
        sl: Optional[float] = None,
        tp: Optional[float] = None,
    ) -> dict:
        """
        Modify SL/TP of an existing position.
        """
        self.ensure_symbol(symbol)
        req = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": int(ticket),
            "symbol": symbol,
        }
        if sl is not None:
            req["sl"] = float(sl)
        if tp is not None:
            req["tp"] = float(tp)
        res = mt5.order_send(req)
        ok = res and res.retcode in (mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED)
        return {
            "ok": bool(ok),
            "retcode": getattr(res, "retcode", None),
            "comment": getattr(res, "comment", ""),
        }

    def get_bars(self, symbol: str, timeframe: str, count: int) -> Optional[Any]:
        """
        Get historical bars for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., 'BTCUSDc')
            timeframe: Timeframe ('M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1')
            count: Number of bars to retrieve
            
        Returns:
            pandas.DataFrame with OHLCV data or None if failed
        """
        try:
            import pandas as pd
            
            # Map timeframe string to MT5 constant
            tf_map = {
                'M1': mt5.TIMEFRAME_M1,
                'M5': mt5.TIMEFRAME_M5,
                'M15': mt5.TIMEFRAME_M15,
                'M30': mt5.TIMEFRAME_M30,
                'H1': mt5.TIMEFRAME_H1,
                'H4': mt5.TIMEFRAME_H4,
                'D1': mt5.TIMEFRAME_D1,
                'W1': mt5.TIMEFRAME_W1,
                'MN1': mt5.TIMEFRAME_MN1
            }
            
            if timeframe not in tf_map:
                logger.error(f"Unsupported timeframe: {timeframe}")
                return None
            
            # Ensure symbol is available
            self.ensure_symbol(symbol)
            
            # Get bars from MT5
            bars = mt5.copy_rates_from_pos(symbol, tf_map[timeframe], 0, count)
            
            if bars is None or len(bars) == 0:
                logger.warning(f"No bars returned for {symbol} {timeframe}")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(bars)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Rename columns to match expected format
            # MT5 returns 'tick_volume' but we need to ensure it exists
            if 'tick_volume' in df.columns:
                df = df.rename(columns={'tick_volume': 'volume'})
            elif 'real_volume' in df.columns:
                df = df.rename(columns={'real_volume': 'volume'})
            else:
                # If no volume column exists, create one with default value
                df['volume'] = 0
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting bars for {symbol} {timeframe}: {e}")
            return None

    def close_position_partial(
        self, 
        ticket: int, 
        volume: float, 
        *, 
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        deviation: Optional[int] = None,
        filling_mode: Optional[int] = None,
        comment: str = "partial_close"
    ) -> Tuple[bool, str]:
        """
        Close part of a position by sending an opposite market deal.
        
        Args:
            ticket: Position ticket number
            volume: Volume to close
            symbol: Symbol (optional, will fetch from position if not provided)
            side: Side ("buy" or "sell", optional, will fetch from position if not provided)
            deviation: Custom deviation in points (optional, will compute if not provided)
            filling_mode: Order filling mode (default: IOC for reliability)
            comment: Order comment
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        # Get position info if symbol/side not provided
        if symbol is None or side is None:
            pos = mt5.positions_get(ticket=ticket)
            if not pos or len(pos) == 0:
                return False, f"Position {ticket} not found"
            position = pos[0]
            symbol = symbol or position.symbol
            if side is None:
                side = "buy" if position.type == mt5.ORDER_TYPE_BUY else "sell"
        
        self.ensure_symbol(symbol)
        q = self.get_quote(symbol)
        is_buy = side.lower().startswith("b")
        
        # To close a BUY, send SELL at Bid; to close a SELL, send BUY at Ask
        order_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
        price = q.bid if is_buy else q.ask
        
        # Use custom deviation or compute default
        if deviation is None:
            deviation = self.compute_deviation_points(symbol, q)
        
        # Use IOC (Immediate or Cancel) by default for reliability
        if filling_mode is None:
            filling_mode = mt5.ORDER_FILLING_IOC
        
        vol = self.normalise_lot(symbol, float(volume))
        
        # Sanitize comment for MT5 (remove special chars, max 31 chars)
        # NOTE: Some brokers reject comments on closing orders even if valid
        # Try with empty comment first, fall back to sanitized if that fails
        safe_comment = sanitize_mt5_comment(comment) if comment else ""
        
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "position": int(ticket),
            "volume": vol,
            "type": order_type,
            "price": price,
            "deviation": deviation,
            "magic": int(getattr(settings, "MT5_MAGIC", 0)),
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
            # "comment": safe_comment,  # Disabled - some brokers reject ANY comment on close
        }
        
        logger.info(f"Closing position {ticket}: {vol} lots of {symbol} at {price} "
                   f"(deviation={deviation}, filling={filling_mode})")
        logger.debug(f"Close request: {req}")
        
        res = mt5.order_send(req)
        
        if res is None:
            last_error = mt5.last_error()
            logger.error(f"order_send returned None! MT5 last_error: {last_error}")
            logger.error(f"Request was: {req}")
            return False, f"MT5 returned None (last_error: {last_error})"
        
        ok = res and res.retcode == mt5.TRADE_RETCODE_DONE
        
        if ok:
            msg = f"Closed {vol} lots at {price}"
        else:
            retcode = getattr(res, "retcode", None)
            comment_text = getattr(res, "comment", "")
            msg = f"Failed: retcode={retcode}, comment={comment_text}"
        
        return bool(ok), msg
