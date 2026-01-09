"""
Tests for Paper Trading System

This module tests the comprehensive paper trading system including:
- Order management and execution
- Trade lifecycle and PnL calculation
- Risk management and position limits
- Performance metrics and reporting
- Market data integration
- Database operations
"""

import pytest
import sqlite3
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from infra.paper_trading_system import (
    PaperTradingEngine, PaperTradingConfig, PaperAccount, PaperOrder,
    PaperTrade, PaperOrderType, PaperOrderSide, PaperOrderStatus,
    PaperTradeStatus, MarketData, MarketDataProvider, OrderManager,
    TradeManager, RiskManager, PaperTradingMetrics,
    get_paper_trading_engine, create_paper_trading_engine,
    start_paper_trading, stop_paper_trading, get_paper_trading_status,
    place_paper_order, close_paper_position, get_paper_trading_report
)


class TestPaperTradingConfig:
    """Test paper trading configuration"""
    
    def test_config_creation(self):
        """Test configuration creation with defaults"""
        config = PaperTradingConfig(symbols=["BTCUSDc", "XAUUSDc"])
        
        assert config.symbols == ["BTCUSDc", "XAUUSDc"]
        assert config.initial_balance == 10000.0
        assert config.leverage == 1.0
        assert config.commission_per_lot == 0.0
        assert config.slippage_bps == 0.5
        assert config.max_positions_per_symbol == 1
        assert config.max_total_positions == 10
        assert config.position_size_percent == 0.1
        assert config.stop_loss_percent == 0.02
        assert config.take_profit_percent == 0.04
        assert config.max_daily_trades == 50
        assert config.max_daily_loss == 0.05
        assert config.enable_news_filter == True
        assert config.enable_weekend_trading == False
        assert config.log_level == "INFO"
        assert config.data_retention_days == 30

    def test_config_custom_values(self):
        """Test configuration with custom values"""
        config = PaperTradingConfig(
            symbols=["EURUSDc"],
            initial_balance=50000.0,
            leverage=2.0,
            commission_per_lot=5.0,
            slippage_bps=1.0,
            max_positions_per_symbol=2,
            max_total_positions=20,
            position_size_percent=0.05,
            stop_loss_percent=0.01,
            take_profit_percent=0.03,
            max_daily_trades=100,
            max_daily_loss=0.02
        )
        
        assert config.symbols == ["EURUSDc"]
        assert config.initial_balance == 50000.0
        assert config.leverage == 2.0
        assert config.commission_per_lot == 5.0
        assert config.slippage_bps == 1.0
        assert config.max_positions_per_symbol == 2
        assert config.max_total_positions == 20
        assert config.position_size_percent == 0.05
        assert config.stop_loss_percent == 0.01
        assert config.take_profit_percent == 0.03
        assert config.max_daily_trades == 100
        assert config.max_daily_loss == 0.02


class TestPaperOrder:
    """Test paper order functionality"""
    
    def test_order_creation(self):
        """Test order creation with all parameters"""
        order = PaperOrder(
            order_id="ORD_001",
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=0.1,
            price=50000.0
        )
        
        assert order.order_id == "ORD_001"
        assert order.symbol == "BTCUSDc"
        assert order.side == PaperOrderSide.BUY
        assert order.order_type == PaperOrderType.MARKET
        assert order.quantity == 0.1
        assert order.price == 50000.0
        assert order.status == PaperOrderStatus.PENDING
        assert order.filled_quantity == 0.0
        assert order.average_fill_price == 0.0
        assert order.created_at > 0
        assert order.updated_at > 0
        assert order.expires_at is None
        assert order.metadata == {}

    def test_order_creation_minimal(self):
        """Test order creation with minimal parameters"""
        order = PaperOrder(
            order_id="ORD_002",
            symbol="XAUUSDc",
            side=PaperOrderSide.SELL,
            order_type=PaperOrderType.LIMIT,
            quantity=1.0
        )
        
        assert order.order_id == "ORD_002"
        assert order.symbol == "XAUUSDc"
        assert order.side == PaperOrderSide.SELL
        assert order.order_type == PaperOrderType.LIMIT
        assert order.quantity == 1.0
        assert order.price is None
        assert order.stop_price is None
        assert order.status == PaperOrderStatus.PENDING

    def test_order_metadata(self):
        """Test order with metadata"""
        metadata = {"strategy": "momentum", "timeframe": "M15"}
        order = PaperOrder(
            order_id="ORD_003",
            symbol="EURUSDc",
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.STOP,
            quantity=0.5,
            stop_price=1.2000,
            metadata=metadata
        )
        
        assert order.metadata == metadata
        assert order.stop_price == 1.2000


class TestPaperTrade:
    """Test paper trade functionality"""
    
    def test_trade_creation(self):
        """Test trade creation with all parameters"""
        trade = PaperTrade(
            trade_id="TRD_001",
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            quantity=0.1,
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0
        )
        
        assert trade.trade_id == "TRD_001"
        assert trade.symbol == "BTCUSDc"
        assert trade.side == PaperOrderSide.BUY
        assert trade.quantity == 0.1
        assert trade.entry_price == 50000.0
        assert trade.exit_price is None
        assert trade.status == PaperTradeStatus.OPEN
        assert trade.pnl == 0.0
        assert trade.pnl_percentage == 0.0
        assert trade.stop_loss == 49000.0
        assert trade.take_profit == 52000.0
        assert trade.created_at > 0
        assert trade.updated_at > 0
        assert trade.closed_at is None

    def test_trade_creation_minimal(self):
        """Test trade creation with minimal parameters"""
        trade = PaperTrade(
            trade_id="TRD_002",
            symbol="XAUUSDc",
            side=PaperOrderSide.SELL,
            quantity=1.0,
            entry_price=1800.0
        )
        
        assert trade.trade_id == "TRD_002"
        assert trade.symbol == "XAUUSDc"
        assert trade.side == PaperOrderSide.SELL
        assert trade.quantity == 1.0
        assert trade.entry_price == 1800.0
        assert trade.stop_loss is None
        assert trade.take_profit is None
        assert trade.status == PaperTradeStatus.OPEN

    def test_trade_metadata(self):
        """Test trade with metadata"""
        metadata = {"strategy": "scalping", "risk_level": "high"}
        trade = PaperTrade(
            trade_id="TRD_003",
            symbol="EURUSDc",
            side=PaperOrderSide.BUY,
            quantity=0.5,
            entry_price=1.2000,
            metadata=metadata
        )
        
        assert trade.metadata == metadata


class TestPaperAccount:
    """Test paper account functionality"""
    
    def test_account_creation(self):
        """Test account creation with all parameters"""
        account = PaperAccount(
            account_id="ACC_001",
            initial_balance=10000.0,
            current_balance=9500.0,
            equity=9800.0,
            margin_used=500.0,
            free_margin=9300.0,
            leverage=2.0,
            currency="USD"
        )
        
        assert account.account_id == "ACC_001"
        assert account.initial_balance == 10000.0
        assert account.current_balance == 9500.0
        assert account.equity == 9800.0
        assert account.margin_used == 500.0
        assert account.free_margin == 9300.0
        assert account.leverage == 2.0
        assert account.currency == "USD"
        assert account.created_at > 0
        assert account.updated_at > 0

    def test_account_creation_defaults(self):
        """Test account creation with defaults"""
        account = PaperAccount(
            account_id="ACC_002",
            initial_balance=5000.0,
            current_balance=5000.0,
            equity=5000.0
        )
        
        assert account.account_id == "ACC_002"
        assert account.initial_balance == 5000.0
        assert account.current_balance == 5000.0
        assert account.equity == 5000.0
        assert account.margin_used == 0.0
        assert account.free_margin == 0.0
        assert account.leverage == 1.0
        assert account.currency == "USD"


class TestMarketData:
    """Test market data functionality"""
    
    def test_market_data_creation(self):
        """Test market data creation"""
        data = MarketData(
            symbol="BTCUSDc",
            timestamp=time.time(),
            bid=50000.0,
            ask=50010.0,
            last=50005.0,
            volume=1.5,
            spread=10.0,
            source="mt5"
        )
        
        assert data.symbol == "BTCUSDc"
        assert data.timestamp > 0
        assert data.bid == 50000.0
        assert data.ask == 50010.0
        assert data.last == 50005.0
        assert data.volume == 1.5
        assert data.spread == 10.0
        assert data.source == "mt5"

    def test_market_data_binance(self):
        """Test market data from Binance"""
        data = MarketData(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bid=50000.0,
            ask=50010.0,
            last=50005.0,
            volume=2.0,
            spread=10.0,
            source="binance"
        )
        
        assert data.symbol == "BTCUSDT"
        assert data.source == "binance"


class TestMarketDataProvider:
    """Test market data provider"""
    
    def setup_method(self):
        """Setup test method"""
        self.config = PaperTradingConfig(symbols=["BTCUSDc", "XAUUSDc"])
        self.provider = MarketDataProvider(self.config)

    def test_provider_initialization(self):
        """Test provider initialization"""
        assert self.provider.config == self.config
        assert self.provider.data_cache == {}
        assert self.provider.subscribers == []

    def test_subscribe_callback(self):
        """Test subscribing to market data updates"""
        callback_called = False
        received_data = None
        
        def callback(data):
            nonlocal callback_called, received_data
            callback_called = True
            received_data = data
            
        self.provider.subscribe(callback)
        
        # Update data
        data = MarketData(
            symbol="BTCUSDc",
            timestamp=time.time(),
            bid=50000.0,
            ask=50010.0,
            last=50005.0,
            volume=1.0,
            spread=10.0,
            source="mt5"
        )
        
        self.provider.update_data("BTCUSDc", data)
        
        assert callback_called
        assert received_data == data

    def test_update_data(self):
        """Test updating market data"""
        data = MarketData(
            symbol="BTCUSDc",
            timestamp=time.time(),
            bid=50000.0,
            ask=50010.0,
            last=50005.0,
            volume=1.0,
            spread=10.0,
            source="mt5"
        )
        
        self.provider.update_data("BTCUSDc", data)
        
        retrieved_data = self.provider.get_data("BTCUSDc")
        assert retrieved_data == data

    def test_get_all_data(self):
        """Test getting all market data"""
        data1 = MarketData(
            symbol="BTCUSDc",
            timestamp=time.time(),
            bid=50000.0,
            ask=50010.0,
            last=50005.0,
            volume=1.0,
            spread=10.0,
            source="mt5"
        )
        
        data2 = MarketData(
            symbol="XAUUSDc",
            timestamp=time.time(),
            bid=1800.0,
            ask=1805.0,
            last=1802.5,
            volume=2.0,
            spread=5.0,
            source="mt5"
        )
        
        self.provider.update_data("BTCUSDc", data1)
        self.provider.update_data("XAUUSDc", data2)
        
        all_data = self.provider.get_all_data()
        assert len(all_data) == 2
        assert "BTCUSDc" in all_data
        assert "XAUUSDc" in all_data


class TestOrderManager:
    """Test order manager functionality"""
    
    def setup_method(self):
        """Setup test method"""
        self.config = PaperTradingConfig(symbols=["BTCUSDc", "XAUUSDc"])
        self.manager = OrderManager(self.config)

    def test_manager_initialization(self):
        """Test order manager initialization"""
        assert self.manager.config == self.config
        assert self.manager.orders == {}
        assert self.manager.order_counter == 0

    def test_create_order(self):
        """Test creating an order"""
        order = self.manager.create_order(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=0.1,
            price=50000.0
        )
        
        assert order.order_id == "ORD_000000"
        assert order.symbol == "BTCUSDc"
        assert order.side == PaperOrderSide.BUY
        assert order.order_type == PaperOrderType.MARKET
        assert order.quantity == 0.1
        assert order.price == 50000.0
        assert order.status == PaperOrderStatus.PENDING
        assert order.order_id in self.manager.orders

    def test_create_multiple_orders(self):
        """Test creating multiple orders"""
        order1 = self.manager.create_order(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=0.1
        )
        
        order2 = self.manager.create_order(
            symbol="XAUUSDc",
            side=PaperOrderSide.SELL,
            order_type=PaperOrderType.LIMIT,
            quantity=1.0,
            price=1800.0
        )
        
        assert order1.order_id == "ORD_000000"
        assert order2.order_id == "ORD_000001"
        assert len(self.manager.orders) == 2

    def test_get_order(self):
        """Test getting an order by ID"""
        order = self.manager.create_order(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=0.1
        )
        
        retrieved_order = self.manager.get_order(order.order_id)
        assert retrieved_order == order
        
        non_existent = self.manager.get_order("NON_EXISTENT")
        assert non_existent is None

    def test_update_order(self):
        """Test updating an order"""
        order = self.manager.create_order(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=0.1
        )
        
        success = self.manager.update_order(
            order.order_id,
            status=PaperOrderStatus.FILLED,
            filled_quantity=0.1,
            average_fill_price=50000.0
        )
        
        assert success
        updated_order = self.manager.get_order(order.order_id)
        assert updated_order.status == PaperOrderStatus.FILLED
        assert updated_order.filled_quantity == 0.1
        assert updated_order.average_fill_price == 50000.0

    def test_cancel_order(self):
        """Test canceling an order"""
        order = self.manager.create_order(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=0.1
        )
        
        success = self.manager.cancel_order(order.order_id)
        assert success
        
        updated_order = self.manager.get_order(order.order_id)
        assert updated_order.status == PaperOrderStatus.CANCELLED

    def test_get_orders_by_symbol(self):
        """Test getting orders by symbol"""
        order1 = self.manager.create_order(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=0.1
        )
        
        order2 = self.manager.create_order(
            symbol="XAUUSDc",
            side=PaperOrderSide.SELL,
            order_type=PaperOrderType.MARKET,
            quantity=1.0
        )
        
        order3 = self.manager.create_order(
            symbol="BTCUSDc",
            side=PaperOrderSide.SELL,
            order_type=PaperOrderType.MARKET,
            quantity=0.2
        )
        
        btc_orders = self.manager.get_orders_by_symbol("BTCUSDc")
        assert len(btc_orders) == 2
        assert order1 in btc_orders
        assert order3 in btc_orders
        assert order2 not in btc_orders

    def test_get_active_orders(self):
        """Test getting active orders"""
        order1 = self.manager.create_order(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=0.1
        )
        
        order2 = self.manager.create_order(
            symbol="XAUUSDc",
            side=PaperOrderSide.SELL,
            order_type=PaperOrderType.MARKET,
            quantity=1.0
        )
        
        # Update one order to filled
        self.manager.update_order(order1.order_id, status=PaperOrderStatus.FILLED)
        
        active_orders = self.manager.get_active_orders()
        assert len(active_orders) == 1
        assert order2 in active_orders
        assert order1 not in active_orders


class TestTradeManager:
    """Test trade manager functionality"""
    
    def setup_method(self):
        """Setup test method"""
        self.config = PaperTradingConfig(symbols=["BTCUSDc", "XAUUSDc"])
        self.manager = TradeManager(self.config)

    def test_manager_initialization(self):
        """Test trade manager initialization"""
        assert self.manager.config == self.config
        assert self.manager.trades == {}
        assert self.manager.positions == {}
        assert self.manager.trade_counter == 0

    def test_create_trade(self):
        """Test creating a trade"""
        trade = self.manager.create_trade(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            quantity=0.1,
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0
        )
        
        assert trade.trade_id == "TRD_000000"
        assert trade.symbol == "BTCUSDc"
        assert trade.side == PaperOrderSide.BUY
        assert trade.quantity == 0.1
        assert trade.entry_price == 50000.0
        assert trade.stop_loss == 49000.0
        assert trade.take_profit == 52000.0
        assert trade.status == PaperTradeStatus.OPEN
        assert trade.trade_id in self.manager.trades
        assert "BTCUSDc" in self.manager.positions

    def test_close_trade(self):
        """Test closing a trade"""
        trade = self.manager.create_trade(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            quantity=0.1,
            entry_price=50000.0
        )
        
        success = self.manager.close_trade(trade.trade_id, 51000.0)
        assert success
        
        updated_trade = self.manager.get_trade(trade.trade_id)
        assert updated_trade.exit_price == 51000.0
        assert updated_trade.status == PaperTradeStatus.CLOSED
        assert updated_trade.pnl == 100.0  # (51000 - 50000) * 0.1
        assert updated_trade.pnl_percentage == 2.0  # (100 / 5000) * 100
        assert updated_trade.closed_at is not None
        assert "BTCUSDc" not in self.manager.positions

    def test_close_trade_sell_side(self):
        """Test closing a sell trade"""
        trade = self.manager.create_trade(
            symbol="XAUUSDc",
            side=PaperOrderSide.SELL,
            quantity=1.0,
            entry_price=1800.0
        )
        
        success = self.manager.close_trade(trade.trade_id, 1750.0)
        assert success
        
        updated_trade = self.manager.get_trade(trade.trade_id)
        assert updated_trade.exit_price == 1750.0
        assert updated_trade.pnl == 50.0  # (1800 - 1750) * 1.0
        assert abs(updated_trade.pnl_percentage - 2.78) < 0.01  # (50 / 1800) * 100

    def test_get_position(self):
        """Test getting position by symbol"""
        trade = self.manager.create_trade(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            quantity=0.1,
            entry_price=50000.0
        )
        
        position = self.manager.get_position("BTCUSDc")
        assert position == trade
        
        no_position = self.manager.get_position("XAUUSDc")
        assert no_position is None

    def test_get_all_positions(self):
        """Test getting all positions"""
        trade1 = self.manager.create_trade(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            quantity=0.1,
            entry_price=50000.0
        )
        
        trade2 = self.manager.create_trade(
            symbol="XAUUSDc",
            side=PaperOrderSide.SELL,
            quantity=1.0,
            entry_price=1800.0
        )
        
        positions = self.manager.get_all_positions()
        assert len(positions) == 2
        assert positions["BTCUSDc"] == trade1
        assert positions["XAUUSDc"] == trade2

    def test_get_closed_trades(self):
        """Test getting closed trades"""
        trade1 = self.manager.create_trade(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            quantity=0.1,
            entry_price=50000.0
        )
        
        trade2 = self.manager.create_trade(
            symbol="XAUUSDc",
            side=PaperOrderSide.SELL,
            quantity=1.0,
            entry_price=1800.0
        )
        
        # Close one trade
        self.manager.close_trade(trade1.trade_id, 51000.0)
        
        closed_trades = self.manager.get_closed_trades()
        assert len(closed_trades) == 1
        assert closed_trades[0] == trade1


class TestRiskManager:
    """Test risk manager functionality"""
    
    def setup_method(self):
        """Setup test method"""
        self.config = PaperTradingConfig(
            symbols=["BTCUSDc", "XAUUSDc"],
            max_daily_trades=10,
            max_daily_loss=0.05,
            max_total_positions=5,
            max_positions_per_symbol=2,
            position_size_percent=0.1
        )
        self.account = PaperAccount(
            account_id="TEST_ACC",
            initial_balance=10000.0,
            current_balance=10000.0,
            equity=10000.0
        )
        self.manager = RiskManager(self.config, self.account)

    def test_manager_initialization(self):
        """Test risk manager initialization"""
        assert self.manager.config == self.config
        assert self.manager.account == self.account
        assert self.manager.daily_trades == 0
        assert self.manager.daily_pnl == 0.0

    def test_can_open_position_success(self):
        """Test successful position opening"""
        can_open, reason = self.manager.can_open_position("BTCUSDc", 0.01, 50000.0)  # Smaller position
        assert can_open
        assert reason == "OK"

    def test_can_open_position_daily_trade_limit(self):
        """Test daily trade limit"""
        # Set daily trades to limit
        self.manager.daily_trades = self.config.max_daily_trades
        
        can_open, reason = self.manager.can_open_position("BTCUSDc", 0.1, 50000.0)
        assert not can_open
        assert "Daily trade limit exceeded" in reason

    def test_can_open_position_daily_loss_limit(self):
        """Test daily loss limit"""
        # Set daily PnL to loss limit
        self.manager.daily_pnl = -self.config.max_daily_loss * self.account.initial_balance
        
        can_open, reason = self.manager.can_open_position("BTCUSDc", 0.1, 50000.0)
        assert not can_open
        assert "Daily loss limit exceeded" in reason

    def test_can_open_position_position_size_limit(self):
        """Test position size limit"""
        # Try to open position larger than allowed
        large_quantity = 1.0  # 1 BTC at 50000 = 50000, which is 500% of 10000 balance
        can_open, reason = self.manager.can_open_position("BTCUSDc", large_quantity, 50000.0)
        assert not can_open
        assert "Position size too large" in reason

    def test_update_daily_metrics(self):
        """Test updating daily metrics"""
        # Update with profit
        self.manager.update_daily_metrics(100.0)
        assert self.manager.daily_trades == 1
        assert self.manager.daily_pnl == 100.0
        
        # Update with loss
        self.manager.update_daily_metrics(-50.0)
        assert self.manager.daily_trades == 2
        assert self.manager.daily_pnl == 50.0

    def test_daily_metrics_reset(self):
        """Test daily metrics reset on new day"""
        # Set some metrics
        self.manager.daily_trades = 5
        self.manager.daily_pnl = 200.0
        
        # Mock datetime to next day
        with patch('infra.paper_trading_system.datetime') as mock_datetime:
            mock_datetime.now.return_value.date.return_value = datetime.now().date() + timedelta(days=1)
            
            self.manager.update_daily_metrics(100.0)
            assert self.manager.daily_trades == 1
            assert self.manager.daily_pnl == 100.0


class TestPaperTradingEngine:
    """Test paper trading engine"""
    
    def setup_method(self):
        """Setup test method"""
        self.config = PaperTradingConfig(
            symbols=["BTCUSDc", "XAUUSDc"],
            initial_balance=100000.0,  # Larger balance for testing
            position_size_percent=0.1  # 10% max position size for testing
        )
        self.engine = PaperTradingEngine(self.config)

    def test_engine_initialization(self):
        """Test engine initialization"""
        assert self.engine.config == self.config
        assert self.engine.account.initial_balance == self.config.initial_balance
        assert self.engine.account.current_balance == self.config.initial_balance
        assert self.engine.account.equity == self.config.initial_balance
        assert self.engine.running == False
        assert self.engine.engine_thread is None

    def test_place_order(self):
        """Test placing an order"""
        order = self.engine.place_order(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=0.1
        )
        
        assert order is not None
        assert order.symbol == "BTCUSDc"
        assert order.side == PaperOrderSide.BUY
        assert order.order_type == PaperOrderType.MARKET
        assert order.quantity == 0.1
        assert order.status == PaperOrderStatus.PENDING

    def test_close_position(self):
        """Test closing a position"""
        # First create a position by placing and filling an order
        order = self.engine.place_order(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=0.1
        )
        
        # Mock market data
        market_data = MarketData(
            symbol="BTCUSDc",
            timestamp=time.time(),
            bid=50000.0,
            ask=50010.0,
            last=50005.0,
            volume=1.0,
            spread=10.0,
            source="mt5"
        )
        
        self.engine.update_market_data("BTCUSDc", market_data)
        
        # Process the order to create a trade
        self.engine._process_order(order)
        
        # Now close the position
        success = self.engine.close_position("BTCUSDc")
        assert success

    def test_get_account_summary(self):
        """Test getting account summary"""
        summary = self.engine.get_account_summary()
        
        assert "account_id" in summary
        assert "initial_balance" in summary
        assert "current_balance" in summary
        assert "equity" in summary
        assert "open_positions" in summary
        assert "daily_trades" in summary
        assert "daily_pnl" in summary

    def test_get_performance_metrics(self):
        """Test getting performance metrics"""
        metrics = self.engine.get_performance_metrics()
        assert isinstance(metrics, PaperTradingMetrics)
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0
        assert metrics.total_pnl == 0.0

    def test_get_trade_history(self):
        """Test getting trade history"""
        history = self.engine.get_trade_history()
        assert isinstance(history, list)
        assert len(history) == 0

    def test_get_positions(self):
        """Test getting positions"""
        positions = self.engine.get_positions()
        assert isinstance(positions, dict)
        assert len(positions) == 0

    def test_get_orders(self):
        """Test getting orders"""
        orders = self.engine.get_orders()
        assert isinstance(orders, list)
        assert len(orders) == 0

    def test_update_market_data(self):
        """Test updating market data"""
        market_data = MarketData(
            symbol="BTCUSDc",
            timestamp=time.time(),
            bid=50000.0,
            ask=50010.0,
            last=50005.0,
            volume=1.0,
            spread=10.0,
            source="mt5"
        )
        
        self.engine.update_market_data("BTCUSDc", market_data)
        
        retrieved_data = self.engine.market_data_provider.get_data("BTCUSDc")
        assert retrieved_data == market_data

    def test_generate_report(self):
        """Test generating comprehensive report"""
        report = self.engine.generate_report()
        
        assert "account" in report
        assert "metrics" in report
        assert "positions" in report
        assert "recent_trades" in report
        
        assert isinstance(report["account"], dict)
        assert isinstance(report["metrics"], dict)
        assert isinstance(report["positions"], dict)
        assert isinstance(report["recent_trades"], list)

    def test_start_stop_engine(self):
        """Test starting and stopping the engine"""
        # Start engine
        self.engine.start()
        assert self.engine.running == True
        assert self.engine.engine_thread is not None
        
        # Stop engine
        self.engine.stop()
        assert self.engine.running == False


class TestGlobalFunctions:
    """Test global functions"""
    
    def setup_method(self):
        """Setup test method"""
        # Clean up any existing engine
        stop_paper_trading()

    def test_create_paper_trading_engine(self):
        """Test creating paper trading engine"""
        config = PaperTradingConfig(symbols=["BTCUSDc"])
        engine = create_paper_trading_engine(config)
        
        assert engine is not None
        assert engine.config == config
        assert get_paper_trading_engine() == engine

    def test_start_paper_trading(self):
        """Test starting paper trading"""
        config = PaperTradingConfig(symbols=["BTCUSDc"])
        engine = start_paper_trading(config)
        
        assert engine is not None
        assert engine.running == True
        assert get_paper_trading_engine() == engine

    def test_stop_paper_trading(self):
        """Test stopping paper trading"""
        config = PaperTradingConfig(symbols=["BTCUSDc"])
        start_paper_trading(config)
        
        stop_paper_trading()
        assert get_paper_trading_engine() is None

    def test_get_paper_trading_status(self):
        """Test getting paper trading status"""
        # No engine
        status = get_paper_trading_status()
        assert status["running"] == False
        assert "error" in status
        
        # With engine
        config = PaperTradingConfig(symbols=["BTCUSDc"])
        start_paper_trading(config)
        
        status = get_paper_trading_status()
        assert status["running"] == True
        assert "account" in status
        assert "metrics" in status

    def test_place_paper_order(self):
        """Test placing paper order via global function"""
        config = PaperTradingConfig(symbols=["BTCUSDc"])
        start_paper_trading(config)
        
        order = place_paper_order("BTCUSDc", "buy", "market", 0.1)
        assert order is not None
        assert order.symbol == "BTCUSDc"
        assert order.side == PaperOrderSide.BUY
        assert order.order_type == PaperOrderType.MARKET
        assert order.quantity == 0.1

    def test_place_paper_order_invalid_side(self):
        """Test placing paper order with invalid side"""
        config = PaperTradingConfig(symbols=["BTCUSDc"])
        start_paper_trading(config)
        
        order = place_paper_order("BTCUSDc", "invalid", "market", 0.1)
        assert order is None

    def test_close_paper_position(self):
        """Test closing paper position via global function"""
        config = PaperTradingConfig(symbols=["BTCUSDc"])
        start_paper_trading(config)
        
        # No position to close
        success = close_paper_position("BTCUSDc")
        assert success == False

    def test_get_paper_trading_report(self):
        """Test getting paper trading report via global function"""
        # No engine
        report = get_paper_trading_report()
        assert "error" in report
        
        # With engine
        config = PaperTradingConfig(symbols=["BTCUSDc"])
        start_paper_trading(config)
        
        report = get_paper_trading_report()
        assert "account" in report
        assert "metrics" in report
        assert "positions" in report
        assert "recent_trades" in report


class TestPaperTradingIntegration:
    """Test paper trading integration scenarios"""
    
    def setup_method(self):
        """Setup test method"""
        self.config = PaperTradingConfig(
            symbols=["BTCUSDc", "XAUUSDc"],
            initial_balance=100000.0,  # Larger balance for testing
            position_size_percent=0.1,  # 10% max position size for testing
            max_daily_trades=100
        )
        self.engine = PaperTradingEngine(self.config)

    def test_complete_trading_scenario(self):
        """Test complete trading scenario"""
        # Start engine
        self.engine.start()
        
        # Update market data
        btc_data = MarketData(
            symbol="BTCUSDc",
            timestamp=time.time(),
            bid=50000.0,
            ask=50010.0,
            last=50005.0,
            volume=1.0,
            spread=10.0,
            source="mt5"
        )
        self.engine.update_market_data("BTCUSDc", btc_data)
        
        # Place buy order
        order = self.engine.place_order(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=0.1
        )
        
        # Process order (simulate order filling)
        self.engine._process_order(order)
        
        # Check position was created
        positions = self.engine.get_positions()
        assert "BTCUSDc" in positions
        
        # Update market data with price increase
        btc_data_up = MarketData(
            symbol="BTCUSDc",
            timestamp=time.time(),
            bid=51000.0,
            ask=51010.0,
            last=51005.0,
            volume=1.0,
            spread=10.0,
            source="mt5"
        )
        self.engine.update_market_data("BTCUSDc", btc_data_up)
        
        # Close position
        success = self.engine.close_position("BTCUSDc")
        assert success
        
        # Check trade was closed
        positions = self.engine.get_positions()
        assert "BTCUSDc" not in positions
        
        # Check performance metrics
        metrics = self.engine.get_performance_metrics()
        assert metrics.total_trades > 0
        
        # Stop engine
        self.engine.stop()

    def test_risk_management_scenario(self):
        """Test risk management scenario"""
        # Set strict limits
        self.config.max_daily_trades = 2
        self.config.position_size_percent = 0.05  # 5% max position size
        
        # Try to place large order
        order = self.engine.place_order(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=1.0  # Very large position
        )
        
        # Update market data
        btc_data = MarketData(
            symbol="BTCUSDc",
            timestamp=time.time(),
            bid=50000.0,
            ask=50010.0,
            last=50005.0,
            volume=1.0,
            spread=10.0,
            source="mt5"
        )
        self.engine.update_market_data("BTCUSDc", btc_data)
        
        # Process order - should be rejected due to size
        self.engine._process_order(order)
        
        # Check order was rejected
        updated_order = self.engine.order_manager.get_order(order.order_id)
        assert updated_order.status == PaperOrderStatus.REJECTED
        assert "Position size too large" in updated_order.metadata.get("rejection_reason", "")

    def test_multiple_symbols_scenario(self):
        """Test trading multiple symbols"""
        # Update market data for both symbols
        btc_data = MarketData(
            symbol="BTCUSDc",
            timestamp=time.time(),
            bid=50000.0,
            ask=50010.0,
            last=50005.0,
            volume=1.0,
            spread=10.0,
            source="mt5"
        )
        
        gold_data = MarketData(
            symbol="XAUUSDc",
            timestamp=time.time(),
            bid=1800.0,
            ask=1805.0,
            last=1802.5,
            volume=2.0,
            spread=5.0,
            source="mt5"
        )
        
        self.engine.update_market_data("BTCUSDc", btc_data)
        self.engine.update_market_data("XAUUSDc", gold_data)
        
        # Place orders for both symbols
        btc_order = self.engine.place_order(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=0.1
        )
        
        gold_order = self.engine.place_order(
            symbol="XAUUSDc",
            side=PaperOrderSide.SELL,
            order_type=PaperOrderType.MARKET,
            quantity=1.0
        )
        
        # Process both orders
        self.engine._process_order(btc_order)
        self.engine._process_order(gold_order)
        
        # Check both positions were created
        positions = self.engine.get_positions()
        assert "BTCUSDc" in positions
        assert "XAUUSDc" in positions
        assert len(positions) == 2

    def test_performance_metrics_calculation(self):
        """Test performance metrics calculation"""
        # Create some trades manually for testing
        trade1 = self.engine.trade_manager.create_trade(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            quantity=0.1,
            entry_price=50000.0
        )
        
        trade2 = self.engine.trade_manager.create_trade(
            symbol="XAUUSDc",
            side=PaperOrderSide.SELL,
            quantity=1.0,
            entry_price=1800.0
        )
        
        # Close trades with different outcomes
        self.engine.trade_manager.close_trade(trade1.trade_id, 51000.0)  # Profit
        self.engine.trade_manager.close_trade(trade2.trade_id, 1850.0)   # Loss
        
        # Update metrics
        self.engine._update_metrics()
        
        # Check metrics
        metrics = self.engine.get_performance_metrics()
        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.win_rate == 0.5
        assert metrics.total_pnl == 50.0  # 100 - 50
        assert metrics.gross_profit == 100.0
        assert metrics.gross_loss == 50.0
        assert metrics.profit_factor == 2.0

    def test_database_operations(self):
        """Test database operations"""
        # Create some test data using the engine's methods
        trade = self.engine.trade_manager.create_trade(
            symbol="BTCUSDc",
            side=PaperOrderSide.BUY,
            quantity=0.1,
            entry_price=50000.0
        )
        
        # Use the engine's close trade method which saves to database
        self.engine._close_trade(trade, 51000.0, "Test close")
        
        # Update metrics to trigger database save
        self.engine._update_metrics()
        self.engine._save_performance_data()
        
        # Check database was created
        assert self.engine.db_path.exists()
        
        # Verify data was saved
        with sqlite3.connect(self.engine.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM paper_trades")
            trade_count = cursor.fetchone()[0]
            assert trade_count > 0
            
            cursor.execute("SELECT COUNT(*) FROM performance_metrics")
            metrics_count = cursor.fetchone()[0]
            assert metrics_count > 0
