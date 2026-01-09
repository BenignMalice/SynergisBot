"""
Download historical candles from MetaTrader 5 and write to CSV.

Example (PowerShell):
  python scripts\download_mt5_history.py --symbol BTCUSDc --year 2025 --timeframes M5 M15
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

import MetaTrader5 as mt5


TF_MAP: Dict[str, int] = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}


def _month_ranges_utc(year: int) -> Iterable[Tuple[int, datetime, datetime]]:
    for month in range(1, 13):
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        yield month, start, end


def _ensure_mt5_symbol(symbol: str) -> None:
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"MT5 symbol not found: {symbol}")
    if not info.visible:
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"MT5 cannot select symbol: {symbol}")


def _utc_iso(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class DownloadResult:
    bars_written: int = 0
    months_with_data: int = 0
    months_empty: int = 0


def download_to_csv(
    *,
    symbol: str,
    timeframe: str,
    year: int,
    out_path: str,
) -> DownloadResult:
    tf_key = timeframe.upper().strip()
    if tf_key not in TF_MAP:
        raise ValueError(f"Unsupported timeframe: {timeframe}. Supported: {sorted(TF_MAP.keys())}")

    tf_enum = TF_MAP[tf_key]
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    # Overwrite by default (deterministic export)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "time_utc",
                "time_epoch",
                "open",
                "high",
                "low",
                "close",
                "tick_volume",
                "spread",
                "real_volume",
            ]
        )

        result = DownloadResult()

        def _field(row, name: str, default):
            """
            MT5 returns numpy structured rows (numpy.void). These support row["field"]
            but do not support dict methods like .get().
            """
            try:
                names = getattr(getattr(row, "dtype", None), "names", None) or ()
                if name in names:
                    return row[name]
            except Exception:
                pass
            return default

        for month, start, end in _month_ranges_utc(year):
            # Treat end as exclusive to avoid any boundary duplication across months.
            end_inclusive = end - timedelta(seconds=1)

            rates = mt5.copy_rates_range(symbol, tf_enum, start, end_inclusive)
            if rates is None or len(rates) == 0:
                print(f"[{symbol} {tf_key}] {year}-{month:02d}: no data")
                result.months_empty += 1
                continue

            # Ensure deterministic ordering
            try:
                rates_sorted = sorted(rates, key=lambda r: int(r["time"]))
            except Exception:
                rates_sorted = rates

            for r in rates_sorted:
                t = int(r["time"])
                w.writerow(
                    [
                        _utc_iso(t),
                        t,
                        float(r["open"]),
                        float(r["high"]),
                        float(r["low"]),
                        float(r["close"]),
                        int(_field(r, "tick_volume", 0) or 0),
                        int(_field(r, "spread", 0) or 0),
                        int(_field(r, "real_volume", 0) or 0),
                    ]
                )

            bars = int(len(rates))
            result.bars_written += bars
            result.months_with_data += 1
            print(f"[{symbol} {tf_key}] {year}-{month:02d}: wrote {bars} bars")

    return result


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Download MT5 historical candles to CSV (chunked by month).")
    p.add_argument("--symbol", default="BTCUSDc", help="MT5 symbol (default: BTCUSDc)")
    p.add_argument("--year", type=int, default=2025, help="Year to download (default: 2025)")
    p.add_argument(
        "--timeframes",
        nargs="+",
        default=["M5", "M15"],
        help="Timeframes to download (default: M5 M15)",
    )
    p.add_argument(
        "--outdir",
        default=os.path.join("data", "mt5_history"),
        help="Output directory (default: data\\mt5_history)",
    )

    args = p.parse_args(argv)

    symbol = str(args.symbol).strip()
    year = int(args.year)
    timeframes = [str(tf).upper().strip() for tf in (args.timeframes or [])]
    outdir = str(args.outdir).strip()

    if not symbol:
        print("ERROR: --symbol cannot be empty", file=sys.stderr)
        return 2
    if year < 1970 or year > 2100:
        print(f"ERROR: --year looks invalid: {year}", file=sys.stderr)
        return 2
    if not timeframes:
        print("ERROR: --timeframes cannot be empty", file=sys.stderr)
        return 2

    print("Initializing MT5...")
    if not mt5.initialize():
        print(f"ERROR: mt5.initialize() failed: {mt5.last_error()}", file=sys.stderr)
        return 1

    try:
        _ensure_mt5_symbol(symbol)

        total_bars = 0
        for tf in timeframes:
            out_path = os.path.join(outdir, f"{symbol}_{tf.upper()}_{year}.csv")
            print(f"\nDownloading {symbol} {tf.upper()} for {year} -> {out_path}")
            res = download_to_csv(symbol=symbol, timeframe=tf, year=year, out_path=out_path)
            total_bars += res.bars_written
            print(
                f"Done {symbol} {tf.upper()} {year}: bars={res.bars_written}, months_with_data={res.months_with_data}, months_empty={res.months_empty}"
            )

        print(f"\nAll done. Total bars written: {total_bars}")
        return 0
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())


