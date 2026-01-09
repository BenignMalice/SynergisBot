"""
Check actual entry price from MT5 for a trade plan
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import MetaTrader5 as mt5
from datetime import datetime, timezone

def check_mt5_entry_price(ticket: int, symbol: str = None, from_date: datetime = None):
    """Check actual entry price from MT5 using ticket number"""
    
    if not mt5.initialize():
        print(f"[ERROR] MT5 initialization failed: {mt5.last_error()}")
        return None
    
    try:
        # First try to get position (if still open)
        positions = mt5.positions_get(ticket=ticket)
        if positions:
            pos = positions[0]
            return {
                'entry_price': pos.price_open,
                'entry_time': datetime.fromtimestamp(pos.time, tz=timezone.utc).isoformat(),
                'volume': pos.volume,
                'symbol': pos.symbol,
                'direction': 'BUY' if pos.type == mt5.ORDER_TYPE_BUY else 'SELL',
                'source': 'position'
            }
        
        # If position closed, get from history
        # Try getting deals by date range if from_date provided
        if from_date:
            deals = mt5.history_deals_get(from_date=from_date, group="*")
        else:
            # Try last 7 days
            from_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            from_date = from_date.replace(day=from_date.day - 7)
            deals = mt5.history_deals_get(from_date=from_date, group="*")
        
        if not deals:
            print(f"[ERROR] No deals found in history")
            return None
        
        # Find deal with matching position_id (ticket)
        entry_deal = None
        for deal in deals:
            if deal.position_id == ticket and deal.entry == mt5.DEAL_ENTRY_IN:
                entry_deal = deal
                break
        
        if not entry_deal:
            # Try any deal with matching position_id
            for deal in deals:
                if deal.position_id == ticket:
                    entry_deal = deal
                    break
        
        if not entry_deal:
            print(f"[WARNING] No entry deal found for ticket {ticket}")
            return None
        
        # Get entry details
        entry_time = datetime.fromtimestamp(entry_deal.time, tz=timezone.utc)
        
        return {
            'entry_price': entry_deal.price,
            'entry_time': entry_time.isoformat(),
            'volume': entry_deal.volume,
            'symbol': entry_deal.symbol,
            'direction': 'BUY' if entry_deal.type == mt5.DEAL_TYPE_BUY else 'SELL',
            'commission': entry_deal.commission,
            'swap': entry_deal.swap,
            'profit': entry_deal.profit,
            'source': 'deal'
        }
    
    finally:
        mt5.shutdown()


def compare_entry_prices(plan_id: str, ticket: int, planned_entry: float, executed_at: str = None, symbol: str = None):
    """Compare planned vs actual entry price"""
    
    print("=" * 80)
    print(f"ENTRY PRICE VERIFICATION: {plan_id}")
    print("=" * 80)
    print()
    
    print("[PLANNED ENTRY]")
    print(f"  Entry Price: ${planned_entry:.2f}")
    print()
    
    print("[CHECKING MT5...]")
    from_date = None
    if executed_at:
        try:
            from_date = datetime.fromisoformat(executed_at.replace('Z', '+00:00'))
            # Start from 1 day before execution
            from_date = from_date.replace(day=from_date.day - 1)
        except:
            pass
    
    actual = check_mt5_entry_price(ticket, symbol=symbol, from_date=from_date)
    
    if not actual:
        print("[ERROR] Could not retrieve actual entry price from MT5")
        return
    
    print("[ACTUAL ENTRY FROM MT5]")
    print(f"  Entry Price: ${actual['entry_price']:.2f}")
    print(f"  Entry Time: {actual['entry_time']}")
    print(f"  Symbol: {actual['symbol']}")
    print(f"  Direction: {actual['direction']}")
    print(f"  Volume: {actual['volume']:.2f} lots")
    if 'commission' in actual:
        print(f"  Commission: ${actual['commission']:.2f}")
    if 'swap' in actual:
        print(f"  Swap: ${actual['swap']:.2f}")
    print()
    
    # Calculate slippage
    price_diff = actual['entry_price'] - planned_entry
    price_diff_pct = (price_diff / planned_entry) * 100 if planned_entry > 0 else 0
    
    print("[SLIPPAGE ANALYSIS]")
    if abs(price_diff) < 0.01:
        print(f"  [OK] No slippage - exact match")
    elif price_diff > 0:
        if actual['direction'] == 'BUY':
            print(f"  [SLIPPAGE] Paid ${price_diff:.2f} more (worse fill)")
            print(f"            {price_diff_pct:+.4f}% above planned entry")
        else:  # SELL
            print(f"  [SLIPPAGE] Got ${price_diff:.2f} less (worse fill)")
            print(f"            {price_diff_pct:+.4f}% below planned entry")
    else:  # price_diff < 0
        if actual['direction'] == 'BUY':
            print(f"  [BETTER FILL] Paid ${abs(price_diff):.2f} less (better fill)")
            print(f"               {price_diff_pct:+.4f}% below planned entry")
        else:  # SELL
            print(f"  [BETTER FILL] Got ${abs(price_diff):.2f} more (better fill)")
            print(f"               {price_diff_pct:+.4f}% above planned entry")
    print()
    
    # User reported entry
    user_reported = 4460.0
    print("[USER REPORTED ENTRY]")
    print(f"  Entry Price: ${user_reported:.2f}")
    print()
    
    # Compare user reported vs MT5
    user_diff = user_reported - actual['entry_price']
    user_diff_pct = (user_diff / actual['entry_price']) * 100 if actual['entry_price'] > 0 else 0
    
    print("[USER REPORTED vs MT5 ACTUAL]")
    if abs(user_diff) < 0.01:
        print(f"  [MATCH] User reported entry matches MT5 actual entry")
    else:
        print(f"  [DIFFERENCE] User reported: ${user_reported:.2f}")
        print(f"               MT5 actual: ${actual['entry_price']:.2f}")
        print(f"               Difference: ${user_diff:.2f} ({user_diff_pct:+.4f}%)")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Planned Entry: ${planned_entry:.2f}")
    print(f"  MT5 Actual Entry: ${actual['entry_price']:.2f}")
    print(f"  User Reported Entry: ${user_reported:.2f}")
    print(f"  Planned vs Actual Slippage: ${price_diff:+.2f} ({price_diff_pct:+.4f}%)")
    print(f"  User vs Actual Difference: ${user_diff:+.2f} ({user_diff_pct:+.4f}%)")
    print()


if __name__ == "__main__":
    # For plan chatgpt_b3bebd76
    plan_id = "chatgpt_b3bebd76"
    ticket = 187646640
    planned_entry = 4452.00
    executed_at = "2026-01-07T20:22:43.543414+00:00"
    symbol = "XAUUSDc"
    
    compare_entry_prices(plan_id, ticket, planned_entry, executed_at=executed_at, symbol=symbol)
