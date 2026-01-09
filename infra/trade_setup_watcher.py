import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

from .mt5_service import MT5Service
from .indicator_bridge import IndicatorBridge
from .session_analyzer import SessionAnalyzer
from .exit_signal_detector import ExitSignalDetector
# from .risk_simulation import RiskSimulation  # Not needed for setup watching
from config import settings

@dataclass
class TradeSetupCondition:
    """Represents a condition that must be met for a trade setup"""
    timeframe: str
    indicator: str
    condition: str
    current_value: float
    required_value: float
    met: bool
    description: str

@dataclass
class TradeSetupAlert:
    """Represents an alert when trade setup conditions are met"""
    symbol: str
    action: str  # BUY or SELL
    confidence: int
    conditions_met: List[TradeSetupCondition]
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    risk_reward: Optional[float]
    timestamp: datetime
    message: str

class TradeSetupWatcher:
    """Watches for trade setup conditions and sends alerts when met"""
    
    def __init__(self, config):
        self.config = config
        self.mt5_service = MT5Service()  # MT5Service doesn't take config argument
        self.indicator_bridge = IndicatorBridge(None)  # Pass None for config
        self.session_analyzer = SessionAnalyzer()  # No config needed
        self.exit_signal_detector = ExitSignalDetector()  # Uses default thresholds
        # self.risk_simulation = RiskSimulation(config)  # Not needed for setup watching
        
        # Track active setups
        self.active_setups: Dict[str, Dict] = {}
        self.setup_history: List[TradeSetupAlert] = []
        
        # Setup conditions thresholds
        self.setup_conditions = {
            'BUY': {
                'H4': {'rsi_min': 50, 'adx_min': 25, 'ema_alignment': 'bullish'},
                'H1': {'rsi_min': 50, 'macd_status': 'bullish', 'price_vs_ema20': 'above'},
                'M30': {'rsi_min': 50, 'ema_alignment': 'bullish', 'atr_min': 5.0},
                'M15': {'rsi_min': 50, 'macd_status': 'bullish', 'price_vs_ema20': 'above'},
                'M5': {'rsi_min': 50, 'macd_status': 'bullish', 'price_vs_ema20': 'above'}
            },
            'SELL': {
                'H4': {'rsi_max': 50, 'adx_min': 25, 'ema_alignment': 'bearish'},
                'H1': {'rsi_max': 50, 'macd_status': 'bearish', 'price_vs_ema20': 'below'},
                'M30': {'rsi_max': 50, 'ema_alignment': 'bearish', 'atr_min': 5.0},
                'M15': {'rsi_max': 50, 'macd_status': 'bearish', 'price_vs_ema20': 'below'},
                'M5': {'rsi_max': 50, 'macd_status': 'bearish', 'price_vs_ema20': 'below'}
            }
        }
        
        self.logger = logging.getLogger(__name__)
    
    def _get_ema_alignment(self, tf_data: Dict) -> str:
        """Determine EMA alignment from timeframe data"""
        close = tf_data.get('current_close', 0.0)
        ema20 = tf_data.get('ema20', 0.0)
        ema50 = tf_data.get('ema50', 0.0)
        
        if close > ema20 > ema50:
            return 'bullish'
        elif close < ema20 < ema50:
            return 'bearish'
        else:
            return 'neutral'
    
    async def check_setup_conditions(self, symbol: str, action: str) -> Tuple[bool, List[TradeSetupCondition], int]:
        """Check if all setup conditions are met for a given symbol and action"""
        try:
            # Get multi-timeframe data from indicator bridge
            # Note: IndicatorBridge.get_multi() is synchronous, not async
            multi_data = self.indicator_bridge.get_multi(symbol)
            if not multi_data:
                return False, [], 0
            
            # Build mtf_analysis structure from multi_data
            mtf_analysis = {
                'timeframes': {}
            }
            
            # Extract data for each timeframe
            for tf in ['H4', 'H1', 'M30', 'M15', 'M5']:
                if tf in multi_data:
                    tf_data = multi_data[tf]
                    mtf_analysis['timeframes'][tf] = {
                        'rsi': tf_data.get('rsi', 50.0),
                        'adx': tf_data.get('adx', 0.0),
                        'atr': tf_data.get('atr14', 0.0),
                        'ema20': tf_data.get('ema20', 0.0),
                        'ema50': tf_data.get('ema50', 0.0),
                        'ema200': tf_data.get('ema200', 0.0),
                        'macd': tf_data.get('macd', 0.0),
                        'macd_signal': tf_data.get('macd_signal', 0.0),
                        'macd_histogram': tf_data.get('macd_histogram', 0.0),
                        'close': tf_data.get('current_close', 0.0),
                        # Determine ema_alignment
                        'ema_alignment': self._get_ema_alignment(tf_data),
                        # Determine macd_status
                        'macd_status': 'bullish' if tf_data.get('macd', 0) > tf_data.get('macd_signal', 0) else 'bearish',
                        # Determine price_vs_ema20
                        'price_vs_ema20': 'above' if tf_data.get('current_close', 0) > tf_data.get('ema20', 0) else 'below'
                    }
            
            if not mtf_analysis['timeframes']:
                return False, [], 0
            
            conditions_met = []
            total_confidence = 0
            conditions_count = 0
            
            # Check each timeframe
            for tf in ['H4', 'H1', 'M30', 'M15', 'M5']:
                if tf not in mtf_analysis['timeframes']:
                    continue
                
                tf_data = mtf_analysis['timeframes'][tf]
                tf_conditions = self.setup_conditions[action].get(tf, {})
                
                # Check RSI condition
                if 'rsi_min' in tf_conditions:
                    rsi_value = tf_data.get('rsi', 0)
                    rsi_met = rsi_value >= tf_conditions['rsi_min']
                    conditions_met.append(TradeSetupCondition(
                        timeframe=tf,
                        indicator='RSI',
                        condition=f'>= {tf_conditions["rsi_min"]}',
                        current_value=rsi_value,
                        required_value=tf_conditions['rsi_min'],
                        met=rsi_met,
                        description=f'{tf} RSI {rsi_value:.1f} >= {tf_conditions["rsi_min"]}'
                    ))
                    if rsi_met:
                        total_confidence += 20
                    conditions_count += 1
                
                elif 'rsi_max' in tf_conditions:
                    rsi_value = tf_data.get('rsi', 0)
                    rsi_met = rsi_value <= tf_conditions['rsi_max']
                    conditions_met.append(TradeSetupCondition(
                        timeframe=tf,
                        indicator='RSI',
                        condition=f'<= {tf_conditions["rsi_max"]}',
                        current_value=rsi_value,
                        required_value=tf_conditions['rsi_max'],
                        met=rsi_met,
                        description=f'{tf} RSI {rsi_value:.1f} <= {tf_conditions["rsi_max"]}'
                    ))
                    if rsi_met:
                        total_confidence += 20
                    conditions_count += 1
                
                # Check MACD condition
                if 'macd_status' in tf_conditions:
                    macd_status = tf_data.get('macd_status', '')
                    macd_met = macd_status == tf_conditions['macd_status']
                    conditions_met.append(TradeSetupCondition(
                        timeframe=tf,
                        indicator='MACD',
                        condition=f'== {tf_conditions["macd_status"]}',
                        current_value=1 if macd_met else 0,
                        required_value=1,
                        met=macd_met,
                        description=f'{tf} MACD {macd_status} == {tf_conditions["macd_status"]}'
                    ))
                    if macd_met:
                        total_confidence += 15
                    conditions_count += 1
                
                # Check price vs EMA20 condition
                if 'price_vs_ema20' in tf_conditions:
                    price_vs_ema20 = tf_data.get('price_vs_ema20', '')
                    price_met = price_vs_ema20 == tf_conditions['price_vs_ema20']
                    conditions_met.append(TradeSetupCondition(
                        timeframe=tf,
                        indicator='Price vs EMA20',
                        condition=f'== {tf_conditions["price_vs_ema20"]}',
                        current_value=1 if price_met else 0,
                        required_value=1,
                        met=price_met,
                        description=f'{tf} Price {price_vs_ema20} EMA20'
                    ))
                    if price_met:
                        total_confidence += 15
                    conditions_count += 1
                
                # Check EMA alignment
                if 'ema_alignment' in tf_conditions:
                    ema_alignment = tf_data.get('ema_alignment', '')
                    ema_met = ema_alignment == tf_conditions['ema_alignment']
                    conditions_met.append(TradeSetupCondition(
                        timeframe=tf,
                        indicator='EMA Alignment',
                        condition=f'== {tf_conditions["ema_alignment"]}',
                        current_value=1 if ema_met else 0,
                        required_value=1,
                        met=ema_met,
                        description=f'{tf} EMA {ema_alignment}'
                    ))
                    if ema_met:
                        total_confidence += 10
                    conditions_count += 1
                
                # Check ADX condition
                if 'adx_min' in tf_conditions:
                    adx_value = tf_data.get('adx', 0)
                    adx_met = adx_value >= tf_conditions['adx_min']
                    conditions_met.append(TradeSetupCondition(
                        timeframe=tf,
                        indicator='ADX',
                        condition=f'>= {tf_conditions["adx_min"]}',
                        current_value=adx_value,
                        required_value=tf_conditions['adx_min'],
                        met=adx_met,
                        description=f'{tf} ADX {adx_value:.1f} >= {tf_conditions["adx_min"]}'
                    ))
                    if adx_met:
                        total_confidence += 10
                    conditions_count += 1
                
                # Check ATR condition
                if 'atr_min' in tf_conditions:
                    atr_value = tf_data.get('atr', 0)
                    atr_met = atr_value >= tf_conditions['atr_min']
                    conditions_met.append(TradeSetupCondition(
                        timeframe=tf,
                        indicator='ATR',
                        condition=f'>= {tf_conditions["atr_min"]}',
                        current_value=atr_value,
                        required_value=tf_conditions['atr_min'],
                        met=atr_met,
                        description=f'{tf} ATR {atr_value:.2f} >= {tf_conditions["atr_min"]}'
                    ))
                    if atr_met:
                        total_confidence += 5
                    conditions_count += 1
            
            # Calculate overall confidence
            if conditions_count > 0:
                overall_confidence = int(total_confidence / conditions_count)
            else:
                overall_confidence = 0
            
            # Check if all conditions are met
            all_met = all(condition.met for condition in conditions_met)
            
            return all_met, conditions_met, overall_confidence
            
        except Exception as e:
            self.logger.error(f"Error checking setup conditions for {symbol} {action}: {e}")
            return False, [], 0
    
    async def generate_trade_alert(self, symbol: str, action: str, conditions_met: List[TradeSetupCondition], confidence: int) -> TradeSetupAlert:
        """Generate a trade alert with entry, SL, TP levels"""
        try:
            # Get current price (synchronous call)
            quote = self.mt5_service.get_quote(symbol)
            current_price = {'ask': quote.ask, 'bid': quote.bid}
            
            # Get ATR from indicator bridge (synchronous call)
            multi_data = self.indicator_bridge.get_multi(symbol)
            m5_data = multi_data.get('M5', {}) if multi_data else {}
            atr = m5_data.get('atr14', 10.0)
            
            # Calculate entry, SL, TP
            if action == 'BUY':
                entry_price = current_price['ask']
                stop_loss = entry_price - (atr * 2.0)  # 2 ATR stop
                take_profit = entry_price + (atr * 3.0)  # 1.5:1 RR
            else:  # SELL
                entry_price = current_price['bid']
                stop_loss = entry_price + (atr * 2.0)  # 2 ATR stop
                take_profit = entry_price - (atr * 3.0)  # 1.5:1 RR
            
            # Calculate risk-reward ratio
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            risk_reward = reward / risk if risk > 0 else 0
            
            # Create alert message
            conditions_text = "\n".join([f"✅ {c.description}" for c in conditions_met if c.met])
            conditions_text += "\n".join([f"❌ {c.description}" for c in conditions_met if not c.met])
            
            message = f"""
🎯 **{action} SETUP ALERT - {symbol}**

**Confidence: {confidence}%**

**Entry Price:** {entry_price:.5f}
**Stop Loss:** {stop_loss:.5f}
**Take Profit:** {take_profit:.5f}
**Risk/Reward:** 1:{risk_reward:.1f}

**Conditions Met:**
{conditions_text}

**Action Required:** Review and execute if conditions align with your strategy.
            """.strip()
            
            return TradeSetupAlert(
                symbol=symbol,
                action=action,
                confidence=confidence,
                conditions_met=conditions_met,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward=risk_reward,
                timestamp=datetime.now(),
                message=message
            )
            
        except Exception as e:
            self.logger.error(f"Error generating trade alert for {symbol} {action}: {e}")
            return None
    
    async def watch_setup(self, symbol: str, action: str, min_confidence: int = 70) -> Optional[TradeSetupAlert]:
        """Watch for a specific setup and return alert when conditions are met"""
        try:
            # Check if setup is already being watched
            setup_key = f"{symbol}_{action}"
            if setup_key in self.active_setups:
                return None  # Already watching
            
            # Mark as being watched
            self.active_setups[setup_key] = {
                'symbol': symbol,
                'action': action,
                'started_at': datetime.now(),
                'min_confidence': min_confidence
            }
            
            # Check conditions
            all_met, conditions_met, confidence = await self.check_setup_conditions(symbol, action)
            
            if all_met and confidence >= min_confidence:
                # Generate alert
                alert = await self.generate_trade_alert(symbol, action, conditions_met, confidence)
                if alert:
                    self.setup_history.append(alert)
                    return alert
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error watching setup for {symbol} {action}: {e}")
            return None
    
    async def stop_watching(self, symbol: str, action: str):
        """Stop watching a specific setup"""
        setup_key = f"{symbol}_{action}"
        if setup_key in self.active_setups:
            del self.active_setups[setup_key]
    
    async def get_active_setups(self) -> List[Dict]:
        """Get list of currently watched setups"""
        return list(self.active_setups.values())
    
    async def get_setup_history(self, limit: int = 10) -> List[TradeSetupAlert]:
        """Get recent setup alerts"""
        return self.setup_history[-limit:]
    
    async def clear_setup_history(self):
        """Clear setup history"""
        self.setup_history.clear()
