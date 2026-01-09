"""
Paper Trading System for 4-6 Weeks with Live Data and Full Logging

This module implements a comprehensive paper trading system that:
- Simulates real trading without actual money
- Uses live market data from MT5 and Binance
- Provides full logging and monitoring
- Tracks performance metrics and risk
- Supports 4-6 week continuous operation
- Includes comprehensive reporting and analysis
"""

import asyncio
import json
import logging
import sqlite3
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
import uuid

import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PaperTradeStatus(Enum):
    """Paper trade status"""
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PaperOrderType(Enum):
    """Paper order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class PaperOrderSide(Enum):
    """Paper order sides"""
    BUY = "buy"
    SELL = "sell"


class PaperOrderStatus(Enum):
    """Paper order status"""
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class MarketSession(Enum):
    """Market session types"""
    ASIAN = "asian"
    LONDON = "london"
    NEW_YORK = "new_york"
    OVERLAP = "overlap"
    CRYPTO_24_7 = "crypto_24_7"


@dataclass
class PaperOrder:
    """Paper order representation"""
    order_id: str
    symbol: str
    side: PaperOrderSide
    order_type: PaperOrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: PaperOrderStatus = PaperOrderStatus.PENDING
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PaperTrade:
    """Paper trade representation"""
    trade_id: str
    symbol: str
    side: PaperOrderSide
    quantity: float
    entry_price: float
    exit_price: Optional[float] = None
    status: PaperTradeStatus = PaperTradeStatus.OPEN
    pnl: float = 0.0
    pnl_percentage: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    closed_at: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PaperAccount:
    """Paper trading account"""
    account_id: str
    initial_balance: float
    current_balance: float
    equity: float
    margin_used: float = 0.0
    free_margin: float = 0.0
    leverage: float = 1.0
    currency: str = "USD"
    positions: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class PaperTradingMetrics:
    """Paper trading performance metrics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    current_drawdown: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    average_trade_duration: float = 0.0
    total_volume: float = 0.0
    commission_paid: float = 0.0
    slippage_cost: float = 0.0


@dataclass
class MarketData:
    """Market data snapshot"""
    symbol: str
    timestamp: float
    bid: float
    ask: float
    last: float
    volume: float
    spread: float
    source: str  # 'mt5' or 'binance'


@dataclass
class PaperTradingConfig:
    """Paper trading configuration"""
    symbols: List[str]
    initial_balance: float = 10000.0
    leverage: float = 1.0
    commission_per_lot: float = 0.0
    slippage_bps: float = 0.5  # 0.5 basis points
    max_positions_per_symbol: int = 1
    max_total_positions: int = 10
    position_size_percent: float = 0.1  # 10% of account per trade
    stop_loss_percent: float = 0.02  # 2% stop loss
    take_profit_percent: float = 0.04  # 4% take profit
    max_daily_trades: int = 50
    max_daily_loss: float = 0.05  # 5% max daily loss
    trading_hours: Dict[str, List[Tuple[int, int]]] = field(default_factory=dict)
    enable_news_filter: bool = True
    enable_weekend_trading: bool = False
    log_level: str = "INFO"
    data_retention_days: int = 30


class MarketDataProvider:
    """Market data provider for paper trading"""
    
    def __init__(self, config: PaperTradingConfig):
        self.config = config
        self.data_cache: Dict[str, MarketData] = {}
        self.data_lock = threading.Lock()
        self.subscribers: List[Callable[[MarketData], None]] = []
        
    def subscribe(self, callback: Callable[[MarketData], None]):
        """Subscribe to market data updates"""
        self.subscribers.append(callback)
        
    def update_data(self, symbol: str, data: MarketData):
        """Update market data for a symbol"""
        with self.data_lock:
            self.data_cache[symbol] = data
            
        # Notify subscribers
        for callback in self.subscribers:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error in market data callback: {e}")
                
    def get_data(self, symbol: str) -> Optional[MarketData]:
        """Get current market data for a symbol"""
        with self.data_lock:
            return self.data_cache.get(symbol)
            
    def get_all_data(self) -> Dict[str, MarketData]:
        """Get all current market data"""
        with self.data_lock:
            return self.data_cache.copy()


class OrderManager:
    """Manages paper trading orders"""
    
    def __init__(self, config: PaperTradingConfig):
        self.config = config
        self.orders: Dict[str, PaperOrder] = {}
        self.order_lock = threading.Lock()
        self.order_counter = 0
        
    def create_order(self, symbol: str, side: PaperOrderSide, order_type: PaperOrderType,
                    quantity: float, price: Optional[float] = None, 
                    stop_price: Optional[float] = None, **kwargs) -> PaperOrder:
        """Create a new paper order"""
        order_id = f"ORD_{self.order_counter:06d}"
        self.order_counter += 1
        
        order = PaperOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            metadata=kwargs
        )
        
        with self.order_lock:
            self.orders[order_id] = order
            
        logger.info(f"Created paper order: {order_id} - {side.value} {quantity} {symbol} @ {price}")
        return order
        
    def get_order(self, order_id: str) -> Optional[PaperOrder]:
        """Get order by ID"""
        with self.order_lock:
            return self.orders.get(order_id)
            
    def update_order(self, order_id: str, **kwargs) -> bool:
        """Update order properties"""
        with self.order_lock:
            if order_id in self.orders:
                order = self.orders[order_id]
                for key, value in kwargs.items():
                    if hasattr(order, key):
                        setattr(order, key, value)
                order.updated_at = time.time()
                return True
        return False
        
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        return self.update_order(order_id, status=PaperOrderStatus.CANCELLED)
        
    def get_orders_by_symbol(self, symbol: str) -> List[PaperOrder]:
        """Get all orders for a symbol"""
        with self.order_lock:
            return [order for order in self.orders.values() if order.symbol == symbol]
            
    def get_active_orders(self) -> List[PaperOrder]:
        """Get all active orders"""
        with self.order_lock:
            return [order for order in self.orders.values() 
                   if order.status in [PaperOrderStatus.PENDING, PaperOrderStatus.PARTIALLY_FILLED]]


class TradeManager:
    """Manages paper trading positions and trades"""
    
    def __init__(self, config: PaperTradingConfig):
        self.config = config
        self.trades: Dict[str, PaperTrade] = {}
        self.positions: Dict[str, PaperTrade] = {}  # symbol -> trade
        self.trade_lock = threading.Lock()
        self.trade_counter = 0
        
    def create_trade(self, symbol: str, side: PaperOrderSide, quantity: float,
                    entry_price: float, stop_loss: Optional[float] = None,
                    take_profit: Optional[float] = None, **kwargs) -> PaperTrade:
        """Create a new paper trade"""
        trade_id = f"TRD_{self.trade_counter:06d}"
        self.trade_counter += 1
        
        trade = PaperTrade(
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata=kwargs
        )
        
        with self.trade_lock:
            self.trades[trade_id] = trade
            self.positions[symbol] = trade
            
        logger.info(f"Created paper trade: {trade_id} - {side.value} {quantity} {symbol} @ {entry_price}")
        return trade
        
    def close_trade(self, trade_id: str, exit_price: float) -> bool:
        """Close a paper trade"""
        with self.trade_lock:
            if trade_id in self.trades:
                trade = self.trades[trade_id]
                trade.exit_price = exit_price
                trade.status = PaperTradeStatus.CLOSED
                trade.closed_at = time.time()
                trade.updated_at = time.time()
                
                # Calculate PnL
                if trade.side == PaperOrderSide.BUY:
                    trade.pnl = (exit_price - trade.entry_price) * trade.quantity
                else:
                    trade.pnl = (trade.entry_price - exit_price) * trade.quantity
                    
                trade.pnl_percentage = (trade.pnl / (trade.entry_price * trade.quantity)) * 100
                
                # Remove from positions
                if trade.symbol in self.positions:
                    del self.positions[trade.symbol]
                    
                logger.info(f"Closed paper trade: {trade_id} - PnL: {trade.pnl:.2f}")
                return True
        return False
        
    def get_trade(self, trade_id: str) -> Optional[PaperTrade]:
        """Get trade by ID"""
        with self.trade_lock:
            return self.trades.get(trade_id)
            
    def get_position(self, symbol: str) -> Optional[PaperTrade]:
        """Get current position for a symbol"""
        with self.trade_lock:
            return self.positions.get(symbol)
            
    def get_all_positions(self) -> Dict[str, PaperTrade]:
        """Get all current positions"""
        with self.trade_lock:
            return self.positions.copy()
            
    def get_closed_trades(self) -> List[PaperTrade]:
        """Get all closed trades"""
        with self.trade_lock:
            return [trade for trade in self.trades.values() if trade.status == PaperTradeStatus.CLOSED]


class RiskManager:
    """Manages risk for paper trading"""
    
    def __init__(self, config: PaperTradingConfig, account: PaperAccount):
        self.config = config
        self.account = account
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.now().date()
        
    def can_open_position(self, symbol: str, quantity: float, price: float) -> Tuple[bool, str]:
        """Check if a position can be opened"""
        # Check daily trade limit
        if self.daily_trades >= self.config.max_daily_trades:
            return False, "Daily trade limit exceeded"
            
        # Check daily loss limit
        if self.daily_pnl <= -self.config.max_daily_loss * self.account.initial_balance:
            return False, "Daily loss limit exceeded"
            
        # Check position limits
        if len(self.account.positions) >= self.config.max_total_positions:
            return False, "Maximum total positions exceeded"
            
        # Check symbol position limit
        if symbol in self.account.positions and len([p for p in self.account.positions.values() if p.symbol == symbol]) >= self.config.max_positions_per_symbol:
            return False, "Maximum positions per symbol exceeded"
            
        # Check position size (use entry price without slippage for calculation)
        position_value = quantity * price
        max_position_value = self.account.current_balance * self.config.position_size_percent
        if position_value > max_position_value:
            return False, f"Position size too large: {position_value:.2f} > {max_position_value:.2f}"
            
        return True, "OK"
        
    def update_daily_metrics(self, pnl: float):
        """Update daily metrics"""
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.daily_trades = 0
            self.daily_pnl = 0.0
            self.last_reset_date = current_date
            
        self.daily_trades += 1
        self.daily_pnl += pnl


class PaperTradingEngine:
    """Main paper trading engine"""
    
    def __init__(self, config: PaperTradingConfig):
        self.config = config
        self.account = PaperAccount(
            account_id=f"PAPER_{uuid.uuid4().hex[:8]}",
            initial_balance=config.initial_balance,
            current_balance=config.initial_balance,
            equity=config.initial_balance,
            leverage=config.leverage
        )
        
        self.market_data_provider = MarketDataProvider(config)
        self.order_manager = OrderManager(config)
        self.trade_manager = TradeManager(config)
        self.risk_manager = RiskManager(config, self.account)
        
        self.running = False
        self.engine_thread = None
        self.metrics = PaperTradingMetrics()
        self.db_path = Path("paper_trading.db")
        self.setup_database()
        
        # Performance tracking
        self.performance_history = deque(maxlen=1000)
        self.trade_history = deque(maxlen=10000)
        
    def setup_database(self):
        """Setup SQLite database for paper trading data"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_trades (
                    trade_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    status TEXT NOT NULL,
                    pnl REAL DEFAULT 0.0,
                    pnl_percentage REAL DEFAULT 0.0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    closed_at REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_orders (
                    order_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL,
                    stop_price REAL,
                    status TEXT NOT NULL,
                    filled_quantity REAL DEFAULT 0.0,
                    average_fill_price REAL DEFAULT 0.0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    expires_at REAL,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    bid REAL NOT NULL,
                    ask REAL NOT NULL,
                    last REAL NOT NULL,
                    volume REAL NOT NULL,
                    spread REAL NOT NULL,
                    source TEXT NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0.0,
                    total_pnl REAL DEFAULT 0.0,
                    gross_profit REAL DEFAULT 0.0,
                    gross_loss REAL DEFAULT 0.0,
                    max_drawdown REAL DEFAULT 0.0,
                    current_drawdown REAL DEFAULT 0.0,
                    sharpe_ratio REAL DEFAULT 0.0,
                    profit_factor REAL DEFAULT 0.0
                )
            """)
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON paper_trades(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_created_at ON paper_trades(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_symbol ON paper_orders(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timestamp ON market_data(symbol, timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_performance_timestamp ON performance_metrics(timestamp)")
            
    def start(self):
        """Start the paper trading engine"""
        if self.running:
            logger.warning("Paper trading engine is already running")
            return
            
        self.running = True
        self.engine_thread = threading.Thread(target=self._run_engine, daemon=True)
        self.engine_thread.start()
        logger.info("Paper trading engine started")
        
    def stop(self):
        """Stop the paper trading engine"""
        self.running = False
        if self.engine_thread:
            self.engine_thread.join(timeout=5.0)
        logger.info("Paper trading engine stopped")
        
    def _run_engine(self):
        """Main engine loop"""
        while self.running:
            try:
                self._process_orders()
                self._update_positions()
                self._update_metrics()
                self._save_performance_data()
                time.sleep(0.1)  # 100ms loop
            except Exception as e:
                logger.error(f"Error in paper trading engine: {e}")
                time.sleep(1.0)
                
    def _process_orders(self):
        """Process pending orders"""
        active_orders = self.order_manager.get_active_orders()
        for order in active_orders:
            try:
                self._process_order(order)
            except Exception as e:
                logger.error(f"Error processing order {order.order_id}: {e}")
                
    def _process_order(self, order: PaperOrder):
        """Process a single order"""
        market_data = self.market_data_provider.get_data(order.symbol)
        if not market_data:
            return
            
        current_price = market_data.last
        spread = market_data.spread
        
        # Check if order should be filled
        should_fill = False
        fill_price = current_price
        
        if order.order_type == PaperOrderType.MARKET:
            should_fill = True
            # Add slippage
            if order.side == PaperOrderSide.BUY:
                fill_price = current_price + (spread * 0.5) + (current_price * self.config.slippage_bps / 10000)
            else:
                fill_price = current_price - (spread * 0.5) - (current_price * self.config.slippage_bps / 10000)
                
        elif order.order_type == PaperOrderType.LIMIT:
            if order.side == PaperOrderSide.BUY and current_price <= order.price:
                should_fill = True
                fill_price = min(order.price, current_price)
            elif order.side == PaperOrderSide.SELL and current_price >= order.price:
                should_fill = True
                fill_price = max(order.price, current_price)
                
        elif order.order_type == PaperOrderType.STOP:
            if order.side == PaperOrderSide.BUY and current_price >= order.stop_price:
                should_fill = True
                fill_price = current_price
            elif order.side == PaperOrderSide.SELL and current_price <= order.stop_price:
                should_fill = True
                fill_price = current_price
                
        if should_fill:
            # Check risk limits using the original price before slippage
            can_open, reason = self.risk_manager.can_open_position(
                order.symbol, order.quantity, current_price
            )
            
            if not can_open:
                self.order_manager.update_order(
                    order.order_id, 
                    status=PaperOrderStatus.REJECTED,
                    metadata={**order.metadata, "rejection_reason": reason}
                )
                logger.warning(f"Order {order.order_id} rejected: {reason}")
                return
                
            self._fill_order(order, fill_price)
            
    def _fill_order(self, order: PaperOrder, fill_price: float):
        """Fill an order"""
        # Update order
        self.order_manager.update_order(
            order.order_id,
            status=PaperOrderStatus.FILLED,
            filled_quantity=order.quantity,
            average_fill_price=fill_price
        )
        
        # Create trade
        trade = self.trade_manager.create_trade(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            entry_price=fill_price,
            metadata=order.metadata
        )
        
        # Update account
        self._update_account_balance(trade)
        
        # Update risk metrics
        self.risk_manager.update_daily_metrics(0.0)  # No PnL yet
        
        logger.info(f"Order {order.order_id} filled at {fill_price}")
        
    def _update_positions(self):
        """Update open positions"""
        positions = self.trade_manager.get_all_positions()
        for symbol, trade in positions.items():
            try:
                self._update_position(trade)
            except Exception as e:
                logger.error(f"Error updating position {trade.trade_id}: {e}")
                
    def _update_position(self, trade: PaperTrade):
        """Update a single position"""
        market_data = self.market_data_provider.get_data(trade.symbol)
        if not market_data:
            return
            
        current_price = market_data.last
        
        # Check stop loss
        if trade.stop_loss:
            if trade.side == PaperOrderSide.BUY and current_price <= trade.stop_loss:
                self._close_trade(trade, current_price, "Stop Loss")
                return
            elif trade.side == PaperOrderSide.SELL and current_price >= trade.stop_loss:
                self._close_trade(trade, current_price, "Stop Loss")
                return
                
        # Check take profit
        if trade.take_profit:
            if trade.side == PaperOrderSide.BUY and current_price >= trade.take_profit:
                self._close_trade(trade, current_price, "Take Profit")
                return
            elif trade.side == PaperOrderSide.SELL and current_price <= trade.take_profit:
                self._close_trade(trade, current_price, "Take Profit")
                return
                
        # Update unrealized PnL
        if trade.side == PaperOrderSide.BUY:
            unrealized_pnl = (current_price - trade.entry_price) * trade.quantity
        else:
            unrealized_pnl = (trade.entry_price - current_price) * trade.quantity
            
        # Update account equity
        self.account.equity = self.account.current_balance + unrealized_pnl
        
    def _close_trade(self, trade: PaperTrade, exit_price: float, reason: str):
        """Close a trade"""
        success = self.trade_manager.close_trade(trade.trade_id, exit_price)
        if success:
            # Update account balance
            self.account.current_balance += trade.pnl
            self.account.equity = self.account.current_balance
            
            # Update risk metrics
            self.risk_manager.update_daily_metrics(trade.pnl)
            
        # Add to trade history
        self.trade_history.append(trade)
        
        # Save trade to database
        self._save_trade_to_database(trade)
        
        # Update metrics immediately
        self._update_metrics()
        
        logger.info(f"Trade {trade.trade_id} closed: {reason} - PnL: {trade.pnl:.2f}")
            
    def _update_account_balance(self, trade: PaperTrade):
        """Update account balance for a new trade"""
        # For paper trading, we don't actually deduct margin
        # Just track the position
        pass
        
    def _update_metrics(self):
        """Update performance metrics"""
        closed_trades = self.trade_manager.get_closed_trades()
        
        if not closed_trades:
            return
            
        # Basic metrics
        self.metrics.total_trades = len(closed_trades)
        self.metrics.winning_trades = len([t for t in closed_trades if t.pnl > 0])
        self.metrics.losing_trades = len([t for t in closed_trades if t.pnl < 0])
        
        if self.metrics.total_trades > 0:
            self.metrics.win_rate = self.metrics.winning_trades / self.metrics.total_trades
            
        # PnL metrics
        self.metrics.total_pnl = sum(t.pnl for t in closed_trades)
        self.metrics.gross_profit = sum(t.pnl for t in closed_trades if t.pnl > 0)
        self.metrics.gross_loss = abs(sum(t.pnl for t in closed_trades if t.pnl < 0))
        
        if self.metrics.gross_loss > 0:
            self.metrics.profit_factor = self.metrics.gross_profit / self.metrics.gross_loss
            
        # Win/Loss metrics
        if self.metrics.winning_trades > 0:
            self.metrics.average_win = self.metrics.gross_profit / self.metrics.winning_trades
        if self.metrics.losing_trades > 0:
            self.metrics.average_loss = self.metrics.gross_loss / self.metrics.losing_trades
            
        # Largest win/loss
        if closed_trades:
            self.metrics.largest_win = max(t.pnl for t in closed_trades)
            self.metrics.largest_loss = min(t.pnl for t in closed_trades)
            
        # Drawdown calculation
        self._calculate_drawdown(closed_trades)
        
        # Sharpe ratio
        self._calculate_sharpe_ratio(closed_trades)
        
    def _calculate_drawdown(self, trades: List[PaperTrade]):
        """Calculate drawdown metrics"""
        if not trades:
            return
            
        # Sort trades by close time
        sorted_trades = sorted(trades, key=lambda t: t.closed_at or t.created_at)
        
        peak_balance = self.account.initial_balance
        max_drawdown = 0.0
        current_drawdown = 0.0
        drawdown_duration = 0
        max_drawdown_duration = 0
        
        running_balance = self.account.initial_balance
        
        for trade in sorted_trades:
            running_balance += trade.pnl
            
            if running_balance > peak_balance:
                peak_balance = running_balance
                current_drawdown = 0.0
                drawdown_duration = 0
            else:
                current_drawdown = (peak_balance - running_balance) / peak_balance
                drawdown_duration += 1
                
            if current_drawdown > max_drawdown:
                max_drawdown = current_drawdown
                max_drawdown_duration = drawdown_duration
                
        self.metrics.max_drawdown = max_drawdown
        self.metrics.max_drawdown_duration = max_drawdown_duration
        self.metrics.current_drawdown = current_drawdown
        
    def _calculate_sharpe_ratio(self, trades: List[PaperTrade]):
        """Calculate Sharpe ratio"""
        if len(trades) < 2:
            return
            
        returns = [trade.pnl for trade in trades]
        if not returns:
            return
            
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return > 0:
            self.metrics.sharpe_ratio = mean_return / std_return
            
    def _save_trade_to_database(self, trade: PaperTrade):
        """Save trade to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO paper_trades (
                        trade_id, symbol, side, quantity, entry_price, exit_price,
                        status, pnl, pnl_percentage, created_at, updated_at, closed_at,
                        stop_loss, take_profit, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.trade_id,
                    trade.symbol,
                    trade.side.value,
                    trade.quantity,
                    trade.entry_price,
                    trade.exit_price,
                    trade.status.value,
                    trade.pnl,
                    trade.pnl_percentage,
                    trade.created_at,
                    trade.updated_at,
                    trade.closed_at,
                    trade.stop_loss,
                    trade.take_profit,
                    json.dumps(trade.metadata)
                ))
        except Exception as e:
            logger.error(f"Error saving trade to database: {e}")

    def _save_performance_data(self):
        """Save performance data to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO performance_metrics (
                        timestamp, total_trades, winning_trades, losing_trades,
                        win_rate, total_pnl, gross_profit, gross_loss,
                        max_drawdown, current_drawdown, sharpe_ratio, profit_factor
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    time.time(),
                    self.metrics.total_trades,
                    self.metrics.winning_trades,
                    self.metrics.losing_trades,
                    self.metrics.win_rate,
                    self.metrics.total_pnl,
                    self.metrics.gross_profit,
                    self.metrics.gross_loss,
                    self.metrics.max_drawdown,
                    self.metrics.current_drawdown,
                    self.metrics.sharpe_ratio,
                    self.metrics.profit_factor
                ))
        except Exception as e:
            logger.error(f"Error saving performance data: {e}")
            
    def place_order(self, symbol: str, side: PaperOrderSide, order_type: PaperOrderType,
                   quantity: float, price: Optional[float] = None, 
                   stop_price: Optional[float] = None, **kwargs) -> PaperOrder:
        """Place a paper trading order"""
        return self.order_manager.create_order(
            symbol, side, order_type, quantity, price, stop_price, **kwargs
        )
        
    def close_position(self, symbol: str) -> bool:
        """Close position for a symbol"""
        position = self.trade_manager.get_position(symbol)
        if not position:
            return False
            
        market_data = self.market_data_provider.get_data(symbol)
        if not market_data:
            return False
            
        # Use the engine's close trade method to trigger metrics updates
        self._close_trade(position, market_data.last, "Manual close")
        return True
        
    def get_account_summary(self) -> Dict[str, Any]:
        """Get account summary"""
        return {
            "account_id": self.account.account_id,
            "initial_balance": self.account.initial_balance,
            "current_balance": self.account.current_balance,
            "equity": self.account.equity,
            "margin_used": self.account.margin_used,
            "free_margin": self.account.free_margin,
            "leverage": self.account.leverage,
            "currency": self.account.currency,
            "open_positions": len(self.trade_manager.get_all_positions()),
            "daily_trades": self.risk_manager.daily_trades,
            "daily_pnl": self.risk_manager.daily_pnl
        }
        
    def get_performance_metrics(self) -> PaperTradingMetrics:
        """Get current performance metrics"""
        return self.metrics
        
    def get_trade_history(self, limit: int = 100) -> List[PaperTrade]:
        """Get trade history"""
        closed_trades = self.trade_manager.get_closed_trades()
        return sorted(closed_trades, key=lambda t: t.closed_at or t.created_at, reverse=True)[:limit]
        
    def get_positions(self) -> Dict[str, PaperTrade]:
        """Get current positions"""
        return self.trade_manager.get_all_positions()
        
    def get_orders(self, symbol: Optional[str] = None) -> List[PaperOrder]:
        """Get orders"""
        if symbol:
            return self.order_manager.get_orders_by_symbol(symbol)
        else:
            return list(self.order_manager.orders.values())
            
    def update_market_data(self, symbol: str, data: MarketData):
        """Update market data"""
        self.market_data_provider.update_data(symbol, data)
        
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive trading report"""
        return {
            "account": self.get_account_summary(),
            "metrics": self.metrics.__dict__,
            "positions": {symbol: {
                "trade_id": trade.trade_id,
                "side": trade.side.value,
                "quantity": trade.quantity,
                "entry_price": trade.entry_price,
                "unrealized_pnl": self._calculate_unrealized_pnl(trade),
                "created_at": trade.created_at
            } for symbol, trade in self.get_positions().items()},
            "recent_trades": [{
                "trade_id": trade.trade_id,
                "symbol": trade.symbol,
                "side": trade.side.value,
                "quantity": trade.quantity,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "pnl": trade.pnl,
                "pnl_percentage": trade.pnl_percentage,
                "created_at": trade.created_at,
                "closed_at": trade.closed_at
            } for trade in self.get_trade_history(10)]
        }
        
    def _calculate_unrealized_pnl(self, trade: PaperTrade) -> float:
        """Calculate unrealized PnL for a position"""
        market_data = self.market_data_provider.get_data(trade.symbol)
        if not market_data:
            return 0.0
            
        current_price = market_data.last
        if trade.side == PaperOrderSide.BUY:
            return (current_price - trade.entry_price) * trade.quantity
        else:
            return (trade.entry_price - current_price) * trade.quantity


# Global functions for easy access
_paper_trading_engine: Optional[PaperTradingEngine] = None

def get_paper_trading_engine() -> Optional[PaperTradingEngine]:
    """Get the global paper trading engine instance"""
    return _paper_trading_engine

def create_paper_trading_engine(config: PaperTradingConfig) -> PaperTradingEngine:
    """Create a new paper trading engine"""
    global _paper_trading_engine
    _paper_trading_engine = PaperTradingEngine(config)
    return _paper_trading_engine

def start_paper_trading(config: PaperTradingConfig) -> PaperTradingEngine:
    """Start paper trading with the given configuration"""
    engine = create_paper_trading_engine(config)
    engine.start()
    return engine

def stop_paper_trading():
    """Stop paper trading"""
    global _paper_trading_engine
    if _paper_trading_engine:
        _paper_trading_engine.stop()
        _paper_trading_engine = None

def get_paper_trading_status() -> Dict[str, Any]:
    """Get paper trading status"""
    if _paper_trading_engine:
        return {
            "running": _paper_trading_engine.running,
            "account": _paper_trading_engine.get_account_summary(),
            "metrics": _paper_trading_engine.get_performance_metrics().__dict__
        }
    return {"running": False, "error": "Paper trading engine not initialized"}

def place_paper_order(symbol: str, side: str, order_type: str, quantity: float, 
                     price: Optional[float] = None, **kwargs) -> Optional[PaperOrder]:
    """Place a paper trading order"""
    if not _paper_trading_engine:
        return None
        
    try:
        side_enum = PaperOrderSide(side.lower())
        order_type_enum = PaperOrderType(order_type.lower())
        return _paper_trading_engine.place_order(
            symbol, side_enum, order_type_enum, quantity, price, **kwargs
        )
    except ValueError as e:
        logger.error(f"Invalid order parameters: {e}")
        return None

def close_paper_position(symbol: str) -> bool:
    """Close a paper trading position"""
    if not _paper_trading_engine:
        return False
    return _paper_trading_engine.close_position(symbol)

def get_paper_trading_report() -> Dict[str, Any]:
    """Get comprehensive paper trading report"""
    if not _paper_trading_engine:
        return {"error": "Paper trading engine not initialized"}
    return _paper_trading_engine.generate_report()
