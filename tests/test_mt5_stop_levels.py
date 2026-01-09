import MetaTrader5 as mt5
from typing import Tuple

# Simple ASCII-only tests for broker stop/freeze levels.
# Run: python -m pytest -q tests/test_mt5_stop_levels.py -k test_print_levels --maxfail=1


def _ensure_connected() -> None:
	if not mt5.initialize():
		raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")


def _get_levels(symbol: str) -> Tuple[int, int, float, int]:
	info = mt5.symbol_info(symbol)
	if info is None:
		raise RuntimeError(f"No symbol info for {symbol}")
	stops = int(getattr(info, "trade_stops_level", 0) or getattr(info, "stops_level", 0) or 0)
	freeze = int(getattr(info, "trade_freeze_level", 0) or getattr(info, "freeze_level", 0) or 0)
	point = float(getattr(info, "point", 0.0) or 0.0)
	digits = int(getattr(info, "digits", 5) or 5)
	return stops, freeze, point, digits


def _mid(symbol: str) -> float:
	t = mt5.symbol_info_tick(symbol)
	if t is None:
		raise RuntimeError("No tick")
	return float((t.ask + t.bid) / 2.0)


def test_print_levels():
	"""Print stop/freeze levels for quick inspection (does not assert)."""
	_ensure_connected()
	symbol = "EURUSDc"  # change if needed
	# Try alternative common broker suffix if unavailable
	info = mt5.symbol_info(symbol) or mt5.symbol_info("EURUSD")
	if info is None:
		raise RuntimeError("EURUSD/EURUSDc not available")
	symbol = info.name
	stops, freeze, point, digits = _get_levels(symbol)
	mid = _mid(symbol)
	print(f"Symbol={symbol} stops={stops} freeze={freeze} point={point} digits={digits} mid={mid}")


def test_validate_distance_rule():
	"""Check that a sample SL/TP distance satisfies broker rules with buffer."""
	_ensure_connected()
	symbol = "EURUSDc"
	info = mt5.symbol_info(symbol) or mt5.symbol_info("EURUSD")
	if info is None:
		raise RuntimeError("EURUSD/EURUSDc not available")
	symbol = info.name
	stops, freeze, point, digits = _get_levels(symbol)
	t = mt5.symbol_info_tick(symbol)
	assert t is not None
	spread_points = int(abs(t.ask - t.bid) / max(point, 1e-9))
	required_points = int(max(0, stops + freeze) + max(0, spread_points // 2) + 2)
	min_dist = required_points * point
	# Assume BUY side
	price = float(t.ask)
	# Propose SL/TP with exactly the minimum distance plus small epsilon, rounded to digits
	sl = round(price - (min_dist * 1.05), digits)
	tp = round(price + (min_dist * 1.05), digits)
	assert (price - sl) >= min_dist * 0.99
	assert (tp - price) >= min_dist * 0.99
