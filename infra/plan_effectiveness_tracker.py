"""
Plan Effectiveness Tracker
Tracks and reports on auto-execution plan performance by linking plan_ids to MT5 trade outcomes.
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)


@dataclass
class PlanOutcome:
    """Outcome of an executed plan"""
    plan_id: str
    symbol: str
    direction: str
    strategy_type: Optional[str]
    ticket: int
    entry_price: float
    planned_sl: float
    planned_tp: float
    actual_entry: float
    actual_exit: Optional[float]
    profit: float
    profit_pips: float
    duration_minutes: int
    outcome: str  # 'win', 'loss', 'breakeven', 'open'
    executed_at: str
    closed_at: Optional[str]


class PlanEffectivenessTracker:
    """Tracks effectiveness of auto-execution plans"""
    
    def __init__(self, db_path: str = "data/auto_execution.db"):
        self.db_path = db_path
        self.mt5_connected = False
    
    def _connect_mt5(self) -> bool:
        """Ensure MT5 is connected"""
        if not self.mt5_connected:
            if not mt5.initialize():
                logger.error("Failed to initialize MT5")
                return False
            self.mt5_connected = True
        return True
    
    def _get_executed_plans(self, days_back: int = 30) -> List[Dict]:
        """Get executed plans from database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        
        c.execute("""
            SELECT plan_id, symbol, direction, entry_price, stop_loss, take_profit, 
                   conditions, executed_at, ticket
            FROM trade_plans 
            WHERE status = 'executed' AND ticket IS NOT NULL AND executed_at > ?
            ORDER BY executed_at DESC
        """, (cutoff,))
        
        plans = []
        for row in c.fetchall():
            conditions = json.loads(row[6]) if row[6] else {}
            plans.append({
                'plan_id': row[0],
                'symbol': row[1],
                'direction': row[2],
                'entry_price': row[3],
                'stop_loss': row[4],
                'take_profit': row[5],
                'strategy_type': conditions.get('strategy_type'),
                'executed_at': row[7],
                'ticket': row[8]
            })
        
        conn.close()
        return plans
    
    def _get_mt5_trade_outcome(self, ticket: int, executed_at: Optional[str] = None) -> Optional[Dict]:
        """
        Get trade outcome from MT5 history
        
        Args:
            ticket: Position ticket (not deal ticket)
            executed_at: Optional ISO timestamp of when trade was executed (for date range optimization)
        """
        if not self._connect_mt5():
            logger.warning(f"MT5 not connected - cannot query outcome for ticket {ticket}")
            return None
        
        # Check open positions first
        positions = mt5.positions_get(ticket=ticket)
        if positions and len(positions) > 0:
            pos = positions[0]
            return {
                'status': 'open',
                'entry_price': pos.price_open,
                'current_price': pos.price_current,
                'profit': pos.profit,
                'open_time': datetime.fromtimestamp(pos.time),
                'close_time': None
            }
        
        # Check history - search by position_id (ticket is a position ticket, not deal ticket)
        # Use executed_at to optimize date range, or fallback to reasonable range
        if executed_at:
            try:
                from_date = datetime.fromisoformat(executed_at.replace('Z', '+00:00'))
                # Subtract 1 day to be safe (in case of timezone issues)
                from_date = from_date - timedelta(days=1)
            except:
                from_date = datetime(2024, 1, 1)
        else:
            from_date = datetime(2024, 1, 1)  # Start from beginning of 2024
        
        to_date = datetime.now() + timedelta(days=1)
        
        try:
            all_deals = mt5.history_deals_get(from_date, to_date, group="*")
        except Exception as e:
            logger.error(f"Error querying MT5 history deals: {e}")
            return None
        
        if all_deals:
            # Filter deals by position_id (the ticket we have is a position ticket)
            deals = [d for d in all_deals if d.position_id == ticket]
            
            # If no matches by position_id, try by order (some brokers use order as position identifier)
            if not deals:
                deals = [d for d in all_deals if d.order == ticket]
        else:
            deals = []
        
        if not deals or len(deals) == 0:
            logger.debug(f"No deals found in MT5 history for ticket {ticket} (position_id search from {from_date.date()} to {to_date.date()})")
            return None
        
        # Find entry and exit deals
        entry_deal = None
        exit_deal = None
        total_profit = 0
        
        for deal in deals:
            if deal.entry == mt5.DEAL_ENTRY_IN:
                entry_deal = deal
            elif deal.entry == mt5.DEAL_ENTRY_OUT:
                exit_deal = deal
            total_profit += deal.profit
        
        if entry_deal:
            result = {
                'status': 'closed' if exit_deal else 'open',
                'entry_price': entry_deal.price,
                'profit': total_profit,
                'open_time': datetime.fromtimestamp(entry_deal.time)
            }
            if exit_deal:
                result['exit_price'] = exit_deal.price
                result['close_time'] = datetime.fromtimestamp(exit_deal.time)
            return result
        
        return None
    
    def _calculate_pips(self, symbol: str, price_diff: float) -> float:
        """Calculate pips from price difference"""
        # JPY pairs have 2 decimal places, others have 4-5
        if 'JPY' in symbol:
            return price_diff * 100
        elif 'XAU' in symbol or 'GOLD' in symbol:
            return price_diff * 10  # Gold in 0.1 increments
        elif 'BTC' in symbol:
            return price_diff  # BTC in dollars
        else:
            return price_diff * 10000
    
    def get_plan_outcomes(self, days_back: int = 30) -> List[PlanOutcome]:
        """Get outcomes for all executed plans"""
        plans = self._get_executed_plans(days_back)
        outcomes = []
        
        for plan in plans:
            mt5_outcome = self._get_mt5_trade_outcome(plan['ticket'])
            
            if mt5_outcome:
                profit = mt5_outcome.get('profit', 0)
                
                # Determine outcome
                if mt5_outcome['status'] == 'open':
                    outcome_str = 'open'
                elif profit > 0.5:
                    outcome_str = 'win'
                elif profit < -0.5:
                    outcome_str = 'loss'
                else:
                    outcome_str = 'breakeven'
                
                # Calculate duration
                open_time = mt5_outcome.get('open_time')
                close_time = mt5_outcome.get('close_time')
                if open_time and close_time:
                    duration = int((close_time - open_time).total_seconds() / 60)
                else:
                    duration = 0
                
                # Calculate pips
                entry = mt5_outcome.get('entry_price', plan['entry_price'])
                exit_price = mt5_outcome.get('exit_price')
                if exit_price and entry:
                    price_diff = exit_price - entry
                    if plan['direction'].upper() == 'SELL':
                        price_diff = -price_diff
                    pips = self._calculate_pips(plan['symbol'], price_diff)
                else:
                    pips = 0
                
                outcomes.append(PlanOutcome(
                    plan_id=plan['plan_id'],
                    symbol=plan['symbol'],
                    direction=plan['direction'],
                    strategy_type=plan['strategy_type'],
                    ticket=plan['ticket'],
                    entry_price=plan['entry_price'],
                    planned_sl=plan['stop_loss'],
                    planned_tp=plan['take_profit'],
                    actual_entry=entry,
                    actual_exit=exit_price,
                    profit=profit,
                    profit_pips=pips,
                    duration_minutes=duration,
                    outcome=outcome_str,
                    executed_at=plan['executed_at'],
                    closed_at=close_time.isoformat() if close_time else None
                ))
        
        return outcomes
    
    def get_effectiveness_report(self, days_back: int = 30) -> Dict[str, Any]:
        """Generate comprehensive effectiveness report"""
        outcomes = self.get_plan_outcomes(days_back)
        
        if not outcomes:
            return {'error': 'No executed plans found', 'total_plans': 0}
        
        # Filter to closed trades only for stats
        closed = [o for o in outcomes if o.outcome in ('win', 'loss', 'breakeven')]
        open_trades = [o for o in outcomes if o.outcome == 'open']
        
        if not closed:
            return {
                'total_plans': len(outcomes),
                'open_trades': len(open_trades),
                'closed_trades': 0,
                'message': 'No closed trades yet'
            }
        
        # Overall stats
        wins = [o for o in closed if o.outcome == 'win']
        losses = [o for o in closed if o.outcome == 'loss']
        breakevens = [o for o in closed if o.outcome == 'breakeven']
        
        total_profit = sum(o.profit for o in closed)
        avg_win = sum(o.profit for o in wins) / len(wins) if wins else 0
        avg_loss = sum(o.profit for o in losses) / len(losses) if losses else 0
        
        # By strategy type
        by_strategy = {}
        for o in closed:
            st = o.strategy_type or 'unknown'
            if st not in by_strategy:
                by_strategy[st] = {'wins': 0, 'losses': 0, 'breakeven': 0, 'profit': 0}
            if o.outcome == 'win':
                by_strategy[st]['wins'] += 1
            elif o.outcome == 'loss':
                by_strategy[st]['losses'] += 1
            else:
                by_strategy[st]['breakeven'] += 1
            by_strategy[st]['profit'] += o.profit
        
        # Calculate win rates per strategy
        for st, data in by_strategy.items():
            total = data['wins'] + data['losses'] + data['breakeven']
            data['total'] = total
            data['win_rate'] = round(data['wins'] / total * 100, 1) if total > 0 else 0
        
        # By symbol
        by_symbol = {}
        for o in closed:
            sym = o.symbol
            if sym not in by_symbol:
                by_symbol[sym] = {'wins': 0, 'losses': 0, 'profit': 0}
            if o.outcome == 'win':
                by_symbol[sym]['wins'] += 1
            elif o.outcome == 'loss':
                by_symbol[sym]['losses'] += 1
            by_symbol[sym]['profit'] += o.profit
        
        for sym, data in by_symbol.items():
            total = data['wins'] + data['losses']
            data['win_rate'] = round(data['wins'] / total * 100, 1) if total > 0 else 0
        
        # Best/worst trades
        sorted_by_profit = sorted(closed, key=lambda x: x.profit, reverse=True)
        
        return {
            'period_days': days_back,
            'total_plans': len(outcomes),
            'open_trades': len(open_trades),
            'closed_trades': len(closed),
            'overall': {
                'wins': len(wins),
                'losses': len(losses),
                'breakeven': len(breakevens),
                'win_rate': round(len(wins) / len(closed) * 100, 1) if closed else 0,
                'total_profit': round(total_profit, 2),
                'avg_win': round(avg_win, 2),
                'avg_loss': round(avg_loss, 2),
                'profit_factor': round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0
            },
            'by_strategy': by_strategy,
            'by_symbol': by_symbol,
            'best_trade': asdict(sorted_by_profit[0]) if sorted_by_profit else None,
            'worst_trade': asdict(sorted_by_profit[-1]) if sorted_by_profit else None,
            'recent_trades': [asdict(o) for o in outcomes[:10]]
        }
    
    def print_report(self, days_back: int = 30):
        """Print formatted effectiveness report"""
        report = self.get_effectiveness_report(days_back)
        
        if 'error' in report:
            print(f"Error: {report['error']}")
            return
        
        print(f"\n{'='*60}")
        print(f"PLAN EFFECTIVENESS REPORT - Last {days_back} Days")
        print(f"{'='*60}")
        
        print(f"\nTotal Plans Executed: {report['total_plans']}")
        print(f"Open Trades: {report['open_trades']}")
        print(f"Closed Trades: {report['closed_trades']}")
        
        if 'overall' in report:
            o = report['overall']
            print(f"\n--- OVERALL PERFORMANCE ---")
            print(f"Win Rate: {o['win_rate']}% ({o['wins']}W / {o['losses']}L / {o['breakeven']}BE)")
            print(f"Total Profit: ${o['total_profit']}")
            print(f"Avg Win: ${o['avg_win']} | Avg Loss: ${o['avg_loss']}")
            print(f"Profit Factor: {o['profit_factor']}")
        
        if report.get('by_strategy'):
            print(f"\n--- BY STRATEGY ---")
            for st, data in sorted(report['by_strategy'].items(), key=lambda x: x[1]['profit'], reverse=True):
                print(f"  {st}: {data['win_rate']}% WR ({data['total']} trades) | ${round(data['profit'], 2)}")
        
        if report.get('by_symbol'):
            print(f"\n--- BY SYMBOL ---")
            for sym, data in sorted(report['by_symbol'].items(), key=lambda x: x[1]['profit'], reverse=True):
                print(f"  {sym}: {data['win_rate']}% WR | ${round(data['profit'], 2)}")
        
        if report.get('best_trade'):
            print(f"\n--- BEST TRADE ---")
            bt = report['best_trade']
            print(f"  {bt['plan_id']} | {bt['symbol']} {bt['direction']} | ${bt['profit']}")
        
        if report.get('worst_trade'):
            print(f"\n--- WORST TRADE ---")
            wt = report['worst_trade']
            print(f"  {wt['plan_id']} | {wt['symbol']} {wt['direction']} | ${wt['profit']}")
        
        print(f"\n{'='*60}\n")


# CLI usage
if __name__ == "__main__":
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    tracker = PlanEffectivenessTracker()
    tracker.print_report(days)

